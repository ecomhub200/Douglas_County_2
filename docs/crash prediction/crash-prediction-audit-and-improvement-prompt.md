# Crash Prediction Module — Data Source Audit & UI Improvement Prompt

**Date:** March 5, 2026
**Auditor:** Claude (Traffic Safety Engineering + Software Analysis)
**Scope:** Crash Prediction tab in `app/index.html` + `scripts/generate_forecast.py` + `data/forecasts_*.json`

---

## Part 1: Data Source Verification

### Finding: The prediction module uses TWO storage systems — confirmed ✅

**Storage System 1 — Cloudflare R2 (Primary Cloud CDN)**

The `initPredictionTab()` function (line 137474) constructs tier-aware R2 paths and fetches forecast JSON via `resolveDataUrl()`, which maps through the R2 manifest to CDN URLs. The path structure is:

- County tier: `{r2Prefix}/{jurisdiction}/forecasts_{roadType}.json`
- State tier: `{r2Prefix}/_state/forecasts_{roadType}.json`
- Region tier: `{r2Prefix}/_region/{regionId}/forecasts_{roadType}.json`
- MPO tier: `{r2Prefix}/_mpo/{mpoId}/forecasts_{roadType}.json`
- Federal tier: `_national/forecasts_{roadType}.json`

R2 credentials are configured via `CF_ACCOUNT_ID`, `CF_R2_ACCESS_KEY_ID`, `CF_R2_SECRET_ACCESS_KEY`, and `R2_BUCKET_NAME` in `server/qdrant-proxy.js`.

**Storage System 2 — Local File System (Fallback)**

When R2 fails (network error, missing file), the module cascades through local fallback paths (lines 137531–137554):

1. `data/{stateDir}/forecasts_{roadType}.json`
2. `data/{stateDir}/{jurisdiction}/forecasts_{roadType}.json`
3. `data/forecasts_{roadType}.json`

Three local forecast files exist:
- `data/forecasts_all_roads.json` (375 KB)
- `data/forecasts_county_roads.json` (374 KB)
- `data/forecasts_no_interstate.json` (385 KB)

### ⚠️ Critical Issue: Model Tag Says "synthetic-demo"

The forecast JSON files contain `"model": "synthetic-demo"` (line 2 of `forecasts_county_roads.json`). This means the **local fallback data is generated via `--dry-run` mode** from `generate_forecast.py`, NOT from the actual Chronos-2 SageMaker endpoint. The data structure is real (52,226 crashes, 2019-01 through 2025-11, correct EPDO weights), but the forecast values themselves are synthetic extrapolations, not true Chronos-2 predictions.

**To confirm R2 has real model output:** Check whether the R2-hosted forecast files use `"model": "Chronos-2"` instead of `"synthetic-demo"`. If they do, then production users are getting real predictions. If they also say `synthetic-demo`, the SageMaker pipeline (`generate_forecast.py`) needs to be run against the actual endpoint with valid AWS credentials.

### Data Pipeline Summary

```
Historical Crash CSVs (data/CDOT/*.csv)
    │
    ▼
generate_forecast.py (Temporal Embedding → Chronos-2 SageMaker)
    │
    ├──► R2 Upload (production forecasts → CDN)
    │
    └──► Local fallback files (data/forecasts_*.json)
            │
            ▼
initPredictionTab() fetches R2 first → falls back to local
    │
    ▼
6 Matrices (M01-M06) + 10 Derived Metrics → UI Rendering
```

### Firebase/Firestore Role Clarification

Firebase Firestore does NOT store prediction data. It stores user profiles, subscription status, and Stripe customer IDs. The two storage systems for predictions are specifically R2 (primary) and local filesystem (fallback).

---

## Part 2: Current UI Assessment

### What Exists Today (3 Sub-tabs)

**Dashboard Sub-tab:**
- 4 KPI cards (Predicted Total, K+A Severe, Highest Risk Corridor, Monthly Average)
- Composite Risk Score gauge
- 8 Chart.js charts (Total Forecast, EPDO, KA, Severity by KABCO, Crash Type, Confidence Band, Crash Type Momentum, Factor Involvement Rates)
- Crash Pattern Matrix (Severity × Crash Type heatmap)
- Seasonal Risk Calendar (monthly EPDO heatmap)
- Severity Shift Index
- Corridor Risk Rank Movement table
- Location Type Split (Intersection vs Segment)

**Corridors Sub-tab:**
- Corridor forecast comparison chart (top 10 routes)
- Corridor ranking table with checkboxes (select up to 5)
- Detail panel with KPI comparison, forecast chart, recommended actions
- Cross-tab navigation (→ Hotspots, → CMF)

**Safety Trends Sub-tab:**
- Contributing factor trends chart (speed, alcohol, pedestrian, bicycle, nighttime)
- Program Effectiveness Scorecard (factor cards with bar charts)
- Location Type Forecast (bar chart + cards)

### Identified Gaps Addressed in This Prompt

1. **Confidence Communication is Weak** — The confidence band chart exists but doesn't explain what it means for decision-making. Engineers need to know: "Is this prediction reliable enough to justify a $500K project?"

2. **Weak Export/Reporting** — PDF export is plain text (`exportPredictionPDF()` outputs a .txt file). No proper formatted report for stakeholders or grant applications.

3. **Cross-Tab Navigation is Broken** — `jumpPredCorridorToHotspot()` navigates but doesn't filter. `jumpPredCorridorToCMF()` navigates but passes no context. Both need to actually connect to the destination tab meaningfully.

---

## Part 3: Claude Code Implementation Prompt

```
# Crash Prediction UI Enhancement — Implementation Prompt

## Context
You are working on `app/index.html` in the CrashLens crash analysis tool. The Crash Prediction tab (id="tab-prediction") currently has 3 sub-tabs: Dashboard, Corridors, and Safety Trends. The prediction module loads forecast JSON from R2 (primary) or local fallback, containing 6 matrices (M01-M06) and 10 derived metrics.

## CRITICAL: Read Before Coding
1. Read `CLAUDE.md` at the project root — it contains architecture rules, state objects, function naming conventions, and common pitfalls.
2. Read the prediction state object at line 137380 of `app/index.html`.
3. Read `initPredictionTab()` at line 137474 to understand data loading.
4. Search for ALL existing `renderPred*` functions before creating new ones — NEVER duplicate function names.
5. Never push directly — always create a PR.

## Overview of Changes
Three targeted improvements to transform raw prediction data into actionable safety intelligence: (1) help engineers understand HOW RELIABLE the predictions are for decision-making, (2) provide professional export reports suitable for stakeholders and grant applications, and (3) fix broken cross-tab navigation so engineers can seamlessly move from prediction insights to countermeasure actions.

---

## Task 1: Enhance Confidence Communication

### Problem
The current Prediction Confidence chart (canvas `predChartConfidence`) renders a confidence band width over time, but it doesn't tell the engineer anything actionable. A traffic safety engineer needs to know: "Can I use this forecast to justify a $500K HSIP project, or is the uncertainty too wide to rely on?"

### 1.1 Add Decision Confidence Indicator to Dashboard

Below the M01 Total Forecast Chart insight box (`predTotalInsight`, around line 9750), add a new HTML container:

```html
<!-- Decision Confidence Indicator -->
<div id="predDecisionConfidence" class="pred-insight-box" style="display:none;background:#f8fafc;border-left:4px solid #64748b;margin-top:.5rem">
  <!-- Rendered dynamically by renderDecisionConfidence() -->
</div>
```

### 1.2 Implement `renderPredDecisionConfidence()` Function

Add this function in the prediction JavaScript section (near the other insight rendering functions). It should be called from `renderPredTotalChart()` after the existing insight text is set (around line 138160).

**Logic:**

```javascript
function renderPredDecisionConfidence() {
    const d = predictionState.data;
    if (!d || !d.matrices.m01) return;

    const el = document.getElementById('predDecisionConfidence');
    if (!el) return;

    const horizon = predictionState.activeHorizon || 6;
    const m01 = d.matrices.m01;
    const p50 = (m01.forecast.p50 || []).slice(0, horizon);
    const p10 = (m01.forecast.p10 || []).slice(0, horizon);
    const p90 = (m01.forecast.p90 || []).slice(0, horizon);

    if (!p50.length) { el.style.display = 'none'; return; }

    // Calculate average predicted value and average confidence band width
    const avgPredicted = p50.reduce((a, b) => a + b, 0) / p50.length;
    const avgWidth = p90.reduce((sum, val, i) => sum + (val - p10[i]), 0) / p90.length;

    // Coefficient of variation of the prediction band
    const cv = avgWidth / Math.max(avgPredicted, 1);

    let level, color, icon, text, useCases;
    if (cv < 0.15) {
        level = 'High';
        color = '#10b981';
        icon = '🟢';
        text = 'High prediction confidence';
        useCases = 'Suitable for HSIP project justification, grant applications, and safety improvement programming. The model has strong historical patterns to draw from.';
    } else if (cv < 0.30) {
        level = 'Moderate';
        color = '#f59e0b';
        icon = '🟡';
        text = 'Moderate prediction confidence';
        useCases = 'Suitable for planning, programming, and trend monitoring. For project-level decisions, consider running a sensitivity analysis or supplementing with before/after studies.';
    } else {
        level = 'Low';
        color = '#ef4444';
        icon = '🔴';
        text = 'Low prediction confidence';
        useCases = 'Use for general awareness and early warning only. The wide confidence band suggests high variability — gather additional data or extend the historical window before committing resources.';
    }

    // Calculate how the confidence width changes over the forecast horizon
    const firstMonthWidth = p90[0] - p10[0];
    const lastMonthWidth = p90[p90.length - 1] - p10[p10.length - 1];
    const widthGrowthPct = firstMonthWidth ? ((lastMonthWidth - firstMonthWidth) / firstMonthWidth * 100) : 0;
    const widthTrend = widthGrowthPct > 10
        ? `Uncertainty grows ${Math.round(widthGrowthPct)}% from Month 1 to Month ${horizon} — shorter horizons are more reliable.`
        : `Uncertainty remains relatively stable across the ${horizon}-month horizon.`;

    el.style.borderLeftColor = color;
    el.innerHTML = `
        <div style="display:flex;align-items:flex-start;gap:.75rem">
            <div style="font-size:1.5rem;line-height:1">${icon}</div>
            <div style="flex:1">
                <div style="font-weight:700;color:${color};font-size:.9rem;margin-bottom:.25rem">${text}</div>
                <div style="font-size:.82rem;color:#475569;line-height:1.5;margin-bottom:.5rem">${useCases}</div>
                <div style="font-size:.78rem;color:#64748b;line-height:1.4">
                    <strong>Band width:</strong> ±${Math.round(avgWidth / 2)} crashes/month avg
                    (CV: ${(cv * 100).toFixed(1)}%). ${widthTrend}
                </div>
            </div>
        </div>`;
    el.style.display = '';
}
```

### 1.3 Also Add Confidence Context to Corridor Detail Panel

In `updatePredCorridorDetailPanel()` (line 137772), after the "Recommended Actions" section, add a per-corridor confidence note. For each selected corridor, calculate the CV from its M03 forecast bands and display a one-line confidence statement.

### 1.4 Integration Points

- Call `renderPredDecisionConfidence()` at the end of `renderPredTotalChart()` (after line 138161)
- Call it again from `setPredictionConfidence()` (line 137607) so changing the confidence level dropdown re-renders the indicator
- Call it from `setPredictionHorizon()` (line 137936) since shorter horizons typically have tighter bands

---

## Task 2: Improve Export — Proper PDF Report

### Problem
The current `exportPredictionPDF()` function (line 137699) generates a plain `.txt` file — not a real PDF. It has no formatting, no tables, no charts, and no visual hierarchy. Traffic engineers need a professional report they can attach to HSIP applications, send to county commissioners, or present at safety committee meetings.

### 2.1 Replace `exportPredictionPDF()` Entirely

Replace the existing function (lines 137699–137719) with a new implementation that generates a styled HTML document and triggers the browser's print-to-PDF flow:

```javascript
function exportPredictionPDF() {
    const d = predictionState.data;
    if (!d) { alert('No forecast data to export.'); return; }

    const h = predictionState.activeHorizon || 6;
    const confLevel = predictionState.confidenceLevel || 80;
    const jurisdiction = predictionState.loadedJurisdiction || 'Unknown';
    const jurisdictionName = (appConfig?.jurisdictions?.[jurisdiction]?.name) || jurisdiction;
    const roadTypeLabels = {
        county_roads: 'County/City Roads Only',
        no_interstate: 'All Roads (No Interstate)',
        all_roads: 'All Roads (Incl. Interstates)',
        dot_roads: 'DOT Roads Only',
        non_dot_roads: 'Non-DOT Roads',
        statewide_all_roads: 'Statewide All Roads'
    };
    const roadLabel = roadTypeLabels[d.roadType || predictionState.activeRoadType] || 'All Roads';

    // ---- Compute all data needed for the report ----

    // M01: Total forecast
    const m01 = d.matrices.m01;
    const p50 = (m01.forecast.p50 || []).slice(0, h);
    const p10 = (m01.forecast.p10 || []).slice(0, h);
    const p90 = (m01.forecast.p90 || []).slice(0, h);
    const months = (m01.forecast.months || []).slice(0, h);
    const totalPred = Math.round(p50.reduce((a, b) => a + b, 0));
    const totalLo = Math.round(p10.reduce((a, b) => a + b, 0));
    const totalHi = Math.round(p90.reduce((a, b) => a + b, 0));
    const histValues = m01.history || [];
    const histSum = histValues.slice(-h).reduce((a, hh) => a + hh.value, 0);
    const changePct = histSum ? ((totalPred - histSum) / histSum * 100) : 0;

    // M02: K+A
    let kaPred = '—', kaEpdo = '—';
    if (d.matrices.m02) {
        const kFc = d.matrices.m02.forecast.K;
        const aFc = d.matrices.m02.forecast.A;
        if (kFc && aFc) {
            const kSum = (kFc.p50 || []).slice(0, h).reduce((a, b) => a + b, 0);
            const aSum = (aFc.p50 || []).slice(0, h).reduce((a, b) => a + b, 0);
            kaPred = Math.round(kSum + aSum);
            kaEpdo = Math.round(kSum * 462 + aSum * 62).toLocaleString();
        }
    }

    // M03: Corridor rankings
    let corridorTableRows = '';
    if (d.matrices.m03) {
        const corridorData = [];
        for (const [name, corr] of Object.entries(d.matrices.m03.corridors)) {
            const cHist = (corr.history || []).slice(-h).reduce((a, hh) => a + hh.value, 0);
            const cPred = (corr.forecast.p50 || []).slice(0, h).reduce((a, b) => a + b, 0);
            const cChange = cHist ? ((cPred - cHist) / cHist * 100) : 0;
            const riskLevel = cPred / h > 33 ? 'HIGH' : cPred / h > 8 ? 'MEDIUM' : 'LOW';
            corridorData.push({ name, hist: Math.round(cHist), pred: Math.round(cPred), change: cChange, epdo: corr.stats?.epdo || 0, risk: riskLevel });
        }
        corridorData.sort((a, b) => b.pred - a.pred);
        corridorTableRows = corridorData.map((c, i) => {
            const changeColor = c.change > 5 ? '#dc2626' : c.change < -5 ? '#16a34a' : '#475569';
            const riskColor = c.risk === 'HIGH' ? '#dc2626' : c.risk === 'MEDIUM' ? '#d97706' : '#16a34a';
            return `<tr>
                <td style="text-align:center;font-weight:600">${i + 1}</td>
                <td style="font-weight:600">${esc(c.name)}</td>
                <td style="text-align:right">${c.hist.toLocaleString()}</td>
                <td style="text-align:right;font-weight:600">${c.pred.toLocaleString()}</td>
                <td style="text-align:right;color:${changeColor};font-weight:600">${c.change > 0 ? '+' : ''}${c.change.toFixed(1)}%</td>
                <td style="text-align:right">${c.epdo.toLocaleString()}</td>
                <td style="text-align:center"><span style="background:${riskColor}15;color:${riskColor};padding:2px 10px;border-radius:12px;font-size:.75rem;font-weight:700">${c.risk}</span></td>
            </tr>`;
        }).join('');
    }

    // M05: Factor trends
    let factorTableRows = '';
    if (d.matrices.m05) {
        const factorLabels = { speed: 'Speed-Related', alcohol: 'Alcohol-Involved', pedestrian: 'Pedestrian', bicycle: 'Bicycle', night: 'Nighttime' };
        for (const [fName, fData] of Object.entries(d.matrices.m05.factors)) {
            const fHist = (fData.history || []).slice(-h).reduce((a, hh) => a + hh.value, 0);
            const fPred = (fData.forecast?.p50 || []).slice(0, h).reduce((a, b) => a + b, 0);
            const fChange = fHist ? ((fPred - fHist) / fHist * 100) : 0;
            const verdict = fChange < -5 ? 'Declining' : fChange > 5 ? 'Rising' : 'Stable';
            const verdictColor = verdict === 'Rising' ? '#dc2626' : verdict === 'Declining' ? '#16a34a' : '#475569';
            factorTableRows += `<tr>
                <td style="font-weight:600">${factorLabels[fName] || fName}</td>
                <td style="text-align:right">${Math.round(fHist)}</td>
                <td style="text-align:right;font-weight:600">${Math.round(fPred)}</td>
                <td style="text-align:right;color:${verdictColor === '#dc2626' ? '#dc2626' : verdictColor};font-weight:600">${fChange > 0 ? '+' : ''}${fChange.toFixed(1)}%</td>
                <td style="color:${verdictColor};font-weight:600">${verdict}</td>
            </tr>`;
        }
    }

    // Monthly forecast table
    const monthlyTableRows = months.map((m, i) => `<tr>
        <td>${m}</td>
        <td style="text-align:right;font-weight:600">${Math.round(p50[i])}</td>
        <td style="text-align:right">${Math.round(p10[i])}</td>
        <td style="text-align:right">${Math.round(p90[i])}</td>
    </tr>`).join('');

    // ---- Build HTML Report ----
    const changeDir = changePct > 2 ? 'increase' : changePct < -2 ? 'decrease' : 'remain stable';
    const changeIcon = changePct > 5 ? '⚠️' : changePct < -5 ? '✅' : 'ℹ️';

    const html = `<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<title>Crash Prediction Report — ${esc(jurisdictionName)}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Segoe UI', Arial, sans-serif; max-width: 850px; margin: 0 auto; padding: 2rem; color: #1e293b; font-size: 13px; line-height: 1.6; }
  h1 { font-size: 1.6rem; color: #1e293b; margin-bottom: .25rem; }
  h2 { font-size: 1.1rem; color: #1e40af; margin: 1.75rem 0 .75rem; padding-bottom: .4rem; border-bottom: 2px solid #dbeafe; }
  h3 { font-size: .95rem; color: #334155; margin: 1rem 0 .5rem; }
  .subtitle { color: #64748b; font-size: .85rem; margin-bottom: 1.5rem; }
  .header-bar { background: linear-gradient(135deg, #1e40af, #3b82f6); color: white; padding: 1.25rem 1.5rem; border-radius: 10px; margin-bottom: 1.5rem; }
  .header-bar h1 { color: white; }
  .header-bar .subtitle { color: #93c5fd; }
  .kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: .75rem; margin: 1rem 0; }
  .kpi-card { border: 1px solid #e2e8f0; border-radius: 8px; padding: .75rem; text-align: center; }
  .kpi-card .value { font-size: 1.4rem; font-weight: 700; color: #1e293b; }
  .kpi-card .label { font-size: .7rem; color: #64748b; margin-top: .15rem; }
  .kpi-card .sub { font-size: .65rem; color: #94a3b8; margin-top: .1rem; }
  .summary-box { background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 1rem; margin: 1rem 0; font-size: .85rem; line-height: 1.7; }
  table { width: 100%; border-collapse: collapse; margin: .75rem 0; font-size: .8rem; }
  th, td { border: 1px solid #e2e8f0; padding: .4rem .6rem; }
  th { background: #f1f5f9; font-weight: 600; text-align: left; font-size: .75rem; text-transform: uppercase; letter-spacing: .3px; color: #475569; }
  .footer { margin-top: 2rem; padding-top: .75rem; border-top: 1px solid #e2e8f0; font-size: .7rem; color: #94a3b8; display: flex; justify-content: space-between; }
  .page-break { page-break-before: always; }
  @media print {
    body { padding: .5rem; font-size: 11px; }
    .header-bar { padding: .75rem 1rem; }
    .kpi-row { gap: .5rem; }
    .no-print { display: none; }
  }
</style>
</head><body>

<div class="header-bar">
  <h1>Crash Prediction Report</h1>
  <div class="subtitle">${esc(jurisdictionName)} · ${roadLabel} · ${h}-Month Forecast · ${confLevel}% Confidence Level</div>
</div>

<div class="summary-box">
  ${changeIcon} <strong>Executive Summary:</strong> Based on ${d.summary.totalCrashes.toLocaleString()} historical crashes (${d.summary.dateRange.start} to ${d.summary.dateRange.end}), the model predicts <strong>${totalPred.toLocaleString()} crashes</strong> over the next ${h} months — a <strong>${changePct > 0 ? '+' : ''}${changePct.toFixed(1)}%</strong> ${changeDir} from the prior equivalent period. The ${confLevel}% confidence interval is ${totalLo.toLocaleString()} to ${totalHi.toLocaleString()}. Fatal and serious injury (K+A) crashes are forecast at <strong>${kaPred}</strong> (EPDO: ${kaEpdo}).
</div>

<div class="kpi-row">
  <div class="kpi-card" style="border-top: 3px solid #3b82f6">
    <div class="value">${totalPred.toLocaleString()}</div>
    <div class="label">Total Predicted (${h}mo)</div>
    <div class="sub">${confLevel}% CI: ${totalLo.toLocaleString()}–${totalHi.toLocaleString()}</div>
  </div>
  <div class="kpi-card" style="border-top: 3px solid #dc2626">
    <div class="value">${kaPred}</div>
    <div class="label">K+A Severe Crashes</div>
    <div class="sub">EPDO: ${kaEpdo}</div>
  </div>
  <div class="kpi-card" style="border-top: 3px solid #f59e0b">
    <div class="value" style="font-size:1rem">${predictionState.corridorRows?.[0]?.name || '—'}</div>
    <div class="label">Highest Risk Corridor</div>
    <div class="sub">${predictionState.corridorRows?.[0]?.pred12 || '—'} predicted</div>
  </div>
  <div class="kpi-card" style="border-top: 3px solid #10b981">
    <div class="value">${d.summary.monthlyAvg.toFixed(0)}</div>
    <div class="label">Monthly Average</div>
    <div class="sub">${d.summary.recentTrend.changePct > 0 ? '+' : ''}${d.summary.recentTrend.changePct.toFixed(1)}% recent trend</div>
  </div>
</div>

<h2>Monthly Forecast Detail</h2>
<table>
  <thead><tr><th>Month</th><th style="text-align:right">Predicted (P50)</th><th style="text-align:right">Lower (P10)</th><th style="text-align:right">Upper (P90)</th></tr></thead>
  <tbody>${monthlyTableRows}</tbody>
</table>

${corridorTableRows ? `
<h2>Corridor Risk Ranking</h2>
<table>
  <thead><tr><th style="text-align:center">Rank</th><th>Corridor</th><th style="text-align:right">Historical (${h}mo)</th><th style="text-align:right">Predicted (${h}mo)</th><th style="text-align:right">Change</th><th style="text-align:right">EPDO</th><th style="text-align:center">Risk</th></tr></thead>
  <tbody>${corridorTableRows}</tbody>
</table>
` : ''}

${factorTableRows ? `
<div class="page-break"></div>
<h2>Contributing Factor Trends</h2>
<table>
  <thead><tr><th>Factor</th><th style="text-align:right">Previous (${h}mo)</th><th style="text-align:right">Predicted (${h}mo)</th><th style="text-align:right">Change</th><th>Verdict</th></tr></thead>
  <tbody>${factorTableRows}</tbody>
</table>
` : ''}

<h2>Report Metadata</h2>
<table>
  <tbody>
    <tr><td style="width:200px;font-weight:600">Model</td><td>${d.model || 'Unknown'}</td></tr>
    <tr><td style="font-weight:600">Historical Data Range</td><td>${d.summary.dateRange.start} to ${d.summary.dateRange.end}</td></tr>
    <tr><td style="font-weight:600">Forecast Horizon</td><td>${h} months</td></tr>
    <tr><td style="font-weight:600">Confidence Level</td><td>${confLevel}%</td></tr>
    <tr><td style="font-weight:600">Road Type Filter</td><td>${roadLabel}</td></tr>
    <tr><td style="font-weight:600">EPDO Weights</td><td>K=${d.epdoWeights.K}, A=${d.epdoWeights.A}, B=${d.epdoWeights.B}, C=${d.epdoWeights.C}, O=${d.epdoWeights.O}</td></tr>
    <tr><td style="font-weight:600">Quantile Levels</td><td>${(d.quantileLevels || []).join(', ')}</td></tr>
  </tbody>
</table>

<div class="footer">
  <div>Generated by CRASH LENS Prediction Module · ${new Date().toLocaleDateString()} ${new Date().toLocaleTimeString()}</div>
  <div>${esc(jurisdictionName)} · ${roadLabel}</div>
</div>

<div class="no-print" style="text-align:center;margin-top:1.5rem;padding:1rem;background:#f1f5f9;border-radius:8px">
  <p style="font-size:.85rem;color:#475569;margin-bottom:.5rem"><strong>💡 Tip:</strong> Use your browser's Print function (Ctrl+P / Cmd+P) to save as PDF.</p>
  <p style="font-size:.75rem;color:#94a3b8">Select "Save as PDF" as the destination for best results. Use "Landscape" for wider tables.</p>
</div>

</body></html>`;

    const win = window.open('', '_blank', 'width=900,height=700');
    win.document.write(html);
    win.document.close();
    // Auto-trigger print after a brief delay for rendering
    setTimeout(() => win.print(), 300);
}
```

### 2.2 Update Export Menu Label

In the export dropdown menu (line 9652), change the PDF button label to be more descriptive:

```html
<button class="export-dropdown-item" onclick="exportPredictionPDF();closePredExportMenu()">📄 Export Formatted PDF Report</button>
```

---

## Task 3: Cross-Tab Integration Improvements

### Problem
The Corridors sub-tab has two action buttons per corridor: "🔥 Hotspots" and "🔧 CMF". Both currently navigate to the target tab but fail to pass any context — the engineer lands on an empty tab with no connection to the corridor they just clicked from.

### 3.1 Fix `jumpPredCorridorToHotspot()` (Currently Broken)

The current implementation (line 137703) navigates to hotspots but doesn't filter to the corridor. Replace the entire function:

```javascript
function jumpPredCorridorToHotspot(corridorName) {
    navigateTo('hotspots');
    setTimeout(() => {
        // Set the grouping to "by route" so the corridor appears in the results
        const groupBy = document.getElementById('hsGroupBy');
        if (groupBy) groupBy.value = 'route';
        analyzeHotspots();

        // Wait for hotspot analysis to complete, then find and highlight the corridor
        setTimeout(() => {
            const rows = document.querySelectorAll('#hsResultsTable tbody tr');
            let found = false;
            for (const row of rows) {
                if (row.textContent.includes(corridorName)) {
                    row.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    // Flash highlight effect
                    row.style.transition = 'background-color 0.3s';
                    row.style.backgroundColor = '#dbeafe';
                    setTimeout(() => {
                        row.style.backgroundColor = '';
                        setTimeout(() => row.style.transition = '', 300);
                    }, 3000);
                    found = true;
                    break;
                }
            }
            if (!found) {
                console.warn(`[Prediction→Hotspots] Corridor "${corridorName}" not found in hotspot results`);
            }
        }, 800); // Give analyzeHotspots() time to render
    }, 150);
}
```

### 3.2 Fix `jumpPredCorridorToCMF()` (Currently Does Nothing Useful)

The current implementation (line 137713) just calls `navigateTo('cmf')` with zero context. Replace entirely:

```javascript
function jumpPredCorridorToCMF(corridorName) {
    // Set cross-tab selection state so the CMF tab picks up the corridor context
    if (typeof selectionState !== 'undefined') {
        selectionState.fromTab = 'prediction';
        selectionState.location = corridorName;
    }

    navigateTo('cmf');

    // Populate the CMF location search field and trigger a search
    setTimeout(() => {
        const searchInput = document.getElementById('cmfLocationSearch');
        if (searchInput) {
            searchInput.value = corridorName;
            // Trigger input event to activate the CMF search logic
            searchInput.dispatchEvent(new Event('input', { bubbles: true }));
        }

        // Also update the AI context indicator if the function exists
        if (typeof updateAIContextIndicator === 'function') {
            updateAIContextIndicator();
        }
    }, 250);
}
```

### 3.3 Add "View Forecast" Action Button to Corridors Table

In the corridor table action buttons (line 138673), add a third button that navigates to the corridor's detailed forecast within the Corridors sub-tab:

```javascript
// Inside the corridor table row rendering in renderPredCorridorTable()
// After the existing CMF button, add:
<button class="pred-corridor-btn" onclick="predSelectAndShowCorridor('${esc(r.name)}')" title="View detailed forecast">📊 Forecast</button>
```

Implement the handler:

```javascript
function predSelectAndShowCorridor(corridorName) {
    // Select this corridor in the checkboxes
    if (!predictionState.selectedCorridors.includes(corridorName)) {
        if (predictionState.selectedCorridors.length >= predictionState.maxCorridorSelections) {
            predictionState.selectedCorridors = [corridorName]; // Replace all if at max
        } else {
            predictionState.selectedCorridors.push(corridorName);
        }
    }
    // Update checkboxes to match
    document.querySelectorAll('#predCorridorBody .pred-corridor-checkbox').forEach(cb => {
        cb.checked = predictionState.selectedCorridors.includes(cb.dataset.corridor);
    });
    updatePredCorridorSelectionCount();
    updatePredCorridorDetailPanel();
    // Scroll to the detail panel
    const panel = document.getElementById('predCorridorDetailPanel');
    if (panel) {
        panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}
```

---

## CSS Additions

Add these styles to the existing prediction CSS section in `app/index.html`:

```css
/* Decision Confidence Indicator */
.pred-confidence-indicator {
    display: flex;
    align-items: flex-start;
    gap: .75rem;
}
.pred-confidence-indicator .level-icon {
    font-size: 1.5rem;
    line-height: 1;
}
.pred-confidence-indicator .level-text {
    font-weight: 700;
    font-size: .9rem;
    margin-bottom: .25rem;
}
.pred-confidence-indicator .use-cases {
    font-size: .82rem;
    color: #475569;
    line-height: 1.5;
    margin-bottom: .5rem;
}
.pred-confidence-indicator .band-detail {
    font-size: .78rem;
    color: #64748b;
    line-height: 1.4;
}

/* Corridor Action Button — Forecast variant */
.pred-corridor-btn.forecast {
    background: #dbeafe;
    color: #1e40af;
    border: 1px solid #93c5fd;
}
.pred-corridor-btn.forecast:hover {
    background: #bfdbfe;
}
```

---

## Testing Checklist

- [ ] Verify Decision Confidence indicator shows correctly for all 3 forecast files (`all_roads`, `county_roads`, `no_interstate`)
- [ ] Test confidence indicator with 3-month horizon (should be tighter) vs 12-month (should be wider)
- [ ] Change confidence dropdown from 80% → 90% → 95% — indicator should update
- [ ] Export PDF: verify the HTML report opens in a new tab with all sections populated
- [ ] Export PDF: verify KPI cards, monthly table, corridor table, and factor table render correctly
- [ ] Export PDF: verify print dialog triggers and "Save as PDF" produces a clean document
- [ ] Cross-tab: Click "🔥 Hotspots" on a corridor → lands on Hotspots tab with corridor highlighted
- [ ] Cross-tab: Click "🔧 CMF" on a corridor → lands on CMF tab with corridor name in search field
- [ ] Cross-tab: Click "📊 Forecast" on a corridor → detail panel opens and scrolls into view
- [ ] Verify no duplicate function names introduced (search: `function renderPred`, `function jumpPred`, `function predSelect`)
- [ ] Console should show no errors when switching between sub-tabs after changes
- [ ] Test with no forecast data loaded — all "no data" states should display correctly

---

## Architecture Notes

- All new functions MUST use unique names prefixed with `pred` or `prediction` to avoid collisions
- Use `predictionState` for all state management — do not create new global objects
- Follow existing patterns: check `predictionState.loaded && predictionState.data` before rendering
- Use `esc()` function for all user-facing text from data to prevent XSS
- Respect the existing horizon and confidence level controls — new features must respond to changes
- Use PRED_COLORS constants for color consistency
- Use existing CSS class patterns (`.pred-*`, `.card`, `.btn-soft`, etc.)
- The `exportPredictionPDF()` function uses `esc()` for all dynamic strings in the HTML to prevent injection
- Cross-tab functions should use `setTimeout()` to account for tab rendering delays (follow existing patterns)
```

---

## Summary

The crash prediction module correctly uses R2 as primary cloud storage with local filesystem fallback, and the 6-matrix forecast structure is comprehensive. The three improvements in this prompt address the most impactful UX gaps: (1) translating confidence bands into plain-language decision guidance so engineers know when predictions are reliable enough for project justification, (2) replacing the bare-text export with a professionally formatted report suitable for HSIP applications and stakeholder presentations, and (3) making the cross-tab navigation actually work so engineers can seamlessly flow from "this corridor is getting worse" to "here are the countermeasures to fix it."
