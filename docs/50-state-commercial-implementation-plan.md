# 50-State Crash Data Commercial Integration: Implementation Plan

**Date:** February 5, 2026
**Version:** 1.0
**Purpose:** Comprehensive plan for autonomously discovering, integrating, and commercializing crash data from all 50 US states

---

## Executive Summary

This plan outlines a phased approach to build a commercial crash data aggregation service covering all 50 US states. The strategy accounts for the legal reality that crash data licensing varies dramatically by state, and only certain commercial models are legally viable.

### Key Findings

| Aspect | Reality |
|--------|---------|
| States with public API access | ~12 (Socrata/REST) |
| States with ArcGIS portals | ~18 (GeoServices API) |
| States with query tools only | ~14 (manual export) |
| States with restricted access | ~6 (DUA/FOIA required) |
| States explicitly allowing commercial use | ~3-5 (NYC, California, Federal) |
| States with ambiguous commercial terms | ~40+ |
| **Viable commercial path** | **3 models (see Section 2)** |

---

## Table of Contents

1. [Legal Framework for Commercial Use](#1-legal-framework-for-commercial-use)
2. [Viable Commercial Models](#2-viable-commercial-models)
3. [State Classification Matrix](#3-state-classification-matrix)
4. [Technical Architecture](#4-technical-architecture)
5. [Autonomous Discovery Pipeline](#5-autonomous-discovery-pipeline)
6. [Data Normalization Factory](#6-data-normalization-factory)
7. [Health Monitoring & Self-Healing](#7-health-monitoring--self-healing)
8. [Phased Implementation Schedule](#8-phased-implementation-schedule)
9. [Cost Analysis](#9-cost-analysis)
10. [Risk Mitigation](#10-risk-mitigation)

---

## 1. Legal Framework for Commercial Use

### 1.1 Federal Law Constraints

| Law | Impact on Commercial Use |
|-----|-------------------------|
| **DPPA (18 U.S.C. § 2721)** | Personal identifiers (names, addresses, SSN, license numbers) are protected. Crash event data itself is NOT protected. De-identified data is commercially usable. |
| **23 U.S.C. § 407** | Data compiled for federal safety programs (HSIP, Section 148) CANNOT be used in litigation. This applies regardless of how data was obtained. |
| **17 U.S.C. § 105** | Federal government works (FARS, CRSS) are public domain. No copyright restrictions on commercial use. |

### 1.2 Data Source Licensing Tiers

```
┌─────────────────────────────────────────────────────────────────────┐
│                    COMMERCIAL VIABILITY SPECTRUM                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ✅ CLEAR YES          ⚠️ AMBIGUOUS           ❌ CLEAR NO            │
│  ───────────          ────────────           ────────────            │
│  • NHTSA FARS/CRSS    • Most state open      • States with DUAs     │
│  • NYC Open Data        data portals           prohibiting           │
│  • CA Open Data       • Custom ToS without     commercial use        │
│  • CC0/PDDL licensed    explicit commercial  • Anti-solicitation    │
│    datasets             mention                restricted uses       │
│                       • "Public information"  • Rhode Island         │
│                         without license       • Alabama (§409)       │
│                                                                       │
│  [~5 states]          [~40 states]           [~5 states]            │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 Required De-Identification

For any commercial product, crash records must be stripped of:

| Must Remove | Can Retain |
|-------------|-----------|
| Driver/occupant names | Crash location (lat/lon, route, milepost) |
| Home addresses | Date, time, day of week |
| Social Security numbers | Severity (KABCO) |
| Driver license numbers | Collision type, manner |
| Phone numbers | Weather, lighting, road conditions |
| Medical details | Vehicle types (not VINs) |
| Photographs of individuals | Contributing factors |
| Date of birth (varies) | Pedestrian/bicycle involvement (Y/N) |

### 1.4 The Litigation Prohibition Reality

**23 U.S.C. § 407 applies broadly.** Any crash data compiled or collected for federal highway safety programs cannot be:
- Discovered in legal proceedings
- Admitted as evidence in federal or state court
- Used to establish liability

This does NOT prevent commercial use for:
- Safety analytics and consulting
- Insurance risk assessment (non-litigation)
- Urban planning and engineering
- Academic research
- Software products for DOTs

---

## 2. Viable Commercial Models

Based on legal analysis and market precedents, three commercial models are viable:

### Model A: Analytics SaaS for Government Agencies (Recommended)

**Description:** Sell software and analytics services to state/local DOTs that process *their own* crash data.

**Precedents:** Numetric (now AASHTOWare), VHB, Iteris

**Legal Structure:**
- You provide the software platform
- Agency provides their own crash data
- No redistribution of raw data
- Revenue from software licenses, not data

**Revenue Model:**
- Per-seat SaaS licensing ($500-2,000/user/month)
- Enterprise contracts ($50K-500K/year per agency)
- Implementation services

**Pros:**
- Cleanest legal path
- High margins on software
- Recurring revenue
- No data licensing risk

**Cons:**
- Long government sales cycles
- Procurement complexity
- Must compete with AASHTOWare

---

### Model B: Aggregated Public Domain Data Product

**Description:** Aggregate and enhance FARS (fatal crashes) + state open data that is clearly licensed for commercial use.

**Data Sources:**
- NHTSA FARS API (public domain, all states, fatal only)
- NHTSA CRSS (public domain, sample data)
- NYC Open Data (explicitly no restrictions)
- California CCRS (open license)
- States with CC0/PDDL licensed datasets

**Legal Structure:**
- Only use data with explicit commercial-friendly licenses
- Add value through: geocoding enhancement, cross-state normalization, historical trends, predictive analytics
- Clearly document provenance of each record

**Revenue Model:**
- API access tiers ($99-999/month)
- Bulk data licensing ($5K-50K/year)
- Custom analytics reports

**Pros:**
- Lower legal risk with clear licensing
- FARS provides 50-state coverage (fatal crashes)
- Differentiation through analytics layer

**Cons:**
- FARS is fatal-only (~40K crashes/year nationally vs. ~6M total)
- Limited to explicitly licensed state data
- Competitors have same access to FARS

---

### Model C: State Partnership / Data Licensing Agreements

**Description:** Negotiate formal data licensing agreements with individual state DOTs that explicitly permit commercial use.

**Precedents:** LexisNexis eCrash/BuyCrash (provides software to agencies in exchange for data access)

**Legal Structure:**
- Formal contracts with each state DOT
- Revenue sharing or per-record fees to the state
- Defined commercial use rights
- Compliance monitoring

**Revenue Model:**
- Resell crash reports to insurers, attorneys, researchers
- API access for commercial customers
- Premium real-time data feeds

**Pros:**
- Full legal clarity through contracts
- Access to complete crash records
- High-value B2B customers (insurance)

**Cons:**
- Must negotiate 50 separate agreements
- States may refuse commercial licensing
- LexisNexis has incumbency advantage
- Higher legal/compliance overhead

---

### Recommended Approach: Hybrid Model A + B

**Phase 1:** Launch with Model B (aggregated public domain data)
- FARS API for 50-state fatal crash coverage
- Add states with explicit open licenses as discovered
- Build the analytics platform and customer base

**Phase 2:** Expand with Model A (SaaS for agencies)
- Use Phase 1 platform as foundation
- Target county/local agencies first (faster sales cycles)
- Each agency brings their own non-public data

**Phase 3:** Selective Model C (state partnerships)
- Target high-value states (TX, FL, CA, NY)
- Propose revenue sharing or software-for-data trades
- Build formal data licensing program

---

## 3. State Classification Matrix

### 3.1 Commercial Viability by State

| State | API Type | License Status | Commercial Viability | Priority |
|-------|----------|---------------|---------------------|----------|
| **Federal (FARS)** | REST API | Public Domain | ✅ CLEAR YES | P0 |
| **New York City** | Socrata | No restrictions (Local Law 11) | ✅ CLEAR YES | P1 |
| **California** | TIMS/CCRS | Open License | ✅ CLEAR YES | P1 |
| **Maryland** | Socrata | Custom ToS | ⚠️ Ambiguous | P2 |
| **Connecticut** | Socrata | Custom ToS | ⚠️ Ambiguous | P2 |
| **Delaware** | Socrata | Custom ToS | ⚠️ Ambiguous | P2 |
| **New York State** | Socrata | Custom ToS | ⚠️ Ambiguous | P2 |
| **Vermont** | REST API | Custom ToS | ⚠️ Ambiguous | P2 |
| **Virginia** | ArcGIS | Custom ToS + §407 | ⚠️ Ambiguous | P2 |
| **Iowa** | ArcGIS | Custom ToS | ⚠️ Ambiguous | P2 |
| **Illinois** | ArcGIS | Custom ToS | ⚠️ Ambiguous | P2 |
| **Florida** | ArcGIS | Anti-solicitation law | ⚠️ Restricted uses | P3 |
| **Texas** | CRIS Portal | Account required | ⚠️ DUA likely | P3 |
| **Massachusetts** | ArcGIS | DPPA-governed | ⚠️ Restricted | P3 |
| **Pennsylvania** | ArcGIS | Custom ToS | ⚠️ Ambiguous | P3 |
| **Ohio** | ArcGIS | Custom ToS | ⚠️ Ambiguous | P3 |
| **Georgia** | Numetric | Restricted | ❌ DUA required | P4 |
| **North Carolina** | TEAAS | Account required | ❌ DUA required | P4 |
| **Alabama** | CARE | §409 protected | ❌ NOT FEASIBLE | - |
| **Rhode Island** | None | Actively denied | ❌ NOT FEASIBLE | - |

### 3.2 Priority Definitions

| Priority | Definition | Target Timeline |
|----------|-----------|-----------------|
| **P0** | Public domain, no legal risk | Month 1 |
| **P1** | Explicit commercial license | Month 1-2 |
| **P2** | Ambiguous but likely safe (de-identified, public portal) | Month 2-4 |
| **P3** | Requires legal review or restricted uses | Month 4-6 |
| **P4** | Requires formal DUA negotiation | Month 6+ |

---

## 4. Technical Architecture

### 4.1 System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     CRASH LENS COMMERCIAL PLATFORM                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐             │
│  │   REGISTRY   │     │   FETCHER    │     │  NORMALIZER  │             │
│  │              │────▶│              │────▶│              │             │
│  │ 50 states    │     │ Per-source   │     │ StateAdapter │             │
│  │ Sources      │     │ Strategies   │     │ Factory      │             │
│  │ Licenses     │     │ Rate limits  │     │              │             │
│  └──────────────┘     └──────────────┘     └──────────────┘             │
│         │                    │                    │                      │
│         ▼                    ▼                    ▼                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐             │
│  │   MONITOR    │     │    CACHE     │     │   UNIFIED    │             │
│  │              │     │              │     │   DATABASE   │             │
│  │ Health check │     │ Redis/S3     │     │              │             │
│  │ Schema drift │     │ 30-day TTL   │     │ PostgreSQL   │             │
│  │ Self-healing │     │              │     │ + PostGIS    │             │
│  └──────────────┘     └──────────────┘     └──────────────┘             │
│                                                    │                      │
│                              ┌─────────────────────┴─────────────────┐   │
│                              ▼                                       ▼   │
│                       ┌──────────────┐                      ┌──────────┐ │
│                       │  PUBLIC API  │                      │ BROWSER  │ │
│                       │              │                      │ APP      │ │
│                       │ REST + GraphQL│                      │ (React)  │ │
│                       │ Rate limited │                      │          │ │
│                       └──────────────┘                      └──────────┘ │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Component Specifications

#### Registry Service (`states/registry.json` + API)

```json
{
  "version": "1.0.0",
  "lastUpdated": "2026-02-05T00:00:00Z",
  "states": {
    "VA": {
      "name": "Virginia",
      "fips": "51",
      "commercialTier": "P2",
      "license": {
        "type": "custom-tos",
        "url": "https://data.virginia.gov/terms",
        "commercialAllowed": "ambiguous",
        "restrictions": ["23 USC 407", "DPPA compliance"],
        "legalReviewDate": null,
        "legalReviewStatus": "pending"
      },
      "sources": [
        {
          "id": "va-arcgis-primary",
          "type": "arcgis",
          "name": "Virginia TREDS ArcGIS",
          "url": "https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/CrashData_Basic_Updated/FeatureServer/0/query",
          "fallbacks": [
            "https://services1.arcgis.com/..."
          ],
          "auth": "none",
          "rateLimit": {
            "requests": 2000,
            "perSeconds": 60
          },
          "pagination": {
            "type": "offset",
            "pageSize": 2000,
            "maxRecords": null
          },
          "status": {
            "current": "active",
            "lastCheck": "2026-02-05T06:00:00Z",
            "lastSuccess": "2026-02-05T06:00:00Z",
            "consecutiveFailures": 0
          },
          "schema": {
            "signature": ["Document Nbr", "Crash Severity", "RTE Name"],
            "lastValidated": "2026-02-05T00:00:00Z",
            "driftDetected": false
          }
        }
      ],
      "adapter": {
        "path": "states/virginia/config.json",
        "type": "native",
        "version": "2.0.0"
      },
      "dataRange": {
        "earliest": "2015-01-01",
        "latest": "current",
        "updateFrequency": "weekly"
      }
    }
  }
}
```

#### Fetcher Service

Handles the complexity of different API types:

| Source Type | Fetcher Strategy |
|-------------|-----------------|
| `socrata` | SODA API with `$limit/$offset` pagination |
| `arcgis` | FeatureServer with `resultOffset/resultRecordCount` |
| `arcgis-mapserver` | MapServer query with geometry export |
| `rest-json` | Generic REST with configurable pagination |
| `bulk-csv` | URL download with ETag/Last-Modified caching |
| `nhtsa-fars` | NHTSA CrashAPI with year/state params |

```python
# Pseudocode: Fetcher dispatch
class FetcherFactory:
    strategies = {
        'socrata': SocrataFetcher,
        'arcgis': ArcGISFetcher,
        'nhtsa-fars': FARSFetcher,
        'bulk-csv': BulkCSVFetcher,
    }

    def fetch(self, source: SourceConfig) -> Iterator[dict]:
        fetcher = self.strategies[source.type](source)
        for page in fetcher.paginate():
            yield from page.records
```

#### Normalizer Service (StateAdapter Factory)

Extends your existing `StateAdapter` pattern:

```javascript
// states/adapter_factory.js
const AdapterFactory = {
    adapters: {},

    async load(stateCode) {
        if (!this.adapters[stateCode]) {
            const config = await import(`./states/${stateCode}/config.json`);
            this.adapters[stateCode] = new StateAdapter(config);
        }
        return this.adapters[stateCode];
    },

    async normalize(stateCode, row) {
        const adapter = await this.load(stateCode);
        return adapter.normalizeRow(row);
    },

    async detectState(headers) {
        for (const [code, adapter] of Object.entries(this.adapters)) {
            if (adapter.matchesSignature(headers)) {
                return code;
            }
        }
        return null;
    }
};
```

### 4.3 Database Schema (Unified Format)

```sql
-- Core crash table (normalized to COL format)
CREATE TABLE crashes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id VARCHAR(50) NOT NULL,        -- e.g., "va-arcgis-primary"
    source_record_id VARCHAR(100) NOT NULL, -- Original ID from source
    state_fips CHAR(2) NOT NULL,
    county_fips CHAR(5),

    -- Temporal
    crash_date DATE NOT NULL,
    crash_time TIME,
    crash_year SMALLINT NOT NULL,

    -- Location
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    geom GEOMETRY(POINT, 4326),
    route_name VARCHAR(100),
    milepost DECIMAL(10,3),
    node_id VARCHAR(200),

    -- Classification
    severity CHAR(1) CHECK (severity IN ('K','A','B','C','O')),
    collision_type VARCHAR(100),
    weather_condition VARCHAR(50),
    light_condition VARCHAR(50),
    road_surface VARCHAR(50),

    -- Flags (boolean)
    pedestrian_involved BOOLEAN DEFAULT FALSE,
    bicycle_involved BOOLEAN DEFAULT FALSE,
    alcohol_involved BOOLEAN DEFAULT FALSE,
    speed_related BOOLEAN DEFAULT FALSE,
    distracted_driving BOOLEAN DEFAULT FALSE,

    -- Counts
    fatality_count SMALLINT DEFAULT 0,
    injury_a_count SMALLINT DEFAULT 0,
    injury_b_count SMALLINT DEFAULT 0,
    injury_c_count SMALLINT DEFAULT 0,

    -- Metadata
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    source_updated_at TIMESTAMPTZ,

    UNIQUE(source_id, source_record_id)
);

-- Indexes for common queries
CREATE INDEX idx_crashes_state_year ON crashes(state_fips, crash_year);
CREATE INDEX idx_crashes_county ON crashes(county_fips);
CREATE INDEX idx_crashes_severity ON crashes(severity);
CREATE INDEX idx_crashes_geom ON crashes USING GIST(geom);
CREATE INDEX idx_crashes_date ON crashes(crash_date);

-- Provenance tracking for legal compliance
CREATE TABLE data_provenance (
    id SERIAL PRIMARY KEY,
    source_id VARCHAR(50) NOT NULL,
    fetch_timestamp TIMESTAMPTZ NOT NULL,
    record_count INTEGER NOT NULL,
    license_type VARCHAR(50),
    license_url TEXT,
    commercial_allowed VARCHAR(20), -- 'yes', 'no', 'ambiguous'
    terms_snapshot_hash VARCHAR(64)
);
```

---

## 5. Autonomous Discovery Pipeline

### 5.1 Using Claude Code for State Research

For each state not yet in the registry, Claude Code can autonomously:

1. **Search for data sources**
   ```
   Web search: "{state} DOT crash data download API"
   Web search: "{state} open data portal crash records"
   Check: data.{state}.gov (Socrata)
   Check: {state}dot.opendata.arcgis.com (ArcGIS Hub)
   Check: NHTSA state data page
   ```

2. **Analyze data dictionary**
   ```
   Fetch: {state} crash data dictionary PDF
   Extract: Column names, data types, value domains
   Map: State columns → COL schema
   Identify: Derived fields (severity from injury counts, etc.)
   ```

3. **Assess licensing**
   ```
   Fetch: Portal terms of service
   Search: "{state} crash data commercial use policy"
   Check: Creative Commons / PDDL indicators
   Flag: Explicit restrictions or ambiguities
   ```

4. **Generate adapter config**
   ```
   Create: states/{state}/config.json
   Create: states/{state}/research.md (provenance)
   Test: With sample data (100 rows)
   Validate: Normalized output matches COL schema
   ```

### 5.2 Discovery Workflow Script

```yaml
# .github/workflows/discover-state.yml
name: Discover State Data Source

on:
  workflow_dispatch:
    inputs:
      state_code:
        description: 'Two-letter state code (e.g., TX)'
        required: true
      force_refresh:
        description: 'Force refresh even if already discovered'
        default: false

jobs:
  discover:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Claude Code Discovery
        uses: anthropic/claude-code-action@v1
        with:
          prompt: |
            Research crash data availability for state: ${{ inputs.state_code }}

            Tasks:
            1. Find all public crash data sources (APIs, portals, downloads)
            2. Document the data format and column schema
            3. Assess commercial licensing viability
            4. Generate states/${{ inputs.state_code }}/config.json
            5. Generate states/${{ inputs.state_code }}/research.md

            Do NOT write code to the main app. Only create config files.

      - name: Create PR with findings
        uses: peter-evans/create-pull-request@v5
        with:
          title: "Add ${{ inputs.state_code }} crash data source"
          branch: "discover/${{ inputs.state_code }}"
```

### 5.3 Batch Discovery Script

For systematic discovery of all 50 states:

```python
# scripts/batch_discover.py
import subprocess
import json
from pathlib import Path

STATES = [
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
]

def get_discovered_states():
    registry = Path('states/registry.json')
    if registry.exists():
        return set(json.loads(registry.read_text())['states'].keys())
    return set()

def discover_remaining():
    discovered = get_discovered_states()
    remaining = [s for s in STATES if s not in discovered]

    print(f"Discovered: {len(discovered)}/50")
    print(f"Remaining: {remaining}")

    for state in remaining:
        print(f"\n{'='*60}")
        print(f"Discovering: {state}")
        print('='*60)

        # Trigger GitHub Action
        subprocess.run([
            'gh', 'workflow', 'run', 'discover-state.yml',
            '-f', f'state_code={state}'
        ])

if __name__ == '__main__':
    discover_remaining()
```

---

## 6. Data Normalization Factory

### 6.1 Adapter Configuration Schema

Each state adapter config follows this schema:

```json
{
  "$schema": "https://crash-lens.com/schemas/state-adapter-v1.json",
  "state": {
    "name": "Texas",
    "abbreviation": "TX",
    "fips": "48",
    "dotName": "TxDOT",
    "crashSystem": "CRIS"
  },

  "columnMapping": {
    "ID": "Crash ID",
    "DATE": "Crash Date",
    "TIME": "Crash Time",
    "YEAR": { "derive": "from_date", "source": "Crash Date" },
    "SEVERITY": "Crash Severity",
    "ROUTE": "Street Name",
    "NODE": {
      "derive": "intersection",
      "sources": ["Street Name", "Intersecting Street Name"],
      "separator": " & "
    },
    "X": "Longitude",
    "Y": "Latitude",
    "COLLISION": "Collision Type",
    "WEATHER": "Weather Condition",
    "LIGHT": "Light Condition"
  },

  "severityMapping": {
    "type": "direct",
    "mapping": {
      "K": "K",
      "A": "A",
      "B": "B",
      "C": "C",
      "N": "O",
      "0": "O"
    }
  },

  "booleanFields": {
    "PED": {
      "type": "column_value",
      "source": "Pedestrian Involved",
      "trueValues": ["Y", "Yes", "1", "true"]
    },
    "BIKE": {
      "type": "column_value",
      "source": "Bicycle Involved",
      "trueValues": ["Y", "Yes", "1", "true"]
    },
    "ALCOHOL": {
      "type": "contains",
      "source": "Contributing Factors",
      "pattern": "(?i)alcohol|dwi|dui|intoxicated"
    },
    "SPEED": {
      "type": "contains",
      "source": "Contributing Factors",
      "pattern": "(?i)speed|exceeded|too fast"
    }
  },

  "roadSystemMapping": {
    "IH": "Interstate",
    "US": "Primary",
    "SH": "Primary",
    "FM": "Secondary",
    "RM": "Secondary",
    "CR": "NonVDOT",
    "CITY": "NonVDOT"
  },

  "coordinateTransform": {
    "type": "none",
    "sourceCRS": "EPSG:4326",
    "targetCRS": "EPSG:4326"
  },

  "dateFormats": ["M/D/YYYY", "YYYY-MM-DD", "MM/DD/YYYY"],

  "validation": {
    "requiredColumns": ["Crash ID", "Crash Date", "Longitude", "Latitude"],
    "latitudeRange": [25.8, 36.5],
    "longitudeRange": [-106.6, -93.5]
  }
}
```

### 6.2 Normalization Engine

```javascript
// Pseudocode: Universal normalizer
class UniversalNormalizer {
    constructor(config) {
        this.config = config;
        this.columnMap = this.buildColumnMap(config.columnMapping);
    }

    normalizeRow(row) {
        const normalized = {};

        // Direct mappings
        for (const [target, source] of Object.entries(this.columnMap.direct)) {
            normalized[target] = row[source];
        }

        // Derived fields
        for (const [target, derivation] of Object.entries(this.columnMap.derived)) {
            normalized[target] = this.derive(row, derivation);
        }

        // Severity
        normalized['Crash Severity'] = this.mapSeverity(row);

        // Boolean fields
        for (const [target, config] of Object.entries(this.config.booleanFields)) {
            normalized[target] = this.evaluateBoolean(row, config) ? 'Y' : 'N';
        }

        // Road system
        normalized['SYSTEM'] = this.mapRoadSystem(row);

        // Coordinates
        const coords = this.transformCoordinates(row);
        normalized['x'] = coords.lon;
        normalized['y'] = coords.lat;

        return normalized;
    }

    mapSeverity(row) {
        const config = this.config.severityMapping;

        if (config.type === 'direct') {
            const rawValue = row[this.columnMap.direct['SEVERITY']];
            return config.mapping[rawValue] || 'O';
        }

        if (config.type === 'fromInjuryCounts') {
            // Derive from injury count columns (Colorado pattern)
            if (parseInt(row[config.columns.K]) > 0) return 'K';
            if (parseInt(row[config.columns.A]) > 0) return 'A';
            if (parseInt(row[config.columns.B]) > 0) return 'B';
            if (parseInt(row[config.columns.C]) > 0) return 'C';
            return 'O';
        }
    }
}
```

### 6.3 Validation & Quality Checks

```javascript
class DataValidator {
    validate(normalizedRow, config) {
        const errors = [];
        const warnings = [];

        // Required fields
        for (const field of config.validation.requiredColumns) {
            if (!normalizedRow[field]) {
                errors.push(`Missing required field: ${field}`);
            }
        }

        // Severity value
        if (!['K', 'A', 'B', 'C', 'O'].includes(normalizedRow['Crash Severity'])) {
            errors.push(`Invalid severity: ${normalizedRow['Crash Severity']}`);
        }

        // Coordinate bounds
        const lat = parseFloat(normalizedRow['y']);
        const lon = parseFloat(normalizedRow['x']);

        if (lat && (lat < config.validation.latitudeRange[0] ||
                    lat > config.validation.latitudeRange[1])) {
            warnings.push(`Latitude ${lat} outside expected range`);
        }

        if (lon && (lon < config.validation.longitudeRange[0] ||
                    lon > config.validation.longitudeRange[1])) {
            warnings.push(`Longitude ${lon} outside expected range`);
        }

        // Date parsing
        const date = this.parseDate(normalizedRow['Crash Date'], config.dateFormats);
        if (!date) {
            errors.push(`Unparseable date: ${normalizedRow['Crash Date']}`);
        }

        return { valid: errors.length === 0, errors, warnings };
    }
}
```

---

## 7. Health Monitoring & Self-Healing

### 7.1 Health Check System

```yaml
# .github/workflows/health-check.yml
name: Data Source Health Check

on:
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM UTC
  workflow_dispatch:

jobs:
  health-check:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install requests aiohttp

      - name: Run health checks
        id: health
        run: python scripts/health_check.py

      - name: Update registry status
        run: python scripts/update_registry_status.py

      - name: Commit status updates
        uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "chore: update data source health status"
          file_pattern: states/registry.json

      - name: Create issue for failures
        if: env.FAILED_SOURCES != ''
        uses: actions/github-script@v7
        with:
          script: |
            const failed = process.env.FAILED_SOURCES.split(',');
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: `🚨 Data Source Failure: ${failed.join(', ')}`,
              body: `## Health Check Failure\n\nThe following data sources failed health checks:\n\n${failed.map(s => '- ' + s).join('\n')}\n\n### Next Steps\n1. Check if the API endpoint has moved\n2. Verify authentication requirements haven't changed\n3. Test fallback URLs\n4. Consider triggering self-healing workflow`,
              labels: ['data-source', 'automated', 'urgent']
            });
```

### 7.2 Health Check Script

```python
# scripts/health_check.py
import asyncio
import aiohttp
import json
from datetime import datetime
from pathlib import Path

async def check_arcgis(session, source):
    """Check ArcGIS FeatureServer health"""
    params = {
        'where': '1=1',
        'resultRecordCount': 1,
        'f': 'json'
    }
    try:
        async with session.get(source['url'], params=params, timeout=30) as resp:
            if resp.status == 200:
                data = await resp.json()
                if 'features' in data:
                    return {'status': 'active', 'records': len(data['features'])}
                if 'error' in data:
                    return {'status': 'error', 'message': data['error'].get('message')}
            return {'status': 'degraded', 'httpCode': resp.status}
    except asyncio.TimeoutError:
        return {'status': 'timeout'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

async def check_socrata(session, source):
    """Check Socrata SODA API health"""
    url = f"https://{source['domain']}/resource/{source['datasetId']}.json"
    params = {'$limit': 1}
    try:
        async with session.get(url, params=params, timeout=30) as resp:
            if resp.status == 200:
                data = await resp.json()
                return {'status': 'active', 'records': len(data)}
            return {'status': 'degraded', 'httpCode': resp.status}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

async def check_fars(session, source):
    """Check NHTSA FARS API health"""
    url = "https://crashviewer.nhtsa.dot.gov/CrashAPI/crashes/GetCaseList"
    params = {'states': '51', 'fromYear': '2023', 'toYear': '2023', 'format': 'json'}
    try:
        async with session.get(url, params=params, timeout=30) as resp:
            if resp.status == 200:
                return {'status': 'active'}
            return {'status': 'degraded', 'httpCode': resp.status}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

CHECKERS = {
    'arcgis': check_arcgis,
    'socrata': check_socrata,
    'nhtsa-fars': check_fars,
}

async def run_health_checks():
    registry = json.loads(Path('states/registry.json').read_text())
    results = {}

    async with aiohttp.ClientSession() as session:
        tasks = []
        for state_code, state in registry['states'].items():
            for source in state.get('sources', []):
                checker = CHECKERS.get(source['type'])
                if checker:
                    tasks.append((state_code, source['id'], checker(session, source)))

        for state_code, source_id, task in tasks:
            result = await task
            results[f"{state_code}/{source_id}"] = {
                **result,
                'checkedAt': datetime.utcnow().isoformat() + 'Z'
            }

    return results

if __name__ == '__main__':
    results = asyncio.run(run_health_checks())

    failed = [k for k, v in results.items() if v['status'] != 'active']
    if failed:
        print(f"::set-env name=FAILED_SOURCES::{','.join(failed)}")

    Path('health_results.json').write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))
```

### 7.3 Schema Drift Detection

```python
# scripts/detect_schema_drift.py
def detect_drift(state_code, source_id, sample_data):
    """Compare current API schema against stored signature"""
    registry = load_registry()
    source = get_source(registry, state_code, source_id)

    expected = set(source['schema']['signature'])
    actual = set(sample_data[0].keys()) if sample_data else set()

    missing = expected - actual
    new = actual - expected

    if missing:
        return {
            'drift': True,
            'type': 'missing_columns',
            'columns': list(missing),
            'suggestions': [fuzzy_match(col, new) for col in missing]
        }

    if new:
        return {
            'drift': False,
            'newColumns': list(new),
            'note': 'New columns available for potential mapping'
        }

    return {'drift': False}
```

### 7.4 Self-Healing Workflow

```yaml
# .github/workflows/self-heal.yml
name: Self-Heal Data Source

on:
  issues:
    types: [labeled]

jobs:
  self-heal:
    if: contains(github.event.issue.labels.*.name, 'self-heal')
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Extract state from issue
        id: parse
        run: |
          # Parse state code from issue title
          STATE=$(echo "${{ github.event.issue.title }}" | grep -oP '[A-Z]{2}')
          echo "state=$STATE" >> $GITHUB_OUTPUT

      - name: Run Claude Code repair
        uses: anthropic/claude-code-action@v1
        with:
          prompt: |
            The data source for state ${{ steps.parse.outputs.state }} has failed.

            Issue details:
            ${{ github.event.issue.body }}

            Tasks:
            1. Research if the API endpoint has moved
            2. Search for new URLs or alternative endpoints
            3. Check if authentication requirements changed
            4. Update states/registry.json with new endpoint
            5. Update states/${{ steps.parse.outputs.state }}/config.json if schema changed
            6. Test the new endpoint

            Create a fix and explain what changed.

      - name: Create PR with fix
        uses: peter-evans/create-pull-request@v5
        with:
          title: "fix(${{ steps.parse.outputs.state }}): repair data source connection"
          branch: "fix/${{ steps.parse.outputs.state }}-source"
          body: |
            Automated repair for ${{ steps.parse.outputs.state }} data source.

            Resolves #${{ github.event.issue.number }}
```

### 7.5 Fallback Cascade Logic

```javascript
// Fallback priority for each state
const FALLBACK_CHAIN = {
    // Primary → Fallback 1 → Fallback 2 → FARS (fatal only)
    'VA': ['va-arcgis-primary', 'va-socrata', 'fars-va'],
    'TX': ['tx-cris-api', 'tx-socrata', 'fars-tx'],
    'FL': ['fl-arcgis', 'fl-fdot-gis', 'fars-fl'],
    // ... all states end with FARS as ultimate fallback
};

async function fetchWithFallback(stateCode, options = {}) {
    const chain = FALLBACK_CHAIN[stateCode] || [`fars-${stateCode.toLowerCase()}`];

    for (const sourceId of chain) {
        try {
            const result = await fetchFromSource(sourceId, options);

            if (result.success) {
                if (sourceId.startsWith('fars-')) {
                    console.warn(`[${stateCode}] Using FARS fallback (fatal crashes only)`);
                }
                return { ...result, sourceId, fallback: sourceId !== chain[0] };
            }
        } catch (err) {
            console.error(`[${stateCode}] Source ${sourceId} failed: ${err.message}`);
            continue;
        }
    }

    throw new Error(`All sources exhausted for ${stateCode}`);
}
```

---

## 8. Phased Implementation Schedule

### Phase 1: Foundation (Weeks 1-4)

| Week | Tasks | Deliverables |
|------|-------|-------------|
| 1 | Set up registry infrastructure | `states/registry.json` schema, validation |
| 1 | Implement FARS API integration | P0 source: 50-state fatal crash coverage |
| 2 | Add NYC Open Data | P1 source: explicit commercial license |
| 2 | Add California CCRS | P1 source: open license |
| 3 | Build health check workflow | GitHub Actions, status tracking |
| 3 | Implement fallback cascade | FARS as universal fallback |
| 4 | Legal review of ToS | Document ambiguous states, flag risks |
| 4 | **Milestone: MVP with 3 confirmed commercial sources** | |

### Phase 2: Expansion (Weeks 5-12)

| Week | Tasks | Deliverables |
|------|-------|-------------|
| 5-6 | Add Socrata states (MD, CT, DE, NY, VT) | 5 new P2 sources |
| 7-8 | Add ArcGIS states (FL, MA, IL, IA, LA) | 5 new P2 sources |
| 9-10 | Build adapter factory | Automated normalization for all added states |
| 11-12 | Implement schema drift detection | Proactive monitoring |
| 12 | **Milestone: 15+ states, automated health monitoring** | |

### Phase 3: Scale (Weeks 13-24)

| Week | Tasks | Deliverables |
|------|-------|-------------|
| 13-16 | Claude Code batch discovery | Research remaining states |
| 17-20 | Build adapters for viable states | Configs + normalizers |
| 21-22 | Implement self-healing workflow | Automated repair pipeline |
| 23-24 | Documentation, legal review | Commercial terms documentation |
| 24 | **Milestone: 35+ states, self-healing infrastructure** | |

### Phase 4: Commercial Launch (Weeks 25-36)

| Week | Tasks | Deliverables |
|------|-------|-------------|
| 25-28 | Build public API | REST + GraphQL endpoints |
| 29-32 | Implement usage tracking, billing | Stripe integration |
| 33-36 | SaaS platform for agencies (Model A) | White-label analytics |
| 36 | **Milestone: Commercial product launch** | |

---

## 9. Cost Analysis

### 9.1 Infrastructure Costs (Monthly)

| Component | Option A (Minimal) | Option B (Standard) | Option C (Scale) |
|-----------|-------------------|--------------------|--------------------|
| **Compute** | GitHub Actions (free tier) | AWS Lambda ($20) | ECS/Fargate ($200) |
| **Database** | Supabase free | RDS PostgreSQL ($50) | RDS Multi-AZ ($200) |
| **Storage** | S3 ($5) | S3 + CloudFront ($20) | S3 + CDN ($50) |
| **Monitoring** | GitHub + free tier | Datadog basic ($30) | Full observability ($100) |
| **Total** | **~$5/month** | **~$120/month** | **~$550/month** |

### 9.2 Development Costs

| Phase | Effort | Cost (at $150/hr) |
|-------|--------|-------------------|
| Phase 1 (Foundation) | 120 hours | $18,000 |
| Phase 2 (Expansion) | 200 hours | $30,000 |
| Phase 3 (Scale) | 160 hours | $24,000 |
| Phase 4 (Commercial) | 240 hours | $36,000 |
| **Total** | **720 hours** | **$108,000** |

### 9.3 Legal Costs

| Item | Estimated Cost |
|------|---------------|
| Initial ToS review (50 states) | $5,000 - $15,000 |
| Commercial licensing opinion | $3,000 - $8,000 |
| Template DUA for state partnerships | $2,000 - $5,000 |
| Ongoing compliance (annual) | $5,000 - $10,000 |
| **Total (Year 1)** | **$15,000 - $38,000** |

### 9.4 Revenue Projections (Model B: Data API)

| Tier | Price | Year 1 Customers | Annual Revenue |
|------|-------|-----------------|----------------|
| Developer | $99/month | 50 | $59,400 |
| Professional | $499/month | 20 | $119,760 |
| Enterprise | $2,500/month | 5 | $150,000 |
| **Total** | | | **$329,160** |

---

## 10. Risk Mitigation

### 10.1 Legal Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| State retroactively restricts commercial use | Medium | High | Diversify sources, FARS fallback, provenance tracking |
| DPPA violation (PII exposure) | Low | Critical | Strict de-identification, no PII in product |
| 23 U.S.C. §407 litigation | Low | Medium | Clear disclaimers, no litigation use marketing |
| Copyright claim on data | Very Low | Medium | Use only public domain / licensed sources |

### 10.2 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| API deprecation without notice | Medium | High | Health monitoring, fallback cascade, FARS backup |
| Schema changes break adapters | Medium | Medium | Schema drift detection, self-healing |
| Rate limiting by states | Medium | Low | Caching, respectful fetching, pagination |
| Data quality issues | High | Medium | Validation rules, anomaly detection |

### 10.3 Business Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| LexisNexis competitive response | Medium | Medium | Focus on analytics value-add, not raw data |
| State DOT builds own tool | Low | Medium | Partner model (SaaS for agencies) |
| Free alternatives emerge | Medium | Low | Superior UX, cross-state normalization |

---

## Appendix A: State-by-State Research Template

For each state discovery, create `states/{STATE}/research.md`:

```markdown
# {State Name} Crash Data Research

**Researched:** {Date}
**Researcher:** Claude Code / {Human name}
**Commercial Viability:** {P0/P1/P2/P3/P4}

## Data Sources Identified

### Source 1: {Name}
- **URL:**
- **Type:** Socrata / ArcGIS / REST / CSV
- **Auth:** None / API Key / Account Required
- **Data Range:**
- **Update Frequency:**

## Schema Analysis

| State Column | COL Mapping | Notes |
|--------------|-------------|-------|
| {Column} | {COL.X} | {transformation notes} |

## Licensing Assessment

- **Terms of Service URL:**
- **License Type:** CC0 / CC-BY / Custom / None specified
- **Commercial Use:** Explicit Yes / Explicit No / Ambiguous
- **Restrictions:**
- **Legal Review Needed:** Yes / No

## Integration Recommendation

{Recommendation paragraph}

## Sample Data

{Link to sample CSV or JSON}
```

---

## Appendix B: Adapter Config Generator Prompt

For Claude Code to generate new state adapters:

```
You are generating a StateAdapter config for {STATE_NAME} crash data.

You have been provided:
1. A sample CSV with 100 crash records
2. The state's crash data dictionary
3. The target COL schema (Virginia format)

Generate states/{STATE_CODE}/config.json following the schema in Section 6.1.

Rules:
1. Map all possible columns to COL equivalents
2. Use derivation rules for fields that need transformation
3. Set appropriate boolean field detection patterns
4. Include coordinate validation bounds for this state
5. Document any unmappable fields in comments

After generating, validate by running the normalizer on all 100 sample rows
and confirm zero errors.
```

---

## Approval & Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Technical Lead | | | |
| Legal Counsel | | | |
| Product Owner | | | |
| Executive Sponsor | | | |

---

*Document Version: 1.0*
*Last Updated: February 5, 2026*
*Classification: Internal - Commercial Strategy*
