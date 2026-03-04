# PlotCode Prompt: Make Jurisdiction Handling Fully Dynamic (State-Agnostic)

## Overview

This codebase is a multi-state crash analysis tool. The user selects **State → County/Jurisdiction → Road Type** in the **Upload Data tab** of `app/index.html`. However, several components are **hard-coded to specific Virginia or Colorado jurisdictions** instead of dynamically using whatever the user selected. Fix all of these so the entire app is fully state/jurisdiction agnostic.

There are **5 components** to fix across **5 files**, plus parent-side sync changes in `app/index.html`.

---

## ISSUE 1: Crash Data Validation Engine (iframe)

**File:** `scripts/crash-data-validator-v13.html`

### Problem
Lines ~3085-3096 contain a hard-coded `JURISDICTIONS` object with only 10 pre-set jurisdictions (5 Virginia, 5 Colorado):

```javascript
const JURISDICTIONS = {
  'va_henrico':      { state: 'virginia', county: 'henrico', label: 'Henrico County, VA', bounds: {...}},
  'va_chesterfield': { state: 'virginia', county: 'chesterfield', label: 'Chesterfield County, VA', bounds: {...}},
  'va_hanover':      { state: 'virginia', county: 'hanover', label: 'Hanover County, VA', bounds: {...}},
  'va_richmond':     { state: 'virginia', county: 'richmond', label: 'City of Richmond, VA', bounds: {...}},
  'va_fairfax':      { state: 'virginia', county: 'fairfax', label: 'Fairfax County, VA', bounds: {...}},
  'co_douglas':      { state: 'colorado', county: 'douglas', label: 'Douglas County, CO', bounds: {...}},
  'co_arapahoe':     { state: 'colorado', county: 'arapahoe', label: 'Arapahoe County, CO', bounds: {...}},
  'co_denver':       { state: 'colorado', county: 'denver', label: 'City & County of Denver, CO', bounds: {...}},
  'co_jefferson':    { state: 'colorado', county: 'jefferson', label: 'Jefferson County, CO', bounds: {...}},
  'co_elpaso':       { state: 'colorado', county: 'elpaso', label: 'El Paso County, CO', bounds: {...}},
};
```

Lines ~815-828 have a hard-coded `<select>` dropdown with only those 10 jurisdictions as `<option>` and `<optgroup>` elements.

### What Happens Now
The parent app (`app/index.html`) sends jurisdiction info via `postMessage` with type `'validator-set-jurisdiction'`. The validator tries to match the key (e.g., `"va_henry"`) against the hard-coded `JURISDICTIONS` object. If it doesn't find a match, it falls back to the `fallback` object with `{state, county, label, bounds}`. **The fallback path actually works** but the preset dropdown is useless for any jurisdiction not in the hard-coded list.

### Fix Required
1. **Replace the hard-coded `JURISDICTIONS` object** with an initially empty object: `let JURISDICTIONS = {};`
2. **Add a new postMessage handler** for type `'validator-set-jurisdictions'` (plural) that receives ALL jurisdictions from the parent and populates the `JURISDICTIONS` object and rebuilds the dropdown, exactly like the traffic-inventory.html already does. Group the dropdown options by state using `<optgroup>` elements.
3. **Update the HTML dropdown** to start empty: `<select id="jurisdictionPreset"><option value="">— Choose Jurisdiction —</option></select>` (remove all hard-coded `<option>` and `<optgroup>` elements).
4. **Keep the existing `'validator-set-jurisdiction'` handler** (singular) as-is — it already has the fallback path that works for any jurisdiction.
5. **Add a ready signal**: When the validator iframe loads, it should send `window.parent.postMessage({ type: 'validator-ready' }, '*');` so the parent knows to send jurisdictions.

### Corresponding Parent-Side Changes (`app/index.html`)
1. **Add a function `sendAllJurisdictionsToValidator()`** that mirrors `sendAllJurisdictionsToTrafficInventory()` — it iterates over `appConfig.states` and all their jurisdictions, builds a flat object with keys like `'va_henrico'` (stateAbbr_jurisId), and sends it to the validator iframe via `postMessage` with type `'validator-set-jurisdictions'`. Each entry should include `{ state, county, label, bounds }` matching the validator's expected format.
2. **Add a message listener** for `'validator-ready'` that calls `sendAllJurisdictionsToValidator()` followed by `syncJurisdictionToValidator()`.
3. **In `saveJurisdictionSelection()`** and **`handleStateSelection()`**, also call `syncJurisdictionToValidator()` (if not already called) so the validator updates when the user changes jurisdiction.

---

## ISSUE 2: Traffic Inventory (iframe)

**File:** `app/traffic-inventory.html`

### Problem
Lines ~760-775 contain a hard-coded `JURISDICTIONS` object with **only 15 Virginia locations** (albemarle, alexandria, arlington, chesapeake, chesterfield, fairfax_county, hanover, henrico, loudoun, newport_news, norfolk, prince_william, richmond_city, roanoke, stafford, virginia_beach).

### What Happens Now
The parent already sends all jurisdictions via `'ti-set-jurisdictions'` postMessage, and the traffic-inventory.html **does** receive them and rebuild the dropdown (lines ~900-934). However, the hard-coded initial `JURISDICTIONS` object means:
- On initial load (before postMessage arrives), only Virginia jurisdictions show
- If the postMessage race condition fails, the user is stuck with Virginia-only options

### Fix Required
1. **Replace the hard-coded `JURISDICTIONS` object** with an empty object: `const JURISDICTIONS = {};`
2. **Show a "Loading jurisdictions..." placeholder** in the dropdown until the parent sends the full list.
3. The existing `'ti-set-jurisdictions'` and `'ti-set-jurisdiction'` message handlers are already correct — no changes needed there.
4. Ensure the `'ti-ready'` postMessage is sent reliably on load so the parent responds with jurisdictions.

---

## ISSUE 3: Asset Deficiency (iframe)

**File:** `app/asset-deficiency.html`

### Problem
Lines ~166-170 have **hard-coded Virginia/Henrico data URLs** in the HTML:

```html
<input id="uCr" value="https://data.aicreatesai.com/virginia/henrico/all_roads.csv">
<input id="uIn" value="https://data.aicreatesai.com/virginia/henrico/traffic-inventory.csv">
```

Line ~184 has a hard-coded FIPS code:
```html
<input id="cFips" value="51087" placeholder="51087">
```

The badge text says `"Virginia Roads + R2"` — also hard-coded.

### What Happens Now
The parent sends config via `'ad-config'` postMessage with FIPS, bbox, mapCenter, mapZoom, jurisdictionName, and state. The asset-deficiency iframe **only updates the FIPS field** from this config. It does NOT update the data URLs or the badge text.

### Fix Required
1. **Clear the hard-coded default values** for the data URL inputs. Set them to empty or a placeholder: `value=""` with `placeholder="Will be set from parent app"`.
2. **Clear the hard-coded FIPS**: Set `value=""` with `placeholder="Set by parent app"`.
3. **Change the badge text** from hard-coded `"Virginia Roads + R2"` to a generic placeholder like `"Roads + R2"` that will be updated dynamically.
4. **Update the `'ad-config'` message handler** to also:
   - Build and set the crash data URL: `https://data.aicreatesai.com/{state}/{county}/all_roads.csv`
   - Build and set the traffic inventory URL: `https://data.aicreatesai.com/{state}/{county}/traffic-inventory.csv`
   - Update the badge text to `"{JurisdictionName} Roads + R2"` or similar
   - Update the FIPS placeholder to match the new value
5. **The parent's `sendConfigToAssetDeficiency()` function** should also include the `county` (jurisdiction folder key) in the config message, since the asset deficiency iframe needs it to build R2 data paths. Currently it only sends `state` but not the jurisdiction key/folder name.

### Parent-Side Changes (`app/index.html`)
In the `sendConfigToAssetDeficiency()` function (around line 54260), add `county: jurisdictionId` to the config object being sent:

```javascript
frame.contentWindow.postMessage({
    type: 'ad-config',
    config: {
        fips: jurisdictionConfig?.stateCountyFips || jurisdictionConfig?.fips || '',
        bbox: jurisdictionConfig?.bbox || null,
        mapCenter: jurisdictionConfig?.mapCenter || null,
        mapZoom: jurisdictionConfig?.mapZoom || 10,
        jurisdictionName: jurisdictionConfig?.name || jurisdictionId,
        state: stateKey,
        county: jurisdictionId  // ADD THIS — needed for R2 data paths
    }
}, '*');
```

---

## ISSUE 4: Inventory Manager (standalone file, needs iframe integration)

**File:** `scripts/crash_lens_asset_inventory_manager_v10.html`

### Problem
This is a standalone MUTCD traffic control device inventory editor that is **not yet integrated as an iframe** in the main app's Analysis tab. It has multiple hard-coded jurisdiction references:

**Hard-coded State/County dropdowns (lines ~163-164):**
```html
<div class="cfg-row"><label>State</label><select id="stSel"><option value="virginia">Virginia</option><option value="colorado">Colorado</option><option value="maryland">Maryland</option></select></div>
<div class="cfg-row"><label>County</label><select id="coSel"><option value="henrico">Henrico</option><option value="chesterfield">Chesterfield</option><option value="hanover">Hanover</option></select></div>
```

**Hard-coded Virginia in address search (line ~686):**
```javascript
const r = await fetch('https://nominatim.openstreetmap.org/search?format=json&limit=1&q=' + encodeURIComponent(q + ', Virginia'));
```

**Config functions use these dropdowns (lines ~440-443):**
```javascript
function getR2Key() { return $('stSel').value + '/' + $('coSel').value + '/traffic-inventory.csv' }
function getLedgerKey() { return $('stSel').value + '/' + $('coSel').value + '/traffic-inventory-edits.json' }
```

**No postMessage integration** — the file has zero `postMessage` or `addEventListener('message')` calls.

### Fix Required — Part A: Make the file itself dynamic
1. **Replace the hard-coded State `<select>`** with an empty dropdown: `<select id="stSel"><option value="">Loading...</option></select>`
2. **Replace the hard-coded County `<select>`** with an empty dropdown: `<select id="coSel"><option value="">Loading...</option></select>`
3. **Fix the address search function (`searchAddr`)** — replace the hard-coded `', Virginia'` with a dynamic state name from the current selection: use `$('stSel').selectedOptions[0]?.textContent || ''` to get the display name of the selected state.
4. **Add postMessage handlers** so when embedded as an iframe, the parent can send jurisdictions and sync the selected one:
   - Listen for `'im-set-jurisdictions'` — receive all jurisdictions, populate the State and County dropdowns grouped by state
   - Listen for `'im-set-jurisdiction'` — receive the currently selected jurisdiction key, auto-select the correct state and county
   - Listen for `'im-config'` — receive R2 config (pub URL, worker URL) from parent so the file doesn't rely solely on localStorage
5. **Add a ready signal**: `window.parent.postMessage({ type: 'im-ready' }, '*');` when the iframe loads, so the parent knows to send data.
6. **Keep the localStorage config (`loadCfg`/`saveCfg`) as fallback** for when the file is opened standalone (not as an iframe).

### Fix Required — Part B: Integrate as iframe in `app/index.html`
1. **Add an "Inventory Manager" subtab button** in the Analysis sub-navigation (around line 6494-6497). Currently the subtabs are: Infrastructure Assets, Traffic Inventory, Asset Deficiency, Sign Deficiency. Add a new button between Traffic Inventory and Asset Deficiency:
   ```html
   <button class="analysis-subtab" data-subtab="inventorymanager" onclick="switchAnalysisSubtab('inventorymanager')">📁 Inventory Manager</button>
   ```
2. **Add the iframe container** (between the traffic inventory and asset deficiency sections, around line 8125):
   ```html
   <!-- INVENTORY MANAGER SUB-TAB (iframe isolation) -->
   <div id="analysis-inventorymanager" class="analysis-subtab-content" style="display:none;">
   <div class="im-iframe-wrapper" style="width:100%;height:calc(100vh - 180px);min-height:600px;border-radius:var(--radius);overflow:hidden;border:1px solid var(--gray-light);background:#f1f5f9">
   <iframe id="inventoryManagerFrame" class="im-iframe" style="width:100%;height:100%;border:none;display:block" src="about:blank" title="Inventory Manager - Asset Editor"></iframe>
   </div>
   </div><!-- End of analysis-inventorymanager -->
   ```
3. **Add lazy-loading** in the `switchAnalysisSubtab()` function (around line 54140):
   ```javascript
   } else if (subtab === 'inventorymanager') {
       const frame = document.getElementById('inventoryManagerFrame');
       if (frame && frame.src === 'about:blank') {
           frame.src = '../scripts/crash_lens_asset_inventory_manager_v10.html';
           console.log('[Analysis] Inventory Manager iframe loaded');
       }
   }
   ```
4. **Add sync functions**:
   ```javascript
   function sendAllJurisdictionsToInventoryManager() {
       const frame = document.getElementById('inventoryManagerFrame');
       if (!frame || !frame.contentWindow || frame.src === 'about:blank') return;
       // Build jurisdictions object similar to sendAllJurisdictionsToTrafficInventory()
       // Send via postMessage type 'im-set-jurisdictions'
   }

   function syncJurisdictionToInventoryManager() {
       const frame = document.getElementById('inventoryManagerFrame');
       if (!frame || !frame.contentWindow || frame.src === 'about:blank') return;
       const jurisdictionKey = getActiveJurisdictionId();
       const stateKey = _getActiveStateKey();
       if (jurisdictionKey && stateKey) {
           frame.contentWindow.postMessage({
               type: 'im-set-jurisdiction',
               state: stateKey,
               jurisdictionKey: jurisdictionKey
           }, '*');
       }
   }
   ```
5. **Add the `'im-ready'` listener**:
   ```javascript
   window.addEventListener('message', function(evt) {
       if (!evt.data || evt.data.type !== 'im-ready') return;
       sendAllJurisdictionsToInventoryManager();
       syncJurisdictionToInventoryManager();
   });
   ```

---

## ISSUE 5: Keeping Everything In Sync

### Current Sync Functions in `app/index.html`
These functions already exist and handle syncing jurisdiction changes to iframes:

- `syncJurisdictionToValidator()` — sends current jurisdiction to validator iframe
- `syncJurisdictionToTrafficInventory()` — sends current jurisdiction key to traffic inventory
- `sendConfigToAssetDeficiency()` — sends full config to asset deficiency

After the fix, there will be **4 sync targets** (adding Inventory Manager).

### What to Verify/Fix
1. **`saveJurisdictionSelection()`** — When the user changes the jurisdiction dropdown, ensure ALL FOUR sync functions are called:
   ```javascript
   syncJurisdictionToValidator();
   syncJurisdictionToTrafficInventory();
   sendConfigToAssetDeficiency();
   syncJurisdictionToInventoryManager();  // NEW
   ```
2. **`handleStateSelection()`** — When the user changes the state, ensure jurisdiction dropdowns are rebuilt AND all iframes are re-synced after the new state's jurisdictions load.
3. **On initial load / tab switch** — When the user first opens the Upload Data tab or the Analysis tab (which contains traffic inventory, inventory manager, and asset deficiency), ensure the iframes receive the current jurisdiction if data is already loaded.

---

## IMPORTANT CONSTRAINTS

1. **Do NOT break existing functionality.** The app works correctly for jurisdictions that happen to be in the hard-coded lists. The fix must make it work for ALL jurisdictions from any state.
2. **Preserve the postMessage protocol.** The existing message types (`validator-set-jurisdiction`, `ti-set-jurisdiction`, `ti-set-jurisdictions`, `ad-config`, etc.) should be preserved. Add new ones only where needed (like `validator-set-jurisdictions`, `im-set-jurisdictions`, `im-set-jurisdiction`, `im-ready`).
3. **The R2 data path pattern is:** `https://data.aicreatesai.com/{state_r2Prefix}/{jurisdiction_key}/` — where `state_r2Prefix` comes from `appConfig.states[stateKey].r2Prefix` and `jurisdiction_key` is the jurisdiction ID (e.g., "henry", "douglas", "henrico").
4. **Keep the fallback logic in the validator.** The fallback path in the validator's `'validator-set-jurisdiction'` handler is good — it handles any jurisdiction not in the presets. But now that presets will be dynamically populated, most jurisdictions should match directly.
5. **No duplicate function names** — JavaScript silently overwrites functions. Always search before creating new ones.
6. **Inventory Manager must work both standalone and as iframe.** Detect iframe mode: `const embedded = (window !== window.parent);` — if embedded, rely on postMessage; if standalone, fall back to localStorage config and hard-coded dropdowns.

---

## FILES TO MODIFY

| File | Changes |
|------|---------|
| `scripts/crash-data-validator-v13.html` | Remove hard-coded JURISDICTIONS & dropdown options; add `validator-set-jurisdictions` handler; add `validator-ready` postMessage |
| `app/traffic-inventory.html` | Replace hard-coded JURISDICTIONS with empty object; add loading placeholder |
| `app/asset-deficiency.html` | Remove hard-coded Virginia/Henrico URLs and FIPS; update `ad-config` handler to set data URLs and badge dynamically |
| `scripts/crash_lens_asset_inventory_manager_v10.html` | Remove hard-coded state/county dropdowns; add postMessage handlers (`im-set-jurisdictions`, `im-set-jurisdiction`, `im-ready`); fix address search to use dynamic state name |
| `app/index.html` | Add Inventory Manager subtab + iframe; add `sendAllJurisdictionsToValidator()` + `sendAllJurisdictionsToInventoryManager()`; add `validator-ready` + `im-ready` listeners; add `county` to asset deficiency config; add `syncJurisdictionToInventoryManager()`; verify ALL sync calls in `saveJurisdictionSelection()` and `handleStateSelection()` |

---

## TESTING CHECKLIST

After making changes, verify:

- [ ] Select Virginia → Henry County → validator iframe shows "Henry County" and loads correct data
- [ ] Select Colorado → Douglas County → validator iframe switches to Douglas County correctly
- [ ] Select any state/jurisdiction not in the old hard-coded lists → validator still works via dynamic sync
- [ ] Traffic Inventory dropdown shows ALL jurisdictions from the selected state (not just 15 Virginia ones)
- [ ] Asset Deficiency data URLs update to match the selected state/jurisdiction (not stuck on virginia/henrico)
- [ ] Asset Deficiency FIPS field updates when jurisdiction changes
- [ ] Asset Deficiency badge text updates to show current jurisdiction name (not "Virginia Roads + R2")
- [ ] Inventory Manager subtab appears in Analysis tab between Traffic Inventory and Asset Deficiency
- [ ] Inventory Manager iframe loads when subtab is clicked
- [ ] Inventory Manager state/county dropdowns are populated from parent's jurisdiction data
- [ ] Inventory Manager auto-selects the jurisdiction matching the Upload Data tab selection
- [ ] Inventory Manager address search uses the dynamically selected state (not hard-coded "Virginia")
- [ ] Changing jurisdiction in the Upload Data tab updates ALL FOUR iframes (validator, traffic inventory, inventory manager, asset deficiency)
- [ ] Changing state in the Upload Data tab resets jurisdiction and updates all iframes
- [ ] Inventory Manager still works as standalone file (opened directly in browser, not as iframe)
- [ ] No console errors related to jurisdiction sync
- [ ] Existing functionality (crash data loading, map, analysis tabs) still works normally
