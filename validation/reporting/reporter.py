"""
Validation Report Generator

Generates reports in various formats (JSON, CSV, HTML) from validation results.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class ValidationReporter:
    """
    Generates validation reports from validation results.

    Supports:
    - JSON reports (machine-readable)
    - CSV reports (spreadsheet-compatible)
    - Summary text (for logging/notifications)
    """

    def __init__(self, jurisdiction: str, validation_version: str = "1.0.0"):
        self.jurisdiction = jurisdiction
        self.validation_version = validation_version
        self.issues = []
        self.corrections = []
        self.stats = {}

    def set_results(self, issues: List[dict], corrections: List[dict], stats: dict):
        """Set validation results for reporting."""
        self.issues = issues
        self.corrections = corrections
        self.stats = stats

    def generate_json_report(self) -> dict:
        """Generate JSON-formatted report."""
        return {
            'metadata': {
                'generatedAt': datetime.utcnow().isoformat() + 'Z',
                'jurisdiction': self.jurisdiction,
                'validationVersion': self.validation_version,
                'runType': self._determine_run_type()
            },
            'summary': self._generate_summary(),
            'totalRecords': self.stats.get('total_records', 0),
            'newRecords': self.stats.get('new_records', 0),
            'autoCorrections': self.stats.get('auto_corrected', 0),
            'flagged': self.stats.get('flagged', 0),
            'errors': self.stats.get('errors', 0),
            'cleanRate': self._calculate_clean_rate(),
            'errorRate': self._calculate_error_rate(),
            'issuesByCategory': self._count_issues_by_category(),
            'correctionsByField': self._count_corrections_by_field(),
            'flaggedRecords': self._get_flagged_records()
        }

    def _determine_run_type(self) -> str:
        """Determine if this was incremental or full validation."""
        total = self.stats.get('total_records', 0)
        new = self.stats.get('new_records', 0)
        return 'incremental' if new < total else 'full'

    def _generate_summary(self) -> str:
        """Generate human-readable summary."""
        new = self.stats.get('new_records', 0)
        corrected = self.stats.get('auto_corrected', 0)
        flagged = self.stats.get('flagged', 0)
        clean = new - corrected - flagged

        return (f"Validated {new} new records. "
                f"{corrected} auto-corrected, {flagged} flagged, {clean} clean.")

    def _calculate_clean_rate(self) -> float:
        """Calculate percentage of clean records."""
        new = self.stats.get('new_records', 1)
        flagged = self.stats.get('flagged', 0)
        return round((1 - flagged / new) * 100, 2) if new > 0 else 100.0

    def _calculate_error_rate(self) -> float:
        """Calculate percentage of error records."""
        new = self.stats.get('new_records', 1)
        errors = self.stats.get('errors', 0)
        return round(errors / new * 100, 2) if new > 0 else 0.0

    def _count_issues_by_category(self) -> dict:
        """Count issues grouped by category."""
        counts = {}
        for issue in self.issues:
            category = issue.get('issue', 'unknown')
            counts[category] = counts.get(category, 0) + 1
        return counts

    def _count_corrections_by_field(self) -> dict:
        """Count corrections grouped by field."""
        counts = {}
        for correction in self.corrections:
            field = correction.get('field', 'unknown')
            counts[field] = counts.get(field, 0) + 1
        return counts

    def _get_flagged_records(self, limit: int = 50) -> List[dict]:
        """Get list of flagged records for review."""
        flagged = []
        seen = set()

        for issue in self.issues:
            if issue.get('severity') in ['error', 'warning']:
                doc = issue.get('document_nbr', f"row_{issue.get('row', 'unknown')}")
                if doc not in seen:
                    flagged.append({
                        'documentNbr': doc,
                        'issues': [issue.get('message', 'Unknown issue')],
                        'severity': issue.get('severity')
                    })
                    seen.add(doc)

                    if len(flagged) >= limit:
                        break

        return flagged

    def save_json_report(self, filepath: Path):
        """Save report as JSON file."""
        report = self.generate_json_report()
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)

    def save_csv_report(self, filepath: Path):
        """Save issues as CSV file."""
        with open(filepath, 'w') as f:
            # Header
            f.write("row,field,issue,severity,value,message\n")

            # Issues
            for issue in self.issues:
                row = [
                    str(issue.get('row', '')),
                    issue.get('field', ''),
                    issue.get('issue', ''),
                    issue.get('severity', ''),
                    str(issue.get('value', '')).replace(',', ';'),
                    issue.get('message', '').replace(',', ';')
                ]
                f.write(','.join(row) + '\n')

    def get_summary_text(self) -> str:
        """Get summary as plain text for logging."""
        return self._generate_summary()
