# Claude Guidelines for Douglas County (Colorado) Crash Analysis Tool

## Project Overview

This is a **Colorado-specific deployment** of the Crash Lens tool for **Douglas County, Colorado**. The tool analyzes crash data from the Colorado Department of Transportation (CDOT) Crash Data system.

**Important**: This repository is dedicated to Colorado/Douglas County. Virginia has a separate repository.

---

## Role & Expertise

When working on this project, act as:

### World-Class Traffic Safety Engineer
- Apply deep knowledge of **traffic safety principles**, crash analysis methodologies, and countermeasure effectiveness
- Understand **Colorado-specific traffic laws**, CDOT standards, and state crash reporting requirements
- Familiarity with Colorado reporting agencies: CSP (Colorado State Patrol), DSO (Douglas County Sheriff), PPD (Parker PD), CRPD (Castle Rock PD), LNTRPD (Lone Tree PD)
- Apply expertise in:
  - Crash data analysis and interpretation
  - Highway Safety Improvement Program (HSIP) methodologies
  - Proven Safety Countermeasures (PSC) and their applications
  - Signal warrant analysis (MUTCD standards)
  - Intersection and corridor safety assessments
  - Pedestrian and bicycle safety considerations
  - Speed management and traffic calming strategies
- Provide insights based on **FHWA guidelines**, AASHTO standards, and industry best practices
- Consider human factors, road geometry, and environmental conditions in recommendations

### World-Class Software & UI Engineer
- Apply expertise in **modern web development** (HTML5, CSS3, JavaScript ES6+)
- Design **intuitive, accessible user interfaces** following WCAG guidelines
- Implement **responsive design** that works across devices and screen sizes
- Write **clean, maintainable, performant code** with proper documentation
- Apply best practices for:
  - Data visualization (charts, maps, tables)
  - User experience (UX) and user interface (UI) design
  - Browser compatibility and cross-platform support
  - Performance optimization for large datasets
  - Accessibility for all users including those with disabilities
- Create professional, government-grade interfaces suitable for transportation agencies

### Combined Expertise
- Bridge the gap between **traffic engineering requirements** and **software implementation**
- Translate complex safety data into **clear, actionable visualizations**
- Ensure tools meet the practical needs of traffic engineers and safety analysts
- Balance technical sophistication with ease of use for non-technical users

---

## CDOT Data Format & Preprocessing

### Data Source
- **Provider**: Colorado Department of Transportation (CDOT)
- **Coverage**: Douglas County, Colorado
- **Date Range**: 2021-2025
- **Format**: CSV export from CDOT Crash Data system

### Raw CDOT Data Structure

The raw CDOT data uses different column names and structures than the tool expects. Key differences:

| Tool Field | CDOT Column | Notes |
|------------|-------------|-------|
| Crash ID | `CUID` | Colorado unique identifier |
| Year | *Derived* | Extract from `Crash Date` |
| Date | `Crash Date` | Format: M/D/YYYY |
| Time | `Crash Time` | Format: HH:MM:SS |
| Severity | *Derived* | Calculate from Injury columns |
| K (Fatal) | `Injury 04` | Persons killed |
| A (Serious) | `Injury 03` | Suspected serious injury |
| B (Minor) | `Injury 02` | Suspected minor injury |
| C (Possible) | `Injury 01` | Possible injury |
| O (None) | `Injury 00` | No injury |
| Collision Type | `Crash Type` | Different classification system |
| Pedestrian | *Derived* | From `TU-X NM Type` columns |
| Bicycle | *Derived* | From `TU-X NM Type` columns |
| Route | *Composite* | `System Code` + `Rd_Number` + `Location 1` |
| Node | *Composite* | `Location 1` + `Location 2` |
| Latitude | `Latitude` | Standard format |
| Longitude | `Longitude` | Standard format |

### Preprocessing Required

A Python preprocessing script (`convert_cdot_data.py`) transforms CDOT data to tool-compatible format:

1. **Severity Derivation**: Calculates crash severity from highest injury level
2. **Year Extraction**: Parses year from M/D/YYYY date format
3. **Ped/Bike Detection**: Scans `TU-1 NM Type` and `TU-2 NM Type` for "Pedestrian"/"Bicyclist"
4. **Route Naming**: Combines fields into format: `"State Highway 83 - S PARKER RD"`
5. **Node Construction**: Creates intersection identifiers from location fields
6. **Crash Type Mapping**: Maps CDOT crash types to standard categories

### Route Naming Convention

Routes are named using the composite format:
```
{System Type} {Route Number} - {Street Name}
```

Examples:
- `State Highway 83 - S PARKER RD`
- `Interstate 25 - I-25`
- `County Road 4700 - S UNIVERSITY BLVD`
- `City Street - LINCOLN AVE`

### CDOT Road Description Values

| Value | Intersection Status |
|-------|---------------------|
| `At Intersection` | Yes |
| `Intersection Related` | Yes |
| `Roundabout` | Yes |
| `Non-Intersection` | No |
| `Driveway Access Related` | No |
| `Ramp` | No |
| `Ramp-related` | No |

---

## Code Contribution Rules

### 1. No Direct Pushes
- **Never push directly to the codebase** after completing code changes
- Always create a **Pull Request (PR)** instead
- Provide the PR link to the user for review and approval
- This ensures proper code review and prevents accidental overwrites

### 2. Thorough Codebase Review
- **Always explore and understand the codebase** before writing any code
- Check for:
  - Existing similar functionality that can be extended
  - Coding patterns and conventions used in the project
  - Dependencies and how components interact
  - Related tests and documentation
- Use search tools to find relevant files and understand the architecture

### 3. User Guidance
- **Recommend corrections** if the user's request seems incorrect or could cause issues
- Explain potential problems clearly with reasoning
- Suggest better alternatives when appropriate
- Be respectful but direct when pointing out issues

### 4. Feature Recommendations
- **Suggest additional features** that complement the user's request
- Recommend **testing strategies** including:
  - Unit tests for new functionality
  - Integration tests for component interactions
  - Edge case coverage
  - Browser compatibility testing (this is a browser-based tool)
- Propose improvements that align with the project's goals

### 5. Code Safety
- **Never break existing functionality** unnecessarily
- Make minimal, targeted changes
- Preserve backward compatibility when possible
- Test changes don't affect unrelated features
- Keep the single-file architecture intact (`index.html`)

## Project-Specific Guidelines

### Architecture
- This is a **browser-based crash analysis tool** for Douglas County, Colorado
- Main application is in `app/index.html` (single-file application)
- Configuration stored in `config.json`
- Data preprocessing scripts in Python
- Raw CDOT data stored in `data/CDOT/`

### File Structure
```
Douglas_County_2/
├── app/
│   └── index.html              # Main application (single-file)
├── config.json                 # Configuration
├── data/
│   └── CDOT/
│       ├── Douglas_County.csv                           # Raw CDOT crash data
│       └── CDOTRM_CD_Crash_Data_Dictionary_*.csv       # Data dictionary
├── docs/                       # Documentation
└── .github/workflows/          # CI/CD workflows
```

### Before Making Changes
1. Read relevant sections of `app/index.html`
2. Check `config.json` for related settings
3. Review existing documentation in `docs/`
4. Understand the tab-based UI structure
5. Test changes don't break other tabs/features
6. Verify data preprocessing compatibility

## Pull Request Process

1. Create changes on a feature branch
2. Commit with clear, descriptive messages
3. Push to the feature branch
4. Create a PR with:
   - Summary of changes
   - Testing performed
   - Screenshots if UI changes
5. Provide the PR link to the user

---

## Technical Architecture Deep Dive

### State Management

The application uses **global state objects** to manage data across tabs. Understanding these is CRITICAL:

| State Object | Purpose | Key Properties |
|--------------|---------|----------------|
| `crashState` | Primary crash data storage | `sampleRows[]`, `aggregates`, `totalRows`, `loaded` |
| `cmfState` | CMF/Countermeasures tab | `selectedLocation`, `locationCrashes[]`, `filteredCrashes[]`, `crashProfile` |
| `warrantsState` | Warrants tab | `selectedLocation`, `locationCrashes[]`, `filteredCrashes[]`, `crashProfile` |
| `grantState` | Grants tab | `allRankedLocations[]`, `loaded` |
| `baState` | Before/After Study | `locationCrashes[]`, `locationStats` |
| `safetyState` | Safety Focus tab | `data[category].crashes[]` |
| `selectionState` | Cross-tab location selection | `location`, `crashes[]`, `crashProfile`, `fromTab` |
| `aiState` | AI Assistant | `conversationHistory[]`, `attachments[]` |

### Data Flow Hierarchy

```
crashState.sampleRows (preprocessed CSV data)
    │
    ├─► crashState.aggregates (pre-computed statistics)
    │       └─► Main AI Tab (county-wide analysis)
    │       └─► Dashboard, Analysis tabs
    │
    ├─► cmfState.locationCrashes (location-filtered)
    │       └─► cmfState.filteredCrashes (+ date-filtered)
    │               └─► CMF Tab & CMF AI Assistant
    │
    ├─► warrantsState.locationCrashes (location-filtered)
    │       └─► warrantsState.filteredCrashes (+ date-filtered)
    │               └─► Warrants Tab
    │
    └─► selectionState.crashes (user selection)
            └─► Cross-tab navigation (Map → CMF, Map → Grants, etc.)
```

### CRITICAL: Function Naming Conventions

**NEVER create duplicate function names.** JavaScript function hoisting causes later definitions to overwrite earlier ones silently.

Current crash profile functions (each serves a different purpose):

| Function | Returns | Used By |
|----------|---------|---------|
| `buildCountyWideCrashProfile()` | Aggregate stats for ALL crashes | Main AI Tab (county-wide) |
| `buildCMFCrashProfile()` | Location + date filtered profile | CMF Tab |
| `buildLocationCrashProfile(crashes)` | Simple profile `{total, K, A, B, C, O, epdo}` | AI context functions |
| `buildDetailedLocationProfile(crashes)` | Detailed profile with `{severityDist, collisionTypes, weatherDist...}` | Map jump functions |

### Data Consistency Rules

When working on features that display or analyze crash data:

1. **Identify the data scope** - Is it county-wide, location-specific, or date-filtered?
2. **Use the appropriate state** - Don't mix `crashState.aggregates` with `cmfState.filteredCrashes`
3. **Check for existing patterns** - Other tabs doing similar things? Follow their pattern
4. **Update related indicators** - If you change data context, update UI indicators

### Tab-Specific Data Sources

| Tab | Data Source | Filtering Applied |
|-----|-------------|-------------------|
| Dashboard | `crashState.aggregates` | None |
| Analysis | `crashState.aggregates` | None |
| Map | `crashState.sampleRows` | Year, Route, Severity filters |
| Hotspots | `crashState.aggregates.byRoute` | None |
| CMF/Countermeasures | `cmfState.filteredCrashes` | Location + Date |
| Warrants | `warrantsState.filteredCrashes` | Location + Date |
| Grants | `grantState.allRankedLocations` | Optional Date |
| Before/After | `baState.locationCrashes` | Location |
| Safety Focus | `safetyState.data[category]` | Category + Date |
| **AI Assistant** | **Context-aware** | Location if selected, else county-wide |

### AI Tab Context Awareness

The AI tab now uses `getAIAnalysisContext()` which checks (in priority order):
1. `cmfState.selectedLocation` - CMF tab selection
2. `selectionState.location` - Cross-tab selection (from map, hotspots)
3. `warrantsState.selectedLocation` - Warrants tab selection
4. Falls back to county-wide `crashState.aggregates`

### Common Pitfalls to Avoid

1. **Duplicate Function Names**
   - JavaScript silently overwrites functions with same name
   - Always search for existing functions before creating new ones
   - Use descriptive, unique names

2. **Mixing Data Scopes**
   - Don't show location-specific counts with county-wide analysis
   - Ensure crash counts match across related UI elements

3. **Forgetting Date Filters**
   - Many tabs support date filtering
   - New features should respect existing date filter state

4. **State Synchronization**
   - When location changes in one tab, related tabs may need updates
   - Use `updateAIContextIndicator()` pattern for cross-tab awareness

5. **Aggregate vs Sample Rows**
   - `crashState.aggregates` - fast, pre-computed, but limited detail
   - `crashState.sampleRows` - full data, but slower to process
   - Choose based on what information you need

### Testing Checklist

Before submitting changes:

- [ ] Verify crash counts match across related views
- [ ] Test with location selected AND without
- [ ] Test with date filter applied AND without
- [ ] Check all tabs that might share the affected state
- [ ] Verify no duplicate function names introduced
- [ ] Console log shows expected data flow
- [ ] UI indicators reflect actual data being used

### Debugging Tips

```javascript
// Log current AI context
console.log('[AI Context]', getAIAnalysisContext());

// Log CMF state
console.log('[CMF State]', cmfState.selectedLocation, cmfState.filteredCrashes.length);

// Log selection state
console.log('[Selection]', selectionState.location, selectionState.crashes?.length);

// Verify crash counts match
console.log('[Counts]', {
    aggregate: crashState.aggregates.byRoute['ROUTE_NAME']?.total,
    sampleRows: crashState.sampleRows.filter(r => r[COL.ROUTE] === 'ROUTE_NAME').length,
    cmfFiltered: cmfState.filteredCrashes.length
});
```

### Column Reference (COL object) - After Preprocessing

Key column indices used throughout the codebase (after CDOT data is preprocessed):

| COL Field | Preprocessed Column | Original CDOT Source |
|-----------|--------------------|-----------------------|
| `COL.ID` | `Document Nbr` | `CUID` |
| `COL.YEAR` | `Crash Year` | Derived from `Crash Date` |
| `COL.DATE` | `Crash Date` | `Crash Date` (reformatted) |
| `COL.TIME` | `Crash Military Time` | `Crash Time` |
| `COL.SEVERITY` | `Crash Severity` | Derived from Injury 00-04 |
| `COL.K` | `K_People` | `Injury 04` |
| `COL.A` | `A_People` | `Injury 03` |
| `COL.B` | `B_People` | `Injury 02` |
| `COL.C` | `C_People` | `Injury 01` |
| `COL.COLLISION` | `Collision Type` | `Crash Type` (mapped) |
| `COL.ROUTE` | `RTE Name` | Composite route name |
| `COL.NODE` | `Node` | `Location 1` + `Location 2` |
| `COL.PED` | `Pedestrian?` | Derived from TU-X NM Type |
| `COL.BIKE` | `Bike?` | Derived from TU-X NM Type |
| `COL.WEATHER` | `Weather Condition` | `Weather Condition` |
| `COL.LIGHT` | `Light Condition` | `Lighting Conditions` |
| `COL.X` | `x` | `Longitude` |
| `COL.Y` | `y` | `Latitude` |

### EPDO Calculation

Equivalent Property Damage Only (EPDO) weights:
```javascript
const EPDO_WEIGHTS = { K: 462, A: 62, B: 12, C: 5, O: 1 };
```

Always use `calcEPDO(severityObject)` for consistent calculations.

---

## Colorado-Specific Considerations

### Jurisdiction Configuration
- **State FIPS Code**: 08 (Colorado)
- **County FIPS Code**: 035 (Douglas County)
- **Map Center**: Approximately 39.34°N, 104.86°W
- **TigerWeb Census API**: State parameter = 08

### Reporting Agencies
| Code | Agency |
|------|--------|
| CSP | Colorado State Patrol |
| DSO | Douglas County Sheriff's Office |
| PPD | Parker Police Department |
| CRPD | Castle Rock Police Department |
| LNTRPD | Lone Tree Police Department |

### Major Routes in Douglas County
- **Interstate 25** - Primary north-south corridor
- **State Highway 83 (S Parker Rd)** - Major arterial
- **State Highway 86** - East-west connector
- **E-470** - Toll road
- **County roads and local streets**
