/**
 * CrashLens County Baselines & Statistical Analysis
 * Extracted from app/index.html — pure computation functions
 */
window.CL = window.CL || {};
CL.analysis = CL.analysis || {};

CL.analysis.baselines = {

    /**
     * Calculate county-wide baseline rates from sample rows.
     * @param {Array} sampleRows - crashState.sampleRows
     * @param {Object} aggregates - crashState.aggregates
     * @returns {Object|null} Baselines object
     */
    calculateCountyBaselines: function(sampleRows, aggregates) {
        var totalCrashes = sampleRows.length;
        if (totalCrashes === 0) return null;

        var totalK = 0, totalA = 0, totalB = 0, totalC = 0, totalO = 0;
        var totalPed = 0, totalBike = 0, totalNight = 0, totalImpaired = 0;
        var totalSpeed = 0, totalAngle = 0, totalHeadOn = 0, totalRearEnd = 0;
        var totalWet = 0, totalDistracted = 0, totalRunOff = 0;
        var totalWeekendNight = 0;
        var crashesByYear = {};

        sampleRows.forEach(function(row) {
            var sev = (row[COL.SEVERITY] || '').toUpperCase().trim();
            if (sev === 'K') totalK++;
            else if (sev === 'A') totalA++;
            else if (sev === 'B') totalB++;
            else if (sev === 'C') totalC++;
            else totalO++;

            if (row[COL.PED] === 'Y' || row[COL.PED] === '1' || row[COL.PED] === 1) totalPed++;
            if (row[COL.BIKE] === 'Y' || row[COL.BIKE] === '1' || row[COL.BIKE] === 1) totalBike++;

            var light = (row[COL.LIGHT] || '').toLowerCase();
            if (CRASH_PATTERN_REGEX.nightLight.test(light)) totalNight++;

            var collision = (row[COL.COLLISION] || '').toLowerCase();
            if (CRASH_PATTERN_REGEX.angleCollision.test(collision)) totalAngle++;
            if (CRASH_PATTERN_REGEX.headOnCollision.test(collision)) totalHeadOn++;
            if (CRASH_PATTERN_REGEX.rearEndCollision.test(collision)) totalRearEnd++;
            if (CRASH_PATTERN_REGEX.runOffRoad.test(collision)) totalRunOff++;

            var surface = (row[COL.WEATHER] || '').toLowerCase();
            if (CRASH_PATTERN_REGEX.wetSurface.test(surface)) totalWet++;

            var impaired = (row[COL.ALCOHOL] || row[COL.DRUG] || '').toString();
            if (impaired === 'Y' || impaired === '1' || impaired === 'Yes') totalImpaired++;

            var speed = (row[COL.SPEED] || '').toString();
            if (speed === 'Y' || speed === '1' || speed === 'Yes') totalSpeed++;

            var date = row[COL.DATE];
            if (date) {
                var year = new Date(date).getFullYear();
                if (!isNaN(year)) {
                    crashesByYear[year] = (crashesByYear[year] || 0) + 1;
                }
            }
        });

        var baselines = {
            totalCrashes: totalCrashes,
            totalK: totalK, totalA: totalA, totalB: totalB, totalC: totalC, totalO: totalO,
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
            crashesByYear: crashesByYear,
            yearCount: Object.keys(crashesByYear).length,
            counts: {
                ped: totalPed, bike: totalBike, night: totalNight,
                impaired: totalImpaired, speed: totalSpeed, angle: totalAngle,
                headOn: totalHeadOn, rearEnd: totalRearEnd, wet: totalWet,
                runOff: totalRunOff
            }
        };

        var nodeEntries = Object.entries(aggregates.byNode || {});
        var routeEntries = Object.entries(aggregates.byRoute || {});

        if (nodeEntries.length > 0) {
            var nodeTotals = nodeEntries.map(function(entry) { return entry[1].total || 0; });
            baselines.avgCrashesPerIntersection = nodeTotals.reduce(function(a, b) { return a + b; }, 0) / nodeTotals.length;
            var mean = baselines.avgCrashesPerIntersection;
            var variance = nodeTotals.reduce(function(sum, val) { return sum + Math.pow(val - mean, 2); }, 0) / nodeTotals.length;
            baselines.stdCrashesPerIntersection = Math.sqrt(variance);
            baselines.avgEPDOPerIntersection = nodeEntries.reduce(function(sum, entry) {
                var d = entry[1];
                return sum + calcEPDO({ K: d.K || 0, A: d.A || 0, B: d.B || 0, C: d.C || 0, O: d.O || 0 });
            }, 0) / nodeEntries.length;
        }

        if (routeEntries.length > 0) {
            var routeTotals = routeEntries.map(function(entry) { return entry[1].total || 0; });
            baselines.avgCrashesPerSegment = routeTotals.reduce(function(a, b) { return a + b; }, 0) / routeTotals.length;
            var mean2 = baselines.avgCrashesPerSegment;
            var variance2 = routeTotals.reduce(function(sum, val) { return sum + Math.pow(val - mean2, 2); }, 0) / routeTotals.length;
            baselines.stdCrashesPerSegment = Math.sqrt(variance2);
            baselines.avgEPDOPerSegment = routeEntries.reduce(function(sum, entry) {
                var d = entry[1];
                return sum + calcEPDO({ K: d.K || 0, A: d.A || 0, B: d.B || 0, C: d.C || 0, O: d.O || 0 });
            }, 0) / routeEntries.length;
        }

        return baselines;
    },

    /**
     * Over-Representation Index calculation.
     */
    calculateORI: function(patterns, baselines) {
        if (!patterns || patterns.total === 0 || !baselines) return {};
        var n = patterns.total;
        var calcORIVal = function(localCount, baselineRate) {
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
            runOff:   { count: patterns.runOffRoad || patterns.runOff || 0, ori: calcORIVal(patterns.runOffRoad || patterns.runOff || 0, baselines.pctRunOff), pct: (patterns.runOffRoad || patterns.runOff || 0) / n },
            wet:      { count: patterns.wetRoad || patterns.wet || 0, ori: calcORIVal(patterns.wetRoad || patterns.wet || 0, baselines.pctWet), pct: (patterns.wetRoad || patterns.wet || 0) / n },
            ped:      { count: patterns.ped || 0, ori: calcORIVal(patterns.ped || 0, baselines.pctPed),      pct: (patterns.ped || 0) / n },
            bike:     { count: patterns.bike || 0, ori: calcORIVal(patterns.bike || 0, baselines.pctBike),   pct: (patterns.bike || 0) / n },
            ka:       { count: (patterns.K || 0) + (patterns.A || 0), ori: calcORIVal((patterns.K || 0) + (patterns.A || 0), baselines.pctKA), pct: ((patterns.K || 0) + (patterns.A || 0)) / n }
        };
    },

    /**
     * Standard normal CDF approximation (Abramowitz & Stegun formula 26.2.17)
     */
    normalCDF: function(x) {
        if (x < -8) return 0;
        if (x > 8) return 1;
        var a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741;
        var a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
        var sign = x < 0 ? -1 : 1;
        var ax = Math.abs(x) / Math.SQRT2;
        var t = 1.0 / (1.0 + p * ax);
        var y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-ax * ax);
        return 0.5 * (1.0 + sign * y);
    },

    /**
     * Statistical significance testing for crash patterns vs county baseline.
     */
    testPatternSignificance: function(patterns, baselines, alpha) {
        if (alpha === undefined) alpha = 0.10;
        if (!patterns || patterns.total === 0 || !baselines) return {};
        var n = patterns.total;
        var self = this;

        var binomialTest = function(observed, n, p0) {
            if (p0 === 0) return observed > 0 ? 0.001 : 1.0;
            if (p0 >= 1) return 1.0;
            if (n < 5) return 1.0;
            var expected = n * p0;
            var stddev = Math.sqrt(n * p0 * (1 - p0));
            if (stddev === 0) return observed > expected ? 0.001 : 1.0;
            var z = (observed - 0.5 - expected) / stddev;
            return 1 - self.normalCDF(z);
        };

        var testPattern = function(count, baselineRate) {
            var pValue = binomialTest(count, n, baselineRate);
            return {
                count: count,
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
            wet:      testPattern(patterns.wetRoad || patterns.wet || 0, baselines.pctWet),
            ped:      testPattern(patterns.ped || 0, baselines.pctPed),
            bike:     testPattern(patterns.bike || 0, baselines.pctBike),
            ka:       testPattern((patterns.K || 0) + (patterns.A || 0), baselines.pctKA)
        };
    },

    /**
     * Potential for Safety Improvement using simplified Empirical Bayes.
     */
    calculatePSI: function(locationData, baselines, grantStateRef) {
        var observed = locationData.total;
        var type = locationData.type;

        var expectedMean = type === 'intersection'
            ? baselines.avgCrashesPerIntersection
            : baselines.avgCrashesPerSegment;

        var expected = expectedMean;
        if (grantStateRef && grantStateRef.useRateBasedScoring && grantStateRef.adtData[locationData.name]) {
            var adt = grantStateRef.adtData[locationData.name];
            var adtValues = Object.values(grantStateRef.adtData);
            var avgADT = adtValues.reduce(function(a, b) { return a + b; }, 0) / adtValues.length;
            if (avgADT > 0) {
                expected = expectedMean * Math.pow(adt / avgADT, 0.85);
            }
        }

        var overdispersion = 2.5;
        var w = overdispersion / (overdispersion + expected);
        var ebEstimate = w * expected + (1 - w) * observed;
        var psi = ebEstimate - expected;

        var observedEPDO = calcEPDO({
            K: locationData.K || 0, A: locationData.A || 0,
            B: locationData.B || 0, C: locationData.C || 0, O: locationData.O || 0
        });
        var expectedEPDO = type === 'intersection'
            ? baselines.avgEPDOPerIntersection
            : baselines.avgEPDOPerSegment;
        var epdo_psi = observedEPDO - expectedEPDO;

        var criticalCrashes = expected + 1.645 * Math.sqrt(expected) + 0.5;

        return {
            observed: observed,
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
};

CL._registerModule('analysis/baselines');
