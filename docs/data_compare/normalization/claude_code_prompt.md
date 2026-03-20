# CRASH LENS — Claude Code Integration Prompt
# =============================================
# Copy everything below this line and paste into a Claude Code session
# opened at the root of your Douglas_County_2 (or crash-lens) repo.
# =============================================

I need you to integrate the CrashLens normalization pipeline into this codebase. Here's the full architecture — read it all before making any changes.

---

## WHAT THE PIPELINE IS

CrashLens normalizes crash data from any US state DOT into a universal 69-column format that the frontend expects. Every state's raw data has different column names, date formats, severity codes, and geography — the pipeline converts all of it into one standard schema.

The pipeline produces 96 output columns per crash row:
- 69 golden standard columns (the CrashLens frontend schema)
- 3 enrichment columns (FIPS, Place FIPS, EPDO_Score)
- 24 ranking columns (4 scopes × 6 metrics for the Grants tab)

---

## THE TWO SHARED FILES

### 1. `geo_resolver.py` (goes at REPO ROOT)

A 1,315-line Python module that resolves geography for ANY US state. It loads the 5 Census Bureau JSON files from `states/geography/` plus an optional per-state `hierarchy.json`, then provides fast per-row resolution for these columns:

| Column | How it's derived |
|---|---|
| Physical Juris Name | Census county/place name matching → centroid fallback |
| Juris Code | Numeric prefix extracted from FIPS |
| FIPS | 3-digit county FIPS via name match → centroid proximity |
| Place FIPS | 5-digit place FIPS for cities/towns from us_places.json |
| VDOT District | hierarchy.json: county FIPS → DOT region |
| Planning District | hierarchy.json: county FIPS → planning district |
| MPO Name | hierarchy.json explicit mapping → us_mpos.json area-based centroid matching |
| Ownership | 4-tier derivation: SYSTEM column → Functional Class + juris type → juris type only → route name pattern |
| Area Type | Census LSADC code: city/town = Urban, county = Rural |

Key class: `GeoResolver(state_fips, state_abbr, geo_dir, hierarchy_path)`
Key method: `resolver.resolve_all(rows)` — enriches all rows in-place

It depends on these files already in the repo at `states/geography/`:
- us_counties.json (3,222 records)
- us_places.json (32,333 records)
- us_mpos.json (410 records)
- us_county_subdivisions.json (36,421 records)
- us_states.json (52 records)

### 2. `state_normalize_template.py` (goes at REPO ROOT as a template)

A 1,251-line Python template that each state copies and customizes. It runs the FULL 7-phase pipeline:

| Phase | What it does |
|---|---|
| Phase 1 | Column mapping: state source columns → 69 golden standard columns via COLUMN_MAP dict |
| Phase 2 | State-specific transforms: datetime parsing, severity→KABCO, Y/N normalization, seatbelt inversion, night detection |
| Phase 3 | Composite crash ID generation: {StateAbbr}-{YYYYMMDD}-{HHMM}-{index:07d} |
| Phase 4 | Geography resolution: calls `geo_resolver.GeoResolver` to fill FIPS, Physical Juris Name, DOT District, Planning District, MPO, Ownership, Area Type |
| Phase 5 | EPDO scoring: severity × state-specific weights (FHWA 2025 default: K=883, A=94, B=21, C=11, O=1) |
| Phase 6 | Validation & auto-correction (10 checks ported from crash-data-validator v13 HTML tool): whitespace trim, duplicate detection, missing GPS, coordinate bounds, KABCO severity cross-validation, cross-field flag consistency, date/time validation, missing Facility Type/Functional Class inference, route-median GPS inference, nearest-neighbor bounds snap |
| Phase 7 | Jurisdiction ranking: 24 columns (4 scopes × 6 metrics), Rank 1 = most dangerous |

The template has clearly marked `── EDIT THIS FOR YOUR STATE ──` sections:
- STATE_FIPS, STATE_ABBR, STATE_NAME, DOT_NAME
- EPDO_WEIGHTS
- COLUMN_MAP dict (source column → target column)
- parse_datetime() function
- map_severity() function
- apply_state_transforms() function

---

## HOW A STATE-SPECIFIC FILE CONNECTS

Example: Delaware (`de_normalize.py`)

```
de_normalize.py                    ← Copied from state_normalize_template.py
  │                                   with DE-specific edits in the 4 sections
  │
  ├── imports geo_resolver.py      ← sys.path.insert(0, '../..') then from geo_resolver import GeoResolver
  │     │
  │     ├── loads states/geography/us_counties.json
  │     ├── loads states/geography/us_places.json
  │     ├── loads states/geography/us_mpos.json
  │     └── loads states/delaware/hierarchy.json
  │
  ├── Phase 1-3: DE-specific column mapping + transforms
  ├── Phase 4: GeoResolver.resolve_all(rows)  ← shared module does the work
  ├── Phase 5: EPDO scoring
  ├── Phase 6: ValidationEngine.run_all()      ← embedded in the template
  └── Phase 7: compute_rankings(rows)          ← embedded in the template
```

CLI usage:
```bash
python states/delaware/de_normalize.py \
  --csv states/delaware/_state/all_roads.csv \
  --output states/delaware/_state/all_roads_normalized.csv \
  --report states/delaware/_state/validation_report.json
```

---

## REPO STRUCTURE (what it should look like after integration)

```
repo-root/
├── geo_resolver.py                              ← PLACE HERE (shared module)
├── state_normalize_template.py                  ← PLACE HERE (template to copy)
│
├── states/
│   ├── geography/                               ← ALREADY EXISTS (verify)
│   │   ├── us_counties.json
│   │   ├── us_places.json
│   │   ├── us_mpos.json
│   │   ├── us_county_subdivisions.json
│   │   └── us_states.json
│   │
│   ├── virginia/
│   │   ├── hierarchy.json                       ← Should already exist
│   │   ├── va_normalize.py                      ← Create from template if missing
│   │   └── _state/
│   │       └── all_roads.csv                    ← Input data
│   │
│   ├── delaware/
│   │   ├── hierarchy.json                       ← Should already exist
│   │   ├── de_normalize.py                      ← Create from template
│   │   └── _state/
│   │       └── all_roads.csv
│   │
│   └── colorado/
│       ├── hierarchy.json                       ← Should already exist
│       ├── co_normalize.py                      ← Create from template
│       └── _state/
│           └── all_roads.csv
│
└── .github/workflows/
    ├── batch-all-jurisdictions.yml               ← Generic (if exists)
    ├── de_batch_all_jurisdictions.yml             ← Per-state
    └── co_batch_all_jurisdictions.yml
```

---

## HOW IT CONNECTS TO batch-all-jurisdictions.yml

The GitHub Actions workflow calls the state normalizer after downloading raw data. Here's the normalization step (Stage 3):

```yaml
      - name: "Stage 3: Normalize to CrashLens Standard"
        run: |
          STATE="${{ inputs.state }}"           # e.g. "delaware"
          ABBR="${{ inputs.state_abbr }}"       # e.g. "DE"
          STATE_DIR="states/${STATE}"

          # The state normalizer imports geo_resolver from repo root automatically
          python "${STATE_DIR}/${ABBR,,}_normalize.py" \
            --csv "${STATE_DIR}/_state/all_roads.csv" \
            --output "${STATE_DIR}/_state/all_roads_normalized.csv" \
            --report "${STATE_DIR}/_state/validation_report.json"

          # Replace the original CSV with the normalized one for downstream stages
          mv "${STATE_DIR}/_state/all_roads_normalized.csv" "${STATE_DIR}/_state/all_roads.csv"
```

The downstream stages (Stage 4: split by jurisdiction, Stage 5: split by road type, etc.) then consume the normalized CSV which now has all 96 columns in the exact format the frontend expects.

---

## WHAT I NEED YOU TO DO

1. **Check if geo_resolver.py already exists at the repo root.** If not, I'll provide it — you'll need to create it there.

2. **Check if state_normalize_template.py already exists at the repo root.** If not, I'll provide it.

3. **Check `states/geography/` for the 5 JSON files.** List what's there.

4. **For each state directory under `states/` that has a hierarchy.json:**
   - Check if a `{abbr}_normalize.py` already exists
   - If it exists, check whether it already imports `geo_resolver` — if not, update it to use the new architecture
   - If it doesn't exist, create one from the template with the correct STATE_FIPS, STATE_ABBR, STATE_NAME, DOT_NAME, and EPDO_WEIGHTS
   - For the COLUMN_MAP, if there's an existing normalizer or mapping config, preserve those mappings

5. **For any existing GitHub Actions workflows** (batch-all-jurisdictions.yml or state-specific ones):
   - Check if they have a normalization step
   - If so, verify it calls the state normalizer correctly
   - If not, add the Stage 3 normalization step shown above

6. **Test the import chain works:**
   ```bash
   cd repo-root
   python -c "from geo_resolver import GeoResolver; print('geo_resolver: OK')"
   python -c "from state_normalize_template import ValidationEngine; print('template: OK')"
   ```

7. **Show me the final file tree** and a summary of what was created/modified.

---

## STATE-SPECIFIC CONFIGURATION REFERENCE

When creating a state normalizer, use these EPDO weights:

| State | FIPS | Abbr | EPDO Preset |
|---|---|---|---|
| Virginia | 51 | VA | K=1032, A=53, B=16, C=10, O=1 (VDOT 2024) |
| Colorado | 08 | CO | K=883, A=94, B=21, C=11, O=1 (FHWA 2025) |
| Delaware | 10 | DE | K=883, A=94, B=21, C=11, O=1 (FHWA 2025) |
| Florida | 12 | FL | K=985, A=50, B=15, C=9, O=1 |
| Maryland | 24 | MD | K=883, A=94, B=21, C=11, O=1 (FHWA 2025) |
| New York | 36 | NY | K=1050, A=55, B=15, C=10, O=1 |
| California | 06 | CA | K=1100, A=58, B=17, C=11, O=1 |
| Texas | 48 | TX | K=920, A=55, B=14, C=9, O=1 |
| Any other | -- | -- | K=883, A=94, B=21, C=11, O=1 (FHWA 2025 default) |

---

## IMPORTANT CONSTRAINTS

- NEVER modify the frontend. The 69-column schema is sacred. All transformations happen in the pipeline.
- The COLUMN_MAP in each state normalizer is the ONLY place where state-specific column names are defined. Everything else is universal.
- geo_resolver.py MUST be importable from any `states/{state}/{abbr}_normalize.py` via the sys.path trick: `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))`
- The 5 geography JSON files at `states/geography/` are read-only reference data — never modify them.
- hierarchy.json is per-state and defines DOT regions → county FIPS mappings. Without it, DOT District and Planning District columns stay blank (which is acceptable for initial integration).

Start by exploring the repo structure and telling me what you find. Then proceed with the integration.
