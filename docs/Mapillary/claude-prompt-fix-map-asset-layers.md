# Claude Code Prompt: Fix Map Tab Asset Layers to Match Inventory Manager

## Context

The Crash Lens application has a **Map tab** with an "Asset Layers" panel and an **Inventory Manager tab** (iframe: `inventory-manager.html`). Both load traffic inventory data from the same R2 CSV source (`traffic-inventory.csv`), but the Map tab's asset layers are **broken** — many layers show 0 assets and layers don't activate when toggled on. The Inventory Manager works correctly and should be the reference implementation.

**The goal**: Make the Map tab's Asset Layers panel match the Inventory Manager in terms of categories, subcategories, icons, counts, and layer activation — so users can toggle layers on/off and see the correct sign markers on the map.

---

## Current Data (Henrico County, Virginia)

The `traffic-inventory.csv` has **55,134 rows** (excluding header) with columns: `id, mutcd, name, class, speed, lat, lon, first_seen, signal_heads`

### Data Breakdown by `class` prefix:
| Class Prefix | Count | Contains |
|---|---|---|
| `object` | 39,668 | Street Light (17,139), Fire Hydrant (11,174), Manhole (10,544), Signal V (776), Ped Signal (23), Signal H (12) |
| `regulatory` | 11,555 | STOP (5,747), YIELD (1,340), Speed signs (3,740), No U-Turn (403), No Parking (150), No Left (67), Turn-related, One Way (39), No Turn Red (28) |
| `marking` | 3,447 | Stop Bar (2,959), Crosswalk (488) |
| `warning` | 366 | Stop Ahead (158), Turn (131), RR (41), Winding (26), Yield Ahead (9), Signal Ahead (1) |
| `information` | 99 | Interstate (71), Hospital (25), Parking (2), Lodging (1) |

### Speed Sign Breakdown (3,740 total, all R2-1 MUTCD):
| Speed | Count | Speed | Count |
|---|---|---|---|
| 5 mph | 3 | 40 mph | 44 |
| 10 mph | 4 | 45 mph | 476 |
| 15 mph | 34 | 50 mph | 1 |
| 20 mph | 11 | 55 mph | 50 |
| 25 mph | 2,240 | 60 mph | 34 |
| 30 mph | 22 | 65 mph | 111 |
| 35 mph | 676 | 70 mph | 34 |

---

## What the Inventory Manager Does RIGHT (Reference)

The Inventory Manager (`inventory-manager.html`) correctly:

1. **Categorizes assets** using `getCategory()` based on `class` and `name` fields:
   - `speed` — name starts with "Speed" and class doesn't include "school"
   - `reg` — class starts with "regulatory" (excluding speed)
   - `warn` — class starts with "warning"
   - `guide` — class starts with "information"
   - `school` — class includes "school" or name includes "School"
   - `mark` — class starts with "marking"
   - `infra` — class includes "traffic-light" or name includes "Signal", plus everything else (objects)

2. **Displays correct counts**: Speed 3,740 | Regulatory 7,815 | Warning 366 | Guide 99 | School 0 | Infrastructure 43,115

3. **Shows speed sub-filters** with individual speed limit icons (5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70) using dynamic SVG `createSpeedIcon(speed)`

4. **Renders proper icons** for each sign type using `SIGN_SVG` object and `getSignSVG()` function with 30+ named SVG icons

5. **Has speed filter buttons**: All | None | ≤30 | 35-50 | ≥55

6. **Shows assets on map** with clustering and proper icons

---

## What's BROKEN in the Map Tab's Asset Layers

### Problem 1: Layers Show 0 Assets
The Map tab's `TI_MAP_CATEGORIES` (line ~124,881 in `app/index.html`) uses MUTCD-based `match()` functions that may not correctly classify items whose MUTCD is `"N/A"` (43,115 out of 55,135 items have MUTCD = "N/A" — these are infrastructure/objects). The classification falls through without matching.

### Problem 2: Layers Don't Activate When Toggled
When a user clicks a layer checkbox, the `toggleTICategory()` function calls `addTIMapLayer()` which creates a Leaflet marker cluster. But if `catState.items` is empty (due to classification failure), nothing renders.

### Problem 3: Icon Mismatch
The Map tab's `getTIMarkerSVG()` function (line ~125,242) uses different icon logic than the Inventory Manager's `getSignSVG()`. They should produce the same visual result.

### Problem 4: Category Structure Mismatch
The Map tab uses a parent-child hierarchy (`TI_PARENT_ORDER` → `TI_MAP_CATEGORIES`) that groups differently than the Inventory Manager:
- Map Tab: Speed is under Regulatory parent
- Inventory Manager: Speed is its own top-level category
- Map Tab: Object Markers are a separate parent
- Inventory Manager: Objects fall under Infrastructure

---

## Required Changes

### 1. Fix the `classifyTIItems()` Function

The classification function must handle ALL items, especially the 43,115 items with MUTCD = "N/A". Use the **same logic as the Inventory Manager's `getCategory()`**:

```
Priority order for classification:
1. If name starts with "Speed" AND class doesn't include "school" → speed category
2. If class includes "school" OR name includes "School" → school category
3. If class starts with "regulatory" → regulatory category
4. If class starts with "warning" → warning category
5. If class starts with "information" → guide category
6. If class starts with "marking" → marking category
7. If class includes "traffic-light" OR name includes "Signal" → infrastructure signals
8. If name is "Street Light" → infrastructure utilities
9. If name is "Fire Hydrant" → infrastructure utilities
10. If name is "Manhole" → infrastructure utilities
11. Everything else → infrastructure (general)
```

The current MUTCD-based matching fails because 78% of items have MUTCD = "N/A". **You MUST add fallback classification by `class` and `name` fields** when MUTCD matching fails.

### 2. Fix the Asset Layers Panel Structure

Make the panel match the Inventory Manager's visual structure:

```
TRAFFIC INVENTORY (55,135)
├── ● SPEED 3,740                    [toggle all speeds]
│   ├── [Speed 5 icon] 5 mph (3)     [individual toggle]
│   ├── [Speed 10 icon] 10 mph (4)
│   ├── [Speed 15 icon] 15 mph (34)
│   ├── [Speed 20 icon] 20 mph (11)
│   ├── [Speed 25 icon] 25 mph (2,240)
│   ├── [Speed 30 icon] 30 mph (22)
│   ├── [Speed 35 icon] 35 mph (676)
│   ├── [Speed 40 icon] 40 mph (44)
│   ├── [Speed 45 icon] 45 mph (476)
│   ├── [Speed 50 icon] 50 mph (1)
│   ├── [Speed 55 icon] 55 mph (50)
│   ├── [Speed 60 icon] 60 mph (34)
│   ├── [Speed 65 icon] 65 mph (111)
│   └── [Speed 70 icon] 70 mph (34)
├── ● REGULATORY 7,815               [toggle all regulatory]
│   ├── [Stop icon] Stop & Yield (7,087)
│   ├── [No U-Turn icon] Turn & Movement (529)
│   ├── [Parking icon] Parking (150)
│   └── [Reg icon] Other Regulatory (49)
├── ▲ WARNING 366                    [toggle all warnings]
│   ├── [Stop Ahead icon] Advance Warnings (168)
│   ├── [Turn icon] Curves & Turns (157)
│   ├── [RR icon] Crossings (41)
│   └── [Supplemental icon] Other Warning (0)
├── ● GUIDE 99                       [toggle all guide]
│   ├── [Interstate icon] Routes (71)
│   └── [Hospital icon] Services & Destination (28)
├── 🏫 SCHOOL 0                      [toggle all school]
├── ◆ OBJECT MARKERS 0              [toggle]
├── 🚦 INFRASTRUCTURE 43,115         [toggle all infrastructure]
│   ├── [Signal icon] Traffic Signals (811) → consolidated to ~X intersections
│   ├── [Street Light icon] Street Lights (17,139)
│   ├── [Hydrant icon] Fire Hydrants (11,174)
│   ├── [Manhole icon] Manholes (10,544)
│   └── [Safety icon] Other Infrastructure (remaining)
└── ═ MARKINGS 3,447                 [toggle all markings]
    ├── [Stop Bar icon] Stop Bars (2,959)
    └── [Crosswalk icon] Crosswalks (488)
```

### 3. Fix Icon Rendering

Use the **same SVG icons as the Inventory Manager**. The key icons needed:

**Speed Signs**: Dynamic SVG with white rectangle, "SPEED LIMIT" text, and bold speed number — use `createTISpeedIcon(speed)` matching the Inventory Manager's `createSpeedIcon()`.

**Named Signs** (match these exactly from Inventory Manager's `SIGN_SVG`):
- STOP → Red octagon with white "STOP"
- YIELD → Red/white inverted triangle
- No U-Turn → White circle with red border, U-turn symbol with red slash
- No Left → White circle with red border, left arrow with red slash
- No Parking → White circle with red border, "P" with red slash
- Stop Ahead → Yellow diamond with small stop sign
- Signal Ahead → Yellow diamond with traffic light
- Turn → Yellow diamond with arrow
- Winding → Yellow diamond with winding road
- RR → Yellow circle with "RR" cross
- Yield Ahead → Yellow diamond with small yield sign
- Interstate → Blue/red shield shape
- Hospital → Blue square with white "H"
- Signal V → Black rectangle with red/yellow/green circles (vertical)
- Signal H → Black rectangle with red/yellow/green circles (horizontal)
- Ped Signal → Black rectangle with white walking figure
- Street Light → Gray circle with light rays
- Fire Hydrant → Red fire hydrant shape
- Manhole → Gray circle with cross pattern
- Stop Bar → White rectangle with red stripe
- Crosswalk → White rectangle with zebra pattern

**Fallback icons by category**:
- Regulatory: Red octagon outline
- Warning: Yellow triangle outline
- Guide: Green square outline
- School: Yellow pentagon outline
- Infrastructure: Gray circle outline
- Marking: Purple rectangle outline

### 4. Fix Layer Activation

Each category and sub-category must correctly:
1. Store classified items in `trafficInventoryLayerState.categories[key].items[]`
2. Create `L.markerClusterGroup()` with proper clustering settings when toggled on
3. Add markers with correct SVG icons to the cluster group
4. Add the cluster group to the map
5. Remove from map when toggled off
6. Show proper popups on marker click with sign info (name, MUTCD, speed if applicable, coordinates)

### 5. Ensure Data Loading Works

The `loadTrafficInventoryForMap()` function must:
1. Fetch from `{R2_BASE_URL}/{state}/{jurisdiction}/traffic-inventory.csv`
2. Parse ALL columns including `class`, `name`, `speed` (not just `mutcd`)
3. Classify using the fixed classification logic
4. Populate `trafficInventoryLayerState.categories` with correct counts
5. Populate `trafficInventoryLayerState.speedCategories` with per-speed breakdowns
6. Update the panel HTML to show correct counts

---

## Architecture Constraints

- **Single-file SPA**: All changes go in `app/index.html`
- **No new dependencies**: Use existing Leaflet, L.markerCluster
- **Preserve existing functionality**: Don't break other tabs or features
- **Follow existing patterns**: Use `trafficInventoryLayerState` for state management
- **Performance**: 55,000+ markers need clustering; don't render all at once
- **Icons must be SVG**: For crisp rendering at all zoom levels

## Key Code Locations in `app/index.html`

| What | Approximate Line |
|---|---|
| `TI_PARENT_ORDER` | 124,865-124,876 |
| `TI_MAP_CATEGORIES` definitions | 124,881-125,190 |
| `getTIMarkerSVG()` icon rendering | 125,242-125,397 |
| `loadTrafficInventoryForMap()` | 125,454-125,551 |
| `classifyTIItems()` | 125,556-125,672 |
| `consolidateTISignals()` | 125,679-125,775 |
| `addTIMapLayer()` | 125,780-125,873 |
| Toggle functions | 125,958-126,105 |
| `buildTIAssetPanelHTML()` | 126,320-126,440 |
| `updateMapAssetPanel()` | 128,145-128,472 |

## Testing Checklist

After making changes, verify:
- [ ] All category counts match Inventory Manager (Speed 3,740 | Regulatory 7,815 | Warning 366 | Guide 99 | Infrastructure 43,115 | Markings 3,447)
- [ ] Each speed limit sub-category shows correct count and icon
- [ ] Toggling a parent category on shows ALL child markers on the map
- [ ] Toggling individual child categories works independently
- [ ] Toggling individual speed limits works (e.g., show only 25 mph signs)
- [ ] Icons on the map match the Inventory Manager icons
- [ ] Marker popups show correct sign info
- [ ] Clustering works properly (markers group at lower zoom, individual at higher zoom)
- [ ] Infrastructure layer shows Street Lights, Fire Hydrants, Manholes, Signals separately
- [ ] No JavaScript errors in console
- [ ] No performance degradation with 55,000+ items
- [ ] Existing map functionality (crash layers, heatmaps, etc.) still works

## Important Notes

1. The **root cause** of 0-count layers is likely that `classifyTIItems()` relies on MUTCD matching but 78% of items have MUTCD = "N/A" (all infrastructure/objects). The fix MUST add `class` and `name` based fallback matching.

2. The Inventory Manager's `getCategory()` function (in `inventory-manager.html`, line 378-388) is the **proven working classification** — port this logic to the Map tab's classifier.

3. Speed signs should be treated as a **top-level category** (like in the Inventory Manager), NOT nested under Regulatory, to match the user's expected UI.

4. Infrastructure should be **broken down into sub-categories**: Signals, Street Lights, Fire Hydrants, Manholes, Other — rather than one monolithic layer with 43,000+ items.

5. When creating the PR, include screenshots showing the Asset Layers panel with correct counts and a map view with markers visible for at least one toggled-on layer.
