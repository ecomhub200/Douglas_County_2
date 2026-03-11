/**
 * CrashLens CMF (Crash Modification Factor) Library
 * Search, recommend, and combine countermeasures from the FHWA CMF Clearinghouse database.
 */

/**
 * Search CMF records with filtering and relevance scoring.
 * Ported from app executeCMFSearch() logic.
 */
export function searchCMF(records, params = {}) {
  const {
    crashTypes = [],
    locationType = 'both',
    areaType = 'all',
    category = null,
    minRating = 3,
    provenOnly = false,
    hsmOnly = false,
    keywords = null,
    limit = 15
  } = params;

  // Filter phase
  let results = records.filter(cmf => {
    if (cmf.r < minRating) return false;

    if (locationType !== 'both' && cmf.loc !== 'both' && cmf.loc !== locationType) return false;

    if (areaType !== 'all' && cmf.at) {
      if (!cmf.at.toLowerCase().includes(areaType.toLowerCase())) return false;
    }

    if (provenOnly && !cmf.psc) return false;
    if (hsmOnly && !cmf.hsm) return false;

    if (category) {
      if (!cmf.c.toLowerCase().includes(category.toLowerCase())) return false;
    }

    if (keywords) {
      const searchText = cmf.n.toLowerCase();
      const keywordList = keywords.toLowerCase().split(/\s+/);
      if (!keywordList.some(kw => searchText.includes(kw))) return false;
    }

    return true;
  });

  // Score phase
  results = results.map(cmf => {
    let score = cmf.r * 10;

    // Crash type matching
    if (crashTypes.length > 0 && cmf.ct) {
      const matches = cmf.ct.filter(t => crashTypes.includes(t) || t === 'all');
      score += matches.length * 20;
      if (matches.some(t => t !== 'all')) score += 30;
    }

    if (cmf.psc) score += 25;
    if (cmf.hsm) score += 15;

    // Bonus for higher CRF (positive = crash reduction)
    if (cmf.crf > 0) score += cmf.crf / 3;

    // Virginia relevance bonus
    if (cmf.va > 50) score += cmf.va / 10;

    return { ...cmf, searchScore: score };
  });

  // Sort and deduplicate by name
  results.sort((a, b) => b.searchScore - a.searchScore);
  const seen = new Set();
  results = results.filter(cmf => {
    if (seen.has(cmf.n)) return false;
    seen.add(cmf.n);
    return true;
  });

  return results.slice(0, limit).map((cmf, idx) => ({
    rank: idx + 1,
    id: cmf.id,
    name: cmf.n,
    category: cmf.c,
    subcategory: cmf.sc,
    cmf: cmf.cmf,
    crf: cmf.crf,
    rating: cmf.r,
    crashTypes: cmf.ct || [],
    severity: cmf.sev || [],
    locationType: cmf.loc,
    areaType: cmf.at,
    isProven: cmf.psc || false,
    inHSM: cmf.hsm || false,
    virginiaRelevance: cmf.va,
    cost: cmf.cost,
    searchScore: cmf.searchScore
  }));
}

/**
 * Recommend countermeasures based on a location's crash profile.
 * Analyzes dominant crash patterns and searches for matching CMFs.
 */
export function recommendCountermeasures(records, crashProfile, options = {}) {
  const { maxResults = 10 } = options;

  // Determine dominant crash patterns from profile
  const patterns = identifyDominantPatterns(crashProfile);
  const crashTypes = patterns.map(p => p.cmfType).filter(Boolean);

  // Determine location type
  const locationType = crashProfile.extended?.intersectionType ? 'intersection' : 'both';

  // Search with profile-derived parameters
  const results = searchCMF(records, {
    crashTypes,
    locationType,
    minRating: 3,
    limit: maxResults * 2 // Get extra to filter
  });

  // Re-score based on how well each CMF addresses the location's specific patterns
  const scored = results.map(cmf => {
    const patternScore = matchCMFToCrashPattern(cmf, patterns);
    return { ...cmf, patternMatchScore: patternScore, totalScore: cmf.searchScore + patternScore };
  });

  scored.sort((a, b) => b.totalScore - a.totalScore);
  return scored.slice(0, maxResults);
}

/**
 * Calculate combined CMF using FHWA successive multiplication method.
 */
export function calculateCombinedCMF(cmfValues, names) {
  if (!cmfValues || cmfValues.length === 0) {
    return { combinedCMF: 1, combinedCRF: 0, individual: [] };
  }

  const combinedCMF = cmfValues.reduce((product, val) => product * val, 1);
  const combinedCRF = (1 - combinedCMF) * 100;

  const individual = cmfValues.map((val, i) => ({
    name: names && names[i] ? names[i] : `Countermeasure ${i + 1}`,
    cmf: val,
    crf: ((1 - val) * 100).toFixed(1)
  }));

  return {
    combinedCMF: +combinedCMF.toFixed(4),
    combinedCRF: +combinedCRF.toFixed(1),
    individual,
    methodology: 'FHWA successive multiplication'
  };
}

/**
 * Score how well a CMF record matches a location's crash patterns.
 */
export function matchCMFToCrashPattern(cmfRecord, patterns) {
  let score = 0;
  const cmfTypes = cmfRecord.crashTypes || [];

  for (const pattern of patterns) {
    if (!pattern.cmfType) continue;
    if (cmfTypes.includes(pattern.cmfType) || cmfTypes.includes('all')) {
      score += pattern.weight * 10;
    }
  }

  return score;
}

/**
 * Identify dominant crash patterns from a detailed profile.
 * Maps collision types and factors to CMF crash type vocabulary.
 */
function identifyDominantPatterns(profile) {
  const patterns = [];
  const total = profile.total || 1;

  // Collision type patterns
  const collisionMap = {
    'Angle': 'angle',
    'Rear End': 'rear_end',
    'Head On': 'head_on',
    'Sideswipe': 'sideswipe',
    'Fixed Object': 'run_off_road',
    'Run Off Road': 'run_off_road'
  };

  if (profile.collisionTypes) {
    for (const [type, count] of Object.entries(profile.collisionTypes)) {
      const pct = count / total;
      if (pct >= 0.10) { // At least 10% of crashes
        const cmfType = Object.entries(collisionMap)
          .find(([key]) => type.toLowerCase().includes(key.toLowerCase()));
        patterns.push({
          pattern: type,
          count,
          pct,
          cmfType: cmfType ? cmfType[1] : null,
          weight: pct
        });
      }
    }
  }

  // Contributing factor patterns
  if (profile.pedInvolved > 0) {
    patterns.push({ pattern: 'Pedestrian', count: profile.pedInvolved, pct: profile.pedInvolved / total, cmfType: 'pedestrian', weight: profile.pedInvolved / total * 2 });
  }
  if (profile.bikeInvolved > 0) {
    patterns.push({ pattern: 'Bicycle', count: profile.bikeInvolved, pct: profile.bikeInvolved / total, cmfType: 'bicycle', weight: profile.bikeInvolved / total * 2 });
  }

  const factors = profile.contributingFactors || {};
  if (factors.Speed) {
    patterns.push({ pattern: 'Speed', count: factors.Speed, pct: factors.Speed / total, cmfType: 'speed', weight: factors.Speed / total });
  }

  // Nighttime
  const nightCount = (profile.lightDist || {})['Dark - No Street Lights'] || 0;
  const darkLit = (profile.lightDist || {})['Dark - Lighted'] || 0;
  const totalNight = nightCount + darkLit;
  if (totalNight / total >= 0.20) {
    patterns.push({ pattern: 'Nighttime', count: totalNight, pct: totalNight / total, cmfType: 'nighttime', weight: totalNight / total });
  }

  // Sort by weight
  patterns.sort((a, b) => b.weight - a.weight);
  return patterns;
}
