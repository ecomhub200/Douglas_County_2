# Claude Code Prompt: Crash Lens Signal Warrant Analyzer

## Project Overview

You are working on the **Crash Lens Signal Warrant Analyzer**, a single-file HTML application that automates MUTCD traffic signal warrant evaluation. This tool is used by traffic engineers to determine if an intersection qualifies for a traffic signal based on volume data.

## Key Files

- `CrashLens_SignalWarrantAnalyzer.html` - The main application (single-file, self-contained)
- `CrashLens_SignalWarrant_Implementation_Plan.md` - Technical specification and algorithm documentation

## Technical Stack

- **Frontend**: Vanilla HTML/CSS/JavaScript (no framework)
- **Libraries** (loaded via CDN):
  - `docx.js` (v8.2.2) - Word document generation
  - `xlsx.js` (v0.18.5) - Excel file parsing
  - Google Fonts: IBM Plex Sans, IBM Plex Mono
- **AI Integration**: Claude API (Anthropic) or OpenAI GPT-4 for data extraction

## MUTCD 11th Edition Compliance

This tool implements signal warrants per the **Manual on Uniform Traffic Control Devices (MUTCD) 11th Edition (December 2023)**. Key sections:

| Warrant | MUTCD Reference | Implementation |
|---------|-----------------|----------------|
| Warrant 1 | Table 4C-1 | Eight-Hour Vehicular Volume |
| Warrant 2 | Figures 4C-1, 4C-2 | Four-Hour Vehicular Volume |
| Warrant 3 | Figures 4C-3, 4C-4 | Peak Hour Volume |

### Critical MUTCD Rules

1. **70% Factor** applies when:
   - Posted/statutory speed limit OR 85th percentile speed > 40 mph on major street
   - OR intersection is in isolated community with population < 10,000

2. **Warrant Satisfaction**:
   - Warrant 1: 8 hours meeting thresholds (Condition A OR Condition B OR Combination)
   - Warrant 2: 4 hours plotting above the curve
   - Warrant 3: Peak hour plotting above the curve

3. **MUTCD 11th Edition Key Change**: Warrants are now "SHOULD" not "SHALL" - engineering judgment required

## Data Structures

### Configuration Object
```javascript
const config = {
  intersectionName: string,
  majorStreet: string,
  minorStreet: string,
  majorLanes: 1 | 2,        // Per approach
  minorLanes: 1 | 2,        // Per approach
  laneConfig: '1x1' | '2x1' | '2x2' | '1x2',
  speedLimit: number,        // mph
  communityPop: number,
  apply70Percent: boolean,
  intersectionLegs: 3 | 4,
  countDuration: '12hr' | '24hr',
  majorDirection: 'EW' | 'NS',
  rtMethod: 'fixed' | 'pagones' | 'none',
  fixedRTPercent: number,    // 0-100
  pagonesConfig: 'sharedLane' | 'exclusiveRTLane' | 'channelizedRT'
};
```

### Extracted Data Structure (from AI)
```javascript
const extractedData = {
  intersection: string,
  date: 'YYYY-MM-DD',
  vendor: string,
  sourceFile: string,
  dataQuality: {
    hoursExtracted: number,
    missingHours: number[],
    warnings: string[]
  },
  peakHour: {
    hour: number,           // 0-23
    totalEntering: number,
    phf: number | null
  },
  hourlyVolumes: {
    [hour: string]: {
      NB: { left: number, thru: number, right: number, total: number },
      SB: { left: number, thru: number, right: number, total: number },
      EB: { left: number, thru: number, right: number, total: number },
      WB: { left: number, thru: number, right: number, total: number }
    }
  },
  computed: {
    majorApproaches: ['EB', 'WB'] | ['NB', 'SB'],
    minorApproaches: ['NB', 'SB'] | ['EB', 'WB'],
    hourlyAggregates: {
      [hour: number]: {
        majorTotal: number,
        minorHighApproach: string,
        minorHighVolume: number,
        minorRightTurn: number,
        rtReduction: number,
        minorAdjusted: number
      }
    }
  }
};
```

### Analysis Results Structure
```javascript
const analysisResults = {
  config: ConfigObject,
  days: number,
  overallWarranted: boolean,
  warrantsFound: string[],
  warrant1: {
    anyDayMet: boolean,
    dayResults: [{
      date: string,
      warranted: boolean,
      conditionAMet: boolean,
      conditionAHours: number,
      conditionBMet: boolean,
      conditionBHours: number,
      combinationMet: boolean,
      combinationAHours: number,
      combinationBHours: number,
      thresholds: object,
      details: object
    }]
  },
  warrant2: {
    anyDayMet: boolean,
    dayResults: [{
      date: string,
      warranted: boolean,
      hoursMet: number,
      hoursRequired: 4,
      factorApplied: '70%' | '100%',
      details: array
    }]
  },
  warrant3: {
    anyDayMet: boolean,
    dayResults: [{
      date: string,
      warranted: boolean,
      peakHour: number,
      peakHourFormatted: string,
      majorVolume: number,
      minorVolume: number,
      threshold: number,
      factorApplied: '70%' | '100%'
    }]
  }
};
```

## Threshold Constants

### Warrant 1 Thresholds (Table 4C-1)
```javascript
WARRANT1_THRESHOLDS.conditionA[laneConfig][percentKey]
WARRANT1_THRESHOLDS.conditionB[laneConfig][percentKey]
// percentKey: 'p100', 'p80', 'p70', 'p56'
// laneConfig: '1x1', '2x1', '2x2', '1x2'
```

### Warrant 2 & 3 Curves
```javascript
WARRANT2_CURVES[curveSet][laneConfig]  // Array of {major, minor} points
WARRANT3_CURVES[curveSet][laneConfig]  // Array of {major, minor} points
// curveSet: 'standard' (100%) or 'reduced' (70%)
```

## Key Functions

### Data Processing
- `computeDayAggregates(day, config)` - Calculate major/minor totals and RT reduction
- `getAnalysisHours(countDuration)` - Return array of hours to analyze (6-17 or 0-23)
- `interpolateThreshold(curve, majorVolume)` - Linear interpolation on warrant curves

### Warrant Evaluation
- `evaluateWarrant1(day, config)` - Returns warrant 1 result object
- `evaluateWarrant2(day, config)` - Returns warrant 2 result object
- `evaluateWarrant3(day, config)` - Returns warrant 3 result object
- `runWarrantAnalysis()` - Main analysis orchestrator

### AI Extraction
- `extractWithAI(fileContent, fileName, apiKey, provider)` - Send to Claude/GPT-4
- `readFileAsText(file)` - Read Excel/CSV files using XLSX library

### Output Generation
- `generateMemo()` - Create Word document using docx.js
- `exportCSV()` - Export hourly data as CSV

## Right-Turn Reduction Methods

### Fixed Percentage
```javascript
rtReduction = rightTurnVolume * (fixedPercent / 100)
adjustedMinor = minorVolume - rtReduction
```

### Pagones Theorem
```javascript
fMinor = PAGONES_FACTORS.minorStreet[config]  // 0.30, 0.75, or 1.00
fMain = lookup(majorVolume / majorLanes)       // 0.00 to 0.70
reductionFactor = max(0, fMinor - fMain)
rtReduction = rightTurnVolume * reductionFactor
```

## Common Modifications

### Adding a New Warrant
1. Add threshold constants at top of `<script>`
2. Create `evaluateWarrantN(day, config)` function
3. Add to `runWarrantAnalysis()` results object
4. Update `renderResults()` and create `renderWarrantNTab()`
5. Add warrant card in HTML and tab button

### Changing Thresholds
- Update the `WARRANT1_THRESHOLDS`, `WARRANT2_CURVES`, or `WARRANT3_CURVES` constants
- Thresholds come directly from MUTCD figures/tables

### Adding Vendor Support
- Modify the AI system prompt in `extractWithAI()` to describe the new format
- The AI handles format detection and extraction

### Styling Changes
- All CSS is in the `<style>` tag at top of file
- Uses CSS custom properties (`:root` variables) for theming
- Primary color: `--primary: #1e3a5f`
- Accent color: `--accent: #e67e22`

## Testing Checklist

When modifying the tool, verify:

- [ ] Warrant 1 evaluates all three paths (A, B, Combination)
- [ ] 70% factor correctly modifies thresholds
- [ ] RT reduction applies only to minor street high approach
- [ ] Peak hour correctly identified for Warrant 3
- [ ] Curve interpolation works for edge cases (below min, above max)
- [ ] Word memo generates with correct values
- [ ] CSV export includes all hourly data
- [ ] UI updates correctly after analysis

## Error Handling

- API errors display in `#api-status` div
- File extraction errors set `file.status = 'error'`
- Missing data handled with `|| 0` fallbacks
- Infinity returned from interpolation when major volume below curve minimum

## Performance Notes

- Excel files parsed client-side with XLSX.js
- Large files (>50KB content) truncated before AI call
- Single-threaded processing (files processed sequentially)
- No local storage used (state resets on page reload)

## API Integration

### Claude (Anthropic)
```javascript
fetch('https://api.anthropic.com/v1/messages', {
  headers: {
    'x-api-key': apiKey,
    'anthropic-version': '2023-06-01'
  },
  body: JSON.stringify({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 8000,
    system: systemPrompt,
    messages: [{ role: 'user', content: prompt }]
  })
})
```

### OpenAI
```javascript
fetch('https://api.openai.com/v1/chat/completions', {
  headers: {
    'Authorization': `Bearer ${apiKey}`
  },
  body: JSON.stringify({
    model: 'gpt-4',
    max_tokens: 8000,
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: prompt }
    ]
  })
})
```

## Future Enhancements (TODO)

1. **Warrant 7 Integration** - Connect to Crash Lens crash data for angle + pedestrian crash analysis
2. **Batch Processing** - Analyze multiple intersections in one session
3. **Gap Analysis Charts** - Visual representation of threshold gaps
4. **Sensitivity Analysis** - Project results with volume growth scenarios
5. **Local Storage** - Save/load analysis sessions
6. **PDF Export** - Alternative to Word memo

## Contact & References

- **MUTCD 11th Edition**: https://mutcd.fhwa.dot.gov/kno_11th_Edition.htm
- **Part 4 (Signals)**: https://mutcd.fhwa.dot.gov/pdfs/11th_Edition/part4.pdf
- **Pagones Theorem**: VDOT IIM-TE-387.1, Page 6

---

When asked to modify this tool, always:
1. Preserve MUTCD compliance
2. Maintain the single-file architecture
3. Test warrant calculations against known values
4. Update both the HTML and this documentation
