# split.py — Implementation Guide for Claude Code
# CrashLens Universal Jurisdiction & Road Type Splitter v2.0
# ===========================================================
# Location: scripts/split.py (moved from data/split.py)
# Read this entire file before touching split.py or the pipeline workflow.
# Every decision is explained with "WHY" reasoning, not just "WHAT".

═══════════════════════════════════════════════════════════════════════════
 1. WHAT split.py DOES IN ONE SENTENCE
═══════════════════════════════════════════════════════════════════════════

Takes a single statewide normalized CSV (115 columns, all crashes for a state)
and produces per-jurisdiction, per-road-type CSV files that match the exact
R2 folder structure the CrashLens frontend fetches from.


═══════════════════════════════════════════════════════════════════════════
 2. WHERE IT FITS IN THE PIPELINE
═══════════════════════════════════════════════════════════════════════════

batch-all-jurisdictions.yml (runs once per state):

  Step 1: Download raw crash data from state API / portal
          → output: raw_crashes.csv  (40 columns, e.g. 566,762 rows for DE)

  Step 2: Run {state}_normalize.py
          → output: statewide_normalized.csv  (115 columns, same row count)
            The 115 = 69 golden + 4 enrichment + 24 ranking + 19 state-extras

  Step 3: Upload statewide_normalized.csv to R2 at:
          {state}/_state/statewide_all_roads.csv

  Step 4: Trigger batch-pipeline.yml  ← split.py runs here

batch-pipeline.yml (triggered by above):

  Stage 0:  Download statewide_normalized.csv from R2
  Stage 1:  split.py  ← THIS FILE
            → produces per-jurisdiction, per-road-type CSVs
  Stage 4:  Upload all split files to R2
  Stage 4.5: Validate & Auto-Correct
  Stage 5:  Generate Forecasts
  Stage 6:  Commit manifest

KEY POINT: split.py reads from the 115-column STANDARD schema.
  It never reads raw state data. This is why it's universal.


═══════════════════════════════════════════════════════════════════════════
 3. THE TWO ROAD TYPE SETS — WHY TWO DIFFERENT SETS
═══════════════════════════════════════════════════════════════════════════

The frontend has two different "view modes":

  HIGH-LEVEL VIEW (State, Region tiers):
    Engineers want to understand the full DOT road network.
    Questions: "How many crashes on DOT-maintained roads statewide?"
    Files needed: dot_roads, primary_roads, non_dot_roads, all_roads

  LOCAL VIEW (County, MPO, PD, City tiers):
    Local agencies want to see crashes on roads they're responsible for.
    Questions: "How many crashes on county roads in Kent County?"
    Files needed: county_roads, city_roads, no_interstate, all_roads

SET A — ROAD_TYPES_STATE_REGION (used for _state/ and _region/ tiers):
  "all_roads"      → No filter. Every crash in the state/region.
  "dot_roads"      → Ownership == "1. State Hwy Agency"
                     State DOT-maintained roads only.
  "primary_roads"  → Functional Class starts with "1-" or "2-"
                     Interstate (FC 1) + Freeway/Expressway (FC 2).
                     These are the highest-speed, highest-volume roads.
  "non_dot_roads"  → Ownership in {County, City/Town, Federal, Toll, Private}
                     Everything the state DOT does NOT maintain.

SET B — ROAD_TYPES_LOCAL (used for county/, _mpo/, _planning_district/, _city/):
  "all_roads"      → No filter.
  "county_roads"   → Ownership == "2. County Hwy Agency"
  "city_roads"     → Ownership == "3. City or Town Hwy Agency"
  "no_interstate"  → Functional Class does NOT start with "1-" or "2-"
                     Removes Interstate AND Freeway/Expressway (both FC 1 and FC 2).
                     This gives local agencies a view without high-speed through roads.

FILTER IMPLEMENTATION:
  The filters use regex pattern r"^[12]-" to match FC 1 and FC 2 together:
    "1-Interstate (A,1)"                                    → matches
    "2-Principal Arterial - Other Freeways and Expressways" → matches
    "3-Principal Arterial - Other (E,2)"                    → does NOT match
    ""  (empty, Tier 2 not run yet)                         → does NOT match
                                                              (safe default: include)

  Why regex instead of startswith(("1-", "2-"))?
  Both work, but the regex is more concise and easier to extend.
  The pattern r"^[12]-" is explicit and won't accidentally match "12-" etc.


═══════════════════════════════════════════════════════════════════════════
 4. THE TWO SPLIT STRATEGIES — WHY AUTO-DETECTION
═══════════════════════════════════════════════════════════════════════════

Different states are at different stages of enrichment:

  VIRGINIA: Fully normalized + Tier 2 enriched.
    VDOT District, MPO Name, Planning District columns are populated
    by the source data directly (Virginia already has these in their
    crash export). detect_strategy() returns "column" for all three.

  DELAWARE: Normalized, Tier 1 enriched, Tier 2 NOT yet run.
    VDOT District is populated (geo_resolver fills this as "North District",
    "Central District", "South District" from hierarchy.json in Phase 3).
    MPO Name is populated ("Dover/Kent County MPO", "WILMAPCO").
    Planning District is populated.
    → detect_strategy() returns "column" for all three for Delaware too.

  NEW STATE (first run, no Tier 2, no geo_resolver run):
    All three jurisdiction columns are empty.
    detect_strategy() returns "hierarchy" for all three.
    split.py falls back to reading hierarchy.json and filtering by
    Physical Juris Name membership in each entity's county list.

DETECTION LOGIC:
  If column exists AND >= 10% of rows have a non-empty value → Strategy A
  Otherwise → Strategy B

  The 10% threshold is intentionally low. For DE with 3 counties,
  every county has millions of records, so any county having data means
  the column is populated. The threshold guards against rare edge cases
  where a column was partially filled (e.g. only 5% of records processed).


═══════════════════════════════════════════════════════════════════════════
 5. R2 FOLDER STRUCTURE — HOW PATHS ARE CONSTRUCTED
═══════════════════════════════════════════════════════════════════════════

The R2 bucket "crash-lens-data" has this structure (from create_r2_folders.py):

  {state_prefix}/
    _state/                      ← underscore prefix = aggregated tier
    _region/{region_id}/         ← underscore prefix = aggregated tier
    _mpo/{mpo_id}/               ← underscore prefix = aggregated tier
    _planning_district/{pd_id}/  ← underscore prefix = aggregated tier
    _city/{city_slug}/           ← underscore prefix = aggregated tier
    {county_key}/                ← NO underscore = leaf/county level

The underscore prefix convention visually distinguishes aggregated tiers
(which contain data from multiple counties) from county-level folders.

NAMING RULES (enforced by name_to_r2_key()):
  - All lowercase
  - Spaces/hyphens → underscores
  - Apostrophes removed: "Prince George's" → "prince_georges"
  - Periods removed: "St. Mary's" → "st_marys"
  - Numeric prefixes stripped: "001. Accomack County" → "accomack_county"
  - Parenthetical qualifiers stripped: "Sussex (partial)" → "sussex_partial"

These rules MUST match create_r2_folders.py exactly. If they diverge,
the files will be uploaded to different paths than the folders the
frontend is configured to read from.

WHICH TIER USES WHICH SET:
  Tier       | Road Type Set | R2 Path Pattern
  -----------|---------------|----------------------------------
  state      | SET A         | {state}/_state/
  region     | SET A         | {state}/_region/{region_id}/
  mpo        | SET B         | {state}/_mpo/{mpo_id}/
  pd         | SET B         | {state}/_planning_district/{pd_id}/
  city       | SET B         | {state}/_city/{city_slug}/
  county     | SET B         | {state}/{county_key}/


═══════════════════════════════════════════════════════════════════════════
 6. PHYSICAL JURIS NAME — TWO FORMATS
═══════════════════════════════════════════════════════════════════════════

VDOT-STYLE (Virginia and states using geo_resolver with VDOT schema):
  "000. Arlington County"     ← county (FIPS 000, but treated as special)
  "001. Accomack County"      ← county
  "100. City of Richmond"     ← independent city
  "200. Town of Leesburg"     ← town

  Detection: strip_juris_prefix() removes "NNN. " prefix.
             classify_juris_name() checks for "County" or "City of"/"Town of".

PLAIN-NAME STYLE (Delaware, Colorado, Maryland):
  "Kent"        ← county (matched against hierarchy.allCounties values)
  "New Castle"  ← county
  "Wilmington"  ← city (if Place FIPS populated, but classify_juris_name
                  returns "unknown" unless it contains "City of"/"Town of")

  For plain-name states, county identification falls back to cross-checking
  against the known county names from hierarchy.allCounties.

SPLIT ROUTING:
  classify_juris_name() returns 'county', 'city', or 'unknown'.
  split_county_level() handles 'county' and 'unknown' (safe inclusion).
  split_city_level() handles 'city' only.
  Cities are explicitly excluded from split_county_level() to avoid
  duplication (same crashes appearing in both county/ and _city/ folders).


═══════════════════════════════════════════════════════════════════════════
 7. STANDARD COLUMN VALUES — WHY THESE EXACT STRINGS
═══════════════════════════════════════════════════════════════════════════

These values are defined in the CrashLens 69-column golden standard schema.
The frontend filters by these exact strings. Any mismatch = empty filter results.

Functional Class (7 values, same across all states post-normalization):
  "1-Interstate (A,1)"
  "2-Principal Arterial - Other Freeways and Expressways (B)"
  "3-Principal Arterial - Other (E,2)"
  "4-Minor Arterial (H,3)"
  "5-Major Collector (I,4)"
  "6-Minor Collector (5)"
  "7-Local (J,6)"

Ownership (6 values):
  "1. State Hwy Agency"
  "2. County Hwy Agency"
  "3. City or Town Hwy Agency"
  "4. Federal Roads"
  "5. Toll Roads Maintained by Others"
  "6. Private/Unknown Roads"

HOW THEY'RE PRODUCED:
  Before Tier 2: Ownership is EMPTY (geo_resolver hasn't run yet).
  After Tier 2 (osmnx + crash_enricher): These values are populated
  by the OSM crosswalk in crash_enricher.py.

  For Delaware: Tier 2 was skipped in the last run (no osmnx in requirements.txt).
  After the osmnx fix, Tier 2 will run and Ownership/FC will be filled.

FILTER BEHAVIOR WHEN COLUMNS ARE EMPTY:
  dot_roads filter:   Ownership == "1. State Hwy Agency"
    → If Ownership column is empty, result is 0 rows (empty CSV written).
    → This is CORRECT behavior. An empty dot_roads.csv is valid — it tells
      the frontend "we don't have ownership data yet, not that there are 0
      state roads." The file still exists so there's no 404 error.

  no_interstate filter: ~FC.str.match(r"^[12]-")
    → If FC column is empty, fillna("") makes it "", which does NOT match
      r"^[12]-", so these rows PASS THROUGH to no_interstate.csv.
    → This is also CORRECT — unknown FC crashes are included in
      no_interstate by default (safe inclusion).


═══════════════════════════════════════════════════════════════════════════
 8. HIERARCHY.JSON STRUCTURE — WHAT split.py READS
═══════════════════════════════════════════════════════════════════════════

hierarchy.json is the per-state glue file. For Delaware:

{
  "state": { "fips": "10", "name": "Delaware", ... },
  "regions": {
    "de_1": {
      "name": "North District",
      "counties": ["003"],              ← FIPS codes
      "countyNames": {"003": "New Castle"}
    },
    "de_2": { "name": "Central District", "counties": ["001"], ... },
    "de_3": { "name": "South District",  "counties": ["005"], ... }
  },
  "tprs": {                              ← tprs = MPOs (Transportation Planning Regions)
    "wilmapcowapc": {
      "name": "WILMAPCO (Wilmington Area Planning Council)",
      "counties": ["003"]
    },
    "dkcmpo": {
      "name": "Dover/Kent County MPO",
      "counties": ["001"]
    }
  },
  "planningDistricts": {},               ← Delaware has none
  "allCounties": {
    "001": "Kent",
    "003": "New Castle",
    "005": "Sussex (partial)"
  }
}

HOW split.py USES IT (Strategy B):
  build_fips_to_name():
    {"001": "Kent", "003": "New Castle", "005": "Sussex"}

  build_entity_county_map(hierarchy["regions"], fips_to_name):
    {"de_1": ["New Castle"], "de_2": ["Kent"], "de_3": ["Sussex"]}

  Then in split_region_level():
    For de_1: df[df["Physical Juris Name"] strip-matches "New Castle"]

  Note: strip_juris_prefix() is applied because VDOT-style data has "001. Kent"
  but hierarchy uses plain "Kent". The strip makes both styles match.


═══════════════════════════════════════════════════════════════════════════
 9. ADDING A NEW STATE — CHECKLIST
═══════════════════════════════════════════════════════════════════════════

split.py requires ZERO code changes for new states. The steps are:

  1. Create {state}_normalize.py (from state_normalize_template.py)
     This produces the statewide normalized CSV with standard columns.

  2. Create states/{state}/hierarchy.json
     Must have: regions, tprs/mpos, planningDistricts, allCounties sections.
     Even if a state has no MPOs, include "tprs": {} so it doesn't error.

  3. Register in states/download-registry.json
     Add the state entry with r2Prefix, script, etc.

  4. Run split.py:
     python split.py --input {state}_statewide_normalized.csv --state {state}

  The auto-detection logic will:
    - Use Strategy A for jurisdiction columns that are populated
    - Use Strategy B (hierarchy fallback) for empty jurisdiction columns
    - Produce exactly the right R2 folder structure
    - Write the right road type files per tier automatically

  WHAT IF A STATE HAS NO REGIONS?
    hierarchy["regions"] will be {} → split_region_level() returns {} immediately.
    No _region/ files are written. This is correct — no folders created,
    no 404s, the frontend just won't show the Region view level.


═══════════════════════════════════════════════════════════════════════════
 10. BATCH-PIPELINE.YML INTEGRATION
═══════════════════════════════════════════════════════════════════════════

CURRENT batch-pipeline.yml stages (IMPLEMENTED):
  Stage 0:     Download statewide CSV from R2
  Stage 0.5:   Normalize to CrashLens standard
  Stages 1-3:  split.py (jurisdiction + road type + aggregate in ONE pass)
  Stage 4:     Upload all split CSVs to R2
  Stage 4.5:   Validate & Auto-Correct
  Stage 5:     Generate Forecasts
  Stage 5b:    Upload forecast JSONs to R2
  Stage 5c:    Aggregate Forecasts (Region + MPO)
  Stage 5d:    Upload aggregated forecast JSONs to R2
  Stage 6:     Commit Manifest

  Stages 1-3 are unified into a single split.py call:

  - name: Stages 1-3: Split by jurisdiction, road type & aggregate
    run: |
      python scripts/split.py \
        --input "$INPUT_CSV" \
        --state "$STATE" \
        --hierarchy states/$STATE/hierarchy.json \
        --output-dir "$DATA_DIR/splits"

  Stage 4 then uploads everything in $DATA_DIR/splits/ to R2,
  using the directory structure as the R2 path directly.


═══════════════════════════════════════════════════════════════════════════
 11. MANIFEST OUTPUT — WHAT split_manifest.json CONTAINS
═══════════════════════════════════════════════════════════════════════════

split_manifest.json is written to the output directory after split.py runs.

Example for Delaware:
{
  "state": "delaware",
  "generated_at": "2026-03-22T03:41:22Z",
  "elapsed_s": 45.3,
  "total_input_rows": 566762,
  "dry_run": false,
  "strategies": {
    "region": "column",         ← VDOT District was populated
    "mpo": "column",            ← MPO Name was populated
    "planning_district": "hierarchy"  ← Planning District was empty
  },
  "splits": {
    "state": {
      "all_roads": 566762,
      "dot_roads": 0,           ← 0 because Ownership not yet populated
      "primary_roads": 0,       ← 0 because FC not yet populated
      "non_dot_roads": 0,
      "statewide_all_roads": 566762
    },
    "regions": {
      "north_district": {"all_roads": 198432, "dot_roads": 0, ...},
      "central_district": {"all_roads": 88412, ...},
      "south_district": {"all_roads": 279918, ...}
    },
    "counties": {
      "kent": {"all_roads": 88412, "county_roads": 0, "city_roads": 0, "no_interstate": 88412},
      "new_castle": {"all_roads": 198432, ...},
      "sussex": {"all_roads": 279918, ...}
    },
    "mpos": { ... },
    "planning_districts": {},
    "cities": {}
  }
}

The 0-counts for dot_roads, county_roads, etc. confirm that Tier 2 enrichment
hasn't run yet (Ownership/FC columns are empty). After Tier 2 runs, rerunning
split.py will produce non-zero counts for these filtered files.


═══════════════════════════════════════════════════════════════════════════
 12. COMMON ERRORS AND FIXES
═══════════════════════════════════════════════════════════════════════════

ERROR: "Missing standard columns: {'Ownership', 'Functional Class'}"
  CAUSE:  Tier 2 enrichment (osmnx) hasn't run yet.
  FIX:    Not an error — split.py continues. Filtered files (dot_roads,
          county_roads, no_interstate) will have 0 rows until Tier 2 runs.
          Add osmnx>=1.9.0 to requirements.txt to enable Tier 2.

ERROR: "No hierarchy.json found — column-based split only"
  CAUSE:  hierarchy.json not in expected locations.
  FIX:    Pass --hierarchy explicitly, or put hierarchy.json in same folder
          as split.py, or in states/{state}/hierarchy.json from repo root.

ERROR: "No regions in hierarchy — skipping"
  CAUSE:  hierarchy.json has empty "regions": {} section.
  FIX:    Add region definitions to hierarchy.json. Or ignore — the state
          just won't have _region/ folders in R2.

ERROR: County key collision (two counties map to same R2 key)
  CAUSE:  Very rare. Example: "Kent County" and "Kent" both → "kent".
  FIX:    The second one silently overwrites. Check for ambiguous
          county names in the Physical Juris Name column. Usually not
          an issue because states use unique county names.

ERROR: "aws CLI not found"
  CAUSE:  awscli not installed in CI environment.
  FIX:    Add "pip install awscli" to the CI setup step, or use the
          --upload-r2 flag only after confirming awscli is installed.

ERROR: R2 upload fails with SignatureDoesNotMatch
  CAUSE:  R2_ENDPOINT or credentials are wrong.
  FIX:    Verify AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and
          R2_ENDPOINT are set correctly in GitHub Actions secrets.


═══════════════════════════════════════════════════════════════════════════
 13. KEY FUNCTIONS REFERENCE
═══════════════════════════════════════════════════════════════════════════

name_to_r2_key(name)
  Converts any name to R2-safe folder key.
  Mirrors create_r2_folders.py county_name_to_key() exactly.
  Used everywhere a folder name is constructed.

strip_juris_prefix(name)
  Strips "NNN. " numeric prefix from VDOT-style Physical Juris Name.
  Used before matching names against hierarchy allCounties values.

classify_juris_name(name)
  Returns 'county', 'city', or 'unknown'.
  Routes Physical Juris Name entries to split_county_level() or split_city_level().

detect_strategy(df, column)
  Returns 'column' or 'hierarchy'.
  Called once per tier at pipeline start to determine split approach.

build_entity_county_map(section, fips_to_name)
  Builds {entity_id: [county_names]} from hierarchy regions/tprs/PDs.
  Used by Strategy B fallback for all three aggregated tiers.

write_road_type_splits(df, output_dir, road_types)
  The workhorse — applies all road type filters and writes CSV files.
  Called by every phase function with the appropriate road type set.

split() — main entry point
  Orchestrates all 6 phases in order.
  Called by the CLI and can also be imported and called from batch-pipeline.


═══════════════════════════════════════════════════════════════════════════
 14. DO NOT MODIFY WITHOUT READING THIS FIRST
═══════════════════════════════════════════════════════════════════════════

DO NOT change OWN_STATE, OWN_COUNTY, OWN_CITY string values.
  They must match the frontend schema exactly character-for-character.

DO NOT change FC_HIGHWAY_PREFIX_PATTERN without checking all states.
  The regex r"^[12]-" is intentional — it covers both FC 1 and FC 2.
  Changing to r"^1-" would break no_interstate (would only exclude FC 1).

DO NOT change name_to_r2_key() without also updating create_r2_folders.py.
  Both scripts must produce identical keys from the same input names.
  Any divergence means split.py uploads files to paths that don't exist
  in the R2 folder structure, causing 404s in the frontend.

DO NOT remove the statewide_all_roads.csv alias from split_state_level().
  The batch-pipeline.yml workflow checks for this specific filename to
  verify the upload step completed. Removing it breaks the CI check.

DO NOT add state-specific code to split.py.
  If you need state-specific behavior, add it to {state}_normalize.py.
  split.py reads the standard 69-column output — it must stay universal.
