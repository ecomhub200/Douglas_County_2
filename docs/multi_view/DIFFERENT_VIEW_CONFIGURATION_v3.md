# Different View Configuration Plan

## Multi-Tier View Architecture: State, Region, MPO, County

**Date:** February 22, 2026
**Author:** Crash Lens Engineering
**Scope:** Explore section only (Dashboard, Map, Crash Tree, Safety Focus, Fatal & Speeding, Hot Spots, Intersections, Ped/Bike, Analysis, Deep Dive, Crash Prediction)
**Excluded:** Solutions section (CMF, Warrants, MUTCD AI, Domain Knowledge), Grants, Reports
**Status:** Planning

---

## Design Principles

1. **State-agnostic** — All view logic must work for any US state, not just Virginia. Each state defines its own regions, MPOs, and counties in `states/{state}/hierarchy.json`. The UI adapts to whatever hierarchy data is loaded.
2. **County view is untouched** — The existing county-level view works correctly and must not be modified.
3. **Map is already set up** — The Map tab already handles all tiers (boundary rendering, data loading, markers). No map changes are proposed in this plan.
4. **Data pipeline already produces per-tier CSVs** — The unified pipeline (`pipeline.yml`) generates region/MPO/state CSV files by concatenating member county rows. Road type splits are already configured per tier. No new data pipeline work is needed for CSV generation.
5. **Road type grouping** — State and Region tiers use DOT/Non-DOT/All Roads naming. MPO and County tiers use County Roads/No Interstate/All Roads naming. This is already implemented in `getActiveRoadTypeSuffix()` and `updateRoadTypeLabels()`.
6. **Users define their geography in the Upload tab** — State, regions, MPOs, and counties are configured per state via `hierarchy.json`. The app reads this at runtime and populates tier selectors dynamically.

---

## 1. What Already Exists (Built Infrastructure)

### 1.1 Tier Selector Buttons (UI)

Four tier buttons in the sidebar (~line 4688–4695):
```
[ State ] [ Region ] [ MPO ] [ County (active) ]
```
Buttons call `handleTierChange(tier)`. County is default active.

### 1.2 Region & MPO Dropdown Selectors (UI)

- Region dropdown (`tierRegionSelect`) → populated from `hierarchy.json` regions
- MPO dropdown (`tierMPOSelect`) → populated from `hierarchy.json` MPOs
- Dynamically shown/hidden based on active tier

### 1.3 Jurisdiction Locking for Solutions Scope

When switching to a higher tier, `jurisdictionContext.solutionsScopeCounty` preserves the county context so Solutions/Grants tabs still work at county level.

### 1.4 Road Type Filter Labels (Tier-Aware)

`updateRoadTypeLabels(tier)` (~line 23325) — already implemented:

| Radio | State / Region | MPO / County |
|-------|---------------|-------------|
| Radio 1 | **DOT Roads Only** | **County/City Roads Only** |
| Radio 2 | **Non-DOT Roads** | **All Roads (No Interstate)** |
| Radio 3 | **Statewide All Roads** / **All Roads** | **All Roads** |

### 1.5 Tier-Aware R2 Data Paths

`getDataFilePath()` (~line 23362) — already implemented:

| Tier | Path Pattern |
|------|-------------|
| State | `{r2Prefix}/_state/{roadType}.csv` |
| Region | `{r2Prefix}/_region/{regionId}/{roadType}.csv` |
| MPO | `{r2Prefix}/_mpo/{mpoId}/{roadType}.csv` |
| County | `{r2Prefix}/{jurisdiction}/{roadType}.csv` |

`getActiveRoadTypeSuffix(tier)` (~line 23295) — already maps radio values to file suffixes per tier:
- State/Region: `dot_roads`, `non_dot_roads`, `statewide_all_roads` / `all_roads`
- MPO/County: `county_roads`, `no_interstate`, `all_roads`

### 1.6 Data Loading per Tier

Three loader functions already exist:
- **`loadStatewideCSVForTier()`** — streams state CSV via Papa.parse
- **`handleRegionSelection()`** — loads region-scoped CSV + renders district boundary
- **`handleMPOSelection()`** — loads MPO-scoped CSV + 3-strategy BTS boundary lookup

All call `onCrashDataReady()` → `updateDashboard()`.

### 1.7 Map Tab (Fully Set Up — No Changes Needed)

- **State tier**: State outline from TIGERweb + map flies to state extent
- **Region tier**: District polygon from `hierarchy.json` + zooms to district
- **MPO tier**: BTS NTAD boundary lookup (3-strategy fallback)
- **County tier**: Standard jurisdiction boundary
- Boundaries properly cleaned up when switching tiers

### 1.8 Tab Visibility Matrix (Current — Will Be Updated)

`TIER_TAB_VISIBILITY` (~line 20545) — current values:

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

### 1.9 Scope Indicator

Scope indicator in sidebar shows current tier context. Updates via `updateScopeIndicator()`.

### 1.10 Hierarchy Data (State-Agnostic)

`states/{state}/hierarchy.json` defines per state:
- **Regions** (e.g., VDOT districts in Virginia, CDOT regions in Colorado) with county FIPS arrays
- **MPOs** with county FIPS, BTS acronyms, population
- **Key corridors** with county and region references

Loaded via `HierarchyRegistry.load(stateDir)`. The front-end reads whatever hierarchy is configured — no state-specific hardcoding.

### 1.11 Data Pipeline (Already Configured)

The unified pipeline (`pipeline.yml`, documented in `data-pipeline/Unified-Pipeline-Architecture.md`) already produces:

| Scope | Files Generated | R2 Location |
|-------|----------------|-------------|
| County | 3 road-type CSVs per county | `{state}/{county}/county_roads.csv`, `no_interstate.csv`, `all_roads.csv` |
| Region | 3 road-type CSVs per region (concat of member county rows) | `{state}/_region/{regionId}/dot_roads.csv`, `non_dot_roads.csv`, `all_roads.csv` |
| MPO | 3 road-type CSVs per MPO (concat of member county rows) | `{state}/_mpo/{mpoId}/county_roads.csv`, `no_interstate.csv`, `all_roads.csv` |
| Statewide | Statewide CSV + gzip | `{state}/_state/statewide_all_roads.csv`, `dot_roads.csv`, `non_dot_roads.csv` |
**Note:** The pipeline produces **CSV files only** (no JSON aggregates). The `aggregate_by_scope.py` script concatenates member county CSV rows into region/MPO CSVs — same Virginia-standard columns, just more rows. The front-end loads these CSVs via Papa.parse just like county CSVs and computes all statistics at runtime.

No new data pipeline work is required for the front-end view configuration.

---

## 2. What Needs to Change

### 2.1 Tab Visibility Matrix — Corrections

Per user requirements, three changes to `TIER_TAB_VISIBILITY`:

| Change | Current | New | Reason |
|--------|---------|-----|--------|
| **Ped/Bike at State** | ❌ (hidden) | ✅ (visible) | Statewide ped/bike analysis is valuable |
| **Crash Tree at MPO** | ❌ (hidden) | ✅ (visible) | MPO users need crash tree analysis |
| **Fatal & Speeding at MPO** | ❌ (hidden) | ✅ (visible) | MPO users need fatal/speeding analysis |

**Updated matrix:**

| Tab | State | Region | MPO | County |
|-----|-------|--------|-----|--------|
| Dashboard | ✅ | ✅ | ✅ | ✅ |
| Map | ✅ | ✅ | ✅ | ✅ |
| Crash Tree | ✅ | ✅ | ✅ | ✅ |
| Safety Focus | ✅ | ✅ | ✅ | ✅ |
| Fatal & Speeding | ✅ | ✅ | ✅ | ✅ |
| Hot Spots | ✅ | ✅ | ✅ | ✅ |
| Intersections | ✅ | ✅ | ✅ | ✅ |
| Ped/Bike | ✅ | ✅ | ✅ | ✅ |
| Analysis | ✅ | ✅ | ✅ | ✅ |
| Deep Dive | ❌ | ❌ | ❌ | ✅ |
| Crash Prediction | ✅ | ✅ | ✅ | ✅ |

Only Deep Dive remains county-only. All other Explore tabs are visible at all tiers.

### 2.2 Dashboard Tab — No Tier Adaptation

`updateDashboard()` (~line 45854) renders the same county-style KPIs regardless of tier. Missing:

- No **comparison matrices** for sub-geographies
- District Matrix widget (magisterial districts ~line 5645) is county-specific but shows at all tiers
- KPI header doesn't reflect scope name
- No drill-down capability from comparison rows

### 2.3 Other Explore Tabs — No County Column at Higher Tiers

Hot Spots, Safety Focus, Intersections, Analysis, Ped/Bike, Crash Tree, and Fatal & Speeding all work with whatever data is loaded, but at multi-county tiers they don't show:
- Which county each crash/route/intersection belongs to
- County-level breakdowns or comparisons
- Filtering by member county

### 2.4 No Drill-Down Navigation

No ability to click from a higher-tier comparison into a specific county's detail view.

---

## 3. State View — Comparison Matrices

When the user selects the **State** tier, the Dashboard should show three comparison matrices, each ranking the sub-geographies within that state.

### 3.1 Region Comparison Matrix

Shows all regions (e.g., VDOT districts in Virginia, CDOT regions in Colorado) ranked by crash metrics.

```
┌───────────────────────────────────────────────────────────────────┐
│  Region Comparison — {State Name} Statewide                       │
│                                                                   │
│  Region           | Total  | K+A  | EPDO    | Ped | Bike | Trend │
│  ─────────────────┼────────┼──────┼─────────┼─────┼──────┼───────│
│  {Region 1}       | 12,403 |  289 | 145,200 |  98 |   34 | ↑ 3% │
│  {Region 2}       | 10,821 |  312 | 162,100 | 112 |   28 | ↓ 2% │
│  {Region 3}       |  9,544 |  276 | 138,400 |  87 |   31 | ↑ 1% │
│  ...              |        |      |         |     |      |       │
│                                                                   │
│  ► Click row to drill into region detail view                     │
│  Color: severity-weighted — darker = worse                        │
└───────────────────────────────────────────────────────────────────┘
```

Data source: Computed at runtime by grouping loaded CSV `sampleRows` by region membership from `hierarchy.json`.

### 3.2 MPO Comparison Matrix

Shows all MPOs defined in the state's `hierarchy.json`.

```
┌───────────────────────────────────────────────────────────────────┐
│  MPO Comparison — {State Name} Statewide                          │
│                                                                   │
│  MPO              | Total  | K+A  | EPDO    | Ped | Bike | Trend │
│  ─────────────────┼────────┼──────┼─────────┼─────┼──────┼───────│
│  {MPO 1}          |  8,231 |  170 |  98,400 | 145 |   67 | ↑ 2% │
│  {MPO 2}          |  6,544 |  134 |  76,200 |  89 |   45 | ↓ 1% │
│  ...              |        |      |         |     |      |       │
│                                                                   │
│  ► Click row to drill into MPO detail view                        │
└───────────────────────────────────────────────────────────────────┘
```

### 3.3 County Comparison Matrix

Shows all counties/jurisdictions in the state, sorted by selected metric.

```
┌───────────────────────────────────────────────────────────────────┐
│  County Comparison — {State Name} Statewide                       │
│                                                                   │
│  County           | Total  | K+A  | EPDO   | Ped | Bike | Region │
│  ─────────────────┼────────┼──────┼────────┼─────┼──────┼────────│
│  {County 1}       |  3,201 |   78 | 42,100 |  45 |   12 | {Rgn} │
│  {County 2}       |  2,987 |   92 | 48,200 |  67 |   23 | {Rgn} │
│  ...              |        |      |        |     |      |        │
│                                                                   │
│  ► Click row to drill into county detail view                     │
│  Sort by any column. Top 20 shown, expandable to full list.       │
└───────────────────────────────────────────────────────────────────┘
```

### 3.4 Layout

All three matrices stack vertically on the Dashboard below the KPI cards. The existing District Matrix widget (magisterial districts) is **hidden** at state tier since it's county-specific.

**Header**: "{State Name} — Statewide — {road type label}" instead of county name.

---

## 4. Region View — County Comparison

When the user selects the **Region** tier and picks a specific region from the dropdown, the Dashboard shows a county comparison matrix for that region's member counties.

### 4.1 County Comparison Matrix (Region Scope)

```
┌───────────────────────────────────────────────────────────────────┐
│  County Comparison — {Region Name}                                │
│                                                                   │
│  County           | Total | K+A | EPDO   | Ped | Bike | Trend |→ │
│  ─────────────────┼───────┼─────┼────────┼─────┼──────┼───────┼── │
│  {County 1}       | 3,201 |  78 | 42,100 |  45 |   12 | ↑ 3% |→ │
│  {County 2}       | 2,987 |  92 | 48,200 |  67 |   23 | ↓ 2% |→ │
│  {County 3}       | 1,844 |  56 | 31,400 |  34 |    8 | ↑ 1% |→ │
│  ...              |       |     |        |     |      |       |   │
│                                                                   │
│  [→] = Drill down to county view                                  │
│  Sort by any column. Highlight rows > regional average.           │
└───────────────────────────────────────────────────────────────────┘
```

Data source: Compute from loaded region CSV by grouping rows on `Physical Juris Name` column (county column in standardized CSV format).

### 4.2 Layout

- **Header**: "{Region Name} — {road type label}"
- **KPI Row**: Same KPI cards showing region totals
- **County Comparison Matrix**: Replaces the District Matrix widget
- **Trend Charts**: Region totals with option to overlay individual county lines
- District Matrix widget: **hidden** (not relevant for region tier)

---

## 5. MPO View — County Comparison

When the user selects the **MPO** tier and picks a specific MPO from the dropdown, the Dashboard shows a member jurisdiction comparison.

### 5.1 Member Jurisdiction Table (MPO Scope)

```
┌───────────────────────────────────────────────────────────────────┐
│  Member Jurisdictions — {MPO Name}                                │
│                                                                   │
│  Jurisdiction     | Total | K+A | EPDO   | Ped | Bike | Trend |→ │
│  ─────────────────┼───────┼─────┼────────┼─────┼──────┼───────┼── │
│  {Jurisdiction 1} | 3,201 |  78 | 42,100 |  45 |   12 | ↑ 2% |→ │
│  {Jurisdiction 2} | 2,987 |  92 | 48,200 |  67 |   23 | ↓ 1% |→ │
│  ...              |       |     |        |     |      |       |   │
│                                                                   │
│  Ped & Bike columns prominent (core MPO function)                 │
│  [→] = Drill down to jurisdiction view                            │
└───────────────────────────────────────────────────────────────────┘
```

### 5.2 Layout

- **Header**: "{MPO Name} — {road type label}"
- **KPI Row**: Same KPI cards showing MPO-wide totals
- **Member Jurisdiction Table**: Replaces District Matrix widget
- District Matrix widget: **hidden**

---

## 6. County View — No Changes

The existing county-level view remains exactly as-is. No modifications to Dashboard layout, KPI cards, District Matrix, charts, or any other county-tier behavior.

---

## 7. State-Agnostic Design

### 7.1 No Hardcoded State References

All view configuration must be driven by `hierarchy.json` data, not state-specific code:

```javascript
// ✅ CORRECT — reads from hierarchy dynamically
const hierarchy = HierarchyRegistry.get(stateKey);
const regions = hierarchy?.regions || [];
const mpos = hierarchy?.mpos || [];

// ❌ WRONG — hardcoded Virginia references
const districts = ['Bristol', 'Salem', 'Lynchburg', ...];
```

### 7.2 Hierarchy-Driven Comparison Tables

The comparison matrices read their data from `hierarchy.json`:

| State | Regions | MPOs | County Count |
|-------|---------|------|-------------|
| Virginia | 9 VDOT Construction Districts | 8 MPOs | 133 |
| Colorado | 5 CDOT Regions | 3 MPOs | 64 |
| Maryland | — | — | 24 |

If a state has no regions defined in `hierarchy.json`, the Region Comparison Matrix is simply empty/hidden at state tier. If a state has no MPOs, the MPO Comparison Matrix is hidden. The code must gracefully handle states with varying levels of hierarchy completeness.

### 7.3 Label Flexibility

Region names vary by state. The UI should use the `hierarchy.json` label field:

| State | What They Call "Regions" |
|-------|------------------------|
| Virginia | Construction Districts |
| Colorado | CDOT Regions |
| Texas | TxDOT Districts |
| California | Caltrans Districts |

The matrix header should say "{Region Label} Comparison" using whatever the state calls its regions, not hardcode "District Comparison."

### 7.4 Road Type Configuration Already State-Agnostic

Road type labels and file suffixes are driven by `states/{state}/config.json` → `roadSystems.filterProfiles`. The front-end code in `getActiveRoadTypeSuffix()` and `updateRoadTypeLabels()` already handles this generically — no changes needed.

---

## 8. Tab-by-Tab Behavior Specification

For each Explore tab, this section specifies what changes at non-county tiers. **County tier behavior is untouched.**

### 8.1 Dashboard Tab

See Sections 3, 4, 5, and 6 above for detailed dashboard behavior per tier.

Summary:
- **State**: KPIs + Region Comparison + MPO Comparison + County Comparison (all three matrices)
- **Region**: KPIs + County Comparison Matrix for member counties
- **MPO**: KPIs + Member Jurisdiction Table
- **County**: No changes (existing behavior)

All tiers: Hide District Matrix widget at non-county tiers. Show KPI header with scope name.

### 8.2 Map Tab — No Changes

The Map tab is already fully set up for all tiers (boundary rendering, data loading, marker display). No modifications needed.

### 8.3 Hot Spots Tab

#### County (no changes)

#### State / Region / MPO
- Rank routes **across all member jurisdictions**
- Add **"County"** column to Hot Spots table showing which jurisdiction each route belongs to
- Allow **filtering by member county** (dropdown filter)
- For state tier: option to show "Top N per region" grouping

### 8.4 Safety Focus Tab

#### County (no changes)

#### State / Region / MPO
- Same crash category cards (rear-end, angle, run-off-road, etc.)
- Add **county breakdown bar** within each category card showing which counties contribute most
- Click county name → drill to that county's Safety Focus for that category

### 8.5 Intersections Tab

#### County (no changes)

#### State / Region / MPO
- Rank intersections **across all member jurisdictions**
- Add **"Jurisdiction"** column to intersection table
- Filter by member jurisdiction dropdown

### 8.6 Analysis Tab

#### County (no changes)

#### State / Region / MPO
- Same chart types with tier-level data
- Add **stacked bar option** breaking down each chart bar by member county
- Add "Compare Counties" toggle for side-by-side small multiples

### 8.7 Crash Tree Tab

Now visible at all tiers (including MPO — changed from previous matrix).

#### State / Region / MPO
- Same Crash Tree logic — processes whatever `crashState.sampleRows` contains
- No special tier adaptation needed; the tree works on the loaded data set

### 8.8 Fatal & Speeding Tab

Now visible at all tiers (including MPO — changed from previous matrix).

#### State / Region / MPO
- Same analysis as county, on the loaded multi-county dataset
- Add county column to fatal crash listing at higher tiers
- Speed analysis applies across all member roads

### 8.9 Ped/Bike Tab

Now visible at all tiers (including State — changed from previous matrix).

#### State / Region / MPO
- Same analysis as county
- Add jurisdiction column to ped/bike crash listing
- MPO users especially need this — ped/bike safety is a core MPO function

### 8.10 Crash Prediction Tab

#### All Tiers
- Prediction models run on whatever scope is loaded
- At state tier: may need pre-computed predictions due to data volume
- Add jurisdiction context to prediction results

### 8.11 Deep Dive Tab

Visible for **County only**. Hidden at all higher tiers. No changes needed.

---

## 9. Drill-Down Navigation

### 9.1 Breadcrumb Pattern

When a user drills from a higher tier to a lower one, show a breadcrumb trail:

```
{State Name} (State) > {Region Name} > {County Name} (County)
```

Each segment is clickable to return to that tier level.

### 9.2 Drill-Down Triggers

- **Dashboard comparison table row** → click [→] → switches to target tier for that geography
- **Hot Spots route** → preserves county context
- **Intersections row** → drill to county + zoom to intersection

### 9.3 State Machine

```
State ──┬── [click region row] ───→ Region (auto-selects that region in dropdown)
        ├── [click MPO row]    ───→ MPO (auto-selects that MPO in dropdown)
        └── [click county row] ───→ County (direct jump)

Region ──── [click county row] ───→ County (auto-selects that county)

MPO    ──── [click jurisdiction] ──→ County (auto-selects that jurisdiction)
```

Returning up: breadcrumb click or back button. Data reloads for target tier.

---

## 10. Data Source Strategy — CSV Only

### 10.1 No New Data Pipeline Work

The unified pipeline (`pipeline.yml`) already generates all needed CSV files per tier. The pipeline uses **CSV only — no JSON aggregate files**. The `aggregate_by_scope.py` script concatenates member county CSV rows into region/MPO/state CSVs with the same Virginia-standard columns.

R2 bucket structure (CSV files only):

```
crash-lens-data/
  {state}/
    _state/dot_roads.csv | non_dot_roads.csv | statewide_all_roads.csv
    _region/{regionId}/dot_roads.csv | non_dot_roads.csv | all_roads.csv
    _mpo/{mpoId}/county_roads.csv | no_interstate.csv | all_roads.csv
    {county}/county_roads.csv | no_interstate.csv | all_roads.csv
```

Road type file naming per tier (confirmed from `pipeline.yml` Stage 5 + `getActiveRoadTypeSuffix()`):
- **State / Region**: `dot_roads.csv`, `non_dot_roads.csv`, `statewide_all_roads.csv` (or `all_roads.csv` for region)
- **MPO / County**: `county_roads.csv`, `no_interstate.csv`, `all_roads.csv`

### 10.2 How the Front-End Gets Data

The existing data loading functions (`loadStatewideCSVForTier()`, `handleRegionSelection()`, `handleMPOSelection()`) stream the tier-appropriate CSV via Papa.parse chunked loading and store rows in `crashState.sampleRows`. The same parsing and aggregation logic that works for county CSVs works identically for region/MPO/state CSVs because they have the exact same column structure.

### 10.3 Comparison Data from Loaded CSV

When a multi-county CSV is loaded (state, region, or MPO), the comparison matrices are computed at runtime by grouping `crashState.sampleRows` on the `Physical Juris Name` column (column index `COL.JURISDICTION`):

```javascript
function buildComparisonFromLoadedData() {
    const byJurisdiction = {};
    crashState.sampleRows.forEach(row => {
        const juris = row[COL.JURISDICTION];
        if (!byJurisdiction[juris]) {
            byJurisdiction[juris] = { total: 0, K: 0, A: 0, B: 0, C: 0, O: 0, ped: 0, bike: 0 };
        }
        byJurisdiction[juris].total++;
        byJurisdiction[juris][row[COL.SEVERITY]]++;
        if (row[COL.PED] === 'Yes') byJurisdiction[juris].ped++;
        if (row[COL.BIKE] === 'Yes') byJurisdiction[juris].bike++;
    });
    return byJurisdiction;
}
```

This is the **only data source** for comparison tables — no JSON aggregates, no separate API calls. The CSV is already loaded by the existing tier handlers; the comparison just adds a grouping step.

### 10.4 Performance Consideration for State Tier

State-level CSVs can have 100K+ rows. Since the pipeline produces CSV only (no pre-computed JSON summaries), the front-end must handle this volume:

- **Papa.parse chunked streaming** is already used by `loadStatewideCSVForTier()` — this works well
- The `buildComparisonFromLoadedData()` grouping is O(n) — a single pass over `sampleRows` — which should complete in <1 second even for 100K+ rows
- The `onCrashDataReady()` callback already computes `crashState.aggregates` from `sampleRows` — the comparison table adds minimal overhead on top of this
- If performance becomes an issue, a web worker could be used for the grouping step, but this is unlikely to be needed

### 10.5 Note on Existing AggregateLoader

The front-end has an `AggregateLoader` class (~line 21929) that fetches `aggregates.json` from R2. This loader is a **legacy component** — the current pipeline does not generate these JSON files. The comparison tables and dashboard rendering should use `crashState.sampleRows` and `crashState.aggregates` (computed from CSV) as the data source, not `AggregateLoader`.

---

## 11. Technical Implementation Notes

### 11.1 Dashboard Tier Switch Pattern

```javascript
function updateDashboard() {
    if (!crashState.loaded) return;
    const tier = jurisdictionContext.viewTier;

    // Update header with scope name
    updateDashboardHeader(tier);

    // Common KPI rendering (works for all tiers — just different data volume)
    renderKPICards(getFilteredStats());

    // Tier-specific comparison sections
    if (tier === 'county') {
        showDistrictMatrix();           // existing magisterial district grid
        hideComparisonMatrices();
    } else if (tier === 'state') {
        hideDistrictMatrix();
        showRegionComparison();         // NEW
        showMPOComparison();            // NEW
        showCountyComparison('state');  // NEW
    } else if (tier === 'region') {
        hideDistrictMatrix();
        showCountyComparison('region'); // NEW — member counties only
    } else if (tier === 'mpo') {
        hideDistrictMatrix();
        showCountyComparison('mpo');    // NEW — member jurisdictions only
    }

    // Charts (work with whatever aggregates are loaded)
    renderTrendCharts();
    renderSeverityCharts();
}
```

### 11.2 Tab Visibility Update

```javascript
const TIER_TAB_VISIBILITY = {
    state:    { dashboard:1, map:1, crashTree:1, safetyFocus:1, fatalSpeed:1, hotSpots:1, intersections:1, pedBike:1, analysis:1, deepDive:0, crashPrediction:1 },
    region:   { dashboard:1, map:1, crashTree:1, safetyFocus:1, fatalSpeed:1, hotSpots:1, intersections:1, pedBike:1, analysis:1, deepDive:0, crashPrediction:1 },
    mpo:      { dashboard:1, map:1, crashTree:1, safetyFocus:1, fatalSpeed:1, hotSpots:1, intersections:1, pedBike:1, analysis:1, deepDive:0, crashPrediction:1 },
    county:   { dashboard:1, map:1, crashTree:1, safetyFocus:1, fatalSpeed:1, hotSpots:1, intersections:1, pedBike:1, analysis:1, deepDive:1, crashPrediction:1 },
};
```

### 11.3 State-Agnostic Comparison Builder

```javascript
function buildComparisonTable(tier, containerId) {
    const hierarchy = HierarchyRegistry.get(_getActiveStateKey());
    if (!hierarchy) return;

    let items = [];
    if (tier === 'state') {
        // For region comparison: iterate hierarchy.regions
        // For MPO comparison: iterate hierarchy.mpos
        // For county comparison: iterate all counties
    } else if (tier === 'region') {
        // Find selected region in hierarchy, get its member counties
        const regionId = jurisdictionContext.tierRegion?.id;
        const region = hierarchy.regions?.find(r => r.id === regionId);
        items = region?.counties || [];
    } else if (tier === 'mpo') {
        // Find selected MPO in hierarchy, get its member counties
        const mpoId = jurisdictionContext.tierMpo?.id;
        const mpo = hierarchy.mpos?.find(m => m.id === mpoId);
        items = mpo?.counties || [];
    }

    // Render sortable table with items
    renderSortableComparisonTable(containerId, items, getComparisonData());
}
```

### 11.4 Key Functions to Modify

| Function | Change |
|----------|--------|
| `TIER_TAB_VISIBILITY` | Enable pedBike for state, crashTree+fatalSpeed for MPO |
| `updateDashboard()` | Add tier branching, show/hide comparison matrices |
| `renderHotSpotsTable()` | Add county column at higher tiers |
| `renderSafetyFocusCards()` | Add county breakdown within each card |
| `renderIntersectionTable()` | Add jurisdiction column at higher tiers |
| `renderAnalysisCharts()` | Add stacked bar option by county |
| `renderCrashTree()` | No change (works with loaded data) |
| `renderFatalSpeedTab()` | Add county column at higher tiers |
| `renderPedBikeTab()` | Add county column at higher tiers |

### 11.5 New Components to Create

| Component | Purpose |
|-----------|---------|
| `RegionComparisonMatrix` | State-tier: sortable table of regions |
| `MPOComparisonMatrix` | State-tier: sortable table of MPOs |
| `CountyComparisonTable` | All higher tiers: sortable table of member counties |
| `DrillDownBreadcrumb` | Navigation breadcrumb for tier traversal |
| `ComparisonHeatmap` | Optional: grid heatmap for cross-county analysis |

---

## 12. Code References

| What | Location | Line |
|------|----------|------|
| `_TIER_EXTENSIONS` | `app/index.html` | ~20531 |
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
| District Matrix (HTML) | `app/index.html` | ~5645 |
| Tier buttons (HTML) | `app/index.html` | ~4688 |
| Region dropdown (HTML) | `app/index.html` | ~4699 |
| MPO dropdown (HTML) | `app/index.html` | ~4705 |
| Road type radios (HTML) | `app/index.html` | ~4764 |
| Pipeline architecture | `data-pipeline/Unified-Pipeline-Architecture.md` | — |
| R2 connection guide | `data-pipeline/Data Pipeline - R2 to Front-End Connection.docx` | — |
| State onboarding | `data-pipeline/Onboarding-New-State.md` | — |

---

## 13. Implementation Phases

### Phase 1: Tab Visibility Fix + Dashboard Tier Adaptation (Critical)
**Effort**: ~4-5 days
- Update `TIER_TAB_VISIBILITY` (3 line changes)
- Make `updateDashboard()` tier-aware
- Hide District Matrix at non-county tiers
- Build `CountyComparisonTable` component (used by all higher tiers)
- Build `RegionComparisonMatrix` component (state tier)
- Build `MPOComparisonMatrix` component (state tier)
- Update dashboard header to show scope name
- State-agnostic: read hierarchy.json, no hardcoded state references

### Phase 2: Drill-Down Navigation
**Effort**: ~2-3 days
- Build `DrillDownBreadcrumb` component
- Wire comparison table row clicks → tier switch
- Implement back navigation via breadcrumb
- Preserve tier history for navigation

### Phase 3: Other Tab Adaptations (County Column + Filtering)
**Effort**: ~4-5 days
- Hot Spots: add county column, cross-county ranking, county filter
- Safety Focus: add county breakdown bars in category cards
- Intersections: add jurisdiction column, county filter
- Analysis: add stacked bar county breakdown option
- Fatal & Speeding: add county column at higher tiers
- Ped/Bike: add county column at higher tiers

### Phase 4: Performance Optimization
**Effort**: ~2-3 days
- Ensure state-tier (100K+ rows) doesn't freeze browser during CSV parsing
- Consider web worker for comparison table computation on large datasets
- Add loading indicators for large dataset operations
- Profile `buildComparisonFromLoadedData()` at scale

### Phase 5: Comparison Heatmap + Sparklines
**Effort**: ~2 days
- Optional heatmap view for cross-county analysis
- Sparkline trends in comparison table rows
- Outlier auto-highlighting (>1.5 SD from mean)

---

## 14. Effort Summary

| Phase | Description | Effort | Priority |
|-------|-------------|--------|----------|
| 1 | Tab Visibility + Dashboard Comparison Matrices | 4-5 days | Critical |
| 2 | Drill-Down Navigation | 2-3 days | Critical |
| 3 | Other Tab Adaptations (county column + filters) | 4-5 days | High |
| 4 | Performance Optimization | 2-3 days | High |
| 5 | Heatmap + Sparklines + Outlier Detection | 2 days | Medium |
| **Total** | | **14-18 days** | |

### Dependencies
- Phase 2 depends on Phase 1 (comparison tables must exist for drill-down)
- Phase 3 is partially independent (can start alongside Phase 2)
- Phase 4 should come before Phase 3 if state-tier CSV volumes cause browser performance issues
- Phase 5 depends on Phase 1 data structures

### No Data Pipeline Work Required
The unified pipeline already generates all tier-level CSVs. Road type splits are already configured. No changes to `pipeline.yml`, `aggregate_by_scope.py`, or any data-pipeline scripts.
