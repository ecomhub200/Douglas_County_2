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
    'Document Nbr', 'Crash Year', 'Crash Date', 'Crash Military Time',
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
    """Colorado CDOT data normalizer - converts to Virginia-compatible format."""

    # Collision type mapping (Colorado → standardized)
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

    ROAD_SYSTEM_MAP = {
        'City Street': 'NonVDOT secondary',
        'County Road': 'NonVDOT secondary',
        'State Highway': 'Primary',
        'Interstate Highway': 'Interstate',
        'Frontage Road': 'Secondary',
        'Non Crash': 'NonVDOT secondary',
    }

    INTERSECTION_MAP = {
        'Non-Intersection': 'Non-Intersection',
        'At Intersection': 'Intersection',
        'Intersection Related': 'Intersection',
        'Driveway Access Related': 'Driveway',
        'Ramp': 'Ramp', 'Ramp-related': 'Ramp',
        'Roundabout': 'Roundabout',
        'Express/Managed/HOV Lane': 'Non-Intersection',
        'Crossover-Related ': 'Intersection',
        'Auxiliary Lane': 'Non-Intersection',
        'Alley Related': 'Intersection',
        'Railroad Crossing Related': 'Railroad Crossing',
        'Mid-Block Crosswalk': 'Intersection',
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
        'Dark – Lighted', 'Dark – Unlighted',
        'Dark - Lighted', 'Dark - Unlighted'
    }

    def normalize_row(self, row: Dict[str, str]) -> Dict[str, str]:
        n = {}

        # --- ID ---
        n['Document Nbr'] = row.get('CUID', '').strip()

        # --- Date/Time ---
        raw_date = row.get('Crash Date', '').strip()
        n['Crash Date'] = raw_date
        n['Crash Year'] = self._extract_year(raw_date)
        n['Crash Military Time'] = row.get('Crash Time', '').replace(':', '').strip()[:4]

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

        # --- Collision Type ---
        crash_type = row.get('Crash Type', '').strip() or row.get('MHE', '').strip()
        n['Collision Type'] = self.COLLISION_MAP.get(crash_type, crash_type or 'Unknown')

        # --- Conditions ---
        n['Weather Condition'] = row.get('Weather Condition', '').strip()
        n['Light Condition'] = row.get('Lighting Conditions', '').strip()
        n['Roadway Surface Condition'] = row.get('Road Condition', '').strip()
        n['Roadway Alignment'] = self._map_alignment(
            row.get('Road Contour Curves', '').strip(),
            row.get('Road Contour Grade', '').strip()
        )

        # --- Road Description / Intersection ---
        road_desc = row.get('Road Description', '').strip()
        n['Roadway Description'] = road_desc
        n['Intersection Type'] = self.INTERSECTION_MAP.get(road_desc, road_desc or 'Unknown')

        # --- Route & Location ---
        n['RTE Name'] = self._build_route_name(row)
        n['SYSTEM'] = self.ROAD_SYSTEM_MAP.get(
            row.get('System Code', '').strip(), 'NonVDOT secondary'
        )
        n['Node'] = self._build_node_id(row)
        system = row.get('System Code', '').strip()
        n['RNS MP'] = row.get('Rd_Section', '').strip() if system in (
            'State Highway', 'Interstate Highway'
        ) else ''

        # --- Coordinates (x=longitude, y=latitude per Virginia convention) ---
        lat_str = row.get('Latitude', '').strip()
        lon_str = row.get('Longitude', '').strip()
        n['x'] = lon_str  # longitude
        n['y'] = lat_str  # latitude

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

        # --- Traffic Control (not in CDOT data) ---
        n['Traffic Control Type'] = ''
        n['Traffic Control Status'] = ''

        # --- Other fields ---
        n['Functional Class'] = ''
        n['Area Type'] = ''
        n['Facility Type'] = ''
        n['Ownership'] = ''
        n['First Harmful Event'] = row.get('First HE', '').strip()
        n['First Harmful Event Loc'] = row.get('Location', '').strip()
        n['Persons Injured'] = row.get('Number Injured', '0').strip()
        n['Pedestrians Killed'] = ''
        n['Pedestrians Injured'] = ''

        # --- Source tracking ---
        n['_source_state'] = 'colorado'
        # Preserve key original Colorado columns
        n['_co_system_code'] = row.get('System Code', '').strip()
        n['_co_agency_id'] = row.get('Agency Id', '').strip()
        n['_co_rd_number'] = row.get('Rd_Number', '').strip()
        n['_co_location1'] = row.get('Location 1', '').strip()
        n['_co_location2'] = row.get('Location 2', '').strip()
        n['_co_city'] = row.get('City', '').strip()

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
        # Try M/D/YYYY
        parts = date_str.split('/')
        if len(parts) == 3:
            return parts[2][:4]
        # Try YYYY-MM-DD
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
        parts = []
        if curves and curves != 'Straight':
            parts.append(curves)
        if grade and grade != 'Level':
            parts.append(grade)
        return ', '.join(parts) if parts else 'Straight/Level'

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
