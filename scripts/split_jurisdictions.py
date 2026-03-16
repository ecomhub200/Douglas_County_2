#!/usr/bin/env python3
"""
Split statewide crash data into per-jurisdiction CSVs with 3 road-type variants.

This script takes a full statewide CSV (downloaded once from the data source)
and splits it into all jurisdictions automatically, producing:
  - {jurisdiction}_county_roads.csv
  - {jurisdiction}_no_interstate.csv
  - {jurisdiction}_all_roads.csv

Works for both Virginia and Colorado by reading state-specific configuration.

Usage:
    # Virginia: Split statewide data into all 133 jurisdictions
    python scripts/split_jurisdictions.py --state virginia --input data/virginia_statewide.csv --output-dir data

    # Colorado: Split statewide data into all 64 counties
    python scripts/split_jurisdictions.py --state colorado --input data/CDOT/colorado_statewide_raw.csv --output-dir data/CDOT

    # Specific jurisdictions only
    python scripts/split_jurisdictions.py --state virginia --input data/va_statewide.csv --jurisdictions henrico chesterfield fairfax_county

    # List all jurisdictions for a state
    python scripts/split_jurisdictions.py --state virginia --list

    # Dry run (report sizes, don't write files)
    python scripts/split_jurisdictions.py --state virginia --input data/va_statewide.csv --dry-run
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd

logger = logging.getLogger('split_jurisdictions')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent


def load_config(state):
    """Load main config.json and state-specific config."""
    config_path = PROJECT_ROOT / 'config.json'
    state_config_path = PROJECT_ROOT / 'states' / state / 'config.json'

    with open(config_path) as f:
        config = json.load(f)

    state_config = None
    if state_config_path.exists():
        with open(state_config_path) as f:
            state_config = json.load(f)

    return config, state_config


def get_jurisdictions(config, state):
    """Get all jurisdiction configs for a given state."""
    jurisdictions = config.get('jurisdictions', {})
    state_abbr = {
        'virginia': 'VA', 'colorado': 'CO'
    }.get(state, state.upper()[:2])

    result = {}
    for jid, jconfig in jurisdictions.items():
        if jid.startswith('_'):
            continue  # Skip separators

        # Check explicit state field first (e.g., "state": "CO")
        j_state = jconfig.get('state', '')
        if j_state:
            if j_state.upper() == state_abbr:
                result[jid] = jconfig
            continue

        # Fallback: Virginia jurisdictions have no prefix; Colorado uses "co_"
        if state == 'virginia' and not jid.startswith('co_'):
            result[jid] = jconfig
        elif state == 'colorado' and jid.startswith('co_'):
            result[jid] = jconfig

    return result


def get_colorado_jurisdictions_from_manifest():
    """Load Colorado jurisdictions from CDOT source manifest."""
    manifest_path = PROJECT_ROOT / 'data' / 'CDOT' / 'source_manifest.json'
    if not manifest_path.exists():
        return {}
    with open(manifest_path) as f:
        manifest = json.load(f)
    filters = manifest.get('jurisdiction_filters', {})
    # Remove metadata keys (e.g., _description)
    return {k: v for k, v in filters.items() if not k.startswith('_') and isinstance(v, dict)}


def get_filter_profiles(config):
    """Get road-type filter profiles from config."""
    return config.get('filterProfiles', {
        'countyOnly': {
            'name': 'County Roads Only',
            'systemValues': ['NonVDOT secondary', 'NONVDOT', 'Non-VDOT']
        },
        'countyPlusVDOT': {
            'name': 'All Roads (No Interstate)',
            'systemValues': ['NonVDOT secondary', 'NONVDOT', 'Non-VDOT', 'Primary', 'Secondary'],
            'excludeRoutePatterns': ['^I-\\d', '^IS \\d', '^Interstate']
        },
        'allRoads': {
            'name': 'All Roads',
            'systemValues': []  # Empty = no filter
        }
    })


def filter_jurisdiction_virginia(df, jconfig):
    """Filter Virginia dataframe by jurisdiction config."""
    juris_code = jconfig.get('jurisCode', '')
    name_patterns = jconfig.get('namePatterns', [])
    fips = jconfig.get('fips', '')

    mask = pd.Series([False] * len(df), index=df.index)

    # Try Juris Code columns (includes standardized column names from download_crash_data.py)
    if juris_code:
        for col in ['Juris Code', 'Juris_Code', 'JURIS_CODE', 'juris_code',
                     'Jurisdiction Code', 'JURISDICTION_CODE', 'JURISCODE']:
            if col in df.columns:
                code_str = str(juris_code)
                mask |= df[col].astype(str).str.strip() == code_str
                # Also try numeric comparison (e.g., "43" vs "43.0")
                if code_str.isdigit():
                    mask |= df[col].astype(str).str.strip() == str(int(code_str))
                break
        else:
            # Fuzzy fallback: search any column containing 'juris' and 'code'
            for col in df.columns:
                if 'juris' in col.lower() and 'code' in col.lower():
                    code_str = str(juris_code)
                    mask |= df[col].astype(str).str.strip() == code_str
                    break

    # Try FIPS columns
    if fips:
        for col in ['FIPS', 'fips', 'County_FIPS', 'COUNTY_FIPS']:
            if col in df.columns:
                mask |= df[col].astype(str).str.strip() == str(fips)
                break

    # Try name patterns (includes standardized column names from download_crash_data.py)
    if name_patterns:
        for col in ['Physical Juris Name', 'Physical_Juris_Name', 'PHYSICAL_JURIS_NAME',
                     'Physical_Jurisdiction', 'PHYSICAL_JURISDICTION',
                     'JURISDICTION', 'Jurisdiction', 'jurisdiction',
                     'Jurisdiction_Name', 'JURISDICTION_NAME',
                     'County_City', 'COUNTY_CITY', 'county_name']:
            if col in df.columns:
                for pattern in name_patterns:
                    try:
                        mask |= df[col].astype(str).str.contains(
                            pattern, case=False, na=False, regex=True
                        )
                    except re.error:
                        mask |= df[col].astype(str).str.lower() == pattern.lower()
                break
        else:
            # Fuzzy fallback: search any column containing 'juris' and 'name'
            for col in df.columns:
                if 'juris' in col.lower() and 'name' in col.lower():
                    for pattern in name_patterns:
                        try:
                            mask |= df[col].astype(str).str.contains(
                                pattern, case=False, na=False, regex=True
                            )
                        except re.error:
                            mask |= df[col].astype(str).str.lower() == pattern.lower()
                    break

    return df[mask].copy()


def filter_jurisdiction_colorado(df, jkey, jconfig):
    """Filter Colorado dataframe by county name."""
    county_name = jconfig.get('county', jkey.upper())

    # Find county column
    county_col = None
    for col in df.columns:
        if col.strip().lower() == 'county':
            county_col = col
            break

    if not county_col:
        logger.warning(f"  No 'County' column found for Colorado filtering")
        return pd.DataFrame()

    mask = df[county_col].astype(str).str.strip().str.upper() == county_name.upper()
    return df[mask].copy()


def filter_by_road_system(df, filter_profile):
    """Apply road-type filter to dataframe."""
    system_values = filter_profile.get('systemValues', [])
    exclude_patterns = filter_profile.get('excludeRoutePatterns', [])

    if not system_values:
        # allRoads: no filter applied
        result = df.copy()
    else:
        # Find SYSTEM column
        system_col = None
        for col in ['SYSTEM', 'System', 'system', 'Rd System', 'RD_SYSTEM']:
            if col in df.columns:
                system_col = col
                break

        if not system_col:
            logger.warning("  No SYSTEM column found — returning all rows")
            return df.copy()

        mask = df[system_col].astype(str).str.upper().apply(
            lambda x: any(sv.upper() in x for sv in system_values)
        )
        result = df[mask].copy()

    # Apply exclude patterns (e.g., remove interstates from countyPlusVDOT)
    if exclude_patterns and len(result) > 0:
        route_col = None
        for col in ['RTE_NM', 'Rte_Nm', 'RTE_NAME', 'Route Name', 'ROUTE_NAME']:
            if col in result.columns:
                route_col = col
                break
        if route_col:
            for pattern in exclude_patterns:
                exclude_mask = result[route_col].astype(str).str.contains(
                    pattern, case=False, na=False, regex=True
                )
                result = result[~exclude_mask]

    return result


def standardize_columns_virginia(df):
    """Minimal column standardization for Virginia data (same as download_crash_data.py)."""
    # Import the standardize function from the download script if available
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from download_crash_data import standardize_columns
        return standardize_columns(df)
    except Exception as e:
        logger.warning(f"Could not import standardize_columns ({e}) — using built-in normalization")
        # Built-in fallback: rename raw ArcGIS field names and decode coded values
        # so that splitConfig column names (Ownership, Functional Class) match.
        header_aliases = {
            'OWNERSHIP': 'Ownership',
            'FUN': 'Functional Class',
            'FAC': 'Facility Type',
            'AREA_TYPE': 'Area Type',
            'PHYSICAL_JURIS': 'Physical Juris Name',
            'JURIS_CODE': 'Juris Code',
            'DOCUMENT_NBR': 'Document Nbr',
            'CRASH_YEAR': 'Crash Year',
            'CRASH_DT': 'Crash Date',
            'CRASH_SEVERITY': 'Crash Severity',
            'CRASH_MILITARY_TM': 'Crash Military Time',
            'COLLISION_TYPE': 'Collision Type',
            'WEATHER_CONDITION': 'Weather Condition',
            'LIGHT_CONDITION': 'Light Condition',
            'RTE_NM': 'RTE Name',
        }
        rename_dict = {k: v for k, v in header_aliases.items() if k in df.columns}
        if rename_dict:
            df = df.rename(columns=rename_dict)
            logger.info(f"  Renamed {len(rename_dict)} raw ArcGIS columns")

        # Decode Ownership codes
        if 'Ownership' in df.columns:
            ownership_map = {
                '1': '1. State Hwy Agency',
                '2': '2. County Hwy Agency',
                '3': '3. City or Town Hwy Agency',
                '4': '4. Federal Roads',
                '5': '5. Toll Roads Maintained by Others',
                '6': '6. Private/Unknown Roads',
            }
            raw = df['Ownership'].astype(str).str.strip()
            if raw.isin(ownership_map.keys()).any() and not raw.str.contains('Hwy Agency', na=False).any():
                df['Ownership'] = raw.map(ownership_map).fillna(df['Ownership'])

        # Decode SYSTEM codes
        if 'SYSTEM' in df.columns:
            system_map = {
                '1': 'VDOT Interstate', '2': 'VDOT Primary', '3': 'VDOT Secondary',
                '4': 'NonVDOT primary', '5': 'NonVDOT secondary', '6': 'Non-VDOT',
            }
            raw = df['SYSTEM'].astype(str).str.strip()
            if raw.isin(system_map.keys()).any() and not raw.str.contains('VDOT', na=False).any():
                df['SYSTEM'] = raw.map(system_map).fillna(df['SYSTEM'])

        # Decode Functional Class codes
        if 'Functional Class' in df.columns:
            func_map = {
                'INT': '1-Interstate (A,1)',
                'OFE': '2-Principal Arterial - Other Freeways and Expressways (B)',
                'OPA': '3-Principal Arterial - Other (E,2)',
                'MIA': '4-Minor Arterial (H,3)',
                'MAC': '5-Major Collector (I,4)',
                'MIC': '6-Minor Collector (5)',
                'LOC': '7-Local (J,6)',
            }
            raw = df['Functional Class'].astype(str).str.strip()
            if raw.isin(func_map.keys()).any() and not raw.str.contains('Interstate', na=False).any():
                df['Functional Class'] = raw.map(func_map).fillna(df['Functional Class'])

        return df


def _resolve_column_pd(df, config_section, default_col):
    """Find the actual column name in a DataFrame, checking primary name then aliases."""
    col = config_section.get('column', default_col)
    if col in df.columns:
        return col
    for alias in config_section.get('columnAliases', []):
        if alias in df.columns:
            return alias
    return None


def _apply_split_config_filter(df, suffix, split_config):
    """Apply splitConfig-based filtering (ownership, functional_class, etc.) to a DataFrame."""
    if suffix == 'county_roads':
        county_config = split_config.get('countyRoads', {})
        method = county_config.get('method', 'system_column')
        col = _resolve_column_pd(df, county_config, 'SYSTEM')
        if col is None:
            logger.warning(f"  Column not found for county roads filter (method={method}) — returning empty")
            return df.iloc[0:0].copy()
        if method in ('ownership', 'system_column', 'column_value'):
            include_values = county_config.get('includeValues', [])
            include_upper = {v.upper() for v in include_values}
            mask = df[col].astype(str).str.strip().str.upper().isin(include_upper)
            return df[mask].copy()
        elif method == 'agency_id':
            agency_map = county_config.get('agencyMap', {})
            all_ids = set()
            for ids in agency_map.values():
                all_ids.update(ids)
            mask = df[col].astype(str).str.strip().isin(all_ids)
            return df[mask].copy()

    elif suffix == 'city_roads':
        city_config = split_config.get('cityRoads', {})
        if not city_config:
            return df.iloc[0:0].copy()  # Empty DataFrame — no cityRoads config
        method = city_config.get('method', 'ownership')
        col = _resolve_column_pd(df, city_config, 'Ownership')
        if col is None:
            logger.warning(f"  Column not found for city roads filter (method={method}) — returning empty")
            return df.iloc[0:0].copy()
        if method in ('ownership', 'system_column', 'column_value'):
            include_values = city_config.get('includeValues', [])
            include_upper = {v.upper() for v in include_values}
            mask = df[col].astype(str).str.strip().str.upper().isin(include_upper)
            return df[mask].copy()
        elif method == 'agency_id':
            agency_map = city_config.get('agencyMap', {})
            all_ids = set()
            for ids in agency_map.values():
                all_ids.update(ids)
            mask = df[col].astype(str).str.strip().isin(all_ids)
            return df[mask].copy()

    elif suffix == 'no_interstate':
        interstate_config = split_config.get('interstateExclusion', {})
        method = interstate_config.get('method', 'system_column')
        col = _resolve_column_pd(df, interstate_config, 'SYSTEM')
        if col is None:
            logger.warning(f"  Column not found for interstate exclusion (method={method}) — returning empty")
            return df.iloc[0:0].copy()
        exclude_values = interstate_config.get('excludeValues', [])
        exclude_upper = {v.upper() for v in exclude_values}
        # Include rows where value is NOT in exclude list (including blank/empty)
        mask = ~df[col].astype(str).str.strip().str.upper().isin(exclude_upper)
        return df[mask].copy()

    return df.copy()


def split_state(df, state, config, jurisdictions, output_dir, dry_run=False,
                skip_validation=False, skip_geocode=False, state_config=None):
    """Split statewide dataframe into per-jurisdiction CSVs with road-type variants."""
    filter_profiles = get_filter_profiles(config)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check if state config has splitConfig (preferred over filterProfiles)
    split_config = None
    if state_config:
        split_config = state_config.get('roadSystems', {}).get('splitConfig', None)

    # Road-type filter mappings (city_roads included when splitConfig.cityRoads exists)
    road_type_map = {
        'county_roads': 'countyOnly',
        'city_roads': 'cityOnly',
        'no_interstate': 'countyPlusVDOT',
        'all_roads': 'allRoads'
    }

    results = {
        'total_jurisdictions': len(jurisdictions),
        'successful': 0,
        'skipped': 0,
        'failed': 0,
        'empty': 0,
        'details': {}
    }

    total = len(jurisdictions)
    start_time = time.time()

    for idx, (jid, jconfig) in enumerate(jurisdictions.items(), 1):
        jname = jconfig.get('name', jid)
        logger.info(f"[{idx}/{total}] Processing: {jname} ({jid})")

        # Filter to this jurisdiction
        if state == 'virginia':
            jdf = filter_jurisdiction_virginia(df, jconfig)
        elif state == 'colorado':
            jdf = filter_jurisdiction_colorado(df, jid, jconfig)
        else:
            logger.warning(f"  Unknown state: {state}")
            results['failed'] += 1
            continue

        if jdf.empty:
            logger.warning(f"  EMPTY: No records found for {jname}")
            results['empty'] += 1
            results['details'][jid] = {'status': 'empty', 'records': 0}
            continue

        logger.info(f"  Found {len(jdf):,} records")

        # Standardize columns BEFORE road-type filtering so that splitConfig
        # column names (e.g. "Ownership", "Functional Class") match the DataFrame.
        if state == 'virginia':
            jdf = standardize_columns_virginia(jdf)

        # For Colorado, strip the co_ prefix for file naming
        file_jid = jid.replace('co_', '') if state == 'colorado' else jid

        # Apply each road-type filter and save
        detail = {'status': 'success', 'records': len(jdf), 'files': {}}

        for suffix, profile_key in road_type_map.items():
            # city_roads requires explicit splitConfig.cityRoads — skip when not configured
            if suffix == 'city_roads' and (not split_config or 'cityRoads' not in split_config):
                logger.info(f"    city_roads: skipped (no cityRoads in splitConfig)")
                continue

            if suffix == 'all_roads':
                # all_roads = full unfiltered jurisdiction data
                filtered = jdf.copy()
            elif split_config:
                # Use state config splitConfig (ownership, functional_class, etc.)
                filtered = _apply_split_config_filter(jdf, suffix, split_config)
            else:
                profile = filter_profiles.get(profile_key, {})
                filtered = filter_by_road_system(jdf, profile)

            output_path = output_dir / f"{file_jid}_{suffix}.csv"
            detail['files'][suffix] = len(filtered)

            if dry_run:
                logger.info(f"    {suffix}: {len(filtered):,} records (dry-run, not saved)")
            else:
                filtered.to_csv(output_path, index=False)
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                logger.info(f"    {suffix}: {len(filtered):,} records → {output_path.name} ({size_mb:.1f} MB)")

        results['successful'] += 1
        results['details'][jid] = detail

    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info(f"SPLIT COMPLETE in {elapsed:.1f}s")
    logger.info(f"  Successful: {results['successful']}/{total}")
    logger.info(f"  Empty:      {results['empty']}/{total}")
    logger.info(f"  Failed:     {results['failed']}/{total}")
    logger.info("=" * 60)

    return results


def build_r2_upload_manifest(state, output_dir, jurisdictions, r2_prefix=None):
    """Generate the files_json array for R2 upload of all jurisdiction CSVs."""
    r2_prefix = r2_prefix or state
    output_dir = Path(output_dir)
    files = []

    for jid, jconfig in jurisdictions.items():
        file_jid = jid.replace('co_', '') if state == 'colorado' else jid

        for suffix in ['county_roads', 'city_roads', 'no_interstate', 'all_roads']:
            local_path = output_dir / f"{file_jid}_{suffix}.csv"
            if local_path.exists():
                files.append({
                    'local_path': str(local_path),
                    'r2_key': f"{r2_prefix}/{file_jid}/{suffix}.csv"
                })

    return files


def parse_args():
    parser = argparse.ArgumentParser(
        description='Split statewide crash data into per-jurisdiction CSVs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--state', '-s', required=True,
                        choices=['virginia', 'colorado', 'maryland', 'delaware'],
                        help='State to process')
    parser.add_argument('--input', '-i', type=str,
                        help='Input statewide CSV file')
    parser.add_argument('--output-dir', '-o', type=str,
                        help='Output directory for per-jurisdiction CSVs')
    parser.add_argument('--jurisdictions', '-j', nargs='+',
                        help='Specific jurisdictions to process (default: all)')
    parser.add_argument('--list', '-l', action='store_true',
                        help='List all jurisdictions and exit')
    parser.add_argument('--dry-run', action='store_true',
                        help='Report sizes without writing files')
    parser.add_argument('--r2-manifest', action='store_true',
                        help='Output R2 upload manifest JSON to stdout')
    parser.add_argument('--r2-prefix', type=str,
                        help='R2 key prefix (default: state name)')
    parser.add_argument('--batch-size', type=int, default=0,
                        help='Process in batches of N jurisdictions (0=all at once)')
    return parser.parse_args()


def main():
    args = parse_args()

    # Load config
    config, state_config = load_config(args.state)

    # Get jurisdictions
    if args.state == 'colorado':
        jurisdictions = get_colorado_jurisdictions_from_manifest()
        if not jurisdictions:
            jurisdictions = get_jurisdictions(config, 'colorado')
        default_output = str(PROJECT_ROOT / 'data' / 'CDOT')
    else:
        jurisdictions = get_jurisdictions(config, args.state)
        default_output = str(PROJECT_ROOT / 'data')

    if not jurisdictions:
        logger.error(f"No jurisdictions found for state: {args.state}")
        return 1

    # Filter to specific jurisdictions if requested
    if args.jurisdictions:
        filtered = {}
        for j in args.jurisdictions:
            if j in jurisdictions:
                filtered[j] = jurisdictions[j]
            else:
                logger.warning(f"Unknown jurisdiction: {j}")
        jurisdictions = filtered

    # List mode
    if args.list:
        print(f"\n{args.state.upper()} Jurisdictions ({len(jurisdictions)} total):")
        print("=" * 60)
        for jid, jconfig in sorted(jurisdictions.items()):
            if isinstance(jconfig, dict):
                name = jconfig.get('name', jconfig.get('display_name', jid))
                fips = jconfig.get('fips', 'N/A')
            else:
                name = str(jconfig)
                fips = 'N/A'
            print(f"  {jid:<25s} {name:<35s} FIPS: {fips}")
        return 0

    # R2 manifest mode
    if args.r2_manifest:
        output_dir = args.output_dir or default_output
        files = build_r2_upload_manifest(
            args.state, output_dir, jurisdictions, args.r2_prefix
        )
        print(json.dumps(files, indent=2))
        return 0

    # Split mode requires input
    if not args.input:
        logger.error("--input is required for split operation")
        return 1

    if not os.path.exists(args.input):
        logger.error(f"Input file not found: {args.input}")
        return 1

    output_dir = args.output_dir or default_output

    # Load the statewide data
    logger.info(f"Loading statewide data from: {args.input}")
    load_start = time.time()
    df = pd.read_csv(args.input, dtype=str, low_memory=False)
    load_elapsed = time.time() - load_start
    logger.info(f"Loaded {len(df):,} records in {load_elapsed:.1f}s")

    # Split
    results = split_state(
        df, args.state, config, jurisdictions,
        output_dir, dry_run=args.dry_run, state_config=state_config
    )

    # Write results report
    report_path = Path(output_dir) / '.split_report.json'
    if not args.dry_run:
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Report saved to: {report_path}")

    return 0 if results['failed'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
