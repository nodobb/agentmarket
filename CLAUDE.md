# AgentMarket — project context

B2A (Business-to-Agent) marketplace: AI agents discover and purchase services
via API with safety controls. FastAPI + SQLAlchemy + Stripe. Owner (nodobb) is
a beginner — explain steps plainly, avoid jargon, handle git/PR mechanics for
them.

## How to run and test

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                      # full suite must pass before any merge
uvicorn main:app --reload   # serves on :8000
```

## Architecture map

- `main.py` — app entry; pages (`/`, `/legal`, `/demo`, `/dashboard`,
  `/docs-agent`), startup guard refuses default secrets when `DEBUG=false`
- `agentmarket/api/` — `auth` (JWT, login form-encoded), `vendors`,
  `agents` (agent registration + X-Agent-API-Key endpoints: search,
  dry-run/commit two-phase purchase, payment-method), `transactions`
  (list/approve/refund; permissions are ownership-based, NOT role-based)
- `agentmarket/services/payments.py` — Stripe charging/refunds; without
  STRIPE_SECRET_KEY runs in "simulated" mode (responses carry `payment_mode`)
- `agentmarket/models/` — engine setup normalizes `postgres://`→`postgresql://`;
  `init_db` adds missing columns to existing DBs (no Alembic yet)
- `tests/` — pytest suite; rate limiting disabled in tests except
  `@pytest.mark.rate_limited`
- `render.yaml` — Render Blueprint: web service + managed Postgres,
  generated secrets, prompts for STRIPE_SECRET_KEY

## Money-safety invariants (do not regress)

- Inventory: conditional atomic update (`WHERE stock_count >= qty`) BEFORE
  charging; reservation rolls back if the charge fails (no oversell)
- Row locks (`with_for_update`) on commit/approve/refund so duplicate
  concurrent requests cannot double-charge or double-refund
- If `db.commit()` fails after a successful charge, `payments.reverse_charge`
  refunds it automatically
- Spending limits enforced at dry-run: per-transaction cap, daily budget
  (UTC day, refunds excluded), owner approval threshold

## Conventions in this repo

- Work on a session branch, push, open a draft PR, wait for CI (GitHub
  Actions runs pytest), then squash-merge; the owner has delegated merging
- gemini-code-assist bot reviews PRs — its feedback has been consistently
  worth addressing (it found the inventory races and double-charge risks);
  note: bot is sunset July 2026
- After a squash-merge, merge `origin/main` back into the working branch
  before new work, or the next PR will show conflicts

## Current state (June 2026)

- Live site: https://agentmarket.onrender.com (Render Blueprint "AgentMarket",
  service `agentmarket` + database `agentmarket-db`)
- **Stripe deadline June 25, 2026**: Stripe requires a business website on
  the account or payments shut off. Site is built (landing + /legal pages).
  Remaining: owner confirms deploy is Live, sets STRIPE_SECRET_KEY and
  SUPPORT_EMAIL env vars in Render, pastes URL into Stripe → Settings →
  Business details → Business website
- Stripe is in TEST mode (sk_test key); owner has standard + restricted keys
- Copilot was supposed to push a Stitch-designed landing page to
  `feature/landing-page-agentmarket` but never did (branch is empty);
  ours shipped instead — compare/swap only if the owner asks

## Open roadmap (in priority order)

1. Vendor payouts via Stripe Connect (platform currently keeps full amount;
   commission model is 2.5%)
2. Real tax/shipping (currently flat 8% / $5 merch placeholder)
3. Semantic product search (currently keyword matching)
4. Alembic migrations to replace the add-missing-columns shim
