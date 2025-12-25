# Crash Lens Signal Warrant Analyzer - Implementation Plan (Revised)

A single-file HTML tool for **Crash Lens** that automates MUTCD signal warrant evaluation using AI-extracted traffic count data. This tool supports multiple vendor formats, offers flexible right-turn reduction options (fixed percentage or Pagones Theorem), and generates Word-formatted decision memos.

---

## Key Design Assumptions

| Assumption | Implementation |
|------------|----------------|
| **Vendor files have various formats** | AI does ALL heavy lifting: extracts, aggregates, and structures data |
| **AI summarizes to hourly L/T/R** | AI processes raw vendor data into standardized hourly volumes by movement |
| **AI calculates peak hour** | AI identifies peak hour from extracted data (or uses vendor-provided if available) |
| **Count duration varies** | Support both 12-hour (6AM-6PM) and 24-hour counts |
| **Right-turn reduction is configurable** | Option 1: Fixed % (default 30%), Option 2: Pagones Theorem |
| **Multi-day analysis** | If ANY single day satisfies a warrant → "Signal Warranted" |
| **General purpose for Crash Lens** | Not agency-specific; user configures location details |

---

## AI Assistant Responsibilities

The AI does **all data processing work**, not the HTML tool:

| Task | AI Responsibility |
|------|-------------------|
| **Format Detection** | Identify vendor type (Quality Counts, Miovision, Rekor, ATD, Jamar, etc.) |
| **Data Extraction** | Parse raw counts from any Excel/PDF layout |
| **Aggregation** | Convert 15-min intervals to hourly totals if needed |
| **Movement Classification** | Identify Left/Thru/Right movements by direction (NB, SB, EB, WB) |
| **Approach Totals** | Calculate total volume per approach per hour |
| **Peak Hour Calculation** | Find highest volume hour and calculate PHF |
| **Data Validation** | Flag missing data, outliers, or extraction errors |
| **Structured Output** | Return clean JSON for warrant analysis |

---

## Data Structure for AI-Processed Traffic Data

The AI returns this structured data after processing raw vendor files:

```javascript
const TrafficDataSchema = {
  // Site information (user-configured in UI)
  site: {
    intersectionName: '',           // "Broad St & Staples Mill Rd"
    majorStreet: '',                // "Broad St"
    minorStreet: '',                // "Staples Mill Rd"
    majorStreetLanes: 2,            // 1 or 2+
    minorStreetLanes: 1,            // 1 or 2+
    speedLimit: 35,                 // Posted speed (mph)
    apply70Percent: false           // Auto-set if speed > 40 mph
  },
  
  // Right-turn reduction configuration (user-configured in UI)
  rtReduction: {
    method: 'fixed',                // 'fixed' or 'pagones'
    fixedPercent: 30,               // Default 30% for fixed method
    pagonesConfig: {                // Only used if method = 'pagones'
      minorStreetConfig: 'sharedLane', // 'sharedLane', 'exclusiveRTLane', 'channelizedRT'
    }
  },
  
  // Count configuration (user-configured in UI)
  countConfig: {
    duration: '12hr',               // '12hr' (6AM-6PM) or '24hr'
    startHour: 6,                   // For 12hr: typically 6
    endHour: 18                     // For 12hr: typically 18 (6PM)
  },
  
  // Uploaded count days (1-7 days supported) - POPULATED BY AI
  countDays: [
    {
      // === AI EXTRACTS THESE FROM FILE ===
      date: '2025-10-03',           // ISO date from file
      sourceFile: 'filename.xlsx',
      vendor: 'Quality Counts',     // Auto-detected by AI
      
      dataQuality: {                // AI reports extraction quality
        hoursExtracted: 14,
        missingHours: [],
        warnings: []
      },
      
      // AI calculates peak hour from extracted data
      peakHour: {
        hour: 17,
        startTime: '17:00',
        endTime: '18:00',
        totalEntering: 1469,
        phf: 0.89
      },
      
      // AI extracts/aggregates hourly volumes by movement
      // Key = hour (0-23), organized by approach and movement
      hourlyVolumes: {
        6: {  // 6:00 AM - 7:00 AM
          NB: { left: 45, thru: 320, right: 67, uTurn: 0, total: 432 },
          SB: { left: 52, thru: 285, right: 43, uTurn: 0, total: 380 },
          EB: { left: 89, thru: 12, right: 34, uTurn: 0, total: 135 },
          WB: { left: 76, thru: 8, right: 41, uTurn: 0, total: 125 }
        },
        7: { /* AI extracts all hours */ },
        // ... continues for all hours with data
      },
      
      // === TOOL CALCULATES THESE AFTER AI EXTRACTION ===
      computed: {
        majorStreetApproaches: ['EB', 'WB'],  // User defines which is major
        minorStreetApproaches: ['NB', 'SB'],
        
        hourlyAggregates: {
          6: {
            majorTotal: 260,              // Sum of both major approaches
            minorHighApproach: 'NB',      // Which minor approach is higher
            minorHighVolume: 432,         // Volume of higher minor approach
            minorRightTurn: 67,           // RT volume from high approach
            minorAdjusted: 412,           // After RT reduction applied
          }
        }
      }
    }
  ]
};
```

---

## Warrant Threshold Tables (MUTCD 11th Edition - December 2023)

**Key Change:** The 11th Edition changed warrant language from "SHALL" to "SHOULD", emphasizing that satisfying a warrant does not automatically require signal installation - engineering judgment is paramount.

```javascript
// MUTCD 11th Edition Table 4C-1: Warrant 1, Eight-Hour Vehicular Volume
// Now explicitly includes all four column types: 100%, 80%, 70%, 56%
const WARRANT_THRESHOLDS = {
  warrant1: {
    conditionA: {
      '1x1': { p100: { major: 500, minor: 150 }, p80: { major: 400, minor: 120 }, p70: { major: 350, minor: 105 }, p56: { major: 280, minor: 84 } },
      '2x1': { p100: { major: 600, minor: 150 }, p80: { major: 480, minor: 120 }, p70: { major: 420, minor: 105 }, p56: { major: 336, minor: 84 } },
      '2x2': { p100: { major: 600, minor: 200 }, p80: { major: 480, minor: 160 }, p70: { major: 420, minor: 140 }, p56: { major: 336, minor: 112 } },
      '1x2': { p100: { major: 500, minor: 200 }, p80: { major: 400, minor: 160 }, p70: { major: 350, minor: 140 }, p56: { major: 280, minor: 112 } }
    },
    conditionB: {
      '1x1': { p100: { major: 750, minor: 75 }, p80: { major: 600, minor: 60 }, p70: { major: 525, minor: 53 }, p56: { major: 420, minor: 42 } },
      '2x1': { p100: { major: 900, minor: 75 }, p80: { major: 720, minor: 60 }, p70: { major: 630, minor: 53 }, p56: { major: 504, minor: 42 } },
      '2x2': { p100: { major: 900, minor: 100 }, p80: { major: 720, minor: 80 }, p70: { major: 630, minor: 70 }, p56: { major: 504, minor: 56 } },
      '1x2': { p100: { major: 750, minor: 100 }, p80: { major: 600, minor: 80 }, p70: { major: 525, minor: 70 }, p56: { major: 420, minor: 56 } }
    }
  }
};

// Select appropriate thresholds based on conditions
function getThresholds(laneConfig, apply70Pct, isCombination) {
  const thresholds = WARRANT_THRESHOLDS.warrant1;
  
  if (isCombination) {
    // Combination uses 80% (standard) or 56% (with 70% factor)
    const key = apply70Pct ? 'p56' : 'p80';
    return {
      conditionA: thresholds.conditionA[laneConfig][key],
      conditionB: thresholds.conditionB[laneConfig][key]
    };
  } else {
    // Standard uses 100% or 70% factor
    const key = apply70Pct ? 'p70' : 'p100';
    return {
      conditionA: thresholds.conditionA[laneConfig][key],
      conditionB: thresholds.conditionB[laneConfig][key]
    };
  }
}

// 70% Factor applies when:
// - Posted/statutory speed limit OR 85th percentile speed > 40 mph on major street
// - OR intersection is in isolated community with population < 10,000
function should70PercentApply(speedLimit, communityPopulation) {
  return speedLimit > 40 || communityPopulation < 10000;
}
```

---

## Right-Turn Reduction Options

### Option 1: Fixed Percentage Reduction (Default)

Simple percentage reduction applied to minor street right-turn volumes. Default is **30%** (common Virginia practice).

```javascript
function applyFixedRTReduction(minorApproachVolume, rightTurnVolume, fixedPercent) {
  // Reduce RT volume by fixed percentage, subtract from total
  const rtReduction = Math.round(rightTurnVolume * (fixedPercent / 100));
  const adjustedVolume = minorApproachVolume - rtReduction;
  
  return {
    originalVolume: minorApproachVolume,
    rightTurnVolume: rightTurnVolume,
    rtReduction: rtReduction,
    adjustedVolume: Math.max(0, adjustedVolume),
    method: 'fixed',
    reductionPercent: fixedPercent
  };
}
```

### Option 2: Pagones Theorem (Variable Reduction)

More sophisticated reduction based on minor street geometry and mainline congestion:

**Formula: R_adj = R × (1 - max(0, f_minor - f_main))**

```javascript
const PAGONES_FACTORS = {
  minorStreet: {
    sharedLane: 0.30,           // Shared through/right lane
    exclusiveRTLane: 0.75,      // Dedicated RT lane
    channelizedRT: 1.00         // Free-flow channelized RT
  },
  mainlineCongestion: [
    { maxVolPerLane: 199, factor: 0.00 },
    { maxVolPerLane: 299, factor: 0.10 },
    { maxVolPerLane: 399, factor: 0.20 },
    { maxVolPerLane: 499, factor: 0.30 },
    { maxVolPerLane: 599, factor: 0.40 },
    { maxVolPerLane: 699, factor: 0.50 },
    { maxVolPerLane: 799, factor: 0.60 },
    { maxVolPerLane: Infinity, factor: 0.70 }
  ]
};

function applyPagonesReduction(minorApproachVolume, rightTurnVolume, 
                                minorConfig, majorVolume, majorLanes) {
  const fMinor = PAGONES_FACTORS.minorStreet[minorConfig];
  const volPerLane = majorVolume / majorLanes;
  
  // Find mainline congestion factor
  const fMain = PAGONES_FACTORS.mainlineCongestion
    .find(r => volPerLane <= r.maxVolPerLane).factor;
  
  // Calculate effective reduction
  const reductionFactor = Math.max(0, fMinor - fMain);
  const rtReduction = Math.round(rightTurnVolume * reductionFactor);
  const adjustedVolume = minorApproachVolume - rtReduction;
  
  return {
    originalVolume: minorApproachVolume,
    rightTurnVolume: rightTurnVolume,
    rtReduction: rtReduction,
    adjustedVolume: Math.max(0, adjustedVolume),
    method: 'pagones',
    fMinor: fMinor,
    fMain: fMain,
    effectiveReduction: Math.round(reductionFactor * 100)
  };
}
```

### Unified Reduction Function

```javascript
function applyRTReduction(trafficData, dayIndex, hour) {
  const day = trafficData.countDays[dayIndex];
  const hourData = day.hourlyVolumes[hour];
  const config = trafficData.rtReduction;
  
  // Get the higher minor street approach
  const minorApproaches = day.computed.minorStreetApproaches;
  const approach1Vol = hourData[minorApproaches[0]]?.total || 0;
  const approach2Vol = hourData[minorApproaches[1]]?.total || 0;
  
  const highApproach = approach1Vol >= approach2Vol ? minorApproaches[0] : minorApproaches[1];
  const highVolume = Math.max(approach1Vol, approach2Vol);
  const rightTurn = hourData[highApproach]?.right || 0;
  
  // Get major street total for Pagones
  const majorApproaches = day.computed.majorStreetApproaches;
  const majorTotal = (hourData[majorApproaches[0]]?.total || 0) + 
                     (hourData[majorApproaches[1]]?.total || 0);
  
  if (config.method === 'fixed') {
    return applyFixedRTReduction(highVolume, rightTurn, config.fixedPercent);
  } else {
    return applyPagonesReduction(
      highVolume, 
      rightTurn, 
      config.pagonesConfig.minorStreetConfig,
      majorTotal,
      trafficData.site.majorStreetLanes
    );
  }
}
```

---

## AI Data Extraction - The AI Does ALL Heavy Lifting

The AI assistant handles **all data processing** from raw vendor files:

```javascript
async function extractTrafficData(fileContent, fileType, apiKey) {
  const systemPrompt = `You are a traffic data analyst. Your job is to extract and process turning movement count (TMC) data from uploaded traffic count files.

## YOUR RESPONSIBILITIES (DO ALL OF THIS):

1. **DETECT VENDOR FORMAT**: Identify the source (Quality Counts, Miovision, Rekor, All Traffic Data, Jamar, etc.)

2. **EXTRACT RAW DATA**: Parse all traffic volumes from the file, regardless of format

3. **AGGREGATE TO HOURLY**: If data is in 15-minute intervals, sum to hourly totals

4. **CLASSIFY MOVEMENTS**: Identify Left, Through, Right, and U-Turn movements for each approach:
   - NB (Northbound), SB (Southbound), EB (Eastbound), WB (Westbound)

5. **CALCULATE APPROACH TOTALS**: Sum L+T+R+U for each approach each hour

6. **FIND PEAK HOUR**: Identify the hour with highest total entering volume and calculate PHF if possible

7. **VALIDATE DATA**: Note any missing hours, suspicious values, or extraction issues

## COMMON VENDOR FORMATS TO HANDLE:

**Quality Counts**: 
- Header rows with intersection name, date, job number
- Row 17-18 area has peak hour volumes by movement (NBLeft, NBThru, NBRight, etc.)
- May have interval data below in 15-min or hourly rows

**Miovision/Scout**:
- Multiple sheets for different vehicle classes
- Column headers like "NB-L", "NB-T", "NB-R" or "NBLeft", "NBThru", "NBRight"
- 15-minute intervals typically

**All Traffic Data (ATD)**:
- Approach-based grouping
- May show totals by approach without movement breakdown

**Jamar/TDC**:
- Approach 1-4 format with R/T/L per approach
- Need to map approaches to directions

**Rekor**:
- Video-based counts
- May have vehicle classification data

## OUTPUT FORMAT (JSON):
{
  "intersection": "Street1 & Street2",
  "date": "YYYY-MM-DD",
  "vendor": "detected vendor name",
  "dataQuality": {
    "hoursExtracted": 14,
    "missingHours": [],
    "warnings": ["any issues noted"]
  },
  
  "peakHour": {
    "hour": 17,
    "startTime": "17:00",
    "endTime": "18:00",
    "totalEntering": 1469,
    "phf": 0.89
  },
  
  "hourlyVolumes": {
    "6": {
      "NB": { "left": 45, "thru": 320, "right": 67, "uTurn": 0, "total": 432 },
      "SB": { "left": 52, "thru": 285, "right": 43, "uTurn": 0, "total": 380 },
      "EB": { "left": 89, "thru": 12, "right": 34, "uTurn": 0, "total": 135 },
      "WB": { "left": 76, "thru": 8, "right": 41, "uTurn": 0, "total": 125 }
    },
    "7": { ... },
    "8": { ... },
    ... ALL hours with data
  }
}

## RULES:
- YOU must do all aggregation - don't assume data is pre-summarized
- Calculate totals yourself: total = left + thru + right + uTurn
- Mark genuinely missing data as null, not zero
- Zero is valid if the count shows zero vehicles
- Find peak hour by summing all approach totals for each hour
- PHF = Peak Hour Volume / (4 × Peak 15-min Volume) if 15-min data available
- Include ALL hours present in the data (6AM-6PM for 12hr, 0-23 for 24hr)`;

  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01'
    },
    body: JSON.stringify({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 8000,
      system: systemPrompt,
      messages: [{ role: 'user', content: `Extract and process TMC data from this ${fileType} file:\n\n${fileContent}` }]
    })
  });
  
  const result = await response.json();
  return JSON.parse(result.content[0].text);
}
```

### Example: Processing Quality Counts File

Given the sample file structure (like 10-03-2025.xlsx):

```
Row 3:  Intersection: N Gayton Rd & Causeway Dr
Row 7:  Date: 2025-10-03
Row 17: [Headers] NBLeft, NBThru, NBRight, SBLeft, SBThru, SBRight, EBLeft...
Row 18: [Values]  48, 423, 23, 82, 452, 168, 132, 1, 53, 22, 4, 61
```

**AI extracts and returns:**
```json
{
  "intersection": "N Gayton Rd & Causeway Dr",
  "date": "2025-10-03",
  "vendor": "Quality Counts",
  "peakHour": {
    "hour": 17,
    "startTime": "17:00",
    "endTime": "18:00",
    "totalEntering": 1469,
    "phf": 0.89
  },
  "hourlyVolumes": {
    "17": {
      "NB": { "left": 48, "thru": 423, "right": 23, "uTurn": 0, "total": 494 },
      "SB": { "left": 82, "thru": 452, "right": 168, "uTurn": 0, "total": 702 },
      "EB": { "left": 132, "thru": 1, "right": 53, "uTurn": 0, "total": 186 },
      "WB": { "left": 22, "thru": 4, "right": 61, "uTurn": 0, "total": 87 }
    }
  }
}
```

---

## Warrant Evaluation Algorithms

### Warrant 1: Eight-Hour Vehicular Volume

```javascript
function evaluateWarrant1(trafficData, dayIndex) {
  const day = trafficData.countDays[dayIndex];
  const site = trafficData.site;
  const laneConfig = `${site.majorStreetLanes}x${site.minorStreetLanes}`;
  
  // Select threshold set
  const thresholdSet = site.apply70Percent ? 'reduced' : 'standard';
  const thresholds = WARRANT_THRESHOLDS.warrant1[thresholdSet];
  const combThresholds = getCombinationThresholds(laneConfig, site.apply70Percent);
  
  // Determine analysis hours based on count duration
  const hours = getAnalysisHours(trafficData.countConfig);
  
  let results = {
    conditionA: { hoursMet: 0, details: [] },
    conditionB: { hoursMet: 0, details: [] },
    combinationA: { hoursMet: 0, details: [] },
    combinationB: { hoursMet: 0, details: [] }
  };
  
  hours.forEach(hour => {
    const agg = day.computed.hourlyAggregates[hour];
    if (!agg) return;
    
    const majorVol = agg.majorTotal;
    const minorVol = agg.minorAdjusted;  // After RT reduction
    
    // Check Condition A
    const meetsA = majorVol >= thresholds.conditionA[laneConfig].major &&
                   minorVol >= thresholds.conditionA[laneConfig].minor;
    if (meetsA) results.conditionA.hoursMet++;
    
    // Check Condition B
    const meetsB = majorVol >= thresholds.conditionB[laneConfig].major &&
                   minorVol >= thresholds.conditionB[laneConfig].minor;
    if (meetsB) results.conditionB.hoursMet++;
    
    // Check Combination (80%/56% thresholds)
    const meetsCombA = majorVol >= combThresholds.conditionA.major &&
                       minorVol >= combThresholds.conditionA.minor;
    const meetsCombB = majorVol >= combThresholds.conditionB.major &&
                       minorVol >= combThresholds.conditionB.minor;
    if (meetsCombA) results.combinationA.hoursMet++;
    if (meetsCombB) results.combinationB.hoursMet++;
    
    results.conditionA.details.push({ hour, majorVol, minorVol, met: meetsA });
    results.conditionB.details.push({ hour, majorVol, minorVol, met: meetsB });
  });
  
  // Warrant 1 satisfied if ANY path meets 8 hours
  const warranted = 
    results.conditionA.hoursMet >= 8 ||
    results.conditionB.hoursMet >= 8 ||
    (results.combinationA.hoursMet >= 8 && results.combinationB.hoursMet >= 8);
  
  return {
    warranted,
    conditionAMet: results.conditionA.hoursMet >= 8,
    conditionBMet: results.conditionB.hoursMet >= 8,
    combinationMet: results.combinationA.hoursMet >= 8 && 
                    results.combinationB.hoursMet >= 8,
    hoursAnalyzed: hours.length,
    results
  };
}

function getAnalysisHours(countConfig) {
  if (countConfig.duration === '12hr') {
    // 6 AM to 6 PM (hours 6-17)
    return Array.from({ length: 12 }, (_, i) => countConfig.startHour + i);
  } else {
    // 24 hours (0-23)
    return Array.from({ length: 24 }, (_, i) => i);
  }
}
```

### Warrant 2: Four-Hour Vehicular Volume (MUTCD 11th Edition Figures 4C-1 and 4C-2)

```javascript
// MUTCD 11th Edition Figure 4C-1: Warrant 2, Four-Hour Vehicular Volume (100%)
// Figure 4C-2: With 70% Factor
// Note: Minor street lower threshold is 80 vph (1 lane) or 115 vph (2+ lanes)
const WARRANT2_CURVES = {
  // 100% thresholds (Figure 4C-1)
  standard: {
    '1x1': [
      { major: 400, minor: 80 },   // Lower threshold for 1-lane minor
      { major: 500, minor: 80 },
      { major: 600, minor: 70 },
      { major: 800, minor: 56 },
      { major: 1000, minor: 47 },
      { major: 1200, minor: 40 }   // Minimum minor = 80 for 1 lane
    ],
    '2x1': [
      { major: 400, minor: 80 },
      { major: 600, minor: 80 },
      { major: 800, minor: 70 },
      { major: 1000, minor: 58 },
      { major: 1200, minor: 50 },
      { major: 1400, minor: 50 }
    ],
    '2x2': [
      { major: 400, minor: 115 },  // Lower threshold for 2-lane minor
      { major: 600, minor: 115 },
      { major: 800, minor: 100 },
      { major: 1000, minor: 83 },
      { major: 1200, minor: 70 },
      { major: 1400, minor: 60 },
      { major: 1600, minor: 50 }
    ],
    '1x2': [
      { major: 400, minor: 115 },
      { major: 500, minor: 115 },
      { major: 600, minor: 100 },
      { major: 800, minor: 80 },
      { major: 1000, minor: 65 },
      { major: 1200, minor: 55 }
    ]
  },
  // 70% Factor thresholds (Figure 4C-2)
  // Lower thresholds: 60 vph (1 lane) or 80 vph (2+ lanes)
  reduced: {
    '1x1': [
      { major: 280, minor: 60 },
      { major: 350, minor: 56 },
      { major: 420, minor: 49 },
      { major: 560, minor: 39 },
      { major: 700, minor: 33 },
      { major: 840, minor: 28 }
    ],
    '2x1': [
      { major: 280, minor: 60 },
      { major: 420, minor: 56 },
      { major: 560, minor: 49 },
      { major: 700, minor: 41 },
      { major: 840, minor: 35 },
      { major: 980, minor: 35 }
    ],
    '2x2': [
      { major: 280, minor: 80 },
      { major: 420, minor: 80 },
      { major: 560, minor: 70 },
      { major: 700, minor: 58 },
      { major: 840, minor: 49 },
      { major: 980, minor: 42 },
      { major: 1120, minor: 35 }
    ],
    '1x2': [
      { major: 280, minor: 80 },
      { major: 350, minor: 80 },
      { major: 420, minor: 70 },
      { major: 560, minor: 56 },
      { major: 700, minor: 46 },
      { major: 840, minor: 39 }
    ]
  }
};

function interpolateThreshold(curve, majorVolume) {
  // Below curve minimum
  if (majorVolume < curve[0].major) return Infinity;
  
  // Above curve maximum - use last point's minor value
  if (majorVolume >= curve[curve.length - 1].major) {
    return curve[curve.length - 1].minor;
  }
  
  // Linear interpolation between points
  for (let i = 0; i < curve.length - 1; i++) {
    if (majorVolume >= curve[i].major && majorVolume < curve[i + 1].major) {
      const ratio = (majorVolume - curve[i].major) / 
                   (curve[i + 1].major - curve[i].major);
      const threshold = curve[i].minor - ratio * (curve[i].minor - curve[i + 1].minor);
      return Math.round(threshold);
    }
  }
  return Infinity;
}

function evaluateWarrant2(trafficData, dayIndex) {
  const day = trafficData.countDays[dayIndex];
  const site = trafficData.site;
  const laneConfig = `${site.majorStreetLanes}x${site.minorStreetLanes}`;
  
  // Select curve based on 70% factor
  const curveSet = site.apply70Percent ? 'reduced' : 'standard';
  const curve = WARRANT2_CURVES[curveSet][laneConfig];
  const hours = getAnalysisHours(trafficData.countConfig);
  
  let hoursMet = 0;
  let details = [];
  
  hours.forEach(hour => {
    const agg = day.computed.hourlyAggregates[hour];
    if (!agg) return;
    
    const threshold = interpolateThreshold(curve, agg.majorTotal);
    const met = agg.minorAdjusted >= threshold;
    if (met) hoursMet++;
    
    details.push({
      hour,
      majorVol: agg.majorTotal,
      minorVol: agg.minorAdjusted,
      threshold,
      met
    });
  });
  
  return {
    warranted: hoursMet >= 4,
    hoursMet,
    hoursRequired: 4,
    details,
    factorApplied: site.apply70Percent ? '70%' : '100%'
  };
}
```

### Warrant 3: Peak Hour (MUTCD 11th Edition Figures 4C-3 and 4C-4)

```javascript
// MUTCD 11th Edition Figure 4C-3: Warrant 3, Peak Hour (100%)
// Figure 4C-4: With 70% Factor
// Note: Minor street lower threshold is 100 vph (1 lane) or 150 vph (2+ lanes)
const WARRANT3_CURVES = {
  // 100% thresholds (Figure 4C-3)
  standard: {
    '1x1': [
      { major: 400, minor: 135 },
      { major: 600, minor: 115 },
      { major: 800, minor: 100 },   // Lower threshold = 100 for 1-lane
      { major: 1000, minor: 100 },
      { major: 1200, minor: 100 },
      { major: 1400, minor: 100 }
    ],
    '2x1': [
      { major: 500, minor: 135 },
      { major: 700, minor: 115 },
      { major: 900, minor: 100 },
      { major: 1100, minor: 100 },
      { major: 1300, minor: 100 },
      { major: 1500, minor: 100 }
    ],
    '2x2': [
      { major: 600, minor: 190 },
      { major: 800, minor: 165 },
      { major: 1000, minor: 150 },  // Lower threshold = 150 for 2-lane
      { major: 1200, minor: 150 },
      { major: 1400, minor: 150 },
      { major: 1600, minor: 150 }
    ],
    '1x2': [
      { major: 500, minor: 175 },
      { major: 700, minor: 150 },
      { major: 900, minor: 150 },
      { major: 1100, minor: 150 },
      { major: 1300, minor: 150 }
    ]
  },
  // 70% Factor thresholds (Figure 4C-4)
  // Lower thresholds: 75 vph (1 lane) or 100 vph (2+ lanes)
  reduced: {
    '1x1': [
      { major: 280, minor: 95 },
      { major: 420, minor: 80 },
      { major: 560, minor: 75 },    // Lower threshold = 75 for 1-lane
      { major: 700, minor: 75 },
      { major: 840, minor: 75 },
      { major: 980, minor: 75 }
    ],
    '2x1': [
      { major: 350, minor: 95 },
      { major: 490, minor: 80 },
      { major: 630, minor: 75 },
      { major: 770, minor: 75 },
      { major: 910, minor: 75 },
      { major: 1050, minor: 75 }
    ],
    '2x2': [
      { major: 420, minor: 133 },
      { major: 560, minor: 115 },
      { major: 700, minor: 100 },   // Lower threshold = 100 for 2-lane
      { major: 840, minor: 100 },
      { major: 980, minor: 100 },
      { major: 1120, minor: 100 }
    ],
    '1x2': [
      { major: 350, minor: 122 },
      { major: 490, minor: 105 },
      { major: 630, minor: 100 },
      { major: 770, minor: 100 },
      { major: 910, minor: 100 }
    ]
  }
};

function evaluateWarrant3(trafficData, dayIndex) {
  const day = trafficData.countDays[dayIndex];
  const site = trafficData.site;
  const laneConfig = `${site.majorStreetLanes}x${site.minorStreetLanes}`;
  
  // Select curve based on 70% factor
  const curveSet = site.apply70Percent ? 'reduced' : 'standard';
  const curve = WARRANT3_CURVES[curveSet][laneConfig];
  
  // Use AI-calculated peak hour
  const peakHour = day.peakHour.hour;
  const agg = day.computed.hourlyAggregates[peakHour];
  
  if (!agg) {
    return { warranted: false, reason: 'Peak hour data not available' };
  }
  
  const peakMajor = agg.majorTotal;
  const peakMinor = agg.minorAdjusted;  // After RT reduction
  
  const threshold = interpolateThreshold(curve, peakMajor);
  const warranted = peakMinor >= threshold;
  
  return {
    warranted,
    peakHour,
    peakHourFormatted: `${String(peakHour).padStart(2, '0')}:00-${String(peakHour + 1).padStart(2, '0')}:00`,
    majorVolume: peakMajor,
    minorVolume: peakMinor,
    threshold,
    phf: day.peakHour.phf || null,
    factorApplied: site.apply70Percent ? '70%' : '100%'
  };
}
```

---

### Warrant 7: Crash Experience (MUTCD 11th Edition - NEW Tables 4C-2 through 4C-5)

**Major Change in 11th Edition:** Warrant 7 now uses specific crash tables based on:
- Angle crashes + Pedestrian crashes only (not all crash types)
- Separate thresholds for "all severities" vs "fatal-and-injury only"
- 1-year OR 3-year analysis periods
- Different tables for standard vs 70% factor locations

```javascript
// MUTCD 11th Edition Tables 4C-2 and 4C-3: Standard Crash Thresholds
// Tables 4C-4 and 4C-5: 70% Factor Crash Thresholds
const WARRANT7_CRASH_THRESHOLDS = {
  // Standard thresholds (Tables 4C-2 and 4C-3)
  standard: {
    oneYear: {
      fourLeg: { allSeverities: 5, fatalInjury: 3 },
      threeLeg: { allSeverities: 4, fatalInjury: 3 }
    },
    threeYear: {
      fourLeg: { allSeverities: 6, fatalInjury: 4 },
      threeLeg: { allSeverities: 5, fatalInjury: 4 }
    }
  },
  // 70% Factor thresholds (Tables 4C-4 and 4C-5)
  // Note: These vary by lane configuration for multi-lane approaches
  reduced: {
    oneYear: {
      '1x1': { fourLeg: { allSeverities: 4, fatalInjury: 3 }, threeLeg: { allSeverities: 3, fatalInjury: 3 } },
      '2x1': { fourLeg: { allSeverities: 10, fatalInjury: 6 }, threeLeg: { allSeverities: 9, fatalInjury: 6 } },
      '2x2': { fourLeg: { allSeverities: 10, fatalInjury: 6 }, threeLeg: { allSeverities: 9, fatalInjury: 6 } },
      '1x2': { fourLeg: { allSeverities: 4, fatalInjury: 3 }, threeLeg: { allSeverities: 3, fatalInjury: 3 } }
    },
    threeYear: {
      '1x1': { fourLeg: { allSeverities: 6, fatalInjury: 4 }, threeLeg: { allSeverities: 5, fatalInjury: 4 } },
      '2x1': { fourLeg: { allSeverities: 16, fatalInjury: 9 }, threeLeg: { allSeverities: 13, fatalInjury: 9 } },
      '2x2': { fourLeg: { allSeverities: 16, fatalInjury: 9 }, threeLeg: { allSeverities: 13, fatalInjury: 9 } },
      '1x2': { fourLeg: { allSeverities: 6, fatalInjury: 4 }, threeLeg: { allSeverities: 5, fatalInjury: 4 } }
    }
  }
};

// Warrant 7 also requires 80% of Warrant 1 volume thresholds (Condition C)
// Uses the 80% columns from Table 4C-1 (or 56% if 70% factor applies)
function evaluateWarrant7(crashData, trafficData) {
  const site = trafficData.site;
  const laneConfig = `${site.majorStreetLanes}x${site.minorStreetLanes}`;
  const legs = crashData.intersectionLegs || 4;  // Default to 4-leg
  const legKey = legs >= 4 ? 'fourLeg' : 'threeLeg';
  
  // Get crash thresholds
  let crashThresholds;
  if (site.apply70Percent) {
    crashThresholds = WARRANT7_CRASH_THRESHOLDS.reduced;
  } else {
    crashThresholds = WARRANT7_CRASH_THRESHOLDS.standard;
  }
  
  // Check crash criteria (Condition B)
  const anglePedCrashes = crashData.angleCrashes + crashData.pedestrianCrashes;
  const anglePedFI = crashData.angleCrashesFI + crashData.pedestrianCrashesFI;
  
  let crashConditionMet = false;
  let crashPeriod = null;
  
  // Check 1-year thresholds
  if (site.apply70Percent) {
    const oneYearThresh = crashThresholds.oneYear[laneConfig][legKey];
    if (anglePedCrashes >= oneYearThresh.allSeverities || anglePedFI >= oneYearThresh.fatalInjury) {
      crashConditionMet = true;
      crashPeriod = '1-year';
    }
  } else {
    const oneYearThresh = crashThresholds.oneYear[legKey];
    if (anglePedCrashes >= oneYearThresh.allSeverities || anglePedFI >= oneYearThresh.fatalInjury) {
      crashConditionMet = true;
      crashPeriod = '1-year';
    }
  }
  
  // Check volume criteria (Condition C) - requires 80% of Warrant 1 for 8 hours
  // This connects to Warrant 1 evaluation with 80%/56% thresholds
  
  return {
    crashConditionMet,
    crashPeriod,
    anglePedCrashes,
    anglePedFI,
    volumeConditionMet: null,  // Evaluated separately with traffic data
    warranted: null  // Requires BOTH crash AND volume conditions
  };
}
```

---

## Multi-Day Analysis Logic

```javascript
function evaluateAllDays(trafficData) {
  const results = {
    overallWarranted: false,
    warrantsFound: [],
    daysAnalyzed: trafficData.countDays.length,
    
    warrant1: { anyDayMet: false, dayResults: [] },
    warrant2: { anyDayMet: false, dayResults: [] },
    warrant3: { anyDayMet: false, dayResults: [] }
  };
  
  // Process each day
  trafficData.countDays.forEach((day, index) => {
    // First compute aggregates with RT reduction
    computeDayAggregates(trafficData, index);
    
    // Evaluate all three warrants
    const w1 = evaluateWarrant1(trafficData, index);
    const w2 = evaluateWarrant2(trafficData, index);
    const w3 = evaluateWarrant3(trafficData, index);
    
    results.warrant1.dayResults.push({ date: day.date, ...w1 });
    results.warrant2.dayResults.push({ date: day.date, ...w2 });
    results.warrant3.dayResults.push({ date: day.date, ...w3 });
    
    if (w1.warranted) results.warrant1.anyDayMet = true;
    if (w2.warranted) results.warrant2.anyDayMet = true;
    if (w3.warranted) results.warrant3.anyDayMet = true;
  });
  
  // ANY warrant met on ANY day = Signal Warranted
  results.overallWarranted = 
    results.warrant1.anyDayMet || 
    results.warrant2.anyDayMet || 
    results.warrant3.anyDayMet;
  
  if (results.warrant1.anyDayMet) results.warrantsFound.push('Warrant 1');
  if (results.warrant2.anyDayMet) results.warrantsFound.push('Warrant 2');
  if (results.warrant3.anyDayMet) results.warrantsFound.push('Warrant 3');
  
  return results;
}

function computeDayAggregates(trafficData, dayIndex) {
  const day = trafficData.countDays[dayIndex];
  const site = trafficData.site;
  
  // Initialize computed structure
  day.computed = day.computed || {};
  day.computed.hourlyAggregates = {};
  
  // Determine major/minor approaches from street orientation
  // Default: EW = major, NS = minor (user can override)
  day.computed.majorStreetApproaches = ['EB', 'WB'];
  day.computed.minorStreetApproaches = ['NB', 'SB'];
  
  Object.keys(day.hourlyVolumes).forEach(hourStr => {
    const hour = parseInt(hourStr);
    const hourData = day.hourlyVolumes[hour];
    
    // Sum major street approaches
    const majorTotal = 
      (hourData.EB?.total || 0) + (hourData.WB?.total || 0);
    
    // Get higher minor approach
    const nbTotal = hourData.NB?.total || 0;
    const sbTotal = hourData.SB?.total || 0;
    const highApproach = nbTotal >= sbTotal ? 'NB' : 'SB';
    const highVolume = Math.max(nbTotal, sbTotal);
    const rightTurn = hourData[highApproach]?.right || 0;
    
    // Apply RT reduction
    const reduction = applyRTReduction(trafficData, dayIndex, hour);
    
    day.computed.hourlyAggregates[hour] = {
      majorTotal,
      minorHighApproach: highApproach,
      minorHighVolume: highVolume,
      minorRightTurn: rightTurn,
      minorAdjusted: reduction.adjustedVolume,
      rtReductionApplied: reduction.rtReduction,
      rtMethod: reduction.method
    };
  });
}
```

---

## HTML User Interface Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Crash Lens - Signal Warrant Analyzer</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/docx/7.1.0/docx.min.js"></script>
</head>
<body>
  <div class="container">
    <header>
      <h1>🚦 Crash Lens Signal Warrant Analyzer</h1>
      <p>MUTCD Warrants 1, 2, and 3 Analysis Tool</p>
    </header>
    
    <!-- Section 1: API Configuration -->
    <div class="card">
      <h2>🔑 AI Configuration</h2>
      <select id="ai-provider">
        <option value="anthropic">Claude (Anthropic)</option>
        <option value="openai">GPT-4 (OpenAI)</option>
      </select>
      <input type="password" id="api-key" placeholder="Enter API Key">
      <button onclick="testAPI()">Test Connection</button>
    </div>
    
    <!-- Section 2: Intersection Details -->
    <div class="card">
      <h2>📍 Intersection Details</h2>
      <input type="text" id="intersection-name" placeholder="Intersection Name">
      <input type="text" id="major-street" placeholder="Major Street">
      <input type="text" id="minor-street" placeholder="Minor Street">
      <select id="major-lanes">
        <option value="1">1 Lane</option>
        <option value="2" selected>2+ Lanes</option>
      </select>
      <select id="minor-lanes">
        <option value="1" selected>1 Lane</option>
        <option value="2">2+ Lanes</option>
      </select>
      <input type="number" id="speed-limit" value="35" placeholder="Speed Limit">
      <label><input type="checkbox" id="apply-70pct"> Apply 70% reduction</label>
    </div>
    
    <!-- Section 3: Count Configuration -->
    <div class="card">
      <h2>⏱️ Count Configuration</h2>
      <select id="count-duration">
        <option value="12hr">12-Hour Count (6 AM - 6 PM)</option>
        <option value="24hr">24-Hour Count</option>
      </select>
      <select id="rt-method">
        <option value="fixed">Fixed Percentage</option>
        <option value="pagones">Pagones Theorem</option>
      </select>
      <input type="number" id="fixed-rt-percent" value="30" min="0" max="100" 
             placeholder="Fixed RT Reduction %">
      <select id="pagones-config" class="hidden">
        <option value="sharedLane">Shared Lane (up to 30%)</option>
        <option value="exclusiveRTLane">Exclusive RT Lane (up to 75%)</option>
        <option value="channelizedRT">Channelized RT (up to 100%)</option>
      </select>
    </div>
    
    <!-- Section 4: File Upload -->
    <div class="card">
      <h2>📁 Upload Count Data (1-7 Days)</h2>
      <div class="upload-zone">
        <p>Drag & drop Excel or PDF files here</p>
        <p>Supports: All Traffic Data, Rekor, Quality Counts, Miovision, Jamar</p>
        <input type="file" multiple accept=".xlsx,.xls,.csv,.pdf">
      </div>
      <div id="uploaded-files"></div>
    </div>
    
    <!-- Section 5: Analysis -->
    <button onclick="runAnalysis()">🔍 Run Warrant Analysis</button>
    
    <!-- Section 6: Results -->
    <div id="results-section" class="hidden">
      <div id="overall-result"></div>
      <div id="warrant-details"></div>
      <button onclick="generateMemo()">📄 Generate Official Memo (Word)</button>
    </div>
    
    <!-- Disclaimer -->
    <div class="disclaimer">
      ⚠️ This tool is for screening purposes only. Final determinations require PE review.
    </div>
  </div>
</body>
</html>
```

---

## Word Memo Generation

```javascript
async function generateMemo() {
  const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell } = docx;
  
  const results = window.analysisResults;
  const site = window.trafficData.site;
  const rtConfig = window.trafficData.rtReduction;
  
  const doc = new Document({
    sections: [{
      children: [
        // Header
        new Paragraph({
          alignment: 'center',
          children: [
            new TextRun({ text: 'TRAFFIC SIGNAL WARRANT ANALYSIS', bold: true, size: 32 }),
            new TextRun({ text: '\nOfficial Memorandum', size: 24, break: 1 })
          ]
        }),
        
        // Location Info
        new Paragraph({
          children: [
            new TextRun({ text: `\nLocation: `, bold: true }),
            new TextRun({ text: site.intersectionName }),
            new TextRun({ text: `\nMajor Street: `, bold: true, break: 1 }),
            new TextRun({ text: site.majorStreet }),
            new TextRun({ text: `\nMinor Street: `, bold: true, break: 1 }),
            new TextRun({ text: site.minorStreet }),
            new TextRun({ text: `\nAnalysis Date: `, bold: true, break: 1 }),
            new TextRun({ text: new Date().toLocaleDateString() }),
            new TextRun({ text: `\nDays Analyzed: `, bold: true, break: 1 }),
            new TextRun({ text: `${results.daysAnalyzed} day(s)` })
          ]
        }),
        
        // Configuration
        new Paragraph({
          children: [
            new TextRun({ text: '\n\nANALYSIS CONFIGURATION', bold: true, break: 2 }),
            new TextRun({ text: `\nLane Configuration: ${site.majorStreetLanes} x ${site.minorStreetLanes}`, break: 1 }),
            new TextRun({ text: `\nSpeed Limit: ${site.speedLimit} mph`, break: 1 }),
            new TextRun({ text: `\n70% Factor: ${site.apply70Percent ? 'Applied' : 'Not Applied'}`, break: 1 }),
            new TextRun({ 
              text: `\nRT Reduction: ${rtConfig.method === 'fixed' 
                ? `Fixed ${rtConfig.fixedPercent}%` 
                : `Pagones Theorem (${rtConfig.pagonesConfig.minorStreetConfig})`}`, 
              break: 1 
            })
          ]
        }),
        
        // Results
        new Paragraph({
          children: [
            new TextRun({ text: '\n\nWARRANT RESULTS', bold: true, break: 2 }),
            new TextRun({ text: `\nWarrant 1 (Eight-Hour): ${results.warrant1.anyDayMet ? 'MET' : 'NOT MET'}`, break: 1 }),
            new TextRun({ text: `\nWarrant 2 (Four-Hour): ${results.warrant2.anyDayMet ? 'MET' : 'NOT MET'}`, break: 1 }),
            new TextRun({ text: `\nWarrant 3 (Peak Hour): ${results.warrant3.anyDayMet ? 'MET' : 'NOT MET'}`, break: 1 })
          ]
        }),
        
        // Conclusion
        new Paragraph({
          children: [
            new TextRun({ text: '\n\nCONCLUSION', bold: true, break: 2 }),
            new TextRun({
              text: results.overallWarranted
                ? `\nA traffic signal IS WARRANTED. Satisfied: ${results.warrantsFound.join(', ')}.`
                : '\nA traffic signal is NOT WARRANTED at this location.',
              bold: true,
              break: 1
            })
          ]
        }),
        
        // Disclaimer
        new Paragraph({
          children: [
            new TextRun({ 
              text: '\n\nNote: This analysis is for screening purposes only.',
              italics: true,
              break: 2
            })
          ]
        })
      ]
    }]
  });
  
  const blob = await Packer.toBlob(doc);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `Signal_Warrant_${site.intersectionName.replace(/[^a-z0-9]/gi, '_')}.docx`;
  a.click();
}
```

---

## Summary of Key Features

| Feature | Description |
|---------|-------------|
| **General Purpose** | For Crash Lens, not agency-specific |
| **MUTCD Version** | **11th Edition (December 2023)** |
| **Vendor Support** | All Traffic Data, Rekor, Quality Counts, Miovision, Jamar - ANY format |
| **AI Heavy Lifting** | AI extracts, aggregates, classifies movements, calculates peak hour |
| **Count Duration** | 12-hour (6AM-6PM) or 24-hour options |
| **RT Reduction** | Fixed % (default 30%) OR Pagones Theorem |
| **70% Factor** | Auto-apply when speed > 40 mph OR community < 10,000 |
| **Peak Hour** | AI calculates from extracted data |
| **Multi-Day** | 1-7 days; ANY day meeting = Warranted |
| **Output** | Word memo with all analysis details |
| **Warrants** | 1 (Eight-Hour), 2 (Four-Hour), 3 (Peak Hour) |

---

## Division of Labor

| Component | Responsibility |
|-----------|----------------|
| **AI Assistant** | Extract raw data → Aggregate to hourly → Classify L/T/R → Calculate peak hour → Return structured JSON |
| **HTML Tool** | Apply RT reduction → Compare to MUTCD 11th Ed thresholds → Evaluate warrants → Generate memo |
| **User** | Configure site info → Upload files → Select RT method → Review results → Apply engineering judgment |

---

## Next Steps for Development

1. **Create HTML file** with complete UI and embedded JavaScript
2. **Test with sample data** from Quality Counts file provided
3. **Integrate with existing Crash Lens** warrant analyzer
4. **Add Warrant 7 connection** (crash data from external source)
5. **User testing** with various vendor formats

---

## My Recommendations for Enhanced Tool

Based on my experience with traffic engineering tools and your workflow, here are additional features I recommend:

### 1. **Gap Analysis Visualization**
Add a visual chart showing how close/far each hour is from meeting thresholds. This helps engineers understand "near misses" and justify decisions.

```javascript
// Show percentage of threshold met for each hour
// Green: ≥100%, Yellow: 80-99%, Red: <80%
function calculateGapAnalysis(hourData, thresholds) {
  return {
    majorPercent: (hourData.majorVol / thresholds.major) * 100,
    minorPercent: (hourData.minorVol / thresholds.minor) * 100,
    bothMet: hourData.majorVol >= thresholds.major && hourData.minorVol >= thresholds.minor
  };
}
```

### 2. **Sensitivity Analysis**
Show what would happen if volumes increased by 5%, 10%, 15%. Useful for projected growth scenarios.

### 3. **Alternative Analysis Suggestions**
When warrant NOT met, suggest alternatives per MUTCD Section 4B.03:
- Roundabout
- Pedestrian Hybrid Beacon (PHB)
- RRFB
- All-way stop
- Turn restrictions

### 4. **Multi-Day Summary Statistics**
Show min/max/average across all days analyzed, not just pass/fail.

### 5. **Export Raw Data Table**
Allow export of hour-by-hour volumes to CSV for documentation.

### 6. **VDOT Signal Justification Report Integration**
Since Virginia requires both warrant AND justification, add fields for:
- Crash history summary (connects to Warrant 7)
- Delay measurements
- Queue observations
- Sight distance assessment

### 7. **QA/QC Checklist**
Built-in checklist before finalizing:
- [ ] Verified major/minor street designation
- [ ] Confirmed lane counts
- [ ] Checked speed limit accuracy
- [ ] Reviewed RT reduction applicability
- [ ] Cross-checked peak hour with vendor data

### 8. **Version History in Memo**
Include MUTCD edition reference and tool version in generated memo for documentation.

### 9. **Batch Processing**
Allow analysis of multiple intersections in one session for corridor studies.

### 10. **Integration with Crash Lens Crash Data**
Since Crash Lens already has crash data:
- Auto-populate Warrant 7 crash counts
- Show angle + pedestrian crashes (per MUTCD 11th Edition)
- Calculate if 80% volume threshold is also met for Warrant 7

---

## MUTCD 11th Edition Important Notes

**Per Section 4C.01 (Page 651-652):**

> "The satisfaction of a traffic signal warrant or warrants shall not in itself require the installation of a traffic control signal."

> "Agencies can install a traffic control signal at a location where no warrants are met, but only after conducting an engineering study that documents the rationale..."

**Tool should clearly display:**
1. Warrant analysis is a SCREENING tool
2. Final decision requires licensed PE review
3. Engineering judgment may override warrant results
4. MUTCD 11th Edition (December 2023) reference
