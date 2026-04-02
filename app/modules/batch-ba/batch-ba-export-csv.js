/**
 * CrashLens Batch Before/After Evaluation — CSV Export
 * Exports flat CSV with all computed metrics.
 */
window.CL = window.CL || {};
CL.batchBA = CL.batchBA || {};

/**
 * Export batch results as CSV file.
 */
CL.batchBA.exportCSV = function() {
    var results = CL.batchBA.state.results.filter(function(r) { return r.status === 'success'; });
    if (results.length === 0) {
        alert('No results to export.');
        return;
    }

    var rows = results.map(function(r) {
        var rating = CL.batchBA.getEffectivenessRating(r.cmf);
        return {
            location_name: r.locationName,
            lat: r.lat,
            lng: r.lng,
            countermeasure_type: r.countermeasureType,
            install_date: r.installDate.toISOString().split('T')[0],
            radius_ft: r.radiusFt,
            before_start: r.beforeStart.toISOString().split('T')[0],
            before_end: r.beforeEnd.toISOString().split('T')[0],
            after_start: r.afterStart.toISOString().split('T')[0],
            after_end: r.afterEnd.toISOString().split('T')[0],
            before_years: r.beforeYears.toFixed(2),
            after_years: r.afterYears.toFixed(2),
            before_total: r.beforeTotal,
            after_total: r.afterTotal,
            change_pct: r.changePct.toFixed(2),
            before_K: r.beforeStats.K,
            before_A: r.beforeStats.A,
            before_B: r.beforeStats.B,
            before_C: r.beforeStats.C,
            before_O: r.beforeStats.O,
            before_U: r.beforeStats.U || 0,
            after_K: r.afterStats.K,
            after_A: r.afterStats.A,
            after_B: r.afterStats.B,
            after_C: r.afterStats.C,
            after_O: r.afterStats.O,
            after_U: r.afterStats.U || 0,
            before_epdo: r.beforeEPDO.toFixed(1),
            after_epdo: r.afterEPDO.toFixed(1),
            epdo_change_pct: r.epdoChangePct.toFixed(2),
            cmf: r.cmf !== null ? r.cmf.toFixed(4) : '',
            crf: r.crf !== null ? r.crf.toFixed(2) : '',
            p_value: r.pValue.toFixed(6),
            significant: r.isSignificant ? 'Yes' : 'No',
            effectiveness_rating: rating.label
        };
    });

    var csv = Papa.unparse(rows);
    var blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'Batch_BA_Results_' + new Date().toISOString().split('T')[0] + '.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
};

CL._registerModule('batch-ba/export-csv');
