# CrashLens — Batch Processing Architecture

## Diagram Links

- **Excalidraw (editable):** https://excalidraw.com/#json=t_292ce0deWied7k382or,i8qkdwIiAkyjmDlysj-evA

## Architecture Overview

The batch processing system consists of two GitHub Actions workflows that work together:

### batch-all-jurisdictions.yml
Registry-driven statewide download → R2 upload → pipeline trigger.

**JOB 1: Download**
1. Resolve from `download-registry.json`
2. Resolve scope (`hierarchy.json`)
3. Install dependencies (registry-driven)
4. Download statewide data
5. Merge + Standardize
6. Finalize + MD5 checksum
7. Normalize to CrashLens standard
8. Upload statewide CSV to R2
8b. Upload gzip to R2 (`_state/`)
9. Update progress manifest + git push

**Incremental Check:** Compares R2 checksum — skips pipeline if data unchanged.

**JOB 2: Trigger Pipeline** — Dispatches `batch-pipeline.yml` via `workflow_dispatch`.

**JOB 3: Notify Skipped** — Runs if data unchanged (incremental mode).

### batch-pipeline.yml
Statewide processing pipeline (Stages 0–6).

**JOB 1: Prepare**
- Resolve scope (`resolve_scope.py`)
- Download statewide CSV from R2 (canonical `_state/` path + fallback)

**JOB 2: Process**
- **Stage 0.5:** Normalize to CrashLens standard
- **Stage 0:** Initialize state-isolated cache
- **Stage 1:** Split by jurisdiction
- **Stage 2:** Split by road type (4 CSVs per jurisdiction)
- **Stage 3:** Aggregate by scope (CSV) — jurisdiction / region / MPO / federal
- **Stage 4:** Upload jurisdiction CSVs to R2 (gzip-compressed)
- **Stage 4.5:** Validate & auto-correct (headless Playwright)
- **Stage 5:** Generate forecasts (per jurisdiction, all road types)
- **Stage 5b:** Upload forecast JSONs to R2 (gzip)
- **Stage 5c:** Aggregate forecasts (region + MPO rollups)
- **Stage 5d:** Upload region/MPO forecast JSONs to R2
- **Stage 6:** Commit manifest & metadata to git

## Color Legend
- **Green** = R2 uploads
- **Yellow** = Validation/checks
- **Blue** = Git commits
- **Red arrow** = `workflow_dispatch` connection between workflows

## External Services
- **Cloudflare R2** (`crash-lens-data` bucket) — all CSV and forecast storage
- **download-registry.json** — state config, scripts, and download commands
- **hierarchy.json** — scope resolution (regions, MPOs, jurisdictions)
- **AWS Bedrock** — forecast generation
