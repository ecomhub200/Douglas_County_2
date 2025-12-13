#!/usr/bin/env python3
"""
Download crash data from Virginia Roads ArcGIS API.
Filters for a specified Virginia jurisdiction and applies road type filters.

Usage:
    python download_crash_data.py                      # Uses default jurisdiction from config
    python download_crash_data.py --jurisdiction henrico
    python download_crash_data.py --jurisdiction chesterfield --filter countyPlusVDOT
    python download_crash_data.py --list               # List available jurisdictions
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

import pandas as pd
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Config file path
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

# Output configuration
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "data")

# Pagination settings
RECORDS_PER_REQUEST = 2000


def load_config():
    """Load configuration from config.json."""
    if not os.path.exists(CONFIG_FILE):
        logger.error(f"Config file not found: {CONFIG_FILE}")
        logger.info("Please ensure config.json exists in the same directory as this script.")
        sys.exit(1)

    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)

    logger.info(f"Loaded config with {len(config.get('jurisdictions', {}))} jurisdictions")
    return config


def get_jurisdiction_config(config, jurisdiction_id):
    """Get configuration for a specific jurisdiction."""
    jurisdictions = config.get('jurisdictions', {})

    if jurisdiction_id not in jurisdictions:
        logger.error(f"Unknown jurisdiction: {jurisdiction_id}")
        logger.info(f"Available jurisdictions: {', '.join(sorted(jurisdictions.keys()))}")
        sys.exit(1)

    return jurisdictions[jurisdiction_id]


def list_jurisdictions(config):
    """List all available jurisdictions."""
    jurisdictions = config.get('jurisdictions', {})

    counties = []
    cities = []

    for jid, jdata in jurisdictions.items():
        item = (jid, jdata.get('name', jid), jdata.get('jurisCode', '?'))
        if jdata.get('type') == 'city':
            cities.append(item)
        else:
            counties.append(item)

    counties.sort(key=lambda x: x[1])
    cities.sort(key=lambda x: x[1])

    print("\n" + "=" * 60)
    print("AVAILABLE VIRGINIA JURISDICTIONS")
    print("=" * 60)

    print(f"\nCOUNTIES ({len(counties)}):")
    print("-" * 40)
    for jid, name, code in counties:
        print(f"  {jid:<25} {name:<30} (Code: {code})")

    print(f"\nINDEPENDENT CITIES ({len(cities)}):")
    print("-" * 40)
    for jid, name, code in cities:
        print(f"  {jid:<25} {name:<30} (Code: {code})")

    print(f"\nTotal: {len(jurisdictions)} jurisdictions")
    print("=" * 60)


def get_arcgis_record_count(api_url, where_clause):
    """Get total record count from ArcGIS API."""
    params = {
        'where': where_clause,
        'returnCountOnly': 'true',
        'f': 'json'
    }

    response = requests.get(api_url, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()

    if 'error' in data:
        raise Exception(f"ArcGIS API error: {data['error']}")

    return data.get('count', 0)


def download_arcgis_page(api_url, where_clause, offset):
    """Download a page of records from ArcGIS API."""
    params = {
        'where': where_clause,
        'outFields': '*',
        'returnGeometry': 'true',
        'outSR': '4326',
        'resultOffset': offset,
        'resultRecordCount': RECORDS_PER_REQUEST,
        'f': 'json'
    }

    response = requests.get(api_url, params=params, timeout=120)
    response.raise_for_status()
    data = response.json()

    if 'error' in data:
        raise Exception(f"ArcGIS API error: {data['error']}")

    features = data.get('features', [])
    records = []
    for feature in features:
        record = feature.get('attributes', {})
        # Extract geometry coordinates
        if 'geometry' in feature and feature['geometry']:
            record['x'] = feature['geometry'].get('x')
            record['y'] = feature['geometry'].get('y')
        records.append(record)
    return records


def download_from_arcgis(config, jurisdiction_config):
    """
    Download crash data from ArcGIS REST API with pagination.
    Filters for the specified jurisdiction.
    """
    api_url = config.get('dataSource', {}).get('apiUrl',
        "https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/CrashData_test/FeatureServer/0/query")

    juris_code = jurisdiction_config.get('jurisCode', '')
    name_patterns = jurisdiction_config.get('namePatterns', [])
    fips = jurisdiction_config.get('fips', '')
    name = jurisdiction_config.get('name', 'Unknown')

    logger.info(f"Attempting download from ArcGIS REST API for {name}...")

    # Build WHERE clauses for this jurisdiction
    where_clauses = []

    if juris_code:
        where_clauses.append(f"Juris_Code = '{juris_code}' OR Juris_Code = {juris_code}")

    if name_patterns:
        for pattern in name_patterns:
            where_clauses.append(f"Physical_Juris_Name LIKE '%{pattern}%'")

    if fips:
        where_clauses.append(f"COUNTYFP = '{fips}' OR FIPS = '{fips}'")

    if not where_clauses:
        logger.error("No filter criteria available for this jurisdiction")
        sys.exit(1)

    # Try each where clause until one works
    all_records = []
    successful_clause = None
    count = 0

    for where_clause in where_clauses:
        try:
            count = get_arcgis_record_count(api_url, where_clause)
            if count > 0:
                logger.info(f"Found {count} records with filter: {where_clause}")
                successful_clause = where_clause
                break
        except Exception as e:
            logger.debug(f"Filter '{where_clause}' failed: {e}")
            continue

    if not successful_clause:
        # Fallback: get all records and filter locally
        logger.info("Specific filters failed, downloading all records for local filtering...")
        successful_clause = "1=1"
        count = get_arcgis_record_count(api_url, successful_clause)
        logger.info(f"Total records in dataset: {count}")

    # Download with pagination
    offset = 0
    while offset < count:
        logger.info(f"Downloading records {offset} to {min(offset + RECORDS_PER_REQUEST, count)}...")
        records = download_arcgis_page(api_url, successful_clause, offset)

        if not records:
            break

        all_records.extend(records)
        offset += RECORDS_PER_REQUEST

    logger.info(f"Downloaded {len(all_records)} total records from ArcGIS API")

    if not all_records:
        raise Exception("No records returned from ArcGIS API")

    return pd.DataFrame(all_records)


def download_from_fallback(config):
    """Download crash data from fallback CSV URL."""
    fallback_url = config.get('dataSource', {}).get('fallbackUrl',
        "https://www.virginiaroads.org/api/download/v1/items/101101cecac34f28b38c0846e847bd0b/csv?layers=1")

    logger.info("Attempting download from fallback CSV URL...")

    response = requests.get(fallback_url, timeout=300)
    response.raise_for_status()

    # Save temporarily and read as CSV
    import io
    df = pd.read_csv(io.StringIO(response.text))

    logger.info(f"Downloaded {len(df)} records from fallback URL")
    return df


def filter_jurisdiction(df, jurisdiction_config):
    """Filter dataframe to only include records for the specified jurisdiction."""
    original_count = len(df)

    juris_code = jurisdiction_config.get('jurisCode', '')
    name_patterns = jurisdiction_config.get('namePatterns', [])
    fips = jurisdiction_config.get('fips', '')
    name = jurisdiction_config.get('name', 'Unknown')

    # Try multiple filter approaches
    mask = pd.Series([False] * len(df))

    # Check various possible column names for jurisdiction code
    if juris_code:
        juris_columns = ['Juris_Code', 'JURIS_CODE', 'juris_code', 'Juris Code']
        for col in juris_columns:
            if col in df.columns:
                mask |= df[col].astype(str).str.strip() == str(juris_code)
                break

    # Check Physical Juris Name
    if name_patterns:
        name_columns = ['Physical_Juris_Name', 'PHYSICAL_JURIS_NAME', 'Physical Juris Name', 'PHYSICAL_JURIS']
        for col in name_columns:
            if col in df.columns:
                for pattern in name_patterns:
                    mask |= df[col].astype(str).str.upper().str.contains(pattern.upper(), na=False)
                break

    # Check FIPS code
    if fips:
        fips_columns = ['COUNTYFP', 'FIPS', 'County_FIPS', 'countyfp']
        for col in fips_columns:
            if col in df.columns:
                mask |= df[col].astype(str).str.strip() == fips
                break

    df_filtered = df[mask].copy().reset_index(drop=True)

    logger.info(f"Filtered from {original_count} to {len(df_filtered)} {name} records")

    return df_filtered


def filter_by_road_system(df, filter_profile):
    """
    Filter dataframe based on road system type (NonVDOT, Primary, Secondary, etc.).
    """
    original_count = len(df)

    system_values = filter_profile.get('systemValues', ['NonVDOT secondary', 'NONVDOT'])
    exclude_patterns = filter_profile.get('excludeRoutePatterns', [])
    filter_name = filter_profile.get('name', 'Unknown Filter')

    # Find the SYSTEM column
    system_columns = ['SYSTEM', 'System', 'system']
    system_col = None
    for col in system_columns:
        if col in df.columns:
            system_col = col
            break

    if system_col is None:
        logger.warning("Could not find SYSTEM column, skipping road system filter")
        return df

    # Filter by system values
    mask = df[system_col].astype(str).str.upper().apply(
        lambda x: any(sys_val.upper() in x for sys_val in system_values)
    )

    df_filtered = df[mask].copy().reset_index(drop=True)

    # Apply route exclusion patterns if specified
    if exclude_patterns and len(df_filtered) > 0:
        route_columns = ['RTE_NM', 'RTE_NAME', 'RTE NAME', 'Rte_Name', 'Route_Name', 'ROUTE_NAME', 'RTE_Name', 'RTE Name']
        route_col = None
        for col in route_columns:
            if col in df_filtered.columns:
                route_col = col
                break

        if route_col:
            route_values = df_filtered[route_col].astype(str)
            exclude_mask = route_values.apply(
                lambda x: any(pd.Series([x]).str.contains(pattern, case=False, na=False, regex=True).iloc[0]
                             for pattern in exclude_patterns)
            )

            df_filtered = df_filtered[~exclude_mask].copy().reset_index(drop=True)

    logger.info(f"Filtered from {original_count} to {len(df_filtered)} records using '{filter_name}'")

    return df_filtered


def standardize_columns(df):
    """Standardize column names to match expected format for index.html."""
    column_mapping = {
        # Core identifiers
        'OBJECTID': 'OBJECTID',
        'DOCUMENT_NBR': 'Document Nbr',
        'Document_Nbr': 'Document Nbr',

        # Crash timing
        'CRASH_YEAR': 'Crash Year',
        'Crash_Year': 'Crash Year',
        'CRASH_DT': 'Crash Date',
        'Crash_Date': 'Crash Date',
        'CRASH_MILITARY_TM': 'Crash Military Time',
        'Crash_Military_Time': 'Crash Military Time',

        # Severity
        'CRASH_SEVERITY': 'Crash Severity',
        'Crash_Severity': 'Crash Severity',
        'K_PEOPLE': 'K_People',
        'A_PEOPLE': 'A_People',
        'B_PEOPLE': 'B_People',
        'C_PEOPLE': 'C_People',

        # Injury counts
        'PERSONS_INJURED': 'Persons Injured',
        'Persons_Injured': 'Persons Injured',
        'PEDESTRIANS_KILLED': 'Pedestrians Killed',
        'Pedestrians_Killed': 'Pedestrians Killed',
        'PEDESTRIANS_INJURED': 'Pedestrians Injured',
        'Pedestrians_Injured': 'Pedestrians Injured',
        'VEH_COUNT': 'Vehicle Count',
        'Vehicle_Count': 'Vehicle Count',

        # Crash characteristics
        'COLLISION_TYPE': 'Collision Type',
        'Collision_Type': 'Collision Type',
        'WEATHER_CONDITION': 'Weather Condition',
        'Weather_Condition': 'Weather Condition',
        'LIGHT_CONDITION': 'Light Condition',
        'Light_Condition': 'Light Condition',
        'ROADWAY_SURFACE_COND': 'Roadway Surface Condition',
        'Roadway_Surface_Condition': 'Roadway Surface Condition',
        'RELATION_TO_ROADWAY': 'Relation To Roadway',
        'Relation_To_Roadway': 'Relation To Roadway',
        'ROADWAY_ALIGNMENT': 'Roadway Alignment',
        'Roadway_Alignment': 'Roadway Alignment',
        'ROADWAY_SURFACE_TYPE': 'Roadway Surface Type',
        'Roadway_Surface_Type': 'Roadway Surface Type',
        'ROADWAY_DEFECT': 'Roadway Defect',
        'Roadway_Defect': 'Roadway Defect',
        'ROADWAY_DESCRIPTION': 'Roadway Description',
        'Roadway_Description': 'Roadway Description',

        # Intersection/control
        'INTERSECTION_TYPE': 'Intersection Type',
        'Intersection_Type': 'Intersection Type',
        'TRAFFIC_CONTROL_TYPE': 'Traffic Control Type',
        'Traffic_Control_Type': 'Traffic Control Type',
        'TRFC_CTRL_STATUS_TYPE': 'Traffic Control Status',
        'Traffic_Control_Status': 'Traffic Control Status',

        # Work zone / school
        'WORK_ZONE_RELATED': 'Work Zone Related',
        'Work_Zone_Related': 'Work Zone Related',
        'WORK_ZONE_LOCATION': 'Work Zone Location',
        'Work_Zone_Location': 'Work Zone Location',
        'WORK_ZONE_TYPE': 'Work Zone Type',
        'Work_Zone_Type': 'Work Zone Type',
        'SCHOOL_ZONE': 'School Zone',
        'School_Zone': 'School Zone',

        # First harmful event
        'FIRST_HARMFUL_EVENT': 'First Harmful Event',
        'First_Harmful_Event': 'First Harmful Event',
        'FIRST_HARMFUL_EVENT_LOC': 'First Harmful Event Loc',
        'First_Harmful_Event_Loc': 'First Harmful Event Loc',

        # Jurisdiction
        'JURIS_CODE': 'Juris Code',
        'Juris_Code': 'Juris Code',
        'PHYSICAL_JURIS': 'Physical Juris Name',
        'Physical_Juris_Name': 'Physical Juris Name',

        # Road classification
        'FUN': 'Functional Class',
        'Functional_Class': 'Functional Class',
        'FAC': 'Facility Type',
        'Facility_Type': 'Facility Type',
        'AREA_TYPE': 'Area Type',
        'Area_Type': 'Area Type',
        'SYSTEM': 'SYSTEM',
        'VSP': 'VSP',
        'OWNERSHIP': 'Ownership',

        # Planning/admin
        'PLAN_DISTRICT': 'Planning District',
        'Planning_District': 'Planning District',
        'MPO_NAME': 'MPO Name',
        'MPO_Name': 'MPO Name',
        'VDOT_DISTRICT': 'VDOT District',
        'VDOT_District': 'VDOT District',

        # Route/location
        'RTE_NM': 'RTE Name',
        'RTE_NAME': 'RTE Name',
        'RTE_Name': 'RTE Name',
        'RNS_MP': 'RNS MP',
        'NODE': 'Node',
        'OFFSET': 'Node Offset (ft)',
        'Node_Offset': 'Node Offset (ft)',

        # Coordinates (keep lowercase)
        'x': 'x',
        'y': 'y',

        # Boolean flags
        'ALCOHOL_NOTALCOHOL': 'Alcohol?',
        'BIKE_NONBIKE': 'Bike?',
        'PED_NONPED': 'Pedestrian?',
        'SPEED_NOTSPEED': 'Speed?',
        'DISTRACTED_NOTDISTRACTED': 'Distracted?',
        'DROWSY_NOTDROWSY': 'Drowsy?',
        'HITRUN_NOT_HITRUN': 'Hitrun?',
        'SENIOR_NOTSENIOR': 'Senior?',
        'YOUNG_NOTYOUNG': 'Young?',
        'NIGHT': 'Night?',
        'BELTED_UNBELTED': 'Unrestrained?',
        'MOTOR_NONMOTOR': 'Motorcycle?',

        # Additional boolean flags
        'DRUG_NODRUG': 'Drug Related?',
        'GR_NOGR': 'Guardrail Related?',
        'LGTRUCK_NONLGTRUCK': 'Lgtruck?',
        'MAINLINE_YN': 'Mainline?',

        # Speed and road attributes
        'SPEED_DIFF_MAX': 'Max Speed Diff',
        'RD_TYPE': 'RoadDeparture Type',
    }

    # Rename columns that exist
    rename_dict = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df.rename(columns=rename_dict)

    return df


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Download crash data from Virginia Roads for a specific jurisdiction.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python download_crash_data.py                          # Use default jurisdiction (henrico)
  python download_crash_data.py --jurisdiction chesterfield
  python download_crash_data.py --jurisdiction fairfax_county --filter allRoads
  python download_crash_data.py --list                   # Show all available jurisdictions
        """
    )

    parser.add_argument(
        '--jurisdiction', '-j',
        type=str,
        help='Jurisdiction ID (e.g., henrico, chesterfield, alexandria)'
    )

    parser.add_argument(
        '--filter', '-f',
        type=str,
        choices=['countyOnly', 'countyPlusVDOT', 'allRoads'],
        help='Road type filter profile'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output file path (default: data/crashes.csv)'
    )

    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List all available jurisdictions and exit'
    )

    return parser.parse_args()


def main():
    """Main function to download and process crash data."""
    args = parse_args()

    # Load configuration
    config = load_config()

    # Handle --list option
    if args.list:
        list_jurisdictions(config)
        return 0

    # Get jurisdiction
    jurisdiction_id = args.jurisdiction or config.get('defaults', {}).get('jurisdiction', 'henrico')
    jurisdiction_config = get_jurisdiction_config(config, jurisdiction_id)

    # Get filter profile
    filter_id = args.filter or config.get('defaults', {}).get('filterProfile', 'countyOnly')
    filter_profiles = config.get('filterProfiles', {})
    filter_profile = filter_profiles.get(filter_id, filter_profiles.get('countyOnly', {}))

    # Get output file
    output_file = args.output or os.path.join(OUTPUT_DIR, "crashes.csv")

    logger.info("=" * 60)
    logger.info(f"Starting crash data download at {datetime.now()}")
    logger.info(f"Jurisdiction: {jurisdiction_config.get('name', jurisdiction_id)}")
    logger.info(f"Filter: {filter_profile.get('name', filter_id)}")
    logger.info(f"Output: {output_file}")
    logger.info("=" * 60)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)

    df = None

    # Try primary API first
    try:
        df = download_from_arcgis(config, jurisdiction_config)
    except Exception as e:
        logger.error(f"Primary API failed: {e}")
        logger.info("Falling back to CSV download...")

    # Try fallback if primary failed
    if df is None or df.empty:
        try:
            df = download_from_fallback(config)
        except Exception as e:
            logger.error(f"Fallback download also failed: {e}")
            sys.exit(1)

    # Filter by jurisdiction
    logger.info("Filtering by jurisdiction...")
    df = filter_jurisdiction(df, jurisdiction_config)

    if df.empty:
        logger.error(f"No {jurisdiction_config.get('name', jurisdiction_id)} records found after filtering!")
        sys.exit(1)

    # Filter by road system
    logger.info("Applying road type filter...")
    df = filter_by_road_system(df, filter_profile)

    if df.empty:
        logger.error("No records remaining after road type filter!")
        sys.exit(1)

    # Standardize column names
    df = standardize_columns(df)

    # Save to CSV
    logger.info(f"Saving {len(df)} records to {output_file}")
    df.to_csv(output_file, index=False)

    logger.info("=" * 60)
    logger.info(f"Successfully downloaded {len(df)} crash records")
    logger.info(f"Output saved to: {output_file}")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
