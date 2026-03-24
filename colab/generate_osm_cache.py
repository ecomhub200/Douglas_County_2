#!/usr/bin/env python3
"""
generate_osm_cache.py — CrashLens OSM Road Cache Generator (CLI)
================================================================
Downloads OSM road network for a state, converts to crash_enricher-compatible
flat parquet format, gzips, and uploads to Cloudflare R2.

SETUP (one-time):
    pip install osmnx geopandas pandas pyarrow scipy boto3

USAGE:
    # Single state:
    python generate_osm_cache.py --state de

    # Multiple states:
    python generate_osm_cache.py --state de va md co

    # All 51 states + DC:
    python generate_osm_cache.py --all

    # Skip R2 upload (just generate local files):
    python generate_osm_cache.py --state de --local-only

    # Force regenerate even if already in R2:
    python generate_osm_cache.py --state de --force

R2 CREDENTIALS (environment variables):
    export R2_ENDPOINT="https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com"
    export R2_ACCESS_KEY_ID="your_key"
    export R2_SECRET_ACCESS_KEY="your_secret"
    export R2_BUCKET="crash-lens-data"    # optional, defaults to crash-lens-data

OUTPUT:
    cache/{abbr}_roads.parquet.gz          -> R2: {prefix}/cache/{abbr}_roads.parquet.gz
    cache/{abbr}_intersections.parquet.gz  -> R2: {prefix}/cache/{abbr}_intersections.parquet.gz
"""

import argparse
import gc
import gzip
import os
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd

# ═══════════════════════════════════════════════════════════════
#  STATE REGISTRY (50 states + DC)
# ═══════════════════════════════════════════════════════════════

ALL_STATES = [
    {"name": "Alabama", "abbreviation": "al", "r2_prefix": "alabama"},
    {"name": "Alaska", "abbreviation": "ak", "r2_prefix": "alaska"},
    {"name": "Arizona", "abbreviation": "az", "r2_prefix": "arizona"},
    {"name": "Arkansas", "abbreviation": "ar", "r2_prefix": "arkansas"},
    {"name": "California", "abbreviation": "ca", "r2_prefix": "california"},
    {"name": "Colorado", "abbreviation": "co", "r2_prefix": "colorado"},
    {"name": "Connecticut", "abbreviation": "ct", "r2_prefix": "connecticut"},
    {"name": "Delaware", "abbreviation": "de", "r2_prefix": "delaware"},
    {"name": "District of Columbia", "abbreviation": "dc", "r2_prefix": "district_of_columbia"},
    {"name": "Florida", "abbreviation": "fl", "r2_prefix": "florida"},
    {"name": "Georgia", "abbreviation": "ga", "r2_prefix": "georgia"},
    {"name": "Hawaii", "abbreviation": "hi", "r2_prefix": "hawaii"},
    {"name": "Idaho", "abbreviation": "id", "r2_prefix": "idaho"},
    {"name": "Illinois", "abbreviation": "il", "r2_prefix": "illinois"},
    {"name": "Indiana", "abbreviation": "in", "r2_prefix": "indiana"},
    {"name": "Iowa", "abbreviation": "ia", "r2_prefix": "iowa"},
    {"name": "Kansas", "abbreviation": "ks", "r2_prefix": "kansas"},
    {"name": "Kentucky", "abbreviation": "ky", "r2_prefix": "kentucky"},
    {"name": "Louisiana", "abbreviation": "la", "r2_prefix": "louisiana"},
    {"name": "Maine", "abbreviation": "me", "r2_prefix": "maine"},
    {"name": "Maryland", "abbreviation": "md", "r2_prefix": "maryland"},
    {"name": "Massachusetts", "abbreviation": "ma", "r2_prefix": "massachusetts"},
    {"name": "Michigan", "abbreviation": "mi", "r2_prefix": "michigan"},
    {"name": "Minnesota", "abbreviation": "mn", "r2_prefix": "minnesota"},
    {"name": "Mississippi", "abbreviation": "ms", "r2_prefix": "mississippi"},
    {"name": "Missouri", "abbreviation": "mo", "r2_prefix": "missouri"},
    {"name": "Montana", "abbreviation": "mt", "r2_prefix": "montana"},
    {"name": "Nebraska", "abbreviation": "ne", "r2_prefix": "nebraska"},
    {"name": "Nevada", "abbreviation": "nv", "r2_prefix": "nevada"},
    {"name": "New Hampshire", "abbreviation": "nh", "r2_prefix": "new_hampshire"},
    {"name": "New Jersey", "abbreviation": "nj", "r2_prefix": "new_jersey"},
    {"name": "New Mexico", "abbreviation": "nm", "r2_prefix": "new_mexico"},
    {"name": "New York", "abbreviation": "ny", "r2_prefix": "new_york"},
    {"name": "North Carolina", "abbreviation": "nc", "r2_prefix": "north_carolina"},
    {"name": "North Dakota", "abbreviation": "nd", "r2_prefix": "north_dakota"},
    {"name": "Ohio", "abbreviation": "oh", "r2_prefix": "ohio"},
    {"name": "Oklahoma", "abbreviation": "ok", "r2_prefix": "oklahoma"},
    {"name": "Oregon", "abbreviation": "or", "r2_prefix": "oregon"},
    {"name": "Pennsylvania", "abbreviation": "pa", "r2_prefix": "pennsylvania"},
    {"name": "Rhode Island", "abbreviation": "ri", "r2_prefix": "rhode_island"},
    {"name": "South Carolina", "abbreviation": "sc", "r2_prefix": "south_carolina"},
    {"name": "South Dakota", "abbreviation": "sd", "r2_prefix": "south_dakota"},
    {"name": "Tennessee", "abbreviation": "tn", "r2_prefix": "tennessee"},
    {"name": "Texas", "abbreviation": "tx", "r2_prefix": "texas"},
    {"name": "Utah", "abbreviation": "ut", "r2_prefix": "utah"},
    {"name": "Vermont", "abbreviation": "vt", "r2_prefix": "vermont"},
    {"name": "Virginia", "abbreviation": "va", "r2_prefix": "virginia"},
    {"name": "Washington", "abbreviation": "wa", "r2_prefix": "washington"},
    {"name": "West Virginia", "abbreviation": "wv", "r2_prefix": "west_virginia"},
    {"name": "Wisconsin", "abbreviation": "wi", "r2_prefix": "wisconsin"},
    {"name": "Wyoming", "abbreviation": "wy", "r2_prefix": "wyoming"},
]

ABBR_LOOKUP = {s["abbreviation"]: s for s in ALL_STATES}


# ═══════════════════════════════════════════════════════════════
#  CORE FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def convert_to_enricher_format(G):
    """
    Convert osmnx graph to crash_enricher-compatible flat DataFrames.

    crash_enricher.py expects:
      roads: u_node, v_node, mid_lat, mid_lon, highway, name, ref, ...
      intersections: node_id, lat, lon, degree

    NOT GeoPandas GeoDataFrames with geometry columns.
    """
    import osmnx as ox

    nodes_gdf, edges_gdf = ox.graph_to_gdfs(G, nodes=True, edges=True)

    # ── Roads (flat format) ──
    road_data = []
    for idx, row in edges_gdf.iterrows():
        u, v = idx[0], idx[1]
        coords = list(row.geometry.coords)
        u_lat, u_lon = coords[0][1], coords[0][0]
        v_lat, v_lon = coords[-1][1], coords[-1][0]

        def _clean(val):
            if isinstance(val, (list, tuple)):
                return '; '.join(str(x) for x in val)
            return str(val) if val is not None and str(val) != 'nan' else ''

        road_data.append({
            'u_node': u, 'v_node': v,
            'u_lat': u_lat, 'u_lon': u_lon,
            'v_lat': v_lat, 'v_lon': v_lon,
            'mid_lat': (u_lat + v_lat) / 2,
            'mid_lon': (u_lon + v_lon) / 2,
            'highway':  _clean(row.get('highway', '')),
            'name':     _clean(row.get('name', '')),
            'ref':      _clean(row.get('ref', '')),
            'oneway':   _clean(row.get('oneway', '')),
            'lanes':    _clean(row.get('lanes', '')),
            'maxspeed': _clean(row.get('maxspeed', '')),
            'length_m': float(row.get('length', 0) or 0),
            'bridge':   _clean(row.get('bridge', '')),
            'tunnel':   _clean(row.get('tunnel', '')),
        })

    road_df = pd.DataFrame(road_data)

    # ── Intersections (flat format) ──
    degrees = dict(G.degree())
    int_data = []
    for node_id, deg in degrees.items():
        if deg >= 3:
            n = nodes_gdf.loc[node_id]
            int_data.append({
                'node_id': node_id,
                'lat': n.geometry.y,
                'lon': n.geometry.x,
                'degree': deg,
            })

    int_df = pd.DataFrame(int_data) if int_data else pd.DataFrame(
        columns=['node_id', 'lat', 'lon', 'degree']
    )

    return road_df, int_df


def gzip_file(src, dst):
    """Gzip a file and return (raw_mb, gz_mb)."""
    with open(src, 'rb') as fi, gzip.open(dst, 'wb', compresslevel=6) as fo:
        shutil.copyfileobj(fi, fo)
    raw = os.path.getsize(src) / 1048576
    gz = os.path.getsize(dst) / 1048576
    return raw, gz


def get_r2_client():
    """Create boto3 S3 client for R2 from environment variables."""
    endpoint = os.environ.get('R2_ENDPOINT', '')
    key_id = os.environ.get('R2_ACCESS_KEY_ID', '')
    secret = os.environ.get('R2_SECRET_ACCESS_KEY', '')

    if not all([endpoint, key_id, secret]):
        return None

    import boto3
    return boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        region_name='auto',
    )


def r2_exists(s3, bucket, prefix, abbr):
    """Check if cache already exists in R2."""
    if not s3:
        return False
    try:
        s3.head_object(Bucket=bucket, Key=f'{prefix}/cache/{abbr}_roads.parquet.gz')
        return True
    except Exception:
        return False


def r2_upload(s3, local_path, bucket, r2_key):
    """Upload file to R2 with retry."""
    for attempt in range(3):
        try:
            s3.upload_file(str(local_path), bucket, r2_key)
            return True
        except Exception as e:
            if attempt == 2:
                print(f"      Upload failed: {e}")
            time.sleep(2 ** (attempt + 1))
    return False


def process_state(state_info, cache_dir, s3, bucket, force=False, local_only=False):
    """Download OSM, convert to enricher format, gzip, upload to R2."""
    name = state_info['name']
    abbr = state_info['abbreviation']
    prefix = state_info['r2_prefix']

    # Check if already in R2
    if not force and not local_only and r2_exists(s3, bucket, prefix, abbr):
        print(f"  [skip] {name} ({abbr}) — already in R2")
        return 'skipped'

    # Check if local gzipped files already exist
    roads_gz = cache_dir / f'{abbr}_roads.parquet.gz'
    ints_gz = cache_dir / f'{abbr}_intersections.parquet.gz'
    if not force and roads_gz.exists() and ints_gz.exists():
        r_mb = os.path.getsize(roads_gz) / 1048576
        i_mb = os.path.getsize(ints_gz) / 1048576
        print(f"  [local] {name} ({abbr}) — cache exists ({r_mb + i_mb:.1f} MB)")
        if not local_only and s3:
            ok1 = r2_upload(s3, roads_gz, bucket, f'{prefix}/cache/{abbr}_roads.parquet.gz')
            ok2 = r2_upload(s3, ints_gz, bucket, f'{prefix}/cache/{abbr}_intersections.parquet.gz')
            if ok1 and ok2:
                print(f"      -> uploaded to R2")
                return 'completed'
            return 'failed'
        return 'completed'

    # Download from OSM
    print(f"\n  [download] {name} ({abbr}) — fetching from OpenStreetMap...")
    t0 = time.time()

    try:
        import osmnx as ox
    except ImportError:
        print("  ERROR: osmnx not installed. Run: pip install osmnx geopandas")
        return 'failed'

    # Special place names for disambiguation
    if name == 'District of Columbia':
        place = 'Washington, DC, United States'
    elif name == 'Georgia':
        place = 'State of Georgia, United States'
    elif name == 'Washington':
        place = 'State of Washington, United States'
    else:
        place = f'{name}, United States'

    try:
        G = ox.graph_from_place(place, network_type='drive', simplify=True)
    except Exception:
        try:
            print(f"      Retrying with 'State of {name}'...")
            G = ox.graph_from_place(f'State of {name}, United States', network_type='drive', simplify=True)
        except Exception as e:
            print(f"  ERROR: {name} download failed: {e}")
            return 'failed'

    dl_sec = time.time() - t0
    print(f"      Downloaded: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges ({dl_sec:.0f}s)")

    # Convert to crash_enricher format
    print(f"      Converting to enricher format...")
    road_df, int_df = convert_to_enricher_format(G)
    print(f"      Roads: {len(road_df):,} segments | Intersections: {len(int_df):,} nodes")

    # Save parquet + gzip
    roads_pq = cache_dir / f'{abbr}_roads.parquet'
    ints_pq = cache_dir / f'{abbr}_intersections.parquet'

    road_df.to_parquet(roads_pq, index=False)
    int_df.to_parquet(ints_pq, index=False)

    raw_r, gz_r = gzip_file(roads_pq, roads_gz)
    raw_i, gz_i = gzip_file(ints_pq, ints_gz)
    roads_pq.unlink(missing_ok=True)
    ints_pq.unlink(missing_ok=True)

    elapsed = time.time() - t0
    print(f"      Saved: {raw_r + raw_i:.1f} MB -> {gz_r + gz_i:.1f} MB gzipped ({elapsed:.0f}s)")

    # Upload to R2
    if not local_only and s3:
        print(f"      Uploading to R2...")
        ok1 = r2_upload(s3, roads_gz, bucket, f'{prefix}/cache/{abbr}_roads.parquet.gz')
        ok2 = r2_upload(s3, ints_gz, bucket, f'{prefix}/cache/{abbr}_intersections.parquet.gz')
        if ok1 and ok2:
            print(f"  [done] {name} — {gz_r + gz_i:.1f} MB in {elapsed:.0f}s")
        else:
            print(f"  [warn] {name} — generated but R2 upload failed")
            return 'failed'
    else:
        print(f"  [done] {name} — saved locally ({gz_r + gz_i:.1f} MB, {elapsed:.0f}s)")

    del G, road_df, int_df
    gc.collect()
    return 'completed'


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="CrashLens OSM Road Cache Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
    python generate_osm_cache.py --state de              # Just Delaware
    python generate_osm_cache.py --state de va md        # Three states
    python generate_osm_cache.py --all                   # All 51
    python generate_osm_cache.py --state tx --local-only # No R2 upload
    python generate_osm_cache.py --state de --force      # Regenerate

R2 CREDENTIALS (environment variables):
    R2_ENDPOINT            https://ACCOUNT.r2.cloudflarestorage.com
    R2_ACCESS_KEY_ID       Your R2 access key
    R2_SECRET_ACCESS_KEY   Your R2 secret key
    R2_BUCKET              Bucket name (default: crash-lens-data)
        """,
    )
    parser.add_argument('--state', nargs='+', help='State abbreviation(s): de va md co')
    parser.add_argument('--all', action='store_true', help='Process all 51 states + DC')
    parser.add_argument('--local-only', action='store_true', help='Skip R2 upload')
    parser.add_argument('--force', action='store_true', help='Regenerate even if exists')
    parser.add_argument('--cache-dir', default='cache', help='Local cache dir (default: cache)')
    args = parser.parse_args()

    if not args.state and not args.all:
        parser.print_help()
        print("\nSpecify --state or --all")
        sys.exit(1)

    # Resolve states
    if args.all:
        states = ALL_STATES
    else:
        states = []
        for abbr in args.state:
            abbr = abbr.lower()
            if abbr in ABBR_LOOKUP:
                states.append(ABBR_LOOKUP[abbr])
            else:
                print(f"Unknown state: {abbr}")
                print(f"Valid: {', '.join(sorted(ABBR_LOOKUP.keys()))}")
                sys.exit(1)

    # Setup
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    bucket = os.environ.get('R2_BUCKET', 'crash-lens-data')

    # R2 client
    s3 = None
    if not args.local_only:
        s3 = get_r2_client()
        if s3:
            try:
                s3.list_objects_v2(Bucket=bucket, Prefix='delaware/', MaxKeys=1)
                print(f"R2 connected: {bucket}")
            except Exception as e:
                print(f"R2 connection failed: {e}")
                print("Set R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY")
                print("Or use --local-only")
                s3 = None
        else:
            print("R2 credentials not set — local-only mode")

    # Process
    print(f"\n{'=' * 60}")
    print(f"  CrashLens OSM Cache Generator")
    print(f"  States: {len(states)} | Cache: {cache_dir} | R2: {'yes' if s3 else 'local'}")
    print(f"{'=' * 60}")

    results = {'completed': 0, 'skipped': 0, 'failed': 0}
    t_start = time.time()

    for i, state in enumerate(states, 1):
        print(f"\n  [{i}/{len(states)}]", end="")
        try:
            result = process_state(state, cache_dir, s3, bucket, args.force, args.local_only)
        except Exception as e:
            print(f"  ERROR: {state['name']} — {e}")
            result = 'failed'
        results[result] += 1

    elapsed = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f"  COMPLETE in {elapsed / 60:.1f} min")
    print(f"  Completed: {results['completed']}")
    print(f"  Skipped:   {results['skipped']}")
    print(f"  Failed:    {results['failed']}")

    gz_files = sorted(cache_dir.glob('*_roads.parquet.gz'))
    if gz_files:
        total_mb = sum(f.stat().st_size for f in gz_files) / 1048576
        int_files = sorted(cache_dir.glob('*_intersections.parquet.gz'))
        total_mb += sum(f.stat().st_size for f in int_files) / 1048576
        print(f"  Local cache: {len(gz_files)} states, {total_mb:.0f} MB")

    print(f"{'=' * 60}\n")


if __name__ == '__main__':
    main()
