#!/usr/bin/env python3
"""
Spatial Validation for Virginia Crash Data.

Combines Overpass API (OSM) for validation and VDOT LRS for FREE correction.

Validation Capabilities (Overpass - FREE):
1. Coordinate-on-road validation - Is GPS point actually on a road?
2. Intersection validation - Does location match intersection type?
3. Route name validation - Is crash on the expected road?

Correction Capabilities (VDOT - FREE, no Mapbox):
1. Node lookup - Free, instant coordinate lookup from pre-built table
2. VDOT LRS/MP lookup - Free, route + milepost to coordinates
3. VDOT LRS API - Free, official VDOT service
4. Flag for manual review - When all free methods fail

Author: CRASH LENS Team
Version: 1.1.0
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

from .geocoder import CrashDataGeocoder, NodeLookupTable
from .overpass_client import OverpassClient

# Import VDOT LRS for free coordinate correction
try:
    from .vdot_lrs_client import VDOTMilepostLookup, VDOTLRSClient
    VDOT_AVAILABLE = True
except ImportError:
    VDOT_AVAILABLE = False

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


class CoordinateCorrector:
    """
    Corrects bad coordinates using FREE VDOT data sources.

    NO Mapbox - uses only:
    1. Node Lookup (pre-built from existing data)
    2. VDOT LRS/MP Lookup (pre-built from existing data)
    3. VDOT LRS API (official free service)
    """

    def __init__(self, use_vdot_api: bool = False):
        """
        Initialize coordinate corrector.

        Args:
            use_vdot_api: Enable VDOT LRS API calls (slower but more complete)
        """
        self.node_lookup = NodeLookupTable()
        self.vdot_milepost_lookup = None
        self.vdot_lrs_client = None
        self.use_vdot_api = use_vdot_api

        if VDOT_AVAILABLE:
            self.vdot_milepost_lookup = VDOTMilepostLookup()
            if use_vdot_api:
                self.vdot_lrs_client = VDOTLRSClient()

        self.stats = {
            'total_bad_coords': 0,
            'corrected_via_node': 0,
            'corrected_via_vdot_mp': 0,
            'corrected_via_vdot_api': 0,
            'flagged_for_review': 0
        }

    def build_lookups(self, df: pd.DataFrame):
        """Build lookup tables from existing data with valid coordinates."""
        # Build node lookup
        self.node_lookup.build_from_dataframe(df)

        # Build VDOT milepost lookup
        if self.vdot_milepost_lookup is not None:
            self.vdot_milepost_lookup.build_from_dataframe(df)

    def correct_coordinate(self, record: pd.Series) -> Optional[Tuple[float, float]]:
        """
        Attempt to correct a bad coordinate using FREE VDOT data.

        Priority:
        1. Node Lookup (instant, free)
        2. VDOT LRS/MP Lookup (instant, free)
        3. VDOT LRS API (free, slower)

        Returns:
            (longitude, latitude) or None if cannot correct
        """
        self.stats['total_bad_coords'] += 1

        # Priority 1: Node Lookup
        if 'Node' in record.index and pd.notna(record.get('Node')):
            coords = self.node_lookup.lookup(record['Node'])
            if coords:
                self.stats['corrected_via_node'] += 1
                return coords

        # Priority 2: VDOT Milepost Lookup
        route_name = record.get('RTE Name') if 'RTE Name' in record.index else None
        milepost = record.get('RNS MP') if 'RNS MP' in record.index else None

        if self.vdot_milepost_lookup and route_name and pd.notna(route_name) and pd.notna(milepost):
            try:
                coords = self.vdot_milepost_lookup.lookup(str(route_name), float(milepost))
                if coords:
                    self.stats['corrected_via_vdot_mp'] += 1
                    return coords
            except (ValueError, TypeError):
                pass

        # Priority 3: VDOT LRS API (if enabled)
        if self.vdot_lrs_client and route_name and pd.notna(route_name) and pd.notna(milepost):
            try:
                coords = self.vdot_lrs_client.geocode_milepost(str(route_name), float(milepost))
                if coords:
                    self.stats['corrected_via_vdot_api'] += 1
                    return coords
            except (ValueError, TypeError):
                pass

        # Cannot correct - flag for manual review
        self.stats['flagged_for_review'] += 1
        return None

    def get_stats(self) -> Dict:
        """Get correction statistics."""
        return self.stats.copy()


class CrashSpatialProcessor:
    """
    Combined spatial processing: validation + correction + geocoding.

    Workflow (incremental - only processes NEW records):
    1. Geocode records with missing coordinates
    2. Validate coordinates against road network (Overpass - FREE)
    3. Auto-correct bad coordinates using VDOT data (FREE - no Mapbox)
    """

    def __init__(self, enable_geocoding: bool = True,
                 enable_validation: bool = True,
                 enable_correction: bool = True,
                 enable_route_validation: bool = False,
                 use_vdot_api: bool = False):
        """
        Initialize spatial processor.

        Args:
            enable_geocoding: Enable geocoding for missing coordinates
            enable_validation: Enable Overpass validation
            enable_correction: Enable auto-correction of bad coordinates
            enable_route_validation: Enable route name validation (slower)
            use_vdot_api: Enable VDOT LRS API for correction (slower but more complete)
        """
        self.enable_geocoding = enable_geocoding
        self.enable_validation = enable_validation
        self.enable_correction = enable_correction

        if enable_geocoding:
            self.geocoder = CrashDataGeocoder()
        else:
            self.geocoder = None

        if enable_validation:
            self.validator = SpatialValidator(enable_route_validation)
        else:
            self.validator = None

        if enable_correction:
            self.corrector = CoordinateCorrector(use_vdot_api=use_vdot_api)
        else:
            self.corrector = None

    def process_dataframe(self, df: pd.DataFrame,
                          geocode_missing: bool = True,
                          validate_sample_pct: float = 0.0,
                          correct_bad_coords: bool = True,
                          validated_ids: Optional[set] = None) -> Tuple[pd.DataFrame, Dict]:
        """
        Process dataframe with geocoding, validation, and correction.

        INCREMENTAL: Only processes new records when validated_ids provided.

        Args:
            df: DataFrame with crash records
            geocode_missing: Whether to geocode records missing coordinates
            validate_sample_pct: Percentage of NEW records to validate (0-100, 0=none)
            correct_bad_coords: Whether to auto-correct bad coordinates
            validated_ids: Set of already-validated Document Numbers (for incremental)

        Returns:
            Tuple of (processed DataFrame, stats dict)
        """
        stats = {
            'geocoding': {},
            'validation': {},
            'correction': {},
            'issues': [],
            'records_processed': 0,
            'records_skipped': 0
        }

        df = df.copy()

        # Filter to new records only (incremental processing)
        if validated_ids and 'Document Nbr' in df.columns:
            new_mask = ~df['Document Nbr'].astype(str).str.strip().isin(validated_ids)
            new_df = df[new_mask]
            stats['records_processed'] = len(new_df)
            stats['records_skipped'] = len(df) - len(new_df)
            logger.info(f"Incremental mode: processing {len(new_df)} new records, skipping {stats['records_skipped']}")
        else:
            new_df = df
            stats['records_processed'] = len(new_df)
            logger.info(f"Full mode: processing all {len(new_df)} records")

        if len(new_df) == 0:
            logger.info("No new records to process")
            return df, stats

        # Build lookup tables from ALL data (including existing validated)
        if self.geocoder:
            self.geocoder.build_lookups(df)
        if self.corrector:
            self.corrector.build_lookups(df)

        # Step 1: Geocode missing coordinates (new records only)
        if self.enable_geocoding and geocode_missing:
            missing_coords = new_df[new_df['x'].isna() | new_df['y'].isna()]
            if len(missing_coords) > 0:
                logger.info(f"Geocoding {len(missing_coords)} records with missing coordinates...")

                for idx in missing_coords.index:
                    coords = self.geocoder.geocode_record(df.loc[idx])
                    if coords:
                        df.at[idx, 'x'] = coords[0]
                        df.at[idx, 'y'] = coords[1]

                stats['geocoding'] = self.geocoder.get_stats()
                logger.info(f"Geocoding complete: {stats['geocoding']}")
            else:
                logger.info("No records with missing coordinates")

        # Step 2: Validate and correct coordinates (new records only)
        if self.enable_validation and validate_sample_pct > 0:
            # Determine records to validate
            if validate_sample_pct >= 100:
                records_to_validate = new_df
            else:
                sample_size = max(1, int(len(new_df) * validate_sample_pct / 100))
                records_to_validate = new_df.sample(n=min(sample_size, len(new_df)), random_state=42)

            logger.info(f"Validating {len(records_to_validate)} coordinates against road network...")

            validation_issues = []
            corrections_made = []

            for idx, row in records_to_validate.iterrows():
                # Validate coordinate
                issues = self.validator.validate_record(row)

                for issue in issues:
                    issue['row'] = idx
                    issue['document_nbr'] = str(row.get('Document Nbr', f'row_{idx}'))

                # If coordinate is bad and correction is enabled, try to fix it
                if issues and self.enable_correction and correct_bad_coords:
                    # Check if any issue is coordinate-related
                    coord_issues = [i for i in issues if i.get('issue') in
                                    ['coordinate_off_road', 'outside_bounds', 'outside_state_bounds']]

                    if coord_issues:
                        # Try to correct using VDOT data (FREE)
                        new_coords = self.corrector.correct_coordinate(row)

                        if new_coords:
                            old_x, old_y = row.get('x'), row.get('y')
                            df.at[idx, 'x'] = new_coords[0]
                            df.at[idx, 'y'] = new_coords[1]

                            corrections_made.append({
                                'document_nbr': str(row.get('Document Nbr', f'row_{idx}')),
                                'old_coords': (old_x, old_y),
                                'new_coords': new_coords,
                                'issue': coord_issues[0]['issue']
                            })

                            # Update issue to show it was corrected
                            for issue in coord_issues:
                                issue['corrected'] = True
                                issue['new_coords'] = new_coords

                validation_issues.extend(issues)

            stats['validation'] = self.validator.get_stats()
            stats['correction'] = self.corrector.get_stats() if self.corrector else {}
            stats['corrections_made'] = corrections_made
            stats['issues'] = validation_issues

            logger.info(f"Validation complete: {stats['validation']}")
            if corrections_made:
                logger.info(f"Auto-corrected {len(corrections_made)} coordinates using VDOT data")

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
