/**
 * CrashLens Signal Warrant Math Utilities
 * Extracted from app/index.html — pure math functions for signal warrant evaluation
 */
window.CL = window.CL || {};
CL.warrants = CL.warrants || {};

CL.warrants.signal = {

    /**
     * Interpolate minor street threshold from MUTCD curve given major street volume.
     * @param {Array} curve - Array of {major, minor} threshold points
     * @param {number} majorVol - Major street volume
     * @returns {number} Interpolated minor street threshold
     */
    interpolateThreshold: function(curve, majorVol) {
        if (majorVol <= curve[0].major) return curve[0].minor;
        if (majorVol >= curve[curve.length - 1].major) return curve[curve.length - 1].minor;

        for (var i = 0; i < curve.length - 1; i++) {
            if (majorVol >= curve[i].major && majorVol <= curve[i + 1].major) {
                var ratio = (majorVol - curve[i].major) / (curve[i + 1].major - curve[i].major);
                return Math.round(curve[i].minor + ratio * (curve[i + 1].minor - curve[i].minor));
            }
        }

        return curve[curve.length - 1].minor;
    },

    /**
     * Calculate street volumes from hourly TMC data.
     * @param {Object} hourlyData - TMC data for a single hour {NB:{L,T,R,U,total}, SB:{...}, EB:{...}, WB:{...}}
     * @param {string} majorDirection - 'EW' or 'NS'
     * @param {Array} approaches - Array of approach names ['NB','SB','EB','WB']
     * @returns {{major: number, minor: number}} Street volume totals
     */
    calculateStreetVolumes: function(hourlyData, majorDirection, approaches) {
        var isMajorEW = majorDirection === 'EW';
        var majorTotal = 0, minorTotal = 0;

        for (var i = 0; i < approaches.length; i++) {
            var approach = approaches[i];
            var data = hourlyData[approach] || {};
            // Sum individual movements
            var sumMovements = (data.L || 0) + (data.T || 0) + (data.R || 0) + (data.U || 0);
            // Use stored total if individual movements sum to 0
            var approachTotal = sumMovements > 0 ? sumMovements : (data.total || 0);

            if ((isMajorEW && (approach === 'EB' || approach === 'WB')) ||
                (!isMajorEW && (approach === 'NB' || approach === 'SB'))) {
                majorTotal += approachTotal;
            } else {
                minorTotal += approachTotal;
            }
        }

        return { major: majorTotal, minor: minorTotal };
    },

    /**
     * Get lane configuration string from config.
     * @param {number} majorLanes - Number of major street lanes
     * @param {number} minorLanes - Number of minor street lanes
     * @returns {string} Lane config string like '2x1', '1x1', etc.
     */
    getLaneConfig: function(majorLanes, minorLanes) {
        var major = majorLanes >= 2 ? '2' : '1';
        var minor = minorLanes >= 2 ? '2' : '1';
        return major + 'x' + minor;
    },

    /**
     * Get reduction factor based on population and speed limit.
     * @param {Object} config - {communityPop, speedLimit, apply70pct}
     * @returns {string} 'p70', 'p80', or 'p100'
     */
    getReductionFactor: function(config) {
        if (config.apply70pct) return 'p70';
        if (config.communityPop < 10000 || config.speedLimit > 40) return 'p70';
        if (config.communityPop < 50000) return 'p80';
        return 'p100';
    }
};

CL._registerModule('warrants/signal');
