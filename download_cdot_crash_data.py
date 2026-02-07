#!/usr/bin/env python3
"""
Download statewide crash data from CDOT's Hyland OnBase document management system,
filter to a specific Colorado county, and save as CSV.

The statewide Excel files are hosted at:
    https://oitco.hylandcloud.com/CDOTRMPop/docpop/docpop.aspx?clienttype=html&docid=<DOCID>

Doc IDs for each year are stored in data/CDOT/source_manifest.json. This file must be
updated manually when CDOT publishes new annual data (they assign arbitrary doc IDs).

Usage:
    python download_cdot_crash_data.py                          # Download all years for default county
    python download_cdot_crash_data.py --latest                 # Download most recent year only
    python download_cdot_crash_data.py --years 2023 2024        # Download specific years
    python download_cdot_crash_data.py --jurisdiction elpaso    # Download for El Paso County
    python download_cdot_crash_data.py --list                   # Show available years and counties
    python download_cdot_crash_data.py --no-dict                # Skip data dictionary downloads
    python download_cdot_crash_data.py --statewide              # Keep statewide file (don't filter)
"""

import argparse
import io
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

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
SCRIPT_DIR = Path(__file__).parent.resolve()

# Manifest path
MANIFEST_FILE = SCRIPT_DIR / 'data' / 'CDOT' / 'source_manifest.json'

# Default output directory
DEFAULT_DATA_DIR = SCRIPT_DIR / 'data' / 'CDOT'

# Retry settings (matches existing downloaders)
MAX_RETRIES = 4
RETRY_BACKOFF_FACTOR = 2  # 2s, 4s, 8s, 16s

# OnBase base URL
ONBASE_BASE_URL = 'https://oitco.hylandcloud.com/CDOTRMPop/docpop/docpop.aspx'

# Realistic browser headers to avoid being blocked
BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# Minimum file size to consider a download valid (100 KB)
MIN_VALID_FILE_SIZE = 100 * 1024

# Excel file magic bytes
XLSX_MAGIC = b'PK'  # ZIP-based format (xlsx)
XLS_MAGIC = b'\xd0\xcf'  # OLE2 format (xls)


def create_session_with_retries():
    """Create a requests session with retry logic."""
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
    session.headers.update(BROWSER_HEADERS)
    return session


def make_request_with_retry(session, url, params=None, timeout=120, max_manual_retries=4,
                            stream=False):
    """
    Make HTTP request with manual retry logic for network errors.
    Uses exponential backoff: 2s, 4s, 8s, 16s
    """
    last_exception = None

    for attempt in range(max_manual_retries):
        try:
            response = session.get(url, params=params, timeout=timeout,
                                   allow_redirects=True, stream=stream)
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout as e:
            last_exception = e
            wait_time = RETRY_BACKOFF_FACTOR ** (attempt + 1)
            logger.warning(f"Request timeout (attempt {attempt + 1}/{max_manual_retries}). "
                           f"Retrying in {wait_time}s...")
            time.sleep(wait_time)
        except requests.exceptions.ConnectionError as e:
            last_exception = e
            wait_time = RETRY_BACKOFF_FACTOR ** (attempt + 1)
            logger.warning(f"Connection error (attempt {attempt + 1}/{max_manual_retries}). "
                           f"Retrying in {wait_time}s...")
            time.sleep(wait_time)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                raise
            last_exception = e
            wait_time = RETRY_BACKOFF_FACTOR ** (attempt + 1)
            logger.warning(f"HTTP error (attempt {attempt + 1}/{max_manual_retries}). "
                           f"Retrying in {wait_time}s...")
            time.sleep(wait_time)

    raise last_exception or Exception("Request failed after all retries")


def load_manifest(manifest_path=None):
    """Load the source manifest with doc IDs and configuration."""
    path = Path(manifest_path) if manifest_path else MANIFEST_FILE
    if not path.exists():
        logger.error(f"Manifest file not found: {path}")
        logger.info("Expected location: data/CDOT/source_manifest.json")
        sys.exit(1)

    with open(path, 'r') as f:
        manifest = json.load(f)

    year_count = len(manifest.get('files', {}))
    county_count = len(manifest.get('jurisdiction_filters', {}))
    logger.info(f"Loaded manifest: {year_count} years, {county_count} jurisdictions")
    return manifest


def detect_file_type(content, content_type='', content_disposition=''):
    """
    Detect if downloaded content is actually an Excel file (not HTML error page).
    Returns (is_valid, extension, reason).
    """
    # Check magic bytes
    if content[:2] == XLSX_MAGIC:
        return True, '.xlsx', 'XLSX (ZIP) magic bytes detected'
    if content[:2] == XLS_MAGIC:
        return True, '.xls', 'XLS (OLE2) magic bytes detected'

    # Check if it's HTML (error page or login redirect)
    if content[:500].strip().lower().startswith((b'<!doctype', b'<html', b'<?xml')):
        return False, '.html', 'Response is HTML (likely error page or login redirect)'

    # Check Content-Type header
    ct = content_type.lower()
    if 'spreadsheet' in ct or 'excel' in ct or 'octet-stream' in ct:
        return True, '.xlsx', f'Content-Type suggests binary: {content_type}'

    # Check Content-Disposition for filename
    if content_disposition:
        match = re.search(r'filename[*]?=["\']?([^"\';\s]+)', content_disposition)
        if match:
            filename = match.group(1)
            if filename.endswith('.xlsx'):
                return True, '.xlsx', f'Filename from header: {filename}'
            if filename.endswith('.xls'):
                return True, '.xls', f'Filename from header: {filename}'

    # Default: check file size (Excel files are typically > 100KB)
    if len(content) > MIN_VALID_FILE_SIZE:
        return True, '.xlsx', f'Large binary file ({len(content):,} bytes), assuming xlsx'

    return False, '.unknown', f'Cannot determine file type ({len(content):,} bytes)'


def extract_download_url_from_html(html_content, base_url):
    """
    If OnBase returns an HTML viewer page instead of the file directly,
    parse it to find the actual document download URL.
    """
    html_str = html_content.decode('utf-8', errors='ignore')

    # Look for common OnBase download URL patterns
    patterns = [
        r'href=["\']([^"\']*PdfPop\.aspx[^"\']*)["\']',
        r'href=["\']([^"\']*GetDoc[^"\']*)["\']',
        r'href=["\']([^"\']*Download[^"\']*)["\']',
        r'src=["\']([^"\']*\.xlsx?[^"\']*)["\']',
        r'window\.location\s*=\s*["\']([^"\']+)["\']',
        r'window\.open\(["\']([^"\']+)["\']',
    ]

    for pattern in patterns:
        match = re.search(pattern, html_str, re.IGNORECASE)
        if match:
            url = match.group(1)
            # Handle relative URLs
            if url.startswith('/'):
                from urllib.parse import urlparse
                parsed = urlparse(base_url)
                url = f"{parsed.scheme}://{parsed.netloc}{url}"
            elif not url.startswith('http'):
                url = base_url.rsplit('/', 1)[0] + '/' + url
            return url

    return None


def download_onbase_document(session, docid, label='document'):
    """
    Download a document from Hyland OnBase. Handles the redirect chain
    and falls back to parsing HTML if needed.

    Returns (content_bytes, extension) or raises on failure.
    """
    url = ONBASE_BASE_URL
    params = {'clienttype': 'html', 'docid': str(docid)}

    logger.info(f"Downloading {label} (docid={docid})...")

    # First attempt: direct request with redirects
    response = make_request_with_retry(session, url, params=params, timeout=180)
    content = response.content
    content_type = response.headers.get('Content-Type', '')
    content_disposition = response.headers.get('Content-Disposition', '')

    is_valid, ext, reason = detect_file_type(content, content_type, content_disposition)
    logger.info(f"  First attempt: {reason}")

    if is_valid:
        logger.info(f"  Downloaded {len(content):,} bytes")
        return content, ext

    # Second attempt: if we got HTML, try to extract the real download URL
    logger.info("  Got HTML response. Parsing for download link...")
    download_url = extract_download_url_from_html(content, response.url)

    if download_url:
        logger.info(f"  Found download link: {download_url[:100]}...")
        response = make_request_with_retry(session, download_url, timeout=180)
        content = response.content
        content_type = response.headers.get('Content-Type', '')
        content_disposition = response.headers.get('Content-Disposition', '')

        is_valid, ext, reason = detect_file_type(content, content_type, content_disposition)
        logger.info(f"  Second attempt: {reason}")

        if is_valid:
            logger.info(f"  Downloaded {len(content):,} bytes")
            return content, ext

    # Third attempt: try clienttype=activex (some OnBase instances support this)
    logger.info("  Trying clienttype=activex...")
    params_activex = {'clienttype': 'activex', 'docid': str(docid)}
    try:
        response = make_request_with_retry(session, url, params=params_activex, timeout=180)
        content = response.content
        content_type = response.headers.get('Content-Type', '')
        content_disposition = response.headers.get('Content-Disposition', '')

        is_valid, ext, reason = detect_file_type(content, content_type, content_disposition)
        logger.info(f"  Third attempt: {reason}")

        if is_valid:
            logger.info(f"  Downloaded {len(content):,} bytes")
            return content, ext
    except Exception as e:
        logger.debug(f"  activex attempt failed: {e}")

    raise Exception(
        f"Failed to download {label} (docid={docid}). "
        f"All download strategies returned non-Excel content. "
        f"The OnBase portal may require browser-based access."
    )


def excel_to_dataframe(content_bytes, ext):
    """Read Excel bytes into a pandas DataFrame."""
    try:
        import pandas as pd
    except ImportError:
        logger.error("pandas is required for Excel-to-CSV conversion. Install with: pip install pandas")
        sys.exit(1)

    try:
        import openpyxl  # noqa: F401 - needed by pandas for xlsx
    except ImportError:
        logger.error("openpyxl is required for reading .xlsx files. Install with: pip install openpyxl")
        sys.exit(1)

    buf = io.BytesIO(content_bytes)

    if ext == '.xls':
        # Older Excel format
        try:
            df = pd.read_excel(buf, engine='xlrd')
        except ImportError:
            logger.error("xlrd is required for reading .xls files. Install with: pip install xlrd")
            sys.exit(1)
    else:
        df = pd.read_excel(buf, engine='openpyxl')

    logger.info(f"  Parsed Excel: {len(df):,} rows x {len(df.columns)} columns")
    return df


def filter_to_jurisdiction(df, jurisdiction_config, jurisdiction_key):
    """
    Filter statewide DataFrame to a specific county.
    Uses the County column as primary filter.
    """
    county_name = jurisdiction_config['county']
    display_name = jurisdiction_config.get('display_name', county_name)

    original_count = len(df)

    # Find the County column (case-insensitive)
    county_col = None
    for col in df.columns:
        if col.strip().lower() == 'county':
            county_col = col
            break

    if county_col is None:
        logger.error(f"County column not found in data. Available columns: {list(df.columns)[:20]}")
        return df

    # Filter by county name (case-insensitive)
    mask = df[county_col].astype(str).str.strip().str.upper() == county_name.upper()
    df_filtered = df[mask].copy().reset_index(drop=True)

    logger.info(f"  Filtered: {original_count:,} statewide → {len(df_filtered):,} {display_name} records")

    if len(df_filtered) == 0:
        # Log unique county values for debugging
        unique_counties = sorted(df[county_col].dropna().astype(str).str.strip().unique())
        logger.warning(f"  No records matched! Unique counties in data ({len(unique_counties)} total):")
        for c in unique_counties[:15]:
            logger.warning(f"    {c}")
        if len(unique_counties) > 15:
            logger.warning(f"    ... and {len(unique_counties) - 15} more")

    return df_filtered


def process_year(session, year, year_info, manifest, data_dir, jurisdiction_key):
    """
    Download a single year's statewide file, filter to county, save as CSV.
    Returns (year, success_bool, output_path_or_error).
    """
    docid = year_info['docid']
    status = year_info.get('status', 'unknown')
    label = f"CDOT Crash Listing {year}"
    if status == 'preliminary':
        label += " (preliminary)"

    try:
        # Download the Excel file
        content, ext = download_onbase_document(session, docid, label=label)

        # Parse Excel to DataFrame
        df = excel_to_dataframe(content, ext)

        if df.empty:
            return year, False, "Downloaded file contains no data rows"

        # Log column summary
        logger.info(f"  Columns: {list(df.columns)[:10]}...")

        # Filter to jurisdiction
        jurisdiction_filters = manifest.get('jurisdiction_filters', {})
        if jurisdiction_key and jurisdiction_key in jurisdiction_filters:
            jur_config = jurisdiction_filters[jurisdiction_key]
            df = filter_to_jurisdiction(df, jur_config, jurisdiction_key)
            display_name = jur_config.get('display_name', jurisdiction_key)
            filename = f"{year} {display_name.lower().replace(' county', '').strip()}.csv"

            if df.empty:
                return year, False, f"No records for {display_name} in {year} data"
        else:
            filename = f"cdot_crash_statewide_{year}.csv"

        # Save as CSV
        output_path = data_dir / filename
        df.to_csv(output_path, index=False)
        logger.info(f"  Saved: {output_path} ({len(df):,} records)")

        return year, True, str(output_path)

    except Exception as e:
        logger.error(f"  Failed to process {year}: {e}")
        return year, False, str(e)


def download_data_dictionary(session, dict_info, data_dir):
    """Download a data dictionary file."""
    docid = dict_info['docid']
    desc = dict_info.get('description', f'docid={docid}')

    try:
        content, ext = download_onbase_document(session, docid, label=desc)
        output_path = data_dir / f"cdot_data_dictionary{ext}"
        with open(output_path, 'wb') as f:
            f.write(content)
        logger.info(f"  Saved data dictionary: {output_path}")
        return True
    except Exception as e:
        logger.warning(f"  Failed to download data dictionary: {e}")
        return False


def list_available(manifest):
    """List all available years and jurisdictions from the manifest."""
    print("\n" + "=" * 60)
    print("CDOT CRASH DATA - AVAILABLE DOWNLOADS")
    print("=" * 60)

    files = manifest.get('files', {})
    print(f"\nYEARS ({len(files)}):")
    print("-" * 40)
    for year in sorted(files.keys(), reverse=True):
        info = files[year]
        status_tag = f" [{info['status']}]" if info.get('status') != 'final' else ''
        print(f"  {year}  docid={info['docid']}{status_tag}")

    jurisdictions = {k: v for k, v in manifest.get('jurisdiction_filters', {}).items()
                     if not k.startswith('_') and isinstance(v, dict)}
    print(f"\nJURISDICTIONS ({len(jurisdictions)}):")
    print("-" * 40)
    for key, jur in sorted(jurisdictions.items()):
        agency = f" (Agency: {', '.join(jur['agency_ids'])})" if jur.get('agency_ids') else ''
        print(f"  {key:<15} {jur['display_name']}{agency}")

    dicts = manifest.get('data_dictionaries', {})
    print(f"\nDATA DICTIONARIES ({len(dicts)}):")
    print("-" * 40)
    for range_key, info in sorted(dicts.items()):
        print(f"  {range_key}  docid={info['docid']}  {info.get('description', '')}")

    print("=" * 60)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Download CDOT statewide crash data, filter to county, and save as CSV.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python download_cdot_crash_data.py                          # All years, default county (douglas)
  python download_cdot_crash_data.py --latest                 # Most recent year only
  python download_cdot_crash_data.py --years 2023 2024        # Specific years
  python download_cdot_crash_data.py --jurisdiction elpaso    # El Paso County
  python download_cdot_crash_data.py --list                   # Show available years/counties
  python download_cdot_crash_data.py --statewide              # Keep statewide (no county filter)
  python download_cdot_crash_data.py --no-dict                # Skip data dictionary
        """
    )

    parser.add_argument(
        '--years', '-y',
        nargs='+',
        type=str,
        help='Specific years to download (e.g., 2023 2024)'
    )

    parser.add_argument(
        '--latest',
        action='store_true',
        help='Download only the most recent year'
    )

    parser.add_argument(
        '--jurisdiction', '-j',
        type=str,
        default='douglas',
        help='County to filter to (default: douglas). See --list for options.'
    )

    parser.add_argument(
        '--statewide',
        action='store_true',
        help='Save statewide data without county filtering'
    )

    parser.add_argument(
        '--data-dir', '-d',
        type=str,
        default=None,
        help=f'Output directory (default: data/CDOT)'
    )

    parser.add_argument(
        '--no-dict',
        action='store_true',
        help='Skip downloading data dictionaries'
    )

    parser.add_argument(
        '--manifest', '-m',
        type=str,
        default=None,
        help='Path to source manifest JSON (default: data/CDOT/source_manifest.json)'
    )

    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List available years and jurisdictions, then exit'
    )

    return parser.parse_args()


def main():
    """Main function."""
    args = parse_args()

    # Load manifest
    manifest = load_manifest(args.manifest)

    # Handle --list
    if args.list:
        list_available(manifest)
        return 0

    # Determine output directory
    data_dir = Path(args.data_dir) if args.data_dir else DEFAULT_DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)

    # Determine which years to download
    all_files = manifest.get('files', {})

    if args.latest:
        latest_year = max(all_files.keys())
        years_to_download = {latest_year: all_files[latest_year]}
    elif args.years:
        years_to_download = {}
        for y in args.years:
            if y in all_files:
                years_to_download[y] = all_files[y]
            else:
                logger.warning(f"Year {y} not found in manifest. Available: {sorted(all_files.keys())}")
        if not years_to_download:
            logger.error("No valid years specified.")
            return 1
    else:
        years_to_download = all_files

    # Determine jurisdiction
    jurisdiction_key = None if args.statewide else args.jurisdiction
    jurisdiction_filters = manifest.get('jurisdiction_filters', {})

    if jurisdiction_key and jurisdiction_key not in jurisdiction_filters:
        logger.error(f"Unknown jurisdiction: {jurisdiction_key}")
        logger.info(f"Available: {', '.join(sorted(jurisdiction_filters.keys()))}")
        return 1

    # Print summary
    logger.info("=" * 60)
    logger.info(f"CDOT Crash Data Downloader")
    logger.info(f"Started at: {datetime.now()}")
    logger.info(f"Years: {', '.join(sorted(years_to_download.keys()))}")
    if jurisdiction_key:
        display = jurisdiction_filters[jurisdiction_key]['display_name']
        logger.info(f"Jurisdiction: {display}")
    else:
        logger.info(f"Jurisdiction: Statewide (no filter)")
    logger.info(f"Output: {data_dir}")
    logger.info("=" * 60)

    # Create session (reuse across all downloads for connection pooling)
    session = create_session_with_retries()

    # Download data dictionaries first (unless skipped)
    if not args.no_dict:
        logger.info("--- Downloading data dictionaries ---")
        for range_key, dict_info in manifest.get('data_dictionaries', {}).items():
            download_data_dictionary(session, dict_info, data_dir)

    # Download and process each year
    results = []
    logger.info(f"--- Downloading {len(years_to_download)} year(s) ---")

    for year in sorted(years_to_download.keys(), reverse=True):
        year_info = years_to_download[year]
        year_result = process_year(session, year, year_info, manifest, data_dir, jurisdiction_key)
        results.append(year_result)

    # Print summary
    successes = [(y, p) for y, ok, p in results if ok]
    failures = [(y, e) for y, ok, e in results if not ok]

    logger.info("")
    logger.info("=" * 60)
    logger.info("DOWNLOAD SUMMARY")
    logger.info("=" * 60)

    if successes:
        logger.info(f"Succeeded: {len(successes)}")
        for year, path in successes:
            logger.info(f"  {year}: {path}")

    if failures:
        logger.warning(f"Failed: {len(failures)}")
        for year, error in failures:
            logger.warning(f"  {year}: {error}")

    logger.info("=" * 60)

    return 1 if failures and not successes else 0


if __name__ == "__main__":
    sys.exit(main())
