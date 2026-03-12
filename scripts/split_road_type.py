#!/usr/bin/env python3
"""
Split jurisdiction CSVs into 3 road-type variants.

For each jurisdiction's all_roads.csv, produces:
  - {jurisdiction}_county_roads.csv  (local/county roads only)
  - {jurisdiction}_no_interstate.csv (everything except interstates)
  - {jurisdiction}_all_roads.csv     (already exists, copied/kept as-is)

Road system filtering is config-driven from states/{state}/config.json → roadSystems.splitConfig.

Usage:
    # Split a single jurisdiction
    python scripts/split_road_type.py --state virginia --jurisdiction henrico --data-dir data

    # Split multiple jurisdictions
    python scripts/split_road_type.py --state colorado --jurisdictions adams arapahoe douglas --data-dir data/CDOT

    # Split all jurisdictions in a directory (auto-detect from *_all_roads.csv files)
    python scripts/split_road_type.py --state virginia --data-dir data --auto
"""

import argparse
import csv
import json
import logging
import os
import re
import sys
from pathlib import Path

logger = logging.getLogger('split_road_type')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

PROJECT_ROOT = Path(__file__).parent.parent


def load_state_config(state):
    """Load state-specific config for road system split rules."""
    config_path = PROJECT_ROOT / 'states' / state / 'config.json'
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}


def get_split_config(state_config):
    """Get road split configuration."""
    return state_config.get('roadSystems', {}).get('splitConfig', {})


def get_system_column(headers, split_config):
    """Determine which column to use for road system filtering."""
    # Check splitConfig for column hints
    county_config = split_config.get('countyRoads', {})
    interstate_config = split_config.get('interstateExclusion', {})

    # Try configured columns first
    for config in [county_config, interstate_config]:
        col = config.get('column', '')
        if col and col in headers:
            return col

    # Fall back to standard SYSTEM column
    for candidate in ['SYSTEM', 'System', 'system']:
        if candidate in headers:
            return candidate

    return None


def filter_county_roads(rows, headers, split_config):
    """Filter to county/local roads only."""
    county_config = split_config.get('countyRoads', {})
    method = county_config.get('method', 'system_column')

    col_idx = {h: i for i, h in enumerate(headers)}

    if method == 'system_column':
        col = county_config.get('column', 'SYSTEM')
        include_values = county_config.get('includeValues', [])
        if not include_values:
            include_values = ['NonVDOT secondary', 'NONVDOT', 'Non-VDOT']

        if col not in col_idx:
            logger.warning(f"  Column '{col}' not found for county roads filter")
            return rows

        idx = col_idx[col]
        include_upper = {v.upper() for v in include_values}
        return [r for r in rows if r[idx].strip().upper() in include_upper]

    elif method == 'agency_id':
        col = county_config.get('column', '_co_agency_id')
        if col not in col_idx:
            logger.warning(f"  Column '{col}' not found for agency-based county roads filter")
            return rows

        idx = col_idx[col]
        # For agency_id method, we need jurisdiction to look up the agency map
        # Since we process per-jurisdiction, we include all rows where the agency matches
        agency_map = county_config.get('agencyMap', {})
        all_agency_ids = set()
        for ids in agency_map.values():
            all_agency_ids.update(ids)

        if all_agency_ids:
            return [r for r in rows if r[idx].strip() in all_agency_ids]
        else:
            return rows

    elif method == 'ownership':
        col = county_config.get('column', 'Ownership')
        include_values = county_config.get('includeValues', ['2. County Hwy Agency'])
        if col not in col_idx:
            logger.warning(f"  Column '{col}' not found for ownership-based county roads filter")
            return rows
        idx = col_idx[col]
        include_upper = {v.upper() for v in include_values}
        return [r for r in rows if r[idx].strip().upper() in include_upper]

    return rows


def filter_no_interstate(rows, headers, split_config):
    """Filter out interstate roads."""
    interstate_config = split_config.get('interstateExclusion', {})
    method = interstate_config.get('method', 'system_column')

    col_idx = {h: i for i, h in enumerate(headers)}

    if method == 'column_value':
        col = interstate_config.get('column', '_co_system_code')
        exclude_values = interstate_config.get('excludeValues', [])
        if col not in col_idx:
            logger.warning(f"  Column '{col}' not found for interstate exclusion")
            return rows
        idx = col_idx[col]
        exclude_upper = {v.upper() for v in exclude_values}
        return [r for r in rows if r[idx].strip().upper() not in exclude_upper]

    elif method == 'system_column':
        col = interstate_config.get('column', 'SYSTEM')
        exclude_values = interstate_config.get('excludeValues', ['Interstate'])
        if col not in col_idx:
            logger.warning(f"  Column '{col}' not found for interstate exclusion")
            return rows
        idx = col_idx[col]
        exclude_upper = {v.upper() for v in exclude_values}
        return [r for r in rows if r[idx].strip().upper() not in exclude_upper]

    elif method == 'functional_class':
        col = interstate_config.get('column', 'Functional Class')
        exclude_values = interstate_config.get('excludeValues', ['1-Interstate (A,1)'])
        if col not in col_idx:
            logger.warning(f"  Column '{col}' not found for functional class interstate exclusion")
            return rows
        idx = col_idx[col]
        exclude_upper = {v.upper() for v in exclude_values}
        # Include rows where value is NOT in exclude list (including blank/empty values)
        return [r for r in rows if r[idx].strip().upper() not in exclude_upper]

    return rows


def split_jurisdiction(jurisdiction, data_dir, split_config):
    """Split a single jurisdiction's all_roads.csv into 3 road-type CSVs."""
    data_dir = Path(data_dir)
    input_path = data_dir / f"{jurisdiction}_all_roads.csv"

    if not input_path.exists():
        logger.warning(f"  {jurisdiction}: all_roads.csv not found at {input_path}")
        return False

    # Read all rows
    with open(input_path, 'r', newline='', encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f)
        headers = next(reader)
        all_rows = list(reader)

    total = len(all_rows)

    # county_roads
    county_rows = filter_county_roads(all_rows, headers, split_config)
    county_path = data_dir / f"{jurisdiction}_county_roads.csv"
    with open(county_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(county_rows)

    # no_interstate
    no_interstate_rows = filter_no_interstate(all_rows, headers, split_config)
    no_interstate_path = data_dir / f"{jurisdiction}_no_interstate.csv"
    with open(no_interstate_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(no_interstate_rows)

    logger.info(f"  {jurisdiction}: all={total:,}, county_roads={len(county_rows):,}, no_interstate={len(no_interstate_rows):,}")
    return True


def main():
    parser = argparse.ArgumentParser(description='Split jurisdiction CSVs into road-type variants')
    parser.add_argument('--state', required=True, help='State key (e.g., virginia, colorado)')
    parser.add_argument('--jurisdiction', help='Single jurisdiction to split')
    parser.add_argument('--jurisdictions', nargs='+', help='Multiple jurisdictions to split')
    parser.add_argument('--data-dir', required=True, help='Directory containing jurisdiction CSVs')
    parser.add_argument('--auto', action='store_true',
                        help='Auto-detect jurisdictions from *_all_roads.csv files')
    args = parser.parse_args()

    state_config = load_state_config(args.state)
    split_config = get_split_config(state_config)

    if not split_config:
        logger.warning(f"No splitConfig found in states/{args.state}/config.json — using defaults")
        split_config = {
            'countyRoads': {
                'method': 'system_column',
                'column': 'SYSTEM',
                'includeValues': ['NonVDOT secondary', 'NONVDOT', 'Non-VDOT']
            },
            'interstateExclusion': {
                'method': 'system_column',
                'column': 'SYSTEM',
                'excludeValues': ['Interstate']
            }
        }

    logger.info(f"[{args.state}] Road-type split")
    logger.info(f"[{args.state}] Data dir: {args.data_dir}")

    # Determine jurisdictions to process
    jurisdictions = []
    if args.jurisdiction:
        jurisdictions = [args.jurisdiction]
    elif args.jurisdictions:
        jurisdictions = args.jurisdictions
    elif args.auto:
        data_dir = Path(args.data_dir)
        for f in sorted(data_dir.glob('*_all_roads.csv')):
            j = f.stem.replace('_all_roads', '')
            jurisdictions.append(j)
        logger.info(f"  Auto-detected {len(jurisdictions)} jurisdictions")
    else:
        logger.error("Specify --jurisdiction, --jurisdictions, or --auto")
        return 1

    success = 0
    failed = 0
    for j in jurisdictions:
        if split_jurisdiction(j, args.data_dir, split_config):
            success += 1
        else:
            failed += 1

    logger.info("=" * 60)
    logger.info(f"[{args.state}] ROAD-TYPE SPLIT COMPLETE")
    logger.info(f"[{args.state}]   Success: {success}/{len(jurisdictions)}")
    if failed:
        logger.info(f"[{args.state}]   Failed:  {failed}")
    logger.info("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
