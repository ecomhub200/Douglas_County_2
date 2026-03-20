# CrashLens — geo_resolver Integration Guide

## Repository File Placement

```
your-repo/
├── geo_resolver.py                          ← NEW: shared geography module
├── states/
│   ├── geography/                           ← Census Bureau JSON files
│   │   ├── us_counties.json                 (3,222 records)
│   │   ├── us_places.json                   (32,333 records)
│   │   ├── us_mpos.json                     (410 records)
│   │   ├── us_county_subdivisions.json      (36,421 records)
│   │   └── us_states.json                   (52 records)
│   │
│   ├── virginia/
│   │   ├── hierarchy.json                   (9 VDOT districts → 133 counties)
│   │   ├── va_normalize.py                  (imports geo_resolver)
│   │   └── ...
│   │
│   ├── delaware/
│   │   ├── hierarchy.json                   (3 regions → 3 counties)
│   │   ├── de_normalize.py                  (imports geo_resolver)
│   │   └── ...
│   │
│   ├── colorado/
│   │   ├── hierarchy.json                   (CDOT regions → 64 counties)
│   │   ├── co_normalize.py                  (imports geo_resolver)
│   │   └── ...
│   │
│   └── {new_state}/
│       ├── hierarchy.json                   ← Create for each new state
│       └── {abbr}_normalize.py              ← Copy from template, edit
│
├── .github/workflows/
│   ├── batch-all-jurisdictions.yml          (generic)
│   ├── de_batch_all_jurisdictions.yml       (Delaware-specific)
│   ├── co_batch_all_jurisdictions.yml       (Colorado-specific)
│   └── {state}_batch_all_jurisdictions.yml  ← Duplicate for new state
│
└── state_normalize_template.py              ← Template for new states
```

## What geo_resolver.py Provides

A single `GeoResolver` class that any state's normalize.py imports.
It loads the 5 Census JSON files + the state's hierarchy.json once, then
resolves 9 columns per crash row in O(1) amortized time (cached per jurisdiction).

### Columns it fills:

| Column | Source | Method |
|---|---|---|
| Physical Juris Name | Census counties + places | Name match → centroid fallback |
| Juris Code | Derived from FIPS | Numeric prefix of Physical Juris Name |
| FIPS | Census counties | Name match → centroid proximity |
| Place FIPS | Census places | Name match for cities/towns |
| VDOT District | hierarchy.json | FIPS → region lookup |
| Planning District | hierarchy.json | FIPS → planning district lookup |
| MPO Name | hierarchy.json + us_mpos.json | Explicit mapping → area-based centroid |
| Ownership | Multi-signal derivation | 4-tier: SYSTEM → FC → juris type → route name |
| Area Type | Census LSADC | City/town = Urban, county = Rural |

### What each state's normalize.py still handles:

- Column mapping (source columns → 69 golden standard)
- Datetime parsing (state-specific format → M/D/YYYY + HHMM)
- Severity mapping (state classification → KABCO)
- Y/N normalization (state-specific values → Yes/No)
- Composite crash ID generation
- EPDO scoring (using state-specific weights)
- Any other state-specific transforms (seatbelt inversion, night detection, etc.)

## Adding a New State — Step by Step

### Step 1: Get the state's crash data architecture

Run the two CLI commands on the state's CSV to extract column names and values:

```bash
# Command 1: Column names
python -c "import pandas as pd,os; f_in=r'STATE_FILE.csv'; df=pd.read_csv(f_in, dtype=str, nrows=1); out=os.path.join(os.path.dirname(os.path.abspath(f_in)),'column_names.txt'); f=open(out,'w',encoding='utf-8'); f.write(f'Total columns: {len(df.columns)}\n\n'); [f.write(f'{i+1}. {col}\n') for i,col in enumerate(df.columns)]; f.close(); print(f'Saved {len(df.columns)} columns to {out}')"

# Command 2: Column values (with universal exclusion)
python -c "
import pandas as pd,os,re
f_in=r'STATE_FILE.csv'
# ... (full command from system prompt)
"
```

### Step 2: Create hierarchy.json

Structure:

```json
{
  "state": {
    "name": "Colorado",
    "abbr": "CO",
    "fips": "08",
    "dot": "CDOT"
  },
  "regions": {
    "region_1": {
      "name": "Region 1 - Denver Metro",
      "shortName": "Denver Metro",
      "planningDistrict": "Denver Metro",
      "mpo": "Denver Regional COG",
      "counties": ["001", "005", "013", "014", "019", "031", "035", "039", "047", "059"]
    },
    "region_2": {
      "name": "Region 2 - Southeast",
      "shortName": "Southeast",
      "planningDistrict": "Southeast",
      "counties": ["025", "041", "043", "061", "071", "089", "099", "101", "109"]
    }
  }
}
```

Find the state DOT's regional structure from their website. Each region lists which counties belong to it.

### Step 3: Create {abbr}_normalize.py

1. Copy `state_normalize_template.py` to `states/{state}/{abbr}_normalize.py`
2. Edit the STATE CONFIGURATION section (FIPS, abbreviation, EPDO weights)
3. Edit the COLUMN_MAP dict to map source columns to golden standard
4. Edit `parse_datetime()` for the state's date format
5. Edit `map_severity()` for the state's severity classification
6. Edit `apply_state_transforms()` for any other state quirks

### Step 4: Test locally

```bash
# Test the normalizer
cd your-repo
python states/{state}/{abbr}_normalize.py \
  --csv path/to/state_crashes.csv \
  --output test_normalized.csv \
  --report test_report.json

# Verify output
python -c "
import pandas as pd
df = pd.read_csv('test_normalized.csv', nrows=5)
print(f'Columns: {len(df.columns)}')
print(f'Expected: 96 (69 golden + 3 enrichment + 24 ranking)')
# Check mandatory columns
for col in ['Physical Juris Name','Crash Severity','Ownership','x','y','FIPS','EPDO_Score']:
    non_empty = df[col].notna().sum()
    print(f'  {col}: {non_empty}/5 populated')
"
```

### Step 5: Create the GitHub Actions workflow

Duplicate `batch-all-jurisdictions.yml` → `{state}_batch_all_jurisdictions.yml`:

```yaml
name: "{State} — Download & Normalize"

on:
  workflow_dispatch:
  schedule:
    - cron: '0 6 1 * *'  # Monthly

jobs:
  download-and-normalize:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install pandas

      - name: Download statewide data
        run: |
          # State-specific download logic
          # (API call, Playwright scrape, etc.)
          python states/{state}/download.py --output states/{state}/_state/all_roads.csv

      - name: Normalize to CrashLens standard
        run: |
          python states/{state}/{abbr}_normalize.py \
            --csv states/{state}/_state/all_roads.csv \
            --output states/{state}/_state/all_roads_normalized.csv \
            --report states/{state}/_state/validation_report.json

      - name: Upload to R2
        run: |
          # Upload normalized CSV to R2 storage
          curl -X PUT "$R2_UPLOAD_URL/{state}/_state/all_roads.csv" \
            -H "Authorization: Bearer $R2_TOKEN" \
            --data-binary @states/{state}/_state/all_roads_normalized.csv
```

### Step 6: Wire into the processing pipeline

In `batch-pipeline.yml` Stage 3 (Normalization), the pipeline now calls the
state-specific normalizer which internally imports `geo_resolver`:

```yaml
      - name: "Stage 3: Normalize"
        run: |
          STATE="${{ inputs.state }}"
          ABBR="${{ inputs.state_abbr }}"

          # The state's normalize.py imports geo_resolver automatically
          python "states/${STATE}/${ABBR}_normalize.py" \
            --csv "states/${STATE}/_state/all_roads.csv" \
            --output "states/${STATE}/_state/all_roads_normalized.csv" \
            --report "states/${STATE}/_state/validation_report.json"
```

## Ownership Derivation — Decision Summary

The 4-tier fallback handles any state regardless of which columns they provide:

| What the state's data has | Tier used | Accuracy |
|---|---|---|
| SYSTEM column (like VDOT) | Tier 1 | ~99% |
| Functional Class + jurisdiction | Tier 2 | ~90% |
| Jurisdiction type only | Tier 3 | ~80% |
| Route name only | Tier 4 | ~70% |
| Nothing | Default: State Hwy | ~60% |

Key insight from VDOT data analysis:

- `SYSTEM = "VDOT *"` → always `1. State Hwy Agency` (regardless of jurisdiction)
- `SYSTEM = "NonVDOT *"` + County → always `2. County Hwy Agency`
- `SYSTEM = "NonVDOT *"` + City/Town → always `3. City or Town Hwy Agency`
- Interstate (FC=1) and Freeways (FC=2) → always State-maintained
- Local roads (FC=7) → owner matches jurisdiction type

## MPO Resolution — How it Works

1. Check `hierarchy.json` for explicit county→MPO mapping (most reliable)
2. If not in hierarchy, compute distance from county centroid to each MPO centroid
3. Compare distance against MPO effective radius: `radius = sqrt(area / π) × 1.5`
4. If within radius → assign that MPO
5. If no MPO matches → leave blank (rural jurisdiction)

The area-based radius prevents false positives where a rural county 50+ miles away
gets assigned to the nearest MPO just because it's the closest.

## Testing the geo_resolver Standalone

```bash
# CLI mode — process a CSV directly
python geo_resolver.py \
  --csv your_crashes.csv \
  --state-fips 08 \
  --state-abbr CO \
  --geo-dir states/geography \
  --hierarchy states/colorado/hierarchy.json \
  --output resolved.csv \
  --report resolution_report.json \
  --limit 1000  # test with first 1000 rows
```

## Output Column Totals

| Category | Count | Columns |
|---|---|---|
| Golden Standard | 69 | OBJECTID through y |
| Enrichment | 3 | FIPS, Place FIPS, EPDO_Score |
| Ranking | 24 | 4 scopes × 6 metrics |
| **Total** | **96** | |
