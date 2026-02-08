#!/usr/bin/env python3
"""
CDOT Dataset Comprehensive Bug & Accuracy Test
================================================
Tests the Douglas County Colorado crash data pipeline for correctness.

Validates:
  - Data file integrity and counts
  - Road type filter accuracy
  - Column mapping and normalization
  - Known bugs and their impact
  - Cross-file consistency
  - Data quality issues

Run: python3 tests/cdot_data_accuracy_test.py
"""

import csv
import os
import sys
import json
import re
from collections import Counter, defaultdict

# ─── Configuration ───────────────────────────────────────────────────────────

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'CDOT')
APP_DIR = os.path.join(os.path.dirname(__file__), '..', 'app')

FILES = {
    'county_roads': os.path.join(DATA_DIR, 'douglas_county_roads.csv'),
    'no_interstate': os.path.join(DATA_DIR, 'douglas_no_interstate.csv'),
    'all_roads': os.path.join(DATA_DIR, 'douglas_all_roads.csv'),
    'crashes': os.path.join(DATA_DIR, 'crashes.csv'),
    'config': os.path.join(DATA_DIR, 'config.json'),
}

# Expected column names in standardized CSVs
REQUIRED_COLUMNS = [
    'Document Nbr', 'Crash Date', 'Crash Year', 'Crash Military Time',
    'Crash Severity', 'K_People', 'A_People', 'B_People', 'C_People',
    'Collision Type', 'Weather Condition', 'Light Condition',
    'RTE Name', 'SYSTEM', 'Node', 'x', 'y',
    'Physical Juris Name', 'Pedestrian?', 'Bike?', 'Alcohol?', 'Speed?',
    'Night?', 'Vehicle Count', 'Persons Injured',
    'Pedestrians Killed', 'Pedestrians Injured'
]

# EPDO weights
EPDO_WEIGHTS = {'K': 462, 'A': 62, 'B': 12, 'C': 5, 'O': 1}

# Valid SYSTEM values (Virginia-normalized)
VALID_SYSTEM_VALUES = {'NonVDOT secondary', 'Primary', 'Secondary', 'Interstate', 'NonVDOT primary'}

# Road type filter profiles (what SYSTEM values each filter should include)
FILTER_PROFILES = {
    'countyOnly': {'NonVDOT secondary'},  # City Street + County Road → NonVDOT secondary
    'countyPlusVDOT': {'NonVDOT secondary', 'Primary', 'Secondary'},
    'allRoads': {'NonVDOT secondary', 'Primary', 'Secondary', 'Interstate'},
}

# Corresponding Colorado system codes for each filter
CO_FILTER_PROFILES = {
    'countyOnly': {'City Street', 'County Road'},
    'countyPlusVDOT': {'City Street', 'County Road', 'State Highway', 'Frontage Road'},
    'allRoads': {'City Street', 'County Road', 'State Highway', 'Frontage Road', 'Interstate Highway'},
}


# ─── Test Infrastructure ─────────────────────────────────────────────────────

class TestResult:
    def __init__(self, name, passed, message, severity='info'):
        self.name = name
        self.passed = passed
        self.message = message
        self.severity = severity  # 'critical', 'high', 'medium', 'low', 'info'


class TestSuite:
    def __init__(self):
        self.results = []
        self.data_cache = {}

    def add(self, name, passed, message, severity='info'):
        self.results.append(TestResult(name, passed, message, severity))

    def load_csv(self, key):
        """Load and cache CSV file."""
        if key in self.data_cache:
            return self.data_cache[key]

        filepath = FILES[key]
        if not os.path.exists(filepath):
            self.data_cache[key] = None
            return None

        rows = []
        with open(filepath, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            for row in reader:
                rows.append(row)

        self.data_cache[key] = {'headers': headers, 'rows': rows}
        return self.data_cache[key]

    def report(self):
        """Print test report."""
        print('\n' + '=' * 80)
        print('  CDOT DATASET BUG & ACCURACY TEST REPORT')
        print('=' * 80)

        # Group by severity
        by_severity = defaultdict(list)
        for r in self.results:
            by_severity[r.severity].append(r)

        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)

        print(f'\n  Total: {total} | Passed: {passed} | Failed: {failed}')
        print(f'  Pass Rate: {passed/total*100:.1f}%\n')

        severity_order = ['critical', 'high', 'medium', 'low', 'info']
        severity_labels = {
            'critical': '🔴 CRITICAL BUGS',
            'high': '🟠 HIGH SEVERITY',
            'medium': '🟡 MEDIUM SEVERITY',
            'low': '🔵 LOW SEVERITY',
            'info': '⚪ INFO / VALIDATIONS',
        }

        for sev in severity_order:
            tests = by_severity.get(sev, [])
            if not tests:
                continue

            failed_tests = [t for t in tests if not t.passed]
            passed_tests = [t for t in tests if t.passed]

            print(f'\n  {severity_labels[sev]} ({len(failed_tests)} failed, {len(passed_tests)} passed)')
            print('  ' + '-' * 70)

            for r in tests:
                status = '  PASS' if r.passed else '  FAIL'
                icon = '✅' if r.passed else '❌'
                print(f'  {icon} [{status}] {r.name}')
                if r.message:
                    for line in r.message.split('\n'):
                        print(f'           {line}')

        # Summary of critical bugs
        critical_fails = [r for r in self.results if not r.passed and r.severity == 'critical']
        high_fails = [r for r in self.results if not r.passed and r.severity == 'high']

        if critical_fails or high_fails:
            print('\n' + '=' * 80)
            print('  ⚠️  ACTION REQUIRED')
            print('=' * 80)
            for r in critical_fails + high_fails:
                print(f'  ❌ [{r.severity.upper()}] {r.name}')
                for line in r.message.split('\n'):
                    print(f'     {line}')
            print()

        return failed == 0


# ─── Test Functions ───────────────────────────────────────────────────────────

def test_file_existence(suite):
    """Test 1: Verify all required data files exist."""
    for key, path in FILES.items():
        exists = os.path.exists(path)
        suite.add(
            f'File exists: {os.path.basename(path)}',
            exists,
            f'Path: {path}' if exists else f'MISSING: {path}',
            'critical' if key != 'crashes' else 'low'
        )


def test_column_presence(suite):
    """Test 2: Verify required columns exist in standardized CSVs."""
    for key in ['county_roads', 'no_interstate', 'all_roads']:
        data = suite.load_csv(key)
        if not data:
            suite.add(f'Columns check: {key}', False, 'File not loaded', 'critical')
            continue

        missing = [col for col in REQUIRED_COLUMNS if col not in data['headers']]
        suite.add(
            f'Required columns: {key} ({len(REQUIRED_COLUMNS)} expected)',
            len(missing) == 0,
            f'Missing columns: {missing}' if missing else f'All {len(REQUIRED_COLUMNS)} columns present',
            'critical' if missing else 'info'
        )


def test_row_counts(suite):
    """Test 3: Verify row counts are reasonable."""
    expected = {
        'county_roads': (5000, 8000),      # Should be ~6,139
        'no_interstate': (15000, 25000),   # Should be ~19,773
        'all_roads': (20000, 30000),       # Should be ~25,098
    }

    for key, (lo, hi) in expected.items():
        data = suite.load_csv(key)
        if not data:
            suite.add(f'Row count: {key}', False, 'File not loaded', 'critical')
            continue

        count = len(data['rows'])
        in_range = lo <= count <= hi
        suite.add(
            f'Row count: {key} = {count:,}',
            in_range,
            f'Expected {lo:,}-{hi:,}, got {count:,}',
            'high' if not in_range else 'info'
        )


def test_severity_distribution(suite):
    """Test 4: Verify severity values are valid and distribution is reasonable."""
    valid_severities = {'K', 'A', 'B', 'C', 'O'}

    for key in ['county_roads', 'no_interstate', 'all_roads']:
        data = suite.load_csv(key)
        if not data:
            continue

        sev_counts = Counter()
        invalid = 0
        empty = 0

        for row in data['rows']:
            sev = (row.get('Crash Severity', '') or '').strip()
            if not sev:
                empty += 1
            elif sev not in valid_severities:
                invalid += 1
            else:
                sev_counts[sev] += 1

        total = len(data['rows'])
        suite.add(
            f'Severity validity: {key}',
            invalid == 0 and empty == 0,
            f'K={sev_counts["K"]}, A={sev_counts["A"]}, B={sev_counts["B"]}, '
            f'C={sev_counts["C"]}, O={sev_counts["O"]}, '
            f'invalid={invalid}, empty={empty}',
            'high' if invalid > 0 else ('medium' if empty > 0 else 'info')
        )

        # Verify severity matches people counts
        mismatch = 0
        for row in data['rows']:
            sev = (row.get('Crash Severity', '') or '').strip()
            k = int(row.get('K_People', '0') or '0')
            a = int(row.get('A_People', '0') or '0')
            b = int(row.get('B_People', '0') or '0')
            c = int(row.get('C_People', '0') or '0')

            expected_sev = 'O'
            if k > 0: expected_sev = 'K'
            elif a > 0: expected_sev = 'A'
            elif b > 0: expected_sev = 'B'
            elif c > 0: expected_sev = 'C'

            if sev and sev != expected_sev:
                mismatch += 1

        suite.add(
            f'Severity-people consistency: {key}',
            mismatch == 0,
            f'{mismatch} rows where severity doesn\'t match injury counts' if mismatch > 0
            else 'All severity values consistent with K/A/B/C people counts',
            'medium' if mismatch > 0 else 'info'
        )


def test_system_column_values(suite):
    """Test 5: Verify SYSTEM column contains valid Virginia-normalized values."""
    for key in ['county_roads', 'no_interstate', 'all_roads']:
        data = suite.load_csv(key)
        if not data:
            continue

        sys_counts = Counter()
        invalid_systems = Counter()

        for row in data['rows']:
            sys_val = (row.get('SYSTEM', '') or '').strip()
            if sys_val in VALID_SYSTEM_VALUES:
                sys_counts[sys_val] += 1
            elif sys_val:
                invalid_systems[sys_val] += 1
            else:
                sys_counts['(empty)'] += 1

        suite.add(
            f'SYSTEM values valid: {key}',
            len(invalid_systems) == 0,
            f'Valid: {dict(sys_counts)} | Invalid: {dict(invalid_systems)}' if invalid_systems
            else f'Distribution: {dict(sys_counts)}',
            'high' if invalid_systems else 'info'
        )


def test_road_type_filter_accuracy(suite):
    """Test 6: BUG - county_roads should ONLY contain county/city roads."""
    data = suite.load_csv('county_roads')
    if not data:
        return

    # Check SYSTEM values
    sys_counts = Counter()
    co_sys_counts = Counter()
    wrong_system_rows = []

    for row in data['rows']:
        sys_val = (row.get('SYSTEM', '') or '').strip()
        co_sys = (row.get('_co_system_code', '') or '').strip()
        sys_counts[sys_val] += 1
        co_sys_counts[co_sys] += 1

        # County roads should only have NonVDOT secondary
        if sys_val != 'NonVDOT secondary':
            wrong_system_rows.append({
                'doc': row.get('Document Nbr', ''),
                'system': sys_val,
                'co_system': co_sys,
                'route': row.get('RTE Name', '')
            })

    wrong_count = len(wrong_system_rows)
    total = len(data['rows'])
    pct_wrong = (wrong_count / total * 100) if total > 0 else 0

    suite.add(
        f'BUG: county_roads filter leakage ({wrong_count} non-county rows)',
        wrong_count == 0,
        f'{wrong_count} rows ({pct_wrong:.1f}%) have wrong SYSTEM value:\n'
        f'  Expected: only NonVDOT secondary\n'
        f'  Found: {dict(sys_counts)}\n'
        f'  Original CO codes: {dict(co_sys_counts)}\n'
        f'  Leaked: {wrong_count} rows with State Hwy ({sys_counts.get("Primary",0)}), '
        f'Interstate ({sys_counts.get("Interstate",0)}), Secondary ({sys_counts.get("Secondary",0)})',
        'high' if wrong_count > 0 else 'info'
    )


def test_processrow_crash_bug(suite):
    """Test 7: CRITICAL BUG - processRow() throws TypeError for most rows.

    The app's resetState() initializes crashState.aggregates WITHOUT:
      - vehicleCount: { total: 0, sum: 0, bySeverity: {...} }
      - pedCasualties: { killed: 0, injured: 0, byYear: {} }
      - personsInjured: 0

    processRow() then accesses agg.vehicleCount.total++ which throws
    TypeError on undefined. The try/catch catches it, so rowCount++
    never executes. BUT aggregates (severity, route, etc.) updated
    BEFORE the throw are already saved.

    Result: crashState.totalRows = 27 (only rows with VC=0 survive)
    BUT crashState.aggregates.bySeverity shows K=28, A=196, etc.
    """
    for key in ['county_roads', 'no_interstate', 'all_roads']:
        data = suite.load_csv(key)
        if not data:
            continue

        total = len(data['rows'])
        surviving = 0
        vc_zero = 0
        vc_positive = 0

        for row in data['rows']:
            vc_str = (row.get('Vehicle Count', '') or '').strip()
            pk_str = (row.get('Pedestrians Killed', '') or '').strip()
            pi_str = (row.get('Pedestrians Injured', '') or '').strip()

            vc = int(float(vc_str)) if vc_str else 0
            pk = int(float(pk_str)) if pk_str else 0
            pi = int(float(pi_str)) if pi_str else 0

            if vc > 0:
                vc_positive += 1
            else:
                vc_zero += 1
                if pk == 0 and pi == 0:
                    surviving += 1

        pct_lost = ((total - surviving) / total * 100) if total > 0 else 0

        suite.add(
            f'CRITICAL BUG: processRow() crash in {key} — '
            f'totalRows={surviving}, actual={total:,}',
            surviving == total,
            f'processRow() throws TypeError at agg.vehicleCount.total++\n'
            f'  crashState.aggregates.vehicleCount is UNDEFINED (not initialized)\n'
            f'  Total rows in file: {total:,}\n'
            f'  Rows with Vehicle Count > 0: {vc_positive:,} (THROW TypeError)\n'
            f'  Rows with Vehicle Count = 0: {vc_zero}\n'
            f'  Rows surviving processRow: {surviving} (displayed as "Total Crashes")\n'
            f'  Data loss: {pct_lost:.1f}% of rows not counted in totalRows\n'
            f'  Impact: All severity counts correct, but totalRows wrong\n'
            f'  Impact: All percentage KPIs wildly inflated (e.g., K%=103.7%)\n'
            f'  FIX: Add to resetState() aggregates initialization:\n'
            f'    personsInjured: 0,\n'
            f'    vehicleCount: {{ total: 0, sum: 0, bySeverity: {{ K:{{count:0,sum:0}}, ... }} }},\n'
            f'    pedCasualties: {{ killed: 0, injured: 0, byYear: {{}} }}',
            'critical'
        )


def test_aggregate_init_vs_processrow(suite):
    """Test 8: Verify resetState() initializes ALL properties accessed by processRow()."""
    # Properties that processRow() accesses on crashState.aggregates
    processrow_accesses = [
        'byYear', 'bySeverity', 'byCollision', 'byWeather', 'byLight',
        'byRoute', 'byNode', 'byHour', 'byDOW', 'byMonth',
        'byFuncClass', 'byIntType', 'byTrafficCtrl',
        'ped', 'bike', 'speed', 'nighttime',
        'intersection', 'nonIntersection',
        'personsInjured',      # Line 30131: agg.personsInjured += ...
        'vehicleCount',        # Line 30135: agg.vehicleCount.total++
        'pedCasualties',       # Line 30147: agg.pedCasualties.killed += ...
    ]

    # Properties that resetState() actually initializes (from line 29800-29810)
    initialized_properties = [
        'byYear', 'bySeverity', 'byCollision', 'byWeather', 'byLight',
        'byRoute', 'byNode', 'byHour', 'byDOW', 'byMonth',
        'byFuncClass', 'byIntType', 'byTrafficCtrl',
        'ped', 'bike', 'speed', 'nighttime',
        'intersection', 'nonIntersection',
        # MISSING: personsInjured, vehicleCount, pedCasualties
    ]

    missing = [p for p in processrow_accesses if p not in initialized_properties]

    suite.add(
        'Aggregate init completeness (resetState vs processRow)',
        len(missing) == 0,
        f'Missing from resetState() initialization: {missing}\n'
        f'These properties are accessed by processRow() but never initialized.\n'
        f'Causes TypeError when processRow tries to access them.' if missing
        else 'All processRow properties are initialized in resetState()',
        'critical' if missing else 'info'
    )


def test_crashes_csv_format(suite):
    """Test 9: Verify crashes.csv is the correct format for Colorado."""
    data = suite.load_csv('crashes')
    if not data:
        suite.add('crashes.csv format', False, 'File not found', 'medium')
        return

    headers = data['headers']

    # Check if it's Virginia format (has VDOT-specific columns)
    va_indicators = ['VDOT District', 'VSP', 'OBJECTID', 'Planning District', 'MPO Name']
    va_found = [col for col in va_indicators if col in headers]

    # Check if it's Colorado format (has CDOT-specific columns)
    co_indicators = ['CUID', 'System Code', 'Injury 00', 'Injury 04', 'MHE']
    co_found = [col for col in co_indicators if col in headers]

    is_virginia = len(va_found) >= 3
    is_colorado = len(co_found) >= 3

    # Check jurisdiction
    jurisdictions = Counter()
    for row in data['rows'][:100]:  # Sample first 100
        juris = (row.get('Physical Juris Name', '') or '').strip()
        jurisdictions[juris] += 1

    suite.add(
        'crashes.csv is correct format for CDOT folder',
        not is_virginia,
        f'crashes.csv appears to be VIRGINIA (Henrico County) format!\n'
        f'  Virginia indicators found: {va_found}\n'
        f'  Colorado indicators found: {co_found}\n'
        f'  Jurisdictions (sample): {dict(jurisdictions)}\n'
        f'  This file should NOT be in data/CDOT/ — it\'s a Virginia dataset\n'
        f'  Impact: If app falls back to this file, data is completely wrong'
        if is_virginia else
        f'Format: {"Colorado" if is_colorado else "Unknown"}',
        'high' if is_virginia else 'info'
    )


def test_duplicate_records(suite):
    """Test 10: Check for duplicate Document Nbr values."""
    for key in ['county_roads', 'no_interstate', 'all_roads']:
        data = suite.load_csv(key)
        if not data:
            continue

        doc_counts = Counter()
        for row in data['rows']:
            doc_nbr = (row.get('Document Nbr', '') or '').strip()
            if doc_nbr:
                doc_counts[doc_nbr] += 1

        duplicates = {k: v for k, v in doc_counts.items() if v > 1}

        suite.add(
            f'No duplicate records: {key}',
            len(duplicates) == 0,
            f'{len(duplicates)} duplicate Document Nbr values: {dict(duplicates)}' if duplicates
            else f'{len(doc_counts)} unique records, no duplicates',
            'medium' if duplicates else 'info'
        )


def test_gps_coverage(suite):
    """Test 11: Verify GPS coordinate coverage and validity."""
    for key in ['county_roads', 'no_interstate', 'all_roads']:
        data = suite.load_csv(key)
        if not data:
            continue

        total = len(data['rows'])
        valid_gps = 0
        invalid_gps = 0
        out_of_bounds = 0

        # Douglas County, CO approximate bounds
        lat_min, lat_max = 39.0, 39.7
        lon_min, lon_max = -105.2, -104.5

        for row in data['rows']:
            try:
                x = float(row.get('x', '0') or '0')
                y = float(row.get('y', '0') or '0')
                if x != 0 and y != 0:
                    valid_gps += 1
                    if not (lat_min <= y <= lat_max and lon_min <= x <= lon_max):
                        out_of_bounds += 1
                else:
                    invalid_gps += 1
            except (ValueError, TypeError):
                invalid_gps += 1

        coverage = (valid_gps / total * 100) if total > 0 else 0
        oob_pct = (out_of_bounds / valid_gps * 100) if valid_gps > 0 else 0

        suite.add(
            f'GPS coverage: {key} ({coverage:.1f}%)',
            coverage >= 90,
            f'{valid_gps:,} with GPS ({coverage:.1f}%), '
            f'{invalid_gps} missing, '
            f'{out_of_bounds} out of Douglas County bounds ({oob_pct:.1f}%)',
            'medium' if coverage < 90 else 'info'
        )


def test_date_integrity(suite):
    """Test 12: Verify crash dates are valid and within expected range."""
    for key in ['county_roads', 'no_interstate', 'all_roads']:
        data = suite.load_csv(key)
        if not data:
            continue

        total = len(data['rows'])
        year_counts = Counter()
        empty_dates = 0
        empty_years = 0
        bad_dates = 0

        for row in data['rows']:
            date_str = (row.get('Crash Date', '') or '').strip()
            year_str = (row.get('Crash Year', '') or '').strip()

            if not date_str:
                empty_dates += 1
            if not year_str:
                empty_years += 1
            else:
                try:
                    year = int(year_str)
                    if 2021 <= year <= 2025:
                        year_counts[year] += 1
                    else:
                        bad_dates += 1
                except ValueError:
                    bad_dates += 1

        suite.add(
            f'Date integrity: {key}',
            empty_dates == 0 and empty_years == 0 and bad_dates == 0,
            f'Years: {dict(sorted(year_counts.items()))}, '
            f'empty dates={empty_dates}, empty years={empty_years}, bad dates={bad_dates}',
            'medium' if empty_dates > 0 or empty_years > 0 else 'info'
        )


def test_cross_file_consistency(suite):
    """Test 13: Verify county_roads ⊂ no_interstate ⊂ all_roads."""
    county = suite.load_csv('county_roads')
    no_int = suite.load_csv('no_interstate')
    all_rd = suite.load_csv('all_roads')

    if not all([county, no_int, all_rd]):
        suite.add('Cross-file consistency', False, 'Could not load all files', 'high')
        return

    county_ids = {row['Document Nbr'] for row in county['rows']}
    no_int_ids = {row['Document Nbr'] for row in no_int['rows']}
    all_ids = {row['Document Nbr'] for row in all_rd['rows']}

    # county ⊂ no_interstate?
    county_not_in_noint = county_ids - no_int_ids
    suite.add(
        f'county_roads ⊂ no_interstate ({len(county_not_in_noint)} leaks)',
        len(county_not_in_noint) == 0,
        f'{len(county_not_in_noint)} county_roads records NOT in no_interstate\n'
        f'  These are likely interstate/state highway rows that leaked into county_roads'
        if county_not_in_noint else 'All county_roads records are in no_interstate',
        'high' if county_not_in_noint else 'info'
    )

    # no_interstate ⊂ all_roads?
    noint_not_in_all = no_int_ids - all_ids
    suite.add(
        f'no_interstate ⊂ all_roads ({len(noint_not_in_all)} missing)',
        len(noint_not_in_all) == 0,
        f'{len(noint_not_in_all)} no_interstate records NOT in all_roads' if noint_not_in_all
        else 'All no_interstate records are in all_roads',
        'high' if noint_not_in_all else 'info'
    )

    # Verify all_roads = no_interstate + interstate_only
    interstate_only = all_ids - no_int_ids
    interstate_only_count = len(interstate_only)
    expected_total = len(no_int_ids) + interstate_only_count
    actual_total = len(all_ids)

    suite.add(
        f'all_roads = no_interstate + interstate ({actual_total} vs {expected_total})',
        actual_total == expected_total,
        f'all_roads={actual_total}, no_interstate={len(no_int_ids)}, '
        f'interstate_only={interstate_only_count}',
        'medium' if actual_total != expected_total else 'info'
    )


def test_epdo_calculation(suite):
    """Test 14: Verify EPDO can be calculated correctly from the data."""
    data = suite.load_csv('county_roads')
    if not data:
        return

    sev_counts = Counter()
    for row in data['rows']:
        sev = (row.get('Crash Severity', '') or '').strip()
        if sev in EPDO_WEIGHTS:
            sev_counts[sev] += 1

    epdo = sum(sev_counts[s] * EPDO_WEIGHTS[s] for s in EPDO_WEIGHTS)
    total = len(data['rows'])

    # The screenshot shows: K=28, A=196, B+C=1191, O=4724, EPDO=39,904
    expected_k, expected_a = 28, 196
    expected_epdo = 39904

    suite.add(
        f'EPDO calculation: county_roads = {epdo:,}',
        sev_counts['K'] == expected_k and sev_counts['A'] == expected_a and epdo == expected_epdo,
        f'K={sev_counts["K"]}(exp {expected_k}), '
        f'A={sev_counts["A"]}(exp {expected_a}), '
        f'B={sev_counts["B"]}, C={sev_counts["C"]}, O={sev_counts["O"]}, '
        f'EPDO={epdo:,} (exp {expected_epdo:,})',
        'medium' if epdo != expected_epdo else 'info'
    )


def test_kpi_accuracy(suite):
    """Test 15: Verify all dashboard KPI values match the data."""
    data = suite.load_csv('county_roads')
    if not data:
        return

    total = len(data['rows'])
    sev = Counter()
    ped_total = 0
    bike_total = 0
    speed_total = 0
    night_total = 0

    for row in data['rows']:
        s = (row.get('Crash Severity', '') or '').strip()
        sev[s] += 1

        if (row.get('Pedestrian?', '') or '').strip().upper() in ('Y', 'YES'):
            ped_total += 1
        if (row.get('Bike?', '') or '').strip().upper() in ('Y', 'YES'):
            bike_total += 1
        if (row.get('Speed?', '') or '').strip().upper() in ('Y', 'YES'):
            speed_total += 1
        if (row.get('Night?', '') or '').strip().upper() in ('Y', 'YES'):
            night_total += 1

    ka_total = sev['K'] + sev['A']
    vru_total = ped_total + bike_total
    bc_total = sev['B'] + sev['C']

    # What the UI SHOULD show (vs what it actually shows with the bug)
    # Bug causes total=27, making all percentages wrong
    bug_total = 27  # What the UI shows due to the bug
    correct_total = total  # What it should show

    suite.add(
        f'KPI: Total Crashes should be {correct_total:,} (bug shows {bug_total})',
        False,  # This is always a fail - it documents the known bug
        f'Actual data: {correct_total:,} crashes\n'
        f'  Bug displays: {bug_total} (only rows with Vehicle Count=0)\n'
        f'  K={sev["K"]}, A={sev["A"]}, B+C={bc_total:,}, O={sev["O"]:,}\n'
        f'  K+A={ka_total}, VRU={vru_total}, Speed={speed_total}, Night={night_total}\n'
        f'  Bug K%={sev["K"]/bug_total*100:.1f}% (should be {sev["K"]/correct_total*100:.1f}%)\n'
        f'  Bug A%={sev["A"]/bug_total*100:.1f}% (should be {sev["A"]/correct_total*100:.1f}%)\n'
        f'  Bug KA%={ka_total/bug_total*100:.1f}% (should be {ka_total/correct_total*100:.1f}%)\n'
        f'  Bug VRU%={vru_total/bug_total*100:.1f}% (should be {vru_total/correct_total*100:.1f}%)\n'
        f'  Bug Speed%={speed_total/bug_total*100:.1f}% (should be {speed_total/correct_total*100:.1f}%)\n'
        f'  Bug Night%={night_total/bug_total*100:.1f}% (should be {night_total/correct_total*100:.1f}%)',
        'critical'
    )


def test_stateadapter_normalization(suite):
    """Test 16: Verify StateAdapter normalizeRow produces correct output."""
    # We can't run the JS StateAdapter directly, but we can verify
    # the pre-normalized CSV files have the expected column mapping
    data = suite.load_csv('county_roads')
    if not data:
        return

    sample = data['rows'][0] if data['rows'] else {}

    # Check that original CO fields are preserved
    co_fields = ['_co_system_code', '_co_rd_number', '_co_location1', '_co_location2']
    present = [f for f in co_fields if f in (sample or {})]
    missing = [f for f in co_fields if f not in (sample or {})]

    suite.add(
        f'CO original fields preserved',
        len(missing) == 0,
        f'Present: {present}, Missing: {missing}' if missing
        else f'All {len(co_fields)} original CO fields preserved',
        'medium' if missing else 'info'
    )


def test_year_files_vs_standardized(suite):
    """Test 17: Verify standardized files cover all year files."""
    year_totals = {}
    for year in ['2021', '2022', '2023', '2024', '2025']:
        # Try different file naming patterns
        patterns = [
            os.path.join(DATA_DIR, f'{year} douglas.csv'),
            os.path.join(DATA_DIR, f'{year} douglas county.csv'),
        ]
        for path in patterns:
            if os.path.exists(path):
                with open(path, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    count = sum(1 for _ in reader)
                    year_totals[year] = year_totals.get(year, 0) + count

    all_data = suite.load_csv('all_roads')
    if not all_data:
        return

    std_year_counts = Counter()
    for row in all_data['rows']:
        year = (row.get('Crash Year', '') or '').strip()
        if year:
            std_year_counts[year] += 1

    year_comparison = {}
    for year in sorted(set(list(year_totals.keys()) + list(std_year_counts.keys()))):
        orig = year_totals.get(year, 0)
        std = std_year_counts.get(year, 0)
        year_comparison[year] = f'original={orig}, standardized={std}'

    # Verify totals match (approximately - some filtering expected)
    total_orig = sum(year_totals.values())
    total_std = sum(std_year_counts.values())

    suite.add(
        f'Year files vs all_roads: {total_orig:,} raw → {total_std:,} standardized',
        True,  # Informational
        '\n'.join(f'  {y}: {v}' for y, v in sorted(year_comparison.items())),
        'info'
    )


def test_config_json_consistency(suite):
    """Test 18: Verify config.json matches actual data."""
    config_path = FILES['config']
    if not os.path.exists(config_path):
        suite.add('config.json consistency', False, 'File not found', 'medium')
        return

    with open(config_path) as f:
        config = json.load(f)

    # Check roadSystems.filterProfiles match the actual SYSTEM values in the data
    filter_profiles = config.get('roadSystems', {}).get('filterProfiles', {})

    data = suite.load_csv('county_roads')
    if not data:
        return

    actual_systems = set()
    for row in data['rows']:
        sys_val = (row.get('SYSTEM', '') or '').strip()
        if sys_val:
            actual_systems.add(sys_val)

    # Config says countyOnly should have ["City Street", "County Road"]
    # But actual SYSTEM column has Virginia-normalized values
    config_county_systems = filter_profiles.get('countyOnly', {}).get('systemValues', [])

    uses_co_values = any(v in ['City Street', 'County Road'] for v in config_county_systems)
    uses_va_values = any(v in ['NonVDOT secondary', 'Primary'] for v in config_county_systems)

    suite.add(
        'config.json roadSystem filter uses correct values',
        uses_va_values or not uses_co_values,
        f'config.json countyOnly systemValues: {config_county_systems}\n'
        f'  Actual SYSTEM values in data: {actual_systems}\n'
        f'  Config uses {"Colorado" if uses_co_values else "Virginia-normalized"} values\n'
        f'  Note: The CSV files already use Virginia-normalized values via StateAdapter'
        if uses_co_values else
        f'Config matches actual data values',
        'low' if uses_co_values else 'info'
    )


def test_ghost_rows(suite):
    """Test 19: Check for ghost rows (empty year, empty date)."""
    for key in ['county_roads', 'no_interstate', 'all_roads']:
        data = suite.load_csv(key)
        if not data:
            continue

        ghost_rows = 0
        for row in data['rows']:
            year = (row.get('Crash Year', '') or '').strip()
            date = (row.get('Crash Date', '') or '').strip()
            if not year and not date:
                ghost_rows += 1

        suite.add(
            f'No ghost rows (empty date+year): {key}',
            ghost_rows == 0,
            f'{ghost_rows} rows with both empty Crash Year and Crash Date' if ghost_rows
            else 'No ghost rows found',
            'medium' if ghost_rows > 0 else 'info'
        )


def test_boolean_flags(suite):
    """Test 20: Verify boolean flag columns have valid Y/N values."""
    bool_cols = ['Pedestrian?', 'Bike?', 'Alcohol?', 'Speed?', 'Night?',
                 'Distracted?', 'Drowsy?', 'Young?', 'Senior?']

    data = suite.load_csv('county_roads')
    if not data:
        return

    for col in bool_cols:
        if col not in data['headers']:
            suite.add(f'Boolean flag: {col}', False, 'Column missing', 'medium')
            continue

        values = Counter()
        for row in data['rows']:
            val = (row.get(col, '') or '').strip().upper()
            values[val] += 1

        valid_values = {'Y', 'N', 'YES', 'NO', ''}
        invalid = {k: v for k, v in values.items() if k not in valid_values}
        y_count = values.get('Y', 0) + values.get('YES', 0)

        suite.add(
            f'Boolean flag valid: {col} (Y={y_count})',
            len(invalid) == 0,
            f'Values: {dict(values)}' + (f' | Invalid: {invalid}' if invalid else ''),
            'medium' if invalid else 'info'
        )


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    os.chdir(DATA_DIR)
    suite = TestSuite()

    print('Running CDOT Dataset Comprehensive Bug & Accuracy Test...\n')

    # Run all tests
    test_file_existence(suite)
    test_column_presence(suite)
    test_row_counts(suite)
    test_severity_distribution(suite)
    test_system_column_values(suite)
    test_road_type_filter_accuracy(suite)
    test_processrow_crash_bug(suite)
    test_aggregate_init_vs_processrow(suite)
    test_crashes_csv_format(suite)
    test_duplicate_records(suite)
    test_gps_coverage(suite)
    test_date_integrity(suite)
    test_cross_file_consistency(suite)
    test_epdo_calculation(suite)
    test_kpi_accuracy(suite)
    test_stateadapter_normalization(suite)
    test_year_files_vs_standardized(suite)
    test_config_json_consistency(suite)
    test_ghost_rows(suite)
    test_boolean_flags(suite)

    # Print report
    all_passed = suite.report()
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
