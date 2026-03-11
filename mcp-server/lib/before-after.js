/**
 * CrashLens Before/After Study Library
 * Naive comparison, Empirical Bayes, and chi-square significance testing.
 */

import { COL } from './constants.js';
import { calcEPDO } from './epdo.js';

/**
 * Run a naive before/after comparison normalized by period length.
 */
export function runNaiveComparison(beforeCrashes, afterCrashes, beforeDays, afterDays) {
  const beforeSev = countSeverity(beforeCrashes);
  const afterSev = countSeverity(afterCrashes);

  const beforeRate = beforeDays > 0 ? beforeCrashes.length / beforeDays * 365 : 0;
  const afterRate = afterDays > 0 ? afterCrashes.length / afterDays * 365 : 0;

  const pctChange = beforeRate > 0 ? ((afterRate - beforeRate) / beforeRate) * 100 : 0;

  const beforeEPDO = calcEPDO(beforeSev);
  const afterEPDO = calcEPDO(afterSev);
  const epdoChange = beforeEPDO > 0 ? ((afterEPDO - beforeEPDO) / beforeEPDO) * 100 : 0;

  return {
    before: {
      crashes: beforeCrashes.length,
      days: beforeDays,
      annualRate: +beforeRate.toFixed(1),
      severity: beforeSev,
      epdo: beforeEPDO
    },
    after: {
      crashes: afterCrashes.length,
      days: afterDays,
      annualRate: +afterRate.toFixed(1),
      severity: afterSev,
      epdo: afterEPDO
    },
    change: {
      totalPctChange: +pctChange.toFixed(1),
      epdoPctChange: +epdoChange.toFixed(1),
      kaChange: {
        before: beforeSev.K + beforeSev.A,
        after: afterSev.K + afterSev.A
      }
    }
  };
}

/**
 * Run Empirical Bayes before/after analysis.
 */
export function runEmpiricalBayes(beforeCrashes, afterCrashes, beforeDays, afterDays, baselines, locationType) {
  const naive = runNaiveComparison(beforeCrashes, afterCrashes, beforeDays, afterDays);

  // Expected crashes using county baselines
  const avgCrashes = locationType === 'intersection'
    ? baselines.avgCrashesPerIntersection
    : baselines.avgCrashesPerSegment;

  const yearsData = baselines.yearCount || 1;
  const expectedPerYear = avgCrashes / yearsData;

  // EB weight (overdispersion parameter)
  const overdispersion = 2.5;
  const expectedBefore = expectedPerYear * (beforeDays / 365);
  const w = overdispersion / (overdispersion + expectedBefore);

  // EB estimate of expected crashes without treatment
  const ebEstimate = w * expectedBefore + (1 - w) * beforeCrashes.length;

  // Project what "after" would have been without treatment (normalize by period length)
  const projectedWithout = ebEstimate * (afterDays / beforeDays);
  const observedAfter = afterCrashes.length;

  // CMF = observed / projected
  const cmf = projectedWithout > 0 ? observedAfter / projectedWithout : 1;
  const crf = (1 - cmf) * 100;

  return {
    ...naive,
    empiricalBayes: {
      ebEstimate: +ebEstimate.toFixed(1),
      projectedWithout: +projectedWithout.toFixed(1),
      observedAfter,
      cmf: +cmf.toFixed(3),
      crf: +crf.toFixed(1),
      weight: +w.toFixed(3),
      interpretation: crf > 0
        ? `Treatment associated with ${crf.toFixed(1)}% crash reduction`
        : `Treatment associated with ${Math.abs(crf).toFixed(1)}% crash increase`
    }
  };
}

/**
 * Chi-square test for significance of before/after difference.
 */
export function chiSquareTest(beforeCount, afterCount, beforeDays, afterDays) {
  // Normalize after count to before period length
  const normalizedAfter = afterDays > 0 ? afterCount * (beforeDays / afterDays) : afterCount;
  const total = beforeCount + normalizedAfter;

  if (total === 0) {
    return { chiSquare: 0, pValue: 1, significant: false, confidenceLevel: 'none' };
  }

  const expectedBefore = total / 2;
  const expectedAfter = total / 2;

  const chiSquare = Math.pow(beforeCount - expectedBefore, 2) / expectedBefore +
    Math.pow(normalizedAfter - expectedAfter, 2) / expectedAfter;

  // Approximate p-value from chi-square with 1 degree of freedom
  const pValue = chiSquarePValue(chiSquare, 1);

  let confidenceLevel = 'none';
  if (pValue < 0.01) confidenceLevel = '99%';
  else if (pValue < 0.05) confidenceLevel = '95%';
  else if (pValue < 0.10) confidenceLevel = '90%';

  return {
    chiSquare: +chiSquare.toFixed(3),
    pValue: +pValue.toFixed(4),
    significant: pValue < 0.05,
    confidenceLevel
  };
}

/**
 * Orchestrator: run a complete before/after study.
 */
export function runBeforeAfterStudy(crashes, treatmentDate, constructionMonths = 3, studyPeriodYears = 3, method = 'naive', baselines = null, locationType = 'intersection') {
  const treatDate = new Date(treatmentDate);
  if (isNaN(treatDate.getTime())) {
    return { error: 'Invalid treatment date' };
  }

  // Construction exclusion period
  const constructionEnd = new Date(treatDate);
  constructionEnd.setMonth(constructionEnd.getMonth() + constructionMonths);

  // Study periods
  const beforeEnd = new Date(treatDate);
  const beforeStart = new Date(treatDate);
  beforeStart.setFullYear(beforeStart.getFullYear() - studyPeriodYears);

  const afterStart = new Date(constructionEnd);
  const afterEnd = new Date(constructionEnd);
  afterEnd.setFullYear(afterEnd.getFullYear() + studyPeriodYears);

  // Split crashes into before/after
  const beforeCrashes = crashes.filter(row => {
    const d = parseCrashDate(row);
    return d && d >= beforeStart && d < beforeEnd;
  });

  const afterCrashes = crashes.filter(row => {
    const d = parseCrashDate(row);
    return d && d >= afterStart && d <= afterEnd;
  });

  const beforeDays = Math.round((beforeEnd - beforeStart) / (1000 * 60 * 60 * 24));
  const afterDays = Math.round((afterEnd - afterStart) / (1000 * 60 * 60 * 24));

  let results;
  if (method === 'empirical_bayes' && baselines) {
    results = runEmpiricalBayes(beforeCrashes, afterCrashes, beforeDays, afterDays, baselines, locationType);
  } else {
    results = runNaiveComparison(beforeCrashes, afterCrashes, beforeDays, afterDays);
  }

  // Significance test
  const significance = chiSquareTest(beforeCrashes.length, afterCrashes.length, beforeDays, afterDays);

  return {
    method,
    treatmentDate: treatmentDate,
    constructionMonths,
    studyPeriodYears,
    periods: {
      before: { start: beforeStart.toISOString().split('T')[0], end: beforeEnd.toISOString().split('T')[0], days: beforeDays },
      construction: { start: treatDate.toISOString().split('T')[0], end: constructionEnd.toISOString().split('T')[0] },
      after: { start: afterStart.toISOString().split('T')[0], end: afterEnd.toISOString().split('T')[0], days: afterDays }
    },
    ...results,
    significance
  };
}

// ---- Helpers ----

function countSeverity(crashes) {
  const sev = { K: 0, A: 0, B: 0, C: 0, O: 0 };
  for (const row of crashes) {
    const s = (row[COL.SEVERITY] || 'O').charAt(0).toUpperCase();
    if (sev[s] !== undefined) sev[s]++;
  }
  return sev;
}

function parseCrashDate(row) {
  const d = row[COL.DATE];
  if (!d) return null;
  const date = new Date(Number(d) || d);
  return isNaN(date.getTime()) ? null : date;
}

/**
 * Approximate p-value from chi-square distribution (1 df).
 */
function chiSquarePValue(x, df) {
  if (x <= 0) return 1;
  // For df=1, use normal approximation
  if (df === 1) {
    const z = Math.sqrt(x);
    return 2 * (1 - normalCDF(z));
  }
  // Rough gamma approximation for other df
  return Math.exp(-x / 2);
}

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
