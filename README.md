# AgentMarket

A B2A (Business-to-Agent) marketplace where autonomous AI agents discover and
purchase services from vendors — built API-first, with safety controls
(budgets, approval thresholds, two-phase transactions) at the core.

> **Status: beta.** All marketplace flows work end-to-end. Purchases are
> charged through Stripe when `STRIPE_SECRET_KEY` is set (test keys charge
> Stripe's test environment, live keys charge real money). Without a key the
> app runs in simulated mode — transactions are recorded but nothing is
> charged. Every purchase response states which via `payment_mode`.

## How it works

1. **Vendors** register an account, create a vendor profile, and list products.
2. **Agent owners** register an account and provision agents — each agent gets
   an API key and safety limits (daily budget, per-transaction cap, and a
   threshold above which a human must approve).
3. **Agents** authenticate with their API key, search products, and buy using
   a two-phase protocol:
   - `POST /api/agents/dry-run` validates the purchase and returns full pricing
     plus a handshake token (expires in 5 minutes)
   - `POST /api/agents/commit` finalizes it — unless the amount crossed a
     safety limit, in which case the owner must approve it first via
     `POST /api/transactions/{id}/approve`

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open http://127.0.0.1:8000/docs for the interactive API docs, or
http://127.0.0.1:8000/ for the landing page.

### Try the full flow

```bash
BASE=http://127.0.0.1:8000

# 1. Create an account and log in
curl -X POST $BASE/api/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"me@example.com","password":"a-strong-password","full_name":"Me"}'
TOKEN=$(curl -s -X POST $BASE/api/auth/login \
  -d 'username=me@example.com&password=a-strong-password' | jq -r .access_token)

# 2. Become a vendor and list a product
curl -X POST $BASE/api/vendors/register -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"business_name":"My Shop","description":"API credits"}'
curl -X POST $BASE/api/vendors/products -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"external_id":"credits-1k","name":"1000 API Credits","description":"Bulk credits","price":9.99,"category":"api_services","tags":["api"],"stock_count":100}'

# 3. Provision an agent (the API key is shown once - save it)
KEY=$(curl -s -X POST $BASE/api/agents/register -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"ShopBot","requires_human_approval_over":25}' | jq -r .api_key)

# 4. The agent shops
curl "$BASE/api/agents/products?query=api+credits" -H "X-Agent-API-Key: $KEY"
HS=$(curl -s -X POST $BASE/api/agents/dry-run -H "X-Agent-API-Key: $KEY" \
  -H 'Content-Type: application/json' \
  -d '{"product_id":"credits-1k","quantity":1}' | jq -r .handshake_token)
curl -X POST $BASE/api/agents/commit -H "X-Agent-API-Key: $KEY" \
  -H 'Content-Type: application/json' -d "{\"handshake_token\":\"$HS\"}"
```

## Enabling real payments (Stripe)

1. Put your Stripe secret key in `.env` (locally) or the Render Environment
   tab (live site): `STRIPE_SECRET_KEY=sk_test_...` — start with a **test**
   key so no real money moves.
2. Attach a payment method to your agent. In test mode, Stripe provides
   ready-made cards like `pm_card_visa`:

   ```bash
   curl -X POST $BASE/api/agents/1/payment-method -H "Authorization: Bearer $TOKEN" \
     -H 'Content-Type: application/json' -d '{"payment_method_id":"pm_card_visa"}'
   ```

3. Purchase as usual. The commit response now shows `payment_mode: "test"`
   and the charge appears in your Stripe dashboard (in test mode).

To go live, swap in your `sk_live_...` key and attach real payment methods
(collected via Stripe.js/Elements so card numbers never touch this server).
Note: the platform currently collects the full amount; paying vendors their
share (Stripe Connect) is not built yet.

## Running the tests

```bash
pip install -r requirements.txt
pytest
```

## Configuration

Settings load from environment variables (or a `.env` file) — see
`agentmarket/utils/config.py` for the full list. Key ones:

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./agentmarket.db` | Use PostgreSQL in production |
| `SECRET_KEY` / `JWT_SECRET_KEY` | placeholders | **Required in production** — the app refuses to start with the defaults when `DEBUG=false` |
| `DEBUG` | `true` | Set `false` in production |
| `COMMISSION_RATE` | `0.025` | Platform commission (2.5%) |
| `RATE_LIMIT_PER_MINUTE` | `60` | Per-agent rate limit on agent endpoints |

## Deployment

`render.yaml` deploys to [Render](https://render.com) with a managed
PostgreSQL database and generated secrets — connect the repo in the Render
dashboard as a Blueprint and it should work out of the box. A `Procfile`
(Heroku-style) and `railway.json` are also included.

## Project structure

```
agentmarket/
├── api/            # Route handlers: auth, vendors, transactions, agents
├── models/         # SQLAlchemy models and DB session setup
├── services/       # Auth and analytics services
└── utils/          # Settings and rate limiting
frontend/           # Jinja2 templates and static files
tests/              # Pytest suite covering the API flows
main.py             # FastAPI app entry point
```

## What's not done yet

- **Vendor payouts** — purchases are charged to the platform's Stripe
  account; splitting revenue out to vendors needs Stripe Connect onboarding
- Tax (flat 8%) and shipping (flat $5 on merch) are placeholders
- Search is keyword matching, not semantic/vector search
