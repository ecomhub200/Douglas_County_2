/**
 * CrashLens Upload Pipeline Module
 * Handles the 4-stage CSV upload pipeline for manual crash data uploads.
 * Stages: 1. Detect & Convert, 2. Validate & Normalize, 3. GPS Check, 4. Load
 *
 * This module manages the manual upload flow when users upload raw state crash
 * data CSV files through the pipeline UI.
 *
 * Dependencies: StateAdapter, Papa (PapaParse), CL.upload
 * Globals accessed: crashState, appConfig
 */
window.CL = window.CL || {};
CL.upload = CL.upload || {};
CL.upload.pipeline = CL.upload.pipeline || {};

(function() {
    'use strict';

    // Pipeline state
    var pipelineState = {
        stage: 0,         // Current stage (0=idle, 1-4=active stages)
        file: null,       // Selected file
        rawData: null,    // Raw CSV text
        parsedData: null, // Parsed rows
        state: null,      // Detected state key
        jurisdiction: null, // Selected jurisdiction
        mergeMode: false,  // Merge with existing data
        progress: 0       // Overall progress percentage
    };

    /**
     * Handle file selection from the pipeline upload zone.
     *
     * @param {Event} event - File input change event
     */
    function handleFileSelect(event) {
        var file = event.target.files && event.target.files[0];
        if (!file) return;
        pipelineState.file = file;
        console.log('[Pipeline] File selected:', file.name, '(' + (file.size / 1024 / 1024).toFixed(2) + ' MB)');
        startPipeline(file);
    }

    /**
     * Handle file drop on the pipeline upload zone.
     *
     * @param {Event} event - Drop event
     */
    function handleFileDrop(event) {
        event.preventDefault();
        event.stopPropagation();
        var zone = document.getElementById('pipelineUploadZone');
        if (zone) {
            zone.style.borderColor = '#93c5fd';
            zone.style.background = '#f0f9ff';
        }
        var file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
        if (!file) return;
        pipelineState.file = file;
        console.log('[Pipeline] File dropped:', file.name);
        startPipeline(file);
    }

    /**
     * Handle state selection change in the pipeline.
     */
    function handleStateChange() {
        var stateSelect = document.getElementById('pipelineStateSelect');
        var jurisdictionSelect = document.getElementById('pipelineJurisdictionSelect');
        if (!stateSelect || !jurisdictionSelect) return;

        var selectedState = stateSelect.value;
        pipelineState.state = selectedState;

        if (!selectedState) {
            jurisdictionSelect.disabled = true;
            jurisdictionSelect.innerHTML = '<option value="">-- Select state first --</option>';
            return;
        }

        // Populate jurisdictions for the selected state
        jurisdictionSelect.disabled = false;
        jurisdictionSelect.innerHTML = '<option value="">-- Select jurisdiction --</option>';

        if (typeof appConfig !== 'undefined' && appConfig && appConfig.jurisdictions) {
            var stateAbbr = appConfig.states && appConfig.states[selectedState] && appConfig.states[selectedState].abbreviation;
            Object.keys(appConfig.jurisdictions).forEach(function(key) {
                var jur = appConfig.jurisdictions[key];
                if (stateAbbr && jur.state === stateAbbr) {
                    var opt = document.createElement('option');
                    opt.value = key;
                    opt.textContent = jur.name;
                    jurisdictionSelect.appendChild(opt);
                }
            });
        }
    }

    /**
     * Start the upload pipeline processing.
     *
     * @param {File} file - The CSV file to process
     */
    function startPipeline(file) {
        var progressContainer = document.getElementById('pipelineProgressContainer');
        if (progressContainer) progressContainer.style.display = 'block';
        updateStage(1, 'active');
        updateProgress(5, 'Reading file...');

        var reader = new FileReader();
        reader.onload = function(e) {
            pipelineState.rawData = e.target.result;
            processStage1(e.target.result);
        };
        reader.onerror = function() {
            updateStage(1, 'error');
            updateProgress(0, 'Error reading file');
        };
        reader.readAsText(file);
    }

    /**
     * Stage 1: Detect state format and convert headers.
     */
    function processStage1(csvText) {
        updateProgress(15, 'Detecting state format...');

        try {
            // Parse first few rows to detect headers
            var preview = Papa.parse(csvText, { header: true, preview: 5 });
            if (!preview.meta || !preview.meta.fields) {
                throw new Error('Could not parse CSV headers');
            }

            // Auto-detect state via StateAdapter
            if (typeof StateAdapter !== 'undefined') {
                StateAdapter.detect(preview.meta.fields);
                var detectedState = StateAdapter.getStateName();
                console.log('[Pipeline] State detected:', detectedState);
                updateProgress(25, 'Detected: ' + detectedState);

                // Auto-select state in dropdown
                var stateSelect = document.getElementById('pipelineStateSelect');
                if (stateSelect && detectedState) {
                    var stateKey = detectedState.toLowerCase().replace(/\s+/g, '');
                    if (stateSelect.querySelector('option[value="' + stateKey + '"]')) {
                        stateSelect.value = stateKey;
                        handleStateChange();
                    }
                }
            }

            updateStage(1, 'done');
            processStage2(csvText);
        } catch (err) {
            updateStage(1, 'error');
            updateProgress(15, 'Detection failed: ' + err.message);
            console.error('[Pipeline] Stage 1 error:', err);
        }
    }

    /**
     * Stage 2: Validate and normalize data.
     */
    function processStage2(csvText) {
        updateStage(2, 'active');
        updateProgress(35, 'Validating and normalizing...');

        try {
            var rows = [];
            var errors = [];

            Papa.parse(csvText, {
                header: true,
                skipEmptyLines: true,
                chunk: function(results) {
                    results.data.forEach(function(row) {
                        try {
                            var normalized = (typeof StateAdapter !== 'undefined' && StateAdapter.needsNormalization())
                                ? StateAdapter.normalizeRow(row) : row;
                            rows.push(normalized);
                        } catch (e) {
                            errors.push(e.message);
                        }
                    });
                },
                complete: function() {
                    pipelineState.parsedData = rows;
                    console.log('[Pipeline] Normalized ' + rows.length + ' rows (' + errors.length + ' errors)');
                    updateProgress(55, rows.length.toLocaleString() + ' rows validated');
                    updateStage(2, 'done');
                    processStage3(rows);
                },
                error: function(err) {
                    updateStage(2, 'error');
                    updateProgress(35, 'Parse error: ' + err.message);
                }
            });
        } catch (err) {
            updateStage(2, 'error');
            updateProgress(35, 'Validation failed: ' + err.message);
        }
    }

    /**
     * Stage 3: GPS coordinate check.
     */
    function processStage3(rows) {
        updateStage(3, 'active');
        updateProgress(65, 'Checking GPS coordinates...');

        var COL = (typeof CL !== 'undefined' && CL.core && CL.core.constants) ? CL.core.constants.COL : null;
        var withGPS = 0, withoutGPS = 0;

        if (COL) {
            rows.forEach(function(row) {
                var lat = parseFloat(row[COL.Y]);
                var lon = parseFloat(row[COL.X]);
                if (lat && lon && !isNaN(lat) && !isNaN(lon) && lat !== 0 && lon !== 0) {
                    withGPS++;
                } else {
                    withoutGPS++;
                }
            });
        }

        var gpsRate = rows.length > 0 ? ((withGPS / rows.length) * 100).toFixed(1) : '0.0';
        console.log('[Pipeline] GPS coverage: ' + gpsRate + '% (' + withGPS + '/' + rows.length + ')');
        updateProgress(80, gpsRate + '% GPS coverage');
        updateStage(3, 'done');
        processStage4(rows);
    }

    /**
     * Stage 4: Load data into the application.
     */
    function processStage4(rows) {
        updateStage(4, 'active');
        updateProgress(90, 'Loading into application...');

        try {
            // Feed rows into the main processRow function
            if (typeof resetState === 'function') resetState();

            rows.forEach(function(row) {
                if (typeof processRow === 'function') processRow(row);
            });

            if (typeof crashState !== 'undefined') {
                crashState.totalRows = rows.length;
                crashState.loaded = true;
            }

            if (typeof finalizeData === 'function') finalizeData();

            updateProgress(100, 'Complete! ' + rows.length.toLocaleString() + ' records loaded');
            updateStage(4, 'done');

            var statusEl = document.getElementById('pipelineStatus');
            if (statusEl) {
                statusEl.innerHTML = '<span class="status-dot" style="color:#16a34a">&#x25CF;</span> Loaded ' + rows.length.toLocaleString() + ' records';
            }

            // Switch to dashboard
            setTimeout(function() {
                if (typeof showUploadSummary === 'function') showUploadSummary();
                if (typeof initDropdowns === 'function') initDropdowns();
                if (typeof showTab === 'function') showTab('dashboard');
            }, 500);

        } catch (err) {
            updateStage(4, 'error');
            updateProgress(90, 'Load failed: ' + err.message);
            console.error('[Pipeline] Stage 4 error:', err);
        }
    }

    /**
     * Update pipeline stage visual indicator.
     */
    function updateStage(stageNum, status) {
        var stageIds = ['pipelineStageConvert', 'pipelineStageValidate', 'pipelineStageGeocode', 'pipelineStageSplit'];
        var el = document.getElementById(stageIds[stageNum - 1]);
        if (!el) return;

        var colors = {
            'active':  { bg: '#dbeafe', color: '#1e40af', border: '1px solid #93c5fd' },
            'done':    { bg: '#dcfce7', color: '#15803d', border: '1px solid #86efac' },
            'error':   { bg: '#fef2f2', color: '#dc2626', border: '1px solid #fecaca' },
            'pending': { bg: '#e2e8f0', color: '#64748b', border: 'none' }
        };
        var style = colors[status] || colors.pending;
        el.style.background = style.bg;
        el.style.color = style.color;
        el.style.border = style.border;
    }

    /**
     * Update pipeline progress bar and message.
     */
    function updateProgress(pct, msg) {
        pipelineState.progress = pct;
        var bar = document.getElementById('pipelineProgressBar');
        var pctEl = document.getElementById('pipelineProgressPct');
        var msgEl = document.getElementById('pipelineProgressMsg');
        if (bar) bar.style.width = pct + '%';
        if (pctEl) pctEl.textContent = pct + '%';
        if (msgEl) msgEl.textContent = msg || '';
    }

    // ============================================================
    // PUBLIC API
    // ============================================================

    CL.upload.pipeline = {
        state: pipelineState,
        handleFileSelect: handleFileSelect,
        handleFileDrop: handleFileDrop,
        handleStateChange: handleStateChange,
        startPipeline: startPipeline
    };

    CL._registerModule('upload/upload-pipeline');
})();
