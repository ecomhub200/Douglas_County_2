/**
 * CrashLens Batch Before/After Evaluation — Chart.js Visualizations
 * Renders before/after bar chart, CMF distribution, severity shift, scatter plot.
 * All charts include plain-English descriptions for layperson accessibility.
 */
window.CL = window.CL || {};
CL.batchBA = CL.batchBA || {};

// Store chart instances for cleanup
CL.batchBA._charts = {};

/** Set a plain-English description below a chart title */
CL.batchBA._setChartDescription = function(id, text) {
    var el = document.getElementById(id);
    if (el) el.textContent = text;
};

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

    var withCMF = results.filter(function(r) { return r.cmf !== null; });

    CL.batchBA._renderKeyTakeaways(results);
    CL.batchBA._renderBeforeAfterBar(results);
    CL.batchBA._renderCMFDistribution(withCMF);
    CL.batchBA._renderSeverityShift(results);
    CL.batchBA._renderScatterPlot(results);

    // Box plot by type if multiple types
    var types = {};
    withCMF.forEach(function(r) { types[r.countermeasureType] = true; });
    if (Object.keys(types).length > 1) {
        document.getElementById('batchBACMFByTypeContainer').style.display = 'block';
        CL.batchBA._renderCMFByType(withCMF);
    }
};

/** Auto-generated plain-English key takeaways box */
CL.batchBA._renderKeyTakeaways = function(results) {
    var el = document.getElementById('batchBAKeyTakeaways');
    if (!el) return;

    var sum = CL.batchBA.state.summary;
    if (!sum || sum.totalAnalyzed === 0) { el.style.display = 'none'; return; }

    var takeaways = [];

    // Overall effectiveness
    var improved = results.filter(function(r) { return r.changePct < 0; }).length;
    var pctImproved = (improved / results.length * 100).toFixed(0);
    takeaways.push(improved + ' of ' + results.length + ' locations (' + pctImproved + '%) had <strong>fewer crashes</strong> after treatment.');

    // Average reduction
    if (sum.avgCrashReduction > 0) {
        takeaways.push('On average, crashes <strong>decreased by ' + sum.avgCrashReduction.toFixed(1) + '%</strong> across all locations.');
    } else if (sum.avgCrashReduction < 0) {
        takeaways.push('On average, crashes <strong>increased by ' + Math.abs(sum.avgCrashReduction).toFixed(1) + '%</strong> across all locations.');
    }

    // Best performer
    var best = results.slice().sort(function(a, b) { return a.changePct - b.changePct; })[0];
    if (best && best.changePct < 0) {
        takeaways.push('Best result: <strong>' + best.locationName + '</strong> saw a ' + Math.abs(best.changePct).toFixed(1) + '% reduction in crashes.');
    }

    // Crashes prevented
    if (sum.crashesPrevented > 0) {
        takeaways.push('A net estimated <strong>' + sum.crashesPrevented + ' crashes were prevented</strong> across all treated locations.');
    } else if (sum.crashesPrevented < 0) {
        takeaways.push('There was a net <strong>increase of ' + Math.abs(sum.crashesPrevented) + ' crashes</strong> across all treated locations.');
    }

    // Statistical significance
    var sigCount = results.filter(function(r) { return r.isSignificant; }).length;
    if (sigCount > 0) {
        takeaways.push(sigCount + ' location(s) showed <strong>statistically significant</strong> improvement (results unlikely due to random chance).');
    }

    var html = '<div style="background:linear-gradient(135deg,#eff6ff,#f0fdf4);border:1px solid #bfdbfe;border-radius:var(--radius);padding:1rem 1.25rem">';
    html += '<div style="display:flex;gap:.75rem;align-items:flex-start">';
    html += '<span style="font-size:1.3rem;flex-shrink:0">💡</span>';
    html += '<div>';
    html += '<strong style="font-size:.95rem;display:block;margin-bottom:.5rem;color:#1e40af">Key Takeaways</strong>';
    html += '<ul style="margin:0;padding-left:1.2rem;font-size:.85rem;line-height:1.7;color:#334155">';
    takeaways.forEach(function(t) { html += '<li>' + t + '</li>'; });
    html += '</ul></div></div></div>';

    el.innerHTML = html;
    el.style.display = 'block';
};

/** Bar chart: Before vs After crash counts per location — shows ALL locations with scrolling */
CL.batchBA._renderBeforeAfterBar = function(results) {
    var sorted = results.slice().sort(function(a, b) { return a.changePct - b.changePct; });

    var ctx = document.getElementById('batchBABarChart');
    if (!ctx) return;

    // Dynamic height: 28px per location (horizontal), min 320px
    var isHorizontal = sorted.length > 10;
    var chartHeight = isHorizontal ? Math.max(320, sorted.length * 28) : 320;

    // Set inner container height for scrolling
    var innerDiv = ctx.parentElement;
    if (innerDiv) innerDiv.style.height = chartHeight + 'px';

    // Description
    CL.batchBA._setChartDescription('batchBABarChartDesc',
        'Each bar shows crashes before (red) and after (green) the safety treatment. ' +
        'Sorted from most improved at top to least improved. ' +
        'Showing all ' + sorted.length + ' locations' + (sorted.length > 20 ? ' — scroll down to see more.' : '.'));

    CL.batchBA._charts.bar = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sorted.map(function(r) {
                return r.locationName.length > 30 ? r.locationName.substring(0, 30) + '...' : r.locationName;
            }),
            datasets: [
                {
                    label: 'Before',
                    data: sorted.map(function(r) { return r.beforeTotal; }),
                    backgroundColor: 'rgba(220, 38, 38, 0.7)',
                    borderColor: '#dc2626',
                    borderWidth: 1
                },
                {
                    label: 'After',
                    data: sorted.map(function(r) { return r.afterTotal; }),
                    backgroundColor: 'rgba(22, 163, 74, 0.7)',
                    borderColor: '#16a34a',
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: isHorizontal ? 'y' : 'x',
            plugins: {
                title: { display: false },
                legend: { position: 'top' },
                tooltip: {
                    callbacks: {
                        afterBody: function(context) {
                            var idx = context[0].dataIndex;
                            var r = sorted[idx];
                            var change = r.changePct < 0 ? (Math.abs(r.changePct).toFixed(1) + '% fewer crashes') : (r.changePct.toFixed(1) + '% more crashes');
                            return change;
                        }
                    }
                }
            },
            scales: {
                x: { beginAtZero: true },
                y: { beginAtZero: true }
            }
        }
    });
};

/** CMF distribution histogram with layman-friendly tooltips */
CL.batchBA._renderCMFDistribution = function(results) {
    var ctx = document.getElementById('batchBACMFChart');
    if (!ctx) return;

    var bins = [0, 0.3, 0.5, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.5, 2.0, 999];
    var binLabels = ['<0.3', '0.3-0.5', '0.5-0.7', '0.7-0.8', '0.8-0.9', '0.9-1.0', '1.0-1.1', '1.1-1.2', '1.2-1.5', '1.5-2.0', '>2.0'];
    var binDescriptions = ['Very Effective', 'Very Effective', 'Effective', 'Moderately Effective', 'Slightly Effective', 'Borderline', 'Borderline Worse', 'Slightly Worse', 'Moderately Worse', 'Much Worse', 'Much Worse'];
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

    // Description
    CL.batchBA._setChartDescription('batchBACMFChartDesc',
        'This chart shows how many locations fall into each safety score range. ' +
        'Scores below 1.0 (green bars) mean fewer crashes after treatment. ' +
        'Scores above 1.0 (red bars) mean more crashes — the treatment may not have helped.');

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
                title: { display: false },
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            var desc = binDescriptions[context.dataIndex] || '';
                            return context.raw + ' location(s) — ' + desc;
                        }
                    }
                }
            },
            scales: {
                y: { beginAtZero: true, title: { display: true, text: 'Number of Locations' } },
                x: { title: { display: true, text: 'Safety Score (lower = better)' } }
            }
        }
    });
};

/** Stacked bar: severity distribution before vs after with human-readable labels */
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

    // Description
    CL.batchBA._setChartDescription('batchBASeverityChartDesc',
        'Compares how severe crashes were before and after treatment. ' +
        'A shift from red/orange (more severe) toward gray (less severe) means the treatment is reducing the most harmful crashes.');

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
                title: { display: false },
                legend: { position: 'top' },
                tooltip: {
                    callbacks: {
                        afterBody: function(context) {
                            var sev = ['K', 'A', 'B', 'C', 'O'][context[0].datasetIndex];
                            var before = beforeAgg[sev];
                            var after = afterAgg[sev];
                            if (before === 0) return '';
                            var pct = ((after - before) / before * 100).toFixed(1);
                            return (pct < 0 ? pct : '+' + pct) + '% change';
                        }
                    }
                }
            },
            scales: {
                x: { stacked: true },
                y: { stacked: true, beginAtZero: true, title: { display: true, text: 'Crash Count' } }
            }
        }
    });
};

/** Scatter plot: Before vs After with shaded improvement/worsening zones */
CL.batchBA._renderScatterPlot = function(results) {
    var ctx = document.getElementById('batchBAScatterChart');
    if (!ctx) return;

    var maxVal = 0;
    var sorted = results.slice().sort(function(a, b) { return a.changePct - b.changePct; });
    var data = sorted.map(function(r) {
        if (r.beforeTotal > maxVal) maxVal = r.beforeTotal;
        if (r.afterTotal > maxVal) maxVal = r.afterTotal;
        var rating = CL.batchBA.getEffectivenessRating(r.cmf);
        return { x: r.beforeTotal, y: r.afterTotal, label: r.locationName, changePct: r.changePct, color: rating.color || '#94a3b8' };
    });

    var refMax = Math.ceil(maxVal * 1.1) || 10;

    // Plugin: shaded green/red zones
    var zonePlugin = {
        id: 'scatterZones',
        beforeDraw: function(chart) {
            var drawCtx = chart.ctx;
            var xAxis = chart.scales.x;
            var yAxis = chart.scales.y;
            var xMax = xAxis.max;
            var yMax = yAxis.max;

            drawCtx.save();
            // Green zone (below y=x line — improvement)
            drawCtx.beginPath();
            drawCtx.moveTo(xAxis.getPixelForValue(0), yAxis.getPixelForValue(0));
            drawCtx.lineTo(xAxis.getPixelForValue(xMax), yAxis.getPixelForValue(xMax));
            drawCtx.lineTo(xAxis.getPixelForValue(xMax), yAxis.getPixelForValue(0));
            drawCtx.closePath();
            drawCtx.fillStyle = 'rgba(22, 163, 74, 0.06)';
            drawCtx.fill();

            // Red zone (above y=x line — worsening)
            drawCtx.beginPath();
            drawCtx.moveTo(xAxis.getPixelForValue(0), yAxis.getPixelForValue(0));
            drawCtx.lineTo(xAxis.getPixelForValue(xMax), yAxis.getPixelForValue(xMax));
            drawCtx.lineTo(xAxis.getPixelForValue(0), yAxis.getPixelForValue(yMax));
            drawCtx.closePath();
            drawCtx.fillStyle = 'rgba(220, 38, 38, 0.06)';
            drawCtx.fill();

            // Zone labels
            drawCtx.font = '11px sans-serif';
            drawCtx.fillStyle = 'rgba(22, 163, 74, 0.55)';
            drawCtx.fillText('Fewer crashes after', xAxis.getPixelForValue(xMax * 0.55), yAxis.getPixelForValue(xMax * 0.12));
            drawCtx.fillStyle = 'rgba(220, 38, 38, 0.55)';
            drawCtx.fillText('More crashes after', xAxis.getPixelForValue(xMax * 0.08), yAxis.getPixelForValue(yMax * 0.55));
            drawCtx.restore();
        }
    };

    // Description
    CL.batchBA._setChartDescription('batchBAScatterChartDesc',
        'Each dot is one location. Dots in the green zone (below the line) had fewer crashes after treatment. ' +
        'Dots in the red zone (above the line) had more crashes. Hover over a dot to see details.');

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
                    pointRadius: 8,
                    pointHoverRadius: 12
                },
                {
                    label: 'No Change Line',
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
                title: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            var d = context.raw;
                            if (!d.label) return '';
                            var change = d.changePct < 0
                                ? Math.abs(d.changePct).toFixed(1) + '% fewer crashes'
                                : d.changePct.toFixed(1) + '% more crashes';
                            return d.label + ': ' + d.x + ' before, ' + d.y + ' after (' + change + ')';
                        }
                    }
                },
                legend: { display: false }
            },
            scales: {
                x: { beginAtZero: true, title: { display: true, text: 'Crashes Before Treatment' } },
                y: { beginAtZero: true, title: { display: true, text: 'Crashes After Treatment' } }
            }
        },
        plugins: [zonePlugin]
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

    // Description
    CL.batchBA._setChartDescription('batchBACMFByTypeChartDesc',
        'Compares average safety scores by treatment type. Bars below the dashed 1.0 line indicate the treatment was effective on average.');

    CL.batchBA._charts.cmfByType = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: types,
            datasets: [{
                label: 'Avg Safety Score',
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
                title: { display: false },
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            var rating = CL.batchBA.getEffectivenessRating(context.raw);
                            return 'Avg Score: ' + context.raw.toFixed(3) + ' — ' + rating.label;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Average Safety Score' },
                    suggestedMax: 1.5
                }
            }
        }
    });
};

CL._registerModule('batch-ba/charts');
