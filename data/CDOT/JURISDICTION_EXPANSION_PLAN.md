# CRASH LENS — Comprehensive Multi-Jurisdiction Expansion Plan

## For CDOT (Colorado Department of Transportation) & Beyond

**Version:** 1.0
**Date:** February 9, 2026
**Status:** PLANNING ONLY — Not Yet Implemented

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Architecture Audit](#2-current-architecture-audit)
3. [CDOT Organizational Structure](#3-cdot-organizational-structure)
4. [Colorado MPOs & Regional Planning Organizations](#4-colorado-mpos--regional-planning-organizations)
5. [User Persona Matrix](#5-user-persona-matrix)
6. [Hierarchical Jurisdiction Model](#6-hierarchical-jurisdiction-model)
7. [Dynamic Multi-Tier Architecture](#7-dynamic-multi-tier-architecture)
8. [State-Level Configuration System](#8-state-level-configuration-system)
9. [Data Pipeline Expansion](#9-data-pipeline-expansion)
10. [UI/UX Redesign for Multi-Jurisdiction](#10-uiux-redesign-for-multi-jurisdiction)
11. [Automated Jurisdiction Onboarding](#11-automated-jurisdiction-onboarding)
12. [CDOT District Office Implementation](#12-cdot-district-office-implementation)
13. [MPO/Regional Aggregation Engine](#13-mporegional-aggregation-engine)
14. [Statewide View (CDOT HQ)](#14-statewide-view-cdot-hq)
15. [Multi-State Scaling Strategy](#15-multi-state-scaling-strategy)
16. [Database & Storage Strategy](#16-database--storage-strategy)
17. [API & Backend Architecture](#17-api--backend-architecture)
18. [Phased Implementation Roadmap](#18-phased-implementation-roadmap)
19. [Risk Assessment & Mitigations](#19-risk-assessment--mitigations)
20. [Appendix A: Complete Colorado County-to-Region Mapping](#appendix-a-complete-colorado-county-to-region-mapping)
21. [Appendix B: Configuration Schema Reference](#appendix-b-configuration-schema-reference)

---

## 1. Executive Summary

### The Problem

CRASH LENS currently operates as a **single-jurisdiction tool** — one county at a time (Douglas County, CO or Henrico County, VA). However, real-world transportation safety work operates at multiple overlapping scales:

- A **county engineer** needs their county's data
- A **CDOT Region engineer** needs data across 8-15 counties in their region
- An **MPO planner** needs data across the 3-9 counties in their planning area
- A **CDOT HQ analyst** needs statewide data subdivided by their 5 engineering regions
- A **FHWA Division** needs cross-state comparisons

These are not separate tools — they are **different views of the same data** with different aggregation levels.

### The Solution

Build a **hierarchical jurisdiction model** with a **dynamic aggregation engine** that lets any user see crash data at their level — from a single intersection up to the entire state — with automatic roll-up and drill-down capabilities.

### Key Design Principles

1. **Zero-code onboarding** — Adding a new county should require ONLY a config file, not code changes
2. **Hierarchical by nature** — County → Region/District → MPO → State are first-class concepts
3. **Data flows up, context flows down** — Raw data lives at the county level; aggregation is computed dynamically
4. **One tool, many views** — The same CRASH LENS instance serves county engineers, regional planners, and state HQ
5. **Offline-first** — Large CSV datasets work without a backend server; optional API layer for scale

---

## 2. Current Architecture Audit

### What Already Exists (Strengths)

| Component | Status | Location |
|-----------|--------|----------|
| StateAdapter (auto-detect CSV format) | ✅ Working | `states/state_adapter.js` |
| FIPSDatabase (all 50 states + counties) | ✅ Working | `states/fips_database.js` |
| US Counties DB (embedded) | ✅ Working | `states/us_counties_db.js` |
| Colorado column mapping | ✅ Working | `data/CDOT/config.json` |
| Virginia 133 jurisdictions | ✅ Working | `config.json` |
| Colorado 6 jurisdictions (hardcoded) | ✅ Working | `state_adapter.js` |
| Dynamic jurisdiction dropdown | ✅ Working | `app/index.html` |
| Data processing pipeline | ✅ Working | `scripts/process_crash_data.py` |
| CDOT data downloader | ✅ Working | `download_cdot_crash_data.py` |

### What's Missing (Gaps)

| Gap | Impact | Priority |
|-----|--------|----------|
| No region/district concept | Cannot aggregate counties into CDOT regions | P0 - Critical |
| No MPO concept | Cannot group counties into planning organizations | P0 - Critical |
| No statewide view | CDOT HQ cannot see all 64 counties at once | P0 - Critical |
| Single-county data loading | Must reload entire app to switch jurisdictions | P1 - High |
| No multi-county selection | Cannot compare or combine adjacent counties | P1 - High |
| Hardcoded Colorado jurisdictions | Only 6 of 64 CO counties defined | P1 - High |
| No role-based views | Everyone sees the same UI regardless of role | P2 - Medium |
| No automated data pipeline for all counties | Only Douglas County downloads automatically | P2 - Medium |
| No cross-jurisdiction hotspot analysis | Hotspots stop at county borders | P2 - Medium |
| No jurisdiction boundary GeoJSON | Map doesn't show county/region outlines | P3 - Nice to have |

---

## 3. CDOT Organizational Structure

### CDOT Engineering Regions

CDOT divides Colorado into **5 Engineering Regions** plus a headquarters. Each region has a Regional Transportation Director (RTD) and manages highway operations, maintenance, and safety within their geographic area.

```
┌─────────────────────────────────────────────────────┐
│                   CDOT HEADQUARTERS                  │
│              4201 E. Arkansas Ave, Denver             │
│                                                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐             │
│  │ Region 1 │ │ Region 2 │ │ Region 3 │             │
│  │ (Denver  │ │ (Pueblo/ │ │ (Grand   │             │
│  │  Metro)  │ │  SE CO)  │ │ Junction)│             │
│  └──────────┘ └──────────┘ └──────────┘             │
│  ┌──────────┐ ┌──────────┐                           │
│  │ Region 4 │ │ Region 5 │                           │
│  │ (Greeley/│ │ (Durango/│                           │
│  │  NE CO)  │ │  SW CO)  │                           │
│  └──────────┘ └──────────┘                           │
└─────────────────────────────────────────────────────┘
```

### Region 1 — Denver Metro / Central

- **Office:** 2000 S. Holly St., Denver, CO 80222
- **Counties (approximately 10):** Adams, Arapahoe, Boulder, Broomfield, Clear Creek, Denver, Douglas, Gilpin, Jefferson, Summit
- **Key Corridors:** I-25 (Denver Metro), I-70 (Mountain Corridor), I-76, I-225, I-270, US-36, US-6, CO-470, C-470, E-470

### Region 2 — Southeast / Pueblo

- **Office:** 905 Erie Ave., Pueblo, CO 81001
- **Counties (approximately 17):** Baca, Bent, Chaffee, Crowley, Custer, El Paso, Elbert, Fremont, Huerfano, Kiowa, Lake, Las Animas, Lincoln, Otero, Park, Prowers, Pueblo, Teller
- **Key Corridors:** I-25 (south of Denver), US-24, US-50, US-285, US-160, CO-115

### Region 3 — Grand Junction / Western Slope

- **Office:** 222 S. 6th St., Grand Junction, CO 81501
- **Counties (approximately 14):** Delta, Eagle, Garfield, Grand, Gunnison, Hinsdale, Jackson, Mesa, Moffat, Montrose, Ouray, Pitkin, Rio Blanco, Routt, San Miguel
- **Key Corridors:** I-70 (Glenwood Canyon to Utah), US-40, US-50, US-550, CO-82, CO-133

### Region 4 — Greeley / Northeast

- **Office:** 1420 2nd St., Greeley, CO 80631
- **Counties (approximately 12):** Cheyenne, Kit Carson, Larimer, Logan, Morgan, Phillips, Sedgwick, Washington, Weld, Yuma
- **Key Corridors:** I-25 (north of Denver), I-76 (east), US-34, US-85, US-287, CO-14

### Region 5 — Durango / Southwest & San Luis Valley

- **Office:** 3803 N. Main Ave., Durango, CO 81301
- **Counties (approximately 13):** Alamosa, Archuleta, Conejos, Costilla, Dolores, La Plata, Mineral, Montezuma, Rio Grande, Saguache, San Juan
- **Key Corridors:** US-160, US-550, US-285 (south), CO-17, CO-145, CO-149

> **Note:** Some counties may overlap between regions, especially in boundary areas. The exact mapping should be confirmed against the latest CDOT region boundary GIS shapefile available at https://dtdapps.coloradodot.info/otis.

---

## 4. Colorado MPOs & Regional Planning Organizations

Colorado is divided into **15 Transportation Planning Regions (TPRs)**: 5 MPOs (urban) and 10 rural TPRs.

### 5 Metropolitan Planning Organizations (MPOs)

| # | MPO | Abbreviation | Counties Covered |
|---|-----|-------------|-----------------|
| 1 | Denver Regional Council of Governments | DRCOG | Adams, Arapahoe, Boulder, Broomfield, Clear Creek, Denver, Douglas, Gilpin, Jefferson, SW Weld |
| 2 | North Front Range MPO | NFRMPO | Larimer, Weld (partial) |
| 3 | Pikes Peak Area Council of Governments | PPACG | El Paso, Teller |
| 4 | Pueblo Area Council of Governments | PACOG | Pueblo |
| 5 | Grand Valley MPO | GVMPO | Mesa |

### 10 Rural Transportation Planning Regions (TPRs)

| # | TPR Name | Abbreviation | Counties Covered | Administering Organization |
|---|----------|-------------|-----------------|---------------------------|
| 6 | Central Front Range | CFR | Custer, Fremont, Park (+ parts of El Paso, Teller) | Upper Arkansas Area COG (UAACOG) |
| 7 | Eastern | EA | Cheyenne, Elbert, Kit Carson, Lincoln, Logan, Phillips, Sedgwick, Washington, Yuma | Yuma County |
| 8 | Gunnison Valley | GV | Delta, Gunnison, Hinsdale, Montrose, Ouray, San Miguel | Region 10 LEAP |
| 9 | Intermountain | IM | Eagle, Garfield, Lake, Pitkin, Summit | NW CO COG (NWCCOG) |
| 10 | Northwest | NW | Grand, Jackson, Moffat, Rio Blanco, Routt | Town of Fraser |
| 11 | San Luis Valley | SLV | Alamosa, Chaffee, Conejos, Costilla, Mineral, Rio Grande, Saguache | SLV Development Resources Group |
| 12 | South Central | SC | Huerfano, Las Animas | South Central COG (SCCOG) |
| 13 | Southeast | SE | Baca, Bent, Crowley, Kiowa, Otero, Prowers | SE CO Enterprise Development |
| 14 | Southwest | SW | Archuleta, Dolores, La Plata, Montezuma, San Juan | SW CO COG (SWCCOG) |
| 15 | Upper Front Range | UFR | Morgan (+ parts of Larimer, Weld) | CDOT Planning Liaison |

### Key Insight: Overlapping Hierarchies

**CDOT Regions and TPRs/MPOs are NOT the same hierarchy.** They overlap:

```
CDOT Region 1 (Denver Metro)     ←→  DRCOG MPO (mostly overlaps)
                                       + parts of NFRMPO
                                       + Intermountain TPR (Summit)

CDOT Region 2 (Pueblo/SE)        ←→  PPACG MPO (El Paso/Teller)
                                       + PACOG MPO (Pueblo)
                                       + Central Front Range TPR
                                       + Eastern TPR (partial)
                                       + Southeast TPR
                                       + South Central TPR

CDOT Region 4 (Greeley/NE)       ←→  NFRMPO (Larimer/Weld)
                                       + Eastern TPR (partial)
                                       + Upper Front Range TPR
```

**This means our data model MUST support a county belonging to multiple groupings simultaneously.**

---

## 5. User Persona Matrix

### Who Uses This Tool and What Do They Need?

| Persona | Organization Level | Data Scope | Primary Use Cases | View Type |
|---------|-------------------|------------|-------------------|-----------|
| **County Traffic Engineer** | County (e.g., Douglas County) | Single county | Hotspot analysis, CMF selection, grant applications, warrant studies | County View |
| **City Traffic Engineer** | Municipality (e.g., Castle Rock) | Single city within county | City-specific crashes, intersection analysis | City View (filtered) |
| **CDOT Region Engineer** | CDOT Region (e.g., Region 1) | 8-15 counties | Regional safety priorities, corridor analysis across counties, resource allocation | Region View |
| **CDOT Region Traffic Safety Manager** | CDOT Region | 8-15 counties | HSIP project selection, systemic safety, before/after studies | Region View + Hotspots |
| **MPO Transportation Planner** | MPO (e.g., DRCOG) | 3-10 counties | Regional transportation plan, TIP programming, safety targets | MPO View |
| **Rural TPR Coordinator** | TPR | 2-9 counties | Rural safety needs, regional transit plans | TPR View |
| **CDOT HQ Safety Analyst** | Statewide | All 64 counties | Statewide HSIP, Strategic Highway Safety Plan (SHSP), performance targets | State View by Region |
| **CDOT HQ Traffic Engineer** | Statewide | All 64 counties | Systemic safety analysis, policy development | State View by Category |
| **FHWA Division Safety Engineer** | Federal/State | One or more states | HSIP oversight, performance measure review | Multi-State View |
| **Consultant/Researcher** | Varies | Varies | Safety studies, corridor studies, crash modification factors | Custom View |

### View Hierarchy Diagram

```
                    ┌──────────────────────┐
                    │    STATEWIDE VIEW     │
                    │   (CDOT HQ / FHWA)   │
                    │  All 64 counties      │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼──────┐ ┌──────▼───────┐ ┌──────▼───────┐
    │  CDOT REGION   │ │  MPO / TPR   │ │  CORRIDOR    │
    │  VIEW          │ │  VIEW        │ │  VIEW        │
    │  (5 regions)   │ │  (15 TPRs)   │ │  (e.g. I-25) │
    └────────┬───────┘ └──────┬───────┘ └──────┬───────┘
             │                │                │
    ┌────────▼───────────────▼────────────────▼───────┐
    │              COUNTY VIEW                         │
    │           (64 counties)                          │
    │   Douglas, El Paso, Denver, Arapahoe, etc.      │
    └────────────────────┬────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │    CITY / PLACE     │
              │    VIEW (optional)  │
              │  Castle Rock, etc.  │
              └─────────────────────┘
```

---

## 6. Hierarchical Jurisdiction Model

### The Core Data Model

The key insight is that **jurisdictions form a DAG (Directed Acyclic Graph), not a simple tree**. A county can belong to:
- Exactly 1 CDOT Engineering Region
- Exactly 1 TPR/MPO
- Exactly 1 State
- Optionally 1+ corridors

```json
{
  "hierarchyModel": {
    "levels": [
      {
        "id": "state",
        "name": "State",
        "description": "Top-level: entire state",
        "example": "Colorado",
        "parentOf": ["cdot_region", "tpr", "corridor"]
      },
      {
        "id": "cdot_region",
        "name": "CDOT Engineering Region",
        "description": "CDOT's 5 operational regions",
        "example": "Region 1 (Denver Metro)",
        "parentOf": ["county"],
        "siblingOf": ["tpr"]
      },
      {
        "id": "tpr",
        "name": "Transportation Planning Region",
        "description": "15 TPRs (5 MPO + 10 rural)",
        "example": "DRCOG, NFRMPO, Eastern TPR",
        "parentOf": ["county"],
        "siblingOf": ["cdot_region"],
        "subtypes": ["mpo", "rural_tpr"]
      },
      {
        "id": "corridor",
        "name": "Corridor",
        "description": "Major route spanning multiple counties",
        "example": "I-25 (Wyoming to New Mexico)",
        "parentOf": ["county"],
        "crossCuts": ["cdot_region", "tpr"]
      },
      {
        "id": "county",
        "name": "County",
        "description": "Primary data unit - where crash data lives",
        "example": "Douglas County",
        "parentOf": ["city"],
        "belongsTo": ["cdot_region", "tpr", "state"]
      },
      {
        "id": "city",
        "name": "City/Place",
        "description": "Municipalities within counties",
        "example": "Castle Rock, Lone Tree",
        "parentOf": [],
        "belongsTo": ["county"]
      }
    ]
  }
}
```

### Why This Matters

When a CDOT Region 1 engineer opens the tool, they should see:
1. **Dashboard** → Aggregate stats for ALL counties in Region 1
2. **Hotspots** → Top crash locations across ALL Region 1 counties, ranked together
3. **Map** → All Region 1 counties visible, with county boundaries
4. **CMF** → Select any location across any Region 1 county
5. **Grants** → HSIP-eligible locations across the entire region

This requires **dynamic data aggregation** — loading multiple county CSVs and combining them in the browser.

---

## 7. Dynamic Multi-Tier Architecture

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     CRASH LENS APPLICATION                   │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  UI LAYER (index.html)                  │  │
│  │                                                          │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐   │  │
│  │  │ Scope       │  │ View        │  │ Comparison   │   │  │
│  │  │ Selector    │  │ Renderer    │  │ Engine       │   │  │
│  │  │ (Cascading) │  │ (Adaptive)  │  │ (Side-by-    │   │  │
│  │  │             │  │             │  │  side/overlay)│   │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬───────┘   │  │
│  │         │                │                │             │  │
│  │  ┌──────▼────────────────▼────────────────▼───────┐    │  │
│  │  │          AGGREGATION ENGINE (NEW)               │    │  │
│  │  │                                                  │    │  │
│  │  │  ┌────────────┐  ┌──────────┐  ┌────────────┐  │    │  │
│  │  │  │ County     │  │ Region   │  │ State      │  │    │  │
│  │  │  │ Aggregator │  │ Combiner │  │ Roll-up    │  │    │  │
│  │  │  └────────────┘  └──────────┘  └────────────┘  │    │  │
│  │  └──────────────────────┬─────────────────────────┘    │  │
│  │                         │                               │  │
│  │  ┌──────────────────────▼─────────────────────────┐    │  │
│  │  │            DATA LAYER                           │    │  │
│  │  │                                                  │    │  │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │    │  │
│  │  │  │ County   │  │ State    │  │ Hierarchy    │  │    │  │
│  │  │  │ CSV      │  │ Adapter  │  │ Registry     │  │    │  │
│  │  │  │ Loader   │  │ (exist.) │  │ (NEW)        │  │    │  │
│  │  │  └──────────┘  └──────────┘  └──────────────┘  │    │  │
│  │  └────────────────────────────────────────────────┘    │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                CONFIG LAYER (file system)               │  │
│  │                                                          │  │
│  │  config.json          → App settings, API keys           │  │
│  │  states/{state}/      → State-specific configs           │  │
│  │  data/{STATE_DIR}/    → State crash data CSVs            │  │
│  │  hierarchy.json       → Region/MPO/County relationships  │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### New Component: Hierarchy Registry

This is the **single source of truth** for which counties belong to which regions, MPOs, and TPRs.

```javascript
// Proposed: hierarchy_registry.js

const HierarchyRegistry = (() => {
    'use strict';

    // Loaded from hierarchy.json at startup
    let hierarchyData = null;

    return {
        /**
         * Load hierarchy config for a state
         * @param {string} stateFips - e.g., '08' for Colorado
         */
        async load(stateFips) {
            const resp = await fetch(`states/${stateFips}/hierarchy.json`);
            hierarchyData = await resp.json();
        },

        /**
         * Get all counties in a CDOT region
         * @param {string} regionId - e.g., 'region_1'
         * @returns {string[]} Array of county FIPS codes
         */
        getCountiesInRegion(regionId) { /* ... */ },

        /**
         * Get all counties in an MPO/TPR
         * @param {string} tprId - e.g., 'drcog', 'eastern_tpr'
         * @returns {string[]} Array of county FIPS codes
         */
        getCountiesInTPR(tprId) { /* ... */ },

        /**
         * Get all groupings a county belongs to
         * @param {string} countyFips - e.g., '035' for Douglas
         * @returns {Object} { cdotRegion, tpr, corridors[] }
         */
        getCountyMemberships(countyFips) { /* ... */ },

        /**
         * Get all regions for the state
         * @returns {Object[]} Array of region definitions
         */
        getAllRegions() { /* ... */ },

        /**
         * Get all TPRs/MPOs for the state
         * @returns {Object[]}
         */
        getAllTPRs() { /* ... */ },

        /**
         * Get counties that share a corridor
         * @param {string} corridorId - e.g., 'I-25'
         * @returns {string[]} Array of county FIPS codes
         */
        getCountiesOnCorridor(corridorId) { /* ... */ }
    };
})();
```

### New Component: Aggregation Engine

Handles combining data from multiple counties.

```javascript
// Proposed: aggregation_engine.js

const AggregationEngine = (() => {
    'use strict';

    // Cache of loaded county data
    const countyDataCache = new Map(); // countyFips → crashRows[]

    return {
        /**
         * Load crash data for a single county
         * Returns cached if already loaded
         */
        async loadCounty(countyFips, stateDataDir) { /* ... */ },

        /**
         * Load and combine crash data for multiple counties
         * Used when viewing a region/MPO/state
         */
        async loadMultipleCounties(countyFipsList, stateDataDir) { /* ... */ },

        /**
         * Build aggregates across multiple counties
         * Returns same structure as crashState.aggregates but combined
         */
        buildMultiCountyAggregates(combinedRows) { /* ... */ },

        /**
         * Build per-county breakdowns within a multi-county view
         * Returns { countyFips: { aggregates } } for comparison
         */
        buildPerCountyBreakdowns(combinedRows) { /* ... */ },

        /**
         * Get cross-county hotspots (rank locations across all loaded counties)
         */
        getCrossCountyHotspots(combinedRows, topN) { /* ... */ },

        /**
         * Memory management: evict least-recently-used county data
         */
        evictCache(maxCounties) { /* ... */ }
    };
})();
```

---

## 8. State-Level Configuration System

### Proposed Directory Structure

```
states/
├── state_adapter.js              # Existing: CSV format detection & normalization
├── fips_database.js              # Existing: All US states & counties
├── us_counties_db.js             # Existing: Embedded county data
├── hierarchy_registry.js         # NEW: Region/MPO/TPR relationships
├── aggregation_engine.js         # NEW: Multi-county data combining
│
├── 08/                           # Colorado (by FIPS code)
│   ├── config.json               # State config (move from data/CDOT/config.json)
│   ├── hierarchy.json            # NEW: Region/MPO/county mappings
│   ├── regions.geojson           # NEW: CDOT region boundaries
│   ├── counties.geojson          # NEW: County boundaries (from Census)
│   ├── tpr_boundaries.geojson    # NEW: TPR/MPO boundaries
│   └── corridors.json            # NEW: Major corridor definitions
│
├── 51/                           # Virginia (by FIPS code)
│   ├── config.json               # Existing (moved from states/virginia/)
│   ├── hierarchy.json            # NEW: VDOT district/MPO mappings
│   ├── regions.geojson           # VDOT district boundaries
│   └── corridors.json            # Major corridor definitions
│
└── template/                     # NEW: Template for new states
    ├── config.json.template
    ├── hierarchy.json.template
    └── README.md                 # Instructions for onboarding a new state
```

### Colorado hierarchy.json (Proposed Schema)

```json
{
  "state": {
    "fips": "08",
    "name": "Colorado",
    "abbreviation": "CO"
  },

  "regionType": {
    "label": "CDOT Engineering Region",
    "labelPlural": "CDOT Engineering Regions",
    "shortLabel": "Region",
    "description": "CDOT's 5 operational engineering regions"
  },

  "regions": {
    "region_1": {
      "id": "region_1",
      "name": "Region 1",
      "fullName": "CDOT Region 1 — Denver Metro / Central",
      "office": "2000 S. Holly St., Denver, CO 80222",
      "counties": ["001", "005", "013", "014", "019", "031", "035", "047", "059", "117"],
      "countyNames": ["Adams", "Arapahoe", "Boulder", "Broomfield", "Clear Creek", "Denver", "Douglas", "Gilpin", "Jefferson", "Summit"],
      "mapCenter": [39.65, -105.15],
      "mapZoom": 9,
      "keyCorridors": ["I-25", "I-70", "I-76", "I-225", "I-270", "US-36", "US-6", "CO-470"]
    },
    "region_2": {
      "id": "region_2",
      "name": "Region 2",
      "fullName": "CDOT Region 2 — Southeast / Pueblo",
      "office": "905 Erie Ave., Pueblo, CO 81001",
      "counties": ["003", "011", "015", "025", "027", "041", "039", "043", "055", "061", "065", "071", "073", "089", "093", "099", "101"],
      "countyNames": ["Baca", "Bent", "Chaffee", "Crowley", "Custer", "El Paso", "Elbert", "Fremont", "Huerfano", "Kiowa", "Lake", "Las Animas", "Lincoln", "Otero", "Park", "Prowers", "Pueblo", "Teller"],
      "mapCenter": [38.5, -104.7],
      "mapZoom": 8,
      "keyCorridors": ["I-25", "US-24", "US-50", "US-285", "US-160"]
    },
    "region_3": {
      "id": "region_3",
      "name": "Region 3",
      "fullName": "CDOT Region 3 — Grand Junction / Western Slope",
      "office": "222 S. 6th St., Grand Junction, CO 81501",
      "counties": ["029", "037", "045", "049", "051", "053", "057", "077", "081", "085", "091", "097", "107", "113"],
      "countyNames": ["Delta", "Eagle", "Garfield", "Grand", "Gunnison", "Hinsdale", "Jackson", "Mesa", "Moffat", "Montrose", "Ouray", "Pitkin", "Rio Blanco", "Routt", "San Miguel"],
      "mapCenter": [39.2, -107.5],
      "mapZoom": 8,
      "keyCorridors": ["I-70", "US-40", "US-50", "US-550", "CO-82"]
    },
    "region_4": {
      "id": "region_4",
      "name": "Region 4",
      "fullName": "CDOT Region 4 — Greeley / Northeast",
      "office": "1420 2nd St., Greeley, CO 80631",
      "counties": ["017", "063", "069", "075", "087", "095", "115", "121", "123"],
      "countyNames": ["Cheyenne", "Kit Carson", "Larimer", "Logan", "Morgan", "Phillips", "Sedgwick", "Washington", "Weld", "Yuma"],
      "mapCenter": [40.3, -104.5],
      "mapZoom": 8,
      "keyCorridors": ["I-25", "I-76", "US-34", "US-85", "US-287"]
    },
    "region_5": {
      "id": "region_5",
      "name": "Region 5",
      "fullName": "CDOT Region 5 — Durango / Southwest & San Luis Valley",
      "office": "3803 N. Main Ave., Durango, CO 81301",
      "counties": ["003", "007", "021", "023", "033", "067", "079", "083", "105", "109", "111"],
      "countyNames": ["Alamosa", "Archuleta", "Conejos", "Costilla", "Dolores", "La Plata", "Mineral", "Montezuma", "Rio Grande", "Saguache", "San Juan"],
      "mapCenter": [37.5, -106.5],
      "mapZoom": 8,
      "keyCorridors": ["US-160", "US-550", "US-285", "CO-17", "CO-145"]
    }
  },

  "tprType": {
    "label": "Transportation Planning Region",
    "labelPlural": "Transportation Planning Regions (TPRs)",
    "shortLabel": "TPR"
  },

  "tprs": {
    "drcog": {
      "id": "drcog",
      "name": "DRCOG",
      "fullName": "Denver Regional Council of Governments",
      "type": "mpo",
      "counties": ["001", "005", "013", "014", "019", "031", "035", "047", "059"],
      "countyNames": ["Adams", "Arapahoe", "Boulder", "Broomfield", "Clear Creek", "Denver", "Douglas", "Gilpin", "Jefferson"],
      "partialCounties": { "123": "Southwest Weld County" },
      "mapCenter": [39.74, -104.99],
      "mapZoom": 10,
      "website": "https://drcog.org"
    },
    "nfrmpo": {
      "id": "nfrmpo",
      "name": "NFRMPO",
      "fullName": "North Front Range MPO",
      "type": "mpo",
      "counties": ["069", "123"],
      "countyNames": ["Larimer", "Weld"],
      "mapCenter": [40.45, -105.0],
      "mapZoom": 10,
      "website": "https://nfrmpo.org"
    },
    "ppacg": {
      "id": "ppacg",
      "name": "PPACG",
      "fullName": "Pikes Peak Area Council of Governments",
      "type": "mpo",
      "counties": ["041", "119"],
      "countyNames": ["El Paso", "Teller"],
      "mapCenter": [38.83, -104.82],
      "mapZoom": 10,
      "website": "https://ppacg.org"
    },
    "pacog": {
      "id": "pacog",
      "name": "PACOG",
      "fullName": "Pueblo Area Council of Governments",
      "type": "mpo",
      "counties": ["101"],
      "countyNames": ["Pueblo"],
      "mapCenter": [38.25, -104.61],
      "mapZoom": 11,
      "website": "https://pacog.net"
    },
    "gvmpo": {
      "id": "gvmpo",
      "name": "GVMPO",
      "fullName": "Grand Valley MPO",
      "type": "mpo",
      "counties": ["077"],
      "countyNames": ["Mesa"],
      "mapCenter": [39.06, -108.55],
      "mapZoom": 11
    },
    "central_front_range": {
      "id": "central_front_range",
      "name": "Central Front Range TPR",
      "fullName": "Central Front Range Transportation Planning Region",
      "type": "rural_tpr",
      "counties": ["027", "043", "093"],
      "countyNames": ["Custer", "Fremont", "Park"],
      "partialCounties": { "041": "Part of El Paso", "119": "Part of Teller" },
      "adminOrg": "Upper Arkansas Area COG (UAACOG)"
    },
    "eastern": {
      "id": "eastern",
      "name": "Eastern TPR",
      "fullName": "Eastern Transportation Planning Region",
      "type": "rural_tpr",
      "counties": ["017", "039", "063", "073", "075", "095", "115", "121", "125"],
      "countyNames": ["Cheyenne", "Elbert", "Kit Carson", "Lincoln", "Logan", "Phillips", "Sedgwick", "Washington", "Yuma"],
      "adminOrg": "Yuma County"
    },
    "gunnison_valley": {
      "id": "gunnison_valley",
      "name": "Gunnison Valley TPR",
      "fullName": "Gunnison Valley Transportation Planning Region",
      "type": "rural_tpr",
      "counties": ["029", "051", "053", "085", "091", "113"],
      "countyNames": ["Delta", "Gunnison", "Hinsdale", "Montrose", "Ouray", "San Miguel"],
      "adminOrg": "Region 10 LEAP"
    },
    "intermountain": {
      "id": "intermountain",
      "name": "Intermountain TPR",
      "fullName": "Intermountain Transportation Planning Region",
      "type": "rural_tpr",
      "counties": ["037", "045", "065", "097", "117"],
      "countyNames": ["Eagle", "Garfield", "Lake", "Pitkin", "Summit"],
      "adminOrg": "NW CO COG (NWCCOG)"
    },
    "northwest": {
      "id": "northwest",
      "name": "Northwest TPR",
      "fullName": "Northwest Transportation Planning Region",
      "type": "rural_tpr",
      "counties": ["049", "057", "081", "103", "107"],
      "countyNames": ["Grand", "Jackson", "Moffat", "Rio Blanco", "Routt"],
      "adminOrg": "Town of Fraser"
    },
    "san_luis_valley": {
      "id": "san_luis_valley",
      "name": "San Luis Valley TPR",
      "fullName": "San Luis Valley Transportation Planning Region",
      "type": "rural_tpr",
      "counties": ["003", "015", "021", "023", "079", "105", "109"],
      "countyNames": ["Alamosa", "Chaffee", "Conejos", "Costilla", "Mineral", "Rio Grande", "Saguache"],
      "adminOrg": "SLV Development Resources Group"
    },
    "south_central": {
      "id": "south_central",
      "name": "South Central TPR",
      "fullName": "South Central Transportation Planning Region",
      "type": "rural_tpr",
      "counties": ["055", "071"],
      "countyNames": ["Huerfano", "Las Animas"],
      "adminOrg": "South Central COG (SCCOG)"
    },
    "southeast": {
      "id": "southeast",
      "name": "Southeast TPR",
      "fullName": "Southeast Transportation Planning Region",
      "type": "rural_tpr",
      "counties": ["009", "011", "025", "061", "089", "099"],
      "countyNames": ["Baca", "Bent", "Crowley", "Kiowa", "Otero", "Prowers"],
      "adminOrg": "SE CO Enterprise Development (SECED)"
    },
    "southwest": {
      "id": "southwest",
      "name": "Southwest TPR",
      "fullName": "Southwest Transportation Planning Region",
      "type": "rural_tpr",
      "counties": ["007", "033", "067", "083", "111"],
      "countyNames": ["Archuleta", "Dolores", "La Plata", "Montezuma", "San Juan"],
      "adminOrg": "SW CO COG (SWCCOG)"
    },
    "upper_front_range": {
      "id": "upper_front_range",
      "name": "Upper Front Range TPR",
      "fullName": "Upper Front Range Transportation Planning Region",
      "type": "rural_tpr",
      "counties": ["087"],
      "countyNames": ["Morgan"],
      "partialCounties": { "069": "Part of Larimer", "123": "Part of Weld" },
      "adminOrg": "CDOT Planning Liaison"
    }
  },

  "corridors": {
    "I-25": {
      "name": "I-25 Corridor",
      "description": "Primary north-south interstate through Colorado",
      "counties": ["071", "055", "101", "041", "035", "005", "031", "001", "069", "123"],
      "regions": ["region_5", "region_2", "region_1", "region_4"],
      "length_miles": 300
    },
    "I-70": {
      "name": "I-70 Corridor",
      "description": "Primary east-west interstate through Colorado",
      "counties": ["063", "073", "039", "005", "031", "059", "019", "117", "037", "045", "077"],
      "regions": ["region_4", "region_2", "region_1", "region_3"],
      "length_miles": 451
    },
    "I-76": {
      "name": "I-76 Corridor",
      "description": "Northeast diagonal interstate",
      "counties": ["001", "123", "087", "075", "095"],
      "regions": ["region_1", "region_4"],
      "length_miles": 187
    },
    "US-285": {
      "name": "US-285 Corridor",
      "description": "North-south route through central Colorado mountains",
      "counties": ["059", "093", "015", "109", "105"],
      "regions": ["region_1", "region_2", "region_5"],
      "length_miles": 305
    }
  }
}
```

---

## 9. Data Pipeline Expansion

### Current Pipeline (Single County)

```
CDOT Excel File
    → download_cdot_crash_data.py (extract one county)
        → scripts/process_crash_data.py (normalize, validate, split)
            → data/CDOT/douglas_all_roads.csv
            → data/CDOT/douglas_county_roads.csv
            → data/CDOT/douglas_no_interstate.csv
```

### Proposed Pipeline (Multi-County / Statewide)

```
CDOT Statewide Data Source
    │
    ▼
┌─────────────────────────────────────────┐
│  STAGE 1: DOWNLOAD                       │
│  download_state_crash_data.py            │
│                                           │
│  Options:                                 │
│  --state colorado                         │
│  --scope statewide        (all counties) │
│  --scope region --region 1 (Region 1)    │
│  --scope county --county douglas         │
│  --scope mpo --mpo drcog  (DRCOG area)  │
│  --years 2021 2022 2023 2024             │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  STAGE 2: SPLIT BY COUNTY               │
│  split_by_jurisdiction.py                │
│                                           │
│  Input: statewide CSV                     │
│  Output: Per-county CSVs                  │
│                                           │
│  data/CDOT/counties/                      │
│    ├── adams_all_roads.csv                │
│    ├── adams_county_roads.csv             │
│    ├── adams_no_interstate.csv            │
│    ├── arapahoe_all_roads.csv             │
│    ├── ...                                │
│    ├── douglas_all_roads.csv              │
│    ├── ...                                │
│    └── yuma_all_roads.csv                 │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  STAGE 3: NORMALIZE & VALIDATE           │
│  process_crash_data.py (existing)        │
│                                           │
│  For each county:                         │
│  - Auto-detect state format              │
│  - Normalize to internal format          │
│  - Validate coordinates                  │
│  - Fill missing geocodes                 │
│  - Split by road type                    │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  STAGE 4: PRE-AGGREGATE (optional)       │
│  pre_aggregate.py (NEW)                  │
│                                           │
│  Build summary JSONs for fast loading:   │
│  data/CDOT/aggregates/                    │
│    ├── region_1_summary.json             │
│    ├── region_2_summary.json             │
│    ├── drcog_summary.json                │
│    ├── statewide_summary.json            │
│    └── county_summaries.json             │
│                                           │
│  Each summary contains:                   │
│  - Total crashes by year, severity       │
│  - EPDO scores                           │
│  - Top hotspots                          │
│  - Trend data                            │
│  (So the UI can show dashboards without  │
│   loading all raw CSVs)                  │
└─────────────────────────────────────────┘
```

### Data Directory Restructure

```
data/
├── CDOT/                          # Colorado state data
│   ├── config.json                # State-specific config (existing)
│   ├── source_manifest.json       # Data source tracking (existing)
│   │
│   ├── counties/                  # Per-county CSVs (NEW structure)
│   │   ├── adams/
│   │   │   ├── all_roads.csv
│   │   │   ├── county_roads.csv
│   │   │   └── no_interstate.csv
│   │   ├── arapahoe/
│   │   │   ├── all_roads.csv
│   │   │   ├── county_roads.csv
│   │   │   └── no_interstate.csv
│   │   ├── douglas/
│   │   │   ├── all_roads.csv      # (existing files moved here)
│   │   │   ├── county_roads.csv
│   │   │   └── no_interstate.csv
│   │   └── .../                   # All 64 counties
│   │
│   ├── aggregates/                # Pre-computed summaries (NEW)
│   │   ├── statewide.json
│   │   ├── by_region/
│   │   │   ├── region_1.json
│   │   │   ├── region_2.json
│   │   │   └── ...
│   │   ├── by_tpr/
│   │   │   ├── drcog.json
│   │   │   ├── nfrmpo.json
│   │   │   └── ...
│   │   └── by_county/
│   │       ├── adams.json
│   │       ├── douglas.json
│   │       └── ...
│   │
│   └── boundaries/                # GeoJSON boundaries (NEW)
│       ├── counties.geojson
│       ├── regions.geojson
│       └── tprs.geojson
│
├── VA/                            # Virginia state data (restructured)
│   ├── counties/
│   │   ├── henrico/
│   │   │   ├── all_roads.csv
│   │   │   └── ...
│   │   └── .../
│   ├── aggregates/
│   └── boundaries/
│
└── README.md                      # Data directory documentation
```

### GitHub Actions Workflow Expansion

```yaml
# .github/workflows/download_crash_data.yml (proposed)

name: Download Crash Data

on:
  schedule:
    - cron: '0 6 * * 1'  # Every Monday at 6 AM UTC
  workflow_dispatch:
    inputs:
      state:
        description: 'State to download'
        required: true
        default: 'colorado'
        type: choice
        options: [colorado, virginia]
      scope:
        description: 'Download scope'
        required: true
        default: 'county'
        type: choice
        options: [county, region, statewide]
      target:
        description: 'County/region name (for county/region scope)'
        required: false
        default: 'douglas'

jobs:
  download:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Download crash data
        run: |
          python download_state_crash_data.py \
            --state ${{ inputs.state }} \
            --scope ${{ inputs.scope }} \
            --target ${{ inputs.target }}

      - name: Process and split data
        run: |
          python scripts/process_crash_data.py \
            --state ${{ inputs.state }} \
            --scope ${{ inputs.scope }}

      - name: Pre-aggregate summaries
        run: |
          python scripts/pre_aggregate.py \
            --state ${{ inputs.state }}

      - name: Commit and push
        run: |
          git add data/
          git commit -m "Update ${{ inputs.state }} crash data (${{ inputs.scope }})"
          git push
```

---

## 10. UI/UX Redesign for Multi-Jurisdiction

### Scope Selector (New Primary Navigation Element)

Replace the current simple jurisdiction dropdown with a **cascading scope selector**:

```
┌─────────────────────────────────────────────────────────┐
│  CRASH LENS — Colorado Crash Analysis Tool               │
│                                                           │
│  ┌─ Scope ──────────────────────────────────────────┐   │
│  │                                                    │   │
│  │  State: [Colorado ▼]                               │   │
│  │                                                    │   │
│  │  View Level: ○ Statewide                           │   │
│  │              ● CDOT Region  [Region 1 ▼]           │   │
│  │              ○ MPO/TPR      [DRCOG ▼]              │   │
│  │              ○ County       [Douglas County ▼]     │   │
│  │              ○ Corridor     [I-25 ▼]               │   │
│  │              ○ Custom       [Select Counties...]   │   │
│  │                                                    │   │
│  │  Road Filter: [All Roads ▼]                        │   │
│  │  Date Range:  [2021-01-01] to [2025-12-31]        │   │
│  │                                                    │   │
│  └────────────────────────────────────────────────────┘   │
│                                                           │
│  [Dashboard] [Analysis] [Map] [Hotspots] [CMF] ...       │
└─────────────────────────────────────────────────────────┘
```

### Adaptive Behavior by Scope Level

| Feature | County View | Region View | State View |
|---------|------------|-------------|------------|
| Dashboard | Single county stats | Region aggregate + per-county breakdown | Statewide + per-region breakdown |
| Map | County boundary, all crashes | Region boundary, county boundaries, crashes | State map, region coloring, county boundaries |
| Hotspots | Top locations in county | Top locations across region, flagged by county | Top locations statewide, grouped by region |
| CMF | Select intersection in county | Select intersection across any county in region | Select intersection anywhere in state |
| AI Assistant | County context | Region context (which counties, cross-county patterns) | Statewide context (regional comparisons) |
| Grants | County HSIP ranking | Regional HSIP project prioritization | Statewide HSIP allocation by region |

### County-Level View (Current, Enhanced)

```
┌──────────────────────────────────────────────────────────┐
│ Douglas County — CRASH LENS                               │
│ CDOT Region 1 │ DRCOG MPO                                │
│                                                            │
│ ┌────────────────────────────────────────────────────┐    │
│ │ DASHBOARD                                          │    │
│ │                                                    │    │
│ │  Total Crashes: 12,456    Fatal (K): 42            │    │
│ │  EPDO Score: 84,221       Serious (A): 187         │    │
│ │  5-Year Trend: ↑ 3.2%     KA Rate: 1.84%          │    │
│ │                                                    │    │
│ │  [Severity Pie] [Trend Line] [Collision Types]     │    │
│ └────────────────────────────────────────────────────┘    │
│                                                            │
│ Context: ℹ️ Viewing Douglas County (1 of 10 counties in    │
│ Region 1). Switch to [Region View] to see all Region 1.   │
└──────────────────────────────────────────────────────────┘
```

### Region-Level View (New)

```
┌──────────────────────────────────────────────────────────┐
│ CDOT Region 1 (Denver Metro) — CRASH LENS                 │
│ 10 Counties │ Population: ~3.2M                           │
│                                                            │
│ ┌────────────────────────────────────────────────────┐    │
│ │ REGION DASHBOARD                                   │    │
│ │                                                    │    │
│ │  Region Totals:  85,234 crashes │ 312 fatal         │    │
│ │  EPDO Score:     621,445                            │    │
│ │                                                    │    │
│ │  ┌─ Per-County Breakdown ──────────────────────┐   │    │
│ │  │ County      │ Crashes │ Fatal │ EPDO   │ %  │   │    │
│ │  │─────────────┼─────────┼───────┼────────┼────│   │    │
│ │  │ Denver      │ 24,521  │  98   │ 182K   │ 29%│   │    │
│ │  │ Arapahoe    │ 18,432  │  67   │ 134K   │ 22%│   │    │
│ │  │ Jefferson   │ 14,876  │  52   │ 108K   │ 17%│   │    │
│ │  │ Adams       │ 12,345  │  48   │  92K   │ 14%│   │    │
│ │  │ Douglas     │  8,234  │  28   │  61K   │ 10%│   │    │
│ │  │ Boulder     │  4,567  │  12   │  34K   │  5%│   │    │
│ │  │ Others (4)  │  2,259  │   7   │  10K   │  3%│   │    │
│ │  └─────────────────────────────────────────────┘   │    │
│ │                                                    │    │
│ │  [Regional Heatmap] [County Comparison Bar Chart]  │    │
│ │  [Click any county to drill down]                  │    │
│ └────────────────────────────────────────────────────┘    │
│                                                            │
│ ┌────────────────────────────────────────────────────┐    │
│ │ CROSS-COUNTY HOTSPOTS (Top 20 across Region 1)    │    │
│ │                                                    │    │
│ │  1. I-25 & CO-470 (Douglas)     EPDO: 4,231       │    │
│ │  2. I-70 & Wadsworth (Jefferson) EPDO: 3,876       │    │
│ │  3. Colfax & Federal (Denver)   EPDO: 3,654       │    │
│ │  ... ranked across ALL 10 counties                 │    │
│ └────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

### Statewide View (New)

```
┌──────────────────────────────────────────────────────────┐
│ Colorado Statewide — CRASH LENS                           │
│ 5 CDOT Regions │ 64 Counties │ All Roads                  │
│                                                            │
│ ┌────────────────────────────────────────────────────┐    │
│ │ STATEWIDE DASHBOARD                                │    │
│ │                                                    │    │
│ │  Total: 142,567 crashes │ 698 fatal │ EPDO: 1.2M   │    │
│ │                                                    │    │
│ │  ┌─ By CDOT Region ───────────────────────────┐   │    │
│ │  │ Region   │ Crashes │ Fatal │ EPDO    │ %    │   │    │
│ │  │──────────┼─────────┼───────┼─────────┼──────│   │    │
│ │  │ Region 1 │  85,234 │  312  │ 621K    │  60% │   │    │
│ │  │ Region 2 │  28,456 │  178  │ 284K    │  20% │   │    │
│ │  │ Region 4 │  15,234 │   98  │ 156K    │  11% │   │    │
│ │  │ Region 3 │   8,432 │   67  │  89K    │   6% │   │    │
│ │  │ Region 5 │   5,211 │   43  │  52K    │   4% │   │    │
│ │  └────────────────────────────────────────────┘   │    │
│ │                                                    │    │
│ │  [CO State Map with Region Coloring]               │    │
│ │  [Click any region to drill down]                  │    │
│ │                                                    │    │
│ │  Toggle: [By Region] [By MPO/TPR] [By Corridor]  │    │
│ └────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

---

## 11. Automated Jurisdiction Onboarding

### Zero-Code Onboarding Pipeline

The goal: to add a new county (e.g., El Paso County), the admin runs ONE command and the county appears in the tool.

```
┌──────────────────────────────────────────────────────────────┐
│                  AUTOMATED ONBOARDING FLOW                    │
│                                                                │
│  STEP 1: Admin runs command                                   │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  python onboard_jurisdiction.py \                       │   │
│  │    --state colorado \                                   │   │
│  │    --county "El Paso" \                                 │   │
│  │    --fips 041                                           │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  STEP 2: Script automatically:                                │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  1. Validates county exists in FIPSDatabase             │   │
│  │  2. Downloads crash data from CDOT source               │   │
│  │  3. Filters for El Paso County only                     │   │
│  │  4. Normalizes using StateAdapter                       │   │
│  │  5. Splits into road-type CSVs                          │   │
│  │  6. Generates pre-aggregated summary JSON               │   │
│  │  7. Updates hierarchy.json with county→region mapping   │   │
│  │  8. Fetches county boundary GeoJSON from Census         │   │
│  │  9. Updates data manifest                               │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  STEP 3: County appears in UI automatically                   │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  - App reads hierarchy.json → finds new county          │   │
│  │  - Dropdown shows "El Paso County"                      │   │
│  │  - Region 2 view now includes El Paso data              │   │
│  │  - PPACG MPO view now includes El Paso data             │   │
│  │  - State totals updated automatically                   │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  NO CODE CHANGES REQUIRED.                                    │
└──────────────────────────────────────────────────────────────┘
```

### onboard_jurisdiction.py (Proposed Script)

```python
"""
Automated jurisdiction onboarding script.

Usage:
    # Onboard a single county
    python onboard_jurisdiction.py --state colorado --county "El Paso"

    # Onboard an entire CDOT region (all counties)
    python onboard_jurisdiction.py --state colorado --region 2

    # Onboard all counties in a state
    python onboard_jurisdiction.py --state colorado --all

    # Onboard a state that doesn't exist yet
    python onboard_jurisdiction.py --state texas --setup
"""

# Key functions (pseudocode):
#
# def onboard_county(state, county_name_or_fips):
#     1. Look up county in FIPS database
#     2. Check if data already exists
#     3. Download crash data (state-specific downloader)
#     4. Process through pipeline
#     5. Update hierarchy.json
#     6. Fetch boundary GeoJSON
#     7. Generate summary statistics
#     8. Update manifest
#
# def onboard_region(state, region_id):
#     1. Look up all counties in region from hierarchy.json
#     2. For each county: onboard_county()
#     3. Generate region-level aggregate
#
# def setup_new_state(state_name):
#     1. Create state directory structure
#     2. Generate config.json template
#     3. Generate hierarchy.json template
#     4. Populate FIPS data from database
#     5. Prompt user for data source configuration
```

### Dynamic County Discovery

For states where we don't have a pre-built hierarchy, the tool can **auto-discover** counties from the crash data itself:

```javascript
// Auto-discovery from CSV data
function discoverJurisdictions(crashRows) {
    const counties = new Map();

    for (const row of crashRows) {
        const countyName = row['Physical Juris Name'] || row['County'] || '';
        if (countyName && !counties.has(countyName)) {
            // Calculate centroid from crash coordinates
            const crashes = crashRows.filter(r =>
                (r['Physical Juris Name'] || r['County']) === countyName
            );
            const avgLat = crashes.reduce((s, r) => s + (parseFloat(r.y) || 0), 0) / crashes.length;
            const avgLon = crashes.reduce((s, r) => s + (parseFloat(r.x) || 0), 0) / crashes.length;

            counties.set(countyName, {
                name: countyName,
                crashCount: crashes.length,
                centroid: [avgLat, avgLon],
                autoDiscovered: true
            });
        }
    }

    return counties;
}
```

---

## 12. CDOT District Office Implementation

### Configuration for CDOT Region-Based View

Each CDOT region gets a dedicated configuration section that defines:

1. **Geographic scope** — Which counties are included
2. **Key corridors** — Which routes are priorities for the region
3. **Office info** — For display in UI headers
4. **Performance targets** — Region-specific safety goals (if different from state)
5. **Data sources** — Any region-specific supplemental data

### Region View Features (Specific to CDOT)

#### A. Regional Dashboard
- Aggregate crash statistics for all counties in the region
- Per-county bar chart comparison
- Year-over-year trend by county
- Regional safety performance vs. targets

#### B. Regional Map
- Region boundary outline
- County boundaries within region
- Color-coded counties by crash rate or EPDO score
- Click county to drill down
- Corridor highlighting (e.g., highlight all of I-25 through Region 1)

#### C. Regional Hotspots
- Cross-county hotspot ranking
- "This intersection in Douglas County is the #3 worst in all of Region 1"
- Filter by route (all I-25 hotspots across region)
- Filter by crash type (all pedestrian hotspots across region)

#### D. Regional HSIP Programming
- Project ranking across all counties
- Cost-benefit analysis at region level
- Budget allocation recommendations by county
- Systemic safety analysis (e.g., all curves across Region 1)

#### E. Region-Level AI Assistant
- "Compare Douglas County vs. Arapahoe County pedestrian safety"
- "What are the top 5 systemic issues across Region 1?"
- "Which county in my region has the worst trend for KA crashes?"

---

## 13. MPO/Regional Aggregation Engine

### How MPO/TPR Views Differ from CDOT Region Views

| Aspect | CDOT Region View | MPO/TPR View |
|--------|-----------------|--------------|
| Purpose | Operations & maintenance | Long-range planning |
| Focus | Safety, mobility, infrastructure | Land use, transit, multimodal |
| Funding | HSIP, state safety funds | STP, CMAQ, TAP, federal formula |
| Key Output | Project lists, performance measures | TIP, Regional Transportation Plan |
| Typical User | CDOT engineers | MPO planners, local agencies |
| Special Features | Corridor analysis, winter operations | Mode share, VMT, transit integration |

### MPO-Specific Features

#### A. TIP (Transportation Improvement Program) Integration
- Map HSIP-eligible locations to TIP funding categories
- Track which projects are already in the TIP
- Identify gaps (high-crash locations NOT in TIP)

#### B. Safety Performance Targets
- Show progress toward federally-required safety targets
- Compare to state targets
- Per-county contribution to MPO targets

#### C. Multi-Modal Analysis
- Pedestrian crash density maps (critical for urban MPOs like DRCOG)
- Bicycle crash hotspots overlaid on bike network
- Transit stop safety analysis

#### D. Planning-Level Analysis
- Crash rates by functional class (for system-level planning)
- Growth area safety projections
- Equity analysis (crashes in disadvantaged communities)

### Partial County Handling

Some TPRs include only PART of a county (e.g., "Southwest Weld County" is in DRCOG, while most of Weld is in NFRMPO). This requires:

```javascript
// For partial counties, filter by geography not just county name
function filterPartialCounty(countyFips, tprBoundaryGeojson, crashRows) {
    // Use turf.js point-in-polygon to determine which crashes
    // within Weld County fall inside the DRCOG boundary
    return crashRows.filter(row => {
        const point = turf.point([parseFloat(row.x), parseFloat(row.y)]);
        return turf.booleanPointInPolygon(point, tprBoundaryGeojson);
    });
}
```

Alternatively, define partial counties by city or census tract boundaries for simpler filtering.

---

## 14. Statewide View (CDOT HQ)

### What CDOT Headquarters Needs

CDOT HQ users need a **statewide safety picture** for:
1. Strategic Highway Safety Plan (SHSP) development
2. HSIP funding allocation across regions
3. Performance measure reporting to FHWA
4. Systemic safety initiative identification
5. Legislative reporting and advocacy

### Statewide Dashboard Design

```
┌──────────────────────────────────────────────────────────────┐
│ COLORADO STATEWIDE — CRASH LENS                               │
│ 5 CDOT Regions │ 15 TPRs │ 64 Counties                       │
│                                                                │
│ ┌─ KEY METRICS ─────────────────────────────────────────┐     │
│ │  142,567 Total Crashes  │  698 Fatalities  │  1,842 KA │     │
│ │  EPDO: 1,247,832        │  5-Year Trend: ↑ 2.1%       │     │
│ └────────────────────────────────────────────────────────┘     │
│                                                                │
│ ┌─ STATE MAP ────────────────────────────────────────────┐    │
│ │                                                          │    │
│ │  [Choropleth map of Colorado]                            │    │
│ │  Color by: [Crash Rate ▼] [EPDO ▼] [KA Count ▼]        │    │
│ │  Group by: [CDOT Region ▼] [County ▼] [TPR ▼]          │    │
│ │                                                          │    │
│ │  Region 3        Region 4                                │    │
│ │  (Western)       (Northeast)                             │    │
│ │    ████             ████                                 │    │
│ │   ██████    Region 1 ███                                 │    │
│ │    ████    (Denver) ██                                   │    │
│ │             █████████                                    │    │
│ │  Region 5    Region 2                                    │    │
│ │  (Southwest) (Southeast)                                 │    │
│ │    ████       ████████                                   │    │
│ │                                                          │    │
│ └──────────────────────────────────────────────────────────┘    │
│                                                                │
│ ┌─ REGION COMPARISON ────────────────────────────────────┐    │
│ │  [Stacked bar: crashes by region by severity]           │    │
│ │  [Radar chart: region performance across 6 metrics]     │    │
│ │  [Sparklines: 5-year trends per region]                 │    │
│ └────────────────────────────────────────────────────────┘    │
│                                                                │
│ ┌─ EMPHASIS AREAS (SHSP) ────────────────────────────────┐    │
│ │  Impaired Driving:  18,432 crashes (13%)  → Region 1   │    │
│ │  Speed:             14,567 crashes (10%)  → Region 2   │    │
│ │  Pedestrians:        3,211 crashes (2%)   → Region 1   │    │
│ │  Intersections:     42,345 crashes (30%)  → Statewide  │    │
│ │  Young Drivers:     21,876 crashes (15%)  → Region 4   │    │
│ │  Lane Departure:    28,765 crashes (20%)  → Region 3   │    │
│ └────────────────────────────────────────────────────────┘    │
│                                                                │
│ ┌─ SYSTEMIC SAFETY ─────────────────────────────────────┐    │
│ │  [Top 50 statewide hotspots across all regions]        │    │
│ │  [Systemic issues: curves, intersections, etc.]        │    │
│ │  [Click any to drill down to county-level detail]      │    │
│ └────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### Performance Loading Strategy for Statewide

Loading 64 county CSVs simultaneously would be too slow. Strategy:

1. **Pre-aggregated summaries** (JSON) load instantly for dashboard/comparisons
2. **On-demand county loading** when user drills down
3. **Region-level CSVs** as intermediate — one CSV per region (pre-combined)
4. **WebWorker processing** for large datasets (keep UI responsive)
5. **IndexedDB caching** — once a county's data is loaded, cache in browser

```javascript
// Loading strategy pseudocode
async function loadStateView() {
    // FAST: Load pre-aggregated state summary (~50KB JSON)
    const stateSummary = await fetch('data/CDOT/aggregates/statewide.json');
    renderStateDashboard(stateSummary);

    // FAST: Load region summaries (~10KB each, 5 regions = 50KB)
    const regionSummaries = await Promise.all(
        ['region_1', 'region_2', 'region_3', 'region_4', 'region_5']
            .map(r => fetch(`data/CDOT/aggregates/by_region/${r}.json`))
    );
    renderRegionComparison(regionSummaries);

    // LAZY: Only load raw CSV when user drills into a specific county
    // Use IndexedDB to cache after first load
}
```

---

## 15. Multi-State Scaling Strategy

### How to Expand Beyond Colorado

The architecture described above is **state-agnostic**. Here's how to add a new state:

```
┌─────────────────────────────────────────────────────────────┐
│              ADDING A NEW STATE (e.g., Texas)                │
│                                                               │
│  STEP 1: Create state config                                 │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  states/48/config.json     → Column mappings            │ │
│  │  states/48/hierarchy.json  → TxDOT districts, MPOs,     │ │
│  │                              counties                    │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  STEP 2: Add StateAdapter signature (if CSV format differs)  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  In state_adapter.js, add:                              │ │
│  │  texas: {                                               │ │
│  │    requiredColumns: ['Crash ID', 'Crash Severity', ...],│ │
│  │    displayName: 'Texas (CRIS)',                         │ │
│  │    configPath: 'states/48/config.json'                  │ │
│  │  }                                                      │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  STEP 3: Create data downloader                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  download_txdot_crash_data.py                           │ │
│  │  (or add Texas to generic download_state_crash_data.py) │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  STEP 4: Run onboarding                                      │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  python onboard_jurisdiction.py --state texas --setup    │ │
│  │  python onboard_jurisdiction.py --state texas --all      │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ZERO changes to app/index.html needed!                      │
│  The Hierarchy Registry and Aggregation Engine handle it.    │
└─────────────────────────────────────────────────────────────┘
```

### Generic State Hierarchy Template

Every state DOT has a similar organizational pattern, but with different names:

| Concept | Colorado | Virginia | Texas | California |
|---------|----------|----------|-------|------------|
| State DOT | CDOT | VDOT | TxDOT | Caltrans |
| District/Region | 5 Engineering Regions | 9 Construction Districts | 25 Districts | 12 Districts |
| MPO equivalent | 5 MPOs + 10 TPRs | 14 MPOs + PDCs | 25 MPOs | 18 MPOs + RTPAs |
| County equivalent | 64 Counties | 95 Counties + 38 Cities | 254 Counties | 58 Counties |
| Sub-county | Cities/Places | Cities/CDPs | Cities/Places | Cities/Places |

The `hierarchy.json` schema handles all of these:

```json
{
  "state": { "fips": "XX", "name": "..." },
  "regionType": {
    "label": "District",
    "labelPlural": "Districts"
  },
  "regions": { },
  "tprType": {
    "label": "MPO",
    "labelPlural": "MPOs"
  },
  "tprs": { },
  "corridors": { }
}
```

### Cross-State Comparison Mode (Future)

For FHWA or multi-state organizations:

```
┌──────────────────────────────────────────────────────────────┐
│  CROSS-STATE COMPARISON                                       │
│                                                                │
│  ┌─ Select States ─────────────────────────────────────────┐  │
│  │  [✓] Colorado    [✓] Virginia    [ ] Texas              │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
│  ┌─ Side-by-Side ──────────────────────────────────────────┐  │
│  │  Metric          │ Colorado    │ Virginia               │  │
│  │──────────────────┼─────────────┼────────────────────────│  │
│  │  Total Crashes   │ 142,567     │ 128,345                │  │
│  │  Fatal Crashes   │ 698         │ 845                    │  │
│  │  KA Rate         │ 1.29%       │ 1.52%                  │  │
│  │  Ped Crashes     │ 3,211       │ 2,876                  │  │
│  │  Impaired        │ 18,432      │ 15,234                 │  │
│  └─────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 16. Database & Storage Strategy

### Tier 1: File-Based (Current + Enhanced) — For Small-Medium Deployments

```
Approach: CSV files + JSON configs on disk/CDN
Best for: Single county to ~10 counties
Performance: Fast for 1 county, acceptable for 5-10 counties
Storage: ~20-50MB per county per 5 years
Deployment: Static hosting (GitHub Pages, S3, Netlify)
```

### Tier 2: IndexedDB + Service Worker — For Medium Deployments

```
Approach: Load CSVs once, cache in browser IndexedDB
Best for: 10-64 counties (full state)
Performance: First load slow, subsequent loads instant
Storage: Up to ~2GB in IndexedDB per origin
Deployment: Static hosting + Service Worker for offline
```

### Tier 3: Backend API + Database — For Large/Enterprise Deployments

```
Approach: PostgreSQL/PostGIS backend, REST/GraphQL API
Best for: Multi-state, real-time data, many concurrent users
Performance: Sub-second queries on millions of records
Storage: Unlimited (server-side)
Deployment: Cloud (AWS, Azure, GCP) or on-premise

Stack:
  Backend: Python FastAPI or Node.js Express
  Database: PostgreSQL + PostGIS
  Cache: Redis
  API: REST or GraphQL
  Hosting: Docker containers on cloud
```

### Recommended Progression

```
Phase 1 (Now)     → Tier 1: File-based (CSV + JSON)
Phase 2 (6 months) → Tier 2: IndexedDB caching for multi-county
Phase 3 (12+ months) → Tier 3: Backend API for statewide/multi-state
```

---

## 17. API & Backend Architecture

### Optional REST API Design (Phase 3)

When file-based loading becomes too slow (100+ counties, multiple states), introduce an API:

```
GET /api/v1/states
  → List all available states

GET /api/v1/states/08/regions
  → List CDOT regions

GET /api/v1/states/08/regions/region_1/summary
  → Aggregated stats for Region 1

GET /api/v1/states/08/counties/035/crashes
  ?year=2024
  &severity=K,A
  &road_type=all
  &limit=1000
  → Douglas County crash records

GET /api/v1/states/08/counties/035/hotspots
  ?top=20
  &method=epdo
  → Top 20 hotspots in Douglas County

GET /api/v1/states/08/tprs/drcog/crashes
  ?year=2024
  → All crashes in DRCOG MPO area

GET /api/v1/states/08/corridors/I-25/crashes
  ?from_county=101&to_county=069
  → I-25 crashes from Pueblo to Larimer

GET /api/v1/compare
  ?entities=08:035,08:005,08:031
  &metrics=total,fatal,epdo
  → Compare Douglas, Arapahoe, Denver
```

### Database Schema (PostgreSQL + PostGIS)

```sql
-- States
CREATE TABLE states (
    fips CHAR(2) PRIMARY KEY,
    name VARCHAR(100),
    abbreviation CHAR(2),
    dot_name VARCHAR(50),
    config JSONB
);

-- Regions (CDOT Engineering Regions, VDOT Districts, etc.)
CREATE TABLE regions (
    id VARCHAR(50) PRIMARY KEY,
    state_fips CHAR(2) REFERENCES states(fips),
    name VARCHAR(200),
    office_address TEXT,
    boundary GEOMETRY(MultiPolygon, 4326),
    config JSONB
);

-- TPRs / MPOs
CREATE TABLE planning_regions (
    id VARCHAR(50) PRIMARY KEY,
    state_fips CHAR(2) REFERENCES states(fips),
    name VARCHAR(200),
    type VARCHAR(20), -- 'mpo' or 'rural_tpr'
    admin_org VARCHAR(200),
    boundary GEOMETRY(MultiPolygon, 4326),
    config JSONB
);

-- Counties
CREATE TABLE counties (
    state_fips CHAR(2),
    county_fips CHAR(3),
    name VARCHAR(200),
    region_id VARCHAR(50) REFERENCES regions(id),
    boundary GEOMETRY(MultiPolygon, 4326),
    config JSONB,
    PRIMARY KEY (state_fips, county_fips)
);

-- County ↔ TPR/MPO (many-to-many, handles partial counties)
CREATE TABLE county_tpr_membership (
    state_fips CHAR(2),
    county_fips CHAR(3),
    tpr_id VARCHAR(50) REFERENCES planning_regions(id),
    coverage VARCHAR(20) DEFAULT 'full', -- 'full' or 'partial'
    notes TEXT,
    PRIMARY KEY (state_fips, county_fips, tpr_id)
);

-- Crashes (partitioned by state for performance)
CREATE TABLE crashes (
    id BIGSERIAL,
    state_fips CHAR(2),
    county_fips CHAR(3),
    crash_date DATE,
    crash_year SMALLINT,
    severity CHAR(1), -- K/A/B/C/O
    collision_type VARCHAR(100),
    route VARCHAR(200),
    node VARCHAR(200),
    location GEOMETRY(Point, 4326),
    weather VARCHAR(100),
    lighting VARCHAR(100),
    pedestrian BOOLEAN,
    bicycle BOOLEAN,
    alcohol BOOLEAN,
    speed BOOLEAN,
    raw_data JSONB, -- Original row for state-specific fields
    PRIMARY KEY (state_fips, id)
) PARTITION BY LIST (state_fips);

-- Partition per state
CREATE TABLE crashes_co PARTITION OF crashes FOR VALUES IN ('08');
CREATE TABLE crashes_va PARTITION OF crashes FOR VALUES IN ('51');

-- Spatial index for map queries
CREATE INDEX idx_crashes_location ON crashes USING GIST (location);

-- Pre-aggregated summaries (refreshed nightly)
CREATE MATERIALIZED VIEW mv_county_summary AS
SELECT
    state_fips, county_fips, crash_year,
    COUNT(*) as total_crashes,
    SUM(CASE WHEN severity = 'K' THEN 1 ELSE 0 END) as fatal,
    SUM(CASE WHEN severity = 'A' THEN 1 ELSE 0 END) as serious_injury,
    SUM(CASE WHEN severity = 'K' THEN 462
             WHEN severity = 'A' THEN 62
             WHEN severity = 'B' THEN 12
             WHEN severity = 'C' THEN 5
             ELSE 1 END) as epdo_score
FROM crashes
GROUP BY state_fips, county_fips, crash_year;
```

---

## 18. Phased Implementation Roadmap

### Phase 1: Foundation (Weeks 1-4)

**Goal:** All 64 Colorado counties loadable with zero code changes per county.

| # | Task | Effort | Dependencies |
|---|------|--------|--------------|
| 1.1 | Create `states/08/hierarchy.json` with all CDOT regions, TPRs, counties | 3 days | Research (done) |
| 1.2 | Build `hierarchy_registry.js` — load and query hierarchy data | 3 days | 1.1 |
| 1.3 | Enhance `download_cdot_crash_data.py` to support all 64 counties | 2 days | — |
| 1.4 | Build `split_by_jurisdiction.py` to split statewide CSV by county | 2 days | — |
| 1.5 | Restructure `data/CDOT/` to per-county subdirectories | 1 day | 1.4 |
| 1.6 | Update `APP_PATHS.getDataFile()` to use new directory structure | 1 day | 1.5 |
| 1.7 | Populate all 64 county configs from FIPSDatabase automatically | 1 day | 1.1 |
| 1.8 | Test: Load Douglas County from new structure, verify no regressions | 1 day | 1.5, 1.6 |

**Deliverable:** Any Colorado county's data can be downloaded, processed, and loaded by changing only a config value.

### Phase 2: Multi-County Aggregation (Weeks 5-8)

**Goal:** View crash data for multiple counties at once (region view).

| # | Task | Effort | Dependencies |
|---|------|--------|--------------|
| 2.1 | Build `aggregation_engine.js` — load and combine multiple county CSVs | 5 days | 1.2 |
| 2.2 | Build WebWorker wrapper for heavy aggregation (keep UI responsive) | 2 days | 2.1 |
| 2.3 | Add IndexedDB caching layer for loaded county data | 3 days | 2.1 |
| 2.4 | Build `pre_aggregate.py` to generate summary JSONs per region/county | 3 days | 1.4 |
| 2.5 | Implement cascading scope selector UI | 3 days | 1.2 |
| 2.6 | Wire scope selector to aggregation engine | 2 days | 2.1, 2.5 |
| 2.7 | Test: Load Region 1 (10 counties), verify aggregation correctness | 2 days | 2.1-2.6 |

**Deliverable:** Users can select "CDOT Region 1" and see combined data from all 10 counties.

### Phase 3: Region & Statewide Views (Weeks 9-14)

**Goal:** Full region dashboard and statewide overview.

| # | Task | Effort | Dependencies |
|---|------|--------|--------------|
| 3.1 | Design & implement Region Dashboard tab (per-county breakdown) | 5 days | 2.1 |
| 3.2 | Implement cross-county hotspot ranking algorithm | 3 days | 2.1 |
| 3.3 | Add county boundary GeoJSON to map view | 3 days | — |
| 3.4 | Add region boundary GeoJSON to map view | 2 days | 3.3 |
| 3.5 | Implement choropleth coloring (counties by crash rate/EPDO) | 3 days | 3.3 |
| 3.6 | Build statewide summary dashboard | 4 days | 2.4 |
| 3.7 | Implement drill-down navigation (state → region → county) | 3 days | 3.1, 3.6 |
| 3.8 | Update AI Assistant for multi-county context awareness | 3 days | 2.1 |
| 3.9 | Test: Full statewide view with all 5 regions | 3 days | All above |

**Deliverable:** CDOT HQ can view statewide dashboard with drill-down to any region/county.

### Phase 4: MPO/TPR Views (Weeks 15-18)

**Goal:** MPO planners can use the tool for their planning area.

| # | Task | Effort | Dependencies |
|---|------|--------|--------------|
| 4.1 | Implement MPO/TPR scope selection in UI | 2 days | 2.5 |
| 4.2 | Handle partial county membership (point-in-polygon or city filter) | 4 days | 3.3 |
| 4.3 | Build TPR boundary GeoJSON layers | 2 days | 3.3 |
| 4.4 | Implement MPO-specific dashboard features | 3 days | 3.1 |
| 4.5 | Add safety performance target tracking | 3 days | 2.4 |
| 4.6 | Test: DRCOG view with 9+ counties | 2 days | All above |

**Deliverable:** MPO planners see their planning area with multi-county aggregation.

### Phase 5: Corridor Analysis (Weeks 19-22)

**Goal:** Analyze crash patterns along a corridor spanning multiple counties.

| # | Task | Effort | Dependencies |
|---|------|--------|--------------|
| 5.1 | Define corridor routes in hierarchy.json | 2 days | 1.1 |
| 5.2 | Implement corridor scope selection | 2 days | 2.5 |
| 5.3 | Build corridor-specific filtering (match route name across counties) | 3 days | 2.1 |
| 5.4 | Linear referencing view (milepost-based crash plotting) | 5 days | 5.3 |
| 5.5 | Corridor safety metrics (crash rate per mile, etc.) | 3 days | 5.3 |
| 5.6 | Test: I-25 corridor from Pueblo to Fort Collins | 2 days | All above |

**Deliverable:** Engineers can analyze I-25 from end to end across all counties it passes through.

### Phase 6: Automated Onboarding & Multi-State (Weeks 23-30)

**Goal:** One command adds a new county or state.

| # | Task | Effort | Dependencies |
|---|------|--------|--------------|
| 6.1 | Build `onboard_jurisdiction.py` script | 5 days | 1.3, 1.4 |
| 6.2 | Build state setup wizard (interactive CLI) | 3 days | 6.1 |
| 6.3 | Auto-fetch county boundaries from Census TIGERweb | 2 days | — |
| 6.4 | Create new-state template directory | 1 day | — |
| 6.5 | Test: Onboard Texas (new state, new CSV format) | 5 days | All above |
| 6.6 | Test: Onboard remaining 58 Colorado counties | 3 days | 6.1 |
| 6.7 | Documentation and usage guide | 3 days | All above |

**Deliverable:** `python onboard_jurisdiction.py --state texas --setup` creates a working Texas instance.

### Phase 7: Backend API (Weeks 31-40) — Optional

**Goal:** Scale to multi-state with real-time data and many users.

| # | Task | Effort | Dependencies |
|---|------|--------|--------------|
| 7.1 | Design and implement REST API (FastAPI) | 10 days | — |
| 7.2 | PostgreSQL + PostGIS database setup | 5 days | — |
| 7.3 | Data import pipeline (CSV → PostgreSQL) | 5 days | 7.2 |
| 7.4 | Modify frontend to use API when available, files as fallback | 5 days | 7.1 |
| 7.5 | Authentication and role-based access | 5 days | 7.1 |
| 7.6 | Docker containerization | 3 days | 7.1, 7.2 |
| 7.7 | CI/CD for automated deployment | 3 days | 7.6 |

**Deliverable:** Production-grade backend supporting unlimited states and concurrent users.

---

## 19. Risk Assessment & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Browser memory limits** with 64-county data | High | Data won't load | Pre-aggregated JSONs for overview; lazy-load raw CSV only on drill-down |
| **CDOT data access** restricted or format changes | Medium | Pipeline breaks | Multiple download methods; format detection in StateAdapter auto-adapts |
| **Overlapping TPR/Region boundaries** cause double-counting | Medium | Incorrect stats | Clearly document: each crash belongs to exactly one county; aggregation is county-based |
| **Partial county TPR membership** hard to implement | Medium | Incorrect MPO stats | Start with full-county approximation; add point-in-polygon for precision later |
| **Performance degradation** at scale | Medium | Poor UX | WebWorkers, IndexedDB caching, pre-aggregation, pagination |
| **Stale data** across many counties | Low | Outdated analysis | Automated weekly GitHub Actions for scheduled counties; manifest tracks freshness |
| **Cross-county intersection naming** inconsistent | Medium | Node matching fails | Normalize intersection names; use coordinates for proximity matching |
| **GeoJSON boundaries** too large for browser | Low | Slow map | Simplify geometries (turf.simplify); use vector tiles at scale |

---

## Appendix A: Complete Colorado County-to-Region Mapping

### All 64 Colorado Counties → CDOT Region → TPR/MPO

| County | FIPS | CDOT Region | TPR/MPO | Pop. (est.) |
|--------|------|-------------|---------|-------------|
| Adams | 001 | Region 1 | DRCOG (MPO) | 519,572 |
| Alamosa | 003 | Region 5 | San Luis Valley TPR | 17,141 |
| Arapahoe | 005 | Region 1 | DRCOG (MPO) | 655,070 |
| Archuleta | 007 | Region 5 | Southwest TPR | 14,029 |
| Baca | 009 | Region 2 | Southeast TPR | 3,556 |
| Bent | 011 | Region 2 | Southeast TPR | 5,577 |
| Boulder | 013 | Region 1 | DRCOG (MPO) | 330,758 |
| Broomfield | 014 | Region 1 | DRCOG (MPO) | 74,112 |
| Chaffee | 015 | Region 2/5 | San Luis Valley TPR | 20,477 |
| Cheyenne | 017 | Region 4 | Eastern TPR | 1,735 |
| Clear Creek | 019 | Region 1 | DRCOG (MPO) | 9,700 |
| Conejos | 021 | Region 5 | San Luis Valley TPR | 7,720 |
| Costilla | 023 | Region 5 | San Luis Valley TPR | 3,887 |
| Crowley | 025 | Region 2 | Southeast TPR | 6,012 |
| Custer | 027 | Region 2 | Central Front Range TPR | 5,068 |
| Delta | 029 | Region 3 | Gunnison Valley TPR | 31,024 |
| Denver | 031 | Region 1 | DRCOG (MPO) | 713,252 |
| Dolores | 033 | Region 5 | Southwest TPR | 2,286 |
| Douglas | 035 | Region 1 | DRCOG (MPO) | 357,978 |
| Eagle | 037 | Region 3 | Intermountain TPR | 55,731 |
| Elbert | 039 | Region 2 | Eastern TPR | 27,440 |
| El Paso | 041 | Region 2 | PPACG (MPO) | 730,395 |
| Fremont | 043 | Region 2 | Central Front Range TPR | 48,004 |
| Garfield | 045 | Region 3 | Intermountain TPR | 62,213 |
| Gilpin | 047 | Region 1 | DRCOG (MPO) | 6,243 |
| Grand | 049 | Region 3 | Northwest TPR | 15,734 |
| Gunnison | 051 | Region 3 | Gunnison Valley TPR | 17,462 |
| Hinsdale | 053 | Region 3 | Gunnison Valley TPR | 820 |
| Huerfano | 055 | Region 2 | South Central TPR | 6,459 |
| Jackson | 057 | Region 3 | Northwest TPR | 1,359 |
| Jefferson | 059 | Region 1 | DRCOG (MPO) | 582,881 |
| Kiowa | 061 | Region 2 | Southeast TPR | 1,406 |
| Kit Carson | 063 | Region 4 | Eastern TPR | 7,096 |
| Lake | 065 | Region 2/3 | Intermountain TPR | 8,327 |
| La Plata | 067 | Region 5 | Southwest TPR | 56,221 |
| Larimer | 069 | Region 4 | NFRMPO (MPO) | 359,066 |
| Las Animas | 071 | Region 2 | South Central TPR | 14,506 |
| Lincoln | 073 | Region 2/4 | Eastern TPR | 5,608 |
| Logan | 075 | Region 4 | Eastern TPR | 22,409 |
| Mesa | 077 | Region 3 | GVMPO (MPO) | 157,502 |
| Mineral | 079 | Region 5 | San Luis Valley TPR | 803 |
| Moffat | 081 | Region 3 | Northwest TPR | 13,283 |
| Montezuma | 083 | Region 5 | Southwest TPR | 26,266 |
| Montrose | 085 | Region 3 | Gunnison Valley TPR | 47,082 |
| Morgan | 087 | Region 4 | Upper Front Range TPR | 29,068 |
| Otero | 089 | Region 2 | Southeast TPR | 18,278 |
| Ouray | 091 | Region 3 | Gunnison Valley TPR | 5,044 |
| Park | 093 | Region 2 | Central Front Range TPR | 18,845 |
| Phillips | 095 | Region 4 | Eastern TPR | 4,285 |
| Pitkin | 097 | Region 3 | Intermountain TPR | 17,767 |
| Prowers | 099 | Region 2 | Southeast TPR | 11,722 |
| Pueblo | 101 | Region 2 | PACOG (MPO) | 168,424 |
| Rio Blanco | 103 | Region 3 | Northwest TPR | 6,352 |
| Rio Grande | 105 | Region 5 | San Luis Valley TPR | 11,180 |
| Routt | 107 | Region 3 | Northwest TPR | 26,090 |
| Saguache | 109 | Region 5 | San Luis Valley TPR | 6,824 |
| San Juan | 111 | Region 5 | Southwest TPR | 737 |
| San Miguel | 113 | Region 3 | Gunnison Valley TPR | 8,179 |
| Sedgwick | 115 | Region 4 | Eastern TPR | 2,248 |
| Summit | 117 | Region 1 | Intermountain TPR | 31,011 |
| Teller | 119 | Region 2 | PPACG (MPO) | 25,388 |
| Washington | 121 | Region 4 | Eastern TPR | 4,830 |
| Weld | 123 | Region 4 | NFRMPO (MPO) / DRCOG (partial) / UFR (partial) | 324,492 |
| Yuma | 125 | Region 4 | Eastern TPR | 10,019 |

> **Note:** Weld County spans three TPRs: NFRMPO, DRCOG (southwest portion), and Upper Front Range (northeast portion). This is the most complex case in Colorado.

---

## Appendix B: Configuration Schema Reference

### hierarchy.json Schema

```jsonc
{
  // State identification
  "state": {
    "fips": "string (2-digit)",      // Required: "08"
    "name": "string",                 // Required: "Colorado"
    "abbreviation": "string (2-char)" // Required: "CO"
  },

  // DOT region/district configuration
  "regionType": {
    "label": "string",               // Display label: "CDOT Engineering Region"
    "labelPlural": "string",         // Plural: "CDOT Engineering Regions"
    "shortLabel": "string",          // Short: "Region"
    "description": "string"          // Description for tooltips
  },

  // Region definitions (keyed by region ID)
  "regions": {
    "<region_id>": {
      "id": "string",                // Unique ID: "region_1"
      "name": "string",              // Short name: "Region 1"
      "fullName": "string",          // Full: "CDOT Region 1 — Denver Metro"
      "office": "string",            // Office address
      "phone": "string",             // Optional contact
      "director": "string",          // Optional director name
      "counties": ["string"],        // Array of 3-digit county FIPS
      "countyNames": ["string"],     // Human-readable county names
      "mapCenter": [number, number], // [lat, lon]
      "mapZoom": "number",           // Mapbox zoom level
      "keyCorridors": ["string"],    // Major routes in this region
      "config": {}                   // Optional region-specific overrides
    }
  },

  // TPR/MPO configuration
  "tprType": {
    "label": "string",               // "Transportation Planning Region"
    "labelPlural": "string",
    "shortLabel": "string"
  },

  // TPR definitions (keyed by TPR ID)
  "tprs": {
    "<tpr_id>": {
      "id": "string",                // Unique ID: "drcog"
      "name": "string",              // Short: "DRCOG"
      "fullName": "string",          // Full: "Denver Regional Council of Governments"
      "type": "string",              // "mpo" or "rural_tpr"
      "counties": ["string"],        // Full-coverage county FIPS codes
      "countyNames": ["string"],
      "partialCounties": {           // Counties with partial coverage
        "<county_fips>": "string"    // Description of partial coverage
      },
      "adminOrg": "string",          // Administering organization
      "website": "string",           // Optional URL
      "mapCenter": [number, number],
      "mapZoom": "number"
    }
  },

  // Corridor definitions
  "corridors": {
    "<corridor_id>": {
      "name": "string",              // "I-25 Corridor"
      "description": "string",
      "routePattern": "string",      // Regex to match route names
      "counties": ["string"],        // County FIPS codes along corridor
      "regions": ["string"],         // Region IDs crossed
      "length_miles": "number"
    }
  }
}
```

### State config.json Schema (Enhanced)

```jsonc
{
  // State identification
  "state": {
    "name": "string",
    "abbreviation": "string",
    "fips": "string",
    "dotName": "string",
    "dotFullName": "string",
    "dataDir": "string"              // Subdirectory in data/
  },

  // Column mapping (state CSV → internal format)
  "columnMapping": {
    "ID": "string",                  // Crash ID column
    "DATE": "string",
    "SEVERITY": "string",            // or null if derived
    // ... (existing schema from data/CDOT/config.json)
  },

  // Fields computed from other columns
  "derivedFields": {
    "SEVERITY": { "method": "...", "sources": ["..."] },
    // ... (existing schema)
  },

  // Road classification
  "roadSystems": {
    "values": {},
    "filterProfiles": {}
  },

  // EPDO weights (may vary by state/agency policy)
  "epdoWeights": {
    "K": 462, "A": 62, "B": 12, "C": 5, "O": 1
  },

  // Data source configuration
  "dataSource": {
    "name": "string",
    "url": "string",
    "apiUrl": "string",
    "fileFormat": "string",
    "downloadMethod": "string"       // "api", "file", "scrape"
  },

  // NEW: Multi-jurisdiction data configuration
  "multiJurisdiction": {
    "enabled": true,
    "hierarchyFile": "states/08/hierarchy.json",
    "boundaryFiles": {
      "counties": "states/08/counties.geojson",
      "regions": "states/08/regions.geojson",
      "tprs": "states/08/tprs.geojson"
    },
    "aggregateDir": "data/CDOT/aggregates",
    "countyDataDir": "data/CDOT/counties",
    "maxConcurrentCountyLoads": 5,
    "preAggregateEnabled": true
  }
}
```

---

## Summary: What Makes This Design "Automatic and Dynamic"

1. **Auto-detection** — StateAdapter reads CSV headers and automatically knows which state's data it's processing. No manual configuration needed per dataset.

2. **Auto-discovery** — If crash data contains a "County" column, the tool can automatically discover all counties present in the data without pre-configuration.

3. **Config-driven hierarchy** — Adding a new county, region, or MPO requires ONLY editing a JSON file. The UI, aggregation, and navigation automatically adapt.

4. **Cascading scope** — Selecting "Region 1" automatically resolves to all counties in that region, loads their data, and aggregates. The user doesn't need to know which counties are in Region 1.

5. **Lazy loading** — Statewide views use pre-aggregated JSON (tiny, instant). Raw CSV is loaded only when drilling into a specific county. Browser memory stays manageable.

6. **Template-based onboarding** — `onboard_jurisdiction.py --state texas --setup` creates all necessary config files from a template, populated with FIPS data already embedded in the codebase.

7. **Multiple overlapping groupings** — A county simultaneously belongs to a CDOT Region AND a TPR/MPO AND corridors. The hierarchy model supports this natively via the DAG (not tree) structure.

8. **Progressive enhancement** — Start with CSV files (works today), add IndexedDB caching (Phase 2), optionally add a backend API (Phase 3). The frontend code works identically in all three modes.

---

*This plan was generated based on analysis of the CRASH LENS codebase, CDOT organizational structure research, and Colorado TPR/MPO documentation. FIPS codes and county assignments should be verified against the latest CDOT region boundary shapefile before implementation.*

**Sources:**
- [CDOT Regions](https://www.codot.gov/about/regions)
- [CDOT TPR/MPO Planning Partners](https://www.codot.gov/programs/planning/planning-partners/tpr-mpo)
- [TPR at a Glance (Jan 2026)](https://www.codot.gov/programs/planning/assets/planning-partners/january2026tpr)
- [DRCOG Member Governments](https://www.drcog.org/about-drcog/member-governments)
- [NFRMPO Partners](https://nfrmpo.org/partners/)
