/**
 * CrashLens Batch Before/After Evaluation — State Management
 * Manages all state for the batch BA feature.
 */
window.CL = window.CL || {};
CL.batchBA = CL.batchBA || {};

CL.batchBA.state = {
    // Mode toggle
    mode: 'single', // 'single' | 'batch'

    // Upload state
    uploadedFile: null,
    parsedRows: [],
    columnMapping: {
        locationName: null,
        latitude: null,
        longitude: null,
        installDate: null,
        countermeasureType: null,
        studyDuration: null,
        radiusFt: null
    },
    validRows: [],
    invalidRows: [],
    autoDetected: false,

    // Processing config
    globalRadiusFt: 250,
    analysisMethod: 'eb', // 'eb' | 'naive'
    confidenceLevel: 0.95,

    // Processing state
    processing: false,
    progress: { current: 0, total: 0, currentName: '' },

    // Results
    results: [],
    summary: null,

    // Sort/filter state for results table
    sortColumn: 'changePct',
    sortAsc: true,
    filterType: 'all',
    filterEffectiveness: 'all',
    filterSignificance: 'all',
    searchText: ''
};

/**
 * Reset batch state to initial values (preserves mode).
 */
CL.batchBA.resetState = function() {
    var s = CL.batchBA.state;
    s.uploadedFile = null;
    s.parsedRows = [];
    s.columnMapping = {
        locationName: null, latitude: null, longitude: null,
        installDate: null, countermeasureType: null, studyDuration: null, radiusFt: null
    };
    s.validRows = [];
    s.invalidRows = [];
    s.autoDetected = false;
    s.processing = false;
    s.progress = { current: 0, total: 0, currentName: '' };
    s.results = [];
    s.summary = null;
    s.sortColumn = 'changePct';
    s.sortAsc = true;
    s.filterType = 'all';
    s.filterEffectiveness = 'all';
    s.filterSignificance = 'all';
    s.searchText = '';
};

/**
 * Get effectiveness rating based on CMF value.
 * @param {number} cmf
 * @returns {{ label: string, color: string, badgeClass: string }}
 */
CL.batchBA.getEffectivenessRating = function(cmf) {
    if (cmf < 0.70) return { label: 'Highly Effective', color: '#16a34a', badgeClass: 'success' };
    if (cmf < 0.90) return { label: 'Effective', color: '#65a30d', badgeClass: 'success' };
    if (cmf < 1.00) return { label: 'Marginal', color: '#ca8a04', badgeClass: 'warning' };
    if (cmf < 1.10) return { label: 'Ineffective', color: '#ea580c', badgeClass: 'danger' };
    return { label: 'Negative Impact', color: '#dc2626', badgeClass: 'danger' };
};

/**
 * Get filtered results based on current filter/search state.
 * @returns {Array}
 */
CL.batchBA.getFilteredResults = function() {
    var s = CL.batchBA.state;
    var results = s.results.slice();

    // Filter by countermeasure type
    if (s.filterType !== 'all') {
        results = results.filter(function(r) { return r.countermeasureType === s.filterType; });
    }
    // Filter by effectiveness
    if (s.filterEffectiveness !== 'all') {
        results = results.filter(function(r) {
            return CL.batchBA.getEffectivenessRating(r.cmf).label === s.filterEffectiveness;
        });
    }
    // Filter by significance
    if (s.filterSignificance !== 'all') {
        if (s.filterSignificance === 'significant') {
            results = results.filter(function(r) { return r.isSignificant; });
        } else {
            results = results.filter(function(r) { return !r.isSignificant; });
        }
    }
    // Search
    if (s.searchText) {
        var search = s.searchText.toLowerCase();
        results = results.filter(function(r) {
            return r.locationName.toLowerCase().indexOf(search) !== -1;
        });
    }
    // Sort
    results.sort(function(a, b) {
        var valA = a[s.sortColumn], valB = b[s.sortColumn];
        if (typeof valA === 'string') {
            return s.sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
        }
        return s.sortAsc ? (valA - valB) : (valB - valA);
    });
    return results;
};

CL._registerModule('batch-ba/state');
