# Plan: Add New Safety Focus Categories

## Overview
Add four new safety category cards to the Safety Focus tab:
1. **Animal** - Animal-related crashes
2. **Unrestrained** - Crashes involving unrestrained occupants
3. **Drowsy** - Drowsy driver crashes
4. **Alcohol Only** - Alcohol-only crashes (excluding drug-related)

These will be implemented consistently with the existing 19 safety category cards.

---

## Implementation Steps

### Step 1: Identify Data Column Mappings
**Location:** `index.html` around lines 7514-7544 (COL object)

Need to verify/add column references for:
- Animal crashes: Look for `Animal?` or similar field
- Unrestrained: Look for `Unrestrained?` or seatbelt-related field
- Drowsy: Look for `Drowsy?` or fatigue-related field
- Alcohol Only: Use existing `Alcohol?` field but exclude `Drug?`

**Action:** Search for available column names in the data to confirm field names.

---

### Step 2: Add HTML Safety Cards
**Location:** `index.html` lines 6100-6214 (`.safety-cards-grid`)

Add 4 new card elements following the existing pattern:

```html
<!-- Animal Card -->
<div class="safety-card" data-category="animal">
    <div class="safety-icon">🐾</div>
    <div class="safety-count" id="safety-count-animal">0</div>
    <div class="safety-label">Animal</div>
    <div class="safety-pct" id="safety-pct-animal">0%</div>
</div>

<!-- Unrestrained Card -->
<div class="safety-card" data-category="unrestrained">
    <div class="safety-icon">🪢</div>
    <div class="safety-count" id="safety-count-unrestrained">0</div>
    <div class="safety-label">Unrestrained</div>
    <div class="safety-pct" id="safety-pct-unrestrained">0%</div>
</div>

<!-- Drowsy Card -->
<div class="safety-card" data-category="drowsy">
    <div class="safety-icon">😴</div>
    <div class="safety-count" id="safety-count-drowsy">0</div>
    <div class="safety-label">Drowsy</div>
    <div class="safety-pct" id="safety-pct-drowsy">0%</div>
</div>

<!-- Alcohol Only Card -->
<div class="safety-card" data-category="alcoholOnly">
    <div class="safety-icon">🍷</div>
    <div class="safety-count" id="safety-count-alcoholOnly">0</div>
    <div class="safety-label">Alcohol Only</div>
    <div class="safety-pct" id="safety-pct-alcoholOnly">0%</div>
</div>
```

---

### Step 3: Add CSS Styling
**Location:** `index.html` lines 513-531 (category border colors)

Add unique left border colors for each new category:

```css
.safety-card[data-category="animal"] { border-left: 4px solid #92400e; }      /* Amber-brown */
.safety-card[data-category="unrestrained"] { border-left: 4px solid #7c3aed; } /* Violet */
.safety-card[data-category="drowsy"] { border-left: 4px solid #0891b2; }       /* Cyan-dark */
.safety-card[data-category="alcoholOnly"] { border-left: 4px solid #be185d; }  /* Pink-dark */
```

---

### Step 4: Update JavaScript State Object
**Location:** `index.html` around lines 29967-30003 (safetyState.data)

Add new category data containers:

```javascript
animal: { crashes: [], byRoute: {}, severity: {K:0, A:0, B:0, C:0, O:0}, bySubcategory: {} },
unrestrained: { crashes: [], byRoute: {}, severity: {K:0, A:0, B:0, C:0, O:0}, bySubcategory: {} },
drowsy: { crashes: [], byRoute: {}, severity: {K:0, A:0, B:0, C:0, O:0}, bySubcategory: {} },
alcoholOnly: { crashes: [], byRoute: {}, severity: {K:0, A:0, B:0, C:0, O:0}, bySubcategory: {} },
```

---

### Step 5: Add Category Configuration
**Location:** `index.html` around lines 30006-30195 (SAFETY_CATEGORIES object)

Add configuration for each new category:

```javascript
animal: {
    name: 'Animal Crashes',
    icon: '🐾',
    filter: (row) => {
        const animal = row[COL.ANIMAL] || '';
        return animal === 'Y' || animal === 'Yes' || animal === '1' || animal === 'true';
    },
    subcategoryField: 'Animal Type',  // or appropriate field
    cmfKeywords: ['animal', 'deer', 'wildlife', 'crossing']
},

unrestrained: {
    name: 'Unrestrained Occupant Crashes',
    icon: '🪢',
    filter: (row) => {
        const unrestrained = row[COL.UNRESTRAINED] || '';
        return unrestrained === 'Y' || unrestrained === 'Yes' || unrestrained === '1' || unrestrained === 'true';
    },
    subcategoryField: 'Restraint Use',
    cmfKeywords: ['seatbelt', 'restraint', 'unbelted', 'occupant protection']
},

drowsy: {
    name: 'Drowsy Driver Crashes',
    icon: '😴',
    filter: (row) => {
        const drowsy = row[COL.DROWSY] || '';
        return drowsy === 'Y' || drowsy === 'Yes' || drowsy === '1' || drowsy === 'true';
    },
    subcategoryField: 'Driver Condition',
    cmfKeywords: ['drowsy', 'fatigue', 'asleep', 'tired', 'rest area']
},

alcoholOnly: {
    name: 'Alcohol Only Crashes',
    icon: '🍷',
    filter: (row) => {
        const alcohol = row[COL.ALCOHOL] || '';
        const drug = row[COL.DRUG] || '';
        const isAlcohol = alcohol === 'Y' || alcohol === 'Yes' || alcohol === '1' || alcohol === 'true';
        const isDrug = drug === 'Y' || drug === 'Yes' || drug === '1' || drug === 'true';
        return isAlcohol && !isDrug;  // Alcohol but NOT drug-related
    },
    subcategoryField: 'BAC Level',
    cmfKeywords: ['alcohol', 'impaired', 'DUI', 'DWI', 'BAC']
},
```

---

### Step 6: Add Column Constants (if needed)
**Location:** `index.html` around lines 7514-7544 (COL object)

Verify and add any missing column mappings:

```javascript
ANIMAL: 'Animal?',           // Verify actual column name in data
UNRESTRAINED: 'Unrestrained?', // Verify actual column name in data
DROWSY: 'Drowsy?',           // Verify actual column name in data
// ALCOHOL and DRUG already exist
```

---

### Step 7: Update Cross Analysis (Optional Enhancement)
**Location:** `index.html` around lines 30429-30560 (calculateCrossAnalysis)

Consider adding relevant cross-analysis combinations:
- Animal + Nighttime (deer crashes at night)
- Drowsy + Nighttime
- Unrestrained + Speed
- Alcohol Only + Nighttime

---

## Testing Plan

1. **Visual Verification:**
   - Confirm all 4 new cards display in the grid
   - Verify icons, colors, and styling match existing cards
   - Check responsive layout on different screen sizes

2. **Functional Testing:**
   - Click each new card and verify detail panel shows
   - Confirm counts are accurate based on data
   - Test severity and date filters work with new categories
   - Verify charts render correctly for each category

3. **Data Validation:**
   - Cross-check counts against raw data
   - Verify "Alcohol Only" correctly excludes drug-related crashes
   - Confirm EPDO calculations are accurate

---

## Files to Modify

| File | Changes |
|------|---------|
| `index.html` | HTML cards, CSS styles, JS state, JS category config |

---

## Estimated Changes

- ~40 lines of HTML (4 cards)
- ~4 lines of CSS (border colors)
- ~10 lines of JS state initialization
- ~50 lines of JS category configuration
- Optional: ~20 lines for cross-analysis combinations

**Total: ~125 lines of code**

---

## Notes

- Using emoji icons consistent with existing categories (🐾, 🪢, 😴, 🍷)
- Border colors chosen to be distinct from existing 19 categories
- "Alcohol Only" is differentiated from existing "Impaired Driving" (which includes both alcohol and drugs)
- May need to adjust column names based on actual data field names
