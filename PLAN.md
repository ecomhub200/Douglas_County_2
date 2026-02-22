# Stripe Payment & Onboarding Flow - Implementation Plan

## Overview

Add Stripe payment integration with an industry-standard SaaS onboarding flow to CRASH LENS. The flow follows the **Pricing-First** pattern used by Linear, Notion, and Vercel.

## Architecture

**Backend**: Add Stripe endpoints to the existing Node.js server (`server/qdrant-proxy.js`) running on port 3001 behind Nginx (`/api/*` → `localhost:3001`).

**Payment Flow**: Stripe Checkout (redirect mode) — users are redirected to Stripe's hosted checkout page.

**Plan Names**: Standardize on `individual` / `team` / `agency` (matching pricing page). Update auth.js from `starter/professional/enterprise`.

---

## User Flow Diagrams

### Flow A: New User from Pricing Page
```
pricing.html → Click "Get Started" (Individual $150/mo)
  → Store plan+billing in sessionStorage
  → Redirect to /login/?plan=individual&billing=monthly
  → User signs up (email or Google)
  → Email verification (if email signup)
  → After auth → auto-call /api/create-checkout-session
  → Redirect to Stripe Checkout hosted page
  → Payment success → /pricing.html?session_id=xxx (webhook fires)
  → Redirect to /app/ with active subscription
```

### Flow B: Existing Logged-In User Upgrading
```
pricing.html or in-app "Upgrade" button
  → Auth check: user is logged in
  → Click plan → call /api/create-checkout-session
  → Stripe Checkout → success → back to /app/
```

### Flow C: Trial Expired
```
/app/ → auth check → trial expired, no paid plan
  → Show upgrade modal or redirect to /pricing.html?expired=true
  → User picks plan → Stripe Checkout → back to /app/
```

### Flow D: Manage Subscription
```
In-app account menu → "Manage Billing"
  → Call /api/create-portal-session
  → Redirect to Stripe Customer Portal
  → Cancel, change plan, update payment → webhook fires
  → Return to /app/
```

---

## Files to Create/Modify

### 1. `server/qdrant-proxy.js` — Add 3 Stripe Endpoints

**New endpoints:**

#### `POST /stripe/create-checkout-session`
- Receives: `{ plan, billingCycle, firebaseUid, email }`
- Creates/retrieves Stripe customer (using email)
- Creates Stripe Checkout Session with correct price ID
- Returns `{ url }` for redirect

#### `POST /stripe/webhook`
- Receives Stripe webhook events (raw body, verified with signing secret)
- Handles:
  - `checkout.session.completed` → Update Firestore: plan, subscriptionStatus, stripeCustomerId, stripeSubscriptionId
  - `customer.subscription.updated` → Plan changes, billing cycle changes
  - `customer.subscription.deleted` → Set subscriptionStatus to 'cancelled'
  - `invoice.payment_failed` → Set subscriptionStatus to 'past_due'
- Uses Firebase Admin SDK to update Firestore directly

#### `POST /stripe/create-portal-session`
- Receives: `{ stripeCustomerId }`
- Creates Stripe Customer Portal session
- Returns `{ url }` for redirect

**Dependencies to add:**
- `stripe` (Stripe Node.js SDK)
- `firebase-admin` (Firebase Admin SDK for server-side Firestore updates)

### 2. `server/package.json` — Add Dependencies
```json
{
  "dependencies": {
    "@aws-sdk/client-s3": "^3.700.0",
    "stripe": "^14.0.0",
    "firebase-admin": "^12.0.0"
  }
}
```

### 3. `pricing.html` — Stripe Checkout Integration

**Changes:**
- Load Firebase SDK + auth.js (to check login state)
- Add `stripe-config.js` inline or load from config
- Change plan buttons from links to buttons with onclick handlers
- Button click flow:
  1. Check if user is logged in (Firebase auth state)
  2. If logged in → call `/api/stripe/create-checkout-session` → redirect to Stripe
  3. If NOT logged in → redirect to `/login/?plan=individual&billing=monthly`
- Handle success redirect: `?session_id=xxx` → show success message → redirect to /app/
- Add Stripe publishable key loading from `/config/api-keys.json`

### 4. `login/index.html` — Plan Selection Redirect

**Changes:**
- Read `?plan=` and `?billing=` URL params on load
- Store in `sessionStorage` as `pendingPlan` and `pendingBilling`
- After successful auth + verification:
  - If `pendingPlan` exists → call `/api/stripe/create-checkout-session` → redirect to Stripe
  - If no pending plan → redirect to `/app/` (existing behavior)
- Show plan context in UI: "Creating account to start Individual plan"

### 5. `assets/js/auth.js` — Post-Auth Checkout Support

**Changes:**
- Update plan values from `starter/professional/enterprise` to `individual/team/agency`
- Add helper: `CrashLensAuth.initiateCheckout(plan, billingCycle)`
  - Calls `/api/stripe/create-checkout-session` with user's Firebase UID + email
  - Handles redirect to Stripe Checkout URL
- Add helper: `CrashLensAuth.openBillingPortal()`
  - Calls `/api/stripe/create-portal-session` with stripeCustomerId
  - Redirects to Stripe Customer Portal
- Update `hasActiveSubscription()` to also check for `past_due` status

### 6. `app/index.html` — In-App Upgrade & Billing

**Changes (minimal, targeted):**
- Add trial expiry banner at top when `trialDaysRemaining <= 7`
- Add "Upgrade" button that links to `/pricing.html`
- Add "Manage Billing" option in user/account area
- Show current plan badge in header/user menu
- When trial expires → show modal with upgrade CTA

### 7. Environment Variables

**New env vars (add to Coolify dashboard):**
```
STRIPE_SECRET_KEY=sk_live_xxx       # Stripe secret key (server-side)
STRIPE_PUBLISHABLE_KEY=pk_live_xxx  # Stripe publishable key (client-side, injected)
STRIPE_WEBHOOK_SECRET=whsec_xxx     # Stripe webhook signing secret
FIREBASE_SERVICE_ACCOUNT='{...}'    # Firebase Admin SDK service account JSON
```

**Stripe Price IDs (environment vars for flexibility):**
```
STRIPE_PRICE_INDIVIDUAL_MONTHLY=price_xxx
STRIPE_PRICE_INDIVIDUAL_ANNUAL=price_xxx
STRIPE_PRICE_TEAM_MONTHLY=price_xxx
STRIPE_PRICE_TEAM_ANNUAL=price_xxx
```

### 8. `entrypoint.sh` — Inject Stripe Publishable Key

Add `STRIPE_PUBLISHABLE_KEY` to the api-keys.json generation so the client can load it.

### 9. `.env.example` — Document New Variables

Add all new Stripe and Firebase Admin env vars with descriptions.

### 10. `CLAUDE.md` — Update Architecture Documentation

- Replace Netlify references with Coolify/Docker architecture
- Document Stripe integration pattern
- Update file structure and state management docs
- Add Stripe-related debugging tips

---

## Stripe Dashboard Configuration (Pre-requisites)

Before deploying, set up in Stripe Dashboard:

1. **Products** (create 2 products):
   - "CRASH LENS Individual" with 2 prices: $150/mo monthly, $120/mo annual ($1,440/yr)
   - "CRASH LENS Team" with 2 prices: $500/mo monthly, $400/mo annual ($4,800/yr)
   - (Agency is custom/sales-driven, no Stripe product)

2. **Customer Portal** (Settings → Billing → Customer Portal):
   - Enable: Cancel subscription, Switch plans, Update payment method
   - Set return URL: `https://crashlens.aicreatesai.com/app/`

3. **Webhook** (Developers → Webhooks):
   - Endpoint URL: `https://crashlens.aicreatesai.com/api/stripe/webhook`
   - Events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`
   - Copy signing secret → `STRIPE_WEBHOOK_SECRET`

4. **API Keys** (Developers → API Keys):
   - Copy publishable key → `STRIPE_PUBLISHABLE_KEY`
   - Copy secret key → `STRIPE_SECRET_KEY`

---

## Implementation Order

1. Server-side Stripe endpoints (server/qdrant-proxy.js + package.json)
2. Environment variable setup (.env.example, entrypoint.sh)
3. Auth module updates (auth.js — plan names, checkout helpers)
4. Pricing page integration (pricing.html)
5. Login page plan redirect (login/index.html)
6. In-app upgrade prompts (app/index.html — minimal changes)
7. CLAUDE.md update
8. Test end-to-end flow
