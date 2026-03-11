/**
 * CrashLens MCP — Infrastructure & Discovery Tools (Tools 8-12, 21-22)
 * evaluate_signal_warrant, score_grant_eligibility, get_forecasts, search_grants,
 * get_jurisdiction_info, list_locations, get_data_quality
 */

import { z } from 'zod';

export function registerInfrastructureTools(server, { COL, calcEPDO, getStateEPDOWeights, calculateCountyBaselines, interpolateThreshold, getLaneConfig, getReductionFactor, WARRANT_1_CURVES, scoreGrantEligibility, dataLoader }) {

  // TOOL 8: evaluate_signal_warrant
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

  // TOOL 9: score_grant_eligibility
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

      const locationData = {
        total: crashes.length,
        K: patterns.K, A: patterns.A, B: patterns.B, C: patterns.C, O: patterns.O,
        type: params.node ? 'intersection' : 'segment',
        name: params.node || params.route
      };

      const result = scoreGrantEligibility(locationData, patterns, baselines, params.scoring_profile || 'balanced');

      return {
        content: [{ type: 'text', text: JSON.stringify({
          location: { route: params.route || null, node: params.node || null },
          crashCount: crashes.length,
          scoringProfile: params.scoring_profile || 'balanced',
          ...result
        }, null, 2) }]
      };
    }
  );

  // TOOL 10: get_forecasts
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
          state: params.state,
          jurisdiction: params.jurisdiction,
          roadType: params.road_type || 'all_roads',
          forecasts
        }, null, 2) }]
      };
    }
  );

  // TOOL 11: search_grants
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
          total: grants.length,
          grants: grants.slice(0, 50)
        }, null, 2) }]
      };
    }
  );

  // TOOL 12: get_jurisdiction_info
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
        result.jurisdictionSample = jurisdictionList.slice(0, 20);
      }

      return {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
      };
    }
  );

  // TOOL 21: list_locations
  server.tool(
    'list_locations',
    'List available routes and intersections in the crash data with crash counts. Useful for discovering what locations exist before running analysis.',
    {
      type: z.enum(['routes', 'intersections', 'both']).optional().default('both').describe('Type of locations to list'),
      min_crashes: z.number().optional().default(1).describe('Minimum crash count to include'),
      search: z.string().optional().describe('Search/filter by name (partial match)'),
      sort_by: z.enum(['name', 'total', 'epdo']).optional().default('total').describe('Sort order'),
      limit: z.number().optional().default(50).describe('Max locations to return')
    },
    async (params) => {
      const agg = dataLoader.buildAggregates();
      const minCrashes = params.min_crashes || 1;
      const limit = params.limit || 50;
      const search = params.search ? params.search.toLowerCase() : null;
      const sortBy = params.sort_by || 'total';
      const result = {};

      if (params.type !== 'intersections') {
        let routes = Object.entries(agg.byRoute)
          .filter(([, d]) => d.total >= minCrashes)
          .map(([name, d]) => ({
            name,
            total: d.total,
            K: d.K, A: d.A, B: d.B, C: d.C, O: d.O,
            epdo: calcEPDO(d),
            jurisdiction: d.jurisdiction || ''
          }));

        if (search) routes = routes.filter(r => r.name.toLowerCase().includes(search));
        if (sortBy === 'epdo') routes.sort((a, b) => b.epdo - a.epdo);
        else if (sortBy === 'name') routes.sort((a, b) => a.name.localeCompare(b.name));
        else routes.sort((a, b) => b.total - a.total);

        result.routes = routes.slice(0, limit);
        result.totalRoutes = routes.length;
      }

      if (params.type !== 'routes') {
        let intersections = Object.entries(agg.byNode)
          .filter(([, d]) => d.total >= minCrashes)
          .map(([name, d]) => ({
            name,
            total: d.total,
            K: d.K, A: d.A, B: d.B, C: d.C, O: d.O,
            epdo: calcEPDO(d),
            routes: d.routes ? Array.from(d.routes) : [],
            jurisdiction: d.jurisdiction || ''
          }));

        if (search) intersections = intersections.filter(n => n.name.toLowerCase().includes(search));
        if (sortBy === 'epdo') intersections.sort((a, b) => b.epdo - a.epdo);
        else if (sortBy === 'name') intersections.sort((a, b) => a.name.localeCompare(b.name));
        else intersections.sort((a, b) => b.total - a.total);

        result.intersections = intersections.slice(0, limit);
        result.totalIntersections = intersections.length;
      }

      return {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
      };
    }
  );

  // TOOL 22: get_data_quality
  server.tool(
    'get_data_quality',
    'Assess data quality and completeness metrics for the crash dataset. Reports missing/unknown values across key fields.',
    {
      route: z.string().optional().describe('Optionally scope to a route'),
      node: z.string().optional().describe('Optionally scope to an intersection')
    },
    async (params) => {
      const crashes = (params.route || params.node)
        ? dataLoader.filterCrashes(params)
        : dataLoader.loadCrashData();

      if (crashes.length === 0) {
        return { content: [{ type: 'text', text: JSON.stringify({ error: 'No crash data found' }) }] };
      }

      const fields = [
        { name: 'Severity', col: COL.SEVERITY },
        { name: 'Collision Type', col: COL.COLLISION },
        { name: 'Weather', col: COL.WEATHER },
        { name: 'Light Condition', col: COL.LIGHT },
        { name: 'Date', col: COL.DATE },
        { name: 'Time', col: COL.TIME },
        { name: 'Route', col: COL.ROUTE },
        { name: 'Node', col: COL.NODE },
        { name: 'Coordinates (X)', col: COL.X },
        { name: 'Coordinates (Y)', col: COL.Y },
        { name: 'Jurisdiction', col: COL.JURISDICTION }
      ];

      const fieldCompleteness = {};
      const unknownValues = {};

      for (const field of fields) {
        let present = 0, missing = 0, unknown = 0;
        for (const row of crashes) {
          const val = (row[field.col] || '').trim();
          if (!val) missing++;
          else if (val.toLowerCase() === 'unknown' || val === '0' || val === 'N/A') unknown++;
          else present++;
        }
        fieldCompleteness[field.name] = {
          present,
          missing,
          unknown,
          pctComplete: +((present / crashes.length) * 100).toFixed(1)
        };
        if (unknown > 0) unknownValues[field.name] = unknown;
      }

      const years = {};
      for (const row of crashes) {
        const y = row[COL.YEAR];
        if (y) years[y] = (years[y] || 0) + 1;
      }
      const sortedYears = Object.keys(years).sort();

      const recommendations = [];
      for (const [name, stats] of Object.entries(fieldCompleteness)) {
        if (stats.pctComplete < 80) {
          recommendations.push(`${name}: Only ${stats.pctComplete}% complete — ${stats.missing} missing, ${stats.unknown} unknown`);
        }
      }
      if (recommendations.length === 0) recommendations.push('Data quality is good across all fields (>80% complete)');

      return {
        content: [{ type: 'text', text: JSON.stringify({
          totalRecords: crashes.length,
          scope: params.route || params.node ? { route: params.route, node: params.node } : 'county-wide',
          dateRange: sortedYears.length > 0 ? { start: sortedYears[0], end: sortedYears[sortedYears.length - 1] } : null,
          fieldCompleteness,
          unknownValues,
          recommendations
        }, null, 2) }]
      };
    }
  );
}
