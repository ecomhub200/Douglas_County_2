#!/usr/bin/env python3
"""
CRASH LENS — Virginia Crash Data Downloader (v9)

Downloads crash data from virginiaroads.org (Virginia Roads Open Data Hub).

Three download methods (tried in order):
  1. HUB CSV EXPORT — Playwright clicks "Download CSV" on the Hub page (primary)
  2. DIRECT REST API — Plain HTTP requests to ArcGIS FeatureServer (fast, no browser)
  3. PLAYWRIGHT FEATURESERVER — Browser-routed FeatureServer queries (legacy fallback)

As of March 2026, VDOT's FeatureServer endpoints require authentication tokens,
so the Hub CSV export via Playwright is now the primary download method.

Supports INCREMENTAL downloads using OBJECTID high-water mark:
  - Tracks max OBJECTID from previous download in a manifest file
  - On incremental runs, only fetches records with OBJECTID > last_max
  - Merges delta into existing statewide CSV, deduplicates by Document Nbr
  - Auto-detects OBJECTID resets and falls back to full download
  - Quarterly full refresh recommended to catch edits/deletions

Strategy:
  1. Try Hub CSV export (Playwright clicks download button on Hub page)
  2. If Hub fails, try direct REST API (requests library)
  3. If REST fails, fall back to Playwright browser-routed FeatureServer queries
  4. Check manifest for last OBJECTID (incremental) or paginate all (full)
  5. Stream results to CSV on disk
  6. Merge delta into existing CSV if incremental

Usage:
    # Incremental (default — fast, only new records):
    python download_virginia_crash_data.py --data-dir data --jurisdiction henrico

    # Full download (all records — use quarterly or with --force):
    python download_virginia_crash_data.py --data-dir data --full --jurisdiction henrico

    # Force full re-download:
    python download_virginia_crash_data.py --data-dir data --force --jurisdiction henrico

    # Force Playwright Hub download only:
    python download_virginia_crash_data.py --data-dir data --playwright-only --jurisdiction henrico

    # Skip Hub export, use only FeatureServer methods:
    python download_virginia_crash_data.py --data-dir data --rest-only --jurisdiction henrico
"""

import argparse
import csv
import gzip
import json
import logging
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('virginia-download')

SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = SCRIPT_DIR / 'config.json'

HUB_URL = 'https://www.virginiaroads.org/datasets/VDOT::full-crash-1/explore?layer=0'

# Hub dataset pages (for CSV export via Playwright download button)
HUB_DATASET_PAGES = [
    'https://www.virginiaroads.org/datasets/VDOT::full-crash-1/about',
    'https://www.virginiaroads.org/datasets/VDOT::crashdata-basic-1/about',
    'https://virginiaroads-vdot.opendata.arcgis.com/datasets/VDOT::full-crash-1/about',
    'https://virginiaroads-vdot.opendata.arcgis.com/datasets/VDOT::crashdata-basic-1/about',
]

# Known FeatureServer URLs (may require auth tokens as of March 2026)
KNOWN_FEATURE_SERVERS = [
    'https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/Full_Crash/FeatureServer/0',
    'https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/CrashData_Basic/FeatureServer/0',
    'https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/CrashData_Basic_Updated/FeatureServer/0',
]

# Minimum acceptable record count for a valid statewide download
MIN_STATEWIDE_RECORDS = 50000

CACHE_PATH = SCRIPT_DIR / '.virginia_featureserver_cache.json'
MANIFEST_FILENAME = 'virginia_download_manifest.json'

# Columns used for deduplication (in priority order)
DEDUP_PRIMARY_COL = 'DOCUMENT_NBR'  # ArcGIS field name (raw from API)
DEDUP_FALLBACK_COLS = ['Document_Nbr', 'Document Nbr', 'document_nbr']


# ============================================================================
# Download manifest — tracks OBJECTID high-water mark for incremental mode
# ============================================================================

def load_manifest(data_dir):
    """Load the download manifest with last OBJECTID, count, and timestamp."""
    path = Path(data_dir) / MANIFEST_FILENAME
    if path.exists():
        try:
            data = json.loads(path.read_text())
            logger.info(f"  Manifest loaded: max_objectid={data.get('max_objectid')}, "
                        f"total_count={data.get('total_count'):,}, "
                        f"date={data.get('download_date')}")
            return data
        except Exception as e:
            logger.warning(f"  Manifest load failed: {e}")
    return None


def save_manifest(data_dir, max_objectid, total_count, record_count, mode,
                  service_url=None, delta_count=0):
    """Save download manifest after successful download."""
    path = Path(data_dir) / MANIFEST_FILENAME
    data = {
        'max_objectid': max_objectid,
        'total_count': total_count,
        'record_count': record_count,
        'download_date': datetime.now().isoformat(),
        'download_mode': mode,
        'delta_count': delta_count,
        'service_url': service_url or '',
    }
    path.write_text(json.dumps(data, indent=2))
    logger.info(f"  Manifest saved: max_objectid={max_objectid}, total={total_count:,}")


def find_doc_nbr_column(fieldnames):
    """Find the Document Number column name from available fields."""
    for col in [DEDUP_PRIMARY_COL] + DEDUP_FALLBACK_COLS:
        if col in fieldnames:
            return col
    # Case-insensitive search
    for col in fieldnames:
        if 'document' in col.lower() and 'nbr' in col.lower():
            return col
    return None


def load_cached_url():
    if CACHE_PATH.exists():
        try:
            data = json.loads(CACHE_PATH.read_text())
            url = data.get('url', '')
            if url:
                logger.info(f"  Cached: {url}")
                return url
        except Exception:
            pass
    return None


def save_cached_url(url):
    try:
        CACHE_PATH.write_text(json.dumps({
            'url': url, 'discovered': datetime.now().isoformat(),
        }))
    except Exception:
        pass


# ============================================================================
# Hub CSV Export download (PRIMARY method — Playwright clicks download button)
# ============================================================================

def download_via_hub_export(output_path, headless=True, timeout_minutes=30):
    """
    Download crash data CSV from Virginia Roads Open Data Hub using Playwright.

    Navigates to the Hub dataset page and clicks the CSV download button.
    This bypasses FeatureServer token requirements because the Hub generates
    its own CSV export from cached/replicated data.

    The ArcGIS Hub "Download" button triggers a server-side CSV generation
    that is served as a file download — completely separate from the
    FeatureServer query API.

    Returns:
        dict with {success, total_written, max_objectid, total_server_count, service_url}
        or False on failure.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return False

    import tempfile

    logger.info("=" * 50)
    logger.info("  HUB CSV EXPORT via Playwright")
    logger.info("=" * 50)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )
            # Use a temp directory for Playwright downloads
            download_dir = tempfile.mkdtemp(prefix='va_hub_dl_')
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                           '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                accept_downloads=True,
            )
            page = context.new_page()

            downloaded_path = None

            for hub_url in HUB_DATASET_PAGES:
                logger.info(f"  Trying Hub page: {hub_url}")
                try:
                    page.goto(hub_url, wait_until='networkidle', timeout=60000)
                    page.wait_for_timeout(3000)
                    title = page.title()
                    logger.info(f"  Page loaded: {title}")

                    # Check if page loaded successfully (not 404 or error)
                    if '404' in title.lower() or 'not found' in title.lower():
                        logger.info(f"  Page not found, trying next...")
                        continue

                    # Strategy 1: Look for the Hub "Download" action/button
                    downloaded_path = _try_hub_download_button(page, download_dir, timeout_minutes)
                    if downloaded_path:
                        break

                    # Strategy 2: Try the "I want to use this" / API download panel
                    downloaded_path = _try_hub_api_download(page, download_dir, timeout_minutes)
                    if downloaded_path:
                        break

                except Exception as e:
                    logger.warning(f"  Hub page failed: {e}")
                    continue

            browser.close()

            if not downloaded_path or not os.path.exists(downloaded_path):
                logger.error("  Hub CSV export failed — no file downloaded")
                # Clean up temp dir
                try:
                    shutil.rmtree(download_dir, ignore_errors=True)
                except Exception:
                    pass
                return False

            # Validate the downloaded file
            file_size = os.path.getsize(downloaded_path)
            logger.info(f"  Downloaded file: {downloaded_path} ({file_size / (1024*1024):.1f} MB)")

            if file_size < 1000:
                logger.error(f"  Downloaded file too small ({file_size} bytes)")
                shutil.rmtree(download_dir, ignore_errors=True)
                return False

            # Check if it's a valid CSV (not HTML error page)
            with open(downloaded_path, 'r', encoding='utf-8-sig', errors='replace') as f:
                first_line = f.readline(2000)
            if '<html' in first_line.lower() or '<HTML' in first_line:
                logger.error("  Downloaded file is HTML (error page), not CSV")
                shutil.rmtree(download_dir, ignore_errors=True)
                return False

            # Handle GeoJSON download — convert to CSV if needed
            if downloaded_path.endswith('.geojson') or first_line.strip().startswith('{'):
                logger.info("  Downloaded GeoJSON — converting to CSV...")
                csv_from_geojson = _geojson_to_csv(downloaded_path, output_path)
                shutil.rmtree(download_dir, ignore_errors=True)
                if csv_from_geojson:
                    return csv_from_geojson
                return False

            # Move CSV to target location
            shutil.move(downloaded_path, output_path)
            shutil.rmtree(download_dir, ignore_errors=True)

            # Count records and find max OBJECTID
            total_written = 0
            max_objectid = 0
            with open(output_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    total_written += 1
                    oid = row.get('OBJECTID') or row.get('objectid') or row.get('FID') or ''
                    try:
                        oid_int = int(oid)
                        if oid_int > max_objectid:
                            max_objectid = oid_int
                    except (ValueError, TypeError):
                        pass

            logger.info(f"  Hub CSV export success: {total_written:,} records")
            logger.info(f"  Max OBJECTID: {max_objectid:,}")

            if total_written < MIN_STATEWIDE_RECORDS:
                logger.warning(f"  Only {total_written:,} records (expected {MIN_STATEWIDE_RECORDS:,}+)")

            return {
                'success': True,
                'total_written': total_written,
                'max_objectid': max_objectid,
                'total_server_count': total_written,
                'service_url': 'hub_csv_export',
            }

    except Exception as e:
        logger.error(f"  Hub export fatal error: {e}")
        import traceback
        traceback.print_exc()
        return False


def _try_hub_download_button(page, download_dir, timeout_minutes):
    """
    Try to find and click the download button on the ArcGIS Hub dataset page.
    Hub pages have various download button patterns depending on the page type.

    Returns: path to downloaded file, or None.
    """
    logger.info("  Strategy 1: Looking for Download button...")

    # ArcGIS Hub dataset "about" pages have a Download button
    # that opens a dropdown with format options (CSV, KML, Shapefile, GeoJSON)
    download_selectors = [
        # Hub v2+ (calcite-based)
        'calcite-button:has-text("Download")',
        'calcite-dropdown-item:has-text("Download")',
        # Hub classic and generic
        'button:has-text("Download")',
        'a:has-text("Download")',
        # Hub "I want to use this" section
        'a[href*="download"]',
        'button[data-testid="download-button"]',
        # Hub action bar
        'calcite-action:has-text("Download")',
    ]

    # First, find and click the main download trigger
    download_clicked = False
    for selector in download_selectors:
        try:
            elements = page.locator(selector).all()
            for el in elements:
                try:
                    if not el.is_visible(timeout=2000):
                        continue
                    text = el.inner_text().strip()
                    # Skip "Recent Downloads" or navigation links
                    if any(skip in text for skip in ['Recent', 'Sign', 'Log']):
                        continue
                    bbox = el.bounding_box()
                    # Skip header/nav elements
                    if bbox and bbox['y'] < 100:
                        continue
                    logger.info(f"    Found download button: '{text}' at y={bbox['y'] if bbox else '?'}")
                    el.click()
                    page.wait_for_timeout(2000)
                    download_clicked = True
                    break
                except Exception:
                    continue
            if download_clicked:
                break
        except Exception:
            continue

    if not download_clicked:
        logger.info("    No download button found")
        return None

    # Now look for CSV format option in the dropdown/modal
    csv_path = _select_csv_format_and_download(page, download_dir, timeout_minutes)
    return csv_path


def _try_hub_api_download(page, download_dir, timeout_minutes):
    """
    Try the Hub API download panel — some Hub pages have a direct
    "Download CSV" link or an API/download section.

    Returns: path to downloaded file, or None.
    """
    logger.info("  Strategy 2: Looking for direct download links...")

    # Look for direct CSV download links
    csv_link_selectors = [
        'a[href*=".csv"]',
        'a[href*="format=csv"]',
        'a[href*="download"][href*="csv"]',
        'a:has-text("CSV")',
        'a:has-text("Spreadsheet")',
        'calcite-dropdown-item:has-text("CSV")',
        'calcite-dropdown-item:has-text("Spreadsheet")',
    ]

    for selector in csv_link_selectors:
        try:
            elements = page.locator(selector).all()
            for el in elements:
                try:
                    if not el.is_visible(timeout=2000):
                        continue
                    text = el.inner_text().strip()
                    href = el.get_attribute('href') or ''
                    logger.info(f"    Found link: '{text}' → {href[:100]}")

                    # Click and wait for download
                    with page.expect_download(timeout=timeout_minutes * 60 * 1000) as dl_info:
                        el.click()

                    download = dl_info.value
                    filename = download.suggested_filename
                    save_path = os.path.join(download_dir, filename)
                    download.save_as(save_path)
                    logger.info(f"    Downloaded: {filename}")
                    return save_path
                except Exception as e:
                    logger.info(f"    Link failed: {e}")
                    continue
        except Exception:
            continue

    # Also try extracting download URL from page and fetching directly
    try:
        download_url = page.evaluate("""
            () => {
                // Look for download links in the page
                const links = document.querySelectorAll('a[href]');
                for (const link of links) {
                    const href = link.href;
                    if (href.includes('download') && (href.includes('csv') || href.includes('spreadsheet'))) {
                        return href;
                    }
                }
                // Check for Hub API download pattern in meta/data attributes
                const meta = document.querySelector('meta[name="dc.identifier"]');
                if (meta) {
                    const itemId = meta.content;
                    return `https://hub.arcgis.com/api/v3/datasets/${itemId}/downloads/data?format=csv&spatialRefId=4326`;
                }
                return null;
            }
        """)
        if download_url:
            logger.info(f"    Found download URL: {download_url[:100]}")
            with page.expect_download(timeout=timeout_minutes * 60 * 1000) as dl_info:
                page.goto(download_url)
            download = dl_info.value
            save_path = os.path.join(download_dir, download.suggested_filename)
            download.save_as(save_path)
            logger.info(f"    Downloaded: {download.suggested_filename}")
            return save_path
    except Exception as e:
        logger.info(f"    URL extraction failed: {e}")

    return None


def _select_csv_format_and_download(page, download_dir, timeout_minutes):
    """
    After clicking the main download button, select CSV format and
    wait for the file to download.

    Returns: path to downloaded file, or None.
    """
    logger.info("    Selecting CSV format...")

    # Look for format options (CSV, Spreadsheet, GeoJSON, etc.)
    format_selectors = [
        # Calcite dropdown items
        'calcite-dropdown-item:has-text("CSV")',
        'calcite-dropdown-item:has-text("Spreadsheet")',
        'calcite-dropdown-item:has-text("csv")',
        # Regular links/buttons
        'a:has-text("CSV")',
        'a:has-text("Spreadsheet")',
        'button:has-text("CSV")',
        'button:has-text("Spreadsheet")',
        # List items
        'li:has-text("CSV")',
        'li:has-text("Spreadsheet")',
        # Hub download panel options
        '[data-format="csv"]',
        '[data-value="csv"]',
    ]

    for selector in format_selectors:
        try:
            elements = page.locator(selector).all()
            for el in elements:
                try:
                    if not el.is_visible(timeout=2000):
                        continue
                    text = el.inner_text().strip()
                    logger.info(f"    Found format option: '{text}'")

                    # Click the CSV option and capture the download
                    try:
                        with page.expect_download(timeout=timeout_minutes * 60 * 1000) as dl_info:
                            el.click()

                        download = dl_info.value
                        filename = download.suggested_filename
                        save_path = os.path.join(download_dir, filename)
                        download.save_as(save_path)
                        logger.info(f"    Downloaded: {filename} ({os.path.getsize(save_path) / (1024*1024):.1f} MB)")
                        return save_path
                    except Exception as e:
                        logger.info(f"    Download capture failed: {e}")
                        # The click may have triggered a redirect instead of download
                        # Check if a file appeared in the download directory
                        page.wait_for_timeout(5000)
                        for f in os.listdir(download_dir):
                            fpath = os.path.join(download_dir, f)
                            if os.path.isfile(fpath) and os.path.getsize(fpath) > 1000:
                                logger.info(f"    Found file in download dir: {f}")
                                return fpath
                        continue
                except Exception:
                    continue
        except Exception:
            continue

    # If no format dropdown found, the download button may have directly
    # triggered a CSV download — check download directory
    logger.info("    No format dropdown found — checking for direct download...")
    page.wait_for_timeout(10000)
    for f in os.listdir(download_dir):
        fpath = os.path.join(download_dir, f)
        if os.path.isfile(fpath) and os.path.getsize(fpath) > 1000:
            logger.info(f"    Found downloaded file: {f}")
            return fpath

    # Last resort: try to intercept a download URL from network traffic
    # and use page.expect_download with a longer timeout
    logger.info("    Waiting longer for Hub to generate export file...")
    try:
        with page.expect_download(timeout=min(timeout_minutes, 10) * 60 * 1000) as dl_info:
            # Some Hub pages auto-start download after clicking
            pass
        download = dl_info.value
        save_path = os.path.join(download_dir, download.suggested_filename)
        download.save_as(save_path)
        return save_path
    except Exception:
        pass

    return None


def _geojson_to_csv(geojson_path, csv_path):
    """Convert a GeoJSON file to CSV. Returns result dict or False."""
    try:
        with open(geojson_path, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)

        features = data.get('features', [])
        if not features:
            logger.error("  GeoJSON has no features")
            return False

        # Extract fieldnames from first feature
        first_props = features[0].get('properties', {})
        fieldnames = list(first_props.keys())

        # Check for geometry — add x/y columns if point geometry
        has_geometry = features[0].get('geometry', {}).get('type') == 'Point'
        if has_geometry:
            fieldnames.extend(['x', 'y'])

        total_written = 0
        max_objectid = 0

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()

            for feat in features:
                row = feat.get('properties', {})
                if has_geometry:
                    geom = feat.get('geometry', {})
                    coords = geom.get('coordinates', [])
                    if len(coords) >= 2:
                        row['x'] = coords[0]
                        row['y'] = coords[1]
                writer.writerow(row)
                total_written += 1

                oid = row.get('OBJECTID') or row.get('objectid') or row.get('FID') or ''
                try:
                    oid_int = int(oid)
                    if oid_int > max_objectid:
                        max_objectid = oid_int
                except (ValueError, TypeError):
                    pass

        logger.info(f"  Converted GeoJSON to CSV: {total_written:,} records")
        return {
            'success': True,
            'total_written': total_written,
            'max_objectid': max_objectid,
            'total_server_count': total_written,
            'service_url': 'hub_geojson_export',
        }

    except Exception as e:
        logger.error(f"  GeoJSON conversion failed: {e}")
        return False


# ============================================================================
# Direct REST API download (fallback — may require auth tokens)
# ============================================================================

REST_API_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Referer': 'https://www.virginiaroads.org/',
    'Origin': 'https://www.virginiaroads.org',
}

# Default REST API endpoint (Full_Crash service)
REST_API_BASE = 'https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/Full_Crash/FeatureServer/0'


def rest_fetch_json(url, retries=5, timeout=60):
    """Fetch JSON from ArcGIS REST API using plain HTTP requests.

    Returns parsed JSON dict, or None on failure.
    """
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=REST_API_HEADERS, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                if 'error' not in data:
                    return data
                err = data.get('error', {})
                err_code = err.get('code', '')
                err_msg = err.get('message', str(err))
                # Token required (499) — don't retry, service is auth-restricted
                if err_code == 499 or 'token' in err_msg.lower():
                    logger.warning(f"  Token required (code {err_code}): {err_msg}")
                    return data  # Return the error response so caller can check
                logger.warning(f"  API error: {err_msg}")
            else:
                logger.warning(f"  HTTP {resp.status_code} from REST API")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"  Connection error: {e}")
        except requests.exceptions.Timeout:
            logger.warning(f"  Request timed out ({timeout}s)")
        except Exception as e:
            logger.warning(f"  REST fetch error: {e}")

        if attempt < retries - 1:
            wait = min(15, 2 ** attempt)
            logger.info(f"    Retry {attempt+1} in {wait}s...")
            time.sleep(wait)

    return None


def _find_working_rest_service():
    """Try known FeatureServer URLs via direct REST API.

    Returns (service_url, total_count) or (None, 0).
    Selects the endpoint with the highest record count (minimum 1,000).
    """
    MIN_RECORDS = 1000
    # Try REST_API_BASE first, then the rest of KNOWN_FEATURE_SERVERS
    urls_to_try = [REST_API_BASE] + [u for u in KNOWN_FEATURE_SERVERS if u != REST_API_BASE]

    best_url, best_count = None, 0
    for url in urls_to_try:
        svc_name = url.split('/')[-3]
        count_url = f'{url}/query?where=1%3D1&returnCountOnly=true&f=json'
        data = rest_fetch_json(count_url, retries=2, timeout=30)
        if data and 'count' in data:
            count = data['count']
            logger.info(f"  REST API {svc_name}: {count:,} records")
            if count > best_count:
                best_url, best_count = url, count
        elif data and 'error' in data:
            err = data.get('error', {})
            code = err.get('code', '')
            msg = err.get('message', '')
            logger.info(f"  REST API {svc_name}: error {code} — {msg}")
            if code == 499 or 'token' in str(msg).lower():
                logger.info(f"    (Token required — FeatureServer is auth-restricted)")
        else:
            logger.info(f"  REST API {svc_name}: failed or blocked")

    if best_url and best_count >= MIN_RECORDS:
        if best_count < MIN_STATEWIDE_RECORDS:
            logger.warning(f"  Best endpoint has only {best_count:,} records (expected {MIN_STATEWIDE_RECORDS:,}+ for statewide)")
        return best_url, best_count

    return None, 0


def download_with_rest_api(output_path, batch_size=5000,
                           where_clause=None, append_mode=False):
    """Download crash data using direct REST API requests (no browser).

    This is the primary/fast download method. Falls back to Playwright
    if the API returns connection errors or bot detection blocks.

    Args:
        output_path: Path to write the CSV file.
        batch_size: Records per paginated request.
        where_clause: ArcGIS WHERE filter (e.g. 'OBJECTID > 500000').
                      None means '1=1' (all records).
        append_mode: If True, writes CSV without header (for merging later).

    Returns:
        dict with {success, total_written, max_objectid, total_server_count, service_url}
        or False on failure.
    """
    logger.info("Attempting direct REST API download...")

    # Step 1: Find a working FeatureServer endpoint
    service_url, total_count = _find_working_rest_service()
    if not service_url:
        logger.warning("  Direct REST API not available — will fall back to Playwright")
        return False

    save_cached_url(service_url)
    logger.info(f"  Using: {service_url}")
    logger.info(f"  Total records on server: {total_count:,}")

    # Step 2: Get field schema
    logger.info("  Fetching field schema...")
    schema_url = f'{service_url}?f=json'
    schema = rest_fetch_json(schema_url, retries=3, timeout=30)

    if not schema or 'fields' not in schema:
        logger.warning("  Could not get field schema via REST — falling back")
        return False

    fields = schema['fields']
    has_geometry = 'Point' in schema.get('geometryType', '')
    fieldnames = [f['name'] for f in fields]
    if has_geometry:
        fieldnames.extend(['x', 'y'])

    logger.info(f"  {len(fields)} fields, geometry={has_geometry}")
    logger.info(f"  Fields: {', '.join(fieldnames[:10])}...")

    # Step 3: Determine download query
    effective_where = where_clause or '1=1'
    encoded_where = quote(effective_where)

    if effective_where != '1=1':
        delta_count_url = f'{service_url}/query?where={encoded_where}&returnCountOnly=true&f=json'
        delta_data = rest_fetch_json(delta_count_url, retries=3, timeout=30)
        download_count = delta_data.get('count', total_count) if delta_data else total_count
        logger.info(f"  Incremental query: {effective_where}")
        logger.info(f"  Delta records to download: {download_count:,}")
    else:
        download_count = total_count
        logger.info(f"  Full download: {download_count:,} records")

    # Step 4: Paginate records via REST API
    logger.info(f"  Downloading {download_count:,} records ({batch_size}/batch) via REST API...")

    temp_path = output_path + '.partial'
    offset = 0
    total_written = 0
    max_objectid_seen = 0
    start_time = time.time()
    consecutive_errors = 0
    max_consecutive_errors = 10

    query_base = f'{service_url}/query'

    with open(temp_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        if not append_mode:
            writer.writeheader()

        while offset < download_count:
            # Progress logging
            pct = min(100, int(offset / max(download_count, 1) * 100))
            elapsed = time.time() - start_time
            rate = total_written / max(elapsed, 0.1)
            remaining = download_count - total_written
            eta = remaining / max(rate, 0.1)

            if offset % (batch_size * 5) == 0 or offset == 0:
                logger.info(
                    f"  {total_written:,} / {download_count:,} ({pct}%) "
                    f"| {rate:.0f} rec/s | ETA {eta/60:.1f} min"
                )

            # Build query URL
            params = (
                f'?where={encoded_where}'
                f'&outFields=*'
                f'&resultOffset={offset}'
                f'&resultRecordCount={batch_size}'
                f'&orderByFields=OBJECTID+ASC'
                f'&f=json'
            )
            if has_geometry:
                params += '&outSR=4326'

            fetch_url = query_base + params

            # Fetch via direct REST API
            data = rest_fetch_json(fetch_url, retries=5, timeout=120)

            if data is None:
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"  {max_consecutive_errors} consecutive REST errors")
                    # If we got at least some data, don't discard it — but signal failure
                    # so main() can decide whether to fall back
                    if total_written > 0:
                        logger.warning(f"  Partial download: {total_written:,} records before failure")
                    # Clean up partial file
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    return False
                continue

            if 'error' in data:
                err = data['error']
                logger.warning(f"  API error at offset {offset}: {err}")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    return False
                time.sleep(2)
                continue

            features = data.get('features', [])
            if not features:
                break

            consecutive_errors = 0

            # Write batch to CSV and track max OBJECTID
            for feat in features:
                row = feat.get('attributes', {})
                geom = feat.get('geometry')
                if geom and has_geometry:
                    row['x'] = geom.get('x', '')
                    row['y'] = geom.get('y', '')
                writer.writerow(row)
                total_written += 1
                # Track highest OBJECTID seen
                oid = row.get('OBJECTID') or row.get('objectid') or row.get('FID')
                if oid is not None:
                    try:
                        max_objectid_seen = max(max_objectid_seen, int(oid))
                    except (ValueError, TypeError):
                        pass

            offset += len(features)
            if len(features) < batch_size:
                break

    elapsed = time.time() - start_time
    logger.info(f"  REST API downloaded {total_written:,} records in {elapsed/60:.1f} min")
    logger.info(f"  Average: {total_written/max(elapsed,1):.0f} rec/s")
    logger.info(f"  Max OBJECTID seen: {max_objectid_seen:,}")

    if total_written == 0:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return {
            'success': True,
            'total_written': 0,
            'max_objectid': max_objectid_seen,
            'total_server_count': total_count,
            'service_url': service_url,
        }

    if effective_where == '1=1' and total_written < total_count * 0.95:
        logger.warning(
            f"  Got {total_written:,} of {total_count:,} "
            f"({total_written/total_count*100:.1f}%)"
        )

    # Replace old file with new one
    if os.path.exists(output_path):
        for attempt in range(5):
            try:
                os.remove(output_path)
                break
            except PermissionError:
                if attempt < 4:
                    logger.info(f"  File locked, retrying in {attempt+1}s...")
                    time.sleep(attempt + 1)
                else:
                    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                    alt_path = output_path.replace('.csv', f'_{ts}.csv')
                    shutil.move(temp_path, alt_path)
                    size = os.path.getsize(alt_path)
                    logger.warning(f"  Old file locked — saved as: {alt_path} ({size/(1024*1024):.1f} MB)")
                    return {
                        'success': True,
                        'total_written': total_written,
                        'max_objectid': max_objectid_seen,
                        'total_server_count': total_count,
                        'service_url': service_url,
                    }

    shutil.move(temp_path, output_path)
    size = os.path.getsize(output_path)
    logger.info(f"  Saved: {output_path} ({size/(1024*1024):.1f} MB)")

    return {
        'success': True,
        'total_written': total_written,
        'max_objectid': max_objectid_seen,
        'total_server_count': total_count,
        'service_url': service_url,
    }


# ============================================================================
# Browser-context API helper (Playwright fallback)
# ============================================================================

def browser_fetch_json(page, url, retries=5):
    """
    Make a fetch() call FROM the browser context. This bypasses bot detection
    because the request has the browser's TLS fingerprint, cookies, and headers.
    Returns parsed JSON dict, or None on failure.
    """
    safe_url = json.dumps(url)  # Properly escape URL for JS string literal
    for attempt in range(retries):
        try:
            result = page.evaluate(f"""
                async () => {{
                    try {{
                        const resp = await fetch({safe_url});
                        if (!resp.ok) return {{error: 'HTTP ' + resp.status}};
                        const text = await resp.text();
                        return JSON.parse(text);
                    }} catch(e) {{
                        return {{error: e.message}};
                    }}
                }}
            """)

            if result and 'error' not in result:
                return result

            err = result.get('error', 'unknown') if result else 'null response'
            if attempt < retries - 1:
                wait = min(15, 2 ** attempt)
                logger.info(f"    fetch error: {err}, retry {attempt+1} in {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"    fetch failed after {retries} attempts: {err}")
                return None

        except Exception as e:
            if attempt < retries - 1:
                wait = min(15, 2 ** attempt)
                logger.info(f"    exception: {e}, retry {attempt+1} in {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"    exception after {retries} attempts: {e}")
                return None

    return None


# ============================================================================
# Main download flow (all inside one browser session)
# ============================================================================

def download_with_browser(output_path, headless=True, batch_size=5000,
                          where_clause=None, append_mode=False):
    """
    Single browser session that:
      1. Loads Hub page (establishes session)
      2. Discovers FeatureServer URL
      3. Paginates records via browser fetch() (all or incremental delta)
      4. Streams to CSV

    Args:
        where_clause: ArcGIS WHERE filter (e.g. 'OBJECTID > 500000').
                      None means '1=1' (all records).
        append_mode: If True, writes CSV without header (for merging later).

    Returns:
        dict with {success, total_written, max_objectid, total_server_count, service_url}
        or False on failure.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
            )
            page = context.new_page()

            # ============================================================
            # Step 1: Load Hub page (establishes cookies/session)
            # ============================================================
            logger.info("Step 1: Loading Hub page to establish session...")
            
            # Capture FeatureServer URLs from network traffic
            discovered_fs_urls = []
            def on_request(request):
                url = request.url
                if 'FeatureServer' in url:
                    discovered_fs_urls.append(url)
                if 'replicafilescache' in url:
                    discovered_fs_urls.append(url)
            page.on('request', on_request)

            page.goto(HUB_URL, wait_until='networkidle', timeout=60000)
            page.wait_for_timeout(3000)
            logger.info(f"  Page loaded: {page.title()}")

            # ============================================================
            # Step 2: Find FeatureServer URL
            # ============================================================
            logger.info("Step 2: Finding FeatureServer URL...")

            service_url = None

            # Try cached URL first (via browser fetch to verify)
            cached = load_cached_url()
            if cached:
                count_url = f'{cached}/query?where=1%3D1&returnCountOnly=true&f=json'
                data = browser_fetch_json(page, count_url, retries=2)
                if data and 'count' in data and data['count'] >= 1000:
                    service_url = cached
                    total_count = data['count']
                    logger.info(f"  Cached URL works: {total_count:,} records")

            # Discover from network traffic
            if not service_url:
                # Click Download → CSV to trigger network requests that reveal the URL
                logger.info("  Triggering download to discover URL...")
                page.evaluate("""
                    () => {
                        const walker = document.createTreeWalker(
                            document.body, NodeFilter.SHOW_ELEMENT, null
                        );
                        let node;
                        while (node = walker.nextNode()) {
                            const text = node.textContent.trim();
                            const tag = node.tagName.toLowerCase();
                            if (text === 'Download' && !text.includes('Recent') &&
                                (tag === 'a' || tag === 'button' || tag === 'calcite-action' || tag === 'calcite-button')) {
                                const rect = node.getBoundingClientRect();
                                if (rect.x < 600 && rect.y > 200) {
                                    node.click();
                                    return true;
                                }
                            }
                        }
                        return false;
                    }
                """)
                page.wait_for_timeout(3000)

                # Click first download button (CSV)
                try:
                    btns = page.locator('a:has-text("Download"), button:has-text("Download"), calcite-button:has-text("Download")').all()
                    for btn in btns:
                        try:
                            if not btn.is_visible(timeout=1000):
                                continue
                            text = btn.inner_text().strip()
                            bbox = btn.bounding_box()
                            if 'Recent' in text or (bbox and bbox['y'] < 200):
                                continue
                            btn.click()
                            page.wait_for_timeout(5000)
                            break
                        except Exception:
                            continue
                except Exception:
                    pass

                # Extract FeatureServer URL from captured traffic
                for url in discovered_fs_urls:
                    match = re.search(
                        r'(https://services\.arcgis\.com/[^/]+/arcgis/rest/services/[^/]+/FeatureServer)',
                        url
                    )
                    if match:
                        candidate = match.group(1) + '/0'
                        count_url = f'{candidate}/query?where=1%3D1&returnCountOnly=true&f=json'
                        data = browser_fetch_json(page, count_url, retries=3)
                        if data and 'count' in data and data['count'] >= 1000:
                            if data['count'] > total_count:
                                service_url = candidate
                                total_count = data['count']
                                save_cached_url(service_url)
                                logger.info(f"  Discovered: {service_url} ({total_count:,} records)")
                            if total_count >= 100000:
                                break

                    # Also check replicafilescache pattern
                    match = re.search(r'rest/services/([^/]+)/FeatureServer', url)
                    if match:
                        svc_name = match.group(1)
                        candidate = f'https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/{svc_name}/FeatureServer/0'
                        if candidate != service_url:
                            count_url = f'{candidate}/query?where=1%3D1&returnCountOnly=true&f=json'
                            data = browser_fetch_json(page, count_url, retries=3)
                            if data and 'count' in data and data['count'] >= 1000:
                                if data['count'] > total_count:
                                    service_url = candidate
                                    total_count = data['count']
                                    save_cached_url(service_url)
                                    logger.info(f"  Discovered: {service_url} ({total_count:,} records)")
                                if total_count >= 100000:
                                    break

            # Try known URLs as fallback — pick best (highest count, min 1000)
            if not service_url:
                logger.info("  Trying known FeatureServer URLs via browser fetch...")
                for url in KNOWN_FEATURE_SERVERS:
                    svc_name = url.split('/')[-3]
                    count_url = f'{url}/query?where=1%3D1&returnCountOnly=true&f=json'
                    data = browser_fetch_json(page, count_url, retries=3)
                    if data and 'count' in data:
                        count = data['count']
                        logger.info(f"  {svc_name}: {count:,} records")
                        if count >= 1000 and count > total_count:
                            service_url = url
                            total_count = count
                            save_cached_url(service_url)
                            if count >= 100000:
                                break
                    else:
                        logger.info(f"  {svc_name}: failed")

            if not service_url:
                logger.error("  No working FeatureServer found")
                browser.close()
                return False

            logger.info(f"  Using: {service_url}")
            logger.info(f"  Total records on server: {total_count:,}")

            # ============================================================
            # Step 3: Get field schema
            # ============================================================
            logger.info("Step 3: Fetching field schema...")
            schema_url = f'{service_url}?f=json'
            schema = browser_fetch_json(page, schema_url)

            if not schema or 'fields' not in schema:
                logger.error("  Could not get field schema")
                browser.close()
                return False

            fields = schema['fields']
            has_geometry = 'Point' in schema.get('geometryType', '')
            fieldnames = [f['name'] for f in fields]
            if has_geometry:
                fieldnames.extend(['x', 'y'])

            logger.info(f"  {len(fields)} fields, geometry={has_geometry}")
            logger.info(f"  Fields: {', '.join(fieldnames[:10])}...")

            # ============================================================
            # Step 4: Determine download query (full vs incremental)
            # ============================================================
            effective_where = where_clause or '1=1'
            encoded_where = quote(effective_where)

            # Get count for the actual query (may differ from total if incremental)
            if effective_where != '1=1':
                delta_count_url = f'{service_url}/query?where={encoded_where}&returnCountOnly=true&f=json'
                delta_data = browser_fetch_json(page, delta_count_url, retries=3)
                download_count = delta_data.get('count', total_count) if delta_data else total_count
                logger.info(f"  Incremental query: {effective_where}")
                logger.info(f"  Delta records to download: {download_count:,}")
            else:
                download_count = total_count
                logger.info(f"  Full download: {download_count:,} records")

            # ============================================================
            # Step 5: Paginate records via browser fetch()
            # ============================================================
            logger.info(f"Step 5: Downloading {download_count:,} records ({batch_size}/batch)...")

            temp_path = output_path + '.partial'
            offset = 0
            total_written = 0
            max_objectid_seen = 0
            start_time = time.time()
            consecutive_errors = 0
            max_consecutive_errors = 10

            query_base = f'{service_url}/query'

            with open(temp_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                if not append_mode:
                    writer.writeheader()

                while offset < download_count:
                    # Progress logging
                    pct = min(100, int(offset / max(download_count, 1) * 100))
                    elapsed = time.time() - start_time
                    rate = total_written / max(elapsed, 0.1)
                    remaining = download_count - total_written
                    eta = remaining / max(rate, 0.1)

                    if offset % (batch_size * 5) == 0 or offset == 0:
                        logger.info(
                            f"  {total_written:,} / {download_count:,} ({pct}%) "
                            f"| {rate:.0f} rec/s | ETA {eta/60:.1f} min"
                        )

                    # Build query URL
                    params = (
                        f'?where={encoded_where}'
                        f'&outFields=*'
                        f'&resultOffset={offset}'
                        f'&resultRecordCount={batch_size}'
                        f'&orderByFields=OBJECTID+ASC'
                        f'&f=json'
                    )
                    if has_geometry:
                        params += '&outSR=4326'

                    fetch_url = query_base + params

                    # Fetch via browser
                    data = browser_fetch_json(page, fetch_url, retries=5)

                    if data is None:
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            logger.error(f"  {max_consecutive_errors} consecutive errors, stopping")
                            break
                        # Try refreshing the page
                        logger.info("  Refreshing page to reset session...")
                        page.goto(HUB_URL, wait_until='networkidle', timeout=60000)
                        page.wait_for_timeout(3000)
                        continue

                    if 'error' in data:
                        err = data['error']
                        logger.warning(f"  API error at offset {offset}: {err}")
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            break
                        time.sleep(2)
                        continue

                    features = data.get('features', [])
                    if not features:
                        break

                    consecutive_errors = 0

                    # Write batch to CSV and track max OBJECTID
                    for feat in features:
                        row = feat.get('attributes', {})
                        geom = feat.get('geometry')
                        if geom and has_geometry:
                            row['x'] = geom.get('x', '')
                            row['y'] = geom.get('y', '')
                        writer.writerow(row)
                        total_written += 1
                        # Track highest OBJECTID seen
                        oid = row.get('OBJECTID') or row.get('objectid') or row.get('FID')
                        if oid is not None:
                            try:
                                max_objectid_seen = max(max_objectid_seen, int(oid))
                            except (ValueError, TypeError):
                                pass

                    offset += len(features)
                    if len(features) < batch_size:
                        break

            browser.close()

            elapsed = time.time() - start_time
            logger.info(f"  Downloaded {total_written:,} records in {elapsed/60:.1f} min")
            logger.info(f"  Average: {total_written/max(elapsed,1):.0f} rec/s")
            logger.info(f"  Max OBJECTID seen: {max_objectid_seen:,}")

            if total_written == 0:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                # Return metadata even for zero-delta (incremental up-to-date)
                return {
                    'success': True,
                    'total_written': 0,
                    'max_objectid': max_objectid_seen,
                    'total_server_count': total_count,
                    'service_url': service_url,
                }

            if effective_where == '1=1' and total_written < total_count * 0.95:
                logger.warning(
                    f"  Got {total_written:,} of {total_count:,} "
                    f"({total_written/total_count*100:.1f}%)"
                )

            # Replace old file with new one (handles Windows file locks)
            if os.path.exists(output_path):
                for attempt in range(5):
                    try:
                        os.remove(output_path)
                        break
                    except PermissionError:
                        if attempt < 4:
                            logger.info(f"  File locked, retrying in {attempt+1}s (close Excel?)...")
                            time.sleep(attempt + 1)
                        else:
                            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                            alt_path = output_path.replace('.csv', f'_{ts}.csv')
                            shutil.move(temp_path, alt_path)
                            size = os.path.getsize(alt_path)
                            logger.warning(f"  Old file locked — saved as: {alt_path} ({size/(1024*1024):.1f} MB)")
                            return {
                                'success': True,
                                'total_written': total_written,
                                'max_objectid': max_objectid_seen,
                                'total_server_count': total_count,
                                'service_url': service_url,
                            }

            shutil.move(temp_path, output_path)
            size = os.path.getsize(output_path)
            logger.info(f"  Saved: {output_path} ({size/(1024*1024):.1f} MB)")

            return {
                'success': True,
                'total_written': total_written,
                'max_objectid': max_objectid_seen,
                'total_server_count': total_count,
                'service_url': service_url,
            }

    except Exception as e:
        logger.error(f"  Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# CSV validation
# ============================================================================

def validate_csv(path):
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            head = f.read(500)
        if '<html' in head.lower() or 'Cannot fetch' in head:
            logger.error("  Error page, not CSV")
            return False
        with open(path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            headers = next(reader)
    except Exception as e:
        logger.error(f"  CSV error: {e}")
        return False

    headers_set = set(h.strip() for h in headers)
    if {'Driver_Age', 'DRIVER_AGE', 'Bike_VehicleNumber'} & headers_set:
        logger.error("  Wrong dataset (driver-level)")
        return False

    with open(path, encoding='utf-8-sig') as fh:
        rows = sum(1 for _ in fh) - 1
    logger.info(f"  CSV: {len(headers)} columns, {rows:,} records")
    logger.info(f"  Columns: {headers[:10]}...")
    return True


# ============================================================================
# Jurisdiction filtering
# ============================================================================

def load_jurisdiction_config(jurisdiction):
    if not CONFIG_PATH.exists():
        return {'name': jurisdiction.replace('_', ' ').title()}
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    jurisdictions = config.get('jurisdictions', {})
    if jurisdiction in jurisdictions:
        return jurisdictions[jurisdiction]
    for key, val in jurisdictions.items():
        if key.lower() == jurisdiction.lower():
            return val
    return {'name': jurisdiction.replace('_', ' ').title()}


def filter_by_jurisdiction(df, jurisdiction, jconfig):
    import pandas as pd

    juris_code = str(jconfig.get('jurisCode', ''))
    fips = str(jconfig.get('fips', ''))
    name_patterns = jconfig.get('namePatterns', [])
    display_name = jconfig.get('name', jurisdiction.replace('_', ' ').title())

    logger.info(f"Filtering to {display_name} (code={juris_code}, fips={fips})")
    mask = pd.Series([False] * len(df), index=df.index)
    cols_lower = {c.lower().strip(): c for c in df.columns}

    if juris_code:
        for cl, ca in cols_lower.items():
            if 'juris' in cl and 'code' in cl:
                mask |= df[ca].astype(str).str.strip() == juris_code
                if juris_code.isdigit():
                    mask |= df[ca].astype(str).str.strip() == str(int(juris_code))
                break

    if fips and mask.sum() == 0:
        for cl, ca in cols_lower.items():
            if 'fips' in cl:
                mask |= df[ca].astype(str).str.strip() == fips
                break

    if name_patterns and mask.sum() == 0:
        for cl, ca in cols_lower.items():
            if ('juris' in cl and 'name' in cl) or 'physical' in cl:
                for pat in name_patterns:
                    try:
                        mask |= df[ca].astype(str).str.contains(pat, case=False, na=False, regex=True)
                    except re.error:
                        mask |= df[ca].astype(str).str.lower() == pat.lower()
                break

    if mask.sum() == 0:
        for cl, ca in cols_lower.items():
            if any(kw in cl for kw in ['juris', 'county', 'city', 'physical']):
                mask |= df[ca].astype(str).str.upper().str.contains(display_name.upper(), na=False)
                if mask.sum() > 0:
                    break

    filtered = df[mask].copy()
    logger.info(f"  {len(df):,} -> {len(filtered):,} records for {display_name}")

    if len(filtered) == 0:
        for cl, ca in cols_lower.items():
            if any(kw in cl for kw in ['juris', 'physical', 'county']):
                sample = df[ca].dropna().unique()[:10].tolist()
                logger.warning(f"  Sample {ca}: {sample}")

    return filtered


def split_road_types(df, jurisdiction, data_dir):
    cols_lower = {c.lower().strip(): c for c in df.columns}
    sys_col = next((cols_lower[cl] for cl in cols_lower if cl in ('system', 'sys_id', 'road_system', 'route_syst')), None)
    own_col = next((cols_lower[cl] for cl in cols_lower if 'ownership' in cl), None)

    # Decode raw ArcGIS numeric codes if present (download returns '1'-'5')
    if sys_col:
        system_decode = {
            '1': 'NonVDOT primary', '2': 'NonVDOT secondary',
            '3': 'VDOT Interstate', '4': 'VDOT Primary', '5': 'VDOT Secondary',
        }
        raw = df[sys_col].astype(str).str.strip()
        if raw.isin(system_decode.keys()).any() and not raw.str.contains('VDOT', na=False).any():
            df[sys_col] = raw.map(system_decode).fillna(df[sys_col])
            logger.info(f"  Decoded SYSTEM numeric codes → text values")

    if own_col:
        ownership_decode = {
            '1': '1. State Hwy Agency', '2': '2. County Hwy Agency',
            '3': '3. City or Town Hwy Agency', '4': '4. Federal Roads',
            '5': '5. Toll Roads Maintained by Others', '6': '6. Private/Unknown Roads',
        }
        raw = df[own_col].astype(str).str.strip()
        if raw.isin(ownership_decode.keys()).any() and not raw.str.contains('Hwy Agency', na=False).any():
            df[own_col] = raw.map(ownership_decode).fillna(df[own_col])
            logger.info(f"  Decoded Ownership numeric codes → text values")

    if sys_col:
        logger.info(f"  System '{sys_col}': {df[sys_col].value_counts().head(8).to_dict()}")
        county_vals = {'NonVDOT secondary', 'NONVDOT', 'Non-VDOT', 'SECONDARY', 'Secondary'}
        county = df[df[sys_col].astype(str).str.strip().isin(county_vals)]
        if len(county) > 0:
            county.to_csv(str(data_dir / f'{jurisdiction}_county_roads.csv'), index=False)
            logger.info(f"  county_roads: {len(county):,}")

        interstate_vals = {'VDOT Interstate', 'Interstate', 'INTERSTATE', 'IS'}
        no_int = df[~df[sys_col].astype(str).str.strip().isin(interstate_vals)]
        if len(no_int) < len(df):
            no_int.to_csv(str(data_dir / f'{jurisdiction}_no_interstate.csv'), index=False)
            logger.info(f"  no_interstate: {len(no_int):,}")

    if own_col:
        logger.info(f"  Ownership '{own_col}': {df[own_col].value_counts().head(8).to_dict()}")
        city = df[df[own_col].astype(str).str.upper().apply(lambda v: 'CITY' in v or 'TOWN' in v)]
        if len(city) > 0:
            city.to_csv(str(data_dir / f'{jurisdiction}_city_roads.csv'), index=False)
            logger.info(f"  city_roads: {len(city):,}")


# ============================================================================
# Merge — append incremental delta to existing CSV
# ============================================================================

def merge_delta_into_csv(existing_path, delta_path, output_path):
    """
    Merge incremental delta CSV into existing statewide CSV.
    Deduplicates by Document Nbr (keeps the newer version from delta).

    Returns: dict with {total_rows, delta_rows, duplicates_removed}
    """
    import pandas as pd

    logger.info("Merging incremental delta into existing CSV...")

    # Load both files
    existing_df = pd.read_csv(existing_path, dtype=str, low_memory=False)
    delta_df = pd.read_csv(delta_path, dtype=str, low_memory=False)

    existing_count = len(existing_df)
    delta_count = len(delta_df)
    logger.info(f"  Existing: {existing_count:,} records")
    logger.info(f"  Delta: {delta_count:,} records")

    if delta_count == 0:
        logger.info("  No new records to merge")
        return {'total_rows': existing_count, 'delta_rows': 0, 'duplicates_removed': 0}

    # Find Document Number column for deduplication
    doc_col = find_doc_nbr_column(list(existing_df.columns))

    # Concatenate: delta goes AFTER existing so drop_duplicates(keep='last')
    # keeps the newer delta version of any duplicated document numbers
    combined_df = pd.concat([existing_df, delta_df], ignore_index=True)

    duplicates_removed = 0
    if doc_col and doc_col in combined_df.columns:
        before_dedup = len(combined_df)
        # Only deduplicate rows that have a non-empty document number
        has_doc = combined_df[doc_col].notna() & (combined_df[doc_col] != '') & (combined_df[doc_col] != 'nan')
        df_with_doc = combined_df[has_doc].drop_duplicates(subset=[doc_col], keep='last')
        df_without_doc = combined_df[~has_doc]
        combined_df = pd.concat([df_with_doc, df_without_doc], ignore_index=True)
        duplicates_removed = before_dedup - len(combined_df)
        logger.info(f"  Deduplicated by {doc_col}: removed {duplicates_removed:,} duplicates")
    else:
        logger.warning("  No Document Nbr column found — skipping deduplication")

    # Write merged result
    combined_df.to_csv(output_path, index=False)
    total_rows = len(combined_df)
    net_new = total_rows - existing_count
    logger.info(f"  Merged result: {total_rows:,} records ({net_new:+,} net new)")

    return {
        'total_rows': total_rows,
        'delta_rows': delta_count,
        'duplicates_removed': duplicates_removed,
    }


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Download Virginia crash data (supports incremental updates)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Download modes:
  Default (incremental):  Only downloads new records since last run.
                          Uses OBJECTID high-water mark from manifest.
                          ~30 seconds for monthly updates vs ~23 min full.

  --full:                 Downloads ALL records (ignore manifest).
                          Use quarterly to catch edits/deletions.

  --force:                Same as --full but also overwrites cached data.

Examples:
  # Monthly incremental (fast — only new records):
  python download_virginia_crash_data.py --data-dir data --jurisdiction henrico

  # Quarterly full refresh (catches edits/deletions):
  python download_virginia_crash_data.py --data-dir data --full --jurisdiction henrico

  # Force full re-download:
  python download_virginia_crash_data.py --data-dir data --force --jurisdiction henrico
        """
    )
    parser.add_argument('--data-dir', default='data')
    parser.add_argument('--jurisdiction', default='statewide')
    parser.add_argument('--force', action='store_true',
                        help='Force full re-download (overwrite everything)')
    parser.add_argument('--full', action='store_true',
                        help='Full download (all records, not incremental)')
    parser.add_argument('--gzip', action='store_true')
    parser.add_argument('--headful', action='store_true', help='Show browser window')
    parser.add_argument('--batch-size', type=int, default=5000, help='Records per request')
    parser.add_argument('--playwright-only', action='store_true',
                        help='Skip REST API and use only Playwright browser method')
    parser.add_argument('--rest-only', action='store_true',
                        help='Use only REST API (no Playwright fallback)')
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    jurisdiction = args.jurisdiction.lower().strip()
    headless = not args.headful
    do_full = args.full or args.force

    output_path = str(data_dir / 'virginia_statewide_all_roads.csv')

    # Determine download mode
    manifest = load_manifest(data_dir) if not do_full else None
    existing_csv_exists = os.path.exists(output_path)

    if manifest and existing_csv_exists and not do_full:
        download_mode = 'incremental'
    else:
        download_mode = 'full'
        if not do_full and not existing_csv_exists:
            logger.info("No existing CSV found — starting with full download")
        elif not do_full and not manifest:
            logger.info("No manifest found — starting with full download")

    use_playwright_only = args.playwright_only
    use_rest_only = args.rest_only

    method_label = 'Hub CSV Export → REST API → Playwright FeatureServer'
    if use_playwright_only:
        method_label = 'Playwright only (Hub export + FeatureServer)'
    elif use_rest_only:
        method_label = 'REST API only (no Playwright/Hub)'

    logger.info("=" * 60)
    logger.info("  CRASH LENS — Virginia Crash Data Download (v9)")
    logger.info(f"  Mode: {download_mode.upper()}")
    logger.info(f"  Method: {method_label}")
    logger.info(f"  Output: {data_dir}")
    logger.info(f"  Jurisdiction: {jurisdiction}")
    logger.info(f"  Batch size: {args.batch_size:,}")
    if download_mode == 'incremental':
        logger.info(f"  Last OBJECTID: {manifest['max_objectid']:,}")
        logger.info(f"  Last download: {manifest.get('download_date', 'unknown')}")
    logger.info(f"  Started: {datetime.now()}")
    logger.info("=" * 60)

    csv_path = None

    def _try_download(out_path, where=None, append=False):
        """Try Hub export first, then REST API, then Playwright FeatureServer.
        Returns result dict or False."""
        result = False

        # Attempt 1: Hub CSV Export via Playwright (primary — works even when
        # FeatureServer requires auth tokens, as Hub serves its own cached export)
        # Only for full downloads (incremental uses FeatureServer with WHERE clause)
        if not use_rest_only and where is None:
            logger.info("=" * 40)
            logger.info("  ATTEMPT 1: Hub CSV Export (Playwright)")
            logger.info("=" * 40)
            result = download_via_hub_export(
                out_path, headless=headless
            )
            if result is not False:
                return result
            logger.warning("  Hub CSV export failed — trying FeatureServer methods")

        # Attempt 2: Direct REST API (fast, no browser — may fail if token required)
        if not use_playwright_only:
            logger.info("=" * 40)
            logger.info("  ATTEMPT 2: Direct REST API")
            logger.info("=" * 40)
            result = download_with_rest_api(
                out_path, batch_size=args.batch_size,
                where_clause=where, append_mode=append
            )
            if result is not False:
                return result
            logger.warning("  REST API download failed")

        # Attempt 3: Playwright browser-routed FeatureServer queries
        if not use_rest_only:
            logger.info("=" * 40)
            logger.info("  ATTEMPT 3: Playwright FeatureServer fallback")
            logger.info("=" * 40)
            result = download_with_browser(
                out_path, headless=headless, batch_size=args.batch_size,
                where_clause=where, append_mode=append
            )
            if result is not False:
                return result
            logger.error("  All download methods failed")

        return False

    if download_mode == 'incremental':
        # ── Incremental: download only new records ──
        last_max = manifest['max_objectid']
        last_count = manifest.get('total_count', 0)
        where_clause = f'OBJECTID > {last_max}'
        delta_path = str(data_dir / 'virginia_delta.csv')

        result = _try_download(delta_path, where=where_clause)

        if result is False:
            logger.error("Incremental download failed — falling back to full download")
            download_mode = 'full'
            result = None
        elif isinstance(result, dict):
            server_count = result.get('total_server_count', 0)
            delta_written = result.get('total_written', 0)

            # ── OBJECTID reset detection ──
            # If delta returned 0 records but server has MORE records than
            # we last saw, the OBJECTIDs were likely reset (dataset republished)
            if delta_written == 0 and server_count > last_count:
                logger.warning("=" * 50)
                logger.warning("  OBJECTID RESET DETECTED!")
                logger.warning(f"  Server has {server_count:,} records (was {last_count:,})")
                logger.warning(f"  But 0 records with OBJECTID > {last_max:,}")
                logger.warning("  Falling back to FULL download")
                logger.warning("=" * 50)
                download_mode = 'full'
                if os.path.exists(delta_path):
                    os.remove(delta_path)
            elif delta_written == 0:
                # Genuinely no new records
                logger.info("  No new records since last download — dataset is up to date")
                csv_path = output_path
                # Update manifest timestamp even if no new data
                save_manifest(
                    data_dir,
                    max_objectid=last_max,
                    total_count=server_count,
                    record_count=last_count,
                    mode='incremental',
                    service_url=result.get('service_url'),
                    delta_count=0,
                )
            else:
                # Merge delta into existing CSV
                logger.info(f"  Downloaded {delta_written:,} new records")
                merge_result = merge_delta_into_csv(output_path, delta_path, output_path)

                # Update manifest
                new_max = result.get('max_objectid', last_max)
                save_manifest(
                    data_dir,
                    max_objectid=new_max,
                    total_count=server_count,
                    record_count=merge_result['total_rows'],
                    mode='incremental',
                    service_url=result.get('service_url'),
                    delta_count=delta_written,
                )
                csv_path = output_path

                # Clean up delta file
                if os.path.exists(delta_path):
                    os.remove(delta_path)

                if not validate_csv(output_path):
                    logger.error("CSV validation failed after merge")
                    sys.exit(1)

    if download_mode == 'full' and csv_path is None:
        # ── Full download ──
        if not args.force and existing_csv_exists:
            size = os.path.getsize(output_path)
            if size > 10_000_000 and not args.full:
                with open(output_path, encoding='utf-8-sig') as fh:
                    rows = sum(1 for _ in fh) - 1
                logger.info(f"Existing: {output_path} ({rows:,} records). Use --force or --full.")
                csv_path = output_path

        if csv_path is None:
            result = _try_download(output_path)
            if result is False or (isinstance(result, dict) and not result.get('success')):
                logger.error("Download failed")
                sys.exit(1)
            if not validate_csv(output_path):
                logger.error("CSV validation failed")
                sys.exit(1)
            csv_path = output_path

            # Save manifest for future incremental runs
            if isinstance(result, dict):
                save_manifest(
                    data_dir,
                    max_objectid=result.get('max_objectid', 0),
                    total_count=result.get('total_server_count', 0),
                    record_count=result.get('total_written', 0),
                    mode='full',
                    service_url=result.get('service_url'),
                )

    if args.gzip and csv_path:
        gz = csv_path + '.gz'
        with open(csv_path, 'rb') as fi, gzip.open(gz, 'wb') as fo:
            shutil.copyfileobj(fi, fo)
        logger.info(f"Compressed: {os.path.getsize(gz)/(1024*1024):.1f} MB")

    if jurisdiction and jurisdiction != 'statewide' and csv_path:
        import pandas as pd
        jconfig = load_jurisdiction_config(jurisdiction)
        df = pd.read_csv(csv_path, dtype=str, low_memory=False)
        logger.info(f"Loaded {len(df):,} statewide ({len(df.columns)} columns)")

        filtered = filter_by_jurisdiction(df, jurisdiction, jconfig)
        if len(filtered) == 0:
            logger.error(f"No records for '{jurisdiction}'")
            sys.exit(1)

        all_path = str(data_dir / f'{jurisdiction}_all_roads.csv')
        filtered.to_csv(all_path, index=False)
        logger.info(f"Saved: {all_path} ({len(filtered):,} records)")
        split_road_types(filtered, jurisdiction, data_dir)

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"  DONE ({download_mode} mode)")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
