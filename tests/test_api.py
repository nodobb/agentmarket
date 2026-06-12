"""
End-to-end API tests covering the marketplace flows:
auth, vendor onboarding, agent provisioning, purchases, and approvals.
"""

import pytest


# --- helpers ---------------------------------------------------------------

def register_and_login(client, email, password="Testpass123!", full_name="Test User"):
    resp = client.post("/api/auth/register", json={
        "email": email, "password": password, "full_name": full_name,
    })
    assert resp.status_code == 200, resp.text
    resp = client.post("/api/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_vendor_with_product(client, headers, price=9.99, external_id="credits-1k", stock=100):
    resp = client.post("/api/vendors/register", headers=headers, json={
        "business_name": "Test Shop", "description": "Sells test products",
    })
    assert resp.status_code == 200, resp.text
    resp = client.post("/api/vendors/products", headers=headers, json={
        "external_id": external_id, "name": "1000 API Credits",
        "description": "Bulk API credits", "price": price,
        "category": "api_services", "tags": ["api", "credits"], "stock_count": stock,
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


def provision_agent(client, headers, approval_threshold=1000.0):
    resp = client.post("/api/agents/register", headers=headers, json={
        "name": "TestBot", "requires_human_approval_over": approval_threshold,
    })
    assert resp.status_code == 200, resp.text
    return {"X-Agent-API-Key": resp.json()["api_key"]}


# --- basics ----------------------------------------------------------------

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_public_pages_render(client):
    home = client.get("/")
    assert home.status_code == 200
    assert "AgentMarket" in home.text
    assert "2.5%" in home.text  # pricing must be visible

    legal = client.get("/legal")
    assert legal.status_code == 200
    for section in ("Terms of Service", "Privacy Policy", "Refund"):
        assert section in legal.text

    for path in ("/demo", "/dashboard", "/docs-agent", "/.well-known/agent-manifest.json"):
        assert client.get(path).status_code == 200, path


def test_register_login_me(client):
    headers = register_and_login(client, "user@example.com")
    resp = client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "user@example.com"
    assert body["role"] == "agent_owner"


def test_cannot_self_register_as_admin(client):
    resp = client.post("/api/auth/register", json={
        "email": "evil@example.com", "password": "Testpass123!",
        "full_name": "Evil", "role": "admin",
    })
    assert resp.status_code == 422


def test_agent_endpoints_reject_bad_api_key(client):
    resp = client.get("/api/agents/products", headers={"X-Agent-API-Key": "ak_wrong"})
    assert resp.status_code == 401


# --- agent provisioning ----------------------------------------------------

def test_agent_provisioning_and_listing(client):
    headers = register_and_login(client, "owner@example.com")

    resp = client.post("/api/agents/register", headers=headers, json={"name": "ShopBot"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["api_key"].startswith("ak_")

    resp = client.get("/api/agents/mine", headers=headers)
    assert resp.status_code == 200
    agents = resp.json()
    assert len(agents) == 1
    assert agents[0]["name"] == "ShopBot"
    # full key must not be exposed in listings
    assert body["api_key"] not in agents[0]["api_key_preview"]


# --- purchase flow ----------------------------------------------------------

def test_full_purchase_flow(client):
    vendor_headers = register_and_login(client, "vendor@example.com")
    create_vendor_with_product(client, vendor_headers)

    owner_headers = register_and_login(client, "owner@example.com")
    agent_headers = provision_agent(client, owner_headers)

    # discovery
    resp = client.get("/api/agents/products", params={"query": "api credits"},
                      headers=agent_headers)
    assert resp.status_code == 200
    products = resp.json()
    assert len(products) == 1
    assert products[0]["external_id"] == "credits-1k"

    # dry-run
    resp = client.post("/api/agents/dry-run", headers=agent_headers,
                       json={"product_id": "credits-1k", "quantity": 2})
    assert resp.status_code == 200
    dry_run = resp.json()
    assert dry_run["requires_human_approval"] is False
    assert dry_run["subtotal"] == pytest.approx(19.98)
    assert dry_run["total_cost"] == pytest.approx(19.98 * 1.08)

    # commit
    resp = client.post("/api/agents/commit", headers=agent_headers,
                       json={"handshake_token": dry_run["handshake_token"]})
    assert resp.status_code == 200
    commit = resp.json()
    assert commit["status"] == "completed"
    assert commit["payment_mode"] == "simulated"

    # inventory was decremented
    resp = client.get("/api/agents/products", headers=agent_headers)
    assert resp.json()[0]["stock_available"] == 98

    # a used handshake token cannot be replayed
    resp = client.post("/api/agents/commit", headers=agent_headers,
                       json={"handshake_token": dry_run["handshake_token"]})
    assert resp.status_code == 404


def test_commit_cannot_oversell(client):
    """Two valid handshakes for the last unit: only one commit may succeed."""
    vendor_headers = register_and_login(client, "vendor@example.com")
    create_vendor_with_product(client, vendor_headers, external_id="last-one", stock=1)
    agent_headers = provision_agent(client, register_and_login(client, "owner@example.com"))

    tokens = [
        client.post("/api/agents/dry-run", headers=agent_headers,
                    json={"product_id": "last-one", "quantity": 1}).json()["handshake_token"]
        for _ in range(2)
    ]
    results = [
        client.post("/api/agents/commit", headers=agent_headers,
                    json={"handshake_token": token}).status_code
        for token in tokens
    ]
    assert sorted(results) == [200, 400]

    products = client.get("/api/agents/products", headers=agent_headers).json()
    assert products[0]["stock_available"] == 0


def test_dry_run_rejects_insufficient_stock(client):
    vendor_headers = register_and_login(client, "vendor@example.com")
    create_vendor_with_product(client, vendor_headers)
    agent_headers = provision_agent(client, register_and_login(client, "owner@example.com"))

    resp = client.post("/api/agents/dry-run", headers=agent_headers,
                       json={"product_id": "credits-1k", "quantity": 101})
    assert resp.status_code == 400


# --- approval flow ----------------------------------------------------------

def approval_required_transaction(client, agent_headers):
    resp = client.post("/api/agents/dry-run", headers=agent_headers,
                       json={"product_id": "credits-1k", "quantity": 1})
    assert resp.status_code == 200
    dry_run = resp.json()
    assert dry_run["requires_human_approval"] is True
    return dry_run


def test_commit_blocked_until_approved(client):
    vendor_headers = register_and_login(client, "vendor@example.com")
    create_vendor_with_product(client, vendor_headers)
    owner_headers = register_and_login(client, "owner@example.com")
    agent_headers = provision_agent(client, owner_headers, approval_threshold=5.0)

    dry_run = approval_required_transaction(client, agent_headers)

    resp = client.post("/api/agents/commit", headers=agent_headers,
                       json={"handshake_token": dry_run["handshake_token"]})
    assert resp.status_code == 400
    assert "approval" in resp.json()["detail"].lower()

    # owner approves, which commits the transaction
    resp = client.get("/api/transactions/", headers=owner_headers,
                      params={"requires_approval": True})
    tx_id = resp.json()[0]["id"]
    resp = client.post(f"/api/transactions/{tx_id}/approve", headers=owner_headers,
                       json={"approved": True, "reason": "looks good"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "committed"


def test_owner_who_is_also_vendor_can_approve(client):
    """Regression test: registering as a vendor must not revoke the ability
    to approve your own agents' transactions."""
    headers = register_and_login(client, "both@example.com")
    agent_headers = provision_agent(client, headers, approval_threshold=5.0)
    create_vendor_with_product(client, headers)  # flips role to vendor

    dry_run = approval_required_transaction(client, agent_headers)
    assert dry_run["requires_human_approval"] is True

    resp = client.get("/api/transactions/", headers=headers,
                      params={"requires_approval": True})
    tx_id = resp.json()[0]["id"]
    resp = client.post(f"/api/transactions/{tx_id}/approve", headers=headers,
                       json={"approved": True})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "committed"


def test_stranger_cannot_approve_or_view(client):
    vendor_headers = register_and_login(client, "vendor@example.com")
    create_vendor_with_product(client, vendor_headers)
    owner_headers = register_and_login(client, "owner@example.com")
    agent_headers = provision_agent(client, owner_headers, approval_threshold=5.0)
    approval_required_transaction(client, agent_headers)

    resp = client.get("/api/transactions/", headers=owner_headers)
    tx_id = resp.json()[0]["id"]

    stranger_headers = register_and_login(client, "stranger@example.com")
    resp = client.post(f"/api/transactions/{tx_id}/approve", headers=stranger_headers,
                       json={"approved": True})
    assert resp.status_code == 403
    resp = client.get(f"/api/transactions/{tx_id}", headers=stranger_headers)
    assert resp.status_code == 403
    assert client.get("/api/transactions/", headers=stranger_headers).json() == []


# --- rate limiting ----------------------------------------------------------

@pytest.mark.rate_limited
def test_login_is_rate_limited(client):
    register_and_login(client, "user@example.com")
    statuses = [
        client.post("/api/auth/login",
                    data={"username": "user@example.com", "password": "bad"}).status_code
        for _ in range(12)
    ]
    assert 429 in statuses
