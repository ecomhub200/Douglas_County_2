# CRASH LENS — Stripe Integration & Pricing Page Update

## Task
Update the CRASH LENS pricing page and integrate Stripe for subscription billing. The app is hosted at `https://crashlens.aicreatesai.com` and deployed via Coolify. Use the existing codebase structure and follow the environment variable pattern already in place.

---

## Stripe Account Details

- **Account**: Crash Lens sandbox (`acct_1T3iWR2KeDJ7ZLpP`)
- **Mode**: Test/Sandbox (switch to live when ready for production)
- **Dashboard**: https://dashboard.stripe.com

---

## Products & Price IDs

### Free Trial
- **Product ID**: `prod_U1mpuM7hpTAa2g`
- **Price**: $0/mo (14-day trial)
- **Monthly Price ID**: `price_1T3jG92KeDJ7ZLpPQFvWGTC5`
- **Payment Link**: https://buy.stripe.com/test_fZuaEQ6zb92d4RSgHWaZi00

### Individual Plan
- **Product ID**: `prod_U1mp4UcZND3E2n`
- **Monthly**: $1,000/mo
- **Monthly Price ID**: `price_1T3jGD2KeDJ7ZLpPWDsfbhI9`
- **Monthly Payment Link**: https://buy.stripe.com/test_8x214gg9L7Y9700dvKaZi01
- **Annual**: $9,600/yr ($800/mo — 20% off)
- **Annual Price ID**: `price_1T3jGJ2KeDJ7ZLpPVaAobRtI`
- **Annual Payment Link**: https://buy.stripe.com/test_eVq6oA1eR6U5ckkfDSaZi02

### Team Plan
- **Product ID**: `prod_U1mp4eZtn7d5c3`
- **Monthly**: $4,500/mo
- **Monthly Price ID**: `price_1T3jGM2KeDJ7ZLpPmxnknkM4`
- **Monthly Payment Link**: https://buy.stripe.com/test_aFa00cbTv3HT4RSbnCaZi03
- **Annual**: $43,200/yr ($3,600/mo — 20% off)
- **Annual Price ID**: `price_1T3jGT2KeDJ7ZLpPlNuuokn3`
- **Annual Payment Link**: https://buy.stripe.com/test_bJecMYcXz3HTfwwezOaZi04

### Agency Plan
- **Product ID**: `prod_U1mpdPMGDsemq3`
- **Pricing**: Custom (no Stripe checkout — routes to contact/sales page)

---

## Coupons

| Coupon Name | Coupon ID | Discount | Duration | Use Case |
|---|---|---|---|---|
| Annual Discount - 20% Off | `sGiKmUYS` | 20% off | Forever | Built-in annual pricing |
| Early Adopter - 30% Off (3 Months) | `dxAZCKlY` | 30% off | 3 months | Launch promotion |
| Government Agency - 15% Off | `PRpwNuEe` | 15% off | Forever | Public sector clients |
| TRB2026 - 25% Off First Month | `UTOJNWhQ` | 25% off | 1 month | Conference leads |
| Referral - 20% Off (2 Months) | `AaLMpSFB` | 20% off | 2 months | Customer referrals |
| Pilot Program - $500 Off | `Aucf2b6f` | $500 off | One-time | Pilot/demo clients |

---

## Environment Variables for Coolify

Set these in Coolify deployment settings:

```env
# Stripe Keys (replace with live keys for production)
STRIPE_SECRET_KEY=sk_test_51T3iWR2KeDJ7...
STRIPE_PUBLISHABLE_KEY=pk_test_51T3iWR2KeDJ7...
STRIPE_WEBHOOK_SECRET=whsec_xxx

# Stripe Price IDs
STRIPE_PRICE_INDIVIDUAL_MONTHLY=price_1T3jGD2KeDJ7ZLpPWDsfbhI9
STRIPE_PRICE_INDIVIDUAL_ANNUAL=price_1T3jGJ2KeDJ7ZLpPVaAobRtI
STRIPE_PRICE_TEAM_MONTHLY=price_1T3jGM2KeDJ7ZLpPmxnknkM4
STRIPE_PRICE_TEAM_ANNUAL=price_1T3jGT2KeDJ7ZLpPlNuuokn3

# App
APP_URL=https://crashlens.aicreatesai.com
FIREBASE_SERVICE_ACCOUNT={"type":"service_account",...}
```

---

## Pricing Page Requirements

### Layout & Design
1. **Billing toggle**: Monthly / Annual switch at the top. When "Annual" is selected, show the discounted price with a "Save 20%" badge.
2. **Plan cards** (4 columns on desktop, stacked on mobile):
   - **Free Trial**: $0 for 14 days, CTA = "Start Free Trial"
   - **Individual**: $1,000/mo or $800/mo (annual), CTA = "Get Started"
   - **Team**: $4,500/mo or $3,600/mo (annual), CTA = "Get Started" — mark as "Most Popular" with a highlighted border/badge
   - **Agency**: "Custom" pricing, CTA = "Contact Sales" → routes to contact form, NOT Stripe checkout
3. **Feature comparison table** below the cards showing what each plan includes
4. **FAQ section** at the bottom addressing common billing questions

### Feature Breakdown per Plan

#### Free Trial (14 Days)
- Full platform access
- Up to 3 crash reports
- Basic AI analysis
- Single user
- Email support

#### Individual ($1,000/mo)
- Unlimited crash reports
- Full AI-powered analysis (countermeasures, grant writing, MUTCD compliance)
- CMF Clearinghouse integration
- Virginia Roads crash database access
- PDF report generation
- Priority email support
- 1 user seat

#### Team ($4,500/mo)
- Everything in Individual
- Up to 10 user seats
- Team dashboards & shared reports
- Admin panel with role management
- Agency-wide crash data aggregation
- Custom branding on reports
- Phone & email support
- API access

#### Agency (Custom)
- Everything in Team
- Unlimited user seats
- Statewide data access
- Custom integrations (GIS, CAD, etc.)
- Dedicated account manager
- SLA guarantee
- On-premise deployment option
- Training & onboarding

---

## Stripe Checkout Integration

### Frontend: Redirect to Stripe Checkout
When a user clicks a plan CTA button, create a Stripe Checkout Session on the backend and redirect.

```javascript
// Example: API route to create checkout session
const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);

app.post('/api/stripe/create-checkout-session', async (req, res) => {
  const { priceId, userId, userEmail } = req.body;

  const session = await stripe.checkout.sessions.create({
    mode: 'subscription',
    payment_method_types: ['card'],
    line_items: [{ price: priceId, quantity: 1 }],
    customer_email: userEmail,
    client_reference_id: userId,
    success_url: `${process.env.APP_URL}/dashboard?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${process.env.APP_URL}/pricing`,
    subscription_data: {
      trial_period_days: 14, // Only for Free Trial plan
    },
    allow_promotion_codes: true, // Enables coupon code field at checkout
    metadata: {
      userId: userId,
      plan: 'individual_monthly' // or team_annual, etc.
    }
  });

  res.json({ url: session.url });
});
```

### Webhook Handler
Create endpoint at `/api/stripe/webhook` to handle subscription lifecycle events:

```javascript
const endpointSecret = process.env.STRIPE_WEBHOOK_SECRET;

app.post('/api/stripe/webhook', express.raw({type: 'application/json'}), async (req, res) => {
  const sig = req.headers['stripe-signature'];
  let event;

  try {
    event = stripe.webhooks.constructEvent(req.body, sig, endpointSecret);
  } catch (err) {
    return res.status(400).send(`Webhook Error: ${err.message}`);
  }

  switch (event.type) {
    case 'checkout.session.completed':
      // Provision access: update Firebase user record with subscription info
      // Store: subscriptionId, plan, status, current_period_end
      break;

    case 'customer.subscription.updated':
      // Handle plan changes, renewals
      // Update Firebase user record
      break;

    case 'customer.subscription.deleted':
      // Revoke access: downgrade user to free/expired
      break;

    case 'invoice.payment_failed':
      // Notify user of failed payment via email (Brevo)
      // Set grace period (e.g., 7 days before revoking access)
      break;
  }

  res.json({ received: true });
});
```

### Stripe Webhook Setup
Register webhook in Stripe Dashboard:
- **URL**: `https://crashlens.aicreatesai.com/api/stripe/webhook`
- **Events to listen for**:
  - `checkout.session.completed`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.payment_failed`

---

## Customer Portal
Enable the Stripe Customer Portal so users can manage their subscriptions (upgrade, downgrade, cancel, update payment method):

```javascript
app.post('/api/stripe/customer-portal', async (req, res) => {
  const { customerId } = req.body;

  const portalSession = await stripe.billingPortal.sessions.create({
    customer: customerId,
    return_url: `${process.env.APP_URL}/dashboard`,
  });

  res.json({ url: portalSession.url });
});
```

**Enable in Stripe Dashboard**: Settings → Billing → Customer Portal
- Allow customers to: update payment methods, view invoices, cancel subscriptions, switch plans

---

## Firebase User Schema Update

Add subscription fields to user documents in Firestore:

```javascript
// Firestore: users/{userId}
{
  // ... existing fields
  subscription: {
    status: 'active' | 'trialing' | 'past_due' | 'canceled' | 'expired',
    plan: 'free_trial' | 'individual' | 'team' | 'agency',
    billingCycle: 'monthly' | 'annual',
    stripeCustomerId: 'cus_xxx',
    stripeSubscriptionId: 'sub_xxx',
    currentPeriodEnd: Timestamp,
    cancelAtPeriodEnd: false,
    seats: 1 | 10 | 'unlimited',
    trialEnd: Timestamp | null
  }
}
```

---

## Access Control Middleware

Gate features based on subscription status:

```javascript
const checkSubscription = (requiredPlan) => async (req, res, next) => {
  const user = await getFirestoreUser(req.userId);
  const sub = user.subscription;

  // Check if subscription is active
  if (!['active', 'trialing'].includes(sub?.status)) {
    return res.status(403).json({ error: 'Active subscription required', redirect: '/pricing' });
  }

  // Check plan hierarchy: agency > team > individual > free_trial
  const planHierarchy = { free_trial: 0, individual: 1, team: 2, agency: 3 };
  if (planHierarchy[sub.plan] < planHierarchy[requiredPlan]) {
    return res.status(403).json({ error: 'Plan upgrade required', redirect: '/pricing' });
  }

  next();
};

// Usage
app.get('/api/reports/generate', checkSubscription('individual'), handleReport);
app.get('/api/team/dashboard', checkSubscription('team'), handleTeamDashboard);
```

---

## Testing Checklist

- [ ] Pricing page renders correctly with monthly/annual toggle
- [ ] All plan CTA buttons redirect to correct Stripe Checkout
- [ ] Free Trial starts with 14-day trial period
- [ ] Annual plans show 20% savings badge
- [ ] Agency plan routes to contact form (no Stripe)
- [ ] `allow_promotion_codes: true` enables coupon input at checkout
- [ ] Webhook receives and processes all 4 event types
- [ ] Firebase user record updates on subscription changes
- [ ] Customer Portal accessible from user dashboard
- [ ] Access control correctly gates features by plan
- [ ] Failed payment triggers email notification
- [ ] Canceled subscription revokes access at period end
- [ ] Mobile responsive layout for pricing page

---

## Stripe CLI Local Testing

```bash
stripe listen --forward-to localhost:3001/api/stripe/webhook
```

Use test cards:
- **Success**: `4242 4242 4242 4242`
- **Decline**: `4000 0000 0000 0002`
- **3D Secure**: `4000 0025 0000 3155`

---

## Notes
- All Price IDs above are **test mode**. When switching to production, create new products/prices in live mode and update env vars.
- The Agency plan uses manual invoicing via Stripe Dashboard — no automated checkout.
- Consider adding Brevo email notifications for: welcome email after signup, payment receipt, failed payment alert, subscription canceled, trial ending reminder (day 12).
