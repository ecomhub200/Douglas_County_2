# GitHub Action Activation Plan — State Workflow Management

> **Created:** 2026-02-17
> **Purpose:** Guide for Claude Code (or developer) to disable idle state workflows and re-activate them when ready.
> **Estimated savings:** ~156 GitHub Actions minutes/month by disabling 26 unused scheduled workflows.

---

## Background

Only **Virginia**, **Colorado**, and **Montgomery County (MD)** have fully working pipelines with crash download, CMF dataset, and/or grant dataset support. The remaining 26 state download workflows all have active monthly cron schedules (`0 11 1 * *`) that consume ~6 minutes each on the 1st of every month — burning ~156 minutes/month with no usable output.

---

## Phase 1: Disable Scheduled Triggers (Immediate)

### What to Do

For each of the 26 state workflows listed below, **comment out the `schedule:` block** so they retain `workflow_dispatch:` (manual trigger) only.

### Change Pattern

In each workflow YAML, change:

```yaml
# BEFORE
on:
  schedule:
    - cron: '0 11 1 * *'
  workflow_dispatch:
```

to:

```yaml
# AFTER — schedule disabled, manual trigger preserved
on:
  # schedule:
  #   - cron: '0 11 1 * *'     # DISABLED — re-enable when pipeline is ready (see activation checklist below)
  workflow_dispatch:
```

### Workflows to Disable (26 total)

| # | Workflow File | State | R2 Prefix | Data Directory |
|---|---------------|-------|-----------|----------------|
| 1 | `.github/workflows/download-alaska-crash-data.yml` | Alaska | `alaska` | `data/AlaskaDOT` |
| 2 | `.github/workflows/download-arkansas-crash-data.yml` | Arkansas | `arkansas` | `data/ArkansasDOT` |
| 3 | `.github/workflows/download-connecticut-crash-data.yml` | Connecticut | `connecticut` | `data/ConnecticutDOT` |
| 4 | `.github/workflows/download-delaware-crash-data.yml` | Delaware | `delaware` | `data/DelawareDOT` |
| 5 | `.github/workflows/download-florida-crash-data.yml` | Florida | `florida` | `data/FloridaDOT` |
| 6 | `.github/workflows/download-georgia-crash-data.yml` | Georgia | `georgia` | `data/GeorgiaDOT` |
| 7 | `.github/workflows/download-hawaii-crash-data.yml` | Hawaii | `hawaii` | `data/HawaiiDOT` |
| 8 | `.github/workflows/download-idaho-crash-data.yml` | Idaho | `idaho` | `data/IdahoDOT` |
| 9 | `.github/workflows/download-illinois-crash-data.yml` | Illinois | `illinois` | `data/IllinoisDOT` |
| 10 | `.github/workflows/download-iowa-crash-data.yml` | Iowa | `iowa` | `data/IowaDOT` |
| 11 | `.github/workflows/download-louisiana-crash-data.yml` | Louisiana | `louisiana` | `data/LouisianaDOT` |
| 12 | `.github/workflows/download-maryland-crash-data.yml` | Maryland | `maryland` | `data/MarylandDOT` |
| 13 | `.github/workflows/download-massachusetts-crash-data.yml` | Massachusetts | `massachusetts` | `data/MassachusettsDOT` |
| 14 | `.github/workflows/download-mississippi-crash-data.yml` | Mississippi | `mississippi` | `data/MississippiDOT` |
| 15 | `.github/workflows/download-montana-crash-data.yml` | Montana | `montana` | `data/MontanaDOT` |
| 16 | `.github/workflows/download-nevada-crash-data.yml` | Nevada | `nevada` | `data/NevadaDOT` |
| 17 | `.github/workflows/download-new-york-crash-data.yml` | New York | `new-york` | `data/NewYorkDOT` |
| 18 | `.github/workflows/download-nyc-crash-data.yml` | NYC | `nyc` | `data/NYCDOT` |
| 19 | `.github/workflows/download-ohio-crash-data.yml` | Ohio | `ohio` | `data/OhioDOT` |
| 20 | `.github/workflows/download-oklahoma-crash-data.yml` | Oklahoma | `oklahoma` | `data/OklahomaDOT` |
| 21 | `.github/workflows/download-oregon-crash-data.yml` | Oregon | `oregon` | `data/OregonDOT` |
| 22 | `.github/workflows/download-pennsylvania-crash-data.yml` | Pennsylvania | `pennsylvania` | `data/PennsylvaniaDOT` |
| 23 | `.github/workflows/download-south-carolina-crash-data.yml` | South Carolina | `south-carolina` | `data/SouthCarolinaDOT` |
| 24 | `.github/workflows/download-texas-crash-data.yml` | Texas | `texas` | `data/TexasDOT` |
| 25 | `.github/workflows/download-utah-crash-data.yml` | Utah | `utah` | `data/UtahDOT` |
| 26 | `.github/workflows/download-vermont-crash-data.yml` | Vermont | `vermont` | `data/VermontDOT` |
| 27 | `.github/workflows/download-washington-crash-data.yml` | Washington | `washington` | `data/WashingtonDOT` |
| 28 | `.github/workflows/download-west-virginia-crash-data.yml` | West Virginia | `west-virginia` | `data/WestVirginiaDOT` |
| 29 | `.github/workflows/download-wisconsin-crash-data.yml` | Wisconsin | `wisconsin` | `data/WisconsinDOT` |

### Workflows to KEEP Running (Do NOT touch)

| Workflow File | Purpose | Schedule |
|---------------|---------|----------|
| `.github/workflows/download-data.yml` | Virginia crash + grants + CMF | Multiple crons (monthly, weekly, quarterly) |
| `.github/workflows/download-cdot-crash-data.yml` | Colorado crash download | 1st of every month |
| `.github/workflows/process-cdot-data.yml` | Colorado processing pipeline | Chained after CO download |
| `.github/workflows/moco_crash_download.yml` | Montgomery County MD download | 1st of every month |
| `.github/workflows/process-moco-data.yml` | Montgomery County processing | Chained after MoCo download |
| `.github/workflows/validate-data.yml` | Monthly data validation | First Monday of each month |
| `.github/workflows/generate-social-media.yml` | Weekly social media content | Every Monday |
| `.github/workflows/send-notifications.yml` | Notifications (daily/weekly/monthly) | Multiple crons |
| `.github/workflows/batch-all-jurisdictions.yml` | Bulk processing (manual only) | workflow_dispatch only |
| `.github/workflows/seed-r2.yml` | R2 seeding (manual only) | workflow_dispatch only |
| `.github/workflows/create-r2-folders.yml` | R2 folder setup (manual only) | workflow_dispatch only |
| `.github/workflows/rename-r2-keys.yml` | R2 key rename (manual only) | workflow_dispatch only |
| `.github/workflows/migrate-forecasts-to-r2.yml` | Forecast migration (manual only) | workflow_dispatch only |

---

## Phase 2: Re-Activation Checklist (Per State)

When you are ready to bring a new state online, complete ALL items below before uncommenting the schedule trigger.

### Pre-Activation Checklist

- [ ] **Download script exists and works** — Run manually via `workflow_dispatch` and confirm CSVs are produced
  ```
  # Test: trigger manually from GitHub Actions UI or CLI
  gh workflow run download-{state}-crash-data.yml -f jurisdiction=statewide
  ```
- [ ] **Data lands in R2** — Verify CSVs appear at `s3://crash-lens-data/{r2_prefix}/statewide/`
- [ ] **Processing pipeline created** — Create `process-{state}-data.yml` modeled on `process-cdot-data.yml`
  - Must include: CONVERT -> VALIDATE -> GEOCODE -> SPLIT -> PREDICT stages
  - Chain via `workflow_run` from the download workflow
- [ ] **CMF dataset configured** — State-specific CMF data is available and integrated
- [ ] **Grants dataset configured** — State-specific grants data source identified and working
- [ ] **config.json updated** — State/jurisdiction entries added to application config
- [ ] **R2 folder structure created** — Run `create-r2-folders.yml` for the new state if needed
- [ ] **Manual end-to-end test passed** — Full pipeline (download -> process -> R2 upload -> app loads data) works
- [ ] **Schedule re-enabled** — Uncomment the `schedule:` block in the workflow YAML

### Activation Steps

1. Complete all checklist items above
2. In the workflow file, uncomment the schedule block:
   ```yaml
   on:
     schedule:
       - cron: '0 11 1 * *'
     workflow_dispatch:
   ```
3. Commit with message: `chore: activate {State} scheduled workflow — pipeline ready`
4. Monitor the first scheduled run to confirm it completes successfully
5. Update the "Workflows to KEEP Running" table in this document

---

## Phase 3: Priority Order for State Onboarding (Suggested)

States with the most accessible open data portals and highest crash volumes:

| Priority | State | Rationale |
|----------|-------|-----------|
| 1 | Florida | Large state, FDOT has open Socrata portal |
| 2 | Texas | TxDOT CRIS system, high crash volume |
| 3 | New York | NYC open data already separate, NY state has portal |
| 4 | Ohio | ODOT has public crash data portal |
| 5 | Pennsylvania | PennDOT crash data accessible |
| 6 | Illinois | IDOT has crash reporting system |
| 7 | Georgia | GDOT open data |
| 8 | Others | As data access is confirmed |

---

## Cost Summary

| Scenario | Estimated Minutes/Month |
|----------|------------------------|
| **Current (all scheduled)** | ~334 min |
| **After Phase 1 (26 disabled)** | ~178 min |
| **Savings** | ~156 min/month (~47% reduction) |

---

## Notes

- Workflow files are NOT deleted — they remain in `.github/workflows/` as templates
- All workflows retain `workflow_dispatch` so they can be triggered manually at any time for testing
- This plan is idempotent — running the disable step multiple times has no additional effect
- GitHub auto-disables scheduled workflows after 60 days of repo inactivity regardless
