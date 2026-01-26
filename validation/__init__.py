"""
Virginia Crash Data Validation System

A comprehensive validation and auto-correction system for Virginia crash data
supporting all 133 jurisdictions with incremental processing capabilities.

Usage:
    python -m validation.run_validation --jurisdiction henrico
    python -m validation.run_validation --jurisdiction henrico --full
    python -m validation.run_validation --all

Author: CRASH LENS Team
Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "CRASH LENS Team"

from pathlib import Path

# Package root directory
PACKAGE_ROOT = Path(__file__).parent

# Reference data directory
REFERENCE_DIR = PACKAGE_ROOT / "reference"

# Default paths
DEFAULT_CONFIG_PATH = PACKAGE_ROOT.parent / "config.json"
DEFAULT_DATA_DIR = PACKAGE_ROOT.parent / "data"
DEFAULT_VALIDATION_DIR = DEFAULT_DATA_DIR / ".validation"
