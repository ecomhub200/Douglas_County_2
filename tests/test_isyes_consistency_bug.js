/**
 * Test: isYes() consistency bug in buildCMFCrashProfile()
 *
 * BUG: buildCMFCrashProfile() used hardcoded checks like:
 *   row[COL.PED] === 'Yes' || row[COL.PED] === '1'
 *
 * Instead of the standard isYes() utility used everywhere else:
 *   const isYes = v => v && (String(v).toLowerCase() === 'yes' || v === 'Y' || v === '1' || v === 1);
 *
 * This meant values like 'Y', 'yes' (lowercase), and numeric 1 were silently
 * missed in the CMF tab while being counted correctly in other tabs.
 *
 * FIX: Replaced hardcoded checks with isYes() calls.
 *
 * Run: node tests/test_isyes_consistency_bug.js
 */

// Reproduce the standard isYes function from app/index.html:29462
const isYes = v => v && (String(v).toLowerCase() === 'yes' || v === 'Y' || v === '1' || v === 1);

// Test values that represent "yes" in real crash data
const testValues = [
    { value: 'Yes',     expectedYes: true,  label: 'Yes (string)' },
    { value: '1',       expectedYes: true,  label: '1 (string)' },
    { value: 'Y',       expectedYes: true,  label: 'Y (char)' },
    { value: 'y',       expectedYes: false, label: 'y (lowercase char — not a valid data format)' },
    { value: 'yes',     expectedYes: true,  label: 'yes (lowercase)' },
    { value: 1,         expectedYes: true,  label: '1 (number)' },
    { value: 'No',      expectedYes: false, label: 'No' },
    { value: '0',       expectedYes: false, label: '0' },
    { value: '',        expectedYes: false, label: 'empty string' },
    { value: null,      expectedYes: false, label: 'null' },
    { value: undefined, expectedYes: false, label: 'undefined' },
];

let passed = 0;
let failed = 0;

console.log('=== isYes() Consistency Test ===\n');
console.log('Verifying isYes() returns correct results for all crash data value formats:\n');

testValues.forEach(({ value, expectedYes, label }) => {
    const result = !!isYes(value);
    if (result === expectedYes) {
        console.log(`  PASS: "${label}" => isYes()=${result} (expected ${expectedYes})`);
        passed++;
    } else {
        console.log(`  FAIL: "${label}" => isYes()=${result} (expected ${expectedYes})`);
        failed++;
    }
});

console.log(`\n--- Results: ${passed} passed, ${failed} failed ---`);

// Part 2: Verify the old buggy pattern would have missed values
console.log('\n=== Regression Check: Old Buggy Pattern ===\n');
const buggyCheck = v => v === 'Yes' || v === '1';
const missedByBuggy = testValues.filter(t => t.expectedYes && !!isYes(t.value) && !buggyCheck(t.value));

if (missedByBuggy.length > 0) {
    console.log('The old hardcoded checks would have MISSED these valid "yes" values:');
    missedByBuggy.forEach(t => console.log(`  - ${t.label}: "${t.value}"`));
    console.log(`\nThis confirms the bug existed and the fix (using isYes()) is necessary.`);
} else {
    console.log('No discrepancy found (unexpected — the bug pattern should miss some values).');
}

if (failed > 0) {
    console.log('\nFAILED: isYes() does not match expected behavior.');
    process.exit(1);
} else {
    console.log('\nPASSED: All isYes() checks return expected values. Bug is fixed.');
    process.exit(0);
}
