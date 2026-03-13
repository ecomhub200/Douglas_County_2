# Claude Guidelines for Virginia Crash Analysis Tool

## Role & Expertise

When working on this project, act as:

### World-Class Traffic Safety Engineer
- Apply deep knowledge of **traffic safety principles**, crash analysis methodologies, and countermeasure effectiveness
- Understand **Virginia-specific traffic laws**, VDOT standards, and DMV crash reporting requirements
- Apply expertise in:
  - Crash data analysis and interpretation
  - Highway Safety Improvement Program (HSIP) methodologies
  - Proven Safety Countermeasures (PSC) and their applications
  - Signal warrant analysis (MUTCD standards)
  - Intersection and corridor safety assessments
  - Pedestrian and bicycle safety considerations
  - Speed management and traffic calming strategies
- Provide insights based on **FHWA guidelines**, AASHTO standards, and industry best practices
- Consider human factors, road geometry, and environmental conditions in recommendations

### World-Class Software & UI Engineer
- Apply expertise in **modern web development** (HTML5, CSS3, JavaScript ES6+)
- Design **intuitive, accessible user interfaces** following WCAG guidelines
- Implement **responsive design** that works across devices and screen sizes
- Write **clean, maintainable, performant code** with proper documentation
- Apply best practices for:
  - Data visualization (charts, maps, tables)
  - User experience (UX) and user interface (UI) design
  - Browser compatibility and cross-platform support
  - Performance optimization for large datasets
  - Accessibility for all users including those with disabilities
- Create professional, government-grade interfaces suitable for transportation agencies

### Combined Expertise
- Bridge the gap between **traffic engineering requirements** and **software implementation**
- Translate complex safety data into **clear, actionable visualizations**
- Ensure tools meet the practical needs of traffic engineers and safety analysts
- Balance technical sophistication with ease of use for non-technical users

---

## Code Contribution Rules

### 1. No Direct Pushes
- **Never push directly to the codebase** after completing code changes
- Always create a **Pull Request (PR)** instead
- Provide the PR link to the user for review and approval
- This ensures proper code review and prevents accidental overwrites

### 2. Thorough Codebase Review
- **Always explore and understand the codebase** before writing any code
- Check for:
  - Existing similar functionality that can be extended
  - Coding patterns and conventions used in the project
  - Dependencies and how components interact
  - Related tests and documentation
- Use search tools to find relevant files and understand the architecture

### 3. User Guidance
- **Recommend corrections** if the user's request seems incorrect or could cause issues
- Explain potential problems clearly with reasoning
- Suggest better alternatives when appropriate
- Be respectful but direct when pointing out issues

### 4. Feature Recommendations
- **Suggest additional features** that complement the user's request
- Recommend **testing strategies** including:
  - Unit tests for new functionality
  - Integration tests for component interactions
  - Edge case coverage
  - Browser compatibility testing (this is a browser-based tool)
- Propose improvements that align with the project's goals

### 5. Code Safety
- **Never break existing functionality** unnecessarily
- Make minimal, targeted changes
- Preserve backward compatibility when possible
- Test changes don't affect unrelated features
- Follow the **modular architecture** — separate HTML, CSS, and JS into distinct files/modules

## Project-Specific Guidelines

### Architecture
- This is a **browser-based crash analysis tool** for transportation agencies (multi-state)
- Main application is in `app/` directory (modular SPA — HTML, CSS, and JS are separated into distinct files/modules)
- Marketing site is at root level (`index.html`, `pricing.html`, `features.html`, etc.)
- Authentication via Firebase Auth (`assets/js/auth.js`) with Google OAuth + Email/Password
- Payment processing via **Stripe Checkout** (redirect mode)
- Configuration stored in `config.json` and `config/api-keys.json`
- Data processing scripts in Python (`download_crash_data.py`, `download_grants_data.py`)

### ⚠️ Modular Architecture (MANDATORY)

The application **MUST NOT** be a single monolithic HTML file. All new code and refactoring must follow a modular structure:

- **Separate HTML, CSS, and JavaScript** into distinct files
- **JavaScript modules**: Break functionality into logical modules (e.g., `app/js/map.js`, `app/js/dashboard.js`, `app/js/cmf.js`, etc.)
- **CSS files**: Organize styles by component or feature area (e.g., `app/css/map.css`, `app/css/dashboard.css`)
- **HTML**: `app/index.html` should be the entry point that loads modules via `<script>` tags or ES module imports
- **Do NOT inline large blocks of CSS or JavaScript** into HTML files
- **Each tab/feature should have its own JS module** to keep files maintainable and under a reasonable size
- When modifying existing code, **actively refactor monolithic sections into separate modules** when practical
- Shared utilities, constants, and helper functions should live in dedicated shared modules (e.g., `app/js/utils.js`, `app/js/constants.js`)

### Hosting: Coolify (Docker)
- **Docker container** running Nginx (static files, port 80) + Node.js API server (port 3001)
- Managed by **supervisord** (`supervisord.conf`)
- Nginx proxies `/api/*` to the Node.js server at `http://127.0.0.1:3001/`
- Environment variables injected via **Coolify Dashboard** → `entrypoint.sh` → `config/api-keys.json`
- Client-side API keys (Mapbox, Google Maps, Firebase, Stripe publishable key) go into `api-keys.json`
- Server-side secrets (Stripe secret key, Firebase Admin, Brevo, Qdrant) stay as env vars

### File Structure
```
crash-lens/
├── index.html              # Marketing homepage
├── pricing.html            # Pricing page (Stripe Checkout integration)
├── features.html           # Features page
├── contact.html            # Contact form
├── contact-sales.html      # Sales inquiry form
├── app/
│   ├── index.html          # Main crash analysis application (entry point)
│   ├── css/                # Application stylesheets (modular CSS)
│   └── js/                 # Application JavaScript modules
├── login/
│   └── index.html          # Authentication page (sign in/sign up)
├── assets/
│   ├── js/
│   │   ├── auth.js         # CrashLensAuth module (Firebase Auth + Stripe checkout helpers)
│   │   ├── firebase-config.js  # Firebase SDK initialization
│   │   └── firebase-config.example.js
│   └── css/
│       └── styles.css      # Global stylesheet
├── server/
│   ├── qdrant-proxy.js     # Node.js API server (Qdrant, Brevo, R2, Stripe endpoints)
│   └── package.json        # Server dependencies (stripe, firebase-admin, @aws-sdk/client-s3)
├── config/
│   ├── api-keys.json       # Runtime-generated client API keys (NOT in git)
│   ├── api-keys.example.json
│   └── settings.json
├── config.json             # Application configuration (state/jurisdiction data)
├── data/                   # Crash data files and imagery
├── states/                 # State-specific configurations
├── docs/                   # Documentation
├── .github/workflows/      # CI/CD pipelines (data download, deployment)
├── netlify/functions/      # Netlify serverless functions (legacy, also works for Netlify deploys)
├── Dockerfile              # Docker container definition
├── nginx.conf              # Nginx web server configuration
├── entrypoint.sh           # Container startup (env vars → api-keys.json)
├── supervisord.conf        # Process manager (Nginx + Node.js)
├── .env.example            # Environment variable documentation
└── netlify.toml            # Netlify deployment config (secondary deploy option)
```

### Payment Architecture (Stripe)

**Server endpoints** (in `server/qdrant-proxy.js`):
- `POST /api/stripe/create-checkout-session` — Creates Stripe Checkout session, redirects to Stripe
- `POST /api/stripe/webhook` — Handles Stripe events, updates Firestore user documents
- `POST /api/stripe/create-portal-session` — Creates Stripe Customer Portal session
- `GET /api/stripe/status` — Checks Stripe configuration status

**Client-side** (in `assets/js/auth.js`):
- `CrashLensAuth.initiateCheckout(plan, billingCycle)` — Calls server, redirects to Stripe
- `CrashLensAuth.openBillingPortal()` — Opens Stripe Customer Portal
- `CrashLensAuth.setPendingCheckout()` / `getPendingCheckout()` — Stores plan selection across login flow

**Plan values**: `'trial'`, `'individual'`, `'team'`, `'agency'`

**Environment variables for Stripe**:
- `STRIPE_SECRET_KEY` — Server-side only
- `STRIPE_PUBLISHABLE_KEY` — Injected into `api-keys.json` for client
- `STRIPE_WEBHOOK_SECRET` — For webhook signature verification
- `STRIPE_PRICE_INDIVIDUAL_MONTHLY`, `STRIPE_PRICE_INDIVIDUAL_ANNUAL` — Stripe Price IDs
- `STRIPE_PRICE_TEAM_MONTHLY`, `STRIPE_PRICE_TEAM_ANNUAL` — Stripe Price IDs
- `FIREBASE_SERVICE_ACCOUNT` — Firebase Admin SDK JSON for server-side Firestore updates

### Before Making Changes
1. Read relevant sections of `app/index.html`
2. Check `config.json` for related settings
3. Review existing documentation in `docs/`
4. Understand the tab-based UI structure
5. Test changes don't break other tabs/features
6. Check `server/qdrant-proxy.js` for backend endpoint patterns

## Pull Request Process

1. Create changes on a feature branch
2. Commit with clear, descriptive messages
3. Push to the feature branch
4. Create a PR with:
   - Summary of changes
   - Testing performed
   - Screenshots if UI changes
5. Provide the PR link to the user

---

## Technical Architecture Deep Dive

### State Management

The application uses **global state objects** to manage data across tabs. Understanding these is CRITICAL:

| State Object | Purpose | Key Properties |
|--------------|---------|----------------|
| `crashState` | Primary crash data storage | `sampleRows[]`, `aggregates`, `totalRows`, `loaded` |
| `cmfState` | CMF/Countermeasures tab | `selectedLocation`, `locationCrashes[]`, `filteredCrashes[]`, `crashProfile` |
| `warrantsState` | Warrants tab | `selectedLocation`, `locationCrashes[]`, `filteredCrashes[]`, `crashProfile` |
| `grantState` | Grants tab | `allRankedLocations[]`, `loaded` |
| `baState` | Before/After Study | `locationCrashes[]`, `locationStats` |
| `safetyState` | Safety Focus tab | `data[category].crashes[]` |
| `selectionState` | Cross-tab location selection | `location`, `crashes[]`, `crashProfile`, `fromTab` |
| `aiState` | AI Assistant | `conversationHistory[]`, `attachments[]` |

### Data Flow Hierarchy

```
crashState.sampleRows (raw CSV data)
    │
    ├─► crashState.aggregates (pre-computed statistics)
    │       └─► Main AI Tab (county-wide analysis)
    │       └─► Dashboard, Analysis tabs
    │
    ├─► cmfState.locationCrashes (location-filtered)
    │       └─► cmfState.filteredCrashes (+ date-filtered)
    │               └─► CMF Tab & CMF AI Assistant
    │
    ├─► warrantsState.locationCrashes (location-filtered)
    │       └─► warrantsState.filteredCrashes (+ date-filtered)
    │               └─► Warrants Tab
    │
    └─► selectionState.crashes (user selection)
            └─► Cross-tab navigation (Map → CMF, Map → Grants, etc.)
```

### ⚠️ CRITICAL: Function Naming Conventions

**NEVER create duplicate function names.** JavaScript function hoisting causes later definitions to overwrite earlier ones silently.

Current crash profile functions (each serves a different purpose):

| Function | Returns | Used By |
|----------|---------|---------|
| `buildCountyWideCrashProfile()` | Aggregate stats for ALL crashes | Main AI Tab (county-wide) |
| `buildCMFCrashProfile()` | Location + date filtered profile | CMF Tab |
| `buildLocationCrashProfile(crashes)` | Simple profile `{total, K, A, B, C, O, epdo}` | AI context functions |
| `buildDetailedLocationProfile(crashes)` | Detailed profile with `{severityDist, collisionTypes, weatherDist...}` | Map jump functions |

### Data Consistency Rules

When working on features that display or analyze crash data:

1. **Identify the data scope** - Is it county-wide, location-specific, or date-filtered?
2. **Use the appropriate state** - Don't mix `crashState.aggregates` with `cmfState.filteredCrashes`
3. **Check for existing patterns** - Other tabs doing similar things? Follow their pattern
4. **Update related indicators** - If you change data context, update UI indicators

### Tab-Specific Data Sources

| Tab | Data Source | Filtering Applied |
|-----|-------------|-------------------|
| Dashboard | `crashState.aggregates` | None |
| Analysis | `crashState.aggregates` | None |
| Map | `crashState.sampleRows` | Year, Route, Severity filters |
| Hotspots | `crashState.aggregates.byRoute` | None |
| CMF/Countermeasures | `cmfState.filteredCrashes` | Location + Date |
| Warrants | `warrantsState.filteredCrashes` | Location + Date |
| Grants | `grantState.allRankedLocations` | Optional Date |
| Before/After | `baState.locationCrashes` | Location |
| Safety Focus | `safetyState.data[category]` | Category + Date |
| **AI Assistant** | **Context-aware** | Location if selected, else county-wide |

### AI Tab Context Awareness

The AI tab now uses `getAIAnalysisContext()` which checks (in priority order):
1. `cmfState.selectedLocation` - CMF tab selection
2. `selectionState.location` - Cross-tab selection (from map, hotspots)
3. `warrantsState.selectedLocation` - Warrants tab selection
4. Falls back to county-wide `crashState.aggregates`

### Common Pitfalls to Avoid

1. **Duplicate Function Names**
   - JavaScript silently overwrites functions with same name
   - Always search for existing functions before creating new ones
   - Use descriptive, unique names

2. **Mixing Data Scopes**
   - Don't show location-specific counts with county-wide analysis
   - Ensure crash counts match across related UI elements

3. **Forgetting Date Filters**
   - Many tabs support date filtering
   - New features should respect existing date filter state

4. **State Synchronization**
   - When location changes in one tab, related tabs may need updates
   - Use `updateAIContextIndicator()` pattern for cross-tab awareness

5. **Aggregate vs Sample Rows**
   - `crashState.aggregates` - fast, pre-computed, but limited detail
   - `crashState.sampleRows` - full data, but slower to process
   - Choose based on what information you need

### Testing Checklist

Before submitting changes:

- [ ] Verify crash counts match across related views
- [ ] Test with location selected AND without
- [ ] Test with date filter applied AND without
- [ ] Check all tabs that might share the affected state
- [ ] Verify no duplicate function names introduced
- [ ] Console log shows expected data flow
- [ ] UI indicators reflect actual data being used

### Debugging Tips

```javascript
// Log current AI context
console.log('[AI Context]', getAIAnalysisContext());

// Log CMF state
console.log('[CMF State]', cmfState.selectedLocation, cmfState.filteredCrashes.length);

// Log selection state
console.log('[Selection]', selectionState.location, selectionState.crashes?.length);

// Verify crash counts match
console.log('[Counts]', {
    aggregate: crashState.aggregates.byRoute['ROUTE_NAME']?.total,
    sampleRows: crashState.sampleRows.filter(r => r[COL.ROUTE] === 'ROUTE_NAME').length,
    cmfFiltered: cmfState.filteredCrashes.length
});
```

### Column Reference (COL object)

Key column indices used throughout the codebase:
- `COL.ROUTE` - Road/route name
- `COL.NODE` - Intersection node ID
- `COL.SEVERITY` - K/A/B/C/O severity
- `COL.COLLISION` - Collision type
- `COL.PED` - Pedestrian involved flag
- `COL.BIKE` - Bicycle involved flag
- `COL.WEATHER` - Weather conditions
- `COL.LIGHT` - Light conditions
- `COL.DATE` - Crash date

### EPDO Calculation

Equivalent Property Damage Only (EPDO) weights:
```javascript
const EPDO_WEIGHTS = { K: 462, A: 62, B: 12, C: 5, O: 1 };
```

Always use `calcEPDO(severityObject)` for consistent calculations.

---

## Multi-State Data Onboarding

### State Onboarding Documentation (MANDATORY)

When onboarding a **new state's crash data** into the system, you **MUST** create a comprehensive onboarding document:

- **File**: `data/{StateDOT}/{state}_dot_data_config_and_onboarding.md`
- **Example**: `data/DelawareDOT/delaware_dot_data_config_and_onboarding.md`

This document serves as the **single source of truth** for Claude Code when working with that state's crash data. It must be created **during** the onboarding process and kept updated with any future changes.

### Required Sections

Every state onboarding document must include:

1. **State Data Profile** — State name, abbreviation, FIPS, DOT name, counties, data custodian, data portal URL, dataset ID, API type, update frequency, historical range
2. **Data Source Details** — API behavior (pagination, filtering, auth), raw field names with descriptions and example values, field name format differences (API vs CSV/Excel)
3. **Normalization Rules** — Normalizer file location, severity mapping (with rationale), composite crash ID format, datetime parsing formats, boolean field mapping table (Virginia Standard → State Source → Transform), fields NOT available (with future resolution plans)
4. **Download Pipeline** — Workflow file path, pipeline flow diagram, download script details, schedule (cron), R2 storage path
5. **Known Limitations & Exceptions** — Data quality issues, analysis limitations (which tabs/features won't work), comparison caveats vs other states
6. **Configuration Files Reference** — Table of all config files with purpose and location
7. **Future Enhancement Roadmap** — Prioritized list of planned improvements (e.g., reverse geocoding, road classification, person-level data)

### Onboarding Checklist

When adding a new state:

1. **Research the data source** — API type, field names, data dictionary, severity levels, available fields
2. **Create the normalizer** — Add `{State}Normalizer` class to `scripts/state_adapter.py` with `STATE_SIGNATURES` entry
3. **Create state config** — `states/{state}/config.json` with jurisdictions, EPDO weights, column mapping
4. **Create hierarchy config** — `states/{state}/hierarchy.json` with regions, MPOs, counties
5. **Create download script** — `data/{StateDOT}/download_{state}_crash_data.py`
6. **Create download workflow** — `.github/workflows/download-{state}-crash-data.yml` with normalize step and pipeline trigger
7. **Register in pipeline** — Add state to `.github/workflows/pipeline.yml` state options
8. **Create onboarding doc** — `data/{StateDOT}/{state}_dot_data_config_and_onboarding.md` (this document)
9. **Test with sample data** — Run normalizer against sample data, verify severity distribution, EPDO, and column mappings
10. **Document limitations** — Record what's missing and what workarounds are in place

### Existing State Onboarding Docs

| State | Document |
|-------|----------|
| Delaware | `data/DelawareDOT/delaware_dot_data_config_and_onboarding.md` |

Update this table as new states are onboarded.
