# Claude Code Prompt — Phase 3.5 TIGERweb PIP Integration

## What This Is

We are adding **GPS Jurisdiction Validation (Phase 3.5)** to the CrashLens crash data normalization pipeline. This fixes a real data quality bug: the source crash data often labels crashes with the wrong county. For example, Delaware's data has ~56 crashes labeled "Kent County" whose GPS coordinates actually fall in New Castle or Sussex County. When you filter by Kent County in the frontend, those misplaced crashes appear far outside the county boundary.

The fix: after FIPS resolution (Phase 3), cross-check every crash's GPS against actual county boundaries using the Census TIGERweb API (the same `tigerWMS_Current/MapServer/82` layer our frontend already uses for `BoundaryService.pointInPolygon()`). Reassign the Physical Juris Name when GPS disagrees, and cascade all dependent fields: FIPS, DOT District, Planning District, MPO Name, Area Type.

## Repository Structure

```
Douglas_County_2/
├── geo_resolver.py              ← shared module (root)
├── crash_enricher.py            ← shared module (root)
├── osm_road_enricher.py         ← shared module (root)
├── state_normalize_template.py  ← shared module (root)
├── tigerweb_pip.py              ← NEW: put here (root, alongside other shared modules)
├── requirements.txt             ← UPDATE: add geopandas + shapely
├── cache/                       ← auto-created at runtime
├── states/
│   ├── geography/
│   │   ├── us_counties.json
│   │   ├── us_places.json
│   │   └── us_mpos.json
│   └── delaware/                ← PRODUCTION state files (Image B)
│       ├── de_normalize.py                          ← UPDATE this file
│       ├── DE_normalization_rank_validation.html     ← UPDATE this file
│       ├── hierarchy.json
│       ├── config.json
│       ├── pipeline.md
│       └── ...
└── docs/
    └── data_compare/
        └── Delware/
            └── normalizer v2/   ← SOURCE reference files (Image A)
                ├── de_normalize.py                          ← read from here
                ├── de_normalization_rank_validationv24.html  ← read from here
                ├── tigerweb_pip.py                          ← read from here
                └── requirements.txt                         ← read from here
```

## Tasks (in order)

### 1. Copy `tigerweb_pip.py` to repo root

Copy `docs/data_compare/Delware/normalizer v2/tigerweb_pip.py` to the **repo root** (same level as `geo_resolver.py`, `crash_enricher.py`, `osm_road_enricher.py`).

This is the 5th shared pipeline module. It is **universal** — works for any U.S. state, not just Delaware. It uses Census TIGERweb `tigerWMS_Current/MapServer/82` (same layer as the CrashLens frontend's `BoundaryService`) with a 3-tier fallback:
- **Tier 1**: Local shapely PIP on cached county boundary GeoJSON (~50K pts/sec)
- **Tier 2**: TIGERweb REST API per-point query with grid deduplication
- **Tier 3**: Centroid nearest-neighbor (zero deps, always works)

### 2. Update `requirements.txt` at repo root

Read `docs/data_compare/Delware/normalizer v2/requirements.txt` and merge the new dependencies into the existing `requirements.txt` at repo root. The new additions are:

```
# Phase 3.5 GPS jurisdiction validation — Tier 1 local PIP (optional but ~100x faster)
geopandas>=0.14.0
shapely>=2.0.0
```

Do NOT remove any existing dependencies. Just add these two if they're not already present.

### 3. Update `states/delaware/de_normalize.py`

Read the reference file at `docs/data_compare/Delware/normalizer v2/de_normalize.py` and apply ALL of the following changes to `states/delaware/de_normalize.py`:

**a) Add `centlat`/`centlon` to `DE_COUNTIES` dict:**
Each county entry must include GPS centroids (from `us_counties.json`):
```python
DE_COUNTIES = {
    "Kent":       {"fips": "001", "geoid": "10001", "district": "Central District",
                   "mpo": "Dover/Kent County MPO", "area_type": "Urban",
                   "centlat": 39.097088, "centlon": -75.502982},
    "New Castle":  {"fips": "003", "geoid": "10003", "district": "North District",
                   "mpo": "WILMAPCO", "area_type": "Urban",
                   "centlat": 39.575915, "centlon": -75.644132},
    "Sussex":      {"fips": "005", "geoid": "10005", "district": "South District",
                   "mpo": "Salisbury-Wicomico MPO", "area_type": "Rural",
                   "centlat": 38.673227, "centlon": -75.337024},
}
```

**b) Add `validate_gps_jurisdiction()` function (Phase 3.5):**
This function goes AFTER `resolve_fips()` and BEFORE `generate_object_ids()`. It:
1. Tries to import `tigerweb_pip.TIGERwebValidator` (the shared module)
2. If found → uses 3-tier PIP (shapely → API → centroid)
3. If not found → falls back to built-in centroid nearest-neighbor
4. For each crash with valid GPS: resolves true county, reassigns if mismatch
5. Cascades: Physical Juris Name, FIPS, DOT District, Planning District, MPO Name, Area Type
6. Uses **2% bounding box buffer** (NOT fixed 0.5°):
   ```python
   lat_span = max(lats) - min(lats) or 1.0
   lon_span = max(lons) - min(lons) or 1.0
   lat_min = min(lats) - 0.02 * lat_span  # ≈ 2 km for Delaware
   ```
7. Re-pads FIPS to 3 digits after all reassignments

**c) Insert Phase 3.5 call into the pipeline `main()` function:**
After FIPS resolution, before crash ID generation:
```python
# [4/8] FIPS Resolution
df, fips_lookup = resolve_fips(df)

# Phase 3.5: GPS Jurisdiction Validation (v2.6.3)
print("        Phase 3.5: GPS jurisdiction cross-check...")
df, gps_reassign_stats = validate_gps_jurisdiction(df)

# [5/8] Crash IDs
df = generate_crash_ids(df)
```

**d) Add `tigerweb_pip.py` to startup module check:**
```python
for name in ["geo_resolver.py", "crash_enricher.py", "osm_road_enricher.py", "tigerweb_pip.py"]:
```

**e) Add `gps_reassign_stats` to validation report:**
- Add `gps_reassign_stats` parameter to `build_validation_report()`
- Add `gps_jurisdiction_validation` key to the report output:
  ```python
  "gps_jurisdiction_validation": {
      "reassignments": gps_reassign_stats or {},
      "total_reassigned": sum((gps_reassign_stats or {}).values()),
  }
  ```

**f) Update version in docstring to v2.6.3** and add Phase 3.5 to the pipeline list.

Use the reference file as the authoritative source — match its implementation exactly.

### 4. Update `states/delaware/DE_normalization_rank_validation.html`

Read the reference file at `docs/data_compare/Delware/normalizer v2/de_normalization_rank_validationv24.html` and apply these changes to the production HTML file:

**a) Update `DELAWARE_GEO.counties` to include `centlat`, `centlon`, and `area_type`:**
```javascript
counties: {
    'Kent':       { fips: '001', geoid: '10001', centLat: 39.097088, centLon: -75.502982, area_type: 'Urban' },
    'New Castle': { fips: '003', geoid: '10003', centLat: 39.575915, centLon: -75.644132, area_type: 'Urban' },
    'Sussex':     { fips: '005', geoid: '10005', centLat: 38.673227, centLon: -75.337024, area_type: 'Rural' },
},
```

**b) Add Phase 3.5 TIGERweb PIP to the `runFIPSResolution()` function:**
After the FIPS resolution loop completes (after "FIPS resolution complete"), add:

1. **Ray-casting PIP functions** — `_pointInRing()` and `_pointInFeature()` — same algorithm as the CrashLens frontend's `BoundaryService.pointInPolygon()` (line 133759):
   ```javascript
   function _pointInRing(lon, lat, ring) {
     let inside = false;
     for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
       const xi = ring[i][0], yi = ring[i][1];
       const xj = ring[j][0], yj = ring[j][1];
       if (((yi > lat) !== (yj > lat)) &&
           (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi)) {
         inside = !inside;
       }
     }
     return inside;
   }
   ```

2. **Fetch county boundaries from TIGERweb** (one request, all state counties):
   ```javascript
   const tigerwebUrl = 'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Current/MapServer/82/query';
   const params = new URLSearchParams({
     where: `STATE = '${stateFips}'`,
     outFields: 'GEOID,STATE,COUNTY,NAME,BASENAME',
     returnGeometry: 'true', outSR: '4326', f: 'geojson'
   });
   ```

3. **For each crash**: resolve via PIP first, centroid fallback if TIGERweb fetch failed. On mismatch → reassign + cascade all 6 fields.

4. **2% bounding box** (NOT fixed 0.5°):
   ```javascript
   const latSpan = Math.max(...centLats) - Math.min(...centLats) || 1.0;
   const lonSpan = Math.max(...centLons) - Math.min(...centLons) || 1.0;
   const bbLatMin = Math.min(...centLats) - 0.02 * latSpan;
   const bbLatMax = Math.max(...centLats) + 0.02 * latSpan;
   ```

5. **"GPS REASSIGNED" stat card** in the FIPS stats display.

6. **Log entries** showing each reassignment pair (e.g., "Kent → New Castle: 30 crashes").

**c) Update version badge** from current version to `v2.6.3`.

Use the reference HTML file as the authoritative source for the complete implementation.

### 5. Verify

After all changes, verify:
- `tigerweb_pip.py` exists at repo root alongside `crash_enricher.py`
- `requirements.txt` includes `geopandas` and `shapely`
- `states/delaware/de_normalize.py` has `validate_gps_jurisdiction()` and calls it in the pipeline
- `states/delaware/DE_normalization_rank_validation.html` has `_pointInRing`, `tigerWMS_Current/MapServer/82`, and `0.02 * latSpan`
- All Python files pass syntax check (`python -c "import ast; ast.parse(open('file').read())"`)

## Key Technical Details (for context)

### TIGERweb Layer 82
- Service: `tigerWMS_Current/MapServer/82` (Counties layer)
- Same layer used by the CrashLens frontend `BoundaryService` (line ~21746)
- Returns actual Census TIGER/Line county boundary polygons (not approximations)
- For bulk download: `?where=STATE='10'&returnGeometry=true&outSR=4326&f=geojson`
- For point query: `?geometry={lon},{lat}&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=GEOID,STATE,COUNTY,NAME,BASENAME&returnGeometry=false&f=json`

### 2% Bounding Box Buffer
- NOT fixed 0.5° (~55 km) — that's way too generous
- Formula: `buffer = 0.02 * (max_centroid - min_centroid)`
- Delaware: lat span 0.903° → buffer 0.018° ≈ 2 km; lon span 0.307° → buffer 0.006° ≈ 0.5 km
- Virginia: lat span 2.2° → buffer 0.044° ≈ 4.9 km
- Texas: lat span 6.5° → buffer 0.13° ≈ 14.4 km
- Crashes outside the bounding box are skipped (bad GPS, not in state)

### Cascade on Reassignment
When a crash is reassigned to a different county, ALL 6 dependent fields update:
1. Physical Juris Name → new county name
2. FIPS → new county FIPS (3-digit zero-padded)
3. DOT District → new county's district
4. Planning District → new county's planning district
5. MPO Name → new county's MPO
6. Area Type → new county's area_type (Urban/Rural)

### Pipeline Execution Order (after this change)
```
[1/9] Column Mapping
[2/9] Value Transforms
[3/9] FIPS Resolution
[3.5] GPS Jurisdiction PIP  ← NEW
[4/9] Crash ID Generation
[5/9] EPDO Scoring
[6/9] Jurisdiction Ranking
[7/9] Validation & Report
[8/9] Enrichment
```
