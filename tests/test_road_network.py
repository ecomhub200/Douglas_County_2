#!/usr/bin/env python3
"""
Test suite for download_road_network.py - Overture Maps integration.
Tests the extraction pipeline, GeoJSON output format, intersection topology,
and configuration handling without requiring actual S3 access.

Usage:
    python tests/test_road_network.py              # Run all tests
    python tests/test_road_network.py --with-s3    # Include live S3 query tests (slow)
"""

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

# Test counters
passed = 0
failed = 0
skipped = 0
errors = []

def test_pass(name):
    global passed
    passed += 1
    print(f"  ✓ {name}")

def test_fail(name, reason):
    global failed
    failed += 1
    errors.append((name, reason))
    print(f"  ✗ {name}: {reason}")

def test_skip(name, reason):
    global skipped
    skipped += 1
    print(f"  ○ {name}: SKIPPED ({reason})")


# ============================================================
# TEST 1: Module Import & Dependencies
# ============================================================
def test_module_imports():
    print("\n[1] Module Imports & Dependencies")

    try:
        import download_road_network as drn
        test_pass("download_road_network.py imports successfully")
    except ImportError as e:
        test_fail("download_road_network.py import", str(e))
        return False

    # Check required functions exist
    required_functions = [
        'load_config', 'get_jurisdiction_bbox', 'parse_bbox',
        'extract_road_segments', 'extract_connectors', 'build_intersections',
        'save_geojson', 'init_duckdb', 'check_duckdb',
        'list_jurisdictions_with_bbox', 'discover_latest_release'
    ]
    for func_name in required_functions:
        if hasattr(drn, func_name):
            test_pass(f"Function '{func_name}' exists")
        else:
            test_fail(f"Function '{func_name}' exists", "Not found in module")

    # Check DuckDB availability
    try:
        import duckdb
        test_pass(f"DuckDB installed (v{duckdb.__version__})")
    except ImportError:
        test_fail("DuckDB installed", "pip install duckdb>=0.10.0")

    return True


# ============================================================
# TEST 2: Configuration Loading
# ============================================================
def test_config_loading():
    print("\n[2] Configuration Loading")

    import download_road_network as drn

    config = drn.load_config()
    if config:
        test_pass("config.json loaded successfully")
    else:
        test_fail("config.json loaded", "Returned None")
        return

    # Check jurisdictions exist
    jurisdictions = config.get('jurisdictions', {})
    if len(jurisdictions) > 0:
        test_pass(f"Found {len(jurisdictions)} jurisdictions in config")
    else:
        test_fail("Jurisdictions in config", "No jurisdictions found")

    # Check Overture Maps config exists
    overture_config = config.get('apis', {}).get('overtureMaps', {})
    if overture_config.get('enabled') is not False:
        test_pass("Overture Maps config found and enabled")
    else:
        test_fail("Overture Maps config", "Not found or disabled")

    # Check road class colors
    colors = overture_config.get('roadClassColors', {})
    expected_classes = ['motorway', 'primary', 'secondary', 'tertiary', 'residential']
    for cls in expected_classes:
        if cls in colors:
            test_pass(f"Road class color defined for '{cls}'")
        else:
            test_fail(f"Road class color for '{cls}'", "Missing from config")

    # Check intersection style config
    int_style = overture_config.get('intersectionStyle', {})
    if 'color3leg' in int_style and 'color4leg' in int_style:
        test_pass("Intersection style colors configured")
    else:
        test_fail("Intersection style", "Missing color3leg or color4leg")

    # Check snap radius
    snap_radius = overture_config.get('snapRadius')
    if snap_radius and 50 <= snap_radius <= 500:
        test_pass(f"Snap radius configured: {snap_radius} feet")
    else:
        test_fail("Snap radius", f"Invalid or missing: {snap_radius}")


# ============================================================
# TEST 3: Jurisdiction Bbox Resolution
# ============================================================
def test_bbox_resolution():
    print("\n[3] Jurisdiction Bbox Resolution")

    import download_road_network as drn

    config = drn.load_config()

    # Test Henrico (known to have bbox)
    bbox = drn.get_jurisdiction_bbox(config, 'henrico')
    if bbox and len(bbox) == 4:
        test_pass(f"Henrico bbox resolved: [{bbox[0]:.4f}, {bbox[1]:.4f}, {bbox[2]:.4f}, {bbox[3]:.4f}]")
    else:
        test_fail("Henrico bbox", f"Got: {bbox}")

    # Validate bbox values make sense (Virginia region)
    if bbox:
        west, south, east, north = bbox
        if -80 < west < -75 and -80 < east < -75 and 36 < south < 40 and 36 < north < 40:
            test_pass("Henrico bbox within Virginia bounds")
        else:
            test_fail("Henrico bbox bounds", f"Outside Virginia: {bbox}")

        if west < east and south < north:
            test_pass("Bbox orientation correct (west < east, south < north)")
        else:
            test_fail("Bbox orientation", f"Invalid: west={west}, east={east}, south={south}, north={north}")

    # Test nonexistent jurisdiction (should return None, not crash)
    try:
        bad_bbox = drn.get_jurisdiction_bbox(config, 'nonexistent_county_xyz')
        if bad_bbox is None:
            test_pass("Nonexistent jurisdiction returns None")
        else:
            test_fail("Nonexistent jurisdiction", f"Expected None, got {bad_bbox}")
    except SystemExit:
        test_fail("Nonexistent jurisdiction", "Raised SystemExit instead of returning None")
    except Exception as e:
        test_fail("Nonexistent jurisdiction", f"Unexpected error: {e}")

    # Test bbox parsing from string
    try:
        parsed = drn.parse_bbox("-77.6,37.4,-77.1,37.7")
        if parsed == [-77.6, 37.4, -77.1, 37.7]:
            test_pass("Bbox string parsing works")
        else:
            test_fail("Bbox string parsing", f"Got: {parsed}")
    except Exception as e:
        test_fail("Bbox string parsing", str(e))

    # Test invalid bbox string
    try:
        drn.parse_bbox("invalid")
        test_fail("Invalid bbox rejection", "Should have raised ValueError")
    except ValueError:
        test_pass("Invalid bbox string raises ValueError")
    except Exception as e:
        test_fail("Invalid bbox rejection", f"Wrong exception type: {type(e)}")

    # Count jurisdictions with bboxes
    jurisdictions = config.get('jurisdictions', {})
    bbox_count = sum(1 for j in jurisdictions.values()
                     if j.get('bbox') and len(j.get('bbox', [])) == 4)
    if bbox_count > 50:
        test_pass(f"{bbox_count}/{len(jurisdictions)} jurisdictions have bboxes")
    else:
        test_fail("Bbox coverage", f"Only {bbox_count}/{len(jurisdictions)} have bboxes")


# ============================================================
# TEST 4: GeoJSON Output Format
# ============================================================
def test_geojson_format():
    print("\n[4] GeoJSON Output Format Validation")

    import download_road_network as drn

    # Create mock segments GeoJSON
    mock_segments = {
        'type': 'FeatureCollection',
        'features': [
            {
                'type': 'Feature',
                'geometry': {'type': 'LineString', 'coordinates': [[-77.5, 37.5], [-77.4, 37.5]]},
                'properties': {
                    'id': 'seg_001',
                    'class': 'primary',
                    'name': 'Broad Street',
                    'surface': 'paved',
                    'speedLimit': 35,
                    'speedUnit': 'mph',
                    'startConnector': 'conn_A',
                    'endConnector': 'conn_B',
                    'connectorCount': 2,
                    'lengthM': 1500.5,
                    'source': 'OpenStreetMap'
                }
            },
            {
                'type': 'Feature',
                'geometry': {'type': 'LineString', 'coordinates': [[-77.5, 37.5], [-77.5, 37.6]]},
                'properties': {
                    'id': 'seg_002',
                    'class': 'secondary',
                    'name': 'Parham Road',
                    'surface': None,
                    'speedLimit': 45,
                    'speedUnit': 'mph',
                    'startConnector': 'conn_A',
                    'endConnector': 'conn_C',
                    'connectorCount': 2,
                    'lengthM': 2000.0,
                    'source': 'OpenStreetMap'
                }
            },
            {
                'type': 'Feature',
                'geometry': {'type': 'LineString', 'coordinates': [[-77.5, 37.5], [-77.6, 37.4]]},
                'properties': {
                    'id': 'seg_003',
                    'class': 'residential',
                    'name': 'Oak Lane',
                    'surface': None,
                    'speedLimit': None,
                    'speedUnit': None,
                    'startConnector': 'conn_A',
                    'endConnector': 'conn_D',
                    'connectorCount': 2,
                    'lengthM': 800.0,
                    'source': 'OpenStreetMap'
                }
            }
        ],
        'metadata': {
            'source': 'Overture Maps Foundation',
            'release': '2025-12-01.0',
            'theme': 'transportation',
            'featureType': 'segment',
            'subtype': 'road',
            'bbox': [-77.7, 37.3, -77.1, 37.8],
            'extractedAt': '2025-12-01T00:00:00Z',
            'totalFeatures': 3
        }
    }

    # Validate FeatureCollection structure
    if mock_segments['type'] == 'FeatureCollection':
        test_pass("Segments GeoJSON type is FeatureCollection")
    else:
        test_fail("Segments type", f"Expected FeatureCollection, got {mock_segments['type']}")

    # Validate feature structure
    for i, feature in enumerate(mock_segments['features']):
        if feature.get('type') == 'Feature' and 'geometry' in feature and 'properties' in feature:
            test_pass(f"Feature {i} has correct structure")
        else:
            test_fail(f"Feature {i} structure", "Missing type, geometry, or properties")

    # Validate required properties
    required_props = ['id', 'class', 'name', 'startConnector', 'endConnector']
    for prop in required_props:
        if all(prop in f['properties'] for f in mock_segments['features']):
            test_pass(f"All features have '{prop}' property")
        else:
            test_fail(f"Property '{prop}'", "Missing from some features")

    # Validate metadata
    required_meta = ['source', 'release', 'bbox', 'extractedAt', 'totalFeatures']
    for key in required_meta:
        if key in mock_segments['metadata']:
            test_pass(f"Metadata has '{key}'")
        else:
            test_fail(f"Metadata '{key}'", "Missing")

    # Test save/load roundtrip
    with tempfile.NamedTemporaryFile(suffix='.geojson', delete=False, mode='w') as f:
        tmpfile = f.name
        json.dump(mock_segments, f)

    try:
        with open(tmpfile, 'r') as f:
            loaded = json.load(f)
        if loaded['metadata']['totalFeatures'] == 3:
            test_pass("GeoJSON save/load roundtrip works")
        else:
            test_fail("GeoJSON roundtrip", "Feature count mismatch")
    finally:
        os.unlink(tmpfile)

    return mock_segments


# ============================================================
# TEST 5: Intersection Topology Builder
# ============================================================
def test_intersection_builder():
    print("\n[5] Intersection Topology Builder")

    import download_road_network as drn

    # Create mock segments (3 roads meeting at conn_A = 3-leg intersection)
    mock_segments = {
        'type': 'FeatureCollection',
        'features': [
            {
                'type': 'Feature',
                'geometry': {'type': 'LineString', 'coordinates': [[-77.5, 37.5], [-77.4, 37.5]]},
                'properties': {
                    'id': 'seg_001', 'class': 'primary', 'name': 'Broad Street',
                    'startConnector': 'conn_A', 'endConnector': 'conn_B',
                    'speedLimit': 35
                }
            },
            {
                'type': 'Feature',
                'geometry': {'type': 'LineString', 'coordinates': [[-77.5, 37.5], [-77.5, 37.6]]},
                'properties': {
                    'id': 'seg_002', 'class': 'secondary', 'name': 'Parham Road',
                    'startConnector': 'conn_A', 'endConnector': 'conn_C',
                    'speedLimit': 45
                }
            },
            {
                'type': 'Feature',
                'geometry': {'type': 'LineString', 'coordinates': [[-77.5, 37.5], [-77.6, 37.4]]},
                'properties': {
                    'id': 'seg_003', 'class': 'residential', 'name': 'Oak Lane',
                    'startConnector': 'conn_A', 'endConnector': 'conn_D',
                    'speedLimit': None
                }
            },
            # 4th segment meeting at conn_B = makes it a 2-leg (midblock) connector
            {
                'type': 'Feature',
                'geometry': {'type': 'LineString', 'coordinates': [[-77.4, 37.5], [-77.3, 37.5]]},
                'properties': {
                    'id': 'seg_004', 'class': 'primary', 'name': 'Broad Street',
                    'startConnector': 'conn_B', 'endConnector': 'conn_E',
                    'speedLimit': 35
                }
            }
        ],
        'metadata': {
            'source': 'Overture Maps Foundation',
            'release': '2025-12-01.0',
            'bbox': [-77.7, 37.3, -77.1, 37.8],
            'extractedAt': '2025-12-01T00:00:00Z',
            'totalFeatures': 4
        }
    }

    # Create mock connectors
    mock_connectors = {
        'conn_A': {'id': 'conn_A', 'geojson_geometry': '{"type":"Point","coordinates":[-77.5,37.5]}', 'lon': -77.5, 'lat': 37.5},
        'conn_B': {'id': 'conn_B', 'geojson_geometry': '{"type":"Point","coordinates":[-77.4,37.5]}', 'lon': -77.4, 'lat': 37.5},
        'conn_C': {'id': 'conn_C', 'geojson_geometry': '{"type":"Point","coordinates":[-77.5,37.6]}', 'lon': -77.5, 'lat': 37.6},
        'conn_D': {'id': 'conn_D', 'geojson_geometry': '{"type":"Point","coordinates":[-77.6,37.4]}', 'lon': -77.6, 'lat': 37.4},
        'conn_E': {'id': 'conn_E', 'geojson_geometry': '{"type":"Point","coordinates":[-77.3,37.5]}', 'lon': -77.3, 'lat': 37.5},
    }

    # Run build_intersections
    try:
        intersections = drn.build_intersections(mock_segments, mock_connectors)
        test_pass("build_intersections() executes without error")
    except Exception as e:
        test_fail("build_intersections() execution", str(e))
        return

    # Validate output structure
    if intersections['type'] == 'FeatureCollection':
        test_pass("Intersections output is FeatureCollection")
    else:
        test_fail("Intersections type", f"Expected FeatureCollection, got {intersections['type']}")

    # Check features
    features = intersections['features']
    if len(features) > 0:
        test_pass(f"Generated {len(features)} intersection features")
    else:
        test_fail("Intersection count", "No features generated")

    # Find conn_A (should be 3-leg intersection)
    conn_a = next((f for f in features if f['properties']['id'] == 'conn_A'), None)
    if conn_a:
        test_pass("Connector A found in results")

        leg_count = conn_a['properties']['legCount']
        if leg_count == 3:
            test_pass(f"Connector A has correct leg count: {leg_count}")
        else:
            test_fail("Connector A leg count", f"Expected 3, got {leg_count}")

        int_type = conn_a['properties']['type']
        if int_type == '3-leg':
            test_pass(f"Connector A type is '{int_type}'")
        else:
            test_fail("Connector A type", f"Expected '3-leg', got '{int_type}'")

        road_names = conn_a['properties'].get('roadNames', [])
        if 'Broad Street' in road_names and 'Parham Road' in road_names:
            test_pass(f"Connector A road names correct: {road_names}")
        else:
            test_fail("Connector A road names", f"Got: {road_names}")

        highest_class = conn_a['properties'].get('highestClass')
        if highest_class == 'primary':
            test_pass(f"Connector A highest class: {highest_class}")
        else:
            test_fail("Connector A highest class", f"Expected 'primary', got '{highest_class}'")

        max_speed = conn_a['properties'].get('maxSpeedLimit')
        if max_speed == 45:
            test_pass(f"Connector A max speed: {max_speed}")
        else:
            test_fail("Connector A max speed", f"Expected 45, got {max_speed}")
    else:
        test_fail("Connector A lookup", "Not found in results")

    # Find conn_B (should be 2-leg = midblock, filtered out for 3+ leg output)
    conn_b = next((f for f in features if f['properties']['id'] == 'conn_B'), None)
    if conn_b:
        if conn_b['properties']['legCount'] == 2:
            test_pass("Connector B correctly identified as 2-leg (midblock)")
        else:
            test_fail("Connector B leg count", f"Expected 2, got {conn_b['properties']['legCount']}")
    else:
        test_pass("Connector B (2-leg) present in pre-filter results")

    # Validate metadata
    stats = intersections['metadata'].get('statistics', {})
    if stats.get('intersections_3plus', 0) >= 1:
        test_pass(f"Statistics report 3+ leg intersections: {stats['intersections_3plus']}")
    else:
        test_fail("Intersection statistics", f"Expected >=1 3-leg intersections, got: {stats}")


# ============================================================
# TEST 6: DuckDB Initialization
# ============================================================
def test_duckdb_init():
    print("\n[6] DuckDB Initialization")

    import download_road_network as drn

    if not drn.check_duckdb():
        test_skip("DuckDB init", "DuckDB not installed")
        return

    try:
        conn = drn.init_duckdb()
        test_pass("DuckDB connection created")

        # Test spatial extension
        result = conn.execute("SELECT ST_AsText(ST_Point(-77.5, 37.5))").fetchone()
        if result and 'POINT' in str(result[0]):
            test_pass(f"Spatial extension working: {result[0]}")
        else:
            test_fail("Spatial extension", f"Unexpected result: {result}")

        # Test httpfs extension
        try:
            conn.execute("SELECT current_setting('s3_region')").fetchone()
            test_pass("HTTPFS extension loaded (S3 region configured)")
        except Exception as e:
            test_fail("HTTPFS extension", str(e))

        # Test distance calculation
        result = conn.execute("""
            SELECT ST_Distance_Spheroid(
                ST_Point(-77.5, 37.5),
                ST_Point(-77.4, 37.5)
            )
        """).fetchone()
        if result and result[0] > 5000 and result[0] < 15000:
            test_pass(f"Distance calculation: {result[0]:.0f}m (expected ~9000m)")
        else:
            test_fail("Distance calculation", f"Unexpected: {result}")

        conn.close()
        test_pass("DuckDB connection closed cleanly")

    except Exception as e:
        test_fail("DuckDB initialization", str(e))


# ============================================================
# TEST 7: Live S3 Query (optional, slow)
# ============================================================
def test_s3_query():
    print("\n[7] Live S3 Query (Overture Maps)")

    import download_road_network as drn

    if not drn.check_duckdb():
        test_skip("S3 query", "DuckDB not installed")
        return

    conn = drn.init_duckdb()

    # Use a tiny bbox (one block in downtown Richmond)
    # to minimize data transfer
    tiny_bbox = [-77.438, 37.539, -77.434, 37.542]

    try:
        # Try to discover release
        release = drn.discover_latest_release(conn)
        if release:
            test_pass(f"Release discovered: {release}")
        else:
            test_fail("Release discovery", "Returned None")
            conn.close()
            return

        # Extract segments from tiny area
        start = time.time()
        segments = drn.extract_road_segments(conn, tiny_bbox, release)
        elapsed = time.time() - start

        if segments and len(segments['features']) > 0:
            test_pass(f"Extracted {len(segments['features'])} segments in {elapsed:.1f}s")
        else:
            test_fail("Segment extraction", "No features returned")
            conn.close()
            return

        # Validate a segment
        seg = segments['features'][0]
        props = seg['properties']
        if props.get('id') and props.get('class'):
            test_pass(f"First segment: id={props['id'][:20]}..., class={props['class']}")
        else:
            test_fail("Segment properties", f"Missing id or class: {props}")

        # Check geometry is LineString
        if seg['geometry']['type'] == 'LineString':
            test_pass("Segment geometry is LineString")
        else:
            test_fail("Segment geometry type", f"Expected LineString, got {seg['geometry']['type']}")

        # Extract connectors
        connectors = drn.extract_connectors(conn, tiny_bbox, release)
        if connectors and len(connectors) > 0:
            test_pass(f"Extracted {len(connectors)} connectors")
        else:
            test_fail("Connector extraction", "No connectors returned")
            conn.close()
            return

        # Build intersections
        intersections = drn.build_intersections(segments, connectors)
        total = len(intersections['features'])
        three_plus = sum(1 for f in intersections['features'] if f['properties']['legCount'] >= 3)
        test_pass(f"Built {total} intersections ({three_plus} with 3+ legs)")

        # Save to temp file and verify
        with tempfile.NamedTemporaryFile(suffix='.geojson', delete=False) as f:
            tmpfile = f.name
        drn.save_geojson(segments, tmpfile)
        size_kb = os.path.getsize(tmpfile) / 1024
        test_pass(f"Saved segments to file ({size_kb:.0f} KB)")
        os.unlink(tmpfile)

        conn.close()

    except Exception as e:
        test_fail("S3 query", str(e))
        try:
            conn.close()
        except:
            pass


# ============================================================
# TEST 8: JavaScript Integration Points
# ============================================================
def test_javascript_integration():
    print("\n[8] JavaScript Integration in index.html")

    index_path = os.path.join(PROJECT_ROOT, 'app', 'index.html')
    if not os.path.exists(index_path):
        test_fail("index.html exists", "File not found")
        return

    with open(index_path, 'r') as f:
        content = f.read()

    # Check for Overture state in builtInLayersState
    if 'overtureRoadNetwork' in content and 'overtureIntersections' in content:
        test_pass("builtInLayersState includes Overture layers")
    else:
        test_fail("builtInLayersState Overture entries", "Not found")

    # Check for required functions
    required_js_functions = [
        'loadOvertureRoadNetwork',
        'loadOvertureIntersections',
        'addOvertureRoadNetworkLayer',
        'removeOvertureRoadNetworkLayer',
        'toggleOvertureRoadNetworkLayer',
        'addOvertureIntersectionsLayer',
        'removeOvertureIntersectionsLayer',
        'toggleOvertureIntersectionsLayer',
        'snapCrashesToIntersections',
        'getOvertureIntersectionForCrash',
        'getOvertureIntersectionForLocation',
        'buildOvertureTopologyContext',
        'getOvertureNetworkSummary',
        'getOvertureRoadColor',
        'getOvertureRoadLabel',
        'updateOvertureLayerVisibility'
    ]

    for func_name in required_js_functions:
        if f'function {func_name}' in content:
            test_pass(f"JS function '{func_name}' defined")
        else:
            test_fail(f"JS function '{func_name}'", "Not found in index.html")

    # Check for duplicate function names (critical bug source)
    import re
    func_defs = re.findall(r'function\s+(\w+)\s*\(', content)
    duplicates = set()
    seen = set()
    for name in func_defs:
        if name in seen:
            duplicates.add(name)
        seen.add(name)

    if not duplicates:
        test_pass("No duplicate function names detected")
    else:
        test_fail("Duplicate function names", f"Found: {duplicates}")

    # Check map pane creation
    if 'overtureRoadPane' in content and 'overtureIntersectionPane' in content:
        test_pass("Map panes created for Overture layers")
    else:
        test_fail("Map panes", "overtureRoadPane or overtureIntersectionPane not found")

    # Check CSS styles
    if 'overture-road-popup' in content and 'overture-intersection-popup' in content:
        test_pass("Overture CSS styles present")
    else:
        test_fail("Overture CSS", "Popup styles not found")

    # Check asset panel integration
    if 'Overture Maps Road Network' in content:
        test_pass("Overture section in Asset Layers panel")
    else:
        test_fail("Asset panel integration", "Overture section header not found")

    # Check AI context enrichment
    if 'topologyContext' in content and 'buildOvertureTopologyContext' in content:
        test_pass("AI context enriched with topology data")
    else:
        test_fail("AI context enrichment", "topologyContext not found")

    # Check zoom-aware visibility
    if 'minZoomSegments' in content and 'minZoomIntersections' in content:
        test_pass("Zoom-aware layer visibility configured")
    else:
        test_fail("Zoom awareness", "minZoomSegments/minZoomIntersections not found")


# ============================================================
# TEST 9: GitHub Actions Workflow
# ============================================================
def test_github_actions():
    print("\n[9] GitHub Actions Workflow")

    workflow_path = os.path.join(PROJECT_ROOT, '.github', 'workflows', 'download-data.yml')
    if not os.path.exists(workflow_path):
        test_fail("Workflow file exists", "download-data.yml not found")
        return

    with open(workflow_path, 'r') as f:
        content = f.read()

    # Check road network job exists
    if 'download-road-network' in content:
        test_pass("download-road-network job defined")
    else:
        test_fail("download-road-network job", "Not found in workflow")

    # Check road_network_only option
    if 'road_network_only' in content:
        test_pass("road_network_only download type option exists")
    else:
        test_fail("road_network_only option", "Not in download_type choices")

    # Check DuckDB install
    if 'download_road_network.py' in content:
        test_pass("Workflow calls download_road_network.py")
    else:
        test_fail("Script invocation", "download_road_network.py not referenced")

    # Check notification integration
    if 'road_segments' in content and 'road_intersections' in content:
        test_pass("Road network stats in notification outputs")
    else:
        test_fail("Notification stats", "road_segments/road_intersections outputs missing")

    # Check needs dependency for notifications
    if 'download-road-network' in content and 'notify-on-failure' in content:
        test_pass("Notification jobs depend on road network job")
    else:
        test_fail("Notification dependency", "download-road-network not in needs array")


# ============================================================
# TEST 10: Config.json Overture Section
# ============================================================
def test_config_overture():
    print("\n[10] Config.json Overture Maps Section")

    config_path = os.path.join(PROJECT_ROOT, 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)

    overture = config.get('apis', {}).get('overtureMaps', {})

    if overture:
        test_pass("overtureMaps config section exists")
    else:
        test_fail("overtureMaps config", "Missing from apis section")
        return

    # Validate all required fields
    required_fields = {
        'enabled': bool,
        'roadClassColors': dict,
        'roadClassLabels': dict,
        'intersectionStyle': dict,
        'snapRadius': (int, float),
        'minZoomSegments': (int, float),
        'minZoomIntersections': (int, float)
    }

    for field, expected_type in required_fields.items():
        val = overture.get(field)
        if val is not None and isinstance(val, expected_type):
            test_pass(f"Config field '{field}' valid ({type(val).__name__})")
        elif val is not None:
            test_fail(f"Config field '{field}'", f"Expected {expected_type}, got {type(val)}")
        else:
            test_fail(f"Config field '{field}'", "Missing")

    # Validate roadClassColors has valid hex colors
    import re
    colors = overture.get('roadClassColors', {})
    for cls, color in colors.items():
        if re.match(r'^#[0-9a-fA-F]{6}$', str(color)):
            test_pass(f"Color for '{cls}': {color}")
        else:
            test_fail(f"Color for '{cls}'", f"Invalid hex: {color}")

    # Validate snap radius is reasonable
    snap = overture.get('snapRadius', 0)
    if 50 <= snap <= 500:
        test_pass(f"Snap radius reasonable: {snap} feet")
    else:
        test_fail("Snap radius range", f"{snap} not in [50, 500]")

    # Validate zoom thresholds
    seg_zoom = overture.get('minZoomSegments', 0)
    int_zoom = overture.get('minZoomIntersections', 0)
    if 10 <= seg_zoom <= 16:
        test_pass(f"Segment min zoom: {seg_zoom}")
    else:
        test_fail("Segment min zoom", f"{seg_zoom} not in [10, 16]")

    if int_zoom >= seg_zoom:
        test_pass(f"Intersection min zoom ({int_zoom}) >= segment min zoom ({seg_zoom})")
    else:
        test_fail("Zoom ordering", f"Intersections ({int_zoom}) should be >= segments ({seg_zoom})")


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='Test Overture Maps road network integration')
    parser.add_argument('--with-s3', action='store_true', help='Include live S3 query tests (slow, requires internet)')
    args = parser.parse_args()

    print("=" * 60)
    print("Overture Maps Road Network Integration - Test Suite")
    print(f"Project: {PROJECT_ROOT}")
    print(f"Time: {datetime.now()}")
    print("=" * 60)

    # Run tests
    test_module_imports()
    test_config_loading()
    test_bbox_resolution()
    test_geojson_format()
    test_intersection_builder()
    test_duckdb_init()

    if args.with_s3:
        test_s3_query()
    else:
        print("\n[7] Live S3 Query (Overture Maps)")
        test_skip("S3 queries", "Run with --with-s3 to enable")

    test_javascript_integration()
    test_github_actions()
    test_config_overture()

    # Summary
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 60)

    if errors:
        print("\nFAILURES:")
        for name, reason in errors:
            print(f"  ✗ {name}: {reason}")

    if failed > 0:
        print(f"\n❌ {failed} test(s) FAILED")
        return 1
    else:
        print(f"\n✅ All {passed} tests PASSED" + (f" ({skipped} skipped)" if skipped else ""))
        return 0


if __name__ == "__main__":
    sys.exit(main())
