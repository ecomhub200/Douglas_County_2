# Claude Code Prompt: Fix Virginia 4-Way Road Type Split & R2 Upload Failures

## Context

The Virginia crash data pipeline needs to produce **4 road-type CSV files** per jurisdiction (not 3). The 4 types are split based on the **Ownership** column in the source data, which has these values:

| Ownership Value | Target File |
|---|---|
| `1. State Hwy Agency` | Part of `all_roads` and `no_interstate` |
| `2. County Hwy Agency` | `{jurisdiction}_county_roads.csv` |
| `3. City or Town Hwy Agency` | `{jurisdiction}_city_roads.csv` |
| `4. Federal Roads` | Part of `all_roads` and `no_interstate` |

The 4 output files per jurisdiction should be:
1. `{jurisdiction}_county_roads.csv` — Ownership = "2. County Hwy Agency"
2. `{jurisdiction}_city_roads.csv` — Ownership = "3. City or Town Hwy Agency"
3. `{jurisdiction}_no_interstate.csv` — Everything except interstate (Functional Class ≠ "1-Interstate (A,1)")
4. `{jurisdiction}_all_roads.csv` — All records unfiltered

The pipeline is also **failing to upload to Cloudflare R2 storage**. Debug and fix this.

---

## What's Already Done (DO NOT REDO)

The following files are already correctly configured for 4-way splitting:

- **`states/virginia/config.json`** — `roadSystems.splitConfig` already has `countyRoads` (method: ownership, includeValues: ["2. County Hwy Agency"]) and `cityRoads` (method: ownership, includeValues: ["3. City or Town Hwy Agency"])
- **`scripts/split_road_type.py`** — Already supports `city_roads` via `filter_city_roads()` which reads `splitConfig.cityRoads`
- **`scripts/split_jurisdictions.py`** — Already iterates over `['county_roads', 'city_roads', 'no_interstate', 'all_roads']` in both `split_state()` and `build_r2_upload_manifest()`
- **`pipeline.yml`** Stage 2 already calls `split_road_type.py` and Stage 5b already iterates over all 4 road types for forecast uploads

---

## Issues to Investigate and Fix

### Issue 1: Download workflow filter default is wrong
**File:** `.github/workflows/download-virginia.yml` (lines 79-87)

The `filter` input defaults to `countyOnly`, which means statewide downloads only get county roads. The pipeline then can't split into city_roads because that data was never downloaded.

**Fix:** Change the default filter to `allRoads` so the statewide CSV contains ALL ownership types. The 4-way split happens downstream in the pipeline, not at download time.

```yaml
filter:
  description: 'Road type filter'
  required: true
  type: choice
  default: 'allRoads'   # <-- Change from 'countyOnly' to 'allRoads'
  options:
    - countyOnly
    - cityOnly          # <-- Add this new option
    - countyPlusVDOT
    - allRoads
```

### Issue 2: download_crash_data.py doesn't accept `cityOnly` filter
**File:** `download_crash_data.py` (line 768)

The argparse choices are hardcoded to `['countyOnly', 'countyPlusVDOT', 'allRoads']`. Add `cityOnly`.

Also add a corresponding filter profile in `config.json` → `filterProfiles` at the root level (currently only exists in `states/virginia/config.json`).

### Issue 3: R2 Upload Failures — Debug the Pipeline

The pipeline (`pipeline.yml`) Stage 4 uploads to R2. Investigate:

1. **Check GitHub Actions secrets** — Are these secrets configured?
   - `CF_R2_ACCESS_KEY_ID`
   - `CF_R2_SECRET_ACCESS_KEY`
   - `CF_ACCOUNT_ID`

2. **Check the R2 bucket** — Does `crash-lens-data` bucket exist? Check using the Cloudflare MCP tools:
   - Use `r2_buckets_list` to verify the bucket exists
   - Try `r2_bucket_get` for `crash-lens-data`

3. **Check the upload manifest generation** — In Stage 4, the pipeline runs:
   ```bash
   python scripts/split_jurisdictions.py --state "$STATE" --r2-manifest --r2-prefix "$R2_PREFIX" --output-dir "$DATA_DIR"
   ```
   The `--state` flag in `split_jurisdictions.py` only accepts `['virginia', 'colorado']` (line 438). If other states trigger this, it will fail.

4. **Check that split CSVs actually exist** before upload — If Stage 1 or Stage 2 fails silently (the `|| { echo "WARNING..." }` pattern), Stage 4 will find no files to upload.

5. **Check the R2 endpoint URL format** — The pipeline uses:
   ```
   https://${CF_ACCOUNT_ID}.r2.cloudflarestorage.com
   ```
   Verify this is the correct format for the Cloudflare account.

6. **Review recent GitHub Actions run logs** — Look at the actual error messages from failed runs. Common failure patterns:
   - `AccessDenied` → Secrets wrong or R2 API token lacks permissions
   - `NoSuchBucket` → Bucket doesn't exist or wrong name
   - `InvalidAccessKeyId` → CF_R2_ACCESS_KEY_ID is wrong
   - Connection timeout → CF_ACCOUNT_ID might be wrong (wrong endpoint URL)

### Issue 4: The download-virginia.yml statewide CSV path
**File:** `.github/workflows/download-virginia.yml` (line 171)

When `MODE=statewide`, the CSV path is hardcoded to `virginia_statewide_all_roads.csv`. But if the filter is `countyOnly`, the content won't match the filename. This is misleading and can cause the pipeline to process partial data as if it were all-roads data.

### Issue 5: Verify the Ownership column survives download + standardization
**File:** `download_crash_data.py` → `standardize_columns()` (line 686)

The standardization maps `'OWNERSHIP': 'Ownership'`. Verify that the downloaded data from ArcGIS API uses `OWNERSHIP` as the column name (API format) and that the CSV download uses `Ownership` directly. Both should map correctly to `Ownership` after standardization, which is what `split_road_type.py` expects.

---

## Testing Checklist

After making changes:

- [ ] Run download with `--filter allRoads` for a single jurisdiction (e.g., henrico) and verify the output CSV contains all 4 Ownership values
- [ ] Run `split_road_type.py --state virginia --jurisdiction henrico --data-dir data` and verify it produces 4 CSV files
- [ ] Verify `county_roads.csv` only has "2. County Hwy Agency" in Ownership column
- [ ] Verify `city_roads.csv` only has "3. City or Town Hwy Agency" in Ownership column
- [ ] Verify `no_interstate.csv` has no rows where Functional Class = "1-Interstate (A,1)"
- [ ] Verify `all_roads.csv` has all records
- [ ] Test R2 upload manually with `aws s3 cp` using the endpoint URL and credentials
- [ ] Run the full pipeline for one jurisdiction and confirm all 4 CSVs appear in R2

---

## Files to Modify

| File | Change |
|---|---|
| `.github/workflows/download-virginia.yml` | Add `cityOnly` filter option, change default to `allRoads` |
| `download_crash_data.py` | Add `cityOnly` to argparse choices (line 768), add cityOnly filter logic |
| `config.json` | Add `cityOnly` to root-level `filterProfiles` |
| `scripts/split_jurisdictions.py` | Expand `--state` choices beyond `['virginia', 'colorado']` or remove the restriction |

---

## Files to Read First (Before Making Any Changes)

1. `states/virginia/config.json` — The splitConfig that drives the 4-way split
2. `.github/workflows/download-virginia.yml` — The download workflow
3. `.github/workflows/pipeline.yml` — The processing pipeline
4. `scripts/split_road_type.py` — Road type splitting logic
5. `scripts/split_jurisdictions.py` — Jurisdiction splitting + R2 manifest
6. `download_crash_data.py` — The download script
7. `config.json` → `filterProfiles` section (around line 4560)
8. Recent GitHub Actions logs for failed runs (check Actions tab)
