# Asset Deficiency Detection System - Implementation Plan

## Overview

The Asset Deficiency Detection system is an AI-powered infrastructure analysis feature that integrates multiple data sources to identify missing or deficient roadway infrastructure at crash locations and recommend evidence-based countermeasures.

**Location in UI**: CMF / Countermeasures Tab → Asset Deficiency (sub-tab)

### Why CMF Tab Placement?

The fundamental question Asset Deficiency answers is: *"What infrastructure is missing that's causing crashes, and what countermeasure should I install?"* This aligns directly with the CMF tab's purpose.

**Benefits of CMF Tab Integration:**
- **Natural workflow**: "What's missing?" → "What countermeasure fixes it?" in one place
- **Reuses existing AI infrastructure**: CMF tab already has multi-agent system
- **Unified recommendations**: Deficiency-based + crash-based recommendations together
- **User intent alignment**: Users come to CMF tab wanting "what to fix"
- **CMF database already loaded**: No need to load separately
- **Grant integration**: CMF tab already links to Grants

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Multi-Model AI Orchestration](#2-multi-model-ai-orchestration)
3. [Data Source Integration](#3-data-source-integration)
4. [FHWA Risk Factors](#4-fhwa-risk-factors)
5. [Deficiency Detection Rules](#5-deficiency-detection-rules)
6. [UI Design](#6-ui-design)
7. [Implementation Phases](#7-implementation-phases)
8. [API Specifications](#8-api-specifications)
9. [State Management](#9-state-management)
10. [Testing Strategy](#10-testing-strategy)

---

## 1. Architecture Overview

### System Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER LOCATION SELECTION                         │
│  (Map polygon / Dropdown selection / Coordinate entry)                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA AGGREGATION LAYER                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│  │   Crashes   │ │   Schools   │ │   Transit   │ │  Mapillary  │       │
│  │ (existing)  │ │ (existing)  │ │ (existing)  │ │ (polygon)   │       │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                       │
│  │  CSV Upload │ │   ArcGIS    │ │  Satellite  │                       │
│  │ (existing)  │ │ (existing)  │ │   Image     │                       │
│  └─────────────┘ └─────────────┘ └─────────────┘                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    MULTI-MODEL AI ANALYSIS                              │
│  GPT-4V (Detect) → Gemini (Verify) → Claude (Consensus)                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    DEFICIENCY DETECTION ENGINE                          │
│  Apply FHWA Risk Factors → Identify Gaps → Generate Recommendations     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         OUTPUT & REPORTING                              │
│  Risk Score → Deficiency List → CMF Recommendations → Export            │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Leverage Existing Infrastructure** - Use existing state objects, UI patterns, and data loaders
2. **Polygon-Scoped Queries** - All external queries limited to user selection (not jurisdiction-wide)
3. **Progressive Enhancement** - System works with minimal data, improves with more sources
4. **Source Priority** - ArcGIS > CSV Upload > Mapillary > Satellite AI
5. **Human Oversight** - AI detections flagged for validation, not auto-accepted

---

## 2. Multi-Model AI Orchestration

### Model Roles

| Model | Role | Strengths | API |
|-------|------|-----------|-----|
| **GPT-4V** | Primary Detector | Object detection, spatial reasoning, counting | OpenAI |
| **Gemini 1.5 Pro** | Verifier | Large context, structured validation | Google AI |
| **Claude** | Consensus + Logic | Reasoning, rule application, safety focus | Anthropic |

### Orchestration Flow

```
SATELLITE IMAGE (Esri Export)
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 1: GPT-4V PRIMARY DETECTION                                      │
│  ─────────────────────────────────                                      │
│  Input: Satellite image (base64)                                        │
│  Task: Detect ALL infrastructure elements                               │
│  Output: Structured JSON with detections + confidence levels            │
│                                                                         │
│  Detections:                                                            │
│  • Geometry: lane count, median type, turn lanes, shoulders, skew       │
│  • Pedestrian: crosswalks, sidewalks, refuge islands, curb ramps        │
│  • Traffic Control: signals, stop bars, lane markings                   │
│  • Context: land use, driveways, parking, lighting poles                │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 2: GEMINI VERIFICATION                                           │
│  ────────────────────────────                                           │
│  Input: Same image + GPT-4V output                                      │
│  Task: Independently verify, challenge LOW confidence items             │
│  Output: AGREE/DISAGREE/UNCERTAIN for each detection                    │
│                                                                         │
│  Focus Areas:                                                           │
│  • Verify lane counts match                                             │
│  • Confirm crosswalk presence/absence                                   │
│  • Check for missed features                                            │
│  • Flag inconsistencies                                                 │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 3: CLAUDE CONSENSUS + DEFICIENCY ENGINE                          │
│  ─────────────────────────────────────────────                          │
│  Input: GPT-4V output + Gemini verification + Crash data + Risk factors │
│  Tasks:                                                                 │
│  1. Resolve conflicts between Stage 1 & 2                               │
│  2. Apply FHWA risk factor rules                                        │
│  3. Cross-reference with crash patterns                                 │
│  4. Cross-reference with Mapillary/CSV/ArcGIS assets                    │
│  5. Generate deficiency findings                                        │
│  6. Match deficiencies to CMF countermeasures                           │
│  7. Calculate risk score (0-100)                                        │
│                                                                         │
│  Output: Final deficiency report with recommendations                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Consensus Rules

```
FOR each detected feature:

IF GPT-4V.confidence = HIGH AND Gemini = AGREE:
    → Accept (HIGH confidence)

IF GPT-4V.confidence = HIGH AND Gemini = DISAGREE:
    → Use Gemini's interpretation (MEDIUM confidence)
    → Flag for review

IF GPT-4V.confidence = MEDIUM/LOW AND Gemini = AGREE:
    → Accept (MEDIUM confidence)

IF GPT-4V.confidence = MEDIUM/LOW AND Gemini = DISAGREE:
    → Mark as UNCERTAIN
    → Exclude from deficiency detection
    → Flag for field verification

IF only one model detects:
    → Include (LOW confidence)
    → Flag for verification
```

### Cost Estimation

| Model | Cost per Image | Latency |
|-------|---------------|---------|
| GPT-4V | ~$0.01-0.03 | 3-5 sec |
| Gemini 1.5 Pro | ~$0.005-0.02 | 2-4 sec |
| Claude 3.5 Sonnet | ~$0.003-0.01 | 2-3 sec |
| **Total per location** | **~$0.02-0.06** | **7-12 sec** |

---

## 3. Data Source Integration

### Source Priority (Highest to Lowest)

1. **ArcGIS Service** - Agency authoritative data (if configured)
2. **Uploaded CSV** - User-provided asset inventory
3. **Mapillary Detection** - Street-level AI detection
4. **Satellite AI Detection** - Aerial view analysis

### Integration with Existing Modules

#### 3.1 School Safety Integration

```
Source: schoolTabState / assetState (type='school')
Trigger: Schools loaded via School Safety tab
Query: Schools within configurable radius (default 500m) of selected polygon

Data Available:
- School coordinates (lat/lng)
- School name and type (elementary, middle, high)
- Enrollment numbers
- Existing crash associations

Risk Factor Application:
- School within 300m → Check for school zone signs (S1-1, S4-3)
- School within 500m → Check for crosswalks, sidewalks
- High enrollment + crashes → Elevated priority
```

#### 3.2 Transit Safety Integration

```
Source: transitTabState / assetState (type='transit')
Trigger: Transit stops loaded via Transit Safety tab
Query: Stops within configurable radius (default 300m) of selected polygon

Data Available:
- Stop coordinates (lat/lng)
- Stop name and routes served
- Existing crash associations

Risk Factor Application:
- Stop within 150m + pedestrian crashes → Check ped facilities
- High-frequency stop → Check lighting, crosswalks
```

#### 3.3 CSV Upload Integration

```
Source: assetState.assets[] (type from user upload)
Trigger: User uploads asset inventory CSV
Query: Assets within selected polygon bounds

Expected CSV Fields:
- latitude/lat (required)
- longitude/lon/lng (required)
- asset_type/type (required)
- mutcd_code (optional)
- condition (optional)
- install_date (optional)

Use Case:
- Agency has sign inventory but not in ArcGIS
- Supplement Mapillary with known assets
- Override AI detections with ground truth
```

#### 3.4 ArcGIS Service Integration

```
Source: assetState.assets[] (loaded from ArcGIS)
Trigger: User configures ArcGIS feature service
Query: Features within selected polygon bounds

Priority: HIGHEST (authoritative agency data)

Use Case:
- VDOT road inventory data
- Agency-maintained asset database
- Official lane counts, median types, etc.
```

#### 3.5 Mapillary Integration (Polygon-Scoped)

```
Source: Mapillary Graph API
Trigger: User initiates Asset Deficiency analysis
Query: Assets within polygon bounding box + 500ft buffer

CRITICAL CHANGE from current implementation:
- Current: Downloads entire jurisdiction (slow, expensive)
- New: Downloads only within user's polygon selection (fast, cheap)

Query Parameters:
- bbox: polygon.bounds expanded by buffer
- object_values: [stop signs, signals, crosswalks, etc.]
- limit: 500 (sufficient for intersection analysis)

Asset Types to Query:
- Regulatory: stop, yield, speed limit, turn restrictions
- Warning: stop ahead, curve, pedestrian crossing, school
- Infrastructure: traffic signals, street lights, guardrails
- Markings: crosswalks, stop bars
```

#### 3.6 Satellite Image Capture

```
Source: Esri World Imagery (FREE, no token required)
Endpoint: https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export

Parameters:
- bbox: polygon.bounds (west,south,east,north)
- size: 800,600 (pixels)
- format: jpg
- f: image

Alternative: Mapbox Static API (requires token, higher resolution)
```

### Unified Asset Query Function

```javascript
// Conceptual structure
async function queryAssetsForLocation(polygon, options = {}) {
    const results = {
        crashes: [],
        schools: [],
        transitStops: [],
        mapillaryAssets: [],
        csvAssets: [],
        arcgisAssets: [],
        satelliteImage: null
    };

    // 1. Get crashes from crashState (always available)
    results.crashes = filterCrashesInPolygon(crashState.sampleRows, polygon);

    // 2. Query schools if School Safety data loaded
    if (schoolTabState.loaded) {
        results.schools = querySchoolsNearPolygon(polygon, options.schoolRadius || 500);
    }

    // 3. Query transit if Transit Safety data loaded
    if (transitTabState.loaded) {
        results.transitStops = queryTransitNearPolygon(polygon, options.transitRadius || 300);
    }

    // 4. Query CSV/ArcGIS assets if loaded
    results.csvAssets = queryAssetsInPolygon(assetState.assets, polygon, 'csv');
    results.arcgisAssets = queryAssetsInPolygon(assetState.assets, polygon, 'arcgis');

    // 5. Fetch Mapillary assets (polygon-scoped)
    if (options.includeMapillary) {
        results.mapillaryAssets = await fetchMapillaryForPolygon(polygon);
    }

    // 6. Capture satellite image
    if (options.includeSatellite) {
        results.satelliteImage = await captureSatelliteImage(polygon);
    }

    return results;
}
```

---

## 4. FHWA Risk Factors

Based on FHWA PE6 Systemic Safety guidance document.

### 4.1 Roadway Departure Risk Factors

| Risk Factor | Detectable Via | Detection Method |
|-------------|---------------|------------------|
| Number of lanes | Satellite, ArcGIS | AI vision, inventory |
| Lane width | ArcGIS | Inventory data |
| Shoulder width/type | Satellite, ArcGIS | AI vision, inventory |
| Median width/type | Satellite, ArcGIS | AI vision, inventory |
| Horizontal curvature | Satellite | AI vision geometry |
| Delineation | Mapillary | Sign detection |
| Advance warning | Mapillary | Sign detection |
| Clear zone | Satellite | AI vision |
| Driveway density | Satellite | AI vision counting |
| Rumble strips | Mapillary | Object detection |
| Lighting | Satellite, Mapillary | Pole detection |

### 4.2 Intersection Risk Factors

| Risk Factor | Detectable Via | Detection Method |
|-------------|---------------|------------------|
| Traffic control device | Mapillary, Satellite | Sign/signal detection |
| Left-turn lanes | Satellite | AI lane analysis |
| Right-turn lanes | Satellite | AI lane analysis |
| Skew angle | Satellite | AI geometry analysis |
| Advance warning signs | Mapillary | Sign detection |
| Near horizontal curve | Satellite | AI geometry |
| Land use type | Satellite | AI context analysis |
| Signal configuration | Mapillary | Object detection |

### 4.3 Pedestrian Risk Factors

| Risk Factor | Detectable Via | Detection Method |
|-------------|---------------|------------------|
| Crosswalk (marked/unmarked) | Satellite, Mapillary | AI marking detection |
| Sidewalk presence | Satellite | AI vision |
| Pedestrian signal | Mapillary | Object detection |
| Curb ramps | Satellite (limited) | AI vision |
| Refuge island | Satellite | AI vision |
| Adjacent land use | Satellite | AI context |
| Lighting | Satellite, Mapillary | Pole detection |

### 4.4 Bicycle Risk Factors

| Risk Factor | Detectable Via | Detection Method |
|-------------|---------------|------------------|
| Bike lane presence | Satellite, Mapillary | AI marking/sign detection |
| Shoulder width | Satellite, ArcGIS | AI vision, inventory |
| Number of lanes | Satellite | AI vision |
| Parking type | Satellite | AI vision |
| Access density | Satellite | AI counting |

### 4.5 Contextual Risk Factors

| Risk Factor | Detectable Via | Detection Method |
|-------------|---------------|------------------|
| School proximity | School Safety tab | Distance calculation |
| Transit stop proximity | Transit Safety tab | Distance calculation |
| Commercial land use | Satellite | AI context |
| Alcohol establishments | External data | Future enhancement |

---

## 5. Deficiency Detection Rules

### 5.1 Rule Structure

```javascript
const DEFICIENCY_RULES = {
    rule_id: {
        name: "Human-readable name",
        description: "What this deficiency means",
        crash_types: ["applicable", "crash", "types"],
        triggers: {
            // Conditions that must be true
            condition1: "expression",
            condition2: "expression"
        },
        data_sources: ["satellite", "mapillary", "school", "transit", "crash"],
        severity: "CRITICAL|HIGH|MEDIUM|LOW",
        countermeasure_ids: ["cmf_1", "cmf_2"],
        fhwa_reference: "PE6 page X"
    }
};
```

### 5.2 Intersection Deficiency Rules

```javascript
// No traffic control at intersection with angle crashes
"int_no_control": {
    name: "Missing Traffic Control",
    description: "No stop sign or signal detected at intersection with angle crashes",
    crash_types: ["angle", "intersection"],
    triggers: {
        mapillary_no_stop: "!mapillary.has('stop') && !mapillary.has('signal')",
        satellite_no_signal: "!satellite.signals.present",
        angle_crashes: "crashes.filter(c => c.type === 'angle').length >= 2"
    },
    severity: "HIGH",
    countermeasure_ids: ["install_stop_sign", "install_signal"],
    fhwa_reference: "PE6 page 18"
},

// No left-turn lane with rear-end/angle crashes
"int_no_ltl": {
    name: "Missing Left-Turn Lane",
    description: "No dedicated left-turn lane on approach with turn-related crashes",
    crash_types: ["angle", "rear_end"],
    triggers: {
        satellite_no_ltl: "!satellite.geometry.left_turn_lanes.present",
        relevant_crashes: "crashes.filter(c => ['angle','rear_end'].includes(c.type)).length >= 3"
    },
    severity: "MEDIUM",
    countermeasure_ids: ["add_left_turn_lane"],
    fhwa_reference: "PE6 page 18"
},

// Skewed intersection
"int_skewed": {
    name: "Skewed Intersection",
    description: "Intersection angle significantly deviates from 90 degrees",
    crash_types: ["angle", "sideswipe"],
    triggers: {
        satellite_skewed: "satellite.geometry.skew_angle.value === 'significantly_skewed'",
        any_crashes: "crashes.length >= 1"
    },
    severity: "MEDIUM",
    countermeasure_ids: ["realign_intersection", "add_warning_signs"],
    fhwa_reference: "PE6 page 18"
}
```

### 5.3 Pedestrian Deficiency Rules

```javascript
// No crosswalk with pedestrian crashes
"ped_no_crosswalk": {
    name: "Missing Crosswalk",
    description: "No marked crosswalk detected at location with pedestrian crashes",
    crash_types: ["pedestrian"],
    triggers: {
        mapillary_no_xwalk: "!mapillary.has('crosswalk')",
        satellite_no_xwalk: "!satellite.pedestrian.crosswalks.present",
        ped_crashes: "crashes.filter(c => c.ped === 'Y').length >= 1"
    },
    severity: "HIGH",
    countermeasure_ids: ["install_crosswalk", "install_rrfb"],
    fhwa_reference: "PE6 page 19"
},

// No sidewalk
"ped_no_sidewalk": {
    name: "Missing Sidewalk",
    description: "Sidewalk absent on one or both sides with pedestrian activity",
    crash_types: ["pedestrian"],
    triggers: {
        satellite_no_sidewalk: "!satellite.pedestrian.sidewalk_north_east.present || !satellite.pedestrian.sidewalk_south_west.present",
        ped_crashes: "crashes.filter(c => c.ped === 'Y').length >= 1"
    },
    severity: "HIGH",
    countermeasure_ids: ["install_sidewalk"],
    fhwa_reference: "PE6 page 19"
},

// Wide crossing without refuge
"ped_no_refuge": {
    name: "Missing Pedestrian Refuge",
    description: "Wide crossing (4+ lanes) without pedestrian refuge island",
    crash_types: ["pedestrian"],
    triggers: {
        wide_crossing: "satellite.geometry.major_road_lanes.value >= 4",
        no_refuge: "!satellite.pedestrian.refuge_island.present",
        ped_crashes: "crashes.filter(c => c.ped === 'Y').length >= 1"
    },
    severity: "MEDIUM",
    countermeasure_ids: ["install_refuge_island"],
    fhwa_reference: "PE6 page 19"
}
```

### 5.4 School Proximity Rules

```javascript
// School nearby without school zone treatment
"school_no_zone": {
    name: "Missing School Zone Treatment",
    description: "School within 300m without school zone signage detected",
    crash_types: ["pedestrian", "bicycle", "speed"],
    triggers: {
        school_nearby: "schools.filter(s => s.distance <= 300).length >= 1",
        no_school_signs: "!mapillary.has('school_zone') && !mapillary.has('school_crossing')"
    },
    severity: "CRITICAL",
    countermeasure_ids: ["install_school_zone_package"],
    fhwa_reference: "PE6 page 21"
},

// School nearby without crosswalk
"school_no_crosswalk": {
    name: "School Area Missing Crosswalk",
    description: "School within 500m without marked crosswalk",
    crash_types: ["pedestrian"],
    triggers: {
        school_nearby: "schools.filter(s => s.distance <= 500).length >= 1",
        no_crosswalk: "!satellite.pedestrian.crosswalks.present"
    },
    severity: "HIGH",
    countermeasure_ids: ["install_crosswalk", "install_school_crossing"],
    fhwa_reference: "PE6 page 21"
}
```

### 5.5 Transit Proximity Rules

```javascript
// Transit stop with pedestrian safety concerns
"transit_ped_risk": {
    name: "Transit Stop Pedestrian Risk",
    description: "Transit stop nearby with pedestrian crashes and missing facilities",
    crash_types: ["pedestrian"],
    triggers: {
        transit_nearby: "transitStops.filter(t => t.distance <= 150).length >= 1",
        ped_crashes: "crashes.filter(c => c.ped === 'Y').length >= 2",
        missing_facilities: "!satellite.pedestrian.crosswalks.present || !satellite.pedestrian.sidewalk_north_east.present"
    },
    severity: "HIGH",
    countermeasure_ids: ["install_crosswalk", "install_sidewalk", "improve_lighting"],
    fhwa_reference: "PE6 page 21"
}
```

### 5.6 Roadway Departure Rules

```javascript
// No shoulders with departure crashes
"rd_no_shoulder": {
    name: "Missing or Narrow Shoulders",
    description: "Shoulders absent or narrow (<2ft) with roadway departure crashes",
    crash_types: ["roadway_departure"],
    triggers: {
        narrow_shoulders: "satellite.geometry.shoulders.width === 'none' || satellite.geometry.shoulders.width === 'narrow'",
        rd_crashes: "crashes.filter(c => c.type === 'roadway_departure').length >= 2"
    },
    severity: "HIGH",
    countermeasure_ids: ["widen_shoulders", "install_rumble_strips"],
    fhwa_reference: "PE6 page 17"
},

// Poor clear zone
"rd_poor_clearzone": {
    name: "Inadequate Clear Zone",
    description: "Fixed objects present in clear zone with roadway departure crashes",
    crash_types: ["roadway_departure"],
    triggers: {
        poor_clearzone: "!satellite.safety_features.clear_zone.adequate",
        rd_crashes: "crashes.filter(c => c.type === 'roadway_departure').length >= 1"
    },
    severity: "HIGH",
    countermeasure_ids: ["install_guardrail", "remove_hazards"],
    fhwa_reference: "PE6 page 17"
}
```

### 5.7 Lighting Rules

```javascript
// Dark location without lighting
"lighting_missing": {
    name: "Missing Roadway Lighting",
    description: "High proportion of dark-condition crashes without street lighting",
    crash_types: ["all"],
    triggers: {
        dark_crashes: "crashes.filter(c => c.light.includes('DARK')).length / crashes.length >= 0.5",
        no_lighting: "!satellite.safety_features.street_lights.present && !mapillary.has('street_light')"
    },
    severity: "HIGH",
    countermeasure_ids: ["install_lighting"],
    fhwa_reference: "PE6 page 17"
}
```

---

## 6. UI Design

### 6.1 Tab Placement

```
CMF / Countermeasures Tab
├── 📍 Location Selection (existing)
├── 📊 Crash Profile (existing)
├── 💡 CMF Recommendations (existing)
├── 🔍 Asset Deficiency         ← NEW SUB-TAB
│   ├── Data Sources Panel
│   ├── AI Analysis Controls
│   └── Deficiency Results
│       └── [Links to CMF Recommendations above]
│
└── 📋 Selected Countermeasures (existing)
```

**Integration with CMF Tab Workflow:**
1. User selects location → Crash profile loads (existing behavior)
2. User clicks "Asset Deficiency" sub-tab
3. System aggregates data sources (crashes, schools, transit, Mapillary, satellite)
4. Multi-model AI analyzes infrastructure
5. Deficiencies identified → Automatically mapped to CMF countermeasures
6. User can add recommendations to Selected Countermeasures list

### 6.2 Main Interface Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  🔍 Asset Deficiency Detection                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  LOCATION SELECTION                                    [Clear]  │    │
│  │                                                                 │    │
│  │  ● Use current map selection                                    │    │
│  │    📍 Main St & Oak Ave (8 crashes, 2 KA)                       │    │
│  │                                                                 │    │
│  │  ○ Enter coordinates                                            │    │
│  │    Lat: [_________]  Lng: [_________]  Radius: [500] ft         │    │
│  │                                                                 │    │
│  │  ○ Select from dropdown                                         │    │
│  │    Route: [Select ▼]  Intersection: [Select ▼]                  │    │
│  │                                                                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  DATA SOURCES                                    [Load All ▶]   │    │
│  │                                                                 │    │
│  │  ☑ Crash Data              ✅ 8 crashes loaded                  │    │
│  │  ☑ School Proximity        ✅ Lincoln Elementary (245m)         │    │
│  │  ☑ Transit Proximity       ✅ 2 stops within 300m               │    │
│  │  ☑ Mapillary Assets        ⏳ Loading... (12 assets)            │    │
│  │  ☐ CSV Inventory           ⚪ Not loaded                        │    │
│  │  ☐ ArcGIS Features         ⚪ Not configured                    │    │
│  │  ☑ Satellite Image         ✅ Captured                          │    │
│  │                                                                 │    │
│  │  [ℹ️ Load School/Transit data from their respective tabs]       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  AI ANALYSIS                                 [Run Analysis ▶]   │    │
│  │                                                                 │    │
│  │  Models:                                                        │    │
│  │  ☑ GPT-4V (Primary detection)                                   │    │
│  │  ☑ Gemini (Verification)                                        │    │
│  │  ☑ Claude (Consensus + Recommendations)                         │    │
│  │                                                                 │    │
│  │  Estimated cost: ~$0.05  |  Estimated time: ~10 seconds         │    │
│  │                                                                 │    │
│  │  API Keys: [Configure in Settings → API Keys]                   │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Results Display

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ANALYSIS RESULTS                                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  RISK SCORE                                                     │    │
│  │                                                                 │    │
│  │  ████████████████████████░░░░░░░░  72/100  [HIGH RISK]          │    │
│  │                                                                 │    │
│  │  Components:                                                    │    │
│  │  • Crash Severity: 38/50 (1 fatal, 2 serious injury)            │    │
│  │  • Deficiencies: 24/35 (4 deficiencies found)                   │    │
│  │  • Proximity: 10/15 (school within 300m)                        │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  DETECTED INFRASTRUCTURE                              [Expand]  │    │
│  │                                                                 │    │
│  │  Geometry:                                                      │    │
│  │  • Lanes: 4 total (2 each direction)          HIGH confidence   │    │
│  │  • Median: None                               HIGH confidence   │    │
│  │  • Left-turn lanes: Not present              MEDIUM confidence  │    │
│  │  • Shoulders: Narrow (<4ft)                  MEDIUM confidence  │    │
│  │                                                                 │    │
│  │  Traffic Control:                                               │    │
│  │  • Signal: Present (overhead)                 HIGH confidence   │    │
│  │  • Stop bars: Visible                        MEDIUM confidence  │    │
│  │                                                                 │    │
│  │  Pedestrian:                                                    │    │
│  │  • Crosswalks: NOT DETECTED                   HIGH confidence   │    │
│  │  • Sidewalk (N/E): Present                   MEDIUM confidence  │    │
│  │  • Sidewalk (S/W): NOT DETECTED               HIGH confidence   │    │
│  │                                                                 │    │
│  │  Context:                                                       │    │
│  │  • Land use: Commercial                       HIGH confidence   │    │
│  │  • School: Lincoln Elem (245m)               CONFIRMED          │    │
│  │  • Transit: 2 stops (89m, 156m)              CONFIRMED          │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  DEFICIENCIES DETECTED (4)                           [Expand]   │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │                                                                 │    │
│  │  🔴 CRITICAL: Missing School Zone Treatment                     │    │
│  │     Lincoln Elementary within 245m, no school signs detected    │    │
│  │     Source: School Safety + Mapillary                           │    │
│  │     FHWA Reference: PE6 page 21                                 │    │
│  │     ┌─────────────────────────────────────────────────────┐     │    │
│  │     │ Recommended: Install School Zone Package            │     │    │
│  │     │ CMF: 0.80 | Cost: $5,000-$15,000                    │     │    │
│  │     │ Expected reduction: 0.6 crashes/year                │     │    │
│  │     └─────────────────────────────────────────────────────┘     │    │
│  │     [View on Map] [Add to CMF Tab] [Add to Grant]               │    │
│  │                                                                 │    │
│  │  ─────────────────────────────────────────────────────────────  │    │
│  │                                                                 │    │
│  │  🔴 HIGH: Missing Crosswalk                                     │    │
│  │     No marked crosswalk, 2 pedestrian crashes, school nearby    │    │
│  │     Source: Satellite AI + Mapillary (confirmed)                │    │
│  │     FHWA Reference: PE6 page 19                                 │    │
│  │     ┌─────────────────────────────────────────────────────┐     │    │
│  │     │ Recommended: Install High-Visibility Crosswalk      │     │    │
│  │     │ CMF: 0.75 | Cost: $2,500-$5,000                     │     │    │
│  │     │ Expected reduction: 0.5 ped crashes/year            │     │    │
│  │     └─────────────────────────────────────────────────────┘     │    │
│  │     [View on Map] [Add to CMF Tab] [Add to Grant]               │    │
│  │                                                                 │    │
│  │  ─────────────────────────────────────────────────────────────  │    │
│  │                                                                 │    │
│  │  🟡 MEDIUM: Missing Left-Turn Lane                              │    │
│  │     4-lane road, no turn lane, 3 angle crashes                  │    │
│  │     Source: Satellite AI                                        │    │
│  │     FHWA Reference: PE6 page 18                                 │    │
│  │     ┌─────────────────────────────────────────────────────┐     │    │
│  │     │ Recommended: Add Left-Turn Lane                     │     │    │
│  │     │ CMF: 0.72 | Cost: $100,000-$500,000                 │     │    │
│  │     │ Expected reduction: 0.8 crashes/year                │     │    │
│  │     └─────────────────────────────────────────────────────┘     │    │
│  │     [View on Map] [Add to CMF Tab] [Add to Grant]               │    │
│  │                                                                 │    │
│  │  ─────────────────────────────────────────────────────────────  │    │
│  │                                                                 │    │
│  │  🟡 MEDIUM: Missing Sidewalk (South/West side)                  │    │
│  │     Sidewalk absent, pedestrian crashes present                 │    │
│  │     Source: Satellite AI                                        │    │
│  │     FHWA Reference: PE6 page 19                                 │    │
│  │     ┌─────────────────────────────────────────────────────┐     │    │
│  │     │ Recommended: Install Sidewalk                       │     │    │
│  │     │ CMF: 0.65 | Cost: $50-$100/linear foot              │     │    │
│  │     │ Expected reduction: 0.3 ped crashes/year            │     │    │
│  │     └─────────────────────────────────────────────────────┘     │    │
│  │     [View on Map] [Add to CMF Tab] [Add to Grant]               │    │
│  │                                                                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  ACTIONS                                                        │    │
│  │                                                                 │    │
│  │  [📄 Export PDF Report]  [📊 Export JSON]  [🗺️ View All on Map] │    │
│  │                                                                 │    │
│  │  [↗️ Send to CMF Tab]  [↗️ Add to Grant Application]            │    │
│  │                                                                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.4 Map Integration Popup

When user selects location on map, add "Asset Deficiency" option:

```
┌─────────────────────────────────────────┐
│  📍 Main St & Oak Ave                   │
│  8 crashes (2 KA) in selection          │
│                                         │
│  [View Crashes]  [CMF Analysis]         │
│  [Warrants]      [🔍 Asset Deficiency]  │  ← NEW BUTTON
└─────────────────────────────────────────┘
```

---

## 7. Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Objective**: Basic infrastructure without AI

| Task | Description | Dependencies |
|------|-------------|--------------|
| 1.1 | Create `assetDeficiencyState` object | None |
| 1.2 | Add "Asset Deficiency" sub-tab in CMF/Countermeasures | Existing CMF tab structure |
| 1.3 | Implement location selection UI | `selectionState` |
| 1.4 | Implement polygon-scoped Mapillary query | Existing Mapillary functions |
| 1.5 | Create `queryAssetsForLocation()` function | School/Transit states |
| 1.6 | Implement school proximity query | `schoolTabState` |
| 1.7 | Implement transit proximity query | `transitTabState` |
| 1.8 | Add satellite image capture (Esri) | None |

**Deliverable**: Tab that aggregates all data sources for a selected location

### Phase 2: Single-Model AI (Week 3)

**Objective**: GPT-4V analysis working

| Task | Description | Dependencies |
|------|-------------|--------------|
| 2.1 | Create satellite image analysis prompt | Phase 1 |
| 2.2 | Implement GPT-4V API integration | API key config |
| 2.3 | Parse structured JSON response | None |
| 2.4 | Display detected infrastructure | Phase 1 UI |
| 2.5 | Basic deficiency detection (without consensus) | Deficiency rules |

**Deliverable**: Working single-model analysis with results display

### Phase 3: Multi-Model Orchestration (Week 4)

**Objective**: Full GPT-4V → Gemini → Claude pipeline

| Task | Description | Dependencies |
|------|-------------|--------------|
| 3.1 | Implement Gemini verification API call | Phase 2 |
| 3.2 | Create verification prompt | None |
| 3.3 | Implement Claude consensus API call | Phase 2 |
| 3.4 | Create consensus + deficiency prompt | Deficiency rules |
| 3.5 | Implement consensus logic | None |
| 3.6 | Aggregate results from all models | Phases 3.1-3.4 |

**Deliverable**: Full multi-model pipeline working

### Phase 4: Deficiency Engine (Week 5)

**Objective**: Complete deficiency detection with CMF integration

| Task | Description | Dependencies |
|------|-------------|--------------|
| 4.1 | Implement all deficiency rules | Phase 3 |
| 4.2 | Integrate with CMF database | Existing CMF functions |
| 4.3 | Calculate expected crash reductions | CMF data |
| 4.4 | Implement risk scoring algorithm | Phase 4.1 |
| 4.5 | Create deficiency results UI | Phase 1 UI |

**Deliverable**: Complete deficiency detection with recommendations

### Phase 5: Integration & Polish (Week 6)

**Objective**: Cross-tab integration and export

| Task | Description | Dependencies |
|------|-------------|--------------|
| 5.1 | "Add to CMF Tab" functionality | CMF tab |
| 5.2 | "Add to Grant" functionality | Grants tab |
| 5.3 | "View on Map" functionality | Map tab |
| 5.4 | Map popup integration | Map tab |
| 5.5 | PDF report export | None |
| 5.6 | JSON export | None |
| 5.7 | Result caching (localStorage) | None |

**Deliverable**: Fully integrated feature with all export options

### Phase 6: Testing & Validation (Week 7)

| Task | Description | Dependencies |
|------|-------------|--------------|
| 6.1 | Test with various location types | All phases |
| 6.2 | Validate deficiency rules accuracy | Phase 4 |
| 6.3 | Test API error handling | Phases 2-3 |
| 6.4 | Test with missing data sources | Phase 1 |
| 6.5 | Performance optimization | All phases |
| 6.6 | User acceptance testing | All phases |

---

## 8. API Specifications

### 8.1 Satellite Image Capture

```
Endpoint: Esri World Imagery Export
URL: https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export

Parameters:
- bbox: {west},{south},{east},{north} (WGS84)
- size: 800,600
- format: jpg
- f: image
- bboxSR: 4326
- imageSR: 4326

Response: JPEG image (binary)

Cost: FREE (no authentication required)
```

### 8.2 GPT-4V Analysis

```
Endpoint: https://api.openai.com/v1/chat/completions
Method: POST
Headers:
  - Authorization: Bearer {OPENAI_API_KEY}
  - Content-Type: application/json

Request Body:
{
  "model": "gpt-4-vision-preview",
  "max_tokens": 4096,
  "messages": [{
    "role": "user",
    "content": [
      {
        "type": "image_url",
        "image_url": {
          "url": "data:image/jpeg;base64,{BASE64_IMAGE}"
        }
      },
      {
        "type": "text",
        "text": "{DETECTION_PROMPT}"
      }
    ]
  }]
}

Response: JSON with structured detections
```

### 8.3 Gemini Verification

```
Endpoint: https://generativelanguage.googleapis.com/v1/models/gemini-1.5-pro:generateContent
Method: POST
Headers:
  - Content-Type: application/json
  - x-goog-api-key: {GOOGLE_API_KEY}

Request Body:
{
  "contents": [{
    "parts": [
      {
        "inline_data": {
          "mime_type": "image/jpeg",
          "data": "{BASE64_IMAGE}"
        }
      },
      {
        "text": "{VERIFICATION_PROMPT_WITH_GPT4V_OUTPUT}"
      }
    ]
  }],
  "generationConfig": {
    "maxOutputTokens": 4096
  }
}

Response: JSON with verification results
```

### 8.4 Claude Consensus

```
Endpoint: https://api.anthropic.com/v1/messages
Method: POST
Headers:
  - Content-Type: application/json
  - x-api-key: {ANTHROPIC_API_KEY}
  - anthropic-version: 2023-06-01

Request Body:
{
  "model": "claude-sonnet-4-20250514",
  "max_tokens": 4096,
  "messages": [{
    "role": "user",
    "content": [
      {
        "type": "image",
        "source": {
          "type": "base64",
          "media_type": "image/jpeg",
          "data": "{BASE64_IMAGE}"
        }
      },
      {
        "type": "text",
        "text": "{CONSENSUS_PROMPT_WITH_ALL_DATA}"
      }
    ]
  }]
}

Response: JSON with final analysis and deficiencies
```

### 8.5 Mapillary Polygon Query

```
Endpoint: https://graph.mapillary.com/map_features
Method: GET
Headers:
  - Authorization: OAuth {MAPILLARY_TOKEN}

Parameters:
- fields: id,object_value,geometry,first_seen_at,last_seen_at
- bbox: {west},{south},{east},{north}
- object_values: regulatory--stop--g1,regulatory--yield--g1,...
- limit: 500

Response: GeoJSON FeatureCollection
```

---

## 9. State Management

### 9.1 New State Object

```javascript
const assetDeficiencyState = {
    // Initialization
    initialized: false,

    // Location
    location: {
        type: null,              // 'polygon' | 'point' | 'dropdown'
        bounds: null,            // [west, south, east, north]
        centroid: null,          // {lat, lng}
        name: null,              // Display name
        radius: 500              // Feet (for point selection)
    },

    // Data Sources (loaded status)
    sources: {
        crashes: { loaded: false, count: 0, data: [] },
        schools: { loaded: false, count: 0, data: [] },
        transit: { loaded: false, count: 0, data: [] },
        mapillary: { loaded: false, count: 0, data: [] },
        csv: { loaded: false, count: 0, data: [] },
        arcgis: { loaded: false, count: 0, data: [] },
        satellite: { loaded: false, imageData: null }
    },

    // AI Analysis
    analysis: {
        running: false,
        stage: null,             // 'gpt4v' | 'gemini' | 'claude'
        gpt4vResult: null,
        geminiResult: null,
        claudeResult: null,
        consensusResult: null,
        error: null
    },

    // Results
    results: {
        timestamp: null,
        infrastructure: {},      // Detected infrastructure
        deficiencies: [],        // Identified deficiencies
        recommendations: [],     // CMF-backed recommendations
        riskScore: null,         // 0-100
        riskCategory: null       // 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
    },

    // UI State
    ui: {
        expandedSections: [],
        selectedDeficiency: null
    }
};
```

### 9.2 Integration with Existing States

```javascript
// Read from existing states (do not modify)
crashState.sampleRows          // Source for crash data
schoolTabState.results         // Source for school data
transitTabState.results        // Source for transit data (when implemented)
assetState.assets              // Source for CSV/ArcGIS data
selectionState                 // Source for user selection
cmfState.selectedLocation      // Current CMF tab location selection
cmfState.filteredCrashes       // Location + date filtered crashes
cmfState.crashProfile          // Already-computed crash profile

// Write to for integration features
cmfState.recommendations       // Add deficiency-based CMF recommendations
grantState                     // When "Add to Grant"
```

**CMF Tab Integration Notes:**
- Asset Deficiency is a sub-tab within CMF/Countermeasures
- Inherits location selection from `cmfState.selectedLocation`
- Uses `cmfState.filteredCrashes` for crash analysis (already filtered by location + date)
- Deficiency recommendations automatically appear in CMF recommendations panel
- User can seamlessly add to Selected Countermeasures list

---

## 10. Testing Strategy

### 10.1 Unit Tests

| Component | Test Cases |
|-----------|------------|
| `queryAssetsForLocation()` | Polygon filtering, empty results, mixed sources |
| Consensus logic | All agreement, all disagreement, mixed |
| Risk score calculation | Edge cases, max/min values |
| Deficiency rules | Each rule individually |

### 10.2 Integration Tests

| Scenario | Test Cases |
|----------|------------|
| Full pipeline | Location → Data load → AI analysis → Results |
| Missing data | No schools, no transit, no Mapillary |
| API failures | GPT-4V timeout, Gemini error, rate limits |
| Cross-tab | Add to CMF, Add to Grant, View on Map |

### 10.3 Location Type Tests

| Location Type | Characteristics |
|---------------|-----------------|
| Urban signalized intersection | 4+ lanes, signals, crosswalks |
| Rural stop-controlled intersection | 2 lanes, stop signs, no sidewalks |
| School zone | School nearby, ped infrastructure |
| Transit corridor | Multiple stops, high ped activity |
| Curve segment | Horizontal curve, departure crashes |

### 10.4 Validation Checklist

- [ ] Deficiency counts match across UI elements
- [ ] Risk score calculation is consistent
- [ ] CMF values match clearinghouse
- [ ] School distances are accurate
- [ ] Transit distances are accurate
- [ ] Mapillary assets are within bounds
- [ ] AI confidence levels are reasonable
- [ ] Consensus logic produces expected results

---

## Appendix A: Satellite Analysis Prompt (GPT-4V)

```
You are an expert traffic safety engineer analyzing a satellite/aerial image of a road location.

Analyze this image and identify infrastructure elements for safety assessment. For each element, provide your detection and confidence level.

## ANALYZE THESE ELEMENTS:

### ROAD GEOMETRY:
- Lane count on major road (each direction)
- Lane count on minor road (each direction, if intersection)
- Median type: none, painted/TWLTL, raised curb, grass/landscaped
- Left-turn lanes: present or absent (each approach)
- Right-turn lanes: present or absent (each approach)
- Shoulder presence and approximate width: none, narrow (<4ft), standard (4-8ft), wide (>8ft)
- Intersection type (if applicable): T-intersection, 4-way, 5+ leg, roundabout, not an intersection
- Skew angle: appears perpendicular (85-95°), slightly skewed (70-85°), significantly skewed (<70°)

### PEDESTRIAN INFRASTRUCTURE:
- Crosswalk markings: none visible, standard parallel lines, high-visibility continental/ladder
- Sidewalk on north/east side: present, absent, partial
- Sidewalk on south/west side: present, absent, partial
- Curb ramps/ADA features: visible, not visible, cannot determine
- Pedestrian refuge island in median: present, absent, not applicable
- Curb extensions/bulb-outs: present, absent

### TRAFFIC CONTROL (visible from aerial):
- Stop bars/limit lines: visible, not visible
- Lane markings condition: clear/good, faded/fair, poor/missing
- Turn arrows painted: present, absent
- Crosswalk markings condition: clear, faded, not present

### SAFETY FEATURES:
- Street light poles visible: yes (count estimate), no
- Guardrail/barrier: present, absent
- Clear zone assessment: adequate (no fixed objects near road), restricted (buildings/poles/trees close to road)

### CONTEXT:
- Land use type: residential, commercial/retail, industrial, school/institutional, mixed, rural
- Driveway density: low (0-2 visible), medium (3-5), high (6+)
- On-street parking: present, absent
- Parking lots adjacent: yes, no
- Transit stop/shelter visible: yes, no

## RESPONSE FORMAT:

Respond ONLY with valid JSON in this exact structure:
{
  "geometry": {
    "major_road_lanes": {"value": 2, "confidence": "HIGH"},
    "minor_road_lanes": {"value": 2, "confidence": "MEDIUM"},
    "median_type": {"value": "none", "confidence": "HIGH"},
    "left_turn_lanes": {"present": false, "approaches_with_ltl": [], "confidence": "MEDIUM"},
    "right_turn_lanes": {"present": false, "approaches_with_rtl": [], "confidence": "MEDIUM"},
    "shoulders": {"present": false, "width": "none", "confidence": "HIGH"},
    "intersection_type": {"value": "4-way", "legs": 4, "confidence": "HIGH"},
    "skew_angle": {"value": "perpendicular", "confidence": "HIGH"}
  },
  "pedestrian": {
    "crosswalks": {"present": false, "type": "none", "count": 0, "confidence": "HIGH"},
    "sidewalk_north_east": {"present": false, "confidence": "MEDIUM"},
    "sidewalk_south_west": {"present": false, "confidence": "MEDIUM"},
    "curb_ramps": {"visible": false, "confidence": "LOW"},
    "refuge_island": {"present": false, "confidence": "HIGH"},
    "curb_extensions": {"present": false, "confidence": "HIGH"}
  },
  "traffic_control": {
    "stop_bars": {"visible": true, "confidence": "MEDIUM"},
    "lane_markings": {"present": true, "condition": "good", "confidence": "MEDIUM"},
    "turn_arrows": {"present": false, "confidence": "MEDIUM"}
  },
  "safety_features": {
    "street_lights": {"present": true, "count_estimate": 2, "confidence": "MEDIUM"},
    "guardrail": {"present": false, "confidence": "HIGH"},
    "clear_zone": {"adequate": false, "hazards": ["utility poles", "trees"], "confidence": "MEDIUM"}
  },
  "context": {
    "land_use": {"value": "commercial", "confidence": "HIGH"},
    "driveway_density": {"value": "medium", "count_estimate": 4, "confidence": "MEDIUM"},
    "on_street_parking": {"present": true, "confidence": "MEDIUM"},
    "parking_lots": {"present": true, "confidence": "HIGH"},
    "transit_stop": {"visible": false, "confidence": "MEDIUM"}
  },
  "overall_assessment": "Brief 1-2 sentence summary of key observations"
}
```

---

## Appendix B: Countermeasure Database

Link deficiencies to countermeasures from existing CMF database:

| Deficiency | Countermeasure | CMF | Cost Range |
|------------|---------------|-----|------------|
| No crosswalk | Install High-Visibility Crosswalk | 0.75 | $2,500-$5,000 |
| No school zone signs | Install School Zone Package | 0.80 | $5,000-$15,000 |
| No left-turn lane | Add Left-Turn Lane | 0.72 | $100,000-$500,000 |
| No sidewalk | Install Sidewalk | 0.65 | $50-$100/LF |
| No refuge island | Install Pedestrian Refuge | 0.68 | $10,000-$40,000 |
| No lighting | Install Roadway Lighting | 0.72 | $5,000-$10,000/pole |
| No guardrail | Install Guardrail | 0.55 | $25-$35/LF |
| No stop sign | Install Stop Sign | 0.60 | $200-$500 |
| No advance warning | Install Advance Warning Signs | 0.88 | $300-$600 |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-16 | Claude | Initial implementation plan |
| 1.1 | 2026-01-16 | Claude | Moved from Analysis tab to CMF/Countermeasures tab for natural workflow integration |

---

## References

1. FHWA Systemic Safety Project Selection Tool (PE6)
2. FHWA CMF Clearinghouse
3. Virginia DMV Crash Data Documentation
4. Mapillary API Documentation
5. Esri World Imagery Service Documentation
