# Before & After Study Feature - Implementation Plan

## Overview

Add a **Before & After Study** tab under the Reports section that allows users to:
1. Select a polygon-based segment from the map
2. Configure study parameters (treatment type, dates, analysis method)
3. Run comprehensive before/after crash analysis
4. Generate professional reports for HSIP documentation

---

## Phase 1: UI Structure & Navigation

### 1.1 Add Navigation Button
**Location**: Within the REPORTS section in the sidebar navigation

```
REPORTS (collapsible section)
├── Reports (existing)
└── Before & After Study (NEW)
```

**Tasks**:
- [ ] Add new navigation button with calendar/chart icon
- [ ] Implement `showTab('tab-before-after')` handler
- [ ] Add active state styling consistent with existing tabs

### 1.2 Create Tab Content Structure
**Location**: After `tab-reports` section in HTML

**Layout Components**:
1. **Header Section**: Title, description, help tooltip
2. **Study Configuration Panel**: Study type, location, treatment type dropdowns
3. **Timeline Configuration**: Treatment date, construction duration, study period length
4. **Before/After Period Display**: Visual date range cards (color-coded)
5. **Analysis Method Selector**: Empirical Bayes, Naive, etc.
6. **Advanced Options**: Collapsible section for expert settings
7. **Action Buttons**: Run Analysis, Reset
8. **Results Container**: Hidden until analysis runs

---

## Phase 2: Map Integration & Polygon Selection

### 2.1 Location Selection System
**Three Selection Modes**:

| Mode | Description | Data Source |
|------|-------------|-------------|
| **Map Selection** | Draw polygon on map | `selectedCrashesFromDrawing` |
| **Route Selection** | Select from route dropdown | `crashState.routes` |
| **Node Selection** | Select intersection | `crashState.nodes` |

### 2.2 Map Drawing Integration
**Leverage Existing System**:
- Use existing `startDrawing('polygon')` function
- Modify `finishDrawing()` to populate Before/After location selector
- Add "Use for B/A Study" button to drawing selection panel

**New Functions Needed**:
```javascript
function selectLocationForBA(source) {
  // source: 'drawing' | 'route' | 'node'
  // Populate baState.selectedLocation
  // Update location dropdown text
  // Enable/disable run button based on validity
}

function syncMapSelectionToBA() {
  // Called when polygon drawing completes
  // Transfers selectedCrashesFromDrawing to baState
  // Shows selection summary (X crashes in polygon)
}
```

### 2.3 Location Display
- Show selected location name in dropdown
- Display crash count preview
- Option to "View on Map" or "Clear Selection"
- Visual indicator when selection is valid

---

## Phase 3: Study Configuration Logic

### 3.1 State Management
**Create `baState` Object**:
```javascript
const baState = {
  // Configuration
  studyType: 'intersection',        // 'intersection' | 'corridor' | 'area'
  treatmentType: '',                // e.g., 'Traffic Signal Installation'
  treatmentDate: null,              // Date object
  constructionDuration: 3,          // months
  studyPeriodYears: 3,              // 1, 3, or 5 years
  analysisMethod: 'empirical_bayes', // 'naive' | 'empirical_bayes'

  // Location
  selectedLocation: null,           // { type, id, name, crashes[] }
  locationCrashes: [],              // All crashes at location

  // Periods (auto-calculated)
  beforePeriod: { start: null, end: null, days: 0 },
  afterPeriod: { start: null, end: null, days: 0 },

  // Filtered crash data
  beforeCrashes: [],
  afterCrashes: [],

  // Results
  results: null,
  reportGenerated: false
};
```

### 3.2 Date Calculation Logic
**Auto-calculate Before/After Periods**:
```
Treatment Date: User Input
Construction Duration: User Input (months)

BEFORE Period:
  End = Treatment Date - 1 day
  Start = End - (studyPeriodYears × 365 days)

AFTER Period:
  Start = Treatment Date + Construction Duration
  End = Today's Date (or specified end)
```

**Real-time Updates**:
- Update period displays when any input changes
- Show duration in years and days
- Validate: After period must have at least 6 months of data
- Warning if periods are unbalanced

### 3.3 Study Type Options
| Study Type | Description |
|------------|-------------|
| Intersection Study | Single intersection node |
| Corridor Study | Route segment between two points |
| Area/Zone Study | Polygon-defined geographic area |

### 3.4 Treatment Type Options
Pre-populated list from FHWA Proven Safety Countermeasures:
- Traffic Signal Installation
- Roundabout Conversion
- Left-Turn Phasing
- Pedestrian Countdown Signals
- Road Diet/Lane Reduction
- Speed Management
- Lighting Improvements
- Curve Warning Signs
- Rumble Strips
- Median Installation
- Access Management
- Custom (user-defined)

---

## Phase 4: Analysis Engine

### 4.1 Core Analysis Function
```javascript
function runBeforeAfterAnalysis() {
  // Step 1: Validate inputs
  if (!validateBAStudyConfig()) return;

  // Step 2: Filter crashes into before/after arrays
  filterCrashesIntoPeriods();

  // Step 3: Calculate base statistics for both periods
  calculatePeriodStatistics();

  // Step 4: Apply selected analysis method
  if (baState.analysisMethod === 'empirical_bayes') {
    runEmpiricalBayesAnalysis();
  } else {
    runNaiveAnalysis();
  }

  // Step 5: Calculate change metrics
  calculateChangeMetrics();

  // Step 6: Perform statistical significance tests
  runStatisticalTests();

  // Step 7: Generate results display
  displayBAResults();
}
```

### 4.2 Statistics Calculations

**Per Period Metrics**:
| Metric | Formula |
|--------|---------|
| Total Crashes | Count of crashes |
| K (Fatal) | Sum of K_People |
| A (Serious Injury) | Sum of A_People |
| B (Minor Injury) | Sum of B_People |
| C (Possible Injury) | Sum of C_People |
| O (PDO) | Count of PDO crashes |
| EPDO | K×13.5 + A×6.0 + B×3.0 + C×1.5 + O×1.0 |
| K+A Crashes | Count with K or A injuries |
| Crash Rate | Crashes per year (normalized) |
| Severity Index | EPDO / Total Crashes |

### 4.3 Naive Method
**Simple Before/After Comparison**:
```javascript
function runNaiveAnalysis() {
  // Normalize for different period lengths
  const beforeRate = baState.beforeCrashes.length / (baState.beforePeriod.days / 365);
  const afterRate = baState.afterCrashes.length / (baState.afterPeriod.days / 365);

  // Calculate percent change
  const percentChange = ((afterRate - beforeRate) / beforeRate) * 100;

  // Note: Does not account for regression-to-mean bias
}
```

### 4.4 Empirical Bayes (EB) Method
**HSIP-Recommended Approach**:
```javascript
function runEmpiricalBayesAnalysis() {
  // Step 1: Calculate expected crashes using reference group
  // (Use jurisdiction-wide or similar location averages)
  const expectedBefore = calculateExpectedCrashes(baState.beforePeriod);

  // Step 2: Calculate weight factor (k)
  // k = 1 / (1 + (variance/mean))
  const weightFactor = calculateWeightFactor();

  // Step 3: Calculate EB estimate
  // EB = k × observed + (1-k) × expected
  const ebBeforeEstimate = weightFactor * baState.beforeCrashes.length +
                           (1 - weightFactor) * expectedBefore;

  // Step 4: Project expected "after" crashes without treatment
  const projectedAfterWithoutTreatment = projectCrashes(ebBeforeEstimate);

  // Step 5: Calculate Crash Modification Factor (CMF)
  const CMF = baState.afterCrashes.length / projectedAfterWithoutTreatment;

  // Step 6: Calculate Crash Reduction Factor (CRF)
  const CRF = (1 - CMF) * 100;  // Percent reduction
}
```

### 4.5 Statistical Significance Tests
```javascript
function runStatisticalTests() {
  // Chi-square test for independence
  const chiSquare = calculateChiSquare(
    baState.beforeCrashes.length,
    baState.afterCrashes.length
  );

  // Calculate p-value
  const pValue = calculatePValue(chiSquare);

  // 95% Confidence Interval for CMF
  const confidenceInterval = calculateCI(baState.results.CMF, 0.95);

  // Determine if statistically significant
  baState.results.isSignificant = pValue < 0.05;
  baState.results.confidenceLevel = (1 - pValue) * 100;
}
```

---

## Phase 5: Results Display

### 5.1 Results Section Layout

```
┌─────────────────────────────────────────────────────────┐
│ 📊 Before & After Study Results                         │
├─────────────────────────────────────────────────────────┤
│ Study Summary                                           │
│ Location: S-VA043PR E PARHAM RD | Treatment: Signal    │
│ Method: Empirical Bayes | Confidence: 95%              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │   BEFORE    │    │    AFTER    │    │   CHANGE    │ │
│  │  12 crashes │ →  │  7 crashes  │ =  │   -41.7%    │ │
│  │  3 years    │    │  2.7 years  │    │  ✓ Signif.  │ │
│  └─────────────┘    └─────────────┘    └─────────────┘ │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ Key Performance Indicators                              │
│ ┌────────┬────────┬────────┬────────┬────────┐        │
│ │ Metric │ Before │ After  │ Change │ % Chg  │        │
│ ├────────┼────────┼────────┼────────┼────────┤        │
│ │ Total  │   12   │   7    │   -5   │ -41.7% │        │
│ │ K+A    │    2   │   0    │   -2   │ -100%  │        │
│ │ EPDO   │  45.0  │  21.5  │ -23.5  │ -52.2% │        │
│ │ Rate   │  4.0/yr│  2.6/yr│  -1.4  │ -35.0% │        │
│ └────────┴────────┴────────┴────────┴────────┘        │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ [Chart: Before vs After Comparison - Bar Chart]         │
│ [Chart: Timeline with Treatment Date Marked]            │
├─────────────────────────────────────────────────────────┤
│ Statistical Analysis                                    │
│ • CMF: 0.58 (95% CI: 0.35 - 0.81)                      │
│ • CRF: 42% crash reduction                              │
│ • p-value: 0.023 (Statistically Significant ✓)         │
├─────────────────────────────────────────────────────────┤
│ [📄 Generate Report] [📊 Export Data] [🗺️ View on Map] │
└─────────────────────────────────────────────────────────┘
```

### 5.2 Visualization Charts

**Chart 1: Before/After Comparison Bar Chart**
- Grouped bars: Total, K, A, B, C, O, EPDO
- Color coding: Before (coral), After (green)

**Chart 2: Timeline Chart**
- X-axis: Date range covering both periods
- Y-axis: Crash count
- Vertical line marking treatment date
- Shaded regions for construction period

**Chart 3: Severity Distribution Pie Charts**
- Side-by-side pies for Before/After
- Show shift in severity composition

### 5.3 Interpretation Guidance
Display contextual help based on results:
- If significant reduction: "The treatment appears effective..."
- If not significant: "Results are inconclusive. Consider..."
- If increase: "Crashes increased after treatment. Possible factors..."

---

## Phase 6: Report Generation

### 6.1 Report Structure
```
╔══════════════════════════════════════════════════════════╗
║           BEFORE & AFTER STUDY REPORT                    ║
║           [Location Name]                                 ║
╠══════════════════════════════════════════════════════════╣
║ 1. EXECUTIVE SUMMARY                                      ║
║    - Study objective                                      ║
║    - Key findings (CMF, CRF, significance)               ║
║    - Recommendation                                       ║
╠══════════════════════════════════════════════════════════╣
║ 2. STUDY METHODOLOGY                                      ║
║    - Study type and location description                 ║
║    - Treatment description                                ║
║    - Analysis method (EB vs Naive)                       ║
║    - Data sources and limitations                        ║
╠══════════════════════════════════════════════════════════╣
║ 3. STUDY PERIODS                                          ║
║    - Before period: [dates], [duration], [crash count]   ║
║    - After period: [dates], [duration], [crash count]    ║
║    - Construction period exclusion                        ║
╠══════════════════════════════════════════════════════════╣
║ 4. CRASH DATA SUMMARY                                     ║
║    - Before period statistics table                       ║
║    - After period statistics table                        ║
║    - Change summary                                       ║
╠══════════════════════════════════════════════════════════╣
║ 5. STATISTICAL ANALYSIS                                   ║
║    - Analysis method description                          ║
║    - CMF calculation                                      ║
║    - Confidence intervals                                 ║
║    - Statistical significance determination              ║
╠══════════════════════════════════════════════════════════╣
║ 6. FINDINGS & CONCLUSIONS                                 ║
║    - Effectiveness determination                          ║
║    - Comparison to expected CMF from literature          ║
║    - Caveats and limitations                             ║
╠══════════════════════════════════════════════════════════╣
║ 7. APPENDICES                                             ║
║    - A: Crash listing (before period)                    ║
║    - B: Crash listing (after period)                     ║
║    - C: Map of study location                            ║
╚══════════════════════════════════════════════════════════╝
```

### 6.2 Export Options
- **PDF Report**: Full formatted report with charts
- **Excel Export**: Data tables for further analysis
- **CSV Export**: Raw crash data for both periods

---

## Phase 7: Advanced Options

### 7.1 Advanced Configuration (Collapsible)
| Option | Description | Default |
|--------|-------------|---------|
| Reference Group | Comparison data for EB method | Jurisdiction-wide |
| Exclude Holidays | Remove holiday crashes | No |
| Weather Normalization | Adjust for weather differences | No |
| AADT Adjustment | Account for traffic volume changes | If available |
| Overdispersion Parameter | For EB calculation | Auto-calculate |
| Confidence Level | For statistical tests | 95% |

### 7.2 Comparison Reference Data
For EB method, use one of:
1. **Jurisdiction Average**: All similar locations in county
2. **State SPF**: Virginia Safety Performance Functions
3. **Custom Reference**: User-provided expected crash rate

---

## Phase 8: Integration & Testing

### 8.1 Integration Points
| Component | Integration |
|-----------|-------------|
| Map Tab | Polygon selection syncs to BA location |
| Crash Data | Filters from `crashState.sampleRows` |
| Reports Tab | Add BA Study to report type dropdown |
| Export System | Reuse existing CSV/PDF export functions |

### 8.2 Testing Scenarios
1. **Polygon Selection**: Draw polygon, verify crash count transfers
2. **Date Validation**: Test overlapping periods, future dates, insufficient data
3. **Calculation Accuracy**: Verify EPDO, rates, CMF calculations
4. **Edge Cases**: Zero crashes in period, single crash, very long periods
5. **Report Generation**: PDF export, formatting, chart rendering

---

## Implementation Checklist

### Phase 1: UI Structure
- [ ] Add sidebar navigation button for "Before & After Study"
- [ ] Create tab content container with ID `tab-before-after`
- [ ] Add study configuration panel HTML
- [ ] Add timeline configuration controls
- [ ] Add before/after period display cards
- [ ] Add analysis method selector
- [ ] Add advanced options collapsible section
- [ ] Add action buttons (Run Analysis, Reset)
- [ ] Add results container (hidden initially)

### Phase 2: Map Integration
- [ ] Add location selector dropdown with map selection option
- [ ] Modify `finishDrawing()` to support BA study selection
- [ ] Create `syncMapSelectionToBA()` function
- [ ] Add "Use for B/A Study" button to drawing panel
- [ ] Display crash count preview for selected location

### Phase 3: Configuration Logic
- [ ] Create `baState` object for state management
- [ ] Implement date calculation functions
- [ ] Add real-time period updates on input change
- [ ] Implement period validation
- [ ] Populate treatment type dropdown

### Phase 4: Analysis Engine
- [ ] Implement `runBeforeAfterAnalysis()` main function
- [ ] Create `filterCrashesIntoPeriods()` function
- [ ] Implement naive analysis calculations
- [ ] Implement Empirical Bayes calculations
- [ ] Add statistical significance tests
- [ ] Calculate CMF and confidence intervals

### Phase 5: Results Display
- [ ] Create results section HTML template
- [ ] Implement KPI comparison cards
- [ ] Create before/after comparison chart
- [ ] Create timeline visualization chart
- [ ] Add interpretation guidance display
- [ ] Style results section with appropriate colors

### Phase 6: Report Generation
- [ ] Create BA study report template
- [ ] Implement `generateBAReport()` function
- [ ] Add PDF export capability
- [ ] Add Excel/CSV export for data tables

### Phase 7: Advanced Options
- [ ] Add advanced options UI (collapsible)
- [ ] Implement reference group selection
- [ ] Add optional filters (holidays, weather)

### Phase 8: Testing & Polish
- [ ] Test all selection modes (polygon, route, node)
- [ ] Verify calculations with known data
- [ ] Test edge cases and error handling
- [ ] Cross-browser compatibility check
- [ ] Performance testing with large datasets

---

## File Changes Summary

**index.html** (single file to modify):
1. **HTML** (~150 lines): Tab structure, forms, results display
2. **CSS** (~100 lines): Styling for new components
3. **JavaScript** (~400 lines): State management, analysis functions, UI handlers

**Estimated Total**: ~650 lines of code additions

---

## Dependencies (Already Available)
- Chart.js - For visualization charts
- Leaflet - For map integration (polygon selection)
- jsPDF - For PDF report export
- PapaParse - For CSV export

No new external dependencies required.

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Insufficient crash data | Warn user, suggest longer period |
| Unbalanced periods | Show warning, allow proceed |
| Statistical insignificance | Explain limitations clearly |
| Complex EB calculations | Provide clear methodology documentation |
| Performance with large datasets | Use efficient filtering, lazy loading |

---

## Success Criteria

1. ✅ User can select polygon from map for study location
2. ✅ Study periods auto-calculate based on treatment date
3. ✅ Run Analysis produces accurate statistics
4. ✅ Results show clear before/after comparison
5. ✅ CMF/CRF calculations match industry standards
6. ✅ Statistical significance properly determined
7. ✅ Report exports to professional PDF format
8. ✅ No breaking changes to existing functionality
