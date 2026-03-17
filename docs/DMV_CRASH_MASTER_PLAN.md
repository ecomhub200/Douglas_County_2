# DMV Crash — Master Plan & UI/UX Design

> **Product Vision:** A standalone crash analysis platform targeting state DMV agencies, law enforcement, and driver safety stakeholders — built on CrashLens's proven architecture but tailored for driver-centric (not road-centric) analysis.

**Date:** March 17, 2026
**Status:** Planning Phase
**Parent Product:** CrashLens (DOT-focused crash analysis)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Market Differentiation: DOT vs DMV](#2-market-differentiation-dot-vs-dmv)
3. [Architecture & Infrastructure Plan](#3-architecture--infrastructure-plan)
4. [Data Strategy](#4-data-strategy)
5. [UI/UX Design Plan](#5-uiux-design-plan)
6. [Tab-by-Tab Feature Design](#6-tab-by-tab-feature-design)
7. [Jurisdiction-Agnostic Design](#7-jurisdiction-agnostic-design)
8. [Coolify Deployment Strategy](#8-coolify-deployment-strategy)
9. [Shared Code Strategy](#9-shared-code-strategy)
10. [Phased Rollout](#10-phased-rollout)
11. [Pricing & Monetization](#11-pricing--monetization)
12. [Risk Assessment](#12-risk-assessment)

---

## 1. Executive Summary

**What:** "DMV Crash" — a separate SaaS product that analyzes crash data from the **driver behavior and licensing perspective**, complementing CrashLens which analyzes from the **road engineering perspective**.

**Why:** State DMVs publish crash datasets that DOTs use for infrastructure decisions. But the same data, analyzed differently, serves DMV agencies for:
- Driver behavior pattern identification
- License action decision support (suspensions/revocations)
- DUI/impaired driving trend analysis
- Young/elderly driver safety programs
- Commercial vehicle oversight
- Insurance and actuarial support

**How:** Fork the CrashLens codebase, strip DOT-specific features, replace with DMV-specific analysis tabs, deploy as a separate Coolify project with independent branding.

**Start:** Virginia DMV first, then expand to other states using the proven multi-state architecture.

---

## 2. Market Differentiation: DOT vs DMV

### Who Uses What

| Dimension | CrashLens (DOT) | DMV Crash (DMV) |
|-----------|-----------------|-----------------|
| **Primary User** | Traffic engineers, safety analysts | DMV analysts, law enforcement, fleet managers |
| **Core Question** | "Where are crashes happening and what road fixes help?" | "Who is crashing and what behavioral patterns exist?" |
| **Analysis Axis** | Location-centric (intersections, corridors, routes) | Person-centric (drivers, demographics, violations) |
| **Key Metrics** | EPDO, crash rate, CMF, signal warrants | Repeat offender rate, DUI frequency, age distribution |
| **Funding Driver** | HSIP grants, FHWA safety programs | DMV operational budget, law enforcement grants |
| **Regulatory Framework** | MUTCD, AASHTO, FHWA guidelines | DPPA, state motor vehicle codes, NHTSA standards |
| **Output** | Safety countermeasures, warrant studies, grant apps | License actions, enforcement targeting, program eval |

### Different Tabs, Same Data

The underlying crash CSV data is largely the same — what changes is the **lens** through which it's analyzed:

```
Same crash record:
  CrashLens sees:  "Intersection X has 15 angle crashes → install signal"
  DMV Crash sees:  "Driver Y has 3 at-fault crashes in 2 years → review license"
```

---

## 3. Architecture & Infrastructure Plan

### Repository Structure

```
dmv-crash/                          # Separate GitHub repo
├── index.html                      # Marketing homepage (DMV branding)
├── pricing.html                    # Stripe checkout (DMV plans)
├── features.html                   # DMV-specific features
├── contact.html                    # Contact / demo request
├── app/
│   ├── index.html                  # Main DMV Crash application (entry point)
│   ├── css/                        # Modular CSS
│   │   ├── layout.css              # Sidebar, header, grid
│   │   ├── dashboard.css           # Dashboard tab styles
│   │   ├── map.css                 # Map tab styles
│   │   ├── driver-profile.css      # Driver analysis styles
│   │   ├── dui.css                 # DUI analysis styles
│   │   ├── demographics.css        # Demographics tab styles
│   │   ├── fleet.css               # Fleet/commercial styles
│   │   ├── enforcement.css         # Enforcement tab styles
│   │   └── reports.css             # Reports styles
│   └── js/                         # Modular JavaScript
│       ├── loader.js               # Module loader & initialization
│       ├── constants.js            # Column indices, EPDO weights
│       ├── utils.js                # Shared utilities
│       ├── state-manager.js        # Global state management
│       ├── data-loader.js          # CSV/R2 data loading
│       ├── dashboard.js            # Dashboard tab logic
│       ├── map.js                  # Map visualization
│       ├── driver-analysis.js      # Driver behavior analysis
│       ├── dui-analysis.js         # DUI/impairment analysis
│       ├── demographics.js         # Age/gender demographics
│       ├── fleet-commercial.js     # Commercial vehicle analysis
│       ├── enforcement.js          # Enforcement targeting
│       ├── trends.js               # Temporal trend analysis
│       ├── reports.js              # Report generation
│       └── ai-assistant.js         # AI chat (DMV context)
├── login/
│   └── index.html                  # Auth page
├── assets/
│   ├── js/
│   │   ├── auth.js                 # Firebase Auth (reused from CrashLens)
│   │   └── firebase-config.js      # Separate Firebase project
│   └── css/
│       └── styles.css              # Global/marketing styles
├── server/
│   ├── dmv-proxy.js                # Node.js API server (forked from qdrant-proxy.js)
│   └── package.json
├── config/
│   ├── api-keys.json               # Runtime-generated (not in git)
│   └── settings.json
├── config.json                     # DMV-specific jurisdiction data
├── states/
│   ├── virginia/
│   │   ├── config.json             # VA DMV column mapping
│   │   ├── hierarchy.json          # VA DMV districts
│   │   └── dmv-fields.json         # VA-specific DMV fields
│   ├── maryland/
│   └── download-registry.json
├── scripts/
│   ├── dmv_state_adapter.py        # DMV-specific normalizer
│   ├── split_jurisdictions.py      # Reuse from CrashLens
│   └── generate_aggregates.py      # DMV-specific aggregates
├── data/
├── docs/
├── .github/workflows/
├── Dockerfile                      # Same Docker pattern
├── nginx.conf
├── entrypoint.sh
└── supervisord.conf
```

### Tech Stack (Identical to CrashLens)

| Layer | Technology | Notes |
|-------|-----------|-------|
| Frontend | HTML5, CSS3, JS ES6+ | Tab-based SPA, modular architecture |
| Maps | Leaflet + Mapbox tiles | Crash location visualization |
| Charts | Chart.js + D3.js | Driver demographics, trends |
| PDF/Excel | jsPDF, SheetJS | Report generation |
| Auth | Firebase Auth | Separate Firebase project |
| Payments | Stripe Checkout | Separate Stripe account |
| Backend | Node.js (Express) | API proxy, Stripe webhooks |
| Storage | Cloudflare R2 | Crash data CSVs |
| Hosting | Coolify (Docker) | Nginx + Node.js + Supervisord |
| AI | Qdrant + Claude/GPT | DMV-context AI assistant |

---

## 4. Data Strategy

### DMV Standard Column Set

All state DMV data normalizes to this standard (superset of CrashLens columns + DMV-specific fields):

#### Shared with CrashLens (reuse)
| Field | Description |
|-------|-------------|
| CRASH_ID | Unique crash identifier |
| DATE | Crash date |
| TIME | Crash time |
| LATITUDE / LONGITUDE | Location |
| SEVERITY | K/A/B/C/O |
| COLLISION_TYPE | Angle, rear-end, head-on, etc. |
| WEATHER | Weather conditions |
| LIGHT | Light conditions |
| ROAD_SURFACE | Dry, wet, icy, etc. |
| ROUTE | Road name |
| SPEED_LIMIT | Posted speed limit |

#### DMV-Specific Fields (new)
| Field | Description | Privacy Level |
|-------|-------------|---------------|
| DRIVER_AGE | Age of at-fault driver | Aggregated only |
| DRIVER_GENDER | Gender of driver | Aggregated only |
| DRIVER_LICENSE_STATE | License issuing state | Public |
| LICENSE_STATUS | Valid/suspended/revoked/expired | Restricted |
| DRIVER_FAULT | At-fault indicator | Public |
| BAC_LEVEL | Blood alcohol content | Aggregated only |
| DRUG_INVOLVED | Drug involvement flag | Public |
| ALCOHOL_INVOLVED | Alcohol involvement flag | Public |
| DISTRACTION_TYPE | Phone, passenger, etc. | Public |
| RESTRAINT_USE | Seatbelt/helmet use | Public |
| VEHICLE_TYPE | Passenger, commercial, motorcycle | Public |
| VEHICLE_YEAR | Vehicle model year | Public |
| COMMERCIAL_VEHICLE | CMV flag | Public |
| CDL_HOLDER | Commercial driver license flag | Public |
| PRIOR_CRASHES | Number of prior crashes (if available) | Restricted |
| PRIOR_VIOLATIONS | Number of prior violations (if available) | Restricted |
| CITATION_ISSUED | Citation issued at scene | Public |
| CONTRIBUTING_FACTOR | Primary contributing factor | Public |

### Privacy Architecture (DPPA Compliance)

The Driver's Privacy Protection Act restricts personally identifiable driver information. DMV Crash handles this:

1. **No PII stored** — No names, addresses, license numbers, SSNs
2. **Aggregate-only fields** — Age, gender, BAC shown only in aggregate charts (never individual records)
3. **Restricted fields** — License status, prior history only available with agency authentication level
4. **Public fields** — Crash-level data without driver PII freely available
5. **Role-based access** — Three tiers:
   - **Public** — Aggregate statistics, maps, trends (no driver detail)
   - **Agency** — Full crash records with anonymized driver data
   - **Admin** — Data management, configuration

### Virginia DMV Data Sources

| Source | URL | Format | Fields Available |
|--------|-----|--------|-----------------|
| Virginia TREDS (existing) | data.virginia.gov | CSV | Base crash data + some driver fields |
| Virginia DMV Crash Reports | dmv.virginia.gov | PDF/CSV | Driver details, citations, BAC |
| Virginia Open Data Portal | data.virginia.gov | API (Socrata) | Aggregated crash statistics |

**Key insight:** Virginia TREDS data (already used by CrashLens) contains many DMV-relevant fields — driver age, alcohol involvement, restraint use. The DMV Crash product can start by **re-analyzing existing data** through a DMV lens before adding DMV-exclusive datasets.

---

## 5. UI/UX Design Plan

### Design Principles

1. **Familiar but distinct** — Same interaction patterns as CrashLens (sidebar nav, tab content, header with jurisdiction selector) but with different color palette and branding
2. **Driver-first hierarchy** — Every analysis starts with "who" not "where"
3. **Actionable insights** — Every view should answer: "What should the DMV *do* about this?"
4. **Privacy by design** — Aggregate by default, detail on authorized request
5. **Print/export ready** — DMV staff need formal reports for license hearings, legislative briefings

### Color Palette

CrashLens uses blue/navy (`#1e3a5f → #1e40af → #3b82f6`). DMV Crash differentiates with **teal/dark green**:

```css
:root {
  /* DMV Crash Brand Colors */
  --primary: #0d9488;           /* Teal 600 */
  --primary-dark: #115e59;      /* Teal 800 */
  --primary-light: #ccfbf1;     /* Teal 100 */
  --secondary: #7c3aed;         /* Violet (accent, same as CrashLens for familiarity) */

  /* Severity Colors (same KABCO, universal) */
  --fatal: #dc2626;             /* K - Fatal */
  --serious-injury: #f97316;    /* A - Serious Injury */
  --minor-injury: #eab308;      /* B - Minor Injury */
  --possible-injury: #3b82f6;   /* C - Possible Injury */
  --pdo: #6b7280;               /* O - Property Damage Only */

  /* DMV-Specific Accent Colors */
  --dui-red: #be123c;           /* DUI/Impairment analysis */
  --young-driver: #8b5cf6;      /* Young driver (16-24) */
  --elderly-driver: #d97706;    /* Elderly driver (65+) */
  --commercial: #0369a1;        /* Commercial vehicle */
  --enforcement: #4338ca;       /* Enforcement targeting */

  /* Layout (same as CrashLens) */
  --dark: #1e293b;
  --gray: #64748b;
  --gray-light: #e2e8f0;
  --light: #f8fafc;
  --white: #fff;
  --border: #cbd5e1;
  --shadow: 0 1px 3px rgba(0,0,0,.1);
  --shadow-lg: 0 4px 12px rgba(0,0,0,.15);
  --radius: 8px;
  --radius-lg: 12px;
}
```

### Header Design

Same layout as CrashLens but with DMV branding:

```
┌──────────────────────────────────────────────────────────────────────┐
│ 🛡 DMV CRASH                     │ Virginia ▾ │ Fairfax County ▾ │ │
│ Driver Safety Analysis Platform  │            │                  │ │
│                                  │ [Help] [Settings] [👤 User]   │ │
└──────────────────────────────────────────────────────────────────────┘
```

- **Logo:** Shield icon (🛡) instead of CrashLens's lens icon — conveys protection/safety
- **Tagline:** "Driver Safety Analysis Platform" (vs CrashLens's "Crash Analysis Tool")
- **Gradient:** `linear-gradient(135deg, #115e59 0%, #0d9488 50%, #2dd4bf 100%)` (teal)
- **Jurisdiction selector:** Same pattern — State dropdown → Jurisdiction dropdown

### Sidebar Navigation Design

Mirror CrashLens's collapsible sidebar with sections, but with DMV-specific tabs:

```
┌──────────────────────┐
│  📤 Upload Data      │ ← Standalone (same as CrashLens)
│                      │
│  ▾ EXPLORE           │ ← Section header
│  ├─ 📊 Dashboard     │
│  ├─ 🗺 Map           │
│  ├─ 📈 Trends        │
│  └─ 📋 Crash Tree    │
│                      │
│  ▾ DRIVER ANALYSIS   │ ← NEW section (DMV-specific)
│  ├─ 👤 Demographics  │
│  ├─ 🍺 DUI/Impaired  │
│  ├─ 📱 Distraction   │
│  ├─ 🔄 Repeat        │
│  │    Offenders      │
│  └─ 🚛 Commercial    │
│                      │
│  ▾ ACTIONABLE        │ ← NEW section (DMV-specific)
│  ├─ 🎯 Enforcement   │
│  │    Targeting      │
│  ├─ 📄 License       │
│  │    Review         │
│  └─ 🤖 AI Assistant  │
│                      │
│  📝 Reports          │ ← Standalone
│  📊 Grants           │ ← Standalone
└──────────────────────┘
```

### Layout Grid

Same responsive grid as CrashLens:

```
Desktop (≥1200px):
┌────────────┬──────────────────────────────────────────────┐
│            │                                              │
│  Sidebar   │              Tab Content Area                │
│  (240px)   │              (flex-grow: 1)                  │
│            │                                              │
│  Collapse  │  ┌──────────────────────────────────────┐   │
│  ◀ button  │  │  Cards / Charts / Tables / Maps      │   │
│            │  │                                      │   │
│            │  │  Same card-based layout as CrashLens │   │
│            │  └──────────────────────────────────────┘   │
└────────────┴──────────────────────────────────────────────┘

Mobile (≤768px):
┌──────────────────────────────────┐
│  Header (hamburger → sidebar)    │
├──────────────────────────────────┤
│                                  │
│         Tab Content              │
│     (full width, stacked)        │
│                                  │
└──────────────────────────────────┘
```

---

## 6. Tab-by-Tab Feature Design

### Tab 1: Upload Data

**Identical to CrashLens.** User uploads a crash CSV or selects from R2-hosted data.

```
┌──────────────────────────────────────────────────────┐
│                   Upload Crash Data                   │
│                                                      │
│  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │  📁 Upload CSV   │  │  ☁ Load from Cloud       │  │
│  │                  │  │                          │  │
│  │  Drag & drop or  │  │  Virginia ▾              │  │
│  │  click to browse │  │  Fairfax County ▾        │  │
│  │                  │  │  [Load Data]             │  │
│  └──────────────────┘  └──────────────────────────┘  │
│                                                      │
│  Supported: Virginia TREDS, Maryland, Delaware...    │
└──────────────────────────────────────────────────────┘
```

### Tab 2: Dashboard

**Similar structure to CrashLens Dashboard** but with DMV-focused KPI cards:

```
┌──────────────────────────────────────────────────────────────┐
│  DASHBOARD                                    2020-2025 ▾    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Total    │ │ Fatal    │ │ DUI      │ │ Young    │       │
│  │ Crashes  │ │ Crashes  │ │ Crashes  │ │ Driver   │       │
│  │ 12,847   │ │ 47       │ │ 1,203    │ │ 3,412    │       │
│  │ ▼ -3.2%  │ │ ▲ +8.5%  │ │ ▼ -12%   │ │ ▲ +2.1%  │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                                                              │
│  ┌──────────────────────────┐ ┌──────────────────────────┐  │
│  │ Severity Distribution    │ │ Contributing Factors     │  │
│  │ [Donut Chart]            │ │ [Horizontal Bar Chart]   │  │
│  │  K: 47 (0.4%)            │ │  Speed: ████████ 2,341   │  │
│  │  A: 312 (2.4%)           │ │  DUI:   ██████ 1,203     │  │
│  │  B: 1,847 (14.4%)        │ │  Distr: █████ 987        │  │
│  │  C: 3,102 (24.1%)        │ │  Follow:████ 856         │  │
│  │  O: 7,539 (58.7%)        │ │  Other: ███ 612          │  │
│  └──────────────────────────┘ └──────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────┐ ┌──────────────────────────┐  │
│  │ Crashes by Time of Day   │ │ Day of Week Distribution │  │
│  │ [Line Chart - 24hr]      │ │ [Bar Chart - Mon-Sun]    │  │
│  │  Peak: 5-6 PM (1,847)    │ │  Peak: Friday (2,103)    │  │
│  └──────────────────────────┘ └──────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ EPDO by Route (Top 10)                               │   │
│  │ [Sortable Table - same as CrashLens]                 │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

**DMV-specific KPIs (not in CrashLens):**
- DUI Crash Count & trend
- Young Driver (16-24) crash count
- Unrestrained occupant fatalities
- Distracted driving crashes
- Commercial vehicle crashes
- Hit-and-run count

### Tab 3: Map

**Nearly identical to CrashLens Map.** Crash markers on Leaflet map with clustering, heatmap, filters.

**DMV-specific additions:**
- Filter by driver age group
- Filter by DUI/impairment
- Filter by commercial vehicle
- Color-code markers by contributing factor (not just severity)
- "Enforcement zones" overlay (high-DUI corridors, school zones)

### Tab 4: Trends

**New tab (replaces CrashLens Analysis tab).** Temporal analysis focused on behavioral trends:

```
┌──────────────────────────────────────────────────────────────┐
│  TRENDS                                     Monthly ▾        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ DUI Crashes Over Time                                │   │
│  │ [Multi-line chart: Total, Fatal, Injury]             │   │
│  │                                                      │   │
│  │  Shows seasonal patterns (holidays, summer)          │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────┐ ┌──────────────────────────┐  │
│  │ Young Driver Trend       │ │ Restraint Use Trend      │  │
│  │ [Area Chart]             │ │ [Stacked Area]           │  │
│  └──────────────────────────┘ └──────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Year-Over-Year Comparison                            │   │
│  │ [Grouped bar: 2023 vs 2024 vs 2025 by category]     │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### Tab 5: Demographics (NEW — DMV-specific)

```
┌──────────────────────────────────────────────────────────────┐
│  DRIVER DEMOGRAPHICS                        All Years ▾      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Age Distribution of At-Fault Drivers                 │   │
│  │ [Histogram / Population Pyramid]                     │   │
│  │                                                      │   │
│  │  16-19 ████████████ 2,341 (18.2%)                    │   │
│  │  20-24 ██████████████ 2,847 (22.1%)                  │   │
│  │  25-34 ████████████████ 3,102 (24.1%)                │   │
│  │  35-44 ████████████ 2,012 (15.6%)                    │   │
│  │  45-54 ████████ 1,203 (9.4%)                         │   │
│  │  55-64 ██████ 847 (6.6%)                             │   │
│  │  65-74 ███ 312 (2.4%)                                │   │
│  │  75+   ██ 183 (1.4%)                                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────┐ ┌──────────────────────────┐  │
│  │ Severity by Age Group    │ │ Gender Distribution      │  │
│  │ [Stacked Bar]            │ │ [Side-by-side bars]      │  │
│  │                          │ │                          │  │
│  │ Young drivers → more K/A │ │ Male: 58% of crashes     │  │
│  │ Elderly → more K per     │ │ Female: 42%              │  │
│  │ crash (fragility)        │ │ Severity differs by...   │  │
│  └──────────────────────────┘ └──────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Out-of-State Drivers Involved                        │   │
│  │ [Choropleth map of license issuing states]           │   │
│  │  VA: 89% | MD: 4% | DC: 3% | NC: 1% | Other: 3%   │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### Tab 6: DUI / Impaired Driving (NEW — DMV-specific)

```
┌──────────────────────────────────────────────────────────────┐
│  DUI / IMPAIRED DRIVING ANALYSIS            2020-2025 ▾      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ DUI      │ │ DUI      │ │ Drug     │ │ BAC >    │       │
│  │ Crashes  │ │ Fatals   │ │ Involved │ │ 0.15     │       │
│  │ 1,203    │ │ 23       │ │ 412      │ │ 387      │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ DUI Crash Heatmap by Time                            │   │
│  │ [24hr × 7day grid heatmap]                           │   │
│  │                                                      │   │
│  │     Mon  Tue  Wed  Thu  Fri  Sat  Sun                │   │
│  │ 12AM  ██   █    █    █   ███  ████ ████              │   │
│  │  1AM  ██   █    █    █   ███  ████ ████              │   │
│  │  2AM  ███  ██   █    ██  ████ █████████              │   │
│  │  ...                                                 │   │
│  │ 11PM  █    █    █    ██  ████ ████ ███               │   │
│  │                                                      │   │
│  │ Peak: Sat/Sun 12AM-3AM                               │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────┐ ┌──────────────────────────┐  │
│  │ DUI by Age Group         │ │ Top DUI Corridors        │  │
│  │ [Bar Chart]              │ │ [Ranked Table]           │  │
│  │                          │ │                          │  │
│  │ 21-25: highest rate      │ │ 1. US-29 (47 DUI)       │  │
│  │ 16-20: zero tolerance    │ │ 2. I-66 (38 DUI)        │  │
│  │ concerns                 │ │ 3. RT-50 (31 DUI)       │  │
│  └──────────────────────────┘ └──────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ DUI Crash Locations (Map)                            │   │
│  │ [Mini Leaflet map with DUI-only clusters]            │   │
│  │ Shows proximity to bars/entertainment districts      │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### Tab 7: Distraction Analysis (NEW — DMV-specific)

```
┌──────────────────────────────────────────────────────────────┐
│  DISTRACTED DRIVING                         2020-2025 ▾      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Distraction Types Breakdown                          │   │
│  │ [Treemap or Donut]                                   │   │
│  │                                                      │   │
│  │  Cell phone use: 42%                                 │   │
│  │  Passenger: 18%                                      │   │
│  │  External distraction: 15%                           │   │
│  │  Eating/drinking: 8%                                 │   │
│  │  GPS/radio: 7%                                       │   │
│  │  Other/unknown: 10%                                  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────┐ ┌──────────────────────────┐  │
│  │ Distraction by Age       │ │ Severity: Distracted vs  │  │
│  │ [Stacked Bar]            │ │ Non-Distracted           │  │
│  │                          │ │ [Comparison Chart]       │  │
│  │ 16-24: highest phone use │ │ Distracted crashes are   │  │
│  │                          │ │ X% more likely to be K/A │  │
│  └──────────────────────────┘ └──────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### Tab 8: Repeat Offenders (NEW — DMV-specific, Agency-only)

**Requires Agency-level authentication** (DPPA compliance):

```
┌──────────────────────────────────────────────────────────────┐
│  REPEAT OFFENDER ANALYSIS 🔒 Agency Access  2020-2025 ▾      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Drivers  │ │ 2+ DUI   │ │ 3+ At-   │ │ License  │       │
│  │ w/ 2+    │ │ Crashes  │ │ Fault    │ │ Action   │       │
│  │ Crashes  │ │          │ │ Crashes  │ │ Eligible │       │
│  │ 847      │ │ 123      │ │ 312      │ │ 435      │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Repeat Offender Patterns                             │   │
│  │ [Sankey diagram: 1st crash → 2nd crash → 3rd crash]  │   │
│  │                                                      │   │
│  │ Time between crashes, escalation patterns,           │   │
│  │ severity progression                                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ⚠ Data shown in aggregate. No individual PII displayed.   │
└──────────────────────────────────────────────────────────────┘
```

### Tab 9: Commercial Vehicles (NEW — DMV-specific)

```
┌──────────────────────────────────────────────────────────────┐
│  COMMERCIAL VEHICLE ANALYSIS                2020-2025 ▾      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────┐ ┌──────────────────────────┐  │
│  │ CMV vs Non-CMV Severity  │ │ CMV Crash Locations      │  │
│  │ [Comparison bar]         │ │ [Map with freight routes] │  │
│  │                          │ │                          │  │
│  │ CMV crashes → higher     │ │ Clusters on interstates  │  │
│  │ severity, more fatals    │ │ and freight corridors    │  │
│  └──────────────────────────┘ └──────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ CDL Driver Analysis                                  │   │
│  │ [Table: Carrier type, crash count, severity, trend]  │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### Tab 10: Enforcement Targeting (NEW — DMV-specific)

```
┌──────────────────────────────────────────────────────────────┐
│  ENFORCEMENT TARGETING                      2020-2025 ▾      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  AI-generated enforcement recommendations based on data:     │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Priority Enforcement Zones                           │   │
│  │ [Map with color-coded zones]                         │   │
│  │                                                      │   │
│  │ Red zones: High DUI + High Speed + High Severity     │   │
│  │ Orange zones: Moderate risk                          │   │
│  │ Yellow zones: Emerging patterns                      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Recommended Enforcement Actions                      │   │
│  │                                                      │   │
│  │ 1. DUI Checkpoint: US-29 & RT-50 intersection       │   │
│  │    Rationale: 23 DUI crashes, peak Fri-Sat 11PM-2AM │   │
│  │    EPDO Impact: 2,341                                │   │
│  │                                                      │   │
│  │ 2. Speed Enforcement: I-66 MM 40-52                  │   │
│  │    Rationale: 47 speed-related crashes, 8 fatal      │   │
│  │    EPDO Impact: 8,102                                │   │
│  │                                                      │   │
│  │ 3. School Zone Patrol: RT-28 near elementary school  │   │
│  │    Rationale: 12 crashes during school hours         │   │
│  │    EPDO Impact: 412                                  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Optimal Patrol Schedule                              │   │
│  │ [Calendar heatmap showing when/where to patrol]      │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### Tab 11: AI Assistant (Adapted from CrashLens)

Same chat interface as CrashLens AI tab, but with DMV-specific context:

```
┌──────────────────────────────────────────────────────────────┐
│  DMV AI ASSISTANT                                            │
├──────────────────────────────────────────────────────────────┤
│  Context: Fairfax County | 12,847 crashes | 2020-2025       │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 🤖 How can I help with your driver safety analysis?  │   │
│  │                                                      │   │
│  │ 👤 What are the top contributing factors for          │   │
│  │    fatal crashes involving drivers under 25?          │   │
│  │                                                      │   │
│  │ 🤖 Based on 47 fatal crashes in Fairfax County       │   │
│  │    (2020-2025), drivers under 25 were involved in    │   │
│  │    14 (29.8%). The top contributing factors:         │   │
│  │                                                      │   │
│  │    1. Speed too fast (6 crashes, 42.9%)              │   │
│  │    2. Alcohol/drug impairment (4 crashes, 28.6%)     │   │
│  │    3. Distracted driving (2 crashes, 14.3%)          │   │
│  │    ...                                               │   │
│  │                                                      │   │
│  │ Suggested questions:                                 │   │
│  │ [Compare DUI trends to state average]                │   │
│  │ [What enforcement actions would reduce fatals?]      │   │
│  │ [Generate a quarterly safety briefing]               │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌────────────────────────────────────────┐ [📎] [Send]     │
│  │ Ask about driver safety patterns...    │                  │
│  └────────────────────────────────────────┘                  │
└──────────────────────────────────────────────────────────────┘
```

**DMV AI context includes:**
- Driver age distribution (not in CrashLens AI)
- DUI/drug involvement rates
- Restraint use statistics
- Contributing factor breakdown
- Commercial vehicle involvement
- Distraction type breakdown
- Seasonal/temporal patterns specific to behavioral factors

### Tab 12: Reports

**Same report generation engine as CrashLens** but with DMV-specific templates:

- **Quarterly DMV Safety Briefing** (PDF/Word)
- **DUI Enforcement Effectiveness Report**
- **Young Driver Safety Program Evaluation**
- **Commercial Vehicle Incident Summary**
- **Legislative Data Brief** (for state legislature requests)
- **Scheduled email reports** (same Brevo infrastructure)

---

## 7. Jurisdiction-Agnostic Design

### Multi-State Configuration Pattern

Reuse CrashLens's proven pattern:

```
states/
├── virginia/
│   ├── config.json           # Column mapping, severity rules
│   ├── hierarchy.json        # DMV districts, regions
│   └── dmv-fields.json       # VA-specific: BAC thresholds, license types
├── maryland/
│   ├── config.json
│   ├── hierarchy.json
│   └── dmv-fields.json       # MD MVA-specific fields
├── delaware/
│   ├── config.json
│   ├── hierarchy.json
│   └── dmv-fields.json
└── download-registry.json    # DMV data source registry
```

### DMV State Adapter

```python
# scripts/dmv_state_adapter.py

class DMVBaseNormalizer:
    """Base class for DMV crash data normalization."""

    # Standard output columns (DMV Standard Column Set)
    STANDARD_COLUMNS = [
        # Shared with CrashLens
        'ID', 'DATE', 'TIME', 'LAT', 'LON', 'SEVERITY',
        'COLLISION_TYPE', 'WEATHER', 'LIGHT', 'ROAD_SURFACE',
        'ROUTE', 'SPEED_LIMIT',
        # DMV-specific
        'DRIVER_AGE', 'DRIVER_GENDER', 'DRIVER_LICENSE_STATE',
        'BAC_LEVEL', 'ALCOHOL_INVOLVED', 'DRUG_INVOLVED',
        'DISTRACTION_TYPE', 'RESTRAINT_USE',
        'VEHICLE_TYPE', 'COMMERCIAL_VEHICLE', 'CDL_HOLDER',
        'CONTRIBUTING_FACTOR', 'CITATION_ISSUED',
        'AT_FAULT', 'DRIVER_FAULT_CODE'
    ]

class VirginiaDMVNormalizer(DMVBaseNormalizer):
    """Virginia TREDS → DMV Standard columns."""
    pass

class MarylandDMVNormalizer(DMVBaseNormalizer):
    """Maryland MVA → DMV Standard columns."""
    pass
```

### What Makes It Jurisdiction-Agnostic

1. **Column mapping per state** — Each state's config.json maps local field names → DMV Standard
2. **Derived fields** — If a state doesn't provide BAC_LEVEL directly, derive ALCOHOL_INVOLVED from other flags
3. **Hierarchy flexibility** — DMV districts differ from DOT districts; hierarchy.json handles this
4. **Feature flags** — If a state lacks driver age data, hide the Demographics tab gracefully
5. **Graceful degradation** — Core tabs (Dashboard, Map, Trends) work with minimal fields; advanced tabs (DUI, Demographics) require specific fields

---

## 8. Coolify Deployment Strategy

### Separate Coolify Project (Same Server)

```
Coolify Dashboard
├── Project: CrashLens
│   ├── Service: crashlens-app (Docker)
│   │   Domain: crashlens.aicreatesai.com
│   │   Repo: github.com/ecomhub200/Douglas_County_2
│   │   Port: 80 (Nginx + Node.js)
│   └── Environment Variables: (CrashLens-specific)
│
├── Project: DMV Crash         ← NEW
│   ├── Service: dmv-crash-app (Docker)
│   │   Domain: dmvcrash.com   ← NEW domain
│   │   Repo: github.com/ecomhub200/dmv-crash  ← NEW repo
│   │   Port: 80 (same Docker pattern)
│   └── Environment Variables: (DMV Crash-specific)
│       ├── FIREBASE_*          ← Separate Firebase project
│       ├── STRIPE_*            ← Separate Stripe account
│       ├── R2_BUCKET_NAME      ← Separate R2 bucket (or shared with prefix)
│       ├── QDRANT_*            ← Can share Qdrant instance (separate collection)
│       └── BREVO_*             ← Can share Brevo account (different templates)
```

### What to Share vs. Separate

| Resource | Share? | Rationale |
|----------|--------|-----------|
| Coolify Server | Share | Cost-efficient, same admin |
| GitHub Org | Share | Same team manages both |
| Firebase Project | **Separate** | Independent user bases, billing |
| Stripe Account | **Separate** | Different products, pricing, invoices |
| R2 Bucket | Share (prefixed) | Same data, different access patterns |
| Qdrant Instance | Share (collections) | Cost savings, separate vector collections |
| Brevo Account | Share | Same team, different email templates |
| Domain | **Separate** | Independent branding |
| SSL Certificates | Coolify auto | Let's Encrypt via Coolify |

### Domain Options

| Option | Domain | Pros | Cons |
|--------|--------|------|------|
| A | `dmvcrash.com` | Independent brand | New domain cost |
| B | `dmv.crashlens.com` | Brand association | Tied to CrashLens brand |
| C | `dmvcrash.aicreatesai.com` | Free (subdomain) | Less professional |

**Recommendation:** Option A (`dmvcrash.com`) for brand independence, with Option B as redirect.

---

## 9. Shared Code Strategy

### Phase 1: Copy-Paste (MVP)

Fork CrashLens repo. Copy what you need. Move fast.

### Phase 2: Extract Shared Packages (Post-MVP)

Once both products stabilize, extract common code:

```
shared-packages/
├── @crashlens/auth           # Firebase Auth wrapper
│   ├── auth.js
│   └── firebase-config.js
├── @crashlens/payments       # Stripe integration
│   ├── checkout.js
│   └── webhook-handler.js
├── @crashlens/map            # Leaflet map components
│   ├── crash-map.js
│   ├── heatmap.js
│   └── marker-cluster.js
├── @crashlens/charts         # Chart.js wrappers
│   ├── severity-donut.js
│   ├── trend-line.js
│   └── distribution-bar.js
├── @crashlens/data           # Data loading, R2 client
│   ├── csv-loader.js
│   ├── r2-client.js
│   └── state-adapter-base.js
├── @crashlens/reports        # PDF/Word/PPT generation
│   ├── pdf-generator.js
│   ├── word-generator.js
│   └── email-scheduler.js
└── @crashlens/ui             # Shared UI components
    ├── sidebar.js
    ├── header.js
    ├── kpi-card.js
    └── filter-bar.js
```

**Don't over-engineer this upfront.** Extract packages only when you find yourself fixing the same bug in both repos.

---

## 10. Phased Rollout

### Phase 1: Foundation (Weeks 1-3)
- [ ] Create `dmv-crash` GitHub repo
- [ ] Fork CrashLens codebase
- [ ] Strip DOT-specific features (CMF, Warrants, Signal Analysis, Grants, MUTCD AI)
- [ ] Apply DMV branding (teal color palette, shield logo, tagline)
- [ ] Set up separate Firebase project
- [ ] Set up separate Stripe account
- [ ] Create Coolify project with new domain
- [ ] Deploy skeleton app (Upload + Dashboard + Map)

### Phase 2: Virginia DMV MVP (Weeks 4-8)
- [ ] Research Virginia DMV data fields in existing TREDS data
- [ ] Build DMV state adapter for Virginia
- [ ] Build Demographics tab
- [ ] Build DUI/Impaired Driving tab
- [ ] Build Distraction Analysis tab
- [ ] Build Trends tab
- [ ] Adapt AI Assistant for DMV context
- [ ] Build DMV-specific Dashboard KPIs
- [ ] Marketing site (landing page, features, pricing)
- [ ] Internal testing with Virginia crash data

### Phase 3: Polish & Launch (Weeks 9-10)
- [ ] Report generation (DMV-specific templates)
- [ ] Enforcement Targeting tab
- [ ] Commercial Vehicle tab
- [ ] Mobile responsive testing
- [ ] Accessibility audit (WCAG 2.1 AA)
- [ ] Performance optimization
- [ ] Beta testing with 2-3 DMV contacts

### Phase 4: Multi-State Expansion (Weeks 11-16)
- [ ] Maryland MVA data integration
- [ ] Delaware DMV data integration
- [ ] Refine DMV Standard Column Set
- [ ] Build Repeat Offender tab (agency-only)
- [ ] License Review tab
- [ ] Multi-state comparison features

### Phase 5: Shared Code Extraction (Ongoing)
- [ ] Identify duplicated code between CrashLens and DMV Crash
- [ ] Extract into shared packages
- [ ] Establish shared CI/CD patterns

---

## 11. Pricing & Monetization

### DMV Crash Pricing Tiers

| Tier | Monthly | Annual | Target User |
|------|---------|--------|-------------|
| **Free Trial** | $0 | $0 | Evaluation (14 days, 1 jurisdiction) |
| **Analyst** | $49/mo | $39/mo | Individual DMV analyst or officer |
| **Team** | $149/mo | $119/mo | DMV office or law enforcement unit (5 seats) |
| **Agency** | $399/mo | $329/mo | State DMV or large PD (unlimited seats) |

**Note:** DMV pricing can be lower than CrashLens DOT pricing because:
- DMV offices have smaller budgets than DOTs
- Law enforcement agencies often need volume licenses
- Lower price point → faster adoption → more states

### Feature Gating

| Feature | Free | Analyst | Team | Agency |
|---------|------|---------|------|--------|
| Dashboard | 1 jurisdiction | 3 jurisdictions | 10 jurisdictions | Unlimited |
| Map | Basic | Full filters | Full filters | Full filters |
| Demographics | View only | Export | Export | Export + API |
| DUI Analysis | Summary | Full | Full | Full |
| Enforcement | - | - | Basic | Full AI |
| Repeat Offender | - | - | - | Full (DPPA) |
| Reports | - | PDF | PDF + Word | All formats |
| AI Assistant | 5 queries | 50 queries | 200 queries | 500 queries |
| Scheduled Reports | - | - | Weekly | All frequencies |

---

## 12. Risk Assessment

### High Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| **DMV data availability varies wildly** | Some states may have minimal driver-level data | Audit 10 target states before building advanced tabs; design for graceful degradation |
| **DPPA compliance** | Legal liability for exposing driver PII | No PII storage; aggregate-only display; role-based access; legal review |
| **Market validation** | DMV users may not have budget/mandate for tools | Validate with 5+ potential users before Phase 2 completion |

### Medium Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Feature divergence** | Shared code becomes unmaintainable | Delay shared packages until patterns stabilize |
| **Cannibalization** | DOT customers confused by DMV product | Clear branding separation, different domains |
| **Data freshness** | DMV data may update less frequently | Document update schedules per state; show data vintage |

### Low Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Coolify resource contention** | Both apps on same server | Monitor resources; separate server if needed |
| **Firebase/Stripe complexity** | Managing two sets of credentials | Document thoroughly; use Coolify env vars |

---

## Appendix A: CrashLens Tabs → DMV Crash Tab Mapping

| CrashLens Tab | DMV Crash Equivalent | Action |
|---------------|---------------------|--------|
| Upload Data | Upload Data | **Reuse** (identical) |
| Dashboard | Dashboard | **Adapt** (DMV KPIs) |
| Map | Map | **Adapt** (DMV filters) |
| Crash Tree | Crash Tree | **Reuse** (works as-is) |
| Safety Focus | — | **Remove** (DOT-specific) |
| Fatal & Speeding | — | **Merge into Trends** |
| Hot Spots | — | **Merge into Enforcement Targeting** |
| Intersections | — | **Remove** (DOT-specific) |
| Ped/Bike | — | **Keep as sub-view** in Dashboard |
| Analysis | Trends | **Adapt** (behavioral trends) |
| Crash Prediction | — | **Defer** (Phase 5+) |
| Deep Dive | — | **Remove** (DOT-specific) |
| Countermeasures (CMF) | — | **Remove** (DOT-specific) |
| Warrant Analyzer | — | **Remove** (DOT-specific) |
| MUTCD AI | DMV AI Assistant | **Adapt** (DMV context) |
| Domain Knowledge | — | **Remove** (DOT-specific) |
| Grants | Grants | **Adapt** (DMV/LE grants) |
| Reports | Reports | **Adapt** (DMV templates) |
| — | **Demographics** | **NEW** |
| — | **DUI/Impaired** | **NEW** |
| — | **Distraction** | **NEW** |
| — | **Repeat Offenders** | **NEW** |
| — | **Commercial Vehicles** | **NEW** |
| — | **Enforcement Targeting** | **NEW** |
| — | **License Review** | **NEW** |

## Appendix B: Virginia DMV Data Field Availability

### Fields Available in Virginia TREDS (existing data)

These fields are already in the CrashLens Virginia dataset and can be immediately used by DMV Crash:

| DMV Crash Field | Virginia TREDS Column | Available? |
|-----------------|----------------------|------------|
| SEVERITY | Crash Severity | Yes |
| ALCOHOL_INVOLVED | Alcohol Involved | Yes |
| DRUG_INVOLVED | Drug Involved | Yes (derived) |
| DRIVER_AGE | Driver Age / DOB | Varies by report |
| DRIVER_GENDER | Driver Gender | Varies by report |
| RESTRAINT_USE | Safety Equipment | Yes |
| DISTRACTION_TYPE | Driver Distraction | Yes |
| VEHICLE_TYPE | Vehicle Type | Yes |
| COMMERCIAL_VEHICLE | Commercial Vehicle | Yes (derived) |
| CONTRIBUTING_FACTOR | Driver Contributing Circumstance | Yes |
| SPEED_RELATED | Speed Related | Yes |
| HIT_AND_RUN | Hit and Run | Yes |

### Fields NOT in TREDS (require DMV-specific data source)

| Field | Status | Resolution |
|-------|--------|------------|
| BAC_LEVEL | Not in TREDS | Need DMV crash report data |
| LICENSE_STATUS | Not in TREDS | Need DMV licensing database |
| PRIOR_CRASHES | Not in TREDS | Need DMV driver record |
| PRIOR_VIOLATIONS | Not in TREDS | Need DMV driver record |
| CDL_HOLDER | Not reliably in TREDS | Need DMV licensing database |
| INSURANCE_STATUS | Not in TREDS | Need DMV/insurance database |

**Phase 1 strategy:** Build MVP with TREDS-available fields. Add DMV-exclusive fields in Phase 4 when data partnerships are established.

---

## Appendix C: Marketing Site Structure

```
dmvcrash.com/
├── index.html          # Hero: "Data-Driven Driver Safety"
│                       # Value props: DUI analysis, demographics,
│                       # enforcement targeting, compliance
│                       # Social proof: DMV logos, testimonials
│                       # CTA: "Start Free Trial"
│
├── features.html       # Tab-by-tab feature showcase
│                       # Screenshots of each analysis view
│                       # Comparison: "Without DMV Crash" vs "With"
│
├── pricing.html        # 4 tiers, annual toggle
│                       # Stripe checkout integration
│                       # FAQ section
│
├── use-cases.html      # DMV Agency, Law Enforcement,
│                       # Fleet Management, Insurance, Research
│
├── contact.html        # Demo request form
│                       # Sales inquiry
│
└── legal/              # Privacy policy, terms, DPPA notice
```

**Marketing messaging focuses on:**
- "Turn crash data into enforcement intelligence"
- "Identify high-risk driver patterns before the next fatal crash"
- "The same crash data your DOT uses — analyzed for driver safety"
- "DPPA-compliant by design"

---

*This document is the single source of truth for DMV Crash planning. Update as decisions are made.*
