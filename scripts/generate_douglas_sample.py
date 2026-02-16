#!/usr/bin/env python3
"""
Generate representative synthetic Douglas County crash data in VDOT-compatible format.

Creates 3 road-type CSV files matching the schema produced by the state_adapter +
fix_douglas_conversion pipeline.  Values use Henrico-style numbered prefixes so
the data loads identically to the real R2-hosted Douglas County datasets.

Output directory: data/CDOT/
Files produced:
  - douglas_all_roads.csv       (~500 crashes/month, 2021-2025)
  - douglas_county_roads.csv    (~220 crashes/month, 2021-2025)
  - douglas_no_interstate.csv   (~350 crashes/month, 2021-2025)
"""

import csv
import os
import random
from datetime import datetime, timedelta

random.seed(2025)

# Output directory
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "CDOT")

# ---------------------------------------------------------------------------
# Column schema — matches fix_douglas_conversion.py build_output_columns()
# ---------------------------------------------------------------------------
COLUMNS = [
    "Document Nbr", "Crash Date", "Crash Year", "Crash Military Time",
    "Crash Severity", "K_People", "A_People", "B_People", "C_People",
    "Collision Type", "Weather Condition", "Light Condition",
    "Roadway Surface Condition", "Roadway Alignment",
    "Roadway Description", "Intersection Type",
    "RTE Name", "SYSTEM", "Node", "RNS MP",
    "x", "y", "Physical Juris Name",
    "Pedestrian?", "Bike?", "Alcohol?", "Speed?", "Hitrun?",
    "Motorcycle?", "Night?", "Distracted?", "Drowsy?", "Drug Related?",
    "Young?", "Senior?", "Unrestrained?", "School Zone", "Work Zone Related",
    "Traffic Control Type", "Traffic Control Status",
    "Functional Class", "Area Type", "Facility Type", "Ownership",
    "First Harmful Event", "First Harmful Event Loc",
    "Relation To Roadway",
    "Vehicle Count", "Persons Injured", "Pedestrians Killed", "Pedestrians Injured",
    "_source_state", "_source_file",
]

# ---------------------------------------------------------------------------
# Douglas County route catalog (real road names from CDOT data)
# ---------------------------------------------------------------------------
DOUGLAS_ROUTES = {
    "county_roads": [
        # Castle Rock core
        "MEADOWS PKWY", "FOUNDERS PKWY", "PLUM CREEK PKWY",
        "CRYSTAL VALLEY PKWY", "WOLFENSBERGER RD", "GILBERT ST",
        "PERRY ST", "FRONT ST", "5TH ST", "CANTRIL ST",
        "CROWFOOT VALLEY RD", "LAGAE RD", "HAPPY CANYON RD",
        # Parker area
        "MAINSTREET", "PINE LN", "HESS RD", "HILLTOP RD",
        "CANTERBERRY CROSSING PKWY", "PINE DR", "PONDEROSA DR",
        # Highlands Ranch / Lone Tree
        "LINCOLN AVE", "RIDGE RD", "CASTLE PINES PKWY",
        "WILDCAT RESERVE PKWY", "PRAIRIE HAWK DR", "N MEADOWS DR",
        "MONARCH BLVD", "UNIVERSITY BLVD", "YOSEMITE ST",
        "QUEBEC ST", "HOLLY ST", "PARK MEADOWS DR",
        # Rural / western Douglas
        "TITAN RD", "TIMBER TRAIL RD", "LARK BUNTING DR",
        "DANIELS PARK RD", "RAMPART RANGE RD", "ROXBOROUGH PARK RD",
        "CHATFIELD AVE", "SANTA FE DR",
    ],
    "city_streets": [
        # Castle Rock town streets
        "ALLEN ST", "WILCOX ST", "3RD ST", "4TH ST",
        "ELBERT ST", "JERRY ST", "LEWIS ST", "SCOTT BLVD",
        # Parker town streets
        "PROGRESS WAY", "CHAMBERS WAY", "GATEWAY DR",
        # Lone Tree / Castle Pines
        "ACRES GREEN DR", "RidgeGate PKWY", "SKY RIDGE AVE",
        "HERITAGE HILLS CIR",
    ],
    "state_highways": [
        "S PARKER RD",       # CO-83
        "FRANKTOWN RD",      # CO-86
        "SEDALIA RD",        # CO-67
        "2ND ST",            # CO-105 through Castle Rock
        "CO-470",            # C-470 toll road
    ],
    "interstates": [
        "I-25",
    ],
}

# Map road category → SYSTEM value (Colorado road system codes)
SYSTEMS = {
    "county_roads": "County Road",
    "city_streets": "City Street",
    "state_highways": "State Highway",
    "interstates": "Interstate Highway",
}

# Map SYSTEM → Ownership (Henrico numbered-prefix)
OWNERSHIP = {
    "County Road": "2. County Hwy Agency",
    "City Street": "3. City or Town Hwy Agency",
    "State Highway": "1. State Hwy Agency",
    "Interstate Highway": "1. State Hwy Agency",
}

# Map SYSTEM → Roadway Description (Henrico numbered-prefix)
ROAD_DESC = {
    "County Road": "1. Two-Way, Not Divided",
    "City Street": "1. Two-Way, Not Divided",
    "State Highway": "2. Two-Way, Divided, Unprotected Median",
    "Interstate Highway": "3. Two-Way, Divided, Positive Median Barrier",
}

# ---------------------------------------------------------------------------
# Probability distributions (Colorado / Douglas County patterns)
# ---------------------------------------------------------------------------

# Severity — slightly higher O rate than Virginia (more PDO in Colorado)
SEVERITY_WEIGHTS = {"K": 0.006, "A": 0.030, "B": 0.10, "C": 0.18, "O": 0.684}

# Collision types (numbered-prefix Henrico format)
COLLISION_TYPES = {
    "1. Rear End": 0.28,
    "2. Angle": 0.18,
    "9. Fixed Object - Off Road": 0.14,
    "4. Sideswipe - Same Direction": 0.09,
    "3. Head On": 0.03,
    "12. Ped": 0.015,
    "13. Bicycle": 0.005,
    "10. Deer/Animal": 0.06,
    "8. Non-Collision": 0.06,
    "5. Sideswipe - Opposite Direction": 0.03,
    "11. Fixed Object in Road": 0.02,
    "16. Other": 0.07,
}

# Intersection types (numbered-prefix Henrico format)
INTERSECTION_TYPES = {
    "1. Not at Intersection": 0.52,
    "4. Four Approaches": 0.30,
    "2. Two Approaches": 0.08,
    "5. Roundabout": 0.04,
    "1. Not at Intersection (Ramp)": 0.06,
}

# Weather — Colorado: more snow, less rain than Virginia, blowing snow in winter
WEATHER = {
    "1. No Adverse Condition (Clear/Cloudy)": 0.72,
    "5. Rain": 0.07,
    "4. Snow": 0.10,
    "3. Fog/Smog/Smoke": 0.01,
    "6. Sleet/Hail/Freezing": 0.03,
    "7. Blowing Sand/Dust": 0.02,
    "8. Severe Crosswinds": 0.02,
    "": 0.03,
}

# Light conditions
LIGHT = {
    "2. Daylight": 0.62,
    "4. Darkness - Road Lighted": 0.16,
    "5. Darkness - Road Not Lighted": 0.10,
    "1. Dawn": 0.06,
    "3. Dusk": 0.06,
}

# Roadway surface (Colorado: more icy/snowy than Virginia)
SURFACE = {
    "1. Dry": 0.68,
    "2. Wet": 0.10,
    "3. Snow": 0.08,
    "5. Ice": 0.06,
    "4. Slush": 0.03,
    "6. Sand/Mud/Dirt/Oil/Gravel": 0.02,
    "16. Other": 0.01,
    "": 0.02,
}

# Roadway alignment
ALIGNMENT = {
    "1. Straight - Level": 0.65,
    "3. Grade - Straight": 0.18,
    "2. Curve - Level": 0.10,
    "4. Grade - Curve": 0.07,
}

# First Harmful Event (common ones, numbered-prefix)
FIRST_HARMFUL_EVENT = {
    "20. Motor Vehicle In Transport": 0.55,
    "9. Fixed Object - Off Road": 0.10,
    "30. Overturn (Rollover)": 0.06,
    "21. Animal": 0.06,
    "3. Utility Pole": 0.03,
    "2. Trees": 0.03,
    "5. Guard Rail": 0.03,
    "15. Concrete Traffic Barrier": 0.02,
    "19. Ped": 0.015,
    "22. Bicycle": 0.005,
    "14. Ditch": 0.02,
    "13. Embankment": 0.02,
    "27. Curb": 0.01,
    "4. Traffic Sign Support": 0.01,
    "24. Other Fixed Object": 0.02,
    "37. Other Object (Not Fixed)": 0.015,
    "38. Other Non-Collision": 0.015,
    "": 0.02,
}

# First Harmful Event Location
FIRST_HE_LOC = {
    "1. On Roadway": 0.60,
    "4. Roadside": 0.20,
    "2. Shoulder": 0.08,
    "3. Median": 0.06,
    "5. Gore": 0.02,
    "9. Outside Right-of-Way": 0.01,
    "": 0.03,
}

# Relation to Roadway
RELATION_TO_ROADWAY = {
    "8. Non-Intersection": 0.45,
    "9. Within Intersection": 0.28,
    "10. Intersection Related - Within 150 Feet": 0.10,
    "2. Acceleration/Deceleration Lanes": 0.05,
    "1. Main-Line Roadway": 0.08,
    "": 0.04,
}

# Seasonal pattern — Colorado: winter weather peaks, summer tourism
SEASONAL = {
    1: 0.90, 2: 0.85, 3: 0.95, 4: 1.00, 5: 1.05, 6: 1.10,
    7: 1.08, 8: 1.05, 9: 1.02, 10: 1.05, 11: 0.98, 12: 0.97,
}

# Douglas County bounding box (from jurisdictions.json)
BBOX = {
    "lon_min": -105.0543, "lon_max": -104.6014,
    "lat_min": 39.1298,   "lat_max": 39.5624,
}

# City clusters — weight coordinates toward populated areas
CITY_CLUSTERS = [
    {"name": "CASTLE ROCK",     "lat": 39.3722, "lon": -104.8561, "weight": 0.30},
    {"name": "PARKER",          "lat": 39.5186, "lon": -104.7614, "weight": 0.20},
    {"name": "LONE TREE",       "lat": 39.5397, "lon": -104.8863, "weight": 0.15},
    {"name": "HIGHLANDS RANCH", "lat": 39.5419, "lon": -104.9697, "weight": 0.15},
    {"name": "CASTLE PINES",    "lat": 39.4622, "lon": -104.8936, "weight": 0.10},
    {"name": "LARKSPUR",        "lat": 39.2225, "lon": -104.8858, "weight": 0.05},
    {"name": "SEDALIA",         "lat": 39.2869, "lon": -104.9642, "weight": 0.03},
    {"name": "ROXBOROUGH PARK", "lat": 39.4636, "lon": -105.0744, "weight": 0.02},
]


def weighted_choice(distribution):
    """Pick a random key from a {key: probability} dict."""
    keys = list(distribution.keys())
    weights = list(distribution.values())
    return random.choices(keys, weights=weights, k=1)[0]


def pick_coordinate():
    """Generate a coordinate clustered around Douglas County population centers."""
    cluster = random.choices(CITY_CLUSTERS,
                             weights=[c["weight"] for c in CITY_CLUSTERS],
                             k=1)[0]
    lat = round(cluster["lat"] + random.gauss(0, 0.025), 6)
    lon = round(cluster["lon"] + random.gauss(0, 0.03), 6)
    # Clamp to Douglas County bbox
    lat = max(BBOX["lat_min"], min(BBOX["lat_max"], lat))
    lon = max(BBOX["lon_min"], min(BBOX["lon_max"], lon))
    return lat, lon


def generate_crashes(road_types, monthly_base, years, output_path, source_file_label):
    """Generate synthetic crash records for Douglas County."""
    rows = []
    doc_counter = 500000  # Start above Henrico's range

    for year in years:
        for month in range(1, 13):
            # Skip future months in current year
            if year == 2025 and month > 12:
                continue

            # Monthly crash count with seasonality and year-over-year trend
            year_factor = 1.0 + (year - 2021) * 0.018  # slight upward trend
            n_crashes = int(monthly_base * SEASONAL[month] * year_factor
                           + random.gauss(0, monthly_base * 0.08))
            n_crashes = max(5, n_crashes)

            for _ in range(n_crashes):
                doc_counter += 1

                # Pick road category weighted by route count
                road_cat = weighted_choice(
                    {k: len(v) for k, v in road_types.items()}
                )
                route = random.choice(road_types[road_cat])
                system = SYSTEMS[road_cat]

                severity = weighted_choice(SEVERITY_WEIGHTS)
                collision = weighted_choice(COLLISION_TYPES)
                intersection = weighted_choice(INTERSECTION_TYPES)
                weather = weighted_choice(WEATHER)
                light = weighted_choice(LIGHT)
                surface = weighted_choice(SURFACE)
                alignment = weighted_choice(ALIGNMENT)
                fhe = weighted_choice(FIRST_HARMFUL_EVENT)
                fhe_loc = weighted_choice(FIRST_HE_LOC)
                rel_road = weighted_choice(RELATION_TO_ROADWAY)

                day = random.randint(1, 28)
                hour = random.randint(0, 23)
                minute = random.randint(0, 59)
                crash_date = f"{month}/{day}/{year}"
                crash_time = f"{hour:02d}{minute:02d}"

                # Coordinate clustered around population centers
                lat, lon = pick_coordinate()

                # Contributing factors (probabilistic)
                is_night = "Y" if light in ("4. Darkness - Road Lighted",
                                             "5. Darkness - Road Not Lighted") else "N"
                is_ped = "Y" if collision == "12. Ped" else "N"
                is_bike = "Y" if collision == "13. Bicycle" else "N"
                is_alcohol = "Y" if random.random() < 0.04 else "N"
                is_speed = "Y" if random.random() < 0.09 else "N"
                is_hitrun = "Y" if random.random() < 0.05 else "N"
                is_distracted = "Y" if random.random() < 0.14 else "N"
                is_drowsy = "Y" if random.random() < 0.02 else "N"
                is_drug = "Y" if random.random() < 0.04 else "N"  # Higher in CO
                is_young = "Y" if random.random() < 0.13 else "N"
                is_senior = "Y" if random.random() < 0.10 else "N"
                is_unrestrained = "Y" if random.random() < 0.04 else "N"
                is_motorcycle = "Y" if random.random() < 0.025 else "N"
                is_school = "N"
                is_workzone = "Y" if random.random() < 0.04 else "N"

                # Severity people counts
                k_ppl = 1 if severity == "K" else 0
                a_ppl = 1 if severity == "A" else 0
                b_ppl = 1 if severity == "B" else 0
                c_ppl = 1 if severity == "C" else 0

                # Vehicle count
                vehicle_count = 2 if collision.startswith(("1.", "2.", "3.", "4.", "5.")) \
                    else 1

                # Persons injured
                persons_injured = 0
                if severity in ("A", "B", "C"):
                    persons_injured = random.choice([1, 1, 1, 2])

                # Pedestrian killed/injured
                ped_killed = 0
                ped_injured = 0
                if is_ped == "Y":
                    if severity == "K":
                        ped_killed = 1
                    elif severity in ("A", "B", "C"):
                        ped_injured = 1

                # Node (intersection ID) — sorted pair of road names
                node = ""
                if "Intersection" in intersection or intersection == "4. Four Approaches":
                    cross_pool = list(road_types.get("county_roads", []))
                    if not cross_pool:
                        cross_pool = list(road_types.get("city_streets", ["MAIN ST"]))
                    cross = random.choice(cross_pool)
                    roads = sorted([route, cross])
                    node = f"{roads[0]} & {roads[1]}"

                row = {
                    "Document Nbr": str(doc_counter),
                    "Crash Date": crash_date,
                    "Crash Year": str(year),
                    "Crash Military Time": crash_time,
                    "Crash Severity": severity,
                    "K_People": k_ppl,
                    "A_People": a_ppl,
                    "B_People": b_ppl,
                    "C_People": c_ppl,
                    "Collision Type": collision,
                    "Weather Condition": weather,
                    "Light Condition": light,
                    "Roadway Surface Condition": surface,
                    "Roadway Alignment": alignment,
                    "Roadway Description": ROAD_DESC.get(system, "1. Two-Way, Not Divided"),
                    "Intersection Type": intersection,
                    "RTE Name": route,
                    "SYSTEM": system,
                    "Node": node,
                    "RNS MP": "",
                    "x": lon,
                    "y": lat,
                    "Physical Juris Name": "DOUGLAS",
                    "Pedestrian?": is_ped,
                    "Bike?": is_bike,
                    "Alcohol?": is_alcohol,
                    "Speed?": is_speed,
                    "Hitrun?": is_hitrun,
                    "Motorcycle?": is_motorcycle,
                    "Night?": is_night,
                    "Distracted?": is_distracted,
                    "Drowsy?": is_drowsy,
                    "Drug Related?": is_drug,
                    "Young?": is_young,
                    "Senior?": is_senior,
                    "Unrestrained?": is_unrestrained,
                    "School Zone": is_school,
                    "Work Zone Related": is_workzone,
                    "Functional Class": "",
                    "Area Type": "",
                    "Facility Type": "",
                    "Ownership": OWNERSHIP.get(system, ""),
                    "Traffic Control Type": "",
                    "Traffic Control Status": "",
                    "First Harmful Event": fhe,
                    "First Harmful Event Loc": fhe_loc,
                    "Relation To Roadway": rel_road,
                    "Vehicle Count": vehicle_count,
                    "Persons Injured": persons_injured,
                    "Pedestrians Killed": ped_killed,
                    "Pedestrians Injured": ped_injured,
                    "_source_state": "colorado",
                    "_source_file": source_file_label,
                }
                rows.append(row)

    # Write CSV
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Written {len(rows):,} records to {output_path}")
    return len(rows)


def main():
    print("=" * 60)
    print("  Generating synthetic Douglas County crash data")
    print("  Format: VDOT-compatible (numbered-prefix, post-pipeline)")
    print("  State: Colorado | Jurisdiction: Douglas County")
    print("=" * 60)

    years = list(range(2021, 2026))  # 2021-2025

    # 1. County roads only (County Road + City Street, ~220 crashes/month)
    county_routes = {
        "county_roads": DOUGLAS_ROUTES["county_roads"],
        "city_streets": DOUGLAS_ROUTES["city_streets"],
    }
    path = os.path.join(DATA_DIR, "douglas_county_roads.csv")
    n = generate_crashes(county_routes, 220, years, path, "sample_county_roads")
    print(f"\n  county_roads: {n:,} records")

    # 2. No interstate (county + city + state highways, ~350 crashes/month)
    no_int_routes = {
        "county_roads": DOUGLAS_ROUTES["county_roads"],
        "city_streets": DOUGLAS_ROUTES["city_streets"],
        "state_highways": DOUGLAS_ROUTES["state_highways"],
    }
    path = os.path.join(DATA_DIR, "douglas_no_interstate.csv")
    n = generate_crashes(no_int_routes, 350, years, path, "sample_no_interstate")
    print(f"  no_interstate: {n:,} records")

    # 3. All roads (all categories including I-25, ~500 crashes/month)
    all_routes = {
        "county_roads": DOUGLAS_ROUTES["county_roads"],
        "city_streets": DOUGLAS_ROUTES["city_streets"],
        "state_highways": DOUGLAS_ROUTES["state_highways"],
        "interstates": DOUGLAS_ROUTES["interstates"],
    }
    path = os.path.join(DATA_DIR, "douglas_all_roads.csv")
    n = generate_crashes(all_routes, 500, years, path, "sample_all_roads")
    print(f"  all_roads: {n:,} records")

    print("\n" + "=" * 60)
    print("  Done! Data files are ready for forecast generation.")
    print(f"  Output directory: {DATA_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
