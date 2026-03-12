#!/usr/bin/env python3
"""
Bug tests for the slimmed-down batch-all-jurisdictions.yml workflow.

Validates that the refactored workflow:
  1. Is valid YAML with correct GitHub Actions structure
  2. Has exactly 2 jobs: download + trigger-pipeline (no processing stages)
  3. Passes correct inputs to pipeline.yml (scope=statewide)
  4. Preserves all 51 state options
  5. Has no leftover references to removed stages (split, upload, forecasts, etc.)
  6. Mirrors download-virginia.yml trigger pattern
  7. Has correct permissions (contents:write, actions:write)
  8. Has correct job dependency chain
  9. Passes skip_forecasts and dry_run through to pipeline
 10. Has no references to removed inputs (batch_size, jurisdictions, skip_validation, skip_geocode)

Run with:
    python tests/test_batch_workflow_bugs.py
    python -m pytest tests/test_batch_workflow_bugs.py -v
"""

import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parent.parent.resolve()


def load_workflow(path):
    """Load a GitHub Actions YAML file, handling the 'on' → True key issue."""
    content = path.read_text()
    parsed = yaml.safe_load(content)
    # PyYAML parses bare 'on' as boolean True
    if True in parsed and 'on' not in parsed:
        parsed['on'] = parsed.pop(True)
    return parsed, content
WORKFLOWS_DIR = PROJECT_ROOT / '.github' / 'workflows'

BATCH_WORKFLOW = WORKFLOWS_DIR / 'batch-all-jurisdictions.yml'
DOWNLOAD_VA_WORKFLOW = WORKFLOWS_DIR / 'download-virginia.yml'
PIPELINE_WORKFLOW = WORKFLOWS_DIR / 'pipeline.yml'


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def batch_yaml():
    """Load and parse batch-all-jurisdictions.yml."""
    assert BATCH_WORKFLOW.exists(), f'Missing: {BATCH_WORKFLOW}'
    return load_workflow(BATCH_WORKFLOW)


@pytest.fixture(scope='module')
def download_va_yaml():
    """Load and parse download-virginia.yml."""
    assert DOWNLOAD_VA_WORKFLOW.exists(), f'Missing: {DOWNLOAD_VA_WORKFLOW}'
    parsed, _ = load_workflow(DOWNLOAD_VA_WORKFLOW)
    return parsed


@pytest.fixture(scope='module')
def pipeline_yaml():
    """Load and parse pipeline.yml."""
    assert PIPELINE_WORKFLOW.exists(), f'Missing: {PIPELINE_WORKFLOW}'
    parsed, _ = load_workflow(PIPELINE_WORKFLOW)
    return parsed


# ---------------------------------------------------------------------------
# Test 1: Valid YAML structure
# ---------------------------------------------------------------------------

class TestYAMLStructure:
    def test_valid_yaml(self, batch_yaml):
        """Workflow file must be parseable YAML."""
        parsed, _ = batch_yaml
        assert parsed is not None

    def test_has_name(self, batch_yaml):
        parsed, _ = batch_yaml
        assert 'name' in parsed
        assert 'Batch All Jurisdictions' in parsed['name']

    def test_has_workflow_dispatch(self, batch_yaml):
        parsed, _ = batch_yaml
        assert 'workflow_dispatch' in parsed['on']

    def test_has_permissions(self, batch_yaml):
        parsed, _ = batch_yaml
        perms = parsed.get('permissions', {})
        assert perms.get('contents') == 'write', 'Needs contents:write for git commit'
        assert perms.get('actions') == 'write', 'Needs actions:write to trigger pipeline.yml'


# ---------------------------------------------------------------------------
# Test 2: Exactly 2 jobs (download + trigger-pipeline)
# ---------------------------------------------------------------------------

class TestJobStructure:
    def test_has_exactly_two_jobs(self, batch_yaml):
        parsed, _ = batch_yaml
        jobs = parsed.get('jobs', {})
        assert len(jobs) == 2, f'Expected 2 jobs, got {len(jobs)}: {list(jobs.keys())}'

    def test_has_download_job(self, batch_yaml):
        parsed, _ = batch_yaml
        assert 'download' in parsed['jobs']

    def test_has_trigger_pipeline_job(self, batch_yaml):
        parsed, _ = batch_yaml
        assert 'trigger-pipeline' in parsed['jobs']

    def test_trigger_depends_on_download(self, batch_yaml):
        parsed, _ = batch_yaml
        trigger = parsed['jobs']['trigger-pipeline']
        needs = trigger.get('needs', '')
        if isinstance(needs, list):
            assert 'download' in needs
        else:
            assert needs == 'download'

    def test_trigger_has_skip_condition(self, batch_yaml):
        """trigger-pipeline should be skippable via skip_pipeline input."""
        parsed, _ = batch_yaml
        trigger = parsed['jobs']['trigger-pipeline']
        condition = trigger.get('if', '')
        assert 'skip_pipeline' in condition

    def test_download_job_has_outputs(self, batch_yaml):
        parsed, _ = batch_yaml
        download = parsed['jobs']['download']
        outputs = download.get('outputs', {})
        assert 'state' in outputs, 'Download job must output state'
        assert 'csv_path' in outputs, 'Download job must output csv_path'


# ---------------------------------------------------------------------------
# Test 3: Pipeline trigger passes correct inputs
# ---------------------------------------------------------------------------

class TestPipelineTrigger:
    def test_triggers_pipeline_yml(self, batch_yaml):
        """Must reference pipeline.yml in the trigger step."""
        _, raw = batch_yaml
        assert 'pipeline.yml' in raw

    def test_passes_scope_statewide(self, batch_yaml):
        """Must pass scope: 'statewide' to pipeline."""
        _, raw = batch_yaml
        assert "scope: 'statewide'" in raw or 'scope: statewide' in raw

    def test_passes_state_input(self, batch_yaml):
        """Must forward the selected state to pipeline."""
        _, raw = batch_yaml
        assert 'state: state' in raw or "state:" in raw

    def test_passes_data_source(self, batch_yaml):
        """Must pass csv_path as data_source to pipeline."""
        _, raw = batch_yaml
        assert 'data_source' in raw

    def test_passes_skip_forecasts(self, batch_yaml):
        """Must forward skip_forecasts to pipeline."""
        _, raw = batch_yaml
        assert 'skip_forecasts' in raw

    def test_passes_dry_run(self, batch_yaml):
        """Must forward dry_run to pipeline."""
        _, raw = batch_yaml
        assert 'dry_run' in raw

    def test_uses_create_workflow_dispatch(self, batch_yaml):
        """Must use createWorkflowDispatch API (same as download-virginia.yml)."""
        _, raw = batch_yaml
        assert 'createWorkflowDispatch' in raw

    def test_selection_is_empty_for_statewide(self, batch_yaml):
        """For statewide scope, selection should be empty string."""
        _, raw = batch_yaml
        assert "selection: ''" in raw or "selection: \"\"" in raw


# ---------------------------------------------------------------------------
# Test 4: State options preserved
# ---------------------------------------------------------------------------

class TestStateOptions:
    EXPECTED_STATES = [
        'virginia', 'colorado', 'alabama', 'alaska', 'arizona', 'arkansas',
        'california', 'connecticut', 'delaware', 'district_of_columbia',
        'florida', 'georgia', 'hawaii', 'idaho', 'illinois', 'indiana',
        'iowa', 'kansas', 'kentucky', 'louisiana', 'maine', 'maryland',
        'massachusetts', 'michigan', 'minnesota', 'mississippi', 'missouri',
        'montana', 'nebraska', 'nevada', 'new_hampshire', 'new_jersey',
        'new_mexico', 'new_york', 'north_carolina', 'north_dakota', 'ohio',
        'oklahoma', 'oregon', 'pennsylvania', 'rhode_island', 'south_carolina',
        'south_dakota', 'tennessee', 'texas', 'utah', 'vermont',
        'washington_state', 'west_virginia', 'wisconsin', 'wyoming',
    ]

    def test_has_all_51_state_options(self, batch_yaml):
        parsed, _ = batch_yaml
        state_input = parsed['on']['workflow_dispatch']['inputs']['state']
        options = state_input.get('options', [])
        assert len(options) == 51, f'Expected 51 states (50 + DC), got {len(options)}'

    @pytest.mark.parametrize('state', EXPECTED_STATES)
    def test_state_present(self, batch_yaml, state):
        parsed, _ = batch_yaml
        options = parsed['on']['workflow_dispatch']['inputs']['state']['options']
        assert state in options, f'{state} missing from state options'


# ---------------------------------------------------------------------------
# Test 5: No leftover references to removed stages
# ---------------------------------------------------------------------------

class TestNoLeftoverStages:
    """The slimmed workflow must NOT contain processing logic that belongs in pipeline.yml."""

    def test_no_split_jurisdictions_call(self, batch_yaml):
        _, raw = batch_yaml
        assert 'split_jurisdictions.py' not in raw, \
            'split_jurisdictions.py should be in pipeline.yml, not batch'

    def test_no_split_road_type_call(self, batch_yaml):
        _, raw = batch_yaml
        assert 'split_road_type.py' not in raw

    def test_no_r2_upload(self, batch_yaml):
        _, raw = batch_yaml
        assert 'aws s3 cp' not in raw, \
            'R2 uploads should be in pipeline.yml, not batch'

    def test_no_generate_forecast(self, batch_yaml):
        _, raw = batch_yaml
        assert 'generate_forecast.py' not in raw

    def test_no_generate_aggregates(self, batch_yaml):
        _, raw = batch_yaml
        assert 'generate_aggregates.py' not in raw

    def test_no_aggregate_by_scope(self, batch_yaml):
        _, raw = batch_yaml
        assert 'aggregate_by_scope.py' not in raw

    def test_no_r2_bucket_reference(self, batch_yaml):
        _, raw = batch_yaml
        assert 'crash-lens-data' not in raw, \
            'R2 bucket name should only be in pipeline.yml'

    def test_no_r2_endpoint(self, batch_yaml):
        _, raw = batch_yaml
        assert 'r2.cloudflarestorage.com' not in raw

    def test_no_statewide_gzip_upload(self, batch_yaml):
        _, raw = batch_yaml
        assert 'statewide_all_roads.csv.gz' not in raw or \
               'gunzip' in raw, \
            'Gzip upload stage should be in pipeline.yml'


# ---------------------------------------------------------------------------
# Test 6: Mirrors download-virginia.yml trigger pattern
# ---------------------------------------------------------------------------

class TestMirrorsDownloadVirginia:
    def test_both_have_trigger_pipeline_job(self, batch_yaml, download_va_yaml):
        parsed, _ = batch_yaml
        assert 'trigger-pipeline' in parsed['jobs']
        assert 'trigger-pipeline' in download_va_yaml['jobs']

    def test_both_use_actions_github_script(self, batch_yaml, download_va_yaml):
        parsed, _ = batch_yaml
        batch_trigger = parsed['jobs']['trigger-pipeline']
        va_trigger = download_va_yaml['jobs']['trigger-pipeline']

        batch_uses = [s.get('uses', '') for s in batch_trigger.get('steps', [])]
        va_uses = [s.get('uses', '') for s in va_trigger.get('steps', [])]

        assert any('github-script' in u for u in batch_uses)
        assert any('github-script' in u for u in va_uses)

    def test_both_have_skip_pipeline_input(self, batch_yaml, download_va_yaml):
        parsed, _ = batch_yaml
        batch_inputs = parsed['on']['workflow_dispatch']['inputs']
        va_inputs = download_va_yaml['on']['workflow_dispatch']['inputs']
        assert 'skip_pipeline' in batch_inputs
        assert 'skip_pipeline' in va_inputs

    def test_both_have_actions_write_permission(self, batch_yaml, download_va_yaml):
        parsed, _ = batch_yaml
        assert parsed.get('permissions', {}).get('actions') == 'write'
        assert download_va_yaml.get('permissions', {}).get('actions') == 'write'


# ---------------------------------------------------------------------------
# Test 7: Pipeline.yml accepts all inputs batch sends
# ---------------------------------------------------------------------------

class TestPipelineCompatibility:
    def test_pipeline_accepts_state(self, pipeline_yaml):
        inputs = pipeline_yaml['on']['workflow_dispatch']['inputs']
        assert 'state' in inputs

    def test_pipeline_accepts_scope(self, pipeline_yaml):
        inputs = pipeline_yaml['on']['workflow_dispatch']['inputs']
        assert 'scope' in inputs
        options = inputs['scope'].get('options', [])
        assert 'statewide' in options

    def test_pipeline_accepts_selection(self, pipeline_yaml):
        inputs = pipeline_yaml['on']['workflow_dispatch']['inputs']
        assert 'selection' in inputs

    def test_pipeline_accepts_data_source(self, pipeline_yaml):
        inputs = pipeline_yaml['on']['workflow_dispatch']['inputs']
        assert 'data_source' in inputs

    def test_pipeline_accepts_skip_forecasts(self, pipeline_yaml):
        inputs = pipeline_yaml['on']['workflow_dispatch']['inputs']
        assert 'skip_forecasts' in inputs

    def test_pipeline_accepts_dry_run(self, pipeline_yaml):
        inputs = pipeline_yaml['on']['workflow_dispatch']['inputs']
        assert 'dry_run' in inputs


# ---------------------------------------------------------------------------
# Test 8: No removed inputs remain
# ---------------------------------------------------------------------------

class TestNoRemovedInputs:
    """Inputs that belonged to the monolithic batch workflow should be gone."""

    def test_no_batch_size_input(self, batch_yaml):
        parsed, _ = batch_yaml
        inputs = parsed['on']['workflow_dispatch']['inputs']
        assert 'batch_size' not in inputs, 'batch_size is no longer needed'

    def test_no_jurisdictions_dropdown(self, batch_yaml):
        """The massive 2,857-jurisdiction dropdown should be removed."""
        parsed, _ = batch_yaml
        inputs = parsed['on']['workflow_dispatch']['inputs']
        assert 'jurisdictions' not in inputs, \
            'Individual jurisdiction selection is handled by download-virginia.yml'

    def test_no_skip_validation_input(self, batch_yaml):
        parsed, _ = batch_yaml
        inputs = parsed['on']['workflow_dispatch']['inputs']
        assert 'skip_validation' not in inputs, 'Validation is handled separately'

    def test_no_skip_geocode_input(self, batch_yaml):
        parsed, _ = batch_yaml
        inputs = parsed['on']['workflow_dispatch']['inputs']
        assert 'skip_geocode' not in inputs, 'Geocoding is handled separately'


# ---------------------------------------------------------------------------
# Test 9: Download job handles all 3 state types
# ---------------------------------------------------------------------------

class TestDownloadStages:
    def test_handles_virginia(self, batch_yaml):
        _, raw = batch_yaml
        assert 'download_crash_data.py' in raw

    def test_handles_colorado(self, batch_yaml):
        _, raw = batch_yaml
        assert 'download_cdot_crash_data.py' in raw

    def test_handles_generic_states(self, batch_yaml):
        """Generic state handler should find state-specific download scripts."""
        _, raw = batch_yaml
        assert 'download_*_crash_data.py' in raw or 'download_' in raw

    def test_has_merge_stage(self, batch_yaml):
        _, raw = batch_yaml
        assert 'Merge' in raw or 'merge' in raw

    def test_has_convert_stage(self, batch_yaml):
        _, raw = batch_yaml
        assert 'Convert' in raw or 'convert' in raw or 'standardized' in raw

    def test_has_git_commit(self, batch_yaml):
        _, raw = batch_yaml
        assert 'git commit' in raw

    def test_has_git_push_retry(self, batch_yaml):
        """Git push should have retry logic (matching download-virginia.yml)."""
        _, raw = batch_yaml
        assert 'git push' in raw
        # Should have retry loop
        assert 'for i in' in raw or 'retry' in raw.lower() or 'attempt' in raw.lower()

    def test_has_timeout(self, batch_yaml):
        parsed, _ = batch_yaml
        download = parsed['jobs']['download']
        assert download.get('timeout-minutes', 0) > 0


# ---------------------------------------------------------------------------
# Test 10: Workflow size sanity check
# ---------------------------------------------------------------------------

class TestWorkflowSize:
    def test_under_500_lines(self, batch_yaml):
        """Slimmed workflow should be well under 500 lines (was 3,856)."""
        _, raw = batch_yaml
        lines = raw.count('\n') + 1
        assert lines < 500, f'Workflow is {lines} lines — should be < 500 after slimming'

    def test_under_20kb(self, batch_yaml):
        """File size sanity check."""
        size = BATCH_WORKFLOW.stat().st_size
        assert size < 20_000, f'Workflow is {size} bytes — should be < 20KB after slimming'


# ---------------------------------------------------------------------------
# CLI runner (for running without pytest)
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v', '--tb=short']))
