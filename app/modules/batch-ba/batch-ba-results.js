/**
 * CrashLens Batch Before/After Evaluation — Results Dashboard
 * Renders summary cards, sortable/filterable table, and detail expansion.
 */
window.CL = window.CL || {};
CL.batchBA = CL.batchBA || {};

/**
 * Render the full results dashboard: summary cards + table + charts.
 */
CL.batchBA.renderResults = function() {
    var s = CL.batchBA.state;
    if (!s.summary || s.summary.totalAnalyzed === 0) {
        document.getElementById('batchBAResultsSection').style.display = 'block';
        document.getElementById('batchBAResultsContent').innerHTML = '<div class="info-box warning"><span class="icon">⚠️</span><div class="content"><p>No locations could be analyzed. Check that crash data is loaded and locations have valid coordinates within the data coverage area.</p></div></div>';
        return;
    }

    document.getElementById('batchBAResultsSection').style.display = 'block';
    CL.batchBA._renderSummaryCards();
    CL.batchBA._renderFilters();
    CL.batchBA._renderResultsTable();

    // Render charts
    if (typeof CL.batchBA.renderCharts === 'function') {
        setTimeout(function() { CL.batchBA.renderCharts(); }, 100);
    }

    document.getElementById('batchBAResultsSection').scrollIntoView({ behavior: 'smooth' });
};

/** Render KPI summary cards row */
CL.batchBA._renderSummaryCards = function() {
    var sum = CL.batchBA.state.summary;
    var html = '<div class="kpi-grid" style="grid-template-columns:repeat(5,1fr);gap:.75rem;margin-bottom:1.5rem">';

    var avgCMFDisplay = sum.avgCMF !== null ? sum.avgCMF.toFixed(3) : 'N/A';
    var avgCMFColor = sum.avgCMF !== null && sum.avgCMF < 1 ? '#15803d' : (sum.avgCMF !== null ? '#dc2626' : '#64748b');
    var avgCMFLight = sum.avgCMF !== null && sum.avgCMF < 1 ? '#22c55e' : (sum.avgCMF !== null ? '#ef4444' : '#94a3b8');

    html += CL.batchBA._kpiCard(sum.totalAnalyzed, 'Locations Analyzed', '#1e40af', '#3b82f6');
    html += CL.batchBA._kpiCard(sum.avgCrashReduction.toFixed(1) + '%', 'Avg Crash Reduction', sum.avgCrashReduction > 0 ? '#15803d' : '#dc2626', sum.avgCrashReduction > 0 ? '#22c55e' : '#ef4444');
    html += CL.batchBA._kpiCard(avgCMFDisplay, 'Avg Safety Score', avgCMFColor, avgCMFLight);
    html += CL.batchBA._kpiCard(sum.crashesPrevented, 'Crashes Prevented', '#7c3aed', '#a78bfa');
    html += CL.batchBA._kpiCard(sum.significantPct.toFixed(0) + '%', 'Significant Improvement', '#0369a1', '#38bdf8');

    html += '</div>';

    // Effectiveness distribution mini bar
    var eff = sum.byEffectiveness;
    html += '<div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:1rem">';
    var badges = [
        { label: 'Highly Effective', count: eff['Highly Effective'] || 0, color: '#16a34a' },
        { label: 'Effective', count: eff['Effective'] || 0, color: '#65a30d' },
        { label: 'Marginal', count: eff['Marginal'] || 0, color: '#ca8a04' },
        { label: 'Ineffective', count: eff['Ineffective'] || 0, color: '#ea580c' },
        { label: 'Negative Impact', count: eff['Negative Impact'] || 0, color: '#dc2626' }
    ];
    badges.forEach(function(b) {
        if (b.count > 0) {
            html += '<span style="display:inline-flex;align-items:center;gap:.35rem;padding:.25rem .65rem;border-radius:9999px;font-size:.8rem;font-weight:600;background:' + b.color + '20;color:' + b.color + '">' + b.count + ' ' + b.label + '</span>';
        }
    });
    html += '</div>';

    // Error summary
    if (sum.errors > 0) {
        html += '<div class="info-box warning" style="margin-bottom:1rem"><span class="icon">⚠️</span><div class="content"><p>' + sum.errors + ' location(s) could not be analyzed.</p></div></div>';
    }

    document.getElementById('batchBASummaryCards').innerHTML = html;
};

/** Build a single KPI card HTML */
CL.batchBA._kpiCard = function(value, label, colorDark, colorLight) {
    return '<div style="background:linear-gradient(135deg,' + colorDark + ',' + colorLight + ');color:white;padding:.75rem;border-radius:var(--radius);text-align:center">' +
        '<div style="font-size:1.3rem;font-weight:700">' + value + '</div>' +
        '<div style="font-size:.7rem;opacity:.9">' + label + '</div></div>';
};

/** Render filter/search bar */
CL.batchBA._renderFilters = function() {
    var s = CL.batchBA.state;
    var results = s.results.filter(function(r) { return r.status === 'success'; });

    // Get unique countermeasure types
    var types = {};
    results.forEach(function(r) { if (r.countermeasureType) types[r.countermeasureType] = true; });
    var typeList = Object.keys(types).sort();

    var html = '<div style="display:flex;gap:.75rem;flex-wrap:wrap;align-items:center;margin-bottom:1rem">';

    // Search
    html += '<input type="text" placeholder="Search locations..." style="flex:1;min-width:180px;padding:.4rem .75rem;border:1px solid var(--border);border-radius:var(--radius);font-size:.85rem" oninput="CL.batchBA._onFilterChange(\'searchText\',this.value)">';

    // Type filter
    if (typeList.length > 1) {
        html += '<select style="padding:.4rem .75rem;border:1px solid var(--border);border-radius:var(--radius);font-size:.85rem" onchange="CL.batchBA._onFilterChange(\'filterType\',this.value)">';
        html += '<option value="all">All Types</option>';
        typeList.forEach(function(t) { html += '<option value="' + t + '">' + t + '</option>'; });
        html += '</select>';
    }

    // Effectiveness filter
    html += '<select style="padding:.4rem .75rem;border:1px solid var(--border);border-radius:var(--radius);font-size:.85rem" onchange="CL.batchBA._onFilterChange(\'filterEffectiveness\',this.value)">';
    html += '<option value="all">All Ratings</option>';
    ['Highly Effective', 'Effective', 'Marginal', 'Ineffective', 'Negative Impact'].forEach(function(r) {
        html += '<option value="' + r + '">' + r + '</option>';
    });
    html += '</select>';

    // Significance filter
    html += '<select style="padding:.4rem .75rem;border:1px solid var(--border);border-radius:var(--radius);font-size:.85rem" onchange="CL.batchBA._onFilterChange(\'filterSignificance\',this.value)">';
    html += '<option value="all">All Significance</option>';
    html += '<option value="significant">Significant Only</option>';
    html += '<option value="not-significant">Not Significant</option>';
    html += '</select>';

    html += '</div>';

    document.getElementById('batchBAFilters').innerHTML = html;
};

CL.batchBA._onFilterChange = function(key, value) {
    CL.batchBA.state[key] = value;
    CL.batchBA._renderResultsTable();
};

CL.batchBA._onSortChange = function(column) {
    var s = CL.batchBA.state;
    if (s.sortColumn === column) {
        s.sortAsc = !s.sortAsc;
    } else {
        s.sortColumn = column;
        s.sortAsc = true;
    }
    CL.batchBA._renderResultsTable();
};

/** Render the sortable results table */
CL.batchBA._renderResultsTable = function() {
    var filtered = CL.batchBA.getFilteredResults();
    var s = CL.batchBA.state;

    var columns = [
        { key: 'locationName', label: 'Location', title: 'Name of the treated location' },
        { key: 'countermeasureType', label: 'Type', title: 'Type of safety treatment installed' },
        { key: 'beforeTotal', label: 'Before', title: 'Total crashes before treatment' },
        { key: 'afterTotal', label: 'After', title: 'Total crashes after treatment' },
        { key: 'changePct', label: 'Change %', title: 'Percentage change in crashes (negative = fewer crashes)' },
        { key: 'beforeEPDO', label: 'Before EPDO', title: 'Severity-weighted crash score before treatment (higher = more severe crashes)' },
        { key: 'afterEPDO', label: 'After EPDO', title: 'Severity-weighted crash score after treatment' },
        { key: 'epdoChangePct', label: 'EPDO Change %', title: 'Change in severity-weighted crash score' },
        { key: 'cmf', label: 'Safety Score', title: 'Below 1.0 = improvement, above 1.0 = worsening' },
        { key: 'pValue', label: 'Sig.', title: 'Statistical significance — check mark means the result is unlikely due to random chance' },
        { key: '_effectiveness', label: 'Rating', title: 'Overall effectiveness rating based on safety score' }
    ];

    var html = '<div style="overflow-x:auto"><table class="data-table" style="font-size:.8rem;width:100%"><thead><tr>';
    columns.forEach(function(col) {
        var arrow = s.sortColumn === col.key ? (s.sortAsc ? ' ▲' : ' ▼') : '';
        var clickable = col.key !== '_effectiveness' ? ' onclick="CL.batchBA._onSortChange(\'' + col.key + '\')" style="cursor:pointer"' : '';
        html += '<th' + clickable + ' title="' + (col.title || '') + '">' + col.label + arrow + '</th>';
    });
    html += '</tr></thead><tbody>';

    if (filtered.length === 0) {
        html += '<tr><td colspan="' + columns.length + '" style="text-align:center;color:#94a3b8;padding:2rem">No results match filters</td></tr>';
    } else {
        filtered.forEach(function(r, idx) {
            var rating = CL.batchBA.getEffectivenessRating(r.cmf);
            var changeColor = r.changePct < 0 ? '#16a34a' : (r.changePct > 0 ? '#dc2626' : '#64748b');
            var epdoColor = r.epdoChangePct < 0 ? '#16a34a' : (r.epdoChangePct > 0 ? '#dc2626' : '#64748b');

            html += '<tr style="cursor:pointer" onclick="CL.batchBA._toggleRowDetail(this,' + idx + ')">';
            html += '<td style="font-weight:600;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + r.locationName + '">' + r.locationName + '</td>';
            html += '<td>' + (r.countermeasureType || '-') + '</td>';
            html += '<td style="text-align:center">' + r.beforeTotal + '</td>';
            html += '<td style="text-align:center">' + r.afterTotal + '</td>';
            html += '<td style="text-align:center;color:' + changeColor + ';font-weight:600">' + r.changePct.toFixed(1) + '%</td>';
            html += '<td style="text-align:center">' + Math.round(r.beforeEPDO) + '</td>';
            html += '<td style="text-align:center">' + Math.round(r.afterEPDO) + '</td>';
            html += '<td style="text-align:center;color:' + epdoColor + ';font-weight:600">' + r.epdoChangePct.toFixed(1) + '%</td>';
            html += '<td style="text-align:center;font-weight:700;color:' + rating.color + '">' + (r.cmf !== null ? r.cmf.toFixed(3) : 'N/A') + '</td>';
            html += '<td style="text-align:center">' + (r.isSignificant ? '<span style="color:#16a34a;font-weight:700">✓</span>' : '<span style="color:#94a3b8">✗</span>') + '</td>';
            html += '<td><span style="display:inline-block;padding:.15rem .5rem;border-radius:9999px;font-size:.72rem;font-weight:600;background:' + rating.color + '20;color:' + rating.color + '">' + rating.label + '</span></td>';
            html += '</tr>';
        });
    }

    html += '</tbody></table></div>';
    html += '<div style="font-size:.8rem;color:#64748b;margin-top:.5rem">Showing ' + filtered.length + ' of ' + CL.batchBA.state.results.filter(function(r) { return r.status === 'success'; }).length + ' locations</div>';

    document.getElementById('batchBAResultsTable').innerHTML = html;
};

/** Toggle detail row expansion */
CL.batchBA._toggleRowDetail = function(rowEl, filteredIdx) {
    var nextRow = rowEl.nextElementSibling;
    if (nextRow && nextRow.classList.contains('batch-ba-detail-row')) {
        nextRow.remove();
        return;
    }

    // Remove any other open detail rows
    var existing = document.querySelectorAll('.batch-ba-detail-row');
    existing.forEach(function(el) { el.remove(); });

    var filtered = CL.batchBA.getFilteredResults();
    var r = filtered[filteredIdx];
    if (!r) return;

    var detailRow = document.createElement('tr');
    detailRow.className = 'batch-ba-detail-row';
    var td = document.createElement('td');
    td.colSpan = 11;
    td.style.cssText = 'padding:1rem;background:#f8fafc;border-left:3px solid #3b82f6';

    var rating = CL.batchBA.getEffectivenessRating(r.cmf);
    var html = '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem">';

    // Location info
    html += '<div>';
    html += '<div style="font-weight:700;color:#1e40af;margin-bottom:.5rem">Location Details</div>';
    html += '<div style="font-size:.82rem;line-height:1.8">';
    html += '<div>Lat/Lng: ' + r.lat.toFixed(5) + ', ' + r.lng.toFixed(5) + '</div>';
    html += '<div>Radius: ' + r.radiusFt + ' ft</div>';
    html += '<div>Install Date: ' + r.installDate.toLocaleDateString() + '</div>';
    html += '<div>Nearby Crashes: ' + r.nearbyCrashCount + '</div>';
    html += '</div></div>';

    // Before/After comparison
    html += '<div>';
    html += '<div style="font-weight:700;color:#1e40af;margin-bottom:.5rem">Severity Comparison</div>';
    html += '<table style="font-size:.8rem;width:100%"><thead><tr><th></th><th>Before</th><th>After</th></tr></thead><tbody>';
    ['K', 'A', 'B', 'C', 'O'].forEach(function(sev) {
        html += '<tr><td style="font-weight:600">' + sev + '</td><td style="text-align:center">' + (r.beforeStats[sev] || 0) + '</td><td style="text-align:center">' + (r.afterStats[sev] || 0) + '</td></tr>';
    });
    html += '<tr style="font-weight:700;border-top:1px solid #e2e8f0"><td>Total</td><td style="text-align:center">' + r.beforeTotal + '</td><td style="text-align:center">' + r.afterTotal + '</td></tr>';
    html += '</tbody></table></div>';

    // Statistical results
    html += '<div>';
    html += '<div style="font-weight:700;color:#1e40af;margin-bottom:.5rem">Statistical Results</div>';
    html += '<div style="font-size:.82rem;line-height:1.8">';
    html += '<div>Safety Score (CMF): <strong style="color:' + rating.color + '">' + (r.cmf !== null ? r.cmf.toFixed(3) : 'N/A (no before-period crashes)') + '</strong></div>';
    html += '<div>Crash Reduction Factor (CRF): ' + (r.crf !== null ? ((r.crf > 0 ? '+' : '') + r.crf.toFixed(1) + '%') : 'N/A') + '</div>';
    html += '<div>p-value: ' + r.pValue.toFixed(4) + '</div>';
    html += '<div>Before Period: ' + r.beforeStart.toLocaleDateString() + ' — ' + r.beforeEnd.toLocaleDateString() + ' (' + r.beforeYears.toFixed(1) + ' yr)</div>';
    html += '<div>After Period: ' + r.afterStart.toLocaleDateString() + ' — ' + r.afterEnd.toLocaleDateString() + ' (' + r.afterYears.toFixed(1) + ' yr)</div>';
    html += '</div></div>';

    html += '</div>';
    td.innerHTML = html;
    detailRow.appendChild(td);
    rowEl.after(detailRow);
};

CL._registerModule('batch-ba/results');
