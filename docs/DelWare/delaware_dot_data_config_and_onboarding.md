# CRASH LENS — Delaware (DelDOT) Full Onboarding Package

*Generated: March 16, 2026 | Target: Virginia-standard CRASH LENS schema*

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
| 30 | School Zone | SCHOOL BUS INVOLVED CODE | VALUE_MAP | Approximate: bus=school zone indicator |
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
| 53 | VDOT District | — | COMPUTED | → `"DelDOT"` (state has no district equiv) |
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

| DE Code | DE Description | KABCO Mapping | K_People | A_People | B_People | C_People |
|---------|---------------|---------------|----------|----------|----------|----------|
| 01 | Fatal | **K** | 1 | 0 | 0 | 0 |
| 03 | Personal Injury | **B** (default) | 0 | 0 | 1 | 0 |
| 02 | Property Damage Only | **O** | 0 | 0 | 0 | 0 |

**Assumption & Data Loss**: Delaware does not distinguish A/B/C injury levels. All "Personal Injury" crashes are mapped to severity **B** (non-incapacitating injury) as the middle-ground default. This means:
- True A-level (incapacitating) injuries are UNDERCOUNTED
- True C-level (possible injury) crashes are OVERCOUNTED as B
- EPDO scores will be approximate for injury crashes
- **Alternative**: Use proportional A/B/C split based on national averages (~15% A, 45% B, 40% C). This is more accurate for aggregate statistics but adds complexity.

**Recommended approach**: Map to B by default. Document the limitation. Allow config override.

### 3.2 Crash Date / Time

Delaware provides a single `CRASH DATETIME` field in ISO 8601 format from Socrata:
- Socrata JSON: `"2023-01-15T14:30:00.000"` 
- Socrata CSV: `01/15/2023 02:30:00 PM` or `2023-01-15T14:30:00`

**Transformation**:
1. Parse the datetime
2. Format date as `M/D/YYYY 5:00:00 AM` (CRASH LENS convention — time portion is placeholder)
3. Extract military time: `1430` (HHMM integer, no leading zeros)

### 3.3 Document Number (Composite Key)

Delaware has no document/report number in the public dataset. Generate a composite key:
```
DE-{YEAR}-{zero-padded-row-index}
```
Example: `DE-2023-000001`, `DE-2023-000002`

**Deduplication**: Use `CRASH DATETIME` + `LATITUDE` + `LONGITUDE` as the natural composite key for duplicate detection.

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
```json
{
  "crash_classification_code": {
    "01": {"Crash Severity": "K", "K_People": 1, "A_People": 0, "B_People": 0, "C_People": 0},
    "03": {"Crash Severity": "B", "K_People": 0, "A_People": 0, "B_People": 1, "C_People": 0},
    "02": {"Crash Severity": "O", "K_People": 0, "A_People": 0, "B_People": 0, "C_People": 0}
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
  "seatbelt_map": {
    "Y": "Belted",
    "N": "Unbelted",
    "U": "Belted",
    "": "Belted",
    null: "Belted"
  }
}
```

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

```
TASK: Add a DelawareNormalizer to scripts/state_adapter.py

CONTEXT:
- CRASH LENS normalizes all state crash data to Virginia's schema
- Delaware data comes from Socrata API at data.delaware.gov (dataset 827n-m6xc)
- Delaware has 40 columns, Virginia target has 69 columns
- Key challenge: Delaware has 3-level severity (Fatal/Injury/PDO), not KABCO
- Key challenge: Delaware has NO Ownership, Functional Class, RTE Name, SYSTEM columns
- Key challenge: Delaware has no Document Number — must generate composite ID

INSTRUCTIONS:

1. Add STATE_SIGNATURES entry:
STATE_SIGNATURES['delaware'] = {
    'required': ['crash_datetime', 'crash_classification_description', 'latitude', 'longitude'],
    'optional': ['manner_of_impact_description', 'weather_1_description', 'county_name'],
    'display_name': 'Delaware (DelDOT)',
    'config_dir': 'delaware'
}
Also add 'delaware_csv' variant with uppercase column names:
STATE_SIGNATURES['delaware_csv'] = {
    'required': ['CRASH DATETIME', 'CRASH CLASSIFICATION DESCRIPTION', 'LATITUDE', 'LONGITUDE'],
    'optional': ['MANNER OF IMPACT DESCRIPTION', 'WEATHER 1 DESCRIPTION', 'COUNTY NAME'],
    'display_name': 'Delaware (DelDOT CSV)',
    'config_dir': 'delaware'
}

2. Create DelawareNormalizer class extending BaseNormalizer:
   
   class DelawareNormalizer(BaseNormalizer):
       """Normalizes Delaware DSHS crash data to Virginia-standard format."""
       
       def __init__(self):
           # Column name mapping (lowercase Socrata API → standard)
           self._col_map = {
               'crash_datetime': 'CRASH DATETIME',
               'crash_classification_code': 'CRASH CLASSIFICATION CODE',
               'crash_classification_description': 'CRASH CLASSIFICATION DESCRIPTION',
               'manner_of_impact_code': 'MANNER OF IMPACT CODE',
               'manner_of_impact_description': 'MANNER OF IMPACT DESCRIPTION',
               'alcohol_involved': 'ALCOHOL INVOLVED',
               'drug_involved': 'DRUG INVOLVED',
               'road_surface_description': 'ROAD SURFACE DESCRIPTION',
               'lighting_condition_code': 'LIGHTING CONDITION CODE',
               'lighting_condition_description': 'LIGHTING CONDITION DESCRIPTION',
               'weather_1_description': 'WEATHER 1 DESCRIPTION',
               'seatbelt_used': 'SEATBELT USED',
               'motorcycle_involved': 'MOTORCYCLE INVOLVED',
               'bicycled_involved': 'BICYCLED INVOLVED',
               'pedestrian_involved': 'PEDESTRIAN INVOLVED',
               'latitude': 'LATITUDE',
               'longitude': 'LONGITUDE',
               'county_code': 'COUNTY CODE',
               'county_name': 'COUNTY NAME',
               'year': 'YEAR',
               'work_zone': 'WORK ZONE',
               'school_bus_involved_code': 'SCHOOL BUS INVOLVED CODE',
           }
           
           # Severity mapping (3-level → KABCO)
           self._severity_map = {
               '01': {'severity': 'K', 'K': 1, 'A': 0, 'B': 0, 'C': 0},
               '1':  {'severity': 'K', 'K': 1, 'A': 0, 'B': 0, 'C': 0},
               'Fatal': {'severity': 'K', 'K': 1, 'A': 0, 'B': 0, 'C': 0},
               '03': {'severity': 'B', 'K': 0, 'A': 0, 'B': 1, 'C': 0},
               '3':  {'severity': 'B', 'K': 0, 'A': 0, 'B': 1, 'C': 0},
               'Personal Injury': {'severity': 'B', 'K': 0, 'A': 0, 'B': 1, 'C': 0},
               '02': {'severity': 'O', 'K': 0, 'A': 0, 'B': 0, 'C': 0},
               '2':  {'severity': 'O', 'K': 0, 'A': 0, 'B': 0, 'C': 0},
               'Property Damage Only': {'severity': 'O', 'K': 0, 'A': 0, 'B': 0, 'C': 0},
           }
           
           # Collision type mapping (Manner of Impact → Virginia Collision Type)
           self._collision_map = {
               '01': '1. Rear End', 'Front to Rear': '1. Rear End',
               '02': '2. Angle', 'Angle': '2. Angle',
               '03': '3. Head On', 'Head On': '3. Head On', 'Front to Front': '3. Head On',
               '04': '4. Sideswipe - Same Direction', 'Sideswipe Same Direction': '4. Sideswipe - Same Direction',
               '05': '5. Sideswipe - Opposite Direction', 'Sideswipe Opposite Direction': '5. Sideswipe - Opposite Direction',
               '06': '8. Non-Collision', 'Non-Collision': '8. Non-Collision',
               '07': '16. Other', 'Rear to Side': '16. Other',
               '08': '16. Other', 'Rear to Rear': '16. Other',
               '09': '16. Other',
               '00': 'Not Applicable', '99': 'Not Provided',
               'Unknown': 'Not Provided', 'Other': '16. Other',
               'Not Applicable': 'Not Applicable',
           }
           
           # Weather mapping
           self._weather_map = {
               'Clear': '1. No Adverse Condition (Clear/Cloudy)',
               'Cloudy': '1. No Adverse Condition (Clear/Cloudy)',
               'Rain': '5. Rain', 'Snow': '6. Snow',
               'Sleet/Hail': '7. Sleet/Hail', 'Fog': '3. Fog',
               'Fog/Smog/Smoke': '3. Fog',
               'Blowing Sand/Soil/Dirt': '10. Blowing Sand, Soil, Dirt, or Snow',
               'Blowing Snow': '10. Blowing Sand, Soil, Dirt, or Snow',
               'Severe Crosswinds': '11. Severe Crosswinds',
               'Other': '9. Other', 'Unknown': 'Not Applicable',
           }
           
           # Light condition mapping
           self._light_map = {
               'Daylight': '2. Daylight', 'Dawn': '1. Dawn', 'Dusk': '3. Dusk',
               'Dark - Lighted': '4. Darkness - Road Lighted',
               'Dark-Lighted': '4. Darkness - Road Lighted',
               'Dark - Not Lighted': '5. Darkness - Road Not Lighted',
               'Dark-Not Lighted': '5. Darkness - Road Not Lighted',
               'Dark - Unknown Lighting': '6. Darkness - Unknown Road Lighting',
               'Dark-Unknown Lighting': '6. Darkness - Unknown Road Lighting',
               'Unknown': '7. Unknown', 'Other': '7. Unknown',
           }
           
           # Road surface mapping
           self._surface_map = {
               'Dry': '1. Dry', 'Wet': '2. Wet', 'Snow': '3. Snowy',
               'Ice': '4. Icy', 'Ice/Frost': '4. Icy',
               'Sand/Mud/Dirt/Oil/Gravel': '5. Muddy',
               'Water': '9. Water (Standing, Moving)', 'Slush': '10. Slush',
               'Other': '7. Other', 'Unknown': 'Not Provided',
           }
           
           # Jurisdiction mapping
           self._juris_map = {
               '1': (1, '001. Kent County'),
               '2': (2, '002. New Castle County'),
               '3': (3, '003. Sussex County'),
               'Kent': (1, '001. Kent County'),
               'New Castle': (2, '002. New Castle County'),
               'Sussex': (3, '003. Sussex County'),
           }
           
           self._row_counter = 0

       def _get_val(self, row, *keys):
           """Get value from row, trying multiple key variants."""
           for k in keys:
               if k in row and row[k] not in (None, '', 'nan'):
                   return str(row[k]).strip()
               lk = k.lower().replace(' ', '_')
               if lk in row and row[lk] not in (None, '', 'nan'):
                   return str(row[lk]).strip()
           return ''

       def _parse_datetime(self, dt_str):
           """Parse Delaware datetime → (crash_date_str, military_time_int, year_int)"""
           from datetime import datetime
           for fmt in ['%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S',
                       '%m/%d/%Y %I:%M:%S %p', '%m/%d/%Y %H:%M:%S',
                       '%m/%d/%Y %H:%M']:
               try:
                   dt = datetime.strptime(dt_str.strip(), fmt)
                   crash_date = f"{dt.month}/{dt.day}/{dt.year} 5:00:00 AM"
                   mil_time = dt.hour * 100 + dt.minute
                   return crash_date, mil_time, dt.year
               except ValueError:
                   continue
           return '1/1/2000 5:00:00 AM', 0, 2000

       def _yn_to_yesno(self, val):
           return 'Yes' if str(val).upper() in ('Y', 'YES', 'TRUE', '1') else 'No'

       def _yn_to_belt(self, val):
           return 'Belted' if str(val).upper() in ('Y', 'YES', 'TRUE', '1') else 'Unbelted'

       def _is_night(self, light_desc):
           desc = str(light_desc).lower()
           return 'Yes' if 'dark' in desc else 'No'

       def normalize_row(self, row):
           """Transform a single Delaware row to Virginia-standard format."""
           # Idempotency check: if already normalized, skip
           if 'Crash Severity' in row and row.get('Crash Severity', '') in ('K','A','B','C','O'):
               if 'Physical Juris Name' in row and '.' in str(row.get('Physical Juris Name', '')):
                   return row  # Already normalized
           
           self._row_counter += 1
           
           # Parse datetime
           dt_str = self._get_val(row, 'CRASH DATETIME', 'crash_datetime')
           crash_date, mil_time, year = self._parse_datetime(dt_str)
           year_val = self._get_val(row, 'YEAR', 'year') or str(year)
           
           # Severity
           sev_code = self._get_val(row, 'CRASH CLASSIFICATION CODE', 'crash_classification_code')
           sev_desc = self._get_val(row, 'CRASH CLASSIFICATION DESCRIPTION', 'crash_classification_description')
           sev_info = self._severity_map.get(sev_code, self._severity_map.get(sev_desc, 
                      {'severity': 'O', 'K': 0, 'A': 0, 'B': 0, 'C': 0}))
           
           # Collision type
           moi_code = self._get_val(row, 'MANNER OF IMPACT CODE', 'manner_of_impact_code')
           moi_desc = self._get_val(row, 'MANNER OF IMPACT DESCRIPTION', 'manner_of_impact_description')
           collision = self._collision_map.get(moi_code, self._collision_map.get(moi_desc, 'Not Provided'))
           
           # Weather
           weather_desc = self._get_val(row, 'WEATHER 1 DESCRIPTION', 'weather_1_description')
           weather = self._weather_map.get(weather_desc, 'Not Applicable')
           
           # Light
           light_desc = self._get_val(row, 'LIGHTING CONDITION DESCRIPTION', 'lighting_condition_description')
           light = self._light_map.get(light_desc, 'Not Applicable')
           
           # Surface
           surf_desc = self._get_val(row, 'ROAD SURFACE DESCRIPTION', 'road_surface_description')
           surface = self._surface_map.get(surf_desc, 'Not Applicable')
           
           # Jurisdiction
           county_code = self._get_val(row, 'COUNTY CODE', 'county_code')
           county_name = self._get_val(row, 'COUNTY NAME', 'county_name')
           juris_info = self._juris_map.get(county_code, self._juris_map.get(county_name, (0, '000. Unknown County')))
           
           # Work zone
           wz = self._get_val(row, 'WORK ZONE', 'work_zone')
           wz_mapped = '1. Yes' if wz.upper() in ('Y', 'YES') else '2. No' if wz.upper() in ('N', 'NO') else 'Not Provided'
           
           # Coordinates
           lat = self._get_val(row, 'LATITUDE', 'latitude')
           lon = self._get_val(row, 'LONGITUDE', 'longitude')
           
           out = {
               'OBJECTID': self._row_counter,
               'Document Nbr': f"DE-{year_val}-{self._row_counter:06d}",
               'Crash Year': int(year_val) if year_val.isdigit() else year,
               'Crash Date': crash_date,
               'Crash Military Time': mil_time,
               'Crash Severity': sev_info['severity'],
               'K_People': sev_info['K'],
               'A_People': sev_info['A'],
               'B_People': sev_info['B'],
               'C_People': sev_info['C'],
               'Persons Injured': sev_info['A'] + sev_info['B'] + sev_info['C'],
               'Pedestrians Killed': 0,
               'Pedestrians Injured': 0,
               'Vehicle Count': 0,
               'Collision Type': collision,
               'Weather Condition': weather,
               'Light Condition': light,
               'Roadway Surface Condition': surface,
               'Relation To Roadway': 'Not Provided',
               'Roadway Alignment': 'Not Applicable',
               'Roadway Surface Type': 'Not Applicable',
               'Roadway Defect': 'Not Applicable',
               'Roadway Description': 'Not Applicable',
               'Intersection Type': 'Not Provided',
               'Traffic Control Type': 'Not Applicable',
               'Traffic Control Status': 'Not Applicable',
               'Work Zone Related': wz_mapped,
               'Work Zone Location': '',
               'Work Zone Type': '',
               'School Zone': '3. No',
               'First Harmful Event': 'Not Provided',
               'First Harmful Event Loc': 'Not Provided',
               'Alcohol?': self._yn_to_yesno(self._get_val(row, 'ALCOHOL INVOLVED', 'alcohol_involved')),
               'Animal Related?': 'No',
               'Unrestrained?': self._yn_to_belt(self._get_val(row, 'SEATBELT USED', 'seatbelt_used')),
               'Bike?': self._yn_to_yesno(self._get_val(row, 'BICYCLED INVOLVED', 'bicycled_involved')),
               'Distracted?': 'No',
               'Drowsy?': 'No',
               'Drug Related?': self._yn_to_yesno(self._get_val(row, 'DRUG INVOLVED', 'drug_involved')),
               'Guardrail Related?': 'No',
               'Hitrun?': 'No',
               'Lgtruck?': 'No',
               'Motorcycle?': self._yn_to_yesno(self._get_val(row, 'MOTORCYCLE INVOLVED', 'motorcycle_involved')),
               'Pedestrian?': self._yn_to_yesno(self._get_val(row, 'PEDESTRIAN INVOLVED', 'pedestrian_involved')),
               'Speed?': 'No',
               'Max Speed Diff': '',
               'RoadDeparture Type': 'NOT_RD',
               'Intersection Analysis': 'Not Intersection',
               'Senior?': 'No',
               'Young?': 'No',
               'Mainline?': 'No',
               'Night?': self._is_night(light_desc),
               'VDOT District': 'DelDOT',
               'Juris Code': juris_info[0],
               'Physical Juris Name': juris_info[1],
               'Functional Class': '7-Local (J,6)',
               'Facility Type': '3-Two-Way Undivided',
               'Area Type': 'Urban',
               'SYSTEM': 'DelDOT Primary',
               'VSP': '',
               'Ownership': '1. State Hwy Agency',
               'Planning District': county_name if county_name else '',
               'MPO Name': '',
               'RTE Name': '',
               'RNS MP': '',
               'Node': '',
               'Node Offset (ft)': '',
               'x': float(lon) if lon else '',
               'y': float(lat) if lat else '',
               '_source_state': 'delaware',
               '_source_file': '',
           }
           
           # Preserve extra source columns
           for src_col in ['DAY OF WEEK CODE', 'DAY OF WEEK DESCRIPTION',
                           'CRASH CLASSIFICATION CODE', 'CRASH CLASSIFICATION DESCRIPTION',
                           'COLLISION ON PRIVATE PROPERTY', 'MANNER OF IMPACT CODE',
                           'MANNER OF IMPACT DESCRIPTION', 'MOTORCYCLE HELMET USED',
                           'BICYCLE HELMET USED', 'WEATHER 2 CODE', 'WEATHER 2 DESCRIPTION',
                           'PRIMARY CONTRIBUTING CIRCUMSTANCE CODE',
                           'PRIMARY CONTRIBUTING CIRCUMSTANCE DESCRIPTION',
                           'SCHOOL BUS INVOLVED CODE', 'SCHOOL BUS INVOLVED DESCRIPTION',
                           'WORKERS PRESENT', 'COUNTY CODE', 'COUNTY NAME']:
               val = self._get_val(row, src_col, src_col.lower().replace(' ', '_'))
               if val:
                   out[src_col] = val
           
           return out

3. Register in _NORMALIZERS:
   _NORMALIZERS['delaware'] = DelawareNormalizer
   _NORMALIZERS['delaware_csv'] = DelawareNormalizer

4. Create states/delaware/config.json (content below in §6 Prompt A Config section)

5. Create states/delaware/hierarchy.json (content below)
```

### Prompt A — Config Files

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
    "crash_classification_code": "Crash Severity",
    "latitude": "y",
    "longitude": "x",
    "county_code": "Juris Code",
    "county_name": "Physical Juris Name",
    "manner_of_impact_description": "Collision Type",
    "weather_1_description": "Weather Condition",
    "lighting_condition_description": "Light Condition",
    "road_surface_description": "Roadway Surface Condition"
  },
  "severityMapping": {
    "01": "K",
    "03": "B",
    "02": "O",
    "Fatal": "K",
    "Personal Injury": "B",
    "Property Damage Only": "O"
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
      "note": "WARNING: Delaware data has no Functional Class field. All records default to Local."
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
    "3-level severity (Fatal/Injury/PDO) mapped to K/B/O — no A/C granularity",
    "No Ownership column — County Roads and City Roads filters return zero results",
    "No Functional Class column — No Interstate filter is non-functional",
    "No RTE Name, Node, SYSTEM — road-level analysis not possible",
    "No Vehicle Count, Persons Injured counts",
    "No Document Number — composite IDs generated"
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
| 7 | Crash Severity values | Only K, B, O | Unique values of `Crash Severity` |
| 8 | No A or C severity | **0 records** with A or C (expected — 3-level system) | `Crash Severity in ('A', 'C')` |
| 9 | SYSTEM values | Only `"DelDOT Primary"` | Unique values of `SYSTEM` |
| 10 | Coordinates in bounds | All lat 38.45–39.84, lon -75.79 to -75.04 | Bounds check on x, y |
| 11 | Crash Date format | Matches `M/D/YYYY 5:00:00 AM` | Regex on `Crash Date` |
| 12 | Boolean flags | Only "Yes"/"No" (or "Belted"/"Unbelted") | Unique values per boolean column |
| 13 | Document Nbr format | Matches `DE-YYYY-NNNNNN` | Regex on `Document Nbr` |
| 14 | Night? consistency | "Yes" only when Light Condition contains "Darkness" | Cross-check Night? vs Light Condition |

### Expected Degradations (Document These for Users)
- County Roads Only filter: returns 0 results → **Expected** (no ownership data from DE)
- City Roads Only filter: returns 0 results → **Expected**
- No Interstate filter: returns ALL results → **Expected** (all default to Local)
- EPDO scores for injury crashes: approximate → **Expected** (no A/B/C granularity)
- Road-level analysis: not possible → **Expected** (no RTE Name/Node)

---

## Summary of Critical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Injury severity mapping | All → B | Middle-ground; most common injury level nationally |
| Missing Ownership | Default to "1. State Hwy Agency" | Allows All Roads to work; County/City acknowledged broken |
| Missing Functional Class | Default to "7-Local (J,6)" | Conservative; doesn't accidentally include as Interstate |
| Document Number | Composite `DE-YYYY-NNNNNN` | Deterministic, sortable, identifiable |
| Missing boolean flags | Default to "No" | Conservative; avoids false positives |
| Night? derivation | From Light Condition | Reliable signal from available data |
