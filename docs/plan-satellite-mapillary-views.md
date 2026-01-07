# Implementation Plan: Satellite View & Mapillary Integration

## Overview

Add Mapbox Satellite View and Mapillary street-level imagery across Map, Countermeasures (CMF), and Warrants tabs to provide traffic engineers with comprehensive visual context for safety analysis.

### Final Feature Matrix

| Location Type | Street View | Satellite View | Mapillary View |
|---------------|-------------|----------------|----------------|
| **Intersection** | ✅ (existing) | ✅ NEW | ✅ NEW (500ft buffer) |
| **Road Segment** | ❌ | ✅ NEW | ✅ NEW |
| **Polygon Selection** | ❌ | ✅ NEW (centroid) | ✅ NEW (centroid) |

### Tabs Affected
- **Map Tab** - Location info panel & Drawing selection panel
- **Countermeasures (CMF) Tab** - Location summary section
- **Warrants Tab** - Location panel (all warrant forms: Signal, Stop Sign, Pedestrian, Roundabout)

---

## Phase 1: Core Infrastructure

### 1.1 Create Satellite Thumbnail Function

**File:** `app/index.html` (JavaScript section, near line ~55057)

```javascript
/**
 * Get Mapbox Static Image URL for satellite view
 * @param {number} lat - Latitude
 * @param {number} lng - Longitude
 * @param {number} width - Image width (default 400)
 * @param {number} height - Image height (default 200)
 * @param {number} zoom - Zoom level (default 18 for detailed view)
 * @param {string} style - Mapbox style (default 'satellite-v9')
 * @returns {string|null} - URL or null if no token
 */
function getSatelliteThumbnailUrl(lat, lng, width = 400, height = 200, zoom = 18, style = 'satellite-v9') {
    const mapboxToken = appConfig?.apis?.mapbox?.accessToken;
    if (!mapboxToken) {
        console.warn('[Satellite] No Mapbox access token configured');
        return null;
    }

    // Mapbox Static Images API
    return `https://api.mapbox.com/styles/v1/mapbox/${style}/static/${lng},${lat},${zoom},0/${width}x${height}@2x?access_token=${mapboxToken}`;
}

/**
 * Get Mapbox Static Image for a bounding box (for segments/polygons)
 */
function getSatelliteBboxUrl(bbox, width = 400, height = 200, style = 'satellite-v9') {
    const mapboxToken = appConfig?.apis?.mapbox?.accessToken;
    if (!mapboxToken) return null;

    // bbox = [minLng, minLat, maxLng, maxLat]
    return `https://api.mapbox.com/styles/v1/mapbox/${style}/static/[${bbox.join(',')}]/${width}x${height}@2x?access_token=${mapboxToken}`;
}
```

### 1.2 Create Mapillary Image Fetch Functions

**File:** `app/index.html` (JavaScript section, near MapillaryAPIClient ~line 17683)

```javascript
/**
 * Fetch nearest Mapillary images for a location
 * @param {number} lat - Latitude
 * @param {number} lng - Longitude
 * @param {number} radius - Search radius in meters (default 152.4 = 500ft)
 * @param {number} limit - Max images to return
 * @returns {Promise<Array>} - Array of image objects with thumbnail URLs
 */
async function fetchMapillaryNearbyImages(lat, lng, radius = 152.4, limit = 4) {
    const token = mapillaryState.accessToken || appConfig?.apis?.mapillary?.accessToken;
    if (!token) {
        console.warn('[Mapillary] No access token configured');
        return [];
    }

    try {
        const bbox = calculateBboxFromPoint(lat, lng, radius);
        const url = `https://graph.mapillary.com/images?access_token=${token}&fields=id,thumb_1024_url,thumb_256_url,captured_at,compass_angle,geometry&bbox=${bbox}&limit=${limit}`;

        const response = await fetch(url);
        if (!response.ok) throw new Error(`Mapillary API error: ${response.status}`);

        const data = await response.json();
        return data.data || [];
    } catch (error) {
        console.error('[Mapillary] Fetch error:', error);
        return [];
    }
}

/**
 * Get single best Mapillary thumbnail for location
 */
async function getMapillaryThumbnailUrl(lat, lng, radius = 152.4) {
    const images = await fetchMapillaryNearbyImages(lat, lng, radius, 1);
    if (images.length > 0) {
        return images[0].thumb_1024_url || images[0].thumb_256_url;
    }
    return null;
}

/**
 * Calculate bounding box from point and radius
 */
function calculateBboxFromPoint(lat, lng, radiusMeters) {
    const latDelta = radiusMeters / 111320;
    const lngDelta = radiusMeters / (111320 * Math.cos(lat * Math.PI / 180));
    return [
        (lng - lngDelta).toFixed(6),
        (lat - latDelta).toFixed(6),
        (lng + lngDelta).toFixed(6),
        (lat + latDelta).toFixed(6)
    ].join(',');
}
```

### 1.3 Create Unified View State Object

**File:** `app/index.html` (State objects section, near line ~17500)

```javascript
// Unified imagery state for all view types
const imageryState = {
    currentLocation: null,
    locationType: null, // 'intersection', 'segment', 'polygon'
    coordinates: { lat: null, lng: null },
    bbox: null, // For segments/polygons

    streetView: {
        available: false,
        thumbnailUrl: null,
        fullUrl: null
    },
    satellite: {
        available: false,
        thumbnailUrl: null
    },
    mapillary: {
        available: false,
        thumbnailUrl: null,
        images: [],
        coverage: 'unknown' // 'available', 'limited', 'none'
    }
};
```

---

## Phase 2: UI Components

### 2.1 Create Tabbed View Component (Reusable)

**File:** `app/index.html` (CSS section, near line ~1112)

```css
/* MULTI-VIEW IMAGERY PANEL STYLES */
.imagery-view-panel {
    border: 1px solid var(--gray-light);
    border-radius: var(--radius);
    overflow: hidden;
    margin-bottom: 0.75rem;
}

.imagery-view-tabs {
    display: flex;
    border-bottom: 1px solid var(--gray-light);
    background: var(--gray-lighter);
}

.imagery-view-tab {
    flex: 1;
    padding: 0.5rem;
    font-size: 0.75rem;
    font-weight: 500;
    text-align: center;
    cursor: pointer;
    border: none;
    background: transparent;
    color: var(--gray);
    transition: all 0.2s;
}

.imagery-view-tab:hover {
    background: var(--gray-light);
}

.imagery-view-tab.active {
    background: white;
    color: var(--primary);
    border-bottom: 2px solid var(--primary);
}

.imagery-view-tab.disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.imagery-view-content {
    position: relative;
    min-height: 120px;
    background: #f8fafc;
}

.imagery-view-pane {
    display: none;
    padding: 0;
}

.imagery-view-pane.active {
    display: block;
}

.imagery-thumb {
    width: 100%;
    height: 140px;
    object-fit: cover;
    cursor: pointer;
    transition: opacity 0.2s;
}

.imagery-thumb:hover {
    opacity: 0.9;
}

.imagery-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 120px;
    color: var(--gray);
    font-size: 0.85rem;
}

.imagery-unavailable {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 120px;
    color: var(--gray);
    font-size: 0.8rem;
    text-align: center;
    padding: 1rem;
}

.imagery-badge {
    position: absolute;
    bottom: 8px;
    left: 8px;
    background: rgba(0,0,0,0.7);
    color: white;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.7rem;
}
```

### 2.2 Create Reusable HTML Component Generator

**File:** `app/index.html` (JavaScript section)

```javascript
/**
 * Generate HTML for multi-view imagery panel
 * @param {string} prefix - Unique prefix for IDs (e.g., 'map', 'cmf', 'warrant')
 * @param {boolean} showStreetView - Whether to show Street View tab
 * @returns {string} HTML string
 */
function generateImageryPanelHTML(prefix, showStreetView = true) {
    const streetViewTab = showStreetView ?
        `<button class="imagery-view-tab active" data-view="streetview" onclick="switchImageryView('${prefix}', 'streetview')">
            📷 Street View
        </button>` : '';

    const streetViewPane = showStreetView ?
        `<div class="imagery-view-pane active" id="${prefix}ViewStreet">
            <img id="${prefix}SvThumb" class="imagery-thumb" alt="Street View" onclick="openStreetViewFor${capitalize(prefix)}()">
            <span class="imagery-badge">📷 Street View</span>
        </div>` : '';

    return `
        <div class="imagery-view-panel" id="${prefix}ImageryPanel">
            <div class="imagery-view-tabs">
                ${streetViewTab}
                <button class="imagery-view-tab ${!showStreetView ? 'active' : ''}" data-view="satellite" onclick="switchImageryView('${prefix}', 'satellite')">
                    🛰️ Satellite
                </button>
                <button class="imagery-view-tab" data-view="mapillary" onclick="switchImageryView('${prefix}', 'mapillary')">
                    🗺️ Mapillary
                </button>
            </div>
            <div class="imagery-view-content">
                ${streetViewPane}
                <div class="imagery-view-pane ${!showStreetView ? 'active' : ''}" id="${prefix}ViewSatellite">
                    <img id="${prefix}SatThumb" class="imagery-thumb" alt="Satellite View" onclick="openSatelliteViewFor${capitalize(prefix)}()">
                    <span class="imagery-badge">🛰️ Satellite</span>
                </div>
                <div class="imagery-view-pane" id="${prefix}ViewMapillary">
                    <img id="${prefix}MapillaryThumb" class="imagery-thumb" alt="Mapillary" onclick="openMapillaryViewFor${capitalize(prefix)}()">
                    <span class="imagery-badge">🗺️ Mapillary</span>
                </div>
                <div class="imagery-loading" id="${prefix}ImageryLoading" style="display:none">
                    <span>⏳ Loading imagery...</span>
                </div>
                <div class="imagery-unavailable" id="${prefix}ImageryUnavailable" style="display:none">
                    <span style="font-size:1.5rem;margin-bottom:0.5rem">📷</span>
                    <span id="${prefix}UnavailableMsg">No imagery available</span>
                </div>
            </div>
        </div>
    `;
}

/**
 * Switch between imagery view tabs
 */
function switchImageryView(prefix, viewType) {
    // Update tab states
    const tabs = document.querySelectorAll(`#${prefix}ImageryPanel .imagery-view-tab`);
    tabs.forEach(tab => {
        tab.classList.toggle('active', tab.dataset.view === viewType);
    });

    // Update pane visibility
    const panes = {
        streetview: document.getElementById(`${prefix}ViewStreet`),
        satellite: document.getElementById(`${prefix}ViewSatellite`),
        mapillary: document.getElementById(`${prefix}ViewMapillary`)
    };

    Object.entries(panes).forEach(([key, pane]) => {
        if (pane) pane.classList.toggle('active', key === viewType);
    });
}
```

---

## Phase 3: Map Tab Integration

### 3.1 Update Map Selected Info Panel HTML

**Location:** `app/index.html` line ~4352-4380

**Replace** the current Street View thumbnail container with the new multi-view panel:

```html
<!-- Before (line 4354-4358): -->
<!-- Street View Thumbnail Preview -->
<div id="mapSvThumbContainer" class="sv-thumb-container" style="display:none">
    <img id="mapSvThumb" class="sv-location-thumb" alt="Street View" onclick="openStreetViewForSelectedLocation()">
    <span class="sv-thumb-badge">📷 Street View</span>
</div>

<!-- After: -->
<!-- Multi-View Imagery Panel -->
<div id="mapImageryContainer" style="display:none">
    <div class="imagery-view-panel" id="mapImageryPanel">
        <div class="imagery-view-tabs" id="mapImageryTabs">
            <button class="imagery-view-tab active" data-view="streetview" onclick="switchMapImageryView('streetview')">📷 Street</button>
            <button class="imagery-view-tab" data-view="satellite" onclick="switchMapImageryView('satellite')">🛰️ Satellite</button>
            <button class="imagery-view-tab" data-view="mapillary" onclick="switchMapImageryView('mapillary')">🗺️ Mapillary</button>
        </div>
        <div class="imagery-view-content">
            <div class="imagery-view-pane active" id="mapViewStreet">
                <img id="mapSvThumb" class="imagery-thumb" alt="Street View" onclick="openStreetViewForSelectedLocation()">
                <span class="imagery-badge">📷 Street View</span>
            </div>
            <div class="imagery-view-pane" id="mapViewSatellite">
                <img id="mapSatThumb" class="imagery-thumb" alt="Satellite" onclick="openSatelliteFullView('map')">
                <span class="imagery-badge">🛰️ Satellite</span>
            </div>
            <div class="imagery-view-pane" id="mapViewMapillary">
                <img id="mapMapillaryThumb" class="imagery-thumb" alt="Mapillary" onclick="openMapillaryViewer('map')">
                <span class="imagery-badge">🗺️ Mapillary</span>
            </div>
            <div class="imagery-loading" id="mapImageryLoading" style="display:none">⏳ Loading...</div>
            <div class="imagery-unavailable" id="mapImageryUnavailable" style="display:none">
                <span>📷</span><span id="mapUnavailableMsg">No imagery available</span>
            </div>
        </div>
    </div>
</div>
```

### 3.2 Update Drawing Selection Panel (Polygon/Circle)

**Location:** `app/index.html` line ~4396-4451

Add satellite and Mapillary views for drawing selections:

```html
<!-- Add after line 4429 (after drawing stats grid) -->
<!-- Drawing Selection Imagery Panel -->
<div id="drawingImageryContainer" style="margin-top:0.75rem">
    <div class="imagery-view-panel" id="drawingImageryPanel">
        <div class="imagery-view-tabs">
            <!-- No Street View for polygon selections -->
            <button class="imagery-view-tab active" data-view="satellite" onclick="switchDrawingImageryView('satellite')">🛰️ Satellite</button>
            <button class="imagery-view-tab" data-view="mapillary" onclick="switchDrawingImageryView('mapillary')">🗺️ Mapillary</button>
        </div>
        <div class="imagery-view-content">
            <div class="imagery-view-pane active" id="drawingViewSatellite">
                <img id="drawingSatThumb" class="imagery-thumb" alt="Satellite" onclick="openSatelliteFullView('drawing')">
                <span class="imagery-badge">🛰️ Selection Area</span>
            </div>
            <div class="imagery-view-pane" id="drawingViewMapillary">
                <img id="drawingMapillaryThumb" class="imagery-thumb" alt="Mapillary" onclick="openMapillaryViewer('drawing')">
                <span class="imagery-badge">🗺️ Mapillary</span>
            </div>
        </div>
    </div>
</div>
```

### 3.3 Create Map Imagery Loading Functions

**File:** `app/index.html` (JavaScript section)

```javascript
/**
 * Load all imagery views for map selection
 * @param {Array} crashes - Crash records for location
 * @param {string} locationType - 'intersection', 'route', or 'polygon'
 */
async function loadMapImagery(crashes, locationType) {
    const container = document.getElementById('mapImageryContainer');
    if (!container) return;

    // Calculate centroid from crashes
    const validCrashes = crashes.filter(c => c[COL.Y] && c[COL.X]);
    if (validCrashes.length === 0) {
        container.style.display = 'none';
        return;
    }

    const lat = validCrashes.reduce((sum, c) => sum + parseFloat(c[COL.Y]), 0) / validCrashes.length;
    const lng = validCrashes.reduce((sum, c) => sum + parseFloat(c[COL.X]), 0) / validCrashes.length;

    // Store coordinates for later use
    mapImageryState.lat = lat;
    mapImageryState.lng = lng;
    mapImageryState.locationType = locationType;

    container.style.display = 'block';

    // Configure tabs based on location type
    const streetTab = document.querySelector('#mapImageryTabs [data-view="streetview"]');
    if (streetTab) {
        if (locationType === 'intersection') {
            streetTab.style.display = '';
            streetTab.classList.add('active');
            document.getElementById('mapViewStreet')?.classList.add('active');
            document.getElementById('mapViewSatellite')?.classList.remove('active');
        } else {
            // Hide Street View for routes/segments
            streetTab.style.display = 'none';
            streetTab.classList.remove('active');
            document.getElementById('mapViewStreet')?.classList.remove('active');
            document.querySelector('#mapImageryTabs [data-view="satellite"]')?.classList.add('active');
            document.getElementById('mapViewSatellite')?.classList.add('active');
        }
    }

    // Load Street View (intersections only)
    if (locationType === 'intersection') {
        const svUrl = getStreetViewThumbnailUrl(lat, lng, 400, 140);
        const svImg = document.getElementById('mapSvThumb');
        if (svImg && svUrl) {
            svImg.src = svUrl;
            svImg.onerror = () => { svImg.style.display = 'none'; };
        }
    }

    // Load Satellite View (all types)
    const satUrl = getSatelliteThumbnailUrl(lat, lng, 400, 140, locationType === 'intersection' ? 18 : 16);
    const satImg = document.getElementById('mapSatThumb');
    if (satImg && satUrl) {
        satImg.src = satUrl;
    }

    // Load Mapillary (async)
    loadMapillaryForLocation('map', lat, lng, locationType === 'intersection' ? 152.4 : 300);
}

/**
 * Load Mapillary imagery for a location
 */
async function loadMapillaryForLocation(prefix, lat, lng, radius = 152.4) {
    const img = document.getElementById(`${prefix}MapillaryThumb`);
    const pane = document.getElementById(`${prefix}ViewMapillary`);

    if (!img || !pane) return;

    try {
        const thumbUrl = await getMapillaryThumbnailUrl(lat, lng, radius);
        if (thumbUrl) {
            img.src = thumbUrl;
            img.style.display = '';
            // Store for opening viewer
            img.dataset.lat = lat;
            img.dataset.lng = lng;
        } else {
            img.style.display = 'none';
            pane.innerHTML = `
                <div class="imagery-unavailable">
                    <span style="font-size:1.5rem">🗺️</span>
                    <span>No Mapillary coverage</span>
                    <a href="https://www.mapillary.com/app?lat=${lat}&lng=${lng}&z=17" target="_blank" style="font-size:0.75rem;color:var(--primary)">Check Mapillary</a>
                </div>
            `;
        }
    } catch (error) {
        console.error('[Mapillary] Load error:', error);
    }
}

// State for map imagery
const mapImageryState = {
    lat: null,
    lng: null,
    locationType: null
};
```

### 3.4 Update Existing Functions

**Modify `updateMapSelectionDisplay()` (~line 34304):**

```javascript
// Replace the existing Street View loading call:
// OLD:
if (selectedMapLocations.length === 1 && stats.crashes && stats.crashes.length > 0 && mapSelectionMode !== 'route') {
    loadMapStreetViewThumbnail(stats.crashes);
}

// NEW:
if (stats.crashes && stats.crashes.length > 0) {
    const locationType = mapSelectionMode === 'route' ? 'route' :
                        selectedMapLocations.length === 1 ? 'intersection' : 'multi';
    loadMapImagery(stats.crashes, locationType);
}
```

---

## Phase 4: CMF Tab Integration

### 4.1 Update CMF Location Summary HTML

**Location:** `app/index.html` line ~9253-9263

**Replace** the Street View thumbnail row:

```html
<!-- Before (line 9253-9263): -->
<!-- Street View Thumbnail Row -->
<div id="cmfSvThumbRow" class="sv-thumb-row" style="display:none;margin-bottom:.75rem">
    <!-- ... existing content ... -->
</div>

<!-- After: -->
<!-- Multi-View Imagery Panel -->
<div id="cmfImageryContainer" style="display:none;margin-bottom:0.75rem">
    <div class="imagery-view-panel" id="cmfImageryPanel">
        <div class="imagery-view-tabs" id="cmfImageryTabs">
            <button class="imagery-view-tab active" data-view="streetview" onclick="switchCMFImageryView('streetview')">📷 Street</button>
            <button class="imagery-view-tab" data-view="satellite" onclick="switchCMFImageryView('satellite')">🛰️ Satellite</button>
            <button class="imagery-view-tab" data-view="mapillary" onclick="switchCMFImageryView('mapillary')">🗺️ Mapillary</button>
        </div>
        <div class="imagery-view-content">
            <div class="imagery-view-pane active" id="cmfViewStreet">
                <img id="cmfSvThumb" class="imagery-thumb" alt="Street View" onclick="openCMFStreetView()">
                <span class="imagery-badge">📷 Street View</span>
            </div>
            <div class="imagery-view-pane" id="cmfViewSatellite">
                <img id="cmfSatThumb" class="imagery-thumb" alt="Satellite" onclick="openSatelliteFullView('cmf')">
                <span class="imagery-badge">🛰️ Satellite</span>
            </div>
            <div class="imagery-view-pane" id="cmfViewMapillary">
                <img id="cmfMapillaryThumb" class="imagery-thumb" alt="Mapillary" onclick="openMapillaryViewer('cmf')">
                <span class="imagery-badge">🗺️ Mapillary</span>
            </div>
        </div>
    </div>
    <div style="font-size:0.75rem;color:#64748b;margin-top:0.25rem;text-align:center">
        Click image to expand • Use tabs to switch views
    </div>
</div>
```

### 4.2 Create CMF Imagery Loading Function

```javascript
/**
 * Load all imagery views for CMF location
 */
async function loadCMFImagery() {
    const container = document.getElementById('cmfImageryContainer');
    if (!container) return;

    const crashes = cmfState.filteredCrashes || cmfState.locationCrashes || [];
    const validCrashes = crashes.filter(c => c[COL.Y] && c[COL.X]);

    if (validCrashes.length === 0) {
        container.style.display = 'none';
        return;
    }

    const lat = validCrashes.reduce((sum, c) => sum + parseFloat(c[COL.Y]), 0) / validCrashes.length;
    const lng = validCrashes.reduce((sum, c) => sum + parseFloat(c[COL.X]), 0) / validCrashes.length;

    // Determine location type
    const isIntersection = cmfState.selectedLocation?.type === 'intersection' ||
                          cmfState.selectedLocation?.name?.includes('/') ||
                          cmfState.selectedLocation?.name?.includes('@');

    // Store coordinates
    cmfImageryState.lat = lat;
    cmfImageryState.lng = lng;
    cmfImageryState.isIntersection = isIntersection;

    container.style.display = 'block';

    // Configure tabs based on location type
    const streetTab = document.querySelector('#cmfImageryTabs [data-view="streetview"]');
    if (streetTab) {
        if (isIntersection) {
            streetTab.style.display = '';
        } else {
            streetTab.style.display = 'none';
            // Switch to satellite as default for segments
            switchCMFImageryView('satellite');
        }
    }

    // Load Street View (intersections only)
    if (isIntersection) {
        const svUrl = getStreetViewThumbnailUrl(lat, lng, 400, 140);
        const svImg = document.getElementById('cmfSvThumb');
        if (svImg && svUrl) svImg.src = svUrl;
    }

    // Load Satellite
    const satUrl = getSatelliteThumbnailUrl(lat, lng, 400, 140, isIntersection ? 18 : 16);
    const satImg = document.getElementById('cmfSatThumb');
    if (satImg && satUrl) satImg.src = satUrl;

    // Load Mapillary
    await loadMapillaryForLocation('cmf', lat, lng, isIntersection ? 152.4 : 300);
}

const cmfImageryState = { lat: null, lng: null, isIntersection: true };

function switchCMFImageryView(viewType) {
    switchImageryView('cmf', viewType);
}
```

### 4.3 Update displayCrashProfile Function

**Modify** `displayCrashProfile()` (~line 61401):

```javascript
// Replace:
loadCMFStreetViewThumbnail();

// With:
loadCMFImagery();
```

---

## Phase 5: Warrants Tab Integration

### 5.1 Add Imagery Panel to Warrant Location Display

**Location:** `app/index.html` line ~10654-10710

Add after the warrant location header:

```html
<!-- Add after line 10657 (after warrantLocationType) -->
<!-- Warrant Imagery Panel -->
<div id="warrantImageryContainer" style="display:none;margin:0.75rem 0">
    <div class="imagery-view-panel" id="warrantImageryPanel">
        <div class="imagery-view-tabs" id="warrantImageryTabs">
            <button class="imagery-view-tab active" data-view="streetview" onclick="switchWarrantImageryView('streetview')">📷 Street</button>
            <button class="imagery-view-tab" data-view="satellite" onclick="switchWarrantImageryView('satellite')">🛰️ Satellite</button>
            <button class="imagery-view-tab" data-view="mapillary" onclick="switchWarrantImageryView('mapillary')">🗺️ Mapillary</button>
        </div>
        <div class="imagery-view-content">
            <div class="imagery-view-pane active" id="warrantViewStreet">
                <img id="warrantSvThumb" class="imagery-thumb" alt="Street View" onclick="openWarrantStreetView()">
                <span class="imagery-badge">📷 Street View</span>
            </div>
            <div class="imagery-view-pane" id="warrantViewSatellite">
                <img id="warrantSatThumb" class="imagery-thumb" alt="Satellite" onclick="openSatelliteFullView('warrant')">
                <span class="imagery-badge">🛰️ Satellite</span>
            </div>
            <div class="imagery-view-pane" id="warrantViewMapillary">
                <img id="warrantMapillaryThumb" class="imagery-thumb" alt="Mapillary" onclick="openMapillaryViewer('warrant')">
                <span class="imagery-badge">🗺️ Mapillary</span>
            </div>
        </div>
    </div>
</div>
```

### 5.2 Create Warrant Imagery Loading Function

```javascript
/**
 * Load all imagery views for Warrants tab location
 */
async function loadWarrantImagery() {
    const container = document.getElementById('warrantImageryContainer');
    if (!container) return;

    // Try multiple sources for coordinates
    let lat, lng;

    // Priority 1: Geocoded location
    if (warrantsState.geocodedLocation?.lat) {
        lat = warrantsState.geocodedLocation.lat;
        lng = warrantsState.geocodedLocation.lng;
    }
    // Priority 2: Polygon centroid
    else if (warrantsState.polygonCentroid) {
        lat = warrantsState.polygonCentroid.lat;
        lng = warrantsState.polygonCentroid.lng;
    }
    // Priority 3: Calculate from crashes
    else if (warrantsState.filteredCrashes?.length > 0) {
        const validCrashes = warrantsState.filteredCrashes.filter(c => c[COL.Y] && c[COL.X]);
        if (validCrashes.length > 0) {
            lat = validCrashes.reduce((sum, c) => sum + parseFloat(c[COL.Y]), 0) / validCrashes.length;
            lng = validCrashes.reduce((sum, c) => sum + parseFloat(c[COL.X]), 0) / validCrashes.length;
        }
    }

    if (!lat || !lng) {
        container.style.display = 'none';
        return;
    }

    // Determine if intersection or segment
    const isIntersection = warrantsState.selectedLocation?.includes('/') ||
                          warrantsState.selectedLocation?.includes('@') ||
                          warrantsState.selectedLocation?.includes(' at ') ||
                          warrantsState.selectedLocation?.includes(' & ');

    warrantImageryState.lat = lat;
    warrantImageryState.lng = lng;
    warrantImageryState.isIntersection = isIntersection;

    container.style.display = 'block';

    // Configure tabs
    const streetTab = document.querySelector('#warrantImageryTabs [data-view="streetview"]');
    if (streetTab) {
        streetTab.style.display = isIntersection ? '' : 'none';
        if (!isIntersection) {
            switchWarrantImageryView('satellite');
        }
    }

    // Load imagery
    if (isIntersection) {
        const svUrl = getStreetViewThumbnailUrl(lat, lng, 400, 140);
        const svImg = document.getElementById('warrantSvThumb');
        if (svImg && svUrl) svImg.src = svUrl;
    }

    const satUrl = getSatelliteThumbnailUrl(lat, lng, 400, 140, isIntersection ? 18 : 16);
    const satImg = document.getElementById('warrantSatThumb');
    if (satImg && satUrl) satImg.src = satUrl;

    await loadMapillaryForLocation('warrant', lat, lng, isIntersection ? 152.4 : 300);
}

const warrantImageryState = { lat: null, lng: null, isIntersection: true };

function switchWarrantImageryView(viewType) {
    switchImageryView('warrant', viewType);
}
```

### 5.3 Update Warrant Location Display Function

**Modify** the warrant location display function (~line 69592):

```javascript
// After showing the warrant location panel, add:
document.getElementById('warrantSelectedLocation').style.display = 'block';
document.getElementById('warrantLocationName').textContent = warrantsState.displayName;

// Add this line:
loadWarrantImagery();
```

---

## Phase 6: Full View Functions

### 6.1 Open Satellite in Full View

```javascript
/**
 * Open satellite view in new tab or modal
 */
function openSatelliteFullView(source) {
    let lat, lng;

    switch (source) {
        case 'map':
            lat = mapImageryState.lat;
            lng = mapImageryState.lng;
            break;
        case 'cmf':
            lat = cmfImageryState.lat;
            lng = cmfImageryState.lng;
            break;
        case 'warrant':
            lat = warrantImageryState.lat;
            lng = warrantImageryState.lng;
            break;
        case 'drawing':
            // Use drawing centroid
            lat = drawingImageryState?.lat;
            lng = drawingImageryState?.lng;
            break;
    }

    if (!lat || !lng) {
        showNotification('No location coordinates available', 'warning');
        return;
    }

    // Open in Google Maps satellite view
    const url = `https://www.google.com/maps/@${lat},${lng},18z/data=!3m1!1e3`;
    window.open(url, '_blank');
}
```

### 6.2 Open Mapillary Viewer

```javascript
/**
 * Open Mapillary viewer for location
 */
function openMapillaryViewer(source) {
    let lat, lng;

    switch (source) {
        case 'map':
            lat = mapImageryState.lat;
            lng = mapImageryState.lng;
            break;
        case 'cmf':
            lat = cmfImageryState.lat;
            lng = cmfImageryState.lng;
            break;
        case 'warrant':
            lat = warrantImageryState.lat;
            lng = warrantImageryState.lng;
            break;
        case 'drawing':
            lat = drawingImageryState?.lat;
            lng = drawingImageryState?.lng;
            break;
    }

    if (!lat || !lng) {
        showNotification('No location coordinates available', 'warning');
        return;
    }

    // Open Mapillary web viewer
    const url = `https://www.mapillary.com/app?lat=${lat}&lng=${lng}&z=17`;
    window.open(url, '_blank');
}
```

---

## Phase 7: Drawing Selection Imagery

### 7.1 Create Drawing Imagery State and Functions

```javascript
const drawingImageryState = {
    lat: null,
    lng: null,
    bbox: null
};

/**
 * Load imagery for drawing selection (polygon/circle)
 */
async function loadDrawingImagery(crashes, centroid) {
    const container = document.getElementById('drawingImageryContainer');
    if (!container) return;

    let lat, lng;

    if (centroid) {
        lat = centroid.lat;
        lng = centroid.lng;
    } else if (crashes && crashes.length > 0) {
        const validCrashes = crashes.filter(c => c[COL.Y] && c[COL.X]);
        if (validCrashes.length > 0) {
            lat = validCrashes.reduce((sum, c) => sum + parseFloat(c[COL.Y]), 0) / validCrashes.length;
            lng = validCrashes.reduce((sum, c) => sum + parseFloat(c[COL.X]), 0) / validCrashes.length;
        }
    }

    if (!lat || !lng) {
        container.style.display = 'none';
        return;
    }

    drawingImageryState.lat = lat;
    drawingImageryState.lng = lng;

    container.style.display = 'block';

    // Load Satellite (use zoom 16 for wider area view)
    const satUrl = getSatelliteThumbnailUrl(lat, lng, 400, 140, 16);
    const satImg = document.getElementById('drawingSatThumb');
    if (satImg && satUrl) satImg.src = satUrl;

    // Load Mapillary with larger radius for polygon areas
    await loadMapillaryForLocation('drawing', lat, lng, 300);
}

function switchDrawingImageryView(viewType) {
    const tabs = document.querySelectorAll('#drawingImageryPanel .imagery-view-tab');
    tabs.forEach(tab => tab.classList.toggle('active', tab.dataset.view === viewType));

    document.getElementById('drawingViewSatellite')?.classList.toggle('active', viewType === 'satellite');
    document.getElementById('drawingViewMapillary')?.classList.toggle('active', viewType === 'mapillary');
}
```

### 7.2 Update Drawing Selection Display Function

**Modify** the drawing selection update function to load imagery:

```javascript
// In updateDrawingSelectionPanel() or similar function:
// After updating crash stats, add:
if (selectedCrashes && selectedCrashes.length > 0) {
    const centroid = drawnShape ? getCentroidFromShape(drawnShape) : null;
    loadDrawingImagery(selectedCrashes, centroid);
}
```

---

## Phase 8: Testing Checklist

### 8.1 Map Tab Tests
- [ ] Select single intersection → All 3 tabs visible, Street View active by default
- [ ] Select route segment → Only Satellite & Mapillary tabs visible
- [ ] Draw polygon → Only Satellite & Mapillary tabs visible
- [ ] Draw circle → Only Satellite & Mapillary tabs visible
- [ ] Click each thumbnail → Opens full view correctly
- [ ] Tab switching works smoothly
- [ ] Graceful fallback when Mapillary has no coverage

### 8.2 CMF Tab Tests
- [ ] Load intersection location → All 3 tabs visible
- [ ] Load route segment → Street View hidden, Satellite default
- [ ] Imagery updates when date filter changes
- [ ] Imagery updates when location changes
- [ ] All open functions work correctly

### 8.3 Warrants Tab Tests
- [ ] Signal warrant form → Imagery panel shows
- [ ] Stop sign warrant form → Imagery panel shows
- [ ] Pedestrian crossing form → Imagery panel shows
- [ ] Roundabout analysis → Imagery panel shows
- [ ] Geocoded location works
- [ ] Polygon selection works

### 8.4 Edge Cases
- [ ] No API token configured → Graceful error message
- [ ] Invalid coordinates → Panel hidden
- [ ] Mapillary rate limited → Show fallback message
- [ ] Slow network → Loading indicator shows

---

## Phase 9: Performance Optimizations

### 9.1 Lazy Loading
- Only load imagery when tab is switched to (except default view)
- Cache loaded imagery URLs in state

### 9.2 Error Handling
- Add error boundaries for each imagery type
- Show "unavailable" state gracefully
- Log errors to console for debugging

### 9.3 Caching
```javascript
const imageryCache = new Map();

function getCachedImagery(key, fetchFn) {
    if (imageryCache.has(key)) {
        return imageryCache.get(key);
    }
    const result = fetchFn();
    imageryCache.set(key, result);
    // Clear cache after 5 minutes
    setTimeout(() => imageryCache.delete(key), 300000);
    return result;
}
```

---

## Summary

### Files Modified
1. `app/index.html` - Main application file

### New Functions (13)
1. `getSatelliteThumbnailUrl()` - Generate Mapbox Static Image URL
2. `getSatelliteBboxUrl()` - Generate bounding box satellite URL
3. `fetchMapillaryNearbyImages()` - Fetch Mapillary images
4. `getMapillaryThumbnailUrl()` - Get best Mapillary thumbnail
5. `calculateBboxFromPoint()` - Helper for bbox calculation
6. `loadMapImagery()` - Load all imagery for Map tab
7. `loadCMFImagery()` - Load all imagery for CMF tab
8. `loadWarrantImagery()` - Load all imagery for Warrants tab
9. `loadDrawingImagery()` - Load imagery for drawing selections
10. `loadMapillaryForLocation()` - Generic Mapillary loader
11. `switchImageryView()` - Tab switching handler
12. `openSatelliteFullView()` - Open satellite in new tab
13. `openMapillaryViewer()` - Open Mapillary viewer

### New CSS Classes (10)
1. `.imagery-view-panel`
2. `.imagery-view-tabs`
3. `.imagery-view-tab`
4. `.imagery-view-content`
5. `.imagery-view-pane`
6. `.imagery-thumb`
7. `.imagery-loading`
8. `.imagery-unavailable`
9. `.imagery-badge`
10. `.imagery-view-tab.disabled`

### State Objects (4)
1. `imageryState` - Global imagery state
2. `mapImageryState` - Map tab specific
3. `cmfImageryState` - CMF tab specific
4. `warrantImageryState` - Warrants tab specific
5. `drawingImageryState` - Drawing selection specific

---

## Estimated Effort

| Phase | Description | Complexity |
|-------|-------------|------------|
| Phase 1 | Core Infrastructure | Medium |
| Phase 2 | UI Components | Medium |
| Phase 3 | Map Tab Integration | High |
| Phase 4 | CMF Tab Integration | Medium |
| Phase 5 | Warrants Tab Integration | Medium |
| Phase 6 | Full View Functions | Low |
| Phase 7 | Drawing Selection | Medium |
| Phase 8 | Testing | High |
| Phase 9 | Performance | Low |

**Total: ~40-50 code changes across the single index.html file**
