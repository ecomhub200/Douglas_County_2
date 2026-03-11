/**
 * CrashLens County Baselines & Statistical Analysis — Node.js ES module port
 * Ported from app/modules/analysis/baselines.js
 */

import { COL, CRASH_PATTERN_REGEX } from './constants.js';
import { calcEPDO } from './epdo.js';

/**
 * Calculate county-wide baseline rates from sample rows.
 */
export function calculateCountyBaselines(sampleRows, aggregates) {
  const totalCrashes = sampleRows.length;
  if (totalCrashes === 0) return null;

  let totalK = 0, totalA = 0, totalB = 0, totalC = 0, totalO = 0;
  let totalPed = 0, totalBike = 0, totalNight = 0, totalImpaired = 0;
  let totalSpeed = 0, totalAngle = 0, totalHeadOn = 0, totalRearEnd = 0;
  let totalWet = 0, totalRunOff = 0;
  const crashesByYear = {};

  for (const row of sampleRows) {
    const sev = (row[COL.SEVERITY] || '').toUpperCase().trim();
    if (sev === 'K') totalK++;
    else if (sev === 'A') totalA++;
    else if (sev === 'B') totalB++;
    else if (sev === 'C') totalC++;
    else totalO++;

    if (row[COL.PED] === 'Y' || row[COL.PED] === '1' || row[COL.PED] === 1 || row[COL.PED] === 'Yes') totalPed++;
    if (row[COL.BIKE] === 'Y' || row[COL.BIKE] === '1' || row[COL.BIKE] === 1 || row[COL.BIKE] === 'Yes') totalBike++;

    const light = (row[COL.LIGHT] || '').toLowerCase();
    if (CRASH_PATTERN_REGEX.nightLight.test(light)) totalNight++;

    const collision = (row[COL.COLLISION] || '').toLowerCase();
    if (CRASH_PATTERN_REGEX.angleCollision.test(collision)) totalAngle++;
    if (CRASH_PATTERN_REGEX.headOnCollision.test(collision)) totalHeadOn++;
    if (CRASH_PATTERN_REGEX.rearEndCollision.test(collision)) totalRearEnd++;
    if (CRASH_PATTERN_REGEX.runOffRoad.test(collision)) totalRunOff++;

    const surface = (row[COL.WEATHER] || '').toLowerCase();
    if (CRASH_PATTERN_REGEX.wetSurface.test(surface)) totalWet++;

    const impaired = (row[COL.ALCOHOL] || row[COL.DRUG] || '').toString();
    if (impaired === 'Y' || impaired === '1' || impaired === 'Yes') totalImpaired++;

    const speed = (row[COL.SPEED] || '').toString();
    if (speed === 'Y' || speed === '1' || speed === 'Yes') totalSpeed++;

    const date = row[COL.DATE];
    if (date) {
      const year = new Date(Number(date) || date).getFullYear();
      if (!isNaN(year)) crashesByYear[year] = (crashesByYear[year] || 0) + 1;
    }
  }

  const baselines = {
    totalCrashes,
    totalK, totalA, totalB, totalC, totalO,
    pctK: totalK / totalCrashes,
    pctA: totalA / totalCrashes,
    pctKA: (totalK + totalA) / totalCrashes,
    pctPed: totalPed / totalCrashes,
    pctBike: totalBike / totalCrashes,
    pctVRU: (totalPed + totalBike) / totalCrashes,
    pctNight: totalNight / totalCrashes,
    pctImpaired: totalImpaired / totalCrashes,
    pctSpeed: totalSpeed / totalCrashes,
    pctAngle: totalAngle / totalCrashes,
    pctHeadOn: totalHeadOn / totalCrashes,
    pctRearEnd: totalRearEnd / totalCrashes,
    pctRunOff: totalRunOff / totalCrashes,
    pctWet: totalWet / totalCrashes,
    avgCrashesPerIntersection: 0,
    avgCrashesPerSegment: 0,
    avgEPDOPerIntersection: 0,
    avgEPDOPerSegment: 0,
    crashesByYear,
    yearCount: Object.keys(crashesByYear).length,
    counts: {
      ped: totalPed, bike: totalBike, night: totalNight,
      impaired: totalImpaired, speed: totalSpeed, angle: totalAngle,
      headOn: totalHeadOn, rearEnd: totalRearEnd, wet: totalWet,
      runOff: totalRunOff
    }
  };

  const nodeEntries = Object.entries(aggregates.byNode || {});
  const routeEntries = Object.entries(aggregates.byRoute || {});

  if (nodeEntries.length > 0) {
    const nodeTotals = nodeEntries.map(e => e[1].total || 0);
    baselines.avgCrashesPerIntersection = nodeTotals.reduce((a, b) => a + b, 0) / nodeTotals.length;
    const mean = baselines.avgCrashesPerIntersection;
    const variance = nodeTotals.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / nodeTotals.length;
    baselines.stdCrashesPerIntersection = Math.sqrt(variance);
    baselines.avgEPDOPerIntersection = nodeEntries.reduce((sum, entry) => {
      const d = entry[1];
      return sum + calcEPDO({ K: d.K || 0, A: d.A || 0, B: d.B || 0, C: d.C || 0, O: d.O || 0 });
    }, 0) / nodeEntries.length;
  }

  if (routeEntries.length > 0) {
    const routeTotals = routeEntries.map(e => e[1].total || 0);
    baselines.avgCrashesPerSegment = routeTotals.reduce((a, b) => a + b, 0) / routeTotals.length;
    const mean2 = baselines.avgCrashesPerSegment;
    const variance2 = routeTotals.reduce((sum, val) => sum + Math.pow(val - mean2, 2), 0) / routeTotals.length;
    baselines.stdCrashesPerSegment = Math.sqrt(variance2);
    baselines.avgEPDOPerSegment = routeEntries.reduce((sum, entry) => {
      const d = entry[1];
      return sum + calcEPDO({ K: d.K || 0, A: d.A || 0, B: d.B || 0, C: d.C || 0, O: d.O || 0 });
    }, 0) / routeEntries.length;
  }

  return baselines;
}

/** Standard normal CDF approximation (Abramowitz & Stegun formula 26.2.17) */
function normalCDF(x) {
  if (x < -8) return 0;
  if (x > 8) return 1;
  const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741;
  const a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
  const sign = x < 0 ? -1 : 1;
  const ax = Math.abs(x) / Math.SQRT2;
  const t = 1.0 / (1.0 + p * ax);
  const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-ax * ax);
  return 0.5 * (1.0 + sign * y);
}

/**
 * Over-Representation Index calculation.
 */
export function calculateORI(patterns, baselines) {
  if (!patterns || patterns.total === 0 || !baselines) return {};
  const n = patterns.total;
  const calcORIVal = (localCount, baselineRate) => {
    if (baselineRate === 0) return localCount > 0 ? 999 : 1.0;
    return (localCount / n) / baselineRate;
  };
  return {
    night:    { count: patterns.night,    ori: calcORIVal(patterns.night, baselines.pctNight),       pct: patterns.night / n },
    impaired: { count: patterns.impaired, ori: calcORIVal(patterns.impaired, baselines.pctImpaired), pct: patterns.impaired / n },
    speed:    { count: patterns.speed,    ori: calcORIVal(patterns.speed, baselines.pctSpeed),       pct: patterns.speed / n },
    angle:    { count: patterns.angle,    ori: calcORIVal(patterns.angle, baselines.pctAngle),       pct: patterns.angle / n },
    headOn:   { count: patterns.headOn,   ori: calcORIVal(patterns.headOn, baselines.pctHeadOn),     pct: patterns.headOn / n },
    rearEnd:  { count: patterns.rearEnd,  ori: calcORIVal(patterns.rearEnd, baselines.pctRearEnd),   pct: patterns.rearEnd / n },
    runOff:   { count: patterns.runOff || 0, ori: calcORIVal(patterns.runOff || 0, baselines.pctRunOff), pct: (patterns.runOff || 0) / n },
    wet:      { count: patterns.wet || 0, ori: calcORIVal(patterns.wet || 0, baselines.pctWet), pct: (patterns.wet || 0) / n },
    ped:      { count: patterns.ped || 0, ori: calcORIVal(patterns.ped || 0, baselines.pctPed),      pct: (patterns.ped || 0) / n },
    bike:     { count: patterns.bike || 0, ori: calcORIVal(patterns.bike || 0, baselines.pctBike),   pct: (patterns.bike || 0) / n },
    ka:       { count: (patterns.K || 0) + (patterns.A || 0), ori: calcORIVal((patterns.K || 0) + (patterns.A || 0), baselines.pctKA), pct: ((patterns.K || 0) + (patterns.A || 0)) / n }
  };
}

/**
 * Statistical significance testing for crash patterns vs county baseline.
 */
export function testPatternSignificance(patterns, baselines, alpha = 0.10) {
  if (!patterns || patterns.total === 0 || !baselines) return {};
  const n = patterns.total;

  const binomialTest = (observed, n, p0) => {
    if (p0 === 0) return observed > 0 ? 0.001 : 1.0;
    if (p0 >= 1) return 1.0;
    if (n < 5) return 1.0;
    const expected = n * p0;
    const stddev = Math.sqrt(n * p0 * (1 - p0));
    if (stddev === 0) return observed > expected ? 0.001 : 1.0;
    const z = (observed - 0.5 - expected) / stddev;
    return 1 - normalCDF(z);
  };

  const testPattern = (count, baselineRate) => {
    const pValue = binomialTest(count, n, baselineRate);
    return {
      count,
      expected: Math.round(n * baselineRate * 10) / 10,
      pValue: Math.round(pValue * 1000) / 1000,
      significant: pValue < alpha,
      confidence: pValue < 0.01 ? 'high' : pValue < 0.05 ? 'medium' : pValue < 0.10 ? 'low' : 'none'
    };
  };

  return {
    night:    testPattern(patterns.night, baselines.pctNight),
    impaired: testPattern(patterns.impaired, baselines.pctImpaired),
    speed:    testPattern(patterns.speed, baselines.pctSpeed),
    angle:    testPattern(patterns.angle, baselines.pctAngle),
    headOn:   testPattern(patterns.headOn, baselines.pctHeadOn),
    rearEnd:  testPattern(patterns.rearEnd || 0, baselines.pctRearEnd),
    wet:      testPattern(patterns.wet || 0, baselines.pctWet),
    ped:      testPattern(patterns.ped || 0, baselines.pctPed),
    bike:     testPattern(patterns.bike || 0, baselines.pctBike),
    ka:       testPattern((patterns.K || 0) + (patterns.A || 0), baselines.pctKA)
  };
}

/**
 * Potential for Safety Improvement using simplified Empirical Bayes.
 */
export function calculatePSI(locationData, baselines) {
  const observed = locationData.total;
  const type = locationData.type;

  const expectedMean = type === 'intersection'
    ? baselines.avgCrashesPerIntersection
    : baselines.avgCrashesPerSegment;

  const expected = expectedMean;
  const overdispersion = 2.5;
  const w = overdispersion / (overdispersion + expected);
  const ebEstimate = w * expected + (1 - w) * observed;
  const psi = ebEstimate - expected;

  const observedEPDO = calcEPDO({
    K: locationData.K || 0, A: locationData.A || 0,
    B: locationData.B || 0, C: locationData.C || 0, O: locationData.O || 0
  });
  const expectedEPDO = type === 'intersection'
    ? baselines.avgEPDOPerIntersection
    : baselines.avgEPDOPerSegment;
  const epdo_psi = observedEPDO - expectedEPDO;

  const criticalCrashes = expected + 1.645 * Math.sqrt(expected) + 0.5;

  return {
    observed,
    expected: Math.round(expected * 10) / 10,
    ebEstimate: Math.round(ebEstimate * 10) / 10,
    psi: Math.round(psi * 10) / 10,
    epdo_psi: Math.round(epdo_psi),
    exceedsCritical: observed > criticalCrashes,
    criticalValue: Math.round(criticalCrashes * 10) / 10,
    ratio: expected > 0 ? Math.round((observed / expected) * 100) / 100 : 0,
    weight: w
  };
}
