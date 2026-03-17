#!/usr/bin/env python3
"""
Delaware Crash Data — Socrata CSV Export Downloader

Downloads crash data from Delaware Department of Safety & Homeland Security
via Socrata's CSV export endpoint, which includes ALL fields (including
CRASH DATETIME and YEAR that are missing from the JSON API).

Data Source: https://data.delaware.gov
Dataset: https://data.delaware.gov/Transportation/Public-Crash-Data/827n-m6xc

NOTE: The JSON API (resource/827n-m6xc.json) uses abbreviated field names
and is missing crash_datetime and year. The CSV export endpoint returns
UPPERCASE column names including CRASH DATETIME and YEAR.

Usage:
    python download_delaware_crash_data.py --jurisdiction sussex
    python download_delaware_crash_data.py --jurisdiction new_castle --years 2023 2024
    python download_delaware_crash_data.py --gzip
    python download_delaware_crash_data.py --health-check
"""

import argparse
import csv
import gzip
import io
import json
import logging
import os
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

# CSV export has ALL fields including CRASH DATETIME and YEAR
SOCRATA_CSV_EXPORT_URL = "https://data.delaware.gov/api/views/827n-m6xc/rows.csv?accessType=DOWNLOAD"
# JSON API (used only for health check — missing datetime fields)
SOCRATA_JSON_URL = "https://data.delaware.gov/resource/827n-m6xc.json"

MAX_RETRIES = 4
RETRY_BACKOFF = [2, 4, 8, 16]

# Delaware jurisdictions: slug → COUNTY NAME value in CSV export
JURISDICTIONS = {
    "kent":       {"county_name": "Kent",       "fips": "10001"},
    "new_castle": {"county_name": "New Castle",  "fips": "10003"},
    "sussex":     {"county_name": "Sussex",      "fips": "10005"},
}

# CSV export uses UPPERCASE column names — these are the county column candidates
COUNTY_COLUMN_CANDIDATES = [
    "COUNTY NAME", "COUNTY_NAME", "county_name",
    "COUNTY DESC", "COUNTY_DESC", "county_desc",
]

# Year column candidates
YEAR_COLUMN_CANDIDATES = [
    "YEAR", "year", "CRASH YEAR", "crash_year",
]

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("delaware_downloader")


# =============================================================================
# Helper Functions
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


def health_check():
    """Test API connectivity using JSON endpoint."""
    log.info("=" * 60)
    log.info("Delaware Socrata API — Health Check")
    log.info("=" * 60)
    try:
        resp = retry_request(SOCRATA_JSON_URL, params={"$limit": 1})
        data = resp.json()
        if data:
            log.info(f"  JSON API fields: {list(data[0].keys())[:10]}...")
            log.info("  JSON API is healthy")
        # Also check CSV export
        resp2 = retry_request(SOCRATA_CSV_EXPORT_URL, stream=True)
        first_line = resp2.iter_lines(decode_unicode=True).__next__()
        resp2.close()
        cols = first_line.split(",")[:10]
        log.info(f"  CSV export columns: {cols}...")
        log.info("  CSV export is healthy")
        return True
    except Exception as e:
        log.error(f"  FAILED: {e}")
        return False


def find_column(headers, candidates):
    """Find the first matching column name from candidates."""
    header_set = set(headers)
    for c in candidates:
        if c in header_set:
            return c
    return None


def download_csv_export():
    """Download the full CSV export from Socrata.

    The CSV export endpoint returns ALL fields with UPPERCASE column names,
    including CRASH DATETIME and YEAR which are missing from the JSON API.
    """
    log.info("  Downloading full CSV export from Socrata...")
    log.info(f"  URL: {SOCRATA_CSV_EXPORT_URL}")

    resp = retry_request(SOCRATA_CSV_EXPORT_URL, stream=True)
    content_length = resp.headers.get('Content-Length')
    if content_length:
        log.info(f"  Content-Length: {int(content_length):,} bytes")

    # Read the full response
    log.info("  Streaming response...")
    raw_text = resp.text
    log.info(f"  Downloaded {len(raw_text):,} bytes")

    # Parse CSV
    reader = csv.DictReader(io.StringIO(raw_text))
    records = list(reader)
    log.info(f"  Parsed {len(records):,} records with {len(reader.fieldnames)} columns")
    log.info(f"  Columns: {reader.fieldnames}")

    return records, reader.fieldnames


def filter_records(records, headers, jurisdiction_key, years):
    """Filter records by jurisdiction and/or year range locally."""
    if not jurisdiction_key and not years:
        return records

    county_col = find_column(headers, COUNTY_COLUMN_CANDIDATES)
    year_col = find_column(headers, YEAR_COLUMN_CANDIDATES)

    filtered = records
    before = len(filtered)

    # Filter by jurisdiction
    if jurisdiction_key and jurisdiction_key in JURISDICTIONS:
        target_county = JURISDICTIONS[jurisdiction_key]["county_name"]
        if county_col:
            filtered = [r for r in filtered if r.get(county_col, '').strip() == target_county]
            log.info(f"  Filtered by {county_col}='{target_county}': {before:,} -> {len(filtered):,}")
        else:
            log.warning(f"  County column not found in headers! Tried: {COUNTY_COLUMN_CANDIDATES}")
            log.warning(f"  Available headers: {headers}")

    # Filter by year
    if years and year_col:
        before = len(filtered)
        year_strs = {str(y) for y in years}
        filtered = [r for r in filtered if r.get(year_col, '').strip() in year_strs]
        log.info(f"  Filtered by {year_col} in {sorted(years)}: {before:,} -> {len(filtered):,}")
    elif years:
        log.warning(f"  Year column not found! Tried: {YEAR_COLUMN_CANDIDATES}")

    return filtered


def save_csv(records, fieldnames, output_path, gzip_output=False):
    """Save records as CSV."""
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


def main():
    parser = argparse.ArgumentParser(
        description="Download Delaware crash data from Socrata CSV export",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --jurisdiction sussex
  %(prog)s --jurisdiction new_castle --years 2023 2024
  %(prog)s --jurisdiction kent --gzip
  %(prog)s --health-check

Available jurisdictions:
  """ + ", ".join(sorted(JURISDICTIONS.keys())),
    )
    parser.add_argument("--jurisdiction", "-j", type=str, default=None,
                        choices=list(JURISDICTIONS.keys()),
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
    args = parser.parse_args()

    if args.health_check:
        sys.exit(0 if health_check() else 1)

    # Build output filename
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
    log.info("Delaware Crash Data Downloader (CSV Export)")
    log.info(f"Started at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    log.info("=" * 60)

    if args.jurisdiction and args.jurisdiction in JURISDICTIONS:
        county_info = JURISDICTIONS[args.jurisdiction]
        log.info(f"  Jurisdiction: {county_info['county_name']} County (FIPS {county_info['fips']})")
    else:
        log.info("  Jurisdiction: statewide (all counties)")
    if args.years:
        log.info(f"  Years: {', '.join(str(y) for y in args.years)}")

    start = time.time()

    # Download full CSV export (includes CRASH DATETIME and YEAR)
    records, fieldnames = download_csv_export()
    if not records:
        log.warning("No records downloaded. Exiting.")
        sys.exit(1)

    # Filter locally by jurisdiction and/or year
    records = filter_records(records, fieldnames, args.jurisdiction, args.years)
    if not records:
        log.warning("No records after filtering. Exiting.")
        sys.exit(1)

    saved = save_csv(records, fieldnames, output_path, gzip_output=args.gzip)
    elapsed = time.time() - start
    log.info("=" * 60)
    log.info("Download complete!")
    log.info(f"  Records: {len(records):,}")
    log.info(f"  Output: {saved}")
    log.info(f"  Elapsed: {elapsed:.1f}s")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
