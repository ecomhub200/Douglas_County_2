#!/usr/bin/env python3
"""
Download road network data from Overture Maps using DuckDB.
Extracts road segments and intersection connectors for a specified jurisdiction
using bounding box queries against Overture Maps GeoParquet on S3.

Usage:
    python download_road_network.py                                  # Uses default jurisdiction
    python download_road_network.py --jurisdiction henrico
    python download_road_network.py --state colorado --jurisdiction douglas
    python download_road_network.py --bbox -77.6,37.4,-77.3,37.7    # Direct bbox
    python download_road_network.py --release 2026-01-21.0           # Specific release
    python download_road_network.py --list                           # List jurisdictions with bboxes
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Config file paths
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

# Output configuration
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "data")

# Overture Maps S3 base path
OVERTURE_S3_BASE = "s3://overturemaps-us-west-2/release"

# Default release (latest known stable)
DEFAULT_RELEASE = "2025-12-01.0"

# Bbox expansion factor (degrees) to capture roads that cross the boundary
BBOX_BUFFER = 0.005  # ~500m buffer

# Maximum file size warning threshold (MB)
MAX_FILE_SIZE_WARNING_MB = 15


def check_duckdb():
    """Check if DuckDB is installed and has required extensions."""
    try:
        import duckdb
        logger.info(f"DuckDB version: {duckdb.__version__}")
        return True
    except ImportError:
        logger.error("DuckDB is not installed. Install with: pip install duckdb>=0.10.0")
        return False


def init_duckdb():
    """Initialize DuckDB with spatial and httpfs extensions."""
    import duckdb

    conn = duckdb.connect(':memory:')

    # Install and load required extensions
    logger.info("Loading DuckDB extensions (spatial, httpfs)...")
    conn.execute("INSTALL spatial; LOAD spatial;")
    conn.execute("INSTALL httpfs; LOAD httpfs;")

    # Configure S3 access (Overture data is public, no credentials needed)
    conn.execute("SET s3_region = 'us-west-2';")

    # Performance settings for remote queries
    conn.execute("SET enable_http_metadata_cache = true;")
    conn.execute("SET enable_object_cache = true;")
    conn.execute("SET threads = 4;")

    logger.info("DuckDB initialized with spatial and httpfs extensions")
    return conn


def load_config():
    """Load configuration from config.json."""
    if not os.path.exists(CONFIG_FILE):
        logger.error(f"Config file not found: {CONFIG_FILE}")
        sys.exit(1)

    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)

    return config


def load_state_config(state_name):
    """Load state-specific configuration."""
    state_config_path = os.path.join(SCRIPT_DIR, "states", state_name, "config.json")
    if os.path.exists(state_config_path):
        with open(state_config_path, 'r') as f:
            return json.load(f)
    return None


def get_jurisdiction_bbox(config, jurisdiction_id, state_name=None):
    """
    Get bounding box for a jurisdiction.
    Returns [west, south, east, north] or None.
    """
    # Check root config jurisdictions first (Virginia)
    jurisdictions = config.get('jurisdictions', {})
    if jurisdiction_id in jurisdictions:
        jconfig = jurisdictions[jurisdiction_id]
        bbox = jconfig.get('bbox')
        if bbox and len(bbox) == 4:
            return bbox
        # Try to construct from mapCenter if bbox not available
        center = jconfig.get('mapCenter')
        if center:
            # Approximate bbox from center (roughly county-sized)
            return [center[1] - 0.3, center[0] - 0.2, center[1] + 0.3, center[0] + 0.2]

    # Check state-specific config
    if state_name:
        state_config = load_state_config(state_name)
        if state_config:
            state_jurisdictions = state_config.get('jurisdictions', {})
            if jurisdiction_id in state_jurisdictions:
                jconfig = state_jurisdictions[jurisdiction_id]
                bbox = jconfig.get('bbox')
                if bbox and len(bbox) == 4:
                    return bbox

    return None


def list_jurisdictions_with_bbox(config):
    """List all jurisdictions that have bounding boxes defined."""
    jurisdictions = config.get('jurisdictions', {})

    with_bbox = []
    without_bbox = []

    for jid, jdata in sorted(jurisdictions.items()):
        name = jdata.get('name', jid)
        bbox = jdata.get('bbox')
        if bbox and len(bbox) == 4:
            with_bbox.append((jid, name, bbox))
        else:
            without_bbox.append((jid, name))

    print("\n" + "=" * 70)
    print("JURISDICTIONS WITH BOUNDING BOXES (ready for road network download)")
    print("=" * 70)

    for jid, name, bbox in with_bbox:
        print(f"  {jid:<25} {name:<30} bbox: [{bbox[0]:.4f}, {bbox[1]:.4f}, {bbox[2]:.4f}, {bbox[3]:.4f}]")

    print(f"\n  Total with bbox: {len(with_bbox)}")

    if without_bbox:
        print(f"\n  Jurisdictions without bbox ({len(without_bbox)}):")
        for jid, name in without_bbox[:10]:
            print(f"    {jid:<25} {name}")
        if len(without_bbox) > 10:
            print(f"    ... and {len(without_bbox) - 10} more")

    print("=" * 70)

    # Also check state configs
    states_dir = os.path.join(SCRIPT_DIR, "states")
    if os.path.isdir(states_dir):
        for state_name in sorted(os.listdir(states_dir)):
            state_config = load_state_config(state_name)
            if state_config and 'jurisdictions' in state_config:
                state_juris = state_config['jurisdictions']
                state_bbox_count = sum(1 for j in state_juris.values()
                                       if j.get('bbox') and len(j.get('bbox', [])) == 4)
                if state_bbox_count > 0:
                    print(f"\n  State '{state_name}': {state_bbox_count} jurisdictions with bbox")


def discover_latest_release(conn):
    """
    Try to discover the latest Overture Maps release.
    Falls back to DEFAULT_RELEASE if discovery fails.
    """
    logger.info("Checking Overture Maps release availability...")

    # Try known recent releases in reverse chronological order
    candidates = [
        "2026-01-21.0",
        "2025-12-01.0",
        "2025-11-01.0",
        "2025-10-01.0",
    ]

    for release in candidates:
        try:
            s3_path = f"{OVERTURE_S3_BASE}/{release}/theme=transportation/type=segment/*"
            # Just try to read metadata (very fast)
            result = conn.execute(f"""
                SELECT count(*) as cnt
                FROM read_parquet('{s3_path}', hive_partitioning=true)
                WHERE bbox.xmin IS NOT NULL
                LIMIT 1
            """).fetchone()
            if result and result[0] > 0:
                logger.info(f"Using Overture Maps release: {release}")
                return release
        except Exception:
            continue

    logger.warning(f"Could not verify latest release, using default: {DEFAULT_RELEASE}")
    return DEFAULT_RELEASE


def extract_road_segments(conn, bbox, release, max_retries=3):
    """
    Extract road segments from Overture Maps within the given bounding box.
    Returns GeoJSON FeatureCollection.
    """
    west, south, east, north = bbox

    # Add buffer to capture roads crossing the boundary
    west -= BBOX_BUFFER
    south -= BBOX_BUFFER
    east += BBOX_BUFFER
    north += BBOX_BUFFER

    s3_path = f"{OVERTURE_S3_BASE}/{release}/theme=transportation/type=segment/*"

    logger.info(f"Extracting road segments from bbox: [{west:.4f}, {south:.4f}, {east:.4f}, {north:.4f}]")

    query = f"""
        SELECT
            id,
            subtype,
            class,
            JSON_EXTRACT_STRING(names, '$.primary') as name,
            JSON_EXTRACT_STRING(sources, '$[0].dataset') as source,
            CASE
                WHEN JSON_EXTRACT(road_surface, '$[0].value') IS NOT NULL
                THEN JSON_EXTRACT_STRING(road_surface, '$[0].value')
                ELSE NULL
            END as surface,
            CASE
                WHEN JSON_EXTRACT(speed_limits, '$[0].max_speed.value') IS NOT NULL
                THEN CAST(JSON_EXTRACT(speed_limits, '$[0].max_speed.value') AS INTEGER)
                ELSE NULL
            END as speed_limit,
            CASE
                WHEN JSON_EXTRACT(speed_limits, '$[0].max_speed.unit') IS NOT NULL
                THEN JSON_EXTRACT_STRING(speed_limits, '$[0].max_speed.unit')
                ELSE NULL
            END as speed_unit,
            CAST(JSON_EXTRACT(connectors, '$[0].connector_id') AS VARCHAR) as start_connector,
            CAST(JSON_EXTRACT(connectors, '$[1].connector_id') AS VARCHAR) as end_connector,
            JSON_ARRAY_LENGTH(connectors) as connector_count,
            ST_AsGeoJSON(geometry) as geojson_geometry,
            ST_Length_Spheroid(geometry) as length_m
        FROM read_parquet('{s3_path}', hive_partitioning=true)
        WHERE
            bbox.xmin >= {west}
            AND bbox.xmax <= {east}
            AND bbox.ymin >= {south}
            AND bbox.ymax <= {north}
            AND subtype = 'road'
        ORDER BY
            CASE class
                WHEN 'motorway' THEN 1
                WHEN 'trunk' THEN 2
                WHEN 'primary' THEN 3
                WHEN 'secondary' THEN 4
                WHEN 'tertiary' THEN 5
                WHEN 'residential' THEN 6
                WHEN 'service' THEN 7
                ELSE 8
            END
    """

    last_error = None
    for attempt in range(max_retries):
        try:
            logger.info(f"Running segment query (attempt {attempt + 1}/{max_retries})...")
            start_time = time.time()
            result = conn.execute(query).fetchall()
            elapsed = time.time() - start_time
            logger.info(f"Query returned {len(result)} segments in {elapsed:.1f}s")
            break
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                logger.warning(f"Query failed (attempt {attempt + 1}): {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"Segment extraction failed after {max_retries} attempts: {e}")
                raise

    # Build GeoJSON FeatureCollection
    features = []
    columns = ['id', 'subtype', 'class', 'name', 'source', 'surface',
               'speed_limit', 'speed_unit', 'start_connector', 'end_connector',
               'connector_count', 'geojson_geometry', 'length_m']

    for row in result:
        row_dict = dict(zip(columns, row))

        try:
            geometry = json.loads(row_dict['geojson_geometry'])
        except (json.JSONDecodeError, TypeError):
            continue

        # Clean up connector IDs (remove quotes from JSON extraction)
        start_conn = row_dict['start_connector']
        end_conn = row_dict['end_connector']
        if start_conn:
            start_conn = start_conn.strip('"')
        if end_conn:
            end_conn = end_conn.strip('"')

        properties = {
            'id': row_dict['id'],
            'class': row_dict['class'],
            'name': row_dict['name'],
            'surface': row_dict['surface'],
            'speedLimit': row_dict['speed_limit'],
            'speedUnit': row_dict['speed_unit'],
            'startConnector': start_conn,
            'endConnector': end_conn,
            'connectorCount': row_dict['connector_count'],
            'lengthM': round(row_dict['length_m'], 1) if row_dict['length_m'] else None,
            'source': row_dict['source']
        }

        features.append({
            'type': 'Feature',
            'geometry': geometry,
            'properties': properties
        })

    geojson = {
        'type': 'FeatureCollection',
        'features': features,
        'metadata': {
            'source': 'Overture Maps Foundation',
            'release': release,
            'theme': 'transportation',
            'featureType': 'segment',
            'subtype': 'road',
            'bbox': [west, south, east, north],
            'extractedAt': datetime.utcnow().isoformat() + 'Z',
            'totalFeatures': len(features)
        }
    }

    return geojson


def extract_connectors(conn, bbox, release, max_retries=3):
    """
    Extract intersection connectors from Overture Maps within the given bounding box.
    Returns GeoJSON FeatureCollection.
    """
    west, south, east, north = bbox

    # Add buffer
    west -= BBOX_BUFFER
    south -= BBOX_BUFFER
    east += BBOX_BUFFER
    north += BBOX_BUFFER

    s3_path = f"{OVERTURE_S3_BASE}/{release}/theme=transportation/type=connector/*"

    logger.info(f"Extracting connectors from bbox: [{west:.4f}, {south:.4f}, {east:.4f}, {north:.4f}]")

    query = f"""
        SELECT
            id,
            ST_AsGeoJSON(geometry) as geojson_geometry,
            ST_X(geometry) as lon,
            ST_Y(geometry) as lat
        FROM read_parquet('{s3_path}', hive_partitioning=true)
        WHERE
            bbox.xmin >= {west}
            AND bbox.xmax <= {east}
            AND bbox.ymin >= {south}
            AND bbox.ymax <= {north}
    """

    last_error = None
    for attempt in range(max_retries):
        try:
            logger.info(f"Running connector query (attempt {attempt + 1}/{max_retries})...")
            start_time = time.time()
            result = conn.execute(query).fetchall()
            elapsed = time.time() - start_time
            logger.info(f"Query returned {len(result)} connectors in {elapsed:.1f}s")
            break
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                logger.warning(f"Query failed (attempt {attempt + 1}): {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"Connector extraction failed after {max_retries} attempts: {e}")
                raise

    columns = ['id', 'geojson_geometry', 'lon', 'lat']

    # Collect all connector IDs
    connector_data = {}
    for row in result:
        row_dict = dict(zip(columns, row))
        connector_data[row_dict['id']] = row_dict

    return connector_data


def build_intersections(segments_geojson, connector_data):
    """
    Build intersection features from segments and connectors.
    Computes leg count, road names, and road classes at each intersection.
    """
    # Count how many segments reference each connector
    connector_segments = {}  # connector_id -> list of segment properties

    for feature in segments_geojson['features']:
        props = feature['properties']
        start_conn = props.get('startConnector')
        end_conn = props.get('endConnector')

        seg_info = {
            'id': props['id'],
            'class': props['class'],
            'name': props['name'],
            'speedLimit': props.get('speedLimit')
        }

        if start_conn:
            if start_conn not in connector_segments:
                connector_segments[start_conn] = []
            connector_segments[start_conn].append(seg_info)

        if end_conn:
            if end_conn not in connector_segments:
                connector_segments[end_conn] = []
            connector_segments[end_conn].append(seg_info)

    # Build intersection features (connectors with 3+ segment references = true intersections)
    features = []
    stats = {'total_connectors': len(connector_data), 'intersections_3plus': 0,
             'intersections_4plus': 0, 'endpoints': 0}

    for conn_id, segments in connector_segments.items():
        leg_count = len(segments)

        if conn_id not in connector_data:
            continue

        cdata = connector_data[conn_id]

        try:
            geometry = json.loads(cdata['geojson_geometry'])
        except (json.JSONDecodeError, TypeError):
            continue

        # Collect unique road names and classes at this intersection
        road_names = list(set(s['name'] for s in segments if s['name']))
        road_classes = list(set(s['class'] for s in segments if s['class']))
        speed_limits = [s['speedLimit'] for s in segments if s.get('speedLimit')]

        # Determine intersection type based on road classes meeting here
        highest_class = 'unknown'
        class_priority = ['motorway', 'trunk', 'primary', 'secondary', 'tertiary',
                          'residential', 'service', 'unclassified']
        for cls in class_priority:
            if cls in road_classes:
                highest_class = cls
                break

        # Classify the intersection
        if leg_count >= 5:
            int_type = 'complex'
        elif leg_count == 4:
            int_type = '4-leg'
        elif leg_count == 3:
            int_type = '3-leg'
        elif leg_count == 2:
            int_type = 'midblock'
        else:
            int_type = 'endpoint'
            stats['endpoints'] += 1

        if leg_count >= 3:
            stats['intersections_3plus'] += 1
        if leg_count >= 4:
            stats['intersections_4plus'] += 1

        properties = {
            'id': conn_id,
            'legCount': leg_count,
            'type': int_type,
            'roadNames': road_names[:5],  # Limit to 5 names
            'roadClasses': road_classes,
            'highestClass': highest_class,
            'maxSpeedLimit': max(speed_limits) if speed_limits else None,
            'lat': cdata['lat'],
            'lon': cdata['lon']
        }

        features.append({
            'type': 'Feature',
            'geometry': geometry,
            'properties': properties
        })

    # Sort by leg count descending (most complex intersections first)
    features.sort(key=lambda f: f['properties']['legCount'], reverse=True)

    geojson = {
        'type': 'FeatureCollection',
        'features': features,
        'metadata': {
            'source': 'Overture Maps Foundation',
            'release': segments_geojson['metadata']['release'],
            'derivedFrom': 'transportation/segment + transportation/connector',
            'bbox': segments_geojson['metadata']['bbox'],
            'extractedAt': datetime.utcnow().isoformat() + 'Z',
            'totalIntersections': len(features),
            'statistics': stats
        }
    }

    return geojson


def save_geojson(geojson, filepath):
    """Save GeoJSON to file with size reporting."""
    with open(filepath, 'w') as f:
        json.dump(geojson, f, separators=(',', ':'))  # Compact JSON

    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    logger.info(f"Saved {filepath} ({size_mb:.1f} MB, {len(geojson['features'])} features)")

    if size_mb > MAX_FILE_SIZE_WARNING_MB:
        logger.warning(f"File size ({size_mb:.1f} MB) exceeds {MAX_FILE_SIZE_WARNING_MB} MB. "
                       "Consider filtering to a smaller area or excluding minor road classes.")

    return size_mb


def parse_bbox(bbox_str):
    """Parse a comma-separated bbox string into [west, south, east, north]."""
    parts = [float(x.strip()) for x in bbox_str.split(',')]
    if len(parts) != 4:
        raise ValueError("Bbox must have exactly 4 values: west,south,east,north")
    return parts


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Download road network data from Overture Maps for a jurisdiction.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python download_road_network.py --jurisdiction henrico
  python download_road_network.py --state colorado --jurisdiction douglas
  python download_road_network.py --bbox -77.6,37.4,-77.3,37.7
  python download_road_network.py --release 2025-12-01.0 --jurisdiction fairfax_county
  python download_road_network.py --list
        """
    )

    parser.add_argument(
        '--jurisdiction', '-j',
        type=str,
        help='Jurisdiction ID (e.g., henrico, fairfax_county, douglas)'
    )

    parser.add_argument(
        '--state', '-s',
        type=str,
        help='State name for state-specific config (e.g., colorado, virginia)'
    )

    parser.add_argument(
        '--bbox', '-b',
        type=str,
        help='Direct bounding box: west,south,east,north (e.g., -77.6,37.4,-77.3,37.7)'
    )

    parser.add_argument(
        '--release', '-r',
        type=str,
        default=None,
        help=f'Overture Maps release version (default: auto-detect, fallback: {DEFAULT_RELEASE})'
    )

    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default=None,
        help='Output directory (default: data/)'
    )

    parser.add_argument(
        '--segments-only',
        action='store_true',
        help='Only extract road segments (skip intersection computation)'
    )

    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List jurisdictions with bounding boxes and exit'
    )

    parser.add_argument(
        '--skip-minor',
        action='store_true',
        help='Skip minor road classes (service, track, path) to reduce file size'
    )

    return parser.parse_args()


def main():
    """Main function to download road network data."""
    args = parse_args()

    # Load configuration
    config = load_config()

    # Handle --list option
    if args.list:
        list_jurisdictions_with_bbox(config)
        return 0

    # Check DuckDB
    if not check_duckdb():
        return 1

    # Determine bounding box
    bbox = None
    jurisdiction_label = 'custom'

    if args.bbox:
        try:
            bbox = parse_bbox(args.bbox)
            jurisdiction_label = 'custom_bbox'
            logger.info(f"Using direct bbox: {bbox}")
        except ValueError as e:
            logger.error(f"Invalid bbox: {e}")
            return 1
    elif args.jurisdiction:
        bbox = get_jurisdiction_bbox(config, args.jurisdiction, args.state)
        jurisdiction_label = args.jurisdiction
        if not bbox:
            logger.error(f"No bounding box found for jurisdiction '{args.jurisdiction}'")
            logger.info("Run with --list to see jurisdictions with bboxes, or provide --bbox directly")
            return 1
        logger.info(f"Using bbox for {args.jurisdiction}: {bbox}")
    else:
        # Try default jurisdiction from settings
        settings_file = os.path.join(SCRIPT_DIR, "config", "settings.json")
        if os.path.exists(settings_file):
            with open(settings_file, 'r') as f:
                settings = json.load(f)
            default_jid = settings.get('selectedJurisdiction', 'henrico')
            bbox = get_jurisdiction_bbox(config, default_jid)
            jurisdiction_label = default_jid
            if bbox:
                logger.info(f"Using default jurisdiction '{default_jid}' bbox: {bbox}")
            else:
                logger.error(f"Default jurisdiction '{default_jid}' has no bbox")
                return 1
        else:
            logger.error("No jurisdiction or bbox specified. Use --jurisdiction, --bbox, or --list")
            return 1

    # Output directory
    output_dir = args.output_dir or OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    logger.info("=" * 60)
    logger.info(f"Overture Maps Road Network Download")
    logger.info(f"Jurisdiction: {jurisdiction_label}")
    logger.info(f"Bbox: [{bbox[0]:.4f}, {bbox[1]:.4f}, {bbox[2]:.4f}, {bbox[3]:.4f}]")
    logger.info(f"Output: {output_dir}")
    logger.info(f"Started: {datetime.now()}")
    logger.info("=" * 60)

    # Initialize DuckDB
    conn = init_duckdb()

    # Determine release
    release = args.release
    if not release:
        try:
            release = discover_latest_release(conn)
        except Exception as e:
            logger.warning(f"Release discovery failed: {e}. Using default: {DEFAULT_RELEASE}")
            release = DEFAULT_RELEASE

    logger.info(f"Using Overture Maps release: {release}")

    # Extract road segments
    logger.info("\n--- Extracting Road Segments ---")
    try:
        segments_geojson = extract_road_segments(conn, bbox, release)
    except Exception as e:
        logger.error(f"Failed to extract road segments: {e}")
        conn.close()
        return 1

    if len(segments_geojson['features']) == 0:
        logger.error("No road segments found in the specified area!")
        logger.info("Check that the bbox is correct and covers a populated area.")
        conn.close()
        return 1

    # Log segment statistics
    class_counts = {}
    for f in segments_geojson['features']:
        cls = f['properties'].get('class', 'unknown')
        class_counts[cls] = class_counts.get(cls, 0) + 1

    logger.info("Road segments by class:")
    for cls, count in sorted(class_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {cls}: {count}")

    # Filter minor roads if requested
    if args.skip_minor:
        minor_classes = {'service', 'track', 'path', 'footway', 'cycleway', 'steps'}
        original_count = len(segments_geojson['features'])
        segments_geojson['features'] = [
            f for f in segments_geojson['features']
            if f['properties'].get('class') not in minor_classes
        ]
        removed = original_count - len(segments_geojson['features'])
        logger.info(f"Filtered out {removed} minor road segments ({len(segments_geojson['features'])} remaining)")
        segments_geojson['metadata']['totalFeatures'] = len(segments_geojson['features'])

    # Save road segments
    segments_file = os.path.join(output_dir, f"{jurisdiction_label}_road_network.geojson")
    segments_size = save_geojson(segments_geojson, segments_file)

    # Extract connectors and build intersections
    if not args.segments_only:
        logger.info("\n--- Extracting Connectors & Building Intersections ---")
        try:
            connector_data = extract_connectors(conn, bbox, release)
            intersections_geojson = build_intersections(segments_geojson, connector_data)
        except Exception as e:
            logger.error(f"Failed to extract connectors: {e}")
            logger.info("Road segments were saved successfully. Skipping intersection computation.")
            conn.close()
            return 0

        # Filter to only true intersections (3+ legs) for the output
        true_intersections = [
            f for f in intersections_geojson['features']
            if f['properties']['legCount'] >= 3
        ]
        intersections_geojson['features'] = true_intersections
        intersections_geojson['metadata']['totalIntersections'] = len(true_intersections)

        # Save intersections
        intersections_file = os.path.join(output_dir, f"{jurisdiction_label}_intersections.geojson")
        intersections_size = save_geojson(intersections_geojson, intersections_file)

        int_stats = intersections_geojson['metadata']['statistics']
        logger.info(f"Intersection statistics:")
        logger.info(f"  Total connectors: {int_stats['total_connectors']}")
        logger.info(f"  3+ leg intersections: {int_stats['intersections_3plus']}")
        logger.info(f"  4+ leg intersections: {int_stats['intersections_4plus']}")

        # Log intersection type distribution
        type_counts = {}
        for f in true_intersections:
            itype = f['properties']['type']
            type_counts[itype] = type_counts.get(itype, 0) + 1
        logger.info("Intersection types:")
        for itype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            logger.info(f"  {itype}: {count}")

    conn.close()

    logger.info("\n" + "=" * 60)
    logger.info(f"Road network download complete!")
    logger.info(f"  Segments: {len(segments_geojson['features'])} ({segments_size:.1f} MB)")
    if not args.segments_only:
        logger.info(f"  Intersections: {len(true_intersections)} ({intersections_size:.1f} MB)")
    logger.info(f"  Release: {release}")
    logger.info(f"  Output: {output_dir}")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
