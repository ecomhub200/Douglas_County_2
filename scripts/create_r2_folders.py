#!/usr/bin/env python3
"""
Create R2 folder structure for crash-lens-data bucket.

Creates zero-byte marker objects in Cloudflare R2 (S3-compatible) to establish
the complete folder hierarchy for all 50 US states + DC.

Reads from:
  - states/{state}/hierarchy.json — regions, MPOs/TPRs, allCounties (all 51)
  - config.json — Virginia jurisdiction keys (authoritative, includes independent cities)
  - data/{State}DOT/source_manifest.json — CO, MD jurisdiction keys (authoritative)

Usage:
    python create_r2_folders.py [--dry-run] [--state STATE_PREFIX] [--list-only]

Environment variables required (for actual R2 creation):
    CF_ACCOUNT_ID          - Cloudflare Account ID
    CF_R2_ACCESS_KEY_ID    - R2 Access Key ID
    CF_R2_SECRET_ACCESS_KEY - R2 Secret Access Key
"""

import os
import re
import sys
import json
import time
import argparse
import subprocess
from pathlib import Path

BUCKET = os.environ.get("R2_BUCKET", "crash-lens-data")
ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "")
ENDPOINT = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"

# ─── All 50 States + DC + NYC ────────────────────────────────────────────────
# Maps R2 state prefix → { hierarchy: states/ dir name, data_dir: data/ dir name }
# hierarchy.json is the SINGLE SOURCE OF TRUTH for regions, MPOs, and counties.
STATE_MAP = {
    # ── States with active data pipelines ──
    "virginia":             {"hierarchy": "virginia",             "data_dir": None},
    "colorado":             {"hierarchy": "colorado",             "data_dir": "CDOT"},
    "maryland":             {"hierarchy": "maryland",             "data_dir": "MarylandDOT"},
    "connecticut":          {"hierarchy": "connecticut",          "data_dir": "ConnecticutDOT"},
    "delaware":             {"hierarchy": "delaware",             "data_dir": "DelawareDOT"},
    "new_york":             {"hierarchy": "new_york",             "data_dir": "NewYorkDOT"},
    "hawaii":               {"hierarchy": "hawaii",               "data_dir": "HawaiiDOT"},
    "iowa":                 {"hierarchy": "iowa",                 "data_dir": "IowaDOT"},
    "illinois":             {"hierarchy": "illinois",             "data_dir": "IllinoisDOT"},
    "louisiana":            {"hierarchy": "louisiana",            "data_dir": "LouisianaDOT"},
    "alaska":               {"hierarchy": "alaska",               "data_dir": "AlaskaDOT"},
    "massachusetts":        {"hierarchy": "massachusetts",        "data_dir": "MassachusettsDOT"},
    "pennsylvania":         {"hierarchy": "pennsylvania",         "data_dir": "PennsylvaniaDOT"},
    "florida":              {"hierarchy": "florida",              "data_dir": "FloridaDOT"},
    "georgia":              {"hierarchy": "georgia",              "data_dir": "GeorgiaDOT"},
    "south_carolina":       {"hierarchy": "south_carolina",       "data_dir": "SouthCarolinaDOT"},
    "ohio":                 {"hierarchy": "ohio",                 "data_dir": "OhioDOT"},
    "wisconsin":            {"hierarchy": "wisconsin",            "data_dir": "WisconsinDOT"},
    "nevada":               {"hierarchy": "nevada",               "data_dir": "NevadaDOT"},
    "utah":                 {"hierarchy": "utah",                 "data_dir": "UtahDOT"},
    "oregon":               {"hierarchy": "oregon",               "data_dir": "OregonDOT"},
    "washington":           {"hierarchy": "washington",           "data_dir": "WashingtonDOT"},
    "idaho":                {"hierarchy": "idaho",                "data_dir": "IdahoDOT"},
    "montana":              {"hierarchy": "montana",              "data_dir": "MontanaDOT"},
    "west_virginia":        {"hierarchy": "west_virginia",        "data_dir": "WestVirginiaDOT"},
    "mississippi":          {"hierarchy": "mississippi",          "data_dir": "MississippiDOT"},
    "oklahoma":             {"hierarchy": "oklahoma",             "data_dir": "OklahomaDOT"},
    "arkansas":             {"hierarchy": "arkansas",             "data_dir": "ArkansasDOT"},
    "vermont":              {"hierarchy": "vermont",              "data_dir": "VermontDOT"},
    "texas":                {"hierarchy": "texas",                "data_dir": "TexasDOT"},
    # ── Remaining US states + DC ──
    "alabama":              {"hierarchy": "alabama",              "data_dir": None},
    "arizona":              {"hierarchy": "arizona",              "data_dir": None},
    "california":           {"hierarchy": "california",           "data_dir": None},
    "district_of_columbia": {"hierarchy": "district_of_columbia", "data_dir": None},
    "indiana":              {"hierarchy": "indiana",              "data_dir": None},
    "kansas":               {"hierarchy": "kansas",               "data_dir": None},
    "kentucky":             {"hierarchy": "kentucky",             "data_dir": None},
    "maine":                {"hierarchy": "maine",                "data_dir": None},
    "michigan":             {"hierarchy": "michigan",             "data_dir": None},
    "minnesota":            {"hierarchy": "minnesota",            "data_dir": None},
    "missouri":             {"hierarchy": "missouri",             "data_dir": None},
    "nebraska":             {"hierarchy": "nebraska",             "data_dir": None},
    "new_hampshire":        {"hierarchy": "new_hampshire",        "data_dir": None},
    "new_jersey":           {"hierarchy": "new_jersey",           "data_dir": None},
    "new_mexico":           {"hierarchy": "new_mexico",           "data_dir": None},
    "north_carolina":       {"hierarchy": "north_carolina",       "data_dir": None},
    "north_dakota":         {"hierarchy": "north_dakota",         "data_dir": None},
    "rhode_island":         {"hierarchy": "rhode_island",         "data_dir": None},
    "south_dakota":         {"hierarchy": "south_dakota",         "data_dir": None},
    "tennessee":            {"hierarchy": "tennessee",            "data_dir": None},
    "wyoming":              {"hierarchy": "wyoming",              "data_dir": None},
    # ── NYC (special sub-state entity, no hierarchy.json) ──
    "nyc":                  {"hierarchy": None,                   "data_dir": "NYCDOT"},
}

# NYC boroughs — hardcoded since NYC has no hierarchy.json
NYC_JURISDICTIONS = ["bronx", "brooklyn", "manhattan", "queens", "staten_island"]


def get_project_root():
    """Get project root directory."""
    return Path(__file__).resolve().parent.parent


def county_name_to_key(name):
    """Convert a county display name to a snake_case R2 folder key.

    Examples:
        "Adams"           -> "adams"
        "El Paso"         -> "el_paso"
        "Prince George's" -> "prince_georges"
        "St. Mary's"      -> "st_marys"
        "De Kalb"         -> "de_kalb"
        "Alexandria City"  -> "alexandria_city"  (VA independent cities)
    """
    key = name.lower()
    # Remove apostrophes: Prince George's -> prince georges
    key = key.replace("'", "")
    # Replace periods: St. Mary -> st mary
    key = key.replace(".", "")
    # Replace spaces/hyphens with underscores
    key = re.sub(r'[\s\-]+', '_', key)
    # Remove any remaining non-alphanumeric except underscores
    key = re.sub(r'[^a-z0-9_]', '', key)
    # Collapse multiple underscores
    key = re.sub(r'_+', '_', key)
    # Strip leading/trailing underscores
    key = key.strip('_')
    return key


def load_hierarchy(state_prefix, project_root):
    """Load full hierarchy.json for a state.

    Returns the parsed JSON dict, or None if not found.
    """
    state_cfg = STATE_MAP.get(state_prefix, {})
    hierarchy_name = state_cfg.get("hierarchy")
    if not hierarchy_name:
        return None

    hierarchy_path = project_root / "states" / hierarchy_name / "hierarchy.json"
    if not hierarchy_path.exists():
        return None

    try:
        with open(hierarchy_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def load_virginia_jurisdictions(project_root):
    """Load Virginia jurisdiction keys from config.json (authoritative source)."""
    config_path = project_root / "config.json"
    if not config_path.exists():
        return []
    with open(config_path) as f:
        config = json.load(f)
    jurisdictions = list(config.get("jurisdictions", {}).keys())
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
        keys = [k for k in filters.keys() if not k.startswith("_")]
        return keys if keys else []
    except (json.JSONDecodeError, KeyError):
        return []


def get_jurisdictions_from_hierarchy(hierarchy):
    """Extract jurisdiction folder names from hierarchy.json allCounties.

    Converts county display names to snake_case keys.
    """
    all_counties = hierarchy.get("allCounties", {})
    if not all_counties:
        return []
    return [county_name_to_key(name) for name in all_counties.values()]


def get_regions(hierarchy):
    """Extract region keys from hierarchy.json."""
    regions = hierarchy.get("regions", {})
    return [k for k in regions.keys() if not k.startswith("_")]


def get_mpos(hierarchy):
    """Extract MPO/TPR keys from hierarchy.json."""
    tprs = hierarchy.get("tprs", {})
    return [k for k in tprs.keys() if not k.startswith("_")]


def get_jurisdictions(state_prefix, project_root, hierarchy):
    """Get jurisdiction list for a state, using the best available source.

    Priority:
      1. Virginia: config.json (has curated keys with _city/_county suffixes)
      2. CO/MD: source_manifest.json (has curated keys)
      3. All others: hierarchy.json allCounties (convert names to snake_case)
    """
    # Virginia — config.json is authoritative (independent cities, etc.)
    if state_prefix == "virginia":
        return load_virginia_jurisdictions(project_root)

    # NYC — hardcoded boroughs
    if state_prefix == "nyc":
        return NYC_JURISDICTIONS

    # States with curated source_manifest.json
    state_cfg = STATE_MAP.get(state_prefix, {})
    data_dir = state_cfg.get("data_dir")
    if data_dir:
        manifest_jurisdictions = load_jurisdictions_from_manifest(project_root, data_dir)
        if manifest_jurisdictions:
            return manifest_jurisdictions

    # Fallback: derive from hierarchy.json allCounties
    if hierarchy:
        return get_jurisdictions_from_hierarchy(hierarchy)

    return []


def generate_all_folders(state_filter=None, top_level_only=False):
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
        "states/",
        "states/geography/",
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

        # Load hierarchy
        hierarchy = load_hierarchy(state_prefix, project_root)

        # ── Regions / DOT Districts ──
        region_keys = get_regions(hierarchy) if hierarchy else []
        if region_keys:
            print(f"    {len(region_keys)} regions: {', '.join(sorted(region_keys)[:5])}{'...' if len(region_keys) > 5 else ''}")
            for r in sorted(region_keys):
                folders.append(f"{state_prefix}/_region/{r}/")

        # ── MPOs / TPRs ──
        mpo_keys = get_mpos(hierarchy) if hierarchy else []
        if mpo_keys:
            print(f"    {len(mpo_keys)} MPOs/TPRs: {', '.join(sorted(mpo_keys)[:5])}{'...' if len(mpo_keys) > 5 else ''}")
            for m in sorted(mpo_keys):
                folders.append(f"{state_prefix}/_mpo/{m}/")

        # ── Jurisdictions ──
        if not top_level_only:
            jurisdictions = get_jurisdictions(state_prefix, project_root, hierarchy)
            print(f"    {len(jurisdictions)} jurisdictions")
            for j in sorted(jurisdictions):
                folders.append(f"{state_prefix}/{j}/")
                folders.append(f"{state_prefix}/{j}/raw/")
        else:
            print(f"    (skipping jurisdictions — top-level-only mode)")

    return folders


def create_folder_via_cli(folder_key, dry_run=False):
    """Create a single folder marker in R2 using AWS CLI."""
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
        if i % 100 == 0 or i == total:
            print(f"  Progress: {i}/{total} ({i*100//total}%)")

        if create_folder_via_cli(folder, dry_run=dry_run):
            created += 1
        else:
            failed += 1

    print(f"\n{'='*60}")
    print(f"RESULTS: {created} created, {failed} failed, {total} total")
    print(f"{'='*60}")

    return failed == 0


GEOGRAPHY_FILES = [
    "us_counties.json",
    "us_county_subdivisions.json",
    "us_mpos.json",
    "us_places.json",
    "us_states.json",
]


def upload_geography_files(dry_run=False):
    """Upload geography JSON files from states/geography/ to R2.

    These files are needed by the HTML normalization tools and the frontend
    for FIPS resolution, MPO lookups, and coordinate-based geography matching.

    R2 path: states/geography/{filename}
    Public URL: https://data.aicreatesai.com/states/geography/{filename}
    """
    project_root = get_project_root()
    geo_dir = project_root / "states" / "geography"

    if not geo_dir.exists():
        print(f"\n  [WARN] Geography directory not found: {geo_dir}")
        return 0, 0

    uploaded = 0
    failed = 0

    print(f"\n{'='*60}")
    print(f"Uploading geography files to R2")
    print(f"  Source: {geo_dir}")
    print(f"  Dest:   s3://{BUCKET}/states/geography/")
    print(f"{'='*60}\n")

    for filename in GEOGRAPHY_FILES:
        local_path = geo_dir / filename
        if not local_path.exists():
            print(f"  [SKIP] {filename} — not found locally")
            continue

        r2_key = f"states/geography/{filename}"
        size_kb = local_path.stat().st_size / 1024
        size_label = f"{size_kb:.0f}KB" if size_kb < 1024 else f"{size_kb/1024:.1f}MB"

        if dry_run:
            print(f"  [DRY-RUN] Would upload: {filename} ({size_label}) → {r2_key}")
            uploaded += 1
            continue

        import gzip as gz
        import shutil
        gz_path = str(local_path) + ".gz"
        with open(local_path, 'rb') as f_in:
            with gz.open(gz_path, 'wb', compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)

        gz_size_kb = os.path.getsize(gz_path) / 1024
        gz_label = f"{gz_size_kb:.0f}KB" if gz_size_kb < 1024 else f"{gz_size_kb/1024:.1f}MB"

        cmd = [
            "aws", "s3", "cp", gz_path, f"s3://{BUCKET}/{r2_key}",
            "--endpoint-url", ENDPOINT,
            "--content-type", "application/json",
            "--content-encoding", "gzip",
            "--only-show-errors",
        ]

        success = False
        for attempt in range(3):
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if result.returncode == 0:
                    success = True
                    break
                print(f"  [WARN] Attempt {attempt+1} failed for {filename}: {result.stderr.strip()}")
            except subprocess.TimeoutExpired:
                print(f"  [WARN] Timeout on attempt {attempt+1} for {filename}")
            if attempt < 2:
                time.sleep(2 ** attempt)

        if os.path.exists(gz_path):
            os.remove(gz_path)

        if success:
            print(f"  [OK] {filename} ({size_label} → {gz_label} gzip) → {r2_key}")
            uploaded += 1
        else:
            print(f"  [FAIL] {filename}")
            failed += 1

    # Also upload hierarchy.json per state to R2
    print(f"\n  Uploading per-state hierarchy.json files...")
    for state_prefix in sorted(STATE_MAP.keys()):
        state_cfg = STATE_MAP[state_prefix]
        hierarchy_name = state_cfg.get("hierarchy")
        if not hierarchy_name:
            continue

        hierarchy_path = project_root / "states" / hierarchy_name / "hierarchy.json"
        if not hierarchy_path.exists():
            continue

        r2_key = f"{state_prefix}/_state/hierarchy.json"
        size_kb = hierarchy_path.stat().st_size / 1024

        if dry_run:
            print(f"  [DRY-RUN] Would upload: {state_prefix}/hierarchy.json ({size_kb:.0f}KB)")
            uploaded += 1
            continue

        cmd = [
            "aws", "s3", "cp", str(hierarchy_path), f"s3://{BUCKET}/{r2_key}",
            "--endpoint-url", ENDPOINT,
            "--content-type", "application/json",
            "--only-show-errors",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print(f"  [OK] {state_prefix}/hierarchy.json → {r2_key}")
                uploaded += 1
            else:
                print(f"  [FAIL] {state_prefix}/hierarchy.json: {result.stderr.strip()}")
                failed += 1
        except subprocess.TimeoutExpired:
            print(f"  [FAIL] {state_prefix}/hierarchy.json: timeout")
            failed += 1

    print(f"\n  Geography upload: {uploaded} uploaded, {failed} failed")
    return uploaded, failed


def main():
    parser = argparse.ArgumentParser(description="Create R2 folder structure")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print folders without creating them")
    parser.add_argument("--state", type=str, default=None,
                        help="Only create folders for a specific state prefix")
    parser.add_argument("--list-only", action="store_true",
                        help="Just list all folder paths and exit")
    parser.add_argument("--top-level-only", action="store_true",
                        help="Only create state meta folders + regions + MPOs (skip jurisdictions)")
    parser.add_argument("--upload-geography", action="store_true",
                        help="Upload geography JSONs and hierarchy files to R2")
    parser.add_argument("--geography-only", action="store_true",
                        help="ONLY upload geography files (skip folder creation)")
    args = parser.parse_args()

    # Validate environment
    if not args.dry_run and not args.list_only:
        if not ACCOUNT_ID:
            print("ERROR: CF_ACCOUNT_ID environment variable required")
            sys.exit(1)
        if not os.environ.get("AWS_ACCESS_KEY_ID"):
            print("ERROR: AWS_ACCESS_KEY_ID environment variable required")
            sys.exit(1)

    if args.geography_only:
        uploaded, failed = upload_geography_files(dry_run=args.dry_run)
        sys.exit(0 if failed == 0 else 1)

    print("Generating R2 folder structure...")
    folders = generate_all_folders(
        state_filter=args.state,
        top_level_only=args.top_level_only
    )

    if args.list_only:
        print(f"\nTotal folders: {len(folders)}\n")
        for f in folders:
            print(f"  {f}")
        return

    print(f"\nTotal folders to create: {len(folders)}")

    if args.dry_run:
        print("\n[DRY-RUN MODE] No changes will be made.\n")

    success = create_folders_batch(folders, dry_run=args.dry_run)

    # Upload geography files if --upload-geography flag or running all states
    if args.upload_geography or (not args.state and not args.top_level_only):
        uploaded, failed = upload_geography_files(dry_run=args.dry_run)
        if failed > 0:
            success = False

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
