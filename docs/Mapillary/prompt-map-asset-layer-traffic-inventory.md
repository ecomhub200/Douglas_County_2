# Claude Code Prompt: Map Tab — Add TI & BTS Data to Polygon/Circle Selection and PDF Report

## Overview

The Crash Lens application's **Map tab** lets users draw a polygon, circle, or measure line to select an area and analyze crashes within it. Currently, the `selectCrashesInDrawing()` function (line ~50303 in `app/index.html`) ONLY extracts crash data — it does NOT capture Traffic Inventory (TI) signs or BTS Federal data layers (bridges, railroad crossings, transit stops, HPMS roads) that fall within the drawn shape.

The **PDF export report** (`generateCrashSelectionPDF()` at line ~51917) also only shows crash analysis. Users need location context (speed limits, signs, bridges, crossings, signals) to understand the infrastructure environment around crashes.

There are **5 tasks** to implement. All changes go primarily in `app/index.html`.

---

## TASK A: Extract TI & BTS Data Within Drawn Polygon/Circle

### Current State
- `selectCrashesInDrawing(shapeType, shapeData)` at line ~50303 iterates `getFilteredMapPoints()` (crash data only) and populates `selectedCrashesFromDrawing[]`
- `trafficInventoryLayerState.data` (line ~125355) holds ALL loaded TI items with fields: `id, mutcd, name, cls, speed, lat, lon, first_seen, signal_heads, _cat, _parent`
- BTS data is cached per-layer in the `btsLayerState` object after being fetched via `btsFetchLayerData()` (line ~123365) from ArcGIS FeatureServer endpoints
- Neither TI nor BTS data is filtered by the drawn shape

### Fix Required

1. **Create `selectTIInDrawing(shapeType, shapeData)`** — a new function that filters `trafficInventoryLayerState.data` to find all TI items within the drawn shape:
   ```javascript
   let selectedTIFromDrawing = []; // NEW global, parallel to selectedCrashesFromDrawing

   function selectTIInDrawing(shapeType, shapeData) {
       selectedTIFromDrawing = [];
       if (!trafficInventoryLayerState.data || !trafficInventoryLayerState.data.length) return;

       trafficInventoryLayerState.data.forEach(item => {
           if (!item.lat || !item.lon) return;
           const latlng = L.latLng(item.lat, item.lon);
           let isInside = false;

           if (shapeType === 'polygon') {
               isInside = isPointInPolygon(latlng, drawingPoints);
           } else if (shapeType === 'circle') {
               isInside = shapeData.center.distanceTo(latlng) <= shapeData.radius;
           } else if (shapeType === 'measure') {
               isInside = isPointNearPolyline(latlng, shapeData.points, shapeData.bufferMeters);
           }

           if (isInside) selectedTIFromDrawing.push(item);
       });

       console.log(`[Drawing] ${selectedTIFromDrawing.length} TI items within selection`);
   }
   ```

2. **Create `selectBTSInDrawing(shapeType, shapeData)`** — filters cached BTS GeoJSON features within the drawn shape:
   ```javascript
   let selectedBTSFromDrawing = {}; // { bridges: [], railroadCrossings: [], transitStops: [], transitRoutes: [], hpmsRoads: [] }

   function selectBTSInDrawing(shapeType, shapeData) {
       selectedBTSFromDrawing = { bridges: [], railroadCrossings: [], transitStops: [], transitRoutes: [], hpmsRoads: [] };

       // Map BTS_ENDPOINTS keys to selectedBTSFromDrawing keys
       const keyMap = {
           hpms: 'hpmsRoads',
           bridges: 'bridges',
           railroadCrossings: 'railroadCrossings',
           transitStops: 'transitStops',
           transitRoutes: 'transitRoutes'
       };

       Object.entries(BTS_ENDPOINTS).forEach(([layerKey, endpoint]) => {
           const targetKey = keyMap[layerKey];
           if (!targetKey) return;

           // Get cached GeoJSON features for this BTS layer
           const cachedGeojson = btsLayerState[layerKey]?.geojson;
           if (!cachedGeojson || !cachedGeojson.features) return;

           cachedGeojson.features.forEach(feature => {
               // For point features
               if (feature.geometry.type === 'Point') {
                   const [lng, lat] = feature.geometry.coordinates;
                   const latlng = L.latLng(lat, lng);
                   let isInside = false;

                   if (shapeType === 'polygon') isInside = isPointInPolygon(latlng, drawingPoints);
                   else if (shapeType === 'circle') isInside = shapeData.center.distanceTo(latlng) <= shapeData.radius;
                   else if (shapeType === 'measure') isInside = isPointNearPolyline(latlng, shapeData.points, shapeData.bufferMeters);

                   if (isInside) selectedBTSFromDrawing[targetKey].push(feature.properties);
               }
               // For line features (HPMS roads, transit routes) — check if any vertex is inside
               else if (feature.geometry.type === 'LineString' || feature.geometry.type === 'MultiLineString') {
                   const coords = feature.geometry.type === 'MultiLineString'
                       ? feature.geometry.coordinates.flat()
                       : feature.geometry.coordinates;
                   const intersects = coords.some(([lng, lat]) => {
                       const latlng = L.latLng(lat, lng);
                       if (shapeType === 'polygon') return isPointInPolygon(latlng, drawingPoints);
                       if (shapeType === 'circle') return shapeData.center.distanceTo(latlng) <= shapeData.radius;
                       if (shapeType === 'measure') return isPointNearPolyline(latlng, shapeData.points, shapeData.bufferMeters);
                       return false;
                   });
                   if (intersects) selectedBTSFromDrawing[targetKey].push(feature.properties);
               }
           });
       });

       console.log('[Drawing] BTS within selection:', Object.entries(selectedBTSFromDrawing).map(([k,v]) => `${k}: ${v.length}`).join(', '));
   }
   ```

3. **Call both new functions from `selectCrashesInDrawing()`** — at the end of the existing function (after line ~50328), add:
   ```javascript
   // Also extract TI and BTS data within the shape
   selectTIInDrawing(shapeType, shapeData);
   selectBTSInDrawing(shapeType, shapeData);
   ```

4. **Important**: If `trafficInventoryLayerState.data` is empty when the user draws (TI not yet loaded), the function should attempt to load TI data first using the existing `loadTrafficInventoryForMap()` function (line ~125603), then filter. Add a check:
   ```javascript
   if (!trafficInventoryLayerState.loaded && !trafficInventoryLayerState.loading) {
       await loadTrafficInventoryForMap();
   }
   ```
   This means `selectCrashesInDrawing` may need to become async, or the TI/BTS extraction can run after the panel is shown and update it asynchronously.

### Key Data References
- TI item fields: `{ id, mutcd, name, cls, speed, lat, lon, first_seen, signal_heads, _cat, _parent }`
- `_cat` values: `ti_stop`, `ti_speed`, `ti_turn`, `ti_parking`, `ti_signals_reg`, `ti_curves`, `ti_intersections`, `ti_advance`, `ti_lanes_road`, `ti_crossings`, `ti_supplemental`, `ti_routes`, `ti_destination`, `ti_services`, `ti_school`, `ti_object_marker`, `ti_marking`, `ti_infra_signals`, `ti_infra_safety`, `ti_infra_street_lights`, `ti_infra_hydrants`, `ti_infra_manholes`, `ti_infra_utilities`
- `_parent` values: `speed`, `regulatory`, `warning`, `guide`, `school`, `object_marker`, `infra`, `marking`
- BTS endpoints (line ~123240): `hpms` (AADT roads), `bridges`, `railroadCrossings`, `transitStops`, `transitRoutes`
- BTS features have `feature.properties` with fields defined in `BTS_ENDPOINTS[key].fields` (line ~123240-123356)
- Existing point-in-polygon: `isPointInPolygon(latlng, drawingPoints)` at line ~50331
- Existing point-near-polyline: `isPointNearPolyline(latlng, points, bufferMeters)` for measure tool

---

## TASK B: Add TI & BTS Data to the PDF Export Report

### Current State
- `getSelectionPDFData()` at line ~51690 assembles crash statistics only
- `generateCrashSelectionPDF()` at line ~51917 creates a multi-page PDF with: cover/summary, collision types, temporal analysis, satellite view + Mapillary assets
- Page 4 already has a "Satellite View & Roadway Assets" section that fetches Mapillary street-level assets via `fetchAssetsForPolygonPDF()` (line ~52457)
- No TI or BTS data is included in the PDF

### Fix Required

1. **Add TI summary data to `getSelectionPDFData()`** — after the existing crash statistics (around line ~51888), add a new section:
   ```javascript
   // TI Location Context
   const tiData = selectedTIFromDrawing || [];
   const btsData = selectedBTSFromDrawing || {};

   // Speed limits in area
   const speedItems = tiData.filter(i => i._cat === 'ti_speed' || i._parent === 'speed');
   const speedValues = [...new Set(speedItems.map(i => parseInt(i.speed)).filter(Boolean))].sort((a,b) => a - b);
   const speedCounts = {};
   speedItems.forEach(i => {
       const s = parseInt(i.speed);
       if (s) speedCounts[s] = (speedCounts[s] || 0) + 1;
   });

   // Categorize TI items by parent
   const tiByParent = {};
   tiData.forEach(i => {
       const parent = i._parent || 'other';
       if (!tiByParent[parent]) tiByParent[parent] = [];
       tiByParent[parent].push(i);
   });

   pdfData.locationContext = {
       totalTIItems: tiData.length,
       speedValues,
       speedCounts,
       tiByParent,
       regulatoryCount: (tiByParent.regulatory || []).length,
       warningCount: (tiByParent.warning || []).length,
       schoolCount: (tiByParent.school || []).length,
       signalCount: tiData.filter(i => i._cat === 'ti_infra_signals').length,
       bridges: btsData.bridges || [],
       railroadCrossings: btsData.railroadCrossings || [],
       transitStops: btsData.transitStops || [],
       transitRoutes: btsData.transitRoutes || [],
       hpmsRoads: btsData.hpmsRoads || []
   };
   ```

2. **Add a new PDF page "Location Context — Traffic Inventory & Infrastructure"** in `generateCrashSelectionPDF()` — after the existing satellite/assets page (after ~line 52700). This page should include:

   **Section 1: Posted Speed Limits**
   - List each speed value with count: "25 mph (2,240 signs) | 35 mph (676 signs) | 45 mph (476 signs)..."
   - If multiple speed limits exist, highlight the **predominant speed limit**
   - Visual: small speed-limit-sign icons next to each value (use the existing `createTISpeedIcon()` at line ~124865 — convert SVG to data URL for jsPDF)

   **Section 2: Traffic Control Summary Table**
   | Category | Count | Key Items |
   |----------|-------|-----------|
   | Regulatory Signs | XX | Stop (XX), Yield (XX), No U-Turn (XX) |
   | Warning Signs | XX | Stop Ahead (XX), Curves (XX), RR Crossing (XX) |
   | Traffic Signals | XX | Signal heads consolidated |
   | School Zones | XX | School speed, school crossing |

   **Section 3: Federal Infrastructure (BTS)**
   - **Bridges**: Count + condition ratings (if available from NBI fields: `DECK_COND_058`, `SUPERSTRUCTURE_COND_059`)
   - **Railroad Crossings**: Count + warning device types (from `WarnDev` field)
   - **Transit Stops**: Count + agency names
   - **HPMS Roads**: AADT values (from `AADT` field), functional classification

   **Section 4: Location Context Summary**
   - One-paragraph narrative summarizing the infrastructure environment, e.g.: "The study area contains 15 speed limit signs (predominantly 35 mph), 3 traffic signals, 1 railroad crossing with gates, and 2 transit stops. The area is served by roads with AADT volumes ranging from 5,000 to 25,000."

### Key References
- jsPDF is already loaded and used throughout `generateCrashSelectionPDF()`
- Existing helper: `drawSectionHeader(y, title)` for section headers
- Existing helper: `addFooter()` for page footers
- Existing helper: `checkPageBreak(y, needed)` for page overflow
- BTS field names are in `BTS_ENDPOINTS[key].fields` (lines 123240-123356):
  - Bridges: `STRUCTURE_NUMBER_008`, `YEAR_BUILT_027`, `ADT_029`, `DECK_COND_058`, `SUPERSTRUCTURE_COND_059`
  - Railroad: `ReasonID`, `WarnDev`, `Highway`, `TotalCrashes5Yr`
  - Transit Stops: `stop_name`, `AgencyName`, `routes_served`, `WheelchairBoarding`
  - HPMS: `AADT`, `ROUTE_NUMBER`, `F_SYSTEM` (functional class), `NHS` (national highway system)

---

## TASK C: Auto-Load TI & BTS Data When User Draws Polygon/Circle

### Current State
- Drawing mode is activated via `enableDKPolygonMode()` / `enableDKCircleMode()` / `enableMeasureMode()`
- TI layers are toggled manually via the Asset Layers panel checkboxes
- BTS layers are toggled manually via the BTS section of the Asset Layers panel
- If TI data hasn't been loaded yet (`trafficInventoryLayerState.loaded === false`), the extraction in Task A would return nothing

### Fix Required

1. **Auto-load TI data (background, no visual rendering)** when the user activates any drawing mode. In each of these functions — `enableDKPolygonMode()`, `enableDKCircleMode()`, `enableMeasureMode()` — add at the start:
   ```javascript
   // Pre-load TI data in background for polygon selection analysis
   if (!trafficInventoryLayerState.loaded && !trafficInventoryLayerState.loading) {
       loadTrafficInventoryForMap().catch(err => {
           console.warn('[Drawing] Could not pre-load TI data:', err);
       });
   }
   ```
   This loads the data into `trafficInventoryLayerState.data` without rendering any map layers. The visual layers remain controlled by the Asset Panel checkboxes.

2. **Pre-fetch BTS data for the viewport** — if BTS layers haven't been fetched yet for the current jurisdiction, trigger background fetching. The BTS data requires a bounding box — use the current map viewport bounds:
   ```javascript
   // Pre-fetch BTS layers in background
   const bounds = crashMap.getBounds();
   const btsBounds = {
       north: bounds.getNorth(), south: bounds.getSouth(),
       east: bounds.getEast(), west: bounds.getWest()
   };
   Object.entries(BTS_ENDPOINTS).forEach(([key, endpoint]) => {
       if (!btsLayerState[key]?.geojson) {
           btsFetchLayerData(endpoint, btsBounds).then(geojson => {
               if (!btsLayerState[key]) btsLayerState[key] = {};
               btsLayerState[key].geojson = geojson;
           }).catch(() => {});
       }
   });
   ```

3. **Do NOT visually toggle layers on/off** — the goal is data availability, not visual rendering. The map layers remain in whatever state the user set them. Only the data arrays are populated for extraction.

### Important: Check `btsLayerState` Structure
Before implementing, verify how `btsLayerState` is structured. Search for `btsLayerState` in `app/index.html` to find where cached GeoJSON is stored. The BTS fetching in `addBTSLayer()` (line ~123550) caches data — make sure the background fetch stores it in the same cache location so `selectBTSInDrawing()` can access it.

---

## TASK D: Fix Speed Limit Layer Display in Map Asset Panel

### Current State
- The Map tab's `TI_MAP_CATEGORIES` has a `ti_speed` category with `isSpeedParent: true` (line ~125011)
- Speed sub-categories are built dynamically in `classifyTIItems()` (line ~125728-125737) based on actual speed values found in the data
- `addTISpeedLayer(speed)` at line ~126044 creates markers with `createTISpeedIcon(item.speed)` (line ~124865)
- The Inventory Manager has its own `createSpeedIcon()` (line ~328 of `inventory-manager.html`) that works correctly
- **Problem**: Some categories show 0 count because the classification logic in `TI_MAP_CATEGORIES[].match()` functions don't properly handle items with MUTCD = "N/A" (78% of the 55,000+ items). The existing prompt `claude-prompt-fix-map-asset-layers.md` covers this in detail.

### Fix Required

1. **Apply the classification fix from `claude-prompt-fix-map-asset-layers.md`** — that prompt has the full breakdown. The core issue: the `match()` functions in `TI_MAP_CATEGORIES` check MUTCD codes first, but 43,115 items have `mutcd: "N/A"` and need to be classified by `cls` (class) and `name` fields instead.

2. **Reference the Inventory Manager's `getCategory()` function** (line ~378 of `inventory-manager.html`) as the ground truth:
   ```javascript
   function getCategory(row) {
       const cls = (row.class || '').toLowerCase(), name = (row.name || '');
       if (name.startsWith('Speed') && !cls.includes('school')) return 'speed';
       if (cls.includes('school') || name.includes('School')) return 'school';
       if (cls.startsWith('regulatory')) return 'reg';
       if (cls.startsWith('warning')) return 'warn';
       if (cls.startsWith('information')) return 'guide';
       if (cls.startsWith('marking')) return 'mark';
       if (cls.includes('traffic-light') || name.includes('Signal')) return 'infra';
       return 'infra';
   }
   ```
   The Map tab's `classifyTIItems()` fallback logic (lines ~125744-125815) should match this priority order.

3. **Verify speed icon rendering** — the existing `createTISpeedIcon(speed)` at line ~124865 creates a white rectangle SVG with "SPEED LIMIT" and the number. Verify it renders at the right size in the marker cluster. The Inventory Manager uses 24×28 px for panel icons and 28×32 px for map markers. Ensure the Map tab uses similar sizing.

4. **Ensure individual speed toggles work** — the panel's `toggleTISpeedLayer(speed, show)` at line ~126156 should correctly add/remove only that specific speed value's markers. Verify `trafficInventoryLayerState.speedCategories[speed]` is properly populated during classification.

5. **Expected counts (Henrico County reference)**: Speed: 3,740 | Regulatory: 7,815 | Warning: 366 | Guide: 99 | Infrastructure: 43,115 | Marking: 3,447. If the Map tab shows significantly different numbers, the classification is wrong.

---

## TASK E: Make TI Data Loading Jurisdiction-Agnostic

### Current State
- `loadTrafficInventoryForMap()` at line ~125603 already constructs a dynamic R2 URL using the active jurisdiction's state and key
- Line ~125622: `const tiUrl = r2Prefix + '/' + jurisdictionKey + '/traffic-inventory.csv'` where `r2Prefix` comes from `appConfig.states[stateKey].r2Prefix` (e.g., `https://data.aicreatesai.com/virginia`)
- The function gets the active jurisdiction via `getActiveJurisdictionId()` and `_getActiveStateKey()`
- **This should already be jurisdiction-agnostic** if the state/jurisdiction config is correct

### Verify & Fix

1. **Test with different jurisdictions** — change jurisdiction in the Upload Data tab and verify TI data reloads for the new jurisdiction. The data should clear and reload:
   ```javascript
   // In loadTrafficInventoryForMap(), ensure data is cleared on jurisdiction change
   trafficInventoryLayerState.data = [];
   trafficInventoryLayerState.loaded = false;
   trafficInventoryLayerState.categories = {};
   trafficInventoryLayerState.speedCategories = {};
   ```

2. **Listen for jurisdiction changes** — verify that when `saveJurisdictionSelection()` or `handleStateSelection()` is called (these trigger jurisdiction sync to iframes), the Map tab's TI data also reloads. Search for where these sync functions are called and ensure `loadTrafficInventoryForMap()` is triggered or the TI state is reset so next access reloads.

3. **Match the Inventory Manager's pattern** — `inventory-manager.html` loads data via:
   - R2 public URL: `https://data.aicreatesai.com`
   - Key: `{state}/{county}/traffic-inventory.csv`
   - Falls back to IndexedDB cache if fetch fails

   The Map tab's `loadTrafficInventoryForMap()` should follow the same pattern. Verify the URL construction matches.

4. **Handle the "reuse from signDefState" optimization** — line ~125613 checks `if (signDefState && signDefState.assets && signDefState.assets.length)` to avoid re-fetching if the Sign Deficiency tab already loaded the same data. Ensure this cross-tab data sharing still works when jurisdictions change (i.e., `signDefState` is cleared when jurisdiction changes).

---

## Architecture & Constraints

| Constraint | Detail |
|------------|--------|
| Primary file | `app/index.html` (147,128 lines — all changes here) |
| Drawing functions | Lines 49918-50301 (activation, preview, finish) |
| Crash extraction | `selectCrashesInDrawing()` at line 50303 |
| PDF generation | `generateCrashSelectionPDF()` at line 51917 |
| PDF data assembly | `getSelectionPDFData()` at line 51690 |
| TI state object | `trafficInventoryLayerState` at line 125355 |
| TI loading | `loadTrafficInventoryForMap()` at line 125603 |
| TI classification | `classifyTIItems()` at line 125705 |
| TI category definitions | `TI_MAP_CATEGORIES` at line 124993 |
| Speed icon | `createTISpeedIcon(speed)` at line 124865 |
| Add TI layer to map | `addTIMapLayer()` at line 125935, `addTISpeedLayer()` at line 126044 |
| BTS endpoints | `BTS_ENDPOINTS` at line 123240 |
| BTS fetch | `btsFetchLayerData()` at line 123365 |
| BTS layer add | `addBTSLayer()` at line 123550 |
| Point-in-polygon | `isPointInPolygon()` at line 50331 |
| Existing Mapillary asset fetch for PDF | `fetchAssetsForPolygonPDF()` called at line 52457 |
| Panel update | `updateMapAssetPanel()` at line 128300 |
| Panel HTML builder | `buildTIAssetPanelHTML()` at line 126475 |

## Key Globals to Add

```javascript
let selectedTIFromDrawing = [];       // TI items within drawn shape
let selectedBTSFromDrawing = {};      // BTS features within drawn shape
```

## Do NOT Break

- Existing crash extraction (`selectCrashesInDrawing` must still populate `selectedCrashesFromDrawing`)
- Existing PDF pages (cover, collision types, temporal, satellite/Mapillary assets)
- Existing TI layer toggling in the Asset Panel
- Existing BTS layer display and caching
- Existing jurisdiction sync to iframes (validator, traffic-inventory, inventory-manager, asset-deficiency)
- Map performance (don't render 55,000 extra markers — only extract data into arrays)

## Testing Checklist

- [ ] Draw a polygon around an area → `selectedTIFromDrawing` contains TI items within the shape
- [ ] Draw a circle → same extraction works for circle geometry
- [ ] Use measure tool → same extraction works within the buffer zone
- [ ] PDF export includes a new "Location Context" page after the existing pages
- [ ] PDF shows posted speed limits with counts (e.g., "25 mph: 12 signs, 35 mph: 8 signs")
- [ ] PDF shows regulatory/warning/signal counts in a summary table
- [ ] PDF shows BTS data: bridges (with condition), railroad crossings, transit stops
- [ ] PDF includes a brief narrative summary of the infrastructure environment
- [ ] TI data auto-loads in background when drawing mode is activated (no visual layer change)
- [ ] BTS data pre-fetches in background when drawing mode is activated
- [ ] Speed limit layer icons render correctly (white rectangle with "SPEED LIMIT" + number)
- [ ] Individual speed values are toggleable in the Asset Panel (25 mph, 35 mph, etc.)
- [ ] Category counts match Inventory Manager's counts (not showing 0 for populated categories)
- [ ] Items with MUTCD = "N/A" are classified correctly by `cls`/`name` fields
- [ ] Changing jurisdiction reloads TI data for the new jurisdiction
- [ ] R2 URL pattern: `https://data.aicreatesai.com/{state}/{county}/traffic-inventory.csv` is built dynamically
- [ ] No console errors during any of the above operations
- [ ] Existing functionality (crash layers, heatmaps, other tabs) unaffected
- [ ] PDF doesn't crash if TI or BTS data is empty/unavailable (graceful fallback)

## Reference Files

| File | Purpose |
|------|---------|
| `app/index.html` | Main app — ALL changes go here |
| `app/inventory-manager.html` | Reference for `getCategory()`, speed icons, R2 loading |
| `app/traffic-inventory.html` | Reference for `createSpeedIcon()`, jurisdiction sync |
| `scripts/crash_lens_asset_inventory_manager_v10.html` | Standalone version of Inventory Manager |
| `docs/Mapillary/claude-prompt-fix-map-asset-layers.md` | Detailed classification fix for 0-count categories |
| `docs/Mapillary/plotcode-fix-jurisdiction-prompt.md` | Full jurisdiction sync architecture |
