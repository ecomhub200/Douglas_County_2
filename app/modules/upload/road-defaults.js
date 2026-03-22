/**
 * CrashLens Road Type Defaults Module
 *
 * Determines the intelligent default road type filter based on the selected
 * state and jurisdiction. Uses national road maintenance responsibility patterns
 * (FHWA data) to decide whether "County Roads Only", "City Roads Only",
 * "All Roads (No Interstate)", or "All Roads" is the best default.
 *
 * Decision cascade:
 *   1. Jurisdiction-level override (maintainsOwnRoads, type === 'city')
 *   2. State exception (consolidated city-county, independent city)
 *   3. State-level pattern from road-maintenance-patterns.json
 *   4. Fallback to 'countyPlusVDOT'
 *
 * User manual overrides are respected: if the user explicitly clicks a
 * different road type, the module won't override it on page reload.
 */
(function () {
    'use strict';

    // ============================================================
    // STATE — loaded patterns and cache
    // ============================================================

    var patterns = null;       // Loaded from config/road-maintenance-patterns.json
    var stateToPattern = {};   // Reverse lookup: state abbreviation → pattern key
    var loaded = false;

    // ============================================================
    // LOAD PATTERNS
    // ============================================================

    /**
     * Load the road maintenance patterns config file.
     * Called once at module init. Non-blocking — if it fails, we fall back gracefully.
     */
    function loadPatterns() {
        var url = '../config/road-maintenance-patterns.json';
        fetch(url)
            .then(function (res) {
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.json();
            })
            .then(function (data) {
                patterns = data;
                loaded = true;
                buildReverseLookup();
                console.log('[RoadDefaults] Loaded road maintenance patterns for',
                    Object.keys(stateToPattern).length, 'states');
            })
            .catch(function (err) {
                console.warn('[RoadDefaults] Could not load road-maintenance-patterns.json:', err.message,
                    '— will use fallback defaults');
            });
    }

    /**
     * Build a reverse lookup from state abbreviation to pattern key.
     * e.g. { "VA": "state_maintained", "CO": "county_maintained", ... }
     */
    function buildReverseLookup() {
        if (!patterns || !patterns.patterns) return;
        stateToPattern = {};
        Object.keys(patterns.patterns).forEach(function (patternKey) {
            var p = patterns.patterns[patternKey];
            if (p.states && Array.isArray(p.states)) {
                p.states.forEach(function (abbr) {
                    stateToPattern[abbr] = patternKey;
                });
            }
        });
    }

    // ============================================================
    // CORE LOGIC
    // ============================================================

    /**
     * Get the state abbreviation for the currently active state.
     * Tries multiple resolution paths for resilience.
     * @returns {string|null} Two-letter abbreviation (e.g. "VA", "CO") or null
     */
    function getActiveStateAbbr() {
        // 1. From jurisdictionContext (most reliable after selection)
        if (typeof jurisdictionContext !== 'undefined' && jurisdictionContext.stateCode) {
            return jurisdictionContext.stateCode;
        }

        // 2. From appConfig.states registry via _getActiveStateKey
        if (typeof _getActiveStateKey === 'function' && typeof appConfig !== 'undefined' && appConfig.states) {
            var stateKey = _getActiveStateKey();
            var stateEntry = appConfig.states[stateKey];
            if (stateEntry && stateEntry.abbreviation) {
                return stateEntry.abbreviation;
            }
        }

        return null;
    }

    /**
     * Get the jurisdiction config for a given jurisdiction ID.
     * Checks state-level config first (more detailed), then global config.json.
     * @param {string} jurisdictionId - e.g. "douglas", "arlington", "alexandria_city"
     * @returns {Object|null} Jurisdiction config object
     */
    function getJurisdictionConfig(jurisdictionId) {
        if (!jurisdictionId) return null;

        // Try state-specific config first (from StateAdapter)
        if (typeof StateAdapter !== 'undefined' && typeof StateAdapter.getFilterProfiles === 'function') {
            // StateAdapter may have jurisdiction info via the active state config
        }

        // Global appConfig.jurisdictions
        if (typeof appConfig !== 'undefined' && appConfig.jurisdictions && appConfig.jurisdictions[jurisdictionId]) {
            return appConfig.jurisdictions[jurisdictionId];
        }

        return null;
    }

    /**
     * Check if a jurisdiction is an exception (consolidated city-county, independent city, etc.)
     * @param {string} stateAbbr - Two-letter state abbreviation
     * @param {string} jurisdictionId - Jurisdiction key
     * @returns {string|null} Override road type, or null if no exception applies
     */
    function checkException(stateAbbr, jurisdictionId) {
        if (!patterns || !patterns.exceptions || !stateAbbr) return null;

        var stateExceptions = patterns.exceptions[stateAbbr];
        if (!stateExceptions) return null;

        // Check maintainsOwnRoads exception list
        if (stateExceptions.maintainsOwnRoads &&
            stateExceptions.maintainsOwnRoads.indexOf(jurisdictionId) !== -1) {
            return 'countyOnly';
        }

        // Check consolidated city-counties
        if (stateExceptions.consolidatedCityCounties &&
            stateExceptions.consolidatedCityCounties.indexOf(jurisdictionId) !== -1) {
            return 'cityOnly';
        }

        // Check independent cities list (for states like MO that list specific ones)
        if (Array.isArray(stateExceptions.independentCities) &&
            stateExceptions.independentCities.indexOf(jurisdictionId) !== -1) {
            return 'cityOnly';
        }

        return null;
    }

    /**
     * Determine the best default road type for a jurisdiction.
     *
     * @param {string} [jurisdictionId] - Jurisdiction key. Auto-detected if omitted.
     * @param {Object} [options] - Options
     * @param {number} [options.minRowsFallback] - If currentRowCount is below this threshold, return 'allRoads'
     * @param {number} [options.currentRowCount] - Current number of loaded rows (requires minRowsFallback)
     * @returns {string} One of: 'countyOnly', 'cityOnly', 'countyPlusVDOT', 'allRoads'
     */
    function getDefaultRoadType(jurisdictionId, options) {
        var opts = options || {};

        // ── Low-data fallback: if loaded row count is below threshold, use allRoads ──
        if (typeof opts.minRowsFallback === 'number' && typeof opts.currentRowCount === 'number') {
            if (opts.currentRowCount < opts.minRowsFallback) {
                console.log('[RoadDefaults] Row count', opts.currentRowCount,
                    'is below threshold', opts.minRowsFallback, '— defaulting to allRoads');
                return 'allRoads';
            }
        }
        // Resolve jurisdiction
        var jId = jurisdictionId;
        if (!jId && typeof getActiveJurisdictionId === 'function') {
            jId = getActiveJurisdictionId();
        }

        var jurisdictionConfig = getJurisdictionConfig(jId);
        var stateAbbr = getActiveStateAbbr();

        // ── Layer 1: Jurisdiction-level override ──
        // If the jurisdiction config explicitly sets maintainsOwnRoads, use it
        if (jurisdictionConfig) {
            // Cities/towns always default to cityOnly
            if (jurisdictionConfig.type === 'city' || jurisdictionConfig.type === 'town') {
                return 'cityOnly';
            }

            // Jurisdiction explicitly maintains own roads → countyOnly
            if (jurisdictionConfig.maintainsOwnRoads === true) {
                return 'countyOnly';
            }

            // Jurisdiction explicitly does NOT maintain own roads → countyPlusVDOT
            if (jurisdictionConfig.maintainsOwnRoads === false) {
                return 'countyPlusVDOT';
            }
        }

        // ── Layer 2: State exception ──
        if (stateAbbr && jId) {
            var exceptionOverride = checkException(stateAbbr, jId);
            if (exceptionOverride) {
                return exceptionOverride;
            }
        }

        // ── Layer 3: State-level pattern ──
        if (stateAbbr && loaded && stateToPattern[stateAbbr]) {
            var patternKey = stateToPattern[stateAbbr];
            var pattern = patterns.patterns[patternKey];
            if (pattern) {
                // Determine if this is a county or city context
                var isCity = jurisdictionConfig && (jurisdictionConfig.type === 'city' || jurisdictionConfig.type === 'town');
                return isCity ? pattern.cityDefault : pattern.countyDefault;
            }
        }

        // ── Layer 4: Fallback ──
        return 'countyPlusVDOT';
    }

    /**
     * Apply the smart default road type to the UI radio buttons.
     * Only applies when the jurisdiction changes — respects user manual overrides on reload.
     *
     * @param {string} [jurisdictionId] - Jurisdiction key. Auto-detected if omitted.
     * @param {Object} [options] - Options
     * @param {boolean} [options.force] - Force apply even if user has manually overridden
     * @param {number} [options.minRowsFallback] - If currentRowCount is below this, switch to 'allRoads'
     * @param {number} [options.currentRowCount] - Current number of loaded rows
     * @returns {string} The road type that was applied
     */
    function applyDefaultRoadType(jurisdictionId, options) {
        var opts = options || {};
        var defaultType = getDefaultRoadType(jurisdictionId, {
            minRowsFallback: opts.minRowsFallback,
            currentRowCount: opts.currentRowCount
        });

        // Map road type values to radio button IDs
        var radioMap = {
            'countyOnly': 'filterCountyOnly',
            'cityOnly': 'filterCityOnly',
            'countyPlusVDOT': 'filterCountyPlusVDOT',
            'allRoads': 'filterAllRoads'
        };

        var radioId = radioMap[defaultType];
        if (!radioId) {
            console.warn('[RoadDefaults] Unknown road type:', defaultType);
            return defaultType;
        }

        var radio = document.getElementById(radioId);
        if (!radio) {
            console.warn('[RoadDefaults] Radio button not found:', radioId);
            return defaultType;
        }

        // Check if user has explicitly saved preferences (don't override their choice on reload)
        if (!opts.force) {
            var userExplicitlySaved = localStorage.getItem('userPreferencesSaved') === 'true';
            var savedFilter = localStorage.getItem('selectedFilterProfile');
            if (userExplicitlySaved && savedFilter) {
                console.log('[RoadDefaults] User has explicit preference:', savedFilter, '— not overriding');
                return savedFilter;
            }
        }

        // Apply the default
        radio.checked = true;
        localStorage.setItem('selectedFilterProfile', defaultType);

        // Log the reasoning
        var stateAbbr = getActiveStateAbbr();
        var patternKey = stateAbbr ? stateToPattern[stateAbbr] : 'unknown';
        var jConfig = getJurisdictionConfig(jurisdictionId);
        var reason = 'fallback';

        if (typeof opts.minRowsFallback === 'number' && typeof opts.currentRowCount === 'number' &&
            opts.currentRowCount < opts.minRowsFallback) {
            reason = 'low data (' + opts.currentRowCount + ' rows < ' + opts.minRowsFallback + ' threshold)';
        } else if (jConfig && (jConfig.type === 'city' || jConfig.type === 'town')) {
            reason = 'jurisdiction type=' + jConfig.type;
        } else if (jConfig && jConfig.maintainsOwnRoads === true) {
            reason = 'jurisdiction maintainsOwnRoads=true';
        } else if (jConfig && jConfig.maintainsOwnRoads === false) {
            reason = 'jurisdiction maintainsOwnRoads=false';
        } else if (stateAbbr && checkException(stateAbbr, jurisdictionId)) {
            reason = 'state exception (' + stateAbbr + ')';
        } else if (patternKey && patternKey !== 'unknown') {
            reason = 'state pattern: ' + patternKey + ' (' + stateAbbr + ')';
        }

        console.log('[RoadDefaults] Applied default:', defaultType,
            'for jurisdiction:', jurisdictionId || '(auto)',
            '| reason:', reason);

        return defaultType;
    }

    /**
     * Check if patterns have been loaded.
     * @returns {boolean}
     */
    function isLoaded() {
        return loaded;
    }

    // ============================================================
    // INIT
    // ============================================================

    // Load patterns immediately on script load
    loadPatterns();

    // ============================================================
    // PUBLIC API — attach to CL.upload.roadDefaults
    // ============================================================

    CL.upload = CL.upload || {};
    CL.upload.roadDefaults = {
        getDefaultRoadType: getDefaultRoadType,
        applyDefaultRoadType: applyDefaultRoadType,
        isLoaded: isLoaded
    };

    CL._registerModule('upload/road-defaults');

})();
