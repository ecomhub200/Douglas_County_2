#!/usr/bin/env python3
"""
Virginia Crash Data Validation System - Main Entry Point

This script orchestrates the validation and auto-correction of Virginia crash data
for all 133 jurisdictions with support for incremental processing.

Usage:
    python run_validation.py                                    # Default jurisdiction
    python run_validation.py --jurisdiction henrico             # Specific jurisdiction
    python run_validation.py --jurisdiction henrico --full      # Force full re-validation
    python run_validation.py --all                              # All jurisdictions
    python run_validation.py --dry-run                          # Preview without changes

Author: CRASH LENS Team
Version: 1.0.0
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from dateutil import parser as date_parser
from tqdm import tqdm

# Spatial processing imports (optional - only if modules exist)
try:
    from validation.utils.spatial_validator import CrashSpatialProcessor
    SPATIAL_AVAILABLE = True
except ImportError:
    try:
        from utils.spatial_validator import CrashSpatialProcessor
        SPATIAL_AVAILABLE = True
    except ImportError:
        SPATIAL_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Script directory
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Paths
CONFIG_PATH = PROJECT_ROOT / "config.json"
DATA_DIR = PROJECT_ROOT / "data"
VALIDATION_DIR = DATA_DIR / ".validation"
REFERENCE_DIR = SCRIPT_DIR / "reference"

# Reference data files
VALID_VALUES_FILE = REFERENCE_DIR / "virginia_valid_values.json"
CORRECTION_RULES_FILE = REFERENCE_DIR / "correction_rules.json"


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


class CrashDataValidator:
    """Main validator class for Virginia crash data."""

    def __init__(self, jurisdiction: str, config: dict):
        self.jurisdiction = jurisdiction
        self.config = config
        self.jurisdiction_config = config.get('jurisdictions', {}).get(jurisdiction, {})

        # Load reference data
        self.valid_values = self._load_json(VALID_VALUES_FILE)
        self.correction_rules = self._load_json(CORRECTION_RULES_FILE)

        # Validation results
        self.issues = []
        self.corrections = []
        self.stats = {
            'total_records': 0,
            'new_records': 0,
            'validated': 0,
            'auto_corrected': 0,
            'flagged': 0,
            'errors': 0
        }

    def _load_json(self, path: Path) -> dict:
        """Load JSON file."""
        if not path.exists():
            logger.warning(f"Reference file not found: {path}")
            return {}
        with open(path, 'r') as f:
            return json.load(f)

    def get_jurisdiction_bounds(self) -> Optional[Dict]:
        """Get bounding box for jurisdiction."""
        bbox = self.jurisdiction_config.get('bbox')
        if bbox and len(bbox) == 4:
            return {
                'minLon': bbox[0],
                'minLat': bbox[1],
                'maxLon': bbox[2],
                'maxLat': bbox[3]
            }
        return None

    def validate_record(self, record: pd.Series, row_idx: int) -> Tuple[List[dict], List[dict]]:
        """
        Validate a single record.

        Returns:
            Tuple of (issues, corrections)
        """
        issues = []
        corrections = []

        # Get Document Nbr for tracking
        doc_nbr = str(record.get('Document Nbr', '')).strip()

        # 1. Schema validation
        issues.extend(self._validate_schema(record, row_idx, doc_nbr))

        # 2. Bounds validation
        issues.extend(self._validate_bounds(record, row_idx, doc_nbr))

        # 3. Category validation
        cat_issues, cat_corrections = self._validate_categories(record, row_idx, doc_nbr)
        issues.extend(cat_issues)
        corrections.extend(cat_corrections)

        # 4. Consistency validation
        con_issues, con_corrections = self._validate_consistency(record, row_idx, doc_nbr)
        issues.extend(con_issues)
        corrections.extend(con_corrections)

        # 5. Completeness validation
        issues.extend(self._validate_completeness(record, row_idx, doc_nbr))

        return issues, corrections

    def _validate_schema(self, record: pd.Series, row_idx: int, doc_nbr: str) -> List[dict]:
        """Validate data types and required fields."""
        issues = []

        # Check Document Nbr
        if pd.isna(record.get('Document Nbr', '')) or doc_nbr == '':
            issues.append({
                'row': row_idx,
                'document_nbr': doc_nbr or f'row_{row_idx}',
                'field': 'Document Nbr',
                'issue': 'missing_required',
                'severity': 'error',
                'message': 'Document Nbr is required'
            })

        # Check Crash Year
        crash_year = record.get('Crash Year')
        if pd.notna(crash_year):
            try:
                year = int(crash_year)
                current_year = datetime.now().year
                if year < 2015 or year > current_year:
                    issues.append({
                        'row': row_idx,
                        'document_nbr': doc_nbr or f'row_{row_idx}',
                        'field': 'Crash Year',
                        'issue': 'out_of_range',
                        'severity': 'error',
                        'value': year,
                        'message': f'Crash Year {year} outside valid range (2015-{current_year})'
                    })
            except (ValueError, TypeError):
                issues.append({
                    'row': row_idx,
                    'document_nbr': doc_nbr or f'row_{row_idx}',
                    'field': 'Crash Year',
                    'issue': 'invalid_type',
                    'severity': 'error',
                    'value': crash_year,
                    'message': 'Crash Year must be an integer'
                })

        # Check Severity - also check for corrections
        severity_raw = str(record.get('Crash Severity', '')).strip()
        severity = severity_raw.upper()
        valid_severities = self.valid_values.get('severity', {}).get('valid', ['K', 'A', 'B', 'C', 'O'])
        if severity_raw and severity not in valid_severities:
            # Check for correction rule
            sev_corrections = self.correction_rules.get('categoryCorrections', {}).get('Crash Severity', {})
            if severity_raw in sev_corrections:
                rule = sev_corrections[severity_raw]
                # Will be handled in _validate_categories
                pass
            else:
                issues.append({
                    'row': row_idx,
                    'document_nbr': doc_nbr or f'row_{row_idx}',
                    'field': 'Crash Severity',
                    'issue': 'invalid_value',
                    'severity': 'error',
                    'value': severity_raw,
                    'message': f'Invalid severity: {severity_raw}'
                })

        # Check Crash Date format
        crash_date = record.get('Crash Date')
        if pd.notna(crash_date) and str(crash_date).strip():
            date_str = str(crash_date).strip()
            valid_date = False
            try:
                # Try common formats
                parsed_date = date_parser.parse(date_str)
                valid_date = True

                # Check date is not in the future
                if parsed_date.date() > datetime.now().date():
                    issues.append({
                        'row': row_idx,
                        'document_nbr': doc_nbr or f'row_{row_idx}',
                        'field': 'Crash Date',
                        'issue': 'future_date',
                        'severity': 'error',
                        'value': date_str,
                        'message': f'Crash Date {date_str} is in the future'
                    })

                # Check date is not too old
                min_year = self.valid_values.get('dateConstraints', {}).get('minYear', 2015)
                if parsed_date.year < min_year:
                    issues.append({
                        'row': row_idx,
                        'document_nbr': doc_nbr or f'row_{row_idx}',
                        'field': 'Crash Date',
                        'issue': 'date_too_old',
                        'severity': 'warning',
                        'value': date_str,
                        'message': f'Crash Date {date_str} is before {min_year}'
                    })
            except (ValueError, TypeError):
                issues.append({
                    'row': row_idx,
                    'document_nbr': doc_nbr or f'row_{row_idx}',
                    'field': 'Crash Date',
                    'issue': 'invalid_date_format',
                    'severity': 'error',
                    'value': date_str,
                    'message': f'Invalid date format: {date_str}'
                })

        return issues

    def _validate_bounds(self, record: pd.Series, row_idx: int, doc_nbr: str) -> List[dict]:
        """Validate geographic coordinates."""
        issues = []

        x = record.get('x')
        y = record.get('y')

        # Skip if coordinates are missing
        if pd.isna(x) or pd.isna(y):
            return issues

        try:
            lon = float(x)
            lat = float(y)
        except (ValueError, TypeError):
            issues.append({
                'row': row_idx,
                'document_nbr': doc_nbr or f'row_{row_idx}',
                'field': 'coordinates',
                'issue': 'invalid_type',
                'severity': 'error',
                'message': 'Coordinates must be numeric'
            })
            return issues

        # Check for transposed lat/lon (latitude in longitude range)
        state_bounds = self.valid_values.get('stateBounds', {}).get('virginia', {})
        if state_bounds:
            # Check if lat/lon might be swapped
            if (state_bounds.get('minLat', 36) <= lon <= state_bounds.get('maxLat', 40) and
                state_bounds.get('minLon', -84) <= lat <= state_bounds.get('maxLon', -75)):
                issues.append({
                    'row': row_idx,
                    'document_nbr': doc_nbr or f'row_{row_idx}',
                    'field': 'coordinates',
                    'issue': 'transposed_lat_lon',
                    'severity': 'warning',
                    'value': f'x={lon}, y={lat}',
                    'message': 'Latitude and longitude may be transposed'
                })

            if not (state_bounds.get('minLon', -84) <= lon <= state_bounds.get('maxLon', -75)):
                issues.append({
                    'row': row_idx,
                    'document_nbr': doc_nbr or f'row_{row_idx}',
                    'field': 'x',
                    'issue': 'outside_state_bounds',
                    'severity': 'error',
                    'value': lon,
                    'message': f'Longitude {lon} outside Virginia bounds'
                })

            if not (state_bounds.get('minLat', 36) <= lat <= state_bounds.get('maxLat', 40)):
                issues.append({
                    'row': row_idx,
                    'document_nbr': doc_nbr or f'row_{row_idx}',
                    'field': 'y',
                    'issue': 'outside_state_bounds',
                    'severity': 'error',
                    'value': lat,
                    'message': f'Latitude {lat} outside Virginia bounds'
                })

        # Check jurisdiction bounds (boundary crashes - info level, not flagged)
        juris_bounds = self.get_jurisdiction_bounds()
        if juris_bounds:
            if not (juris_bounds['minLon'] <= lon <= juris_bounds['maxLon']):
                issues.append({
                    'row': row_idx,
                    'document_nbr': doc_nbr or f'row_{row_idx}',
                    'field': 'x',
                    'issue': 'boundary_warning',
                    'severity': 'info',
                    'value': lon,
                    'message': f'Longitude {lon} outside {self.jurisdiction} bounds (boundary crash)'
                })

            if not (juris_bounds['minLat'] <= lat <= juris_bounds['maxLat']):
                issues.append({
                    'row': row_idx,
                    'document_nbr': doc_nbr or f'row_{row_idx}',
                    'field': 'y',
                    'issue': 'boundary_warning',
                    'severity': 'info',
                    'value': lat,
                    'message': f'Latitude {lat} outside {self.jurisdiction} bounds (boundary crash)'
                })

        return issues

    def _validate_categories(self, record: pd.Series, row_idx: int, doc_nbr: str) -> Tuple[List[dict], List[dict]]:
        """Validate category fields against valid values."""
        issues = []
        corrections = []

        category_fields = {
            'Collision Type': 'collisionTypes',
            'Weather Condition': 'weatherConditions',
            'Light Condition': 'lightConditions',
            'Roadway Surface Condition': 'surfaceConditions',
            'Intersection Type': 'intersectionTypes',
            'Traffic Control Type': 'trafficControlTypes',
            'Crash Severity': 'severity'
        }

        for field, ref_key in category_fields.items():
            value = str(record.get(field, '')).strip()
            if not value:
                continue

            valid_values = self.valid_values.get(ref_key, {}).get('valid', [])
            if value not in valid_values:
                # Check for correction rule
                field_corrections = self.correction_rules.get('categoryCorrections', {}).get(field, {})
                if value in field_corrections:
                    rule = field_corrections[value]
                    confidence = rule.get('confidence', 0)

                    if rule.get('correctTo') and confidence >= 85:
                        corrections.append({
                            'row': row_idx,
                            'document_nbr': doc_nbr or f'row_{row_idx}',
                            'field': field,
                            'original': value,
                            'corrected': rule['correctTo'],
                            'confidence': confidence,
                            'reason': rule.get('reason', 'Correction rule applied'),
                            'auto_applied': True
                        })
                    else:
                        issues.append({
                            'row': row_idx,
                            'document_nbr': doc_nbr or f'row_{row_idx}',
                            'field': field,
                            'issue': 'invalid_category',
                            'severity': 'warning',
                            'value': value,
                            'suggestion': rule.get('correctTo'),
                            'confidence': confidence,
                            'message': f'Invalid {field}: {value}'
                        })
                else:
                    issues.append({
                        'row': row_idx,
                        'document_nbr': doc_nbr or f'row_{row_idx}',
                        'field': field,
                        'issue': 'unknown_category',
                        'severity': 'warning',
                        'value': value,
                        'message': f'Unknown {field}: {value}'
                    })

        return issues, corrections

    def _validate_consistency(self, record: pd.Series, row_idx: int, doc_nbr: str) -> Tuple[List[dict], List[dict]]:
        """Validate cross-field consistency."""
        issues = []
        corrections = []

        # Check: Fatal severity should have K_People > 0
        severity = str(record.get('Crash Severity', '')).strip().upper()
        k_people = record.get('K_People', 0)
        try:
            k_people = int(k_people) if pd.notna(k_people) else 0
        except (ValueError, TypeError):
            k_people = 0

        if severity == 'K' and k_people == 0:
            issues.append({
                'row': row_idx,
                'document_nbr': doc_nbr or f'row_{row_idx}',
                'field': 'K_People',
                'issue': 'severity_mismatch',
                'severity': 'error',
                'value': k_people,
                'message': 'Fatal crash (K) should have K_People > 0'
            })

        # Check: Serious injury (A) should have A_People > 0 or injuries
        a_people = record.get('A_People', 0)
        try:
            a_people = int(a_people) if pd.notna(a_people) else 0
        except (ValueError, TypeError):
            a_people = 0

        if severity == 'A' and a_people == 0:
            issues.append({
                'row': row_idx,
                'document_nbr': doc_nbr or f'row_{row_idx}',
                'field': 'A_People',
                'issue': 'severity_mismatch',
                'severity': 'warning',
                'value': a_people,
                'message': 'Serious injury crash (A) should have A_People > 0'
            })

        # Check: Pedestrian collision should have Pedestrian? = Yes
        collision_type = str(record.get('Collision Type', '')).strip()
        ped_flag = str(record.get('Pedestrian?', '')).strip()

        if collision_type == '12. Ped' and ped_flag != 'Yes':
            corrections.append({
                'row': row_idx,
                'document_nbr': doc_nbr or f'row_{row_idx}',
                'field': 'Pedestrian?',
                'original': ped_flag,
                'corrected': 'Yes',
                'confidence': 98,
                'reason': 'Pedestrian collision should have Pedestrian flag = Yes',
                'auto_applied': True
            })

        # Check: Bicycle collision should have Bike? = Yes
        bike_flag = str(record.get('Bike?', '')).strip()

        if collision_type == '13. Bicyclist' and bike_flag != 'Yes':
            corrections.append({
                'row': row_idx,
                'document_nbr': doc_nbr or f'row_{row_idx}',
                'field': 'Bike?',
                'original': bike_flag,
                'corrected': 'Yes',
                'confidence': 98,
                'reason': 'Bicycle collision should have Bike flag = Yes',
                'auto_applied': True
            })

        # Check: Motorcycle collision should have Motorcycle? = Yes
        motorcycle_flag = str(record.get('Motorcycle?', '')).strip()

        if collision_type == '14. Motorcyclist' and motorcycle_flag != 'Yes':
            corrections.append({
                'row': row_idx,
                'document_nbr': doc_nbr or f'row_{row_idx}',
                'field': 'Motorcycle?',
                'original': motorcycle_flag,
                'corrected': 'Yes',
                'confidence': 98,
                'reason': 'Motorcycle collision should have Motorcycle flag = Yes',
                'auto_applied': True
            })

        # Check: Darkness should have Night? = Yes
        light_condition = str(record.get('Light Condition', '')).strip()
        night_flag = str(record.get('Night?', '')).strip()
        darkness_values = [
            '4. Darkness - Road Lighted',
            '5. Darkness - Road Not Lighted',
            '6. Darkness - Unknown Road Lighting'
        ]

        if light_condition in darkness_values and night_flag != 'Yes':
            corrections.append({
                'row': row_idx,
                'document_nbr': doc_nbr or f'row_{row_idx}',
                'field': 'Night?',
                'original': night_flag,
                'corrected': 'Yes',
                'confidence': 95,
                'reason': 'Darkness light condition should have Night flag = Yes',
                'auto_applied': True
            })

        return issues, corrections

    def _validate_completeness(self, record: pd.Series, row_idx: int, doc_nbr: str) -> List[dict]:
        """Check for missing required/preferred fields."""
        issues = []

        # Required fields
        required_fields = ['Document Nbr', 'Crash Year', 'Crash Date', 'Crash Severity']
        for field in required_fields:
            value = record.get(field)
            if pd.isna(value) or str(value).strip() == '':
                issues.append({
                    'row': row_idx,
                    'document_nbr': doc_nbr or f'row_{row_idx}',
                    'field': field,
                    'issue': 'missing_required',
                    'severity': 'error',
                    'message': f'Required field {field} is missing'
                })

        # Preferred fields (info level)
        preferred_fields = ['x', 'y', 'RTE Name', 'Collision Type']
        for field in preferred_fields:
            value = record.get(field)
            if pd.isna(value) or str(value).strip() == '':
                issues.append({
                    'row': row_idx,
                    'document_nbr': doc_nbr or f'row_{row_idx}',
                    'field': field,
                    'issue': 'missing_preferred',
                    'severity': 'info',
                    'message': f'Preferred field {field} is missing'
                })

        return issues

    def _validate_duplicates(self, df: pd.DataFrame) -> Tuple[List[dict], List[int]]:
        """
        Check for and auto-deduplicate records.

        Auto-deduplicates when: same date + same GPS coordinates + same collision type.
        Note: Same Document Nbr alone is NOT treated as duplicate (could be data entry issue).

        Returns:
            Tuple of (issues list, indices to remove for deduplication)
        """
        issues = []
        indices_to_remove = []

        # Auto-deduplicate: same date + same GPS + same collision type (description)
        dup_cols = ['Crash Date', 'x', 'y', 'Collision Type']
        existing_cols = [c for c in dup_cols if c in df.columns]

        if len(existing_cols) >= 3 and 'x' in existing_cols and 'y' in existing_cols:
            df_clean = df.dropna(subset=['x', 'y'])  # Only check records with coordinates
            if len(df_clean) > 0:
                duplicates = df_clean[df_clean.duplicated(subset=existing_cols, keep=False)]
                if len(duplicates) > 0:
                    dup_groups = duplicates.groupby(existing_cols).groups
                    for group_key, indices in dup_groups.items():
                        if len(indices) > 1:
                            # Keep first occurrence, remove the rest
                            indices_list = list(indices)
                            for idx in indices_list[1:]:
                                doc_nbr = str(df.at[idx, 'Document Nbr']) if 'Document Nbr' in df.columns else f'row_{idx}'
                                issues.append({
                                    'row': idx,
                                    'document_nbr': doc_nbr,
                                    'field': 'multiple',
                                    'issue': 'auto_deduplicated',
                                    'severity': 'info',
                                    'message': f'Auto-removed duplicate (same date, location, collision type as record {indices_list[0]})'
                                })
                                indices_to_remove.append(idx)

        return issues, indices_to_remove

    def validate_dataframe(self, df: pd.DataFrame, incremental: bool = True,
                           validated_ids: Optional[set] = None) -> pd.DataFrame:
        """
        Validate entire dataframe.

        Args:
            df: DataFrame to validate
            incremental: If True, only validate new records
            validated_ids: Set of previously validated Document Numbers

        Returns:
            Corrected DataFrame
        """
        self.stats['total_records'] = len(df)

        # Preprocess: Apply format corrections to entire dataframe
        df = self._apply_format_corrections(df)

        if incremental and validated_ids:
            # Filter to new records only
            new_mask = ~df['Document Nbr'].isin(validated_ids)
            new_df = df[new_mask].copy()
            existing_df = df[~new_mask].copy()
            self.stats['new_records'] = len(new_df)
            logger.info(f"Incremental mode: validating {len(new_df)} new records "
                        f"(skipping {len(existing_df)} previously validated)")
        else:
            new_df = df.copy()
            existing_df = pd.DataFrame()
            self.stats['new_records'] = len(new_df)
            logger.info(f"Full validation mode: validating all {len(new_df)} records")

        if len(new_df) == 0:
            logger.info("No new records to validate")
            return df

        # Check for duplicates and auto-deduplicate
        duplicate_issues, indices_to_remove = self._validate_duplicates(new_df)

        # Remove duplicates from dataframe
        if indices_to_remove:
            logger.info(f"Auto-deduplicating {len(indices_to_remove)} duplicate records")
            new_df = new_df.drop(index=indices_to_remove)

        # Validate each record
        all_issues = list(duplicate_issues)  # Start with duplicate issues
        all_corrections = []

        for idx, row in tqdm(new_df.iterrows(), total=len(new_df), desc="Validating"):
            issues, corrections = self.validate_record(row, idx)
            all_issues.extend(issues)
            all_corrections.extend(corrections)

        self.issues = all_issues
        self.corrections = all_corrections

        # Apply corrections
        corrected_df = self._apply_corrections(new_df, all_corrections)

        # Update stats - count unique RECORDS with issues, not total issues
        self.stats['validated'] = len(new_df)
        self.stats['auto_corrected'] = len([c for c in all_corrections if c.get('auto_applied')])
        self.stats['deduplicated'] = len(indices_to_remove)

        # Count unique records with errors/warnings (not total issues)
        flagged_records = set()
        error_records = set()
        for issue in all_issues:
            record_key = issue.get('document_nbr', f"row_{issue.get('row', 0)}")
            if issue['severity'] in ['error', 'warning']:
                flagged_records.add(record_key)
            if issue['severity'] == 'error':
                error_records.add(record_key)

        self.stats['flagged'] = len(flagged_records)
        self.stats['errors'] = len(error_records)
        self.stats['total_issues'] = len([i for i in all_issues if i['severity'] in ['error', 'warning']])
        self.stats['duplicates'] = len([i for i in all_issues if 'duplicate' in i.get('issue', '') or 'dedup' in i.get('issue', '')])

        # Merge with existing validated data
        if len(existing_df) > 0:
            final_df = pd.concat([existing_df, corrected_df], ignore_index=True)
        else:
            final_df = corrected_df

        return final_df

    def _apply_format_corrections(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply format corrections to all records (whitespace, quotes, booleans)."""
        df = df.copy()

        # Trim whitespace from all string columns
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
            # Replace 'nan' string with empty string
            df[col] = df[col].replace('nan', '')

        # Remove enclosing quotes
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].str.replace(r'^["\']|["\']$', '', regex=True)

        # Normalize boolean fields
        boolean_fields = self.valid_values.get('booleanFields', {}).get('fieldNames', [])
        bool_mappings = {
            'Y': 'Yes', 'N': 'No',
            '1': 'Yes', '0': 'No',
            'TRUE': 'Yes', 'FALSE': 'No',
            'true': 'Yes', 'false': 'No',
            'yes': 'Yes', 'no': 'No'
        }
        for field in boolean_fields:
            if field in df.columns:
                df[field] = df[field].replace(bool_mappings)

        # Uppercase severity
        if 'Crash Severity' in df.columns:
            df['Crash Severity'] = df['Crash Severity'].str.upper()

        # Ensure injury counts are integers
        injury_cols = ['K_People', 'A_People', 'B_People', 'C_People', 'Persons Injured',
                       'Pedestrians Killed', 'Pedestrians Injured']
        for col in injury_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

        return df

    def _apply_corrections(self, df: pd.DataFrame, corrections: List[dict]) -> pd.DataFrame:
        """Apply auto-corrections to dataframe."""
        df = df.copy()

        for correction in corrections:
            if correction.get('auto_applied'):
                row_idx = correction['row']
                field = correction['field']
                new_value = correction['corrected']

                if row_idx in df.index:
                    df.at[row_idx, field] = new_value
                    logger.debug(f"Applied correction: row {row_idx}, "
                                 f"{field}: {correction['original']} -> {new_value}")

        return df

    def get_report(self) -> dict:
        """Generate validation report."""
        deduplicated = self.stats.get('deduplicated', 0)
        total_issues = self.stats.get('total_issues', 0)
        clean_records = self.stats['validated'] - self.stats['flagged']
        clean_rate = round((clean_records / max(self.stats['new_records'], 1)) * 100, 2)

        summary_parts = [f"Validated {self.stats['new_records']} records"]
        if deduplicated > 0:
            summary_parts.append(f"{deduplicated} duplicates removed")
        summary_parts.append(f"{clean_records} clean ({clean_rate}%)")
        if self.stats['flagged'] > 0:
            summary_parts.append(f"{self.stats['flagged']} flagged")
        if self.stats['auto_corrected'] > 0:
            summary_parts.append(f"{self.stats['auto_corrected']} auto-corrected")

        return {
            'metadata': {
                'generatedAt': datetime.utcnow().isoformat() + 'Z',
                'jurisdiction': self.jurisdiction,
                'validationVersion': '1.3.0',
                'runType': 'incremental' if self.stats['new_records'] < self.stats['total_records'] else 'full'
            },
            'summary': ". ".join(summary_parts) + ".",
            'totalRecords': self.stats['total_records'],
            'newRecords': self.stats['new_records'],
            'autoCorrections': self.stats['auto_corrected'],
            'deduplicated': deduplicated,
            'flaggedRecords': self.stats['flagged'],
            'totalIssues': total_issues,
            'errors': self.stats['errors'],
            'cleanRecords': clean_records,
            'cleanRate': clean_rate,
            'errorRate': round(self.stats['errors'] / max(self.stats['new_records'], 1) * 100, 2),
            'issuesByCategory': self._count_issues_by_category(),
            'correctionsByField': self._count_corrections_by_field(),
            'flaggedRecordsList': self._get_flagged_records()
        }

    def _count_issues_by_category(self) -> dict:
        """Count issues by category."""
        counts = {}
        for issue in self.issues:
            category = issue.get('issue', 'unknown')
            counts[category] = counts.get(category, 0) + 1
        return counts

    def _count_corrections_by_field(self) -> dict:
        """Count corrections by field."""
        counts = {}
        for correction in self.corrections:
            field = correction.get('field', 'unknown')
            counts[field] = counts.get(field, 0) + 1
        return counts

    def _get_flagged_records(self, limit: int = 50) -> List[dict]:
        """Get list of flagged records (errors and warnings)."""
        flagged = []
        seen_docs = set()

        for issue in self.issues:
            if issue['severity'] in ['error', 'warning']:
                doc_nbr = issue.get('document_nbr', f"row_{issue['row']}")
                if doc_nbr not in seen_docs:
                    flagged.append({
                        'documentNbr': doc_nbr,
                        'issues': [issue['message']],
                        'severity': issue['severity']
                    })
                    seen_docs.add(doc_nbr)

                    if len(flagged) >= limit:
                        break

        return flagged


def load_config() -> dict:
    """Load configuration from config.json."""
    if not CONFIG_PATH.exists():
        logger.error(f"Config file not found: {CONFIG_PATH}")
        sys.exit(1)

    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)


def load_validated_ids(jurisdiction: str, filter_type: str) -> set:
    """Load set of previously validated Document Numbers."""
    ids_file = VALIDATION_DIR / f"validated_ids_{jurisdiction}_{filter_type}.txt"

    if not ids_file.exists():
        return set()

    with open(ids_file, 'r') as f:
        return set(line.strip() for line in f if line.strip() and not line.startswith('#'))


def save_validated_ids(jurisdiction: str, filter_type: str, ids: set):
    """Save validated Document Numbers."""
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    ids_file = VALIDATION_DIR / f"validated_ids_{jurisdiction}_{filter_type}.txt"

    with open(ids_file, 'w') as f:
        f.write(f"# Validated Document Numbers for {jurisdiction}_{filter_type}.csv\n")
        f.write(f"# Last updated: {datetime.utcnow().isoformat()}Z\n")
        f.write(f"# Total: {len(ids)}\n")
        for doc_id in sorted(ids):
            f.write(f"{doc_id}\n")


def save_corrections_log(corrections: List[dict], jurisdiction: str):
    """Append corrections to log file."""
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    log_file = VALIDATION_DIR / "corrections_log.csv"

    # Create header if file doesn't exist
    write_header = not log_file.exists()

    with open(log_file, 'a') as f:
        if write_header:
            f.write("timestamp,jurisdiction,document_nbr,field,original_value,corrected_value,confidence,reason,auto_applied\n")

        timestamp = datetime.utcnow().isoformat() + 'Z'
        for c in corrections:
            if c.get('auto_applied'):
                row = [
                    timestamp,
                    jurisdiction,
                    str(c.get('document_nbr', f"row_{c['row']}")),
                    c['field'],
                    str(c['original']).replace(',', ';'),
                    str(c['corrected']).replace(',', ';'),
                    str(c['confidence']),
                    c.get('reason', '').replace(',', ';'),
                    'true'
                ]
                f.write(','.join(row) + '\n')


def save_report(report: dict):
    """Save validation report."""
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    report_file = VALIDATION_DIR / "latest_report.json"

    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    # Also save to history
    history_dir = VALIDATION_DIR / "history"
    history_dir.mkdir(exist_ok=True)
    month = datetime.utcnow().strftime('%Y-%m')
    history_file = history_dir / f"report_{month}.json"

    with open(history_file, 'w') as f:
        json.dump(report, f, indent=2)


def save_manifest(jurisdiction: str, stats: dict, files_validated: List[str]):
    """Save validation manifest."""
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    manifest_file = VALIDATION_DIR / "manifest.json"

    manifest = {
        'lastRun': datetime.utcnow().isoformat() + 'Z',
        'runType': 'incremental' if stats['new_records'] < stats['total_records'] else 'full',
        'jurisdiction': jurisdiction,
        'validationRulesVersion': '1.0.0',
        'correctionRulesVersion': '1.0.0',
        'recordsProcessed': stats,
        'filesValidated': files_validated
    }

    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)


def get_data_files(jurisdiction: str, config: dict) -> List[Tuple[str, str]]:
    """Get list of data files for jurisdiction."""
    juris_config = config.get('jurisdictions', {}).get(jurisdiction, {})
    maintains_own_roads = juris_config.get('maintainsOwnRoads', False)

    files = []

    if maintains_own_roads:
        # Counties like Henrico and Arlington have 3 files
        files.append((f"{jurisdiction}_county_roads.csv", "county_roads"))
        files.append((f"{jurisdiction}_no_interstate.csv", "no_interstate"))
        files.append((f"{jurisdiction}_all_roads.csv", "all_roads"))
    else:
        # Other jurisdictions have only all_roads
        files.append((f"{jurisdiction}_all_roads.csv", "all_roads"))

    return files


def validate_jurisdiction(jurisdiction: str, config: dict, full: bool = False,
                          dry_run: bool = False, auto_correct: bool = True,
                          geocode: bool = False, spatial_validate_pct: float = 0) -> dict:
    """
    Validate all data files for a jurisdiction.

    Args:
        jurisdiction: Jurisdiction ID (e.g., 'henrico')
        config: Configuration dict
        full: Force full re-validation
        dry_run: Preview without making changes
        auto_correct: Apply auto-corrections

    Returns:
        Validation report dict
    """
    logger.info(f"=" * 60)
    logger.info(f"Validating jurisdiction: {jurisdiction}")
    logger.info(f"=" * 60)

    if geocode or spatial_validate_pct > 0:
        if SPATIAL_AVAILABLE:
            logger.info(f"Spatial processing enabled: geocode={geocode}, validate={spatial_validate_pct}%")
        else:
            logger.warning("Spatial processing requested but modules not available")

    validator = CrashDataValidator(jurisdiction, config)
    data_files = get_data_files(jurisdiction, config)
    files_validated = []
    combined_report = None

    for filename, filter_type in data_files:
        filepath = DATA_DIR / filename

        if not filepath.exists():
            logger.warning(f"Data file not found: {filepath}")
            continue

        logger.info(f"Processing: {filename}")

        # Load data
        df = pd.read_csv(filepath)
        logger.info(f"Loaded {len(df)} records")

        # Load validated IDs for incremental processing
        validated_ids = set() if full else load_validated_ids(jurisdiction, filter_type)

        # Validate
        corrected_df = validator.validate_dataframe(
            df,
            incremental=not full,
            validated_ids=validated_ids
        )

        # Spatial processing (geocoding + validation + correction)
        spatial_stats = {}
        if SPATIAL_AVAILABLE and (geocode or spatial_validate_pct > 0):
            logger.info("Running spatial processing (incremental - new records only)...")
            spatial_processor = CrashSpatialProcessor(
                enable_geocoding=geocode,
                enable_validation=spatial_validate_pct > 0,
                enable_correction=True  # Auto-correct bad coords using FREE VDOT data
            )
            corrected_df, spatial_stats = spatial_processor.process_dataframe(
                corrected_df,
                geocode_missing=geocode,
                validate_sample_pct=spatial_validate_pct,
                correct_bad_coords=True,
                validated_ids=validated_ids  # Incremental: skip already-validated records
            )
            logger.info(f"Spatial processing complete: {spatial_stats.get('geocoding', {})}")
            if spatial_stats.get('corrections_made'):
                logger.info(f"Auto-corrected {len(spatial_stats['corrections_made'])} coordinates")

        # Generate report
        report = validator.get_report()

        # Add spatial stats to report
        if spatial_stats:
            report['spatialProcessing'] = spatial_stats

        combined_report = report  # Use last report as combined (could merge)

        if dry_run:
            logger.info(f"DRY RUN - Would make {report['autoCorrections']} corrections")
            logger.info(f"DRY RUN - Would flag {report['flaggedRecords']} records")
        else:
            if auto_correct:
                # Save corrected data
                corrected_df.to_csv(filepath, index=False)
                logger.info(f"Saved validated data to {filepath}")

                # Update validated IDs
                all_ids = validated_ids | set(corrected_df['Document Nbr'].dropna().astype(str))
                save_validated_ids(jurisdiction, filter_type, all_ids)

                # Save corrections log
                save_corrections_log(validator.corrections, jurisdiction)

        files_validated.append(filename)

        logger.info(f"Results: {report['autoCorrections']} corrected, "
                    f"{report['flaggedRecords']} flagged, {report['errors']} errors")

    if not dry_run and combined_report:
        # Save report and manifest
        save_report(combined_report)
        save_manifest(jurisdiction, validator.stats, files_validated)

        # Copy county_roads to crashes.csv (fallback)
        county_roads_file = DATA_DIR / f"{jurisdiction}_county_roads.csv"
        crashes_fallback = DATA_DIR / "crashes.csv"
        if county_roads_file.exists():
            import shutil
            shutil.copy(county_roads_file, crashes_fallback)
            logger.info(f"Updated fallback: {crashes_fallback}")

    return combined_report or {}


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Virginia Crash Data Validation System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_validation.py                                # Default jurisdiction
  python run_validation.py --jurisdiction henrico         # Specific jurisdiction
  python run_validation.py --jurisdiction henrico --full  # Force full re-validation
  python run_validation.py --dry-run                      # Preview without changes
  python run_validation.py --all                          # All jurisdictions
        """
    )

    parser.add_argument(
        '--jurisdiction', '-j',
        type=str,
        nargs='+',
        help='Jurisdiction ID(s) to validate (e.g., henrico, arlington)'
    )

    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='Validate all configured jurisdictions'
    )

    parser.add_argument(
        '--full', '-f',
        action='store_true',
        help='Force full re-validation (ignore incremental state)'
    )

    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Preview validation without making changes'
    )

    parser.add_argument(
        '--no-auto-correct',
        action='store_true',
        help='Disable auto-correction (flag only)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--geocode',
        action='store_true',
        help='Enable geocoding for records with missing coordinates'
    )

    parser.add_argument(
        '--spatial-validate',
        type=float,
        default=0,
        metavar='PCT',
        help='Validate PCT%% of records against OSM road network (0-100, 0=disabled)'
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load config
    config = load_config()

    # Determine jurisdictions to validate
    if args.all:
        jurisdictions = list(config.get('jurisdictions', {}).keys())
        logger.info(f"Validating all {len(jurisdictions)} jurisdictions")
    elif args.jurisdiction:
        jurisdictions = args.jurisdiction
    else:
        # Default jurisdiction from config
        jurisdictions = [config.get('defaults', {}).get('jurisdiction', 'henrico')]

    # Validate each jurisdiction
    all_reports = {}
    for jurisdiction in jurisdictions:
        try:
            report = validate_jurisdiction(
                jurisdiction=jurisdiction,
                config=config,
                full=args.full,
                dry_run=args.dry_run,
                auto_correct=not args.no_auto_correct,
                geocode=args.geocode,
                spatial_validate_pct=args.spatial_validate
            )
            all_reports[jurisdiction] = report

            # Check error rate threshold
            if report.get('errorRate', 0) > 10:
                logger.error(f"Error rate exceeds 10% for {jurisdiction}. Manual review required.")

        except Exception as e:
            logger.error(f"Validation failed for {jurisdiction}: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()

    # Summary
    logger.info("=" * 60)
    logger.info("VALIDATION COMPLETE")
    logger.info("=" * 60)

    for jurisdiction, report in all_reports.items():
        logger.info(f"{jurisdiction}: {report.get('summary', 'No summary')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
