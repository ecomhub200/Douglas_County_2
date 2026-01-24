# Comprehensive US State Crash Database Research

**Date:** January 24, 2026
**Purpose:** Evaluate public crash databases for all 50 US states for potential integration with the Virginia Crash Analysis Tool

---

## Executive Summary

This research identifies crash database availability and API access for all 50 US states. States are categorized by their data accessibility:

| Category | Count | Description |
|----------|-------|-------------|
| **Tier 1 - Full API** | 12 | Public REST API with programmatic access |
| **Tier 2 - ArcGIS Portal** | 18 | ArcGIS-based open data with GeoServices API |
| **Tier 3 - Query Tool Only** | 14 | Web-based query tools, limited export |
| **Tier 4 - Restricted** | 6 | No public access, requires authorization |

---

## Quick Reference: States with Public APIs

### Tier 1: Full Public REST API Available

| State | Platform | API Endpoint | Notes |
|-------|----------|--------------|-------|
| **Maryland** | Socrata | `opendata.maryland.gov/resource/65du-s3qu.json` | Best for integration |
| **Connecticut** | Socrata | `data.ct.gov` | Full crash repository |
| **New York** | Socrata | `data.ny.gov` | 3-year rolling window |
| **Delaware** | Socrata | `data.delaware.gov` | Since 2009 |
| **Vermont** | Custom API | `apps.vtrans.vermont.gov/crashdata` | REST JSON API |
| **Iowa** | ArcGIS + API | `data.iowadot.gov/api/search/definition/` | Feature Server available |
| **Illinois** | ArcGIS | `gis-idot.opendata.arcgis.com` | Multiple years |
| **Louisiana** | ArcGIS | `data-ladotd.opendata.arcgis.com` | GeoServices API |
| **Texas** | CRIS Extract | `cris.dot.state.tx.us` | Bulk CSV via registration |
| **Hawaii** | CKAN/Socrata | `opendata.hawaii.gov` | CKAN API |
| **Alaska** | ArcGIS | `data-soa-akdot.opendata.arcgis.com` | Search API available |
| **NYC** | Socrata | `data.cityofnewyork.us` | City-level, very comprehensive |

### Tier 2: ArcGIS Open Data Portal (GeoServices API)

| State | Portal URL | API Type |
|-------|------------|----------|
| Massachusetts | massdot-impact-crashes-vhb.opendata.arcgis.com | GeoServices |
| Pennsylvania | crashinfo.penndot.gov + GIS Portal | GeoServices |
| Florida | gis-fdot.opendata.arcgis.com | GeoServices |
| Georgia | gdot.aashtowaresafety.net | Numetric/AASHTOWare |
| South Carolina | fatality-count-scdps.hub.arcgis.com | GeoServices |
| Ohio | gis.dot.state.oh.us/tims | GeoServices |
| Wisconsin | data-wisdot.opendata.arcgis.com | GeoServices |
| Colorado | data-cdot.opendata.arcgis.com | GeoServices |
| Nevada | data-ndot.opendata.arcgis.com | GeoServices |
| Utah | data-uplan.opendata.arcgis.com | GeoServices |
| Oregon | ArcGIS web apps | GeoServices |
| Washington | geo.wa.gov | GeoServices |
| Idaho | data-iplan.opendata.arcgis.com | GeoServices |
| Montana | gis-mdt.opendata.arcgis.com | GeoServices |
| West Virginia | data-wvdot.opendata.arcgis.com | GeoServices |
| Mississippi | gis-mdot.opendata.arcgis.com | GeoServices |
| Oklahoma | gis-okdot.opendata.arcgis.com | GeoServices |
| Arkansas | ArcGIS Dashboard | Feature Service |

---

## Detailed State-by-State Analysis

### Northeast Region

#### Connecticut
- **System:** Connecticut Crash Data Repository (CTCDR)
- **Portal:** data.ct.gov, ctcrash.uconn.edu
- **API:** ✅ Socrata SODA API
- **Data Range:** Multi-year
- **Format:** JSON, CSV, XML
- **Integration:** HIGH priority

#### Delaware
- **System:** Delaware Open Data Portal
- **Portal:** data.delaware.gov/Transportation/Public-Crash-Data/827n-m6xc
- **API:** ✅ Socrata SODA API
- **Data Range:** Since 2009
- **Format:** JSON, CSV
- **Integration:** HIGH priority
- **Notes:** Dashboard updated monthly

#### Maine
- **System:** Maine Public Crash Query Tool
- **Portal:** mdotapps.maine.gov/mainecrashpublic/
- **API:** ❌ No public API
- **Access:** Web query tool, advanced user registration available
- **Integration:** LOW priority

#### Maryland
- **System:** Maryland Open Data Portal (Socrata)
- **Portal:** opendata.maryland.gov/resource/65du-s3qu
- **API:** ✅ Full Socrata SODA API
- **Data Range:** Multi-year
- **Format:** JSON, CSV, XML, GeoJSON
- **Integration:** **HIGHEST** priority - best candidate for immediate integration

#### Massachusetts
- **System:** MassDOT Impact Open Data Hub
- **Portal:** massdot-impact-crashes-vhb.opendata.arcgis.com
- **API:** ✅ ArcGIS GeoServices API
- **Format:** CSV, KML, GeoJSON
- **Integration:** HIGH priority

#### New Hampshire
- **System:** Vision (DMV Crash Data System)
- **Portal:** nhgeodata.unh.edu (GIS Hub)
- **API:** ❌ No public crash API
- **Access:** Contact NHDOT, TDMS for traffic data
- **Integration:** LOW priority

#### New Jersey
- **System:** NJTR-1 Reports (NJDOT)
- **Portal:** nj.gov/transportation/refdata/accident/crash_data.shtm
- **API:** ⚠️ No official API, but `njtr1` R package available
- **Data Range:** 2001-2020
- **Format:** TXT files (no headers)
- **Integration:** MEDIUM priority (requires processing)

#### New York State
- **System:** Accident Information System (AIS)
- **Portal:** data.ny.gov (Motor Vehicle Crashes datasets)
- **API:** ✅ Socrata SODA API
- **Data Range:** 3-year rolling window
- **Format:** CSV, JSON, XML, RDF
- **Integration:** HIGH priority

#### NYC (City)
- **System:** Motor Vehicle Collisions
- **Portal:** data.cityofnewyork.us
- **API:** ✅ Socrata SODA API
- **Data Range:** Since April 2016
- **Format:** JSON, CSV
- **Integration:** HIGH priority (city-level)

#### Pennsylvania
- **System:** PCIT (Pennsylvania Crash Information Tool)
- **Portal:** crashinfo.penndot.pa.gov
- **API:** ✅ ArcGIS GIS Portal (partial)
- **Data Range:** 20 years (10-year query limit)
- **Format:** CSV, GeoJSON via GIS Portal
- **Integration:** MEDIUM priority

#### Rhode Island
- **System:** RIDOT (restricted)
- **Portal:** None public
- **API:** ❌ **No public access**
- **Notes:** RIDOT denies public crash data requests citing 23 U.S.C. §409
- **Integration:** NOT FEASIBLE without legislation

#### Vermont
- **System:** VTrans CRASH API
- **Portal:** apps.vtrans.vermont.gov/crashdata
- **API:** ✅ **Custom REST API (JSON)**
- **Endpoint:** `GET api/Accident`
- **Data Range:** Multi-year
- **Integration:** HIGH priority - has dedicated API

---

### Southeast Region

#### Alabama
- **System:** CARE (Critical Analysis Reporting Environment)
- **Portal:** safety.aladata.com (restricted)
- **API:** ❌ **No public access**
- **Notes:** 23 U.S.C. §409 protection; ALDOT ceased releasing data in 1995
- **Integration:** NOT FEASIBLE

#### Florida
- **System:** Signal Four Analytics (S4)
- **Portal:** signal4analytics.com, gis-fdot.opendata.arcgis.com
- **API:** ✅ ArcGIS GeoServices
- **Access:** Public dashboard free; full access restricted to government
- **Integration:** MEDIUM priority

#### Georgia
- **System:** GEARS (LexisNexis)
- **Portal:** gearsportal.com (restricted), gdot.aashtowaresafety.net
- **API:** ⚠️ GEARS restricted; public dashboard allows data download
- **Access:** Requires authorization for full GEARS access
- **Integration:** MEDIUM priority (dashboard data only)

#### Kentucky
- **System:** KYOPS
- **Portal:** crashinformationky.org (query tool)
- **API:** ❌ No public API
- **Access:** Web query tool, formal data requests
- **Contact:** KSP Records 502-227-8700
- **Integration:** LOW priority

#### Louisiana
- **System:** CARTS (LSU)
- **Portal:** data-ladotd.opendata.arcgis.com, carts.lsu.edu
- **API:** ✅ ArcGIS GeoServices API
- **Format:** CSV, GeoJSON, API
- **Integration:** HIGH priority

#### Mississippi
- **System:** MDOT GIS
- **Portal:** gis-mdot.opendata.arcgis.com
- **API:** ✅ ArcGIS GeoServices
- **Integration:** MEDIUM priority

#### North Carolina
- **System:** TEAAS (Traffic Engineering Accident Analysis System)
- **Portal:** connect.ncdot.gov (requires training/account)
- **API:** ❌ No public API
- **Access:** Training + account required
- **Integration:** LOW priority

#### South Carolina
- **System:** SCCATTS
- **Portal:** fatality-count-scdps.hub.arcgis.com
- **API:** ✅ ArcGIS GeoServices
- **Format:** CSV, GeoJSON
- **Integration:** MEDIUM priority

#### Tennessee
- **System:** TITAN
- **Portal:** titan.safety.tn.gov (law enforcement only)
- **API:** ❌ No public API
- **Access:** Dashboards at tntrafficsafety.org
- **Integration:** LOW priority

#### Virginia
- **System:** Virginia Roads ArcGIS
- **Portal:** virginiaroads.org (current implementation)
- **API:** ✅ ArcGIS REST API
- **Status:** Already integrated

#### West Virginia
- **System:** WVDOT GIS
- **Portal:** data-wvdot.opendata.arcgis.com
- **API:** ✅ ArcGIS GeoServices
- **Integration:** MEDIUM priority

---

### Midwest Region

#### Illinois
- **System:** IDOT GIS Portal
- **Portal:** gis-idot.opendata.arcgis.com
- **API:** ✅ ArcGIS GeoServices
- **Data Range:** Multiple years (2014, 2016, 2020, 2022+)
- **Format:** CSV, KML, GeoJSON
- **Integration:** HIGH priority

#### Indiana
- **System:** ARIES (LexisNexis)
- **Portal:** ariesportal.com (restricted)
- **API:** ⚠️ Restricted; dashboard available
- **Access:** Contact aries.support@lexisnexisrisk.com
- **Integration:** LOW priority

#### Iowa
- **System:** ICAT (Iowa Crash Analysis Tool)
- **Portal:** data.iowadot.gov, icat.iowadot.gov
- **API:** ✅ **Multiple APIs available**
  - Search API: `data.iowadot.gov/api/search/definition/`
  - Feature Server: `gis.iowadot.gov/agshost/rest/services/Traffic_Safety/Crash_Data/FeatureServer`
- **Data Range:** 10 years
- **Integration:** **HIGH priority**

#### Kansas
- **System:** KCARS
- **Portal:** ksdot.gov (dashboard)
- **API:** ❌ No public API
- **Access:** Request form, open records
- **Integration:** LOW priority

#### Michigan
- **System:** MTCF (Michigan Traffic Crash Facts)
- **Portal:** michigantrafficcrashfacts.org
- **API:** ❌ No public API
- **Access:** Web query tool with export
- **Contact:** CrashTCRS@michigan.gov
- **Integration:** LOW priority

#### Minnesota
- **System:** MnCMAT2
- **Portal:** mncmat2.dot.state.mn.us (restricted to professionals)
- **API:** ❌ No public API
- **Access:** Account required for traffic safety professionals
- **Integration:** LOW priority

#### Missouri
- **System:** STARS/MOCARS
- **Portal:** modot.org dashboards, savemolives.com
- **API:** ❌ No public API
- **Access:** Web dashboards, mapping tools
- **Integration:** LOW priority

#### Nebraska
- **System:** NDOT NTIP
- **Portal:** ndotdata.nebraska.gov, ntip.nebraska.gov
- **API:** ⚠️ API available per documentation
- **Integration:** MEDIUM priority

#### North Dakota
- **System:** NDDOT Traffic Records
- **Portal:** gishubdata-ndgov.hub.arcgis.com
- **API:** ✅ ArcGIS GeoServices
- **Integration:** MEDIUM priority

#### Ohio
- **System:** GCAT (GIS Crash Analysis Tool)
- **Portal:** gis.dot.state.oh.us/tims, ohtrafficdata.dps.ohio.gov
- **API:** ⚠️ ODOT TIMS GeoServices (account may be required)
- **Access:** CSV exports via email within 24 hours
- **Integration:** MEDIUM priority

#### South Dakota
- **System:** SDARS
- **Portal:** safesd.gov
- **API:** ❌ No public API
- **Access:** Pipe-delimited downloads annually
- **Integration:** LOW priority

#### Wisconsin
- **System:** WisTransPortal (TOPS Lab)
- **Portal:** data-wisdot.opendata.arcgis.com, transportal.cee.wisc.edu
- **API:** ✅ ArcGIS GeoServices
- **Access:** Account available for government/consultants
- **Integration:** MEDIUM priority

---

### Southwest Region

#### Arizona
- **System:** ACIS (Arizona Crash Information System)
- **Portal:** Citrix remote desktop (restricted)
- **API:** ❌ No public API
- **Access:** ADOT VPN required
- **Integration:** LOW priority

#### New Mexico
- **System:** TraCS / NMDOT Traffic Records
- **Portal:** nmtrafficrecords.com (data request forms)
- **API:** ❌ No public API
- **Access:** Data requests, 23 U.S.C. §409 restrictions
- **Integration:** LOW priority

#### Oklahoma
- **System:** SAFE-T (OU ITS Lab)
- **Portal:** gis-okdot.opendata.arcgis.com
- **API:** ✅ ArcGIS GeoServices
- **Integration:** MEDIUM priority

#### Texas
- **System:** CRIS (Crash Records Information System)
- **Portal:** cris.dot.state.tx.us/public/Query
- **API:** ⚠️ **Bulk CSV extracts via registration**
- **Access:** Self-registration at cris.txdot.gov
- **Data Range:** 10 years retention
- **Guide:** txdot.gov CRIS Guide PDF
- **Integration:** **HIGH priority** - large state, bulk data access

---

### Western Region

#### Alaska
- **System:** Alaska DOT&PF
- **Portal:** data-soa-akdot.opendata.arcgis.com
- **API:** ✅ ArcGIS GeoServices + Search API
- **Data Range:** 2013-2022 certified
- **Integration:** MEDIUM priority

#### California
- **System:** CCRS (California Crash Reporting System) - replaced SWITRS in 2025
- **Portal:** data.ca.gov/dataset/ccrs
- **API:** ⚠️ Check California Open Data for CCRS API
- **Alternative:** TIMS (tims.berkeley.edu) for geocoded data
- **Integration:** HIGH priority (large state)

#### Colorado
- **System:** CDOT Safety Portal
- **Portal:** data-cdot.opendata.arcgis.com
- **API:** ✅ ArcGIS GeoServices
- **Data Range:** 2021-2025+
- **Integration:** HIGH priority

#### Hawaii
- **System:** Hawaii Open Data Portal
- **Portal:** opendata.hawaii.gov (CKAN), data.hawaii.gov (Socrata)
- **API:** ✅ CKAN API + Socrata API
- **Integration:** MEDIUM priority

#### Idaho
- **System:** ITD Safety Dashboards
- **Portal:** data-iplan.opendata.arcgis.com
- **API:** ✅ ArcGIS GeoServices
- **Integration:** MEDIUM priority

#### Montana
- **System:** MDT GIS
- **Portal:** gis-mdt.opendata.arcgis.com
- **API:** ✅ ArcGIS GeoServices
- **Data Range:** 2020-2024
- **Integration:** MEDIUM priority

#### Nevada
- **System:** NDOT GeoHub
- **Portal:** data-ndot.opendata.arcgis.com, geohub-ndot.hub.arcgis.com
- **API:** ✅ ArcGIS GeoServices
- **Data Range:** 2019-2023
- **Integration:** HIGH priority

#### Oregon
- **System:** CDS (Crash Data System)
- **Portal:** oregon.gov/odot/data (Crash Data Viewer, TransGIS)
- **API:** ⚠️ ArcGIS web apps; API in development
- **Access:** Access Decode Databases, Geodatabases
- **Integration:** MEDIUM priority

#### Utah
- **System:** Numetric/AASHTOWare Safety
- **Portal:** data-uplan.opendata.arcgis.com, udps.numetric.net
- **API:** ✅ ArcGIS GeoServices
- **Access:** Numetric account for full access
- **Integration:** MEDIUM priority

#### Washington
- **System:** WSDOT Crash Data Portal
- **Portal:** geo.wa.gov (WSDOT Crash Data Portal)
- **API:** ✅ ArcGIS GeoServices
- **Access:** Public disclosure for detailed data
- **Integration:** HIGH priority

#### Wyoming
- **System:** WYDOT Highway Safety
- **Portal:** dot.state.wy.us (Public Reports Tool)
- **API:** ❌ No public API
- **Access:** Web reports tool, contact for data
- **Integration:** LOW priority

---

## Federal Supplemental Data Sources

### NHTSA FARS API (All States)
- **URL:** crashviewer.nhtsa.dot.gov/CrashAPI
- **Scope:** Fatal crashes only (K severity)
- **Coverage:** All 50 states + DC + Puerto Rico
- **Data Range:** 2010-present
- **Formats:** JSON, CSV, XML
- **Limit:** 5000 records per query
- **State Codes:** MD=24, KY=21, MI=26, VA=51, etc.

**Key Endpoints:**
```
/crashes/GetCaseList?states={code}&fromYear={year}&toYear={year}&format=json
/crashes/GetCrashesByLocation?state={code}&county={code}&format=json
/FARSData/GetFARSData?dataset=Accident&FromYear={year}&ToYear={year}&State={code}&format=csv
```

### FMCSA Crash Statistics
- **URL:** ai.fmcsa.dot.gov/CrashStatistics/Visualization
- **Scope:** Commercial motor vehicle crashes
- **Use:** Truck/bus crash analysis

---

## Integration Priority Matrix

### Immediate Integration (Phase 1)
| State | Platform | Effort | Value |
|-------|----------|--------|-------|
| Maryland | Socrata | Low | High |
| Connecticut | Socrata | Low | Medium |
| Delaware | Socrata | Low | Medium |
| New York | Socrata | Low | High |
| Vermont | Custom API | Low | Medium |

### Near-Term Integration (Phase 2)
| State | Platform | Effort | Value |
|-------|----------|--------|-------|
| Iowa | ArcGIS + API | Medium | Medium |
| Illinois | ArcGIS | Medium | High |
| Texas | CRIS Bulk | Medium | High |
| California | CCRS | Medium | High |
| Florida | ArcGIS | Medium | High |
| Washington | ArcGIS | Medium | Medium |

### Future Integration (Phase 3)
| State | Platform | Effort | Value |
|-------|----------|--------|-------|
| All ArcGIS States | GeoServices | Medium | Varies |
| NHTSA FARS | REST API | Low | All states (fatal only) |

---

## Recommended Configuration Architecture

### Multi-State Config Structure

```json
{
  "version": "2.0",
  "activeState": "virginia",
  "states": {
    "maryland": {
      "name": "Maryland",
      "fipsCode": "24",
      "region": "northeast",
      "dataSource": {
        "type": "socrata",
        "baseUrl": "https://opendata.maryland.gov",
        "dataset": "65du-s3qu",
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
        "route": "route_name",
        "collisionType": "collision_type",
        "weather": "weather",
        "light": "light",
        "roadCondition": "road_condition",
        "pedestrian": "ped_visible",
        "bicycle": "bike_visible"
      },
      "severityMapping": {
        "FATAL": "K",
        "SUSPECTED SERIOUS INJURY": "A",
        "SUSPECTED MINOR INJURY": "B",
        "POSSIBLE INJURY": "C",
        "NO APPARENT INJURY": "O"
      },
      "jurisdictions": {
        "montgomery": {
          "name": "Montgomery County",
          "fips": "031",
          "filter": "county_name='Montgomery'"
        },
        "baltimore_county": {
          "name": "Baltimore County",
          "fips": "005",
          "filter": "county_name='Baltimore'"
        },
        "prince_georges": {
          "name": "Prince George's County",
          "fips": "033",
          "filter": "county_name='Prince George\\'s'"
        }
      }
    },
    "connecticut": {
      "name": "Connecticut",
      "fipsCode": "09",
      "region": "northeast",
      "dataSource": {
        "type": "socrata",
        "baseUrl": "https://data.ct.gov",
        "dataset": "tusz-n3pv",
        "apiKey": null
      },
      "columnMapping": { /* ... */ }
    },
    "iowa": {
      "name": "Iowa",
      "fipsCode": "19",
      "region": "midwest",
      "dataSource": {
        "type": "arcgis",
        "baseUrl": "https://gis.iowadot.gov/agshost/rest/services/Traffic_Safety/Crash_Data/FeatureServer",
        "layer": 0
      },
      "columnMapping": { /* ... */ }
    },
    "texas": {
      "name": "Texas",
      "fipsCode": "48",
      "region": "southwest",
      "dataSource": {
        "type": "cris",
        "registrationUrl": "https://cris.txdot.gov",
        "queryUrl": "https://cris.dot.state.tx.us/public/Query/app/home",
        "bulkExtract": true
      },
      "columnMapping": { /* ... */ }
    },
    "vermont": {
      "name": "Vermont",
      "fipsCode": "50",
      "region": "northeast",
      "dataSource": {
        "type": "custom",
        "apiUrl": "http://apps.vtrans.vermont.gov/crashdata/api/Accident",
        "format": "json"
      },
      "columnMapping": { /* ... */ }
    }
  },
  "federalSources": {
    "fars": {
      "name": "NHTSA FARS",
      "apiUrl": "https://crashviewer.nhtsa.dot.gov/CrashAPI",
      "scope": "fatal",
      "enabled": true
    }
  }
}
```

### Data Source Type Handlers

| Type | Handler | Notes |
|------|---------|-------|
| `socrata` | Socrata SODA API | JSON/CSV, SoQL queries |
| `arcgis` | ArcGIS REST API | Feature Service queries |
| `cris` | TxDOT CRIS | Bulk CSV extracts |
| `custom` | Custom REST | State-specific APIs |
| `static` | Local CSV | Manual download states |

---

## Implementation Roadmap

### Phase 1: Socrata States (Weeks 1-2)
1. Create `download_socrata_crash_data.py`
2. Implement Maryland integration
3. Add Connecticut, Delaware, New York
4. Test column mappings

### Phase 2: ArcGIS States (Weeks 3-4)
1. Create `download_arcgis_crash_data.py`
2. Implement Iowa (has both APIs)
3. Add Illinois, Florida, Washington
4. Handle pagination and rate limits

### Phase 3: Special Cases (Weeks 5-6)
1. Texas CRIS bulk extract support
2. Vermont custom API integration
3. NHTSA FARS supplemental data
4. UI state selector

### Phase 4: Expansion (Ongoing)
1. Add remaining ArcGIS states
2. Column mapping templates
3. Data quality validation
4. Performance optimization

---

## State Contact Information

### High-Priority States

| State | Contact | Email/Phone |
|-------|---------|-------------|
| Maryland | Open Data Portal | support via portal |
| Texas | TxDOT CRIS | cris@txdot.gov |
| California | CHP/Caltrans | via CCRS portal |
| Florida | FDOT Safety | signal4analytics.com |
| Iowa | DOT Traffic Safety | crashdatarequest form |

### Data Request Contacts

| State | Method | Contact |
|-------|--------|---------|
| Kentucky | Phone | KSP 502-227-8700 |
| Michigan | Email | CrashTCRS@michigan.gov |
| North Carolina | Email | TEAAS_Support@ncdot.gov |
| Vermont | Email | AOT-CrashRequests@vermont.gov |
| Wisconsin | Email | crash-data@topslab.wisc.edu |

---

## Legal Considerations

### 23 U.S.C. §409 Protection
Several states cite federal law to restrict crash data release:
- **Alabama** - No public release since 1995
- **Rhode Island** - Denies all public requests
- **New Mexico** - Restrictions on raw data

### Open Records Alternatives
States with restrictions may still provide:
- Aggregated statistics
- De-identified datasets
- Research agreements
- FOIA/public records requests

---

## Conclusion

**Best States for Immediate Integration:**
1. **Maryland** - Full Socrata API, similar structure to VA
2. **Connecticut** - Full Socrata API
3. **Delaware** - Full Socrata API, since 2009
4. **New York** - Full Socrata API
5. **Vermont** - Custom REST API
6. **Iowa** - Multiple APIs available

**States Requiring Alternative Approaches:**
- Rhode Island, Alabama - Not feasible without legislation
- Kentucky, Michigan, Minnesota - Formal data agreements needed
- Texas - Bulk extract via registration (worthwhile for large state)

**Universal Supplemental:**
- NHTSA FARS API for fatal crash data across all states

---

## Appendix: State FIPS Codes

| State | FIPS | State | FIPS |
|-------|------|-------|------|
| Alabama | 01 | Montana | 30 |
| Alaska | 02 | Nebraska | 31 |
| Arizona | 04 | Nevada | 32 |
| Arkansas | 05 | New Hampshire | 33 |
| California | 06 | New Jersey | 34 |
| Colorado | 08 | New Mexico | 35 |
| Connecticut | 09 | New York | 36 |
| Delaware | 10 | North Carolina | 37 |
| Florida | 12 | North Dakota | 38 |
| Georgia | 13 | Ohio | 39 |
| Hawaii | 15 | Oklahoma | 40 |
| Idaho | 16 | Oregon | 41 |
| Illinois | 17 | Pennsylvania | 42 |
| Indiana | 18 | Rhode Island | 44 |
| Iowa | 19 | South Carolina | 45 |
| Kansas | 20 | South Dakota | 46 |
| Kentucky | 21 | Tennessee | 47 |
| Louisiana | 22 | Texas | 48 |
| Maine | 23 | Utah | 49 |
| Maryland | 24 | Vermont | 50 |
| Massachusetts | 25 | Virginia | 51 |
| Michigan | 26 | Washington | 53 |
| Minnesota | 27 | West Virginia | 54 |
| Mississippi | 28 | Wisconsin | 55 |
| Missouri | 29 | Wyoming | 56 |

---

## Sources

### State Portals
- [Maryland Open Data](https://opendata.maryland.gov/)
- [Connecticut Open Data](https://data.ct.gov/)
- [Delaware Open Data](https://data.delaware.gov/)
- [New York Open Data](https://data.ny.gov/)
- [Vermont VTrans](https://vtrans.vermont.gov/)
- [Iowa DOT Open Data](https://data.iowadot.gov/)
- [Illinois DOT GIS](https://gis-idot.opendata.arcgis.com/)
- [Texas CRIS](https://cris.dot.state.tx.us/)
- [California Open Data](https://data.ca.gov/)
- [Florida Signal Four](https://signal4analytics.com/)

### Federal Resources
- [NHTSA Crash API](https://crashviewer.nhtsa.dot.gov/CrashAPI)
- [NHTSA FARS](https://www.nhtsa.gov/research-data/fatality-analysis-reporting-system-fars)
- [Crash Data Sources by State](https://www.saferstreetspriorityfinder.com/tool/crashdatasources/)

### API Documentation
- [Socrata Developer Portal](https://dev.socrata.com/)
- [ArcGIS REST API](https://developers.arcgis.com/rest/)
