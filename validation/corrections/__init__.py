"""
Auto-correction engine for Virginia crash data.

Modules:
    - corrector: Main corrector class applying corrections
    - rules: Rule engine for loading and applying correction rules
"""

from .corrector import CrashDataCorrector

__all__ = ["CrashDataCorrector"]
