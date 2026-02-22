# Plan: Fix Scheduled Email to Use Actual Standard Reports

## Context

The scheduled email feature currently generates a **bare-bones 1-page PDF** using `generateReportForEmail()` (lines 37058-37173 in `index.html`). This function manually draws a simple severity summary using jsPDF — it does NOT use any of the actual report generators that the Standard Reports tab uses.

Meanwhile, the Standard Reports tab has **10 rich, multi-page report generators** (e.g., `generateStandardReportPDF()` at line 63021 which produces 4-6 page professional PDFs with charts, tables, severity bars, cover pages, etc.). The email PDF and the standard PDF are completely disconnected systems.

**The uploaded PDF confirms the problem:** The email sends a single page with just a header, metadata, and a basic severity count — not the actual report content.

### Problems to Fix
1. **PDF report is fake** — `generateReportForEmail()` creates a 1-page stub, not the actual standard report
2. **Email subject line is generic** — `[CRASH LENS] Comprehensive Quarterly Report (20-Page) - Your County`
3. **Email body is bare** — No crash highlights, no key stats, no actionable insights
4. **No location filter in email modal** — Standard Reports has location selection; email modal doesn't
5. **Settings not synced** — If user configures report in Standard Reports tab, they must re-enter everything in email modal
6. **"Your County" placeholder** — Jurisdiction falls back to "Your County" when crashState isn't loaded

---

## Implementation Plan

### 1. Replace `generateReportForEmail()` with actual `generateStandardReportPDF()`

**File:** `app/index.html` (lines 37058-37173)

**Approach:** Instead of the current stub that manually draws a 1-page summary, call the existing `generateStandardReportPDF()` function (line 63021) which already produces professional multi-page PDFs.

**Steps:**
- Rewrite `generateReportForEmail(reportType, options)` to:
  1. Filter crashes by date range (keep existing logic)
  2. Filter by location/route if specified (NEW)
  3. Call `generateStandardReportPDF(type, crashes, title, author, route, startDate, endDate)` for report types it supports (`systemwide`, `corridor`, `safety`, `pedbike`, `trend`, `countermeasures`, `intersection`)
  4. For `infographic` type → call `generateInfographicPDF()` (if exists) or the infographic generator
  5. For `comprehensive` type → call the comprehensive report PDF generator
  6. Return the jsPDF doc as base64 with actual page count
- The existing `generateStandardReportPDF()` already returns a jsPDF doc object — extract base64 from it

**Key existing functions to reuse:**
- `generateStandardReportPDF(type, crashes, title, author, route, startDate, endDate)` — line 63021
- `computeStats(crashes)` — statistics computation
- `calcEPDO(stats)` — EPDO calculation
- `getDateRange(crashes)` — date range extraction

### 2. Add Location Selection to Email Modal

**File:** `app/index.html` (lines 35930-35970, inside `openEmailNotificationModal()`)

**Approach:** Add a location dropdown (route/intersection) to the email modal's report configuration section, matching the Standard Reports tab pattern.

**Steps:**
- Add a location type selector (All Locations / Route / Intersection) below the report type dropdown
- Add a location dropdown populated from `crashState.aggregates.byRoute` (same data source as Standard Reports)
- Show/hide location selector based on report type (corridor/intersection need it; systemwide doesn't)
- Store selected location in `notificationState.preferences.reports.location`
- Pass location to `generateReportForEmail()` when generating PDF

### 3. Improve Email Subject Line

**File:** `app/index.html` (line 36845, inside `testEmailNotification()`)

**Current:** `[CRASH LENS] Comprehensive Quarterly Report (20-Page) - Your County`

**New format:** `Douglas County Crash Report — Q4 2025 | 2,847 Crashes, 12 Fatal`

**Steps:**
- Build a dynamic subject line that includes:
  - Actual jurisdiction name (from `crashState.aggregates.jurisdiction`)
  - Report type (shorter label)
  - Time period (formatted as quarter/year or date range)
  - Key stat highlight (total crashes + fatals)
- Create a helper function `buildEmailSubjectLine(reportType, jurisdiction, crashes, startDate, endDate)`
- Apply to both `testEmailNotification()` and `saveEmailNotificationSettings()`

### 4. Enhance Email Body with Crash Highlights

**File:** `app/index.html` (lines 36792-36831, `buildEmailHtml()` inside `testEmailNotification()`)

**Current:** Just shows jurisdiction, report type, period, and "PDF attached" notice.

**Enhanced to include:**
- **Key stats banner**: Total crashes, Fatal (K), Serious Injury (A), EPDO score
- **Trend indicator**: Up/down arrows comparing to previous period (if data available)
- **Top 3 findings**: Auto-generated from crash data (e.g., "Rear-end collisions account for 42% of crashes")
- **Quick severity breakdown**: Visual colored bars in the email (inline CSS, email-safe)
- **CTA button**: "View Full Report in CRASH LENS" with link to the tool

**Steps:**
- Create `buildEmailStatsSection(crashes)` helper that generates email-safe HTML stats
- Create `buildEmailFindings(crashes)` that picks top 3 actionable insights
- Add severity breakdown mini-chart using inline CSS (table-based for email compatibility)
- Include the stats section before the attachment notice in the email body

### 5. Auto-Sync Standard Reports Settings → Email Modal

**File:** `app/index.html` (inside `openEmailNotificationModal()`)

**Approach:** When user opens the email modal FROM the Standard Reports tab (via the "📧 Schedule Email" button), pre-populate the email modal with the current Standard Reports tab settings.

**Steps:**
- In `openEmailNotificationModal('reports')`, check if coming from Reports tab
- If so, read current values from Standard Reports form fields:
  - `#reportType` → `#emailReportType`
  - `#reportStartDate` / `#reportEndDate` → `#emailStartDate` / `#emailEndDate`
  - `#reportAgency` → `#emailAgency`
  - `#reportDepartment` → `#emailDepartment`
  - `#reportAuthor` → `#emailPreparedBy`
  - `#reportRoute` / `#reportLocationSelect` → email location selector
- This ensures zero re-entry when user clicks "Schedule Email" from Reports tab

### 6. Fix "Your County" Jurisdiction Fallback

**File:** `app/index.html` (line 36769)

**Current:** `const jurisdiction = typeof crashState !== 'undefined' && crashState.aggregates?.jurisdiction ? crashState.aggregates.jurisdiction : 'Your County';`

**Fix:**
- Also check `notificationState.preferences.reports.agency` as fallback
- Also check `document.getElementById('emailAgency')?.value`
- Chain: `crashState.aggregates.jurisdiction` → `emailAgency input` → `saved agency pref` → `'County'`

---

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `app/index.html` | 37058-37173 | Rewrite `generateReportForEmail()` to use real PDF generators |
| `app/index.html` | 35930-35970 | Add location selector to email modal |
| `app/index.html` | 36792-36831 | Enhance `buildEmailHtml()` with stats/findings |
| `app/index.html` | 36845 | Improve email subject line |
| `app/index.html` | 36769 | Fix jurisdiction fallback |
| `app/index.html` | 35714-35720 | Auto-sync from Reports tab settings |
| `app/index.html` | 36558-36640 | Update `saveEmailNotificationSettings()` to persist location |

---

## Verification Plan

1. **PDF Report Quality**: Open email modal → select each report type → click "Send Test" → verify the received PDF matches what Standard Reports tab generates (multi-page, charts, tables, professional formatting)
2. **Subject Line**: Verify email subject contains actual jurisdiction name, report period, and crash counts
3. **Email Body**: Verify email body includes severity stats, key findings, and visual breakdown
4. **Location Filter**: Select "Corridor Analysis" → verify location dropdown appears → select a route → verify PDF is filtered to that route
5. **Settings Sync**: Go to Standard Reports → configure a report → click "Schedule Email" → verify all fields are pre-populated
6. **Jurisdiction Fix**: Verify "Your County" never appears when crash data is loaded
7. **No Regressions**: Verify Standard Reports tab still generates reports correctly, other tabs unaffected

---

## PR Deliverable

Single PR with clear commit messages, screenshots of before/after email comparison, and testing notes covering all 10 report types.
