#!/usr/bin/env python3
"""
Delaware Crash Data — Dual-Strategy Downloader (v2)

Strategy:
  1. PRIMARY: Socrata CSV Export API (fast, no browser needed)
  2. FALLBACK: Playwright browser-routed ArcGIS FeatureServer pagination
     (bypasses bot detection when Socrata blocks server IPs)

Data Sources:
  - Socrata: https://data.delaware.gov/Transportation/Public-Crash-Data/827n-m6xc
  - ArcGIS Hub: https://de-firstmap-delaware.hub.arcgis.com/datasets/delaware::delaware-public-crash-data-2-0

Usage:
    python download_delaware_crash_data.py --jurisdiction sussex
    python download_delaware_crash_data.py --jurisdiction statewide --gzip
    python download_delaware_crash_data.py --strategy playwright --force
    python download_delaware_crash_data.py --health-check
"""

import argparse
import csv
import gzip
import io
import json
import logging
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install with: pip install requests")
    sys.exit(1)

# =============================================================================
# Constants
# =============================================================================

SCRIPT_DIR = Path(__file__).parent.resolve()

# Socrata endpoints (PRIMARY)
SOCRATA_CSV_EXPORT_URL = "https://data.delaware.gov/api/views/827n-m6xc/rows.csv?accessType=DOWNLOAD"
SOCRATA_JSON_URL = "https://data.delaware.gov/resource/827n-m6xc.json"
SOCRATA_SODA_CSV_URL = "https://data.delaware.gov/resource/827n-m6xc.csv"

# ArcGIS Hub (FALLBACK — Playwright)
ARCGIS_HUB_URL = "https://de-firstmap-delaware.hub.arcgis.com/datasets/delaware::delaware-public-crash-data-2-0/explore"

# Known ArcGIS FeatureServer URLs for Delaware crash data
KNOWN_FEATURE_SERVERS = [
    "https://services1.arcgis.com/PlCPCPzGOwulHGCj/arcgis/rest/services/Delaware_Public_Crash_Data_2_0/FeatureServer/0",
    "https://services1.arcgis.com/PlCPCPzGOwulHGCj/arcgis/rest/services/Public_Crash_Data/FeatureServer/0",
]

CACHE_PATH = SCRIPT_DIR / ".delaware_featureserver_cache.json"

MAX_RETRIES = 4
RETRY_BACKOFF = [2, 4, 8, 16]

# Delaware jurisdictions
JURISDICTIONS = {
    "kent":       {"county_name": "Kent",       "fips": "10001"},
    "new_castle": {"county_name": "New Castle",  "fips": "10003"},
    "sussex":     {"county_name": "Sussex",      "fips": "10005"},
}
VALID_JURISDICTIONS = list(JURISDICTIONS.keys()) + ["statewide"]

COUNTY_COLUMN_CANDIDATES = [
    "COUNTY NAME", "COUNTY_NAME", "county_name", "COUNTY_DESC", "county_desc",
]
YEAR_COLUMN_CANDIDATES = [
    "YEAR", "year", "CRASH YEAR", "crash_year",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("delaware_downloader")


# =============================================================================
# Shared Helpers
# =============================================================================

def find_column(headers, candidates):
    """Find the first matching column name from candidates."""
    header_set = set(headers)
    for c in candidates:
        if c in header_set:
            return c
    return None


def filter_records(records, headers, jurisdiction_key, years):
    """Filter records by jurisdiction and/or year range locally."""
    if not jurisdiction_key and not years:
        return records

    county_col = find_column(headers, COUNTY_COLUMN_CANDIDATES)
    year_col = find_column(headers, YEAR_COLUMN_CANDIDATES)
    filtered = records
    before = len(filtered)

    if jurisdiction_key and jurisdiction_key in JURISDICTIONS:
        target_county = JURISDICTIONS[jurisdiction_key]["county_name"]
        if county_col:
            filtered = [r for r in filtered if r.get(county_col, "").strip() == target_county]
            log.info(f"  Filtered by {county_col}='{target_county}': {before:,} -> {len(filtered):,}")
        else:
            log.warning(f"  County column not found! Tried: {COUNTY_COLUMN_CANDIDATES}")

    if years and year_col:
        before = len(filtered)
        year_strs = {str(y) for y in years}
        filtered = [r for r in filtered if r.get(year_col, "").strip() in year_strs]
        log.info(f"  Filtered by {year_col} in {sorted(years)}: {before:,} -> {len(filtered):,}")
    elif years:
        log.warning(f"  Year column not found! Tried: {YEAR_COLUMN_CANDIDATES}")

    return filtered


def save_csv(records, fieldnames, output_path, gzip_output=False):
    """Save records as CSV (plain or gzipped)."""
    if not records:
        return None
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    if gzip_output:
        gz_path = str(output_path) + ".gz"
        with gzip.open(gz_path, "wt", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        log.info(f"  Saved: {gz_path} ({os.path.getsize(gz_path):,} bytes)")
        return gz_path
    else:
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        log.info(f"  Saved: {output_path} ({os.path.getsize(output_path):,} bytes)")
        return str(output_path)


def validate_csv(path):
    """Validate downloaded CSV is real data, not an error page."""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            head = f.read(500)
        if "<html" in head.lower() or "Cannot fetch" in head:
            log.error("  Error page detected, not CSV data")
            return False
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            headers = next(reader)
    except Exception as e:
        log.error(f"  CSV validation error: {e}")
        return False

    rows = sum(1 for _ in open(path, encoding="utf-8-sig")) - 1
    log.info(f"  CSV validated: {len(headers)} columns, {rows:,} records")
    return rows > 0


# =============================================================================
# STRATEGY 1: Socrata API (PRIMARY)
# =============================================================================

def retry_request(url, params=None, max_retries=MAX_RETRIES, stream=False):
    """Make HTTP GET with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=300, stream=stream)
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait = RETRY_BACKOFF[attempt]
                log.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(wait)
            else:
                raise


def download_socrata(jurisdiction_key=None, years=None):
    """Download crash data via Socrata API. Returns (records, fieldnames) or raises."""
    where_clauses = []
    if jurisdiction_key and jurisdiction_key in JURISDICTIONS:
        county = JURISDICTIONS[jurisdiction_key]["county_name"]
        where_clauses.append(f"county_desc='{county}'")
    if years:
        year_list = ",".join(str(y) for y in years)
        where_clauses.append(f"year in({year_list})")

    if where_clauses:
        where = " AND ".join(where_clauses)
        params = {"$where": where, "$limit": 500000}
        log.info(f"  Downloading via SODA CSV with filter: {where}")
        resp = retry_request(SOCRATA_SODA_CSV_URL, params=params)
        raw_text = resp.text
        log.info(f"  Downloaded {len(raw_text):,} bytes")
        reader = csv.DictReader(io.StringIO(raw_text))
        records = list(reader)
        fieldnames = reader.fieldnames or []
        log.info(f"  Parsed {len(records):,} records with {len(fieldnames)} columns")
        if records and "crash_datetime" not in fieldnames and "CRASH DATETIME" not in fieldnames:
            log.warning("  SODA CSV missing crash_datetime — falling back to full CSV export")
        else:
            return records, fieldnames

    log.info("  Downloading full CSV export from Socrata...")
    resp = retry_request(SOCRATA_CSV_EXPORT_URL)
    content_length = resp.headers.get("Content-Length")
    if content_length:
        log.info(f"  Content-Length: {int(content_length):,} bytes")
    raw_text = resp.text
    log.info(f"  Downloaded {len(raw_text):,} bytes")
    reader = csv.DictReader(io.StringIO(raw_text))
    records = list(reader)
    log.info(f"  Parsed {len(records):,} records with {len(reader.fieldnames)} columns")
    return records, reader.fieldnames


def health_check():
    """Test API connectivity."""
    log.info("=" * 60)
    log.info("Delaware API — Health Check")
    log.info("=" * 60)
    ok = True

    # Socrata
    try:
        resp = retry_request(SOCRATA_JSON_URL, params={"$limit": 1})
        data = resp.json()
        if data:
            log.info(f"  Socrata JSON API: healthy ({list(data[0].keys())[:5]}...)")
    except Exception as e:
        log.error(f"  Socrata JSON API: FAILED ({e})")
        ok = False

    try:
        resp2 = retry_request(SOCRATA_CSV_EXPORT_URL, stream=True)
        first_line = next(resp2.iter_lines(decode_unicode=True))
        resp2.close()
        log.info(f"  Socrata CSV export: healthy ({first_line[:80]}...)")
    except Exception as e:
        log.error(f"  Socrata CSV export: FAILED ({e})")
        ok = False

    # ArcGIS FeatureServer (quick check via requests — may 403)
    for fs_url in KNOWN_FEATURE_SERVERS:
        try:
            r = requests.get(f"{fs_url}/query?where=1%3D1&returnCountOnly=true&f=json", timeout=30)
            if r.ok:
                count = r.json().get("count", 0)
                log.info(f"  ArcGIS FeatureServer: {count:,} records (direct API)")
                break
            else:
                log.info(f"  ArcGIS FeatureServer: HTTP {r.status_code} (may need Playwright)")
        except Exception as e:
            log.info(f"  ArcGIS FeatureServer: {e} (may need Playwright)")

    return ok


# =============================================================================
# STRATEGY 2: Playwright ArcGIS Hub (FALLBACK)
# =============================================================================

def load_cached_url():
    """Load cached FeatureServer URL."""
    if CACHE_PATH.exists():
        try:
            data = json.loads(CACHE_PATH.read_text())
            url = data.get("url", "")
            if url:
                log.info(f"  Cached FeatureServer: {url}")
                return url
        except Exception:
            pass
    return None


def save_cached_url(url):
    """Save discovered FeatureServer URL to cache."""
    try:
        CACHE_PATH.write_text(json.dumps({
            "url": url,
            "discovered": datetime.now().isoformat(),
        }))
    except Exception:
        pass


def browser_fetch_json(page, url, retries=5):
    """Make a fetch() call FROM the browser context to bypass bot detection."""
    for attempt in range(retries):
        try:
            result = page.evaluate(f"""
                async () => {{
                    try {{
                        const resp = await fetch("{url}");
                        if (!resp.ok) return {{error: 'HTTP ' + resp.status}};
                        const text = await resp.text();
                        return JSON.parse(text);
                    }} catch(e) {{
                        return {{error: e.message}};
                    }}
                }}
            """)
            if result and "error" not in result:
                return result
            err = result.get("error", "unknown") if result else "null response"
            if attempt < retries - 1:
                wait = min(15, 2 ** attempt)
                log.info(f"    fetch error: {err}, retry {attempt+1} in {wait}s...")
                time.sleep(wait)
            else:
                log.error(f"    fetch failed after {retries} attempts: {err}")
                return None
        except Exception as e:
            if attempt < retries - 1:
                wait = min(15, 2 ** attempt)
                log.info(f"    exception: {e}, retry {attempt+1} in {wait}s...")
                time.sleep(wait)
            else:
                log.error(f"    exception after {retries} attempts: {e}")
                return None
    return None


def download_with_playwright(output_path, headless=True, batch_size=5000):
    """
    Playwright-based download from ArcGIS FeatureServer.
    Opens browser → establishes session → discovers FeatureServer → paginates all records.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()

            # ==============================================================
            # Step 1: Load ArcGIS Hub page (establish cookies/session)
            # ==============================================================
            log.info("Step 1: Loading ArcGIS Hub page to establish session...")

            discovered_fs_urls = []

            def on_request(request):
                url = request.url
                if "FeatureServer" in url:
                    discovered_fs_urls.append(url)
                if "replicafilescache" in url:
                    discovered_fs_urls.append(url)

            page.on("request", on_request)
            page.goto(ARCGIS_HUB_URL, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)
            log.info(f"  Page loaded: {page.title()}")

            # ==============================================================
            # Step 2: Discover FeatureServer URL
            # ==============================================================
            log.info("Step 2: Finding FeatureServer URL...")

            service_url = None
            total_count = 0

            # Try cached URL first
            cached = load_cached_url()
            if cached:
                count_url = f"{cached}/query?where=1%3D1&returnCountOnly=true&f=json"
                data = browser_fetch_json(page, count_url, retries=2)
                if data and "count" in data and data["count"] > 10000:
                    service_url = cached
                    total_count = data["count"]
                    log.info(f"  Cached URL works: {total_count:,} records")

            # Discover from network traffic
            if not service_url:
                log.info("  Triggering download to discover URL...")
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

                # Click CSV download button to trigger FeatureServer request
                try:
                    btns = page.locator(
                        'a:has-text("Download"), button:has-text("Download"), calcite-button:has-text("Download")'
                    ).all()
                    for btn in btns:
                        try:
                            if not btn.is_visible(timeout=1000):
                                continue
                            text = btn.inner_text().strip()
                            bbox = btn.bounding_box()
                            if "Recent" in text or (bbox and bbox["y"] < 200):
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
                        r"(https://services\d*\.arcgis\.com/[^/]+/arcgis/rest/services/[^/]+/FeatureServer)",
                        url,
                    )
                    if match:
                        candidate = match.group(1) + "/0"
                        count_url = f"{candidate}/query?where=1%3D1&returnCountOnly=true&f=json"
                        data = browser_fetch_json(page, count_url, retries=3)
                        if data and "count" in data and data["count"] > 10000:
                            service_url = candidate
                            total_count = data["count"]
                            save_cached_url(service_url)
                            log.info(f"  Discovered: {service_url} ({total_count:,} records)")
                            break

            # Try known URLs as last resort
            if not service_url:
                log.info("  Trying known FeatureServer URLs via browser fetch...")
                for url in KNOWN_FEATURE_SERVERS:
                    svc_name = url.split("/")[-3]
                    count_url = f"{url}/query?where=1%3D1&returnCountOnly=true&f=json"
                    data = browser_fetch_json(page, count_url, retries=3)
                    if data and "count" in data:
                        count = data["count"]
                        log.info(f"  {svc_name}: {count:,} records")
                        if count > 10000:
                            service_url = url
                            total_count = count
                            save_cached_url(service_url)
                            break
                    else:
                        log.info(f"  {svc_name}: failed")

            if not service_url:
                log.error("  No working FeatureServer found")
                browser.close()
                return False

            log.info(f"  Using: {service_url}")
            log.info(f"  Total records: {total_count:,}")

            # ==============================================================
            # Step 3: Get field schema
            # ==============================================================
            log.info("Step 3: Fetching field schema...")
            schema_url = f"{service_url}?f=json"
            schema = browser_fetch_json(page, schema_url)

            if not schema or "fields" not in schema:
                log.error("  Could not get field schema")
                browser.close()
                return False

            fields = schema["fields"]
            has_geometry = "Point" in schema.get("geometryType", "")
            fieldnames = [f["name"] for f in fields]
            if has_geometry:
                fieldnames.extend(["x", "y"])

            log.info(f"  {len(fields)} fields, geometry={has_geometry}")
            log.info(f"  Fields: {', '.join(fieldnames[:10])}...")

            # ==============================================================
            # Step 4: Paginate all records via browser fetch()
            # ==============================================================
            log.info(f"Step 4: Downloading {total_count:,} records ({batch_size}/batch)...")

            temp_path = str(output_path) + ".partial"
            offset = 0
            total_written = 0
            start_time = time.time()
            consecutive_errors = 0
            max_consecutive_errors = 10

            query_base = f"{service_url}/query"

            with open(temp_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()

                while offset < total_count + batch_size:
                    pct = min(100, int(offset / max(total_count, 1) * 100))
                    elapsed = time.time() - start_time
                    rate = total_written / max(elapsed, 0.1)
                    eta = (total_count - total_written) / max(rate, 0.1)

                    if offset % (batch_size * 5) == 0 or offset == 0:
                        log.info(
                            f"  {total_written:,} / {total_count:,} ({pct}%) "
                            f"| {rate:.0f} rec/s | ETA {eta/60:.1f} min"
                        )

                    params = (
                        f"?where=1%3D1"
                        f"&outFields=*"
                        f"&resultOffset={offset}"
                        f"&resultRecordCount={batch_size}"
                        f"&orderByFields=OBJECTID+ASC"
                        f"&f=json"
                    )
                    if has_geometry:
                        params += "&outSR=4326"

                    fetch_url = query_base + params
                    data = browser_fetch_json(page, fetch_url, retries=5)

                    if data is None:
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            log.error(f"  {max_consecutive_errors} consecutive errors, stopping")
                            break
                        log.info("  Refreshing page to reset session...")
                        page.goto(ARCGIS_HUB_URL, wait_until="networkidle", timeout=60000)
                        page.wait_for_timeout(3000)
                        continue

                    if "error" in data:
                        err = data["error"]
                        log.warning(f"  API error at offset {offset}: {err}")
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            break
                        time.sleep(2)
                        continue

                    features = data.get("features", [])
                    if not features:
                        break

                    consecutive_errors = 0

                    for feat in features:
                        row = feat.get("attributes", {})
                        geom = feat.get("geometry")
                        if geom and has_geometry:
                            row["x"] = geom.get("x", "")
                            row["y"] = geom.get("y", "")
                        writer.writerow(row)
                        total_written += 1

                    offset += len(features)
                    if len(features) < batch_size:
                        break

            browser.close()

            elapsed = time.time() - start_time
            log.info(f"  Downloaded {total_written:,} records in {elapsed/60:.1f} min")
            log.info(f"  Average: {total_written/max(elapsed,1):.0f} rec/s")

            if total_written == 0:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return False

            if total_written < total_count * 0.95:
                log.warning(
                    f"  Got {total_written:,} of {total_count:,} "
                    f"({total_written/total_count*100:.1f}%)"
                )

            # Atomic move: temp → final
            output_str = str(output_path)
            if os.path.exists(output_str):
                for attempt in range(5):
                    try:
                        os.remove(output_str)
                        break
                    except PermissionError:
                        if attempt < 4:
                            log.info(f"  File locked, retrying in {attempt+1}s...")
                            time.sleep(attempt + 1)
                        else:
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            alt_path = output_str.replace(".csv", f"_{ts}.csv")
                            shutil.move(temp_path, alt_path)
                            log.warning(f"  Old file locked — saved as: {alt_path}")
                            return True

            shutil.move(temp_path, output_str)
            size = os.path.getsize(output_str)
            log.info(f"  Saved: {output_str} ({size/(1024*1024):.1f} MB)")
            return True

    except Exception as e:
        log.error(f"  Playwright fatal error: {e}")
        import traceback
        traceback.print_exc()
        return False


# =============================================================================
# Main — Dual-Strategy Orchestrator
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Download Delaware crash data (Socrata primary, Playwright fallback)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Strategy:
  auto       Try Socrata API first, fall back to Playwright if blocked (default)
  socrata    Socrata API only (no Playwright)
  playwright Playwright browser-based download only (ArcGIS Hub)

Examples:
  %(prog)s --jurisdiction sussex
  %(prog)s --jurisdiction statewide --gzip
  %(prog)s --strategy playwright --force
  %(prog)s --health-check

Available jurisdictions: """ + ", ".join(sorted(VALID_JURISDICTIONS)),
    )
    parser.add_argument("--jurisdiction", "-j", type=str, default=None,
                        choices=VALID_JURISDICTIONS,
                        help="County to filter to (default: all statewide)")
    parser.add_argument("--years", "-y", type=int, nargs="+", default=None,
                        help="Years to download (e.g., --years 2023 2024)")
    parser.add_argument("--data-dir", "-d", type=str, default="data/DelawareDOT",
                        help="Output directory (default: data/DelawareDOT)")
    parser.add_argument("--gzip", "-g", action="store_true",
                        help="Output gzip-compressed CSV (.csv.gz) for R2 storage")
    parser.add_argument("--health-check", action="store_true",
                        help="Test API connectivity and exit")
    parser.add_argument("--force", action="store_true",
                        help="Force re-download even if output file already exists")
    parser.add_argument("--strategy", "-s", type=str, default="auto",
                        choices=["auto", "socrata", "playwright"],
                        help="Download strategy (default: auto)")
    parser.add_argument("--headful", action="store_true",
                        help="Show browser window (Playwright only)")
    parser.add_argument("--batch-size", type=int, default=5000,
                        help="Records per request (Playwright only, default: 5000)")
    args = parser.parse_args()

    if args.health_check:
        sys.exit(0 if health_check() else 1)

    jurisdiction_key = args.jurisdiction
    if jurisdiction_key == "statewide":
        jurisdiction_key = None

    jurisdiction = args.jurisdiction or "statewide"
    year_suffix = ""
    if args.years:
        if len(args.years) == 1:
            year_suffix = f"_{args.years[0]}"
        else:
            year_suffix = f"_{min(args.years)}-{max(args.years)}"

    output_filename = f"{jurisdiction}{year_suffix}_crashes.csv"
    output_path = Path(args.data_dir) / output_filename

    gz_path = Path(str(output_path) + ".gz")
    if not args.force and (output_path.exists() or gz_path.exists()):
        existing = gz_path if gz_path.exists() else output_path
        log.info(f"Output already exists: {existing}")
        log.info("Use --force to re-download")
        sys.exit(0)

    log.info("=" * 60)
    log.info("Delaware Crash Data Downloader v2 (Dual-Strategy)")
    log.info(f"  Strategy: {args.strategy}")
    log.info(f"  Started:  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    log.info("=" * 60)

    if jurisdiction_key and jurisdiction_key in JURISDICTIONS:
        county_info = JURISDICTIONS[jurisdiction_key]
        log.info(f"  Jurisdiction: {county_info['county_name']} County (FIPS {county_info['fips']})")
    else:
        log.info("  Jurisdiction: statewide (all counties)")
    if args.years:
        log.info(f"  Years: {', '.join(str(y) for y in args.years)}")

    start = time.time()
    records = None
    fieldnames = None
    strategy_used = None

    # ── Strategy: Socrata API (primary) ──
    if args.strategy in ("auto", "socrata"):
        log.info("")
        log.info("─── Strategy 1: Socrata API ───")
        try:
            records, fieldnames = download_socrata(jurisdiction_key, args.years)
            if records and len(records) > 0:
                strategy_used = "socrata"
                log.info(f"  Socrata succeeded: {len(records):,} records")
            else:
                log.warning("  Socrata returned 0 records")
                records = None
        except Exception as e:
            log.warning(f"  Socrata FAILED: {e}")
            records = None

    # ── Strategy: Playwright ArcGIS Hub (fallback) ──
    if records is None and args.strategy in ("auto", "playwright"):
        log.info("")
        log.info("─── Strategy 2: Playwright ArcGIS Hub (fallback) ───")
        Path(args.data_dir).mkdir(parents=True, exist_ok=True)

        success = download_with_playwright(
            output_path,
            headless=not args.headful,
            batch_size=args.batch_size,
        )

        if success and output_path.exists():
            strategy_used = "playwright"
            # Read back for filtering/gzip if needed
            with open(output_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                records = list(reader)
                fieldnames = reader.fieldnames
            log.info(f"  Playwright succeeded: {len(records):,} records")
        else:
            log.error("  Playwright also FAILED")

    if not records:
        log.error("All download strategies failed. Exiting.")
        sys.exit(1)

    # Apply local filtering (safety net for both strategies)
    records = filter_records(records, fieldnames, jurisdiction_key, args.years)
    if not records:
        log.warning("No records after filtering. Exiting.")
        sys.exit(1)

    # Save final output
    if strategy_used == "playwright" and not jurisdiction_key and not args.years and not args.gzip:
        # Playwright already wrote the file, no re-save needed
        pass
    else:
        save_csv(records, fieldnames, output_path, gzip_output=args.gzip)

    elapsed = time.time() - start
    log.info("")
    log.info("=" * 60)
    log.info("Download complete!")
    log.info(f"  Strategy: {strategy_used}")
    log.info(f"  Records:  {len(records):,}")
    log.info(f"  Output:   {output_path}")
    log.info(f"  Elapsed:  {elapsed:.1f}s")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
