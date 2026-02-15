#!/usr/bin/env python3
"""
Create R2 folder structure for crash-lens-data bucket.

Creates zero-byte marker objects in Cloudflare R2 (S3-compatible) to establish
the complete folder hierarchy for all states and jurisdictions.

Usage:
    python create_r2_folders.py [--dry-run] [--state STATE_PREFIX]

Environment variables required:
    CF_ACCOUNT_ID          - Cloudflare Account ID
    CF_R2_ACCESS_KEY_ID    - R2 Access Key ID
    CF_R2_SECRET_ACCESS_KEY - R2 Secret Access Key

Optional:
    R2_BUCKET              - Bucket name (default: crash-lens-data)
"""

import os
import sys
import json
import time
import argparse
import subprocess
from pathlib import Path

BUCKET = os.environ.get("R2_BUCKET", "crash-lens-data")
ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "")
ENDPOINT = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"

# ─── State Prefixes & Data Directories ───────────────────────────────────────
# Maps R2 state prefix → data directory name (relative to data/)
STATE_MAP = {
    "virginia":       None,          # Jurisdictions from config.json
    "colorado":       "CDOT",
    "maryland":       "MarylandDOT",
    "connecticut":    "ConnecticutDOT",
    "delaware":       "DelawareDOT",
    "new_york":       "NewYorkDOT",
    "nyc":            "NYCDOT",
    "hawaii":         "HawaiiDOT",
    "iowa":           "IowaDOT",
    "illinois":       "IllinoisDOT",
    "louisiana":      "LouisianaDOT",
    "alaska":         "AlaskaDOT",
    "massachusetts":  "MassachusettsDOT",
    "pennsylvania":   "PennsylvaniaDOT",
    "florida":        "FloridaDOT",
    "georgia":        "GeorgiaDOT",
    "south_carolina": "SouthCarolinaDOT",
    "ohio":           "OhioDOT",
    "wisconsin":      "WisconsinDOT",
    "nevada":         "NevadaDOT",
    "utah":           "UtahDOT",
    "oregon":         "OregonDOT",
    "washington":     "WashingtonDOT",
    "idaho":          "IdahoDOT",
    "montana":        "MontanaDOT",
    "west_virginia":  "WestVirginiaDOT",
    "mississippi":    "MississippiDOT",
    "oklahoma":       "OklahomaDOT",
    "arkansas":       "ArkansasDOT",
    "vermont":        "VermontDOT",
    "texas":          "TexasDOT",
}

# Known jurisdiction lists for states without source_manifest.json jurisdiction_filters
# These are the standard US county/jurisdiction lists used as R2 folder names
KNOWN_JURISDICTIONS = {
    "connecticut": [
        "fairfield", "hartford", "litchfield", "middlesex",
        "new_haven", "new_london", "tolland", "windham"
    ],
    "delaware": ["kent", "new_castle", "sussex"],
    "hawaii": ["hawaii", "honolulu", "kauai", "maui"],
    "nyc": ["bronx", "brooklyn", "manhattan", "queens", "staten_island"],
    "alaska": [
        "anchorage", "fairbanks_north_star", "matanuska_susitna", "kenai_peninsula",
        "juneau", "bethel", "nome", "north_slope", "northwest_arctic", "kodiak_island",
        "valdez_cordova", "southeast_fairbanks", "denali", "dillingham", "haines",
        "ketchikan_gateway", "lake_and_peninsula", "prince_of_wales_hyder",
        "sitka", "skagway", "wrangell", "yakutat", "aleutians_east",
        "aleutians_west", "bristol_bay", "hoonah_angoon", "kusilvak",
        "petersburg", "yukon_koyukuk", "copper_river"
    ],
    "vermont": [
        "addison", "bennington", "caledonia", "chittenden", "essex",
        "franklin", "grand_isle", "lamoille", "orange", "orleans",
        "rutland", "washington", "windham", "windsor"
    ],
}


def get_project_root():
    """Get project root directory."""
    return Path(__file__).resolve().parent.parent


def load_virginia_jurisdictions(project_root):
    """Load Virginia jurisdiction keys from config.json."""
    config_path = project_root / "config.json"
    if not config_path.exists():
        print(f"  [WARN] config.json not found at {config_path}")
        return []
    with open(config_path) as f:
        config = json.load(f)
    jurisdictions = list(config.get("jurisdictions", {}).keys())
    # Filter out separators and Colorado legacy entries
    return [j for j in jurisdictions
            if not j.startswith("_") and not j.startswith("co_")]


def load_jurisdictions_from_manifest(project_root, data_dir):
    """Load jurisdiction keys from a state's source_manifest.json."""
    manifest_path = project_root / "data" / data_dir / "source_manifest.json"
    if not manifest_path.exists():
        return []
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
        filters = manifest.get("jurisdiction_filters", {})
        # Filter out metadata keys starting with _
        return [k for k in filters.keys() if not k.startswith("_")]
    except (json.JSONDecodeError, KeyError):
        return []


def get_jurisdictions(state_prefix, project_root):
    """Get jurisdiction list for a given state prefix."""
    if state_prefix == "virginia":
        return load_virginia_jurisdictions(project_root)

    data_dir = STATE_MAP.get(state_prefix)
    if data_dir:
        jurisdictions = load_jurisdictions_from_manifest(project_root, data_dir)
        if jurisdictions:
            return jurisdictions

    # Fall back to known jurisdictions
    if state_prefix in KNOWN_JURISDICTIONS:
        return KNOWN_JURISDICTIONS[state_prefix]

    return []


def generate_all_folders(state_filter=None):
    """Generate the complete list of R2 folder paths to create."""
    project_root = get_project_root()
    folders = []

    # ── Top-level folders ──
    folders.extend([
        "_federal/",
        "_national/",
        "_national/snapshots/",
        "shared/",
        "shared/boundaries/",
        "shared/mutcd/",
    ])

    # ── Per-state folders ──
    states = STATE_MAP.keys()
    if state_filter:
        states = [s for s in states if s == state_filter]

    for state_prefix in sorted(states):
        print(f"\n  Processing: {state_prefix}")

        # State-level meta folders
        folders.extend([
            f"{state_prefix}/",
            f"{state_prefix}/_state/",
            f"{state_prefix}/_statewide/",
            f"{state_prefix}/_statewide/snapshots/",
        ])

        # Load jurisdictions
        jurisdictions = get_jurisdictions(state_prefix, project_root)
        print(f"    Found {len(jurisdictions)} jurisdictions")

        # Jurisdiction folders
        for j in sorted(jurisdictions):
            folders.append(f"{state_prefix}/{j}/")
            folders.append(f"{state_prefix}/{j}/raw/")

    return folders


def create_folder_via_cli(folder_key, dry_run=False):
    """Create a single folder marker in R2 using AWS CLI."""
    s3_uri = f"s3://{BUCKET}/{folder_key}"

    if dry_run:
        print(f"  [DRY-RUN] Would create: {folder_key}")
        return True

    cmd = [
        "aws", "s3api", "put-object",
        "--bucket", BUCKET,
        "--key", folder_key,
        "--content-length", "0",
        "--endpoint-url", ENDPOINT,
    ]

    for attempt in range(3):
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return True
            print(f"  [WARN] Attempt {attempt+1} failed for {folder_key}: {result.stderr.strip()}")
        except subprocess.TimeoutExpired:
            print(f"  [WARN] Timeout on attempt {attempt+1} for {folder_key}")
        if attempt < 2:
            time.sleep(2 ** attempt)

    print(f"  [ERROR] Failed to create: {folder_key}")
    return False


def create_folders_batch(folders, dry_run=False):
    """Create all folders, reporting progress."""
    total = len(folders)
    created = 0
    failed = 0

    print(f"\n{'='*60}")
    print(f"Creating {total} folders in R2 bucket: {BUCKET}")
    print(f"Endpoint: {ENDPOINT}")
    print(f"{'='*60}\n")

    for i, folder in enumerate(folders, 1):
        if i % 50 == 0 or i == total:
            print(f"  Progress: {i}/{total} ({i*100//total}%)")

        if create_folder_via_cli(folder, dry_run=dry_run):
            created += 1
        else:
            failed += 1

    print(f"\n{'='*60}")
    print(f"RESULTS: {created} created, {failed} failed, {total} total")
    print(f"{'='*60}")

    return failed == 0


def main():
    parser = argparse.ArgumentParser(description="Create R2 folder structure")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print folders without creating them")
    parser.add_argument("--state", type=str, default=None,
                        help="Only create folders for a specific state prefix")
    parser.add_argument("--list-only", action="store_true",
                        help="Just list all folder paths and exit")
    args = parser.parse_args()

    # Validate environment
    if not args.dry_run and not args.list_only:
        if not ACCOUNT_ID:
            print("ERROR: CF_ACCOUNT_ID environment variable required")
            sys.exit(1)
        if not os.environ.get("AWS_ACCESS_KEY_ID"):
            print("ERROR: AWS_ACCESS_KEY_ID environment variable required")
            sys.exit(1)

    print("Generating R2 folder structure...")
    folders = generate_all_folders(state_filter=args.state)

    if args.list_only:
        print(f"\nTotal folders: {len(folders)}\n")
        for f in folders:
            print(f"  {f}")
        return

    print(f"\nTotal folders to create: {len(folders)}")

    if args.dry_run:
        print("\n[DRY-RUN MODE] No changes will be made.\n")

    success = create_folders_batch(folders, dry_run=args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
