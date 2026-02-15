# R2 Storage & Pipeline Architecture for Multi-Tier Views

## Context

The Crash Lens app supports 5 view tiers: **Federal > State > Region > MPO > County**.
Currently only county-level data exists in R2 (Douglas for CO, Henrico for VA).
The higher tiers (State, Region, MPO, Federal) need data to function.

## Approach

1. **Bottom-up**: Aggregate existing county-level CSVs → form Region and MPO datasets
2. **Top-down**: Download a separate copy of the statewide dataset → save as gzip in R2
3. **County data**: Untouched — existing pipeline continues as-is
4. **Federal**: Cross-state aggregation of statewide aggregates

**Key constraint**: Use the existing pipeline architecture. Inject statewide download
into the right stage rather than creating a separate pipeline.

---

## Processing Requirements Per State

### Colorado (CDOT) — Full Pipeline Required

Colorado statewide data goes through **the same convert + validate pipeline** as county data:

| Stage | What It Does | Applied to Statewide? |
|-------|-------------|----------------------|
| **MERGE** | Combine per-year CSVs into single file | Yes — merges all years, deduplicates by CUID |
| **CONVERT** | `ColoradoNormalizer` transforms CDOT columns → Virginia-compatible format | **Yes — REQUIRED** (severity, collision types, weather, route names, etc.) |
| **VALIDATE** | Quality checks, bounds validation, duplicate detection, auto-correction | **Yes — REQUIRED** |
| **GEOCODE** | Fill missing GPS coordinates | **Yes** — runs on statewide data (timeout raised to 1800s) |
| **SPLIT** | Create road-type variants (all_roads, county_roads, no_interstate) | Skipped — statewide is kept as single `all_roads` |
| **GZIP** | Compress for R2 storage | Yes |

**Implementation**: `download_cdot_crash_data.py --save-statewide-gzip` calls
`scripts/process_crash_data.py` with `--skip-split` to run
CONVERT + VALIDATE + GEOCODE on the merged statewide CSV before gzipping.

### Virginia — Standardize Only (No Conversion Needed)

Virginia data from `virginiaroads.org` is **already in the standard format**.
Only column renaming is needed:

| Stage | What It Does | Applied to Statewide? |
|-------|-------------|----------------------|
| **DOWNLOAD** | Fetch full statewide CSV from Virginia Roads fallback URL | Yes — data already in memory |
| **STANDARDIZE** | `standardize_columns()` — rename raw column names to standard names | Yes |
| **CONVERT** | State format → Virginia format | **SKIP** — already Virginia format |
| **VALIDATE** | Quality checks | Not applied (Virginia data is pre-validated by VDOT) |
| **GEOCODE** | Fill missing GPS | Not applied |
| **GZIP** | Compress for R2 storage | Yes |

**Implementation**: `download_crash_data.py --save-statewide` calls
`standardize_columns()` on the full DataFrame before filtering, then gzips.

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
Stage 4.5: Upload statewide gzip to R2 (NEW)
Stage 5:   Generate Forecasts
Stage 6:   Upload Forecasts to R2
Stage 6.5: Generate & upload region/MPO/federal aggregates (NEW)
Stage 7:   Commit metadata to Git
```

### Colorado (`download-cdot-crash-data.yml` → `process-cdot-data.yml`)

```
Stage 1:    Download per-year Excel from CDOT OnBase
Stage 1.5:  Assemble statewide: merge → CONVERT → VALIDATE → gzip (NEW)
Stage 2a:   Upload raw year CSVs to R2
Stage 2a.5: Upload statewide gzip to R2 (NEW)
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

  {state}/
    _state/                                    # Full state dataset (gzipped)
      statewide_all_roads.csv.gz               #   CO: ~8-15MB, VA: ~30-50MB
                                               #   CO: converted + validated
                                               #   VA: standardized columns only

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
      forecasts_*.json
```

---

## Data Flow Diagram

```
  EXISTING COUNTY PIPELINE (untouched)        STATEWIDE (new, parallel path)
  ═══════════════════════════                 ════════════════════════════════

  download_crash_data.py                      Same download call
  --jurisdiction henrico                      but save pre-filter DataFrame
        │                                           │
        ▼                                           ▼
  County CSVs (filtered)                      Full State CSV (unfiltered)
        │                                           │
        ▼                                     ┌─────▼─────────────────┐
  Validate → Geocode → R2                     │ CO: CONVERT+VALIDATE  │
        │                                     │ VA: standardize only  │
        ▼                                     └─────┬─────────────────┘
  generate_aggregates.py                            │
  reads ALL county CSVs in R2                       ▼
        │                                     gzip → R2: {state}/_state/
        ├──► _statewide/aggregates.json       statewide_all_roads.csv.gz
        ├──► _region/{id}/aggregates.json
        ├──► _mpo/{id}/aggregates.json
        │
        ▼
  _federal/aggregates.json (combine all state aggregates)
```

---

## Files Changed

| File | Change | Stage |
|------|--------|-------|
| `download_crash_data.py` | `--save-statewide` flag; standardize + gzip | 1.5 |
| `download_cdot_crash_data.py` | `--save-statewide-gzip` flag; merge + **convert + validate** + gzip | 1.5 |
| `.github/actions/upload-r2/action.yml` | Gzip Content-Encoding support | 4.5 |
| `.github/workflows/download-data.yml` | Stage 4.5 + 6.5 injection | 4.5, 6.5 |
| `.github/workflows/download-cdot-crash-data.yml` | Stage 2a.5 injection | 2a.5 |
| `.github/workflows/process-cdot-data.yml` | Stage 6.5 injection | 6.5 |
| `scripts/generate_aggregates.py` | `--federal` flag for cross-state aggregation | 6.5 |
| `data/r2-manifest.json` | Version 3 with gzip metadata | 7 |

---

## Colorado Statewide Processing Detail

The `--save-statewide-gzip` flag in `download_cdot_crash_data.py` performs:

```
1. MERGE: Concatenate all per-year CSVs (2019-2024)
2. DEDUP: Remove duplicate CUIDs (keep first occurrence)
3. CONVERT: Call process_crash_data.py with:
     - ColoradoNormalizer maps CDOT columns → Virginia-compatible format
     - Severity derived from injury columns (Injury 04/03/02/01/00 → K/A/B/C/O)
     - Collision types mapped (MHE → VDOT numbered format)
     - Weather/Light/Surface mapped to VDOT format
     - Route names built from System Code + Rd_Number
     - Boolean flags derived (ped, bike, alcohol, speed, etc.)
4. VALIDATE: Data quality checks, bounds validation, auto-correction
5. GZIP: Compress standardized CSV (6x-8x compression ratio)
6. UPLOAD: R2 at colorado/_state/statewide_all_roads.csv.gz
```

**Geocoding runs** on statewide data with a 1800s timeout (30 min). The geocode
cache from county-level runs will be reused, so only new locations need API calls.

---

## Bug Fixes Applied (Post-Review)

| # | Severity | Bug | Fix |
|---|----------|-----|-----|
| 1 | **CRITICAL** | `hashFiles()` evaluated at parse time — never matches runtime-generated gzip files. Stage 4.5 (VA) and 2a.5 (CO) **never execute**. | Replaced with runtime `[ -f "$GZ" ]` check via step output. |
| 2 | **CRITICAL** | `--output-dir data` causes aggregates to write to `data/_statewide/` but upload manifest looks for `data/{state}/_statewide/`. **Aggregates never uploaded.** | Changed to `--output-dir data/$STATE` in both workflows. |
| 3 | **MODERATE** | `uncompressed_size` never passed to upload-r2 action — manifest lacks gzip metadata. | Added gzip footer read to extract uncompressed size; passed in `files_json`. |
| 4 | **MODERATE** | `_get_col_mapping()` had dead code (`config_path` unused) and was hardcoded to only VA/CO. | Rewrote to scan `states/` directory dynamically. |
| 5 | **USER-REQ** | Colorado statewide skipped geocoding (`--skip-geocode`). | Removed `--skip-geocode`; increased timeout to 1800s. |

---

## Decisions

1. **Federal view**: Cross-state aggregation from statewide aggregate JSONs
2. **Region/MPO storage**: Aggregate JSONs only — no raw CSV subsets
3. **Injection point**: Stage 1.5 (post-download, pre-validate) for statewide save
4. **CO processing**: Full CONVERT + VALIDATE pipeline (same as county)
5. **VA processing**: standardize_columns() only (already in standard format)
6. **No new scripts**: Uses existing download + process + aggregate scripts with new flags
