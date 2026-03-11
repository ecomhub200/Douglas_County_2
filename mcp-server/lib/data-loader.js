/**
 * CrashLens Data Loader — loads and caches crash data, grants, configs
 */

import { readFileSync, existsSync, readdirSync } from 'fs';
import { resolve, join } from 'path';
import { parse } from 'csv-parse/sync';
import { COL, CRASH_PATTERN_REGEX } from './constants.js';
import { isYes } from './epdo.js';

// Cached data store
let _crashData = null;
let _grantData = null;
let _cmfData = null;
let _cmfMetadata = null;
let _aggregates = null;
let _config = null;
let _stateConfigs = {};
let _projectRoot = null;

/**
 * Initialize the data loader with project root path.
 */
export function init(projectRoot) {
  _projectRoot = projectRoot;
}

/**
 * Get project root, auto-detecting if not set.
 */
function getRoot() {
  if (_projectRoot) return _projectRoot;
  // Try to detect from current working directory
  let dir = process.cwd();
  while (dir !== '/') {
    if (existsSync(join(dir, 'config.json')) && existsSync(join(dir, 'data'))) {
      _projectRoot = dir;
      return dir;
    }
    dir = resolve(dir, '..');
  }
  _projectRoot = process.cwd();
  return _projectRoot;
}

/**
 * Load and parse crash CSV data.
 */
export function loadCrashData() {
  if (_crashData) return _crashData;

  const root = getRoot();
  const csvPath = join(root, 'data', 'all_roads.csv');
  if (!existsSync(csvPath)) {
    console.error(`[CrashLens MCP] Crash data file not found: ${csvPath}`);
    _crashData = [];
    return _crashData;
  }

  const csvContent = readFileSync(csvPath, 'utf-8');
  _crashData = parse(csvContent, {
    columns: true,
    skip_empty_lines: true,
    trim: true,
    relax_column_count: true
  });

  console.error(`[CrashLens MCP] Loaded ${_crashData.length} crash records from ${csvPath}`);
  return _crashData;
}

/**
 * Load and parse grant CSV data.
 */
export function loadGrantData() {
  if (_grantData) return _grantData;

  const root = getRoot();
  const csvPath = join(root, 'data', 'grants.csv');
  if (!existsSync(csvPath)) {
    console.error(`[CrashLens MCP] Grants file not found: ${csvPath}`);
    _grantData = [];
    return _grantData;
  }

  const csvContent = readFileSync(csvPath, 'utf-8');
  _grantData = parse(csvContent, {
    columns: true,
    skip_empty_lines: true,
    trim: true,
    relax_column_count: true
  });

  console.error(`[CrashLens MCP] Loaded ${_grantData.length} grant records`);
  return _grantData;
}

/**
 * Build aggregates from crash data (byRoute, byNode, bySeverity, etc.)
 */
export function buildAggregates() {
  if (_aggregates) return _aggregates;

  const rows = loadCrashData();
  const agg = {
    bySeverity: { K: 0, A: 0, B: 0, C: 0, O: 0 },
    byRoute: {},
    byNode: {},
    byCollision: {},
    byWeather: {},
    byLight: {},
    byYear: {},
    ped: { total: 0 },
    bike: { total: 0 },
    intersection: { total: 0 },
    totalRows: rows.length
  };

  for (const row of rows) {
    const sev = (row[COL.SEVERITY] || 'O').charAt(0).toUpperCase();
    if (agg.bySeverity[sev] !== undefined) agg.bySeverity[sev]++;
    else agg.bySeverity.O++;

    // By route
    const route = (row[COL.ROUTE] || '').trim();
    if (route) {
      if (!agg.byRoute[route]) {
        agg.byRoute[route] = { total: 0, K: 0, A: 0, B: 0, C: 0, O: 0, collisions: {}, jurisdiction: '' };
      }
      agg.byRoute[route].total++;
      if (agg.byRoute[route][sev] !== undefined) agg.byRoute[route][sev]++;
      const collision = (row[COL.COLLISION] || '').trim();
      if (collision) agg.byRoute[route].collisions[collision] = (agg.byRoute[route].collisions[collision] || 0) + 1;
      if (!agg.byRoute[route].jurisdiction && row[COL.JURISDICTION]) {
        agg.byRoute[route].jurisdiction = row[COL.JURISDICTION];
      }
    }

    // By node
    const node = (row[COL.NODE] || '').trim();
    if (node) {
      if (!agg.byNode[node]) {
        agg.byNode[node] = { total: 0, K: 0, A: 0, B: 0, C: 0, O: 0, collisions: {}, routes: new Set(), jurisdiction: '' };
      }
      agg.byNode[node].total++;
      if (agg.byNode[node][sev] !== undefined) agg.byNode[node][sev]++;
      if (route) agg.byNode[node].routes.add(route);
      const collision = (row[COL.COLLISION] || '').trim();
      if (collision) agg.byNode[node].collisions[collision] = (agg.byNode[node].collisions[collision] || 0) + 1;
      if (!agg.byNode[node].jurisdiction && row[COL.JURISDICTION]) {
        agg.byNode[node].jurisdiction = row[COL.JURISDICTION];
      }
    }

    // By collision type
    const collType = (row[COL.COLLISION] || '').trim();
    if (collType) agg.byCollision[collType] = (agg.byCollision[collType] || 0) + 1;

    // By weather
    const weather = (row[COL.WEATHER] || '').trim();
    if (weather) agg.byWeather[weather] = (agg.byWeather[weather] || 0) + 1;

    // By light
    const light = (row[COL.LIGHT] || '').trim();
    if (light) agg.byLight[light] = (agg.byLight[light] || 0) + 1;

    // By year
    const year = row[COL.YEAR] || '';
    if (year) agg.byYear[year] = (agg.byYear[year] || 0) + 1;

    // Ped/Bike
    if (isYes(row[COL.PED])) agg.ped.total++;
    if (isYes(row[COL.BIKE])) agg.bike.total++;

    // Intersection
    const intType = row[COL.INT_TYPE] || '';
    if (intType && !intType.toLowerCase().includes('non') && !intType.toLowerCase().includes('not')) {
      agg.intersection.total++;
    }
  }

  _aggregates = agg;
  return agg;
}

/**
 * Load the main config.json.
 */
export function loadConfig() {
  if (_config) return _config;

  const root = getRoot();
  const configPath = join(root, 'config.json');
  if (!existsSync(configPath)) {
    _config = {};
    return _config;
  }

  _config = JSON.parse(readFileSync(configPath, 'utf-8'));
  return _config;
}

/**
 * Load a state-specific config.
 */
export function loadStateConfig(stateName) {
  const key = stateName.toLowerCase().replace(/\s+/g, '_');
  if (_stateConfigs[key]) return _stateConfigs[key];

  const root = getRoot();
  const configPath = join(root, 'states', key, 'config.json');
  if (!existsSync(configPath)) return null;

  _stateConfigs[key] = JSON.parse(readFileSync(configPath, 'utf-8'));
  return _stateConfigs[key];
}

/**
 * List available states with configs.
 */
export function listStates() {
  const root = getRoot();
  const statesDir = join(root, 'states');
  if (!existsSync(statesDir)) return [];

  return readdirSync(statesDir, { withFileTypes: true })
    .filter(d => d.isDirectory())
    .map(d => d.name)
    .filter(name => existsSync(join(statesDir, name, 'config.json')));
}

/**
 * Load forecast data for a jurisdiction.
 */
export function loadForecasts(state, jurisdiction, roadType = 'all_roads') {
  const root = getRoot();
  const forecastPath = join(root, 'data', state.toLowerCase(), jurisdiction.toLowerCase(), `forecasts_${roadType}.json`);
  if (!existsSync(forecastPath)) return null;

  return JSON.parse(readFileSync(forecastPath, 'utf-8'));
}

/**
 * Filter crash rows by criteria.
 */
export function filterCrashes(options = {}) {
  const rows = loadCrashData();
  let filtered = rows;

  if (options.route) {
    const r = options.route.toLowerCase();
    filtered = filtered.filter(row => (row[COL.ROUTE] || '').toLowerCase().includes(r));
  }
  if (options.node) {
    const n = options.node.toLowerCase();
    filtered = filtered.filter(row => (row[COL.NODE] || '').toLowerCase().includes(n));
  }
  if (options.severity && options.severity.length > 0) {
    const sevSet = new Set(options.severity.map(s => s.toUpperCase()));
    filtered = filtered.filter(row => sevSet.has((row[COL.SEVERITY] || 'O').charAt(0).toUpperCase()));
  }
  if (options.date_start) {
    const start = new Date(options.date_start);
    filtered = filtered.filter(row => {
      const d = row[COL.DATE];
      if (!d) return false;
      return new Date(Number(d) || d) >= start;
    });
  }
  if (options.date_end) {
    const end = new Date(options.date_end);
    filtered = filtered.filter(row => {
      const d = row[COL.DATE];
      if (!d) return false;
      return new Date(Number(d) || d) <= end;
    });
  }
  if (options.collision_type) {
    const ct = options.collision_type.toLowerCase();
    filtered = filtered.filter(row => (row[COL.COLLISION] || '').toLowerCase().includes(ct));
  }
  if (options.weather) {
    const w = options.weather.toLowerCase();
    filtered = filtered.filter(row => (row[COL.WEATHER] || '').toLowerCase().includes(w));
  }
  if (options.factors && options.factors.length > 0) {
    for (const factor of options.factors) {
      const f = factor.toLowerCase();
      if (f === 'ped' || f === 'pedestrian') filtered = filtered.filter(row => isYes(row[COL.PED]));
      else if (f === 'bike' || f === 'bicycle') filtered = filtered.filter(row => isYes(row[COL.BIKE]));
      else if (f === 'alcohol') filtered = filtered.filter(row => isYes(row[COL.ALCOHOL]));
      else if (f === 'speed') filtered = filtered.filter(row => isYes(row[COL.SPEED]));
      else if (f === 'distracted') filtered = filtered.filter(row => isYes(row[COL.DISTRACTED]));
      else if (f === 'night') filtered = filtered.filter(row => isYes(row[COL.NIGHT]));
      else if (f === 'hitrun') filtered = filtered.filter(row => isYes(row[COL.HITRUN]));
    }
  }

  return filtered;
}

/**
 * Analyze crash patterns at a location for ORI/significance use.
 */
export function analyzeCrashPatterns(crashes) {
  const patterns = {
    total: crashes.length,
    K: 0, A: 0, B: 0, C: 0, O: 0,
    night: 0, impaired: 0, speed: 0,
    angle: 0, headOn: 0, rearEnd: 0,
    runOff: 0, wet: 0,
    ped: 0, bike: 0
  };

  for (const row of crashes) {
    const sev = (row[COL.SEVERITY] || 'O').charAt(0).toUpperCase();
    if (patterns[sev] !== undefined) patterns[sev]++;

    const light = (row[COL.LIGHT] || '').toLowerCase();
    if (CRASH_PATTERN_REGEX.nightLight.test(light)) patterns.night++;

    const collision = (row[COL.COLLISION] || '').toLowerCase();
    if (CRASH_PATTERN_REGEX.angleCollision.test(collision)) patterns.angle++;
    if (CRASH_PATTERN_REGEX.headOnCollision.test(collision)) patterns.headOn++;
    if (CRASH_PATTERN_REGEX.rearEndCollision.test(collision)) patterns.rearEnd++;
    if (CRASH_PATTERN_REGEX.runOffRoad.test(collision)) patterns.runOff++;

    const weather = (row[COL.WEATHER] || '').toLowerCase();
    if (CRASH_PATTERN_REGEX.wetSurface.test(weather)) patterns.wet++;

    if (isYes(row[COL.ALCOHOL]) || isYes(row[COL.DRUG])) patterns.impaired++;
    if (isYes(row[COL.SPEED])) patterns.speed++;
    if (isYes(row[COL.PED])) patterns.ped++;
    if (isYes(row[COL.BIKE])) patterns.bike++;
  }

  return patterns;
}

/**
 * Load CMF (Crash Modification Factor) database.
 */
export function loadCMFData() {
  if (_cmfData) return _cmfData;

  const root = getRoot();
  const jsonPath = join(root, 'data', 'cmf_processed.json');
  if (!existsSync(jsonPath)) {
    console.error(`[CrashLens MCP] CMF data file not found: ${jsonPath}`);
    _cmfData = { records: [], categories: [], indexes: {} };
    return _cmfData;
  }

  _cmfData = JSON.parse(readFileSync(jsonPath, 'utf-8'));
  console.error(`[CrashLens MCP] Loaded ${_cmfData.records.length} CMF records`);
  return _cmfData;
}

/**
 * Get CMF records array.
 */
export function getCMFRecords() {
  return loadCMFData().records;
}

/**
 * Get CMF categories array.
 */
export function getCMFCategories() {
  return loadCMFData().categories;
}

/**
 * Get CMF metadata (stats, version info).
 */
export function getCMFMetadata() {
  if (_cmfMetadata) return _cmfMetadata;

  const root = getRoot();
  const metaPath = join(root, 'data', 'cmf_metadata.json');
  if (!existsSync(metaPath)) {
    return loadCMFData().stats || {};
  }

  _cmfMetadata = JSON.parse(readFileSync(metaPath, 'utf-8'));
  return _cmfMetadata;
}

/**
 * Get a summary of the loaded data.
 */
export function getDataSummary() {
  const rows = loadCrashData();
  const agg = buildAggregates();

  const years = Object.keys(agg.byYear).sort();
  const routes = Object.keys(agg.byRoute);
  const nodes = Object.keys(agg.byNode);
  const jurisdictions = new Set();
  for (const row of rows) {
    const j = row[COL.JURISDICTION];
    if (j) jurisdictions.add(j);
  }

  return {
    totalRecords: rows.length,
    dateRange: years.length > 0 ? { start: years[0], end: years[years.length - 1] } : null,
    yearBreakdown: agg.byYear,
    severityBreakdown: agg.bySeverity,
    routeCount: routes.length,
    intersectionCount: nodes.length,
    jurisdictions: Array.from(jurisdictions).sort(),
    pedestrianCrashes: agg.ped.total,
    bicycleCrashes: agg.bike.total,
    intersectionCrashes: agg.intersection.total
  };
}
