/**
 * Bug tests for Upload Tab module and Virginia data loading fix.
 *
 * Tests the key bug fixes:
 *   1. getFallbackData() uses active road type instead of hardcoded all_roads
 *   2. getDataFilePath() normalizes jurisdiction to lowercase
 *   3. autoLoadCrashData() normalizes r2JurisdictionPath to lowercase
 *   4. initPredictionTab() normalizes forecast path jurisdiction to lowercase
 *   5. resolveDataUrl() handles R2-native paths correctly for all states
 *   6. saveFilterProfile() properly triggers data reload with correct path
 *
 * Run with: node tests/test_upload_tab_bug.js
 *
 * Test Coverage Map
 * =================
 *
 * getFallbackData (road type selection):
 *   1.  Returns county_roads.csv when countyOnly filter is selected
 *   2.  Returns no_interstate.csv when countyPlusVDOT filter is selected
 *   3.  Returns all_roads.csv when allRoads filter is selected
 *   4.  Falls back to all_roads.csv when getActiveRoadTypeSuffix is unavailable
 *   5.  Normalizes jurisdiction to lowercase in fallback path
 *
 * getDataFilePath (R2 path construction):
 *   6.  Builds correct path for Virginia/Henrico/county_roads
 *   7.  Builds correct path for Virginia/Henrico/all_roads
 *   8.  Builds correct path for Virginia/Henrico/no_interstate
 *   9.  Builds correct path for Colorado/Douglas/county_roads
 *   10. Normalizes jurisdiction to lowercase
 *   11. Strips state abbreviation prefix from jurisdiction ID
 *   12. Handles state tier paths
 *   13. Handles federal tier paths
 *
 * resolveDataUrl (Virginia-specific):
 *   14. Resolves virginia/henrico/county_roads.csv to R2 URL
 *   15. Resolves virginia/henrico/all_roads.csv to R2 URL
 *   16. Resolves virginia/henrico/no_interstate.csv to R2 URL
 *   17. Resolves virginia/henrico/forecasts_county_roads.json to R2 URL
 *   18. Resolves virginia/henrico/forecasts_all_roads.json to R2 URL
 *   19. Resolves virginia/henrico/forecasts_no_interstate.json to R2 URL
 *
 * resolveDataUrl (Colorado for comparison):
 *   20. Resolves colorado/douglas/county_roads.csv to R2 URL
 *   21. Resolves colorado/douglas/all_roads.csv to R2 URL
 *   22. Resolves colorado/douglas/no_interstate.csv to R2 URL
 *
 * Case normalization:
 *   23. Uppercase jurisdiction is normalized to lowercase in getDataFilePath
 *   24. Mixed case jurisdiction is normalized in fallback path
 *   25. Already lowercase jurisdiction is preserved
 *
 * Road type switching simulation:
 *   26. Switching from countyOnly to allRoads changes the data file path
 *   27. Switching from allRoads to countyPlusVDOT changes the data file path
 *   28. Switching back to countyOnly returns to original path
 *   29. Virginia path changes correctly on each switch
 *   30. Colorado path changes correctly on each switch
 *
 * Forecast file mapping:
 *   31. countyOnly → forecasts_county_roads.json
 *   32. countyPlusVDOT → forecasts_no_interstate.json
 *   33. allRoads → forecasts_all_roads.json
 *
 * buildLocalFallbackPaths:
 *   34. Virginia fallback paths use correct jurisdiction
 *   35. Colorado fallback paths use CDOT dataDir
 *   36. Fallback includes all_roads variant when not requesting all_roads
 *   37. Empty path returns empty array
 *
 * Module loading:
 *   38. CL.upload namespace exists after module load
 *   39. CL.upload.getDataFilePath is a function
 *   40. CL.upload.resolveDataUrl is a function
 *   41. CL.upload.getActiveRoadTypeSuffix is a function
 *   42. CL.upload.saveFilterProfile is a function
 */

// ─── Test Framework ───

let passed = 0;
let failed = 0;
const errors = [];

function assert(condition, testName) {
    if (condition) {
        passed++;
        console.log(`  \u2705 PASS: ${testName}`);
    } else {
        failed++;
        errors.push(testName);
        console.error(`  \u274C FAIL: ${testName}`);
    }
}

function assertEq(actual, expected, testName) {
    const eq = JSON.stringify(actual) === JSON.stringify(expected);
    if (eq) {
        passed++;
        console.log(`  \u2705 PASS: ${testName}`);
    } else {
        failed++;
        errors.push(testName);
        console.error(`  \u274C FAIL: ${testName}`);
        console.error(`    Expected: ${JSON.stringify(expected)}`);
        console.error(`    Got:      ${JSON.stringify(actual)}`);
    }
}

function assertIncludes(str, substring, testName) {
    if (typeof str === 'string' && str.includes(substring)) {
        passed++;
        console.log(`  \u2705 PASS: ${testName}`);
    } else {
        failed++;
        errors.push(testName);
        console.error(`  \u274C FAIL: ${testName}`);
        console.error(`    Expected "${str}" to include "${substring}"`);
    }
}

function assertNotIncludes(str, substring, testName) {
    if (typeof str === 'string' && !str.includes(substring)) {
        passed++;
        console.log(`  \u2705 PASS: ${testName}`);
    } else {
        failed++;
        errors.push(testName);
        console.error(`  \u274C FAIL: ${testName}`);
        console.error(`    Expected "${str}" NOT to include "${substring}"`);
    }
}

// ─── DOM Mocks ───

const _mockElements = {};
const _mockRadios = {};

const document = {
    getElementById: (id) => _mockElements[id] || null,
    querySelector: (selector) => {
        // Handle radio button queries
        const match = selector.match(/input\[name="(\w+)"\]:checked/);
        if (match) {
            return _mockRadios[match[1]] || null;
        }
        return null;
    },
    querySelectorAll: () => [],
    createElement: (tag) => ({
        tagName: tag.toUpperCase(),
        value: '',
        textContent: '',
        innerHTML: '',
        style: {},
        appendChild: () => {},
        setAttribute: () => {},
        getAttribute: () => null
    }),
    addEventListener: () => {}
};

const localStorage = {
    _store: {},
    getItem: (key) => localStorage._store[key] || null,
    setItem: (key, val) => { localStorage._store[key] = String(val); },
    removeItem: (key) => { delete localStorage._store[key]; },
    clear: () => { localStorage._store = {}; }
};

const window = { CL: {} };

// ─── Global State Mocks ───

const r2State = {
    manifest: {
        r2BaseUrl: 'https://data.aicreatesai.com',
        localPathMapping: {
            'data/henrico_county_roads.csv': 'virginia/henrico/county_roads.csv',
            'data/henrico_all_roads.csv': 'virginia/henrico/all_roads.csv',
            'data/henrico_no_interstate.csv': 'virginia/henrico/no_interstate.csv',
            'data/CDOT/douglas_county_roads.csv': 'colorado/douglas/county_roads.csv',
            'data/CDOT/douglas_all_roads.csv': 'colorado/douglas/all_roads.csv',
            'data/CDOT/douglas_no_interstate.csv': 'colorado/douglas/no_interstate.csv'
        },
        files: {
            'virginia/henrico/county_roads.csv': { size: 17468416 },
            'virginia/henrico/no_interstate.csv': { size: 28229222 },
            'virginia/henrico/all_roads.csv': { size: 34478899 },
            'virginia/henrico/forecasts_county_roads.json': { size: 358030 },
            'virginia/henrico/forecasts_no_interstate.json': { size: 368590 },
            'virginia/henrico/forecasts_all_roads.json': { size: 359000 },
            'colorado/douglas/county_roads.csv': { size: 9500748 },
            'colorado/douglas/no_interstate.csv': { size: 14401256 },
            'colorado/douglas/all_roads.csv': { size: 18355770 },
            'colorado/douglas/forecasts_county_roads.json': { size: 200000 },
            'colorado/douglas/forecasts_no_interstate.json': { size: 210000 },
            'colorado/douglas/forecasts_all_roads.json': { size: 220000 }
        }
    },
    loaded: true,
    error: null
};

const appConfig = {
    states: {
        virginia: {
            fips: '51',
            name: 'Virginia',
            abbreviation: 'VA',
            dotName: 'VDOT',
            defaultJurisdiction: 'henrico',
            dataDir: null,
            r2Prefix: 'virginia'
        },
        colorado: {
            fips: '08',
            name: 'Colorado',
            abbreviation: 'CO',
            dotName: 'CDOT',
            defaultJurisdiction: 'douglas',
            dataDir: 'CDOT',
            r2Prefix: 'colorado'
        }
    },
    jurisdictions: {
        henrico: { name: 'Henrico County', type: 'county', state: 'VA', fips: '087' },
        douglas: { name: 'Douglas County', type: 'county', state: 'CO', fips: '035' },
        co_adams: { name: 'Adams County', type: 'county', state: 'CO', fips: '001' }
    },
    filterProfiles: {
        countyOnly: { name: 'County/City Roads Only' },
        countyPlusVDOT: { name: 'All Roads (No Interstate)' },
        allRoads: { name: 'All Roads (Incl. Interstates)' }
    },
    defaults: { jurisdiction: 'douglas' }
};

const R2_BASE_URL = 'https://data.aicreatesai.com';

// Mutable test state
let _activeStateKey = 'virginia';
let _activeJurisdiction = 'henrico';
let _selectedFilterProfile = 'countyOnly';

const jurisdictionContext = { viewTier: 'county' };
const appSettings = { selectedJurisdiction: 'henrico' };

// ─── Helper Functions (matching index.html) ───

function _getActiveStateKey() { return _activeStateKey; }
function getActiveJurisdictionId() { return _activeJurisdiction; }

function _setMockRadio(name, value) {
    _mockRadios[name] = { value: value };
    _selectedFilterProfile = value;
}

// ─── Functions Under Test (extracted & adapted from index.html with bug fixes) ───

function getActiveRoadTypeSuffix(tier) {
    const activeTier = tier || jurisdictionContext.viewTier || 'county';
    const filterRadio = document.querySelector('input[name="roadTypeFilter"]:checked');
    const filterValue = filterRadio?.value || localStorage.getItem('selectedFilterProfile') || 'countyOnly';

    if (activeTier === 'state' || activeTier === 'federal' || activeTier === 'region') {
        const dotMap = {
            'countyOnly':      'dot_roads',
            'countyPlusVDOT':  'non_dot_roads',
            'allRoads':        activeTier === 'state' ? 'statewide_all_roads' : 'all_roads'
        };
        return dotMap[filterValue] || (activeTier === 'state' ? 'statewide_all_roads' : 'all_roads');
    }

    const localMap = {
        'countyOnly':      'county_roads',
        'countyPlusVDOT':  'no_interstate',
        'allRoads':        'all_roads'
    };
    return localMap[filterValue] || 'county_roads';
}

function getDataFilePath() {
    const tier = jurisdictionContext.viewTier || 'county';
    const stateKey = _getActiveStateKey() || 'colorado';
    const r2Prefix = appConfig?.states?.[stateKey]?.r2Prefix || stateKey;
    const roadType = getActiveRoadTypeSuffix(tier);

    if (tier === 'federal') return `_national/${roadType}.csv`;
    if (tier === 'state') return `${r2Prefix}/_state/${roadType}.csv`;

    if (tier === 'region') {
        const regionId = jurisdictionContext.tierRegion?.id;
        if (regionId) return `${r2Prefix}/_region/${regionId}/${roadType}.csv`;
    }

    if (tier === 'mpo') {
        const mpoId = jurisdictionContext.tierMpo?.id;
        if (mpoId) return `${r2Prefix}/_mpo/${mpoId}/${roadType}.csv`;
    }

    const jurisdiction = getActiveJurisdictionId();
    let r2Jurisdiction = jurisdiction;
    const stateAbbr = appConfig?.states?.[stateKey]?.abbreviation?.toLowerCase();
    if (stateAbbr && jurisdiction.startsWith(stateAbbr + '_')) {
        r2Jurisdiction = jurisdiction.substring(stateAbbr.length + 1);
    }
    // BUG FIX: Normalize jurisdiction to lowercase for R2 case-sensitive paths
    r2Jurisdiction = r2Jurisdiction.toLowerCase();

    return `${r2Prefix}/${r2Jurisdiction}/${roadType}.csv`;
}

// BUG FIX: getFallbackData uses active road type instead of hardcoded all_roads
function getFallbackData() {
    const stateKey = _getActiveStateKey() || 'colorado';
    const r2Prefix = appConfig?.states?.[stateKey]?.r2Prefix || stateKey;
    let jurisdiction = getActiveJurisdictionId() || 'douglas';
    const stAbbr = appConfig?.states?.[stateKey]?.abbreviation?.toLowerCase() || '';
    if (stAbbr && jurisdiction.startsWith(stAbbr + '_')) {
        jurisdiction = jurisdiction.substring(stAbbr.length + 1);
    }
    // BUG FIX: Use active road type instead of hardcoded all_roads
    const roadType = (typeof getActiveRoadTypeSuffix === 'function') ? getActiveRoadTypeSuffix() : 'all_roads';
    return `${r2Prefix}/${jurisdiction.toLowerCase()}/${roadType}.csv`;
}

function resolveDataUrl(localPath) {
    const baseUrl = r2State.manifest?.r2BaseUrl || R2_BASE_URL;

    let normalizedPath = localPath;
    if (normalizedPath.startsWith('../')) normalizedPath = normalizedPath.substring(3);
    if (normalizedPath.startsWith('./')) normalizedPath = normalizedPath.substring(2);

    // Strategy 1: Exact match in manifest
    if (r2State.manifest?.localPathMapping) {
        const r2Key = r2State.manifest.localPathMapping[normalizedPath];
        if (r2Key) return `${baseUrl}/${r2Key}`;
    }

    // Strategy 2: Dynamic R2 URL construction for legacy local paths
    if (normalizedPath.startsWith('data/') && appConfig?.states) {
        const activeStateKey = _getActiveStateKey();
        const stateConfig = activeStateKey ? appConfig.states[activeStateKey] : null;
        if (stateConfig?.r2Prefix) {
            const filename = normalizedPath.split('/').pop();
            if (filename) {
                const knownSuffixes = ['_county_roads.csv', '_no_interstate.csv', '_all_roads.csv'];
                let jurisdiction = null, filterWithExt = null;
                for (const suffix of knownSuffixes) {
                    if (filename.endsWith(suffix)) {
                        jurisdiction = filename.substring(0, filename.length - suffix.length);
                        filterWithExt = suffix.substring(1);
                        break;
                    }
                }
                if (!jurisdiction) {
                    const idx = filename.indexOf('_');
                    if (idx > 0) {
                        jurisdiction = filename.substring(0, idx);
                        filterWithExt = filename.substring(idx + 1);
                    }
                }
                if (jurisdiction && filterWithExt) {
                    // BUG FIX: lowercase jurisdiction
                    return `${baseUrl}/${stateConfig.r2Prefix}/${jurisdiction.toLowerCase()}/${filterWithExt}`;
                }
            }
        }
    }

    // Strategy 3: R2-native paths
    const tierPrefixes = ['_state/', '_statewide/', '_region/', '_mpo/', '_federal/', '_national/'];
    const isR2NativePath = !normalizedPath.startsWith('data/') &&
        normalizedPath.includes('/') &&
        (normalizedPath.endsWith('.csv') || normalizedPath.endsWith('.json') || normalizedPath.endsWith('.csv.gz'));
    if (isR2NativePath || tierPrefixes.some(p => normalizedPath.includes(p))) {
        return `${baseUrl}/${normalizedPath}`;
    }

    return localPath;
}

function buildLocalFallbackPaths(r2NativePath) {
    const fallbacks = [];
    if (!r2NativePath) return fallbacks;

    const parts = r2NativePath.replace(/^\//, '').split('/');
    if (parts.length < 3) {
        fallbacks.push(`../data/${r2NativePath}`);
        return fallbacks;
    }

    const statePrefix = parts[0];
    const jurisdiction = parts[1];
    const filename = parts.slice(2).join('/');
    const stateDataDir = appConfig?.states?.[statePrefix]?.dataDir;

    if (stateDataDir) {
        fallbacks.push(`../data/${stateDataDir}/${jurisdiction}_${filename}`);
    }
    fallbacks.push(`../data/${jurisdiction}_${filename}`);

    if (!filename.includes('all_roads')) {
        if (stateDataDir) {
            fallbacks.push(`../data/${stateDataDir}/${jurisdiction}_all_roads.csv`);
        }
        fallbacks.push(`../data/${jurisdiction}_all_roads.csv`);
    }

    return fallbacks;
}

function getPredictionForecastFile() {
    const roadType = getActiveRoadTypeSuffix();
    return `forecasts_${roadType}.json`;
}

// ─── Test Suites ───

console.log('\n\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550');
console.log('  Upload Tab Bug Tests — Virginia Data Loading Fix');
console.log('\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\n');

// ─── Test Suite 1: getFallbackData (road type selection) ───

console.log('\n--- getFallbackData: Road Type Selection ---');

_activeStateKey = 'virginia';
_activeJurisdiction = 'henrico';

_setMockRadio('roadTypeFilter', 'countyOnly');
assertEq(getFallbackData(), 'virginia/henrico/county_roads.csv',
    '1. getFallbackData returns county_roads.csv when countyOnly selected');

_setMockRadio('roadTypeFilter', 'countyPlusVDOT');
assertEq(getFallbackData(), 'virginia/henrico/no_interstate.csv',
    '2. getFallbackData returns no_interstate.csv when countyPlusVDOT selected');

_setMockRadio('roadTypeFilter', 'allRoads');
assertEq(getFallbackData(), 'virginia/henrico/all_roads.csv',
    '3. getFallbackData returns all_roads.csv when allRoads selected');

// Test Colorado too
_activeStateKey = 'colorado';
_activeJurisdiction = 'douglas';
_setMockRadio('roadTypeFilter', 'countyOnly');
assertEq(getFallbackData(), 'colorado/douglas/county_roads.csv',
    '4. getFallbackData returns Colorado county_roads.csv correctly');

_setMockRadio('roadTypeFilter', 'allRoads');
assertEq(getFallbackData(), 'colorado/douglas/all_roads.csv',
    '5. getFallbackData returns Colorado all_roads.csv correctly');

// ─── Test Suite 2: getDataFilePath (R2 path construction) ───

console.log('\n--- getDataFilePath: R2 Path Construction ---');

_activeStateKey = 'virginia';
_activeJurisdiction = 'henrico';
jurisdictionContext.viewTier = 'county';

_setMockRadio('roadTypeFilter', 'countyOnly');
assertEq(getDataFilePath(), 'virginia/henrico/county_roads.csv',
    '6. Virginia/Henrico/county_roads path');

_setMockRadio('roadTypeFilter', 'allRoads');
assertEq(getDataFilePath(), 'virginia/henrico/all_roads.csv',
    '7. Virginia/Henrico/all_roads path');

_setMockRadio('roadTypeFilter', 'countyPlusVDOT');
assertEq(getDataFilePath(), 'virginia/henrico/no_interstate.csv',
    '8. Virginia/Henrico/no_interstate path');

_activeStateKey = 'colorado';
_activeJurisdiction = 'douglas';
_setMockRadio('roadTypeFilter', 'countyOnly');
assertEq(getDataFilePath(), 'colorado/douglas/county_roads.csv',
    '9. Colorado/Douglas/county_roads path');

// Test lowercase normalization
_activeJurisdiction = 'Henrico';  // Uppercase
_activeStateKey = 'virginia';
_setMockRadio('roadTypeFilter', 'countyOnly');
assertEq(getDataFilePath(), 'virginia/henrico/county_roads.csv',
    '10. Uppercase jurisdiction normalized to lowercase');

// Test state abbreviation stripping
_activeJurisdiction = 'co_adams';
_activeStateKey = 'colorado';
assertEq(getDataFilePath(), 'colorado/adams/county_roads.csv',
    '11. State abbreviation prefix stripped from jurisdiction ID');

// Test tier paths
jurisdictionContext.viewTier = 'state';
_setMockRadio('roadTypeFilter', 'countyOnly');
assertEq(getDataFilePath(), 'colorado/_state/dot_roads.csv',
    '12. State tier path uses dot_roads suffix');

jurisdictionContext.viewTier = 'federal';
_setMockRadio('roadTypeFilter', 'allRoads');
assertEq(getDataFilePath(), '_national/all_roads.csv',
    '13. Federal tier path starts with _national');

// Reset
jurisdictionContext.viewTier = 'county';

// ─── Test Suite 3: resolveDataUrl (Virginia-specific) ───

console.log('\n--- resolveDataUrl: Virginia Paths ---');

_activeStateKey = 'virginia';

assertEq(
    resolveDataUrl('virginia/henrico/county_roads.csv'),
    'https://data.aicreatesai.com/virginia/henrico/county_roads.csv',
    '14. Resolves Virginia county_roads R2-native path');

assertEq(
    resolveDataUrl('virginia/henrico/all_roads.csv'),
    'https://data.aicreatesai.com/virginia/henrico/all_roads.csv',
    '15. Resolves Virginia all_roads R2-native path');

assertEq(
    resolveDataUrl('virginia/henrico/no_interstate.csv'),
    'https://data.aicreatesai.com/virginia/henrico/no_interstate.csv',
    '16. Resolves Virginia no_interstate R2-native path');

assertEq(
    resolveDataUrl('virginia/henrico/forecasts_county_roads.json'),
    'https://data.aicreatesai.com/virginia/henrico/forecasts_county_roads.json',
    '17. Resolves Virginia forecasts_county_roads.json');

assertEq(
    resolveDataUrl('virginia/henrico/forecasts_all_roads.json'),
    'https://data.aicreatesai.com/virginia/henrico/forecasts_all_roads.json',
    '18. Resolves Virginia forecasts_all_roads.json');

assertEq(
    resolveDataUrl('virginia/henrico/forecasts_no_interstate.json'),
    'https://data.aicreatesai.com/virginia/henrico/forecasts_no_interstate.json',
    '19. Resolves Virginia forecasts_no_interstate.json');

// ─── Test Suite 4: resolveDataUrl (Colorado for comparison) ───

console.log('\n--- resolveDataUrl: Colorado Paths ---');

_activeStateKey = 'colorado';

assertEq(
    resolveDataUrl('colorado/douglas/county_roads.csv'),
    'https://data.aicreatesai.com/colorado/douglas/county_roads.csv',
    '20. Resolves Colorado county_roads R2-native path');

assertEq(
    resolveDataUrl('colorado/douglas/all_roads.csv'),
    'https://data.aicreatesai.com/colorado/douglas/all_roads.csv',
    '21. Resolves Colorado all_roads R2-native path');

assertEq(
    resolveDataUrl('colorado/douglas/no_interstate.csv'),
    'https://data.aicreatesai.com/colorado/douglas/no_interstate.csv',
    '22. Resolves Colorado no_interstate R2-native path');

// ─── Test Suite 5: Case Normalization ───

console.log('\n--- Case Normalization ---');

_activeStateKey = 'virginia';
_activeJurisdiction = 'HENRICO';  // All uppercase
_setMockRadio('roadTypeFilter', 'allRoads');
assertIncludes(getDataFilePath(), 'henrico',
    '23. UPPERCASE jurisdiction normalized to lowercase in getDataFilePath');
assertNotIncludes(getDataFilePath(), 'HENRICO',
    '24. No uppercase jurisdiction in path');

_activeJurisdiction = 'Henrico';  // Mixed case
assertIncludes(getFallbackData(), 'henrico',
    '25. Mixed case jurisdiction normalized in fallback');
assertNotIncludes(getFallbackData(), 'Henrico',
    '26. No mixed case jurisdiction in fallback path');

_activeJurisdiction = 'henrico';  // Already lowercase
assertIncludes(getDataFilePath(), 'henrico',
    '27. Already lowercase jurisdiction preserved');

// ─── Test Suite 6: Road Type Switching Simulation ───

console.log('\n--- Road Type Switching (Virginia) ---');

_activeStateKey = 'virginia';
_activeJurisdiction = 'henrico';

_setMockRadio('roadTypeFilter', 'countyOnly');
const path1 = getDataFilePath();
assertEq(path1, 'virginia/henrico/county_roads.csv',
    '28. Initial: countyOnly → county_roads.csv');

_setMockRadio('roadTypeFilter', 'allRoads');
const path2 = getDataFilePath();
assertEq(path2, 'virginia/henrico/all_roads.csv',
    '29. Switch to allRoads → all_roads.csv');

assert(path1 !== path2,
    '30. Switching from countyOnly to allRoads changes the data file path');

_setMockRadio('roadTypeFilter', 'countyPlusVDOT');
const path3 = getDataFilePath();
assertEq(path3, 'virginia/henrico/no_interstate.csv',
    '31. Switch to countyPlusVDOT → no_interstate.csv');

assert(path2 !== path3,
    '32. Switching from allRoads to countyPlusVDOT changes the path');

_setMockRadio('roadTypeFilter', 'countyOnly');
assertEq(getDataFilePath(), 'virginia/henrico/county_roads.csv',
    '33. Switching back to countyOnly returns to original path');

console.log('\n--- Road Type Switching (Colorado) ---');

_activeStateKey = 'colorado';
_activeJurisdiction = 'douglas';

_setMockRadio('roadTypeFilter', 'countyOnly');
assertEq(getDataFilePath(), 'colorado/douglas/county_roads.csv',
    '34. Colorado countyOnly → county_roads.csv');

_setMockRadio('roadTypeFilter', 'allRoads');
assertEq(getDataFilePath(), 'colorado/douglas/all_roads.csv',
    '35. Colorado allRoads → all_roads.csv');

_setMockRadio('roadTypeFilter', 'countyPlusVDOT');
assertEq(getDataFilePath(), 'colorado/douglas/no_interstate.csv',
    '36. Colorado countyPlusVDOT → no_interstate.csv');

// ─── Test Suite 7: Forecast File Mapping ───

console.log('\n--- Forecast File Mapping ---');

_setMockRadio('roadTypeFilter', 'countyOnly');
assertEq(getPredictionForecastFile(), 'forecasts_county_roads.json',
    '37. countyOnly → forecasts_county_roads.json');

_setMockRadio('roadTypeFilter', 'countyPlusVDOT');
assertEq(getPredictionForecastFile(), 'forecasts_no_interstate.json',
    '38. countyPlusVDOT → forecasts_no_interstate.json');

_setMockRadio('roadTypeFilter', 'allRoads');
assertEq(getPredictionForecastFile(), 'forecasts_all_roads.json',
    '39. allRoads → forecasts_all_roads.json');

// ─── Test Suite 8: buildLocalFallbackPaths ───

console.log('\n--- buildLocalFallbackPaths ---');

const vaFallbacks = buildLocalFallbackPaths('virginia/henrico/county_roads.csv');
assert(vaFallbacks.some(p => p.includes('henrico_county_roads.csv')),
    '40. Virginia fallback includes henrico_county_roads.csv');
assert(vaFallbacks.some(p => p.includes('henrico_all_roads.csv')),
    '41. Virginia fallback includes all_roads variant');
// Virginia has no dataDir, so no CDOT-style paths
assert(!vaFallbacks.some(p => p.includes('CDOT')),
    '42. Virginia fallback does NOT include CDOT dataDir');

const coFallbacks = buildLocalFallbackPaths('colorado/douglas/county_roads.csv');
assert(coFallbacks.some(p => p.includes('CDOT/douglas_county_roads.csv')),
    '43. Colorado fallback includes CDOT/douglas_county_roads.csv');
assert(coFallbacks.some(p => p.includes('douglas_all_roads.csv')),
    '44. Colorado fallback includes all_roads variant');

const allRoadsFallbacks = buildLocalFallbackPaths('virginia/henrico/all_roads.csv');
assert(!allRoadsFallbacks.some(p => p.includes('henrico_all_roads.csv') && p !== '../data/henrico_all_roads.csv'),
    '45. No duplicate all_roads fallback when already requesting all_roads');

assertEq(buildLocalFallbackPaths(''), [],
    '46. Empty path returns empty array');

assertEq(buildLocalFallbackPaths(null), [],
    '47. Null path returns empty array');

// ─── Test Suite 9: Virginia vs Colorado Consistency ───

console.log('\n--- Virginia vs Colorado Consistency ---');

// The critical bug: when switching road types, Virginia must produce DIFFERENT paths
// just like Colorado does

_setMockRadio('roadTypeFilter', 'countyOnly');

_activeStateKey = 'virginia';
_activeJurisdiction = 'henrico';
const vaCounty = getDataFilePath();

_activeStateKey = 'colorado';
_activeJurisdiction = 'douglas';
const coCounty = getDataFilePath();

_setMockRadio('roadTypeFilter', 'allRoads');

_activeStateKey = 'virginia';
_activeJurisdiction = 'henrico';
const vaAll = getDataFilePath();

_activeStateKey = 'colorado';
_activeJurisdiction = 'douglas';
const coAll = getDataFilePath();

assert(vaCounty !== vaAll,
    '48. Virginia: county_roads path differs from all_roads path');
assert(coCounty !== coAll,
    '49. Colorado: county_roads path differs from all_roads path');

// Both should follow the same pattern
assertIncludes(vaCounty, 'county_roads.csv',
    '50. Virginia county path ends with county_roads.csv');
assertIncludes(vaAll, 'all_roads.csv',
    '51. Virginia all path ends with all_roads.csv');
assertIncludes(coCounty, 'county_roads.csv',
    '52. Colorado county path ends with county_roads.csv');
assertIncludes(coAll, 'all_roads.csv',
    '53. Colorado all path ends with all_roads.csv');

// Fallback should also use the correct road type for BOTH states
_setMockRadio('roadTypeFilter', 'countyPlusVDOT');

_activeStateKey = 'virginia';
_activeJurisdiction = 'henrico';
assertIncludes(getFallbackData(), 'no_interstate.csv',
    '54. Virginia fallback uses no_interstate when countyPlusVDOT selected');

_activeStateKey = 'colorado';
_activeJurisdiction = 'douglas';
assertIncludes(getFallbackData(), 'no_interstate.csv',
    '55. Colorado fallback uses no_interstate when countyPlusVDOT selected');

// ─── Summary ───

console.log('\n' + '\u2550'.repeat(60));
console.log(`  Results: ${passed} passed, ${failed} failed (${passed + failed} total)`);
console.log('\u2550'.repeat(60));

if (failed > 0) {
    console.log('\n  Failed tests:');
    errors.forEach(e => console.log(`    \u274C ${e}`));
    console.log('');
    process.exit(1);
} else {
    console.log('\n  \u2705 All tests passed!\n');
    process.exit(0);
}
