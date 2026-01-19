# HERE Road Attributes Integration Plan

## Overview

Integrate HERE road attribute data (speed limits, slope/grade, lane data, traffic signals) into **existing panels** across CMF Tab, Map Tab, Warrants Tab, and AI Assistant.

### Integration Approach: Option B

Add road attributes as new sections within existing location detail views rather than creating a separate panel.

| Tab | Integration Point |
|-----|-------------------|
| **CMF Tab** | Below crash profile, above recommendations |
| **Map Tab** | In location popup/sidebar |
| **Warrants Tab** | In signal warrant analysis section |
| **AI Assistant** | Include in context for recommendations |

---

## Phase 1: Foundation & Configuration

### 1.1 State Management Setup

| Task | Description | Dependencies |
|------|-------------|--------------|
| 1.1.1 | Define `hereState` object structure | None |
| 1.1.2 | Add to global state initialization | 1.1.1 |
| 1.1.3 | Create localStorage persistence for API key | 1.1.1 |
| 1.1.4 | Create localStorage persistence for cache | 1.1.1 |

**State Structure:**
```javascript
hereState = {
    apiKey: string | null,
    enabled: boolean,
    cache: {
        [locationKey]: {
            data: RoadAttributes,
            fetchedAt: timestamp,
            expiresAt: timestamp
        }
    },
    usageCount: number,
    usageResetDate: string,
    error: string | null,
    loading: boolean
}
```

### 1.2 Settings UI

| Task | Description | Dependencies |
|------|-------------|--------------|
| 1.2.1 | Add "Data Sources" section to existing Settings/Config area | None |
| 1.2.2 | Create API key input field with show/hide toggle | 1.2.1 |
| 1.2.3 | Add "Test Connection" button | 1.2.2 |
| 1.2.4 | Create checkboxes for data layer selection | 1.2.1 |
| 1.2.5 | Add usage meter display (X / 2,500 free) | 1.1.4 |
| 1.2.6 | Add help link to developer.here.com | 1.2.1 |
| 1.2.7 | Save/load settings from localStorage | 1.2.2, 1.1.3 |

**UI Location:** Add to existing config panel or create gear icon menu

---

## Phase 2: API Integration Layer

### 2.1 Core API Functions

| Task | Description | Dependencies |
|------|-------------|--------------|
| 2.1.1 | Create `convertToHereTile(lat, lon, level)` - coordinate to tile conversion | None |
| 2.1.2 | Create `fetchRoadAttributes(lat, lon)` - main API call function | 2.1.1 |
| 2.1.3 | Create `parseSpeedLimitResponse(data)` | 2.1.2 |
| 2.1.4 | Create `parseSlopeResponse(data)` | 2.1.2 |
| 2.1.5 | Create `parseLaneResponse(data)` | 2.1.2 |
| 2.1.6 | Create `parseTrafficSignResponse(data)` | 2.1.2 |
| 2.1.7 | Create `buildRoadContext(parsedData)` - normalize into standard format | 2.1.3-2.1.6 |

**Standard RoadContext Object:**
```javascript
{
    speedLimit: { value: 45, unit: 'mph', type: 'regulatory' },
    conditionalSpeeds: [{ value: 25, condition: 'school zone', times: '7-9am, 2-4pm' }],
    grade: { value: 2.1, direction: 'upgrade', unit: 'percent' },
    lanes: { count: 4, perDirection: 2, turnLanes: false, median: 'raised' },
    signal: { present: true, type: 'traffic signal' },
    curve: { radius: null, straight: true },
    source: 'HERE',
    fetchedAt: timestamp
}
```

### 2.2 Cache Management

| Task | Description | Dependencies |
|------|-------------|--------------|
| 2.2.1 | Create `generateLocationKey(lat, lon, route, node)` | None |
| 2.2.2 | Create `getCachedRoadContext(locationKey)` | 2.2.1 |
| 2.2.3 | Create `setCachedRoadContext(locationKey, data)` | 2.2.1 |
| 2.2.4 | Create `isCacheValid(cacheEntry)` - check TTL (30 days) | 2.2.2 |
| 2.2.5 | Create `clearExpiredCache()` - cleanup function | 2.2.4 |
| 2.2.6 | Create `getRoadContext(location)` - main entry point (cache-first) | 2.2.2, 2.1.2 |

### 2.3 Error Handling & Usage Tracking

| Task | Description | Dependencies |
|------|-------------|--------------|
| 2.3.1 | Create `handleHereApiError(error)` - user-friendly messages | 2.1.2 |
| 2.3.2 | Create `incrementUsageCount()` | 1.1.4 |
| 2.3.3 | Create `checkUsageLimit()` - warn if approaching 2,500 | 2.3.2 |
| 2.3.4 | Create `resetMonthlyUsage()` - auto-reset on new month | 2.3.2 |

---

## Phase 3: CMF Tab Integration

### 3.1 UI Components

| Task | Description | Dependencies |
|------|-------------|--------------|
| 3.1.1 | Create `renderRoadContextSection(roadContext)` - HTML generator | Phase 2 |
| 3.1.2 | Add "Road Characteristics" section to location detail panel | 3.1.1 |
| 3.1.3 | Add loading spinner during API fetch | 3.1.2 |
| 3.1.4 | Add error state display ("Unable to fetch road data") | 3.1.2, 2.3.1 |
| 3.1.5 | Add "Data not available" state for locations outside coverage | 3.1.2 |
| 3.1.6 | Add source attribution ("Source: HERE Technologies") | 3.1.2 |

**Integration Point:** Below crash profile summary, above CMF recommendations

### 3.2 Data Flow Integration

| Task | Description | Dependencies |
|------|-------------|--------------|
| 3.2.1 | Modify `selectCMFLocation()` to trigger road context fetch | 3.1.2, 2.2.6 |
| 3.2.2 | Add `roadContext` property to `cmfState` | 3.2.1 |
| 3.2.3 | Create `updateCMFRoadContext()` - refresh UI on data arrival | 3.2.2 |
| 3.2.4 | Handle case when HERE is disabled (hide section gracefully) | 3.2.1 |

### 3.3 Enhanced CMF Recommendations

| Task | Description | Dependencies |
|------|-------------|--------------|
| 3.3.1 | Create `getRoadContextCMFFactors(roadContext)` - identify relevant factors | 3.2.2 |
| 3.3.2 | Modify CMF scoring to boost speed-related CMFs when speed ≥ 45 | 3.3.1 |
| 3.3.3 | Modify CMF scoring to boost grade-related CMFs when grade ≥ 4% | 3.3.1 |
| 3.3.4 | Modify CMF scoring to boost ped CMFs when lanes ≥ 4 | 3.3.1 |
| 3.3.5 | Add "WHY" explanations referencing road context | 3.3.2-3.3.4 |
| 3.3.6 | Add visual indicator showing road-context-enhanced recommendations | 3.3.5 |

**CMF Enhancement Logic:**

| Road Attribute | Triggers CMF Category |
|----------------|----------------------|
| Speed ≥ 45 mph | Speed management countermeasures |
| Grade ≥ 4% | Grade-related treatments (truck climbing lanes, runaway ramps) |
| No signal + high volume | Signal warrant consideration |
| Lanes ≥ 4 | Pedestrian crossing treatments |
| Curve radius < 1000 ft | Curve warning signs, delineation |

---

## Phase 4: Map Tab Integration

### 4.1 Location Popup Enhancement

| Task | Description | Dependencies |
|------|-------------|--------------|
| 4.1.1 | Modify map popup template to include road context section | Phase 2 |
| 4.1.2 | Add compact road context display (single line or small grid) | 4.1.1 |
| 4.1.3 | Trigger road context fetch on popup open | 4.1.1, 2.2.6 |
| 4.1.4 | Add "View Details" link to jump to CMF tab with context | 4.1.2 |

**Compact Display Format:**
```
📍 US-250 @ Gaskins Rd
Crashes: 47 | EPDO: 892
Speed: 45 mph | Grade: +2% | Lanes: 4 | Signal: ✓
[View Details →]
```

### 4.2 Map Sidebar Enhancement (if applicable)

| Task | Description | Dependencies |
|------|-------------|--------------|
| 4.2.1 | Add road context section to location detail sidebar | Phase 2 |
| 4.2.2 | Match styling with CMF tab road context section | 4.2.1, 3.1.1 |

---

## Phase 5: Warrants Tab Integration

### 5.1 Signal Warrant Context

| Task | Description | Dependencies |
|------|-------------|--------------|
| 5.1.1 | Add road context section to warrant analysis panel | Phase 2 |
| 5.1.2 | Display current signal status from HERE data | 5.1.1 |
| 5.1.3 | Display speed limit (relevant for Warrant 7 - Crash Experience) | 5.1.1 |
| 5.1.4 | Display lane count (relevant for pedestrian warrants) | 5.1.1 |
| 5.1.5 | Add context notes for warrant analysis | 5.1.2-5.1.4 |

**Example Context Note:**
```
ⓘ Road Context: 4-lane roadway (2 per direction) with 45 mph speed limit.
   No existing traffic signal detected.
   Consider Warrant 4 (Pedestrian Volume) given lane configuration.
```

---

## Phase 6: AI Assistant Integration

### 6.1 Context Enhancement

| Task | Description | Dependencies |
|------|-------------|--------------|
| 6.1.1 | Modify `getAIAnalysisContext()` to include road context | Phase 2 |
| 6.1.2 | Format road context for AI prompt inclusion | 6.1.1 |
| 6.1.3 | Update AI context indicator to show "Road data included" | 6.1.1 |
| 6.1.4 | Handle case when road context unavailable (don't include) | 6.1.1 |

**Enhanced AI Context Format:**
```
Location: US-250 @ Gaskins Rd
Crash Summary: 47 crashes (K:0, A:2, B:8, C:15, O:22), EPDO: 892
Top Collision Types: Angle (40%), Rear-end (30%), Sideswipe (15%)
Conditions: 15% wet weather, 20% dark lighting

Road Characteristics (from HERE):
- Posted Speed Limit: 45 mph (regulatory)
- Grade: +2.1% (eastbound upgrade)
- Lanes: 4 total (2 per direction), no dedicated turn lanes
- Traffic Control: Signalized intersection
- Horizontal Alignment: Straight approach
```

### 6.2 AI Response Enhancement

| Task | Description | Dependencies |
|------|-------------|--------------|
| 6.2.1 | Update system prompt to reference road characteristics when available | 6.1.2 |
| 6.2.2 | Add example prompts that leverage road context | 6.2.1 |

---

## Phase 7: Testing & Polish

### 7.1 Testing

| Task | Description | Dependencies |
|------|-------------|--------------|
| 7.1.1 | Test with valid API key - verify data fetch | Phases 1-6 |
| 7.1.2 | Test without API key - verify graceful degradation | Phases 1-6 |
| 7.1.3 | Test with invalid API key - verify error handling | Phases 1-6 |
| 7.1.4 | Test cache persistence across browser sessions | Phase 2 |
| 7.1.5 | Test usage tracking accuracy | 2.3.2 |
| 7.1.6 | Test all tabs with HERE enabled/disabled | Phases 3-6 |
| 7.1.7 | Verify crash counts still match across views | Phases 3-6 |
| 7.1.8 | Test with locations outside HERE coverage | 2.3.1 |

### 7.2 Polish

| Task | Description | Dependencies |
|------|-------------|--------------|
| 7.2.1 | Add consistent styling across all road context displays | Phases 3-5 |
| 7.2.2 | Add tooltips explaining each road attribute | 7.2.1 |
| 7.2.3 | Add "Beta" badge to road context sections | 7.2.1 |
| 7.2.4 | Add loading states for all integration points | Phases 3-5 |
| 7.2.5 | Performance optimization - debounce rapid location changes | Phase 2 |

---

## Dependency Graph

```
Phase 1 (Foundation)
    │
    ├── 1.1 State Management ──────┐
    │                              │
    └── 1.2 Settings UI ───────────┤
                                   │
                                   ▼
                           Phase 2 (API Layer)
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
              Phase 3         Phase 4        Phase 5
              (CMF Tab)       (Map Tab)      (Warrants)
                    │              │              │
                    └──────────────┼──────────────┘
                                   │
                                   ▼
                           Phase 6 (AI Assistant)
                                   │
                                   ▼
                           Phase 7 (Testing)
```

---

## Estimated Scope

| Phase | Tasks | Complexity |
|-------|-------|------------|
| Phase 1 | 11 | Low |
| Phase 2 | 17 | Medium |
| Phase 3 | 13 | Medium |
| Phase 4 | 6 | Low |
| Phase 5 | 5 | Low |
| Phase 6 | 6 | Low |
| Phase 7 | 13 | Medium |
| **Total** | **71 tasks** | |

---

## Files Modified

| File | Changes |
|------|---------|
| `index.html` | All UI and logic (single-file architecture) |
| `config.json` | Add HERE default settings (optional) |

---

## API Reference

### HERE Map Attributes API

**Base URL:** `https://smap.hereapi.com/v8/maps/attributes`

| Data Type | Layer Name | Key Fields Returned |
|-----------|------------|---------------------|
| **Speed Limits** | `SPEED_LIMITS_FCn` | `SPEED_LIMIT`, `SPEED_LIMIT_TYPE` |
| **Conditional Speeds** | `SPEED_LIMITS_COND_FCn` | Time-based, weather-based limits |
| **Slope/Grade** | `ADAS_ATTRIB_FCn` | `SLOPES`, `HPZ` (elevation) |
| **Elevation** | `BASIC_HEIGHT_FCn` | Height above sea level |
| **Traffic Signs** | `TRAFFIC_SIGN_FCn` | Sign type, location |
| **Lane Data** | `LANE_FCn` | Lane count, type, width |
| **Curvature** | `ADAS_ATTRIB_FCn` | `CURVATURES`, `HEADINGS` |
| **Road Class** | `LINK_ATTRIBUTE_FCn` | Functional class, paved/unpaved |

*Note: `FCn` = Functional Class (FC1=highways, FC5=local roads)*

### Example API Calls

**Get Speed Limits for a Tile:**
```
GET https://smap.hereapi.com/v8/maps/attributes
    ?layers=SPEED_LIMITS_FC3,SPEED_LIMITS_FC4
    &in=tile:25833791
    &apiKey={YOUR_API_KEY}
```

**Get Slope Data:**
```
GET https://smap.hereapi.com/v8/maps/attributes
    ?layers=ADAS_ATTRIB_FC3,BASIC_HEIGHT_FC3
    &in=tile:24267002
    &apiKey={YOUR_API_KEY}
```

**Get Traffic Signs:**
```
GET https://smap.hereapi.com/v8/maps/attributes
    ?layers=TRAFFIC_SIGN_FC3,TRAFFIC_SIGN_FC4
    &in=tile:25833791
    &apiKey={YOUR_API_KEY}
```

**Get All Attributes Along a Route (Route Matching API):**
```
POST https://routematching.hereapi.com/v8/match/routelinks
    ?routeMatch=1
    &mode=fastest;car
    &attributes=SPEED_LIMITS_FCn(*),ADAS_ATTRIB_FCn(*),LANE_FCn(*)
    &apiKey={YOUR_API_KEY}

Body: [GPS coordinates as CSV or JSON]
```

---

## Pricing

| Tier | Free Allowance | Cost After |
|------|----------------|------------|
| **Maps Attributes** | 2,500 transactions/month | **$5.00 per 1,000** |
| Volume discount | — | 20% off at higher volumes |

### Cost Estimate

| Scenario | Transactions | Monthly Cost |
|----------|--------------|--------------|
| Light use (100 lookups) | 100 | **Free** |
| Moderate (5,000 lookups) | 5,000 | ~$12.50 |
| Heavy (50,000 lookups) | 50,000 | ~$237.50 |

---

## Success Criteria

| Criteria | Measurement |
|----------|-------------|
| Road context displays in CMF tab | Manual verification |
| Road context displays in Map popup | Manual verification |
| Road context displays in Warrants tab | Manual verification |
| AI includes road context in analysis | Check AI prompts |
| Cache reduces API calls | Monitor usage counter |
| Graceful degradation without API key | Test with key removed |
| No impact on existing functionality | All tabs still work |
| Usage stays within free tier | Track monthly calls |

---

## References

- [HERE Map Attributes API Guide](https://developer.here.com/documentation/content-map-attributes/dev_guide/topics/here-map-content.html)
- [HERE Route Matching API](https://developer.here.com/documentation/route-matching/dev_guide/topics/here-map-content.html)
- [HERE Developer Portal](https://developer.here.com/)
- [HERE Pricing](https://www.here.com/get-started/pricing)
- [Getting API Credentials](https://developer.here.com/tutorials/getting-here-credentials/)
