#!/usr/bin/env python3
"""
Generate crash forecasts using Chronos-2 on Amazon SageMaker.

Reads crash data from data/CDOT/*.csv, aggregates into monthly time series,
sends to the Chronos-2 SageMaker endpoint, and writes forecasts to
data/CDOT/forecasts*.json for the Crash Prediction tab in CRASH LENS.

Each DOT's prediction data is stored alongside its source data (e.g., data/CDOT/).

Implements all 6 prediction matrices:
  M01: Total Crash Frequency (county-wide)
  M02: Severity-Level Multivariate (K/A/B/C/O)
  M03: Corridor Cross-Learning (top 10 routes)
  M04: Crash Type Distribution (rear-end, angle, etc.)
  M05: Contributing Factor Trends (speed, alcohol, ped, bike)
  M06: Intersection vs Segment

Usage:
    python scripts/generate_forecast.py
    python scripts/generate_forecast.py --horizon 12 --data data/crashes.csv
    python scripts/generate_forecast.py --dry-run  # Generate sample data without endpoint

Environment Variables:
    AWS_ACCESS_KEY_ID       - IAM user access key
    AWS_SECRET_ACCESS_KEY   - IAM user secret key
    AWS_REGION              - AWS region (default: us-east-1)
"""

import argparse
import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Install with: pip install pandas")
    sys.exit(1)

# ============================================================
# Configuration
# ============================================================

ENDPOINT_NAME = "crashlens-chronos2-endpoint"
QUANTILE_LEVELS = [0.1, 0.25, 0.5, 0.75, 0.9]
DEFAULT_HORIZON = 12  # months

# EPDO weights (must match index.html)
EPDO_WEIGHTS = {"K": 462, "A": 62, "B": 12, "C": 5, "O": 1}

# Top corridors by crash volume (from Douglas County data)
TOP_CORRIDORS = [
    "I-25", "C-470", "S PARKER RD", "HWY 85", "LINCOLN AVE",
    "FOUNDERS PKWY", "HWY 83", "E LINCOLN AVE", "HWY 86", "RIDGEGATE PKWY",
]

# Crash type mapping
CRASH_TYPE_MAP = {
    "1. Rear End": "rear_end",
    "2. Broadside": "angle",
    "2. Angle": "angle",
    "9. Fixed Object - Off Road": "fixed_object",
    "9. Fixed Object": "fixed_object",
    "4. Sideswipe - Same Direction": "sideswipe_same",
    "4. Sideswipe Same": "sideswipe_same",
    "10. Deer/Animal": "animal",
    "3. Head On": "head_on",
}

# Intersection type mapping
INTERSECTION_TYPE_MAP = {
    "1. Not at Intersection": "segment",
    "4. Four Approaches": "four_leg",
    "2. Two Approaches": "three_leg",
    "5. Roundabout": "roundabout",
}


def load_crash_data(csv_path):
    """Load and parse crash CSV data."""
    print(f"Loading crash data from {csv_path}...")
    df = pd.read_csv(csv_path, low_memory=False)
    print(f"  Loaded {len(df):,} crash records")

    # Parse dates
    df["date"] = pd.to_datetime(df["Crash Date"], format="mixed", errors="coerce")
    df = df.dropna(subset=["date"])

    # Ensure severity column
    if "Crash Severity" in df.columns:
        df["severity"] = df["Crash Severity"].str.strip()
    else:
        df["severity"] = "O"

    # Extract month period
    df["month"] = df["date"].dt.to_period("M")

    print(f"  Date range: {df['date'].min().strftime('%Y-%m')} to {df['date'].max().strftime('%Y-%m')}")
    print(f"  Months: {df['month'].nunique()}")
    return df


def build_monthly_series(df, group_col=None, value_col=None, filter_func=None):
    """Build monthly time series from crash data.

    Args:
        df: DataFrame with crash records
        group_col: Column to group by (creates multiple series)
        value_col: Column to count distinct values of (default: count rows)
        filter_func: Optional function to filter df before aggregation

    Returns:
        dict: {series_id: [(month_str, count), ...]}
    """
    if filter_func:
        df = filter_func(df)

    if group_col:
        groups = df.groupby([group_col, "month"]).size().reset_index(name="count")
        # Ensure all months present for each group
        all_months = sorted(df["month"].unique())
        result = {}
        for group_name in groups[group_col].unique():
            group_data = groups[groups[group_col] == group_name]
            month_counts = dict(zip(group_data["month"], group_data["count"]))
            series = [(str(m), month_counts.get(m, 0)) for m in all_months]
            result[str(group_name)] = series
        return result
    else:
        monthly = df.groupby("month").size().reset_index(name="count")
        all_months = sorted(df["month"].unique())
        month_counts = dict(zip(monthly["month"], monthly["count"]))
        series = [(str(m), month_counts.get(m, 0)) for m in all_months]
        return {"total": series}


def calc_epdo(severity_counts):
    """Calculate EPDO score from severity counts."""
    return sum(
        severity_counts.get(s, 0) * w for s, w in EPDO_WEIGHTS.items()
    )


def invoke_endpoint(session, series_dict, horizon):
    """Send time series to SageMaker endpoint and get forecasts.

    Args:
        session: boto3 Session
        series_dict: {series_id: [(month, count), ...]}
        horizon: prediction length in months

    Returns:
        dict: {series_id: {quantile: [values], months: [month_strs]}}
    """
    runtime = session.client("sagemaker-runtime")

    # Build payload
    series_ids = list(series_dict.keys())
    inputs = []
    for sid in series_ids:
        target = [point[1] for point in series_dict[sid]]
        inputs.append({"target": target})

    payload = {
        "inputs": inputs,
        "parameters": {
            "prediction_length": horizon,
            "quantile_levels": QUANTILE_LEVELS,
        },
    }

    print(f"  Sending {len(inputs)} series to endpoint (horizon={horizon})...")
    response = runtime.invoke_endpoint(
        EndpointName=ENDPOINT_NAME,
        ContentType="application/json",
        Body=json.dumps(payload),
    )

    result = json.loads(response["Body"].read().decode("utf-8"))
    predictions = result.get("predictions", {})

    # Parse response — generate future month labels
    last_month_str = series_dict[series_ids[0]][-1][0]  # e.g., "2025-08"
    last_date = pd.Period(last_month_str, freq="M")
    future_months = [str(last_date + i + 1) for i in range(horizon)]

    forecasts = {}
    for idx, sid in enumerate(series_ids):
        forecast = {"months": future_months}
        for q_key, q_values in predictions.items():
            if q_key == "mean":
                forecast["mean"] = q_values[idx] if idx < len(q_values) else []
            else:
                forecast[f"p{int(float(q_key)*100)}"] = (
                    q_values[idx] if idx < len(q_values) else []
                )
        forecasts[sid] = forecast

    return forecasts


def generate_synthetic_forecast(series_dict, horizon):
    """Generate plausible synthetic forecasts for dry-run / demo mode.

    Uses seasonal decomposition and noise to create realistic-looking
    forecasts without calling the SageMaker endpoint.
    """
    import random
    random.seed(42)

    forecasts = {}
    for sid, series in series_dict.items():
        values = [point[1] for point in series]
        if not values:
            continue

        # Calculate base statistics
        mean_val = sum(values) / len(values) if values else 0
        recent_mean = sum(values[-6:]) / min(6, len(values))
        std_val = (sum((v - mean_val) ** 2 for v in values) / len(values)) ** 0.5

        # Calculate monthly seasonality (if enough data)
        monthly_factors = {}
        if len(values) >= 12:
            for i, (month_str, count) in enumerate(series):
                m = int(month_str.split("-")[1])
                if m not in monthly_factors:
                    monthly_factors[m] = []
                monthly_factors[m].append(count)
            monthly_factors = {
                m: sum(v) / len(v) / max(mean_val, 1)
                for m, v in monthly_factors.items()
            }

        # Detect trend from last 12 months
        if len(values) >= 12:
            first_half = sum(values[-12:-6]) / 6
            second_half = sum(values[-6:]) / 6
            trend_per_month = (second_half - first_half) / 6
        else:
            trend_per_month = 0

        # Generate future months
        last_month_str = series[-1][0]
        last_date = pd.Period(last_month_str, freq="M")
        future_months = [str(last_date + i + 1) for i in range(horizon)]

        # Generate quantile forecasts
        p50 = []
        for i, fm in enumerate(future_months):
            month_num = int(fm.split("-")[1])
            seasonal = monthly_factors.get(month_num, 1.0)
            base = recent_mean * seasonal + trend_per_month * (i + 1)
            base = max(0, base)
            p50.append(round(base, 1))

        # Generate other quantiles by spreading around p50
        spread = max(std_val * 0.5, mean_val * 0.1)
        forecast = {
            "months": future_months,
            "p10": [round(max(0, v - spread * 1.28 + random.gauss(0, spread * 0.1)), 1) for v in p50],
            "p25": [round(max(0, v - spread * 0.67 + random.gauss(0, spread * 0.05)), 1) for v in p50],
            "p50": p50,
            "p75": [round(v + spread * 0.67 + random.gauss(0, spread * 0.05), 1) for v in p50],
            "p90": [round(v + spread * 1.28 + random.gauss(0, spread * 0.1), 1) for v in p50],
            "mean": [round(v + random.gauss(0, spread * 0.03), 1) for v in p50],
        }
        forecasts[sid] = forecast

    return forecasts


def build_matrix_01(df, horizon, call_endpoint):
    """Matrix 01: Total Crash Frequency Forecast (county-wide monthly)."""
    print("\n[M01] Total Crash Frequency Forecast...")
    series = build_monthly_series(df)
    forecasts = call_endpoint(series, horizon)

    # Add history
    history = [{"month": m, "value": v} for m, v in series["total"]]

    return {
        "id": "m01",
        "title": "Total Crash Frequency",
        "subtitle": "County-Wide Monthly Forecast",
        "history": history,
        "forecast": forecasts.get("total", {}),
    }


def build_matrix_02(df, horizon, call_endpoint):
    """Matrix 02: Severity-Level Multivariate Forecast (K/A/B/C/O)."""
    print("\n[M02] Severity-Level Multivariate Forecast...")
    series = build_monthly_series(df, group_col="severity")

    # Ensure all severity levels present
    for sev in ["K", "A", "B", "C", "O"]:
        if sev not in series:
            # Build empty series
            all_months = sorted(df["month"].unique())
            series[sev] = [(str(m), 0) for m in all_months]

    forecasts = call_endpoint(series, horizon)

    # Build history per severity
    history = {}
    for sev in ["K", "A", "B", "C", "O"]:
        if sev in series:
            history[sev] = [{"month": m, "value": v} for m, v in series[sev]]

    # Calculate historical EPDO per month
    all_months = sorted(df["month"].unique())
    epdo_history = []
    for month in all_months:
        month_sev = {}
        for sev in ["K", "A", "B", "C", "O"]:
            month_data = dict(series.get(sev, []))
            month_sev[sev] = month_data.get(month, 0)
        epdo_history.append({
            "month": str(month),
            "value": calc_epdo(month_sev),
        })

    return {
        "id": "m02",
        "title": "Severity-Level Forecast",
        "subtitle": "Joint K-A-B-C-O Prediction",
        "history": history,
        "forecast": forecasts,
        "epdoHistory": epdo_history,
    }


def build_matrix_03(df, horizon, call_endpoint):
    """Matrix 03: Corridor-Level Cross-Learning Forecast."""
    print("\n[M03] Corridor Cross-Learning Forecast...")

    # Normalize route names for matching
    df_corr = df.copy()
    if "RTE Name" in df_corr.columns:
        route_col = "RTE Name"
    elif "RTE_NAME" in df_corr.columns:
        route_col = "RTE_NAME"
    else:
        print("  WARNING: No route column found. Skipping corridor forecast.")
        return None

    # Match top corridors (case-insensitive partial match)
    corridor_map = {}
    for _, row in df_corr.iterrows():
        rte = str(row.get(route_col, "")).strip().upper()
        for corr in TOP_CORRIDORS:
            if corr.upper() in rte or rte in corr.upper():
                corridor_map[row.name] = corr
                break

    df_corr["corridor"] = df_corr.index.map(corridor_map)
    df_corr = df_corr.dropna(subset=["corridor"])

    if df_corr.empty:
        print("  WARNING: No corridor matches found. Skipping.")
        return None

    series = build_monthly_series(df_corr, group_col="corridor")
    forecasts = call_endpoint(series, horizon)

    # Build history + stats per corridor
    corridors = {}
    for corr_name, corr_series in series.items():
        total = sum(v for _, v in corr_series)
        monthly_avg = total / max(len(corr_series), 1)
        # Get severity breakdown
        corr_df = df_corr[df_corr["corridor"] == corr_name]
        sev_counts = corr_df["severity"].value_counts().to_dict()
        epdo = calc_epdo(sev_counts)

        corridors[corr_name] = {
            "history": [{"month": m, "value": v} for m, v in corr_series],
            "forecast": forecasts.get(corr_name, {}),
            "stats": {
                "total": int(total),
                "monthlyAvg": round(monthly_avg, 1),
                "epdo": int(epdo),
                "severity": {k: int(v) for k, v in sev_counts.items()},
            },
        }

    return {
        "id": "m03",
        "title": "Corridor Forecast",
        "subtitle": "Cross-Learning Top Routes",
        "corridors": corridors,
    }


def build_matrix_04(df, horizon, call_endpoint):
    """Matrix 04: Crash Type Distribution Forecast."""
    print("\n[M04] Crash Type Distribution Forecast...")

    if "Collision Type" not in df.columns:
        print("  WARNING: No Collision Type column. Skipping.")
        return None

    df_typed = df.copy()
    df_typed["crash_type"] = df_typed["Collision Type"].map(CRASH_TYPE_MAP)
    df_typed = df_typed.dropna(subset=["crash_type"])

    series = build_monthly_series(df_typed, group_col="crash_type")
    forecasts = call_endpoint(series, horizon)

    # Build stats per type
    types = {}
    for type_name, type_series in series.items():
        total = sum(v for _, v in type_series)
        types[type_name] = {
            "history": [{"month": m, "value": v} for m, v in type_series],
            "forecast": forecasts.get(type_name, {}),
            "total": int(total),
        }

    return {
        "id": "m04",
        "title": "Crash Type Forecast",
        "subtitle": "By Collision Type",
        "types": types,
    }


def build_matrix_05(df, horizon, call_endpoint):
    """Matrix 05: Contributing Factor Trends Forecast."""
    print("\n[M05] Contributing Factor Trends Forecast...")

    factors = {
        "speed": "Speed?",
        "alcohol": "Alcohol?",
        "pedestrian": "Pedestrian?",
        "bicycle": "Bike?",
        "night": "Night?",
    }

    all_series = {}
    factor_stats = {}
    for factor_name, col_name in factors.items():
        if col_name not in df.columns:
            continue
        factor_df = df[df[col_name].str.strip().str.upper().isin(["YES", "Y", "1", "TRUE"])]
        series = build_monthly_series(factor_df)
        all_series[factor_name] = series["total"]
        factor_stats[factor_name] = {
            "total": int(len(factor_df)),
            "history": [{"month": m, "value": v} for m, v in series["total"]],
        }

    if not all_series:
        print("  WARNING: No contributing factor columns found. Skipping.")
        return None

    forecasts = call_endpoint(all_series, horizon)

    for factor_name in factor_stats:
        factor_stats[factor_name]["forecast"] = forecasts.get(factor_name, {})

    return {
        "id": "m05",
        "title": "Contributing Factor Trends",
        "subtitle": "Speed / Alcohol / Ped / Bike / Night",
        "factors": factor_stats,
    }


def build_matrix_06(df, horizon, call_endpoint):
    """Matrix 06: Intersection vs Segment Forecast."""
    print("\n[M06] Intersection vs Segment Forecast...")

    if "Intersection Type" not in df.columns:
        print("  WARNING: No Intersection Type column. Skipping.")
        return None

    df_loc = df.copy()
    df_loc["loc_type"] = df_loc["Intersection Type"].map(INTERSECTION_TYPE_MAP)
    df_loc = df_loc.dropna(subset=["loc_type"])

    series = build_monthly_series(df_loc, group_col="loc_type")
    forecasts = call_endpoint(series, horizon)

    loc_types = {}
    for loc_name, loc_series in series.items():
        total = sum(v for _, v in loc_series)
        loc_types[loc_name] = {
            "history": [{"month": m, "value": v} for m, v in loc_series],
            "forecast": forecasts.get(loc_name, {}),
            "total": int(total),
        }

    return {
        "id": "m06",
        "title": "Intersection vs Segment",
        "subtitle": "By Location Type",
        "locationTypes": loc_types,
    }


def build_summary_stats(df, matrices):
    """Build summary statistics for the dashboard KPI cards."""
    total = len(df)
    years = sorted(df["Crash Year"].unique()) if "Crash Year" in df.columns else []
    sev = df["severity"].value_counts().to_dict()

    # Recent trend (last 6 months vs previous 6 months)
    months = sorted(df["month"].unique())
    if len(months) >= 12:
        recent_6 = months[-6:]
        prev_6 = months[-12:-6]
        recent_count = len(df[df["month"].isin(recent_6)])
        prev_count = len(df[df["month"].isin(prev_6)])
        trend_pct = ((recent_count - prev_count) / max(prev_count, 1)) * 100
    else:
        recent_count = total
        prev_count = total
        trend_pct = 0

    return {
        "totalCrashes": int(total),
        "years": [int(y) for y in years],
        "dateRange": {
            "start": str(months[0]) if months else "",
            "end": str(months[-1]) if months else "",
        },
        "severity": {k: int(v) for k, v in sev.items()},
        "epdo": int(calc_epdo(sev)),
        "monthlyAvg": round(total / max(len(months), 1), 1),
        "recentTrend": {
            "recent6mo": int(recent_count),
            "prev6mo": int(prev_count),
            "changePct": round(trend_pct, 1),
        },
    }


def build_derived_metrics(matrices, summary, horizon):
    """Build derived analytics from the 6 prediction matrices.

    These metrics provide deeper insights beyond raw forecasts:
    - Uncertainty/confidence analysis
    - EPDO-weighted risk forecasts
    - Severity shift detection
    - Corridor rank movement predictions
    - Crash type momentum (which types are growing fastest)
    - Seasonal risk calendar
    - Composite risk scoring
    """
    derived = {}

    # ---- 1. Prediction Confidence Width (from M01) ----
    m01 = matrices.get("m01", {})
    fc01 = m01.get("forecast", {})
    if fc01.get("p90") and fc01.get("p10"):
        widths = [round(p90 - p10, 1) for p90, p10 in zip(fc01["p90"], fc01["p10"])]
        avg_width = round(sum(widths) / max(len(widths), 1), 1)
        p50_avg = sum(fc01.get("p50", [0])) / max(len(fc01.get("p50", [1])), 1)
        # Coefficient of variation of the CI — lower = more confident
        cv = round(avg_width / max(p50_avg, 1) * 100, 1)
        derived["confidenceWidth"] = {
            "monthlyWidths": widths,
            "months": fc01.get("months", []),
            "avgWidth": avg_width,
            "coefficientOfVariation": cv,
            "interpretation": "low" if cv < 30 else "moderate" if cv < 60 else "high",
        }

    # ---- 2. EPDO Forecast (from M02 severity forecasts) ----
    m02 = matrices.get("m02", {})
    fc02 = m02.get("forecast", {})
    if fc02.get("K") and fc02["K"].get("p50"):
        months_list = fc02["K"].get("months", [])
        epdo_forecast = []
        epdo_p10 = []
        epdo_p90 = []
        for i in range(len(months_list)):
            epdo_val = 0
            ep10 = 0
            ep90 = 0
            for sev, weight in EPDO_WEIGHTS.items():
                sev_fc = fc02.get(sev, {})
                p50_vals = sev_fc.get("p50", [])
                p10_vals = sev_fc.get("p10", [])
                p90_vals = sev_fc.get("p90", [])
                epdo_val += (p50_vals[i] if i < len(p50_vals) else 0) * weight
                ep10 += (p10_vals[i] if i < len(p10_vals) else 0) * weight
                ep90 += (p90_vals[i] if i < len(p90_vals) else 0) * weight
            epdo_forecast.append(round(epdo_val))
            epdo_p10.append(round(ep10))
            epdo_p90.append(round(ep90))

        # Compare to historical EPDO
        hist_epdo = m02.get("epdoHistory", [])
        hist_6mo = sum(h["value"] for h in hist_epdo[-6:]) if hist_epdo else 0
        pred_6mo = sum(epdo_forecast[:6])
        epdo_change = round(((pred_6mo - hist_6mo) / max(hist_6mo, 1)) * 100, 1) if hist_6mo else 0

        derived["epdoForecast"] = {
            "months": months_list,
            "p50": epdo_forecast,
            "p10": epdo_p10,
            "p90": epdo_p90,
            "predicted6moTotal": round(pred_6mo),
            "historical6moTotal": round(hist_6mo),
            "changePct": epdo_change,
        }

    # ---- 3. Predicted KA Rate (fatal + serious injury forecast) ----
    if fc02.get("K") and fc02.get("A"):
        months_list = fc02["K"].get("months", [])
        ka_forecast = []
        total_forecast = fc01.get("p50", [])
        for i in range(len(months_list)):
            k_val = fc02["K"]["p50"][i] if i < len(fc02["K"].get("p50", [])) else 0
            a_val = fc02["A"]["p50"][i] if i < len(fc02["A"].get("p50", [])) else 0
            ka_forecast.append(round(k_val + a_val, 1))

        # KA rate as percentage of total
        ka_rates = []
        for i, ka in enumerate(ka_forecast):
            total = total_forecast[i] if i < len(total_forecast) else 1
            ka_rates.append(round(ka / max(total, 1) * 100, 1))

        # Historical KA rate for comparison
        hist_k = m02.get("history", {}).get("K", [])
        hist_a = m02.get("history", {}).get("A", [])
        hist_ka_6mo = (sum(h["value"] for h in hist_k[-6:]) +
                       sum(h["value"] for h in hist_a[-6:])) if hist_k else 0
        pred_ka_6mo = sum(ka_forecast[:6])

        derived["kaForecast"] = {
            "months": months_list,
            "predicted": ka_forecast,
            "kaRatePct": ka_rates,
            "predicted6mo": round(pred_ka_6mo, 1),
            "historical6mo": round(hist_ka_6mo, 1),
            "trend": "worsening" if pred_ka_6mo > hist_ka_6mo else "improving",
        }

    # ---- 4. Severity Shift Index (is severity mix changing?) ----
    if fc02.get("K") and fc02.get("O"):
        # Compare predicted severity distribution vs historical
        hist_sev = summary.get("severity", {})
        hist_total = sum(hist_sev.values())
        hist_ka_share = round((hist_sev.get("K", 0) + hist_sev.get("A", 0)) / max(hist_total, 1) * 100, 2)

        pred_sev = {}
        for sev in ["K", "A", "B", "C", "O"]:
            sev_fc = fc02.get(sev, {})
            p50 = sev_fc.get("p50", [])
            pred_sev[sev] = round(sum(p50[:6]))
        pred_total = sum(pred_sev.values())
        pred_ka_share = round((pred_sev.get("K", 0) + pred_sev.get("A", 0)) / max(pred_total, 1) * 100, 2)

        shift = round(pred_ka_share - hist_ka_share, 2)
        derived["severityShift"] = {
            "historicalKAShare": hist_ka_share,
            "predictedKAShare": pred_ka_share,
            "shiftPct": shift,
            "interpretation": "worsening" if shift > 0.5 else "stable" if shift > -0.5 else "improving",
            "predictedDistribution": pred_sev,
        }

    # ---- 5. Corridor Risk Ranking Movement (from M03) ----
    m03 = matrices.get("m03", {})
    corridors = m03.get("corridors", {})
    if corridors:
        corridor_rankings = []
        for name, cdata in corridors.items():
            stats = cdata.get("stats", {})
            fc = cdata.get("forecast", {})
            hist = cdata.get("history", [])

            # Historical monthly average (last 6 months)
            hist_6mo_avg = sum(h["value"] for h in hist[-6:]) / 6 if len(hist) >= 6 else 0
            # Predicted monthly average (next 6 months)
            p50 = fc.get("p50", [])
            pred_6mo_avg = sum(p50[:6]) / min(6, len(p50)) if p50 else 0

            # Trend direction
            change_pct = round(((pred_6mo_avg - hist_6mo_avg) / max(hist_6mo_avg, 1)) * 100, 1)

            # Confidence width (uncertainty) for this corridor
            p90 = fc.get("p90", [])
            p10 = fc.get("p10", [])
            avg_ci = round(sum(a - b for a, b in zip(p90[:6], p10[:6])) / 6, 1) if p90 and p10 else 0

            corridor_rankings.append({
                "name": name,
                "historical6moAvg": round(hist_6mo_avg, 1),
                "predicted6moAvg": round(pred_6mo_avg, 1),
                "changePct": change_pct,
                "epdo": stats.get("epdo", 0),
                "confidenceWidth": avg_ci,
                "direction": "rising" if change_pct > 5 else "falling" if change_pct < -5 else "stable",
            })

        # Sort by predicted average (highest risk first)
        corridor_rankings.sort(key=lambda x: x["predicted6moAvg"], reverse=True)
        # Add rank and rank change
        hist_sorted = sorted(corridor_rankings, key=lambda x: x["historical6moAvg"], reverse=True)
        hist_rank_map = {c["name"]: i + 1 for i, c in enumerate(hist_sorted)}
        for i, c in enumerate(corridor_rankings):
            c["predictedRank"] = i + 1
            c["historicalRank"] = hist_rank_map.get(c["name"], 0)
            c["rankChange"] = c["historicalRank"] - c["predictedRank"]  # positive = moved up in risk

        # Identify emerging risk corridors (biggest upward movers)
        emerging = [c for c in corridor_rankings if c["changePct"] > 5]
        emerging.sort(key=lambda x: x["changePct"], reverse=True)

        derived["corridorRankMovement"] = {
            "rankings": corridor_rankings,
            "emergingRisk": [c["name"] for c in emerging[:3]],
            "improvingMost": sorted(
                [c for c in corridor_rankings if c["changePct"] < -5],
                key=lambda x: x["changePct"]
            )[:3] if corridor_rankings else [],
        }

    # ---- 6. Crash Type Momentum (from M04) ----
    m04 = matrices.get("m04", {})
    crash_types = m04.get("types", {})
    if crash_types:
        type_momentum = []
        for type_name, tdata in crash_types.items():
            hist = tdata.get("history", [])
            fc = tdata.get("forecast", {})
            p50 = fc.get("p50", [])

            hist_6mo = sum(h["value"] for h in hist[-6:]) if len(hist) >= 6 else 0
            pred_6mo = sum(p50[:6]) if p50 else 0
            change_pct = round(((pred_6mo - hist_6mo) / max(hist_6mo, 1)) * 100, 1) if hist_6mo else 0

            # Calculate trend slope (linear regression of predicted values)
            if len(p50) >= 3:
                n = len(p50)
                x_mean = (n - 1) / 2
                y_mean = sum(p50) / n
                slope = sum((i - x_mean) * (p50[i] - y_mean) for i in range(n)) / max(
                    sum((i - x_mean) ** 2 for i in range(n)), 1
                )
            else:
                slope = 0

            type_momentum.append({
                "type": type_name,
                "historical6mo": round(hist_6mo),
                "predicted6mo": round(pred_6mo),
                "changePct": change_pct,
                "trendSlope": round(slope, 2),
                "total": tdata.get("total", 0),
                "momentum": "accelerating" if change_pct > 10 else "decelerating" if change_pct < -10 else "steady",
            })

        type_momentum.sort(key=lambda x: x["changePct"], reverse=True)
        derived["crashTypeMomentum"] = {
            "types": type_momentum,
            "fastestGrowing": type_momentum[0]["type"] if type_momentum else None,
            "fastestDeclining": type_momentum[-1]["type"] if type_momentum else None,
        }

    # ---- 7. Contributing Factor Trend Slopes (from M05) ----
    m05 = matrices.get("m05", {})
    factors = m05.get("factors", {})
    if factors:
        factor_trends = []
        for factor_name, fdata in factors.items():
            hist = fdata.get("history", [])
            fc = fdata.get("forecast", {})
            p50 = fc.get("p50", [])

            hist_6mo = sum(h["value"] for h in hist[-6:]) if len(hist) >= 6 else 0
            pred_6mo = sum(p50[:6]) if p50 else 0
            change_pct = round(((pred_6mo - hist_6mo) / max(hist_6mo, 1)) * 100, 1) if hist_6mo else 0

            # As percentage of total predicted crashes
            total_pred = sum(fc01.get("p50", [0])[:6]) if fc01.get("p50") else 1
            involvement_rate = round(pred_6mo / max(total_pred, 1) * 100, 1)

            factor_trends.append({
                "factor": factor_name,
                "historical6mo": round(hist_6mo),
                "predicted6mo": round(pred_6mo),
                "changePct": change_pct,
                "involvementRatePct": involvement_rate,
                "total": fdata.get("total", 0),
            })

        factor_trends.sort(key=lambda x: x["changePct"], reverse=True)
        derived["factorTrends"] = {
            "factors": factor_trends,
            "steepestRising": factor_trends[0]["factor"] if factor_trends and factor_trends[0]["changePct"] > 0 else None,
        }

    # ---- 8. Seasonal Risk Calendar (from M01 + M02) ----
    if fc01.get("p50") and fc01.get("months"):
        monthly_risk = []
        for i, month_str in enumerate(fc01["months"]):
            month_num = int(month_str.split("-")[1])
            total_pred = fc01["p50"][i] if i < len(fc01["p50"]) else 0

            # Get KA prediction for this month
            ka_pred = 0
            for sev in ["K", "A"]:
                sev_fc = fc02.get(sev, {})
                p50 = sev_fc.get("p50", [])
                ka_pred += p50[i] if i < len(p50) else 0

            # EPDO for this month
            epdo_val = 0
            for sev, weight in EPDO_WEIGHTS.items():
                sev_fc = fc02.get(sev, {})
                p50 = sev_fc.get("p50", [])
                epdo_val += (p50[i] if i < len(p50) else 0) * weight

            monthly_risk.append({
                "month": month_str,
                "monthNum": month_num,
                "totalPredicted": round(total_pred, 1),
                "kaPredicted": round(ka_pred, 1),
                "epdoPredicted": round(epdo_val),
            })

        # Rank months by risk (EPDO)
        sorted_by_risk = sorted(monthly_risk, key=lambda x: x["epdoPredicted"], reverse=True)
        for rank, m in enumerate(sorted_by_risk):
            m["riskRank"] = rank + 1

        derived["seasonalRiskCalendar"] = {
            "months": monthly_risk,
            "highestRiskMonth": sorted_by_risk[0]["month"] if sorted_by_risk else None,
            "lowestRiskMonth": sorted_by_risk[-1]["month"] if sorted_by_risk else None,
        }

    # ---- 9. Composite Risk Score (blended index) ----
    # Combines total crash trend, severity trend, and EPDO trend into one score
    total_trend = summary.get("recentTrend", {}).get("changePct", 0)
    severity_shift = derived.get("severityShift", {}).get("shiftPct", 0)
    epdo_change = derived.get("epdoForecast", {}).get("changePct", 0)

    # Weighted composite: EPDO matters most (50%), total trend (30%), severity shift (20%)
    composite = round(epdo_change * 0.5 + total_trend * 0.3 + severity_shift * 10 * 0.2, 1)
    if composite > 10:
        risk_level = "critical"
    elif composite > 5:
        risk_level = "elevated"
    elif composite > -5:
        risk_level = "moderate"
    else:
        risk_level = "low"

    derived["compositeRiskScore"] = {
        "score": composite,
        "level": risk_level,
        "components": {
            "totalTrend": round(total_trend, 1),
            "severityShift": round(severity_shift, 2),
            "epdoChange": round(epdo_change, 1),
        },
        "weights": {"epdoChange": 0.5, "totalTrend": 0.3, "severityShift": 0.2},
    }

    # ---- 10. Location Type Split Forecast (from M06) ----
    m06 = matrices.get("m06", {})
    loc_types = m06.get("locationTypes", {})
    if loc_types:
        intersection_pred = 0
        segment_pred = 0
        for lt_name, lt_data in loc_types.items():
            p50 = lt_data.get("forecast", {}).get("p50", [])
            pred_6mo = sum(p50[:6]) if p50 else 0
            if lt_name in ("four_leg", "three_leg", "roundabout"):
                intersection_pred += pred_6mo
            else:
                segment_pred += pred_6mo

        total_loc = intersection_pred + segment_pred
        derived["locationTypeSplit"] = {
            "intersectionPredicted6mo": round(intersection_pred),
            "segmentPredicted6mo": round(segment_pred),
            "intersectionSharePct": round(intersection_pred / max(total_loc, 1) * 100, 1),
            "segmentSharePct": round(segment_pred / max(total_loc, 1) * 100, 1),
        }

    return derived


def generate_single_forecast(csv_path, output_path, horizon, dry_run, road_type_label=None):
    """Generate forecast for a single crash data file."""
    df = load_crash_data(csv_path)

    # Set up endpoint caller or synthetic generator
    if dry_run:
        call_endpoint = lambda series, h: generate_synthetic_forecast(series, h)
    else:
        try:
            import boto3
        except ImportError:
            print("ERROR: boto3 required for live mode. Use --dry-run for testing.")
            sys.exit(1)

        session = boto3.Session(
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
        call_endpoint = lambda series, h: invoke_endpoint(session, series, h)

    # Build all 6 matrices
    matrices = {}

    m01 = build_matrix_01(df, horizon, call_endpoint)
    matrices["m01"] = m01

    m02 = build_matrix_02(df, horizon, call_endpoint)
    matrices["m02"] = m02

    m03 = build_matrix_03(df, horizon, call_endpoint)
    if m03:
        matrices["m03"] = m03

    m04 = build_matrix_04(df, horizon, call_endpoint)
    if m04:
        matrices["m04"] = m04

    m05 = build_matrix_05(df, horizon, call_endpoint)
    if m05:
        matrices["m05"] = m05

    m06 = build_matrix_06(df, horizon, call_endpoint)
    if m06:
        matrices["m06"] = m06

    # Build summary
    summary = build_summary_stats(df, matrices)

    # Build derived analytics from the matrices
    print("\n[Derived] Building derived prediction metrics...")
    derived = build_derived_metrics(matrices, summary, horizon)
    print(f"  Derived metrics: {list(derived.keys())}")

    # Assemble final output
    output = {
        "generated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "model": "amazon/chronos-2" if not dry_run else "synthetic-demo",
        "horizon": horizon,
        "quantileLevels": QUANTILE_LEVELS,
        "epdoWeights": EPDO_WEIGHTS,
        "roadType": road_type_label or "all_roads",
        "summary": summary,
        "matrices": matrices,
        "derivedMetrics": derived,
    }

    # Write output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nForecast written to {output_path}")
    print(f"  Road type: {road_type_label or 'all_roads'}")
    print(f"  Matrices generated: {list(matrices.keys())}")
    print(f"  Horizon: {horizon} months")
    file_size = os.path.getsize(output_path)
    print(f"  File size: {file_size:,} bytes")


# Road type configurations matching CRASH LENS UI filter options
ROAD_TYPE_CONFIGS = {
    "county_roads": {
        "label": "County/City Roads Only",
        "suffix": "county_roads",
        "output": "forecasts_county_roads.json",
    },
    "no_interstate": {
        "label": "All Roads (No Interstate)",
        "suffix": "no_interstate",
        "output": "forecasts_no_interstate.json",
    },
    "all_roads": {
        "label": "All Roads (Including Interstates)",
        "suffix": "all_roads",
        "output": "forecasts_all_roads.json",
    },
}


def main():
    parser = argparse.ArgumentParser(description="Generate crash forecasts with Chronos-2")
    parser.add_argument("--data", default="data/CDOT/douglas_all_roads.csv", help="Path to crash CSV")
    parser.add_argument("--output", default="data/CDOT/forecasts.json", help="Output JSON path")
    parser.add_argument("--horizon", type=int, default=DEFAULT_HORIZON, help="Forecast horizon (months)")
    parser.add_argument("--dry-run", action="store_true", help="Generate synthetic forecasts without SageMaker")
    parser.add_argument("--all-road-types", action="store_true",
                        help="Generate forecasts for all 3 road type datasets (county_roads, no_interstate, all_roads)")
    parser.add_argument("--jurisdiction", default="douglas",
                        help="Jurisdiction name prefix for data files (default: douglas)")
    parser.add_argument("--data-dir", default="data/CDOT",
                        help="Directory containing road-type CSV files (default: data/CDOT)")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if args.dry_run:
        print("\n*** DRY RUN MODE — generating synthetic forecasts ***\n")

    if args.all_road_types:
        # Generate forecasts for all 3 road type datasets
        data_dir = os.path.join(project_root, args.data_dir) if not os.path.isabs(args.data_dir) else args.data_dir
        output_dir = os.path.join(project_root, "data", "CDOT")
        generated = 0

        for road_type, config in ROAD_TYPE_CONFIGS.items():
            csv_file = os.path.join(data_dir, f"{args.jurisdiction}_{config['suffix']}.csv")
            out_file = os.path.join(output_dir, config["output"])

            if not os.path.exists(csv_file):
                print(f"\n[SKIP] {csv_file} not found — skipping {road_type}")
                continue

            print(f"\n{'='*60}")
            print(f"  Generating forecast: {config['label']}")
            print(f"  Data: {csv_file}")
            print(f"  Output: {out_file}")
            print(f"{'='*60}")

            generate_single_forecast(csv_file, out_file, args.horizon, args.dry_run, road_type)
            generated += 1

        print(f"\n{'='*60}")
        print(f"  Generated {generated} forecast files for {generated} road types")
        print(f"{'='*60}")
    else:
        # Single file mode (backward compatible)
        csv_path = os.path.join(project_root, args.data) if not os.path.isabs(args.data) else args.data
        output_path = os.path.join(project_root, args.output) if not os.path.isabs(args.output) else args.output

        # Detect road type from filename
        road_type = "all_roads"
        for rt, config in ROAD_TYPE_CONFIGS.items():
            if config["suffix"] in os.path.basename(csv_path):
                road_type = rt
                break

        generate_single_forecast(csv_path, output_path, args.horizon, args.dry_run, road_type)

    print("\nDone!")


if __name__ == "__main__":
    main()
