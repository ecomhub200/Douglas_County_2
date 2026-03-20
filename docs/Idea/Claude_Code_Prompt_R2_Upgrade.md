# Claude Code Prompt — R2 Folder Structure Upgrade + Frontend View Expansion

> Paste this entire prompt into Claude Code. It will upgrade your R2 folder structure to match the full geography database, add missing frontend views (Planning District, MPO, County, City, Town), and wire the data connections.

---

## CONTEXT

We have a crash data analytics platform called **CRASH LENS** with:
- **Backend:** Cloudflare R2 bucket (`crash-lens-data`) at `https://data.aicreatesai.com`
- **Frontend:** Plain HTML/JS app in `app/index.html` with modular upload tab (`app/modules/upload/`)
- **GitHub Actions:** `create-r2-folders.yml` workflow + `scripts/create_r2_folders.py` for R2 folder creation
- **Geography database:** 5 JSON files in `states/geography/` on R2, downloaded from Census Gazetteer + BTS/USDOT:
  - `us_states.json` — 52 records (50 states + DC + PR). Fields: GEOID, STATE, NAME, USPS, CENTLAT, CENTLON
  - `us_counties.json` — 3,222 records. Fields: GEOID, STATE, COUNTY (3-digit FIPS), NAME, BASENAME, CENTLAT, CENTLON
  - `us_places.json` — 32,333 records (cities/towns/CDPs). Fields: GEOID, STATE, PLACE (5-digit FIPS), NAME, BASENAME, CENTLAT, CENTLON
  - `us_mpos.json` — 410 records. Fields: MPO_ID, MPO_NAME, NAME, STATE (2-letter abbr), CENTLAT, CENTLON
  - `us_county_subdivisions.json` — 36,421 records (townships/boroughs). Fields: GEOID, STATE, COUNTY, COUSUB, NAME, CENTLAT, CENTLON

### Current R2 Folder Structure (PARTIAL — needs upgrade):

```
crash-lens-data/
  _national/
    state_comparison.json
    dot_roads.csv | non_dot_roads.csv | statewide_all_roads.csv
  states/
    geography/
      us_states.json | us_counties.json | us_places.json
      us_mpos.json | us_county_subdivisions.json
  {state}/                          # e.g., colorado/, virginia/
    _state/                         # Statewide raw data
      all_roads.csv | dot_roads.csv | non_dot_roads.csv
    _statewide/                     # Statewide aggregates
      aggregates.json
    _region/{regionId}/             # DOT district/region
      aggregates.json | all_roads.csv | dot_roads.csv
    _mpo/{mpoId}/                   # MPO tier (PARTIALLY EXISTS)
      aggregates.json | all_roads.csv
    {county}/                       # County-level (e.g., douglas/, henrico/)
      county_roads.csv | no_interstate.csv | all_roads.csv
      standardized.csv
      forecasts_county_roads.json | forecasts_no_interstate.json | forecasts_all_roads.json
```

### What's MISSING in R2 (needs to be added):

```
  {state}/
    _planning_district/{pdId}/      # ← NEW: Planning District tier
      aggregates.json | all_roads.csv | dot_roads.csv | non_dot_roads.csv
      forecasts_county_roads.json | forecasts_no_interstate.json | forecasts_all_roads.json
    _mpo/{mpoId}/                   # ← UPGRADE: Add road type splits + forecasts
      dot_roads.csv | non_dot_roads.csv
      forecasts_county_roads.json | forecasts_no_interstate.json | forecasts_all_roads.json
    _city/{citySlug}/               # ← NEW: City/Town tier (from us_places.json)
      aggregates.json | all_roads.csv | county_roads.csv | no_interstate.csv
      forecasts_county_roads.json | forecasts_no_interstate.json | forecasts_all_roads.json
    _town/{townSlug}/               # ← NEW: Town/subdivision tier (from us_county_subdivisions.json)
      aggregates.json | all_roads.csv
```

### What's MISSING in Frontend:

The frontend Upload Data tab currently only has **State** and **County** dropdowns. It's missing:
- Planning District / Planning Commission view level
- MPO view level (folders exist but no dropdown selector)
- City view level
- Town view level

The frontend uses a **tier** system in `getDataFilePath()` to build R2 paths. Currently it supports:
- `federal` → `_national/`
- `state` → `{state}/_state/`
- `region` → `{state}/_region/{regionId}/`
- `mpo` → `{state}/_mpo/{mpoId}/`  (partially, no UI selector)
- `county` → `{state}/{county}/`

---

## TASK 1: Upgrade `scripts/create_r2_folders.py`

Update the R2 folder creation script to create the FULL folder hierarchy based on the geography JSONs. The script already reads `states/{state}/hierarchy.json` for regions. Now it must also:

1. **Read `states/geography/us_mpos.json`** — for each state, create `{state}/_mpo/{mpo_slug}/` folders for every MPO where `STATE` matches (note: MPO file uses 2-letter state abbreviation in STATE field, not FIPS)
2. **Read `states/geography/us_places.json`** — for each state, create `{state}/_city/{place_slug}/` for places with `FUNCSTAT='A'` and `LSADC` in ['25','43','46','47','49','57'] (incorporated places — cities, towns, villages, boroughs, etc.)
3. **Read `states/geography/us_county_subdivisions.json`** — for each state, create `{state}/_town/{cousub_slug}/` for subdivisions with `FUNCSTAT='A'`
4. **Read `hierarchy.json`** — if the state has `planningDistricts` or `regions` with PD assignments, create `{state}/_planning_district/{pd_slug}/` folders

**Slug rules:** lowercase, replace spaces with underscores, strip special characters. Example: `"Dover/Kent County MPO"` → `dover_kent_county_mpo`

**Each new folder must contain these marker files** (same pattern as existing county folders):
- `aggregates.json`
- `all_roads.csv`
- `county_roads.csv` (for city/PD tiers)
- `no_interstate.csv` (for city/PD tiers)
- `forecasts_all_roads.json`
- `forecasts_county_roads.json`
- `forecasts_no_interstate.json`

**Also update the `--geography-only` scope** to upload all 5 geography JSONs to `states/geography/` on R2, plus each state's `hierarchy.json` to `{state}/hierarchy.json`.

---

## TASK 2: Upgrade `data/r2-manifest.json`

Update the manifest generation to include the new tiers. The manifest's `localPathMapping` must include entries for:
- `{state}/_planning_district/{pdId}/all_roads.csv`
- `{state}/_city/{citySlug}/all_roads.csv`
- `{state}/_town/{townSlug}/all_roads.csv`

Add a new `tiers` section to the manifest:

```json
{
  "version": 4,
  "r2BaseUrl": "https://data.aicreatesai.com",
  "tiers": ["federal", "state", "region", "planning_district", "mpo", "county", "city", "town"],
  "geography": {
    "states": "states/geography/us_states.json",
    "counties": "states/geography/us_counties.json",
    "places": "states/geography/us_places.json",
    "mpos": "states/geography/us_mpos.json",
    "subdivisions": "states/geography/us_county_subdivisions.json"
  }
}
```

---

## TASK 3: Upgrade Frontend — Add View Level Selector

In `app/index.html`, find the Upload Data tab section where the State and County dropdowns are. Add a **View Level** selector between State and the jurisdiction dropdown. This controls which tier of data to load.

### 3A: Add the View Level dropdown

```html
<div class="form-group" id="viewLevelGroup">
  <label>View Level</label>
  <select id="viewLevelSelect" onchange="onViewLevelChange()">
    <option value="county" selected>County</option>
    <option value="city">City / Town</option>
    <option value="planning_district">Planning District</option>
    <option value="mpo">MPO (Metropolitan Planning Organization)</option>
    <option value="state">Statewide</option>
  </select>
</div>
```

### 3B: Dynamic Jurisdiction Dropdown

When the view level changes, repopulate the jurisdiction dropdown with the appropriate list:

```javascript
async function onViewLevelChange() {
  const level = document.getElementById('viewLevelSelect').value;
  const stateAbbr = getCurrentStateAbbr(); // 2-letter
  const stateFips = getCurrentStateFips(); // 2-digit FIPS
  const stateName = getCurrentStateName().toLowerCase().replace(/\s+/g, '_');

  const jurisdictionSelect = document.getElementById('jurisdictionDropdown');
  jurisdictionSelect.innerHTML = '<option value="">Loading...</option>';

  try {
    if (level === 'county') {
      // Load from us_counties.json — filter by STATE FIPS
      const counties = await loadGeoData('counties');
      const stateCounties = counties.filter(c => c.STATE === stateFips);
      populateDropdown(jurisdictionSelect, stateCounties, 'BASENAME', 'COUNTY');

    } else if (level === 'city') {
      // Load from us_places.json — filter by STATE FIPS
      const places = await loadGeoData('places');
      const statePlaces = places.filter(p => p.STATE === stateFips && p.FUNCSTAT === 'A');
      populateDropdown(jurisdictionSelect, statePlaces, 'NAME', 'PLACE');

    } else if (level === 'mpo') {
      // Load from us_mpos.json — filter by STATE abbreviation
      const mpos = await loadGeoData('mpos');
      const stateMpos = mpos.filter(m => m.STATE === stateAbbr);
      populateDropdown(jurisdictionSelect, stateMpos, 'MPO_NAME', 'MPO_ID');

    } else if (level === 'planning_district') {
      // Load from hierarchy.json — extract planning districts/regions
      const hierarchy = await loadHierarchy(stateName);
      const pds = Object.entries(hierarchy.regions || {}).map(([key, val]) => ({
        name: val.name || val.shortName || key,
        id: key
      }));
      populateDropdownFromList(jurisdictionSelect, pds);

    } else if (level === 'state') {
      jurisdictionSelect.innerHTML = '<option value="_state">Statewide (All Jurisdictions)</option>';
    }
  } catch (err) {
    console.error('[ViewLevel] Failed to load jurisdiction list:', err);
    jurisdictionSelect.innerHTML = '<option value="">Failed to load</option>';
  }
}
```

### 3C: Geography Data Loader (cached)

```javascript
const _geoCache = {};

async function loadGeoData(type) {
  if (_geoCache[type]) return _geoCache[type];

  const r2Base = 'https://data.aicreatesai.com';
  const paths = {
    states: '/states/geography/us_states.json',
    counties: '/states/geography/us_counties.json',
    places: '/states/geography/us_places.json',
    mpos: '/states/geography/us_mpos.json',
    subdivisions: '/states/geography/us_county_subdivisions.json'
  };

  const resp = await fetch(r2Base + paths[type]);
  if (!resp.ok) throw new Error(`Failed to load ${type}: ${resp.status}`);
  const data = await resp.json();
  _geoCache[type] = data.records || data;
  return _geoCache[type];
}

async function loadHierarchy(stateSlug) {
  const cacheKey = `hierarchy_${stateSlug}`;
  if (_geoCache[cacheKey]) return _geoCache[cacheKey];

  const r2Base = 'https://data.aicreatesai.com';
  const paths = [
    `/${stateSlug}/hierarchy.json`,
    `/${stateSlug}/_state/hierarchy.json`,
    `/states/${stateSlug}/hierarchy.json`
  ];

  for (const path of paths) {
    try {
      const resp = await fetch(r2Base + path);
      if (resp.ok) {
        const data = await resp.json();
        _geoCache[cacheKey] = data;
        return data;
      }
    } catch (e) { /* try next path */ }
  }
  return { regions: {} };
}
```

---

## TASK 4: Upgrade `getDataFilePath()` — Support All Tiers

Find `getDataFilePath()` in `app/index.html` (around line ~23177). Update it to handle the new view levels:

```javascript
function getDataFilePath() {
  const viewLevel = document.getElementById('viewLevelSelect')?.value || 'county';
  const statePrefix = getR2Prefix(); // e.g., 'colorado'
  const jurisdictionId = getSelectedJurisdiction(); // selected dropdown value
  const roadType = getActiveRoadTypeSuffix(); // 'county_roads' | 'no_interstate' | 'all_roads'

  // Slug the jurisdiction ID for R2 path
  const slug = jurisdictionId.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/_+$/, '');

  switch (viewLevel) {
    case 'state':
      return `${statePrefix}/_state/${roadType}.csv`;

    case 'region':
      return `${statePrefix}/_region/${slug}/${roadType}.csv`;

    case 'planning_district':
      return `${statePrefix}/_planning_district/${slug}/${roadType}.csv`;

    case 'mpo':
      return `${statePrefix}/_mpo/${slug}/${roadType}.csv`;

    case 'county':
      return `${statePrefix}/${slug}/${roadType}.csv`;

    case 'city':
      return `${statePrefix}/_city/${slug}/${roadType}.csv`;

    case 'town':
      return `${statePrefix}/_town/${slug}/${roadType}.csv`;

    default:
      return `${statePrefix}/${slug}/${roadType}.csv`;
  }
}
```

**Also update `getFallbackData()`** (around line ~21835) to use the same view-level-aware path construction. It currently hardcodes county-tier paths.

**Also update `getPredictionForecastFile()`** in `initPredictionTab()` (around line ~143184) to use the same tier logic for forecast JSON paths:

```javascript
function getPredictionForecastFile() {
  const viewLevel = document.getElementById('viewLevelSelect')?.value || 'county';
  const statePrefix = getR2Prefix();
  const jurisdictionId = getSelectedJurisdiction();
  const roadType = getActiveRoadTypeSuffix();
  const slug = jurisdictionId.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/_+$/, '');

  const tierPath = {
    state: `${statePrefix}/_state`,
    region: `${statePrefix}/_region/${slug}`,
    planning_district: `${statePrefix}/_planning_district/${slug}`,
    mpo: `${statePrefix}/_mpo/${slug}`,
    county: `${statePrefix}/${slug}`,
    city: `${statePrefix}/_city/${slug}`,
    town: `${statePrefix}/_town/${slug}`
  }[viewLevel] || `${statePrefix}/${slug}`;

  return `${tierPath}/forecasts_${roadType}.json`;
}
```

---

## TASK 5: Upgrade `resolveDataUrl()` — Recognize New Tier Paths

Find `resolveDataUrl()` in `app/index.html` (around line ~22055). The R2-native path detection regex must recognize the new tier prefixes:

```javascript
// Strategy 3: R2-native path detection
const isR2NativePath = !normalizedPath.startsWith('data/')
    && normalizedPath.includes('/')
    && (normalizedPath.endsWith('.csv')
        || normalizedPath.endsWith('.json')
        || normalizedPath.endsWith('.csv.gz'));
```

This should already work since `_planning_district/`, `_city/`, `_town/` all match the generic pattern. But verify it handles paths like:
- `colorado/_planning_district/greater_denver/all_roads.csv`
- `virginia/_city/richmond/county_roads.csv`
- `delaware/_mpo/wilmapco/all_roads.csv`

All should resolve to: `https://data.aicreatesai.com/{path}`

---

## TASK 6: Upgrade `config.json` — Add Tier Metadata per State

In the root `config.json`, add a `tiers` array to each state config so the frontend knows which view levels are available:

```json
{
  "colorado": {
    "fips": "08",
    "r2Prefix": "colorado",
    "defaultJurisdiction": "douglas",
    "tiers": ["state", "region", "mpo", "planning_district", "county", "city"]
  },
  "virginia": {
    "fips": "51",
    "r2Prefix": "virginia",
    "defaultJurisdiction": "henrico",
    "tiers": ["state", "region", "mpo", "planning_district", "county", "city"]
  },
  "delaware": {
    "fips": "10",
    "r2Prefix": "delaware",
    "defaultJurisdiction": "new_castle",
    "tiers": ["state", "mpo", "county", "city"]
  }
}
```

Then in `onViewLevelChange()`, filter the View Level dropdown to only show tiers that exist for the selected state:

```javascript
function updateViewLevelOptions(stateTiers) {
  const select = document.getElementById('viewLevelSelect');
  const allTiers = [
    { value: 'county', label: 'County' },
    { value: 'city', label: 'City / Town' },
    { value: 'planning_district', label: 'Planning District' },
    { value: 'mpo', label: 'MPO' },
    { value: 'state', label: 'Statewide' }
  ];
  select.innerHTML = '';
  allTiers.forEach(t => {
    if (stateTiers.includes(t.value)) {
      select.innerHTML += `<option value="${t.value}">${t.label}</option>`;
    }
  });
}
```

---

## TASK 7: Update `checkR2DataAvailability()`

Find `checkR2DataAvailability()` (around line ~21938). Update it to check all tiers, not just county:

```javascript
async function checkR2DataAvailability() {
  const viewLevel = document.getElementById('viewLevelSelect')?.value || 'county';
  const testPath = getDataFilePath();
  const testUrl = resolveDataUrl(testPath);

  try {
    const resp = await fetch(testUrl, { method: 'HEAD' });
    if (resp.ok) {
      console.log(`[R2] Data available at ${viewLevel} tier: ${testUrl}`);
      return true;
    }
    console.warn(`[R2] No data at ${viewLevel} tier: ${resp.status} ${testUrl}`);
    return false;
  } catch (e) {
    console.error('[R2] Availability check failed:', e.message);
    return false;
  }
}
```

---

## TASK 8: Update `updateCurrentSelectionDisplay()`

Find where the current selection summary is displayed (something like "Colorado > Douglas County > All Roads"). Update it to show the view level:

```javascript
function updateCurrentSelectionDisplay() {
  const state = getCurrentStateName();
  const viewLevel = document.getElementById('viewLevelSelect')?.value || 'county';
  const jurisdiction = getSelectedJurisdictionName();
  const roadType = getActiveRoadTypeSuffix().replace(/_/g, ' ');

  const levelLabels = {
    state: 'Statewide',
    region: 'Region',
    planning_district: 'Planning District',
    mpo: 'MPO',
    county: 'County',
    city: 'City',
    town: 'Town'
  };

  const display = viewLevel === 'state'
    ? `${state} > ${levelLabels[viewLevel]} > ${roadType}`
    : `${state} > ${levelLabels[viewLevel]}: ${jurisdiction} > ${roadType}`;

  document.getElementById('currentSelectionText').textContent = display;
}
```

---

## TASK 9: Wire `create-r2-folders.yml` Workflow

Update the GitHub Actions workflow to pass the geography upload flag and support the new folder tiers. The `create_r2_folders.py` script should:

1. For each state, read all 5 geography JSONs to determine which entities belong to that state
2. Create folder markers for every tier:
   - `{state}/_planning_district/{pd_slug}/` — from hierarchy.json regions
   - `{state}/_mpo/{mpo_slug}/` — from us_mpos.json filtered by state
   - `{state}/_city/{city_slug}/` — from us_places.json filtered by state (incorporated places only)
   - `{state}/_town/{town_slug}/` — from us_county_subdivisions.json filtered by state
3. Upload geography JSONs to `states/geography/` on R2
4. Upload each state's `hierarchy.json` to `{state}/hierarchy.json` on R2

**Expected folder counts per state (examples):**
- Delaware: 3 counties + ~57 places + ~3 county subdivisions + 2 MPOs + 3 regions ≈ 68 folders
- Virginia: 133 counties/cities + ~500 places + ~300 subdivisions + ~15 MPOs + 9 VDOT districts ≈ 957 folders
- Colorado: 64 counties + ~450 places + ~15 MPOs + 15 TPRs ≈ 544 folders

---

## TASK 10: Verify Data Connection Links

After all changes, verify end-to-end:

1. **R2 path construction** — for every view level, `getDataFilePath()` produces a valid R2 key
2. **URL resolution** — `resolveDataUrl()` converts every path to `https://data.aicreatesai.com/{path}`
3. **Forecast paths** — `getPredictionForecastFile()` returns correct forecast JSON paths for each tier
4. **Case sensitivity** — ALL paths are lowercase before hitting R2
5. **Dropdown population** — each view level populates its jurisdiction dropdown from the correct geography JSON
6. **State filtering** — geography data is correctly filtered by state FIPS (counties, places, subdivisions) or state abbreviation (MPOs)

### Test matrix:

| View Level | State | Jurisdiction | Expected R2 Path |
|-----------|-------|-------------|-----------------|
| county | Colorado | Douglas | `colorado/douglas/all_roads.csv` |
| city | Virginia | Richmond | `virginia/_city/richmond/all_roads.csv` |
| mpo | Delaware | WILMAPCO | `delaware/_mpo/wilmapco/all_roads.csv` |
| planning_district | Virginia | Hampton Roads | `virginia/_planning_district/hampton_roads/all_roads.csv` |
| state | Colorado | (statewide) | `colorado/_state/all_roads.csv` |
| town | Delaware | Wilmington | `delaware/_town/wilmington/all_roads.csv` |

### Console diagnostic:

```javascript
async function diagFullTiers() {
  const levels = ['state', 'region', 'planning_district', 'mpo', 'county', 'city', 'town'];
  console.group('[Tier Diagnostics]');
  for (const level of levels) {
    document.getElementById('viewLevelSelect').value = level;
    await onViewLevelChange();
    const path = getDataFilePath();
    const url = resolveDataUrl(path);
    console.log(`${level}: ${path} → ${url}`);
  }
  console.groupEnd();
}
```

---

## IMPORTANT RULES

1. **All R2 paths must be lowercase.** Apply `.toLowerCase()` everywhere.
2. **Never modify the 69-column CrashLens standard schema.** This is frontend data structure only.
3. **Geography JSONs are read-only reference data.** Never modify them — only read from them to build folder structures and populate dropdowns.
4. **Slug format:** `name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/_+$/, '').replace(/^_+/, '')`
5. **The frontend is plain HTML/JS** — no React, no build step. All changes go in `app/index.html` or the `app/modules/upload/*.js` files.
6. **Keep backward compatibility.** Existing county-tier data loading must continue to work exactly as before. New tiers are additive.
7. **Cache geography data.** The JSON files are large (us_places = 32K records, us_county_subdivisions = 36K records). Load once, cache in memory.
8. **MPO STATE field uses 2-letter abbreviation** (e.g., "CO", "VA"), NOT FIPS codes. All other files use 2-digit FIPS in STATE field.

---

## FILES TO MODIFY (Summary)

| File | Changes |
|------|---------|
| `scripts/create_r2_folders.py` | Add _planning_district, _city, _town folder creation from geography JSONs |
| `.github/workflows/create-r2-folders.yml` | Already handles the script — may need minor updates |
| `data/r2-manifest.json` | Bump to v4, add tiers array, add geography paths |
| `config.json` | Add `tiers` array to each state config |
| `app/index.html` | Add View Level dropdown, update `getDataFilePath()`, `getFallbackData()`, `resolveDataUrl()`, `initPredictionTab()`, `checkR2DataAvailability()`, `updateCurrentSelectionDisplay()` |
| `app/modules/upload/upload-tab.js` | Add `onViewLevelChange()`, `loadGeoData()`, `loadHierarchy()`, `updateViewLevelOptions()` |
| `tests/test_r2_integration.js` | Add tests for new tier path construction |
| `tests/test_upload_tab_bug.js` | Add tests for view level switching |
