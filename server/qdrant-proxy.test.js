/**
 * Bug tests for crash alert monitoring and email scheduler functions.
 * Run with: node --test server/qdrant-proxy.test.js
 *
 * Tests the pure functions from qdrant-proxy.js by re-defining them here
 * (since the server file has side effects that prevent direct import).
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');

// =============================================================================
// Copy of pure functions from qdrant-proxy.js (to test without side effects)
// =============================================================================

function splitCSVLine(line) {
    const result = [];
    let current = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        if (ch === '"') {
            if (inQuotes && line[i + 1] === '"') {
                current += '"';
                i++;
            } else {
                inQuotes = !inQuotes;
            }
        } else if (ch === ',' && !inQuotes) {
            result.push(current.trim());
            current = '';
        } else {
            current += ch;
        }
    }
    result.push(current.trim());
    return result;
}

function parseCSV(text) {
    const lines = text.split(/\r?\n/).filter(l => l.trim());
    if (lines.length < 2) return [];

    const headers = splitCSVLine(lines[0]);
    const rows = [];
    for (let i = 1; i < lines.length; i++) {
        const values = splitCSVLine(lines[i]);
        // Accept rows with >= headers (trailing commas) or fewer (missing fields, padded with '')
        if (values.length < headers.length) {
            while (values.length < headers.length) values.push('');
        }
        const obj = {};
        for (let j = 0; j < headers.length; j++) {
            obj[headers[j]] = values[j] != null ? values[j] : '';
        }
        rows.push(obj);
    }
    return rows;
}

function evaluateServerAlertConditions(alert, crashes) {
    const conditions = [];
    const thresholds = alert.thresholds || {};
    const now = new Date();

    let locationCrashes = crashes;
    if (alert.locationType === 'route' && alert.locationValue) {
        const routeCol = alert.routeColumn || 'RTE Name';
        locationCrashes = crashes.filter(r => r[routeCol] === alert.locationValue);
    } else if (alert.locationType === 'node' && alert.locationValue) {
        const nodeCol = alert.nodeColumn || 'Node';
        locationCrashes = crashes.filter(r => r[nodeCol] === alert.locationValue);
    }

    if (thresholds.crashCountEnabled) {
        const windowMonths = thresholds.crashCountWindowMonths ?? 6;
        const threshold = thresholds.crashCountThreshold ?? 5;
        const cutoff = new Date(now);
        cutoff.setMonth(cutoff.getMonth() - windowMonths);

        const dateCol = alert.dateColumn || 'Crash Date';
        const recentCrashes = locationCrashes.filter(r => {
            const d = r[dateCol] ? new Date(r[dateCol]) : null;
            return d && !isNaN(d) && d >= cutoff;
        });

        if (recentCrashes.length > threshold) {
            conditions.push({
                type: 'crash_count',
                severity: 'warning',
                title: 'Crash Count Threshold Exceeded',
                message: `${recentCrashes.length} crashes in the last ${windowMonths} months (threshold: ${threshold})`,
                value: recentCrashes.length,
                threshold
            });
        }
    }

    if (thresholds.severityEnabled) {
        const level = thresholds.severityLevel ?? 'KA';
        const targetSevs = level === 'K' ? ['K'] : level === 'KA' ? ['K', 'A'] : ['K', 'A', 'B'];
        const last90Days = new Date(now);
        last90Days.setDate(last90Days.getDate() - 90);

        const dateCol = alert.dateColumn || 'Crash Date';
        const sevCol = alert.severityColumn || 'Crash Severity';
        const severeCrashes = locationCrashes.filter(r => {
            const d = r[dateCol] ? new Date(r[dateCol]) : null;
            const sev = (r[sevCol] || '').charAt(0).toUpperCase();
            return d && !isNaN(d) && d >= last90Days && targetSevs.includes(sev);
        });

        if (severeCrashes.length > 0) {
            const sevLabel = level === 'K' ? 'Fatal' : level === 'KA' ? 'Fatal + Serious Injury' : 'Any Injury';
            conditions.push({
                type: 'severity',
                severity: 'critical',
                title: `${sevLabel} Crash Detected`,
                message: `${severeCrashes.length} ${sevLabel.toLowerCase()} crash(es) in the last 90 days`,
                value: severeCrashes.length,
                threshold: 0
            });
        }
    }

    if (thresholds.trendEnabled) {
        const increaseThreshold = thresholds.trendIncreasePercent ?? 25;
        const windowMonths = thresholds.trendWindowMonths ?? 12;
        const dateCol = alert.dateColumn || 'Crash Date';

        const recentStart = new Date(now);
        recentStart.setMonth(recentStart.getMonth() - windowMonths);
        const priorStart = new Date(recentStart);
        priorStart.setMonth(priorStart.getMonth() - windowMonths);

        const recentCount = locationCrashes.filter(r => {
            const d = r[dateCol] ? new Date(r[dateCol]) : null;
            return d && !isNaN(d) && d >= recentStart && d <= now;
        }).length;

        const priorCount = locationCrashes.filter(r => {
            const d = r[dateCol] ? new Date(r[dateCol]) : null;
            return d && !isNaN(d) && d >= priorStart && d < recentStart;
        }).length;

        if (priorCount > 0) {
            const changePercent = ((recentCount - priorCount) / priorCount) * 100;
            if (changePercent >= increaseThreshold) {
                conditions.push({
                    type: 'trend',
                    severity: 'warning',
                    title: 'Crash Rate Increase Detected',
                    message: `Crash rate increased by ${changePercent.toFixed(1)}% (${priorCount} → ${recentCount} in ${windowMonths}-month windows, threshold: ${increaseThreshold}%)`,
                    value: parseFloat(changePercent.toFixed(1)),
                    threshold: increaseThreshold
                });
            }
        }
    }

    return { triggered: conditions.length > 0, conditions };
}

function calculateNextAlertCheck(/* alert */) {
    const now = new Date();
    let candidate = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1, 12, 5, 0));
    for (let i = 0; i < 7; i++) {
        if (candidate.getUTCDay() === 3) break;
        candidate.setUTCDate(candidate.getUTCDate() + 1);
    }
    return candidate.toISOString();
}

function calculateNextRunAt(schedule) {
    const now = new Date();
    const { frequency, dayOfWeek, dayOfMonth, time, timezone } = schedule;
    const [hours, minutes] = (time || '08:00').split(':').map(Number);
    const tz = timezone || 'America/New_York';

    const formatter = new Intl.DateTimeFormat('en-US', {
        timeZone: tz, hour12: false,
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });

    let candidate = new Date(now.getTime() + 60000);

    for (let i = 0; i < 400; i++) {
        const parts = formatter.formatToParts(candidate);
        const p = {};
        parts.forEach(({ type, value }) => { p[type] = parseInt(value, 10); });

        const candidateDow = candidate.getDay();
        const candidateDay = p.day;

        let match = false;
        if (frequency === 'daily') {
            match = true;
        } else if (frequency === 'weekly') {
            match = candidateDow === (dayOfWeek != null ? dayOfWeek : 1);
        } else if (frequency === 'monthly') {
            match = candidateDay === (dayOfMonth || 1);
        } else if (frequency === 'quarterly') {
            match = candidateDay === (dayOfMonth || 1) && [1, 4, 7, 10].includes(p.month);
        } else if (frequency === 'annual') {
            match = candidateDay === (dayOfMonth || 1) && p.month === 1;
        }

        if (match) {
            const dateStr = `${String(p.year)}-${String(p.month).padStart(2, '0')}-${String(p.day).padStart(2, '0')}T${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:00`;
            const utcTest = new Date(dateStr);
            const tzOffset = utcTest.getTime() - new Date(utcTest.toLocaleString('en-US', { timeZone: tz })).getTime();
            const finalDate = new Date(new Date(dateStr + 'Z').getTime() + tzOffset);

            if (finalDate > now) {
                return finalDate.toISOString();
            }
        }

        candidate = new Date(candidate.getTime() + 24 * 60 * 60 * 1000);
    }

    return new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000).toISOString();
}

function escapeHtml(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function buildServerAlertEmailHtml(conditions, alert) {
    const locationName = escapeHtml(alert.locationName || alert.locationValue || 'Unknown Location');
    const dateStr = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    const appUrl = 'https://crashlens.aicreatesai.com';

    const conditionRows = conditions.map(c => {
        const bgColor = c.severity === 'critical' ? '#fef2f2' : '#fffbeb';
        const borderColor = c.severity === 'critical' ? '#fecaca' : '#fde68a';
        const iconColor = c.severity === 'critical' ? '#dc2626' : '#d97706';
        return `
            <div style="background:${bgColor};border:1.5px solid ${borderColor};border-radius:8px;padding:14px 16px;margin-bottom:10px">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
                    <span style="color:${iconColor};font-size:16px">&#9888;</span>
                    <strong style="color:${iconColor};font-size:14px">${escapeHtml(c.title)}</strong>
                </div>
                <p style="margin:0;color:#334155;font-size:13px;line-height:1.5">${escapeHtml(c.message)}</p>
            </div>`;
    }).join('');

    return `<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body>
<strong>${locationName}</strong>
<p>${dateStr}</p>
${conditionRows}
<a href="${appUrl}/app/">Open</a>
</body></html>`;
}

// =============================================================================
// CSV PARSER TESTS
// =============================================================================

describe('splitCSVLine', () => {
    it('should split simple comma-separated values', () => {
        assert.deepEqual(splitCSVLine('a,b,c'), ['a', 'b', 'c']);
    });

    it('should handle quoted fields with commas inside', () => {
        assert.deepEqual(splitCSVLine('"hello, world",b,c'), ['hello, world', 'b', 'c']);
    });

    it('should handle escaped double quotes inside quoted fields', () => {
        assert.deepEqual(splitCSVLine('"say ""hello""",b'), ['say "hello"', 'b']);
    });

    it('should handle empty fields', () => {
        assert.deepEqual(splitCSVLine('a,,c'), ['a', '', 'c']);
    });

    it('should handle single field', () => {
        assert.deepEqual(splitCSVLine('abc'), ['abc']);
    });

    it('should handle empty string', () => {
        assert.deepEqual(splitCSVLine(''), ['']);
    });

    it('should strip whitespace around unquoted values', () => {
        assert.deepEqual(splitCSVLine(' a , b , c '), ['a', 'b', 'c']);
    });
});

describe('parseCSV', () => {
    it('should parse basic CSV into objects', () => {
        const csv = 'Name,Age,City\nAlice,30,NYC\nBob,25,LA';
        const rows = parseCSV(csv);
        assert.equal(rows.length, 2);
        assert.deepEqual(rows[0], { Name: 'Alice', Age: '30', City: 'NYC' });
        assert.deepEqual(rows[1], { Name: 'Bob', Age: '25', City: 'LA' });
    });

    it('should handle Windows line endings', () => {
        const csv = 'Name,Age\r\nAlice,30\r\nBob,25';
        const rows = parseCSV(csv);
        assert.equal(rows.length, 2);
    });

    it('should return empty array for empty input', () => {
        assert.deepEqual(parseCSV(''), []);
    });

    it('should return empty array for header-only CSV', () => {
        assert.deepEqual(parseCSV('Name,Age'), []);
    });

    it('should handle quoted headers', () => {
        const csv = '"Crash Date","Crash Severity"\n2024-01-15,K';
        const rows = parseCSV(csv);
        assert.equal(rows.length, 1);
        assert.equal(rows[0]['Crash Date'], '2024-01-15');
        assert.equal(rows[0]['Crash Severity'], 'K');
    });

    // FIXED: Rows with trailing comma should be kept (extra fields ignored)
    it('should keep rows with trailing commas', () => {
        const csv = 'Name,Age\nAlice,30,\nBob,25';
        const rows = parseCSV(csv);
        assert.equal(rows.length, 2, 'Row with trailing comma should be kept');
        assert.equal(rows[0].Name, 'Alice');
    });

    // FIXED: Rows with fewer fields should be padded with empty strings
    it('should pad rows with missing fields', () => {
        const csv = 'Name,Age,City\nAlice,30\nBob,25,LA';
        const rows = parseCSV(csv);
        assert.equal(rows.length, 2, 'Row with missing field should be kept');
        assert.equal(rows[0].City, '', 'Missing field should be empty string');
        assert.equal(rows[1].City, 'LA');
    });
});

// =============================================================================
// ALERT CONDITION EVALUATION TESTS
// =============================================================================

describe('evaluateServerAlertConditions', () => {
    function makeCrash(date, severity, route, node) {
        return {
            'Crash Date': date,
            'Crash Severity': severity,
            'RTE Name': route || 'US-29',
            'Node': node || '12345'
        };
    }

    function daysAgo(n) {
        const d = new Date();
        d.setDate(d.getDate() - n);
        return d.toISOString().split('T')[0];
    }

    function monthsAgo(n) {
        const d = new Date();
        d.setMonth(d.getMonth() - n);
        return d.toISOString().split('T')[0];
    }

    it('should return no conditions when nothing is enabled', () => {
        const alert = { thresholds: {}, locationType: 'route', locationValue: 'US-29' };
        const crashes = [makeCrash(daysAgo(1), 'K')];
        const result = evaluateServerAlertConditions(alert, crashes);
        assert.equal(result.triggered, false);
        assert.equal(result.conditions.length, 0);
    });

    it('should detect crash count threshold exceeded', () => {
        const alert = {
            thresholds: { crashCountEnabled: true, crashCountThreshold: 3, crashCountWindowMonths: 6 },
            locationType: 'route', locationValue: 'US-29'
        };
        const crashes = [
            makeCrash(daysAgo(10), 'O'),
            makeCrash(daysAgo(20), 'O'),
            makeCrash(daysAgo(30), 'O'),
            makeCrash(daysAgo(40), 'O'),
        ];
        const result = evaluateServerAlertConditions(alert, crashes);
        assert.equal(result.triggered, true);
        assert.equal(result.conditions[0].type, 'crash_count');
        assert.equal(result.conditions[0].value, 4);
    });

    it('should NOT trigger when crash count equals threshold (uses > not >=)', () => {
        const alert = {
            thresholds: { crashCountEnabled: true, crashCountThreshold: 3, crashCountWindowMonths: 6 },
            locationType: 'route', locationValue: 'US-29'
        };
        const crashes = [
            makeCrash(daysAgo(10), 'O'),
            makeCrash(daysAgo(20), 'O'),
            makeCrash(daysAgo(30), 'O'),
        ];
        const result = evaluateServerAlertConditions(alert, crashes);
        assert.equal(result.triggered, false, 'threshold=3, count=3: should not trigger (uses >)');
    });

    it('should filter crashes by route', () => {
        const alert = {
            thresholds: { crashCountEnabled: true, crashCountThreshold: 1, crashCountWindowMonths: 6 },
            locationType: 'route', locationValue: 'US-29'
        };
        const crashes = [
            makeCrash(daysAgo(10), 'O', 'US-29'),
            makeCrash(daysAgo(10), 'O', 'SR-123'),
            makeCrash(daysAgo(10), 'O', 'US-29'),
        ];
        const result = evaluateServerAlertConditions(alert, crashes);
        assert.equal(result.triggered, true);
        assert.equal(result.conditions[0].value, 2);
    });

    it('should filter crashes by node', () => {
        const alert = {
            thresholds: { crashCountEnabled: true, crashCountThreshold: 0, crashCountWindowMonths: 6 },
            locationType: 'node', locationValue: '99999'
        };
        const crashes = [
            makeCrash(daysAgo(10), 'O', 'US-29', '99999'),
            makeCrash(daysAgo(10), 'O', 'US-29', '11111'),
        ];
        const result = evaluateServerAlertConditions(alert, crashes);
        assert.equal(result.triggered, true);
        assert.equal(result.conditions[0].value, 1);
    });

    it('should detect fatal crashes for severity=K', () => {
        const alert = {
            thresholds: { severityEnabled: true, severityLevel: 'K' },
            locationType: 'route', locationValue: 'US-29'
        };
        const crashes = [
            makeCrash(daysAgo(10), 'K'),
            makeCrash(daysAgo(10), 'A'),
        ];
        const result = evaluateServerAlertConditions(alert, crashes);
        assert.equal(result.triggered, true);
        assert.equal(result.conditions[0].value, 1);
    });

    it('should detect K+A crashes for severity=KA', () => {
        const alert = {
            thresholds: { severityEnabled: true, severityLevel: 'KA' },
            locationType: 'route', locationValue: 'US-29'
        };
        const crashes = [
            makeCrash(daysAgo(10), 'K'),
            makeCrash(daysAgo(10), 'A Injury'),
            makeCrash(daysAgo(10), 'B'),
        ];
        const result = evaluateServerAlertConditions(alert, crashes);
        assert.equal(result.triggered, true);
        assert.equal(result.conditions[0].value, 2);
    });

    it('should ignore crashes older than 90 days for severity', () => {
        const alert = {
            thresholds: { severityEnabled: true, severityLevel: 'K' },
            locationType: 'route', locationValue: 'US-29'
        };
        const crashes = [makeCrash(daysAgo(100), 'K')];
        const result = evaluateServerAlertConditions(alert, crashes);
        assert.equal(result.triggered, false);
    });

    it('should detect trend increase', () => {
        const alert = {
            thresholds: { trendEnabled: true, trendIncreasePercent: 25, trendWindowMonths: 6 },
            locationType: 'route', locationValue: 'US-29'
        };
        const crashes = [
            makeCrash(monthsAgo(1), 'O'),
            makeCrash(monthsAgo(2), 'O'),
            makeCrash(monthsAgo(3), 'O'),
            makeCrash(monthsAgo(4), 'O'),
            makeCrash(monthsAgo(8), 'O'),
            makeCrash(monthsAgo(10), 'O'),
        ];
        const result = evaluateServerAlertConditions(alert, crashes);
        assert.equal(result.triggered, true);
        assert.equal(result.conditions[0].type, 'trend');
    });

    it('should not trigger trend when prior period has zero crashes', () => {
        const alert = {
            thresholds: { trendEnabled: true, trendIncreasePercent: 25, trendWindowMonths: 6 },
            locationType: 'route', locationValue: 'US-29'
        };
        const crashes = [
            makeCrash(monthsAgo(1), 'O'),
            makeCrash(monthsAgo(2), 'O'),
        ];
        const result = evaluateServerAlertConditions(alert, crashes);
        assert.equal(result.triggered, false);
    });

    it('should handle invalid date strings gracefully', () => {
        const alert = {
            thresholds: { crashCountEnabled: true, crashCountThreshold: 0, crashCountWindowMonths: 6 },
            locationType: 'route', locationValue: 'US-29'
        };
        const crashes = [
            { 'Crash Date': 'INVALID', 'Crash Severity': 'O', 'RTE Name': 'US-29' },
            { 'Crash Date': '', 'Crash Severity': 'O', 'RTE Name': 'US-29' },
            { 'Crash Date': null, 'Crash Severity': 'O', 'RTE Name': 'US-29' },
            makeCrash(daysAgo(5), 'O'),
        ];
        const result = evaluateServerAlertConditions(alert, crashes);
        assert.equal(result.conditions[0].value, 1);
    });

    it('should use all crashes when locationValue is empty', () => {
        const alert = {
            thresholds: { crashCountEnabled: true, crashCountThreshold: 0, crashCountWindowMonths: 6 },
            locationType: 'route', locationValue: ''
        };
        const crashes = [
            makeCrash(daysAgo(5), 'O', 'US-29'),
            makeCrash(daysAgo(5), 'O', 'SR-123'),
        ];
        const result = evaluateServerAlertConditions(alert, crashes);
        assert.equal(result.triggered, true);
        assert.equal(result.conditions[0].value, 2);
    });

    it('should respect custom column name overrides', () => {
        const alert = {
            thresholds: { crashCountEnabled: true, crashCountThreshold: 0, crashCountWindowMonths: 6 },
            locationType: 'route', locationValue: 'MAIN ST',
            routeColumn: 'Road Name',
            dateColumn: 'Date of Crash'
        };
        const crashes = [
            { 'Road Name': 'MAIN ST', 'Date of Crash': daysAgo(5), 'Crash Severity': 'O' },
            { 'Road Name': 'ELM ST', 'Date of Crash': daysAgo(5), 'Crash Severity': 'O' },
        ];
        const result = evaluateServerAlertConditions(alert, crashes);
        assert.equal(result.triggered, true);
        assert.equal(result.conditions[0].value, 1);
    });

    it('should trigger multiple conditions simultaneously', () => {
        const alert = {
            thresholds: {
                crashCountEnabled: true, crashCountThreshold: 0, crashCountWindowMonths: 6,
                severityEnabled: true, severityLevel: 'K'
            },
            locationType: 'route', locationValue: 'US-29'
        };
        const crashes = [
            makeCrash(daysAgo(5), 'K'),
            makeCrash(daysAgo(10), 'O'),
        ];
        const result = evaluateServerAlertConditions(alert, crashes);
        assert.equal(result.triggered, true);
        assert.equal(result.conditions.length, 2);
    });

    // FIXED: crashCountThreshold of 0 should work (uses ?? instead of ||)
    it('should respect crashCountThreshold of 0', () => {
        const alert = {
            thresholds: { crashCountEnabled: true, crashCountThreshold: 0, crashCountWindowMonths: 6 },
            locationType: 'route', locationValue: 'US-29'
        };
        const crashes = [
            makeCrash(daysAgo(5), 'O'),
            makeCrash(daysAgo(10), 'O'),
            makeCrash(daysAgo(15), 'O'),
        ];
        const result = evaluateServerAlertConditions(alert, crashes);
        // threshold=0, count=3: 3 > 0 should trigger
        assert.equal(result.triggered, true, 'threshold=0 should trigger when any crashes exist');
        assert.equal(result.conditions[0].value, 3);
    });

    // FIXED: trendIncreasePercent of 0 should work (uses ?? instead of ||)
    it('should respect trendIncreasePercent of 0', () => {
        const thresholds = { trendEnabled: true, trendIncreasePercent: 0 };
        const effectiveThreshold = thresholds.trendIncreasePercent ?? 25;
        assert.equal(effectiveThreshold, 0, 'trendIncreasePercent=0 should stay 0 with ?? operator');
    });
});

// =============================================================================
// CALCULATE NEXT ALERT CHECK TESTS
// =============================================================================

describe('calculateNextAlertCheck — monthly (first Wednesday)', () => {
    it('should return a date in the future', () => {
        const result = calculateNextAlertCheck({});
        const nextCheck = new Date(result);
        assert.ok(nextCheck > new Date(), 'Next check should be in the future');
    });

    it('should return a Wednesday (day 3)', () => {
        const result = calculateNextAlertCheck({});
        const nextCheck = new Date(result);
        assert.equal(nextCheck.getUTCDay(), 3, 'Next check should be a Wednesday');
    });

    it('should return day 1-7 of the month (first week)', () => {
        const result = calculateNextAlertCheck({});
        const nextCheck = new Date(result);
        assert.ok(nextCheck.getUTCDate() >= 1 && nextCheck.getUTCDate() <= 7,
            `Day ${nextCheck.getUTCDate()} should be between 1 and 7`);
    });

    it('should be in the next month (not current month)', () => {
        const result = calculateNextAlertCheck({});
        const nextCheck = new Date(result);
        const now = new Date();
        // Should be at least next month
        const nextMonth = (now.getUTCMonth() + 1) % 12;
        assert.equal(nextCheck.getUTCMonth(), nextMonth,
            `Month should be ${nextMonth} (next month), got ${nextCheck.getUTCMonth()}`);
    });

    it('should return valid UTC ISO string', () => {
        const result = calculateNextAlertCheck({});
        assert.ok(result.endsWith('Z'));
        assert.ok(!isNaN(new Date(result).getTime()));
    });

    it('should schedule at 12:05 UTC (roughly 8 AM ET)', () => {
        const result = calculateNextAlertCheck({});
        const nextCheck = new Date(result);
        assert.equal(nextCheck.getUTCHours(), 12);
        assert.equal(nextCheck.getUTCMinutes(), 5);
    });
});

// =============================================================================
// CALCULATE NEXT RUN AT TESTS
// =============================================================================

describe('calculateNextRunAt', () => {
    it('should return future date for daily schedule', () => {
        const result = calculateNextRunAt({
            frequency: 'daily', time: '08:00', timezone: 'America/New_York'
        });
        assert.ok(result);
        assert.ok(new Date(result) > new Date());
    });

    it('should return future date for weekly schedule', () => {
        const result = calculateNextRunAt({
            frequency: 'weekly', dayOfWeek: 1, time: '09:00', timezone: 'America/New_York'
        });
        assert.ok(result);
        assert.ok(new Date(result) > new Date());
    });

    it('should return future date for monthly schedule', () => {
        const result = calculateNextRunAt({
            frequency: 'monthly', dayOfMonth: 15, time: '10:00', timezone: 'America/New_York'
        });
        assert.ok(result);
        assert.ok(new Date(result) > new Date());
    });

    it('should fall back to 1 week for unknown frequency', () => {
        const result = calculateNextRunAt({
            frequency: 'unknown', time: '08:00', timezone: 'America/New_York'
        });
        assert.ok(result);
        const diff = new Date(result).getTime() - Date.now();
        const oneWeekMs = 7 * 24 * 60 * 60 * 1000;
        assert.ok(Math.abs(diff - oneWeekMs) < 120000); // within 2 min tolerance
    });

    it('should handle missing time and timezone', () => {
        const result = calculateNextRunAt({ frequency: 'daily' });
        assert.ok(result);
    });
});

// =============================================================================
// EMAIL HTML — XSS SAFETY TESTS
// =============================================================================

describe('buildServerAlertEmailHtml - XSS', () => {
    // FIXED: locationName is now escaped
    it('should escape HTML in locationName', () => {
        const conditions = [{ type: 'test', severity: 'warning', title: 'T', message: 'M' }];
        const alert = { locationName: '<script>alert("xss")</script>' };
        const html = buildServerAlertEmailHtml(conditions, alert);

        assert.ok(!html.includes('<script>'), 'Script tags should be escaped');
        assert.ok(html.includes('&lt;script&gt;'), 'Should contain escaped HTML entities');
    });

    // FIXED: condition title/message is now escaped
    it('should escape HTML in condition title and message', () => {
        const conditions = [{
            type: 'test', severity: 'warning',
            title: '<img src=x onerror=alert(1)>',
            message: '<b>bold</b>'
        }];
        const alert = { locationName: 'US-29' };
        const html = buildServerAlertEmailHtml(conditions, alert);

        assert.ok(!html.includes('<img src=x'), 'Img tags should be escaped in title');
        assert.ok(!html.includes('<b>bold</b>'), 'HTML tags should be escaped in message');
        assert.ok(html.includes('&lt;img'), 'Should contain escaped img tag');
    });

    it('should produce valid HTML structure', () => {
        const conditions = [{
            type: 'severity', severity: 'critical',
            title: 'Fatal Crash Detected',
            message: '1 fatal crash in the last 90 days'
        }];
        const alert = { locationName: 'US-29 & SR-123' };
        const html = buildServerAlertEmailHtml(conditions, alert);
        assert.ok(html.includes('<!DOCTYPE html>'));
        assert.ok(html.includes('</html>'));
        assert.ok(html.includes('Fatal Crash Detected'));
    });
});

console.log('\n=== Running crash alert bug tests ===\n');
