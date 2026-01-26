"""
Main Validator Class for Virginia Crash Data

This module contains the CrashDataValidator class which is also defined
in run_validation.py for standalone execution. This file serves as a
module import point for when the validation system is used as a library.

For the full implementation, see run_validation.py
"""

# Re-export from run_validation for library usage
# This allows: from validation.core import CrashDataValidator

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from run_validation import CrashDataValidator
except ImportError:
    # Placeholder class if run_validation not available
    class CrashDataValidator:
        """
        Placeholder for CrashDataValidator.
        See run_validation.py for full implementation.
        """
        def __init__(self, jurisdiction: str, config: dict):
            self.jurisdiction = jurisdiction
            self.config = config
            raise NotImplementedError(
                "CrashDataValidator should be imported from run_validation.py"
            )
