/**
 * CrashLens Grant Ranking Logic — Node.js ES module port
 * Ported from app/modules/grants/ranking.js
 *
 * Note: The original uses a helper injection pattern. In the MCP context,
 * we provide a simplified scoring that doesn't require all helper functions.
 */

import { calcEPDO } from './epdo.js';
import { calculateORI, testPatternSignificance, calculatePSI } from './baselines.js';

/**
 * Simplified grant eligibility scoring for MCP context.
 * Uses available baselines + patterns to produce a grant score.
 */
export function scoreGrantEligibility(locationData, patterns, baselines, scoringProfile = 'balanced') {
  if (!baselines || !patterns || patterns.total === 0) {
    return {
      compositeScore: 0,
      needScore: 0, patternScore: 0,
      bestGrant: 'unknown',
      confidence: 'low',
      reasons: ['Insufficient data for grant scoring']
    };
  }

  const ori = calculateORI(patterns, baselines);
  const significance = testPatternSignificance(patterns, baselines);
  const psi = calculatePSI(locationData, baselines);

  // NEED SCORE (0-100)
  let needScore = 0;
  if (psi.exceedsCritical) {
    needScore += Math.min(40, 10 + (psi.ratio - 1) * 15);
  }
  const ka = (locationData.K || 0) + (locationData.A || 0);
  needScore += Math.min(40, ka * 12 + (locationData.B || 0) * 2);
  needScore += Math.min(20, locationData.total * 0.5);
  needScore = Math.min(100, needScore);

  // PATTERN SCORE (0-100)
  let patternScore = 0;
  const sigCount = Object.values(significance).filter(s => s && s.significant).length;
  const strongORI = Object.values(ori).filter(o => o && o.ori > 1.5).length;
  patternScore += sigCount * 15;
  patternScore += strongORI * 8;
  if (patterns.total >= 20) patternScore += 10;
  else if (patterns.total >= 10) patternScore += 5;
  patternScore = Math.min(100, patternScore);

  // Grant fit scores (simplified)
  const grantScores = [];

  // HSIP fit — favors high severity, intersection issues
  let hsipScore = 0;
  if (psi.exceedsCritical) hsipScore += 30;
  hsipScore += Math.min(30, ka * 10);
  if (significance.angle?.significant) hsipScore += 20;
  if (significance.headOn?.significant) hsipScore += 20;
  grantScores.push({ program: 'hsip', score: Math.min(100, hsipScore) });

  // SS4A fit — favors systemic safety, VRU crashes
  let ss4aScore = 0;
  if (significance.ped?.significant) ss4aScore += 30;
  if (significance.bike?.significant) ss4aScore += 25;
  if (significance.speed?.significant) ss4aScore += 20;
  ss4aScore += Math.min(25, ka * 8);
  grantScores.push({ program: 'ss4a', score: Math.min(100, ss4aScore) });

  // 402 fit — behavioral safety
  let n402Score = 0;
  if (significance.impaired?.significant) n402Score += 30;
  if (significance.speed?.significant) n402Score += 25;
  if (significance.night?.significant) n402Score += 20;
  n402Score += Math.min(25, locationData.total * 0.8);
  grantScores.push({ program: '402', score: Math.min(100, n402Score) });

  // 405d fit — impaired driving
  let n405dScore = 0;
  if (significance.impaired?.significant) n405dScore += 40;
  if (significance.night?.significant) n405dScore += 25;
  n405dScore += Math.min(20, (patterns.impaired || 0) * 5);
  n405dScore += Math.min(15, ka * 5);
  grantScores.push({ program: '405d', score: Math.min(100, n405dScore) });

  grantScores.sort((a, b) => b.score - a.score);
  const bestGrant = grantScores[0];
  const matchingGrants = grantScores.filter(g => g.score >= 25);

  // Composite score
  let compositeScore;
  if (scoringProfile === 'balanced') {
    compositeScore = (needScore * 3) + (patternScore * 2) + (bestGrant.score * 3);
  } else {
    const target = grantScores.find(g => g.program === scoringProfile) || bestGrant;
    compositeScore = (needScore * 2) + (patternScore * 2) + (target.score * 5);
  }
  compositeScore = Math.round(compositeScore);

  // Confidence
  let confidence = 'low';
  if (patterns.total >= 15 && sigCount >= 2) confidence = 'high';
  else if (patterns.total >= 8 && sigCount >= 1) confidence = 'medium';

  // Reasons
  const reasons = [];
  if (psi.exceedsCritical) reasons.push(`${psi.observed} crashes vs ${psi.expected} expected (${psi.ratio}x)`);
  if (ka > 0) reasons.push(`${locationData.K || 0}K/${locationData.A || 0}A severe crashes`);

  for (const [key, val] of Object.entries(significance)) {
    if (val && val.significant) {
      const oriVal = ori[key];
      reasons.push(`${key}: ${val.count} crashes, ${oriVal ? oriVal.ori.toFixed(1) : '?'}x county avg (p=${val.pValue})`);
    }
  }

  return {
    compositeScore,
    needScore: Math.round(needScore),
    patternScore: Math.round(patternScore),
    grantFitScores: Object.fromEntries(grantScores.map(g => [g.program, g.score])),
    bestGrant: bestGrant.program,
    bestGrantScore: bestGrant.score,
    allMatchingGrants: matchingGrants,
    confidence,
    psi, ori, significance,
    reasons
  };
}
