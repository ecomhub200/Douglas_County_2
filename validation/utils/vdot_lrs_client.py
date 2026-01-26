#!/usr/bin/env python3
"""
VDOT Linear Referencing System (LRS) Client.

Provides geocoding using VDOT's official LRS API to convert
Route Name + Milepost to GPS coordinates.

VDOT LRS API Endpoints:
- Feature Server: https://vdotgisuportal.vdot.virginia.gov/env/rest/services/VDOT_Map/Virginia_Tech_LRS_Routes/FeatureServer
- Map Server: https://vdotgisuportal.vdot.virginia.gov/env/rest/services/VDOT_Map/Virginia_Tech_LRS_Routes/MapServer

No API key required - public service.

Author: CRASH LENS Team
Version: 1.0.0
"""

import json
import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / ".validation" / "vdot_cache"


class VDOTLRSClient:
    """
    Client for VDOT Linear Referencing System API.

    Converts Route Name + Milepost to GPS coordinates using VDOT's
    official ArcGIS Feature Server.
    """

    # VDOT LRS API endpoints
    FEATURE_SERVER = "https://vdotgisuportal.vdot.virginia.gov/env/rest/services/VDOT_Map/Virginia_Tech_LRS_Routes/FeatureServer"
    MAP_SERVER = "https://vdotgisuportal.vdot.virginia.gov/env/rest/services/VDOT_Map/Virginia_Tech_LRS_Routes/MapServer"

    # Layer IDs in Feature Server
    LAYERS = {
        'route_master': 0,      # VDOT_ROUTE_MASTER_LRS_DAILY
        'route_overlap': 1,     # VDOT_ROUTE_OVERLAP_LRS_DAILY
        'responsibility': 2,    # VDOT_RESPONSIBILITY_MASTER_ROUTE
        'nhs': 3,              # NHS_MASTER_ROUTE
        'functional_class': 4   # FUNCTIONAL_CLASS_MASTER_ROUTE
    }

    def __init__(self, cache_ttl_hours: int = 168):
        """
        Initialize VDOT LRS client.

        Args:
            cache_ttl_hours: Cache time-to-live in hours (default: 7 days)
        """
        self.cache_dir = CACHE_DIR
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.request_delay = 0.2  # Minimum seconds between requests
        self.last_request_time = 0
        self.timeout = 30

        # Route lookup cache (route_id -> geometry)
        self.route_cache: Dict[str, dict] = {}
        self.milepost_cache: Dict[str, Tuple[float, float]] = {}

        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load caches
        self._load_caches()

    def _load_caches(self):
        """Load cached data from disk."""
        milepost_cache_file = self.cache_dir / "milepost_coords.json"
        if milepost_cache_file.exists():
            try:
                with open(milepost_cache_file, 'r') as f:
                    data = json.load(f)
                    self.milepost_cache = {k: tuple(v) for k, v in data.items()}
                logger.info(f"Loaded {len(self.milepost_cache)} cached milepost coordinates")
            except Exception as e:
                logger.warning(f"Failed to load milepost cache: {e}")

    def _save_caches(self):
        """Save caches to disk."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        milepost_cache_file = self.cache_dir / "milepost_coords.json"
        try:
            with open(milepost_cache_file, 'w') as f:
                json.dump(self.milepost_cache, f)
        except Exception as e:
            logger.warning(f"Failed to save milepost cache: {e}")

    def _respect_rate_limit(self):
        """Ensure minimum delay between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)

    def _parse_route_name(self, route_name: str) -> Optional[Dict]:
        """
        Parse Virginia route name into components.

        Virginia route names follow patterns like:
        - "R-VA   US00250WB" -> Route US 250 Westbound
        - "S-VA043NP NUCKOLS RD" -> Secondary VA 043
        - "I-64" -> Interstate 64

        Args:
            route_name: Raw route name from crash data

        Returns:
            Dict with route_type, route_number, direction, or None
        """
        if not route_name:
            return None

        route_name = str(route_name).strip().upper()

        # Pattern: R-VA   US00250WB
        match = re.match(r'^R-VA\s+([A-Z]+)(\d+)([NSEW]B)?', route_name)
        if match:
            return {
                'route_type': match.group(1),  # US, VA, etc.
                'route_number': match.group(2).lstrip('0'),
                'direction': match.group(3) or '',
                'full_route': f"{match.group(1)} {match.group(2).lstrip('0')}"
            }

        # Pattern: S-VA043NP
        match = re.match(r'^S-VA(\d+)', route_name)
        if match:
            return {
                'route_type': 'SR',  # Secondary Route
                'route_number': match.group(1).lstrip('0'),
                'direction': '',
                'full_route': f"SR {match.group(1).lstrip('0')}"
            }

        # Pattern: I-64, I-95
        match = re.match(r'^I-?(\d+)', route_name)
        if match:
            return {
                'route_type': 'I',
                'route_number': match.group(1),
                'direction': '',
                'full_route': f"I-{match.group(1)}"
            }

        # Pattern: US 250, VA 10
        match = re.match(r'^(US|VA|SR)\s*(\d+)', route_name)
        if match:
            return {
                'route_type': match.group(1),
                'route_number': match.group(2),
                'direction': '',
                'full_route': f"{match.group(1)} {match.group(2)}"
            }

        return None

    def query_route(self, route_name: str, milepost: float) -> Optional[dict]:
        """
        Query VDOT LRS for route geometry at milepost.

        Args:
            route_name: Route name from crash data
            milepost: Milepost value (RNS MP)

        Returns:
            Route data with geometry, or None if not found
        """
        parsed = self._parse_route_name(route_name)
        if not parsed:
            logger.debug(f"Could not parse route name: {route_name}")
            return None

        self._respect_rate_limit()

        # Build query for route master layer
        layer_url = f"{self.FEATURE_SERVER}/{self.LAYERS['route_master']}/query"

        # Query routes containing the milepost
        where_clause = (
            f"RTE_NM LIKE '%{parsed['route_type']}%{parsed['route_number']}%' "
            f"AND RTE_FROM_MSR <= {milepost} AND RTE_TO_MSR >= {milepost}"
        )

        params = {
            'where': where_clause,
            'outFields': '*',
            'returnGeometry': 'true',
            'geometryPrecision': 6,
            'outSR': '4326',  # WGS84
            'f': 'json'
        }

        try:
            response = requests.get(layer_url, params=params, timeout=self.timeout)
            self.last_request_time = time.time()
            response.raise_for_status()

            data = response.json()

            if 'error' in data:
                logger.warning(f"VDOT API error: {data['error']}")
                return None

            features = data.get('features', [])
            if features:
                return features[0]  # Return first matching route

        except requests.exceptions.Timeout:
            logger.warning("VDOT LRS API timeout")
        except requests.exceptions.RequestException as e:
            logger.warning(f"VDOT LRS API error: {e}")
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON from VDOT API: {e}")

        return None

    def interpolate_milepost(self, route_geometry: dict,
                             from_mp: float, to_mp: float,
                             target_mp: float) -> Optional[Tuple[float, float]]:
        """
        Interpolate coordinates for a milepost along route geometry.

        Args:
            route_geometry: Route geometry from VDOT API
            from_mp: Start milepost of route segment
            to_mp: End milepost of route segment
            target_mp: Target milepost to find

        Returns:
            (longitude, latitude) tuple or None
        """
        if not route_geometry or 'paths' not in route_geometry:
            return None

        paths = route_geometry['paths']
        if not paths or not paths[0]:
            return None

        # Get all points along route
        points = paths[0]  # First path

        if len(points) < 2:
            return None

        # Calculate proportion along route
        total_mp_range = to_mp - from_mp
        if total_mp_range <= 0:
            # Single point route
            return (points[0][0], points[0][1])

        mp_fraction = (target_mp - from_mp) / total_mp_range
        mp_fraction = max(0, min(1, mp_fraction))  # Clamp to [0, 1]

        # Find position along polyline
        total_segments = len(points) - 1
        segment_idx = int(mp_fraction * total_segments)
        segment_idx = min(segment_idx, total_segments - 1)

        # Interpolate within segment
        segment_fraction = (mp_fraction * total_segments) - segment_idx

        p1 = points[segment_idx]
        p2 = points[segment_idx + 1]

        lon = p1[0] + (p2[0] - p1[0]) * segment_fraction
        lat = p1[1] + (p2[1] - p1[1]) * segment_fraction

        return (lon, lat)

    def geocode_milepost(self, route_name: str, milepost: float) -> Optional[Tuple[float, float]]:
        """
        Geocode a route + milepost to GPS coordinates.

        Args:
            route_name: Route name from crash data (e.g., "R-VA   US00250WB")
            milepost: Milepost value from RNS MP field

        Returns:
            (longitude, latitude) tuple or None
        """
        if not route_name or milepost is None:
            return None

        # Check cache first
        cache_key = f"{route_name}|{milepost}"
        if cache_key in self.milepost_cache:
            return self.milepost_cache[cache_key]

        # Query VDOT LRS
        route_data = self.query_route(route_name, milepost)
        if not route_data:
            return None

        # Get route attributes
        attrs = route_data.get('attributes', {})
        from_mp = attrs.get('RTE_FROM_MSR', 0)
        to_mp = attrs.get('RTE_TO_MSR', milepost + 1)

        # Get geometry
        geometry = route_data.get('geometry')
        if not geometry:
            return None

        # Interpolate coordinates
        coords = self.interpolate_milepost(geometry, from_mp, to_mp, milepost)

        if coords:
            # Cache result
            self.milepost_cache[cache_key] = coords
            self._save_caches()

        return coords

    def get_stats(self) -> Dict:
        """Get client statistics."""
        return {
            'milepost_cache_size': len(self.milepost_cache),
            'route_cache_size': len(self.route_cache)
        }


class VDOTMilepostLookup:
    """
    Build and use a local milepost lookup table from crash data.

    Similar to NodeLookupTable, builds a lookup from existing crash records
    where route, milepost, and coordinates are all present.
    """

    def __init__(self):
        self.milepost_coords: Dict[str, Tuple[float, float]] = {}
        self.cache_file = CACHE_DIR / "milepost_lookup.json"
        self._load_cache()

    def _load_cache(self):
        """Load cached milepost coordinates."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    self.milepost_coords = {k: tuple(v) for k, v in data.items()}
                logger.info(f"Loaded {len(self.milepost_coords)} milepost coordinates from cache")
            except Exception as e:
                logger.warning(f"Failed to load milepost cache: {e}")

    def _save_cache(self):
        """Save milepost coordinates to cache."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(self.milepost_coords, f)
        logger.info(f"Saved {len(self.milepost_coords)} milepost coordinates to cache")

    def _make_key(self, route_name: str, milepost: float) -> str:
        """Create lookup key from route and milepost."""
        # Round milepost to 2 decimal places for fuzzy matching
        mp_rounded = round(milepost, 2)
        return f"{route_name}|{mp_rounded}"

    def build_from_dataframe(self, df):
        """
        Build lookup table from dataframe with route, milepost, and coordinates.

        Args:
            df: DataFrame with 'RTE Name', 'RNS MP', 'x', 'y' columns
        """
        import pandas as pd

        # Required columns
        required = ['RTE Name', 'RNS MP', 'x', 'y']
        if not all(col in df.columns for col in required):
            logger.warning(f"Missing required columns for milepost lookup: {required}")
            return

        # Filter to records with all values
        valid = df[
            df['RTE Name'].notna() &
            df['RNS MP'].notna() &
            df['x'].notna() &
            df['y'].notna()
        ].copy()

        if len(valid) == 0:
            logger.warning("No valid route + milepost + coordinate records found")
            return

        # Build lookup (using mean for duplicate keys)
        new_count = 0
        for _, row in valid.iterrows():
            try:
                route = str(row['RTE Name']).strip()
                mp = float(row['RNS MP'])
                key = self._make_key(route, mp)

                if key not in self.milepost_coords:
                    new_count += 1

                self.milepost_coords[key] = (float(row['x']), float(row['y']))
            except (ValueError, TypeError):
                continue

        logger.info(f"Built milepost lookup: {len(self.milepost_coords)} total, {new_count} new")
        self._save_cache()

    def lookup(self, route_name: str, milepost: float,
               tolerance: float = 0.1) -> Optional[Tuple[float, float]]:
        """
        Lookup coordinates for route + milepost.

        Args:
            route_name: Route name
            milepost: Milepost value
            tolerance: Milepost tolerance for fuzzy matching

        Returns:
            (longitude, latitude) or None
        """
        if not route_name or milepost is None:
            return None

        try:
            mp = float(milepost)
        except (ValueError, TypeError):
            return None

        # Try exact match first
        key = self._make_key(route_name, mp)
        if key in self.milepost_coords:
            return self.milepost_coords[key]

        # Try fuzzy match within tolerance
        for offset in [0.01, 0.02, 0.05, tolerance]:
            for delta in [offset, -offset]:
                fuzzy_key = self._make_key(route_name, mp + delta)
                if fuzzy_key in self.milepost_coords:
                    return self.milepost_coords[fuzzy_key]

        return None

    def __len__(self):
        return len(self.milepost_coords)


def geocode_with_vdot_lrs(route_name: str, milepost: float) -> Optional[Tuple[float, float]]:
    """
    Convenience function to geocode using VDOT LRS API.

    Args:
        route_name: Route name from crash data
        milepost: Milepost value

    Returns:
        (longitude, latitude) or None
    """
    client = VDOTLRSClient()
    return client.geocode_milepost(route_name, milepost)


if __name__ == "__main__":
    # Test VDOT LRS client
    logging.basicConfig(level=logging.INFO)

    print("\n=== Testing VDOT LRS Client ===\n")

    client = VDOTLRSClient()

    # Test route name parsing
    test_routes = [
        "R-VA   US00250WB",
        "S-VA043NP NUCKOLS RD",
        "I-64",
        "VA 10"
    ]

    print("Route name parsing:")
    for route in test_routes:
        parsed = client._parse_route_name(route)
        print(f"  {route} -> {parsed}")

    # Test geocoding
    print("\n\nMilepost geocoding:")
    test_cases = [
        ("R-VA   US00250WB", 156.03),  # From sample data
        ("I-64", 180.0)
    ]

    for route, mp in test_cases:
        coords = client.geocode_milepost(route, mp)
        print(f"  {route} @ MP {mp} -> {coords}")

    print(f"\nStats: {client.get_stats()}")
