# Multi-State Crash Database Research

**Date:** January 24, 2026
**Purpose:** Evaluate public crash databases for Maryland, Kentucky, and Michigan for potential integration with the Virginia Crash Analysis Tool

---

## Executive Summary

| State | Primary System | Public API | Data Format | Integration Feasibility |
|-------|---------------|------------|-------------|------------------------|
| **Maryland** | Open Data Portal (Socrata) | ✅ Yes | JSON, CSV, XML | **High** - Ready for integration |
| **Kentucky** | KYOPS | ❌ No | Web portal only | **Low** - Requires data agreement |
| **Michigan** | MTCF | ❌ No | Web export only | **Low** - Requires data agreement |

---

## 1. Maryland

### Data Sources

- **Maryland Open Data Portal** - https://opendata.maryland.gov/
  - Powered by Socrata platform
  - Full public access with API

- **Maryland Statewide Vehicle Crashes** - https://opendata.maryland.gov/Public-Safety/Maryland-Statewide-Vehicle-Crashes/65du-s3qu
  - Primary crash dataset
  - Includes pedestrian details, vehicle info

- **MDTA Accidents** - https://dev.socrata.com/foundry/opendata.maryland.gov/rqid-652u
  - Maryland Transportation Authority data

- **Zero Deaths MD** - https://zerodeathsmd.gov/resources/crashdata/
  - Crash and fatality visualization
  - Data derived from SHA's TANG database

### API Details

**Socrata Open Data API (SODA):**
- RESTful endpoints
- Output formats: JSON, CSV, XML, GeoJSON
- Query language: SoQL (SQL-like)
- No authentication required for public datasets
- Rate limits apply (typically 1000 requests/hour without app token)

**Example API Calls:**

```bash
# Get all crashes as JSON
curl "https://opendata.maryland.gov/resource/65du-s3qu.json"

# Get crashes as CSV with pagination
curl "https://opendata.maryland.gov/resource/65du-s3qu.csv?\$limit=5000&\$offset=0"

# Filter by county
curl "https://opendata.maryland.gov/resource/65du-s3qu.json?county_name=Montgomery"

# Filter by date range
curl "https://opendata.maryland.gov/resource/65du-s3qu.json?\$where=crash_date>='2023-01-01'"

# Complex query with multiple conditions
curl "https://opendata.maryland.gov/resource/65du-s3qu.json?\$where=county_name='Montgomery' AND injury_severity='FATAL'"
```

**Available Fields (partial list):**
- `crash_date`, `crash_time`
- `county_name`, `municipality`
- `latitude`, `longitude`
- `injury_severity`
- `collision_type`
- `weather`, `light`, `road_condition`
- `vehicle_count`, `person_count`

### County-Level Data

Montgomery County also provides enhanced local data:
- **Crash Reporting - Drivers Data** - https://data.montgomerycountymd.gov/Public-Safety/Crash-Reporting-Drivers-Data/mmzv-x632
- Weekly updates
- Vision Zero integration

### Integration Recommendation

**Priority: HIGH**

Maryland is the best candidate for immediate integration due to:
1. Full public API access
2. Similar data structure to Virginia
3. No authentication barriers
4. Geographic proximity

---

## 2. Kentucky

### Data Sources

- **KYOPS (Kentucky Open Portal System)** - https://kyops.ky.gov/
  - Maintained by Kentucky State Police
  - Primary repository for traffic collision data
  - Law enforcement access required for full functionality

- **Crash Information Kentucky** - http://crashinformationky.org/
  - Public-facing analysis interface
  - Limited query capabilities

- **KYTC Highway Safety Resources** - https://transportation.ky.gov/HighwaySafety/Pages/Resources.aspx
  - Statistical reports
  - Annual summaries

- **Kentucky Transportation Center (KTC)** - https://ktc.uky.edu/traffic-safety-page/
  - Crash Data Analysis Tool (CDAT)
  - Academic research access

### API Details

**No public API available.**

Access methods:
1. **Web Query Tool** at crashinformationky.org
   - Interactive mapping
   - Limited export functionality

2. **Data Requests**
   - Kentucky State Police Records Section: 502-227-8700
   - Kentucky Office of Highway Safety: 502-564-1438
   - Email requests may be required

3. **CDAT (Crash Data Analysis Tool)**
   - Developed by KTC for KYTC
   - Professional use only
   - Static annual snapshots

### Data Characteristics

- KYOPS includes latitude/longitude since 2000
- County, Route, and Milepoint (CRMP) data available
- Traffic Records Strategic Plan 2022-2026 active

### Integration Recommendation

**Priority: LOW**

Kentucky would require:
1. Formal data sharing agreement with Kentucky State Police
2. Manual data download and processing
3. Regular manual updates

---

## 3. Michigan

### Data Sources

- **Michigan Traffic Crash Facts (MTCF)** - https://www.michigantrafficcrashfacts.org/
  - Primary public interface
  - Operated by UMTRI (University of Michigan Transportation Research Institute)

- **MTCF Data Query Tool** - https://www.michigantrafficcrashfacts.org/querytool/map
  - Interactive maps, charts, tables
  - Export to various formats

- **Michigan State Police OHSP** - https://www.michigan.gov/msp/divisions/ohsp/traffic-crash-data
  - Official source
  - Annual reports

- **CMISST** - https://www.cmisst.org/tools-resources/database-resources/
  - Center for Management of Information for Safe and Sustainable Transportation
  - Some bulk data access

### API Details

**No public API available.**

Access methods:
1. **Data Query Tool**
   - Export charts, tables, lists
   - Limited bulk download
   - Years available: 2004-2024

2. **Police Report Downloads**
   - Individual crash reports available
   - Not suitable for bulk analysis

3. **Data Requests**
   - Traffic Crash Reporting Unit: 517-241-1699
   - Email: CrashTCRS@michigan.gov

### Data Characteristics

- UD-10 Traffic Crash Report format
- Comprehensive field coverage
- Historical data back to 1952 (publications)

### Integration Recommendation

**Priority: LOW**

Michigan would require:
1. Contact with MSP Traffic Crash Reporting Unit
2. Manual data export and processing
3. Potentially formal data agreement

---

## 4. Supplemental: NHTSA FARS API

The **NHTSA Crash API** provides fatal crash data for all 50 states.

**URL:** https://crashviewer.nhtsa.dot.gov/CrashAPI

### Features

- Covers all states
- FARS (Fatality Analysis Reporting System) data
- Data from 2010 onwards
- Multiple output formats: JSON, CSV, XML

### API Endpoints

```bash
# Get case list by state(s)
# State codes: MD=24, KY=21, MI=26, VA=51
/crashes/GetCaseList?states=24&fromYear=2020&toYear=2024&format=json

# Get crashes by location (state/county)
/crashes/GetCrashesByLocation?state=24&county=1&fromCaseYear=2020&toCaseYear=2024&format=json

# Get FARS dataset
/FARSData/GetFARSData?dataset=Accident&FromYear=2020&ToYear=2024&State=24&format=csv

# Get crashes by person characteristics
/crashes/GetCrashesByPerson?age=30&sex=2&state=24&fromCaseYear=2020&toCaseYear=2024&format=json
```

### Limitations

- **Fatal crashes only** (K severity)
- Does not include injury-only crashes (A, B, C) or PDO (O)
- Limited to ~5000 records per query

### Integration Recommendation

**Priority: MEDIUM**

Useful as supplemental data source for any state, but cannot replace full crash databases.

---

## Implementation Recommendations

### Phase 1: Maryland Integration

1. **Create `download_maryland_crash_data.py`**
   - Socrata API client
   - County filtering
   - Column mapping to Virginia format

2. **Update `config.json`**
   - Add Maryland state configuration
   - Define county jurisdictions
   - Add column mappings

3. **Modify `index.html`**
   - Add state selector
   - Handle different column names
   - Adjust aggregation logic

### Phase 2: Static Data Support

1. **Create data ingestion pipeline for manual CSVs**
   - `data/{state}/crashes.csv` structure
   - Column mapping templates
   - Validation scripts

2. **Add Kentucky/Michigan as static data states**
   - Document manual download process
   - Provide column mapping

### Phase 3: NHTSA FARS Integration

1. **Add FARS API support**
   - Fatal crash overlay for any state
   - Standardized data format

### Proposed Config Structure

```json
{
  "activeState": "virginia",
  "states": {
    "virginia": {
      "name": "Virginia",
      "fipsCode": "51",
      "dataSource": {
        "type": "arcgis",
        "apiUrl": "https://services.arcgis.com/p5v98VHDX9Atv3l7/...",
        "fallbackUrl": "https://www.virginiaroads.org/api/download/..."
      },
      "jurisdictions": { /* existing structure */ }
    },
    "maryland": {
      "name": "Maryland",
      "fipsCode": "24",
      "dataSource": {
        "type": "socrata",
        "apiUrl": "https://opendata.maryland.gov/resource/65du-s3qu.json",
        "apiKey": null,
        "rateLimit": 1000
      },
      "columnMapping": {
        "crashDate": "crash_date",
        "crashTime": "crash_time",
        "severity": "injury_severity",
        "latitude": "latitude",
        "longitude": "longitude",
        "county": "county_name",
        "collisionType": "collision_type",
        "weather": "weather",
        "light": "light",
        "roadCondition": "road_condition"
      },
      "jurisdictions": {
        "montgomery": {
          "name": "Montgomery County",
          "filter": "county_name='Montgomery'"
        },
        "baltimore_county": {
          "name": "Baltimore County",
          "filter": "county_name='Baltimore'"
        },
        "prince_georges": {
          "name": "Prince George's County",
          "filter": "county_name='Prince George\\'s'"
        }
      }
    },
    "kentucky": {
      "name": "Kentucky",
      "fipsCode": "21",
      "dataSource": {
        "type": "static",
        "localPath": "data/kentucky/crashes.csv",
        "downloadInstructions": "Contact KSP at 502-227-8700"
      }
    },
    "michigan": {
      "name": "Michigan",
      "fipsCode": "26",
      "dataSource": {
        "type": "static",
        "localPath": "data/michigan/crashes.csv",
        "downloadInstructions": "Export from MTCF query tool or contact MSP"
      }
    }
  }
}
```

---

## Column Mapping Reference

| Virginia Field | Maryland | Kentucky (est.) | Michigan (est.) |
|---------------|----------|-----------------|-----------------|
| Crash Date | crash_date | COLLISIONDATE | CRASHDATE |
| Crash Severity | injury_severity | SEVERITY | INJSEVER |
| Collision Type | collision_type | COLLISIONTYPE | TYPECOLL |
| Weather Condition | weather | WEATHER | WEATHER |
| Light Condition | light | LIGHT | LIGHTCOND |
| Road Surface | road_condition | ROADSURFACE | RDSURF |
| RTE Name | route_name | ROUTEID | ROADNAME |
| Latitude | latitude | LATITUDE | LATITUDE |
| Longitude | longitude | LONGITUDE | LONGITUDE |
| County | county_name | COUNTY | COUNTY |
| Pedestrian? | ped_visible | PED_FLAG | PEDCRASH |
| Bicycle? | bike_visible | BIKE_FLAG | BIKECRASH |

---

## Contact Information

### Maryland
- Open Data Portal: https://opendata.maryland.gov/
- Socrata Support: dev.socrata.com

### Kentucky
- KSP Records Section: 502-227-8700
- Office of Highway Safety: 502-564-1438
- KTC: https://ktc.uky.edu/

### Michigan
- Traffic Crash Reporting Unit: 517-241-1699
- Email: CrashTCRS@michigan.gov
- MTCF: https://www.michigantrafficcrashfacts.org/

### NHTSA
- FARS API: https://crashviewer.nhtsa.dot.gov/CrashAPI
- Data requests: crashstats.nhtsa.dot.gov

---

## Conclusion

**Maryland** is the only state among the three with a fully public, programmatic API that can be integrated immediately. **Kentucky** and **Michigan** would require formal data sharing agreements or manual data handling. The **NHTSA FARS API** can supplement fatal crash data for any state but is limited to fatal crashes only.

Recommended approach:
1. Start with Maryland integration (immediate value, similar to Virginia workflow)
2. Add NHTSA FARS as a supplemental data source
3. Pursue formal data agreements with Kentucky and Michigan if needed
