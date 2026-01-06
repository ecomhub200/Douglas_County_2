# Street View AI Algorithm Improvement Plan

## Overview

This plan outlines the implementation strategy to improve the Street View AI infrastructure detection algorithm's accuracy and efficiency based on research findings and identified flaws.

---

## Phase 1: Foundation Improvements (Priority: Critical)

### 1.1 Imagery Availability Pre-Check

**Goal**: Eliminate wasted API calls and provide transparency about data quality.

**Implementation**:
- Add call to Google Street View Metadata API before fetching images
- Check `status` field for "OK" vs "ZERO_RESULTS"
- Extract and display `date` field (imagery capture date)
- Store metadata in `streetViewState` for reporting

**Files to modify**: `app/index.html`

**Functions to create/modify**:
```
checkStreetViewAvailability(lat, lng, googleApiKey) → {available: bool, date: string, panoId: string}
```

**Integration points**:
- Call before `fetchStreetViewImages()` in `runStreetViewAnalysis()`
- Display imagery date in results panel
- Show warning if imagery > 2 years old

---

### 1.2 Multi-Distance Sampling

**Goal**: Capture infrastructure at approach distances (300ft, 500ft) in addition to intersection center.

**Implementation**:
- Calculate offset coordinates along each approach direction
- Capture images at: center (0ft), 300ft back on each approach, optionally 500ft
- Pass all images to AI for comprehensive analysis

**New configuration**:
```javascript
const SV_CONFIG = {
    imageSize: '640x480',
    fov: 90,
    pitch: 10,
    headings: [0, 90, 180, 270],
    // NEW:
    captureDistances: [0, 300], // feet from center
    enableExtendedCapture: true
};
```

**Functions to create**:
```
calculateOffsetCoordinates(centerLat, centerLng, bearingDeg, distanceFeet) → {lat, lng}
generateMultiDistanceCaptures(centerCoords, approaches) → [{lat, lng, heading, distance, direction}]
```

**Integration points**:
- Modify `fetchStreetViewImages()` to iterate over multiple capture points
- Update progress indicator to show "Fetching images (1/12)..." for multi-point capture
- Group images by distance in AI prompt for clarity

---

### 1.3 Approach-Aligned Headings

**Goal**: Capture images looking down actual road approaches, not just cardinal directions.

**Implementation**:
- Option A: Use OpenStreetMap Overpass API to get road geometry at intersection
- Option B: Infer approach directions from crash GPS coordinates clustering
- Option C: Allow user to manually specify approach bearings
- Calculate actual road bearings and capture looking both toward and away from intersection

**Functions to create**:
```
fetchRoadGeometry(lat, lng) → {approaches: [{bearing, roadName}]}
inferApproachesFromCrashes(crashes, centerCoords) → [{bearing, crashCount}]
alignHeadingsToApproaches(approaches) → [heading1, heading2, ...]
```

**UI additions**:
- "Auto-detect approaches" button
- Manual bearing input fields (optional override)
- Visual indicator showing capture directions on mini-map

---

## Phase 2: Detection Quality Improvements

### 2.1 Variable Camera Parameters

**Goal**: Optimize FOV and pitch for different feature types.

**Implementation**:
- Create capture presets for different analysis needs
- Execute multiple passes with different parameters when needed

**New configuration**:
```javascript
const SV_CAPTURE_PRESETS = {
    signals: { fov: 70, pitch: 25, size: '800x600' },      // Look up at signals
    signs: { fov: 90, pitch: 5, size: '800x600' },         // Eye-level signs
    pavement: { fov: 90, pitch: -10, size: '800x600' },    // Look down at markings
    overview: { fov: 120, pitch: 10, size: '640x480' },    // Wide context
    default: { fov: 90, pitch: 10, size: '640x480' }
};
```

**Functions to create**:
```
selectCapturePreset(analysisType, locationType) → preset
fetchStreetViewWithPreset(lat, lng, heading, preset, apiKey) → imageData
```

**Integration points**:
- Add analysis type selector in UI (Quick Scan vs Detailed)
- "Detailed" mode captures with multiple presets
- Merge detections across presets

---

### 2.2 Improved AI Prompt Engineering

**Goal**: Get more accurate and consistent detections from vision models.

**Implementation**:
- Restructure prompt to be more systematic
- Add explicit instructions for each feature category
- Request structured confidence with justification
- Include negative examples (what NOT to report)

**Prompt improvements**:
```
1. Analyze images in sequence (approach → center → departure)
2. For each feature, report:
   - Present/Absent/Partially Visible/Cannot Determine
   - Confidence (High/Medium/Low) with REASON
   - Which image(s) show this feature
3. Explicitly state features NOT visible (don't assume)
4. Flag potential occlusions that limit visibility
```

**Functions to modify**:
- `analyzeStreetViewWithAI()` - restructure prompt
- `buildSVAPrompt()` - create modular prompt builder

---

### 2.3 Semantic Consensus Algorithm

**Goal**: Reduce false conflicts from terminology differences between models.

**Implementation**:
- Create feature ontology mapping equivalent terms
- Implement fuzzy matching for feature names
- Weight by confidence levels
- Separate "agreement" from "terminology difference"

**New data structure**:
```javascript
const FEATURE_ONTOLOGY = {
    'traffic_signal': ['traffic signal', 'traffic light', 'signal', 'stoplight', 'signal head'],
    'stop_sign': ['stop sign', 'stop', 'STOP sign'],
    'crosswalk': ['crosswalk', 'pedestrian crossing', 'marked crossing', 'zebra crossing'],
    // ... etc
};
```

**Functions to create**:
```
normalizeFeatureName(rawName) → canonicalName
semanticMatch(feature1, feature2) → {match: bool, confidence: float}
buildSemanticConsensus(primaryResult, secondaryResult) → mergedResult
```

**Integration points**:
- Replace `buildSVAConsensus()` with improved version
- Add "terminology conflicts" vs "detection conflicts" in results

---

## Phase 3: Satellite Integration

### 3.1 Satellite Imagery Capture

**Goal**: Detect horizontal features (lanes, markings, geometry) from overhead view.

**Implementation**:
- Use Google Static Maps API with satellite view
- Capture at multiple zoom levels (17, 18, 19)
- Send to vision AI for lane/marking analysis

**Functions to create**:
```
fetchSatelliteImages(lat, lng, googleApiKey) → [{zoom, base64, size}]
analyzeSatelliteWithAI(images, apiKey) → {lanes, markings, geometry}
```

**UI additions**:
- Toggle for "Include satellite analysis"
- Separate results section for overhead features
- Visual lane diagram based on detection

---

### 3.2 Multi-Modal Fusion

**Goal**: Merge Street View and satellite detections into unified inventory.

**Implementation**:
- Define which features come from which source
- Resolve conflicts when both sources detect same feature
- Present unified results with source attribution

**Feature source mapping**:
```javascript
const FEATURE_SOURCES = {
    // Street View primary
    'traffic_signal': 'streetview',
    'stop_sign': 'streetview',
    'pedestrian_signal': 'streetview',
    'street_lighting': 'streetview',

    // Satellite primary
    'lane_count': 'satellite',
    'turn_lanes': 'satellite',
    'median_type': 'satellite',
    'crosswalk_pattern': 'satellite',

    // Both (fusion)
    'crosswalk_presence': 'fusion',
    'sidewalk': 'fusion'
};
```

**Functions to create**:
```
fuseDetectionResults(streetViewResult, satelliteResult) → unifiedInventory
resolveSourceConflict(svDetection, satDetection, featureType) → resolvedDetection
```

---

## Phase 4: Validation & Accuracy Tracking

### 4.1 Ground Truth Comparison Framework

**Goal**: Enable accuracy measurement against known data.

**Implementation**:
- Create schema for ground truth data entry
- Build comparison function to calculate metrics
- Store historical accuracy by feature type

**Data structure**:
```javascript
const groundTruth = {
    locationId: 'RT1_MAIN_ST',
    verifiedDate: '2024-01-15',
    verifiedBy: 'field_visit',
    features: {
        traffic_control: 'signal',
        signal_type: 'mast_arm',
        crosswalks: { N: true, E: true, S: true, W: false },
        lane_count: { NB: 2, SB: 2, EB: 1, WB: 1 },
        // ...
    }
};
```

**Functions to create**:
```
compareToGroundTruth(aiResult, groundTruth) → {precision, recall, f1, details}
updateAccuracyMetrics(comparison) → void
getAccuracyByFeatureType() → {feature: {precision, recall, sampleSize}}
```

---

### 4.2 Confidence Calibration

**Goal**: Make confidence indicators reflect actual accuracy.

**Implementation**:
- Track predictions vs outcomes over time
- Adjust displayed confidence based on historical accuracy
- Per-feature-type calibration

**Functions to create**:
```
getCalibratedConfidence(rawConfidence, featureType, historicalAccuracy) → calibratedConfidence
updateCalibrationData(prediction, outcome, featureType) → void
```

---

## Phase 5: UI/UX Improvements

### 5.1 Enhanced Results Display

- Show imagery capture date prominently
- Display confidence with justification tooltip
- Color-code by detection source (SV vs satellite vs fusion)
- Add "Needs Field Verification" flag for low-confidence items

### 5.2 Analysis Configuration Panel

- Quick Scan vs Detailed Analysis toggle
- Approach distance selector (300ft, 500ft, both)
- Satellite inclusion toggle
- Dual-model verification toggle

### 5.3 Accuracy Transparency

- Show historical accuracy metrics in footer
- "Last validated: X intersections, Y% overall accuracy"
- Per-feature accuracy available on hover

---

## Implementation Sequence

```
Week 1-2: Phase 1.1 (Pre-check) + Phase 1.2 (Multi-distance)
    └── Establishes foundation for better data capture

Week 3-4: Phase 1.3 (Approach alignment) + Phase 2.2 (Prompt engineering)
    └── Improves what we capture and how we analyze

Week 5-6: Phase 2.1 (Variable params) + Phase 2.3 (Semantic consensus)
    └── Refines detection quality

Week 7-8: Phase 3.1 + 3.2 (Satellite integration)
    └── Adds overhead detection capability

Week 9-10: Phase 4.1 + 4.2 (Validation framework)
    └── Enables accuracy measurement

Week 11-12: Phase 5 (UI/UX) + Testing + Documentation
    └── Polish and release
```

---

## Success Metrics

| Metric | Current (Est.) | Target | Measurement Method |
|--------|---------------|--------|-------------------|
| Overall detection accuracy | ~65% | 85% | Ground truth comparison |
| Signal detection accuracy | ~85% | 95% | Ground truth comparison |
| Lane count accuracy | ~55% | 90% | Ground truth comparison |
| False positive rate | ~20% | <10% | Ground truth comparison |
| API cost per intersection | $0.05 | $0.30 | Usage tracking |
| Analysis time | 15s | 45s | Performance monitoring |
| User-reported data quality | N/A | >4/5 stars | User feedback |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Google API costs increase | Implement caching, allow user to select analysis depth |
| AI model accuracy varies | Multi-model consensus, confidence calibration |
| Street View coverage gaps | Pre-check, graceful fallback to satellite-only |
| Breaking existing functionality | Incremental rollout, feature flags |
| Performance degradation | Async processing, progress indicators, batch optimization |

---

## Files to Modify

Primary: `app/index.html`
- Lines ~46167-46707: Street View analysis functions
- Lines ~46930-47767: SVA state and functions
- Lines ~47788-48850: Condition diagram functions

Secondary:
- `config.json`: Add new configuration options
- Potentially extract to separate JS file if complexity warrants

---

## Dependencies

- Google Street View Static API (existing)
- Google Street View Metadata API (new)
- Google Static Maps API (new - for satellite)
- OpenStreetMap Overpass API (optional - for road geometry)
- Claude/GPT-4V/Gemini Vision APIs (existing)

---

## Next Steps

1. Review and approve this plan
2. Create feature branch for implementation
3. Begin Phase 1.1 (imagery pre-check) as proof of concept
4. Validate improvement before proceeding to subsequent phases
