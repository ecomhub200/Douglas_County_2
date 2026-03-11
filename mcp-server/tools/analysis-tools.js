/**
 * CrashLens MCP — Analysis Tools (Tools 6-7, 18, 20)
 * calculate_baselines, analyze_over_representation, analyze_crash_trends, compare_locations
 */

import { z } from 'zod';

export function registerAnalysisTools(server, { COL, calcEPDO, buildLocationCrashProfile, buildDetailedLocationProfile, calculateCountyBaselines, calculateORI, testPatternSignificance, calculateSeverityTrend, analyzeTemporalPatterns, calculateYearOverYearChange, dataLoader }) {

  // TOOL 6: calculate_baselines
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

  // TOOL 7: analyze_over_representation
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

  // TOOL 18: analyze_crash_trends
  server.tool(
    'analyze_crash_trends',
    'Analyze temporal crash trends: year-over-year changes, severity trends (worsening/stable/improving), time-of-day and day-of-week patterns.',
    {
      route: z.string().optional().describe('Route name'),
      node: z.string().optional().describe('Intersection node ID'),
      date_start: z.string().optional().describe('Start date (YYYY-MM-DD)'),
      date_end: z.string().optional().describe('End date (YYYY-MM-DD)')
    },
    async (params) => {
      const crashes = dataLoader.filterCrashes(params);
      if (crashes.length === 0) {
        return { content: [{ type: 'text', text: JSON.stringify({ error: 'No crashes found matching criteria' }) }] };
      }

      const byYear = {};
      for (const row of crashes) {
        const year = row[COL.YEAR] || '';
        if (year) byYear[year] = (byYear[year] || 0) + 1;
      }

      const severityTrend = calculateSeverityTrend(byYear);
      const temporal = analyzeTemporalPatterns(crashes);
      const yearOverYear = calculateYearOverYearChange(byYear);

      return {
        content: [{ type: 'text', text: JSON.stringify({
          dataContext: dataLoader.getDataContext(),
          totalCrashes: crashes.length,
          location: { route: params.route || null, node: params.node || null },
          severityTrend,
          yearOverYear,
          temporal
        }, null, 2) }]
      };
    }
  );

  // TOOL 20: compare_locations
  server.tool(
    'compare_locations',
    'Side-by-side comparison of two locations (routes or intersections). Compares crash counts, severity, patterns, EPDO, and ORI.',
    {
      location_a: z.object({
        route: z.string().optional(),
        node: z.string().optional()
      }).describe('First location'),
      location_b: z.object({
        route: z.string().optional(),
        node: z.string().optional()
      }).describe('Second location'),
      date_start: z.string().optional().describe('Start date (YYYY-MM-DD)'),
      date_end: z.string().optional().describe('End date (YYYY-MM-DD)')
    },
    async (params) => {
      const crashesA = dataLoader.filterCrashes({ ...params.location_a, date_start: params.date_start, date_end: params.date_end });
      const crashesB = dataLoader.filterCrashes({ ...params.location_b, date_start: params.date_start, date_end: params.date_end });

      if (crashesA.length === 0 && crashesB.length === 0) {
        return { content: [{ type: 'text', text: JSON.stringify({ error: 'No crashes found for either location' }) }] };
      }

      const rows = dataLoader.loadCrashData();
      const agg = dataLoader.buildAggregates();
      const baselines = calculateCountyBaselines(rows, agg);

      const buildComparison = (crashes, location) => {
        if (crashes.length === 0) return { name: location.route || location.node || 'Unknown', total: 0, error: 'No crashes' };
        const profile = buildDetailedLocationProfile(crashes);
        const simple = buildLocationCrashProfile(crashes);
        const patterns = dataLoader.analyzeCrashPatterns(crashes);
        const ori = calculateORI(patterns, baselines);
        return {
          name: location.route || location.node || 'Unknown',
          total: crashes.length,
          severity: { K: simple.K, A: simple.A, B: simple.B, C: simple.C, O: simple.O },
          epdo: profile.epdo,
          topCollisionTypes: Object.entries(profile.collisionTypes).sort((a, b) => b[1] - a[1]).slice(0, 5),
          contributingFactors: profile.contributingFactors,
          pedInvolved: profile.pedInvolved,
          bikeInvolved: profile.bikeInvolved,
          overRepresentation: ori
        };
      };

      const a = buildComparison(crashesA, params.location_a);
      const b = buildComparison(crashesB, params.location_b);

      return {
        content: [{ type: 'text', text: JSON.stringify({
          dataContext: dataLoader.getDataContext(),
          locationA: a,
          locationB: b,
          comparison: {
            totalDiff: a.total - b.total,
            epdoDiff: (a.epdo || 0) - (b.epdo || 0),
            higherCrashCount: a.total >= b.total ? 'A' : 'B',
            higherEPDO: (a.epdo || 0) >= (b.epdo || 0) ? 'A' : 'B'
          }
        }, null, 2) }]
      };
    }
  );
}
