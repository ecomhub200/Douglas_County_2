---
name: frontend-r2-connection
description: "Front-end R2 folder structure and connection audit. Covers R2 bucket hierarchy, front-end path construction, iframe module R2 sync, and tier-aware path mapping for all jurisdiction types (county, state, region, MPO, planning district, city, federal). Use for: R2 path debugging, verifying upload destinations, auditing iframe R2 sync, adding tier support to child modules, understanding folder naming conventions."
---

# Front-End R2 Connection & Folder Structure

Comprehensive reference for how the CrashLens front-end connects to Cloudflare R2 storage, how folder paths are constructed, and how child iframe modules sync with the R2 hierarchy.

## When to Apply

Use this skill when:
- Debugging R2 upload/download paths in any module
- Adding a new jurisdiction tier or modifying existing tier paths
- Updating child iframe modules (validator, inventory, asset deficiency) for tier awareness
- Verifying that front-end R2 paths match the `create_r2_folders.py` structure
- Onboarding a new state and ensuring R2 folders align with front-end expectations
- Auditing data flow between parent app and iframe modules
- Troubleshooting "file not found" errors from R2

---

## R2 Bucket Structure (Source of Truth)

**Bucket:** `crash-lens-data`
**Public URL:** `https://data.aicreatesai.com`
**Folder creation script:** `scripts/create_r2_folders.py`
**Workflow:** `.github/workflows/create-r2-folders.yml`

### Complete Hierarchy

```
crash-lens-data/
├── _federal/
├── _national/
│   ├── all_roads.csv
│   ├── dot_roads.csv
│   └── non_dot_roads.csv
├── shared/
│   ├── boundaries/
│   └── mutcd/
├── states/
│   └── geography/
│       ├── us_states.json
│       ├── us_counties.json
│       ├── us_mpos.json
│       ├── us_places.json
│       └── us_county_subdivisions.json
└── {state_prefix}/                          # e.g., virginia, colorado
    ├── _state/
    │   ├── hierarchy.json
    │   ├── statewide_all_roads.csv
    │   ├── dot_roads.csv
    │   └── city_roads.csv
    ├── _statewide/
    │   └── snapshots/
    ├── _region/{region_id}/
    │   ├── all_roads.csv
    │   ├── dot_roads.csv
    │   └── city_roads.csv
    ├── _planning_district/{pd_id}/
    │   └── all_roads.csv
    ├── _mpo/{mpo_id}/
    │   └── all_roads.csv
    ├── _city/{city_slug}/
    │   └── all_roads.csv
    └── {jurisdiction_id}/                   # County-level (default)
        ├── raw/                             # Raw annual source data
        ├── all_roads.csv
        ├── county_roads.csv
        ├── city_roads.csv
        ├── no_interstate.csv
        ├── traffic-inventory.csv
        ├── traffic-inventory-edits.json
        ├── corrections_ledger_{fileKey}.json
        └── validation_report_{fileKey}.json
```

### Naming Conventions

| Entity | Convention | Example |
|--------|-----------|---------|
| State prefix | lowercase, underscores | `virginia`, `new_york`, `north_carolina` |
| Region ID | from `hierarchy.json` regions keys | `bristol`, `region_1`, `hampton_roads` |
| MPO ID | snake_case slug | `drcog`, `hrtpo`, `dover_kent_county_mpo` |
| Planning District ID | from `hierarchy.json` planningDistricts keys | `pd_1`, `mount_rogers` |
| City slug | lowercase, no apostrophes/periods, underscores | `arlington`, `virginia_beach` |
| County/Jurisdiction ID | from `config.json` jurisdictions keys | `henrico`, `douglas`, `accomack` |

### County Key Conversion (`county_name_to_key()` in create_r2_folders.py)
- Lowercase all text
- Remove apostrophes: `Prince George's` -> `prince_georges`
- Remove periods: `St. Mary's` -> `st_marys`
- Replace spaces/hyphens with underscores: `El Paso` -> `el_paso`
- Remove non-alphanumeric (except underscores)
- Collapse multiple underscores, strip leading/trailing

---

## Front-End Path Construction (Parent App)

### Primary Function: `getDataFilePath()`
**File:** `app/modules/upload/upload-tab.js` (lines 61-102)

Constructs R2-native paths based on current `jurisdictionContext.viewTier`:

| View Tier | R2 Path Pattern |
|-----------|----------------|
| `federal` | `_national/{roadType}.csv` |
| `state` | `{r2Prefix}/_state/{roadType}.csv` |
| `region` | `{r2Prefix}/_region/{regionId}/{roadType}.csv` |
| `mpo` | `{r2Prefix}/_mpo/{mpoId}/{roadType}.csv` |
| `planning_district` | `{r2Prefix}/_planning_district/{pdId}/{roadType}.csv` |
| `city` | `{r2Prefix}/_city/{cityId}/{roadType}.csv` |
| `county` (default) | `{r2Prefix}/{jurisdictionId}/{roadType}.csv` |

### Road Type Suffix: `getActiveRoadTypeSuffix(tier)`
**File:** `app/modules/upload/upload-tab.js` (lines 31-53)

**For state/region/federal tiers:**
| Filter Profile | Suffix |
|---------------|--------|
| `countyOnly` | `dot_roads` |
| `cityOnly` | `city_roads` |
| `countyPlusVDOT` | `non_dot_roads` |
| `allRoads` | `statewide_all_roads` (state), `all_roads` (region/federal) |

**For county/MPO/city/planning_district tiers:**
| Filter Profile | Suffix |
|---------------|--------|
| `countyOnly` | `county_roads` |
| `cityOnly` | `city_roads` |
| `countyPlusVDOT` | `no_interstate` |
| `allRoads` | `all_roads` |

### URL Resolution: `resolveDataUrl(localPath)`
**File:** `app/modules/upload/upload-tab.js` (lines 111-175)

Resolution order:
1. **Manifest lookup** — check `r2State.manifest.localPathMapping`
2. **Dynamic construction** — parse legacy `data/` paths into R2 keys
3. **R2-native passthrough** — paths with `_state/`, `_region/`, etc. used directly

### Pipeline Upload: `buildR2DestinationPath()`
**File:** `app/modules/upload/upload-pipeline.js` (lines 57-87)

Same tier logic as `getDataFilePath()`, used for manual CSV pipeline uploads.

### `jurisdictionContext` Global Object
Tracks active view tier and selected entity:
```javascript
jurisdictionContext = {
  viewTier: 'county' | 'state' | 'region' | 'mpo' | 'planning_district' | 'city' | 'federal',
  tierState: { name, ... },
  tierRegion: { id, name, ... },
  tierMpo: { id, name, ... },
  tierPlanningDistrict: { id, name, ... },
  tierCity: { id, name, ... }
}
```

---

## Configuration Files That Drive R2 Paths

| File | Key Properties | Used For |
|------|---------------|----------|
| `config.json` | `states[key].r2Prefix`, `jurisdictions[key]` | State R2 prefix, county IDs |
| `states/{state}/hierarchy.json` | `regions`, `tprs`, `planningDistricts`, `allCounties` | Region/MPO/PD entity IDs |
| `data/r2-manifest.json` | `files`, `localPathMapping`, `r2BaseUrl` | Legacy path resolution |
| `states/{state}/config.json` | `roadSystems.filterProfiles` | Road type suffix mapping |

### State Config in config.json
```json
{
  "states": {
    "colorado": {
      "fips": "08",
      "name": "Colorado",
      "abbreviation": "CO",
      "r2Prefix": "colorado",
      "dataDir": "CDOT",
      "defaultJurisdiction": "douglas"
    }
  }
}
```

---

## Child Iframe Modules — R2 Connections

### Overview

All 4 iframe modules communicate with parent via `postMessage` API. The parent sends jurisdiction context; the child builds R2 paths from it.

### 1. Crash Validation Engine
**File:** `scripts/crash-data-validator-v13.html`
**Iframe ID:** `validatorIframe`
**Parent sync message:** `validator-set-jurisdiction`

**R2 Uploads:**
| Upload | Endpoint | R2 Key Pattern |
|--------|----------|---------------|
| Corrected CSV | `/api/r2/worker-upload` | `{r2Path}{filename}.csv` |
| Corrections Ledger | `/api/r2/worker-upload` | `{state}/{county}/corrections_ledger_{fileKey}.json` |
| Validation Report | `/api/r2/worker-upload` | `{state}/{county}/validation_report_{fileKey}.json` |

**R2 Path Construction (line 1296, 3336):**
```javascript
APP.config.r2Path = '/' + state + '/' + county + '/';
```

**Current Tier Support:** County-only

### 2. Traffic Inventory (Mapillary Downloader)
**File:** `app/traffic-inventory.html`
**Iframe ID:** `trafficInventoryFrame`
**Parent sync message:** `ti-set-jurisdiction`, `ti-set-jurisdictions`

**R2 Key Pattern:** `{state}/{folder}/traffic-inventory.csv`

**R2 Path Construction (line 619):**
```javascript
const key = `${currentJurisdiction.state}/${currentJurisdiction.folder}/traffic-inventory.csv`;
```

**Current Tier Support:** County-only (`folder` is always county-level)

### 3. Asset Inventory Manager
**File:** `app/inventory-manager.html`
**Iframe ID:** `inventoryManagerFrame`
**Parent sync message:** `im-set-jurisdiction`, `im-set-jurisdictions`

**R2 Uploads:**
| Upload | Endpoint | R2 Key Pattern |
|--------|----------|---------------|
| Inventory CSV | `/api/r2/worker-upload` | `{state}/{county}/traffic-inventory.csv` |
| Edits Ledger | `/api/r2/worker-upload` | `{state}/{county}/traffic-inventory-edits.json` |
| Consolidation | `/api/r2/consolidate-inventory` | Statewide merge (fire-and-forget) |

**R2 Path Construction (lines 466, 500-501):**
```javascript
function getR2Key() { return $('stSel').value + '/' + $('coSel').value + '/traffic-inventory.csv' }
```

**Current Tier Support:** County-only

### 4. Asset Deficiency (MUTCD Screening)
**File:** `app/asset-deficiency.html`
**Iframe ID:** `assetDeficiencyFrame`
**Parent sync message:** `ad-config`, `ad-crash-data`

**R2 Reads (no uploads):**
| Data | URL Pattern |
|------|------------|
| Crash CSV | `{r2BaseUrl}/{r2Path}/all_roads.csv` |
| Inventory CSV | `{r2BaseUrl}/{r2Path}/traffic-inventory.csv` |

**R2 Path received from parent (index.html line 57736):**
```javascript
const r2Path = r2Prefix + '/' + jurisdictionId;  // Always county-level
```

**Current Tier Support:** Accepts whatever path parent sends (currently county-only from parent)

---

## CRITICAL FINDING: Tier Support Gap

### Parent App vs Child Iframes

| Component | Federal | State | Region | MPO | Planning District | City | County |
|-----------|---------|-------|--------|-----|-------------------|------|--------|
| **Parent (upload-tab.js)** | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| **Parent (upload-pipeline.js)** | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| **Crash Validator** | No | No | No | No | No | No | **Yes** |
| **Traffic Inventory** | No | No | No | No | No | No | **Yes** |
| **Inventory Manager** | No | No | No | No | No | No | **Yes** |
| **Asset Deficiency** | No | No | No | No | No | No | **Yes** |

### Root Cause

The parent app's iframe sync functions (`sendConfigToAssetDeficiency()`, `syncJurisdictionToTrafficInventory()`, `syncJurisdictionToInventoryManager()`) always send **county-level** jurisdiction info to child iframes, ignoring `jurisdictionContext.viewTier`.

The parent app's own data loading (`getDataFilePath()`) is fully tier-aware, but this tier awareness does NOT propagate to iframe children.

### To Fix (Future Work)

1. **Parent app** — Modify iframe sync functions to include `viewTier` and construct tier-aware `r2Path` using `getDataFilePath()` logic
2. **Each child iframe** — Accept `tier` in message payload, implement tier-aware path construction
3. **All 4 modules** need to build paths matching:
   ```
   federal:            _national/
   state:              {r2Prefix}/_state/
   region:             {r2Prefix}/_region/{regionId}/
   mpo:                {r2Prefix}/_mpo/{mpoId}/
   planning_district:  {r2Prefix}/_planning_district/{pdId}/
   city:               {r2Prefix}/_city/{cityId}/
   county:             {r2Prefix}/{jurisdictionId}/
   ```

---

## Server-Side R2 Endpoints

**File:** `server/qdrant-proxy.js`

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/api/r2/upload-geocoded` | POST | Upload CSV via S3 SDK | API key |
| `/api/r2/worker-upload` | POST | Upload via R2 Worker | `X-Upload-Secret` header |
| `/api/r2/consolidate-inventory` | POST | Merge jurisdiction CSVs statewide | R2 Worker |
| `/api/r2/worker-status` | GET | Check R2 Worker config status | None |

### R2 Key Validation (server-side regex, line 625):
```regex
/^(?:_national\/[a-z0-9_]+\.csv|[a-z_]+\/(?:_(?:state|statewide|region|mpo|planning_district|city|town)\/(?:[a-z0-9_]+\/)?)?[a-z0-9_]+(?:\/[a-z0-9_]+)?\.csv)$/
```

Supports all tier patterns. No server-side changes needed for tier support.

---

## R2 Folder Creation Reference

### Script: `scripts/create_r2_folders.py`
### Workflow: `.github/workflows/create-r2-folders.yml`

**Execution Modes:**
| Mode | Flag | What It Creates |
|------|------|-----------------|
| All states | (default) | Complete hierarchy for all 51 states |
| Top-level only | `--top-level-only` | Meta folders, regions, MPOs, PDs (no jurisdictions) |
| Single state | `--state {prefix}` | One state only |
| Geography only | `--geography-only` | Uploads geography JSON files only |

**Data Sources for Folder Names:**
| Source | Drives |
|--------|--------|
| `states/{state}/hierarchy.json` | Region IDs, MPO/TPR IDs, PD IDs, county FIPS->name |
| `config.json` jurisdictions | Virginia jurisdiction keys (authoritative) |
| `data/{StateDOT}/source_manifest.json` | CO, MD jurisdiction keys |
| `states/geography/us_places.json` | City/town slugs for `_city/` folders |
| `states/geography/us_mpos.json` | Additional MPO entries |

**Key Functions:**
| Function | Purpose |
|----------|---------|
| `generate_all_folders()` | Generates complete folder path list (lines 367-462) |
| `county_name_to_key()` | Converts county names to R2 keys (lines 106-130) |
| `_name_to_slug()` | Converts city/place names to folder slugs |
| `upload_geography_files()` | Uploads geography JSONs to R2 (lines 593-714) |

---

## Debugging R2 Path Issues

### Check Current R2 Path in Console
```javascript
// What path would the parent app construct?
console.log('[R2 Path]', getDataFilePath());

// What tier is active?
console.log('[Tier]', jurisdictionContext.viewTier);

// What entity is selected?
console.log('[Entity]', {
  region: jurisdictionContext.tierRegion,
  mpo: jurisdictionContext.tierMpo,
  pd: jurisdictionContext.tierPlanningDistrict,
  city: jurisdictionContext.tierCity
});

// R2 prefix for current state
console.log('[R2 Prefix]', appConfig.states[getActiveStateKey()]?.r2Prefix);
```

### Verify R2 File Exists
```bash
# Using AWS CLI (configured for R2)
aws s3 ls s3://crash-lens-data/virginia/_mpo/hrtpo/ --endpoint-url https://<account>.r2.cloudflarestorage.com
```

### Common Issues
1. **404 on R2 fetch** — Folder exists but file hasn't been uploaded yet (folders are zero-byte markers)
2. **Wrong jurisdiction ID** — Check `county_name_to_key()` conversion vs `config.json` key
3. **Iframe shows wrong data** — Parent sending county path when user selected MPO/region tier
4. **Upload to wrong folder** — Check `buildR2DestinationPath()` vs `getDataFilePath()` (they should agree)
