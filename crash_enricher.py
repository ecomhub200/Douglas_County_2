#!/usr/bin/env python3
"""
crash_enricher.py — CrashLens Universal Crash Data Enrichment Module
====================================================================
Shared module that enriches ANY normalized crash dataset by deriving
missing columns from GPS coordinates, contributing circumstances,
temporal data, HPMS federal road data, and OpenStreetMap.

DATA AUTHORITY HIERARCHY (v2.6.5):
  Tier A — HPMS OVERWRITE: FC, Ownership, SYSTEM, Facility Type, Surface Type
    → FHWA-validated road inventory always replaces state crash-report values.
  Tier B — STATE AUTHORITATIVE: RTE Name, Node, Node Offset, RNS MP
    → State data preserved. HPMS/OSM only fill empty cells.
  Tier C — FIRST AVAILABLE: Speed Limit, Alignment, AADT, Lanes, etc.
    → HPMS fills first, then state, then OSM. No overwrites.

ENRICHMENT ORDER:
  Tier 1: Self-enrichment    — derive from existing crash fields (zero deps)
  Tier 3: HPMS (PRIMARY)     — GPS → nearest HPMS segment → federal road attributes
  Tier 2: OSM (fills gaps)   — GPS → nearest OSM road → local road attributes
  Tier 2b: POI proximity     — GPS → nearby bars, schools, signals, hospitals
  Tier 2c: Federal safety    — GPS → NBI bridges, FRA rail, Urban schools, NTM transit

Usage:
    from crash_enricher import CrashEnricher
    enricher = CrashEnricher(state_fips="10", state_abbr="DE")
    df = enricher.enrich_all(df)  # enriches in-place, returns df
"""

import math
import os
import re
import json
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
#  CROSSWALK TABLES — OSM Tags → CrashLens Standard Values
# ─────────────────────────────────────────────────────────────────────────────

# OSM highway tag → FHWA Functional Class (CrashLens standard values)
OSM_HIGHWAY_TO_FC = {
    "motorway":        "1-Interstate (A,1)",
    "motorway_link":   "1-Interstate (A,1)",
    "trunk":           "2-Principal Arterial - Other Freeways and Expressways (B)",
    "trunk_link":      "2-Principal Arterial - Other Freeways and Expressways (B)",
    "primary":         "3-Principal Arterial - Other (E,2)",
    "primary_link":    "3-Principal Arterial - Other (E,2)",
    "secondary":       "4-Minor Arterial (H,3)",
    "secondary_link":  "4-Minor Arterial (H,3)",
    "tertiary":        "5-Major Collector (I,4)",
    "tertiary_link":   "5-Major Collector (I,4)",
    "unclassified":    "6-Minor Collector (5)",
    "residential":     "7-Local (J,6)",
    "service":         "7-Local (J,6)",
    "living_street":   "7-Local (J,6)",
    "track":           "7-Local (J,6)",
    "path":            "7-Local (J,6)",
}

# Functional Class → Ownership derivation
FC_TO_OWNERSHIP = {
    "1-Interstate (A,1)":  "1. State Hwy Agency",
    "2-Principal Arterial - Other Freeways and Expressways (B)": "1. State Hwy Agency",
    "3-Principal Arterial - Other (E,2)": "1. State Hwy Agency",
    "4-Minor Arterial (H,3)": "1. State Hwy Agency",
    "5-Major Collector (I,4)": "2. County Hwy Agency",
    "6-Minor Collector (5)":   "2. County Hwy Agency",
    "7-Local (J,6)":          "3. City or Town Hwy Agency",
}

# Functional Class → SYSTEM derivation (generic — states customize the label)
FC_TO_SYSTEM = {
    "1-Interstate (A,1)":  "DOT Interstate",
    "2-Principal Arterial - Other Freeways and Expressways (B)": "DOT Primary",
    "3-Principal Arterial - Other (E,2)": "DOT Primary",
    "4-Minor Arterial (H,3)": "DOT Secondary",
    "5-Major Collector (I,4)": "DOT Secondary",
    "6-Minor Collector (5)":   "Non-DOT primary",
    "7-Local (J,6)":          "Non-DOT secondary",
}

# Functional Class → default Facility Type
FC_TO_FACILITY_TYPE = {
    "1-Interstate (A,1)":  "4-Two-Way Divided",
    "2-Principal Arterial - Other Freeways and Expressways (B)": "4-Two-Way Divided",
    "3-Principal Arterial - Other (E,2)": "3-Two-Way Undivided",
    "4-Minor Arterial (H,3)": "3-Two-Way Undivided",
    "5-Major Collector (I,4)": "3-Two-Way Undivided",
    "6-Minor Collector (5)":   "3-Two-Way Undivided",
    "7-Local (J,6)":          "3-Two-Way Undivided",
}

# FC → Mainline?
FC_TO_MAINLINE = {
    "1-Interstate (A,1)": "Yes",
    "2-Principal Arterial - Other Freeways and Expressways (B)": "Yes",
    "3-Principal Arterial - Other (E,2)": "Yes",
    "4-Minor Arterial (H,3)": "No",
    "5-Major Collector (I,4)": "No",
    "6-Minor Collector (5)": "No",
    "7-Local (J,6)": "No",
}

# OSM oneway tag → Facility Type refinement
OSM_ONEWAY_FACILITY = {
    "yes": "1-One-Way Undivided",
    "-1":  "1-One-Way Undivided",
}

# OSM lanes + divided → Roadway Description
def derive_roadway_description(oneway, lanes, divided):
    """Derive CrashLens Roadway Description from OSM road attributes."""
    if oneway in ("yes", "-1"):
        return "4. One-Way, Not Divided"
    if divided in ("yes", "true", "1"):
        return "2. Two-Way, Divided, Unprotected Median"
    return "1. Two-Way, Not Divided"

# Route name → FC override (catches cases OSM misclassifies)
ROUTE_PREFIX_TO_FC = {
    r"^I[-\s]?\d":   "1-Interstate (A,1)",
    r"^US[-\s]?\d":  "3-Principal Arterial - Other (E,2)",
    r"^SR[-\s]?\d":  "4-Minor Arterial (H,3)",
    r"^DE[-\s]?\d":  "4-Minor Arterial (H,3)",
    r"^CR[-\s]?\d":  "6-Minor Collector (5)",
    r"^CO[-\s]?\d":  "6-Minor Collector (5)",
}

# ─────────────────────────────────────────────────────────────────────────────
#  TIER 2b: POI PROXIMITY THRESHOLDS
#  Distances for crash-to-POI proximity analysis
# ─────────────────────────────────────────────────────────────────────────────

POI_PROXIMITY = {
    # category     threshold_m  column_name             value_if_near
    "bar":         (457,        "Near_Bar_1500ft",      "Yes"),    # 1500 ft / 0.28 mi
    "school":      (305,        "Near_School_1000ft",   "Yes"),    # 1000 ft / 0.19 mi
    "crossing":    (30,         "Near_Crossing_100ft",  "Yes"),    # 100 ft
    "parking":     (46,         "Near_Parking_150ft",   "Yes"),    # 150 ft
    "rail_xing":   (46,         "Near_Rail_Xing_150ft", "Yes"),    # 150 ft
}

# Traffic control: signal within 30m → "3. Traffic Signal", stop sign within 20m → "4. Stop Sign"
POI_TRAFFIC_CONTROL = {
    "signal":    (30,  "3. Traffic Signal"),
    "stop_sign": (20,  "4. Stop Sign"),
}

# Hospital distance column (continuous, in miles)
POI_HOSPITAL_DIST_COL = "Nearest_Hospital_mi"

# ─────────────────────────────────────────────────────────────────────────────
#  TIER 2c: FEDERAL SAFETY DATA
#  NBI bridges, FRA rail crossings, Urban Institute schools, NTM transit stops
#  These UPGRADE existing OSM/POI proximity flags with authoritative detail.
# ─────────────────────────────────────────────────────────────────────────────

# Federal cache file suffixes (looked up as {abbr}_{suffix}.parquet in cache_dir)
FEDERAL_SOURCES = {
    "schools":        "schools",
    "bridges":        "bridges",
    "rail_crossings": "rail_crossings",
    "transit":        "transit",
}

# Proximity thresholds for federal enrichment (in meters)
FEDERAL_SCHOOL_THRESHOLD_M = 305     # 1000 ft (same as POI Near_School_1000ft)
FEDERAL_BRIDGE_THRESHOLD_M = 46      # 150 ft
FEDERAL_RAIL_THRESHOLD_M = 46        # 150 ft (same as POI Near_Rail_Xing_150ft)
FEDERAL_TRANSIT_THRESHOLD_M = 152    # 500 ft

# Output column names
FEDERAL_COL_SCHOOL_ENROLLMENT = "School_Enrollment_Nearest"
FEDERAL_COL_BRIDGE_CONDITION = "Bridge_Condition"
FEDERAL_COL_BRIDGE_YEAR = "Bridge_Year_Built"
FEDERAL_COL_RAIL_WARNING = "Rail_Warning_Device"
FEDERAL_COL_RAIL_TRAINS = "Rail_Trains_Per_Day"
FEDERAL_COL_TRANSIT = "Near_Transit_500ft"

# ─────────────────────────────────────────────────────────────────────────────
#  TIER 3: HPMS — Federal Highway Performance Monitoring System
#  Official FHWA road data: AADT, FC, speed, lanes, surface, ownership
#  HPMS is the PRIMARY source; OSM fills gaps for roads not in HPMS.
# ─────────────────────────────────────────────────────────────────────────────

# HPMS F_System → CrashLens Functional Class
HPMS_FSYSTEM_TO_FC = {
    1: "1-Interstate (A,1)",
    2: "2-Principal Arterial - Other Freeways and Expressways (B)",
    3: "3-Principal Arterial - Other (E,2)",
    4: "4-Minor Arterial (H,3)",
    5: "5-Major Collector (I,4)",
    6: "6-Minor Collector (5)",
    7: "7-Local (J,6)",
}

# HPMS Ownership → CrashLens Ownership
HPMS_OWNERSHIP_MAP = {
    1: "1. State Hwy Agency",
    2: "2. County Hwy Agency",
    3: "3. City or Town Hwy Agency",
    4: "4. Federal Agency",
    11: "1. State Hwy Agency",      # State Park or Forest
    12: "1. State Hwy Agency",      # State Toll Authority
    21: "2. County Hwy Agency",     # County Toll Authority
    25: "3. City or Town Hwy Agency",
    26: "3. City or Town Hwy Agency",  # Special District
    31: "4. Federal Agency",        # National Forest
    32: "4. Federal Agency",        # Indian Affairs
    40: "4. Federal Agency",        # Other Federal
    50: "4. Federal Agency",        # Railroad
    60: "4. Federal Agency",        # Corps of Engineers
    62: "4. Federal Agency",        # Nat'l Park Service
    70: "4. Federal Agency",        # Military
    80: "4. Federal Agency",        # Other
}

# HPMS Surface_Type → CrashLens Roadway Surface Type
HPMS_SURFACE_MAP = {
    1: "4. Slag, Gravel, Stone",           # Unpaved
    2: "2. Blacktop, Asphalt, Bituminous",  # Asphalt
    3: "2. Blacktop, Asphalt, Bituminous",  # Asphalt over concrete
    4: "2. Blacktop, Asphalt, Bituminous",  # Asphalt on other
    5: "1. Concrete",                       # Concrete (JPCP)
    6: "1. Concrete",                       # Concrete (JRCP)
    7: "1. Concrete",                       # Concrete (CRCP)
    8: "1. Concrete",                       # Concrete over asphalt
    9: "1. Concrete",                       # Concrete on other
    10: "6. Other",                         # Composite
    11: "3. Brick or Block",               # Brick
}

# HPMS Median_Type → CrashLens Roadway Description refinement
HPMS_MEDIAN_TO_DESC = {
    1: "1. Two-Way, Not Divided",           # No median
    2: "2. Two-Way, Divided, Unprotected Median",  # Curbed
    3: "3. Two-Way, Divided, Positive Median Barrier",  # Positive barrier
    4: "2. Two-Way, Divided, Unprotected Median",  # Painted/flush
    5: "2. Two-Way, Divided, Unprotected Median",  # Depressed
    6: "2. Two-Way, Divided, Unprotected Median",  # Raised
}

# HPMS Terrain → CrashLens Roadway Alignment refinement
HPMS_TERRAIN_TO_ALIGNMENT = {
    1: "1. Straight - Level",       # Flat
    2: "3. Grade - Straight",       # Rolling
    3: "4. Grade - Curve",          # Mountainous
}

# ─────────────────────────────────────────────────────────────────────────────
#  DATA AUTHORITY HIERARCHY
#  Determines whether HPMS overwrites state data or only fills gaps.
#
#  TIER A — HPMS-AUTHORITATIVE (OVERWRITE):
#    HPMS always wins when it has a value. Rationale: FHWA-validated road
#    inventory is more accurate than crash-report linked attributes.
#    State data in these columns comes from officer reports or imperfect
#    crash-to-road linking. HPMS data went through federal QA.
#
#  TIER B — STATE-AUTHORITATIVE (FILL only):
#    State data preserved. HPMS/OSM only fills empty cells.
#    Rationale: States know their own route naming, LRS nodes,
#    mileposts, and local designations better than any federal dataset.
#
#  TIER C — FIRST-AVAILABLE (FILL only):
#    HPMS fills first, then state, then OSM. No overwrites.
#    Rationale: Multiple sources are roughly equivalent in quality,
#    or the "best" source depends on context.
# ─────────────────────────────────────────────────────────────────────────────

# Tier A: HPMS overwrites state data (FHWA-validated road inventory)
HPMS_OVERWRITE_COLUMNS = {
    "Functional Class",     # FHWA approves all state FC assignments
    "Ownership",            # FHWA tracks legal road ownership
    "SYSTEM",               # Derived from FC — must be consistent
    "Facility Type",        # One-way/two-way from road inventory, not officer report
    "Roadway Surface Type", # Systematic pavement survey > officer observation
}

# Tier B: State data wins — HPMS/OSM only fill if cell is empty
STATE_AUTHORITATIVE_COLUMNS = {
    "RTE Name",             # State route naming convention (US 29 BUS, SR 234)
    "Node",                 # State LRS node system
    "Node Offset (ft)",     # State LRS reference
    "RNS MP",               # State milepost system
}

# Tier C: First-available wins (HPMS fills → state fills → OSM fills)
# Everything not in Tier A or B defaults to this behavior.
# Includes: Speed Limit, Roadway Alignment, Roadway Description,
#           Traffic Control Type, Intersection Type, Max Speed Diff,
#           all HPMS-only columns (AADT, Through_Lanes, etc.)

# ─────────────────────────────────────────────────────────────────────────────
#  TIER 2c: ROAD ATTRIBUTE ENRICHMENT — Surface, Curvature, Lighting, Sidewalk
# ─────────────────────────────────────────────────────────────────────────────

# OSM surface tag → Roadway Surface Type (golden column)
OSM_SURFACE_MAP = {
    "asphalt":  "2. Blacktop, Asphalt, Bituminous",
    "paved":    "2. Blacktop, Asphalt, Bituminous",
    "concrete": "1. Concrete",
    "gravel":   "4. Slag, Gravel, Stone",
    "dirt":     "5. Dirt",
    "unpaved":  "4. Slag, Gravel, Stone",
    "sand":     "5. Dirt",
    "paving_stones": "3. Brick or Block",
    "cobblestone":   "3. Brick or Block",
}

# Curvature → Roadway Alignment (golden column)
# curvature = road_length / straight_line_distance (1.0 = straight)
def derive_roadway_alignment(curvature):
    """Derive CrashLens Roadway Alignment from computed curvature ratio.
    Note: curvature only captures horizontal curves, not vertical grade.
    Grade info comes from HPMS terrain_type (Tier 3, runs first).
    """
    if curvature <= 1.05:
        return "1. Straight - Level"
    elif curvature <= 1.15:
        return "2. Curve - Level"       # slight curve, no grade info
    elif curvature <= 1.40:
        return "2. Curve - Level"       # moderate curve
    else:
        return "2. Curve - Level"       # sharp curve (no grade from OSM)

def parse_maxspeed_mph(maxspeed_str):
    """Extract numeric speed in mph from OSM maxspeed tag."""
    if not maxspeed_str or maxspeed_str == 'nan':
        return None
    s = str(maxspeed_str).strip().split(';')[0].strip()
    is_kmh = 'km/h' in s or 'kmh' in s
    s = s.replace(' mph', '').replace(' km/h', '').replace(' kmh', '').strip()
    try:
        val = int(float(s))
        if is_kmh or val > 120:
            val = round(val * 0.621371)
        return val
    except (ValueError, TypeError):
        return None

# ─────────────────────────────────────────────────────────────────────────────
#  TIER 1: CONTRIBUTING CIRCUMSTANCE → FLAG DERIVATION
#  These mappings derive boolean flag columns from the state's
#  "Primary Contributing Circumstance" field. Works for any state.
# ─────────────────────────────────────────────────────────────────────────────

# Keywords in contributing circumstance → CrashLens flag columns
CIRCUMSTANCE_TO_FLAGS = {
    "Distracted?": [
        "distract", "inattenti", "cell phone", "texting", "electronic device",
        "passenger distract", "outside distract", "eating", "grooming",
    ],
    "Drowsy?": [
        "drowsy", "asleep", "fell asleep", "fatigued",
        # NOTE: "fatigue" alone is excluded because many states combine
        # "distraction or fatigue" — use only strong fatigue indicators
    ],
    "Speed?": [
        "speed", "exceeding", "too fast", "racing", "aggressive",
    ],
    "Animal Related?": [
        "animal", "deer", "wildlife", "elk", "moose", "horse",
    ],
    "Hitrun?": [
        "hit and run", "hit-and-run", "hitrun", "hit & run", "left scene",
        "fled", "fleeing",
    ],
}

# Combined flag: Distraction + Fatigue often in same field
# (Delaware: "Driver inattention, distraction, or fatigue")
COMBINED_DISTRACTION_FATIGUE_KEYWORDS = [
    "inattention, distraction, or fatigue",
    "inattention/distraction",
]


# ─────────────────────────────────────────────────────────────────────────────
#  TIER 1: INTERSECTION CLUSTERING (GPS-based)
#  Detect intersections by finding GPS coordinate clusters
# ─────────────────────────────────────────────────────────────────────────────

def _haversine_meters(lat1, lon1, lat2, lon2):
    """Haversine distance in meters between two GPS points."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def detect_crash_clusters(lats, lons, radius_m=30.0, min_crashes=3):
    """
    Find GPS crash clusters (potential intersections) using spatial proximity.
    Returns list of (center_lat, center_lon, crash_count, crash_indices).
    """
    n = len(lats)
    if n == 0:
        return []

    # Grid-based pre-filter for O(n) instead of O(n²)
    grid_size = radius_m / 111000  # approx degrees
    grid = defaultdict(list)
    for i in range(n):
        gx = int(lats[i] / grid_size)
        gy = int(lons[i] / grid_size)
        grid[(gx, gy)].append(i)

    clusters = []
    visited = set()

    for i in range(n):
        if i in visited:
            continue
        gx = int(lats[i] / grid_size)
        gy = int(lons[i] / grid_size)

        # Check 3x3 grid neighborhood
        neighbors = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((gx + dx, gy + dy), []):
                    if j not in visited:
                        dist = _haversine_meters(lats[i], lons[i], lats[j], lons[j])
                        if dist <= radius_m:
                            neighbors.append(j)

        if len(neighbors) >= min_crashes:
            clat = sum(lats[j] for j in neighbors) / len(neighbors)
            clon = sum(lons[j] for j in neighbors) / len(neighbors)
            clusters.append((clat, clon, len(neighbors), neighbors))
            visited.update(neighbors)

    return clusters


# ─────────────────────────────────────────────────────────────────────────────
#  TIER 2: OSM ROAD NETWORK MATCHING
#  Downloads state road network via osmnx, builds KD-tree, matches crashes
# ─────────────────────────────────────────────────────────────────────────────

def _load_or_download_road_network(state_name, state_abbr, cache_dir="cache"):
    """
    Load cached road network or download from OSM using osmnx.
    Returns a GeoDataFrame of road edges with attributes.
    """
    cache_path = Path(cache_dir) / f"{state_abbr.lower()}_roads.parquet"

    if cache_path.exists():
        print(f"    Loading cached road network: {cache_path}")
        return pd.read_parquet(cache_path)

    # ── Import osmnx separately so we don't mask internal ImportErrors ──
    try:
        import osmnx as ox
    except ImportError:
        print("    osmnx not installed — Tier 2 OSM enrichment skipped")
        print("    Install: pip install osmnx")
        return None

    try:
        print(f"    Downloading {state_name} road network from OSM (this takes 2-10 min)...")

        # Download drivable road network for the state
        G = ox.graph_from_place(
            f"{state_name}, United States",
            network_type="drive",
            simplify=True,
        )
        # Convert to GeoDataFrame of edges
        edges = ox.graph_to_gdfs(G, nodes=True, edges=True)
        nodes_gdf, edges_gdf = edges

        # Extract key attributes
        road_data = []
        for idx, row in edges_gdf.iterrows():
            u, v, key = idx
            u_node = nodes_gdf.loc[u]
            v_node = nodes_gdf.loc[v]

            # Midpoint of edge
            mid_lat = (u_node.y + v_node.y) / 2
            mid_lon = (u_node.x + v_node.x) / 2

            highway = row.get("highway", "")
            if isinstance(highway, list):
                highway = highway[0]

            name = row.get("name", "")
            if isinstance(name, list):
                name = name[0] if name else ""

            ref = row.get("ref", "")
            if isinstance(ref, list):
                ref = ref[0] if ref else ""

            road_data.append({
                "u_node": u,
                "v_node": v,
                "u_lat": u_node.y,
                "u_lon": u_node.x,
                "v_lat": v_node.y,
                "v_lon": v_node.x,
                "mid_lat": mid_lat,
                "mid_lon": mid_lon,
                "highway": highway or "",
                "name": name or "",
                "ref": ref or "",
                "oneway": str(row.get("oneway", "")),
                "lanes": str(row.get("lanes", "")),
                "maxspeed": str(row.get("maxspeed", "")),
                "length_m": float(row.get("length", 0)),
                "bridge": str(row.get("bridge", "")),
                "tunnel": str(row.get("tunnel", "")),
            })

        road_df = pd.DataFrame(road_data)

        # Also extract intersection nodes (degree ≥ 3)
        node_degrees = dict(G.degree())
        intersections = []
        for node_id, degree in node_degrees.items():
            if degree >= 3:
                n = nodes_gdf.loc[node_id]
                intersections.append({
                    "node_id": node_id,
                    "lat": n.y,
                    "lon": n.x,
                    "degree": degree,
                })
        intersection_df = pd.DataFrame(intersections) if intersections else pd.DataFrame()

        # Cache
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        road_df.to_parquet(cache_path, index=False)
        if len(intersection_df) > 0:
            int_path = Path(cache_dir) / f"{state_abbr.lower()}_intersections.parquet"
            intersection_df.to_parquet(int_path, index=False)

        print(f"    Cached {len(road_df):,} road segments, {len(intersection_df):,} intersections")
        return road_df

    except ImportError as e:
        print(f"    OSM download failed — missing dependency: {e}")
        return None
    except Exception as e:
        print(f"    OSM download error: {e}")
        import traceback
        traceback.print_exc()
        return None


def _build_kdtree(lats, lons):
    """Build a KD-tree from lat/lon arrays for fast nearest-neighbor lookup."""
    from scipy.spatial import KDTree
    # Convert to approximate Cartesian (good enough for nearest-neighbor)
    # At mid-latitudes, 1 degree lat ≈ 111km, 1 degree lon ≈ 85km
    mid_lat = sum(lats) / len(lats)
    lon_scale = math.cos(math.radians(mid_lat))
    points = [(lat * 111000, lon * 111000 * lon_scale) for lat, lon in zip(lats, lons)]
    return KDTree(points), lon_scale


def _match_crashes_to_roads(crash_lats, crash_lons, road_df, max_dist_m=100):
    """
    Match each crash GPS point to the nearest road segment using KD-tree.
    Returns dict of crash_index → road attributes.
    """
    if road_df is None or len(road_df) == 0:
        return {}

    try:
        from scipy.spatial import KDTree
    except ImportError:
        print("    scipy not installed — KD-tree matching unavailable")
        return {}

    # Build tree from road midpoints
    road_lats = road_df["mid_lat"].values.tolist()
    road_lons = road_df["mid_lon"].values.tolist()

    mid_lat = sum(road_lats) / max(len(road_lats), 1)
    lon_scale = math.cos(math.radians(mid_lat))

    road_points = [
        (lat * 111000, lon * 111000 * lon_scale)
        for lat, lon in zip(road_lats, road_lons)
    ]
    tree = KDTree(road_points)

    # Query each crash point
    crash_points = [
        (lat * 111000, lon * 111000 * lon_scale)
        for lat, lon in zip(crash_lats, crash_lons)
    ]

    distances, indices = tree.query(crash_points, k=1)

    matches = {}
    for i, (dist, idx) in enumerate(zip(distances, indices)):
        if dist <= max_dist_m:
            road = road_df.iloc[idx]
            matches[i] = {
                "highway":  road["highway"],
                "name":     road["name"],
                "ref":      road["ref"],
                "oneway":   road["oneway"],
                "lanes":    road["lanes"],
                "maxspeed": road["maxspeed"],
                "length_m": road["length_m"],
                "bridge":   road["bridge"],
                "distance_m": dist,
                "u_node":   road["u_node"],
                "v_node":   road["v_node"],
            }

    return matches


def _match_crashes_to_intersections(crash_lats, crash_lons, state_abbr, cache_dir="cache"):
    """Match crashes to nearest intersection node. Returns dict of crash_index → node info."""
    int_path = Path(cache_dir) / f"{state_abbr.lower()}_intersections.parquet"
    if not int_path.exists():
        return {}

    try:
        from scipy.spatial import KDTree
        int_df = pd.read_parquet(int_path)
        if len(int_df) == 0:
            return {}

        int_lats = int_df["lat"].values.tolist()
        int_lons = int_df["lon"].values.tolist()

        mid_lat = sum(int_lats) / len(int_lats)
        lon_scale = math.cos(math.radians(mid_lat))

        int_points = [(lat * 111000, lon * 111000 * lon_scale) for lat, lon in zip(int_lats, int_lons)]
        tree = KDTree(int_points)

        crash_points = [(lat * 111000, lon * 111000 * lon_scale) for lat, lon in zip(crash_lats, crash_lons)]
        distances, indices = tree.query(crash_points, k=1)

        matches = {}
        for i, (dist, idx) in enumerate(zip(distances, indices)):
            node = int_df.iloc[idx]
            degree = int(node["degree"])

            # Derive Intersection Type from node degree
            if dist > 50:  # More than 50m from intersection
                int_type = "1. Not at Intersection"
            elif degree == 3:
                int_type = "3. Three Approaches"
            elif degree == 4:
                int_type = "4. Four Approaches"
            elif degree >= 5:
                int_type = "5. Five-Point, or More"
            else:
                int_type = "2. Two Approaches"

            matches[i] = {
                "node_id":          int(node["node_id"]),
                "distance_ft":      round(dist * 3.28084),  # meters → feet
                "intersection_type": int_type,
                "degree":           degree,
            }

        return matches

    except Exception as e:
        print(f"    Intersection matching error: {e}")
        return {}


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN ENRICHER CLASS
# ─────────────────────────────────────────────────────────────────────────────

class CrashEnricher:
    """
    Universal crash data enricher. Works for any state.

    Usage:
        enricher = CrashEnricher(state_fips="10", state_abbr="DE", state_name="Delaware")
        df = enricher.enrich_all(df)

    Enrichment tiers:
        Tier 1: Self-enrichment (always runs, zero dependencies)
        Tier 2: OSM road matching (needs osmnx + scipy, cached after first run)
    """

    def __init__(self, state_fips, state_abbr, state_name=None, cache_dir="cache",
                 circumstance_col="PRIMARY CONTRIBUTING CIRCUMSTANCE DESCRIPTION",
                 private_property_col="COLLISION ON PRIVATE PROPERTY"):
        self.state_fips = state_fips
        self.state_abbr = state_abbr
        self.state_name = state_name or state_abbr
        self.cache_dir = cache_dir
        self.circumstance_col = circumstance_col
        self.private_property_col = private_property_col
        self.stats = {}

    def enrich_all(self, df, skip_tier2=False):
        """Run all enrichment tiers. Returns enriched DataFrame.
        
        Order: Tier1 (self) → Tier3 (HPMS, primary) → Tier2 (OSM, fills gaps)
               → Tier2b (POI proximity) → Tier2c (Federal safety data)
        HPMS runs FIRST because it has authoritative federal data.
        OSM runs SECOND to fill gaps (local roads not in HPMS).
        Federal safety data runs LAST to upgrade proximity flags with detail.
        """
        t0 = time.time()
        print(f"\n  {'='*55}")
        print(f"  CrashLens Universal Enricher | {self.state_name} ({self.state_abbr})")
        print(f"  {'='*55}")

        df = self.enrich_tier1(df)

        if not skip_tier2:
            df = self.enrich_tier3_hpms(df)   # HPMS first (authoritative)
            df = self.enrich_tier2(df)         # OSM second (fills gaps)
            df = self.enrich_tier2b_pois(df)   # POI proximity
            df = self.enrich_tier2c_federal(df)  # Federal safety data

        # ── Intersection Analysis (derived AFTER all tiers provide best data) ──
        df = self._derive_intersection_analysis(df)

        elapsed = time.time() - t0
        print(f"\n  Enrichment complete in {elapsed:.1f}s")
        self._print_fill_report(df)
        return df

    # ─── TIER 1: Self-Enrichment ─────────────────────────────────────────

    def enrich_tier1(self, df):
        """
        Tier 1: Derive missing columns from existing crash data fields.
        No external data needed. Works for any state.
        """
        print("\n  [Tier 1] Self-enrichment from existing fields...")

        # 1. Contributing Circumstance → Flag columns
        df = self._derive_flags_from_circumstance(df)

        # 2. Private Property → Mainline?
        df = self._derive_mainline_from_private_property(df)

        # 3. Collision Type + Pedestrian/Bike → cross-validate flags
        df = self._cross_validate_flags(df)

        # 4. GPS clustering → intersection proximity detection
        df = self._detect_intersections_from_clusters(df)

        # 5. Severity → K/A/B/C People count estimation
        df = self._estimate_kabco_people(df)

        # 6. Route name pattern → Functional Class (if RTE Name exists)
        df = self._derive_fc_from_route_name(df)

        return df

    def _derive_flags_from_circumstance(self, df):
        """Derive Distracted?, Drowsy?, Speed?, Animal Related?, Hitrun? from contributing circumstance."""
        circ_col = self.circumstance_col

        # Find the circumstance column (case-insensitive search)
        actual_col = None
        for c in df.columns:
            if c.upper().strip() == circ_col.upper().strip():
                actual_col = c
                break
        if actual_col is None:
            # Try finding it among extra columns
            for c in df.columns:
                cl = c.upper().strip()
                if "CONTRIBUTING" in cl and "CIRCUMSTANCE" in cl:
                    actual_col = c
                    break
        if actual_col is None:
            print("    No contributing circumstance column found — skipping flag derivation")
            return df

        circ_lower = df[actual_col].fillna("").str.strip().str.lower()
        derived_count = 0

        for flag, keywords in CIRCUMSTANCE_TO_FLAGS.items():
            if flag in df.columns and df[flag].fillna("").str.strip().ne("").any():
                existing_yes = (df[flag] == "Yes").sum()
                if existing_yes > 0:
                    continue  # Don't overwrite existing data

            mask = pd.Series(False, index=df.index)
            for kw in keywords:
                mask |= circ_lower.str.contains(kw, na=False)

            df[flag] = mask.map({True: "Yes", False: "No"})
            yes_count = mask.sum()
            if yes_count > 0:
                derived_count += yes_count
                print(f"    {flag}: {yes_count} 'Yes' derived from contributing circumstance")

        # Handle combined Distraction+Fatigue fields (e.g., Delaware)
        # Conservative: combined field → Distracted?=Yes only
        # Drowsy? only from strong standalone fatigue indicators
        for combo_kw in COMBINED_DISTRACTION_FATIGUE_KEYWORDS:
            combo_mask = circ_lower.str.contains(combo_kw, na=False)
            if combo_mask.any():
                df.loc[combo_mask, "Distracted?"] = "Yes"
                # DON'T flag Drowsy? from combined field — too imprecise
                print(f"    Note: {combo_mask.sum()} rows have combined distraction/fatigue coding — "
                      f"only Distracted? flagged (Drowsy? requires standalone fatigue indicator)")

        self.stats["tier1_flags_derived"] = derived_count
        return df

    def _derive_mainline_from_private_property(self, df):
        """Derive Mainline? from Collision on Private Property: N (public road) = potential mainline."""
        pp_col = self.private_property_col
        actual_col = None
        for c in df.columns:
            if c.upper().strip() == pp_col.upper().strip():
                actual_col = c
                break

        if actual_col is None:
            return df

        existing = df.get("Mainline?", pd.Series("", index=df.index))
        needs_fill = existing.fillna("").str.strip() == ""

        if needs_fill.any():
            pp_val = df[actual_col].fillna("").str.strip().str.upper()
            # Private property = NOT mainline; public road = potentially mainline
            # (will be refined by Tier 2 FC-based derivation)
            df.loc[needs_fill, "Mainline?"] = pp_val.map(
                {"N": "Yes", "Y": "No"}
            ).fillna("No")
            print(f"    Mainline?: derived from Private Property ({(pp_val == 'N').sum()} public road crashes)")

        return df

    def _cross_validate_flags(self, df):
        """Cross-validate flag columns against collision type and each other."""
        fixed = 0

        # If Pedestrian?=No but Collision Type contains pedestrian → fix
        if "Pedestrian?" in df.columns and "Collision Type" in df.columns:
            ped_collision = df["Collision Type"].fillna("").str.contains("12\\. Ped|ped", case=False, na=False)
            ped_no = df["Pedestrian?"].fillna("") == "No"
            fix_mask = ped_collision & ped_no
            if fix_mask.any():
                df.loc[fix_mask, "Pedestrian?"] = "Yes"
                fixed += fix_mask.sum()

        # If Bike?=No but Collision Type contains bicyclist → fix
        if "Bike?" in df.columns and "Collision Type" in df.columns:
            bike_collision = df["Collision Type"].fillna("").str.contains("13\\. Bicycl|bicycl", case=False, na=False)
            bike_no = df["Bike?"].fillna("") == "No"
            fix_mask = bike_collision & bike_no
            if fix_mask.any():
                df.loc[fix_mask, "Bike?"] = "Yes"
                fixed += fix_mask.sum()

        if fixed:
            print(f"    Cross-validation: {fixed} flag corrections (Ped/Bike vs Collision Type)")
        self.stats["tier1_cross_validated"] = fixed
        return df

    def _detect_intersections_from_clusters(self, df):
        """Use GPS clustering to detect intersection-proximity crashes."""
        if "x" not in df.columns or "y" not in df.columns:
            return df

        try:
            lons = pd.to_numeric(df["x"], errors="coerce")
            lats = pd.to_numeric(df["y"], errors="coerce")
            valid = lats.notna() & lons.notna() & (lats != 0) & (lons != 0)

            if valid.sum() < 10:
                return df

            valid_lats = lats[valid].tolist()
            valid_lons = lons[valid].tolist()
            valid_indices = df.index[valid].tolist()

            clusters = detect_crash_clusters(valid_lats, valid_lons, radius_m=30, min_crashes=3)

            # Mark crashes near cluster centers as "at intersection"
            cluster_count = 0
            for clat, clon, count, member_indices in clusters:
                for mi in member_indices:
                    actual_idx = valid_indices[mi]
                    # Only fill if Intersection Type is currently blank
                    if df.at[actual_idx, "Intersection Type"] in ("", "Not Applicable", None):
                        df.at[actual_idx, "Intersection Type"] = "4. Four Approaches"  # conservative default
                        cluster_count += 1

            if cluster_count:
                print(f"    GPS clustering: {len(clusters)} potential intersections detected, "
                      f"{cluster_count} crashes tagged")
            self.stats["tier1_intersection_clusters"] = len(clusters)

        except Exception as e:
            print(f"    GPS clustering error: {e}")

        return df

    def _estimate_kabco_people(self, df):
        """Estimate K/A/B/C people counts from severity (1 per crash as minimum)."""
        if "Crash Severity" not in df.columns:
            return df

        for sev, col in [("K", "K_People"), ("A", "A_People"), ("B", "B_People"), ("C", "C_People")]:
            if col in df.columns:
                needs_fill = df[col].fillna("").str.strip().isin(["", "0"])
                sev_match = df["Crash Severity"] == sev
                fill_mask = needs_fill & sev_match
                if fill_mask.any():
                    df.loc[fill_mask, col] = "1"  # Minimum 1 person

        return df

    def _derive_fc_from_route_name(self, df):
        """If RTE Name is populated, derive Functional Class from route name patterns."""
        if "RTE Name" not in df.columns or "Functional Class" not in df.columns:
            return df

        needs_fc = df["Functional Class"].fillna("").str.strip() == ""
        has_rte = df["RTE Name"].fillna("").str.strip() != ""
        fill_mask = needs_fc & has_rte

        if not fill_mask.any():
            return df

        filled = 0
        for pattern, fc in ROUTE_PREFIX_TO_FC.items():
            match_mask = fill_mask & df["RTE Name"].str.upper().str.match(pattern, na=False)
            if match_mask.any():
                df.loc[match_mask, "Functional Class"] = fc
                filled += match_mask.sum()
                fill_mask &= ~match_mask  # Don't double-fill

        if filled:
            print(f"    Route name → FC: {filled} rows derived from route name patterns")

        return df

    # ─── TIER 3: HPMS Federal Road Data (PRIMARY SOURCE) ─────────────────

    def enrich_tier3_hpms(self, df):
        """
        Tier 3: Match crashes to HPMS road segments (federal authoritative data).

        DATA AUTHORITY HIERARCHY:
          Tier A (OVERWRITE): FC, Ownership, SYSTEM, Facility Type, Surface Type
            → HPMS always wins. State crash-report values are replaced.
          Tier B (FILL only): RTE Name, Node, Node Offset, RNS MP
            → State data preserved. HPMS only fills empty cells.
          Tier C (FILL only): Speed Limit, Alignment, Description, AADT, Lanes...
            → First-available wins. HPMS fills, then OSM fills remaining gaps.
        """
        hpms_path = Path(self.cache_dir) / f"{self.state_abbr.lower()}_hpms.parquet"
        if not hpms_path.exists():
            print("\n  [Tier 3] HPMS federal road data — skipped (no HPMS cache)")
            print(f"    Generate with: python generate_hpms_data.py --state {self.state_abbr}")
            return df

        try:
            from scipy.spatial import KDTree
        except ImportError:
            print("\n  [Tier 3] HPMS — skipped (scipy not installed)")
            return df

        print("\n  [Tier 3] HPMS federal road data (authoritative)...")
        hpms_df = pd.read_parquet(hpms_path)
        print(f"    Loaded {len(hpms_df):,} HPMS road segments")

        # Get valid crash coordinates
        try:
            lons = pd.to_numeric(df["x"], errors="coerce")
            lats = pd.to_numeric(df["y"], errors="coerce")
        except Exception:
            print("    No valid GPS — Tier 3 skipped")
            return df

        valid = lats.notna() & lons.notna() & (lats != 0) & (lons != 0)
        if valid.sum() == 0:
            return df

        crash_lats = lats[valid].tolist()
        crash_lons = lons[valid].tolist()
        valid_indices = df.index[valid].tolist()

        # Build KDTree from HPMS midpoints
        h_lats = hpms_df["mid_lat"].tolist()
        h_lons = hpms_df["mid_lon"].tolist()
        mid_lat = sum(crash_lats) / len(crash_lats)
        lon_scale = math.cos(math.radians(mid_lat))

        hpms_points = [
            (lat * 111000, lon * 111000 * lon_scale)
            for lat, lon in zip(h_lats, h_lons)
        ]
        crash_points = [
            (lat * 111000, lon * 111000 * lon_scale)
            for lat, lon in zip(crash_lats, crash_lons)
        ]

        tree = KDTree(hpms_points)
        dists, indices = tree.query(crash_points, k=1)

        # Track fills vs overwrites separately
        filled = defaultdict(int)       # empty cell → HPMS value
        overwritten = defaultdict(int)  # state value → replaced by HPMS
        matched = 0

        # Ensure new columns exist
        for col in ["AADT", "Through_Lanes", "Access_Control", "Lane_Width_ft",
                     "Median_Width_ft", "Shoulder_Width_ft", "AADT_Trucks",
                     "Design_Speed_mph"]:
            if col not in df.columns:
                df[col] = ""

        # ── Helper: should we write this value? ──
        def _should_write(col_name, crash_idx):
            """Returns (should_write, is_overwrite) based on authority tier."""
            cell = str(df.at[crash_idx, col_name]).strip() if col_name in df.columns else ""
            has_value = bool(cell and cell.lower() not in ("", "nan", "none"))
            if col_name in HPMS_OVERWRITE_COLUMNS:
                # Tier A: always write if HPMS has data
                return True, has_value
            elif col_name in STATE_AUTHORITATIVE_COLUMNS:
                # Tier B: only fill empty cells (state data is sacred)
                return not has_value, False
            else:
                # Tier C: only fill empty cells (first-available)
                return not has_value, False

        for i, (dist, idx) in enumerate(zip(dists, indices)):
            if dist > 100:  # skip if >100m from nearest HPMS segment
                continue
            matched += 1
            crash_idx = valid_indices[i]
            road = hpms_df.iloc[idx]

            # ── Functional Class (TIER A — OVERWRITE) ──
            f_sys = int(road.get("f_system", 0) or 0)
            fc = HPMS_FSYSTEM_TO_FC.get(f_sys, "") if f_sys else ""
            if fc:
                should, is_ow = _should_write("Functional Class", crash_idx)
                if should:
                    df.at[crash_idx, "Functional Class"] = fc
                    if is_ow:
                        overwritten["Functional Class"] += 1
                    else:
                        filled["Functional Class"] += 1

                # ── Ownership (TIER A — OVERWRITE) ──
                own_code = int(road.get("ownership", 0) or 0)
                own = HPMS_OWNERSHIP_MAP.get(own_code, FC_TO_OWNERSHIP.get(fc, ""))
                if own:
                    should, is_ow = _should_write("Ownership", crash_idx)
                    if should:
                        df.at[crash_idx, "Ownership"] = own
                        if is_ow:
                            overwritten["Ownership"] += 1
                        else:
                            filled["Ownership"] += 1

                # ── SYSTEM (TIER A — OVERWRITE, derived from FC) ──
                sys_val = FC_TO_SYSTEM.get(fc, "")
                if sys_val:
                    should, is_ow = _should_write("SYSTEM", crash_idx)
                    if should:
                        df.at[crash_idx, "SYSTEM"] = sys_val
                        if is_ow:
                            overwritten["SYSTEM"] += 1
                        else:
                            filled["SYSTEM"] += 1

                # Mainline? always set from FC (not a state-reported field)
                df.at[crash_idx, "Mainline?"] = FC_TO_MAINLINE.get(fc, "No")

            # ── Facility Type (TIER A — OVERWRITE) ──
            fac = int(road.get("facility_type", 0) or 0)
            med = int(road.get("median_type", 0) or 0)
            if fac:
                fac_val = ""
                if fac == 1:
                    fac_val = "1-One-Way Undivided"
                elif med and med >= 2:
                    fac_val = "4-Two-Way Divided"
                else:
                    fac_val = "3-Two-Way Undivided"
                if fac_val:
                    should, is_ow = _should_write("Facility Type", crash_idx)
                    if should:
                        df.at[crash_idx, "Facility Type"] = fac_val
                        if is_ow:
                            overwritten["Facility Type"] += 1
                        else:
                            filled["Facility Type"] += 1

            # ── Roadway Surface Type (TIER A — OVERWRITE) ──
            surf = int(road.get("surface_type", 0) or 0)
            if surf:
                mapped = HPMS_SURFACE_MAP.get(surf, "")
                if mapped:
                    should, is_ow = _should_write("Roadway Surface Type", crash_idx)
                    if should:
                        df.at[crash_idx, "Roadway Surface Type"] = mapped
                        if is_ow:
                            overwritten["Roadway Surface Type"] += 1
                        else:
                            filled["Roadway Surface Type"] += 1

            # ── AADT (TIER C — FILL, HPMS-only field, no state equivalent) ──
            aadt_val = int(road.get("aadt", 0) or 0)
            if aadt_val > 0 and not df.at[crash_idx, "AADT"]:
                df.at[crash_idx, "AADT"] = str(aadt_val)
                filled["AADT"] += 1

            # ── Max Speed Diff (TIER C — FILL) ──
            spd = int(road.get("speed_limit", 0) or 0)
            if spd > 0 and not df.at[crash_idx, "Max Speed Diff"]:
                df.at[crash_idx, "Max Speed Diff"] = str(spd)
                filled["Max Speed Diff"] += 1

            # ── RTE Name (TIER B — STATE AUTHORITATIVE, fill only) ──
            rte = str(road.get("route_name", "") or "").strip()
            if rte and not df.at[crash_idx, "RTE Name"]:
                df.at[crash_idx, "RTE Name"] = rte
                filled["RTE Name"] += 1

            # ── Roadway Description (TIER C — FILL) ──
            if not df.at[crash_idx, "Roadway Description"]:
                if fac == 1:  # one-way
                    df.at[crash_idx, "Roadway Description"] = "4. One-Way, Not Divided"
                    filled["Roadway Description"] += 1
                elif med and med in HPMS_MEDIAN_TO_DESC:
                    df.at[crash_idx, "Roadway Description"] = HPMS_MEDIAN_TO_DESC[med]
                    filled["Roadway Description"] += 1

            # ── Roadway Alignment (TIER C — FILL) ──
            terrain = int(road.get("terrain_type", 0) or 0)
            curve = str(road.get("curve_class", "") or "").strip()
            if not df.at[crash_idx, "Roadway Alignment"]:
                if curve in ("D", "E"):
                    df.at[crash_idx, "Roadway Alignment"] = "4. Grade - Curve"
                    filled["Roadway Alignment"] += 1
                elif curve in ("B", "C"):
                    df.at[crash_idx, "Roadway Alignment"] = "2. Curve - Level"
                    filled["Roadway Alignment"] += 1
                elif terrain and terrain in HPMS_TERRAIN_TO_ALIGNMENT:
                    df.at[crash_idx, "Roadway Alignment"] = HPMS_TERRAIN_TO_ALIGNMENT[terrain]
                    filled["Roadway Alignment"] += 1

            # ── Through Lanes (TIER C — FILL, HPMS-only) ──
            lanes = int(road.get("through_lanes", 0) or 0)
            if lanes > 0 and not df.at[crash_idx, "Through_Lanes"]:
                df.at[crash_idx, "Through_Lanes"] = str(lanes)
                filled["Through_Lanes"] += 1

            # ── Access Control (TIER C — FILL, HPMS-only) ──
            acc = int(road.get("access_control", 0) or 0)
            acc_map = {1: "Full", 2: "Partial", 3: "None"}
            if acc and not df.at[crash_idx, "Access_Control"]:
                df.at[crash_idx, "Access_Control"] = acc_map.get(acc, "")
                filled["Access_Control"] += 1

            # ── Lane Width (TIER C — FILL, HPMS-only) ──
            lw = float(road.get("lane_width", 0) or 0)
            if lw > 0 and not df.at[crash_idx, "Lane_Width_ft"]:
                df.at[crash_idx, "Lane_Width_ft"] = str(round(lw))
                filled["Lane_Width_ft"] += 1

            # ── Median Width (TIER C — FILL, HPMS-only) ──
            mw = float(road.get("median_width", 0) or 0)
            if mw > 0 and not df.at[crash_idx, "Median_Width_ft"]:
                df.at[crash_idx, "Median_Width_ft"] = str(round(mw))
                filled["Median_Width_ft"] += 1

            # ── Shoulder Width (TIER C — FILL, HPMS-only) ──
            sw = float(road.get("shoulder_width_r", 0) or 0)
            if sw > 0 and not df.at[crash_idx, "Shoulder_Width_ft"]:
                df.at[crash_idx, "Shoulder_Width_ft"] = str(round(sw))
                filled["Shoulder_Width_ft"] += 1

            # ── Truck AADT (TIER C — FILL, HPMS-only) ──
            trk_comb = int(road.get("aadt_combination", 0) or 0)
            trk_su = int(road.get("aadt_single_unit", 0) or 0)
            if (trk_comb + trk_su) > 0 and not df.at[crash_idx, "AADT_Trucks"]:
                df.at[crash_idx, "AADT_Trucks"] = str(trk_comb + trk_su)
                filled["AADT_Trucks"] += 1

            # ── Design Speed (TIER C — FILL, HPMS-only) ──
            ds = int(road.get("design_speed", 0) or 0)
            if ds > 0 and not df.at[crash_idx, "Design_Speed_mph"]:
                df.at[crash_idx, "Design_Speed_mph"] = str(ds)
                filled["Design_Speed_mph"] += 1

            # ── Traffic Control Type (TIER C — FILL) ──
            sig = int(road.get("signal_type", 0) or 0)
            if sig > 0 and not df.at[crash_idx, "Traffic Control Type"]:
                sig_map = {1: "3. Traffic Signal", 2: "3. Traffic Signal",
                           3: "3. Traffic Signal", 4: "4. Stop Sign", 5: "13. Other"}
                mapped = sig_map.get(sig, "")
                if mapped:
                    df.at[crash_idx, "Traffic Control Type"] = mapped
                    filled["Traffic Control Type"] += 1

        # ── Report ──
        print(f"    Matched: {matched:,} / {len(crash_lats):,} ({matched/max(len(crash_lats),1)*100:.1f}%)")
        if overwritten:
            print(f"    TIER A — OVERWRITTEN (HPMS replaces state data):")
            for col, count in sorted(overwritten.items()):
                print(f"      {col}: {count:,} rows overwritten by HPMS")
        if filled:
            print(f"    FILLED (empty cells → HPMS value):")
            for col, count in sorted(filled.items()):
                print(f"      {col}: {count:,} rows filled")

        self.stats["tier3_matched"] = matched
        self.stats["tier3_overwritten"] = dict(overwritten)
        self.stats["tier3_filled"] = dict(filled)
        return df

    # ─── TIER 2: OSM Road Network Matching ───────────────────────────────

    def enrich_tier2(self, df):
        """
        Tier 2: Match crashes to OSM road network, derive road attributes.

        AUTHORITY HIERARCHY (Tier 3 runs BEFORE this):
          - HPMS Tier A columns (FC, Ownership, SYSTEM, Facility Type, Surface Type)
            are already set by Tier 3 with authoritative values.
            OSM will NOT touch them (existing 'not df.at[idx, col]' guards skip filled cells).
          - For crashes HPMS didn't match (<100m threshold), OSM fills everything.
          - OSM is the universal backstop for local/residential roads not in HPMS.
          - OSM-unique columns (Intersection Name, Node, lighting, sidewalk, etc.)
            are always filled by this tier regardless of HPMS.
        """
        print("\n  [Tier 2] OSM road network matching...")

        # Load or download road network
        road_df = _load_or_download_road_network(
            self.state_name, self.state_abbr, self.cache_dir
        )
        if road_df is None:
            print("    Tier 2 skipped — no road network available")
            return df

        # Ensure Intersection Name column exists
        if "Intersection Name" not in df.columns:
            df["Intersection Name"] = ""

        # Build node → road names lookup for Intersection Name derivation
        node_road_names = defaultdict(set)
        if "u_node" in road_df.columns and "v_node" in road_df.columns:
            for _, road_row in road_df.iterrows():
                name = str(road_row.get("name", "") or "").strip()
                ref = str(road_row.get("ref", "") or "").strip()
                label = name if name and name != "nan" else ref if ref and ref != "nan" else ""
                if label:
                    node_road_names[road_row["u_node"]].add(label)
                    node_road_names[road_row["v_node"]].add(label)
            print(f"    Intersection name lookup: {len(node_road_names):,} nodes with road names")

        # Get valid crash coordinates
        try:
            lons = pd.to_numeric(df["x"], errors="coerce")
            lats = pd.to_numeric(df["y"], errors="coerce")
        except Exception:
            print("    No valid GPS coordinates — Tier 2 skipped")
            return df

        valid = lats.notna() & lons.notna() & (lats != 0) & (lons != 0)
        if valid.sum() == 0:
            return df

        crash_lats = lats[valid].tolist()
        crash_lons = lons[valid].tolist()
        valid_indices = df.index[valid].tolist()

        # Match crashes to nearest road segments
        print(f"    Matching {len(crash_lats):,} crashes to road network...")
        matches = _match_crashes_to_roads(crash_lats, crash_lons, road_df, max_dist_m=100)
        print(f"    Matched: {len(matches):,} / {len(crash_lats):,} ({len(matches)/max(len(crash_lats),1)*100:.1f}%)")

        # Apply road attributes to crash rows
        filled = defaultdict(int)

        for i, road in matches.items():
            idx = valid_indices[i]
            highway = road["highway"]
            fc = OSM_HIGHWAY_TO_FC.get(highway, "")

            # Apply route ref override (I-95, US-13, DE-1, etc.)
            ref = road.get("ref", "")
            if ref:
                for pattern, override_fc in ROUTE_PREFIX_TO_FC.items():
                    if re.match(pattern, ref.upper()):
                        fc = override_fc
                        break

            # RTE Name — from OSM name or ref
            rte_name = road.get("ref", "") or road.get("name", "")
            if rte_name and not df.at[idx, "RTE Name"]:
                df.at[idx, "RTE Name"] = rte_name
                filled["RTE Name"] += 1

            # Functional Class
            if fc and not df.at[idx, "Functional Class"]:
                df.at[idx, "Functional Class"] = fc
                filled["Functional Class"] += 1

                # Derive downstream columns from FC
                if not df.at[idx, "Ownership"]:
                    df.at[idx, "Ownership"] = FC_TO_OWNERSHIP.get(fc, "")
                    filled["Ownership"] += 1

                if not df.at[idx, "Facility Type"]:
                    oneway = road.get("oneway", "")
                    if oneway in OSM_ONEWAY_FACILITY:
                        df.at[idx, "Facility Type"] = OSM_ONEWAY_FACILITY[oneway]
                    else:
                        df.at[idx, "Facility Type"] = FC_TO_FACILITY_TYPE.get(fc, "")
                    filled["Facility Type"] += 1

                if not df.at[idx, "SYSTEM"]:
                    df.at[idx, "SYSTEM"] = FC_TO_SYSTEM.get(fc, "")
                    filled["SYSTEM"] += 1

                # Mainline? refinement (FC-based is more accurate than Tier 1)
                df.at[idx, "Mainline?"] = FC_TO_MAINLINE.get(fc, "No")

            # Roadway Description from OSM attributes
            if not df.at[idx, "Roadway Description"]:
                oneway = road.get("oneway", "")
                lanes = road.get("lanes", "")
                divided = ""  # OSM doesn't always have this
                desc = derive_roadway_description(oneway, lanes, divided)
                df.at[idx, "Roadway Description"] = desc
                filled["Roadway Description"] += 1

            # ── NEW: Roadway Surface Type from OSM surface tag ──
            if not df.at[idx, "Roadway Surface Type"]:
                surface = str(road.get("surface", "")).strip().split(';')[0].strip().lower()
                if surface and surface != 'nan':
                    mapped = OSM_SURFACE_MAP.get(surface, "")
                    if mapped:
                        df.at[idx, "Roadway Surface Type"] = mapped
                        filled["Roadway Surface Type"] += 1

            # ── NEW: Roadway Alignment from computed curvature ──
            if not df.at[idx, "Roadway Alignment"]:
                curvature = road.get("curvature", 1.0)
                if curvature and str(curvature) != 'nan':
                    try:
                        curv_val = float(curvature)
                        alignment = derive_roadway_alignment(curv_val)
                        df.at[idx, "Roadway Alignment"] = alignment
                        filled["Roadway Alignment"] += 1
                    except (ValueError, TypeError):
                        pass

            # ── NEW: Max Speed Diff from OSM maxspeed tag ──
            if not df.at[idx, "Max Speed Diff"]:
                speed_mph = parse_maxspeed_mph(road.get("maxspeed", ""))
                if speed_mph:
                    df.at[idx, "Max Speed Diff"] = str(speed_mph)
                    filled["Max Speed Diff"] += 1

            # ── NEW: Has_Street_Lighting from OSM lit tag ──
            col_lit = "Has_Street_Lighting"
            if col_lit not in df.columns:
                df[col_lit] = ""
            if not df.at[idx, col_lit]:
                lit = str(road.get("lit", "")).strip().lower()
                if lit in ("yes", "automatic"):
                    df.at[idx, col_lit] = "Yes"
                    filled[col_lit] += 1
                elif lit in ("no",):
                    df.at[idx, col_lit] = "No"

            # ── NEW: Has_Sidewalk from OSM sidewalk tag ──
            col_sw = "Has_Sidewalk"
            if col_sw not in df.columns:
                df[col_sw] = ""
            if not df.at[idx, col_sw]:
                sw = str(road.get("sidewalk", "")).strip().lower()
                if sw in ("yes", "both", "left", "right", "separate"):
                    df.at[idx, col_sw] = "Yes"
                    filled[col_sw] += 1
                elif sw in ("no", "none"):
                    df.at[idx, col_sw] = "No"

            # ── NEW: Has_Bike_Lane from OSM cycleway tag ──
            col_bk = "Has_Bike_Lane"
            if col_bk not in df.columns:
                df[col_bk] = ""
            if not df.at[idx, col_bk]:
                cw = str(road.get("cycleway", "")).strip().lower()
                if cw in ("lane", "track", "shared_lane", "shared_busway", "separate"):
                    df.at[idx, col_bk] = "Yes"
                    filled[col_bk] += 1
                elif cw in ("no", "none"):
                    df.at[idx, col_bk] = "No"

            # ── NEW: On_Bridge from OSM bridge tag ──
            col_br = "On_Bridge"
            if col_br not in df.columns:
                df[col_br] = ""
            if not df.at[idx, col_br]:
                bridge = str(road.get("bridge", "")).strip().lower()
                if bridge and bridge not in ("", "nan", "no"):
                    df.at[idx, col_br] = "Yes"
                    filled[col_br] += 1
                else:
                    df.at[idx, col_br] = "No"

        for col, count in sorted(filled.items()):
            print(f"    {col}: {count} rows enriched")

        # Match crashes to intersections
        int_matches = _match_crashes_to_intersections(
            crash_lats, crash_lons, self.state_abbr, self.cache_dir
        )
        if int_matches:
            int_filled = 0
            int_name_filled = 0
            for i, node_info in int_matches.items():
                idx = valid_indices[i]
                node_id = node_info["node_id"]
                dist_ft = node_info["distance_ft"]

                if not df.at[idx, "Node"]:
                    df.at[idx, "Node"] = str(node_id)
                if not df.at[idx, "Node Offset (ft)"]:
                    df.at[idx, "Node Offset (ft)"] = str(dist_ft)
                if not df.at[idx, "Intersection Type"]:
                    df.at[idx, "Intersection Type"] = node_info["intersection_type"]
                    int_filled += 1

                # Derive Intersection Name from road names at this node
                if not df.at[idx, "Intersection Name"]:
                    names = sorted(node_road_names.get(node_id, set()))
                    if len(names) >= 2:
                        int_name = f"{names[0]} & {names[1]}"
                    elif len(names) == 1:
                        int_name = names[0]
                    else:
                        int_name = ""
                    if int_name:
                        df.at[idx, "Intersection Name"] = int_name
                        int_name_filled += 1

            print(f"    Intersection Type: {int_filled} rows from OSM node analysis")
            if int_name_filled:
                print(f"    Intersection Name: {int_name_filled:,} rows (cross-street names from OSM)")

        self.stats["tier2_matched"] = len(matches)
        return df

    # ─── TIER 2b: POI PROXIMITY ANALYSIS ─────────────────────────────────

    def enrich_tier2b_pois(self, df):
        """
        Tier 2b: Match crashes to nearby Points of Interest (bars, schools,
        hospitals, traffic signals, crosswalks, etc.) from cached POI parquet.

        Fills:
          - Traffic Control Type (golden column — from signals/stop signs)
          - Near_Bar_1500ft, Near_School_1000ft, etc. (new proximity flags)
          - Nearest_Hospital_mi (distance to nearest hospital)
        """
        poi_path = Path(self.cache_dir) / f"{self.state_abbr.lower()}_pois.parquet"
        if not poi_path.exists():
            print("\n  [Tier 2b] POI proximity — skipped (no POI cache)")
            print(f"    Generate with: python generate_osm_pois.py --state {self.state_abbr}")
            return df

        try:
            from scipy.spatial import KDTree
        except ImportError:
            print("\n  [Tier 2b] POI proximity — skipped (scipy not installed)")
            return df

        print("\n  [Tier 2b] POI proximity analysis...")
        poi_df = pd.read_parquet(poi_path)
        print(f"    Loaded {len(poi_df):,} POIs across {poi_df['category'].nunique()} categories")

        # Get valid crash coordinates
        try:
            lons = pd.to_numeric(df["x"], errors="coerce")
            lats = pd.to_numeric(df["y"], errors="coerce")
        except Exception:
            print("    No valid GPS — Tier 2b skipped")
            return df

        valid = lats.notna() & lons.notna() & (lats != 0) & (lons != 0)
        if valid.sum() == 0:
            return df

        crash_lats = lats[valid].tolist()
        crash_lons = lons[valid].tolist()
        valid_indices = df.index[valid].tolist()

        mid_lat = sum(crash_lats) / len(crash_lats)
        lon_scale = math.cos(math.radians(mid_lat))

        crash_points = [
            (lat * 111000, lon * 111000 * lon_scale)
            for lat, lon in zip(crash_lats, crash_lons)
        ]

        filled_counts = {}

        # ── Proximity flags (bar, school, crossing, parking, rail_xing) ──
        for category, (threshold_m, col_name, yes_val) in POI_PROXIMITY.items():
            cat_pois = poi_df[poi_df["category"] == category]
            if len(cat_pois) == 0:
                continue

            # Ensure column exists
            if col_name not in df.columns:
                df[col_name] = ""

            poi_lats = cat_pois["lat"].tolist()
            poi_lons = cat_pois["lon"].tolist()
            poi_points = [
                (lat * 111000, lon * 111000 * lon_scale)
                for lat, lon in zip(poi_lats, poi_lons)
            ]
            tree = KDTree(poi_points)

            dists, _ = tree.query(crash_points, k=1)
            count = 0
            for i, dist in enumerate(dists):
                idx = valid_indices[i]
                if not df.at[idx, col_name]:  # smart-skip
                    if dist <= threshold_m:
                        df.at[idx, col_name] = yes_val
                        count += 1
                    else:
                        df.at[idx, col_name] = "No"

            if count > 0:
                filled_counts[col_name] = count
                print(f"    {col_name}: {count:,} crashes within {threshold_m}m of a {category}")

        # ── Traffic Control Type (fills golden column from signals + stop signs) ──
        tc_filled = 0
        for category, (threshold_m, tc_value) in POI_TRAFFIC_CONTROL.items():
            cat_pois = poi_df[poi_df["category"] == category]
            if len(cat_pois) == 0:
                continue

            poi_lats = cat_pois["lat"].tolist()
            poi_lons = cat_pois["lon"].tolist()
            poi_points = [
                (lat * 111000, lon * 111000 * lon_scale)
                for lat, lon in zip(poi_lats, poi_lons)
            ]
            tree = KDTree(poi_points)
            dists, _ = tree.query(crash_points, k=1)

            for i, dist in enumerate(dists):
                idx = valid_indices[i]
                if not df.at[idx, "Traffic Control Type"]:  # smart-skip
                    if dist <= threshold_m:
                        df.at[idx, "Traffic Control Type"] = tc_value
                        tc_filled += 1

        if tc_filled > 0:
            filled_counts["Traffic Control Type"] = tc_filled
            print(f"    Traffic Control Type: {tc_filled:,} rows filled from OSM signals/stop signs")

        # ── Nearest Hospital distance (miles) ──
        hospital_pois = poi_df[poi_df["category"].isin(["hospital", "clinic"])]
        if len(hospital_pois) > 0:
            if POI_HOSPITAL_DIST_COL not in df.columns:
                df[POI_HOSPITAL_DIST_COL] = ""

            h_lats = hospital_pois["lat"].tolist()
            h_lons = hospital_pois["lon"].tolist()
            h_points = [
                (lat * 111000, lon * 111000 * lon_scale)
                for lat, lon in zip(h_lats, h_lons)
            ]
            tree = KDTree(h_points)
            dists, _ = tree.query(crash_points, k=1)

            h_filled = 0
            for i, dist in enumerate(dists):
                idx = valid_indices[i]
                if not df.at[idx, POI_HOSPITAL_DIST_COL]:
                    miles = round(dist / 1609.34, 1)
                    df.at[idx, POI_HOSPITAL_DIST_COL] = str(miles)
                    h_filled += 1

            if h_filled > 0:
                avg_dist = sum(float(df.at[valid_indices[i], POI_HOSPITAL_DIST_COL])
                               for i in range(min(len(valid_indices), 1000))) / min(len(valid_indices), 1000)
                print(f"    {POI_HOSPITAL_DIST_COL}: {h_filled:,} rows (avg {avg_dist:.1f} mi)")

        self.stats["tier2b_poi_fills"] = filled_counts
        return df

    # ─── TIER 2c: FEDERAL SAFETY DATA ────────────────────────────────────

    def enrich_tier2c_federal(self, df):
        """
        Tier 2c: Upgrade proximity flags with authoritative federal data.

        NBI bridges    → Bridge_Condition (Good/Fair/Poor), Bridge_Year_Built
        FRA rail xings → Rail_Warning_Device (Gates/Signals/Signs/None)
                         Rail_Trains_Per_Day
        Urban schools  → School_Enrollment_Nearest (student count)
        NTM transit    → Near_Transit_500ft (Yes/No)

        These are enrichment upgrades to existing Tier 2b proximity flags.
        E.g., On_Bridge=Yes from OSM → Bridge_Condition=Poor from NBI.
        """
        abbr = self.state_abbr.lower()
        cache = Path(self.cache_dir)

        try:
            from scipy.spatial import KDTree
        except ImportError:
            print("\n  [Tier 2c] Federal safety — skipped (scipy not installed)")
            return df

        # Check which federal caches are available
        available = {}
        for source, suffix in FEDERAL_SOURCES.items():
            path = cache / f"{abbr}_{suffix}.parquet"
            if path.exists():
                try:
                    available[source] = pd.read_parquet(path)
                except Exception as e:
                    print(f"    Warning: {path.name} unreadable — {e}")

        if not available:
            print("\n  [Tier 2c] Federal safety — skipped (no federal caches)")
            print(f"    Generate with: python generate_federal_data.py --state {abbr}")
            return df

        print(f"\n  [Tier 2c] Federal safety data ({', '.join(sorted(available))})...")

        # Get valid crash coordinates
        try:
            lons = pd.to_numeric(df["x"], errors="coerce")
            lats = pd.to_numeric(df["y"], errors="coerce")
        except Exception:
            print("    No valid GPS — Tier 2c skipped")
            return df

        valid = lats.notna() & lons.notna() & (lats != 0) & (lons != 0)
        if valid.sum() == 0:
            return df

        crash_lats = lats[valid].tolist()
        crash_lons = lons[valid].tolist()
        valid_indices = df.index[valid].tolist()

        mid_lat = sum(crash_lats) / len(crash_lats)
        lon_scale = math.cos(math.radians(mid_lat))

        crash_points = [
            (lat * 111000, lon * 111000 * lon_scale)
            for lat, lon in zip(crash_lats, crash_lons)
        ]

        filled_counts = {}

        # ── Schools: enrollment of nearest school within 1000ft ──
        if "schools" in available:
            sdf = available["schools"]
            if "enrollment" in sdf.columns and len(sdf) > 0:
                col = FEDERAL_COL_SCHOOL_ENROLLMENT
                if col not in df.columns:
                    df[col] = ""

                s_points = [
                    (lat * 111000, lon * 111000 * lon_scale)
                    for lat, lon in zip(sdf["lat"].tolist(), sdf["lon"].tolist())
                ]
                tree = KDTree(s_points)
                dists, idxs = tree.query(crash_points, k=1)

                count = 0
                for i, (dist, idx) in enumerate(zip(dists, idxs)):
                    ci = valid_indices[i]
                    if not df.at[ci, col] and dist <= FEDERAL_SCHOOL_THRESHOLD_M:
                        enrollment = sdf.iloc[idx].get("enrollment", 0)
                        if pd.notna(enrollment) and int(enrollment) > 0:
                            df.at[ci, col] = str(int(enrollment))
                            count += 1

                if count > 0:
                    filled_counts[col] = count
                    print(f"    {col}: {count:,} crashes near a school with enrollment data")

        # ── Bridges: condition rating of nearest bridge within 150ft ──
        if "bridges" in available:
            bdf = available["bridges"]
            if "condition" in bdf.columns and len(bdf) > 0:
                # Bridge Condition
                col_cond = FEDERAL_COL_BRIDGE_CONDITION
                col_year = FEDERAL_COL_BRIDGE_YEAR
                if col_cond not in df.columns:
                    df[col_cond] = ""
                if col_year not in df.columns:
                    df[col_year] = ""

                b_points = [
                    (lat * 111000, lon * 111000 * lon_scale)
                    for lat, lon in zip(bdf["lat"].tolist(), bdf["lon"].tolist())
                ]
                tree = KDTree(b_points)
                dists, idxs = tree.query(crash_points, k=1)

                count_cond = 0
                count_year = 0
                for i, (dist, idx) in enumerate(zip(dists, idxs)):
                    ci = valid_indices[i]
                    if dist <= FEDERAL_BRIDGE_THRESHOLD_M:
                        bridge = bdf.iloc[idx]
                        # Condition
                        if not df.at[ci, col_cond]:
                            cond = str(bridge.get("condition", "")).strip()
                            if cond and cond != "nan":
                                df.at[ci, col_cond] = cond
                                count_cond += 1
                        # Year built
                        if not df.at[ci, col_year]:
                            yr = bridge.get("year_built", "")
                            if pd.notna(yr) and str(yr).strip() not in ("", "0", "nan"):
                                df.at[ci, col_year] = str(int(yr))
                                count_year += 1

                if count_cond > 0:
                    filled_counts[col_cond] = count_cond
                    print(f"    {col_cond}: {count_cond:,} crashes on bridges with condition data")
                if count_year > 0:
                    filled_counts[col_year] = count_year
                    print(f"    {col_year}: {count_year:,} crashes on bridges with year built")

        # ── Rail crossings: warning device of nearest crossing within 150ft ──
        if "rail_crossings" in available:
            rdf = available["rail_crossings"]
            if len(rdf) > 0:
                col_warn = FEDERAL_COL_RAIL_WARNING
                col_tpd = FEDERAL_COL_RAIL_TRAINS
                if col_warn not in df.columns:
                    df[col_warn] = ""
                if col_tpd not in df.columns:
                    df[col_tpd] = ""

                r_points = [
                    (lat * 111000, lon * 111000 * lon_scale)
                    for lat, lon in zip(rdf["lat"].tolist(), rdf["lon"].tolist())
                ]
                tree = KDTree(r_points)
                dists, idxs = tree.query(crash_points, k=1)

                count_warn = 0
                count_tpd = 0
                for i, (dist, idx) in enumerate(zip(dists, idxs)):
                    ci = valid_indices[i]
                    if dist <= FEDERAL_RAIL_THRESHOLD_M:
                        xing = rdf.iloc[idx]
                        # Warning device (use warning_level if available, else warning_device)
                        if not df.at[ci, col_warn]:
                            # Prefer warning_level (simplified: Gates/Signals/Signs/None)
                            wd = str(xing.get("warning_level", "")).strip()
                            if not wd or wd in ("", "Other", "nan"):
                                wd = str(xing.get("warning_device", "")).strip()
                            if wd and wd not in ("", "nan", "Unknown"):
                                df.at[ci, col_warn] = wd
                                count_warn += 1
                        # Trains per day
                        if not df.at[ci, col_tpd]:
                            tpd = xing.get("trains_per_day", "")
                            if pd.notna(tpd):
                                tpd_str = str(tpd).strip()
                                # Validate: must be reasonable integer (< 1000)
                                try:
                                    tpd_int = int(float(tpd_str))
                                    if 0 < tpd_int < 1000:
                                        df.at[ci, col_tpd] = str(tpd_int)
                                        count_tpd += 1
                                except (ValueError, OverflowError):
                                    pass

                if count_warn > 0:
                    filled_counts[col_warn] = count_warn
                    print(f"    {col_warn}: {count_warn:,} crashes at rail crossings with device data")
                if count_tpd > 0:
                    filled_counts[col_tpd] = count_tpd
                    print(f"    {col_tpd}: {count_tpd:,} crashes at rail crossings with train frequency")

        # ── Transit stops: proximity flag within 500ft ──
        if "transit" in available:
            tdf = available["transit"]
            if len(tdf) > 0:
                col = FEDERAL_COL_TRANSIT
                if col not in df.columns:
                    df[col] = ""

                t_points = [
                    (lat * 111000, lon * 111000 * lon_scale)
                    for lat, lon in zip(tdf["lat"].tolist(), tdf["lon"].tolist())
                ]
                tree = KDTree(t_points)
                dists, _ = tree.query(crash_points, k=1)

                count = 0
                for i, dist in enumerate(dists):
                    ci = valid_indices[i]
                    if not df.at[ci, col]:
                        if dist <= FEDERAL_TRANSIT_THRESHOLD_M:
                            df.at[ci, col] = "Yes"
                            count += 1
                        else:
                            df.at[ci, col] = "No"

                if count > 0:
                    filled_counts[col] = count
                    print(f"    {col}: {count:,} crashes within 500ft of a transit stop")

        self.stats["tier2c_federal_fills"] = filled_counts
        return df

    # ─── INTERSECTION ANALYSIS DERIVATION ─────────────────────────────

    def _derive_intersection_analysis(self, df):
        """
        Derive Intersection Analysis from Intersection Type + Ownership.
        Frontend expects: 'Not Intersection', 'Urban Intersection', 'DOT Intersection'.
        
        Logic:
          - Intersection Type = '1. Not at Intersection' → 'Not Intersection'
          - Ownership = '1. State Hwy Agency' (DOT road) → 'DOT Intersection'
          - Everything else at intersection → 'Urban Intersection'
        """
        if "Intersection Analysis" not in df.columns:
            df["Intersection Analysis"] = ""

        ia_filled = 0
        for idx in df.index:
            if df.at[idx, "Intersection Analysis"]:
                continue  # already set by state data

            int_type = str(df.at[idx, "Intersection Type"]).strip() if "Intersection Type" in df.columns else ""
            ownership = str(df.at[idx, "Ownership"]).strip() if "Ownership" in df.columns else ""

            if int_type == "1. Not at Intersection" or not int_type or int_type in ("nan", "None"):
                df.at[idx, "Intersection Analysis"] = "Not Intersection"
            elif ownership == "1. State Hwy Agency":
                df.at[idx, "Intersection Analysis"] = "DOT Intersection"
            else:
                df.at[idx, "Intersection Analysis"] = "Urban Intersection"
            ia_filled += 1

        if ia_filled > 0:
            dot_ct = (df["Intersection Analysis"] == "DOT Intersection").sum()
            urb_ct = (df["Intersection Analysis"] == "Urban Intersection").sum()
            not_ct = (df["Intersection Analysis"] == "Not Intersection").sum()
            print(f"\n  [Intersection Analysis] {ia_filled:,} rows derived:")
            print(f"    DOT Intersection: {dot_ct:,}, Urban Intersection: {urb_ct:,}, Not Intersection: {not_ct:,}")

        return df

    # ─── REPORTING ───────────────────────────────────────────────────────

    def _print_fill_report(self, df):
        """Print before/after column fill rates."""
        key_columns = [
            # Golden columns (Tier 2 road matching)
            "RTE Name", "Functional Class", "Facility Type", "Ownership",
            "SYSTEM", "Mainline?", "Roadway Description", "Intersection Type",
            "Intersection Name", "Node", "Node Offset (ft)",
            # Golden columns (new fills from road attributes)
            "Roadway Surface Type", "Roadway Alignment", "Max Speed Diff",
            "Traffic Control Type", "Intersection Analysis",
            # HPMS-only columns
            "AADT", "Through_Lanes", "Access_Control",
            "Lane_Width_ft", "Median_Width_ft", "Shoulder_Width_ft",
            "AADT_Trucks", "Design_Speed_mph",
            # Tier 1 flags
            "Distracted?", "Drowsy?", "Speed?", "Animal Related?", "Hitrun?",
            "K_People", "A_People", "Area Type",
            # New: road infrastructure columns
            "Has_Street_Lighting", "Has_Sidewalk", "Has_Bike_Lane", "On_Bridge",
            # New: POI proximity columns (ft-based)
            "Near_Bar_1500ft", "Near_School_1000ft", "Near_Crossing_100ft",
            "Near_Parking_150ft", "Near_Rail_Xing_150ft", "Nearest_Hospital_mi",
            # New: Federal safety data (Tier 2c)
            "School_Enrollment_Nearest", "Bridge_Condition", "Bridge_Year_Built",
            "Rail_Warning_Device", "Rail_Trains_Per_Day", "Near_Transit_500ft",
        ]
        total = len(df)
        print(f"\n  {'─'*55}")
        print(f"  Column Fill Report ({total:,} rows)")
        print(f"  {'─'*55}")
        print(f"  {'Column':<28} {'Filled':>8} {'%':>8}")
        print(f"  {'─'*44}")

        for col in key_columns:
            if col in df.columns:
                filled = (df[col].fillna("").str.strip() != "").sum()
                pct = filled / max(total, 1) * 100
                marker = "***" if pct > 0 and pct < 100 else ("   " if pct == 100 else "---")
                print(f"  {col:<28} {filled:>8,} {pct:>7.1f}% {marker}")

        print(f"  {'─'*55}")


# ─────────────────────────────────────────────────────────────────────────────
#  CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CrashLens Universal Crash Data Enricher")
    parser.add_argument("--input", "-i", required=True, help="Normalized CSV path")
    parser.add_argument("--output", "-o", default=None, help="Output CSV path")
    parser.add_argument("--state-fips", required=True, help="State FIPS code")
    parser.add_argument("--state-abbr", required=True, help="State abbreviation")
    parser.add_argument("--state-name", default=None, help="State full name")
    parser.add_argument("--cache-dir", default="cache", help="Cache directory for OSM data")
    parser.add_argument("--skip-osm", action="store_true", help="Skip Tier 2 OSM enrichment")
    parser.add_argument("--circumstance-col", default="PRIMARY CONTRIBUTING CIRCUMSTANCE DESCRIPTION",
                        help="Contributing circumstance column name")
    args = parser.parse_args()

    df = pd.read_csv(args.input, dtype=str, low_memory=False)
    enricher = CrashEnricher(
        state_fips=args.state_fips,
        state_abbr=args.state_abbr,
        state_name=args.state_name,
        cache_dir=args.cache_dir,
        circumstance_col=args.circumstance_col,
    )
    df = enricher.enrich_all(df, skip_tier2=args.skip_osm)

    out = args.output or args.input.replace(".csv", "_enriched.csv")
    df.to_csv(out, index=False)
    print(f"\n  Output: {out}")
