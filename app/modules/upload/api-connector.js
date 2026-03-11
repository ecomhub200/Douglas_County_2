/**
 * CrashLens API Connector Module
 * Manages external data source connections (Roads, Signals, Speed, BikePed)
 * via ArcGIS REST services.
 *
 * This module handles testing connections, field mapping, data dictionary
 * uploads, and state preset management for the external API data sources.
 *
 * Dependencies: CL.upload
 * Globals accessed: appConfig
 */
window.CL = window.CL || {};
CL.upload = CL.upload || {};
CL.upload.apiConnector = CL.upload.apiConnector || {};

(function() {
    'use strict';

    // API connector state
    var connectorState = {
        expanded: false,
        sources: {
            roads: { connected: false, url: '', fields: null, dictFile: null },
            signals: { connected: false, url: '', fields: null, dictFile: null },
            speed: { connected: false, url: '', fields: null, dictFile: null },
            bikeped: { connected: false, url: '', fields: null, dictFile: null }
        },
        mappingMode: {
            roads: 'auto',
            signals: 'auto',
            speed: 'auto',
            bikeped: 'auto'
        }
    };

    // State presets for known ArcGIS endpoints
    var statePresets = {
        virginia: {
            roads: 'https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/Virginia_Road_Centerline/FeatureServer/0',
            signals: '',
            speed: '',
            bikeped: ''
        },
        colorado: {
            roads: 'https://dtdapps.coloradodot.info/arcgis/rest/services/COGO/COGO_Data/MapServer/10',
            signals: 'https://dtdapps.coloradodot.info/arcgis/rest/services/COGO/COGO_Data/MapServer/13',
            speed: '',
            bikeped: ''
        },
        maryland: {
            roads: 'https://services.arcgis.com/njFNhDsUCentVYJW/arcgis/rest/services/MDOT_SHA_Roadway_Centerlines/FeatureServer/0',
            signals: '',
            speed: '',
            bikeped: ''
        }
    };

    /**
     * Toggle the API connector card expansion.
     */
    function toggle() {
        var body = document.getElementById('apiConnectorBody');
        var chevron = document.getElementById('apiConnectorChevron');
        if (!body) return;

        connectorState.expanded = !connectorState.expanded;
        body.style.display = connectorState.expanded ? 'block' : 'none';
        if (chevron) {
            chevron.style.transform = connectorState.expanded ? 'rotate(180deg)' : 'rotate(0deg)';
        }

        var toggleEl = body.previousElementSibling;
        if (toggleEl) {
            toggleEl.setAttribute('aria-expanded', String(connectorState.expanded));
        }
    }

    /**
     * Test connection to an API data source.
     *
     * @param {string} sourceType - Source type ('roads', 'signals', 'speed', 'bikeped')
     */
    async function testConnection(sourceType) {
        var urlInput = document.getElementById('apiUrl' + capitalize(sourceType));
        var statusEl = document.getElementById('apiStatus' + capitalize(sourceType));
        var btnEl = document.getElementById('apiBtnTest' + capitalize(sourceType));

        if (!urlInput || !urlInput.value.trim()) {
            if (statusEl) statusEl.innerHTML = '<span class="status-dot" style="color:#dc2626">&#x25CF;</span> No URL provided';
            return;
        }

        var url = urlInput.value.trim();
        if (statusEl) statusEl.innerHTML = '<span class="status-dot" style="color:#f59e0b">&#x25CF;</span> Testing...';
        if (btnEl) btnEl.disabled = true;

        try {
            // Query the ArcGIS REST endpoint for metadata
            var queryUrl = url + '?f=json';
            var response = await fetch(queryUrl);
            if (!response.ok) throw new Error('HTTP ' + response.status);

            var data = await response.json();
            if (data.error) throw new Error(data.error.message || 'API error');

            // Success — extract field information
            var fieldCount = data.fields ? data.fields.length : 0;
            var featureCount = data.count || data.maxRecordCount || 'unknown';

            connectorState.sources[sourceType].connected = true;
            connectorState.sources[sourceType].url = url;
            connectorState.sources[sourceType].fields = data.fields || [];

            if (statusEl) {
                statusEl.innerHTML = '<span class="status-dot" style="color:#16a34a">&#x25CF;</span> Connected (' + fieldCount + ' fields)';
                statusEl.className = 'api-source-status connected';
            }

            // Show field mapping section
            var mappingEl = document.getElementById('apiMapping' + capitalize(sourceType));
            if (mappingEl) mappingEl.style.display = 'block';

            // Auto-map fields
            if (connectorState.mappingMode[sourceType] === 'auto') {
                autoMapFields(sourceType, data.fields || []);
            }

            updateConnectedCount();
            console.log('[API] Connected to ' + sourceType + ':', url, '(' + fieldCount + ' fields)');

        } catch (err) {
            connectorState.sources[sourceType].connected = false;
            if (statusEl) {
                statusEl.innerHTML = '<span class="status-dot" style="color:#dc2626">&#x25CF;</span> Failed: ' + err.message;
                statusEl.className = 'api-source-status error';
            }
            console.warn('[API] Connection failed for ' + sourceType + ':', err.message);
        } finally {
            if (btnEl) btnEl.disabled = false;
        }
    }

    /**
     * Clear a data source connection.
     *
     * @param {string} sourceType - Source type to clear
     */
    function clearSource(sourceType) {
        var urlInput = document.getElementById('apiUrl' + capitalize(sourceType));
        var statusEl = document.getElementById('apiStatus' + capitalize(sourceType));
        var mappingEl = document.getElementById('apiMapping' + capitalize(sourceType));

        if (urlInput) urlInput.value = '';
        if (statusEl) {
            statusEl.innerHTML = '<span class="status-dot">&#x25CF;</span> Not connected';
            statusEl.className = 'api-source-status idle';
        }
        if (mappingEl) mappingEl.style.display = 'none';

        connectorState.sources[sourceType].connected = false;
        connectorState.sources[sourceType].url = '';
        connectorState.sources[sourceType].fields = null;

        updateConnectedCount();
    }

    /**
     * Apply a state preset to fill in known API URLs.
     *
     * @param {string} presetKey - State key (e.g., 'virginia', 'colorado')
     */
    function applyPreset(presetKey) {
        if (!presetKey || presetKey === 'custom') return;

        var preset = statePresets[presetKey];
        if (!preset) {
            console.warn('[API] No preset found for:', presetKey);
            return;
        }

        var types = ['roads', 'signals', 'speed', 'bikeped'];
        types.forEach(function(type) {
            var urlInput = document.getElementById('apiUrl' + capitalize(type));
            if (urlInput && preset[type]) {
                urlInput.value = preset[type];
            }
        });

        var infoEl = document.getElementById('apiPresetInfo');
        if (infoEl) {
            infoEl.textContent = 'Applied ' + presetKey + ' preset. Click Test to verify connections.';
        }

        console.log('[API] Applied preset:', presetKey);
    }

    /**
     * Handle data dictionary file upload for a source type.
     *
     * @param {Event} event - File input change event
     * @param {string} sourceType - Source type
     */
    function handleDataDict(event, sourceType) {
        var file = event.target.files && event.target.files[0];
        if (!file) return;

        connectorState.sources[sourceType].dictFile = file;
        var statusEl = document.getElementById('apiDictStatus' + capitalize(sourceType));
        if (statusEl) {
            statusEl.textContent = file.name + ' (' + (file.size / 1024).toFixed(1) + ' KB)';
            statusEl.style.color = '#16a34a';
        }
        console.log('[API] Data dictionary uploaded for ' + sourceType + ':', file.name);
    }

    /**
     * Set field mapping mode (auto or manual) for a source type.
     *
     * @param {string} sourceType - Source type
     * @param {string} mode - 'auto' or 'manual'
     */
    function setMappingMode(sourceType, mode) {
        connectorState.mappingMode[sourceType] = mode;

        var autoBtn = document.getElementById('apiModeAuto' + capitalize(sourceType));
        var manualBtn = document.getElementById('apiModeManual' + capitalize(sourceType));
        if (autoBtn) autoBtn.className = mode === 'auto' ? 'active' : '';
        if (manualBtn) manualBtn.className = mode === 'manual' ? 'active' : '';

        if (mode === 'auto' && connectorState.sources[sourceType].fields) {
            autoMapFields(sourceType, connectorState.sources[sourceType].fields);
        }
    }

    // ============================================================
    // INTERNAL HELPERS
    // ============================================================

    function capitalize(str) {
        if (!str) return '';
        // Handle special cases
        if (str === 'bikeped') return 'BikePed';
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    function updateConnectedCount() {
        var count = 0;
        Object.keys(connectorState.sources).forEach(function(key) {
            if (connectorState.sources[key].connected) count++;
        });
        var badge = document.getElementById('apiConnectedCount');
        if (badge) badge.textContent = count + ' connected';
    }

    /**
     * Auto-map fields from API response to expected field names.
     */
    function autoMapFields(sourceType, fields) {
        var gridEl = document.getElementById('apiMappingGrid' + capitalize(sourceType));
        if (!gridEl || !fields || fields.length === 0) return;

        // Define expected fields per source type
        var expectedFields = {
            roads: ['AADT', 'Lanes', 'Speed Limit', 'Functional Class', 'Road Name', 'Surface Type'],
            signals: ['Signal Type', 'Install Date', 'Control Mode', 'Intersection Name'],
            speed: ['Speed Limit', 'Road Name', 'Direction'],
            bikeped: ['Facility Type', 'Width', 'Surface', 'ADA Compliant']
        };

        var expected = expectedFields[sourceType] || [];
        var html = '';

        expected.forEach(function(fieldName) {
            // Simple fuzzy match
            var bestMatch = findBestFieldMatch(fieldName, fields);
            html += '<div class="api-mapping-row">' +
                '<span class="api-mapping-target">' + fieldName + '</span>' +
                '<span class="api-mapping-arrow">&rarr;</span>' +
                '<select class="api-mapping-select">';

            html += '<option value="">-- Not mapped --</option>';
            fields.forEach(function(f) {
                var fname = f.name || f;
                var selected = (bestMatch && (bestMatch.name || bestMatch) === fname) ? ' selected' : '';
                html += '<option value="' + fname + '"' + selected + '>' + fname + '</option>';
            });

            html += '</select></div>';
        });

        gridEl.innerHTML = html;
    }

    function findBestFieldMatch(target, fields) {
        var targetLower = target.toLowerCase().replace(/[^a-z0-9]/g, '');
        var best = null;
        var bestScore = 0;

        fields.forEach(function(f) {
            var fname = (f.name || f).toLowerCase().replace(/[^a-z0-9]/g, '');
            // Simple substring matching
            if (fname === targetLower) {
                best = f;
                bestScore = 100;
            } else if (fname.indexOf(targetLower) !== -1 && bestScore < 80) {
                best = f;
                bestScore = 80;
            } else if (targetLower.indexOf(fname) !== -1 && bestScore < 60) {
                best = f;
                bestScore = 60;
            }
        });

        return best;
    }

    // ============================================================
    // PUBLIC API
    // ============================================================

    CL.upload.apiConnector = {
        state: connectorState,
        presets: statePresets,
        toggle: toggle,
        testConnection: testConnection,
        clearSource: clearSource,
        applyPreset: applyPreset,
        handleDataDict: handleDataDict,
        setMappingMode: setMappingMode
    };

    CL._registerModule('upload/api-connector');
})();
