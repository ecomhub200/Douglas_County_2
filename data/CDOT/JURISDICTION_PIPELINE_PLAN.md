# Jurisdiction Pipeline Plan: Federal → State → MPO → County/City

## Executive Summary

This plan defines how to extend CRASH LENS from its current 2-jurisdiction setup (Henrico County VA + Douglas County CO) to a multi-tier system supporting **Federal, State, and MPO** views — while keeping the **existing County/City view completely untouched**. All new views build on pre-computed aggregate data loaded from R2, using the existing pipeline infrastructure.

**Scope:** Federal, State, and MPO tiers only. County view remains as-is.

---

## 1. Current State Assessment

### What We Have Today

| Asset | Details |
|-------|---------|
| **States** | Virginia (133 jurisdictions in config.json), Colorado (64 counties in jurisdictions.json) |
| **Active Data** | Henrico County VA (34 MB all_roads), Douglas County CO (18 MB all_roads) |
| **R2 Bucket** | `crash-lens-data/` with `{state}/{jurisdiction}/{file}.csv` structure |
| **Pipelines** | VA: `download_crash_data.py` (ArcGIS API — full state download, replaces previous), CO: `download_cdot_crash_data.py` (OnBase — updated year only, replaces previous) |
| **Validation** | Full system with auto-correction, geocoding, spatial validation |
| **Forecasting** | SageMaker Chronos-2 integration |
| **UI** | Single-jurisdiction view with Upload Data tab (state/jurisdiction/road-type dropdowns) |
| **Map Asset Layers** | Mapillary (coverage, signs, features), TIGERweb (county boundary, magisterial districts), BTS/NTAD (AADT, bridges, railroad crossings, transit stops, transit routes), user-uploaded assets |
| **State Adapter** | `scripts/state_adapter.py` — normalizes to VDOT format |

### What Each New Tier Needs

| Tier | User Persona | What They Need |
|------|-------------|---------------|
| **Federal** | FHWA analysts, NHTSA researchers | Cross-state comparisons, national safety trends, HSIP performance |
| **State** | VDOT HQ, CDOT HQ, State Safety Engineers | Statewide crash totals, county rankings, regional comparisons, road type filtering |
| **MPO** | DRCOG, Hampton Roads TPO, FAMPO planners | Multi-county aggregation within planning boundary, cross-county hotspot ranking, road type filtering |

---

## 2. Data Pipeline Architecture

### 2.1 State-Specific Download Strategies

**Each state has fundamentally different data sources and update patterns. The pipeline must respect these differences.**

| State | Download Strategy | What Gets Replaced | Frequency |
|-------|-------------------|-------------------|-----------|
| **Virginia** | Full statewide CSV download from Virginia Roads ArcGIS API | Entire dataset replaced each run | Monthly (1st Monday) |
| **Colorado** | Updated year's Excel from CDOT OnBase portal | Only the new/updated year file replaces the previous version of that year | Monthly (1st of month) |

#### Virginia Pipeline (Replace-All Strategy)

```
download_crash_data.py --all-jurisdictions
    │
    ├─ 1. Download full statewide CSV (~500 MB) from Virginia Roads
    │     (replaces any previous statewide file entirely)
    │
    ├─ 2. Split into 133 jurisdictions by jurisCode
    │     Each jurisdiction's CSV replaces previous version
    │
    ├─ 3. Validate + Geocode (batch, shared cache)
    │
    ├─ 4. Generate road-type variants per county
    │     county_roads.csv, no_interstate.csv, all_roads.csv
    │
    ├─ 5. Upload all county CSVs to R2 (overwrite)
    │
    └─ 6. Generate state + MPO aggregates → Upload to R2
```

#### Colorado Pipeline (Year-Update Strategy)

```
download_cdot_crash_data.py --latest
    │
    ├─ 1. Download latest year's Excel from OnBase
    │     (only the updated year, e.g., 2025.xlsx replaces previous 2025.xlsx)
    │
    ├─ 2. Merge updated year into county's multi-year dataset
    │     Existing prior years remain untouched
    │
    ├─ 3. Process through 5-stage pipeline per county
    │     Stage 1: Standardize → Stage 2: Validate → Stage 3: Geocode
    │     → Stage 4: Split by road type → Stage 5: Forecast
    │
    ├─ 4. Upload county CSVs to R2 (overwrite)
    │
    └─ 5. Generate state + MPO/region aggregates → Upload to R2
```

#### Key Design Rule: No Historical Snapshots of Raw Data

Since both states use a **replace** strategy (VA replaces entire dataset, CO replaces the updated year), we do NOT store monthly snapshots of raw CSVs. The data in R2 is always the **current** version. Historical trend analysis comes from the crash dates within the dataset itself, not from multiple snapshot files.

What we DO archive monthly: the small aggregate JSONs (`aggregates.json`, `county_summary.json`) so we can track how our aggregated metrics change over time (e.g., did a county's crash count go up after a data correction?).

```
R2 Archive (aggregates only, not raw CSVs):
  {state}/_statewide/
    aggregates.json              ← Current
    county_summary.json          ← Current
    snapshots/
      2026-01_aggregates.json    ← Monthly aggregate archive (~200 KB each)
      2026-02_aggregates.json
```

### 2.2 Dataset Size Reduction Strategies

**Current sizes:**
| Dataset | Files | Total Size |
|---------|-------|------------|
| Colorado / Douglas (4 CSVs) | standardized + 3 road types | 57.9 MB |
| Virginia / Henrico (3 CSVs) | 3 road types | 76.5 MB |
| **Total** | | **134.4 MB** |

At scale: 133 VA jurisdictions × 3 road types × ~25 MB avg = **~10 GB**. Size reduction is critical.

#### Strategy 1: Drop Unused Columns (Savings: ~15%)

The Colorado pipeline currently outputs **112 columns**, but the UI (`COL` object in index.html) only references **57**. There are **26 columns** that are written to CSVs but never read by the browser:

| Category | Unused Columns | Count |
|----------|---------------|-------|
| Non-motorist 2 (entire block) | `_co_nm2_type`, `_co_nm2_age`, `_co_nm2_sex`, `_co_nm2_action`, `_co_nm2_movement`, `_co_nm2_location`, `_co_nm2_facility`, `_co_nm2_contributing_factor` | 8 |
| Transport Unit 2 details | `_co_tu2_direction`, `_co_tu2_movement`, `_co_tu2_estimated_speed`, `_co_tu2_speed_limit`, `_co_tu2_stated_speed` | 5 |
| Redundant/tracking | `_co_crash_type`, `_co_total_vehicles`, `_co_injury00_uninjured`, `_co_link`, `_co_location2`, `_co_rd_number`, `_co_weather2`, `_source_file` | 8 |
| NM1 partial | `_co_nm1_age`, `_co_nm1_movement`, `_co_nm1_sex` | 3 |
| TU1 partial | `_co_tu1_direction`, `_co_tu1_movement` | 2 |

**Action:** Add `--slim` flag to `state_adapter.py` that drops unused columns from output. Keep a `--full` mode for archival/research use.

#### Strategy 2: Encode Categorical Values (Savings: ~20%)

The VDOT-format categorical values are verbose strings. Examples:

| Column | Current Value (avg 30 chars) | Encoded (avg 2 chars) |
|--------|------------------------------|----------------------|
| Weather | `1. No Adverse Condition (Clear/Cloudy)` | `1` |
| Road Desc | `3. Two-Way, Divided, Positive Median Barrier` | `3` |
| Relation To Roadway | `10. Intersection Related - Within 150 Feet` | `10` |
| Light | `5. Darkness - Road Not Lighted` | `5` |
| Collision Type | `4. Sideswipe - Same Direction` | `4` |
| Surface | `6. Sand/Mud/Dirt/Oil/Gravel` | `6` |
| Intersection Type | `1. Not at Intersection` | `1` |

Across 11 categorical columns × thousands of rows, each row saves ~120 characters.

**Action:** Store only the numeric prefix code in CSVs. Add a lightweight `value_labels.json` (~5 KB) lookup table in R2 that the UI loads once at startup to reconstruct display labels.

```json
// shared/value_labels.json (loaded once, cached)
{
  "Weather Condition": {
    "1": "No Adverse Condition (Clear/Cloudy)",
    "2": "Blowing Sand/Snow",
    "3": "Fog/Smog"
  },
  "Collision Type": {
    "1": "Rear End",
    "2": "Angle",
    "3": "Head On"
  }
}
```

#### Strategy 3: Boolean Encoding (Savings: ~4%)

18 boolean columns currently store `"Yes"/"No"`. The UI's `isYes()` function already handles `"1"`, `"Y"`, `"y"`, `"Yes"`.

**Action:** Encode as `"1"/"0"` in pipeline output. No UI changes needed.

#### Strategy 4: Coordinate Rounding (Savings: ~2%)

GPS coordinates like `-104.952300000000` can be truncated to 5 decimal places (`-104.95230`), which is ~1.1 meter accuracy — more than sufficient for crash mapping.

**Action:** Round `x` and `y` to 5 decimal places in `state_adapter.py`.

#### Strategy 5: Gzip/Brotli Compression on R2 (Savings: ~70% transfer)

R2 supports serving pre-compressed files. CSV compresses extremely well.

**Action:** Upload `.csv.gz` alongside `.csv`. Browser decompresses transparently with `Accept-Encoding: gzip`. A 25 MB CSV becomes ~5-7 MB over the wire.

#### Combined Impact Estimate

| Strategy | Per-File Savings | Risk | Priority |
|----------|-----------------|------|----------|
| Drop unused columns | ~15% | None (columns not used) | P0 |
| Encode categoricals | ~20% | Low (add decode table) | P1 |
| Boolean encoding | ~4% | None (isYes() handles it) | P0 |
| Coordinate rounding | ~2% | None (1m accuracy sufficient) | P0 |
| Gzip on R2 | ~70% transfer | None (transparent) | P0 |
| **Combined** | **~41% file size, ~85% transfer** | | |

**Projected sizes at Virginia scale (133 jurisdictions):**

| Metric | Before | After (slim+encode) | After (+ gzip transfer) |
|--------|--------|---------------------|------------------------|
| Per-county CSV | ~25 MB avg | ~15 MB avg | ~4 MB transfer |
| State total (133 × 3) | ~10 GB | ~6 GB | ~1.6 GB transfer |
| R2 storage cost | ~$0.15/mo | ~$0.09/mo | Same (storage) |

### 2.3 Automated Multi-County Processing

**Recommendation: Chunked Pipeline (Option D)**

```
Step 1: Download statewide dataset once
        VA: full CSV from Virginia Roads (replaces previous)
        CO: latest year Excel from OnBase (replaces that year only)
Step 2: Split into per-jurisdiction CSVs (fast, CPU-only)
Step 3: Batch validate (shared geocode cache across all counties — massive speedup)
Step 4: Generate road-type variants per county (all_roads, county_roads, no_interstate)
Step 5: Batch upload to R2 (all files, overwrite)
Step 6: Generate state + MPO aggregates from county CSVs
Step 7: Upload aggregates to R2
Step 8: Commit updated r2-manifest.json
```

**Estimated processing (Virginia, 133 jurisdictions):**
| Step | Time |
|------|------|
| Download statewide CSV | ~2-5 min |
| Split into 133 jurisdictions | ~1-2 min |
| Batch validate (cached geocodes) | ~10-20 min |
| Road-type split (133 × 3 = 399 files) | ~5 min |
| Upload 399 + aggregates to R2 | ~15-30 min |
| Generate aggregates | ~5 min |
| **Total** | **~40-65 min** (within GitHub Actions free tier) |

---

## 3. R2 Folder Structure

### 3.1 Recommended R2 Key Hierarchy

```
crash-lens-data/
│
├── _national/                              ← FEDERAL TIER
│   ├── state_comparison.json               ← Cross-state metrics (our data + FARS)
│   ├── fars_summary.json                   ← FARS fatality data by state
│   ├── hsip_performance.json               ← HSIP performance targets by state
│   └── snapshots/
│       └── 2026-02_state_comparison.json
│
├── virginia/                               ← STATE TIER (Virginia)
│   ├── _statewide/                         ← State-level aggregates
│   │   ├── aggregates.json                 ← Statewide totals, trends, YoY
│   │   ├── county_summary.json             ← Per-county ranking table (by road type)
│   │   ├── mpo_summary.json                ← Per-MPO aggregates (by road type)
│   │   └── snapshots/
│   │       ├── 2026-01_aggregates.json
│   │       └── 2026-02_aggregates.json
│   │
│   ├── _mpo/                               ← MPO TIER (Virginia)
│   │   ├── hrtpo/
│   │   │   ├── aggregates.json             ← MPO-level aggregates (by road type)
│   │   │   ├── member_counties.json        ← County list + per-county stats
│   │   │   └── hotspots.json               ← Cross-county hotspot ranking
│   │   ├── nvta/
│   │   │   ├── aggregates.json
│   │   │   ├── member_counties.json
│   │   │   └── hotspots.json
│   │   └── ... (other MPOs)
│   │
│   ├── henrico/                            ← COUNTY TIER (existing, untouched)
│   │   ├── all_roads.csv
│   │   ├── county_roads.csv
│   │   ├── no_interstate.csv
│   │   ├── forecasts_all_roads.json
│   │   ├── forecasts_county_roads.json
│   │   └── forecasts_no_interstate.json
│   │
│   └── ... (132 more jurisdictions)
│
├── colorado/                               ← STATE TIER (Colorado)
│   ├── _statewide/
│   │   ├── aggregates.json
│   │   ├── county_summary.json
│   │   ├── region_summary.json             ← CDOT 5-region breakdown
│   │   └── snapshots/
│   │
│   ├── _region/                            ← CDOT REGION TIER (CO-specific)
│   │   ├── region_1/
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
│   ├── douglas/                            ← COUNTY TIER (existing, untouched)
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
│   ├── value_labels.json                   ← Categorical value decode table (~5 KB)
│   ├── boundaries/                         ← GeoJSON boundaries for choropleth maps
│   │   ├── us_states.geojson               ← Federal tier map
│   │   ├── virginia_counties.geojson       ← VA state tier map
│   │   ├── colorado_counties.geojson       ← CO state tier map
│   │   ├── virginia_mpos.geojson           ← VA MPO boundaries (from BTS NTAD)
│   │   └── colorado_mpos.geojson           ← CO MPO boundaries (from BTS NTAD)
│   └── mutcd/                              ← MUTCD reference data
│       └── *.json
│
└── manifest.json                           ← Master manifest of all files
```

### 3.2 Aggregate JSONs Include Road-Type Breakdowns

Since State and MPO views will support road type filtering (same as County), aggregates must include per-road-type stats:

```json
// county_summary.json schema
{
  "state": "virginia",
  "period": "2020-2025",
  "generated": "2026-02-13T00:00:00Z",
  "roadTypes": {
    "all_roads": {
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
          "name": "Henrico County", "fips": "087",
          "total": 28500, "K": 89, "A": 412, "B": 1205,
          "epdo": 112340, "crashRate": 4.2,
          "trend": -0.03, "rank": 5,
          "center": [-77.45, 37.55]
        }
      }
    },
    "county_roads": {
      "statewide": { ... },
      "counties": { ... }
    },
    "no_interstate": {
      "statewide": { ... },
      "counties": { ... }
    }
  },
  "mpos": {
    "hrtpo": {
      "name": "Hampton Roads TPO",
      "memberCounties": ["norfolk", "virginia_beach", "chesapeake", ...],
      "all_roads": { "total": 45000, "K": 156, "epdo": 267890 },
      "county_roads": { "total": 18000, "K": 42, "epdo": 98000 },
      "no_interstate": { "total": 38000, "K": 120, "epdo": 210000 }
    }
  }
}
```

---

## 4. UI Architecture: Tier Selector + Map Strategy

### 4.1 Tier Selector in Upload Data Tab

**Location:** Inside the existing Upload Data tab, above the current State/Jurisdiction selector.

```
┌──────────────────────────────────────────────────┐
│  📊 View Level                                    │
│                                                   │
│  ┌─────────┐ ┌─────────┐ ┌──────┐ ┌──────────┐  │
│  │ Federal │ │  State  │ │ MPO  │ │ County ● │  │
│  └─────────┘ └─────────┘ └──────┘ └──────────┘  │
│  (Segmented control — County is default/existing) │
│                                                   │
│  ╔═══ When "Federal" selected ═══════════════╗    │
│  ║ Showing: National Overview                ║    │
│  ║ States with data: Virginia, Colorado      ║    │
│  ║ Road Type: ○ County ○ No Interstate ● All ║    │
│  ║ [Load National View]                      ║    │
│  ╚═══════════════════════════════════════════╝    │
│                                                   │
│  ╔═══ When "State" selected ═════════════════╗    │
│  ║ State: [Virginia ▾]                       ║    │
│  ║ Road Type: ○ County ○ No Interstate ● All ║    │
│  ║ [Load State View]                         ║    │
│  ╚═══════════════════════════════════════════╝    │
│                                                   │
│  ╔═══ When "MPO" selected ═══════════════════╗    │
│  ║ State: [Virginia ▾]                       ║    │
│  ║ MPO:   [Hampton Roads TPO ▾]              ║    │
│  ║ Road Type: ○ County ○ No Interstate ● All ║    │
│  ║ Member Counties: Norfolk, VB, Ches...     ║    │
│  ║ [Load MPO View]                           ║    │
│  ╚═══════════════════════════════════════════╝    │
│                                                   │
│  ╔═══ When "County" selected (EXISTING) ═════╗    │
│  ║ State: [Virginia ▾]                       ║    │
│  ║ County: [Henrico ▾]                       ║    │
│  ║ Road Type: ○ County ○ No Interstate ● All ║    │
│  ║ [Load County Data] (existing behavior)    ║    │
│  ╚═══════════════════════════════════════════╝    │
│                                                   │
└──────────────────────────────────────────────────┘
```

**Road type selector at every tier:** The existing 3-option radio (County Roads / No Interstate / All Roads) appears for Federal, State, MPO, and County views. This filters which aggregate data is displayed at higher tiers, and which CSV variant loads at county tier.

### 4.2 Map Strategy for Each View Level

#### Current County Map (Untouched)

The existing Leaflet.js map with:
- **Base layers:** OpenStreetMap (street) / Mapbox Satellite
- **Crash markers:** Clustered markers, heatmap, individual pins
- **Asset Layers Panel** with toggles for:
  - Mapillary: Coverage (green lines), Traffic Signs, Map Features
  - TIGERweb: County Boundary (dashed blue), Magisterial Districts (colored subdivisions)
  - BTS/NTAD: AADT Network, Bridge Inventory, Railroad Crossings, Transit Stops, Transit Routes
  - User-uploaded assets

#### Federal Map — US State Choropleth

| Aspect | Design |
|--------|--------|
| **Base** | Same Leaflet instance, zoomed to CONUS (center: [-98.5, 39.8], zoom: 4) |
| **Primary Layer** | State-level choropleth polygons colored by selected metric |
| **Boundary Source** | `shared/boundaries/us_states.geojson` from R2 (pre-downloaded from Census TIGER/Line, simplified to ~2 MB) |
| **Color Metric** | Selectable: Total Crashes, Fatalities (K), KA Rate, EPDO, Crash Trend (dropdown above map) |
| **Interaction** | Hover: tooltip with state name + metrics. Click: drills down to State view for that state |
| **Legend** | Color ramp legend showing min/max values for selected metric |
| **Road Type** | Switches which set of aggregate numbers powers the choropleth coloring |

**Asset Layers at Federal Level:**

| Layer | Available? | Behavior |
|-------|-----------|----------|
| Mapillary Coverage | ❌ Hidden | Too zoomed out, not useful |
| Mapillary Signs | ❌ Hidden | Too zoomed out |
| Mapillary Features | ❌ Hidden | Too zoomed out |
| TIGERweb Boundaries | ❌ Hidden | State boundaries come from GeoJSON choropleth |
| Magisterial Districts | ❌ Hidden | County-level only |
| BTS AADT Network | ❌ Hidden | Too much data nationally |
| BTS Bridges | ✅ Available | National bridge condition overview (clustered) |
| BTS Railroad Crossings | ❌ Hidden | Too much data nationally |
| BTS Transit Stops | ❌ Hidden | Too much data nationally |
| BTS Transit Routes | ❌ Hidden | Too much data nationally |
| User Assets | ✅ Available | If user uploaded national-scope assets |

#### State Map — County Choropleth

| Aspect | Design |
|--------|--------|
| **Base** | Same Leaflet instance, zoomed to state bounds (from config.json state bbox) |
| **Primary Layer** | County-level choropleth polygons colored by selected metric |
| **Boundary Source** | `shared/boundaries/{state}_counties.geojson` from R2 (pre-downloaded from Census, ~2-3 MB per state) |
| **MPO Overlay** | Optional toggle: MPO boundary outlines (dashed purple, from BTS NTAD MPO FeatureServer — see Section 5) overlaid on county choropleth |
| **Color Metric** | Selectable dropdown: Total Crashes, K Fatalities, KA Rate, EPDO, Ped/Bike Crashes, Crash Trend |
| **Interaction** | Hover: tooltip with county name + metrics. Click: drills down to County view |
| **Road Type** | Radio selection switches which road-type aggregate set colors the choropleth |
| **Legend** | Color ramp legend |

**Asset Layers at State Level:**

| Layer | Available? | Behavior |
|-------|-----------|----------|
| Mapillary Coverage | ❌ Hidden | Too zoomed out for state view |
| Mapillary Signs | ❌ Hidden | Too zoomed out |
| Mapillary Features | ❌ Hidden | Too zoomed out |
| TIGERweb Boundaries | ✅ Adapted | County boundaries come from choropleth GeoJSON |
| Magisterial Districts | ❌ Hidden | County-level only |
| BTS AADT Network | ⚠️ Toggle | Show NHS network overlay (filter to NHS routes only for performance) |
| BTS Bridges | ✅ Available | Clustered at state zoom, shows condition ratings |
| BTS Railroad Crossings | ✅ Available | Clustered at state zoom |
| BTS Transit Stops | ❌ Hidden | Too dense at state zoom |
| BTS Transit Routes | ✅ Available | Major routes visible at state zoom |
| **NEW: BTS MPO Boundaries** | ✅ Available | Toggle to show all MPO boundaries overlaid (see Section 5) |
| User Assets | ✅ Available | If user uploaded state-scope assets |

#### MPO Map — Hybrid Choropleth + Heatmap

| Aspect | Design |
|--------|--------|
| **Base** | Same Leaflet instance, zoomed to MPO bounding box |
| **Primary Layer** | MPO boundary polygon (from BTS NTAD, bold outline) with member county sub-boundaries |
| **Boundary Source** | BTS NTAD MPO boundary (Section 5) + `shared/boundaries/{state}_counties.geojson` filtered to member counties |
| **County Fill** | Member counties colored by metric (mini-choropleth within MPO) |
| **Crash Layer** | Heatmap or clustered crash markers aggregated from all member county CSVs (lazy-loaded) |
| **Color Metric** | Same dropdown as State view |
| **Interaction** | Hover county: tooltip. Click county: drills down to County view. Click cluster: zoom in |
| **Road Type** | Radio switches aggregate data + which crash CSVs to load for heatmap |
| **Progressive Detail** | At higher zoom levels, transition from heatmap to individual crash markers (same as current county behavior) |

**Asset Layers at MPO Level:**

| Layer | Available? | Behavior |
|-------|-----------|----------|
| Mapillary Coverage | ✅ Available | Visible at MPO zoom level |
| Mapillary Signs | ✅ Available | Visible when zoomed to street level within MPO |
| Mapillary Features | ✅ Available | Visible when zoomed to street level within MPO |
| TIGERweb Boundaries | ✅ Adapted | Member county boundaries from choropleth |
| Magisterial Districts | ⚠️ On drill | Available when user hovers/clicks into a specific county |
| BTS AADT Network | ✅ Available | Full AADT network within MPO bounds |
| BTS Bridges | ✅ Available | All bridges within MPO |
| BTS Railroad Crossings | ✅ Available | All crossings within MPO |
| BTS Transit Stops | ✅ Available | All transit stops within MPO |
| BTS Transit Routes | ✅ Available | All transit routes within MPO |
| **NEW: BTS MPO Boundary** | ✅ Always On | Bold MPO boundary outline always visible |
| User Assets | ✅ Available | If user uploaded MPO-scope assets |

#### Map Rendering Summary

| View | Crash Display | Boundaries | Zoom Level | Asset Layer Availability |
|------|---------------|-----------|------------|--------------------------|
| **Federal** | None (aggregates only) | State choropleth polygons | ~4 (CONUS) | Bridges only |
| **State** | None (aggregates only) | County choropleth polygons + MPO outlines | ~6-8 (state) | Bridges, Railroad, Transit Routes, AADT (NHS), MPO boundaries |
| **MPO** | Heatmap → Clusters → Markers (progressive) | MPO boundary + member county fills | ~8-12 (region) | All layers available |
| **County** | Clusters → Markers (existing) | County boundary + districts (existing) | ~10-14 (county) | All layers available (existing, untouched) |

---

## 5. BTS MPO Boundary API Integration

### 5.1 BTS NTAD MPO FeatureServer

The Bureau of Transportation Statistics publishes official MPO boundaries via a **free, public ArcGIS REST API** — no API key required:

**Primary Endpoint:**
```
https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/NTAD_Metropolitan_Planning_Organizations/FeatureServer/0
```

**Query for a specific state (e.g., Virginia):**
```
/query?where=STATE='VA'&outFields=MPO_ID,MPO_NAME,ACRONYM,STATE,POP&returnGeometry=true&f=geojson
```

**Available Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `MPO_ID` | String | Unique MPO identifier |
| `MPO_NAME` | String | Full MPO name |
| `ACRONYM` | String | Short name (e.g., "HRTPO") |
| `STATE` | String | Primary state (e.g., "VA") |
| `STATE_2` | String | Secondary state (multi-state MPOs) |
| `STATE_3` | String | Third state |
| `POP` | Integer | Population served |
| `MPO_URL` | String | MPO website |
| `Shape` | Polygon | Geographic boundary geometry |

### 5.2 Integration into Asset Layers

Add BTS MPO Boundaries as a new layer in the existing **Asset Layers Panel**, alongside the existing BTS layers:

```
Asset Layers Panel (updated):
  ├── Mapillary Layers
  │   ├── 📷 Street Imagery Coverage
  │   ├── 🚦 Traffic Signs
  │   └── 🛤️ Map Features
  │
  ├── BTS Federal Data
  │   ├── 🛣️ AADT Road Network       (existing)
  │   ├── 🌉 Bridge Inventory         (existing)
  │   ├── 🚂 Railroad Grade Crossings (existing)
  │   ├── 🚏 Transit Stops            (existing)
  │   ├── 🚌 Transit Routes           (existing)
  │   └── 🗺️ MPO Boundaries          ← NEW
  │
  ├── Jurisdiction Boundaries
  │   ├── 📍 County/City Boundary     (existing)
  │   └── 🗺️ Magisterial Districts   (existing)
  │
  └── User Uploaded Assets            (existing)
```

**Implementation Details:**

```javascript
// Add to BTS_ENDPOINTS object (line ~110061 in index.html)
btsMPOBoundaries: {
  name: 'MPO Boundaries',
  description: 'Metropolitan Planning Organization boundaries from BTS/NTAD',
  icon: '🗺️',
  color: '#7c3aed',  // Purple (matches district styling)
  url: 'https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/NTAD_Metropolitan_Planning_Organizations/FeatureServer/0',
  geometryType: 'polygon',
  minZoom: 0,
  pageSize: 500,
  maxPages: 5,
  popupFields: ['MPO_NAME', 'ACRONYM', 'STATE', 'POP', 'MPO_URL'],
  style: {
    color: '#7c3aed',
    weight: 2,
    fillOpacity: 0.08,
    dashArray: '6, 3'
  }
}
```

**Query Strategy:**
- **Federal view:** Load all MPOs nationally (`where=1=1`)
- **State view:** Filter by state (`where=STATE='VA' OR STATE_2='VA' OR STATE_3='VA'`)
- **MPO view:** Load the selected MPO boundary only
- **County view:** Load MPOs that intersect the county bbox (spatial query)

**Caching:** Cache the GeoJSON per-state in `builtInLayersState.btsMPOBoundaries.geojsonCache[stateKey]` — same pattern as existing BTS layers.

### 5.3 Additional BTS Layers to Consider

The NTAD provides ~90 datasets. Beyond the 5 already integrated + MPO Boundaries, these are relevant for a crash analysis tool:

| Dataset | Endpoint | Relevance | Priority |
|---------|----------|-----------|----------|
| **Counties** | `NTAD_Counties/FeatureServer` | Alternate county boundaries for choropleth | Low (TIGERweb already provides this) |
| **Urbanized Areas** | `Urbanized_Areas/MapServer` | Context for urban/rural crash analysis | Medium |
| **Freight Analysis Framework** | `Freight_Analysis_Framework_Network/MapServer` | Truck crash context | Medium |
| **NHS (National Highway System)** | In HPMS dataset | Filter AADT to NHS-only for state view | High |
| **Airports** | `Airports/MapServer` | Context for crashes near airports | Low |
| **Bikeshare Stations** | Available in NTAD | Context for bike crash analysis | Medium |

**Recommendation:** Add MPO Boundaries now (directly supports the MPO tier). Add Urbanized Areas and Freight Network later as optional layers.

---

## 6. Explore Section: Tab Behavior Per Tier

### 6.1 Tab Visibility Matrix

**County view is completely untouched.** The following shows behavior for the 3 new tiers only:

| Tab | Federal | State | MPO |
|-----|---------|-------|-----|
| Dashboard | ✅ State comparison table | ✅ County ranking table | ✅ Member county table |
| Map | ✅ State choropleth | ✅ County choropleth + MPO outlines | ✅ MPO boundary + county fills + heatmap |
| Crash Tree | ❌ Hidden | ✅ Statewide taxonomy | ❌ Hidden |
| Safety Focus | ✅ National emphasis | ✅ State emphasis | ✅ MPO emphasis |
| Fatal & Speeding | ❌ Hidden | ✅ Statewide stats | ❌ Hidden |
| Hot Spots | ✅ Top locations nationally | ✅ Top locations statewide | ✅ Cross-county ranking |
| Intersections | ❌ Hidden | ⚠️ Top N summary | ✅ Cross-county |
| Ped/Bike | ❌ Hidden | ❌ Hidden | ❌ Hidden |
| Analysis | ✅ Cross-state charts | ✅ County comparison | ✅ Inter-county |
| Crash Prediction | ❌ Hidden | ❌ Hidden | ❌ Hidden |
| Deep Dive | ❌ Hidden | ❌ Hidden | ❌ Hidden |

### 6.2 Drill-Down Navigation

Every higher-tier view supports drill-down to County:

| From | Action | Result |
|------|--------|--------|
| Federal Dashboard | Click state row | Switch to State view for that state |
| Federal Map | Click state polygon | Switch to State view for that state |
| State Dashboard | Click county row | Switch to County view for that county |
| State Map | Click county polygon | Switch to County view for that county |
| MPO Dashboard | Click county row | Switch to County view for that county |
| MPO Map | Click county polygon | Switch to County view for that county |

Drill-down loads the county CSV from R2 (existing behavior), sets the road type filter, and switches the tier selector to "County."

---

## 7. Complete Phased Roadmap

### Phase 1 — Pipeline: Size Reduction + Multi-County (Build First)
- [ ] Add `--slim` flag to `state_adapter.py` to drop 26 unused columns
- [ ] Implement boolean encoding (`1`/`0`) and coordinate rounding (5 decimals)
- [ ] Add categorical value encoding (numeric prefix only) + create `shared/value_labels.json`
- [ ] Add `--all-jurisdictions` flag to `download_crash_data.py` (VA: split from statewide download)
- [ ] Extend `split_cdot_data.py` to emit all 64 CO counties
- [ ] Extend `scripts/upload-to-r2.py` to batch-upload all jurisdictions
- [ ] Enable gzip/brotli compression on R2 uploads

### Phase 2 — Pipeline: Aggregates + Hierarchy
- [ ] Create `scripts/generate_aggregates.py` (reads county CSVs → produces aggregates with road-type breakdowns)
- [ ] Create `states/virginia/hierarchy.json` (all MPOs, VDOT districts, PDCs)
- [ ] Complete `states/colorado/hierarchy.json` (CDOT regions, MPOs/TPRs)
- [ ] Generate and upload state + MPO aggregates for VA and CO
- [ ] Archive monthly aggregate snapshots in `_statewide/snapshots/`
- [ ] Update `download-data.yml` workflow for batch processing + aggregate generation

### Phase 3 — Map: Boundaries + BTS MPO Layer
- [ ] Pre-download state/county boundary GeoJSONs from Census TIGER/Line → upload to R2 `shared/boundaries/`
- [ ] Add BTS MPO Boundaries as new layer in `BTS_ENDPOINTS` object
- [ ] Implement `addBTSMPOBoundaryLayer()` with state-filtered queries
- [ ] Add MPO Boundaries toggle to Asset Layers Panel
- [ ] Test: VA MPOs load correctly, CO MPOs load correctly, multi-state MPOs handled

### Phase 4 — UI: Tier Selector
- [ ] Add tier selector segmented control (Federal / State / MPO / County) to Upload Data tab
- [ ] Add road type selector to Federal, State, MPO tiers (reuse existing radio component)
- [ ] Add `viewTier` to global `jurisdictionContext` state object
- [ ] Implement data loading logic per tier (aggregate JSONs from R2)
- [ ] Implement tab visibility toggling based on tier (hide/show tabs per matrix above)

### Phase 5 — UI: State View
- [ ] Implement State Dashboard (county ranking table with road-type switching)
- [ ] Implement State Map (county choropleth with metric dropdown + MPO overlay toggle)
- [ ] Adapt Hot Spots for cross-county ranking
- [ ] Adapt Safety Focus for statewide emphasis areas
- [ ] Adapt Analysis for county comparison charts
- [ ] Implement drill-down: click county → load County view

### Phase 6 — UI: MPO View
- [ ] Implement MPO Dashboard (member county breakdown table)
- [ ] Implement MPO Map (MPO boundary + county fills + progressive crash heatmap/clusters)
- [ ] Implement lazy-loading of member county CSVs for crash-level heatmap
- [ ] Adapt Hot Spots for cross-county hotspot ranking within MPO
- [ ] Implement drill-down: click county → load County view

### Phase 7 — UI: Federal View
- [ ] Create `scripts/generate_national_summary.py` (roll up state aggregates + FARS data)
- [ ] Implement Federal Dashboard (state comparison table)
- [ ] Implement Federal Map (US state choropleth with metric dropdown)
- [ ] Adapt Safety Focus for national emphasis areas
- [ ] Implement drill-down: click state → load State view

### Phase 8 — New State Onboarding
- [ ] Document onboarding checklist (states/{state}/config.json template)
- [ ] Create state onboarding script (column mapping wizard)
- [ ] Onboard first new state (e.g., Maryland or North Carolina)
- [ ] Verify full pipeline: download → validate → geocode → split → aggregate → upload → display

---

## 8. Key Recommendations

### 8.1 Storage Strategy

| Data Tier | Store in R2? | Store in Git? | Format | Update |
|-----------|-------------|---------------|--------|--------|
| National aggregates | ✅ | ❌ | JSON | Monthly |
| State aggregates | ✅ | ❌ | JSON | Monthly (archive snapshots) |
| MPO aggregates | ✅ | ❌ | JSON | Monthly |
| County crash CSVs | ✅ | ❌ | CSV (slim+encoded) | Monthly (replace, no snapshots) |
| County forecasts | ✅ | ✅ (small) | JSON | Monthly |
| Value labels | ✅ | ✅ | JSON (~5 KB) | Rarely |
| Boundary GeoJSONs | ✅ | ❌ | GeoJSON | Annually (Census updates) |
| Grants | ❌ | ✅ | CSV | Weekly |
| CMF data | ❌ | ✅ | JSON | Quarterly |
| Config/hierarchy | ❌ | ✅ | JSON | As needed |
| R2 manifest | ❌ | ✅ | JSON | After each upload |

### 8.2 R2 Cost Projection (with size reduction)

| Scale | Storage (slim CSVs) | Monthly Cost |
|-------|---------------------|-------------|
| Current (2 counties) | ~80 MB | Free |
| Virginia (133 counties) | ~3-5 GB | Free (10 GB free tier) |
| VA + CO (133 + 64) | ~5-9 GB | Free |
| 5 states | ~20-40 GB | ~$0.45/month |
| All 50 states | ~300-600 GB | ~$4.50-$9/month |

### 8.3 Performance Strategy

| Tier | Data Load | Transfer (gzipped) | Load Time |
|------|-----------|-------------------|-----------|
| Federal | ~50 KB aggregate JSON | ~15 KB | Instant |
| State | ~200-500 KB summary JSON | ~60-150 KB | Instant |
| MPO | ~50-100 KB aggregate JSON | ~15-30 KB | Instant |
| MPO (with crash heatmap) | ~30-90 MB member county CSVs | ~8-25 MB | Progressive (2-5s per county) |
| County | ~15 MB slim CSV | ~4 MB | 1-3 seconds |

### 8.4 Asset Layer Adaptations Summary

| Asset Layer | Federal | State | MPO | County |
|-------------|---------|-------|-----|--------|
| Mapillary Coverage | ❌ | ❌ | ✅ | ✅ |
| Mapillary Signs | ❌ | ❌ | ✅ | ✅ |
| Mapillary Features | ❌ | ❌ | ✅ | ✅ |
| BTS AADT Network | ❌ | ⚠️ NHS only | ✅ Full | ✅ Full |
| BTS Bridges | ✅ Clustered | ✅ Clustered | ✅ | ✅ |
| BTS Railroad Crossings | ❌ | ✅ Clustered | ✅ | ✅ |
| BTS Transit Stops | ❌ | ❌ | ✅ | ✅ |
| BTS Transit Routes | ❌ | ✅ Major | ✅ | ✅ |
| **BTS MPO Boundaries** | ✅ All | ✅ State-filtered | ✅ Selected | ⚠️ Intersecting |
| TIGERweb Boundary | ❌ | Via choropleth | Via choropleth | ✅ Existing |
| Magisterial Districts | ❌ | ❌ | ⚠️ On drill | ✅ Existing |
| User Assets | ✅ | ✅ | ✅ | ✅ |

### 8.5 BTS MPO Boundary Queries Per Tier

| Tier | Query | Expected Records |
|------|-------|-----------------|
| Federal | `where=1=1` (all MPOs nationally) | ~400 MPOs |
| State | `where=STATE='VA' OR STATE_2='VA' OR STATE_3='VA'` | ~10-15 per state |
| MPO | `where=MPO_ID='{selected}'` | 1 |
| County | Spatial query: `geometry={county_bbox}&spatialRel=esriSpatialRelIntersects` | 0-3 |

### 8.6 Additional Federal Data Sources

| Source | What It Provides | Download | Integration |
|--------|-----------------|----------|-------------|
| **FARS** (NHTSA) | Fatality data for all 50 states | Annual CSV from NHTSA | Script: `download_fars_data.py` |
| **HSIP Performance** (FHWA) | Safety targets by state | FHWA reports | Manual or scrape |
| **GES/CRSS** (NHTSA) | National crash estimates (sampled) | Annual from NHTSA | Optional supplement |
| **BTS NTAD Counties** | County boundaries for all states | Free ArcGIS REST | For choropleth maps |
| **BTS NTAD Urbanized Areas** | Urban/rural boundaries | Free ArcGIS REST | Context layer |
| **BTS Freight Analysis Framework** | Freight network for truck crashes | Free ArcGIS REST | Optional layer |
