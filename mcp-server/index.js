#!/usr/bin/env node

/**
 * CrashLens MCP Server
 * Exposes crash data analysis tools to Claude Code and AI assistants via stdio transport.
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

// Analysis modules
import { COL, STATE_EPDO_WEIGHTS, EPDO_WEIGHTS_DEFAULT } from './lib/constants.js';
import { calcEPDO, getStateEPDOWeights } from './lib/epdo.js';
import { buildLocationCrashProfile, buildDetailedLocationProfile } from './lib/crash-profile.js';
import { calculateCountyBaselines, calculateORI, testPatternSignificance, calculatePSI } from './lib/baselines.js';
import { scoreAndRank } from './lib/hotspots.js';
import { interpolateThreshold, getLaneConfig, getReductionFactor, WARRANT_1_CURVES } from './lib/signal-warrant.js';
import { scoreGrantEligibility } from './lib/grant-ranking.js';
import * as dataLoader from './lib/data-loader.js';

// Resolve project root (parent of mcp-server/)
const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(__dirname, '..');

// Initialize data loader
dataLoader.init(PROJECT_ROOT);

// Create MCP server
const server = new McpServer({
  name: 'crashlens',
  version: '1.0.0',
  description: 'Crash Lens — Traffic safety crash data analysis tools'
});

// ============================================================
// TOOL 1: query_crashes
// ============================================================
server.tool(
  'query_crashes',
  'Query crash records with flexible filters (route, severity, date range, collision type, weather, contributing factors). Returns matching crash summaries.',
  {
    route: z.string().optional().describe('Filter by route/road name (partial match)'),
    node: z.string().optional().describe('Filter by intersection node ID (partial match)'),
    severity: z.array(z.enum(['K', 'A', 'B', 'C', 'O'])).optional().describe('Filter by severity levels'),
    date_start: z.string().optional().describe('Start date (YYYY-MM-DD)'),
    date_end: z.string().optional().describe('End date (YYYY-MM-DD)'),
    collision_type: z.string().optional().describe('Filter by collision type (partial match)'),
    weather: z.string().optional().describe('Filter by weather condition (partial match)'),
    factors: z.array(z.string()).optional().describe('Contributing factors: ped, bike, alcohol, speed, distracted, night, hitrun'),
    limit: z.number().optional().default(100).describe('Max records to return (default 100)')
  },
  async (params) => {
    const filtered = dataLoader.filterCrashes(params);
    const total = filtered.length;
    const limit = params.limit || 100;
    const results = filtered.slice(0, limit).map(row => ({
      id: row[COL.ID] || '',
      date: row[COL.DATE] || '',
      year: row[COL.YEAR] || '',
      severity: row[COL.SEVERITY] || '',
      route: row[COL.ROUTE] || '',
      node: row[COL.NODE] || '',
      collision: row[COL.COLLISION] || '',
      weather: row[COL.WEATHER] || '',
      light: row[COL.LIGHT] || '',
      ped: row[COL.PED] || '',
      bike: row[COL.BIKE] || '',
      alcohol: row[COL.ALCOHOL] || '',
      speed: row[COL.SPEED] || '',
      x: row[COL.X] || '',
      y: row[COL.Y] || '',
      jurisdiction: row[COL.JURISDICTION] || ''
    }));

    return {
      content: [{ type: 'text', text: JSON.stringify({ dataContext: dataLoader.getDataContext(), total, returned: results.length, limit, crashes: results }, null, 2) }]
    };
  }
);

// ============================================================
// TOOL 2: get_crash_statistics
// ============================================================
server.tool(
  'get_crash_statistics',
  'Get aggregate crash statistics — county-wide or for a specific route/intersection. Includes severity breakdown, EPDO, collision types, contributing factors.',
  {
    route: z.string().optional().describe('Route name to analyze'),
    node: z.string().optional().describe('Intersection node to analyze'),
    date_start: z.string().optional().describe('Start date (YYYY-MM-DD)'),
    date_end: z.string().optional().describe('End date (YYYY-MM-DD)')
  },
  async (params) => {
    const crashes = dataLoader.filterCrashes(params);
    if (crashes.length === 0) {
      return { content: [{ type: 'text', text: JSON.stringify({ error: 'No crashes found matching criteria' }) }] };
    }

    const profile = buildDetailedLocationProfile(crashes);
    const simple = buildLocationCrashProfile(crashes);

    return {
      content: [{ type: 'text', text: JSON.stringify({
        dataContext: dataLoader.getDataContext(),
        total: crashes.length,
        severity: { K: simple.K, A: simple.A, B: simple.B, C: simple.C, O: simple.O },
        epdo: profile.epdo,
        collisionTypes: profile.collisionTypes,
        contributingFactors: profile.contributingFactors,
        weatherConditions: profile.weatherDist,
        lightConditions: profile.lightDist,
        pedestrianInvolved: profile.pedInvolved,
        bicycleInvolved: profile.bikeInvolved,
        temporal: profile.extended.peakPeriods,
        weekdayVsWeekend: { weekday: profile.extended.weekday, weekend: profile.extended.weekend },
        byYear: profile.extended.byYear
      }, null, 2) }]
    };
  }
);

// ============================================================
// TOOL 3: calculate_epdo
// ============================================================
server.tool(
  'calculate_epdo',
  'Calculate EPDO (Equivalent Property Damage Only) score from severity counts. Optionally specify a state FIPS code to use state-specific weights.',
  {
    K: z.number().describe('Fatal crash count'),
    A: z.number().describe('Serious injury (A) crash count'),
    B: z.number().describe('Minor injury (B) crash count'),
    C: z.number().describe('Possible injury (C) crash count'),
    O: z.number().describe('Property damage only (O) crash count'),
    state_fips: z.string().optional().describe('State FIPS code for state-specific weights (e.g., "51" for Virginia)')
  },
  async (params) => {
    const stateInfo = params.state_fips
      ? getStateEPDOWeights(params.state_fips)
      : { name: 'HSM Standard (2010)', weights: EPDO_WEIGHTS_DEFAULT, source: 'Highway Safety Manual standard' };

    const epdo = calcEPDO(
      { K: params.K, A: params.A, B: params.B, C: params.C, O: params.O },
      stateInfo.weights
    );

    return {
      content: [{ type: 'text', text: JSON.stringify({
        epdo,
        weights: stateInfo.weights,
        weightSource: stateInfo.name,
        source: stateInfo.source,
        breakdown: {
          K: params.K * stateInfo.weights.K,
          A: params.A * stateInfo.weights.A,
          B: params.B * stateInfo.weights.B,
          C: params.C * stateInfo.weights.C,
          O: params.O * stateInfo.weights.O
        }
      }, null, 2) }]
    };
  }
);

// ============================================================
// TOOL 4: analyze_hotspots
// ============================================================
server.tool(
  'analyze_hotspots',
  'Identify and rank crash hotspot locations by EPDO, total crashes, KA severity, or crashes per year.',
  {
    type: z.enum(['route', 'intersection']).describe('Analyze by route or intersection'),
    min_crashes: z.number().optional().default(5).describe('Minimum crashes to qualify (default 5)'),
    sort_by: z.enum(['epdo', 'total', 'ka', 'perYear']).optional().default('epdo').describe('Sort/rank by'),
    limit: z.number().optional().default(20).describe('Max hotspots to return (default 20)')
  },
  async (params) => {
    const agg = dataLoader.buildAggregates();
    const sourceData = params.type === 'intersection' ? agg.byNode : agg.byRoute;
    const years = Object.keys(agg.byYear);
    const numYears = years.length || 1;

    const hotspots = scoreAndRank(
      sourceData,
      params.min_crashes || 5,
      params.sort_by || 'epdo',
      numYears,
      (d) => calcEPDO(d)
    );

    const limit = params.limit || 20;
    return {
      content: [{ type: 'text', text: JSON.stringify({
        dataContext: dataLoader.getDataContext(),
        type: params.type,
        totalLocations: Object.keys(sourceData).length,
        qualifyingLocations: hotspots.length,
        dataYears: numYears,
        sortedBy: params.sort_by || 'epdo',
        hotspots: hotspots.slice(0, limit)
      }, null, 2) }]
    };
  }
);

// ============================================================
// TOOL 5: build_crash_profile
// ============================================================
server.tool(
  'build_crash_profile',
  'Generate a detailed crash profile for a specific route or intersection. Includes severity, collision types, weather, light, contributing factors, temporal patterns.',
  {
    route: z.string().optional().describe('Route name'),
    node: z.string().optional().describe('Intersection node ID'),
    date_start: z.string().optional().describe('Start date (YYYY-MM-DD)'),
    date_end: z.string().optional().describe('End date (YYYY-MM-DD)')
  },
  async (params) => {
    if (!params.route && !params.node) {
      return { content: [{ type: 'text', text: JSON.stringify({ error: 'At least one of route or node is required' }) }] };
    }

    const crashes = dataLoader.filterCrashes(params);
    if (crashes.length === 0) {
      return { content: [{ type: 'text', text: JSON.stringify({ error: 'No crashes found for this location' }) }] };
    }

    const profile = buildDetailedLocationProfile(crashes);
    // Remove raw speed diffs array for cleaner output
    delete profile.extended.speedDiffs;

    return {
      content: [{ type: 'text', text: JSON.stringify({
        dataContext: dataLoader.getDataContext(),
        location: { route: params.route || null, node: params.node || null },
        profile
      }, null, 2) }]
    };
  }
);

// ============================================================
// TOOL 6: calculate_baselines
// ============================================================
server.tool(
  'calculate_baselines',
  'Calculate county-wide baseline crash rates for statistical comparison. Returns severity rates, pattern rates, and per-location averages.',
  {},
  async () => {
    const rows = dataLoader.loadCrashData();
    const agg = dataLoader.buildAggregates();
    const baselines = calculateCountyBaselines(rows, agg);

    if (!baselines) {
      return { content: [{ type: 'text', text: JSON.stringify({ error: 'No crash data loaded' }) }] };
    }

    return {
      content: [{ type: 'text', text: JSON.stringify({ dataContext: dataLoader.getDataContext(), ...baselines }, null, 2) }]
    };
  }
);

// ============================================================
// TOOL 7: analyze_over_representation
// ============================================================
server.tool(
  'analyze_over_representation',
  'Calculate Over-Representation Index (ORI) for a location vs county baselines. Identifies statistically significant crash patterns.',
  {
    route: z.string().optional().describe('Route name'),
    node: z.string().optional().describe('Intersection node ID')
  },
  async (params) => {
    if (!params.route && !params.node) {
      return { content: [{ type: 'text', text: JSON.stringify({ error: 'At least one of route or node is required' }) }] };
    }

    const crashes = dataLoader.filterCrashes(params);
    if (crashes.length === 0) {
      return { content: [{ type: 'text', text: JSON.stringify({ error: 'No crashes found for this location' }) }] };
    }

    const rows = dataLoader.loadCrashData();
    const agg = dataLoader.buildAggregates();
    const baselines = calculateCountyBaselines(rows, agg);
    const patterns = dataLoader.analyzeCrashPatterns(crashes);
    const ori = calculateORI(patterns, baselines);
    const significance = testPatternSignificance(patterns, baselines);

    return {
      content: [{ type: 'text', text: JSON.stringify({
        dataContext: dataLoader.getDataContext(),
        location: { route: params.route || null, node: params.node || null },
        crashCount: crashes.length,
        patterns,
        overRepresentation: ori,
        significance
      }, null, 2) }]
    };
  }
);

// ============================================================
// TOOL 8: evaluate_signal_warrant
// ============================================================
server.tool(
  'evaluate_signal_warrant',
  'Evaluate MUTCD signal warrant criteria for an intersection based on traffic volumes.',
  {
    major_volume: z.number().describe('Major street hourly volume (vehicles/hour)'),
    minor_volume: z.number().describe('Minor street hourly volume (vehicles/hour)'),
    major_lanes: z.number().describe('Number of major street approach lanes'),
    minor_lanes: z.number().describe('Number of minor street approach lanes'),
    community_pop: z.number().optional().default(50000).describe('Community population (affects reduction factor)'),
    speed_limit: z.number().optional().default(35).describe('Speed limit (mph)')
  },
  async (params) => {
    const laneConfig = getLaneConfig(params.major_lanes, params.minor_lanes);
    const reductionFactor = getReductionFactor({
      communityPop: params.community_pop || 50000,
      speedLimit: params.speed_limit || 35,
      apply70pct: false
    });

    const curves = WARRANT_1_CURVES[laneConfig] || WARRANT_1_CURVES['1x1'];
    const curve = curves[reductionFactor] || curves.p100;
    const threshold = interpolateThreshold(curve, params.major_volume);
    const met = params.minor_volume >= threshold;

    return {
      content: [{ type: 'text', text: JSON.stringify({
        warrant1: {
          met,
          majorVolume: params.major_volume,
          minorVolume: params.minor_volume,
          minorThreshold: threshold,
          laneConfig,
          reductionFactor,
          description: met
            ? `Warrant 1 MET: Minor volume (${params.minor_volume}) >= threshold (${threshold})`
            : `Warrant 1 NOT MET: Minor volume (${params.minor_volume}) < threshold (${threshold})`
        },
        parameters: {
          majorLanes: params.major_lanes,
          minorLanes: params.minor_lanes,
          communityPop: params.community_pop || 50000,
          speedLimit: params.speed_limit || 35
        }
      }, null, 2) }]
    };
  }
);

// ============================================================
// TOOL 9: score_grant_eligibility
// ============================================================
server.tool(
  'score_grant_eligibility',
  'Score a location for traffic safety grant funding eligibility. Evaluates fit for HSIP, SS4A, 402, and 405d programs.',
  {
    route: z.string().optional().describe('Route name'),
    node: z.string().optional().describe('Intersection node ID'),
    scoring_profile: z.enum(['balanced', 'hsip', 'ss4a', '402', '405d']).optional().default('balanced').describe('Scoring focus')
  },
  async (params) => {
    if (!params.route && !params.node) {
      return { content: [{ type: 'text', text: JSON.stringify({ error: 'At least one of route or node is required' }) }] };
    }

    const crashes = dataLoader.filterCrashes(params);
    if (crashes.length === 0) {
      return { content: [{ type: 'text', text: JSON.stringify({ error: 'No crashes found for this location' }) }] };
    }

    const rows = dataLoader.loadCrashData();
    const agg = dataLoader.buildAggregates();
    const baselines = calculateCountyBaselines(rows, agg);
    const patterns = dataLoader.analyzeCrashPatterns(crashes);

    // Build locationData from crashes
    const locationData = {
      total: crashes.length,
      K: patterns.K, A: patterns.A, B: patterns.B, C: patterns.C, O: patterns.O,
      type: params.node ? 'intersection' : 'segment',
      name: params.node || params.route
    };

    const result = scoreGrantEligibility(locationData, patterns, baselines, params.scoring_profile || 'balanced');

    return {
      content: [{ type: 'text', text: JSON.stringify({
        dataContext: dataLoader.getDataContext(),
        location: { route: params.route || null, node: params.node || null },
        crashCount: crashes.length,
        scoringProfile: params.scoring_profile || 'balanced',
        ...result
      }, null, 2) }]
    };
  }
);

// ============================================================
// TOOL 10: get_forecasts
// ============================================================
server.tool(
  'get_forecasts',
  'Get crash forecasts for a state/jurisdiction. Returns predicted crash trends.',
  {
    state: z.string().describe('State name (e.g., "virginia")'),
    jurisdiction: z.string().describe('Jurisdiction/county name (e.g., "henrico")'),
    road_type: z.enum(['all_roads', 'county_roads', 'no_interstate']).optional().default('all_roads').describe('Road type filter')
  },
  async (params) => {
    const forecasts = dataLoader.loadForecasts(params.state, params.jurisdiction, params.road_type || 'all_roads');
    if (!forecasts) {
      return { content: [{ type: 'text', text: JSON.stringify({ error: `No forecasts found for ${params.state}/${params.jurisdiction}/${params.road_type || 'all_roads'}` }) }] };
    }

    return {
      content: [{ type: 'text', text: JSON.stringify({
        dataContext: dataLoader.getDataContext(),
        state: params.state,
        jurisdiction: params.jurisdiction,
        roadType: params.road_type || 'all_roads',
        forecasts
      }, null, 2) }]
    };
  }
);

// ============================================================
// TOOL 11: search_grants
// ============================================================
server.tool(
  'search_grants',
  'Search available traffic safety grants. Filter by program, keyword, or status.',
  {
    program: z.string().optional().describe('Grant program (HSIP, SS4A, 402, 405b, 405c, 405d)'),
    keyword: z.string().optional().describe('Keyword search in grant title/description'),
    status: z.string().optional().describe('Grant status filter')
  },
  async (params) => {
    let grants = dataLoader.loadGrantData();

    if (params.program) {
      const prog = params.program.toLowerCase();
      grants = grants.filter(g => {
        const title = (g.Title || g.title || '').toLowerCase();
        const desc = (g.Description || g.description || '').toLowerCase();
        const cfda = (g.CFDA || g.cfda || '').toLowerCase();
        return title.includes(prog) || desc.includes(prog) || cfda.includes(prog);
      });
    }

    if (params.keyword) {
      const kw = params.keyword.toLowerCase();
      grants = grants.filter(g => {
        const title = (g.Title || g.title || '').toLowerCase();
        const desc = (g.Description || g.description || '').toLowerCase();
        return title.includes(kw) || desc.includes(kw);
      });
    }

    if (params.status) {
      const st = params.status.toLowerCase();
      grants = grants.filter(g => (g.Status || g.status || '').toLowerCase().includes(st));
    }

    return {
      content: [{ type: 'text', text: JSON.stringify({
        dataContext: dataLoader.getDataContext(),
        total: grants.length,
        grants: grants.slice(0, 50)
      }, null, 2) }]
    };
  }
);

// ============================================================
// TOOL 12: get_jurisdiction_info
// ============================================================
server.tool(
  'get_jurisdiction_info',
  'Get jurisdiction metadata, available configurations, and EPDO weights for a state.',
  {
    state_fips: z.string().optional().describe('State FIPS code (e.g., "51" for Virginia)'),
    state_name: z.string().optional().describe('State name (e.g., "virginia")')
  },
  async (params) => {
    const result = {};

    if (params.state_fips) {
      result.epdoWeights = getStateEPDOWeights(params.state_fips);
    }

    if (params.state_name) {
      const stateConfig = dataLoader.loadStateConfig(params.state_name);
      if (stateConfig) {
        result.stateConfig = stateConfig;
      } else {
        result.stateConfigError = `No config found for state: ${params.state_name}`;
      }
    }

    result.availableStates = dataLoader.listStates();

    const config = dataLoader.loadConfig();
    if (config.jurisdictions) {
      const jurisdictionList = Object.entries(config.jurisdictions).map(([key, val]) => ({
        key,
        name: val.name || key,
        state: val.state || '',
        fips: val.fips || ''
      }));
      result.jurisdictionCount = jurisdictionList.length;
      // Return first 20 as sample
      result.jurisdictionSample = jurisdictionList.slice(0, 20);
    }

    return {
      content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
    };
  }
);

// ============================================================
// RESOURCES
// ============================================================

server.resource(
  'data-summary',
  'crashlens://data/summary',
  async (uri) => {
    const summary = dataLoader.getDataSummary();
    return {
      contents: [{ uri: uri.href, mimeType: 'application/json', text: JSON.stringify({ dataContext: dataLoader.getDataContext(), ...summary }, null, 2) }]
    };
  }
);

server.resource(
  'epdo-weights',
  'crashlens://config/epdo-weights',
  async (uri) => {
    return {
      contents: [{ uri: uri.href, mimeType: 'application/json', text: JSON.stringify(STATE_EPDO_WEIGHTS, null, 2) }]
    };
  }
);

server.resource(
  'available-states',
  'crashlens://config/states',
  async (uri) => {
    const states = dataLoader.listStates();
    return {
      contents: [{ uri: uri.href, mimeType: 'application/json', text: JSON.stringify({ states }, null, 2) }]
    };
  }
);

// ============================================================
// START SERVER
// ============================================================
async function main() {
  const transport = new StdioServerTransport();
  console.error('[CrashLens MCP] Starting server...');

  // Pre-load data
  try {
    dataLoader.loadCrashData();
    dataLoader.buildAggregates();
    const ctx = dataLoader.getDataContext();
    console.error(`[CrashLens MCP] Data loaded: ${ctx.jurisdiction} — ${ctx.totalRecords} records (${ctx.dateRange})`);
  } catch (err) {
    console.error('[CrashLens MCP] Warning: Could not pre-load data:', err.message);
  }

  await server.connect(transport);
  console.error('[CrashLens MCP] Server running on stdio');
}

main().catch(err => {
  console.error('[CrashLens MCP] Fatal error:', err);
  process.exit(1);
});
