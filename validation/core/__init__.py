"""
Core validation modules for Virginia crash data.

Modules:
    - validator: Main validator class orchestrating all checks
    - schema: Schema validation (data types, required fields)
    - bounds: Geographic bounds validation
    - categories: Category/enumeration validation
    - consistency: Cross-field consistency checks
    - completeness: Missing value detection
    - duplicates: Duplicate record detection
    - spatial: Overpass API integration for road validation
"""

from .validator import CrashDataValidator

__all__ = ["CrashDataValidator"]
