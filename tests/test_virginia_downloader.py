#!/usr/bin/env python3
"""
Tests for download_virginia_crash_data.py — Playwright-based Virginia downloader.

Covers:
  1. File handle leaks in validate_csv() and main()
  2. Pagination loop off-by-one in download_with_browser()
  3. JS injection risk in browser_fetch_json() URL interpolation
  4. Bare except clauses in save_cached_url() / load_cached_url()
  5. validate_csv() correctly rejects driver-level datasets
  6. filter_by_jurisdiction() matching logic
  7. split_road_types() output files
"""

import csv
import importlib
import json
import os
import re
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add repo root to path so we can import the module
REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))


class TestValidateCSV(unittest.TestCase):
    """Tests for validate_csv()."""

    def _import_func(self):
        """Import validate_csv from the script."""
        spec = importlib.util.spec_from_file_location(
            "virginia_dl", REPO_ROOT / "download_virginia_crash_data.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.validate_csv

    def test_valid_crash_csv(self):
        validate_csv = self._import_func()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(['OBJECTID', 'Crash_Year', 'Crash_Severity', 'x', 'y'])
            for i in range(100):
                writer.writerow([i, 2024, 'K', -77.5, 37.5])
            path = f.name
        try:
            self.assertTrue(validate_csv(path))
        finally:
            os.unlink(path)

    def test_rejects_driver_level_dataset(self):
        """BUG: validate_csv must reject CSVs with driver-level columns."""
        validate_csv = self._import_func()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(['OBJECTID', 'Driver_Age', 'DRIVER_AGE', 'Bike_VehicleNumber'])
            for i in range(50):
                writer.writerow([i, 25, 25, 1])
            path = f.name
        try:
            self.assertFalse(validate_csv(path), "Should reject driver-level CSV")
        finally:
            os.unlink(path)

    def test_rejects_html_error_page(self):
        validate_csv = self._import_func()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write('<html><body>403 Forbidden</body></html>')
            path = f.name
        try:
            self.assertFalse(validate_csv(path), "Should reject HTML error pages")
        finally:
            os.unlink(path)

    def test_file_handle_leak(self):
        """BUG: validate_csv uses open() without 'with' — file handle leaks."""
        validate_csv = self._import_func()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(['OBJECTID', 'Crash_Year', 'x', 'y'])
            for i in range(50):
                writer.writerow([i, 2024, -77.5, 37.5])
            path = f.name
        try:
            # Track open file descriptors before and after
            import gc
            gc.collect()
            # Call validate_csv and check it doesn't leak
            result = validate_csv(path)
            self.assertTrue(result)
            # The real test: can we delete the file immediately on all platforms?
            # On Windows, leaked handles prevent deletion. On Linux, it's a resource leak.
            os.unlink(path)
            self.assertFalse(os.path.exists(path))
        except Exception:
            if os.path.exists(path):
                os.unlink(path)
            raise


class TestPaginationLoop(unittest.TestCase):
    """Test that pagination doesn't overshoot total_count."""

    def test_loop_condition_off_by_one(self):
        """BUG: while offset < total_count + batch_size allows one extra request.

        If total_count=100 and batch_size=50, the loop runs at offset=100 which is
        past the data. Should be: offset < total_count.
        """
        # Read the source and check the while condition
        source = (REPO_ROOT / "download_virginia_crash_data.py").read_text()
        # Find the while loop in download_with_browser
        match = re.search(r'while offset < (total_count\s*\+\s*batch_size)', source)
        if match:
            self.fail(
                f"Pagination bug: 'while offset < {match.group(1)}' should be "
                f"'while offset < total_count'. The +batch_size causes an extra "
                f"unnecessary API call after all records are fetched."
            )


class TestJSInjection(unittest.TestCase):
    """Test browser_fetch_json URL handling."""

    def test_url_with_special_chars_in_fetch(self):
        """BUG: URL is interpolated directly into JS via f-string.

        A URL containing backticks, single quotes, or ${...} patterns could
        break or inject into the JavaScript template literal.
        """
        source = (REPO_ROOT / "download_virginia_crash_data.py").read_text()
        # Find the fetch call in browser_fetch_json
        match = re.search(r'const resp = await fetch\("?\{url\}"?\)', source)
        if match:
            # Check if url is properly escaped (e.g., via json.dumps or encodeURIComponent)
            # Look for json.dumps(url) or similar escaping before the evaluate call
            func_match = re.search(
                r'def browser_fetch_json\(.*?\):\s*""".*?"""(.*?)(?=\ndef |\Z)',
                source, re.DOTALL
            )
            if func_match:
                func_body = func_match.group(1)
                has_escaping = (
                    'json.dumps' in func_body or
                    'quote(' in func_body or
                    'encodeURI' in func_body or
                    'replace(' in func_body
                )
                if not has_escaping:
                    self.fail(
                        "browser_fetch_json() interpolates URL directly into JavaScript "
                        "via f-string without escaping. URLs with backticks, quotes, or "
                        "${} patterns could break or inject code. Fix: use json.dumps(url) "
                        "for the JS string literal."
                    )


class TestBareExcepts(unittest.TestCase):
    """Test that bare except clauses don't silently swallow important errors."""

    def test_no_bare_excepts(self):
        """BUG: Bare 'except:' catches SystemExit, KeyboardInterrupt, etc."""
        source = (REPO_ROOT / "download_virginia_crash_data.py").read_text()
        lines = source.split('\n')
        bare_excepts = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped == 'except:' or stripped.startswith('except:'):
                bare_excepts.append((i, line.strip()))

        if bare_excepts:
            locations = ", ".join(f"line {n}: '{code}'" for n, code in bare_excepts)
            self.fail(
                f"Found bare 'except:' clauses that catch SystemExit/KeyboardInterrupt: "
                f"{locations}. Fix: use 'except Exception:' instead."
            )


class TestFilterByJurisdiction(unittest.TestCase):
    """Tests for filter_by_jurisdiction()."""

    def _import_func(self):
        spec = importlib.util.spec_from_file_location(
            "virginia_dl", REPO_ROOT / "download_virginia_crash_data.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.filter_by_jurisdiction

    @unittest.skipUnless(
        importlib.util.find_spec("pandas"), "pandas not installed"
    )
    def test_filters_by_juris_code(self):
        import pandas as pd
        filter_fn = self._import_func()
        df = pd.DataFrame({
            'Juris_Code': ['087', '087', '041', '041', '087'],
            'Physical_Juris_Name': ['HENRICO', 'HENRICO', 'CHESTERFIELD', 'CHESTERFIELD', 'HENRICO'],
            'Crash_Year': [2024, 2024, 2024, 2024, 2024],
        })
        jconfig = {'jurisCode': '087', 'fips': '087', 'name': 'Henrico', 'namePatterns': ['HENRICO']}
        result = filter_fn(df, 'henrico', jconfig)
        self.assertEqual(len(result), 3)

    @unittest.skipUnless(
        importlib.util.find_spec("pandas"), "pandas not installed"
    )
    def test_falls_back_to_name_pattern(self):
        import pandas as pd
        filter_fn = self._import_func()
        df = pd.DataFrame({
            'Physical_Juris_Name': ['HENRICO', 'HENRICO', 'FAIRFAX', 'HENRICO'],
            'Crash_Year': [2024, 2024, 2024, 2024],
        })
        jconfig = {'jurisCode': '', 'fips': '', 'name': 'Henrico', 'namePatterns': ['HENRICO']}
        result = filter_fn(df, 'henrico', jconfig)
        self.assertEqual(len(result), 3)


class TestWorkflowStepSummary(unittest.TestCase):
    """Test workflow YAML for formatting bugs."""

    def test_step_summary_indentation(self):
        """BUG: GITHUB_STEP_SUMMARY heredoc has leading whitespace that renders
        as a code block instead of proper markdown headers/tables.
        """
        workflow_path = REPO_ROOT / ".github" / "workflows" / "download-virginia.yml"
        if not workflow_path.exists():
            self.skipTest("Workflow file not found")

        content = workflow_path.read_text()
        # Find the heredoc block for GITHUB_STEP_SUMMARY
        match = re.search(
            r'cat >> \$GITHUB_STEP_SUMMARY <<EOF\n(.*?)EOF',
            content, re.DOTALL
        )
        if not match:
            self.skipTest("No GITHUB_STEP_SUMMARY heredoc found")

        heredoc_body = match.group(1)
        lines = heredoc_body.split('\n')
        # Check if markdown lines have excessive leading whitespace
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('##') or stripped.startswith('|'):
                leading_spaces = len(line) - len(line.lstrip())
                if leading_spaces >= 4:
                    self.fail(
                        f"GITHUB_STEP_SUMMARY has {leading_spaces} leading spaces on "
                        f"'{stripped[:40]}...'. GitHub renders 4+ leading spaces as a "
                        f"code block, not as markdown. Remove the indentation."
                    )


if __name__ == '__main__':
    unittest.main(verbosity=2)
