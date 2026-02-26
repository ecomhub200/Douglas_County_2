# Corrections Pipeline: Upload Tab to R2 with Incremental Processing

**Version:** 1.0
**Date:** February 2026
**Location:** `data-pipeline/corrections-pipeline.md`
**Companion to:** `data-pipeline/parquet-and-duckdb-wasm-integration.md` (Phase 5)

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Current State Analysis](#2-current-state-analysis)
3. [Design Goals](#3-design-goals)
4. [Corrections Overlay Format](#4-corrections-overlay-format)
5. [Browser-Side: Save Corrections to R2](#5-browser-side-save-corrections-to-r2)
6. [Server-Side: Upload Endpoint](#6-server-side-upload-endpoint)
7. [Incremental Monthly Processing](#7-incremental-monthly-processing)
8. [Pipeline Integration: Merge Corrections](#8-pipeline-integration-merge-corrections)
9. [GPS Recovery via OSM Nominatim](#9-gps-recovery-via-osm-nominatim)
10. [R2 Storage Layout](#10-r2-storage-layout)
11. [Parquet/DuckDB Integration](#11-parquetduckdb-integration)
12. [Data Flow Diagrams](#12-data-flow-diagrams)
13. [Edge Cases & Safety](#13-edge-cases--safety)
14. [Implementation Plan](#14-implementation-plan)
15. [Files to Modify](#15-files-to-modify)
16. [Verification Plan](#16-verification-plan)

---

## 1. Problem Statement

Users in the Upload Tab can:
- **Validate** crash data (auto-corrections for severity, weather, etc.)
- **Correct** flagged records manually (fix severity codes, collision types, etc.)
- **Recover GPS** coordinates for records with missing lat/lng (via OSM Nominatim)

**Current limitations:**
- Corrections are **local-only** (stored in browser memory + IndexedDB)
- No mechanism to **push corrections back to R2** so they persist for all users
- `saveGeocodedDataToR2()` exists but **overwrites the entire CSV** -- no delta/overlay approach
- Every month, when new DOT data arrives, **all previous corrections are lost**
- No way to **skip already-corrected records** during monthly re-validation
- Manual export (`dqExportCorrectedCSV()`) creates a local file -- not integrated with pipeline

**What we need:**
- Store corrections as a **separate overlay** on R2 (not overwrite canonical CSV)
- Pipeline **merges corrections** into fresh DOT data during monthly processing
- Browser **skips already-corrected records** during validation
- GPS coordinates recovered via OSM are **persisted** and not re-geocoded monthly
- Full **audit trail** of what was corrected, when, and by whom

---

## 2. Current State Analysis

### What Exists Today

| Component | Location | Status |
|-----------|----------|--------|
| `validationState.manualCorrections` | `app/index.html:24342` | In-memory corrections by Document Nbr |
| `dqSaveCorrectionsToCache()` | `app/index.html:26933` | Saves to IndexedDB (local only) |
| `dqLoadCorrectionsFromCache()` | `app/index.html:26997` | Restores from IndexedDB |
| `dqExportCorrectedCSV()` | `app/index.html:26867` | Downloads corrected CSV locally |
| `saveGeocodedDataToR2()` | `app/geocode-engine.js:560` | Uploads FULL CSV to R2 (overwrites) |
| `POST /r2/upload-geocoded` | `server/qdrant-proxy.js:446` | Server endpoint for R2 upload |
| `GET /r2/status` | `server/qdrant-proxy.js:435` | Checks R2 configuration |
| R2 Worker (traffic inventory) | `app/traffic-inventory.html` | Browser-direct PUT to R2 Worker |

### How Corrections Work Today

```
User loads county data from R2 (CSV)
  -> crashState.sampleRows populated
  -> User runs dqRunValidation()
     -> Auto-corrections applied to sampleRows (>=85% confidence)
     -> Flagged records shown for manual review
  -> User manually corrects flagged records
     -> validationState.manualCorrections[docNbr][field] = newValue
     -> Changes applied directly to crashState.sampleRows[rowIdx][field]
  -> User can:
     A) dqExportCorrectedCSV() -> downloads CSV locally (data island)
     B) dqSaveCorrectionsToCache() -> saves to IndexedDB (local, session-persistent)
     C) saveGeocodedDataToR2() -> overwrites entire CSV on R2 (destructive)
```

### Key Data Structures

**Document Nbr (COL.ID)** is the unique identifier for each crash record.

```javascript
// Manual corrections format
validationState.manualCorrections = {
    "DOC-2024-001": {
        "Crash Severity": "K",
        "Weather Condition": "Clear"
    },
    "DOC-2024-002": {
        "x": "-81.234",     // Recovered GPS longitude
        "y": "39.456"       // Recovered GPS latitude
    }
};

// Reviewed records tracking
validationState.reviewedRecords = new Set([
    "DOC-2024-001|Crash Severity",
    "DOC-2024-001|Weather Condition",
    "DOC-2024-002|x",
    "DOC-2024-002|y"
]);
```

---

## 3. Design Goals

| Goal | Approach |
|------|----------|
| **Non-destructive** | Corrections stored as overlay, never overwrite canonical CSV |
| **Incremental** | Monthly pipeline skips already-corrected records |
| **Auditable** | Full trail: who corrected what, when, original vs corrected value |
| **Persistent** | Corrections survive across sessions, browsers, and pipeline runs |
| **Lightweight** | Corrections overlay is tiny (~5-50 KB) vs full CSV (~2 MB) |
| **Pipeline-compatible** | `merge_corrections.py` applies overlay before aggregate generation |
| **GPS-aware** | Geocoded coordinates are treated as corrections, same overlay format |
| **Multi-user safe** | Last-write-wins with timestamps; future: merge conflicts UI |

---

## 4. Corrections Overlay Format

### corrections.json (Per Jurisdiction, Per Road Type)

Stored on R2 at: `{state}/{jurisdiction}/corrections.json`

```json
{
  "_version": 1,
  "_format": "corrections-overlay",
  "state": "colorado",
  "jurisdiction": "douglas",
  "roadType": "all_roads",
  "lastUpdated": "2026-02-26T15:30:00Z",
  "updatedBy": "user@example.com",
  "totalCorrections": 12,
  "records": {
    "DOC-2024-001": {
      "corrections": {
        "Crash Severity": {
          "original": "x",
          "corrected": "K",
          "source": "auto",
          "confidence": 95,
          "correctedAt": "2026-02-26T15:30:00Z"
        },
        "Weather Condition": {
          "original": "",
          "corrected": "Clear",
          "source": "manual",
          "confidence": 100,
          "correctedAt": "2026-02-26T15:31:00Z"
        }
      },
      "recordHash": "a1b2c3d4",
      "firstCorrectedAt": "2026-02-26T15:30:00Z",
      "lastCorrectedAt": "2026-02-26T15:31:00Z"
    },
    "DOC-2024-002": {
      "corrections": {
        "x": {
          "original": "",
          "corrected": "-104.8726",
          "source": "geocode-osm",
          "confidence": 88,
          "correctedAt": "2026-02-26T15:35:00Z",
          "geocodeDetails": {
            "strategy": "nominatim",
            "query": "US-85 & Lincoln Ave, Douglas County, CO",
            "osmId": "way/12345678"
          }
        },
        "y": {
          "original": "",
          "corrected": "39.3433",
          "source": "geocode-osm",
          "confidence": 88,
          "correctedAt": "2026-02-26T15:35:00Z"
        }
      },
      "recordHash": "e5f6g7h8",
      "firstCorrectedAt": "2026-02-26T15:35:00Z",
      "lastCorrectedAt": "2026-02-26T15:35:00Z"
    }
  }
}
```

### corrections_log.jsonl (Append-Only Audit Trail)

Stored on R2 at: `{state}/{jurisdiction}/corrections_log.jsonl`

Each line is a JSON object representing one correction event:

```jsonl
{"ts":"2026-02-26T15:30:00Z","docNbr":"DOC-2024-001","field":"Crash Severity","from":"x","to":"K","source":"auto","confidence":95,"user":"user@example.com"}
{"ts":"2026-02-26T15:31:00Z","docNbr":"DOC-2024-001","field":"Weather Condition","from":"","to":"Clear","source":"manual","confidence":100,"user":"user@example.com"}
{"ts":"2026-02-26T15:35:00Z","docNbr":"DOC-2024-002","field":"x","from":"","to":"-104.8726","source":"geocode-osm","confidence":88,"user":"user@example.com"}
{"ts":"2026-02-26T15:35:00Z","docNbr":"DOC-2024-002","field":"y","from":"","to":"39.3433","source":"geocode-osm","confidence":88,"user":"user@example.com"}
```

### Why This Format?

1. **corrections.json** is the "current truth" -- latest correction per field per record
2. **corrections_log.jsonl** is the audit trail -- every correction ever made, in order
3. **Keyed by Document Nbr** -- the existing unique identifier in crash data
4. **recordHash** -- MD5 of the original row, so pipeline can detect if DOT data changed under us
5. **source field** -- distinguishes `auto` (validation rules), `manual` (user edit), `geocode-osm` (GPS recovery), `geocode-node` (node lookup), `geocode-milepost` (milepost interpolation)
6. **Confidence score** -- preserved from validation/geocoding for traceability

---

## 5. Browser-Side: Save Corrections to R2

### New Function: `saveCorrectionsToR2()`

Replaces the current pattern of overwriting the full CSV. Instead, uploads only the corrections overlay.

```javascript
async function saveCorrectionsToR2() {
    // 1. Build corrections.json from validationState
    const overlay = {
        _version: 1,
        _format: 'corrections-overlay',
        state: getActiveStateKey(),
        jurisdiction: getActiveJurisdictionId(),
        roadType: getActiveRoadTypeSuffix(),
        lastUpdated: new Date().toISOString(),
        updatedBy: currentUser?.email || 'anonymous',
        totalCorrections: 0,
        records: {}
    };

    // 2. Merge auto-corrections from validation
    for (const corr of validationState.corrections) {
        const docNbr = corr.documentNbr;
        if (!overlay.records[docNbr]) {
            overlay.records[docNbr] = {
                corrections: {},
                recordHash: computeRowHash(corr.row),
                firstCorrectedAt: new Date().toISOString(),
                lastCorrectedAt: new Date().toISOString()
            };
        }
        overlay.records[docNbr].corrections[corr.field] = {
            original: corr.original,
            corrected: corr.corrected,
            source: 'auto',
            confidence: corr.confidence,
            correctedAt: new Date().toISOString()
        };
        overlay.totalCorrections++;
    }

    // 3. Merge manual corrections
    for (const [docNbr, fields] of Object.entries(validationState.manualCorrections)) {
        if (!overlay.records[docNbr]) {
            overlay.records[docNbr] = {
                corrections: {},
                recordHash: '',
                firstCorrectedAt: new Date().toISOString(),
                lastCorrectedAt: new Date().toISOString()
            };
        }
        for (const [field, value] of Object.entries(fields)) {
            // Find original value from sampleRows
            const rowIdx = findRowByDocNbr(docNbr);
            const originalValue = rowIdx >= 0 ?
                crashState.sampleRows[rowIdx]._originals?.[field] || '' : '';

            overlay.records[docNbr].corrections[field] = {
                original: originalValue,
                corrected: value,
                source: (field === 'x' || field === 'y') ? 'geocode-osm' : 'manual',
                confidence: 100,
                correctedAt: new Date().toISOString()
            };
            overlay.totalCorrections++;
        }
        overlay.records[docNbr].lastCorrectedAt = new Date().toISOString();
    }

    // 4. Merge with existing corrections on R2 (fetch-merge-upload pattern)
    try {
        const existing = await fetchExistingCorrections();
        if (existing) {
            mergeCorrections(overlay, existing);
        }
    } catch (e) {
        console.log('[Corrections] No existing corrections found, creating new');
    }

    // 5. Upload corrections.json to R2
    const r2Key = `${overlay.state}/${overlay.jurisdiction}/corrections.json`;
    const response = await fetch('/api/r2/upload-corrections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ r2Key, jsonData: JSON.stringify(overlay) })
    });

    // 6. Also append to corrections_log.jsonl
    const logEntries = buildLogEntries(overlay);
    if (logEntries.length > 0) {
        const logKey = `${overlay.state}/${overlay.jurisdiction}/corrections_log.jsonl`;
        await fetch('/api/r2/append-corrections-log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ r2Key: logKey, entries: logEntries })
        });
    }

    return { success: true, totalCorrections: overlay.totalCorrections };
}
```

### Merge Strategy: Fetch-Merge-Upload

When saving corrections, the browser:
1. **Fetches** existing `corrections.json` from R2 (if exists)
2. **Merges** new corrections into existing ones (last-write-wins by timestamp)
3. **Uploads** the merged result back to R2

This prevents overwriting corrections made by other users or from previous sessions.

```javascript
function mergeCorrections(newOverlay, existingOverlay) {
    for (const [docNbr, existingRecord] of Object.entries(existingOverlay.records)) {
        if (!newOverlay.records[docNbr]) {
            // Record only exists in existing -- keep it
            newOverlay.records[docNbr] = existingRecord;
            newOverlay.totalCorrections += Object.keys(existingRecord.corrections).length;
        } else {
            // Record exists in both -- merge field by field
            for (const [field, existingCorr] of Object.entries(existingRecord.corrections)) {
                const newCorr = newOverlay.records[docNbr].corrections[field];
                if (!newCorr) {
                    // Field only corrected in existing -- keep it
                    newOverlay.records[docNbr].corrections[field] = existingCorr;
                    newOverlay.totalCorrections++;
                } else if (new Date(existingCorr.correctedAt) > new Date(newCorr.correctedAt)) {
                    // Existing correction is newer -- keep existing
                    newOverlay.records[docNbr].corrections[field] = existingCorr;
                }
                // Else: new correction is newer or same -- keep new (already in overlay)
            }
        }
    }
}
```

### Integration with Existing dqSaveCorrectionsToCache()

Keep the existing IndexedDB cache for offline/instant access. Add R2 save as an additional step:

```javascript
// Modified save flow:
async function dqSaveAllCorrections() {
    // 1. Save to IndexedDB (instant, offline-capable)
    dqSaveCorrectionsToCache();

    // 2. Save to R2 (persistent, shared, pipeline-compatible)
    const r2Status = await fetch('/api/r2/status').then(r => r.json());
    if (r2Status.configured) {
        try {
            const result = await saveCorrectionsToR2();
            showToast(`Corrections saved to cloud (${result.totalCorrections} corrections)`);
        } catch (e) {
            console.warn('[Corrections] R2 save failed, corrections preserved locally:', e);
            showToast('Corrections saved locally (cloud sync failed)', 'warning');
        }
    }
}
```

---

## 6. Server-Side: Upload Endpoint

### New Endpoint: `POST /r2/upload-corrections`

Similar to existing `/r2/upload-geocoded` but accepts JSON instead of CSV.

```javascript
// In server/qdrant-proxy.js

// POST /r2/upload-corrections
// Body: { r2Key: "colorado/douglas/corrections.json", jsonData: "{...}" }
if (req.url === '/r2/upload-corrections' && req.method === 'POST') {
    const { r2Key, jsonData } = JSON.parse(body);

    // Validate r2Key format: {state}/{jurisdiction}/corrections.json
    const keyPattern = /^[a-z_-]+\/[a-z_-]+\/corrections(_.+)?\.json$/;
    if (!keyPattern.test(r2Key)) {
        res.writeHead(400);
        res.end(JSON.stringify({ error: 'Invalid key format' }));
        return;
    }

    // Upload to R2
    await s3Client.send(new PutObjectCommand({
        Bucket: R2_BUCKET_NAME,
        Key: r2Key,
        Body: jsonData,
        ContentType: 'application/json',
    }));

    res.writeHead(200);
    res.end(JSON.stringify({
        success: true,
        r2Key,
        size: Buffer.byteLength(jsonData),
        uploadedAt: new Date().toISOString()
    }));
}
```

### New Endpoint: `POST /r2/append-corrections-log`

Appends new entries to the JSONL audit log. Uses a read-append-write pattern since R2 doesn't support append operations.

```javascript
// POST /r2/append-corrections-log
// Body: { r2Key: "colorado/douglas/corrections_log.jsonl", entries: [...] }
if (req.url === '/r2/append-corrections-log' && req.method === 'POST') {
    const { r2Key, entries } = JSON.parse(body);

    // Read existing log (if any)
    let existingLog = '';
    try {
        const existing = await s3Client.send(new GetObjectCommand({
            Bucket: R2_BUCKET_NAME,
            Key: r2Key,
        }));
        existingLog = await existing.Body.transformToString();
    } catch (e) {
        // No existing log -- start fresh
    }

    // Append new entries
    const newEntries = entries.map(e => JSON.stringify(e)).join('\n');
    const combined = existingLog
        ? existingLog.trimEnd() + '\n' + newEntries + '\n'
        : newEntries + '\n';

    // Write back
    await s3Client.send(new PutObjectCommand({
        Bucket: R2_BUCKET_NAME,
        Key: r2Key,
        Body: combined,
        ContentType: 'application/x-ndjson',
    }));

    res.writeHead(200);
    res.end(JSON.stringify({ success: true, entriesAdded: entries.length }));
}
```

---

## 7. Incremental Monthly Processing

### The Problem

Every month, a new batch of crash data arrives from the DOT. The pipeline:
1. Downloads new monthly data
2. Processes and splits by jurisdiction
3. Uploads to R2

Without incremental processing, all previous corrections are lost because the pipeline overwrites the CSV with fresh DOT data.

### The Solution: Correction-Aware Pipeline

```
Monthly Pipeline Flow:

1. Download new month's data from DOT
2. Process + split by jurisdiction (existing steps)
3. NEW: For each jurisdiction:
   a. Fetch corrections.json from R2
   b. Identify which records in the new data match corrected Document Nbrs
   c. Apply corrections from overlay to matching records
   d. Records NOT in corrections.json -> run validation + geocoding as normal
   e. Records IN corrections.json -> skip validation (already corrected)
   f. Upload merged CSV to R2
   g. Re-generate aggregates.json and meta.json
   h. Update corrections.json if DOT data for a record changed
      (flag as "needs re-review" if original hash doesn't match)
```

### How "Skip Already-Corrected" Works

The corrections.json contains a `recordHash` for each corrected record. This hash is computed from the original row values **before** corrections were applied.

```python
# In merge_corrections.py

def should_skip_validation(row, corrections_overlay):
    """Check if this record was already corrected and DOT data hasn't changed."""
    doc_nbr = row.get('Document Nbr', '')
    if doc_nbr not in corrections_overlay.get('records', {}):
        return False  # Not previously corrected -> run validation

    record = corrections_overlay['records'][doc_nbr]
    current_hash = compute_row_hash(row)

    if current_hash == record.get('recordHash', ''):
        # DOT data unchanged -> apply existing corrections, skip validation
        return True
    else:
        # DOT data changed underneath us -> need re-review
        # Mark as "stale correction" so user is alerted
        return False

def compute_row_hash(row):
    """Hash key fields of a row for change detection."""
    # Hash only the fields that DOT provides (not our corrections)
    key_fields = ['Document Nbr', 'Crash Date', 'Crash Severity',
                  'RTE Name', 'Node', 'Physical Juris Name']
    values = '|'.join(str(row.get(f, '')) for f in key_fields)
    return hashlib.md5(values.encode()).hexdigest()[:8]
```

### Monthly Processing Decision Tree

```
For each record in new DOT data:
  |
  |-- Is Document Nbr in corrections.json?
  |     |
  |     |-- YES: Does recordHash match current row hash?
  |     |     |
  |     |     |-- YES (data unchanged):
  |     |     |     Apply all corrections from overlay
  |     |     |     Skip validation/geocoding
  |     |     |     Status: "corrected"
  |     |     |
  |     |     |-- NO (DOT updated this record):
  |     |           Flag as "stale-correction"
  |     |           Apply corrections cautiously
  |     |           Re-run validation to check for new issues
  |     |           User should review in next session
  |     |
  |     |-- NO: Run full validation + geocoding as normal
  |           Status: "new-uncorrected"
```

### New Records (Not in Previous Month)

Records that appear for the first time (new Document Nbrs) always get full validation and geocoding. No corrections exist for them yet.

### Removed Records (In Corrections but Not in New Data)

If a Document Nbr exists in corrections.json but NOT in the new DOT data:
- Keep the correction in the overlay (don't delete)
- Mark as `"status": "orphaned"` with the date it was last seen
- After 12 months of orphaned status, auto-archive to corrections_log.jsonl

---

## 8. Pipeline Integration: Merge Corrections

### New Script: `scripts/merge_corrections.py`

```python
#!/usr/bin/env python3
"""
Merge corrections overlay into canonical CSV during pipeline processing.

Reads:
  - Fresh CSV from DOT pipeline (e.g., data/CDOT/douglas_all_roads.csv)
  - corrections.json from R2 (downloaded during pipeline)

Produces:
  - Merged CSV with corrections applied
  - Updated corrections.json with stale/orphaned status flags
  - Validation skip list (Document Nbrs to skip during validation)

Usage:
  python scripts/merge_corrections.py \
    --csv data/CDOT/douglas_all_roads.csv \
    --corrections data/colorado/douglas/corrections.json \
    --output data/CDOT/douglas_all_roads.csv

  # Dry run (show what would be merged):
  python scripts/merge_corrections.py \
    --csv data/CDOT/douglas_all_roads.csv \
    --corrections data/colorado/douglas/corrections.json \
    --dry-run
"""

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def compute_row_hash(row, key_fields=None):
    """Hash key fields of a row for change detection."""
    if key_fields is None:
        key_fields = ['Document Nbr', 'Crash Date', 'Crash Severity',
                      'RTE Name', 'Node', 'Physical Juris Name']
    values = '|'.join(str(row.get(f, '')) for f in key_fields)
    return hashlib.md5(values.encode()).hexdigest()[:8]


def merge_corrections(csv_path, corrections_path, output_path, dry_run=False):
    """Merge corrections overlay into CSV."""

    # Load corrections
    with open(corrections_path) as f:
        overlay = json.load(f)

    records = overlay.get('records', {})
    if not records:
        print(f'  No corrections to apply')
        return 0, 0, 0

    # Read CSV
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    applied = 0
    skipped = 0
    stale = 0
    skip_list = set()  # Document Nbrs that had corrections applied

    for row in rows:
        doc_nbr = row.get('Document Nbr', '').strip()
        if doc_nbr not in records:
            continue

        record = records[doc_nbr]
        current_hash = compute_row_hash(row)
        stored_hash = record.get('recordHash', '')

        if stored_hash and current_hash != stored_hash:
            # DOT data changed -- apply cautiously, flag as stale
            stale += 1
            record['_status'] = 'stale'
            record['_staleDetectedAt'] = datetime.now(timezone.utc).isoformat()

        # Apply corrections
        for field, correction in record.get('corrections', {}).items():
            corrected_value = correction.get('corrected', '')
            if field in row and corrected_value:
                if not dry_run:
                    row[field] = corrected_value
                applied += 1

        skip_list.add(doc_nbr)
        skipped += 1

    # Check for orphaned corrections (in overlay but not in CSV)
    csv_doc_nbrs = {row.get('Document Nbr', '').strip() for row in rows}
    for doc_nbr in records:
        if doc_nbr not in csv_doc_nbrs:
            records[doc_nbr].setdefault('_status', 'orphaned')
            records[doc_nbr]['_lastSeenAt'] = records[doc_nbr].get(
                '_lastSeenAt', datetime.now(timezone.utc).isoformat())

    if dry_run:
        print(f'  DRY RUN: Would apply {applied} corrections to {skipped} records ({stale} stale)')
        return applied, skipped, stale

    # Write merged CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Write updated corrections overlay (with stale/orphaned flags)
    overlay['_lastMerged'] = datetime.now(timezone.utc).isoformat()
    with open(corrections_path, 'w') as f:
        json.dump(overlay, f, indent=2)
        f.write('\n')

    # Write skip list for validation step
    skip_list_path = Path(output_path).parent / f'{Path(output_path).stem}_skip_validation.json'
    with open(skip_list_path, 'w') as f:
        json.dump({'skipDocumentNbrs': sorted(skip_list)}, f, indent=2)
        f.write('\n')

    print(f'  Applied {applied} corrections to {skipped} records ({stale} stale)')
    print(f'  Skip list: {skip_list_path}')

    return applied, skipped, stale


def main():
    parser = argparse.ArgumentParser(description='Merge corrections overlay into CSV')
    parser.add_argument('--csv', required=True, help='Path to CSV file')
    parser.add_argument('--corrections', required=True, help='Path to corrections.json')
    parser.add_argument('--output', help='Output CSV path (default: overwrite input)')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
    args = parser.parse_args()

    output = args.output or args.csv
    print(f'Merging corrections: {args.corrections} -> {args.csv}')
    applied, skipped, stale = merge_corrections(args.csv, args.corrections, output, args.dry_run)

    if stale > 0:
        print(f'\n  WARNING: {stale} records have stale corrections (DOT data changed)')
        print(f'  These should be reviewed in the Upload Tab')


if __name__ == '__main__':
    main()
```

### Pipeline.yml Integration

Add to `.github/workflows/pipeline.yml` after CSV split and before validation:

```yaml
# Step: Merge corrections from R2 (if available)
- name: Merge user corrections
  run: |
    # Download corrections.json from R2 for each jurisdiction
    for corrections_file in data/${STATE}/**/corrections.json; do
      if [ -f "$corrections_file" ]; then
        jurisdiction=$(dirname "$corrections_file" | xargs basename)
        csv_file="data/${DATA_DIR}/${jurisdiction}_all_roads.csv"
        if [ -f "$csv_file" ]; then
          python scripts/merge_corrections.py \
            --csv "$csv_file" \
            --corrections "$corrections_file"
        fi
      fi
    done

# Step: Run validation (skip already-corrected records)
- name: Validate crash data
  run: |
    python scripts/validate_crash_data.py \
      --state ${{ env.STATE }} \
      --skip-list data/${DATA_DIR}/*_skip_validation.json
```

---

## 9. GPS Recovery via OSM Nominatim

### Current Geocoding Infrastructure

The geocode engine (`app/geocode-engine.js`) uses 3 strategies:

| Strategy | Speed | Confidence | Rate Limit |
|----------|-------|-----------|------------|
| Node Lookup | Instant | 0.95 | None |
| OSM Nominatim | 1 req/sec | 0.5-0.9 | 1 req/1.1s, max 500 |
| Milepost Interpolation | Instant | 0.4-0.9 | None |

### How GPS Corrections Flow into corrections.json

When the geocode engine recovers coordinates:

```javascript
// In geocode-engine.js, after successful geocoding:
function onGeocodeComplete(docNbr, lat, lng, strategy, confidence) {
    // 1. Update sampleRows (existing behavior)
    const rowIdx = findRowByDocNbr(docNbr);
    if (rowIdx >= 0) {
        crashState.sampleRows[rowIdx]['x'] = String(lng);
        crashState.sampleRows[rowIdx]['y'] = String(lat);
    }

    // 2. NEW: Also record in validationState.manualCorrections
    // (so saveCorrectionsToR2() captures GPS corrections)
    if (!validationState.manualCorrections[docNbr]) {
        validationState.manualCorrections[docNbr] = {};
    }
    validationState.manualCorrections[docNbr]['x'] = String(lng);
    validationState.manualCorrections[docNbr]['y'] = String(lat);

    // 3. Store geocoding metadata for the overlay
    validationState.manualCorrections[docNbr]['_geocodeSource'] = strategy;
    validationState.manualCorrections[docNbr]['_geocodeConfidence'] = confidence;
}
```

### Incremental GPS Recovery

Records already in corrections.json with GPS coordinates (`source: "geocode-osm"`) are **not re-geocoded** in subsequent months:

```javascript
// In geocode-engine.js startGeocoding():
async function startGeocoding() {
    // NEW: Load existing corrections from R2 to skip already-geocoded records
    const existing = await fetchExistingCorrections();
    const alreadyGeocoded = new Set();

    if (existing?.records) {
        for (const [docNbr, record] of Object.entries(existing.records)) {
            if (record.corrections?.x?.source?.startsWith('geocode-')) {
                alreadyGeocoded.add(docNbr);
            }
        }
    }

    // Filter out already-geocoded records
    const needsGeocoding = recordsWithMissingGPS.filter(
        r => !alreadyGeocoded.has(r[COL.ID])
    );

    console.log(`[Geocode] ${needsGeocoding.length} records need geocoding`
        + ` (${alreadyGeocoded.size} already geocoded, skipped)`);

    // Proceed with geocoding only the new records
    for (const record of needsGeocoding) {
        await geocodeRecord(record);
    }
}
```

---

## 10. R2 Storage Layout

### Per-Jurisdiction Structure (After All Phases)

```
R2 Bucket: crash-lens-data
  colorado/
    douglas/
      all_roads.csv                    <-- Canonical CSV (pipeline output)
      all_roads.parquet                <-- Parquet (Phase 2)
      county_roads.csv                 <-- Canonical CSV
      county_roads.parquet             <-- Parquet (Phase 2)
      no_interstate.csv                <-- Canonical CSV
      no_interstate.parquet            <-- Parquet (Phase 2)
      aggregates.json                  <-- Pre-computed (Phase 1)
      aggregates_county_roads.json     <-- Pre-computed (Phase 1)
      aggregates_no_interstate.json    <-- Pre-computed (Phase 1)
      meta.json                        <-- Cache invalidation (Phase 1)
      meta_county_roads.json           <-- Cache invalidation (Phase 1)
      meta_no_interstate.json          <-- Cache invalidation (Phase 1)
      corrections.json                 <-- Corrections overlay (Phase 5) ~5-50 KB
      corrections_log.jsonl            <-- Audit trail (Phase 5) grows over time
```

### Size Estimates for Corrections

| Jurisdiction Size | Records | Typical Corrections | corrections.json Size |
|-------------------|---------|--------------------|-----------------------|
| Small county (500 records) | 500 | 5-20 | ~2-5 KB |
| Medium county (2000 records) | 2000 | 20-80 | ~10-25 KB |
| Large county (10000 records) | 10000 | 50-200 | ~25-75 KB |
| Very large (50000 records) | 50000 | 100-500 | ~50-200 KB |

The corrections overlay is always tiny compared to the full CSV.

---

## 11. Parquet/DuckDB Integration

### How Corrections Interact with Parquet

1. **Pipeline generates Parquet AFTER merging corrections** -- so Parquet files always contain the corrected data
2. **DuckDB queries in the browser read corrected Parquet** -- no need for browser-side correction application
3. **If user makes NEW corrections in-session** -- corrections applied to in-memory sampleRows (existing behavior) and saved to R2 overlay for next pipeline run

### Data Freshness Flow

```
DOT releases new data (monthly)
  -> Pipeline downloads and processes
  -> Pipeline fetches corrections.json from R2
  -> Pipeline applies corrections to fresh CSV
  -> Pipeline generates:
     - Corrected CSV (with corrections merged in)
     - Corrected Parquet (from corrected CSV)
     - New aggregates.json (from corrected data)
     - New meta.json (hash changes -> browser cache invalidated)
  -> All uploaded to R2

Browser user visits:
  -> Fetches meta.json -> hash changed -> fetches new aggregates.json
  -> Dashboard shows corrected data instantly
  -> Map/CMF tabs query corrected Parquet via DuckDB
  -> If user makes more corrections -> saves to corrections.json overlay
  -> Next pipeline run picks up new corrections
```

### Browser-Side Correction Application (During Session)

When a user makes corrections in the current session, they're applied to `crashState.sampleRows` immediately. The aggregates displayed to the user will reflect these corrections in real-time. However, the `aggregates.json` on R2 won't be updated until the next pipeline run.

This is acceptable because:
- The user sees their own corrections instantly (in-memory)
- Other users seeing this jurisdiction will get updated data after the next pipeline run
- Corrections are persisted to R2 immediately (via `saveCorrectionsToR2()`)

---

## 12. Data Flow Diagrams

### Complete Corrections Lifecycle

```
USER SESSION (Browser)
========================

1. Load Data
   R2 -> aggregates.json + meta.json -> Dashboard instant
   R2 -> CSV (background) -> crashState.sampleRows

2. Validate Data (Upload Tab)
   crashState.sampleRows -> dqRunValidation()
     -> Auto-corrections (>= 85% confidence)
        -> Applied to sampleRows
        -> Stored in validationState.corrections[]
     -> Flagged records (< 85% confidence)
        -> Shown to user for manual review

3. Load Existing Corrections from R2 (NEW)
   R2 -> corrections.json -> Skip already-corrected records
   Already-corrected records shown as "Previously Corrected" in UI

4. User Reviews & Corrects
   Manual edits -> validationState.manualCorrections[docNbr][field]
   GPS recovery -> geocode-engine -> manualCorrections[docNbr][x/y]

5. Save Corrections (NEW)
   A) IndexedDB (instant, local) -> dqSaveCorrectionsToCache()
   B) R2 (persistent, shared) -> saveCorrectionsToR2()
      -> POST /r2/upload-corrections
      -> corrections.json written to R2
      -> corrections_log.jsonl appended


PIPELINE (GitHub Actions, Monthly)
===================================

1. Download new data from DOT
2. Process + split by jurisdiction (existing)
3. Fetch corrections.json from R2 for each jurisdiction (NEW)
4. Merge corrections into fresh CSV (NEW: merge_corrections.py)
   - Match by Document Nbr
   - Check recordHash for stale corrections
   - Generate skip_validation.json for already-corrected records
5. Run validation on non-corrected records only (incremental)
6. Run geocoding on records without GPS (skip already-geocoded)
7. Generate aggregates.json + meta.json (Phase 1)
8. Generate Parquet files (Phase 2)
9. Upload everything to R2 (CSV + Parquet + JSON)
```

### Monthly Incremental Processing Timeline

```
Month 1: Fresh DOT data arrives
  - 2000 records total
  - Validation finds 80 issues, auto-corrects 60, flags 20
  - User manually corrects 15 of 20 flagged records
  - GPS recovered for 30 records
  - corrections.json saved with 105 corrected records (60 auto + 15 manual + 30 GPS)

Month 2: New DOT data arrives (includes Month 1 + new crashes)
  - 2150 records total (150 new)
  - Pipeline fetches corrections.json (105 records)
  - Pipeline checks: 100 of 105 records still match (hash unchanged)
  - Pipeline applies 100 corrections automatically (skips validation)
  - Pipeline flags 5 records as "stale" (DOT updated them)
  - Pipeline runs validation on 150 new + 5 stale = 155 records (not all 2150)
  - User reviews 5 stale + any new flagged records
  - corrections.json updated with new corrections

Month 3: Same pattern, only new + stale records need attention
  - Over time, the number of records needing review decreases
  - Most corrections are applied automatically from the overlay
```

---

## 13. Edge Cases & Safety

### What If Two Users Correct the Same Record?

**Current design: Last-write-wins with timestamps.**

When saving corrections, the browser fetches existing `corrections.json`, merges using timestamps:
- If existing correction is newer -> keep existing
- If new correction is newer -> overwrite with new
- Conflicts are unlikely because most users work on different jurisdictions

**Future enhancement:** Show conflict resolution UI if the same record was corrected differently by two users within the same day.

### What If DOT Retroactively Changes a Record?

The `recordHash` catches this. When the pipeline detects a hash mismatch:
1. The correction is flagged as `"_status": "stale"`
2. The correction is still applied (better than nothing)
3. User is alerted in the Upload Tab: "5 records have stale corrections -- DOT data changed"
4. User can review and update the correction or confirm it's still valid

### What If corrections.json Gets Corrupted?

1. **corrections_log.jsonl** serves as backup -- can reconstruct corrections.json from the log
2. **IndexedDB** has a local copy of the user's corrections
3. **Canonical CSV on R2** is never directly modified by corrections (overlay pattern)

### What If R2 Upload Fails?

1. Corrections are always saved to IndexedDB first (instant, reliable)
2. R2 upload is attempted as a second step
3. If R2 fails, user sees "Corrections saved locally (cloud sync failed)"
4. Next time the user saves, the full corrections set is re-attempted

### What About Large Jurisdictions (50K+ records)?

Even with 500 corrections on a 50K-record jurisdiction:
- corrections.json is still <200 KB (tiny)
- Merge is O(n) where n = number of CSV rows (single pass)
- Skip list lookup is O(1) (Set-based)
- No performance concerns at any realistic scale

### What About Records Without Document Nbr?

If a record has no `Document Nbr` (empty or missing):
- It cannot be tracked in corrections.json
- Corrections for such records are local-only
- The validation UI should flag this as a critical data quality issue
- Pipeline should assign a synthetic ID based on date + route + node hash

---

## 14. Implementation Plan

### Step 1: corrections.json Format + Browser Save (This PR)

**Changes:**
1. Add `saveCorrectionsToR2()` function to `app/index.html`
2. Add `POST /r2/upload-corrections` endpoint to `server/qdrant-proxy.js`
3. Modify `dqSaveCorrectionsToCache()` to also trigger R2 save
4. Add "Save to Cloud" button in Upload Tab UI
5. Load existing corrections.json when entering Upload Tab

### Step 2: Pipeline Merge Script

**Changes:**
1. Create `scripts/merge_corrections.py`
2. Modify pipeline.yml to download corrections.json and run merge before validation
3. Generate skip_validation.json for validation step

### Step 3: Incremental Geocoding

**Changes:**
1. Modify `geocode-engine.js` to fetch existing corrections and skip already-geocoded records
2. Store geocoding metadata in corrections overlay
3. Update `saveGeocodedDataToR2()` to save corrections overlay instead of full CSV

### Step 4: UI Enhancements

**Changes:**
1. Show "Previously Corrected" badge on records that have corrections in overlay
2. Show "Stale Correction" warning on records where DOT data changed
3. Add corrections summary panel showing total corrections, by source, by date
4. Add "Export Corrections Log" button for audit purposes

---

## 15. Files to Modify

| File | Change | Step |
|------|--------|------|
| `app/index.html` | `saveCorrectionsToR2()`, `fetchExistingCorrections()`, `mergeCorrections()`, UI for save-to-cloud button, previously-corrected badge | 1, 4 |
| `server/qdrant-proxy.js` | `POST /r2/upload-corrections`, `POST /r2/append-corrections-log` endpoints | 1 |
| `scripts/merge_corrections.py` | **NEW** -- merge corrections overlay into CSV | 2 |
| `.github/workflows/pipeline.yml` | Download corrections + run merge before validation | 2 |
| `app/geocode-engine.js` | Skip already-geocoded records, store geocode metadata in manualCorrections | 3 |

---

## 16. Verification Plan

### Step 1 Verification
1. Make corrections in Upload Tab -> click "Save to Cloud"
2. Check R2 for `corrections.json` (correct format, correct values)
3. Clear browser data -> reload -> verify corrections are loaded from R2
4. Make additional corrections -> save -> verify merge (not overwrite) of existing corrections
5. Check `corrections_log.jsonl` in R2 has correct audit entries

### Step 2 Verification
1. Run `python scripts/merge_corrections.py --dry-run` -> verify correct merge preview
2. Run merge -> verify CSV has corrections applied
3. Verify skip_validation.json contains correct Document Nbrs
4. Modify a record in the CSV manually (simulate DOT change) -> verify "stale" detection
5. Run full pipeline -> verify aggregates.json reflects corrected data

### Step 3 Verification
1. Geocode 10 records -> save corrections to R2
2. Reload page -> start geocoding again -> verify 10 records are skipped
3. Add 5 new records without GPS -> verify only 5 are geocoded (not 15)

### Step 4 Verification
1. Load county with existing corrections -> verify "Previously Corrected" badges
2. Simulate DOT data change -> verify "Stale Correction" warning
3. Export corrections log -> verify CSV/JSON format is correct
