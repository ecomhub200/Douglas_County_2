# Multi-State Migration Checklist

## Overview

This document provides a comprehensive checklist for migrating the CRASH LENS tool from Virginia to another state (e.g., Colorado). The codebase contains **141,000+ Virginia-specific references** across **107 files**.

---

## Migration Priority Levels

| Priority | Description | Impact |
|----------|-------------|--------|
| **P0 - Critical** | Tool won't function without these changes | Blocks all functionality |
| **P1 - High** | Core features broken without changes | Major features unusable |
| **P2 - Medium** | Features degraded but tool usable | Some features broken |
| **P3 - Low** | Cosmetic/documentation only | No functional impact |

---

## P0 - Critical Changes (Tool Won't Work Without)

### 1. Crash Data Column Mappings

**File:** `app/index.html` (COL constant definition)

**Current Virginia TREDS Column Names:**
```javascript
const COL = {
  ID: 'Document Nbr',           // Virginia DMV crash report number
  YEAR: 'Crash Year',
  DATE: 'Crash Date',
  TIME: 'Crash Military Time',
  SEVERITY: 'Crash Severity',   // K/A/B/C/O codes
  K: 'K_People', A: 'A_People', B: 'B_People', C: 'C_People',
  COLLISION: 'Collision Type',
  WEATHER: 'Weather Condition',
  LIGHT: 'Light Condition',
  SURFACE: 'Roadway Surface Condition',
  ROUTE: 'RTE Name',            // Virginia route format
  NODE: 'Node',                 // Virginia node ID system
  MP: 'RNS MP',                 // Virginia milepost reference
  JURISDICTION: 'Physical Juris Name',
  ROAD_SYSTEM: 'SYSTEM',        // DOT/Non-DOT
  LAT: 'LATITUDE',
  LON: 'LONGITUDE',
  // ... 40+ total columns
};
```

**Required Actions:**
- [ ] Obtain new state's crash data dictionary/schema
- [ ] Map each Virginia column to equivalent new state column
- [ ] Update all COL references throughout codebase
- [ ] Handle columns that don't exist in new state (graceful fallback)
- [ ] Add new columns specific to the target state

**Colorado Example (CDOT Crash Data):**
| Virginia Column | Colorado Equivalent |
|-----------------|---------------------|
| `Document Nbr` | `CRASH_ID` or `CASE_NUMBER` |
| `Crash Severity` | `INJURY_SEVERITY` |
| `RTE Name` | `ROUTE_NAME` or `HIGHWAY_NUMBER` |
| `Physical Juris Name` | `COUNTY_NAME` |

---

### 2. Jurisdiction Database

**File:** `config.json` (lines 70-3200+)

**Current:** 133 Virginia jurisdictions (95 counties + 38 cities)

**Required for Each Jurisdiction:**
```json
{
  "denver": {
    "name": "Denver County",
    "type": "county",
    "fips": "031",                    // Colorado FIPS
    "jurisCode": "1",                 // State-specific code
    "namePatterns": [                 // Match crash data values
      "DENVER",
      "Denver County",
      "031. Denver County"
    ],
    "mapCenter": [39.7392, -104.9903],  // Lat/Lon
    "mapZoom": 11,
    "maintainsOwnRoads": true,        // Local road maintenance
    "education": {
      "leaId": "0880000",             // Dept of Ed LEA ID
      "districtName": "Denver Public Schools"
    },
    "bbox": [-105.1098, 39.6144, -104.5996, 39.9142]  // Bounding box
  }
}
```

**Required Actions:**
- [ ] Create jurisdiction list for new state
- [ ] Obtain FIPS codes for each county/city
- [ ] Calculate bounding boxes for each jurisdiction
- [ ] Define map centers and zoom levels
- [ ] Identify name patterns matching crash data
- [ ] Research which jurisdictions maintain own roads
- [ ] Add education LEA IDs if school zone analysis needed

**Colorado Stats:**
- 64 counties
- ~272 incorporated municipalities
- Total jurisdictions to configure: varies by implementation scope

---

### 3. State FIPS Code

**File:** `config.json` (line 36)

```json
"stateFips": "51"  // Virginia = 51
```

**State FIPS Codes:**
| State | FIPS |
|-------|------|
| Virginia | 51 |
| Colorado | 08 |
| Texas | 48 |
| California | 06 |
| Florida | 12 |

**Required Actions:**
- [ ] Update `stateFips` in config.json
- [ ] Verify TigerWeb API works with new FIPS
- [ ] Test county subdivision queries

---

### 4. Crash Data API/Source

**File:** `config.json` (lines 3287-3302)

**Current Virginia Roads API:**
```json
"dataSource": {
  "name": "Virginia Roads",
  "url": "https://www.virginiaroads.org",
  "apiUrl": "https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/CrashData_Basic_Updated/FeatureServer/0/query",
  "fallbackUrl": "https://www.virginiaroads.org/api/download/...",
  "datasetId": "1a96a2f31b4f4d77991471b6cabb38ba"
}
```

**Required Actions:**
- [ ] Identify new state's crash data portal
- [ ] Obtain API endpoints (if available)
- [ ] Document authentication requirements
- [ ] Test API rate limits
- [ ] Update all endpoint URLs
- [ ] Create fallback data source

**Common State Data Sources:**
| State | Data Source |
|-------|-------------|
| Colorado | CDOT Open Data Portal, CRIS |
| Texas | CRIS (Crash Records Information System) |
| California | SWITRS (Statewide Integrated Traffic Records System) |
| Florida | Signal Four Analytics |

---

### 5. Severity & Crash Type Codes

**File:** `validation/reference/virginia_valid_values.json`

**Virginia KABCO System:**
```json
{
  "severity": {
    "K": "Fatal Injury",
    "A": "Serious Injury (Incapacitating)",
    "B": "Minor Injury (Non-Incapacitating)",
    "C": "Possible Injury",
    "O": "Property Damage Only"
  },
  "epdoWeights": {
    "K": 883, "A": 94, "B": 21, "C": 11, "O": 1
  }
}
```

**Required Actions:**
- [ ] Verify new state uses KABCO (most do, federally required)
- [ ] Check if EPDO weights differ by state policy
- [ ] Update collision type codes (Virginia has 16 types)
- [ ] Update weather condition codes
- [ ] Update light condition codes
- [ ] Update surface condition codes
- [ ] Update intersection type codes
- [ ] Update traffic control codes

**Note:** While KABCO is federally standardized, collision types and other codes vary significantly by state.

---

### 6. Road System Classifications

**File:** `config.json` (lines 3242-3285)

**Virginia System:**
```json
"roadSystems": {
  "Non-DOT secondary": { "includeInCountyFilter": true },
  "Non-DOT": { "includeInCountyFilter": true },
  "Primary": { "isVDOT": true },
  "Secondary": { "isVDOT": true },
  "Interstate": { "isInterstate": true }
}
```

**Required Actions:**
- [ ] Identify new state's road classification system
- [ ] Map Virginia classifications to new state equivalents
- [ ] Update filter profiles:
  - [ ] `countyOnly` - Local roads only
  - [ ] `countyPlusVDOT` - Local + state roads (no interstate)
  - [ ] `allRoads` - All road types
- [ ] Update UI labels (change "VDOT" to "CDOT" etc.)

**Colorado Example:**
| Virginia | Colorado Equivalent |
|----------|---------------------|
| DOT Primary | CDOT State Highway |
| DOT Secondary | CDOT Secondary |
| Non-DOT | Local/County Roads |
| Interstate | Interstate (same) |

---

## P1 - High Priority Changes (Core Features)

### 7. Python Data Download Scripts

**Files:**
- `download_crash_data.py`
- `download_grants_data.py`
- `download_cmf_data.py`

**Required Actions:**
- [ ] Rewrite API connection code for new data source
- [ ] Update column mapping transformations
- [ ] Update road system filtering logic
- [ ] Update jurisdiction filtering
- [ ] Update authentication (if required)
- [ ] Update error handling for new API responses
- [ ] Test data format compatibility

---

### 8. Linear Referencing System (LRS)

**File:** `validation/utils/vdot_lrs_client.py` (460+ lines)

**Virginia LRS Features:**
- Route name patterns: `"R-VA US00250WB"`, `"S-VA043NP NUCKOLS RD"`
- VDOT LRS API endpoints
- Milepost-to-coordinate interpolation

**Required Actions:**
- [ ] Research new state's LRS availability
- [ ] Obtain LRS API endpoints (if available)
- [ ] Update route name parsing patterns
- [ ] Update coordinate interpolation logic
- [ ] Create fallback if no LRS available
- [ ] Rename file from `vdot_lrs_client.py` to generic name

**Note:** Not all states have publicly accessible LRS APIs. May need to rely on lat/lon coordinates only.

---

### 9. Data Validation Rules

**Files:**
- `validation/reference/virginia_valid_values.json`
- `validation/reference/correction_rules.json`
- `validation/core/validator.py`
- `validation/corrections/corrector.py`

**Required Actions:**
- [ ] Create new state's valid values file
- [ ] Update correction rules for common data errors
- [ ] Update validation logic for state-specific fields
- [ ] Test validation against sample data
- [ ] Update error messages with state-specific context

---

### 10. Geographic Boundaries

**Files:** Multiple locations

**Current Virginia Bounds:**
```
Latitude: 36.5° to 39.5°N
Longitude: 75.2° to 83.7°W
```

**Required Actions:**
- [ ] Update coordinate validation bounds
- [ ] Update all jurisdiction bounding boxes
- [ ] Update default map center
- [ ] Update TigerWeb census layer queries
- [ ] Test boundary polygon loading

**Colorado Bounds:**
```
Latitude: ~37° to 41°N
Longitude: ~102° to 109°W
```

---

### 11. MUTCD & Warrant Analysis

**Files:** `app/index.html` (signal warrant analysis section)

**Virginia MUTCD References:**
- "Virginia MUTCD 11.0"
- "Virginia MUTCD Figures 4C-5 through 4C-8"
- "Virginia MUTCD Section 2B.07"

**Required Actions:**
- [ ] Research new state's MUTCD adoption status
- [ ] Identify state-specific supplements (if any)
- [ ] Update warrant threshold references
- [ ] Update figure/section citations
- [ ] Test warrant calculations match state standards

**Note:** Most states adopt federal MUTCD with state-specific supplements. Colorado uses standard MUTCD with minimal modifications.

---

### 12. Grant Programs

**File:** `app/index.html` (grants tab)

**Virginia Grant References:**
- Virginia DMV - VAHSO
- Virginia-specific HSIP allocations

**Required Actions:**
- [ ] Research new state's traffic safety grants
- [ ] Update CFDA numbers for state programs
- [ ] Update agency contacts
- [ ] Update eligibility criteria
- [ ] Update funding amounts/cycles
- [ ] Update application deadlines

**Federal Programs (Same Across States):**
- HSIP (Highway Safety Improvement Program)
- SS4A (Safe Streets for All)
- NHTSA 402

**Colorado-Specific:**
- CDOT Traffic Safety Programs
- FASTER (Funding Advancements for Surface Transportation)

---

## P2 - Medium Priority Changes (Features)

### 13. Administrative Subdivisions

**Current:** Virginia Magisterial Districts

**Required Actions:**
- [ ] Research new state's administrative subdivisions
- [ ] Update or remove magisterial district feature
- [ ] Update filter options in UI
- [ ] Update GeoJSON loading logic

**Note:** Not all states use magisterial districts. Colorado uses:
- County subdivisions
- Census Designated Places (CDPs)
- Unincorporated areas

---

### 14. Transit Data Integration

**File:** `app/index.html`, `config.json`

**Current:** Virginia DRPT transit stops

**Required Actions:**
- [ ] Identify new state's transit authority
- [ ] Obtain GTFS feed URLs
- [ ] Update API endpoints
- [ ] Update UI labels

**Colorado Transit:**
- RTD (Regional Transportation District) - Denver metro
- Mountain Metro - Colorado Springs
- Transfort - Fort Collins

---

### 15. CMF Data Processing

**File:** `download_cmf_data.py`

**Required Actions:**
- [ ] Update crash type mapping for new state codes
- [ ] Update relevance scoring algorithm
- [ ] Verify CMF Clearinghouse compatibility
- [ ] Test countermeasure recommendations

---

### 16. Route Name Parsing

**Files:** Multiple parsing functions

**Virginia Route Patterns:**
```
I-64, I-95, I-295, I-85, I-81, I-77, I-66, I-664
US-1, US-29, US-250, US-460
VA-7, VA-123, VA-28
```

**Required Actions:**
- [ ] Update interstate patterns for new state
- [ ] Update US route patterns
- [ ] Update state route patterns
- [ ] Update local road naming conventions

**Colorado Route Patterns:**
```
I-25, I-70, I-76, I-225, I-270
US-6, US-24, US-36, US-40, US-50, US-85, US-287
CO-2, CO-7, CO-58, CO-93, CO-119
```

---

## P3 - Low Priority Changes (Documentation/Cosmetic)

### 17. Application Branding

**Files:** `index.html`, `config.json`, `manifest.json`

**Required Actions:**
- [ ] Update app subtitle: "Virginia Crash Analysis Tool" → "[State] Crash Analysis Tool"
- [ ] Update meta tags and keywords
- [ ] Update Open Graph descriptions
- [ ] Update manifest.json app name

---

### 18. UI Text & Labels

**Files:** Throughout `app/index.html`

**Search & Replace:**
| Find | Replace |
|------|---------|
| "Virginia" | "[New State]" |
| "VDOT" | "[State DOT]" |
| "Virginia Roads" | "[State Data Portal]" |
| "TREDS" | "[State System Name]" |
| "Virginia DMV" | "[State DMV]" |

**Required Actions:**
- [ ] Search for all Virginia references in HTML
- [ ] Update placeholders and help text
- [ ] Update error messages
- [ ] Update loading messages
- [ ] Update report headers/footers

---

### 19. Case Studies & Examples

**Files:** Marketing pages, documentation

**Virginia Examples:**
- Henrico County DPW
- City of Richmond DPW
- VDOT Salem District
- $2.4M HSIP funding references

**Required Actions:**
- [ ] Remove or replace Virginia agency case studies
- [ ] Add new state agency examples (if available)
- [ ] Update funding/project examples
- [ ] Update agency testimonials

---

### 20. Documentation Updates

**Files:** `docs/` directory, `README.md`, `CLAUDE.md`

**Required Actions:**
- [ ] Update README.md state references
- [ ] Update ARCHITECTURE.md technical docs
- [ ] Update all implementation plan documents
- [ ] Update CLAUDE.md instructions
- [ ] Create state-specific data dictionary
- [ ] Update contact information

---

## File-by-File Change Summary

### Critical Files (Must Change)

| File | Changes Required | Effort |
|------|-----------------|--------|
| `config.json` | Jurisdiction database, FIPS, APIs | High |
| `app/index.html` | Column mappings, UI text, validation | High |
| `download_crash_data.py` | API endpoints, data transformations | High |
| `validation/reference/virginia_valid_values.json` | All valid value lists | Medium |
| `validation/utils/vdot_lrs_client.py` | Complete rewrite | High |

### Important Files (Should Change)

| File | Changes Required | Effort |
|------|-----------------|--------|
| `download_grants_data.py` | Grant program updates | Medium |
| `download_cmf_data.py` | Crash type mappings | Low |
| `validation/reference/correction_rules.json` | Data correction rules | Medium |
| `validation/core/validator.py` | Validation logic | Low |

### Documentation Files (Nice to Change)

| File | Changes Required | Effort |
|------|-----------------|--------|
| `README.md` | State references | Low |
| `CLAUDE.md` | State-specific instructions | Low |
| `docs/ARCHITECTURE.md` | Technical documentation | Low |
| `docs/*.md` | All documentation files | Medium |

---

## Data Requirements from New State

Before starting migration, obtain:

1. **Crash Data Schema/Dictionary**
   - All field names and data types
   - Valid values for coded fields
   - Sample data files

2. **Geographic Data**
   - County/jurisdiction list with FIPS codes
   - Bounding boxes or shapefiles
   - LRS information (if available)

3. **Agency Information**
   - State DOT name and abbreviations
   - Data portal URLs and API documentation
   - Contact for data questions

4. **Regulatory Information**
   - MUTCD adoption status
   - State-specific supplements
   - Grant program details

5. **Road Classification System**
   - How roads are categorized
   - Maintenance responsibility rules
   - Route naming conventions

---

## Estimated Effort by State

| State | Data Availability | LRS | Estimated Effort |
|-------|-------------------|-----|------------------|
| Colorado | Good (CDOT Open Data) | Limited | Medium |
| Texas | Excellent (CRIS) | Good | Medium |
| California | Good (SWITRS) | Good | Medium |
| Florida | Excellent (Signal Four) | Good | Low-Medium |
| Ohio | Good | Good | Medium |

---

## Testing Checklist

After migration:

- [ ] Data loads correctly from new source
- [ ] All jurisdictions appear in dropdown
- [ ] Map centers on correct state
- [ ] Crash counts aggregate correctly
- [ ] Severity distribution calculates properly
- [ ] CMF recommendations work
- [ ] Warrant analysis produces valid results
- [ ] Grant information is accurate
- [ ] All tabs function without errors
- [ ] No Virginia references remain in UI
- [ ] Coordinate validation works for new state
- [ ] Report generation includes correct state name

---

## Multi-State Architecture (Future)

For supporting multiple states simultaneously:

```javascript
// Proposed state-agnostic architecture
const STATE_CONFIG = {
  current: 'CO',  // Currently selected state
  available: ['VA', 'CO', 'TX'],

  getConfig: (stateCode) => {
    return stateConfigs[stateCode];
  },

  getColumnMapping: (stateCode) => {
    return columnMappings[stateCode];
  }
};
```

Consider:
- [ ] State selector in UI
- [ ] Separate config files per state
- [ ] Dynamic column mapping
- [ ] State-specific validation rules
- [ ] Modular jurisdiction databases

---

## Contact & Resources

### State DOT Data Portals

| State | Portal URL |
|-------|------------|
| Virginia | https://www.virginiaroads.org |
| Colorado | https://data.colorado.gov (CDOT) |
| Texas | https://cris.dot.state.tx.us |
| California | https://iswitrs.chp.ca.gov |
| Florida | https://signal4analytics.com |

### FHWA Resources
- CMF Clearinghouse: https://www.cmfclearinghouse.org
- HSIP Manual: https://safety.fhwa.dot.gov/hsip
- MUTCD: https://mutcd.fhwa.dot.gov

---

## APPENDIX A: Exact Virginia ↔ Colorado Column Mapping

### Direct Column Mappings

| Internal Field | Virginia Column | Colorado Column | Notes |
|---------------|-----------------|-----------------|-------|
| ID | `Document Nbr` | `CUID` | Crash identifier |
| YEAR | `Crash Year` | *(derived from Crash Date)* | CO: extract year from M/D/YYYY |
| DATE | `Crash Date` | `Crash Date` | Different format: VA=varies, CO=M/D/YYYY |
| TIME | `Crash Military Time` | `Crash Time` | CO: HH:MM:SS → strip colons |
| SEVERITY | `Crash Severity` | *(derived from Injury 00-04)* | **CO has NO severity column** |
| K count | `K_People` | `Injury 04` | Persons killed |
| A count | `A_People` | `Injury 03` | Suspected serious injury |
| B count | `B_People` | `Injury 02` | Suspected minor injury |
| C count | `C_People` | `Injury 01` | Possible injury |
| COLLISION | `Collision Type` | `Crash Type` / `MHE` | CO: text values, needs mapping |
| WEATHER | `Weather Condition` | `Weather Condition` | Same field name, similar values |
| LIGHT | `Light Condition` | `Lighting Conditions` | Different column name |
| SURFACE | `Roadway Surface Condition` | `Road Condition` | Different column name |
| ROAD_DESC | `Roadway Description` | `Road Description` | CO has more categories |
| ROUTE | `RTE Name` | *(built from System Code + Rd_Number + Location 1)* | CO: multiple fields combined |
| NODE | `Node` | *(built from Location 1 + Location 2)* | CO: no numeric node system |
| MP | `RNS MP` | `Rd_Section` | Only for state highways |
| LAT | `y` | `Latitude` | |
| LON | `x` | `Longitude` | |
| JURISDICTION | `Physical Juris Name` | `County` | |
| ROAD_SYSTEM | `SYSTEM` | `System Code` | Different classification names |
| WORKZONE | `Work Zone Related` | `Construction Zone` | CO: TRUE/FALSE |
| SCHOOL | `School Zone` | `School Zone` | CO: TRUE/FALSE |
| FIRST_HARMFUL | `First Harmful Event` | `First HE` | |

### Derived Boolean Flags (Virginia has directly, Colorado must compute)

| Flag | Virginia Column | Colorado Derivation |
|------|----------------|---------------------|
| Pedestrian? | `Pedestrian?` (Y/N) | `TU-1 NM Type` or `TU-2 NM Type` contains "Pedestrian" |
| Bike? | `Bike?` (Y/N) | `TU-1 NM Type` or `TU-2 NM Type` contains "Bicycle" |
| Alcohol? | `Alcohol?` (Y/N) | `TU-1/2 Alcohol Suspected` = "Yes - SFST/BAC/Both/Observation" |
| Speed? | `Speed?` (Y/N) | `TU-1/2 Driver Action` = "Too Fast for Conditions" or "Exceeded Speed Limit" |
| Hitrun? | `Hitrun?` (Y/N) | `TU-1/2 Hit And Run` = "TRUE" |
| Motorcycle? | `Motorcycle?` (Y/N) | `TU-1/2 Type` = "Motorcycle" |
| Night? | `Night?` (Y/N) | `Lighting Conditions` starts with "Dark" |
| Distracted? | `Distracted?` (Y/N) | `TU-1/2 Driver Action` or `Human Contributing Factor` contains distraction keywords |
| Drowsy? | `Drowsy?` (Y/N) | `TU-1/2 Human Contributing Factor` contains "Asleep/Fatigued" |
| Drug? | `Drug Related?` (Y/N) | `TU-1/2 Marijuana Suspected` or `Other Drugs Suspected` = positive |
| Young? | `Young?` (Y/N) | `TU-1/2 Age` between 16-20 |
| Senior? | `Senior?` (Y/N) | `TU-1/2 Age` ≥ 65 |
| Unrestrained? | `Unrestrained?` (Y/N) | `TU-1/2 Safety restraint Use` = "Not Used" or "Improperly Used" |

### Road System Mapping

| Virginia Value | Colorado Value | Filter Category |
|---------------|----------------|-----------------|
| Non-DOT secondary | City Street | Local (countyOnly) |
| Non-DOT | County Road | Local (countyOnly) |
| Primary | State Highway | State (countyPlusState) |
| Secondary | Frontage Road | State (countyPlusState) |
| Interstate | Interstate Highway | Interstate (allRoads) |

### Collision Type Mapping

| Colorado Crash Type / MHE | Mapped To (Virginia Standard) |
|--------------------------|-------------------------------|
| Rear-End | Rear End |
| Broadside | Angle |
| Approach Turn | Angle |
| Overtaking Turn | Angle |
| Head-On | Head On |
| Sideswipe Same Direction | Sideswipe - Same Direction |
| Sideswipe Opposite Direction | Sideswipe - Opposite Direction |
| Pedestrian | Pedestrian |
| Bicycle/Motorized Bicycle | Bicyclist |
| Wild Animal | Other Animal |
| Overturning/Rollover | Non-Collision |
| Light Pole/Utility Pole | Fixed Object - Off Road |
| Concrete Highway Barrier | Fixed Object - Off Road |
| Guardrail Face/End | Fixed Object - Off Road |
| Tree, Fence, Sign, Curb, Embankment, Ditch | Fixed Object - Off Road |
| Vehicle Debris or Cargo | Fixed Object in Road |
| Parked Motor Vehicle | Other |

### Fields Only in Colorado (Extra Data)

| Colorado Column | Description | Not in Virginia |
|----------------|-------------|-----------------|
| `Agency Id` | Reporting police agency (e.g., DCSO, CSP) | ✓ |
| `City` | City where crash occurred | ✓ |
| `MHE` | Most Harmful Event | ✓ |
| `Approach Overtaking Turn` | Turn type detail | ✓ |
| `Wild Animal` | Animal type for animal crashes | ✓ |
| `Number Killed` | Total persons killed | ✓ |
| `Number Injured` | Total persons injured | ✓ |
| `Secondary Crash` | Related to previous incident | ✓ |
| `TU-1/2 Autonomous Vehicle` | Autonomous vehicle capability | ✓ |
| `TU-1/2 Marijuana Suspected` | Marijuana impairment (CO-specific) | ✓ |
| `TU-1/2 Estimated Speed` | Officer estimated speed | ✓ |
| `TU-1/2 Speed` | Driver stated speed | ✓ |
| `Road Contour Curves` | Curve direction detail | ✓ |
| `Road Contour Grade` | Grade detail | ✓ |

### Fields Only in Virginia (Not in Colorado)

| Virginia Column | Description | Not in Colorado |
|----------------|-------------|-----------------|
| `Functional Class` | Federal functional classification | ✓ |
| `Area Type` | Urban/Rural classification | ✓ |
| `Facility Type` | Road facility type | ✓ |
| `Ownership` | Road ownership | ✓ |
| `Node Offset` | Distance from node | ✓ |
| `Traffic Control Type` | Signal, stop sign, etc. | ✓ |
| `Traffic Control Status` | Functioning, not functioning | ✓ |
| `Guardrail Related?` | Guardrail involvement | ✓ |
| `RoadDeparture Type` | Road departure classification | ✓ |
| `Max Speed Diff` | Speed differential | ✓ |
| `Roadway Defect` | Road defect type | ✓ |
| `Relation To Roadway` | On/off roadway | ✓ |

---

## APPENDIX B: Multi-State Adapter Architecture

The `states/state_adapter.js` module handles all normalization automatically:

```
states/
├── state_adapter.js              ← Auto-detect + normalize (include in HTML)
├── INTEGRATION_GUIDE.md          ← Step-by-step integration instructions
├── colorado/
│   ├── config.json               ← Column mappings, road systems, valid values
│   └── jurisdictions.json        ← Douglas County + 5 neighboring counties
└── virginia/
    └── config.json               ← Reference config (existing state)
```

### How It Works

1. User uploads a CSV (any supported state)
2. `StateAdapter.detect(headers)` examines column names
3. If Colorado: `StateAdapter.normalizeRow(row)` transforms each row
4. Normalized data has Virginia-compatible column names
5. All existing analysis logic works unchanged

### Adding a New State

1. Get a sample crash CSV
2. Create `states/{state}/config.json`
3. Add detection signature in `state_adapter.js`
4. Add normalizer function in `state_adapter.js`
5. Create `states/{state}/jurisdictions.json`

---

*Document Version: 2.0*
*Created: February 2026*
*Last Updated: February 2026*
