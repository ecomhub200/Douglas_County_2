/**
 * CrashLens Hotspot Scoring Math
 * Extracted from app/index.html — pure scoring and ranking computations
 */
window.CL = window.CL || {};
CL.analysis = CL.analysis || {};

CL.analysis.hotspots = {

    /**
     * Score and rank location data into hotspot entries.
     * @param {Object} sourceData - Aggregated location data (byRoute or byNode)
     * @param {number} minCrashes - Minimum crash threshold
     * @param {string} sortBy - Sort field: 'epdo', 'total', 'ka', or 'perYear'
     * @param {number} numYears - Number of years in the data (for per-year calculation)
     * @param {Function} calcEPDOFn - EPDO calculation function
     * @returns {Array} Sorted array of hotspot objects
     */
    scoreAndRank: function(sourceData, minCrashes, sortBy, numYears, calcEPDOFn) {
        var hotspots = Object.entries(sourceData)
            .filter(function(entry) { return entry[1].total >= minCrashes; })
            .map(function(entry) {
                var loc = entry[0];
                var d = entry[1];
                var epdo = calcEPDOFn(d);
                var ka = (d.K || 0) + (d.A || 0);
                var perYear = (d.total / numYears).toFixed(1);
                var topType = d.collisions ? Object.entries(d.collisions).sort(function(a, b) { return b[1] - a[1]; })[0] : null;
                // Support both old 'route' field and new 'routes' Set
                var routeVal = d.routes ? Array.from(d.routes)[0] || '' : (d.route || '');
                // Add county/jurisdiction for multi-county tiers
                var county = d.jurisdiction || '';
                return {
                    loc: loc,
                    total: d.total,
                    K: d.K || 0,
                    A: d.A || 0,
                    B: d.B || 0,
                    C: d.C || 0,
                    O: d.O || 0,
                    epdo: epdo,
                    ka: ka,
                    perYear: perYear,
                    topType: topType ? topType[0] : 'N/A',
                    route: routeVal,
                    county: county
                };
            });

        if (sortBy === 'epdo') hotspots.sort(function(a, b) { return b.epdo - a.epdo; });
        else if (sortBy === 'total') hotspots.sort(function(a, b) { return b.total - a.total; });
        else if (sortBy === 'ka') hotspots.sort(function(a, b) { return b.ka - a.ka; });
        else hotspots.sort(function(a, b) { return parseFloat(b.perYear) - parseFloat(a.perYear); });

        return hotspots;
    }
};

CL._registerModule('analysis/hotspots');
