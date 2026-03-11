/**
 * CrashLens MCP — Crash Data Tools (Tools 1-5)
 * query_crashes, get_crash_statistics, calculate_epdo, analyze_hotspots, build_crash_profile
 */

import { z } from 'zod';

export function registerCrashTools(server, { COL, calcEPDO, getStateEPDOWeights, EPDO_WEIGHTS_DEFAULT, buildLocationCrashProfile, buildDetailedLocationProfile, scoreAndRank, dataLoader }) {

  // TOOL 1: query_crashes
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

  // TOOL 2: get_crash_statistics
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

  // TOOL 3: calculate_epdo
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

  // TOOL 4: analyze_hotspots
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

  // TOOL 5: build_crash_profile
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
}
