#!/usr/bin/env python3
"""
Geocoding utilities for Virginia Crash Data Validation.

Priority order for missing coordinates:
1. Node Lookup (instant, free) - uses pre-computed node coordinates
2. Mapbox Geocoding (API) - for records without Node
3. Flag for manual review

Author: CRASH LENS Team
Version: 1.0.0
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / ".validation" / "geocache"


class NodeLookupTable:
    """
    Lookup table for Node ID → GPS coordinates.
    Built from existing crash data where Node and coordinates are both present.
    """

    def __init__(self):
        self.node_coords: Dict[str, Tuple[float, float]] = {}
        self.cache_file = CACHE_DIR / "node_coordinates.json"
        self._load_cache()

    def _load_cache(self):
        """Load cached node coordinates."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    # Convert string keys back to proper format
                    self.node_coords = {k: tuple(v) for k, v in data.items()}
                logger.info(f"Loaded {len(self.node_coords)} node coordinates from cache")
            except Exception as e:
                logger.warning(f"Failed to load node cache: {e}")

    def _save_cache(self):
        """Save node coordinates to cache."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(self.node_coords, f)
        logger.info(f"Saved {len(self.node_coords)} node coordinates to cache")

    def build_from_dataframe(self, df: pd.DataFrame):
        """
        Build lookup table from dataframe with Node and coordinates.
        Uses mean coordinates for each Node (handles slight variations).
        """
        # Filter to records with Node and valid coordinates
        valid = df[
            df['Node'].notna() &
            df['x'].notna() &
            df['y'].notna()
        ].copy()

        if len(valid) == 0:
            logger.warning("No valid Node + coordinate records found")
            return

        # Calculate mean coordinates per Node
        node_means = valid.groupby('Node').agg({
            'x': 'mean',
            'y': 'mean'
        }).reset_index()

        # Update lookup table
        new_count = 0
        for _, row in node_means.iterrows():
            node_id = str(int(row['Node']))
            if node_id not in self.node_coords:
                new_count += 1
            self.node_coords[node_id] = (row['x'], row['y'])

        logger.info(f"Built node lookup: {len(self.node_coords)} total, {new_count} new")
        self._save_cache()

    def lookup(self, node_id) -> Optional[Tuple[float, float]]:
        """
        Lookup coordinates for a Node ID.
        Returns (longitude, latitude) or None if not found.
        """
        if pd.isna(node_id):
            return None
        node_str = str(int(float(node_id)))
        return self.node_coords.get(node_str)

    def __len__(self):
        return len(self.node_coords)


class MapboxGeocoder:
    """
    Geocoder using Mapbox Geocoding API.
    Includes caching and rate limiting.
    """

    def __init__(self, access_token: str = None):
        self.access_token = access_token or self._load_token()
        self.endpoint = "https://api.mapbox.com/geocoding/v5/mapbox.places"
        self.cache: Dict[str, Tuple[float, float]] = {}
        self.cache_file = CACHE_DIR / "mapbox_geocache.json"
        self.rate_limit_delay = 0.1  # seconds between requests
        self.last_request_time = 0
        self._load_cache()

    def _load_token(self) -> str:
        """Load Mapbox token from config."""
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
                return config.get('apis', {}).get('mapbox', {}).get('accessToken', '')
        return ''

    def _load_cache(self):
        """Load cached geocoding results."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    self.cache = {k: tuple(v) for k, v in data.items()}
                logger.info(f"Loaded {len(self.cache)} cached geocoding results")
            except Exception as e:
                logger.warning(f"Failed to load geocache: {e}")

    def _save_cache(self):
        """Save geocoding results to cache."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f)

    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def geocode(self, address: str, state: str = "Virginia") -> Optional[Tuple[float, float]]:
        """
        Geocode an address using Mapbox API.
        Returns (longitude, latitude) or None if not found.
        """
        if not self.access_token:
            logger.warning("No Mapbox access token configured")
            return None

        # Normalize address for caching
        cache_key = f"{address}, {state}".lower().strip()
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Rate limit
        self._rate_limit()

        try:
            # Build request
            query = f"{address}, {state}, USA"
            url = f"{self.endpoint}/{requests.utils.quote(query)}.json"
            params = {
                'access_token': self.access_token,
                'country': 'US',
                'types': 'address,poi,place',
                'limit': 1
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('features'):
                coords = data['features'][0]['center']  # [lon, lat]
                result = (coords[0], coords[1])
                self.cache[cache_key] = result
                self._save_cache()
                return result

        except Exception as e:
            logger.warning(f"Mapbox geocoding failed for '{address}': {e}")

        return None

    def geocode_intersection(self, road1: str, road2: str,
                            jurisdiction: str = None) -> Optional[Tuple[float, float]]:
        """
        Geocode an intersection.
        """
        address = f"{road1} and {road2}"
        if jurisdiction:
            address = f"{address}, {jurisdiction}"
        return self.geocode(address)


class CrashDataGeocoder:
    """
    Main geocoder for crash data validation.
    Implements priority-based geocoding strategy.
    """

    def __init__(self):
        self.node_lookup = NodeLookupTable()
        self.mapbox = MapboxGeocoder()
        self.stats = {
            'total_processed': 0,
            'node_lookup_success': 0,
            'mapbox_success': 0,
            'failed': 0
        }

    def build_node_lookup(self, df: pd.DataFrame):
        """Build node lookup table from existing data."""
        self.node_lookup.build_from_dataframe(df)

    def geocode_record(self, record: pd.Series) -> Optional[Tuple[float, float]]:
        """
        Geocode a single record using priority strategy.

        Priority:
        1. Node lookup (if Node field populated)
        2. Mapbox geocoding (if address/route available)

        Returns (longitude, latitude) or None.
        """
        self.stats['total_processed'] += 1

        # Priority 1: Node Lookup
        if 'Node' in record.index and pd.notna(record.get('Node')):
            coords = self.node_lookup.lookup(record['Node'])
            if coords:
                self.stats['node_lookup_success'] += 1
                return coords

        # Priority 2: Mapbox Geocoding
        # Try to build an address from available fields
        address_parts = []

        # Use route name if available
        if 'RTE Name' in record.index and pd.notna(record.get('RTE Name')):
            route = str(record['RTE Name'])
            # Clean up route name (e.g., "S-VA043NP NUCKOLS RD" → "Nuckols Rd")
            if ' ' in route:
                address_parts.append(route.split(' ', 1)[1])

        # Add jurisdiction if available
        jurisdiction = None
        if 'Physical Juris Name' in record.index and pd.notna(record.get('Physical Juris Name')):
            jurisdiction = str(record['Physical Juris Name'])

        if address_parts:
            address = ' '.join(address_parts)
            coords = self.mapbox.geocode(address, jurisdiction or "Virginia")
            if coords:
                self.stats['mapbox_success'] += 1
                return coords

        self.stats['failed'] += 1
        return None

    def geocode_dataframe(self, df: pd.DataFrame,
                          only_missing: bool = True) -> pd.DataFrame:
        """
        Geocode records in a dataframe.

        Args:
            df: DataFrame with crash records
            only_missing: If True, only geocode records with missing coordinates

        Returns:
            DataFrame with geocoded coordinates
        """
        df = df.copy()

        # Build node lookup from records that have coordinates
        if 'Node' in df.columns:
            self.build_node_lookup(df)

        # Find records needing geocoding
        if only_missing:
            mask = df['x'].isna() | df['y'].isna()
        else:
            mask = pd.Series([True] * len(df), index=df.index)

        records_to_geocode = df[mask]
        logger.info(f"Geocoding {len(records_to_geocode)} records")

        # Geocode each record
        for idx in records_to_geocode.index:
            coords = self.geocode_record(df.loc[idx])
            if coords:
                df.at[idx, 'x'] = coords[0]
                df.at[idx, 'y'] = coords[1]
                logger.debug(f"Geocoded record {idx}: {coords}")

        return df

    def get_stats(self) -> dict:
        """Get geocoding statistics."""
        return {
            **self.stats,
            'node_lookup_size': len(self.node_lookup),
            'mapbox_cache_size': len(self.mapbox.cache)
        }


def geocode_missing_coordinates(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """
    Convenience function to geocode missing coordinates in a dataframe.

    Returns:
        Tuple of (geocoded dataframe, statistics dict)
    """
    geocoder = CrashDataGeocoder()
    result_df = geocoder.geocode_dataframe(df, only_missing=True)
    return result_df, geocoder.get_stats()


if __name__ == "__main__":
    # Test with sample data
    logging.basicConfig(level=logging.INFO)

    # Load sample data
    df = pd.read_csv(DATA_DIR / "henrico_all_roads.csv", low_memory=False)

    # Build node lookup
    geocoder = CrashDataGeocoder()
    geocoder.build_node_lookup(df)

    print(f"\nNode lookup table size: {len(geocoder.node_lookup)}")
    print(f"Mapbox configured: {bool(geocoder.mapbox.access_token)}")

    # Test node lookup
    test_node = df[df['Node'].notna()]['Node'].iloc[0]
    coords = geocoder.node_lookup.lookup(test_node)
    print(f"\nTest node {test_node} → {coords}")
