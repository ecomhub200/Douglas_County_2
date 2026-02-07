# CDOT Pipeline Architecture Reference

> **Purpose:** This document captures the complete pipeline architecture used to process Colorado (CDOT) crash data. Use it as a blueprint when adding support for a new state.

---

## Table of Contents

1. [Pipeline Overview](#1-pipeline-overview)
2. [File Structure](#2-file-structure)
3. [Stage-by-Stage Walkthrough](#3-stage-by-stage-walkthrough)
4. [State Detection System](#4-state-detection-system)
5. [Column Mapping (Raw CDOT -> Standardized)](#5-column-mapping-raw-cdot---standardized)
6. [Derived Fields (Fields That Don't Exist in Raw Data)](#6-derived-fields-fields-that-dont-exist-in-raw-data)
7. [Road System Classification](#7-road-system-classification)
8. [Crash Type / Collision Mapping](#8-crash-type--collision-mapping)
9. [Boolean Flag Derivation](#9-boolean-flag-derivation)
10. [Validation Rules](#10-validation-rules)
11. [Geocoding Strategy](#11-geocoding-strategy)
12. [Split / Road-Type Filtering](#12-split--road-type-filtering)
13. [Configuration Files Required](#13-configuration-files-required)
14. [Output Files Produced](#14-output-files-produced)
15. [Execution Paths (Browser vs Server)](#15-execution-paths-browser-vs-server)
16. [Step-by-Step: Adding a New State](#16-step-by-step-adding-a-new-state)
17. [Appendix A: Raw CDOT Columns](#appendix-a-raw-cdot-columns)
18. [Appendix B: Standardized Output Columns](#appendix-b-standardized-output-columns)
19. [Appendix C: Command-Line Reference](#appendix-c-command-line-reference)

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

**Core Design Principle:** All state data is normalized to a single "Virginia-compatible" internal format. The browser tool only understands this one format. Adding a new state means writing a normalizer that transforms that state's raw CSV into the same standardized columns.

---

## 2. File Structure

```
project_root/
|
+-- scripts/                          # Python processing scripts
|   +-- process_crash_data.py         # Main pipeline orchestrator (962 lines)
|   +-- state_adapter.py              # State detection + normalization (642 lines)
|   +-- split_cdot_data.py            # Road-type filtering (243 lines)
|   +-- pipeline_server.py            # HTTP server for browser uploads (361 lines)
|
+-- states/                           # Per-state configuration
|   +-- colorado/
|   |   +-- config.json               # Column mappings, derived fields, road systems, bounds
|   |   +-- jurisdictions.json        # County definitions (FIPS, bbox, cities, agencies)
|   +-- virginia/
|   |   +-- config.json               # Virginia config (reference baseline)
|   +-- state_adapter.js              # Browser-side normalization (JS version)
|   +-- fips_database.js              # FIPS code lookups
|   +-- us_counties_db.js             # US county database
|   +-- INTEGRATION_GUIDE.md          # Integration guide for browser
|
+-- data/
|   +-- CDOT/                         # Colorado data folder (named after DOT)
|   |   +-- *.csv                     # Raw input files
|   |   +-- douglas_standardized.csv  # Stage 1 output
|   |   +-- douglas_all_roads.csv     # Stage 4 output
|   |   +-- douglas_county_roads.csv  # Stage 4 output
|   |   +-- douglas_no_interstate.csv # Stage 4 output
|   |   +-- .validation/
|   |       +-- pipeline_report.json  # Processing report
|   +-- crashes.csv                   # Default fallback (copy of county_roads)
|
+-- app/
    +-- index.html                    # Browser UI with inline pipeline JS
```

---

## 3. Stage-by-Stage Walkthrough

### Stage 0: MERGE (Optional)

**Script:** `process_crash_data.py` -> `stage_merge()`
**When:** Multiple input files (e.g., one CSV per year)
**What it does:** Concatenates CSVs, keeping only the header from the first file
**Output:** `{jurisdiction}_merged_raw.csv`

```bash
# Example: merge 4 years of Douglas County data
python process_crash_data.py -i "data/CDOT/202*.csv" -j douglas --merge
```

**Skip if:** You have a single input file.

---

### Stage 1: CONVERT (Normalization)

**Script:** `state_adapter.py` -> `convert_file()` + `ColoradoNormalizer.normalize_row()`
**What it does:**
1. Auto-detects state format from CSV headers
2. Instantiates the correct normalizer class
3. Transforms every row to standardized Virginia-compatible format
4. Tracks GPS coordinate coverage

**Output:** `{jurisdiction}_standardized.csv` (70+ columns)

**This is the most critical stage.** Each row goes through:

```
Raw CDOT Row (48+ columns)
    |
    +-- Map direct columns (CUID -> Document Nbr, etc.)
    +-- Derive severity from Injury 00-04 counts
    +-- Map collision type via COLLISION_MAP
    +-- Map road system via ROAD_SYSTEM_MAP
    +-- Build route name from System Code + Rd_Number + Location 1
    +-- Build intersection Node ID from Location 1 + Location 2
    +-- Derive 13 boolean flags (ped, bike, alcohol, speed, etc.)
    +-- Preserve original columns with _co_ prefix
    |
    v
Standardized Row (57 columns)
```

---

### Stage 2: VALIDATE (QA/QC)

**Script:** `process_crash_data.py` -> `stage_validate()`
**What it does:** Quality checks with auto-correction

| Check | Action |
|-------|--------|
| Severity not in K/A/B/C/O | Auto-correct (F->K, P->O) |
| Year outside 2015-current | Flag as issue |
| Coordinates out of state bounds | Flag as out-of-bounds |
| Lat/lon transposed | Auto-swap |
| Fatal crash (K) with K_People=0 | Set K_People=1 |
| Ped collision but Pedestrian?=No | Set Pedestrian?=Yes |
| Bike collision but Bike?=No | Set Bike?=Yes |
| Duplicate rows (date+location+type) | Remove |
| Boolean inconsistency (Y vs Yes) | Normalize to Yes/No |

**Output:** Validated CSV + `.validation/pipeline_report.json`

**Sample report:**
```json
{
  "timestamp": "2026-02-06T22:36:06.525535Z",
  "state": "colorado",
  "jurisdiction": "douglas",
  "input_rows": 4323,
  "output_rows": 4296,
  "corrections": 0,
  "issues": 0,
  "duplicates_removed": 27,
  "gps_coverage": "95.7%"
}
```

---

### Stage 3: GEOCODE (Fill Missing GPS)

**Script:** `process_crash_data.py` -> `stage_geocode()`
**What it does:** Two strategies applied sequentially:

1. **Node Lookup** -- Rows with GPS at known intersection Nodes form a lookup table. Rows missing GPS but sharing the same Node ID get coordinates copied.
2. **Nominatim/OpenStreetMap** -- Free geocoding service, querying `"{Location 1} and {Location 2}, {jurisdiction}, {state}"`. Rate-limited to 1 req/sec.

**Only runs in server pipeline** (Python path). Browser path skips this.

---

### Stage 4: SPLIT (Road-Type Filtering)

**Script:** `split_cdot_data.py` + `process_crash_data.py` -> `stage_split()`
**What it does:** Creates three filtered views per jurisdiction.

**Colorado filtering logic:**

| Output File | Filter |
|-------------|--------|
| `{jurisdiction}_all_roads.csv` | No filter (everything) |
| `{jurisdiction}_county_roads.csv` | Agency Id matches county agency code |
| `{jurisdiction}_no_interstate.csv` | System Code != "Interstate Highway" |

**Agency-to-county mapping:**
```python
COUNTY_AGENCY_MAP = {
    'douglas':  'DSO',   # Douglas County Sheriff's Office
    'arapahoe': 'ASO',
    'jefferson': 'JSO',
    'elpaso':   'EPSO',
    'denver':   'DPD',
    'adams':    'ACSO',
}
```

Also copies `county_roads.csv` to `data/crashes.csv` as the UI default fallback.

---

## 4. State Detection System

**File:** `state_adapter.py` -> `StateDetector`

The pipeline auto-detects which state a CSV came from by examining column headers against known signatures.

### Signature Definitions

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

### Detection Logic

1. Read CSV headers
2. For each known state: check if ALL `required` columns exist
3. If exact match found -> return that state key
4. If no exact match: calculate partial match score (required columns found / total required)
5. Score > 50% -> return that state as a tentative match
6. Otherwise -> return `'unknown'`

### Adding a new state detection

Add a new entry to `STATE_SIGNATURES` with 3-4 columns that are unique to that state's CSV format. Choose columns that NO other state would have.

---

## 5. Column Mapping (Raw CDOT -> Standardized)

These are the direct column renames (1-to-1 mapping):

| Raw CDOT Column | Standardized Column | Notes |
|-----------------|---------------------|-------|
| `CUID` | `Document Nbr` | Unique crash ID |
| `Crash Date` | `Crash Date` | Same name, format M/D/YYYY |
| `Crash Time` | `Crash Military Time` | Same name |
| `Latitude` | `y` | Virginia convention: y = latitude |
| `Longitude` | `x` | Virginia convention: x = longitude |
| `County` | `Physical Juris Name` | Jurisdiction name |
| `Injury 04` | `K_People` | Fatal count |
| `Injury 03` | `A_People` | Serious injury count |
| `Injury 02` | `B_People` | Minor injury count |
| `Injury 01` | `C_People` | Possible injury count |
| `Number Injured` | `Persons Injured` | Total injured |
| `Road Condition` | `Roadway Surface Condition` | Surface condition |
| `Lighting Conditions` | `Light Condition` | Lighting |
| `Weather Condition` | `Weather Condition` | Same name |
| `Construction Zone` | `Work Zone Related` | Work zone flag |
| `School Zone` | `School Zone` | Same name |
| `First HE` | `First Harmful Event` | First harmful event |

### Preserved Colorado-Specific Columns (with `_co_` prefix)

| Preserved Column | Source |
|-----------------|--------|
| `_co_system_code` | `System Code` |
| `_co_agency_id` | `Agency Id` |
| `_co_rd_number` | `Rd_Number` |
| `_co_location1` | `Location 1` |
| `_co_location2` | `Location 2` |
| `_co_city` | `City` |
| `_source_state` | Always `"colorado"` |
| `_source_file` | Input filename |

---

## 6. Derived Fields (Fields That Don't Exist in Raw Data)

These fields must be **computed** because CDOT data doesn't have them directly.

### Severity (Most Critical Derivation)

Colorado has NO single severity column. Derive from highest injury level:

```
If Injury 04 > 0 -> K (Fatal)
Else if Injury 03 > 0 -> A (Suspected Serious Injury)
Else if Injury 02 > 0 -> B (Suspected Minor Injury)
Else if Injury 01 > 0 -> C (Possible Injury)
Else -> O (Property Damage Only)
```

### Year

Extracted from `Crash Date` (format `M/D/YYYY`):
```
"3/15/2023" -> "2023"
```

### Route Name (RTE Name)

Built from multiple fields based on road system:

| System Code | Route Name Construction | Example |
|-------------|------------------------|---------|
| Interstate Highway | `I-{Rd_Number}` (strip trailing letter) | `I-25` |
| State Highway | `Location 1` or `CO-{Rd_Number}` | `S PARKER RD` |
| Frontage Road | `{Location 1} (Frontage)` | `I-25 FRONTAGE (Frontage)` |
| County Road | `Location 1` | `CASTLE PINES PKWY` |
| City Street | `Location 1` | `PLUM CREEK BLVD` |

### Node (Intersection ID)

Built from intersection location fields:
```
If Road Description in ("At Intersection", "Intersection Related", "Roundabout"):
    Node = "{Location 1} & {Location 2}" (alphabetically sorted)
Else:
    Node = "" (non-intersection crash)
```

### Road System (SYSTEM)

Mapped via `ROAD_SYSTEM_MAP`:

| Colorado System Code | -> Standardized SYSTEM |
|---------------------|------------------------|
| City Street | NonVDOT secondary |
| County Road | NonVDOT secondary |
| State Highway | Primary |
| Frontage Road | Secondary |
| Interstate Highway | Interstate |

### Collision Type

Mapped via `COLLISION_MAP` from `Crash Type` or fallback `MHE`:

| Colorado Crash Type | -> Standardized Collision Type |
|--------------------|-----------------------------|
| Rear-End | Rear End |
| Broadside | Angle |
| Approach Turn | Angle |
| Head-On | Head On |
| Sideswipe Same Direction | Sideswipe - Same Direction |
| Sideswipe Opposite Direction | Sideswipe - Opposite Direction |
| Overturning/Rollover | Non-Collision |
| Pedestrian | Pedestrian |
| Bicycle/Motorized Bicycle | Bicyclist |
| Wild Animal | Other Animal |
| Tree, Guardrail, Pole, etc. | Fixed Object - Off Road |
| Vehicle Debris or Cargo | Fixed Object in Road |

### Intersection Type

Mapped via `INTERSECTION_MAP` from `Road Description`:

| Colorado Road Description | -> Standardized Intersection Type |
|--------------------------|----------------------------------|
| Non-Intersection | Non-Intersection |
| At Intersection | Intersection |
| Intersection Related | Intersection |
| Driveway Access Related | Driveway |
| Ramp / Ramp-related | Ramp |
| Roundabout | Roundabout |
| Railroad Crossing Related | Railroad Crossing |

### Roadway Alignment

Derived from `Road Contour Curves` + `Road Contour Grade`:
```
If curves != "Straight" -> "Curve"
Else if grade != "Level" -> "Grade"
Else -> "Straight/Level"
```

---

## 7. Road System Classification

### Colorado Road Systems

```json
{
  "City Street":        { "category": "local",      "isInterstate": false },
  "County Road":        { "category": "local",      "isInterstate": false },
  "State Highway":      { "category": "state",      "isInterstate": false },
  "Frontage Road":      { "category": "state",      "isInterstate": false },
  "Interstate Highway": { "category": "interstate", "isInterstate": true  }
}
```

### Filter Profiles (3 standard views)

| Profile | What's Included | Use Case |
|---------|----------------|----------|
| `countyOnly` | City Street + County Road | Locally-maintained roads only |
| `countyPlusState` | Above + State Highway + Frontage Road | All non-interstate |
| `allRoads` | Everything including Interstate | Complete picture |

### Douglas County Route Distribution

```
City Street:          1,142 crashes (26.4%)
County Road:          1,037 crashes (24.0%)
State Highway:        1,143 crashes (26.4%)
Interstate Highway:     992 crashes (22.9%)
Frontage Road:            8 crashes (0.2%)
```

---

## 8. Crash Type / Collision Mapping

Full mapping from Colorado `Crash Type` / `MHE` to standardized `Collision Type`:

```
Rear-End                                    -> Rear End
Broadside                                   -> Angle
Head-On                                     -> Head On
Sideswipe Same Direction                    -> Sideswipe - Same Direction
Sideswipe Opposite Direction                -> Sideswipe - Opposite Direction
Approach Turn                               -> Angle
Overtaking Turn                             -> Angle
Overturning/Rollover                        -> Non-Collision
Pedestrian                                  -> Pedestrian
Bicycle/Motorized Bicycle                   -> Bicyclist
Wild Animal                                 -> Other Animal
Parked Motor Vehicle                        -> Other
Light Pole/Utility Pole                     -> Fixed Object - Off Road
Concrete Highway Barrier                    -> Fixed Object - Off Road
Guardrail Face                              -> Fixed Object - Off Road
Guardrail End                               -> Fixed Object - Off Road
Cable Rail                                  -> Fixed Object - Off Road
Tree                                        -> Fixed Object - Off Road
Fence                                       -> Fixed Object - Off Road
Sign                                        -> Fixed Object - Off Road
Curb                                        -> Fixed Object - Off Road
Embankment                                  -> Fixed Object - Off Road
Ditch                                       -> Fixed Object - Off Road
Large Rocks or Boulder                      -> Fixed Object - Off Road
Electrical/Utility Box                      -> Fixed Object - Off Road
Vehicle Debris or Cargo                     -> Fixed Object in Road
Other Fixed Object (Describe in Narrative)  -> Fixed Object - Off Road
Other Non-Fixed Object (Describe ...)       -> Other
Other Non-Collision                         -> Non-Collision
```

**Unmapped values** default to the raw value passed through.

---

## 9. Boolean Flag Derivation

Colorado derives all boolean flags from Traffic Unit (TU) fields. Each flag checks TU-1 and TU-2 columns.

| Flag | How Derived | Source Columns |
|------|-------------|---------------|
| `Pedestrian?` | TU NM Type contains "Pedestrian" OR Crash Type = "Pedestrian" | `TU-1 NM Type`, `TU-2 NM Type`, `Crash Type` |
| `Bike?` | TU NM Type contains "Bicycle" | `TU-1 NM Type`, `TU-2 NM Type` |
| `Alcohol?` | TU Alcohol Suspected in {Yes-SFST, Yes-BAC, Yes-Both, Yes-Observation} | `TU-1 Alcohol Suspected`, `TU-2 Alcohol Suspected` |
| `Speed?` | TU Driver Action in {Too Fast for Conditions, Exceeded Speed Limit} | `TU-1 Driver Action`, `TU-2 Driver Action` |
| `Hitrun?` | TU Hit And Run = TRUE | `TU-1 Hit And Run`, `TU-2 Hit And Run` |
| `Motorcycle?` | TU Type = "Motorcycle" | `TU-1 Type`, `TU-2 Type` |
| `Night?` | Lighting in {Dark-Lighted, Dark-Unlighted, Dark-Lighted, Dark-Unlighted} | `Lighting Conditions` |
| `Distracted?` | Driver Action or Human Factor in distraction set | `TU-1 Driver Action`, `TU-1 Human Contributing Factor`, etc. |
| `Drowsy?` | Human Factor in {Asleep/Fatigued, Fatigued/Asleep, Ill/Asleep/Fatigued} | `TU-1 Human Contributing Factor`, `TU-2 Human Contributing Factor` |
| `Drug Related?` | Marijuana or Drugs Suspected in positive set | `TU-1 Marijuana Suspected`, `TU-1 Other Drugs Suspected`, etc. |
| `Young?` | Any TU Age between 16-20 | `TU-1 Age`, `TU-2 Age` |
| `Senior?` | Any TU Age >= 65 | `TU-1 Age`, `TU-2 Age` |
| `Unrestrained?` | Safety Restraint Use in {Not Used, Improperly Used} | `TU-1 Safety restraint Use`, `TU-2 Safety restraint Use` |

**All booleans output as `"Yes"` or `"No"` (string).**

---

## 10. Validation Rules

### State Coordinate Bounds

```json
{
  "colorado": { "latMin": 36.99, "latMax": 41.01, "lonMin": -109.06, "lonMax": -102.04 },
  "virginia": { "latMin": 36.5,  "latMax": 39.5,  "lonMin": -83.7,   "lonMax": -75.2  }
}
```

### Validation Checks (Applied in Order)

1. **Format normalization** -- Strip whitespace, normalize case
2. **Severity validation** -- Must be K/A/B/C/O; auto-correct F->K, P->O
3. **Date validation** -- Year must be 2015 to current year
4. **Coordinate bounds** -- Must fall within state bounds (above)
5. **Transposed coordinate detection** -- If lat/lon are swapped but fall within bounds when corrected, auto-swap
6. **Boolean normalization** -- Y/N/TRUE/FALSE -> Yes/No
7. **Cross-field consistency:**
   - Fatal (K) crash must have K_People > 0
   - Pedestrian collision must have Pedestrian? = Yes
   - Bicycle collision must have Bike? = Yes
8. **Duplicate detection** -- Same date + coordinates + collision type -> remove
9. **Injury count normalization** -- Ensure non-negative integers

---

## 11. Geocoding Strategy

**Only available in server pipeline (Python).**

### Strategy 1: Node Lookup (Fast, Free, No API)

1. Scan all rows with valid GPS coordinates
2. Build a lookup: `{ Node_ID: (lat, lon) }`
3. For rows missing GPS but having a known Node ID, copy coordinates
4. Cache saved to `data/.validation/geocache/node_coordinates.json`

### Strategy 2: Nominatim / OpenStreetMap (Slow, Free, Rate-Limited)

1. For remaining rows without GPS
2. Query: `"{Location 1} and {Location 2}, {jurisdiction}, {state}"`
3. Rate limit: 1 request per second (free tier compliance)
4. Results cached in memory per session

---

## 12. Split / Road-Type Filtering

### Three Output Files Per Jurisdiction

| File | Description | Colorado Filter | Virginia Filter |
|------|-------------|----------------|-----------------|
| `*_all_roads.csv` | Everything | No filter | No filter |
| `*_county_roads.csv` | County-maintained only | `Agency Id` matches county code | `SYSTEM` in {NonVDOT secondary, NONVDOT, Non-VDOT} |
| `*_no_interstate.csv` | No interstates | `System Code` != "Interstate Highway" | `SYSTEM` != "Interstate" |

### Colorado County Agency Codes

```
douglas   -> DSO  (Douglas County Sheriff's Office)
arapahoe  -> ASO
jefferson -> JSO
elpaso    -> EPSO
denver    -> DPD
adams     -> ACSO
```

**For standardized files**, the `_co_agency_id` preserved column is used for filtering.

---

## 13. Configuration Files Required

For each state, you need two config files under `states/{state_key}/`:

### config.json (Required)

```json
{
  "state": {
    "name": "State Name",
    "abbreviation": "XX",
    "fips": "00",
    "dotName": "XDOT",
    "dotFullName": "State Department of Transportation",
    "coordinateBounds": {
      "latMin": 0.0, "latMax": 0.0,
      "lonMin": 0.0, "lonMax": 0.0
    },
    "dataDir": "XDOT"
  },

  "columnMapping": {
    "ID": "their_crash_id_column",
    "DATE": "their_date_column",
    "SEVERITY": "their_severity_column",
    "ROUTE": "their_route_column",
    "LAT": "their_latitude_column",
    "LON": "their_longitude_column"
    // ... full mapping (see colorado/config.json for complete example)
  },

  "derivedFields": {
    "SEVERITY": {
      "method": "direct|fromInjuryCounts|custom",
      "description": "How severity is obtained",
      "sources": ["col1", "col2"]
    }
    // ... one entry per field that needs derivation
  },

  "roadSystems": {
    "values": {
      "Their System Value": {
        "category": "local|state|interstate",
        "isStateDOT": true/false,
        "isInterstate": true/false,
        "displayName": "Display Name"
      }
    },
    "filterProfiles": {
      "countyOnly": { "systemValues": ["..."] },
      "countyPlusState": { "systemValues": ["..."] },
      "allRoads": { "systemValues": ["..."] }
    }
  },

  "crashTypeMapping": {
    "Their Crash Type": "Standardized Collision Type"
  },

  "epdoWeights": { "K": 462, "A": 62, "B": 12, "C": 5, "O": 1 },

  "validValues": {
    "severity": { "K": "Fatal", "A": "Serious", "B": "Minor", "C": "Possible", "O": "PDO" }
  }
}
```

### jurisdictions.json (Required for Multi-County Support)

```json
{
  "defaults": {
    "jurisdiction": "county_key",
    "filterProfile": "countyOnly"
  },
  "jurisdictions": {
    "county_key": {
      "name": "County Name",
      "type": "county",
      "fips": "000",
      "stateCountyFips": "00000",
      "namePatterns": ["COUNTY", "County Name"],
      "mapCenter": [lat, lon],
      "mapZoom": 11,
      "bbox": [west, south, east, north],
      "cities": ["CITY1", "CITY2"]
    }
  }
}
```

---

## 14. Output Files Produced

After running the full pipeline for jurisdiction `douglas`:

```
data/CDOT/
  douglas_standardized.csv       # Stage 1: Normalized format (1.5 MB)
  douglas_all_roads.csv          # Stage 4: Complete dataset (1.5 MB)
  douglas_county_roads.csv       # Stage 4: County roads only (383 KB)
  douglas_no_interstate.csv      # Stage 4: No interstate (1.2 MB)
  .validation/
    pipeline_report.json         # Processing statistics

data/
  crashes.csv                    # Copy of county_roads (UI default fallback)
```

---

## 15. Execution Paths (Browser vs Server)

### Path A: Browser-Only (JavaScript in index.html)

```
User uploads CSV in Upload tab
    |
    v
Papa.parse reads CSV in chunks
    |
    v
StateAdapter.detect(headers)  -- auto-detect state
    |
    v
StateAdapter.normalizeRow(row) -- per-row transformation
    |
    v
processRow(normalizedRow) -- build aggregates + sampleRows
    |
    v
Data cached in IndexedDB -> UI loads Dashboard
```

**Pros:** Fast, no server needed, works offline
**Cons:** No geocoding, no file output, no split files

### Path B: Server Pipeline (Python)

```
POST /api/pipeline/run (file + state + jurisdiction)
    |
    v
pipeline_server.py saves temp file
    |
    v
Background thread runs process_crash_data.py
    |
    v
Stage 0 -> 1 -> 2 -> 3 -> 4
    |
    v
Output files written to data/{DOT}/
Client polls GET /api/pipeline/status
```

**Pros:** Full geocoding, validation report, persistent output files
**Cons:** Requires Python + server running

### Server API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Server health check |
| GET | `/api/pipeline/status` | Current pipeline progress |
| GET | `/api/pipeline/states` | List supported states |
| POST | `/api/pipeline/run` | Upload file and start processing |

---

## 16. Step-by-Step: Adding a New State

### What You Need

1. A sample CSV export from the new state's DOT
2. The state's data dictionary (column definitions)
3. State FIPS code and coordinate bounding box
4. Knowledge of their road system classification

### Steps

#### Step 1: Create State Config Directory

```
states/{state_key}/
  config.json
  jurisdictions.json
```

Use `states/colorado/config.json` as your template. Fill in:
- `state.*` metadata (name, abbreviation, FIPS, DOT name, coordinate bounds)
- `columnMapping` -- map their column names to internal field codes
- `derivedFields` -- document how each derived field is computed
- `roadSystems` -- classify their road types into local/state/interstate
- `crashTypeMapping` -- map their collision types to standardized types
- `validValues` -- enumerate their valid values for key fields

#### Step 2: Add Detection Signature

In `scripts/state_adapter.py`, add to `STATE_SIGNATURES`:

```python
STATE_SIGNATURES['newstate'] = {
    'required': ['UniqueCol1', 'UniqueCol2', 'UniqueCol3'],  # 3-4 columns unique to this state
    'optional': ['OptionalCol1'],
    'display_name': 'State Name (DOT Name)',
    'config_dir': 'newstate'
}
```

Pick columns that ONLY this state's CSV would have.

#### Step 3: Create Normalizer Class

In `scripts/state_adapter.py`, create a new class:

```python
class NewStateNormalizer(BaseNormalizer):
    # Define mapping dictionaries as class constants
    COLLISION_MAP = { ... }
    ROAD_SYSTEM_MAP = { ... }

    def normalize_row(self, row: Dict[str, str]) -> Dict[str, str]:
        """Transform one raw row to standardized format."""
        out = {}

        # 1. Direct column renames
        out['Document Nbr'] = row.get('their_id_col', '')
        out['Crash Date'] = row.get('their_date_col', '')

        # 2. Derive severity
        out['Crash Severity'] = self._derive_severity(row)

        # 3. Map collision type
        raw_type = row.get('their_collision_col', '')
        out['Collision Type'] = self.COLLISION_MAP.get(raw_type, raw_type)

        # 4. Map road system
        raw_system = row.get('their_system_col', '')
        out['SYSTEM'] = self.ROAD_SYSTEM_MAP.get(raw_system, raw_system)

        # 5. Build route name
        out['RTE Name'] = self._build_route_name(row)

        # 6. Coordinates (x=longitude, y=latitude -- Virginia convention!)
        out['x'] = row.get('their_lon_col', '')
        out['y'] = row.get('their_lat_col', '')

        # 7. Boolean flags
        out['Pedestrian?'] = 'Yes' if self._check_pedestrian(row) else 'No'
        # ... repeat for all 13 boolean flags

        # 8. Preserve original columns
        out['_source_state'] = 'newstate'
        out['_ns_original_col'] = row.get('their_col', '')

        return out
```

#### Step 4: Register Normalizer

In `scripts/state_adapter.py`:

```python
_NORMALIZERS['newstate'] = NewStateNormalizer
```

#### Step 5: Add Split Logic

In `scripts/split_cdot_data.py`, add the new state's county/interstate filtering rules:

```python
# In detect_format():
if '_ns_original_col' in headers:
    return 'standardized_newstate'

# In split_data():
elif fmt == 'standardized_newstate':
    county_rows = [r for r in rows if r.get('_ns_county_col') == county_value]
    no_interstate = [r for r in rows if r.get('SYSTEM') != 'Interstate']
```

#### Step 6: Add Browser-Side Adapter (Optional)

In `states/state_adapter.js`, add the detection signature and normalizer for browser-side processing.

#### Step 7: Update Pipeline UI

In `app/index.html`, add the state to the `PIPELINE_STATE_MAP`:

```javascript
const PIPELINE_STATE_MAP = {
    '08': { key: 'colorado', name: 'Colorado (CO)', dotName: 'CDOT' },
    '51': { key: 'virginia', name: 'Virginia (VA)', dotName: 'VDOT' },
    'XX': { key: 'newstate', name: 'State Name (XX)', dotName: 'XDOT' },
};
```

#### Step 8: Test

```bash
# Run full pipeline
python scripts/process_crash_data.py \
    -i "data/XDOT/sample.csv" \
    -s newstate \
    -j jurisdiction_name \
    -v

# Verify output
head -2 data/XDOT/jurisdiction_standardized.csv
wc -l data/XDOT/jurisdiction_*.csv
cat data/XDOT/.validation/pipeline_report.json
```

Verify:
- [ ] Severity distribution looks reasonable (not all O)
- [ ] GPS coverage percentage matches expectations
- [ ] Collision type distribution has recognizable categories
- [ ] Route names are meaningful
- [ ] Boolean flags are populated (not all No)
- [ ] Split files have correct row counts
- [ ] county_roads < all_roads (some filtering happened)
- [ ] No duplicate function names introduced

---

## Appendix A: Raw CDOT Columns

Full list of columns in a raw CDOT CSV export (48 columns):

```
CUID, System Code, Rd_Number, Rd_Section, City_Street,
Crash Date, Crash Time, Agency Id, City, County,
Latitude, Longitude, Location 1, Link, Location 2,
Location, Road Description, First HE, Second HE, Third HE,
Fourth HE, MHE, Crash Type, Approach Overtaking Turn, Wild Animal,
Number Killed, Number Injured, Injury 00, Injury 01, Injury 02,
Injury 03, Injury 04, Total Vehicles, Secondary Crash, Construction Zone,
School Zone, Road Contour Curves, Road Contour Grade, Road Condition,
Lighting Conditions, Weather Condition, Weather Condition 2, Lane Position,
TU-1 Direction, TU-2 Direction, TU-1 Movement, TU-2 Movement,
TU-1 Type, TU-2 Type, TU-1 Special Function, TU-2 Special Function,
TU-1 Speed Limit, TU-1 Estimated Speed, TU-2 Speed Limit, TU-2 Estimated Speed,
TU-1 Driver Action, TU-2 Driver Action,
TU-1 Human Contributing Factor, TU-2 Human Contributing Factor,
TU-1 Age, TU-2 Age, TU-1 Sex, TU-2 Sex,
TU-1 Alcohol Suspected, TU-2 Alcohol Suspected,
TU-1 Marijuana Suspected, TU-2 Marijuana Suspected,
TU-1 Other Drugs Suspected, TU-2 Other Drugs Suspected,
TU-1 Hit And Run, TU-2 Hit And Run,
TU-1 NM Type, TU-2 NM Type, TU-1 NM Age, TU-2 NM Age,
TU-1 Safety restraint Use, TU-2 Safety restraint Use,
Record Status, Processing Status, Last Updated
```

---

## Appendix B: Standardized Output Columns

Full list of columns in the standardized output (57 columns):

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
Persons Injured, Pedestrians Killed, Pedestrians Injured,
_source_state,
_co_system_code, _co_agency_id, _co_rd_number,
_co_location1, _co_location2, _co_city,
_source_file
```

---

## Appendix C: Command-Line Reference

### process_crash_data.py

```bash
# Full pipeline (auto-detect state)
python scripts/process_crash_data.py -i data/CDOT/Douglas_County.csv -j douglas

# Explicit state
python scripts/process_crash_data.py -i data/CDOT/Douglas_County.csv -s colorado -j douglas

# Merge multiple year files
python scripts/process_crash_data.py -i "data/CDOT/202*.csv" -j douglas --merge

# Convert only (skip validate/geocode/split)
python scripts/process_crash_data.py -i data/CDOT/Douglas_County.csv -j douglas --convert-only

# Skip specific stages
python scripts/process_crash_data.py -i data/CDOT/Douglas_County.csv -j douglas --skip-geocode
python scripts/process_crash_data.py -i data/CDOT/Douglas_County.csv -j douglas --skip-split

# Dry run (preview without writing)
python scripts/process_crash_data.py -i data/CDOT/Douglas_County.csv -j douglas --dry-run

# Verbose logging
python scripts/process_crash_data.py -i data/CDOT/Douglas_County.csv -j douglas -v

# Force overwrite existing files
python scripts/process_crash_data.py -i data/CDOT/Douglas_County.csv -j douglas -f
```

### split_cdot_data.py

```bash
# Auto-detect source file
python scripts/split_cdot_data.py -j douglas

# Explicit source
python scripts/split_cdot_data.py -j douglas --source data/CDOT/douglas_standardized.csv

# Explicit state
python scripts/split_cdot_data.py -j douglas -s colorado
```

### pipeline_server.py

```bash
# Start server
python scripts/pipeline_server.py --port 5050

# Custom host/port
python scripts/pipeline_server.py --host 127.0.0.1 --port 8080
```

### Server API Usage

```bash
# Health check
curl http://localhost:5050/health

# List supported states
curl http://localhost:5050/api/pipeline/states

# Check pipeline status
curl http://localhost:5050/api/pipeline/status

# Upload and process
curl -X POST \
  -F "state=colorado" \
  -F "jurisdiction=douglas" \
  -F "file=@data/CDOT/Douglas_County.csv" \
  http://localhost:5050/api/pipeline/run
```
