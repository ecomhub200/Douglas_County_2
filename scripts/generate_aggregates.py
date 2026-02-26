#!/usr/bin/env python3
"""
Generate pre-aggregated JSON summaries for State, Region, and MPO tiers.

Reads per-county CSV crash data and produces aggregate JSON files that power
the State/Region/MPO dashboard views without requiring raw CSV loading.

Output structure (designed to match R2 folder hierarchy):
  {state}/_statewide/aggregates.json       — Statewide totals, trends, YoY
  {state}/_statewide/county_summary.json   — Per-county ranking table (by road type)
  {state}/_region/{region}/aggregates.json  — Region totals + member counties
  {state}/_region/{region}/hotspots.json    — Cross-county hotspot ranking
  {state}/_mpo/{mpo}/aggregates.json        — MPO totals + member counties
  {state}/_mpo/{mpo}/hotspots.json          — Cross-county hotspot ranking
  {state}/{county}/aggregates.json          — Full browser-compatible aggregates (--county-level)
  {state}/{county}/meta.json                — Hash + timestamp for cache invalidation (--county-level)

Usage:
  # Generate aggregates for Colorado
  python scripts/generate_aggregates.py --state colorado

  # Generate for Virginia
  python scripts/generate_aggregates.py --state virginia

  # Dry run (preview output paths without writing)
  python scripts/generate_aggregates.py --state colorado --dry-run

  # Specify custom data directory
  python scripts/generate_aggregates.py --state colorado --data-dir ./data/CDOT

  # Generate federal-level cross-state aggregates (combines all state aggregates)
  python scripts/generate_aggregates.py --federal

  # Generate per-county aggregates.json + meta.json for browser instant loading
  python scripts/generate_aggregates.py --state colorado --county-level

  # Dry run county-level generation (preview output paths)
  python scripts/generate_aggregates.py --state virginia --county-level --dry-run

Prerequisites:
  pip install pandas
"""

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent


def load_hierarchy(state_key):
    """Load hierarchy.json for the given state."""
    path = PROJECT_ROOT / 'states' / state_key / 'hierarchy.json'
    if not path.exists():
        print(f"[ERROR] Hierarchy file not found: {path}")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def load_state_config(state_key):
    """Load state config.json for EPDO weights and column mapping."""
    path = PROJECT_ROOT / 'states' / state_key / 'config.json'
    if not path.exists():
        print(f"[WARN] State config not found: {path}, using defaults")
        return {}
    with open(path) as f:
        return json.load(f)


def get_epdo_weights(config):
    """Extract EPDO weights from state config, with HSM 2010 fallback."""
    defaults = {'K': 462, 'A': 62, 'B': 12, 'C': 5, 'O': 1}
    return config.get('epdoWeights', defaults)


def calc_epdo(severity_counts, weights):
    """Calculate EPDO score from severity counts and weights."""
    return sum(severity_counts.get(sev, 0) * weights.get(sev, 0) for sev in ['K', 'A', 'B', 'C', 'O'])


def find_county_csvs(data_dir, state_key, hierarchy):
    """
    Find all county CSV files in the data directory.

    Searches for files matching patterns like:
      {county_name}_all_roads.csv
      {county_name}_county_roads.csv
      {county_name}_no_interstate.csv
    """
    found = {}
    all_counties = hierarchy.get('allCounties', {})

    # Build name→fips lookup from hierarchy
    name_to_fips = {}
    for fips, name in all_counties.items():
        name_lower = name.lower().replace(' ', '_').replace("'", '')
        name_to_fips[name_lower] = fips

    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"[WARN] Data directory not found: {data_path}")
        return found

    road_types = ['all_roads', 'county_roads', 'no_interstate']

    for csv_file in data_path.glob('*.csv'):
        fname = csv_file.stem.lower()
        for rt in road_types:
            if fname.endswith(f'_{rt}'):
                county_name = fname[:-len(f'_{rt}')]
                fips = name_to_fips.get(county_name)
                if fips:
                    if fips not in found:
                        found[fips] = {}
                    found[fips][rt] = str(csv_file)
                break

    return found


def parse_csv_crashes(csv_path, col_mapping):
    """Parse a crash CSV and return structured crash records."""
    crashes = []
    severity_map = col_mapping.get('SEVERITY')
    date_col = col_mapping.get('DATE')
    route_col = col_mapping.get('ROUTE')
    node_col = col_mapping.get('NODE', '')
    collision_col = col_mapping.get('COLLISION')
    weather_col = col_mapping.get('WEATHER')
    light_col = col_mapping.get('LIGHT')
    ped_col = col_mapping.get('PED')
    bike_col = col_mapping.get('BIKE')
    speed_col = col_mapping.get('SPEED')
    alcohol_col = col_mapping.get('ALCOHOL')
    x_col = col_mapping.get('X')
    y_col = col_mapping.get('Y')

    # Colorado derives severity from injury columns
    k_col = col_mapping.get('K')
    a_col = col_mapping.get('A')
    b_col = col_mapping.get('B')
    c_col = col_mapping.get('C')
    o_col = col_mapping.get('O')

    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Determine severity
                sev = None
                if severity_map and severity_map in row:
                    sev = row[severity_map]
                else:
                    # Derive from injury columns (Colorado pattern)
                    for sev_label, col in [('K', k_col), ('A', a_col), ('B', b_col), ('C', c_col), ('O', o_col)]:
                        if col and col in row:
                            try:
                                if int(float(row[col] or 0)) > 0:
                                    sev = sev_label
                                    break
                            except (ValueError, TypeError):
                                pass
                    if not sev:
                        sev = 'O'

                # Extract year
                year = None
                if date_col and date_col in row and row[date_col]:
                    try:
                        date_str = row[date_col]
                        if '/' in date_str:
                            parts = date_str.split('/')
                            year = int(parts[-1]) if len(parts[-1]) == 4 else int('20' + parts[-1])
                        elif '-' in date_str:
                            year = int(date_str.split('-')[0])
                        else:
                            year = int(date_str[:4])
                    except (ValueError, IndexError):
                        pass

                crash = {
                    'severity': sev,
                    'year': year,
                    'route': row.get(route_col, '') if route_col else '',
                    'node': row.get(node_col, '') if node_col else '',
                    'collision': row.get(collision_col, '') if collision_col else '',
                    'weather': row.get(weather_col, '') if weather_col else '',
                    'light': row.get(light_col, '') if light_col else '',
                    'ped': _is_yes(row.get(ped_col, '')) if ped_col else False,
                    'bike': _is_yes(row.get(bike_col, '')) if bike_col else False,
                    'speed': _is_yes(row.get(speed_col, '')) if speed_col else False,
                    'alcohol': _is_yes(row.get(alcohol_col, '')) if alcohol_col else False,
                }
                crashes.append(crash)
    except Exception as e:
        print(f"[ERROR] Failed to parse {csv_path}: {e}")

    return crashes


def parse_csv_crashes_detailed(csv_path, col_mapping):
    """Parse a crash CSV with ALL columns needed for county-level aggregates.json.

    Returns crash records with additional fields (hour, dow, month, funcClass,
    intType, trafficCtrl, night, personsInjured, vehicleCount, pedKilled,
    pedInjured) that match what the browser's processRow() tracks.
    """
    crashes = []
    severity_map = col_mapping.get('SEVERITY')
    date_col = col_mapping.get('DATE')
    time_col = col_mapping.get('TIME')
    route_col = col_mapping.get('ROUTE')
    node_col = col_mapping.get('NODE', '')
    collision_col = col_mapping.get('COLLISION')
    weather_col = col_mapping.get('WEATHER')
    light_col = col_mapping.get('LIGHT')
    ped_col = col_mapping.get('PED')
    bike_col = col_mapping.get('BIKE')
    speed_col = col_mapping.get('SPEED')
    alcohol_col = col_mapping.get('ALCOHOL')
    night_col = col_mapping.get('NIGHT')
    func_class_col = col_mapping.get('FUNC_CLASS')
    int_type_col = col_mapping.get('INT_TYPE')
    traffic_ctrl_col = col_mapping.get('TRAFFIC_CTRL')
    vehicle_count_col = col_mapping.get('VEHICLE_COUNT')
    persons_injured_col = col_mapping.get('PERSONS_INJURED')
    ped_killed_col = col_mapping.get('PED_KILLED')
    ped_injured_col = col_mapping.get('PED_INJURED')

    k_col = col_mapping.get('K')
    a_col = col_mapping.get('A')
    b_col = col_mapping.get('B')
    c_col = col_mapping.get('C')
    o_col = col_mapping.get('O')

    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Determine severity (same logic as parse_csv_crashes)
                sev = None
                if severity_map and severity_map in row:
                    sev = row[severity_map]
                else:
                    for sev_label, col in [('K', k_col), ('A', a_col), ('B', b_col), ('C', c_col), ('O', o_col)]:
                        if col and col in row:
                            try:
                                if int(float(row[col] or 0)) > 0:
                                    sev = sev_label
                                    break
                            except (ValueError, TypeError):
                                pass
                    if not sev:
                        sev = 'O'

                # Extract year, month, dow from date
                year = None
                month = None
                dow = None
                if date_col and date_col in row and row[date_col]:
                    try:
                        date_str = row[date_col]
                        parsed_date = None
                        if '/' in date_str:
                            parts = date_str.split('/')
                            if len(parts) == 3:
                                m, d, y = int(parts[0]), int(parts[1]), int(parts[2])
                                if y < 100:
                                    y += 2000
                                year = y
                                try:
                                    from datetime import date as dt_date
                                    parsed_date = dt_date(y, m, d)
                                    month = parsed_date.month - 1  # 0-indexed like JS
                                    dow = parsed_date.weekday()  # Mon=0
                                    # Convert to JS convention: Sun=0
                                    dow = (dow + 1) % 7
                                except ValueError:
                                    pass
                        elif '-' in date_str:
                            parts = date_str.split('-')
                            year = int(parts[0])
                            if len(parts) >= 3:
                                try:
                                    from datetime import date as dt_date
                                    parsed_date = dt_date(int(parts[0]), int(parts[1]), int(parts[2][:2]))
                                    month = parsed_date.month - 1
                                    dow = (parsed_date.weekday() + 1) % 7
                                except (ValueError, IndexError):
                                    pass
                        else:
                            year = int(date_str[:4])
                    except (ValueError, IndexError):
                        pass

                # Extract hour from time
                hour = None
                if time_col and time_col in row and row[time_col]:
                    try:
                        time_str = str(row[time_col]).strip()
                        if ':' in time_str:
                            hour = int(time_str.split(':')[0])
                        elif len(time_str) >= 3:
                            # Military time like "1430"
                            hour = int(time_str[:2]) if len(time_str) >= 4 else int(time_str[0])
                        if hour is not None and (hour < 0 or hour > 23):
                            hour = None
                    except (ValueError, TypeError):
                        pass

                # Node determines intersection
                node_val = row.get(node_col, '') if node_col else ''
                is_intersection = bool(node_val and node_val.strip())

                crash = {
                    'severity': sev,
                    'year': year,
                    'month': month,
                    'dow': dow,
                    'hour': hour,
                    'route': row.get(route_col, '') if route_col else '',
                    'node': node_val,
                    'collision': (row.get(collision_col, '') if collision_col else '').strip() or 'Unknown',
                    'weather': (row.get(weather_col, '') if weather_col else '').strip() or 'Unknown',
                    'light': (row.get(light_col, '') if light_col else '').strip() or 'Unknown',
                    'ped': _is_yes(row.get(ped_col, '')) if ped_col else False,
                    'bike': _is_yes(row.get(bike_col, '')) if bike_col else False,
                    'speed': _is_yes(row.get(speed_col, '')) if speed_col else False,
                    'alcohol': _is_yes(row.get(alcohol_col, '')) if alcohol_col else False,
                    'night': _is_yes(row.get(night_col, '')) if night_col else False,
                    'isIntersection': is_intersection,
                    'funcClass': (row.get(func_class_col, '') if func_class_col else '').strip() or 'Unknown',
                    'intType': (row.get(int_type_col, '') if int_type_col else '').strip(),
                    'trafficCtrl': (row.get(traffic_ctrl_col, '') if traffic_ctrl_col else '').strip(),
                    'vehicleCount': _safe_int(row.get(vehicle_count_col, '')) if vehicle_count_col else 0,
                    'personsInjured': _safe_int(row.get(persons_injured_col, '')) if persons_injured_col else 0,
                    'pedKilled': _safe_int(row.get(ped_killed_col, '')) if ped_killed_col else 0,
                    'pedInjured': _safe_int(row.get(ped_injured_col, '')) if ped_injured_col else 0,
                }
                crashes.append(crash)
    except Exception as e:
        print(f"[ERROR] Failed to parse {csv_path}: {e}")

    return crashes


def _safe_int(val):
    """Safely convert a value to int, returning 0 on failure."""
    if not val:
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def _is_yes(val):
    """Check if a field value indicates 'yes' / true."""
    if not val:
        return False
    v = str(val).strip().upper()
    return v in ('Y', 'YES', '1', 'TRUE', 'T')


def compute_county_stats(crashes, epdo_weights):
    """Compute aggregate statistics for a set of crashes."""
    stats = {
        'total': len(crashes),
        'K': 0, 'A': 0, 'B': 0, 'C': 0, 'O': 0,
        'epdo': 0,
        'pedCrashes': 0,
        'bikeCrashes': 0,
        'speedCrashes': 0,
        'alcoholCrashes': 0,
        'yearlyTrend': defaultdict(lambda: {'total': 0, 'K': 0, 'A': 0, 'B': 0, 'C': 0, 'O': 0}),
        'collisionTypes': defaultdict(int),
        'weatherDist': defaultdict(int),
        'lightDist': defaultdict(int),
        'byRoute': defaultdict(lambda: {'total': 0, 'K': 0, 'A': 0, 'B': 0, 'C': 0, 'O': 0, 'epdo': 0})
    }

    for c in crashes:
        sev = c['severity']
        if sev in ('K', 'A', 'B', 'C', 'O'):
            stats[sev] += 1
        if c.get('ped'):
            stats['pedCrashes'] += 1
        if c.get('bike'):
            stats['bikeCrashes'] += 1
        if c.get('speed'):
            stats['speedCrashes'] += 1
        if c.get('alcohol'):
            stats['alcoholCrashes'] += 1

        if c.get('year'):
            yt = stats['yearlyTrend'][c['year']]
            yt['total'] += 1
            if sev in ('K', 'A', 'B', 'C', 'O'):
                yt[sev] += 1

        if c.get('collision'):
            stats['collisionTypes'][c['collision']] += 1
        if c.get('weather'):
            stats['weatherDist'][c['weather']] += 1
        if c.get('light'):
            stats['lightDist'][c['light']] += 1

        route = c.get('route', '')
        if route:
            br = stats['byRoute'][route]
            br['total'] += 1
            if sev in ('K', 'A', 'B', 'C', 'O'):
                br[sev] += 1

    # Compute EPDO
    sev_counts = {s: stats[s] for s in ['K', 'A', 'B', 'C', 'O']}
    stats['epdo'] = calc_epdo(sev_counts, epdo_weights)

    # Compute per-route EPDO
    for route, rd in stats['byRoute'].items():
        rd['epdo'] = calc_epdo(rd, epdo_weights)

    # Convert yearly trend to sorted list
    years = sorted(stats['yearlyTrend'].keys())
    stats['yearlyTrend'] = [{'year': y, **stats['yearlyTrend'][y]} for y in years]

    # Compute YoY trend (last 2 years)
    if len(stats['yearlyTrend']) >= 2:
        prev = stats['yearlyTrend'][-2]['total']
        curr = stats['yearlyTrend'][-1]['total']
        stats['trend'] = round((curr - prev) / prev, 4) if prev > 0 else 0
    else:
        stats['trend'] = 0

    # Convert collision types to sorted list (top 10)
    ct = sorted(stats['collisionTypes'].items(), key=lambda x: -x[1])[:10]
    total = stats['total'] or 1
    stats['topCollisionTypes'] = [{'type': t, 'count': c, 'pct': round(c / total * 100, 1)} for t, c in ct]

    # Convert weather/light to dicts
    stats['weatherDist'] = dict(stats['weatherDist'])
    stats['lightDist'] = dict(stats['lightDist'])

    # Convert byRoute to sorted list (top 25)
    route_list = sorted(stats['byRoute'].items(), key=lambda x: -x[1]['epdo'])[:25]
    stats['topRoutes'] = [{'route': r, **d} for r, d in route_list]

    # Remove internal defaultdicts before serialization
    del stats['collisionTypes']
    del stats['byRoute']

    return stats


def compute_hotspots(crashes, epdo_weights, top_n=50):
    """Compute top-N hotspot locations ranked by EPDO."""
    by_location = defaultdict(lambda: {'total': 0, 'K': 0, 'A': 0, 'B': 0, 'C': 0, 'O': 0})

    for c in crashes:
        route = c.get('route', '')
        node = c.get('node', '')
        if not route:
            continue
        loc_key = f"{route}|{node}" if node else route
        loc = by_location[loc_key]
        loc['total'] += 1
        sev = c['severity']
        if sev in ('K', 'A', 'B', 'C', 'O'):
            loc[sev] += 1

    # Compute EPDO and sort
    hotspots = []
    for loc_key, stats in by_location.items():
        parts = loc_key.split('|', 1)
        route = parts[0]
        node = parts[1] if len(parts) > 1 else ''
        epdo = calc_epdo(stats, epdo_weights)
        hotspots.append({
            'route': route,
            'node': node,
            'total': stats['total'],
            'K': stats['K'], 'A': stats['A'], 'B': stats['B'],
            'C': stats['C'], 'O': stats['O'],
            'epdo': epdo,
            'ka': stats['K'] + stats['A']
        })

    hotspots.sort(key=lambda x: -x['epdo'])
    return hotspots[:top_n]


def generate_statewide_aggregates(county_data, hierarchy, epdo_weights, road_type='all_roads'):
    """Generate statewide aggregate from all counties."""
    all_crashes = []
    county_stats = {}
    all_counties = hierarchy.get('allCounties', {})

    for fips, road_types in county_data.items():
        csv_path = road_types.get(road_type)
        if not csv_path:
            continue
        col_mapping = _get_col_mapping(hierarchy)
        crashes = parse_csv_crashes(csv_path, col_mapping)
        if crashes:
            stats = compute_county_stats(crashes, epdo_weights)
            county_name = all_counties.get(fips, fips)
            stats['name'] = county_name
            stats['fips'] = fips
            county_stats[fips] = stats
            all_crashes.extend(crashes)
            print(f"  [{fips}] {county_name}: {len(crashes)} crashes, EPDO={stats['epdo']:,}")

    # Statewide totals
    statewide = compute_county_stats(all_crashes, epdo_weights) if all_crashes else {}

    return statewide, county_stats


def generate_group_aggregates(county_data, group_counties, hierarchy, epdo_weights, road_type='all_roads'):
    """Generate aggregate for a group of counties (region or MPO)."""
    group_crashes = []
    member_stats = {}
    all_counties = hierarchy.get('allCounties', {})
    col_mapping = _get_col_mapping(hierarchy)

    for fips in group_counties:
        road_types = county_data.get(fips, {})
        csv_path = road_types.get(road_type)
        if not csv_path:
            continue
        crashes = parse_csv_crashes(csv_path, col_mapping)
        if crashes:
            stats = compute_county_stats(crashes, epdo_weights)
            county_name = all_counties.get(fips, fips)
            stats['name'] = county_name
            stats['fips'] = fips
            member_stats[fips] = stats
            # Tag crashes with county for hotspot attribution
            for c in crashes:
                c['_county_fips'] = fips
                c['_county_name'] = county_name
            group_crashes.extend(crashes)

    group_totals = compute_county_stats(group_crashes, epdo_weights) if group_crashes else {}
    hotspots = compute_hotspots(group_crashes, epdo_weights) if group_crashes else []

    # Add county attribution to hotspots
    crash_by_route_node = defaultdict(lambda: defaultdict(int))
    for c in group_crashes:
        route = c.get('route', '')
        node = c.get('node', '')
        loc_key = f"{route}|{node}" if node else route
        crash_by_route_node[loc_key][c.get('_county_name', 'Unknown')] += 1

    for hs in hotspots:
        loc_key = f"{hs['route']}|{hs['node']}" if hs['node'] else hs['route']
        county_dist = crash_by_route_node.get(loc_key, {})
        if county_dist:
            top_county = max(county_dist.items(), key=lambda x: x[1])
            hs['county'] = top_county[0]
            hs['countyDist'] = dict(county_dist)

    return group_totals, member_stats, hotspots


def _get_col_mapping(hierarchy):
    """Get column mapping for the state.

    Resolves the state directory by trying the abbreviation (e.g. 'co'),
    then scanning states/ for a config.json whose abbreviation matches.
    """
    abbreviation = hierarchy.get('state', {}).get('abbreviation', '').lower()

    # Try abbreviation directly, then scan states/ dirs for a matching abbreviation
    states_dir = PROJECT_ROOT / 'states'
    candidates = [states_dir / abbreviation]
    if states_dir.is_dir():
        for d in sorted(states_dir.iterdir()):
            if d.is_dir() and d.name != abbreviation:
                candidates.append(d)

    for d in candidates:
        p = d / 'config.json'
        if p.exists():
            with open(p) as f:
                config = json.load(f)
            # Verify this config belongs to the right state
            cfg_abbr = config.get('state', {}).get('abbreviation', '').lower()
            if cfg_abbr == abbreviation or d.name == abbreviation:
                return config.get('columnMapping', {})
    return {}


def write_output(output_dir, relative_path, data, dry_run=False):
    """Write JSON output file."""
    out_path = Path(output_dir) / relative_path
    if dry_run:
        size = len(json.dumps(data))
        print(f"  [DRY-RUN] Would write: {out_path} ({size:,} bytes)")
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    size = out_path.stat().st_size
    print(f"  [WRITE] {out_path} ({size:,} bytes)")


def compute_detailed_aggregates(crashes, epdo_weights):
    """Compute the FULL crashState.aggregates-compatible structure from crash records.

    This produces the exact JSON shape that the browser's processRow() builds,
    allowing the browser to skip CSV download+parse and load this JSON directly.
    Used for county-level aggregates.json files.
    """
    agg = {
        'byYear': {},
        'bySeverity': {'K': 0, 'A': 0, 'B': 0, 'C': 0, 'O': 0},
        'byCollision': {},
        'byWeather': {},
        'byLight': {},
        'byRoute': {},
        'byNode': {},
        'byHour': {},
        'byDOW': {},
        'byMonth': {},
        'byFuncClass': {},
        'byIntType': {},
        'byTrafficCtrl': {},
        'ped': {'total': 0, 'K': 0, 'A': 0, 'B': 0, 'C': 0, 'O': 0, 'byYear': {}, 'byLight': {}, 'byRoute': {}},
        'bike': {'total': 0, 'K': 0, 'A': 0, 'B': 0, 'C': 0, 'O': 0, 'byYear': {}, 'byLight': {}, 'byRoute': {}},
        'speed': {'total': 0, 'K': 0, 'A': 0, 'B': 0, 'C': 0, 'O': 0, 'byYear': {}},
        'nighttime': {'total': 0, 'K': 0, 'A': 0, 'B': 0, 'C': 0, 'O': 0, 'byYear': {}},
        'intersection': {'total': 0, 'K': 0, 'A': 0, 'B': 0, 'C': 0, 'O': 0},
        'nonIntersection': {'total': 0, 'K': 0, 'A': 0, 'B': 0, 'C': 0, 'O': 0},
        'personsInjured': 0,
        'vehicleCount': {
            'total': 0, 'sum': 0,
            'bySeverity': {
                'K': {'count': 0, 'sum': 0}, 'A': {'count': 0, 'sum': 0},
                'B': {'count': 0, 'sum': 0}, 'C': {'count': 0, 'sum': 0},
                'O': {'count': 0, 'sum': 0}
            }
        },
        'pedCasualties': {'killed': 0, 'injured': 0, 'byYear': {}},
    }

    # Track node→routes mapping (will convert set to list for JSON)
    node_routes = defaultdict(set)

    for c in crashes:
        sev = c.get('severity', 'O')
        year = c.get('year')
        route = c.get('route', '') or 'Unknown'
        node = c.get('node', '')
        collision = c.get('collision', 'Unknown')
        weather = c.get('weather', 'Unknown')
        light = c.get('light', 'Unknown')
        hour = c.get('hour')
        dow = c.get('dow')
        month_val = c.get('month')
        func_class = c.get('funcClass', 'Unknown')
        int_type = c.get('intType', '')
        traffic_ctrl = c.get('trafficCtrl', '')

        # bySeverity
        if sev in agg['bySeverity']:
            agg['bySeverity'][sev] += 1

        # byYear
        if year:
            yr_key = str(year)
            if yr_key not in agg['byYear']:
                agg['byYear'][yr_key] = {'total': 0, 'K': 0, 'A': 0, 'B': 0, 'C': 0, 'O': 0, 'ped': 0, 'bike': 0, 'speed': 0, 'nighttime': 0}
            agg['byYear'][yr_key]['total'] += 1
            if sev in agg['byYear'][yr_key]:
                agg['byYear'][yr_key][sev] += 1
            if c.get('ped'):
                agg['byYear'][yr_key]['ped'] += 1
            if c.get('bike'):
                agg['byYear'][yr_key]['bike'] += 1

        # byCollision
        agg['byCollision'][collision] = agg['byCollision'].get(collision, 0) + 1

        # byWeather
        agg['byWeather'][weather] = agg['byWeather'].get(weather, 0) + 1

        # byLight
        agg['byLight'][light] = agg['byLight'].get(light, 0) + 1

        # byRoute
        if route != 'Unknown':
            if route not in agg['byRoute']:
                agg['byRoute'][route] = {
                    'total': 0, 'K': 0, 'A': 0, 'B': 0, 'C': 0, 'O': 0,
                    'collisions': {}, 'ped': 0, 'bike': 0, 'byYear': {}
                }
            br = agg['byRoute'][route]
            br['total'] += 1
            if sev in br:
                br[sev] += 1
            br['collisions'][collision] = br['collisions'].get(collision, 0) + 1
            if c.get('ped'):
                br['ped'] += 1
            if c.get('bike'):
                br['bike'] += 1
            if year:
                yr_key = str(year)
                if yr_key not in br['byYear']:
                    br['byYear'][yr_key] = {'total': 0, 'K': 0, 'A': 0, 'B': 0, 'C': 0, 'O': 0, 'ped': 0, 'bike': 0}
                br['byYear'][yr_key]['total'] += 1
                if sev in br['byYear'][yr_key]:
                    br['byYear'][yr_key][sev] += 1
                if c.get('ped'):
                    br['byYear'][yr_key]['ped'] += 1
                if c.get('bike'):
                    br['byYear'][yr_key]['bike'] += 1

        # byNode
        if node:
            if node not in agg['byNode']:
                agg['byNode'][node] = {'total': 0, 'K': 0, 'A': 0, 'B': 0, 'C': 0, 'O': 0, 'routes': [], 'ctrl': traffic_ctrl}
            agg['byNode'][node]['total'] += 1
            if sev in agg['byNode'][node]:
                agg['byNode'][node][sev] += 1
            if route and route != 'Unknown':
                node_routes[node].add(route)

        # byHour
        if hour is not None:
            hr_key = str(hour)
            agg['byHour'][hr_key] = agg['byHour'].get(hr_key, 0) + 1

        # byDOW
        if dow is not None:
            dow_key = str(dow)
            agg['byDOW'][dow_key] = agg['byDOW'].get(dow_key, 0) + 1

        # byMonth
        if month_val is not None:
            m_key = str(month_val)
            agg['byMonth'][m_key] = agg['byMonth'].get(m_key, 0) + 1

        # byFuncClass
        if func_class not in agg['byFuncClass']:
            agg['byFuncClass'][func_class] = {'total': 0, 'K': 0, 'A': 0, 'B': 0, 'C': 0, 'O': 0}
        agg['byFuncClass'][func_class]['total'] += 1
        if sev in agg['byFuncClass'][func_class]:
            agg['byFuncClass'][func_class][sev] += 1

        # byIntType
        if int_type:
            if int_type not in agg['byIntType']:
                agg['byIntType'][int_type] = {'total': 0, 'K': 0, 'A': 0}
            agg['byIntType'][int_type]['total'] += 1
            if sev == 'K':
                agg['byIntType'][int_type]['K'] += 1
            if sev == 'A':
                agg['byIntType'][int_type]['A'] += 1

        # byTrafficCtrl
        if traffic_ctrl:
            agg['byTrafficCtrl'][traffic_ctrl] = agg['byTrafficCtrl'].get(traffic_ctrl, 0) + 1

        # intersection vs nonIntersection
        if c.get('isIntersection'):
            agg['intersection']['total'] += 1
            if sev in agg['intersection']:
                agg['intersection'][sev] += 1
        else:
            agg['nonIntersection']['total'] += 1
            if sev in agg['nonIntersection']:
                agg['nonIntersection'][sev] += 1

        # Pedestrian
        if c.get('ped'):
            agg['ped']['total'] += 1
            if sev in agg['ped']:
                agg['ped'][sev] += 1
            if year:
                yr_key = str(year)
                agg['ped']['byYear'][yr_key] = agg['ped']['byYear'].get(yr_key, 0) + 1
            agg['ped']['byLight'][light] = agg['ped']['byLight'].get(light, 0) + 1
            if route != 'Unknown':
                agg['ped']['byRoute'][route] = agg['ped']['byRoute'].get(route, 0) + 1

        # Bicycle
        if c.get('bike'):
            agg['bike']['total'] += 1
            if sev in agg['bike']:
                agg['bike'][sev] += 1
            if year:
                yr_key = str(year)
                agg['bike']['byYear'][yr_key] = agg['bike']['byYear'].get(yr_key, 0) + 1
            agg['bike']['byLight'][light] = agg['bike']['byLight'].get(light, 0) + 1
            if route != 'Unknown':
                agg['bike']['byRoute'][route] = agg['bike']['byRoute'].get(route, 0) + 1

        # Speed
        if c.get('speed'):
            agg['speed']['total'] += 1
            if sev in agg['speed']:
                agg['speed'][sev] += 1
            if year:
                yr_key = str(year)
                agg['speed']['byYear'][yr_key] = agg['speed']['byYear'].get(yr_key, 0) + 1
                # Also update byYear speed count
                if yr_key in agg['byYear']:
                    agg['byYear'][yr_key]['speed'] += 1

        # Nighttime
        if c.get('night'):
            agg['nighttime']['total'] += 1
            if sev in agg['nighttime']:
                agg['nighttime'][sev] += 1
            if year:
                yr_key = str(year)
                agg['nighttime']['byYear'][yr_key] = agg['nighttime']['byYear'].get(yr_key, 0) + 1
                if yr_key in agg['byYear']:
                    agg['byYear'][yr_key]['nighttime'] = agg['byYear'][yr_key].get('nighttime', 0) + 1

        # Persons injured
        pi = c.get('personsInjured', 0)
        if pi > 0:
            agg['personsInjured'] += pi

        # Vehicle count
        vc = c.get('vehicleCount', 0)
        if vc > 0:
            agg['vehicleCount']['total'] += 1
            agg['vehicleCount']['sum'] += vc
            if sev in agg['vehicleCount']['bySeverity']:
                agg['vehicleCount']['bySeverity'][sev]['count'] += 1
                agg['vehicleCount']['bySeverity'][sev]['sum'] += vc

        # Pedestrian casualties
        pk = c.get('pedKilled', 0)
        pj = c.get('pedInjured', 0)
        if pk > 0 or pj > 0:
            agg['pedCasualties']['killed'] += pk
            agg['pedCasualties']['injured'] += pj
            if year:
                yr_key = str(year)
                if yr_key not in agg['pedCasualties']['byYear']:
                    agg['pedCasualties']['byYear'][yr_key] = {'killed': 0, 'injured': 0}
                agg['pedCasualties']['byYear'][yr_key]['killed'] += pk
                agg['pedCasualties']['byYear'][yr_key]['injured'] += pj

    # Convert node route sets to sorted lists for JSON serialization
    for node_key, routes_set in node_routes.items():
        if node_key in agg['byNode']:
            agg['byNode'][node_key]['routes'] = sorted(routes_set)

    return agg


def generate_county_level_aggregates(county_data, hierarchy, epdo_weights, state_key,
                                     output_dir, road_types=None, dry_run=False):
    """Generate per-county aggregates.json + meta.json for browser-side instant loading.

    For each county and each road type, produces:
      {state}/{county}/aggregates.json  — full crashState.aggregates-compatible JSON
      {state}/{county}/meta.json        — hash + timestamp for cache invalidation
    """
    if road_types is None:
        road_types = ['all_roads', 'county_roads', 'no_interstate']

    all_counties = hierarchy.get('allCounties', {})
    col_mapping = _get_col_mapping(hierarchy)
    generated_count = 0

    for fips, available_road_types in county_data.items():
        county_name = all_counties.get(fips, fips)
        # Derive the R2-compatible jurisdiction name (lowercase, underscores)
        jurisdiction_id = county_name.lower().replace(' ', '_').replace("'", '')

        for rt in road_types:
            csv_path = available_road_types.get(rt)
            if not csv_path:
                continue

            print(f"  [{fips}] {county_name} ({rt}): ", end='')

            # Parse with detailed extractor
            crashes = parse_csv_crashes_detailed(csv_path, col_mapping)
            if not crashes:
                print("0 crashes — skipped")
                continue

            # Compute full aggregates
            agg = compute_detailed_aggregates(crashes, epdo_weights)
            total_rows = len(crashes)

            # Derive years, routes, nodes lists (matches browser's finalizeData())
            years = sorted(int(y) for y in agg['byYear'].keys())
            routes = sorted(r for r in agg['byRoute'].keys() if r != 'Unknown')
            nodes = sorted(agg['byNode'].keys())

            # Build the wrapper object (matches what crashCacheSave stores)
            county_agg = {
                '_version': 1,
                '_generated': datetime.now(timezone.utc).isoformat(),
                '_generator': 'generate_aggregates.py',
                'state': state_key,
                'jurisdiction': jurisdiction_id,
                'roadType': rt,
                'totalRows': total_rows,
                'aggregates': agg,
                'years': years,
                'routes': routes,
                'nodes': nodes,
                'epdoWeights': epdo_weights,
            }

            # Write aggregates.json
            # For the default road type (all_roads), write to aggregates.json
            # For other road types, write to aggregates_{road_type}.json
            if rt == 'all_roads':
                agg_path = f'{jurisdiction_id}/aggregates.json'
            else:
                agg_path = f'{jurisdiction_id}/aggregates_{rt}.json'

            write_output(output_dir, agg_path, county_agg, dry_run)

            # Generate meta.json (hash of the aggregates for cache invalidation)
            agg_json_str = json.dumps(county_agg, sort_keys=True, default=str)
            agg_hash = hashlib.md5(agg_json_str.encode()).hexdigest()

            # Also compute CSV hash for the meta
            csv_hash = ''
            try:
                with open(csv_path, 'rb') as fh:
                    csv_hash = hashlib.md5(fh.read()).hexdigest()
            except Exception:
                pass

            meta = {
                'lastUpdated': datetime.now(timezone.utc).isoformat(),
                'rowCount': total_rows,
                'csvHash': csv_hash,
                'aggregateHash': agg_hash,
                'roadType': rt,
                'state': state_key,
                'jurisdiction': jurisdiction_id,
                'years': years,
            }

            if rt == 'all_roads':
                meta_path = f'{jurisdiction_id}/meta.json'
            else:
                meta_path = f'{jurisdiction_id}/meta_{rt}.json'

            write_output(output_dir, meta_path, meta, dry_run)

            generated_count += 1
            print(f"{total_rows} crashes, {len(routes)} routes, {len(nodes)} nodes")

    return generated_count


def generate_federal_aggregates(output_dir, states=None, dry_run=False):
    """
    Generate federal-level cross-state aggregates by combining statewide aggregates.

    Reads existing {state}/_statewide/aggregates.json files for all states
    and produces _federal/aggregates.json + _federal/state_summary.json.
    """
    if states is None:
        states = ['colorado', 'virginia']

    output_base = Path(output_dir)
    state_aggregates = {}

    for state_key in states:
        # Look for statewide aggregates in the output directory structure
        candidates = [
            output_base / state_key / '_statewide' / 'aggregates.json',
            output_base.parent / state_key / '_statewide' / 'aggregates.json',
            PROJECT_ROOT / 'data' / state_key / '_statewide' / 'aggregates.json',
        ]
        for path in candidates:
            if path.exists():
                with open(path) as f:
                    state_aggregates[state_key] = json.load(f)
                print(f"  Loaded statewide aggregates for {state_key}: {path}")
                break
        else:
            print(f"  [WARN] No statewide aggregates found for {state_key}")

    if not state_aggregates:
        print("[WARN] No state aggregates found — skipping federal generation")
        return

    # Combine statewide totals across all states
    fed_totals = {'total': 0, 'K': 0, 'A': 0, 'B': 0, 'C': 0, 'O': 0, 'epdo': 0,
                  'pedCrashes': 0, 'bikeCrashes': 0, 'speedCrashes': 0, 'alcoholCrashes': 0}
    for state_key, agg in state_aggregates.items():
        for field in fed_totals:
            fed_totals[field] += agg.get(field, 0)

    federal_agg = {
        'tier': 'federal',
        'generated': datetime.now(timezone.utc).isoformat(),
        'statesIncluded': list(state_aggregates.keys()),
        **fed_totals
    }
    write_output(str(output_base), '_federal/aggregates.json', federal_agg, dry_run)

    # State summary (ranking table)
    state_summary = {
        'tier': 'federal',
        'generated': datetime.now(timezone.utc).isoformat(),
        'states': {}
    }
    ranked = sorted(state_aggregates.items(), key=lambda x: -x[1].get('epdo', 0))
    for rank, (state_key, agg) in enumerate(ranked, 1):
        state_summary['states'][state_key] = {
            'name': agg.get('stateName', state_key),
            'rank': rank,
            'total': agg.get('total', 0),
            'K': agg.get('K', 0), 'A': agg.get('A', 0),
            'B': agg.get('B', 0), 'C': agg.get('C', 0), 'O': agg.get('O', 0),
            'epdo': agg.get('epdo', 0),
            'pedCrashes': agg.get('pedCrashes', 0),
            'bikeCrashes': agg.get('bikeCrashes', 0),
            'countiesIncluded': agg.get('countiesIncluded', 0)
        }
    write_output(str(output_base), '_federal/state_summary.json', state_summary, dry_run)

    print(f"  Federal aggregates: {len(state_aggregates)} states, {fed_totals['total']:,} total crashes")


def main():
    parser = argparse.ArgumentParser(description='Generate aggregate JSONs for CRASH LENS multi-tier views')
    parser.add_argument('--state', help='State key (colorado, virginia). Required unless --federal is used.')
    parser.add_argument('--federal', action='store_true',
                        help='Generate federal-level cross-state aggregates from existing statewide aggregates')
    parser.add_argument('--county-level', action='store_true',
                        help='Generate per-county aggregates.json + meta.json for browser-side instant loading')
    parser.add_argument('--data-dir', help='Directory containing county CSVs')
    parser.add_argument('--output-dir', help='Output directory (default: data/{STATE} or data/ for --federal)')
    parser.add_argument('--road-type', default='all_roads', choices=['all_roads', 'county_roads', 'no_interstate'],
                        help='Road type variant to aggregate (default: all_roads)')
    parser.add_argument('--dry-run', action='store_true', help='Preview output paths without writing')
    args = parser.parse_args()

    # Federal mode: generate cross-state aggregates and exit
    if args.federal:
        output_dir = args.output_dir or str(PROJECT_ROOT / 'data')
        print(f"\n{'='*60}")
        print(f"CRASH LENS — Federal Aggregate Generator")
        print(f"{'='*60}\n")
        generate_federal_aggregates(output_dir, dry_run=args.dry_run)
        print(f"\n{'='*60}")
        print(f"Federal aggregate generation {'(DRY RUN) ' if args.dry_run else ''}complete!")
        print(f"{'='*60}\n")
        return

    if not args.state:
        parser.error("--state is required unless --federal is used")

    state_key = args.state.lower()
    print(f"\n{'='*60}")
    print(f"CRASH LENS — Aggregate Generator")
    print(f"State: {state_key}")
    print(f"Road type: {args.road_type}")
    print(f"{'='*60}\n")

    # Load hierarchy
    hierarchy = load_hierarchy(state_key)
    state_info = hierarchy.get('state', {})
    print(f"State: {state_info.get('name', state_key)} ({state_info.get('abbreviation', '?')})")
    print(f"Regions: {len(hierarchy.get('regions', {}))}")
    print(f"TPRs/MPOs: {len(hierarchy.get('tprs', {}))}")
    print(f"Counties: {len(hierarchy.get('allCounties', {}))}")

    # Load state config for EPDO weights
    config = load_state_config(state_key)
    epdo_weights = get_epdo_weights(config)
    print(f"EPDO Weights: K={epdo_weights['K']}, A={epdo_weights['A']}, B={epdo_weights['B']}, C={epdo_weights['C']}, O={epdo_weights['O']}")

    # Determine data directory
    data_dir = args.data_dir
    if not data_dir:
        # Auto-detect
        candidates = [
            PROJECT_ROOT / 'data' / 'CDOT' if state_key == 'colorado' else PROJECT_ROOT / 'data',
            PROJECT_ROOT / 'data',
        ]
        for d in candidates:
            if d.exists():
                data_dir = str(d)
                break
    print(f"Data directory: {data_dir}")

    # Output directory
    output_dir = args.output_dir or str(PROJECT_ROOT / 'data' / state_key)

    # Find county CSVs
    county_data = find_county_csvs(data_dir, state_key, hierarchy)
    print(f"\nFound CSV data for {len(county_data)} counties")

    if not county_data:
        print("[WARN] No county CSVs found. Ensure data directory contains files like 'douglas_all_roads.csv'")
        return

    # ---- Generate County-Level Aggregates (--county-level) ----
    if args.county_level:
        print(f"\n--- County-Level Aggregates (all road types) ---")
        # Generate for all available road types so each county gets aggregates.json + meta.json
        road_types_to_generate = ['all_roads', 'county_roads', 'no_interstate']
        count = generate_county_level_aggregates(
            county_data, hierarchy, epdo_weights, state_key,
            output_dir, road_types=road_types_to_generate, dry_run=args.dry_run)
        print(f"\n{'='*60}")
        print(f"County-level aggregate generation {'(DRY RUN) ' if args.dry_run else ''}complete!")
        print(f"Generated {count} aggregate files across {len(county_data)} counties")
        print(f"{'='*60}\n")
        return

    # ---- Generate Statewide Aggregates ----
    print(f"\n--- Statewide Aggregates ({args.road_type}) ---")
    statewide, county_stats = generate_statewide_aggregates(county_data, hierarchy, epdo_weights, args.road_type)

    if statewide:
        # aggregates.json
        agg = {
            'state': state_key,
            'stateName': state_info.get('name', state_key),
            'period': f"{min(y['year'] for y in statewide.get('yearlyTrend', [{'year': 0}]))}-{max(y['year'] for y in statewide.get('yearlyTrend', [{'year': 0}]))}",
            'generated': datetime.now(timezone.utc).isoformat(),
            'roadType': args.road_type,
            'epdoWeights': epdo_weights,
            'epdoSource': config.get('epdoSource', 'HSM Standard 2010'),
            'countiesIncluded': len(county_stats),
            **statewide
        }
        write_output(output_dir, '_statewide/aggregates.json', agg, args.dry_run)

        # county_summary.json
        summary = {
            'state': state_key,
            'generated': datetime.now(timezone.utc).isoformat(),
            'roadType': args.road_type,
            'epdoWeights': epdo_weights,
            'statewide': {k: statewide[k] for k in ['total', 'K', 'A', 'B', 'C', 'O', 'epdo', 'trend',
                                                      'pedCrashes', 'bikeCrashes'] if k in statewide},
            'counties': {}
        }
        # Rank counties by EPDO
        ranked = sorted(county_stats.items(), key=lambda x: -x[1].get('epdo', 0))
        for rank, (fips, cs) in enumerate(ranked, 1):
            summary['counties'][fips] = {
                'name': cs['name'],
                'fips': fips,
                'rank': rank,
                'total': cs['total'],
                'K': cs['K'], 'A': cs['A'], 'B': cs['B'], 'C': cs['C'], 'O': cs['O'],
                'epdo': cs['epdo'],
                'trend': cs.get('trend', 0),
                'pedCrashes': cs.get('pedCrashes', 0),
                'bikeCrashes': cs.get('bikeCrashes', 0),
                'topCollisionTypes': cs.get('topCollisionTypes', [])[:5]
            }
        write_output(output_dir, '_statewide/county_summary.json', summary, args.dry_run)

        # Monthly snapshot
        snapshot_name = datetime.now().strftime('%Y-%m') + '_aggregates.json'
        write_output(output_dir, f'_statewide/snapshots/{snapshot_name}', agg, args.dry_run)

    # ---- Generate Region Aggregates ----
    regions = hierarchy.get('regions', {})
    if regions:
        print(f"\n--- Region Aggregates ({len(regions)} regions) ---")
        for region_id, region in regions.items():
            print(f"\n  Region: {region.get('shortName', region_id)}")
            counties = region.get('counties', [])
            group_totals, member_stats, hotspots = generate_group_aggregates(
                county_data, counties, hierarchy, epdo_weights, args.road_type)

            if group_totals:
                region_agg = {
                    'regionId': region_id,
                    'regionName': region.get('name', region_id),
                    'state': state_key,
                    'generated': datetime.now(timezone.utc).isoformat(),
                    'roadType': args.road_type,
                    'epdoWeights': epdo_weights,
                    'memberCounties': len(member_stats),
                    **group_totals,
                    'counties': {fips: {
                        'name': ms['name'], 'total': ms['total'],
                        'K': ms['K'], 'A': ms['A'], 'epdo': ms['epdo'], 'trend': ms.get('trend', 0)
                    } for fips, ms in member_stats.items()}
                }
                write_output(output_dir, f'_region/{region_id}/aggregates.json', region_agg, args.dry_run)
                write_output(output_dir, f'_region/{region_id}/hotspots.json',
                             {'regionId': region_id, 'generated': datetime.now(timezone.utc).isoformat(),
                              'hotspots': hotspots}, args.dry_run)

    # ---- Generate MPO/TPR Aggregates ----
    tprs = hierarchy.get('tprs', {})
    mpos = {k: v for k, v in tprs.items() if v.get('type') == 'mpo'}
    if mpos:
        print(f"\n--- MPO Aggregates ({len(mpos)} MPOs) ---")
        for mpo_id, mpo in mpos.items():
            print(f"\n  MPO: {mpo.get('shortName', mpo_id)}")
            counties = mpo.get('counties', [])
            group_totals, member_stats, hotspots = generate_group_aggregates(
                county_data, counties, hierarchy, epdo_weights, args.road_type)

            if group_totals:
                mpo_agg = {
                    'mpoId': mpo_id,
                    'mpoName': mpo.get('name', mpo_id),
                    'btsAcronym': mpo.get('btsAcronym'),
                    'state': state_key,
                    'generated': datetime.now(timezone.utc).isoformat(),
                    'roadType': args.road_type,
                    'epdoWeights': epdo_weights,
                    'memberCounties': len(member_stats),
                    **group_totals,
                    'counties': {fips: {
                        'name': ms['name'], 'total': ms['total'],
                        'K': ms['K'], 'A': ms['A'], 'epdo': ms['epdo'], 'trend': ms.get('trend', 0)
                    } for fips, ms in member_stats.items()}
                }
                write_output(output_dir, f'_mpo/{mpo_id}/aggregates.json', mpo_agg, args.dry_run)
                write_output(output_dir, f'_mpo/{mpo_id}/hotspots.json',
                             {'mpoId': mpo_id, 'generated': datetime.now(timezone.utc).isoformat(),
                              'hotspots': hotspots}, args.dry_run)

    print(f"\n{'='*60}")
    print(f"Aggregate generation {'(DRY RUN) ' if args.dry_run else ''}complete!")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
