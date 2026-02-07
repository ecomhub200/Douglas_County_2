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
17. [Step-by-Step: Adding a New State](#17-step-by-step-adding-a-new-state)
18. [Colorado (CDOT) Complete Example](#18-colorado-cdot-complete-example)
19. [Appendix A: Standardized Output Columns](#appendix-a-standardized-output-columns)
20. [Appendix B: VDOT Value Reference Tables](#appendix-b-vdot-value-reference-tables)
21. [Appendix C: Command-Line Reference](#appendix-c-command-line-reference)

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
+-- data/
|   +-- {DOT_NAME}/                   # State data folder (e.g., CDOT, TxDOT)
|   |   +-- *.csv                     # Raw input + processed output
|   |   +-- .validation/
|   |       +-- pipeline_report.json  # Processing report
|   +-- crashes.csv                   # Default active dataset for browser tool
|   +-- henrico_all_roads.csv         # VDOT REFERENCE dataset (Henrico County, VA)
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

Node lookup + Nominatim. See [Section 13](#13-geocoding-strategy).

### Stage 4: SPLIT (Road-Type Filtering)

Creates 3 filtered views. See [Section 14](#14-split--road-type-filtering).

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

Three output files per jurisdiction:

| File | Colorado Filter | Virginia Filter |
|------|----------------|-----------------|
| `*_all_roads.csv` | No filter | No filter |
| `*_county_roads.csv` | `_co_agency_id` matches county code | `SYSTEM` in NonVDOT |
| `*_no_interstate.csv` | `_co_system_code` != "Interstate Highway" | `SYSTEM` != "Interstate" |

### Colorado County Agency Codes

```
douglas -> DSO    arapahoe -> ASO    jefferson -> JSO
elpaso  -> EPSO   denver   -> DPD    adams     -> ACSO
```

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

### Path A: Browser-Only (JavaScript)

User uploads CSV -> StateAdapter.js detects state -> normalizes per-row -> builds aggregates

### Path B: Server Pipeline (Python)

POST /api/pipeline/run -> process_crash_data.py -> Stage 0-4 -> output files

---

## 17. Step-by-Step: Adding a New State

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

## 18. Colorado (CDOT) Complete Example

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
