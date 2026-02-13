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

# OnBase direct retrieval endpoints (bypass HTML viewer)
ONBASE_GETDOC_URLS = [
    'https://oitco.hylandcloud.com/CDOTRMPop/docpop/GetDoc.aspx',
    'https://oitco.hylandcloud.com/CDOTRMPop/docpop/PdfPop.aspx',
    'https://oitco.hylandcloud.com/CDOTRMPop/api/document',
]

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
    html_str = (html_content.decode('utf-8', errors='ignore')
                if isinstance(html_content, bytes) else html_content)

    # Look for common OnBase download URL patterns
    patterns = [
        r'href=["\']([^"\']*PdfPop\.aspx[^"\']*)["\']',
        r'href=["\']([^"\']*GetDoc[^"\']*)["\']',
        r'href=["\']([^"\']*Download[^"\']*)["\']',
        r'src=["\']([^"\']*\.xlsx?[^"\']*)["\']',
        r'window\.location\s*=\s*["\']([^"\']+)["\']',
        r'window\.open\(["\']([^"\']+)["\']',
        # OnBase native-document retrieval patterns (viewer pages)
        r'href=["\']([^"\']*RetrieveNativeDocument[^"\']*)["\']',
        r'href=["\']([^"\']*GetNativeDoc[^"\']*)["\']',
        r'href=["\']([^"\']*SendToApplication[^"\']*)["\']',
        r'href=["\']([^"\']*RenderDocument[^"\']*)["\']',
        r'href=["\']([^"\']*docid=\d+[^"\']*\.(?:xlsx?|csv)[^"\']*)["\']',
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


def extract_obtoken_url(html_content, base_url):
    """
    Extract the ViewDocumentEx.aspx?OBToken=... URL from an OnBase DocPop HTML
    response.

    When docpop.aspx processes a document request the server generates a
    session-scoped OBToken GUID and embeds it in the frameset, iframe src, or
    inline JavaScript.  ViewDocumentEx.aspx requires this token (along with the
    matching ASP.NET_SessionId cookie) to serve the actual file content.

    Returns the absolute URL string, or None if no OBToken was found.
    """
    html_str = (html_content.decode('utf-8', errors='ignore')
                if isinstance(html_content, bytes) else html_content)

    from urllib.parse import urljoin

    # Patterns ordered from most specific (frame/iframe src) to broadest
    # (standalone GUID).  We stop at the first match.
    patterns = [
        # <frame src="ViewDocumentEx.aspx?OBToken=..."> or <iframe src="...">
        r'(?:frame|iframe)[^>]+src=["\']([^"\']*ViewDocumentEx[^"\']*OBToken=[^"\']+)["\']',
        # Any src= or href= containing OBToken
        r'(?:src|href)\s*=\s*["\']([^"\']*OBToken=[^"\']+)["\']',
        # JS: .src = "...OBToken=..."  or  location = "...OBToken=..."
        r'(?:\.src|location)\s*=\s*["\']([^"\']*OBToken=[^"\']+)["\']',
        # JS: window.open("...OBToken=...")
        r'window\.open\(\s*["\']([^"\']*OBToken=[^"\']+)["\']',
        # Quoted string with full ViewDocumentEx URL (catches JS variable assignments)
        r'["\']([^"\']*ViewDocumentEx\.aspx\?[^"\']*OBToken=[^"\']+)["\']',
        # Bare OBToken GUID anywhere in the page — we'll construct the URL
        r'OBToken=([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})',
    ]

    for pattern in patterns:
        match = re.search(pattern, html_str, re.IGNORECASE)
        if match:
            url = match.group(1)
            # Last pattern captures only the bare GUID — build the URL
            if re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', url):
                url = f'ViewDocumentEx.aspx?OBToken={url}'
            # Resolve relative URLs against the base (docpop.aspx response URL)
            if not url.startswith('http'):
                url = urljoin(base_url, url)
            return url

    return None


def _playwright_available():
    """Check if Playwright is installed and has browsers."""
    try:
        from playwright.sync_api import sync_playwright
        # Verify chromium binary is actually installed (not just the Python package)
        with sync_playwright() as p:
            browser_path = p.chromium.executable_path
            if browser_path and os.path.isfile(browser_path):
                return True
            logger.warning(f"  Playwright package installed but chromium binary not found at: {browser_path}")
            return False
    except ImportError:
        return False
    except Exception as e:
        logger.warning(f"  Playwright availability check failed: {e}")
        return False


def download_with_playwright(docid, label='document', timeout_ms=60000):
    """
    Fallback: use a headless Chromium browser to download the file.
    Playwright handles JavaScript rendering, session cookies, and redirects
    that requests cannot follow.

    OnBase uses an ASP.NET frameset where the DocSelectPage iframe starts at
    blank.aspx and gets populated asynchronously by JavaScript.  We must:
      1. Intercept network responses carrying Excel/binary content
      2. Wait for the iframe to navigate away from blank.aspx
      3. Look for download triggers inside the iframe (not just the main page)

    Returns (content_bytes, extension) or raises on failure.
    """
    from playwright.sync_api import sync_playwright

    url = f"{ONBASE_BASE_URL}?clienttype=html&docid={docid}"
    logger.info(f"  Playwright fallback: launching headless browser...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # --- Network response interceptor ---
        # OnBase may serve the Excel file as a sub-request while the
        # DocSelectPage iframe loads.  Capture it before it disappears.
        captured_excel = {}

        def _on_response(response):
            if captured_excel:
                return  # already captured
            try:
                ct = (response.headers.get('content-type') or '').lower()
                cd = response.headers.get('content-disposition') or ''
                resp_url = response.url.lower()

                is_binary = ('octet-stream' in ct or 'spreadsheet' in ct or
                             'excel' in ct or 'ms-excel' in ct)
                has_file_url = any(k in resp_url for k in [
                    '.xlsx', '.xls', 'getdoc', 'retrievedoc',
                    'fetchdocument', 'renderpage',
                ])
                has_file_disp = '.xls' in cd.lower()

                if is_binary or has_file_url or has_file_disp:
                    body = response.body()
                    if len(body) > 1000:  # skip tiny responses
                        is_valid, ext, reason = detect_file_type(body, ct, cd)
                        if is_valid:
                            captured_excel['data'] = body
                            captured_excel['ext'] = ext
                            captured_excel['reason'] = f'network intercept: {reason}'
                            logger.info(f"  [Intercept] Captured Excel from {response.url[:100]}")
            except Exception:
                pass

        page.on('response', _on_response)

        # Visit the DocPop landing page first to establish session cookies,
        # then navigate to the document.
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

            # Check if network interceptor already captured the file
            if captured_excel:
                browser.close()
                logger.info(f"  Playwright success ({captured_excel['reason']})")
                return captured_excel['data'], captured_excel['ext']

            # --- Wait for DocSelectPage iframe to navigate ---
            # The iframe starts at blank.aspx and JS populates it.
            logger.info("  Waiting for OnBase DocSelectPage iframe to load...")
            doc_frame = None
            for _ in range(40):  # up to ~40 seconds
                for frame in page.frames:
                    furl = frame.url.lower()
                    if (frame != page.main_frame
                            and 'blank.aspx' not in furl
                            and 'unloadhandler' not in furl
                            and furl not in ('', 'about:blank')):
                        doc_frame = frame
                        break
                if doc_frame or captured_excel:
                    break
                page.wait_for_timeout(1000)

            if captured_excel:
                browser.close()
                logger.info(f"  Playwright success ({captured_excel['reason']})")
                return captured_excel['data'], captured_excel['ext']

            # --- Prepare list of frames to search for download triggers ---
            all_frames = [page] + ([doc_frame] if doc_frame else [])
            if doc_frame:
                logger.info(f"  DocSelectPage iframe navigated to: {doc_frame.url[:150]}")
                try:
                    doc_frame.wait_for_load_state('networkidle', timeout=15000)
                except Exception:
                    pass
                if captured_excel:
                    browser.close()
                    logger.info(f"  Playwright success ({captured_excel['reason']})")
                    return captured_excel['data'], captured_excel['ext']
            else:
                logger.info("  DocSelectPage iframe did not navigate away from blank.aspx")

            # --- Click download triggers in all frames ---
            # OnBase ViewDocumentEx uses toolbar buttons (img/span elements with
            # onclick handlers), NOT standard <a> links.  We search for both
            # traditional links and OnBase-specific toolbar controls.
            download_selectors = [
                # OnBase toolbar buttons (img with title/alt, span with title)
                'img[title*="Send to"]', 'img[title*="send to"]',
                'img[title*="Retrieve"]', 'img[title*="retrieve"]',
                'img[title*="Download"]', 'img[title*="download"]',
                'img[title*="Save"]', 'img[title*="save"]',
                'img[title*="Export"]', 'img[title*="export"]',
                'img[alt*="Send to"]', 'img[alt*="Retrieve"]',
                'img[alt*="Download"]', 'img[alt*="Export"]',
                # OnBase toolbar span/div buttons
                'span[title*="Send to"]', 'span[title*="Retrieve"]',
                'span[title*="Download"]', 'span[title*="Export"]',
                'div[title*="Send to"]', 'div[title*="Retrieve"]',
                'div[title*="Download"]', 'div[title*="Export"]',
                # OnBase-specific element IDs
                '[id*="SendToApp"]', '[id*="sendToApp"]',
                '[id*="RetrieveNative"]', '[id*="retrieveNative"]',
                '[id*="NativeDoc"]', '[id*="nativeDoc"]',
                '[id*="ToolbarSendTo"]', '[id*="toolbarSendTo"]',
                '[id*="imgSendTo"]', '[id*="imgRetrieve"]',
                '[id*="imgDownload"]', '[id*="imgExport"]',
                # Standard link-based selectors
                'a[href*="GetDoc"]', 'a[href*="getdoc"]',
                'a[href*="Download"]', 'a[href*="download"]',
                'a[href*="Retrieve"]', 'a[href*="retrieve"]',
                'a[href*="RetrieveNativeDocument"]',
                'a[href*="PdfPop"]', 'a[href*="pdfpop"]',
                'a[href*=".xlsx"]', 'a[href*=".xls"]',
                '[id*="lnkRetrieve"]', '[id*="btnDownload"]',
                '[id*="btnRetrieve"]', '[id*="SendTo"]', '[id*="sendTo"]',
                'input[type="button"][value*="Download"]',
                'input[type="button"][value*="Retrieve"]',
                'input[type="submit"][value*="Download"]',
                'input[type="submit"][value*="Retrieve"]',
                '[title*="Send to"]', '[title*="Retrieve"]',
                '[title*="Download"]', '[title*="Save"]',
                'text=Download', 'text=Retrieve',
                'text=Open', 'text=Save',
                'text=Send to', 'text=Send To',
            ]

            for target_frame in all_frames:
                frame_label = 'main' if target_frame == page else 'iframe'
                for selector in download_selectors:
                    try:
                        el = target_frame.query_selector(selector)
                        if el and el.is_visible():
                            logger.info(f"  Clicking [{frame_label}]: {selector}")
                            try:
                                with page.expect_download(timeout=15000) as dl_info:
                                    el.click()
                                download = dl_info.value
                                downloaded_path = download.path()
                                logger.info(f"  Download captured: {download.suggested_filename}")
                                break
                            except Exception:
                                if captured_excel:
                                    browser.close()
                                    logger.info(f"  Playwright success ({captured_excel['reason']})")
                                    return captured_excel['data'], captured_excel['ext']
                    except Exception:
                        continue
                if downloaded_path:
                    break

            # --- Try fetching iframe URL directly (it may serve the file) ---
            if downloaded_path is None and doc_frame and doc_frame.url:
                frame_url = doc_frame.url
                if 'blank.aspx' not in frame_url.lower():
                    logger.info(f"  Trying direct fetch of iframe URL: {frame_url[:120]}")
                    try:
                        resp = page.request.get(frame_url)
                        body = resp.body()
                        is_valid, ext, reason = detect_file_type(body)
                        if is_valid:
                            browser.close()
                            logger.info(f"  Playwright success via iframe URL: {reason}")
                            return body, ext
                    except Exception as e:
                        logger.info(f"  Direct iframe URL fetch failed: {e}")

            # --- JavaScript-based download trigger across all frames ---
            # OnBase viewer uses JS functions for native document retrieval.
            # Try calling known OnBase client-side APIs and clicking toolbar
            # elements that may not be standard <a> links.
            if downloaded_path is None:
                for target_frame in all_frames:
                    try:
                        with page.expect_download(timeout=10000) as dl_info:
                            target_frame.evaluate("""() => {
                                // 1. Try OnBase JS API functions (if available)
                                if (typeof SendToApplication === 'function') {
                                    SendToApplication(); return true;
                                }
                                if (typeof RetrieveNativeDocument === 'function') {
                                    RetrieveNativeDocument(); return true;
                                }
                                if (typeof GetNativeDocument === 'function') {
                                    GetNativeDocument(); return true;
                                }
                                if (typeof window.HSViewer !== 'undefined') {
                                    if (typeof window.HSViewer.sendToApplication === 'function') {
                                        window.HSViewer.sendToApplication(); return true;
                                    }
                                    if (typeof window.HSViewer.retrieveNative === 'function') {
                                        window.HSViewer.retrieveNative(); return true;
                                    }
                                }

                                // 2. Click any toolbar image/button with send/retrieve title
                                const toolbarBtns = document.querySelectorAll(
                                    'img[title], span[title], div[title], td[title]'
                                );
                                for (const el of toolbarBtns) {
                                    const t = (el.title || '').toLowerCase();
                                    if (t.includes('send to') || t.includes('retrieve') ||
                                        t.includes('download') || t.includes('native') ||
                                        t.includes('export')) {
                                        el.click(); return true;
                                    }
                                }

                                // 3. Click any element with onclick containing
                                //    retrieve/sendto/download
                                const allEls = document.querySelectorAll('[onclick]');
                                for (const el of allEls) {
                                    const oc = (el.getAttribute('onclick') || '').toLowerCase();
                                    if (oc.includes('retrieve') || oc.includes('sendto') ||
                                        oc.includes('download') || oc.includes('native')) {
                                        el.click(); return true;
                                    }
                                }

                                // 4. Standard link-based fallback
                                const links = document.querySelectorAll('a');
                                for (const a of links) {
                                    const href = (a.href || '').toLowerCase();
                                    if (href.includes('getdoc') || href.includes('download') ||
                                        href.includes('.xls') || href.includes('pdfpop') ||
                                        href.includes('retrieve') || href.includes('native')) {
                                        a.click();
                                        return true;
                                    }
                                }

                                const btn = document.querySelector(
                                    '[id*="download"], [id*="Download"], ' +
                                    '[id*="Retrieve"], [id*="retrieve"], ' +
                                    '[id*="SendTo"], [id*="sendTo"], ' +
                                    '[id*="Native"], [id*="native"]'
                                );
                                if (btn) { btn.click(); return true; }
                                return false;
                            }""")
                        download = dl_info.value
                        downloaded_path = download.path()
                        logger.info(f"  JS-triggered download: {download.suggested_filename}")
                        break
                    except Exception:
                        continue

            # --- Final check on network interceptor ---
            if captured_excel:
                browser.close()
                logger.info(f"  Playwright success ({captured_excel['reason']})")
                return captured_excel['data'], captured_excel['ext']

            # --- Diagnostic dump (only on failure) ---
            if downloaded_path is None:
                try:
                    page_html = page.content()
                    logger.info(f"  [Playwright diag] Page URL: {page.url}")
                    logger.info(f"  [Playwright diag] Page title: {page.title()}")
                    logger.info(f"  [Playwright diag] HTML length: {len(page_html):,} chars")
                    all_links = page.evaluate("""() => {
                        return Array.from(document.querySelectorAll('a')).slice(0, 20).map(a => ({
                            text: (a.textContent || '').trim().substring(0, 60),
                            href: (a.href || '').substring(0, 120),
                            visible: a.offsetParent !== null
                        }));
                    }""")
                    logger.info(f"  [Playwright diag] Links found: {len(all_links)}")
                    for lnk in all_links:
                        logger.info(f"    <a href='{lnk['href']}' visible={lnk['visible']}>{lnk['text']}</a>")

                    # Dump toolbar elements with titles (OnBase uses img/span toolbar)
                    toolbar_els = page.evaluate("""() => {
                        const results = [];
                        for (const frame of [document, ...Array.from(document.querySelectorAll('iframe')).map(f => { try { return f.contentDocument } catch(e) { return null } }).filter(Boolean)]) {
                            const titled = frame.querySelectorAll('[title], [onclick], img[alt]');
                            for (const el of Array.from(titled).slice(0, 30)) {
                                results.push({
                                    tag: el.tagName,
                                    id: (el.id || '').substring(0, 60),
                                    title: (el.title || '').substring(0, 80),
                                    alt: (el.alt || '').substring(0, 80),
                                    onclick: (el.getAttribute('onclick') || '').substring(0, 100),
                                    visible: el.offsetParent !== null
                                });
                            }
                        }
                        return results;
                    }""")
                    logger.info(f"  [Playwright diag] Titled/onclick elements: {len(toolbar_els)}")
                    for el in toolbar_els:
                        attrs = ' '.join(f'{k}="{v}"' for k, v in el.items() if v)
                        logger.info(f"    <{attrs}>")

                    all_iframes = page.evaluate("""() => {
                        return Array.from(document.querySelectorAll('iframe')).map(f => ({
                            src: (f.src || '').substring(0, 150),
                            id: f.id || '',
                            name: f.name || ''
                        }));
                    }""")
                    logger.info(f"  [Playwright diag] Iframes: {len(all_iframes)}")
                    for ifr in all_iframes:
                        logger.info(f"    <iframe src='{ifr['src']}' id='{ifr['id']}' name='{ifr['name']}'/>")

                    # Dump iframe content and their toolbar elements
                    for frame in page.frames:
                        if frame != page.main_frame:
                            try:
                                fc = frame.content()
                                logger.info(f"  [Playwright diag] Frame {frame.url[:80]} HTML ({len(fc)} chars):\n{fc[:1000]}")
                                # Also search for toolbar/onclick elements in frames
                                frame_btns = frame.evaluate("""() => {
                                    const results = [];
                                    const els = document.querySelectorAll('[title], [onclick], img[alt], [id*="toolbar"], [class*="toolbar"]');
                                    for (const el of Array.from(els).slice(0, 20)) {
                                        results.push({
                                            tag: el.tagName,
                                            id: (el.id || '').substring(0, 60),
                                            title: (el.title || '').substring(0, 80),
                                            alt: (el.alt || '').substring(0, 80),
                                            onclick: (el.getAttribute('onclick') || '').substring(0, 120),
                                            className: (el.className || '').toString().substring(0, 80)
                                        });
                                    }
                                    return results;
                                }""")
                                if frame_btns:
                                    logger.info(f"  [Playwright diag] Frame toolbar elements: {len(frame_btns)}")
                                    for btn in frame_btns:
                                        attrs = ' '.join(f'{k}="{v}"' for k, v in btn.items() if v)
                                        logger.info(f"    <{attrs}>")
                            except Exception:
                                pass
                    logger.info(f"  [Playwright diag] Main HTML preview:\n{page_html[:1500]}")
                except Exception as diag_err:
                    logger.warning(f"  [Playwright diag] Failed to dump page: {diag_err}")

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
      1.  Direct requests with redirect following
      1b. Re-bootstrap session and retry (if strategy 1 got 403)
      1.5 Extract OBToken from HTML frameset → fetch ViewDocumentEx directly
      1c. Direct document retrieval endpoints (GetDoc, PdfPop, /api)
      2.  Parse HTML response for real download URL
      3.  clienttype=activex parameter
      4.  Playwright headless browser (fallback for JS-rendered pages)

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
        logger.info(f"    Content-Type: {content_type}")
        logger.info(f"    Content-Disposition: {content_disposition}")
        logger.info(f"    Response URL: {response.url[:120]}")
        logger.info(f"    Response size: {len(content):,} bytes")

        if is_valid:
            logger.info(f"  Downloaded {len(content):,} bytes")
            return content, ext

        # Not a valid file — save HTML for strategy 2
        html_content = content
        response_url = response.url
        # Log first 500 chars of HTML for debugging
        if content[:500].strip().lower().startswith((b'<!doctype', b'<html', b'<?xml')):
            logger.debug(f"  HTML preview: {content[:500].decode('utf-8', errors='replace')}")

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

    # --- Strategy 1.5: extract OBToken from HTML and fetch ViewDocumentEx ---
    # OnBase embeds a session-scoped OBToken in the DocPop frameset/iframe.
    # ViewDocumentEx.aspx?OBToken=<GUID> serves the actual file when called
    # with the same session cookies (ASP.NET_SessionId).
    if html_content is not None:
        obtoken_url = extract_obtoken_url(html_content, response_url or url)
        if obtoken_url:
            logger.info(f"  Strategy 1.5: found OBToken URL: {obtoken_url[:150]}")
            try:
                response = make_request_with_retry(session, obtoken_url, timeout=180,
                                                    max_manual_retries=2)
                content = response.content
                content_type = response.headers.get('Content-Type', '')
                content_disposition = response.headers.get('Content-Disposition', '')

                is_valid, ext, reason = detect_file_type(content, content_type,
                                                          content_disposition)
                logger.info(f"  Strategy 1.5 (OBToken): {reason}")
                logger.info(f"    Content-Type: {content_type}")
                logger.info(f"    Response URL: {response.url[:150]}")
                logger.info(f"    Response size: {len(content):,} bytes")

                if is_valid:
                    logger.info(f"  Downloaded {len(content):,} bytes via OBToken")
                    return content, ext

                # ViewDocumentEx returned HTML (viewer page) — search for the
                # native-document download link inside the viewer.
                viewer_download_url = extract_download_url_from_html(
                    content, response.url)
                if viewer_download_url:
                    logger.info(f"  OBToken viewer returned HTML. "
                                f"Following download link: {viewer_download_url[:120]}")
                    try:
                        resp2 = make_request_with_retry(
                            session, viewer_download_url, timeout=180,
                            max_manual_retries=2)
                        content2 = resp2.content
                        ct2 = resp2.headers.get('Content-Type', '')
                        cd2 = resp2.headers.get('Content-Disposition', '')

                        is_valid2, ext2, reason2 = detect_file_type(content2, ct2, cd2)
                        logger.info(f"  Strategy 1.5 viewer follow-up: {reason2}")

                        if is_valid2:
                            logger.info(f"  Downloaded {len(content2):,} bytes via "
                                        f"OBToken viewer link")
                            return content2, ext2
                    except Exception as e2:
                        logger.info(f"  OBToken viewer follow-up failed: {e2}")
                else:
                    logger.info("  No native download link found in OBToken viewer HTML")
            except Exception as e:
                logger.warning(f"  Strategy 1.5 (OBToken) failed: {e}")
        else:
            logger.info("  Strategy 1.5: no OBToken found in HTML response")

    # --- Strategy 1c: try direct document retrieval endpoints ---
    for i, getdoc_url in enumerate(ONBASE_GETDOC_URLS):
        try:
            logger.info(f"  Strategy 1c-{i+1}: trying direct endpoint {getdoc_url}...")
            getdoc_params = {'docid': str(docid)}
            response = make_request_with_retry(session, getdoc_url, params=getdoc_params,
                                                timeout=180, max_manual_retries=2)
            content = response.content
            content_type = response.headers.get('Content-Type', '')
            content_disposition = response.headers.get('Content-Disposition', '')

            is_valid, ext, reason = detect_file_type(content, content_type, content_disposition)
            logger.info(f"  Strategy 1c-{i+1}: {reason}")

            if is_valid:
                logger.info(f"  Downloaded {len(content):,} bytes via direct endpoint")
                return content, ext
        except Exception as e:
            logger.info(f"  Strategy 1c-{i+1}: {e}")

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

    # --- Strategy 3: alternative client types ---
    for ctype in ['activex', 'browser']:
        logger.info(f"  Trying clienttype={ctype}...")
        params_alt = {'clienttype': ctype, 'docid': str(docid)}
        try:
            response = make_request_with_retry(session, url, params=params_alt, timeout=180,
                                               max_manual_retries=2)
            content = response.content
            content_type = response.headers.get('Content-Type', '')
            content_disposition = response.headers.get('Content-Disposition', '')

            is_valid, ext, reason = detect_file_type(content, content_type, content_disposition)
            logger.info(f"  Strategy 3 ({ctype}): {reason}")

            if is_valid:
                logger.info(f"  Downloaded {len(content):,} bytes")
                return content, ext
        except Exception as e:
            logger.warning(f"  Strategy 3 ({ctype}) failed: {e}")

    # --- Strategy 4: Playwright headless browser ---
    playwright_status = 'not_installed'
    if _playwright_available():
        playwright_status = 'available'
        logger.info("  Falling back to Playwright headless browser...")
        try:
            return download_with_playwright(docid, label=label)
        except Exception as e:
            playwright_status = f'failed: {e}'
            logger.error(f"  Playwright fallback failed: {e}")
    else:
        logger.warning("  Playwright not installed. To enable browser fallback:")
        logger.warning("    pip install playwright && playwright install chromium")

    strategies_tried = "requests + direct-endpoint + HTML-parse + activex + browser"
    if playwright_status == 'not_installed':
        strategies_tried += " (Playwright NOT available — install it for headless browser fallback)"
    else:
        strategies_tried += f" + Playwright ({playwright_status})"

    raise Exception(
        f"Failed to download {label} (docid={docid}). "
        f"All strategies failed: {strategies_tried}"
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

    # Bootstrap session — visit the DocPop landing page to establish cookies.
    # OnBase returns 403 for direct document requests without a valid session.
    bootstrap_session(session)

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

    if failures:
        all_files = manifest.get('files', {})
        all_preliminary = all(
            all_files.get(str(y), {}).get('status') == 'preliminary'
            for y, _ in failures
        )

        if all_preliminary and successes:
            # Some downloads succeeded + only preliminary data failed → non-fatal
            logger.warning("Preliminary data downloads failed — treating as non-fatal "
                           "since other downloads succeeded.")
            return 0
        elif all_preliminary and not successes:
            # All downloads failed but they were all preliminary → exit 2
            # (distinct code so workflows can distinguish "no data available yet"
            # from hard errors, but still non-zero to surface the failure)
            logger.error("ALL downloads failed. No crash data was produced.")
            logger.error("OnBase may be blocking automated access or the data "
                         "may not be published yet.")
            logger.error("Check the strategy logs above for details.")
            return 2

        # Mix of final + preliminary failures, or final-only failures → hard fail
        logger.error(f"{len(failures)} download(s) failed (including finalized data).")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
