# CLAUDE CODE: Fix R2 Storage to Front-End Connection

## READ THIS FIRST

**Before making ANY changes, read the architecture document at `data-pipeline/Data Pipeline - R2 to Front-End Connection.docx`.** That document is the single source of truth for the correct architecture. Extract the text with pandoc or python and study it completely. Every fix below is derived from that document. If anything in this prompt conflicts with the pipeline document, the pipeline document wins.

---

## Problem Summary

The Crash Lens front-end (`app/index.html`) cannot load crash data from Cloudflare R2 cloud storage. The app has a three-layer URL resolution system:

```
Layer 1: getDataFilePath()    → Builds R2 key like "colorado/douglas/county_roads.csv"
Layer 2: resolveDataUrl()     → Converts that key to full R2 URL using the manifest
Layer 3: fetch()              → Browser HTTP request to R2 CDN
```

This chain is broken. Data never reaches the browser. There are 6 known failure points documented in `data-pipeline/` — manifest 404, path mismatches, missing base URL, CORS, legacy paths, and load-order race conditions.

**R2 Production Endpoint:** `https://pub-3334b656e3c74ea28eb4165b32499843.r2.dev`
**R2 Bucket:** `crash-lens-data`
**Manifest File:** `data/r2-manifest.json` (version 3)

---

## Complete File Map (All Files You Must Touch)

Read each of these files before making changes. The pipeline document (Section 2) has exact line numbers, but lines may have shifted — search by function name instead.

### R2 Connection Files (Primary Fix Targets)

| File | What To Find | Search For |
|------|-------------|------------|
| `app/index.html` | r2State object initialization | `const r2State =` |
| `app/index.html` | `loadR2Manifest()` function | `async function loadR2Manifest` |
| `app/index.html` | `resolveDataUrl()` — 3-strategy URL resolver | `function resolveDataUrl` |
| `app/index.html` | `getDataFilePath()` — R2 key builder | `function getDataFilePath` |
| `app/index.html` | `getActiveRoadTypeSuffix()` — filename mapper | `function getActiveRoadTypeSuffix` |
| `app/index.html` | `AggregateLoader` with `_resolveR2Url()` | `const AggregateLoader` |
| `app/index.html` | Startup sequence (DOMContentLoaded) | `document.addEventListener('DOMContentLoaded'` near end of file |
| `app/index.html` | UltraFailsafe backup autoloader | `ULTRA-FAILSAFE` or `window.addEventListener('load'` near `r2State` |
| `app/index.html` | FinalGuarantee backup autoloader | `FinalGuarantee` near very end of file |
| `app/index.html` | `autoLoadCrashData()` | `async function autoLoadCrashData` |
| `app/index.html` | `APP_PATHS` object | `const APP_PATHS =` |
| `app/index.html` | `getMinimalFallbackConfig()` | `function getMinimalFallbackConfig` |
| `app/index.html` | `R2_BASE_URL` constant | `const R2_BASE_URL =` |
| `data/r2-manifest.json` | Full manifest file | N/A — read entire file |
| `config.json` | State `r2Prefix` values | Search for `"r2Prefix"` |

### Supporting Files (Read for Context, Don't Modify Unless Needed)

| File | Contains |
|------|----------|
| `states/state_adapter.js` | Multi-state CSV detection and normalization |
| `states/colorado/config.json` | Colorado column mapping and jurisdictions |
| `states/colorado/hierarchy.json` | Colorado regions, MPOs, all 64 counties |
| `tests/test_r2_integration.js` | 48+ test cases for R2 resolution — run after fixes |
| `data/CDOT/config.json` | CDOT column mapping and processing rules |

---

## R2 Bucket Folder Structure (From Pipeline Doc Section 3.2)

This is what lives INSIDE the R2 bucket. Your `getDataFilePath()` output must match these paths exactly:

```
crash-lens-data/
  _national/                          ← Federal-level data
    state_comparison.json
    dot_roads.csv | non_dot_roads.csv | statewide_all_roads.csv
  {state}/                            ← e.g., colorado/, virginia/
    _statewide/aggregates.json        ← State rollup stats
    _state/                           ← State-tier road data
      dot_roads.csv | non_dot_roads.csv | statewide_all_roads.csv
    _region/{regionId}/               ← Region-tier data
      aggregates.json | dot_roads.csv | all_roads.csv
    _mpo/{mpoId}/                     ← MPO-tier data
      aggregates.json | dot_roads.csv | all_roads.csv
    {county}/                         ← e.g., douglas/, henrico/
      county_roads.csv                ← Road type 1: County only
      no_interstate.csv               ← Road type 2: No interstate
      all_roads.csv                   ← Road type 3: All roads
      standardized.csv                ← Full standardized dataset
      forecasts_county_roads.json     ← Forecast data
```

### Road Type Mapping (3 Radio Buttons)

| Radio Button | Filter Value | County-Level File | State-Level File |
|-------------|-------------|-------------------|-----------------|
| County Roads Only | `countyOnly` | `county_roads.csv` | `dot_roads.csv` |
| No Interstate | `countyPlusVDOT` | `no_interstate.csv` | `non_dot_roads.csv` |
| All Roads | `allRoads` | `all_roads.csv` | `statewide_all_roads.csv` |

---

## Correct Data Flow (End-to-End) — From Pipeline Doc Section 4

This is the EXACT execution sequence from page load to data render. Every step must complete successfully.

### Startup Sequence (Must Be This Order):
1. `validateAppPaths()` — detect broken file references
2. `loadR2Manifest()` — fetch `data/r2-manifest.json`, populate `r2State.manifest` ← **MUST COMPLETE BEFORE STEP 7**
3. `loadAppConfig()` — load `config.json` with state `r2Prefix` values
4. `loadAppSettings()` — load saved jurisdiction/filter preferences
5. `populateStateDropdown()` — fill state selector (50 states + DC)
6. `populateJurisdictionDropdown()` — fill county selector
7. `autoLoadCrashData()` — **ONLY after all above resolve**

### Data Fetch Chain (Inside autoLoadCrashData):
1. Check IndexedDB cache. If cache hit → use cached data, stop.
2. Call `getDataFilePath()` → builds R2 key like `colorado/douglas/county_roads.csv`
3. Call `resolveDataUrl(path)` which applies 3 strategies in order:
   - **Strategy 1:** Exact match in `r2State.manifest.localPathMapping`
   - **Strategy 2:** Dynamic construction from state `r2Prefix` + parsed filename (legacy paths only)
   - **Strategy 3:** R2-native path detection (pass-through to R2 base URL)
   - **Fallback:** Return original local path unchanged
4. `fetch()` the resolved URL. If fail → use `APP_PATHS.getFallbackData()` and retry.
5. Parse CSV with PapaParse. On first chunk → `StateAdapter.detect(headers)`.
6. Normalize rows → cache in IndexedDB.

---

## IMPLEMENTATION TASKS (Apply In This Exact Order)

### TASK 1 — CRITICAL: Fix `loadR2Manifest()` Fetch Path

**Find:** `async function loadR2Manifest` in `app/index.html`

**Current Bug:** The function uses a single relative path `fetch('../data/r2-manifest.json')`. This only works when the HTML is served from the `app/` directory. It breaks when:
- App is served from root `/` (GitHub Pages default)
- Netlify or other hosts rewrite paths
- Server root doesn't match the expected directory structure

**Required Fix:** Replace the single fetch with a multi-path fallback loop. Try these paths in order until one succeeds:

```javascript
async function loadR2Manifest() {
    const manifestPaths = [
        '../data/r2-manifest.json',
        './data/r2-manifest.json',
        'data/r2-manifest.json',
        '/data/r2-manifest.json'
    ];

    for (const path of manifestPaths) {
        try {
            const response = await fetch(path);
            if (!response.ok) continue;

            const manifest = await response.json();

            // Validate manifest has minimum required structure
            if (!manifest.r2BaseUrl || !manifest.localPathMapping ||
                Object.keys(manifest.localPathMapping).length === 0) {
                console.log(`[R2] Manifest at ${path} empty or missing r2BaseUrl — trying next`);
                continue;
            }

            r2State.manifest = manifest;
            r2State.loaded = true;
            console.log(`[R2] Manifest loaded from ${path}: ${Object.keys(manifest.localPathMapping).length} files mapped, base URL: ${manifest.r2BaseUrl}`);
            return; // Success — exit
        } catch (e) {
            continue; // Try next path
        }
    }

    // All paths failed
    console.warn('[R2] Manifest not found at any path — using R2_BASE_URL fallback');
    r2State.loaded = true;
}
```

**Do NOT remove** the `R2_BASE_URL` hardcoded constant — it's the safety net when the manifest can't load.

---

### TASK 2 — CRITICAL: Fix Race Condition (Backup Autoloaders vs Manifest)

**The Problem:** There are THREE independent backup mechanisms that call `autoLoadCrashData()` without checking if the manifest is ready:

1. **UltraFailsafe** — search for `ULTRA-FAILSAFE` or `window.addEventListener('load'` near the `r2State` section. Fires `autoLoadCrashData()` 3 seconds after `window.load`.
2. **Backup autoloader** — inside the `DOMContentLoaded` handler near end of file. `setTimeout(() => { autoLoadCrashData() }, 5000)`.
3. **FinalGuarantee** — search for `FinalGuarantee` near the very end of the file. Fires at 1s, 3s, 6s, and 10s intervals.

If ANY of these fire before `loadR2Manifest()` finishes, `r2State.manifest` is `null`, and `resolveDataUrl()` can't use Strategy 1 (manifest lookup) or Strategy 2 (dynamic construction). Data fetch falls through to local paths that don't exist → 404.

**Required Fix:** Add a manifest-readiness guard at the TOP of `autoLoadCrashData()`. This ensures that no matter which backup triggers it, it always waits for the manifest:

```javascript
async function autoLoadCrashData(skipCache = false) {
    // ── R2 Manifest Guard ──
    // Ensure the manifest has finished loading before we try to resolve R2 URLs.
    // Backup autoloaders (UltraFailsafe, FinalGuarantee) may call this function
    // before loadR2Manifest() completes in the startup sequence.
    if (!r2State.loaded) {
        console.log('[AutoLoad] Waiting for R2 manifest to finish loading...');
        await new Promise(resolve => {
            const check = setInterval(() => {
                if (r2State.loaded) { clearInterval(check); resolve(); }
            }, 100);
            // Safety timeout: don't wait forever — proceed after 2s even without manifest
            setTimeout(() => { clearInterval(check); r2State.loaded = true; resolve(); }, 2000);
        });
    }

    // ... rest of existing function unchanged ...
```

Place this IMMEDIATELY after the function declaration line, BEFORE the existing `console.log('[AutoLoad] Starting...')` line.

---

### TASK 3 — HIGH: Add Diagnostic Logging

**Find:** `function resolveDataUrl` in `app/index.html`

Add these lines at the very top of the function body:

```javascript
console.log('[R2-DEBUG] resolveDataUrl called with:', localPath);
console.log('[R2-DEBUG] r2State:', { loaded: r2State.loaded, hasManifest: !!r2State.manifest, r2BaseUrl: r2State.manifest?.r2BaseUrl });
console.log('[R2-DEBUG] localPathMapping keys:', Object.keys(r2State.manifest?.localPathMapping || {}).length);
```

**Find:** `function getDataFilePath` in `app/index.html`

Add this line right after the local variable declarations (after `const roadType = ...`):

```javascript
console.log('[R2-DEBUG] getDataFilePath:', { tier, stateKey, r2Prefix, roadType });
```

**Find:** `function _resolveR2Url` inside `AggregateLoader`

Add this line right before the `return` statement:

```javascript
console.log('[AggregateLoader] _resolveR2Url base:', r2Base, 'path:', path, 'url:', `${r2Base}/${path}`);
```

---

### TASK 4 — HIGH: Verify `getDataFilePath()` Returns R2-Native Paths Only

**Find:** `function getDataFilePath` in `app/index.html`

Read every `return` statement in this function. Every single return MUST produce an R2-native path. NONE should start with `data/`, `../data/`, or `./data/`.

**Expected return patterns:**

| Tier | Return Pattern | Example |
|------|---------------|---------|
| `federal` | `_national/{roadType}.csv` | `_national/dot_roads.csv` |
| `state` | `{r2Prefix}/_state/{roadType}.csv` | `colorado/_state/statewide_all_roads.csv` |
| `region` | `{r2Prefix}/_region/{regionId}/{roadType}.csv` | `colorado/_region/region_1/all_roads.csv` |
| `mpo` | `{r2Prefix}/_mpo/{mpoId}/{roadType}.csv` | `colorado/_mpo/drcog/dot_roads.csv` |
| `county` | `{r2Prefix}/{jurisdiction}/{roadType}.csv` | `colorado/douglas/county_roads.csv` |

If ANY return statement produces a legacy `data/CDOT/...` path, rewrite it to match the R2-native pattern above. The `r2Prefix` comes from `appConfig.states[stateKey].r2Prefix`.

---

### TASK 5 — HIGH: Verify `resolveDataUrl()` Strategy 3 R2-Native Detection

**Find:** `function resolveDataUrl` in `app/index.html`, scroll to Strategy 3 (the section with `isR2NativePath`)

Verify the detection condition correctly matches ALL outputs from `getDataFilePath()`:

```javascript
const tierPrefixes = ['_state/', '_statewide/', '_region/', '_mpo/', '_federal/', '_national/'];
const isR2NativePath = !normalizedPath.startsWith('data/')
    && normalizedPath.includes('/')
    && (normalizedPath.endsWith('.csv') || normalizedPath.endsWith('.json') || normalizedPath.endsWith('.csv.gz'));
```

Test mentally with these paths:
- `colorado/douglas/county_roads.csv` → `isR2NativePath` should be `true` ✓
- `_national/dot_roads.csv` → should be `true` ✓
- `colorado/_state/statewide_all_roads.csv` → should be `true` ✓
- `data/CDOT/something.csv` → should be `false` (starts with `data/`) ✓

If the detection misses any valid pattern, fix it. The resulting URL must be:
`https://pub-3334b656e3c74ea28eb4165b32499843.r2.dev/{normalizedPath}`

---

### TASK 6 — MEDIUM: Add `r2.publicUrl` to `getMinimalFallbackConfig()`

**Find:** `function getMinimalFallbackConfig` in `app/index.html`

The `AggregateLoader._resolveR2Url()` checks `appConfig?.r2?.publicUrl` as fallback when manifest is null. But `getMinimalFallbackConfig()` does NOT have an `r2` block. If `config.json` also fails, AggregateLoader falls to `'../data'` (broken).

**Fix:** Add this property to the return object, at the top level alongside `states`, `defaultState`, etc.:

```javascript
r2: {
    publicUrl: "https://pub-3334b656e3c74ea28eb4165b32499843.r2.dev"
},
```

---

### TASK 7 — MEDIUM: Fix `AggregateLoader._resolveR2Url()` Fallback Chain

**Find:** `function _resolveR2Url` inside the `AggregateLoader` IIFE in `app/index.html`

**Current code** falls back: manifest → appConfig → `'../data'`. The `'../data'` fallback is useless for deployed apps.

**Fix:** Insert the `R2_BASE_URL` constant as a third fallback before `'../data'`:

```javascript
function _resolveR2Url(path) {
    const r2Base = (typeof r2State !== 'undefined' && r2State.manifest?.r2BaseUrl)
        ? r2State.manifest.r2BaseUrl
        : (typeof appConfig !== 'undefined' && appConfig?.r2?.publicUrl)
            ? appConfig.r2.publicUrl
            : (typeof R2_BASE_URL !== 'undefined')
                ? R2_BASE_URL
                : '../data';
    console.log('[AggregateLoader] _resolveR2Url base:', r2Base, 'path:', path);
    return `${r2Base}/${path}`;
}
```

---

### TASK 8 — MEDIUM: Add `diagR2Connection()` Health Check

**Find:** The section of `app/index.html` right after `resolveDataUrl()` ends.

**Add this new function:**

```javascript
/**
 * R2 Connection Diagnostic — call from browser DevTools: diagR2Connection()
 * Verifies the entire R2 pipeline end-to-end.
 */
async function diagR2Connection() {
    console.group('[R2 Diagnostics]');
    console.log('1. r2State.loaded:', r2State.loaded);
    console.log('2. r2State.error:', r2State.error);
    console.log('3. Manifest present:', !!r2State.manifest);
    console.log('4. r2BaseUrl:', r2State.manifest?.r2BaseUrl);
    console.log('5. Files in manifest:', Object.keys(r2State.manifest?.files || {}).length);
    console.log('6. LocalPathMapping entries:', Object.keys(r2State.manifest?.localPathMapping || {}).length);

    // Test actual R2 fetch
    const testPath = 'colorado/douglas/county_roads.csv';
    const testUrl = resolveDataUrl(testPath);
    console.log('7. resolveDataUrl test:', testPath, '→', testUrl);
    try {
        const resp = await fetch(testUrl, { method: 'HEAD' });
        console.log('8. HEAD response:', resp.status, resp.statusText);
        console.log('9. Content-Type:', resp.headers.get('content-type'));
        console.log('10. CORS OK: true');
    } catch (e) {
        console.error('8. Fetch FAILED:', e.message);
        if (e.message.includes('CORS') || e.message.includes('blocked')) {
            console.error('10. CORS BLOCKED — check R2 bucket CORS config');
        }
    }
    console.groupEnd();
}
window.diagR2Connection = diagR2Connection;
```

---

### TASK 9 — LOW: Validate `config.json` State Entries Have `r2Prefix`

**File:** `config.json`

Search for every state entry under the `states` object. Every state with data in R2 MUST have `"r2Prefix": "{statename}"`. Check at minimum:

- `"colorado"` → `"r2Prefix": "colorado"` ✓
- `"virginia"` → `"r2Prefix": "virginia"` ✓
- `"maryland"` → `"r2Prefix": "maryland"` (if data exists)

If any `r2Prefix` is missing, `getDataFilePath()` falls back to `stateKey` which may not match the actual R2 folder name.

---

## Verification Checklist (Run After ALL Fixes)

### 1. Run Existing Tests
```bash
node tests/test_r2_integration.js
```
All 48+ tests must pass. If any fail, read the test to understand what it expects and fix your code accordingly.

### 2. Console Diagnostic
Open `app/index.html` in a browser. Open DevTools Console. Run:
```javascript
diagR2Connection()
```
Expected results:
- `r2State.loaded: true`
- `r2State.error: null`
- `Manifest present: true`
- `r2BaseUrl: https://pub-3334b656e3c74ea28eb4165b32499843.r2.dev`
- `Files in manifest: > 0`
- `LocalPathMapping entries: > 0`
- `resolveDataUrl test: colorado/douglas/county_roads.csv → https://pub-3334b656e3c74ea28eb4165b32499843.r2.dev/colorado/douglas/county_roads.csv`
- `HEAD response: 200 OK`

### 3. Functional Test
1. Select **Colorado → Douglas County → County Roads Only**
2. Open Network tab in DevTools
3. Verify request goes to: `https://pub-3334b656e3c74ea28eb4165b32499843.r2.dev/colorado/douglas/county_roads.csv`
4. Verify response is `200 OK` with CSV content
5. Switch to **All Roads** → verify request to `.../all_roads.csv`
6. Switch to **Virginia → Henrico** → verify `/virginia/henrico/` path

### 4. Zero Console Errors
After data loads, there should be ZERO errors matching:
- `[R2] Manifest not found`
- `[R2] No mapping found for:`
- `Failed to fetch` / `net::ERR_`
- `CORS` / `Access-Control-Allow-Origin`
- `404 Not Found` on any R2 URL

---

## Priority Summary

| # | Priority | Task | What Breaks Without It |
|---|----------|------|----------------------|
| 1 | **CRITICAL** | Fix `loadR2Manifest()` multi-path fallback | Manifest never loads on deployed hosts → all R2 resolution fails |
| 2 | **CRITICAL** | Fix race condition — manifest guard in `autoLoadCrashData()` | Data loads before manifest ready → local paths used → 404 |
| 3 | HIGH | Add diagnostic logging to `resolveDataUrl()` + `getDataFilePath()` | Failures are silent, impossible to debug |
| 4 | HIGH | Verify `getDataFilePath()` returns R2-native paths only | Legacy `data/` paths skip Strategy 3 → wrong URLs |
| 5 | HIGH | Verify Strategy 3 R2-native detection in `resolveDataUrl()` | Valid R2 paths not detected → returned as local paths |
| 6 | MEDIUM | Add `r2.publicUrl` to `getMinimalFallbackConfig()` | AggregateLoader has no R2 fallback → aggregate data broken |
| 7 | MEDIUM | Fix `AggregateLoader._resolveR2Url()` fallback chain | When manifest null + no appConfig → falls to `../data` → broken |
| 8 | MEDIUM | Add `diagR2Connection()` health check | No way to diagnose R2 issues from DevTools |
| 9 | LOW | Validate `r2Prefix` in `config.json` state entries | Wrong folder names in R2 paths |

---

## CRITICAL REMINDERS

1. **Read `data-pipeline/Data Pipeline - R2 to Front-End Connection.docx` FIRST** — it is the authoritative reference for the correct architecture.
2. **Do NOT change the R2 base URL** — it is `https://pub-3334b656e3c74ea28eb4165b32499843.r2.dev` and must stay exactly that.
3. **Do NOT remove any existing backup autoloaders** (UltraFailsafe, FinalGuarantee) — they are safety nets. Just add the manifest guard inside `autoLoadCrashData()` so they work correctly.
4. **Do NOT modify `data/r2-manifest.json`** — its contents are generated by the data pipeline and should not be hand-edited.
5. **Run the tests** (`node tests/test_r2_integration.js`) after every change to catch regressions immediately.
6. **`app/index.html` is a massive file (131,000+ lines)** — search by function name, not line number. Line numbers shift as you edit.
