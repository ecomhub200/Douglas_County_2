/**
 * CrashLens EPDO Calculation Logic
 * Extracted from app/index.html — pure computation functions only
 */
window.CL = window.CL || {};
CL.core = CL.core || {};

CL.core.epdo = {
    /**
     * Look up recommended EPDO weights for a state by FIPS code.
     * Falls back to HSM Standard if state not found.
     * @param {string|number} stateFips - Two-digit state FIPS code
     * @returns {{ name: string, weights: {K:number,A:number,B:number,C:number,O:number}, source: string }}
     */
    getStateEPDOWeights: function(stateFips) {
        var stateWeights = CL.core.constants.STATE_EPDO_WEIGHTS;
        var padded = String(stateFips).padStart(2, '0');
        return stateWeights[padded] || stateWeights['_default'];
    },

    /**
     * Calculate EPDO score from severity counts using given weights.
     * @param {Object} severityObj - { K, A, B, C, O } counts
     * @param {Object} weights - { K, A, B, C, O } weight values
     * @returns {number} EPDO score
     */
    calcEPDO: function(severityObj, weights) {
        return (severityObj.K||0)*weights.K + (severityObj.A||0)*weights.A + (severityObj.B||0)*weights.B + (severityObj.C||0)*weights.C + (severityObj.O||0)*weights.O;
    }
};

CL._registerModule('core/epdo');
