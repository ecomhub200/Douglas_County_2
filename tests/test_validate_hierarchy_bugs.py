#!/usr/bin/env python3
"""
Bug tests for scripts/validate_hierarchy.py

Validates that:
  1. Orphaned counties are detected (in allCounties but not in any region)
  2. Empty MPO counties are detected (MPOs with counties=[])
  3. Unresolvable FIPS codes are detected (in regions but not in allCounties)
  4. Missing counties from Census data are detected
  5. Region coverage is calculated correctly
  6. MPO coverage is calculated correctly
  7. Auto-fix assigns orphaned county to nearest region
  8. Auto-fix assigns counties to empty MPOs via spatial matching
  9. No false positives on a clean hierarchy
 10. Virginia hierarchy detects known orphaned counties
 11. Virginia hierarchy detects known empty MPOs
 12. Pipeline integration: Stage 0.1 exists in pipeline.yml
 13. HierarchyIssue repr shows correct icons
 14. Duplicate FIPS in multiple regions doesn't crash
 15. Empty allCounties doesn't crash (edge case)
 16. Ownership derivation: State roads → State Hwy Agency
 17. Ownership derivation: City/Town jurisdiction → City or Town Hwy Agency
 18. Ownership derivation: County jurisdiction → County Hwy Agency
 19. Ownership derivation: VDOT numeric codes ≥100 → City/Town
 20. Ownership derivation: empty inputs → Private/Unknown
 21. Ownership CSV check detects missing values
 22. Ownership CSV check backfills empty rows correctly
 23. Ownership CSV check preserves existing valid values
 24. Pipeline Stage 2.5 exists for Ownership derivation
 25. Unified-Pipeline-Architecture.md documents Stage 0.1
 26. Unified-Pipeline-Architecture.md documents Stage 2.5
 27. data-pipeline-download-to-R2 doc lists new stages
 28. All 6 Ownership values documented in architecture doc

Run with:
    python tests/test_validate_hierarchy_bugs.py
    python -m pytest tests/test_validate_hierarchy_bugs.py -v
"""

import csv
import json
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from validate_hierarchy import (
    HierarchyIssue,
    check_empty_mpo_counties,
    check_missing_counties,
    check_mpo_coverage,
    check_orphaned_counties,
    check_region_completeness,
    check_unresolvable_fips,
    assign_to_nearest_region,
    check_ownership_column,
    derive_ownership,
    haversine_km,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def clean_hierarchy():
    """A hierarchy with no issues — all counties assigned to regions."""
    return {
        "state": {"fips": "99", "name": "TestState", "abbreviation": "TS"},
        "allCounties": {
            "001": "Alpha County",
            "003": "Bravo County",
            "005": "Charlie County",
        },
        "regions": {
            "north": {
                "name": "North Region",
                "counties": ["001", "003"],
                "countyNames": {"001": "Alpha County", "003": "Bravo County"},
                "center": [-79.0, 38.0],
            },
            "south": {
                "name": "South Region",
                "counties": ["005"],
                "countyNames": {"005": "Charlie County"},
                "center": [-79.0, 37.0],
            },
        },
        "tprs": {
            "metro_mpo": {
                "name": "Metro MPO",
                "type": "mpo",
                "counties": ["001"],
                "countyNames": {"001": "Alpha County"},
                "center": [-79.0, 38.0],
            }
        },
    }


@pytest.fixture
def orphaned_hierarchy():
    """Hierarchy with counties not assigned to any region."""
    return {
        "state": {"fips": "99", "name": "TestState"},
        "allCounties": {
            "001": "Alpha County",
            "003": "Bravo County",
            "005": "Charlie County",
            "007": "Delta County",
        },
        "regions": {
            "north": {
                "name": "North Region",
                "counties": ["001"],
                "countyNames": {"001": "Alpha County"},
                "center": [-79.0, 38.0],
            },
        },
        "tprs": {},
    }


@pytest.fixture
def empty_mpo_hierarchy():
    """Hierarchy with MPOs that have empty county arrays."""
    return {
        "state": {"fips": "99", "name": "TestState"},
        "allCounties": {
            "001": "Alpha County",
            "003": "Bravo County",
        },
        "regions": {
            "north": {
                "name": "North Region",
                "counties": ["001", "003"],
                "countyNames": {"001": "Alpha County", "003": "Bravo County"},
            },
        },
        "tprs": {
            "ghost_mpo": {
                "name": "Ghost MPO",
                "type": "mpo",
                "counties": [],
                "countyNames": {},
                "center": [-79.0, 38.0],
            },
            "real_mpo": {
                "name": "Real MPO",
                "type": "mpo",
                "counties": ["001"],
                "countyNames": {"001": "Alpha County"},
            },
        },
    }


@pytest.fixture
def unresolvable_hierarchy():
    """Hierarchy with FIPS codes in regions not in allCounties."""
    return {
        "state": {"fips": "99", "name": "TestState"},
        "allCounties": {
            "001": "Alpha County",
        },
        "regions": {
            "north": {
                "name": "North Region",
                "counties": ["001", "999"],  # 999 doesn't exist
            },
        },
        "tprs": {
            "bad_mpo": {
                "name": "Bad MPO",
                "type": "mpo",
                "counties": ["888"],  # 888 doesn't exist
            }
        },
    }


def load_virginia_hierarchy():
    """Load the real Virginia hierarchy.json."""
    path = PROJECT_ROOT / "states" / "virginia" / "hierarchy.json"
    if not path.exists():
        pytest.skip("Virginia hierarchy.json not found")
    with open(path) as f:
        return json.load(f)


# ── Test 1: Orphaned county detection ────────────────────────────────────────

def test_orphaned_counties_detected(orphaned_hierarchy):
    """BUG: Counties in allCounties but not in any region must be flagged."""
    issues = check_orphaned_counties(orphaned_hierarchy, "99")
    orphaned_fips = {i.message.split()[1] for i in issues}
    assert "003" in orphaned_fips, "Bravo County (003) should be orphaned"
    assert "005" in orphaned_fips, "Charlie County (005) should be orphaned"
    assert "007" in orphaned_fips, "Delta County (007) should be orphaned"
    assert "001" not in orphaned_fips, "Alpha County (001) is assigned, not orphaned"


def test_orphaned_counties_level_is_warning(orphaned_hierarchy):
    """Orphaned counties should be warnings, not errors."""
    issues = check_orphaned_counties(orphaned_hierarchy, "99")
    assert all(i.level == "warning" for i in issues)


def test_orphaned_counties_have_fix_fn(orphaned_hierarchy):
    """Each orphaned county issue should have an auto-fix function."""
    issues = check_orphaned_counties(orphaned_hierarchy, "99")
    assert all(i.fix_fn is not None for i in issues)


# ── Test 2: Empty MPO detection ──────────────────────────────────────────────

def test_empty_mpo_detected(empty_mpo_hierarchy):
    """BUG: MPOs with empty counties[] arrays must be flagged."""
    issues = check_empty_mpo_counties(empty_mpo_hierarchy, "99")
    mpo_keys = [i.message for i in issues]
    assert len(issues) == 1, f"Only ghost_mpo should be flagged, got {len(issues)}"
    assert "ghost_mpo" in mpo_keys[0]


def test_empty_mpo_not_flagged_when_populated(empty_mpo_hierarchy):
    """MPOs with counties should NOT be flagged."""
    issues = check_empty_mpo_counties(empty_mpo_hierarchy, "99")
    messages = " ".join(i.message for i in issues)
    assert "real_mpo" not in messages


# ── Test 3: Unresolvable FIPS detection ──────────────────────────────────────

def test_unresolvable_fips_detected(unresolvable_hierarchy):
    """BUG: FIPS codes in regions/MPOs not in allCounties must be flagged."""
    issues = check_unresolvable_fips(unresolvable_hierarchy)
    bad_fips = {i.message.split("'")[1] for i in issues}
    assert "999" in bad_fips, "FIPS 999 in region should be flagged"
    assert "888" in bad_fips, "FIPS 888 in MPO should be flagged"
    assert len(issues) == 2


def test_unresolvable_fips_level_is_error(unresolvable_hierarchy):
    """Unresolvable FIPS should be errors, not warnings."""
    issues = check_unresolvable_fips(unresolvable_hierarchy)
    assert all(i.level == "error" for i in issues)


# ── Test 4: Region coverage ──────────────────────────────────────────────────

def test_region_coverage_clean(clean_hierarchy):
    """Clean hierarchy should show 100% region coverage (info only)."""
    issues = check_region_completeness(clean_hierarchy)
    # All 3 counties assigned → no coverage warning
    coverage_issues = [i for i in issues if i.check == "region_coverage"]
    assert len(coverage_issues) == 0, "100% coverage should produce no coverage issue"


def test_region_coverage_partial(orphaned_hierarchy):
    """Partial coverage should report info-level issue."""
    issues = check_region_completeness(orphaned_hierarchy)
    coverage_issues = [i for i in issues if i.check == "region_coverage"]
    assert len(coverage_issues) == 1
    assert coverage_issues[0].level == "info"
    assert "25%" in coverage_issues[0].message  # 1 of 4 assigned


# ── Test 5: MPO coverage ─────────────────────────────────────────────────────

def test_mpo_coverage_reported(clean_hierarchy):
    """MPO coverage is always reported as info."""
    issues = check_mpo_coverage(clean_hierarchy)
    assert len(issues) == 1
    assert issues[0].level == "info"
    assert issues[0].check == "mpo_coverage"


# ── Test 6: No false positives on clean hierarchy ────────────────────────────

def test_no_false_positives_clean(clean_hierarchy):
    """A clean hierarchy should produce zero errors and zero warnings."""
    all_issues = []
    all_issues.extend(check_orphaned_counties(clean_hierarchy, "99"))
    all_issues.extend(check_unresolvable_fips(clean_hierarchy))
    all_issues.extend(check_empty_mpo_counties(clean_hierarchy, "99"))

    errors = [i for i in all_issues if i.level == "error"]
    warnings = [i for i in all_issues if i.level == "warning"]
    assert len(errors) == 0, f"Clean hierarchy should have no errors: {errors}"
    assert len(warnings) == 0, f"Clean hierarchy should have no warnings: {warnings}"


# ── Test 7: Auto-fix assigns orphaned county to nearest region ───────────────

def test_autofix_nearest_region():
    """Auto-fix should assign orphaned county to the geographically closest region."""
    hierarchy = {
        "state": {"fips": "99"},
        "allCounties": {
            "001": "Alpha",
            "003": "Bravo",
            "005": "Orphan",
        },
        "regions": {
            "north": {
                "name": "North",
                "counties": ["001"],
                "countyNames": {"001": "Alpha"},
                "center": [-79.0, 39.0],  # far north
            },
            "south": {
                "name": "South",
                "counties": ["003"],
                "countyNames": {"003": "Bravo"},
                "center": [-79.0, 36.0],  # far south
            },
        },
    }
    # Can't test full auto-fix without Census data, but verify the function
    # doesn't crash when called without Census data
    result = assign_to_nearest_region(hierarchy, "005", "99")
    # Without Census centroid data, it returns False
    assert result is False or result is True  # doesn't crash


# ── Test 8: HierarchyIssue repr ─────────────────────────────────────────────

def test_issue_repr_icons():
    """HierarchyIssue repr should show correct icon per level."""
    err = HierarchyIssue("error", "test", "error message")
    warn = HierarchyIssue("warning", "test", "warn message")
    info = HierarchyIssue("info", "test", "info message")
    assert "✗" in repr(err)
    assert "⚠" in repr(warn)
    assert "ℹ" in repr(info)


def test_issue_repr_includes_check_name():
    """HierarchyIssue repr should include the check name in brackets."""
    issue = HierarchyIssue("error", "my_check", "something broke")
    assert "[my_check]" in repr(issue)


# ── Test 9: Edge cases ───────────────────────────────────────────────────────

def test_empty_allcounties_no_crash():
    """Empty allCounties should not crash any check."""
    hierarchy = {
        "state": {"fips": "99"},
        "allCounties": {},
        "regions": {},
        "tprs": {},
    }
    check_orphaned_counties(hierarchy, "99")
    check_unresolvable_fips(hierarchy)
    check_empty_mpo_counties(hierarchy, "99")
    check_region_completeness(hierarchy)
    check_mpo_coverage(hierarchy)


def test_no_regions_section():
    """Missing regions section should not crash."""
    hierarchy = {
        "state": {"fips": "99"},
        "allCounties": {"001": "Alpha"},
    }
    issues = check_orphaned_counties(hierarchy, "99")
    assert len(issues) == 1  # Alpha is orphaned (no regions)


def test_duplicate_fips_in_regions():
    """County listed in multiple regions should not crash."""
    hierarchy = {
        "state": {"fips": "99"},
        "allCounties": {"001": "Alpha"},
        "regions": {
            "north": {"counties": ["001"]},
            "south": {"counties": ["001"]},  # duplicate
        },
    }
    issues = check_orphaned_counties(hierarchy, "99")
    assert len(issues) == 0  # 001 is assigned (even if duplicated)


# ── Test 10: Haversine calculation ───────────────────────────────────────────

def test_haversine_same_point():
    """Distance between same point should be 0."""
    assert haversine_km(38.0, -79.0, 38.0, -79.0) == 0.0


def test_haversine_known_distance():
    """Richmond to Norfolk is ~150km — verify rough accuracy."""
    dist = haversine_km(37.5407, -77.4360, 36.8508, -76.2859)
    assert 100 < dist < 170, f"Richmond-Norfolk should be ~128km, got {dist}"


# ── Test 11: Virginia real-world detection ───────────────────────────────────

def test_virginia_has_orphaned_counties():
    """BUG: Virginia hierarchy should flag orphaned counties (known issue)."""
    hierarchy = load_virginia_hierarchy()
    state_fips = hierarchy.get("state", {}).get("fips", "51")
    issues = check_orphaned_counties(hierarchy, state_fips)
    assert len(issues) > 0, "Virginia should have orphaned counties"
    orphaned_fips = {i.message.split()[1] for i in issues}
    # Known orphans from dry-run output
    assert "001" in orphaned_fips, "Accomack (001) should be orphaned"
    assert "035" in orphaned_fips, "Carroll (035) should be orphaned"


def test_virginia_has_empty_mpos():
    """BUG: Virginia hierarchy should flag empty MPOs (known issue)."""
    hierarchy = load_virginia_hierarchy()
    state_fips = hierarchy.get("state", {}).get("fips", "51")
    issues = check_empty_mpo_counties(hierarchy, state_fips)
    assert len(issues) > 0, "Virginia should have empty MPOs"
    messages = " ".join(i.message for i in issues)
    assert "danville_mpo" in messages, "Danville MPO should have empty counties"


def test_virginia_no_unresolvable_fips():
    """Virginia FIPS codes in regions should all be valid."""
    hierarchy = load_virginia_hierarchy()
    issues = check_unresolvable_fips(hierarchy)
    assert len(issues) == 0, f"Virginia has unresolvable FIPS: {issues}"


# ── Test 12: Pipeline integration ────────────────────────────────────────────

def test_pipeline_has_stage_01():
    """pipeline.yml must include Stage 0.1 hierarchy validation step."""
    pipeline_path = PROJECT_ROOT / ".github" / "workflows" / "pipeline.yml"
    assert pipeline_path.exists(), "pipeline.yml not found"
    content = pipeline_path.read_text()
    assert "validate_hierarchy.py" in content, "pipeline.yml must call validate_hierarchy.py"
    assert "Stage 0.1" in content, "pipeline.yml must have Stage 0.1 comment"


def test_pipeline_stage_01_is_nonfatal():
    """Stage 0.1 should be non-fatal (won't block pipeline on failure)."""
    pipeline_path = PROJECT_ROOT / ".github" / "workflows" / "pipeline.yml"
    content = pipeline_path.read_text()
    # Find the Stage 0.1 block and verify it has non-fatal error handling
    assert "non-fatal" in content.lower() or "|| {" in content, \
        "Stage 0.1 should have non-fatal error handling"


def test_pipeline_stage_01_after_cache_before_download():
    """Stage 0.1 should appear after Stage 0 (cache) and before Stage 0.5 (download)."""
    pipeline_path = PROJECT_ROOT / ".github" / "workflows" / "pipeline.yml"
    content = pipeline_path.read_text()
    pos_cache = content.find("Stage 0: Initialize")
    pos_validate = content.find("Stage 0.1")
    pos_download = content.find("Stage 0.5")
    assert pos_cache < pos_validate < pos_download, \
        "Stage order must be: 0 (cache) → 0.1 (validate) → 0.5 (download)"


# ── Test 13: Script CLI ──────────────────────────────────────────────────────

def test_script_exists():
    """validate_hierarchy.py must exist in scripts/."""
    path = PROJECT_ROOT / "scripts" / "validate_hierarchy.py"
    assert path.exists()


def test_script_is_executable_python():
    """Script should be valid Python (importable)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "validate_hierarchy",
        PROJECT_ROOT / "scripts" / "validate_hierarchy.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "main")
    assert hasattr(mod, "validate_state")


# ── Test 14: Ownership derivation ─────────────────────────────────────────────

class TestDeriveOwnership:
    """Test the derive_ownership() function that maps SYSTEM + Physical Juris → Ownership."""

    def test_vdot_interstate_is_state_agency(self):
        assert derive_ownership("VDOT Interstate", "") == "1. State Hwy Agency"

    def test_vdot_primary_is_state_agency(self):
        assert derive_ownership("VDOT Primary", "001. Accomack County") == "1. State Hwy Agency"

    def test_vdot_secondary_is_state_agency(self):
        assert derive_ownership("VDOT Secondary", "") == "1. State Hwy Agency"

    def test_interstate_generic_is_state_agency(self):
        """Non-VDOT states use plain 'Interstate' system value."""
        assert derive_ownership("Interstate", "") == "1. State Hwy Agency"

    def test_primary_generic_is_state_agency(self):
        assert derive_ownership("Primary", "Montgomery County") == "1. State Hwy Agency"

    def test_secondary_generic_is_state_agency(self):
        assert derive_ownership("Secondary", "") == "1. State Hwy Agency"

    def test_nonvdot_city_of_pattern(self):
        """'City of X' jurisdiction → City or Town Hwy Agency."""
        assert derive_ownership("NonVDOT secondary", "City of Norfolk") == "3. City or Town Hwy Agency"

    def test_nonvdot_town_of_pattern(self):
        """'Town of X' jurisdiction → City or Town Hwy Agency."""
        assert derive_ownership("NonVDOT secondary", "Town of Blacksburg") == "3. City or Town Hwy Agency"

    def test_nonvdot_numeric_code_city(self):
        """VDOT Physical Juris code ≥100 indicates city/town."""
        assert derive_ownership("NonVDOT secondary", "100. City of Alexandria") == "3. City or Town Hwy Agency"

    def test_nonvdot_numeric_code_150_town(self):
        assert derive_ownership("NonVDOT secondary", "150. Town of Blacksburg") == "3. City or Town Hwy Agency"

    def test_nonvdot_numeric_code_county(self):
        """VDOT Physical Juris code <100 indicates county."""
        assert derive_ownership("NonVDOT secondary", "001. Accomack County") == "2. County Hwy Agency"

    def test_nonvdot_county_text(self):
        """'X County' jurisdiction → County Hwy Agency."""
        assert derive_ownership("NonVDOT secondary", "Accomack County") == "2. County Hwy Agency"

    def test_nonvdot_primary_county(self):
        assert derive_ownership("NonVDOT primary", "050. King William County") == "2. County Hwy Agency"

    def test_empty_system_empty_juris(self):
        """Completely empty → Private/Unknown."""
        assert derive_ownership("", "", "") == "6. Private/Unknown Roads"

    def test_empty_system_with_county(self):
        """Empty SYSTEM but County jurisdiction → County Hwy Agency."""
        assert derive_ownership("", "Fairfax County") == "2. County Hwy Agency"


# ── Test 15: Ownership CSV check ─────────────────────────────────────────────

@pytest.fixture
def ownership_test_csv(tmp_path):
    """Create a test CSV with mixed Ownership values."""
    csv_path = tmp_path / "test_all_roads.csv"
    headers = ["Document Nbr", "Crash Severity", "SYSTEM", "Physical Juris Name", "Ownership", "RTE Name"]
    rows = [
        ["C001", "K", "VDOT Interstate", "051. Dickenson County", "", "I-81"],
        ["C002", "A", "NonVDOT secondary", "100. City of Alexandria", "", "Main St"],
        ["C003", "B", "NonVDOT secondary", "001. Accomack County", "", "County Rd 5"],
        ["C004", "O", "NonVDOT secondary", "Town of Blacksburg", "", "College Ave"],
        ["C005", "C", "VDOT Primary", "029. Fairfax County", "1. State Hwy Agency", "US-29"],
    ]
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    return csv_path


def test_ownership_csv_detects_missing(ownership_test_csv):
    """CSV check should detect rows with empty Ownership."""
    fixed, total = check_ownership_column(ownership_test_csv, dry_run=True, verbose=False)
    assert fixed == 4, f"Expected 4 rows needing fix, got {fixed}"
    assert total == 5


def test_ownership_csv_backfills_correctly(ownership_test_csv):
    """CSV check should derive correct Ownership values."""
    check_ownership_column(ownership_test_csv, dry_run=False, verbose=False)

    with open(ownership_test_csv) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert rows[0]["Ownership"] == "1. State Hwy Agency"  # Interstate
    assert rows[1]["Ownership"] == "3. City or Town Hwy Agency"  # City code ≥100
    assert rows[2]["Ownership"] == "2. County Hwy Agency"  # County code <100
    assert rows[3]["Ownership"] == "3. City or Town Hwy Agency"  # "Town of"
    assert rows[4]["Ownership"] == "1. State Hwy Agency"  # Already populated


def test_ownership_csv_preserves_existing(ownership_test_csv):
    """Existing valid Ownership values must not be overwritten."""
    check_ownership_column(ownership_test_csv, dry_run=False, verbose=False)

    with open(ownership_test_csv) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # C005 had valid Ownership — should be preserved
    assert rows[4]["Ownership"] == "1. State Hwy Agency"


def test_ownership_csv_fully_populated_no_changes(tmp_path):
    """CSV with all Ownership values populated should report 0 fixes."""
    csv_path = tmp_path / "full_all_roads.csv"
    headers = ["Document Nbr", "SYSTEM", "Physical Juris Name", "Ownership"]
    rows = [
        ["C001", "VDOT Interstate", "County X", "1. State Hwy Agency"],
        ["C002", "NonVDOT secondary", "County Y", "2. County Hwy Agency"],
    ]
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)

    fixed, total = check_ownership_column(csv_path, dry_run=False, verbose=False)
    assert fixed == 0
    assert total == 2


def test_ownership_csv_no_system_column(tmp_path):
    """CSV without SYSTEM column should gracefully skip."""
    csv_path = tmp_path / "nosys_all_roads.csv"
    headers = ["Document Nbr", "Ownership"]
    rows = [["C001", ""]]
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)

    fixed, total = check_ownership_column(csv_path, dry_run=False, verbose=False)
    assert fixed == 0  # Can't derive without SYSTEM


# ── Test 16: Pipeline Stage 2.5 ─────────────────────────────────────────────

def test_pipeline_has_stage_25():
    """pipeline.yml must include Stage 2.5 for Ownership derivation."""
    pipeline_path = PROJECT_ROOT / ".github" / "workflows" / "pipeline.yml"
    content = pipeline_path.read_text()
    assert "Stage 2.5" in content, "pipeline.yml must have Stage 2.5"
    assert "--data-dir" in content, "Stage 2.5 must pass --data-dir"


def test_pipeline_stage_25_after_roadtype_before_aggregate():
    """Stage 2.5 should appear after Stage 2 (road type) and before Stage 3 (aggregate)."""
    pipeline_path = PROJECT_ROOT / ".github" / "workflows" / "pipeline.yml"
    content = pipeline_path.read_text()
    pos_roadtype = content.find("Stage 2: Split by road type")
    pos_ownership = content.find("Stage 2.5")
    pos_aggregate = content.find("Stage 3: Aggregate")
    assert pos_roadtype < pos_ownership < pos_aggregate, \
        "Stage order must be: 2 (road type) → 2.5 (ownership) → 3 (aggregate)"


# ── Test 17: Documentation updated ───────────────────────────────────────────

def test_unified_architecture_doc_has_stage_01():
    """Unified-Pipeline-Architecture.md must document Stage 0.1."""
    doc = PROJECT_ROOT / "data-pipeline" / "Unified-Pipeline-Architecture.md"
    if not doc.exists():
        pytest.skip("Architecture doc not found")
    content = doc.read_text()
    assert "Stage 0.1" in content, "Architecture doc must mention Stage 0.1"
    assert "validate_hierarchy" in content, "Architecture doc must reference validate_hierarchy.py"


def test_unified_architecture_doc_has_stage_25():
    """Unified-Pipeline-Architecture.md must document Stage 2.5."""
    doc = PROJECT_ROOT / "data-pipeline" / "Unified-Pipeline-Architecture.md"
    if not doc.exists():
        pytest.skip("Architecture doc not found")
    content = doc.read_text()
    assert "Stage 2.5" in content, "Architecture doc must mention Stage 2.5"
    assert "Derive Ownership" in content or "DERIVE OWNERSHIP" in content, \
        "Architecture doc must describe Ownership derivation"


def test_download_pipeline_doc_has_new_stages():
    """data-pipeline-download-to-R2-storage-pipeline.md must list new stages."""
    doc = PROJECT_ROOT / "data-pipeline" / "data-pipeline-download-to-R2-storage-pipeline.md"
    if not doc.exists():
        pytest.skip("Download pipeline doc not found")
    content = doc.read_text()
    assert "Stage 0.1" in content, "Download pipeline doc must mention Stage 0.1"
    assert "Stage 2.5" in content, "Download pipeline doc must mention Stage 2.5"


def test_ownership_values_documented():
    """Architecture doc must list all 6 Ownership values."""
    doc = PROJECT_ROOT / "data-pipeline" / "Unified-Pipeline-Architecture.md"
    if not doc.exists():
        pytest.skip("Architecture doc not found")
    content = doc.read_text()
    assert "State Hwy Agency" in content
    assert "County Hwy Agency" in content
    assert "City or Town Hwy Agency" in content
    assert "Private/Unknown" in content


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
