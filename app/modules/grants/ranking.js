/**
 * CrashLens Grant Ranking Logic
 * Extracted from app/index.html — pure grant scoring computation
 */
window.CL = window.CL || {};
CL.grants = CL.grants || {};

CL.grants.ranking = {

    /**
     * Calculate improved grant score for a location.
     * Delegates to existing global functions for sub-calculations.
     * @param {Object} locationData - Location aggregate data {type, name, total, K, A, B, C, O, ...}
     * @param {Object} patterns - Crash pattern analysis from analyzeCrashPatterns
     * @param {Array} crashes - Raw crash rows for the location
     * @param {Object} baselines - County baseline rates
     * @param {string} scoringProfile - 'balanced', 'hsip', 'ss4a', '402', or '405d'
     * @param {Object} helpers - Helper functions {calculateORI, testPatternSignificance, calculatePSI,
     *                           calculateFeasibilityAndBC, calculateGrantFitScores, calculateSeverityTrend,
     *                           calculateEnhancedGrantScore_legacy, getBestMatchProgramEnhanced_legacy,
     *                           getMatchingGrantsEnhanced_legacy}
     * @returns {Object} Scoring result
     */
    calculateImprovedGrantScore: function(locationData, patterns, crashes, baselines, scoringProfile, helpers) {
        // If baselines not available, fall back to legacy
        if (!baselines) {
            var legacyScore = helpers.calculateEnhancedGrantScore_legacy(locationData, patterns, crashes);
            return {
                compositeScore: legacyScore,
                needScore: 0, patternScore: 0, feasibilityScore: 0,
                grantFitScores: null,
                bestGrant: helpers.getBestMatchProgramEnhanced_legacy(locationData, patterns),
                bestGrantScore: 0,
                allMatchingGrants: helpers.getMatchingGrantsEnhanced_legacy(locationData, patterns),
                confidence: 'low', psi: null, ori: null, significance: null,
                feasibility: null, reasons: ['Legacy scoring (baselines unavailable)']
            };
        }

        var ori = helpers.calculateORI(patterns, baselines);
        var significance = helpers.testPatternSignificance(patterns, baselines);
        var psi = helpers.calculatePSI(locationData, baselines);
        var feasibility = helpers.calculateFeasibilityAndBC(locationData, patterns, ori, significance);
        var grantFitScores = helpers.calculateGrantFitScores(
            locationData, patterns, ori, significance, psi, feasibility
        );

        // NEED SCORE (0-100)
        var needScore = 0;
        if (psi.exceedsCritical) {
            needScore += Math.min(40, 10 + (psi.ratio - 1) * 15);
        }
        var ka = (locationData.K || 0) + (locationData.A || 0);
        needScore += Math.min(40, ka * 12 + (locationData.B || 0) * 2);
        needScore += Math.min(20, locationData.total * 0.5);
        needScore = Math.min(100, needScore);

        // PATTERN SCORE (0-100)
        var patternScore = 0;
        var sigCount = Object.values(significance).filter(function(s) { return s && s.significant; }).length;
        var strongORI = Object.values(ori).filter(function(o) { return o && o.ori > 1.5; }).length;
        patternScore += sigCount * 15;
        patternScore += strongORI * 8;
        if (patterns.total >= 20) patternScore += 10;
        else if (patterns.total >= 10) patternScore += 5;
        patternScore = Math.min(100, patternScore);

        // Best grant match
        var grantScores = [
            { program: 'hsip',  score: grantFitScores.hsip.score },
            { program: 'ss4a',  score: grantFitScores.ss4a.score },
            { program: '402',   score: grantFitScores.n402.score },
            { program: '405d',  score: grantFitScores.n405d.score }
        ].sort(function(a, b) { return b.score - a.score; });

        var bestGrant = grantScores[0];
        var matchingGrants = grantScores.filter(function(g) { return g.score >= 25; });

        // Composite score (weighted by scoring profile)
        var profile = scoringProfile || 'balanced';
        var compositeScore;

        if (profile === 'balanced') {
            compositeScore = (needScore * 3) + (patternScore * 2) +
                             (feasibility.feasibilityScore * 2) +
                             (bestGrant.score * 3);
        } else {
            var targetGrant = profile === 'hsip' ? grantFitScores.hsip :
                             profile === 'ss4a' ? grantFitScores.ss4a :
                             profile === '402'  ? grantFitScores.n402 :
                             grantFitScores.n405d;
            compositeScore = (needScore * 2) + (patternScore * 2) +
                             (feasibility.feasibilityScore * 1) +
                             (targetGrant.score * 5);
        }

        // Apply trend multiplier
        if (patterns && patterns.total >= 5) {
            var trend = helpers.calculateSeverityTrend(patterns);
            if (trend.direction === 'worsening') compositeScore *= 1.15;
            else if (trend.direction === 'improving') compositeScore *= 0.9;
        }

        compositeScore = Math.round(compositeScore);

        // Confidence level
        var confidence = 'low';
        if (patterns.total >= 15 && sigCount >= 2) confidence = 'high';
        else if (patterns.total >= 8 && sigCount >= 1) confidence = 'medium';

        // Human-readable reasons
        var reasons = [];
        if (psi.exceedsCritical) reasons.push(psi.observed + ' crashes vs ' + psi.expected + ' expected (' + psi.ratio + 'x)');
        if (ka > 0) reasons.push((locationData.K || 0) + 'K/' + (locationData.A || 0) + 'A severe crashes');

        Object.entries(significance).forEach(function(entry) {
            var key = entry[0], val = entry[1];
            if (val && val.significant) {
                var oriVal = ori[key];
                reasons.push(key + ': ' + val.count + ' crashes, ' + (oriVal ? oriVal.ori.toFixed(1) : '?') + 'x county avg (p=' + val.pValue + ')');
            }
        });

        if (feasibility.bestCountermeasure) {
            reasons.push('Best CM: ' + feasibility.bestCountermeasure + ' (B/C=' + feasibility.bestBCRatio + ')');
        }

        return {
            compositeScore: compositeScore,
            needScore: Math.round(needScore),
            patternScore: Math.round(patternScore),
            feasibilityScore: feasibility.feasibilityScore,
            grantFitScores: grantFitScores,
            bestGrant: bestGrant.program,
            bestGrantScore: bestGrant.score,
            allMatchingGrants: matchingGrants,
            confidence: confidence,
            psi: psi,
            ori: ori,
            significance: significance,
            feasibility: feasibility,
            reasons: reasons
        };
    }
};

CL._registerModule('grants/ranking');
