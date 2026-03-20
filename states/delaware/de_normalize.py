#!/usr/bin/env python3
"""
de_normalize.py — CrashLens Delaware (DelDOT) Normalization Script
State: Delaware | FIPS: 10 | DOT: DelDOT

Pipeline:
  Phase 1 — Column Mapping & Rename
  Phase 2 — State-Specific Post-Normalization Transforms
  Phase 3 — FIPS Resolution (hardcoded — DE has only 3 counties)
  Phase 4 — Composite Crash ID Generation
  Phase 5 — EPDO Scoring
  Phase 6 — Jurisdiction Ranking (24 columns: 4 scopes × 6 metrics)
  Phase 7 — Validation & Reporting

Output: {input_stem}_normalized_ranked.csv  (69 + 3 + 24 = 96 columns)
        {input_stem}_validation_report.json

Usage:
    python de_normalize.py --input all_roads.csv
    python de_normalize.py --input all_roads.csv --output de_normalized.csv
    python de_normalize.py --input all_roads.csv --epdo vdot2024
    python de_normalize.py --input all_roads.csv --skip-if-normalized
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG & CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

STATE_FIPS     = "10"
STATE_ABBR     = "DE"
STATE_NAME     = "Delaware"
STATE_DOT      = "DelDOT"
GOLDEN_COLUMNS = [
    "OBJECTID", "Document Nbr", "Crash Year", "Crash Date", "Crash Military Time",
    "Crash Severity", "K_People", "A_People", "B_People", "C_People",
    "Persons Injured", "Pedestrians Killed", "Pedestrians Injured", "Vehicle Count",
    "Collision Type", "Weather Condition", "Light Condition", "Roadway Surface Condition",
    "Relation To Roadway", "Roadway Alignment", "Roadway Surface Type", "Roadway Defect",
    "Roadway Description", "Intersection Type", "Traffic Control Type", "Traffic Control Status",
    "Work Zone Related", "Work Zone Location", "Work Zone Type", "School Zone",
    "First Harmful Event", "First Harmful Event Loc",
    "Alcohol?", "Animal Related?", "Unrestrained?", "Bike?", "Distracted?", "Drowsy?",
    "Drug Related?", "Guardrail Related?", "Hitrun?", "Lgtruck?", "Motorcycle?", "Pedestrian?",
    "Speed?", "Max Speed Diff", "RoadDeparture Type", "Intersection Analysis",
    "Senior?", "Young?", "Mainline?", "Night?",
    "VDOT District", "Juris Code", "Physical Juris Name", "Functional Class",
    "Facility Type", "Area Type", "SYSTEM", "VSP", "Ownership",
    "Planning District", "MPO Name", "RTE Name", "RNS MP", "Node", "Node Offset (ft)",
    "x", "y",
]

ENRICHMENT_COLUMNS = ["FIPS", "Place FIPS", "EPDO_Score"]

RANKING_SCOPES  = ["District", "Juris", "PlanningDistrict", "MPO"]
RANKING_METRICS = [
    "total_crash", "total_ped_crash", "total_bike_crash",
    "total_fatal", "total_fatal_serious_injury", "total_epdo",
]

EPDO_PRESETS = {
    "hsm2010":  {"K": 462,  "A": 62, "B": 12, "C": 5,  "O": 1},
    "vdot2024": {"K": 1032, "A": 53, "B": 16, "C": 10, "O": 1},
    "fhwa2022": {"K": 975,  "A": 48, "B": 13, "C": 8,  "O": 1},
    "fhwa2025": {"K": 883,  "A": 94, "B": 21, "C": 11, "O": 1},  # default
}
DEFAULT_EPDO_PRESET = "fhwa2025"

# ─────────────────────────────────────────────────────────────────────────────
#  DELAWARE GEOGRAPHY  (authoritative — only 3 counties)
# ─────────────────────────────────────────────────────────────────────────────

DE_COUNTIES = {
    "Kent":        {"fips": "001", "geoid": "10001", "district": "Central District", "mpo": "Dover/Kent County MPO"},
    "New Castle":  {"fips": "003", "geoid": "10003", "district": "North District",   "mpo": "WILMAPCO"},
    "Sussex":      {"fips": "005", "geoid": "10005", "district": "South District",   "mpo": "Salisbury-Wicomico MPO"},
}

# County code (single letter) → county name
DE_COUNTY_CODE_MAP = {"K": "Kent", "N": "New Castle", "S": "Sussex"}

# ─────────────────────────────────────────────────────────────────────────────
#  VALUE MAPPING TABLES  (Delaware → CrashLens Standard)
# ─────────────────────────────────────────────────────────────────────────────

MAP_SEVERITY = {
    "fatality crash":           "K",
    "fatal crash":              "K",
    "personal injury crash":    "A",
    "injury crash":             "A",
    "personal injury":          "A",
    "property damage only":     "O",
    "property damage":          "O",
    "pdo":                      "O",
    "non-reportable":           "O",
    "non reportable":           "O",
}

MAP_COLLISION_TYPE = {
    "front to rear":                          "1. Rear End",
    "angle":                                  "2. Angle",
    "front to front":                         "3. Head On",
    "sideswipe, same direction":              "4. Sideswipe - Same Direction",
    "sideswipe, opposite direction":          "5. Sideswipe - Opposite Direction",
    "not a collision between two vehicles":   "8. Non-Collision",
    "rear to rear":                           "16. Other",
    "rear to side":                           "16. Other",
    "other":                                  "16. Other",
    "unknown":                                "Not Provided",
}

MAP_WEATHER = {
    "clear":                                    "1. No Adverse Condition (Clear/Cloudy)",
    "cloudy":                                   "1. No Adverse Condition (Clear/Cloudy)",
    "fog, smog, smoke":                         "3. Fog",
    "rain":                                     "5. Rain",
    "snow":                                     "6. Snow",
    "sleet, hail (freezing rain or drizzle)":   "7. Sleet/Hail",
    "blowing sand, soil, dirt":                 "10. Blowing Sand, Soil, Dirt, or Snow",
    "blowing snow":                             "10. Blowing Sand, Soil, Dirt, or Snow",
    "severe crosswinds":                        "11. Severe Crosswinds",
    "other":                                    "9. Other",
    "unknown":                                  "Not Applicable",
}

MAP_LIGHT = {
    "dawn":                    "1. Dawn",
    "daylight":                "2. Daylight",
    "dusk":                    "3. Dusk",
    "dark-lighted":            "4. Darkness - Road Lighted",
    "dark-not lighted":        "5. Darkness - Road Not Lighted",
    "dark-unknown lighting":   "6. Darkness - Unknown Road Lighting",
    "other":                   "7. Unknown",
    "unknown":                 "7. Unknown",
}

MAP_ROAD_SURFACE = {
    "dry":                      "1. Dry",
    "wet":                      "2. Wet",
    "snow":                     "3. Snowy",
    "ice/frost":                "4. Icy",
    "oil":                      "6. Oil/Other Fluids",
    "mud, dirt, gravel":        "11. Sand, Dirt, Gravel",
    "sand":                     "11. Sand, Dirt, Gravel",
    "slush":                    "10. Slush",
    "water (standing, moving)": "9. Water (Standing, Moving)",
    "other":                    "7. Other",
    "unknown":                  "Not Applicable",
}

MAP_WORK_ZONE_LOCATION = {
    "advance warning area":                  "1. Advance Warning Area",
    "before the first work zone warning sign": "1. Advance Warning Area",
    "transition area":                       "2. Transition Area",
    "activity area":                         "3. Activity Area",
    "termination area":                      "4. Termination Area",
}

MAP_WORK_ZONE_TYPE = {
    "lane closure":               "1. Lane Closure",
    "lane shift/crossover":       "2. Lane Shift/Crossover",
    "work on shoulder or median": "3. Work on Shoulder or Median",
    "intermittent or moving work":"4. Intermittent or Moving Work",
    "other":                      "5. Other",
}

# Delaware uses school bus, not school zone — best-effort mapping
MAP_SCHOOL_BUS_TO_ZONE = {
    "no":                    "3. No",
    "yes, directly involved":"2. Yes - With School Activity",
    "yes, indirectly involved": "1. Yes",
}

# Y/N fields → Yes/No
YN_COLUMNS = [
    ("PEDESTRIAN INVOLVED",  "Pedestrian?"),
    ("ALCOHOL INVOLVED",     "Alcohol?"),
    ("DRUG INVOLVED",        "Drug Related?"),
    ("MOTORCYCLE INVOLVED",  "Motorcycle?"),
    ("BICYCLED INVOLVED",    "Bike?"),
]

NIGHT_KEYWORDS = {"dark-lighted", "dark-not lighted", "dark-unknown lighting", "dusk", "dawn"}

# ─────────────────────────────────────────────────────────────────────────────
#  DETECTION: Is this file already normalized?
# ─────────────────────────────────────────────────────────────────────────────

def is_already_normalized(columns: list[str]) -> bool:
    """Returns True if the DataFrame already has the CrashLens standard headers."""
    required = {"Document Nbr", "Crash Severity", "Physical Juris Name", "x", "y"}
    return required.issubset(set(columns))


# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 1 — COLUMN MAPPING & RENAME
# ─────────────────────────────────────────────────────────────────────────────

# Direct renames: source column → target column
COLUMN_RENAMES = {
    "CRASH DATETIME":                     "Crash Date",          # further parsed in Phase 2
    "YEAR":                               "Crash Year",
    "LATITUDE":                           "y",
    "LONGITUDE":                          "x",
    "COUNTY NAME":                        "Physical Juris Name",
    "COUNTY CODE":                        "Juris Code",
    "PEDESTRIAN INVOLVED":               "Pedestrian?",
    "BICYCLED INVOLVED":                 "Bike?",
    "ALCOHOL INVOLVED":                  "Alcohol?",
    "DRUG INVOLVED":                     "Drug Related?",
    "MOTORCYCLE INVOLVED":               "Motorcycle?",
    "SEATBELT USED":                     "Unrestrained?",
    "WEATHER 1 DESCRIPTION":             "Weather Condition",
    "LIGHTING CONDITION DESCRIPTION":    "Light Condition",
    "ROAD SURFACE DESCRIPTION":          "Roadway Surface Condition",
    "MANNER OF IMPACT DESCRIPTION":      "Collision Type",
    "SCHOOL BUS INVOLVED DESCRIPTION":   "School Zone",
    "WORK ZONE":                         "Work Zone Related",
    "WORK ZONE LOCATION DESCRIPTION":    "Work Zone Location",
    "WORK ZONE TYPE DESCRIPTION":        "Work Zone Type",
    "CRASH CLASSIFICATION DESCRIPTION":  "Crash Severity",
}

# Extra source columns not in the 69-column standard — kept as passthrough
EXTRA_COLUMNS = [
    "DAY OF WEEK CODE", "DAY OF WEEK DESCRIPTION",
    "CRASH CLASSIFICATION CODE",
    "COLLISION ON PRIVATE PROPERTY",
    "MANNER OF IMPACT CODE",
    "ROAD SURFACE CODE", "LIGHTING CONDITION CODE",
    "WEATHER 1 CODE", "WEATHER 2 CODE", "WEATHER 2 DESCRIPTION",
    "MOTORCYCLE HELMET USED", "BICYCLE HELMET USED",
    "SCHOOL BUS INVOLVED CODE",
    "WORK ZONE LOCATION CODE", "WORK ZONE TYPE CODE", "WORKERS PRESENT",
    "PRIMARY CONTRIBUTING CIRCUMSTANCE CODE",
    "PRIMARY CONTRIBUTING CIRCUMSTANCE DESCRIPTION",
]


def apply_column_renames(df: pd.DataFrame) -> pd.DataFrame:
    """Rename Delaware source columns to CrashLens standard names."""
    rename_map = {}
    src_cols = {c.strip().upper(): c for c in df.columns}

    for src, tgt in COLUMN_RENAMES.items():
        if src in src_cols:
            rename_map[src_cols[src]] = tgt

    df = df.rename(columns=rename_map)

    # Ensure all 69 golden columns exist (fill missing with empty string)
    for col in GOLDEN_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 2 — STATE-SPECIFIC TRANSFORMS
# ─────────────────────────────────────────────────────────────────────────────

_MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def parse_delaware_datetime(raw: str) -> tuple[str, str, str]:
    """
    Parse DelDOT datetime: '2015 Jul 17 03:15:00 PM'
    Returns (date: 'M/D/YYYY', mil_time: 'HHMM', year: 'YYYY')
    """
    if not raw or not raw.strip():
        return "", "", ""

    parts = raw.strip().split()
    if len(parts) < 4:
        return raw, "", ""

    year    = parts[0]
    mon     = _MONTHS.get(parts[1].lower(), "01")
    day     = parts[2]
    t_parts = parts[3].split(":")
    hour    = int(t_parts[0]) if t_parts else 0
    minute  = t_parts[1] if len(t_parts) > 1 else "00"
    ampm    = parts[4].upper() if len(parts) > 4 else ""

    if ampm == "PM" and hour < 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0

    mil_time = f"{hour:02d}{minute}"
    date_str = f"{int(mon)}/{int(day)}/{year}"
    return date_str, mil_time, year


def _lv(val: str) -> str:
    return val.strip().lower()


def apply_value_transforms(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all value-level transformations row-by-row efficiently using vectorised maps."""

    # ── Datetime ──────────────────────────────────────────────────────────────
    if "Crash Date" in df.columns:
        parsed = df["Crash Date"].fillna("").apply(parse_delaware_datetime)
        df["Crash Date"]          = parsed.apply(lambda t: t[0])
        df["Crash Military Time"] = parsed.apply(lambda t: t[1])
        # Only overwrite Crash Year from datetime if YEAR column was absent
        year_from_dt = parsed.apply(lambda t: t[2])
        mask_no_year = df["Crash Year"].fillna("").str.strip() == ""
        df.loc[mask_no_year, "Crash Year"] = year_from_dt[mask_no_year]

    # ── Crash Severity → KABCO ────────────────────────────────────────────────
    if "Crash Severity" in df.columns:
        df["Crash Severity"] = (
            df["Crash Severity"].fillna("").str.strip().str.lower()
            .map(MAP_SEVERITY).fillna("O")
        )

    # ── Collision Type ─────────────────────────────────────────────────────────
    if "Collision Type" in df.columns:
        df["Collision Type"] = (
            df["Collision Type"].fillna("").str.strip().str.lower()
            .map(MAP_COLLISION_TYPE).fillna("Not Provided")
        )

    # ── Weather ────────────────────────────────────────────────────────────────
    if "Weather Condition" in df.columns:
        df["Weather Condition"] = (
            df["Weather Condition"].fillna("").str.strip().str.lower()
            .map(MAP_WEATHER).fillna("Not Applicable")
        )

    # ── Light Condition ────────────────────────────────────────────────────────
    if "Light Condition" in df.columns:
        df["Light Condition"] = (
            df["Light Condition"].fillna("").str.strip().str.lower()
            .map(MAP_LIGHT).fillna("7. Unknown")
        )

    # ── Roadway Surface ────────────────────────────────────────────────────────
    if "Roadway Surface Condition" in df.columns:
        df["Roadway Surface Condition"] = (
            df["Roadway Surface Condition"].fillna("").str.strip().str.lower()
            .map(MAP_ROAD_SURFACE).fillna("Not Applicable")
        )

    # ── Y / N Boolean fields → Yes / No ───────────────────────────────────────
    for std_col in ["Pedestrian?", "Alcohol?", "Drug Related?", "Motorcycle?", "Bike?"]:
        if std_col in df.columns:
            df[std_col] = df[std_col].fillna("").str.strip().str.upper().map(
                {"Y": "Yes", "N": "No", "YES": "Yes", "NO": "No"}
            ).fillna("No")

    # ── Unrestrained? (inverted seatbelt) ─────────────────────────────────────
    if "Unrestrained?" in df.columns:
        df["Unrestrained?"] = df["Unrestrained?"].fillna("").str.strip().str.upper().map(
            {"Y": "Belted", "N": "Unbelted"}
        ).fillna("Belted")

    # ── Work Zone Related ──────────────────────────────────────────────────────
    if "Work Zone Related" in df.columns:
        df["Work Zone Related"] = df["Work Zone Related"].fillna("").str.strip().str.upper().map(
            {"Y": "1. Yes", "N": "2. No", "YES": "1. Yes", "NO": "2. No"}
        ).fillna("2. No")

    # ── Work Zone Location ─────────────────────────────────────────────────────
    if "Work Zone Location" in df.columns:
        df["Work Zone Location"] = (
            df["Work Zone Location"].fillna("").str.strip().str.lower()
            .map(MAP_WORK_ZONE_LOCATION).fillna("")
        )

    # ── Work Zone Type ─────────────────────────────────────────────────────────
    if "Work Zone Type" in df.columns:
        df["Work Zone Type"] = (
            df["Work Zone Type"].fillna("").str.strip().str.lower()
            .map(MAP_WORK_ZONE_TYPE).fillna("")
        )

    # ── School Zone (derived from school bus involvement) ─────────────────────
    if "School Zone" in df.columns:
        df["School Zone"] = (
            df["School Zone"].fillna("").str.strip().str.lower()
            .map(MAP_SCHOOL_BUS_TO_ZONE).fillna("3. No")
        )

    # ── Night? ─────────────────────────────────────────────────────────────────
    # Derive from already-mapped Light Condition values
    if "Light Condition" in df.columns:
        night_values = {
            "1. Dawn", "3. Dusk",
            "4. Darkness - Road Lighted",
            "5. Darkness - Road Not Lighted",
            "6. Darkness - Unknown Road Lighting",
        }
        df["Night?"] = df["Light Condition"].isin(night_values).map({True: "Yes", False: "No"})

    # ── County → Juris Code (keep letter codes) ────────────────────────────────
    # Juris Code is kept as-is (K/N/S); Physical Juris Name already renamed

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 3 — FIPS RESOLUTION  (hardcoded — Delaware has only 3 counties)
# ─────────────────────────────────────────────────────────────────────────────

def resolve_fips(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Assign FIPS, District, MPO, and Planning District from the county name.
    Returns updated DataFrame and a fips_lookup dict for the validation report.
    """
    fips_lookup = {}

    for county, geo in DE_COUNTIES.items():
        fips_lookup[county] = {
            "fips":            geo["fips"],
            "countyName":      county,
            "geoid":           geo["geoid"],
            "region":          geo["district"],
            "planningDistrict": geo["district"],
            "mpo":             geo["mpo"],
            "source":          "state_transform",
            "conflicts":       [],
        }

    def _assign(row):
        juris = str(row.get("Physical Juris Name", "")).strip()
        # If juris is a county code (K/N/S), resolve it first
        if juris in DE_COUNTY_CODE_MAP:
            juris = DE_COUNTY_CODE_MAP[juris]
        geo = DE_COUNTIES.get(juris, {})
        row["FIPS"]             = geo.get("fips", "")
        row["Place FIPS"]       = ""
        row["VDOT District"]    = geo.get("district", "")
        row["Planning District"] = geo.get("district", "")
        row["MPO Name"]         = geo.get("mpo", "")
        # Normalise Physical Juris Name to county name (not code)
        if juris in DE_COUNTIES:
            row["Physical Juris Name"] = juris
        return row

    df = df.apply(_assign, axis=1)
    return df, fips_lookup


# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 4 — COMPOSITE CRASH ID
# ─────────────────────────────────────────────────────────────────────────────

def generate_crash_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Generate DE-YYYYMMDD-HHMM-NNNNNNN composite IDs for Document Nbr."""
    needs_id = df["Document Nbr"].fillna("").str.strip() == ""

    def _make_id(row_idx, row):
        date_str = str(row["Crash Date"])
        parts = date_str.split("/")
        if len(parts) == 3:
            date_clean = f"{parts[2]}{int(parts[0]):02d}{int(parts[1]):02d}"
        else:
            date_clean = re.sub(r"[^0-9]", "", date_str)[:8].ljust(8, "0")
        time_str = str(row.get("Crash Military Time", "0000") or "0000").strip().ljust(4, "0")
        return f"DE-{date_clean}-{time_str}-{row_idx + 1:07d}"

    ids = [
        _make_id(i, row) if needs_id.iloc[i] else df["Document Nbr"].iloc[i]
        for i, (_, row) in enumerate(df.iterrows())
    ]
    df["Document Nbr"] = ids
    df["OBJECTID"] = [str(i + 1) for i in range(len(df))]
    return df


# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 5 — EPDO SCORING
# ─────────────────────────────────────────────────────────────────────────────

def compute_epdo(df: pd.DataFrame, weights: dict) -> pd.DataFrame:
    sev_map = {"K": weights["K"], "A": weights["A"], "B": weights["B"],
               "C": weights["C"], "O": weights["O"]}
    df["EPDO_Score"] = df["Crash Severity"].map(sev_map).fillna(weights["O"]).astype(int)
    return df


# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 6 — JURISDICTION RANKING (24 columns)
# ─────────────────────────────────────────────────────────────────────────────

def _yn_true(series: pd.Series) -> pd.Series:
    return series.isin(["Yes", "Y", "1", "YES", "TRUE", "true"])


def compute_rankings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-jurisdiction metrics and 24 ranking columns.
    Rank 1 = most crashes / highest EPDO (most dangerous).
    """

    # Build jurisdiction-level metrics
    metrics: dict[str, dict] = {}

    for _, row in df.iterrows():
        fips  = str(row.get("FIPS", "")).strip()
        juris = str(row.get("Physical Juris Name", "")).strip()
        key   = fips or juris
        if not key:
            continue

        if key not in metrics:
            metrics[key] = {
                "juris":  juris,
                "fips":   fips,
                "district": str(row.get("VDOT District", "") or ""),
                "mpo":    str(row.get("MPO Name", "") or ""),
                "pd":     str(row.get("Planning District", "") or ""),
                "total_crash":                  0,
                "total_ped_crash":              0,
                "total_bike_crash":             0,
                "total_fatal":                  0,
                "total_fatal_serious_injury":   0,
                "total_epdo":                   0,
            }

        m = metrics[key]
        m["total_crash"] += 1
        m["total_epdo"]  += int(row.get("EPDO_Score", 1) or 1)

        if str(row.get("Pedestrian?", "")) in ("Yes", "Y"):
            m["total_ped_crash"] += 1
        if str(row.get("Bike?", "")) in ("Yes", "Y"):
            m["total_bike_crash"] += 1

        sev = str(row.get("Crash Severity", ""))
        if sev == "K":
            m["total_fatal"] += 1
        if sev in ("K", "A"):
            m["total_fatal_serious_injury"] += 1

    # Ranking helper
    def _rank_within(groups: dict[str, list[tuple[str, dict]]], metric: str, col_prefix: str) -> dict[str, int | None]:
        rank_map: dict[str, int | None] = {}
        for grp_entries in groups.values():
            sorted_entries = sorted(grp_entries, key=lambda x: x[1][metric], reverse=True)
            r, prev_val = 0, -1
            for idx, (key, m) in enumerate(sorted_entries):
                if m[metric] != prev_val:
                    r = idx + 1
                    prev_val = m[metric]
                rank_map[key] = r
        return rank_map

    ranking_results: dict[str, dict[str, int | None]] = {k: {} for k in metrics}

    for metric in RANKING_METRICS:
        # Juris scope — all jurisdictions statewide
        juris_groups: dict[str, list] = {"ALL": list(metrics.items())}
        rm = _rank_within(juris_groups, metric, "Juris")
        for k, r in rm.items():
            ranking_results[k][f"Juris_Rank_{metric}"] = r

        # District scope
        by_district: dict[str, list] = {}
        for k, m in metrics.items():
            d = m["district"] or "_unassigned"
            by_district.setdefault(d, []).append((k, m))
        rm = _rank_within(by_district, metric, "District")
        for k, r in rm.items():
            d_key = metrics[k]["district"]
            ranking_results[k][f"District_Rank_{metric}"] = r if d_key else None

        # MPO scope
        by_mpo: dict[str, list] = {}
        for k, m in metrics.items():
            if m["mpo"]:
                by_mpo.setdefault(m["mpo"], []).append((k, m))
            else:
                ranking_results[k][f"MPO_Rank_{metric}"] = None
        rm = _rank_within(by_mpo, metric, "MPO")
        for k, r in rm.items():
            ranking_results[k][f"MPO_Rank_{metric}"] = r

        # PlanningDistrict scope
        by_pd: dict[str, list] = {}
        for k, m in metrics.items():
            if m["pd"]:
                by_pd.setdefault(m["pd"], []).append((k, m))
            else:
                ranking_results[k][f"PlanningDistrict_Rank_{metric}"] = None
        rm = _rank_within(by_pd, metric, "PlanningDistrict")
        for k, r in rm.items():
            ranking_results[k][f"PlanningDistrict_Rank_{metric}"] = r

    # Apply rankings back to each row
    for scope in RANKING_SCOPES:
        for metric in RANKING_METRICS:
            col = f"{scope}_Rank_{metric}"
            df[col] = ""

    def _apply_ranks(row):
        fips  = str(row.get("FIPS", "")).strip()
        juris = str(row.get("Physical Juris Name", "")).strip()
        key   = fips or juris
        ranks = ranking_results.get(key, {})
        for scope in RANKING_SCOPES:
            for metric in RANKING_METRICS:
                col = f"{scope}_Rank_{metric}"
                val = ranks.get(col)
                row[col] = "" if val is None else str(val)
        return row

    df = df.apply(_apply_ranks, axis=1)
    return df, metrics


# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 7 — VALIDATION & REPORTING
# ─────────────────────────────────────────────────────────────────────────────

def build_validation_report(
    df: pd.DataFrame,
    fips_lookup: dict,
    metrics: dict,
    epdo_preset_name: str,
    epdo_weights: dict,
    column_mapping: dict,
) -> dict:
    total = len(df)
    sev_dist: dict[str, int] = {}
    for sev in ["K", "A", "B", "C", "O"]:
        sev_dist[sev] = int((df["Crash Severity"] == sev).sum())
    sev_dist["unmapped"] = int(~df["Crash Severity"].isin(["K","A","B","C","O"]).sum())

    fips_resolved = sum(1 for v in fips_lookup.values() if v.get("fips"))
    mapped   = sum(1 for v in column_mapping.values() if v["status"] == "mapped")
    renamed  = sum(1 for v in column_mapping.values() if v["status"] == "renamed")
    missing  = sum(1 for v in column_mapping.values() if v["status"] == "missing")

    quality = round(
        0.5 * (mapped + renamed) / len(GOLDEN_COLUMNS) * 100
        + 0.5 * (fips_resolved / max(len(fips_lookup), 1)) * 100,
        1,
    )

    mandatory_check = {}
    for col in ["Physical Juris Name", "x", "y", "Crash Severity"]:
        pct = float((df[col].fillna("").str.strip() != "").sum()) / max(total, 1) * 100
        mandatory_check[col] = f"OK ({pct:.1f}% filled)" if pct > 90 else f"WARNING ({pct:.1f}% filled)"

    # Unmapped values check (Crash Severity)
    unmapped_sev = df.loc[~df["Crash Severity"].isin(["K","A","B","C","O"]), "Crash Severity"].value_counts().to_dict()

    return {
        "state":         STATE_NAME,
        "state_fips":    STATE_FIPS,
        "state_abbr":    STATE_ABBR,
        "processed_at":  datetime.now(timezone.utc).isoformat(),
        "total_rows":    total,
        "total_columns": 69 + len(ENRICHMENT_COLUMNS) + len(RANKING_SCOPES) * len(RANKING_METRICS),
        "golden_columns":     69,
        "enrichment_columns": len(ENRICHMENT_COLUMNS),
        "ranking_columns":    len(RANKING_SCOPES) * len(RANKING_METRICS),
        "quality_score": quality,
        "fips_coverage": {
            "total_jurisdictions": len(fips_lookup),
            "resolved":    fips_resolved,
            "unresolved":  len(fips_lookup) - fips_resolved,
            "coverage_pct": round(fips_resolved / max(len(fips_lookup), 1) * 100, 1),
            "method_breakdown": {
                m: sum(1 for v in fips_lookup.values() if v.get("source") == m)
                for m in ["name_match", "centroid", "state_transform", "hierarchy_fallback"]
            },
        },
        "severity_distribution": sev_dist,
        "epdo_config": {
            "preset": epdo_preset_name,
            "weights": epdo_weights,
        },
        "mapping_completeness": {
            "mapped":   mapped,
            "renamed":  renamed,
            "missing":  missing,
            "coverage_pct": round((mapped + renamed) / len(GOLDEN_COLUMNS) * 100, 1),
        },
        "mandatory_columns": mandatory_check,
        "ranking_scopes":  RANKING_SCOPES,
        "ranking_metrics": RANKING_METRICS,
        "conflicts": [],
        "warnings": [],
        "unmapped_values": {"Crash Severity": unmapped_sev} if unmapped_sev else {},
    }


# ─────────────────────────────────────────────────────────────────────────────
#  COLUMN MAPPING RECORD  (for validation report)
# ─────────────────────────────────────────────────────────────────────────────

def build_column_mapping_record(source_cols: list[str]) -> dict:
    src_upper = {c.upper().strip() for c in source_cols}
    mapping = {}

    rename_upper = {k.upper(): v for k, v in COLUMN_RENAMES.items()}

    for tgt in GOLDEN_COLUMNS:
        if tgt in source_cols:
            mapping[tgt] = {"source": tgt, "status": "mapped"}
        elif tgt.upper() in rename_upper.values():
            # Find the source col that renames to this target
            for src_u, tgt_v in rename_upper.items():
                if tgt_v == tgt and src_u in src_upper:
                    orig = next((c for c in source_cols if c.upper().strip() == src_u), src_u)
                    mapping[tgt] = {"source": orig, "status": "renamed"}
                    break
            else:
                mapping[tgt] = {"source": None, "status": "missing"}
        else:
            mapping[tgt] = {"source": None, "status": "missing"}

    return mapping


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def normalize(
    input_path: str,
    output_path: str | None = None,
    epdo_preset: str = DEFAULT_EPDO_PRESET,
    skip_if_normalized: bool = False,
    report_path: str | None = None,
) -> str:
    t0 = time.time()
    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"Input not found: {src}")

    print(f"\n{'─'*60}")
    print(f"  CrashLens Delaware Normalization  |  {datetime.now():%Y-%m-%d %H:%M}")
    print(f"  Input : {src.name}")
    print(f"{'─'*60}")

    # Load
    print("  [1/7] Loading CSV...")
    df = pd.read_csv(src, dtype=str, low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    total_rows = len(df)
    print(f"        {total_rows:,} rows  ×  {len(df.columns)} columns")

    # Skip if already normalized
    if skip_if_normalized and is_already_normalized(df.columns.tolist()):
        print("  ✓ Already normalized — skipping (use --force to override)")
        return str(src)

    # Column mapping record (before renames)
    col_mapping = build_column_mapping_record(df.columns.tolist())

    # Phase 1 — Column renames
    print("  [2/7] Phase 1: Column renames...")
    df = apply_column_renames(df)

    # Phase 2 — Value transforms
    print("  [3/7] Phase 2: Value transforms (datetime, severity, Y/N, etc.)...")
    df = apply_value_transforms(df)

    # Phase 3 — FIPS Resolution
    print("  [4/7] Phase 3: FIPS resolution (DE hardcoded — 3 counties)...")
    df, fips_lookup = resolve_fips(df)
    resolved = sum(1 for v in fips_lookup.values() if v["fips"])
    print(f"        {resolved}/{len(fips_lookup)} jurisdictions resolved")

    # Phase 4 — Crash IDs
    print("  [5/7] Phase 4: Generating composite crash IDs...")
    df = generate_crash_ids(df)
    print(f"        IDs: DE-YYYYMMDD-HHMM-NNNNNNN format")

    # Phase 5 — EPDO
    weights = EPDO_PRESETS.get(epdo_preset, EPDO_PRESETS[DEFAULT_EPDO_PRESET])
    print(f"  [6/7] Phase 5+6: EPDO scoring ({epdo_preset.upper()}) + Ranking...")
    df = compute_epdo(df, weights)

    # Phase 6 — Rankings
    df, metrics = compute_rankings(df)
    print(f"        Ranked {len(metrics)} jurisdictions across {len(RANKING_SCOPES)} scopes × {len(RANKING_METRICS)} metrics")

    # Phase 7 — Validation report
    print("  [7/7] Phase 7: Validation report...")
    report = build_validation_report(df, fips_lookup, metrics, epdo_preset, weights, col_mapping)
    print(f"        Quality score: {report['quality_score']}%")
    sev = report["severity_distribution"]
    print(f"        Severity: K={sev['K']}  A={sev['A']}  B={sev['B']}  C={sev['C']}  O={sev['O']}")

    # Build output column order: 69 standard + enrichment + 24 ranking + extras
    extra_cols = [c for c in df.columns if c in EXTRA_COLUMNS]
    ranking_cols = [f"{s}_Rank_{m}" for s in RANKING_SCOPES for m in RANKING_METRICS]
    all_out_cols = GOLDEN_COLUMNS + ENRICHMENT_COLUMNS + ranking_cols + extra_cols

    # Keep only columns that exist in df
    all_out_cols = [c for c in all_out_cols if c in df.columns]

    # Determine output path
    if output_path is None:
        output_path = str(src.parent / f"{src.stem}_normalized_ranked.csv")
    if report_path is None:
        report_path = str(src.parent / f"{src.stem}_validation_report.json")

    df[all_out_cols].to_csv(output_path, index=False)
    with open(report_path, "w", encoding="utf-8") as fp:
        json.dump(report, fp, indent=2)

    elapsed = time.time() - t0
    print(f"\n  ✅ Done in {elapsed:.1f}s")
    print(f"     Output  → {output_path}")
    print(f"     Report  → {report_path}")
    print(f"     Columns → {len(all_out_cols)} ({len(GOLDEN_COLUMNS)} standard + {len(ENRICHMENT_COLUMNS)} enrich + {len(ranking_cols)} rank + {len(extra_cols)} extra)")
    print(f"{'─'*60}\n")
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
#  CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CrashLens — Delaware (DelDOT) crash data normalization pipeline"
    )
    parser.add_argument("--input",  "-i", required=True,  help="Input CSV path")
    parser.add_argument("--output", "-o", default=None,   help="Output CSV path (default: {stem}_normalized_ranked.csv)")
    parser.add_argument("--report", "-r", default=None,   help="Validation report JSON path")
    parser.add_argument(
        "--epdo", default=DEFAULT_EPDO_PRESET,
        choices=list(EPDO_PRESETS.keys()),
        help=f"EPDO weight preset (default: {DEFAULT_EPDO_PRESET})"
    )
    parser.add_argument(
        "--skip-if-normalized", action="store_true",
        help="Skip processing if file is already in CrashLens standard format"
    )
    args = parser.parse_args()

    try:
        normalize(
            input_path=args.input,
            output_path=args.output,
            epdo_preset=args.epdo,
            skip_if_normalized=args.skip_if_normalized,
            report_path=args.report,
        )
    except Exception as exc:
        print(f"\n  ❌ Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
