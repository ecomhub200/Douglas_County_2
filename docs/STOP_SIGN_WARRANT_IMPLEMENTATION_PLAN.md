# Stop Sign Warrant Analysis Implementation Plan

## MUTCD 2009 Section 2B.07 (Virginia 2011 Supplement)

**Created:** December 28, 2025
**Standard:** MUTCD 2009 Section 2B.07 - Multi-Way Stop Applications
**Virginia Adoption:** 2011 Virginia Supplement (Revision 1, September 2013)

---

## 1. Executive Summary

This plan outlines the implementation of a comprehensive Stop Sign (Multi-Way Stop) Warrant Analysis feature for the Crash Lens tool. The implementation follows the MUTCD 2009 Section 2B.07 criteria as adopted by Virginia's 2011 Supplement, mirroring the architecture of the existing Signal Warrant Analyzer.

### Key Features
- **Crash-based warrant evaluation** (Criterion B) with auto-population from location crash data
- **8-hour volume analysis** (Criteria C.1, C.2, C.3) with traffic count table
- **AI-powered data extraction** for traffic count documents
- **Professional reports** (PDF, Word memo, CSV export)
- **Seamless integration** with existing location selection system

---

## 2. MUTCD 2009 Section 2B.07 Warrant Criteria

### 2.1 Warrant Structure

| Criterion | Description | Threshold |
|-----------|-------------|-----------|
| **A** | Interim measure pending signal installation | Signal warrant met, awaiting installation |
| **B** | Crash problem | **5+ crashes in 12 months** susceptible to correction |
| **C.1** | Major street volume | **≥300 vph** for any 8 hours of average day |
| **C.2** | Minor street volume | **≥200 vph** for same 8 hours |
| **C.3** | Minor street delay | **≥30 seconds** average delay during highest hour |
| **D** | Combined 80% rule | B + C.1 + C.2 all met at 80% of thresholds |

### 2.2 High-Speed Reduction (70%)

When 85th-percentile approach speed on major street exceeds **40 mph**:
- C.1 threshold: 300 × 0.70 = **210 vph**
- C.2 threshold: 200 × 0.70 = **140 vph**

### 2.3 Warrant Determination Logic

```
MULTI-WAY STOP WARRANTED if ANY of the following:
  1. Criterion A is met (interim measure)
  2. Criterion B is met (5+ susceptible crashes)
  3. Criteria C.1 AND C.2 AND C.3 are ALL met (volume + delay)
  4. Criterion D is met (80% combined rule)
```

### 2.4 Susceptible Crash Types

Per MUTCD 2B.07, crashes "susceptible to correction by multi-way stop":
- **Right-angle collisions** (ANGLE, RIGHT ANGLE)
- **Left-turn collisions** (LEFT TURN)
- **Right-turn collisions** (RIGHT TURN)

---

## 3. Data Architecture

### 3.1 State Object Extension

Add to `warrantsState.stopsign`:

```javascript
warrantsState.stopsign = {
    // MUTCD Reference
    mutcdSection: '2B.07',
    mutcdYear: 2009,
    vaSupplementYear: 2011,

    // Intersection Configuration
    config: {
        intersectionName: '',
        majorStreet: '',
        minorStreet: '',
        intersectionLegs: 4,        // 3 or 4
        majorSpeedLimit: 35,        // Posted speed (mph)
        majorSpeed85th: null,       // 85th percentile speed (mph)
        existingControl: 'two-way-stop',  // 'none', 'two-way-stop', 'yield'
        areaType: 'urban'           // 'urban', 'suburban', 'rural'
    },

    // Criterion A: Interim Measure
    criterionA: {
        signalWarrantMet: false,
        signalPending: false,
        notes: ''
    },

    // Criterion B: Crash Problem (Auto-populated)
    criterionB: {
        susceptibleCrashes: 0,      // Total susceptible crashes
        threshold: 5,               // MUTCD threshold
        period: '12month',
        autoPopulated: true,
        crashBreakdown: {
            rightAngle: 0,
            leftTurn: 0,
            rightTurn: 0
        },
        sourceData: null            // Reference to crash records
    },

    // Criterion C: Volume Analysis
    criterionC: {
        apply70pct: false,          // True if speed > 40 mph
        majorThreshold: 300,        // Adjusted if 70% applied
        minorThreshold: 200,        // Adjusted if 70% applied
        delayThreshold: 30,         // Seconds
        hoursMeetingC1: 0,          // Count of hours meeting major threshold
        hoursMeetingC2: 0,          // Count of hours meeting minor threshold
        avgDelayHighestHour: null,  // Measured delay (seconds)
        delayStudyDate: null
    },

    // Criterion D: Combined 80% Rule
    criterionD: {
        b80pct: false,              // 4+ crashes (80% of 5)
        c1_80pct: false,            // 240+ vph major (80% of 300)
        c2_80pct: false             // 160+ vph minor (80% of 200)
    },

    // Traffic Count Data (8-hour analysis)
    multiDayData: {},               // Same structure as signal warrant
    averagingMethod: 'tue-wed-thu', // 'tue-wed-thu', 'any-single-day', 'custom'

    // AI Extraction State
    uploadedFiles: {},
    extractionStatus: 'idle',       // 'idle', 'extracting', 'reviewing', 'complete'
    pendingExtractions: [],
    reviewQueue: [],
    isReviewMode: false,

    // Analysis Results
    analysisResults: null,
    lastAnalysisTimestamp: null,

    // UI State
    currentTab: 'config'            // 'config', 'counts', 'analysis', 'results'
};
```

### 3.2 Data Flow Diagram

```
Location Selection (Map/Dropdown/Search)
         │
         ▼
warrantsState.selectedLocation
         │
         ├──► loadLocationDataForWarrants()
         │           │
         │           ▼
         │    warrantsState.locationCrashes
         │           │
         │           ▼
         │    filterWarrantCrashesByDate() [12-month filter]
         │           │
         │           ▼
         │    warrantsState.filteredCrashes
         │           │
         │           ▼
         │    stopsign_buildCrashProfile()
         │           │
         │           ├──► criterionB.susceptibleCrashes
         │           │         (rightAngle + leftTurn + rightTurn)
         │           │
         │           └──► criterionD.b80pct evaluation
         │
         └──► Auto-populate form fields
                  │
                  ▼
         stopsign_autoPopulateCriterionB()
```

### 3.3 Traffic Count Data Structure

```javascript
// Hourly volume data for 8-hour analysis
stopsign.multiDayData = {
    'day1': {
        date: '2025-03-15',
        dayOfWeek: 2,  // Tuesday
        countType: 'manual',
        hourlyData: {
            6:  { majorVol: 285, minorVol: 165, pedBike: 8 },
            7:  { majorVol: 420, minorVol: 225, pedBike: 15 },
            8:  { majorVol: 385, minorVol: 195, pedBike: 12 },
            // ... hours 9-17
            17: { majorVol: 395, minorVol: 210, pedBike: 18 }
        },
        delayStudy: {
            peakHour: 17,
            avgDelay: 35  // seconds
        }
    },
    'day2': { ... },
    'day3': { ... }
};
```

---

## 4. UI Components

### 4.1 Tab Structure

Replace existing basic stop sign form with tabbed interface:

```
┌────────────────────────────────────────────────────────────┐
│ 🛑 Stop Sign Warrant Study (MUTCD 2B.07)     [View MUTCD]  │
├──────────┬──────────┬──────────┬──────────┬────────────────┤
│  Config  │  Traffic │ Criteria │ Results  │                │
│          │  Counts  │          │          │                │
└──────────┴──────────┴──────────┴──────────┴────────────────┘
```

### 4.2 Tab 1: Configuration

```html
<!-- Intersection Configuration -->
- Intersection Name (auto-filled from selection)
- Major Street Name
- Minor Street Name
- Intersection Type: [3-leg] [4-leg]
- Existing Control: [None] [Two-way Stop] [Yield]
- Major Street Speed Limit (mph)
- 85th Percentile Speed (mph) [optional - enables 70% reduction]
- Area Type: [Urban] [Suburban] [Rural]
```

### 4.3 Tab 2: Traffic Counts

```html
<!-- AI Data Extraction Panel (Collapsible) -->
<div class="ai-panel-collapsible">
    - File upload zone (PDF, Excel, images)
    - AI extraction status
    - QA/QC validation results
    - Review mode for extracted data
</div>

<!-- Volume Entry Table -->
<table>
    <tr>
        <th>Hour</th>
        <th>Major St. Vol</th>
        <th>Minor St. Vol</th>
        <th>Ped/Bike</th>
        <th>≥300?</th>
        <th>≥200?</th>
    </tr>
    <!-- Hours 6 AM - 6 PM (12 rows) -->
</table>

<!-- Delay Study Section -->
- Peak Hour Delay Study Date
- Average Delay (seconds)
- Methodology: [Manual observation] [HCS analysis] [Synchro]

<!-- Multi-Day Data Cards -->
- Day cards showing summary of each counted day
- Averaging method selector
```

### 4.4 Tab 3: Criteria Evaluation

```html
<!-- Criterion A: Interim Measure -->
<div class="criterion-section">
    <h4>Criterion A: Interim Measure</h4>
    <label><input type="checkbox"> Signal warrant is met</label>
    <label><input type="checkbox"> Signal installation is pending</label>
    <div class="result-indicator">[MET/NOT MET]</div>
</div>

<!-- Criterion B: Crash Problem (Auto-populated) -->
<div class="criterion-section highlight">
    <h4>Criterion B: Crash Problem</h4>
    <div class="info-box">Auto-populated from crash data</div>

    <table class="crash-breakdown">
        <tr><td>Right-angle crashes:</td><td>[X]</td></tr>
        <tr><td>Left-turn crashes:</td><td>[X]</td></tr>
        <tr><td>Right-turn crashes:</td><td>[X]</td></tr>
        <tr><th>Total Susceptible:</th><th>[X]</th></tr>
    </table>

    <div>Threshold: 5 crashes in 12 months</div>
    <div class="result-indicator">[MET/NOT MET] - [X] of 5</div>
</div>

<!-- Criterion C: Volume -->
<div class="criterion-section">
    <h4>Criterion C: Volume Analysis</h4>

    <div class="sub-criterion">
        <strong>C.1 Major Street:</strong>
        Hours meeting ≥[300/210] vph: [X] of 8 required
        <div class="result-indicator">[MET/NOT MET]</div>
    </div>

    <div class="sub-criterion">
        <strong>C.2 Minor Street:</strong>
        Hours meeting ≥[200/140] vph: [X] of 8 required
        <div class="result-indicator">[MET/NOT MET]</div>
    </div>

    <div class="sub-criterion">
        <strong>C.3 Minor Street Delay:</strong>
        Average delay: [X] seconds (≥30 required)
        <div class="result-indicator">[MET/NOT MET]</div>
    </div>
</div>

<!-- Criterion D: Combined 80% -->
<div class="criterion-section">
    <h4>Criterion D: Combined 80% Rule</h4>
    <div>Requires B + C.1 + C.2 all at 80%:</div>
    <ul>
        <li>Crashes: [X] ≥ 4 (80% of 5) [✓/✗]</li>
        <li>Major volume: [X] ≥ 240 vph (80% of 300) [✓/✗]</li>
        <li>Minor volume: [X] ≥ 160 vph (80% of 200) [✓/✗]</li>
    </ul>
    <div class="result-indicator">[MET/NOT MET]</div>
</div>
```

### 4.5 Tab 4: Results

```html
<!-- Overall Result Banner -->
<div class="warrant-result-banner [pass/fail]">
    <h3>[✓ MULTI-WAY STOP IS WARRANTED / ⚠ NOT WARRANTED]</h3>
    <p>Based on MUTCD 2009 Section 2B.07 (Virginia 2011 Supplement)</p>
</div>

<!-- Summary Table -->
<table class="results-summary">
    <tr><th>Criterion</th><th>Threshold</th><th>Actual</th><th>Result</th></tr>
    <tr><td>A: Interim</td><td>Signal pending</td><td>[Yes/No]</td><td>[MET/NOT MET]</td></tr>
    <tr><td>B: Crashes</td><td>≥5 in 12 mo</td><td>[X]</td><td>[MET/NOT MET]</td></tr>
    <tr><td>C.1: Major Vol</td><td>≥300 vph × 8 hrs</td><td>[X] hrs</td><td>[MET/NOT MET]</td></tr>
    <tr><td>C.2: Minor Vol</td><td>≥200 vph × 8 hrs</td><td>[X] hrs</td><td>[MET/NOT MET]</td></tr>
    <tr><td>C.3: Delay</td><td>≥30 sec</td><td>[X] sec</td><td>[MET/NOT MET]</td></tr>
    <tr><td>D: Combined 80%</td><td>B+C.1+C.2 @ 80%</td><td>[details]</td><td>[MET/NOT MET]</td></tr>
</table>

<!-- Export Buttons -->
<div class="export-buttons">
    <button onclick="stopsign_generatePDFReport()">📄 Export PDF Report</button>
    <button onclick="stopsign_generateWordMemo()">📝 Export Word Memo</button>
    <button onclick="stopsign_exportCSV()">📊 Export CSV Data</button>
</div>
```

---

## 5. Function Specifications

### 5.1 Core Functions

| Function | Purpose | Location |
|----------|---------|----------|
| `stopsign_initForm()` | Initialize stop sign form and state | Warrants module |
| `stopsign_showTab(tabName)` | Switch between tabs | Warrants module |
| `stopsign_loadLocationData()` | Load crashes for selected location | Warrants module |
| `stopsign_buildCrashProfile(crashes)` | Build crash profile with susceptible breakdown | Warrants module |
| `stopsign_autoPopulateCriterionB()` | Auto-populate crash criterion | Warrants module |
| `stopsign_evaluateAllCriteria()` | Evaluate all criteria and update results | Warrants module |
| `stopsign_evaluateCriterionA()` | Evaluate interim measure criterion | Warrants module |
| `stopsign_evaluateCriterionB()` | Evaluate crash criterion | Warrants module |
| `stopsign_evaluateCriterionC()` | Evaluate volume criteria | Warrants module |
| `stopsign_evaluateCriterionD()` | Evaluate 80% combined criterion | Warrants module |

### 5.2 Traffic Count Functions

| Function | Purpose |
|----------|---------|
| `stopsign_generateCountTable()` | Generate hourly volume input table |
| `stopsign_addDayToAnalysis()` | Add a counted day to multi-day data |
| `stopsign_removeDayFromAnalysis(dayKey)` | Remove a day from analysis |
| `stopsign_calculateAverages()` | Calculate averaged volumes across days |
| `stopsign_countHoursMeetingThreshold()` | Count hours meeting C.1/C.2 thresholds |
| `stopsign_updateVolumeInputs()` | Handle volume input changes |
| `stopsign_apply70pctReduction(apply)` | Toggle 70% threshold reduction |

### 5.3 AI Extraction Functions

| Function | Purpose |
|----------|---------|
| `stopsign_toggleAIPanel()` | Expand/collapse AI panel |
| `stopsign_handleFileUpload(files)` | Handle file upload for AI extraction |
| `stopsign_extractAllWithAI()` | Run AI extraction on uploaded files |
| `stopsign_extractSingleFileWithDualAI(file)` | Extract + validate single file |
| `stopsign_processExtractedData(data)` | Process AI-extracted data |
| `stopsign_enterReviewMode()` | Enter manual review mode |
| `stopsign_confirmReviewedData()` | Confirm reviewed data |

### 5.4 Report Generation Functions

| Function | Purpose |
|----------|---------|
| `stopsign_generatePDFReport()` | Generate PDF report |
| `stopsign_generateWordMemo()` | Generate Word document |
| `stopsign_exportCSV()` | Export traffic count data as CSV |
| `stopsign_buildReportHeader(doc)` | Add report header |
| `stopsign_buildCrashSection(doc)` | Add crash analysis section |
| `stopsign_buildVolumeSection(doc)` | Add volume analysis section |
| `stopsign_buildResultsSection(doc)` | Add results summary |

---

## 6. AI Data Extractor Specification

### 6.1 Extraction Prompt Template

```
MULTI-WAY STOP WARRANT TRAFFIC DATA EXTRACTION
Per MUTCD 2009 Section 2B.07 (Virginia 2011 Supplement)

TASK: Extract traffic volume data from the uploaded document for multi-way stop warrant analysis.

REQUIRED DATA:
1. INTERSECTION IDENTIFICATION
   - Street names (identify major and minor streets)
   - Location/intersection name
   - Count date(s)

2. HOURLY VOLUME DATA (need 8+ hours for warrant analysis)
   For each hour, extract:
   - Major street entering volume (both approaches combined)
   - Minor street entering volume (both approaches combined)
   - Pedestrian counts (if available)
   - Bicycle counts (if available)

3. SPEED DATA (if available)
   - Posted speed limit
   - 85th percentile speed (triggers 70% reduction if > 40 mph)

4. DELAY DATA (if available)
   - Average delay on minor street approaches
   - Peak hour identification

OUTPUT FORMAT:
{
  "confidence": 0.0-1.0,
  "intersectionName": "string",
  "majorStreet": "string",
  "minorStreet": "string",
  "countDate": "YYYY-MM-DD",
  "dayOfWeek": 0-6,
  "speedLimit": number,
  "speed85th": number or null,
  "hourlyData": {
    "6": { "majorVol": number, "minorVol": number, "pedBike": number },
    "7": { ... },
    ...
  },
  "delayData": {
    "peakHour": number,
    "avgDelay": number
  },
  "warnings": ["string"],
  "missingData": ["string"]
}

THRESHOLDS FOR REFERENCE:
- Standard: Major ≥ 300 vph, Minor ≥ 200 vph for 8 hours
- High-speed (>40 mph): Major ≥ 210 vph, Minor ≥ 140 vph
- Delay: ≥ 30 seconds average on minor street
```

### 6.2 QA/QC Validation Rules

```javascript
const STOPSIGN_VALIDATION_RULES = {
    // Minimum data requirements
    minHours: 8,

    // Volume reasonableness checks
    volumeRange: { min: 10, max: 3000 },  // vph

    // Consistency checks
    majorShouldExceedMinor: true,

    // Required fields
    requiredFields: ['majorVol', 'minorVol'],

    // Warning thresholds
    lowConfidenceThreshold: 0.7,

    // Auto-flag conditions
    flagConditions: [
        'majorVol < minorVol for majority of hours',
        'Missing more than 2 consecutive hours',
        'Volumes exceed 2500 vph (unusual)',
        'All volumes identical (likely error)'
    ]
};
```

---

## 7. Report Templates

### 7.1 PDF Report Structure

```
┌─────────────────────────────────────────────────────────────┐
│                    [AGENCY HEADER/LOGO]                      │
│                                                              │
│              MULTI-WAY STOP WARRANT STUDY                   │
│         Per MUTCD 2009 Section 2B.07                        │
│         Virginia Supplement (2011, Revision 1)              │
├─────────────────────────────────────────────────────────────┤
│ Location: [Intersection Name]                                │
│ Evaluation Date: [Date]                                      │
│ Prepared By: [Evaluator]                                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ 1. INTRODUCTION                                              │
│    [Study purpose and methodology]                           │
│                                                              │
│ 2. EXISTING CONDITIONS                                       │
│    • Major Street: [Name] ([Speed] mph)                     │
│    • Minor Street: [Name]                                   │
│    • Intersection Type: [3/4-leg]                           │
│    • Existing Control: [Type]                               │
│                                                              │
│ 3. CRITERION A: INTERIM MEASURE                             │
│    Signal warrant status: [Met/Not Met]                     │
│    Result: [APPLICABLE / NOT APPLICABLE]                    │
│                                                              │
│ 4. CRITERION B: CRASH EXPERIENCE                            │
│    Analysis Period: [Start] to [End] (12 months)            │
│    ┌─────────────────────┬───────────┐                      │
│    │ Crash Type          │ Count     │                      │
│    ├─────────────────────┼───────────┤                      │
│    │ Right-angle         │ [X]       │                      │
│    │ Left-turn           │ [X]       │                      │
│    │ Right-turn          │ [X]       │                      │
│    ├─────────────────────┼───────────┤                      │
│    │ TOTAL SUSCEPTIBLE   │ [X]       │                      │
│    └─────────────────────┴───────────┘                      │
│    Threshold: 5 crashes                                      │
│    Result: [MET / NOT MET]                                   │
│                                                              │
│ 5. CRITERION C: VOLUME ANALYSIS                             │
│    Count Date(s): [Dates]                                    │
│    70% Reduction Applied: [Yes/No]                          │
│                                                              │
│    [Hourly volume table with 8-hour analysis]               │
│                                                              │
│    C.1 Major Street: [X] of 8 hours ≥ [300/210] vph        │
│        Result: [MET / NOT MET]                              │
│                                                              │
│    C.2 Minor Street: [X] of 8 hours ≥ [200/140] vph        │
│        Result: [MET / NOT MET]                              │
│                                                              │
│    C.3 Minor Street Delay: [X] seconds                      │
│        Threshold: 30 seconds                                 │
│        Result: [MET / NOT MET]                              │
│                                                              │
│ 6. CRITERION D: COMBINED 80% RULE                           │
│    Crashes at 80%: [X] ≥ 4 → [Yes/No]                       │
│    Major vol at 80%: [X] ≥ 240 → [Yes/No]                   │
│    Minor vol at 80%: [X] ≥ 160 → [Yes/No]                   │
│    Result: [MET / NOT MET]                                   │
│                                                              │
│ 7. SUMMARY AND RECOMMENDATION                               │
│    ┌─────────────────────────────────────────────────────┐  │
│    │ MULTI-WAY STOP [IS / IS NOT] WARRANTED              │  │
│    │                                                      │  │
│    │ Criteria Met: [List of met criteria]                │  │
│    └─────────────────────────────────────────────────────┘  │
│                                                              │
│    Engineering Recommendation:                               │
│    [Recommendation text]                                     │
│                                                              │
│ ─────────────────────────────────────────────────────────── │
│ Evaluator: ________________  Date: ________________         │
│ Reviewer:  ________________  Date: ________________         │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 CSV Export Format

```csv
# Multi-Way Stop Warrant Study - Traffic Count Data
# Location: [Intersection Name]
# Count Date: [Date]
# MUTCD Section: 2B.07 (Virginia 2011 Supplement)

Hour,Major_Street_Vol,Minor_Street_Vol,Ped_Bike,Major_Threshold,Minor_Threshold,Meets_C1,Meets_C2
6,285,165,8,300,200,No,No
7,420,225,15,300,200,Yes,Yes
8,385,195,12,300,200,Yes,No
9,310,185,6,300,200,Yes,No
10,295,175,4,300,200,No,No
11,320,205,8,300,200,Yes,Yes
12,345,215,12,300,200,Yes,Yes
13,330,195,10,300,200,Yes,No
14,305,180,5,300,200,Yes,No
15,340,210,14,300,200,Yes,Yes
16,425,245,22,300,200,Yes,Yes
17,395,220,18,300,200,Yes,Yes

# Summary
# Hours meeting C.1 (Major ≥ 300): 10
# Hours meeting C.2 (Minor ≥ 200): 6
# Criterion C.1: MET (10 ≥ 8)
# Criterion C.2: NOT MET (6 < 8)
```

---

## 8. Implementation Phases

### Phase 1: Core Infrastructure (Priority: HIGH)

**Estimated Scope:** State object, data flow, crash auto-population

1. **Extend warrantsState.stopsign object**
   - Add all new properties per Section 3.1
   - Initialize default values

2. **Implement crash data connection**
   - `stopsign_loadLocationData()` - Connect to location selection
   - `stopsign_buildCrashProfile()` - Build susceptible crash counts
   - `stopsign_autoPopulateCriterionB()` - Auto-fill crash criterion

3. **Update existing evaluateStopWarrant()**
   - Rename to `stopsign_evaluateAllCriteria()`
   - Implement proper MUTCD 2B.07 logic
   - Update result display

4. **Connect to location selection system**
   - Mirror `loadLocationDataForWarrants()` pattern
   - Apply 12-month date filter automatically

### Phase 2: Volume Analysis (Priority: HIGH)

**Estimated Scope:** Traffic count table, 8-hour analysis

1. **Build traffic count table UI**
   - `stopsign_generateCountTable()` - Create hourly input grid
   - `stopsign_updateVolumeInputs()` - Handle input changes
   - Hour selection (6 AM - 6 PM default)

2. **Implement volume analysis**
   - `stopsign_countHoursMeetingThreshold()` - Count qualifying hours
   - `stopsign_evaluateCriterionC()` - Full criterion C evaluation
   - 70% reduction toggle

3. **Multi-day data support**
   - `stopsign_addDayToAnalysis()` - Add counted days
   - `stopsign_calculateAverages()` - Average across days
   - Day cards UI (mirror signal warrant pattern)

4. **Delay study input**
   - Peak hour delay input
   - Criterion C.3 evaluation

### Phase 3: AI Data Extraction (Priority: MEDIUM)

**Estimated Scope:** AI extraction pipeline, QA/QC

1. **Build AI extraction panel**
   - Collapsible panel UI (mirror signal warrant)
   - File upload zone
   - Status indicators

2. **Implement extraction pipeline**
   - `stopsign_extractAllWithAI()` - Main extraction function
   - `stopsign_extractSingleFileWithDualAI()` - Dual-agent extraction
   - Extraction prompt (Section 6.1)

3. **QA/QC validation**
   - Validation rules (Section 6.2)
   - Confidence scoring
   - Warning display

4. **Review mode**
   - `stopsign_enterReviewMode()` - Review extracted data
   - Editable extracted values
   - `stopsign_confirmReviewedData()` - Confirm and apply

### Phase 4: Reporting (Priority: MEDIUM)

**Estimated Scope:** PDF, Word, CSV exports

1. **PDF report generation**
   - `stopsign_generatePDFReport()` - Main PDF function
   - Report sections (Section 7.1)
   - Professional formatting

2. **Word memo generation**
   - `stopsign_generateWordMemo()` - DOCX export
   - Same content as PDF
   - Editable format

3. **CSV data export**
   - `stopsign_exportCSV()` - Traffic count data
   - Format per Section 7.2
   - Include summary calculations

### Phase 5: UI Polish (Priority: LOW)

**Estimated Scope:** Tabbed interface, help text, validation

1. **Implement tabbed interface**
   - Config / Counts / Criteria / Results tabs
   - Tab navigation function
   - State persistence

2. **Add help text and guidance**
   - MUTCD reference tooltips
   - Input validation messages
   - Warning indicators

3. **Enhanced visualizations**
   - Volume comparison chart
   - Threshold indicator bars
   - Crash breakdown pie chart

---

## 9. Testing Checklist

### 9.1 Data Flow Tests

- [ ] Location selection triggers crash data load
- [ ] 12-month date filter applied correctly
- [ ] Susceptible crash types identified correctly (angle, LT, RT)
- [ ] Crash counts match between form and crashProfile
- [ ] Multi-day averaging calculates correctly

### 9.2 Criterion Evaluation Tests

- [ ] Criterion A: Checkbox logic correct
- [ ] Criterion B: 5+ threshold evaluated correctly
- [ ] Criterion C.1: 8-hour major volume check
- [ ] Criterion C.2: 8-hour minor volume check
- [ ] Criterion C.3: 30-second delay check
- [ ] Criterion D: 80% combined rule
- [ ] 70% reduction applied when speed > 40 mph

### 9.3 Integration Tests

- [ ] Signal warrant Criterion C interaction (if interim measure)
- [ ] Cross-tab navigation from Map maintains selection
- [ ] Export functions produce valid output
- [ ] AI extraction processes typical count documents

### 9.4 Edge Case Tests

- [ ] Zero crashes at location
- [ ] Missing traffic count data
- [ ] 3-leg vs 4-leg intersections
- [ ] High-speed location (>40 mph)
- [ ] Rural vs urban threshold considerations

---

## 10. File Locations

### 10.1 Code Changes

| File | Changes |
|------|---------|
| `app/index.html` | Add stopsign state, UI, functions |
| `config.json` | Add any stop sign specific config |

### 10.2 New Documentation

| File | Purpose |
|------|---------|
| `docs/STOP_SIGN_WARRANT_IMPLEMENTATION_PLAN.md` | This plan |
| `docs/stop-sign-warrant-user-guide.md` | User documentation (Phase 5) |

---

## 11. Dependencies

### 11.1 Existing Dependencies (Already in Project)

- **jsPDF** - PDF generation
- **docx** - Word document generation
- **Claude API** - AI extraction

### 11.2 No New Dependencies Required

The implementation uses existing libraries and patterns from the Signal Warrant Analyzer.

---

## 12. Approval

**Plan Author:** Claude (AI Assistant)
**Plan Date:** December 28, 2025
**MUTCD Reference:** 2009 Edition, Section 2B.07
**Virginia Supplement:** 2011 (Revision 1, September 2013)

---

### Approval Signature

- [ ] **User Approval** - Approve this implementation plan

---

*End of Implementation Plan*
