# Implementation Plan: CMF Clearinghouse Data Sync

## Overview

Implement automated quarterly synchronization of Crash Modification Factor (CMF) data from the FHWA CMF Clearinghouse, replacing the current static embedded database with a dynamically updated external JSON file.

---

## Current State

```
app/index.html
└── const CMF_EMBEDDED_DATA = [...]   // ~4.7 MB, 3000+ records embedded in HTML
```

**Problems:**
- Data is static and never updates
- CMF Clearinghouse updates quarterly with new countermeasures
- No mechanism to sync new CMFs into the application
- HTML file is bloated with embedded data

---

## Target State

```
henrico_crash_tool/
├── app/index.html                    # Fetches external JSON
├── data/
│   ├── cmf_database.json            # Primary CMF data (updated quarterly)
│   └── cmf_database_backup.json     # Previous version (auto-backup)
├── download_cmf_data.py              # New sync script
└── .github/workflows/
    └── download-data.yml             # Updated with CMF download step
```

---

## Data Source

### FHWA CMF Clearinghouse

| Attribute | Value |
|-----------|-------|
| **Website** | https://cmfclearinghouse.fhwa.dot.gov |
| **Data Download Page** | https://cmfclearinghouse.fhwa.dot.gov/cmf_data.php |
| **CSV Download** | Available on download page |
| **XML Download** | https://cmfclearinghouse.fhwa.dot.gov/cmf_dataxml.php?file=cmfclearinghouse.xml |
| **Data Dictionary** | https://cmfclearinghouse.fhwa.dot.gov/cmf_datapdf.php?file=cmfdictionary.pdf |
| **Update Frequency** | Quarterly (reviews 4x/year) |
| **Last Updated** | May 07, 2025 |
| **Total Records** | 3,000+ CMFs |
| **Fields per Record** | 47 attributes |
| **Contact** | Sarah Weissman Pascual (sarah.pascual@dot.gov) |

---

## Sync Schedule

### Quarterly Download Schedule

| Quarter | Month | Cron Expression | Date |
|---------|-------|-----------------|------|
| Q1 | January | `0 11 8-14 1 1` | 2nd Monday, 6:00 AM EST |
| Q2 | April | `0 11 8-14 4 1` | 2nd Monday, 6:00 AM EST |
| Q3 | July | `0 11 8-14 7 1` | 2nd Monday, 6:00 AM EST |
| Q4 | October | `0 11 8-14 10 1` | 2nd Monday, 6:00 AM EST |

**Why 2nd Monday?**
- Allows time for Clearinghouse to publish after quarter-end
- Aligns with existing Monday workflow schedule (crash data runs 1st Monday)
- 6:00 AM EST (11:00 UTC) avoids peak hours

### Manual Trigger
- Add `workflow_dispatch` for on-demand runs
- Useful for testing or urgent updates

---

## Schema Mapping

### Clearinghouse CSV Fields → Application JSON Schema

| Clearinghouse Field | App Field | Type | Transform |
|---------------------|-----------|------|-----------|
| CMF ID | `id` | string | Direct |
| Countermeasure | `name` | string | Direct |
| Countermeasure Description | `desc` | string | Direct |
| Category | `category` | string | Direct |
| Subcategory | `subcategory` | string | Direct |
| CMF | `cmf` | number | Direct |
| CMF | `crfPct` | number | `(1 - CMF) * 100` |
| Star Rating | `rating` | number | Direct |
| Crash Type | `crashTypes` | array | Parse/split |
| Crash Severity | `severities` | array | Parse/split |
| Roadway/Intersection | `locationType` | string | Map values |
| Standard Error | `standardError` | number | Direct |
| CI Lower | `ciLow` | number | Direct |
| CI Upper | `ciHigh` | number | Direct |
| State | `state` | string | Direct |
| AADT Min | `minAADT` | number | Direct |
| AADT Max | `maxAADT` | number | Direct |
| Speed Limit Min | `minSpeed` | number | Direct |
| Speed Limit Max | `maxSpeed` | number | Direct |
| Number of Lanes Min | `minLanes` | number | Direct |
| Number of Lanes Max | `maxLanes` | number | Direct |
| Roadway Type | `roadwayType` | string | Direct |
| Area Type | `areaType` | string | Map values |
| Intersection Type | `intersectionType` | string | Direct |
| Intersection Geometry | `intersectionGeometry` | string | Direct |
| Traffic Control | `trafficControl` | string | Direct |
| Road Division | `roadDivision` | string | Direct |
| Time of Day | `timeOfDay` | string | Direct |
| Publication Year | `pubYear` | number | Direct |
| Study Link | `studyLink` | string | Direct |
| Prior Condition | `priorCondition` | string | Direct |

### Fields to Remove (No Longer Needed)

| Field | Reason |
|-------|--------|
| `isProven` | Not using custom enrichments |
| `isVirginia` | Not using custom enrichments |
| `inHSM` | Not using custom enrichments |

---

## Minimum Safeguards

### 1. Record Count Validation

```
Expected: 2,500+ records
Action: REJECT if new file has < 2,500 records

Log warning if:
- New count < 90% of previous count
- New count > 150% of previous count (unexpected spike)
```

### 2. Required Fields Check

Every record MUST have:
- `id` - unique identifier (non-empty string)
- `name` - countermeasure name (non-empty string)
- `cmf` - CMF value (number between 0 and 5)
- `rating` - star rating (number 1-5)

Action: REJECT entire file if any record fails validation.

### 3. Backup Before Overwrite

```
Before saving new data:
1. Copy cmf_database.json → cmf_database_backup.json
2. Write new data to cmf_database.json
3. On failure, restore from backup
```

### 4. Change Detection & Logging

Generate summary report:
```
CMF Database Sync - Q2 2025
============================
Timestamp: 2025-04-14 06:00:00 UTC
Source: cmfclearinghouse.fhwa.dot.gov

Previous Records: 3,127
New Records: 3,156
Added: 29 new CMFs
Removed: 0 CMFs
Modified: 12 CMFs (updated values)

Status: SUCCESS
```

### 5. Failure Notification

On workflow failure:
- GitHub Actions shows failed status
- Consider adding email notification (optional)
- Workflow logs contain error details

---

## Architecture Changes

### Current: Embedded Data

```javascript
// app/index.html (line ~24792)
const CMF_EMBEDDED_DATA = [
  {"id":"10358","name":"Install HFST",...},
  {"id":"10359","name":"Add left-turn lane",...},
  // ... 3000+ records embedded
];

function loadCMFDatabase() {
  cmfState.database = CMF_EMBEDDED_DATA;
  cmfState.loaded = true;
}
```

### Target: External JSON with Fallback

```javascript
// app/index.html
async function loadCMFDatabase() {
  const statusEl = document.getElementById('cmfDatabaseStatus');

  try {
    // Try to fetch external JSON
    const response = await fetch('../data/cmf_database.json');

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    // Validate minimum record count
    if (data.length < 2500) {
      throw new Error(`Invalid data: only ${data.length} records`);
    }

    cmfState.database = data;
    cmfState.loaded = true;
    showCMFLoadedStatus();

  } catch (error) {
    console.error('Failed to load CMF database:', error);

    // Fallback to embedded data if available
    if (typeof CMF_EMBEDDED_DATA !== 'undefined') {
      cmfState.database = CMF_EMBEDDED_DATA;
      cmfState.loaded = true;
      showCMFLoadedStatus('(using cached data)');
    } else {
      statusEl.innerHTML = `
        <div style="color:var(--danger)">
          <strong>Error Loading CMF Database</strong>
          <p>${error.message}</p>
        </div>
      `;
    }
  }
}
```

### Cache Busting (Optional)

To ensure browsers get fresh data after updates:

```javascript
// Add version or timestamp query param
const response = await fetch(`../data/cmf_database.json?v=${Date.now()}`);
```

Or use config-based versioning:
```javascript
const response = await fetch(`../data/cmf_database.json?v=${config.cmfDataVersion}`);
```

---

## Implementation Phases

### Phase 1: Create Download Script

**File:** `download_cmf_data.py`

**Responsibilities:**
1. Download CSV from CMF Clearinghouse
2. Parse and transform to application schema
3. Calculate derived fields (crfPct)
4. Validate data quality
5. Output to `data/cmf_database.json`

**Dependencies:**
- `requests` - HTTP downloads
- `pandas` - CSV parsing
- `json` - JSON output

**Error Handling:**
- Retry on network failure (3 attempts with backoff)
- Validate response status
- Check for empty/malformed data

---

### Phase 2: Extract Current Embedded Data

**Purpose:** Create initial `data/cmf_database.json` from current embedded data.

**Steps:**
1. Extract `CMF_EMBEDDED_DATA` from `app/index.html`
2. Save as `data/cmf_database.json`
3. Validate JSON is valid and complete

**One-time task** - provides baseline for comparison.

---

### Phase 3: Update Application to Fetch External JSON

**File:** `app/index.html`

**Changes:**
1. Modify `loadCMFDatabase()` to fetch external JSON
2. Add error handling and fallback
3. Keep embedded data temporarily as fallback
4. Add loading indicator during fetch

**Testing:**
- Verify CMF tab loads correctly
- Test with network failure (fallback works)
- Verify all CMF card features work

---

### Phase 4: Update GitHub Actions Workflow

**File:** `.github/workflows/download-data.yml`

**Add new job or step:**

```yaml
# Quarterly CMF sync (2nd Monday of Jan, Apr, Jul, Oct)
- name: Download CMF data (quarterly)
  if: github.event_name == 'workflow_dispatch' ||
      (github.event_name == 'schedule' && <quarterly-condition>)
  run: |
    python download_cmf_data.py --output data/cmf_database.json

    # Validate output
    RECORD_COUNT=$(python -c "import json; print(len(json.load(open('data/cmf_database.json'))))")
    echo "CMF records: $RECORD_COUNT"

    if [ "$RECORD_COUNT" -lt 2500 ]; then
      echo "ERROR: CMF data validation failed (only $RECORD_COUNT records)"
      exit 1
    fi
```

**Schedule Options:**

Option A: Separate quarterly workflow
```yaml
on:
  schedule:
    - cron: '0 11 8-14 1,4,7,10 1'  # 2nd Monday of quarter months
  workflow_dispatch:
```

Option B: Add to existing workflow with conditional
```yaml
- name: Download CMF data
  if: <is-second-monday-of-quarter>
  run: python download_cmf_data.py
```

---

### Phase 5: Remove Embedded Data (Final)

**After confirming external fetch works reliably:**

1. Remove `const CMF_EMBEDDED_DATA = [...]` from `app/index.html`
2. Remove fallback code (or keep minimal fallback)
3. HTML file size reduces by ~4.7 MB

**Timeline:** 1-2 quarters after initial deployment to ensure stability.

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `download_cmf_data.py` | CREATE | New Python script for CMF sync |
| `data/cmf_database.json` | CREATE | External CMF database |
| `app/index.html` | MODIFY | Fetch external JSON, update loadCMFDatabase() |
| `.github/workflows/download-data.yml` | MODIFY | Add quarterly CMF download step |
| `requirements.txt` | MODIFY | Add pandas if not present |

---

## Rollback Plan

### If External Fetch Fails in Production

1. **Immediate:** Fallback to embedded data (if still present)
2. **Short-term:** Manually run workflow to refresh data
3. **If data is corrupt:** Restore from `cmf_database_backup.json` or git history

### If Clearinghouse Changes Format

1. Workflow will fail validation (record count < 2500)
2. Investigate CSV structure changes
3. Update `download_cmf_data.py` field mappings
4. Re-run workflow manually

---

## Testing Checklist

### Pre-Deployment
- [ ] Download Clearinghouse CSV manually
- [ ] Run transform script locally
- [ ] Compare output to current embedded data
- [ ] Verify all required fields present
- [ ] Test field mapping accuracy
- [ ] Validate JSON structure

### Post-Deployment
- [ ] CMF tab loads without errors
- [ ] CMF cards display correctly
- [ ] Filters work (crash type, severity, rating)
- [ ] AI search finds CMFs correctly
- [ ] Location-based recommendations work
- [ ] Shortlist feature works
- [ ] Network failure shows fallback/error gracefully

### Quarterly Validation
- [ ] Workflow runs successfully
- [ ] New CMFs appear in database
- [ ] Record count logged correctly
- [ ] No duplicate or missing IDs

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Sync success rate | 100% (4/4 quarters) |
| Data freshness | < 2 weeks after Clearinghouse update |
| Validation pass rate | 100% |
| Application errors | 0 related to CMF data |
| HTML file size reduction | ~4.7 MB (after embedded removal) |

---

## Future Enhancements (Optional)

1. **Email notification** on sync completion/failure
2. **Diff report** showing exactly which CMFs changed
3. **Version history** tracking in separate file
4. **API endpoint** to check last sync date
5. **Admin UI** to trigger manual sync

---

## References

- [CMF Clearinghouse](https://cmfclearinghouse.fhwa.dot.gov/)
- [Data Download Page](https://cmfclearinghouse.fhwa.dot.gov/cmf_data.php)
- [Data Dictionary (PDF)](https://cmfclearinghouse.fhwa.dot.gov/cmf_datapdf.php?file=cmfdictionary.pdf)
- [CMF Clearinghouse User Guide](https://cmfclearinghouse.fhwa.dot.gov/collateral/CMF_UserGuide_2021.pdf)
- [FHWA CMF Overview](https://highways.dot.gov/safety/data-analysis-tools/rsdp/rsdp-tools/cmf-clearinghouse)

---

## Contact

For CMF Clearinghouse data questions:
- **Sarah Weissman Pascual**
- **Email:** sarah.pascual@dot.gov
- **Organization:** FHWA / UNC Highway Safety Research Center
