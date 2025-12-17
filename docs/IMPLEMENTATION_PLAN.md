# Implementation Plan: Marketing Site, Authentication & Pricing

## Overview

Transform CRASH LENS from a single-page tool into a full product with:
- Marketing/landing page
- Firebase Authentication (Microsoft, Google, Email)
- Pricing tiers with Stripe
- AI Assistant with Claude API (BYOK for free users)

---

## Current State

```
henrico_crash_tool/
├── index.html          # Main app (single-file, ~15K+ lines)
├── config.json         # Jurisdictions & settings
├── data/               # CSV data files
└── docs/               # Documentation
```

**Hosting**: GitHub Pages (ecomhub200.github.io/henrico_crash_tool)
**Custom Domain**: Available (to be configured)

---

## Target Architecture

```
henrico_crash_tool/
├── index.html              # NEW: Marketing/Landing page
├── login/
│   └── index.html          # Login page
├── app/
│   └── index.html          # MOVED: Main crash analysis tool
├── pricing/
│   └── index.html          # Pricing page
├── assets/
│   ├── css/
│   │   ├── marketing.css
│   │   └── shared.css
│   └── js/
│       ├── firebase-config.js
│       ├── auth.js
│       └── stripe.js
├── config.json
├── data/
└── docs/
```

**URLs**:
- `crashlens.com/` → Marketing page
- `crashlens.com/login` → Login
- `crashlens.com/pricing` → Pricing
- `crashlens.com/app` → Protected application

---

## Pricing Model

| Tier | Price | Users | AI Assistant |
|------|-------|-------|--------------|
| Free Trial | $0 (2 weeks) | 1 | BYOK (unlimited) |
| Individual | $150/mo ($1,500/yr) | 1 | 100/mo included + BYOK |
| Team | $500/mo ($5,000/yr) | 5 | 500/mo included + BYOK |
| Agency | Custom | Unlimited | 1,000+/mo included + BYOK |

**Add-ons**:
- Extra team seat: +$75/user/month
- Extra AI queries: +$25 per 100 queries

---

## Phase 1: Project Restructure

### Tasks

1. **Create directory structure**
   ```
   mkdir -p login pricing app assets/css assets/js
   ```

2. **Move current app**
   - Copy `index.html` → `app/index.html`
   - Update relative paths in app (data/, config.json)

3. **Create placeholder pages**
   - `index.html` (marketing)
   - `login/index.html`
   - `pricing/index.html`

4. **Configure GitHub Pages**
   - Ensure all routes work with directory-based navigation
   - Add 404.html for SPA-like behavior (optional)

### File Changes

| File | Action |
|------|--------|
| `index.html` | Replace with marketing page |
| `app/index.html` | Current app (moved) |
| `login/index.html` | New login page |
| `pricing/index.html` | New pricing page |

---

## Phase 2: Firebase Setup

### 2.1 Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Create new project: `crash-lens` (or similar)
3. Enable these services:
   - **Authentication**
   - **Firestore Database**
   - **Hosting** (optional, can stay on GitHub Pages)

### 2.2 Configure Authentication Providers

| Provider | Priority | Setup |
|----------|----------|-------|
| Microsoft | 1 | Azure AD app registration required |
| Google | 2 | Enable in Firebase console |
| Email/Password | 3 | Enable in Firebase console |

#### Microsoft Setup (For Government Users)

1. Go to [Azure Portal](https://portal.azure.com)
2. Register new application
3. Add redirect URI: `https://crashlens.com/__/auth/handler`
4. Copy Application (client) ID
5. Create client secret
6. Add to Firebase: Authentication → Sign-in method → Microsoft

#### Google Setup

1. Firebase Console → Authentication → Sign-in method
2. Enable Google provider
3. Add authorized domains

### 2.3 Firestore Schema

```javascript
// Collection: users
users/{userId} {
  email: string,
  displayName: string,
  photoURL: string,
  provider: "microsoft.com" | "google.com" | "password",
  createdAt: timestamp,

  // Subscription
  plan: "trial" | "individual" | "team" | "agency",
  billingCycle: "monthly" | "annual" | null,
  trialEndsAt: timestamp | null,
  subscriptionStatus: "active" | "canceled" | "past_due" | "expired",
  stripeCustomerId: string | null,

  // AI Assistant
  ai: {
    queriesUsedThisMonth: number,
    queriesLimit: number,  // 0, 100, 500, 1000+
    quotaResetDate: timestamp,
    useBYOK: boolean
  },

  // For team/agency
  organizationId: string | null
}

// Collection: organizations (for Team/Agency)
organizations/{orgId} {
  name: string,
  plan: "team" | "agency",
  ownerId: string,
  members: string[],  // array of userIds
  maxMembers: number, // 5 for team, unlimited for agency
  stripeSubscriptionId: string,
  createdAt: timestamp
}
```

### 2.4 Firebase Config File

Create `assets/js/firebase-config.js`:

```javascript
// Firebase configuration
const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "crash-lens.firebaseapp.com",
  projectId: "crash-lens",
  storageBucket: "crash-lens.appspot.com",
  messagingSenderId: "YOUR_SENDER_ID",
  appId: "YOUR_APP_ID"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();
const db = firebase.firestore();
```

---

## Phase 3: Authentication Implementation

### 3.1 Login Page (`login/index.html`)

**Features**:
- Sign in with Microsoft (primary button)
- Sign in with Google (secondary button)
- Email/password form
- "Forgot password" link
- "Sign up" link
- Redirect to `/app` after success

**Flow**:
```
User visits /login
    │
    ├─ Already logged in? → Redirect to /app
    │
    └─ Not logged in → Show login options
           │
           ├─ Microsoft → Firebase signInWithPopup
           ├─ Google → Firebase signInWithPopup
           └─ Email → Firebase signInWithEmailAndPassword
                  │
                  └─ Success → Create/update user doc → Redirect to /app
```

### 3.2 Auth State Management (`assets/js/auth.js`)

**Functions**:
- `initAuth()` - Initialize auth listener
- `signInWithMicrosoft()` - Microsoft OAuth
- `signInWithGoogle()` - Google OAuth
- `signInWithEmail(email, password)` - Email login
- `signUp(email, password, name)` - Email registration
- `signOut()` - Logout
- `getCurrentUser()` - Get current user
- `getUserData()` - Get Firestore user document
- `requireAuth()` - Protect page (redirect if not logged in)

### 3.3 Protect the App (`app/index.html`)

Add at the top of `<script>`:

```javascript
// Auth check - runs before app loads
(async function() {
  const user = await requireAuth();
  if (!user) return; // Redirect handled by requireAuth

  const userData = await getUserData();

  // Check trial expiration
  if (userData.plan === 'trial' && userData.trialEndsAt < Date.now()) {
    window.location.href = '/pricing?expired=true';
    return;
  }

  // Check subscription status
  if (userData.subscriptionStatus === 'expired') {
    window.location.href = '/pricing?resubscribe=true';
    return;
  }

  // User is valid - continue loading app
  window.currentUser = userData;
})();
```

---

## Phase 4: Stripe Integration

### 4.1 Stripe Setup

1. Create [Stripe account](https://stripe.com)
2. Get API keys (publishable + secret)
3. Create products and prices:

| Product | Price ID | Amount |
|---------|----------|--------|
| Individual Monthly | `price_individual_monthly` | $150 |
| Individual Annual | `price_individual_annual` | $1,500 |
| Team Monthly | `price_team_monthly` | $500 |
| Team Annual | `price_team_annual` | $5,000 |
| Extra Seat | `price_extra_seat` | $75/mo |
| Extra AI Queries | `price_extra_ai` | $25/100 |

### 4.2 Checkout Flow

**Option A: Stripe Checkout (Recommended for simplicity)**

```javascript
// On pricing page
async function subscribeToPlan(priceId) {
  const user = getCurrentUser();

  // Create Checkout Session via Firebase Function
  const response = await fetch('/api/create-checkout-session', {
    method: 'POST',
    body: JSON.stringify({
      priceId: priceId,
      userId: user.uid,
      successUrl: 'https://crashlens.com/app?subscribed=true',
      cancelUrl: 'https://crashlens.com/pricing'
    })
  });

  const { sessionId } = await response.json();

  // Redirect to Stripe
  const stripe = Stripe('pk_live_...');
  stripe.redirectToCheckout({ sessionId });
}
```

### 4.3 Webhook Handler (Firebase Function)

```
Stripe webhook events to handle:
├── checkout.session.completed → Create subscription in Firestore
├── invoice.paid → Update subscription status
├── invoice.payment_failed → Mark as past_due
├── customer.subscription.deleted → Mark as canceled
└── customer.subscription.updated → Sync changes
```

### 4.4 Firebase Functions Needed

| Function | Trigger | Purpose |
|----------|---------|---------|
| `createCheckoutSession` | HTTP | Create Stripe Checkout session |
| `stripeWebhook` | HTTP | Handle Stripe events |
| `createPortalSession` | HTTP | Stripe Customer Portal link |
| `resetAIQuotas` | Scheduled (1st of month) | Reset AI query counts |

---

## Phase 5: AI Assistant Integration

### 5.1 Architecture

```
User sends query
       │
       ▼
┌─────────────────┐
│ Check AI access │
│ (plan + quota)  │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
  BYOK     Included
    │         │
    ▼         ▼
Use user's   Use your
API key     API key
(browser)   (server)
```

### 5.2 BYOK Implementation (Browser-side)

For free trial users (and optional for paid users):

```javascript
// Store key in localStorage (never sent to server)
function saveClaudeApiKey(key) {
  localStorage.setItem('claude_api_key', key);
}

// Call Claude API directly from browser
async function askClaudeWithBYOK(prompt, context) {
  const apiKey = localStorage.getItem('claude_api_key');

  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'anthropic-dangerous-direct-browser-access': 'true'
    },
    body: JSON.stringify({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 1024,
      messages: [{ role: 'user', content: prompt }]
    })
  });

  return response.json();
}
```

### 5.3 Included Queries (Server-side)

For paid users using included quota:

```javascript
// Firebase Function: askClaude
async function askClaude(userId, prompt, context) {
  // 1. Check user quota
  const userDoc = await db.collection('users').doc(userId).get();
  const userData = userDoc.data();

  if (userData.ai.queriesUsedThisMonth >= userData.ai.queriesLimit) {
    throw new Error('QUOTA_EXCEEDED');
  }

  // 2. Call Claude API with YOUR key
  const response = await anthropic.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 1024,
    messages: [{ role: 'user', content: prompt }]
  });

  // 3. Increment usage
  await userDoc.ref.update({
    'ai.queriesUsedThisMonth': admin.firestore.FieldValue.increment(1)
  });

  return response;
}
```

### 5.4 AI Query Source Toggle

In app UI, paid users can switch:

```
Query source: ○ Included (73/100 left)  ● My API key
```

---

## Phase 6: Marketing Page

### 6.1 Sections

| Section | Content |
|---------|---------|
| **Hero** | Headline, subhead, CTA buttons, hero image |
| **Trusted By** | Logos (if available) or "Built for Virginia agencies" |
| **Features** | 6-8 key features with icons |
| **How It Works** | 3-step process |
| **Screenshot/Demo** | App preview |
| **Pricing** | Summary of tiers with link to /pricing |
| **Security** | Trust signals for government |
| **Footer** | Links, contact, copyright |

### 6.2 Design Notes

- Professional, government-appropriate design
- Blue color scheme (matches current app)
- Responsive (mobile-friendly)
- Fast loading (minimal JS on marketing page)

---

## Phase 7: Custom Domain Setup

### 7.1 GitHub Pages + Custom Domain

1. Add `CNAME` file to repo root:
   ```
   crashlens.com
   ```

2. Configure DNS (at your domain registrar):
   ```
   Type    Name    Value
   A       @       185.199.108.153
   A       @       185.199.109.153
   A       @       185.199.110.153
   A       @       185.199.111.153
   CNAME   www     ecomhub200.github.io
   ```

3. Enable HTTPS in GitHub Pages settings

### 7.2 Update Firebase Auth Domains

Add `crashlens.com` to Firebase authorized domains:
- Firebase Console → Authentication → Settings → Authorized domains

---

## Implementation Checklist

### Phase 1: Restructure (Week 1)
- [ ] Create directory structure
- [ ] Move app to `/app/index.html`
- [ ] Update paths in app
- [ ] Create placeholder marketing page
- [ ] Create placeholder login page
- [ ] Create placeholder pricing page
- [ ] Test all routes work

### Phase 2: Firebase Setup (Week 1-2)
- [ ] Create Firebase project
- [ ] Enable Authentication
- [ ] Configure Microsoft provider (Azure AD setup)
- [ ] Configure Google provider
- [ ] Configure Email/Password provider
- [ ] Set up Firestore database
- [ ] Create Firestore security rules
- [ ] Create `firebase-config.js`

### Phase 3: Authentication (Week 2)
- [ ] Build login page UI
- [ ] Implement `auth.js` module
- [ ] Add Microsoft sign-in
- [ ] Add Google sign-in
- [ ] Add Email sign-in/sign-up
- [ ] Add password reset flow
- [ ] Protect app with auth check
- [ ] Add user menu to app header (logout, etc.)
- [ ] Handle trial creation on first login

### Phase 4: Stripe (Week 3)
- [ ] Create Stripe account
- [ ] Create products and prices
- [ ] Set up Firebase Functions project
- [ ] Implement `createCheckoutSession` function
- [ ] Implement `stripeWebhook` function
- [ ] Implement `createPortalSession` function
- [ ] Build pricing page with checkout buttons
- [ ] Test checkout flow end-to-end
- [ ] Add subscription status to app

### Phase 5: AI Assistant (Week 4)
- [ ] Build AI chat UI in app
- [ ] Implement BYOK flow (browser-side)
- [ ] Implement included queries flow (server-side)
- [ ] Add query source toggle for paid users
- [ ] Track usage in Firestore
- [ ] Show usage counter in UI
- [ ] Handle quota exceeded state
- [ ] Add "buy more queries" option
- [ ] Set up monthly quota reset (scheduled function)

### Phase 6: Marketing (Week 4-5)
- [ ] Design marketing page
- [ ] Build hero section
- [ ] Build features section
- [ ] Build how it works section
- [ ] Add app screenshot/demo
- [ ] Build pricing summary
- [ ] Build security/trust section
- [ ] Build footer
- [ ] Mobile responsive design
- [ ] SEO meta tags

### Phase 7: Domain & Launch (Week 5)
- [ ] Configure custom domain DNS
- [ ] Add CNAME file
- [ ] Enable HTTPS
- [ ] Update Firebase authorized domains
- [ ] Update OAuth redirect URIs
- [ ] Update meta tags with new domain
- [ ] Test all flows on custom domain
- [ ] Launch!

---

## Security Considerations

### Firestore Rules

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Users can only read/write their own data
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }

    // Organization members can read org data
    match /organizations/{orgId} {
      allow read: if request.auth != null &&
        request.auth.uid in resource.data.members;
      allow write: if request.auth != null &&
        request.auth.uid == resource.data.ownerId;
    }
  }
}
```

### API Key Security

- BYOK keys stored in `localStorage` only (never sent to your server)
- Your Claude API key stored in Firebase Functions environment variables
- Stripe secret key stored in Firebase Functions environment variables

---

## Cost Estimates

### Firebase (Free tier covers most usage)

| Service | Free Tier | Estimated Usage |
|---------|-----------|-----------------|
| Authentication | 10K/month | Well under |
| Firestore | 50K reads/day | Depends on users |
| Functions | 2M invocations/mo | Depends on AI usage |

### Stripe

- 2.9% + $0.30 per transaction
- No monthly fees

### Claude API (Your cost for included queries)

- ~$0.003-0.015 per query (depending on length)
- 100 queries ≈ $0.30-1.50
- Well within profit margin of $150/mo subscription

---

## Notes

1. **Keep app single-file**: Don't split `app/index.html` - it works well as-is
2. **GitHub Pages hosting**: Sufficient for now, Firebase Hosting optional upgrade
3. **Start simple**: Launch with core features, add team management later
4. **Test with government emails**: Ensure Microsoft auth works with .gov domains
