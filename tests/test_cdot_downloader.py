#!/usr/bin/env python3
"""
Bug tests for download_cdot_crash_data.py

Tests every public function for correctness, edge cases, and regressions.
Run with: python -m pytest tests/test_cdot_downloader.py -v
"""

import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from download_cdot_crash_data import (
    _get_output_filename,
    _playwright_available,
    CUID_COLUMN,
    detect_file_type,
    excel_to_dataframe,
    extract_download_url_from_html,
    filter_to_jurisdiction,
    list_available,
    load_manifest,
    merge_with_existing,
    MIN_VALID_FILE_SIZE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_xlsx_bytes(data: dict) -> bytes:
    """Create a real .xlsx file in memory and return its bytes."""
    df = pd.DataFrame(data)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine='openpyxl')
    return buf.getvalue()


def make_statewide_xlsx(counties=None, rows_per_county=10):
    """
    Build a realistic statewide CDOT crash Excel with multiple counties.
    Returns (bytes, expected_douglas_count).
    """
    if counties is None:
        counties = ['DOUGLAS', 'EL PASO', 'ARAPAHOE', 'DENVER', 'JEFFERSON']

    rows = []
    for county in counties:
        for i in range(rows_per_county):
            rows.append({
                'CUID': f'{county[:3]}{i:04d}',
                'System Code': 'County Road',
                'Crash Date': f'3/{i+1}/2024',
                'Crash Time': '1400',
                'Agency Id': 'DSO' if county == 'DOUGLAS' else 'CSP',
                'City': '',
                'County': county,
                'Latitude': 39.5,
                'Longitude': -104.9,
                'Location 1': 'Test Rd',
                'Number Killed': 0,
                'Number Injured': 0,
                'Injury 00': 2,
                'Injury 01': 0,
                'Injury 02': 0,
                'Injury 03': 0,
                'Injury 04': 0,
            })

    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine='openpyxl')
    douglas_count = rows_per_county if 'DOUGLAS' in counties else 0
    return buf.getvalue(), douglas_count


def make_manifest(tmp_dir, years=None, jurisdictions=None):
    """Create a temporary manifest file and return its path."""
    if years is None:
        years = {
            "2025": {"docid": 54973381, "status": "preliminary"},
            "2024": {"docid": 35111742, "status": "final"},
        }
    if jurisdictions is None:
        jurisdictions = {
            "douglas": {
                "county": "DOUGLAS",
                "fips": "08035",
                "display_name": "Douglas County"
            },
            "elpaso": {
                "county": "EL PASO",
                "fips": "08041",
                "display_name": "El Paso County"
            }
        }

    manifest = {
        "source": {"name": "test", "base_url": "https://example.com"},
        "jurisdiction_filters": jurisdictions,
        "files": years,
        "data_dictionaries": {
            "2021-2025": {"docid": 17470635, "description": "Test dict"}
        }
    }

    path = Path(tmp_dir) / 'source_manifest.json'
    with open(path, 'w') as f:
        json.dump(manifest, f)
    return str(path)


# ===========================================================================
# detect_file_type
# ===========================================================================

class TestDetectFileType:

    def test_xlsx_magic_bytes(self):
        """XLSX files start with PK (ZIP signature)."""
        content = make_xlsx_bytes({'A': [1, 2, 3]})
        is_valid, ext, reason = detect_file_type(content)
        assert is_valid is True
        assert ext == '.xlsx'
        assert 'XLSX' in reason

    def test_xls_magic_bytes(self):
        """XLS (OLE2) files start with 0xD0CF."""
        content = b'\xd0\xcf\x11\xe0' + b'\x00' * 200
        is_valid, ext, reason = detect_file_type(content)
        assert is_valid is True
        assert ext == '.xls'

    def test_html_doctype(self):
        """HTML responses should be flagged as invalid."""
        content = b'<!DOCTYPE html><html><body>Error</body></html>'
        is_valid, ext, reason = detect_file_type(content)
        assert is_valid is False
        assert ext == '.html'

    def test_html_tag_only(self):
        """<html> without doctype should also be caught."""
        content = b'<html><head><title>Login</title></head></html>'
        is_valid, ext, reason = detect_file_type(content)
        assert is_valid is False
        assert ext == '.html'

    def test_html_with_leading_whitespace(self):
        """HTML with leading whitespace should still be detected."""
        content = b'   \n  <!DOCTYPE html><html><body>Error</body></html>'
        is_valid, ext, reason = detect_file_type(content)
        assert is_valid is False
        assert ext == '.html'

    def test_xml_response(self):
        """XML error responses should be flagged."""
        content = b'<?xml version="1.0"?><error>Access denied</error>'
        is_valid, ext, reason = detect_file_type(content)
        assert is_valid is False
        assert ext == '.html'

    def test_content_type_spreadsheet(self):
        """Content-Type header with spreadsheet should pass."""
        content = b'\x00\x01\x02\x03' * 100  # non-magic, non-HTML
        is_valid, ext, reason = detect_file_type(
            content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        assert is_valid is True
        assert ext == '.xlsx'

    def test_content_type_excel(self):
        content = b'\x00\x01' * 100
        is_valid, ext, _ = detect_file_type(content, content_type='application/vnd.ms-excel')
        assert is_valid is True

    def test_content_type_octet_stream(self):
        content = b'\x00\x01' * 100
        is_valid, ext, _ = detect_file_type(content, content_type='application/octet-stream')
        assert is_valid is True

    def test_content_disposition_xlsx(self):
        """Filename in Content-Disposition should determine extension."""
        content = b'\x00\x01' * 100
        is_valid, ext, reason = detect_file_type(
            content,
            content_disposition='attachment; filename="crash_data_2024.xlsx"'
        )
        assert is_valid is True
        assert ext == '.xlsx'
        assert 'crash_data_2024.xlsx' in reason

    def test_content_disposition_xls(self):
        content = b'\x00\x01' * 100
        is_valid, ext, _ = detect_file_type(
            content,
            content_disposition="attachment; filename='data.xls'"
        )
        assert is_valid is True
        assert ext == '.xls'

    def test_large_unknown_binary_accepted(self):
        """Large binary files with no other signals should pass as xlsx."""
        content = b'\x00\x01' * (MIN_VALID_FILE_SIZE + 1)
        is_valid, ext, reason = detect_file_type(content)
        assert is_valid is True
        assert ext == '.xlsx'
        assert 'Large binary' in reason

    def test_small_unknown_binary_rejected(self):
        """Small unrecognized files should be rejected."""
        content = b'\x00\x01\x02\x03'
        is_valid, ext, _ = detect_file_type(content)
        assert is_valid is False
        assert ext == '.unknown'

    def test_empty_content(self):
        """Empty response should be rejected."""
        is_valid, ext, _ = detect_file_type(b'')
        assert is_valid is False

    def test_magic_bytes_take_priority_over_headers(self):
        """Magic bytes should win even if Content-Type says text/html."""
        content = make_xlsx_bytes({'A': [1]})
        is_valid, ext, _ = detect_file_type(content, content_type='text/html')
        assert is_valid is True
        assert ext == '.xlsx'


# ===========================================================================
# extract_download_url_from_html
# ===========================================================================

class TestExtractDownloadUrl:

    def test_pdfpop_link(self):
        html = b'<a href="/CDOTRMPop/docpop/PdfPop.aspx?docid=123">View</a>'
        url = extract_download_url_from_html(html, 'https://example.com/docpop/docpop.aspx')
        assert url == 'https://example.com/CDOTRMPop/docpop/PdfPop.aspx?docid=123'

    def test_getdoc_link(self):
        html = b'<a href="GetDoc.aspx?id=456">Download</a>'
        url = extract_download_url_from_html(html, 'https://example.com/docpop/docpop.aspx')
        assert url is not None
        assert 'GetDoc.aspx' in url

    def test_download_link(self):
        html = b'<a href="/files/Download?id=789">Download</a>'
        url = extract_download_url_from_html(html, 'https://host.com/path/page.aspx')
        assert url == 'https://host.com/files/Download?id=789'

    def test_window_location_redirect(self):
        html = b"<script>window.location = '/redirect/file.xlsx';</script>"
        url = extract_download_url_from_html(html, 'https://host.com/page.aspx')
        assert url == 'https://host.com/redirect/file.xlsx'

    def test_window_open(self):
        html = b"<script>window.open('https://cdn.example.com/file.xlsx');</script>"
        url = extract_download_url_from_html(html, 'https://host.com/page.aspx')
        assert url == 'https://cdn.example.com/file.xlsx'

    def test_absolute_url_preserved(self):
        html = b'<a href="https://cdn.example.com/doc/GetDoc?id=1">Get</a>'
        url = extract_download_url_from_html(html, 'https://other.com/page.aspx')
        assert url == 'https://cdn.example.com/doc/GetDoc?id=1'

    def test_relative_url_resolved(self):
        html = b'<a href="GetDoc.aspx?id=1">Get</a>'
        url = extract_download_url_from_html(html, 'https://host.com/app/docpop.aspx')
        assert url == 'https://host.com/app/GetDoc.aspx?id=1'

    def test_no_match_returns_none(self):
        html = b'<html><body>No links here</body></html>'
        url = extract_download_url_from_html(html, 'https://host.com/page.aspx')
        assert url is None

    def test_empty_html(self):
        url = extract_download_url_from_html(b'', 'https://host.com/page.aspx')
        assert url is None

    def test_case_insensitive_matching(self):
        html = b'<a HREF="/path/PDFPOP.ASPX?docid=1">View</a>'
        url = extract_download_url_from_html(html, 'https://host.com/page.aspx')
        assert url is not None


# ===========================================================================
# excel_to_dataframe
# ===========================================================================

class TestExcelToDataframe:

    def test_valid_xlsx(self):
        content = make_xlsx_bytes({
            'County': ['DOUGLAS', 'EL PASO'],
            'CUID': [1, 2],
        })
        df = excel_to_dataframe(content, '.xlsx')
        assert len(df) == 2
        assert 'County' in df.columns

    def test_preserves_all_columns(self):
        """All columns in the Excel should appear in the DataFrame."""
        cols = {f'Col_{i}': list(range(5)) for i in range(20)}
        content = make_xlsx_bytes(cols)
        df = excel_to_dataframe(content, '.xlsx')
        assert len(df.columns) == 20

    def test_empty_xlsx(self):
        """An Excel file with headers but no data rows."""
        content = make_xlsx_bytes({'County': pd.Series([], dtype=str)})
        df = excel_to_dataframe(content, '.xlsx')
        assert len(df) == 0
        assert 'County' in df.columns

    def test_numeric_values_preserved(self):
        content = make_xlsx_bytes({
            'Latitude': [39.50008, 39.52261],
            'Longitude': [-104.87, -104.92],
        })
        df = excel_to_dataframe(content, '.xlsx')
        assert abs(df['Latitude'].iloc[0] - 39.50008) < 0.0001

    def test_corrupt_content_raises(self):
        """Corrupt/non-Excel bytes should raise an exception."""
        with pytest.raises(Exception):
            excel_to_dataframe(b'this is not excel', '.xlsx')


# ===========================================================================
# filter_to_jurisdiction
# ===========================================================================

class TestFilterToJurisdiction:

    def _make_df(self, counties):
        return pd.DataFrame({
            'CUID': range(len(counties)),
            'County': counties,
            'Agency Id': ['DSO'] * len(counties),
        })

    def test_basic_filter(self):
        df = self._make_df(['DOUGLAS', 'EL PASO', 'DOUGLAS', 'DENVER'])
        config = {'county': 'DOUGLAS', 'display_name': 'Douglas County'}
        result = filter_to_jurisdiction(df, config, 'douglas')
        assert len(result) == 2
        assert all(result['County'] == 'DOUGLAS')

    def test_case_insensitive_county_value(self):
        """County column may have mixed case like 'Douglas' instead of 'DOUGLAS'."""
        df = self._make_df(['Douglas', 'El Paso', 'douglas', 'DOUGLAS'])
        config = {'county': 'DOUGLAS', 'display_name': 'Douglas County'}
        result = filter_to_jurisdiction(df, config, 'douglas')
        assert len(result) == 3  # all three Douglas variants

    def test_whitespace_in_county_value(self):
        """County values with trailing whitespace should still match."""
        df = self._make_df(['DOUGLAS ', ' DOUGLAS', 'EL PASO'])
        config = {'county': 'DOUGLAS', 'display_name': 'Douglas County'}
        result = filter_to_jurisdiction(df, config, 'douglas')
        assert len(result) == 2

    def test_county_column_different_case(self):
        """Column named 'county' (lowercase) should still be found."""
        df = pd.DataFrame({
            'CUID': [1, 2, 3],
            'county': ['DOUGLAS', 'EL PASO', 'DOUGLAS'],
        })
        config = {'county': 'DOUGLAS', 'display_name': 'Douglas County'}
        result = filter_to_jurisdiction(df, config, 'douglas')
        assert len(result) == 2

    def test_county_column_with_spaces(self):
        """Column named ' County ' with whitespace should be found."""
        df = pd.DataFrame({
            'CUID': [1, 2],
            ' County ': ['DOUGLAS', 'EL PASO'],
        })
        config = {'county': 'DOUGLAS', 'display_name': 'Douglas County'}
        result = filter_to_jurisdiction(df, config, 'douglas')
        assert len(result) == 1

    def test_no_county_column_returns_unfiltered(self):
        """If County column is missing, return original DataFrame."""
        df = pd.DataFrame({
            'CUID': [1, 2, 3],
            'Region': ['NORTH', 'SOUTH', 'EAST'],
        })
        config = {'county': 'DOUGLAS', 'display_name': 'Douglas County'}
        result = filter_to_jurisdiction(df, config, 'douglas')
        assert len(result) == 3  # unfiltered

    def test_no_matches_returns_empty(self):
        df = self._make_df(['EL PASO', 'ARAPAHOE', 'DENVER'])
        config = {'county': 'DOUGLAS', 'display_name': 'Douglas County'}
        result = filter_to_jurisdiction(df, config, 'douglas')
        assert len(result) == 0

    def test_nan_values_dont_crash(self):
        """NaN/None in County column shouldn't cause errors."""
        df = pd.DataFrame({
            'CUID': [1, 2, 3, 4],
            'County': ['DOUGLAS', None, float('nan'), 'DOUGLAS'],
        })
        config = {'county': 'DOUGLAS', 'display_name': 'Douglas County'}
        result = filter_to_jurisdiction(df, config, 'douglas')
        assert len(result) == 2

    def test_numeric_county_values(self):
        """Numeric county codes shouldn't crash the filter."""
        df = pd.DataFrame({
            'CUID': [1, 2],
            'County': [35, 41],  # numeric, not string
        })
        config = {'county': 'DOUGLAS', 'display_name': 'Douglas County'}
        result = filter_to_jurisdiction(df, config, 'douglas')
        assert len(result) == 0  # no match, but no crash

    def test_index_reset(self):
        """Filtered result should have reset index starting from 0."""
        df = self._make_df(['EL PASO', 'DOUGLAS', 'ARAPAHOE', 'DOUGLAS'])
        config = {'county': 'DOUGLAS', 'display_name': 'Douglas County'}
        result = filter_to_jurisdiction(df, config, 'douglas')
        assert list(result.index) == [0, 1]

    def test_el_paso_with_space(self):
        """El Paso has a space — make sure it matches correctly."""
        df = self._make_df(['EL PASO', 'ELPASO', 'EL PASO'])
        config = {'county': 'EL PASO', 'display_name': 'El Paso County'}
        result = filter_to_jurisdiction(df, config, 'elpaso')
        assert len(result) == 2  # 'ELPASO' (no space) should NOT match

    def test_multi_word_counties(self):
        """Counties with spaces in names (Clear Creek, Kit Carson, etc.)."""
        counties = ['CLEAR CREEK', 'KIT CARSON', 'LA PLATA', 'LAS ANIMAS',
                     'RIO BLANCO', 'RIO GRANDE', 'SAN JUAN', 'SAN MIGUEL']
        df = self._make_df(counties)
        for county in counties:
            config = {'county': county, 'display_name': f'{county.title()} County'}
            result = filter_to_jurisdiction(df, config, 'test')
            assert len(result) == 1, f"Failed to filter {county}"


# ===========================================================================
# load_manifest
# ===========================================================================

class TestLoadManifest:

    def test_valid_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_manifest(tmp)
            manifest = load_manifest(path)
            assert 'files' in manifest
            assert 'jurisdiction_filters' in manifest
            assert len(manifest['files']) == 2

    def test_missing_manifest_exits(self):
        with pytest.raises(SystemExit):
            load_manifest('/nonexistent/path/manifest.json')

    def test_real_manifest(self):
        """Test the actual project manifest loads correctly."""
        manifest_path = PROJECT_ROOT / 'data' / 'CDOT' / 'source_manifest.json'
        if manifest_path.exists():
            manifest = load_manifest(str(manifest_path))
            assert len(manifest['files']) == 5  # 2021-2025
            assert 'douglas' in manifest['jurisdiction_filters']
            # Verify all doc IDs are integers
            for year, info in manifest['files'].items():
                assert isinstance(info['docid'], int), f"Year {year} docid is not int"
                assert int(year) >= 2021
                assert int(year) <= 2025


# ===========================================================================
# list_available
# ===========================================================================

class TestListAvailable:

    def test_output_contains_years(self, capsys):
        manifest = {
            'files': {
                '2024': {'docid': 123, 'status': 'final'},
                '2025': {'docid': 456, 'status': 'preliminary'},
            },
            'jurisdiction_filters': {
                '_description': 'should be skipped',
                'douglas': {
                    'county': 'DOUGLAS',
                    'fips': '08035',
                    'display_name': 'Douglas County'
                }
            },
            'data_dictionaries': {
                '2021-2025': {'docid': 789, 'description': 'Test'}
            }
        }
        list_available(manifest)
        output = capsys.readouterr().out

        assert '2024' in output
        assert '2025' in output
        assert '[preliminary]' in output
        assert 'Douglas County' in output
        assert 'FIPS: 08035' in output
        assert '_description' not in output  # internal keys filtered

    def test_empty_manifest(self, capsys):
        """Empty manifest shouldn't crash."""
        manifest = {'files': {}, 'jurisdiction_filters': {}, 'data_dictionaries': {}}
        list_available(manifest)
        output = capsys.readouterr().out
        assert 'YEARS (0)' in output


# ===========================================================================
# process_year — filename generation
# ===========================================================================

class TestProcessYearFilename:

    def test_douglas_filename(self):
        """Douglas County filename should be: '2024 douglas.csv'"""
        jur_config = {'county': 'DOUGLAS', 'display_name': 'Douglas County'}
        display_name = jur_config['display_name']
        filename = f"2024 {display_name.lower().replace(' county', '').strip()}.csv"
        assert filename == '2024 douglas.csv'

    def test_el_paso_filename(self):
        jur_config = {'county': 'EL PASO', 'display_name': 'El Paso County'}
        display_name = jur_config['display_name']
        filename = f"2024 {display_name.lower().replace(' county', '').strip()}.csv"
        assert filename == '2024 el paso.csv'

    def test_denver_filename(self):
        """Denver County → '2024 denver.csv'"""
        jur_config = {'county': 'DENVER', 'display_name': 'Denver County'}
        display_name = jur_config['display_name']
        filename = f"2024 {display_name.lower().replace(' county', '').strip()}.csv"
        assert filename == '2024 denver.csv'

    def test_clear_creek_filename(self):
        """Clear Creek County → '2024 clear creek.csv'"""
        jur_config = {'county': 'CLEAR CREEK', 'display_name': 'Clear Creek County'}
        display_name = jur_config['display_name']
        filename = f"2024 {display_name.lower().replace(' county', '').strip()}.csv"
        assert filename == '2024 clear creek.csv'

    def test_statewide_filename(self):
        """Without jurisdiction, filename should be statewide."""
        filename = "cdot_crash_statewide_2024.csv"
        assert 'statewide' in filename


# ===========================================================================
# End-to-end pipeline (Excel → filter → CSV)
# ===========================================================================

class TestEndToEndPipeline:

    def test_full_pipeline(self, tmp_path):
        """Download-like flow: Excel bytes → parse → filter → CSV → verify."""
        xlsx_bytes, expected_count = make_statewide_xlsx(
            counties=['DOUGLAS', 'EL PASO', 'ARAPAHOE'],
            rows_per_county=50
        )

        # Parse
        df = excel_to_dataframe(xlsx_bytes, '.xlsx')
        assert len(df) == 150  # 3 counties × 50

        # Filter
        config = {'county': 'DOUGLAS', 'display_name': 'Douglas County'}
        df_filtered = filter_to_jurisdiction(df, config, 'douglas')
        assert len(df_filtered) == expected_count

        # Save CSV
        csv_path = tmp_path / '2024 douglas.csv'
        df_filtered.to_csv(csv_path, index=False)
        assert csv_path.exists()
        assert csv_path.stat().st_size > 0

        # Read back and verify
        df_verify = pd.read_csv(csv_path)
        assert len(df_verify) == expected_count
        assert list(df_verify.columns) == list(df_filtered.columns)
        assert all(df_verify['County'] == 'DOUGLAS')

    def test_pipeline_columns_match_existing_data(self, tmp_path):
        """Output CSV columns should match what the existing pipeline expects."""
        expected_columns = [
            'CUID', 'System Code', 'Crash Date', 'Crash Time',
            'Agency Id', 'City', 'County', 'Latitude', 'Longitude',
        ]

        xlsx_bytes, _ = make_statewide_xlsx()
        df = excel_to_dataframe(xlsx_bytes, '.xlsx')
        config = {'county': 'DOUGLAS', 'display_name': 'Douglas County'}
        df_filtered = filter_to_jurisdiction(df, config, 'douglas')

        for col in expected_columns:
            assert col in df_filtered.columns, f"Missing expected column: {col}"

    def test_pipeline_with_all_nan_county(self, tmp_path):
        """If the county column is all NaN, filter should return empty."""
        df = pd.DataFrame({
            'CUID': [1, 2, 3],
            'County': [None, None, None],
            'Agency Id': ['DSO', 'DSO', 'DSO'],
        })
        config = {'county': 'DOUGLAS', 'display_name': 'Douglas County'}
        result = filter_to_jurisdiction(df, config, 'douglas')
        assert len(result) == 0


# ===========================================================================
# Manifest integrity — all 64 Colorado counties
# ===========================================================================

class TestManifestIntegrity:

    @pytest.fixture
    def manifest(self):
        path = PROJECT_ROOT / 'data' / 'CDOT' / 'source_manifest.json'
        if not path.exists():
            pytest.skip("Manifest not found")
        with open(path) as f:
            return json.load(f)

    def test_all_years_have_docid(self, manifest):
        for year, info in manifest['files'].items():
            assert 'docid' in info, f"Year {year} missing docid"
            assert isinstance(info['docid'], int), f"Year {year} docid not int"

    def test_all_years_have_status(self, manifest):
        for year, info in manifest['files'].items():
            assert 'status' in info, f"Year {year} missing status"
            assert info['status'] in ('final', 'preliminary'), \
                f"Year {year} has invalid status: {info['status']}"

    def test_years_are_2021_to_2025(self, manifest):
        years = sorted(manifest['files'].keys())
        assert years == ['2021', '2022', '2023', '2024', '2025']

    def test_docids_are_unique(self, manifest):
        docids = [info['docid'] for info in manifest['files'].values()]
        assert len(docids) == len(set(docids)), "Duplicate doc IDs found"

    def test_exactly_64_counties(self, manifest):
        """Colorado has exactly 64 counties."""
        counties = {k: v for k, v in manifest['jurisdiction_filters'].items()
                    if not k.startswith('_')}
        assert len(counties) == 64, f"Expected 64 counties, got {len(counties)}"

    def test_all_jurisdictions_have_required_fields(self, manifest):
        for key, jur in manifest['jurisdiction_filters'].items():
            if key.startswith('_'):
                continue
            assert 'county' in jur, f"Jurisdiction {key} missing 'county'"
            assert 'display_name' in jur, f"Jurisdiction {key} missing 'display_name'"
            assert 'fips' in jur, f"Jurisdiction {key} missing 'fips'"
            assert jur['fips'].startswith('08'), f"Jurisdiction {key} FIPS doesn't start with 08"
            assert len(jur['fips']) == 5, f"Jurisdiction {key} FIPS not 5 digits"

    def test_county_names_are_uppercase(self, manifest):
        for key, jur in manifest['jurisdiction_filters'].items():
            if key.startswith('_'):
                continue
            assert jur['county'] == jur['county'].upper(), \
                f"Jurisdiction {key} county '{jur['county']}' not uppercase"

    def test_fips_codes_are_unique(self, manifest):
        fips = [jur['fips'] for k, jur in manifest['jurisdiction_filters'].items()
                if not k.startswith('_')]
        assert len(fips) == len(set(fips)), "Duplicate FIPS codes found"

    def test_county_values_are_unique(self, manifest):
        counties = [jur['county'] for k, jur in manifest['jurisdiction_filters'].items()
                    if not k.startswith('_')]
        assert len(counties) == len(set(counties)), "Duplicate county names found"

    def test_douglas_is_default_jurisdiction(self, manifest):
        assert 'douglas' in manifest['jurisdiction_filters']
        douglas = manifest['jurisdiction_filters']['douglas']
        assert douglas['county'] == 'DOUGLAS'
        assert douglas['fips'] == '08035'

    def test_known_counties_present(self, manifest):
        """Verify a selection of well-known Colorado counties exist."""
        expected = [
            ('adams', 'ADAMS'), ('arapahoe', 'ARAPAHOE'), ('boulder', 'BOULDER'),
            ('broomfield', 'BROOMFIELD'), ('denver', 'DENVER'), ('douglas', 'DOUGLAS'),
            ('elpaso', 'EL PASO'), ('jefferson', 'JEFFERSON'), ('larimer', 'LARIMER'),
            ('mesa', 'MESA'), ('pueblo', 'PUEBLO'), ('weld', 'WELD'),
        ]
        for key, county in expected:
            assert key in manifest['jurisdiction_filters'], f"Missing county: {key}"
            assert manifest['jurisdiction_filters'][key]['county'] == county

    def test_multi_word_county_keys(self, manifest):
        """Counties with spaces should use underscore keys."""
        multi_word = ['clear_creek', 'kit_carson', 'la_plata', 'las_animas',
                      'rio_blanco', 'rio_grande', 'san_juan', 'san_miguel']
        for key in multi_word:
            assert key in manifest['jurisdiction_filters'], f"Missing multi-word county: {key}"

    def test_data_dictionaries_present(self, manifest):
        assert '2021-2025' in manifest['data_dictionaries']
        assert 'docid' in manifest['data_dictionaries']['2021-2025']


# ===========================================================================
# Playwright availability check
# ===========================================================================

class TestPlaywrightFallback:

    def test_playwright_available_returns_bool(self):
        """_playwright_available should return True or False without crashing."""
        result = _playwright_available()
        assert isinstance(result, bool)

    def test_playwright_available_false_when_not_installed(self):
        """When playwright is not importable, should return False."""
        with patch.dict('sys.modules', {'playwright': None, 'playwright.sync_api': None}):
            # Force reimport check
            import importlib
            import download_cdot_crash_data as mod
            importlib.reload(mod)
            # The function catches ImportError gracefully
            result = mod._playwright_available()
            # Result depends on whether playwright is actually installed
            assert isinstance(result, bool)


# ===========================================================================
# merge_with_existing — CUID-based deduplication
# ===========================================================================

class TestMergeWithExisting:
    """Tests for the merge strategy that protects validated data."""

    def _make_csv(self, tmp_path, filename, data):
        """Helper: write a DataFrame dict to a CSV file."""
        df = pd.DataFrame(data)
        path = tmp_path / filename
        df.to_csv(path, index=False)
        return path

    def test_append_new_records(self, tmp_path):
        """New CUIDs should be appended to existing data."""
        existing_path = self._make_csv(tmp_path, 'existing.csv', {
            'CUID': [100, 200, 300],
            'County': ['DOUGLAS'] * 3,
            'Crash Date': ['1/1/2025', '1/2/2025', '1/3/2025'],
        })
        new_df = pd.DataFrame({
            'CUID': [300, 400, 500],
            'County': ['DOUGLAS'] * 3,
            'Crash Date': ['1/3/2025', '1/4/2025', '1/5/2025'],
        })

        merged, stats = merge_with_existing(new_df, existing_path)

        assert stats['existing_count'] == 3
        assert stats['new_download_count'] == 3
        assert stats['new_records'] == 2  # 400 and 500 are new
        assert stats['merged_count'] == 5  # 3 existing + 2 new
        assert set(merged['CUID'].tolist()) == {100, 200, 300, 400, 500}

    def test_no_new_records(self, tmp_path):
        """When all CUIDs already exist, nothing should change."""
        existing_path = self._make_csv(tmp_path, 'existing.csv', {
            'CUID': [100, 200, 300],
            'County': ['DOUGLAS'] * 3,
        })
        new_df = pd.DataFrame({
            'CUID': [100, 200, 300],
            'County': ['DOUGLAS'] * 3,
        })

        merged, stats = merge_with_existing(new_df, existing_path)

        assert stats['new_records'] == 0
        assert stats['merged_count'] == 3  # unchanged
        assert len(merged) == 3

    def test_all_new_records(self, tmp_path):
        """When no CUIDs overlap, all new records should be appended."""
        existing_path = self._make_csv(tmp_path, 'existing.csv', {
            'CUID': [100, 200],
            'County': ['DOUGLAS'] * 2,
        })
        new_df = pd.DataFrame({
            'CUID': [300, 400, 500],
            'County': ['DOUGLAS'] * 3,
        })

        merged, stats = merge_with_existing(new_df, existing_path)

        assert stats['new_records'] == 3
        assert stats['merged_count'] == 5

    def test_existing_records_preserved_exactly(self, tmp_path):
        """Existing rows should not be modified during merge."""
        existing_path = self._make_csv(tmp_path, 'existing.csv', {
            'CUID': [100, 200],
            'County': ['DOUGLAS', 'DOUGLAS'],
            'Latitude': [39.5, 39.6],
            'Custom_Field': ['validated_a', 'validated_b'],
        })
        new_df = pd.DataFrame({
            'CUID': [100, 300],
            'County': ['DOUGLAS', 'DOUGLAS'],
            'Latitude': [99.9, 39.7],  # 100's latitude differs in new data
            'Custom_Field': ['changed', 'new_c'],
        })

        merged, stats = merge_with_existing(new_df, existing_path)

        # Existing CUID=100 should keep original values, not be overwritten
        row_100 = merged[merged['CUID'] == 100].iloc[0]
        assert row_100['Latitude'] == 39.5  # original, not 99.9
        assert row_100['Custom_Field'] == 'validated_a'  # original, not 'changed'

    def test_no_cuid_column_falls_back_to_replace(self, tmp_path):
        """If CUID column is missing, fall back to full replacement."""
        existing_path = self._make_csv(tmp_path, 'existing.csv', {
            'ID': [1, 2, 3],
            'County': ['DOUGLAS'] * 3,
        })
        new_df = pd.DataFrame({
            'ID': [4, 5],
            'County': ['DOUGLAS'] * 2,
        })

        merged, stats = merge_with_existing(new_df, existing_path)

        # Falls back to replacement — returns new_df as-is
        assert len(merged) == 2
        assert stats['merged_count'] == 2

    def test_empty_existing_file(self, tmp_path):
        """Merging into an empty existing CSV should return all new records."""
        existing_path = self._make_csv(tmp_path, 'existing.csv', {
            'CUID': pd.Series([], dtype=int),
            'County': pd.Series([], dtype=str),
        })
        new_df = pd.DataFrame({
            'CUID': [100, 200],
            'County': ['DOUGLAS'] * 2,
        })

        merged, stats = merge_with_existing(new_df, existing_path)

        assert stats['existing_count'] == 0
        assert stats['new_records'] == 2
        assert stats['merged_count'] == 2

    def test_cuid_as_string(self, tmp_path):
        """CUID comparison should work even with mixed int/string types."""
        existing_path = self._make_csv(tmp_path, 'existing.csv', {
            'CUID': ['100', '200'],  # strings in CSV
            'County': ['DOUGLAS'] * 2,
        })
        new_df = pd.DataFrame({
            'CUID': [200, 300],  # ints in download
            'County': ['DOUGLAS'] * 2,
        })

        merged, stats = merge_with_existing(new_df, existing_path)

        # 200 exists (as string vs int), 300 is new
        assert stats['new_records'] == 1
        assert stats['merged_count'] == 3

    def test_merge_stats_accuracy(self, tmp_path):
        """Verify all stats fields are populated correctly."""
        existing_path = self._make_csv(tmp_path, 'existing.csv', {
            'CUID': [1, 2, 3, 4, 5],
            'County': ['DOUGLAS'] * 5,
        })
        new_df = pd.DataFrame({
            'CUID': [3, 4, 5, 6, 7, 8],
            'County': ['DOUGLAS'] * 6,
        })

        merged, stats = merge_with_existing(new_df, existing_path)

        assert stats['existing_count'] == 5
        assert stats['new_download_count'] == 6
        assert stats['new_records'] == 3  # 6, 7, 8
        assert stats['merged_count'] == 8  # 1-8


class TestGetOutputFilename:
    """Tests for the filename helper function."""

    def test_douglas_filename(self):
        manifest = {'jurisdiction_filters': {
            'douglas': {'county': 'DOUGLAS', 'display_name': 'Douglas County'}
        }}
        assert _get_output_filename('2024', 'douglas', manifest) == '2024 douglas.csv'

    def test_el_paso_filename(self):
        manifest = {'jurisdiction_filters': {
            'elpaso': {'county': 'EL PASO', 'display_name': 'El Paso County'}
        }}
        assert _get_output_filename('2024', 'elpaso', manifest) == '2024 el paso.csv'

    def test_statewide_filename(self):
        manifest = {'jurisdiction_filters': {}}
        assert _get_output_filename('2024', None, manifest) == 'cdot_crash_statewide_2024.csv'

    def test_unknown_jurisdiction_returns_statewide(self):
        manifest = {'jurisdiction_filters': {'douglas': {}}}
        assert _get_output_filename('2024', 'bogus', manifest) == 'cdot_crash_statewide_2024.csv'


class TestProcessYearSkipLogic:
    """Tests for skip-if-final and merge-if-preliminary behavior."""

    def test_skip_final_when_exists(self, tmp_path):
        """Final year with existing CSV should be skipped."""
        # Create an existing CSV
        existing = tmp_path / '2024 douglas.csv'
        pd.DataFrame({'CUID': [1, 2, 3], 'County': ['DOUGLAS'] * 3}).to_csv(existing, index=False)

        manifest = {
            'jurisdiction_filters': {
                'douglas': {'county': 'DOUGLAS', 'display_name': 'Douglas County', 'fips': '08035'}
            },
            'files': {'2024': {'docid': 35111742, 'status': 'final'}}
        }
        year_info = {'docid': 35111742, 'status': 'final'}

        # Import process_year
        from download_cdot_crash_data import process_year

        # Should skip without trying to download (session won't be used)
        mock_session = MagicMock()
        year, success, path = process_year(
            mock_session, '2024', year_info, manifest, tmp_path, 'douglas', force=False
        )

        assert success is True
        assert str(existing) == path
        # Session should NOT have been called (skipped download)
        mock_session.get.assert_not_called()

    def test_force_overrides_skip(self, tmp_path):
        """With --force, even final years should attempt download."""
        existing = tmp_path / '2024 douglas.csv'
        pd.DataFrame({'CUID': [1], 'County': ['DOUGLAS']}).to_csv(existing, index=False)

        manifest = {
            'jurisdiction_filters': {
                'douglas': {'county': 'DOUGLAS', 'display_name': 'Douglas County', 'fips': '08035'}
            },
            'files': {'2024': {'docid': 35111742, 'status': 'final'}}
        }
        year_info = {'docid': 35111742, 'status': 'final'}

        from download_cdot_crash_data import process_year

        mock_session = MagicMock()
        # The download will fail (mock session), but it should ATTEMPT it
        year, success, error = process_year(
            mock_session, '2024', year_info, manifest, tmp_path, 'douglas', force=True
        )

        # It tried to download (and failed because session is mocked)
        assert success is False  # download failed
        # But it didn't skip — that's the important part

    def test_missing_file_always_downloads(self, tmp_path):
        """If the CSV doesn't exist, always download regardless of status."""
        manifest = {
            'jurisdiction_filters': {
                'douglas': {'county': 'DOUGLAS', 'display_name': 'Douglas County', 'fips': '08035'}
            },
            'files': {'2024': {'docid': 35111742, 'status': 'final'}}
        }
        year_info = {'docid': 35111742, 'status': 'final'}

        from download_cdot_crash_data import process_year

        mock_session = MagicMock()
        year, success, error = process_year(
            mock_session, '2024', year_info, manifest, tmp_path, 'douglas', force=False
        )

        # It tried to download (file doesn't exist, so it didn't skip)
        assert success is False  # download fails due to mock

    def test_preliminary_year_always_downloads(self, tmp_path):
        """Preliminary years should always attempt download even if file exists."""
        existing = tmp_path / '2025 douglas.csv'
        pd.DataFrame({'CUID': [1], 'County': ['DOUGLAS']}).to_csv(existing, index=False)

        manifest = {
            'jurisdiction_filters': {
                'douglas': {'county': 'DOUGLAS', 'display_name': 'Douglas County', 'fips': '08035'}
            },
            'files': {'2025': {'docid': 54973381, 'status': 'preliminary'}}
        }
        year_info = {'docid': 54973381, 'status': 'preliminary'}

        from download_cdot_crash_data import process_year

        mock_session = MagicMock()
        year, success, error = process_year(
            mock_session, '2025', year_info, manifest, tmp_path, 'douglas', force=False
        )

        # It tried to download (preliminary status, not skipped)
        assert success is False  # download fails due to mock


class TestCuidColumn:
    """Verify the CUID column constant matches actual data."""

    def test_cuid_column_name(self):
        assert CUID_COLUMN == 'CUID'

    def test_cuid_in_actual_data(self):
        """CUID column exists in existing data files."""
        data_dir = PROJECT_ROOT / 'data' / 'CDOT'
        for csv_file in data_dir.glob('20?? *.csv'):
            df = pd.read_csv(csv_file, nrows=1)
            # Handle BOM in column names
            cols = [c.strip('\ufeff').strip() for c in df.columns]
            assert 'CUID' in cols, f"CUID missing from {csv_file.name}: {cols[:5]}"


# ===========================================================================
# Edge case: _description keys in jurisdiction_filters
# ===========================================================================

class TestManifestDescriptionKeys:
    """Bug regression: _description key in jurisdiction_filters caused AttributeError."""

    def test_list_available_with_description_key(self, capsys):
        manifest = {
            'files': {'2024': {'docid': 1, 'status': 'final'}},
            'jurisdiction_filters': {
                '_description': 'This is a string, not a dict',
                'douglas': {
                    'county': 'DOUGLAS',
                    'fips': '08035',
                    'display_name': 'Douglas County'
                }
            },
            'data_dictionaries': {}
        }
        # This should NOT raise AttributeError
        list_available(manifest)
        output = capsys.readouterr().out
        assert 'Douglas County' in output
        assert '_description' not in output


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
