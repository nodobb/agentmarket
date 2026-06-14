"""
Stripe Connect tests: vendor onboarding, split charges, and split refunds.
Stripe's API is mocked throughout.
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
from tests.test_payments import attach_card, fake_payment_method  # noqa: F401


@pytest.fixture
def stripe_configured(monkeypatch):
    monkeypatch.setattr(payments.settings, "STRIPE_SECRET_KEY", "sk_test_fake")


def connected_account(charges_enabled=True, payouts_enabled=True):
    return SimpleNamespace(
        id="acct_123", charges_enabled=charges_enabled, payouts_enabled=payouts_enabled
    )


# --- onboarding ---------------------------------------------------------------


def test_onboarding_requires_stripe(client):
    headers = register_and_login(client, "vendor@example.com")
    create_vendor_with_product(client, headers)
    resp = client.post("/api/vendors/connect/onboard", headers=headers)
    assert resp.status_code == 400
    assert "not configured" in resp.json()["detail"]


def test_onboarding_creates_account_and_link(client, stripe_configured):
    headers = register_and_login(client, "vendor@example.com")
    create_vendor_with_product(client, headers)

    with patch.object(payments.stripe.Account, "create",
                      return_value=SimpleNamespace(id="acct_123")) as acct, \
         patch.object(payments.stripe.AccountLink, "create",
                      return_value=SimpleNamespace(url="https://connect.stripe.com/setup/x")) as link:
        resp = client.post("/api/vendors/connect/onboard", headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["onboarding_url"].startswith("https://connect.stripe.com/")
    assert acct.call_args.kwargs["type"] == "express"
    assert link.call_args.kwargs["account"] == "acct_123"

    # second call reuses the stored account instead of creating another
    with patch.object(payments.stripe.Account, "create") as acct2, \
         patch.object(payments.stripe.AccountLink, "create",
                      return_value=SimpleNamespace(url="https://connect.stripe.com/setup/y")):
        resp = client.post("/api/vendors/connect/onboard", headers=headers)
    assert resp.status_code == 200
    assert not acct2.called


def test_connect_status(client, stripe_configured):
    headers = register_and_login(client, "vendor@example.com")
    create_vendor_with_product(client, headers)

    resp = client.get("/api/vendors/connect/status", headers=headers)
    assert resp.json() == {"connected": False, "charges_enabled": False, "payouts_enabled": False}

    with patch.object(payments.stripe.Account, "create",
                      return_value=SimpleNamespace(id="acct_123")), \
         patch.object(payments.stripe.AccountLink, "create",
                      return_value=SimpleNamespace(url="https://connect.stripe.com/setup/x")):
        client.post("/api/vendors/connect/onboard", headers=headers)

    with patch.object(payments.stripe.Account, "retrieve",
                      return_value=connected_account()):
        resp = client.get("/api/vendors/connect/status", headers=headers)
    assert resp.json() == {"connected": True, "charges_enabled": True, "payouts_enabled": True}


# --- split charges ------------------------------------------------------------


def connected_marketplace(client, charges_enabled=True):
    """Vendor with a Connect account + an agent with a card. When
    charges_enabled, a status check populates the cached flag the checkout
    path reads."""
    vendor_headers = register_and_login(client, "vendor@example.com")
    create_vendor_with_product(client, vendor_headers)
    with patch.object(payments.stripe.Account, "create",
                      return_value=SimpleNamespace(id="acct_123")), \
         patch.object(payments.stripe.AccountLink, "create",
                      return_value=SimpleNamespace(url="https://connect.stripe.com/setup/x")):
        assert client.post("/api/vendors/connect/onboard", headers=vendor_headers).status_code == 200

    # A status check refreshes the cached stripe_charges_enabled flag
    with patch.object(payments.stripe.Account, "retrieve",
                      return_value=connected_account(charges_enabled=charges_enabled)):
        client.get("/api/vendors/connect/status", headers=vendor_headers)

    owner_headers = register_and_login(client, "owner@example.com")
    agent_headers = provision_agent(client, owner_headers)
    assert attach_card(client, owner_headers).status_code == 200
    return owner_headers, agent_headers


def test_charge_splits_to_connected_vendor(client, stripe_configured):
    _, agent_headers = connected_marketplace(client)

    dry_run = client.post("/api/agents/dry-run", headers=agent_headers,
                          json={"product_id": "credits-1k", "quantity": 1}).json()

    # No Stripe Account call needed at checkout - the cached flag drives the split
    with patch.object(payments.stripe.PaymentIntent, "create",
                      return_value=SimpleNamespace(id="pi_1", latest_charge="ch_1")) as intent:
        resp = client.post("/api/agents/commit", headers=agent_headers,
                           json={"handshake_token": dry_run["handshake_token"]})

    assert resp.status_code == 200, resp.text
    kwargs = intent.call_args.kwargs
    assert kwargs["transfer_data"] == {"destination": "acct_123"}
    assert kwargs["application_fee_amount"] == int(round(dry_run["commission"] * 100))


def test_charge_does_not_split_until_onboarding_complete(client, stripe_configured):
    _, agent_headers = connected_marketplace(client, charges_enabled=False)

    dry_run = client.post("/api/agents/dry-run", headers=agent_headers,
                          json={"product_id": "credits-1k", "quantity": 1}).json()

    with patch.object(payments.stripe.PaymentIntent, "create",
                      return_value=SimpleNamespace(id="pi_1", latest_charge="ch_1")) as intent:
        resp = client.post("/api/agents/commit", headers=agent_headers,
                           json={"handshake_token": dry_run["handshake_token"]})

    assert resp.status_code == 200, resp.text
    kwargs = intent.call_args.kwargs
    assert "transfer_data" not in kwargs
    assert "application_fee_amount" not in kwargs


# --- split refunds ------------------------------------------------------------


def test_refund_reverses_vendor_transfer(client, stripe_configured):
    owner_headers, agent_headers = connected_marketplace(client)

    dry_run = client.post("/api/agents/dry-run", headers=agent_headers,
                          json={"product_id": "credits-1k", "quantity": 1}).json()
    with patch.object(payments.stripe.PaymentIntent, "create",
                      return_value=SimpleNamespace(id="pi_1", latest_charge="ch_1")):
        assert client.post("/api/agents/commit", headers=agent_headers,
                           json={"handshake_token": dry_run["handshake_token"]}).status_code == 200

    tx_id = client.get("/api/transactions/", headers=owner_headers).json()[0]["id"]

    with patch.object(payments.stripe.PaymentIntent, "retrieve",
                      return_value=SimpleNamespace(id="pi_1", transfer_data={"destination": "acct_123"})), \
         patch.object(payments.stripe.Refund, "create",
                      return_value=SimpleNamespace(id="re_1")) as refund:
        resp = client.post(f"/api/transactions/{tx_id}/refund", headers=owner_headers)

    assert resp.status_code == 200, resp.text
    kwargs = refund.call_args.kwargs
    assert kwargs["reverse_transfer"] is True
    assert kwargs["refund_application_fee"] is True


def test_refund_of_unsplit_charge_does_not_reverse(client, stripe_configured, monkeypatch):
    # commit in simulated mode (no Stripe), then refund with Stripe on:
    # no payment intent exists, so the refund stays simulated
    monkeypatch.setattr(payments.settings, "STRIPE_SECRET_KEY", None)
    vendor_headers = register_and_login(client, "vendor@example.com")
    create_vendor_with_product(client, vendor_headers)
    owner_headers = register_and_login(client, "owner@example.com")
    agent_headers = provision_agent(client, owner_headers)
    dry_run = client.post("/api/agents/dry-run", headers=agent_headers,
                          json={"product_id": "credits-1k", "quantity": 1}).json()
    assert client.post("/api/agents/commit", headers=agent_headers,
                       json={"handshake_token": dry_run["handshake_token"]}).status_code == 200

    monkeypatch.setattr(payments.settings, "STRIPE_SECRET_KEY", "sk_test_fake")
    tx_id = client.get("/api/transactions/", headers=owner_headers).json()[0]["id"]
    resp = client.post(f"/api/transactions/{tx_id}/refund", headers=owner_headers)
    assert resp.status_code == 200
    assert resp.json()["payment_mode"] == "simulated"
