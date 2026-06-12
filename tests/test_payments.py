"""
Payment tests.

Stripe's API is mocked so tests run offline; the simulated mode (no key)
is covered by test_api.py's purchase-flow tests.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agentmarket.services import payments
from tests.test_api import (
    register_and_login,
    create_vendor_with_product,
    provision_agent,
)


@pytest.fixture
def stripe_configured(monkeypatch):
    monkeypatch.setattr(payments.settings, "STRIPE_SECRET_KEY", "sk_test_fake")


def fake_payment_method(pm_id="pm_card_visa"):
    return SimpleNamespace(
        id=pm_id, type="card", card=SimpleNamespace(brand="visa", last4="4242")
    )


def setup_purchase(client):
    vendor_headers = register_and_login(client, "vendor@example.com")
    create_vendor_with_product(client, vendor_headers)
    owner_headers = register_and_login(client, "owner@example.com")
    agent_headers = provision_agent(client, owner_headers)
    return owner_headers, agent_headers


def attach_card(client, owner_headers, agent_id=1):
    with patch.object(payments.stripe.Customer, "create",
                      return_value=SimpleNamespace(id="cus_123")), \
         patch.object(payments.stripe.PaymentMethod, "attach",
                      return_value=fake_payment_method()), \
         patch.object(payments.stripe.Customer, "modify"):
        return client.post(f"/api/agents/{agent_id}/payment-method",
                           headers=owner_headers,
                           json={"payment_method_id": "pm_card_visa"})


def test_attach_payment_method_requires_stripe(client):
    owner_headers, _ = setup_purchase(client)
    resp = client.post("/api/agents/1/payment-method", headers=owner_headers,
                       json={"payment_method_id": "pm_card_visa"})
    assert resp.status_code == 400
    assert "not configured" in resp.json()["detail"]


def test_attach_payment_method(client, stripe_configured):
    owner_headers, _ = setup_purchase(client)
    resp = attach_card(client, owner_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["payment_method"] == "visa ending in 4242"


def test_only_owner_can_attach_payment_method(client, stripe_configured):
    setup_purchase(client)
    stranger_headers = register_and_login(client, "stranger@example.com")
    resp = client.post("/api/agents/1/payment-method", headers=stranger_headers,
                       json={"payment_method_id": "pm_card_visa"})
    assert resp.status_code == 403


def test_commit_charges_saved_card(client, stripe_configured):
    owner_headers, agent_headers = setup_purchase(client)
    assert attach_card(client, owner_headers).status_code == 200

    dry_run = client.post("/api/agents/dry-run", headers=agent_headers,
                          json={"product_id": "credits-1k", "quantity": 1}).json()

    with patch.object(payments.stripe.PaymentIntent, "create",
                      return_value=SimpleNamespace(id="pi_123", latest_charge="ch_123")) as intent:
        resp = client.post("/api/agents/commit", headers=agent_headers,
                           json={"handshake_token": dry_run["handshake_token"]})

    assert resp.status_code == 200, resp.text
    assert resp.json()["payment_mode"] == "test"
    # charged the exact total, in cents, against the saved card
    kwargs = intent.call_args.kwargs
    assert kwargs["amount"] == int(round(dry_run["total_cost"] * 100))
    assert kwargs["customer"] == "cus_123"
    assert kwargs["payment_method"] == "pm_card_visa"
    assert kwargs["confirm"] is True


def test_commit_without_card_is_rejected(client, stripe_configured):
    _, agent_headers = setup_purchase(client)
    dry_run = client.post("/api/agents/dry-run", headers=agent_headers,
                          json={"product_id": "credits-1k", "quantity": 1}).json()
    resp = client.post("/api/agents/commit", headers=agent_headers,
                       json={"handshake_token": dry_run["handshake_token"]})
    assert resp.status_code == 402
    assert "no payment method" in resp.json()["detail"]


def test_declined_card_does_not_complete_purchase(client, stripe_configured):
    owner_headers, agent_headers = setup_purchase(client)
    assert attach_card(client, owner_headers).status_code == 200

    dry_run = client.post("/api/agents/dry-run", headers=agent_headers,
                          json={"product_id": "credits-1k", "quantity": 1}).json()

    decline = payments.stripe.CardError("declined", None, code="card_declined")
    with patch.object(payments.stripe.PaymentIntent, "create", side_effect=decline):
        resp = client.post("/api/agents/commit", headers=agent_headers,
                           json={"handshake_token": dry_run["handshake_token"]})
    assert resp.status_code == 402

    # stock untouched, and the handshake can be retried
    products = client.get("/api/agents/products", headers=agent_headers).json()
    assert products[0]["stock_available"] == 100


def test_reverse_charge_refunds_at_stripe(stripe_configured):
    with patch.object(payments.stripe.Refund, "create",
                      return_value=SimpleNamespace(id="re_1")) as refund:
        payments.reverse_charge({"payment_mode": "test", "payment_intent_id": "pi_9"}, 42)
    assert refund.call_args.kwargs["payment_intent"] == "pi_9"


def test_reverse_charge_skips_simulated_payments(stripe_configured):
    with patch.object(payments.stripe.Refund, "create") as refund:
        payments.reverse_charge({"payment_mode": "simulated", "payment_intent_id": None}, 42)
    assert not refund.called


def test_reverse_charge_never_raises(stripe_configured):
    boom = payments.stripe.StripeError("stripe down")
    with patch.object(payments.stripe.Refund, "create", side_effect=boom):
        payments.reverse_charge({"payment_mode": "test", "payment_intent_id": "pi_9"}, 42)


def test_approval_path_charges_card(client, stripe_configured):
    vendor_headers = register_and_login(client, "vendor@example.com")
    create_vendor_with_product(client, vendor_headers)
    owner_headers = register_and_login(client, "owner@example.com")
    agent_headers = provision_agent(client, owner_headers, approval_threshold=5.0)
    assert attach_card(client, owner_headers).status_code == 200

    dry_run = client.post("/api/agents/dry-run", headers=agent_headers,
                          json={"product_id": "credits-1k", "quantity": 1}).json()
    assert dry_run["requires_human_approval"] is True

    tx_id = client.get("/api/transactions/", headers=owner_headers,
                       params={"requires_approval": True}).json()[0]["id"]

    with patch.object(payments.stripe.PaymentIntent, "create",
                      return_value=SimpleNamespace(id="pi_456", latest_charge="ch_456")) as intent:
        resp = client.post(f"/api/transactions/{tx_id}/approve", headers=owner_headers,
                           json={"approved": True, "reason": "ok"})

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "committed"
    assert intent.called
