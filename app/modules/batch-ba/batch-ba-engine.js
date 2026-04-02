/**
 * CrashLens Batch Before/After Evaluation — Processing Engine
 * Runs B/A analysis for each location using spatial crash filtering.
 */
window.CL = window.CL || {};
CL.batchBA = CL.batchBA || {};

/**
 * Start batch processing of all valid locations.
 */
CL.batchBA.startProcessing = function() {
    var s = CL.batchBA.state;
    if (s.processing) return;
    if (s.validRows.length === 0) {
        alert('No valid locations to process. Please upload and validate a file first.');
        return;
    }
    if (!crashState || !crashState.mapPoints || crashState.mapPoints.length === 0) {
        alert('No crash data loaded. Please load crash data before running batch analysis.');
        return;
    }

    s.processing = true;
    s.results = [];
    s.progress = { current: 0, total: s.validRows.length, currentName: '' };

    // Show progress UI
    document.getElementById('batchBAProgressSection').style.display = 'block';
    document.getElementById('batchBAResultsSection').style.display = 'none';
    CL.batchBA._updateProgressUI();

    // Process in chunks to avoid UI freeze
    CL.batchBA._processChunk(0, 5);
};

/**
 * Process a chunk of locations starting at `startIdx`, `chunkSize` at a time.
 */
CL.batchBA._processChunk = function(startIdx, chunkSize) {
    var s = CL.batchBA.state;
    var rows = s.validRows;
    var endIdx = Math.min(startIdx + chunkSize, rows.length);

    for (var i = startIdx; i < endIdx; i++) {
        var row = rows[i];
        s.progress.current = i + 1;
        s.progress.currentName = row.locationName;

        try {
            var result = CL.batchBA._analyzeLocation(row, i);
            s.results.push(result);
        } catch (err) {
            console.error('[BatchBA] Error processing location:', row.locationName, err);
            s.results.push({
                locationName: row.locationName,
                lat: row.lat,
                lng: row.lng,
                countermeasureType: row.countermeasureType || '',
                installDate: row.installDate,
                error: err.message || 'Unknown error',
                status: 'error'
            });
        }
    }

    CL.batchBA._updateProgressUI();

    if (endIdx < rows.length) {
        // Schedule next chunk
        setTimeout(function() {
            CL.batchBA._processChunk(endIdx, chunkSize);
        }, 50);
    } else {
        // Processing complete
        s.processing = false;
        CL.batchBA._computeSummary();
        document.getElementById('batchBAProgressSection').style.display = 'none';
        CL.batchBA.renderResults();
    }
};

/**
 * Analyze a single location: find crashes within radius, split before/after, compute stats.
 * @param {Object} location - { locationName, lat, lng, installDate, countermeasureType, studyDuration, radiusFt }
 * @returns {Object} Result object with all computed metrics.
 */
CL.batchBA._analyzeLocation = function(location, locationIndex) {
    var s = CL.batchBA.state;
    var radiusFt = location.radiusFt || s.globalRadiusFt;
    var radiusMeters = radiusFt * 0.3048;
    var installDate = location.installDate;
    var now = new Date();

    // Determine study periods using duration configuration if available
    var durationConfig = (typeof locationIndex === 'number' && s.locationDurations[locationIndex]) ?
        s.locationDurations[locationIndex] : null;
    var buffer = s.constructionBuffer || 0;

    var afterStart, afterEnd, beforeStart, beforeEnd;

    if (durationConfig && durationConfig.beforeMonths > 0 && durationConfig.afterMonths > 0) {
        // Use configured durations with construction buffer
        beforeEnd = new Date(installDate);
        beforeEnd.setMonth(beforeEnd.getMonth() - buffer);
        beforeEnd.setDate(beforeEnd.getDate() - 1);

        afterStart = new Date(installDate);
        afterStart.setMonth(afterStart.getMonth() + buffer);

        beforeStart = new Date(beforeEnd);
        beforeStart.setMonth(beforeStart.getMonth() - durationConfig.beforeMonths);

        afterEnd = new Date(afterStart);
        afterEnd.setMonth(afterEnd.getMonth() + durationConfig.afterMonths);
        if (afterEnd > now) afterEnd = now;
    } else {
        // Fallback: original logic (no duration config)
        var studyMonths = location.studyDuration || null;
        afterEnd = now;
        afterStart = new Date(installDate);
        afterStart.setMonth(afterStart.getMonth() + buffer);
        beforeEnd = new Date(installDate);
        beforeEnd.setMonth(beforeEnd.getMonth() - buffer);
        beforeEnd.setDate(beforeEnd.getDate() - 1);

        if (studyMonths) {
            afterEnd = new Date(installDate);
            afterEnd.setMonth(afterEnd.getMonth() + studyMonths);
            if (afterEnd > now) afterEnd = now;
            beforeStart = new Date(installDate);
            beforeStart.setMonth(beforeStart.getMonth() - studyMonths);
        } else {
            var afterMs = afterEnd - afterStart;
            beforeStart = new Date(beforeEnd.getTime() - afterMs);
        }
    }

    // Safety: ensure no date overlap between before and after periods
    if (beforeEnd >= afterStart) {
        beforeEnd = new Date(afterStart);
        beforeEnd.setDate(beforeEnd.getDate() - 1);
    }
    // Safety: ensure before period is not negative-length after clamping
    if (beforeStart >= beforeEnd) {
        beforeStart = new Date(beforeEnd);
    }

    // Find crashes within radius using spatial filter
    var nearbyCrashes = CL.batchBA._findCrashesInRadius(location.lat, location.lng, radiusMeters);

    // Split into before/after periods
    var beforeCrashes = CL.batchBA._filterByPeriod(nearbyCrashes, beforeStart, beforeEnd);
    var afterCrashes = CL.batchBA._filterByPeriod(nearbyCrashes, afterStart, afterEnd);

    // Compute severity stats
    var beforeStats = CL.batchBA._computeSeverityStats(beforeCrashes);
    var afterStats = CL.batchBA._computeSeverityStats(afterCrashes);

    // Compute period lengths
    var beforeYears = Math.max((beforeEnd - beforeStart) / (365.25 * 24 * 3600 * 1000), 0.01);
    var afterYears = Math.max((afterEnd - afterStart) / (365.25 * 24 * 3600 * 1000), 0.01);

    // Compute CMF, CRF, significance
    var adjustmentFactor = afterYears / beforeYears;
    var expectedAfter = beforeStats.total * adjustmentFactor;
    var cmf, crf, pValue, isSignificant;

    if (beforeStats.total === 0 && afterStats.total === 0) {
        cmf = 1.0;
        crf = 0;
        pValue = 1.0;
        isSignificant = false;
    } else if (beforeStats.total === 0) {
        // Cannot compute meaningful CMF with zero before-crashes
        cmf = null;
        crf = null;
        pValue = 1.0;
        isSignificant = false;
    } else {
        cmf = afterStats.total / expectedAfter;
        crf = (1 - cmf) * 100;
        // Poisson significance test
        var variance = expectedAfter;
        var stdError = Math.sqrt(variance);
        if (stdError > 0) {
            var zScore = (expectedAfter - afterStats.total) / stdError;
            pValue = 2 * (1 - CL.batchBA._normalCDF(Math.abs(zScore)));
        } else {
            pValue = 1.0;
        }
        isSignificant = pValue < (1 - s.confidenceLevel);
    }

    // Get EPDO weights
    var stateFips = (typeof getCurrentStateFips === 'function') ? getCurrentStateFips() : '_default';
    var epdoInfo = CL.core.epdo.getStateEPDOWeights(stateFips);
    var weights = epdoInfo.weights;
    var beforeEPDO = CL.core.epdo.calcEPDO(beforeStats, weights);
    var afterEPDO = CL.core.epdo.calcEPDO(afterStats, weights);
    var epdoChangePct = beforeEPDO > 0 ? ((afterEPDO - beforeEPDO) / beforeEPDO * 100) : 0;

    var changePct = beforeStats.total > 0 ? ((afterStats.total - beforeStats.total) / beforeStats.total * 100) : 0;

    return {
        locationName: location.locationName,
        lat: location.lat,
        lng: location.lng,
        countermeasureType: location.countermeasureType || 'Not specified',
        installDate: installDate,
        radiusFt: radiusFt,
        beforeStart: beforeStart,
        beforeEnd: beforeEnd,
        afterStart: afterStart,
        afterEnd: afterEnd,
        beforeYears: beforeYears,
        afterYears: afterYears,
        beforeTotal: beforeStats.total,
        afterTotal: afterStats.total,
        changePct: changePct,
        beforeStats: beforeStats,
        afterStats: afterStats,
        beforeEPDO: beforeEPDO,
        afterEPDO: afterEPDO,
        epdoChangePct: epdoChangePct,
        cmf: cmf,
        crf: crf,
        pValue: pValue,
        isSignificant: isSignificant,
        nearbyCrashCount: nearbyCrashes.length,
        beforeCrashes: beforeCrashes,
        afterCrashes: afterCrashes,
        status: 'success'
    };
};

/**
 * Find all crashes within a radius (meters) of a lat/lng using Haversine.
 */
CL.batchBA._findCrashesInRadius = function(lat, lng, radiusMeters) {
    var points = crashState.mapPoints || [];
    var results = [];
    for (var i = 0; i < points.length; i++) {
        var p = points[i];
        if (p.lat == null || p.lng == null) continue;
        var dist = CL.batchBA._haversineMeters(lat, lng, p.lat, p.lng);
        if (dist <= radiusMeters) {
            results.push(p);
        }
    }
    return results;
};

/** Haversine distance in meters */
CL.batchBA._haversineMeters = function(lat1, lng1, lat2, lng2) {
    var R = 6371000;
    var dLat = (lat2 - lat1) * Math.PI / 180;
    var dLng = (lng2 - lng1) * Math.PI / 180;
    var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
};

/** Filter crash points by date period */
CL.batchBA._filterByPeriod = function(crashes, startDate, endDate) {
    return crashes.filter(function(c) {
        var dateVal = c.date !== undefined ? c.date :
            (typeof COL !== 'undefined' && COL.DATE ? c[COL.DATE] : 0);
        var num = Number(dateVal);
        // If numeric (epoch ms), use directly; otherwise parse as date string
        var d = !isNaN(num) && num > 0 ? new Date(num) : new Date(dateVal);
        if (isNaN(d.getTime())) return false;
        return d >= startDate && d <= endDate;
    });
};

/** Compute severity breakdown from map points */
CL.batchBA._computeSeverityStats = function(crashes) {
    var stats = { total: crashes.length, K: 0, A: 0, B: 0, C: 0, O: 0, U: 0, ped: 0, bike: 0 };
    for (var i = 0; i < crashes.length; i++) {
        var c = crashes[i];
        var s = (c.sev || '').charAt(0).toUpperCase();
        if (s === 'K' || s === 'A' || s === 'B' || s === 'C' || s === 'O') {
            stats[s]++;
        } else {
            stats.U++;
        }
        if (c.isPed) stats.ped++;
        if (c.isBike) stats.bike++;
    }
    return stats;
};

/** Normal CDF approximation */
CL.batchBA._normalCDF = function(x) {
    var a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741;
    var a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
    var sign = x < 0 ? -1 : 1;
    x = Math.abs(x) / Math.sqrt(2);
    var t = 1.0 / (1.0 + p * x);
    var y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
    return 0.5 * (1.0 + sign * y);
};

/** Update progress bar UI */
CL.batchBA._updateProgressUI = function() {
    var prog = CL.batchBA.state.progress;
    var pct = prog.total > 0 ? Math.round((prog.current / prog.total) * 100) : 0;
    var bar = document.getElementById('batchBAProgressBar');
    var text = document.getElementById('batchBAProgressText');
    if (bar) bar.style.width = pct + '%';
    if (text) text.textContent = 'Processing location ' + prog.current + ' of ' + prog.total + ': ' + prog.currentName;
};

/**
 * Compute batch summary statistics from results.
 */
CL.batchBA._computeSummary = function() {
    var results = CL.batchBA.state.results;
    var successful = results.filter(function(r) { return r.status === 'success'; });
    var errors = results.filter(function(r) { return r.status === 'error'; });

    if (successful.length === 0) {
        CL.batchBA.state.summary = { totalAnalyzed: 0, errors: errors.length };
        return;
    }

    var totalCrashChange = 0;
    var totalCMF = 0;
    var significantCount = 0;
    var crashesPrevented = 0;
    var byEffectiveness = { 'Highly Effective': 0, 'Effective': 0, 'Marginal': 0, 'Ineffective': 0, 'Negative Impact': 0 };
    var byType = {};

    var cmfCount = 0; // track locations with valid CMF
    successful.forEach(function(r) {
        totalCrashChange += r.changePct;
        if (r.cmf !== null) { totalCMF += r.cmf; cmfCount++; }
        if (r.isSignificant) significantCount++;
        crashesPrevented += (r.beforeTotal - r.afterTotal);
        var rating = CL.batchBA.getEffectivenessRating(r.cmf).label;
        byEffectiveness[rating] = (byEffectiveness[rating] || 0) + 1;

        var type = r.countermeasureType || 'Not specified';
        if (!byType[type]) byType[type] = { count: 0, totalCMF: 0, cmfCount: 0, totalChange: 0 };
        byType[type].count++;
        if (r.cmf !== null) { byType[type].totalCMF += r.cmf; byType[type].cmfCount++; }
        byType[type].totalChange += r.changePct;
    });

    CL.batchBA.state.summary = {
        totalAnalyzed: successful.length,
        errors: errors.length,
        avgCrashReduction: -(totalCrashChange / successful.length),
        avgCMF: cmfCount > 0 ? (totalCMF / cmfCount) : null,
        significantCount: significantCount,
        significantPct: (significantCount / successful.length * 100),
        crashesPrevented: crashesPrevented,
        byEffectiveness: byEffectiveness,
        byType: byType
    };
};

CL._registerModule('batch-ba/engine');
