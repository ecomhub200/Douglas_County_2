# Jurisdiction Pipeline Plan: Federal → State → MPO → County/City

## Executive Summary

This plan defines how to extend CRASH LENS from its current 2-jurisdiction setup (Henrico County VA + Douglas County CO) to a multi-tier system supporting **Federal, State, MPO, and County/City** views — using the existing codebase, pipelines, and R2 infrastructure as the foundation.

---

## 1. Current State Assessment

### What We Have Today

| Asset | Details |
|-------|---------|
| **States** | Virginia (133 jurisdictions defined in config.json), Colorado (64 counties in jurisdictions.json) |
| **Active Data** | Henrico County VA (34 MB all_roads), Douglas County CO (18 MB all_roads) |
| **R2 Bucket** | `crash-lens-data/` with `{state}/{jurisdiction}/{file}.csv` structure |
| **Pipelines** | VA: `download_crash_data.py` (ArcGIS API), CO: `download_cdot_crash_data.py` (OnBase) + `process_crash_data.py` (5-stage pipeline) |
| **Validation** | Full system with auto-correction, geocoding, spatial validation |
| **Forecasting** | SageMaker Chronos-2 integration |
| **UI** | Single-jurisdiction view with Upload Data tab (state/jurisdiction dropdowns) |
| **State Adapter** | `states/state_adapter.js` — detects VA/CO from CSV headers, normalizes to VDOT format |
| **Existing Plans** | `JURISDICTION_EXPANSION_PLAN.md`, `PIPELINE_ARCHITECTURE.md`, `r2-integration-plan.md` |

### What Each Tier Needs

| Tier | User Persona | What They Need |
|------|-------------|---------------|
| **Federal** | FHWA analysts, NHTSA researchers | Cross-state comparisons, national safety trends, HSIP performance, Proven Safety Countermeasure adoption rates |
| **State** | VDOT HQ, CDOT HQ, State Safety Engineers | Statewide crash totals, county rankings, regional comparisons, SHSP progress tracking |
| **MPO** | DRCOG, Hampton Roads TPO, FAMPO planners | Multi-county aggregation within planning area, TIP project prioritization, safety target tracking |
| **County/City** | County engineers, city traffic departments | Current single-jurisdiction view (what we have now), plus peer comparison |

---

## 2. Data Pipeline Architecture

### 2.1 Should We Save State-Level Datasets Monthly?

**Recommendation: YES, but with a tiered storage strategy.**

#### Virginia — Full State Download is Already Feasible

The existing `download_crash_data.py` already downloads from the **statewide** Virginia Roads CSV endpoint:
```
https://www.virginiaroads.org/api/download/v1/items/1a96a2f31b4f4d77991471b6cabb38ba/csv
```

This endpoint returns **all Virginia crashes**. We currently filter it down to one jurisdiction. The change is minimal:

| Current Flow | Proposed Flow |
|-------------|--------------|
| Download statewide CSV → Filter to 1 jurisdiction → Upload 1 set to R2 | Download statewide CSV → Save state-level copy → Split into 133 jurisdictions → Upload all to R2 |

**Storage Cost Estimate (Virginia):**
- Statewide all_roads CSV: ~500 MB–1 GB (133 jurisdictions × ~5-30 MB each)
- Monthly snapshots: ~6–12 GB/year
- Cloudflare R2 free tier: 10 GB storage, 10 million reads/month — sufficient for first year
- After year 1: $0.015/GB/month = ~$0.18/month

**Recommended Monthly Cadence:**
- **Crash data**: Monthly (1st Monday) — already scheduled
- **Grants data**: Weekly (every Monday) — already scheduled
- **CMF data**: Quarterly — already scheduled
- **State-level snapshot**: Monthly alongside crash data (one extra save step)

#### Colorado — Requires Different Approach

CDOT publishes annual Excel files via OnBase, not a live API. The pipeline is:
1. Manual/scheduled download of annual Excel files
2. Process through 5-stage pipeline
3. Upload per-county results to R2

**Recommendation for CO:** Download the full annual statewide file, split by county on demand. No monthly snapshots needed since data only updates annually.

#### State-Level Dataset Structure

```
R2 State-Level Files:
  {state}/_statewide/
    all_roads.csv              ← Current month's complete dataset
    snapshots/
      2026-01_all_roads.csv    ← Monthly archive
      2026-02_all_roads.csv
    aggregates.json            ← Pre-computed state-level aggregates
    county_summary.json        ← Per-county summary stats (for state-level dashboard)
```

**Why pre-compute aggregates?** Loading a 500 MB+ statewide CSV in-browser is impractical. Instead:
- The pipeline computes state-level aggregates during processing
- A `county_summary.json` (~200-500 KB) gives the State-tier UI everything it needs
- County-level detail loads on demand when user drills down

### 2.2 Automated County-Level Dataset Generation

**Recommendation: Automate splitting from the statewide download.**

#### Virginia — Fully Automatable

The Virginia pipeline change is straightforward:

```
Current:
  download_crash_data.py --jurisdiction henrico → data/henrico_*.csv → R2

Proposed:
  download_crash_data.py --all-jurisdictions →
    For each of 133 jurisdictions:
      → data/virginia/{jurisdiction}/*.csv
      → Validate & Geocode
      → Upload to R2: virginia/{jurisdiction}/*.csv
    → Generate virginia/_statewide/aggregates.json
    → Generate virginia/_statewide/county_summary.json
```

**Implementation Strategy (using existing code):**

1. **Add `--all-jurisdictions` flag** to `download_crash_data.py`
   - Downloads statewide CSV once
   - Iterates through `config.json` jurisdictions
   - Filters by `jurisCode` or `namePatterns` (already implemented in the script)
   - Writes per-jurisdiction CSVs

2. **Batch validation** — Modify `validation/run_validation.py`
   - Already supports `--all-jurisdictions` mode
   - Run validation across all counties in one pass

3. **Batch R2 upload** — Modify `scripts/upload-to-r2.py`
   - Already supports `--state` and `--jurisdiction` parameters
   - Add `--all` flag to upload all jurisdictions for a state

4. **Workflow update** — Modify `download-data.yml`
   - Add a matrix strategy: run the same pipeline for each jurisdiction in parallel (GitHub Actions supports matrix builds)
   - Or: single job that loops through all jurisdictions sequentially

**Estimated Processing:**
- Virginia statewide CSV download: 1 download (~2-5 minutes)
- Split into 133 jurisdictions: ~1-2 minutes
- Validate all: ~10-20 minutes (with caching)
- Upload 133 × 3 road types = 399 files to R2: ~15-30 minutes
- **Total: ~30-60 minutes per monthly run** (within GitHub Actions free tier limits)

#### Colorado — Semi-Automated

CDOT data arrives as annual Excel files per year (not per county). The existing pipeline handles:
1. Download annual statewide file
2. Split by county using `scripts/split_cdot_data.py`
3. Process through 5-stage pipeline per county

**To automate for all 64 CO counties:**
- Extend `split_cdot_data.py` to emit all counties (not just Douglas)
- Extend `process_crash_data.py` to batch-process all counties
- Upload all to R2

#### Adding a New State

To onboard any new state, the process is:

1. **Create `states/{state}/config.json`** — Column mappings, value mappings, jurisdiction list
2. **Create download script** (if API available) or document manual upload process
3. **Extend `state_adapter.py`** — Add state signature for auto-detection
4. **Extend `state_adapter.js`** — Add browser-side normalization
5. **Run pipeline** — Process through existing 5-stage pipeline
6. **Upload to R2** — Uses existing `{state}/{jurisdiction}/` structure

The `PIPELINE_ARCHITECTURE.md` already documents this process thoroughly.

---

## 3. R2 Folder Structure

### 3.1 Recommended R2 Key Hierarchy

```
crash-lens-data/
│
├── _national/                              ← FEDERAL TIER
│   ├── state_comparison.json               ← Cross-state metrics (FARS-derived)
│   ├── fars_summary.json                   ← FARS fatality data by state
│   ├── hsip_performance.json               ← HSIP performance targets by state
│   └── snapshots/
│       └── 2026-02_state_comparison.json
│
├── virginia/                               ← STATE TIER (Virginia)
│   ├── _statewide/                         ← State-level aggregates
│   │   ├── aggregates.json                 ← Statewide totals, trends, YoY
│   │   ├── county_summary.json             ← Per-county ranking table
│   │   ├── mpo_summary.json                ← Per-MPO aggregates
│   │   ├── all_roads.csv                   ← Full state dataset (optional, for power users)
│   │   └── snapshots/
│   │       ├── 2026-01_aggregates.json
│   │       └── 2026-02_aggregates.json
│   │
│   ├── _mpo/                               ← MPO TIER (Virginia)
│   │   ├── hampton_roads/
│   │   │   ├── aggregates.json             ← MPO-level aggregates
│   │   │   ├── member_counties.json        ← County list + their stats
│   │   │   └── hotspots.json               ← Cross-county hotspot ranking
│   │   ├── northern_virginia/
│   │   │   ├── aggregates.json
│   │   │   ├── member_counties.json
│   │   │   └── hotspots.json
│   │   └── ... (other MPOs)
│   │
│   ├── henrico/                            ← COUNTY TIER (existing)
│   │   ├── all_roads.csv
│   │   ├── county_roads.csv
│   │   ├── no_interstate.csv
│   │   ├── forecasts_all_roads.json
│   │   ├── forecasts_county_roads.json
│   │   └── forecasts_no_interstate.json
│   │
│   ├── fairfax/                            ← Another county
│   │   ├── all_roads.csv
│   │   ├── county_roads.csv
│   │   └── ...
│   │
│   └── ... (131 more jurisdictions)
│
├── colorado/                               ← STATE TIER (Colorado)
│   ├── _statewide/
│   │   ├── aggregates.json
│   │   ├── county_summary.json
│   │   ├── region_summary.json             ← CDOT 5-region breakdown
│   │   └── snapshots/
│   │
│   ├── _region/                            ← CDOT REGION TIER (Colorado-specific)
│   │   ├── region_1/                       ← Denver Metro
│   │   │   ├── aggregates.json
│   │   │   ├── member_counties.json
│   │   │   └── hotspots.json
│   │   └── ... (4 more regions)
│   │
│   ├── _mpo/                               ← MPO TIER (Colorado)
│   │   ├── drcog/
│   │   │   ├── aggregates.json
│   │   │   └── member_counties.json
│   │   └── ... (other MPOs/TPRs)
│   │
│   ├── douglas/                            ← COUNTY TIER (existing)
│   │   ├── all_roads.csv
│   │   ├── county_roads.csv
│   │   ├── no_interstate.csv
│   │   └── standardized.csv
│   │
│   └── ... (63 more counties)
│
├── shared/                                 ← CROSS-CUTTING DATA
│   ├── grants.csv                          ← Federal + state grants
│   ├── cmf_processed.json                  ← CMF clearinghouse data
│   ├── cmf_metadata.json
│   └── mutcd/                              ← MUTCD reference data
│       └── *.json
│
└── manifest.json                           ← Master manifest of all files
```

### 3.2 Key Design Decisions

**Why `_statewide/`, `_mpo/`, `_region/` prefixes with underscore?**
- Prevents collision with county names (no county starts with `_`)
- Clear visual separation of aggregation tiers
- Consistent pattern across all states

**Why pre-computed aggregates instead of raw CSVs at higher tiers?**
- A state-level `all_roads.csv` for Virginia could be 500 MB–1 GB
- Browser can't process that in real time
- Pre-computed JSONs are 100–500 KB — instant load
- County CSVs remain the source of truth for drill-down

**What goes in aggregate JSONs?**
```json
// county_summary.json example
{
  "period": "2020-2024",
  "generated": "2026-02-13",
  "counties": {
    "henrico": {
      "total": 28500, "K": 89, "A": 412, "B": 1205, "C": 3890, "O": 22904,
      "epdo": 112340, "pedCrashes": 234, "bikeCrashes": 78,
      "topCollisionType": "Rear End", "trend": -0.03
    },
    "fairfax": { ... },
    ...
  }
}
```

### 3.3 R2 Cost Projection

| Scale | Storage | Monthly Cost (R2) |
|-------|---------|-------------------|
| Current (2 counties) | ~120 MB | Free tier |
| Virginia (133 jurisdictions) | ~4-8 GB | Free tier (10 GB free) |
| VA + CO (133 + 64) | ~8-15 GB | ~$0.08/month |
| 5 states | ~30-60 GB | ~$0.75/month |
| All 50 states | ~500 GB–1 TB | ~$7.50–$15/month |

R2 has no egress fees, so read costs are essentially zero.

---

## 4. UI Architecture: Jurisdiction Tier Selector

### 4.1 Where It Lives

**Location:** Inside the existing **Upload Data** tab, enhancing the current State/Jurisdiction selector.

Currently the Upload Data tab has:
- State dropdown → County dropdown → Road type radios

**Proposed Enhancement:**

```
┌─────────────────────────────────────────┐
│  📊 Data Scope                          │
│                                         │
│  View Level: [Federal ▾] [State ▾] [MPO ▾] [County ▾]  │
│              ─────────────────────────  │
│  (Tier selector — radio or segmented control)            │
│                                         │
│  ┌─── When "Federal" selected ──────┐   │
│  │ Showing: National Overview       │   │
│  │ States with data: VA, CO         │   │
│  │ [Load National Dashboard]        │   │
│  └──────────────────────────────────┘   │
│                                         │
│  ┌─── When "State" selected ────────┐   │
│  │ State: [Virginia ▾]             │   │
│  │ Showing: 133 jurisdictions       │   │
│  │ [Load State Dashboard]           │   │
│  └──────────────────────────────────┘   │
│                                         │
│  ┌─── When "MPO" selected ──────────┐   │
│  │ State: [Virginia ▾]             │   │
│  │ MPO:   [Hampton Roads TPO ▾]    │   │
│  │ Counties: Norfolk, VB, Ches...   │   │
│  │ [Load MPO Dashboard]             │   │
│  └──────────────────────────────────┘   │
│                                         │
│  ┌─── When "County" selected ───────┐   │
│  │ State: [Virginia ▾]             │   │
│  │ County: [Henrico ▾]             │   │
│  │ Road Type: ○ County ○ No I ● All│   │
│  │ [Load County Data]  (existing)   │   │
│  └──────────────────────────────────┘   │
│                                         │
└─────────────────────────────────────────┘
```

### 4.2 What Each View Shows in Explore Section

#### Federal View — National Overview

| Tab | Content | Data Source |
|-----|---------|-------------|
| **Dashboard** | States with data, total crashes/fatalities by state, national trends | `_national/state_comparison.json` |
| **Map** | US choropleth — states colored by fatality rate or EPDO | `_national/state_comparison.json` + state boundary GeoJSON |
| **Hot Spots** | Top N most dangerous corridors/intersections nationally | Aggregated from state-level data |
| **Safety Focus** | National emphasis areas (ped/bike, impaired, speeding, young drivers) | `_national/fars_summary.json` |
| **Analysis** | Cross-state comparison charts, trend lines | `_national/state_comparison.json` |

**Tabs hidden at Federal level:** Crash Tree, Intersections, Fatal & Speeding (too granular), Ped/Bike (separate national data needed), Crash Prediction, Deep Dive

**Data Source for Federal:**
- Primary: Aggregated from our state-level `aggregates.json` files
- Supplementary: FARS (Fatality Analysis Reporting System) data from NHTSA — downloadable CSV, updated annually
- Optional future: GES/CRSS national crash estimates

#### State View — Statewide Overview

| Tab | Content | Data Source |
|-----|---------|-------------|
| **Dashboard** | Total crashes, fatalities, severity breakdown, YoY trend, top 10 dangerous counties | `{state}/_statewide/county_summary.json` |
| **Map** | County choropleth — counties colored by EPDO, crash rate, fatality rate; click county to drill down | `{state}/_statewide/county_summary.json` + county boundary GeoJSON |
| **Crash Tree** | Statewide crash taxonomy | `{state}/_statewide/aggregates.json` |
| **Safety Focus** | State emphasis area performance | `{state}/_statewide/aggregates.json` |
| **Fatal & Speeding** | Statewide fatal/speeding stats | `{state}/_statewide/aggregates.json` |
| **Hot Spots** | Cross-county top dangerous locations | `{state}/_statewide/county_summary.json` |
| **Intersections** | Summary only — top N worst intersections statewide | Pre-computed in `aggregates.json` |
| **Analysis** | County comparison charts, regional trends | `{state}/_statewide/county_summary.json` |

**Tabs hidden at State level:** Ped/Bike (needs per-crash detail), Crash Prediction (county-level model), Deep Dive (needs raw rows)

#### MPO View — Regional Planning

| Tab | Content | Data Source |
|-----|---------|-------------|
| **Dashboard** | MPO totals, per-member-county breakdown table | `{state}/_mpo/{mpo}/aggregates.json` |
| **Map** | Member counties highlighted, crash heatmap across MPO area | `{state}/_mpo/{mpo}/member_counties.json` + county CSVs (lazy load) |
| **Hot Spots** | Cross-county hotspot ranking within MPO | `{state}/_mpo/{mpo}/hotspots.json` |
| **Safety Focus** | MPO emphasis areas | `{state}/_mpo/{mpo}/aggregates.json` |
| **Analysis** | Inter-county comparison within MPO | Member county summaries |
| **Intersections** | Top N intersections across all MPO counties | Pre-computed in `hotspots.json` |

**Key MPO feature:** Click a county in the MPO dashboard → drills down to County view for that county.

#### County/City View — Detailed Analysis (Existing)

All existing tabs work as-is. This is the current default and requires no changes. Every Explore tab is available with full crash-level detail.

### 4.3 Tab Visibility Matrix

| Tab | Federal | State | MPO | County |
|-----|---------|-------|-----|--------|
| Dashboard | ✅ Adapted | ✅ Adapted | ✅ Adapted | ✅ Existing |
| Map | ✅ Choropleth | ✅ Choropleth | ✅ Hybrid | ✅ Existing |
| Crash Tree | ❌ | ✅ Adapted | ❌ | ✅ Existing |
| Safety Focus | ✅ Adapted | ✅ Adapted | ✅ Adapted | ✅ Existing |
| Fatal & Speeding | ❌ | ✅ Adapted | ❌ | ✅ Existing |
| Hot Spots | ✅ Adapted | ✅ Adapted | ✅ Adapted | ✅ Existing |
| Intersections | ❌ | ⚠️ Summary | ✅ Adapted | ✅ Existing |
| Ped/Bike | ❌ | ❌ | ❌ | ✅ Existing |
| Analysis | ✅ Adapted | ✅ Adapted | ✅ Adapted | ✅ Existing |
| Crash Prediction | ❌ | ❌ | ❌ | ✅ Existing |
| Deep Dive | ❌ | ❌ | ❌ | ✅ Existing |

**✅ = Available, ⚠️ = Limited, ❌ = Hidden**

### 4.4 Solutions, Grants, Reports — No Tier Changes

Per the existing expansion plan, these stay single-jurisdiction:

| Section | Behavior Across Tiers |
|---------|----------------------|
| **CMF/Countermeasures** | Always requires a specific location. User must drill to County view first. |
| **Warrant Analyzer** | Requires specific intersection volumes. County view only. |
| **MUTCD AI** | Reference tool — works at any tier (not data-dependent). |
| **Domain Knowledge** | Reference tool — works at any tier. |
| **Grants** | Display at any tier, but grant applications are per-jurisdiction. State view could show grants available to all counties. |
| **Reports** | Generated for specific jurisdictions. State view could offer "state summary report" as new template. |

---

## 5. Pipeline Implementation Plan

### Phase 1: State-Level Foundation (Build First)

**Goal:** Generate and store state-level aggregate data for VA and CO.

**Changes to existing code:**

| File | Change |
|------|--------|
| `download_crash_data.py` | Add `--all-jurisdictions` flag. After downloading statewide CSV, loop through config.json jurisdictions and split. |
| `scripts/process_crash_data.py` | Add `--generate-aggregates` flag. After processing county CSVs, compute state-level `aggregates.json` and `county_summary.json`. |
| `scripts/upload-to-r2.py` | Add `--all` flag. Support uploading `_statewide/` and `_mpo/` folders. |
| `.github/workflows/download-data.yml` | Add job step for state-level aggregate generation after county processing. |
| `data/r2-manifest.json` | Extend to track `_statewide/` and `_mpo/` files. |

**New files to create:**

| File | Purpose |
|------|---------|
| `scripts/generate_aggregates.py` | Reads all county CSVs for a state, produces `aggregates.json`, `county_summary.json`, `mpo_summary.json` |
| `states/virginia/hierarchy.json` | Defines VA MPOs, PDCs, VDOT districts with member counties |
| `states/colorado/hierarchy.json` | Already partially exists. Defines CDOT regions, MPOs/TPRs with member counties |

**Aggregate JSON Schema:**
```json
{
  "state": "virginia",
  "period": "2020-2025",
  "generated": "2026-02-13T00:00:00Z",
  "statewide": {
    "total": 450000, "K": 890, "A": 4120, "B": 12050,
    "C": 38900, "O": 394040, "epdo": 1234567,
    "pedCrashes": 5600, "bikeCrashes": 1200,
    "yearlyTrend": [
      {"year": 2020, "total": 85000, "K": 170},
      {"year": 2021, "total": 88000, "K": 185}
    ],
    "topCollisionTypes": [
      {"type": "Rear End", "count": 156000, "pct": 34.7},
      {"type": "Angle", "count": 98000, "pct": 21.8}
    ]
  },
  "counties": {
    "henrico": {
      "name": "Henrico County",
      "total": 28500, "K": 89, "A": 412, "B": 1205,
      "epdo": 112340, "crashRate": 4.2,
      "trend": -0.03, "rank": 5
    }
  },
  "mpos": {
    "hampton_roads": {
      "name": "Hampton Roads TPO",
      "memberCounties": ["norfolk", "virginia_beach", "chesapeake", "newport_news", "hampton", "suffolk", "portsmouth", "williamsburg", "york", "james_city", "gloucester", "isle_of_wight", "poquoson"],
      "total": 45000, "K": 156, "epdo": 267890
    }
  }
}
```

### Phase 2: Automated Multi-County Processing

**Goal:** Run the pipeline for all jurisdictions in a state, not just one.

**Workflow Strategy Options:**

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| **A. Sequential loop** | One GitHub Actions job loops through all counties | Simple, no concurrency issues | Slow (~2-4 hours for 133 VA counties) |
| **B. Matrix strategy** | GitHub Actions matrix spawns parallel jobs per county | Fast (~20-30 min), built-in parallelism | 133 parallel jobs may exceed GitHub limits |
| **C. Batch groups** | Matrix with county batches (10-15 counties per job) | Balanced speed/resources | Moderate complexity |
| **D. Chunked pipeline** | Download once → split locally → process in batches → upload all | Most efficient, single download | Requires the most pipeline refactoring |

**Recommendation: Option D (Chunked Pipeline)**

```
Step 1: Download statewide CSV once
Step 2: Split into 133 jurisdiction CSVs (fast, CPU-only)
Step 3: Batch validate (shared geocode cache across counties)
Step 4: Batch upload to R2 (all 399 files)
Step 5: Generate state-level aggregates
Step 6: Upload aggregates to R2
Step 7: Commit updated r2-manifest.json
```

This reuses the statewide download, shares the geocode cache (massive speedup), and does one batch upload.

### Phase 3: MPO/Regional Aggregation

**Goal:** Generate MPO-level and regional aggregates.

**Requires:** `hierarchy.json` files defining which counties belong to which MPOs.

**Processing Flow:**
```
County CSVs already in R2
        ↓
generate_aggregates.py --state virginia --tier mpo
        ↓
For each MPO in hierarchy.json:
    → Load member county CSVs
    → Compute aggregate stats
    → Compute cross-county hotspot ranking
    → Write {state}/_mpo/{mpo}/aggregates.json
    → Write {state}/_mpo/{mpo}/hotspots.json
        ↓
Upload to R2
```

### Phase 4: Federal/National Tier

**Goal:** Aggregate across states for national view.

**Data Sources:**
1. **Our own data:** Roll up state-level `aggregates.json` files from all onboarded states
2. **FARS data:** NHTSA publishes annual fatality data for all 50 states as downloadable CSVs from `https://www.nhtsa.gov/file-downloads`
3. **HSIP performance:** Available from FHWA performance reports

**New Script:** `scripts/generate_national_summary.py`
- Reads all `{state}/_statewide/aggregates.json` files
- Optionally merges FARS data for non-onboarded states (gives 50-state fatality map even if we only have detailed data for 2-3 states)
- Outputs `_national/state_comparison.json`

### Phase 5: UI Implementation

**Goal:** Add tier selector to Upload Data tab and adapt Explore tabs.

**Implementation approach:**
1. Add tier selector segmented control to Upload Data tab
2. Add `viewTier` to the global `jurisdictionContext` state object
3. Each Explore tab checks `jurisdictionContext.viewTier` and renders accordingly:
   - County → existing behavior (no changes)
   - State/MPO/Federal → loads aggregate JSONs, renders adapted views
4. Map tab switches between choropleth (state/MPO) and markers (county)
5. Dashboard tab switches between county dashboard (existing) and comparison table (state/MPO/federal)

**Progressive Loading:**
- Federal: Load `_national/state_comparison.json` (~50 KB)
- State: Load `{state}/_statewide/county_summary.json` (~200 KB)
- MPO: Load `{state}/_mpo/{mpo}/aggregates.json` (~50 KB)
- County: Load county CSV from R2 (~5-30 MB) — existing behavior

---

## 6. Hierarchy Configuration

### Virginia Hierarchy (to create: `states/virginia/hierarchy.json`)

```json
{
  "state": "virginia",
  "vdotDistricts": {
    "richmond": {
      "name": "Richmond District",
      "counties": ["henrico", "chesterfield", "hanover", "goochland", "powhatan", "new_kent", "charles_city", "richmond_city", "colonial_heights", "hopewell", "petersburg"]
    },
    "hampton_roads": {
      "name": "Hampton Roads District",
      "counties": ["norfolk", "virginia_beach", "chesapeake", "newport_news", "hampton", "suffolk", "portsmouth", "williamsburg", "york", "james_city", "gloucester", "isle_of_wight", "poquoson"]
    }
  },
  "mpos": {
    "hrtpo": {
      "name": "Hampton Roads Transportation Planning Organization",
      "counties": ["norfolk", "virginia_beach", "chesapeake", "newport_news", "hampton", "suffolk", "portsmouth", "williamsburg", "york", "james_city", "gloucester", "isle_of_wight", "poquoson"]
    },
    "fampo": {
      "name": "Fredericksburg Area MPO",
      "counties": ["fredericksburg", "spotsylvania", "stafford"]
    },
    "nvta": {
      "name": "Northern Virginia Transportation Authority",
      "counties": ["arlington", "fairfax", "loudoun", "prince_william", "alexandria", "fairfax_city", "falls_church", "manassas", "manassas_park"]
    },
    "rrtpo": {
      "name": "Richmond Regional Transportation Planning Organization",
      "counties": ["henrico", "chesterfield", "hanover", "goochland", "powhatan", "new_kent", "charles_city", "richmond_city"]
    }
  },
  "planningDistrictCommissions": {
    "pdc5": {
      "name": "Thomas Jefferson Planning District",
      "counties": ["albemarle", "charlottesville", "fluvanna", "greene", "louisa", "nelson"]
    }
  }
}
```

### Colorado Hierarchy (to extend: `states/colorado/hierarchy.json`)

Already partially defined. Needs:
- CDOT Region → County mappings (5 regions)
- MPO/TPR → County mappings (15 TPRs)

---

## 7. Complete Phased Roadmap

### Phase 1 — State-Level Aggregates ⟵ Start Here
- [ ] Create `scripts/generate_aggregates.py`
- [ ] Create `states/virginia/hierarchy.json`
- [ ] Extend `download_crash_data.py` with `--all-jurisdictions` flag
- [ ] Extend `scripts/upload-to-r2.py` to handle `_statewide/` paths
- [ ] Test: Generate VA statewide aggregates from Henrico data as proof of concept
- [ ] Update `r2-manifest.json` schema to support aggregate files

### Phase 2 — Multi-County Automation
- [ ] Implement chunked pipeline (download once → split → batch process → upload)
- [ ] Update `download-data.yml` workflow for batch processing
- [ ] Run full Virginia pipeline (133 jurisdictions) — verify R2 output
- [ ] Run full Colorado pipeline (64 counties) — verify R2 output
- [ ] Implement incremental processing (only re-process counties with new data)

### Phase 3 — MPO/Regional Aggregation
- [ ] Complete `states/virginia/hierarchy.json` (all MPOs, VDOT districts, PDCs)
- [ ] Complete `states/colorado/hierarchy.json` (all CDOT regions, TPRs)
- [ ] Extend `generate_aggregates.py` for MPO-level computation
- [ ] Generate and upload MPO aggregates to R2
- [ ] Generate cross-county hotspot rankings per MPO

### Phase 4 — UI Tier Selector
- [ ] Add tier selector to Upload Data tab (Federal / State / MPO / County)
- [ ] Add `viewTier` to `jurisdictionContext` global state
- [ ] Implement data loading logic per tier (aggregate JSONs vs county CSVs)
- [ ] Adapt Dashboard tab for State and MPO views
- [ ] Adapt Map tab for choropleth (state/MPO) vs markers (county)
- [ ] Adapt Hot Spots tab for cross-county ranking
- [ ] Implement drill-down navigation (State → County, MPO → County)
- [ ] Hide/show tabs based on tier (visibility matrix)

### Phase 5 — Federal Tier
- [ ] Create `scripts/generate_national_summary.py`
- [ ] Integrate FARS data for 50-state fatality baseline
- [ ] Implement Federal view in Dashboard (state comparison table)
- [ ] Implement Federal view in Map (US choropleth)
- [ ] Cross-state comparison charts in Analysis tab

### Phase 6 — New State Onboarding
- [ ] Document onboarding checklist (states/{state}/config.json template)
- [ ] Create state onboarding CLI tool or script
- [ ] Onboard first new state (e.g., Maryland, North Carolina — VDOT-adjacent, similar data)
- [ ] Verify full pipeline: download → validate → geocode → split → aggregate → upload → display

---

## 8. Key Recommendations

### 8.1 Storage Strategy

| Data Tier | Store in R2? | Store in Git? | Format | Update Frequency |
|-----------|-------------|---------------|--------|------------------|
| National aggregates | ✅ | ❌ | JSON | Monthly |
| State aggregates | ✅ | ❌ | JSON | Monthly |
| MPO aggregates | ✅ | ❌ | JSON | Monthly |
| County crash CSVs | ✅ | ❌ | CSV | Monthly |
| County forecasts | ✅ | ✅ (small) | JSON | Monthly |
| Grants | ❌ | ✅ | CSV | Weekly |
| CMF data | ❌ | ✅ | JSON | Quarterly |
| MUTCD reference | ❌ | ✅ | JSON | Rarely |
| Config/hierarchy | ❌ | ✅ | JSON | As needed |
| R2 manifest | ❌ | ✅ | JSON | After each upload |

### 8.2 Performance Strategy

| Tier | Expected Data Size | Load Strategy |
|------|-------------------|---------------|
| Federal | ~50 KB (aggregate JSON) | Instant load |
| State | ~200-500 KB (county summary JSON) | Instant load |
| MPO | ~50-100 KB (aggregate JSON) | Instant load |
| County | ~5-30 MB (crash CSV) | Progressive load with spinner |
| County (large) | ~50-100 MB (e.g., Fairfax) | Chunked loading, IndexedDB cache |

### 8.3 Data Freshness

| Concern | Solution |
|---------|----------|
| How current is the data? | Show `generated` timestamp from aggregate JSONs |
| Monthly vs real-time? | Monthly is standard for crash data (reports take weeks to file). Display "Data through: January 2026" |
| Stale data warning | If aggregate `generated` date is >45 days old, show amber warning |

### 8.4 GeoJSON Boundary Files

For choropleth maps at State and MPO tiers, we need boundary polygons:

| Boundary | Source | Size | Storage |
|----------|--------|------|---------|
| US States | Census Bureau TIGER/Line simplified | ~2 MB | R2: `shared/boundaries/us_states.geojson` |
| VA Counties | Census Bureau | ~3 MB | R2: `shared/boundaries/virginia_counties.geojson` |
| CO Counties | Census Bureau | ~2 MB | R2: `shared/boundaries/colorado_counties.geojson` |
| VA MPOs | MPO boundary shapefiles | ~1 MB | R2: `shared/boundaries/virginia_mpos.geojson` |
| CO TPRs | CDOT TPR boundaries | ~1 MB | R2: `shared/boundaries/colorado_tprs.geojson` |

The TIGERweb API integration already exists in `config.json` — we can use it to fetch boundaries on demand, or pre-download and cache in R2 for performance.

### 8.5 Security & Access Control

| Tier | Who Should See It | Access Control Suggestion |
|------|-------------------|--------------------------|
| Federal | FHWA, state DOTs, researchers | Public (crash data is public record) |
| State | State DOT, MPOs, counties, public | Public |
| MPO | MPO staff, member counties, public | Public |
| County | County engineers, city staff, public | Public |

Crash data is generally public record. However, some states restrict detailed location/severity data. If access control is needed later, Cloudflare Access or Firebase Auth (already configured) can gate R2 access.

### 8.6 Monitoring & Alerting

Extend the existing `send-notifications.yml` workflow:

| Alert | Trigger | Recipient |
|-------|---------|-----------|
| Pipeline success | Monthly run completes | State DOT data steward |
| Pipeline failure | Any stage fails | Engineering team |
| Data quality drop | Error rate > threshold | Data steward |
| New data available | R2 upload complete | Subscribed county engineers |
| Stale data | No update in 45+ days | Engineering team |

---

## 9. Summary: Answering Your Questions

### Q1: Should we save entire state-level dataset monthly?
**Yes**, but save the **aggregate** (JSON, ~200-500 KB) monthly, not the raw statewide CSV (~500 MB). The per-county CSVs in R2 serve as the detail. Only save raw statewide CSVs if you need historical snapshots for trend analysis (store in `_statewide/snapshots/`).

### Q2: Automated way to get county-level datasets for other counties?
**Yes.** Modify `download_crash_data.py` to iterate through all jurisdictions in `config.json` after a single statewide download. For Colorado, extend `split_cdot_data.py` to emit all 64 counties. The "chunked pipeline" approach (download once → split → batch process → upload) is the most efficient.

### Q3: How to arrange R2 folders?
Use the hierarchy: `{state}/{jurisdiction}/` for county data, `{state}/_statewide/` for aggregates, `{state}/_mpo/{mpo}/` for MPO aggregates, `_national/` for federal data, `shared/` for cross-cutting data (grants, CMF, boundaries).

### Q4: How to arrange UI?
Add a **tier selector** (Federal / State / MPO / County) to the Upload Data tab. Each tier loads different data and shows/hides Explore tabs accordingly. Only the **Explore section** changes per tier. Solutions, Grants, and Reports remain single-jurisdiction tools.

### Q5: Everything else to consider?
- Pre-compute aggregates (don't load 500 MB in browser)
- Use hierarchy.json files to define MPO/region memberships
- Start with Virginia (data is already accessible via API)
- GeoJSON boundary files needed for choropleth maps
- Existing TIGERweb integration can provide boundaries
- R2 costs remain near-zero even at 50-state scale
- FARS data gives national fatality baseline for states we haven't onboarded yet
- Incremental processing (only re-process counties with changes) saves CI time
- IndexedDB caching in browser reduces repeat R2 fetches
