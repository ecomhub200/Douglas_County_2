/**
 * CrashLens Batch Before/After Evaluation — Study Duration Configuration
 * Provides interactive UI for configuring before/after study periods per location,
 * with feasibility checks based on available crash data date range.
 */
window.CL = window.CL || {};
CL.batchBA = CL.batchBA || {};
CL.batchBA.duration = {};

// Minimum months for a valid B/A study (FHWA recommendation)
var BA_MIN_STUDY_MONTHS = 12;

/**
 * Calculate integer months between two dates (calendar-based).
 * @param {Date} dateA - Start date
 * @param {Date} dateB - End date
 * @returns {number} Whole months (floored), or 0 if dateB <= dateA
 */
CL.batchBA.duration._monthsBetween = function(dateA, dateB) {
    if (!dateA || !dateB || dateB <= dateA) return 0;
    return (dateB.getFullYear() - dateA.getFullYear()) * 12 +
           (dateB.getMonth() - dateA.getMonth());
};

/**
 * Compute feasibility status for a location's study periods.
 * @param {number} beforeMonths
 * @param {number} afterMonths
 * @param {Date|null} installDate
 * @returns {string} 'valid' | 'warning' | 'insufficient' | 'missing'
 */
CL.batchBA.duration._computeStatus = function(beforeMonths, afterMonths, installDate) {
    if (!installDate) return 'missing';
    var minPeriod = Math.min(beforeMonths, afterMonths);
    if (minPeriod >= BA_MIN_STUDY_MONTHS) return 'valid';
    if (minPeriod >= 6) return 'warning';
    return 'insufficient';
};

/**
 * Return HTML for a status badge.
 * @param {string} status
 * @returns {string} HTML
 */
CL.batchBA.duration._statusBadge = function(status) {
    var map = {
        valid:        { icon: '\u2705', label: 'Valid',        bg: '#dcfce7', color: '#15803d' },
        warning:      { icon: '\u26A0\uFE0F', label: 'Warning',     bg: '#fef9c3', color: '#a16207' },
        insufficient: { icon: '\u274C', label: 'Insufficient', bg: '#fef2f2', color: '#dc2626' },
        missing:      { icon: '\uD83D\uDEAB', label: 'No Date',     bg: '#f1f5f9', color: '#64748b' }
    };
    var s = map[status] || map.missing;
    return '<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:9999px;font-size:.75rem;font-weight:600;background:' + s.bg + ';color:' + s.color + '">' + s.icon + ' ' + s.label + '</span>';
};

/**
 * Initialize duration configuration for all valid rows.
 * Called after validation succeeds.
 */
CL.batchBA.duration.init = function() {
    var s = CL.batchBA.state;
    CL.batchBA.duration._computeLocationDurations();

    // If uniform mode, apply the median feasible default to all
    if (s.uniformDuration && s.locationDurations.length > 0) {
        var feasible = s.locationDurations.filter(function(d) { return d.status !== 'missing'; });
        if (feasible.length > 0) {
            // Use the minimum of all max defaults as the uniform value
            var uniformVal = Infinity;
            feasible.forEach(function(d) {
                var maxSymmetric = Math.min(d.maxBeforeMonths, d.maxAfterMonths);
                if (maxSymmetric < uniformVal) uniformVal = maxSymmetric;
            });
            uniformVal = Math.max(BA_MIN_STUDY_MONTHS, uniformVal);
            s.locationDurations.forEach(function(d) {
                if (d.status === 'missing') return;
                d.beforeMonths = Math.min(uniformVal, d.maxBeforeMonths);
                d.afterMonths = Math.min(uniformVal, d.maxAfterMonths);
                d.status = CL.batchBA.duration._computeStatus(d.beforeMonths, d.afterMonths, d.installDate);
            });
        }
    }
};

/**
 * Compute max available before/after months for each valid row.
 */
CL.batchBA.duration._computeLocationDurations = function() {
    var s = CL.batchBA.state;
    var dataStart = (typeof getMinCrashDate === 'function') ? getMinCrashDate() : null;
    var dataEnd = (typeof getMaxCrashDate === 'function') ? getMaxCrashDate() : null;
    var buffer = s.constructionBuffer || 0;

    s.locationDurations = [];

    // Guard: cannot compute durations without valid crash data date range
    if (!dataStart || !dataEnd || dataEnd <= dataStart) return;

    s.validRows.forEach(function(row) {
        var installDate = row.installDate;
        if (!installDate) {
            s.locationDurations.push({
                installDate: null,
                maxBeforeMonths: 0,
                maxAfterMonths: 0,
                beforeMonths: 0,
                afterMonths: 0,
                status: 'missing'
            });
            return;
        }

        // Effective before-end and after-start with buffer
        var beforeEndDate = new Date(installDate);
        beforeEndDate.setMonth(beforeEndDate.getMonth() - buffer);
        var afterStartDate = new Date(installDate);
        afterStartDate.setMonth(afterStartDate.getMonth() + buffer);

        var maxBefore = dataStart ? CL.batchBA.duration._monthsBetween(dataStart, beforeEndDate) : 0;
        var maxAfter = dataEnd ? CL.batchBA.duration._monthsBetween(afterStartDate, dataEnd) : 0;
        maxBefore = Math.max(0, maxBefore);
        maxAfter = Math.max(0, maxAfter);

        // Default: symmetric, clamped to min study duration
        var defaultDur = Math.max(BA_MIN_STUDY_MONTHS, Math.min(maxBefore, maxAfter));

        // If CSV provided studyDuration, use as initial (clamped)
        var csvDuration = row.studyDuration || null;
        var beforeMonths, afterMonths;
        if (csvDuration) {
            beforeMonths = Math.min(csvDuration, maxBefore);
            afterMonths = Math.min(csvDuration, maxAfter);
        } else {
            beforeMonths = Math.min(defaultDur, maxBefore);
            afterMonths = Math.min(defaultDur, maxAfter);
        }

        var status = CL.batchBA.duration._computeStatus(beforeMonths, afterMonths, installDate);

        s.locationDurations.push({
            installDate: installDate,
            maxBeforeMonths: maxBefore,
            maxAfterMonths: maxAfter,
            beforeMonths: beforeMonths,
            afterMonths: afterMonths,
            status: status
        });
    });
};

/**
 * Render the full duration configuration section.
 */
CL.batchBA.duration.render = function() {
    var el = document.getElementById('batchBADurationContent');
    if (!el) return;

    var html = '';
    html += CL.batchBA.duration._renderGlobalControls();
    html += CL.batchBA.duration._renderSummaryStats();
    html += CL.batchBA.duration._renderLocationTable();

    el.innerHTML = html;
};

/**
 * Render global controls: buffer, uniform toggle, symmetric lock.
 */
CL.batchBA.duration._renderGlobalControls = function() {
    var s = CL.batchBA.state;
    var html = '<div style="display:flex;flex-wrap:wrap;gap:1rem;align-items:flex-end;margin-bottom:1rem">';

    // Construction buffer
    html += '<div class="filter-group" style="min-width:180px">';
    html += '<label style="font-size:.85rem;font-weight:600;color:#1d4ed8">Construction Buffer</label>';
    html += '<select id="batchBABufferSelect" onchange="CL.batchBA.duration._onBufferChange(this.value)" style="font-size:.85rem">';
    [0, 3, 6].forEach(function(v) {
        var sel = s.constructionBuffer === v ? ' selected' : '';
        var label = v === 0 ? 'None (0 mo)' : v === 3 ? 'Standard (3 mo)' : 'Extended (6 mo)';
        html += '<option value="' + v + '"' + sel + '>' + label + '</option>';
    });
    html += '</select>';
    html += '<div style="font-size:.7rem;color:#64748b;margin-top:2px">Excludes months around install date</div>';
    html += '</div>';

    // Uniform duration toggle
    html += '<div style="display:flex;align-items:center;gap:.5rem;padding-bottom:4px">';
    html += '<label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:.85rem;font-weight:600;color:#1d4ed8">';
    html += '<input type="checkbox" id="batchBAUniformToggle" ' + (s.uniformDuration ? 'checked' : '') + ' onchange="CL.batchBA.duration._onUniformToggle(this.checked)" style="width:16px;height:16px">';
    html += 'Apply Uniform Duration</label>';
    html += '</div>';

    // Symmetric lock toggle
    html += '<div style="display:flex;align-items:center;gap:.5rem;padding-bottom:4px">';
    html += '<label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:.85rem;font-weight:600;color:#1d4ed8">';
    html += '<input type="checkbox" id="batchBASymmetricToggle" ' + (s.symmetricLock ? 'checked' : '') + ' onchange="CL.batchBA.duration._onSymmetricToggle(this.checked)" style="width:16px;height:16px">';
    html += '\uD83D\uDD17 Symmetric (Before = After)</label>';
    html += '</div>';

    html += '</div>';

    // Uniform duration sliders (only when uniform mode is on)
    if (s.uniformDuration) {
        html += CL.batchBA.duration._renderUniformSliders();
    }

    // Min study duration info
    html += '<div style="font-size:.75rem;color:#64748b;margin-bottom:.75rem">';
    html += '<strong>Min study duration:</strong> ' + BA_MIN_STUDY_MONTHS + ' months (FHWA recommended minimum for valid B/A study)';

    // Show data range
    var dataStart = (typeof getMinCrashDate === 'function') ? getMinCrashDate() : null;
    var dataEnd = (typeof getMaxCrashDate === 'function') ? getMaxCrashDate() : null;
    if (dataStart && dataEnd) {
        html += ' &nbsp;|&nbsp; <strong>Data range:</strong> ' +
            CL.batchBA.duration._formatDate(dataStart) + ' to ' +
            CL.batchBA.duration._formatDate(dataEnd);
    }
    html += '</div>';

    return html;
};

/**
 * Render uniform duration sliders (shown when uniform mode is on).
 */
CL.batchBA.duration._renderUniformSliders = function() {
    var s = CL.batchBA.state;
    var durations = s.locationDurations.filter(function(d) { return d.status !== 'missing'; });
    if (durations.length === 0) return '';

    // Find the max possible uniform value (min of all maxes)
    var maxUniformBefore = Infinity, maxUniformAfter = Infinity;
    durations.forEach(function(d) {
        if (d.maxBeforeMonths < maxUniformBefore) maxUniformBefore = d.maxBeforeMonths;
        if (d.maxAfterMonths < maxUniformAfter) maxUniformAfter = d.maxAfterMonths;
    });

    // Current uniform value (take from first feasible location)
    var currentBefore = durations[0].beforeMonths;
    var currentAfter = durations[0].afterMonths;

    var html = '<div style="background:white;border:1px solid #bfdbfe;border-radius:var(--radius);padding:.75rem;margin-bottom:1rem">';
    html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">';

    // Before slider
    html += '<div>';
    html += '<label style="font-size:.8rem;font-weight:600;color:#1e40af">Before Period (months)</label>';
    html += '<div style="display:flex;align-items:center;gap:.5rem">';
    html += '<input type="range" id="batchBAUniformBefore" min="1" max="' + maxUniformBefore + '" value="' + currentBefore + '" ';
    html += 'oninput="CL.batchBA.duration._onUniformDurationChange(\'before\',parseInt(this.value))" style="flex:1">';
    html += '<span id="batchBAUniformBeforeVal" style="font-weight:700;color:#1e40af;min-width:40px">' + currentBefore + '</span>';
    html += '</div>';
    html += '<div style="display:flex;justify-content:space-between;font-size:.65rem;color:#94a3b8"><span>1</span><span>' + maxUniformBefore + ' max</span></div>';
    html += '</div>';

    // After slider
    html += '<div>';
    html += '<label style="font-size:.8rem;font-weight:600;color:#1e40af">After Period (months)</label>';
    html += '<div style="display:flex;align-items:center;gap:.5rem">';
    html += '<input type="range" id="batchBAUniformAfter" min="1" max="' + maxUniformAfter + '" value="' + currentAfter + '" ';
    if (s.symmetricLock) html += 'disabled ';
    html += 'oninput="CL.batchBA.duration._onUniformDurationChange(\'after\',parseInt(this.value))" style="flex:1">';
    html += '<span id="batchBAUniformAfterVal" style="font-weight:700;color:#1e40af;min-width:40px">' + currentAfter + '</span>';
    html += '</div>';
    html += '<div style="display:flex;justify-content:space-between;font-size:.65rem;color:#94a3b8"><span>1</span><span>' + maxUniformAfter + ' max</span></div>';
    if (s.symmetricLock) {
        html += '<div style="font-size:.7rem;color:#94a3b8;font-style:italic">Locked to before value</div>';
    }
    html += '</div>';

    html += '</div>';

    // Show clamping warning if needed
    var clampedCount = 0;
    durations.forEach(function(d) {
        if (d.beforeMonths < currentBefore || d.afterMonths < currentAfter) clampedCount++;
    });
    if (clampedCount > 0) {
        html += '<div style="font-size:.75rem;color:#a16207;margin-top:.5rem">\u26A0\uFE0F ' + clampedCount + ' location(s) clamped to their maximum available period.</div>';
    }

    html += '</div>';
    return html;
};

/**
 * Render summary statistics.
 */
CL.batchBA.duration._renderSummaryStats = function() {
    var durations = CL.batchBA.state.locationDurations;
    var counts = { valid: 0, warning: 0, insufficient: 0, missing: 0 };
    var totalBefore = 0, totalAfter = 0, feasibleCount = 0;

    durations.forEach(function(d) {
        counts[d.status] = (counts[d.status] || 0) + 1;
        if (d.status !== 'missing') {
            totalBefore += d.beforeMonths;
            totalAfter += d.afterMonths;
            feasibleCount++;
        }
    });

    var avgBefore = feasibleCount > 0 ? (totalBefore / feasibleCount).toFixed(1) : 0;
    var avgAfter = feasibleCount > 0 ? (totalAfter / feasibleCount).toFixed(1) : 0;

    var html = '<div style="display:flex;flex-wrap:wrap;gap:.75rem;margin-bottom:1rem">';

    // Status counts
    html += '<div style="display:flex;gap:.5rem;align-items:center">';
    if (counts.valid > 0) html += CL.batchBA.duration._statusBadge('valid') + ' <span style="font-size:.8rem;font-weight:600">' + counts.valid + '</span>';
    if (counts.warning > 0) html += CL.batchBA.duration._statusBadge('warning') + ' <span style="font-size:.8rem;font-weight:600">' + counts.warning + '</span>';
    if (counts.insufficient > 0) html += CL.batchBA.duration._statusBadge('insufficient') + ' <span style="font-size:.8rem;font-weight:600">' + counts.insufficient + '</span>';
    if (counts.missing > 0) html += CL.batchBA.duration._statusBadge('missing') + ' <span style="font-size:.8rem;font-weight:600">' + counts.missing + '</span>';
    html += '</div>';

    // Averages
    html += '<div style="margin-left:auto;font-size:.8rem;color:#475569">';
    html += 'Avg before: <strong>' + avgBefore + ' mo</strong> &nbsp;|&nbsp; Avg after: <strong>' + avgAfter + ' mo</strong>';
    html += '</div>';

    html += '</div>';
    return html;
};

/**
 * Render the per-location duration table.
 */
CL.batchBA.duration._renderLocationTable = function() {
    var s = CL.batchBA.state;
    var rows = s.validRows;
    var durations = s.locationDurations;
    if (rows.length === 0) return '';

    var html = '<div style="max-height:400px;overflow-y:auto;border:1px solid #e2e8f0;border-radius:var(--radius)">';
    html += '<table class="data-table" style="font-size:.8rem;margin:0">';
    html += '<thead><tr>';
    html += '<th style="width:30px">#</th>';
    html += '<th>Location</th>';
    html += '<th style="width:90px">Install Date</th>';
    html += '<th style="width:80px">Max Before</th>';
    html += '<th style="width:100px">Before (mo)</th>';
    html += '<th style="width:100px">After (mo)</th>';
    html += '<th style="width:80px">Max After</th>';
    html += '<th style="width:90px">Status</th>';
    html += '</tr></thead><tbody>';

    rows.forEach(function(row, idx) {
        var d = durations[idx];
        if (!d) return;

        var rowBg = d.status === 'insufficient' ? 'background:#fef2f2' :
                    d.status === 'warning' ? 'background:#fefce8' : '';

        html += '<tr style="' + rowBg + '">';
        html += '<td>' + (idx + 1) + '</td>';
        html += '<td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + (row.locationName || '').replace(/"/g, '&quot;') + '">' + (row.locationName || 'N/A') + '</td>';
        html += '<td>' + (d.installDate ? CL.batchBA.duration._formatDate(d.installDate) : 'N/A') + '</td>';
        html += '<td style="text-align:center;color:#64748b">' + d.maxBeforeMonths + '</td>';

        // Before input
        html += '<td>';
        if (d.status !== 'missing') {
            html += '<input type="number" min="1" max="' + d.maxBeforeMonths + '" value="' + d.beforeMonths + '" ';
            html += 'onchange="CL.batchBA.duration._onLocationDurationChange(' + idx + ',\'before\',parseInt(this.value))" ';
            html += 'style="width:60px;font-size:.8rem;padding:2px 4px;text-align:center;border:1px solid #cbd5e1;border-radius:4px" ';
            if (s.uniformDuration) html += 'disabled title="Controlled by uniform duration"';
            html += '>';
        } else {
            html += '<span style="color:#94a3b8">\u2014</span>';
        }
        html += '</td>';

        // After input
        html += '<td>';
        if (d.status !== 'missing') {
            html += '<input type="number" min="1" max="' + d.maxAfterMonths + '" value="' + d.afterMonths + '" ';
            html += 'onchange="CL.batchBA.duration._onLocationDurationChange(' + idx + ',\'after\',parseInt(this.value))" ';
            html += 'style="width:60px;font-size:.8rem;padding:2px 4px;text-align:center;border:1px solid #cbd5e1;border-radius:4px" ';
            if (s.uniformDuration || s.symmetricLock) html += 'disabled title="' + (s.uniformDuration ? 'Controlled by uniform duration' : 'Locked to before value') + '"';
            html += '>';
        } else {
            html += '<span style="color:#94a3b8">\u2014</span>';
        }
        html += '</td>';

        html += '<td style="text-align:center;color:#64748b">' + d.maxAfterMonths + '</td>';
        html += '<td>' + CL.batchBA.duration._statusBadge(d.status) + '</td>';
        html += '</tr>';
    });

    html += '</tbody></table></div>';
    return html;
};

/**
 * Format a Date object as YYYY-MM.
 */
CL.batchBA.duration._formatDate = function(date) {
    if (!date) return '';
    var y = date.getFullYear();
    var m = ('0' + (date.getMonth() + 1)).slice(-2);
    return y + '-' + m;
};

// ——— Event Handlers ———

/**
 * Construction buffer changed.
 */
CL.batchBA.duration._onBufferChange = function(value) {
    CL.batchBA.state.constructionBuffer = parseInt(value) || 0;
    CL.batchBA.duration._computeLocationDurations();
    CL.batchBA.duration._applyUniformIfNeeded();
    CL.batchBA.duration.render();
};

/**
 * Uniform toggle changed.
 */
CL.batchBA.duration._onUniformToggle = function(checked) {
    CL.batchBA.state.uniformDuration = checked;
    if (checked) {
        CL.batchBA.duration._applyUniformIfNeeded();
    }
    CL.batchBA.duration.render();
};

/**
 * Symmetric lock toggle changed.
 */
CL.batchBA.duration._onSymmetricToggle = function(checked) {
    CL.batchBA.state.symmetricLock = checked;
    if (checked) {
        // Sync after to match before for all locations
        CL.batchBA.state.locationDurations.forEach(function(d) {
            if (d.status === 'missing') return;
            d.afterMonths = Math.min(d.beforeMonths, d.maxAfterMonths);
            d.status = CL.batchBA.duration._computeStatus(d.beforeMonths, d.afterMonths, d.installDate);
        });
    }
    CL.batchBA.duration.render();
};

/**
 * Uniform slider value changed.
 */
CL.batchBA.duration._onUniformDurationChange = function(field, value) {
    var s = CL.batchBA.state;
    if (isNaN(value) || value < 1) return;

    s.locationDurations.forEach(function(d) {
        if (d.status === 'missing') return;
        if (field === 'before') {
            d.beforeMonths = Math.min(value, d.maxBeforeMonths);
            if (s.symmetricLock) {
                d.afterMonths = Math.min(d.beforeMonths, d.maxAfterMonths);
            }
        } else {
            d.afterMonths = Math.min(value, d.maxAfterMonths);
        }
        d.status = CL.batchBA.duration._computeStatus(d.beforeMonths, d.afterMonths, d.installDate);
    });

    // Update display labels without full re-render
    var beforeLabel = document.getElementById('batchBAUniformBeforeVal');
    var afterLabel = document.getElementById('batchBAUniformAfterVal');
    var afterSlider = document.getElementById('batchBAUniformAfter');

    if (field === 'before') {
        if (beforeLabel) beforeLabel.textContent = value;
        if (s.symmetricLock && afterSlider) {
            afterSlider.value = value;
            if (afterLabel) afterLabel.textContent = value;
        }
    } else {
        if (afterLabel) afterLabel.textContent = value;
    }

    // Update table and summary (partial re-render)
    CL.batchBA.duration.render();
};

/**
 * Per-location duration input changed (individual mode).
 */
CL.batchBA.duration._onLocationDurationChange = function(index, field, value) {
    var s = CL.batchBA.state;
    var d = s.locationDurations[index];
    if (!d || d.status === 'missing') return;
    if (isNaN(value) || value < 1) return;

    if (field === 'before') {
        d.beforeMonths = Math.min(value, d.maxBeforeMonths);
        if (s.symmetricLock) {
            d.afterMonths = Math.min(d.beforeMonths, d.maxAfterMonths);
        }
    } else {
        d.afterMonths = Math.min(value, d.maxAfterMonths);
    }
    d.status = CL.batchBA.duration._computeStatus(d.beforeMonths, d.afterMonths, d.installDate);
    CL.batchBA.duration.render();
};

/**
 * Apply uniform duration values to all locations.
 */
CL.batchBA.duration._applyUniformIfNeeded = function() {
    var s = CL.batchBA.state;
    if (!s.uniformDuration) return;

    var feasible = s.locationDurations.filter(function(d) { return d.status !== 'missing'; });
    if (feasible.length === 0) return;

    // Find min of maxes for uniform cap
    var minMaxBefore = Infinity, minMaxAfter = Infinity;
    feasible.forEach(function(d) {
        if (d.maxBeforeMonths < minMaxBefore) minMaxBefore = d.maxBeforeMonths;
        if (d.maxAfterMonths < minMaxAfter) minMaxAfter = d.maxAfterMonths;
    });

    var uniformBefore = Math.max(BA_MIN_STUDY_MONTHS, s.symmetricLock ? Math.min(minMaxBefore, minMaxAfter) : minMaxBefore);
    var uniformAfter = s.symmetricLock ? uniformBefore : Math.max(BA_MIN_STUDY_MONTHS, minMaxAfter);

    s.locationDurations.forEach(function(d) {
        if (d.status === 'missing') return;
        d.beforeMonths = Math.min(uniformBefore, d.maxBeforeMonths);
        d.afterMonths = Math.min(uniformAfter, d.maxAfterMonths);
        d.status = CL.batchBA.duration._computeStatus(d.beforeMonths, d.afterMonths, d.installDate);
    });
};

CL._registerModule('batch-ba/duration');
