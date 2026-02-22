# Different View Configuration Plan

## Multi-Tier View Architecture: State, Region, MPO

**Date:** February 22, 2026
**Author:** Crash Lens Engineering
**Scope:** Explore section only (Dashboard, Map, Crash Tree, Safety Focus, Fatal & Speeding, Hot Spots, Intersections, Ped/Bike, Analysis, Deep Dive, Crash Prediction)
**Excluded:** Solutions section (CMF, Warrants, MUTCD AI, Domain Knowledge), Grants, Reports
**Status:** Planning

---

## 1. What Already Exists (Built Infrastructure)

Before describing what needs to be built, it is essential to document the significant tier infrastructure already implemented in `app/index.html`. This avoids duplicating work and ensures new development builds on existing foundations.

### 1.1 Tier Selector Buttons (UI)

Four tier buttons exist in the sidebar (~line 4688–4695):

```
[ State ] [ Region ] [ MPO ] [ County (active) ]
```

- Buttons call `handleTierChange(tier)` on click
- Active button gets `.active` class styling
- County is the default active tier

### 1.2 Region & MPO Dropdown Selectors (UI)

Region dropdown (~line 4699–4703):
```html
<div id="tierRegionRow" style="display:none">
  <select id="tierRegionSelect" onchange="handleRegionSelection()">
```

MPO dropdown (~line 4705–4709):
```html
<div id="tierMPORow" style="display:none">
  <select id="tierMPOSelect" onchange="handleMPOSelection()">
```

- Region row shows when "Region" tier is active; MPO row shows for "MPO" tier
- Dropdowns are populated from `hierarchy.json` via `populateRegionDropdown()` and `populateMPODropdown()`

### 1.3 Jurisdiction Locking for Solutions Scope

When switching from county to a higher tier, the existing county is stored in `jurisdictionContext.solutionsScopeCounty` so Solutions/Grants tabs can still operate at county level while Explore tabs show multi-county data.

### 1.4 Road Type Filter Labels (Tier-Aware)

`updateRoadTypeLabels(tier)` (~line 23325) switches radio button labels per tier:

| Radio | State / Region | County / MPO (_default) |
|-------|---------------|------------------------|
| Radio 1 | **DOT Roads Only** – State DOT-maintained roads | **County/City Roads Only** – Local roads (non-state) |
| Radio 2 | **Non-DOT Roads** – Local and non-state roads | **All Roads (No Interstate)** – Includes state routes |
| Radio 3 | **Statewide All Roads** – DOT + Non-DOT combined | **All Roads** – Including interstates |

### 1.5 Tier-Aware R2 Data Paths

`getDataFilePath()` (~line 23362) constructs cloud storage paths per tier:

| Tier | Path Pattern | Example |
|------|-------------|---------|
| State | `{r2Prefix}/_state/{roadType}.csv` | `virginia/_state/dot_roads.csv` |
| Region | `{r2Prefix}/_region/{regionId}/{roadType}.csv` | `virginia/_region/hampton_roads/dot_roads.csv` |
| MPO | `{r2Prefix}/_mpo/{mpoId}/{roadType}.csv` | `virginia/_mpo/hrtpo/all_roads.csv` |
| County | `{r2Prefix}/{fips}/{roadType}.csv` | `virginia/51087/all_roads.csv` |

`getActiveRoadTypeSuffix(tier)` maps radio values to file suffixes per tier.

### 1.6 Data Loading per Tier

Three loading functions exist:

- **`loadStatewideCSVForTier()`** (~line 20790): Streams entire state CSV via Papa.parse chunked loading. Stores rows in `crashState.sampleRows`, computes aggregates, then calls `onCrashDataReady()`.
- **`handleRegionSelection()`** (~line 20888): Loads region-scoped CSV from R2. Renders district boundary from `hierarchy.json`. Updates aggregates and calls `onCrashDataReady()`.
- **`handleMPOSelection()`** (~line 20941): Loads MPO-scoped CSV from R2. Has 3-strategy BTS NTAD boundary lookup for MPO polygon. Updates aggregates and calls `onCrashDataReady()`.

All three ultimately call `onCrashDataReady()` which triggers `updateDashboard()`, chart renders, etc.

### 1.7 Map Boundary Rendering per Tier

- **State tier**: Fetches state outline from TIGERweb Census boundary service via `BoundaryService.getStateOutline()`; flies map to state extent
- **Region tier**: Renders district polygon from `hierarchy.json` geometry; zooms to district bounds
- **MPO tier**: 3-strategy BTS NTAD boundary lookup (`BoundaryService.getMPOBoundary()`); falls back through BTS acronym → partial name match → county FIPS union
- **County tier**: Standard jurisdiction boundary from TIGERweb
- Boundary layers are properly cleaned up when switching tiers (`removeMPOBoundaryLayer`, `removeRegionBoundaryLayer`, etc.)

### 1.8 Tab Visibility Matrix

`TIER_TAB_VISIBILITY` (~line 20545) controls which sidebar tabs show per tier:

| Tab | State | Region | MPO | County |
|-----|-------|--------|-----|--------|
| Dashboard | ✅ | ✅ | ✅ | ✅ |
| Map | ✅ | ✅ | ✅ | ✅ |
| Crash Tree | ✅ | ✅ | ❌ | ✅ |
| Safety Focus | ✅ | ✅ | ✅ | ✅ |
| Fatal & Speeding | ✅ | ✅ | ❌ | ✅ |
| Hot Spots | ✅ | ✅ | ✅ | ✅ |
| Intersections | ✅ | ✅ | ✅ | ✅ |
| Ped/Bike | ❌ | ✅ | ✅ | ✅ |
| Analysis | ✅ | ✅ | ✅ | ✅ |
| Deep Dive | ❌ | ❌ | ❌ | ✅ |
| Crash Prediction | ✅ | ✅ | ✅ | ✅ |

`updateTabVisibilityForTier(tier)` (~line 20564) shows/hides sidebar items accordingly.

### 1.9 Scope Indicator

A scope indicator element exists in the sidebar that shows the current tier context (e.g., "State: Virginia" or "MPO: HRTPO"). Updates via `updateScopeIndicator()`.

### 1.10 Hierarchy Data (Virginia)

`states/virginia/hierarchy.json` defines:
- **9 VDOT Construction Districts** with county FIPS arrays, geometry boundaries
- **8 MPOs** (HRTPO, NVTA, RVARC, FAMPO, CAMPO, RVAMPO, SAWMPO, WinFredMPO) with county FIPS, BTS acronyms, population
- Key corridors with county and region references

Loaded via `HierarchyRegistry.load(stateDir)`.

---

## 2. What Is NOT Built Yet (The Gaps)

Despite the extensive infrastructure above, the actual **Explore tab content** does not adapt when a non-county tier is selected. Specifically:

### 2.1 Dashboard Tab — No Tier Adaptation

`updateDashboard()` (~line 45854) renders the same KPI cards, EPDO breakdown, and charts regardless of tier. It uses `getFilteredStats()` which returns aggregates — but the **UI layout** is identical whether showing state data or county data. Missing:

- No **county comparison table/heatmap** when showing multi-county tiers
- No **per-county breakdown** of KPIs
- District Matrix widget (magisterial districts at ~line 5645) is county-specific and shows even at state/region/mpo tiers where it makes no sense
- No **SHSP target tracking** panel for state tier
- No **PM1 performance measures** panel for MPO tier
- No **jurisdiction ranking** by severity, crash rate, or EPDO
- KPI header doesn't reflect the scope (e.g., should say "HRTPO Region" not just county name)

### 2.2 Map Tab — No Tier-Specific Rendering

The map loads crash markers at all tiers (via `onCrashDataReady()`), but:

- No **heat map** or **cluster density** mode for high-volume tiers (state can have 100K+ crashes)
- No **county boundary overlay** showing choropleth coloring by crash density
- No **click-to-drill-down** from county polygon to county view
- Marker rendering will be slow/unusable at state tier with full crash CSV

### 2.3 Hot Spots — No Multi-County Ranking

Hot Spots tab ranks routes within a single jurisdiction. At higher tiers:

- Should rank routes **across all member counties**
- Should show which county each hot spot belongs to
- Should allow filtering by member county

### 2.4 Safety Focus — County-Centric Labels

Safety Focus categories (rear-end, angle, run-off-road, etc.) render the same regardless of tier:

- Should show **county comparison** within each category at higher tiers
- Header should reflect scope

### 2.5 Intersections — No Cross-County Context

Intersection analysis is meaningful at all tiers, but:

- At higher tiers, should show **county name** alongside each intersection
- Should allow sorting/filtering by member county

### 2.6 Analysis Tab — No Tier Context

Analysis tab charts work with whatever aggregates are loaded, but:

- Should add **county-level breakdowns** in charts (stacked bars by county)
- Should show comparison metrics

### 2.7 No County Comparison Module

The most significant missing feature: when a user selects State, Region, or MPO — they are looking at **multiple counties**. There is no way to:

- Compare counties side by side
- Rank counties by crash rate, severity, EPDO
- See which counties drive the overall numbers
- Identify outlier counties needing attention

### 2.8 No Drill-Down Navigation

No ability to click from a state-tier county comparison into that county's full detail view:

- State → Region → County click-through
- MPO → County click-through
- Breadcrumb navigation showing tier path

---

## 3. Virginia Geographic Hierarchy Reference

### 3.1 State Level
- **Virginia (FIPS 51)**: 95 counties + 38 independent cities = 133 jurisdictions
- **State-level users**: VDOT Central Office, FHWA Virginia Division, Virginia Highway Safety Office (VHSO)

### 3.2 VDOT Construction Districts (Regions)

| District | Key Cities | County Count | Key Corridors |
|----------|-----------|--------------|---------------|
| Bristol | Bristol, Abingdon, Norton | 11 | I-81, US-19, US-23, US-58 |
| Salem | Roanoke, Blacksburg, Radford | 14 | I-81, I-581, US-460, US-220 |
| Lynchburg | Lynchburg, Bedford | 13 | US-29, US-460, US-501 |
| Richmond | Richmond, Petersburg | 22 | I-95, I-64, I-295, US-1, US-360 |
| Hampton Roads | Norfolk, Virginia Beach, Newport News | 15 | I-64, I-264, I-664, US-13, US-58 |
| Fredericksburg | Fredericksburg, Stafford | 9 | I-95, US-1, US-17, US-301 |
| Culpeper | Charlottesville, Culpeper, Staunton | 13 | I-64, US-29, US-15, US-33 |
| Staunton | Harrisonburg, Winchester | 10 | I-81, I-64, US-11, US-33 |
| NOVA | Arlington, Alexandria, Fairfax | 10 | I-95, I-66, I-495, I-395, US-50 |

### 3.3 MPOs

| MPO | Short Name | Population | Counties | Parent District |
|-----|-----------|------------|----------|-----------------|
| Hampton Roads TPO | HRTPO | 1,840,000 | 16 | Hampton Roads |
| Northern Virginia TA | NVTA | 3,100,000 | 10 | NOVA |
| Roanoke Valley-Alleghany RC | RVARC | 310,000 | 5 | Salem |
| Fred. Area MPO | FAMPO | 385,000 | 4 | Fredericksburg |
| Charlottesville-Albemarle MPO | CAMPO | 240,000 | 3 | Culpeper |
| Richmond Area MPO | RVAMPO | 1,310,000 | 9 | Richmond |
| Staunton-Augusta-Waynesboro MPO | SAWMPO | 125,000 | 3 | Staunton |
| Winchester-Frederick MPO | WinFredMPO | 140,000 | 3 | Staunton |

---

## 4. User Personas & Their Analytical Needs

### 4.1 State-Level User (VDOT Central Office / VHSO / FHWA Division)

**Job**: Allocate HSIP funds, set statewide safety targets, track SHSP progress, report to FHWA.

**Questions they ask**:
- Which districts/corridors have the worst fatal+serious injury trends?
- Are we meeting our SHSP targets (fatality reduction, serious injury reduction)?
- Where should we direct the next round of HSIP funding?
- How does this year compare to our 5-year rolling average?
- Which crash types are growing fastest statewide?

**What they need from Crash Lens**:
- District-level comparison heatmap (all 9 districts ranked)
- SHSP target tracking panel (fatality count vs target, serious injury count vs target)
- Statewide trend charts with year-over-year comparison
- Top 20 worst corridors across the entire state
- Click from district → drill into that district's detail view

### 4.2 Region-Level User (District Traffic Engineer / District Safety Engineer)

**Job**: Prioritize safety projects within their district, prepare HSIP applications, respond to citizen concerns.

**Questions they ask**:
- Which counties in my district have the most severe crashes?
- What corridors within my district need attention?
- How do my district's numbers compare to adjacent districts?
- What countermeasures will be most effective for my crash patterns?
- Where are the pedestrian/bicycle problem areas?

**What they need from Crash Lens**:
- County comparison matrix within their district (all member counties ranked)
- Top corridors by EPDO within the district
- Trend charts showing district total and per-county breakdown
- Quick drill-down from county row to full county analysis
- Ped/Bike tab (already visible for region tier)

### 4.3 MPO-Level User (Transportation Planner / Safety Analyst)

**Job**: Develop regional TIP safety projects, report to policy board, apply for federal safety funds, comply with PM1 targets.

**Questions they ask**:
- How do our member jurisdictions compare on crash rates?
- Are we meeting our PM1 safety performance targets?
- Where should our next safety study focus?
- What are the ped/bike hot spots in our urbanized area?
- Which intersections need signal warrant studies?

**What they need from Crash Lens**:
- Member jurisdiction table with crash counts, EPDO, ped/bike columns
- PM1 target tracking panel (5 federal safety measures)
- Top 10 intersections across all member jurisdictions
- Ped/Bike tab with urbanized area focus (already visible)
- Click from jurisdiction → full county-level view

---

## 5. Tab-by-Tab Behavior Specification

For each visible Explore tab, this section specifies exactly what changes at non-county tiers. **County tier behavior is unchanged** — all modifications are additive for State, Region, and MPO tiers.

### 5.1 Dashboard Tab

#### County (current — no changes)
Existing KPI cards, EPDO breakdown, trend charts, District Matrix. Works as-is.

#### State Tier

**Header**: "Virginia Statewide — {road type label}" instead of county name.

**KPI Row**: Same KPI cards (Total, Fatal, Serious Injury, EPDO, etc.) showing statewide totals. Same as current, just with bigger numbers.

**NEW: SHSP Target Panel** (insert below KPI row):
```
┌─────────────────────────────────────────────────────────┐
│  SHSP Target Tracking (Current Year vs Target)          │
│                                                         │
│  Fatalities:  ████████░░  732 / 800 target (8.5% below) │
│  Serious Inj: ██████████  4,201 / 3,800 target (OVER)  │
│  Fat Rate:    ███████░░░  1.12 / 1.20 target (on track) │
│  Inj Rate:    █████████░  2.83 / 2.50 target (OVER)    │
│                                                         │
│  ● On Track  ● At Risk  ● Exceeds Target               │
└─────────────────────────────────────────────────────────┘
```
Data source: SHSP targets can be configured in `config.json` or a supplemental targets file. Actual values come from `crashState.aggregates` filtered to latest year.

**NEW: District Comparison Heatmap** (replace the county-specific District Matrix):
```
┌──────────────────────────────────────────────────────────┐
│  District Comparison                                      │
│                                                          │
│  District     | Total  | K+A  | EPDO    | Trend | Action│
│  ─────────────┼────────┼──────┼─────────┼───────┼───────│
│  NOVA         | 12,403 |  289 | 145,200 |  ↑ 3% | [→]  │
│  Richmond     | 10,821 |  312 | 162,100 |  ↓ 2% | [→]  │
│  Hampton Rds  |  9,544 |  276 | 138,400 |  ↑ 1% | [→]  │
│  Salem        |  5,672 |  198 |  96,300 |  ─ 0% | [→]  │
│  Fredericksbg |  4,210 |  134 |  72,800 |  ↑ 5% | [→]  │
│  ...          |        |      |         |       |       │
│                                                          │
│  [→] = Click to drill into district detail view          │
│  Color: severity-weighted — darker = worse               │
└──────────────────────────────────────────────────────────┘
```
Data source: `crashState.aggregates.byRoute` grouped by district membership from `hierarchy.json`. Or, preferably, a new `aggregates.json` field `byDistrict` pre-computed in the data pipeline.

**Trend Charts**: Same charts as county, but showing statewide totals. Optionally add a small sparkline per district.

**Hide**: District Matrix widget (magisterial districts). Not meaningful at state level.

#### Region Tier

**Header**: "{District Name} District — {road type label}"

**KPI Row**: Same KPI cards showing district totals.

**NEW: County Comparison Matrix** (replace District Matrix):
```
┌──────────────────────────────────────────────────────────┐
│  County Comparison — Hampton Roads District               │
│                                                          │
│  County          | Total | K+A | EPDO   | Ped | Bike |→ │
│  ────────────────┼───────┼─────┼────────┼─────┼──────┼── │
│  Virginia Beach  | 3,201 |  78 | 42,100 |  45 |   12 |→ │
│  Norfolk         | 2,987 |  92 | 48,200 |  67 |   23 |→ │
│  Newport News    | 1,844 |  56 | 31,400 |  34 |    8 |→ │
│  Chesapeake      | 1,512 |  41 | 24,800 |  22 |    5 |→ │
│  Hampton         | 1,233 |  38 | 22,100 |  28 |    7 |→ │
│  ...             |       |     |        |     |      |   │
│                                                          │
│  [→] = Drill down to county view                         │
│  Sort by any column. Highlight rows > district average.  │
└──────────────────────────────────────────────────────────┘
```
Data source: `crashState.aggregates.byCounty` (new field needed — see Section 8) or computed from `sampleRows` grouped by county FIPS.

**Trend Charts**: District total trend with option to overlay individual county lines.

**Hide**: District Matrix widget.

#### MPO Tier

**Header**: "{MPO Name} — {road type label}"

**KPI Row**: Same KPI cards showing MPO-wide totals.

**NEW: PM1 Target Panel** (insert below KPI row):
```
┌─────────────────────────────────────────────────────────┐
│  Federal PM1 Safety Performance Measures                 │
│                                                         │
│  1. # Fatalities:              ███████░░  target: 800   │
│  2. Fatality Rate (per 100M VMT): █████░░  target: 1.20 │
│  3. # Serious Injuries:       █████████░  target: 3,200 │
│  4. Serious Injury Rate:      ██████░░░░  target: 2.50  │
│  5. # Non-motorized Fat+SI:   ████░░░░░░  target: 120   │
│                                                         │
│  ● Meeting Target  ● Not Meeting Target                 │
└─────────────────────────────────────────────────────────┘
```
Data source: PM1 targets configured per MPO (supplemental config). Actual values from filtered crash data.

**NEW: Member Jurisdiction Table** (replace District Matrix):
```
┌──────────────────────────────────────────────────────────┐
│  Member Jurisdictions — HRTPO                            │
│                                                          │
│  Jurisdiction    | Total | K+A | EPDO   | Ped | Bike |→ │
│  ────────────────┼───────┼─────┼────────┼─────┼──────┼── │
│  Virginia Beach  | 3,201 |  78 | 42,100 |  45 |   12 |→ │
│  Norfolk         | 2,987 |  92 | 48,200 |  67 |   23 |→ │
│  Newport News    | 1,844 |  56 | 31,400 |  34 |    8 |→ │
│  ...             |       |     |        |     |      |   │
│                                                          │
│  Includes Ped & Bike columns (MPO ped/bike focus)        │
│  [→] = Drill down to jurisdiction view                   │
└──────────────────────────────────────────────────────────┘
```

**Trend Charts**: MPO total trend with jurisdiction overlay option.

**Hide**: District Matrix widget.

### 5.2 Map Tab

#### County (no changes)
Current marker-based rendering. Works fine for county-level data volumes.

#### State Tier
- **Default view**: Choropleth map — county polygons colored by crash density or EPDO per capita
- **Click county polygon** → zooms in + shows popup with county summary + "Drill Down" button
- **Disable individual crash markers** at state level (too many — 100K+ points would freeze browser)
- Heatmap layer option as alternative to choropleth
- County boundary GeoJSON from TIGERweb Census

#### Region Tier
- **County polygons within district** colored by crash density
- **Crash markers visible** if total count is manageable (<15K points); else cluster markers or heatmap
- Click county → popup + drill-down option
- Roads outside district boundary slightly dimmed

#### MPO Tier
- **Crash markers** with cluster grouping (MPOs are smaller, usually <10K crashes — markers work)
- **Member jurisdiction outlines** visible on map
- Click jurisdiction area → highlight + popup
- Ped/Bike toggle overlay for MPO focus

### 5.3 Hot Spots Tab

#### County (no changes)
Ranks routes within a single jurisdiction.

#### State / Region / MPO
- Rank routes **across all member jurisdictions**
- Add **"County"** column to Hot Spots table showing which jurisdiction each route belongs to
- Allow **filtering by member county** (dropdown or checkbox filter)
- For state tier: group by district first, then show top routes per district
- Route clicking still works — opens the route detail in map

### 5.4 Safety Focus Tab

#### County (no changes)
Existing crash category analysis.

#### State / Region / MPO
- Same crash category cards (rear-end, angle, run-off-road, etc.)
- Add **county breakdown bar** within each category card showing which counties contribute most
- Example: "Rear-End crashes: 4,201 total — Virginia Beach (890), Norfolk (756), Newport News (521), ..."
- Click county name → drill to that county's Safety Focus for that category

### 5.5 Intersections Tab

#### County (no changes)
Ranks intersections by crash count/severity.

#### State / Region / MPO
- Rank intersections **across all member jurisdictions**
- Add **"Jurisdiction"** column to intersection table
- Top N intersections across the whole scope (state: top 50, region: top 30, MPO: top 20)
- Filter by member jurisdiction dropdown
- For state tier: option to show "Top 5 per district" view

### 5.6 Analysis Tab

#### County (no changes)
Charts showing severity distribution, collision types, weather, light, etc.

#### State / Region / MPO
- Same chart types, using tier-level aggregated data
- **Add stacked bar option**: break down each chart bar by member county
  - Example: Severity Distribution stacked bar where each segment = county contribution
- Add "Compare Counties" toggle that shows side-by-side small multiples per county
- Y-axis labels should show percentages as well as counts for cross-county comparison

### 5.7 Crash Tree Tab

Visible for: State ✅, Region ✅, County ✅ (hidden for MPO per visibility matrix).

#### State / Region
- Works the same as county — the Crash Tree logic processes whatever `crashState.sampleRows` contains
- No special tier adaptation needed beyond data scope

### 5.8 Fatal & Speeding Tab

Visible for: State ✅, Region ✅, County ✅ (hidden for MPO per visibility matrix).

#### State / Region
- Same analysis as county but on larger dataset
- Consider adding county column to fatal crash listing
- Speed analysis applies across all member roads

### 5.9 Ped/Bike Tab

Visible for: Region ✅, MPO ✅, County ✅ (hidden for State per visibility matrix).

#### Region / MPO
- Same analysis as county
- Add jurisdiction column to ped/bike crash listing
- MPO users especially need this — ped/bike safety is a core MPO function
- Consider adding "Urbanized Area" filter for MPO tier

### 5.10 Crash Prediction Tab

Visible for: State ✅, Region ✅, MPO ✅, County ✅.

#### All Tiers
- Prediction models can run on whatever scope is loaded
- At state tier: may need to use pre-computed predictions due to data volume
- Add jurisdiction context to prediction results

### 5.11 Deep Dive Tab

Visible for: County ✅ only. Hidden at all higher tiers. No changes needed.

---

## 6. County Comparison Module (Cross-Cutting Feature)

This is the single most important new feature for non-county tiers. It should be accessible from the Dashboard but also reusable from other tabs.

### 6.1 Core Comparison Table

A sortable, filterable table showing all member jurisdictions:

| Column | Description |
|--------|------------|
| Jurisdiction | County/city name |
| FIPS | County FIPS code |
| Total Crashes | Raw count |
| Fatal (K) | Fatal crash count |
| Serious Injury (A) | A-severity count |
| K+A | Combined fatal + serious |
| K+A % | K+A as percentage of total |
| EPDO | Equivalent PDO score |
| Ped Crashes | Pedestrian involved |
| Bike Crashes | Bicycle involved |
| YoY Trend | Year-over-year change (↑/↓/─) |
| Rank | Rank within scope (by selected sort column) |

### 6.2 Comparison Sparklines

Each row includes a small sparkline showing 5-year trend for the selected metric, allowing quick visual identification of improving vs worsening jurisdictions.

### 6.3 Comparison Heatmap View

Alternative to table: grid where rows = jurisdictions, columns = crash categories (rear-end, angle, ped, bike, run-off-road, etc.), cell color = severity-weighted count. Allows quick pattern identification across jurisdictions.

### 6.4 Outlier Highlighting

Jurisdictions exceeding the group average by >1.5 standard deviations on key metrics (K+A rate, EPDO per capita) are automatically highlighted. Helps users quickly identify where to focus attention.

---

## 7. Drill-Down Navigation

### 7.1 Breadcrumb Pattern

When a user drills from a higher tier to a lower one, show a breadcrumb trail:

```
Virginia (State) > Hampton Roads District > Norfolk (County)
```

Each segment is clickable to return to that tier level.

### 7.2 Drill-Down Triggers

- **Dashboard county table row** → click [→] button → switches to county tier for that jurisdiction
- **Map county polygon** → click → popup with "View County Detail" link
- **Hot Spots route** → already goes to map; county context preserved
- **Intersections row** → drill to county + zoom to intersection

### 7.3 State Machine

```
State ──┬── [click district row] ──→ Region (auto-selects that district)
        └── [click county row]   ──→ County (direct jump)

Region ──── [click county row]   ──→ County (auto-selects that county)

MPO    ──── [click jurisdiction] ──→ County (auto-selects that jurisdiction)
```

Returning up: use breadcrumb or back button. Data is reloaded for the target tier.

---

## 8. Data Pipeline Requirements

### 8.1 Aggregate JSON Enhancement

Currently, `aggregates.json` per county provides pre-computed stats. For higher tiers, we need:

**State aggregate** (`virginia/_state/aggregates.json`):
```json
{
  "total": 120000,
  "severity": { "K": 800, "A": 4200, "B": 12000, "C": 28000, "O": 75000 },
  "byYear": { "2019": {}, "2020": {} },
  "byDistrict": {
    "nova": { "total": 12403, "severity": {}, "counties": [] },
    "richmond": { "total": 10821, "severity": {}, "counties": [] }
  },
  "byCounty": {
    "51001": { "name": "Accomack", "total": 450, "severity": {} },
    "51003": { "name": "Albemarle", "total": 1200, "severity": {} }
  }
}
```

**Region aggregate** (`virginia/_region/{id}/aggregates.json`):
```json
{
  "total": 9544,
  "severity": {},
  "byYear": {},
  "byCounty": {
    "51710": { "name": "Norfolk", "total": 2987, "severity": {}, "ped": 67, "bike": 23 },
    "51810": { "name": "Virginia Beach", "total": 3201, "severity": {}, "ped": 45, "bike": 12 }
  }
}
```

**MPO aggregate** (`virginia/_mpo/{id}/aggregates.json`):
Same structure as region aggregate, with `byCounty` breakdown.

### 8.2 Why Pre-Computed Aggregates Matter

At state tier, the full CSV can be 100K+ rows. Loading and parsing this just to show Dashboard KPIs is wasteful. Pre-computed aggregates allow:
- **Instant Dashboard rendering** — no CSV parse needed
- **County comparison table** — populated from `byCounty` in aggregate JSON
- **Trend charts** — from `byYear` in aggregate JSON
- Full CSV is only loaded when user navigates to Map tab (needs point data) or other tabs requiring row-level data

### 8.3 Lazy CSV Loading

For non-county tiers, implement a two-phase loading strategy:
1. **Phase 1 (immediate)**: Load `aggregates.json` → render Dashboard, KPIs, comparison tables
2. **Phase 2 (on demand)**: Load full CSV only when user clicks into Map, Hot Spots, or other tabs requiring individual crash records

This prevents a 30-second wait on a 100K-row CSV just to show a dashboard.

---

## 9. Updated Tab Visibility Matrix

No changes proposed to the existing `TIER_TAB_VISIBILITY`. The current matrix is well-considered:
- State hides Ped/Bike and Deep Dive (too detailed for statewide)
- MPO hides Crash Tree and Fatal & Speeding (less relevant for urbanized planning)
- Region has the most tabs visible (district engineers need broad analysis)
- County has everything

---

## 10. Implementation Phases

### Phase 1: Dashboard Tier Adaptation (Highest Priority)
**Effort**: ~3-4 days
- Make `updateDashboard()` tier-aware
- Hide District Matrix at non-county tiers
- Show County Comparison Table at State/Region/MPO tiers
- Update dashboard header to show scope name
- Add `byCounty` field to tier aggregate JSONs (data pipeline)

### Phase 2: Drill-Down Navigation
**Effort**: ~2-3 days
- Implement breadcrumb component
- Wire county comparison table row clicks → tier switch to county
- Implement back navigation (breadcrumb click)
- Preserve tier history for back/forward

### Phase 3: Map Tier Adaptation
**Effort**: ~3-4 days
- Choropleth mode for state tier (county polygons colored by metric)
- Cluster markers for region/MPO tiers (when point count is high)
- Click-to-drill-down on county polygons
- Lazy CSV loading (Phase 2 load) when Map tab is activated

### Phase 4: SHSP & PM1 Target Panels
**Effort**: ~2 days
- SHSP target panel for state Dashboard
- PM1 target panel for MPO Dashboard
- Configuration for target values (supplemental config file or config.json)

### Phase 5: Other Tab Adaptations
**Effort**: ~3-4 days
- Hot Spots: add county column, cross-county ranking
- Safety Focus: add county breakdown bars
- Intersections: add jurisdiction column, cross-county ranking
- Analysis: add stacked bar county breakdown option

### Phase 6: Comparison Heatmap & Outlier Detection
**Effort**: ~2 days
- Comparison heatmap view (alternative to table)
- Outlier auto-highlighting
- Sparkline trend in comparison rows

---

## 11. Technical Implementation Notes

### 11.1 Dashboard Tier Switch Pattern

```javascript
function updateDashboard() {
    if (!crashState.loaded) return;
    const tier = jurisdictionContext.viewTier;

    // Common KPI rendering (works for all tiers)
    renderKPICards(getFilteredStats());

    // Tier-specific sections
    if (tier === 'county') {
        showDistrictMatrix();        // existing magisterial district grid
        hideCountyComparison();
        hideSHSPPanel();
        hidePM1Panel();
    } else {
        hideDistrictMatrix();        // not relevant at higher tiers
        showCountyComparison(tier);  // NEW: comparison table
        if (tier === 'state') showSHSPPanel();
        if (tier === 'mpo')   showPM1Panel();
    }

    // Charts (already work with whatever aggregates are loaded)
    renderTrendCharts();
    renderSeverityCharts();
}
```

### 11.2 County Comparison Data Source

```javascript
function getCountyComparisonData(tier) {
    const agg = crashState.aggregates;
    if (agg.byCounty) {
        // Pre-computed in aggregates.json — fast path
        return Object.entries(agg.byCounty).map(([fips, data]) => ({
            fips, name: data.name,
            total: data.total, severity: data.severity,
            ped: data.ped || 0, bike: data.bike || 0,
            epdo: calcEPDO(data.severity)
        }));
    }
    // Fallback: compute from sampleRows (slow for large datasets)
    return computeCountyBreakdownFromRows(crashState.sampleRows);
}
```

### 11.3 Lazy CSV Loading

```javascript
async function ensureCSVLoaded() {
    if (crashState.sampleRows.length > 0) return; // already loaded
    const filePath = getDataFilePath();
    await loadCSVChunked(filePath); // existing Papa.parse chunked loader
}

// Call from tabs that need individual crash records:
async function onMapTabActivated() {
    await ensureCSVLoaded();
    renderMapMarkers();
}
```

### 11.4 Key Functions to Modify

| Function | Change |
|----------|--------|
| `updateDashboard()` | Add tier branching, hide/show tier-specific panels |
| `onCrashDataReady()` | Support two-phase loading (aggregates first, CSV on demand) |
| `renderHotSpotsTable()` | Add county column, cross-county ranking |
| `renderSafetyFocusCards()` | Add county breakdown within each card |
| `renderIntersectionTable()` | Add jurisdiction column |
| `renderAnalysisCharts()` | Add stacked bar option by county |

### 11.5 New Components to Create

| Component | Purpose |
|-----------|---------|
| `CountyComparisonTable` | Sortable table of member jurisdictions |
| `SHSPTargetPanel` | State-level SHSP target progress bars |
| `PM1TargetPanel` | MPO-level PM1 target progress bars |
| `DrillDownBreadcrumb` | Navigation breadcrumb for tier traversal |
| `ChoroplethMapLayer` | County polygon choropleth for state/region map |
| `ComparisonHeatmap` | Grid heatmap view for cross-county analysis |

---

## 12. Code References

Key existing code locations for implementation:

| What | Location | Line |
|------|----------|------|
| `_TIER_EXTENSIONS` (state object) | `app/index.html` | ~20531 |
| `TIER_TAB_VISIBILITY` | `app/index.html` | ~20545 |
| `setViewTier()` | `app/index.html` | ~20555 |
| `updateTabVisibilityForTier()` | `app/index.html` | ~20564 |
| `handleTierChange()` | `app/index.html` | ~20654 |
| `loadStatewideCSVForTier()` | `app/index.html` | ~20790 |
| `handleRegionSelection()` | `app/index.html` | ~20888 |
| `handleMPOSelection()` | `app/index.html` | ~20941 |
| `AggregateLoader` | `app/index.html` | ~21929 |
| `getActiveRoadTypeSuffix()` | `app/index.html` | ~23295 |
| `updateRoadTypeLabels()` | `app/index.html` | ~23325 |
| `getDataFilePath()` | `app/index.html` | ~23362 |
| `updateDashboard()` | `app/index.html` | ~45854 |
| District Matrix widget (HTML) | `app/index.html` | ~5645 |
| Tier buttons (HTML) | `app/index.html` | ~4688 |
| Region dropdown (HTML) | `app/index.html` | ~4699 |
| MPO dropdown (HTML) | `app/index.html` | ~4705 |
| Road type radios (HTML) | `app/index.html` | ~4764 |
| Hierarchy data | `states/virginia/hierarchy.json` | — |

---

## 13. Effort Summary

| Phase | Description | Estimated Effort | Priority |
|-------|-------------|-----------------|----------|
| 1 | Dashboard Tier Adaptation + County Comparison | 3-4 days | Critical |
| 2 | Drill-Down Navigation + Breadcrumb | 2-3 days | Critical |
| 3 | Map Tier Adaptation + Choropleth | 3-4 days | High |
| 4 | SHSP & PM1 Target Panels | 2 days | High |
| 5 | Other Tab Adaptations | 3-4 days | Medium |
| 6 | Comparison Heatmap & Outlier Detection | 2 days | Medium |
| **Total** | | **15-19 days** | |

### Dependencies
- Phase 2 depends on Phase 1 (comparison table needs to exist for drill-down)
- Phase 3 partially independent (map work can start alongside Phase 1)
- Phase 4 independent (target panels are standalone widgets)
- Phase 5 depends on Phase 1 patterns being established
- Phase 6 depends on Phase 1 data structures

### Data Pipeline Prerequisite
- Add `byCounty` and `byDistrict` fields to state/region/MPO `aggregates.json`
- This can be done in the existing `download_crash_data.py` pipeline
- Should be started before or in parallel with Phase 1
