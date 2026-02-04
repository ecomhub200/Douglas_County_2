/**
 * CRASH LENS - Multi-State Data Adapter
 *
 * Auto-detects which state's crash data is being loaded by analyzing CSV column headers,
 * then normalizes the data to CRASH LENS internal format.
 *
 * USAGE:
 *   1. Include this file in index.html BEFORE the main app logic
 *   2. After CSV headers are parsed, call: StateAdapter.detect(headers)
 *   3. For each row, call: StateAdapter.normalizeRow(rawRow)
 *   4. The normalized row will have Virginia-compatible column names
 *      so existing app logic works WITHOUT changes
 *
 * ADDING A NEW STATE:
 *   1. Create states/{state}/config.json with column mappings
 *   2. Add a detection signature in STATE_SIGNATURES below
 *   3. Add normalization logic in NORMALIZERS below
 */

const StateAdapter = (() => {
    'use strict';

    // ─── State detection signatures ───
    // Each state has unique column names that fingerprint its data source
    const STATE_SIGNATURES = {
        colorado: {
            requiredColumns: ['CUID', 'System Code', 'Injury 00', 'Injury 04'],
            optionalColumns: ['Rd_Number', 'Rd_Section', 'MHE'],
            displayName: 'Colorado (CDOT)',
            configPath: 'states/colorado/config.json'
        },
        virginia: {
            requiredColumns: ['Document Nbr', 'Crash Severity', 'RTE Name', 'SYSTEM'],
            optionalColumns: ['K_People', 'A_People', 'Node', 'Physical Juris Name'],
            displayName: 'Virginia (TREDS)',
            configPath: 'states/virginia/config.json'
        }
        // Add more states here:
        // texas: { requiredColumns: [...], ... }
        // california: { requiredColumns: [...], ... }
    };

    // ─── Current state ───
    let detectedState = null;
    let stateConfig = null;

    // ─── Detection ───
    function detect(csvHeaders) {
        // Normalize headers for comparison (trim whitespace)
        const normalizedHeaders = new Set(csvHeaders.map(h => h.trim()));

        for (const [stateKey, signature] of Object.entries(STATE_SIGNATURES)) {
            const allRequired = signature.requiredColumns.every(col => normalizedHeaders.has(col));
            if (allRequired) {
                detectedState = stateKey;
                console.log(`[StateAdapter] Detected state: ${signature.displayName}`);
                console.log(`[StateAdapter] Matched columns: ${signature.requiredColumns.join(', ')}`);
                return stateKey;
            }
        }

        // Fallback: check partial matches
        let bestMatch = null;
        let bestScore = 0;
        for (const [stateKey, signature] of Object.entries(STATE_SIGNATURES)) {
            const allCols = [...signature.requiredColumns, ...signature.optionalColumns];
            const score = allCols.filter(col => normalizedHeaders.has(col)).length / allCols.length;
            if (score > bestScore) {
                bestScore = score;
                bestMatch = stateKey;
            }
        }

        if (bestScore > 0.5) {
            detectedState = bestMatch;
            console.warn(`[StateAdapter] Partial match (${Math.round(bestScore * 100)}%): ${STATE_SIGNATURES[bestMatch].displayName}`);
            return bestMatch;
        }

        console.warn('[StateAdapter] Could not detect state from CSV headers. Assuming Virginia format.');
        detectedState = 'virginia';
        return 'virginia';
    }

    // ─── Colorado Normalizer ───
    // Transforms a Colorado CDOT row into Virginia-compatible format
    const COLORADO_NORMALIZER = {

        normalizeRow(row) {
            const normalized = {};

            // ── ID ──
            normalized['Document Nbr'] = row['CUID'] || '';

            // ── Date/Time ──
            const rawDate = (row['Crash Date'] || '').trim();
            normalized['Crash Date'] = rawDate;
            normalized['Crash Year'] = this._extractYear(rawDate);
            normalized['Crash Military Time'] = (row['Crash Time'] || '').replace(/:/g, '').substring(0, 4);

            // ── Severity (DERIVED from injury counts) ──
            const injK = parseInt(row['Injury 04']) || 0;
            const injA = parseInt(row['Injury 03']) || 0;
            const injB = parseInt(row['Injury 02']) || 0;
            const injC = parseInt(row['Injury 01']) || 0;
            const injO = parseInt(row['Injury 00']) || 0;

            if (injK > 0) normalized['Crash Severity'] = 'K';
            else if (injA > 0) normalized['Crash Severity'] = 'A';
            else if (injB > 0) normalized['Crash Severity'] = 'B';
            else if (injC > 0) normalized['Crash Severity'] = 'C';
            else normalized['Crash Severity'] = 'O';

            normalized['K_People'] = injK;
            normalized['A_People'] = injA;
            normalized['B_People'] = injB;
            normalized['C_People'] = injC;

            // ── Collision Type (mapped from Crash Type / MHE) ──
            normalized['Collision Type'] = this._mapCollisionType(row['Crash Type'] || row['MHE'] || '');

            // ── Conditions ──
            normalized['Weather Condition'] = row['Weather Condition'] || '';
            normalized['Light Condition'] = row['Lighting Conditions'] || '';
            normalized['Roadway Surface Condition'] = row['Road Condition'] || '';
            normalized['Roadway Alignment'] = this._mapAlignment(row['Road Contour Curves'] || '', row['Road Contour Grade'] || '');

            // ── Road Description / Intersection ──
            normalized['Roadway Description'] = row['Road Description'] || '';
            normalized['Intersection Type'] = this._mapIntersectionType(row['Road Description'] || '');

            // ── Route & Location ──
            normalized['RTE Name'] = this._buildRouteName(row);
            normalized['SYSTEM'] = this._mapRoadSystem(row['System Code'] || '');
            normalized['Node'] = this._buildNodeId(row);
            normalized['RNS MP'] = (row['System Code'] === 'State Highway' || row['System Code'] === 'Interstate Highway')
                ? row['Rd_Section'] || '' : '';

            // ── Coordinates ──
            normalized['x'] = parseFloat(row['Longitude']) || 0;
            normalized['y'] = parseFloat(row['Latitude']) || 0;

            // ── Jurisdiction ──
            normalized['Physical Juris Name'] = row['County'] || '';

            // ── Boolean flags (DERIVED) ──
            normalized['Pedestrian?'] = this._checkNonMotoristType(row, 'Pedestrian') ? 'Y' : 'N';
            normalized['Bike?'] = this._checkNonMotoristType(row, 'Bicycle') ? 'Y' : 'N';
            normalized['Alcohol?'] = this._checkAlcohol(row) ? 'Y' : 'N';
            normalized['Speed?'] = this._checkSpeed(row) ? 'Y' : 'N';
            normalized['Hitrun?'] = (row['TU-1 Hit And Run'] === 'TRUE' || row['TU-2 Hit And Run'] === 'TRUE') ? 'Y' : 'N';
            normalized['Motorcycle?'] = this._checkVehicleType(row, 'Motorcycle') ? 'Y' : 'N';
            normalized['Night?'] = this._isNighttime(row['Lighting Conditions'] || '') ? 'Y' : 'N';
            normalized['Distracted?'] = this._checkDistracted(row) ? 'Y' : 'N';
            normalized['Drowsy?'] = this._checkDrowsy(row) ? 'Y' : 'N';
            normalized['Drug Related?'] = this._checkDrugs(row) ? 'Y' : 'N';
            normalized['Young?'] = this._checkAge(row, 16, 20) ? 'Y' : 'N';
            normalized['Senior?'] = this._checkAge(row, 65, 999) ? 'Y' : 'N';
            normalized['Unrestrained?'] = this._checkUnrestrained(row) ? 'Y' : 'N';
            normalized['School Zone'] = (row['School Zone'] === 'TRUE' || row['School Zone'] === 'True') ? 'Y' : 'N';
            normalized['Work Zone Related'] = (row['Construction Zone'] === 'TRUE' || row['Construction Zone'] === 'True') ? 'Y' : 'N';

            // ── Traffic Control (not directly available in CO data - mark as N/A) ──
            normalized['Traffic Control Type'] = 'N/A';
            normalized['Traffic Control Status'] = 'N/A';

            // ── Functional Class (not in CO data) ──
            normalized['Functional Class'] = '';
            normalized['Area Type'] = '';
            normalized['Facility Type'] = '';
            normalized['Ownership'] = '';

            // ── First Harmful Event ──
            normalized['First Harmful Event'] = row['First HE'] || '';
            normalized['First Harmful Event Loc'] = row['Location'] || '';

            // ── Keep original CO fields for reference ──
            normalized['_co_system_code'] = row['System Code'] || '';
            normalized['_co_rd_number'] = row['Rd_Number'] || '';
            normalized['_co_location1'] = row['Location 1'] || '';
            normalized['_co_location2'] = row['Location 2'] || '';
            normalized['_co_link'] = row['Link'] || '';
            normalized['_co_crash_type'] = row['Crash Type'] || '';
            normalized['_co_mhe'] = row['MHE'] || '';
            normalized['_co_agency'] = row['Agency Id'] || '';
            normalized['_co_city'] = row['City'] || '';
            normalized['_co_tu1_speed_limit'] = row['TU-1 Speed Limit'] || '';
            normalized['_co_tu1_estimated_speed'] = row['TU-1 Estimated Speed'] || '';
            normalized['_co_tu1_driver_action'] = row['TU-1 Driver Action'] || '';
            normalized['_co_tu1_human_factor'] = row['TU-1 Human Contributing Factor'] || '';

            return normalized;
        },

        // ── Helper: Extract year from M/D/YYYY ──
        _extractYear(dateStr) {
            if (!dateStr) return '';
            const parts = dateStr.split('/');
            if (parts.length === 3) return parts[2];
            return '';
        },

        // ── Helper: Map Colorado crash type to standardized collision type ──
        _mapCollisionType(crashType) {
            const ct = (crashType || '').trim();
            const mapping = {
                'Rear-End': 'Rear End',
                'Broadside': 'Angle',
                'Head-On': 'Head On',
                'Sideswipe Same Direction': 'Sideswipe - Same Direction',
                'Sideswipe Opposite Direction': 'Sideswipe - Opposite Direction',
                'Approach Turn': 'Angle',
                'Overtaking Turn': 'Angle',
                'Overturning/Rollover': 'Non-Collision',
                'Pedestrian': 'Pedestrian',
                'Bicycle/Motorized Bicycle': 'Bicyclist',
                'Wild Animal': 'Other Animal',
                'Parked Motor Vehicle': 'Other',
                'Light Pole/Utility Pole': 'Fixed Object - Off Road',
                'Concrete Highway Barrier': 'Fixed Object - Off Road',
                'Guardrail Face': 'Fixed Object - Off Road',
                'Guardrail End': 'Fixed Object - Off Road',
                'Cable Rail': 'Fixed Object - Off Road',
                'Tree': 'Fixed Object - Off Road',
                'Fence': 'Fixed Object - Off Road',
                'Sign': 'Fixed Object - Off Road',
                'Curb': 'Fixed Object - Off Road',
                'Embankment': 'Fixed Object - Off Road',
                'Ditch': 'Fixed Object - Off Road',
                'Large Rocks or Boulder': 'Fixed Object - Off Road',
                'Electrical/Utility Box': 'Fixed Object - Off Road',
                'Vehicle Debris or Cargo': 'Fixed Object in Road',
                'Other Fixed Object (Describe in Narrative)': 'Fixed Object - Off Road',
                'Other Non-Fixed Object Describe in Narrative)': 'Other',
                'Other Non-Collision': 'Non-Collision'
            };
            return mapping[ct] || ct || 'Unknown';
        },

        // ── Helper: Map Road Description to intersection type ──
        _mapIntersectionType(roadDesc) {
            const rd = (roadDesc || '').trim();
            const mapping = {
                'Non-Intersection': 'Non-Intersection',
                'At Intersection': 'Intersection',
                'Intersection Related': 'Intersection',
                'Driveway Access Related': 'Driveway',
                'Ramp': 'Ramp',
                'Ramp-related': 'Ramp',
                'Roundabout': 'Roundabout',
                'Express/Managed/HOV Lane': 'Non-Intersection',
                'Crossover-Related ': 'Intersection',
                'Auxiliary Lane': 'Non-Intersection',
                'Alley Related': 'Intersection',
                'Railroad Crossing Related': 'Railroad Crossing',
                'Mid-Block Crosswalk': 'Intersection'
            };
            return mapping[rd] || rd || 'Unknown';
        },

        // ── Helper: Build route name from Colorado fields ──
        _buildRouteName(row) {
            const system = (row['System Code'] || '').trim();
            const rdNum = (row['Rd_Number'] || '').trim();
            const loc1 = (row['Location 1'] || '').trim();

            if (system === 'Interstate Highway') {
                // Extract interstate number from Rd_Number (e.g., "025A" → "I-25")
                const num = rdNum.replace(/^0+/, '').replace(/[A-Z]$/i, '');
                return `I-${num}`;
            }
            if (system === 'State Highway') {
                // State Highway: use Location 1 name if available, else CO-{number}
                if (loc1) return loc1;
                const num = rdNum.replace(/^0+/, '').replace(/[A-Z]$/i, '');
                return `CO-${num}`;
            }
            if (system === 'Frontage Road') {
                if (loc1) return `${loc1} (Frontage)`;
                return `Frontage Rd ${rdNum}`;
            }
            // City Street or County Road: use Location 1
            return loc1 || `Road ${rdNum}`;
        },

        // ── Helper: Map System Code to Virginia-style SYSTEM values ──
        // This enables the existing filter logic to work
        _mapRoadSystem(systemCode) {
            const sc = (systemCode || '').trim();
            const mapping = {
                'City Street': 'NonVDOT secondary',
                'County Road': 'NonVDOT secondary',
                'State Highway': 'Primary',
                'Interstate Highway': 'Interstate',
                'Frontage Road': 'Secondary'
            };
            return mapping[sc] || sc;
        },

        // ── Helper: Build node ID from intersection data ──
        _buildNodeId(row) {
            const rd = (row['Road Description'] || '').trim();
            const loc1 = (row['Location 1'] || '').trim();
            const loc2 = (row['Location 2'] || '').trim();
            const link = (row['Link'] || '').trim();

            // Only create node for intersection crashes
            if (rd === 'At Intersection' || rd === 'Intersection Related' || rd === 'Roundabout') {
                if (loc1 && loc2) {
                    // Create a stable node ID from the two road names
                    const roads = [loc1, loc2].sort();
                    return `${roads[0]} & ${roads[1]}`;
                }
            }
            return '';
        },

        // ── Helper: Map alignment from curves + grade ──
        _mapAlignment(curves, grade) {
            const parts = [];
            if (curves && curves !== 'Straight') parts.push(curves);
            if (grade && grade !== 'Level') parts.push(grade);
            return parts.length > 0 ? parts.join(', ') : 'Straight/Level';
        },

        // ── Helper: Check non-motorist type ──
        _checkNonMotoristType(row, type) {
            const tu1 = (row['TU-1 NM Type'] || '').trim();
            const tu2 = (row['TU-2 NM Type'] || '').trim();
            return tu1.includes(type) || tu2.includes(type);
        },

        // ── Helper: Check vehicle type ──
        _checkVehicleType(row, type) {
            const tu1 = (row['TU-1 Type'] || '').trim();
            const tu2 = (row['TU-2 Type'] || '').trim();
            return tu1.includes(type) || tu2.includes(type);
        },

        // ── Helper: Check alcohol ──
        _checkAlcohol(row) {
            const positiveValues = ['Yes - SFST', 'Yes - BAC', 'Yes - Both', 'Yes - Observation'];
            const tu1 = (row['TU-1 Alcohol Suspected'] || '').trim();
            const tu2 = (row['TU-2 Alcohol Suspected'] || '').trim();
            return positiveValues.includes(tu1) || positiveValues.includes(tu2);
        },

        // ── Helper: Check speed ──
        _checkSpeed(row) {
            const speedActions = ['Too Fast for Conditions', 'Exceeded Speed Limit', 'Exceeded Safe/Posted Speed'];
            const tu1a = (row['TU-1 Driver Action'] || '').trim();
            const tu2a = (row['TU-2 Driver Action'] || '').trim();
            return speedActions.includes(tu1a) || speedActions.includes(tu2a);
        },

        // ── Helper: Check distracted ──
        _checkDistracted(row) {
            const distractedValues = [
                'Distracted', 'Cell Phone', 'Inattention',
                'Distracted - Cell Phone/Electronic Device',
                'Distracted - Other', 'Inattentive/Distracted'
            ];
            const fields = [
                row['TU-1 Driver Action'], row['TU-2 Driver Action'],
                row['TU-1 Human Contributing Factor'], row['TU-2 Human Contributing Factor']
            ];
            return fields.some(f => {
                const v = (f || '').trim();
                return distractedValues.some(d => v.includes(d));
            });
        },

        // ── Helper: Check drowsy ──
        _checkDrowsy(row) {
            const drowsyValues = ['Asleep/Fatigued', 'Fatigued/Asleep', 'Ill/Asleep/Fatigued'];
            const tu1 = (row['TU-1 Human Contributing Factor'] || '').trim();
            const tu2 = (row['TU-2 Human Contributing Factor'] || '').trim();
            return drowsyValues.some(v => tu1.includes(v) || tu2.includes(v));
        },

        // ── Helper: Check drugs ──
        _checkDrugs(row) {
            const positiveValues = ['Yes - Observation', 'Yes - SFST', 'Yes - Both', 'Yes - Test Results'];
            const fields = [
                row['TU-1  Marijuana Suspected'], row['TU-2 Marijuana Suspected'],
                row['TU-1 Other Drugs Suspected '], row['TU-2 Other Drugs Suspected ']
            ];
            return fields.some(f => positiveValues.includes((f || '').trim()));
        },

        // ── Helper: Check age range ──
        _checkAge(row, minAge, maxAge) {
            const tu1 = parseInt(row['TU-1 Age']) || 0;
            const tu2 = parseInt(row['TU-2 Age']) || 0;
            return (tu1 >= minAge && tu1 <= maxAge) || (tu2 >= minAge && tu2 <= maxAge);
        },

        // ── Helper: Check unrestrained ──
        _checkUnrestrained(row) {
            const unrestrained = ['Not Used', 'Improperly Used'];
            const tu1 = (row['TU-1 Safety restraint Use'] || '').trim();
            const tu2 = (row['TU-2 Safety restraint Use'] || '').trim();
            return unrestrained.includes(tu1) || unrestrained.includes(tu2);
        },

        // ── Helper: Check nighttime ──
        _isNighttime(lighting) {
            const night = ['Dark – Lighted', 'Dark – Unlighted', 'Dark - Lighted', 'Dark - Unlighted'];
            return night.includes((lighting || '').trim());
        }
    };

    // ─── Virginia Normalizer ───
    // Virginia data already matches internal format, just pass through
    const VIRGINIA_NORMALIZER = {
        normalizeRow(row) {
            return row; // Virginia format IS the internal format
        }
    };

    // ─── Normalizer Registry ───
    const NORMALIZERS = {
        colorado: COLORADO_NORMALIZER,
        virginia: VIRGINIA_NORMALIZER
    };

    // ─── Public API ───
    return {
        /**
         * Detect which state's data is in the CSV by examining headers.
         * @param {string[]} headers - Array of CSV column header names
         * @returns {string} State key (e.g., 'colorado', 'virginia')
         */
        detect(headers) {
            return detect(headers);
        },

        /**
         * Normalize a single CSV row from the detected state's format
         * into the CRASH LENS internal format (Virginia-compatible).
         * @param {Object} row - Raw CSV row object (column name → value)
         * @returns {Object} Normalized row with Virginia-compatible column names
         */
        normalizeRow(row) {
            const state = detectedState || 'virginia';
            const normalizer = NORMALIZERS[state];
            if (!normalizer) {
                console.error(`[StateAdapter] No normalizer for state: ${state}`);
                return row;
            }
            return normalizer.normalizeRow(row);
        },

        /**
         * Get the currently detected state.
         * @returns {string|null} State key or null if not detected
         */
        getDetectedState() {
            return detectedState;
        },

        /**
         * Get display name for detected state.
         * @returns {string}
         */
        getStateName() {
            if (!detectedState) return 'Unknown';
            return STATE_SIGNATURES[detectedState]?.displayName || detectedState;
        },

        /**
         * Check if data normalization is needed (i.e., not Virginia).
         * @returns {boolean}
         */
        needsNormalization() {
            return detectedState !== null && detectedState !== 'virginia';
        },

        /**
         * Get the road system filter profiles for the detected state.
         * @returns {Object} Filter profiles
         */
        getFilterProfiles() {
            if (detectedState === 'colorado') {
                return {
                    countyOnly: {
                        name: "County/City Roads Only",
                        systemValues: ["NonVDOT secondary"]  // mapped from City Street + County Road
                    },
                    countyPlusVDOT: {
                        name: "All Roads (No Interstate)",
                        systemValues: ["NonVDOT secondary", "Primary", "Secondary"]  // mapped
                    },
                    allRoads: {
                        name: "All Roads (Including Interstate)",
                        systemValues: ["NonVDOT secondary", "Primary", "Secondary", "Interstate"]  // mapped
                    }
                };
            }
            // Default Virginia profiles
            return null;
        },

        /**
         * Get available state signatures for the setup wizard.
         * @returns {Object} State signatures
         */
        getAvailableStates() {
            return { ...STATE_SIGNATURES };
        },

        /**
         * Manually set the state (skip auto-detection).
         * @param {string} stateKey - State key (e.g., 'colorado')
         */
        setState(stateKey) {
            if (STATE_SIGNATURES[stateKey]) {
                detectedState = stateKey;
                console.log(`[StateAdapter] State manually set to: ${STATE_SIGNATURES[stateKey].displayName}`);
            } else {
                console.error(`[StateAdapter] Unknown state: ${stateKey}`);
            }
        },

        /**
         * Get Colorado-specific road system info for a row.
         * Useful for displaying original classification in UI.
         * @param {Object} normalizedRow - A normalized row
         * @returns {Object} Original road system details
         */
        getOriginalRoadSystem(normalizedRow) {
            if (detectedState !== 'colorado') return null;
            return {
                systemCode: normalizedRow['_co_system_code'] || '',
                rdNumber: normalizedRow['_co_rd_number'] || '',
                location1: normalizedRow['_co_location1'] || '',
                location2: normalizedRow['_co_location2'] || '',
                link: normalizedRow['_co_link'] || '',
                city: normalizedRow['_co_city'] || '',
                agency: normalizedRow['_co_agency'] || ''
            };
        }
    };
})();

// Export for Node.js testing (ignored in browser)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StateAdapter;
}
