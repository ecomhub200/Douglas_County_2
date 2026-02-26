# Parquet & DuckDB-WASM Integration Plan

**Version:** 1.0
**Date:** February 2026
**Location:** `data-pipeline/parquet-and-duckdb-wasm-integration.md`

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Current Architecture](#2-current-architecture)
3. [Why Not AWS? Why Stay on R2?](#3-why-not-aws-why-stay-on-r2)
4. [What Is Parquet?](#4-what-is-parquet)
5. [What Is DuckDB-WASM?](#5-what-is-duckdb-wasm)
6. [Data Volume Analysis](#6-data-volume-analysis)
7. [Recommended Format Strategy](#7-recommended-format-strategy)
8. [Phase 1: Pre-Computed Aggregates + Meta.json](#8-phase-1-pre-computed-aggregates--metajson)
9. [Phase 2: Parquet Generation in Pipeline](#9-phase-2-parquet-generation-in-pipeline)
10. [Phase 3: DuckDB-WASM Browser Integration](#10-phase-3-duckdb-wasm-browser-integration)
11. [Phase 4: Content-Based Cache Invalidation](#11-phase-4-content-based-cache-invalidation)
12. [Phase 5: Corrections Pipeline (Upload Tab to R2)](#12-phase-5-corrections-pipeline-upload-tab-to-r2)
13. [R2 Storage Structure](#13-r2-storage-structure)
14. [Architecture Diagram](#14-architecture-diagram)
15. [Files to Modify](#15-files-to-modify)
16. [Verification Plan](#16-verification-plan)
17. [What NOT to Do](#17-what-not-to-do)

---

## 1. Problem Statement

The CrashLens app currently fetches full CSV files from Cloudflare R2 for every county view, parsing them in the browser via PapaParse. This works for 2 states but breaks at 30+ state scale:

| Issue | Impact |
|-------|--------|
| **2-10MB CSV per county on first visit** | Users wait 3-10 seconds for dashboard |
| **50-100MB statewide CSVs (TX, CA)** | Browser can't parse 500K+ rows efficiently |
| **30-day TTL cache** | Users see stale data or cache is wasted |
| **No partial loading** | Dashboard needs 5 columns but downloads all 50 |
| **No compression** | CSV is 10x larger than necessary |

**Key constraint:** Users are NOT allowed to aggregate multi-state data. Each user sees only their own state/jurisdiction. This simplifies the architecture significantly.

---

## 2. Current Architecture

```
DOT Sites (30+ states)
  -> GitHub Actions (download + process + split)
    -> CSV upload to Cloudflare R2 (data.aicreatesai.com)
      -> Browser fetches FULL CSV directly from R2
        -> PapaParse parses ALL rows in browser
          -> JavaScript processRow() builds crashState.aggregates
            -> IndexedDB cache stores aggregates (30-day TTL)
              -> Background loads sampleRows for Map/CMF/Search
```

**Current scale:**
- Virginia: ~200K records across 133 jurisdictions -> ~400 MB total (399 CSVs)
- Colorado: ~150K records across 64 counties -> ~200 MB total (192 CSVs)
- Per-county CSV: typically 1,500-2,300 records (manageable)
- Statewide CSV: full state data in one file (problematic for large states)

**What already works well:**
- IndexedDB cache (`CrashLensDataCache`) -- serves aggregates instantly on repeat visits
- Background `loadSampleRowsInBackground()` -- loads raw rows after dashboard renders
- `AggregateLoader` -- pre-computed JSON for state/region/MPO tiers
- R2 manifest with availability checking

---

## 3. Why Not AWS? Why Stay on R2?

### Cost Comparison at 30-State Scale

| Metric | Cloudflare R2 | AWS S3 Standard |
|--------|---------------|-----------------|
| **Storage (20GB)** | $0.30/mo | $0.46/mo |
| **Egress (500GB/mo)** | **$0.00** | **$45.00/mo** |
| **Read operations (5M/mo)** | $1.80/mo | $2.00/mo |
| **Monthly total** | **~$4.35** | **~$50.00** |
| **Annual total** | **~$52** | **~$600** |

### Why R2 Wins for CrashLens

1. **Zero egress fees** -- the app is egress-heavy (every page load fetches data)
2. **Cloudflare CDN built-in** -- data served from 300+ global edge locations
3. **S3-compatible API** -- existing `@aws-sdk/client-s3` code in `server/qdrant-proxy.js` works unchanged
4. **Free custom domain** -- already using `data.aicreatesai.com`
5. **HTTP Range Requests supported** -- required for DuckDB-WASM Parquet queries

### When AWS Would Make Sense (Not Our Case)

- Deep AWS ecosystem integration (Lambda, EMR, Redshift) -- we use GitHub Actions + Coolify
- Compliance certifications (FedRAMP, HIPAA) -- not required
- >100TB of cold archival data -- S3 Glacier is cheaper, but our total data is <20GB

**Decision: Stay on R2.**

---

## 4. What Is Parquet?

Parquet is a **columnar file format** -- it stores data column by column instead of row by row.

### CSV (Row-Based) vs Parquet (Column-Based)

```
CSV stores data row by row:
  Row 1: US-50, K, 2024-01-15, 38.92, -77.45, Clear, Angle
  Row 2: I-95,  A, 2024-02-20, 37.54, -77.43, Rain,  Rear-end
  Row 3: SR-7,  O, 2024-03-10, 38.83, -77.11, Clear, Sideswipe

Parquet stores data column by column, compressed:
  ROUTE column:    [US-50, I-95, SR-7]       -> dictionary: [0,1,2] + lookup table
  SEVERITY column: [K, A, O]                 -> dictionary: [0,1,2]
  DATE column:     [20240115, 20240220, ...]  -> delta-encoded (differences only)
  LAT column:      [38.92, 37.54, 38.83]     -> float compression
```

### Why Columnar Matters for Crash Data

- Dashboard needs SEVERITY + ROUTE columns -> Parquet reads ONLY those 2 columns
- CSV must read the ENTIRE row (all 50 columns) even if you only need 2
- Crash data has many columns (~30-50) but most views only need 5-10

### Size Comparison for Crash Data

| Scenario | CSV Size | Parquet Size | Ratio |
|----------|----------|--------------|-------|
| 1 county (2,000 records) | ~2 MB | ~200 KB | **10x smaller** |
| 1 county (10,000 records) | ~8 MB | ~600 KB | **13x smaller** |
| Statewide VA (200K records) | ~150 MB | ~12 MB | **12x smaller** |
| Statewide TX (2.8M records, 5yr) | ~2.1 GB | ~180 MB | **12x smaller** |
| All 50 states | ~15-20 GB CSV | ~1.5-2 GB Parquet | **10x smaller** |

Crash data compresses especially well because:
- SEVERITY has only 5 values (K/A/B/C/O) -> dictionary-encoded to bits
- WEATHER has ~10 values -> dictionary compression
- ROUTE names repeat -> dictionary compression
- Dates are sequential -> delta encoding
- Lat/Lng are similar numbers -> float compression

---

## 5. What Is DuckDB-WASM?

DuckDB is a fast analytical database (like SQLite but for analytics). **DuckDB-WASM** runs it in the browser via WebAssembly.

### How It Works with Parquet on R2

```
Instead of:
  Browser -> fetch entire CSV from R2 -> PapaParse parses all rows -> JS loops to build aggregates

With DuckDB-WASM:
  Browser -> load DuckDB-WASM -> point it at Parquet file on R2 -> run SQL -> get ONLY needed data
```

### The Magic: HTTP Range Requests

DuckDB-WASM does NOT download the whole Parquet file. It:

1. Reads the Parquet **footer** (last few KB) -> learns schema, row groups, column locations
2. Issues HTTP **Range Requests** to read ONLY the columns and row groups needed
3. For "severity counts by route" on a 200MB file -> transfers only **2-5MB**

```
Example: User loads Douglas County dashboard
- File on R2: colorado/douglas/all_roads.parquet (600 KB)
- DuckDB reads footer: 4 KB transferred
- Dashboard needs: severity counts, top routes, yearly trend
- DuckDB reads only SEVERITY, ROUTE, DATE columns: ~100 KB transferred
- Total: ~104 KB vs downloading 2 MB CSV
```

### DuckDB-WASM Limitations (Honest Assessment)

| Limitation | Impact on CrashLens | Severity |
|-----------|---------------------|----------|
| WASM binary: ~11-33 MB | First-visit downloads extra 11MB (cached after) | MEDIUM |
| Browser memory: ~2-4 GB | Cannot load >2GB raw data | LOW (single jurisdiction never exceeds this) |
| Single-threaded | Queries on 500K+ rows take 1-2 seconds | LOW (acceptable) |
| Range request detection brittle | Some CDN configs cause full-file download | MEDIUM (R2 supports range requests well) |
| Not full feature parity | Some compression codecs missing | LOW (standard codecs work) |
| No multi-thread in Safari | Safari users see slower queries | LOW (most users on Chrome) |

---

## 6. Data Volume Analysis

### Largest US States (Worst-Case Scenarios)

| State | Annual Crashes | 5-Year Total | CSV Size | Parquet Size | Counties | Per-County Avg |
|-------|---------------|-------------|----------|-------------|----------|---------------|
| **Texas** | ~559,000 | ~2.8M | ~2.1 GB | ~180 MB | 254 | ~11K |
| **California** | ~500,000 | ~2.5M | ~1.9 GB | ~160 MB | 58 | ~43K |
| **Florida** | ~395,000 | ~2.0M | ~1.5 GB | ~130 MB | 67 | ~30K |
| **New York** | ~300,000 | ~1.5M | ~1.1 GB | ~95 MB | 62 | ~24K |
| **Virginia** | ~200,000 | ~600K | ~450 MB | ~40 MB | 133 | ~4.5K |

### Can the Browser Handle This?

**Per-county view (what most users see):**

| State | Per-County Records | Parquet Size | DuckDB Query Time | Verdict |
|-------|-------------------|-------------|-------------------|---------|
| Texas county avg | ~11K | ~800 KB | <100ms | Easily handled |
| CA large county (LA) | ~120K | ~8 MB | ~500ms | Handled with DuckDB |
| FL (Miami-Dade) | ~60K | ~4 MB | ~200ms | Easily handled |

**Statewide view (state-tier users):**

| State | Statewide Records | Parquet Size | DuckDB Range Read | Full Load |
|-------|------------------|-------------|-------------------|-----------|
| Texas (5yr) | ~2.8M | ~180 MB | ~5-10 MB (agg query) | Too big for full load |
| California (5yr) | ~2.5M | ~160 MB | ~5-8 MB (agg query) | Too big for full load |
| Virginia (5yr) | ~600K | ~40 MB | ~2-3 MB (agg query) | Possible but slow |

**Key insight:** With DuckDB + Parquet + Range Requests, statewide views work because you NEVER download the entire file -- you query it remotely.

### The No-Multi-State Constraint Works in Our Favor

Since each user only sees their own state/jurisdiction:
- Each session touches at most ONE statewide Parquet file (~40-180 MB)
- DuckDB range requests pull ~2-10 MB per query
- Browser memory never exceeds ~500 MB
- Well within the 2-4 GB WASM memory limit

**Verdict: DuckDB-WASM + Parquet handles the maximum volume including Texas.**

---

## 7. Recommended Format Strategy

### Keep CSV + Add Parquet + Add Meta.json + Add Aggregates.json

```
R2 Storage Structure (per jurisdiction):
colorado/douglas/
  all_roads.csv            <-- KEEP: backward-compatible, manual upload/export, debugging
  all_roads.parquet        <-- NEW: 10x smaller, column-prunable, range-queryable
  county_roads.csv         <-- KEEP
  county_roads.parquet     <-- NEW
  no_interstate.csv        <-- KEEP
  no_interstate.parquet    <-- NEW
  aggregates.json          <-- NEW: pre-computed dashboard data (~50-200 KB)
  meta.json                <-- NEW: hash + timestamp for cache invalidation (~1 KB)
```

### Why Keep CSV?

1. **Manual upload** -- Users upload their own CSV via drag-and-drop. PapaParse handles this
2. **Data export** -- Users expect CSV (Excel-compatible)
3. **Debugging** -- CSV is human-readable
4. **Backward compatibility** -- All existing pipeline scripts and `processRow()` work with CSV
5. **Fallback** -- If DuckDB-WASM fails (old browser, WASM blocked), fall back to CSV

### Why Add Parquet?

1. **10x smaller storage** -- 20GB CSV -> 2GB Parquet
2. **Column-prunable** -- Dashboard needs 5 columns? Transfer 5, not 50
3. **DuckDB range requests** -- Statewide query on 180MB transfers only ~5MB
4. **Pre-sorted/indexed** -- Row group statistics enable predicate pushdown
5. **Type-safe** -- No more string-to-float parsing

### Why Add meta.json?

Current IndexedDB cache uses a 30-day TTL:
- Pipeline updates data -> users see stale cache for up to 30 days
- Shorter TTL -> less effective caching

With `meta.json` (generated during pipeline):
```json
{
  "lastUpdated": "2026-02-26T10:00:00Z",
  "rowCount": 2847,
  "csvHash": "abc123def456",
  "aggregateHash": "789ghi012jkl",
  "state": "colorado",
  "jurisdiction": "douglas"
}
```

Browser: fetch meta.json (1KB) -> compare hash with cache -> match = serve forever, mismatch = re-fetch.

### Why Add aggregates.json?

Pre-computed county-level aggregates (~50-200 KB) power Dashboard, Analysis, Hotspots, Grants tabs instantly -- without downloading CSV OR loading DuckDB-WASM. Fastest possible initial page load.

---

## 8. Phase 1: Pre-Computed Aggregates + Meta.json

**No DuckDB, no Parquet. Just JSON. Maximum safety.**

### Pipeline Changes

**`scripts/generate_aggregates.py --county-level`:**
- New `parse_csv_crashes_detailed()` -- extracts ALL columns (hour, dow, month, funcClass, intType, trafficCtrl, night, personsInjured, vehicleCount, pedKilled, pedInjured)
- New `compute_detailed_aggregates()` -- produces the EXACT `crashState.aggregates` JSON structure the browser expects
- New `generate_county_level_aggregates()` -- per-county orchestration, generates both `aggregates.json` and `meta.json`
- `meta.json` includes MD5 hashes for cache invalidation

```bash
# Generate for all Colorado counties
python scripts/generate_aggregates.py --state colorado --county-level

# Dry run (preview paths without writing)
python scripts/generate_aggregates.py --state virginia --county-level --dry-run
```

**`scripts/upload-to-r2.py`:**
- Discovers `*.json` files in `data/{state}/{jurisdiction}/`
- Sets `Content-Type: application/json`

### Browser Changes

**`app/index.html` -- `autoLoadCrashData()`:**

New Step 2b before existing CSV fetch:
1. Try `fetch({r2Prefix}/{jurisdiction}/aggregates.json)`
2. If found: populate `crashState.aggregates` directly -> dashboard instant -> background-load CSV
3. If not found: fall through to existing CSV fetch (zero regression)

New `checkCacheFreshnessViaMeta()`:
1. On cache hit, fetch tiny `meta.json` from R2
2. Compare `rowCount` and `aggregateHash` with cached data
3. Stale -> invalidate cache -> re-fetch. Fresh -> serve cache indefinitely

### Impact

| Metric | Before | After Phase 1 |
|--------|--------|---------------|
| First-visit dashboard load | 3-10s (download CSV + parse) | **<500ms** (100KB JSON) |
| Cache freshness | 30-day guess | **Always accurate** (meta.json hash) |
| Dependencies added | N/A | None |
| Risk of regression | N/A | **Zero** (CSV fallback) |

---

## 9. Phase 2: Parquet Generation in Pipeline

**Generate Parquet alongside CSV during the pipeline. Browser doesn't use it yet.**

### Pipeline Changes

Add to `pipeline.yml` after CSV split:

```bash
pip install pyarrow
python scripts/generate_parquet.py --state colorado
```

**New `scripts/generate_parquet.py`:**
```python
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.csv as pac

# For each county CSV:
# 1. Read CSV with pyarrow (fast, schema-aware)
# 2. Write Parquet with snappy compression + row group size 50K
# 3. Upload to R2 alongside CSV

def csv_to_parquet(csv_path, parquet_path):
    table = pac.read_csv(csv_path)
    pq.write_table(table, parquet_path,
                    compression='snappy',
                    row_group_size=50000)
```

**`scripts/upload-to-r2.py`:**
- Discover `*.parquet` files alongside CSVs
- Set `Content-Type: application/octet-stream`

### Impact

| Metric | Before | After Phase 2 |
|--------|--------|---------------|
| R2 storage | ~20 GB (all CSV) | **~12 GB** (CSV + Parquet, but Parquet 10x smaller) |
| New dependency | N/A | `pyarrow` in pipeline |
| Browser changes | None | **None** (Parquet stored but not consumed yet) |
| Risk | N/A | **Zero** (additive only) |

---

## 10. Phase 3: DuckDB-WASM Browser Integration

**Load DuckDB-WASM in the browser for Parquet queries. CSV+PapaParse becomes fallback.**

### Browser Changes

**`app/index.html` -- New `DuckDBManager` module:**

```javascript
// Lazy-load DuckDB-WASM only when needed (Map, CMF, statewide views)
const DuckDBManager = {
    db: null,
    conn: null,

    async init() {
        if (this.db) return;
        const DUCKDB_CDN = 'https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@latest/dist/';
        const bundle = await duckdb.selectBundle({
            mvp: {
                mainModule: DUCKDB_CDN + 'duckdb-mvp.wasm',
                mainWorker: DUCKDB_CDN + 'duckdb-browser-mvp.worker.js'
            },
            eh: {
                mainModule: DUCKDB_CDN + 'duckdb-eh.wasm',
                mainWorker: DUCKDB_CDN + 'duckdb-browser-eh.worker.js'
            }
        });
        const worker = new Worker(bundle.mainWorker);
        const logger = new duckdb.ConsoleLogger();
        this.db = new duckdb.AsyncDuckDB(logger, worker);
        await this.db.instantiate(bundle.mainModule);
        this.conn = await this.db.connect();
    },

    async query(parquetUrl, sql) {
        await this.init();
        await this.db.registerFileURL(
            'data.parquet', parquetUrl,
            duckdb.DuckDBDataProtocol.HTTP, false
        );
        const result = await this.conn.query(
            sql.replace('data.parquet', "'data.parquet'")
        );
        return result.toArray();
    }
};
```

**Loading flow changes:**
1. Dashboard: loads `aggregates.json` (Phase 1, no change)
2. Map tab: uses DuckDB to query Parquet for coordinates + severity -> builds mapPoints
3. CMF tab: uses DuckDB to query Parquet for location-specific crashes
4. Statewide view: uses DuckDB range requests on statewide Parquet (never downloads full file)
5. Fallback: if DuckDB init fails -> existing CSV + PapaParse path

### Impact

| Metric | Before | After Phase 3 |
|--------|--------|---------------|
| Map tab load (county) | Download full CSV + parse | **DuckDB queries ~100KB from Parquet** |
| Statewide view (TX) | Impossible (2.1GB CSV) | **Works** (5-10MB range requests) |
| New dependency | N/A | DuckDB-WASM (~11MB, cached after first load) |
| Fallback | N/A | CSV + PapaParse (existing code, unchanged) |

---

## 11. Phase 4: Content-Based Cache Invalidation

**Replace 30-day TTL with hash-based freshness checking.**

### Changes

**`app/index.html` -- `checkCacheFreshnessViaMeta()`:**
- On each cache hit, fetch `meta.json` (1KB, `cache: 'no-cache'`)
- Compare `aggregateHash` and `rowCount` with cached IndexedDB record
- Fresh -> serve cache forever. Stale -> invalidate and re-fetch
- Unknown (no meta.json) -> use existing TTL as fallback

**`crashCacheSave()`:**
- Store `_aggregateHash` in the cached record for future comparison

### Impact

| Metric | Before | After Phase 4 |
|--------|--------|---------------|
| Cache freshness | 30-day guess | **Always accurate** (<1KB check) |
| Cache waste | Up to 30 days stale | **Zero** (invalidated within minutes of pipeline run) |
| Network cost | Re-fetch full data every 30 days | **Only when data actually changes** |

---

## 12. Phase 5: Corrections Pipeline (Upload Tab to R2)

**See companion document: `data-pipeline/corrections-pipeline.md`**

This phase covers:
- User corrections (validation + GPS recovery) flowing back to R2
- Incremental monthly processing (skip already-corrected records)
- Corrections overlay format stored alongside canonical CSV
- Integration with Parquet/DuckDB pipeline
- Using existing `saveGeocodedDataToR2()` and `/r2/upload-geocoded` infrastructure

---

## 13. R2 Storage Structure (After All Phases)

```
R2 Bucket: crash-lens-data
  colorado/
    douglas/
      all_roads.csv                      <-- existing
      all_roads.parquet                  <-- Phase 2
      county_roads.csv                   <-- existing
      county_roads.parquet               <-- Phase 2
      no_interstate.csv                  <-- existing
      no_interstate.parquet              <-- Phase 2
      aggregates.json                    <-- Phase 1 (50-200 KB)
      aggregates_county_roads.json       <-- Phase 1
      aggregates_no_interstate.json      <-- Phase 1
      meta.json                          <-- Phase 1 (1 KB)
      meta_county_roads.json             <-- Phase 1
      meta_no_interstate.json            <-- Phase 1
      corrections.json                   <-- Phase 5 (correction overlay)
      corrections_log.jsonl              <-- Phase 5 (audit trail)
    _statewide/
      aggregates.json                    <-- existing (state tier)
      county_summary.json                <-- existing
      statewide_all_roads.parquet        <-- Phase 2
      statewide_all_roads.csv.gz         <-- existing
    _region/{id}/aggregates.json         <-- existing
    _mpo/{id}/aggregates.json            <-- existing
  virginia/
    (same structure per jurisdiction)
  _federal/
    aggregates.json                      <-- existing
```

---

## 14. Architecture Diagram (After All Phases)

```
DOT Sites (30+ states)
  -> GitHub Actions download scripts (one per state)
    -> Unified pipeline.yml:
        Validate -> Geocode -> Split Jurisdiction -> Split Road Type
        -> Merge Corrections (Phase 5: apply corrections.json overlay)
        -> Generate Aggregates JSON (Phase 1)
        -> Generate Meta JSON (Phase 1)
        -> Generate Parquet (Phase 2)
        -> Upload to R2 (CSV + Parquet + JSON + Corrections)

Browser Load Sequence:
  1. Fetch meta.json (1 KB)      -> check IndexedDB cache hash (Phase 4)
  2. Cache valid                  -> Load from IndexedDB (0ms)
  3. Cache stale or miss          -> Fetch aggregates.json (100 KB) -> Dashboard instant (Phase 1)
  4. User clicks Map/CMF          -> DuckDB queries Parquet via range requests (Phase 3)
  5. DuckDB fails                 -> Fallback: fetch CSV.gz -> PapaParse (existing)
  6. User uploads own CSV         -> PapaParse handles it (existing, unchanged)

User Corrections Flow (Phase 5):
  1. User validates/corrects data in Upload Tab
  2. User geocodes missing GPS coordinates (OSM Nominatim)
  3. Browser saves corrections.json to R2 via /r2/upload-geocoded
  4. Next pipeline run merges corrections into canonical CSV
  5. Re-generates aggregates.json, meta.json, Parquet
```

---

## 15. Files to Modify

### Phase 1 (Current PR)

| File | Change |
|------|--------|
| `scripts/generate_aggregates.py` | `--county-level` flag, `compute_detailed_aggregates()`, `meta.json` generation |
| `scripts/upload-to-r2.py` | JSON file discovery, `Content-Type: application/json` |
| `app/index.html` | Step 2b: aggregates.json loading, `checkCacheFreshnessViaMeta()` |

### Phase 2 (Future PR)

| File | Change |
|------|--------|
| `scripts/generate_parquet.py` | **NEW** -- CSV to Parquet conversion with pyarrow |
| `scripts/upload-to-r2.py` | Parquet file discovery and upload |
| `.github/workflows/pipeline.yml` | Add `pip install pyarrow` + Parquet generation step |

### Phase 3 (Future PR)

| File | Change |
|------|--------|
| `app/index.html` | `DuckDBManager` module, Parquet-backed Map/CMF/Search |
| `app/index.html` | DuckDB-WASM CDN script tag (lazy-loaded) |

### Phase 4 (Can bundle with Phase 1)

| File | Change |
|------|--------|
| `app/index.html` | `crashCacheSave()` stores `_aggregateHash` |

### Phase 5 (Corrections Pipeline)

| File | Change |
|------|--------|
| `app/index.html` | `saveCorrectionsToR2()`, corrections overlay format, incremental tracking |
| `server/qdrant-proxy.js` | `/r2/upload-corrections` endpoint (JSON upload) |
| `scripts/merge_corrections.py` | **NEW** -- merge corrections overlay into canonical CSV |
| `.github/workflows/pipeline.yml` | Add corrections merge step before aggregate generation |

---

## 16. Verification Plan

### Phase 1
1. `python scripts/generate_aggregates.py --state colorado --county-level --dry-run` -> verify output paths
2. `python scripts/generate_aggregates.py --state colorado --county-level` -> verify JSON files generated
3. Upload to R2 -> load app -> Network tab should show `aggregates.json` fetch (not CSV) for dashboard
4. Remove aggregates.json from R2 -> reload -> verify CSV fallback works unchanged
5. Modify meta.json in R2 (change rowCount) -> reload with cached data -> verify cache is invalidated

### Phase 2
1. `python scripts/generate_parquet.py --state colorado` -> verify `.parquet` files generated
2. Compare file sizes: Parquet should be ~10x smaller than CSV
3. Upload to R2 -> verify files accessible via `curl -I` (check Content-Type)

### Phase 3
1. Load app -> check DuckDB-WASM binary is lazy-loaded only when Map tab is clicked
2. Open Map tab -> Network tab should show small Range Request to Parquet (not full file download)
3. Disable WASM in browser -> verify CSV fallback works
4. Load statewide TX view -> verify DuckDB queries complete in <3 seconds

### Phase 5
1. Make corrections in Upload Tab -> verify corrections.json uploaded to R2
2. Run pipeline with corrections -> verify canonical CSV has corrections applied
3. Verify already-corrected records are skipped on next validation run
4. Verify corrections persist across sessions (IndexedDB + R2)

---

## 17. What NOT to Do

1. **Don't move to AWS S3** -- R2 costs 10-12x less for our egress-heavy pattern
2. **Don't abandon CSV** -- needed for manual upload, export, debugging, and fallback
3. **Don't merge all state data** -- per-jurisdiction split is correct (users only see their own)
4. **Don't use a traditional database (PostgreSQL)** -- static files on R2+CDN are simpler and cheaper for read-heavy workloads
5. **Don't add DuckDB-WASM before Phase 1** -- aggregates.json gives 90% of the benefit with zero new dependencies
6. **Don't remove the IndexedDB cache** -- it serves repeat visits instantly; meta.json just makes it smarter
7. **Don't over-optimize R2 storage costs** -- 50 states at $0.30/month is negligible; focus on user latency
8. **Don't store corrections inside the canonical CSV** -- keep them as a separate overlay for auditability
9. **Don't re-validate already-corrected records** -- use Document Nbr tracking for incremental processing
