/**
 * CrashLens Batch Before/After Evaluation — Chart.js Visualizations
 * Renders before/after bar chart, CMF distribution, severity shift, scatter plot.
 */
window.CL = window.CL || {};
CL.batchBA = CL.batchBA || {};

// Store chart instances for cleanup
CL.batchBA._charts = {};

/**
 * Render all batch BA charts.
 */
CL.batchBA.renderCharts = function() {
    var results = CL.batchBA.state.results.filter(function(r) { return r.status === 'success'; });
    if (results.length === 0) return;

    // Destroy existing charts
    Object.keys(CL.batchBA._charts).forEach(function(key) {
        if (CL.batchBA._charts[key]) {
            CL.batchBA._charts[key].destroy();
            CL.batchBA._charts[key] = null;
        }
    });

    document.getElementById('batchBAChartsSection').style.display = 'block';

    CL.batchBA._renderBeforeAfterBar(results);
    CL.batchBA._renderCMFDistribution(results);
    CL.batchBA._renderSeverityShift(results);
    CL.batchBA._renderScatterPlot(results);

    // Box plot by type if multiple types
    var types = {};
    results.forEach(function(r) { types[r.countermeasureType] = true; });
    if (Object.keys(types).length > 1) {
        document.getElementById('batchBACMFByTypeContainer').style.display = 'block';
        CL.batchBA._renderCMFByType(results);
    }
};

/** Bar chart: Before vs After crash counts per location (sorted by reduction) */
CL.batchBA._renderBeforeAfterBar = function(results) {
    var sorted = results.slice().sort(function(a, b) { return a.changePct - b.changePct; });
    var maxItems = Math.min(sorted.length, 30); // Limit to 30 for readability
    var display = sorted.slice(0, maxItems);

    var ctx = document.getElementById('batchBABarChart');
    if (!ctx) return;

    CL.batchBA._charts.bar = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: display.map(function(r) { return r.locationName.length > 20 ? r.locationName.substring(0, 20) + '...' : r.locationName; }),
            datasets: [
                {
                    label: 'Before',
                    data: display.map(function(r) { return r.beforeTotal; }),
                    backgroundColor: 'rgba(220, 38, 38, 0.7)',
                    borderColor: '#dc2626',
                    borderWidth: 1
                },
                {
                    label: 'After',
                    data: display.map(function(r) { return r.afterTotal; }),
                    backgroundColor: 'rgba(22, 163, 74, 0.7)',
                    borderColor: '#16a34a',
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: display.length > 15 ? 'y' : 'x',
            plugins: {
                title: { display: true, text: 'Before vs After Crash Counts (sorted by reduction %)', font: { size: 13 } },
                legend: { position: 'top' }
            },
            scales: {
                x: { beginAtZero: true },
                y: { beginAtZero: true }
            }
        }
    });
};

/** CMF distribution histogram with reference line at 1.0 */
CL.batchBA._renderCMFDistribution = function(results) {
    var ctx = document.getElementById('batchBACMFChart');
    if (!ctx) return;

    // Create histogram bins
    var bins = [0, 0.3, 0.5, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.5, 2.0, 999];
    var binLabels = ['<0.3', '0.3-0.5', '0.5-0.7', '0.7-0.8', '0.8-0.9', '0.9-1.0', '1.0-1.1', '1.1-1.2', '1.2-1.5', '1.5-2.0', '>2.0'];
    var counts = new Array(binLabels.length).fill(0);
    var colors = ['#16a34a', '#16a34a', '#22c55e', '#65a30d', '#84cc16', '#ca8a04', '#ea580c', '#dc2626', '#dc2626', '#dc2626', '#991b1b'];

    results.forEach(function(r) {
        var cmf = Math.min(r.cmf, 999);
        for (var i = 0; i < bins.length - 1; i++) {
            if (cmf >= bins[i] && cmf < bins[i + 1]) {
                counts[i]++;
                break;
            }
        }
    });

    CL.batchBA._charts.cmf = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: binLabels,
            datasets: [{
                label: 'Locations',
                data: counts,
                backgroundColor: colors.map(function(c) { return c + 'cc'; }),
                borderColor: colors,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: { display: true, text: 'CMF Distribution (1.0 = no change)', font: { size: 13 } },
                legend: { display: false },
                annotation: {
                    annotations: {
                        line1: {
                            type: 'line',
                            xMin: 5.5, xMax: 5.5,
                            borderColor: '#1e40af',
                            borderWidth: 2,
                            borderDash: [6, 3],
                            label: { content: 'CMF = 1.0', display: true, position: 'start' }
                        }
                    }
                }
            },
            scales: {
                y: { beginAtZero: true, title: { display: true, text: 'Number of Locations' } },
                x: { title: { display: true, text: 'CMF Range' } }
            }
        }
    });
};

/** Stacked bar: severity distribution before vs after (aggregated) */
CL.batchBA._renderSeverityShift = function(results) {
    var ctx = document.getElementById('batchBASeverityChart');
    if (!ctx) return;

    var beforeAgg = { K: 0, A: 0, B: 0, C: 0, O: 0 };
    var afterAgg = { K: 0, A: 0, B: 0, C: 0, O: 0 };

    results.forEach(function(r) {
        ['K', 'A', 'B', 'C', 'O'].forEach(function(s) {
            beforeAgg[s] += (r.beforeStats[s] || 0);
            afterAgg[s] += (r.afterStats[s] || 0);
        });
    });

    var sevColors = { K: '#dc2626', A: '#ea580c', B: '#f97316', C: '#facc15', O: '#9ca3af' };
    var sevLabels = { K: 'Fatal (K)', A: 'Serious (A)', B: 'Moderate (B)', C: 'Minor (C)', O: 'PDO (O)' };

    CL.batchBA._charts.severity = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Before', 'After'],
            datasets: ['K', 'A', 'B', 'C', 'O'].map(function(s) {
                return {
                    label: sevLabels[s],
                    data: [beforeAgg[s], afterAgg[s]],
                    backgroundColor: sevColors[s] + 'cc',
                    borderColor: sevColors[s],
                    borderWidth: 1
                };
            })
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: { display: true, text: 'Aggregated Severity Distribution: Before vs After', font: { size: 13 } },
                legend: { position: 'top' }
            },
            scales: {
                x: { stacked: true },
                y: { stacked: true, beginAtZero: true, title: { display: true, text: 'Crash Count' } }
            }
        }
    });
};

/** Scatter plot: Before (x) vs After (y) with y=x reference */
CL.batchBA._renderScatterPlot = function(results) {
    var ctx = document.getElementById('batchBAScatterChart');
    if (!ctx) return;

    var maxVal = 0;
    var data = results.map(function(r) {
        if (r.beforeTotal > maxVal) maxVal = r.beforeTotal;
        if (r.afterTotal > maxVal) maxVal = r.afterTotal;
        var rating = CL.batchBA.getEffectivenessRating(r.cmf);
        return { x: r.beforeTotal, y: r.afterTotal, label: r.locationName, color: rating.color };
    });

    // y=x reference line data
    var refMax = Math.ceil(maxVal * 1.1) || 10;

    CL.batchBA._charts.scatter = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [
                {
                    label: 'Locations',
                    data: data,
                    backgroundColor: data.map(function(d) { return d.color + '99'; }),
                    borderColor: data.map(function(d) { return d.color; }),
                    borderWidth: 1,
                    pointRadius: 6,
                    pointHoverRadius: 8
                },
                {
                    label: 'No Change Line (y=x)',
                    data: [{ x: 0, y: 0 }, { x: refMax, y: refMax }],
                    type: 'line',
                    borderColor: '#94a3b8',
                    borderDash: [6, 3],
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: { display: true, text: 'Before vs After Crashes (below line = improvement)', font: { size: 13 } },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            var d = context.raw;
                            return (d.label || '') + ': Before=' + d.x + ', After=' + d.y;
                        }
                    }
                },
                legend: { display: false }
            },
            scales: {
                x: { beginAtZero: true, title: { display: true, text: 'Before Crashes' } },
                y: { beginAtZero: true, title: { display: true, text: 'After Crashes' } }
            }
        }
    });
};

/** Grouped bar: average CMF by countermeasure type */
CL.batchBA._renderCMFByType = function(results) {
    var ctx = document.getElementById('batchBACMFByTypeChart');
    if (!ctx) return;

    var byType = {};
    results.forEach(function(r) {
        var t = r.countermeasureType || 'Not specified';
        if (!byType[t]) byType[t] = [];
        byType[t].push(r.cmf);
    });

    var types = Object.keys(byType).sort();
    var avgCMFs = types.map(function(t) {
        var arr = byType[t];
        return arr.reduce(function(a, b) { return a + b; }, 0) / arr.length;
    });
    var colors = avgCMFs.map(function(cmf) { return CL.batchBA.getEffectivenessRating(cmf).color; });

    CL.batchBA._charts.cmfByType = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: types,
            datasets: [{
                label: 'Average CMF',
                data: avgCMFs,
                backgroundColor: colors.map(function(c) { return c + 'cc'; }),
                borderColor: colors,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: { display: true, text: 'Average CMF by Countermeasure Type', font: { size: 13 } },
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Average CMF' },
                    suggestedMax: 1.5
                }
            }
        }
    });
};

CL._registerModule('batch-ba/charts');
