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


def _playwright_available():
    """Check if Playwright is installed and has browsers."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except ImportError:
        return False


def download_with_playwright(docid, label='document', timeout_ms=60000):
    """
    Fallback: use a headless Chromium browser to download the file.
    Playwright handles JavaScript rendering, session cookies, and redirects
    that requests cannot follow.

    Returns (content_bytes, extension) or raises on failure.
    """
    from playwright.sync_api import sync_playwright

    url = f"{ONBASE_BASE_URL}?clienttype=html&docid={docid}"
    logger.info(f"  Playwright fallback: launching headless browser...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        downloaded_path = None

        try:
            # Navigate to the document page
            page.goto(url, wait_until='networkidle', timeout=timeout_ms)
            logger.info(f"  Page loaded: {page.title()}")

            # Strategy A: intercept automatic download triggered by OnBase
            # Some OnBase pages auto-start a download on page load
            try:
                with page.expect_download(timeout=15000) as download_info:
                    # Click any visible download/open link on the page
                    for selector in [
                        'a[href*="GetDoc"]',
                        'a[href*="Download"]',
                        'a[href*="PdfPop"]',
                        'a[href*=".xlsx"]',
                        'a[href*=".xls"]',
                        'text=Download',
                        'text=Open',
                        'text=Save',
                    ]:
                        link = page.query_selector(selector)
                        if link and link.is_visible():
                            logger.info(f"  Clicking download link: {selector}")
                            link.click()
                            break

                download = download_info.value
                downloaded_path = download.path()
                logger.info(f"  Browser download captured: {download.suggested_filename}")
            except Exception:
                # Strategy B: no auto-download, try to find a direct link
                logger.info("  No automatic download triggered. Checking page content...")

            # Strategy B: if no download was captured, try fetching page content
            # The OnBase viewer may embed the document or provide a link
            if downloaded_path is None:
                # Look for iframe or embedded content with the actual document
                for frame in page.frames:
                    frame_url = frame.url
                    if any(ext in frame_url.lower() for ext in ['.xlsx', '.xls', 'getdoc', 'pdfpop']):
                        logger.info(f"  Found document frame: {frame_url[:100]}")
                        # Fetch the frame URL directly
                        resp = page.request.get(frame_url)
                        content = resp.body()
                        is_valid, ext, reason = detect_file_type(content)
                        if is_valid:
                            browser.close()
                            logger.info(f"  Playwright success via frame: {reason}")
                            return content, ext

                # Strategy C: try triggering download via JavaScript
                try:
                    with page.expect_download(timeout=10000) as download_info:
                        page.evaluate("""() => {
                            // Try clicking the document link in OnBase viewer
                            const links = document.querySelectorAll('a');
                            for (const a of links) {
                                const href = (a.href || '').toLowerCase();
                                if (href.includes('getdoc') || href.includes('download') ||
                                    href.includes('.xls') || href.includes('pdfpop')) {
                                    a.click();
                                    return;
                                }
                            }
                            // Try the OnBase-specific download button
                            const btn = document.querySelector('[id*="download"], [id*="Download"]');
                            if (btn) btn.click();
                        }""")
                    download = download_info.value
                    downloaded_path = download.path()
                    logger.info(f"  JS-triggered download: {download.suggested_filename}")
                except Exception:
                    pass

            # Read the downloaded file
            if downloaded_path:
                with open(downloaded_path, 'rb') as f:
                    content = f.read()

                is_valid, ext, reason = detect_file_type(content)
                browser.close()

                if is_valid:
                    logger.info(f"  Playwright success: {len(content):,} bytes ({reason})")
                    return content, ext
                else:
                    raise Exception(f"Playwright downloaded file but it's not Excel: {reason}")

            browser.close()
            raise Exception("Playwright could not trigger a file download from OnBase")

        except Exception as e:
            browser.close()
            raise Exception(f"Playwright fallback failed: {e}")


def download_onbase_document(session, docid, label='document'):
    """
    Download a document from Hyland OnBase. Tries multiple strategies:
      1. Direct requests with redirect following
      2. Parse HTML response for real download URL
      3. clienttype=activex parameter
      4. Playwright headless browser (fallback for JS-rendered pages)

    Returns (content_bytes, extension) or raises on failure.
    """
    url = ONBASE_BASE_URL
    params = {'clienttype': 'html', 'docid': str(docid)}

    logger.info(f"Downloading {label} (docid={docid})...")

    # --- Strategy 1: direct request with redirects ---
    try:
        response = make_request_with_retry(session, url, params=params, timeout=180)
        content = response.content
        content_type = response.headers.get('Content-Type', '')
        content_disposition = response.headers.get('Content-Disposition', '')

        is_valid, ext, reason = detect_file_type(content, content_type, content_disposition)
        logger.info(f"  Strategy 1 (requests): {reason}")

        if is_valid:
            logger.info(f"  Downloaded {len(content):,} bytes")
            return content, ext

        # --- Strategy 2: parse HTML for download URL ---
        logger.info("  Got HTML response. Parsing for download link...")
        download_url = extract_download_url_from_html(content, response.url)

        if download_url:
            logger.info(f"  Found download link: {download_url[:100]}...")
            response = make_request_with_retry(session, download_url, timeout=180)
            content = response.content
            content_type = response.headers.get('Content-Type', '')
            content_disposition = response.headers.get('Content-Disposition', '')

            is_valid, ext, reason = detect_file_type(content, content_type, content_disposition)
            logger.info(f"  Strategy 2 (HTML parse): {reason}")

            if is_valid:
                logger.info(f"  Downloaded {len(content):,} bytes")
                return content, ext

        # --- Strategy 3: clienttype=activex ---
        logger.info("  Trying clienttype=activex...")
        params_activex = {'clienttype': 'activex', 'docid': str(docid)}
        try:
            response = make_request_with_retry(session, url, params=params_activex, timeout=180)
            content = response.content
            content_type = response.headers.get('Content-Type', '')
            content_disposition = response.headers.get('Content-Disposition', '')

            is_valid, ext, reason = detect_file_type(content, content_type, content_disposition)
            logger.info(f"  Strategy 3 (activex): {reason}")

            if is_valid:
                logger.info(f"  Downloaded {len(content):,} bytes")
                return content, ext
        except Exception as e:
            logger.debug(f"  activex attempt failed: {e}")

    except Exception as e:
        logger.warning(f"  All requests-based strategies failed: {e}")

    # --- Strategy 4: Playwright headless browser ---
    if _playwright_available():
        logger.info("  Falling back to Playwright headless browser...")
        try:
            return download_with_playwright(docid, label=label)
        except Exception as e:
            logger.error(f"  Playwright fallback failed: {e}")
    else:
        logger.info("  Playwright not installed. To enable browser fallback:")
        logger.info("    pip install playwright && playwright install chromium")

    raise Exception(
        f"Failed to download {label} (docid={docid}). "
        f"All strategies (requests + HTML parse + activex + Playwright) failed. "
        f"Try: pip install playwright && playwright install chromium"
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


def _get_output_filename(year, jurisdiction_key, manifest):
    """Build the output CSV filename for a given year and jurisdiction."""
    jurisdiction_filters = manifest.get('jurisdiction_filters', {})
    if jurisdiction_key and jurisdiction_key in jurisdiction_filters:
        display_name = jurisdiction_filters[jurisdiction_key].get('display_name', jurisdiction_key)
        return f"{year} {display_name.lower().replace(' county', '').strip()}.csv"
    return f"cdot_crash_statewide_{year}.csv"


# The unique crash identifier column used for deduplication
CUID_COLUMN = 'CUID'


def merge_with_existing(new_df, existing_path):
    """
    Merge new downloaded data with an existing CSV file using CUID as the
    deduplication key. Preserves all existing records and appends only
    genuinely new ones.

    Returns (merged_df, stats_dict) where stats_dict contains:
      - existing_count: rows in the existing file
      - new_download_count: rows in the fresh download
      - new_records: count of records added (CUID not in existing)
      - updated_records: count of records with same CUID but changed data
      - merged_count: total rows in the merged result
    """
    import pandas as pd

    existing_df = pd.read_csv(existing_path)
    stats = {
        'existing_count': len(existing_df),
        'new_download_count': len(new_df),
        'new_records': 0,
        'updated_records': 0,
        'merged_count': 0,
    }

    # Find the CUID column (case-insensitive) in both DataFrames
    cuid_col_existing = None
    for col in existing_df.columns:
        if col.strip().upper() == CUID_COLUMN:
            cuid_col_existing = col
            break

    cuid_col_new = None
    for col in new_df.columns:
        if col.strip().upper() == CUID_COLUMN:
            cuid_col_new = col
            break

    if cuid_col_existing is None or cuid_col_new is None:
        # No CUID column — can't deduplicate, fall back to full replace
        logger.warning(f"  CUID column not found. Falling back to full replacement.")
        logger.warning(f"    Existing columns: {list(existing_df.columns)[:10]}")
        logger.warning(f"    New columns: {list(new_df.columns)[:10]}")
        stats['merged_count'] = len(new_df)
        return new_df, stats

    existing_cuids = set(existing_df[cuid_col_existing].dropna().astype(str))
    new_cuids = set(new_df[cuid_col_new].dropna().astype(str))

    # New records: CUIDs in download that aren't in existing
    added_cuids = new_cuids - existing_cuids
    stats['new_records'] = len(added_cuids)

    # Check for updated records (same CUID, different data)
    common_cuids = existing_cuids & new_cuids
    if common_cuids:
        # Compare row counts — if CDOT revised a record, the new version wins
        # but we log it for audit
        existing_common = existing_df[existing_df[cuid_col_existing].astype(str).isin(common_cuids)]
        new_common = new_df[new_df[cuid_col_new].astype(str).isin(common_cuids)]

        # Quick check: row count difference in common CUIDs
        if len(existing_common) != len(new_common):
            stats['updated_records'] = abs(len(new_common) - len(existing_common))

    if stats['new_records'] == 0:
        logger.info(f"  No new records to merge (all {len(common_cuids)} CUIDs already exist)")
        stats['merged_count'] = len(existing_df)
        return existing_df, stats

    # Append only the new rows
    new_rows = new_df[new_df[cuid_col_new].astype(str).isin(added_cuids)].copy()
    merged_df = pd.concat([existing_df, new_rows], ignore_index=True)
    stats['merged_count'] = len(merged_df)

    logger.info(f"  Merge: {stats['existing_count']:,} existing + {stats['new_records']:,} new "
                f"= {stats['merged_count']:,} total")

    return merged_df, stats


def process_year(session, year, year_info, manifest, data_dir, jurisdiction_key,
                 force=False):
    """
    Download a single year's statewide file, filter to county, save as CSV.

    Merge strategy:
      - "final" years: skip download if CSV already exists (use --force to override)
      - "preliminary" years: download and merge with existing using CUID dedup
      - missing files: download fresh regardless of status

    Returns (year, success_bool, output_path_or_error).
    """
    docid = year_info['docid']
    status = year_info.get('status', 'unknown')
    label = f"CDOT Crash Listing {year}"
    if status == 'preliminary':
        label += " (preliminary)"

    # Build output filename
    filename = _get_output_filename(year, jurisdiction_key, manifest)
    output_path = data_dir / filename

    # --- Skip-if-final: don't re-download finalized years that already exist ---
    if output_path.exists() and status == 'final' and not force:
        import pandas as pd
        existing_count = len(pd.read_csv(output_path))
        logger.info(f"  {year}: SKIPPED — final data already exists "
                    f"({output_path.name}, {existing_count:,} records). Use --force to re-download.")
        return year, True, str(output_path)

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

            if df.empty:
                return year, False, f"No records for {display_name} in {year} data"
        else:
            pass  # statewide — no filter

        # --- Merge logic: merge with existing data if file exists ---
        if output_path.exists() and status == 'preliminary':
            logger.info(f"  Merging with existing {output_path.name}...")
            df, merge_stats = merge_with_existing(df, output_path)
            logger.info(f"  Merge result: +{merge_stats['new_records']} new records")
        elif output_path.exists() and force:
            logger.info(f"  Force mode: replacing existing {output_path.name}")

        # Save as CSV
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
        fips = f" (FIPS: {jur['fips']})" if jur.get('fips') else ''
        print(f"  {key:<15} {jur['display_name']}{fips}")

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
  python download_cdot_crash_data.py --force --years 2024      # Re-download even if 2024 exists
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

    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-download even for finalized years that already exist locally'
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
        year_result = process_year(session, year, year_info, manifest, data_dir, jurisdiction_key,
                                   force=args.force)
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
