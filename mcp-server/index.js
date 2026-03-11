#!/usr/bin/env node

/**
 * CrashLens MCP Server
 * Exposes 22 crash data analysis tools to Claude Code and AI assistants via stdio transport.
 * Tools are organized into modular registration files under ./tools/
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

// Library modules
import { COL, STATE_EPDO_WEIGHTS, EPDO_WEIGHTS_DEFAULT } from './lib/constants.js';
import { calcEPDO, getStateEPDOWeights, isYes } from './lib/epdo.js';
import { buildLocationCrashProfile, buildDetailedLocationProfile } from './lib/crash-profile.js';
import { calculateCountyBaselines, calculateORI, testPatternSignificance, calculatePSI } from './lib/baselines.js';
import { scoreAndRank } from './lib/hotspots.js';
import { interpolateThreshold, getLaneConfig, getReductionFactor, WARRANT_1_CURVES } from './lib/signal-warrant.js';
import { scoreGrantEligibility } from './lib/grant-ranking.js';
import { searchCMF, recommendCountermeasures, calculateCombinedCMF } from './lib/cmf.js';
import { analyzeSafetyCategory, analyzeAllCategories, listCategories } from './lib/safety-focus.js';
import { calculateSeverityTrend, analyzeTemporalPatterns, calculateYearOverYearChange } from './lib/trends.js';
import { runBeforeAfterStudy } from './lib/before-after.js';
import * as dataLoader from './lib/data-loader.js';

// Tool registration modules
import { registerCrashTools } from './tools/crash-tools.js';
import { registerAnalysisTools } from './tools/analysis-tools.js';
import { registerCMFTools } from './tools/cmf-tools.js';
import { registerSafetyTools } from './tools/safety-tools.js';
import { registerInfrastructureTools } from './tools/infrastructure-tools.js';

// Resolve paths
const __dirname = dirname(fileURLToPath(import.meta.url));
const DEV_PROJECT_ROOT = resolve(__dirname, '..');

// Detect standalone vs dev mode from environment variables
const CRASHLENS_STATE = process.env.CRASHLENS_STATE || '';
const CRASHLENS_JURISDICTION = process.env.CRASHLENS_JURISDICTION || '';
const CRASHLENS_ROAD_TYPE = process.env.CRASHLENS_ROAD_TYPE || 'all_roads';
const CRASHLENS_API_KEY = process.env.CRASHLENS_API_KEY || '';
const IS_STANDALONE = !!(CRASHLENS_STATE && CRASHLENS_JURISDICTION);

// Create MCP server
const server = new McpServer({
  name: 'crashlens',
  version: '2.0.0',
  description: 'Crash Lens — Traffic safety crash data analysis tools (22 tools)'
});

// ============================================================
// REGISTER ALL TOOLS (22 total)
// ============================================================

// Shared dependencies passed to tool registration functions
const deps = {
  COL, STATE_EPDO_WEIGHTS, EPDO_WEIGHTS_DEFAULT,
  calcEPDO, getStateEPDOWeights, isYes,
  buildLocationCrashProfile, buildDetailedLocationProfile,
  calculateCountyBaselines, calculateORI, testPatternSignificance, calculatePSI,
  scoreAndRank,
  interpolateThreshold, getLaneConfig, getReductionFactor, WARRANT_1_CURVES,
  scoreGrantEligibility,
  searchCMF, recommendCountermeasures, calculateCombinedCMF,
  analyzeSafetyCategory, analyzeAllCategories, listCategories,
  calculateSeverityTrend, analyzeTemporalPatterns, calculateYearOverYearChange,
  runBeforeAfterStudy,
  dataLoader
};

registerCrashTools(server, deps);           // Tools 1-5
registerAnalysisTools(server, deps);        // Tools 6-7, 18, 20
registerInfrastructureTools(server, deps);  // Tools 8-12, 21-22
registerCMFTools(server, deps);             // Tools 13-15
registerSafetyTools(server, deps);          // Tools 16-17, 19

// ============================================================
// RESOURCES (6 total)
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

server.resource(
  'cmf-database-summary',
  'crashlens://data/cmf-summary',
  async (uri) => {
    const cmfData = dataLoader.loadCMFData();
    const metadata = dataLoader.getCMFMetadata();
    return {
      contents: [{ uri: uri.href, mimeType: 'application/json', text: JSON.stringify({
        version: cmfData.version,
        updated: cmfData.updated,
        source: cmfData.source,
        totalCountermeasures: cmfData.records.length,
        categories: cmfData.categories,
        stats: metadata.stats || cmfData.stats
      }, null, 2) }]
    };
  }
);

server.resource(
  'safety-categories',
  'crashlens://config/safety-categories',
  async (uri) => {
    const categories = listCategories();
    return {
      contents: [{ uri: uri.href, mimeType: 'application/json', text: JSON.stringify({ categories }, null, 2) }]
    };
  }
);

server.resource(
  'cmf-categories',
  'crashlens://config/cmf-categories',
  async (uri) => {
    const cmfData = dataLoader.loadCMFData();
    const categoryCounts = {};
    for (const record of cmfData.records) {
      categoryCounts[record.c] = (categoryCounts[record.c] || 0) + 1;
    }
    return {
      contents: [{ uri: uri.href, mimeType: 'application/json', text: JSON.stringify({
        totalCategories: cmfData.categories.length,
        categories: cmfData.categories.map(cat => ({
          name: cat,
          recordCount: categoryCounts[cat] || 0
        }))
      }, null, 2) }]
    };
  }
);

// ============================================================
// START SERVER
// ============================================================
async function main() {
  const transport = new StdioServerTransport();
  console.error('[CrashLens MCP] Starting server v2.0.0 (22 tools, 6 resources)...');

  // Initialize data loader based on mode
  if (IS_STANDALONE) {
    // Require API key in standalone mode
    if (!CRASHLENS_API_KEY) {
      console.error('[CrashLens MCP] ERROR: CRASHLENS_API_KEY is required.');
      console.error('[CrashLens MCP] Get your API key at https://crashlens.aicreatesai.com → My Account → API Keys');
      console.error('[CrashLens MCP] Add it to your Claude Desktop config:');
      console.error('[CrashLens MCP]   "env": { "CRASHLENS_API_KEY": "your-key-here" }');
      process.exit(1);
    }

    console.error(`[CrashLens MCP] Standalone mode: ${CRASHLENS_STATE}/${CRASHLENS_JURISDICTION} (${CRASHLENS_ROAD_TYPE})`);
    try {
      await dataLoader.initStandalone(CRASHLENS_STATE, CRASHLENS_JURISDICTION, CRASHLENS_ROAD_TYPE, CRASHLENS_API_KEY);
    } catch (err) {
      console.error(`[CrashLens MCP] Failed to initialize: ${err.message}`);
      if (err.message.includes('API key') || err.message.includes('Subscription')) {
        console.error('[CrashLens MCP] Check your API key at https://crashlens.aicreatesai.com → My Account → API Keys');
      } else {
        console.error('[CrashLens MCP] Check that CRASHLENS_STATE and CRASHLENS_JURISDICTION are correct.');
        console.error('[CrashLens MCP] Example: CRASHLENS_STATE=virginia CRASHLENS_JURISDICTION=henrico');
      }
      process.exit(1);
    }
  } else {
    // Dev/legacy mode: use parent directory as project root
    dataLoader.init(DEV_PROJECT_ROOT);
    console.error('[CrashLens MCP] Dev mode: using local project data');
  }

  // Pre-load and aggregate data
  try {
    dataLoader.loadCrashData();
    dataLoader.buildAggregates();
    dataLoader.loadCMFData();
    const ctx = dataLoader.getDataContext();
    console.error(`[CrashLens MCP] Data loaded: ${ctx.jurisdiction} — ${ctx.totalRecords} records (${ctx.dateRange}), CMF: ${dataLoader.getCMFRecords().length} countermeasures`);
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
