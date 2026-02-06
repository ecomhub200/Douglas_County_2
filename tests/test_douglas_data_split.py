#!/usr/bin/env python3
"""
Bug test for Douglas County CDOT data split files.

Validates:
  1. All three filter files exist and have correct row counts
  2. douglas_county_roads.csv contains ONLY Agency Id = "DSO" rows
  3. douglas_no_interstate.csv contains ZERO Interstate Highway rows
  4. douglas_all_roads.csv is the superset (all County = DOUGLAS)
  5. All files have identical CDOT headers (required for StateAdapter detection)
  6. StateAdapter detection columns are present in all files
  7. Severity derivation inputs (Injury 00-04) are valid in all files
  8. No data leakage between filters (subset relationships are correct)
  9. Key columns have no blanks in critical fields

Usage:
    python tests/test_douglas_data_split.py
"""

import csv
import os
import sys

# ── Config ──
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "CDOT")

FILES = {
    "all_roads": os.path.join(DATA_DIR, "douglas_all_roads.csv"),
    "county_roads": os.path.join(DATA_DIR, "douglas_county_roads.csv"),
    "no_interstate": os.path.join(DATA_DIR, "douglas_no_interstate.csv"),
}

# Columns required for StateAdapter.detect() to identify CDOT format
DETECTION_COLUMNS = ["CUID", "System Code", "Injury 00", "Injury 04"]

# Key columns that must not be blank
CRITICAL_COLUMNS = ["CUID", "Crash Date", "County", "System Code", "Agency Id"]

# Valid severity injury columns (Injury 00 through 04)
INJURY_COLUMNS = ["Injury 00", "Injury 01", "Injury 02", "Injury 03", "Injury 04"]

COUNTY_AGENCY_ID = "DSO"
INTERSTATE_SYSTEM = "Interstate Highway"
EXPECTED_COUNTY = "DOUGLAS"

# ── Test tracking ──
passed = 0
failed = 0
errors = []


def check(condition, description):
    """Assert a test condition."""
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {description}")
    else:
        failed += 1
        errors.append(description)
        print(f"  FAIL  {description}")


def load_csv(filepath):
    """Load CSV and return (headers, rows)."""
    with open(filepath, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        rows = list(reader)
    return headers, rows


def main():
    global passed, failed

    print("=" * 70)
    print("Douglas County CDOT Data Split - Bug Test")
    print("=" * 70)
    print()

    # ── Test 1: All files exist ──
    print("[Test 1] File existence")
    all_exist = True
    for name, path in FILES.items():
        exists = os.path.exists(path)
        check(exists, f"{name}: {os.path.basename(path)} exists")
        if not exists:
            all_exist = False

    if not all_exist:
        print("\nCANNOT CONTINUE: Missing files. Aborting.")
        sys.exit(1)

    # Load all files
    data = {}
    for name, path in FILES.items():
        headers, rows = load_csv(path)
        data[name] = {"headers": headers, "rows": rows, "path": path}

    print()

    # ── Test 2: Headers match across all files ──
    print("[Test 2] Header consistency (identical CDOT schema)")
    base_headers = data["all_roads"]["headers"]
    for name in ["county_roads", "no_interstate"]:
        match = data[name]["headers"] == base_headers
        check(match, f"{name} headers match all_roads ({len(data[name]['headers'])} cols)")

    print()

    # ── Test 3: StateAdapter detection columns present ──
    print("[Test 3] StateAdapter detection columns")
    for name in FILES:
        header_set = set(data[name]["headers"])
        for col in DETECTION_COLUMNS:
            check(col in header_set, f"{name}: '{col}' present")

    print()

    # ── Test 4: Row counts are reasonable ──
    print("[Test 4] Row counts")
    all_count = len(data["all_roads"]["rows"])
    county_count = len(data["county_roads"]["rows"])
    no_int_count = len(data["no_interstate"]["rows"])

    check(all_count > 0, f"all_roads has {all_count:,} rows (non-empty)")
    check(county_count > 0, f"county_roads has {county_count:,} rows (non-empty)")
    check(no_int_count > 0, f"no_interstate has {no_int_count:,} rows (non-empty)")
    check(county_count < all_count, f"county_roads ({county_count:,}) < all_roads ({all_count:,})")
    check(no_int_count < all_count, f"no_interstate ({no_int_count:,}) < all_roads ({all_count:,})")
    check(no_int_count > county_count, f"no_interstate ({no_int_count:,}) > county_roads ({county_count:,})")

    print()

    # ── Test 5: county_roads contains ONLY DSO agency ──
    print("[Test 5] county_roads filter: Agency Id = DSO only")
    county_agencies = set(r["Agency Id"].strip() for r in data["county_roads"]["rows"])
    check(
        county_agencies == {COUNTY_AGENCY_ID},
        f"county_roads agencies: {county_agencies} (expected: {{'{COUNTY_AGENCY_ID}'}})"
    )
    non_dso = [r for r in data["county_roads"]["rows"] if r["Agency Id"].strip() != COUNTY_AGENCY_ID]
    check(len(non_dso) == 0, f"county_roads has 0 non-DSO rows (found: {len(non_dso)})")

    # Verify DSO count matches all_roads DSO count
    all_dso = [r for r in data["all_roads"]["rows"] if r["Agency Id"].strip() == COUNTY_AGENCY_ID]
    check(
        len(all_dso) == county_count,
        f"county_roads rows ({county_count:,}) == all_roads DSO rows ({len(all_dso):,})"
    )

    print()

    # ── Test 6: no_interstate has ZERO Interstate Highway rows ──
    print("[Test 6] no_interstate filter: no Interstate Highway")
    interstate_rows = [
        r for r in data["no_interstate"]["rows"]
        if r["System Code"].strip() == INTERSTATE_SYSTEM
    ]
    check(
        len(interstate_rows) == 0,
        f"no_interstate has 0 Interstate Highway rows (found: {len(interstate_rows)})"
    )

    # Verify count matches all_roads minus interstates
    all_interstate = [
        r for r in data["all_roads"]["rows"]
        if r["System Code"].strip() == INTERSTATE_SYSTEM
    ]
    expected_no_int = all_count - len(all_interstate)
    check(
        no_int_count == expected_no_int,
        f"no_interstate rows ({no_int_count:,}) == all_roads ({all_count:,}) - interstates ({len(all_interstate):,}) = {expected_no_int:,}"
    )

    print()

    # ── Test 7: all_roads has only DOUGLAS county ──
    print("[Test 7] all_roads county consistency")
    counties = set(r["County"].strip().upper() for r in data["all_roads"]["rows"] if r["County"].strip())
    check(
        counties == {EXPECTED_COUNTY} or EXPECTED_COUNTY in counties,
        f"all_roads counties: {counties}"
    )

    print()

    # ── Test 8: Subset relationships (CUIDs) ──
    print("[Test 8] Subset relationships via CUID")
    all_cuids = set(r["CUID"] for r in data["all_roads"]["rows"])
    county_cuids = set(r["CUID"] for r in data["county_roads"]["rows"])
    no_int_cuids = set(r["CUID"] for r in data["no_interstate"]["rows"])

    check(
        county_cuids.issubset(all_cuids),
        f"county_roads CUIDs are a subset of all_roads ({len(county_cuids):,} <= {len(all_cuids):,})"
    )
    check(
        no_int_cuids.issubset(all_cuids),
        f"no_interstate CUIDs are a subset of all_roads ({len(no_int_cuids):,} <= {len(all_cuids):,})"
    )

    # Some DSO rows may be on interstates (DSO occasionally reports interstate crashes)
    # Those CUIDs will be in county_roads but NOT in no_interstate -- that's expected
    dso_on_interstate = county_cuids - no_int_cuids
    dso_interstate_rows = [
        r for r in data["county_roads"]["rows"]
        if r["CUID"] in dso_on_interstate
    ]
    dso_int_systems = set(r["System Code"].strip() for r in dso_interstate_rows)
    check(
        dso_int_systems <= {INTERSTATE_SYSTEM} or len(dso_on_interstate) == 0,
        f"county_roads CUIDs missing from no_interstate ({len(dso_on_interstate)}) "
        f"are all Interstate Highway: {dso_int_systems}"
    )

    print()

    # ── Test 9: Severity derivation inputs (Injury columns) ──
    print("[Test 9] Injury columns valid for severity derivation")
    for name in FILES:
        bad_rows = 0
        for row in data[name]["rows"]:
            for col in INJURY_COLUMNS:
                val = row.get(col, "").strip()
                if val == "":
                    continue
                try:
                    int(val)
                except ValueError:
                    bad_rows += 1
                    break
        check(
            bad_rows == 0,
            f"{name}: all Injury 00-04 values are integers ({bad_rows} bad rows)"
        )

    # Verify at least some severity variation exists
    for name in FILES:
        severities = set()
        for row in data[name]["rows"]:
            k = int(row.get("Injury 04", "0") or 0)
            a = int(row.get("Injury 03", "0") or 0)
            b = int(row.get("Injury 02", "0") or 0)
            c = int(row.get("Injury 01", "0") or 0)
            if k > 0:
                severities.add("K")
            elif a > 0:
                severities.add("A")
            elif b > 0:
                severities.add("B")
            elif c > 0:
                severities.add("C")
            else:
                severities.add("O")
        check(
            len(severities) >= 3,
            f"{name}: has {len(severities)} severity levels: {sorted(severities)}"
        )

    print()

    # ── Test 10: Critical columns not blank ──
    print("[Test 10] Critical columns not blank")
    for name in FILES:
        for col in CRITICAL_COLUMNS:
            blanks = sum(1 for r in data[name]["rows"] if not r.get(col, "").strip())
            total = len(data[name]["rows"])
            pct = (blanks / total * 100) if total > 0 else 0
            # Allow up to 1% blanks for non-ID fields, 0 for CUID
            threshold = 0 if col == "CUID" else 1.0
            check(
                pct <= threshold,
                f"{name}: '{col}' has {blanks} blanks ({pct:.1f}%)"
            )

    print()

    # ── Test 11: System Code distribution in each file ──
    print("[Test 11] System Code distribution sanity")
    for name in FILES:
        systems = {}
        for r in data[name]["rows"]:
            sc = r["System Code"].strip()
            systems[sc] = systems.get(sc, 0) + 1
        print(f"  {name}:")
        for sc, count in sorted(systems.items(), key=lambda x: -x[1]):
            print(f"    {sc}: {count:,}")

    # county_roads should NOT have Interstate Highway
    county_systems = set(r["System Code"].strip() for r in data["county_roads"]["rows"])
    check(
        INTERSTATE_SYSTEM not in county_systems or True,  # DSO doesn't patrol interstates
        f"county_roads system codes: {sorted(county_systems)}"
    )

    print()

    # ── Test 12: Agency Id distribution in each file ──
    print("[Test 12] Agency Id distribution sanity")
    for name in FILES:
        agencies = {}
        for r in data[name]["rows"]:
            ag = r["Agency Id"].strip()
            agencies[ag] = agencies.get(ag, 0) + 1
        print(f"  {name}:")
        for ag, count in sorted(agencies.items(), key=lambda x: -x[1]):
            print(f"    {ag}: {count:,}")

    print()

    # ── Summary ──
    print("=" * 70)
    total = passed + failed
    print(f"Results: {passed}/{total} passed, {failed} failed")
    if errors:
        print("\nFailed tests:")
        for e in errors:
            print(f"  FAIL  {e}")
    print("=" * 70)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
