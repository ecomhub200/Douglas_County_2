/**
 * CrashLens MCP — Safety Tools (Tools 16-17, 19)
 * analyze_safety_category, get_safety_overview, run_before_after_study
 */

import { z } from 'zod';

export function registerSafetyTools(server, { analyzeSafetyCategory, analyzeAllCategories, runBeforeAfterStudy, calculateCountyBaselines, dataLoader }) {

  // TOOL 16: analyze_safety_category
  server.tool(
    'analyze_safety_category',
    'Analyze crashes for a specific systemic safety focus category (e.g., pedestrian, speed-related, nighttime, curve, work zone).',
    {
      category: z.enum([
        'curves', 'workzone', 'school', 'guardrail', 'senior', 'young',
        'roaddeparture', 'lgtruck', 'pedestrian', 'bicycle', 'speed',
        'impaired', 'intersection', 'nighttime', 'distracted', 'motorcycle',
        'hitrun', 'weather', 'animal', 'unrestrained', 'drowsy'
      ]).describe('Safety focus category to analyze'),
      route: z.string().optional().describe('Optionally scope to a specific route'),
      date_start: z.string().optional().describe('Start date (YYYY-MM-DD)'),
      date_end: z.string().optional().describe('End date (YYYY-MM-DD)')
    },
    async (params) => {
      const crashes = dataLoader.filterCrashes({
        route: params.route,
        date_start: params.date_start,
        date_end: params.date_end
      });

      if (crashes.length === 0) {
        return { content: [{ type: 'text', text: JSON.stringify({ error: 'No crashes found matching criteria' }) }] };
      }

      const result = analyzeSafetyCategory(crashes, params.category);
      return {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
      };
    }
  );

  // TOOL 17: get_safety_overview
  server.tool(
    'get_safety_overview',
    'Get a comprehensive overview of all 21 systemic safety categories for the jurisdiction, ranked by crash frequency and severity.',
    {
      date_start: z.string().optional().describe('Start date (YYYY-MM-DD)'),
      date_end: z.string().optional().describe('End date (YYYY-MM-DD)'),
      sort_by: z.enum(['total', 'epdo', 'ka', 'pct']).optional().default('epdo').describe('Sort categories by')
    },
    async (params) => {
      const crashes = dataLoader.filterCrashes({
        date_start: params.date_start,
        date_end: params.date_end
      });

      if (crashes.length === 0) {
        return { content: [{ type: 'text', text: JSON.stringify({ error: 'No crashes found' }) }] };
      }

      let categories = analyzeAllCategories(crashes);
      const sortBy = params.sort_by || 'epdo';
      categories.sort((a, b) => b[sortBy] - a[sortBy]);

      return {
        content: [{ type: 'text', text: JSON.stringify({
          totalCrashes: crashes.length,
          categoriesAnalyzed: categories.length,
          sortedBy: sortBy,
          categories,
          topConcerns: categories.slice(0, 5).map(c => ({ key: c.key, name: c.name, total: c.total, epdo: c.epdo }))
        }, null, 2) }]
      };
    }
  );

  // TOOL 19: run_before_after_study
  server.tool(
    'run_before_after_study',
    'Run a before/after crash study to evaluate treatment effectiveness. Supports naive comparison and Empirical Bayes methods with chi-square significance testing.',
    {
      route: z.string().optional().describe('Route name'),
      node: z.string().optional().describe('Intersection node ID'),
      treatment_date: z.string().describe('Treatment/implementation date (YYYY-MM-DD)'),
      construction_months: z.number().optional().default(3).describe('Months to exclude during construction'),
      study_period_years: z.number().optional().default(3).describe('Years for before/after period'),
      method: z.enum(['naive', 'empirical_bayes']).optional().default('naive').describe('Analysis method')
    },
    async (params) => {
      if (!params.route && !params.node) {
        return { content: [{ type: 'text', text: JSON.stringify({ error: 'At least one of route or node is required' }) }] };
      }

      const crashes = dataLoader.filterCrashes({ route: params.route, node: params.node });
      if (crashes.length === 0) {
        return { content: [{ type: 'text', text: JSON.stringify({ error: 'No crashes found for this location' }) }] };
      }

      let baselines = null;
      let locationType = params.node ? 'intersection' : 'segment';
      if (params.method === 'empirical_bayes') {
        const rows = dataLoader.loadCrashData();
        const agg = dataLoader.buildAggregates();
        baselines = calculateCountyBaselines(rows, agg);
      }

      const result = runBeforeAfterStudy(
        crashes,
        params.treatment_date,
        params.construction_months || 3,
        params.study_period_years || 3,
        params.method || 'naive',
        baselines,
        locationType
      );

      return {
        content: [{ type: 'text', text: JSON.stringify({
          location: { route: params.route || null, node: params.node || null },
          ...result
        }, null, 2) }]
      };
    }
  );
}
