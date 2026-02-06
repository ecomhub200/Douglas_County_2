#!/usr/bin/env python3
"""
Split CDOT merged crash data into three road-type filter files.

Reads the all-roads merged CSV and produces:
  - {jurisdiction}_county_roads.csv  : Agency Id = "DSO" only (county-maintained roads)
  - {jurisdiction}_no_interstate.csv : All roads EXCEPT Interstate Highway
  - {jurisdiction}_all_roads.csv     : Already exists (unchanged)

Usage:
    python split_cdot_data.py [--jurisdiction douglas] [--data-dir ../data/CDOT]

Filtering logic:
    county_roads   -> Agency Id = "DSO" (Douglas County Sheriff's Office)
                      DSO only reports on county-maintained roads
    no_interstate  -> System Code != "Interstate Highway"
                      All Douglas County crashes minus interstates
    all_roads      -> Source file (County = "DOUGLAS"), unchanged
"""

import argparse
import csv
import os
import sys

AGENCY_ID_COLUMN = "Agency Id"
SYSTEM_CODE_COLUMN = "System Code"
COUNTY_COLUMN = "County"

# Douglas County Sheriff's Office - handles county-maintained roads only
COUNTY_AGENCY_ID = "DSO"


def split_data(source_path, output_dir, jurisdiction):
    """Read the all-roads CSV and write filtered versions."""

    if not os.path.exists(source_path):
        print(f"ERROR: Source file not found: {source_path}")
        sys.exit(1)

    # Read all rows once
    with open(source_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames

        for required_col in [AGENCY_ID_COLUMN, SYSTEM_CODE_COLUMN]:
            if required_col not in headers:
                print(f"ERROR: '{required_col}' column not found in CSV headers.")
                print(f"  Available columns: {', '.join(headers[:10])}...")
                sys.exit(1)

        all_rows = list(reader)

    print(f"Source: {source_path}")
    print(f"Total rows: {len(all_rows):,}")
    print(f"Output directory: {output_dir}")
    print()

    # Show distributions
    agency_counts = {}
    system_counts = {}
    for row in all_rows:
        ag = row[AGENCY_ID_COLUMN].strip()
        sc = row[SYSTEM_CODE_COLUMN].strip()
        agency_counts[ag] = agency_counts.get(ag, 0) + 1
        system_counts[sc] = system_counts.get(sc, 0) + 1

    print("Agency Id distribution:")
    for ag, count in sorted(agency_counts.items(), key=lambda x: -x[1]):
        marker = " <-- county-maintained" if ag == COUNTY_AGENCY_ID else ""
        print(f"  {ag}: {count:,}{marker}")
    print()

    print("System Code distribution:")
    for sc, count in sorted(system_counts.items(), key=lambda x: -x[1]):
        print(f"  {sc}: {count:,}")
    print()

    # === Filter 1: county_roads (Agency Id = DSO only) ===
    county_roads = [r for r in all_rows if r[AGENCY_ID_COLUMN].strip() == COUNTY_AGENCY_ID]
    _write_csv(
        os.path.join(output_dir, f"{jurisdiction}_county_roads.csv"),
        headers, county_roads,
        f"County/City Roads Only (Agency Id = {COUNTY_AGENCY_ID})",
        len(all_rows)
    )

    # === Filter 2: no_interstate (all except Interstate Highway) ===
    no_interstate = [r for r in all_rows if r[SYSTEM_CODE_COLUMN].strip() != "Interstate Highway"]
    _write_csv(
        os.path.join(output_dir, f"{jurisdiction}_no_interstate.csv"),
        headers, no_interstate,
        "All Roads (No Interstate) - System Code != Interstate Highway",
        len(all_rows)
    )

    print("Done! All filter files created.")


def _write_csv(output_path, headers, rows, description, total):
    """Write a filtered CSV and print summary."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Created: {output_path}")
    print(f"  Filter: {description}")
    print(f"  Rows: {len(rows):,} / {total:,}")
    print(f"  Size: {size_mb:.1f} MB")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Split CDOT merged crash data into road-type filter files."
    )
    parser.add_argument(
        "--jurisdiction",
        default="douglas",
        help="Jurisdiction name (default: douglas)",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Directory containing the all_roads CSV (default: auto-detect)",
    )
    args = parser.parse_args()

    # Auto-detect data directory
    if args.data_dir:
        data_dir = args.data_dir
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.dirname(script_dir)
        data_dir = os.path.join(repo_root, "data", "CDOT")

    source_file = os.path.join(data_dir, f"{args.jurisdiction}_all_roads.csv")
    split_data(source_file, data_dir, args.jurisdiction)


if __name__ == "__main__":
    main()
