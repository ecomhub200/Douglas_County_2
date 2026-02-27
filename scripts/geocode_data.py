#!/usr/bin/env python3
"""
Geocode crash data CSV with incremental caching.

Fills missing GPS coordinates (x=longitude, y=latitude) using:
  Strategy 1: Node lookup (intersection name → known coordinates)
  Strategy 2: Nominatim/OSM reverse geocode (road name + jurisdiction → coordinates)
  Strategy 3: Persistent cache (location_key → coordinates from previous runs)

After geocoding, saves the statewide validated+geocoded CSV as an intermediate
artifact: data/{DOT_NAME}/{state}_statewide_validated_geocoded.csv

Uses a state-isolated cache to avoid re-geocoding known locations.

Usage:
    python scripts/geocode_data.py --state virginia --input data/all_roads.csv --output data/virginia_statewide_validated_geocoded.csv
    python scripts/geocode_data.py --state colorado --input data/CDOT/co_validated.csv --output data/CDOT/colorado_statewide_validated_geocoded.csv
    python scripts/geocode_data.py --state virginia --input data/all_roads.csv --cache-dir .cache/virginia/geocode --force-geocode
"""

import argparse
import csv
import gzip
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger('geocode_data')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

PROJECT_ROOT = Path(__file__).parent.parent

# Rate limiting for Nominatim
NOMINATIM_DELAY = 1.1  # seconds between requests (Nominatim policy)
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
NOMINATIM_HEADERS = {'User-Agent': 'CrashLens/1.0 (crash-data-pipeline)'}
FAILED_CACHE_TTL_DAYS = 30  # Re-try failed lookups after this many days

# 2% buffer on coordinate bounds so geocoded results near
# state/jurisdiction borders aren't falsely rejected.
BOUNDARY_BUFFER_PERCENT = 0.02


def apply_boundary_buffer(bounds, buffer_pct=BOUNDARY_BUFFER_PERCENT):
    """Expand coordinate bounds by a percentage of their span.

    A 2% buffer on Virginia (lat span ~3.0°) adds ~0.06° ≈ 4.1 miles.
    A 2% buffer on Colorado (lat span ~4.2°) adds ~0.08° ≈ 5.8 miles.
    This accommodates geocoding imprecision and border-area crashes.
    """
    lat_span = bounds['lat_max'] - bounds['lat_min']
    lon_span = bounds['lon_max'] - bounds['lon_min']
    lat_buf = lat_span * buffer_pct
    lon_buf = lon_span * buffer_pct
    return {
        'lat_min': bounds['lat_min'] - lat_buf,
        'lat_max': bounds['lat_max'] + lat_buf,
        'lon_min': bounds['lon_min'] - lon_buf,
        'lon_max': bounds['lon_max'] + lon_buf,
    }


def load_state_bounds(state):
    """Load coordinate bounds from state config with 2% boundary buffer."""
    config_path = PROJECT_ROOT / 'states' / state / 'config.json'
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
        bounds = config.get('state', {}).get('coordinateBounds', {})
        raw_bounds = {
            'lat_min': bounds.get('latMin', -90),
            'lat_max': bounds.get('latMax', 90),
            'lon_min': bounds.get('lonMin', -180),
            'lon_max': bounds.get('lonMax', 180),
        }
        return apply_boundary_buffer(raw_bounds)
    return {'lat_min': -90, 'lat_max': 90, 'lon_min': -180, 'lon_max': 180}


def coords_within_bounds(lon, lat, bounds):
    """Check if coordinates fall within the buffered state bounds."""
    return (bounds['lon_min'] <= lon <= bounds['lon_max'] and
            bounds['lat_min'] <= lat <= bounds['lat_max'])


def build_location_key(row, col_idx):
    """Build a location key from available fields for cache lookup."""
    parts = []
    for field in ['RTE Name', 'Node', 'Physical Juris Name', 'RNS MP']:
        idx = col_idx.get(field)
        if idx is not None and idx < len(row):
            parts.append(str(row[idx]).strip())
        else:
            parts.append('')
    return '|'.join(parts)


def has_valid_coordinates(row, col_idx):
    """Check if row already has valid x (lon) and y (lat)."""
    x_idx = col_idx.get('x')
    y_idx = col_idx.get('y')
    if x_idx is None or y_idx is None:
        return False
    try:
        x_str = row[x_idx].strip() if x_idx < len(row) else ''
        y_str = row[y_idx].strip() if y_idx < len(row) else ''
        if not x_str or not y_str:
            return False
        x = float(x_str)
        y = float(y_str)
        return x != 0 and y != 0
    except (ValueError, IndexError):
        return False


# Road name normalization patterns for better Nominatim hit rates
_ROAD_ABBREVIATIONS = [
    (r'\bRT\b\.?\s*', 'Route '),
    (r'\bRTE\b\.?\s*', 'Route '),
    (r'\bI-(\d+)', r'Interstate \1'),
    (r'\bUS\b\.?\s*(\d+)', r'US Route \1'),
    (r'\bSR\b\.?\s*(\d+)', r'State Route \1'),
    (r'\bST\b\.?\s*$', 'Street'),
    (r'\bAVE\b\.?\s*$', 'Avenue'),
    (r'\bBLVD\b\.?\s*$', 'Boulevard'),
    (r'\bDR\b\.?\s*$', 'Drive'),
    (r'\bLN\b\.?\s*$', 'Lane'),
    (r'\bPKWY\b\.?\s*$', 'Parkway'),
    (r'\bCT\b\.?\s*$', 'Court'),
    (r'\bPL\b\.?\s*$', 'Place'),
    (r'\bRD\b\.?\s*$', 'Road'),
    (r'\bHWY\b\.?\s*', 'Highway '),
    (r'\bCIR\b\.?\s*$', 'Circle'),
    (r'\bTER\b\.?\s*$', 'Terrace'),
    (r'\bTRPK\b\.?\s*$', 'Turnpike'),
    (r'\bTPKE\b\.?\s*$', 'Turnpike'),
]


def normalize_road_name(name):
    """Normalize road abbreviations for better Nominatim geocoding hit rate.

    Examples:
        'RT 288'     → 'Route 288'
        'I-64'       → 'Interstate 64'
        'US 1'       → 'US Route 1'
        'BROAD ST'   → 'BROAD Street'
        'SR 7'       → 'State Route 7'
    """
    if not name:
        return name
    result = name.strip()
    for pattern, replacement in _ROAD_ABBREVIATIONS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    # Collapse multiple spaces
    result = re.sub(r'\s+', ' ', result).strip()
    return result


# Track last API call time for rate limiting (sleep only between consecutive calls)
_last_api_call_time = 0.0


def geocode_nominatim(road_name, jurisdiction, state):
    """Geocode using Nominatim (OSM). Returns (lon, lat) or None."""
    global _last_api_call_time
    try:
        import requests
    except ImportError:
        return None

    if not road_name or not jurisdiction:
        return None

    normalized = normalize_road_name(road_name)
    query = f"{normalized}, {jurisdiction}, {state}"
    params = {
        'q': query,
        'format': 'json',
        'limit': 1,
        'countrycodes': 'us'
    }

    try:
        # Rate limit: sleep only if we've called the API recently
        now = time.time()
        elapsed = now - _last_api_call_time
        if _last_api_call_time > 0 and elapsed < NOMINATIM_DELAY:
            time.sleep(NOMINATIM_DELAY - elapsed)
        _last_api_call_time = time.time()

        resp = requests.get(NOMINATIM_URL, params=params, headers=NOMINATIM_HEADERS, timeout=10)
        if resp.status_code == 200:
            results = resp.json()
            if results:
                lon = float(results[0]['lon'])
                lat = float(results[0]['lat'])
                return (lon, lat)
    except Exception as e:
        logger.debug(f"Nominatim error for '{query}': {e}")
    return None


def load_geocode_cache(cache_dir):
    """Load geocode cache (location_key → {x, y, method, confidence, cached_at})."""
    cache_file = Path(cache_dir) / 'geocode_cache.json'
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)
    return {}


def load_geocoded_records(cache_dir):
    """Load record tracking (Document Nbr → location_key)."""
    records_file = Path(cache_dir) / 'geocoded_records.json'
    if records_file.exists():
        with open(records_file) as f:
            return json.load(f)
    return {}


def save_geocode_cache(cache_dir, cache):
    """Save geocode cache."""
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    cache_file = Path(cache_dir) / 'geocode_cache.json'
    with open(cache_file, 'w') as f:
        json.dump(cache, f)


def save_geocoded_records(cache_dir, records):
    """Save geocoded records tracking."""
    records_file = Path(cache_dir) / 'geocoded_records.json'
    with open(records_file, 'w') as f:
        json.dump(records, f)


def save_cache_stats(cache_dir, stats):
    """Save cache statistics."""
    stats_file = Path(cache_dir) / 'cache_stats.json'
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)


def update_geocode_cache_manifest(cache_dir, state, stats, total_locations):
    """Update the state-level cache_manifest.json with geocode run stats."""
    cache_dir_path = Path(cache_dir)
    state_cache_dir = cache_dir_path.parent if cache_dir_path.name == 'geocode' else cache_dir_path
    manifest_path = state_cache_dir / 'cache_manifest.json'

    manifest = {}
    if manifest_path.exists():
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
        except (json.JSONDecodeError, IOError):
            manifest = {}

    now = datetime.utcnow().isoformat() + 'Z'
    manifest['last_updated'] = now
    manifest.setdefault('state', state)
    manifest.setdefault('version', 1)

    total_lookups = stats['total_rows'] - stats['already_had_coords']
    hit_rate = round(stats['cache_hits'] / max(1, total_lookups), 4)

    manifest['geocode'] = {
        'last_run': now,
        'total_locations': total_locations,
        'api_calls_total': stats['api_calls'],
        'api_successes': stats['api_successes'],
        'cache_hit_rate': hit_rate,
        'node_hits': stats.get('node_hits', 0),
        'stale_refreshed': stats['stale_refreshed'],
        'stale_reused': stats.get('stale_reused', 0),
        'api_failures_cached': stats.get('api_failures_cached', 0),
        'not_geocoded': stats['no_geocode']
    }

    state_cache_dir.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)


def get_geocode_ttl(state):
    """Get geocode TTL from state config (default: 365 days)."""
    config_path = PROJECT_ROOT / 'states' / state / 'config.json'
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
        cache_config = config.get('cache_config', {})
        return cache_config.get('geocode_ttl_days', 365)
    return 365


def is_cache_stale(entry, ttl_days):
    """Check if a cache entry is stale (older than TTL)."""
    cached_at = entry.get('cached_at', '')
    if not cached_at:
        return True
    try:
        cached_dt = datetime.fromisoformat(cached_at.replace('Z', '+00:00'))
        return datetime.now(cached_dt.tzinfo) - cached_dt > timedelta(days=ttl_days)
    except (ValueError, TypeError):
        return True


def main():
    parser = argparse.ArgumentParser(description='Geocode crash data CSV with incremental caching')
    parser.add_argument('--state', required=True, help='State key (e.g., virginia, colorado)')
    parser.add_argument('--input', required=True, help='Path to validated CSV')
    parser.add_argument('--output', default=None, help='Output path for geocoded CSV')
    parser.add_argument('--cache-dir', default=None, help='Cache directory (default: .cache/{state}/geocode)')
    parser.add_argument('--force-geocode', action='store_true', help='Ignore cache, re-geocode everything')
    parser.add_argument('--max-api-calls', type=int, default=2500, help='Max Nominatim API calls per run')
    parser.add_argument('--save-gzip', action='store_true', help='Also save a gzipped copy')
    args = parser.parse_args()

    state = args.state
    input_path = Path(args.input)
    cache_dir = args.cache_dir or f'.cache/{state}/geocode'
    ttl_days = get_geocode_ttl(state)

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return 1

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.parent / f"{state}_statewide_validated_geocoded.csv"

    # Load buffered state bounds for validating geocode results
    state_bounds = load_state_bounds(state)

    logger.info(f"[{state}] Geocoding: {input_path}")
    logger.info(f"[{state}] Output: {output_path}")
    logger.info(f"[{state}] Cache TTL: {ttl_days} days")
    logger.info(f"[{state}] Bounds (with {BOUNDARY_BUFFER_PERCENT:.0%} buffer): "
                f"lat=[{state_bounds['lat_min']:.4f}, {state_bounds['lat_max']:.4f}], "
                f"lon=[{state_bounds['lon_min']:.4f}, {state_bounds['lon_max']:.4f}]")

    # Load caches
    if args.force_geocode:
        geo_cache = {}
        geo_records = {}
        logger.info(f"[{state}] Force geocode — cache cleared")
    else:
        geo_cache = load_geocode_cache(cache_dir)
        geo_records = load_geocoded_records(cache_dir)
        logger.info(f"[{state}] Cache loaded: {len(geo_cache)} locations, {len(geo_records)} records")

    # Stats
    stats = {
        'total_rows': 0,
        'already_had_coords': 0,
        'cache_hits': 0,
        'stale_refreshed': 0,
        'stale_reused': 0,
        'node_hits': 0,
        'api_calls': 0,
        'api_successes': 0,
        'api_failures_cached': 0,
        'geocode_rejected': 0,
        'no_geocode': 0,
    }

    # Process
    output_rows = []
    api_calls_remaining = args.max_api_calls

    # Node-based geocoding: build a lookup of Node → (x, y) from rows that
    # already have valid coordinates. This fills coordinates for other rows
    # at the same intersection without any API calls.
    node_coords = {}  # Node value → (lon, lat)

    with open(input_path, 'r', newline='', encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f)
        headers = next(reader)

        col_idx = {}
        for i, h in enumerate(headers):
            col_idx[h.strip()] = i

        x_idx = col_idx.get('x')
        y_idx = col_idx.get('y')
        doc_idx = col_idx.get('Document Nbr')
        route_idx = col_idx.get('RTE Name')
        juris_idx = col_idx.get('Physical Juris Name')
        node_idx = col_idx.get('Node')

        output_rows.append(headers)

        # Pass 1: Build node coordinate lookup from rows with valid coords
        all_rows = list(reader)
        for row in all_rows:
            if node_idx is not None and node_idx < len(row) and has_valid_coordinates(row, col_idx):
                node_val = row[node_idx].strip()
                if node_val and node_val not in node_coords:
                    x_val = float(row[x_idx].strip())
                    y_val = float(row[y_idx].strip())
                    node_coords[node_val] = (x_val, y_val)

        if node_coords:
            logger.info(f"[{state}] Node lookup built: {len(node_coords):,} unique nodes with coordinates")

        # Pass 2: Process all rows
        for row in all_rows:
            stats['total_rows'] += 1

            # Already has valid coordinates
            if has_valid_coordinates(row, col_idx):
                stats['already_had_coords'] += 1
                output_rows.append(row)
                if doc_idx is not None and doc_idx < len(row):
                    doc_nbr = row[doc_idx].strip()
                    loc_key_hash = hashlib.md5(build_location_key(row, col_idx).encode()).hexdigest()[:12]
                    if doc_nbr:
                        geo_records[doc_nbr] = loc_key_hash
                continue

            # Build location key for cache lookup
            loc_key = build_location_key(row, col_idx)
            loc_key_hash = hashlib.md5(loc_key.encode()).hexdigest()[:12]

            # Strategy 1: Node-based coordinate lookup
            if node_idx is not None and node_idx < len(row):
                node_val = row[node_idx].strip()
                if node_val and node_val in node_coords:
                    lon, lat = node_coords[node_val]
                    if x_idx is not None and x_idx < len(row):
                        row[x_idx] = str(lon)
                    if y_idx is not None and y_idx < len(row):
                        row[y_idx] = str(lat)
                    stats['node_hits'] += 1
                    output_rows.append(row)
                    if doc_idx is not None and doc_idx < len(row):
                        doc_nbr = row[doc_idx].strip()
                        if doc_nbr:
                            geo_records[doc_nbr] = loc_key_hash
                    continue

            # Strategy 2: Check geocode cache
            if loc_key_hash in geo_cache and not args.force_geocode:
                entry = geo_cache[loc_key_hash]

                # Check if this is a cached failure
                if entry.get('failed'):
                    if not is_cache_stale(entry, FAILED_CACHE_TTL_DAYS):
                        stats['no_geocode'] += 1
                        output_rows.append(row)
                        continue
                    # Stale failure — allow retry below

                elif not is_cache_stale(entry, ttl_days):
                    # Cache hit — use cached coordinates
                    if x_idx is not None and x_idx < len(row):
                        row[x_idx] = str(entry.get('x', ''))
                    if y_idx is not None and y_idx < len(row):
                        row[y_idx] = str(entry.get('y', ''))
                    stats['cache_hits'] += 1
                    output_rows.append(row)
                    if doc_idx is not None and doc_idx < len(row):
                        doc_nbr = row[doc_idx].strip()
                        if doc_nbr:
                            geo_records[doc_nbr] = loc_key_hash
                    continue

            # Stale entry — remember it so we can fall back if API fails
            stale_entry = geo_cache.get(loc_key_hash) if loc_key_hash in geo_cache else None

            # Strategy 3: Nominatim geocoding (if API calls remaining)
            geocoded = False
            if api_calls_remaining > 0:
                road_name = row[route_idx].strip() if route_idx is not None and route_idx < len(row) else ''
                jurisdiction = row[juris_idx].strip() if juris_idx is not None and juris_idx < len(row) else ''

                if road_name and jurisdiction:
                    result = geocode_nominatim(road_name, jurisdiction, state)
                    stats['api_calls'] += 1
                    api_calls_remaining -= 1

                    if result:
                        lon, lat = result

                        # Validate result falls within buffered state bounds
                        if not coords_within_bounds(lon, lat, state_bounds):
                            logger.debug(f"[{state}] Geocode rejected (out of bounds): "
                                         f"lon={lon}, lat={lat} for '{road_name}, {jurisdiction}'")
                            stats['geocode_rejected'] += 1
                        else:
                            if x_idx is not None and x_idx < len(row):
                                row[x_idx] = str(lon)
                            if y_idx is not None and y_idx < len(row):
                                row[y_idx] = str(lat)
                            stats['api_successes'] += 1
                            geocoded = True

                            if stale_entry and not stale_entry.get('failed'):
                                stats['stale_refreshed'] += 1

                            # Update cache with fresh result
                            geo_cache[loc_key_hash] = {
                                'x': lon,
                                'y': lat,
                                'method': 'nominatim',
                                'confidence': 'medium',
                                'cached_at': datetime.utcnow().isoformat() + 'Z',
                                'location_key': loc_key
                            }
                    else:
                        # Cache the failure so we don't retry on next run
                        geo_cache[loc_key_hash] = {
                            'failed': True,
                            'method': 'nominatim',
                            'cached_at': datetime.utcnow().isoformat() + 'Z',
                            'location_key': loc_key
                        }
                        stats['api_failures_cached'] += 1

            if not geocoded:
                # Fall back to stale entry if available (stale data > no data)
                if stale_entry and not stale_entry.get('failed') and stale_entry.get('x') and stale_entry.get('y'):
                    if x_idx is not None and x_idx < len(row):
                        row[x_idx] = str(stale_entry['x'])
                    if y_idx is not None and y_idx < len(row):
                        row[y_idx] = str(stale_entry['y'])
                    stats['stale_reused'] += 1
                else:
                    stats['no_geocode'] += 1

            output_rows.append(row)
            if doc_idx is not None and doc_idx < len(row):
                doc_nbr = row[doc_idx].strip()
                if doc_nbr:
                    geo_records[doc_nbr] = loc_key_hash

            # Progress
            if stats['total_rows'] % 10000 == 0:
                logger.info(f"[{state}]   Progress: {stats['total_rows']:,} rows processed")

    # Write output CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(output_rows)

    logger.info(f"[{state}] Saved: {output_path} ({len(output_rows)-1:,} rows)")

    # Save gzip if requested
    if args.save_gzip:
        gz_path = str(output_path) + '.gz' if not str(output_path).endswith('.gz') else str(output_path)
        if not str(output_path).endswith('.gz'):
            with open(output_path, 'rb') as f_in:
                with gzip.open(gz_path, 'wb') as f_out:
                    f_out.write(f_in.read())
            logger.info(f"[{state}] Gzip saved: {gz_path}")

    # Save caches
    save_geocode_cache(cache_dir, geo_cache)
    save_geocoded_records(cache_dir, geo_records)

    # Save stats
    cache_stats = {
        'total_lookups': stats['total_rows'] - stats['already_had_coords'],
        'cache_hits': stats['cache_hits'],
        'api_calls': stats['api_calls'],
        'hit_rate': round(stats['cache_hits'] / max(1, stats['total_rows'] - stats['already_had_coords']), 4),
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    save_cache_stats(cache_dir, cache_stats)

    # Update cache_manifest.json (state-level cache metadata)
    update_geocode_cache_manifest(cache_dir, state, stats, len(geo_cache))

    # Summary
    logger.info("=" * 60)
    logger.info(f"[{state}] GEOCODING COMPLETE")
    logger.info(f"[{state}]   Total rows:           {stats['total_rows']:,}")
    logger.info(f"[{state}]   Already had coords:   {stats['already_had_coords']:,}")
    logger.info(f"[{state}]   Node lookup hits:      {stats['node_hits']:,}")
    logger.info(f"[{state}]   Cache hits:            {stats['cache_hits']:,}")
    logger.info(f"[{state}]   Stale refreshed:       {stats['stale_refreshed']:,}")
    logger.info(f"[{state}]   Stale reused:          {stats['stale_reused']:,}")
    logger.info(f"[{state}]   API calls:             {stats['api_calls']:,} ({stats['api_successes']} success)")
    logger.info(f"[{state}]   API failures cached:   {stats['api_failures_cached']:,}")
    logger.info(f"[{state}]   Geocode rejected (OOB): {stats['geocode_rejected']:,}")
    logger.info(f"[{state}]   Not geocoded:          {stats['no_geocode']:,}")
    logger.info(f"[{state}]   Cache locations:        {len(geo_cache):,}")
    logger.info("=" * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
