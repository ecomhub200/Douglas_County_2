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

# Minimum file size to consider a download valid (100 KB)
MIN_VALID_FILE_SIZE = 100 * 1024

# Excel file magic bytes
XLSX_MAGIC = b'PK'  # ZIP-based format (xlsx)
XLS_MAGIC = b'\xd0\xcf'  # OLE2 format (xls)

# Session management
SESSION_REFRESH_INTERVAL = 3  # Re-bootstrap session every N downloads
INTER_DOWNLOAD_DELAY = 2      # Seconds to wait between downloads

# Updated browser headers (Chrome 131, current as of 2026)
BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# ──────────────────────────────────────────────────────────────────────
# STANDARDIZATION MAPPINGS
# Maps raw CDOT values to CRASH LENS universal numbered categories.
# ──────────────────────────────────────────────────────────────────────

SYSTEM_MAP = {
    'Interstate Highway': 'Interstate',
    'State Highway':      'Primary',
    'County Road':        'NonVDOT secondary',
    'City Street':        'NonVDOT secondary',
    'Frontage Road':      'Secondary',
    'Non Crash':          'NonVDOT secondary',  # Edge case: miscoded records
}

ROADWAY_DESC_MAP = {
    'Interstate':        '3. Two-Way, Divided, Positive Median Barrier',
    'Primary':           '2. Two-Way, Divided, Unprotected Median',
    'NonVDOT secondary': '1. Two-Way, Not Divided',
    'Secondary':         '2. Two-Way, Divided, Unprotected Median',
}

OWNERSHIP_MAP = {
    'Interstate Highway': '1. State Hwy Agency',
    'State Highway':      '1. State Hwy Agency',
    'Frontage Road':      '1. State Hwy Agency',
    'County Road':        '2. County Hwy Agency',
    'City Street':        '3. City or Town Hwy Agency',
    'Non Crash':          '',
}

COLLISION_TYPE_MAP = {
    'Rear-End':              '1. Rear End',
    'Broadside':             '2. Angle',
    'Head-On':               '3. Head On',
    'Sideswipe Same Direction':     '4. Sideswipe - Same Direction',
    'Sideswipe Opposite Direction': '5. Sideswipe - Opposite Direction',
    'Approach Turn':         '2. Angle',
    'Overtaking Turn':       '2. Angle',
    'Overturning/Rollover':  '8. Non-Collision',
    'Pedestrian':            '12. Ped',
    'Bicycle/Motorized Bicycle': '13. Bicycle',
    'Wild Animal':           '10. Deer/Animal',
    # Fixed objects
    'Light Pole/Utility Pole':   '9. Fixed Object - Off Road',
    'Concrete Highway Barrier':  '9. Fixed Object - Off Road',
    'Guardrail Face':            '9. Fixed Object - Off Road',
    'Guardrail End':             '9. Fixed Object - Off Road',
    'Cable Rail':                '9. Fixed Object - Off Road',
    'Tree':                      '9. Fixed Object - Off Road',
    'Fence':                     '9. Fixed Object - Off Road',
    'Sign':                      '9. Fixed Object - Off Road',
    'Curb':                      '9. Fixed Object - Off Road',
    'Embankment':                '9. Fixed Object - Off Road',
    'Ditch':                     '9. Fixed Object - Off Road',
    'Large Rocks or Boulder':    '9. Fixed Object - Off Road',
    'Electrical/Utility Box':    '9. Fixed Object - Off Road',
    'Other Fixed Object (Describe in Narrative)': '9. Fixed Object - Off Road',
    'Vehicle Debris or Cargo':   '11. Fixed Object in Road',
    'Parked Motor Vehicle':      '16. Other',
    'Other Non-Fixed Object Describe in Narrative)': '16. Other',
    'Other Non-Collision':       '8. Non-Collision',
}

WEATHER_MAP = {
    'Clear':     '1. No Adverse Condition (Clear/Cloudy)',
    'Cloudy':    '1. No Adverse Condition (Clear/Cloudy)',
    'Fog':       '3. Fog/Smog/Smoke',
    'Snow':      '4. Snow',
    'Rain':      '5. Rain',
    'Sleet or Hail':                    '6. Sleet/Hail/Freezing',
    'Freezing Rain or Freezing Drizzle':'6. Sleet/Hail/Freezing',
    'Blowing Snow':  '4. Snow',
    'Wind':          '8. Severe Crosswinds',
    'Dust':          '7. Blowing Sand/Dust',
}

LIGHT_MAP = {
    'Daylight':           '2. Daylight',
    'Dark – Lighted':     '4. Darkness - Road Lighted',
    'Dark – Unlighted':   '5. Darkness - Road Not Lighted',
    'Dark - Lighted':     '4. Darkness - Road Lighted',
    'Dark - Unlighted':   '5. Darkness - Road Not Lighted',
    'Dark-lighted':       '4. Darkness - Road Lighted',
    'Dark-unlighted':     '5. Darkness - Road Not Lighted',
    # Dawn or Dusk split by time of day in standardize_dataframe()
}

SURFACE_MAP = {
    'Dry':       '1. Dry',
    'Wet':       '2. Wet',
    'Snowy':     '3. Snow',
    'Snow':      '3. Snow',
    'Slushy':    '4. Slush',
    'Slush':     '4. Slush',
    'Icy':       '5. Ice',
    'Ice':       '5. Ice',
    'Sand/Gravel': '6. Sand/Mud/Dirt/Oil/Gravel',
    'Muddy':       '6. Sand/Mud/Dirt/Oil/Gravel',
    'Dry W/Visible Icy Road Treatment':    '1. Dry',
    'Snowy W/Visible Icy Road Treatment':  '3. Snow',
    'Icy W/Visible Icy Road Treatment':    '5. Ice',
    'Wet W/Visible Icy Road Treatment':    '2. Wet',
    'Slushy W/Visible Icy Road Treatment': '4. Slush',
    'Roto-Milled':      '16. Other',
    'Foreign Material':  '16. Other',
}

RELATION_MAP = {
    'Non-Intersection':          '8. Non-Intersection',
    'At Intersection':           '9. Within Intersection',
    'Intersection Related':      '10. Intersection Related - Within 150 Feet',
    'Driveway Access Related':   '10. Intersection Related - Within 150 Feet',
    'Ramp':                      '2. Acceleration/Deceleration Lanes',
    'Ramp-related':              '2. Acceleration/Deceleration Lanes',
    'Roundabout':                '9. Within Intersection',
    'Express/Managed/HOV Lane':  '1. Main-Line Roadway',
    'Crossover-Related ':        '10. Intersection Related - Within 150 Feet',
    'Mid-Block Crosswalk':       '9. Within Intersection',
    'Auxiliary Lane':            '2. Acceleration/Deceleration Lanes',
    'Alley Related':             '9. Within Intersection',
    'Railroad Crossing Related': '9. Within Intersection',
}

INTERSECTION_TYPE_MAP = {
    'Non-Intersection':          '1. Not at Intersection',
    'At Intersection':           '4. Four Approaches',
    'Intersection Related':      '4. Four Approaches',
    'Driveway Access Related':   '2. Two Approaches',
    'Roundabout':                '5. Roundabout',
    'Ramp':                      '1. Not at Intersection',
    'Ramp-related':              '1. Not at Intersection',
    'Express/Managed/HOV Lane':  '1. Not at Intersection',
    'Crossover-Related ':        '4. Four Approaches',
    'Mid-Block Crosswalk':       '2. Two Approaches',
    'Auxiliary Lane':            '1. Not at Intersection',
    'Alley Related':             '2. Two Approaches',
    'Railroad Crossing Related': '2. Two Approaches',
}

FIRST_HE_MAP = {
    'Front to Rear':         '20. Motor Vehicle In Transport',
    'Front to Side':         '20. Motor Vehicle In Transport',
    'Side to Side-Same Direction': '20. Motor Vehicle In Transport',
    'Side to Side-Opposite Direction': '20. Motor Vehicle In Transport',
    'Front to Front':        '20. Motor Vehicle In Transport',
    'Wild Animal':           '21. Animal',
    'Parked Motor Vehicle':  '6. Parked Vehicle',
    'Concrete Highway Barrier': '15. Concrete Traffic Barrier',
    'Overturning/Rollover':  '30. Overturn (Rollover)',
    'Sign':                  '4. Traffic Sign Support',
    'Fence':                 '8. Fence',
    'Light Pole/Utility Pole': '3. Utility Pole',
    'Curb':                  '27. Curb',
    'Tree':                  '2. Trees',
    'Vehicle Debris or Cargo': '37. Other Object (Not Fixed)',
    'Guardrail Face':        '5. Guard Rail',
    'Guardrail End':         '5. Guard Rail',
    'Cable Rail':            '5. Guard Rail',
    'Ditch':                 '14. Ditch',
    'Embankment':            '13. Embankment',
    'Large Rocks or Boulder': '24. Other Fixed Object',
    'Electrical/Utility Box': '24. Other Fixed Object',
    'Pedestrian':            '19. Ped',
    'Bicycle/Motorized Bicycle': '22. Bicycle',
    'Other Fixed Object (Describe in Narrative)': '24. Other Fixed Object',
    'Other Non-Fixed Object Describe in Narrative)': '37. Other Object (Not Fixed)',
    'Other Non-Collision':   '38. Other Non-Collision',
    'Impact Attenuator/Crash Cushion': '16. Impact Attenuator/Crash Cushion',
}

FIRST_HE_LOC_MAP = {
    'On Roadway':         '1. On Roadway',
    'On-roadway':         '1. On Roadway',
    'Ran off right side': '4. Roadside',
    'Ran off left side':  '4. Roadside',
    'Ran off "T" intersection': '4. Roadside',
    'Center median/ Island':    '3. Median',
    'Center Median/Island':     '3. Median',
    'Vehicle crossed center median into opposing lanes': '3. Median',
    'On Private Property':      '9. Outside Right-of-Way',
    'Shared-Use Path or Trail': '4. Roadside',
    'Parking Lot':              '9. Outside Right-of-Way',
}


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


def bootstrap_session(session):
    """
    Visit the OnBase DocPop landing page to establish session cookies.
    Many document management systems require a valid session before serving
    individual documents. Without this step, direct document requests
    return 403 Forbidden.
    """
    landing_url = ONBASE_BASE_URL
    logger.info("Bootstrapping OnBase session (visiting DocPop landing page)...")
    try:
        resp = session.get(landing_url, timeout=60, allow_redirects=True)
        # Accept any 2xx/3xx — we just need the cookies, not the content
        logger.info(f"  Session bootstrap: HTTP {resp.status_code}, "
                     f"cookies={list(session.cookies.keys())}")
        # Follow any meta-refresh or JS redirects embedded in the HTML
        if resp.status_code == 200:
            html = resp.text[:4000].lower()
            meta_match = re.search(
                r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\'][\d;]*\s*url=([^"\'>\s]+)',
                html
            )
            if meta_match:
                redirect_url = meta_match.group(1)
                if not redirect_url.startswith('http'):
                    from urllib.parse import urljoin
                    redirect_url = urljoin(landing_url, redirect_url)
                logger.info(f"  Following meta-refresh to {redirect_url[:80]}...")
                session.get(redirect_url, timeout=60, allow_redirects=True)
        return True
    except Exception as e:
        logger.warning(f"  Session bootstrap failed (non-fatal): {e}")
        return False


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

        # Visit the DocPop landing page first to establish session cookies,
        # then navigate to the document. This mirrors how a real user would
        # access the portal.
        try:
            logger.info(f"  Playwright: visiting DocPop landing page for session...")
            page.goto(ONBASE_BASE_URL, wait_until='networkidle', timeout=30000)
            logger.info(f"  Playwright: session established, page title: {page.title()}")
        except Exception as e:
            logger.warning(f"  Playwright: landing page visit failed (continuing): {e}")

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
      1b. Re-bootstrap session and retry (if strategy 1 got 403)
      2. Parse HTML response for real download URL
      3. clienttype=activex parameter
      4. Playwright headless browser (fallback for JS-rendered pages)

    Returns (content_bytes, extension) or raises on failure.
    """
    url = ONBASE_BASE_URL
    params = {'clienttype': 'html', 'docid': str(docid)}

    logger.info(f"Downloading {label} (docid={docid})...")

    html_content = None  # Saved for strategy 2 if strategy 1 returns HTML
    response_url = None

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

        # Not a valid file — save HTML for strategy 2
        html_content = content
        response_url = response.url

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else 'unknown'
        logger.warning(f"  Strategy 1 failed: HTTP {status}")

        # --- Strategy 1b: re-bootstrap session and retry on 403 ---
        if e.response is not None and e.response.status_code == 403:
            logger.info("  Got 403 — re-bootstrapping session and retrying...")
            bootstrap_session(session)
            try:
                response = make_request_with_retry(session, url, params=params, timeout=180)
                content = response.content
                content_type = response.headers.get('Content-Type', '')
                content_disposition = response.headers.get('Content-Disposition', '')

                is_valid, ext, reason = detect_file_type(content, content_type, content_disposition)
                logger.info(f"  Strategy 1b (post-bootstrap): {reason}")

                if is_valid:
                    logger.info(f"  Downloaded {len(content):,} bytes")
                    return content, ext

                html_content = content
                response_url = response.url
            except Exception as e2:
                logger.warning(f"  Strategy 1b also failed: {e2}")
    except Exception as e:
        logger.warning(f"  Strategy 1 failed: {e}")

    # --- Strategy 2: parse HTML for download URL ---
    if html_content is not None:
        logger.info("  Got HTML response. Parsing for download link...")
        try:
            download_url = extract_download_url_from_html(html_content, response_url or url)
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
            else:
                logger.info("  Strategy 2: no download link found in HTML")
        except Exception as e:
            logger.warning(f"  Strategy 2 failed: {e}")

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
        logger.warning(f"  Strategy 3 (activex) failed: {e}")

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


def _safe_get(row, col):
    """Safely get a column value from a DataFrame row, returning '' for missing/NaN."""
    val = row.get(col, '')
    if val is None or (isinstance(val, float) and str(val) == 'nan'):
        return ''
    return str(val).strip()


def _safe_int(val, default=0):
    """Convert a value to int, returning default for non-numeric."""
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def _check_any_match(row, columns, match_values):
    """Check if any of the given columns contain any of the match values."""
    for col in columns:
        val = _safe_get(row, col)
        if val and any(m.lower() in val.lower() for m in match_values):
            return True
    return False


def _check_positive_flags(row, columns, positive_values):
    """Check if any column has a positive value (exact match, case-insensitive)."""
    for col in columns:
        val = _safe_get(row, col)
        if val and val.lower() in [pv.lower() for pv in positive_values]:
            return True
    return False


def _check_age_range(row, columns, min_age, max_age):
    """Check if any driver age falls within the given range."""
    for col in columns:
        age = _safe_int(_safe_get(row, col), -1)
        if min_age <= age <= max_age:
            return True
    return False


def derive_severity(row):
    """Derive KABCO severity from injury count columns."""
    if _safe_int(_safe_get(row, 'Injury 04')) > 0:
        return 'K'
    if _safe_int(_safe_get(row, 'Injury 03')) > 0:
        return 'A'
    if _safe_int(_safe_get(row, 'Injury 02')) > 0:
        return 'B'
    if _safe_int(_safe_get(row, 'Injury 01')) > 0:
        return 'C'
    return 'O'


def derive_light_condition(row):
    """Map lighting condition, splitting Dawn/Dusk by time of day."""
    raw = _safe_get(row, 'Lighting Conditions')
    if raw in LIGHT_MAP:
        return LIGHT_MAP[raw]

    # Handle Dawn or Dusk — split by crash time
    if 'dawn' in raw.lower() or 'dusk' in raw.lower():
        time_str = _safe_get(row, 'Crash Time')
        try:
            # Parse HH:MM:SS or HHMM
            hour = int(time_str.replace(':', '')[:2])
            return '1. Dawn' if hour < 12 else '3. Dusk'
        except (ValueError, IndexError):
            return '3. Dusk'

    return raw  # Pass through unknown values


def derive_alignment(row):
    """Build roadway alignment from curves + grade."""
    curves = _safe_get(row, 'Road Contour Curves')
    grade = _safe_get(row, 'Road Contour Grade')
    is_curve = bool(curves and 'Curve' in curves)
    is_grade = bool(grade and grade.lower() not in ('', 'level'))
    if is_curve and is_grade:
        return '4. Grade - Curve'
    elif is_grade:
        return '3. Grade - Straight'
    elif is_curve:
        return '2. Curve - Level'
    return '1. Straight - Level'


def build_route_name(row):
    """Build a route name from System Code + Rd_Number + Location 1."""
    system = _safe_get(row, 'System Code')
    location1 = _safe_get(row, 'Location 1')

    # For interstates/state highways, use Location 1 (e.g., "I-25", "CO-83")
    if system in ('Interstate Highway', 'State Highway', 'Frontage Road') and location1:
        return location1

    # For local roads, use Location 1 (street name)
    if location1:
        return location1

    # Fallback to road number
    rd_num = _safe_get(row, 'Rd_Number')
    return rd_num if rd_num else ''


def build_node_id(row):
    """Build intersection node ID from Location 1 + Location 2."""
    loc1 = _safe_get(row, 'Location 1')
    loc2 = _safe_get(row, 'Location 2')

    # Only build a node for intersection-type records
    road_desc = _safe_get(row, 'Road Description')
    if road_desc in ('Non-Intersection',) or not loc2:
        return ''

    # Skip milepost-style Location 2 values (e.g., "MM 190")
    if loc2.startswith('MM ') or loc2.endswith('ME') or loc2.endswith('MW'):
        return ''

    return f'{loc2} & {loc1}' if loc2 and loc1 else ''


def format_military_time(time_str):
    """Convert 'HH:MM:SS' or 'H:MM:SS' to 4-digit military time 'HHMM'."""
    if not time_str:
        return ''
    cleaned = time_str.replace(':', '')
    # Take first 4 digits
    digits = ''.join(c for c in cleaned if c.isdigit())
    return digits[:4].zfill(4) if digits else ''


def standardize_dataframe(df, source_file=''):
    """
    Transform a raw CDOT DataFrame into the CRASH LENS standardized format.
    Applies column mapping, derives computed fields, and preserves raw values
    as _co_* columns for reference.
    """
    import pandas as pd

    logger.info(f"  Standardizing {len(df):,} rows...")

    # Clean column names (strip BOM, whitespace)
    df.columns = [col.lstrip('\ufeff').strip() for col in df.columns]

    rows = []
    for _, raw_row in df.iterrows():
        system_code = _safe_get(raw_row, 'System Code')
        system = SYSTEM_MAP.get(system_code, system_code)
        crash_type = _safe_get(raw_row, 'Crash Type')
        mhe = _safe_get(raw_row, 'MHE')
        road_desc = _safe_get(raw_row, 'Road Description')
        first_he = _safe_get(raw_row, 'First HE')
        location = _safe_get(raw_row, 'Location')

        # Derive severity from injury counts
        severity = derive_severity(raw_row)

        # Boolean flag derivations
        ped = 'Yes' if _check_any_match(raw_row,
            ['TU-1 NM Type', 'TU-2 NM Type'], ['Pedestrian']) else 'No'
        bike = 'Yes' if _check_any_match(raw_row,
            ['TU-1 NM Type', 'TU-2 NM Type'], ['Bicycle']) else 'No'
        alcohol = 'Yes' if _check_positive_flags(raw_row,
            ['TU-1 Alcohol Suspected', 'TU-2 Alcohol Suspected'],
            ['Yes - SFST', 'Yes - BAC', 'Yes - Both', 'Yes - Observation',
             'Yes - Preliminary Breath Test', 'Yes - Blood Test',
             'Yes SFST', 'Yes BAC', 'Yes Both', 'Yes Observation']) else 'No'
        speed = 'Yes' if _check_any_match(raw_row,
            ['TU-1 Driver Action', 'TU-2 Driver Action'],
            ['Too Fast for Conditions', 'Exceeded Speed Limit']) else 'No'
        hitrun = 'Yes' if _check_positive_flags(raw_row,
            ['TU-1 Hit And Run', 'TU-2 Hit And Run'],
            ['TRUE', 'True', 'true']) else 'No'
        motorcycle = 'Yes' if _check_any_match(raw_row,
            ['TU-1 Type', 'TU-2 Type'], ['Motorcycle']) else 'No'
        night = 'Yes' if _safe_get(raw_row, 'Lighting Conditions').lower().startswith('dark') else 'No'
        distracted = 'Yes' if _check_any_match(raw_row,
            ['TU-1 Driver Action', 'TU-2 Driver Action',
             'TU-1 Human Contributing Factor', 'TU-2 Human Contributing Factor'],
            ['Distracted', 'Cell Phone', 'Inattention', 'Inattentive']) else 'No'
        drowsy = 'Yes' if _check_any_match(raw_row,
            ['TU-1 Human Contributing Factor', 'TU-2 Human Contributing Factor'],
            ['Asleep', 'Fatigued', 'Drowsy']) else 'No'
        drug = 'Yes' if _check_positive_flags(raw_row,
            ['TU-1  Marijuana Suspected', 'TU-2 Marijuana Suspected',
             'TU-1 Other Drugs Suspected ', 'TU-2 Other Drugs Suspected '],
            ['Yes - Observation', 'Yes - SFST', 'Yes - Both', 'Yes - Test Results',
             'Marijuana Suspected', 'Yes Observation']) else 'No'
        young = 'Yes' if _check_age_range(raw_row, ['TU-1 Age', 'TU-2 Age'], 16, 20) else 'No'
        senior = 'Yes' if _check_age_range(raw_row, ['TU-1 Age', 'TU-2 Age'], 65, 999) else 'No'
        unrestrained = 'Yes' if _check_any_match(raw_row,
            ['TU-1 Safety restraint Use', 'TU-2 Safety restraint Use'],
            ['Not Used', 'Improperly Used']) else 'No'

        # Map collision type: try Crash Type first, then MHE
        collision = COLLISION_TYPE_MAP.get(crash_type,
                    COLLISION_TYPE_MAP.get(mhe, '16. Other'))

        row = {
            'Document Nbr':            _safe_get(raw_row, 'CUID'),
            'Crash Date':              _safe_get(raw_row, 'Crash Date'),
            'Crash Year':              _safe_get(raw_row, 'Crash Date').split('/')[-1] if '/' in _safe_get(raw_row, 'Crash Date') else '',
            'Crash Military Time':     format_military_time(_safe_get(raw_row, 'Crash Time')),
            'Crash Severity':          severity,
            'K_People':                _safe_int(_safe_get(raw_row, 'Injury 04')),
            'A_People':                _safe_int(_safe_get(raw_row, 'Injury 03')),
            'B_People':                _safe_int(_safe_get(raw_row, 'Injury 02')),
            'C_People':                _safe_int(_safe_get(raw_row, 'Injury 01')),
            'Collision Type':          collision,
            'Weather Condition':       WEATHER_MAP.get(_safe_get(raw_row, 'Weather Condition'), _safe_get(raw_row, 'Weather Condition')),
            'Light Condition':         derive_light_condition(raw_row),
            'Roadway Surface Condition': SURFACE_MAP.get(_safe_get(raw_row, 'Road Condition'), _safe_get(raw_row, 'Road Condition')),
            'Roadway Alignment':       derive_alignment(raw_row),
            'Roadway Description':     ROADWAY_DESC_MAP.get(system, ''),
            'Intersection Type':       INTERSECTION_TYPE_MAP.get(road_desc, road_desc),
            'Relation To Roadway':     RELATION_MAP.get(road_desc, road_desc),
            'RTE Name':                build_route_name(raw_row),
            'SYSTEM':                  system,
            'Node':                    build_node_id(raw_row),
            'RNS MP':                  _safe_get(raw_row, 'Link') if _safe_get(raw_row, 'Link') not in ('AT', '') else _safe_get(raw_row, 'Rd_Section'),
            'x':                       _safe_get(raw_row, 'Longitude'),
            'y':                       _safe_get(raw_row, 'Latitude'),
            'Physical Juris Name':     _safe_get(raw_row, 'County'),
            'Pedestrian?':             ped,
            'Bike?':                   bike,
            'Alcohol?':                alcohol,
            'Speed?':                  speed,
            'Hitrun?':                 hitrun,
            'Motorcycle?':             motorcycle,
            'Night?':                  night,
            'Distracted?':             distracted,
            'Drowsy?':                 drowsy,
            'Drug Related?':           drug,
            'Young?':                  young,
            'Senior?':                 senior,
            'Unrestrained?':           unrestrained,
            'School Zone':             _safe_get(raw_row, 'School Zone'),
            'Work Zone Related':       _safe_get(raw_row, 'Construction Zone'),
            'Traffic Control Type':    '',
            'Traffic Control Status':  '',
            'Functional Class':        '',
            'Area Type':               '',
            'Facility Type':           '',
            'Ownership':               OWNERSHIP_MAP.get(system_code, ''),
            'First Harmful Event':     FIRST_HE_MAP.get(first_he, FIRST_HE_MAP.get(mhe, first_he)),
            'First Harmful Event Loc': FIRST_HE_LOC_MAP.get(location, location),
            'Vehicle Count':           _safe_int(_safe_get(raw_row, 'Total Vehicles')),
            'Persons Injured':         _safe_int(_safe_get(raw_row, 'Number Injured')),
            'Pedestrians Killed':      0,
            'Pedestrians Injured':     0,
            # Source metadata
            '_source_state':           'colorado',
            # Preserved Colorado-specific raw values
            '_co_system_code':         system_code,
            '_co_agency_id':           _safe_get(raw_row, 'Agency Id'),
            '_co_rd_number':           _safe_get(raw_row, 'Rd_Number'),
            '_co_location1':           _safe_get(raw_row, 'Location 1'),
            '_co_location2':           _safe_get(raw_row, 'Location 2'),
            '_co_city':                _safe_get(raw_row, 'City'),
            '_co_total_vehicles':      _safe_int(_safe_get(raw_row, 'Total Vehicles')),
            '_co_mhe':                 mhe,
            '_co_crash_type':          crash_type,
            '_co_link':                _safe_get(raw_row, 'Link'),
            '_co_second_he':           _safe_get(raw_row, 'Second HE'),
            '_co_third_he':            _safe_get(raw_row, 'Third HE'),
            '_co_wild_animal':         _safe_get(raw_row, 'Wild Animal'),
            '_co_secondary_crash':     _safe_get(raw_row, 'Secondary Crash'),
            '_co_weather2':            _safe_get(raw_row, 'Weather Condition 2'),
            '_co_lane_position':       _safe_get(raw_row, 'Lane Position'),
            '_co_injury00_uninjured':  _safe_int(_safe_get(raw_row, 'Injury 00')),
            '_co_tu1_direction':       _safe_get(raw_row, 'TU-1 Direction'),
            '_co_tu1_movement':        _safe_get(raw_row, 'TU-1 Movement'),
            '_co_tu1_vehicle_type':    _safe_get(raw_row, 'TU-1 Type'),
            '_co_tu1_speed_limit':     _safe_get(raw_row, 'TU-1 Speed Limit'),
            '_co_tu1_estimated_speed': _safe_get(raw_row, 'TU-1 Estimated Speed'),
            '_co_tu1_stated_speed':    _safe_get(raw_row, 'TU-1 Speed'),
            '_co_tu1_driver_action':   _safe_get(raw_row, 'TU-1 Driver Action'),
            '_co_tu1_human_factor':    _safe_get(raw_row, 'TU-1 Human Contributing Factor'),
            '_co_tu1_age':             _safe_get(raw_row, 'TU-1 Age'),
            '_co_tu1_sex':             _safe_get(raw_row, 'TU-1 Sex '),
            '_co_tu2_direction':       _safe_get(raw_row, 'TU-2 Direction'),
            '_co_tu2_movement':        _safe_get(raw_row, 'TU-2 Movement'),
            '_co_tu2_vehicle_type':    _safe_get(raw_row, 'TU-2 Type'),
            '_co_tu2_speed_limit':     _safe_get(raw_row, 'TU-2 Speed Limit'),
            '_co_tu2_estimated_speed': _safe_get(raw_row, 'TU-2 Estimated Speed'),
            '_co_tu2_stated_speed':    _safe_get(raw_row, 'TU-2 Speed'),
            '_co_tu2_driver_action':   _safe_get(raw_row, 'TU-2 Driver Action'),
            '_co_tu2_human_factor':    _safe_get(raw_row, 'TU-2 Human Contributing Factor'),
            '_co_tu2_age':             _safe_get(raw_row, 'TU-2 Age'),
            '_co_tu2_sex':             _safe_get(raw_row, 'TU-2 Sex'),
            '_co_nm1_type':            _safe_get(raw_row, 'TU-1 NM Type'),
            '_co_nm1_age':             _safe_get(raw_row, 'TU-1 NM Age '),
            '_co_nm1_sex':             _safe_get(raw_row, 'TU-1 NM Sex '),
            '_co_nm1_action':          _safe_get(raw_row, 'TU-1 NM Action '),
            '_co_nm1_movement':        _safe_get(raw_row, 'TU-1 NM Movement'),
            '_co_nm1_location':        _safe_get(raw_row, 'TU-1 NM Location '),
            '_co_nm1_facility':        _safe_get(raw_row, 'TU-1 NM Facility Available'),
            '_co_nm1_contributing_factor': _safe_get(raw_row, 'TU-1 NM Human Contributing Factor '),
            '_co_nm2_type':            _safe_get(raw_row, 'TU-2 NM Type'),
            '_co_nm2_age':             _safe_get(raw_row, 'TU-2 NM Age '),
            '_co_nm2_sex':             _safe_get(raw_row, 'TU-2 NM Sex '),
            '_co_nm2_action':          _safe_get(raw_row, 'TU-2 NM Action '),
            '_co_nm2_movement':        _safe_get(raw_row, 'TU-2 NM Movement'),
            '_co_nm2_location':        _safe_get(raw_row, 'TU-2 NM Location '),
            '_co_nm2_facility':        _safe_get(raw_row, 'TU-2 NM Facility Available'),
            '_co_nm2_contributing_factor': _safe_get(raw_row, 'TU-2 NM Human Contributing Factor '),
            '_source_file':            source_file,
        }
        rows.append(row)

    result = pd.DataFrame(rows)
    logger.info(f"  Standardized: {len(result):,} rows, {len(result.columns)} columns")
    return result


def generate_road_variants(standardized_df, data_dir, jurisdiction_key):
    """
    Generate road-type filtered CSV variants from the standardized DataFrame.
    Produces: all_roads, county_roads, no_interstate, and crashes.csv.
    """
    import pandas as pd
    import shutil

    # Save standardized (all data including interstate)
    std_path = data_dir / f'{jurisdiction_key}_standardized.csv'
    standardized_df.to_csv(std_path, index=False)
    logger.info(f"  Saved: {std_path.name} ({len(standardized_df):,} rows)")

    # All roads = same as standardized (excludes nothing)
    all_roads_path = data_dir / f'{jurisdiction_key}_all_roads.csv'
    standardized_df.to_csv(all_roads_path, index=False)
    logger.info(f"  Saved: {all_roads_path.name} ({len(standardized_df):,} rows)")

    # County roads only (NonVDOT secondary)
    county_mask = standardized_df['SYSTEM'] == 'NonVDOT secondary'
    county_df = standardized_df[county_mask]
    county_path = data_dir / f'{jurisdiction_key}_county_roads.csv'
    county_df.to_csv(county_path, index=False)
    logger.info(f"  Saved: {county_path.name} ({len(county_df):,} rows)")

    # No interstate (everything except Interstate)
    no_int_mask = standardized_df['SYSTEM'] != 'Interstate'
    no_int_df = standardized_df[no_int_mask]
    no_int_path = data_dir / f'{jurisdiction_key}_no_interstate.csv'
    no_int_df.to_csv(no_int_path, index=False)
    logger.info(f"  Saved: {no_int_path.name} ({len(no_int_df):,} rows)")

    # crashes.csv (copy of standardized for compatibility)
    crashes_path = data_dir / 'crashes.csv'
    standardized_df.to_csv(crashes_path, index=False)
    logger.info(f"  Saved: crashes.csv ({len(standardized_df):,} rows)")

    return {
        'standardized': str(std_path),
        'all_roads': str(all_roads_path),
        'county_roads': str(county_path),
        'no_interstate': str(no_int_path),
        'crashes': str(crashes_path),
    }


def post_process(data_dir, jurisdiction_key, manifest):
    """
    Post-processing pipeline: combine all annual CSVs, standardize columns,
    and generate road-filtered variants for R2 upload.
    """
    import pandas as pd

    logger.info("")
    logger.info("=" * 60)
    logger.info("POST-PROCESSING: Standardization Pipeline")
    logger.info("=" * 60)

    # Find all raw annual CSVs
    annual_csvs = sorted(data_dir.glob('20*.csv'))
    # Filter to only raw annual files (not processed outputs)
    annual_csvs = [f for f in annual_csvs
                   if not any(suffix in f.name for suffix in
                              ['standardized', 'all_roads', 'county_roads',
                               'no_interstate', 'merged_raw', 'crash export'])]

    if not annual_csvs:
        logger.warning("  No raw annual CSVs found in data directory. Skipping standardization.")
        return None

    logger.info(f"  Found {len(annual_csvs)} annual CSV files:")
    for f in annual_csvs:
        logger.info(f"    {f.name}")

    # Combine all annual CSVs
    frames = []
    for csv_path in annual_csvs:
        try:
            df = pd.read_csv(csv_path)
            # Clean BOM from first column
            df.columns = [col.lstrip('\ufeff').strip() for col in df.columns]
            logger.info(f"  Read {csv_path.name}: {len(df):,} rows")
            frames.append((csv_path.name, df))
        except Exception as e:
            logger.warning(f"  Failed to read {csv_path.name}: {e}")

    if not frames:
        logger.error("  No annual CSVs could be read. Aborting standardization.")
        return None

    # Standardize each year's data and combine
    std_frames = []
    for source_file, df in frames:
        std_df = standardize_dataframe(df, source_file=source_file)
        std_frames.append(std_df)

    # Combine and deduplicate by Document Nbr (CUID)
    combined = pd.concat(std_frames, ignore_index=True)
    original_count = len(combined)

    if 'Document Nbr' in combined.columns:
        combined = combined.drop_duplicates(subset='Document Nbr', keep='last')
        if len(combined) < original_count:
            logger.info(f"  Deduplicated: {original_count:,} → {len(combined):,} rows "
                        f"({original_count - len(combined):,} duplicates removed)")

    # Sort by date descending
    combined = combined.sort_values(['Crash Year', 'Crash Date'], ascending=[False, False])
    combined = combined.reset_index(drop=True)

    logger.info(f"  Combined standardized data: {len(combined):,} rows")

    # Generate road-filtered variants
    logger.info("  Generating road-filtered variants...")
    paths = generate_road_variants(combined, data_dir, jurisdiction_key)

    logger.info("  Standardization pipeline complete!")
    return paths


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


def preflight_check(session):
    """
    Verify OnBase is accessible before starting batch downloads.
    Returns True if reachable, False otherwise.
    """
    logger.info("Preflight check: verifying OnBase is accessible...")
    try:
        resp = session.get(ONBASE_BASE_URL, timeout=30, allow_redirects=True)
        if resp.status_code == 200:
            logger.info(f"  OnBase is reachable (HTTP 200, {len(resp.content):,} bytes)")
            return True
        else:
            logger.warning(f"  OnBase returned HTTP {resp.status_code}")
            return True  # Non-200 but reachable; let the download logic handle it
    except Exception as e:
        logger.error(f"  OnBase is not reachable: {e}")
        logger.error("  Downloads will likely fail. Check network connectivity.")
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

    parser.add_argument(
        '--standardize-only',
        action='store_true',
        help='Skip downloads; only run standardization on existing raw CSVs'
    )

    parser.add_argument(
        '--no-standardize',
        action='store_true',
        help='Skip the post-download standardization step'
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

    # Handle --standardize-only (skip downloads, just re-process existing CSVs)
    if args.standardize_only:
        logger.info("--- Standardize-only mode: skipping downloads ---")
        post_result = post_process(data_dir, jurisdiction_key, manifest)
        if post_result:
            logger.info("Standardization complete!")
            return 0
        else:
            logger.error("Standardization failed.")
            return 1

    # Create session (reuse across all downloads for connection pooling)
    session = create_session_with_retries()

    # Bootstrap session — visit the DocPop landing page to establish cookies.
    # OnBase returns 403 for direct document requests without a valid session.
    bootstrap_session(session)

    # Preflight health check
    if not preflight_check(session):
        logger.warning("OnBase may be unreachable. Proceeding anyway...")

    # Download data dictionaries first (unless skipped)
    if not args.no_dict:
        logger.info("--- Downloading data dictionaries ---")
        for range_key, dict_info in manifest.get('data_dictionaries', {}).items():
            download_data_dictionary(session, dict_info, data_dir)

    # Download and process each year
    results = []
    download_count = 0
    logger.info(f"--- Downloading {len(years_to_download)} year(s) ---")

    for year in sorted(years_to_download.keys(), reverse=True):
        year_info = years_to_download[year]

        # Re-bootstrap session periodically to prevent stale cookies
        if download_count > 0 and download_count % SESSION_REFRESH_INTERVAL == 0:
            logger.info("  Refreshing OnBase session...")
            bootstrap_session(session)

        # Inter-download delay to avoid rate limiting
        if download_count > 0:
            logger.info(f"  Waiting {INTER_DOWNLOAD_DELAY}s between downloads...")
            time.sleep(INTER_DOWNLOAD_DELAY)

        year_result = process_year(session, year, year_info, manifest, data_dir, jurisdiction_key,
                                   force=args.force)
        results.append(year_result)
        download_count += 1

    # Print download summary
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

    # Run standardization pipeline (unless skipped or all downloads failed)
    if not args.no_standardize and successes:
        post_result = post_process(data_dir, jurisdiction_key, manifest)
        if not post_result:
            logger.warning("Standardization had issues but downloads succeeded.")

    return 1 if failures and not successes else 0


if __name__ == "__main__":
    sys.exit(main())
