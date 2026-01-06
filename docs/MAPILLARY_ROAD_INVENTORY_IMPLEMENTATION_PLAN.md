# Mapillary Road Inventory - Comprehensive Implementation Plan

## Executive Summary

This plan outlines a complete Mapillary-powered Road Inventory system integrated with crash analysis, designed for professional traffic engineers. The system leverages Mapillary's free API for pre-detected features without requiring AI/ML models.

---

## Part 1: Architecture Overview

### 1.1 New Tab Structure

```
CRASH LENS Application
├── Existing Tabs (unchanged)
│   ├── Dashboard
│   ├── Analysis
│   ├── Map
│   ├── Safety Focus
│   ├── Hot Spots
│   ├── CMF/Countermeasures
│   ├── Warrants
│   ├── MUTCD
│   ├── Grants
│   └── Before/After
│
└── NEW: Asset Inventory Tab
    ├── Sub-tab: Extract Assets
    ├── Sub-tab: View Inventory
    ├── Sub-tab: Coverage Map
    └── Sub-tab: Upload Data (for non-coverage areas)
```

### 1.2 State Management

```javascript
// New global state object for inventory
const inventoryState = {
    // Extraction state
    extractionRuns: [],           // History of extraction runs
    currentExtraction: null,      // Active extraction job

    // Feature data
    features: [],                 // Extracted Mapillary features
    filteredFeatures: [],         // After applying filters

    // Selection
    selectedFeatures: [],         // User-selected features
    selectedArea: null,           // Current selection area (bbox, polygon, etc.)

    // UI state
    activeSubTab: 'extract',      // 'extract', 'view', 'coverage', 'upload'
    assetFilters: [],             // Selected asset types
    viewMode: 'table',            // 'table', 'map', 'cards'

    // Integration
    linkedLocation: null,         // Location from other tabs
    crashCorrelation: {},         // Feature -> crash mapping

    // Coverage
    coverageData: null,           // Mapillary coverage tiles
    noCoverageAreas: [],          // User-uploaded data for gaps

    // Loading states
    isLoading: false,
    loadingProgress: 0,
    loadingMessage: ''
};
```

### 1.3 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER SELECTION                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │Jurisdiction│ │Bounding  │ │ Hotspot  │ │  CSV     │            │
│  │ Dropdown  │ │   Box    │ │ Dropdown │ │ Upload   │            │
│  └─────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
│        └─────────────┴─────────────┴─────────────┘                  │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    MAPILLARY API LAYER                        │   │
│  │  • Rate limiting (50k/day)                                    │   │
│  │  • Request batching                                           │   │
│  │  • Response caching                                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    DATA PROCESSING                            │   │
│  │  • Feature classification                                     │   │
│  │  • Crash correlation                                          │   │
│  │  • Route/Node matching                                        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    IndexedDB STORAGE                          │   │
│  │  • Extraction runs                                            │   │
│  │  • Features                                                   │   │
│  │  • Images metadata                                            │   │
│  │  • Crash correlations                                         │   │
│  │  • User presets                                               │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│        ┌─────────────────────┼─────────────────────┐                │
│        ▼                     ▼                     ▼                │
│  ┌──────────┐         ┌──────────┐          ┌──────────┐           │
│  │ Inventory│         │   Map    │          │   PDF    │           │
│  │  Table   │         │ Display  │          │  Report  │           │
│  └──────────┘         └──────────┘          └──────────┘           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Part 2: Mapillary API Integration

### 2.1 API Endpoints

| Endpoint | Purpose | Rate Limit | Cost |
|----------|---------|------------|------|
| `graph.mapillary.com/map_features` | Query detected features | 50k/day | FREE |
| `graph.mapillary.com/images` | Get imagery metadata | 50k/day | FREE |
| `tiles.mapillary.com/maps/vtp/mly_map_feature_traffic_sign` | Vector tiles for signs | Unlimited* | FREE |
| `tiles.mapillary.com/maps/vtp/mly_map_feature_point` | Vector tiles for points | Unlimited* | FREE |
| `tiles.mapillary.com/maps/vtp/mly1_public` | Image coverage tiles | Unlimited* | FREE |

### 2.2 Data Fields to Extract (Per User Request)

**INCLUDE all fields except:**
- Camera angle (compass_angle) - Excluded per user request
- User/Organization info - Excluded per user request
- API token details - Excluded per user request

**Fields to Extract:**

```javascript
const MAPILLARY_FIELDS = {
    // Feature identification
    id: true,                    // Unique feature ID
    object_value: true,          // Mapillary classification (e.g., "regulatory--stop--g1")
    object_type: true,           // Feature type category

    // Location
    geometry: true,              // GeoJSON point (lat/lng)

    // Temporal
    first_seen_at: true,         // First detection timestamp
    last_seen_at: true,          // Most recent detection

    // Image references
    images: true                 // Array of image IDs for verification
};

const IMAGE_FIELDS = {
    id: true,                    // Image ID
    captured_at: true,           // Capture timestamp
    geometry: true,              // Location
    thumb_256_url: true,         // Small thumbnail
    thumb_1024_url: true,        // Medium thumbnail
    thumb_2048_url: true,        // Large thumbnail
    sequence_id: true,           // For route reconstruction
    is_pano: true,               // Panoramic indicator
    height: true,                // Image dimensions
    width: true
    // EXCLUDED: compass_angle, creator, make, model
};
```

### 2.3 Feature Taxonomy

```
ASSET CATEGORIES (Traffic Engineer Focused)
├── 🚦 TRAFFIC CONTROL
│   ├── Traffic Signals (vehicle)
│   │   └── object--traffic-light--*
│   ├── Pedestrian Signals
│   │   └── object--traffic-light--pedestrians
│   ├── Stop Signs
│   │   └── regulatory--stop--*
│   ├── Yield Signs
│   │   └── regulatory--yield--*
│   └── Flashing Beacons
│       └── object--traffic-light--warning
│
├── 🚗 SPEED REGULATION
│   ├── Speed Limit Signs (all values)
│   │   └── regulatory--speed-limit-*--*
│   ├── School Zone Speed
│   │   └── regulatory--speed-limit-*--school
│   ├── Work Zone Speed
│   │   └── regulatory--speed-limit-*--construction
│   └── Minimum Speed
│       └── regulatory--minimum-speed-limit-*--*
│
├── ↩️ TURN & LANE CONTROL
│   ├── No Left Turn
│   │   └── regulatory--no-left-turn--*
│   ├── No Right Turn
│   │   └── regulatory--no-right-turn--*
│   ├── No U-Turn
│   │   └── regulatory--no-u-turn--*
│   ├── U-Turn Permitted
│   │   └── regulatory--u-turn--*
│   ├── Left Turn Only
│   │   └── regulatory--turn-left--*, regulatory--left-turn-only--*
│   ├── Right Turn Only
│   │   └── regulatory--turn-right--*, regulatory--right-turn-only--*
│   ├── Through Only
│   │   └── regulatory--straight-only--*
│   ├── Lane Use Control
│   │   └── regulatory--lane-control--*
│   ├── One-Way Signs
│   │   └── regulatory--one-way-*--*
│   ├── Do Not Enter
│   │   └── regulatory--do-not-enter--*
│   └── Wrong Way
│       └── regulatory--wrong-way--*
│
├── ⚠️ WARNING SIGNS
│   ├── Curve/Turn Warnings
│   │   └── warning--curve-*--, warning--turn--*
│   ├── Intersection Ahead
│   │   └── warning--intersection--*, warning--t-intersection--*
│   ├── Signal Ahead
│   │   └── warning--traffic-signals--*
│   ├── Stop/Yield Ahead
│   │   └── warning--stop-ahead--*, warning--yield-ahead--*
│   ├── Merge/Lane Ends
│   │   └── warning--merge-*--, warning--lane-ends--*
│   └── Road Condition Warnings
│       └── warning--slippery-road--*, warning--bump--*, etc.
│
├── 🚶 PEDESTRIAN FACILITIES
│   ├── Crosswalk Signs
│   │   └── warning--pedestrians-crossing--*
│   ├── Crosswalk Markings
│   │   └── marking--crosswalk-*--*
│   ├── School Zone Signs
│   │   └── warning--school-zone--*, warning--children--*
│   ├── School Crossing Signs
│   │   └── warning--school-crossing--*
│   └── Pedestrian Signals
│       └── object--traffic-light--pedestrians
│
├── 🚲 BICYCLE FACILITIES
│   ├── Bike Lane Signs
│   │   └── regulatory--bicycles-only--*
│   ├── Bike Route Signs
│   │   └── information--bike-route--*
│   ├── Share the Road
│   │   └── warning--share-the-road--*
│   ├── Bike Crossing Signs
│   │   └── warning--bicycles-crossing--*
│   └── Bike Lane Markings
│       └── marking--bike-lane--*, marking--sharrow--*
│
├── 💡 ROADSIDE INFRASTRUCTURE
│   ├── Street Lights
│   │   └── object--street-light--*
│   ├── Utility Poles
│   │   └── object--utility-pole--*
│   ├── Fire Hydrants
│   │   └── object--fire-hydrant--*
│   ├── Guard Rails
│   │   └── object--guard-rail--*
│   └── Bollards
│       └── object--bollard--*
│
└── 📍 ROAD MARKINGS
    ├── Stop Lines
    │   └── marking--stop-line--*
    ├── Yield Lines
    │   └── marking--give-way-line--*
    ├── Turn Arrows
    │   └── marking--arrow-*--*
    └── Lane Markings
        └── marking--continuous-*--, marking--dashed-*--
```

---

## Part 3: User Interface Design

### 3.1 Asset Inventory Tab Layout

```html
<!-- ASSET INVENTORY TAB -->
<div id="tab-inventory" class="tab-content">
    <div class="inventory-container">

        <!-- Sub-Navigation -->
        <div class="inventory-sub-tabs">
            <button class="inv-tab active" data-tab="extract">
                📥 Extract Assets
            </button>
            <button class="inv-tab" data-tab="view">
                📋 View Inventory
            </button>
            <button class="inv-tab" data-tab="coverage">
                🗺️ Coverage Map
            </button>
            <button class="inv-tab" data-tab="upload">
                ⬆️ Upload Data
            </button>
        </div>

        <!-- Sub-Tab Content -->
        <div class="inventory-content">
            <!-- Content loaded based on active sub-tab -->
        </div>

    </div>
</div>
```

### 3.2 Extract Assets Sub-Tab

```
┌─────────────────────────────────────────────────────────────────────┐
│ 📥 EXTRACT ASSETS                                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ ┌─ STEP 1: SELECT AREA ─────────────────────────────────────────┐  │
│ │                                                                │  │
│ │  ○ 🏛️ Jurisdiction(s)                                         │  │
│ │     ┌────────────────────────────────────────────────────┐    │  │
│ │     │ ☑ Henrico County                              ▼    │    │  │
│ │     └────────────────────────────────────────────────────┘    │  │
│ │     [+ Add Another Jurisdiction]                              │  │
│ │                                                                │  │
│ │  ○ 🗺️ Draw on Map                                             │  │
│ │     [Polygon] [Rectangle] [Circle]                            │  │
│ │                                                                │  │
│ │  ○ 📏 Road Segment                                             │  │
│ │     Start: [_______] End: [_______] Buffer: [50m ▼]           │  │
│ │                                                                │  │
│ │  ○ 📍 Around Location                                          │  │
│ │     [Search address or coordinates...        ]                │  │
│ │     Radius: ○100m ○250m ○500m ○1000m                         │  │
│ │                                                                │  │
│ │  ○ 🔥 From Hotspot                                             │  │
│ │     Source: [Top Crash Intersections ▼]                       │  │
│ │     Location: [Broad St & Parham Rd ▼]                        │  │
│ │     Radius: [100m ▼]                                          │  │
│ │                                                                │  │
│ │  ○ 📄 Upload Location List (CSV)                               │  │
│ │     [Choose File...] [Download Template]                      │  │
│ │                                                                │  │
│ │  ○ 🔗 From Current Selection                                   │  │
│ │     Using: "Broad St & Parham Rd" from Map tab               │  │
│ │     [Use This Location]                                       │  │
│ │                                                                │  │
│ └────────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ┌─ STEP 2: SELECT ASSET TYPES ──────────────────────────────────┐  │
│ │                                                                │  │
│ │  Presets: [All Assets ▼] [Save Current as Preset]             │  │
│ │                                                                │  │
│ │  🚦 TRAFFIC CONTROL          ⚠️ WARNING SIGNS                  │  │
│ │  ☑ Traffic Signals           ☑ Curve/Turn Warnings            │  │
│ │  ☑ Pedestrian Signals        ☑ Intersection Ahead             │  │
│ │  ☑ Stop Signs                ☑ Signal Ahead                   │  │
│ │  ☑ Yield Signs               ☑ Stop/Yield Ahead               │  │
│ │  ☐ Flashing Beacons          ☑ Merge/Lane Ends                │  │
│ │                                                                │  │
│ │  🚗 SPEED REGULATION          🚶 PEDESTRIAN FACILITIES         │  │
│ │  ☑ Speed Limit Signs (all)   ☑ Crosswalk Signs                │  │
│ │    └ ☐15 ☐20 ☑25 ☑30 ☑35    ☑ Crosswalk Markings             │  │
│ │      ☑40 ☑45 ☐50+            ☑ School Zone Signs              │  │
│ │  ☐ School Zone Speed         ☑ Pedestrian Signals             │  │
│ │  ☐ Work Zone Speed                                            │  │
│ │                               🚲 BICYCLE FACILITIES            │  │
│ │  ↩️ TURN & LANE CONTROL       ☑ Bike Lane Signs                │  │
│ │  ☑ No Left Turn              ☑ Bike Route Signs               │  │
│ │  ☑ No Right Turn             ☐ Share the Road                 │  │
│ │  ☑ No U-Turn                 ☑ Bike Crossing Signs            │  │
│ │  ☑ U-Turn Permitted                                           │  │
│ │  ☑ Left/Right Turn Only      💡 ROADSIDE INFRASTRUCTURE       │  │
│ │  ☑ Through Only              ☑ Street Lights                  │  │
│ │  ☑ Lane Use Control          ☐ Utility Poles                  │  │
│ │  ☑ One-Way Signs             ☐ Fire Hydrants                  │  │
│ │  ☑ Do Not Enter / Wrong Way  ☐ Guard Rails                    │  │
│ │                                                                │  │
│ │  [☑ Select All]  [☐ Clear All]                                │  │
│ │                                                                │  │
│ └────────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ┌─ STEP 3: EXTRACTION OPTIONS ──────────────────────────────────┐  │
│ │                                                                │  │
│ │  ☑ Include street-level imagery metadata                      │  │
│ │  ☑ Calculate crash correlation (within 100m radius)           │  │
│ │  ☑ Match to crash data routes/nodes                           │  │
│ │  ☐ Include coverage gap analysis                              │  │
│ │                                                                │  │
│ │  Estimated features: ~2,500 | Est. time: ~45 seconds          │  │
│ │                                                                │  │
│ │  [🚀 Start Extraction]                                        │  │
│ │                                                                │  │
│ └────────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.3 View Inventory Sub-Tab

```
┌─────────────────────────────────────────────────────────────────────┐
│ 📋 VIEW INVENTORY                                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ ┌─ FILTERS ─────────────────────────────────────────────────────┐  │
│ │ Run: [Latest - Aug 20, 2024 ▼]  Category: [All ▼]             │  │
│ │ Search: [________________] Type: [All ▼] Crashes: [Any ▼]     │  │
│ └────────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ┌─ SUMMARY CARDS ───────────────────────────────────────────────┐  │
│ │ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐       │  │
│ │ │  🚦    │ │  🚗    │ │  ↩️    │ │  🚶    │ │  💡    │       │  │
│ │ │  142   │ │  891   │ │  234   │ │  456   │ │ 1,204  │       │  │
│ │ │Traffic │ │ Speed  │ │ Turn   │ │ Ped    │ │Lighting│       │  │
│ │ │Control │ │ Signs  │ │Control │ │Facility│ │        │       │  │
│ │ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘       │  │
│ └────────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ┌─ VIEW TOGGLE ─────────────────────────────────────────────────┐  │
│ │ [📋 Table] [🗺️ Map] [🃏 Cards]    Export: [JSON] [CSV] [KML]  │  │
│ └────────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ┌─ ASSET TABLE ─────────────────────────────────────────────────┐  │
│ │ ☐ │ Type          │ Location       │ Route      │ Crashes │ ⋮ │  │
│ │───┼───────────────┼────────────────┼────────────┼─────────┼───│  │
│ │ ☐ │ 🛑 Stop Sign  │ 37.55, -77.46  │ BROAD ST   │ 12 (498)│ ⋮ │  │
│ │ ☐ │ 🚦 Signal     │ 37.55, -77.45  │ BROAD ST   │ 8 (240) │ ⋮ │  │
│ │ ☐ │ ⚠️ Curve Warn │ 37.54, -77.47  │ PARHAM RD  │ 5 (125) │ ⋮ │  │
│ │ ☐ │ 🚶 Crosswalk  │ 37.55, -77.46  │ BROAD ST   │ 3 (42)  │ ⋮ │  │
│ │ ☐ │ 💡 Light      │ 37.55, -77.46  │ BROAD ST   │ 2 (14)  │ ⋮ │  │
│ │                                                                │  │
│ │ Showing 1-50 of 2,927 assets    [< Prev] [1] [2] ... [Next >]  │  │
│ └────────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ┌─ ACTIONS ─────────────────────────────────────────────────────┐  │
│ │ Selected: 0 assets                                             │  │
│ │ [📍 Go to Map] [📷 View Images] [📊 Analyze] [📄 Add to Report]│  │
│ └────────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.4 Asset Detail Panel (Slide-out or Modal)

```
┌─────────────────────────────────────────────────────────────────┐
│ ASSET DETAILS                                              [✕]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                         │   │
│  │              [MAPILLARY IMAGE THUMBNAIL]                │   │
│  │                     256x192                             │   │
│  │                                                         │   │
│  │  [< Prev Image]  Image 1 of 4  [Next Image >]          │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  🛑 STOP SIGN                                                   │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  IDENTIFICATION                                                 │
│  ├─ ID: ASSET_00123                                            │
│  ├─ Mapillary ID: 1234567890                                   │
│  ├─ Category: Traffic Control                                  │
│  ├─ Type: regulatory--stop--g1                                 │
│  └─ Confidence: High (4 observations)                          │
│                                                                 │
│  LOCATION                                                       │
│  ├─ Coordinates: 37.551234, -77.456789                         │
│  ├─ Nearest Route: S-VA043PR BROAD ST                          │
│  ├─ Nearest Node: 12345                                        │
│  └─ Approx Address: Broad St & Parham Rd                       │
│                                                                 │
│  DETECTION HISTORY                                              │
│  ├─ First Detected: Jun 15, 2023                               │
│  ├─ Last Verified: Aug 20, 2024                                │
│  ├─ Total Images: 4                                            │
│  └─ Status: ✅ Current                                         │
│                                                                 │
│  CRASH CORRELATION (100m radius)                                │
│  ├─ Total Crashes: 12                                          │
│  ├─ Severity: K:0 A:2 B:3 C:4 O:3                              │
│  ├─ EPDO Score: 498                                            │
│  ├─ Top Collision: Angle (42%)                                 │
│  └─ Nearest Crash: 23m                                         │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  [🗺️ Show on Map]  [🌐 Open in Mapillary]  [📄 Add to Report]  │
│  [🔧 Link to CMF]  [📋 Link to Warrants]   [📥 Export]         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.5 Map Integration Panel

Add to existing Map tab's layer controls:

```
┌─ ASSET LAYERS ──────────────────────────────────────────────────┐
│                                                                  │
│  ☑ Show Mapillary Assets    [Load Inventory for This Area]     │
│                                                                  │
│  Visibility:                                                     │
│  ├─ ☑ 🚦 Traffic Control (142)                                  │
│  ├─ ☑ 🚗 Speed Signs (891)                                      │
│  ├─ ☑ ↩️ Turn Control (234)                                     │
│  ├─ ☑ ⚠️ Warning Signs (567)                                    │
│  ├─ ☑ 🚶 Pedestrian (456)                                       │
│  ├─ ☑ 🚲 Bicycle (123)                                          │
│  └─ ☐ 💡 Lighting (1204)                                        │
│                                                                  │
│  Display:                                                        │
│  ○ Icons  ○ Clusters  ○ Heatmap                                 │
│                                                                  │
│  Mapillary Coverage:                                             │
│  ☑ Show coverage layer  [Coverage: 94%]                         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Part 4: PDF Report Integration

### 4.1 Existing Report - UNCHANGED

The current PDF report from Map tab remains **100% unchanged**. The existing structure:

```
EXISTING PDF REPORT (No Changes)
├── Header with location name & date
├── Crash Summary Statistics
├── Severity Breakdown (K/A/B/C/O)
├── Collision Type Analysis
├── Weather/Light Conditions
├── Map Screenshot with Crash Markers
├── Detailed Crash Table
└── Footer with data source
```

### 4.2 New Section - Appended at End (Opt-in)

```
NEW SECTION: INFRASTRUCTURE INVENTORY (Appended)
├── Only appears if:
│   ├── User checks "Include Infrastructure Inventory" checkbox
│   └── Inventory data exists for the location
│
├── Section Header
│   └── "ROAD INFRASTRUCTURE INVENTORY"
│   └── "Data Source: Mapillary | Extraction Date: Aug 20, 2024"
│
├── Option A: Same Map with Asset Overlay
│   └── Existing map view + asset markers overlaid
│   └── Legend showing asset types
│
├── Option B: Separate Asset Map (smaller)
│   └── Dedicated map showing just infrastructure
│   └── Clean view without crash markers
│
├── Asset Summary Table
│   ┌──────────────────────┬───────┬────────────────────┐
│   │ Asset Category       │ Count │ Last Verified      │
│   ├──────────────────────┼───────┼────────────────────┤
│   │ Traffic Signals      │ 2     │ Aug 2024           │
│   │ Stop Signs           │ 4     │ Aug 2024           │
│   │ Speed Limit (35 mph) │ 2     │ Jul 2024           │
│   │ Crosswalks           │ 6     │ Aug 2024           │
│   │ Street Lights        │ 12    │ Aug 2024           │
│   │ Warning Signs        │ 3     │ Jun 2024           │
│   └──────────────────────┴───────┴────────────────────┘
│
├── Detailed Asset List (if < 20 assets)
│   └── Each asset with coordinates and type
│
└── Data Attribution
    └── "Infrastructure data powered by Mapillary"
    └── "Coverage: 94% of selected area"
```

### 4.3 PDF Report Dialog Enhancement

```
┌─────────────────────────────────────────────────────────────────┐
│ GENERATE PDF REPORT                                        [✕]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Location: Broad St & Parham Rd                                 │
│  Crashes: 47 | Date Range: 2019-2024                           │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  Report Sections:                                               │
│  ☑ Crash Summary Statistics                                     │
│  ☑ Severity Analysis                                            │
│  ☑ Collision Type Breakdown                                     │
│  ☑ Environmental Conditions                                     │
│  ☑ Map with Crash Locations                                     │
│  ☑ Detailed Crash Table                                         │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  📦 INFRASTRUCTURE INVENTORY (Optional)                         │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ ☐ Include Infrastructure Inventory                        │ │
│  │                                                           │ │
│  │   Assets Found: 29 (from extraction Aug 20, 2024)        │ │
│  │                                                           │ │
│  │   Map Options:                                            │ │
│  │   ☑ Option A: Overlay assets on crash map                │ │
│  │   ☑ Option B: Separate infrastructure map                 │ │
│  │                                                           │ │
│  │   Include Details:                                        │ │
│  │   ☑ Asset summary table                                   │ │
│  │   ☐ Individual asset list                                 │ │
│  │   ☑ Mapillary image thumbnails (up to 4)                  │ │
│  │                                                           │ │
│  │   [🔄 Refresh Inventory] [📥 Load for This Location]      │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  [Cancel]                              [📄 Generate PDF Report] │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.4 "Load Inventory" Button in Location Popup

Add to existing Map selection panel:

```
┌─ SELECTED LOCATION ─────────────────────────────────────────────┐
│ 📍 Broad St & Parham Rd                                         │
│ Crashes: 47 | Severity: K:1 A:5 B:12 C:15 O:14                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ QUICK ACTIONS                                                   │
│ [🔧 CMF] [📋 Warrants] [💰 Grants] [📈 B/A Study] [📊 Analyze] │
│ [🛣️ Street View] [📄 PDF Report] [📥 Export] [🌍 KML]          │
│                                                                 │
│ ─────────────────────────────────────────────────────────────── │
│                                                                 │
│ 📦 INFRASTRUCTURE INVENTORY           ← NEW SECTION             │
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ Status: ✅ 29 assets loaded (Aug 20, 2024)                  ││
│ │                                                             ││
│ │ Quick Summary:                                              ││
│ │ 🚦 2 Signals | 🛑 4 Stop Signs | 🚶 6 Crosswalks            ││
│ │                                                             ││
│ │ [📦 View Full Inventory] [🔄 Refresh] [📥 Load Nearby]      ││
│ └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│ [✕ Clear Selection]                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 5: Data Storage Architecture

### 5.1 IndexedDB Schema

```javascript
const INVENTORY_DB_SCHEMA = {
    name: 'MapillaryInventoryDB',
    version: 1,
    stores: {

        // Store 1: Extraction Runs (metadata)
        runs: {
            keyPath: 'runId',
            autoIncrement: false,
            indexes: [
                { name: 'jurisdiction', keyPath: 'jurisdiction' },
                { name: 'timestamp', keyPath: 'timestamp' },
                { name: 'status', keyPath: 'status' }
            ],
            schema: {
                runId: 'string',           // UUID
                timestamp: 'date',
                jurisdiction: 'string',    // or 'multiple'
                jurisdictions: 'array',    // if multiple
                areaType: 'string',        // 'jurisdiction', 'polygon', 'segment', 'radius', 'csv', 'hotspot'
                areaGeometry: 'object',    // GeoJSON
                assetFilters: 'array',     // Selected asset categories
                status: 'string',          // 'pending', 'running', 'complete', 'error'
                featureCount: 'number',
                imageCount: 'number',
                duration: 'number',        // ms
                errorMessage: 'string',
                crashCorrelationEnabled: 'boolean',
                coveragePercent: 'number'
            }
        },

        // Store 2: Extracted Features
        features: {
            keyPath: 'id',
            autoIncrement: false,
            indexes: [
                { name: 'runId', keyPath: 'runId' },
                { name: 'category', keyPath: 'category' },
                { name: 'type', keyPath: 'type' },
                { name: 'route', keyPath: 'nearestRoute' },
                { name: 'crashCount', keyPath: 'crashCount' },
                { name: 'location', keyPath: ['lat', 'lng'] }
            ],
            schema: {
                id: 'string',              // Internal asset ID
                runId: 'string',           // Link to run
                mapillaryId: 'string',     // Mapillary feature ID
                category: 'string',        // 'traffic_control', 'speed', etc.
                type: 'string',            // 'stop_sign', 'signal', etc.
                subtype: 'string',         // Mapillary object_value
                displayName: 'string',     // Human-readable name
                lat: 'number',
                lng: 'number',
                firstSeen: 'date',
                lastSeen: 'date',
                imageIds: 'array',
                imageCount: 'number',
                confidence: 'string',      // 'high', 'medium', 'low'
                nearestRoute: 'string',    // Matched crash route
                nearestNode: 'string',     // Matched crash node
                approxAddress: 'string',
                crashCount: 'number',
                crashEPDO: 'number',
                crashSeverity: 'object'    // {K:0, A:1, B:2, C:3, O:4}
            }
        },

        // Store 3: Image Metadata
        images: {
            keyPath: 'id',
            autoIncrement: false,
            indexes: [
                { name: 'featureId', keyPath: 'featureId' },
                { name: 'capturedAt', keyPath: 'capturedAt' }
            ],
            schema: {
                id: 'string',              // Mapillary image ID
                featureId: 'string',       // Linked feature
                capturedAt: 'date',
                lat: 'number',
                lng: 'number',
                sequenceId: 'string',
                isPano: 'boolean',
                width: 'number',
                height: 'number',
                thumbUrl256: 'string',
                thumbUrl1024: 'string',
                thumbUrl2048: 'string',
                viewerUrl: 'string'        // Link to Mapillary viewer
            }
        },

        // Store 4: Crash Correlations
        crashCorrelation: {
            keyPath: 'featureId',
            autoIncrement: false,
            indexes: [
                { name: 'runId', keyPath: 'runId' },
                { name: 'crashCount', keyPath: 'crashCount' }
            ],
            schema: {
                featureId: 'string',
                runId: 'string',
                correlationRadius: 'number',
                crashIds: 'array',
                crashCount: 'number',
                severityCounts: 'object',  // {K:0, A:1, B:2, C:3, O:5}
                epdo: 'number',
                collisionTypes: 'object',
                weatherDist: 'object',
                lightDist: 'object',
                nearestCrashDist: 'number',
                pedCount: 'number',
                bikeCount: 'number'
            }
        },

        // Store 5: User Presets
        presets: {
            keyPath: 'name',
            autoIncrement: false,
            schema: {
                name: 'string',
                assetFilters: 'array',
                description: 'string',
                createdAt: 'date',
                isDefault: 'boolean'
            }
        },

        // Store 6: User-Uploaded Data (for non-coverage areas)
        userAssets: {
            keyPath: 'id',
            autoIncrement: true,
            indexes: [
                { name: 'uploadId', keyPath: 'uploadId' },
                { name: 'category', keyPath: 'category' },
                { name: 'location', keyPath: ['lat', 'lng'] }
            ],
            schema: {
                id: 'number',              // Auto-increment
                uploadId: 'string',        // Batch upload ID
                category: 'string',
                type: 'string',
                displayName: 'string',
                lat: 'number',
                lng: 'number',
                notes: 'string',
                imageUrl: 'string',        // User-provided image URL
                createdAt: 'date',
                createdBy: 'string',
                source: 'string'           // 'manual', 'csv_upload', 'field_collection'
            }
        },

        // Store 7: Cache (for API responses)
        cache: {
            keyPath: 'key',
            autoIncrement: false,
            schema: {
                key: 'string',
                data: 'any',
                timestamp: 'date',
                ttl: 'number'              // Time to live in ms
            }
        }
    }
};
```

### 5.2 Export Formats

#### JSON Export (Full Data)

```javascript
{
    "exportVersion": "1.0",
    "exportDate": "2024-08-20T10:30:00Z",
    "exportedBy": "CRASH LENS - Virginia Crash Analysis Tool",

    "metadata": {
        "jurisdiction": "Henrico County",
        "jurisdictions": ["Henrico County"],
        "extractionDate": "2024-08-20",
        "extractionRunId": "run_abc123",
        "areaType": "jurisdiction",
        "areaDescription": "Full jurisdiction boundary",
        "totalFeatures": 2927,
        "assetFilters": ["traffic_control", "speed", "pedestrian", "warning"],
        "crashCorrelationRadius": 100,
        "coveragePercent": 94.2
    },

    "summary": {
        "byCategory": {
            "traffic_control": { "count": 142, "crashCorrelated": 89 },
            "speed_regulation": { "count": 891, "crashCorrelated": 234 },
            "turn_control": { "count": 234, "crashCorrelated": 56 },
            "warning": { "count": 567, "crashCorrelated": 123 },
            "pedestrian": { "count": 456, "crashCorrelated": 78 },
            "bicycle": { "count": 123, "crashCorrelated": 34 },
            "lighting": { "count": 514, "crashCorrelated": 156 }
        },
        "topCrashCorrelated": [
            { "id": "ASSET_001", "type": "stop_sign", "crashes": 15, "epdo": 892 },
            { "id": "ASSET_045", "type": "signal", "crashes": 12, "epdo": 678 }
        ]
    },

    "features": [
        {
            "id": "ASSET_001",
            "mapillaryId": "1234567890",
            "category": "traffic_control",
            "type": "stop_sign",
            "mapillaryValue": "regulatory--stop--g1",
            "displayName": "Stop Sign",
            "location": {
                "lat": 37.551234,
                "lng": -77.456789
            },
            "detection": {
                "firstSeen": "2023-06-15",
                "lastSeen": "2024-08-20",
                "confidence": "high",
                "imageCount": 4
            },
            "roadMatch": {
                "route": "S-VA043PR BROAD ST",
                "node": "12345",
                "approxAddress": "Broad St & Parham Rd"
            },
            "crashCorrelation": {
                "radius": 100,
                "count": 12,
                "severity": { "K": 0, "A": 2, "B": 3, "C": 4, "O": 3 },
                "epdo": 498,
                "topCollision": "Angle",
                "nearestCrashDist": 23
            }
        }
        // ... more features
    ],

    "images": [
        {
            "id": "img_123456",
            "featureId": "ASSET_001",
            "capturedAt": "2024-08-15",
            "lat": 37.551230,
            "lng": -77.456785,
            "thumbUrl": "https://...",
            "viewerUrl": "https://www.mapillary.com/app/?pKey=123456"
        }
    ],

    "dataSource": {
        "provider": "Mapillary",
        "apiVersion": "v4",
        "attribution": "Infrastructure data powered by Mapillary",
        "license": "CC-BY-SA"
    }
}
```

#### CSV Export (GIS Compatible)

```csv
id,mapillary_id,category,type,subtype,display_name,lat,lng,first_seen,last_seen,confidence,image_count,route,node,address,crash_count,crash_epdo,crash_k,crash_a,crash_b,crash_c,crash_o
ASSET_001,1234567890,traffic_control,stop_sign,regulatory--stop--g1,Stop Sign,37.551234,-77.456789,2023-06-15,2024-08-20,high,4,S-VA043PR BROAD ST,12345,Broad St & Parham Rd,12,498,0,2,3,4,3
```

#### GeoJSON Export (Mapping)

```javascript
{
    "type": "FeatureCollection",
    "name": "Henrico_County_Road_Inventory",
    "crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" } },
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [-77.456789, 37.551234]
            },
            "properties": {
                "id": "ASSET_001",
                "category": "traffic_control",
                "type": "stop_sign",
                "displayName": "Stop Sign",
                "route": "S-VA043PR BROAD ST",
                "crashCount": 12,
                "epdo": 498,
                "confidence": "high",
                "lastSeen": "2024-08-20"
            }
        }
    ]
}
```

### 5.3 Import Formats

#### JSON Import (Restore Session)

Same format as JSON export - allows users to reload previous extraction data.

#### CSV Upload Template (User-Provided Assets)

For areas without Mapillary coverage:

```csv
lat,lng,category,type,display_name,notes,image_url
37.551234,-77.456789,traffic_control,stop_sign,Stop Sign - Northbound,New installation 2024,https://...
37.552345,-77.457890,speed_regulation,speed_limit_35,Speed Limit 35 mph,Near school zone,
```

#### CSV Location List Template (for Batch Extraction)

```csv
lat,lng,name,radius_m,extract_type
37.5512,-77.4567,Broad St & Parham Rd,100,intersection
37.5498,-77.4612,Broad St & Glenside Dr,100,intersection
37.5534,-77.4489,Broad St Corridor Start,50,segment_start
37.5623,-77.4201,Broad St Corridor End,50,segment_end
```

---

## Part 6: Cross-Tab Integration

### 6.1 Shared Selection State Enhancement

```javascript
// Enhanced selectionState for inventory integration
const selectionState = {
    // Existing fields (unchanged)
    location: null,
    locationType: null,
    crashes: [],
    crashProfile: null,
    fromTab: null,
    timestamp: null,
    multiLocations: [],

    // NEW: Inventory integration
    inventory: {
        features: [],           // Inventory features for this location
        lastLoaded: null,       // When inventory was loaded
        runId: null,            // Which extraction run
        summary: {              // Quick stats
            total: 0,
            byCategory: {}
        }
    }
};
```

### 6.2 CMF Tab Integration

```javascript
// When CMF tab loads a location, show existing infrastructure
function loadCMFLocationWithInventory(location) {
    // Existing CMF logic (unchanged)
    const crashes = getCrashesForLocation(location);
    cmfState.filteredCrashes = crashes;

    // NEW: Load and display inventory
    const inventory = getInventoryForLocation(location);

    if (inventory && inventory.features.length > 0) {
        // Show "Existing Infrastructure" section
        renderExistingInfrastructure(inventory);

        // Adjust CMF recommendations
        // - Don't recommend "Add stop sign" if one exists
        // - Show "Upgrade crosswalk" instead of "Add crosswalk"
        const adjustedCMFs = adjustCMFRecommendations(cmfState.cmfs, inventory);
        renderCMFList(adjustedCMFs);
    }
}

// Existing Infrastructure Panel for CMF Tab
/*
┌─ EXISTING INFRASTRUCTURE AT THIS LOCATION ──────────────────────┐
│                                                                  │
│  This location currently has:                                    │
│  • 🚦 1 Traffic Signal (4-way)                                  │
│  • 🛑 2 Stop Signs (minor approaches)                           │
│  • 🚶 2 Marked Crosswalks (standard)                            │
│  • 💡 4 Street Lights                                           │
│  • ⚠️ 1 Signal Ahead Warning                                    │
│                                                                  │
│  Speed Limit: 35 mph                                             │
│  Control Type: Signalized                                        │
│                                                                  │
│  [📷 View Street Imagery] [📦 Full Inventory Details]            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
*/
```

### 6.3 Warrants Tab Integration

```javascript
// Signal Warrant evaluation uses inventory
function evaluateSignalWarrantWithInventory(location) {
    const inventory = getInventoryForLocation(location);

    // Determine current control type from inventory
    const currentControl = determineControlType(inventory);
    // Returns: 'signalized', 'stop_controlled', 'yield_controlled', 'uncontrolled'

    // Display current control in warrant form
    warrantsState.signal.currentControl = currentControl;

    // Show in UI
    /*
    ┌─ CURRENT TRAFFIC CONTROL ───────────────────────────────────┐
    │                                                              │
    │  Based on Mapillary inventory data:                         │
    │                                                              │
    │  Control Type: STOP-CONTROLLED (2-way)                      │
    │                                                              │
    │  Detected Devices:                                           │
    │  • Stop signs on minor approaches (2)                       │
    │  • No traffic signals detected                              │
    │  • Crosswalks present (2)                                   │
    │                                                              │
    │  Last Verified: Aug 20, 2024                                │
    │                                                              │
    │  [📷 View Street Imagery]                                    │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘
    */

    if (currentControl === 'signalized') {
        showWarning('This location appears to already be signalized.');
    }
}
```

### 6.4 MUTCD Tab Integration

```javascript
// MUTCD compliance checking with inventory
function checkMUTCDComplianceWithInventory(location, crashes) {
    const inventory = getInventoryForLocation(location);
    const recommendations = [];

    // Example checks:

    // 1. School zone signage
    if (isNearSchool(location) && !hasSchoolZoneSigns(inventory)) {
        recommendations.push({
            type: 'missing_sign',
            sign: 'School Zone Warning (S1-1)',
            mutcdRef: 'Section 7B.15',
            priority: 'high',
            rationale: 'School within 500ft, no school zone signage detected'
        });
    }

    // 2. Speed limit posting
    if (!hasSpeedLimitSign(inventory, 500)) {
        recommendations.push({
            type: 'missing_sign',
            sign: 'Speed Limit',
            mutcdRef: 'Section 2B.13',
            priority: 'medium',
            rationale: 'No speed limit sign detected within 500m'
        });
    }

    // 3. Stop ahead warning
    if (hasStopSign(inventory) && !hasStopAheadWarning(inventory)) {
        const crashCount = crashes.filter(c =>
            c[COL.COLLISION] === 'Rear End' ||
            c[COL.COLLISION] === 'Angle'
        ).length;

        if (crashCount >= 3) {
            recommendations.push({
                type: 'recommended_sign',
                sign: 'Stop Ahead Warning (W3-1)',
                mutcdRef: 'Section 2C.36',
                priority: 'medium',
                rationale: `${crashCount} rear-end/angle crashes suggest visibility issue`
            });
        }
    }

    // 4. Pedestrian crossing
    if (hasPedCrashes(crashes, 2) && !hasCrosswalkSign(inventory)) {
        recommendations.push({
            type: 'recommended_sign',
            sign: 'Pedestrian Crossing Warning (W11-2)',
            mutcdRef: 'Section 2C.50',
            priority: 'high',
            rationale: 'Multiple pedestrian crashes, no warning signage detected'
        });
    }

    return recommendations;
}
```

### 6.5 Grants Tab Integration

```javascript
// Grant application support with inventory data
function enhanceGrantApplicationWithInventory(location) {
    const inventory = getInventoryForLocation(location);
    const crashes = getCrashesForLocation(location);

    // Generate inventory summary for grant narrative
    const inventorySummary = {
        currentConditions: describeCurrentConditions(inventory),
        deficiencies: identifyDeficiencies(inventory, crashes),
        proposedImprovements: suggestImprovements(inventory, crashes)
    };

    /*
    GRANT APPLICATION - EXISTING CONDITIONS

    Current Infrastructure:
    The intersection of Broad St & Parham Rd currently has:
    - 4-way traffic signal (installed pre-2020, based on imagery)
    - Standard marked crosswalks on all approaches
    - 35 mph posted speed limit
    - Adequate street lighting (4 luminaires detected)

    Identified Deficiencies:
    - No pedestrian countdown signals detected
    - No ADA-compliant curb ramps visible
    - No bicycle facilities present

    Proposed Improvements:
    Based on crash patterns (12 ped crashes) and existing conditions:
    1. Install pedestrian countdown signals (all approaches)
    2. Upgrade crosswalks to high-visibility continental style
    3. Add bike lane markings on Broad St approaches

    Supporting Data:
    - Mapillary imagery date: Aug 2024
    - Coverage confidence: High (4+ observations per feature)
    */
}
```

### 6.6 Before/After Study Integration

```javascript
// B/A study with inventory context
function enhanceBAStudyWithInventory(location) {
    const inventory = getInventoryForLocation(location);

    // Show what countermeasures are currently installed
    // This helps engineers understand the "after" condition

    /*
    BEFORE/AFTER STUDY - INFRASTRUCTURE CONTEXT

    Current Infrastructure (as of Aug 2024):
    ┌─────────────────────────────────────────────────────────────┐
    │ The following devices are currently installed:              │
    │                                                             │
    │ • Traffic Signal (detected Aug 2024)                       │
    │ • High-visibility crosswalks (detected Aug 2024)           │
    │ • Pedestrian countdown signals (detected Aug 2024)         │
    │ • Left-turn signal phases (inferred from signal heads)     │
    │                                                             │
    │ Note: If your "After" period predates Aug 2024, these      │
    │ features may have been installed during your study period. │
    │                                                             │
    │ [📷 View Historical Imagery] [📅 Check Installation Dates] │
    └─────────────────────────────────────────────────────────────┘
    */
}
```

---

## Part 7: Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Objective:** Core infrastructure and basic extraction

**Tasks:**
1. IndexedDB setup and schema implementation
2. Mapillary API wrapper with rate limiting
3. Feature taxonomy and classification mapping
4. Basic Asset Inventory tab UI structure
5. Jurisdiction dropdown (reuse existing pattern from config.json)
6. Simple bbox query for single jurisdiction
7. Feature table with pagination (basic)
8. Basic state management (inventoryState)

**Deliverables:**
- [ ] IndexedDB operational with all stores
- [ ] Can extract features for one jurisdiction
- [ ] Basic table display of features
- [ ] Data persists across sessions

### Phase 2: Selection Methods (Week 2-3)

**Objective:** Multiple ways to select extraction area

**Tasks:**
1. Multi-jurisdiction selection (checkboxes)
2. Draw polygon on map (reuse existing drawing tools)
3. Draw rectangle/circle on map
4. Road segment selection (click start/end)
5. Radius around address/coordinates
6. Hotspot dropdown integration (pull from Hot Spots tab)
7. CSV upload for batch locations
8. "From Current Selection" link to Map tab

**Deliverables:**
- [ ] All 7 selection methods operational
- [ ] Selection preview on map
- [ ] Estimated feature count before extraction
- [ ] CSV template download

### Phase 3: Data Processing & Correlation (Week 3-4)

**Objective:** Meaningful data enrichment

**Tasks:**
1. Crash correlation calculation (within radius)
2. EPDO calculation for correlated crashes
3. Route/Node matching to crash data
4. Confidence scoring based on observation count
5. Address approximation via reverse geocoding
6. Feature deduplication
7. Progress tracking during extraction
8. Error handling and retry logic

**Deliverables:**
- [ ] Every feature has crash correlation data
- [ ] Features matched to crash data routes
- [ ] Confidence levels assigned
- [ ] Robust extraction with retries

### Phase 4: Map Visualization (Week 4-5)

**Objective:** Rich map display of inventory

**Tasks:**
1. Asset markers with category icons
2. Marker clustering for dense areas
3. Asset layer toggle in Map tab
4. Feature popup with quick actions
5. "Go to location" from inventory table
6. "Open in Mapillary" viewer link
7. Coverage layer visualization
8. Heatmap view option

**Deliverables:**
- [ ] Assets display on Map tab
- [ ] Layer controls functional
- [ ] Popups show all feature details
- [ ] Coverage gaps visible

### Phase 5: Cross-Tab Integration (Week 5-6)

**Objective:** Inventory flows to all tabs

**Tasks:**
1. CMF tab: Existing infrastructure panel
2. Warrants tab: Current control detection
3. MUTCD tab: Compliance recommendations
4. Grants tab: Narrative generation
5. Before/After: Infrastructure context
6. Shared selectionState.inventory
7. "Load Inventory" button in Map selection panel
8. Context indicator updates

**Deliverables:**
- [ ] All tabs show relevant inventory data
- [ ] Seamless navigation between tabs
- [ ] Selection state includes inventory
- [ ] Context-aware analysis

### Phase 6: PDF Report Integration (Week 6-7)

**Objective:** Inventory in PDF reports (opt-in)

**Tasks:**
1. PDF dialog checkbox for inventory inclusion
2. Option A: Overlay assets on crash map
3. Option B: Separate asset map generation
4. Asset summary table in PDF
5. Mapillary thumbnail embedding
6. Map capture with asset layers
7. Attribution footer
8. No changes to existing PDF sections

**Deliverables:**
- [ ] PDF dialog has inventory options
- [ ] Both map options (A & B) functional
- [ ] Asset table renders correctly
- [ ] Thumbnails display in PDF

### Phase 7: Export & Import (Week 7-8)

**Objective:** Complete data portability

**Tasks:**
1. JSON export (full data)
2. CSV export (GIS compatible)
3. GeoJSON export (mapping tools)
4. KML export (Google Earth)
5. JSON import (session restore)
6. CSV import (user-provided assets)
7. Preset save/load for asset filters
8. Batch export for multiple runs

**Deliverables:**
- [ ] All export formats working
- [ ] Import restores full session
- [ ] User presets persist
- [ ] Batch operations functional

### Phase 8: User Upload & Non-Coverage (Week 8-9)

**Objective:** Handle areas without Mapillary

**Tasks:**
1. Coverage gap detection
2. User upload form for manual assets
3. CSV batch upload for user assets
4. Image URL support
5. User asset display in table/map
6. Merge user assets with Mapillary data
7. Export includes user assets
8. Attribution distinction

**Deliverables:**
- [ ] Coverage gaps clearly shown
- [ ] Users can add manual assets
- [ ] User assets integrated in views
- [ ] Clear data source attribution

### Phase 9: Polish & Performance (Week 9-10)

**Objective:** Production-ready quality

**Tasks:**
1. Loading states and progress bars
2. Error handling improvements
3. Rate limit management (visual feedback)
4. Caching optimization
5. Mobile responsive design
6. Accessibility review (WCAG)
7. Performance optimization for large datasets
8. User documentation/help

**Deliverables:**
- [ ] Smooth UX with no blocking
- [ ] Works on mobile devices
- [ ] Accessible to all users
- [ ] Help documentation complete

---

## Part 8: Technical Specifications

### 8.1 API Rate Limit Management

```javascript
const MapillaryRateLimiter = {
    requests: [],
    maxPerMinute: 500,  // Conservative limit (API allows more)
    maxPerDay: 45000,   // Leave buffer from 50k limit
    dailyCount: 0,
    lastReset: null,

    async checkDailyReset() {
        const today = new Date().toDateString();
        if (this.lastReset !== today) {
            this.dailyCount = 0;
            this.lastReset = today;
        }
    },

    async throttle() {
        await this.checkDailyReset();

        // Check daily limit
        if (this.dailyCount >= this.maxPerDay) {
            throw new Error('Daily API limit reached. Try again tomorrow.');
        }

        // Check per-minute limit
        const now = Date.now();
        this.requests = this.requests.filter(t => now - t < 60000);

        if (this.requests.length >= this.maxPerMinute) {
            const waitTime = 60000 - (now - this.requests[0]);
            await new Promise(r => setTimeout(r, waitTime));
        }

        this.requests.push(now);
        this.dailyCount++;
    },

    async fetch(url, options = {}) {
        await this.throttle();

        const response = await fetch(url, options);

        if (response.status === 429) {
            // Rate limited - wait and retry
            await new Promise(r => setTimeout(r, 60000));
            return this.fetch(url, options);
        }

        return response;
    },

    getUsageStats() {
        return {
            minuteUsed: this.requests.length,
            minuteLimit: this.maxPerMinute,
            dailyUsed: this.dailyCount,
            dailyLimit: this.maxPerDay,
            percentUsed: Math.round((this.dailyCount / this.maxPerDay) * 100)
        };
    }
};
```

### 8.2 Caching Strategy

```javascript
const InventoryCache = {
    memory: new Map(),

    async get(key) {
        // Check memory first
        if (this.memory.has(key)) {
            const cached = this.memory.get(key);
            if (!this.isExpired(cached)) {
                return cached.data;
            }
            this.memory.delete(key);
        }

        // Check IndexedDB
        const db = await this.getDB();
        const cached = await db.get('cache', key);
        if (cached && !this.isExpired(cached)) {
            this.memory.set(key, cached);
            return cached.data;
        }

        return null;
    },

    async set(key, data, ttl = 3600000) { // Default 1 hour
        const cached = {
            key,
            data,
            timestamp: Date.now(),
            ttl
        };

        this.memory.set(key, cached);

        const db = await this.getDB();
        await db.put('cache', cached);
    },

    isExpired(cached) {
        return Date.now() - cached.timestamp > cached.ttl;
    },

    async clear() {
        this.memory.clear();
        const db = await this.getDB();
        await db.clear('cache');
    },

    // Cache keys
    keys: {
        features: (bbox) => `features_${bbox.join('_')}`,
        images: (featureId) => `images_${featureId}`,
        coverage: (bbox) => `coverage_${bbox.join('_')}`
    }
};
```

### 8.3 Error Handling

```javascript
const MAPILLARY_ERRORS = {
    RATE_LIMITED: {
        code: 429,
        message: 'Rate limit exceeded',
        action: 'wait',
        retryAfter: 60000,
        userMessage: 'API rate limit reached. Waiting 1 minute before retrying...'
    },
    INVALID_TOKEN: {
        code: 401,
        message: 'Invalid access token',
        action: 'configure',
        userMessage: 'Mapillary API token is invalid. Please check settings.'
    },
    NO_COVERAGE: {
        code: 'NO_DATA',
        message: 'No Mapillary coverage in this area',
        action: 'notify',
        userMessage: 'No street-level imagery available for this area. You can manually upload asset data.'
    },
    NETWORK_ERROR: {
        code: 'NETWORK',
        message: 'Network error',
        action: 'retry',
        maxRetries: 3,
        userMessage: 'Network error. Retrying...'
    },
    BBOX_TOO_LARGE: {
        code: 'BBOX_SIZE',
        message: 'Bounding box too large',
        action: 'split',
        userMessage: 'Area too large for single request. Splitting into smaller tiles...'
    }
};

async function handleMapillaryError(error, context) {
    const errorConfig = MAPILLARY_ERRORS[error.code] || {
        message: error.message,
        action: 'notify',
        userMessage: 'An unexpected error occurred.'
    };

    console.error(`[Mapillary Error] ${errorConfig.message}`, context);

    switch (errorConfig.action) {
        case 'wait':
            showToast(errorConfig.userMessage, 'warning');
            await new Promise(r => setTimeout(r, errorConfig.retryAfter));
            return { retry: true };

        case 'retry':
            if (context.retryCount < errorConfig.maxRetries) {
                showToast(errorConfig.userMessage, 'warning');
                await new Promise(r => setTimeout(r, 2000 * (context.retryCount + 1)));
                return { retry: true, retryCount: context.retryCount + 1 };
            }
            break;

        case 'split':
            return { split: true };

        case 'configure':
            showToast(errorConfig.userMessage, 'error');
            // Could open settings modal
            break;

        default:
            showToast(errorConfig.userMessage, 'info');
    }

    return { retry: false };
}
```

### 8.4 Feature Classification

```javascript
const FEATURE_CLASSIFIER = {
    // Map Mapillary object_value to our categories
    classify(mapillaryValue) {
        const value = mapillaryValue.toLowerCase();

        // Traffic Control
        if (value.includes('regulatory--stop')) {
            return { category: 'traffic_control', type: 'stop_sign', displayName: 'Stop Sign' };
        }
        if (value.includes('regulatory--yield')) {
            return { category: 'traffic_control', type: 'yield_sign', displayName: 'Yield Sign' };
        }
        if (value.includes('object--traffic-light')) {
            if (value.includes('pedestrians')) {
                return { category: 'pedestrian', type: 'ped_signal', displayName: 'Pedestrian Signal' };
            }
            return { category: 'traffic_control', type: 'traffic_signal', displayName: 'Traffic Signal' };
        }

        // Speed Regulation
        if (value.includes('regulatory--speed-limit')) {
            const match = value.match(/speed-limit-(\d+)/);
            const speed = match ? match[1] : 'unknown';
            return {
                category: 'speed_regulation',
                type: `speed_limit_${speed}`,
                displayName: `Speed Limit ${speed} mph`
            };
        }

        // Turn Control
        if (value.includes('regulatory--no-left-turn')) {
            return { category: 'turn_control', type: 'no_left_turn', displayName: 'No Left Turn' };
        }
        if (value.includes('regulatory--no-right-turn')) {
            return { category: 'turn_control', type: 'no_right_turn', displayName: 'No Right Turn' };
        }
        if (value.includes('regulatory--no-u-turn')) {
            return { category: 'turn_control', type: 'no_u_turn', displayName: 'No U-Turn' };
        }
        if (value.includes('regulatory--u-turn')) {
            return { category: 'turn_control', type: 'u_turn_permitted', displayName: 'U-Turn Permitted' };
        }
        if (value.includes('regulatory--one-way')) {
            return { category: 'turn_control', type: 'one_way', displayName: 'One Way' };
        }
        if (value.includes('regulatory--do-not-enter')) {
            return { category: 'turn_control', type: 'do_not_enter', displayName: 'Do Not Enter' };
        }

        // Warning Signs
        if (value.includes('warning--curve') || value.includes('warning--turn')) {
            return { category: 'warning', type: 'curve_warning', displayName: 'Curve Warning' };
        }
        if (value.includes('warning--intersection')) {
            return { category: 'warning', type: 'intersection_ahead', displayName: 'Intersection Ahead' };
        }
        if (value.includes('warning--traffic-signals')) {
            return { category: 'warning', type: 'signal_ahead', displayName: 'Signal Ahead' };
        }
        if (value.includes('warning--stop-ahead')) {
            return { category: 'warning', type: 'stop_ahead', displayName: 'Stop Ahead' };
        }
        if (value.includes('warning--pedestrians')) {
            return { category: 'pedestrian', type: 'ped_crossing_warning', displayName: 'Pedestrian Crossing' };
        }
        if (value.includes('warning--school')) {
            return { category: 'pedestrian', type: 'school_zone', displayName: 'School Zone' };
        }
        if (value.includes('warning--bicycles')) {
            return { category: 'bicycle', type: 'bike_crossing', displayName: 'Bicycle Crossing' };
        }

        // Pedestrian Facilities
        if (value.includes('marking--crosswalk')) {
            return { category: 'pedestrian', type: 'crosswalk', displayName: 'Crosswalk' };
        }

        // Bicycle Facilities
        if (value.includes('marking--bike-lane') || value.includes('marking--sharrow')) {
            return { category: 'bicycle', type: 'bike_lane', displayName: 'Bike Lane' };
        }
        if (value.includes('regulatory--bicycles-only')) {
            return { category: 'bicycle', type: 'bike_lane_sign', displayName: 'Bike Lane Sign' };
        }

        // Lighting
        if (value.includes('object--street-light')) {
            return { category: 'lighting', type: 'street_light', displayName: 'Street Light' };
        }

        // Road Markings
        if (value.includes('marking--stop-line')) {
            return { category: 'road_marking', type: 'stop_line', displayName: 'Stop Line' };
        }
        if (value.includes('marking--arrow')) {
            return { category: 'road_marking', type: 'lane_arrow', displayName: 'Lane Arrow' };
        }

        // Default/Other
        return {
            category: 'other',
            type: 'other',
            displayName: this.humanize(value)
        };
    },

    humanize(value) {
        return value
            .replace(/--/g, ' ')
            .replace(/-/g, ' ')
            .replace(/\b\w/g, c => c.toUpperCase());
    }
};
```

---

## Part 9: UI Component Specifications

### 9.1 Asset Category Icons

```javascript
const ASSET_ICONS = {
    traffic_control: {
        icon: '🚦',
        color: '#22c55e',  // Green
        markerColor: 'green'
    },
    stop_sign: {
        icon: '🛑',
        color: '#dc2626',  // Red
        markerColor: 'red'
    },
    yield_sign: {
        icon: '⚠️',
        color: '#f59e0b',  // Amber
        markerColor: 'orange'
    },
    speed_regulation: {
        icon: '🚗',
        color: '#3b82f6',  // Blue
        markerColor: 'blue'
    },
    turn_control: {
        icon: '↩️',
        color: '#8b5cf6',  // Purple
        markerColor: 'purple'
    },
    warning: {
        icon: '⚠️',
        color: '#f59e0b',  // Amber
        markerColor: 'orange'
    },
    pedestrian: {
        icon: '🚶',
        color: '#06b6d4',  // Cyan
        markerColor: 'cyan'
    },
    bicycle: {
        icon: '🚲',
        color: '#10b981',  // Emerald
        markerColor: 'green'
    },
    lighting: {
        icon: '💡',
        color: '#eab308',  // Yellow
        markerColor: 'yellow'
    },
    road_marking: {
        icon: '📍',
        color: '#6b7280',  // Gray
        markerColor: 'gray'
    }
};
```

### 9.2 CSS Styling

```css
/* Asset Inventory Tab Styles */
.inventory-container {
    padding: 0;
    width: 100%;
    box-sizing: border-box;
}

.inventory-sub-tabs {
    display: flex;
    gap: 0.5rem;
    padding: 1rem;
    background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
    border-bottom: 1px solid #bae6fd;
}

.inv-tab {
    padding: 0.6rem 1.2rem;
    border: 2px solid transparent;
    border-radius: var(--radius);
    background: white;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 500;
    transition: all 0.2s;
}

.inv-tab:hover {
    border-color: var(--primary);
    background: var(--primary-light);
}

.inv-tab.active {
    border-color: var(--primary);
    background: var(--primary);
    color: white;
}

/* Asset Cards */
.asset-summary-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
}

.asset-summary-card {
    background: white;
    border-radius: var(--radius-lg);
    padding: 1rem;
    text-align: center;
    border: 2px solid var(--gray-light);
    transition: all 0.2s;
    cursor: pointer;
}

.asset-summary-card:hover {
    border-color: var(--primary);
    transform: translateY(-2px);
    box-shadow: var(--shadow);
}

.asset-summary-card.active {
    border-color: var(--primary);
    background: var(--primary-light);
}

.asset-card-icon {
    font-size: 2rem;
    margin-bottom: 0.5rem;
}

.asset-card-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--dark);
}

.asset-card-label {
    font-size: 0.8rem;
    color: var(--gray);
    margin-top: 0.25rem;
}

/* Asset Table */
.asset-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
}

.asset-table th {
    background: var(--light);
    padding: 0.75rem;
    text-align: left;
    font-weight: 600;
    border-bottom: 2px solid var(--border);
    position: sticky;
    top: 0;
}

.asset-table td {
    padding: 0.75rem;
    border-bottom: 1px solid var(--border);
    vertical-align: middle;
}

.asset-table tr:hover {
    background: var(--primary-light);
}

.asset-type-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.25rem 0.6rem;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 500;
}

.asset-crash-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-size: 0.75rem;
}

.asset-crash-badge.high {
    background: #fee2e2;
    color: #dc2626;
}

.asset-crash-badge.medium {
    background: #fef3c7;
    color: #d97706;
}

.asset-crash-badge.low {
    background: #dcfce7;
    color: #16a34a;
}

/* Extraction Progress */
.extraction-progress {
    background: white;
    border-radius: var(--radius-lg);
    padding: 1.5rem;
    margin: 1rem 0;
    border: 2px solid var(--primary);
}

.extraction-progress-bar {
    height: 8px;
    background: var(--gray-light);
    border-radius: 4px;
    overflow: hidden;
    margin: 1rem 0;
}

.extraction-progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--primary) 0%, #8b5cf6 100%);
    transition: width 0.3s ease;
}

.extraction-stats {
    display: flex;
    justify-content: space-between;
    font-size: 0.85rem;
    color: var(--gray);
}

/* Asset Detail Panel */
.asset-detail-panel {
    position: fixed;
    right: 0;
    top: 0;
    width: 400px;
    height: 100vh;
    background: white;
    box-shadow: -4px 0 20px rgba(0,0,0,0.15);
    z-index: 2000;
    transform: translateX(100%);
    transition: transform 0.3s ease;
    overflow-y: auto;
}

.asset-detail-panel.visible {
    transform: translateX(0);
}

.asset-detail-header {
    padding: 1rem;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.asset-detail-image {
    width: 100%;
    height: 200px;
    object-fit: cover;
    background: var(--gray-light);
}

.asset-detail-section {
    padding: 1rem;
    border-bottom: 1px solid var(--border);
}

.asset-detail-section h4 {
    font-size: 0.85rem;
    color: var(--gray);
    text-transform: uppercase;
    margin-bottom: 0.75rem;
}

.asset-detail-row {
    display: flex;
    justify-content: space-between;
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
}

.asset-detail-row .label {
    color: var(--gray);
}

.asset-detail-row .value {
    font-weight: 500;
}
```

---

## Part 10: Testing Checklist

### 10.1 Functional Testing

- [ ] Extraction works for single jurisdiction
- [ ] Extraction works for multiple jurisdictions
- [ ] Polygon drawing selects correct area
- [ ] Rectangle/circle selection works
- [ ] Road segment selection works
- [ ] Address search + radius works
- [ ] Hotspot dropdown integration works
- [ ] CSV upload parses correctly
- [ ] "From Current Selection" uses Map tab selection
- [ ] Asset type filters apply correctly
- [ ] All asset categories classify correctly
- [ ] Crash correlation calculates accurately
- [ ] Route/node matching is accurate
- [ ] Confidence scoring works
- [ ] Table pagination works
- [ ] Table sorting works
- [ ] Table filtering works
- [ ] Map markers display correctly
- [ ] Marker clustering works
- [ ] Layer toggle controls work
- [ ] Feature popup displays all data
- [ ] "Go to Map" navigates correctly
- [ ] "Open in Mapillary" opens correct viewer
- [ ] JSON export includes all data
- [ ] CSV export is GIS compatible
- [ ] GeoJSON export validates
- [ ] KML export opens in Google Earth
- [ ] JSON import restores session
- [ ] User asset upload works
- [ ] User assets display with Mapillary data
- [ ] PDF report checkbox appears
- [ ] PDF Option A (overlay) renders
- [ ] PDF Option B (separate map) renders
- [ ] PDF asset table renders
- [ ] PDF thumbnails display
- [ ] Existing PDF sections unchanged

### 10.2 Integration Testing

- [ ] CMF tab shows existing infrastructure
- [ ] CMF recommendations adjust for existing devices
- [ ] Warrants tab detects current control
- [ ] MUTCD tab generates compliance recommendations
- [ ] Grants tab includes inventory in narrative
- [ ] Before/After shows infrastructure context
- [ ] selectionState.inventory syncs across tabs
- [ ] "Load Inventory" in Map panel works
- [ ] Context switches preserve inventory state

### 10.3 Performance Testing

- [ ] Extraction of 10,000+ features completes
- [ ] Table renders 5,000+ rows smoothly
- [ ] Map handles 10,000+ markers
- [ ] IndexedDB operations don't block UI
- [ ] Memory usage stays reasonable
- [ ] Mobile performance acceptable

### 10.4 Error Handling Testing

- [ ] Rate limit handled gracefully
- [ ] Network errors retry correctly
- [ ] Invalid token shows clear message
- [ ] No coverage areas handled
- [ ] Large bbox splits automatically
- [ ] Malformed CSV shows error
- [ ] Invalid coordinates handled

---

## Part 11: Documentation Requirements

### 11.1 User Documentation

1. **Quick Start Guide**
   - How to extract assets for your jurisdiction
   - Understanding the inventory table
   - Using inventory in PDF reports

2. **Feature Reference**
   - Asset categories explained
   - Mapillary data fields
   - Crash correlation methodology

3. **Integration Guide**
   - Using inventory with CMF recommendations
   - Warrant analysis with infrastructure data
   - Grant applications with inventory support

4. **Troubleshooting**
   - Common errors and solutions
   - Coverage gaps
   - Data quality issues

### 11.2 Technical Documentation

1. **API Reference**
   - Mapillary API usage
   - Rate limiting
   - Error codes

2. **Data Schema**
   - IndexedDB structure
   - Export formats
   - Import requirements

3. **Architecture**
   - State management
   - Cross-tab integration
   - Caching strategy

---

## Appendix A: Mapillary API Response Examples

### Feature Query Response

```javascript
{
    "data": [
        {
            "id": "1234567890",
            "geometry": {
                "type": "Point",
                "coordinates": [-77.456789, 37.551234]
            },
            "object_value": "regulatory--stop--g1",
            "object_type": "traffic_sign",
            "first_seen_at": "2023-06-15T14:30:00Z",
            "last_seen_at": "2024-08-20T10:15:00Z"
        }
    ],
    "paging": {
        "cursors": {
            "after": "cursor_abc123"
        }
    }
}
```

### Image Query Response

```javascript
{
    "data": [
        {
            "id": "9876543210",
            "captured_at": "2024-08-15T09:30:00Z",
            "geometry": {
                "type": "Point",
                "coordinates": [-77.456785, 37.551230]
            },
            "sequence_id": "seq_xyz789",
            "is_pano": false,
            "height": 2048,
            "width": 2732,
            "thumb_256_url": "https://scontent...",
            "thumb_1024_url": "https://scontent...",
            "thumb_2048_url": "https://scontent..."
        }
    ]
}
```

---

## Appendix B: Jurisdiction Boundary Data

The implementation will use the existing `config.json` jurisdictions structure, with boundary polygons to be sourced from:

1. Virginia GIS data (VGIN)
2. US Census TIGER boundaries
3. OpenStreetMap administrative boundaries

Boundary data format:
```javascript
{
    "henrico": {
        "name": "Henrico County",
        "boundary": {
            "type": "Polygon",
            "coordinates": [[[-77.6, 37.4], [-77.3, 37.4], [-77.3, 37.7], [-77.6, 37.7], [-77.6, 37.4]]]
        }
    }
}
```

---

## Summary

This implementation plan provides:

1. **Complete Mapillary Integration** - All available feature types with full metadata
2. **Traffic Engineer-Focused Design** - Asset categories aligned with engineering practice
3. **Multiple Selection Methods** - Jurisdiction, drawing, segments, hotspots, CSV
4. **Full Data Lifecycle** - Extract, store, view, export, import
5. **Cross-Tab Integration** - CMF, Warrants, MUTCD, Grants, Before/After
6. **PDF Report Enhancement** - Opt-in inventory section, unchanged existing report
7. **User Data Upload** - Support for non-coverage areas
8. **Scalable Architecture** - IndexedDB, caching, rate limiting
9. **Attractive UI** - Modern design matching existing application style

**Estimated Total Development Time: 9-10 weeks**

Ready to proceed with Phase 1 implementation upon approval.
