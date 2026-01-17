# Crash Tree Diagram Feature - Comprehensive Implementation Plan

## Virginia Statewide Crash Analysis Tool

**Document Version:** 1.0
**Date:** January 2026
**Author:** Traffic Safety Engineering & UI/UX Design Team

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Strategic Vision](#2-strategic-vision)
3. [User Experience Design](#3-user-experience-design)
4. [Technical Architecture](#4-technical-architecture)
5. [Data Requirements](#5-data-requirements)
6. [Feature Specifications](#6-feature-specifications)
7. [Integration with Existing Tabs](#7-integration-with-existing-tabs)
8. [Report Generation System](#8-report-generation-system)
9. [Implementation Phases](#9-implementation-phases)
10. [Testing Strategy](#10-testing-strategy)
11. [Appendices](#appendices)

---

## 1. Executive Summary

### Purpose
Implement an interactive Crash Tree Diagram feature that enables Virginia transportation agencies to conduct FHWA-compliant systemic safety analysis at state, district, county, and corridor levels.

### Business Value
| Stakeholder | Value Delivered |
|-------------|-----------------|
| VDOT Central Office | Statewide safety trend identification, SHSP monitoring |
| VDOT Districts | Regional priority setting, resource allocation |
| Counties/Cities | HSIP grant applications, Local Road Safety Plans |
| MPOs/PDCs | Regional safety planning, TIP project justification |

### Key Differentiators
- **Statewide scalability** - Works for any Virginia jurisdiction
- **FHWA methodology compliance** - Follows Systemic Safety Project Selection Tool
- **Integrated workflow** - Connects to CMF, Grants, and all analysis tabs
- **Automated reporting** - One-click HSIP-ready documentation

---

## 2. Strategic Vision

### 2.1 Design Philosophy

#### As a World-Class Traffic Engineer
The crash tree must support the complete systemic safety workflow:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SYSTEMIC SAFETY WORKFLOW                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│  │  STEP 1  │───▶│  STEP 2  │───▶│  STEP 3  │───▶│  STEP 4  │     │
│  │  Crash   │    │  Screen  │    │  Select  │    │Prioritize│     │
│  │   Tree   │    │ Locations│    │   CMFs   │    │ Projects │     │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘     │
│       │               │               │               │            │
│       ▼               ▼               ▼               ▼            │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│  │  This    │    │  Map &   │    │   CMF    │    │  Grants  │     │
│  │   Tab    │    │ Hotspots │    │   Tab    │    │   Tab    │     │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

#### As a World-Class UI Designer
The interface must balance:
- **Power** - Full analytical capability for experienced engineers
- **Simplicity** - Intuitive enough for occasional users
- **Guidance** - Teach systemic methodology through the interface itself
- **Beauty** - Professional, government-grade aesthetics

### 2.2 Tab Placement Rationale

**Recommended Position:** Immediately before Analysis tab

```
Dashboard → [CRASH TREE] → Analysis → Map → Hotspots → CMF → ...
```

**Justification:**
1. **Foundational Decision First** - Crash tree identifies WHAT to focus on before diving into detailed analysis
2. **Strategic Before Tactical** - User makes strategic focus decisions (Crash Tree) → Then explores detailed metrics (Analysis) → Then locations (Map/Hotspots)
3. **Systemic Methodology** - FHWA systemic approach starts with identifying focus crash type/facility BEFORE analyzing specific data
4. **Decision Funnel** - Establishes analysis scope upfront, making all subsequent tabs more focused and relevant

### 2.3 Statewide Scalability

The feature must work seamlessly across Virginia's jurisdictional hierarchy:

```
                    ┌─────────────────┐
                    │    VIRGINIA     │
                    │   (Statewide)   │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
    ┌────▼────┐        ┌────▼────┐        ┌────▼────┐
    │ Bristol │        │ Salem   │        │ NOVA    │
    │District │        │District │   ...  │District │
    └────┬────┘        └────┬────┘        └────┬────┘
         │                   │                   │
    ┌────▼────┐        ┌────▼────┐        ┌────▼────┐
    │ County/ │        │ County/ │        │ County/ │
    │  City   │        │  City   │        │  City   │
    └────┬────┘        └────┬────┘        └────┬────┘
         │                   │                   │
    ┌────▼────┐        ┌────▼────┐        ┌────▼────┐
    │  Route  │        │  Route  │        │  Route  │
    │Corridor │        │Corridor │        │Corridor │
    └─────────┘        └─────────┘        └─────────┘
```

---

## 3. User Experience Design

### 3.1 Interface Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  [Logo]  Dashboard  Crash Tree  Analysis  Map  Hotspots  CMF  ...    [?]   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ JURISDICTION: [Virginia ▼] [All Districts ▼] [Henrico County ▼]    │   │
│  │ COMPARE TO:   [☑ State Average] [☐ Select Another Jurisdiction]    │   │
│  │ DATE RANGE:   [2019-01-01] to [2023-12-31]  SEVERITY: [KA ▼]       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌──────────────┐ ┌─────────────────────────────────┐ ┌─────────────────┐  │
│  │              │ │                                 │ │                 │  │
│  │   TREE       │ │                                 │ │    SUMMARY      │  │
│  │   CONFIG     │ │      INTERACTIVE CRASH TREE     │ │    PANEL        │  │
│  │              │ │                                 │ │                 │  │
│  │ ○ Crash Type │ │         [Visualization]        │ │ Focus Crash:    │  │
│  │ ● Facility   │ │                                 │ │ ► Intersection  │  │
│  │              │ │                                 │ │                 │  │
│  │ Split By:    │ │                                 │ │ Focus Facility: │  │
│  │ [Urban/Rural]│ │                                 │ │ ► Rural Unsig.  │  │
│  │ [Int/Segment]│ │                                 │ │   High-Speed    │  │
│  │ [Control]    │ │                                 │ │   Stop-Ctrl     │  │
│  │ [Speed]      │ │                                 │ │                 │  │
│  │              │ │                                 │ │ Risk Factors:   │  │
│  │ [Advanced ▼] │ │                                 │ │ • ADT >2000     │  │
│  │              │ │                                 │ │ • Skewed angle  │  │
│  │              │ │                                 │ │                 │  │
│  └──────────────┘ └─────────────────────────────────┘ └─────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ [📊 View Data Table] [📈 Risk Factor Analysis] [🔗 Apply to Tabs]  │   │
│  │ [📄 Generate Report] [💾 Export Tree Image]    [📤 Share Analysis] │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Tree Visualization Design

#### Visual Hierarchy Principles

```
                           ┌─────────────────────┐
                           │ ALL SEVERE CRASHES  │
                           │    N = 12,450       │
                           │    100%             │
                           └──────────┬──────────┘
                                      │
              ┌───────────────────────┴───────────────────────┐
              │                                               │
    ┌─────────▼─────────┐                         ┌──────────▼──────────┐
    │   INTERSECTION    │ ◄── Highlighted         │   ROAD DEPARTURE    │
    │    N = 7,470      │     (Higher %)          │     N = 4,980       │
    │      60%          │                         │       40%           │
    └─────────┬─────────┘                         └─────────────────────┘
              │
    ┌─────────┴─────────┐
    │                   │
┌───▼───┐         ┌────▼────┐
│ RURAL │ ◄──     │  URBAN  │
│  65%  │ Focus   │   35%   │
└───┬───┘         └─────────┘
    │
    ▼
   ...
```

#### Color Coding System

| Element | Color | Meaning |
|---------|-------|---------|
| Dominant Path | `#1565C0` (Primary Blue) | Highest percentage branch |
| Secondary Path | `#90CAF9` (Light Blue) | Other branches |
| Selected Node | `#FF6F00` (Orange) | User's current selection |
| Fatal (K) | `#D32F2F` (Red) | Fatal crashes within node |
| Serious (A) | `#F57C00` (Orange) | Serious injury crashes |
| Comparison | `#7B1FA2` (Purple) | State average comparison |

#### Node Design

```
┌─────────────────────────────────────┐
│         RURAL INTERSECTIONS         │  ← Category Label
│  ═══════════════════════════════   │
│                                     │
│     N = 4,856    │    65.0%        │  ← Count & Percentage
│                  │                  │
│  ┌─────────────────────────────┐   │
│  │████████████████████░░░░░░░░│   │  ← Severity Bar
│  │  K: 45  │  A: 312  │ B+: 4499│   │
│  └─────────────────────────────┘   │
│                                     │
│  State Avg: 58.2%   ▲ +6.8%        │  ← Comparison (if enabled)
│                                     │
│  [+ Expand]                         │  ← Expand Control
└─────────────────────────────────────┘
```

### 3.3 Interaction Patterns

#### Progressive Disclosure
1. **Initial State**: Show only top-level split (e.g., Crash Type breakdown)
2. **First Click**: Expand to second level (e.g., Urban/Rural)
3. **Subsequent Clicks**: Continue drilling down
4. **"Auto-Expand Dominant Path"**: One-click to reveal focus facility

#### Guided Workflow
```
┌────────────────────────────────────────────────────────────────┐
│  STEP 1 of 3: Select Focus Crash Type                         │
│  ─────────────────────────────────────────────────────────     │
│  Click on the crash type with the highest percentage of       │
│  fatal and serious injury crashes, or click "Auto-Select"     │
│                                                                │
│  [Auto-Select Dominant Path]  [I'll Choose Manually]          │
└────────────────────────────────────────────────────────────────┘
```

### 3.4 Responsive Design

#### Desktop (1200px+)
- Full three-column layout
- Tree visualization at center
- Config panel left, Summary panel right

#### Tablet (768px - 1199px)
- Two-column layout
- Config panel collapses to top toolbar
- Summary panel moves below tree

#### Mobile (< 768px)
- Single column
- Vertical tree layout (top-to-bottom)
- Collapsible panels

---

## 4. Technical Architecture

### 4.1 State Management

```javascript
const crashTreeState = {
    // Jurisdiction Selection
    jurisdiction: {
        level: 'county',              // 'state' | 'district' | 'county' | 'route'
        statewide: false,
        districtCode: null,
        countyFIPS: '51087',          // Henrico example
        routeId: null,
        name: 'Henrico County'
    },

    // Comparison Settings
    comparison: {
        enabled: true,
        compareToState: true,
        compareToJurisdiction: null,
        compareToTimePeriod: null
    },

    // Filter Settings
    filters: {
        dateRange: {
            start: '2019-01-01',
            end: '2023-12-31'
        },
        severity: ['K', 'A'],         // KA crashes only by default
        crashTypes: 'all',            // or specific types
        roadSystem: 'all'             // 'state' | 'local' | 'all'
    },

    // Tree Configuration
    treeConfig: {
        treeType: 'facility',         // 'crashType' | 'facility'
        splitVariables: [
            'URBAN_RURAL',
            'INTERSECTION_FLAG',
            'TRAFFIC_CONTROL',
            'SPEED_CATEGORY'
        ],
        customSplits: [],
        maxDepth: 5
    },

    // Tree Data (computed)
    treeData: {
        root: null,                   // Hierarchical tree structure
        totalCrashes: 0,
        focusCrashType: null,
        focusFacility: null,
        dominantPath: []
    },

    // User Interaction State
    interaction: {
        expandedNodes: ['root'],
        selectedNode: null,
        highlightedPath: [],
        hoveredNode: null
    },

    // Risk Factor Analysis
    riskFactors: {
        available: [],                // All potential risk factors
        selected: [],                 // User-selected for analysis
        analyzed: [],                 // Results of overrepresentation analysis
        recommended: []               // System-recommended factors
    },

    // Report State
    report: {
        generating: false,
        lastGenerated: null,
        savedReports: []
    }
};
```

### 4.2 Core Functions

```javascript
// Tree Building Functions
function buildCrashTree(crashes, config) { }
function calculateNodeStatistics(node, crashes) { }
function identifyDominantPath(treeData) { }
function compareToBaseline(nodeStats, baselineStats) { }

// Data Processing
function filterCrashesByJurisdiction(crashes, jurisdiction) { }
function categorizeCrash(crash, splitVariable) { }
function calculateOverrepresentation(observed, expected) { }

// Risk Factor Analysis
function analyzeRiskFactors(crashes, focusFacility, factors) { }
function rankRiskFactors(analysisResults) { }
function suggestRiskFactors(focusCrashType, focusFacility) { }

// Integration Functions
function applyFocusToTabs(focusCrashType, focusFacility) { }
function syncWithCMFTab(focusFacility, riskFactors) { }
function syncWithGrantsTab(focusFacility, prioritizedLocations) { }
function updateAIContext(crashTreeState) { }

// Report Generation
function generateCrashTreeReport(state, options) { }
function exportTreeAsImage(treeElement, format) { }
function exportDataAsCSV(treeData) { }
```

### 4.3 Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW                                   │
└─────────────────────────────────────────────────────────────────────┘

    crashState.sampleRows
           │
           ▼
    ┌──────────────────┐
    │ Filter by        │
    │ Jurisdiction     │
    │ Date Range       │
    │ Severity         │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ Build Tree       │
    │ Structure        │◄─── treeConfig.splitVariables
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ Calculate Node   │
    │ Statistics       │◄─── comparison.baseline (if enabled)
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ Identify         │
    │ Dominant Path    │
    └────────┬─────────┘
             │
             ├────────────────────┬────────────────────┐
             ▼                    ▼                    ▼
    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
    │ Tree         │    │ Summary      │    │ Risk Factor  │
    │ Visualization│    │ Panel        │    │ Analysis     │
    └──────────────┘    └──────────────┘    └──────────────┘
             │                    │                    │
             └────────────────────┼────────────────────┘
                                  │
                                  ▼
                        ┌──────────────────┐
                        │ Apply to Other   │
                        │ Tabs             │
                        └──────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
              ┌─────────┐  ┌─────────┐  ┌─────────┐
              │   Map   │  │   CMF   │  │ Grants  │
              └─────────┘  └─────────┘  └─────────┘
```

---

## 5. Data Requirements

### 5.1 Required Crash Data Fields

| Field | Purpose | Tree Level | Example Values |
|-------|---------|------------|----------------|
| `CRASH_SEVERITY` | Severity filter | All | K, A, B, C, O |
| `CRASH_DATE` | Date filter | All | 2023-05-15 |
| `COUNTY_FIPS` | Jurisdiction | All | 51087 |
| `VDOT_DISTRICT` | Jurisdiction | All | Richmond |
| `URBAN_RURAL_CD` | Tree split | Level 2 | U, R |
| `INTERSECTION_TYPE` | Tree split | Level 3 | Intersection, Segment |
| `TRAFFIC_CONTROL` | Tree split | Level 4 | Signal, Stop, None |
| `SPEED_LIMIT` | Tree split | Level 5 | 25, 35, 45, 55+ |
| `COLLISION_TYPE` | Crash type tree | Level 1 | Angle, Rear-end, etc. |
| `ROUTE_NAME` | Location | Filter | US-250, I-64 |
| `ROAD_SYSTEM` | Filter | All | State, Local |

### 5.2 Derived/Calculated Fields

| Field | Calculation | Purpose |
|-------|-------------|---------|
| `SPEED_CATEGORY` | `SPEED_LIMIT >= 55 ? 'High' : 'Lower'` | Binary speed split |
| `CRASH_TYPE_GROUP` | Mapped from `COLLISION_TYPE` | Simplified categories |
| `SEVERITY_WEIGHT` | EPDO calculation | Weighted analysis |
| `JURISDICTION_LEVEL` | Hierarchy position | Aggregation |

### 5.3 Baseline/Comparison Data

For statewide comparisons, pre-compute:

```javascript
const stateBaseline = {
    byUrbanRural: {
        urban: { total: 45000, pct: 0.58, ka: 2100 },
        rural: { total: 32000, pct: 0.42, ka: 3200 }
    },
    byIntersection: {
        intersection: { total: 48000, pct: 0.62, ka: 2800 },
        segment: { total: 29000, pct: 0.38, ka: 2500 }
    },
    // ... etc for all split variables
};
```

### 5.4 Virginia-Specific Data Mapping

| Virginia DMV Field | Maps To | Notes |
|-------------------|---------|-------|
| `CRASH_SEVERITY_CD` | `CRASH_SEVERITY` | K=1, A=2, B=3, C=4, O=5 |
| `LOCALITY_FIPS_CD` | `COUNTY_FIPS` | 5-digit FIPS |
| `FUNC_CLASS_CD` | `ROAD_SYSTEM` | 1-2=Interstate, 3-4=Arterial, etc. |
| `URBANIZATION_CD` | `URBAN_RURAL_CD` | 1=Urban, 2=Rural |
| `INTER_TYPE_CD` | `INTERSECTION_TYPE` | 01=4-leg, 02=T, etc. |
| `TRF_CNTL_DEVICE_CD` | `TRAFFIC_CONTROL` | 01=Signal, 02=Stop, etc. |

---

## 6. Feature Specifications

### 6.1 Crash Type Tree

**Purpose:** Identify which crash type (emphasis area) should be the focus

**Default Split Variables:**
1. Level 1: Crash Type Category
   - Road Departure
   - Intersection
   - Pedestrian
   - Bicycle
   - Head-On/Sideswipe
   - Heavy Vehicle
   - Other

**Output:** Selected focus crash type (e.g., "Intersection crashes")

### 6.2 Facility Type Tree

**Purpose:** Identify which facility type has highest overrepresentation of severe crashes

**Default Split Variables:**
1. Level 1: Urban vs. Rural
2. Level 2: Intersection vs. Segment
3. Level 3: Traffic Control (Signalized / Stop-Controlled / Uncontrolled)
4. Level 4: Speed Category (High ≥55mph / Lower <55mph)
5. Level 5 (optional): Number of Approaches / Lanes

**Output:** Selected focus facility (e.g., "Rural unsignalized high-speed minor-approach stop-controlled intersections")

### 6.3 Custom Tree Builder

For advanced users:

```
┌────────────────────────────────────────────────────────────────┐
│  CUSTOM TREE BUILDER                                           │
│  ────────────────────────────────────────────────────────────  │
│                                                                │
│  Available Variables:           Your Tree Structure:           │
│  ┌──────────────────┐          ┌──────────────────┐           │
│  │ ☐ Urban/Rural    │          │ 1. [Urban/Rural ▼]│           │
│  │ ☐ Road System    │    ──►   │ 2. [Int/Segment ▼]│           │
│  │ ☐ Functional Cls │          │ 3. [Control Type▼]│           │
│  │ ☐ Speed Limit    │          │ 4. [Add Level... ]│           │
│  │ ☐ Weather        │          └──────────────────┘           │
│  │ ☐ Light Cond.    │                                         │
│  │ ☐ Day of Week    │          [Preview Tree]                 │
│  └──────────────────┘                                         │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 6.4 Risk Factor Analysis Panel

After focus facility is identified:

```
┌────────────────────────────────────────────────────────────────┐
│  RISK FACTOR ANALYSIS                                          │
│  Focus: Rural High-Speed Stop-Controlled Intersections         │
│  ────────────────────────────────────────────────────────────  │
│                                                                │
│  POTENTIAL RISK FACTORS        OVERREPRESENTATION              │
│                                                                │
│  ■ Major ADT >5,000 vpd       ████████████████░░░░ 82% vs 34% │
│  ■ Skewed intersection        █████████████░░░░░░░ 67% vs 28% │
│  □ No left-turn lane          ██████████░░░░░░░░░░ 51% vs 45% │
│  □ Near horizontal curve      ████████░░░░░░░░░░░░ 42% vs 38% │
│  □ >1 mile from signal        ██████░░░░░░░░░░░░░░ 31% vs 29% │
│                                                                │
│  ■ = Recommended (statistically overrepresented)               │
│                                                                │
│  [Select All Recommended]  [Apply to Location Screening]       │
└────────────────────────────────────────────────────────────────┘
```

### 6.5 Comparison Mode

```
┌────────────────────────────────────────────────────────────────┐
│  COMPARISON: Henrico County vs. Virginia Statewide             │
│  ────────────────────────────────────────────────────────────  │
│                                                                │
│                     Henrico    Virginia    Difference          │
│  Intersection         68%        61%        +7% ▲              │
│    └─ Urban           72%        58%       +14% ▲▲             │
│    └─ Rural           28%        42%       -14% ▼▼             │
│                                                                │
│  Road Departure       24%        31%        -7% ▼              │
│  Pedestrian           6%         5%         +1% ─              │
│  Bicycle              2%         3%         -1% ─              │
│                                                                │
│  ▲▲ Significantly higher than state   ▼▼ Significantly lower  │
│  ▲  Moderately higher                 ▼  Moderately lower     │
│  ─  Similar to state average                                   │
└────────────────────────────────────────────────────────────────┘
```

---

## 7. Integration with Existing Tabs

### 7.1 Integration Matrix

| Tab | Integration Type | Data Passed | User Action |
|-----|-----------------|-------------|-------------|
| **Dashboard** | Display | Focus crash type badge | Auto on selection |
| **Analysis** | Filter preset | Crash type filter | "View in Analysis" |
| **Map** | Filter + Highlight | Focus facility locations | "Show on Map" |
| **Hotspots** | Ranking weight | Focus facility boost | Auto adjustment |
| **CMF** | Pre-filter | Applicable CMFs only | "Find Countermeasures" |
| **Warrants** | Context | Focus crash type | Info display |
| **Grants** | Scoring | Focus facility weight | Auto in ranking |
| **Before/After** | Comparison type | Focus crash type | Study design |
| **Safety Focus** | Category | Focus crash type | Direct link |
| **AI Assistant** | Context | Full tree state | Informed analysis |

### 7.2 Integration Implementation

#### "Apply to All Tabs" Function

```javascript
function applyFocusToTabs() {
    const { focusCrashType, focusFacility, riskFactors } = crashTreeState.treeData;

    // Update global selection state
    selectionState.focusCrashType = focusCrashType;
    selectionState.focusFacility = focusFacility;
    selectionState.riskFactors = riskFactors.selected;

    // Notify each tab
    updateDashboardFocusBadge(focusCrashType);
    updateMapFocusFilter(focusFacility);
    updateHotspotsWeighting(focusFacility);
    updateCMFFilter(focusFacility, riskFactors.selected);
    updateGrantsScoring(focusFacility);
    updateAIContext({
        focusCrashType,
        focusFacility,
        riskFactors: riskFactors.selected,
        treeData: crashTreeState.treeData
    });

    showToast('Focus applied to all tabs', 'success');
}
```

#### CMF Tab Integration

When user clicks "Find Countermeasures":

```javascript
function navigateToCMFWithFocus() {
    // Pre-filter CMF database
    cmfState.filters.facilityType = crashTreeState.treeData.focusFacility;
    cmfState.filters.crashType = crashTreeState.treeData.focusCrashType;

    // Highlight recommended CMFs based on risk factors
    cmfState.highlightedCMFs = matchCMFsToRiskFactors(
        crashTreeState.riskFactors.selected
    );

    // Navigate to CMF tab
    switchToTab('cmf');

    // Show guidance message
    showGuidance(`Showing ${cmfState.highlightedCMFs.length} countermeasures
                  applicable to ${focusFacility}`);
}
```

#### Grants Tab Integration

```javascript
function updateGrantsWithFocus() {
    // Add focus facility match as ranking criterion
    grantState.rankingCriteria.focusFacilityMatch = {
        enabled: true,
        weight: 1.5,  // 50% bonus for matching focus facility
        facility: crashTreeState.treeData.focusFacility
    };

    // Re-rank locations
    recalculateGrantRankings();

    // Update UI to show focus-based ranking
    updateGrantsUI();
}
```

### 7.3 AI Assistant Integration

```javascript
function getAIContextWithCrashTree() {
    return {
        ...getExistingAIContext(),

        crashTreeAnalysis: {
            completed: crashTreeState.treeData.focusFacility !== null,
            focusCrashType: crashTreeState.treeData.focusCrashType,
            focusFacility: crashTreeState.treeData.focusFacility,
            riskFactors: crashTreeState.riskFactors.selected,
            jurisdiction: crashTreeState.jurisdiction.name,
            comparisonToState: crashTreeState.comparison.enabled ?
                calculateComparisonSummary() : null
        },

        systemicAnalysisPrompt: `
            User has completed crash tree analysis for ${crashTreeState.jurisdiction.name}.
            Focus crash type: ${crashTreeState.treeData.focusCrashType}
            Focus facility: ${crashTreeState.treeData.focusFacility}
            Key risk factors: ${crashTreeState.riskFactors.selected.join(', ')}

            When answering questions about safety priorities, countermeasures, or
            project selection, reference this systemic analysis as the foundation.
        `
    };
}
```

---

## 8. Report Generation System

### 8.1 Report Types

| Report Type | Purpose | Audience | Format |
|-------------|---------|----------|--------|
| **Executive Summary** | Quick overview for leadership | Elected officials, managers | 2-page PDF |
| **Technical Report** | Detailed methodology | Engineers, FHWA | 10-15 page PDF |
| **HSIP Application** | Grant documentation | VDOT, FHWA | HSIP-formatted PDF |
| **LRSP Chapter** | Local Road Safety Plan section | Planners | Word/PDF |
| **Presentation** | Meeting slides | Various | PowerPoint/PDF |
| **Data Export** | Raw analysis data | Analysts | CSV/Excel |

### 8.2 Executive Summary Report Template

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│     [JURISDICTION LOGO]         SYSTEMIC SAFETY ANALYSIS           │
│                                 Executive Summary                   │
│                                                                     │
│     [Jurisdiction Name]         Date: [Generated Date]              │
│     Analysis Period: [Date Range]                                   │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  KEY FINDINGS                                                       │
│  ═══════════════════════════════════════════════════════════════   │
│                                                                     │
│  Focus Crash Type: [CRASH TYPE]                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  [Crash Type Breakdown Chart - horizontal bar]              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Focus Facility: [FACILITY DESCRIPTION]                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  [Crash Tree Diagram - simplified version]                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Key Risk Factors:                                                 │
│  • [Risk Factor 1] - [X]% overrepresented                         │
│  • [Risk Factor 2] - [X]% overrepresented                         │
│  • [Risk Factor 3] - [X]% overrepresented                         │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  RECOMMENDED ACTIONS                                               │
│  ═══════════════════════════════════════════════════════════════   │
│                                                                     │
│  1. [Prioritized countermeasure recommendation]                    │
│  2. [Prioritized countermeasure recommendation]                    │
│  3. [Prioritized countermeasure recommendation]                    │
│                                                                     │
│  Estimated locations for improvement: [N] sites                    │
│  Potential crash reduction: [X] severe crashes/year                │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Methodology: FHWA Systemic Safety Project Selection Tool          │
│  Data Source: Virginia DMV Crash Database                          │
│  Generated by: Virginia Crash Analysis Tool                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.3 HSIP Application Report Template

```
┌─────────────────────────────────────────────────────────────────────┐
│  HSIP SYSTEMIC SAFETY PROJECT APPLICATION                          │
│  Supporting Documentation                                           │
│                                                                     │
│  Applicant: [Jurisdiction Name]                                    │
│  Project Title: [Project Name]                                     │
│  Date: [Date]                                                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. SAFETY PROBLEM IDENTIFICATION                                  │
│  ───────────────────────────────────────────────────────────────   │
│                                                                     │
│  1.1 Focus Crash Type                                              │
│      [Table: Crash type breakdown with counts and percentages]     │
│      [Chart: Crash type comparison to state average]               │
│                                                                     │
│  1.2 Focus Facility Type                                           │
│      [Crash Tree Diagram]                                          │
│      [Narrative explanation of selection]                          │
│                                                                     │
│  1.3 Risk Factor Analysis                                          │
│      [Table: Risk factors with overrepresentation analysis]        │
│      [Chart: Risk factor comparison]                               │
│                                                                     │
│  2. CANDIDATE LOCATION IDENTIFICATION                              │
│  ───────────────────────────────────────────────────────────────   │
│                                                                     │
│  [Table: Prioritized locations with risk factor scores]            │
│  [Map: Location visualization]                                     │
│                                                                     │
│  3. COUNTERMEASURE SELECTION                                       │
│  ───────────────────────────────────────────────────────────────   │
│                                                                     │
│  [Table: Selected countermeasures with CMFs]                       │
│  [Justification for countermeasure selection]                      │
│                                                                     │
│  4. BENEFIT-COST ANALYSIS                                          │
│  ───────────────────────────────────────────────────────────────   │
│                                                                     │
│  [Calculations and summary]                                        │
│                                                                     │
│  APPENDICES                                                        │
│  A. Methodology Description                                        │
│  B. Data Sources                                                   │
│  C. Detailed Crash Data                                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.4 Report Generation Functions

```javascript
async function generateReport(reportType, options = {}) {
    const reportConfig = {
        executive: {
            template: 'executive_summary',
            pages: 2,
            sections: ['keyFindings', 'recommendations']
        },
        technical: {
            template: 'technical_report',
            pages: 15,
            sections: ['methodology', 'dataAnalysis', 'treeDetails',
                      'riskFactors', 'recommendations', 'appendices']
        },
        hsip: {
            template: 'hsip_application',
            pages: 10,
            sections: ['problemId', 'candidateLocations',
                      'countermeasures', 'benefitCost']
        },
        lrsp: {
            template: 'lrsp_chapter',
            pages: 8,
            sections: ['introduction', 'methodology', 'findings',
                      'recommendations']
        }
    };

    const config = reportConfig[reportType];

    // Gather data
    const reportData = {
        jurisdiction: crashTreeState.jurisdiction,
        dateRange: crashTreeState.filters.dateRange,
        treeData: crashTreeState.treeData,
        riskFactors: crashTreeState.riskFactors,
        comparison: crashTreeState.comparison.enabled ?
            calculateComparisonData() : null,
        generatedDate: new Date().toISOString(),
        toolVersion: APP_VERSION
    };

    // Generate tree image
    const treeImage = await exportTreeAsImage('png');

    // Generate charts
    const charts = await generateReportCharts(reportData);

    // Build PDF
    const pdf = await buildPDF(config.template, {
        ...reportData,
        treeImage,
        charts,
        ...options
    });

    return pdf;
}

async function exportTreeAsImage(format = 'png') {
    const treeElement = document.getElementById('crash-tree-container');

    // Use html2canvas for raster, or custom SVG export for vector
    if (format === 'svg') {
        return exportTreeAsSVG(treeElement);
    } else {
        const canvas = await html2canvas(treeElement, {
            scale: 2,  // Higher resolution
            backgroundColor: '#ffffff'
        });
        return canvas.toDataURL(`image/${format}`);
    }
}

function exportDataAsCSV() {
    const rows = flattenTreeToRows(crashTreeState.treeData.root);

    const headers = [
        'Level', 'Category', 'Count', 'Percentage',
        'Fatal', 'Serious', 'StateAverage', 'Difference'
    ];

    const csv = [
        headers.join(','),
        ...rows.map(row => headers.map(h => row[h]).join(','))
    ].join('\n');

    downloadFile(csv, 'crash_tree_data.csv', 'text/csv');
}
```

### 8.5 Sharing and Collaboration

```
┌────────────────────────────────────────────────────────────────┐
│  SHARE ANALYSIS                                                │
│  ────────────────────────────────────────────────────────────  │
│                                                                │
│  Generate Shareable Link:                                      │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ https://va-crash.tool/tree/abc123xyz                   │   │
│  └────────────────────────────────────────────────────────┘   │
│  [Copy Link]  Link expires in: [30 days ▼]                    │
│                                                                │
│  Download Options:                                             │
│  [📄 PDF Report]  [📊 Excel Data]  [🖼️ Tree Image]           │
│                                                                │
│  Save to My Analyses:                                          │
│  Name: [Henrico 2023 Systemic Analysis_____________]          │
│  [💾 Save]                                                     │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 9. Implementation Phases

### Phase 1: Foundation (MVP)
**Duration:** 4-6 weeks
**Goal:** Basic crash tree functionality

#### Deliverables:
- [ ] New "Crash Tree" tab with basic layout
- [ ] Jurisdiction selector (state/district/county)
- [ ] Facility type tree with 4 default levels
- [ ] Interactive tree visualization (expand/collapse)
- [ ] Dominant path highlighting
- [ ] Basic summary panel
- [ ] Tree image export (PNG)

#### Technical Tasks:
1. Create `crashTreeState` management
2. Implement `buildCrashTree()` function
3. Create tree visualization component
4. Add jurisdiction filtering
5. Implement dominant path algorithm
6. Create summary panel
7. Add PNG export

### Phase 2: Analysis Enhancement
**Duration:** 3-4 weeks
**Goal:** Risk factor analysis and comparison

#### Deliverables:
- [ ] Crash type tree option
- [ ] Risk factor analysis panel
- [ ] Overrepresentation calculations
- [ ] State average comparison
- [ ] Comparison visualization
- [ ] Data table view

#### Technical Tasks:
1. Implement crash type tree builder
2. Create risk factor analysis functions
3. Pre-compute state baselines
4. Build comparison visualization
5. Add data table component

### Phase 3: Integration
**Duration:** 3-4 weeks
**Goal:** Connect to other tabs

#### Deliverables:
- [ ] "Apply to All Tabs" functionality
- [ ] CMF tab integration
- [ ] Grants tab integration
- [ ] Map tab filter sync
- [ ] AI Assistant context update
- [ ] Dashboard focus badge

#### Technical Tasks:
1. Create `applyFocusToTabs()` function
2. Update CMF filter logic
3. Update Grants scoring algorithm
4. Add Map filter presets
5. Extend AI context
6. Add Dashboard components

### Phase 4: Reporting
**Duration:** 3-4 weeks
**Goal:** Professional report generation

#### Deliverables:
- [ ] Executive Summary report
- [ ] Technical Report
- [ ] HSIP Application report
- [ ] CSV data export
- [ ] SVG tree export
- [ ] Shareable links

#### Technical Tasks:
1. Create report templates
2. Implement PDF generation
3. Build chart generation
4. Create export functions
5. Implement sharing system

### Phase 5: Advanced Features
**Duration:** 4-6 weeks
**Goal:** Power user features

#### Deliverables:
- [ ] Custom tree builder
- [ ] Multi-jurisdiction comparison
- [ ] Time period comparison
- [ ] Saved analyses
- [ ] Batch report generation
- [ ] API endpoints (for advanced users)

#### Technical Tasks:
1. Build custom tree UI
2. Implement multi-comparison
3. Add temporal analysis
4. Create saved analyses storage
5. Build batch processing
6. Create API layer

---

## 10. Testing Strategy

### 10.1 Unit Tests

```javascript
// Tree building tests
describe('buildCrashTree', () => {
    it('should create root node with all crashes', () => {});
    it('should split by urban/rural correctly', () => {});
    it('should calculate percentages accurately', () => {});
    it('should handle empty data gracefully', () => {});
    it('should respect severity filter', () => {});
});

// Dominant path tests
describe('identifyDominantPath', () => {
    it('should find highest percentage path', () => {});
    it('should handle ties correctly', () => {});
    it('should work with custom depth', () => {});
});

// Risk factor tests
describe('analyzeRiskFactors', () => {
    it('should calculate overrepresentation correctly', () => {});
    it('should rank factors by significance', () => {});
    it('should handle missing data', () => {});
});
```

### 10.2 Integration Tests

```javascript
describe('Tab Integration', () => {
    it('should update CMF filters when focus applied', () => {});
    it('should update Grants scoring when focus applied', () => {});
    it('should update Map filters when focus applied', () => {});
    it('should update AI context when focus applied', () => {});
});

describe('Report Generation', () => {
    it('should generate valid PDF for executive summary', () => {});
    it('should include all required HSIP sections', () => {});
    it('should export tree image at correct resolution', () => {});
});
```

### 10.3 User Acceptance Testing

| Test Case | Expected Result | Pass Criteria |
|-----------|-----------------|---------------|
| Load tree for Henrico County | Tree displays within 3 seconds | Tree visible, no errors |
| Compare to state average | Comparison data shown | Differences calculated correctly |
| Expand all nodes | Full tree visible | All levels accessible |
| Generate executive report | PDF downloaded | PDF opens, content correct |
| Apply focus to CMF tab | CMF tab filtered | Only applicable CMFs shown |
| Export as image | PNG downloaded | Image clear at 300dpi |

### 10.4 Performance Testing

| Operation | Target | Maximum |
|-----------|--------|---------|
| Initial tree load | < 2 seconds | 5 seconds |
| Node expansion | < 100ms | 500ms |
| Statewide comparison | < 5 seconds | 10 seconds |
| Report generation | < 10 seconds | 30 seconds |
| Image export | < 3 seconds | 10 seconds |

### 10.5 Cross-Browser Testing

| Browser | Version | Status |
|---------|---------|--------|
| Chrome | Latest 2 | Required |
| Firefox | Latest 2 | Required |
| Safari | Latest 2 | Required |
| Edge | Latest 2 | Required |
| IE 11 | - | Not supported |

---

## Appendices

### Appendix A: Virginia SHSP Emphasis Areas Mapping

| Virginia SHSP Emphasis Area | Crash Tree Mapping |
|-----------------------------|-------------------|
| Roadway Departure | `COLLISION_TYPE` in [ROR, FO, etc.] |
| Intersection Safety | `INTERSECTION_TYPE` != null |
| Pedestrian Safety | `PEDESTRIAN_FLAG` = Y |
| Bicycle Safety | `BICYCLE_FLAG` = Y |
| Speed Management | `SPEED_RELATED` = Y |
| Impaired Driving | `ALCOHOL_FLAG` = Y or `DRUG_FLAG` = Y |
| Occupant Protection | `UNRESTRAINED` = Y |
| Young Drivers | `DRIVER_AGE` < 25 |
| Older Drivers | `DRIVER_AGE` >= 65 |
| Heavy Vehicles | `VEHICLE_TYPE` in [Truck, Bus, etc.] |

### Appendix B: FHWA Systemic Safety Methodology Reference

Source: FHWA-SA-13-019 "Systemic Safety Project Selection Tool"

Key principles implemented:
1. Risk-based screening (not just crash history)
2. Focus on severe crashes (KA)
3. Binary tree splits for manageable analysis
4. Overrepresentation analysis for risk factors
5. Proactive site identification

### Appendix C: Data Dictionary

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `treeNodeId` | string | Unique node identifier | "root_urban_int_signal" |
| `level` | number | Depth in tree (0=root) | 2 |
| `category` | string | Node category name | "Urban" |
| `crashCount` | number | Total crashes in node | 4523 |
| `kaCount` | number | Fatal+Serious crashes | 312 |
| `percentage` | number | Percent of parent node | 0.65 |
| `stateAverage` | number | State average percentage | 0.58 |
| `children` | array | Child nodes | [...] |

### Appendix D: Glossary

| Term | Definition |
|------|------------|
| **Focus Crash Type** | The crash type with greatest severe crash representation |
| **Focus Facility** | The facility type with highest risk for focus crash type |
| **Dominant Path** | The tree branch with highest percentages at each level |
| **Overrepresentation** | When crash percentage exceeds system percentage |
| **Risk Factor** | Characteristic associated with higher crash likelihood |
| **Systemic Analysis** | Network-wide analysis vs. site-specific (spot) analysis |
| **KA Crashes** | Fatal (K) and Serious Injury (A) crashes |
| **HSIP** | Highway Safety Improvement Program (federal funding) |
| **SHSP** | Strategic Highway Safety Plan (state safety plan) |
| **LRSP** | Local Road Safety Plan |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Claude | Initial comprehensive plan |

---

*This implementation plan follows FHWA's Systemic Safety Project Selection Tool methodology and Virginia-specific crash data standards.*
