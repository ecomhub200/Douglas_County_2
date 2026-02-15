# R2 Storage & Pipeline Architecture for Multi-Tier Views

## Context

The Crash Lens app supports 7 view tiers: **Federal > State > Region > MPO > County > City > Corridor**.
This plan covers how data flows from the CI/CD pipeline into R2 storage and back to the
frontend app for each tier. It is designed to be **reusable for any new state** added to the system.

## Approach

1. **Bottom-up**: Aggregate existing county-level CSVs → form Region and MPO datasets
2. **Top-down**: Download a separate copy of the statewide dataset → save as gzip in R2
3. **County data**: Untouched — existing pipeline continues as-is
4. **Federal**: Cross-state aggregation of statewide aggregates

**Key constraint**: Use the existing pipeline architecture. Inject statewide download
into the right stage rather than creating a separate pipeline.

---

## Adding a New State — Checklist

To onboard a new state (e.g., Texas), follow these steps:

### 1. State Configuration Files

```
states/{state_key}/
  config.json           # Column mappings, EPDO weights, state metadata
  hierarchy.json        # Regions, MPOs, corridors, county memberships
```

**`config.json`** must include:
```json
{
  "state": { "abbreviation": "TX", "name": "Texas", "fips": "48" },
  "columnMapping": { ... },
  "epdoWeights": { "K": 462, "A": 62, "B": 12, "C": 5, "O": 1 }
}
```

**`hierarchy.json`** must include:
```json
{
  "state": { "abbreviation": "TX", "name": "Texas" },
  "regions": [ { "id": "region_1", "name": "...", "counties": ["county_a", ...] } ],
  "mpos": [ { "id": "mpo_1", "name": "...", "counties": ["county_a", ...] } ]
}
```

### 2. State Adapter (if non-Virginia format)

If the state's raw CSV format differs from Virginia's, create a normalizer in
`scripts/state_adapter.py` (pattern: `ColoradoNormalizer`). The normalizer maps
the state's columns to the standard format used by the app.

### 3. Download Script

Create `download_{state}_crash_data.py` following the pattern of:
- `download_crash_data.py` (Virginia — ArcGIS API)
- `download_cdot_crash_data.py` (Colorado — Hyland OnBase)

Must support:
- `--save-statewide` or `--save-statewide-gzip` flag
- Calls `scripts/process_crash_data.py` with `--skip-split` for statewide processing
- Outputs `{state}_statewide_all_roads.csv.gz`

### 4. GitHub Actions Workflow

Create `.github/workflows/download-{state}-crash-data.yml` following the pattern.
Required stages:

```
Stage 1:    Download raw data from state source
Stage 1.5:  Assemble statewide gzip (merge → convert → validate → geocode → gzip)
Stage 2:    Upload raw/county CSVs to R2
Stage 2.5:  Upload statewide gzip to R2
Stage 3-6:  Process → Forecast → Upload (same as existing)
Stage 6.5:  Generate & upload region/MPO/federal aggregates
Stage 7:    Commit metadata to Git
```

**Critical patterns** (learned from bug fixes):
- Use `[ -f "$GZ" ]` runtime check for gzip existence, NOT `hashFiles()`
- Use `--output-dir "data/$STATE"` for aggregate generation (not `--output-dir data`)
- Pass `uncompressed_size` in `files_json` for gzip uploads

### 5. Frontend Registration

In `config.json`, add the state to the `states` registry:
```json
{
  "texas": {
    "fips": "48",
    "name": "Texas",
    "abbreviation": "TX",
    "dotName": "TxDOT",
    "defaultJurisdiction": "harris",
    "dataDir": "TXDOT",
    "r2Prefix": "texas"
  }
}
```

### 6. R2 Storage

After the first pipeline run, the state will have:
```
crash-lens-data/
  texas/
    _state/statewide_all_roads.csv.gz    # Full state gzip
    _statewide/aggregates.json           # Bottom-up aggregates
    _statewide/county_summary.json
    _region/{id}/aggregates.json         # Per-region aggregates
    _mpo/{id}/aggregates.json            # Per-MPO aggregates
    {jurisdiction}/all_roads.csv         # County-level data
```

---

## Processing Requirements Per State

### Generic — Full Pipeline

States with non-Virginia CSV formats require the full pipeline:

| Stage | What It Does | Applied to Statewide? |
|-------|-------------|----------------------|
| **MERGE** | Combine per-year/per-source CSVs into single file | Yes — deduplicates by unique crash ID |
| **CONVERT** | State normalizer transforms columns → standard format | **Yes — REQUIRED** |
| **VALIDATE** | Quality checks, bounds validation, auto-correction | **Yes — REQUIRED** |
| **GEOCODE** | Fill missing GPS coordinates | **Yes** (timeout: 1800s) |
| **SPLIT** | Create road-type variants | Skipped — statewide is single `all_roads` |
| **GZIP** | Compress for R2 storage | Yes |

**Implementation**: `download_{state}_crash_data.py --save-statewide-gzip` calls
`scripts/process_crash_data.py` with `--skip-split` to run the full pipeline.

### Virginia — Exception (Standardize Only)

Virginia data from `virginiaroads.org` is **already in the standard format**.
Only column renaming via `standardize_columns()` is needed before gzipping.

---

## Frontend: R2 → App Data Flow

### How the App Resolves R2 URLs

`resolveDataUrl(localPath)` uses 3 strategies in order:

| Strategy | Pattern | Example |
|----------|---------|---------|
| **1. Manifest lookup** | Exact match in `r2-manifest.json` `localPathMapping` | `data/henrico_all_roads.csv` → `virginia/henrico/all_roads.csv` |
| **2. Dynamic construction** | `{r2Prefix}/{jurisdiction}/{filter}.{ext}` | `data/CDOT/douglas_all_roads.csv` → `colorado/douglas/all_roads.csv` |
| **3. Tier path passthrough** | Direct R2 key for `_state/`, `_statewide/`, `_region/`, `_mpo/`, `_federal/` paths | `colorado/_state/statewide_all_roads.csv.gz` → R2 URL directly |

### How the App Loads Data Per Tier

| Tier | Data Source | Loading Mechanism |
|------|-------------|-------------------|
| **County** | `{state}/{jurisdiction}/all_roads.csv` | `autoLoadCrashData()` → `fetch(resolveDataUrl(path))` → `Papa.parse()` → `processRow()` |
| **State** | Aggregates: `{state}/_statewide/aggregates.json` | `AggregateLoader.loadStatewide(stateKey)` → `_fetch()` → JSON |
| **State** | Raw CSV: `{state}/_state/statewide_all_roads.csv.gz` | `AggregateLoader.loadStatewideCSV(stateKey)` → `fetch()` → browser auto-decompresses gzip → `Papa.parse()` |
| **Region** | `{state}/_region/{id}/aggregates.json` | `AggregateLoader.loadRegion(stateKey, regionId)` |
| **MPO** | `{state}/_mpo/{id}/aggregates.json` | `AggregateLoader.loadMPO(stateKey, mpoId)` |
| **Federal** | `_federal/aggregates.json` | `AggregateLoader.loadNational()` |

### Gzip Transparent Decompression

Files uploaded to R2 with `Content-Encoding: gzip` header are **automatically decompressed
by the browser** when fetched via `fetch()`. No frontend decompression library (like pako) is needed.

```
R2 stores: statewide_all_roads.csv.gz (8 MB compressed)
Browser fetches URL → R2 responds with Content-Encoding: gzip
fetch().text() → returns full decompressed CSV text (50 MB)
Papa.parse(csvText) → processes rows normally
```

### Key Frontend Functions

| Function | Purpose | File |
|----------|---------|------|
| `resolveDataUrl(localPath)` | Maps local/tier paths to R2 URLs | `app/index.html` |
| `getDataFilePath()` | Returns the data path for the current tier + jurisdiction | `app/index.html` |
| `AggregateLoader.loadStatewideCSV(stateKey)` | Fetches + caches statewide gzip CSV from R2 | `app/index.html` |
| `loadStatewideCSVForTier(stateKey)` | Parses statewide CSV into `crashState` for tabs | `app/index.html` |
| `handleTierChange(tier)` | Orchestrates tier switch: boundary, aggregates, CSV | `app/index.html` |

---

## Current Pipeline Stages (Reference)

### Virginia (`download-data.yml`)

```
Stage 0:   Pre-flight (determine jurisdiction, health check)
Stage 1:   Download 3 road-type CSVs per county
Stage 1.5: Save statewide copy as gzip (NEW — standardize_columns only)
Stage 2:   Validate & Auto-Correct county data
Stage 3:   Geocode county data
Stage 4:   Upload county CSVs to R2
Stage 4.5: Check gzip exists (runtime) → Upload statewide gzip to R2 (NEW)
Stage 5:   Generate Forecasts
Stage 6:   Upload Forecasts to R2
Stage 6.5: Generate & upload region/MPO/federal aggregates (NEW)
Stage 7:   Commit metadata to Git
```

### Colorado (`download-cdot-crash-data.yml` → `process-cdot-data.yml`)

```
Stage 1:    Download per-year Excel from CDOT OnBase
Stage 1.5:  Assemble statewide: merge → CONVERT → VALIDATE → GEOCODE → gzip (NEW)
Stage 2a:   Upload raw year CSVs to R2
Stage 2a.5: Check gzip exists (runtime) → Upload statewide gzip to R2 (NEW)
Stage 2b:   Commit metadata
            ─── auto-triggers process-cdot-data.yml ───
Stage 3:    Process county data (Merge → Convert → Validate → Geocode → Split)
Stage 4:    Upload processed county CSVs to R2
Stage 5:    Generate Forecasts
Stage 6:    Upload Forecasts
Stage 6.5:  Generate & upload region/MPO/federal aggregates (NEW)
Stage 7:    Commit metadata
```

---

## R2 Storage Layout

```
crash-lens-data/
  _federal/                                    # Cross-state aggregation
    aggregates.json                            #   national totals (sum of all states)
    state_summary.json                         #   per-state ranking by EPDO

  {state}/                                     # e.g., colorado/, virginia/, texas/
    _state/                                    # Full state dataset (gzipped)
      statewide_all_roads.csv.gz               #   Served with Content-Encoding: gzip
                                               #   Browser auto-decompresses on fetch

    _statewide/                                # Statewide aggregate JSONs
      aggregates.json                          #   (built bottom-up from county CSVs)
      county_summary.json                      #   per-county ranking by EPDO
      mpo_summary.json                         #   per-MPO ranking

    _region/{region_id}/                       # Region aggregates (JSON only)
      aggregates.json                          #   (built from member county CSVs)
      hotspots.json

    _mpo/{mpo_id}/                             # MPO aggregates (JSON only)
      aggregates.json                          #   (built from member county CSVs)
      hotspots.json

    {jurisdiction}/                            # UNCHANGED: Existing county data
      all_roads.csv
      county_roads.csv
      no_interstate.csv
      standardized.csv
      forecasts_*.json
```

---

## Data Flow Diagram

```
  EXISTING COUNTY PIPELINE (untouched)        STATEWIDE (new, parallel path)
  ═══════════════════════════                 ════════════════════════════════

  download_{state}_crash_data.py              Same download call
  --jurisdiction {county}                     but save pre-filter DataFrame
        │                                           │
        ▼                                           ▼
  County CSVs (filtered)                      Full State CSV (unfiltered)
        │                                           │
        ▼                                     ┌─────▼──────────────────────┐
  Validate → Geocode → R2                     │ Non-VA: CONVERT+VALIDATE   │
        │                                     │     VA: standardize only   │
        ▼                                     └─────┬──────────────────────┘
  generate_aggregates.py                            │
  --state {state} --data-dir {dir}                  ▼
  --output-dir data/{state}                   gzip → R2: {state}/_state/
        │                                     statewide_all_roads.csv.gz
        ├──► {state}/_statewide/aggregates.json
        ├──► {state}/_region/{id}/aggregates.json        FRONTEND
        ├──► {state}/_mpo/{id}/aggregates.json     ══════════════════
        │                                     AggregateLoader._fetch(path)
        ▼                                       → loads JSON aggregates
  _federal/aggregates.json                    AggregateLoader.loadStatewideCSV()
  (combine all state aggregates)                → fetch gzip CSV from R2
                                                → browser auto-decompresses
                                                → Papa.parse → crashState
```

---

## Files Changed

| File | Change | Stage |
|------|--------|-------|
| `download_crash_data.py` | `--save-statewide` flag; standardize + gzip | 1.5 |
| `download_cdot_crash_data.py` | `--save-statewide-gzip` flag; merge + convert + validate + geocode + gzip | 1.5 |
| `.github/actions/upload-r2/action.yml` | Gzip Content-Encoding support | 4.5 |
| `.github/workflows/download-data.yml` | Stage 4.5 + 6.5 injection | 4.5, 6.5 |
| `.github/workflows/download-cdot-crash-data.yml` | Stage 2a.5 injection | 2a.5 |
| `.github/workflows/process-cdot-data.yml` | Stage 6.5 injection | 6.5 |
| `scripts/generate_aggregates.py` | `--federal` flag; dynamic state config lookup | 6.5 |
| `data/r2-manifest.json` | Version 3 with gzip metadata | 7 |
| `app/index.html` | `AggregateLoader.loadStatewideCSV()`, `resolveDataUrl()` Strategy 3, `loadStatewideCSVForTier()`, tier-aware `getDataFilePath()` | Frontend |

---

## Bug Fixes Applied (Post-Review)

| # | Severity | Bug | Fix |
|---|----------|-----|-----|
| 1 | **CRITICAL** | `hashFiles()` evaluated at parse time — never matches runtime-generated gzip files. Stage 4.5 (VA) and 2a.5 (CO) **never execute**. | Replaced with runtime `[ -f "$GZ" ]` check via step output. |
| 2 | **CRITICAL** | `--output-dir data` causes aggregates to write to `data/_statewide/` but upload manifest looks for `data/{state}/_statewide/`. **Aggregates never uploaded.** | Changed to `--output-dir data/$STATE` in both workflows. |
| 3 | **CRITICAL** | Frontend had no code to fetch statewide gzip CSV from R2 — `resolveDataUrl()` couldn't handle `_state/` paths, no CSV loader existed. | Added `AggregateLoader.loadStatewideCSV()`, `resolveDataUrl()` Strategy 3, `loadStatewideCSVForTier()`, tier-aware `getDataFilePath()`. |
| 4 | **MODERATE** | `uncompressed_size` never passed to upload-r2 action — manifest lacks gzip metadata. | Added gzip footer read to extract uncompressed size; passed in `files_json`. |
| 5 | **MODERATE** | `_get_col_mapping()` had dead code (`config_path` unused) and was hardcoded to only VA/CO. | Rewrote to scan `states/` directory dynamically. |
| 6 | **USER-REQ** | Colorado statewide skipped geocoding (`--skip-geocode`). | Removed `--skip-geocode`; increased timeout to 1800s. |

---

## Decisions

1. **Federal view**: Cross-state aggregation from statewide aggregate JSONs
2. **Region/MPO storage**: Aggregate JSONs only — no raw CSV subsets
3. **Injection point**: Stage 1.5 (post-download, pre-validate) for statewide save
4. **Non-VA processing**: Full CONVERT + VALIDATE + GEOCODE pipeline (same as county)
5. **VA processing**: standardize_columns() only (already in standard format)
6. **No new scripts**: Uses existing download + process + aggregate scripts with new flags
7. **Gzip serving**: `Content-Encoding: gzip` header on R2 → browser auto-decompresses
8. **Frontend tier-aware**: `getDataFilePath()` returns R2 tier paths for state view
