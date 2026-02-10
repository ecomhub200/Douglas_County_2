#!/usr/bin/env python3
"""
Multi-State Crash Data Adapter (Python)

Detects the source state from CSV headers and converts raw crash data
to the standardized CRASH LENS internal format (Virginia-compatible columns).

This is the Python counterpart to states/state_adapter.js - it performs
the same normalization but as a persistent pre-processing step, writing
standardized CSV files that the validation system can then process.

Supported states:
  - Virginia (TREDS) - passthrough, already in internal format
  - Colorado (CDOT) - full column mapping + severity derivation

Adding a new state:
  1. Create states/{state}/config.json with columnMapping + derivedFields
  2. Add a detection signature in STATE_SIGNATURES
  3. Add a normalizer class inheriting from BaseNormalizer

Usage:
    from state_adapter import StateDetector, get_normalizer

    detector = StateDetector()
    state = detector.detect_from_headers(csv_headers)
    normalizer = get_normalizer(state)
    standardized_row = normalizer.normalize_row(raw_row)
"""

import csv
import json
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# --- State detection signatures ---
STATE_SIGNATURES = {
    'colorado': {
        'required': ['CUID', 'System Code', 'Injury 00', 'Injury 04'],
        'optional': ['Rd_Number', 'Rd_Section', 'MHE'],
        'display_name': 'Colorado (CDOT)',
        'config_dir': 'colorado'
    },
    'virginia': {
        'required': ['Document Nbr', 'Crash Severity', 'RTE Name', 'SYSTEM'],
        'optional': ['K_People', 'A_People', 'Node', 'Physical Juris Name'],
        'display_name': 'Virginia (TREDS)',
        'config_dir': 'virginia'
    }
}

# Standardized output columns (Virginia-compatible format)
STANDARD_COLUMNS = [
    'Document Nbr', 'Crash Date', 'Crash Year', 'Crash Military Time',
    'Crash Severity', 'K_People', 'A_People', 'B_People', 'C_People',
    'Collision Type', 'Weather Condition', 'Light Condition',
    'Roadway Surface Condition', 'Roadway Alignment',
    'Roadway Description', 'Intersection Type',
    'RTE Name', 'SYSTEM', 'Node', 'RNS MP',
    'x', 'y',  # longitude, latitude (Virginia convention: x=lon, y=lat)
    'Physical Juris Name',
    'Pedestrian?', 'Bike?', 'Alcohol?', 'Speed?', 'Hitrun?',
    'Motorcycle?', 'Night?', 'Distracted?', 'Drowsy?', 'Drug Related?',
    'Young?', 'Senior?', 'Unrestrained?', 'School Zone', 'Work Zone Related',
    'Traffic Control Type', 'Traffic Control Status',
    'Functional Class', 'Area Type', 'Facility Type', 'Ownership',
    'First Harmful Event', 'First Harmful Event Loc',
    'Relation To Roadway',  # intersection location relationship
    'Vehicle Count',         # number of vehicles involved
    'Persons Injured', 'Pedestrians Killed', 'Pedestrians Injured',
    # Original state columns preserved with prefix
    '_source_state', '_source_file'
]


class StateDetector:
    """Detect which state's crash data format a CSV uses."""

    def detect_from_headers(self, headers: List[str]) -> str:
        """
        Detect state from CSV column headers.

        Returns state key (e.g., 'colorado', 'virginia') or 'unknown'.
        """
        normalized = set(h.strip() for h in headers)

        # Exact match first
        for state_key, sig in STATE_SIGNATURES.items():
            if all(col in normalized for col in sig['required']):
                return state_key

        # Partial match fallback
        best_match = None
        best_score = 0.0
        for state_key, sig in STATE_SIGNATURES.items():
            all_cols = sig['required'] + sig.get('optional', [])
            score = sum(1 for c in all_cols if c in normalized) / len(all_cols)
            if score > best_score:
                best_score = score
                best_match = state_key

        if best_score > 0.5 and best_match:
            return best_match

        return 'unknown'

    def detect_from_file(self, filepath: str) -> str:
        """Detect state from CSV file headers."""
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            headers = next(reader)
        return self.detect_from_headers(headers)


class BaseNormalizer(ABC):
    """Base class for state-specific data normalizers."""

    def __init__(self, state_key: str, config_path: Optional[str] = None):
        self.state_key = state_key
        self.config = {}
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self.config = json.load(f)

    @abstractmethod
    def normalize_row(self, row: Dict[str, str]) -> Dict[str, str]:
        """Convert a raw CSV row dict to standardized format."""
        pass

    def get_state_bounds(self) -> Optional[Dict]:
        """Get coordinate bounds for this state."""
        state_cfg = self.config.get('state', {})
        bounds = state_cfg.get('coordinateBounds', {})
        if bounds:
            return {
                'minLat': bounds.get('latMin', 0),
                'maxLat': bounds.get('latMax', 0),
                'minLon': bounds.get('lonMin', 0),
                'maxLon': bounds.get('lonMax', 0)
            }
        return None

    def get_road_system_column(self) -> str:
        """Get the column name used for road system classification."""
        mapping = self.config.get('columnMapping', {})
        return mapping.get('ROAD_SYSTEM', 'SYSTEM')

    def get_agency_column(self) -> str:
        """Get the column name used for agency identification."""
        mapping = self.config.get('columnMapping', {})
        return mapping.get('AGENCY', 'Agency Id')


class VirginiaNormalizer(BaseNormalizer):
    """Virginia TREDS data - already in standard format, passthrough."""

    def normalize_row(self, row: Dict[str, str]) -> Dict[str, str]:
        normalized = dict(row)
        normalized['_source_state'] = 'virginia'
        return normalized


class ColoradoNormalizer(BaseNormalizer):
    """Colorado CDOT data normalizer - converts to Virginia-compatible VDOT format.

    Produces output with numbered-prefix values matching the Henrico VDOT reference
    format used by CRASH LENS (e.g., '1. Rear End', '2. Daylight').
    """

    # ----------------------------------------------------------------
    # Step 1: Colorado MHE/Crash Type → intermediate collision category
    # ----------------------------------------------------------------
    COLLISION_MAP = {
        'Rear-End': 'Rear End', 'Front to Rear': 'Rear End',
        'Broadside': 'Angle', 'Front to Side': 'Angle',
        'Rear to Side': 'Angle', 'Approach Turn': 'Angle',
        'Overtaking Turn': 'Angle',
        'Head-On': 'Head On', 'Front to Front': 'Head On',
        'Sideswipe Same Direction': 'Sideswipe - Same Direction',
        'Side to Side-Same Direction': 'Sideswipe - Same Direction',
        'Sideswipe Opposite Direction': 'Sideswipe - Opposite Direction',
        'Side to Side-Opposite Direction': 'Sideswipe - Opposite Direction',
        'Overturning/Rollover': 'Non-Collision',
        'Other Non-Collision': 'Non-Collision',
        'Fell from Motor Vehicle': 'Non-Collision', 'Ground': 'Non-Collision',
        'Pedestrian': 'Pedestrian',
        'School Age To/From School': 'Pedestrian',
        'Bicycle/Motorized Bicycle': 'Bicyclist',
        'Wild Animal': 'Other Animal', 'Domestic Animal': 'Other Animal',
        # Fixed objects
        'Light Pole/Utility Pole': 'Fixed Object - Off Road',
        'Traffic Signal Pole': 'Fixed Object - Off Road',
        'Concrete Highway Barrier': 'Fixed Object - Off Road',
        'Guardrail Face': 'Fixed Object - Off Road',
        'Guardrail End': 'Fixed Object - Off Road',
        'Cable Rail': 'Fixed Object - Off Road',
        'Tree': 'Fixed Object - Off Road', 'Fence': 'Fixed Object - Off Road',
        'Sign': 'Fixed Object - Off Road', 'Curb': 'Fixed Object - Off Road',
        'Embankment': 'Fixed Object - Off Road', 'Ditch': 'Fixed Object - Off Road',
        'Large Rocks or Boulder': 'Fixed Object - Off Road',
        'Electrical/Utility Box': 'Fixed Object - Off Road',
        'Electical/Utility Box': 'Fixed Object - Off Road',  # typo in source
        'Crash Cushion/Traffic Barrel': 'Fixed Object - Off Road',
        'Mailbox': 'Fixed Object - Off Road',
        'Delineator/Milepost': 'Fixed Object - Off Road',
        'Culvert or Headwall': 'Fixed Object - Off Road',
        'Wall or Building': 'Fixed Object - Off Road',
        'Barricade': 'Fixed Object - Off Road',
        'Bridge Structure (Not Overhead)': 'Fixed Object - Off Road',
        'Overhead Structure (Not Bridge)': 'Fixed Object - Off Road',
        'Railroad Crossing Equipment': 'Fixed Object - Off Road',
        'Other Fixed Object (Describe in Narrative)': 'Fixed Object - Off Road',
        'Vehicle Debris or Cargo': 'Fixed Object in Road',
        'Parked Motor Vehicle': 'Other',
        'Other Non-Fixed Object (Describe in Narrative)': 'Other',
        'Other Non-Fixed Object Describe in Narrative)': 'Other',
    }

    # ----------------------------------------------------------------
    # Step 2: Intermediate category → VDOT numbered-prefix format
    # ----------------------------------------------------------------
    COLLISION_VDOT_MAP = {
        'Rear End': '1. Rear End',
        'Angle': '2. Angle',
        'Head On': '3. Head On',
        'Sideswipe - Same Direction': '4. Sideswipe - Same Direction',
        'Sideswipe - Opposite Direction': '5. Sideswipe - Opposite Direction',
        'Non-Collision': '8. Non-Collision',
        'Fixed Object - Off Road': '9. Fixed Object - Off Road',
        'Other Animal': '10. Deer/Animal',
        'Fixed Object in Road': '11. Fixed Object in Road',
        'Pedestrian': '12. Ped',
        'Bicyclist': '13. Bicycle',
        'Other': '16. Other',
        'Unknown': '16. Other',
    }

    # ----------------------------------------------------------------
    # Weather: Colorado raw → VDOT numbered format
    # ----------------------------------------------------------------
    WEATHER_VDOT_MAP = {
        'Clear': '1. No Adverse Condition (Clear/Cloudy)',
        'Cloudy': '1. No Adverse Condition (Clear/Cloudy)',
        'Rain': '5. Rain',
        'Snow': '4. Snow',
        'Blowing Snow': '4. Snow',
        'Sleet, Hail (Freezing Rain or Drizzle)': '6. Sleet/Hail/Freezing',
        'Freezing Rain or Freezing Drizzle': '6. Sleet/Hail/Freezing',
        'Sleet or Hail': '6. Sleet/Hail/Freezing',
        'Fog': '3. Fog/Smog/Smoke',
        'Blowing Sand, Soil, Dirt': '7. Blowing Sand/Dust',
        'Dust': '7. Blowing Sand/Dust',
        'Severe Crosswinds': '8. Severe Crosswinds',
        'Wind': '8. Severe Crosswinds',
    }

    # ----------------------------------------------------------------
    # Light: Colorado raw → VDOT numbered format
    # ----------------------------------------------------------------
    LIGHT_VDOT_MAP = {
        'Daylight': '2. Daylight',
        'Dark \u2013 Lighted': '4. Darkness - Road Lighted',
        'Dark \u2013 Unlighted': '5. Darkness - Road Not Lighted',
        'Dark - Lighted': '4. Darkness - Road Lighted',
        'Dark - Unlighted': '5. Darkness - Road Not Lighted',
        'Dawn or Dusk': '1. Dawn',  # refined by time in normalize_row
    }

    # ----------------------------------------------------------------
    # Roadway Surface: Colorado raw → VDOT numbered format
    # ----------------------------------------------------------------
    SURFACE_VDOT_MAP = {
        'Dry': '1. Dry',
        'Wet': '2. Wet',
        'Snow': '3. Snow', 'Snowy': '3. Snow',
        'Snowy W/Visible Icy Road Treatment': '3. Snow',
        'Ice': '5. Ice', 'Icy': '5. Ice',
        'Icy W/Visible Icy Road Treatment': '5. Ice',
        'Slush': '4. Slush', 'Slushy': '4. Slush',
        'Slushy W/Visible Icy Road Treatment': '4. Slush',
        'Dry W/Visible Icy Road Treatment': '1. Dry',
        'Wet W/Visible Icy Road Treatment': '2. Wet',
        'Sand, Mud, Dirt, Oil, Gravel': '6. Sand/Mud/Dirt/Oil/Gravel',
        'Sand/Gravel': '6. Sand/Mud/Dirt/Oil/Gravel',
        'Muddy': '6. Sand/Mud/Dirt/Oil/Gravel',
        'Water (Standing, Moving)': '7. Water',
        'Roto-Milled': '16. Other',
        'Other': '16. Other',
    }

    # ----------------------------------------------------------------
    # Roadway Description: derive road geometry from System Code
    # (CO "Road Description" is actually intersection relation, not geometry)
    # ----------------------------------------------------------------
    ROAD_DESC_FROM_SYSTEM = {
        'Interstate Highway': '3. Two-Way, Divided, Positive Median Barrier',
        'State Highway': '2. Two-Way, Divided, Unprotected Median',
        'County Road': '1. Two-Way, Not Divided',
        'City Street': '1. Two-Way, Not Divided',
        'Frontage Road': '1. Two-Way, Not Divided',
    }

    # ----------------------------------------------------------------
    # Intersection Type: CO Road Description → VDOT approach counts
    # ----------------------------------------------------------------
    INTERSECTION_VDOT_MAP = {
        'Non-Intersection': '1. Not at Intersection',
        'At Intersection': '4. Four Approaches',
        'Intersection Related': '4. Four Approaches',
        'Driveway Access Related': '2. Two Approaches',
        'Ramp': '1. Not at Intersection',
        'Ramp-related': '1. Not at Intersection',
        'Roundabout': '5. Roundabout',
        'Crossover-Related': '1. Not at Intersection',
        'Crossover-Related ': '1. Not at Intersection',
        'Express/Managed/HOV Lane': '1. Not at Intersection',
        'Auxiliary Lane': '1. Not at Intersection',
        'Alley Related': '4. Four Approaches',
        'Railroad Crossing Related': '2. Two Approaches',
        'Mid-Block Crosswalk': '1. Not at Intersection',
    }

    # ----------------------------------------------------------------
    # Relation To Roadway: CO Road Description → VDOT relation codes
    # ----------------------------------------------------------------
    RELATION_TO_ROADWAY_MAP = {
        'Non-Intersection': '8. Non-Intersection',
        'At Intersection': '9. Within Intersection',
        'Intersection Related': '10. Intersection Related - Within 150 Feet',
        'Ramp': '2. Acceleration/Deceleration Lanes',
        'Ramp-related': '2. Acceleration/Deceleration Lanes',
        'Driveway Access Related': '8. Non-Intersection',
        'Crossover-Related': '1. Main-Line Roadway',
        'Crossover-Related ': '1. Main-Line Roadway',
        'Roundabout': '9. Within Intersection',
        'Express/Managed/HOV Lane': '1. Main-Line Roadway',
        'Auxiliary Lane': '1. Main-Line Roadway',
        'Alley Related': '8. Non-Intersection',
        'Railroad Crossing Related': '8. Non-Intersection',
        'Mid-Block Crosswalk': '8. Non-Intersection',
    }

    # ----------------------------------------------------------------
    # First Harmful Event: CO raw → VDOT numbered codes
    # ----------------------------------------------------------------
    FIRST_HE_VDOT_MAP = {
        # Motor vehicle collisions
        'Front to Rear': '20. Motor Vehicle In Transport',
        'Front to Side': '20. Motor Vehicle In Transport',
        'Rear to Side': '20. Motor Vehicle In Transport',
        'Front to Front': '20. Motor Vehicle In Transport',
        'Side to Side-Same Direction': '20. Motor Vehicle In Transport',
        'Side to Side-Opposite Direction': '20. Motor Vehicle In Transport',
        'Rear to Rear': '20. Motor Vehicle In Transport',
        'Other Non-Collision': '38. Other Non-Collision',
        'Other Non-Fixed Object (Describe in Narrative)': '37. Other Object (Not Fixed)',
        'Other Non-Fixed Object Describe in Narrative)': '37. Other Object (Not Fixed)',
        # Fixed objects
        'Light Pole/Utility Pole': '3. Utility Pole',
        'Traffic Signal Pole': '3. Utility Pole',
        'Electrical/Utility Box': '3. Utility Pole',
        'Electical/Utility Box': '3. Utility Pole',  # typo in source
        'Tree': '2. Trees',
        'Guardrail Face': '5. Guard Rail',
        'Guardrail End': '5. Guard Rail',
        'Cable Rail': '5. Guard Rail',
        'Fence': '8. Fence',
        'Curb': '27. Curb',
        'Ditch': '14. Ditch',
        'Embankment': '13. Embankment',
        'Sign': '4. Traffic Sign Support',
        'Concrete Highway Barrier': '15. Concrete Traffic Barrier',
        'Crash Cushion/Traffic Barrel': '16. Impact Attenuator/Crash Cushion',
        'Bridge Structure (Not Overhead)': '17. Bridge Pier or Abutment',
        'Overhead Structure (Not Bridge)': '18. Overhead Sign Post',
        'Wall or Building': '12. Building/Structure',
        'Large Rocks or Boulder': '24. Other Fixed Object',
        'Delineator/Milepost': '24. Other Fixed Object',
        'Mailbox': '7. Mailbox',
        'Culvert or Headwall': '10. Culvert',
        'Barricade': '24. Other Fixed Object',
        'Railroad Crossing Equipment': '24. Other Fixed Object',
        'Other Fixed Object (Describe in Narrative)': '24. Other Fixed Object',
        # Rollover / non-collision
        'Overturning/Rollover': '30. Overturn (Rollover)',
        'Ground': '30. Overturn (Rollover)',
        'Fell from Motor Vehicle': '39. Fell/Jumped From Vehicle',
        # Non-motorist
        'Pedestrian': '19. Ped',
        'School Age To/From School': '19. Ped',
        'Bicycle/Motorized Bicycle': '22. Bicycle',
        # Animals
        'Wild Animal': '21. Animal',
        'Domestic Animal': '21. Animal',
        # Parked vehicles
        'Parked Motor Vehicle': '6. Parked Vehicle',
        'Vehicle Debris or Cargo': '37. Other Object (Not Fixed)',
        # Fire
        'Fire/Explosion': '34. Fire/Explosion',
    }

    # ----------------------------------------------------------------
    # First Harmful Event Location: CO raw → VDOT numbered codes
    # ----------------------------------------------------------------
    FIRST_HE_LOC_VDOT_MAP = {
        'On Roadway': '1. On Roadway',
        'Center median/ Island': '3. Median',
        'Ran off left side': '4. Roadside',
        'Ran off right side': '4. Roadside',
        'Shoulder': '2. Shoulder',
        'In Parking Lane': '1. On Roadway',
        'Gore': '5. Gore',
        'Vehicle crossed center median into opposing lanes': '3. Median',
        'Ran off "T" intersection': '4. Roadside',
        'On private property': '9. Outside Right-of-Way',
    }

    # ----------------------------------------------------------------
    # Ownership: derive from System Code
    # ----------------------------------------------------------------
    OWNERSHIP_FROM_SYSTEM = {
        'Interstate Highway': '1. State Hwy Agency',
        'State Highway': '1. State Hwy Agency',
        'County Road': '2. County Hwy Agency',
        'City Street': '3. City or Town Hwy Agency',
        'Frontage Road': '1. State Hwy Agency',
    }

    ROAD_SYSTEM_MAP = {
        'City Street': 'NonVDOT secondary',
        'County Road': 'NonVDOT secondary',
        'State Highway': 'Primary',
        'Interstate Highway': 'Interstate',
        'Frontage Road': 'Secondary',
        'Non Crash': 'NonVDOT secondary',
    }

    SPEED_ACTIONS = {
        'Too Fast for Conditions', 'Exceeded Speed Limit',
        'Exceeded Safe/Posted Speed', 'Speeding'
    }

    DISTRACTED_VALUES = {
        'Distracted', 'Cell Phone', 'Inattention',
        'Distracted - Cell Phone/Electronic Device',
        'Distracted - Other', 'Inattentive/Distracted'
    }

    DROWSY_VALUES = {
        'Asleep or Fatigued', 'Asleep/Fatigued', 'Fatigued/Asleep',
        'Ill/Asleep/Fatigued', 'Fatigued', 'Asleep'
    }

    ALCOHOL_POSITIVE = {
        'Yes - SFST', 'Yes - BAC', 'Yes - Both', 'Yes - Observation'
    }

    DRUG_POSITIVE = {
        'Yes - Observation', 'Yes - SFST', 'Yes - Both', 'Yes - Test Results'
    }

    DARKNESS_VALUES = {
        'Dark \u2013 Lighted', 'Dark \u2013 Unlighted',
        'Dark - Lighted', 'Dark - Unlighted'
    }

    # Colorado-specific detail columns to preserve (output_name, raw_col_name)
    CO_EXTRA_COLUMNS = [
        ('_co_total_vehicles', 'Total Vehicles'),
        ('_co_mhe', 'MHE'),
        ('_co_crash_type', 'Crash Type'),
        ('_co_link', 'Link'),
        ('_co_second_he', 'Second HE'),
        ('_co_third_he', 'Third HE'),
        ('_co_wild_animal', 'Wild Animal'),
        ('_co_secondary_crash', 'Secondary Crash'),
        ('_co_weather2', 'Weather Condition 2'),
        ('_co_lane_position', 'Lane Position'),
        ('_co_injury00_uninjured', 'Injury 00'),
        # TU-1 fields
        ('_co_tu1_direction', 'TU-1 Direction'),
        ('_co_tu1_movement', 'TU-1 Movement'),
        ('_co_tu1_vehicle_type', 'TU-1 Type'),
        ('_co_tu1_speed_limit', 'TU-1 Speed Limit'),
        ('_co_tu1_estimated_speed', 'TU-1 Estimated Speed'),
        ('_co_tu1_stated_speed', 'TU-1 Speed'),
        ('_co_tu1_driver_action', 'TU-1 Driver Action'),
        ('_co_tu1_human_factor', 'TU-1 Human Contributing Factor'),
        ('_co_tu1_age', 'TU-1 Age'),
        ('_co_tu1_sex', 'TU-1 Sex '),
        # TU-2 fields
        ('_co_tu2_direction', 'TU-2 Direction'),
        ('_co_tu2_movement', 'TU-2 Movement'),
        ('_co_tu2_vehicle_type', 'TU-2 Type'),
        ('_co_tu2_speed_limit', 'TU-2 Speed Limit'),
        ('_co_tu2_estimated_speed', 'TU-2 Estimated Speed'),
        ('_co_tu2_stated_speed', 'TU-2 Speed'),
        ('_co_tu2_driver_action', 'TU-2 Driver Action'),
        ('_co_tu2_human_factor', 'TU-2 Human Contributing Factor'),
        ('_co_tu2_age', 'TU-2 Age'),
        ('_co_tu2_sex', 'TU-2 Sex'),
        # Non-motorist (ped/bike) fields
        ('_co_nm1_type', 'TU-1 NM Type'),
        ('_co_nm1_age', 'TU-1 NM Age '),
        ('_co_nm1_sex', 'TU-1 NM Sex '),
        ('_co_nm1_action', 'TU-1 NM Action '),
        ('_co_nm1_movement', 'TU-1 NM Movement'),
        ('_co_nm1_location', 'TU-1 NM Location '),
        ('_co_nm1_facility', 'TU-1 NM Facility Available'),
        ('_co_nm1_contributing_factor', 'TU-1 NM Human Contributing Factor '),
        ('_co_nm2_type', 'TU-2 NM Type'),
        ('_co_nm2_age', 'TU-2 NM Age '),
        ('_co_nm2_sex', 'TU-2 NM Sex '),
        ('_co_nm2_action', 'TU-2 NM Action '),
        ('_co_nm2_movement', 'TU-2 NM Movement'),
        ('_co_nm2_location', 'TU-2 NM Location '),
        ('_co_nm2_facility', 'TU-2 NM Facility Available'),
        ('_co_nm2_contributing_factor', 'TU-2 NM Human Contributing Factor '),
    ]

    def normalize_row(self, row: Dict[str, str]) -> Dict[str, str]:
        n = {}

        # --- ID ---
        n['Document Nbr'] = row.get('CUID', '').strip()

        # --- Date/Time ---
        raw_date = row.get('Crash Date', '').strip()
        n['Crash Date'] = raw_date
        n['Crash Year'] = self._extract_year(raw_date)
        mil_time = row.get('Crash Time', '').replace(':', '').strip()[:4]
        n['Crash Military Time'] = mil_time

        # --- Severity (derived from injury counts) ---
        inj_k = self._int(row.get('Injury 04', '0'))
        inj_a = self._int(row.get('Injury 03', '0'))
        inj_b = self._int(row.get('Injury 02', '0'))
        inj_c = self._int(row.get('Injury 01', '0'))

        if inj_k > 0:
            n['Crash Severity'] = 'K'
        elif inj_a > 0:
            n['Crash Severity'] = 'A'
        elif inj_b > 0:
            n['Crash Severity'] = 'B'
        elif inj_c > 0:
            n['Crash Severity'] = 'C'
        else:
            n['Crash Severity'] = 'O'

        n['K_People'] = str(inj_k)
        n['A_People'] = str(inj_a)
        n['B_People'] = str(inj_b)
        n['C_People'] = str(inj_c)

        # --- Collision Type (two-step: CO raw → category → VDOT numbered) ---
        crash_type = row.get('Crash Type', '').strip() or row.get('MHE', '').strip()
        intermediate = self.COLLISION_MAP.get(crash_type, crash_type or 'Unknown')
        n['Collision Type'] = self.COLLISION_VDOT_MAP.get(intermediate, '16. Other')

        # --- Weather Condition (VDOT numbered format) ---
        raw_weather = row.get('Weather Condition', '').strip()
        n['Weather Condition'] = self.WEATHER_VDOT_MAP.get(raw_weather, raw_weather)

        # --- Light Condition (VDOT numbered format + Dawn/Dusk split by time) ---
        raw_light = row.get('Lighting Conditions', '').strip()
        mapped_light = self.LIGHT_VDOT_MAP.get(raw_light, raw_light)
        if mapped_light == '1. Dawn' and mil_time:
            try:
                if int(mil_time) >= 1200:
                    mapped_light = '3. Dusk'
            except ValueError:
                pass
        n['Light Condition'] = mapped_light

        # --- Roadway Surface Condition (VDOT numbered format) ---
        raw_surface = row.get('Road Condition', '').strip()
        n['Roadway Surface Condition'] = self.SURFACE_VDOT_MAP.get(raw_surface, raw_surface)

        # --- Roadway Alignment (VDOT 4-category system) ---
        n['Roadway Alignment'] = self._map_alignment(
            row.get('Road Contour Curves', '').strip(),
            row.get('Road Contour Grade', '').strip()
        )

        # --- Road Description / Intersection / Relation To Roadway ---
        # CO "Road Description" is actually intersection relation, NOT road geometry
        road_desc = row.get('Road Description', '').strip()
        system = row.get('System Code', '').strip()

        # Roadway Description = road geometry (derived from system code)
        n['Roadway Description'] = self.ROAD_DESC_FROM_SYSTEM.get(
            system, '1. Two-Way, Not Divided')

        # Intersection Type = VDOT approach-count format (derived from CO Road Description)
        n['Intersection Type'] = self.INTERSECTION_VDOT_MAP.get(
            road_desc, '1. Not at Intersection')

        # Relation To Roadway = VDOT location relationship (from CO Road Description)
        n['Relation To Roadway'] = self.RELATION_TO_ROADWAY_MAP.get(road_desc, road_desc)

        # --- Route & Location ---
        n['RTE Name'] = self._build_route_name(row)
        n['SYSTEM'] = self.ROAD_SYSTEM_MAP.get(system, 'NonVDOT secondary')
        n['Node'] = self._build_node_id(row)
        n['RNS MP'] = row.get('Rd_Section', '').strip() if system in (
            'State Highway', 'Interstate Highway'
        ) else ''

        # --- Coordinates (x=longitude, y=latitude per Virginia convention) ---
        n['x'] = row.get('Longitude', '').strip()
        n['y'] = row.get('Latitude', '').strip()

        # --- Jurisdiction ---
        n['Physical Juris Name'] = row.get('County', '').strip()

        # --- Boolean flags (derived) ---
        n['Pedestrian?'] = 'Yes' if self._check_pedestrian(row) else 'No'
        n['Bike?'] = 'Yes' if self._check_bicycle(row) else 'No'
        n['Alcohol?'] = 'Yes' if self._check_alcohol(row) else 'No'
        n['Speed?'] = 'Yes' if self._check_speed(row) else 'No'
        n['Hitrun?'] = 'Yes' if self._check_hitrun(row) else 'No'
        n['Motorcycle?'] = 'Yes' if self._check_vehicle_type(row, 'Motorcycle') else 'No'
        n['Night?'] = 'Yes' if self._is_nighttime(row.get('Lighting Conditions', '')) else 'No'
        n['Distracted?'] = 'Yes' if self._check_distracted(row) else 'No'
        n['Drowsy?'] = 'Yes' if self._check_drowsy(row) else 'No'
        n['Drug Related?'] = 'Yes' if self._check_drugs(row) else 'No'
        n['Young?'] = 'Yes' if self._check_age(row, 16, 20) else 'No'
        n['Senior?'] = 'Yes' if self._check_age(row, 65, 999) else 'No'
        n['Unrestrained?'] = 'Yes' if self._check_unrestrained(row) else 'No'
        n['School Zone'] = 'Yes' if row.get('School Zone', '').strip() in ('TRUE', 'True') else 'No'
        n['Work Zone Related'] = 'Yes' if row.get('Construction Zone', '').strip() in ('TRUE', 'True') else 'No'

        # --- Derived safety fields (for Safety Focus tab) ---
        n['Animal Related?'] = 'Yes' if self._check_animal(row) else 'No'
        n['Guardrail Related?'] = 'Yes' if self._check_guardrail(row) else 'No'
        n['Lgtruck?'] = 'Yes' if self._check_large_truck(row) else 'No'
        n['RoadDeparture Type'] = self._derive_road_departure_type(row)
        n['Intersection Analysis'] = self._derive_intersection_analysis(row)
        n['Max Speed Diff'] = self._calc_speed_diff(row)

        # --- Traffic Control (not available in CDOT data) ---
        n['Traffic Control Type'] = ''
        n['Traffic Control Status'] = ''

        # --- Infrastructure fields ---
        n['Functional Class'] = ''
        n['Area Type'] = ''
        n['Facility Type'] = ''
        n['Ownership'] = self.OWNERSHIP_FROM_SYSTEM.get(system, '')

        # --- First Harmful Event (VDOT numbered codes) ---
        raw_fhe = row.get('First HE', '').strip()
        n['First Harmful Event'] = self.FIRST_HE_VDOT_MAP.get(raw_fhe, raw_fhe)

        # --- First Harmful Event Location (VDOT numbered codes) ---
        raw_fhe_loc = row.get('Location', '').strip()
        n['First Harmful Event Loc'] = self.FIRST_HE_LOC_VDOT_MAP.get(
            raw_fhe_loc, raw_fhe_loc)

        # --- Vehicle Count ---
        n['Vehicle Count'] = row.get('Total Vehicles', '').strip()

        # --- Injury counts ---
        n['Persons Injured'] = row.get('Number Injured', '0').strip()

        # --- Pedestrians Killed/Injured (derived from NM data) ---
        pk, pi = self._derive_ped_killed_injured(row)
        n['Pedestrians Killed'] = str(pk)
        n['Pedestrians Injured'] = str(pi)

        # --- Source tracking ---
        n['_source_state'] = 'colorado'
        n['_co_system_code'] = system
        n['_co_agency_id'] = row.get('Agency Id', '').strip()
        n['_co_rd_number'] = row.get('Rd_Number', '').strip()
        n['_co_location1'] = row.get('Location 1', '').strip()
        n['_co_location2'] = row.get('Location 2', '').strip()
        n['_co_city'] = row.get('City', '').strip()

        # --- Colorado-specific detail columns ---
        for col_name, raw_col in self.CO_EXTRA_COLUMNS:
            n[col_name] = row.get(raw_col, '').strip()

        return n

    # --- Helpers ---

    def _int(self, val: str) -> int:
        try:
            return int(val.strip()) if val.strip() else 0
        except (ValueError, TypeError):
            return 0

    def _extract_year(self, date_str: str) -> str:
        if not date_str:
            return ''
        parts = date_str.split('/')
        if len(parts) == 3:
            return parts[2][:4]
        parts = date_str.split('-')
        if len(parts) == 3 and len(parts[0]) == 4:
            return parts[0]
        return ''

    def _build_route_name(self, row: Dict[str, str]) -> str:
        system = row.get('System Code', '').strip()
        rd_num = row.get('Rd_Number', '').strip()
        loc1 = row.get('Location 1', '').strip()

        if system == 'Interstate Highway':
            num = re.sub(r'^0+', '', rd_num).rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
            return f'I-{num}' if num else loc1 or f'I-{rd_num}'
        if system == 'State Highway':
            if loc1:
                return loc1
            num = re.sub(r'^0+', '', rd_num).rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
            return f'CO-{num}' if num else f'CO-{rd_num}'
        if system == 'Frontage Road':
            return f'{loc1} (Frontage)' if loc1 else f'Frontage Rd {rd_num}'
        return loc1 or f'Road {rd_num}'

    def _build_node_id(self, row: Dict[str, str]) -> str:
        rd = row.get('Road Description', '').strip()
        loc1 = row.get('Location 1', '').strip()
        loc2 = row.get('Location 2', '').strip()

        if rd in ('At Intersection', 'Intersection Related', 'Roundabout'):
            if loc1 and loc2:
                roads = sorted([loc1, loc2])
                return f'{roads[0]} & {roads[1]}'
        return ''

    def _map_alignment(self, curves: str, grade: str) -> str:
        """Map CO Road Contour fields to VDOT 4-category alignment."""
        # Only recognized curve values count (Unknown, empty, Straight do not)
        curve_values = {'Curve Right', 'Curve Left'}
        grade_values = {'Uphill', 'Downhill', 'Hill Crest'}
        has_curve = curves in curve_values
        has_grade = grade in grade_values
        if has_curve and has_grade:
            return '4. Grade - Curve'
        if has_curve:
            return '2. Curve - Level'
        if has_grade:
            return '3. Grade - Straight'
        return '1. Straight - Level'

    def _derive_ped_killed_injured(self, row: Dict[str, str]):
        """Derive pedestrian killed/injured from NM type + injury counts."""
        ped_killed = 0
        ped_injured = 0
        for tu in ['TU-1', 'TU-2']:
            nm_type = row.get(f'{tu} NM Type', '').strip()
            if 'Pedestrian' in nm_type:
                if self._int(row.get('Injury 04', '0')) > 0:
                    ped_killed = max(ped_killed, 1)
                if (self._int(row.get('Injury 03', '0')) > 0 or
                        self._int(row.get('Injury 02', '0')) > 0 or
                        self._int(row.get('Injury 01', '0')) > 0):
                    ped_injured = max(ped_injured, 1)
        return ped_killed, ped_injured

    def _check_nm_type(self, row: Dict[str, str], nm_type: str) -> bool:
        tu1 = row.get('TU-1 NM Type', '').strip()
        tu2 = row.get('TU-2 NM Type', '').strip()
        return nm_type in tu1 or nm_type in tu2

    def _check_pedestrian(self, row: Dict[str, str]) -> bool:
        if self._check_nm_type(row, 'Pedestrian'):
            return True
        ct = row.get('Crash Type', '').strip()
        mhe = row.get('MHE', '').strip()
        return ct in ('Pedestrian', 'School Age To/From School') or \
               mhe in ('Pedestrian', 'School Age To/From School')

    def _check_bicycle(self, row: Dict[str, str]) -> bool:
        if self._check_nm_type(row, 'Bicycle'):
            return True
        ct = row.get('Crash Type', '').strip()
        mhe = row.get('MHE', '').strip()
        return 'Bicycle' in ct or 'Bicycle' in mhe

    def _check_alcohol(self, row: Dict[str, str]) -> bool:
        tu1 = row.get('TU-1 Alcohol Suspected', '').strip()
        tu2 = row.get('TU-2 Alcohol Suspected', '').strip()
        return tu1 in self.ALCOHOL_POSITIVE or tu2 in self.ALCOHOL_POSITIVE

    def _check_speed(self, row: Dict[str, str]) -> bool:
        fields = [
            row.get('TU-1 Driver Action', '').strip(),
            row.get('TU-2 Driver Action', '').strip(),
            row.get('TU-1 Human Contributing Factor', '').strip(),
            row.get('TU-2 Human Contributing Factor', '').strip(),
        ]
        return any(f in self.SPEED_ACTIONS for f in fields)

    def _check_hitrun(self, row: Dict[str, str]) -> bool:
        tu1 = row.get('TU-1 Hit And Run', '').strip()
        tu2 = row.get('TU-2 Hit And Run', '').strip()
        return tu1 == 'TRUE' or tu2 == 'TRUE'

    def _check_vehicle_type(self, row: Dict[str, str], vtype: str) -> bool:
        tu1 = row.get('TU-1 Type', '').strip()
        tu2 = row.get('TU-2 Type', '').strip()
        return vtype in tu1 or vtype in tu2

    def _is_nighttime(self, lighting: str) -> bool:
        return lighting.strip() in self.DARKNESS_VALUES

    def _check_distracted(self, row: Dict[str, str]) -> bool:
        fields = [
            row.get('TU-1 Driver Action', '').strip(),
            row.get('TU-2 Driver Action', '').strip(),
            row.get('TU-1 Human Contributing Factor', '').strip(),
            row.get('TU-2 Human Contributing Factor', '').strip(),
        ]
        return any(
            any(d in f for d in self.DISTRACTED_VALUES)
            for f in fields if f
        )

    def _check_drowsy(self, row: Dict[str, str]) -> bool:
        tu1 = row.get('TU-1 Human Contributing Factor', '').strip()
        tu2 = row.get('TU-2 Human Contributing Factor', '').strip()
        return any(v in tu1 or v in tu2 for v in self.DROWSY_VALUES)

    def _check_drugs(self, row: Dict[str, str]) -> bool:
        fields = [
            row.get('TU-1  Marijuana Suspected', '').strip(),
            row.get('TU-2 Marijuana Suspected', '').strip(),
            row.get('TU-1 Other Drugs Suspected ', '').strip(),
            row.get('TU-2 Other Drugs Suspected ', '').strip(),
        ]
        return any(f in self.DRUG_POSITIVE for f in fields)

    def _check_age(self, row: Dict[str, str], min_age: int, max_age: int) -> bool:
        for col in ['TU-1 Age', 'TU-2 Age']:
            try:
                age = int(row.get(col, '0').strip())
                if min_age <= age <= max_age:
                    return True
            except (ValueError, TypeError):
                pass
        return False

    def _check_unrestrained(self, row: Dict[str, str]) -> bool:
        unrestrained = {'Not Used', 'Improperly Used'}
        tu1 = row.get('TU-1 Safety restraint Use', '').strip()
        tu2 = row.get('TU-2 Safety restraint Use', '').strip()
        return tu1 in unrestrained or tu2 in unrestrained

    def _check_animal(self, row: Dict[str, str]) -> bool:
        wild = row.get('Wild Animal', '').strip()
        if wild:
            return True
        ct = (row.get('Crash Type', '') or row.get('MHE', '')).strip()
        return ct in ('Wild Animal', 'Domestic Animal')

    def _check_guardrail(self, row: Dict[str, str]) -> bool:
        for f in ('MHE', 'Crash Type', 'First HE'):
            if 'Guardrail' in row.get(f, ''):
                return True
        return False

    def _check_large_truck(self, row: Dict[str, str]) -> bool:
        truck_keywords = ('Medium/Heavy Truck', 'Truck/Tractor', 'Truck Tractor',
                          'Semi-Trailer', 'Bus', 'Working Vehicle', 'Farm Equipment')
        tu1 = row.get('TU-1 Type', '').strip()
        tu2 = row.get('TU-2 Type', '').strip()
        return any(k in tu1 or k in tu2 for k in truck_keywords)

    def _derive_road_departure_type(self, row: Dict[str, str]) -> str:
        mhe = row.get('MHE', '').strip()
        first_he = row.get('First HE', '').strip()
        indicators = ('Tree', 'Utility Pole', 'Guard Rail', 'Guardrail', 'Fence',
                      'Embankment', 'Ditch', 'Concrete Highway Barrier', 'Cable Rail',
                      'Culvert', 'Overturning', 'Rollover', 'Large Rocks', 'Sign',
                      'Mailbox', 'Crash Cushion', 'Wall or Building', 'Barricade',
                      'Bridge Structure')
        if any(ind in mhe or ind in first_he for ind in indicators):
            return 'RD_UNKNOWN'
        return 'NOT_RD'

    def _derive_intersection_analysis(self, row: Dict[str, str]) -> str:
        rd = row.get('Road Description', '').strip()
        if rd in ('At Intersection', 'Intersection Related', 'Roundabout',
                  'Alley Related', 'Mid-Block Crosswalk'):
            return 'Urban Intersection'
        return 'Not Intersection'

    def _calc_speed_diff(self, row: Dict[str, str]) -> str:
        limit = self._int(row.get('TU-1 Speed Limit', ''))
        est = self._int(row.get('TU-1 Estimated Speed', ''))
        if limit > 0 and est > 0:
            return str(est - limit)
        return ''


# --- Normalizer Registry ---
_NORMALIZERS = {
    'colorado': ColoradoNormalizer,
    'virginia': VirginiaNormalizer,
}


def get_normalizer(state_key: str, config_path: Optional[str] = None) -> BaseNormalizer:
    """
    Get a normalizer instance for the given state.

    Args:
        state_key: State identifier (e.g., 'colorado', 'virginia')
        config_path: Optional path to state config JSON

    Returns:
        BaseNormalizer subclass instance
    """
    if not config_path:
        states_dir = Path(__file__).parent.parent / 'states'
        sig = STATE_SIGNATURES.get(state_key, {})
        config_dir = sig.get('config_dir', state_key)
        config_path = str(states_dir / config_dir / 'config.json')

    cls = _NORMALIZERS.get(state_key)
    if not cls:
        raise ValueError(
            f"No normalizer for state '{state_key}'. "
            f"Available: {', '.join(_NORMALIZERS.keys())}"
        )
    return cls(state_key, config_path)


def get_supported_states() -> Dict[str, str]:
    """Return dict of state_key -> display_name for all supported states."""
    return {k: v['display_name'] for k, v in STATE_SIGNATURES.items()}


def convert_file(
    input_path: str,
    output_path: str,
    state: Optional[str] = None,
    source_filename: Optional[str] = None,
) -> Tuple[str, int, int]:
    """
    Convert a raw crash data CSV to standardized format.

    Args:
        input_path: Path to raw CSV
        output_path: Path for standardized output CSV
        state: State key (auto-detected if None)
        source_filename: Original filename for tracking

    Returns:
        Tuple of (detected_state, total_rows, rows_with_gps)
    """
    detector = StateDetector()

    # Auto-detect state if not specified
    if not state:
        state = detector.detect_from_file(input_path)
        if state == 'unknown':
            raise ValueError(
                f"Could not auto-detect state from {input_path}. "
                f"Please specify --state explicitly."
            )

    normalizer = get_normalizer(state)
    src_name = source_filename or os.path.basename(input_path)

    total = 0
    with_gps = 0

    with open(input_path, 'r', encoding='utf-8-sig') as fin:
        reader = csv.DictReader(fin)

        # Build output columns from first normalized row
        first_row = next(reader)
        normalized_first = normalizer.normalize_row(first_row)
        normalized_first['_source_file'] = src_name

        # Use all keys from normalized row as output columns
        output_cols = list(normalized_first.keys())

        with open(output_path, 'w', newline='', encoding='utf-8') as fout:
            writer = csv.DictWriter(fout, fieldnames=output_cols, extrasaction='ignore')
            writer.writeheader()

            # Write first row
            writer.writerow(normalized_first)
            total = 1
            if normalized_first.get('x') and normalized_first.get('y'):
                try:
                    float(normalized_first['x'])
                    float(normalized_first['y'])
                    with_gps += 1
                except ValueError:
                    pass

            # Process remaining rows
            for row in reader:
                normalized = normalizer.normalize_row(row)
                normalized['_source_file'] = src_name
                writer.writerow(normalized)
                total += 1

                if normalized.get('x') and normalized.get('y'):
                    try:
                        float(normalized['x'])
                        float(normalized['y'])
                        with_gps += 1
                    except ValueError:
                        pass

    return state, total, with_gps
