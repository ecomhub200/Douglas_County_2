#!/usr/bin/env python3
"""
Split CDOT merged crash data into three road-type filter files.

Reads the all-roads merged CSV and produces:
  - {jurisdiction}_county_roads.csv  : City Street + County Road only (local roads)
  - {jurisdiction}_no_interstate.csv : All roads EXCEPT Interstate Highway
  - {jurisdiction}_all_roads.csv     : Already exists (unchanged)

Usage:
    python split_cdot_data.py [--jurisdiction douglas] [--data-dir ../data/CDOT]

System Code values in CDOT data:
    City Street        -> local (included in county_roads)
    County Road        -> local (included in county_roads)
    State Highway      -> state-maintained
    Interstate Highway -> state-maintained (excluded from no_interstate)
    Frontage Road      -> state-maintained
    Non Crash          -> misc
"""

import argparse
import csv
import os
import sys

# Filter definitions matching states/colorado/config.json filterProfiles
FILTER_PROFILES = {
    "county_roads": {
        "description": "County/City Roads Only - Local roads (NonVDOT equivalent)",
        "include_systems": ["City Street", "County Road"],
        "exclude_systems": [],
    },
    "no_interstate": {
        "description": "All Roads (No Interstate) - Includes state highways",
        "include_systems": None,  # None = include all
        "exclude_systems": ["Interstate Highway"],
    },
    # all_roads is the source file itself - no filtering needed
}

SYSTEM_CODE_COLUMN = "System Code"


def split_data(source_path, output_dir, jurisdiction):
    """Read the all-roads CSV and write filtered versions."""

    if not os.path.exists(source_path):
        print(f"ERROR: Source file not found: {source_path}")
        sys.exit(1)

    # Read all rows once
    with open(source_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        if SYSTEM_CODE_COLUMN not in headers:
            print(f"ERROR: '{SYSTEM_CODE_COLUMN}' column not found in CSV headers.")
            print(f"  Available columns: {', '.join(headers[:10])}...")
            sys.exit(1)

        all_rows = list(reader)

    print(f"Source: {source_path}")
    print(f"Total rows: {len(all_rows):,}")
    print(f"Output directory: {output_dir}")
    print()

    # Show system code distribution
    system_counts = {}
    for row in all_rows:
        sc = row[SYSTEM_CODE_COLUMN]
        system_counts[sc] = system_counts.get(sc, 0) + 1
    print("System Code distribution:")
    for sc, count in sorted(system_counts.items(), key=lambda x: -x[1]):
        print(f"  {sc}: {count:,}")
    print()

    # Generate each filtered file
    for suffix, profile in FILTER_PROFILES.items():
        output_path = os.path.join(output_dir, f"{jurisdiction}_{suffix}.csv")

        filtered = []
        for row in all_rows:
            system = row[SYSTEM_CODE_COLUMN]

            # If include list is specified, row must match
            if profile["include_systems"] is not None:
                if system not in profile["include_systems"]:
                    continue

            # If exclude list is specified, row must NOT match
            if system in profile["exclude_systems"]:
                continue

            filtered.append(row)

        # Write filtered CSV
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(filtered)

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"Created: {output_path}")
        print(f"  Profile: {profile['description']}")
        print(f"  Rows: {len(filtered):,} / {len(all_rows):,}")
        print(f"  Size: {size_mb:.1f} MB")
        print()

    print("Done! All filter files created.")


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
        # Try relative to script location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.dirname(script_dir)
        data_dir = os.path.join(repo_root, "data", "CDOT")

    source_file = os.path.join(data_dir, f"{args.jurisdiction}_all_roads.csv")
    split_data(source_file, data_dir, args.jurisdiction)


if __name__ == "__main__":
    main()
