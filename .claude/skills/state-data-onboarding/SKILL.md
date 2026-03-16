---
name: state-data-onboarding
description: "CrashLens state crash data onboarding, normalization, and validation. Actions: onboard new state, normalize data, validate mapping, fix schema change, add normalizer, create download script, compare schemas, audit decode maps. Triggers: new state, state onboarding, crash data, normalize, normalizer, state adapter, decode map, value mapping, schema change, VDOT, ArcGIS, Socrata, KABCO, EPDO, sentinel values, coded values, split jurisdiction, split road type, pipeline, download registry."
---

# State Data Onboarding — CrashLens Normalization Engine

Comprehensive guide for onboarding new U.S. state crash data into CrashLens. Virginia's data format is the gold standard — all states normalize TO it.

## When to Apply

Use this skill when:
- Onboarding a new state's crash data
- An existing state changed their data format (schema change)
- Adding/fixing value decode maps in normalizers
- Debugging why frontend filters return zero results
- Creating download scripts for new data sources
- Adding state to the pipeline workflow
- Auditing normalization for correctness against frontend expectations

## Quick Reference: Architecture

### File Locations
```
scripts/state_adapter.py          # Normalizer classes + auto-detection
states/{state}/config.json        # State config (roadSystems, EPDO, splitConfig)
states/{state}/hierarchy.json     # Regional organization (optional)
states/download-registry.json     # Maps states to download scripts + pipeline flags
download_crash_data.py            # Virginia-specific download + standardize_columns()
data/{StateDOT}/                  # State-specific download scripts + data
.github/workflows/pipeline.yml    # Unified processing pipeline
.github/workflows/download-{state}-crash-data.yml  # Per-state download workflow
scripts/split_jurisdictions.py    # Split data by jurisdiction
scripts/split_road_type.py        # Split into all_roads, county_roads, no_interstate
docs/data_compare/claude project/ # Target schema + system prompt for Claude Projects
```

### Normalizer Pattern
```python
# In scripts/state_adapter.py:

# 1. Add signature for auto-detection
STATE_SIGNATURES['newstate'] = {
    'required': ['unique_col_1', 'unique_col_2'],
    'optional': ['optional_col'],
    'display_name': 'NewState (DOT)',
    'config_dir': 'newstate'
}

# 2. Create normalizer class
class NewStateNormalizer(BaseNormalizer):
    def normalize_row(self, row):
        normalized = {}
        # Map fields to Virginia-standard columns
        normalized['Document Nbr'] = row.get('report_id', '')
        normalized['Crash Severity'] = self._map_severity(row)
        # ... all standard columns
        normalized['_source_state'] = 'newstate'
        return normalized

# 3. Register in _NORMALIZERS
_NORMALIZERS['newstate'] = NewStateNormalizer
```

### Standard Output Columns (Virginia Format)
```
Document Nbr, Crash Date, Crash Year, Crash Military Time,
Crash Severity (K/A/B/C/O), K_People, A_People, B_People, C_People,
Collision Type, Weather Condition, Light Condition,
Roadway Surface Condition, Roadway Alignment, Roadway Surface Type,
Roadway Defect, Roadway Description, Intersection Type,
Traffic Control Type, Traffic Control Status,
Work Zone Related, Work Zone Location, Work Zone Type, School Zone,
First Harmful Event, First Harmful Event Loc,
Route or Street Name,
Alcohol?, Animal Related?, Unrestrained? (Belted/Unbelted),
Bike?, Distracted?, Drowsy?, Drug Related?, Guardrail Related?,
Hitrun?, Lgtruck?, Motorcycle?, Pedestrian?, Speed?,
Max Speed Diff, RoadDeparture Type, Intersection Analysis,
Senior?, Young?, Mainline?, Night?,
VDOT District, Juris Code, Physical Juris Name (NNN. Name format),
Functional Class, Facility Type, Area Type,
SYSTEM, VSP, Ownership, Planning District, MPO Name,
RTE Name, RNS MP, Node, Node Offset (ft), Local Case CD,
x (longitude), y (latitude)
```

---

## Onboarding Workflow

### Step 1: Research the Data Source

```bash
# Check existing state infrastructure
ls states/{state}/
cat states/download-registry.json | python3 -m json.tool | grep -A5 '{state}'

# Check if normalizer already exists
grep -n '{state}' scripts/state_adapter.py
```

For a new state, find their crash data portal:
- **ArcGIS REST services** (most common for DOTs) — paginated JSON with coded values
- **Socrata SODA API** (e.g., Delaware, data.gov sites) — SQL-like queries, JSON/CSV
- **Direct CSV/Excel downloads** — from state DOT websites
- Document: endpoint URL, auth requirements, rate limits, pagination, field names

### Step 2: Classify Every Column

Read the source data schema and classify each field:

| Classification | Meaning | Example |
|---------------|---------|---------|
| DIRECT | Same name, same values | `Crash Severity` already K/A/B/C/O |
| RENAME | Different name, same data | `report_number` → `Document Nbr` |
| VALUE_MAP | Same concept, coded values | `"1"` → `"1. Rear End"` |
| RENAME+MAP | Different name AND coded values | `Senior Driver?` → `Senior?` + `0/1` → `Yes/No` |
| COMPUTED | Derived from other fields | `Crash Year` from `Crash Date` |
| MISSING | No source equivalent | Set to empty/default |

### Step 3: Build Value Mappings

**CRITICAL**: Include sentinel values (0 and 99) in every coded map:
```python
collision_type_map = {
    '0': 'Not Applicable',      # sentinel
    '1': '1. Rear End',
    '2': '2. Angle',
    # ... all codes ...
    '16': '16. Other',
    '99': 'Not Provided',       # sentinel
}
```

**SYSTEM mapping** (Virginia-specific, codes differ from what you'd expect):
```python
system_map = {
    '1': 'NonVDOT primary',
    '2': 'NonVDOT secondary',
    '3': 'VDOT Interstate',
    '4': 'VDOT Primary',
    '5': 'VDOT Secondary',
}
```

**Boolean flags**: `0` → `No`, `1` → `Yes`
**Exception**: `Unrestrained?` uses `0` → `Belted`, `1` → `Unbelted`

**Crash Date format**: `M/D/YYYY H:MM:SS AM` (12-hour with seconds)
- Epoch ms: `dt.strftime('%-m/%-d/%Y %-I:%M:%S %p')`
- Date-only: append ` 5:00:00 AM`

**Physical Juris Name format**: `NNN. Name` with "City of" / "Town of" prefix
- `"043. Henrico County"`, `"100. City of Alexandria"`, `"150. Town of Blacksburg"`

### Step 4: Create State Config

```bash
# Create state directory
mkdir -p states/{state}
```

`states/{state}/config.json` must include:
```json
{
  "state": {
    "name": "StateName",
    "abbreviation": "ST",
    "fips": "XX",
    "dotName": "DOT"
  },
  "columnMapping": { ... },
  "severityMapping": { ... },
  "roadSystems": {
    "column": "SYSTEM",
    "values": { ... }
  },
  "splitConfig": { ... },
  "filterProfiles": { ... },
  "epdoWeights": {
    "K": 883, "A": 94, "B": 21, "C": 11, "O": 1
  }
}
```

### Step 5: Create Normalizer Class

Add to `scripts/state_adapter.py`:
1. `STATE_SIGNATURES` entry
2. Normalizer class extending `BaseNormalizer`
3. `_NORMALIZERS` registry entry

Follow the pattern of existing normalizers:
- **Simple states**: Follow `VirginiaNormalizer` (passthrough)
- **Complex states**: Follow `ColoradoNormalizer` (full transformation)
- **Socrata APIs**: Follow `DelawareNormalizer` (API + CSV format support)
- **Dual portals**: Follow `MarylandNormalizer` (county + statewide)

### Step 6: Create Download Script

Create `data/{StateDOT}/download_{state}_crash_data.py` with:
- API client with retry logic (4 retries, exponential backoff: 2s, 4s, 8s, 16s)
- CLI flags: `--jurisdiction`, `--years`, `--force`, `--gzip`, `--health-check`
- Pagination handling
- Raw data saved to `data/{StateDOT}/`

### Step 7: Create Workflow + Register

Create `.github/workflows/download-{state}-crash-data.yml` and add entry to `states/download-registry.json`:
```json
"{state}": {
  "tier": 2,
  "script": "data/{StateDOT}/download_{state}_crash_data.py",
  "dataDir": "data/{StateDOT}/",
  "needsStandardization": true,
  "workflow": "download-{state}-crash-data.yml"
}
```

### Step 8: Create Onboarding Documentation

Create `data/{StateDOT}/{state}_dot_data_config_and_onboarding.md` with sections:
1. State Data Profile
2. Data Source Details
3. Normalization Rules
4. Download Pipeline
5. Known Limitations
6. Configuration Files Reference
7. Future Enhancement Roadmap

Reference: `data/DelawareDOT/delaware_dot_data_config_and_onboarding.md`

---

## Validation Checklist

After normalization, verify:

### Road Type Filters Work
```python
# These must return > 0 records:
df[df['Ownership'] == '2. County Hwy Agency']
df[df['Ownership'] == '3. City or Town Hwy Agency']
df[df['Functional Class'] != '1-Interstate (A,1)']
```

### Jurisdiction Dropdown Works
```python
# No raw numeric codes:
assert not df['Physical Juris Name'].str.match(r'^\d+$').any()
# All values match NNN. Name format:
assert df['Physical Juris Name'].str.match(r'^\d{3}\. .+').all()
```

### Severity is Valid
```python
assert df['Crash Severity'].isin(['K', 'A', 'B', 'C', 'O']).all()
```

### SYSTEM Values Match Config
```python
config_values = set(config['roadSystems']['values'].keys())
data_values = set(df['SYSTEM'].dropna().unique())
assert data_values.issubset(config_values)
```

### Boolean Fields are Yes/No
```python
bool_cols = ['Alcohol?', 'Bike?', 'Pedestrian?', 'Speed?', 'Distracted?',
             'Drowsy?', 'Drug Related?', 'Guardrail Related?', 'Hitrun?',
             'Lgtruck?', 'Motorcycle?', 'Animal Related?', 'Senior?',
             'Young?', 'Mainline?', 'Night?']
for col in bool_cols:
    if col in df.columns:
        assert df[col].isin(['Yes', 'No', '']).all(), f"{col} has invalid values"
# Special case:
assert df['Unrestrained?'].isin(['Belted', 'Unbelted', '']).all()
```

### Crash Date Format
```python
import re
pattern = r'^\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}:\d{2} [AP]M$'
assert df['Crash Date'].str.match(pattern).all()
```

---

## Common Pitfalls

1. **SYSTEM codes are NOT intuitive**: 1=NonVDOT primary, NOT VDOT Interstate
2. **Physical Juris Name uses "City of" prefix**: `"100. City of Alexandria"` not `"100. Alexandria City"`
3. **Collision Type 7 is Train, not Parked Vehicle**: The numbered list doesn't match what you'd expect
4. **Weather code 2 doesn't exist**: Values jump from 1 to 3
5. **Sentinel values are real codes**: Code 0 and 99 appear in data and must be decoded
6. **Work Zone fields use empty string for 0/99**: NOT "Not Applicable"
7. **Crash Date needs 12-hour format with seconds**: `M/D/YYYY H:MM:SS AM`
8. **EPDO weights are configurable per state**: Virginia uses K=1032 (VDOT), default is K=883 (FHWA)
9. **Idempotency is required**: Use `skip_if_contains` to avoid double-decoding
10. **Two Virginia data paths**: ArcGIS API (ALL_CAPS, epoch dates) vs VDOT website (mixed-case, formatted dates)

---

## Reference Files

| File | Purpose |
|------|---------|
| `docs/data_compare/claude project/CRASHLENS_TARGET_SCHEMA updated v2.md` | Complete target schema with all allowed values |
| `docs/data_compare/claude project/PROJECT_SYSTEM_PROMPT updated v2.md` | System prompt for Claude Projects |
| `docs/data_compare/Crashlens frontend VDOT previos dataset all_columns_values.txt` | Every unique value in the frontend's expected format |
| `docs/data_compare/current vdot modified dataset all_columns_values.txt` | Current VDOT raw coded values |
| `data/DelawareDOT/delaware_dot_data_config_and_onboarding.md` | Complete onboarding example |
| `tests/test_standardize_columns.py` | 138 tests for Virginia normalization |

## Existing Onboarded States

| State | Normalizer | Tier | Config | Download Script |
|-------|-----------|------|--------|-----------------|
| Virginia | `VirginiaNormalizer` (passthrough) | 1 | `states/virginia/` | `download_crash_data.py` |
| Colorado | `ColoradoNormalizer` | 1 | `states/colorado/` | `data/CDOT/download_cdot_crash_data.py` |
| Maryland | `MarylandNormalizer` | 2 | `states/maryland/` | `data/MarylandDOT/` |
| Delaware | `DelawareNormalizer` | 2 | `states/delaware/` | `data/DelawareDOT/download_delaware_crash_data.py` |
