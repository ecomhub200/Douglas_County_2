# Crash Data Pipeline Architecture

> **Purpose:** Complete reference guide for converting any state's crash data into the CRASH LENS standardized format. Use Colorado (CDOT) as the worked example when adding a new state.

---

## Table of Contents

1. [Pipeline Overview](#1-pipeline-overview)
2. [File Structure](#2-file-structure)
3. [Stage-by-Stage Walkthrough](#3-stage-by-stage-walkthrough)
4. [Target Output Format (VDOT Reference)](#4-target-output-format-vdot-reference)
5. [State Detection System](#5-state-detection-system)
6. [Column Mapping (Raw State -> Standardized)](#6-column-mapping-raw-state---standardized)
7. [VDOT Value Format Compliance](#7-vdot-value-format-compliance)
8. [Derived Fields](#8-derived-fields)
9. [Road System Classification](#9-road-system-classification)
10. [Boolean Flag Derivation](#10-boolean-flag-derivation)
11. [State-Specific Detail Columns](#11-state-specific-detail-columns)
12. [Validation Rules](#12-validation-rules)
13. [Geocoding Strategy](#13-geocoding-strategy)
14. [Split / Road-Type Filtering](#14-split--road-type-filtering)
15. [Configuration Files Required](#15-configuration-files-required)
16. [Execution Paths (Browser vs Server)](#16-execution-paths-browser-vs-server)
17. [Auto-Trigger Workflow (GitHub Actions)](#17-auto-trigger-workflow-github-actions)
18. [Step-by-Step: Adding a New State](#18-step-by-step-adding-a-new-state)
19. [Colorado (CDOT) Complete Example](#19-colorado-cdot-complete-example)
20. [CDOT Auto-Downloader & Merge Strategy](#20-cdot-auto-downloader--merge-strategy)
21. [Appendix A: Standardized Output Columns](#appendix-a-standardized-output-columns)
22. [Appendix B: VDOT Value Reference Tables](#appendix-b-vdot-value-reference-tables)
23. [Appendix C: Command-Line Reference](#appendix-c-command-line-reference)

---

## 1. Pipeline Overview

The pipeline converts raw state-specific crash CSVs into a normalized, validated, geocoded, and split format that the CRASH LENS browser tool can consume.

```
Raw CSV(s) from State DOT
      |
      v
+----------------+    +----------------+    +----------------+    +----------------+    +----------------+
|   STAGE 0      |    |   STAGE 1      |    |   STAGE 2      |    |   STAGE 3      |    |   STAGE 4      |
|   MERGE        |--->|   CONVERT      |--->|   VALIDATE     |--->|   GEOCODE      |--->|   SPLIT        |
|   (optional)   |    |   (normalize)  |    |   (QA/QC)      |    |   (fill GPS)   |    |   (road type)  |
+----------------+    +----------------+    +----------------+    +----------------+    +----------------+
                                                                                              |
                                                                                              v
                                                                                    3 output CSV files
                                                                                    + pipeline_report.json
```

### Core Design Principle

**All state data is normalized to the Henrico (Virginia) VDOT reference format.** The browser tool only understands this one format. Adding a new state means writing a normalizer that transforms that state's raw CSV into identical column names AND value formats.

### Key Lesson Learned (Colorado)

It is NOT enough to map column names. **You must also map column VALUES to match the VDOT vocabulary.** For example:

| What went wrong | Raw value | What tool expects |
|----------------|-----------|-------------------|
| Missing numbered prefixes | `Rear End` | `1. Rear End` |
| Different vocabulary | `Clear` | `1. No Adverse Condition (Clear/Cloudy)` |
| Wrong semantic meaning | `Non-Intersection` in Roadway Description | `1. Two-Way, Not Divided` |
| Different granularity | `Curve Right, Downhill` | `4. Grade - Curve` |

---

## 2. File Structure

```
project_root/
|
+-- .github/workflows/
|   +-- process-cdot-data.yml         # Auto-trigger pipeline on new CSV push
|   +-- download-cdot-crash-data.yml  # CDOT auto-downloader (monthly + manual)
|   +-- download-data.yml             # Scheduled Virginia data downloads
|   +-- validate-data.yml             # Scheduled data validation
|   +-- send-notifications.yml        # Email notifications
|
+-- download_cdot_crash_data.py       # CDOT OnBase downloader + county filter + merge
+-- requirements.txt                  # Python deps (requests, pandas, openpyxl)
|
+-- scripts/
|   +-- process_crash_data.py         # Main pipeline orchestrator
|   +-- state_adapter.py              # State detection + normalization (THE KEY FILE)
|   +-- split_cdot_data.py            # Road-type filtering
|   +-- pipeline_server.py            # HTTP server for browser uploads
|   +-- fix_douglas_conversion.py     # One-time correction script (reference only)
|
+-- states/                           # Per-state configuration
|   +-- colorado/
|   |   +-- config.json               # Column mappings, bounds, road systems
|   |   +-- jurisdictions.json        # County definitions (FIPS, bbox, cities)
|   +-- virginia/
|   |   +-- config.json               # Virginia config (reference baseline)
|   +-- state_adapter.js              # Browser-side normalization (JS version)
|
+-- tests/
|   +-- test_cdot_downloader.py       # 152 tests for downloader + merge logic
|
+-- data/
|   +-- {DOT_NAME}/                   # State data folder (e.g., CDOT, TxDOT)
|   |   +-- source_manifest.json      # CDOT OnBase doc ID registry (64 counties)
|   |   +-- *.csv                     # Raw input + processed output
|   |   +-- {year} {county}.csv       # Per-year county-filtered crash data
|   |   +-- {jurisdiction}_standardized.csv  # Stage 1 output
|   |   +-- {jurisdiction}_all_roads.csv     # Stage 4 output
|   |   +-- {jurisdiction}_county_roads.csv  # Stage 4 output
|   |   +-- {jurisdiction}_no_interstate.csv # Stage 4 output
|   |   +-- crashes.csv               # Default fallback (copy of county_roads)
|   |   +-- .geocode_cache.json      # Persistent geocode cache
|   |   +-- .validation/
|   |       +-- pipeline_report.json  # Processing report
|   +-- henrico_all_roads.csv         # VDOT REFERENCE dataset (Henrico County, VA)
|
+-- app/
    +-- index.html                    # Browser UI with inline pipeline JS
```

---

## 3. Stage-by-Stage Walkthrough

### Stage 0: MERGE (Optional)

Concatenates multiple year-files into one CSV. Skip if you have a single input file.

### Stage 1: CONVERT (Normalization) -- THE CRITICAL STAGE

**Script:** `state_adapter.py` -> `{State}Normalizer.normalize_row()`

This stage does ALL of the following in a single pass per row:

1. **Rename columns** (e.g., `CUID` -> `Document Nbr`)
2. **Derive missing fields** (e.g., severity from injury counts)
3. **Map values to VDOT format** (e.g., `Clear` -> `1. No Adverse Condition (Clear/Cloudy)`)
4. **Fix semantic mismatches** (e.g., CO "Road Description" -> Relation To Roadway)
5. **Derive boolean flags** (13 Yes/No flags from raw detail fields)
6. **Preserve state-specific detail** (raw fields as `_xx_` prefixed columns)

**Output:** `{jurisdiction}_standardized.csv`

### Stage 2: VALIDATE (QA/QC)

Quality checks with auto-correction. See [Section 12](#12-validation-rules).

### Stage 3: GEOCODE (Fill Missing GPS)

**Script:** `process_crash_data.py` -> `stage_geocode()`
**What it does:** Three strategies applied sequentially, with a **persistent cache** to avoid redundant API calls across runs:

1. **Persistent Cache Lookup** -- Checks `.geocode_cache.json` for previously resolved coordinates (both node and Nominatim results from prior runs). Instant, no API calls.
2. **Node Lookup** -- Rows with GPS at known intersection Nodes form a lookup table. Rows missing GPS but sharing the same Node ID get coordinates copied. New mappings are added to the persistent cache.
3. **Nominatim/OpenStreetMap** -- Free geocoding service, querying `"{Location 1} and {Location 2}, {jurisdiction}, {state}"`. Rate-limited to 1 req/sec. Results (including failed lookups) are cached persistently.

**Geocode Cache File:** `data/CDOT/.geocode_cache.json`
```json
{
  "nodes": { "NODE_ID": [longitude, latitude], ... },
  "nominatim": { "query string": [longitude, latitude] | null, ... }
}
```

**Performance impact:**

| Scenario | Without Cache | With Cache |
|----------|--------------|------------|
| First run (1000 rows, 500 missing GPS) | ~500 API calls (~8 min) | ~500 API calls (~8 min) |
| Add new year data (200 new rows) | ~500 API calls again | ~20 new locations (~20 sec) |
| Re-run same data | ~500 API calls again | 0 API calls (~0 sec) |

The cache file is committed to the repository so it persists across CI runs.

Also see [Section 13](#13-geocoding-strategy) for detailed strategy documentation.

**Only runs in server pipeline** (Python path). Browser path skips this.

---

### Stage 4: SPLIT (Road-Type Filtering)

**Script:** `split_cdot_data.py` + `process_crash_data.py` -> `stage_split()`
**What it does:** Creates three filtered views per jurisdiction. See [Section 14](#14-split--road-type-filtering).

**Colorado filtering example:**

| Output File | Filter |
|-------------|--------|
| `{jurisdiction}_all_roads.csv` | No filter (everything) |
| `{jurisdiction}_county_roads.csv` | Agency Id matches county agency code |
| `{jurisdiction}_no_interstate.csv` | System Code != "Interstate Highway" |

Also copies `county_roads.csv` to `data/{DOT}/crashes.csv` as the UI default fallback.

---

## 4. Target Output Format (VDOT Reference)

The **Henrico County, Virginia** dataset (`data/henrico_all_roads.csv`) is the reference format. Every column value in your converted output must match the vocabulary and format used in this file.

### Reference Dataset Quick Facts

- 48,074 rows, 69 columns
- Years: 2017-present
- All values use **numbered prefixes** (e.g., `1. Rear End`, `2. Daylight`)
- Source: Virginia TREDS (Traffic Records Electronic Data System)

### Why This Matters

The CRASH LENS browser tool (`index.html`) performs string matching, filtering, and aggregation on these exact values. If your converted data uses `Rear End` instead of `1. Rear End`, the tool's collision type charts, CMF lookups, and safety analysis will all break.

### How to Audit Your Output

After converting a new state's data, compare every categorical column against the Henrico reference:

```python
import csv

# Load your converted output
with open('data/{DOT}/{jurisdiction}_all_roads.csv') as f:
    converted = list(csv.DictReader(f))

# Load Henrico reference
with open('data/henrico_all_roads.csv') as f:
    henrico = list(csv.DictReader(f))

# Compare unique values per column
for col in ['Collision Type', 'Weather Condition', 'Light Condition', ...]:
    my_vals = set(r.get(col, '') for r in converted if r.get(col))
    ref_vals = set(r.get(col, '') for r in henrico if r.get(col))
    unmatched = my_vals - ref_vals
    if unmatched:
        print(f"WARNING: {col} has values not in reference: {unmatched}")
```

---

## 5. State Detection System

**File:** `state_adapter.py` -> `StateDetector`

Auto-detects which state a CSV came from by examining column headers.

```python
STATE_SIGNATURES = {
    'colorado': {
        'required': ['CUID', 'System Code', 'Injury 00', 'Injury 04'],
        'optional': ['Rd_Number', 'Rd_Section', 'MHE'],
        'display_name': 'Colorado (CDOT)',
        'config_dir': 'colorado'
    },
    'virginia': {
        'required': ['Document Nbr', 'Crash Severity', 'RTE Name', 'SYSTEM'],
        'optional': ['K_People', 'A_People', 'Node', 'Physical Juris Name'],
        'display_name': 'Virginia (TREDS)',
        'config_dir': 'virginia'
    }
}
```

Pick 3-4 columns that ONLY your state's CSV would have.

---

## 6. Column Mapping (Raw State -> Standardized)

### Direct Renames

Every state will need a mapping from its raw column names to the standardized names:

| Standardized Column | Colorado (CDOT) | Virginia (TREDS) | Your State |
|---------------------|-----------------|------------------|------------|
| `Document Nbr` | `CUID` | `Document Nbr` | ? |
| `Crash Date` | `Crash Date` | `Crash Date` | ? |
| `Crash Military Time` | `Crash Time` (strip colons) | `Crash Military Time` | ? |
| `Crash Severity` | **Derived** from Injury 00-04 | `Crash Severity` | ? |
| `K_People` | `Injury 04` | `K_People` | ? |
| `A_People` | `Injury 03` | `A_People` | ? |
| `B_People` | `Injury 02` | `B_People` | ? |
| `C_People` | `Injury 01` | `C_People` | ? |
| `x` (longitude) | `Longitude` | `x` | ? |
| `y` (latitude) | `Latitude` | `y` | ? |
| `Physical Juris Name` | `County` | `Physical Juris Name` | ? |
| `Persons Injured` | `Number Injured` | `Persons Injured` | ? |
| `Vehicle Count` | `Total Vehicles` | `Vehicle Count` | ? |

### Columns That Require Value Mapping (Not Just Rename)

These columns need their values transformed -- see [Section 7](#7-vdot-value-format-compliance):

- Collision Type
- Weather Condition
- Light Condition
- Roadway Surface Condition
- Roadway Alignment
- Roadway Description
- Intersection Type
- Relation To Roadway
- First Harmful Event
- First Harmful Event Loc
- Ownership

---

## 7. VDOT Value Format Compliance

This is the section most likely to be missed. **Every categorical column must output values in the exact VDOT format.**

### Pattern: Numbered Prefix

Most VDOT columns use a `{number}. {description}` format:

```
1. Rear End
2. Angle
3. Head On
4. Sideswipe - Same Direction
...
```

### Column-by-Column VDOT Value Requirements

#### Collision Type

| VDOT Value | Description |
|------------|-------------|
| `1. Rear End` | Rear-end collision |
| `2. Angle` | Angle/broadside/turning |
| `3. Head On` | Head-on collision |
| `4. Sideswipe - Same Direction` | Same-direction sideswipe |
| `5. Sideswipe - Opposite Direction` | Opposite-direction sideswipe |
| `8. Non-Collision` | Rollover, fell from vehicle |
| `9. Fixed Object - Off Road` | Hit fixed object off roadway |
| `10. Deer/Animal` | Animal collision |
| `11. Fixed Object in Road` | Hit object in roadway |
| `12. Ped` | Pedestrian collision |
| `13. Bicycle` | Bicycle collision |
| `16. Other` | Everything else |

**Colorado example (two-step mapping):**
```
Raw CO "MHE": "Front to Rear"
  -> Step 1 (COLLISION_MAP): "Rear End"
  -> Step 2 (COLLISION_VDOT_MAP): "1. Rear End"
```

#### Weather Condition

| VDOT Value | Colorado Values That Map Here |
|------------|-------------------------------|
| `1. No Adverse Condition (Clear/Cloudy)` | `Clear`, `Cloudy` |
| `3. Fog/Smog/Smoke` | `Fog` |
| `4. Snow` | `Snow`, `Blowing Snow` |
| `5. Rain` | `Rain` |
| `6. Sleet/Hail/Freezing` | `Freezing Rain or Freezing Drizzle`, `Sleet or Hail` |
| `7. Blowing Sand/Dust` | `Dust`, `Blowing Sand, Soil, Dirt` |
| `8. Severe Crosswinds` | `Severe Crosswinds`, `Wind` |

#### Light Condition

| VDOT Value | Colorado Values That Map Here |
|------------|-------------------------------|
| `1. Dawn` | `Dawn or Dusk` (if time < 1200) |
| `2. Daylight` | `Daylight` |
| `3. Dusk` | `Dawn or Dusk` (if time >= 1200) |
| `4. Darkness - Road Lighted` | `Dark - Lighted`, `Dark \u2013 Lighted` |
| `5. Darkness - Road Not Lighted` | `Dark - Unlighted`, `Dark \u2013 Unlighted` |

**Note:** Colorado combines Dawn and Dusk into one value. Split by military time.

#### Roadway Surface Condition

| VDOT Value | Colorado Values That Map Here |
|------------|-------------------------------|
| `1. Dry` | `Dry`, `Dry W/Visible Icy Road Treatment` |
| `2. Wet` | `Wet`, `Wet W/Visible Icy Road Treatment` |
| `3. Snow` | `Snowy`, `Snowy W/Visible Icy Road Treatment` |
| `4. Slush` | `Slushy`, `Slushy W/Visible Icy Road Treatment` |
| `5. Ice` | `Icy`, `Icy W/Visible Icy Road Treatment` |
| `6. Sand/Mud/Dirt/Oil/Gravel` | `Sand/Gravel`, `Muddy` |
| `16. Other` | `Roto-Milled`, `Other` |

#### Roadway Alignment

| VDOT Value | Derivation |
|------------|------------|
| `1. Straight - Level` | Straight + Level (or Unknown) |
| `2. Curve - Level` | Curve Right/Left + Level |
| `3. Grade - Straight` | Straight + Uphill/Downhill/Hill Crest |
| `4. Grade - Curve` | Curve + Uphill/Downhill/Hill Crest |

**Colorado:** Derived from two separate fields: `Road Contour Curves` + `Road Contour Grade`.

#### Roadway Description (SEMANTIC MISMATCH WARNING)

| VDOT Value | Meaning |
|------------|---------|
| `1. Two-Way, Not Divided` | Road geometry: undivided two-way |
| `2. Two-Way, Divided, Unprotected Median` | Road geometry: divided, no barrier |
| `3. Two-Way, Divided, Positive Median Barrier` | Road geometry: divided with barrier |
| `4. One-Way, Not Divided` | One-way road |

**CRITICAL:** Colorado's `Road Description` field describes intersection location (`Non-Intersection`, `At Intersection`), NOT road geometry. This is a **semantic mismatch**. The Colorado normalizer derives Roadway Description from `System Code` instead:

```
Interstate Highway -> "3. Two-Way, Divided, Positive Median Barrier"
State Highway      -> "2. Two-Way, Divided, Unprotected Median"
County Road        -> "1. Two-Way, Not Divided"
City Street        -> "1. Two-Way, Not Divided"
```

The original CO `Road Description` value goes to `Relation To Roadway` instead.

#### Intersection Type

| VDOT Value | Colorado Road Description Values |
|------------|----------------------------------|
| `1. Not at Intersection` | `Non-Intersection`, `Ramp`, `Ramp-related`, `Crossover-Related`, etc. |
| `2. Two Approaches` | `Driveway Access Related`, `Railroad Crossing Related` |
| `4. Four Approaches` | `At Intersection`, `Intersection Related`, `Alley Related` |
| `5. Roundabout` | `Roundabout` |

#### Relation To Roadway (NEW -- not in original Henrico, added for completeness)

| VDOT Value | Colorado Road Description Values |
|------------|----------------------------------|
| `1. Main-Line Roadway` | `Crossover-Related`, `Express/Managed/HOV Lane` |
| `2. Acceleration/Deceleration Lanes` | `Ramp`, `Ramp-related` |
| `8. Non-Intersection` | `Non-Intersection`, `Driveway Access Related` |
| `9. Within Intersection` | `At Intersection`, `Roundabout` |
| `10. Intersection Related - Within 150 Feet` | `Intersection Related` |

#### First Harmful Event

| VDOT Value | Colorado First HE Values |
|------------|--------------------------|
| `2. Trees` | `Tree` |
| `3. Utility Pole` | `Light Pole/Utility Pole`, `Traffic Signal Pole`, `Electrical/Utility Box` |
| `5. Guard Rail` | `Guardrail Face`, `Guardrail End`, `Cable Rail` |
| `6. Parked Vehicle` | `Parked Motor Vehicle` |
| `8. Fence` | `Fence` |
| `14. Ditch` | `Ditch` |
| `15. Concrete Traffic Barrier` | `Concrete Highway Barrier` |
| `19. Ped` | `Pedestrian`, `School Age To/From School` |
| `20. Motor Vehicle In Transport` | `Front to Rear`, `Front to Side`, `Side to Side-*`, etc. |
| `21. Animal` | `Wild Animal`, `Domestic Animal` |
| `22. Bicycle` | `Bicycle/Motorized Bicycle` |
| `24. Other Fixed Object` | `Large Rocks or Boulder`, `Delineator/Milepost`, `Barricade` |
| `27. Curb` | `Curb` |
| `30. Overturn (Rollover)` | `Overturning/Rollover`, `Ground` |

(See `FIRST_HE_VDOT_MAP` in `state_adapter.py` for the complete 42-value mapping.)

#### First Harmful Event Location

| VDOT Value | Colorado Location Values |
|------------|--------------------------|
| `1. On Roadway` | `On Roadway`, `In Parking Lane` |
| `2. Shoulder` | `Shoulder` |
| `3. Median` | `Center median/ Island`, `Vehicle crossed center median...` |
| `4. Roadside` | `Ran off left side`, `Ran off right side`, `Ran off "T" intersection` |
| `5. Gore` | `Gore` |
| `9. Outside Right-of-Way` | `On private property` |

#### Ownership

| VDOT Value | Colorado System Code |
|------------|----------------------|
| `1. State Hwy Agency` | `Interstate Highway`, `State Highway`, `Frontage Road` |
| `2. County Hwy Agency` | `County Road` |
| `3. City or Town Hwy Agency` | `City Street` |

---

## 8. Derived Fields

### Severity (KABCO)

If the state doesn't have a single severity column, derive from injury counts:

```
If fatal_count > 0   -> K
Elif serious_count > 0 -> A
Elif minor_count > 0   -> B
Elif possible_count > 0 -> C
Else                    -> O
```

**Colorado:** `Injury 04` (K), `Injury 03` (A), `Injury 02` (B), `Injury 01` (C)

### Year

Extract from date: `"3/15/2023"` -> `"2023"`

### Route Name (RTE Name)

Build from road system + route number + location:

| Colorado System | Construction | Example |
|----------------|--------------|---------|
| Interstate Highway | `I-{Rd_Number stripped}` | `I-25` |
| State Highway | `Location 1` or `CO-{number}` | `S PARKER RD` |
| County Road / City Street | `Location 1` | `PLUM CREEK BLVD` |

### Node (Intersection ID)

For intersection crashes, build from cross-street names:
```
If "At Intersection" or "Intersection Related":
    Node = "{sorted Location 1} & {sorted Location 2}"
Else:
    Node = "" (non-intersection)
```

### Pedestrians Killed / Injured

Derive from non-motorist (NM) type + injury severity:
```
If any TU NM Type contains "Pedestrian":
    If fatal crash -> Pedestrians Killed = 1
    If injury crash -> Pedestrians Injured = 1
```

---

## 9. Road System Classification

Map the state's road system values to the standardized SYSTEM categories:

| Standardized | Description | Colorado |
|-------------|-------------|----------|
| `Interstate` | Interstate highways | `Interstate Highway` |
| `Primary` | State routes | `State Highway` |
| `Secondary` | Frontage roads | `Frontage Road` |
| `NonVDOT secondary` | Local roads | `County Road`, `City Street` |

---

## 10. Boolean Flag Derivation

All 13 boolean flags output as `"Yes"` or `"No"` (string).

| Flag | Colorado Derivation |
|------|---------------------|
| `Pedestrian?` | NM Type contains "Pedestrian" OR Crash Type = "Pedestrian" |
| `Bike?` | NM Type contains "Bicycle" |
| `Alcohol?` | Alcohol Suspected in {Yes-SFST, Yes-BAC, Yes-Both, Yes-Observation} |
| `Speed?` | Driver Action in {Too Fast for Conditions, Exceeded Speed Limit, Speeding} |
| `Hitrun?` | Hit And Run = TRUE |
| `Motorcycle?` | TU Type = "Motorcycle" |
| `Night?` | Lighting in {Dark-Lighted, Dark-Unlighted} |
| `Distracted?` | Driver Action/Human Factor contains distraction keywords |
| `Drowsy?` | Human Factor in {Asleep or Fatigued, Fatigued/Asleep, ...} |
| `Drug Related?` | Marijuana or Drugs Suspected = positive value |
| `Young?` | Any driver age 16-20 |
| `Senior?` | Any driver age >= 65 |
| `Unrestrained?` | Restraint Use in {Not Used, Improperly Used} |

---

## 11. State-Specific Detail Columns

Preserve raw state fields that provide richer detail than the boolean flags. Prefix with `_{state_abbrev}_`.

### Colorado Example (46 columns)

| Category | Columns Preserved |
|----------|-------------------|
| **Crash context** | `_co_total_vehicles`, `_co_mhe`, `_co_crash_type`, `_co_link`, `_co_second_he`, `_co_third_he`, `_co_wild_animal`, `_co_secondary_crash`, `_co_weather2`, `_co_lane_position`, `_co_injury00_uninjured` |
| **TU-1 (Vehicle 1)** | `_co_tu1_direction`, `_co_tu1_movement`, `_co_tu1_vehicle_type`, `_co_tu1_speed_limit`, `_co_tu1_estimated_speed`, `_co_tu1_stated_speed`, `_co_tu1_driver_action`, `_co_tu1_human_factor`, `_co_tu1_age`, `_co_tu1_sex` |
| **TU-2 (Vehicle 2)** | Same fields as TU-1 with `_co_tu2_` prefix |
| **Non-Motorist 1** | `_co_nm1_type`, `_co_nm1_age`, `_co_nm1_sex`, `_co_nm1_action`, `_co_nm1_movement`, `_co_nm1_location`, `_co_nm1_facility`, `_co_nm1_contributing_factor` |
| **Non-Motorist 2** | Same fields with `_co_nm2_` prefix |
| **Source tracking** | `_co_system_code`, `_co_agency_id`, `_co_rd_number`, `_co_location1`, `_co_location2`, `_co_city` |

### Why Preserve These?

- **Speed data** (`_co_tu1_speed_limit`, `_co_tu1_estimated_speed`) -- essential for speed management analysis; the boolean `Speed?` flag loses all detail
- **Driver action** (`_co_tu1_driver_action`) -- "Failed to Yield ROW" vs "Too Fast for Conditions" is critical for countermeasure selection
- **Vehicle type** (`_co_tu1_vehicle_type`) -- truck involvement analysis
- **Non-motorist detail** -- pedestrian/bicycle age, sex, action, crosswalk facility availability

---

## 12. Validation Rules

### State Coordinate Bounds

```json
{
  "colorado": { "latMin": 36.99, "latMax": 41.01, "lonMin": -109.06, "lonMax": -102.04 },
  "virginia": { "latMin": 36.5,  "latMax": 39.5,  "lonMin": -83.7,   "lonMax": -75.2  }
}
```

### Checks Applied

1. Severity must be K/A/B/C/O (auto-correct F->K, P->O)
2. Year must be 2015-current
3. Coordinates within state bounds
4. Transposed lat/lon auto-swap
5. Boolean normalization: Y/N/TRUE/FALSE -> Yes/No
6. Fatal (K) must have K_People > 0
7. Pedestrian collision must have Pedestrian? = Yes
8. Duplicate detection: same date + GPS + collision type -> remove

---

## 13. Geocoding Strategy

### Strategy 1: Node Lookup (Free, Fast)

Rows with GPS at known intersection Nodes form a lookup table. Rows missing GPS but sharing the same Node ID get coordinates copied.

### Strategy 2: Nominatim/OpenStreetMap (Free, Rate-Limited)

Query: `"{Location 1} and {Location 2}, {jurisdiction}, {state}"`
Rate: 1 request/second

---

## 14. Split / Road-Type Filtering

Three output files per jurisdiction, filtered from the standardized source:

| File | Filter Column | Colorado Include Values | Virginia Filter |
|------|--------------|------------------------|-----------------|
| `*_all_roads.csv` | `_co_system_code` | All valid system codes | No filter |
| `*_county_roads.csv` | `_co_system_code` | `City Street`, `County Road` | `SYSTEM` in NonVDOT |
| `*_no_interstate.csv` | `_co_system_code` | `City Street`, `County Road`, `State Highway`, `Frontage Road` | `SYSTEM` != "Interstate" |

### CRITICAL: Filter on Original State Column, NOT Normalized Column

**Always filter on `_co_system_code` (the original Colorado value), NOT on `SYSTEM` (the Virginia-normalized value).** The `SYSTEM` column maps multiple CO values to the same VA value (e.g., both "City Street" and "County Road" map to "NonVDOT secondary"), making it impossible to do precise filtering.

### Data Quality Rules During Split

Before writing output files, the split script MUST:
1. **Remove ghost rows** — rows with empty `Crash Year` AND empty `Crash Date`
2. **Remove duplicates** — rows with duplicate `Document Nbr` (keep first occurrence)
3. **Verify subset relationships** — `county_roads ⊂ no_interstate ⊂ all_roads`
4. **Verify filter accuracy** — every row's `_co_system_code` must be in the include set
5. **Log row counts** — for audit trail

### Rebuild Script

```bash
python3 scripts/rebuild_road_type_csvs.py
```

This script reads `douglas_standardized.csv` and produces all three output files
with strict filtering, ghost row removal, and deduplication.

---

## 15. Configuration Files Required

### states/{state_key}/config.json

```json
{
  "state": {
    "name": "Colorado",
    "abbreviation": "CO",
    "fips": "08",
    "dotName": "CDOT",
    "coordinateBounds": { "latMin": 36.99, "latMax": 41.01, "lonMin": -109.06, "lonMax": -102.04 },
    "dataDir": "CDOT"
  },
  "columnMapping": { "ID": "CUID", "DATE": "Crash Date", ... },
  "roadSystems": { ... },
  "crashTypeMapping": { ... },
  "epdoWeights": { "K": 462, "A": 62, "B": 12, "C": 5, "O": 1 }
}
```

### states/{state_key}/jurisdictions.json

```json
{
  "jurisdictions": {
    "douglas": {
      "name": "Douglas County",
      "fips": "035",
      "mapCenter": [39.33, -104.92],
      "mapZoom": 11,
      "cities": ["CASTLE ROCK", "PARKER", "LONE TREE"]
    }
  }
}
```

---

## 16. Execution Paths (Browser vs Server)

After running the full pipeline for jurisdiction `douglas`:

```
data/CDOT/
  douglas_standardized.csv       # Stage 1: Normalized format (1.5 MB)
  douglas_all_roads.csv          # Stage 4: Complete dataset (1.5 MB)
  douglas_county_roads.csv       # Stage 4: County roads only (383 KB)
  douglas_no_interstate.csv      # Stage 4: No interstate (1.2 MB)
  crashes.csv                    # Copy of county_roads (UI default fallback)
  .geocode_cache.json            # Persistent geocode cache (grows over time)
  .validation/
    pipeline_report.json         # Processing statistics
```

### Path A: Browser-Only (JavaScript)

Both paths start from the same Upload UI. The browser always processes the file locally for instant analysis, then attempts to save it to the server for persistent storage and the full pipeline.

### Combined Path: Browser + Server (Recommended)

```
User uploads CSV via Upload tab (selects State + Jurisdiction)
    |
    v
Browser reads file (FileReader)
    |
    +-------- Immediate: browser-side processing --------+
    |                                                      |
    v                                                      |
Papa.parse in chunks                                       |
    |                                                      |
    v                                                      |
StateAdapter.detect() + normalizeRow()                     |
    |                                                      |
    v                                                      |
processRow() builds aggregates -> Dashboard loads          |
    |                                                      |
    +-------- Background: server save + pipeline ---------+
    |
    v
POST /api/pipeline/run (file + state + jurisdiction)
    |
    v
pipeline_server.py saves raw CSV to data/{DOT}/
  (e.g., data/CDOT/2024 douglas.csv)
    |
    v
Collects ALL raw CSVs in data/{DOT}/ for merging
    |
    v
Runs process_crash_data.py --merge -f
  Merge -> Convert -> Validate -> Geocode -> Split
    |
    v
Output files written to data/{DOT}/
UI shows save status (saved / offline / error)
```

**If server is running:** File is saved permanently to `data/{DOT}/`, full pipeline runs with merge.
**If server is not running:** Browser-only mode — data loads in UI but is not saved to disk. A toast message indicates "Server offline."

### Path A: Manual File Drop (No Browser)

```
User drops CSV file into data/{DOT}/ manually
    |
    v
git add + commit + push to main
    |
    v
GitHub Actions workflow triggers
    |
    v
process-{dot}-data.yml detects new CSV
    |
    v
Merges all raw CSVs -> full pipeline
    |
    v
Output files committed back to repo
```

### Path B: Server-Only (curl / API)

```
curl -X POST -F "state=colorado" -F "jurisdiction=douglas" \
     -F "file=@data/CDOT/new_data.csv" \
     http://localhost:5050/api/pipeline/run
    |
    v
Server saves to data/CDOT/new_data.csv
    |
    v
Merges all raw CSVs -> full pipeline
    |
    v
Output files written to data/CDOT/
```

### Server API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Server health check |
| GET | `/api/pipeline/status` | Current pipeline progress |
| GET | `/api/pipeline/states` | List supported states |
| POST | `/api/pipeline/run` | Upload CSV, save to `data/{DOT}/`, trigger pipeline |

### POST /api/pipeline/run Response

```json
{
  "status": "started",
  "message": "Pipeline started for colorado/douglas",
  "savedAs": "data/CDOT/2024 douglas.csv",
  "outputDir": "data/CDOT/",
  "merging": true,
  "rawFileCount": 4,
  "pollUrl": "/api/pipeline/status"
}
```

### File Naming Convention

When the server saves an uploaded file, it uses the original filename if descriptive (e.g., `2024 douglas.csv`). Generic names like `data.csv` or `upload.csv` are renamed to `{jurisdiction}_{date}.csv`. If a file with the same name already exists, a timestamp suffix is appended to prevent overwriting.

---

## 17. Auto-Trigger Workflow (GitHub Actions)

The pipeline can run automatically when a new CSV is pushed to `data/{DOT}/`.

**Workflow file (Colorado example):** `.github/workflows/process-cdot-data.yml`

### How It Triggers

| Trigger | When | Behavior |
|---------|------|----------|
| **Push to main** | A `.csv` file is added/changed under `data/{DOT}/` | Auto-detects new raw CSVs, merges all raw files, runs full pipeline |
| **Manual dispatch** | Click "Run workflow" in GitHub Actions UI | Choose jurisdiction, input files, merge mode, geocode, dry-run |

### Push Trigger: What Counts as "New Data"

The workflow watches for CSV changes in the state data folder but **ignores pipeline output files**:

```yaml
paths:
  - 'data/CDOT/**/*.csv'
  - 'data/CDOT/*.csv'
  # Ignored (pipeline outputs):
  - '!data/CDOT/*_standardized.csv'
  - '!data/CDOT/*_all_roads.csv'
  - '!data/CDOT/*_county_roads.csv'
  - '!data/CDOT/*_no_interstate.csv'
  - '!data/CDOT/crashes.csv'
```

So dropping `2024 douglas.csv` into `data/CDOT/` and pushing to main will trigger it. But the pipeline's own output commits will **not** re-trigger (no infinite loop).

### Adding a New Year of Data

**Step-by-step (Colorado example):**

1. Get the new CSV from CDOT (e.g., `2024 douglas.csv`)
2. Drop it into `data/CDOT/`
3. Commit and push to main:
   ```bash
   git add "data/CDOT/2024 douglas.csv"
   git commit -m "Add 2024 Douglas County crash data"
   git push origin main
   ```
4. The workflow auto-triggers and:
   - Detects the new CSV
   - Collects ALL raw CSVs in `data/CDOT/` (existing years + new year)
   - Merges them into one dataset
   - Runs Convert -> Validate -> Geocode -> Split
   - Commits the updated output files back to the repo
5. Check results in the Actions tab or in `data/CDOT/.validation/pipeline_report.json`

### Manual Trigger Options

Go to **Actions** > **Process CDOT Crash Data** > **Run workflow**:

| Option | Default | Description |
|--------|---------|-------------|
| Jurisdiction | `douglas` | Which county to process |
| Input files | _(empty = all raw CSVs)_ | Glob pattern, e.g., `data/CDOT/2024*.csv` |
| Merge | `true` | Combine all matching files before pipeline |
| Skip geocode | `false` | Set `true` for faster processing |
| Dry run | `false` | Preview without writing output |

### What the Workflow Does

```
1. Checkout repo
2. Install Python + dependencies (pandas, requests)
3. Detect input files:
   - Push trigger: diff HEAD~1 for changed CSVs, filter out outputs
   - Manual trigger: use provided glob or all raw CSVs
4. Run process_crash_data.py with flags:
   -i <files> -s colorado -j <jurisdiction> -f -v [--merge] [--skip-geocode] [--dry-run]
5. Display pipeline report (input/output rows, GPS coverage, duplicates)
6. Verify output files exist with correct row counts
7. Commit output files only (not raw input CSVs)
8. Push with retry logic (4 attempts, exponential backoff)
```

### Output Commit

The workflow commits only pipeline output files:
- `data/{DOT}/{jurisdiction}_standardized.csv`
- `data/{DOT}/{jurisdiction}_all_roads.csv`
- `data/{DOT}/{jurisdiction}_county_roads.csv`
- `data/{DOT}/{jurisdiction}_no_interstate.csv`
- `data/{DOT}/crashes.csv`
- `data/{DOT}/.validation/pipeline_report.json`

Commit message format:
```
Auto-process: CDOT douglas pipeline - 2026-02-07

Pipeline: 8646 input -> 8592 output | GPS: 95.7%
Trigger: push
```

### Preventing Infinite Loops

The workflow only triggers on raw CSV changes and explicitly excludes output filenames in the `paths` filter. The commit step only stages output files. Since output filenames (`*_standardized.csv`, `*_all_roads.csv`, etc.) are in the ignore list, the output commit does NOT re-trigger the workflow.

---


## 18. Step-by-Step: Adding a New State

### Prerequisites

1. Sample CSV export from the state's DOT
2. Data dictionary (column definitions + valid values)
3. State FIPS code and coordinate bounding box
4. Henrico reference dataset for value comparison

### Step 1: Analyze the Raw Data

```python
import csv
with open('raw_state_data.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# List all columns
print("COLUMNS:", list(rows[0].keys()))

# For each column, show unique values
for col in rows[0].keys():
    vals = set(r.get(col, '') for r in rows if r.get(col))
    print(f"\n{col} ({len(vals)} unique):")
    for v in sorted(vals)[:10]:
        print(f"  '{v}'")
```

### Step 2: Map Columns to Standardized Names

Create a mapping table (see [Section 6](#6-column-mapping-raw-state---standardized)). Identify:
- Direct renames (same data, different column name)
- Derived fields (not in raw data, must be computed)
- Semantic mismatches (same name but different meaning)

### Step 3: Build VDOT Value Mapping Tables

**This is the most important step.** For every categorical column:

1. List all unique values in your raw data
2. List all VDOT reference values from Henrico
3. Create a mapping from each raw value to the correct VDOT value
4. Handle unmapped values (default to `16. Other` or pass through with prefix)

See [Section 7](#7-vdot-value-format-compliance) for the complete reference.

### Step 4: Add Detection Signature

```python
# In state_adapter.py
STATE_SIGNATURES['newstate'] = {
    'required': ['UniqueCol1', 'UniqueCol2', 'UniqueCol3'],
    'optional': ['OptionalCol1'],
    'display_name': 'State Name (DOT)',
    'config_dir': 'newstate'
}
```

### Step 5: Create Normalizer Class

```python
class NewStateNormalizer(BaseNormalizer):
    """New state normalizer -- follow ColoradoNormalizer as template."""

    # VALUE MAPPING TABLES (raw -> VDOT format)
    COLLISION_MAP = { 'Their Rear End': '1. Rear End', ... }
    WEATHER_MAP = { 'Their Clear': '1. No Adverse Condition (Clear/Cloudy)', ... }
    LIGHT_MAP = { ... }
    SURFACE_MAP = { ... }
    FIRST_HE_MAP = { ... }
    FIRST_HE_LOC_MAP = { ... }
    INTERSECTION_MAP = { ... }
    ROAD_DESC_MAP = { ... }
    OWNERSHIP_MAP = { ... }

    # State-specific detail columns to preserve
    EXTRA_COLUMNS = [
        ('_xx_speed_limit', 'Their Speed Limit Column'),
        ('_xx_driver_action', 'Their Driver Action Column'),
        ...
    ]

    def normalize_row(self, row):
        n = {}
        # 1. ID, date, time
        # 2. Severity (direct or derived)
        # 3. Collision Type (mapped to VDOT format)
        # 4. Weather, Light, Surface (mapped to VDOT format)
        # 5. Alignment (mapped to 4-category VDOT format)
        # 6. Road Description (road geometry, NOT intersection type)
        # 7. Intersection Type (approach counts)
        # 8. Relation To Roadway (intersection location relationship)
        # 9. First Harmful Event + Location (VDOT numbered codes)
        # 10. Route name, system, node, coordinates
        # 11. Boolean flags (13 total)
        # 12. Ownership, Vehicle Count, Pedestrians Killed/Injured
        # 13. State-specific detail columns
        return n
```

### Step 6: Register and Test

```python
# Register
_NORMALIZERS['newstate'] = NewStateNormalizer

# Test
python -c "
from scripts.state_adapter import convert_file
state, total, gps = convert_file('data/XDOT/raw.csv', '/tmp/test.csv')
print(f'{total} rows, {gps} with GPS')
"

# Verify against Henrico reference (see Section 4 audit script)
```

### Step 7: Add Split Logic

In `split_cdot_data.py`, add filtering rules for county roads and interstate exclusion.

### Step 8: Create Config Files

Create `states/{state_key}/config.json` and `jurisdictions.json`.

### Verification Checklist

- [ ] All categorical columns have VDOT numbered prefixes
- [ ] No unmapped values in Collision Type, Weather, Light, Surface
- [ ] Roadway Description contains road geometry (not intersection type)
- [ ] Intersection Type uses approach counts (1/2/3/4/5. ...)
- [ ] First Harmful Event uses VDOT codes (not raw state values)
- [ ] Severity distribution looks reasonable (not all O)
- [ ] GPS coverage > 90%
- [ ] Boolean flags are populated (not all No)
- [ ] State-specific detail columns have data
- [ ] Split files: county_roads < all_roads
- [ ] Pipeline is idempotent (running twice produces same output)

---

## 19. Colorado (CDOT) Complete Example

### Raw Data Profile

- **Source:** CDOT Crash Reporting Module (CRM) exports
- **Format:** 110 columns per row, one row per crash
- **Key columns:** CUID, System Code, Injury 00-04, Crash Type, MHE, Road Description, TU-1/TU-2 fields
- **Severity:** No single column -- derived from Injury 00 (O) through Injury 04 (K)
- **Data dictionary:** `CDOTRM_CD_Crash_Data_Dictionary_-_9-20-2023.csv`

### Conversion Challenges Solved

| Challenge | Solution |
|-----------|----------|
| No single severity column | Derived from Injury 00-04 counts |
| 50+ collision type values | Two-step mapping: CO -> intermediate -> VDOT numbered |
| `Road Description` = intersection type, not road geometry | Map to `Relation To Roadway`; derive `Roadway Description` from System Code |
| Combined `Dawn or Dusk` lighting | Split by military time (before/after 1200) |
| `Road Contour Curves` + `Grade` as separate fields | Combine into VDOT's 4-category alignment |
| Colorado-specific surface conditions (Icy, Slushy, "W/Visible Treatment") | Map all variants to VDOT categories |
| 42 First HE values (raw impact descriptions) | Map each to VDOT numbered codes |
| Source data typo (`Electical/Utility Box`) | Added to mapping table |
| Boolean flags from 26+ TU detail fields | Check both TU-1 and TU-2 for each flag |
| Rich detail lost in boolean reduction | Preserved as 46 `_co_*` columns |

### Douglas County Baseline Stats

```
Input:  4,323 rows (2021-2025), 110 columns
Output: 4,296 rows (27 duplicates removed), 103 columns
GPS:    99.1% coverage (147 recovered via node lookup)
Time:   ~40 seconds full pipeline
```

### Files Produced

```
data/CDOT/
  douglas_standardized.csv       # 4,296 rows, normalized
  douglas_all_roads.csv          # 4,296 rows, all roads
  douglas_county_roads.csv       # 1,061 rows, county-maintained only
  douglas_no_interstate.csv      # 3,310 rows, no interstate
  .validation/pipeline_report.json
```

---

## 20. CDOT Auto-Downloader & Merge Strategy

### Overview

The auto-downloader fetches statewide crash data from CDOT's Hyland OnBase document portal, filters it to a specific county, and saves it as a CSV that feeds into the pipeline.

```
CDOT Hyland OnBase (statewide Excel files)
        |
        v
+--------------------+     +--------------------+     +--------------------+
|  DOWNLOAD          |     |  FILTER            |     |  MERGE             |
|  Multi-strategy    |---->|  County filter     |---->|  CUID dedup        |
|  (requests/PW)     |     |  (DOUGLAS, etc.)   |     |  (append-only)     |
+--------------------+     +--------------------+     +--------------------+
        |                                                       |
        v                                                       v
  Statewide .xlsx                                   data/CDOT/{year} {county}.csv
  (discarded after                                          |
   filtering)                                               v
                                                  Pipeline auto-triggers
                                                  (process-cdot-data.yml)
```

### Three Data Entry Points

Data can enter the system through any of three paths. All three ultimately land a CSV in `data/CDOT/`, which triggers the same pipeline.

```
ENTRY 1: Auto-Download          ENTRY 2: UI Upload          ENTRY 3: Manual Drop
(GitHub Actions monthly)        (Browser upload tab)        (git push to data/CDOT/)
         |                              |                            |
         v                              v                            v
download_cdot_crash_data.py     pipeline_server.py           User drops CSV file
  - Downloads from OnBase         - Saves to data/CDOT/        into data/CDOT/
  - Filters to county            - Triggers pipeline           and pushes to main
  - CUID merge (append-only)       immediately (server-side)
  - Commits to repo
         |                              |                            |
         v                              v                            v
   Push to main branch          Pipeline runs server-side    Push triggers workflow
         |                       (Convert → Validate →               |
         |                        Geocode → Split)                   |
         v                                                           v
   process-cdot-data.yml ◄───────────────────────────────────────────┘
   (auto-triggers on CSV push)
         |
         v
   Merge all year CSVs → Convert → Validate → Geocode → Split
         |
         v
   douglas_county_roads.csv → crashes.csv → CRASH LENS loads it
```

#### Entry 1: Auto-Download (GitHub Actions)

- **Trigger:** Monthly cron (1st of month at 6 AM UTC) or manual "Run workflow" button
- **What happens:** `download_cdot_crash_data.py` downloads statewide Excel from OnBase → filters to Douglas County → CUID merge with existing CSV → commits to repo
- **Merge protection:** Final years (2021-2024) are skipped entirely. Preliminary years (2025) get merge-appended — only new CUIDs added, existing records untouched
- **After commit:** The push to `data/CDOT/` auto-triggers `process-cdot-data.yml`

#### Entry 2: UI Upload (Browser)

- **Trigger:** User uploads a CSV through the Upload tab in CRASH LENS
- **What happens:** Browser processes it instantly for dashboard display (JavaScript). If the pipeline server is running, it also saves the file to `data/CDOT/` and runs the full Python pipeline server-side
- **No CUID merge here** — the server saves the file as-is. The pipeline's own Stage 0 (merge) handles combining multiple year files during processing
- **If server is offline:** Browser-only mode — data loads in UI but isn't persisted to disk

#### Entry 3: Manual Drop (git push)

- **Trigger:** User manually places a CSV in `data/CDOT/` and pushes to main
- **What happens:** GitHub detects the new/changed CSV and auto-triggers `process-cdot-data.yml`
- **Simplest path** — just drop the file and push. No filtering or CUID merge (file is assumed to be already county-specific)

### Two Different Merges (Don't Confuse Them)

There are two merge operations in the system. They serve different purposes and happen at different stages:

| | Downloader CUID Merge | Pipeline Stage 0 Merge |
|---|---|---|
| **Where** | `download_cdot_crash_data.py` | `process_crash_data.py` (Stage 0) |
| **When** | Before CSV lands on disk | After all CSVs are on disk |
| **What it does** | Protects a single year file — appends only new crash records (by CUID) to `2025 douglas.csv` | Concatenates all year files (2021 + 2022 + 2023 + 2024 + 2025) into one big dataset |
| **Dedup logic** | CUID-based (per-year, per-county) | Simple concat (years are already clean) |
| **Applies to** | Entry 1 only (auto-download) | All entries (runs in pipeline) |

```
CUID merge (per-year file protection)      Pipeline Stage 0 (combine all years)
         |                                            |
         v                                            v
  "2025 douglas.csv"                       All 5 year files concatenated
  (1,065 existing + 47 new = 1,112)        (5K + 4.6K + 5.4K + 5.5K + 1.1K = ~21.6K rows)
         |                                            |
         v                                            v
  Stays on disk as individual file          Goes through Convert → Validate → Geocode → Split
```

### What the Pipeline Does After Any Entry

Regardless of how data got into `data/CDOT/`, the pipeline performs the same stages:

| Stage | What | Why |
|-------|------|-----|
| **0. Merge** | Combine all year CSVs (2021-2025) into one dataset | CRASH LENS needs the full history in one file |
| **1. Convert** | Map Colorado columns/values to VDOT format | CRASH LENS only understands VDOT format |
| **2. Validate** | QA/QC — fix severity, check bounds, remove duplicates | Catch data quality issues automatically |
| **3. Geocode** | Fill missing GPS coordinates (node lookup + Nominatim) | Map tab needs lat/lon for every crash |
| **4. Split** | Create 3 filtered views (all roads, county roads, no interstate) | Different analysis needs different road subsets |

The final output is `crashes.csv` (copy of `county_roads`) which CRASH LENS loads automatically.

### What You Don't Have to Worry About

| Concern | Why It's Handled |
|---------|-----------------|
| Re-downloading 2021-2024 | Skipped automatically (`status: final` + file exists) |
| Overwriting validated data | CUID merge only appends new records to preliminary years |
| Running the pipeline manually | Auto-triggers on any CSV push to `data/CDOT/` |
| Combining multiple year files | Pipeline Stage 0 merges all year CSVs automatically |
| Duplicate crashes across years | Pipeline Stage 2 deduplicates (date + GPS + collision type) |
| Missing GPS coordinates | Pipeline Stage 3 fills them (node lookup + Nominatim geocoding) |
| Updating the manifest yearly | Only manual step: add new doc ID when CDOT publishes a new year |

### Data Source: Hyland OnBase

CDOT publishes statewide crash data as Excel files on their Hyland OnBase document management system:

- **URL:** `https://oitco.hylandcloud.com/CDOTRMPop/docpop/docpop.aspx`
- **File format:** `.xlsx` (MS Excel), one file per year
- **Scope:** Entire state of Colorado (~150,000+ crashes/year)
- **Update cadence:** Annual (final), with preliminary data for current year
- **Access:** Public, no authentication required

Each year's file has a unique **doc ID** that CDOT assigns when uploading. These IDs are unpredictable and must be manually discovered from the OnBase portal.

### Source Manifest

All doc IDs are stored in `data/CDOT/source_manifest.json` — a config-driven registry that humans update when new data becomes available.

```json
{
  "files": {
    "2025": {"docid": 54973381, "status": "preliminary", "note": "Subject to revision"},
    "2024": {"docid": 35111742, "status": "final"},
    "2023": {"docid": 24805487, "status": "final"},
    "2022": {"docid": 17470642, "status": "final"},
    "2021": {"docid": 13118621, "status": "final"}
  },
  "jurisdiction_filters": {
    "douglas":  {"county": "DOUGLAS",  "fips": "08035", "display_name": "Douglas County"},
    "elpaso":   {"county": "EL PASO",  "fips": "08041", "display_name": "El Paso County"},
    "...": "all 64 Colorado counties"
  }
}
```

**Key fields:**
- `status`: `"final"` (won't change) or `"preliminary"` (CDOT may add/revise records)
- `docid`: OnBase document ID — the only way to fetch a specific year's file
- `fips`: 5-digit FIPS code (state 08 + 3-digit county)

**When to update:** When CDOT publishes a new year or changes a doc ID (usually once a year).

### Download Strategy (4-Level Cascade)

OnBase is an enterprise document portal with unpredictable response behavior. The downloader tries 4 strategies in order:

| Strategy | Method | When It Works |
|----------|--------|---------------|
| **1. Direct Request** | `requests.get(docpop.aspx?docid=X)` with browser headers | OnBase returns the Excel file directly |
| **2. HTML Parse** | Parse HTML response for download links (`PdfPop.aspx`, `GetDoc.aspx`) | OnBase returns a viewer page with embedded download link |
| **3. ActiveX Mode** | Retry with `clienttype=activex` parameter | OnBase serves different content to programmatic clients |
| **4. Playwright** | Headless Chromium renders the page, clicks download | JavaScript-rendered pages that `requests` can't handle |

Each strategy validates the response using:
- **Magic byte detection:** XLSX starts with `PK` (ZIP), XLS starts with `\xd0\xcf` (OLE2)
- **Content-Type/Disposition headers** as fallback
- **HTML/XML rejection** to prevent saving error pages as data

### Merge Strategy: Protecting Validated Data

**Problem:** You have 2021-2025 data that's already been validated, corrected, and fed through the pipeline. A naive re-download would overwrite everything.

**Solution:** The downloader uses a two-tier merge strategy based on the `status` field in the manifest:

```
                         Does CSV exist locally?
                        /                        \
                      NO                          YES
                      |                            |
                 Download fresh              Check status
                      |                     /            \
                      v                  "final"      "preliminary"
                 Save new CSV              |               |
                                       SKIP            MERGE
                                    (don't touch    (CUID dedup,
                                     validated      append only)
                                     data)
```

#### Tier 1: Skip Finalized Years

Files marked `"status": "final"` (2021-2024) that already exist locally are **not re-downloaded**. The validated data is preserved exactly as-is.

```
$ python download_cdot_crash_data.py
  2024: SKIPPED — final data already exists (2024 douglas.csv, 5,497 records)
  2023: SKIPPED — final data already exists (2023 douglas county.csv, 5,382 records)
  ...
```

Override with `--force` if you specifically need to re-download a finalized year.

#### Tier 2: CUID-Based Merge for Preliminary Years

Files marked `"status": "preliminary"` (2025) are downloaded fresh and **merged** with existing data using `CUID` as the deduplication key.

**CUID** (Crash Unique Identifier) is the first column in every CDOT crash file. Each crash report has a unique CUID that never changes.

```
Existing 2025 file:        New download:
  CUID  County  Date         CUID  County  Date
  1001  DOUGLAS 1/5/25       1001  DOUGLAS 1/5/25    ← already exists, SKIP
  1002  DOUGLAS 1/8/25       1002  DOUGLAS 1/8/25    ← already exists, SKIP
  1003  DOUGLAS 2/1/25       1003  DOUGLAS 2/1/25    ← already exists, SKIP
                              1004  DOUGLAS 3/15/25   ← NEW, APPEND
                              1005  DOUGLAS 3/20/25   ← NEW, APPEND

Result: 5 records (3 original + 2 new)
```

**Key guarantees:**
- Existing records are **never modified or overwritten**
- Only genuinely new CUIDs are appended
- If CDOT revises a record (same CUID, different data), the **original version is kept** — the change is logged but not applied
- Stats are logged: `Merge: 1,065 existing + 47 new = 1,112 total`

#### Merge Decision Matrix

| Year Status | File Exists? | `--force`? | Action |
|-------------|-------------|-----------|--------|
| `final` | Yes | No | **SKIP** — validated data untouched |
| `final` | Yes | Yes | Re-download and **REPLACE** |
| `final` | No | — | Download fresh |
| `preliminary` | Yes | No | Download + **MERGE** (CUID dedup) |
| `preliminary` | Yes | Yes | Re-download and **REPLACE** |
| `preliminary` | No | — | Download fresh |

#### What if CUID Is Missing?

If the CUID column isn't found in either the existing or new data (unlikely for CDOT, but possible for other states), the merge **falls back to full replacement** and logs a warning. This prevents silent data corruption.

### County Filtering

Each statewide Excel contains all ~150,000+ crashes across Colorado. The downloader filters to a single county:

```python
# Filter uses the County column (case-insensitive, whitespace-trimmed)
mask = df['County'].str.strip().str.upper() == 'DOUGLAS'
```

The `jurisdiction_filters` section in the manifest maps all 64 Colorado counties. This means the same downloader works for any county — just change `--jurisdiction`:

```bash
python download_cdot_crash_data.py --jurisdiction elpaso    # El Paso County
python download_cdot_crash_data.py --jurisdiction denver    # Denver County
python download_cdot_crash_data.py --statewide              # No filter (all CO)
```

### GitHub Actions Workflow

**File:** `.github/workflows/download-cdot-crash-data.yml`

#### Automatic (Monthly)

Runs on the 1st of every month at 6:00 AM UTC. Uses `--latest` to check only the most recent year for new data.

```yaml
schedule:
  - cron: '0 6 1 * *'
```

**Why monthly?** CDOT publishes annual data. Monthly checks catch preliminary-year updates without excessive runs.

#### Manual Dispatch

Go to **Actions** > **Download CDOT Crash Data** > **Run workflow**:

| Input | Default | Description |
|-------|---------|-------------|
| years | _(empty = latest)_ | Comma-separated years (e.g., `2024,2025`) |
| jurisdiction | `douglas` | Any of 64 Colorado counties |
| latest_only | `true` | Download only the most recent year |
| skip_dictionaries | `false` | Skip data dictionary download |
| force_download | `false` | Force re-download even for finalized years |

#### Workflow Steps

```
1. Checkout repo
2. Install Python + deps (requests, pandas, openpyxl, playwright)
3. Install Playwright chromium browser (for fallback strategy)
4. Build CLI arguments from workflow inputs
5. Run download_cdot_crash_data.py
6. Check for changed/new files via git diff
7. Commit + push if data changed (with retry logic)
```

#### Integration with Pipeline

The download workflow commits new/updated CSVs to `data/CDOT/`. This triggers `process-cdot-data.yml` which runs the full pipeline (Convert → Validate → Geocode → Split). The two workflows chain automatically:

```
download-cdot-crash-data.yml          process-cdot-data.yml
  (monthly cron or manual)              (auto-triggers on push)
         |                                       |
         v                                       v
  Downloads from OnBase              Detects new CSV in data/CDOT/
  Filters to county                  Merges all year files
  Merges with existing               Converts to VDOT format
  Commits CSV                        Validates, Geocodes, Splits
         |                           Commits pipeline outputs
         +--- push triggers -------->|
```

### How Data Flows Through the System

Here's the complete lifecycle from OnBase to CRASH LENS:

```
CDOT Hyland OnBase
    |
    | download_cdot_crash_data.py
    | (Strategy 1-4 cascade)
    v
Statewide .xlsx (150K+ rows)
    |
    | filter_to_jurisdiction()
    | (County == DOUGLAS)
    v
~5,000 Douglas rows
    |
    | merge_with_existing()
    | (CUID dedup, append-only)
    v
data/CDOT/2025 douglas.csv ← committed to repo
    |
    | process-cdot-data.yml auto-triggers
    v
Stage 0: Merge all year CSVs (2021-2025)
    |
    v
Stage 1: Convert (CO raw → VDOT format)
    |
    v
Stage 2: Validate (QA/QC, dedup)
    |
    v
Stage 3: Geocode (fill missing GPS)
    |
    v
Stage 4: Split (all_roads, county_roads, no_interstate)
    |
    v
data/CDOT/douglas_county_roads.csv → crashes.csv
    |
    v
CRASH LENS browser tool loads crashes.csv
```

### Test Coverage

The downloader has **152 automated tests** (`tests/test_cdot_downloader.py`):

| Test Area | Count | What It Validates |
|-----------|-------|-------------------|
| File detection | 15 | Magic bytes, HTML rejection, headers, size thresholds |
| URL extraction | 10 | Parsing download links from OnBase HTML pages |
| Excel parsing | 5 | XLSX → DataFrame conversion, corrupt file handling |
| County filtering | 12 | Case/whitespace handling, multi-word counties, NaN values |
| Manifest loading | 3 | Valid manifest, missing file, real manifest validation |
| CLI output | 2 | `--list` command formatting |
| Filename generation | 9 | County names → filenames, statewide fallback |
| End-to-end pipeline | 3 | Excel → filter → CSV → read-back roundtrip |
| Manifest integrity | 13 | All 64 counties, FIPS codes, status values |
| Playwright fallback | 2 | Availability check, ImportError handling |
| **CUID merge** | **8** | Append, no-change, all-new, preserve existing, no-CUID fallback |
| **Merge edge cases** | **6** | BOM, NaN CUIDs, duplicates, column mismatch, 10K perf |
| **Skip/force logic** | **4** | Final-skip, force-override, missing-downloads, preliminary-always |
| **Download cascade** | **5** | 4 strategies + all-fail error |
| **HTTP session** | **7** | Adapters, retries, backoff, headers |
| **Retry logic** | **8** | Timeout, connection, 429, 4xx non-retry, backoff timing |
| **Data dictionary** | **3** | Success, failure, missing description |
| **CLI parsing** | **11** | All flags + combined flags |
| **main() integration** | **4** | --list, invalid inputs, --latest selection |
| **Real data validation** | **9** | CUID uniqueness, Douglas-only, date/year match, cross-year overlap |
| **Constants** | **5** | URLs, retries, magic bytes |
| CUID actual data | 2 | CUID column exists in real data files |
| Regression | 1 | `_description` key bug fix |

Run with: `python -m pytest tests/test_cdot_downloader.py -v`

---

## Appendix A: Standardized Output Columns

### Core VDOT-Compatible Columns (51)

```
Document Nbr, Crash Date, Crash Year, Crash Military Time,
Crash Severity, K_People, A_People, B_People, C_People,
Collision Type, Weather Condition, Light Condition,
Roadway Surface Condition, Roadway Alignment,
Roadway Description, Intersection Type,
RTE Name, SYSTEM, Node, RNS MP,
x, y,
Physical Juris Name,
Pedestrian?, Bike?, Alcohol?, Speed?, Hitrun?,
Motorcycle?, Night?, Distracted?, Drowsy?, Drug Related?,
Young?, Senior?, Unrestrained?,
School Zone, Work Zone Related,
Traffic Control Type, Traffic Control Status,
Functional Class, Area Type, Facility Type, Ownership,
First Harmful Event, First Harmful Event Loc,
Relation To Roadway, Vehicle Count,
Persons Injured, Pedestrians Killed, Pedestrians Injured,
_source_state, _source_file
```

### Colorado-Specific Columns (52)

```
_co_system_code, _co_agency_id, _co_rd_number,
_co_location1, _co_location2, _co_city,
_co_total_vehicles, _co_mhe, _co_crash_type, _co_link,
_co_second_he, _co_third_he, _co_wild_animal,
_co_secondary_crash, _co_weather2, _co_lane_position,
_co_injury00_uninjured,
_co_tu1_direction, _co_tu1_movement, _co_tu1_vehicle_type,
_co_tu1_speed_limit, _co_tu1_estimated_speed, _co_tu1_stated_speed,
_co_tu1_driver_action, _co_tu1_human_factor, _co_tu1_age, _co_tu1_sex,
_co_tu2_direction, _co_tu2_movement, _co_tu2_vehicle_type,
_co_tu2_speed_limit, _co_tu2_estimated_speed, _co_tu2_stated_speed,
_co_tu2_driver_action, _co_tu2_human_factor, _co_tu2_age, _co_tu2_sex,
_co_nm1_type, _co_nm1_age, _co_nm1_sex, _co_nm1_action,
_co_nm1_movement, _co_nm1_location, _co_nm1_facility, _co_nm1_contributing_factor,
_co_nm2_type, _co_nm2_age, _co_nm2_sex, _co_nm2_action,
_co_nm2_movement, _co_nm2_location, _co_nm2_facility, _co_nm2_contributing_factor
```

---

## Appendix B: VDOT Value Reference Tables

These are the exact values used in the Henrico reference dataset. Your converted output must use these values.

### Collision Type (17 values in Henrico)

```
1. Rear End, 2. Angle, 3. Head On,
4. Sideswipe - Same Direction, 5. Sideswipe - Opposite Direction,
6. Backed Into, 7. Non-Collision (Runaway),
8. Non-Collision, 9. Fixed Object - Off Road,
10. Deer/Animal, 11. Fixed Object in Road,
12. Ped, 13. Bicycle, 14. Train,
15. Non-Collision (Other), 16. Other, 17. Unknown
```

### Weather Condition (10 values)

```
1. No Adverse Condition (Clear/Cloudy), 2. Blowing Sand/Dust,
3. Fog/Smog/Smoke, 4. Snow, 5. Rain,
6. Sleet/Hail/Freezing, 7. Blowing Sand/Dust,
8. Severe Crosswinds, 9. Other, 16. Other
```

### Light Condition (8 values)

```
1. Dawn, 2. Daylight, 3. Dusk,
4. Darkness - Road Lighted, 5. Darkness - Road Not Lighted,
6. Darkness - Unknown Lighting, 7. Other, 8. Unknown
```

### Roadway Surface Condition (11 values)

```
1. Dry, 2. Wet, 3. Snow, 4. Slush, 5. Ice,
6. Sand/Mud/Dirt/Oil/Gravel, 7. Water,
8. Other, 9. Unknown, 16. Other
```

### Roadway Alignment (4+)

```
1. Straight - Level, 2. Curve - Level,
3. Grade - Straight, 4. Grade - Curve
```

### SYSTEM (5 values)

```
VDOT Interstate, VDOT Primary, VDOT Secondary,
NonVDOT primary, NonVDOT secondary
```

---

## Appendix C: Command-Line Reference

### CDOT Auto-Downloader

```bash
# Download latest year, default county (Douglas)
python download_cdot_crash_data.py --latest

# Download all years (2021-2025)
python download_cdot_crash_data.py

# Download specific years
python download_cdot_crash_data.py --years 2024 2025

# Download for a different county
python download_cdot_crash_data.py --latest -j elpaso

# Force re-download finalized years (overrides skip)
python download_cdot_crash_data.py --force --years 2024

# Download statewide (no county filter)
python download_cdot_crash_data.py --statewide --latest

# List available years, counties, and doc IDs
python download_cdot_crash_data.py --list

# Skip data dictionary download
python download_cdot_crash_data.py --latest --no-dict

# Custom manifest and output directory
python download_cdot_crash_data.py -m /path/to/manifest.json -d /tmp/output

# Quick smoke test (list mode, no network required)
python download_cdot_crash_data.py --list
```

#### All Flags

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--years` | `-y` | all years | Specific years to download |
| `--latest` | — | off | Download only the most recent year |
| `--jurisdiction` | `-j` | `douglas` | County to filter to (any of 64 CO counties) |
| `--statewide` | — | off | Save statewide data without county filtering |
| `--force` | — | off | Force re-download even for finalized years |
| `--data-dir` | `-d` | `data/CDOT` | Output directory |
| `--manifest` | `-m` | `data/CDOT/source_manifest.json` | Path to manifest JSON |
| `--no-dict` | — | off | Skip data dictionary download |
| `--list` | `-l` | off | List available years/counties and exit |

### Full Pipeline

```bash
python scripts/process_crash_data.py -i data/CDOT/Douglas_County.csv -j douglas -s colorado -v
```

### Convert Only

```bash
python scripts/process_crash_data.py -i data/CDOT/Douglas_County.csv -j douglas --convert-only
```

### Split Only

```bash
python scripts/split_cdot_data.py -j douglas -s colorado
```

### Pipeline Server

```bash
python scripts/pipeline_server.py --port 5050

# Upload via API
curl -X POST \
  -F "state=colorado" \
  -F "jurisdiction=douglas" \
  -F "file=@data/CDOT/Douglas_County.csv" \
  http://localhost:5050/api/pipeline/run
```

### Run Downloader Tests

```bash
# Run all 152 tests
python -m pytest tests/test_cdot_downloader.py -v

# Run only merge tests
python -m pytest tests/test_cdot_downloader.py -v -k "merge"

# Run only real data validation
python -m pytest tests/test_cdot_downloader.py -v -k "RealData"
```

### Quick Verification Script

```bash
python3 -c "
from scripts.state_adapter import convert_file
state, total, gps = convert_file(
    'data/CDOT/Douglas_County.csv',
    '/tmp/test_output.csv',
    state='colorado'
)
print(f'State: {state}, Rows: {total}, GPS: {gps}')
"
```

---

## 24. Lessons Learned & Data Quality Checklist for New States

> **This section documents bugs found during the Colorado onboarding (Feb 2026) and the mandatory checks to prevent them when adding any new state.**

### Bug 1: CRITICAL — `resetState()` Missing Aggregate Properties

**What happened:** `processRow()` in `index.html` was updated to aggregate `vehicleCount`, `pedCasualties`, and `personsInjured`, but `resetState()` was NOT updated to initialize these properties. Result: `agg.vehicleCount.total++` threw a TypeError for 99.6% of rows. The try/catch silently ate the error, so `rowCount++` never executed — but the severity/route/node aggregates that were updated BEFORE the throw were kept.

**Visible symptom:** Dashboard showed "27 Total Crashes" (only the 27 rows with Vehicle Count = 0 survived) while severity counts correctly summed to 6,139.

**Prevention rule:** When adding ANY new property to `processRow()`, you MUST also add it to the `resetState()` aggregates initialization. Run the accuracy test (`tests/cdot_data_accuracy_test.py`) to verify `totalRows` matches the sum of all severity counts.

### Bug 2: HIGH — Road Type CSV Filter Used Wrong Column

**What happened:** The split script filtered `county_roads.csv` on the Virginia-normalized `SYSTEM` column or on `_co_agency_id` instead of `_co_system_code`. Since both "City Street" and "County Road" normalize to `NonVDOT secondary`, the filter included some State Highway rows (which also normalize to `Primary`) that leaked through.

**Visible symptom:** `county_roads.csv` had 201 non-county rows (162 State Highway, 35 Interstate, 4 Frontage Road). Conversely, it was MISSING most City Street rows (only 164 of 6,870).

**Prevention rule:** ALWAYS filter on the original state-specific system code column (`_co_system_code`), never on the Virginia-normalized `SYSTEM` column. Use `scripts/rebuild_road_type_csvs.py` as the reference implementation.

### Bug 3: HIGH — Wrong `crashes.csv` in Data Folder

**What happened:** `data/CDOT/crashes.csv` contained Virginia/Henrico County data (24,597 rows) instead of Colorado data. If the primary road-type CSV fetch failed, the app fell back to this file and loaded completely wrong data.

**Prevention rule:** Never commit a generic `crashes.csv` to a state data folder. The fallback path should point to `{jurisdiction}_all_roads.csv`, not a separate file. Delete stale files from previous states when onboarding a new one.

### Bug 4: MEDIUM — Ghost Rows (Empty Date/Year)

**What happened:** 392 rows in `douglas_standardized.csv` had empty `Crash Year` and `Crash Date`. These rows had empty `_co_system_code` too, so they weren't filtered by any road type. They appeared in `no_interstate` and `all_roads` but inflated counts with invalid data.

**Prevention rule:** The rebuild script must reject rows where both `Crash Year` and `Crash Date` are empty. Add this as a validation step in every pipeline.

---

### Mandatory Checklist: Adding a New State

Run these checks AFTER processing a new state's data, BEFORE deploying:

#### Data Pipeline Checks
- [ ] All 3 road-type CSVs exist: `{jurisdiction}_county_roads.csv`, `{jurisdiction}_no_interstate.csv`, `{jurisdiction}_all_roads.csv`
- [ ] No `crashes.csv` file exists in the state data folder (use road-type CSVs only)
- [ ] `county_roads ⊂ no_interstate ⊂ all_roads` (proper subset relationships)
- [ ] No ghost rows (empty Crash Year AND empty Crash Date)
- [ ] No duplicate Document Nbr values within any file
- [ ] `county_roads` contains ONLY local road system codes (no state highways or interstates)
- [ ] All severity values are exactly K/A/B/C/O (no blanks, no variations)
- [ ] GPS coverage > 90% (valid lat/lon within state bounds)
- [ ] Year distribution covers expected range (e.g., 2021-2025)
- [ ] `_co_system_code` (or equivalent) preserved for each row

#### App Integration Checks
- [ ] `resetState()` aggregates initialization includes ALL properties accessed by `processRow()`
- [ ] `totalRows` equals the sum of K+A+B+C+O severity counts
- [ ] Dashboard KPI percentages are < 100% (sanity check: K% should be < 5% for most jurisdictions)
- [ ] All 3 road type radio buttons load the correct CSV file
- [ ] Fallback path points to `{jurisdiction}_all_roads.csv`, not `crashes.csv`
- [ ] Road type filter labels use state-neutral language (not "VDOT" or "NonVDOT")
- [ ] StateAdapter correctly detects the state from CSV headers
- [ ] `config.json` `roadSystems.filterProfiles` match actual SYSTEM column values

#### Automated Test
```bash
python3 tests/cdot_data_accuracy_test.py
# Must pass 100% — any CRITICAL or HIGH failure blocks deployment
```
