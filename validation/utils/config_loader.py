"""
Configuration Loader Utility

Loads and provides access to configuration from config.json,
including jurisdiction settings, API endpoints, and bounds.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional


class ConfigLoader:
    """
    Loads and provides access to application configuration.

    Provides convenient methods for accessing:
    - Jurisdiction configurations
    - Bounding boxes
    - API settings
    - Default values
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize config loader.

        Args:
            config_path: Path to config.json. Defaults to project root.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config.json"

        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load configuration from JSON file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            return json.load(f)

    def get_jurisdiction(self, jurisdiction_id: str) -> Optional[dict]:
        """
        Get configuration for a specific jurisdiction.

        Args:
            jurisdiction_id: Jurisdiction identifier (e.g., 'henrico')

        Returns:
            Jurisdiction config dict or None if not found
        """
        return self.config.get('jurisdictions', {}).get(jurisdiction_id)

    def get_jurisdiction_bounds(self, jurisdiction_id: str) -> Optional[dict]:
        """
        Get bounding box for a jurisdiction.

        Args:
            jurisdiction_id: Jurisdiction identifier

        Returns:
            Dict with minLon, minLat, maxLon, maxLat or None
        """
        juris = self.get_jurisdiction(jurisdiction_id)
        if juris and 'bbox' in juris:
            bbox = juris['bbox']
            if len(bbox) == 4:
                return {
                    'minLon': bbox[0],
                    'minLat': bbox[1],
                    'maxLon': bbox[2],
                    'maxLat': bbox[3]
                }
        return None

    def get_all_jurisdictions(self) -> Dict[str, dict]:
        """Get all jurisdiction configurations."""
        return self.config.get('jurisdictions', {})

    def get_jurisdictions_with_own_roads(self) -> List[str]:
        """Get list of jurisdictions that maintain their own roads."""
        result = []
        for jid, jconfig in self.get_all_jurisdictions().items():
            if jconfig.get('maintainsOwnRoads', False):
                result.append(jid)
        return result

    def get_default_jurisdiction(self) -> str:
        """Get default jurisdiction from config."""
        return self.config.get('defaults', {}).get('jurisdiction', 'henrico')

    def get_api_config(self, api_name: str) -> Optional[dict]:
        """
        Get configuration for an API.

        Args:
            api_name: API name (e.g., 'tigerweb', 'mapbox')

        Returns:
            API config dict or None
        """
        return self.config.get('apis', {}).get(api_name)

    def get_virginia_bounds(self) -> dict:
        """Get Virginia state bounding box."""
        # Calculated from all jurisdiction bounds
        return {
            'minLon': -83.675,
            'minLat': 36.541,
            'maxLon': -75.242,
            'maxLat': 39.466
        }

    def is_coordinate_in_virginia(self, lon: float, lat: float) -> bool:
        """Check if coordinate is within Virginia bounds."""
        bounds = self.get_virginia_bounds()
        return (bounds['minLon'] <= lon <= bounds['maxLon'] and
                bounds['minLat'] <= lat <= bounds['maxLat'])

    def is_coordinate_in_jurisdiction(self, lon: float, lat: float,
                                      jurisdiction_id: str) -> bool:
        """Check if coordinate is within jurisdiction bounds."""
        bounds = self.get_jurisdiction_bounds(jurisdiction_id)
        if not bounds:
            return True  # Can't validate without bounds

        return (bounds['minLon'] <= lon <= bounds['maxLon'] and
                bounds['minLat'] <= lat <= bounds['maxLat'])
