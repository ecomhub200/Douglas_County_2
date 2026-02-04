#!/usr/bin/env python3
"""
CDOT to Crash Lens Data Converter
==================================
Converts raw Colorado DOT crash data to the format expected by the Crash Lens tool.

Usage:
    python convert_cdot_data.py

Input:  Raw CDOT CSV files in data/CDOT/
Output: Processed CSV file in data/processed/Douglas_County_Processed.csv

Author: Claude Code Assistant
Date: 2026-02-04
"""

import csv
import os
import re
from datetime import datetime
from pathlib import Path

# Configuration
INPUT_DIR = Path(__file__).parent.parent / "data" / "CDOT"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "processed"
OUTPUT_FILE = OUTPUT_DIR / "Douglas_County_Processed.csv"

# Input files (in order)
INPUT_FILES = [
    "2021 douglas.csv",
    "2022 douglas county.csv",
    "2023 douglas county.csv",
    "2024 douglas county.csv",
    "Douglas_County.csv",  # 2025
]

# CDOT Column Names (source)
class CDOT:
    CUID = "CUID"
    SYSTEM_CODE = "System Code"
    RD_NUMBER = "Rd_Number"
    RD_SECTION = "Rd_Section"
    CITY_STREET = "City_Street"
    CRASH_DATE = "Crash Date"
    CRASH_TIME = "Crash Time"
    AGENCY_ID = "Agency Id"
    CITY = "City"
    COUNTY = "County"
    LATITUDE = "Latitude"
    LONGITUDE = "Longitude"
    LOCATION_1 = "Location 1"
    LINK = "Link"
    LOCATION_2 = "Location 2"
    LOCATION = "Location"
    ROAD_DESC = "Road Description"
    FIRST_HE = "First HE"
    MHE = "MHE"
    CRASH_TYPE = "Crash Type"
    INJURY_00 = "Injury 00"  # No injury (O)
    INJURY_01 = "Injury 01"  # Possible injury (C)
    INJURY_02 = "Injury 02"  # Minor injury (B)
    INJURY_03 = "Injury 03"  # Serious injury (A)
    INJURY_04 = "Injury 04"  # Fatal (K)
    NUM_KILLED = "Number Killed"
    NUM_INJURED = "Number Injured"
    TOTAL_VEHICLES = "Total Vehicles"
    SECONDARY_CRASH = "Secondary Crash"
    CONSTRUCTION_ZONE = "Construction Zone"
    SCHOOL_ZONE = "School Zone"
    ROAD_CONTOUR_CURVES = "Road Contour Curves"
    ROAD_CONTOUR_GRADE = "Road Contour Grade"
    ROAD_CONDITION = "Road Condition"
    LIGHTING = "Lighting Conditions"
    WEATHER = "Weather Condition"
    WEATHER_2 = "Weather Condition 2"
    TU1_TYPE = "TU-1 Type"
    TU2_TYPE = "TU-2 Type"
    TU1_SPEED_LIMIT = "TU-1 Speed Limit"
    TU1_EST_SPEED = "TU-1 Estimated Speed"
    TU1_DRIVER_ACTION = "TU-1 Driver Action"
    TU2_DRIVER_ACTION = "TU-2 Driver Action"
    TU1_HUMAN_FACTOR = "TU-1 Human Contributing Factor"
    TU2_HUMAN_FACTOR = "TU-2 Human Contributing Factor"
    TU1_AGE = "TU-1 Age"
    TU2_AGE = "TU-2 Age"
    TU1_ALCOHOL = "TU-1 Alcohol Suspected"
    TU2_ALCOHOL = "TU-2 Alcohol Suspected"
    TU1_HIT_RUN = "TU-1 Hit And Run"
    TU2_HIT_RUN = "TU-2 Hit And Run"
    TU1_RESTRAINT = "TU-1 Safety restraint Use"
    TU2_RESTRAINT = "TU-2 Safety restraint Use"
    TU1_NM_TYPE = "TU-1 NM Type"
    TU2_NM_TYPE = "TU-2 NM Type"
    TU1_MARIJUANA = "TU-1  Marijuana Suspected"
    TU2_MARIJUANA = "TU-2 Marijuana Suspected"
    TU1_DRUGS = "TU-1 Other Drugs Suspected "
    TU2_DRUGS = "TU-2 Other Drugs Suspected "


# Output Column Names (tool expects)
OUTPUT_COLUMNS = [
    "Document Nbr",
    "Crash Year",
    "Crash Date",
    "Crash Military Time",
    "Crash Severity",
    "K_People",
    "A_People",
    "B_People",
    "C_People",
    "O_People",
    "Collision Type",
    "Weather Condition",
    "Light Condition",
    "Roadway Surface Condition",
    "Roadway Alignment",
    "Roadway Description",
    "Intersection Type",
    "Traffic Control Type",
    "Work Zone Related",
    "School Zone",
    "Alcohol?",
    "Bike?",
    "Pedestrian?",
    "Speed?",
    "Distracted?",
    "Hitrun?",
    "Senior?",
    "Young?",
    "Night?",
    "Unrestrained?",
    "Motorcycle?",
    "Drug Related?",
    "RTE Name",
    "Node",
    "x",
    "y",
    "Physical Juris Name",
    "Agency",
    "Total Vehicles",
    "First Harmful Event",
]


def safe_int(value, default=0):
    """Safely convert value to int."""
    try:
        return int(value) if value else default
    except (ValueError, TypeError):
        return default


def derive_severity(row):
    """
    Derive crash severity from injury columns.
    Returns highest severity: K > A > B > C > O
    """
    k = safe_int(row.get(CDOT.INJURY_04, 0))
    a = safe_int(row.get(CDOT.INJURY_03, 0))
    b = safe_int(row.get(CDOT.INJURY_02, 0))
    c = safe_int(row.get(CDOT.INJURY_01, 0))

    if k > 0:
        return "K"
    elif a > 0:
        return "A"
    elif b > 0:
        return "B"
    elif c > 0:
        return "C"
    else:
        return "O"


def extract_year(date_str):
    """Extract year from M/D/YYYY format."""
    if not date_str:
        return ""
    try:
        parts = date_str.split("/")
        if len(parts) == 3:
            return parts[2]
    except:
        pass
    return ""


def format_time(time_str):
    """Convert HH:MM:SS to HHMM military time."""
    if not time_str:
        return ""
    try:
        # Handle HH:MM:SS format
        if ":" in time_str:
            parts = time_str.split(":")
            return f"{parts[0].zfill(2)}{parts[1].zfill(2)}"
        # Already in HHMM format
        return time_str.zfill(4)
    except:
        return ""


def build_route_name(row):
    """
    Build composite route name.
    Format: "State Highway 83 - S PARKER RD"
    """
    system = row.get(CDOT.SYSTEM_CODE, "").strip()
    rd_num = row.get(CDOT.RD_NUMBER, "").strip()
    location1 = row.get(CDOT.LOCATION_1, "").strip()

    # Clean up route number (remove leading zeros and section letters)
    rd_num_clean = re.sub(r'^0+', '', rd_num)  # Remove leading zeros
    rd_num_clean = re.sub(r'[A-Za-z]$', '', rd_num_clean)  # Remove trailing letter

    # Build route name based on system code
    if system == "Interstate Highway":
        if location1:
            return f"Interstate {rd_num_clean} - {location1}"
        return f"Interstate {rd_num_clean}"
    elif system == "State Highway":
        if location1:
            return f"State Highway {rd_num_clean} - {location1}"
        return f"State Highway {rd_num_clean}"
    elif system == "County Road":
        if location1:
            return f"County Road {rd_num_clean} - {location1}"
        return f"County Road {rd_num_clean}"
    elif system == "City Street":
        if location1:
            return f"City Street - {location1}"
        return "City Street"
    else:
        # Default: use location1 or system
        if location1:
            return location1
        return system or "Unknown"


def build_node(row):
    """
    Build intersection node from Location 1 + Location 2.
    Format: "LOCATION1 & LOCATION2"
    """
    loc1 = row.get(CDOT.LOCATION_1, "").strip()
    loc2 = row.get(CDOT.LOCATION_2, "").strip()

    if loc1 and loc2:
        return f"{loc1} & {loc2}"
    elif loc1:
        return loc1
    else:
        return ""


def is_pedestrian(row):
    """Check if crash involves pedestrian."""
    nm1 = row.get(CDOT.TU1_NM_TYPE, "").lower()
    nm2 = row.get(CDOT.TU2_NM_TYPE, "").lower()
    return "Y" if "pedestrian" in nm1 or "pedestrian" in nm2 else "N"


def is_bicycle(row):
    """Check if crash involves bicycle."""
    nm1 = row.get(CDOT.TU1_NM_TYPE, "").lower()
    nm2 = row.get(CDOT.TU2_NM_TYPE, "").lower()
    return "Y" if "bicycl" in nm1 or "bicycl" in nm2 else "N"


def is_motorcycle(row):
    """Check if crash involves motorcycle."""
    tu1 = row.get(CDOT.TU1_TYPE, "").lower()
    tu2 = row.get(CDOT.TU2_TYPE, "").lower()
    return "Y" if "motorcycle" in tu1 or "motorcycle" in tu2 else "N"


def is_alcohol(row):
    """Check if alcohol was suspected."""
    alc1 = row.get(CDOT.TU1_ALCOHOL, "").lower()
    alc2 = row.get(CDOT.TU2_ALCOHOL, "").lower()
    return "Y" if "yes" in alc1 or "yes" in alc2 else "N"


def is_drug_related(row):
    """Check if drugs (marijuana or other) were suspected."""
    mar1 = row.get(CDOT.TU1_MARIJUANA, "").lower()
    mar2 = row.get(CDOT.TU2_MARIJUANA, "").lower()
    drug1 = row.get(CDOT.TU1_DRUGS, "").lower()
    drug2 = row.get(CDOT.TU2_DRUGS, "").lower()
    return "Y" if any("yes" in x for x in [mar1, mar2, drug1, drug2]) else "N"


def is_hit_run(row):
    """Check if hit and run."""
    hr1 = str(row.get(CDOT.TU1_HIT_RUN, "")).upper()
    hr2 = str(row.get(CDOT.TU2_HIT_RUN, "")).upper()
    return "Y" if hr1 == "TRUE" or hr2 == "TRUE" else "N"


def is_speed_related(row):
    """Check if speed was a factor."""
    action1 = row.get(CDOT.TU1_DRIVER_ACTION, "").lower()
    action2 = row.get(CDOT.TU2_DRIVER_ACTION, "").lower()
    factor1 = row.get(CDOT.TU1_HUMAN_FACTOR, "").lower()
    factor2 = row.get(CDOT.TU2_HUMAN_FACTOR, "").lower()

    speed_terms = ["too fast", "speed", "racing", "exceeded"]
    all_fields = [action1, action2, factor1, factor2]

    return "Y" if any(term in field for term in speed_terms for field in all_fields) else "N"


def is_distracted(row):
    """Check if distraction was a factor."""
    factor1 = row.get(CDOT.TU1_HUMAN_FACTOR, "").lower()
    factor2 = row.get(CDOT.TU2_HUMAN_FACTOR, "").lower()

    distract_terms = ["distract", "cell phone", "electronic", "texting", "inattent"]

    return "Y" if any(term in factor1 or term in factor2 for term in distract_terms) else "N"


def is_unrestrained(row):
    """Check if unrestrained occupant."""
    rest1 = row.get(CDOT.TU1_RESTRAINT, "").lower()
    rest2 = row.get(CDOT.TU2_RESTRAINT, "").lower()
    return "Y" if "not used" in rest1 or "not used" in rest2 else "N"


def is_senior(row):
    """Check if senior driver (65+)."""
    age1 = safe_int(row.get(CDOT.TU1_AGE, 0))
    age2 = safe_int(row.get(CDOT.TU2_AGE, 0))
    return "Y" if age1 >= 65 or age2 >= 65 else "N"


def is_young(row):
    """Check if young driver (under 25)."""
    age1 = safe_int(row.get(CDOT.TU1_AGE, 0))
    age2 = safe_int(row.get(CDOT.TU2_AGE, 0))
    # Only count if age is valid (> 0)
    return "Y" if (0 < age1 < 25) or (0 < age2 < 25) else "N"


def is_night(row):
    """Check if nighttime crash."""
    light = row.get(CDOT.LIGHTING, "").lower()
    return "Y" if "dark" in light else "N"


def is_intersection(row):
    """Determine intersection type from Road Description."""
    road_desc = row.get(CDOT.ROAD_DESC, "").lower()

    if "at intersection" in road_desc:
        return "At Intersection"
    elif "intersection related" in road_desc:
        return "Intersection Related"
    elif "roundabout" in road_desc:
        return "Roundabout"
    elif "driveway" in road_desc:
        return "Driveway"
    elif "ramp" in road_desc:
        return "Ramp"
    else:
        return "Non-Intersection"


def map_collision_type(row):
    """Map CDOT Crash Type to standard collision types."""
    crash_type = row.get(CDOT.CRASH_TYPE, "").strip()

    # Direct mappings for common types
    type_map = {
        "Rear-End": "Rear End",
        "Sideswipe Same Direction": "Sideswipe - Same Direction",
        "Sideswipe Opposite Direction": "Sideswipe - Opposite Direction",
        "Broadside": "Angle",
        "Approach Turn": "Angle",
        "Overtaking Turn": "Angle",
        "Head-On": "Head On",
        "Backing": "Backed Into",
        "Parked Motor Vehicle": "Parked Vehicle",
        "Wild Animal": "Animal",
        "Domestic Animal": "Animal",
        "Pedestrian": "Pedestrian",
        "Bicycle": "Bicycle",
        "Overturning/Rollover": "Non-Collision",
    }

    # Check direct map first
    if crash_type in type_map:
        return type_map[crash_type]

    # Fixed object types
    fixed_objects = [
        "Guardrail", "Concrete", "Light Pole", "Sign", "Tree", "Fence",
        "Ditch", "Embankment", "Curb", "Bridge", "Wall", "Culvert",
        "Fire Hydrant", "Mail", "Utility", "Building", "Boulder"
    ]
    for obj in fixed_objects:
        if obj.lower() in crash_type.lower():
            return "Fixed Object"

    # Default
    return crash_type if crash_type else "Unknown"


def map_weather(row):
    """Map weather condition."""
    weather = row.get(CDOT.WEATHER, "").strip()
    weather2 = row.get(CDOT.WEATHER_2, "").strip()

    if weather:
        return weather
    elif weather2:
        return weather2
    return "Unknown"


def map_lighting(row):
    """Map lighting condition."""
    light = row.get(CDOT.LIGHTING, "").strip()

    # Normalize CDOT lighting values
    light_map = {
        "Daylight": "Daylight",
        "Dark – Lighted": "Dark - Lighted",
        "Dark – Unlighted": "Dark - Not Lighted",
        "Dawn or Dusk": "Dawn/Dusk",
    }

    return light_map.get(light, light) if light else "Unknown"


def map_road_surface(row):
    """Map road condition to surface condition."""
    condition = row.get(CDOT.ROAD_CONDITION, "").strip()
    return condition if condition else "Unknown"


def map_road_alignment(row):
    """Map road contour to alignment."""
    curves = row.get(CDOT.ROAD_CONTOUR_CURVES, "").strip()
    grade = row.get(CDOT.ROAD_CONTOUR_GRADE, "").strip()

    if curves and grade:
        return f"{curves}, {grade}"
    elif curves:
        return curves
    elif grade:
        return grade
    return "Unknown"


def get_jurisdiction(row):
    """Get jurisdiction from city or agency."""
    city = row.get(CDOT.CITY, "").strip()
    agency = row.get(CDOT.AGENCY_ID, "").strip()

    # Map agency codes to jurisdiction names
    agency_map = {
        "CSP": "Colorado State Patrol",
        "DSO": "Douglas County Sheriff",
        "PPD": "Parker",
        "CRPD": "Castle Rock",
        "LNTRPD": "Lone Tree",
        "LTPD": "Lone Tree",
        "AURPD": "Aurora",
    }

    if city:
        return city
    elif agency in agency_map:
        return agency_map[agency]
    return "Douglas County"


def process_row(row):
    """Process a single CDOT row and return tool-compatible row."""
    return {
        "Document Nbr": row.get(CDOT.CUID, "").strip().lstrip('\ufeff'),
        "Crash Year": extract_year(row.get(CDOT.CRASH_DATE, "")),
        "Crash Date": row.get(CDOT.CRASH_DATE, ""),
        "Crash Military Time": format_time(row.get(CDOT.CRASH_TIME, "")),
        "Crash Severity": derive_severity(row),
        "K_People": safe_int(row.get(CDOT.INJURY_04, 0)),
        "A_People": safe_int(row.get(CDOT.INJURY_03, 0)),
        "B_People": safe_int(row.get(CDOT.INJURY_02, 0)),
        "C_People": safe_int(row.get(CDOT.INJURY_01, 0)),
        "O_People": safe_int(row.get(CDOT.INJURY_00, 0)),
        "Collision Type": map_collision_type(row),
        "Weather Condition": map_weather(row),
        "Light Condition": map_lighting(row),
        "Roadway Surface Condition": map_road_surface(row),
        "Roadway Alignment": map_road_alignment(row),
        "Roadway Description": row.get(CDOT.ROAD_DESC, ""),
        "Intersection Type": is_intersection(row),
        "Traffic Control Type": "",  # Not available in CDOT data
        "Work Zone Related": "Y" if str(row.get(CDOT.CONSTRUCTION_ZONE, "")).upper() == "TRUE" else "N",
        "School Zone": "Y" if str(row.get(CDOT.SCHOOL_ZONE, "")).upper() == "TRUE" else "N",
        "Alcohol?": is_alcohol(row),
        "Bike?": is_bicycle(row),
        "Pedestrian?": is_pedestrian(row),
        "Speed?": is_speed_related(row),
        "Distracted?": is_distracted(row),
        "Hitrun?": is_hit_run(row),
        "Senior?": is_senior(row),
        "Young?": is_young(row),
        "Night?": is_night(row),
        "Unrestrained?": is_unrestrained(row),
        "Motorcycle?": is_motorcycle(row),
        "Drug Related?": is_drug_related(row),
        "RTE Name": build_route_name(row),
        "Node": build_node(row),
        "x": row.get(CDOT.LONGITUDE, ""),
        "y": row.get(CDOT.LATITUDE, ""),
        "Physical Juris Name": get_jurisdiction(row),
        "Agency": row.get(CDOT.AGENCY_ID, ""),
        "Total Vehicles": safe_int(row.get(CDOT.TOTAL_VEHICLES, 0)),
        "First Harmful Event": row.get(CDOT.FIRST_HE, ""),
    }


def main():
    """Main processing function."""
    print("=" * 60)
    print("CDOT to Crash Lens Data Converter")
    print("=" * 60)

    # Create output directory if needed
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Process all files
    all_rows = []
    stats = {
        "total": 0,
        "by_year": {},
        "by_severity": {"K": 0, "A": 0, "B": 0, "C": 0, "O": 0},
        "pedestrian": 0,
        "bicycle": 0,
        "motorcycle": 0,
        "alcohol": 0,
    }

    for filename in INPUT_FILES:
        filepath = INPUT_DIR / filename
        if not filepath.exists():
            print(f"WARNING: File not found: {filename}")
            continue

        print(f"\nProcessing: {filename}")

        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            file_count = 0

            for row in reader:
                processed = process_row(row)
                all_rows.append(processed)
                file_count += 1

                # Update stats
                year = processed["Crash Year"]
                sev = processed["Crash Severity"]

                stats["total"] += 1
                stats["by_year"][year] = stats["by_year"].get(year, 0) + 1
                stats["by_severity"][sev] = stats["by_severity"].get(sev, 0) + 1

                if processed["Pedestrian?"] == "Y":
                    stats["pedestrian"] += 1
                if processed["Bike?"] == "Y":
                    stats["bicycle"] += 1
                if processed["Motorcycle?"] == "Y":
                    stats["motorcycle"] += 1
                if processed["Alcohol?"] == "Y":
                    stats["alcohol"] += 1

            print(f"  Processed: {file_count:,} rows")

    # Write output file
    print(f"\nWriting output: {OUTPUT_FILE}")

    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)

    # Print summary
    print("\n" + "=" * 60)
    print("CONVERSION COMPLETE")
    print("=" * 60)
    print(f"\nTotal crashes processed: {stats['total']:,}")
    print(f"Output file: {OUTPUT_FILE}")
    print(f"File size: {OUTPUT_FILE.stat().st_size / 1024 / 1024:.2f} MB")

    print("\n--- Crashes by Year ---")
    for year in sorted(stats["by_year"].keys()):
        print(f"  {year}: {stats['by_year'][year]:,}")

    print("\n--- Crashes by Severity ---")
    for sev in ["K", "A", "B", "C", "O"]:
        print(f"  {sev}: {stats['by_severity'][sev]:,}")

    print("\n--- Special Categories ---")
    print(f"  Pedestrian: {stats['pedestrian']:,}")
    print(f"  Bicycle: {stats['bicycle']:,}")
    print(f"  Motorcycle: {stats['motorcycle']:,}")
    print(f"  Alcohol: {stats['alcohol']:,}")

    print("\n" + "=" * 60)
    print("Done!")


if __name__ == "__main__":
    main()
