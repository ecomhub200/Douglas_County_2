#!/usr/bin/env python3
"""
Ranking Validation Step (Stage 2.5) — FIPS Resolution + Enrichment + Rankings

Runs AFTER road-type splitting (Stage 2) and BEFORE aggregation (Stage 3).
Three phases:

  Phase 0 — FIPS Resolution (offline, using local Census geography data):
    Compute jurisdiction centroids from crash lat/lon, match to nearest
    county in states/geography/us_counties.json via haversine distance.
    Also resolves Place FIPS from us_places.json for cities/towns.
    NO external API calls — all data is local.

  Phase A — Enrich:
    Add 5 geographic columns: FIPS, Place FIPS, {DOT} District,
    Planning District, MPO Name

  Phase B — Rank:
    Compute 20 ranking columns (4 scopes × 5 metrics) for crash
    severity/frequency. Rankings computed on all_roads, applied to
    all road-type variants.

Usage:
    # Full run (statewide)
    python scripts/ranking_validation.py \\
        --state virginia --data-dir data/VirginiaDOT

    # Specific jurisdictions
    python scripts/ranking_validation.py \\
        --state virginia --data-dir data/VirginiaDOT \\
        --jurisdictions henrico chesterfield fairfax_county

    # Dry run (report only, no file changes)
    python scripts/ranking_validation.py \\
        --state virginia --data-dir data/VirginiaDOT --dry-run

    # Force recompute (overwrite existing ranking columns)
    python scripts/ranking_validation.py \\
        --state virginia --data-dir data/VirginiaDOT --force

Exit codes:
    0 = success
    1 = partial failure (some jurisdictions failed)
    2 = fatal error (missing config, no data)
"""

import argparse
import csv
import json
import logging
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("ranking_validation")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

# ─── Paths ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
STATES_DIR = ROOT / "states"
GEO_DIR = STATES_DIR / "geography"

# ─── Constants ────────────────────────────────────────────────────────────────

ROAD_TYPES = ["all_roads", "no_interstate", "county_roads", "city_roads"]

# 5 crash metrics to rank by
METRIC_NAMES = [
    "total_crash",
    "total_ped_crash",
    "total_bike_crash",
    "total_fatal",
    "total_fatal_serious_injury",
]

# 4 geographic scopes for ranking → 4 × 5 = 20 ranking columns
RANKING_SCOPES = ["District", "Juris", "PlanningDistrict", "MPO"]

# Boolean-ish truthy values in crash data
_TRUTHY = {"Y", "YES", "1", "TRUE", "True", "true"}

# ─── Geography data loaders (cached) ─────────────────────────────────────────

_counties_cache = None
_places_cache = None


def _load_geo_records(filename):
    """Load records from a states/geography/ JSON file."""
    path = GEO_DIR / filename
    if not path.exists():
        logger.warning(f"Geography file not found: {path}")
        return []
    with open(path) as f:
        data = json.load(f)
    return data.get("records", data if isinstance(data, list) else [])


def load_counties_for_state(state_fips):
    """Load county records for a single state, indexed by COUNTY FIPS (3-digit)."""
    global _counties_cache
    if _counties_cache is None:
        _counties_cache = {}
        for rec in _load_geo_records("us_counties.json"):
            sf = rec.get("STATE", "")
            if sf:
                _counties_cache.setdefault(sf, []).append(rec)
    return _counties_cache.get(state_fips, [])


def load_places_for_state(state_fips):
    """Load place records for a single state."""
    global _places_cache
    if _places_cache is None:
        _places_cache = {}
        for rec in _load_geo_records("us_places.json"):
            sf = rec.get("STATE", "")
            if sf:
                _places_cache.setdefault(sf, []).append(rec)
    return _places_cache.get(state_fips, [])


# ─── Utility ──────────────────────────────────────────────────────────────────


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(min(1.0, math.sqrt(a)))


def county_name_to_key(name):
    """Convert display name to snake_case key (matches aggregate_by_scope.py)."""
    key = name.lower().strip()
    key = key.replace("'", "").replace(".", "")
    key = re.sub(r"[^a-z0-9]+", "_", key)
    return key.strip("_")


def load_hierarchy(state):
    """Load states/{state}/hierarchy.json."""
    path = STATES_DIR / state / "hierarchy.json"
    if not path.exists():
        logger.error(f"No hierarchy.json for '{state}' at {path}")
        sys.exit(2)
    with open(path) as f:
        return json.load(f)


# ─── Phase 0: FIPS Resolution (offline — local geography data) ───────────────


def compute_jurisdiction_centroids(rows, juris_col="Physical Juris Name"):
    """
    Group crash rows by jurisdiction, compute median lat/lon for each.

    Uses MEDIAN (not MEAN) to be robust against outlier coordinates.
    Returns: {juris_name: (median_lat, median_lon)}
    """
    coords = defaultdict(lambda: ([], []))  # juris → (lats, lons)

    for row in rows:
        juris = row.get(juris_col, "").strip()
        if not juris:
            continue
        try:
            lon = float(row.get("x", 0))
            lat = float(row.get("y", 0))
            if lon != 0 and lat != 0 and -180 <= lon <= 180 and -90 <= lat <= 90:
                coords[juris][0].append(lat)
                coords[juris][1].append(lon)
        except (ValueError, TypeError):
            continue

    centroids = {}
    for juris, (lats, lons) in coords.items():
        if lats:
            lats.sort()
            lons.sort()
            centroids[juris] = (lats[len(lats) // 2], lons[len(lons) // 2])

    return centroids


def resolve_fips_from_geography(centroids, state_fips):
    """
    Match each jurisdiction centroid to the nearest county in us_counties.json
    using haversine distance. Also resolve Place FIPS from us_places.json.

    Returns: {juris_name: {
        county_fips, state_fips, county_geoid, county_name, county_basename,
        place_fips, place_name, place_type, distance_km, source
    }}
    """
    counties = load_counties_for_state(state_fips)
    places = load_places_for_state(state_fips)

    # Pre-parse county coordinates
    county_coords = []
    for rec in counties:
        try:
            clat = float(rec.get("INTPTLAT", 0))
            clon = float(rec.get("INTPTLON", 0))
            if clat and clon:
                county_coords.append((clat, clon, rec))
        except (ValueError, TypeError):
            continue

    # Pre-parse place coordinates
    place_coords = []
    for rec in places:
        try:
            plat = float(rec.get("INTPTLAT", 0))
            plon = float(rec.get("INTPTLON", 0))
            if plat and plon:
                place_coords.append((plat, plon, rec))
        except (ValueError, TypeError):
            continue

    results = {}
    for juris_name, (jlat, jlon) in centroids.items():
        # Find nearest county
        best_county = None
        best_dist = float("inf")
        for clat, clon, rec in county_coords:
            dist = haversine_km(jlat, jlon, clat, clon)
            if dist < best_dist:
                best_dist = dist
                best_county = rec

        result = {
            "county_fips": "",
            "state_fips": state_fips,
            "county_geoid": "",
            "county_name": "",
            "county_basename": "",
            "place_fips": None,
            "place_name": None,
            "place_type": None,
            "distance_km": round(best_dist, 2) if best_county else None,
            "centroid": [jlat, jlon],
            "source": "geography_file",
        }

        if best_county:
            result["county_fips"] = best_county.get("COUNTY", "")
            result["county_geoid"] = best_county.get("GEOID", "")
            result["county_name"] = best_county.get("NAME", "")
            result["county_basename"] = best_county.get("BASENAME", "")

            if best_dist > 50:
                logger.warning(
                    f"    {juris_name}: nearest county is {best_dist:.1f}km away "
                    f"({best_county.get('NAME', '')})"
                )

        # Find nearest place (city/town) within 15km
        best_place = None
        best_place_dist = float("inf")
        for plat, plon, rec in place_coords:
            dist = haversine_km(jlat, jlon, plat, plon)
            if dist < best_place_dist:
                best_place_dist = dist
                best_place = rec

        if best_place and best_place_dist < 15:
            result["place_fips"] = best_place.get("PLACE", "")
            result["place_name"] = best_place.get("NAME", "")
            result["place_type"] = best_place.get("LSADC", "")

        results[juris_name] = result

    return results


def build_fips_lookup(geo_results, hierarchy):
    """
    Build definitive FIPS + hierarchy lookup table.

    For each jurisdiction:
      1. FIPS from geography resolution (authoritative)
      2. District from hierarchy regions (by FIPS membership)
      3. MPO from hierarchy tprs (by FIPS membership)
      4. Planning District from hierarchy planningDistricts (by FIPS membership)

    Returns: {juris_name: {fips, region_key, region_name, mpo_key, mpo_name, ...}}
    """
    state_info = hierarchy.get("state", {})
    regions = hierarchy.get("regions", {})
    tprs = hierarchy.get("tprs", {})
    planning_districts = hierarchy.get("planningDistricts", {})

    # Build reverse indexes: FIPS → region/mpo/pd keys
    fips_to_regions = defaultdict(list)
    for rkey, rdata in regions.items():
        for fips in rdata.get("counties", []):
            fips_to_regions[fips].append(rkey)

    fips_to_mpos = defaultdict(list)
    for mkey, mdata in tprs.items():
        for fips in mdata.get("counties", []):
            fips_to_mpos[fips].append(mkey)

    fips_to_pds = defaultdict(list)
    for pkey, pdata in planning_districts.items():
        for fips in pdata.get("counties", []):
            fips_to_pds[fips].append(pkey)

    lookup = {}
    conflicts = []

    for juris_name, geo in geo_results.items():
        fips = geo.get("county_fips", "")

        entry = {
            "juris_name": juris_name,
            "fips": fips,
            "state_fips": geo.get("state_fips", ""),
            "county_geoid": geo.get("county_geoid", ""),
            "county_name": geo.get("county_name", ""),
            "place_fips": geo.get("place_fips"),
            "place_name": geo.get("place_name"),
            "region_key": None,
            "region_name": "",
            "planning_district_key": None,
            "planning_district_name": "",
            "mpo_key": None,
            "mpo_name": "",
            "fips_source": geo.get("source", "unknown"),
            "distance_km": geo.get("distance_km"),
            "conflicts": [],
        }

        if not fips:
            lookup[juris_name] = entry
            continue

        # Region lookup
        rkeys = fips_to_regions.get(fips, [])
        if len(rkeys) > 1:
            msg = f"DUPLICATE: FIPS {fips} ({juris_name}) in regions {rkeys}"
            entry["conflicts"].append(msg)
            conflicts.append(msg)
            logger.warning(f"    {msg}")
            # Use first region as default
            entry["region_key"] = rkeys[0]
            entry["region_name"] = regions[rkeys[0]].get("name", "")
        elif rkeys:
            entry["region_key"] = rkeys[0]
            entry["region_name"] = regions[rkeys[0]].get("name", "")
        else:
            entry["region_key"] = "_unassigned"

        # MPO lookup
        mkeys = fips_to_mpos.get(fips, [])
        if mkeys:
            entry["mpo_key"] = mkeys[0]
            entry["mpo_name"] = tprs[mkeys[0]].get("name", "")

        # Planning District lookup
        pkeys = fips_to_pds.get(fips, [])
        if pkeys:
            entry["planning_district_key"] = pkeys[0]
            entry["planning_district_name"] = planning_districts[pkeys[0]].get(
                "name", ""
            )

        lookup[juris_name] = entry

    return lookup, conflicts


def save_validation_report(lookup_table, conflicts, state, output_dir):
    """Save hierarchy_validation_report.json."""
    total = len(lookup_table)
    resolved = sum(1 for v in lookup_table.values() if v.get("fips"))
    place_count = sum(1 for v in lookup_table.values() if v.get("place_fips"))

    duplicates = [c for c in conflicts if "DUPLICATE" in c]
    orphans = [
        v["juris_name"]
        for v in lookup_table.values()
        if v.get("region_key") == "_unassigned" and v.get("fips")
    ]

    report = {
        "state": state,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fips_resolution": {
            "total_jurisdictions": total,
            "resolved": resolved,
            "unresolved": total - resolved,
            "source": "states/geography/us_counties.json (offline)",
        },
        "hierarchy_conflicts": {
            "duplicates_found": len(duplicates),
            "duplicate_details": duplicates,
            "orphans_found": len(orphans),
            "orphan_jurisdictions": orphans,
        },
        "place_fips_coverage": {
            "jurisdictions_with_place_fips": place_count,
            "jurisdictions_without": total - place_count,
            "note": "Independent cities and towns have place FIPS; counties do not",
        },
        "distance_stats": {
            "max_distance_km": max(
                (v.get("distance_km", 0) or 0 for v in lookup_table.values()),
                default=0,
            ),
            "avg_distance_km": round(
                sum(v.get("distance_km", 0) or 0 for v in lookup_table.values())
                / max(total, 1),
                2,
            ),
        },
    }

    report_path = Path(output_dir) / "hierarchy_validation_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"  Saved: {report_path}")


# ─── Phase A: Enrich crash data ──────────────────────────────────────────────


def enrich_rows(headers, rows, lookup_table, dot_abbrev, force=False):
    """
    Add 5 geographic columns to crash rows.

    Columns: FIPS, Place FIPS, {DOT} District, Planning District, MPO Name
    Only fills MISSING or EMPTY values — never overwrites existing data
    (unless --force).

    Returns: (new_headers, enriched_rows)
    """
    district_col = f"{dot_abbrev} District"
    new_cols = ["FIPS", "Place FIPS", district_col, "Planning District", "MPO Name"]

    # Check if already enriched
    if not force:
        existing = [c for c in new_cols if c in headers]
        if len(existing) == len(new_cols):
            # Check if FIPS is actually populated
            sample = rows[:100] if rows else []
            populated = sum(1 for r in sample if r.get("FIPS", "").strip())
            if populated > len(sample) * 0.5:
                return headers, rows  # Already enriched

    new_headers = list(headers)
    for col in new_cols:
        if col not in new_headers:
            new_headers.append(col)

    enriched = []
    for row in rows:
        nr = dict(row)
        juris = row.get("Physical Juris Name", "").strip()
        entry = lookup_table.get(juris, {})

        # FIPS — always write (new column)
        if force or not nr.get("FIPS", "").strip():
            nr["FIPS"] = entry.get("fips", "")

        # Place FIPS
        if force or not nr.get("Place FIPS", "").strip():
            nr["Place FIPS"] = entry.get("place_fips") or ""

        # District
        if force or not nr.get(district_col, "").strip():
            nr[district_col] = entry.get("region_name", "")

        # Planning District
        if force or not nr.get("Planning District", "").strip():
            nr["Planning District"] = entry.get("planning_district_name", "")

        # MPO Name
        if force or not nr.get("MPO Name", "").strip():
            nr["MPO Name"] = entry.get("mpo_name", "")

        enriched.append(nr)

    return new_headers, enriched


# ─── Phase B: Compute Rankings ────────────────────────────────────────────────


def compute_metrics_by_fips(rows):
    """
    Compute 5 crash metrics grouped by FIPS.

    Returns: {fips: {total_crash: N, total_ped_crash: N, ...}}
    """
    by_fips = defaultdict(list)
    for row in rows:
        fips = row.get("FIPS", "").strip()
        if fips:
            by_fips[fips].append(row)

    metrics = {}
    for fips, fips_rows in by_fips.items():
        metrics[fips] = {
            "total_crash": len(fips_rows),
            "total_ped_crash": sum(
                1 for r in fips_rows if r.get("Pedestrian?", "") in _TRUTHY
            ),
            "total_bike_crash": sum(
                1 for r in fips_rows if r.get("Bike?", "") in _TRUTHY
            ),
            "total_fatal": sum(
                1 for r in fips_rows if r.get("Crash Severity", "").upper() == "K"
            ),
            "total_fatal_serious_injury": sum(
                1
                for r in fips_rows
                if r.get("Crash Severity", "").upper() in ("K", "A")
            ),
        }

    return metrics


def rank_within_scope(metrics, lookup_table, scope):
    """
    Rank jurisdictions within a scope.

    scope = 'District'         → group by region_key, rank within each
    scope = 'Juris'            → rank all jurisdictions statewide
    scope = 'PlanningDistrict' → group by planning_district_key
    scope = 'MPO'              → group by mpo_key

    Rank 1 = HIGHEST crash count (most crashes = rank 1).
    Ties: method='min' (both get rank 2, next gets rank 4).

    Returns: {fips: {'{scope}_Rank_total_crash': N, ...}}
    """
    # Build FIPS → scope group mapping
    fips_to_group = {}
    for entry in lookup_table.values():
        fips = entry.get("fips", "")
        if not fips:
            continue

        if scope == "District":
            group = entry.get("region_key", "")
        elif scope == "Juris":
            group = "_statewide"
        elif scope == "PlanningDistrict":
            group = entry.get("planning_district_key", "")
        elif scope == "MPO":
            group = entry.get("mpo_key", "")
        else:
            group = ""

        if group and group != "_unassigned":
            fips_to_group[fips] = group

    # Group FIPS by scope
    groups = defaultdict(list)
    for fips, group in fips_to_group.items():
        if fips in metrics:
            groups[group].append(fips)

    # Rank within each group
    ranks = {}
    for group_key, fips_list in groups.items():
        for metric_name in METRIC_NAMES:
            # Sort descending (highest count = rank 1)
            sorted_fips = sorted(
                fips_list,
                key=lambda f: metrics.get(f, {}).get(metric_name, 0),
                reverse=True,
            )

            # Assign ranks with min-tie method
            prev_val = None
            prev_rank = 0
            for i, fips in enumerate(sorted_fips, 1):
                val = metrics.get(fips, {}).get(metric_name, 0)
                if val != prev_val:
                    prev_rank = i
                    prev_val = val

                ranks.setdefault(fips, {})[f"{scope}_Rank_{metric_name}"] = prev_rank

    return ranks


def compute_all_rankings(rows, lookup_table):
    """
    Compute all 20 ranking columns (4 scopes × 5 metrics).

    Rankings are computed on ALL rows (all_roads), then the same rank values
    are applied to all road-type variants to ensure consistency.

    Returns: {fips: {col_name: rank_value, ...}}
    """
    metrics = compute_metrics_by_fips(rows)

    all_ranks = {}
    active_scopes = []

    for scope in RANKING_SCOPES:
        scope_ranks = rank_within_scope(metrics, lookup_table, scope)
        if scope_ranks:
            active_scopes.append(scope)
            for fips, rank_dict in scope_ranks.items():
                all_ranks.setdefault(fips, {}).update(rank_dict)
        else:
            logger.info(f"    {scope} scope: skipped (not configured or no data)")

    logger.info(f"    Active scopes: {', '.join(active_scopes)}")
    return all_ranks, metrics


def add_rankings_to_rows(headers, rows, all_ranks, force=False):
    """
    Add 20 ranking columns to rows. Returns: (new_headers, ranked_rows).
    """
    # Build column names
    rank_cols = []
    for scope in RANKING_SCOPES:
        for metric in METRIC_NAMES:
            rank_cols.append(f"{scope}_Rank_{metric}")

    # Check if already ranked
    if not force:
        existing = [c for c in rank_cols if c in headers]
        if len(existing) == len(rank_cols):
            sample = rows[:100] if rows else []
            populated = sum(
                1
                for r in sample
                if r.get("Juris_Rank_total_crash", "").strip()
            )
            if populated > len(sample) * 0.5:
                return headers, rows  # Already ranked

    new_headers = list(headers)
    for col in rank_cols:
        if col not in new_headers:
            new_headers.append(col)

    ranked = []
    for row in rows:
        nr = dict(row)
        fips = nr.get("FIPS", "").strip()
        fips_ranks = all_ranks.get(fips, {})

        for col in rank_cols:
            if force or not nr.get(col, "").strip():
                val = fips_ranks.get(col, "")
                nr[col] = str(val) if val != "" else ""

        ranked.append(nr)

    return new_headers, ranked


# ─── CSV I/O ─────────────────────────────────────────────────────────────────


def read_csv(path):
    """Read CSV, return (headers, rows_as_dicts)."""
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)
    return headers, rows


def write_csv(path, headers, rows):
    """Write CSV from headers and row dicts."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ─── Main orchestrator ────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Stage 2.5: Ranking Validation & Enrichment"
    )
    parser.add_argument(
        "--state", required=True, help="State directory name (virginia, colorado, etc.)"
    )
    parser.add_argument(
        "--data-dir", required=True, help="Directory with jurisdiction CSVs"
    )
    parser.add_argument(
        "--jurisdictions", nargs="+", help="Specific jurisdictions (auto-detect if omitted)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Report only, no file changes"
    )
    parser.add_argument(
        "--force", action="store_true", help="Force recompute even if columns exist"
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        sys.exit(2)

    # ── Load hierarchy ──
    hierarchy = load_hierarchy(args.state)
    state_info = hierarchy.get("state", {})
    state_fips = state_info.get("fips", "")
    dot_abbrev = state_info.get("dot", "DOT")
    state_name = state_info.get("name", args.state)

    if not state_fips:
        logger.error(f"No state FIPS in hierarchy.json for {args.state}")
        sys.exit(2)

    print("=" * 60)
    print(f"  Stage 2.5: Ranking Validation & Enrichment")
    print(f"  State: {state_name} ({dot_abbrev}) | FIPS: {state_fips}")
    print("=" * 60)

    # ── Discover jurisdictions ──
    if args.jurisdictions:
        jurisdictions = args.jurisdictions
    else:
        jurisdictions = sorted(
            {p.stem.replace("_all_roads", "") for p in data_dir.glob("*_all_roads.csv")}
        )

    if not jurisdictions:
        logger.warning("No jurisdiction CSVs found — nothing to process")
        sys.exit(0)

    logger.info(f"  Jurisdictions: {len(jurisdictions)}")

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 0: FIPS Resolution (offline — local geography data)
    # ══════════════════════════════════════════════════════════════════════════

    print("\n── Phase 0: FIPS Resolution ──")

    # Read ALL all_roads rows to compute centroids
    logger.info("  Reading crash data for centroid computation...")
    all_rows = []
    rows_by_juris = {}
    for juris in jurisdictions:
        path = data_dir / f"{juris}_all_roads.csv"
        if not path.exists():
            logger.warning(f"    {juris}_all_roads.csv not found — skipping")
            continue
        _, rows = read_csv(path)
        all_rows.extend(rows)
        rows_by_juris[juris] = rows

    if not all_rows:
        logger.error("  No crash data loaded — aborting")
        sys.exit(2)

    logger.info(f"  Loaded {len(all_rows):,} rows from {len(rows_by_juris)} jurisdictions")

    # Compute centroids
    logger.info("  Computing jurisdiction centroids...")
    centroids = compute_jurisdiction_centroids(all_rows)
    logger.info(f"    {len(centroids)} centroids computed")

    # Resolve FIPS from local geography data
    logger.info("  Resolving FIPS from states/geography/us_counties.json...")
    geo_results = resolve_fips_from_geography(centroids, state_fips)

    resolved = sum(1 for v in geo_results.values() if v.get("county_fips"))
    place_count = sum(1 for v in geo_results.values() if v.get("place_fips"))
    logger.info(f"    County FIPS resolved: {resolved}/{len(centroids)}")
    logger.info(f"    Place FIPS resolved:  {place_count}")

    # Build lookup table
    logger.info("  Building definitive FIPS + hierarchy lookup...")
    lookup_table, conflicts = build_fips_lookup(geo_results, hierarchy)

    orphan_count = sum(
        1 for v in lookup_table.values()
        if v.get("region_key") == "_unassigned" and v.get("fips")
    )
    if orphan_count:
        logger.info(f"    Orphaned jurisdictions (no region): {orphan_count}")
    if conflicts:
        logger.info(f"    Hierarchy conflicts: {len(conflicts)}")

    # Save validation report
    save_validation_report(lookup_table, conflicts, args.state, data_dir)

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE A + B: Enrich + Rank
    # ══════════════════════════════════════════════════════════════════════════

    print(f"\n── Phase A: Enrich + Phase B: Rank ──")

    # Phase B: Compute rankings on all_roads FIRST (need enriched FIPS column)
    # We need to enrich all_rows first to get FIPS, then compute rankings
    logger.info("  Enriching all_roads data with FIPS...")
    dummy_headers = list(all_rows[0].keys()) if all_rows else []
    _, enriched_all = enrich_rows(
        dummy_headers, all_rows, lookup_table, dot_abbrev, force=True
    )

    logger.info("  Computing rankings on all_roads...")
    all_ranks, metrics = compute_all_rankings(enriched_all, lookup_table)

    # Log top 5
    if metrics:
        sorted_by_total = sorted(
            metrics.items(), key=lambda x: x[1].get("total_crash", 0), reverse=True
        )[:5]
        if sorted_by_total:
            logger.info("  Top 5 — Juris_Rank_total_crash:")
            for i, (fips, m) in enumerate(sorted_by_total, 1):
                name = next(
                    (
                        v["county_name"]
                        for v in lookup_table.values()
                        if v.get("fips") == fips
                    ),
                    fips,
                )
                logger.info(f"    {i}. {name} ({fips}): {m['total_crash']:,}")

    # Process each jurisdiction × each road type
    logger.info(
        f"  Processing {len(jurisdictions)} jurisdictions × {len(ROAD_TYPES)} road types..."
    )
    success = 0
    skipped = 0
    total_files = 0

    for juris in jurisdictions:
        juris_ok = True

        for road_type in ROAD_TYPES:
            csv_path = data_dir / f"{juris}_{road_type}.csv"
            if not csv_path.exists():
                continue

            total_files += 1
            headers, rows = read_csv(csv_path)

            # Phase A: Enrich
            headers, rows = enrich_rows(
                headers, rows, lookup_table, dot_abbrev, force=args.force
            )

            # Phase B: Add rankings (same ranks for all road types)
            headers, rows = add_rankings_to_rows(
                headers, rows, all_ranks, force=args.force
            )

            if not args.dry_run:
                write_csv(csv_path, headers, rows)

        if juris_ok:
            success += 1
        else:
            skipped += 1

    action = "Would write" if args.dry_run else "Wrote"
    logger.info(f"  {action} 25 new columns to {total_files} CSV files")
    logger.info(f"  Jurisdictions: {success} ok, {skipped} skipped")

    # ── Summary ──
    print(f"\n{'=' * 60}")
    print(f"  Stage 2.5 Complete {'(DRY RUN)' if args.dry_run else ''}")
    print(f"  25 new columns per crash row:")
    print(f"    2 FIPS columns  (FIPS, Place FIPS)")
    print(f"    3 hierarchy     ({dot_abbrev} District, Planning District, MPO Name)")
    print(f"    20 rankings     (4 scopes × 5 metrics)")
    print(f"  Files processed: {total_files}")
    print(f"{'=' * 60}")

    return 0 if skipped == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
