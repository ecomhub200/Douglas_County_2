# Crash Lens — Universal Data Pipeline: Download to R2 Storage

> **SUPERSEDED:** This document (v1.0) has been superseded by **[Unified-Pipeline-Architecture.md](./Unified-Pipeline-Architecture.md)** (v5.1). The v5.1 document contains all content from this document plus the unified two-workflow architecture, scope-aware processing, CSV aggregation, incremental caching, and full implementation status. **Use v5.1 for all new work.** This file is retained for historical reference only.

**Version:** 1.0 (Superseded)
**Last Updated:** February 2026
**Superseded By:** `Unified-Pipeline-Architecture.md` v5.1
**Purpose:** Single reference document for building a complete state data pipeline from raw crash data download through Cloudflare R2 storage upload. Follow this document step-by-step when onboarding any new state.

**Working Implementations:** Colorado (CDOT), Virginia (VDOT)

---

## Table of Contents

1. [Pipeline Overview](#1-pipeline-overview)
2. [Prerequisites — What You Need Before Starting](#2-prerequisites)
3. [Folder Structure — Files to Create Per State](#3-folder-structure)
4. [Stage 0: Download Raw Data](#4-stage-0-download)
5. [Stage 1: Merge (Optional)](#5-stage-1-merge)
6. [Stage 2: Convert / Normalize](#6-stage-2-convert)
7. [Stage 3: Validate (QA/QC)](#7-stage-3-validate)
8. [Stage 4: Geocode (Fill Missing GPS)](#8-stage-4-geocode)
9. [Stage 5: Split (Road-Type Filtering)](#9-stage-5-split)
10. [Stage 6: Predict (Forecast Generation)](#10-stage-6-predict)
11. [Stage 7: Upload to R2 Storage](#11-stage-7-upload-to-r2)
12. [Stage 8: Manifest Update & Git Commit](#12-stage-8-manifest-update)
13. [GitHub Actions Workflow](#13-github-actions-workflow)
14. [Front-End Connection — How the Browser Loads Data](#14-front-end-connection)
15. [State Onboarding Checklist](#15-state-onboarding-checklist)
16. [Appendix A: Standardized Column Format](#appendix-a)
17. [Appendix B: API Types Across States](#appendix-b)
18. [Appendix C: R2 Bucket Structure](#appendix-c)
19. [Appendix D: Reference Implementations](#appendix-d)

---

## 1. Pipeline Overview

Every state follows the same 9-stage pipeline. The stages are sequential — each stage's output is the next stage's input.

```
┌─────────────────────────────────────────────────────────────────┐
│                    CRASH LENS DATA PIPELINE                     │
│                (Generic — Works for Any State)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STAGE 0: DOWNLOAD                                              │
│  ├─ Fetch raw crash data from state DOT source                  │
│  ├─ API type: Socrata, ArcGIS, REST, Bulk Portal, or Custom     │
│  └─ Output: raw CSV/Excel files in data/{DOT_NAME}/             │
│                          ↓                                      │
│  STAGE 1: MERGE (optional)                                      │
│  ├─ Combine multiple yearly or partial files                    │
│  └─ Output: single merged CSV per jurisdiction                  │
│                          ↓                                      │
│  STAGE 2: CONVERT / NORMALIZE                                   │
│  ├─ Auto-detect state format from CSV headers                   │
│  ├─ Map raw columns → standardized Virginia-compatible format   │
│  ├─ Derive severity, boolean flags, route names                 │
│  ├─ Map state-specific values → VDOT vocabulary                 │
│  └─ Output: {jurisdiction}_standardized.csv                     │
│                          ↓                                      │
│  STAGE 3: VALIDATE (QA/QC)                                      │
│  ├─ Coordinate bounds check (state + jurisdiction bbox)         │
│  ├─ Severity validation (K/A/B/C/O only)                       │
│  ├─ Date range check, mandatory fields, duplicates              │
│  ├─ Auto-correction: swapped coords, typos, whitespace          │
│  └─ Output: validated CSV + pipeline_report.json                │
│                          ↓                                      │
│  STAGE 4: GEOCODE (fill missing GPS)                            │
│  ├─ Strategy 1: Node lookup (other crashes at same intersection)│
│  ├─ Strategy 2: Nominatim/OpenStreetMap reverse geocoding       │
│  ├─ Strategy 3: Persistent cache reuse                          │
│  └─ Output: CSV with filled lat/lon + .geocode_cache.json       │
│                          ↓                                      │
│  STAGE 5: SPLIT (road-type filtering)                           │
│  ├─ county_roads.csv    (local roads only)                      │
│  ├─ no_interstate.csv   (excludes interstates)                  │
│  ├─ all_roads.csv       (complete dataset)                      │
│  └─ Output: 3 filtered CSVs per jurisdiction                    │
│                          ↓                                      │
│  STAGE 6: PREDICT (forecast generation)                         │
│  ├─ SageMaker Chronos-2 time-series prediction                  │
│  ├─ 6 prediction matrices per file                              │
│  └─ Output: 3 forecast JSON files per jurisdiction              │
│                          ↓                                      │
│  STAGE 7: UPLOAD TO R2                                          │
│  ├─ Upload CSVs + JSONs to Cloudflare R2 bucket                 │
│  ├─ Path: crash-lens-data/{state}/{jurisdiction}/               │
│  └─ Output: files live on R2 CDN                                │
│                          ↓                                      │
│  STAGE 8: MANIFEST UPDATE                                       │
│  ├─ Update data/r2-manifest.json with file metadata             │
│  ├─ Commit manifest to git                                      │
│  └─ Output: browser can resolve R2 URLs via manifest            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Prerequisites

Before building a pipeline for a new state, you need:

### 2.1 Infrastructure (Already Exists)

These are shared across all states — do NOT recreate:

| Resource | Value | Notes |
|----------|-------|-------|
| R2 Bucket | `crash-lens-data` | Cloudflare R2 storage |
| R2 Public URL | `https://pub-3334b656e3c74ea28eb4165b32499843.r2.dev` | CDN endpoint |
| R2 CORS Policy | `AllowedOrigins: [*], Methods: [GET, HEAD]` | Already configured |
| SageMaker Endpoint | `crashlens-chronos2-endpoint` | Chronos-2 forecasting |
| Manifest File | `data/r2-manifest.json` (version 3) | Shared across all states |
| State Adapter | `scripts/state_adapter.py` | Multi-state detection engine |
| Validation System | `validation/run_validation.py` | Multi-state validators |
| Main Orchestrator | `scripts/process_crash_data.py` | Runs stages 1-6 |
| R2 Uploader | `scripts/upload-to-r2.py` | Handles R2 upload + manifest |

### 2.2 Credentials (GitHub Secrets)

These must be configured in the repo's GitHub Actions secrets:

| Secret | Purpose |
|--------|---------|
| `CF_ACCOUNT_ID` | Cloudflare account ID |
| `CF_R2_ACCESS_KEY_ID` | R2 API access key |
| `CF_R2_SECRET_ACCESS_KEY` | R2 API secret key |
| `AWS_ACCESS_KEY_ID` | SageMaker access (for forecasting) |
| `AWS_SECRET_ACCESS_KEY` | SageMaker secret (for forecasting) |

### 2.3 Information to Gather for the New State

Before writing any code, research and collect:

| Item | Example (Colorado) | Where to Find |
|------|-------------------|---------------|
| State name & abbreviation | Colorado / CO | — |
| State FIPS code | 08 | Census Bureau |
| DOT name/abbreviation | CDOT | State DOT website |
| Data source URL | `https://oitco.hylandcloud.com/CDOTRMPop/...` | State DOT open data |
| API type | OnBase Portal (custom) | See Appendix B |
| Data format | Excel (.xlsx) | Download a sample |
| Coordinate bounds | lat [36.9, 41.1], lon [-109.1, -101.9] | State boundary |
| Column names in raw data | CUID, Crash Date, Injury 04, etc. | Download sample, inspect headers |
| Severity field | Derived from Injury 00-04 | Check if direct or derived |
| Road system classification | Interstate Highway, State Highway, County Road, City Street | Raw data values |
| County/jurisdiction list | 64 counties with FIPS codes | Census Bureau |
| EPDO weights | K=462, A=62, B=12, C=5, O=1 (HSM default) | State DOT or use HSM standard |
| Target jurisdictions | Douglas, Arapahoe, Jefferson, etc. | Start with 1-3, expand later |

---

## 3. Folder Structure

For each new state, create these files. Use the Colorado (`data/CDOT/`) or Virginia structure as templates.

### 3.1 Files to Create

```
project-root/
├── data/{DOT_NAME}/                        ← State data folder
│   ├── CLAUDE.md                           ← State overview + pipeline instructions
│   ├── config.json                         ← Column mappings, road systems, EPDO
│   ├── source_manifest.json                ← Data source IDs/URLs per county
│   ├── jurisdictions.json                  ← County definitions (bbox, cities, routes)
│   ├── enhancements.json                   ← Deep Dive panel mappings (optional)
│   └── .validation/                        ← Created automatically by validation stage
│       └── pipeline_report.json
│
├── states/{state_key}/                     ← State adapter config
│   ├── config.json                         ← Column mapping for state_adapter.py
│   └── hierarchy.json                      ← Regions, MPOs, counties hierarchy
│
├── download_{state}_crash_data.py          ← Download script (at project root)
│
└── .github/workflows/
    └── download-{state}-crash-data.yml     ← GitHub Actions workflow
```

### 3.2 Config.json Structure (data/{DOT_NAME}/config.json)

This is the heart of the state configuration. Template:

```json
{
  "state": "{state_name}",
  "dotName": "{DOT_NAME}",
  "fips": "{state_fips}",
  "coordinateBounds": {
    "latMin": 0.0, "latMax": 0.0,
    "lonMin": 0.0, "lonMax": 0.0
  },
  "columnMapping": {
    "ID": "{raw_id_column}",
    "DATE": "{raw_date_column}",
    "TIME": "{raw_time_column}",
    "SEVERITY": "{raw_severity_column_or_DERIVED}",
    "LAT": "{raw_lat_column}",
    "LON": "{raw_lon_column}",
    "ROUTE": "{raw_route_column_or_DERIVED}",
    "ROAD_SYSTEM": "{raw_system_column}",
    "COLLISION_TYPE": "{raw_collision_column}",
    "WEATHER": "{raw_weather_column}",
    "LIGHT": "{raw_light_column}",
    "JUNCTION": "{raw_junction_column}",
    "JURISDICTION": "{raw_county_column}"
  },
  "derivedFields": {
    "SEVERITY": {
      "method": "injury_hierarchy | direct",
      "columns": ["fatal_col", "serious_col", "minor_col", "possible_col", "pdo_col"],
      "labels": ["K", "A", "B", "C", "O"]
    }
  },
  "crashTypeMapping": {
    "{state_value}": "{vdot_numbered_value}"
  },
  "weatherMapping": {
    "{state_value}": "{vdot_numbered_value}"
  },
  "lightMapping": {
    "{state_value}": "{vdot_numbered_value}"
  },
  "roadSystems": {
    "splitConfig": {
      "countyRoads": {
        "method": "system_column | agency_id",
        "column": "{column_name}",
        "includeValues": ["list", "of", "local", "road", "types"]
      },
      "interstateExclusion": {
        "method": "column_value",
        "column": "{column_name}",
        "excludeValues": ["Interstate"]
      }
    }
  },
  "epdoWeights": {
    "K": 462, "A": 62, "B": 12, "C": 5, "O": 1
  },
  "booleanFlags": {
    "PED": {"column": "{col}", "trueValues": ["Y", "Yes", "1", "TRUE"]},
    "BIKE": {"column": "{col}", "trueValues": ["Y", "Yes", "1", "TRUE"]},
    "ALCOHOL": {"column": "{col}", "trueValues": ["Y", "Yes", "1", "TRUE"]},
    "SPEED": {"column": "{col}", "trueValues": ["Y", "Yes", "1", "TRUE"]},
    "HITRUN": {"column": "{col}", "trueValues": ["Y", "Yes", "1", "TRUE"]},
    "MOTORCYCLE": {"column": "{col}", "trueValues": ["Y", "Yes", "1", "TRUE"]},
    "NIGHT": {"derivedFrom": "LIGHT", "trueValues": ["Dark"]},
    "DISTRACTED": {"column": "{col}", "trueValues": ["Y"]},
    "DROWSY": {"column": "{col}", "trueValues": ["Y"]},
    "DRUG": {"column": "{col}", "trueValues": ["Y"]},
    "YOUNG": {"derivedFrom": "AGE", "range": [16, 25]},
    "SENIOR": {"derivedFrom": "AGE", "range": [65, 999]},
    "UNRESTRAINED": {"column": "{col}", "trueValues": ["Y"]}
  }
}
```

### 3.3 State Adapter Signature (states/{state_key}/config.json)

Register the new state in the state adapter detection system. Add a signature to `scripts/state_adapter.py`:

```python
'{state_key}': {
    'required': ['col1', 'col2', 'col3'],   # 3-4 unique header columns
    'display_name': '{State Name} ({DOT_NAME})',
    'config_dir': '{state_key}'
}
```

The `required` columns must be unique to this state — columns that no other state's CSV would have.

### 3.4 Main Config Registration (config.json at project root)

Add the state entry under `states`:

```json
"{state_key}": {
  "fips": "{fips}",
  "name": "{State Name}",
  "abbreviation": "{XX}",
  "dotName": "{DOT_NAME}",
  "defaultJurisdiction": "{default_county}",
  "dataDir": "{DOT_NAME}",
  "r2Prefix": "{state_key}",
  "appSubtitle": "{State Name} Crash Analysis Tool"
}
```

The `r2Prefix` MUST match the folder name used in R2 storage (lowercase state name).

---

## 4. Stage 0: Download Raw Data

### 4.1 Purpose

Fetch raw crash data from the state DOT's data portal and save it locally as CSV.

### 4.2 API Types (Choose One)

| API Type | States Using It | Python Library | Pagination |
|----------|----------------|---------------|------------|
| **Socrata SODA** | MD, CT, DE, NY, NYC, HI | `requests` (REST) | `$offset` + `$limit` |
| **ArcGIS GeoServices** | IA, IL, FL, OR, PA, MA, OH, WI, AK, NV, UT, ID, WA, GA, SC, AR, MT, MS, OK, LA, WV | `requests` (REST) | `resultOffset` + `resultRecordCount` |
| **Custom REST** | VT | `requests` | Varies |
| **Bulk Download Portal** | TX | `requests` (direct file download) | N/A (full file) |
| **OnBase Document Portal** | CO | `requests` + browser headers | N/A (document by ID) |

### 4.3 Download Script Template

Create `download_{state}_crash_data.py` at the project root. Every download script must:

1. Accept `--jurisdiction` to filter by county
2. Accept `--list` to show available jurisdictions
3. Accept `--years` to specify year range
4. Implement retry logic with exponential backoff (at least 3 retries)
5. Use persistent sessions with connection pooling
6. Validate downloaded file size (minimum 100 KB)
7. Save output to `data/{DOT_NAME}/`
8. Print download statistics (rows, size, duration)

**Minimal structure:**

```python
#!/usr/bin/env python3
"""Download {STATE_NAME} crash data from {SOURCE_NAME}."""

import argparse, requests, time, os, sys
from pathlib import Path

# ── Configuration ──
STATE_KEY = '{state_key}'
DOT_NAME = '{DOT_NAME}'
API_BASE_URL = '{api_url}'
DATA_DIR = Path(f'data/{DOT_NAME}')
MIN_VALID_FILE_SIZE = 100 * 1024  # 100 KB

def download_data(jurisdiction, years, output_dir):
    """Download crash data with pagination and retry."""
    session = requests.Session()
    session.headers.update({'User-Agent': 'CrashLens-Pipeline/1.0'})

    # ... API-specific pagination loop ...
    # ... Retry logic with exponential backoff ...
    # ... County/jurisdiction filtering ...
    # ... Save to CSV ...

    return output_path

def list_jurisdictions():
    """Print available jurisdictions from source_manifest.json."""
    manifest = json.load(open(DATA_DIR / 'source_manifest.json'))
    for jur_id, info in manifest['jurisdictions'].items():
        print(f"  {jur_id}: {info['name']} (FIPS: {info['fips']})")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=f'Download {DOT_NAME} crash data')
    parser.add_argument('--jurisdiction', '-j', default=None)
    parser.add_argument('--years', nargs='+', type=int, default=None)
    parser.add_argument('--list', action='store_true', help='List jurisdictions')
    parser.add_argument('--output', '-o', default=str(DATA_DIR))
    args = parser.parse_args()

    if args.list:
        list_jurisdictions()
    else:
        download_data(args.jurisdiction, args.years, args.output)
```

### 4.4 Reference Implementations

| State | Script | API Type | Key Differences |
|-------|--------|----------|----------------|
| Virginia | `download_crash_data.py` | ArcGIS FeatureServer | 2,000 records/page, jurisdiction filter via county FIPS |
| Colorado | `download_cdot_crash_data.py` | OnBase Portal | Document ID-based, Excel format, statewide then filter |

---

## 5. Stage 1: Merge (Optional)

### 5.1 When to Use

Only needed when the state provides data as multiple files (e.g., one Excel file per year, like Colorado). Skip if the API returns a single combined dataset (like Virginia).

### 5.2 What It Does

1. Read multiple CSV/Excel files matching a glob pattern
2. Concatenate all rows into a single DataFrame
3. Remove exact duplicate rows
4. Save as a single merged CSV

### 5.3 Command

```bash
python scripts/process_crash_data.py \
  --input 'data/{DOT_NAME}/2021*.csv' 'data/{DOT_NAME}/2022*.csv' \
  --jurisdiction {jurisdiction} \
  --merge
```

### 5.4 Output

`data/{DOT_NAME}/{jurisdiction}_merged.csv` — single file containing all years.

---

## 6. Stage 2: Convert / Normalize

### 6.1 Purpose

Transform state-specific raw CSV columns into the standardized Virginia-compatible format that the front-end expects. This is the most state-specific stage.

### 6.2 How Auto-Detection Works

The state adapter (`scripts/state_adapter.py`) examines the CSV header row and matches against registered state signatures:

```python
# Detection flow:
headers = csv_file.columns.tolist()
for state_key, signature in STATE_SIGNATURES.items():
    if all(col in headers for col in signature['required']):
        return state_key  # Found match
```

### 6.3 What Gets Normalized

| Category | Action | Example |
|----------|--------|---------|
| **Column Renaming** | Raw column → standardized name | `CUID` → `Document Nbr` |
| **Severity** | Direct passthrough OR derived from injury counts | CO: `Injury 04 > 0` → `K` |
| **Route Name** | Direct passthrough OR derived from components | CO: `System Code + Rd_Number` → `RTE Name` |
| **Value Mapping** | State values → VDOT numbered vocabulary | `Clear` → `1. No Adverse Condition` |
| **Boolean Flags** | Derive 13 Yes/No flags from raw fields | See flag list below |
| **State Detail Columns** | Preserve originals with `_{xx}_` prefix | `Speed Limit` → `_co_tu1_speed_limit` |
| **Coordinates** | Standardize to `x` (longitude) and `y` (latitude) | Various column names → `x`, `y` |

### 6.4 The 13 Boolean Flags

Every state must derive these flags (Yes/No):

| Flag | Meaning | Common Raw Sources |
|------|---------|-------------------|
| `Pedestrian?` | Pedestrian involved | Pedestrian count, crash type contains "ped" |
| `Bike?` | Bicyclist involved | Bicycle count, crash type contains "bik" |
| `Motorcycle?` | Motorcycle involved | Vehicle type column |
| `Alcohol?` | Alcohol involvement | DUI flag, alcohol-related column |
| `Speed?` | Speed-related | Speed-related flag |
| `Hitrun?` | Hit and run | Hit-run flag |
| `Distracted?` | Distracted driving | Driver action column |
| `Drowsy?` | Drowsy driving | Driver action or factor column |
| `Drug Related?` | Drug involvement | Drug-related flag |
| `Young?` | Driver age 16-25 | Driver age column |
| `Senior?` | Driver age 65+ | Driver age column |
| `Unrestrained?` | Seatbelt not used | Restraint column |
| `Night?` | Dark conditions | Derived from Light Condition |

### 6.5 Severity Derivation Methods

**Method 1: Direct Passthrough** (Virginia, most states)
The raw data has a single severity column with K/A/B/C/O values.

**Method 2: Injury Hierarchy** (Colorado, some states)
No single severity column. Derive from injury count columns:
```
If Fatal_Count > 0        → K
Elif Serious_Inj_Count > 0 → A
Elif Minor_Inj_Count > 0   → B
Elif Possible_Inj_Count > 0 → C
Else                        → O (Property Damage Only)
```

Configure the method in `data/{DOT_NAME}/config.json` → `derivedFields.SEVERITY`.

### 6.6 Command

```bash
python scripts/process_crash_data.py \
  --input data/{DOT_NAME}/{jurisdiction}_merged.csv \
  --state {state_key} \
  --jurisdiction {jurisdiction} \
  --convert-only   # Run only Stage 2
```

### 6.7 Output

`data/{DOT_NAME}/{jurisdiction}_standardized.csv` — standardized column format.

---

## 7. Stage 3: Validate (QA/QC)

### 7.1 Purpose

Check data quality, flag issues, auto-correct common problems, and remove duplicates.

### 7.2 Validation Checks

| Check | What It Does | Auto-Correctable? |
|-------|-------------|-------------------|
| **Coordinate bounds** | Verify lat/lon within state bounds | Yes (swap detection) |
| **Jurisdiction bounds** | Verify within county-specific bbox | No (flagged only) |
| **Date validation** | Format check, reasonable year range (2010-present) | Yes (format fix) |
| **Severity validation** | Must be K, A, B, C, or O | No (flagged) |
| **Mandatory fields** | ID, Date, Severity must be non-empty | No (flagged) |
| **Duplicate detection** | Remove exact duplicate rows by ID | Yes (removed) |
| **Whitespace trim** | Strip leading/trailing whitespace | Yes |
| **Transposed coordinates** | Detect lat/lon swapped | Yes (swap correction) |
| **Cross-field consistency** | Severity matches injury counts | No (flagged) |

### 7.3 State-Specific Configuration

Coordinate bounds come from `data/{DOT_NAME}/config.json` → `coordinateBounds`. Jurisdiction bounding boxes come from `config.json` → `jurisdictions.{id}.bbox`.

### 7.4 Command

```bash
python validation/run_validation.py \
  --jurisdiction {jurisdiction} \
  --state {state_key}

# Or validate all jurisdictions:
python validation/run_validation.py --all --state {state_key}
```

### 7.5 Output

- Same CSV with corrections applied
- `data/{DOT_NAME}/.validation/pipeline_report.json` — statistics, issues, corrections

### 7.6 Pipeline Report Format

```json
{
  "timestamp": "2026-02-07T04:32:35Z",
  "state": "{state_key}",
  "jurisdiction": "{jurisdiction}",
  "input_rows": 27180,
  "output_rows": 25098,
  "corrections": 12,
  "issues": 3,
  "duplicates_removed": 2082,
  "gps_coverage": "81.6%"
}
```

---

## 8. Stage 4: Geocode (Fill Missing GPS)

### 8.1 Purpose

Fill in missing latitude/longitude coordinates so crashes can be mapped. Many state datasets have 10-30% missing GPS.

### 8.2 Three-Strategy Approach

**Strategy 1: Node Lookup (Instant)**
- Build a lookup table from rows that DO have GPS coordinates
- Match by intersection node ID (if the state provides one)
- Rows at the same intersection get the same coordinates
- Zero API calls, instant resolution

**Strategy 2: Nominatim/OpenStreetMap (Rate-Limited)**
- Free geocoding API: `https://nominatim.openstreetmap.org/search`
- Query: `"{Location 1} and {Location 2}, {jurisdiction}, {state}"`
- Rate limit: 1 request per second (mandatory — Nominatim policy)
- Results cached persistently (even null results for failed lookups)

**Strategy 3: Persistent Cache Reuse (Instant)**
- Check `.geocode_cache.json` from previous pipeline runs
- Avoids re-calling Nominatim for locations already tried
- Makes re-runs near-instant for existing data

### 8.3 Cache File

**Location:** `data/{DOT_NAME}/.geocode_cache.json`

```json
{
  "nodes": { "NODE_ID": [longitude, latitude] },
  "nominatim": { "query string": [longitude, latitude] }
}
```

This file must be committed to git so cache persists across CI/CD runs.

### 8.4 Performance

| Scenario | API Calls | Duration |
|----------|-----------|----------|
| First run, 1000 missing | ~1000 | ~17 minutes |
| Re-run same data | 0 | ~0 seconds |
| Add new year, 200 new locations | ~200 | ~3 minutes |

### 8.5 Command

```bash
python scripts/process_crash_data.py \
  --input data/{DOT_NAME}/{jurisdiction}_standardized.csv \
  --jurisdiction {jurisdiction}

# Skip geocoding (useful for quick re-runs):
python scripts/process_crash_data.py --input data.csv -j {jurisdiction} --skip-geocode
```

### 8.6 Target

GPS coverage should reach 95%+ after geocoding. Check the `gps_coverage` field in the pipeline report.

---

## 9. Stage 5: Split (Road-Type Filtering)

### 9.1 Purpose

Create 3 filtered CSV files from the standardized data. Each corresponds to a radio button in the front-end UI.

### 9.2 Three Output Files

| File | UI Label | What's Included | What's Excluded |
|------|----------|----------------|-----------------|
| `county_roads.csv` | "County Roads Only" | Local/county-maintained roads | State highways, interstates |
| `no_interstate.csv` | "No Interstate" | Everything except interstates | Interstate highways |
| `all_roads.csv` | "All Roads" | Complete dataset | Nothing |

### 9.3 Filtering Methods

The filter logic varies by state — configure in `data/{DOT_NAME}/config.json` → `roadSystems.splitConfig`:

**Method A: System Column (Virginia)**
```json
"countyRoads": {
  "method": "system_column",
  "column": "SYSTEM",
  "includeValues": ["NonVDOT secondary", "NONVDOT", "Non-VDOT"]
}
```

**Method B: Agency ID (Colorado)**
```json
"countyRoads": {
  "method": "agency_id",
  "column": "_co_agency_id",
  "agencyMap": {
    "douglas": ["DSO"],
    "arapahoe": ["ASO"]
  }
}
```

**Method C: Road Class (Generic)**
```json
"countyRoads": {
  "method": "column_value",
  "column": "Functional_Class",
  "includeValues": ["Local", "Minor Collector", "Major Collector"]
}
```

### 9.4 Command

```bash
python scripts/process_crash_data.py \
  --input data/{DOT_NAME}/{jurisdiction}_standardized.csv \
  --jurisdiction {jurisdiction}

# Or split-only:
python scripts/split_cdot_data.py \
  --input data/{DOT_NAME}/{jurisdiction}_all_roads.csv \
  --output-dir data/{DOT_NAME}/
```

### 9.5 Output

Three files in `data/{DOT_NAME}/`:
- `{jurisdiction}_county_roads.csv`
- `{jurisdiction}_no_interstate.csv`
- `{jurisdiction}_all_roads.csv`

---

## 10. Stage 6: Predict (Forecast Generation)

### 10.1 Purpose

Generate 12-month crash forecasts using Amazon SageMaker Chronos-2, a foundation model for time-series prediction.

### 10.2 Six Prediction Matrices

| Matrix | Description | Input |
|--------|-------------|-------|
| **M01** | Total crash frequency (monthly) | All crashes grouped by month |
| **M02** | Severity-level multivariate (K/A/B/C/O by month) | Crashes by severity × month |
| **M03** | Corridor cross-learning (top 10 routes) | Top routes by crash volume |
| **M04** | Crash type distribution | Crash types by month |
| **M05** | Contributing factor trends | Speed, alcohol, ped, bike by month |
| **M06** | Intersection vs. segment | Location type by month |

### 10.3 Temporal Embedding

**For high-count series (≥10 crashes/month, 2+ years history):**
- Seasonal decomposition (additive, 12-month cycle)
- Removes cyclical pattern; model focuses on trend + irregular

**For low-count series (<10 crashes/month):**
- Log1p variance stabilization
- Compresses range for proportional treatment of rare events (e.g., fatalities)

### 10.4 Output Format

```json
{
  "jurisdiction": "douglas",
  "state": "colorado",
  "roadType": "county_roads",
  "generatedAt": "2026-02-07T04:32:35Z",
  "horizon": 12,
  "quantiles": [0.1, 0.25, 0.5, 0.75, 0.9],
  "matrices": {
    "M01_total": { "monthly": [...] },
    "M02_severity": { "K": [...], "A": [...], "B": [...], "C": [...], "O": [...] },
    "M03_corridors": { "I-25": [...], "CO-83": [...] },
    "M04_types": { "Rear End": [...], "Angle": [...] },
    "M05_factors": { "speed": [...], "alcohol": [...] },
    "M06_location": { "intersection": [...], "segment": [...] }
  }
}
```

### 10.5 Execution Modes

| Mode | Flag | When to Use | AWS Required? |
|------|------|------------|---------------|
| **Live** | (default) | CI/CD with AWS secrets | Yes |
| **Dry-run** | `--dry-run` | Local dev, no AWS credentials | No (synthetic data) |
| **Skip** | omit `--predict` flag | Data corrections, no forecast needed | No |

Forecasting is **non-fatal** — if SageMaker is down or credentials are missing, stages 0-5 still produce valid CSVs. The pipeline logs a warning and continues.

### 10.6 Command

```bash
python scripts/generate_forecast.py \
  --data data/{DOT_NAME}/{jurisdiction}_county_roads.csv \
  --horizon 12

# Dry run (no AWS needed):
python scripts/generate_forecast.py --dry-run
```

### 10.7 Output

Three JSON files per jurisdiction:
- `forecasts_county_roads.json`
- `forecasts_no_interstate.json`
- `forecasts_all_roads.json`

---

## 11. Stage 7: Upload to R2 Storage

### 11.1 Purpose

Upload all processed CSVs and forecast JSONs to Cloudflare R2 cloud storage so the browser can load them.

### 11.2 R2 Bucket Path Convention

Every state follows this exact folder structure inside the `crash-lens-data` bucket:

```
crash-lens-data/
  {state_key}/                          ← e.g., colorado/
    _statewide/                         ← State rollup aggregates
      aggregates.json
      county_summary.json
      mpo_summary.json
    _state/                             ← State-tier road data
      dot_roads.csv
      non_dot_roads.csv
      statewide_all_roads.csv
    _region/{regionId}/                 ← Region-tier data
      aggregates.json
      dot_roads.csv
      all_roads.csv
    _mpo/{mpoId}/                       ← MPO-tier data
      aggregates.json
      dot_roads.csv
      all_roads.csv
    {jurisdiction}/                     ← e.g., douglas/
      county_roads.csv                  ← Road type 1
      no_interstate.csv                 ← Road type 2
      all_roads.csv                     ← Road type 3
      standardized.csv                  ← Full standardized dataset
      forecasts_county_roads.json
      forecasts_no_interstate.json
      forecasts_all_roads.json
```

### 11.3 Upload File List Per Jurisdiction

| File | Source Stage | Required? |
|------|-------------|-----------|
| `county_roads.csv` | Stage 5 (Split) | Yes |
| `no_interstate.csv` | Stage 5 (Split) | Yes |
| `all_roads.csv` | Stage 5 (Split) | Yes |
| `standardized.csv` | Stage 2 (Convert) | Optional |
| `forecasts_county_roads.json` | Stage 6 (Predict) | If forecasting enabled |
| `forecasts_no_interstate.json` | Stage 6 (Predict) | If forecasting enabled |
| `forecasts_all_roads.json` | Stage 6 (Predict) | If forecasting enabled |

### 11.4 Command

```bash
# Upload specific jurisdiction:
python scripts/upload-to-r2.py --state {state_key} --jurisdiction {jurisdiction}

# Dry run (preview only):
python scripts/upload-to-r2.py --dry-run

# With explicit credentials:
CF_ACCOUNT_ID=xxx CF_R2_ACCESS_KEY_ID=xxx CF_R2_SECRET_ACCESS_KEY=xxx \
  python scripts/upload-to-r2.py --state {state_key} --jurisdiction {jurisdiction}
```

---

## 12. Stage 8: Manifest Update & Git Commit

### 12.1 Purpose

After uploading files to R2, update the shared manifest file so the browser knows what's available and where to find it.

### 12.2 Manifest File

**Location:** `data/r2-manifest.json` (version 3)

**Structure:**

```json
{
  "version": 3,
  "r2BaseUrl": "https://pub-3334b656e3c74ea28eb4165b32499843.r2.dev",
  "updated": "2026-02-16T00:45:07.223028+00:00",
  "files": {
    "{state_key}/{jurisdiction}/county_roads.csv": {
      "size": 9500000,
      "md5": "abc123...",
      "uploaded": "2026-02-13T03:32:40.216522+00:00"
    }
  },
  "localPathMapping": {
    "data/{DOT_NAME}/{jurisdiction}_county_roads.csv": "{state_key}/{jurisdiction}/county_roads.csv"
  }
}
```

### 12.3 What Gets Updated

1. **`files` object:** Add/update entries for each uploaded file (size, md5, timestamp)
2. **`localPathMapping` object:** Map legacy local paths → R2 keys (for backwards compatibility)
3. **`updated` timestamp:** Set to current UTC time

### 12.4 Git Commit

After manifest update, commit to git so the deployed app can access the updated manifest:

```bash
git add data/r2-manifest.json
git commit -m "Update R2 manifest: {state_key}/{jurisdiction} data refresh"
git push
```

In GitHub Actions, this is automated with the `actions/checkout` token.

---

## 13. GitHub Actions Workflow

### 13.1 Workflow Template

Create `.github/workflows/download-{state}-crash-data.yml`. Template:

```yaml
name: "Download {State Name} Crash Data"

on:
  # Manual trigger with options
  workflow_dispatch:
    inputs:
      jurisdiction:
        description: 'County/jurisdiction to process'
        required: false
        default: '{default_jurisdiction}'
        type: choice
        options:
          - '{jurisdiction_1}'
          - '{jurisdiction_2}'
          - 'all'
      force_download:
        description: 'Force re-download even if cached'
        required: false
        default: false
        type: boolean

  # Scheduled trigger (monthly)
  schedule:
    - cron: '0 11 1 * *'   # 1st of every month, 11:00 UTC

env:
  R2_STATE_PREFIX: '{state_key}'

jobs:
  download-and-process:
    runs-on: ubuntu-latest
    timeout-minutes: 60

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      # Stage 0: Download
      - name: Download crash data
        run: |
          python download_{state}_crash_data.py \
            --jurisdiction ${{ github.event.inputs.jurisdiction || '{default}' }}

      # Stages 1-5: Process
      - name: Process crash data
        run: |
          python scripts/process_crash_data.py \
            --input 'data/{DOT_NAME}/*.csv' \
            --jurisdiction ${{ github.event.inputs.jurisdiction || '{default}' }} \
            --merge

      # Stage 6: Predict
      - name: Generate forecasts
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          python scripts/generate_forecast.py --dry-run
        continue-on-error: true   # Non-fatal

      # Stage 7: Upload to R2
      - name: Upload to R2
        env:
          CF_ACCOUNT_ID: ${{ secrets.CF_ACCOUNT_ID }}
          CF_R2_ACCESS_KEY_ID: ${{ secrets.CF_R2_ACCESS_KEY_ID }}
          CF_R2_SECRET_ACCESS_KEY: ${{ secrets.CF_R2_SECRET_ACCESS_KEY }}
        run: |
          python scripts/upload-to-r2.py \
            --state {state_key} \
            --jurisdiction ${{ github.event.inputs.jurisdiction || '{default}' }}

      # Stage 8: Commit manifest
      - name: Commit manifest update
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/r2-manifest.json data/{DOT_NAME}/.geocode_cache.json
          git diff --cached --quiet || git commit -m "Pipeline: update {state_key} data"
          git push
```

### 13.2 Reference Workflows

| State | Workflow File | Schedule |
|-------|-------------|----------|
| Virginia | `download-data.yml` | 1st Monday/month, 11:00 UTC |
| Colorado (download) | `download-cdot-crash-data.yml` | 1st of month, 11:00 UTC |
| Colorado (process) | `process-cdot-data.yml` | Triggered after download |

---

## 14. Front-End Connection

### 14.1 How the Browser Loads Data from R2

Once data is in R2, the browser app (`app/index.html`) loads it through a three-layer URL resolution system:

```
User selects: {State} > {County} > {Road Type}
        ↓
Layer 1: getDataFilePath()
  - Reads current tier, state r2Prefix, jurisdiction ID, road type
  - Returns R2-native path: "{state_key}/{jurisdiction}/{road_type}.csv"
        ↓
Layer 2: resolveDataUrl(path)
  - Strategy 1: Exact lookup in r2-manifest.json localPathMapping
  - Strategy 2: Dynamic construction from state r2Prefix
  - Strategy 3: R2-native path detection (prepend R2 base URL)
  - Returns: "https://pub-xxx.r2.dev/{state_key}/{jurisdiction}/{road_type}.csv"
        ↓
Layer 3: fetch()
  - Browser HTTP GET to R2 CDN
  - Parse CSV with PapaParse
  - StateAdapter.detect(headers) identifies the state format
  - Normalize rows, populate dashboard
```

### 14.2 What the Pipeline Must Ensure

For the front-end to work, the pipeline must guarantee:

1. **Files exist in R2** at the correct paths (Stage 7)
2. **r2-manifest.json is updated** with file metadata (Stage 8)
3. **config.json has `r2Prefix`** for the state (Section 3.4)
4. **State adapter detects the format** from CSV headers (Section 6)
5. **Column names are standardized** to Virginia-compatible format (Stage 2)

### 14.3 Road Type to Filename Mapping (Front-End)

| Radio Button | Filter Value | County-Level File | State-Level File |
|-------------|-------------|-------------------|-----------------|
| County Roads Only | `countyOnly` | `county_roads.csv` | `dot_roads.csv` |
| No Interstate | `countyPlusVDOT` | `no_interstate.csv` | `non_dot_roads.csv` |
| All Roads | `allRoads` | `all_roads.csv` | `statewide_all_roads.csv` |

---

## 15. State Onboarding Checklist

Use this checklist when adding a new state. Check off each item as completed.

### Phase 1: Research & Setup

- [ ] Identify state DOT data source (URL, API type, format)
- [ ] Download a sample file and inspect column headers
- [ ] Document column mapping (raw → standardized)
- [ ] Determine severity method (direct or derived)
- [ ] Identify road system classification values
- [ ] Get coordinate bounds for the state
- [ ] Get FIPS codes for target counties
- [ ] Determine EPDO weights (use HSM standard if state-specific unavailable)

### Phase 2: Configuration Files

- [ ] Create `data/{DOT_NAME}/` folder
- [ ] Create `data/{DOT_NAME}/CLAUDE.md` — state overview
- [ ] Create `data/{DOT_NAME}/config.json` — column mappings, road systems, EPDO
- [ ] Create `data/{DOT_NAME}/source_manifest.json` — data source registry
- [ ] Create `data/{DOT_NAME}/jurisdictions.json` — county definitions
- [ ] Create `states/{state_key}/config.json` — state adapter configuration
- [ ] Create `states/{state_key}/hierarchy.json` — region/county hierarchy
- [ ] Add state signature to `scripts/state_adapter.py`
- [ ] Add state entry to root `config.json` under `states` (with `r2Prefix`)

### Phase 3: Download Script

- [ ] Create `download_{state}_crash_data.py`
- [ ] Implement API pagination
- [ ] Add retry logic with exponential backoff
- [ ] Add `--jurisdiction`, `--years`, `--list` arguments
- [ ] Test download for at least 1 jurisdiction
- [ ] Verify file size > 100 KB

### Phase 4: Pipeline Processing

- [ ] Run Stage 2 (Convert) — verify standardized output
- [ ] Run Stage 3 (Validate) — check pipeline_report.json
- [ ] Run Stage 4 (Geocode) — verify GPS coverage improvement
- [ ] Run Stage 5 (Split) — verify 3 output CSVs are correct
- [ ] Run Stage 6 (Predict) — verify 3 forecast JSONs (or dry-run)

### Phase 5: R2 Upload & Integration

- [ ] Create R2 folder: `crash-lens-data/{state_key}/`
- [ ] Upload test data with `scripts/upload-to-r2.py --dry-run`
- [ ] Upload real data with `scripts/upload-to-r2.py`
- [ ] Verify `data/r2-manifest.json` updated correctly
- [ ] Test in browser: select new state → data loads from R2

### Phase 6: Automation

- [ ] Create `.github/workflows/download-{state}-crash-data.yml`
- [ ] Test manual workflow_dispatch trigger
- [ ] Enable scheduled trigger (monthly)
- [ ] Verify end-to-end: download → process → upload → manifest commit

### Phase 7: Expansion

- [ ] Add more jurisdictions (counties) to source_manifest.json
- [ ] Configure Deep Dive panels in enhancements.json (optional)
- [ ] Add state-specific hierarchy (regions, MPOs) to hierarchy.json
- [ ] Generate aggregate data (`scripts/generate_aggregates.py`)

---

## Appendix A: Standardized Column Format

All states normalize to this column set (Virginia-compatible):

```
Document Nbr          — Unique crash identifier
Crash Date            — Date (YYYY-MM-DD or M/D/YYYY)
Crash Year            — Year (derived from date)
Crash Military Time   — Time (HHMM format)
Crash Severity        — K / A / B / C / O
K_People              — Fatal count
A_People              — Serious injury count
B_People              — Minor injury count
C_People              — Possible injury count
Collision Type        — Numbered VDOT format (e.g., "1. Rear End")
Weather Condition     — Numbered VDOT format
Light Condition       — Numbered VDOT format
Roadway Surface Condition
Roadway Alignment
Roadway Description
Intersection Type
RTE Name              — Route name
SYSTEM                — Road system (Interstate, US Route, etc.)
Node                  — Intersection node ID (if available)
RNS MP                — Route milepost (if available)
x                     — Longitude (decimal degrees, negative for US)
y                     — Latitude (decimal degrees, positive for US)
Physical Juris Name   — Jurisdiction/county name
Pedestrian?           — Y/N boolean flag
Bike?                 — Y/N boolean flag
Alcohol?              — Y/N boolean flag
Speed?                — Y/N boolean flag
Hitrun?               — Y/N boolean flag
Motorcycle?           — Y/N boolean flag
Night?                — Y/N boolean flag
Distracted?           — Y/N boolean flag
Drowsy?               — Y/N boolean flag
Drug Related?         — Y/N boolean flag
Young?                — Y/N boolean flag
Senior?               — Y/N boolean flag
Unrestrained?         — Y/N boolean flag
School Zone           — Y/N
Work Zone Related     — Y/N
Traffic Control Type
Traffic Control Status
Functional Class
Area Type
Facility Type
Ownership
First Harmful Event
First Harmful Event Loc
Relation To Roadway
Vehicle Count
Persons Injured
Pedestrians Killed
Pedestrians Injured
_source_state         — State key (e.g., "colorado")
_source_file          — Original filename
```

---

## Appendix B: API Types Across 30+ States

| API Type | States | Base URL Pattern | Pagination |
|----------|--------|-----------------|------------|
| **Socrata SODA** | MD, CT, DE, NY, NYC, HI | `https://{domain}/resource/{dataset_id}.csv` | `$offset`, `$limit` |
| **ArcGIS GeoServices** | IA, IL, FL, OR, PA, MA, OH, WI, AK, NV, UT, ID, WA, GA, SC, AR, MT, MS, OK, LA, WV | `https://services.arcgis.com/.../FeatureServer/0/query` | `resultOffset`, `resultRecordCount` |
| **Custom REST** | VT | `https://{domain}/api/...` | Varies |
| **Bulk Download** | TX | Direct file URL | N/A |
| **OnBase Portal** | CO | `https://{domain}/docpop/GetDoc.aspx?docid={id}` | N/A |

---

## Appendix C: R2 Bucket Complete Structure

```
crash-lens-data/
├── _national/
│   ├── state_comparison.json
│   ├── dot_roads.csv
│   ├── non_dot_roads.csv
│   └── statewide_all_roads.csv
├── colorado/
│   ├── _statewide/
│   │   ├── aggregates.json
│   │   ├── county_summary.json
│   │   └── mpo_summary.json
│   ├── _state/
│   │   ├── dot_roads.csv
│   │   ├── non_dot_roads.csv
│   │   └── statewide_all_roads.csv
│   ├── _region/{regionId}/
│   │   ├── aggregates.json
│   │   └── all_roads.csv
│   ├── _mpo/{mpoId}/
│   │   ├── aggregates.json
│   │   └── all_roads.csv
│   ├── douglas/
│   │   ├── county_roads.csv
│   │   ├── no_interstate.csv
│   │   ├── all_roads.csv
│   │   ├── standardized.csv
│   │   ├── forecasts_county_roads.json
│   │   ├── forecasts_no_interstate.json
│   │   └── forecasts_all_roads.json
│   ├── arapahoe/
│   │   └── (same structure)
│   └── ... (other counties)
├── virginia/
│   ├── _statewide/
│   ├── henrico/
│   └── ... (other counties)
└── {new_state}/
    └── (same structure)
```

---

## Appendix D: Reference Implementations

### Colorado (CDOT) — Key Files

| File | Purpose |
|------|---------|
| `download_cdot_crash_data.py` | Download from OnBase portal |
| `data/CDOT/config.json` | Column mapping, severity derivation, road systems |
| `data/CDOT/source_manifest.json` | OnBase doc IDs for all 64 counties |
| `data/CDOT/CLAUDE.md` | State overview |
| `states/colorado/config.json` | State adapter configuration |
| `states/colorado/hierarchy.json` | Regions, MPOs, 64 counties |
| `.github/workflows/download-cdot-crash-data.yml` | Download workflow |
| `.github/workflows/process-cdot-data.yml` | Processing workflow |

### Virginia (VDOT) — Key Files

| File | Purpose |
|------|---------|
| `download_crash_data.py` | Download from ArcGIS API |
| `states/virginia/config.json` | Column mapping (passthrough), road systems |
| `states/virginia/hierarchy.json` | Construction districts, 133 jurisdictions |
| `.github/workflows/download-data.yml` | Full pipeline workflow |

### Key Differences Between the Two

| Aspect | Colorado | Virginia |
|--------|----------|---------|
| Data source | OnBase document portal (Excel) | ArcGIS FeatureServer (CSV) |
| Severity | Derived from injury columns | Direct passthrough |
| Route name | Derived from System Code + Rd_Number | Direct passthrough |
| Value mapping | Extensive (Colorado → VDOT vocabulary) | Minimal (already VDOT format) |
| Road split | By agency ID | By SYSTEM column |
| Counties | 64 (6 configured) | 95 + 38 cities (133 total) |
| Download format | Excel (.xlsx) per year | CSV via API query |
| Merge needed? | Yes (multiple year files) | No (single query) |
| EPDO weights | HSM 2010 standard | VDOT 2024 state-specific |

---

## Quick Reference: Full Pipeline Command Sequence

For a new state with everything configured:

```bash
# 1. Download
python download_{state}_crash_data.py --jurisdiction {jurisdiction}

# 2. Process (stages 1-5 in one command)
python scripts/process_crash_data.py \
  --input data/{DOT_NAME}/*.csv \
  --jurisdiction {jurisdiction} \
  --merge

# 3. Forecast (stage 6)
python scripts/generate_forecast.py --dry-run

# 4. Upload to R2 (stage 7)
python scripts/upload-to-r2.py --state {state_key} --jurisdiction {jurisdiction}

# 5. Verify in browser
# Open app/index.html → Select new state → Data should load from R2
```

---

## Appendix E: Additional File Templates

### E.1 source_manifest.json Template

Registry of data source identifiers per jurisdiction (URLs, doc IDs, API endpoints):

```json
{
  "state": "{state_name}",
  "dotName": "{DOT_NAME}",
  "dataSource": {
    "type": "arcgis | socrata | onbase | rest | bulk",
    "baseUrl": "{api_base_url}",
    "notes": "Brief description of how to access data"
  },
  "years": {
    "2025": { "status": "preliminary" },
    "2024": { "status": "final" },
    "2023": { "status": "final" }
  },
  "jurisdictions": {
    "{jurisdiction_id}": {
      "name": "{County Name} County",
      "fips": "{county_fips}",
      "apiFilter": "{api_specific_filter_value}"
    }
  }
}
```

For Colorado (OnBase), each year also has a `docid` field. For ArcGIS states, `apiFilter` is the FIPS or name used in API queries.

### E.2 jurisdictions.json Template

County definitions with map boundaries and metadata:

```json
{
  "{jurisdiction_id}": {
    "name": "{County Name} County",
    "type": "county",
    "fips": "{county_fips}",
    "state": "{XX}",
    "center": { "lat": 0.0, "lon": 0.0 },
    "zoom": 11,
    "bbox": [-0.0, 0.0, -0.0, 0.0],
    "cities": ["{City1}", "{City2}"],
    "majorRoutes": ["I-XX", "US-XX", "SR-XX"],
    "reportingAgencies": ["{agency_code}"]
  }
}
```

### E.3 CLAUDE.md Template

State overview for pipeline context (used by Claude Code to understand state-specific rules):

```markdown
# {DOT_NAME} ({State Full Name}) — Pipeline Instructions

## State Overview

| Field | Value |
|-------|-------|
| **State** | {State Name} |
| **Abbreviation** | {XX} |
| **FIPS** | {fips} |
| **DOT Name** | {DOT_NAME} |
| **Counties** | {count} |

## Data Source

- **System:** {source_system_name}
- **URL:** `{source_url}`
- **Format:** {CSV/Excel/JSON}
- **Refresh:** {Annual/Monthly/Quarterly}

## Column Mapping Summary

| CRASH LENS Field | Raw Column | Notes |
|-----------------|-----------|-------|
| ID | `{raw_id}` | Unique crash identifier |
| DATE | `{raw_date}` | Date of crash |
| SEVERITY | `{raw_severity}` or DERIVED | {Notes on derivation} |
| ROUTE | `{raw_route}` or DERIVED | {Notes on derivation} |
| JURISDICTION | `{raw_county}` | County/jurisdiction name |

## Severity Mapping

{Direct passthrough OR injury hierarchy derivation rules}

## Road Systems

| Raw Value | Classification |
|-----------|---------------|
| {value1} | Local |
| {value2} | State-maintained |
| {value3} | Interstate |

## Key Files in This Folder

| File | Purpose |
|------|---------|
| `config.json` | Column mappings, road systems, EPDO weights |
| `source_manifest.json` | Data source registry |
| `jurisdictions.json` | County definitions |
```

### E.4 hierarchy.json Template

Region/MPO/county hierarchy for multi-tier navigation:

```json
{
  "state": "{state_key}",
  "regions": [
    {
      "id": "{region_id}",
      "name": "{Region Name}",
      "shortName": "{Short}",
      "counties": ["{county1}", "{county2}"]
    }
  ],
  "mpos": [
    {
      "id": "{mpo_id}",
      "name": "{MPO Full Name}",
      "shortName": "{Acronym}",
      "counties": ["{county1}", "{county2}"]
    }
  ],
  "counties": {
    "{county_id}": {
      "name": "{County Name}",
      "fips": "{county_fips}",
      "region": "{region_id}",
      "mpo": "{mpo_id_or_null}",
      "center": [0.0, 0.0],
      "zoom": 11
    }
  }
}
```

### E.5 enhancements.json Template (Optional)

Deep Dive tab panel configuration for state-specific analysis columns:

```json
{
  "panels": [
    {
      "id": "driver_demographics",
      "title": "Driver Demographics",
      "description": "Age and gender analysis",
      "columns": ["_{xx}_driver_age", "_{xx}_driver_sex"],
      "chartType": "bar"
    },
    {
      "id": "speed_intelligence",
      "title": "Speed Intelligence",
      "description": "Posted vs actual speed analysis",
      "columns": ["_{xx}_speed_limit", "_{xx}_estimated_speed"],
      "chartType": "scatter"
    }
  ]
}
```

Only create this file if the state's raw data has unique columns worth analyzing beyond the standard set.

---

*End of Document — Crash Lens Universal Data Pipeline: Download to R2 Storage*
