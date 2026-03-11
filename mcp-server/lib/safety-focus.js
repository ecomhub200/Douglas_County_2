/**
 * CrashLens Safety Focus Categories
 * 21 systemic safety categories for crash analysis.
 * Ported from app safety focus tab definitions.
 */

import { COL } from './constants.js';
import { isYes, calcEPDO } from './epdo.js';

export const SAFETY_CATEGORIES = {
  curves: {
    name: 'Curves',
    cmfKeywords: ['curve', 'horizontal', 'alignment', 'superelevation'],
    filter: (row) => {
      const align = row[COL.ALIGNMENT] || '';
      return align.includes('Curve') || align.startsWith('2.') || align.startsWith('4.') || align.startsWith('6.') || align.startsWith('8.');
    }
  },
  workzone: {
    name: 'Work Zone',
    cmfKeywords: ['work zone', 'construction', 'temporary'],
    filter: (row) => {
      const wz = row[COL.WORKZONE] || '';
      return wz.includes('Yes') || wz.startsWith('1.');
    }
  },
  school: {
    name: 'School Zone',
    cmfKeywords: ['school', 'school zone', 'crossing guard'],
    filter: (row) => {
      const sz = row[COL.SCHOOL] || '';
      const szLower = String(sz).toLowerCase();
      if (!szLower.includes('yes') && !isYes(sz)) return false;
      if (szLower === 'yes - working' || sz === '1. Yes - Working' || sz === '2. Yes - Working and Obscured') return false;
      return true;
    }
  },
  guardrail: {
    name: 'Guardrail',
    cmfKeywords: ['guardrail', 'barrier', 'median barrier', 'cable barrier'],
    filter: (row) => isYes(row[COL.GUARDRAIL])
  },
  senior: {
    name: 'Senior Driver (65+)',
    cmfKeywords: ['older driver', 'senior', 'visibility', 'sign legibility'],
    filter: (row) => isYes(row[COL.SENIOR])
  },
  young: {
    name: 'Young Driver (16-24)',
    cmfKeywords: ['young driver', 'teen', 'novice driver'],
    filter: (row) => isYes(row[COL.YOUNG])
  },
  roaddeparture: {
    name: 'Road Departure',
    cmfKeywords: ['road departure', 'run off road', 'roadside', 'rumble strip', 'shoulder'],
    filter: (row) => {
      const rwd = row[COL.ROAD_DEPARTURE] || '';
      return rwd !== '' && rwd !== 'NOT_RD' && rwd.toLowerCase() !== 'not_rd' &&
        rwd.toLowerCase() !== 'not applicable' && rwd.toLowerCase() !== 'n/a' &&
        rwd !== '0' && !rwd.startsWith('0.');
    }
  },
  lgtruck: {
    name: 'Large Truck',
    cmfKeywords: ['truck', 'heavy vehicle', 'commercial vehicle'],
    filter: (row) => {
      const lt = row[COL.LGTRUCK] || '';
      return isYes(lt) || lt.startsWith('1.');
    }
  },
  pedestrian: {
    name: 'Pedestrian',
    cmfKeywords: ['pedestrian', 'crosswalk', 'sidewalk', 'ped signal', 'RRFB'],
    filter: (row) => isYes(row[COL.PED])
  },
  bicycle: {
    name: 'Bicycle',
    cmfKeywords: ['bicycle', 'bike lane', 'bike', 'cycle track'],
    filter: (row) => isYes(row[COL.BIKE])
  },
  speed: {
    name: 'Speed-Related',
    cmfKeywords: ['speed', 'speed limit', 'traffic calming', 'speed management'],
    filter: (row) => isYes(row[COL.SPEED])
  },
  impaired: {
    name: 'Impaired Driving',
    cmfKeywords: ['alcohol', 'impaired', 'DUI', 'drug'],
    filter: (row) => isYes(row[COL.ALCOHOL]) || isYes(row[COL.DRUG])
  },
  intersection: {
    name: 'Intersection',
    cmfKeywords: ['intersection', 'signal', 'roundabout', 'turn lane', 'stop sign'],
    filter: (row) => {
      const intType = row[COL.INT_TYPE] || '';
      return intType !== '' && !intType.toLowerCase().includes('not at intersection') && !intType.startsWith('0.');
    }
  },
  nighttime: {
    name: 'Nighttime',
    cmfKeywords: ['lighting', 'illumination', 'retroreflective', 'nighttime'],
    filter: (row) => isYes(row[COL.NIGHT])
  },
  distracted: {
    name: 'Distracted Driving',
    cmfKeywords: ['distracted', 'cell phone', 'rumble strip'],
    filter: (row) => isYes(row[COL.DISTRACTED])
  },
  motorcycle: {
    name: 'Motorcycle',
    cmfKeywords: ['motorcycle', 'rider'],
    filter: (row) => isYes(row[COL.MOTORCYCLE])
  },
  hitrun: {
    name: 'Hit and Run',
    cmfKeywords: ['hit and run', 'enforcement', 'camera'],
    filter: (row) => isYes(row[COL.HITRUN])
  },
  weather: {
    name: 'Weather-Related',
    cmfKeywords: ['wet road', 'friction', 'drainage', 'anti-icing', 'weather'],
    filter: (row) => {
      const weather = (row[COL.WEATHER] || '').toLowerCase();
      return weather !== '' && weather !== 'clear' && weather !== 'unknown' &&
        !weather.includes('clear') && !weather.startsWith('1.') && !weather.startsWith('0.');
    }
  },
  animal: {
    name: 'Animal',
    cmfKeywords: ['animal', 'deer', 'wildlife', 'fencing'],
    filter: (row) => {
      if (isYes(row[COL.ANIMAL])) return true;
      const harmful = (row[COL.FIRST_HARMFUL] || '').toLowerCase();
      return harmful.includes('animal') || harmful.includes('deer');
    }
  },
  unrestrained: {
    name: 'Unrestrained Occupant',
    cmfKeywords: ['seat belt', 'restraint', 'occupant protection'],
    filter: (row) => {
      const unrest = row[COL.UNRESTRAINED] || '';
      return isYes(unrest) || unrest === 'Unbelted';
    }
  },
  drowsy: {
    name: 'Drowsy Driving',
    cmfKeywords: ['drowsy', 'fatigue', 'rumble strip'],
    filter: (row) => isYes(row[COL.DROWSY])
  }
};

/**
 * Analyze crashes for a specific safety category.
 */
export function analyzeSafetyCategory(crashes, categoryKey) {
  const cat = SAFETY_CATEGORIES[categoryKey];
  if (!cat) return { error: `Unknown category: ${categoryKey}` };

  const filtered = crashes.filter(cat.filter);
  const severity = { K: 0, A: 0, B: 0, C: 0, O: 0 };
  const byRoute = {};
  const byNode = {};
  const byYear = {};

  for (const row of filtered) {
    const sev = (row[COL.SEVERITY] || 'O').charAt(0).toUpperCase();
    if (severity[sev] !== undefined) severity[sev]++;

    const route = (row[COL.ROUTE] || '').trim();
    if (route) {
      if (!byRoute[route]) byRoute[route] = { total: 0, K: 0, A: 0, B: 0, C: 0, O: 0 };
      byRoute[route].total++;
      if (byRoute[route][sev] !== undefined) byRoute[route][sev]++;
    }

    const node = (row[COL.NODE] || '').trim();
    if (node) {
      if (!byNode[node]) byNode[node] = { total: 0, K: 0, A: 0, B: 0, C: 0, O: 0 };
      byNode[node].total++;
      if (byNode[node][sev] !== undefined) byNode[node][sev]++;
    }

    const year = row[COL.YEAR] || '';
    if (year) byYear[year] = (byYear[year] || 0) + 1;
  }

  const epdo = calcEPDO(severity);

  // Top routes and nodes sorted by total
  const topRoutes = Object.entries(byRoute)
    .map(([name, data]) => ({ name, ...data, epdo: calcEPDO(data) }))
    .sort((a, b) => b.epdo - a.epdo)
    .slice(0, 10);

  const topNodes = Object.entries(byNode)
    .map(([name, data]) => ({ name, ...data, epdo: calcEPDO(data) }))
    .sort((a, b) => b.epdo - a.epdo)
    .slice(0, 10);

  return {
    category: categoryKey,
    name: cat.name,
    totalCrashes: filtered.length,
    severity,
    epdo,
    percentOfAll: crashes.length > 0 ? +(filtered.length / crashes.length * 100).toFixed(1) : 0,
    byYear,
    topRoutes,
    topNodes,
    cmfKeywords: cat.cmfKeywords
  };
}

/**
 * Analyze all 21 safety categories and return sorted summary.
 */
export function analyzeAllCategories(crashes) {
  const results = [];

  for (const [key, cat] of Object.entries(SAFETY_CATEGORIES)) {
    const filtered = crashes.filter(cat.filter);
    const severity = { K: 0, A: 0, B: 0, C: 0, O: 0 };

    for (const row of filtered) {
      const sev = (row[COL.SEVERITY] || 'O').charAt(0).toUpperCase();
      if (severity[sev] !== undefined) severity[sev]++;
    }

    const epdo = calcEPDO(severity);
    results.push({
      key,
      name: cat.name,
      total: filtered.length,
      severity,
      epdo,
      ka: severity.K + severity.A,
      pctOfAll: crashes.length > 0 ? +(filtered.length / crashes.length * 100).toFixed(1) : 0,
      cmfKeywords: cat.cmfKeywords
    });
  }

  return results;
}

/**
 * List available categories with metadata.
 */
export function listCategories() {
  return Object.entries(SAFETY_CATEGORIES).map(([key, cat]) => ({
    key,
    name: cat.name,
    cmfKeywords: cat.cmfKeywords
  }));
}
