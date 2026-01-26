#!/usr/bin/env python3
"""
Overpass API Client for Spatial Validation

This module provides road network validation using OpenStreetMap data
via the Overpass API. It supports endpoint rotation, caching, and
batch coordinate validation.

Author: CRASH LENS Team
Version: 1.0.0
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class OverpassClient:
    """Client for querying Overpass API for road network data."""

    ENDPOINTS = [
        'https://overpass-api.de/api/interpreter',
        'https://overpass.kumi.systems/api/interpreter',
        'https://overpass.openstreetmap.fr/api/interpreter',
        'https://z.overpass-api.de/api/interpreter'
    ]

    def __init__(self, cache_dir: Optional[Path] = None, cache_ttl_hours: int = 168):
        """
        Initialize Overpass client.

        Args:
            cache_dir: Directory for caching responses
            cache_ttl_hours: Cache time-to-live in hours (default: 7 days)
        """
        self.current_endpoint_idx = 0
        self.cache_dir = cache_dir or Path(__file__).parent.parent.parent / 'data' / '.validation' / 'overpass_cache'
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.request_delay = 1.0  # Minimum seconds between requests
        self.last_request_time = 0
        self.timeout = 60  # Request timeout in seconds

        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, query_hash: str) -> Path:
        """Get cache file path for a query."""
        return self.cache_dir / f"{query_hash}.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file exists and is not expired."""
        if not cache_path.exists():
            return False
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < self.cache_ttl

    def _hash_query(self, query: str) -> str:
        """Create a hash of the query for caching."""
        import hashlib
        return hashlib.md5(query.encode()).hexdigest()

    def _respect_rate_limit(self):
        """Ensure minimum delay between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)

    def _rotate_endpoint(self):
        """Rotate to next endpoint."""
        self.current_endpoint_idx = (self.current_endpoint_idx + 1) % len(self.ENDPOINTS)

    def query(self, query: str, use_cache: bool = True) -> Optional[dict]:
        """
        Execute Overpass query with endpoint rotation and caching.

        Args:
            query: Overpass QL query string
            use_cache: Whether to use cached results

        Returns:
            Query result as dict, or None if all endpoints fail
        """
        query_hash = self._hash_query(query)
        cache_path = self._get_cache_path(query_hash)

        # Check cache first
        if use_cache and self._is_cache_valid(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    logger.debug(f"Cache hit for query hash {query_hash}")
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass  # Cache corrupted, fetch fresh

        # Try each endpoint
        last_error = None
        for attempt in range(len(self.ENDPOINTS)):
            endpoint = self.ENDPOINTS[self.current_endpoint_idx]

            try:
                self._respect_rate_limit()
                logger.debug(f"Querying {endpoint}")

                response = requests.post(
                    endpoint,
                    data={'data': query},
                    timeout=self.timeout,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                self.last_request_time = time.time()

                if response.status_code == 200:
                    data = response.json()

                    # Check for Overpass error in response
                    if 'remark' in data and 'error' in data.get('remark', '').lower():
                        logger.warning(f"Overpass error: {data['remark']}")
                        last_error = Exception(data['remark'])
                        self._rotate_endpoint()
                        continue

                    # Cache successful response
                    if use_cache:
                        try:
                            with open(cache_path, 'w') as f:
                                json.dump(data, f)
                        except IOError as e:
                            logger.warning(f"Failed to cache response: {e}")

                    return data

                elif response.status_code == 429:
                    logger.warning(f"Rate limited by {endpoint}")
                    self._rotate_endpoint()
                    time.sleep(5)  # Extra delay on rate limit
                    continue

                elif response.status_code >= 500:
                    logger.warning(f"Server error from {endpoint}: {response.status_code}")
                    self._rotate_endpoint()
                    continue

                else:
                    logger.error(f"Unexpected status {response.status_code} from {endpoint}")
                    last_error = Exception(f"HTTP {response.status_code}")
                    self._rotate_endpoint()

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout from {endpoint}")
                self._rotate_endpoint()
                last_error = Exception("Request timeout")

            except requests.exceptions.RequestException as e:
                logger.warning(f"Request error from {endpoint}: {e}")
                self._rotate_endpoint()
                last_error = e

        logger.error(f"All Overpass endpoints failed. Last error: {last_error}")
        return None

    def get_roads_near_point(self, lat: float, lon: float, radius: int = 100) -> Optional[List[dict]]:
        """
        Get roads near a coordinate.

        Args:
            lat: Latitude
            lon: Longitude
            radius: Search radius in meters

        Returns:
            List of road features, or None if query fails
        """
        query = f"""
[out:json][timeout:30];
(
  way(around:{radius},{lat},{lon})["highway"];
);
out tags center;
"""
        result = self.query(query)
        if result and 'elements' in result:
            return result['elements']
        return None

    def is_coordinate_near_road(self, lat: float, lon: float, max_distance: int = 100) -> Tuple[bool, Optional[dict]]:
        """
        Check if coordinate is near any road.

        Args:
            lat: Latitude
            lon: Longitude
            max_distance: Maximum distance in meters

        Returns:
            Tuple of (is_near_road, nearest_road_info)
        """
        roads = self.get_roads_near_point(lat, lon, max_distance)
        if roads is None:
            return False, {'error': 'Query failed'}

        if len(roads) == 0:
            return False, {'message': f'No roads within {max_distance}m'}

        # Find road with matching tags
        for road in roads:
            tags = road.get('tags', {})
            return True, {
                'highway_type': tags.get('highway'),
                'name': tags.get('name', tags.get('ref', 'Unnamed')),
                'road_count': len(roads)
            }

        return True, {'road_count': len(roads)}

    def validate_route_name(self, lat: float, lon: float, expected_route: str,
                            radius: int = 50) -> Tuple[bool, Optional[str]]:
        """
        Validate that coordinate is on expected route.

        Args:
            lat: Latitude
            lon: Longitude
            expected_route: Expected road name
            radius: Search radius in meters

        Returns:
            Tuple of (matches, actual_road_name)
        """
        if not expected_route:
            return True, None

        roads = self.get_roads_near_point(lat, lon, radius)
        if roads is None:
            return False, None

        # Normalize expected route for comparison
        expected_normalized = expected_route.lower().strip()

        for road in roads:
            tags = road.get('tags', {})
            road_name = tags.get('name', '')
            road_ref = tags.get('ref', '')

            # Check if any variation matches
            if (road_name.lower().strip() == expected_normalized or
                road_ref.lower().strip() == expected_normalized or
                expected_normalized in road_name.lower() or
                expected_normalized in road_ref.lower()):
                return True, road_name or road_ref

        # Return first road found as actual
        if roads:
            first_road = roads[0].get('tags', {})
            actual = first_road.get('name', first_road.get('ref', 'Unknown'))
            return False, actual

        return False, None

    def is_intersection(self, lat: float, lon: float, radius: int = 30) -> Tuple[bool, int]:
        """
        Check if coordinate is at an intersection.

        Args:
            lat: Latitude
            lon: Longitude
            radius: Search radius in meters

        Returns:
            Tuple of (is_intersection, road_count)
        """
        query = f"""
[out:json][timeout:30];
(
  way(around:{radius},{lat},{lon})["highway"];
);
out body;
>;
out skel qt;
"""
        result = self.query(query)
        if result is None:
            return False, 0

        # Count unique ways
        ways = [e for e in result.get('elements', []) if e.get('type') == 'way']
        return len(ways) >= 2, len(ways)

    def batch_validate_coordinates(self, coordinates: List[Tuple[float, float, int]],
                                   max_distance: int = 100) -> Dict[int, dict]:
        """
        Validate multiple coordinates in batch.

        Args:
            coordinates: List of (lat, lon, row_idx) tuples
            max_distance: Maximum distance from road in meters

        Returns:
            Dict mapping row_idx to validation result
        """
        results = {}

        for lat, lon, row_idx in coordinates:
            is_near, info = self.is_coordinate_near_road(lat, lon, max_distance)
            results[row_idx] = {
                'is_valid': is_near,
                'info': info
            }

            # Add small delay to avoid rate limiting
            time.sleep(0.1)

        return results

    def get_jurisdiction_road_network(self, bbox: Tuple[float, float, float, float]) -> Optional[dict]:
        """
        Get all roads within a jurisdiction bounding box.

        Args:
            bbox: (min_lon, min_lat, max_lon, max_lat)

        Returns:
            Road network data, or None if query fails

        Note:
            This is a heavy query - use caching and limit calls
        """
        min_lon, min_lat, max_lon, max_lat = bbox
        query = f"""
[out:json][timeout:180];
(
  way["highway"]({min_lat},{min_lon},{max_lat},{max_lon});
);
out tags center;
"""
        return self.query(query, use_cache=True)

    def clear_cache(self, older_than_hours: Optional[int] = None):
        """
        Clear cached responses.

        Args:
            older_than_hours: Only clear files older than this (None = all)
        """
        if not self.cache_dir.exists():
            return

        cutoff = None
        if older_than_hours:
            cutoff = datetime.now() - timedelta(hours=older_than_hours)

        count = 0
        for cache_file in self.cache_dir.glob('*.json'):
            if cutoff:
                mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                if mtime > cutoff:
                    continue
            cache_file.unlink()
            count += 1

        logger.info(f"Cleared {count} cache files")


# Convenience function for simple validation
def validate_coordinate(lat: float, lon: float, max_distance: int = 100) -> dict:
    """
    Quick validation of a single coordinate.

    Args:
        lat: Latitude
        lon: Longitude
        max_distance: Maximum distance from road in meters

    Returns:
        Validation result dict
    """
    client = OverpassClient()
    is_near, info = client.is_coordinate_near_road(lat, lon, max_distance)
    return {
        'is_valid': is_near,
        'lat': lat,
        'lon': lon,
        **info
    }
