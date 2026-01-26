"""
Utility modules for validation system.

Modules:
    - config_loader: Load configuration from config.json
    - file_handler: CSV read/write operations
    - overpass_client: Overpass API client for road validation
    - geocoder: Geocoding for missing coordinates (Node Lookup + Mapbox)
    - spatial_validator: Spatial validation using OSM Overpass
"""

from .config_loader import ConfigLoader
from .file_handler import FileHandler
from .overpass_client import OverpassClient
from .geocoder import (
    NodeLookupTable,
    MapboxGeocoder,
    CrashDataGeocoder,
    geocode_missing_coordinates
)
from .spatial_validator import (
    SpatialValidator,
    CrashSpatialProcessor,
    geocode_and_validate
)
from .vdot_lrs_client import (
    VDOTLRSClient,
    VDOTMilepostLookup,
    geocode_with_vdot_lrs
)

__all__ = [
    "ConfigLoader",
    "FileHandler",
    "OverpassClient",
    "NodeLookupTable",
    "MapboxGeocoder",
    "CrashDataGeocoder",
    "geocode_missing_coordinates",
    "SpatialValidator",
    "CrashSpatialProcessor",
    "geocode_and_validate",
    "VDOTLRSClient",
    "VDOTMilepostLookup",
    "geocode_with_vdot_lrs"
]
