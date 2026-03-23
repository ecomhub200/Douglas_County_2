/**
 * CrashLens Lazy SampleRows Loader
 * Provides ensureSampleRows() for on-demand loading of raw crash row data.
 * Used by tabs that need individual row access (CMF, Warrants, Search, etc.)
 * while keeping initial load fast (aggregates + mapPoints only).
 */
window.CL = window.CL || {};
CL.worker = CL.worker || {};

(function() {
    'use strict';

    var _loadPromise = null;

    /**
     * Ensure crashState.sampleRows is populated.
     * Returns immediately if already loaded. Otherwise triggers background load
     * and returns a Promise that resolves when sampleRows are ready.
     */
    CL.worker.ensureSampleRows = function() {
        // Already loaded — fast path
        if (typeof crashState !== 'undefined' && crashState.sampleRowsLoaded &&
            crashState.sampleRows && crashState.sampleRows.length > 0) {
            return Promise.resolve();
        }

        // Load already in progress — return existing promise
        if (_loadPromise) return _loadPromise;

        // Trigger background load
        _loadPromise = _loadSampleRows().then(function() {
            _loadPromise = null;
        }).catch(function(err) {
            _loadPromise = null;
            console.error('[SampleRowsLoader] Load failed:', err);
            throw err;
        });

        return _loadPromise;
    };

    /**
     * Wait for sampleRows to be available with a timeout.
     * @param {number} timeoutMs - Maximum wait time (default 60s)
     * @returns {Promise<void>}
     */
    CL.worker.waitForSampleRows = function(timeoutMs) {
        timeoutMs = timeoutMs || 60000;

        if (typeof crashState !== 'undefined' && crashState.sampleRowsLoaded &&
            crashState.sampleRows && crashState.sampleRows.length > 0) {
            return Promise.resolve();
        }

        return new Promise(function(resolve, reject) {
            var start = Date.now();
            var check = setInterval(function() {
                if (crashState.sampleRowsLoaded && crashState.sampleRows && crashState.sampleRows.length > 0) {
                    clearInterval(check);
                    resolve();
                } else if (Date.now() - start > timeoutMs) {
                    clearInterval(check);
                    reject(new Error('sampleRows load timeout after ' + timeoutMs + 'ms'));
                }
            }, 100);
        });
    };

    /**
     * Reset the loader state (call when data is cleared/reloaded).
     */
    CL.worker.resetSampleRowsLoader = function() {
        _loadPromise = null;
    };

    /**
     * Internal: Load sampleRows by re-fetching CSV and parsing it.
     * Uses the existing loadSampleRowsInBackground() if available,
     * otherwise falls back to direct fetch + processSampleRowsFromText().
     */
    function _loadSampleRows() {
        console.log('[SampleRowsLoader] Starting lazy sampleRows load...');

        // Use existing background loader if available (it handles R2 fallback, generation checks, etc.)
        if (typeof loadSampleRowsInBackground === 'function') {
            var gen = (typeof _autoLoadGeneration !== 'undefined') ? _autoLoadGeneration : 0;
            return loadSampleRowsInBackground(gen);
        }

        // Fallback: direct fetch
        if (typeof getDataFilePath !== 'function' || typeof resolveDataUrl !== 'function') {
            return Promise.reject(new Error('Data path functions not available'));
        }

        var dataFilePath = getDataFilePath();
        return fetch(resolveDataUrl(dataFilePath))
            .then(function(response) {
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.text();
            })
            .then(function(csvText) {
                if (typeof processSampleRowsFromText === 'function') {
                    return processSampleRowsFromText(csvText);
                }
                throw new Error('processSampleRowsFromText not available');
            });
    }

    CL._registerModule('worker/sample-rows-loader');
})();
