# Roadway Context Services Integration Plan

## Executive Summary

This document outlines the implementation plan for integrating VDOT roadway attribute services (Speed Limits, Traffic Volume, Functional Classification) into the Virginia Crash Analysis Tool. These services will provide contextual enrichment for crash analysis, improve CMF recommendations, and enable automated asset deficiency detection.

**Target Completion:** 4 Implementation Phases
**Priority:** High - Enhances core analysis capabilities
**Risk Level:** Medium - External API dependencies

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Solution Overview](#solution-overview)
3. [Data Sources](#data-sources)
4. [Architecture Design](#architecture-design)
5. [Implementation Phases](#implementation-phases)
6. [Technical Specifications](#technical-specifications)
7. [Risk Assessment & Mitigation](#risk-assessment--mitigation)
8. [Testing Strategy](#testing-strategy)
9. [Multi-State Adaptation Guide](#multi-state-adaptation-guide)
10. [Appendix](#appendix)

---

## Problem Statement

### Current Limitations

1. **No Speed Context**: When analyzing crash hotspots, engineers cannot see the posted speed limit, making it difficult to:
   - Select speed-appropriate countermeasures
   - Identify speed transition zone issues
   - Understand severity patterns (higher speeds = more severe crashes)

2. **No Traffic Volume Data**: Without AADT (Annual Average Daily Traffic), engineers cannot:
   - Calculate crash rates (crashes per million VMT)
   - Identify high-exposure locations
   - Apply volume-specific CMFs correctly

3. **No Functional Classification**: Missing road type context prevents:
   - Proper CMF applicability filtering
   - Understanding design standard expectations
   - Appropriate countermeasure selection for road type

4. **Manual Research Required**: Engineers must manually look up this information from separate sources, slowing analysis.

### Business Value

| Metric | Current State | With Integration |
|--------|---------------|------------------|
| Time to analyze location | 15-20 min | 2-3 min |
| CMF applicability accuracy | ~60% (guessing) | ~95% (data-driven) |
| Deficiency detection | Manual only | Automated rules |
| Multi-state deployment | N/A | Config-driven |

---

## Solution Overview

### Architectural Decision: Hybrid Contextual Enrichment

After evaluating multiple options, we recommend a **Hybrid Contextual Architecture**:

| Approach | Implementation | Use Case |
|----------|---------------|----------|
| **Primary** | Automatic enrichment on location selection | CMF tab, Warrants, AI analysis |
| **Secondary** | Optional map overlay layers | Visual exploration |
| **Advanced** | Automated deficiency detection | Asset Deficiency analysis |

### Why NOT a Dedicated Tab?

- Speed limits, traffic volume, and functional classification are **road attributes**, not **assets**
- They don't fit conceptually under "Infrastructure Assets" (which is for physical objects like signs, signals)
- They're most valuable as **context** when analyzing a specific location
- Adding another tab increases UI complexity without proportional value

### Integration Points

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         INTEGRATION ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────┐     ┌─────────────────────────────────────────────┐   │
│   │ config.json │────▶│         ROADWAY CONTEXT SERVICE              │   │
│   │ - Endpoints │     │                                              │   │
│   │ - Fields    │     │  ┌─────────────────────────────────────┐    │   │
│   │ - Rules     │     │  │      enrichLocationContext()        │    │   │
│   └─────────────┘     │  │  - Query speed limits API           │    │   │
│                       │  │  - Query traffic volume API         │    │   │
│                       │  │  - Query functional class API       │    │   │
│   ┌─────────────┐     │  │  - Cache results in IndexedDB       │    │   │
│   │  IndexedDB  │◀───▶│  │  - Return unified context object    │    │   │
│   │   Cache     │     │  └─────────────────────────────────────┘    │   │
│   └─────────────┘     └──────────────────┬──────────────────────────┘   │
│                                          │                               │
│                    ┌─────────────────────┼─────────────────────┐        │
│                    │                     │                     │        │
│                    ▼                     ▼                     ▼        │
│            ┌─────────────┐       ┌─────────────┐       ┌─────────────┐  │
│            │   CMF TAB   │       │  WARRANTS   │       │     AI      │  │
│            │             │       │     TAB     │       │  ASSISTANT  │  │
│            │ - Context   │       │             │       │             │  │
│            │   display   │       │ - Speed for │       │ - Full      │  │
│            │ - CMF       │       │   warrants  │       │   context   │  │
│            │   filtering │       │ - Volume    │       │   in prompt │  │
│            │ - Speed-    │       │   thresholds│       │             │  │
│            │   specific  │       │             │       │             │  │
│            └─────────────┘       └─────────────┘       └─────────────┘  │
│                    │                                                     │
│                    ▼                                                     │
│            ┌─────────────────────────────────────────────────────────┐  │
│            │              ASSET DEFICIENCY DETECTION                  │  │
│            │                                                          │  │
│            │  Rules Engine analyzes:                                  │  │
│            │  - Speed + Ped crashes + No sidewalk = Deficiency        │  │
│            │  - High AADT + Angle crashes + No signal = Deficiency    │  │
│            │  - Arterial + Night crashes + No lighting = Deficiency   │  │
│            └─────────────────────────────────────────────────────────┘  │
│                                                                          │
│            ┌─────────────────────────────────────────────────────────┐  │
│            │              MAP TAB (Optional Layers)                   │  │
│            │                                                          │  │
│            │  [ ] Speed Limits    [ ] Traffic Volume   [ ] Func Class │  │
│            │  (Toggle polyline overlays for visual exploration)       │  │
│            └─────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Sources

### VDOT Services (Virginia)

| Service | Endpoint | Geometry | Update Freq | Auth |
|---------|----------|----------|-------------|------|
| **Speed Limits** | `https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/VDOT_Posted_Speed_Limits/FeatureServer/0` | Polyline | Weekly | None |
| **Traffic Volume** | `https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/VDOT_Bidirectional_Traffic_Volume/FeatureServer/0` | Polyline | Annually | None |
| **Functional Class** | `https://vdotgisuportal.vdot.virginia.gov/env/rest/services/VDOT_Map/Virginia_Tech_LRS_Routes/FeatureServer/4` | Polyline | Nightly | None |

### Key Fields

#### Speed Limits
| Field | Type | Description |
|-------|------|-------------|
| `CAR_SPEED` | Integer | Posted speed limit for passenger vehicles (mph) |
| `TRUCK_SPEED` | Integer | Posted speed limit for trucks (mph) |
| `SPEEDZONE_TYPE` | String | "Statutory" or "Resolution" zone type |
| `ROUTE_NAME` | String | Route identifier |

#### Traffic Volume
| Field | Type | Description |
|-------|------|-------------|
| `AADT` | Integer | Annual Average Daily Traffic (vehicles/day) |
| `AADT_YEAR` | Integer | Year of traffic count |
| `ROUTE_ID` | String | Route identifier |

#### Functional Classification
| Field | Type | Description |
|-------|------|-------------|
| `FUNC_CLASS` | Integer | Functional class code (1-7) |
| `FUNC_CLASS_DESC` | String | Description (e.g., "Urban Minor Arterial") |

### Functional Class Codes
| Code | Description | Typical Speed | Typical AADT |
|------|-------------|---------------|--------------|
| 1 | Interstate | 55-70 mph | 20,000+ |
| 2 | Other Freeways & Expressways | 45-65 mph | 15,000+ |
| 3 | Other Principal Arterial | 35-55 mph | 10,000+ |
| 4 | Minor Arterial | 30-45 mph | 5,000-15,000 |
| 5 | Major Collector | 25-40 mph | 2,000-8,000 |
| 6 | Minor Collector | 25-35 mph | 500-3,000 |
| 7 | Local | 15-30 mph | <2,000 |

---

## Architecture Design

### State Management

```javascript
// New state object for roadway context
const roadwayContextState = {
    // Initialization status
    initialized: false,
    initError: null,

    // Service health tracking
    servicesHealth: {
        speedLimits: {
            available: null,      // null = unchecked, true/false = checked
            lastCheck: null,      // timestamp
            error: null,          // error message if failed
            responseTime: null    // ms for performance monitoring
        },
        trafficVolume: { available: null, lastCheck: null, error: null, responseTime: null },
        functionalClass: { available: null, lastCheck: null, error: null, responseTime: null }
    },

    // IndexedDB cache reference
    cache: null,
    cacheStats: {
        hits: 0,
        misses: 0,
        size: 0
    },

    // Current enriched location
    currentContext: null,

    // Map layer visibility
    mapLayersVisible: {
        speedLimits: false,
        trafficVolume: false,
        functionalClass: false
    },

    // Map layer data (GeoJSON)
    mapLayerData: {
        speedLimits: null,
        trafficVolume: null,
        functionalClass: null
    }
};
```

### Config Schema

Add to `config.json`:

```json
{
  "roadwayContext": {
    "enabled": true,
    "description": "Roadway attribute services for crash enrichment",
    "healthCheckOnStartup": true,
    "healthCheckTimeout": 5000,
    "queryTimeout": 8000,

    "cache": {
      "enabled": true,
      "dbName": "roadwayContextCache",
      "dbVersion": 1,
      "maxAge": {
        "speedLimits": 604800000,
        "trafficVolume": 2592000000,
        "functionalClass": 2592000000,
        "locationEnrichment": 86400000
      },
      "maxEntries": 10000,
      "cleanupInterval": 3600000
    },

    "services": {
      "speedLimits": {
        "enabled": true,
        "name": "Speed Limits",
        "description": "Posted speed limits on VDOT-maintained highways",
        "serviceUrl": "https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/VDOT_Posted_Speed_Limits/FeatureServer/0",
        "geometryType": "polyline",
        "spatialQuery": {
          "buffer": 30,
          "bufferUnit": "meters",
          "spatialRel": "esriSpatialRelIntersects"
        },
        "fields": {
          "carSpeed": {
            "name": "CAR_SPEED",
            "alias": "Speed Limit",
            "type": "integer",
            "unit": "mph"
          },
          "truckSpeed": {
            "name": "TRUCK_SPEED",
            "alias": "Truck Speed Limit",
            "type": "integer",
            "unit": "mph"
          },
          "zoneType": {
            "name": "SPEEDZONE_TYPE",
            "alias": "Zone Type",
            "type": "string"
          }
        },
        "displayField": "carSpeed",
        "mapLayer": {
          "enabled": true,
          "style": "speed-gradient",
          "colorRamp": {
            "15": "#22c55e",
            "25": "#84cc16",
            "35": "#eab308",
            "45": "#f97316",
            "55": "#ef4444",
            "65": "#dc2626"
          },
          "lineWidth": 3,
          "opacity": 0.7
        }
      },

      "trafficVolume": {
        "enabled": true,
        "name": "Traffic Volume (AADT)",
        "description": "Annual Average Daily Traffic counts",
        "serviceUrl": "https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/VDOT_Bidirectional_Traffic_Volume/FeatureServer/0",
        "geometryType": "polyline",
        "spatialQuery": {
          "buffer": 50,
          "bufferUnit": "meters",
          "spatialRel": "esriSpatialRelIntersects"
        },
        "fields": {
          "aadt": {
            "name": "AADT",
            "alias": "AADT",
            "type": "integer",
            "unit": "vpd"
          },
          "aadtYear": {
            "name": "AADT_YEAR",
            "alias": "Count Year",
            "type": "integer"
          }
        },
        "displayField": "aadt",
        "thresholds": {
          "veryLow": 1000,
          "low": 5000,
          "medium": 15000,
          "high": 30000,
          "veryHigh": 50000
        },
        "mapLayer": {
          "enabled": true,
          "style": "volume-width",
          "widthRamp": {
            "1000": 1,
            "5000": 2,
            "15000": 3,
            "30000": 4,
            "50000": 5
          },
          "color": "#3b82f6",
          "opacity": 0.6
        }
      },

      "functionalClass": {
        "enabled": true,
        "name": "Functional Classification",
        "description": "Federal functional classification of roadways",
        "serviceUrl": "https://vdotgisuportal.vdot.virginia.gov/env/rest/services/VDOT_Map/Virginia_Tech_LRS_Routes/FeatureServer/4",
        "geometryType": "polyline",
        "spatialQuery": {
          "buffer": 30,
          "bufferUnit": "meters",
          "spatialRel": "esriSpatialRelIntersects"
        },
        "fields": {
          "funcClass": {
            "name": "FUNC_CLASS",
            "alias": "Functional Class Code",
            "type": "integer"
          },
          "funcClassDesc": {
            "name": "FUNC_CLASS_DESC",
            "alias": "Functional Class",
            "type": "string"
          }
        },
        "displayField": "funcClassDesc",
        "categories": {
          "1": { "name": "Interstate", "color": "#dc2626" },
          "2": { "name": "Other Freeways & Expressways", "color": "#ea580c" },
          "3": { "name": "Other Principal Arterial", "color": "#ca8a04" },
          "4": { "name": "Minor Arterial", "color": "#65a30d" },
          "5": { "name": "Major Collector", "color": "#0891b2" },
          "6": { "name": "Minor Collector", "color": "#7c3aed" },
          "7": { "name": "Local", "color": "#6b7280" }
        },
        "mapLayer": {
          "enabled": true,
          "style": "categorical",
          "lineWidth": 2,
          "opacity": 0.7
        }
      }
    },

    "deficiencyRules": {
      "enabled": true,
      "rules": [
        {
          "id": "high_speed_ped_no_infra",
          "name": "High-Speed Road Missing Pedestrian Infrastructure",
          "description": "Locations with speed >= 40 mph, pedestrian crashes, but no pedestrian facilities",
          "severity": "HIGH",
          "conditions": {
            "speedLimit": { "gte": 40 },
            "pedestrianCrashes": { "gte": 2 },
            "requiredAssets": ["crosswalk", "sidewalk", "pedestrian_signal"],
            "hasRequiredAssets": false
          },
          "recommendations": [
            { "action": "Install marked crosswalk with advance warning signs", "cmfRange": "0.50-0.70" },
            { "action": "Add pedestrian refuge island", "cmfRange": "0.44-0.56" },
            { "action": "Install RRFB (Rectangular Rapid Flashing Beacon)", "cmfRange": "0.47" },
            { "action": "Consider speed limit reduction", "cmfRange": "0.71-0.93" }
          ]
        },
        {
          "id": "high_volume_no_signal",
          "name": "High-Volume Intersection Without Signal Control",
          "description": "Intersections with AADT >= 15,000 and angle crashes but no traffic signal",
          "severity": "HIGH",
          "conditions": {
            "aadt": { "gte": 15000 },
            "locationType": "intersection",
            "angleCrashes": { "gte": 3 },
            "requiredAssets": ["traffic_signal"],
            "hasRequiredAssets": false
          },
          "recommendations": [
            { "action": "Conduct traffic signal warrant analysis (MUTCD)", "cmfRange": "N/A" },
            { "action": "Install modern roundabout", "cmfRange": "0.52-0.65" },
            { "action": "Add left-turn lanes", "cmfRange": "0.73" },
            { "action": "Install all-way stop control", "cmfRange": "0.45-0.75" }
          ]
        },
        {
          "id": "arterial_nighttime_no_lighting",
          "name": "Arterial Corridor with High Nighttime Crash Rate",
          "description": "Arterial roads (FC 1-4) where >40% of crashes occur in dark conditions",
          "severity": "MEDIUM",
          "conditions": {
            "funcClass": { "lte": 4 },
            "nighttimeCrashPercent": { "gte": 0.4 },
            "requiredAssets": ["street_light", "roadway_lighting"],
            "hasRequiredAssets": false
          },
          "recommendations": [
            { "action": "Install continuous roadway lighting", "cmfRange": "0.72" },
            { "action": "Add retroreflective signage and delineation", "cmfRange": "0.85" },
            { "action": "Install raised pavement markers", "cmfRange": "0.90" }
          ]
        },
        {
          "id": "high_speed_bike_no_facility",
          "name": "High-Speed Road with Bicycle Crashes",
          "description": "Roads with speed >= 35 mph and bicycle crashes but no bike facilities",
          "severity": "MEDIUM",
          "conditions": {
            "speedLimit": { "gte": 35 },
            "bicycleCrashes": { "gte": 2 },
            "requiredAssets": ["bike_lane", "shared_use_path", "cycle_track"],
            "hasRequiredAssets": false
          },
          "recommendations": [
            { "action": "Install separated bike lane or cycle track", "cmfRange": "0.44-0.56" },
            { "action": "Add bike lane with buffer", "cmfRange": "0.55" },
            { "action": "Consider road diet with bike lanes", "cmfRange": "0.47" }
          ]
        },
        {
          "id": "rear_end_no_turn_lane",
          "name": "Rear-End Crash Pattern Without Turn Lanes",
          "description": "Locations with high rear-end crashes but no dedicated turn lanes",
          "severity": "MEDIUM",
          "conditions": {
            "rearEndCrashes": { "gte": 5 },
            "rearEndPercent": { "gte": 0.5 },
            "requiredAssets": ["left_turn_lane", "right_turn_lane"],
            "hasRequiredAssets": false
          },
          "recommendations": [
            { "action": "Add left-turn lane", "cmfRange": "0.73" },
            { "action": "Add right-turn lane", "cmfRange": "0.86" },
            { "action": "Extend existing turn lane storage", "cmfRange": "0.85" }
          ]
        }
      ]
    }
  }
}
```

### IndexedDB Cache Schema

```javascript
// Database: roadwayContextCache
// Version: 1

const DB_SCHEMA = {
    name: 'roadwayContextCache',
    version: 1,
    stores: {
        speedLimits: {
            keyPath: 'cacheKey',
            indexes: [
                { name: 'timestamp', keyPath: 'timestamp' },
                { name: 'route', keyPath: 'route' }
            ]
        },
        trafficVolume: {
            keyPath: 'cacheKey',
            indexes: [
                { name: 'timestamp', keyPath: 'timestamp' },
                { name: 'route', keyPath: 'route' }
            ]
        },
        functionalClass: {
            keyPath: 'cacheKey',
            indexes: [
                { name: 'timestamp', keyPath: 'timestamp' },
                { name: 'route', keyPath: 'route' }
            ]
        },
        locationEnrichments: {
            keyPath: 'locationKey',
            indexes: [
                { name: 'timestamp', keyPath: 'timestamp' }
            ]
        }
    }
};

// Cache key format: lat_lng (rounded to 4 decimal places)
// Example: "37.5407_-77.4360"
```

---

## Implementation Phases

### Phase 1: Configuration & Core Infrastructure

**Duration:** 1-2 days
**Priority:** Critical - Foundation for all other phases

#### Tasks

1. **Update config.json**
   - Add `roadwayContext` configuration block
   - Include all service endpoints, field mappings, and options
   - Add deficiency rules configuration

2. **Create State Object**
   - Add `roadwayContextState` to global state
   - Initialize on app load

3. **Implement IndexedDB Cache**
   - Create database initialization function
   - Implement CRUD operations
   - Add cache cleanup/expiration logic

4. **Add Health Check System**
   - Query each service endpoint on startup
   - Store availability status
   - Display status in UI (subtle indicator)

#### Code Structure

```
index.html additions:
├── Section: ROADWAY CONTEXT SERVICES
│   ├── State: roadwayContextState
│   ├── Function: initRoadwayContext()
│   ├── Function: openRoadwayContextDB()
│   ├── Function: checkRoadwayServicesHealth()
│   ├── Function: getRoadwayCache()
│   ├── Function: setRoadwayCache()
│   └── Function: cleanupRoadwayCache()
```

#### Acceptance Criteria

- [ ] Config loads without errors
- [ ] IndexedDB creates successfully
- [ ] Health check runs on startup
- [ ] Service status logged to console
- [ ] No impact on existing functionality

---

### Phase 2: Enrichment Service & Query Functions

**Duration:** 2-3 days
**Priority:** Critical - Core functionality

#### Tasks

1. **Implement Polyline Query Function**
   - Query ArcGIS service at point location
   - Handle buffer/distance parameters
   - Parse response and extract fields
   - Handle errors gracefully

2. **Create Unified Enrichment Function**
   - Query all enabled services in parallel
   - Combine results into single context object
   - Cache results
   - Return even if some services fail

3. **Add Retry Logic**
   - Exponential backoff for failed requests
   - Timeout handling
   - Fallback to cached data if available

#### Core Functions

```javascript
/**
 * Query a single roadway service at a point location
 * @param {string} serviceKey - 'speedLimits', 'trafficVolume', or 'functionalClass'
 * @param {number} lat - Latitude
 * @param {number} lng - Longitude
 * @returns {Promise<Object|null>} - Service data or null if failed
 */
async function queryRoadwayService(serviceKey, lat, lng) { ... }

/**
 * Enrich a location with all available roadway context
 * @param {number} lat - Latitude
 * @param {number} lng - Longitude
 * @param {string} [route] - Optional route name for cache key
 * @returns {Promise<Object>} - Unified context object
 */
async function enrichLocationContext(lat, lng, route = null) { ... }

/**
 * Get roadway context for current CMF/Warrants selection
 * Uses existing selection state to determine location
 * @returns {Promise<Object>} - Context object
 */
async function getRoadwayContextForSelection() { ... }
```

#### Expected Output Format

```javascript
// Return value from enrichLocationContext()
{
    available: true,
    timestamp: 1705500000000,
    location: {
        lat: 37.5407,
        lng: -77.4360,
        route: "US-60"
    },
    speedLimits: {
        carSpeed: 45,
        truckSpeed: 45,
        zoneType: "Resolution"
    },
    trafficVolume: {
        aadt: 18500,
        aadtYear: 2023
    },
    functionalClass: {
        funcClass: 4,
        funcClassDesc: "Urban Minor Arterial"
    },
    services: {
        speedLimits: { success: true, cached: false, responseTime: 245 },
        trafficVolume: { success: true, cached: true, responseTime: 2 },
        functionalClass: { success: false, error: "Timeout", responseTime: null }
    }
}
```

#### Acceptance Criteria

- [ ] Can query each service individually
- [ ] Parallel queries complete efficiently (<1s typical)
- [ ] Results cached correctly
- [ ] Cached results returned when fresh
- [ ] Graceful handling of service failures
- [ ] Console logging for debugging

---

### Phase 3: CMF Tab Integration

**Duration:** 2-3 days
**Priority:** High - Primary user value

#### Tasks

1. **Add Roadway Context Display Panel**
   - Show speed limit, AADT, functional class when location selected
   - Display data source indicators (live vs cached)
   - Handle missing data gracefully

2. **Implement CMF Filtering by Context**
   - Filter CMF list based on speed applicability
   - Filter based on road type (functional class)
   - Show filtering indicators

3. **Enhance AI Context**
   - Include roadway context in AI prompts
   - Update `getAIAnalysisContext()` function

4. **Add Warrants Tab Integration**
   - Display speed/volume for warrant analysis
   - Support MUTCD volume thresholds

#### UI Components

```html
<!-- Roadway Context Panel (CMF Tab) -->
<div id="cmfRoadwayContext" class="roadway-context-panel">
    <div class="rc-header">
        <span class="rc-icon">🛣️</span>
        <span class="rc-title">Roadway Characteristics</span>
        <button class="rc-refresh" onclick="refreshRoadwayContext()" title="Refresh data">
            <span class="rc-refresh-icon">↻</span>
        </button>
    </div>

    <div class="rc-grid">
        <div class="rc-item" id="rcSpeedLimit">
            <div class="rc-value-large">--</div>
            <div class="rc-label">Speed Limit (mph)</div>
            <div class="rc-source"></div>
        </div>

        <div class="rc-item" id="rcAADT">
            <div class="rc-value-large">--</div>
            <div class="rc-label">AADT</div>
            <div class="rc-source"></div>
        </div>

        <div class="rc-item" id="rcFuncClass">
            <div class="rc-value-text">--</div>
            <div class="rc-label">Road Type</div>
            <div class="rc-source"></div>
        </div>
    </div>

    <div class="rc-status" id="rcStatus">
        <!-- Status messages appear here -->
    </div>
</div>
```

#### CSS Styling

```css
/* Roadway Context Panel Styles */
.roadway-context-panel {
    background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
    border: 1px solid #0ea5e9;
    border-radius: 12px;
    padding: 1rem;
    margin-bottom: 1rem;
}

.rc-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid rgba(14, 165, 233, 0.2);
}

.rc-icon { font-size: 1.2rem; }

.rc-title {
    font-weight: 600;
    color: #0369a1;
    flex: 1;
}

.rc-refresh {
    background: none;
    border: none;
    cursor: pointer;
    padding: 0.25rem;
    border-radius: 4px;
    color: #0ea5e9;
    transition: all 0.2s;
}

.rc-refresh:hover {
    background: rgba(14, 165, 233, 0.1);
}

.rc-refresh.loading .rc-refresh-icon {
    animation: spin 1s linear infinite;
}

.rc-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
}

.rc-item {
    text-align: center;
    padding: 0.5rem;
    background: white;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.rc-value-large {
    font-size: 1.5rem;
    font-weight: 700;
    color: #0c4a6e;
}

.rc-value-text {
    font-size: 0.9rem;
    font-weight: 600;
    color: #0c4a6e;
}

.rc-label {
    font-size: 0.75rem;
    color: #64748b;
    margin-top: 0.25rem;
}

.rc-source {
    font-size: 0.65rem;
    color: #94a3b8;
    margin-top: 0.25rem;
}

.rc-status {
    margin-top: 0.5rem;
    font-size: 0.75rem;
    color: #64748b;
}

.rc-status.error {
    color: #dc2626;
}

.rc-status.warning {
    color: #d97706;
}

@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}
```

#### Acceptance Criteria

- [ ] Context panel displays when location selected
- [ ] All three data points shown correctly
- [ ] Loading state while fetching
- [ ] Error handling for failed services
- [ ] CMF filtering works based on context
- [ ] AI context includes roadway data
- [ ] Warrants tab shows relevant data

---

### Phase 4: Asset Deficiency Integration

**Duration:** 3-4 days
**Priority:** High - Advanced functionality

#### Tasks

1. **Implement Deficiency Rules Engine**
   - Parse rules from config
   - Evaluate conditions against crash data + roadway context + assets
   - Generate deficiency findings

2. **Add UI for Roadway Deficiencies**
   - New section in Asset Deficiency panel
   - Deficiency cards with severity indicators
   - Recommended countermeasures with CMF ranges

3. **Integrate with Existing Asset Deficiency Flow**
   - Run roadway deficiency check when location analyzed
   - Combine with other deficiency types
   - Sort by severity

4. **Add Export Capability**
   - Include roadway deficiencies in reports
   - Add data sources to export

#### Rules Engine

```javascript
/**
 * Evaluate deficiency rules against location data
 * @param {Object} location - Location object with lat/lng
 * @param {Array} crashes - Crash records for location
 * @param {Array} existingAssets - Assets at/near location
 * @returns {Promise<Array>} - Array of deficiency findings
 */
async function detectRoadwayDeficiencies(location, crashes, existingAssets) {
    const context = await enrichLocationContext(location.lat, location.lng);
    if (!context.available) return [];

    const rules = window.appConfig?.roadwayContext?.deficiencyRules?.rules || [];
    const deficiencies = [];

    // Build crash profile
    const crashProfile = buildCrashProfileForDeficiency(crashes);

    // Evaluate each rule
    for (const rule of rules) {
        if (evaluateDeficiencyRule(rule, context, crashProfile, existingAssets)) {
            deficiencies.push({
                ruleId: rule.id,
                severity: rule.severity,
                title: rule.name,
                description: rule.description,
                context: {
                    speedLimit: context.speedLimits?.carSpeed,
                    aadt: context.trafficVolume?.aadt,
                    funcClass: context.functionalClass?.funcClassDesc,
                    crashProfile: crashProfile
                },
                recommendations: rule.recommendations,
                dataSource: 'VDOT Roadway Services + Crash Analysis',
                timestamp: Date.now()
            });
        }
    }

    return deficiencies;
}

/**
 * Evaluate a single deficiency rule
 */
function evaluateDeficiencyRule(rule, context, crashProfile, existingAssets) {
    const conditions = rule.conditions;

    // Check speed limit condition
    if (conditions.speedLimit) {
        const speed = context.speedLimits?.carSpeed;
        if (!speed) return false;
        if (conditions.speedLimit.gte && speed < conditions.speedLimit.gte) return false;
        if (conditions.speedLimit.lte && speed > conditions.speedLimit.lte) return false;
    }

    // Check AADT condition
    if (conditions.aadt) {
        const aadt = context.trafficVolume?.aadt;
        if (!aadt) return false;
        if (conditions.aadt.gte && aadt < conditions.aadt.gte) return false;
        if (conditions.aadt.lte && aadt > conditions.aadt.lte) return false;
    }

    // Check functional class condition
    if (conditions.funcClass) {
        const fc = context.functionalClass?.funcClass;
        if (!fc) return false;
        if (conditions.funcClass.gte && fc < conditions.funcClass.gte) return false;
        if (conditions.funcClass.lte && fc > conditions.funcClass.lte) return false;
    }

    // Check crash conditions
    if (conditions.pedestrianCrashes) {
        if (crashProfile.pedestrian < conditions.pedestrianCrashes.gte) return false;
    }
    if (conditions.bicycleCrashes) {
        if (crashProfile.bicycle < conditions.bicycleCrashes.gte) return false;
    }
    if (conditions.angleCrashes) {
        if (crashProfile.angle < conditions.angleCrashes.gte) return false;
    }
    if (conditions.rearEndCrashes) {
        if (crashProfile.rearEnd < conditions.rearEndCrashes.gte) return false;
    }
    if (conditions.nighttimeCrashPercent) {
        const pct = crashProfile.nighttime / crashProfile.total;
        if (pct < conditions.nighttimeCrashPercent.gte) return false;
    }

    // Check asset conditions
    if (conditions.requiredAssets && conditions.hasRequiredAssets === false) {
        const hasRequired = conditions.requiredAssets.some(assetType =>
            existingAssets.some(a => a.type === assetType || a.type?.includes(assetType))
        );
        if (hasRequired) return false; // Has required assets, so no deficiency
    }

    return true; // All conditions met
}
```

#### Acceptance Criteria

- [ ] Rules engine evaluates correctly
- [ ] Deficiencies display in UI
- [ ] Severity levels shown correctly
- [ ] Recommendations include CMF ranges
- [ ] Data sources documented
- [ ] Integrates with existing deficiency flow
- [ ] Export includes roadway deficiencies

---

### Phase 5: Map Overlay Layers (Optional)

**Duration:** 2-3 days
**Priority:** Medium - Enhancement

#### Tasks

1. **Add Layer Toggle Controls**
   - Checkbox toggles in map panel
   - Layer visibility state

2. **Implement Viewport-Based Loading**
   - Query service for current map bounds
   - Request GeoJSON format
   - Limit records for performance

3. **Render Polylines with Styling**
   - Speed: Color gradient by speed limit
   - Volume: Line width by AADT
   - Functional Class: Categorical colors

4. **Add Legends**
   - Dynamic legends based on visible layers
   - Click to toggle

#### Performance Considerations

```javascript
// Debounce map move events
let mapMoveTimeout = null;
map.on('moveend', () => {
    clearTimeout(mapMoveTimeout);
    mapMoveTimeout = setTimeout(() => {
        refreshVisibleRoadwayLayers();
    }, 500);
});

// Limit features per layer
const MAX_FEATURES_PER_LAYER = 2000;

// Simplify geometry at low zoom levels
function getGeometryPrecision(zoom) {
    if (zoom < 12) return 4;  // ~10m precision
    if (zoom < 14) return 5;  // ~1m precision
    return 6;                  // ~0.1m precision
}
```

#### Acceptance Criteria

- [ ] Toggle controls work correctly
- [ ] Layers load on toggle
- [ ] Styling applied correctly
- [ ] Performance acceptable (no freeze)
- [ ] Legends display
- [ ] Layers clear when toggled off

---

### Phase 6: Multi-State Adaptation

**Duration:** 1-2 days
**Priority:** Medium - Future-proofing

#### Tasks

1. **Create State Configuration Templates**
   - Virginia (current)
   - Template for new states
   - Documentation

2. **Add Admin UI for Endpoint Configuration**
   - Settings panel for service URLs
   - Field mapping interface
   - Test connection button

3. **Document Onboarding Process**
   - How to find state DOT services
   - Required fields mapping
   - Testing procedure

#### State Template Structure

```
config/
├── states/
│   ├── virginia.json       # Current production config
│   ├── north_carolina.json # Example template
│   ├── maryland.json       # Example template
│   └── template.json       # Blank template with instructions
```

#### Template File

```json
{
  "_template_version": "1.0",
  "_instructions": "Copy this file and fill in your state's service URLs and field mappings",

  "state": {
    "name": "YOUR STATE NAME",
    "abbreviation": "XX",
    "dataPortal": "https://your-state-gis-portal.gov"
  },

  "roadwayContext": {
    "enabled": true,
    "services": {
      "speedLimits": {
        "enabled": true,
        "serviceUrl": "PASTE_YOUR_SPEED_LIMITS_SERVICE_URL_HERE",
        "fields": {
          "carSpeed": { "name": "YOUR_SPEED_FIELD_NAME" },
          "truckSpeed": { "name": "YOUR_TRUCK_SPEED_FIELD_NAME_OR_NULL" }
        },
        "_findingInstructions": "Search your state GIS portal for 'speed limit' or 'posted speed'"
      },

      "trafficVolume": {
        "enabled": true,
        "serviceUrl": "PASTE_YOUR_AADT_SERVICE_URL_HERE",
        "fields": {
          "aadt": { "name": "YOUR_AADT_FIELD_NAME" },
          "aadtYear": { "name": "YOUR_COUNT_YEAR_FIELD_NAME" }
        },
        "_findingInstructions": "Search for 'traffic volume', 'AADT', or 'traffic count'"
      },

      "functionalClass": {
        "enabled": true,
        "serviceUrl": "PASTE_YOUR_FUNCTIONAL_CLASS_SERVICE_URL_HERE",
        "fields": {
          "funcClass": { "name": "YOUR_FUNC_CLASS_CODE_FIELD" },
          "funcClassDesc": { "name": "YOUR_FUNC_CLASS_DESC_FIELD" }
        },
        "_findingInstructions": "Search for 'functional classification' or 'road type'"
      }
    }
  }
}
```

#### Acceptance Criteria

- [ ] Template files created
- [ ] Admin UI functional
- [ ] Test connection works
- [ ] Documentation complete
- [ ] At least one other state template created as example

---

## Technical Specifications

### API Query Format

```javascript
// Standard ArcGIS REST API query for point-to-polyline intersection
const queryUrl = new URL(`${serviceUrl}/query`);
queryUrl.searchParams.set('geometry', JSON.stringify({
    x: lng,
    y: lat,
    spatialReference: { wkid: 4326 }
}));
queryUrl.searchParams.set('geometryType', 'esriGeometryPoint');
queryUrl.searchParams.set('spatialRel', 'esriSpatialRelIntersects');
queryUrl.searchParams.set('distance', bufferMeters);
queryUrl.searchParams.set('units', 'esriSRUnit_Meter');
queryUrl.searchParams.set('outFields', fieldList);
queryUrl.searchParams.set('returnGeometry', 'false');
queryUrl.searchParams.set('f', 'json');
```

### Error Handling

```javascript
const ERROR_TYPES = {
    NETWORK: 'Network error - check internet connection',
    TIMEOUT: 'Service timeout - try again later',
    SERVICE_ERROR: 'Service returned an error',
    NO_DATA: 'No data found at this location',
    INVALID_RESPONSE: 'Invalid response from service',
    CORS: 'Cross-origin request blocked'
};

function handleRoadwayServiceError(error, serviceKey) {
    let errorType = 'UNKNOWN';
    let userMessage = 'An error occurred';

    if (error.name === 'AbortError') {
        errorType = 'TIMEOUT';
        userMessage = 'Request timed out';
    } else if (error.message?.includes('Failed to fetch')) {
        errorType = 'NETWORK';
        userMessage = 'Network error';
    } else if (error.message?.includes('CORS')) {
        errorType = 'CORS';
        userMessage = 'Service access blocked';
    }

    console.warn(`[RoadwayContext] ${serviceKey} error:`, errorType, error.message);

    return {
        success: false,
        errorType,
        userMessage,
        details: error.message
    };
}
```

### Performance Targets

| Operation | Target | Maximum |
|-----------|--------|---------|
| Single service query | <300ms | 1000ms |
| Full enrichment (3 services) | <500ms | 2000ms |
| Cache read | <10ms | 50ms |
| Cache write | <20ms | 100ms |
| Map layer load (viewport) | <1000ms | 3000ms |

### Browser Support

| Browser | Minimum Version | Notes |
|---------|-----------------|-------|
| Chrome | 80+ | Full support |
| Firefox | 75+ | Full support |
| Safari | 13.1+ | Full support |
| Edge | 80+ | Full support |
| IE | Not supported | No IndexedDB |

---

## Risk Assessment & Mitigation

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Service downtime | Medium | Medium | Cache layer, graceful degradation |
| Endpoint URL changes | Low-Medium | High | Config-driven URLs, health checks |
| Rate limiting | Low | Low | Query throttling, caching |
| Schema changes | Low | Medium | Field validation on startup |
| CORS issues | Low | High | Verify services allow CORS |
| Performance degradation | Low | Medium | Viewport limiting, pagination |

### Mitigation Strategies

#### 1. Service Unavailability

```javascript
// Graceful degradation pattern
async function enrichWithFallback(lat, lng) {
    const context = await enrichLocationContext(lat, lng);

    // Check if any services failed
    const failed = Object.entries(context.services || {})
        .filter(([k, v]) => !v.success)
        .map(([k]) => k);

    if (failed.length > 0) {
        // Try cache for failed services
        for (const serviceKey of failed) {
            const cached = await getStaleCache(serviceKey, lat, lng);
            if (cached) {
                context[serviceKey] = cached.data;
                context.services[serviceKey] = { success: true, cached: true, stale: true };
            }
        }
    }

    return context;
}
```

#### 2. URL Change Detection

```javascript
// Health check with schema validation
async function validateServiceSchema(serviceKey) {
    const config = window.appConfig?.roadwayContext?.services?.[serviceKey];
    if (!config) return false;

    try {
        const metaUrl = `${config.serviceUrl}?f=json`;
        const response = await fetch(metaUrl, { signal: AbortSignal.timeout(5000) });
        const meta = await response.json();

        // Validate expected fields exist
        const expectedFields = Object.values(config.fields).map(f => f.name);
        const actualFields = (meta.fields || []).map(f => f.name);

        const missingFields = expectedFields.filter(f => !actualFields.includes(f));

        if (missingFields.length > 0) {
            console.warn(`[RoadwayContext] ${serviceKey} missing fields:`, missingFields);
            return false;
        }

        return true;
    } catch (error) {
        console.error(`[RoadwayContext] ${serviceKey} validation failed:`, error);
        return false;
    }
}
```

---

## Testing Strategy

### Unit Tests

```javascript
// Test cases for rules engine
describe('Deficiency Rules Engine', () => {
    test('high speed + ped crashes + no infrastructure = deficiency', () => {
        const context = { speedLimits: { carSpeed: 45 } };
        const crashes = [{ PED: 'Y' }, { PED: 'Y' }, { PED: 'Y' }];
        const assets = [];

        const deficiencies = evaluateRules(context, crashes, assets);

        expect(deficiencies).toHaveLength(1);
        expect(deficiencies[0].ruleId).toBe('high_speed_ped_no_infra');
        expect(deficiencies[0].severity).toBe('HIGH');
    });

    test('high speed + ped crashes + has crosswalk = no deficiency', () => {
        const context = { speedLimits: { carSpeed: 45 } };
        const crashes = [{ PED: 'Y' }, { PED: 'Y' }, { PED: 'Y' }];
        const assets = [{ type: 'crosswalk' }];

        const deficiencies = evaluateRules(context, crashes, assets);

        expect(deficiencies).toHaveLength(0);
    });
});
```

### Integration Tests

| Test Case | Steps | Expected Result |
|-----------|-------|-----------------|
| Basic enrichment | Select location on map | Context panel shows speed, AADT, FC |
| Cache hit | Query same location twice | Second query returns cached data <10ms |
| Service failure | Disconnect network, query | Graceful error message, cached data if available |
| CMF filtering | Select 45mph location | Speed-inappropriate CMFs hidden |
| Deficiency detection | Analyze high-speed ped crash location | Ped infrastructure deficiency shown |

### Manual Testing Checklist

- [ ] Load app, verify health check runs
- [ ] Select location, verify context loads
- [ ] Check console for errors
- [ ] Toggle map layers on/off
- [ ] Test with slow network (throttle to 3G)
- [ ] Test with network offline
- [ ] Verify cache persists after refresh
- [ ] Test all deficiency rules trigger correctly
- [ ] Export report includes roadway data

---

## Multi-State Adaptation Guide

### Step 1: Find Your State's GIS Portal

Common state DOT GIS portals:
- Virginia: virginiaroads.org
- North Carolina: connect.ncdot.gov/resources/gis
- Maryland: geodata.md.gov
- Pennsylvania: gis.penndot.gov
- Texas: gis.txdot.gov

### Step 2: Search for Required Layers

Search terms to try:
- "speed limit" or "posted speed"
- "traffic volume" or "AADT"
- "functional classification" or "road type"

### Step 3: Get the Feature Service URL

1. Find the dataset page
2. Look for "API" or "Service URL" or "ArcGIS REST Services"
3. URL should end with `/FeatureServer/0` or `/MapServer/0`

### Step 4: Identify Field Names

1. Add `?f=json` to the service URL
2. Look at the `fields` array in the response
3. Find fields matching:
   - Speed limit (integer, mph)
   - Truck speed if available
   - AADT (integer)
   - Year of count
   - Functional class code and description

### Step 5: Test the Service

```bash
# Test query
curl "https://your-service-url/query?where=1=1&outFields=*&resultRecordCount=1&f=json"
```

### Step 6: Create Configuration

Copy `config/states/template.json` and fill in your values.

### Step 7: Validate

Use the Admin UI "Test Connection" button to validate each service.

---

## Appendix

### A. Complete Function Reference

| Function | Purpose | Location |
|----------|---------|----------|
| `initRoadwayContext()` | Initialize system on app load | Section 12 |
| `openRoadwayContextDB()` | Open IndexedDB cache | Section 12 |
| `checkRoadwayServicesHealth()` | Validate all service endpoints | Section 12 |
| `queryRoadwayService(key, lat, lng)` | Query single service | Section 12 |
| `enrichLocationContext(lat, lng)` | Get all context for location | Section 12 |
| `getRoadwayCache(key, cacheKey)` | Read from cache | Section 12 |
| `setRoadwayCache(key, cacheKey, data)` | Write to cache | Section 12 |
| `cleanupRoadwayCache()` | Remove expired entries | Section 12 |
| `updateRoadwayContextPanel(context)` | Update UI display | Section 12 |
| `filterCMFsByRoadwayContext(cmfs, context)` | Filter CMF list | Section 12 |
| `detectRoadwayDeficiencies(loc, crashes, assets)` | Run rules engine | Section 12 |
| `evaluateDeficiencyRule(rule, context, crashes, assets)` | Evaluate single rule | Section 12 |
| `toggleRoadwayLayer(key)` | Toggle map layer | Section 12 |
| `loadRoadwayLayerForViewport(key)` | Load layer data | Section 12 |
| `renderRoadwayGeoJSON(key, geojson)` | Render polylines | Section 12 |

### B. Configuration Reference

See full config schema in [Architecture Design](#config-schema) section.

### C. Known Service URLs by State

| State | Speed Limits | Traffic Volume | Functional Class |
|-------|--------------|----------------|------------------|
| Virginia | ✅ Documented | ✅ Documented | ✅ Documented |
| North Carolina | TBD | TBD | TBD |
| Maryland | TBD | TBD | TBD |

### D. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-17 | Initial plan created |

---

## Document Metadata

- **Author:** Claude Code Assistant
- **Created:** January 17, 2025
- **Last Updated:** January 17, 2025
- **Status:** Draft - Awaiting Implementation
- **Review Required:** Yes

---

*End of Implementation Plan*
