# Plan: Scale Virginia Crash Data Pipeline to All 133 Jurisdictions

## Context

The project currently has a fully working pipeline for Henrico County that downloads Virginia crash data, filters for Henrico, validates, geocodes, generates forecasts, and uploads to Cloudflare R2 storage. All 133 Virginia jurisdictions (95 counties + 38 independent cities) are already fully defined in `config.json` with `jurisCode`, `fips`, `namePatterns`, and `bbox`. A batch workflow (`batch-all-jurisdictions.yml`) already exists but is manual-only and has gaps compared to the Henrico pipeline. The goal is to schedule automated monthly processing for all 133 jurisdictions, replicating the exact same pipeline Henrico uses, without modifying the existing Henrico pipeline.

## What Already Exists (No Changes Needed)

| Component | Status |
|-----------|--------|
| 133 Virginia jurisdictions in `config.json` | Complete (jurisCode, fips, namePatterns, bbox) |
| `download_crash_data.py` (statewide download + jurisdiction filter) | Working |
| `scripts/split_jurisdictions.py` (split statewide into per-jurisdiction CSVs) | Working |
| `validation/run_validation.py` (auto-correct + quality checks) | Working |
| `scripts/process_crash_data.py` (geocoding) | Working |
| `scripts/generate_forecast.py` (per-jurisdiction forecasts) | Working |
| `scripts/generate_aggregates.py` (statewide/region/MPO summaries) | Working |
| `.github/actions/upload-r2/action.yml` (composite upload + manifest) | Working |
| R2 naming convention: `virginia/{jurisdiction}/{filter}.csv` | Established |
| `download-data.yml` (Henrico single-jurisdiction pipeline) | **DO NOT MODIFY** |

## Gap Analysis: Batch Workflow vs Henrico Pipeline

| Feature | Henrico Pipeline | Batch Workflow | Gap? |
|---------|-----------------|----------------|------|
| Download statewide CSV | Yes | Yes | No |
| Split by jurisdiction | Inline filter | `split_jurisdictions.py` | No |
| 3 road-type variants | Yes | Yes | No |
| Validate | Yes | Yes | No |
| Geocode | Yes | Yes | No |
| Upload CSVs to R2 | Composite action (updates manifest) | Raw `aws s3 cp` (no manifest update) | **Minor** |
| Upload statewide gzip | Yes | Yes | No |
| Generate forecasts | Always runs | `skip_forecasts: true` by default | **Gap** |
| Upload forecast JSONs to R2 | Yes (3 files per jurisdiction) | **Missing entirely** | **Critical** |
| Generate aggregates | Yes | Yes | No |
| Commit geocode cache | Yes | No | **Minor** |
| Failure notifications | Email | **Missing** | **Gap** |
| Scheduled trigger | Monthly cron | Manual only | **Gap** |
| `workflow_call` support | N/A | **Missing** (needed for orchestrator) | **Gap** |

## Current Henrico Pipeline Flow (Reference)

The existing Henrico pipeline in `download-data.yml` follows this sequence:

1. **Download**: `download_crash_data.py --jurisdiction henrico --filter {countyOnly|countyPlusVDOT|allRoads}` — downloads statewide CSV from Virginia Roads, filters for Henrico, produces 3 road-type variant CSVs
2. **Save statewide**: `--save-statewide` flag saves a gzip of the full statewide CSV before jurisdiction filtering
3. **Validate**: `validation/run_validation.py --jurisdiction henrico` — auto-corrects data quality issues, flags errors
4. **Geocode**: `scripts/process_crash_data.py` — fills missing GPS coordinates using geocoding
5. **Upload CSVs to R2**: Via `.github/actions/upload-r2` composite action — uploads 3 CSVs + updates `data/r2-manifest.json`
6. **Upload statewide gzip**: `virginia/_state/statewide_all_roads.csv.gz`
7. **Generate forecasts**: `scripts/generate_forecast.py --all-road-types --jurisdiction henrico --data-dir data` — produces 3 forecast JSONs
8. **Upload forecasts to R2**: `virginia/henrico/forecasts_{county_roads|no_interstate|all_roads}.json`
9. **Generate aggregates**: `scripts/generate_aggregates.py --state virginia` — statewide/region/MPO summaries
10. **Upload aggregates**: `virginia/_statewide/`, `virginia/_region/`, `virginia/_mpo/` paths
11. **Commit metadata**: `data/r2-manifest.json`, `data/.validation/`, `data/.geocode_cache.json`

## Implementation Plan

### File 1: `.github/workflows/batch-all-jurisdictions.yml` (Modify)

**1a. Add `workflow_call` trigger** (alongside existing `workflow_dispatch`)

Add `on.workflow_call.inputs` mirroring all `workflow_dispatch` inputs so the batch workflow can be called by the new orchestrator workflow. Update all `github.event.inputs.X` references to use `inputs.X || github.event.inputs.X` pattern for dual-trigger compatibility.

**1b. Add Stage 6.5: Upload forecast JSONs to R2**

After the existing forecast generation step (Stage 6, around line 446), add a new step that:
- Iterates through all jurisdictions in the output directory
- For each jurisdiction with `forecasts_*.json` files, uploads to `virginia/{jurisdiction}/forecasts_{type}.json`
- Uses the same `aws s3 cp` pattern as Stage 5
- Only runs when `skip_forecasts != 'true'`

R2 keys to upload per jurisdiction:
```
virginia/{jurisdiction}/forecasts_county_roads.json
virginia/{jurisdiction}/forecasts_no_interstate.json
virginia/{jurisdiction}/forecasts_all_roads.json
```

**1c. Add geocode cache to commit step** (Stage 8)

Add `git add data/.geocode_cache.json` to the metadata commit step (line 523) to match Henrico pipeline behavior.

**1d. Add failure notification job**

Add a `notify-on-failure` job matching the pattern in `download-data.yml` (lines 803-832), using `dawidd6/action-send-mail@v3`.

### File 2: `.github/workflows/scheduled-va-batch.yml` (Create New)

A lightweight orchestrator workflow that triggers the batch workflow on a monthly schedule:

```yaml
name: Scheduled VA Batch (All 133 Jurisdictions)

on:
  schedule:
    # Second Monday of month at 15:00 UTC (10:00 AM ET)
    # Staggered 1 week after Henrico pipeline (first Monday 11:00 UTC)
    - cron: '0 15 8-14 * 1'
  workflow_dispatch:
    inputs:
      skip_forecasts:
        description: 'Skip forecast generation'
        default: true
        type: boolean
      jurisdictions:
        description: 'Specific jurisdictions (comma-separated, empty=all)'
        default: ''
        type: string

jobs:
  batch-virginia:
    uses: ./.github/workflows/batch-all-jurisdictions.yml
    with:
      state: virginia
      batch_size: '20'
      skip_forecasts: ${{ github.event.inputs.skip_forecasts || 'true' }}
      skip_validation: false
      skip_geocode: false
      dry_run: false
    secrets: inherit
```

### Schedule Stagger (No Conflicts)

| Workflow | Schedule | Purpose |
|----------|----------|---------|
| `download-data.yml` | 1st Monday, 11:00 UTC | Henrico only (unchanged) |
| `scheduled-va-batch.yml` | 2nd Monday, 15:00 UTC | All 133 jurisdictions |

1-week separation ensures no concurrent R2 writes or git push conflicts.

### R2 Output Per Jurisdiction (133 jurisdictions x 9 files = 1,197 files)

Each jurisdiction gets the same R2 structure as Henrico:
```
virginia/{jurisdiction}/county_roads.csv
virginia/{jurisdiction}/no_interstate.csv
virginia/{jurisdiction}/all_roads.csv
virginia/{jurisdiction}/forecasts_county_roads.json      (when forecasts enabled)
virginia/{jurisdiction}/forecasts_no_interstate.json     (when forecasts enabled)
virginia/{jurisdiction}/forecasts_all_roads.json         (when forecasts enabled)
```

Plus shared state-level files:
```
virginia/_state/statewide_all_roads.csv.gz
virginia/_statewide/aggregates.json
virginia/_statewide/county_summary.json
virginia/_region/{region_id}/aggregates.json
virginia/_mpo/{mpo_id}/aggregates.json
```

### Timing Within 6-Hour GitHub Actions Limit

| Stage | Est. Duration (133 jurisdictions) |
|-------|-----------------------------------|
| Download statewide CSV | ~5-10 min |
| Split into 133 jurisdictions | ~2-3 min |
| Validate all | ~35-65 min |
| Geocode all | ~60-120 min |
| Upload 399 CSVs to R2 | ~35-65 min |
| Upload statewide gzip | ~2-5 min |
| Generate forecasts (dry-run) | ~65 min |
| Upload forecast JSONs | ~20-30 min |
| Generate aggregates | ~10-15 min |
| **Total** | **~3.5-5.5 hours** (fits within 6h) |

If forecasts are skipped (default), total drops to ~2.5-4 hours.

## Files Modified/Created Summary

| File | Action |
|------|--------|
| `docs/PLAN_SCALING_133_VA_JURISDICTIONS.md` | **Create**: This plan document |
| `.github/workflows/batch-all-jurisdictions.yml` | **Modify**: Add `workflow_call` trigger, add forecast upload stage (6.5), add geocode cache commit, add failure notification |
| `.github/workflows/scheduled-va-batch.yml` | **Create**: Scheduled orchestrator with monthly cron |

**No changes to**: `download-data.yml`, `config.json`, `split_jurisdictions.py`, `generate_forecast.py`, `generate_aggregates.py`, `upload-to-r2.py`, `process_crash_data.py`, or any validation scripts.

## Verification

1. **Dry run**: Manually trigger `batch-all-jurisdictions.yml` with `state: virginia`, `dry_run: true` — verify 133 jurisdictions detected, split counts reported
2. **Small subset**: Run with `jurisdictions: "henrico,chesterfield,fairfax_county"`, `dry_run: false`, `skip_forecasts: true` — verify 3x3=9 CSVs uploaded to R2
3. **Compare Henrico output**: Download `virginia/henrico/county_roads.csv` from R2 and verify it matches the output from the regular Henrico pipeline
4. **Full batch**: Run all 133 with `skip_forecasts: true` — verify 399 CSVs uploaded, aggregates generated
5. **Full with forecasts**: Run all 133 with `skip_forecasts: false` — verify 399 forecast JSONs uploaded
6. **Scheduled trigger**: Verify the cron fires on the 2nd Monday of the month

## All 133 Virginia Jurisdictions

### Counties (95)
accomack, albemarle, alleghany, amelia, amherst, appomattox, arlington, augusta, bath, bedford_county, bland, botetourt, brunswick, buchanan, buckingham, campbell, caroline, carroll, charles_city, charlotte, chesterfield, clarke, craig, culpeper, cumberland, dickenson, dinwiddie, essex, fairfax_county, fauquier, floyd, fluvanna, franklin_county, frederick, giles, gloucester, goochland, grayson, greene, greensville, halifax, hanover, henrico, henry, highland, isle_of_wight, james_city, king_and_queen, king_george, king_william, lancaster, lee, loudoun, louisa, lunenburg, madison, mathews, mecklenburg, middlesex, montgomery, nelson, new_kent, northampton, northumberland, nottoway, orange, page, patrick, pittsylvania, powhatan, prince_edward, prince_george, prince_william, pulaski, rappahannock, richmond_county, roanoke_county, rockbridge, rockingham, russell, scott, shenandoah, smyth, southampton, spotsylvania, stafford, surry, sussex, tazewell, warren, washington, westmoreland, wise, wythe, york

### Independent Cities (38)
alexandria, bristol, buena_vista, charlottesville, chesapeake, colonial_heights, covington, danville, emporia, fairfax_city, falls_church, franklin_city, fredericksburg, galax, hampton, harrisonburg, hopewell, lexington, lynchburg, manassas, manassas_park, martinsville, newport_news, norfolk, norton, petersburg, poquoson, portsmouth, radford, richmond_city, roanoke_city, salem, staunton, suffolk, virginia_beach, waynesboro, williamsburg, winchester
