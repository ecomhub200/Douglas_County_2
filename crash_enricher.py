#!/usr/bin/env python3
"""
crash_enricher.py — CrashLens Universal Crash Data Enrichment Module
====================================================================
Shared module that enriches ANY normalized crash dataset by deriving
missing columns from GPS coordinates, contributing circumstances,
temporal data, and OpenStreetMap road network data.

Three-tier enrichment strategy:
  Tier 1: Self-Enrichment     — derive from existing crash fields (zero external deps)
  Tier 2: OSM Road Matching   — GPS → nearest road → road attributes → CrashLens columns
  Tier 3: Federal Data Overlay — HPMS, Census urban boundaries, NBI (future)

Usage:
    from crash_enricher import CrashEnricher
    enricher = CrashEnricher(state_fips="10", state_abbr="DE")
    df = enricher.enrich_all(df)  # enriches in-place, returns df

    # Or tier-by-tier:
    df = enricher.enrich_tier1(df)   # self-enrichment (always runs)
    df = enricher.enrich_tier2(df)   # OSM road matching (needs cached network)
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
    "1-Interstate (A,1)":  "State Primary",
    "2-Principal Arterial - Other Freeways and Expressways (B)": "State Primary",
    "3-Principal Arterial - Other (E,2)": "State Primary",
    "4-Minor Arterial (H,3)": "State Secondary",
    "5-Major Collector (I,4)": "State Secondary",
    "6-Minor Collector (5)":   "County",
    "7-Local (J,6)":          "Local",
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
        """Run all enrichment tiers. Returns enriched DataFrame."""
        t0 = time.time()
        print(f"\n  {'='*55}")
        print(f"  CrashLens Universal Enricher | {self.state_name} ({self.state_abbr})")
        print(f"  {'='*55}")

        df = self.enrich_tier1(df)

        if not skip_tier2:
            df = self.enrich_tier2(df)

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

    # ─── TIER 2: OSM Road Network Matching ───────────────────────────────

    def enrich_tier2(self, df):
        """
        Tier 2: Match crashes to OSM road network, derive road attributes.
        Requires osmnx (first run downloads and caches road network).
        """
        print("\n  [Tier 2] OSM road network matching...")

        # Load or download road network
        road_df = _load_or_download_road_network(
            self.state_name, self.state_abbr, self.cache_dir
        )
        if road_df is None:
            print("    Tier 2 skipped — no road network available")
            return df

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

        for col, count in sorted(filled.items()):
            print(f"    {col}: {count} rows enriched")

        # Match crashes to intersections
        int_matches = _match_crashes_to_intersections(
            crash_lats, crash_lons, self.state_abbr, self.cache_dir
        )
        if int_matches:
            int_filled = 0
            for i, node_info in int_matches.items():
                idx = valid_indices[i]
                if not df.at[idx, "Node"]:
                    df.at[idx, "Node"] = str(node_info["node_id"])
                if not df.at[idx, "Node Offset (ft)"]:
                    df.at[idx, "Node Offset (ft)"] = str(node_info["distance_ft"])
                if not df.at[idx, "Intersection Type"]:
                    df.at[idx, "Intersection Type"] = node_info["intersection_type"]
                    int_filled += 1
            print(f"    Intersection Type: {int_filled} rows from OSM node analysis")

        self.stats["tier2_matched"] = len(matches)
        return df

    # ─── REPORTING ───────────────────────────────────────────────────────

    def _print_fill_report(self, df):
        """Print before/after column fill rates."""
        key_columns = [
            "RTE Name", "Functional Class", "Facility Type", "Ownership",
            "SYSTEM", "Mainline?", "Roadway Description", "Intersection Type",
            "Node", "Node Offset (ft)", "Distracted?", "Drowsy?", "Speed?",
            "Animal Related?", "Hitrun?", "K_People", "A_People", "Area Type",
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
