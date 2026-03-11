/**
 * CrashLens MCP — CMF/Countermeasure Tools (Tools 13-15)
 * search_cmf_database, recommend_countermeasures, calculate_combined_cmf
 */

import { z } from 'zod';

export function registerCMFTools(server, { searchCMF, recommendCountermeasures, calculateCombinedCMF, buildDetailedLocationProfile, dataLoader }) {

  // TOOL 13: search_cmf_database
  server.tool(
    'search_cmf_database',
    'Search the FHWA CMF Clearinghouse database of 808 countermeasures. Filter by crash type, category, location type, quality rating, proven safety status.',
    {
      crash_types: z.array(z.string()).optional().describe('Crash types to match: angle, rear_end, pedestrian, run_off_road, head_on, sideswipe, bicycle, speed, nighttime, etc.'),
      category: z.string().optional().describe('CMF category: Roadway, Intersection geometry, Speed management, Shoulder treatments, etc.'),
      location_type: z.enum(['intersection', 'segment', 'both']).optional().default('both').describe('Location type filter'),
      area_type: z.enum(['all', 'rural', 'urban']).optional().default('all').describe('Area type filter'),
      min_rating: z.number().optional().default(3).describe('Minimum star rating (1-5)'),
      proven_only: z.boolean().optional().default(false).describe('FHWA Proven Safety Countermeasures only'),
      hsm_only: z.boolean().optional().default(false).describe('Highway Safety Manual included only'),
      keywords: z.string().optional().describe('Keyword search in countermeasure names'),
      limit: z.number().optional().default(15).describe('Max results to return')
    },
    async (params) => {
      const records = dataLoader.getCMFRecords();
      if (records.length === 0) {
        return { content: [{ type: 'text', text: JSON.stringify({ error: 'CMF database not loaded' }) }] };
      }

      const results = searchCMF(records, params);
      return {
        content: [{ type: 'text', text: JSON.stringify({
          totalInDatabase: records.length,
          returned: results.length,
          filters: {
            crashTypes: params.crash_types || [],
            category: params.category || null,
            locationType: params.location_type || 'both',
            areaType: params.area_type || 'all',
            minRating: params.min_rating || 3,
            provenOnly: params.proven_only || false,
            hsmOnly: params.hsm_only || false,
            keywords: params.keywords || null
          },
          results
        }, null, 2) }]
      };
    }
  );

  // TOOL 14: recommend_countermeasures
  server.tool(
    'recommend_countermeasures',
    'Analyze a location crash profile and automatically recommend best-matching FHWA countermeasures.',
    {
      route: z.string().optional().describe('Route name'),
      node: z.string().optional().describe('Intersection node ID'),
      date_start: z.string().optional().describe('Start date (YYYY-MM-DD)'),
      date_end: z.string().optional().describe('End date (YYYY-MM-DD)'),
      max_results: z.number().optional().default(10).describe('Max recommendations to return')
    },
    async (params) => {
      if (!params.route && !params.node) {
        return { content: [{ type: 'text', text: JSON.stringify({ error: 'At least one of route or node is required' }) }] };
      }

      const crashes = dataLoader.filterCrashes(params);
      if (crashes.length === 0) {
        return { content: [{ type: 'text', text: JSON.stringify({ error: 'No crashes found for this location' }) }] };
      }

      const records = dataLoader.getCMFRecords();
      const profile = buildDetailedLocationProfile(crashes);
      const recommendations = recommendCountermeasures(records, profile, { maxResults: params.max_results || 10 });

      return {
        content: [{ type: 'text', text: JSON.stringify({
          location: { route: params.route || null, node: params.node || null },
          crashCount: crashes.length,
          epdo: profile.epdo,
          topCollisionTypes: Object.entries(profile.collisionTypes)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5)
            .map(([type, count]) => ({ type, count, pct: +(count / crashes.length * 100).toFixed(1) })),
          recommendations
        }, null, 2) }]
      };
    }
  );

  // TOOL 15: calculate_combined_cmf
  server.tool(
    'calculate_combined_cmf',
    'Calculate the combined effect of applying multiple countermeasures using FHWA successive CMF multiplication method.',
    {
      cmf_values: z.array(z.number()).describe('Array of individual CMF values to combine'),
      names: z.array(z.string()).optional().describe('Names of countermeasures for labeling')
    },
    async (params) => {
      const result = calculateCombinedCMF(params.cmf_values, params.names);
      return {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
      };
    }
  );
}
