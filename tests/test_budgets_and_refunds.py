"""
Tests for agent spending limits (per-transaction and daily budget)
and the refund flow.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agentmarket.services import payments
from tests.test_api import (
    register_and_login,
    create_vendor_with_product,
)


def provision_agent_with_limits(client, headers, *, approval_over=1000.0,
                                transaction_limit=1000.0, daily_budget=1000.0):
    resp = client.post("/api/agents/register", headers=headers, json={
        "name": "LimitBot",
        "requires_human_approval_over": approval_over,
        "transaction_limit": transaction_limit,
        "daily_budget_limit": daily_budget,
    })
    assert resp.status_code == 200, resp.text
    return {"X-Agent-API-Key": resp.json()["api_key"]}


def buy(client, agent_headers, quantity=1):
    """Dry-run and, if allowed, commit. Returns the dry-run body."""
    dry_run = client.post("/api/agents/dry-run", headers=agent_headers,
                          json={"product_id": "credits-1k", "quantity": quantity}).json()
    if not dry_run["requires_human_approval"]:
        resp = client.post("/api/agents/commit", headers=agent_headers,
                           json={"handshake_token": dry_run["handshake_token"]})
        assert resp.status_code == 200, resp.text
    return dry_run


def marketplace(client, **agent_limits):
    vendor_headers = register_and_login(client, "vendor@example.com")
    create_vendor_with_product(client, vendor_headers)  # $9.99 -> $10.79 with tax
    owner_headers = register_and_login(client, "owner@example.com")
    agent_headers = provision_agent_with_limits(client, owner_headers, **agent_limits)
    return owner_headers, agent_headers


# --- spending limits ---------------------------------------------------------


def test_per_transaction_limit_triggers_approval(client):
    _, agent_headers = marketplace(client, transaction_limit=15.0)

    assert buy(client, agent_headers, quantity=1)["requires_human_approval"] is False

    dry_run = client.post("/api/agents/dry-run", headers=agent_headers,
                          json={"product_id": "credits-1k", "quantity": 2}).json()
    assert dry_run["requires_human_approval"] is True
    assert "per-transaction limit" in dry_run["approval_reason"]


def test_daily_budget_triggers_approval(client):
    # Each purchase totals ~$10.79; a $25 daily budget allows two, not three
    _, agent_headers = marketplace(client, daily_budget=25.0)

    assert buy(client, agent_headers)["requires_human_approval"] is False
    assert buy(client, agent_headers)["requires_human_approval"] is False

    third = buy(client, agent_headers)
    assert third["requires_human_approval"] is True
    assert "daily budget" in third["approval_reason"]


def test_status_reports_remaining_budget(client):
    _, agent_headers = marketplace(client, daily_budget=100.0)
    buy(client, agent_headers)

    status = client.get("/api/agents/status", headers=agent_headers).json()
    assert status["daily_budget_remaining"] == pytest.approx(100.0 - 9.99 * 1.08, abs=0.01)


# --- refunds -----------------------------------------------------------------


def committed_purchase(client):
    owner_headers, agent_headers = marketplace(client)
    buy(client, agent_headers)
    tx_id = client.get("/api/transactions/", headers=owner_headers).json()[0]["id"]
    return owner_headers, agent_headers, tx_id


def test_refund_restores_stock_and_sets_status(client):
    owner_headers, agent_headers, tx_id = committed_purchase(client)

    resp = client.post(f"/api/transactions/{tx_id}/refund", headers=owner_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "refunded"
    assert body["payment_mode"] == "simulated"

    products = client.get("/api/agents/products", headers=agent_headers).json()
    assert products[0]["stock_available"] == 100

    # refunded money no longer counts against the daily budget
    status = client.get("/api/agents/status", headers=agent_headers).json()
    assert status["daily_budget_remaining"] == pytest.approx(1000.0)


def test_refund_cannot_be_repeated(client):
    owner_headers, _, tx_id = committed_purchase(client)
    assert client.post(f"/api/transactions/{tx_id}/refund", headers=owner_headers).status_code == 200
    resp = client.post(f"/api/transactions/{tx_id}/refund", headers=owner_headers)
    assert resp.status_code == 400


def test_stranger_cannot_refund(client):
    _, _, tx_id = committed_purchase(client)
    stranger_headers = register_and_login(client, "stranger@example.com")
    resp = client.post(f"/api/transactions/{tx_id}/refund", headers=stranger_headers)
    assert resp.status_code == 403


def test_refund_calls_stripe_when_charged(client, monkeypatch):
    owner_headers, agent_headers, tx_id = committed_purchase(client)

    # simulate that this transaction was charged through Stripe
    monkeypatch.setattr(payments.settings, "STRIPE_SECRET_KEY", "sk_test_fake")
    from agentmarket.models import SessionLocal
    from agentmarket.models.database import Transaction
    db = SessionLocal()
    db.query(Transaction).filter(Transaction.id == tx_id).update(
        {"stripe_payment_intent_id": "pi_123"})
    db.commit()
    db.close()

    with patch.object(payments.stripe.PaymentIntent, "retrieve",
                      return_value=SimpleNamespace(id="pi_123", transfer_data=None)), \
         patch.object(payments.stripe.Refund, "create",
                      return_value=SimpleNamespace(id="re_123")) as refund:
        resp = client.post(f"/api/transactions/{tx_id}/refund", headers=owner_headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["refund_id"] == "re_123"
    assert refund.call_args.kwargs["payment_intent"] == "pi_123"
