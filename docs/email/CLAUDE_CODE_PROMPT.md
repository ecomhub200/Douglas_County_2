# Claude Code Prompt: Fix Scheduled Email Reports

## Task
Fix the scheduled email notification system in CRASH LENS so that emailed PDF reports use the **actual Standard Report PDF generators** instead of the current bare-bones 1-page stub. Also improve the email subject, body, add location filtering, auto-sync settings, and fix the "Your County" fallback.

## Background
The file `app/index.html` contains the entire application. The scheduled email feature (function `generateReportForEmail()`) currently creates a simple 1-page PDF with just a header and severity counts. But the tool already has a professional multi-page PDF generator called `generateStandardReportPDF()` that produces 4-6 page reports with cover pages, executive summaries, collision analysis tables, severity bars, and KPI cards. These two systems are completely disconnected. The email should send the real report.

## Step-by-Step Instructions

Follow the CLAUDE.md guidelines. Do NOT push directly — create a PR.

---

### Step 1: Modify `generateStandardReportPDF()` to support returning the doc

Find the function `generateStandardReportPDF(type, crashes, title, author, route, startDate, endDate)` and:

1. Add an `options = {}` parameter at the end of the signature
2. Before the `doc.save(filename)` line at the end of the function, add:
```javascript
if (options.returnDoc) {
    return doc;
}
```
This allows the email system to get the jsPDF document object instead of triggering a browser download.

---

### Step 2: Rewrite `generateReportForEmail()`

Replace the entire `generateReportForEmail()` function body. The new version should:

1. Accept `options` with: `startDate, endDate, agency, department, preparedBy, title, route, location`
2. Filter `crashState.sampleRows` by date range (keep existing logic)
3. Filter by route/location if provided
4. Call `generateStandardReportPDF(type, crashes, title, author, route, startDate, endDate, { returnDoc: true })` for these types: `systemwide, corridor, safety, pedbike, trend, intersection, countermeasures`
5. For `comprehensive` → fallback to `systemwide` (comprehensive needs DOM rendering which isn't available for email)
6. For `safetyfocus` → fallback to `safety`
7. For `infographic` → fallback to `systemwide` (infographic needs html2canvas)
8. Extract base64: `doc.output('datauristring').split(',')[1]`
9. Return `{ base64, filename, pageCount: doc.internal.getNumberOfPages() }`

---

### Step 3: Add `buildEmailSubjectLine()` helper function

Create a new function after `generateReportForEmail()`:

```javascript
function buildEmailSubjectLine(reportType, jurisdiction, crashes, startDate, endDate) {
    const stats = computeStats(crashes);
    // Short labels for each report type
    // Format time period as "Jan-Mar 2025" or "Jan 2024-Mar 2025"
    // Return: "Douglas County Corridor Analysis — Jan-Mar 2025 | 2,847 Crashes, 12 Fatal"
}
```

Then in `testEmailNotification()`, replace the subject line:
```javascript
// OLD:
const subject = `[CRASH LENS] ${reportLabel} - ${jurisdiction}`;
// NEW:
const subject = emailCrashes.length > 0
    ? buildEmailSubjectLine(reportType, jurisdiction, emailCrashes, startDate, endDate)
    : `[CRASH LENS] ${reportLabel} — ${jurisdiction}`;
```

---

### Step 4: Add `buildEmailStatsSection()` and `buildEmailFindings()` helpers

**`buildEmailStatsSection(crashes)`** generates email-safe HTML with:
- 4-column stats table: Total Crashes, Fatal (K), Serious (A), EPDO Score
- Severity breakdown with colored progress bars (use inline CSS only — no classes)

**`buildEmailFindings(crashes)`** generates:
- Top collision type with percentage
- Vulnerable road user count (ped + bike)
- K+A rate highlight
- Wrapped in a styled container

Both should use only inline CSS (emails don't support `<style>` tags reliably).

---

### Step 5: Enhance `buildEmailHtml()` inside `testEmailNotification()`

Before `buildEmailHtml()` is defined, compute `emailCrashes` by filtering `crashState.sampleRows` with the same date/location filters.

Inside `buildEmailHtml()`, add:
1. Call `buildEmailStatsSection(emailCrashes)` — insert after the intro paragraph
2. The PDF attachment notice with page count
3. Call `buildEmailFindings(emailCrashes)` — insert after the attachment notice
4. A "View Full Report in CRASH LENS" CTA button (`<a>` styled as button)
5. Keep the metadata table but move it below the findings

---

### Step 6: Add Location Selector to Email Modal

In `openEmailNotificationModal()`, after the Report Type dropdown (`<select id="emailReportType">`), add:

```html
<!-- Location Selection -->
<div id="emailLocationGroup" style="margin-bottom:.85rem;display:none">
    <label class="email-field-label">Location / Route</label>
    <select id="emailLocationSelect" class="brevo-input">
        <option value="all">All Locations (System-Wide)</option>
        <!-- Populate from crashState.aggregates.byRoute -->
    </select>
</div>
```

Add `onchange="updateEmailLocationVisibility()"` to the `#emailReportType` select.

Create `updateEmailLocationVisibility()`:
- Show location group for types: `corridor, intersection, safety, trend, countermeasures`
- Hide for: `systemwide, comprehensive, infographic, pedbike, safetyfocus`

Update `saveEmailNotificationSettings()` to persist `location: getVal('emailLocationSelect', 'all')`.

---

### Step 7: Auto-Sync from Standard Reports Tab

Create `syncFromStandardReportsTab()` that copies:
- `#reportType` → `#emailReportType`
- `#reportStartDate` / `#reportEndDate` → `#emailStartDate` / `#emailEndDate`
- `#reportAgency` → `#emailAgency`
- `#reportDepartment` → `#emailDepartment`
- `#reportAuthor` → `#emailPreparedBy`
- `#reportRoute` or `#reportLocationSelect` → `#emailLocationSelect`

Call it in `openEmailNotificationModal()` when `context === 'reports'`, after the modal is appended to DOM.

---

### Step 8: Fix "Your County" Jurisdiction Fallback

In `testEmailNotification()`, replace:
```javascript
// OLD:
const jurisdiction = typeof crashState !== 'undefined' && crashState.aggregates?.jurisdiction ? crashState.aggregates.jurisdiction : 'Your County';
// NEW:
const jurisdiction = (typeof crashState !== 'undefined' && crashState.aggregates?.jurisdiction)
    ? crashState.aggregates.jurisdiction
    : (document.getElementById('emailAgency')?.value?.trim()
        || notificationState.preferences?.reports?.agency
        || 'County');
```

---

### Step 9: Update `testEmailNotification()` to Pass Location

Where `generateReportForEmail()` is called, add the route parameter:
```javascript
const pdfResult = await generateReportForEmail(reportType, {
    startDate, endDate, agency, department, preparedBy,
    route: emailLocationRoute,  // NEW
    title: getDefaultReportTitle(reportType, jurisdiction)  // NEW
});
```

Get `emailLocationRoute` from: `document.getElementById('emailLocationSelect')?.value || ''`

---

## Important Rules (from CLAUDE.md)

1. **Never create duplicate function names** — search before creating
2. **Never push directly** — create a PR with the link
3. **Don't break existing functionality** — `generateStandardReportPDF()` must still work for its original callers (the Reports tab download button)
4. **Single file architecture** — all changes go in `app/index.html`
5. **Use existing patterns** — follow the code conventions already in the file

## Verification Checklist

- [ ] `generateStandardReportPDF()` still downloads PDF when called without `{ returnDoc: true }`
- [ ] `generateReportForEmail()` returns multi-page PDF (check `pageCount > 1`)
- [ ] Email subject includes jurisdiction name, report type, date range, crash count
- [ ] Email body shows severity stats cards, findings, and CTA button
- [ ] Location dropdown appears for corridor/intersection report types
- [ ] Settings sync when opening email modal from Reports tab
- [ ] "Your County" never appears when data is loaded
- [ ] No duplicate function names introduced
- [ ] JavaScript syntax is valid (no console errors)

## PR Format

```
Title: Fix scheduled email to use actual standard report PDF generators

## Summary
- Replace 1-page PDF stub with real multi-page standard reports (4-6 pages)
- Add location/route selector to email notification modal
- Dynamic email subject with crash stats
- Enhanced email body with severity cards, findings, and CTA
- Auto-sync from Standard Reports tab settings
- Fix "Your County" jurisdiction fallback

## Test plan
- [ ] Send test email for each report type, verify multi-page PDF attached
- [ ] Verify email subject shows real jurisdiction and crash counts
- [ ] Verify email body has stats cards, severity bars, and findings
- [ ] Select Corridor Analysis → verify location dropdown appears
- [ ] Configure report in Standard Reports → open email modal → verify auto-sync
- [ ] Verify Standard Reports tab still generates/downloads reports correctly
```
