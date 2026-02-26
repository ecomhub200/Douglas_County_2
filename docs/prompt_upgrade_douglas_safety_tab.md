# Comprehensive Prompt: Upgrade Douglas County Safety Tab to Match Virginia Implementation

## CONTEXT

You are working on the **Douglas County Crash Lens** application located at:
`Douglas_County_2-main/app/index.html`

A **reference implementation** exists in the Virginia version at:
`Virginia-main/app/index.html`

The Virginia version has been updated with significant new features in the **Safety Focus tab** that the Douglas County version is currently missing. Your task is to port these features to Douglas County while preserving all existing functionality.

**IMPORTANT**: The Virginia implementation has been examined, tested, and everything passes. Follow it precisely. Do NOT lose any features, do NOT simplify, do NOT skip any part.

---

## WHAT ALREADY EXISTS IN DOUGLAS COUNTY (DO NOT BREAK)

The Douglas County Safety tab (`id="tab-safety"`, starts around line 13298 in `app/index.html`) currently has:

1. **Severity Filter Bar** — K/A/B/C/O checkboxes + date range picker with 1Y/3Y/5Y presets ✅
2. **24 Safety Category Cards** — curves, workzone, school, guardrail, senior, young, roaddeparture, lgtruck, pedestrian, bicycle, speed, impaired, intersection, nighttime, distracted, motorcycle, hitrun, weather, animal, unrestrained, drowsy, alcoholonly, cross, custommatrix ✅
3. **Detail Panel** — Shows when a category is selected with header, severity bar, stats row, factor badges, 5 breakdown charts (subcategory, collision, roadway, harmful event, year-over-year) ✅
4. **Top Locations Table** — Basic table with columns: Route, Count, K+A, EPDO, Actions ✅
5. **Countermeasures Section** — Dynamic cards with CMF data ✅
6. **Cross Analysis Panel** — 18 cross-factor combinations ✅
7. **Custom Matrix Builder Panel** — 2-4 factor analysis ✅
8. **Safety Details Modal** — Basic location detail overlay ✅
9. Existing JS functions: `initSafetyFocus()`, `processSafetyData()`, `applySafetyFilters()`, `selectSafetyCategory()`, `updateSafetyCards()`, `updateSafetyLocationTable()`, `renderSafetyCountermeasures()`, `exportSafetyData()`, `exportSafetyToKML()`, `getSafetyCMF()`, `showSafetyLocationDetails()`, etc. ✅

---

## WHAT IS MISSING IN DOUGLAS COUNTY (MUST ADD)

### FEATURE 1: Replace MUTCD Button with PDF Report Button in Detail Panel Header

**Current Douglas County** (line ~13482):
```html
<button class="btn btn-sm" style="background:#7c3aed;color:white" onclick="if(typeof safetyState!=='undefined')askMUTCDForSafetyCategory(safetyState.activeCategory)">📖 MUTCD</button>
```

**Replace with** (matching Virginia line 12036):
```html
<button class="btn btn-sm" style="background:#7c3aed;color:white" onclick="exportSafetyCategoryPDF()">📄 PDF Report</button>
```

This replaces the MUTCD button with a professional PDF Report button. Keep all other buttons unchanged (View All on Map, Export Data, Export KML, Get CMF, Evaluate Crossing).

---

### FEATURE 2: Add Location Selection System to Top Locations Table

**Current Douglas County** has a basic table header (line ~13599-13618):
```html
<div class="card">
<div class="card-title">📍 Top Locations <span id="safetyTableCount" ...></span></div>
```

**Replace the entire Top Locations table section** with the Virginia version that includes:

#### A. Enhanced Card Title with Selection Counter + PDF Selected Button
```html
<div class="card">
<div class="card-title" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem">
<span>📍 Top Locations <span id="safetyTableCount" style="font-weight:400;color:var(--gray);font-size:.85rem"></span></span>
<div style="display:flex;gap:.5rem;align-items:center">
<span id="safetySelectedCount" style="font-size:.8rem;color:var(--gray);display:none">0 selected</span>
<button class="btn btn-sm" style="background:#7c3aed;color:white;display:none" id="safetyLocationPdfBtn" onclick="exportSafetySelectedLocationsPDF()">📄 PDF Selected</button>
</div>
</div>
```

#### B. Selection Header Row (Select for Analysis)
Add this immediately after the card-title div:
```html
<!-- Selection header -->
<div class="sf-select-header" id="sfSelectHeader">
<input type="checkbox" class="sf-checkbox" id="sfSelectAll" onchange="toggleAllSfSelection(this.checked)" title="Select all (max 5)">
<label for="sfSelectAll" style="font-size:.85rem;font-weight:600;cursor:pointer">Select for Analysis</label>
<span class="sf-select-count" id="sfSelectCount">0 of 5 selected</span>
<button class="btn-soft btn-soft-secondary btn-soft-sm" onclick="clearSfSelection()" style="margin-left:auto">Clear All</button>
</div>
```

#### C. Updated Table Headers (add checkbox column)
```html
<table class="safety-location-table" id="safetyLocationTable">
<thead>
<tr>
<th style="width:40px"><span class="help-tooltip" data-tooltip="Select up to 5 locations for detailed analysis">&#10003;</span></th>
<th>Route</th>
<th>Count</th>
<th>K+A</th>
<th>EPDO</th>
<th>Actions</th>
</tr>
</thead>
<tbody id="safetyLocationBody">
<tr><td colspan="6" style="text-align:center;color:var(--gray);padding:2rem">Select a category above to view locations</td></tr>
</tbody>
</table>
```

Note: The `colspan` changes from `5` to `6` because of the new checkbox column.

---

### FEATURE 3: Add Detailed Analysis Panel (sf-detail-panel)

This is a **major new UI section** that appears between the Top Locations table and the Countermeasures section. When users select locations (up to 5) from the Top Locations table, this panel slides in with rich analysis.

Insert this HTML **after the Top Locations table closing `</div>` and before the Countermeasures section**:

```html
<!-- Safety Focus Location Detail Analysis Panel -->
<div class="sf-detail-panel" id="sfDetailPanel">
<div class="sf-detail-header">
<div class="sf-detail-title">
<span>📊</span>
<span id="sfDetailTitle">Detailed Analysis</span>
</div>
<div class="sf-detail-controls">
<div class="sf-view-toggle">
<button class="sf-view-btn active" onclick="setSfViewMode('combined')" id="sfBtnViewCombined">Combined</button>
<button class="sf-view-btn" onclick="setSfViewMode('compare')" id="sfBtnViewCompare">Compare</button>
</div>
<div class="sf-export-btns">
<button class="sf-export-btn" onclick="exportSfDetailCSV()" title="Export selected location crash details to CSV">📥 CSV</button>
<button class="sf-export-btn" onclick="exportSfDetailPDF()" title="Export selected location crash details to PDF">📄 PDF</button>
<button class="sf-export-btn" onclick="exportSfDetailKML()" title="Export selected location crashes to KML">🌍 KML</button>
</div>
<button class="sf-export-btn" onclick="clearSfSelection()" title="Close panel">✕</button>
</div>
</div>
<div class="sf-detail-body" id="sfDetailBody">
<!-- Dynamic content rendered by renderSfDetailContent() -->
</div>
</div>
```

---

### FEATURE 4: Add Required CSS Styles

Add these CSS styles to the `<style>` section of the Douglas County `app/index.html`. These styles power the selection system and the detailed analysis panel:

```css
/* ── Safety Focus Location Selection Checkboxes ── */
.sf-checkbox {
    width: 18px;
    height: 18px;
    accent-color: #7c3aed;
    cursor: pointer;
}

.sf-select-header {
    display: flex;
    align-items: center;
    gap: .75rem;
    padding: .5rem .75rem;
    background: #f8fafc;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    margin-bottom: .5rem;
}

.sf-select-count {
    font-size: .8rem;
    color: var(--gray);
}

/* ── Safety Focus Detail Analysis Panel ── */
.sf-detail-panel {
    margin-top: 1rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    max-height: 0;
    opacity: 0;
    transition: max-height 0.4s ease, opacity 0.3s ease, margin 0.3s ease;
    margin-bottom: 0;
}

.sf-detail-panel.visible {
    max-height: 5000px;
    opacity: 1;
    margin-bottom: 1rem;
}

.sf-detail-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: .5rem;
    padding: .75rem 1rem;
    background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
    color: white;
}

.sf-detail-title {
    display: flex;
    align-items: center;
    gap: .5rem;
    font-weight: 700;
    font-size: 1rem;
}

.sf-detail-controls {
    display: flex;
    align-items: center;
    gap: .5rem;
    flex-wrap: wrap;
}

.sf-view-toggle {
    display: flex;
    background: rgba(255,255,255,0.15);
    border-radius: 6px;
    overflow: hidden;
}

.sf-view-btn {
    padding: .3rem .75rem;
    font-size: .8rem;
    border: none;
    background: transparent;
    color: rgba(255,255,255,0.7);
    cursor: pointer;
    transition: all 0.2s;
}

.sf-view-btn.active {
    background: rgba(255,255,255,0.25);
    color: white;
    font-weight: 600;
}

.sf-export-btns {
    display: flex;
    gap: .25rem;
}

.sf-export-btn {
    padding: .3rem .6rem;
    font-size: .75rem;
    border: 1px solid rgba(255,255,255,0.3);
    background: rgba(255,255,255,0.1);
    color: white;
    border-radius: 4px;
    cursor: pointer;
    transition: background 0.2s;
}

.sf-export-btn:hover {
    background: rgba(255,255,255,0.25);
}

.sf-detail-body {
    padding: 1rem;
    background: white;
}

/* ── KPI Row inside detail panel ── */
.sf-kpi-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: .75rem;
    margin-bottom: 1rem;
}

.sf-kpi {
    background: #f8fafc;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: .75rem;
    text-align: center;
    position: relative;
    overflow: hidden;
}

.sf-kpi::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
}

.sf-kpi-value {
    font-size: 1.5rem;
    font-weight: 700;
    line-height: 1.2;
}

.sf-kpi-label {
    font-size: .75rem;
    color: var(--gray);
    margin-top: .25rem;
}

.sf-kpi-sub {
    font-size: .7rem;
    color: var(--gray);
    margin-top: .15rem;
}

/* ── Charts Grid ── */
.sf-charts-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1rem;
    margin-bottom: 1rem;
}

/* ── Factors Grid ── */
.sf-factors-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: .5rem;
    margin-bottom: 1rem;
}

.sf-factor-item {
    background: #f8fafc;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: .5rem .75rem;
    display: flex;
    align-items: center;
    gap: .5rem;
}

.sf-factor-bar {
    flex: 1;
    height: 6px;
    background: #e2e8f0;
    border-radius: 3px;
    overflow: hidden;
    position: relative;
}

.sf-factor-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.5s ease;
}

.sf-factor-benchmark {
    position: absolute;
    top: -2px;
    width: 2px;
    height: 10px;
    background: #334155;
    border-radius: 1px;
}

/* ── VRU Grid (Vulnerable Road Users) ── */
.sf-vru-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: .75rem;
    margin-bottom: 1rem;
}

/* ── Compare View (side-by-side locations) ── */
.sf-compare-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1rem;
}

.sf-compare-card {
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
}

.sf-compare-card-header {
    padding: .5rem .75rem;
    font-weight: 600;
    font-size: .9rem;
    color: white;
}

.sf-compare-card-body {
    padding: .75rem;
}

/* ── Mobile Responsive ── */
@media (max-width: 768px) {
    .sf-detail-header {
        flex-direction: column;
        align-items: flex-start;
    }
    .sf-charts-grid {
        grid-template-columns: 1fr;
    }
    .sf-compare-container {
        grid-template-columns: 1fr;
    }
    .sf-kpi-row {
        grid-template-columns: repeat(2, 1fr);
    }
}
```

---

### FEATURE 5: Add SELECTION_PDF_STYLES Constant

If the Douglas County `app/index.html` does NOT already have a `SELECTION_PDF_STYLES` constant, add it in the JavaScript section (near other constants):

```javascript
const SELECTION_PDF_STYLES = {
    colors: {
        primary: [30, 60, 114],      // #1e3c72 - dark blue
        secondary: [42, 82, 152],    // #2a5298 - medium blue
        fatal: [220, 53, 69],        // #dc3545 - red
        serious: [253, 126, 20],     // #fd7e14 - orange
        minor: [255, 193, 7],        // #ffc107 - yellow
        possible: [23, 162, 184],    // #17a2b8 - cyan
        pdo: [40, 167, 69],          // #28a745 - green
        text: [51, 51, 51],          // #333333
        lightGray: [245, 247, 250],  // #f5f7fa
        white: [255, 255, 255]
    },
    severityColors: {
        K: [220, 53, 69],
        A: [253, 126, 20],
        B: [255, 193, 7],
        C: [23, 162, 184],
        O: [40, 167, 69]
    }
};
```

---

### FEATURE 6: Add `exportSafetyCategoryPDF()` Function

Port the **entire** `exportSafetyCategoryPDF()` function from Virginia (`Virginia-main/app/index.html` starting at line 85829). This function generates a professional multi-page PDF report for the active safety category. It includes:

- **Cover page** with gradient header, "CRASH LENS" branding, category name, info box (Category, Period, Total Crashes, Generated date)
- **8 KPI cards** in 2 rows: Total Crashes, Fatal (K), Serious Injury (A), EPDO Score, K+A Injuries, Minor (B), Possible (C), Locations
- **Severity Distribution** section with colored stacked bar (K/A/B/C/O segments) and legend
- **Cross-Functional Contributing Factors** section with a 6-factor grid (Speed-Related, Senior Driver, Young Driver, Nighttime, Impaired, Distracted) showing count, percentage, and mini bar charts drawn natively in PDF
- **Chart pages** capturing canvas images from: Subcategory Breakdown, Collision Type Distribution, and Year-Over-Year Trend charts
- **Natively drawn charts** for Roadway Alignment Breakdown and First Harmful Event Breakdown (drawn as horizontal bar charts directly in the PDF for reliability when canvas capture fails)
- **Top Locations table** (up to 25 rows sorted by EPDO) using `jspdf-autotable` with severity color-coded cells
- Helper functions: `addFooter()`, `drawMiniHeader()`, `drawSectionHeader()`, `drawKPI()`, `addNewPage()`
- Page numbering, footer with attribution, date stamps

**CRITICAL**: Copy this function EXACTLY from the Virginia file. It is ~800 lines long. Do not simplify or abbreviate.

---

### FEATURE 7: Add `exportSafetySelectedLocationsPDF()` Function

Port the **entire** `exportSafetySelectedLocationsPDF()` function from Virginia (starting at line 86621). This generates a PDF report for selected locations (up to 5). It includes:

- **Cover page** with "Selected Locations Report" title, category name, location count
- **Summary Comparison Table** showing all selected locations side-by-side with columns: Location, Crashes, K, A, K+A, B, C, O, EPDO, plus a TOTAL row at the bottom
- **Combined Segment Analysis page** (when 2+ locations selected) with aggregate KPIs
- **Per-location detail pages** for each selected route:
  - KPI cards (Total Crashes, K+A Rate, EPDO Score, VRU Crashes, YoY Trend)
  - Contributing factors grid
  - Top collision types
  - Severity distribution table
  - Location contribution analysis (% of category total)
- Page break management for large selections
- Same footer, header, and helper functions pattern as the category PDF

**CRITICAL**: Copy this function EXACTLY from Virginia. Do not simplify.

---

### FEATURE 8: Add Location Selection State Management & Functions

Add these JavaScript functions that manage the location selection system. Port from Virginia:

#### A. Selection State Object
Add `sfDetailState` to manage selection state:
```javascript
const sfDetailState = {
    selectedLocations: [],
    viewMode: 'combined',   // 'combined' or 'compare'
    aggregatedData: null,
    categoryBenchmarks: null
};
```

#### B. Selection Functions
Port these functions from Virginia:
- `toggleSfLocationSelection(route)` — Toggle a location's selection (max 5)
- `toggleAllSfSelection(checked)` — Select/deselect all visible locations (max 5)
- `clearSfSelection()` — Clear all selections and hide detail panel
- `updateSfSelectionUI()` — Update selected count badge, PDF Selected button visibility, checkbox states
- `syncSafetySelectedLocations()` — Sync `sfDetailState.selectedLocations` with `safetyState.selectedLocations` for PDF export compatibility

#### C. Update `updateSafetyLocationTable()` Function
The existing `updateSafetyLocationTable()` must be updated to:
1. Add a **checkbox column** as the first column in each row
2. Each row gets: `<td><input type="checkbox" class="sf-checkbox" onchange="toggleSfLocationSelection('${route}')" ${isChecked ? 'checked' : ''}></td>`
3. Track which routes are selected using `sfDetailState.selectedLocations`
4. Update the selection UI after rendering rows

#### D. Detail Panel Orchestrator Functions
Port from Virginia:
- `updateSfDetailPanel(skipScroll)` — Main orchestrator that validates selections, shows panel, aggregates data, renders content
- `aggregateSfDetailData()` — Aggregates crash data from all selected locations within the active category (severity, by year, by month, by DOW, by hour, by peak period, by collision type, by weather, by light, by surface, by traffic control, contributing factors, VRU, demographics, special zones, per-location breakdown)
- `calculateSfCategoryBenchmarks()` — Calculates benchmark rates from the full category for comparison

#### E. Rendering Functions
Port from Virginia:
- `renderSfDetailContent()` — Renders the detail panel body based on viewMode ('combined' or 'compare')
- `setSfViewMode(mode)` — Toggles between Combined and Compare view modes

**Combined Mode** renders:
- KPI row (Total Crashes, KA Rate with benchmark comparison indicator ↑/↓, EPDO Score, VRU Crashes, YoY Trend)
- Temporal Analysis section: Yearly Trend chart (stacked bar: Total + K+A), Severity by Year chart (stacked bar: K/A/B/C/O)
- Monthly Heatmap (year × month grid with color-coded cells)
- Time of Day chart (24-hour distribution bar chart)
- Peak Period badges (AM Peak, Midday, PM Peak, Night with counts)
- Day of Week distribution
- Contributing Factors grid with benchmark comparison bars
- VRU section (Pedestrian, Bicycle, Motorcycle with K+A counts)
- Demographics section (Senior, Young, Unrestrained)
- Collision Type Distribution (horizontal bar chart)
- Environmental Factors: Weather, Light Conditions, Road Surface
- If multiple locations: Location Contribution table and pie-style breakdown

**Compare Mode** renders:
- Side-by-side cards for each selected location
- Each card shows: severity breakdown, total crashes, K+A rate, EPDO, top collision types, contributing factors

#### F. Export Functions for Detail Panel
Port from Virginia:
- `exportSfDetailCSV()` — Exports all crash data from selected locations to CSV
- `exportSfDetailPDF()` — Exports detailed analysis to PDF (similar structure to category PDF but scoped to selected locations)
- `exportSfDetailKML()` — Exports selected location crashes to KML format

---

### FEATURE 9: Update `showSafetyLocationDetails()` Modal

Update the existing `showSafetyLocationDetails()` function to match Virginia's version which shows:
- 4-KPI header (Total Crashes, K+A Injuries, EPDO, Fatal counts) with colored values
- Severity distribution summary line
- Action buttons row (View on Map, Export Data, Export KML, Get CMF) with proper styling
- Paginated crash list (first 100 crashes with "more" indicator)
- Each crash item shows: severity badge (color-coded), collision type, date, and route

---

## IMPLEMENTATION CHECKLIST

Work through these steps IN ORDER:

1. ☐ Add CSS styles (Feature 4) to the `<style>` section
2. ☐ Add `SELECTION_PDF_STYLES` constant (Feature 5) near other JS constants
3. ☐ Add `sfDetailState` object (Feature 8A)
4. ☐ Replace MUTCD button with PDF Report button (Feature 1)
5. ☐ Replace Top Locations table HTML with enhanced version (Feature 2)
6. ☐ Add sf-detail-panel HTML between locations table and countermeasures (Feature 3)
7. ☐ Add selection management functions (Feature 8B)
8. ☐ Update `updateSafetyLocationTable()` to include checkbox column (Feature 8C)
9. ☐ Add detail panel orchestrator functions (Feature 8D)
10. ☐ Add rendering functions for Combined and Compare modes (Feature 8E)
11. ☐ Add export functions for detail panel (Feature 8F)
12. ☐ Add `exportSafetyCategoryPDF()` function (Feature 6)
13. ☐ Add `exportSafetySelectedLocationsPDF()` function (Feature 7)
14. ☐ Update `showSafetyLocationDetails()` modal (Feature 9)
15. ☐ Verify all existing functions still work (do not break `applySafetyFilters`, `selectSafetyCategory`, `renderSafetyCountermeasures`, etc.)
16. ☐ Test that safety tab navigation still works via `navigateTo('safety')`

---

### FEATURE 10: Additional Functions and CSS Not Listed Above

The following additional items exist in Virginia but NOT in Douglas County. They MUST also be ported:

#### A. Additional Selection Sync Functions
- `syncSfCheckboxStates()` — Synchronizes checkbox checked states in the location table with `sfDetailState.selectedLocations` after any selection change. Also syncs with `safetyState.selectedLocations` (a Set) for backward compatibility with PDF export functions.

**Important state sync detail**: `sfDetailState.selectedLocations` is an **Array**, while `safetyState.selectedLocations` is a **Set**. Both must stay in sync. When a location is toggled, update BOTH.

#### B. Chart Initialization Functions for Detail Panel
These are called by `renderSfDetailContent()` and must be ported:
- `initSfDetailCharts()` — Main dispatcher that calls combined or compare chart init
- `initSfCombinedCharts(data)` — Initializes all Chart.js charts for the combined view: Yearly Trend (stacked bar), Severity by Year (stacked bar), Monthly Heatmap, Time of Day (bar), Day of Week, Collision Type (horizontal bar), Weather, Light Conditions, Road Surface, Traffic Control
- `initSfCompareCharts(data)` — Initializes charts for compare view: location comparison bar chart, severity distribution per location

#### C. Data Validation Functions (for Data Check feature)
- `sfCheckLocationTableConsistency(results)` — Validates location table data integrity
- `sfCheckCrossAnalysisConsistency(results)` — Validates cross-analysis data integrity
- `sfCheckFilterConsistency(results)` — Validates filter state consistency
- `sfCheckDetailPanelAccuracy(results)` — Validates detail panel data accuracy

#### D. Additional CSS Classes for Detail Panel Content
These CSS classes are used inside `renderSfDetailContent()` for the monthly heatmap and special zones:

```css
/* ── Monthly Heatmap ── */
.sf-monthly-heatmap {
    display: grid;
    gap: 2px;
}

.sf-heatmap-labels {
    display: flex;
    gap: 2px;
}

.sf-heatmap-label {
    font-size: .65rem;
    color: var(--gray);
    text-align: center;
}

.sf-heatmap-cell {
    border-radius: 2px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: .65rem;
    min-height: 22px;
    transition: transform 0.15s;
    cursor: default;
}

.sf-heatmap-cell:hover {
    transform: scale(1.1);
    z-index: 1;
}

/* ── Special Zones & Infrastructure ── */
.sf-special-zones {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: .75rem;
}

.sf-zone-card {
    background: #f8fafc;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: .75rem;
    text-align: center;
}

.sf-zone-icon {
    font-size: 1.5rem;
    margin-bottom: .25rem;
}

.sf-zone-value {
    font-size: 1.3rem;
    font-weight: 700;
}

.sf-zone-label {
    font-size: .75rem;
    color: var(--gray);
}
```

#### E. Special Zones Section in Combined View
The `renderSfDetailContent()` combined mode includes a "Special Zones & Infrastructure" section rendering Work Zone Crashes, School Zone Crashes, Dark Condition Crashes, and Adverse Weather Crashes cards. Make sure this is included.

---

## CRITICAL RULES

1. **DO NOT REMOVE** any existing functionality — only ADD new features
2. **COPY EXACTLY** from Virginia — do not simplify, abbreviate, or "improve" the code
3. **The file is `app/index.html`** — a single-page application with all HTML/CSS/JS in one file
4. **jsPDF and jspdf-autotable** libraries must already be loaded (check `<head>` section for CDN links). If missing, add:
   ```html
   <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
   <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.8.1/jspdf.plugin.autotable.min.js"></script>
   ```
5. **html2canvas** must be loaded. If missing, add:
   ```html
   <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
   ```
6. Preserve all existing ID attributes and function names
7. The safety tab uses these existing state objects: `safetyState`, `safetyCategories`, `crashState` — work with them, do not rename
8. Reference Virginia file (`Virginia-main/app/index.html`) for the COMPLETE implementation of any function when the description above is not sufficient

---

## REFERENCE FILE LOCATIONS

- **Virginia (source of truth)**: `Virginia-main/app/index.html` (~124,898 lines)
  - Safety HTML: lines 11849–12433
  - CSS styles: lines 749–1164
  - `SELECTION_PDF_STYLES`: line 42414
  - `renderSafetyCountermeasures()`: line 76022
  - `showSafetyLocationDetails()`: line 83800
  - `setSfViewMode()`: line 84054
  - `updateSfDetailPanel()`: line 84062
  - `aggregateSfDetailData()`: line 84098
  - `calculateSfCategoryBenchmarks()`: line 84256
  - `renderSfDetailContent()`: line 84300
  - `exportSfDetailCSV()`: line 84889
  - `exportSfDetailPDF()`: line 84944
  - `exportSafetyCategoryPDF()`: line 85829
  - `exportSafetySelectedLocationsPDF()`: line 86621

- **Douglas County (target)**: `Douglas_County_2-main/app/index.html` (~134KB)
  - Safety HTML: lines 13298–13836
  - Safety JS functions: starting around line 86540+
