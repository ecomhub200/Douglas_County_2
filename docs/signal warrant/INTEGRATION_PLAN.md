# Signal Warrant Analyzer Integration Plan

## Overview

This document outlines the plan to integrate the standalone Signal Warrant Analyzer (`data/form/signal warrant analyzer.html`) into the existing Warrants tab, replacing the current simple checkbox-based Signal sub-tab with a full MUTCD 11th Edition signal warrant analysis tool.

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Integration Method | Option A: Replace Signal Sub-Tab | Cleaner, single implementation |
| AI Provider | Existing Claude API (`callCMFAI`) | Reuse proven infrastructure |
| Default MUTCD Version | Virginia MUTCD 11.0 | User requirement |
| PDF/CSV Export | Standalone form's templates | More professional output |
| Word Export | Fix existing or port from standalone | TBD based on complexity |

---

## Collision Type Mapping for Warrant 7

### Source Data (from `virginiaBenchmarks.collision`)
```javascript
const COLLISION_TYPES = {
    "Rear End": 0.289,
    "Angle": 0.187,
    "Single Vehicle": 0.312,
    "Sideswipe - Same Direction": 0.073,
    "Sideswipe - Opposite Direction": 0.025,
    "Head On": 0.024,
    "Pedestrian": 0.039,
    "Bicycle": 0.012,
    "Other": 0.039
};
```

### Warrant 7 Mapping Logic
```javascript
// Angle crashes for Warrant 7 (MUTCD 4C.07)
function isAngleCrash(crash) {
    const type = (crash[COL.COLLISION] || '').toLowerCase();
    return type.includes('angle');  // Matches "Angle"
}

// Pedestrian crashes for Warrant 7
function isPedestrianCrash(crash) {
    const type = (crash[COL.COLLISION] || '').toLowerCase();
    return type.includes('pedestrian') || crash[COL.PED] === 'Y';
}

// Fatal + Injury count (K, A, B per MUTCD)
function isFatalOrInjury(crash) {
    const sev = crash[COL.SEVERITY];
    return ['K', 'A', 'B'].includes(sev);
}
```

### Warrant 7 Thresholds (MUTCD 11th Edition)
```javascript
// From standalone form - WARRANT7_THRESHOLDS
const SIGNAL_WARRANT7_THRESHOLDS = {
    standard_1year: {
        '1x1': { fourLeg: { total: 5, injury: 3 }, threeLeg: { total: 4, injury: 3 } },
        '2x1': { fourLeg: { total: 5, injury: 3 }, threeLeg: { total: 4, injury: 3 } },
        '2x2': { fourLeg: { total: 5, injury: 3 }, threeLeg: { total: 4, injury: 3 } },
        '1x2': { fourLeg: { total: 5, injury: 3 }, threeLeg: { total: 4, injury: 3 } }
    },
    standard_3year: {
        '1x1': { fourLeg: { total: 6, injury: 4 }, threeLeg: { total: 5, injury: 4 } },
        '2x1': { fourLeg: { total: 6, injury: 4 }, threeLeg: { total: 5, injury: 4 } },
        '2x2': { fourLeg: { total: 6, injury: 4 }, threeLeg: { total: 5, injury: 4 } },
        '1x2': { fourLeg: { total: 6, injury: 4 }, threeLeg: { total: 5, injury: 4 } }
    },
    reduced_1year: { /* 70% reduction thresholds */ },
    reduced_3year: { /* 70% reduction thresholds */ }
};
```

---

## State Structure Extension

### Current `warrantsState` (line 7316)
```javascript
const warrantsState = {
    loaded: false,
    currentStudy: 'pedestrian',
    selectedLocation: null,
    locationType: null,
    locationCrashes: [],
    filteredCrashes: [],
    crashProfile: null,
    roadProperties: {},
    attachments: [],
    extractedData: null,
    formData: {
        pedestrian: {},
        stopsign: {},
        signal: {},      // Currently basic
        roundabout: {}
    },
    dateFilter: { /* ... */ },
    requiredPeriods: { /* ... */ }
};
```

### Extended `warrantsState.signal` Structure
```javascript
warrantsState.signal = {
    // Multi-day TMC data
    multiDayData: {},           // { 'day1': { hourlyData: {...}, date: '...', dow: 2 }, ... }
    averagingMethod: 'tue-wed-thu',  // 'tue-wed-thu', 'any-single-day', 'all-weekdays', 'custom'
    includeWeekend: false,

    // Intersection configuration
    config: {
        intersectionName: '',
        majorStreet: '',
        minorStreet: '',
        majorLanes: 2,          // 1 or 2+ (affects thresholds)
        minorLanes: 1,
        majorDirection: 'EW',   // 'EW' or 'NS' (affects TMC grid labels)
        intersectionLegs: 4,    // 3 or 4
        speedLimit: 35,
        communityPop: 50000,
        apply70pct: false,
        countType: '12hr'       // '12hr' or '24hr'
    },

    // Right-turn adjustment
    rtAdjustment: {
        method: 'pagones',      // 'none', 'actual', 'fixed', 'pagones'
        fixedPercent: 30,
        pagonesConfig: 'sharedLane'  // 'sharedLane', 'exclusiveRTLane', 'channelizedRT'
    },

    // Virginia mode
    virginiaMode: true,         // DEFAULT TRUE per user request

    // Optional warrant inputs
    warrant4: {                 // Pedestrian Volume
        enabled: false,
        analysisType: '4hour',
        pedCrossingSpeed: 'normal',
        hourlyPedCounts: [0, 0, 0, 0],
        hourlyMajorVolumes: [0, 0, 0, 0]
    },
    warrant5: {                 // School Crossing
        enabled: false,
        childrenCount: 0,
        crossingMinutes: 60,
        adequateGaps: 0,
        gapStudyDone: false
    },
    warrant7: {                 // Crash Experience - AUTO-POPULATED
        enabled: true,
        period: '1year',
        angleCrashesTotal: 0,
        angleCrashesInjury: 0,
        pedCrashesTotal: 0,
        pedCrashesInjury: 0,
        alternativesTried: false,
        autoPopulated: true,    // Flag to show data source
        sourceData: null        // Reference to crash records
    },

    // AI extraction
    uploadedFiles: {},          // { slot1: { file, status, extractedData }, ... }
    extractionStatus: null,
    pendingExtractions: [],
    reviewQueue: [],
    isReviewMode: false,

    // Analysis results
    analysisResults: null,
    lastAnalysisTimestamp: null
};
```

---

## Function Namespacing Map

### Core Functions (Standalone → Namespaced)

| Standalone Function | Namespaced Version | Purpose |
|--------------------|--------------------|---------|
| `runAnalysis()` | `signal_runAnalysis()` | Main warrant evaluation |
| `evaluateWarrant1()` | `signal_evaluateWarrant1()` | 8-hour warrant |
| `evaluateWarrant2()` | `signal_evaluateWarrant2()` | 4-hour warrant |
| `evaluateWarrant3()` | `signal_evaluateWarrant3()` | Peak hour warrant |
| `evaluateWarrant4()` | `signal_evaluateWarrant4()` | Pedestrian volume |
| `evaluateWarrant5()` | `signal_evaluateWarrant5()` | School crossing |
| `evaluateWarrant7()` | `signal_evaluateWarrant7()` | Crash experience |
| `computeHourlyAggregates()` | `signal_computeHourlyAggregates()` | TMC processing |
| `applyRTAdjustment()` | `signal_applyRTAdjustment()` | Right-turn reduction |

### TMC Grid Functions

| Standalone Function | Namespaced Version |
|--------------------|-------------------|
| `updateTMCGrid()` | `signal_updateTMCGrid()` |
| `populateTMCGridFromExtraction()` | `signal_populateTMCFromExtraction()` |
| `addManualDay()` | `signal_addManualDay()` |
| `clearManualEntry()` | `signal_clearManualEntry()` |
| `renderDayCards()` | `signal_renderDayCards()` |

### AI Extraction Functions

| Standalone Function | Namespaced Version | Notes |
|--------------------|-------------------|-------|
| `extractAllWithDualAI()` | `signal_extractAllWithDualAI()` | Port to use `callCMFAI()` |
| `handleBulkFileUpload()` | `signal_handleBulkFileUpload()` | File handling |
| `confirmExtractedData()` | `signal_confirmExtractedData()` | Review mode |
| `enterReviewMode()` | `signal_enterReviewMode()` | |
| `exitReviewMode()` | `signal_exitReviewMode()` | |

### Export Functions

| Standalone Function | Namespaced Version | Notes |
|--------------------|-------------------|-------|
| `generatePDFReport()` | `signal_generatePDFReport()` | Keep standalone's professional template |
| `exportCSV()` | `signal_exportCSV()` | Keep standalone's format |
| `generateWordMemo()` | `signal_generateWordMemo()` | Port from standalone |

### Helper Functions (Reuse Existing)

| Function | Source | Action |
|----------|--------|--------|
| `showToast()` | Existing (line ~various) | REUSE - don't duplicate |
| `calcEPDO()` | Existing | REUSE |
| `formatRouteName()` | Existing | REUSE |
| `getCMFAIApiKey()` | Existing (line 14205) | REUSE for API key |
| `callCMFAI()` | Existing (line 14201) | REUSE for AI calls |

---

## API Integration

### Current `callCMFAI()` Function (line 14201-14323)
- Supports: Claude, OpenAI, Gemini
- Claude model: `claude-sonnet-4-5-20250929`
- Supports: text, images, PDFs
- Already handles attachments

### Adaptation for TMC Extraction
```javascript
async function signal_extractTMCWithAI(file) {
    // Use existing API infrastructure
    const apiKey = getCMFAIApiKey();
    const headerProvider = document.getElementById('headerAIProvider');
    const provider = headerProvider?.value || 'claude';

    // Build content with file attachment
    const content = buildTMCExtractionContent(file);

    // Use existing callCMFAI with extraction prompt
    const result = await callCMFAI(
        SIGNAL_TMC_EXTRACTION_PROMPT,
        SIGNAL_TMC_SYSTEM_PROMPT,
        [{ name: file.name, type: file.type, data: fileDataUrl, isImage: false }]
    );

    return parseExtractionResult(result);
}
```

### Extraction Prompt (Adapted from Standalone)
```javascript
const SIGNAL_TMC_EXTRACTION_PROMPT = `You are an expert traffic engineer assistant...
// Use the detailed prompt from standalone lines 3802-3950
`;

const SIGNAL_VALIDATION_PROMPT = `You are an expert QA/QC traffic data validator...
// Use the validation prompt from standalone lines 4516-4610
`;
```

---

## Crash Data Integration for Warrant 7

### Auto-Population Function
```javascript
function signal_autoPopulateWarrant7() {
    const crashes = warrantsState.filteredCrashes;
    if (!crashes || crashes.length === 0) {
        // Clear warrant 7 data
        warrantsState.signal.warrant7 = {
            enabled: true,
            period: detectWarrant7Period(),
            angleCrashesTotal: 0,
            angleCrashesInjury: 0,
            pedCrashesTotal: 0,
            pedCrashesInjury: 0,
            alternativesTried: false,
            autoPopulated: true,
            sourceData: null
        };
        return;
    }

    // Filter for angle crashes
    const angleCrashes = crashes.filter(c => {
        const type = (c[COL.COLLISION] || '').toLowerCase();
        return type.includes('angle');
    });

    // Filter for pedestrian crashes
    const pedCrashes = crashes.filter(c => {
        const type = (c[COL.COLLISION] || '').toLowerCase();
        return type.includes('pedestrian') || c[COL.PED] === 'Y';
    });

    // Count injuries (K, A, B per MUTCD)
    const countInjury = (arr) => arr.filter(c =>
        ['K', 'A', 'B'].includes(c[COL.SEVERITY])
    ).length;

    warrantsState.signal.warrant7 = {
        enabled: true,
        period: detectWarrant7Period(),
        angleCrashesTotal: angleCrashes.length,
        angleCrashesInjury: countInjury(angleCrashes),
        pedCrashesTotal: pedCrashes.length,
        pedCrashesInjury: countInjury(pedCrashes),
        alternativesTried: false,
        autoPopulated: true,
        sourceData: { angleCrashes, pedCrashes }
    };

    // Update UI
    signal_updateWarrant7Display();
}

function detectWarrant7Period() {
    const { startDate, endDate } = warrantsState.dateFilter;
    if (!startDate || !endDate) return '1year';

    const months = (new Date(endDate) - new Date(startDate)) / (1000 * 60 * 60 * 24 * 30);
    return months >= 30 ? '3year' : '1year';
}
```

---

## PDF Export Adaptation

### Use Standalone's Professional Template
The standalone form's `generatePDFReport()` (lines 6487-7029) produces a professional multi-page report with:

1. **Page 1: Summary**
   - Intersection info box
   - Warrant summary cards (Pass/Fail)
   - Configuration details

2. **Page 2: Detailed Analysis**
   - Warrant 1, 2, 3 detailed results
   - Threshold comparisons
   - Hours met breakdown

3. **Page 3: Hourly Volume Table**
   - 24-hour volume breakdown
   - Peak hours highlighted
   - Daily totals

4. **Page 4: Individual Day Results**
   - Multi-day comparison table
   - Methodology note

5. **Footer on all pages**
   - Timestamp, page numbers
   - "Generated by CrashLens Signal Warrant Analyzer"

### Adaptation Points
```javascript
function signal_generatePDFReport() {
    // Use existing jsPDF + autoTable (already loaded)
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF('p', 'mm', 'letter');

    // Port the standalone's generatePDFReport() with:
    // 1. Namespace all internal calls (signal_*)
    // 2. Use warrantsState.signal for data source
    // 3. Add crash integration data
    // 4. Keep professional styling/colors

    // Additional section: Crash History (from existing exportWarrantPDF)
    if (warrantsState.signal.warrant7.autoPopulated) {
        signal_addCrashHistoryPage(doc);
    }
}
```

---

## CSV Export Adaptation

### Keep Standalone's Format
The standalone's `exportCSV()` (lines 7032-7108) produces:
- Intersection metadata
- Warrant results summary
- Individual day results (for multi-day)
- Full hourly data with all movements

### Enhancement: Add Crash Data Section
```javascript
function signal_exportCSV() {
    // Port standalone's exportCSV() logic
    let csv = '...';

    // Add crash section if auto-populated
    if (warrantsState.signal.warrant7.autoPopulated) {
        csv += '\nWARRANT 7 CRASH DATA (Auto-populated)\n';
        csv += `Source,CrashLens Database\n`;
        csv += `Period,${warrantsState.signal.warrant7.period}\n`;
        csv += `Angle Crashes (Total),${warrantsState.signal.warrant7.angleCrashesTotal}\n`;
        csv += `Angle Crashes (Injury),${warrantsState.signal.warrant7.angleCrashesInjury}\n`;
        csv += `Pedestrian Crashes (Total),${warrantsState.signal.warrant7.pedCrashesTotal}\n`;
        csv += `Pedestrian Crashes (Injury),${warrantsState.signal.warrant7.pedCrashesInjury}\n`;
    }

    // Download
    downloadCSV(csv, `Signal_Warrant_${intersectionName}.csv`);
}
```

---

## Word Memo Export

### Current Status
The existing `generateWordMemo()` in standalone (not shown in excerpts) or existing warrant export may need work.

### Approach
1. Check if standalone has Word export implementation
2. If yes, port using existing `docx` library
3. If no, create using existing `new Document()` patterns (lines 11176, 11881, 11990)

```javascript
async function signal_generateWordMemo() {
    const { Document, Paragraph, TextRun, Table, TableRow, TableCell, ... } = docx;

    const doc = new Document({
        sections: [{
            properties: {},
            children: [
                // Title
                new Paragraph({
                    children: [new TextRun({ text: 'SIGNAL WARRANT ANALYSIS MEMORANDUM', bold: true, size: 32 })]
                }),

                // To/From/Subject/Date
                signal_buildMemoHeader(),

                // Purpose
                signal_buildPurposeSection(),

                // Analysis Results
                signal_buildResultsSection(),

                // Recommendation
                signal_buildRecommendationSection(),

                // Attachments reference
                signal_buildAttachmentsSection()
            ]
        }]
    });

    const blob = await docx.Packer.toBlob(doc);
    saveAs(blob, `Signal_Warrant_Memo_${intersectionName}.docx`);
}
```

---

## Virginia MUTCD Mode

### Default: TRUE
Per user requirement, Virginia mode should be enabled by default.

### Virginia-Specific Requirements
1. **Section 4C.01 SHALL condition** - Warrant satisfaction is mandatory if criteria met
2. **IIM-TE-387 SJR requirements** - Signal Justification Report required
3. **Roundabout/alternative consideration** - Must document alternatives

### UI Indicator
```html
<div class="virginia-panel">
    <div class="virginia-header">
        <input type="checkbox" id="signal_virginiaMode" checked onchange="signal_toggleVirginiaMode()">
        <label for="signal_virginiaMode">Apply Virginia MUTCD 11.0 Requirements</label>
        <span class="virginia-badge">VA-Specific</span>
    </div>
    <div id="signal_virginiaInfo" class="virginia-info">
        <strong>Virginia Requirements:</strong>
        <ul>
            <li>Section 4C.01: Warrant satisfaction is a <strong>SHALL</strong> condition</li>
            <li>IIM-TE-387: Signal Justification Report (SJR) required</li>
            <li>Roundabout/alternative consideration mandatory</li>
        </ul>
    </div>
</div>
```

---

## HTML Structure Overview

### Location in `index.html`
Replace content of `<div class="card warrant-study-form" id="warrantFormSignal">` (around line 5241+)

### Major Sections
1. **Intersection Configuration** (with AI extraction panel)
2. **TMC Data Entry** (manual grid + day cards)
3. **Right-Turn Adjustment**
4. **Optional Warrants** (4, 5, 7)
5. **Analysis Action Bar**
6. **Results Section** (hidden until analysis run)
7. **Export Section**

### CSS Classes to Add (scoped)
- `.signal-tmc-grid` - TMC table styling
- `.signal-day-card` - Multi-day card styling
- `.signal-result-banner` - Pass/fail banner
- `.signal-warrant-card` - Individual warrant results
- `.signal-quality-metric` - Data quality indicators

---

## Implementation Phases

### Phase 1: State Structure (Day 1)
- [x] Document collision type mapping
- [ ] Extend `warrantsState.signal` with full structure
- [ ] Initialize signal state on load

### Phase 2: Core Functions (Days 2-3)
- [ ] Port warrant evaluation functions (1, 2, 3) with namespace
- [ ] Port TMC computation functions
- [ ] Port threshold tables (MUTCD 11th Edition)

### Phase 3: HTML/UI (Days 4-5)
- [ ] Build intersection configuration section
- [ ] Build TMC grid with merged headers
- [ ] Build day cards section
- [ ] Build results display section

### Phase 4: Crash Integration (Day 6)
- [ ] Implement `signal_autoPopulateWarrant7()`
- [ ] Wire to location selection events
- [ ] Add UI indicators for auto-populated data

### Phase 5: AI Extraction (Days 7-8)
- [ ] Port extraction prompts
- [ ] Adapt to use `callCMFAI()`
- [ ] Implement review mode workflow

### Phase 6: Exports (Day 9)
- [ ] Port PDF report generator
- [ ] Port CSV export
- [ ] Create/port Word memo

### Phase 7: Virginia Mode & Polish (Day 10)
- [ ] Set Virginia mode as default
- [ ] Add Virginia-specific messaging
- [ ] Testing and bug fixes

---

## Files to Modify

| File | Changes |
|------|---------|
| `app/index.html` | Main implementation (~3,500 lines added) |
| (none others) | Single-file architecture maintained |

---

## Testing Checklist

- [ ] Select location → Intersection name auto-fills
- [ ] Change location → Warrant 7 auto-updates
- [ ] Date filter change → Warrant 7 recalculates
- [ ] TMC manual entry → Totals calculate correctly
- [ ] Add multi-day data → Averaging works
- [ ] 70% factor → Thresholds adjust
- [ ] Virginia mode → Extra messaging shows
- [ ] Run analysis → All warrants evaluate
- [ ] PDF export → Professional report generates
- [ ] CSV export → Complete data exports
- [ ] AI extraction → Files process correctly
- [ ] Other warrant tabs → Still functional
- [ ] Map integration → Select from map works

---

## Estimated Lines of Code

| Component | Lines |
|-----------|-------|
| State extension | ~100 |
| Threshold tables | ~150 |
| Core evaluation functions | ~800 |
| TMC grid functions | ~400 |
| AI extraction adaptation | ~300 |
| HTML structure | ~500 |
| CSS styles | ~200 |
| PDF export | ~600 |
| CSV export | ~100 |
| Word memo | ~200 |
| Integration glue | ~150 |
| **Total** | **~3,500** |

---

*Document created: December 2024*
*For: CrashLens Signal Warrant Analyzer Integration*
