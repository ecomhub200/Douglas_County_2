// ============================================================================
// IMPROVED GRANT-READY LOCATIONS ALGORITHM
// Version 2.0 - Statistical, Evidence-Based Scoring
// ============================================================================
//
// KEY IMPROVEMENTS OVER CURRENT ALGORITHM:
// 1. Statistical significance testing (not arbitrary thresholds)
// 2. Over-Representation Index (ORI) for pattern detection
// 3. Expected vs Observed crash comparison (PSI methodology)
// 4. Confidence-weighted scoring (accounts for sample size)
// 5. B/C ratio estimation for HSIP
// 6. Multi-dimensional sub-scores (Need, Pattern, Feasibility, Grant Fit)
// 7. SPORTS-aligned network screening
// ============================================================================


// ============================================================================
// SECTION 1: COUNTY BASELINE CALCULATOR (Run once, cache results)
// ============================================================================

/**
 * Calculates county-wide baseline statistics for comparison.
 * This is the foundation - every location is compared against these baselines.
 * Cache this and only recalculate when data changes.
 */
function calculateCountyBaselines(sampleRows, aggregates) {
    const totalCrashes = sampleRows.length;
    if (totalCrashes === 0) return null;

    // Count crash characteristics across ALL crashes
    let totalK = 0, totalA = 0, totalB = 0, totalC = 0, totalO = 0;
    let totalPed = 0, totalBike = 0, totalNight = 0, totalImpaired = 0;
    let totalSpeed = 0, totalAngle = 0, totalHeadOn = 0, totalRearEnd = 0;
    let totalWet = 0, totalDistracted = 0, totalRunOff = 0;
    let totalWeekendNight = 0;
    const crashesByYear = {};

    sampleRows.forEach(row => {
        // Severity
        const sev = (row[COL.SEVERITY] || '').toUpperCase().trim();
        if (sev === 'K') totalK++;
        else if (sev === 'A') totalA++;
        else if (sev === 'B') totalB++;
        else if (sev === 'C') totalC++;
        else totalO++;

        // VRU
        if (row[COL.PED] === 'Y' || row[COL.PED] === '1' || row[COL.PED] === 1) totalPed++;
        if (row[COL.BIKE] === 'Y' || row[COL.BIKE] === '1' || row[COL.BIKE] === 1) totalBike++;

        // Light conditions (night)
        const light = (row[COL.LIGHT] || '').toLowerCase();
        if (CRASH_PATTERN_REGEX.nightLight.test(light)) totalNight++;

        // Collision type
        const collision = (row[COL.COLLISION] || '').toLowerCase();
        if (CRASH_PATTERN_REGEX.angleCollision.test(collision)) totalAngle++;
        if (CRASH_PATTERN_REGEX.headOnCollision.test(collision)) totalHeadOn++;
        if (CRASH_PATTERN_REGEX.rearEndCollision.test(collision)) totalRearEnd++;
        if (CRASH_PATTERN_REGEX.runOffRoad.test(collision)) totalRunOff++;

        // Surface condition
        const surface = (row[COL.WEATHER] || '').toLowerCase();
        if (CRASH_PATTERN_REGEX.wetSurface.test(surface)) totalWet++;

        // Impaired - check alcohol/drug columns if available
        const impaired = (row[COL.ALCOHOL] || row[COL.DRUG] || '').toString();
        if (impaired === 'Y' || impaired === '1' || impaired === 'Yes') totalImpaired++;

        // Speed
        const speed = (row[COL.SPEED_RELATED] || '').toString();
        if (speed === 'Y' || speed === '1' || speed === 'Yes') totalSpeed++;

        // Year tracking
        const date = row[COL.DATE];
        if (date) {
            const year = new Date(date).getFullYear();
            if (!isNaN(year)) {
                crashesByYear[year] = (crashesByYear[year] || 0) + 1;
            }
        }
    });

    // Calculate RATES (proportions) - these are the "expected" proportions
    const baselines = {
        totalCrashes,
        totalK, totalA, totalB, totalC, totalO,

        // Proportion baselines (county-wide rates)
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

        // Average crashes per location (for expected value calculations)
        avgCrashesPerIntersection: 0,
        avgCrashesPerSegment: 0,
        avgEPDOPerIntersection: 0,
        avgEPDOPerSegment: 0,

        // Year data for trend baselines
        crashesByYear,
        yearCount: Object.keys(crashesByYear).length,

        // Counts
        counts: {
            ped: totalPed, bike: totalBike, night: totalNight,
            impaired: totalImpaired, speed: totalSpeed, angle: totalAngle,
            headOn: totalHeadOn, rearEnd: totalRearEnd, wet: totalWet,
            runOff: totalRunOff
        }
    };

    // Calculate average crashes per location type
    const nodeEntries = Object.entries(aggregates.byNode || {});
    const routeEntries = Object.entries(aggregates.byRoute || {});

    if (nodeEntries.length > 0) {
        const nodeTotals = nodeEntries.map(([, d]) => d.total || 0);
        baselines.avgCrashesPerIntersection = nodeTotals.reduce((a, b) => a + b, 0) / nodeTotals.length;

        // Calculate standard deviation for intersections
        const mean = baselines.avgCrashesPerIntersection;
        const variance = nodeTotals.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / nodeTotals.length;
        baselines.stdCrashesPerIntersection = Math.sqrt(variance);

        // EPDO average
        baselines.avgEPDOPerIntersection = nodeEntries.reduce((sum, [, d]) => {
            return sum + calcEPDO({ K: d.K || 0, A: d.A || 0, B: d.B || 0, C: d.C || 0, O: d.O || 0 });
        }, 0) / nodeEntries.length;
    }

    if (routeEntries.length > 0) {
        const routeTotals = routeEntries.map(([, d]) => d.total || 0);
        baselines.avgCrashesPerSegment = routeTotals.reduce((a, b) => a + b, 0) / routeTotals.length;

        const mean = baselines.avgCrashesPerSegment;
        const variance = routeTotals.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / routeTotals.length;
        baselines.stdCrashesPerSegment = Math.sqrt(variance);

        baselines.avgEPDOPerSegment = routeEntries.reduce((sum, [, d]) => {
            return sum + calcEPDO({ K: d.K || 0, A: d.A || 0, B: d.B || 0, C: d.C || 0, O: d.O || 0 });
        }, 0) / routeEntries.length;
    }

    return baselines;
}


// ============================================================================
// SECTION 2: OVER-REPRESENTATION INDEX (ORI)
// ============================================================================

/**
 * Calculates how much each crash pattern at a location exceeds the county average.
 * ORI = (Location %) / (County %)
 * ORI > 1.0 = over-represented, ORI > 1.5 = notably, ORI > 2.0 = strongly
 *
 * This replaces arbitrary pattern weights with data-driven comparison.
 */
function calculateORI(patterns, baselines) {
    if (!patterns || patterns.total === 0 || !baselines) return {};

    const n = patterns.total;

    const calcORI = (localCount, baselineRate) => {
        if (baselineRate === 0) return localCount > 0 ? 999 : 1.0; // Avoid division by zero
        const localRate = localCount / n;
        return localRate / baselineRate;
    };

    return {
        night:    { count: patterns.night,    ori: calcORI(patterns.night, baselines.pctNight),       pct: patterns.night / n },
        impaired: { count: patterns.impaired, ori: calcORI(patterns.impaired, baselines.pctImpaired), pct: patterns.impaired / n },
        speed:    { count: patterns.speed,    ori: calcORI(patterns.speed, baselines.pctSpeed),       pct: patterns.speed / n },
        angle:    { count: patterns.angle,    ori: calcORI(patterns.angle, baselines.pctAngle),       pct: patterns.angle / n },
        headOn:   { count: patterns.headOn,   ori: calcORI(patterns.headOn, baselines.pctHeadOn),     pct: patterns.headOn / n },
        rearEnd:  { count: patterns.rearEnd,  ori: calcORI(patterns.rearEnd, baselines.pctRearEnd),   pct: patterns.rearEnd / n },
        runOff:   { count: patterns.runOffRoad || patterns.runOff || 0, ori: calcORI(patterns.runOffRoad || patterns.runOff || 0, baselines.pctRunOff), pct: (patterns.runOffRoad || patterns.runOff || 0) / n },
        wet:      { count: patterns.wetRoad || patterns.wet || 0, ori: calcORI(patterns.wetRoad || patterns.wet || 0, baselines.pctWet), pct: (patterns.wetRoad || patterns.wet || 0) / n },
        ped:      { count: patterns.ped || 0, ori: calcORI(patterns.ped || 0, baselines.pctPed),      pct: (patterns.ped || 0) / n },
        bike:     { count: patterns.bike || 0, ori: calcORI(patterns.bike || 0, baselines.pctBike),   pct: (patterns.bike || 0) / n },
        ka:       { count: (patterns.K || 0) + (patterns.A || 0), ori: calcORI((patterns.K || 0) + (patterns.A || 0), baselines.pctKA), pct: ((patterns.K || 0) + (patterns.A || 0)) / n }
    };
}


// ============================================================================
// SECTION 3: STATISTICAL SIGNIFICANCE TESTING
// ============================================================================

/**
 * Tests whether each crash pattern at a location is STATISTICALLY significant
 * compared to the county baseline, using exact binomial probability.
 *
 * This prevents small-sample false positives:
 * - 2/3 crashes impaired (67%) at a location is NOT significant
 * - 15/30 crashes impaired (50%) at a location IS significant
 *
 * Returns p-values and significance flags for each pattern.
 */
function testPatternSignificance(patterns, baselines, alpha = 0.10) {
    if (!patterns || patterns.total === 0 || !baselines) return {};

    const n = patterns.total;

    /**
     * Approximate one-sided binomial test using normal approximation.
     * Tests: P(X >= observed | n, p0) where p0 is the county baseline rate.
     * For small samples, this is conservative (which is good).
     */
    const binomialTest = (observed, n, p0) => {
        if (p0 === 0) return observed > 0 ? 0.001 : 1.0;
        if (p0 >= 1) return 1.0;
        if (n < 5) return 1.0; // Too few crashes for any pattern to be significant

        const expected = n * p0;
        const stddev = Math.sqrt(n * p0 * (1 - p0));

        if (stddev === 0) return observed > expected ? 0.001 : 1.0;

        // Continuity-corrected z-score
        const z = (observed - 0.5 - expected) / stddev;

        // Standard normal CDF approximation (Abramowitz & Stegun)
        const pValue = 1 - normalCDF(z);
        return pValue;
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
        wet:      testPattern(patterns.wetRoad || patterns.wet || 0, baselines.pctWet),
        ped:      testPattern(patterns.ped || 0, baselines.pctPed),
        bike:     testPattern(patterns.bike || 0, baselines.pctBike),
        ka:       testPattern((patterns.K || 0) + (patterns.A || 0), baselines.pctKA)
    };
}

/**
 * Standard normal CDF approximation (Abramowitz & Stegun formula 26.2.17)
 * Accurate to 1.5 × 10^-7
 */
function normalCDF(x) {
    if (x < -8) return 0;
    if (x > 8) return 1;

    const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741;
    const a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
    const sign = x < 0 ? -1 : 1;
    x = Math.abs(x) / Math.SQRT2;
    const t = 1.0 / (1.0 + p * x);
    const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
    return 0.5 * (1.0 + sign * y);
}


// ============================================================================
// SECTION 4: POTENTIAL FOR SAFETY IMPROVEMENT (PSI)
// ============================================================================

/**
 * Calculates the Potential for Safety Improvement using simplified
 * Empirical Bayes methodology. This is the core of VDOT's SPORTS system.
 *
 * PSI = Observed - Expected
 * Locations with highest PSI have the most "excess" crashes above what's normal.
 *
 * Without full Safety Performance Functions (SPFs), we use the county average
 * for the facility type as the expected value, with overdispersion adjustment.
 */
function calculatePSI(locationData, baselines) {
    const observed = locationData.total;
    const type = locationData.type; // 'intersection' or 'route'

    // Expected crashes based on county average for this facility type
    const expectedMean = type === 'intersection'
        ? baselines.avgCrashesPerIntersection
        : baselines.avgCrashesPerSegment;

    // If ADT data available, adjust expected value by volume ratio
    let expected = expectedMean;
    if (grantState.useRateBasedScoring && grantState.adtData[locationData.name]) {
        // ADT-adjusted expected: scale by traffic volume relative to average
        // This is a simplified SPF: E(crashes) ∝ ADT^α where α ≈ 0.8-1.0
        const adt = grantState.adtData[locationData.name];
        const avgADT = Object.values(grantState.adtData).reduce((a, b) => a + b, 0) /
                        Object.keys(grantState.adtData).length;
        if (avgADT > 0) {
            expected = expectedMean * Math.pow(adt / avgADT, 0.85);
        }
    }

    // Simplified Empirical Bayes adjustment
    // EB estimate = w * expected + (1-w) * observed
    // where w = overdispersion / (overdispersion + expected)
    // Higher overdispersion → more weight on expected (regression to mean)
    const overdispersion = 2.5; // Typical for intersections (can be calibrated)
    const w = overdispersion / (overdispersion + expected);
    const ebEstimate = w * expected + (1 - w) * observed;

    // PSI = EB estimate - expected
    const psi = ebEstimate - expected;

    // EPDO-weighted PSI for severity consideration
    const observedEPDO = calcEPDO({
        K: locationData.K || 0, A: locationData.A || 0,
        B: locationData.B || 0, C: locationData.C || 0, O: locationData.O || 0
    });
    const expectedEPDO = type === 'intersection'
        ? baselines.avgEPDOPerIntersection
        : baselines.avgEPDOPerSegment;
    const epdo_psi = observedEPDO - expectedEPDO;

    // Critical rate: locations exceeding this are statistically over-represented
    // Critical Rate = Average Rate + K * sqrt(Average Rate / Exposure) + 0.5/Exposure
    // Simplified: using Poisson-based critical value
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
        weight: w  // EB weight (higher = more regression to mean)
    };
}


// ============================================================================
// SECTION 5: COUNTERMEASURE FEASIBILITY & B/C ESTIMATION
// ============================================================================

/**
 * Estimates benefit-cost ratio based on identified crash patterns
 * and applicable countermeasures from the CMF Clearinghouse.
 *
 * This is critical for HSIP applications where B/C ratio is 35% of scoring.
 */
const COUNTERMEASURE_LOOKUP = {
    // Pattern → { cmf, avgCost, name, applicableTo }
    // CMF < 1.0 means crash reduction; lower = more effective
    angle_intersection: {
        cmf: 0.56, avgCost: 350000, name: 'Roundabout conversion',
        applicableTo: 'intersection', grantPrograms: ['hsip', 'ss4a']
    },
    angle_signal: {
        cmf: 0.75, avgCost: 50000, name: 'Protected left-turn phase',
        applicableTo: 'intersection', grantPrograms: ['hsip']
    },
    rearEnd_intersection: {
        cmf: 0.85, avgCost: 25000, name: 'Signal timing optimization',
        applicableTo: 'intersection', grantPrograms: ['hsip']
    },
    headOn_segment: {
        cmf: 0.56, avgCost: 150000, name: 'Median barrier/cable median',
        applicableTo: 'route', grantPrograms: ['hsip']
    },
    runOff_segment: {
        cmf: 0.72, avgCost: 80000, name: 'Rumble strips + clear zone',
        applicableTo: 'route', grantPrograms: ['hsip']
    },
    pedestrian: {
        cmf: 0.56, avgCost: 250000, name: 'Pedestrian hybrid beacon (HAWK)',
        applicableTo: 'both', grantPrograms: ['hsip', 'ss4a']
    },
    pedestrian_crosswalk: {
        cmf: 0.69, avgCost: 50000, name: 'High-visibility crosswalk + lighting',
        applicableTo: 'both', grantPrograms: ['hsip', 'ss4a']
    },
    bicycle: {
        cmf: 0.55, avgCost: 200000, name: 'Protected bike lane',
        applicableTo: 'both', grantPrograms: ['ss4a']
    },
    speed_segment: {
        cmf: 0.67, avgCost: 100000, name: 'Road diet / lane reduction',
        applicableTo: 'route', grantPrograms: ['hsip', 'ss4a']
    },
    speed_intersection: {
        cmf: 0.80, avgCost: 75000, name: 'Speed management (curb extensions, raised crosswalk)',
        applicableTo: 'intersection', grantPrograms: ['hsip', 'ss4a']
    },
    night: {
        cmf: 0.62, avgCost: 120000, name: 'Intersection/segment lighting',
        applicableTo: 'both', grantPrograms: ['hsip', 'ss4a']
    },
    wet_segment: {
        cmf: 0.80, avgCost: 200000, name: 'High-friction surface treatment',
        applicableTo: 'route', grantPrograms: ['hsip']
    },
    impaired: {
        cmf: 0.85, avgCost: 50000, name: 'DUI enforcement zone / sobriety checkpoints',
        applicableTo: 'both', grantPrograms: ['405d', '402']
    }
};

/**
 * VDOT HSIP crash cost values (2024 dollars, Virginia-specific)
 * Used for benefit calculation in B/C analysis
 */
const CRASH_COSTS = {
    K: 12800000,  // Fatal
    A: 526000,    // Serious Injury (Suspected Serious)
    B: 155000,    // Minor Injury (Suspected Minor)
    C: 78000,     // Possible Injury
    O: 12000      // Property Damage Only
};

function calculateFeasibilityAndBC(locationData, patterns, ori, significance) {
    const applicableCountermeasures = [];
    let bestBCRatio = 0;
    let bestCountermeasure = null;

    // Identify applicable countermeasures based on significant patterns
    const type = locationData.type;

    const checkAndAdd = (patternKey, lookupKey, count, oriData, sigData) => {
        if (count >= 2 && oriData && oriData.ori > 1.2) {
            const cm = COUNTERMEASURE_LOOKUP[lookupKey];
            if (cm && (cm.applicableTo === 'both' || cm.applicableTo === type)) {
                // Estimate annual crash reduction
                const crf = 1 - cm.cmf;  // Crash Reduction Factor
                const reducedCrashes = count * crf;

                // Estimate annual monetary benefit
                // Distribute reduced crashes proportionally by severity
                const total = locationData.total || 1;
                const benefit = reducedCrashes * (
                    ((locationData.K || 0) / total) * CRASH_COSTS.K +
                    ((locationData.A || 0) / total) * CRASH_COSTS.A +
                    ((locationData.B || 0) / total) * CRASH_COSTS.B +
                    ((locationData.C || 0) / total) * CRASH_COSTS.C +
                    ((locationData.O || 0) / total) * CRASH_COSTS.O
                );

                // Annualize cost over service life (typically 10-20 years)
                const serviceLife = 15;
                const discountRate = 0.04;
                const annualizedCost = cm.avgCost * (discountRate * Math.pow(1 + discountRate, serviceLife)) /
                    (Math.pow(1 + discountRate, serviceLife) - 1);

                // B/C ratio (annual benefit / annualized cost)
                const bcRatio = annualizedCost > 0 ? benefit / annualizedCost : 0;

                applicableCountermeasures.push({
                    name: cm.name,
                    cmf: cm.cmf,
                    estimatedCost: cm.avgCost,
                    estimatedAnnualBenefit: Math.round(benefit),
                    bcRatio: Math.round(bcRatio * 100) / 100,
                    crashReduction: Math.round(reducedCrashes * 10) / 10,
                    isSignificant: sigData ? sigData.significant : false,
                    grantPrograms: cm.grantPrograms
                });

                if (bcRatio > bestBCRatio) {
                    bestBCRatio = bcRatio;
                    bestCountermeasure = cm.name;
                }
            }
        }
    };

    // Check each pattern against countermeasure lookup
    checkAndAdd('angle', type === 'intersection' ? 'angle_intersection' : 'angle_signal',
        patterns.angle, ori.angle, significance.angle);
    checkAndAdd('rearEnd', 'rearEnd_intersection',
        patterns.rearEnd || 0, ori.rearEnd, significance.rearEnd);
    checkAndAdd('headOn', 'headOn_segment',
        patterns.headOn, ori.headOn, significance.headOn);
    checkAndAdd('runOff', 'runOff_segment',
        patterns.runOffRoad || patterns.runOff || 0, ori.runOff, null);
    checkAndAdd('ped', 'pedestrian',
        locationData.ped || 0, ori.ped, significance.ped);
    checkAndAdd('bike', 'bicycle',
        locationData.bike || 0, ori.bike, significance.bike);
    checkAndAdd('speed', type === 'route' ? 'speed_segment' : 'speed_intersection',
        patterns.speed, ori.speed, significance.speed);
    checkAndAdd('night', 'night',
        patterns.night, ori.night, significance.night);
    checkAndAdd('wet', 'wet_segment',
        patterns.wetRoad || patterns.wet || 0, ori.wet, significance.wet);
    checkAndAdd('impaired', 'impaired',
        patterns.impaired, ori.impaired, significance.impaired);

    return {
        countermeasures: applicableCountermeasures.sort((a, b) => b.bcRatio - a.bcRatio),
        bestBCRatio: Math.round(bestBCRatio * 100) / 100,
        bestCountermeasure,
        feasibilityScore: calculateFeasibilitySubScore(applicableCountermeasures, significance),
        countermeasureCount: applicableCountermeasures.length
    };
}

function calculateFeasibilitySubScore(countermeasures, significance) {
    if (countermeasures.length === 0) return 10; // Minimum score

    // Score based on: number of applicable CMs, best B/C, significance
    let score = 0;

    // Points for having applicable countermeasures (max 30)
    score += Math.min(countermeasures.length * 10, 30);

    // Points for B/C ratio (max 40)
    const bestBC = Math.max(...countermeasures.map(c => c.bcRatio));
    if (bestBC > 10) score += 40;
    else if (bestBC > 5) score += 30;
    else if (bestBC > 2) score += 20;
    else if (bestBC > 1) score += 10;

    // Points for statistically significant patterns (max 30)
    const significantCMs = countermeasures.filter(c => c.isSignificant).length;
    score += Math.min(significantCMs * 15, 30);

    return Math.min(score, 100);
}


// ============================================================================
// SECTION 6: GRANT-SPECIFIC FIT SCORING
// ============================================================================

/**
 * Calculates how well a location matches each specific grant program's
 * actual scoring criteria, not just crash characteristics.
 */
function calculateGrantFitScores(locationData, patterns, ori, significance, psi, feasibility) {
    return {
        hsip:  calculateHSIPFit(locationData, patterns, ori, significance, psi, feasibility),
        ss4a:  calculateSS4AFit(locationData, patterns, ori, significance, psi),
        n402:  calculate402Fit(locationData, patterns, ori, significance),
        n405d: calculate405dFit(locationData, patterns, ori, significance)
    };
}

/**
 * HSIP Scoring Criteria (Virginia HSIP Application):
 * - B/C Ratio: 35%
 * - Crash Reduction Potential: 25%
 * - SHSP Alignment: 15%
 * - Systemic Applicability: 15%
 * - Project Readiness: 10%
 */
function calculateHSIPFit(locationData, patterns, ori, significance, psi, feasibility) {
    let score = 0;
    const reasons = [];

    // B/C Ratio component (35 pts max)
    if (feasibility.bestBCRatio > 10) { score += 35; reasons.push(`Excellent B/C: ${feasibility.bestBCRatio}`); }
    else if (feasibility.bestBCRatio > 5) { score += 28; reasons.push(`Strong B/C: ${feasibility.bestBCRatio}`); }
    else if (feasibility.bestBCRatio > 2) { score += 20; reasons.push(`Good B/C: ${feasibility.bestBCRatio}`); }
    else if (feasibility.bestBCRatio > 1) { score += 12; reasons.push(`Positive B/C: ${feasibility.bestBCRatio}`); }

    // Crash Reduction Potential (25 pts max) - based on PSI
    if (psi.exceedsCritical) {
        const excessRatio = psi.observed / psi.expected;
        if (excessRatio > 3) { score += 25; reasons.push('Very high excess crashes'); }
        else if (excessRatio > 2) { score += 20; reasons.push('High excess crashes'); }
        else if (excessRatio > 1.5) { score += 15; reasons.push('Moderate excess crashes'); }
        else { score += 10; reasons.push('Above expected crashes'); }
    }

    // SHSP Alignment (15 pts max) - Virginia's emphasis areas
    const shspAreas = ['angle', 'headOn', 'speed', 'impaired', 'ped', 'bike'];
    const alignedAreas = shspAreas.filter(area =>
        significance[area] && significance[area].significant
    );
    score += Math.min(alignedAreas.length * 5, 15);
    if (alignedAreas.length > 0) reasons.push(`SHSP: ${alignedAreas.join(', ')}`);

    // Systemic Applicability (15 pts max) - are similar locations affected?
    if (feasibility.countermeasureCount >= 3) { score += 15; reasons.push('Multiple systemic solutions'); }
    else if (feasibility.countermeasureCount >= 2) { score += 10; reasons.push('Systemic solutions available'); }
    else if (feasibility.countermeasureCount >= 1) { score += 5; }

    // Project Readiness proxy (10 pts max) - clear patterns = easier to design
    const significantPatterns = Object.values(significance).filter(s => s && s.significant).length;
    if (significantPatterns >= 3) { score += 10; }
    else if (significantPatterns >= 2) { score += 7; }
    else if (significantPatterns >= 1) { score += 4; }

    return { score: Math.min(score, 100), reasons, program: 'hsip' };
}

/**
 * SS4A Scoring Criteria (USDOT SS4A NOFO):
 * - Safety Impact: 30%
 * - Equity: 20% (NOTE: requires census data overlay - estimated here)
 * - Effective Practices: 20%
 * - Climate/Sustainability: 10%
 * - Collaboration: 10%
 * - Demonstrated Need: 10%
 */
function calculateSS4AFit(locationData, patterns, ori, significance, psi) {
    let score = 0;
    const reasons = [];

    // Safety Impact (30 pts max) - K/A crashes + VRU
    const ka = (locationData.K || 0) + (locationData.A || 0);
    const vru = (locationData.ped || 0) + (locationData.bike || 0);

    if (locationData.K >= 2) { score += 30; reasons.push(`${locationData.K} fatalities`); }
    else if (locationData.K >= 1 && vru > 0) { score += 28; reasons.push('Fatal + VRU crashes'); }
    else if (ka >= 3 && vru > 0) { score += 25; reasons.push('Severe injuries + VRU'); }
    else if (ka >= 2) { score += 18; reasons.push(`${ka} K/A crashes`); }
    else if (vru >= 2) { score += 20; reasons.push(`${vru} VRU crashes`); }
    else if (ka >= 1 || vru >= 1) { score += 10; }

    // Equity placeholder (20 pts max)
    // In production, overlay Census tract data for disadvantaged communities
    // For now, use a proxy: locations with higher pedestrian crashes tend to be
    // in more urban, often underserved areas
    if (vru >= 3) { score += 15; reasons.push('High VRU exposure (equity proxy)'); }
    else if (vru >= 1) { score += 8; }
    // TODO: Integrate Census CEJST or DOT Equitable Transportation Community data

    // Effective Practices (20 pts max) - Safe System alignment
    if (vru > 0 && ori.ped && ori.ped.ori > 1.5) { score += 10; reasons.push('VRU over-represented'); }
    if (ori.speed && ori.speed.ori > 1.5) { score += 5; reasons.push('Speed management opportunity'); }
    if (ori.night && ori.night.ori > 1.5) { score += 5; reasons.push('Lighting/visibility opportunity'); }

    // Demonstrated Need (10 pts max)
    if (psi.exceedsCritical) { score += 10; reasons.push('Exceeds expected crash frequency'); }
    else if (psi.psi > 0) { score += 5; }

    // Climate bonus (10 pts max) - multimodal projects score here
    if (vru > 0) { score += 7; reasons.push('Multimodal safety'); }

    // Collaboration (10 pts max) - proxy
    score += 5; // Assume baseline collaboration potential

    return { score: Math.min(score, 100), reasons, program: 'ss4a' };
}

/**
 * NHTSA 402 Scoring (State Highway Safety Office criteria):
 * - Problem Identification: 25%
 * - Evidence-Based Strategies: 25%
 * - Performance Measures: 20%
 * - Evaluation Plan: 15%
 * - Partnerships: 15%
 */
function calculate402Fit(locationData, patterns, ori, significance) {
    let score = 0;
    const reasons = [];

    // Problem Identification (25 pts max) - statistically significant behavioral patterns
    if (significance.speed && significance.speed.significant) {
        score += 15; reasons.push(`Speed: ${significance.speed.count} crashes (p=${significance.speed.pValue})`);
    }
    if (significance.impaired && significance.impaired.significant) {
        score += 10; reasons.push(`Impaired: ${significance.impaired.count} (p=${significance.impaired.pValue})`);
    }
    // Distracted driving (if available)
    if (patterns.distracted >= 3) { score += 5; reasons.push('Distracted driving pattern'); }

    // Evidence-Based Strategies (25 pts max) - ORI shows clear behavioral problem
    const behavioralORI = Math.max(
        ori.speed ? ori.speed.ori : 0,
        ori.impaired ? ori.impaired.ori : 0
    );
    if (behavioralORI > 2.0) { score += 25; reasons.push('Strong behavioral over-representation'); }
    else if (behavioralORI > 1.5) { score += 18; }
    else if (behavioralORI > 1.2) { score += 10; }

    // Performance Measures (20 pts max) - clear measurable targets
    if (patterns.total >= 10) { score += 20; reasons.push('Sufficient data for measurement'); }
    else if (patterns.total >= 5) { score += 12; }
    else { score += 5; }

    // Evaluation feasibility (15 pts) + Partnership (15 pts)
    score += 10; // Baseline for structured program
    if (ori.impaired && ori.impaired.ori > 1.5) { score += 10; reasons.push('LEO partnership opportunity'); }
    else if (ori.speed && ori.speed.ori > 1.5) { score += 5; }

    return { score: Math.min(score, 100), reasons, program: '402' };
}

/**
 * NHTSA 405d Scoring (Impaired Driving focused):
 * - Eligibility: 30%
 * - Effectiveness: 25%
 * - Coordination: 20%
 * - Tracking: 15%
 * - Innovation: 10%
 */
function calculate405dFit(locationData, patterns, ori, significance) {
    let score = 0;
    const reasons = [];

    // Eligibility (30 pts max) - is impaired driving THE problem?
    if (significance.impaired && significance.impaired.significant) {
        if (ori.impaired.ori > 2.0) { score += 30; reasons.push(`Impaired ORI: ${ori.impaired.ori.toFixed(1)}x county avg`); }
        else if (ori.impaired.ori > 1.5) { score += 22; reasons.push('Significant impaired over-representation'); }
        else { score += 15; reasons.push('Statistically significant impaired pattern'); }
    } else if (patterns.impaired >= 2) {
        score += 8; reasons.push(`${patterns.impaired} impaired crashes (not yet significant)`);
    }

    // Effectiveness (25 pts max) - weekend night pattern correlation
    if (patterns.weekendNight >= 3 && ori.night && ori.night.ori > 1.3) {
        score += 25; reasons.push('Strong weekend-night corridor pattern');
    } else if (patterns.weekendNight >= 2) {
        score += 15; reasons.push('Weekend night crash pattern');
    }

    // Coordination (20 pts max) - corridor-level problem
    if (locationData.type === 'route' && patterns.impaired >= 3) {
        score += 20; reasons.push('Corridor-level impaired driving problem');
    } else if (patterns.impaired >= 2) {
        score += 10;
    }

    // Tracking feasibility (15 pts) + Innovation (10 pts)
    if (patterns.total >= 10) { score += 15; }
    else if (patterns.total >= 5) { score += 8; }

    score += 5; // Baseline innovation potential

    return { score: Math.min(score, 100), reasons, program: '405d' };
}


// ============================================================================
// SECTION 7: COMPOSITE SCORING ENGINE
// ============================================================================

/**
 * The main improved scoring function that replaces calculateEnhancedGrantScore.
 * Produces a multi-dimensional score with transparency.
 *
 * Returns: {
 *   compositeScore,    // 0-10000+ (replaces old single score)
 *   needScore,         // 0-100: How severe is this location?
 *   patternScore,      // 0-100: How clear/significant are the patterns?
 *   feasibilityScore,  // 0-100: Can we fix it with known countermeasures?
 *   grantFitScores,    // { hsip, ss4a, 402, 405d } each 0-100
 *   bestGrant,         // Which grant program fits best
 *   allMatchingGrants, // All programs with score > threshold
 *   confidence,        // 'high', 'medium', 'low' based on sample size + significance
 *   psi,               // Potential for Safety Improvement details
 *   ori,               // Over-Representation Indices
 *   significance,      // Statistical significance results
 *   feasibility,       // Countermeasure analysis
 *   reasons            // Human-readable explanation array
 * }
 */
function calculateImprovedGrantScore(locationData, patterns, crashes, baselines) {
    // Step 1: Over-Representation Indices
    const ori = calculateORI(patterns, baselines);

    // Step 2: Statistical Significance
    const significance = testPatternSignificance(patterns, baselines);

    // Step 3: Potential for Safety Improvement
    const psi = calculatePSI(locationData, baselines);

    // Step 4: Countermeasure Feasibility & B/C Estimation
    const feasibility = calculateFeasibilityAndBC(locationData, patterns, ori, significance);

    // Step 5: Grant-Specific Fit Scores
    const grantFitScores = calculateGrantFitScores(
        locationData, patterns, ori, significance, psi, feasibility
    );

    // Step 6: Calculate sub-scores

    // NEED SCORE (0-100): How bad is this location?
    let needScore = 0;
    // PSI component (40 pts)
    if (psi.exceedsCritical) {
        needScore += Math.min(40, 10 + (psi.ratio - 1) * 15);
    }
    // Severity component (40 pts)
    const ka = (locationData.K || 0) + (locationData.A || 0);
    needScore += Math.min(40, ka * 12 + (locationData.B || 0) * 2);
    // Volume component (20 pts)
    needScore += Math.min(20, locationData.total * 0.5);
    needScore = Math.min(100, needScore);

    // PATTERN SCORE (0-100): How clear are the crash patterns?
    let patternScore = 0;
    const sigCount = Object.values(significance).filter(s => s && s.significant).length;
    const strongORI = Object.values(ori).filter(o => o && o.ori > 1.5).length;
    patternScore += sigCount * 15;           // Significant patterns (max ~60)
    patternScore += strongORI * 8;           // Strong ORI (max ~40)
    // Sample size confidence bonus
    if (patterns.total >= 20) patternScore += 10;
    else if (patterns.total >= 10) patternScore += 5;
    patternScore = Math.min(100, patternScore);

    // Step 7: Determine best grant match
    const grantScores = [
        { program: 'hsip',  score: grantFitScores.hsip.score },
        { program: 'ss4a',  score: grantFitScores.ss4a.score },
        { program: '402',   score: grantFitScores.n402.score },
        { program: '405d',  score: grantFitScores.n405d.score }
    ].sort((a, b) => b.score - a.score);

    const bestGrant = grantScores[0];
    const matchingGrants = grantScores.filter(g => g.score >= 25); // Minimum threshold

    // Step 8: Composite score (weighted by selected scoring profile)
    const profile = grantState.scoringProfile || 'balanced';
    let compositeScore;

    if (profile === 'balanced') {
        compositeScore = (needScore * 3) + (patternScore * 2) +
                         (feasibility.feasibilityScore * 2) +
                         (bestGrant.score * 3);
    } else {
        // When a specific grant is selected, weight that grant's fit heavily
        const targetGrant = profile === 'hsip' ? grantFitScores.hsip :
                           profile === 'ss4a' ? grantFitScores.ss4a :
                           profile === '402'  ? grantFitScores.n402 :
                           grantFitScores.n405d;
        compositeScore = (needScore * 2) + (patternScore * 2) +
                         (feasibility.feasibilityScore * 1) +
                         (targetGrant.score * 5);
    }

    // Apply trend multiplier
    if (patterns && patterns.total >= 5) {
        const trend = calculateSeverityTrend(patterns);
        if (trend.direction === 'worsening') compositeScore *= 1.15;
        else if (trend.direction === 'improving') compositeScore *= 0.9;
    }

    compositeScore = Math.round(compositeScore);

    // Step 9: Confidence level
    let confidence = 'low';
    if (patterns.total >= 15 && sigCount >= 2) confidence = 'high';
    else if (patterns.total >= 8 && sigCount >= 1) confidence = 'medium';

    // Step 10: Compile human-readable reasons
    const reasons = [];
    if (psi.exceedsCritical) reasons.push(`${psi.observed} crashes vs ${psi.expected} expected (${psi.ratio}x)`);
    if (ka > 0) reasons.push(`${locationData.K || 0}K/${locationData.A || 0}A severe crashes`);

    Object.entries(significance).forEach(([key, val]) => {
        if (val && val.significant) {
            const oriVal = ori[key];
            reasons.push(`${key}: ${val.count} crashes, ${oriVal ? oriVal.ori.toFixed(1) : '?'}x county avg (p=${val.pValue})`);
        }
    });

    if (feasibility.bestCountermeasure) {
        reasons.push(`Best CM: ${feasibility.bestCountermeasure} (B/C=${feasibility.bestBCRatio})`);
    }

    return {
        compositeScore,
        needScore: Math.round(needScore),
        patternScore: Math.round(patternScore),
        feasibilityScore: feasibility.feasibilityScore,
        grantFitScores,
        bestGrant: bestGrant.program,
        bestGrantScore: bestGrant.score,
        allMatchingGrants: matchingGrants,
        confidence,
        psi,
        ori,
        significance,
        feasibility,
        reasons
    };
}


// ============================================================================
// SECTION 8: IMPROVED GRANT MATCHING (replaces getMatchingGrantsEnhanced)
// ============================================================================

/**
 * Returns grant matches with statistical evidence and confidence levels.
 * Replaces rule-based matching with evidence-based scoring.
 */
function getImprovedGrantMatches(locationData, patterns, baselines) {
    const ori = calculateORI(patterns, baselines);
    const significance = testPatternSignificance(patterns, baselines);

    const matches = [];

    // SS4A - requires VRU severity OR high fatality rate with Safe System relevance
    const vru = (locationData.ped || 0) + (locationData.bike || 0);
    const ka = (locationData.K || 0) + (locationData.A || 0);

    if (vru > 0 || (locationData.K >= 1) || (ka >= 2 && locationData.total >= 10)) {
        const reasons = [];
        let strength = 'moderate';

        if (locationData.K >= 2 || (locationData.K >= 1 && vru > 0)) strength = 'strong';
        if (vru > 0) reasons.push(`${vru} VRU crashes`);
        if (locationData.K >= 1) reasons.push(`${locationData.K} fatal`);
        if (significance.ped && significance.ped.significant) {
            reasons.push(`Ped over-represented (p=${significance.ped.pValue})`);
            strength = 'strong';
        }

        matches.push({ program: 'ss4a', reasons, strength,
                       evidence: significance.ped || significance.ka || null });
    }

    // HSIP - requires infrastructure-correctable patterns with statistical evidence
    const infraPatterns = ['angle', 'headOn', 'rearEnd', 'wet', 'night'].filter(p =>
        significance[p] && significance[p].significant
    );

    if (infraPatterns.length > 0 || (ka >= 1 && locationData.total >= 5)) {
        const reasons = infraPatterns.map(p =>
            `${p}: ORI ${ori[p] ? ori[p].ori.toFixed(1) : '?'}x (p=${significance[p]?.pValue || '?'})`
        );
        if (ka >= 1 && reasons.length === 0) reasons.push('K/A crashes present');

        matches.push({
            program: 'hsip',
            reasons,
            strength: infraPatterns.length >= 2 ? 'strong' : 'moderate',
            evidence: { significantPatterns: infraPatterns }
        });
    }

    // 402 - requires STATISTICALLY significant behavioral patterns
    if ((significance.speed && significance.speed.significant) ||
        (patterns.distracted >= 3) ||
        (significance.impaired && significance.impaired.significant && ori.impaired.ori < 2.0)) {
        const reasons = [];
        if (significance.speed?.significant) reasons.push(`Speed ORI: ${ori.speed.ori.toFixed(1)}x`);
        if (patterns.distracted >= 3) reasons.push('Distracted driving cluster');

        matches.push({
            program: '402', reasons,
            strength: (significance.speed?.significant && ori.speed.ori > 2.0) ? 'strong' : 'moderate'
        });
    }

    // 405d - requires STATISTICALLY significant impaired driving
    if (significance.impaired && significance.impaired.significant) {
        const reasons = [`Impaired: ${patterns.impaired} crashes, ORI ${ori.impaired.ori.toFixed(1)}x`];
        if (patterns.weekendNight >= 3) reasons.push('Weekend night corridor pattern');

        matches.push({
            program: '405d', reasons,
            strength: ori.impaired.ori > 2.0 ? 'strong' : 'moderate'
        });
    }

    return matches;
}


// ============================================================================
// SECTION 9: IMPROVED getBestMatchProgram (replaces getBestMatchProgramEnhanced)
// ============================================================================

/**
 * Determines the single best grant program match using evidence-based scoring.
 * Instead of rule-based priority, uses the grant fit scores.
 */
function getImprovedBestMatch(locationData, patterns, baselines) {
    const ori = calculateORI(patterns, baselines);
    const significance = testPatternSignificance(patterns, baselines);
    const psi = calculatePSI(locationData, baselines);
    const feasibility = calculateFeasibilityAndBC(locationData, patterns, ori, significance);
    const grantFit = calculateGrantFitScores(locationData, patterns, ori, significance, psi, feasibility);

    const scores = [
        { program: 'hsip',  score: grantFit.hsip.score },
        { program: 'ss4a',  score: grantFit.ss4a.score },
        { program: '402',   score: grantFit.n402.score },
        { program: '405d',  score: grantFit.n405d.score }
    ].sort((a, b) => b.score - a.score);

    return scores[0].program;
}


// ============================================================================
// SECTION 10: INTEGRATION - Drop-in replacement for rankLocationsForGrants
// ============================================================================

/**
 * Modified rankLocationsForGrants that uses the improved algorithm.
 * Maintains the same output structure for UI compatibility.
 *
 * INTEGRATION INSTRUCTIONS:
 * 1. Add calculateCountyBaselines() call after crash data loads
 * 2. Store result in grantState.baselines
 * 3. In rankLocationsForGrants(), replace the scoring calls with improved versions
 * 4. Add new columns to table display for sub-scores
 *
 * The key change in the ranking loop (inside processIntersectionBatch / processRouteBatch):
 *
 * BEFORE:
 *   const patterns = analyzeCrashPatterns(crashes);
 *   const score = calculateEnhancedGrantScore(locData, patterns, crashes);
 *   const bestMatch = getBestMatchProgramEnhanced(locData, patterns);
 *   const matchingGrants = getMatchingGrantsEnhanced(locData, patterns);
 *
 * AFTER:
 *   const patterns = analyzeCrashPatterns(crashes);
 *   const result = calculateImprovedGrantScore(locData, patterns, crashes, grantState.baselines);
 *   const score = result.compositeScore;
 *   const bestMatch = result.bestGrant;
 *   const matchingGrants = result.allMatchingGrants.map(g => ({
 *       program: g.program,
 *       reason: result.grantFitScores[g.program === '402' ? 'n402' : g.program === '405d' ? 'n405d' : g.program]?.reasons?.join(', ') || '',
 *       strength: g.score >= 60 ? 'strong' : g.score >= 40 ? 'moderate' : 'weak'
 *   }));
 *
 *   // Store additional data for enhanced display
 *   loc.needScore = result.needScore;
 *   loc.patternScore = result.patternScore;
 *   loc.feasibilityScore = result.feasibilityScore;
 *   loc.grantFitScores = result.grantFitScores;
 *   loc.confidence = result.confidence;
 *   loc.psi = result.psi;
 *   loc.bcRatio = result.feasibility.bestBCRatio;
 *   loc.bestCountermeasure = result.feasibility.bestCountermeasure;
 *   loc.reasons = result.reasons;
 */


// ============================================================================
// SECTION 11: SPORTS-ALIGNED NETWORK SCREENING SUMMARY
// ============================================================================

/**
 * SPORTS (Safety Planning Optimization and Reporting Tool System) Integration Notes:
 *
 * Virginia's SPORTS uses these core methodologies that this improved algorithm aligns with:
 *
 * 1. NETWORK SCREENING via PSI:
 *    - Our calculatePSI() implements simplified Empirical Bayes
 *    - Compares observed to expected crashes
 *    - Accounts for regression to the mean
 *    - Prioritizes locations with genuine safety problems vs random variation
 *
 * 2. PATTERN ANALYSIS:
 *    - Our ORI calculation mirrors SPORTS' over-representation analysis
 *    - Statistical significance testing ensures patterns are real
 *    - County baselines provide the reference framework
 *
 * 3. COUNTERMEASURE IDENTIFICATION:
 *    - CMF-based countermeasure matching from the Clearinghouse
 *    - B/C ratio estimation for HSIP prioritization
 *    - Links patterns → countermeasures → grant programs
 *
 * 4. PRIORITIZATION:
 *    - Multi-criteria scoring (need, patterns, feasibility, grant fit)
 *    - Confidence levels based on statistical evidence
 *    - Grant-specific scoring aligned with actual program criteria
 *
 * FUTURE ENHANCEMENTS (require additional data):
 * - Full SPF calibration with Virginia-specific coefficients
 * - Census tract equity overlay for SS4A
 * - Real ADT data integration for crash rate calculations
 * - SHSP emphasis area spatial overlay
 * - Pedestrian/bicycle exposure data (not just crash data)
 * - School zone, work zone, and corridor-level analysis
 */


// ============================================================================
// EXPORT / USAGE
// ============================================================================

// To integrate, add to your initialization after crash data loads:
//
// grantState.baselines = calculateCountyBaselines(crashState.sampleRows, crashState.aggregates);
//
// Then in rankLocationsForGrants(), replace scoring calls as shown in Section 10.
