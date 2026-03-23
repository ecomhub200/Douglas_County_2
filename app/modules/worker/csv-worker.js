/**
 * CrashLens CSV Web Worker
 * Parses CSV data off the main thread, computes aggregates and mapPoints.
 * Keeps UI responsive during large dataset loading (1M+ rows).
 *
 * Messages IN:
 *   { type: 'parse', csvText, colMapping }
 *
 * Messages OUT:
 *   { type: 'progress', rows: number }
 *   { type: 'mapPointsChunk', points: array, chunkIndex: number }
 *   { type: 'complete', aggregates, totalRows, mapPointCount, years, routes, nodes, missingGPS, minDate, maxDate }
 *   { type: 'error', message: string }
 *
 * MapPoints are sent in chunks of 50k to avoid main-thread freeze from
 * deserializing 1M+ objects in a single structured clone.
 */

/* global importScripts, Papa */
importScripts('https://cdnjs.cloudflare.com/ajax/libs/PapaParse/5.4.1/papaparse.min.js');

// ── Constants ──

var MAP_POINTS_CHUNK_SIZE = 50000; // Send mapPoints in 50k batches

// ── Helpers (replicated from main thread for worker isolation) ──

function isYes(v) {
    return v && (String(v).toLowerCase() === 'yes' || v === 'Y' || v === '1' || v === 1);
}

function getHour(t) {
    if (!t) return null;
    return parseInt(String(t).padStart(4, '0').slice(0, 2), 10);
}

function isIntersection(row) {
    var intAnalysis = (row['Intersection Analysis'] || '').toLowerCase();
    if (intAnalysis !== '' && !intAnalysis.includes('not intersection')) return true;
    var intType = row['Intersection Type'] || '';
    return intType !== '' && !intType.toLowerCase().includes('not at intersection') && !intType.startsWith('0.');
}

function parseCrashDateToTimestamp(dateStr) {
    if (!dateStr) return null;
    var numVal = Number(dateStr);
    if (!isNaN(numVal) && numVal > 946684800000) return numVal;
    var d = new Date(dateStr);
    if (!isNaN(d.getTime())) return d.getTime();
    return null;
}

// ── Aggregate initialization (mirrors resetState() structure) ──

function initAggregates() {
    return {
        byYear: {},
        bySeverity: { K: 0, A: 0, B: 0, C: 0, O: 0 },
        byCollision: {},
        byWeather: {},
        byLight: {},
        byRoute: {},
        byNode: {},
        byHour: {},
        byDOW: {},
        byMonth: {},
        byFuncClass: {},
        byIntType: {},
        byTrafficCtrl: {},
        ped: { total: 0, K: 0, A: 0, B: 0, C: 0, O: 0, byYear: {}, byLight: {}, byRoute: {} },
        bike: { total: 0, K: 0, A: 0, B: 0, C: 0, O: 0, byYear: {}, byLight: {}, byRoute: {} },
        speed: { total: 0, K: 0, A: 0, B: 0, C: 0, O: 0, byYear: {} },
        nighttime: { total: 0, K: 0, A: 0, B: 0, C: 0, O: 0, byYear: {} },
        intersection: { total: 0, K: 0, A: 0, B: 0, C: 0, O: 0 },
        nonIntersection: { total: 0, K: 0, A: 0, B: 0, C: 0, O: 0 },
        personsInjured: 0,
        vehicleCount: {
            total: 0, sum: 0,
            bySeverity: {
                K: { count: 0, sum: 0 }, A: { count: 0, sum: 0 },
                B: { count: 0, sum: 0 }, C: { count: 0, sum: 0 },
                O: { count: 0, sum: 0 }
            }
        },
        pedCasualties: { killed: 0, injured: 0, byYear: {} }
    };
}

// ── Row processing (mirrors processRow() from app/index.html) ──
// Uses _routeSets object for O(1) route dedup per node (converted to arrays before postMessage)

var _routeSets = {}; // node -> {routeName: true} for O(1) dedup

function processRowForAggregates(row, agg, COL, mapPoints, missingGPSRef) {
    var year = parseInt(row[COL.YEAR]) || null;

    // Convert date string to timestamp
    if (row[COL.DATE] && typeof row[COL.DATE] === 'string') {
        var ts = parseCrashDateToTimestamp(row[COL.DATE]);
        if (ts) row[COL.DATE] = ts;
    }

    var sev = (row[COL.SEVERITY] || '').trim().toUpperCase().charAt(0);
    var collision = (row[COL.COLLISION] || '').trim() || 'Unknown';
    var weather = (row[COL.WEATHER] || '').trim() || 'Unknown';
    var light = (row[COL.LIGHT] || '').trim() || 'Unknown';
    var route = row[COL.ROUTE] || 'Unknown';
    var node = row[COL.NODE] || '';
    var hour = getHour(row[COL.TIME]);
    var isPed = isYes(row[COL.PED]);
    var isBike = isYes(row[COL.BIKE]);
    var isInt = isIntersection(row);
    var funcClass = row[COL.FUNC_CLASS] || 'Unknown';
    var intType = row[COL.INT_TYPE] || '';
    var trafficCtrl = row[COL.TRAFFIC_CTRL] || '';

    // By year
    if (year) {
        if (!agg.byYear[year]) agg.byYear[year] = { total: 0, K: 0, A: 0, B: 0, C: 0, O: 0, ped: 0, bike: 0, speed: 0, nighttime: 0 };
        agg.byYear[year].total++;
        if (sev && agg.byYear[year][sev] !== undefined) agg.byYear[year][sev]++;
        if (isPed) agg.byYear[year].ped++;
        if (isBike) agg.byYear[year].bike++;
    }

    // By severity
    if (sev && agg.bySeverity[sev] !== undefined) agg.bySeverity[sev]++;

    // By collision type
    agg.byCollision[collision] = (agg.byCollision[collision] || 0) + 1;

    // By weather
    agg.byWeather[weather] = (agg.byWeather[weather] || 0) + 1;

    // By light
    agg.byLight[light] = (agg.byLight[light] || 0) + 1;

    // By route
    if (route !== 'Unknown') {
        if (!agg.byRoute[route]) agg.byRoute[route] = { total: 0, K: 0, A: 0, B: 0, C: 0, O: 0, collisions: {}, ped: 0, bike: 0, byYear: {} };
        agg.byRoute[route].total++;
        if (sev) agg.byRoute[route][sev]++;
        agg.byRoute[route].collisions[collision] = (agg.byRoute[route].collisions[collision] || 0) + 1;
        if (isPed) agg.byRoute[route].ped++;
        if (isBike) agg.byRoute[route].bike++;

        if (year) {
            if (!agg.byRoute[route].byYear[year]) agg.byRoute[route].byYear[year] = { total: 0, K: 0, A: 0, B: 0, C: 0, O: 0, ped: 0, bike: 0 };
            agg.byRoute[route].byYear[year].total++;
            if (sev) agg.byRoute[route].byYear[year][sev]++;
            if (isPed) agg.byRoute[route].byYear[year].ped++;
            if (isBike) agg.byRoute[route].byYear[year].bike++;
        }
    }

    // By node (intersection) — O(1) route dedup via _routeSets object lookup
    if (node) {
        if (!agg.byNode[node]) {
            agg.byNode[node] = { total: 0, K: 0, A: 0, B: 0, C: 0, O: 0, routes: [], ctrl: trafficCtrl };
            _routeSets[node] = {};
        }
        agg.byNode[node].total++;
        if (sev) agg.byNode[node][sev]++;
        if (route && !_routeSets[node][route]) {
            _routeSets[node][route] = true;
            agg.byNode[node].routes.push(route);
        }
    }

    // By hour, DOW, month
    if (hour !== null) agg.byHour[hour] = (agg.byHour[hour] || 0) + 1;
    if (row[COL.DATE]) {
        var d = new Date(Number(row[COL.DATE]));
        if (!isNaN(d)) {
            agg.byDOW[d.getDay()] = (agg.byDOW[d.getDay()] || 0) + 1;
            agg.byMonth[d.getMonth()] = (agg.byMonth[d.getMonth()] || 0) + 1;
        }
    }

    // By functional class
    agg.byFuncClass[funcClass] = agg.byFuncClass[funcClass] || { total: 0, K: 0, A: 0, B: 0, C: 0, O: 0 };
    agg.byFuncClass[funcClass].total++;
    if (sev) agg.byFuncClass[funcClass][sev]++;

    // By intersection type
    if (intType) {
        agg.byIntType[intType] = agg.byIntType[intType] || { total: 0, K: 0, A: 0 };
        agg.byIntType[intType].total++;
        if (sev === 'K') agg.byIntType[intType].K++;
        if (sev === 'A') agg.byIntType[intType].A++;
    }

    // By traffic control
    if (trafficCtrl) {
        agg.byTrafficCtrl[trafficCtrl] = (agg.byTrafficCtrl[trafficCtrl] || 0) + 1;
    }

    // Intersection vs non-intersection
    if (isInt) {
        agg.intersection.total++;
        if (sev && agg.intersection[sev] !== undefined) agg.intersection[sev]++;
    } else {
        agg.nonIntersection.total++;
        if (sev && agg.nonIntersection[sev] !== undefined) agg.nonIntersection[sev]++;
    }

    // Pedestrian
    if (isPed) {
        agg.ped.total++;
        if (sev && agg.ped[sev] !== undefined) agg.ped[sev]++;
        if (year) agg.ped.byYear[year] = (agg.ped.byYear[year] || 0) + 1;
        agg.ped.byLight[light] = (agg.ped.byLight[light] || 0) + 1;
        if (route !== 'Unknown') agg.ped.byRoute[route] = (agg.ped.byRoute[route] || 0) + 1;
    }

    // Bicycle
    if (isBike) {
        agg.bike.total++;
        if (sev && agg.bike[sev] !== undefined) agg.bike[sev]++;
        if (year) agg.bike.byYear[year] = (agg.bike.byYear[year] || 0) + 1;
        agg.bike.byLight[light] = (agg.bike.byLight[light] || 0) + 1;
        if (route !== 'Unknown') agg.bike.byRoute[route] = (agg.bike.byRoute[route] || 0) + 1;
    }

    // Speed-related
    var isSpeed = isYes(row[COL.SPEED]);
    if (isSpeed) {
        agg.speed.total++;
        if (sev && agg.speed[sev] !== undefined) agg.speed[sev]++;
        if (year) {
            agg.speed.byYear[year] = (agg.speed.byYear[year] || 0) + 1;
            if (agg.byYear[year]) agg.byYear[year].speed = (agg.byYear[year].speed || 0) + 1;
        }
    }

    // Nighttime
    var isNight = isYes(row[COL.NIGHT]);
    if (isNight) {
        agg.nighttime.total++;
        if (sev && agg.nighttime[sev] !== undefined) agg.nighttime[sev]++;
        if (year) {
            agg.nighttime.byYear[year] = (agg.nighttime.byYear[year] || 0) + 1;
            if (agg.byYear[year]) agg.byYear[year].nighttime = (agg.byYear[year].nighttime || 0) + 1;
        }
    }

    // Persons injured & vehicle count
    var personsInjuredVal = parseInt(row[COL.PERSONS_INJURED]) || 0;
    if (personsInjuredVal > 0) agg.personsInjured += personsInjuredVal;

    var vehicleCountVal = parseInt(row[COL.VEHICLE_COUNT]) || 0;
    if (vehicleCountVal > 0) {
        agg.vehicleCount.total++;
        agg.vehicleCount.sum += vehicleCountVal;
        if (sev && agg.vehicleCount.bySeverity[sev]) {
            agg.vehicleCount.bySeverity[sev].count++;
            agg.vehicleCount.bySeverity[sev].sum += vehicleCountVal;
        }
    }

    // Pedestrian casualties
    var pedKilledVal = parseInt(row[COL.PED_KILLED]) || 0;
    var pedInjuredVal = parseInt(row[COL.PED_INJURED]) || 0;
    if (pedKilledVal > 0 || pedInjuredVal > 0) {
        agg.pedCasualties.killed += pedKilledVal;
        agg.pedCasualties.injured += pedInjuredVal;
        if (year) {
            if (!agg.pedCasualties.byYear[year]) agg.pedCasualties.byYear[year] = { killed: 0, injured: 0 };
            agg.pedCasualties.byYear[year].killed += pedKilledVal;
            agg.pedCasualties.byYear[year].injured += pedInjuredVal;
        }
    }

    // Extract map point if coordinates exist (COL.X = longitude, COL.Y = latitude)
    var x = parseFloat(row[COL.X]);
    var y = parseFloat(row[COL.Y]);
    if (!isNaN(x) && !isNaN(y) && x !== 0 && y !== 0) {
        mapPoints.push({
            lat: y, lng: x, sev: sev, route: route, node: node, collision: collision,
            date: row[COL.DATE], time: row[COL.TIME],
            isPed: isPed, isBike: isBike, isInt: isInt, weather: weather, light: light,
            isSpeed: isSpeed,
            isYoung: isYes(row[COL.YOUNG]),
            isNight: isNight,
            docNum: row[COL.ID] || ''
        });
    } else {
        missingGPSRef.count++;
    }
}

// ── Send mapPoints in chunks to avoid main-thread freeze from structured clone ──

function flushMapPointChunks(mapPoints) {
    var chunkIndex = 0;
    for (var i = 0; i < mapPoints.length; i += MAP_POINTS_CHUNK_SIZE) {
        var chunk = mapPoints.slice(i, i + MAP_POINTS_CHUNK_SIZE);
        self.postMessage({
            type: 'mapPointsChunk',
            points: chunk,
            chunkIndex: chunkIndex
        });
        chunkIndex++;
    }
    return chunkIndex; // total chunks sent
}

// ── Main message handler ──

self.onmessage = function(e) {
    var data = e.data;

    if (data.type !== 'parse') {
        self.postMessage({ type: 'error', message: 'Unknown message type: ' + data.type });
        return;
    }

    var csvText = data.csvText;
    var COL = data.colMapping;

    if (!csvText || !COL) {
        self.postMessage({ type: 'error', message: 'Missing csvText or colMapping' });
        return;
    }

    // Reset route dedup sets
    _routeSets = {};

    var agg = initAggregates();
    var mapPoints = [];
    var missingGPSRef = { count: 0 };
    var totalRows = 0;
    var minDate = Infinity;
    var maxDate = -Infinity;
    var lastProgressUpdate = Date.now();

    try {
        Papa.parse(csvText, {
            header: true,
            skipEmptyLines: true,
            chunkSize: 1024 * 1024 * 5, // 5MB chunks for better throughput on large files
            chunk: function(results) {
                results.data.forEach(function(row) {
                    try {
                        processRowForAggregates(row, agg, COL, mapPoints, missingGPSRef);
                        totalRows++;

                        // Track min/max dates
                        var dateVal = Number(row[COL.DATE]);
                        if (!isNaN(dateVal) && dateVal > 946684800000) {
                            if (dateVal < minDate) minDate = dateVal;
                            if (dateVal > maxDate) maxDate = dateVal;
                        }
                    } catch (err) {
                        // Skip malformed rows
                    }
                });

                // Send progress updates every 200ms
                var now = Date.now();
                if (now - lastProgressUpdate > 200) {
                    self.postMessage({ type: 'progress', rows: totalRows });
                    lastProgressUpdate = now;
                }
            },
            complete: function() {
                // Free route dedup memory
                _routeSets = {};

                // Derive years, routes, nodes from aggregates
                var years = Object.keys(agg.byYear).map(Number).sort(function(a, b) { return a - b; });
                var routes = Object.keys(agg.byRoute).filter(function(r) { return r !== 'Unknown'; }).sort();
                var nodes = Object.keys(agg.byNode).sort();

                // Send mapPoints in chunks (50k each) to avoid main-thread freeze
                var chunkCount = flushMapPointChunks(mapPoints);

                // Send completion (aggregates are small — safe as single message)
                self.postMessage({
                    type: 'complete',
                    aggregates: agg,
                    totalRows: totalRows,
                    mapPointCount: mapPoints.length,
                    mapPointChunks: chunkCount,
                    missingGPS: missingGPSRef.count,
                    years: years,
                    routes: routes,
                    nodes: nodes,
                    minDate: minDate === Infinity ? null : minDate,
                    maxDate: maxDate === -Infinity ? null : maxDate
                });

                // Free mapPoints memory in Worker
                mapPoints = null;
            },
            error: function(err) {
                self.postMessage({ type: 'error', message: 'CSV parse error: ' + err.message });
            }
        });
    } catch (err) {
        self.postMessage({ type: 'error', message: 'Worker error: ' + err.message });
    }
};
