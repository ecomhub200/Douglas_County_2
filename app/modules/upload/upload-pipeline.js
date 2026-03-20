/**
 * CrashLens Upload Pipeline Module
 * Handles the 5-stage CSV upload pipeline for manual crash data uploads.
 * Stages: 1. Detect & Convert, 2. Validate & Normalize, 3. GPS Check, 4. Load, 5. Save to R2
 *
 * This module manages the manual upload flow when users upload raw state crash
 * data CSV files through the pipeline UI. Supports all R2 folder tiers:
 * county, state, region, MPO, planning district, city, town, and federal.
 *
 * Dependencies: StateAdapter, Papa (PapaParse), CL.upload, HierarchyRegistry
 * Globals accessed: crashState, appConfig
 */
window.CL = window.CL || {};
CL.upload = CL.upload || {};
CL.upload.pipeline = CL.upload.pipeline || {};

(function() {
    'use strict';

    // Pipeline state
    var pipelineState = {
        stage: 0,         // Current stage (0=idle, 1-5=active stages)
        file: null,       // Selected file
        rawData: null,    // Raw CSV text
        parsedData: null, // Parsed rows
        state: null,      // Detected state key
        jurisdiction: null, // Selected jurisdiction
        destTier: 'county', // Destination tier
        destEntityId: null, // Selected entity within tier (region id, mpo id, etc.)
        mergeMode: false,  // Merge with existing data
        progress: 0       // Overall progress percentage
    };

    // ============================================================
    // TIER-AWARE DESTINATION HELPERS
    // ============================================================

    /**
     * Get the R2 state prefix for the selected pipeline state.
     * @returns {string} State prefix like 'colorado', 'virginia'
     */
    function _getR2StatePrefix() {
        var stateSelect = document.getElementById('pipelineStateSelect');
        var stateKey = stateSelect ? stateSelect.value : '';
        if (!stateKey) return '';
        // Use appConfig r2Prefix if available, otherwise use state key directly
        if (typeof appConfig !== 'undefined' && appConfig && appConfig.states && appConfig.states[stateKey]) {
            return appConfig.states[stateKey].r2Prefix || stateKey;
        }
        return stateKey;
    }

    /**
     * Build the R2 destination path based on current tier selection.
     * @returns {string} R2 key like 'colorado/douglas/all_roads.csv'
     */
    function buildR2DestinationPath() {
        var tier = pipelineState.destTier || 'county';
        var statePrefix = _getR2StatePrefix();
        var entitySelect = document.getElementById('pipelineJurisdictionSelect');
        var entityId = entitySelect ? entitySelect.value : '';
        var roadType = 'all_roads'; // Default road type for pipeline uploads

        if (tier === 'federal') {
            return '_national/' + roadType + '.csv';
        }
        if (tier === 'state') {
            return statePrefix + '/_state/statewide_' + roadType + '.csv';
        }
        if (tier === 'region' && entityId) {
            return statePrefix + '/_region/' + entityId + '/' + roadType + '.csv';
        }
        if (tier === 'mpo' && entityId) {
            return statePrefix + '/_mpo/' + entityId + '/' + roadType + '.csv';
        }
        if (tier === 'planning_district' && entityId) {
            return statePrefix + '/_planning_district/' + entityId + '/' + roadType + '.csv';
        }
        if (tier === 'city' && entityId) {
            return statePrefix + '/_city/' + entityId + '/' + roadType + '.csv';
        }
        if (tier === 'town' && entityId) {
            return statePrefix + '/_town/' + entityId + '/' + roadType + '.csv';
        }
        // County tier (default)
        if (entityId) {
            return statePrefix + '/' + entityId.toLowerCase() + '/' + roadType + '.csv';
        }
        return '';
    }

    /**
     * Update the R2 path preview in the UI.
     */
    function updateR2PathPreview() {
        var previewEl = document.getElementById('pipelineR2PathPreview');
        var pathEl = document.getElementById('pipelineR2Path');
        var path = buildR2DestinationPath();
        if (previewEl && pathEl) {
            if (path) {
                pathEl.textContent = path;
                previewEl.style.display = '';
            } else {
                previewEl.style.display = 'none';
            }
        }
    }

    /**
     * Handle destination tier change — repopulate the entity dropdown.
     */
    function handleTierChange() {
        var tierSelect = document.getElementById('pipelineDestTier');
        var tier = tierSelect ? tierSelect.value : 'county';
        pipelineState.destTier = tier;

        var entitySelect = document.getElementById('pipelineJurisdictionSelect');
        var labelEl = document.getElementById('pipelineDestLabel');
        if (!entitySelect) return;

        var tierLabels = {
            county: 'Select County/Jurisdiction',
            state: 'State (no selection needed)',
            region: 'Select Region',
            mpo: 'Select MPO',
            planning_district: 'Select Planning District',
            city: 'Select City',
            town: 'Select Town/Subdivision',
            federal: 'Federal (no selection needed)'
        };
        if (labelEl) labelEl.textContent = tierLabels[tier] || 'Select Destination';

        // State/Federal don't need entity selection
        if (tier === 'state' || tier === 'federal') {
            entitySelect.disabled = true;
            entitySelect.innerHTML = '<option value="">N/A — ' + (tier === 'federal' ? 'national scope' : 'statewide scope') + '</option>';
            updateR2PathPreview();
            return;
        }

        var stateSelect = document.getElementById('pipelineStateSelect');
        var selectedState = stateSelect ? stateSelect.value : '';
        if (!selectedState) {
            entitySelect.disabled = true;
            entitySelect.innerHTML = '<option value="">-- Select state first --</option>';
            updateR2PathPreview();
            return;
        }

        entitySelect.disabled = false;

        if (tier === 'county') {
            // Populate from appConfig jurisdictions (existing behavior)
            _populateCountyDropdown(selectedState);
        } else if (tier === 'region' || tier === 'mpo' || tier === 'planning_district') {
            // Populate from hierarchy.json
            _populateHierarchyDropdown(selectedState, tier);
        } else if (tier === 'city' || tier === 'town') {
            // Populate from geography JSON
            _populateGeoDropdown(selectedState, tier);
        }

        updateR2PathPreview();
    }

    /**
     * Populate county dropdown from appConfig.
     */
    function _populateCountyDropdown(stateKey) {
        var entitySelect = document.getElementById('pipelineJurisdictionSelect');
        entitySelect.innerHTML = '<option value="">-- Select jurisdiction --</option>';

        if (typeof appConfig !== 'undefined' && appConfig && appConfig.jurisdictions) {
            var stateAbbr = appConfig.states && appConfig.states[stateKey] && appConfig.states[stateKey].abbreviation;
            Object.keys(appConfig.jurisdictions).forEach(function(key) {
                var jur = appConfig.jurisdictions[key];
                if (stateAbbr && jur.state === stateAbbr) {
                    var opt = document.createElement('option');
                    opt.value = key;
                    opt.textContent = jur.name;
                    entitySelect.appendChild(opt);
                }
            });
        }
    }

    /**
     * Populate region/MPO/planning district dropdown from hierarchy.json.
     */
    function _populateHierarchyDropdown(stateKey, tier) {
        var entitySelect = document.getElementById('pipelineJurisdictionSelect');
        var placeholderMap = {
            region: '-- Select region --',
            mpo: '-- Select MPO --',
            planning_district: '-- Select planning district --'
        };
        entitySelect.innerHTML = '<option value="">' + (placeholderMap[tier] || '-- Select --') + '</option>';

        // Try to get hierarchy data
        var hierarchy = null;
        if (typeof HierarchyRegistry !== 'undefined') {
            hierarchy = HierarchyRegistry.getCurrent() || HierarchyRegistry.getData();
        }

        if (!hierarchy) {
            entitySelect.innerHTML = '<option value="">Loading hierarchy...</option>';
            // Attempt to load hierarchy for this state
            if (typeof HierarchyRegistry !== 'undefined') {
                var stateDir = stateKey;
                if (typeof FIPSDatabase !== 'undefined') {
                    var stInfo = FIPSDatabase.getState(stateKey);
                    if (stInfo) stateDir = stInfo.name.toLowerCase().replace(/\s+/g, '_');
                }
                HierarchyRegistry.load(stateDir).then(function() {
                    _populateHierarchyDropdown(stateKey, tier);
                }).catch(function(err) {
                    console.warn('[Pipeline] Failed to load hierarchy:', err);
                    entitySelect.innerHTML = '<option value="">No hierarchy data available</option>';
                });
            }
            return;
        }

        var source = {};
        if (tier === 'region') {
            source = hierarchy.regions || {};
        } else if (tier === 'mpo') {
            source = hierarchy.tprs || {};
        } else if (tier === 'planning_district') {
            source = hierarchy.planningDistricts || {};
            if (Object.keys(source).length === 0 && hierarchy.regions) {
                source = hierarchy.regions;
            }
        }

        Object.keys(source).sort().forEach(function(key) {
            if (key.startsWith('_')) return;
            var val = source[key];
            var name = (typeof val === 'object') ? (val.name || val.shortName || key) : key;
            var opt = document.createElement('option');
            opt.value = key;
            opt.textContent = name;
            entitySelect.appendChild(opt);
        });
    }

    /**
     * Populate city/town dropdown from geography JSON on R2.
     */
    function _populateGeoDropdown(stateKey, tier) {
        var entitySelect = document.getElementById('pipelineJurisdictionSelect');
        entitySelect.innerHTML = '<option value="">Loading ' + tier + ' list...</option>';

        // Get state FIPS from FIPSDatabase or stateSelect value
        var stateFips = stateKey;
        if (typeof FIPSDatabase !== 'undefined') {
            // stateKey might be a FIPS code already if coming from stateSelect.value
            var stInfo = FIPSDatabase.getState(stateKey);
            if (stInfo) stateFips = stInfo.fips || stateKey;
        }

        var geoType = tier === 'city' ? 'places' : 'subdivisions';
        if (typeof loadGeoData === 'function') {
            loadGeoData(geoType).then(function(records) {
                var filtered = records.filter(function(r) {
                    return r.STATE === stateFips && r.FUNCSTAT === 'A';
                });
                filtered.sort(function(a, b) {
                    return (a.NAME || '').localeCompare(b.NAME || '');
                });

                entitySelect.innerHTML = '<option value="">-- Select ' + tier + ' --</option>';
                filtered.forEach(function(r) {
                    var slug = (r.NAME || '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
                    var opt = document.createElement('option');
                    opt.value = slug;
                    opt.textContent = r.NAME || r.BASENAME;
                    entitySelect.appendChild(opt);
                });
                console.log('[Pipeline] Populated ' + filtered.length + ' ' + tier + ' entries');
            }).catch(function(err) {
                console.warn('[Pipeline] Failed to load ' + tier + ' list:', err);
                entitySelect.innerHTML = '<option value="">Failed to load ' + tier + ' list</option>';
            });
        } else {
            entitySelect.innerHTML = '<option value="">Geography data not available</option>';
        }
    }

    // ============================================================
    // PIPELINE FILE HANDLERS
    // ============================================================

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
        var selectedState = stateSelect ? stateSelect.value : '';
        pipelineState.state = selectedState;

        // Re-populate entity dropdown for the current tier
        handleTierChange();
    }

    // ============================================================
    // PIPELINE STAGES
    // ============================================================

    /**
     * Start the upload pipeline processing.
     *
     * @param {File} file - The CSV file to process
     */
    function startPipeline(file) {
        var progressContainer = document.getElementById('pipelineProgressContainer');
        if (progressContainer) progressContainer.style.display = 'block';
        // Reset stage 5 if re-running
        updateStage(5, 'pending');
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
        updateProgress(12, 'Detecting state format...');

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
                updateProgress(20, 'Detected: ' + detectedState);

                // Auto-select state in dropdown
                var stateSelect = document.getElementById('pipelineStateSelect');
                if (stateSelect && detectedState) {
                    var stateKey = detectedState.toLowerCase().replace(/\s+/g, '_');
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
            updateProgress(12, 'Detection failed: ' + err.message);
            console.error('[Pipeline] Stage 1 error:', err);
        }
    }

    /**
     * Stage 2: Validate and normalize data.
     */
    function processStage2(csvText) {
        updateStage(2, 'active');
        updateProgress(30, 'Validating and normalizing...');

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
                    updateProgress(45, rows.length.toLocaleString() + ' rows validated');
                    updateStage(2, 'done');
                    processStage3(rows);
                },
                error: function(err) {
                    updateStage(2, 'error');
                    updateProgress(30, 'Parse error: ' + err.message);
                }
            });
        } catch (err) {
            updateStage(2, 'error');
            updateProgress(30, 'Validation failed: ' + err.message);
        }
    }

    /**
     * Stage 3: GPS coordinate check.
     */
    function processStage3(rows) {
        updateStage(3, 'active');
        updateProgress(55, 'Checking GPS coordinates...');

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
        updateProgress(65, gpsRate + '% GPS coverage');
        updateStage(3, 'done');
        processStage4(rows);
    }

    /**
     * Stage 4: Load data into the application.
     */
    function processStage4(rows) {
        updateStage(4, 'active');
        updateProgress(75, 'Loading into application...');

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

            updateProgress(85, rows.length.toLocaleString() + ' records loaded');
            updateStage(4, 'done');

            // Check if we should save to R2
            var saveToR2 = document.getElementById('pipelineSaveToR2');
            if (saveToR2 && saveToR2.checked) {
                processStage5(rows);
            } else {
                // Skip R2 upload — mark complete
                updateStage(5, 'done');
                updateProgress(100, 'Complete! ' + rows.length.toLocaleString() + ' records loaded (R2 upload skipped)');
                pipelineComplete(rows.length);
            }

        } catch (err) {
            updateStage(4, 'error');
            updateProgress(75, 'Load failed: ' + err.message);
            console.error('[Pipeline] Stage 4 error:', err);
        }
    }

    /**
     * Stage 5: Save processed data to R2 cloud storage.
     */
    function processStage5(rows) {
        updateStage(5, 'active');
        updateProgress(90, 'Uploading to R2...');

        var r2Key = buildR2DestinationPath();
        if (!r2Key) {
            updateStage(5, 'error');
            updateProgress(90, 'R2 upload skipped — no destination path configured');
            console.warn('[Pipeline] No R2 destination path — skipping upload');
            pipelineComplete(rows.length);
            return;
        }

        // Convert rows to CSV
        var csvOutput;
        if (typeof Papa !== 'undefined' && Papa.unparse) {
            csvOutput = Papa.unparse(rows);
        } else {
            // Fallback: manual CSV generation
            var headers = Object.keys(rows[0] || {});
            var csvLines = [headers.join(',')];
            rows.forEach(function(row) {
                var vals = headers.map(function(h) {
                    var v = (row[h] !== undefined && row[h] !== null) ? String(row[h]) : '';
                    return v.indexOf(',') !== -1 || v.indexOf('"') !== -1 || v.indexOf('\n') !== -1
                        ? '"' + v.replace(/"/g, '""') + '"' : v;
                });
                csvLines.push(vals.join(','));
            });
            csvOutput = csvLines.join('\n');
        }

        var sizeMB = (csvOutput.length / 1024 / 1024).toFixed(1);
        console.log('[Pipeline] Uploading to R2: ' + r2Key + ' (' + sizeMB + ' MB, ' + rows.length + ' rows)');
        updateProgress(92, 'Uploading ' + sizeMB + ' MB to R2...');

        // POST to server-side R2 upload endpoint
        fetch('/api/r2/upload-geocoded', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ r2Key: r2Key, csvData: csvOutput })
        })
        .then(function(response) {
            if (!response.ok) {
                return response.json().then(function(data) {
                    throw new Error(data.message || data.error || 'Upload failed (' + response.status + ')');
                });
            }
            return response.json();
        })
        .then(function(result) {
            updateStage(5, 'done');
            updateProgress(100, 'Complete! Saved to R2: ' + r2Key);
            console.log('[Pipeline] R2 upload success:', result);
            pipelineComplete(rows.length, r2Key);
        })
        .catch(function(err) {
            updateStage(5, 'error');
            updateProgress(95, 'R2 upload failed: ' + err.message);
            console.error('[Pipeline] Stage 5 error:', err);
            // Still mark as partially complete — data is loaded in app
            pipelineComplete(rows.length, null, err.message);
        });
    }

    /**
     * Finalize pipeline — update status and UI.
     */
    function pipelineComplete(rowCount, r2Key, uploadError) {
        var statusEl = document.getElementById('pipelineStatus');
        if (statusEl) {
            var statusMsg = 'Loaded ' + rowCount.toLocaleString() + ' records';
            if (r2Key) statusMsg += ' | Saved to R2';
            if (uploadError) statusMsg += ' | R2 save failed';
            statusEl.innerHTML = '<span class="status-dot" style="color:' + (uploadError ? '#f59e0b' : '#16a34a') + '">&#x25CF;</span> ' + statusMsg;
        }

        // Switch to dashboard
        setTimeout(function() {
            if (typeof showUploadSummary === 'function') showUploadSummary();
            if (typeof initDropdowns === 'function') initDropdowns();
            if (typeof showTab === 'function') showTab('dashboard');
        }, 500);
    }

    // ============================================================
    // UI HELPERS
    // ============================================================

    /**
     * Update pipeline stage visual indicator.
     */
    function updateStage(stageNum, status) {
        var stageIds = ['pipelineStageConvert', 'pipelineStageValidate', 'pipelineStageGeocode', 'pipelineStageSplit', 'pipelineStageUpload'];
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
    // INITIALIZATION
    // ============================================================

    /**
     * Populate pipelineStateSelect dropdown from appConfig.states.
     * Called on DOMContentLoaded so the dropdown is ready before user interaction.
     */
    function _initStateDropdown() {
        var stateSelect = document.getElementById('pipelineStateSelect');
        if (!stateSelect) return;
        if (typeof appConfig === 'undefined' || !appConfig || !appConfig.states) return;

        Object.keys(appConfig.states).sort().forEach(function(key) {
            if (key.startsWith('_')) return; // skip _comment etc.
            var st = appConfig.states[key];
            var label = st.name || key.replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); });
            var opt = document.createElement('option');
            opt.value = key;
            opt.textContent = label;
            stateSelect.appendChild(opt);
        });
        console.log('[Pipeline] State dropdown populated with', stateSelect.options.length - 1, 'states');
    }

    // Run init when DOM is ready (or immediately if already loaded)
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _initStateDropdown);
    } else {
        _initStateDropdown();
    }

    // ============================================================
    // PUBLIC API
    // ============================================================

    CL.upload.pipeline = {
        state: pipelineState,
        init: _initStateDropdown,
        handleFileSelect: handleFileSelect,
        handleFileDrop: handleFileDrop,
        handleStateChange: handleStateChange,
        handleTierChange: handleTierChange,
        updateR2PathPreview: updateR2PathPreview,
        buildR2DestinationPath: buildR2DestinationPath,
        startPipeline: startPipeline
    };

    CL._registerModule('upload/upload-pipeline');
})();
