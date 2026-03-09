# Crash Lens Professional Report System - Implementation Plan

**Date:** March 9, 2026
**Author:** Development Team
**Version:** 2.0
**Status:** Ready for Implementation

---

## 1. Executive Summary

This plan redesigns the Crash Lens report system from 10 loosely-organized report types into a **categorized, professional, subscription-worthy reporting suite** with 17 report types organized into 4 categories. Every Explore tab gets a dedicated, professionally designed report that mirrors the tab's data and visualizations in a polished PDF format.

### Key Principles
- **Every Explore tab = One dedicated professional report**
- **Consistent professional design**: Cover page, TOC, executive summary, KPI cards, charts-as-tables, branded header/footer, recommendations
- **Follow the `generateStandardReportPDF()` pattern** already established in the codebase (jsPDF + autoTable)
- **No duplicate function names** (per CLAUDE.md critical rule)
- **Backward compatible** with existing report generation

---

## 2. New Report Type Architecture

### Category Structure (for `<select>` dropdown with `<optgroup>`)

```
FLAGSHIP REPORTS
  ├── Crash Poster Infographic (2-Page)          [KEEP - value="infographic"]
  └── Comprehensive Quarterly Report (20-Page)   [KEEP - value="comprehensive"]

EXPLORE REPORTS
  ├── Executive Dashboard Summary                [NEW  - value="dashboard"]
  ├── Corridor & Segment Analysis                [KEEP - value="corridor"]
  ├── Systemic Safety Analysis (Crash Tree)      [NEW  - value="crashtree"]
  ├── Safety Focus Category Report               [KEEP - value="safetyfocus"]
  ├── Fatal & Speed-Related Analysis             [NEW  - value="fatalspeed"]
  ├── High-Crash Location (Hotspot) Report       [NEW  - value="hotspot"]
  ├── Intersection Safety Analysis               [KEEP - value="intersection"]
  ├── Vulnerable Road User (Ped/Bike) Report     [KEEP - value="pedbike"]
  ├── Crash Prediction & Forecast                [NEW  - value="prediction"]
  └── Comprehensive Data Deep Dive               [NEW  - value="deepdive"]

SOLUTIONS REPORTS
  ├── Countermeasures Effectiveness Report        [KEEP - value="countermeasures"]
  ├── Before/After Study Report                   [NEW  - value="beforeafter"]
  └── Grant Application Support Package           [NEW  - value="grantsupport"]

PERFORMANCE REPORTS
  ├── Safety Performance Report                   [KEEP - value="safety"]
  └── Multi-Year Trend Analysis                   [KEEP - value="trend"]
```

### Reports REMOVED (merged into others)
- `systemwide` → Merged into `dashboard` (Executive Dashboard Summary covers the same ground but better)

---

## 3. Report Type Specifications

### 3.1 FLAGSHIP REPORTS

#### 3.1.1 Crash Poster Infographic (2-Page) — `infographic` [KEEP AS-IS]
- **Source:** `generateInfographic()` (line 65789)
- **No changes needed** — user explicitly requested keeping this

#### 3.1.2 Comprehensive Quarterly Report (20-Page) — `comprehensive` [KEEP AS-IS]
- **Source:** `generateComprehensiveReport()` (line 66641)
- **No changes needed** — user explicitly requested keeping this

---

### 3.2 EXPLORE REPORTS

#### 3.2.1 Executive Dashboard Summary — `dashboard` [NEW]
**Maps to:** Dashboard tab
**Data source:** `crashState.aggregates`, `crashState.sampleRows`
**Pages:** 4-6
**Function:** `generateDashboardReport(crashes, title, author, startDate, endDate)`

**Content:**
1. **Cover Page** — Title, jurisdiction, period, KPI cards (Total, Fatal, Serious, EPDO, K+A Rate, VRU, Speed, Nighttime)
2. **Executive Summary** — Auto-generated narrative of key findings
3. **Severity Distribution** — Severity bar + table (K/A/B/C/O with counts, percentages, EPDO)
4. **EPDO Breakdown** — Table showing contribution of each severity level with weighted values
5. **District/Magisterial Analysis** — Table by district with severity breakdown (if applicable)
6. **Year-Over-Year Comparison** — Multi-year table with trend indicators (↑/↓/→)
7. **Quick Facts Panel** — Pedestrian %, Bicycle %, Intersection %, Nighttime %, Speed-Related %
8. **Recommendations** — Auto-generated based on data patterns

---

#### 3.2.2 Corridor & Segment Analysis — `corridor` [ENHANCE]
**Maps to:** Map tab
**Data source:** `crashState.sampleRows` filtered by route
**Pages:** 5-7
**Function:** `generateCorridorReport()` (existing, enhance with professional PDF)

**Enhancements:**
1. Add satellite imagery reference (lat/lon coordinates)
2. Add node-by-node breakdown table
3. Add collision type distribution per segment
4. Add time-of-day analysis table
5. Professional cover page matching new template

---

#### 3.2.3 Systemic Safety Analysis (Crash Tree) — `crashtree` [NEW]
**Maps to:** Crash Tree tab
**Data source:** `crashState.sampleRows` processed through crash tree logic
**Pages:** 5-8
**Function:** `generateCrashTreeReportPDF(crashes, title, author, startDate, endDate)`

**Content:**
1. **Cover Page** — FHWA Systemic Safety Analysis branding
2. **Executive Summary** — Overview of systemic patterns identified
3. **Facility Type Breakdown** — Table: Facility Type → Total, K, A, B, C, O, EPDO, % of Total
4. **Crash Type Hierarchy** — Table: Crash Type → Facility → Count, Severity
5. **Contributing Factors Tree** — Table: Factor → Crash Types affected, severity distribution
6. **Cross-Analysis Matrix** — Crash Type × Facility Type matrix table
7. **High-Risk Combinations** — Top 10 facility-type + crash-type combinations by EPDO
8. **FHWA Systemic Approach Recommendations** — Category-specific countermeasures
9. **Methodology Notes** — FHWA systemic safety framework reference

---

#### 3.2.4 Safety Focus Category Report — `safetyfocus` [ENHANCE]
**Maps to:** Safety Focus tab
**Data source:** `safetyState.data[category]` for selected category
**Pages:** 6-8
**Function:** `generateSafetyFocusReport()` (existing, enhance)

**Enhancements:**
1. Add category-specific icon/branding on cover
2. Add subcategory breakdown table (from Safety Focus charts)
3. Add collision type distribution for the selected focus area
4. Add roadway description breakdown
5. Add first harmful event distribution
6. Add contributing factor badges as a table (Speed %, Senior %, Young %, etc.)
7. Add year-over-year trend table for the category
8. Add top locations table with EPDO ranking
9. Add category-specific countermeasures section
10. Mandatory: Include which of the 16+ categories was selected

---

#### 3.2.5 Fatal & Speed-Related Analysis — `fatalspeed` [NEW]
**Maps to:** Fatal & Speeding tab
**Data source:** `crashState.sampleRows` filtered for fatal OR speed-related
**Pages:** 6-8
**Function:** `generateFatalSpeedReportPDF(crashes, title, author, startDate, endDate)`

**Content:**
1. **Cover Page** — Fatal & Speed emphasis with red/orange KPI cards
2. **Executive Summary** — Fatal crash narrative + speed-related narrative
3. **Fatal Crash Analysis**
   - Total fatal crashes, fatalities, K+A rate
   - Fatal crashes by year table
   - Fatal crashes by collision type
   - Fatal crashes by light condition
   - Fatal crash locations (top 10 by count)
4. **Speed-Related Analysis**
   - Speed-related crash total, % of all crashes
   - Speed vs posted limit analysis (if data available)
   - Speed crashes by severity
   - Speed crashes by road type
5. **Combined Risk Analysis**
   - Fatal + Speed overlap analysis
   - High-risk corridors where both factors present
6. **Countermeasures** — Speed management, enforcement, engineering countermeasures
7. **Recommendations** — Prioritized by EPDO impact

---

#### 3.2.6 High-Crash Location (Hotspot) Report — `hotspot` [NEW]
**Maps to:** Hot Spots tab
**Data source:** `crashState.aggregates.byRoute` or `crashState.aggregates.byNode`
**Pages:** 6-10
**Function:** `generateHotspotReportPDF(crashes, title, author, startDate, endDate, groupBy, topN)`

**Content:**
1. **Cover Page** — "High-Crash Location Analysis" with total locations analyzed
2. **Executive Summary** — Top findings, highest-EPDO location, K+A concentration
3. **Methodology** — EPDO ranking methodology, data period, minimum threshold
4. **Top Locations Ranking Table** (Top 15-25)
   - Rank, Location Name, Total, K, A, B, C, O, EPDO, Crashes/Year, Primary Collision Type
   - Color-coded severity indicators
5. **Detailed Location Profiles** (Top 5)
   - For each: Severity distribution, collision types, contributing factors, time patterns
6. **Route-Level Summary** — Routes ranked by aggregate EPDO
7. **Intersection vs Segment Comparison** — Split analysis
8. **Prioritized Recommendations** — Location-specific countermeasures for top 5

---

#### 3.2.7 Intersection Safety Analysis — `intersection` [ENHANCE]
**Maps to:** Intersections tab
**Data source:** `crashState.sampleRows` filtered for intersection crashes
**Pages:** 5-7
**Function:** `generateIntersectionReport()` (existing, enhance)

**Enhancements:**
1. Add traffic control type breakdown table
2. Add approach-based analysis (if node data available)
3. Add time-of-day pattern table
4. Add weather condition table
5. Add light condition breakdown
6. Add intersection-specific countermeasures
7. Professional cover page with intersection count KPI

---

#### 3.2.8 Vulnerable Road User (Ped/Bike) Report — `pedbike` [ENHANCE]
**Maps to:** Ped/Bike tab
**Data source:** `crashState.sampleRows` filtered for ped/bike
**Pages:** 6-8
**Function:** `generatePedBikeReport()` (existing, enhance)

**Enhancements:**
1. **Separate sections for Pedestrian and Bicycle** (currently combined)
2. **People Injury Analysis** — People killed/injured counts (not just crash counts)
3. Add contributing factors table (Speeding, Unrestrained, Alcohol, Distracted, Age Group, User Type)
4. Add light condition breakdown per VRU type
5. Add location type analysis (crosswalk, intersection, midblock)
6. Add high-crash locations for pedestrian and bicycle separately
7. Add ADA/accessibility considerations in recommendations

---

#### 3.2.9 Crash Prediction & Forecast — `prediction` [NEW]
**Maps to:** Crash Prediction tab
**Data source:** Prediction model output
**Pages:** 4-6
**Function:** `generatePredictionReportPDF(crashes, title, author, startDate, endDate)`

**Content:**
1. **Cover Page** — "Crash Prediction & Forecast Report" with confidence level indicator
2. **Executive Summary** — Predicted crash counts, trend direction, confidence intervals
3. **Monthly Forecast Detail** — Table: Month, P10, P50 (Median), P90, Historical Average, % Change
4. **Corridor Risk Ranking** — Table: Corridor, Predicted Crashes, % Change, Risk Level (High/Med/Low)
5. **Safety Trend Analysis** — Historical vs Predicted comparison table
6. **Contributing Factor Trends** — Which factors are trending up/down
7. **Methodology** — Model description, confidence levels, limitations disclaimer
8. **Recommendations** — Proactive measures based on predictions

---

#### 3.2.10 Comprehensive Data Deep Dive — `deepdive` [NEW]
**Maps to:** Deep Dive tab
**Data source:** `crashState.sampleRows` with advanced analysis
**Pages:** 8-12
**Function:** `generateDeepDiveReportPDF(crashes, title, author, startDate, endDate)`

**Content:**
1. **Cover Page** — "Comprehensive Crash Data Deep Dive"
2. **Executive Summary** — Key insights from all 10 analysis panels
3. **Driver Behavior & Human Factors**
   - Top driver actions table
   - Human factors breakdown
   - Driver action × Crash type cross-tabulation
4. **Speed Intelligence**
   - Speed differential statistics
   - Top routes by average speed excess
   - Speed vs severity correlation
5. **Crash Sequence Analysis**
   - Multi-event crash statistics
   - Secondary crash rates
   - Event chain patterns
6. **Driver Demographics**
   - Age distribution table
   - Age group × severity cross-tab
   - Gender distribution
7. **Vehicle Fleet Analysis**
   - Vehicle types involved
   - Vehicle type vs severity
8. **Non-Motorist Detail**
   - Non-motorist types, actions, contributing factors
9. **Data Quality Audit**
   - Column coverage matrix
   - Validation checks summary
   - Data completeness score
10. **Recommendations** — Based on deepest patterns identified

---

### 3.3 SOLUTIONS REPORTS

#### 3.3.1 Countermeasures Effectiveness Report — `countermeasures` [KEEP, ENHANCE]
**Maps to:** Countermeasures tab
**Enhancement:** Add CMF values, expected crash reduction calculations, cost-effectiveness

#### 3.3.2 Before/After Study Report — `beforeafter` [NEW]
**Maps to:** Before/After Study tab
**Data source:** `baState.locationCrashes`, `baState.locationStats`
**Pages:** 4-6
**Function:** `generateBeforeAfterReportPDF(locationData, title, author)`

**Content:**
1. **Cover Page** — "Before/After Safety Study" with location name
2. **Study Design** — Before period, after period, treatment description
3. **Before Period Statistics** — Severity, collision types, EPDO
4. **After Period Statistics** — Same metrics
5. **Statistical Comparison** — % change, statistical significance
6. **Crash Modification Factor** — Observed CMF from the study
7. **Conclusions & Recommendations**

#### 3.3.3 Grant Application Support Package — `grantsupport` [NEW]
**Maps to:** Grants tab
**Data source:** `grantState.allRankedLocations`
**Pages:** 4-6
**Function:** `generateGrantSupportReportPDF(crashes, title, author)`

**Content:**
1. **Cover Page** — "Safety Improvement Grant Support Data"
2. **Project Justification** — Crash statistics supporting the need
3. **Location Rankings** — EPDO-ranked locations with severity data
4. **Benefit-Cost Analysis Data** — Expected crash reduction, monetized benefits
5. **Supporting Data Tables** — Collision types, severity, trends
6. **Appendix** — Data source citations, methodology

---

### 3.4 PERFORMANCE REPORTS

#### 3.4.1 Safety Performance Report — `safety` [KEEP, ENHANCE]
- Add yearly K+A by type table
- Add K+A by light condition
- Add high-severity location listing

#### 3.4.2 Multi-Year Trend Analysis — `trend` [KEEP, ENHANCE]
- Add statistical trend significance indicators
- Add forecast extension (1 year forward)
- Add K+A trend separate from total trend

---

## 4. HTML Dropdown Replacement

### Current Code (lines 9999-10010)
```html
<select id="reportType" onchange="updateReportOptions()">
  <option value="infographic">🎨 Crash Poster Infographic (2-Page)</option>
  <!-- ... 10 flat options ... -->
</select>
```

### New Code
```html
<select id="reportType" onchange="updateReportOptions()" style="font-size:.9rem">
  <optgroup label="⭐ FLAGSHIP REPORTS">
    <option value="infographic">🎨 Crash Poster Infographic (2-Page)</option>
    <option value="comprehensive">📑 Comprehensive Quarterly Report (20-Page)</option>
  </optgroup>
  <optgroup label="📊 EXPLORE REPORTS">
    <option value="dashboard">📊 Executive Dashboard Summary</option>
    <option value="corridor">📍 Corridor & Segment Analysis</option>
    <option value="crashtree">🌳 Systemic Safety Analysis (Crash Tree)</option>
    <option value="safetyfocus">🛡️ Safety Focus Category Report</option>
    <option value="fatalspeed">☠️ Fatal & Speed-Related Analysis</option>
    <option value="hotspot">🔥 High-Crash Location (Hotspot) Report</option>
    <option value="intersection">🚦 Intersection Safety Analysis</option>
    <option value="pedbike">🚶 Vulnerable Road User (Ped/Bike) Report</option>
    <option value="prediction">📉 Crash Prediction & Forecast</option>
    <option value="deepdive">🔬 Comprehensive Data Deep Dive</option>
  </optgroup>
  <optgroup label="💡 SOLUTIONS REPORTS">
    <option value="countermeasures">💡 Countermeasures Effectiveness Report</option>
    <option value="beforeafter">📋 Before/After Study Report</option>
    <option value="grantsupport">💰 Grant Application Support Package</option>
  </optgroup>
  <optgroup label="📈 PERFORMANCE REPORTS">
    <option value="safety">⚠️ Safety Performance Report</option>
    <option value="trend">📈 Multi-Year Trend Analysis</option>
  </optgroup>
</select>
```

---

## 5. Professional PDF Design Template

Every report PDF MUST follow this template:

### Page Structure
```
┌─────────────────────────────────────┐
│ HEADER BAR (12mm, dark blue #1E3A5F)│
│  "CRASH LENS"     "Report Type"     │
├─────────────────────────────────────┤
│                                     │
│  CONTENT AREA                       │
│  (18mm margins, ~180mm content)     │
│                                     │
│                                     │
│                                     │
├─────────────────────────────────────┤
│ FOOTER (20mm)                       │
│  Brand  |  Date/Period  |  Page X/Y │
│  ────────── Disclaimer ──────────── │
└─────────────────────────────────────┘
```

### Cover Page Template
```
┌─────────────────────────────────────┐
│ [HEADER BAR]                        │
│                                     │
│         REPORT TITLE (26pt bold)    │
│         Subtitle (14pt)             │
│                                     │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐  │
│  │ KPI │ │ KPI │ │ KPI │ │ KPI │  │
│  │Card │ │Card │ │Card │ │Card │  │
│  └─────┘ └─────┘ └─────┘ └─────┘  │
│                                     │
│  ┌─────────────────────────────┐   │
│  │     Report Details Box       │   │
│  │  Period: Jan 2023 - Dec 2025 │   │
│  │  Prepared by: John Smith     │   │
│  │  Report ID: CLR-2026-0309   │   │
│  │  Generated: March 9, 2026    │   │
│  └─────────────────────────────┘   │
│                                     │
│ [FOOTER]                            │
└─────────────────────────────────────┘
```

### Required PDF Helpers (existing, reuse from `generateStandardReportPDF`)
- `drawHeader(type)` — Dark blue header bar with branding
- `drawFooter()` — Footer with page numbers, date, report ID
- `newPage()` — Page break with header/footer
- `checkPageBreak(neededSpace)` — Auto page break
- `addText(text, size, style, color, indent)` — Wrapped text
- `addSectionTitle(title, color)` — Section header with accent bar
- `addSubsectionTitle(title, color)` — Subsection header
- `drawSeverityBar(severity)` — Color-coded severity distribution
- `drawKPICard(x, y, w, h, value, label, color)` — KPI card
- `doc.autoTable({})` — Professional tables with alternating rows

### Color Palette (consistent across all reports)
```javascript
const COLORS = {
    primary:     '#1E3A5F',  // Dark navy blue
    primaryLight:'#2563eb',  // Bright blue
    text:        '#374151',  // Dark gray
    textLight:   '#6b7280',  // Medium gray
    fatal:       '#991B1B',  // Dark red
    fatalLight:  '#dc2626',  // Red
    serious:     '#C2410C',  // Orange
    moderate:    '#f97316',  // Light orange
    minor:       '#facc15',  // Yellow
    pdo:         '#9CA3AF',  // Gray
    success:     '#065f46',  // Dark green
    pedestrian:  '#0891b2',  // Teal
    bicycle:     '#059669',  // Green
    speed:       '#92400e',  // Brown
    intersection:'#7c3aed',  // Purple
    nighttime:   '#4338ca',  // Indigo
    impaired:    '#be185d',  // Pink
};
```

---

## 6. Function Naming Convention

To avoid duplicate function names (critical rule from CLAUDE.md):

| Report Type | Generate Function | PDF Export Function |
|------------|-------------------|---------------------|
| dashboard | `generateDashboardReport()` | `generateDashboardReportPDF()` |
| crashtree | `generateCrashTreeSystemicReport()` | `generateCrashTreeReportPDF()` |
| fatalspeed | `generateFatalSpeedReport()` | `generateFatalSpeedReportPDF()` |
| hotspot | `generateHotspotRankingReport()` | `generateHotspotReportPDF()` |
| prediction | `generatePredictionForecastReport()` | `generatePredictionReportPDF()` |
| deepdive | `generateDeepDiveAnalysisReport()` | `generateDeepDiveReportPDF()` |
| beforeafter | `generateBeforeAfterStudyReport()` | `generateBeforeAfterReportPDF()` |
| grantsupport | `generateGrantSupportReport()` | `generateGrantSupportReportPDF()` |

**Check existing functions before implementing:**
- `generateCrashTreeReport()` already exists (line ~95683) — use different name
- `exportDeepDivePDF()` already exists (line ~143995) — use different name
- `exportPredictionPDF()` already exists (line ~141764) — use different name

---

## 7. Implementation Phases

### Phase 1: Foundation (HTML + Routing)
**Effort:** 2-3 hours
**Files:** `app/index.html`

1. Replace `<select id="reportType">` with categorized `<optgroup>` structure
2. Update `updateReportOptions()` to handle new report types (titles, location requirements)
3. Update `generateReport()` routing to dispatch to new generators
4. Update `generateStandardReportPDF()` header type map to include new types
5. Update `showTableOfContents()` to support new report types
6. Remove `systemwide` option (merge into `dashboard`)

### Phase 2: New Report Generators (HTML Preview)
**Effort:** 8-12 hours
**Files:** `app/index.html`

Implement HTML preview generators for each new report type:
1. `generateDashboardReport()`
2. `generateCrashTreeSystemicReport()`
3. `generateFatalSpeedReport()`
4. `generateHotspotRankingReport()`
5. `generatePredictionForecastReport()`
6. `generateDeepDiveAnalysisReport()`
7. `generateBeforeAfterStudyReport()`
8. `generateGrantSupportReport()`

### Phase 3: Professional PDF Generation
**Effort:** 12-16 hours
**Files:** `app/index.html`

Implement PDF export for each new report type following the `generateStandardReportPDF()` pattern:
1. Each PDF uses jsPDF with autoTable
2. Professional cover page with KPI cards
3. Executive summary with auto-generated narrative
4. Table of contents
5. Data tables with alternating row colors
6. Branded header/footer on every page
7. Report ID, timestamp, disclaimer

### Phase 4: Enhancement of Existing Reports
**Effort:** 4-6 hours
**Files:** `app/index.html`

Enhance existing reports to match new professional standard:
1. `corridor` — Add node breakdown, time-of-day, satellite reference
2. `safetyfocus` — Add subcategory detail, contributing factors table
3. `intersection` — Add traffic control, weather, light condition tables
4. `pedbike` — Separate pedestrian and bicycle sections, add people injury data
5. `safety` — Add K+A by type and light condition
6. `trend` — Add statistical significance, forecast extension

### Phase 5: Integration & Polish
**Effort:** 4-6 hours
**Files:** `app/index.html`

1. Cross-tab report launching (e.g., from Hotspot tab → "Generate Full Report" button)
2. Report scheduling via email (existing infrastructure)
3. Word document export for new report types
4. Testing across all report types
5. Performance optimization for large datasets

---

## 8. Data Requirements Per Report

| Report | Primary Data | Additional Data | Requires Location |
|--------|-------------|-----------------|-------------------|
| dashboard | `crashState.sampleRows` | `crashState.aggregates` | No |
| corridor | `crashState.sampleRows` | Route filter | Yes (route) |
| crashtree | `crashState.sampleRows` | Crash tree hierarchy | No |
| safetyfocus | `safetyState.data[category]` | Category selection | No |
| fatalspeed | `crashState.sampleRows` | Fatal + Speed filters | No |
| hotspot | `crashState.aggregates` | byRoute, byNode | No |
| intersection | `crashState.sampleRows` | Node filter | Optional |
| pedbike | `crashState.sampleRows` | Ped + Bike filters | No |
| prediction | Prediction model output | Historical data | No |
| deepdive | `crashState.sampleRows` | All columns | No |
| countermeasures | `cmfState.locationCrashes` | CMF data | Yes |
| beforeafter | `baState.locationCrashes` | Before/After periods | Yes |
| grantsupport | `grantState.allRankedLocations` | Grant data | No |
| safety | `crashState.sampleRows` | — | No |
| trend | `crashState.sampleRows` | — | No |

---

## 9. Professional Report Quality Checklist

Every report must satisfy:

- [ ] **Cover page** with report title, subtitle, jurisdiction, KPI cards, report details box
- [ ] **Table of Contents** with section names and page numbers
- [ ] **Executive Summary** with auto-generated narrative (2-3 paragraphs)
- [ ] **KPI Section** with at minimum: Total, Fatal, K+A Rate, EPDO
- [ ] **Branded Header** on every page (dark blue bar, "CRASH LENS", report type)
- [ ] **Branded Footer** on every page (date, page number, report ID)
- [ ] **Data Tables** with alternating row colors, professional styling
- [ ] **Severity Distribution** visualization (color-coded bar or table)
- [ ] **Recommendations Section** with actionable, data-driven suggestions
- [ ] **Disclaimer** at bottom of last page
- [ ] **Report ID** in format CLR-YYYY-MMDD-### for tracking
- [ ] **Clean text** — no emojis, no special characters in PDF output
- [ ] **Page breaks** — no content overflowing footer area
- [ ] **Consistent typography** — Helvetica, sizes: 26pt title, 14pt subtitle, 11pt section, 9-10pt body
- [ ] **Color consistency** — Same COLORS palette across all reports

---

## 10. Subscription Value Proposition

These reports provide value that justifies a paid subscription:

| Report | Value for Engineer | Comparable Commercial Product |
|--------|-------------------|-------------------------------|
| Crash Poster | Quick visual summary for presentations | Numetric, ATSPM |
| Comprehensive Quarterly | Board/council presentations | MicroStrategy, Tableau |
| Dashboard Summary | Monthly status reports | Iteris, Transcore |
| Crash Tree | Systemic safety analysis (FHWA HSIP) | FHWA ISATe tool |
| Safety Focus | Category-specific safety studies | SafetyAnalyst |
| Fatal & Speed | Speed management program support | IIHS data products |
| Hotspot Report | HSIP project prioritization | AASHTOWare Safety |
| Intersection | Signal warrant and safety analysis | Synchro/HCM reports |
| Ped/Bike | Active transportation safety plans | PBCAT tool |
| Prediction | Proactive safety management | Highway Safety Manual |
| Deep Dive | Comprehensive crash data exploration | SAS crash analytics |
| Countermeasures | CMF-based project justification | CMF Clearinghouse |
| Before/After | Treatment effectiveness evaluation | NCHRP reports |
| Grant Support | Federal safety grant applications | Custom consulting |
| Safety Performance | HSIP annual reporting | State DOT reports |
| Trend Analysis | Multi-year performance monitoring | FARS query tool |

---

## 11. Testing Strategy

### Unit Testing (per report type)
1. Generate with full dataset (1000+ crashes)
2. Generate with minimal dataset (< 10 crashes)
3. Generate with no fatal crashes
4. Generate with date filter applied
5. Generate with location filter applied
6. Verify PDF opens without errors
7. Verify page count matches expected
8. Verify all tables render with correct data
9. Verify no text overflow or truncation

### Integration Testing
1. Generate report from each Explore tab's "Report" button
2. Switch between report types without errors
3. Email scheduling works for all report types
4. Word export works for new report types
5. Print preview renders correctly

### Browser Testing
- Chrome 90+
- Firefox 90+
- Safari 15+
- Edge 90+

---

## 12. File Change Summary

**Files to modify:**
- `app/index.html` — All changes in single file
  - Lines 9999-10010: Replace report type dropdown
  - Lines 63308-63320: Update title map in `updateReportOptions()`
  - Lines 63323-63403: Update `generateReport()` routing
  - Lines 64349-64449: Update `showTableOfContents()` for new types
  - Lines 65101-65600: Update `generateStandardReportPDF()` type handling
  - Lines 65188-65196: Update header type name map
  - NEW CODE: Add ~8 new report generator functions
  - NEW CODE: Add ~8 new PDF export functions

**Estimated total new code:** ~3,000-4,000 lines of JavaScript

---

*This plan serves as the complete blueprint for transforming Crash Lens reports from a basic collection into a professional, subscription-worthy reporting suite.*
