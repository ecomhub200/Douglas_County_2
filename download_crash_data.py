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
import time
from datetime import datetime

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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

# Retry settings
MAX_RETRIES = 4
RETRY_BACKOFF_FACTOR = 2  # 2s, 4s, 8s, 16s


def create_session_with_retries():
    """Create a requests session with retry logic and browser-like headers."""
    session = requests.Session()
    retry_strategy = Retry(
        total=MAX_RETRIES,
        backoff_factor=RETRY_BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    # ArcGIS Hub blocks requests with default Python User-Agent (returns 403).
    # Use a browser-like User-Agent to avoid this.
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/csv,application/json,text/html,*/*',
    })
    return session


def make_request_with_retry(url, params=None, timeout=60, max_manual_retries=3):
    """
    Make HTTP request with manual retry logic for network errors.
    Uses exponential backoff: 2s, 4s, 8s, 16s
    """
    session = create_session_with_retries()
    last_exception = None

    for attempt in range(max_manual_retries):
        try:
            response = session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout as e:
            last_exception = e
            wait_time = RETRY_BACKOFF_FACTOR ** (attempt + 1)
            logger.warning(f"Request timeout (attempt {attempt + 1}/{max_manual_retries}). Retrying in {wait_time}s...")
            time.sleep(wait_time)
        except requests.exceptions.ConnectionError as e:
            last_exception = e
            wait_time = RETRY_BACKOFF_FACTOR ** (attempt + 1)
            logger.warning(f"Connection error (attempt {attempt + 1}/{max_manual_retries}). Retrying in {wait_time}s...")
            time.sleep(wait_time)
        except requests.exceptions.HTTPError as e:
            # Don't retry on 4xx errors (except 429 which is handled by Retry strategy)
            if e.response is not None and 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                raise
            last_exception = e
            wait_time = RETRY_BACKOFF_FACTOR ** (attempt + 1)
            logger.warning(f"HTTP error (attempt {attempt + 1}/{max_manual_retries}). Retrying in {wait_time}s...")
            time.sleep(wait_time)

    raise last_exception or Exception("Request failed after all retries")


def health_check_api(api_url):
    """
    Perform a health check on the API endpoint.
    Returns True if API is accessible, False otherwise.
    """
    try:
        params = {'where': '1=1', 'returnCountOnly': 'true', 'f': 'json'}
        response = make_request_with_retry(api_url, params=params, timeout=30, max_manual_retries=2)
        data = response.json()

        if 'error' in data:
            logger.error(f"API health check failed: {data['error']}")
            return False

        count = data.get('count', 0)
        logger.info(f"API health check passed. Total records available: {count:,}")
        return True
    except Exception as e:
        logger.error(f"API health check failed: {e}")
        return False


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
    """Get total record count from ArcGIS API with retry logic."""
    params = {
        'where': where_clause,
        'returnCountOnly': 'true',
        'f': 'json'
    }

    response = make_request_with_retry(api_url, params=params, timeout=60)
    data = response.json()

    if 'error' in data:
        raise Exception(f"ArcGIS API error: {data['error']}")

    return data.get('count', 0)


def download_arcgis_page(api_url, where_clause, offset):
    """Download a page of records from ArcGIS API with retry logic."""
    params = {
        'where': where_clause,
        'outFields': '*',
        'returnGeometry': 'true',
        'outSR': '4326',
        'resultOffset': offset,
        'resultRecordCount': RECORDS_PER_REQUEST,
        'f': 'json'
    }

    response = make_request_with_retry(api_url, params=params, timeout=120)
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


def get_data_source_config(config, state='virginia'):
    """
    Get the data source configuration for a state.
    Handles both old format (config['dataSource']) and new format (config['dataSources'][state]).
    """
    # Try new format first: dataSources.<state>
    data_sources = config.get('dataSources', {})
    if state in data_sources:
        return data_sources[state]

    # Fall back to old format: dataSource (singular)
    return config.get('dataSource', {})


def find_working_api_url(config, state='virginia'):
    """
    Try to find a working API URL from configured options.
    Returns the first URL that passes health check.
    """
    data_source = get_data_source_config(config, state)
    primary_url = data_source.get('apiUrl')
    alternative_urls = data_source.get('apiUrlAlternatives', [])

    # Build list of URLs to try
    urls_to_try = []
    if primary_url:
        urls_to_try.append(primary_url)
    urls_to_try.extend(alternative_urls)

    # Default fallback
    if not urls_to_try:
        urls_to_try.append("https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/CrashData_Basic_Updated/FeatureServer/0/query")

    for url in urls_to_try:
        logger.info(f"Testing API endpoint: {url}")
        if health_check_api(url):
            logger.info(f"Using API endpoint: {url}")
            return url
        else:
            logger.warning(f"API endpoint not available: {url}")

    logger.error("No working API endpoint found!")
    return None


def download_from_arcgis(config, jurisdiction_config, state='virginia'):
    """
    Download crash data from ArcGIS REST API with pagination.
    Tries multiple API endpoints and filters for the specified jurisdiction.
    """
    api_url = find_working_api_url(config, state)

    if not api_url:
        raise Exception("No working ArcGIS API endpoint available")

    juris_code = jurisdiction_config.get('jurisCode', '')
    name_patterns = jurisdiction_config.get('namePatterns', [])
    fips = jurisdiction_config.get('fips', '')
    name = jurisdiction_config.get('name', 'Unknown')

    logger.info(f"Attempting download from ArcGIS REST API for {name}...")

    # Build WHERE clauses for this jurisdiction
    # Order matters: Physical_Juris_Name is tried first because it captures ALL
    # roads within a jurisdiction's boundaries (including Interstate, State Hwy).
    # Juris_Code may only match locally-maintained roads, giving partial results.
    where_clauses = []

    if name_patterns:
        for pattern in name_patterns:
            where_clauses.append(f"Physical_Juris_Name LIKE '%{pattern}%'")

    if juris_code:
        where_clauses.append(f"Juris_Code = '{juris_code}' OR Juris_Code = {juris_code}")

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

        # Warn if dataset is suspiciously small (likely district-specific, not statewide)
        if count < 50000:
            logger.warning(f"API has only {count:,} records — likely a district-specific dataset, not statewide")
            logger.warning("This endpoint may not contain data for the requested jurisdiction")

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


def download_csv_from_url(url, max_poll_attempts=6, poll_interval_seconds=30):
    """Download crash data CSV from a single URL with polling for async generation.

    ArcGIS Hub may return a JSON "Pending" status for large datasets that are
    generated asynchronously. This function polls until the CSV is ready.
    """
    import io

    for attempt in range(max_poll_attempts):
        response = make_request_with_retry(url, timeout=300, max_manual_retries=4)
        text = response.text.strip()

        # Check for async generation response (ArcGIS Hub returns JSON when generating)
        if text.startswith('{'):
            try:
                status = json.loads(text)
                if status.get('status') == 'Pending' or 'being generated' in status.get('message', ''):
                    if attempt < max_poll_attempts - 1:
                        logger.info(f"CSV generation pending, polling in {poll_interval_seconds}s "
                                    f"(attempt {attempt + 1}/{max_poll_attempts})...")
                        time.sleep(poll_interval_seconds)
                        continue
                    else:
                        raise Exception(
                            f"CSV still pending after {max_poll_attempts * poll_interval_seconds}s. "
                            f"The ArcGIS Hub may be slow — try again later.")
            except json.JSONDecodeError:
                pass  # Not valid JSON, try parsing as CSV below

        # Parse as CSV
        df = pd.read_csv(io.StringIO(text))

        # Validate it looks like real crash data
        if len(df) < 10 or len(df.columns) < 5:
            raise Exception(f"CSV appears empty or malformed ({len(df)} rows, {len(df.columns)} columns)")

        logger.info(f"Downloaded {len(df)} records from CSV endpoint")
        return df

    raise Exception("CSV download timed out waiting for file generation")


def download_from_fallback(config, state='virginia'):
    """Download crash data from CSV URLs with retry logic.

    Tries multiple CSV download URLs in order. ArcGIS Hub sometimes blocks
    specific item URLs or returns 403, so having alternatives is important.
    """
    data_source = get_data_source_config(config, state)

    # Build list of CSV URLs to try (primary + alternatives)
    csv_urls = []

    primary_url = data_source.get('fallbackUrl')
    if primary_url:
        csv_urls.append(primary_url)

    csv_urls.extend(data_source.get('fallbackUrlAlternatives', []))

    # Hardcoded defaults if nothing configured
    if not csv_urls:
        csv_urls = [
            # CrashData Basic (the original default)
            "https://www.virginiaroads.org/api/download/v1/items/1a96a2f31b4f4d77991471b6cabb38ba/csv?layers=0",
            # Full Crash dataset (statewide with all fields)
            "https://www.virginiaroads.org/api/download/v1/items/3bd854bff90d49eaa85bdc68acf952e0/csv?layers=0",
            # CrashData Details (layer 1)
            "https://www.virginiaroads.org/api/download/v1/items/101101cecac34f28b38c0846e847bd0b/csv?layers=1",
        ]

    last_error = None
    for url in csv_urls:
        try:
            logger.info(f"Trying CSV download: {url}")
            df = download_csv_from_url(url)
            return df
        except Exception as e:
            last_error = e
            logger.warning(f"CSV download failed for {url}: {e}")
            continue

    raise last_error or Exception("All CSV download URLs failed")


def filter_jurisdiction(df, jurisdiction_config):
    """Filter dataframe to only include records for the specified jurisdiction."""
    original_count = len(df)

    juris_code = jurisdiction_config.get('jurisCode', '')
    name_patterns = jurisdiction_config.get('namePatterns', [])
    fips = jurisdiction_config.get('fips', '')
    name = jurisdiction_config.get('name', 'Unknown')

    # Log available columns for debugging
    logger.info(f"Available columns in data: {list(df.columns)[:20]}...")  # First 20

    # Try multiple filter approaches
    mask = pd.Series([False] * len(df))
    found_columns = []

    # Check various possible column names for jurisdiction code
    if juris_code:
        juris_columns = [
            'Juris_Code', 'JURIS_CODE', 'juris_code', 'Juris Code',
            'JURISCODE', 'JurisCode', 'Jurisdiction_Code', 'JURISDICTION_CODE'
        ]
        for col in juris_columns:
            if col in df.columns:
                found_columns.append(f"juris_code:{col}")
                # Try both numeric and string comparison
                mask |= df[col].astype(str).str.strip() == str(juris_code)
                mask |= df[col].astype(str).str.strip() == str(int(juris_code)) if juris_code.isdigit() else False
                break
        # Also try case-insensitive column search
        if not any('juris_code' in c for c in found_columns):
            for col in df.columns:
                if 'juris' in col.lower() and 'code' in col.lower():
                    found_columns.append(f"juris_code:{col}")
                    mask |= df[col].astype(str).str.strip() == str(juris_code)
                    break

    # Check Physical Juris Name
    if name_patterns:
        name_columns = [
            'Physical_Juris_Name', 'PHYSICAL_JURIS_NAME', 'Physical Juris Name',
            'PHYSICAL_JURIS', 'PhysicalJurisName', 'PHYSICALJURISNAME',
            'Physical_Jurisdiction', 'PHYSICAL_JURISDICTION', 'Jurisdiction_Name'
        ]
        for col in name_columns:
            if col in df.columns:
                found_columns.append(f"name:{col}")
                for pattern in name_patterns:
                    mask |= df[col].astype(str).str.upper().str.contains(pattern.upper(), na=False)
                break
        # Also try case-insensitive column search
        if not any('name:' in c for c in found_columns):
            for col in df.columns:
                if 'juris' in col.lower() and 'name' in col.lower():
                    found_columns.append(f"name:{col}")
                    for pattern in name_patterns:
                        mask |= df[col].astype(str).str.upper().str.contains(pattern.upper(), na=False)
                    break

    # Check FIPS code
    if fips:
        fips_columns = [
            'COUNTYFP', 'FIPS', 'County_FIPS', 'countyfp',
            'COUNTY_FIPS', 'CountyFIPS', 'FIPS_Code', 'FIPSCode'
        ]
        for col in fips_columns:
            if col in df.columns:
                found_columns.append(f"fips:{col}")
                mask |= df[col].astype(str).str.strip() == fips
                mask |= df[col].astype(str).str.strip().str.zfill(3) == fips.zfill(3)
                break

    logger.info(f"Filter columns found: {found_columns}")
    logger.info(f"Filter criteria - juris_code: {juris_code}, fips: {fips}, patterns: {name_patterns}")

    df_filtered = df[mask].copy().reset_index(drop=True)

    # If no records found, log sample values from relevant columns
    if len(df_filtered) == 0 and len(df) > 0:
        logger.warning("No records matched! Sample values from potential jurisdiction columns:")
        for col in df.columns:
            col_lower = col.lower()
            if any(kw in col_lower for kw in ['juris', 'county', 'fips', 'physical']):
                sample_vals = df[col].dropna().astype(str).unique()[:5]
                logger.warning(f"  {col}: {list(sample_vals)}")

    logger.info(f"Filtered from {original_count} to {len(df_filtered)} {name} records")

    return df_filtered


def filter_by_road_system(df, filter_profile):
    """
    Filter dataframe based on road system type or ownership values.
    """
    original_count = len(df)

    system_values = filter_profile.get('systemValues', [])
    ownership_values = filter_profile.get('ownershipValues', [])
    exclude_patterns = filter_profile.get('excludeRoutePatterns', [])
    filter_name = filter_profile.get('name', 'Unknown Filter')

    if ownership_values:
        # Filter by ownership column
        ownership_columns = ['Ownership', 'OWNERSHIP', 'ownership']
        ownership_col = None
        for col in ownership_columns:
            if col in df.columns:
                ownership_col = col
                break

        if ownership_col is None:
            logger.warning("Could not find Ownership column, skipping ownership filter")
            return df

        mask = df[ownership_col].astype(str).apply(
            lambda x: any(val in x for val in ownership_values)
        )
        df_filtered = df[mask].copy().reset_index(drop=True)

    elif system_values:
        # Filter by system values
        system_columns = ['SYSTEM', 'System', 'system']
        system_col = None
        for col in system_columns:
            if col in df.columns:
                system_col = col
                break

        if system_col is None:
            logger.warning("Could not find SYSTEM column, skipping road system filter")
            return df

        mask = df[system_col].astype(str).str.upper().apply(
            lambda x: any(sys_val.upper() in x for sys_val in system_values)
        )
        df_filtered = df[mask].copy().reset_index(drop=True)

    else:
        logger.warning(f"Filter profile '{filter_name}' has no systemValues or ownershipValues, returning all data")
        return df

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

    # Additional column names from newer ArcGIS endpoints
    column_mapping.update({
        'LOCAL_CASE_CD': 'Local Case CD',
        'ROUTE_OR_STREET_NM': 'Route or Street Name',
        'INTERSECTION_ANALYSIS': 'Intersection Analysis',
        'ANIMAL': 'Animal Related?',
    })

    # Rename columns that exist
    rename_dict = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df.rename(columns=rename_dict)

    # ── Decode ArcGIS FeatureServer coded domain values ──
    # The FeatureServer API returns raw numeric/abbreviated codes instead of
    # human-readable text (e.g., OWNERSHIP=3 instead of "3. City or Town Hwy Agency").
    # These mappings are derived from the VDOT ArcGIS service field domains.

    # Ownership codes → text labels
    if 'Ownership' in df.columns:
        ownership_map = {
            '1': '1. State Hwy Agency',
            '2': '2. County Hwy Agency',
            '3': '3. City or Town Hwy Agency',
            '4': '4. Federal Roads',
            '5': '5. State Toll Authority',
            '6': '6. Other',
        }
        raw = df['Ownership'].astype(str).str.strip()
        # Only decode if values are numeric codes (not already decoded text)
        if raw.isin(ownership_map.keys()).any() and not raw.str.contains('Hwy Agency', na=False).any():
            df['Ownership'] = raw.map(ownership_map).fillna(df['Ownership'])

    # SYSTEM codes → text labels
    if 'SYSTEM' in df.columns:
        system_map = {
            '1': 'Interstate',
            '2': 'Primary',
            '3': 'Secondary',
            '4': 'NonVDOT primary',
            '5': 'NonVDOT secondary',
            '6': 'Non-VDOT',
        }
        raw = df['SYSTEM'].astype(str).str.strip()
        if raw.isin(system_map.keys()).any() and not raw.str.contains('VDOT', na=False).any():
            df['SYSTEM'] = raw.map(system_map).fillna(df['SYSTEM'])

    # Functional Class codes → text labels
    if 'Functional Class' in df.columns:
        func_class_map = {
            'INT': '1-Interstate (A,1)',
            'OFE': '2-Principal Arterial - Other Freeways and Expressways (B)',
            'OPA': '3-Principal Arterial - Other (E,2)',
            'MIA': '4-Minor Arterial (H,3)',
            'MAC': '5-Major Collector (I,4)',
            'MIC': '6-Minor Collector (5)',
            'LOC': '7-Local (J,6)',
        }
        raw = df['Functional Class'].astype(str).str.strip()
        if raw.isin(func_class_map.keys()).any() and not raw.str.contains('Interstate', na=False).any():
            df['Functional Class'] = raw.map(func_class_map).fillna(df['Functional Class'])

    # Facility Type codes → text labels
    if 'Facility Type' in df.columns:
        facility_map = {
            'TUD': 'Two-Way Undivided',
            'TDD': 'Two-Way Divided',
            'OWA': 'One-Way',
        }
        raw = df['Facility Type'].astype(str).str.strip()
        if raw.isin(facility_map.keys()).any() and not raw.str.contains('Way', na=False).any():
            df['Facility Type'] = raw.map(facility_map).fillna(df['Facility Type'])

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
        choices=['countyOnly', 'cityOnly', 'countyPlusVDOT', 'allRoads'],
        help='Road type filter profile'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output file path (default: data/<jurisdiction>_all_roads.csv)'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        help='Output directory (auto-generates filename from jurisdiction). Ignored if --output is set.'
    )

    parser.add_argument(
        '--force-download',
        action='store_true',
        help='Force re-download even if cached data exists'
    )

    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List all available jurisdictions and exit'
    )

    parser.add_argument(
        '--health-check',
        action='store_true',
        help='Run API health check and exit'
    )

    parser.add_argument(
        '--merge',
        action='store_true',
        help='Merge new data with existing validated dataset instead of replacing it'
    )

    parser.add_argument(
        '--save-statewide',
        action='store_true',
        help='Save a gzipped copy of the full statewide dataset before jurisdiction filtering'
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

    # Handle --health-check option
    if args.health_check:
        logger.info("Running API health check...")
        working_url = find_working_api_url(config)
        if working_url:
            logger.info(f"Health check PASSED. Working endpoint: {working_url}")
            return 0
        else:
            logger.error("Health check FAILED. No working API endpoint found.")
            return 1

    # Get jurisdiction
    jurisdiction_id = args.jurisdiction or config.get('defaults', {}).get('jurisdiction', 'henrico')
    jurisdiction_config = get_jurisdiction_config(config, jurisdiction_id)

    # Get filter profile
    filter_id = args.filter or config.get('defaults', {}).get('filterProfile', 'allRoads')
    filter_profiles = config.get('filterProfiles', {})
    filter_profile = filter_profiles.get(filter_id, filter_profiles.get('countyOnly', {}))

    # Get output file
    if args.output:
        output_file = args.output
    elif args.output_dir:
        output_file = os.path.join(args.output_dir, f"{jurisdiction_id}_all_roads.csv")
    else:
        output_file = os.path.join(OUTPUT_DIR, f"{jurisdiction_id}_all_roads.csv")

    logger.info("=" * 60)
    logger.info(f"Starting crash data download at {datetime.now()}")
    logger.info(f"Jurisdiction: {jurisdiction_config.get('name', jurisdiction_id)}")
    logger.info(f"Filter: {filter_profile.get('name', filter_id)}")
    logger.info(f"Output: {output_file}")
    logger.info("=" * 60)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)

    df = None
    df_filtered = None
    used_api_fallback = False
    statewide_saved = False

    # Try CSV download first (primary source - has complete statewide data)
    try:
        logger.info("Downloading from Virginia Roads CSV (primary source)...")
        df = download_from_fallback(config, state='virginia')

        # Stage 1.5: Save statewide copy as gzip before jurisdiction filtering
        if args.save_statewide and df is not None and not df.empty:
            try:
                statewide_dir = args.output_dir or OUTPUT_DIR
                statewide_path = os.path.join(statewide_dir, "virginia_statewide_all_roads.csv")
                logger.info(f"Saving statewide dataset ({len(df):,} records) before filtering...")
                df_statewide = standardize_columns(df.copy())

                # Validate that this is crash-level data (not driver-level)
                required_cols = {'Crash_Severity', 'Crash Severity', 'crash_seve', 'Crash_Year', 'Crash Year', 'crash_year'}
                has_crash_cols = bool(required_cols & set(df_statewide.columns))
                if not has_crash_cols:
                    logger.warning(f"Downloaded data appears to be driver-level (columns: {list(df_statewide.columns)[:10]}...)")
                    logger.warning("Skipping statewide save — data lacks crash-level columns needed for splitting.")
                else:
                    # Validate that jurisdiction columns exist (needed for split_jurisdictions.py)
                    jurisdiction_cols = {
                        'Juris_Code', 'Juris Code', 'JURIS_CODE',
                        'Physical_Juris_Name', 'Physical Juris Name', 'PHYSICAL_JURIS_NAME',
                        'FIPS', 'County_FIPS', 'COUNTY_FIPS', 'COUNTYFP',
                        'Jurisdiction', 'JURISDICTION', 'County_City', 'COUNTY_CITY'
                    }
                    has_jurisdiction_cols = bool(jurisdiction_cols & set(df_statewide.columns))
                    if not has_jurisdiction_cols:
                        logger.warning(f"Downloaded data has NO jurisdiction columns (columns: {list(df_statewide.columns)[:15]}...)")
                        logger.warning("Skipping statewide save — data cannot be split by jurisdiction without Juris_Code/FIPS/Physical_Juris_Name.")
                    else:
                        df_statewide.to_csv(statewide_path, index=False)
                        statewide_saved = True
                        logger.info(f"Statewide CSV saved: {statewide_path} ({os.path.getsize(statewide_path):,} bytes)")

                        # Gzip the statewide CSV
                        import gzip
                        import shutil
                        gz_path = f"{statewide_path}.gz"
                        with open(statewide_path, 'rb') as f_in:
                            with gzip.open(gz_path, 'wb', compresslevel=6) as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        uncompressed_size = os.path.getsize(statewide_path)
                        compressed_size = os.path.getsize(gz_path)
                        # Keep uncompressed CSV alongside gzip for batch splitting workflows
                        # (split_jurisdictions.py needs the uncompressed CSV to split into
                        # per-jurisdiction files). The batch workflow cleans up after splitting.
                        ratio = uncompressed_size / compressed_size if compressed_size > 0 else 0
                        logger.info(f"Statewide gzip saved: {gz_path} ({compressed_size:,} bytes, {ratio:.1f}x compression)")
            except Exception as e:
                logger.warning(f"Failed to save statewide copy (non-fatal): {e}")

        # Filter by jurisdiction
        logger.info("Filtering by jurisdiction...")
        df_filtered = filter_jurisdiction(df, jurisdiction_config)

        if df_filtered.empty:
            logger.warning(f"CSV data has no records for {jurisdiction_config.get('name', jurisdiction_id)}")
            df = None  # Reset to trigger API fallback

    except Exception as e:
        logger.error(f"CSV download failed: {e}")
        logger.info("Falling back to ArcGIS API...")

    # Try ArcGIS API as fallback if CSV failed or returned no records
    if df is None or (df_filtered is not None and df_filtered.empty):
        try:
            logger.info("=" * 40)
            logger.info("Attempting ArcGIS API fallback...")
            df = download_from_arcgis(config, jurisdiction_config, state='virginia')
            used_api_fallback = True

            # Filter by jurisdiction
            logger.info("Filtering API data by jurisdiction...")
            df_filtered = filter_jurisdiction(df, jurisdiction_config)

        except Exception as e:
            logger.error(f"ArcGIS API fallback also failed: {e}")
            sys.exit(1)

    # Use the filtered dataframe
    df = df_filtered

    if df is None or df.empty:
        logger.error(f"No {jurisdiction_config.get('name', jurisdiction_id)} records found after filtering!")
        logger.error("Neither CSV nor API contained data for this jurisdiction.")
        sys.exit(1)

    if used_api_fallback:
        logger.info(f"Successfully retrieved {len(df)} records using ArcGIS API fallback")
        # CRITICAL: If --save-statewide was requested but CSV download failed,
        # the ArcGIS API only returns jurisdiction-specific data (not statewide).
        # The statewide CSV was NOT saved. Warn loudly so the batch workflow knows.
        if args.save_statewide and not statewide_saved:
            logger.error("=" * 60)
            logger.error("WARNING: --save-statewide was requested but CSV download failed!")
            logger.error("ArcGIS API fallback only has jurisdiction-specific data.")
            logger.error("NO statewide CSV was saved. Batch pipeline will NOT work.")
            logger.error("Fix: Ensure Virginia Roads CSV URLs are accessible.")
            logger.error("=" * 60)
    else:
        logger.info(f"Successfully retrieved {len(df)} records from CSV source")

    # Filter by road system
    logger.info("Applying road type filter...")
    df = filter_by_road_system(df, filter_profile)

    if df.empty:
        logger.error("No records remaining after road type filter!")
        sys.exit(1)

    # Standardize column names
    df = standardize_columns(df)

    # Merge with existing validated dataset if --merge flag is set
    if args.merge and os.path.exists(output_file):
        logger.info("=" * 40)
        logger.info("MERGE MODE: Merging with existing dataset")
        logger.info("=" * 40)

        try:
            existing_df = pd.read_csv(output_file, dtype=str)
            existing_count = len(existing_df)
            logger.info(f"Existing dataset: {existing_count} records")
            logger.info(f"New download: {len(df)} records")

            # Concatenate existing + new
            combined_df = pd.concat([existing_df, df], ignore_index=True)
            combined_count = len(combined_df)

            # Deduplicate: prefer existing records (keep='first')
            # Primary key: Document Nbr (if available)
            doc_col = None
            for col in ['Document Nbr', 'Document Number', 'CrashID', 'CRASH_ID']:
                if col in combined_df.columns:
                    doc_col = col
                    break

            dedup_count_before = len(combined_df)

            if doc_col:
                # Remove rows with duplicate Document Numbers (keep existing = first)
                mask = combined_df[doc_col].notna() & (combined_df[doc_col] != '') & (combined_df[doc_col] != 'nan')
                has_doc = combined_df[mask]
                no_doc = combined_df[~mask]
                has_doc_deduped = has_doc.drop_duplicates(subset=[doc_col], keep='first')
                combined_df = pd.concat([has_doc_deduped, no_doc], ignore_index=True)
                logger.info(f"  Doc# dedup: {dedup_count_before} -> {len(combined_df)} records")

            # Secondary dedup: Crash Date + coordinates + Collision Type
            dedup_cols = ['Crash Date', 'x', 'y', 'Collision Type']
            existing_dedup_cols = [c for c in dedup_cols if c in combined_df.columns]
            if len(existing_dedup_cols) == 4:
                has_coords = (
                    combined_df['x'].notna() & (combined_df['x'] != '') & (combined_df['x'] != '0') &
                    combined_df['y'].notna() & (combined_df['y'] != '') & (combined_df['y'] != '0')
                )
                df_with_coords = combined_df[has_coords]
                df_without_coords = combined_df[~has_coords]
                dedup_before = len(df_with_coords)
                df_with_coords_deduped = df_with_coords.drop_duplicates(
                    subset=existing_dedup_cols, keep='first'
                )
                combined_df = pd.concat([df_with_coords_deduped, df_without_coords], ignore_index=True)
                logger.info(f"  Geo dedup: {dedup_before + len(df_without_coords)} -> {len(combined_df)} records")

            duplicates_removed = dedup_count_before - len(combined_df)
            new_records = len(combined_df) - existing_count
            logger.info(f"  Merge result: {existing_count} existing + {new_records} new ({duplicates_removed} duplicates removed)")
            df = combined_df

        except Exception as e:
            logger.error(f"Merge failed: {e}")
            logger.info("Falling back to full replacement")

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
