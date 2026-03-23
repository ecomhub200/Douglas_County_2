/**
 * CrashLens Lazy SampleRows Loader
 * Provides ensureSampleRows() for on-demand loading of raw crash row data.
 * Used by tabs that need individual row access (CMF, Warrants, Search, etc.)
 * while keeping initial load fast (aggregates + mapPoints only).
 *
 * Caches the CSV text from initial fetch to avoid re-downloading (critical for 1M+ row files).
 */
window.CL = window.CL || {};
CL.worker = CL.worker || {};

(function() {
    'use strict';

    var _loadPromise = null;
    var _cachedCsvText = null; // Cached from initial fetch — avoids second network request

    /**
     * Cache CSV text from the initial fetch so lazy sampleRows load doesn't re-download.
     * Call this from autoLoadCrashData right after fetching the CSV.
     * @param {string} csvText - The raw CSV text
     */
    CL.worker.cacheCsvText = function(csvText) {
        _cachedCsvText = csvText;
    };

    /**
     * Release cached CSV text to free memory (call after sampleRows are loaded).
     */
    CL.worker.releaseCsvCache = function() {
        _cachedCsvText = null;
    };

    /**
     * Check if CSV text is cached (useful for debugging).
     * @returns {boolean}
     */
    CL.worker.hasCachedCsv = function() {
        return _cachedCsvText !== null;
    };

    /**
     * Get approximate cached CSV size in MB (for memory monitoring).
     * @returns {number}
     */
    CL.worker.getCachedCsvSizeMB = function() {
        if (!_cachedCsvText) return 0;
        return Math.round(_cachedCsvText.length / (1024 * 1024) * 10) / 10;
    };

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
        _cachedCsvText = null;
    };

    /**
     * Internal: Load sampleRows from cached CSV text or by re-fetching.
     * Prefers cached CSV (no network request) over background loader.
     */
    function _loadSampleRows() {
        console.log('[SampleRowsLoader] Starting lazy sampleRows load...');

        // Preferred path: use cached CSV text (avoids re-download)
        if (_cachedCsvText && typeof processSampleRowsFromText === 'function') {
            console.log('[SampleRowsLoader] Using cached CSV text (' +
                CL.worker.getCachedCsvSizeMB() + 'MB) — no network request');
            var text = _cachedCsvText;
            // Release cache after starting parse to free memory during processing
            return Promise.resolve().then(function() {
                return processSampleRowsFromText(text);
            }).then(function() {
                _cachedCsvText = null;
                console.log('[SampleRowsLoader] sampleRows loaded from cache, CSV cache released');
            });
        }

        // Fallback: use existing background loader if available (it handles R2 fallback, generation checks, etc.)
        if (typeof loadSampleRowsInBackground === 'function') {
            console.log('[SampleRowsLoader] No cached CSV — falling back to network fetch');
            var gen = (typeof _autoLoadGeneration !== 'undefined') ? _autoLoadGeneration : 0;
            return loadSampleRowsInBackground(gen);
        }

        // Last resort: direct fetch
        if (typeof getDataFilePath !== 'function' || typeof resolveDataUrl !== 'function') {
            return Promise.reject(new Error('Data path functions not available'));
        }

        console.log('[SampleRowsLoader] No cached CSV — falling back to direct network fetch');
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
