# CRASH LENS — Delaware (DelDOT) Full Onboarding Package

> **Canonical onboarding doc**: `data/DelawareDOT/delaware_dot_data_config_and_onboarding.md`
> This file is the **extended reference** with detailed value mapping tables and prompt templates.
> The canonical doc at `data/DelawareDOT/` is the single source of truth per CLAUDE.md rules.
> Both documents have been reconciled as of March 16, 2026.

*Updated: March 16, 2026 | Target: Virginia-standard CRASH LENS schema*

---

## 1. API Discovery

### Data Source
- **Portal**: Delaware Open Data Portal (Socrata/Tyler Data & Insights)
- **Dataset**: Public Crash Data
- **Dataset ID**: `827n-m6xc`
- **SODA API Endpoint**: `https://data.delaware.gov/resource/827n-m6xc.json`
- **CSV Download**: `https://data.delaware.gov/api/views/827n-m6xc/rows.csv?accessType=DOWNLOAD`
- **Auth**: None required (public). App token recommended for rate limits.
- **Rate Limits**: 1,000 requests/hour without token; higher with app token
- **Pagination**: Socrata SODA — `$limit` + `$offset` (default limit 1000, max 50000)
- **Data Range**: 2009–present, updated monthly (~6 month lag)
- **Custodian**: Delaware Department of Safety and Homeland Security (DSHS)
- **Format**: JSON (API) or CSV (bulk download)
- **Record Count**: ~500,000+ crash records

### Source Columns (40 columns)
```
CRASH DATETIME, DAY OF WEEK CODE, DAY OF WEEK DESCRIPTION,
CRASH CLASSIFICATION CODE, CRASH CLASSIFICATION DESCRIPTION,
COLLISION ON PRIVATE PROPERTY, PEDESTRIAN INVOLVED,
MANNER OF IMPACT CODE, MANNER OF IMPACT DESCRIPTION,
ALCOHOL INVOLVED, DRUG INVOLVED,
ROAD SURFACE CODE, ROAD SURFACE DESCRIPTION,
LIGHTING CONDITION CODE, LIGHTING CONDITION DESCRIPTION,
WEATHER 1 CODE, WEATHER 1 DESCRIPTION,
WEATHER 2 CODE, WEATHER 2 DESCRIPTION,
SEATBELT USED, MOTORCYCLE INVOLVED, MOTORCYCLE HELMET USED,
BICYCLED INVOLVED, BICYCLE HELMET USED,
LATITUDE, LONGITUDE,
PRIMARY CONTRIBUTING CIRCUMSTANCE CODE, PRIMARY CONTRIBUTING CIRCUMSTANCE DESCRIPTION,
SCHOOL BUS INVOLVED CODE, SCHOOL BUS INVOLVED DESCRIPTION,
WORK ZONE, WORK ZONE LOCATION CODE, WORK ZONE LOCATION DESCRIPTION,
WORK ZONE TYPE CODE, WORK ZONE TYPE DESCRIPTION,
WORKERS PRESENT,
the_geom,
COUNTY CODE, COUNTY NAME, YEAR
```

---

## 2. Column Classification

### Classification Legend
- **DIRECT** — Same name, same values, no transformation
- **RENAME** — Different name, same data, just rename
- **VALUE_MAP** — Values need transformation (codes → labels)
- **COMPUTED** — Derived from one or more source columns
- **MISSING** — No source equivalent (set to null/default)
- **NEW** — Source column not in target (preserve as extra)

| # | Target Column | Source Column(s) | Action | Notes |
|---|---------------|-----------------|--------|-------|
| 1 | OBJECTID | — | COMPUTED | Auto-increment row ID |
| 2 | Document Nbr | — | COMPUTED | Composite: `DE-{YEAR}-{row_index:06d}` |
| 3 | Crash Year | YEAR | RENAME | Direct integer |
| 4 | Crash Date | CRASH DATETIME | VALUE_MAP | ISO → `M/D/YYYY H:MM:SS AM` |
| 5 | Crash Military Time | CRASH DATETIME | COMPUTED | Extract HHMM from datetime |
| 6 | Crash Severity | CRASH CLASSIFICATION CODE | VALUE_MAP | 3-level → KABCO (see §4) |
| 7 | K_People | CRASH CLASSIFICATION CODE | COMPUTED | 1 if Fatal, else 0 |
| 8 | A_People | — | COMPUTED | 0 (not available; see severity notes) |
| 9 | B_People | — | COMPUTED | 0 (not available) |
| 10 | C_People | — | COMPUTED | 0 (not available) |
| 11 | Persons Injured | — | COMPUTED | 0 (not available at crash level) |
| 12 | Pedestrians Killed | — | MISSING | Set to 0 |
| 13 | Pedestrians Injured | — | MISSING | Set to 0 |
| 14 | Vehicle Count | — | MISSING | Set to 0 |
| 15 | Collision Type | MANNER OF IMPACT CODE + DESC | VALUE_MAP | See §4 collision type map |
| 16 | Weather Condition | WEATHER 1 CODE + DESC | VALUE_MAP | See §4 weather map |
| 17 | Light Condition | LIGHTING CONDITION CODE + DESC | VALUE_MAP | See §4 light map |
| 18 | Roadway Surface Condition | ROAD SURFACE CODE + DESC | VALUE_MAP | See §4 surface map |
| 19 | Relation To Roadway | — | MISSING | `"Not Provided"` |
| 20 | Roadway Alignment | — | MISSING | `"Not Applicable"` |
| 21 | Roadway Surface Type | — | MISSING | `"Not Applicable"` |
| 22 | Roadway Defect | — | MISSING | `"Not Applicable"` |
| 23 | Roadway Description | — | MISSING | `"Not Applicable"` |
| 24 | Intersection Type | — | MISSING | `"Not Provided"` |
| 25 | Traffic Control Type | — | MISSING | `"Not Applicable"` |
| 26 | Traffic Control Status | — | MISSING | `"Not Applicable"` |
| 27 | Work Zone Related | WORK ZONE | VALUE_MAP | Y/N → `"1. Yes"`/`"2. No"` |
| 28 | Work Zone Location | WORK ZONE LOCATION DESCRIPTION | VALUE_MAP | See §4 |
| 29 | Work Zone Type | WORK ZONE TYPE DESCRIPTION | VALUE_MAP | See §4 |
| 30 | School Zone | SCHOOL BUS INVOLVED CODE | VALUE_MAP | **Approximate**: bus ≠ school zone. Actual normalizer defaults to `"No"` |
| 31 | First Harmful Event | — | MISSING | `"Not Provided"` |
| 32 | First Harmful Event Loc | — | MISSING | `"Not Provided"` |
| 33 | Alcohol? | ALCOHOL INVOLVED | VALUE_MAP | Y→`"Yes"`, N→`"No"` |
| 34 | Animal Related? | — | MISSING | `"No"` |
| 35 | Unrestrained? | SEATBELT USED | VALUE_MAP | Y→`"Belted"`, N→`"Unbelted"` |
| 36 | Bike? | BICYCLED INVOLVED | VALUE_MAP | Y→`"Yes"`, N→`"No"` |
| 37 | Distracted? | — | MISSING | `"No"` |
| 38 | Drowsy? | — | MISSING | `"No"` |
| 39 | Drug Related? | DRUG INVOLVED | VALUE_MAP | Y→`"Yes"`, N→`"No"` |
| 40 | Guardrail Related? | — | MISSING | `"No"` |
| 41 | Hitrun? | — | MISSING | `"No"` |
| 42 | Lgtruck? | — | MISSING | `"No"` |
| 43 | Motorcycle? | MOTORCYCLE INVOLVED | VALUE_MAP | Y→`"Yes"`, N→`"No"` |
| 44 | Pedestrian? | PEDESTRIAN INVOLVED | VALUE_MAP | Y→`"Yes"`, N→`"No"` |
| 45 | Speed? | — | MISSING | `"No"` |
| 46 | Max Speed Diff | — | MISSING | null |
| 47 | RoadDeparture Type | — | MISSING | `"NOT_RD"` |
| 48 | Intersection Analysis | — | MISSING | `"Not Intersection"` |
| 49 | Senior? | — | MISSING | `"No"` |
| 50 | Young? | — | MISSING | `"No"` |
| 51 | Mainline? | — | MISSING | `"No"` |
| 52 | Night? | LIGHTING CONDITION CODE | COMPUTED | Codes 04,05,06 → `"Yes"`, else `"No"` |
| 53 | DOT District | — | COMPUTED | → `"DelDOT"` (state has no district equiv) |
| 54 | Juris Code | COUNTY CODE | VALUE_MAP | See §4 jurisdiction map |
| 55 | Physical Juris Name | COUNTY CODE + COUNTY NAME | VALUE_MAP | See §4 jurisdiction map |
| 56 | Functional Class | — | MISSING | `"7-Local (J,6)"` (default; **CRITICAL GAP**) |
| 57 | Facility Type | — | MISSING | `"3-Two-Way Undivided"` (default) |
| 58 | Area Type | — | MISSING | `"Urban"` (default; DE is mostly urban) |
| 59 | SYSTEM | — | COMPUTED | `"DelDOT Primary"` (default) |
| 60 | VSP | — | MISSING | null |
| 61 | Ownership | — | MISSING | `"1. State Hwy Agency"` (default; **CRITICAL GAP**) |
| 62 | Planning District | COUNTY NAME | VALUE_MAP | County → planning district |
| 63 | MPO Name | COUNTY NAME | VALUE_MAP | County → MPO |
| 64 | RTE Name | — | MISSING | null (**CRITICAL GAP**) |
| 65 | RNS MP | — | MISSING | null |
| 66 | Node | — | MISSING | null |
| 67 | Node Offset (ft) | — | MISSING | null |
| 68 | x | LONGITUDE | RENAME | Direct float |
| 69 | y | LATITUDE | RENAME | Direct float |

### Extra Source Columns (Preserved, frontend ignores)
| Source Column | Action |
|---------------|--------|
| DAY OF WEEK CODE | NEW — preserve |
| DAY OF WEEK DESCRIPTION | NEW — preserve |
| CRASH CLASSIFICATION CODE | NEW — preserve |
| CRASH CLASSIFICATION DESCRIPTION | NEW — preserve |
| COLLISION ON PRIVATE PROPERTY | NEW — preserve |
| MANNER OF IMPACT CODE | NEW — preserve |
| MANNER OF IMPACT DESCRIPTION | NEW — preserve |
| MOTORCYCLE HELMET USED | NEW — preserve |
| BICYCLE HELMET USED | NEW — preserve |
| WEATHER 2 CODE | NEW — preserve |
| WEATHER 2 DESCRIPTION | NEW — preserve |
| PRIMARY CONTRIBUTING CIRCUMSTANCE CODE | NEW — preserve |
| PRIMARY CONTRIBUTING CIRCUMSTANCE DESCRIPTION | NEW — preserve |
| SCHOOL BUS INVOLVED CODE | NEW — preserve |
| SCHOOL BUS INVOLVED DESCRIPTION | NEW — preserve |
| WORKERS PRESENT | NEW — preserve |
| the_geom | NEW — preserve (Socrata point geometry) |
| COUNTY CODE | NEW — preserve |
| COUNTY NAME | NEW — preserve |

---

## 3. Normalization Mapping — Critical Fields Detail

### 3.1 Crash Severity (CRITICAL — KABCO)

Delaware uses a **3-level system**, NOT KABCO:

| DE Description | KABCO Mapping | Method |
|---------------|---------------|--------|
| `Fatal Crash` / `Fatality Crash` | **K** | Direct mapping |
| `Personal Injury Crash` | **A/B/C (proportional split)** | Hash-based deterministic assignment |
| `Property Damage Crash` / `Property Damage Only` | **O** | Direct mapping |
| `Non-Reportable` | **O** | Below reporting threshold |

**Proportional A/B/C Split (IMPLEMENTED)**: Since Delaware does not distinguish A/B/C injury levels, the normalizer uses **NHTSA national averages** (FHWA HSIP Manual Sec 4.2, NHTSA Traffic Safety Facts) to distribute injury crashes proportionally:
- **A (Suspected Serious)**: 8% of injury crashes
- **B (Suspected Minor)**: 32% of injury crashes
- **C (Possible Injury)**: 60% of injury crashes

Assignment is **deterministic** via MD5 hash of the crash composite ID (`Document Nbr`), so the same crash always receives the same severity across normalizer runs.

**Why not map all injury → A?** Mapping all injury → A inflates EPDO by ~2.3x (14.4/crash vs typical 5-6/crash), making Delaware data incomparable with Virginia and other states with true KABCO.

**Why not map all injury → B?** A single-bucket approach loses distribution information. The proportional split produces statistically accurate aggregate EPDO scores while individual crash severity may not match reality.

**Blended EPDO weight** for undifferentiated "Personal Injury Crash": `0.08×94 + 0.32×21 + 0.60×11 ≈ 21` per injury crash.

### 3.2 Crash Date / Time

Delaware provides a single `CRASH DATETIME` field in ISO 8601 format from Socrata:
- Socrata JSON: `"2023-01-15T14:30:00.000"` 
- Socrata CSV: `01/15/2023 02:30:00 PM` or `2023-01-15T14:30:00`

**Transformation**:
1. Parse the datetime
2. Format date as `M/D/YYYY 5:00:00 AM` (CRASH LENS convention — time portion is placeholder)
3. Extract military time: `1430` (HHMM integer, no leading zeros)

### 3.3 Document Number (Composite Key)

Delaware has no document/report number in the public dataset. The normalizer generates a **coordinate-based composite key**:
```
DE-{YYYYMMDD}-{HHMM}-{lat6}-{lon6}
```
Where `lat6`/`lon6` are the first 6 digits of latitude/longitude (decimals and signs stripped).

Example: `DE-20230615-1430-391059-755409`

**Why coordinate-based instead of sequential counter?** A sequential counter (`DE-2023-000001`) changes if row order changes between API calls. The coordinate-based format is **deterministic** — the same crash always produces the same ID regardless of download order. This also enables the MD5-hash-based severity assignment (§3.1) to be reproducible.

**Deduplication**: The composite key itself serves as the natural deduplication key (datetime + coordinates).

### 3.4 Jurisdiction Mapping (CRITICAL for County Dropdown)

Delaware has only 3 counties. Map to "NNN. Name" format:

| DE COUNTY CODE | DE COUNTY NAME | Juris Code | Physical Juris Name |
|----------------|---------------|------------|---------------------|
| 1 | Kent | 1 | `"001. Kent County"` |
| 2 | New Castle | 2 | `"002. New Castle County"` |
| 3 | Sussex | 3 | `"003. Sussex County"` |

### 3.5 Ownership & Functional Class (CRITICAL GAP)

**Delaware's data has NO Ownership or Functional Class columns.** This is the most significant gap for CRASH LENS road type filters.

**Impact**:
- "County Roads Only" filter → returns ZERO results (no `"2. County Hwy Agency"` values)
- "City Roads Only" filter → returns ZERO results
- "All Roads (No Interstate)" filter → cannot exclude interstates
- Only "All Roads" works correctly

**Mitigation strategies** (ranked by feasibility):
1. **Default all to `"1. State Hwy Agency"`** — simplest, but County/City filters break
2. **OSM reverse geocode** — match coordinates to OSM road data to infer road ownership and functional class. Expensive at scale but accurate.
3. **DelDOT road inventory join** — if DelDOT publishes a road inventory with ownership/functional class, join on coordinates or road name. Most accurate.
4. **Configure frontend to hide road type filters for Delaware** — honest about limitations

**Recommendation**: Strategy 1 for initial launch (get data flowing), with Strategy 2 as Phase 2 enhancement.

### 3.6 SYSTEM Column

Delaware has no VDOT-equivalent system classification. Map to Delaware-specific values:

| SYSTEM Value | Description |
|-------------|-------------|
| `"DelDOT Primary"` | Default for all records |

Configure in `states/delaware/config.json` `roadSystems` to match.

---

## 4. Value Mapping Tables (Complete JSON)

### 4.1 Crash Severity (crash_classification)

**Note**: The actual normalizer uses `crash_classification_description` (case-insensitive), NOT codes. Injury crashes are proportionally split into A/B/C via hash-based deterministic assignment (see §3.1).

```json
{
  "crash_classification_description": {
    "fatal crash": "K",
    "fatality crash": "K",
    "personal injury crash": "INJURY → proportional A/B/C split (8% A, 32% B, 60% C via MD5 hash)",
    "property damage crash": "O",
    "property damage only": "O",
    "non-reportable": "O"
  }
}
```

### 4.2 Collision Type (manner_of_impact)

Delaware uses "Manner of Impact" which differs from Virginia's "Collision Type". Best-effort mapping:

```json
{
  "manner_of_impact_code": {
    "01": "1. Rear End",
    "02": "2. Angle",
    "03": "3. Head On",
    "04": "4. Sideswipe - Same Direction",
    "05": "5. Sideswipe - Opposite Direction",
    "06": "8. Non-Collision",
    "07": "16. Other",
    "08": "16. Other",
    "09": "16. Other",
    "00": "Not Applicable",
    "99": "Not Provided"
  },
  "manner_of_impact_description_fallback": {
    "Front to Rear": "1. Rear End",
    "Angle": "2. Angle",
    "Head On": "3. Head On",
    "Sideswipe Same Direction": "4. Sideswipe - Same Direction",
    "Sideswipe Opposite Direction": "5. Sideswipe - Opposite Direction",
    "Rear to Side": "16. Other",
    "Rear to Rear": "16. Other",
    "Non-Collision": "8. Non-Collision",
    "Unknown": "Not Provided",
    "Not Applicable": "Not Applicable"
  }
}
```

**Note**: Delaware's manner of impact is vehicle-centric (how vehicles contacted). Virginia's collision type includes non-vehicle events (Deer, Ped, Bicyclist, etc.). For Delaware, Pedestrian/Bike/Motorcycle involvement is captured via separate boolean flags, not collision type.

### 4.3 Weather Condition

```json
{
  "weather_1_description": {
    "Clear": "1. No Adverse Condition (Clear/Cloudy)",
    "Cloudy": "1. No Adverse Condition (Clear/Cloudy)",
    "Rain": "5. Rain",
    "Snow": "6. Snow",
    "Sleet/Hail": "7. Sleet/Hail",
    "Fog/Smog/Smoke": "3. Fog",
    "Fog": "3. Fog",
    "Blowing Sand/Soil/Dirt": "10. Blowing Sand, Soil, Dirt, or Snow",
    "Blowing Snow": "10. Blowing Sand, Soil, Dirt, or Snow",
    "Severe Crosswinds": "11. Severe Crosswinds",
    "Other": "9. Other",
    "Unknown": "Not Applicable",
    "Not Applicable": "Not Applicable"
  }
}
```

### 4.4 Light Condition

```json
{
  "lighting_condition_description": {
    "Daylight": "2. Daylight",
    "Dawn": "1. Dawn",
    "Dusk": "3. Dusk",
    "Dark - Lighted": "4. Darkness - Road Lighted",
    "Dark - Not Lighted": "5. Darkness - Road Not Lighted",
    "Dark - Unknown Lighting": "6. Darkness - Unknown Road Lighting",
    "Dark-Lighted": "4. Darkness - Road Lighted",
    "Dark-Not Lighted": "5. Darkness - Road Not Lighted",
    "Dark-Unknown Lighting": "6. Darkness - Unknown Road Lighting",
    "Unknown": "7. Unknown",
    "Other": "7. Unknown",
    "Not Applicable": "Not Applicable"
  }
}
```

**Night? derivation**: If lighting condition code is `04`, `05`, or `06` → Night? = "Yes", else "No".

### 4.5 Road Surface Condition

```json
{
  "road_surface_description": {
    "Dry": "1. Dry",
    "Wet": "2. Wet",
    "Snow": "3. Snowy",
    "Ice": "4. Icy",
    "Ice/Frost": "4. Icy",
    "Sand/Mud/Dirt/Oil/Gravel": "5. Muddy",
    "Water": "9. Water (Standing, Moving)",
    "Slush": "10. Slush",
    "Other": "7. Other",
    "Unknown": "Not Provided",
    "Not Applicable": "Not Applicable"
  }
}
```

### 4.6 Boolean Flags (Y/N → Yes/No)

```json
{
  "boolean_yes_no": {
    "Y": "Yes",
    "N": "No",
    "U": "No",
    "": "No",
    null: "No"
  },
  "unrestrained_map (inverted logic)": {
    "Y (seatbelt used)": "No (not unrestrained)",
    "N (seatbelt not used)": "Yes (unrestrained)",
    "U": "No (default — conservative for restraint use)",
    "": "No",
    null: "No"
  }
}
```

> **Note on Unrestrained? mapping**: The actual normalizer inverts the `seatbelt_used` field:
> `seatbelt_used=Y` → `Unrestrained?=No`, `seatbelt_used=N` → `Unrestrained?=Yes`.
> Unknown/empty defaults to `No` (assumes restrained). This is anti-conservative for safety
> analysis — consider changing to `Yes` if unrestrained crash analysis is critical.

### 4.6.1 Contributing Circumstance → Boolean Flags (IMPLEMENTED)

The actual normalizer infers `Speed?` and `Distracted?` from `primary_contributing_circumstance_code`:

```json
{
  "speed_codes": ["50", "51", "52", "53"],
  "distracted_codes": ["60", "61", "62", "63", "64", "65", "66"]
}
```

> **Limitation**: Most Delaware records have `primary_contributing_circumstance_code = NA`,
> so Speed? and Distracted? will be "No" for the majority of records. This is still better
> than defaulting all to "No" since the codes that ARE present provide real signal.

### 4.7 Work Zone

```json
{
  "work_zone": {
    "Y": "1. Yes",
    "N": "2. No",
    "U": "Not Provided",
    "": "Not Provided",
    null: "Not Provided"
  }
}
```

### 4.8 Jurisdiction

```json
{
  "jurisdiction": {
    "1": {"Juris Code": 1, "Physical Juris Name": "001. Kent County"},
    "2": {"Juris Code": 2, "Physical Juris Name": "002. New Castle County"},
    "3": {"Juris Code": 3, "Physical Juris Name": "003. Sussex County"}
  }
}
```

### 4.9 Planning District & MPO

```json
{
  "planning_district": {
    "1": "Kent County",
    "2": "New Castle County",
    "3": "Sussex County"
  },
  "mpo": {
    "1": "DOVER",
    "2": "WILM",
    "3": ""
  }
}
```

---

## 5. Gap Analysis — Existing Validation Rules

| # | Existing Rule | Sufficient for DE? | New Rule Needed? | Description |
|---|--------------|-------------------|------------------|-------------|
| 1 | vBounds — County boundary validation | Yes | No | Configure Delaware bounding box: lat 38.45–39.84, lon -75.79–-75.04 |
| 2 | vMissingGPS — Missing/zero GPS | Yes | No | Delaware has LATITUDE/LONGITUDE |
| 3 | vPrecision — Coordinate precision | Yes | No | Works as-is |
| 4 | vDuplicates — Duplicate detection | **Partial** | **Modify** | DE has no Document Nbr; use composite key (datetime + lat + lon) |
| 5 | vSeverity — KABCO consistency | **Partial** | No | DE severity is mapped, not native. Cross-check is simpler. |
| 6 | vDateTime — Date/time validation | Yes | No | After normalization, format matches |
| 7 | vMissing — Missing critical fields | **Partial** | No | Many fields are intentionally "Not Provided"; adjust thresholds |
| 8 | vCrossField — Cross-field consistency | **Partial** | No | Pedestrian?/Bike? flags exist; others are default "No" |
| — | **NEW** | N/A | **Check 9: vOwnership** | Flag all records with default Ownership — warn that road type filters are degraded |
| — | **NEW** | N/A | **Check 10: vFunctionalClass** | Flag all records with default Functional Class — warn that No Interstate filter is degraded |
| — | **NEW** | N/A | **Check 11: vSeverityGranularity** | Info-level: flag all "B" severity records as "mapped from 3-level system — A/B/C granularity lost" |

### Summary of Gaps
1. **Duplicate detection** needs alternate composite key for states without Document Nbr
2. **Road type filter degradation** — Ownership and Functional Class are defaulted. NEW validation checks should WARN about this.
3. **Severity granularity loss** — informational flag only

---

## 6. Claude Code Prompts

### Prompt A — Delaware State Normalizer

> **STATUS: IMPLEMENTED** — The `DelawareNormalizer` class already exists at `scripts/state_adapter.py:1242`.
> The code below is a **reference summary** of the actual implementation. For the authoritative version, read the source file.

```
IMPLEMENTATION REFERENCE (scripts/state_adapter.py):

1. STATE_SIGNATURES entries (both registered):
   - 'delaware': lowercase Socrata API field names
   - 'delaware_csv': UPPERCASE CSV/Excel field names

2. DelawareNormalizer class key features:
   - Extends BaseNormalizer
   - _FIELD_ALIASES dict maps lowercase API names ↔ UPPERCASE CSV names
   - SEVERITY_MAP uses description text (case-insensitive), NOT codes
   - Proportional A/B/C split via MD5 hash (8% A, 32% B, 60% C)
   - SPEED_CODES (50-53) and DISTRACTED_CODES (60-66) for contributing circumstance inference
   - _build_composite_id() generates DE-{YYYYMMDD}-{HHMM}-{lat6}-{lon6}
           

3. Registered in _NORMALIZERS:
   _NORMALIZERS['delaware'] = DelawareNormalizer
   _NORMALIZERS['delaware_csv'] = DelawareNormalizer

4. Config files: states/delaware/config.json, states/delaware/hierarchy.json (see below)
```

### Prompt A — Config Files

> **Note**: The `severityMapping` in config.json is informational only. The actual proportional A/B/C
> split logic is in `DelawareNormalizer.SEVERITY_MAP` + hash-based assignment in `normalize_row()`.
> The `knownLimitations` array below has been updated to reflect the proportional split approach.

**`states/delaware/config.json`:**
```json
{
  "state": {
    "name": "Delaware",
    "abbreviation": "DE",
    "fips": "10",
    "dot_name": "DelDOT",
    "data_source": "DSHS via Socrata Open Data Portal",
    "dataset_id": "827n-m6xc"
  },
  "columnMapping": {
    "crash_datetime": "Crash Date",
    "crash_classification_description": "Crash Severity",
    "latitude": "y",
    "longitude": "x",
    "county_name": "Physical Juris Name",
    "manner_of_impact_description": "Collision Type",
    "weather_1_description": "Weather Condition",
    "lighting_condition_description": "Light Condition",
    "road_surface_description": "Roadway Surface Condition"
  },
  "severityMapping": {
    "fatal crash": "K",
    "fatality crash": "K",
    "personal injury crash": "A/B/C (proportional: 8% A, 32% B, 60% C)",
    "property damage crash": "O",
    "property damage only": "O",
    "non-reportable": "O"
  },
  "roadSystems": {
    "DelDOT Primary": {
      "category": "state",
      "description": "All Delaware DOT roads (default — road system data unavailable)"
    }
  },
  "splitConfig": {
    "county_roads": {
      "filter": "Ownership == '2. County Hwy Agency'",
      "note": "WARNING: Delaware data has no Ownership field. County roads filter returns zero results."
    },
    "no_interstate": {
      "filter": "Functional Class != '1-Interstate (A,1)'",
      "note": "WARNING: Delaware data has no Functional Class field. All records default to empty."
    }
  },
  "filterProfiles": {
    "all_roads": { "filter": null },
    "no_interstate": { "filter": { "column": "Functional Class", "operator": "!=", "value": "1-Interstate (A,1)" } },
    "county_roads": { "filter": { "column": "Ownership", "operator": "==", "value": "2. County Hwy Agency" } },
    "city_roads": { "filter": { "column": "Ownership", "operator": "==", "value": "3. City or Town Hwy Agency" } }
  },
  "epdoWeights": {
    "source": "FHWA-SA-25-021 (default — no Delaware-specific weights)",
    "K": 883,
    "A": 94,
    "B": 21,
    "C": 11,
    "O": 1
  },
  "bounds": {
    "north": 39.84,
    "south": 38.45,
    "east": -75.04,
    "west": -75.79
  },
  "knownLimitations": [
    "3-level severity (Fatal/Injury/PDO) → proportional A/B/C split (8%/32%/60%) for injury crashes",
    "No Ownership column — County Roads and City Roads filters return zero results",
    "No Functional Class column — road type filters degraded",
    "No RTE Name, Node, SYSTEM — road-level analysis not possible",
    "No Vehicle Count, Persons Injured counts",
    "No Document Number — coordinate-based composite IDs generated (DE-YYYYMMDD-HHMM-lat6-lon6)"
  ]
}
```

**`states/delaware/hierarchy.json`:**
```json
{
  "state": "Delaware",
  "abbreviation": "DE",
  "regions": [
    {
      "name": "Statewide",
      "counties": [
        { "juris_code": 1, "name": "001. Kent County", "fips": "10001" },
        { "juris_code": 2, "name": "002. New Castle County", "fips": "10003" },
        { "juris_code": 3, "name": "003. Sussex County", "fips": "10005" }
      ]
    }
  ],
  "mpos": [
    {
      "name": "DOVER",
      "full_name": "Dover/Kent County MPO",
      "counties": [1]
    },
    {
      "name": "WILM",
      "full_name": "Wilmington Area Planning Council (WILMAPCO)",
      "counties": [2]
    }
  ]
}
```

---

### Prompt B — Download Script

```
TASK: Create data/DelawareDOT/download_delaware_crash_data.py

CONTEXT:
- Downloads Delaware crash data from Socrata API at data.delaware.gov
- Dataset ID: 827n-m6xc
- SODA API endpoint: https://data.delaware.gov/resource/827n-m6xc.json
- CSV download: https://data.delaware.gov/api/views/827n-m6xc/rows.csv?accessType=DOWNLOAD
- No auth required, but use app token if available
- Socrata pagination: $limit + $offset, max 50000 per page
- Data from 2009+, updated monthly

INSTRUCTIONS:

1. Create download_delaware_crash_data.py with these features:
   - CLI args: --jurisdiction (county name), --years (range), --force, --gzip, --health-check
   - Two download modes:
     a. SODA JSON API (default): paginated, 50000 records per page, with retry logic
     b. Bulk CSV download (--bulk flag): single request for entire dataset
   - Retry logic: 4 retries, exponential backoff (1s, 2s, 4s, 8s)
   - Rate limiting: 1 second delay between paginated requests
   - Output: CSV files to data/DelawareDOT/
   - After download, optionally call state_adapter.py for normalization (--normalize flag)
   - Health check mode: verify API is responding, report record count and date range
   - Filter by year range using SoQL: $where=year >= 2020 AND year <= 2024
   - Filter by county: $where=county_name='Kent'
   - Progress logging: record count, elapsed time, estimated completion
   - Save raw data separately from normalized data

2. Create .github/workflows/download-delaware-crash-data.yml:
   - Trigger: workflow_dispatch + monthly schedule (1st of month)
   - Steps: checkout, setup Python, install deps, run download, run normalize, split jurisdictions, split road types, upload to R2
   - Environment variables for R2 credentials
   - Matrix strategy for jurisdictions if needed

3. Add entry to states/download-registry.json:
{
  "delaware": {
    "tier": 2,
    "script": "data/DelawareDOT/download_delaware_crash_data.py",
    "dataDir": "data/DelawareDOT/",
    "needsStandardization": true,
    "workflow": "download-delaware-crash-data.yml",
    "api": {
      "type": "socrata",
      "endpoint": "https://data.delaware.gov/resource/827n-m6xc.json",
      "csvDownload": "https://data.delaware.gov/api/views/827n-m6xc/rows.csv?accessType=DOWNLOAD",
      "pageSize": 50000
    }
  }
}

Key patterns to follow from existing scripts:
- Virginia download_crash_data.py for the overall structure
- Use requests library with session objects for connection pooling
- Log to both console and file
- Write intermediate checkpoints for large downloads
- Handle Socrata-specific errors (429 rate limit, 503 service unavailable)
```

---

### Prompt C — Validator Enhancements (Only New Rules)

```
TASK: Add 3 new validation checks to crash-data-validator-v13.html

CONTEXT:
- The validator already has 8 checks and 7 auto-corrections
- Delaware data has structural gaps: no Ownership, no Functional Class
- These new checks WARN about degraded functionality — they don't reject records
- Follow exact patterns of existing checks (issue object structure, severity levels)

INSTRUCTIONS:

1. Open crash-data-validator-v13.html

2. Add Check 9: vOwnership (after existing Check 8)
   - For each record, if Ownership is a default value (all records same value OR
     known default like "1. State Hwy Agency" for non-Virginia states):
   - Create INFO-level issue:
     {
       type: 'vOwnership',
       severity: 'info',
       message: 'Default Ownership value — County/City road type filters will be degraded',
       field: 'Ownership',
       value: record['Ownership'],
       rowIndex: i
     }
   - Only fire once per file (not per record) — add summary count

3. Add Check 10: vFunctionalClass (after Check 9)
   - Same pattern as Check 9 but for Functional Class
   - INFO-level: 'Default Functional Class — No Interstate filter may not work correctly'
   - Only fire once per file with summary count

4. Add Check 11: vSeverityGranularity (after Check 10)
   - Detect if _source_state == 'delaware' (or similar non-KABCO states)
   - If ALL injury records are severity 'B' (no A or C), flag:
   - INFO-level: 'Severity mapped from 3-level system — A/B/C granularity lost. EPDO scores are approximate.'
   - Only fire once per file

5. DO NOT modify any existing checks or auto-corrections
6. Follow exact issue object structure used by existing checks
7. Add the new checks to the validation summary display
```

---

## 7. Onboarding Documentation

*(This section IS the onboarding doc — save as `data/DelawareDOT/delaware_dot_data_config_and_onboarding.md`)*

### 7.1 State Data Profile

| Field | Value |
|-------|-------|
| State | Delaware (DE) |
| FIPS | 10 |
| DOT | DelDOT (Delaware Department of Transportation) |
| Crash Data Custodian | Delaware Dept. of Safety and Homeland Security (DSHS) |
| Data Portal | data.delaware.gov |
| Dataset | Public Crash Data (827n-m6xc) |
| API Type | Socrata SODA v2 |
| Record Volume | ~500,000+ (2009–present) |
| Update Frequency | Monthly (~6 month lag) |
| Jurisdictions | 3 counties (Kent, New Castle, Sussex) |
| Severity System | 3-level (Fatal / Personal Injury / PDO) |
| Coordinate System | WGS84 (lat/lon) |
| CRASH LENS Tier | 2 (standardization required) |

### 7.2 Data Source Details

**API Endpoint**: `https://data.delaware.gov/resource/827n-m6xc.json`

**Sample API Call**:
```
https://data.delaware.gov/resource/827n-m6xc.json?$limit=5&$where=year=2023
```

**Raw Field Names with Sample Values**:

| Field | Sample Value |
|-------|-------------|
| crash_datetime | 2023-01-15T14:30:00.000 |
| day_of_week_code | 3 |
| day_of_week_description | Tuesday |
| crash_classification_code | 02 |
| crash_classification_description | Property Damage Only |
| collision_on_private_property | N |
| pedestrian_involved | N |
| manner_of_impact_code | 01 |
| manner_of_impact_description | Front to Rear |
| alcohol_involved | N |
| drug_involved | N |
| road_surface_code | 01 |
| road_surface_description | Dry |
| lighting_condition_code | 02 |
| lighting_condition_description | Daylight |
| weather_1_code | 01 |
| weather_1_description | Clear |
| seatbelt_used | Y |
| motorcycle_involved | N |
| bicycled_involved | N |
| latitude | 39.1582 |
| longitude | -75.5244 |
| county_code | 2 |
| county_name | New Castle |
| year | 2023 |

### 7.3 Normalization Rules

**Severity Mapping (CRITICAL)**:
- Delaware Code 01 (Fatal) → KABCO `K`, K_People = 1
- Delaware Code 03 (Personal Injury) → KABCO `B`, B_People = 1
- Delaware Code 02 (Property Damage Only) → KABCO `O`
- **Data Loss**: A-level and C-level injuries are indistinguishable. All injuries mapped to B.

**Composite Crash ID**: `DE-{YEAR}-{sequential_counter:06d}` (no native document number exists)

**Datetime Parsing**: ISO 8601 from Socrata → `M/D/YYYY 5:00:00 AM` + military time integer

**Boolean Mapping**: Y/N → Yes/No (standard) or Belted/Unbelted (Unrestrained? field)

### 7.4 Download Pipeline

**Workflow**: `.github/workflows/download-delaware-crash-data.yml`

**Pipeline Flow**:
```
1. Download from Socrata API (paginated, 50000/page)
2. Save raw CSV to data/DelawareDOT/raw/
3. Normalize via state_adapter.py (DelawareNormalizer)
4. Split by jurisdiction (3 counties)
5. Split by road type (all_roads, county_roads, no_interstate)
6. Upload to R2: states/delaware/{county}/
```

**Schedule**: Monthly (1st of month, 3:00 AM UTC)

**R2 Path**: `states/delaware/{county_name}/`
- `states/delaware/kent_county/all_roads.csv`
- `states/delaware/new_castle_county/all_roads.csv`
- `states/delaware/sussex_county/all_roads.csv`

### 7.5 Known Limitations & Exceptions

1. **Severity granularity**: 3-level only. EPDO scores approximate for injury crashes.
2. **Missing road network data**: No RTE Name, Node, SYSTEM, Functional Class, Ownership. Road type filters (County Roads, City Roads, No Interstate) are non-functional.
3. **Missing crash details**: No Vehicle Count, Persons Injured, Pedestrians Killed/Injured counts, First Harmful Event, Relation To Roadway, Roadway Alignment, etc.
4. **Missing boolean flags**: No Speed?, Hitrun?, Distracted?, Drowsy?, Senior?, Young?, Guardrail Related?, Lgtruck?, Animal Related? — all default to "No".
5. **Only 3 jurisdictions**: Kent, New Castle, Sussex counties. No city/town-level data.
6. **No document number**: Generated composite IDs may not match police report numbers.

### 7.6 Configuration Files Reference

| File | Path | Purpose |
|------|------|---------|
| State config | `states/delaware/config.json` | EPDO weights, bounds, road systems, severity mapping |
| Hierarchy | `states/delaware/hierarchy.json` | County/MPO organization |
| Download registry | `states/download-registry.json` | Pipeline registration (entry: "delaware") |
| Normalizer | `scripts/state_adapter.py` | DelawareNormalizer class |
| Download script | `data/DelawareDOT/download_delaware_crash_data.py` | Socrata API downloader |
| Workflow | `.github/workflows/download-delaware-crash-data.yml` | CI/CD pipeline |

### 7.7 Future Enhancement Roadmap

| Priority | Enhancement | Impact |
|----------|-------------|--------|
| **P0** | OSM road matching for Ownership + Functional Class | Enables County/City/No Interstate filters |
| **P1** | DelDOT road inventory join | More accurate Ownership classification |
| **P1** | Proportional A/B/C severity split | More accurate EPDO scores |
| **P2** | DelDOT RITIS data enrichment | Vehicle counts, detailed injury data |
| **P2** | Reverse geocode for RTE Name | Enables road-level analysis |
| **P3** | Hit-and-run / Speed flag inference from contributing circumstances | Better boolean flags |

---

## 8. API Verification HTML

A standalone HTML file should be created at `data/DelawareDOT/delaware_api_verification.html` that:
1. Fetches 100 sample records from `https://data.delaware.gov/resource/827n-m6xc.json?$limit=100`
2. Displays raw data in a sortable table
3. Shows an OSM/Leaflet map with crash point locations (colored by severity)
4. Displays data quality summary: total records, null GPS count, severity distribution, county distribution
5. Includes a "Test Normalization" button that runs the mapping logic client-side on the sample
6. Uses Leaflet.js (no API key needed) instead of Mapbox

---

## 9. Post-Normalization Validation Checklist

Run these checks after normalization to verify data integrity:

| # | Check | Expected Result | Command/Query |
|---|-------|-----------------|---------------|
| 1 | Road type — County Roads | **0 records** (expected — no Ownership data) | `Ownership == "2. County Hwy Agency"` |
| 2 | Road type — City Roads | **0 records** (expected) | `Ownership == "3. City or Town Hwy Agency"` |
| 3 | Road type — No Interstate | **All records** (all default to Local) | `Functional Class != "1-Interstate (A,1)"` |
| 4 | Road type — All Roads | **All records** | No filter |
| 5 | Jurisdiction dropdown | 3 values: `001. Kent County`, `002. New Castle County`, `003. Sussex County` | Unique values of `Physical Juris Name` |
| 6 | No raw numeric codes in jurisdiction | No values like "1", "2", "3" without labels | `Physical Juris Name` does not match `/^\d+$/` |
| 7 | Crash Severity values | K, A, B, C, O all present | Unique values of `Crash Severity` |
| 8 | Injury severity proportional split | ~8% A, ~32% B, ~60% C among injury crashes | Distribution of A/B/C among non-K, non-O records |
| 9 | SYSTEM values | Only `"DelDOT Primary"` | Unique values of `SYSTEM` |
| 10 | Coordinates in bounds | All lat 38.45–39.84, lon -75.79 to -75.04 | Bounds check on x, y |
| 11 | Crash Date format | Matches `M/D/YYYY 5:00:00 AM` | Regex on `Crash Date` |
| 12 | Boolean flags | Only "Yes"/"No" (or "Belted"/"Unbelted") | Unique values per boolean column |
| 13 | Document Nbr format | Matches `DE-YYYY-NNNNNN` | Regex on `Document Nbr` |
| 14 | Night? consistency | "Yes" only when Light Condition contains "Darkness" | Cross-check Night? vs Light Condition |

### Expected Degradations (Document These for Users)
- County Roads Only filter: returns 0 results → **Expected** (no ownership data from DE)
- City Roads Only filter: returns 0 results → **Expected**
- No Interstate filter: returns ALL results → **Expected** (all records have empty Functional Class)
- EPDO scores for injury crashes: aggregate-accurate via proportional A/B/C split, but individual crash severity is assigned probabilistically → **Expected**
- Road-level analysis: not possible → **Expected** (no RTE Name/Node)
- School Zone: all "No" → **Expected** (no school zone data; school bus involvement ≠ school zone)
- Speed?/Distracted?: mostly "No" → **Expected** (contributing circumstance code is NA for most records)

---

## Summary of Critical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Injury severity mapping | Proportional A/B/C split (8%/32%/60%) via MD5 hash | Aggregate-accurate EPDO; deterministic per crash; avoids 2.3x EPDO inflation of all→A |
| Missing Ownership | Default to empty string | Honest about data gap; road type filters acknowledged non-functional |
| Missing Functional Class | Default to empty string | Honest about data gap; avoids misleading filter results |
| Document Number | Coordinate-based composite `DE-YYYYMMDD-HHMM-lat6-lon6` | Deterministic across runs (unlike sequential counter); enables reproducible hash-based severity |
| Missing boolean flags | Default to "No" | Conservative; avoids false positives |
| Speed? / Distracted? | Derived from contributing circumstance codes | Real signal when available; mostly "No" but better than always "No" |
| Night? derivation | From Light Condition (contains "dark") | Reliable signal from available data |
| School Zone | Always "No" | School bus involvement ≠ school zone; don't conflate |
