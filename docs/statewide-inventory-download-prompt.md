# Claude Code Prompt: Statewide Inventory Download & R2 Consolidation Worker

## Overview

Two related enhancements to the Traffic Inventory system:

1. **Statewide Download Button** — A new button in `app/traffic-inventory.html` that loops through ALL jurisdictions in a state and downloads inventory data for each one, uploading each to R2 automatically.
2. **R2 Consolidation Worker** — A Cloudflare R2 Worker (or server-side endpoint) that merges all individual jurisdiction `traffic-inventory.csv` files into a single statewide `traffic-inventory.csv` and stores it in the state's `_statewide/` folder. It must also incorporate edits from the Inventory Manager's ledger files.

---

## PART 1: Statewide Download Button

### Context — Current System (DO NOT MODIFY)

The current single-jurisdiction download flow works correctly. Do not change it:

- **File**: `app/traffic-inventory.html`
- **Jurisdiction data**: `JURISDICTIONS` object (line 759), populated dynamically from the parent app via `postMessage` with type `ti-set-jurisdictions` (line 886)
- **Each jurisdiction** has: `name`, `state`, `folder`, `bbox`, `fips`, `type`, `mapCenter`, `mapZoom`
- **Download function**: `startDownload()` (line 1102) — fetches Mapillary map features tile-by-tile for `currentJurisdiction`
- **R2 upload**: `uploadToR2()` (line 583) — generates CSV from `allFeatures`, uploads to `{state}/{folder}/traffic-inventory.csv` via `POST /api/r2/worker-upload`
- **Auto-upload**: After download completes, if R2 is configured, auto-uploads (line 1144-1147)
- **R2 path pattern**: `{currentJurisdiction.state}/{currentJurisdiction.folder}/traffic-inventory.csv`
  - Example: `virginia/arlington_county/traffic-inventory.csv`

### Requirements — Statewide Download Button

Add a **"Statewide Download"** button to the UI in `app/traffic-inventory.html` with these behaviors:

#### UI Elements

1. **Checkbox** labeled something like: _"⚠️ I understand this will download inventory data for ALL jurisdictions in the state. This may take a very long time (hours). Keep this tab open — you can use other browser tabs meanwhile."_
2. **"Statewide Download" button** — disabled by default; only enabled when the checkbox is checked AND R2 is configured AND the `JURISDICTIONS` object is populated
3. **Progress display** — show which jurisdiction is currently being processed (e.g., "Downloading 14 of 134: Fairfax County") with an overall progress bar
4. **Per-jurisdiction status log** — show success/failure for each county as it completes
5. **Cancel button** — allow the user to stop the statewide download at any point

#### Logic

1. When clicked, collect all jurisdiction keys from the `JURISDICTIONS` object
2. Loop through each jurisdiction sequentially (one at a time to avoid API rate limits):
   a. Set `currentJurisdiction` and `currentJurisdictionKey` to the current iteration's jurisdiction
   b. Call the existing `startDownload()` logic (or replicate its core logic) for that jurisdiction
   c. After download completes for that jurisdiction, call `uploadToR2()` to push the CSV to R2
   d. Log success/failure, update progress, move to next jurisdiction
3. After ALL jurisdictions complete, trigger the R2 consolidation (Part 2) to merge all individual files into the statewide file
4. Handle errors gracefully — if one jurisdiction fails, log the error and continue to the next one. At the end, show a summary of successes and failures.

#### Important Implementation Notes

- **DO NOT modify the existing `startDownload()` or `uploadToR2()` functions** — create new wrapper functions for the statewide flow
- The statewide download should reuse the same Mapillary API token, tile generation, and feature fetching logic
- Each jurisdiction's `allFeatures` array must be reset before starting the next jurisdiction
- The R2 key for each jurisdiction follows the existing pattern: `{jurisdiction.state}/{jurisdiction.folder}/traffic-inventory.csv`
- Add a `isStatewideDownloading` flag to prevent conflicts with single-jurisdiction downloads
- Consider adding a brief delay (e.g., 2-5 seconds) between jurisdictions to be kind to the Mapillary API
- For Virginia, there are 134 counties/cities — this will take significant time. The UI must clearly communicate this.

---

## PART 2: R2 Consolidation — Statewide Traffic Inventory Merge

### Context — Current R2 Storage Structure

After downloads, individual jurisdiction CSV files are stored in R2 at:
```
{state}/{jurisdiction_folder}/traffic-inventory.csv
```

Example for Virginia:
```
virginia/arlington_county/traffic-inventory.csv
virginia/fairfax_county/traffic-inventory.csv
virginia/loudoun_county/traffic-inventory.csv
... (134 total)
```

The **Inventory Manager** (`app/inventory-manager.html`) allows users to edit individual assets and saves edits as a JSON ledger file alongside the CSV:
```
virginia/arlington_county/traffic-inventory-edits.json
```

The ledger contains asset-level edits (condition, notes, inspector, name changes, new assets, lat/lon corrections, etc.) keyed by asset ID.

### Requirements — Statewide Consolidation

Create a mechanism (recommend your approach — see options below) that:

1. **Lists all jurisdiction folders** under a given state prefix in R2 (e.g., all folders under `virginia/`)
2. **Downloads each jurisdiction's `traffic-inventory.csv`** from R2
3. **Downloads each jurisdiction's `traffic-inventory-edits.json`** (if it exists) from R2
4. **Applies the edit ledger** to the CSV data (matching by asset ID) — the same merge logic used in `inventory-manager.html` `applyLedger()` function (line 529):
   - If an asset ID has a ledger entry, apply the edits (condition, notes, name, mutcd, class, speed, lat, lon, signal_heads, etc.)
   - If a ledger entry has `_isNew: true` and the asset ID doesn't exist in the CSV, add it as a new row
5. **Adds a `jurisdiction` column** to each row to identify which county/city the asset belongs to
6. **Concatenates all jurisdiction CSVs** (with edits applied) into a single statewide CSV
7. **Deduplicates** by asset ID (Mapillary IDs are globally unique, but if an asset appears in overlapping bounding boxes, keep only one instance — prefer the version with edits)
8. **Uploads the merged statewide CSV** to R2 at: `{state}/_statewide/traffic-inventory.csv`
   - Example: `virginia/_statewide/traffic-inventory.csv`

### Approach Options (Recommend Best Fit)

**Option A: Cloudflare Worker (Recommended)**
- Create a new Cloudflare Worker that runs on a schedule or is triggered via HTTP
- The Worker has direct R2 binding access (fast, no egress costs)
- Can be triggered after the statewide download completes OR after any individual Inventory Manager edit is pushed
- Pros: Fast, scalable, runs close to R2, no server load
- Cons: Requires separate Worker deployment, Worker size limits (may need streaming for large states)

**Option B: Server-Side Endpoint**
- Add a new endpoint to `server/qdrant-proxy.js` (e.g., `POST /api/r2/consolidate-statewide`)
- The endpoint uses the existing R2 Worker proxy to list, download, merge, and re-upload
- Can be triggered from the frontend after statewide download completes
- Pros: No additional infrastructure, reuses existing R2 proxy pattern
- Cons: Server must download all files, merge in memory, re-upload (slower, more memory)

**Option C: Hybrid — Worker triggered by Server**
- Server endpoint triggers the Cloudflare Worker to do the actual merge
- Pros: Clean separation of concerns
- Cons: More complex setup

### CSV Schema

The traffic inventory CSV has these columns (from `generateCSV()` in traffic-inventory.html and `expCSV()` in inventory-manager.html):

```
id, mutcd, name, class, speed, lat, lon, first_seen, signal_heads, condition, notes, next_inspection, inspector, edited, edit_timestamp
```

The statewide merged CSV should add:
```
jurisdiction
```

So the final statewide CSV columns are:
```
id, mutcd, name, class, speed, lat, lon, first_seen, signal_heads, condition, notes, next_inspection, inspector, edited, edit_timestamp, jurisdiction
```

### Trigger Points

The consolidation should run:

1. **After a statewide download completes** (Part 1) — automatically triggered
2. **After an Inventory Manager edit is pushed to R2** — when `saveEdit(push=true)` in `inventory-manager.html` (line 1029) successfully pushes the ledger to R2, it should also trigger a re-consolidation (or at minimum, queue one)
3. **Manually** — provide a button or API endpoint to trigger on demand

---

## Architecture & File Placement

Follow the project's modular architecture rules from CLAUDE.md:

- **New JavaScript for the statewide download UI logic**: Create a new module file (e.g., `app/js/statewide-download.js`) rather than adding large blocks to `traffic-inventory.html`
- **New server endpoint** (if Option B): Add to `server/qdrant-proxy.js` following existing patterns
- **New Cloudflare Worker** (if Option A): Create in a new directory (e.g., `workers/r2-consolidation/`)
- **Tests**: Add test coverage for the consolidation logic

## Key Files to Study Before Implementation

| File | What to Look At |
|------|----------------|
| `app/traffic-inventory.html` | Lines 547-590 (state, R2 config, uploadToR2), Lines 880-918 (jurisdiction message handling), Lines 1102-1150 (startDownload flow) |
| `app/inventory-manager.html` | Lines 497-533 (R2 keys, loadData, ledger loading/applying), Lines 1029-1067 (saveEdit with R2 push) |
| `server/qdrant-proxy.js` | Lines 842-900 (POST /r2/worker-upload endpoint — the R2 proxy pattern to follow) |
| `config.json` | Jurisdiction definitions with state, folder, bbox, fips for all counties |

## Pull Request Process

1. Create a feature branch
2. Implement Part 1 (Statewide Download Button) first — this is self-contained
3. Implement Part 2 (R2 Consolidation) second — depends on understanding the data flow
4. Test with a small subset of jurisdictions first (e.g., 3-5 counties) before running full state
5. Create a PR with screenshots of the new UI and a summary of the architecture chosen for consolidation
6. Provide the PR link for review
