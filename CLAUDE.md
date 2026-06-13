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

- `main.py` — app entry; pages (`/`, `/vendors`, `/legal`, `/demo`,
  `/dashboard`, `/docs-agent`), startup guard refuses default secrets when
  `DEBUG=false`
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

- Live site: **https://agentmarket.tech** (custom domain, DNS A/@ + CNAME/www
  → Render; https://agentmarket.onrender.com is the same service). Render
  Blueprint "AgentMarket", service `agentmarket` + database `agentmarket-db`,
  both pinned to region oregon (cross-region broke DB connectivity once)
- **Stripe deadline June 25, 2026: DONE (June 12)** — business website
  (agentmarket.tech), product description, and support contact all filed in
  Stripe → Business details. Stripe is in TEST mode (sk_test key set in
  Render); owner has standard + restricted keys
- Owner email: support@agentmarket.tech ($3/mo hosted inbox). When the inbox
  is confirmed working, set SUPPORT_EMAIL=support@agentmarket.tech in Render
  (it renders in the site footer and /legal)
- Pages: `/` terminal-demo landing, `/vendors` plain-English vendor pitch,
  `/legal` (terms/privacy/refunds) — Stripe was pointed at these; keep them
  consistent with actual platform behavior
- Old Google-Docs terms/privacy from a previous project exist but contradict
  the platform (no-refunds clause); deliberately NOT used
- Copilot was supposed to push a Stitch-designed landing page to
  `feature/landing-page-agentmarket` but never did (branch is empty);
  ours shipped instead — compare/swap only if the owner asks

## Open roadmap (in priority order)

1. First customers: honest vendor outreach (NOTE: scripts/vendor_onboarding.py
   contains FABRICATED stats/social proof — never send as-is; an honest
   rewrite was drafted in the June 12 session chat)
2. Vendor payouts via Stripe Connect (platform currently keeps full amount;
   commission model is 2.5%; beta vendors are told payouts are manual)
3. Real tax/shipping (currently flat 8% / $5 merch placeholder)
4. Semantic product search (currently keyword matching)
5. Alembic migrations to replace the add-missing-columns shim
