# CRASH LENS — Delaware Data Normalization
# Claude Code Prompt (Copy and paste this entire file into Claude Code)
#
# PURPOSE: Transform Delaware's public crash CSV into the CRASH LENS
#          69-column standard schema so the frontend filters work correctly.
#
# INPUT:  Raw Delaware crash CSV from data.delaware.gov (dataset 827n-m6xc)
# OUTPUT: Normalized CSV matching the CRASH LENS 69-column standard
#
# USAGE:  python de_normalize.py input.csv output.csv

"""
INSTRUCTIONS FOR CLAUDE CODE:

Read the input CSV file and produce an output CSV that matches the CRASH LENS
frontend 69-column schema. The frontend expects EXACT string values — a single
typo will break filters.

The script must be IDEMPOTENT: if the data is already normalized, detect it
and skip re-processing.

Below is the complete transformation specification.
"""

import pandas as pd
import sys
import os
import json
from datetime import datetime

# ============================================================
# CONFIGURATION — VALUE MAPPING TABLES
# ============================================================

# --- CRASH SEVERITY (MANDATORY) ---
# Delaware only has: Fatality / Personal Injury / PDO / Non-Reportable
# Frontend expects: K, A, B, C, O
# WARNING: DE does NOT distinguish A/B/C injury levels.
# All "Personal Injury Crash" → B (documented limitation)
SEVERITY_MAP = {
    "Fatality Crash": "K",
    "Personal Injury Crash": "B",
    "Property Damage Only": "O",
    "Non-Reportable": "O",
}

# --- PHYSICAL JURIS NAME (MANDATORY) ---
# Delaware has 3 counties. Format: "NNN. County Name"
COUNTY_NAME_MAP = {
    "Kent": "001. Kent County",
    "New Castle": "003. New Castle County",
    "Sussex": "005. Sussex County",
}

COUNTY_CODE_MAP = {
    "K": "001",
    "N": "003",
    "S": "005",
}

# --- COLLISION TYPE ---
COLLISION_TYPE_MAP = {
    "Front to rear": "1. Rear End",
    "Angle": "2. Angle",
    "Front to front": "3. Head On",
    "Sideswipe, same direction": "4. Sideswipe - Same Direction",
    "Sideswipe, opposite direction": "5. Sideswipe - Opposite Direction",
    "Not a collision between two vehicles": "8. Non-Collision",
    "Rear to rear": "16. Other",
    "Rear to side": "16. Other",
    "Other": "16. Other",
    "Unknown": "Not Provided",
}

# --- WEATHER CONDITION ---
WEATHER_MAP = {
    "Clear": "1. No Adverse Condition (Clear/Cloudy)",
    "Cloudy": "1. No Adverse Condition (Clear/Cloudy)",
    "Fog, Smog, Smoke": "3. Fog",
    "Rain": "5. Rain",
    "Snow": "6. Snow",
    "Sleet, Hail (freezing rain or drizzle)": "7. Sleet/Hail",
    "Blowing Sand, Soil, Dirt": "10. Blowing Sand, Soil, Dirt, or Snow",
    "Blowing Snow": "10. Blowing Sand, Soil, Dirt, or Snow",
    "Severe Crosswinds": "11. Severe Crosswinds",
    "Other": "9. Other",
    "Unknown": "9. Other",
}

# --- LIGHT CONDITION ---
LIGHT_MAP = {
    "Dawn": "1. Dawn",
    "Daylight": "2. Daylight",
    "Dusk": "3. Dusk",
    "Dark-Lighted": "4. Darkness - Road Lighted",
    "Dark-Not Lighted": "5. Darkness - Road Not Lighted",
    "Dark-Unknown Lighting": "6. Darkness - Unknown Road Lighting",
    "Other": "7. Unknown",
    "Unknown": "7. Unknown",
}

# --- ROADWAY SURFACE CONDITION ---
SURFACE_MAP = {
    "Dry": "1. Dry",
    "Wet": "2. Wet",
    "Snow": "3. Snowy",
    "Ice/Frost": "4. Icy",
    "Oil": "6. Oil/Other Fluids",
    "Other": "7. Other",
    "Water (standing, moving)": "9. Water (Standing, Moving)",
    "Slush": "10. Slush",
    "Mud, Dirt, Gravel": "11. Sand, Dirt, Gravel",
    "Sand": "11. Sand, Dirt, Gravel",
    "Unknown": "7. Other",
}

# --- WORK ZONE RELATED ---
WORK_ZONE_MAP = {"Y": "1. Yes", "N": "2. No"}

# --- WORK ZONE LOCATION ---
WZ_LOCATION_MAP = {
    "Advance Warning Area": "1. Advance Warning Area",
    "Transition Area": "2. Transition Area",
    "Activity Area": "3. Activity Area",
    "Termination Area": "4. Termination Area",
    "Before the First Work Zone Warning Sign": "1. Advance Warning Area",
}

# --- WORK ZONE TYPE ---
WZ_TYPE_MAP = {
    "Lane Closure": "1. Lane Closure",
    "Lane Shift/Crossover": "2. Lane Shift/Crossover",
    "Work on Shoulder or Median": "3. Work on Shoulder or Median",
    "Intermittent or Moving Work": "4. Intermittent or Moving Work",
    "Other": "5. Other",
}

# --- Y/N → Yes/No ---
YN_MAP = {"Y": "Yes", "N": "No"}

# --- SEATBELT → Unrestrained ---
# Y = seatbelt USED = Belted ; N = not used = Unbelted
SEATBELT_MAP = {"Y": "Belted", "N": "Unbelted"}

# --- NIGHT? (derived from lighting) ---
NIGHT_MAP = {
    "Dark-Lighted": "Yes",
    "Dark-Not Lighted": "Yes",
    "Dark-Unknown Lighting": "Yes",
    "Dawn": "No",
    "Daylight": "No",
    "Dusk": "No",
    "Other": "No",
    "Unknown": "No",
}


# ============================================================
# MAIN NORMALIZATION FUNCTION
# ============================================================
def normalize_delaware(input_path, output_path):
    print(f"\n{'='*60}")
    print(f"  CRASH LENS — Delaware Normalizer")
    print(f"  Input:  {input_path}")
    print(f"  Output: {output_path}")
    print(f"{'='*60}\n")

    # Read
    df = pd.read_csv(input_path, dtype=str, low_memory=False)
    total = len(df)
    print(f"  Loaded {total:,} rows, {len(df.columns)} columns")

    # --- IDEMPOTENCY CHECK ---
    if "Crash Severity" in df.columns and "Physical Juris Name" in df.columns:
        # Check if values already match frontend format
        sample_sev = df["Crash Severity"].dropna().head(10).tolist()
        if all(v in ("K", "A", "B", "C", "O") for v in sample_sev if v):
            print("  ⚠️  Data appears already normalized. Skipping.")
            df.to_csv(output_path, index=False)
            return

    # --- PARSE DATETIME ---
    print("  Parsing CRASH DATETIME...")
    dt_series = pd.to_datetime(df["CRASH DATETIME"], errors="coerce")
    df["Crash Year"] = dt_series.dt.year.astype("Int64").astype(str).str.replace("<NA>", "")
    # If YEAR column exists and Crash Year is empty, fall back
    if "YEAR" in df.columns:
        mask = (df["Crash Year"] == "") | (df["Crash Year"] == "nan")
        df.loc[mask, "Crash Year"] = df.loc[mask, "YEAR"]
    df["Crash Date"] = dt_series.dt.strftime("%m/%d/%Y").fillna("")
    df["Crash Military Time"] = dt_series.dt.strftime("%H%M").fillna("")

    # --- MANDATORY: CRASH SEVERITY ---
    print("  Mapping Crash Severity...")
    df["Crash Severity"] = df["CRASH CLASSIFICATION DESCRIPTION"].map(SEVERITY_MAP)
    unmapped_sev = df[df["Crash Severity"].isna() & df["CRASH CLASSIFICATION DESCRIPTION"].notna()]["CRASH CLASSIFICATION DESCRIPTION"].unique()
    if len(unmapped_sev) > 0:
        print(f"    ⚠️  UNMAPPED severity values: {unmapped_sev}")
    df["Crash Severity"] = df["Crash Severity"].fillna("O")

    # --- MANDATORY: PHYSICAL JURIS NAME ---
    print("  Mapping Physical Juris Name...")
    df["Physical Juris Name"] = df["COUNTY NAME"].map(COUNTY_NAME_MAP)
    df["Physical Juris Name"] = df["Physical Juris Name"].fillna("Unknown")

    # --- MANDATORY: JURIS CODE ---
    df["Juris Code"] = df["COUNTY CODE"].map(COUNTY_CODE_MAP).fillna("")

    # --- MANDATORY: COORDINATES ---
    df["x"] = df.get("LONGITUDE", "")
    df["y"] = df.get("LATITUDE", "")

    # --- VALUE-MAPPED COLUMNS ---
    print("  Mapping value columns...")
    df["Collision Type"] = df["MANNER OF IMPACT DESCRIPTION"].map(COLLISION_TYPE_MAP).fillna("Not Provided")
    df["Weather Condition"] = df["WEATHER 1 DESCRIPTION"].map(WEATHER_MAP).fillna("9. Other")
    df["Light Condition"] = df["LIGHTING CONDITION DESCRIPTION"].map(LIGHT_MAP).fillna("7. Unknown")
    df["Roadway Surface Condition"] = df["ROAD SURFACE DESCRIPTION"].map(SURFACE_MAP).fillna("7. Other")

    # Boolean flags
    df["Alcohol?"] = df["ALCOHOL INVOLVED"].map(YN_MAP).fillna("No")
    df["Drug Related?"] = df["DRUG INVOLVED"].map(YN_MAP).fillna("No")
    df["Bike?"] = df["BICYCLED INVOLVED"].map(YN_MAP).fillna("No")
    df["Motorcycle?"] = df["MOTORCYCLE INVOLVED"].map(YN_MAP).fillna("No")
    df["Pedestrian?"] = df["PEDESTRIAN INVOLVED"].map(YN_MAP).fillna("No")
    df["Unrestrained?"] = df["SEATBELT USED"].map(SEATBELT_MAP).fillna("Belted")

    # Work zone
    df["Work Zone Related"] = df["WORK ZONE"].map(WORK_ZONE_MAP).fillna("2. No")
    df["Work Zone Location"] = df["WORK ZONE LOCATION DESCRIPTION"].map(WZ_LOCATION_MAP).fillna("")
    df["Work Zone Type"] = df["WORK ZONE TYPE DESCRIPTION"].map(WZ_TYPE_MAP).fillna("")

    # Night? (derived)
    df["Night?"] = df["LIGHTING CONDITION DESCRIPTION"].map(NIGHT_MAP).fillna("No")

    # --- GENERATED COLUMNS ---
    print("  Generating gap-fill columns...")
    df["OBJECTID"] = range(1, len(df) + 1)
    df["Document Nbr"] = df.apply(
        lambda r: f"DE-{r.get('Crash Year','0000')}-{r.name+1:06d}", axis=1
    )

    # --- DERIVED COUNTS (approximations) ---
    df["K_People"] = (df["Crash Severity"] == "K").astype(int).astype(str)
    df["A_People"] = "0"
    df["B_People"] = (df["Crash Severity"] == "B").astype(int).astype(str)
    df["C_People"] = "0"
    df["Persons Injured"] = df["B_People"]
    df["Pedestrians Killed"] = ((df["Crash Severity"] == "K") & (df["Pedestrian?"] == "Yes")).astype(int).astype(str)
    df["Pedestrians Injured"] = ((df["Crash Severity"] == "B") & (df["Pedestrian?"] == "Yes")).astype(int).astype(str)

    # --- SET DEFAULT COLUMNS (gaps with no data) ---
    defaults = {
        "Vehicle Count": "",
        "Relation To Roadway": "Not Provided",
        "Roadway Alignment": "",
        "Roadway Surface Type": "",
        "Roadway Defect": "",
        "Roadway Description": "",
        "Intersection Type": "",
        "Traffic Control Type": "",
        "Traffic Control Status": "",
        "School Zone": "Not Provided",
        "First Harmful Event": "",
        "First Harmful Event Loc": "",
        "Animal Related?": "No",
        "Distracted?": "No",
        "Drowsy?": "No",
        "Guardrail Related?": "No",
        "Hitrun?": "No",
        "Lgtruck?": "No",
        "Speed?": "No",
        "Max Speed Diff": "",
        "RoadDeparture Type": "NOT_RD",
        "Intersection Analysis": "Not Intersection",
        "Senior?": "No",
        "Young?": "No",
        "Mainline?": "No",
        "DOT District": "",
        "Functional Class": "",     # CRITICAL GAP - must be filled externally
        "Facility Type": "",
        "Area Type": "",
        "SYSTEM": "",
        "VSP": "",
        "Ownership": "",            # CRITICAL GAP - must be filled externally
        "Planning District": "",
        "MPO Name": "",
        "RTE Name": "",
        "RNS MP": "",
        "Node": "",
        "Node Offset (ft)": "",
    }
    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val

    # --- BUILD OUTPUT IN EXACT 69-COLUMN ORDER ---
    frontend_cols = [
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
        "DOT District", "Juris Code", "Physical Juris Name",
        "Functional Class", "Facility Type", "Area Type", "SYSTEM", "VSP", "Ownership",
        "Planning District", "MPO Name", "RTE Name", "RNS MP", "Node", "Node Offset (ft)",
        "x", "y",
    ]

    # Identify extra columns to preserve (DE-specific)
    extra_cols = [c for c in df.columns if c not in frontend_cols]
    output_cols = frontend_cols + extra_cols
    # Ensure all columns exist
    for col in output_cols:
        if col not in df.columns:
            df[col] = ""

    out = df[output_cols]

    # --- VALIDATION ---
    print("\n  VALIDATION:")
    sev_valid = out["Crash Severity"].isin(["K", "A", "B", "C", "O"])
    print(f"    Crash Severity valid:     {sev_valid.sum():,} / {total:,} ({sev_valid.mean()*100:.1f}%)")
    juris_valid = out["Physical Juris Name"].str.match(r"^\d{3}\. ")
    print(f"    Physical Juris Name valid: {juris_valid.sum():,} / {total:,} ({juris_valid.mean()*100:.1f}%)")
    has_coords = (out["x"] != "") & (out["y"] != "")
    print(f"    Coordinates present:       {has_coords.sum():,} / {total:,} ({has_coords.mean()*100:.1f}%)")
    fc_valid = out["Functional Class"] != ""
    print(f"    Functional Class filled:   {fc_valid.sum():,} / {total:,} ({fc_valid.mean()*100:.1f}%)")
    own_valid = out["Ownership"] != ""
    print(f"    Ownership filled:          {own_valid.sum():,} / {total:,} ({own_valid.mean()*100:.1f}%)")

    if fc_valid.sum() == 0:
        print("\n    ⚠️  CRITICAL: Functional Class is EMPTY.")
        print("       'All Roads (No Interstate)' filter will NOT work.")
        print("       Contact DelDOT for HPMS road classification data,")
        print("       or use OSM road tags to derive functional class from x,y.")

    if own_valid.sum() == 0:
        print("\n    ⚠️  CRITICAL: Ownership is EMPTY.")
        print("       'County Roads Only' and 'City Roads Only' filters will NOT work.")
        print("       Contact DelDOT for road ownership data,")
        print("       or derive from OSM road attributes.")

    # --- WRITE ---
    out.to_csv(output_path, index=False)
    size_mb = os.path.getsize(output_path) / (1024*1024)
    print(f"\n  ✅ Output: {output_path} ({size_mb:.1f} MB)")
    print(f"     {len(out):,} rows × {len(out.columns)} columns")
    print(f"     69 standard + {len(extra_cols)} extra passthrough columns")
    print(f"\n{'='*60}\n")


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python de_normalize.py input.csv output.csv")
        sys.exit(1)
    normalize_delaware(sys.argv[1], sys.argv[2])
