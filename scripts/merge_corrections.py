#!/usr/bin/env python3
"""
Merge corrections overlay into canonical CSV during pipeline processing.

Reads a corrections.json overlay (uploaded by users from the Upload Tab) and
applies the corrections to the fresh CSV data from the DOT pipeline. This
enables incremental processing: already-corrected records are patched
automatically, and only new/changed records need validation.

Reads:
  - Fresh CSV from DOT pipeline (e.g., data/CDOT/douglas_all_roads.csv)
  - corrections.json from R2 or local (downloaded during pipeline)

Produces:
  - Merged CSV with corrections applied (overwrites input by default)
  - Updated corrections.json with stale/orphaned status flags
  - Skip list JSON (Document Nbrs to skip during validation)

Usage:
  # Apply corrections and overwrite CSV in place:
  python scripts/merge_corrections.py \\
    --csv data/CDOT/douglas_all_roads.csv \\
    --corrections data/colorado/douglas/corrections.json

  # Write to separate output file:
  python scripts/merge_corrections.py \\
    --csv data/CDOT/douglas_all_roads.csv \\
    --corrections data/colorado/douglas/corrections.json \\
    --output data/CDOT/douglas_all_roads_corrected.csv

  # Dry run (show what would be merged):
  python scripts/merge_corrections.py \\
    --csv data/CDOT/douglas_all_roads.csv \\
    --corrections data/colorado/douglas/corrections.json \\
    --dry-run

  # Specify the Document Nbr column name (default: "Document Nbr"):
  python scripts/merge_corrections.py \\
    --csv data.csv --corrections corrections.json \\
    --id-column "CrashID"

Prerequisites:
  None (uses only Python standard library)
"""

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def compute_row_hash(row, key_fields=None):
    """Hash key fields of a row for change detection.

    Returns an 8-character hex digest. Used to detect when DOT data
    changes underneath existing corrections (stale corrections).
    """
    if key_fields is None:
        key_fields = ['Document Nbr', 'Crash Date', 'Crash Severity',
                      'RTE Name', 'Node', 'Physical Juris Name']
    values = '|'.join(str(row.get(f, '')) for f in key_fields)
    return hashlib.md5(values.encode()).hexdigest()[:8]


def merge_corrections(csv_path, corrections_path, output_path,
                      id_column='Document Nbr', dry_run=False):
    """Merge corrections overlay into CSV.

    Returns:
        tuple: (applied_count, skipped_count, stale_count)
    """
    # Load corrections overlay
    try:
        with open(corrections_path, encoding='utf-8') as f:
            overlay = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f'  ERROR: Cannot read corrections file: {e}')
        return 0, 0, 0

    records = overlay.get('records', {})
    if not records:
        print('  No corrections to apply')
        return 0, 0, 0

    # Read CSV
    try:
        with open(csv_path, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)
    except FileNotFoundError:
        print(f'  ERROR: CSV file not found: {csv_path}')
        return 0, 0, 0

    if not fieldnames:
        print('  ERROR: CSV has no headers')
        return 0, 0, 0

    applied = 0
    skipped = 0
    stale = 0
    skip_list = set()

    for row in rows:
        doc_nbr = row.get(id_column, '').strip()
        if not doc_nbr or doc_nbr not in records:
            continue

        record = records[doc_nbr]
        current_hash = compute_row_hash(row)
        stored_hash = record.get('recordHash', '')

        if stored_hash and current_hash != stored_hash:
            # DOT data changed for this record since correction was made
            stale += 1
            record['_status'] = 'stale'
            record['_staleDetectedAt'] = datetime.now(timezone.utc).isoformat()
            record['_currentHash'] = current_hash

        # Apply corrections to the row
        corrections = record.get('corrections', {})
        for field, correction in corrections.items():
            corrected_value = correction.get('corrected', '')
            if field in row and corrected_value:
                if not dry_run:
                    row[field] = corrected_value
                applied += 1

        skip_list.add(doc_nbr)
        skipped += 1

    # Detect orphaned corrections (in overlay but not in CSV)
    csv_doc_nbrs = {row.get(id_column, '').strip() for row in rows}
    orphaned = 0
    for doc_nbr in records:
        if doc_nbr not in csv_doc_nbrs:
            if records[doc_nbr].get('_status') != 'orphaned':
                records[doc_nbr]['_status'] = 'orphaned'
                records[doc_nbr]['_orphanedAt'] = datetime.now(timezone.utc).isoformat()
                orphaned += 1

    if dry_run:
        print(f'  DRY RUN: Would apply {applied} field corrections '
              f'to {skipped} records ({stale} stale, {orphaned} orphaned)')
        return applied, skipped, stale

    # Write merged CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Update corrections overlay with status flags
    overlay['_lastMerged'] = datetime.now(timezone.utc).isoformat()
    overlay['_mergedRecords'] = skipped
    overlay['_staleRecords'] = stale
    overlay['_orphanedRecords'] = orphaned
    with open(corrections_path, 'w', encoding='utf-8') as f:
        json.dump(overlay, f, indent=2)
        f.write('\n')

    # Write skip list for validation step
    skip_list_path = Path(output_path).parent / f'{Path(output_path).stem}_skip_validation.json'
    with open(str(skip_list_path), 'w', encoding='utf-8') as f:
        json.dump({
            'generated': datetime.now(timezone.utc).isoformat(),
            'csvFile': str(csv_path),
            'correctionsFile': str(corrections_path),
            'skipDocumentNbrs': sorted(skip_list),
            'totalSkipped': len(skip_list),
            'staleCount': stale
        }, f, indent=2)
        f.write('\n')

    print(f'  Applied {applied} field corrections to {skipped} records')
    if stale > 0:
        print(f'  WARNING: {stale} records have stale corrections (DOT data changed)')
    if orphaned > 0:
        print(f'  INFO: {orphaned} corrected records no longer in CSV (orphaned)')
    print(f'  Skip list written: {skip_list_path}')

    return applied, skipped, stale


def main():
    parser = argparse.ArgumentParser(
        description='Merge corrections overlay into canonical CSV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--csv', required=True,
                        help='Path to CSV file to merge corrections into')
    parser.add_argument('--corrections', required=True,
                        help='Path to corrections.json overlay')
    parser.add_argument('--output',
                        help='Output CSV path (default: overwrite input)')
    parser.add_argument('--id-column', default='Document Nbr',
                        help='Column name for unique record identifier (default: "Document Nbr")')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview what would be merged without writing files')
    args = parser.parse_args()

    output = args.output or args.csv

    print(f'CRASH LENS - Corrections Merge Tool')
    print(f'  CSV: {args.csv}')
    print(f'  Corrections: {args.corrections}')
    print(f'  Output: {output}')
    print(f'  ID Column: {args.id_column}')
    if args.dry_run:
        print(f'  Mode: DRY RUN')
    print()

    applied, skipped, stale = merge_corrections(
        args.csv, args.corrections, output,
        id_column=args.id_column, dry_run=args.dry_run
    )

    if stale > 0:
        print(f'\n  ACTION NEEDED: {stale} records have stale corrections.')
        print(f'  Review these in the Upload Tab after pipeline completes.')
        sys.exit(2)  # Exit code 2 = stale corrections (non-fatal warning)


if __name__ == '__main__':
    main()
