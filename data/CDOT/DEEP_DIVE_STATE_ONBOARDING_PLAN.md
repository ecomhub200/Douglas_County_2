# Deep Dive Tab — State Onboarding Plan

## Overview

When onboarding a new state's crash data, some columns will be standard (used across all states) and some will be state-specific (unused by the core tool). The Deep Dive tab automatically detects state-specific columns and creates analysis panels for them.

This document is the step-by-step guide for Claude Code (or a developer) to onboard a new state's unused columns into the Deep Dive tab.

---

## Phase 1: Discovery & Classification

### Step 1.1 — Read the validated CSV and identify all columns

```bash
head -1 data/<STATE>/<file>.csv | tr ',' '\n' | cat -n
```

### Step 1.2 — Compare against the COL object

The `COL` object in `index.html` defines all standard columns. Any column NOT in COL and NOT a derived/metadata column is a candidate for Deep Dive.

**Standard columns (always utilized):**
- ID, YEAR, DATE, TIME, SEVERITY, K, A, B, C
- COLLISION, WEATHER, LIGHT, SURFACE, ALIGNMENT
- ROAD_DESC, INT_TYPE, TRAFFIC_CTRL, CTRL_STATUS
- WORKZONE, SCHOOL, ALCOHOL, BIKE, PED, SPEED
- DISTRACTED, DROWSY, HITRUN, SENIOR, YOUNG, NIGHT
- UNRESTRAINED, MOTORCYCLE, FUNC_CLASS, AREA_TYPE
- ROUTE, NODE, MP, X, Y, JURISDICTION
- VEHICLE_COUNT, PERSONS_INJURED, PED_KILLED, PED_INJURED

**Metadata columns (skip):**
- `_source_state`, `_source_file`

### Step 1.3 — Classify unused columns into categories

Map each unused column to one of the 9 Deep Dive categories:

| Category | Panel ID | Typical Column Patterns |
|----------|----------|------------------------|
| Driver Demographics | `DriverDemo` | age, sex, gender, dob for each transport unit |
| Speed Intelligence | `Speed` | speed_limit, estimated_speed, stated_speed, travel_speed |
| Driver Behavior | `Behavior` | driver_action, human_factor, contributing_factor, driver_condition |
| Vehicle Fleet | `Vehicle` | vehicle_type, vehicle_make, vehicle_model, vehicle_year |
| Non-Motorist | `NonMotorist` | nm_type, nm_action, nm_location, nm_facility, nm_contributing |
| Crash Sequence | `Sequence` | most_harmful_event, second_harmful, third_harmful, secondary_crash |
| Location Detail | `Location` | city, community, lane_position, location_description |
| Animal Specifics | `Animal` | animal_type, wild_animal, animal_species |
| Agency Metadata | `Agency` | system_code, agency_id, reporting_agency, road_system |

If a column doesn't fit any existing category, consider:
- Adding it to the closest existing category
- Creating a new category (requires HTML panel + JS render function)

---

## Phase 2: Configuration

### Step 2.1 — Create/update enhancements.json

Create `states/<state>/enhancements.json`:

```json
{
  "_description": "Deep Dive panel configuration for <State> data",
  "stateEnhancements": {
    "driverDemographics": {
      "enabled": true,
      "columns": ["_<st>_tu1_age", "_<st>_tu1_sex"],
      "label": "Driver Demographics",
      "description": "Age and gender analysis"
    }
    // ... repeat for each detected category
  },
  "standardUnused": {
    "_description": "Standard columns utilized in Dashboard/Ped-Bike tabs",
    "vehicleCount": { "column": "Vehicle Count", "enriches": "Dashboard" },
    "personsInjured": { "column": "Persons Injured", "enriches": "Dashboard" },
    "pedestriansKilled": { "column": "Pedestrians Killed", "enriches": "Ped/Bike" },
    "pedestriansInjured": { "column": "Pedestrians Injured", "enriches": "Ped/Bike" }
  }
}
```

### Step 2.2 — Update panelConfig in index.html

In the `deepDiveState.panelConfig` object, update column names to match the new state's prefix:

```javascript
DriverDemo: { columns: ['_<st>_tu1_age','_<st>_tu1_sex',...], label: 'Driver Demographics', icon: '👤' }
```

**Convention:** State-specific columns use prefix `_<state_abbrev>_` (e.g., `_co_`, `_va_`, `_nc_`).

### Step 2.3 — Update state config.json

Ensure `states/<state>/config.json` includes mappings for:
- `VEHICLE_COUNT`, `PERSONS_INJURED`, `PED_KILLED`, `PED_INJURED` (if available)

---

## Phase 3: Data Quality Checks

Before deploying, verify each column:

### Step 3.1 — Check data population rates

```python
for col in state_specific_columns:
    non_empty = sum(1 for r in rows if r[col].strip())
    print(f"{col}: {non_empty}/{total} ({non_empty/total*100:.1f}%)")
```

### Step 3.2 — Check for data quality issues

| Issue | Example | Fix |
|-------|---------|-----|
| Outlier values | Speed = 510 mph | Filter: `est <= 150` |
| Coded values | Lane = "N01" | Decode: `ddDecodeLanePos()` |
| Low population | City only 3% populated | Add context note in insight |
| Cross-column dependency | Facility data without NM type | Query columns independently |
| Inconsistent casing | "TRUE" vs "True" vs "true" | Normalize: `.toUpperCase()` |

### Step 3.3 — Validate severity mapping

Ensure the state's severity values map correctly to K/A/B/C/O. Check:
```python
set(r['Crash Severity'] for r in rows)
```

---

## Phase 4: Render Function Adaptation

Each panel has a render function `renderDD<PanelId>(rows)`. When adapting for a new state:

### Key patterns that may differ by state:

1. **Column names** — Update all `r['_co_...']` references to new state prefix
2. **Value formats** — Different states encode values differently:
   - Boolean: "TRUE"/"FALSE" vs "Yes"/"No" vs "1"/"0"
   - Age: numeric vs range string
   - Speed: mph vs km/h
3. **Data availability** — Some states may have TU3, TU4 (3rd, 4th transport unit); others only TU1
4. **NM data structure** — Some states have NM2 (second non-motorist); others only NM1

### Adaptation checklist:

- [ ] Update column name references in render functions
- [ ] Verify boolean/flag value parsing
- [ ] Adjust outlier thresholds for state's data range
- [ ] Add state-specific value decoders if needed (like `ddDecodeLanePos`)
- [ ] Test each chart renders with actual data
- [ ] Verify KPI calculations use correct columns
- [ ] Check insight text makes sense with state's data patterns

---

## Phase 5: Testing

### Test matrix:

| Test | What to verify |
|------|---------------|
| Panel detection | Correct panels show/hide based on available columns |
| Chart rendering | All charts display data (no empty charts) |
| KPI accuracy | KPI values match manual calculation |
| Date filtering | Filter panel correctly restricts data |
| Export CSV | Exported file contains correct columns and data |
| Export PDF | PDF contains insights from all active panels |
| Responsive | Layout works on mobile/tablet |
| No console errors | No JavaScript errors in browser console |

### Automated validation:

```javascript
// Run in browser console after data loads
console.log('Deep Dive State:', deepDiveState);
console.log('Detected columns:', deepDiveState.detectedColumns);
console.log('Active panels:', deepDiveState.activePanels);
console.log('Filtered rows:', deepDiveState.filteredRows.length);
```

---

## Phase 6: Making panelConfig State-Agnostic (Future)

Currently, `panelConfig` hardcodes `_co_` prefixed columns. To make this truly state-agnostic:

### Option A — Pattern-based detection

Instead of exact column names, detect by pattern:
```javascript
// Detect any column matching *_tu1_age, *_tu1_sex, etc.
const ageCol = allCols.find(c => c.match(/_tu1_age$/));
const sexCol = allCols.find(c => c.match(/_tu1_sex$/));
```

### Option B — Config-driven

Load panel config from `enhancements.json`:
```javascript
const config = await fetch(`states/${state}/enhancements.json`).then(r => r.json());
deepDiveState.panelConfig = buildPanelConfig(config.stateEnhancements);
```

### Option C — Auto-categorize by naming convention

If the state conversion pipeline consistently names columns:
- `_<st>_tu<N>_*` → Transport unit fields → DriverDemo, Speed, Behavior, Vehicle
- `_<st>_nm<N>_*` → Non-motorist fields → NonMotorist
- `_<st>_mhe`, `_<st>_*_he` → Harmful events → Sequence
- `_<st>_city`, `_<st>_location*` → Location
- `_<st>_wild_animal*` → Animal
- `_<st>_system_code`, `_<st>_agency*` → Agency

---

## Quick Reference: Current Implementation

### Files modified:
- `app/index.html` — Deep Dive HTML (tab content), CSS (panel styles), JavaScript (state management, 9 render functions, filtering, export)
- `states/<state>/config.json` — Column mappings for standard unused columns
- `states/<state>/enhancements.json` — Deep Dive panel configuration

### Key functions:
| Function | Purpose |
|----------|---------|
| `detectDeepDiveColumns()` | Scan CSV headers for state-specific columns |
| `initDeepDiveTab()` | Initialize tab, show panels, first render |
| `applyDeepDiveFilters()` | Apply date filters and re-render |
| `renderAllDeepDivePanels()` | Orchestrate rendering all active panels |
| `renderDD<PanelId>(rows)` | Render individual panel (charts, KPIs, tables, insights) |
| `ddRenderKpiRow(id, kpis)` | Render KPI card row following Hotspots pattern |
| `ddDecodeLanePos(code)` | Decode lane position codes to human-readable labels |
| `exportDeepDiveCSV()` | Export state-specific data to CSV |
| `exportDeepDivePDF()` | Generate PDF report with all panel insights |

### Data flow:
```
crashState.sampleRows
    → ddGetFilteredRows() (apply date filter)
    → renderAllDeepDivePanels()
        → Top-level KPI summary
        → Each panel: KPI row → Charts → Tables → Insight text
```

### Bugs fixed in current implementation:
1. **NM facility chart empty** — Was pre-filtering all NM data by nm1_type; now queries each column independently
2. **Speed outliers** — Added max speed filter (150 mph) to exclude data errors
3. **Lane position codes** — Added `ddDecodeLanePos()` to translate coded values
4. **City data context** — Added note when < 50% of crashes have city data
5. **Heat map intensity** — Matrix heat maps now scale to actual data max, not hardcoded threshold
