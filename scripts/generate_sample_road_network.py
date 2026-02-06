#!/usr/bin/env python3
"""
Generate sample road network GeoJSON for development/testing.
Creates realistic road segments and intersections for a jurisdiction
based on known major roads, without requiring DuckDB or S3 access.

This is useful for:
- Local development without internet
- CI environments without DuckDB extensions
- Quick prototyping of UI features

Usage:
    python scripts/generate_sample_road_network.py                          # Default (henrico)
    python scripts/generate_sample_road_network.py --jurisdiction henrico
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CONFIG_FILE = os.path.join(PROJECT_ROOT, "config.json")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data")

# Major roads in Henrico County, VA (representative sample)
HENRICO_ROADS = [
    # (name, class, speed_limit, coordinates as [[lon,lat],...])
    ("W Broad St", "primary", 45, [[-77.615, 37.590], [-77.580, 37.590], [-77.540, 37.590], [-77.500, 37.590], [-77.460, 37.590], [-77.420, 37.590], [-77.380, 37.588]]),
    ("Patterson Ave", "secondary", 35, [[-77.600, 37.565], [-77.560, 37.565], [-77.520, 37.565], [-77.480, 37.565], [-77.440, 37.564]]),
    ("Three Chopt Rd", "secondary", 35, [[-77.600, 37.580], [-77.570, 37.580], [-77.540, 37.578], [-77.510, 37.576], [-77.480, 37.575]]),
    ("Parham Rd", "secondary", 45, [[-77.540, 37.630], [-77.540, 37.610], [-77.540, 37.590], [-77.540, 37.570], [-77.540, 37.550], [-77.540, 37.530]]),
    ("Staples Mill Rd", "secondary", 45, [[-77.500, 37.640], [-77.500, 37.620], [-77.500, 37.600], [-77.500, 37.590], [-77.500, 37.575], [-77.500, 37.555]]),
    ("Glenside Dr", "tertiary", 35, [[-77.490, 37.610], [-77.490, 37.600], [-77.490, 37.590], [-77.490, 37.580], [-77.490, 37.570]]),
    ("Gaskins Rd", "secondary", 35, [[-77.570, 37.610], [-77.570, 37.590], [-77.570, 37.570], [-77.570, 37.550]]),
    ("Pump Rd", "secondary", 35, [[-77.600, 37.610], [-77.600, 37.590], [-77.600, 37.570], [-77.600, 37.550]]),
    ("Nuckols Rd", "tertiary", 35, [[-77.610, 37.630], [-77.580, 37.630], [-77.550, 37.630], [-77.520, 37.630]]),
    ("Hungary Rd", "tertiary", 35, [[-77.520, 37.620], [-77.490, 37.620], [-77.460, 37.620], [-77.430, 37.620]]),
    ("Brook Rd", "secondary", 45, [[-77.450, 37.640], [-77.450, 37.620], [-77.450, 37.600], [-77.450, 37.590], [-77.447, 37.570]]),
    ("Mechanicsville Tpke", "primary", 45, [[-77.440, 37.580], [-77.410, 37.575], [-77.380, 37.570], [-77.350, 37.568], [-77.320, 37.565]]),
    ("Williamsburg Rd", "primary", 45, [[-77.420, 37.530], [-77.380, 37.525], [-77.340, 37.520], [-77.300, 37.515], [-77.260, 37.510]]),
    ("Nine Mile Rd", "secondary", 35, [[-77.420, 37.555], [-77.390, 37.550], [-77.360, 37.545], [-77.330, 37.540]]),
    ("Laburnum Ave", "secondary", 45, [[-77.460, 37.570], [-77.440, 37.565], [-77.420, 37.560], [-77.400, 37.555], [-77.380, 37.550]]),
    ("Monument Ave Ext", "tertiary", 25, [[-77.505, 37.555], [-77.480, 37.555], [-77.460, 37.555], [-77.440, 37.555]]),
    ("Creighton Rd", "tertiary", 35, [[-77.370, 37.590], [-77.350, 37.580], [-77.340, 37.570], [-77.330, 37.560]]),
    ("I-64", "motorway", 65, [[-77.650, 37.560], [-77.610, 37.562], [-77.570, 37.565], [-77.530, 37.567], [-77.490, 37.565], [-77.450, 37.560], [-77.410, 37.555], [-77.370, 37.548], [-77.330, 37.540], [-77.290, 37.535], [-77.250, 37.530]]),
    ("I-295", "motorway", 65, [[-77.550, 37.680], [-77.530, 37.660], [-77.510, 37.640], [-77.490, 37.620], [-77.470, 37.600], [-77.460, 37.580], [-77.450, 37.560], [-77.430, 37.540], [-77.400, 37.520], [-77.370, 37.510]]),
    ("I-95", "motorway", 65, [[-77.480, 37.680], [-77.470, 37.660], [-77.460, 37.640], [-77.455, 37.620], [-77.450, 37.600], [-77.445, 37.580], [-77.440, 37.560], [-77.435, 37.540]]),
    ("US-250", "trunk", 55, [[-77.620, 37.590], [-77.580, 37.590], [-77.540, 37.590], [-77.500, 37.590], [-77.460, 37.590], [-77.420, 37.588]]),
    ("US-33", "trunk", 50, [[-77.500, 37.560], [-77.460, 37.558], [-77.420, 37.555], [-77.380, 37.550]]),
    ("Ridgefield Pkwy", "tertiary", 35, [[-77.580, 37.605], [-77.560, 37.600], [-77.540, 37.598], [-77.520, 37.595]]),
    ("Pemberton Rd", "residential", 25, [[-77.560, 37.580], [-77.560, 37.570], [-77.560, 37.560]]),
    ("Skipwith Rd", "residential", 25, [[-77.490, 37.595], [-77.490, 37.585], [-77.490, 37.575]]),
    ("Springfield Rd", "residential", 25, [[-77.510, 37.610], [-77.510, 37.600], [-77.510, 37.590]]),
    ("Cox Rd", "tertiary", 35, [[-77.620, 37.610], [-77.610, 37.600], [-77.600, 37.590], [-77.590, 37.580]]),
    ("Church Rd", "tertiary", 35, [[-77.340, 37.600], [-77.340, 37.580], [-77.340, 37.560], [-77.340, 37.540]]),
    ("Lakeside Ave", "residential", 25, [[-77.460, 37.600], [-77.460, 37.590], [-77.460, 37.580]]),
    ("Hilliard Rd", "residential", 25, [[-77.480, 37.600], [-77.480, 37.590], [-77.480, 37.580]]),
]


def gen_id(prefix="overture"):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def build_road_segments(roads):
    """Build GeoJSON features for road segments."""
    features = []
    connector_map = {}  # (lon, lat) -> connector_id

    def get_or_create_connector(lon, lat):
        # Round to avoid floating point key issues
        key = (round(lon, 5), round(lat, 5))
        if key not in connector_map:
            connector_map[key] = gen_id("conn")
        return connector_map[key]

    for name, road_class, speed, coords in roads:
        # Create one segment per pair of consecutive points
        for i in range(len(coords) - 1):
            start = coords[i]
            end = coords[i + 1]

            start_conn = get_or_create_connector(start[0], start[1])
            end_conn = get_or_create_connector(end[0], end[1])

            # Approximate length in meters
            dlat = abs(end[1] - start[1])
            dlon = abs(end[0] - start[0])
            length_m = ((dlat * 111000) ** 2 + (dlon * 85000) ** 2) ** 0.5

            features.append({
                'type': 'Feature',
                'geometry': {
                    'type': 'LineString',
                    'coordinates': [start, end]
                },
                'properties': {
                    'id': gen_id("seg"),
                    'class': road_class,
                    'name': name,
                    'surface': 'paved',
                    'speedLimit': speed,
                    'speedUnit': 'mph',
                    'startConnector': start_conn,
                    'endConnector': end_conn,
                    'connectorCount': 2,
                    'lengthM': round(length_m, 1),
                    'source': 'OpenStreetMap'
                }
            })

    return features, connector_map


def build_connectors_and_intersections(segments, connector_map):
    """Build intersection features from segments and connector map."""
    # Count segments per connector
    conn_segments = {}
    for feat in segments:
        p = feat['properties']
        for conn_id in [p['startConnector'], p['endConnector']]:
            if conn_id not in conn_segments:
                conn_segments[conn_id] = []
            conn_segments[conn_id].append({
                'id': p['id'],
                'class': p['class'],
                'name': p['name'],
                'speedLimit': p.get('speedLimit')
            })

    # Reverse lookup: connector_id -> (lon, lat)
    conn_coords = {}
    for (lon, lat), conn_id in connector_map.items():
        conn_coords[conn_id] = (lon, lat)

    # Build intersection features (3+ legs only)
    features = []
    stats = {'total_connectors': len(connector_map), 'intersections_3plus': 0, 'intersections_4plus': 0, 'endpoints': 0}

    for conn_id, segs in conn_segments.items():
        leg_count = len(segs)
        if conn_id not in conn_coords:
            continue

        lon, lat = conn_coords[conn_id]

        road_names = list(set(s['name'] for s in segs if s['name']))
        road_classes = list(set(s['class'] for s in segs if s['class']))
        speed_limits = [s['speedLimit'] for s in segs if s.get('speedLimit')]

        # Determine highest class
        highest_class = 'unknown'
        class_priority = ['motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'residential', 'service', 'unclassified']
        for cls in class_priority:
            if cls in road_classes:
                highest_class = cls
                break

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

        if leg_count < 3:
            continue  # Only output true intersections

        features.append({
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [lon, lat]
            },
            'properties': {
                'id': conn_id,
                'legCount': leg_count,
                'type': int_type,
                'roadNames': road_names[:5],
                'roadClasses': road_classes,
                'highestClass': highest_class,
                'maxSpeedLimit': max(speed_limits) if speed_limits else None,
                'lat': lat,
                'lon': lon
            }
        })

    features.sort(key=lambda f: f['properties']['legCount'], reverse=True)

    return features, stats


def main():
    parser = argparse.ArgumentParser(description='Generate sample road network GeoJSON for development')
    parser.add_argument('--jurisdiction', '-j', type=str, default='henrico', help='Jurisdiction ID')
    args = parser.parse_args()

    jurisdiction = args.jurisdiction
    print(f"Generating sample road network for: {jurisdiction}")

    # Build segments
    segments, connector_map = build_road_segments(HENRICO_ROADS)
    print(f"  Generated {len(segments)} road segments from {len(HENRICO_ROADS)} roads")
    print(f"  Created {len(connector_map)} connector points")

    # Build intersections
    intersections, int_stats = build_connectors_and_intersections(segments, connector_map)
    print(f"  Found {len(intersections)} intersections (3+ legs)")
    print(f"    3+ leg: {int_stats['intersections_3plus']}, 4+ leg: {int_stats['intersections_4plus']}")

    # Road class distribution
    class_counts = {}
    for f in segments:
        cls = f['properties']['class']
        class_counts[cls] = class_counts.get(cls, 0) + 1
    print(f"  Road classes: {json.dumps(class_counts)}")

    # Build GeoJSON outputs
    segments_geojson = {
        'type': 'FeatureCollection',
        'features': segments,
        'metadata': {
            'source': 'Overture Maps Foundation (sample)',
            'release': '2025-12-01.0',
            'theme': 'transportation',
            'featureType': 'segment',
            'subtype': 'road',
            'bbox': [-77.66, 37.39, -77.15, 37.72],
            'extractedAt': datetime.utcnow().isoformat() + 'Z',
            'totalFeatures': len(segments),
            'note': 'Sample data generated for development. Run download_road_network.py for production data.'
        }
    }

    intersections_geojson = {
        'type': 'FeatureCollection',
        'features': intersections,
        'metadata': {
            'source': 'Overture Maps Foundation (sample)',
            'release': '2025-12-01.0',
            'derivedFrom': 'transportation/segment + transportation/connector',
            'bbox': [-77.66, 37.39, -77.15, 37.72],
            'extractedAt': datetime.utcnow().isoformat() + 'Z',
            'totalIntersections': len(intersections),
            'statistics': int_stats,
            'note': 'Sample data generated for development.'
        }
    }

    # Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    seg_path = os.path.join(OUTPUT_DIR, f"{jurisdiction}_road_network.geojson")
    with open(seg_path, 'w') as f:
        json.dump(segments_geojson, f, separators=(',', ':'))
    seg_size = os.path.getsize(seg_path) / 1024
    print(f"\n  Saved: {seg_path} ({seg_size:.0f} KB)")

    int_path = os.path.join(OUTPUT_DIR, f"{jurisdiction}_intersections.geojson")
    with open(int_path, 'w') as f:
        json.dump(intersections_geojson, f, separators=(',', ':'))
    int_size = os.path.getsize(int_path) / 1024
    print(f"  Saved: {int_path} ({int_size:.0f} KB)")

    print(f"\n  Done! Open the app and navigate to Map tab to see the road network.")


if __name__ == "__main__":
    main()
