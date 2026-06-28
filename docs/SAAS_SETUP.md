# kobeAi SaaS — Setup Guide

This turns kobeAi from a "bring-your-own-MuAPI-key" app into a **paid SaaS**:
users sign up, subscribe and/or buy credit packs, and every AI generation is
metered against their credit balance while being proxied through **your** single
MuAPI key.

## How it works

```
User ── login (Google / email magic link) ──► kobeAi
User ── pays (Stripe: subscription or credit pack) ──► credits added to account
User ── clicks "Generate" ──► /api/v1/... (gated)
            │  1. require signed-in session
            │  2. estimate credit cost for the model
            │  3. deduct credits (refund if upstream fails)
            └► forwards to MuAPI with MUAPI_PLATFORM_KEY (your key)
```

- **Auth:** Auth.js (NextAuth v5) — Google OAuth + passwordless email links.
- **Billing:** Stripe — monthly subscription plans *and* one-time credit packs.
- **Metering:** a Postgres-backed credit ledger; costs are configurable per
  model in `lib/billing-config.js`.
- **Gating:** `app/api/v1/[[...path]]/route.js` enforces auth + credits and
  injects your platform key. Client-supplied keys are ignored in SaaS mode.

## Architecture / key files

| Area | File |
|---|---|
| DB schema | `prisma/schema.prisma` |
| Auth config | `lib/auth.js`, `lib/auth.config.js`, `app/api/auth/[...nextauth]/route.js` |
| Plans, packs, model costs | `lib/billing-config.js` |
| Credit ledger | `lib/credits.js` |
| Stripe checkout / portal / webhook | `app/api/billing/*` |
| Gated generation proxy | `app/api/v1/[[...path]]/route.js`, `lib/muapi.js` |
| UI | `app/login`, `app/pricing`, `app/account`, `components/CreditBadge.js` |

## Quick start (Docker, recommended)

1. **Configure env**

   ```bash
   cp .env.example .env
   # edit .env — at minimum set AUTH_SECRET, MUAPI_PLATFORM_KEY,
   # Google OAuth creds, and the Stripe keys/prices.
   openssl rand -base64 32   # use for AUTH_SECRET
   ```

2. **Create Stripe products** in the dashboard (test mode first):
   - Recurring prices for **Pro** and **Studio** → paste IDs into
     `STRIPE_PRICE_PRO`, `STRIPE_PRICE_STUDIO`.
   - One-time prices for the three credit packs → `STRIPE_PRICE_PACK_*`.
   - (Tune amounts/credits in `lib/billing-config.js` to match.)

3. **Boot the stack** (app + Postgres + Mailhog):

   ```bash
   docker compose up --build
   ```

   Migrations run automatically on start. App: <http://localhost:3001>.
   Dev email inbox (magic links): <http://localhost:8025>.

4. **Stripe webhook.** Point Stripe at `{APP_URL}/api/billing/webhook`.
   For local testing:

   ```bash
   stripe listen --forward-to localhost:3001/api/billing/webhook
   # copy the printed whsec_... into STRIPE_WEBHOOK_SECRET, then restart
   ```

## Quick start (local, no Docker)

```bash
npm install
cp .env.example .env            # set DATABASE_URL to your Postgres
npm run db:push                 # create tables from the schema
npm run build:packages
npm run dev                     # http://localhost:3000
```

## Google OAuth

1. Google Cloud Console → Credentials → OAuth client ID (Web application).
2. Authorized redirect URI: `{APP_URL}/api/auth/callback/google`.
3. Put the client id/secret in `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`.

## The credit / cost model

`lib/billing-config.js` is the single source of truth:

- `PLANS` — subscription tiers and their **monthlyCredits** (granted on each
  paid invoice; balance is topped up to at least the quota, so it doesn't stack
  infinitely).
- `CREDIT_PACKS` — one-time top-ups that add to the balance and never expire.
- `COST_BY_KIND` / `COST_BY_MODEL` / `DEFAULT_COST` — how many credits a
  generation costs. **Tune these to sit safely above your real MuAPI cost** so
  you never lose money. Video/Veo/Kling are expensive; SDXL images are cheap.
- `SIGNUP_BONUS_CREDITS` — free credits for new accounts.

Charging happens in `app/api/v1/[[...path]]/route.js`: credits are deducted
*before* the upstream call on billable POSTs and **refunded automatically** if
MuAPI returns an error, so users are never charged for failures.

> The cost classifier (`lib/muapi.js`) is heuristic (matches on the model id /
> path). Review `isBillable()` and `estimateCost()` against the exact MuAPI
> endpoints your studio calls and adjust before charging real money.

## Going to production

- Set `APP_URL` to your https domain and `AUTH_TRUST_HOST=true`.
- Use **live** Stripe keys + a real webhook endpoint secret.
- Swap Mailhog for a real SMTP provider (`EMAIL_SERVER_*`) and a verified
  `EMAIL_FROM` domain.
- Back up the Postgres volume (`kobe_pgdata`).
- Consider Stripe **Tax** (or a merchant-of-record) for global VAT/sales tax.
- Add Terms of Service & Privacy Policy pages (linked from `/login`).
