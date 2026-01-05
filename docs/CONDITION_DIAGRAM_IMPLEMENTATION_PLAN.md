# Condition Diagram Implementation Plan

## Multi-Model AI Street View & Satellite Analysis with SVG Intersection Diagram

**Created:** January 5, 2026
**Feature Location:** Street View AI Tab > New "Condition Diagram" Subtab (after Bicycle)
**Primary Goal:** Generate accurate, direction-based infrastructure inventory with SVG intersection visualization

---

## 1. Executive Summary

This plan outlines the implementation of an advanced **Condition Diagram** feature that combines:

1. **Multi-Model AI Consensus** for maximum accuracy
   - Street View: 3 models (GPT-4V as master, Gemini, Claude)
   - Satellite View: 2 models (GPT-4V as master, Gemini)
2. **Distance-Based Image Capture** at strategic intervals
3. **Direction-Specific Inventory** (Northbound, Eastbound, Southbound, Westbound)
4. **SVG-Based Intersection Diagram** auto-generated from AI analysis
5. **Mapbox Satellite Integration** for lane geometry verification

### Key Innovation

The 2-of-3 (Street View) and 2-of-2 (Satellite) consensus approach ensures **high accuracy** by requiring model agreement before including any detected feature in the final inventory.

---

## 2. Multi-Model Architecture

### 2.1 Model Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                      GPT-4V (MASTER MODEL)                      │
│  • Primary detection authority                                  │
│  • Highest spatial reasoning accuracy (76.3% benchmark)         │
│  • Final arbiter when models disagree                          │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│     Gemini Pro Vision     │   │      Claude Vision        │
│  (VALIDATOR + SATELLITE)  │   │      (VALIDATOR)          │
│  • Natively multimodal    │   │  • Strong reasoning       │
│  • Good for aerial views  │   │  • Detail-oriented        │
│  • Used in both analyses  │   │  • Street View only       │
└───────────────────────────┘   └───────────────────────────┘
```

### 2.2 Model Assignment by Image Type

| Image Type | Models Used | Consensus Requirement |
|------------|-------------|----------------------|
| **Street View** | GPT-4V + Gemini + Claude | 2 of 3 must agree |
| **Satellite** | GPT-4V + Gemini | 2 of 2 must agree (both) |

### 2.3 Consensus Decision Matrix

#### Street View (3 Models)

| GPT-4V | Gemini | Claude | Result | Confidence |
|--------|--------|--------|--------|------------|
| ✓ | ✓ | ✓ | **INCLUDE** | HIGH |
| ✓ | ✓ | ✗ | **INCLUDE** | HIGH |
| ✓ | ✗ | ✓ | **INCLUDE** | HIGH |
| ✗ | ✓ | ✓ | **INCLUDE** | MEDIUM (flag for review) |
| ✓ | ✗ | ✗ | **EXCLUDE** | Master-only detection |
| ✗ | ✓ | ✗ | **EXCLUDE** | Single validator |
| ✗ | ✗ | ✓ | **EXCLUDE** | Single validator |
| ✗ | ✗ | ✗ | **EXCLUDE** | Not detected |

#### Satellite (2 Models)

| GPT-4V | Gemini | Result | Confidence |
|--------|--------|--------|------------|
| ✓ | ✓ | **INCLUDE** | HIGH |
| ✓ | ✗ | **EXCLUDE** | No consensus |
| ✗ | ✓ | **EXCLUDE** | No consensus |
| ✗ | ✗ | **EXCLUDE** | Not detected |

### 2.4 Why This Model Selection

| Model | Strengths | Role |
|-------|-----------|------|
| **GPT-4V** | Best spatial reasoning (76.3%), precise counting, excellent at sign reading | Master for both |
| **Gemini Pro Vision** | Natively multimodal, excellent for aerial/satellite imagery, fast | Validator + Satellite specialist |
| **Claude Vision** | Strong reasoning, good at describing context, catches subtle details | Street View validator only |

---

## 3. Distance Interval Specifications

### 3.1 Street View Capture Strategy

Based on AASHTO sight distance requirements and research on optimal street-level imagery intervals.

#### Intersection Capture Points

```
                         500ft (Far Approach)
                              │
                              ▼ [Capture: looking toward center]
                         300ft (Mid Approach)
                              │
                              ▼ [Capture: looking toward center]
                         ─────┼───── CENTER (0ft)
                              │      [Capture: 4 cardinal directions]
                              │
                         300ft (Mid Approach)
                              │
                         500ft (Far Approach)
```

#### Street View Distance Configuration

```javascript
const STREET_VIEW_CAPTURE = {
    intersection: {
        center: {
            distance: 0,
            headings: [0, 90, 180, 270],  // N, E, S, W
            pitch: 10,
            fov: 90
        },
        approaches: [
            {
                distance: 300,  // feet
                description: "Mid-approach - lane config, signals visible",
                lookDirection: "toward_center",
                pitch: 5,
                fov: 90
            },
            {
                distance: 500,  // feet
                description: "Far approach - advance signs, sight distance",
                lookDirection: "toward_center",
                pitch: 0,
                fov: 90
            }
        ]
    },
    imagesPerIntersection: {
        center: 4,           // 4 directions
        perApproach: 2,      // 300ft + 500ft
        totalApproaches: 4,  // N, E, S, W
        total: 12            // 4 + (2 × 4) = 12 images
    }
};
```

#### Why These Distances?

| Distance | Purpose | Captures |
|----------|---------|----------|
| **0 ft (Center)** | Intersection geometry | Signal heads, crosswalks, corner features, ADA ramps |
| **300 ft** | Mid-approach view | Lane configuration, pavement markings, signal visibility |
| **500 ft** | Far approach (AASHTO ISD) | Advance warning signs, sight distance assessment, approach context |

### 3.2 Satellite View Capture Strategy

Unlike Street View which uses physical distance, satellite imagery uses **zoom levels** and **offset positions**.

#### Satellite Capture Configuration

```javascript
const SATELLITE_CAPTURE = {
    intersection: {
        overview: {
            zoom: 18,
            offset: { lat: 0, lng: 0 },
            description: "Overall intersection geometry, ~200m view",
            captureSize: "640x640"
        },
        detail: {
            zoom: 19,
            offset: { lat: 0, lng: 0 },
            description: "Lane details, crosswalks, ~100m view",
            captureSize: "640x640"
        },
        approaches: {
            zoom: 19,
            offsetDistance: 150,  // feet from center
            description: "Approach-specific lane details",
            directions: ['N', 'E', 'S', 'W']
        }
    },
    imagesPerIntersection: {
        overview: 1,         // Zoom 18 center
        detail: 1,           // Zoom 19 center
        approaches: 4,       // One per direction at offset
        total: 6             // 1 + 1 + 4 = 6 satellite images
    }
};
```

#### Satellite Zoom Level Reference

| Zoom | Ground Coverage | Best For |
|------|-----------------|----------|
| **17** | ~400m | Wide area context |
| **18** | ~200m | Intersection overview, leg identification |
| **19** | ~100m | Lane count, turn lanes, median type |
| **20** | ~50m | Pavement markings, crosswalk details |

#### Why Satellite Approach Offsets?

Offsetting 150ft along each approach at zoom 19 provides:
- Clear view of approach lane configuration
- Turn lane pocket lengths
- Median nose locations
- Better angle for pavement marking visibility

### 3.3 Combined Capture Summary

| Image Type | Count | Purpose |
|------------|-------|---------|
| Street View Center | 4 | Intersection features from eye level |
| Street View 300ft | 4 | Mid-approach infrastructure |
| Street View 500ft | 4 | Far approach, advance signs |
| Satellite Overview (Z18) | 1 | Overall geometry |
| Satellite Detail (Z19) | 1 | Lane configuration |
| Satellite Approaches (Z19) | 4 | Direction-specific lanes |
| **TOTAL** | **18 images** | |

### 3.4 API Calls Summary

| Analysis Type | Images | Models | API Calls |
|---------------|--------|--------|-----------|
| Street View | 12 | 3 (GPT-4V, Gemini, Claude) | 36 |
| Satellite | 6 | 2 (GPT-4V, Gemini) | 12 |
| **TOTAL** | **18** | | **48 API calls** |

---

## 4. Detection Categories

### 4.1 Street View Detection Categories

#### Traffic Control Devices

```javascript
const TRAFFIC_CONTROL = {
    signals: {
        type: ['standard_3section', 'protected_left', 'flashing', 'pedestrian', 'bicycle'],
        heads_per_approach: Number,
        backplates: Boolean,
        LED: Boolean
    },
    signs: {
        regulatory: ['stop', 'yield', 'speed_limit', 'no_turn', 'one_way', 'do_not_enter'],
        warning: ['signal_ahead', 'stop_ahead', 'curve', 'intersection', 'pedestrian', 'school'],
        guide: ['street_name', 'route_marker', 'destination']
    },
    pavement_markings: ['stop_bar', 'crosswalk', 'turn_arrows', 'lane_lines', 'edge_lines']
};
```

#### Infrastructure Elements

```javascript
const INFRASTRUCTURE = {
    lanes: {
        through_lanes: Number,
        left_turn_lanes: Number,
        right_turn_lanes: Number,
        bike_lanes: Boolean,
        lane_width: String  // 'narrow', 'standard', 'wide'
    },
    median: {
        type: ['none', 'painted', 'raised', 'landscaped'],
        width: String,
        turn_bay: Boolean
    },
    shoulders: {
        present: Boolean,
        width: String,
        type: ['paved', 'gravel', 'none']
    },
    sidewalks: {
        present: Boolean,
        width: String,
        buffer: Boolean,
        condition: String
    },
    curb_ramps: {
        present: Boolean,
        ada_compliant: String,  // 'yes', 'no', 'unclear'
        tactile_warning: Boolean
    },
    street_lights: {
        present: Boolean,
        type: ['standard', 'decorative', 'cobra_head'],
        spacing: String
    }
};
```

#### Sight Distance Factors

```javascript
const SIGHT_DISTANCE = {
    obstructions: ['vegetation', 'building', 'parked_vehicles', 'utility_box', 'sign', 'terrain'],
    estimated_distance: Number,  // feet
    adequacy: ['adequate', 'marginal', 'inadequate'],
    notes: String
};
```

### 4.2 Satellite Detection Categories

```javascript
const SATELLITE_DETECTION = {
    geometry: {
        intersection_type: ['4-leg', '3-leg', 'offset', 'skewed', 'roundabout'],
        leg_angles: Object,  // {NB: 0, EB: 88, SB: 180, WB: 272}
        intersection_size: String  // 'compact', 'standard', 'wide'
    },
    lanes: {
        NB: { through: Number, left: Number, right: Number },
        EB: { through: Number, left: Number, right: Number },
        SB: { through: Number, left: Number, right: Number },
        WB: { through: Number, left: Number, right: Number }
    },
    medians: {
        NS_street: { type: String, width: String },
        EW_street: { type: String, width: String }
    },
    crosswalks: {
        NB: { present: Boolean, type: String },
        EB: { present: Boolean, type: String },
        SB: { present: Boolean, type: String },
        WB: { present: Boolean, type: String }
    },
    turn_bays: {
        NB_left: { present: Boolean, length: String },
        // ... for each approach
    },
    pavement_condition: String  // 'good', 'fair', 'poor'
};
```

---

## 5. SVG Condition Diagram Specification

### 5.1 Diagram Overview

The SVG diagram will be a **schematic representation** of a 4-leg intersection showing:

- Approach lanes with turn arrows
- Traffic control devices (signals, signs)
- Crosswalks
- Medians
- Detected signs and their locations
- Direction labels (N, E, S, W)

### 5.2 SVG Structure

```xml
<svg viewBox="0 0 800 800" xmlns="http://www.w3.org/2000/svg">
    <!-- Background -->
    <rect class="background" />

    <!-- Road surfaces -->
    <g id="roads">
        <rect id="ns-road" />  <!-- North-South road -->
        <rect id="ew-road" />  <!-- East-West road -->
        <rect id="intersection-box" />
    </g>

    <!-- Lane markings -->
    <g id="lane-markings">
        <g id="nb-lanes" />
        <g id="eb-lanes" />
        <g id="sb-lanes" />
        <g id="wb-lanes" />
    </g>

    <!-- Medians -->
    <g id="medians">
        <rect id="ns-median" />
        <rect id="ew-median" />
    </g>

    <!-- Crosswalks -->
    <g id="crosswalks">
        <g id="nb-crosswalk" />
        <g id="eb-crosswalk" />
        <g id="sb-crosswalk" />
        <g id="wb-crosswalk" />
    </g>

    <!-- Traffic signals -->
    <g id="signals">
        <circle id="nb-signal" />
        <circle id="eb-signal" />
        <circle id="sb-signal" />
        <circle id="wb-signal" />
    </g>

    <!-- Signs (positioned along approaches) -->
    <g id="signs">
        <g id="nb-signs" />
        <g id="eb-signs" />
        <g id="sb-signs" />
        <g id="wb-signs" />
    </g>

    <!-- Direction labels -->
    <g id="labels">
        <text id="north-label">N</text>
        <text id="east-label">E</text>
        <text id="south-label">S</text>
        <text id="west-label">W</text>
    </g>

    <!-- Legend -->
    <g id="legend" />

    <!-- Title and metadata -->
    <g id="title-block" />
</svg>
```

### 5.3 Visual Elements

#### Lane Representation

```
NB Approach (2 through + 1 left turn):
┌─────┬─────┬─────┐
│  ↑  │  ↑  │  ←  │
│     │     │     │
└─────┴─────┴─────┘
  T1    T2    LT
```

#### Signal Representation

```
●──┤  Signal head with mast arm
   │
   │  Signal pole
```

#### Sign Representation

```
┌───┐
│35 │  Speed limit sign
└───┘

 ⬡    Warning sign (diamond)

[STOP]  Stop sign (octagon)
```

### 5.4 SVG Generation Logic

```javascript
function generateConditionDiagramSVG(inventoryData) {
    const svg = {
        width: 800,
        height: 800,
        center: { x: 400, y: 400 }
    };

    // Road dimensions based on lane counts
    const roadWidths = {
        NS: calculateRoadWidth(inventoryData.NB.lanes, inventoryData.SB.lanes),
        EW: calculateRoadWidth(inventoryData.EB.lanes, inventoryData.WB.lanes)
    };

    // Generate elements
    const elements = {
        roads: generateRoadSurfaces(svg, roadWidths),
        lanes: generateLaneMarkings(svg, inventoryData),
        medians: generateMedians(svg, inventoryData),
        crosswalks: generateCrosswalks(svg, inventoryData),
        signals: generateSignals(svg, inventoryData),
        signs: generateSigns(svg, inventoryData),
        labels: generateLabels(svg),
        legend: generateLegend(svg, inventoryData),
        titleBlock: generateTitleBlock(svg, inventoryData)
    };

    return assembleSVG(elements);
}
```

### 5.5 Color Scheme

| Element | Color | Hex |
|---------|-------|-----|
| Road surface | Dark gray | #4A4A4A |
| Lane lines | White | #FFFFFF |
| Center line | Yellow | #FFD700 |
| Median (raised) | Green | #228B22 |
| Median (painted) | Yellow | #FFD700 |
| Crosswalk | White | #FFFFFF |
| Signal (active) | Green | #00FF00 |
| Stop sign | Red | #CC0000 |
| Warning sign | Yellow | #FFD700 |
| Speed limit | White/Black | #FFFFFF |
| Background | Light gray | #E8E8E8 |

---

## 6. State Management

### 6.1 New State Object

```javascript
const conditionDiagramState = {
    // Location info
    location: null,
    coordinates: null,

    // Capture configuration
    captureConfig: {
        streetViewDistances: [0, 300, 500],  // feet
        satelliteZooms: [18, 19],
        includeApproachOffsets: true
    },

    // Image data storage
    images: {
        streetView: {
            center: [],      // 4 images (N, E, S, W)
            approach_300: [], // 4 images
            approach_500: []  // 4 images
        },
        satellite: {
            overview: null,   // Zoom 18
            detail: null,     // Zoom 19
            approaches: []    // 4 images
        }
    },

    // Raw model responses
    modelResponses: {
        streetView: {
            gpt4v: null,
            gemini: null,
            claude: null
        },
        satellite: {
            gpt4v: null,
            gemini: null
        }
    },

    // Consensus results
    consensus: {
        streetView: null,
        satellite: null,
        merged: null
    },

    // Direction-based inventory
    inventory: {
        NB: { trafficControl: {}, infrastructure: {}, sightDistance: {}, signs: [] },
        EB: { trafficControl: {}, infrastructure: {}, sightDistance: {}, signs: [] },
        SB: { trafficControl: {}, infrastructure: {}, sightDistance: {}, signs: [] },
        WB: { trafficControl: {}, infrastructure: {}, sightDistance: {}, signs: [] },
        intersection: {
            type: null,
            geometry: {},
            crosswalks: {},
            medians: {}
        }
    },

    // SVG diagram
    svgDiagram: null,

    // Analysis state
    status: 'idle',  // 'idle', 'capturing', 'analyzing', 'building_consensus', 'generating_diagram', 'complete', 'error'
    progress: {
        step: '',
        current: 0,
        total: 0,
        details: ''
    },
    error: null,

    // Timestamps
    analysisTimestamp: null,

    // API keys (reference to main config)
    apiKeys: {
        openai: null,   // For GPT-4V
        google: null,   // For Gemini + Maps
        anthropic: null, // For Claude
        mapbox: null    // For satellite
    }
};
```

### 6.2 Data Flow Diagram

```
User Selects Location
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                   IMAGE CAPTURE PHASE                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────┐    ┌─────────────────────┐        │
│  │   Street View API   │    │   Mapbox Static API  │        │
│  │   (Google Maps)     │    │   (Satellite)        │        │
│  └──────────┬──────────┘    └──────────┬──────────┘        │
│             │                           │                    │
│             ▼                           ▼                    │
│    12 Street View Images        6 Satellite Images          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   AI ANALYSIS PHASE                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  STREET VIEW (12 images × 3 models = 36 API calls)         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                     │
│  │ GPT-4V  │  │ Gemini  │  │ Claude  │                     │
│  │ Master  │  │Validator│  │Validator│                     │
│  └────┬────┘  └────┬────┘  └────┬────┘                     │
│       │            │            │                           │
│       └────────────┼────────────┘                           │
│                    ▼                                         │
│           Street View Consensus                              │
│           (2 of 3 agreement)                                 │
│                                                              │
│  SATELLITE (6 images × 2 models = 12 API calls)            │
│  ┌─────────┐  ┌─────────┐                                  │
│  │ GPT-4V  │  │ Gemini  │                                  │
│  │ Master  │  │Validator│                                  │
│  └────┬────┘  └────┬────┘                                  │
│       │            │                                        │
│       └─────┬──────┘                                        │
│             ▼                                                │
│       Satellite Consensus                                    │
│       (2 of 2 agreement)                                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   MERGE & VERIFY PHASE                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Street View Consensus ──┬── Satellite Consensus            │
│                          │                                   │
│                          ▼                                   │
│              ┌─────────────────────┐                        │
│              │   MERGE RESULTS     │                        │
│              ├─────────────────────┤                        │
│              │ • Lane counts from  │                        │
│              │   satellite (primary)│                        │
│              │ • Signs from street │                        │
│              │   view (primary)    │                        │
│              │ • Cross-verify both │                        │
│              └──────────┬──────────┘                        │
│                         │                                    │
│                         ▼                                    │
│            Direction-Based Inventory                         │
│            (NB, EB, SB, WB)                                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   SVG GENERATION PHASE                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Direction Inventory ───► generateConditionDiagramSVG()     │
│                                   │                          │
│                                   ▼                          │
│                          SVG Condition Diagram               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    Display Results + Export
```

---

## 7. API Integration Specifications

### 7.1 OpenAI GPT-4V API

```javascript
async function analyzeWithGPT4V(images, analysisType) {
    const apiKey = conditionDiagramState.apiKeys.openai;

    const systemPrompt = analysisType === 'streetView'
        ? STREET_VIEW_ANALYSIS_PROMPT
        : SATELLITE_ANALYSIS_PROMPT;

    const messages = [
        {
            role: "system",
            content: systemPrompt
        },
        {
            role: "user",
            content: [
                { type: "text", text: buildAnalysisPrompt(analysisType) },
                ...images.map(img => ({
                    type: "image_url",
                    image_url: {
                        url: `data:image/jpeg;base64,${img.base64}`,
                        detail: "high"
                    }
                }))
            ]
        }
    ];

    const response = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${apiKey}`
        },
        body: JSON.stringify({
            model: 'gpt-4o',  // GPT-4V/GPT-4o with vision
            messages: messages,
            max_tokens: 4096,
            temperature: 0.1  // Low temperature for consistency
        })
    });

    return await response.json();
}
```

### 7.2 Google Gemini API

```javascript
async function analyzeWithGemini(images, analysisType) {
    const apiKey = conditionDiagramState.apiKeys.google;

    const prompt = analysisType === 'streetView'
        ? STREET_VIEW_ANALYSIS_PROMPT
        : SATELLITE_ANALYSIS_PROMPT;

    const parts = [
        { text: prompt },
        ...images.map(img => ({
            inline_data: {
                mime_type: img.mediaType,
                data: img.base64
            }
        }))
    ];

    const response = await fetch(
        `https://generativelanguage.googleapis.com/v1/models/gemini-1.5-pro:generateContent?key=${apiKey}`,
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                contents: [{ parts }],
                generationConfig: {
                    temperature: 0.1,
                    maxOutputTokens: 4096
                }
            })
        }
    );

    return await response.json();
}
```

### 7.3 Anthropic Claude API

```javascript
async function analyzeWithClaude(images, analysisType) {
    const apiKey = conditionDiagramState.apiKeys.anthropic;

    const content = [
        ...images.map(img => ({
            type: "image",
            source: {
                type: "base64",
                media_type: img.mediaType,
                data: img.base64
            }
        })),
        {
            type: "text",
            text: STREET_VIEW_ANALYSIS_PROMPT  // Claude only for street view
        }
    ];

    const response = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'x-api-key': apiKey,
            'anthropic-version': '2023-06-01'
        },
        body: JSON.stringify({
            model: 'claude-sonnet-4-20250514',
            max_tokens: 4096,
            messages: [{ role: "user", content }]
        })
    });

    return await response.json();
}
```

### 7.4 Mapbox Static API (Satellite)

```javascript
async function fetchMapboxSatellite(lat, lng, zoom, width = 640, height = 640) {
    const accessToken = conditionDiagramState.apiKeys.mapbox;

    const url = `https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/${lng},${lat},${zoom},0/${width}x${height}@2x?access_token=${accessToken}`;

    const response = await fetch(url);
    const blob = await response.blob();
    const base64 = await blobToBase64(blob);

    return {
        base64,
        mediaType: 'image/png',
        zoom,
        coordinates: { lat, lng }
    };
}
```

---

## 8. Analysis Prompts

### 8.1 Street View Analysis Prompt

```
INTERSECTION INFRASTRUCTURE ANALYSIS - STREET VIEW
Direction-Based Inventory for Traffic Engineering

You are analyzing street-level imagery of an intersection for a transportation agency.
Your task is to provide a detailed, direction-specific infrastructure inventory.

IMAGES PROVIDED:
- Center view in 4 directions (N, E, S, W looking outward)
- 300ft approach views (looking toward intersection)
- 500ft approach views (looking toward intersection)

FOR EACH DIRECTION (Northbound, Eastbound, Southbound, Westbound), identify:

1. TRAFFIC CONTROL DEVICES
   - Signal heads: count, type (3-section, protected left, pedestrian)
   - Stop signs: present/absent
   - Yield signs: present/absent
   - Speed limit signs: value
   - Warning signs: type, message
   - Other regulatory signs

2. LANE CONFIGURATION (looking toward intersection)
   - Number of through lanes
   - Left turn lane(s): dedicated, shared
   - Right turn lane(s): dedicated, channelized
   - Bike lane: present, type

3. PAVEMENT MARKINGS
   - Stop bar: present
   - Crosswalk: present, type (standard, continental, none)
   - Turn arrows
   - Lane lines

4. PEDESTRIAN FACILITIES
   - Sidewalk: present, width estimate
   - Curb ramps: present, ADA features
   - Pedestrian signals: present, type

5. SIGHT DISTANCE
   - Obstructions: type, location
   - Estimated available sight distance
   - Adequacy assessment

6. OTHER INFRASTRUCTURE
   - Street lights: present, type
   - Median: type, width
   - Shoulder: present, width

OUTPUT FORMAT (JSON):
{
  "NB": {
    "approach_name": "Street Name (direction)",
    "traffic_control": {...},
    "lanes": {...},
    "markings": {...},
    "pedestrian": {...},
    "sight_distance": {...},
    "other": {...}
  },
  "EB": {...},
  "SB": {...},
  "WB": {...},
  "intersection": {
    "type": "signalized/unsignalized/stop-controlled",
    "legs": 4,
    "overall_observations": "..."
  },
  "confidence": 0.0-1.0,
  "limitations": ["..."]
}

Be precise. Only report what you can clearly see. Use "unclear" for uncertain observations.
```

### 8.2 Satellite Analysis Prompt

```
INTERSECTION GEOMETRY ANALYSIS - SATELLITE VIEW
Lane Configuration and Pavement Marking Inventory

You are analyzing satellite/aerial imagery of an intersection. Your task is to identify
lane geometry and pavement features that are best visible from above.

IMAGES PROVIDED:
- Overview image (wider context)
- Detail image (closer view of intersection)
- Approach-offset images (one per direction)

IDENTIFY THE FOLLOWING:

1. INTERSECTION GEOMETRY
   - Type: 4-leg, 3-leg, offset, skewed
   - Approximate leg angles
   - Intersection size classification

2. LANE CONFIGURATION (for each approach: NB, EB, SB, WB)
   - Through lanes: count
   - Left turn lanes: count, approximate length
   - Right turn lanes: count, channelized?
   - Receiving lanes on departure side

3. MEDIANS
   - North-South street: type (raised, painted, none), width
   - East-West street: type, width
   - Median nose locations

4. CROSSWALKS
   - Location (which approaches)
   - Type (continental, standard, decorative, unmarked)
   - Approximate width

5. PAVEMENT FEATURES
   - Stop bars visible
   - Turn arrows visible
   - Lane line condition
   - Overall pavement condition

6. OTHER VISIBLE FEATURES
   - Islands
   - Channelization
   - Right turn slip lanes
   - Bus stops/pull-outs

OUTPUT FORMAT (JSON):
{
  "geometry": {
    "type": "4-leg",
    "legs": {...}
  },
  "lanes": {
    "NB": {"through": 2, "left_turn": 1, "right_turn": 0},
    "EB": {...},
    "SB": {...},
    "WB": {...}
  },
  "medians": {...},
  "crosswalks": {...},
  "pavement_features": {...},
  "confidence": 0.0-1.0,
  "limitations": ["..."]
}

Focus on geometric features. Do not attempt to identify signs or vertical elements
(those are better detected in street view imagery).
```

---

## 9. Consensus Algorithm

### 9.1 Core Consensus Function

```javascript
function buildConsensus(modelResults, threshold, modelWeights) {
    const detections = {};

    // Collect all detections from all models
    for (const [modelName, result] of Object.entries(modelResults)) {
        const weight = modelWeights[modelName] || 1.0;

        traverseDetections(result, (path, value) => {
            const key = path.join('.');
            if (!detections[key]) {
                detections[key] = {
                    values: [],
                    models: [],
                    weights: []
                };
            }
            detections[key].values.push(value);
            detections[key].models.push(modelName);
            detections[key].weights.push(weight);
        });
    }

    // Apply consensus threshold
    const consensus = {};
    for (const [key, data] of Object.entries(detections)) {
        const agreementCount = data.models.length;

        if (agreementCount >= threshold) {
            // Determine consensus value
            const consensusValue = determineConsensusValue(data);
            setNestedValue(consensus, key.split('.'), {
                value: consensusValue,
                confidence: calculateConfidence(data, threshold),
                agreeing_models: data.models,
                method: agreementCount === data.models.length ? 'unanimous' : 'majority'
            });
        }
    }

    return consensus;
}

function determineConsensusValue(data) {
    // For numeric values, use weighted average
    if (data.values.every(v => typeof v === 'number')) {
        let weightedSum = 0;
        let totalWeight = 0;
        data.values.forEach((v, i) => {
            weightedSum += v * data.weights[i];
            totalWeight += data.weights[i];
        });
        return Math.round(weightedSum / totalWeight);
    }

    // For boolean/string values, use majority vote (weighted)
    const votes = {};
    data.values.forEach((v, i) => {
        const key = String(v);
        votes[key] = (votes[key] || 0) + data.weights[i];
    });

    return Object.entries(votes).sort((a, b) => b[1] - a[1])[0][0];
}

function calculateConfidence(data, threshold) {
    const totalModels = Object.keys(MODEL_WEIGHTS).length;
    const agreementRatio = data.models.length / totalModels;
    const weightedAgreement = data.weights.reduce((a, b) => a + b, 0) /
                              Object.values(MODEL_WEIGHTS).reduce((a, b) => a + b, 0);

    return (agreementRatio + weightedAgreement) / 2;
}
```

### 9.2 Model Weights Configuration

```javascript
const MODEL_WEIGHTS = {
    streetView: {
        gpt4v: 1.2,    // Master model, slightly higher weight
        gemini: 1.0,   // Standard weight
        claude: 1.0    // Standard weight
    },
    satellite: {
        gpt4v: 1.1,    // Slight preference
        gemini: 1.0    // Good for aerial imagery
    }
};

const CONSENSUS_THRESHOLDS = {
    streetView: 2,  // 2 of 3 models must agree
    satellite: 2    // 2 of 2 models must agree (both)
};
```

### 9.3 Merge Street View and Satellite Results

```javascript
function mergeAnalysisResults(streetViewConsensus, satelliteConsensus) {
    const merged = {
        NB: {}, EB: {}, SB: {}, WB: {},
        intersection: {}
    };

    const directions = ['NB', 'EB', 'SB', 'WB'];

    for (const dir of directions) {
        merged[dir] = {
            // Lane counts: prefer satellite (better top-down view)
            lanes: satelliteConsensus.lanes?.[dir] || streetViewConsensus[dir]?.lanes,

            // Traffic control: prefer street view (eye-level)
            trafficControl: streetViewConsensus[dir]?.traffic_control,

            // Signs: street view only
            signs: streetViewConsensus[dir]?.signs || [],

            // Crosswalks: merge both (satellite for presence, street view for type)
            crosswalks: mergeCrosswalks(
                satelliteConsensus.crosswalks?.[dir],
                streetViewConsensus[dir]?.markings?.crosswalk
            ),

            // Pedestrian facilities: street view
            pedestrian: streetViewConsensus[dir]?.pedestrian,

            // Sight distance: street view only
            sightDistance: streetViewConsensus[dir]?.sight_distance,

            // Median: prefer satellite for type, street view for details
            median: mergeMedianData(
                satelliteConsensus.medians,
                streetViewConsensus[dir]?.other?.median,
                dir
            )
        };
    }

    // Intersection-level data
    merged.intersection = {
        type: streetViewConsensus.intersection?.type,
        geometry: satelliteConsensus.geometry,
        legs: satelliteConsensus.geometry?.legs || 4
    };

    return merged;
}
```

---

## 10. UI Components

### 10.1 New Subtab Structure

Add after Bicycle subtab in Street View AI navigation:

```html
<button class="sv-subtab" data-subtab="condition" onclick="switchSVASubtab('condition')">
    <span>📊</span> Condition Diagram
</button>
```

### 10.2 Condition Diagram Subtab Content

```html
<div class="sv-subtab-content" id="svaSubtab-condition" style="display:none">

    <!-- Header -->
    <div class="sv-analysis-header" style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem">
        <span style="font-size:2rem">📊</span>
        <div>
            <h3 style="margin:0;color:#1e40af">Condition Diagram Generator</h3>
            <p style="margin:0;font-size:.85rem;color:#6b7280">
                Multi-model AI analysis with SVG intersection diagram
            </p>
        </div>
    </div>

    <!-- API Configuration Panel -->
    <div class="sv-config-panel" id="conditionApiConfig" style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px;padding:1rem;margin-bottom:1.5rem">
        <h4 style="margin:0 0 1rem 0;color:#0369a1">
            <span>🔑</span> API Configuration
        </h4>

        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem">
            <!-- OpenAI API Key -->
            <div class="api-key-input">
                <label style="font-size:.8rem;color:#374151">OpenAI (GPT-4V) API Key</label>
                <input type="password" id="conditionOpenaiKey" placeholder="sk-..."
                       style="width:100%;padding:.5rem;border:1px solid #d1d5db;border-radius:4px">
                <span class="key-status" id="openaiKeyStatus"></span>
            </div>

            <!-- Google/Gemini API Key -->
            <div class="api-key-input">
                <label style="font-size:.8rem;color:#374151">Google (Gemini) API Key</label>
                <input type="password" id="conditionGeminiKey" placeholder="AIza..."
                       style="width:100%;padding:.5rem;border:1px solid #d1d5db;border-radius:4px">
                <span class="key-status" id="geminiKeyStatus"></span>
            </div>

            <!-- Anthropic API Key (already configured in main header) -->
            <div class="api-key-input">
                <label style="font-size:.8rem;color:#374151">Anthropic (Claude) API Key</label>
                <div style="padding:.5rem;background:#e0f2fe;border-radius:4px;font-size:.8rem">
                    ✓ Using main header API key
                </div>
            </div>

            <!-- Mapbox API Key -->
            <div class="api-key-input">
                <label style="font-size:.8rem;color:#374151">Mapbox Access Token</label>
                <input type="password" id="conditionMapboxKey" placeholder="pk...."
                       style="width:100%;padding:.5rem;border:1px solid #d1d5db;border-radius:4px">
                <span class="key-status" id="mapboxKeyStatus"></span>
            </div>
        </div>

        <button onclick="saveConditionApiKeys()"
                style="margin-top:1rem;padding:.5rem 1rem;background:#0369a1;color:white;border:none;border-radius:4px;cursor:pointer">
            Save API Keys
        </button>
    </div>

    <!-- Location Selection -->
    <div class="sv-location-panel" style="background:white;border:1px solid #e5e7eb;border-radius:8px;padding:1rem;margin-bottom:1.5rem">
        <h4 style="margin:0 0 1rem 0">
            <span>📍</span> Location Selection
        </h4>

        <div id="conditionLocationDisplay">
            <p style="color:#6b7280;font-style:italic">No location selected. Select a location from the CMF tab or enter coordinates below.</p>
        </div>

        <div style="display:flex;gap:1rem;align-items:end;margin-top:1rem">
            <div>
                <label style="font-size:.8rem;color:#374151">Latitude</label>
                <input type="number" step="0.000001" id="conditionLat" placeholder="37.5xxx"
                       style="width:120px;padding:.5rem;border:1px solid #d1d5db;border-radius:4px">
            </div>
            <div>
                <label style="font-size:.8rem;color:#374151">Longitude</label>
                <input type="number" step="0.000001" id="conditionLng" placeholder="-77.4xxx"
                       style="width:120px;padding:.5rem;border:1px solid #d1d5db;border-radius:4px">
            </div>
            <button onclick="setConditionCoordinates()"
                    style="padding:.5rem 1rem;background:#059669;color:white;border:none;border-radius:4px;cursor:pointer">
                Set Location
            </button>
        </div>
    </div>

    <!-- Capture Configuration -->
    <div class="sv-capture-config" style="background:#fefce8;border:1px solid #fde047;border-radius:8px;padding:1rem;margin-bottom:1.5rem">
        <h4 style="margin:0 0 1rem 0;color:#a16207">
            <span>⚙️</span> Capture Settings
        </h4>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:2rem">
            <!-- Street View Settings -->
            <div>
                <h5 style="margin:0 0 .5rem 0">Street View (3 Models)</h5>
                <div style="font-size:.85rem;color:#374151">
                    <label><input type="checkbox" checked disabled> Center (4 directions)</label><br>
                    <label><input type="checkbox" id="sv300ft" checked> 300ft approaches (4 images)</label><br>
                    <label><input type="checkbox" id="sv500ft" checked> 500ft approaches (4 images)</label>
                </div>
                <div style="margin-top:.5rem;font-size:.8rem;color:#6b7280">
                    Models: GPT-4V (master) + Gemini + Claude
                </div>
            </div>

            <!-- Satellite Settings -->
            <div>
                <h5 style="margin:0 0 .5rem 0">Satellite View (2 Models)</h5>
                <div style="font-size:.85rem;color:#374151">
                    <label><input type="checkbox" checked disabled> Overview (Zoom 18)</label><br>
                    <label><input type="checkbox" id="satDetail" checked> Detail (Zoom 19)</label><br>
                    <label><input type="checkbox" id="satApproaches" checked> Approach offsets (4 images)</label>
                </div>
                <div style="margin-top:.5rem;font-size:.8rem;color:#6b7280">
                    Models: GPT-4V (master) + Gemini
                </div>
            </div>
        </div>

        <!-- Estimated API Calls -->
        <div style="margin-top:1rem;padding:.75rem;background:#fef3c7;border-radius:4px">
            <strong>Estimated API Calls:</strong>
            <span id="estimatedApiCalls">48 calls (12 SV × 3 + 6 Sat × 2)</span>
        </div>
    </div>

    <!-- Analysis Button -->
    <div style="text-align:center;margin-bottom:1.5rem">
        <button onclick="runConditionDiagramAnalysis()" id="conditionAnalyzeBtn"
                style="padding:1rem 2rem;font-size:1.1rem;background:linear-gradient(135deg,#1e40af,#7c3aed);color:white;border:none;border-radius:8px;cursor:pointer;font-weight:600">
            🔍 Generate Condition Diagram
        </button>
    </div>

    <!-- Progress Panel -->
    <div id="conditionProgress" style="display:none;background:#f3f4f6;border-radius:8px;padding:1.5rem;margin-bottom:1.5rem">
        <h4 style="margin:0 0 1rem 0">Analysis Progress</h4>

        <div class="progress-bar-container" style="background:#e5e7eb;border-radius:4px;height:24px;overflow:hidden">
            <div id="conditionProgressBar" style="background:linear-gradient(90deg,#3b82f6,#8b5cf6);height:100%;width:0%;transition:width 0.3s"></div>
        </div>

        <div style="display:flex;justify-content:space-between;margin-top:.5rem;font-size:.85rem">
            <span id="conditionProgressStep">Initializing...</span>
            <span id="conditionProgressPercent">0%</span>
        </div>

        <div id="conditionProgressDetails" style="margin-top:1rem;font-size:.8rem;color:#6b7280"></div>
    </div>

    <!-- Results Panel -->
    <div id="conditionResults" style="display:none">

        <!-- SVG Diagram -->
        <div class="condition-diagram-container" style="background:white;border:2px solid #1e40af;border-radius:8px;padding:1rem;margin-bottom:1.5rem">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
                <h4 style="margin:0;color:#1e40af">📊 Intersection Condition Diagram</h4>
                <div>
                    <button onclick="downloadConditionSVG()" style="padding:.5rem 1rem;background:#059669;color:white;border:none;border-radius:4px;cursor:pointer;margin-right:.5rem">
                        ⬇️ Download SVG
                    </button>
                    <button onclick="downloadConditionPNG()" style="padding:.5rem 1rem;background:#0369a1;color:white;border:none;border-radius:4px;cursor:pointer">
                        🖼️ Download PNG
                    </button>
                </div>
            </div>

            <div id="conditionSvgContainer" style="text-align:center;background:#f9fafb;padding:1rem;border-radius:4px">
                <!-- SVG will be inserted here -->
            </div>
        </div>

        <!-- Direction Tabs -->
        <div class="direction-inventory-tabs" style="margin-bottom:1.5rem">
            <div style="display:flex;border-bottom:2px solid #e5e7eb">
                <button class="dir-tab active" data-dir="NB" onclick="switchDirectionTab('NB')"
                        style="padding:.75rem 1.5rem;background:white;border:none;border-bottom:3px solid #1e40af;cursor:pointer;font-weight:600">
                    ⬆️ Northbound
                </button>
                <button class="dir-tab" data-dir="EB" onclick="switchDirectionTab('EB')"
                        style="padding:.75rem 1.5rem;background:#f3f4f6;border:none;cursor:pointer">
                    ➡️ Eastbound
                </button>
                <button class="dir-tab" data-dir="SB" onclick="switchDirectionTab('SB')"
                        style="padding:.75rem 1.5rem;background:#f3f4f6;border:none;cursor:pointer">
                    ⬇️ Southbound
                </button>
                <button class="dir-tab" data-dir="WB" onclick="switchDirectionTab('WB')"
                        style="padding:.75rem 1.5rem;background:#f3f4f6;border:none;cursor:pointer">
                    ⬅️ Westbound
                </button>
            </div>

            <!-- Direction Content -->
            <div id="directionInventoryContent" style="background:white;border:1px solid #e5e7eb;border-top:none;padding:1.5rem">
                <!-- Dynamic content per direction -->
            </div>
        </div>

        <!-- Model Agreement Summary -->
        <div class="model-agreement-summary" style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:1rem;margin-bottom:1.5rem">
            <h4 style="margin:0 0 1rem 0;color:#166534">✓ Model Agreement Summary</h4>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
                <div>
                    <h5 style="margin:0 0 .5rem 0">Street View Analysis</h5>
                    <div id="svAgreementStats" style="font-size:.85rem"></div>
                </div>
                <div>
                    <h5 style="margin:0 0 .5rem 0">Satellite Analysis</h5>
                    <div id="satAgreementStats" style="font-size:.85rem"></div>
                </div>
            </div>
        </div>

        <!-- Export Options -->
        <div class="export-options" style="background:#f3f4f6;border-radius:8px;padding:1rem">
            <h4 style="margin:0 0 1rem 0">📤 Export Options</h4>

            <div style="display:flex;gap:1rem;flex-wrap:wrap">
                <button onclick="exportConditionJSON()" style="padding:.75rem 1.5rem;background:#1e40af;color:white;border:none;border-radius:4px;cursor:pointer">
                    📋 Export JSON
                </button>
                <button onclick="exportConditionCSV()" style="padding:.75rem 1.5rem;background:#059669;color:white;border:none;border-radius:4px;cursor:pointer">
                    📊 Export CSV
                </button>
                <button onclick="exportConditionPDF()" style="padding:.75rem 1.5rem;background:#dc2626;color:white;border:none;border-radius:4px;cursor:pointer">
                    📄 Export PDF Report
                </button>
                <button onclick="copyInventoryToClipboard()" style="padding:.75rem 1.5rem;background:#6b7280;color:white;border:none;border-radius:4px;cursor:pointer">
                    📋 Copy to Clipboard
                </button>
            </div>
        </div>

    </div>

</div>
```

### 10.3 Direction Inventory Template

```html
<!-- Template for each direction's inventory display -->
<template id="directionInventoryTemplate">
    <div class="direction-inventory" data-direction="{DIR}">

        <!-- Traffic Control Section -->
        <div class="inventory-section">
            <h5 style="color:#dc2626;border-bottom:2px solid #fecaca;padding-bottom:.5rem">
                🚦 Traffic Control
            </h5>
            <table class="inventory-table" style="width:100%;font-size:.9rem">
                <tr>
                    <td style="width:40%">Signal Type</td>
                    <td><strong>{signal_type}</strong></td>
                    <td class="confidence">{signal_confidence}</td>
                </tr>
                <tr>
                    <td>Signal Heads</td>
                    <td><strong>{signal_heads}</strong></td>
                    <td class="confidence">{heads_confidence}</td>
                </tr>
                <tr>
                    <td>Stop Sign</td>
                    <td><strong>{stop_sign}</strong></td>
                    <td class="confidence">{stop_confidence}</td>
                </tr>
            </table>
        </div>

        <!-- Lane Configuration Section -->
        <div class="inventory-section">
            <h5 style="color:#1e40af;border-bottom:2px solid #bfdbfe;padding-bottom:.5rem">
                🛣️ Lane Configuration
            </h5>
            <table class="inventory-table" style="width:100%;font-size:.9rem">
                <tr>
                    <td style="width:40%">Through Lanes</td>
                    <td><strong>{through_lanes}</strong></td>
                    <td class="confidence">{through_confidence}</td>
                </tr>
                <tr>
                    <td>Left Turn Lanes</td>
                    <td><strong>{left_lanes}</strong></td>
                    <td class="confidence">{left_confidence}</td>
                </tr>
                <tr>
                    <td>Right Turn Lanes</td>
                    <td><strong>{right_lanes}</strong></td>
                    <td class="confidence">{right_confidence}</td>
                </tr>
                <tr>
                    <td>Bike Lane</td>
                    <td><strong>{bike_lane}</strong></td>
                    <td class="confidence">{bike_confidence}</td>
                </tr>
            </table>
        </div>

        <!-- Signs Section -->
        <div class="inventory-section">
            <h5 style="color:#ca8a04;border-bottom:2px solid #fef08a;padding-bottom:.5rem">
                🪧 Signs Detected
            </h5>
            <div class="signs-list" id="{DIR}-signs-list">
                <!-- Dynamic sign list -->
            </div>
        </div>

        <!-- Pedestrian Facilities Section -->
        <div class="inventory-section">
            <h5 style="color:#059669;border-bottom:2px solid #a7f3d0;padding-bottom:.5rem">
                🚶 Pedestrian Facilities
            </h5>
            <table class="inventory-table" style="width:100%;font-size:.9rem">
                <tr>
                    <td style="width:40%">Sidewalk</td>
                    <td><strong>{sidewalk}</strong></td>
                    <td class="confidence">{sidewalk_confidence}</td>
                </tr>
                <tr>
                    <td>Crosswalk</td>
                    <td><strong>{crosswalk}</strong></td>
                    <td class="confidence">{crosswalk_confidence}</td>
                </tr>
                <tr>
                    <td>Curb Ramp</td>
                    <td><strong>{curb_ramp}</strong></td>
                    <td class="confidence">{ramp_confidence}</td>
                </tr>
                <tr>
                    <td>Ped Signal</td>
                    <td><strong>{ped_signal}</strong></td>
                    <td class="confidence">{ped_signal_confidence}</td>
                </tr>
            </table>
        </div>

        <!-- Sight Distance Section -->
        <div class="inventory-section">
            <h5 style="color:#7c3aed;border-bottom:2px solid #ddd6fe;padding-bottom:.5rem">
                👁️ Sight Distance
            </h5>
            <table class="inventory-table" style="width:100%;font-size:.9rem">
                <tr>
                    <td style="width:40%">Available</td>
                    <td><strong>{sight_distance} ft</strong></td>
                    <td class="confidence">{sight_confidence}</td>
                </tr>
                <tr>
                    <td>Adequacy</td>
                    <td><strong class="{adequacy_class}">{sight_adequacy}</strong></td>
                    <td></td>
                </tr>
                <tr>
                    <td>Obstructions</td>
                    <td>{obstructions}</td>
                    <td></td>
                </tr>
            </table>
        </div>

    </div>
</template>
```

---

## 11. Implementation Phases

### Phase 1: Foundation (Priority: HIGH)

**Scope:** State management, API integration, basic UI

| Task | Description | Complexity |
|------|-------------|------------|
| 1.1 | Add `conditionDiagramState` object | Low |
| 1.2 | Create subtab HTML structure | Low |
| 1.3 | Implement API key management | Medium |
| 1.4 | Add subtab navigation handler | Low |
| 1.5 | Connect to CMF location selection | Medium |

**Deliverables:**
- New subtab visible and navigable
- API keys can be saved/loaded
- Location syncs from CMF tab

### Phase 2: Image Capture (Priority: HIGH)

**Scope:** Street View and Satellite image fetching

| Task | Description | Complexity |
|------|-------------|------------|
| 2.1 | Implement Street View capture (center) | Medium |
| 2.2 | Implement Street View capture (300ft, 500ft) | Medium |
| 2.3 | Implement coordinate offset calculation | Medium |
| 2.4 | Implement Mapbox Satellite capture | Medium |
| 2.5 | Add progress tracking for capture phase | Low |

**Deliverables:**
- 12 Street View images captured correctly
- 6 Satellite images captured correctly
- Progress UI shows capture status

### Phase 3: Multi-Model Analysis (Priority: HIGH)

**Scope:** API calls to all three vision models

| Task | Description | Complexity |
|------|-------------|------------|
| 3.1 | Implement GPT-4V analysis function | Medium |
| 3.2 | Implement Gemini analysis function | Medium |
| 3.3 | Implement Claude analysis function | Low (existing) |
| 3.4 | Create Street View analysis prompt | Medium |
| 3.5 | Create Satellite analysis prompt | Medium |
| 3.6 | Implement batch processing with progress | Medium |

**Deliverables:**
- All three models receive images and return analysis
- Prompts produce structured JSON output
- Progress shows which model is processing

### Phase 4: Consensus Engine (Priority: HIGH)

**Scope:** Multi-model consensus algorithm

| Task | Description | Complexity |
|------|-------------|------------|
| 4.1 | Implement consensus algorithm | High |
| 4.2 | Add model weighting system | Medium |
| 4.3 | Implement Street View consensus (2/3) | Medium |
| 4.4 | Implement Satellite consensus (2/2) | Medium |
| 4.5 | Implement result merging | High |
| 4.6 | Calculate confidence scores | Medium |

**Deliverables:**
- Consensus correctly identifies agreed detections
- Confidence scores reflect model agreement
- Merged results combine SV + Satellite data

### Phase 5: Direction-Based Inventory (Priority: HIGH)

**Scope:** Organize results by direction

| Task | Description | Complexity |
|------|-------------|------------|
| 5.1 | Structure inventory by N/E/S/W | Medium |
| 5.2 | Implement direction tab UI | Low |
| 5.3 | Render inventory tables | Medium |
| 5.4 | Display confidence indicators | Low |
| 5.5 | Show model agreement details | Medium |

**Deliverables:**
- Engineers can view inventory per direction
- Confidence clearly shown for each item
- Model agreement visible

### Phase 6: SVG Diagram Generation (Priority: HIGH)

**Scope:** Automatic SVG intersection diagram

| Task | Description | Complexity |
|------|-------------|------------|
| 6.1 | Create SVG template structure | Medium |
| 6.2 | Implement lane rendering | High |
| 6.3 | Implement signal/sign icons | Medium |
| 6.4 | Implement crosswalk rendering | Medium |
| 6.5 | Implement median rendering | Medium |
| 6.6 | Add legend and title block | Low |
| 6.7 | Implement dynamic scaling | High |

**Deliverables:**
- SVG accurately represents detected inventory
- Lanes, signals, signs, crosswalks all shown
- Diagram scales based on lane counts

### Phase 7: Export & Polish (Priority: MEDIUM)

**Scope:** Export functionality and UI refinements

| Task | Description | Complexity |
|------|-------------|------------|
| 7.1 | Implement SVG download | Low |
| 7.2 | Implement PNG export | Medium |
| 7.3 | Implement JSON export | Low |
| 7.4 | Implement CSV export | Medium |
| 7.5 | Implement PDF report | High |
| 7.6 | Add error handling throughout | Medium |
| 7.7 | Performance optimization | Medium |

**Deliverables:**
- All export formats working
- Error messages helpful
- Analysis completes in reasonable time

---

## 12. Function Reference

### 12.1 Core Functions

| Function | Purpose | Phase |
|----------|---------|-------|
| `initConditionDiagramState()` | Initialize state object | 1 |
| `saveConditionApiKeys()` | Save API keys to localStorage | 1 |
| `loadConditionApiKeys()` | Load API keys from localStorage/config | 1 |
| `setConditionCoordinates()` | Set location from manual input | 1 |
| `syncLocationFromCMF()` | Sync location from CMF tab | 1 |

### 12.2 Capture Functions

| Function | Purpose | Phase |
|----------|---------|-------|
| `captureStreetViewImages()` | Fetch all Street View images | 2 |
| `captureSatelliteImages()` | Fetch all Mapbox Satellite images | 2 |
| `calculateOffsetCoordinates(lat, lng, distance, bearing)` | Calculate offset position | 2 |
| `fetchStreetViewImage(lat, lng, heading, pitch, fov)` | Fetch single SV image | 2 |
| `fetchMapboxSatellite(lat, lng, zoom)` | Fetch single satellite image | 2 |

### 12.3 Analysis Functions

| Function | Purpose | Phase |
|----------|---------|-------|
| `runConditionDiagramAnalysis()` | Main analysis orchestrator | 3 |
| `analyzeWithGPT4V(images, type)` | Send to GPT-4V API | 3 |
| `analyzeWithGemini(images, type)` | Send to Gemini API | 3 |
| `analyzeWithClaude(images)` | Send to Claude API | 3 |
| `parseModelResponse(response, model)` | Parse JSON from response | 3 |

### 12.4 Consensus Functions

| Function | Purpose | Phase |
|----------|---------|-------|
| `buildStreetViewConsensus(responses)` | 2/3 consensus for SV | 4 |
| `buildSatelliteConsensus(responses)` | 2/2 consensus for Satellite | 4 |
| `mergeAnalysisResults(svConsensus, satConsensus)` | Merge SV + Satellite | 4 |
| `calculateConfidence(detections)` | Calculate confidence scores | 4 |
| `determineConsensusValue(values, weights)` | Weighted voting | 4 |

### 12.5 Inventory Functions

| Function | Purpose | Phase |
|----------|---------|-------|
| `buildDirectionInventory(merged)` | Structure by N/E/S/W | 5 |
| `renderDirectionInventory(dir)` | Render single direction | 5 |
| `switchDirectionTab(dir)` | Handle tab switching | 5 |
| `renderModelAgreementSummary()` | Show agreement stats | 5 |

### 12.6 SVG Functions

| Function | Purpose | Phase |
|----------|---------|-------|
| `generateConditionDiagramSVG(inventory)` | Generate complete SVG | 6 |
| `generateRoadSurfaces(config)` | Draw road rectangles | 6 |
| `generateLaneMarkings(config, inventory)` | Draw lane lines | 6 |
| `generateSignals(config, inventory)` | Draw signal icons | 6 |
| `generateSigns(config, inventory)` | Draw sign icons | 6 |
| `generateCrosswalks(config, inventory)` | Draw crosswalk patterns | 6 |
| `generateLegend(config)` | Draw legend | 6 |

### 12.7 Export Functions

| Function | Purpose | Phase |
|----------|---------|-------|
| `downloadConditionSVG()` | Download as SVG file | 7 |
| `downloadConditionPNG()` | Convert and download as PNG | 7 |
| `exportConditionJSON()` | Export inventory as JSON | 7 |
| `exportConditionCSV()` | Export inventory as CSV | 7 |
| `exportConditionPDF()` | Generate PDF report | 7 |
| `copyInventoryToClipboard()` | Copy to clipboard | 7 |

---

## 13. Testing Checklist

### 13.1 API Integration Tests

- [ ] OpenAI GPT-4V API connects successfully
- [ ] Google Gemini API connects successfully
- [ ] Claude API works (existing)
- [ ] Mapbox Static API returns images
- [ ] Google Street View API returns images
- [ ] API keys persist in localStorage
- [ ] Invalid API keys show appropriate errors

### 13.2 Image Capture Tests

- [ ] Center Street View captures 4 directions
- [ ] 300ft approach images have correct headings
- [ ] 500ft approach images have correct headings
- [ ] Coordinate offset calculation is accurate
- [ ] Satellite zoom 18 captures correctly
- [ ] Satellite zoom 19 captures correctly
- [ ] Satellite approach offsets are correct

### 13.3 Consensus Tests

- [ ] 3/3 agreement → HIGH confidence
- [ ] 2/3 agreement → HIGH confidence
- [ ] 1/3 agreement → EXCLUDED
- [ ] 2/2 satellite agreement → INCLUDED
- [ ] 1/2 satellite agreement → EXCLUDED
- [ ] Weighted voting works correctly
- [ ] Numeric values use weighted average
- [ ] Boolean values use majority vote

### 13.4 Inventory Tests

- [ ] All 4 directions populated
- [ ] Lane counts from satellite match expected
- [ ] Signs from street view correct
- [ ] Crosswalk merge works correctly
- [ ] Confidence scores calculated correctly
- [ ] Model agreement displayed correctly

### 13.5 SVG Generation Tests

- [ ] SVG renders in browser
- [ ] Lane count affects road width
- [ ] Turn lanes shown with arrows
- [ ] Signals appear at correct locations
- [ ] Signs appear along approaches
- [ ] Crosswalks render correctly
- [ ] Legend is complete
- [ ] SVG scales appropriately

### 13.6 Export Tests

- [ ] SVG download works
- [ ] PNG export is correct resolution
- [ ] JSON export has all data
- [ ] CSV export is properly formatted
- [ ] PDF report includes SVG
- [ ] Clipboard copy works

### 13.7 Edge Case Tests

- [ ] Location with no Street View coverage
- [ ] 3-leg intersection handling
- [ ] Skewed intersection handling
- [ ] Missing API key handling
- [ ] API rate limit handling
- [ ] Network error recovery
- [ ] Very wide intersection (5+ lanes)
- [ ] Rural intersection (minimal features)

---

## 14. Cost Estimation

### 14.1 Per Analysis Costs (Approximate)

| Service | Calls | Cost per Call | Total |
|---------|-------|---------------|-------|
| Google Street View | 12 | $0.007 | $0.084 |
| Mapbox Satellite | 6 | ~$0.001 | $0.006 |
| OpenAI GPT-4V | 18 | ~$0.02 | $0.36 |
| Google Gemini | 18 | ~$0.002 | $0.036 |
| Anthropic Claude | 12 | ~$0.01 | $0.12 |
| **TOTAL per analysis** | | | **~$0.61** |

### 14.2 Monthly Estimates

| Usage Level | Analyses/Month | Monthly Cost |
|-------------|----------------|--------------|
| Light | 50 | ~$30 |
| Moderate | 200 | ~$122 |
| Heavy | 500 | ~$305 |

---

## 15. Security Considerations

### 15.1 API Key Storage

- Store API keys in localStorage (client-side only)
- Never log API keys to console
- Option to load from config file (gitignored)
- Clear keys on logout/session end

### 15.2 Data Privacy

- Images processed via API are subject to provider policies
- Consider data retention policies of each provider
- Do not store raw images longer than necessary
- Offer option to clear cached analysis data

---

## 16. Future Enhancements

### 16.1 Planned Enhancements

| Enhancement | Description | Priority |
|-------------|-------------|----------|
| Road Segment Mode | Analyze linear segments with intervals | High |
| 3-Leg Support | Handle T-intersections | Medium |
| Roundabout Support | Handle circular intersections | Medium |
| Historical Comparison | Compare analyses over time | Low |
| Batch Processing | Analyze multiple locations | Medium |
| Custom Model Selection | Let user choose models | Low |

### 16.2 Road Segment Analysis (Future)

```javascript
const SEGMENT_ANALYSIS = {
    input: {
        startCoordinates: { lat, lng },
        endCoordinates: { lat, lng },
        interval: 0.1  // miles
    },
    capturePoints: 'calculated',  // Based on segment length
    directions: 2,  // Both directions of travel
    output: {
        perPoint: 'inventory',
        aggregate: 'summary'
    }
};
```

---

## 17. Approval

**Plan Author:** Claude (AI Assistant)
**Plan Date:** January 5, 2026
**Feature Location:** Street View AI Tab > Condition Diagram Subtab
**Target Models:** GPT-4V (Master), Gemini Pro Vision, Claude Vision

---

### Approval Signature

- [ ] **User Approval** - Approve this implementation plan

---

*End of Implementation Plan*
