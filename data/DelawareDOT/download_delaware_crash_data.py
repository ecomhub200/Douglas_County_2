#!/usr/bin/env python3
"""
Delaware Crash Data — Socrata SODA API Downloader

Downloads crash data from Delaware Department of Transportation via Socrata SODA API.
Supports jurisdiction filtering, date range queries, gzip compression for R2 storage.

Data Source: https://data.delaware.gov
API: https://data.delaware.gov/resource/827n-m6xc.json

Usage:
    python download_delaware_crash_data.py --jurisdiction <county> --years 2023 2024
    python download_delaware_crash_data.py --gzip
    python download_delaware_crash_data.py --health-check
"""

import argparse
import csv
import gzip
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

SOCRATA_BASE_URL = "https://data.delaware.gov/resource/827n-m6xc.json"
SOCRATA_METADATA_URL = "https://data.delaware.gov/api/views/827n-m6xc.json"

PAGE_SIZE = 50000
MAX_RETRIES = 4
RETRY_BACKOFF = [2, 4, 8, 16]

# Delaware jurisdictions: slug → county_name value in Socrata dataset
JURISDICTIONS = {
    "kent":       {"county_name": "Kent",       "fips": "10001"},
    "new_castle": {"county_name": "New Castle",  "fips": "10003"},
    "sussex":     {"county_name": "Sussex",      "fips": "10005"},
}

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("delaware_downloader")


# =============================================================================
# Helper Functions
# =============================================================================

def retry_request(url, params=None, max_retries=MAX_RETRIES):
    """Make HTTP GET with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=120)
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
    """Test API connectivity."""
    log.info("=" * 60)
    log.info("Delaware Socrata API — Health Check")
    log.info("=" * 60)
    try:
        resp = retry_request(SOCRATA_BASE_URL, params={"$limit": 1})
        data = resp.json()
        if data:
            log.info(f"  Sample record keys: {list(data[0].keys())[:10]}...")
            log.info("  ✓ API is healthy")
            return True
        log.warning("  Empty response")
        return False
    except Exception as e:
        log.error(f"  FAILED: {e}")
        return False


def build_where_clause(jurisdiction_key, years):
    """Build SoQL $where clause for filtering."""
    clauses = []

    # Jurisdiction filter (county_name field in Delaware dataset)
    if jurisdiction_key and jurisdiction_key in JURISDICTIONS:
        county_name = JURISDICTIONS[jurisdiction_key]["county_name"]
        clauses.append(f"county_name='{county_name}'")

    # Year filter (crash_datetime is a floating_timestamp in Socrata)
    if years:
        year_clauses = []
        for year in years:
            start = f"{year}-01-01T00:00:00.000"
            end = f"{year}-12-31T23:59:59.999"
            year_clauses.append(f"(crash_datetime>='{start}' AND crash_datetime<='{end}')")
        if len(year_clauses) == 1:
            clauses.append(year_clauses[0])
        else:
            clauses.append(f"({' OR '.join(year_clauses)})")

    return " AND ".join(clauses) if clauses else None


def download_data(jurisdiction_key, years):
    """Download crash data from Socrata API with pagination."""
    where_clause = build_where_clause(jurisdiction_key, years)

    log.info(f"Downloading Delaware crash data...")
    if jurisdiction_key and jurisdiction_key in JURISDICTIONS:
        county_info = JURISDICTIONS[jurisdiction_key]
        log.info(f"  Jurisdiction: {county_info['county_name']} County (FIPS {county_info['fips']})")
    else:
        log.info(f"  Jurisdiction: statewide (all counties)")
    if years:
        log.info(f"  Years: {', '.join(str(y) for y in years)}")
    if where_clause:
        log.info(f"  SoQL filter: $where={where_clause}")

    all_records = []
    offset = 0
    page = 1
    while True:
        params = {"$limit": PAGE_SIZE, "$offset": offset, "$order": ":id"}
        if where_clause:
            params["$where"] = where_clause
        log.info(f"  Page {page}: offset={offset}, limit={PAGE_SIZE}")
        resp = retry_request(SOCRATA_BASE_URL, params=params)
        records = resp.json()
        if not records:
            log.info(f"  No more records at offset {offset}")
            break
        all_records.extend(records)
        log.info(f"  Received {len(records)} records (total: {len(all_records)})")
        if len(records) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        page += 1
        time.sleep(0.5)

    log.info(f"  Total records downloaded: {len(all_records)}")
    return all_records


def save_csv(records, output_path, gzip_output=False):
    """Save records as CSV."""
    if not records:
        return None
    fieldnames = list(dict.fromkeys(k for r in records for k in r.keys()))
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
        description="Download Delaware crash data from Socrata SODA API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --jurisdiction sussex --years 2023 2024
  %(prog)s --jurisdiction new_castle --gzip
  %(prog)s --health-check
  %(prog)s --gzip  # Download all statewide data, gzip compressed

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
    log.info(f"Delaware Crash Data Downloader")
    log.info(f"Started at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    log.info("=" * 60)

    start = time.time()
    records = download_data(args.jurisdiction, args.years)
    if not records:
        log.warning("No records downloaded. Exiting.")
        sys.exit(1)

    saved = save_csv(records, output_path, gzip_output=args.gzip)
    elapsed = time.time() - start
    log.info("=" * 60)
    log.info(f"Download complete!")
    log.info(f"  Records: {len(records):,}")
    log.info(f"  Output: {saved}")
    log.info(f"  Elapsed: {elapsed:.1f}s")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
