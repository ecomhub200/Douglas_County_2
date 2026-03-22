# Claude Code Prompt: Update State Hierarchy Files, View Levels & R2 Folder Structure

## Context

The CrashLens application uses `states/{state}/hierarchy.json` files to define the geographic hierarchy for each US state. An audit revealed significant gaps across all 50 states + DC. This prompt instructs Claude Code to fix all identified issues systematically.

### Current View Levels
```
Federal > State > Region (DOT District) > MPO > County
```

### Target View Levels (after this update)
```
Federal > State > Region (DOT District) > Planning District > MPO > County
```

---

## Audit Findings Summary

### 1. MPOs Incomplete Across Most States
Virginia has only 8 of 15 MPOs. Other states with known gaps: Ohio (missing 5), Georgia (missing 5), North Carolina (missing 3), Michigan (missing 3), Texas (missing 2), California (missing 1), Maryland (missing 1). Most other states have not been validated against BTS/FHWA MPO lists.

### 2. Planning Districts / Regional Councils — Completely Missing
No state hierarchy.json has a `planningDistricts` section. Every state has planning regions that sit between DOT Districts and MPOs:

| State | Planning Region Name | Approx. Count |
|-------|---------------------|---------------|
| Virginia | Planning District Commission (PDC) | 21 |
| North Carolina | Rural Planning Organization (RPO) + COG | 20 |
| Texas | Council of Governments (COG) | 24 |
| Georgia | Regional Commission (RC) | 12 |
| Florida | Regional Planning Council (RPC) | 10 |
| Colorado | Already has TPRs, needs COG layer | 14 |
| Ohio | Regional Planning Organization | 17 |
| Pennsylvania | Metropolitan/Rural Planning Org | 23 |
| (All other states) | Varies (COG, RPC, RPO, ADD, etc.) | Varies |

### 3. Counties Not Assigned to Regions
Virginia has 20 counties/cities not assigned to any VDOT Construction District, including Accomack, Carroll, Grayson, Fluvanna, Prince Edward, Charlottesville City, Danville City, Winchester City, and others.

### 4. Towns/Municipalities Missing
Virginia's crash data uses 324 jurisdiction codes (95 counties + ~40 independent cities + ~190 incorporated towns). The hierarchy.json `allCounties` only has 133 entries. Towns should be nested under their parent county (not as separate top-level entries).

---

## Task Instructions

### Phase 1: Fix Virginia (Template State)

#### 1A. Complete Virginia MPO List (15 total)

Using the VDOT reference data, add the 7 missing MPOs to `states/virginia/hierarchy.json` under `tprs`:

| Key | Full Name | VDOT Code | Counties (FIPS) |
|-----|-----------|-----------|-----------------|
| `bristol_mpo` | Bristol VA-TN MPO | BRIS | 191 (Washington), 520 (Bristol City) |
| `danville_mpo` | Danville MPO | DAN | 083 (Halifax), 143 (Pittsylvania), 590 (Danville City) |
| `harrisonburg_mpo` | Harrisonburg-Rockingham MPO | HAR | 165 (Rockingham), 660 (Harrisonburg City) |
| `kingsport_mpo` | Kingsport TN-VA MPO | KING | 169 (Scott), 105 (Lee) — VA portion |
| `lynchburg_mpo` | Lynchburg Area MPO | LYN | 009 (Amherst), 031 (Campbell), 019 (Bedford), 680 (Lynchburg City) |
| `nrvmpo` | New River Valley MPO | NRV | 121 (Montgomery), 155 (Pulaski), 750 (Radford City) |
| `tricities_mpo` | Tri-Cities Area TN-VA MPO | TCAT | 185 (Tazewell) — VA portion |

Verify existing MPOs match VDOT codes:
- HRTPO = HAMP ✓
- NVTA = NOVA ✓
- RVARC = RICH ✓
- FAMPO = FRED ✓
- CAMPO = CVIL ✓
- RVAMPO = ROAN ✓
- SAWMPO = SAW ✓
- WVMPO = WINC ✓

Add a `vdotCode` field to each MPO entry for cross-reference.

#### 1B. Add Virginia Planning Districts (21 PDCs)

Add a new `planningDistricts` section to `states/virginia/hierarchy.json`. Use this structure:

```json
"planningDistrictType": {
  "label": "Planning District Commission",
  "labelPlural": "Planning District Commissions",
  "shortLabel": "PDC"
},
"planningDistricts": {
  "lenowisco": {
    "name": "LENOWISCO Planning District",
    "shortName": "LENOWISCO",
    "center": [-82.6, 36.8],
    "zoom": 10,
    "counties": ["105", "169", "195", "051", "720"],
    "countyNames": { "105": "Lee", "169": "Scott", "195": "Wise", "051": "Dickenson", "720": "Norton City" },
    "parentRegion": "bristol"
  },
  "cumberland_plateau": { ... },
  "mount_rogers": { ... },
  "new_river_valley": { ... },
  "roanoke_valley_alleghany": { ... },
  "west_piedmont": { ... },
  "region_2000": { ... },
  "central_shenandoah": { ... },
  "northern_shenandoah_valley": { ... },
  "thomas_jefferson": { ... },
  "rappahannock_rapidan": { ... },
  "george_washington": { ... },
  "northern_neck": { ... },
  "middle_peninsula": { ... },
  "richmond_regional": { ... },
  "crater": { ... },
  "accomack_northampton": { ... },
  "hampton_roads": { ... },
  "southside": { ... },
  "commonwealth_regional": { ... },
  "northern_virginia": { ... }
}
```

**Source data**: Use the uploaded VDOT reference file `vdot district planning mpo county town city.txt` which maps every jurisdiction to its Planning District. Also web-search "Virginia Planning District Commissions" for county-to-PDC mapping and coordinates.

#### 1C. Fix Orphaned Counties in Virginia Regions

These 20 jurisdictions are NOT assigned to any VDOT Construction District region. Research and assign each to the correct district:

- 001 Accomack → Hampton Roads
- 035 Carroll → Salem (or Bristol — verify)
- 065 Fluvanna → Culpeper (or Lynchburg — verify)
- 077 Grayson → Bristol (or Salem — verify)
- 081 Greensville → Richmond
- 089 Henry → Salem
- 097 King and Queen → Fredericksburg (or Richmond — verify)
- 117 Mecklenburg → Lynchburg (currently listed in Richmond as "127")
- 131 Northampton → Hampton Roads
- 135 Nottoway → Lynchburg (or Richmond — verify)
- 147 Prince Edward → Lynchburg
- 187 Warren → Staunton (or Culpeper — verify)
- 193 Westmoreland → Fredericksburg
- 540 Charlottesville City → Culpeper
- 590 Danville City → Lynchburg
- 620 Franklin City → Hampton Roads
- 678 Lexington City → Staunton
- 690 Martinsville City → Salem
- 775 Salem City → Salem
- 840 Winchester City → Staunton

**Cross-reference with uploaded VDOT reference data** to verify each assignment. The file has a `DOT District` column for every jurisdiction.

#### 1D. Add Towns to Virginia (Nested Under Parent County)

Add a `towns` array inside each county's entry in the `regions` section. For the `allCounties` section, do NOT add towns as separate entries. Instead, add a new top-level `towns` section:

```json
"towns": {
  "003": [
    {"code": "298", "name": "Scottsville"},
    ...
  ],
  "009": [
    {"code": "163", "name": "Amherst"},
    ...
  ]
}
```

Key: parent county FIPS code. Value: array of town objects with VDOT juris code and name.

**Source**: The uploaded VDOT reference file has all 190+ towns with their juris codes and parent county assignments.

---

### Phase 2: Update All 50 States + DC

For EACH state, perform web research and update `hierarchy.json`:

#### 2A. Complete MPO Lists

For each state, web-search: `"{state name}" metropolitan planning organizations list FHWA`

Cross-reference with: https://www.bts.gov/geospatial/metropolitan-planning-organizations

Add any missing MPOs with: name, shortName, type, counties, countyNames, center coordinates, zoom level, btsAcronym, btsMpoId, parentRegion.

#### 2B. Add Planning Districts / Regional Councils

Research each state's regional planning body type:

| State Pattern | Planning Region Type | Search Query |
|--------------|---------------------|-------------|
| VA, NC, SC, WV | Planning District Commission | "{state} planning district commissions list" |
| TX, GA, CO | Council of Governments (COG) | "{state} council of governments list" |
| FL | Regional Planning Council (RPC) | "Florida regional planning councils list" |
| OH, PA, NY | Regional Planning Organization | "{state} regional planning organizations" |
| Most others | Regional Council / Development District | "{state} regional councils counties" |

For each state, add:

```json
"planningDistrictType": {
  "label": "{appropriate label for this state}",
  "labelPlural": "{plural form}",
  "shortLabel": "{abbreviation}"
},
"planningDistricts": {
  "{key}": {
    "name": "...",
    "shortName": "...",
    "center": [lon, lat],
    "zoom": N,
    "counties": ["FIPS1", "FIPS2", ...],
    "countyNames": { "FIPS1": "Name1", ... },
    "parentRegion": "{region_key}"
  }
}
```

#### 2C. Fix Orphaned Counties

For each state, verify that EVERY county in `allCounties` appears in at least one region's `counties` array. If orphaned, research the correct DOT district assignment and add it.

#### 2D. Add Towns/Municipalities (State-Specific)

Not all states need towns. Apply this logic:

- **Virginia**: Add all ~190 incorporated towns (VDOT jurisdiction codes)
- **Other states with independent cities**: Research and add (e.g., Maryland's Baltimore City is already there)
- **States where cities/towns report crashes separately**: Add as nested entries under parent county
- **States where only county-level data exists**: Skip towns (no data to match)

Use judgment: if the state's crash data includes a jurisdiction field that maps to municipalities, include those municipalities. If crash data is county-only, skip.

---

### Phase 3: Update R2 Folder Structure

#### 3A. Update `scripts/create_r2_folders.py`

Add planning district folder creation. The script currently creates:
```
{state}/_state/
{state}/_statewide/
{state}/_region/{id}/
{state}/_mpo/{id}/
{state}/{jurisdiction}/
```

Add:
```
{state}/_planning_district/{id}/
```

Update the `get_planning_districts()` function (new) to read from `hierarchy.json`:
```python
def get_planning_districts(hierarchy):
    """Extract planning district keys from hierarchy.json."""
    pds = hierarchy.get("planningDistricts", {})
    return [k for k in pds.keys() if not k.startswith("_")]
```

For towns (nested under parent county), add town subfolders:
```
{state}/{county}/towns/{town_key}/
```

#### 3B. Update `create-r2-folders.yml` Workflow

No changes needed to the workflow itself — it already calls `create_r2_folders.py` which will pick up the new planning district logic.

#### 3C. Update Upload Tab UI

In `app/modules/upload/upload-tab.js`, add the new "Planning District" view level button between "Region" and "MPO" in the view level selector. When selected, populate the dropdown from `hierarchy.json`'s `planningDistricts` section.

---

### Phase 4: Validation

After all changes:

1. **County coverage check**: For every state, verify `allCounties` count matches the official county count (e.g., Virginia = 95 counties + 38 independent cities = 133)
2. **Region assignment check**: Every entry in `allCounties` must appear in at least one region
3. **Planning district coverage**: Every county must appear in exactly one planning district
4. **MPO cross-reference**: Log which counties are NOT in any MPO (rural counties — this is expected)
5. **JSON validity**: Validate every hierarchy.json is valid JSON after changes
6. **R2 dry run**: Run `python scripts/create_r2_folders.py --dry-run` and verify folder counts make sense

---

## Key Rules

1. **Do NOT push directly** — create a PR for review
2. **Use web search** for every state's planning districts and MPO lists — do not guess
3. **Preserve existing data** — only ADD missing entries, don't remove or rename existing ones
4. **Follow the Virginia template** — use Virginia as the pattern for all other states
5. **Commit in logical batches** — one commit per state or per group of related states
6. **Cross-reference the VDOT uploaded file** for all Virginia-specific data
7. **Add `vdotCode`** (or equivalent state-specific code) to MPO entries where the state DOT uses its own abbreviation system

---

## Files to Modify

| File | Changes |
|------|---------|
| `states/virginia/hierarchy.json` | Add 7 MPOs, 21 planning districts, fix 20 orphaned counties, add towns |
| `states/{every other state}/hierarchy.json` | Complete MPOs, add planning districts, fix orphans |
| `scripts/create_r2_folders.py` | Add planning district folder creation, town subfolder creation |
| `app/modules/upload/upload-tab.js` | Add "Planning District" view level button and dropdown logic |

## Estimated Scope

- ~51 hierarchy.json files to update
- ~1 Python script to update
- ~1 JS module to update
- PR should include a validation script that checks all the above rules
