/**
 * Bug Test Suite — Grant AI Prompt Enrichment & Data Context
 *
 * Tests all changes from the grant prompt improvement PR:
 * 1. getCombinedSelectionStats() — crash pattern aggregation
 * 2. buildEnrichedGrantContext() — context string builder
 * 3. buildGrantProgramRequirements() / GRANT_PROGRAM_REQUIREMENTS — state-aware
 * 4. getGrantAISystemPrompt() — upgraded prompt content
 * 5. getGrantSearchSystemPrompt() — expanded programs
 * 6. getFullApplicationSystemPrompt() — enhanced sections
 * 7. buildGrantAgent1Input() — crash patterns in agent input
 * 8. Agent system prompts — enhanced content
 *
 * Run in browser console on the CRASH LENS app page.
 *
 * Usage (Browser console):
 *   Copy-paste into DevTools console while app is loaded.
 *   Or: fetch('/tests/test_grant_prompt_enrichment.js').then(r=>r.text()).then(eval)
 *
 * Tests marked [DATA] require crashState.loaded === true.
 * Tests marked [GRANT] require the Grants tab to have been initialized.
 */
(function() {
    'use strict';

    let passed = 0;
    let failed = 0;
    let skipped = 0;
    let errors = [];

    function assert(condition, testName) {
        if (condition) {
            passed++;
            console.log(`  ✅ PASS: ${testName}`);
        } else {
            failed++;
            errors.push(testName);
            console.error(`  ❌ FAIL: ${testName}`);
        }
    }

    function assertEq(actual, expected, testName) {
        const eq = JSON.stringify(actual) === JSON.stringify(expected);
        if (eq) {
            passed++;
            console.log(`  ✅ PASS: ${testName}`);
        } else {
            failed++;
            errors.push(`${testName} (expected: ${JSON.stringify(expected)}, got: ${JSON.stringify(actual)})`);
            console.error(`  ❌ FAIL: ${testName}\n    Expected: ${JSON.stringify(expected)}\n    Got:      ${JSON.stringify(actual)}`);
        }
    }

    function assertContains(str, substr, testName) {
        if (typeof str === 'string' && str.includes(substr)) {
            passed++;
            console.log(`  ✅ PASS: ${testName}`);
        } else {
            failed++;
            errors.push(`${testName} (string does not contain "${substr}")`);
            console.error(`  ❌ FAIL: ${testName}\n    String does not contain: "${substr}"`);
        }
    }

    function assertType(val, type, testName) {
        if (typeof val === type) {
            passed++;
            console.log(`  ✅ PASS: ${testName}`);
        } else {
            failed++;
            errors.push(`${testName} (expected type ${type}, got ${typeof val})`);
            console.error(`  ❌ FAIL: ${testName}\n    Expected type: ${type}\n    Got: ${typeof val}`);
        }
    }

    function skip(testName) {
        skipped++;
        console.log(`  ⏭️ SKIP: ${testName}`);
    }

    console.log('\n╔══════════════════════════════════════════════════════════════╗');
    console.log('║  GRANT AI PROMPT ENRICHMENT — BUG TEST SUITE               ║');
    console.log('╚══════════════════════════════════════════════════════════════╝\n');

    // ═══════════════════════════════════════════════════════════
    // TEST GROUP 1: Function Existence
    // ═══════════════════════════════════════════════════════════
    console.log('═══ 1. FUNCTION EXISTENCE CHECKS ═══');

    assert(typeof getCombinedSelectionStats === 'function', 'getCombinedSelectionStats exists');
    assert(typeof buildEnrichedGrantContext === 'function', 'buildEnrichedGrantContext exists');
    assert(typeof buildGrantProgramRequirements === 'function', 'buildGrantProgramRequirements exists');
    assert(typeof getGrantAISystemPrompt === 'function', 'getGrantAISystemPrompt exists');
    assert(typeof getGrantSearchSystemPrompt === 'function', 'getGrantSearchSystemPrompt exists');
    assert(typeof getFullApplicationSystemPrompt === 'function', 'getFullApplicationSystemPrompt exists');
    assert(typeof buildGrantAgent1Input === 'function', 'buildGrantAgent1Input exists');

    // ═══════════════════════════════════════════════════════════
    // TEST GROUP 2: GRANT_PROGRAM_REQUIREMENTS — State-Aware
    // ═══════════════════════════════════════════════════════════
    console.log('\n═══ 2. GRANT_PROGRAM_REQUIREMENTS — STATE-AWARE ═══');

    assert(typeof GRANT_PROGRAM_REQUIREMENTS === 'object', 'GRANT_PROGRAM_REQUIREMENTS is an object');
    assert(GRANT_PROGRAM_REQUIREMENTS.ss4a !== undefined, 'ss4a program exists');
    assert(GRANT_PROGRAM_REQUIREMENTS.hsip !== undefined, 'hsip program exists');
    assert(GRANT_PROGRAM_REQUIREMENTS.nhtsa402 !== undefined, 'nhtsa402 program exists');
    assert(GRANT_PROGRAM_REQUIREMENTS.nhtsa405 !== undefined, 'nhtsa405 program exists');

    // SS4A should always be USDOT (not state-specific)
    assertEq(GRANT_PROGRAM_REQUIREMENTS.ss4a.agency, 'USDOT', 'SS4A agency is USDOT');
    assertEq(GRANT_PROGRAM_REQUIREMENTS.ss4a.federalShare, '80%', 'SS4A federal share is 80%');

    // HSIP should NOT be hardcoded to "VDOT"
    assert(GRANT_PROGRAM_REQUIREMENTS.hsip.agency !== undefined, 'HSIP has agency defined');
    const hsipAgency = GRANT_PROGRAM_REQUIREMENTS.hsip.agency;
    // If we're in Colorado, it should NOT say "VDOT"
    if (jurisdictionContext.stateFips === '08') {
        assert(hsipAgency !== 'VDOT', 'HSIP agency is NOT hardcoded to VDOT (Colorado context)');
    }

    // NHTSA 402/405 should NOT be hardcoded to "Virginia DMV"
    assert(GRANT_PROGRAM_REQUIREMENTS.nhtsa402.agency !== 'Virginia DMV',
        'NHTSA 402 agency is NOT hardcoded to Virginia DMV');
    assert(GRANT_PROGRAM_REQUIREMENTS.nhtsa405.agency !== 'Virginia DMV',
        'NHTSA 405 agency is NOT hardcoded to Virginia DMV');

    // Check enhanced content
    assert(GRANT_PROGRAM_REQUIREMENTS.ss4a.focusAreas.length >= 5,
        'SS4A has 5+ focus areas (enhanced)');
    assertContains(GRANT_PROGRAM_REQUIREMENTS.ss4a.tips, 'Justice40',
        'SS4A tips mention Justice40');
    assertContains(GRANT_PROGRAM_REQUIREMENTS.hsip.tips, 'CMF Clearinghouse',
        'HSIP tips mention CMF Clearinghouse');
    assertContains(GRANT_PROGRAM_REQUIREMENTS.nhtsa402.tips, 'Countermeasures That Work',
        'NHTSA 402 tips mention Countermeasures That Work');

    // Check scoring emphasis has reasonable weights
    const ss4aScoring = GRANT_PROGRAM_REQUIREMENTS.ss4a.scoringEmphasis;
    const ss4aTotal = Object.values(ss4aScoring).reduce((a, b) => a + b, 0);
    assertEq(ss4aTotal, 100, 'SS4A scoring weights sum to 100');

    const hsipScoring = GRANT_PROGRAM_REQUIREMENTS.hsip.scoringEmphasis;
    const hsipTotal = Object.values(hsipScoring).reduce((a, b) => a + b, 0);
    assertEq(hsipTotal, 100, 'HSIP scoring weights sum to 100');

    // ═══════════════════════════════════════════════════════════
    // TEST GROUP 3: getGrantAISystemPrompt() — Content Quality
    // ═══════════════════════════════════════════════════════════
    console.log('\n═══ 3. getGrantAISystemPrompt() — CONTENT QUALITY ═══');

    const grantPrompt = getGrantAISystemPrompt();
    assertType(grantPrompt, 'string', 'getGrantAISystemPrompt returns string');
    assert(grantPrompt.length > 500, 'Grant AI prompt is substantial (>500 chars)');

    // Must mention key concepts
    assertContains(grantPrompt, 'Safe System', 'Prompt mentions Safe System approach');
    assertContains(grantPrompt, 'Vision Zero', 'Prompt mentions Vision Zero');
    assertContains(grantPrompt, 'CMF Clearinghouse', 'Prompt mentions CMF Clearinghouse');
    assertContains(grantPrompt, 'SHSP', 'Prompt mentions SHSP alignment');
    assertContains(grantPrompt, 'Justice40', 'Prompt mentions Justice40');
    assertContains(grantPrompt, 'EPDO', 'Prompt mentions EPDO');
    assertContains(grantPrompt, 'Countermeasures That Work', 'Prompt mentions Countermeasures That Work');
    assertContains(grantPrompt, 'crash', 'Prompt uses "crash" terminology');
    assertContains(grantPrompt, 'accident', 'Prompt warns against using "accident"');

    // Must mention grant programs
    assertContains(grantPrompt, 'SS4A', 'Prompt mentions SS4A');
    assertContains(grantPrompt, 'HSIP', 'Prompt mentions HSIP');
    assertContains(grantPrompt, 'NHTSA 402', 'Prompt mentions NHTSA 402');
    assertContains(grantPrompt, '405', 'Prompt mentions 405');

    // Should NOT contain "undefined" or template literal errors
    assert(!grantPrompt.includes('undefined'), 'Prompt has no "undefined" values');
    assert(!grantPrompt.includes('${'), 'Prompt has no unresolved template literals');

    // ═══════════════════════════════════════════════════════════
    // TEST GROUP 4: getGrantSearchSystemPrompt() — Expanded Programs
    // ═══════════════════════════════════════════════════════════
    console.log('\n═══ 4. getGrantSearchSystemPrompt() — EXPANDED PROGRAMS ═══');

    const searchPrompt = getGrantSearchSystemPrompt();
    assertType(searchPrompt, 'string', 'getGrantSearchSystemPrompt returns string');

    // Should mention expanded program list
    assertContains(searchPrompt, 'RAISE', 'Search prompt mentions RAISE grants');
    assertContains(searchPrompt, 'INFRA', 'Search prompt mentions INFRA grants');
    assertContains(searchPrompt, 'TAP', 'Search prompt mentions TAP');
    assertContains(searchPrompt, '405b', 'Search prompt mentions 405b');
    assertContains(searchPrompt, '405c', 'Search prompt mentions 405c');
    assertContains(searchPrompt, '405d', 'Search prompt mentions 405d');
    assertContains(searchPrompt, '405f', 'Search prompt mentions 405f');

    // Should have crash-pattern-to-grant matching rules
    assertContains(searchPrompt, 'VRU', 'Search prompt has VRU matching');
    assertContains(searchPrompt, 'impaired', 'Search prompt has impaired matching');
    assertContains(searchPrompt, 'speed', 'Search prompt has speed matching');
    assertContains(searchPrompt, 'night', 'Search prompt has night crash matching');
    assertContains(searchPrompt, 'grant stacking', 'Search prompt mentions grant stacking');

    assert(!searchPrompt.includes('undefined'), 'Search prompt has no "undefined" values');

    // ═══════════════════════════════════════════════════════════
    // TEST GROUP 5: getFullApplicationSystemPrompt() — Enhanced
    // ═══════════════════════════════════════════════════════════
    console.log('\n═══ 5. getFullApplicationSystemPrompt() — ENHANCED ═══');

    const fullPrompt = getFullApplicationSystemPrompt();
    assertType(fullPrompt, 'string', 'getFullApplicationSystemPrompt returns string');

    assertContains(fullPrompt, 'Justice40', 'Full prompt mentions Justice40 in equity section');
    assertContains(fullPrompt, 'CDC', 'Full prompt mentions CDC SVI');
    assertContains(fullPrompt, 'EJ Screen', 'Full prompt mentions EJ Screen');
    assertContains(fullPrompt, 'Safe System', 'Full prompt mentions Safe System');
    assertContains(fullPrompt, 'behavioral', 'Full prompt mentions behavioral factors');
    assertContains(fullPrompt, 'SHSP', 'Full prompt mentions SHSP alignment');
    assertContains(fullPrompt, 'crash pattern', 'Full prompt mentions crash patterns');

    assert(!fullPrompt.includes('undefined'), 'Full prompt has no "undefined" values');

    // ═══════════════════════════════════════════════════════════
    // TEST GROUP 6: Agent System Prompts — Enhanced Content
    // ═══════════════════════════════════════════════════════════
    console.log('\n═══ 6. AGENT SYSTEM PROMPTS — ENHANCED ═══');

    // Agent 1
    assertContains(GRANT_AGENT1_SYSTEM_PROMPT, 'behavioralFactors', 'Agent 1 prompt includes behavioral factors in output format');
    assertContains(GRANT_AGENT1_SYSTEM_PROMPT, 'grantImplications', 'Agent 1 prompt includes grant implications field');
    assertContains(GRANT_AGENT1_SYSTEM_PROMPT, 'tenYearProjection', 'Agent 1 prompt includes 10-year projection');
    assertContains(GRANT_AGENT1_SYSTEM_PROMPT, 'kaContext', 'Agent 1 prompt includes K+A context comparison');

    // Agent 2
    assertContains(GRANT_AGENT2_SYSTEM_PROMPT, 'Safe System', 'Agent 2 prompt mentions Safe System');
    assertContains(GRANT_AGENT2_SYSTEM_PROMPT, 'SHSP', 'Agent 2 prompt mentions SHSP');
    assertContains(GRANT_AGENT2_SYSTEM_PROMPT, 'crashPatternStrategy', 'Agent 2 output includes crash pattern strategy');
    assertContains(GRANT_AGENT2_SYSTEM_PROMPT, 'safeSystemPillars', 'Agent 2 output includes Safe System pillars');

    // Agent 3
    assertContains(GRANT_AGENT3_SYSTEM_PROMPT, 'Justice40', 'Agent 3 prompt mentions Justice40');
    assertContains(GRANT_AGENT3_SYSTEM_PROMPT, 'SECTION-SPECIFIC', 'Agent 3 prompt has section-specific guidance');
    assertContains(GRANT_AGENT3_SYSTEM_PROMPT, 'Complete Streets', 'Agent 3 prompt mentions Complete Streets');
    assertContains(GRANT_AGENT3_SYSTEM_PROMPT, 'CMF ID', 'Agent 3 prompt requires CMF IDs');

    // Agent 4
    assertContains(GRANT_AGENT4_SYSTEM_PROMPT, 'COMMON REJECTION REASONS', 'Agent 4 prompt has rejection reasons');
    assertContains(GRANT_AGENT4_SYSTEM_PROMPT, 'fundingLikelihood', 'Agent 4 output includes funding likelihood');
    assertContains(GRANT_AGENT4_SYSTEM_PROMPT, 'programSpecific', 'Agent 4 checks program-specific requirements');
    assertContains(GRANT_AGENT4_SYSTEM_PROMPT, 'Countermeasure-to-pattern', 'Agent 4 checks countermeasure linkage');

    // ═══════════════════════════════════════════════════════════
    // TEST GROUP 7: getCombinedSelectionStats() — Pattern Aggregation
    // ═══════════════════════════════════════════════════════════
    console.log('\n═══ 7. getCombinedSelectionStats() — PATTERN AGGREGATION ═══');

    if (typeof grantState === 'undefined' || !grantState.rankedLocations || grantState.rankedLocations.length === 0) {
        skip('[GRANT] getCombinedSelectionStats — no ranked locations loaded');
        skip('[GRANT] Pattern fields exist on combined stats');
        skip('[GRANT] Rates are calculated');
    } else {
        // Save original selection, set up test selection
        const origSelection = [...grantState.selectedLocationIndices];

        // Select first location for testing
        grantState.selectedLocationIndices = [0];
        const combined = getCombinedSelectionStats();

        // Check new pattern fields exist
        assert('night' in combined, 'Combined stats has "night" field');
        assert('impaired' in combined, 'Combined stats has "impaired" field');
        assert('speed' in combined, 'Combined stats has "speed" field');
        assert('distracted' in combined, 'Combined stats has "distracted" field');
        assert('angle' in combined, 'Combined stats has "angle" field');
        assert('headOn' in combined, 'Combined stats has "headOn" field');
        assert('rearEnd' in combined, 'Combined stats has "rearEnd" field');
        assert('sideswipe' in combined, 'Combined stats has "sideswipe" field');
        assert('runOffRoad' in combined, 'Combined stats has "runOffRoad" field');
        assert('wetRoad' in combined, 'Combined stats has "wetRoad" field');
        assert('weekendNight' in combined, 'Combined stats has "weekendNight" field');
        assert('rushHour' in combined, 'Combined stats has "rushHour" field');
        assert('collisionTypes' in combined, 'Combined stats has "collisionTypes" field');
        assert('lightConditions' in combined, 'Combined stats has "lightConditions" field');

        // Check rate fields
        assert('kaRate' in combined, 'Combined stats has "kaRate" field');
        assert('vruRate' in combined, 'Combined stats has "vruRate" field');
        assert('nightRate' in combined, 'Combined stats has "nightRate" field');
        assert('impairedRate' in combined, 'Combined stats has "impairedRate" field');
        assert('speedRate' in combined, 'Combined stats has "speedRate" field');

        // Check types
        assertType(combined.night, 'number', 'night is a number');
        assertType(combined.impaired, 'number', 'impaired is a number');
        assertType(combined.collisionTypes, 'object', 'collisionTypes is an object');
        assertType(combined.kaRate, 'string', 'kaRate is a string (percentage)');

        // Check rates are valid numbers (not NaN)
        assert(!isNaN(parseFloat(combined.kaRate)), 'kaRate is not NaN');
        assert(!isNaN(parseFloat(combined.vruRate)), 'vruRate is not NaN');
        assert(!isNaN(parseFloat(combined.nightRate)), 'nightRate is not NaN');

        // Check rates are between 0 and 100
        const kr = parseFloat(combined.kaRate);
        assert(kr >= 0 && kr <= 100, `kaRate (${kr}) is between 0-100`);

        // Check pattern values are non-negative
        assert(combined.night >= 0, 'night count is non-negative');
        assert(combined.impaired >= 0, 'impaired count is non-negative');
        assert(combined.speed >= 0, 'speed count is non-negative');

        // Check that original fields still work
        assert(combined.crashes >= 0, 'crashes count still works');
        assert(combined.K >= 0, 'K count still works');
        assert(combined.epdo >= 0, 'epdo still works');
        assert(combined.vru >= 0, 'vru still works');
        assertEq(combined.vru, combined.ped + combined.bike, 'vru = ped + bike');

        // Test multi-selection aggregation
        if (grantState.rankedLocations.length >= 2) {
            grantState.selectedLocationIndices = [0, 1];
            const multi = getCombinedSelectionStats();

            const loc0 = grantState.rankedLocations[0];
            const loc1 = grantState.rankedLocations[1];

            assertEq(multi.crashes, loc0.crashes + loc1.crashes,
                'Multi-select: crash counts aggregate correctly');
            assertEq(multi.K, loc0.K + loc1.K,
                'Multi-select: K counts aggregate correctly');

            // Pattern aggregation
            if (loc0.patterns && loc1.patterns) {
                assertEq(multi.night, (loc0.patterns.night || 0) + (loc1.patterns.night || 0),
                    'Multi-select: night patterns aggregate correctly');
                assertEq(multi.impaired, (loc0.patterns.impaired || 0) + (loc1.patterns.impaired || 0),
                    'Multi-select: impaired patterns aggregate correctly');
            }
        }

        // Restore original selection
        grantState.selectedLocationIndices = origSelection;
    }

    // ═══════════════════════════════════════════════════════════
    // TEST GROUP 8: buildEnrichedGrantContext() — Context Builder
    // ═══════════════════════════════════════════════════════════
    console.log('\n═══ 8. buildEnrichedGrantContext() — CONTEXT BUILDER ═══');

    // Test with mock data
    const mockLocs = [{
        name: 'Test Rd @ Main St', type: 'intersection',
        crashes: 20, K: 1, A: 3, B: 5, C: 6, O: 5,
        epdo: 800, ped: 2, bike: 1, bestMatch: 'ss4a',
        matchingGrants: [{ program: 'ss4a', strength: 'strong' }, { program: 'hsip', strength: 'moderate' }],
        patterns: { night: 6, impaired: 3, speed: 4, distracted: 2, angle: 8, headOn: 1, rearEnd: 5, sideswipe: 2, runOffRoad: 0, wetRoad: 3, weekendNight: 2, rushHour: 7, collisionTypes: { 'Angle': 8, 'Rear End': 5 }, lightConditions: { 'Dark': 6, 'Daylight': 14 } }
    }];
    const mockCombined = {
        crashes: 20, K: 1, A: 3, B: 5, C: 6, O: 5,
        epdo: 800, ped: 2, bike: 1, vru: 3, score: 150,
        night: 6, impaired: 3, speed: 4, distracted: 2,
        angle: 8, headOn: 1, rearEnd: 5, sideswipe: 2, runOffRoad: 0,
        wetRoad: 3, weekendNight: 2, rushHour: 7,
        collisionTypes: { 'Angle': 8, 'Rear End': 5 },
        lightConditions: { 'Dark': 6, 'Daylight': 14 },
        kaRate: '20.0', vruRate: '15.0', nightRate: '30.0',
        impairedRate: '15.0', speedRate: '20.0'
    };

    const ctx = buildEnrichedGrantContext(mockLocs, mockCombined);
    assertType(ctx, 'string', 'buildEnrichedGrantContext returns string');
    assert(ctx.length > 200, 'Context string is substantial');

    // Check sections exist
    assertContains(ctx, 'JURISDICTION', 'Context has JURISDICTION section');
    assertContains(ctx, 'SELECTED LOCATIONS', 'Context has SELECTED LOCATIONS section');
    assertContains(ctx, 'COMBINED CRASH SUMMARY', 'Context has CRASH SUMMARY section');
    assertContains(ctx, 'CRASH PATTERNS', 'Context has CRASH PATTERNS section');
    assertContains(ctx, 'COLLISION TYPE DISTRIBUTION', 'Context has COLLISION TYPE section');
    assertContains(ctx, 'FINANCIAL IMPACT', 'Context has FINANCIAL IMPACT section');
    assertContains(ctx, 'MATCHING GRANT PROGRAMS', 'Context has MATCHING GRANTS section');

    // Check data appears correctly
    assertContains(ctx, 'Test Rd @ Main St', 'Context includes location name');
    assertContains(ctx, 'K+A Rate: 20.0%', 'Context includes K+A rate');
    assertContains(ctx, 'Night/Dark: 6', 'Context includes night crash count');
    assertContains(ctx, 'Impaired', 'Context includes impaired data');
    assertContains(ctx, 'Speed-Related', 'Context includes speed data');
    assertContains(ctx, 'Angle: 8', 'Context includes collision type counts');
    assertContains(ctx, 'Annual Crash Cost', 'Context includes annual crash cost');

    // Test with grant program option
    const ctxWithGrant = buildEnrichedGrantContext(mockLocs, mockCombined, { grantProgram: 'ss4a' });
    assertContains(ctxWithGrant, 'TARGET GRANT PROGRAM', 'Context with grant has TARGET section');
    assertContains(ctxWithGrant, 'Safe Streets', 'Context includes SS4A program name');
    assertContains(ctxWithGrant, 'Scoring Criteria', 'Context includes scoring criteria');

    // Test without grant program (should not have TARGET section)
    assert(!ctx.includes('TARGET GRANT PROGRAM'), 'Context without grant has no TARGET section');

    // Test with empty/zero crashes (division by zero guard)
    const zeroCombined = { ...mockCombined, crashes: 0, night: 0, impaired: 0 };
    try {
        const zeroCtx = buildEnrichedGrantContext(mockLocs, zeroCombined);
        assert(typeof zeroCtx === 'string', 'Context handles zero crashes without error');
        assert(!zeroCtx.includes('NaN'), 'Context has no NaN with zero crashes');
        assert(!zeroCtx.includes('Infinity'), 'Context has no Infinity with zero crashes');
    } catch (e) {
        assert(false, `Context threw error with zero crashes: ${e.message}`);
    }

    // ═══════════════════════════════════════════════════════════
    // TEST GROUP 9: buildGrantAgent1Input() — Crash Patterns
    // ═══════════════════════════════════════════════════════════
    console.log('\n═══ 9. buildGrantAgent1Input() — CRASH PATTERNS ═══');

    const testCrashData = {
        locationName: 'Test Intersection',
        locationType: 'Intersection',
        total: 30,
        K: 2, A: 4, B: 8, C: 10, O: 6,
        yearRange: '2020-2024',
        pedestrian: 3, bicycle: 1,
        collisionTypes: { 'Angle': 12, 'Rear End': 10 },
        patterns: {
            night: 8, impaired: 5, speed: 3, distracted: 2,
            angle: 12, headOn: 1, rearEnd: 10, sideswipe: 3, runOffRoad: 0,
            wetRoad: 4, weekendNight: 3, rushHour: 9
        }
    };
    const testProjectParams = {
        cost: 750000, cmf: 0.70, analysisPeriod: 10,
        crashCosts: { K: 12800000, A: 655000, B: 198000, C: 125000, O: 12400 }
    };

    const agent1Input = buildGrantAgent1Input(testCrashData, testProjectParams);
    assertType(agent1Input, 'string', 'buildGrantAgent1Input returns string');

    // Check basic data
    assertContains(agent1Input, 'Test Intersection', 'Agent 1 input has location name');
    assertContains(agent1Input, 'Total=30', 'Agent 1 input has total crashes');

    // Check NEW crash pattern data is included
    assertContains(agent1Input, 'CRASH PATTERNS', 'Agent 1 input has CRASH PATTERNS section');
    assertContains(agent1Input, 'Night/Dark: 8', 'Agent 1 input has night crash count');
    assertContains(agent1Input, 'Impaired: 5', 'Agent 1 input has impaired count');
    assertContains(agent1Input, 'Speed-Related: 3', 'Agent 1 input has speed count');
    assertContains(agent1Input, 'Angle: 12', 'Agent 1 input has angle collision count');
    assertContains(agent1Input, 'Wet Road', 'Agent 1 input has wet road data');
    assertContains(agent1Input, 'Weekend Night', 'Agent 1 input has weekend night data');

    // Check percentages are calculated correctly
    assertContains(agent1Input, '26.7%', 'Agent 1 input has correct night % (8/30=26.7%)');
    assertContains(agent1Input, '16.7%', 'Agent 1 input has correct impaired % (5/30=16.7%)');

    // Check K+A rate is included
    assertContains(agent1Input, 'K+A RATE', 'Agent 1 input has K+A rate');

    // Check jurisdiction context
    assertContains(agent1Input, 'JURISDICTION', 'Agent 1 input has jurisdiction');

    // Test WITHOUT patterns (backward compatibility)
    const noPatternsData = { ...testCrashData, patterns: null };
    const noPatternsInput = buildGrantAgent1Input(noPatternsData, testProjectParams);
    assert(!noPatternsInput.includes('CRASH PATTERNS'), 'Agent 1 input without patterns omits CRASH PATTERNS section');
    assertContains(noPatternsInput, 'Total=30', 'Agent 1 input without patterns still has basic data');

    // Test with zero crashes (division by zero guard)
    const zeroCrashData = { ...testCrashData, total: 0, patterns: { night: 0, impaired: 0, speed: 0, distracted: 0, angle: 0, headOn: 0, rearEnd: 0, sideswipe: 0, runOffRoad: 0, wetRoad: 0, weekendNight: 0, rushHour: 0 } };
    try {
        const zeroInput = buildGrantAgent1Input(zeroCrashData, testProjectParams);
        assert(!zeroInput.includes('NaN'), 'Agent 1 input has no NaN with zero crashes');
        assert(!zeroInput.includes('Infinity'), 'Agent 1 input has no Infinity with zero crashes');
        passed++;
        console.log('  ✅ PASS: Agent 1 input handles zero crashes without error');
    } catch (e) {
        assert(false, `Agent 1 input threw error with zero crashes: ${e.message}`);
    }

    // ═══════════════════════════════════════════════════════════
    // TEST GROUP 10: getCombinedSelectionStats — Division-by-Zero Guard
    // ═══════════════════════════════════════════════════════════
    console.log('\n═══ 10. EDGE CASES — DIVISION BY ZERO ═══');

    // Test with empty selection
    const origSel = grantState?.selectedLocationIndices ? [...grantState.selectedLocationIndices] : [];
    if (typeof grantState !== 'undefined') {
        grantState.selectedLocationIndices = [];
        const emptyCombined = getCombinedSelectionStats();
        assertEq(emptyCombined.crashes, 0, 'Empty selection: crashes = 0');
        assert(!isNaN(parseFloat(emptyCombined.kaRate)), 'Empty selection: kaRate is not NaN');
        assertEq(emptyCombined.kaRate, '0.0', 'Empty selection: kaRate = 0.0');
        assertEq(emptyCombined.vruRate, '0.0', 'Empty selection: vruRate = 0.0');
        assertEq(emptyCombined.nightRate, '0.0', 'Empty selection: nightRate = 0.0');

        grantState.selectedLocationIndices = origSel;
    }

    // ═══════════════════════════════════════════════════════════
    // TEST GROUP 11: buildEnrichedGrantContext — No Undefined/NaN
    // ═══════════════════════════════════════════════════════════
    console.log('\n═══ 11. CONTEXT STRING — NO UNDEFINED/NaN ═══');

    // Test with minimal data (lots of nulls/undefined)
    const minimalLocs = [{ name: 'Minimal Rd', type: 'route', crashes: 5, K: 0, A: 0, B: 2, C: 2, O: 1, epdo: 29, ped: 0, bike: 0 }];
    const minimalCombined = {
        crashes: 5, K: 0, A: 0, B: 2, C: 2, O: 1,
        epdo: 29, ped: 0, bike: 0, vru: 0, score: 10,
        night: 1, impaired: 0, speed: 0, distracted: 0,
        angle: 2, headOn: 0, rearEnd: 1, sideswipe: 0, runOffRoad: 0,
        wetRoad: 0, weekendNight: 0, rushHour: 0,
        collisionTypes: { 'Angle': 2, 'Rear End': 1 },
        lightConditions: {},
        kaRate: '0.0', vruRate: '0.0', nightRate: '20.0',
        impairedRate: '0.0', speedRate: '0.0'
    };
    const minCtx = buildEnrichedGrantContext(minimalLocs, minimalCombined);
    assert(!minCtx.includes('undefined'), 'Minimal context has no "undefined"');
    assert(!minCtx.includes('NaN'), 'Minimal context has no "NaN"');
    assert(!minCtx.includes('null'), 'Minimal context has no "null" strings');

    // Test with no matching grants (no matchingGrants property)
    const noGrantLocs = [{ name: 'No Grant Rd', type: 'route', crashes: 3, K: 0, A: 0, B: 1, C: 1, O: 1, epdo: 18, ped: 0, bike: 0 }];
    const noGrantCtx = buildEnrichedGrantContext(noGrantLocs, minimalCombined);
    assert(!noGrantCtx.includes('MATCHING GRANT PROGRAMS'), 'No-grant context omits matching grants section');

    // ═══════════════════════════════════════════════════════════
    // TEST GROUP 12: Integration — Live Data Flow [DATA/GRANT]
    // ═══════════════════════════════════════════════════════════
    console.log('\n═══ 12. INTEGRATION — LIVE DATA FLOW ═══');

    if (typeof crashState !== 'undefined' && crashState.loaded &&
        typeof grantState !== 'undefined' && grantState.allRankedLocations?.length > 0) {

        // Check that ranked locations have patterns
        const firstLoc = grantState.allRankedLocations[0];
        assert(firstLoc.patterns !== undefined, 'First ranked location has patterns object');

        if (firstLoc.patterns) {
            assertType(firstLoc.patterns.night, 'number', 'Location patterns.night is a number');
            assertType(firstLoc.patterns.impaired, 'number', 'Location patterns.impaired is a number');
            assert(firstLoc.patterns.total >= 0, 'Location patterns.total is non-negative');
            assert(typeof firstLoc.patterns.collisionTypes === 'object', 'Location has collisionTypes object');
        }

        // Check matching grants exist
        assert(firstLoc.matchingGrants !== undefined, 'First location has matchingGrants');
        assert(Array.isArray(firstLoc.matchingGrants), 'matchingGrants is an array');

        // Test full context building with real data
        const origSel2 = [...grantState.selectedLocationIndices];
        grantState.selectedLocationIndices = [0];
        const realCombined = getCombinedSelectionStats();

        // Verify pattern aggregation matches single location
        if (firstLoc.patterns) {
            assertEq(realCombined.night, firstLoc.patterns.night || 0,
                'Single selection: night matches location patterns');
            assertEq(realCombined.impaired, firstLoc.patterns.impaired || 0,
                'Single selection: impaired matches location patterns');
        }

        // Build real context
        const realLocs = [grantState.rankedLocations[0]];
        const realCtx = buildEnrichedGrantContext(realLocs, realCombined);
        assert(!realCtx.includes('NaN'), 'Real data context has no NaN');
        assert(!realCtx.includes('undefined'), 'Real data context has no undefined');
        assertContains(realCtx, 'CRASH PATTERNS', 'Real data context has crash patterns');
        assertContains(realCtx, 'FINANCIAL IMPACT', 'Real data context has financial impact');

        grantState.selectedLocationIndices = origSel2;
    } else {
        skip('[DATA/GRANT] Integration tests — crash data or grant tab not loaded');
    }

    // ═══════════════════════════════════════════════════════════
    // RESULTS
    // ═══════════════════════════════════════════════════════════
    console.log('\n╔══════════════════════════════════════════════════════════════╗');
    console.log(`║  RESULTS: ${passed} passed, ${failed} failed, ${skipped} skipped`);
    console.log('╚══════════════════════════════════════════════════════════════╝');

    if (errors.length > 0) {
        console.log('\n❌ FAILURES:');
        errors.forEach((e, i) => console.error(`  ${i + 1}. ${e}`));
    }

    if (failed === 0) {
        console.log('\n🎉 ALL TESTS PASSED!');
    }

    return { passed, failed, skipped, errors };
})();
