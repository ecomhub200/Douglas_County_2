/**
 * CrashLens Crash Profile Builders
 * Extracted from app/index.html — four profile builder functions
 * These are pure data-in, object-out functions.
 */
window.CL = window.CL || {};
CL.analysis = CL.analysis || {};

CL.analysis.crashProfile = {

    /**
     * Build county-wide crash profile from aggregates.
     * @param {Object} aggregates - crashState.aggregates
     * @param {number} totalRows - crashState.totalRows
     * @param {Object} [safetyStateRef] - safetyState (optional, for special categories)
     * @returns {Object|null} County-wide crash profile
     */
    buildCountyWideCrashProfile: function(aggregates, totalRows, safetyStateRef) {
        if (!aggregates) return null;

        var agg = aggregates;
        var total = totalRows;

        // Calculate collision type percentages
        var collisionTypes = agg.byCollision || {};
        var angleCount = Object.entries(collisionTypes)
            .filter(function(entry) { return entry[0].toLowerCase().includes('angle'); })
            .reduce(function(sum, entry) { return sum + entry[1]; }, 0);
        var rearEndCount = Object.entries(collisionTypes)
            .filter(function(entry) { return entry[0].toLowerCase().includes('rear'); })
            .reduce(function(sum, entry) { return sum + entry[1]; }, 0);

        // Calculate light condition percentages
        var lightConditions = agg.byLight || {};
        var nightCount = Object.entries(lightConditions)
            .filter(function(entry) { return entry[0].toLowerCase().includes('dark') || entry[0].toLowerCase().includes('night'); })
            .reduce(function(sum, entry) { return sum + entry[1]; }, 0);

        return {
            totalCrashes: total,
            // Severity
            fatalCount: agg.bySeverity.K,
            seriousCount: agg.bySeverity.A,
            kaCount: agg.bySeverity.K + agg.bySeverity.A,
            kaPercent: ((agg.bySeverity.K + agg.bySeverity.A) / total * 100).toFixed(1),
            // Collision types
            anglePercent: (angleCount / total * 100).toFixed(1),
            hasAngleCrashes: angleCount > 0,
            rearEndPercent: (rearEndCount / total * 100).toFixed(1),
            // Vulnerable road users
            pedCount: agg.ped?.total || 0,
            pedPercent: ((agg.ped?.total || 0) / total * 100).toFixed(1),
            hasPedCrashes: (agg.ped?.total || 0) > 0,
            bikeCount: agg.bike?.total || 0,
            bikePercent: ((agg.bike?.total || 0) / total * 100).toFixed(1),
            hasBikeCrashes: (agg.bike?.total || 0) > 0,
            // Light conditions
            nightPercent: (nightCount / total * 100).toFixed(1),
            hasNightCrashes: nightCount > 0,
            // Intersection
            intersectionPercent: ((agg.intersection?.total || 0) / total * 100).toFixed(1),
            isIntersection: (agg.intersection?.total || 0) > (total / 2),
            // Special categories (from safety state if available)
            hasSchoolZone: (safetyStateRef && safetyStateRef.categories?.school?.crashes?.length > 0) || false,
            hasSpeedCrashes: (safetyStateRef && safetyStateRef.categories?.speed?.crashes?.length > 0) || false,
            speedPercent: (safetyStateRef && safetyStateRef.categories?.speed?.crashes?.length)
                ? (safetyStateRef.categories.speed.crashes.length / total * 100).toFixed(1) : '0',
            hasCurveCrashes: (safetyStateRef && safetyStateRef.categories?.curves?.crashes?.length > 0) || false
        };
    },

    /**
     * Build simple crash profile for a location's crashes.
     * @param {Array} crashes - Array of crash row objects
     * @returns {Object} { total, K, A, B, C, O, anglePercent, pedCount, bikeCount, epdo }
     */
    buildLocationCrashProfile: function(crashes) {
        if (!crashes || crashes.length === 0) {
            return { total: 0, K: 0, A: 0, B: 0, C: 0, O: 0, anglePercent: 0, pedCount: 0, bikeCount: 0 };
        }

        var profile = { total: crashes.length, K: 0, A: 0, B: 0, C: 0, O: 0 };

        var angleCount = 0;
        var pedCount = 0;
        var bikeCount = 0;

        crashes.forEach(function(c) {
            var sev = (c[COL.SEVERITY] || '').charAt(0).toUpperCase();
            if (profile[sev] !== undefined) profile[sev]++;

            var collision = (c[COL.COLLISION] || '').toLowerCase();
            if (collision.includes('angle')) angleCount++;

            if (isYes(c[COL.PED])) pedCount++;
            if (isYes(c[COL.BIKE])) bikeCount++;
        });

        profile.anglePercent = (angleCount / crashes.length * 100).toFixed(1);
        profile.pedCount = pedCount;
        profile.bikeCount = bikeCount;
        profile.epdo = calcEPDO(profile);

        return profile;
    },

    /**
     * Build detailed location profile with severity, collision, weather, light distributions.
     * @param {Array} crashes - Array of crash row objects
     * @returns {Object} Detailed profile object
     */
    buildDetailedLocationProfile: function(crashes) {
        var profile = {
            total: crashes.length,
            severityDist: {},
            collisionTypes: {},
            contributingFactors: {},
            weatherDist: {},
            lightDist: {},
            pedInvolved: 0,
            bikeInvolved: 0,
            epdo: 0
        };

        crashes.forEach(function(row) {
            // Severity distribution
            var sev = row[COL.SEVERITY] || 'O';
            profile.severityDist[sev] = (profile.severityDist[sev] || 0) + 1;
            profile.epdo += EPDO_WEIGHTS[sev] || 0;

            // Collision types
            var collType = (row[COL.COLLISION] || '').trim();
            if (collType && collType !== 'Unknown') {
                profile.collisionTypes[collType] = (profile.collisionTypes[collType] || 0) + 1;
            }

            // Contributing factors
            if (isYes(row[COL.ALCOHOL])) {
                profile.contributingFactors['Alcohol'] = (profile.contributingFactors['Alcohol'] || 0) + 1;
            }
            if (isYes(row[COL.SPEED])) {
                profile.contributingFactors['Speed'] = (profile.contributingFactors['Speed'] || 0) + 1;
            }
            if (isYes(row[COL.DISTRACTED])) {
                profile.contributingFactors['Distracted'] = (profile.contributingFactors['Distracted'] || 0) + 1;
            }
            if (isYes(row[COL.DROWSY])) {
                profile.contributingFactors['Drowsy'] = (profile.contributingFactors['Drowsy'] || 0) + 1;
            }
            if (row[COL.UNRESTRAINED] === 'Unbelted' || isYes(row[COL.UNRESTRAINED])) {
                profile.contributingFactors['Unrestrained'] = (profile.contributingFactors['Unrestrained'] || 0) + 1;
            }

            // Weather
            var weather = (row[COL.WEATHER] || '').trim();
            if (weather && weather !== 'Unknown') {
                profile.weatherDist[weather] = (profile.weatherDist[weather] || 0) + 1;
            }

            // Light conditions
            var light = (row[COL.LIGHT] || '').trim();
            if (light && light !== 'Unknown') {
                profile.lightDist[light] = (profile.lightDist[light] || 0) + 1;
            }

            // Pedestrian/Bicycle
            if (isYes(row[COL.PED])) {
                profile.pedInvolved++;
            }
            if (isYes(row[COL.BIKE])) {
                profile.bikeInvolved++;
            }
        });

        return profile;
    },

    /**
     * Build CMF crash profile from CMF state data.
     * @param {Object} cmfStateRef - cmfState object
     * @returns {Object} CMF crash profile
     */
    buildCMFCrashProfile: function(cmfStateRef) {
        var crashes = cmfStateRef.filteredCrashes && cmfStateRef.filteredCrashes.length > 0
            ? cmfStateRef.filteredCrashes
            : cmfStateRef.locationCrashes;

        var hasDateFilter = cmfStateRef.dateFilter?.startDate || cmfStateRef.dateFilter?.endDate;
        var totalCount = crashes.length;

        var profile = {
            total: totalCount,
            displayTotal: (!hasDateFilter && cmfStateRef.aggregateCount) ? cmfStateRef.aggregateCount : totalCount,
            severity: { K: 0, A: 0, B: 0, C: 0, O: 0 },
            collisionTypes: {},
            collisionTypesEPDO: {},
            weatherConditions: {},
            lightConditions: {},
            factors: {
                pedestrian: 0,
                bicycle: 0,
                alcohol: 0,
                speed: 0,
                distracted: 0,
                nighttime: 0,
                wetRoad: 0,
                intersection: 0
            },
            epdo: 0,
            extended: {
                surfaceConditions: {},
                roadAlignment: {},
                roadDefect: 0,
                relationToRoadway: {},
                firstHarmfulEventLoc: {},
                unrestrained: 0,
                drowsy: 0,
                drugRelated: 0,
                hitrun: 0,
                senior: 0,
                young: 0,
                motorcycle: 0,
                lgtruck: 0,
                guardrailRelated: 0,
                roadDeparture: 0,
                speedDiffs: [],
                peakPeriods: { am: 0, midday: 0, pm: 0, evening: 0, night: 0 },
                weekday: 0,
                weekend: 0,
                byYear: {},
                workZone: 0,
                schoolZone: 0
            }
        };

        crashes.forEach(function(row) {
            var sev = row[COL.SEVERITY] || 'O';
            if (profile.severity[sev] !== undefined) {
                profile.severity[sev]++;
            }

            // Collision type with EPDO tracking
            var collision = row[COL.COLLISION] || 'Unknown';
            profile.collisionTypes[collision] = (profile.collisionTypes[collision] || 0) + 1;
            profile.collisionTypesEPDO[collision] = (profile.collisionTypesEPDO[collision] || 0) + (EPDO_WEIGHTS[sev] || 0);

            // Weather
            var weather = row[COL.WEATHER] || 'Unknown';
            profile.weatherConditions[weather] = (profile.weatherConditions[weather] || 0) + 1;

            // Light
            var light = row[COL.LIGHT] || 'Unknown';
            profile.lightConditions[light] = (profile.lightConditions[light] || 0) + 1;

            // Factors
            if (row[COL.PED] === 'Yes' || row[COL.PED] === '1') profile.factors.pedestrian++;
            if (row[COL.BIKE] === 'Yes' || row[COL.BIKE] === '1') profile.factors.bicycle++;
            if (row[COL.ALCOHOL] === 'Yes' || row[COL.ALCOHOL] === '1') profile.factors.alcohol++;
            if (row[COL.SPEED] === 'Yes' || row[COL.SPEED] === '1') profile.factors.speed++;
            if (row[COL.DISTRACTED] === 'Yes' || row[COL.DISTRACTED] === '1') profile.factors.distracted++;
            if (row[COL.NIGHT] === 'Yes' || row[COL.NIGHT] === '1') profile.factors.nighttime++;

            // Wet road
            var surface = (row[COL.SURFACE] || '').toLowerCase();
            if (surface.includes('wet') || surface.includes('snow') || surface.includes('ice')) {
                profile.factors.wetRoad++;
            }

            // Intersection
            var intType = row[COL.INT_TYPE] || '';
            if (intType && !intType.toLowerCase().includes('non') && !intType.toLowerCase().includes('not')) {
                profile.factors.intersection++;
            }

            // EPDO
            profile.epdo += EPDO_WEIGHTS[sev] || 0;

            // ========== EXTENDED DATA AGGREGATION ==========

            // Surface conditions
            var surfaceCond = row[COL.SURFACE] || 'Unknown';
            profile.extended.surfaceConditions[surfaceCond] = (profile.extended.surfaceConditions[surfaceCond] || 0) + 1;

            // Road alignment
            var alignment = row[COL.ALIGNMENT] || 'Unknown';
            profile.extended.roadAlignment[alignment] = (profile.extended.roadAlignment[alignment] || 0) + 1;

            // Road defect
            var defect = row[COL.ROAD_DEFECT] || '';
            if (defect && !defect.toLowerCase().includes('no defect')) {
                profile.extended.roadDefect++;
            }

            // Relation to roadway
            var relation = row[COL.RELATION_TO_ROAD] || 'Unknown';
            profile.extended.relationToRoadway[relation] = (profile.extended.relationToRoadway[relation] || 0) + 1;

            // First harmful event location
            var harmfulLoc = row[COL.FIRST_HARMFUL_LOC] || 'Unknown';
            profile.extended.firstHarmfulEventLoc[harmfulLoc] = (profile.extended.firstHarmfulEventLoc[harmfulLoc] || 0) + 1;

            // Driver/Vehicle factors
            if (row[COL.UNRESTRAINED] === 'Yes' || row[COL.UNRESTRAINED] === 'Unbelted') profile.extended.unrestrained++;
            if (row[COL.DROWSY] === 'Yes' || row[COL.DROWSY] === '1') profile.extended.drowsy++;
            if (row[COL.DRUG] === 'Yes' || row[COL.DRUG] === '1') profile.extended.drugRelated++;
            if (row[COL.HITRUN] === 'Yes' || row[COL.HITRUN] === '1') profile.extended.hitrun++;
            if (row[COL.SENIOR] === 'Yes' || row[COL.SENIOR] === '1') profile.extended.senior++;
            if (row[COL.YOUNG] === 'Yes' || row[COL.YOUNG] === '1') profile.extended.young++;
            if (row[COL.MOTORCYCLE] === 'Yes' || row[COL.MOTORCYCLE] === '1') profile.extended.motorcycle++;
            if (row[COL.LGTRUCK] === 'Yes' || row[COL.LGTRUCK] === '1') profile.extended.lgtruck++;
            if (row[COL.GUARDRAIL] === 'Yes' || row[COL.GUARDRAIL] === '1') profile.extended.guardrailRelated++;

            // Road departure
            var rdType = row[COL.ROAD_DEPARTURE] || '';
            if (rdType && rdType !== 'NOT_RD' && rdType.trim() !== '') {
                profile.extended.roadDeparture++;
            }

            // Speed diff collection
            var speedDiff = parseFloat(row[COL.MAX_SPEED_DIFF]);
            if (!isNaN(speedDiff) && speedDiff > 0) {
                profile.extended.speedDiffs.push(speedDiff);
            }

            // Temporal: Peak periods from military time
            var time = row[COL.TIME] || '';
            if (time) {
                var hour = parseInt(time.substring(0, 2)) || parseInt(time.split(':')[0]) || 0;
                if (hour >= 6 && hour < 9) profile.extended.peakPeriods.am++;
                else if (hour >= 9 && hour < 15) profile.extended.peakPeriods.midday++;
                else if (hour >= 15 && hour < 19) profile.extended.peakPeriods.pm++;
                else if (hour >= 19 && hour < 22) profile.extended.peakPeriods.evening++;
                else profile.extended.peakPeriods.night++;
            }

            // Weekday vs Weekend
            var dateVal = row[COL.DATE];
            if (dateVal) {
                var crashDate = new Date(Number(dateVal));
                if (!isNaN(crashDate.getTime())) {
                    var dow = crashDate.getDay();
                    if (dow === 0 || dow === 6) {
                        profile.extended.weekend++;
                    } else {
                        profile.extended.weekday++;
                    }
                }
            }

            // Year tracking
            var year = row[COL.YEAR];
            if (year) {
                profile.extended.byYear[year] = (profile.extended.byYear[year] || 0) + 1;
            }

            // Special Zones
            var workZone = row[COL.WORKZONE] || '';
            if (workZone === 'Yes' || workZone === '1' || workZone === '1. Yes') {
                profile.extended.workZone++;
            }
            var schoolZone = row[COL.SCHOOL] || '';
            if (schoolZone === 'Yes' || schoolZone === '1' || schoolZone === '1. Yes') {
                profile.extended.schoolZone++;
            }
        });

        // Calculate average speed diff
        if (profile.extended.speedDiffs.length > 0) {
            profile.extended.avgSpeedDiff = (profile.extended.speedDiffs.reduce(function(a, b) { return a + b; }, 0) / profile.extended.speedDiffs.length).toFixed(1);
        } else {
            profile.extended.avgSpeedDiff = null;
        }

        return profile;
    }
};

CL._registerModule('analysis/crash-profile');
