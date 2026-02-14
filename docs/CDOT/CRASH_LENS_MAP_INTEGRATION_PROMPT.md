# CRASH LENS Integration Prompt — Map-Centered Jurisdiction Views

## Overview
The JSON file `us_states_dot_districts_mpos.json` now includes **map center points, zoom levels, and bounding boxes** for every state, DOT district, and MPO. When a user selects a jurisdiction, the map should automatically fly/pan to show that jurisdiction's boundaries with optimal framing.

---

## JSON Structure (New Fields)

### State Level
```json
{
  "VA": {
    "name": "Virginia",
    "fips": "51",
    "dot_name": "VDOT",
    "mapCenter": { "lat": 37.769337, "lng": -78.169968 },
    "mapZoom": 7,
    "dot_districts": [...],
    "mpos": [...]
  }
}
```

### DOT District Level
```json
{
  "id": "VA-1",
  "name": "Bristol District",
  "hq": "Bristol",
  "mapCenter": { "lat": 36.85, "lng": -81.90 },
  "mapZoom": 8,
  "mapBounds": {
    "sw": [36.50, -83.50],
    "ne": [37.40, -80.80]
  },
  "counties": ["Bland", "Buchanan", ...]
}
```

### MPO Level
```json
{
  "id": "VA-MPO-1",
  "name": "HRTPO (Hampton Roads TPO)",
  "mapCenter": { "lat": 36.85, "lng": -76.29 },
  "mapZoom": 10,
  "counties": ["Chesapeake", "Hampton", ...]
}
```

---

## Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `mapCenter` | `{lat, lng}` | Geographic center point for the jurisdiction |
| `mapZoom` | `number` | Recommended zoom level (Leaflet/Google Maps scale: 4=continent, 7=state, 9=region, 10=metro, 12=city) |
| `mapBounds` | `{sw: [lat,lng], ne: [lat,lng]}` | Bounding box (DOT districts only). SW = southwest corner, NE = northeast corner |

---

## Implementation Guide

### 1. Map Viewport Change on Selection

When the user selects a jurisdiction from any dropdown, update the map view:

```javascript
function updateMapView(jurisdiction) {
  // Priority: use bounds if available (best fit), else center+zoom
  if (jurisdiction.mapBounds) {
    // Fit to bounding box — ensures all counties are visible
    const bounds = L.latLngBounds(
      L.latLng(jurisdiction.mapBounds.sw[0], jurisdiction.mapBounds.sw[1]),
      L.latLng(jurisdiction.mapBounds.ne[0], jurisdiction.mapBounds.ne[1])
    );
    map.flyToBounds(bounds, {
      padding: [50, 50],      // 50px padding for UI elements
      duration: 1.2,          // smooth animation
      maxZoom: jurisdiction.mapZoom || 12
    });
  } else if (jurisdiction.mapCenter) {
    // Fly to center point with recommended zoom
    map.flyTo(
      [jurisdiction.mapCenter.lat, jurisdiction.mapCenter.lng],
      jurisdiction.mapZoom || 10,
      { duration: 1.2 }
    );
  }
}
```

### 2. View Level → Map Behavior Matrix

| View Level | On Selection | Map Action |
|------------|-------------|------------|
| **Federal** | (no selection needed) | `flyTo([39.5, -98.35], 4)` — Continental US overview |
| **State** | State dropdown changes | `flyTo(state.mapCenter, state.mapZoom)` |
| **Region** | District dropdown changes | `flyToBounds(district.mapBounds)` or `flyTo(district.mapCenter, district.mapZoom)` |
| **MPO** | MPO dropdown changes | `flyTo(mpo.mapCenter, mpo.mapZoom)` |
| **County** | County dropdown changes | Use existing county centroid logic, zoom 11-12 |

### 3. Cascade Behavior

When the user changes the **state** dropdown:
1. Map flies to the new state's center/zoom
2. Region and MPO dropdowns repopulate with that state's data
3. No district/MPO is selected yet — map shows full state

When the user then selects a **district** or **MPO**:
1. Map smoothly flies to the district/MPO view
2. Crash data filters to the counties in that jurisdiction
3. Scope label updates: "Scope: Bristol District" or "Scope: HRTPO"

### 4. Animation Settings (UX Best Practice)

```javascript
// Smooth, professional transitions
const MAP_ANIMATION_OPTIONS = {
  duration: 1.2,           // seconds for fly animation
  easeLinearity: 0.25,    // smooth deceleration
  padding: [50, 50],       // pixels of padding around bounds
  maxZoom: 14,             // never zoom closer than this
  animate: true
};

// For Leaflet:
map.flyTo(center, zoom, MAP_ANIMATION_OPTIONS);
map.flyToBounds(bounds, MAP_ANIMATION_OPTIONS);

// For Google Maps:
map.panTo(center);
map.setZoom(zoom);
// Or use smooth transition:
map.fitBounds(bounds, { padding: MAP_ANIMATION_OPTIONS.padding });
```

### 5. District Boundary Highlighting (Optional Enhancement)

If you want to visually highlight the selected jurisdiction on the map:

```javascript
// Draw boundary rectangle for districts with mapBounds
function highlightBounds(jurisdiction) {
  // Remove previous highlight
  if (window.currentBoundary) {
    map.removeLayer(window.currentBoundary);
  }
  
  if (jurisdiction.mapBounds) {
    window.currentBoundary = L.rectangle(
      [jurisdiction.mapBounds.sw, jurisdiction.mapBounds.ne],
      {
        color: '#2563eb',       // blue border
        weight: 2,
        fillColor: '#3b82f6',
        fillOpacity: 0.08,
        dashArray: '8 4'
      }
    ).addTo(map);
  }
}
```

### 6. Dropdown Population (Updated from Original Prompt)

```javascript
function populateRegionDropdown(stateCode) {
  const state = statesData[stateCode];
  const select = document.getElementById('regionSelect');
  select.innerHTML = `<option value="">Select a ${state.dot_name} District...</option>`;
  
  state.dot_districts.forEach(district => {
    const opt = document.createElement('option');
    opt.value = district.id;
    opt.textContent = `${district.name} (${district.counties.length} counties)`;
    // Store geo data on the option element for quick access
    opt.dataset.lat = district.mapCenter?.lat;
    opt.dataset.lng = district.mapCenter?.lng;
    opt.dataset.zoom = district.mapZoom;
    opt.dataset.bounds = district.mapBounds ? JSON.stringify(district.mapBounds) : '';
    select.appendChild(opt);
  });
}

function populateMPODropdown(stateCode) {
  const state = statesData[stateCode];
  const select = document.getElementById('mpoSelect');
  select.innerHTML = `<option value="">Select an MPO...</option>`;
  
  state.mpos.forEach(mpo => {
    const opt = document.createElement('option');
    opt.value = mpo.id;
    opt.textContent = `${mpo.name} (${mpo.counties.length} counties)`;
    opt.dataset.lat = mpo.mapCenter?.lat;
    opt.dataset.lng = mpo.mapCenter?.lng;
    opt.dataset.zoom = mpo.mapZoom;
    select.appendChild(opt);
  });
}
```

### 7. Event Handlers

```javascript
// State selection changed
document.getElementById('stateSelect').addEventListener('change', (e) => {
  const stateCode = e.target.value;
  const state = statesData[stateCode];
  
  if (state) {
    // Fly map to state
    updateMapView(state);
    
    // Repopulate dropdowns
    populateRegionDropdown(stateCode);
    populateMPODropdown(stateCode);
    
    // Update scope label
    updateScopeLabel(`State: ${state.name}`);
  }
});

// Region (District) selection changed
document.getElementById('regionSelect').addEventListener('change', (e) => {
  const districtId = e.target.value;
  if (!districtId) return;
  
  const district = findDistrictById(districtId);
  if (district) {
    updateMapView(district);
    highlightBounds(district);
    filterCrashDataByCounties(district.counties);
    updateScopeLabel(`Region: ${district.name}`);
  }
});

// MPO selection changed
document.getElementById('mpoSelect').addEventListener('change', (e) => {
  const mpoId = e.target.value;
  if (!mpoId) return;
  
  const mpo = findMPOById(mpoId);
  if (mpo) {
    updateMapView(mpo);
    filterCrashDataByCounties(mpo.counties);
    updateScopeLabel(`MPO: ${mpo.name}`);
  }
});
```

---

## Data Coverage Summary

| Level | Count | With mapCenter | With mapBounds |
|-------|-------|---------------|----------------|
| States | 51 | 51 (100%) | — |
| DOT Districts | 361 | 361 (100%) | 361 (100%) |
| MPOs | 413 | 413 (100%) | — |

### Zoom Level Guidelines
- **4** — Continental US (Federal view)
- **6** — Large states (TX, CA, AK)
- **7** — Medium states (most states)
- **8** — DOT districts / large regions
- **9** — Metro areas / multi-county MPOs
- **10** — Single-metro MPOs (most common)
- **11-12** — Small MPOs / individual counties

---

## Testing Checklist

- [ ] Selecting a state flies to state center at correct zoom
- [ ] Selecting a DOT district flies to district bounds (smooth animation)
- [ ] Selecting an MPO flies to MPO metro center at correct zoom
- [ ] Changing state → changing district gives smooth sequential animation
- [ ] Federal view resets to continental US zoom level 4
- [ ] Virginia districts match expected locations (Bristol = SW, NOVA = N)
- [ ] Texas districts (25) all show distinct centers
- [ ] Florida MPOs (27) all show correct metro locations
- [ ] Small states (RI, DE, CT) zoom appropriately (not too far out)
- [ ] Large states (AK, TX, CA) zoom appropriately (not too close)
- [ ] Mobile: map viewport adjusts properly on smaller screens
- [ ] Map padding doesn't clip behind sidebar/header UI elements
- [ ] Boundary highlight rectangle (if implemented) clears on new selection
