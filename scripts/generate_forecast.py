#!/usr/bin/env python3
"""
Generate crash forecasts using Chronos-2 on Amazon SageMaker.

Reads crash data from data/crashes.csv, aggregates into monthly time series,
sends to the Chronos-2 SageMaker endpoint, and writes forecasts to
data/forecasts.json for the Crash Prediction tab in CRASH LENS.

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


def main():
    parser = argparse.ArgumentParser(description="Generate crash forecasts with Chronos-2")
    parser.add_argument("--data", default="data/CDOT/douglas_all_roads.csv", help="Path to crash CSV")
    parser.add_argument("--output", default="data/forecasts.json", help="Output JSON path")
    parser.add_argument("--horizon", type=int, default=DEFAULT_HORIZON, help="Forecast horizon (months)")
    parser.add_argument("--dry-run", action="store_true", help="Generate synthetic forecasts without SageMaker")
    args = parser.parse_args()

    # Resolve paths relative to project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(project_root, args.data) if not os.path.isabs(args.data) else args.data
    output_path = os.path.join(project_root, args.output) if not os.path.isabs(args.output) else args.output

    # Load data
    df = load_crash_data(csv_path)

    # Set up endpoint caller or synthetic generator
    if args.dry_run:
        print("\n*** DRY RUN MODE — generating synthetic forecasts ***\n")
        call_endpoint = lambda series, horizon: generate_synthetic_forecast(series, horizon)
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
        call_endpoint = lambda series, horizon: invoke_endpoint(session, series, horizon)

    # Build all 6 matrices
    horizon = args.horizon
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

    # Assemble final output
    output = {
        "generated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "model": "amazon/chronos-2" if not args.dry_run else "synthetic-demo",
        "horizon": horizon,
        "quantileLevels": QUANTILE_LEVELS,
        "epdoWeights": EPDO_WEIGHTS,
        "summary": summary,
        "matrices": matrices,
    }

    # Write output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nForecast written to {output_path}")
    print(f"  Matrices generated: {list(matrices.keys())}")
    print(f"  Horizon: {horizon} months")
    file_size = os.path.getsize(output_path)
    print(f"  File size: {file_size:,} bytes")
    print("\nDone!")


if __name__ == "__main__":
    main()
