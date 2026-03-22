# Claude Code Prompt: Ranking Validation Step (Stage 2.5)

## Context

Add a new **Stage 2.5: Ranking Validation** to the batch pipeline (`batch-pipeline.yml` and `pipeline.yml`). This step runs AFTER normalization + road-type splitting (Stage 2) and BEFORE aggregation (Stage 3). It does three things in order:

1. **Phase 0 — Hierarchy Pre-Check + FIPS Resolution**: Audit the state's `hierarchy.json` for data quality issues. Use **TIGERweb** and **Census Geocoder** APIs as the authoritative source of truth to resolve conflicts — NOT hierarchy.json guesswork
2. **Phase A — Enrich**: Add missing geographic columns (FIPS, District, Planning District, MPO) to each crash row
3. **Phase B — Rank**: Compute 20 ranking columns (4 scopes × 5 metrics)

### Why TIGERweb?

An audit found **25 of 51 states have hierarchy.json errors**: 98 duplicate county assignments, 37 orphaned counties, 2 mislabeled entries. Instead of trusting hierarchy.json and trying to patch it, we use the **US Census Bureau's TIGERweb REST API** as the authoritative geographic lookup. Given a crash's lat/lon, TIGERweb tells us the definitive county FIPS code, place FIPS code (for cities/towns), and state FIPS — straight from the Census Bureau's TIGER database. No fuzzy name matching, no hierarchy.json dependency for the critical FIPS assignment.

---

## Pipeline Position

```
Stage 0: Init Cache
Stage 1: Split by Jurisdiction
Stage 2: Split by Road Type
>>> Stage 2.5: Ranking Validation <<<  ← NEW (this prompt)
Stage 3: Aggregate by Scope
Stage 4: Upload to R2
```

---

## Key Files to Read Before Coding

| File | Why |
|------|-----|
| `scripts/state_adapter.py` | Understand STANDARD_COLUMNS — especially `x` (longitude), `y` (latitude), `Physical Juris Name` |
| `scripts/split_jurisdictions.py` | Understand how jurisdiction CSVs are named and laid out |
| `scripts/split_road_type.py` | Understand road-type CSV naming |
| `scripts/aggregate_by_scope.py` | Follow its pattern for loading hierarchy.json + building FIPS→key maps |
| `scripts/validate_data.py` | Follow its pattern for incremental processing + reporting |
| `states/virginia/hierarchy.json` | Understand the hierarchy schema (regions, tprs, allCounties) |
| `states/colorado/hierarchy.json` | Second reference — different region/TPR structure |
| `.github/workflows/batch-pipeline.yml` | Where Stage 2.5 will be inserted |
| `.github/workflows/pipeline.yml` | Single-jurisdiction pipeline — also needs Stage 2.5 |

---

## Create: `scripts/ranking_validation.py`

### Script Interface

```bash
# Full run (statewide)
python scripts/ranking_validation.py \
    --state virginia \
    --input-dir data/ \
    --jurisdictions henrico chesterfield fairfax_county \
    --output-dir data/

# Dry run (report only, no file changes)
python scripts/ranking_validation.py \
    --state virginia \
    --input-dir data/ \
    --dry-run

# Skip TIGERweb lookups (use hierarchy.json only — offline mode)
python scripts/ranking_validation.py \
    --state virginia \
    --input-dir data/ \
    --offline

# Force re-compute even if ranking columns already exist
python scripts/ranking_validation.py \
    --state virginia \
    --input-dir data/ \
    --force
```

### Constants

```python
# Road types to process
ROAD_TYPES = ['all_roads', 'no_interstate', 'county_roads', 'city_roads']

# 5 crash metrics to rank by
RANKING_METRICS = {
    'total_crash':                  lambda df: len(df),
    'total_ped_crash':              lambda df: df['Pedestrian?'].isin(['Y','Yes','1','TRUE','true',True]).sum(),
    'total_bike_crash':             lambda df: df['Bike?'].isin(['Y','Yes','1','TRUE','true',True]).sum(),
    'total_fatal':                  lambda df: (df['Crash Severity'] == 'K').sum(),
    'total_fatal_serious_injury':   lambda df: df['Crash Severity'].isin(['K','A']).sum(),
}

# 4 geographic scopes for ranking
RANKING_SCOPES = ['District', 'Juris', 'PlanningDistrict', 'MPO']
# → 4 × 5 = 20 ranking columns

# TIGERweb API endpoints (Census Bureau — authoritative FIPS source)
TIGERWEB_COUNTY_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/State_County/MapServer/11/query"
)
TIGERWEB_PLACES_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/Places_CouSub_ConCity_SubMCD/MapServer/4/query"
)
# Census Geocoder (fallback — returns county + state + tract + block)
CENSUS_GEOCODER_URL = (
    "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
)
```

---

## PHASE 0: Hierarchy Pre-Check + FIPS Resolution via TIGERweb

This is the self-healing layer. Instead of trusting hierarchy.json for FIPS assignments, we use the **crash data's own lat/lon coordinates** to query the Census Bureau's TIGERweb API and get the authoritative county FIPS.

### The 4 Hierarchy Error Types Found Across 25 States

| Error Type | Count (51 states) | Example | Impact if Uncaught |
|-----------|-------------------|---------|-------------------|
| **Duplicate FIPS** | 98 cases | VA: Clarke(043) in NOVA + Culpeper | Crash counted in 2 districts → inflated rankings |
| **Orphaned FIPS** | 37 cases | VA: 20 counties with no region | NULL district → excluded from district rankings |
| **Mislabeled FIPS** | 2 cases | VA: "127" labeled "Mecklenburg" but 127 = New Kent | Wrong county in UI |
| **Ghost FIPS** | 0 (currently) | FIPS in region but not in allCounties | Silently dropped |

### Step 0.1: Compute Jurisdiction Centroids from Crash Data

For each unique `Physical Juris Name` in the crash data, compute the **centroid** (median lat, median lon) from all crash rows. This gives us ~133 coordinates for Virginia, ~64 for Colorado, etc.

```python
def compute_jurisdiction_centroids(df):
    """
    Group crash data by Physical Juris Name.
    For each jurisdiction, compute median x (lon) and median y (lat).

    Use MEDIAN not MEAN to be robust against outlier coordinates.
    Skip rows where x or y is missing/invalid.

    Returns: dict of {juris_name: (median_lon, median_lat)}
    """
```

Why centroids? We only need **one representative lat/lon per jurisdiction** to query TIGERweb, not one per crash. This keeps API calls to ~133 per state (not 500K).

### Step 0.2: Query TIGERweb for County FIPS (Primary API)

For each jurisdiction centroid, query TIGERweb's **Counties layer (ID: 11)** to get the authoritative county FIPS.

```python
def tigerweb_county_lookup(lon, lat):
    """
    Query TIGERweb State_County MapServer, Counties layer (ID: 11).

    URL: https://tigerweb.geo.census.gov/arcgis/rest/services/
         TIGERweb/State_County/MapServer/11/query

    Parameters:
        geometry:       {lon},{lat}
        geometryType:   esriGeometryPoint
        inSR:           4326
        spatialRel:     esriSpatialRelIntersects
        outFields:      GEOID,NAME,STATE,COUNTY,BASENAME
        returnGeometry: false
        f:              json

    Example request:
        .../11/query?geometry=-77.45,37.55&geometryType=esriGeometryPoint
        &inSR=4326&spatialRel=esriSpatialRelIntersects
        &outFields=GEOID,NAME,STATE,COUNTY,BASENAME
        &returnGeometry=false&f=json

    Example response:
        {
            "features": [{
                "attributes": {
                    "GEOID": "51087",
                    "NAME": "Henrico County",
                    "STATE": "51",
                    "COUNTY": "087",
                    "BASENAME": "Henrico"
                }
            }]
        }

    Returns: {
        "state_fips": "51",
        "county_fips": "087",
        "county_geoid": "51087",
        "county_name": "Henrico County",
        "county_basename": "Henrico"
    }
    or None if no match / API error.
    """
```

### Step 0.3: Query TIGERweb for Place FIPS (Cities/Towns)

For the same centroid, also query the **Incorporated Places layer (ID: 4)** from the Places service to get the place-level FIPS code. This identifies whether a crash is inside an incorporated city or town.

```python
def tigerweb_place_lookup(lon, lat):
    """
    Query TIGERweb Places_CouSub_ConCity_SubMCD MapServer,
    Incorporated Places layer (ID: 4).

    URL: https://tigerweb.geo.census.gov/arcgis/rest/services/
         TIGERweb/Places_CouSub_ConCity_SubMCD/MapServer/4/query

    Parameters: (same pattern as county query)
        geometry:       {lon},{lat}
        geometryType:   esriGeometryPoint
        inSR:           4326
        spatialRel:     esriSpatialRelIntersects
        outFields:      GEOID,NAME,STATE,PLACE,BASENAME,LSADC,FUNCSTAT
        returnGeometry: false
        f:              json

    Example response (if point is inside an incorporated place):
        {
            "features": [{
                "attributes": {
                    "GEOID": "5135000",
                    "NAME": "Herndon town",
                    "STATE": "51",
                    "PLACE": "35000",
                    "BASENAME": "Herndon",
                    "LSADC": "57",
                    "FUNCSTAT": "A"
                }
            }]
        }

    LSADC codes:
        "25" = City
        "43" = Town (New England)
        "47" = Village
        "57" = Town (other states, like Virginia)
        "C1" = Consolidated city-county

    Returns: {
        "place_fips": "35000",
        "place_geoid": "5135000",
        "place_name": "Herndon town",
        "place_basename": "Herndon",
        "place_type": "57"  (LSADC code)
    }
    or None if point is not inside any incorporated place.
    """
```

### Step 0.4: Census Geocoder Fallback

If TIGERweb returns no result (rare — could be API downtime or coordinates in water/outside US), fall back to the Census Geocoder.

```python
def census_geocoder_lookup(lon, lat):
    """
    Fallback: Census Bureau Geocoder API.

    URL: https://geocoding.geo.census.gov/geocoder/geographies/coordinates
        ?x={lon}&y={lat}
        &benchmark=Public_AR_Current
        &vintage=Current_Current
        &format=json

    Response structure:
        result.geographies.Counties[0].COUNTY = "087"
        result.geographies.Counties[0].STATE  = "42"
        result.geographies.Counties[0].NAME   = "Luzerne County"

    Slower than TIGERweb but more comprehensive.
    Use as fallback when TIGERweb returns empty features array.
    """
```

### Step 0.5: Batch All Lookups with Rate Limiting

```python
def batch_tigerweb_lookups(centroids, state_fips):
    """
    For each jurisdiction centroid, query TIGERweb County + Place layers.

    Rate limiting:
    - TIGERweb has no published rate limit but be respectful
    - Add 100ms delay between requests (0.1s × 133 = ~13 seconds for Virginia)
    - Retry 3 times with exponential backoff on HTTP errors
    - If TIGERweb is completely down, fall back to Census Geocoder for all

    Optimization:
    - Filter centroids to only the target state (by state_fips) to avoid
      cross-state false positives
    - Cache results in a JSON file so re-runs don't re-query
      Cache file: .cache/{state}/tigerweb_fips_cache.json

    Returns: dict of {
        juris_name: {
            "county_fips": "087",
            "state_fips": "51",
            "county_geoid": "51087",
            "county_name": "Henrico County",
            "place_fips": None,        # or "35000" if inside a place
            "place_name": None,        # or "Herndon town"
            "source": "tigerweb"       # or "census_geocoder" or "hierarchy_fallback"
        }
    }
    """
```

### Step 0.6: Build the Definitive FIPS Lookup Table

Now combine TIGERweb results with hierarchy.json to build the complete lookup:

```python
def build_fips_lookup(tigerweb_results, hierarchy, crash_df):
    """
    Build the definitive FIPS + hierarchy lookup table.

    For each jurisdiction found in the crash data:

    1. FIPS ASSIGNMENT (authoritative):
       - Use TIGERweb county_fips as the DEFINITIVE FIPS code
       - If TIGERweb and hierarchy.json disagree, TIGERweb WINS (log the conflict)
       - If TIGERweb returned no result, fall back to hierarchy.json name matching

    2. DISTRICT ASSIGNMENT:
       - Using the TIGERweb-verified FIPS, look up which region in hierarchy.json
         contains this FIPS
       - If FIPS appears in multiple regions (DUPLICATE): TIGERweb resolved it
         by geography — the county polygon is definitive
       - If FIPS appears in zero regions (ORPHAN): we still know the FIPS,
         so we can log "FIPS 001 (Accomack) not assigned to any region"
         and assign district = "_unassigned"
       - If the crash data itself has a district column (e.g., Virginia's VDOT
         District), use that as secondary confirmation

    3. PLANNING DISTRICT / MPO:
       - Using the verified FIPS, look up planningDistricts and tprs in hierarchy
       - Same logic: if present, assign; if missing section, skip

    4. CONFLICT LOGGING:
       Log every disagreement between TIGERweb and hierarchy.json:
       - FIPS mismatch: "Jurisdiction 'X' → TIGERweb says FIPS 087 (Henrico),
         hierarchy name match says FIPS 043 (Clarke)"
       - Region conflict: "FIPS 043 in 2 regions [culpeper, nova],
         TIGERweb centroid is in Culpeper District"

    Returns: dict of {
        juris_name: {
            "fips": "087",
            "state_fips": "51",
            "county_geoid": "51087",
            "county_name": "Henrico County",
            "place_fips": None or "35000",
            "place_name": None or "Herndon town",
            "region_key": "richmond",
            "region_name": "Richmond District",
            "planning_district_key": "richmond_regional" or None,
            "planning_district_name": "Richmond Regional" or "",
            "mpo_key": "rvarc" or None,
            "mpo_name": "RVARC" or "",
            "fips_source": "tigerweb" | "census_geocoder" | "hierarchy_fallback",
            "conflicts": []  # list of conflict descriptions
        }
    }
    """
```

### Step 0.7: Save Validation Report

```python
def save_validation_report(lookup_table, state, output_dir):
    """
    Save hierarchy_validation_report.json alongside the enriched CSVs.

    {
        "state": "virginia",
        "timestamp": "2026-03-19T14:30:00Z",
        "fips_resolution": {
            "total_jurisdictions": 133,
            "resolved_via_tigerweb": 128,
            "resolved_via_census_geocoder": 3,
            "resolved_via_hierarchy_fallback": 2,
            "unresolved": 0
        },
        "hierarchy_conflicts": {
            "duplicates_found": 4,
            "details": [
                {
                    "fips": "043", "name": "Clarke",
                    "hierarchy_regions": ["culpeper", "nova"],
                    "tigerweb_confirms": "culpeper",
                    "centroid": [-78.01, 39.11]
                }
            ],
            "orphans_found": 20,
            "orphan_details": [
                {
                    "fips": "001", "name": "Accomack",
                    "tigerweb_fips": "001",
                    "hierarchy_region": null,
                    "assigned_to": "_unassigned"
                }
            ],
            "mislabels_found": 1,
            "mislabel_details": [
                {
                    "fips": "127",
                    "region": "richmond",
                    "hierarchy_says": "Mecklenburg",
                    "tigerweb_says": "New Kent",
                    "likely_intended_fips": "117"
                }
            ]
        },
        "place_fips_coverage": {
            "jurisdictions_with_place_fips": 42,
            "jurisdictions_without": 91,
            "note": "Independent cities and towns have place FIPS; counties do not"
        }
    }
    """
```

---

## PHASE A: Enrich with Hierarchy + FIPS Columns

Using the clean lookup table from Phase 0, add **5 columns** to each crash row.

### Columns to Add

| Column Name | Source | Value Example |
|------------|--------|---------------|
| `FIPS` | TIGERweb county_fips (3-digit) | `"087"` |
| `{DOT} District` | hierarchy region lookup by FIPS | `"4. Richmond"` |
| `Planning District` | hierarchy planningDistricts lookup by FIPS | `"Richmond Regional"` |
| `MPO Name` | hierarchy tprs lookup by FIPS | `"RVARC"` |
| `Place FIPS` | TIGERweb place_fips (5-digit, if inside city/town) | `"35000"` or blank |

The `{DOT} District` column name is dynamic per state:
- Virginia → `DOT District`
- Colorado → `CDOT Region`
- Texas → `TxDOT District`
- Generic → read from `hierarchy.state.dot` + " District"

### Logic per Row

```python
def enrich_row(row, lookup_table, dot_abbrev):
    """
    For each crash row:
    1. Get Physical Juris Name
    2. Look up in the definitive lookup table (Phase 0)
    3. Fill columns that are MISSING or EMPTY only — never overwrite existing data

    For the FIPS column specifically:
    - This is ALWAYS written (new column, won't exist in source data)
    - It's the 3-digit county FIPS from TIGERweb

    For district/PD/MPO columns:
    - Only fill if column is missing, empty, or NaN
    - If source data already has "DOT District" populated, keep it
    """
```

---

## PHASE B: Compute Rankings (4 × 5 = 20 columns)

### Step B.1: Aggregate Metrics per Jurisdiction

```python
def compute_jurisdiction_metrics(df):
    """
    Group by FIPS (NOT by Physical Juris Name — FIPS is authoritative).

    Returns DataFrame:
        FIPS | juris_name       | total_crash | total_ped | total_bike | total_fatal | total_ksi
        087  | Henrico County   | 5234        | 89        | 45         | 23          | 67
        059  | Fairfax County   | 15234       | 234       | 112        | 45          | 134
    """
```

Why group by FIPS instead of Physical Juris Name? Because jurisdiction names can have variants ("Henrico County" vs "Henrico" vs "043. Henrico County") but FIPS is canonical. TIGERweb guarantees one FIPS per jurisdiction.

### Step B.2: Rank Within Each Scope

```python
def rank_within_scope(metrics_df, lookup_table, scope):
    """
    scope = 'District' | 'Juris' | 'PlanningDistrict' | 'MPO'

    For 'District':           group jurisdictions by their region, rank within each
    For 'Juris':              rank across ALL jurisdictions statewide (single group)
    For 'PlanningDistrict':   group by PD, rank within each
    For 'MPO':                group by MPO, rank within each

    Ranking rules:
    - Rank 1 = HIGHEST crash count (most dangerous = rank 1)
    - Ties: method='min' (both get rank 2, next gets rank 4)
    - NaN/0 values: rank last
    - MPO scope: jurisdictions NOT in any MPO get NaN for all 5 MPO rank columns
    - PlanningDistrict scope: if hierarchy has no planningDistricts section, all 5 get NaN
    - Orphaned jurisdictions (_unassigned district): get NaN for District rank columns
    """
```

### Step B.3: Rankings Computed on all_roads, Applied to All Variants

```python
# Rankings computed on all_roads (complete picture)
# Same rank values applied to county_roads, city_roads, no_interstate
# This prevents inconsistency across road-type CSVs
```

### Step B.4: Assign Ranks to Rows

Every crash row from Henrico gets Henrico's rank values. The 20 columns:

```
District_Rank_total_crash
District_Rank_total_ped_crash
District_Rank_total_bike_crash
District_Rank_total_fatal
District_Rank_total_fatal_serious_injury

Juris_Rank_total_crash
Juris_Rank_total_ped_crash
Juris_Rank_total_bike_crash
Juris_Rank_total_fatal
Juris_Rank_total_fatal_serious_injury

PlanningDistrict_Rank_total_crash
PlanningDistrict_Rank_total_ped_crash
PlanningDistrict_Rank_total_bike_crash
PlanningDistrict_Rank_total_fatal
PlanningDistrict_Rank_total_fatal_serious_injury

MPO_Rank_total_crash
MPO_Rank_total_ped_crash
MPO_Rank_total_bike_crash
MPO_Rank_total_fatal
MPO_Rank_total_fatal_serious_injury
```

---

## Output: Enriched CSV — 25 New Columns Total

| Category | Columns | Count |
|----------|---------|-------|
| FIPS | `FIPS`, `Place FIPS` | 2 |
| Hierarchy | `{DOT} District`, `Planning District`, `MPO Name` | 3 |
| Rankings | `{Scope}_Rank_{metric}` × 4 scopes × 5 metrics | 20 |
| **Total** | | **25** |

---

## Integrate into Workflows

### Add to `batch-pipeline.yml`

Insert between Stage 2 and Stage 3 in the `process` job:

```yaml
      # ── Stage 2.5: Ranking Validation ──
      - name: "Stage 2.5: Ranking validation & enrichment"
        run: |
          STATE="${{ needs.prepare.outputs.state }}"
          DATA_DIR="${{ needs.prepare.outputs.data_dir }}"
          JURISDICTIONS='${{ needs.prepare.outputs.jurisdictions_json }}'

          echo "=========================================="
          echo "Stage 2.5: Ranking Validation & Enrichment"
          echo "  Phase 0: FIPS resolution via TIGERweb"
          echo "  Phase A: Enrich with hierarchy columns"
          echo "  Phase B: Compute 20 ranking columns"
          echo "=========================================="

          JURIS_LIST=$(echo "$JURISDICTIONS" | python3 -c "import json,sys; print(' '.join(json.load(sys.stdin)))")

          python scripts/ranking_validation.py \
            --state "$STATE" \
            --input-dir "$DATA_DIR" \
            --jurisdictions $JURIS_LIST \
            --output-dir "$DATA_DIR" || {
            echo "WARNING: Ranking validation had issues (non-fatal)"
          }
```

### Add to `pipeline.yml` (single-jurisdiction)

Same step but with single jurisdiction. Use `--offline` flag if you want to skip TIGERweb for single-jurisdiction reruns (cache from statewide run should exist).

### Update Stage 4 Upload

Add upload of validation report + FIPS cache:

```yaml
      # Inside Stage 4, after existing uploads:
      # Upload hierarchy validation report
      for REPORT in "$DATA_DIR/hierarchy_validation_report.json" ".cache/$STATE/tigerweb_fips_cache.json"; do
        if [ -f "$REPORT" ]; then
          BASENAME=$(basename "$REPORT")
          aws s3 cp "$REPORT" \
            "s3://$R2_BUCKET/$R2_PREFIX/_validation/$BASENAME" \
            --endpoint-url "$R2_ENDPOINT" \
            --content-type "application/json" \
            --only-show-errors
        fi
      done
```

---

## Console Output Format

```
==========================================
Stage 2.5: Ranking Validation & Enrichment
State: Virginia (VDOT) | FIPS: 51
==========================================

── Phase 0: FIPS Resolution ──
  Computing centroids for 133 jurisdictions...
  Querying TIGERweb County layer (133 lookups)...
    [████████████████████████████████] 133/133 (13.4s)
  Querying TIGERweb Places layer (133 lookups)...
    [████████████████████████████████] 133/133 (13.2s)

  TIGERweb results:
    128 resolved via TIGERweb
      3 resolved via Census Geocoder fallback
      2 resolved via hierarchy.json fallback
    133 total — 0 unresolved

  Hierarchy conflicts detected:
    DUPLICATE: FIPS 043 (Clarke) in regions [culpeper, nova]
      → TIGERweb centroid (-78.01, 39.11) falls in Culpeper District ✓
    DUPLICATE: FIPS 061 (Fauquier) in regions [lynchburg, culpeper]
      → TIGERweb centroid (-77.81, 38.73) falls in Culpeper District ✓
    DUPLICATE: FIPS 153 (Prince William) in regions [fredericksburg, nova]
      → TIGERweb centroid (-77.47, 38.79) falls in NOVA District ✓
    DUPLICATE: FIPS 163 (Rockbridge) in regions [lynchburg, staunton]
      → TIGERweb centroid (-79.45, 37.81) falls in Staunton District ✓
    MISLABEL: FIPS 127 in richmond labeled "Mecklenburg" → TIGERweb says "New Kent"
    ORPHAN: 20 FIPS codes not in any region (assigned to _unassigned)

  Place FIPS: 42 jurisdictions have incorporated place boundaries
  Clean lookup table built: 133 entries

── Phase A: Enrich Crash Data ──
  Processing 133 jurisdictions × 4 road types...
  FIPS column: 133 jurisdictions assigned (NEW column)
  Place FIPS column: 42 populated, 91 blank (counties without place boundaries)
  DOT District: 113 already populated, 20 filled from lookup
  Planning District: skipped (not in hierarchy)
  MPO Name: 98 filled, 35 blank (not in MPO)

── Phase B: Compute Rankings ──
  Computing metrics on all_roads (523,401 rows)...
  District scope: 9 districts + 1 _unassigned, 133 jurisdictions ranked
  Juris scope: 133 jurisdictions ranked statewide
  PlanningDistrict scope: skipped (not configured)
  MPO scope: 8 MPOs, 98 jurisdictions ranked

  Top 5 — Juris_Rank_total_crash:
    1. Fairfax County (059): 15,234
    2. Virginia Beach City (810): 12,891
    3. Prince William County (153): 8,912
    4. Henrico County (087): 8,456
    5. Chesterfield County (041): 7,823

  25 new columns written to 532 CSV files
  Saved: hierarchy_validation_report.json

==========================================
```

---

## TIGERweb Caching Strategy

TIGERweb results should be cached so re-runs and pipeline reruns don't re-query the API.

```python
CACHE_DIR = Path('.cache') / state / 'tigerweb'

def load_fips_cache(state):
    """Load cached TIGERweb results from .cache/{state}/tigerweb/fips_cache.json"""

def save_fips_cache(state, results):
    """Save TIGERweb results. Cache format:
    {
        "state": "virginia",
        "queried_at": "2026-03-19T14:30:00Z",
        "api_version": "TIGERweb_Current",
        "entries": {
            "Henrico County": {
                "centroid": [-77.35, 37.55],
                "county_fips": "087",
                "state_fips": "51",
                "county_geoid": "51087",
                "county_name": "Henrico County",
                "place_fips": null,
                "place_name": null,
                "source": "tigerweb"
            }
        }
    }
    """

def is_cache_valid(cache, max_age_days=90):
    """Cache is valid for 90 days (Census boundaries change ~annually)."""
```

Cache is also uploaded to R2 (in Stage 4) so other workflows can reuse it without re-querying TIGERweb.

---

## Offline Mode (`--offline`)

When `--offline` is passed (or TIGERweb is unreachable):

1. Try to load from `.cache/{state}/tigerweb/fips_cache.json`
2. If cache exists and is < 90 days old, use it
3. If no cache, fall back to hierarchy.json name-matching logic:
   - Parse `Physical Juris Name` → find matching entry in `allCounties`
   - Use that FIPS code for hierarchy lookups
   - Log: "Running in offline mode — FIPS from hierarchy name matching (less accurate)"

This ensures the pipeline never fails if TIGERweb is temporarily down.

---

## Edge Cases

1. **State has no `planningDistricts` section**: Fill all 5 `PlanningDistrict_Rank_*` with NaN. Log: "PD not configured — skipped"

2. **State has no MPOs**: Fill all 5 `MPO_Rank_*` with NaN

3. **Crash lat/lon is missing**: Can't query TIGERweb for that centroid. Fall back to hierarchy.json name matching for that jurisdiction

4. **Crash is on a state border**: TIGERweb county polygon is authoritative — if the centroid falls in the neighboring state's county, log a warning but use the result

5. **Virginia independent cities**: TIGERweb treats these as counties (they have their own county FIPS). The county query will return them correctly. The place query will ALSO return them — use county FIPS as the primary, place FIPS as supplementary

6. **Virginia towns**: The county query returns the PARENT county. The place query returns the town itself. Both FIPS codes are valuable — `FIPS` column gets the county, `Place FIPS` gets the town

7. **Re-runs / idempotency**: If `FIPS` and ranking columns already exist, skip unless `--force`

8. **Very small jurisdictions** (< 10 crashes): Still rank them. No size threshold

9. **TIGERweb returns multiple features**: Rare, but possible at county boundaries. Use the feature with the largest area overlap or just take the first result

10. **GitHub Actions network**: TIGERweb is a public US government API with no auth required. Should be accessible from GitHub Actions runners (Ubuntu). Add timeout of 10 seconds per request

---

## Dependencies

```python
# Standard library + pandas (already in pipeline) + requests (already installed)
import pandas as pd
import requests
import json
import os
import sys
import argparse
import logging
import time
from pathlib import Path
from collections import defaultdict
```

No new pip installs needed — `pandas` and `requests` are already in the pipeline.

---

## Testing

```bash
# 1. Virginia (all 4 error types, 133 jurisdictions)
python scripts/ranking_validation.py --state virginia --input-dir data/ --dry-run

# 2. Colorado (clean hierarchy, 64 counties)
python scripts/ranking_validation.py --state colorado --input-dir data/CDOT --dry-run

# 3. Offline mode (no API calls)
python scripts/ranking_validation.py --state virginia --input-dir data/ --offline --dry-run
```

Verify:
- [ ] TIGERweb returns FIPS for all jurisdiction centroids
- [ ] Duplicates are resolved by TIGERweb geography (not guesswork)
- [ ] Orphans still get FIPS from TIGERweb (they exist geographically even if hierarchy is incomplete)
- [ ] Mislabels are detected (TIGERweb name ≠ hierarchy name for same FIPS)
- [ ] FIPS column is populated for all rows
- [ ] Place FIPS is populated for cities/towns, blank for counties
- [ ] 20 ranking columns are computed correctly
- [ ] Rankings match when spot-checked (top/bottom jurisdictions)
- [ ] Validation report JSON is well-formed and uploaded
- [ ] Cache file is created and reused on re-run
- [ ] `--offline` mode works with cache
- [ ] `--dry-run` makes zero file changes
- [ ] Total new columns = 25 (2 FIPS + 3 hierarchy + 20 ranking)

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `scripts/ranking_validation.py` | **CREATE** — core script (Phase 0 + A + B) |
| `.github/workflows/batch-pipeline.yml` | **MODIFY** — insert Stage 2.5 |
| `.github/workflows/pipeline.yml` | **MODIFY** — insert Stage 2.5 |
| `CLAUDE.md` | **MODIFY** — document 25 new columns, Stage 2.5, TIGERweb usage |

Do NOT modify hierarchy.json files — this script works WITH whatever hierarchy data exists, using TIGERweb as the authoritative FIPS source.

## PR Strategy

Single PR: `feat: add ranking validation step (Stage 2.5) with TIGERweb FIPS resolution`

Include dry-run output from Virginia and Colorado as proof of correctness in the PR description.

---

## API Reference Summary

| API | Endpoint | Layer | Returns | Rate Limit |
|-----|----------|-------|---------|------------|
| **TIGERweb Counties** | `tigerweb.geo.census.gov/.../State_County/MapServer/11/query` | Counties (ID: 11) | `STATE`, `COUNTY`, `GEOID`, `NAME`, `BASENAME` | None published; use 100ms delay |
| **TIGERweb Places** | `tigerweb.geo.census.gov/.../Places_CouSub_ConCity_SubMCD/MapServer/4/query` | Incorporated Places (ID: 4) | `STATE`, `PLACE`, `GEOID`, `NAME`, `BASENAME`, `LSADC` | Same |
| **Census Geocoder** | `geocoding.geo.census.gov/geocoder/geographies/coordinates` | N/A | Counties, Tracts, Blocks with `STATE`, `COUNTY`, `GEOID` | 10K batch limit |

All three are free, no auth required, and operated by the US Census Bureau.
