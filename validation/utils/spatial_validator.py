#!/usr/bin/env python3
"""
Spatial Validation for Virginia Crash Data.

Combines Overpass API (OSM) for validation and Geocoder for missing coordinates.

Validation Capabilities (Overpass):
1. Coordinate-on-road validation - Is GPS point actually on a road?
2. Intersection validation - Does location match intersection type?
3. Route name validation - Is crash on the expected road?

Geocoding Capabilities (Node Lookup + Mapbox):
1. Node lookup - Free, instant coordinate lookup from pre-built table
2. Mapbox geocoding - API-based for records without Node
3. Flag for manual review - When both fail

Author: CRASH LENS Team
Version: 1.0.0
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .geocoder import CrashDataGeocoder, NodeLookupTable
from .overpass_client import OverpassClient

logger = logging.getLogger(__name__)


class SpatialValidator:
    """
    Spatial validation using OSM Overpass API.

    Validates crash coordinates against real-world road network.
    """

    def __init__(self, enable_route_validation: bool = False):
        """
        Initialize spatial validator.

        Args:
            enable_route_validation: Whether to validate route names (slower, more API calls)
        """
        self.overpass = OverpassClient()
        self.enable_route_validation = enable_route_validation
        self.stats = {
            'total_validated': 0,
            'on_road': 0,
            'off_road': 0,
            'intersection_valid': 0,
            'intersection_invalid': 0,
            'route_match': 0,
            'route_mismatch': 0,
            'api_errors': 0
        }

    def validate_coordinate_on_road(self, lat: float, lon: float,
                                     max_distance: int = 100) -> Dict:
        """
        Validate that coordinate is near a road.

        Args:
            lat: Latitude
            lon: Longitude
            max_distance: Maximum distance from road in meters

        Returns:
            Validation result dict
        """
        self.stats['total_validated'] += 1

        is_near, info = self.overpass.is_coordinate_near_road(lat, lon, max_distance)

        if 'error' in info:
            self.stats['api_errors'] += 1
            return {
                'valid': None,  # Unknown due to error
                'issue': 'api_error',
                'message': 'Could not validate - API error'
            }

        if is_near:
            self.stats['on_road'] += 1
            return {
                'valid': True,
                'road_type': info.get('highway_type'),
                'road_name': info.get('name'),
                'roads_nearby': info.get('road_count', 1)
            }
        else:
            self.stats['off_road'] += 1
            return {
                'valid': False,
                'issue': 'coordinate_off_road',
                'severity': 'warning',
                'message': f'Coordinate not within {max_distance}m of any road'
            }

    def validate_intersection(self, lat: float, lon: float,
                               intersection_type: str) -> Dict:
        """
        Validate intersection type against actual road network.

        Args:
            lat: Latitude
            lon: Longitude
            intersection_type: Reported intersection type from crash data

        Returns:
            Validation result dict
        """
        # Non-intersection types don't need validation
        non_intersection_types = [
            '1. Not at Intersection',
            'Not at Intersection',
            '0. Not Applicable',
            'Not Applicable'
        ]

        if not intersection_type or intersection_type in non_intersection_types:
            return {'valid': True, 'skipped': True}

        # Check if coordinate is actually at an intersection
        is_intersection, road_count = self.overpass.is_intersection(lat, lon, radius=30)

        if is_intersection:
            self.stats['intersection_valid'] += 1
            return {
                'valid': True,
                'road_count': road_count,
                'message': f'Intersection confirmed ({road_count} roads)'
            }
        else:
            self.stats['intersection_invalid'] += 1
            return {
                'valid': False,
                'issue': 'intersection_mismatch',
                'severity': 'info',  # Info level - OSM may not have all intersections
                'road_count': road_count,
                'message': f'Reported as intersection but only {road_count} road(s) found'
            }

    def validate_route(self, lat: float, lon: float,
                       expected_route: str) -> Dict:
        """
        Validate that coordinate is on expected route.

        Args:
            lat: Latitude
            lon: Longitude
            expected_route: Expected road name from crash data

        Returns:
            Validation result dict
        """
        if not expected_route or not self.enable_route_validation:
            return {'valid': True, 'skipped': True}

        # Clean route name - Virginia TREDS format: "S-VA043NP NUCKOLS RD"
        clean_route = expected_route
        if ' ' in expected_route:
            # Extract the actual road name part
            clean_route = expected_route.split(' ', 1)[1] if ' ' in expected_route else expected_route

        matches, actual_road = self.overpass.validate_route_name(lat, lon, clean_route)

        if matches:
            self.stats['route_match'] += 1
            return {
                'valid': True,
                'matched_road': actual_road
            }
        else:
            self.stats['route_mismatch'] += 1
            return {
                'valid': False,
                'issue': 'route_mismatch',
                'severity': 'info',  # Info level - naming differences are common
                'expected': clean_route,
                'actual': actual_road,
                'message': f'Route name mismatch: expected "{clean_route}", found "{actual_road}"'
            }

    def validate_record(self, record: pd.Series) -> List[Dict]:
        """
        Perform spatial validation on a single record.

        Args:
            record: Pandas Series with crash record data

        Returns:
            List of validation issues (empty if all valid)
        """
        issues = []

        # Get coordinates
        x = record.get('x')
        y = record.get('y')

        if pd.isna(x) or pd.isna(y):
            return issues  # No spatial validation possible without coordinates

        try:
            lon = float(x)
            lat = float(y)
        except (ValueError, TypeError):
            return issues  # Invalid coordinates handled elsewhere

        # 1. Validate coordinate is on road
        road_result = self.validate_coordinate_on_road(lat, lon)
        if road_result.get('valid') is False:
            issues.append({
                'field': 'coordinates',
                'issue': road_result['issue'],
                'severity': road_result.get('severity', 'warning'),
                'message': road_result['message']
            })

        # 2. Validate intersection type
        intersection_type = str(record.get('Intersection Type', '')).strip()
        if intersection_type:
            int_result = self.validate_intersection(lat, lon, intersection_type)
            if int_result.get('valid') is False:
                issues.append({
                    'field': 'Intersection Type',
                    'issue': int_result['issue'],
                    'severity': int_result.get('severity', 'info'),
                    'message': int_result['message']
                })

        # 3. Validate route name (optional)
        if self.enable_route_validation:
            route_name = str(record.get('RTE Name', '')).strip()
            if route_name:
                route_result = self.validate_route(lat, lon, route_name)
                if route_result.get('valid') is False:
                    issues.append({
                        'field': 'RTE Name',
                        'issue': route_result['issue'],
                        'severity': route_result.get('severity', 'info'),
                        'message': route_result['message']
                    })

        return issues

    def get_stats(self) -> Dict:
        """Get validation statistics."""
        return self.stats.copy()


class CrashSpatialProcessor:
    """
    Combined spatial processing: validation + geocoding.

    Workflow:
    1. Geocode records with missing coordinates
    2. Validate coordinates against road network
    """

    def __init__(self, enable_geocoding: bool = True,
                 enable_validation: bool = True,
                 enable_route_validation: bool = False):
        """
        Initialize spatial processor.

        Args:
            enable_geocoding: Enable geocoding for missing coordinates
            enable_validation: Enable Overpass validation
            enable_route_validation: Enable route name validation (slower)
        """
        self.enable_geocoding = enable_geocoding
        self.enable_validation = enable_validation

        if enable_geocoding:
            self.geocoder = CrashDataGeocoder()
        else:
            self.geocoder = None

        if enable_validation:
            self.validator = SpatialValidator(enable_route_validation)
        else:
            self.validator = None

    def process_dataframe(self, df: pd.DataFrame,
                          geocode_missing: bool = True,
                          validate_sample_pct: float = 0.0) -> Tuple[pd.DataFrame, Dict]:
        """
        Process dataframe with geocoding and validation.

        Args:
            df: DataFrame with crash records
            geocode_missing: Whether to geocode records missing coordinates
            validate_sample_pct: Percentage of records to validate (0-100, 0=none)

        Returns:
            Tuple of (processed DataFrame, stats dict)
        """
        stats = {
            'geocoding': {},
            'validation': {},
            'issues': []
        }

        # Step 1: Geocode missing coordinates
        if self.enable_geocoding and geocode_missing:
            logger.info("Geocoding records with missing coordinates...")

            # Build node lookup from existing data
            self.geocoder.build_node_lookup(df)

            # Geocode
            df = self.geocoder.geocode_dataframe(df, only_missing=True)
            stats['geocoding'] = self.geocoder.get_stats()

            logger.info(f"Geocoding complete: {stats['geocoding']}")

        # Step 2: Validate coordinates
        if self.enable_validation and validate_sample_pct > 0:
            logger.info(f"Validating {validate_sample_pct}% of coordinates...")

            # Sample records for validation (full validation is slow)
            records_to_validate = df.sample(
                frac=validate_sample_pct / 100,
                random_state=42
            )

            validation_issues = []
            for idx, row in records_to_validate.iterrows():
                issues = self.validator.validate_record(row)
                for issue in issues:
                    issue['row'] = idx
                    issue['document_nbr'] = str(row.get('Document Nbr', f'row_{idx}'))
                validation_issues.extend(issues)

            stats['validation'] = self.validator.get_stats()
            stats['issues'] = validation_issues

            logger.info(f"Validation complete: {stats['validation']}")

        return df, stats


def geocode_and_validate(df: pd.DataFrame,
                         geocode_missing: bool = True,
                         validate_pct: float = 0.0) -> Tuple[pd.DataFrame, Dict]:
    """
    Convenience function for spatial processing.

    Args:
        df: DataFrame with crash records
        geocode_missing: Whether to geocode missing coordinates
        validate_pct: Percentage of records to validate spatially

    Returns:
        Tuple of (processed DataFrame, stats dict)
    """
    processor = CrashSpatialProcessor(
        enable_geocoding=geocode_missing,
        enable_validation=validate_pct > 0
    )
    return processor.process_dataframe(df, geocode_missing, validate_pct)


if __name__ == "__main__":
    # Test spatial validation
    import sys
    logging.basicConfig(level=logging.INFO)

    # Test with sample coordinates
    validator = SpatialValidator(enable_route_validation=True)

    # Test coordinate near known intersection (Nuckols Rd & Staples Mill)
    test_lat, test_lon = 37.6456, -77.5234

    print("\n=== Testing Spatial Validator ===")
    print(f"\nTest coordinate: {test_lat}, {test_lon}")

    # Test on-road validation
    road_result = validator.validate_coordinate_on_road(test_lat, test_lon)
    print(f"\nOn-road validation: {road_result}")

    # Test intersection validation
    int_result = validator.validate_intersection(test_lat, test_lon, "2. Two Approaches")
    print(f"\nIntersection validation: {int_result}")

    # Test route validation
    route_result = validator.validate_route(test_lat, test_lon, "Nuckols Rd")
    print(f"\nRoute validation: {route_result}")

    print(f"\nStats: {validator.get_stats()}")
