# Mapillary Integration Plan for Street View AI Tab

## Overview

This plan implements **Option A: Use Mapillary As Primary** - querying Mapillary's free API for pre-detected traffic infrastructure, with automatic fallback to Google Street View + VLM analysis when Mapillary coverage is unavailable.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER SELECTS LOCATION                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 1: CHECK MAPILLARY COVERAGE                          │
│                                                                              │
│   Query: graph.mapillary.com/images?bbox=...&limit=1                        │
│   Purpose: Verify if Mapillary has imagery within 100m of location          │
│   Cost: FREE                                                                 │
│   Speed: ~200ms                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
┌─────────────────────────────┐   ┌─────────────────────────────────────────┐
│   MAPILLARY HAS COVERAGE    │   │        NO MAPILLARY COVERAGE            │
│                             │   │                                         │
│  ┌────────────────────────┐ │   │  ┌─────────────────────────────────────┐│
│  │ Query Map Features     │ │   │  │ Fall back to Google Street View    ││
│  │ - Traffic signs        │ │   │  │ + Claude Vision analysis            ││
│  │ - Point features       │ │   │  │ (existing implementation)           ││
│  │ Cost: FREE             │ │   │  │ Cost: ~$0.05-0.15/location          ││
│  │ Speed: ~500ms          │ │   │  │ Speed: ~15-30 seconds               ││
│  └────────────────────────┘ │   │  └─────────────────────────────────────┘│
│              │              │   │                  │                      │
│              ▼              │   │                  ▼                      │
│  ┌────────────────────────┐ │   │  ┌─────────────────────────────────────┐│
│  │ Get Mapillary Images   │ │   │  │ Show "VLM Analysis" badge          ││
│  │ for visualization      │ │   │  │ Display imagery source: Google      ││
│  │ Cost: FREE             │ │   │  └─────────────────────────────────────┘│
│  └────────────────────────┘ │   │                                         │
│              │              │   └─────────────────────────────────────────┘
│              ▼              │
│  ┌────────────────────────┐ │
│  │ OPTIONAL: VLM for      │ │
│  │ context/recommendations│ │
│  │ (user can trigger)     │ │
│  └────────────────────────┘ │
└─────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         UNIFIED RESULTS DISPLAY                              │
│                                                                              │
│   - Data source badge (Mapillary / Google Street View / Hybrid)             │
│   - Coverage quality indicator                                               │
│   - Detected features with confidence                                        │
│   - Imagery thumbnails (from Mapillary or Google)                           │
│   - Optional: "Enhance with AI" button for VLM analysis                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Mapillary API Foundation

### 1.1 State Management

Add Mapillary-specific state to track API status and results:

```javascript
// New: Mapillary Integration State
const mapillaryState = {
    accessToken: localStorage.getItem('mapillaryAccessToken') || '',
    tokenConfigured: false,

    // Coverage check results
    coverage: {
        checked: false,
        available: false,
        imageCount: 0,
        nearestImageDistance: null,
        coverageQuality: null  // 'excellent', 'good', 'sparse', 'none'
    },

    // Detected features from Mapillary
    features: {
        trafficSigns: [],
        pointFeatures: [],
        totalCount: 0,
        lastUpdated: null
    },

    // Mapillary imagery
    images: [],
    selectedImage: null,

    // Analysis state
    loading: false,
    error: null,

    // Cache to avoid redundant API calls
    cache: new Map(),  // key: "lat,lng" -> { features, timestamp }
    cacheExpiry: 3600000  // 1 hour
};
```

### 1.2 Configuration

```javascript
// Mapillary API Configuration
const MAPILLARY_CONFIG = {
    baseUrl: 'https://graph.mapillary.com',
    tilesUrl: 'https://tiles.mapillary.com',

    // Search radius in meters
    searchRadius: 50,        // Primary search
    extendedRadius: 100,     // If primary returns no results
    maxRadius: 200,          // Maximum search distance

    // Feature types to query
    featureTypes: {
        trafficSigns: true,
        pointFeatures: true
    },

    // Rate limiting (be nice to free API)
    requestDelay: 100,  // ms between requests
    maxConcurrent: 3,

    // Image settings
    imageThumbSize: 320,
    imageFullSize: 1024,

    // Fields to request
    mapFeatureFields: [
        'id',
        'object_value',
        'object_type',
        'geometry',
        'first_seen_at',
        'last_seen_at'
    ],
    imageFields: [
        'id',
        'captured_at',
        'compass_angle',
        'geometry',
        'thumb_256_url',
        'thumb_1024_url'
    ]
};
```

### 1.3 Core API Functions

```javascript
/**
 * Check if Mapillary has coverage at a location
 * @param {number} lat - Latitude
 * @param {number} lng - Longitude
 * @returns {Promise<{available: boolean, imageCount: number, quality: string}>}
 */
async function checkMapillaryCoverage(lat, lng) {
    // Implementation
}

/**
 * Query Mapillary for traffic signs near a location
 * @param {number} lat - Latitude
 * @param {number} lng - Longitude
 * @param {number} radius - Search radius in meters
 * @returns {Promise<Array>} Array of traffic sign features
 */
async function queryMapillaryTrafficSigns(lat, lng, radius = 50) {
    // Implementation
}

/**
 * Query Mapillary for point features (signals, crosswalks, etc.)
 * @param {number} lat - Latitude
 * @param {number} lng - Longitude
 * @param {number} radius - Search radius in meters
 * @returns {Promise<Array>} Array of point features
 */
async function queryMapillaryPointFeatures(lat, lng, radius = 50) {
    // Implementation
}

/**
 * Get Mapillary images near a location for visualization
 * @param {number} lat - Latitude
 * @param {number} lng - Longitude
 * @param {number} limit - Maximum images to return
 * @returns {Promise<Array>} Array of image metadata
 */
async function getMapillaryImages(lat, lng, limit = 8) {
    // Implementation
}

/**
 * Get Mapillary image thumbnail URL
 * @param {string} imageId - Mapillary image ID
 * @param {string} size - 'thumb_256_url' or 'thumb_1024_url'
 * @returns {string} Image URL
 */
function getMapillaryImageUrl(imageId, size = 'thumb_256_url') {
    // Implementation
}
```

---

## Phase 2: Feature Detection & Mapping

### 2.1 Mapillary Feature Value Mapping

Map Mapillary's feature codes to user-friendly names:

```javascript
/**
 * Mapillary traffic sign value to readable name mapping
 * Based on Mapillary's classification scheme
 */
const MAPILLARY_SIGN_MAPPING = {
    // Regulatory Signs
    'regulatory--stop--g1': { name: 'Stop Sign', category: 'traffic_control', icon: '🛑' },
    'regulatory--stop--g2': { name: 'Stop Sign', category: 'traffic_control', icon: '🛑' },
    'regulatory--yield--g1': { name: 'Yield Sign', category: 'traffic_control', icon: '⚠️' },
    'regulatory--speed-limit-25--g1': { name: 'Speed Limit 25', category: 'signing', icon: '🚗' },
    'regulatory--speed-limit-30--g1': { name: 'Speed Limit 30', category: 'signing', icon: '🚗' },
    'regulatory--speed-limit-35--g1': { name: 'Speed Limit 35', category: 'signing', icon: '🚗' },
    'regulatory--speed-limit-45--g1': { name: 'Speed Limit 45', category: 'signing', icon: '🚗' },
    'regulatory--no-parking--g1': { name: 'No Parking', category: 'signing', icon: '🚫' },
    'regulatory--no-left-turn--g1': { name: 'No Left Turn', category: 'signing', icon: '🚫' },
    'regulatory--no-right-turn--g1': { name: 'No Right Turn', category: 'signing', icon: '🚫' },
    'regulatory--no-u-turn--g1': { name: 'No U-Turn', category: 'signing', icon: '🚫' },
    'regulatory--one-way-left--g1': { name: 'One Way Left', category: 'signing', icon: '➡️' },
    'regulatory--one-way-right--g1': { name: 'One Way Right', category: 'signing', icon: '⬅️' },
    'regulatory--keep-right--g1': { name: 'Keep Right', category: 'signing', icon: '↗️' },
    'regulatory--turn-right--g1': { name: 'Turn Right Only', category: 'signing', icon: '↪️' },
    'regulatory--turn-left--g1': { name: 'Turn Left Only', category: 'signing', icon: '↩️' },

    // Warning Signs
    'warning--curve-left--g1': { name: 'Curve Left Ahead', category: 'signing', icon: '⚠️' },
    'warning--curve-right--g1': { name: 'Curve Right Ahead', category: 'signing', icon: '⚠️' },
    'warning--signal-ahead--g1': { name: 'Signal Ahead', category: 'signing', icon: '🚦' },
    'warning--stop-ahead--g1': { name: 'Stop Ahead', category: 'signing', icon: '🛑' },
    'warning--yield-ahead--g1': { name: 'Yield Ahead', category: 'signing', icon: '⚠️' },
    'warning--pedestrian-crossing--g1': { name: 'Pedestrian Crossing', category: 'pedestrian', icon: '🚶' },
    'warning--school-zone--g1': { name: 'School Zone', category: 'signing', icon: '🏫' },
    'warning--children--g1': { name: 'Children', category: 'signing', icon: '👶' },
    'warning--intersection--g1': { name: 'Intersection Ahead', category: 'signing', icon: '✚' },
    'warning--railroad-crossing--g1': { name: 'Railroad Crossing', category: 'signing', icon: '🚂' },

    // Information Signs
    'information--parking--g1': { name: 'Parking', category: 'signing', icon: '🅿️' },
    'information--hospital--g1': { name: 'Hospital', category: 'signing', icon: '🏥' },

    // Default for unknown
    '_default': { name: 'Traffic Sign', category: 'signing', icon: '🪧' }
};

/**
 * Mapillary point feature mapping
 */
const MAPILLARY_POINT_MAPPING = {
    'object--traffic-light--*': { name: 'Traffic Signal', category: 'traffic_control', icon: '🚦' },
    'object--street-light--*': { name: 'Street Light', category: 'lighting', icon: '💡' },
    'object--fire-hydrant--*': { name: 'Fire Hydrant', category: 'other', icon: '🚒' },
    'object--utility-pole--*': { name: 'Utility Pole', category: 'other', icon: '📍' },
    'object--manhole--*': { name: 'Manhole', category: 'other', icon: '⭕' },
    'object--bench--*': { name: 'Bench', category: 'pedestrian', icon: '🪑' },
    'object--trash-can--*': { name: 'Trash Can', category: 'other', icon: '🗑️' },
    'object--bike-rack--*': { name: 'Bike Rack', category: 'pedestrian', icon: '🚲' },
    'marking--crosswalk-zebra--*': { name: 'Zebra Crosswalk', category: 'pedestrian', icon: '🚶' },

    '_default': { name: 'Point Feature', category: 'other', icon: '📍' }
};

/**
 * Convert Mapillary feature value to readable format
 */
function mapMapillaryFeature(objectValue, objectType) {
    // Implementation to lookup and return user-friendly feature info
}
```

### 2.2 Feature Aggregation

```javascript
/**
 * Aggregate Mapillary features into infrastructure inventory
 * @param {Array} trafficSigns - Traffic sign features from Mapillary
 * @param {Array} pointFeatures - Point features from Mapillary
 * @returns {Object} Aggregated inventory matching existing analysis format
 */
function aggregateMapillaryFeatures(trafficSigns, pointFeatures) {
    // Group by category
    // Determine traffic control type
    // Build infrastructure array
    // Return format compatible with existing renderSVAnalysisResults()
}
```

---

## Phase 3: Unified Analysis Flow

### 3.1 New Primary Analysis Function

```javascript
/**
 * Run infrastructure analysis - Mapillary first, fallback to VLM
 * This replaces/wraps the existing runStreetViewAnalysis()
 */
async function runInfrastructureAnalysis() {
    const coords = getLocationCoordinates();
    if (!coords) {
        showToast('No valid coordinates found', 'warning');
        return;
    }

    // Update UI to loading state
    setAnalysisLoadingState(true);
    updateLoadingStatus('Checking Mapillary coverage...');

    try {
        // Step 1: Check Mapillary coverage
        const coverage = await checkMapillaryCoverage(coords.lat, coords.lng);
        mapillaryState.coverage = coverage;

        if (coverage.available && coverage.quality !== 'none') {
            // Step 2a: Use Mapillary
            updateLoadingStatus('Fetching Mapillary detections...');
            const result = await runMapillaryAnalysis(coords);
            renderAnalysisResults(result, 'mapillary');
        } else {
            // Step 2b: Fallback to Google Street View + VLM
            updateLoadingStatus('No Mapillary coverage - using Street View AI...');
            const result = await runStreetViewAnalysis();
            renderAnalysisResults(result, 'streetview');
        }
    } catch (error) {
        handleAnalysisError(error);
    } finally {
        setAnalysisLoadingState(false);
    }
}

/**
 * Run Mapillary-based analysis
 */
async function runMapillaryAnalysis(coords) {
    // Query traffic signs
    updateLoadingStatus('Detecting traffic signs...');
    const trafficSigns = await queryMapillaryTrafficSigns(coords.lat, coords.lng);

    // Query point features
    updateLoadingStatus('Detecting infrastructure features...');
    const pointFeatures = await queryMapillaryPointFeatures(coords.lat, coords.lng);

    // Get images for visualization
    updateLoadingStatus('Loading imagery...');
    const images = await getMapillaryImages(coords.lat, coords.lng, 8);

    // Aggregate into standard format
    const analysis = aggregateMapillaryFeatures(trafficSigns, pointFeatures);
    analysis.dataSource = 'mapillary';
    analysis.images = images;
    analysis.featureCount = trafficSigns.length + pointFeatures.length;

    // Store in state
    mapillaryState.features.trafficSigns = trafficSigns;
    mapillaryState.features.pointFeatures = pointFeatures;
    mapillaryState.images = images;

    return analysis;
}
```

### 3.2 Optional VLM Enhancement

```javascript
/**
 * Enhance Mapillary results with VLM analysis
 * User-triggered for additional context and recommendations
 */
async function enhanceWithVLMAnalysis() {
    if (!mapillaryState.images.length) {
        showToast('No imagery available for AI analysis', 'warning');
        return;
    }

    // Use Mapillary images for VLM analysis
    // Focus prompt on:
    // - Condition assessment (are signs faded?)
    // - Missing features (what's NOT there)
    // - Safety observations
    // - Recommendations based on crash data

    const enhancement = await analyzeImagesWithVLM(mapillaryState.images);

    // Merge with existing Mapillary results
    mergeVLMEnhancement(enhancement);
}
```

---

## Phase 4: UI/UX Updates

### 4.1 Settings Panel Updates

Add Mapillary configuration to the Street View AI settings:

```html
<!-- Mapillary Configuration Section -->
<div class="sv-config-section">
    <h4><span>🗺️</span> Mapillary Configuration</h4>

    <div class="sv-config-group">
        <label>Mapillary Access Token</label>
        <input type="password" id="mapillaryAccessToken"
               placeholder="MLY|..."
               onchange="saveMapillaryToken(this.value)">
        <div class="sv-config-hint">
            <a href="https://www.mapillary.com/developer" target="_blank">Get free token</a>
            - 100% free, no credit card required
        </div>
    </div>

    <div class="sv-config-group">
        <label>Data Source Priority</label>
        <select id="dataSourcePriority" onchange="updateDataSourcePriority(this.value)">
            <option value="mapillary_first">Mapillary First (recommended)</option>
            <option value="streetview_only">Google Street View Only</option>
            <option value="both">Always Use Both</option>
        </select>
        <div class="sv-config-hint">Mapillary is free and instant; Street View uses AI credits</div>
    </div>

    <div class="sv-config-group">
        <label>Search Radius</label>
        <select id="mapillarySearchRadius">
            <option value="50">50 meters (precise)</option>
            <option value="100" selected>100 meters (recommended)</option>
            <option value="200">200 meters (wide)</option>
        </select>
    </div>
</div>
```

### 4.2 Results Display Updates

Show data source clearly:

```html
<!-- Data Source Badge -->
<div class="sv-data-source-badge" id="svDataSourceBadge">
    <!-- Populated dynamically -->
</div>
```

```javascript
function renderDataSourceBadge(source, coverage) {
    const badge = document.getElementById('svDataSourceBadge');

    if (source === 'mapillary') {
        badge.innerHTML = `
            <div class="data-source-mapillary">
                <span class="data-source-icon">🗺️</span>
                <span class="data-source-label">Mapillary</span>
                <span class="data-source-detail">FREE • ${coverage.imageCount} images</span>
                <span class="data-source-quality quality-${coverage.quality}">
                    ${coverage.quality} coverage
                </span>
            </div>
        `;
    } else if (source === 'streetview') {
        badge.innerHTML = `
            <div class="data-source-streetview">
                <span class="data-source-icon">📷</span>
                <span class="data-source-label">Google Street View + AI</span>
                <span class="data-source-detail">VLM Analysis</span>
            </div>
        `;
    } else if (source === 'hybrid') {
        badge.innerHTML = `
            <div class="data-source-hybrid">
                <span class="data-source-icon">🔄</span>
                <span class="data-source-label">Hybrid</span>
                <span class="data-source-detail">Mapillary + AI Enhancement</span>
            </div>
        `;
    }
}
```

### 4.3 Feature Display with Source Attribution

```javascript
function renderFeatureCard(feature, source) {
    const sourceIcon = source === 'mapillary' ? '🗺️' : '🤖';
    const sourceClass = source === 'mapillary' ? 'source-mapillary' : 'source-vlm';

    return `
        <div class="sv-feature-card ${sourceClass}">
            <div class="sv-feature-card-header">
                <div class="sv-feature-card-title">${feature.name}</div>
                <div class="sv-feature-card-icon">${feature.icon}</div>
            </div>
            <div class="sv-feature-card-value">${statusBadge(feature.status)}</div>
            <div class="sv-feature-card-meta">
                <span class="feature-source" title="Detected by ${source}">
                    ${sourceIcon}
                </span>
                ${feature.lastSeen ? `
                    <span class="feature-date" title="Last verified">
                        📅 ${formatDate(feature.lastSeen)}
                    </span>
                ` : ''}
            </div>
        </div>
    `;
}
```

### 4.4 Enhance with AI Button

```html
<!-- Show when using Mapillary data -->
<div class="sv-enhance-section" id="svEnhanceSection" style="display:none">
    <div class="sv-enhance-prompt">
        <span>💡</span>
        <span>Want AI-powered recommendations based on crash patterns?</span>
    </div>
    <button class="btn-soft btn-soft-primary" onclick="enhanceWithVLMAnalysis()">
        🤖 Enhance with AI Analysis
    </button>
    <div class="sv-enhance-note">
        Uses Claude Vision to analyze imagery and provide safety recommendations
    </div>
</div>
```

---

## Phase 5: Caching & Performance

### 5.1 Result Caching

```javascript
/**
 * Cache Mapillary results to avoid redundant API calls
 */
const mapillaryCache = {
    storage: new Map(),
    maxAge: 3600000, // 1 hour

    generateKey(lat, lng, radius) {
        // Round to ~10m precision for cache key
        const roundedLat = Math.round(lat * 10000) / 10000;
        const roundedLng = Math.round(lng * 10000) / 10000;
        return `${roundedLat},${roundedLng},${radius}`;
    },

    get(lat, lng, radius) {
        const key = this.generateKey(lat, lng, radius);
        const cached = this.storage.get(key);

        if (cached && Date.now() - cached.timestamp < this.maxAge) {
            console.log('[Mapillary] Using cached results');
            return cached.data;
        }
        return null;
    },

    set(lat, lng, radius, data) {
        const key = this.generateKey(lat, lng, radius);
        this.storage.set(key, {
            data,
            timestamp: Date.now()
        });

        // Limit cache size
        if (this.storage.size > 100) {
            const firstKey = this.storage.keys().next().value;
            this.storage.delete(firstKey);
        }
    },

    clear() {
        this.storage.clear();
    }
};
```

### 5.2 Batch Operations for Multiple Locations

```javascript
/**
 * Batch query Mapillary for multiple locations (for hotspot analysis)
 * @param {Array} locations - Array of {lat, lng, name} objects
 * @returns {Promise<Map>} Map of location name -> features
 */
async function batchQueryMapillary(locations) {
    const results = new Map();
    const batchSize = 5;

    for (let i = 0; i < locations.length; i += batchSize) {
        const batch = locations.slice(i, i + batchSize);

        const promises = batch.map(async loc => {
            const features = await queryMapillaryFeatures(loc.lat, loc.lng);
            return { name: loc.name, features };
        });

        const batchResults = await Promise.all(promises);
        batchResults.forEach(r => results.set(r.name, r.features));

        // Rate limiting between batches
        if (i + batchSize < locations.length) {
            await new Promise(r => setTimeout(r, 200));
        }
    }

    return results;
}
```

---

## Phase 6: Error Handling & Edge Cases

### 6.1 Error Scenarios

```javascript
const MAPILLARY_ERRORS = {
    NO_TOKEN: {
        code: 'NO_TOKEN',
        message: 'Mapillary access token not configured',
        action: 'fallback',  // Fall back to Street View
        userMessage: 'Configure Mapillary token for free infrastructure detection'
    },
    INVALID_TOKEN: {
        code: 'INVALID_TOKEN',
        message: 'Mapillary access token is invalid',
        action: 'fallback',
        userMessage: 'Invalid Mapillary token - using Street View AI instead'
    },
    RATE_LIMITED: {
        code: 'RATE_LIMITED',
        message: 'Mapillary rate limit exceeded',
        action: 'retry',
        retryAfter: 60000,
        userMessage: 'Too many requests - please wait a moment'
    },
    NO_COVERAGE: {
        code: 'NO_COVERAGE',
        message: 'No Mapillary coverage at this location',
        action: 'fallback',
        userMessage: 'No Mapillary imagery here - using Street View AI'
    },
    NETWORK_ERROR: {
        code: 'NETWORK_ERROR',
        message: 'Network error connecting to Mapillary',
        action: 'fallback',
        userMessage: 'Could not reach Mapillary - using Street View AI'
    }
};

/**
 * Handle Mapillary API errors gracefully
 */
function handleMapillaryError(error) {
    console.error('[Mapillary] Error:', error);

    const errorInfo = MAPILLARY_ERRORS[error.code] || {
        action: 'fallback',
        userMessage: 'Mapillary error - using Street View AI'
    };

    if (errorInfo.action === 'fallback') {
        showToast(errorInfo.userMessage, 'info');
        return runStreetViewAnalysis();  // Automatic fallback
    } else if (errorInfo.action === 'retry') {
        // Schedule retry
        setTimeout(() => runInfrastructureAnalysis(), errorInfo.retryAfter);
        showToast(errorInfo.userMessage, 'warning');
    }
}
```

---

## Implementation Sequence

### Week 1: Foundation
- [ ] Add Mapillary state management
- [ ] Add configuration constants
- [ ] Implement `checkMapillaryCoverage()`
- [ ] Add settings UI for token configuration
- [ ] Test coverage check API

### Week 2: Feature Detection
- [ ] Implement `queryMapillaryTrafficSigns()`
- [ ] Implement `queryMapillaryPointFeatures()`
- [ ] Create feature value mappings
- [ ] Implement `aggregateMapillaryFeatures()`
- [ ] Test feature detection

### Week 3: Image Integration
- [ ] Implement `getMapillaryImages()`
- [ ] Create Mapillary image display components
- [ ] Add image viewer integration
- [ ] Test image loading

### Week 4: Unified Flow
- [ ] Implement `runInfrastructureAnalysis()`
- [ ] Implement `runMapillaryAnalysis()`
- [ ] Create unified results renderer
- [ ] Implement fallback logic
- [ ] Add data source badges

### Week 5: Enhancement & Polish
- [ ] Implement VLM enhancement option
- [ ] Add result caching
- [ ] Implement error handling
- [ ] Add batch operations
- [ ] Performance optimization

### Week 6: Testing & Documentation
- [ ] Test with various Henrico County locations
- [ ] Verify fallback scenarios
- [ ] Test error handling
- [ ] Update user documentation
- [ ] Performance benchmarking

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| API cost reduction | 80% | Compare before/after for locations with Mapillary coverage |
| Analysis speed (Mapillary) | < 2 seconds | Time from click to results |
| Analysis speed (fallback) | < 30 seconds | Existing VLM performance |
| Coverage rate (Henrico) | Measure baseline | % of locations with Mapillary data |
| Feature detection accuracy | > 90% | Compare to field verification |
| User satisfaction | Positive feedback | Qualitative assessment |

---

## Files to Modify

### Primary
- `app/index.html` - Main application file
  - Add Mapillary state and config (~lines 46150-46200)
  - Add Mapillary API functions (new section)
  - Update `runStreetViewAnalysis()` (~line 46568)
  - Update UI components

### Secondary
- `config.json` - Add Mapillary token storage option

---

## Dependencies

### Required
- Mapillary Access Token (free from mapillary.com/developer)

### Optional
- Google Maps API Key (for fallback)
- Claude/Anthropic API Key (for VLM fallback)

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Low Mapillary coverage in Henrico | Automatic fallback to Street View + VLM |
| Mapillary API changes | Abstract API calls, version pin |
| Rate limiting | Caching, request throttling |
| Token exposure | Store in localStorage, never log |
| Feature mapping incomplete | Default fallback category, log unknowns |

---

## Next Steps

1. **Verify Coverage**: Check Mapillary coverage for top 20 crash hotspots in Henrico
2. **Get Token**: User has Mapillary account - obtain access token
3. **Prototype**: Build minimal coverage check + feature query
4. **Iterate**: Expand based on coverage findings
