"""
Auto-Correction Engine for Virginia Crash Data

This module handles applying corrections to crash data based on
confidence-scored rules defined in correction_rules.json.

The main correction logic is currently embedded in run_validation.py.
This module will be expanded in future phases for more sophisticated
correction handling.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Reference data path
CORRECTION_RULES_FILE = Path(__file__).parent.parent / "reference" / "correction_rules.json"


class CrashDataCorrector:
    """
    Handles auto-correction of crash data based on defined rules.

    Attributes:
        rules: Correction rules loaded from correction_rules.json
        confidence_threshold: Minimum confidence for auto-apply (default: 85)
    """

    def __init__(self, confidence_threshold: int = 85):
        self.confidence_threshold = confidence_threshold
        self.rules = self._load_rules()
        self.applied_corrections = []

    def _load_rules(self) -> dict:
        """Load correction rules from JSON file."""
        if not CORRECTION_RULES_FILE.exists():
            return {}

        with open(CORRECTION_RULES_FILE, 'r') as f:
            return json.load(f)

    def get_category_correction(self, field: str, value: str) -> Optional[dict]:
        """
        Look up correction for a category field value.

        Args:
            field: Field name (e.g., 'Light Condition')
            value: Current value to check

        Returns:
            Correction dict if found, None otherwise
        """
        field_corrections = self.rules.get('categoryCorrections', {}).get(field, {})
        return field_corrections.get(value)

    def should_auto_apply(self, confidence: int) -> bool:
        """Check if correction should be auto-applied based on confidence."""
        return confidence >= self.confidence_threshold

    def apply_correction(self, record: dict, field: str,
                        original: str, corrected: str,
                        confidence: int, reason: str) -> dict:
        """
        Apply a correction to a record and log it.

        Args:
            record: Record dict to modify
            field: Field name to correct
            original: Original value
            corrected: Corrected value
            confidence: Confidence score (0-100)
            reason: Explanation for correction

        Returns:
            Modified record
        """
        record[field] = corrected

        self.applied_corrections.append({
            'field': field,
            'original': original,
            'corrected': corrected,
            'confidence': confidence,
            'reason': reason,
            'auto_applied': self.should_auto_apply(confidence)
        })

        return record

    def get_correction_summary(self) -> dict:
        """Get summary of all applied corrections."""
        by_field = {}
        for c in self.applied_corrections:
            field = c['field']
            by_field[field] = by_field.get(field, 0) + 1

        return {
            'total': len(self.applied_corrections),
            'auto_applied': len([c for c in self.applied_corrections if c['auto_applied']]),
            'by_field': by_field
        }

    def reset(self):
        """Reset correction tracking."""
        self.applied_corrections = []
