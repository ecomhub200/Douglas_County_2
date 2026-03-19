#!/usr/bin/env python3
"""
Download comprehensive US geographic/administrative data from federal APIs.

Data sources:
  1. Census TIGERweb API — States, counties, incorporated places (cities/towns/villages)
  2. BTS/USDOT — Metropolitan Planning Organizations (MPO boundaries + member counties)
  3. Census County Subdivisions — Minor Civil Divisions (towns in New England, townships, etc.)

Outputs (all saved to data/geographic/):
  - us_states.json          — All 50 states + DC with FIPS, centroid, bbox
  - us_counties.json        — All 3,200+ counties with FIPS, centroid, bbox, LSAD
  - us_places.json          — All 30,000+ incorporated places (cities/towns/CDPs) with FIPS, centroid, type
  - us_mpos.json            — All ~400 MPOs with name, member counties, centroid, bbox
  - us_county_subdivisions.json — County subdivisions (MCDs/townships) with FIPS, centroid

Usage:
    python scripts/download_geographic_data.py
    python scripts/download_geographic_data.py --layer counties
    python scripts/download_geographic_data.py --layer mpos
    python scripts/download_geographic_data.py --state 51    # Virginia only

Requires: requests (pip install requests)
"""

import json
import time
import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone

# ─── ArcGIS REST API helpers ────────────────────────────────────────────────

# Census TIGERweb endpoints (ordered by preference)
# The Census Bureau periodically retires vintage services, so we try multiple.
TIGER_SERVICES = [
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Current/MapServer",
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer",
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2024/MapServer",
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2023/MapServer",
]
TIGER_BASE = None  # Resolved dynamically at startup

# Layer name → expected ArcGIS layer names (for dynamic lookup)
TIGER_LAYER_NAMES = {
    "states": ["States", "Census States"],
    "counties": ["Counties", "Census Counties"],
    "places": ["Places", "Incorporated Places", "Census Places"],
    "county_subdivisions": ["County Subdivisions", "Census County Subdivisions"],
}

# Fallback layer IDs (last known good — used only if dynamic lookup fails)
TIGER_LAYERS_FALLBACK = {
    "states": [80, 54, 82, 84, 86, 88, 90],
    "counties": [82, 86, 100, 102],
    "places": [28, 30, 150, 152],
    "county_subdivisions": [30, 32, 160, 162],
}

# BTS/USDOT National Transportation Atlas — MPO boundaries
BTS_MPO_URL = "https://geo.dot.gov/server/rest/services/NTAD/Metropolitan_Planning_Organizations/MapServer/0/query"

# Rate limiting
REQUEST_DELAY = 0.25  # seconds between paginated requests
MAX_RETRIES = 4
PAGE_SIZE = 2000  # ArcGIS max varies; 2000 is safe for TIGERweb

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "geographic"


def arcgis_query_all(url, where="1=1", out_fields="*", return_geometry=True,
                     out_sr=4326, page_size=PAGE_SIZE, extra_params=None, label="records"):
    """
    Paginate through an ArcGIS REST API FeatureServer/MapServer query endpoint.
    Returns list of all features (attributes + geometry).
    """
    try:
        import requests
    except ImportError:
        print("ERROR: 'requests' package required. Install with: pip install requests")
        sys.exit(1)

    all_features = []
    offset = 0

    while True:
        params = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": "true" if return_geometry else "false",
            "outSR": out_sr,
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": page_size,
        }
        if extra_params:
            params.update(extra_params)

        data = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.get(url, params=params, timeout=60)
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as e:
                wait = 2 ** (attempt + 1)
                print(f"  ⚠ Request failed (attempt {attempt+1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    print(f"    Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"  ✗ Giving up after {MAX_RETRIES} attempts")
                    return all_features

        if data is None:
            break

        # Check for ArcGIS error responses (returned with HTTP 200)
        if "error" in data:
            err = data["error"]
            code = err.get("code", "?")
            msg = err.get("message", "Unknown error")
            details = err.get("details", [])
            print(f"  ✗ ArcGIS API error (code {code}): {msg}")
            if details:
                for d in details[:3]:
                    print(f"    → {d}")
            return all_features

        features = data.get("features", [])
        if not features:
            # Print diagnostic info on first page returning empty
            if offset == 0:
                keys = list(data.keys())
                print(f"  ⚠ API returned 0 features. Response keys: {keys}")
                if len(str(data)) < 500:
                    print(f"    Full response: {json.dumps(data, indent=None)[:400]}")
            break

        all_features.extend(features)
        count = len(all_features)
        print(f"  Fetched {count} {label}...", end="\r")

        # Check if there might be more
        exceeded = data.get("exceededTransferLimit", False)
        if len(features) < page_size and not exceeded:
            break

        offset += len(features)
        time.sleep(REQUEST_DELAY)

    print(f"  Fetched {len(all_features)} {label} total.     ")
    return all_features


def compute_centroid_from_rings(geometry):
    """Compute centroid and bbox from polygon rings."""
    rings = geometry.get("rings", [])
    if not rings:
        return None, None

    all_x, all_y = [], []
    for ring in rings:
        for coord in ring:
            all_x.append(coord[0])
            all_y.append(coord[1])

    if not all_x:
        return None, None

    centroid = [round(sum(all_x) / len(all_x), 6), round(sum(all_y) / len(all_y), 6)]
    bbox = [round(min(all_x), 6), round(min(all_y), 6),
            round(max(all_x), 6), round(max(all_y), 6)]
    return centroid, bbox


def compute_centroid_from_point(geometry):
    """Extract centroid from a point geometry."""
    x = geometry.get("x")
    y = geometry.get("y")
    if x is not None and y is not None:
        return [round(x, 6), round(y, 6)], None
    return None, None


# ─── Dynamic service discovery ───────────────────────────────────────────────

def _discover_tiger_service():
    """
    Try each TIGERweb service URL until one responds with valid layer metadata.
    Returns (base_url, {layer_name: layer_id}) or raises RuntimeError.
    """
    import requests
    global TIGER_BASE

    for service_url in TIGER_SERVICES:
        service_name = service_url.split("/services/")[1].split("/MapServer")[0]
        try:
            resp = requests.get(service_url, params={"f": "json"}, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                print(f"  ⚠ {service_name}: API error — {data['error'].get('message', '?')}")
                continue

            layers = data.get("layers", [])
            if not layers:
                print(f"  ⚠ {service_name}: No layers found")
                continue

            # Build lookup: layer name → layer id
            layer_lookup = {layer["name"]: layer["id"] for layer in layers}

            # Verify we can find our required layers
            resolved = {}
            for key, candidate_names in TIGER_LAYER_NAMES.items():
                for name in candidate_names:
                    if name in layer_lookup:
                        resolved[key] = layer_lookup[name]
                        break

            if len(resolved) >= 2:  # At least states + counties
                TIGER_BASE = service_url
                print(f"  ✓ Using {service_name}")
                for key, layer_id in resolved.items():
                    print(f"    {key}: layer {layer_id}")
                return service_url, resolved
            else:
                print(f"  ⚠ {service_name}: Only matched {len(resolved)}/{len(TIGER_LAYER_NAMES)} layers")

        except requests.exceptions.RequestException as e:
            print(f"  ⚠ {service_name}: {e}")
            continue

    # All services failed — use fallback layer IDs with first service URL
    print("  ⚠ Dynamic layer discovery failed, will try fallback layer IDs")
    TIGER_BASE = TIGER_SERVICES[0]
    return TIGER_BASE, None


def _resolve_layer_url(layer_key, discovered_layers):
    """
    Get the query URL for a layer, trying discovered IDs first,
    then fallback IDs until one returns data.
    """
    if discovered_layers and layer_key in discovered_layers:
        return f"{TIGER_BASE}/{discovered_layers[layer_key]}/query"

    # Try fallback layer IDs
    import requests
    for layer_id in TIGER_LAYERS_FALLBACK.get(layer_key, []):
        url = f"{TIGER_BASE}/{layer_id}/query"
        try:
            resp = requests.get(url, params={
                "where": "1=1", "outFields": "GEOID",
                "returnGeometry": "false", "f": "json",
                "resultRecordCount": 1
            }, timeout=15)
            data = resp.json()
            if data.get("features"):
                print(f"  ✓ Found {layer_key} at layer {layer_id}")
                return url
            if "error" in data:
                continue
        except Exception:
            continue

    # Last resort: use first fallback ID
    fallback_id = TIGER_LAYERS_FALLBACK.get(layer_key, [0])[0]
    return f"{TIGER_BASE}/{fallback_id}/query"


# Module-level state for discovered layers
_discovered_layers = None


def _ensure_service():
    """Discover the TIGERweb service once per run."""
    global _discovered_layers, TIGER_BASE
    if TIGER_BASE is not None:
        return
    print("\n═══ Discovering Census TIGERweb Service ═══")
    _, _discovered_layers = _discover_tiger_service()


# ─── Layer download functions ────────────────────────────────────────────────

def download_states():
    """Download all US states + DC from TIGERweb."""
    print("\n═══ Downloading States ═══")
    _ensure_service()
    url = _resolve_layer_url("states", _discovered_layers)
    features = arcgis_query_all(
        url,
        where="1=1",
        out_fields="GEOID,NAME,STUSAB,FUNCSTAT,ALAND,AWATER",
        return_geometry=True,
        label="states"
    )

    states = []
    for f in features:
        attr = f.get("attributes", {})
        geoid = attr.get("GEOID", "")
        # Skip territories (only 50 states + DC)
        if geoid not in _VALID_STATE_FIPS:
            continue

        centroid, bbox = compute_centroid_from_rings(f.get("geometry", {}))
        states.append({
            "fips": geoid,
            "name": attr.get("NAME", ""),
            "abbreviation": attr.get("STUSAB", ""),
            "centroid": centroid,  # [lon, lat]
            "bbox": bbox,         # [west, south, east, north]
            "landAreaSqM": attr.get("ALAND"),
            "waterAreaSqM": attr.get("AWATER"),
        })

    states.sort(key=lambda s: s["fips"])
    print(f"  ✓ {len(states)} states processed")
    return states


def download_counties(state_fips=None):
    """Download all US counties from TIGERweb."""
    print("\n═══ Downloading Counties ═══")
    _ensure_service()
    url = _resolve_layer_url("counties", _discovered_layers)

    where = f"STATE='{state_fips}'" if state_fips else "1=1"
    features = arcgis_query_all(
        url,
        where=where,
        out_fields="GEOID,STATE,COUNTY,NAME,LSAD,FUNCSTAT,ALAND,AWATER",
        return_geometry=True,
        label="counties"
    )

    counties = []
    for f in features:
        attr = f.get("attributes", {})
        state = attr.get("STATE", "")
        if state not in _VALID_STATE_FIPS:
            continue

        centroid, bbox = compute_centroid_from_rings(f.get("geometry", {}))
        counties.append({
            "stateFips": state,
            "countyFips": attr.get("COUNTY", ""),
            "geoid": attr.get("GEOID", ""),
            "name": attr.get("NAME", ""),
            "lsad": attr.get("LSAD", ""),      # 06=County, 03=City/Borough, 04=Borough, 12=Parish, 15=city(VA), 25=city(MO/NV)
            "centroid": centroid,
            "bbox": bbox,
            "landAreaSqM": attr.get("ALAND"),
        })

    counties.sort(key=lambda c: c["geoid"])
    print(f"  ✓ {len(counties)} counties processed")
    return counties


def download_places(state_fips=None):
    """Download all incorporated places (cities, towns, villages, CDPs) from TIGERweb."""
    print("\n═══ Downloading Incorporated Places ═══")
    _ensure_service()
    url = _resolve_layer_url("places", _discovered_layers)

    where = f"STATE='{state_fips}'" if state_fips else "1=1"
    features = arcgis_query_all(
        url,
        where=where,
        out_fields="GEOID,STATE,PLACEFP,NAME,NAMELSAD,LSAD,FUNCSTAT,ALAND",
        return_geometry=True,
        label="places"
    )

    places = []
    for f in features:
        attr = f.get("attributes", {})
        state = attr.get("STATE", "")
        if state not in _VALID_STATE_FIPS:
            continue

        funcstat = attr.get("FUNCSTAT", "")
        # A = Active, S = Statistical (CDP). Include both.
        if funcstat not in ("A", "S"):
            continue

        centroid, bbox = compute_centroid_from_rings(f.get("geometry", {}))
        lsad = attr.get("LSAD", "")
        places.append({
            "stateFips": state,
            "placeFips": attr.get("PLACEFP", ""),
            "geoid": attr.get("GEOID", ""),
            "name": attr.get("NAME", ""),
            "fullName": attr.get("NAMELSAD", ""),
            "lsad": lsad,
            "type": _LSAD_PLACE_TYPE.get(lsad, "other"),
            "funcstat": funcstat,  # A=incorporated, S=statistical/CDP
            "centroid": centroid,
            "bbox": bbox,
            "landAreaSqM": attr.get("ALAND"),
        })

    places.sort(key=lambda p: p["geoid"])
    print(f"  ✓ {len(places)} places processed")
    return places


def download_county_subdivisions(state_fips=None):
    """Download county subdivisions (MCDs, townships, towns) from TIGERweb."""
    print("\n═══ Downloading County Subdivisions ═══")
    _ensure_service()
    url = _resolve_layer_url("county_subdivisions", _discovered_layers)

    where = f"STATE='{state_fips}'" if state_fips else "1=1"
    features = arcgis_query_all(
        url,
        where=where,
        out_fields="GEOID,STATE,COUNTY,COUSUBFP,NAME,NAMELSAD,LSAD,FUNCSTAT",
        return_geometry=True,
        label="county subdivisions"
    )

    subdivisions = []
    for f in features:
        attr = f.get("attributes", {})
        state = attr.get("STATE", "")
        if state not in _VALID_STATE_FIPS:
            continue

        funcstat = attr.get("FUNCSTAT", "")
        if funcstat not in ("A", "S"):
            continue

        centroid, bbox = compute_centroid_from_rings(f.get("geometry", {}))
        subdivisions.append({
            "stateFips": state,
            "countyFips": attr.get("COUNTY", ""),
            "cousubFips": attr.get("COUSUBFP", ""),
            "geoid": attr.get("GEOID", ""),
            "name": attr.get("NAME", ""),
            "fullName": attr.get("NAMELSAD", ""),
            "lsad": attr.get("LSAD", ""),
            "funcstat": funcstat,
            "centroid": centroid,
            "bbox": bbox,
        })

    subdivisions.sort(key=lambda s: s["geoid"])
    print(f"  ✓ {len(subdivisions)} county subdivisions processed")
    return subdivisions


def download_mpos():
    """Download MPO boundaries from BTS/USDOT NTAD service."""
    print("\n═══ Downloading MPOs (BTS/USDOT) ═══")

    # First try the BTS NTAD service
    features = arcgis_query_all(
        BTS_MPO_URL,
        where="1=1",
        out_fields="*",
        return_geometry=True,
        label="MPOs"
    )

    if not features:
        # Fallback: try alternate URLs
        alt_urls = [
            "https://geo.dot.gov/server/rest/services/NTAD/Metropolitan_Planning_Organizations/FeatureServer/0/query",
            "https://geo.dot.gov/server/rest/services/Hosted/Metropolitan_Planning_Organizations/FeatureServer/0/query",
            "https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/Metropolitan_Planning_Organizations/FeatureServer/0/query",
        ]
        for alt_url in alt_urls:
            print(f"  Trying alternate endpoint: {alt_url.split('/services/')[1].split('/query')[0]}...")
            features = arcgis_query_all(
                alt_url,
                where="1=1",
                out_fields="*",
                return_geometry=True,
                label="MPOs"
            )
            if features:
                break

    mpos = []
    for f in features:
        attr = f.get("attributes", {})
        geometry = f.get("geometry", {})

        centroid, bbox = compute_centroid_from_rings(geometry)

        # Extract all available fields — field names vary across service versions
        mpo = {
            "name": attr.get("MPO_NAME") or attr.get("NAME") or attr.get("MpoName") or "",
            "acronym": attr.get("MPO_ACRONYM") or attr.get("ACRONYM") or attr.get("MpoAcronym") or "",
            "mpoId": attr.get("MPO_ID") or attr.get("OBJECTID") or attr.get("MpoId") or "",
            "stateFips": attr.get("STATE_FIPS") or attr.get("STFIPS") or attr.get("StateFips") or "",
            "stateAbbr": attr.get("STATE") or attr.get("STUSAB") or attr.get("StateAbbr") or "",
            "centroid": centroid,
            "bbox": bbox,
            "population": attr.get("POP") or attr.get("POPULATION") or attr.get("Pop") or None,
            "status": attr.get("STATUS") or attr.get("Status") or "",
        }

        # Capture all raw attributes for inspection
        mpo["_rawFields"] = {k: v for k, v in attr.items() if v is not None and v != ""}

        mpos.append(mpo)

    mpos.sort(key=lambda m: (m.get("stateAbbr", ""), m.get("name", "")))
    print(f"  ✓ {len(mpos)} MPOs processed")
    return mpos


# ─── Spatial join: assign counties to MPOs ───────────────────────────────────

def assign_counties_to_mpos(mpos, counties):
    """
    Use centroid-in-bbox to roughly assign counties to MPOs.
    This is an approximation — proper spatial join would need shapely.
    We check if the county centroid falls within an MPO's bbox.
    """
    print("\n═══ Assigning Counties to MPOs (centroid-in-bbox) ═══")

    for mpo in mpos:
        mpo["counties"] = []
        mpo_bbox = mpo.get("bbox")
        if not mpo_bbox:
            continue

        west, south, east, north = mpo_bbox
        for county in counties:
            c = county.get("centroid")
            if not c:
                continue
            lon, lat = c[0], c[1]
            if west <= lon <= east and south <= lat <= north:
                mpo["counties"].append({
                    "stateFips": county["stateFips"],
                    "countyFips": county["countyFips"],
                    "geoid": county["geoid"],
                    "name": county["name"],
                })

    assigned = sum(1 for m in mpos if m.get("counties"))
    print(f"  ✓ {assigned}/{len(mpos)} MPOs have county assignments")
    return mpos


# ─── Reference data ─────────────────────────────────────────────────────────

# 50 states + DC FIPS codes
_VALID_STATE_FIPS = {
    "01", "02", "04", "05", "06", "08", "09", "10", "11", "12",
    "13", "15", "16", "17", "18", "19", "20", "21", "22", "23",
    "24", "25", "26", "27", "28", "29", "30", "31", "32", "33",
    "34", "35", "36", "37", "38", "39", "40", "41", "42", "44",
    "45", "46", "47", "48", "49", "50", "51", "53", "54", "55", "56"
}

# LSAD codes for places → human-readable type
_LSAD_PLACE_TYPE = {
    "25": "city",
    "43": "town",
    "47": "village",
    "53": "CDP",       # Census Designated Place (unincorporated)
    "55": "CDP",
    "57": "CDP",
    "21": "borough",
    "44": "township",
    "46": "plantation",
    "49": "charter_township",
    "00": "city",      # Consolidated city
}


# ─── Main ────────────────────────────────────────────────────────────────────

def save_json(data, filename, metadata=None):
    """Save data to JSON file with metadata header."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / filename

    output = {
        "_metadata": {
            "source": "Census TIGERweb + BTS/USDOT NTAD",
            "downloadedAt": datetime.now(timezone.utc).isoformat(),
            "script": "scripts/download_geographic_data.py",
            "recordCount": len(data),
        },
        "data": data,
    }
    if metadata:
        output["_metadata"].update(metadata)

    with open(filepath, "w") as f:
        json.dump(output, f, indent=2)

    size_mb = filepath.stat().st_size / (1024 * 1024)
    print(f"  💾 Saved {filepath} ({size_mb:.1f} MB, {len(data)} records)")


def main():
    parser = argparse.ArgumentParser(
        description="Download US geographic/administrative data from federal APIs"
    )
    parser.add_argument(
        "--layer", type=str, default="all",
        choices=["all", "states", "counties", "places", "subdivisions", "mpos"],
        help="Which data layer to download (default: all)"
    )
    parser.add_argument(
        "--state", type=str, default=None,
        help="2-digit state FIPS to limit download (e.g., 51 for Virginia)"
    )
    parser.add_argument(
        "--skip-subdivisions", action="store_true",
        help="Skip county subdivisions (largest dataset, ~35,000 records)"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  CRASH LENS — Geographic Data Downloader")
    print(f"  Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    if args.state:
        print(f"  Scope: State FIPS {args.state}")
    else:
        print("  Scope: Nationwide (50 states + DC)")
    print("=" * 60)

    layer = args.layer
    counties_data = None

    # ── States ──
    if layer in ("all", "states") and not args.state:
        states = download_states()
        save_json(states, "us_states.json")

    # ── Counties ──
    if layer in ("all", "counties"):
        counties_data = download_counties(state_fips=args.state)
        suffix = f"_{args.state}" if args.state else ""
        save_json(counties_data, f"us_counties{suffix}.json")

    # ── Incorporated Places ──
    if layer in ("all", "places"):
        places = download_places(state_fips=args.state)
        suffix = f"_{args.state}" if args.state else ""
        save_json(places, f"us_places{suffix}.json")

    # ── County Subdivisions ──
    if layer in ("all", "subdivisions"):
        if args.skip_subdivisions and layer == "all":
            print("\n⏭ Skipping county subdivisions (--skip-subdivisions)")
        else:
            subdivisions = download_county_subdivisions(state_fips=args.state)
            suffix = f"_{args.state}" if args.state else ""
            save_json(subdivisions, f"us_county_subdivisions{suffix}.json")

    # ── MPOs ──
    if layer in ("all", "mpos"):
        mpos = download_mpos()
        # If we have counties, do spatial assignment
        if counties_data:
            mpos = assign_counties_to_mpos(mpos, counties_data)
        elif layer == "mpos":
            # Need counties for assignment — download them
            print("\n  (Downloading counties for MPO-county assignment...)")
            counties_data = download_counties(state_fips=args.state)
            mpos = assign_counties_to_mpos(mpos, counties_data)
        save_json(mpos, "us_mpos.json")

    # ── Validate results ──
    print("\n" + "=" * 60)
    total_records = 0
    failures = []
    for json_file in sorted(OUTPUT_DIR.glob("*.json")):
        try:
            with open(json_file) as jf:
                meta = json.load(jf).get("_metadata", {})
                count = meta.get("recordCount", 0)
                total_records += count
                if count == 0:
                    failures.append(json_file.name)
        except Exception:
            failures.append(json_file.name)

    if total_records == 0:
        print("  ✗ FAILED: All downloads returned 0 records!")
        print("    This likely means the Census TIGERweb API has changed.")
        print("    Check: https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb")
        print("=" * 60)
        sys.exit(1)
    elif failures:
        print(f"  ⚠ Partial success: {len(failures)} layer(s) returned 0 records:")
        for f in failures:
            print(f"    - {f}")
        print(f"  Total records across other layers: {total_records}")
    else:
        print("  ✓ Download complete!")

    print(f"  Output directory: {OUTPUT_DIR}")
    print("=" * 60)

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
