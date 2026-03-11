/**
 * CrashLens Hotspot Scoring — Node.js ES module port
 * Ported from app/modules/analysis/hotspots.js
 */

/**
 * Score and rank location data into hotspot entries.
 * @param {Object} sourceData - Aggregated location data (byRoute or byNode)
 * @param {number} minCrashes - Minimum crash threshold
 * @param {string} sortBy - 'epdo', 'total', 'ka', or 'perYear'
 * @param {number} numYears - Number of years in the data
 * @param {Function} calcEPDOFn - EPDO calculation function
 * @returns {Array} Sorted array of hotspot objects
 */
export function scoreAndRank(sourceData, minCrashes, sortBy, numYears, calcEPDOFn) {
  let hotspots = Object.entries(sourceData)
    .filter(([, d]) => d.total >= minCrashes)
    .map(([loc, d]) => {
      const epdo = calcEPDOFn(d);
      const ka = (d.K || 0) + (d.A || 0);
      const perYear = (d.total / numYears).toFixed(1);
      const topType = d.collisions
        ? Object.entries(d.collisions).sort((a, b) => b[1] - a[1])[0]
        : null;
      const routeVal = d.routes ? Array.from(d.routes)[0] || '' : (d.route || '');
      const county = d.jurisdiction || '';
      return {
        loc, total: d.total,
        K: d.K || 0, A: d.A || 0, B: d.B || 0, C: d.C || 0, O: d.O || 0,
        epdo, ka, perYear,
        topType: topType ? topType[0] : 'N/A',
        route: routeVal, county
      };
    });

  if (sortBy === 'epdo') hotspots.sort((a, b) => b.epdo - a.epdo);
  else if (sortBy === 'total') hotspots.sort((a, b) => b.total - a.total);
  else if (sortBy === 'ka') hotspots.sort((a, b) => b.ka - a.ka);
  else hotspots.sort((a, b) => parseFloat(b.perYear) - parseFloat(a.perYear));

  return hotspots;
}
