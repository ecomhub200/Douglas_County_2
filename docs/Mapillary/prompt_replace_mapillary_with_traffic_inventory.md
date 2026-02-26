# Task: Replace "Mapillary Assets" Tab with "Traffic Inventory" UI in Crash Lens App

## Objective
In `app/index.html`, the **Analysis** tab currently has two subtabs: "Infrastructure Assets" and "Mapillary Assets". I want to **remove the Mapillary Assets subtab entirely** and **replace it with a new "Traffic Inventory" subtab** whose content comes from a standalone HTML file.

## Source File (DO NOT MODIFY THIS FILE)
The Traffic Inventory UI is in:
```
scripts/mapillary_asset_downloader_v4_7_r2.html
```
This file is a **tested, working, standalone HTML page**. It has 3 sections:
- **CSS** (lines 12–158): Inline `<style>` block
- **HTML body** (lines 161–550): The UI markup (starts after `<body>`, ends at the `<footer>` tag)
- **JavaScript** (lines 551–2802): A single `<script>` block containing all logic

**CRITICAL: Do NOT change, rename, refactor, or "clean up" any code from this file. Copy it exactly as-is.**

## What to Do in `app/index.html`

### Step 1: Replace the Subtab Button (line 6753)
**Find:**
```html
<button class="analysis-subtab" data-subtab="mapillary" onclick="switchAnalysisSubtab('mapillary')">🗺️ Mapillary Assets</button>
```
**Replace with:**
```html
<button class="analysis-subtab" data-subtab="trafficinventory" onclick="switchAnalysisSubtab('trafficinventory')">🗺️ Traffic Inventory</button>
```

### Step 2: Replace the Mapillary HTML Content (lines 8377–8854)
**Remove** the entire block:
```html
<div id="analysis-mapillary" class="analysis-subtab-content" style="display:none;">
   ... (everything inside) ...
</div><!-- End analysis-mapillary -->
```
**Replace with** a new container that wraps the Traffic Inventory body HTML:
```html
<div id="analysis-trafficinventory" class="analysis-subtab-content" style="display:none;">
   <!-- Paste the ENTIRE HTML body content from mapillary_asset_downloader_v4_7_r2.html lines 161–550 here -->
   <!-- This includes everything from the toast container div through the footer -->
</div>
```
Copy lines 161–550 from `scripts/mapillary_asset_downloader_v4_7_r2.html` **exactly as they are** into this new div.

### Step 3: Replace the Mapillary CSS (lines 2203–2345)
**Remove** the entire CSS block starting with:
```css
/* Mapillary Asset Downloader Styles (mlyDL-) */
```
and ending around line 2345 (all styles prefixed with `.mlyDL-`).

**Replace with** the CSS from `scripts/mapillary_asset_downloader_v4_7_r2.html` lines 12–157 (the contents inside the `<style>` tags). Wrap it with a comment:
```css
/* Traffic Inventory Styles */
... (paste CSS here exactly as-is from the source file) ...
/* End Traffic Inventory Styles */
```

### Step 4: Replace the Mapillary JavaScript Module (lines 133102–134799)
**Remove** the entire block:
```javascript
// MAPILLARY ASSET DOWNLOADER MODULE (mlyDL_)
... (everything) ...
// MAPILLARY ASSET DOWNLOADER MODULE - END
```
**Replace with** the JavaScript from `scripts/mapillary_asset_downloader_v4_7_r2.html` lines 552–2801 (the contents inside the `<script>` tags, not the tags themselves). Wrap it with:
```javascript
// TRAFFIC INVENTORY MODULE
... (paste JS here exactly as-is from the source file) ...
// TRAFFIC INVENTORY MODULE - END
```

### Step 5: Update the `switchAnalysisSubtab()` Function (around line 57548)
**Find:**
```javascript
} else if (subtab === 'mapillary') {
    mlyDL_initSubtab();
}
```
**Replace with:**
```javascript
} else if (subtab === 'trafficinventory') {
    // Traffic Inventory initializes itself on load, no init function needed
}
```
If the Traffic Inventory JS has its own init/setup function that runs on page load (check for DOMContentLoaded listeners or IIFE patterns), you may need to extract it into a callable function and call it here instead. Look for the initialization pattern in the JS and adapt accordingly.

### Step 6: Update Cross-Reference Buttons
There are buttons in the app that jump to the Mapillary Assets tab:

**Button 1 (line 6069):**
```html
<button id="btnAnalyzeAssets" class="btn-soft btn-soft-info btn-soft-sm" onclick="locationJumpToMapillaryAssets()" title="Analyze Mapillary assets at this intersection (500ft area)" style="display:none">🗺️ Analyze Assets</button>
```
Update the title and onclick to reference the new Traffic Inventory tab. You can rename the function or update it.

**Button 2 (line 6165):**
```html
<button class="btn-soft btn-soft-info btn-soft-sm" onclick="jumpToMapillaryAssetsWithSelection()" title="Analyze Mapillary assets in selected area">🗺️ Analyze Assets</button>
```
Same — update title text. The functions `locationJumpToMapillaryAssets()` and `jumpToMapillaryAssetsWithSelection()` (lines 51837–52153) should be updated to switch to the `'trafficinventory'` subtab instead of `'mapillary'`.

### Step 7: Update the Mapillary Sources Section in Asset Deficiency (lines 12046–12062)
The "Asset Deficiency" analysis has a "Mapillary Assets" data source section. Update the label from "Mapillary Assets" to "Traffic Inventory" and update IDs:
- `adSourceMapillary` → `adSourceTrafficInventory` (or similar)
- `adSourceMapillaryCheck` → update accordingly
- `adSourceMapillaryStatus` → update accordingly
- Search for all references to these IDs and update them consistently.

### Step 8: Clean Up Remaining Mapillary References
Search for ALL remaining references to "mapillary", "Mapillary", "mlyDL" in the file and update or remove them as appropriate. This includes:
- The map overlay functions (lines 125165–126425) — these are **Mapillary map layer** functions for the map view. These are SEPARATE from the subtab content and can remain if they serve the map layer toggle. Review whether they're still needed.
- Any variable names, comments, or state references.

## Important Rules
1. **DO NOT modify the source file** (`scripts/mapillary_asset_downloader_v4_7_r2.html`) — only read from it
2. **Copy CSS, HTML, and JS exactly** — do not rename variables, refactor, minify, or "improve" the Traffic Inventory code
3. **The standalone HTML file uses its own CSS class names** (like `.app-header`, `.container`, `.card`, etc.) — these may conflict with the main app's styles. If so, you may need to **scope them** by wrapping the Traffic Inventory content in a container with a unique class and prefixing the CSS selectors. But try without scoping first and only add scoping if there are visible style conflicts.
4. **The standalone HTML file has its own `<script>` with global variables and functions.** Since it will now live inside `index.html`, make sure there are no naming conflicts with existing global functions/variables. If there are conflicts, wrap the Traffic Inventory JS in an IIFE: `(function() { ... })();`
5. **Test that the Analysis tab loads correctly** — clicking "Traffic Inventory" should show the full UI from the standalone file
6. **Test that "Infrastructure Assets" still works** — the first subtab should be unaffected
7. The file `app/index.html` is ~138,000 lines. Be careful with large edits — work section by section.
