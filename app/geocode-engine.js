/**
 * CRASH LENS — GPS Coordinate Recovery Engine
 *
 * Three-strategy pipeline for recovering missing GPS coordinates:
 *   Strategy 1: Node Lookup (instant, in-memory)
 *   Strategy 2: OSM Nominatim Geocoding (1 req/sec, deduplicated, cached)
 *   Strategy 3: Milepost Interpolation (instant, in-memory)
 *
 * After recovery, corrected data can be saved back to R2 cloud storage.
 *
 * Dependencies (from index.html globals):
 *   - crashState, geocodeState, validationState, COL
 *   - isYes(), isIntersection(), getMapCoordinateBounds()
 *   - showToast(), updateMapDisplay(), crashMap
 *   - _getActiveStateKey(), getActiveJurisdictionId(), getActiveRoadTypeSuffix()
 *   - appConfig
 */

// ============================================================
// IndexedDB Cache — Persists Nominatim results for 90 days
// ============================================================

const GEOCODE_CACHE_CONSTANTS = {
    DB_NAME: 'CrashLensGeocodeCache',
    DB_VERSION: 1,
    STORE_NAME: 'geocodedLocations',
    CACHE_DAYS: 90
};

function geocodeCacheOpen() {
    return new Promise((resolve, reject) => {
        if (geocodeState._db) { resolve(geocodeState._db); return; }
        const request = indexedDB.open(GEOCODE_CACHE_CONSTANTS.DB_NAME, GEOCODE_CACHE_CONSTANTS.DB_VERSION);
        request.onerror = () => reject(request.error);
        request.onsuccess = () => { geocodeState._db = request.result; resolve(request.result); };
        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains(GEOCODE_CACHE_CONSTANTS.STORE_NAME)) {
                const store = db.createObjectStore(GEOCODE_CACHE_CONSTANTS.STORE_NAME, { keyPath: 'locationKey' });
                store.createIndex('cachedAt', 'cachedAt', { unique: false });
            }
        };
    });
}

async function geocodeCacheLoad(locationKey) {
    try {
        const db = await geocodeCacheOpen();
        return new Promise((resolve) => {
            const tx = db.transaction(GEOCODE_CACHE_CONSTANTS.STORE_NAME, 'readonly');
            const store = tx.objectStore(GEOCODE_CACHE_CONSTANTS.STORE_NAME);
            const req = store.get(locationKey);
            req.onsuccess = () => resolve(req.result || null);
            req.onerror = () => resolve(null);
        });
    } catch (e) { return null; }
}

async function geocodeCacheSave(locationKey, result) {
    try {
        const db = await geocodeCacheOpen();
        return new Promise((resolve) => {
            const tx = db.transaction(GEOCODE_CACHE_CONSTANTS.STORE_NAME, 'readwrite');
            const store = tx.objectStore(GEOCODE_CACHE_CONSTANTS.STORE_NAME);
            store.put({ ...result, locationKey, cachedAt: Date.now() });
            tx.oncomplete = () => resolve(true);
            tx.onerror = () => resolve(false);
        });
    } catch (e) { return false; }
}

function geocodeCacheExpired(cached) {
    if (!cached?.cachedAt) return true;
    return (Date.now() - cached.cachedAt) / (1000 * 60 * 60 * 24) > GEOCODE_CACHE_CONSTANTS.CACHE_DAYS;
}

// ============================================================
// Location Key — Deduplicates crashes by route/node/jurisdiction/milepost
// ============================================================

function buildGeocodeLocationKey(row) {
    const route = (row[COL.ROUTE] || '').trim();
    const node = (row[COL.NODE] || '').trim();
    const jurisdiction = (row[COL.JURISDICTION] || '').trim();
    const mp = (row[COL.MP] || '').trim();
    return route + '|' + node + '|' + jurisdiction + '|' + mp;
}

// ============================================================
// Strategy 1: Node Lookup — Zero API calls, highest confidence
// ============================================================

function buildNodeCoordinateMap() {
    const nodeMap = {};
    for (const row of crashState.sampleRows) {
        const node = (row[COL.NODE] || '').trim();
        if (!node) continue;
        const x = parseFloat(row[COL.X]);
        const y = parseFloat(row[COL.Y]);
        if (isNaN(x) || isNaN(y) || x === 0 || y === 0) continue;
        if (!nodeMap[node]) nodeMap[node] = { lats: [], lngs: [] };
        nodeMap[node].lats.push(y);
        nodeMap[node].lngs.push(x);
    }
    const result = {};
    for (const [node, coords] of Object.entries(nodeMap)) {
        coords.lats.sort((a, b) => a - b);
        coords.lngs.sort((a, b) => a - b);
        const midIdx = Math.floor(coords.lats.length / 2);
        result[node] = { lat: coords.lats[midIdx], lng: coords.lngs[midIdx], count: coords.lats.length };
    }
    geocodeState.nodeCoordinateMap = result;
    return result;
}

// ============================================================
// Strategy 2: OSM Nominatim Geocoding — 1 req/sec, cached
// ============================================================

async function geocodeViaNominatim(routeName, jurisdictionName) {
    let query = routeName;
    if (jurisdictionName) query += ', ' + jurisdictionName;
    const stateName = (typeof appConfig !== 'undefined' && appConfig?.stateName) ? appConfig.stateName : '';
    if (stateName && !query.toLowerCase().includes(stateName.toLowerCase())) {
        query += ', ' + stateName;
    }
    if (!query.toLowerCase().includes('usa') && !query.toLowerCase().includes('united states')) {
        query += ', USA';
    }

    const gcBounds = (typeof getMapCoordinateBounds === 'function') ? getMapCoordinateBounds() : null;
    let url = 'https://nominatim.openstreetmap.org/search?format=json&limit=1&q=' + encodeURIComponent(query);
    if (gcBounds) {
        url += '&viewbox=' + gcBounds.lonMin + ',' + gcBounds.latMax + ',' + gcBounds.lonMax + ',' + gcBounds.latMin + '&bounded=1';
    }
    url += '&countrycodes=us';

    const response = await fetch(url, {
        headers: { 'User-Agent': 'CrashLens/1.0 (crash-lens.aicreatesai.com)' }
    });
    if (!response.ok) throw new Error('Nominatim: ' + response.status);
    const data = await response.json();
    if (!data || data.length === 0) return null;

    const feature = data[0];
    return {
        x: parseFloat(feature.lon),
        y: parseFloat(feature.lat),
        method: 'nominatim',
        confidence: feature.importance || 0.5,
        placeName: feature.display_name
    };
}

async function runNominatimGeocoding(missingIndices) {
    const locationGroups = new Map();
    for (const idx of missingIndices) {
        const row = crashState.sampleRows[idx];
        const key = buildGeocodeLocationKey(row);
        if (!locationGroups.has(key)) {
            locationGroups.set(key, {
                indices: [],
                route: (row[COL.ROUTE] || '').trim(),
                jurisdiction: (row[COL.JURISDICTION] || '').trim()
            });
        }
        locationGroups.get(key).indices.push(idx);
    }

    console.log('[Geocode] Nominatim: ' + missingIndices.length + ' crashes deduplicated to ' + locationGroups.size + ' unique locations');

    const uncachedLocations = [];
    for (const [key, group] of locationGroups) {
        const cached = await geocodeCacheLoad(key);
        if (cached && !geocodeCacheExpired(cached)) {
            if (cached.failed) continue;
            for (const idx of group.indices) {
                if (applyGeocodedCoordinates(idx, cached.x, cached.y, cached.method, cached.confidence)) {
                    geocodeState.resolvedByNominatim++;
                }
            }
        } else {
            uncachedLocations.push({ key, group });
        }
    }

    const cacheHits = locationGroups.size - uncachedLocations.length;
    if (cacheHits > 0) console.log('[Geocode] Nominatim: ' + cacheHits + ' cache hits, ' + uncachedLocations.length + ' need API calls');

    const maxCalls = Math.min(geocodeState.maxApiCalls, uncachedLocations.length);
    for (let i = 0; i < maxCalls && !geocodeState.cancelled; i++) {
        const { key, group } = uncachedLocations[i];
        try {
            if (!group.route) continue;

            const result = await geocodeViaNominatim(group.route, group.jurisdiction);
            geocodeState.apiCallCount++;

            if (result && result.confidence >= geocodeState.confidenceThreshold) {
                await geocodeCacheSave(key, result);
                for (const idx of group.indices) {
                    if (applyGeocodedCoordinates(idx, result.x, result.y, 'nominatim', result.confidence)) {
                        geocodeState.resolvedByNominatim++;
                    }
                }
            } else {
                await geocodeCacheSave(key, { x: 0, y: 0, method: 'nominatim', confidence: 0, failed: true });
            }
        } catch (err) {
            console.warn('[Geocode] Nominatim failed for "' + group.route + '":', err.message);
        }

        updateGeocodeProgressUI('nominatim_progress',
            geocodeState.resolvedByNode + geocodeState.resolvedByNominatim,
            geocodeState.totalMissing);

        if (i < maxCalls - 1 && !geocodeState.cancelled) {
            await new Promise(resolve => setTimeout(resolve, 1100));
        }
    }
}

// ============================================================
// Strategy 3: Milepost Interpolation — Zero API calls
// ============================================================

function buildRouteMilepostMap() {
    const routeMap = {};
    for (const row of crashState.sampleRows) {
        const route = (row[COL.ROUTE] || '').trim();
        const mp = parseFloat(row[COL.MP]);
        const x = parseFloat(row[COL.X]);
        const y = parseFloat(row[COL.Y]);
        if (!route || isNaN(mp) || isNaN(x) || isNaN(y) || x === 0 || y === 0) continue;
        if (!routeMap[route]) routeMap[route] = [];
        routeMap[route].push({ mp, lat: y, lng: x });
    }
    for (const route of Object.keys(routeMap)) {
        routeMap[route].sort((a, b) => a.mp - b.mp);
    }
    geocodeState.routeMilepostMap = routeMap;
    return routeMap;
}

function interpolateByMilepost(route, targetMp) {
    const points = geocodeState.routeMilepostMap[route];
    if (!points || points.length < 2) return null;
    let before = null, after = null;
    for (let i = 0; i < points.length; i++) {
        if (points[i].mp <= targetMp) before = points[i];
        if (points[i].mp >= targetMp && !after) after = points[i];
    }
    if (!before && !after) return null;
    if (before && !after) return { lat: before.lat, lng: before.lng, confidence: 0.4 };
    if (!before && after) return { lat: after.lat, lng: after.lng, confidence: 0.4 };
    if (before.mp === after.mp) return { lat: before.lat, lng: before.lng, confidence: 0.8 };
    const ratio = (targetMp - before.mp) / (after.mp - before.mp);
    return {
        lat: before.lat + ratio * (after.lat - before.lat),
        lng: before.lng + ratio * (after.lng - before.lng),
        confidence: Math.max(0.5, 0.9 - Math.abs(ratio - 0.5) * 0.4)
    };
}

function runMilepostInterpolation(missingIndices) {
    let resolved = 0;
    for (const idx of missingIndices) {
        if (geocodeState.cancelled) break;
        const row = crashState.sampleRows[idx];
        const route = (row[COL.ROUTE] || '').trim();
        const mp = parseFloat(row[COL.MP]);
        if (!route || isNaN(mp)) continue;
        const result = interpolateByMilepost(route, mp);
        if (result && result.confidence >= geocodeState.confidenceThreshold) {
            if (applyGeocodedCoordinates(idx, result.lng, result.lat, 'interpolation', result.confidence)) {
                resolved++;
                geocodeState.resolvedByInterpolation++;
            }
        }
    }
    console.log('[Geocode] Strategy 3 (Milepost Interpolation): ' + resolved + ' resolved');
}

// ============================================================
// Apply Geocoded Coordinates — Updates row data + mapPoints
// ============================================================

function applyGeocodedCoordinates(rowIndex, lng, lat, method, confidence) {
    const row = crashState.sampleRows[rowIndex];
    if (!row) return false;

    const bounds = (typeof getMapCoordinateBounds === 'function') ? getMapCoordinateBounds() : null;
    if (bounds && (lat < bounds.latMin || lat > bounds.latMax || lng < bounds.lonMin || lng > bounds.lonMax)) {
        return false;
    }

    const existX = parseFloat(row[COL.X]);
    const existY = parseFloat(row[COL.Y]);
    if (!isNaN(existX) && !isNaN(existY) && existX !== 0 && existY !== 0) return false;

    row[COL.X] = lng.toString();
    row[COL.Y] = lat.toString();

    const sev = (row[COL.SEVERITY] || '').trim().toUpperCase().charAt(0) || 'O';
    crashState.mapPoints.push({
        lat: lat, lng: lng, sev: sev,
        route: row[COL.ROUTE] || '', node: row[COL.NODE] || '',
        collision: (row[COL.COLLISION] || '').trim() || 'Unknown',
        date: row[COL.DATE], time: row[COL.TIME],
        isPed: isYes(row[COL.PED]), isBike: isYes(row[COL.BIKE]),
        isInt: isIntersection(row),
        weather: (row[COL.WEATHER] || '').trim() || 'Unknown',
        light: (row[COL.LIGHT] || '').trim() || 'Unknown',
        isSpeed: isYes(row[COL.SPEED]), isYoung: isYes(row[COL.YOUNG]),
        isNight: isYes(row[COL.NIGHT]), docNum: row[COL.ID] || '',
        geocoded: true, geocodeMethod: method, geocodeConfidence: confidence
    });
    return true;
}

// ============================================================
// UI Progress Updates
// ============================================================

function updateGeocodeProgressUI(phase, resolved, total) {
    const progressArea = document.getElementById('geocodeProgressArea');
    if (!progressArea) return;
    if (total === 0) return;
    progressArea.style.display = 'block';

    const pct = total > 0 ? Math.round((resolved / total) * 100) : 0;
    const bar = document.getElementById('geocodeProgressBar');
    if (bar) bar.style.width = pct + '%';

    const el = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
    el('geocodeNodeCount', geocodeState.resolvedByNode.toLocaleString());
    el('geocodeNominatimCount', geocodeState.resolvedByNominatim.toLocaleString());
    el('geocodeInterpolationCount', geocodeState.resolvedByInterpolation.toLocaleString());
    el('geocodeFailedCount', (total - resolved).toLocaleString());

    const cancelBtn = document.getElementById('geocodeCancelBtn');
    const saveBtn = document.getElementById('geocodeSaveBtn');
    const statusIcon = document.getElementById('geocodeStatusIcon');
    const statusText = document.getElementById('geocodeStatusText');
    const startBtn = document.getElementById('geocodeBtn');
    const summaryText = document.getElementById('geocodeMissingSummary');

    switch (phase) {
        case 'starting':
            if (statusIcon) statusIcon.textContent = '🔍';
            if (statusText) statusText.textContent = 'Found ' + total.toLocaleString() + ' crashes missing GPS. Starting recovery...';
            if (cancelBtn) cancelBtn.style.display = 'inline-block';
            if (saveBtn) saveBtn.style.display = 'none';
            if (startBtn) startBtn.style.display = 'none';
            if (summaryText) summaryText.style.display = 'none';
            break;
        case 'node_complete':
            if (statusIcon) statusIcon.textContent = '🔄';
            if (statusText) statusText.textContent = 'Node lookup: ' + resolved.toLocaleString() + ' recovered. Running Nominatim geocoding...';
            break;
        case 'nominatim_progress':
            if (statusText) statusText.textContent = 'Progress: ' + resolved.toLocaleString() + '/' + total.toLocaleString() + ' recovered (' + pct + '%). API calls: ' + geocodeState.apiCallCount;
            break;
        case 'complete':
            if (statusIcon) statusIcon.textContent = pct >= 90 ? '✅' : pct >= 50 ? '🟡' : '🟠';
            if (statusText) statusText.textContent = 'Recovery complete: ' + resolved.toLocaleString() + '/' + total.toLocaleString() + ' (' + pct + '%) coordinates recovered.';
            if (cancelBtn) cancelBtn.style.display = 'none';
            if (saveBtn) saveBtn.style.display = resolved > 0 ? 'inline-block' : 'none';
            if (startBtn) startBtn.style.display = 'none';
            // Update panel style to reflect completion
            var panel = document.getElementById('geocodePanel');
            if (panel && pct >= 50) {
                panel.style.borderLeftColor = '#22c55e';
                panel.style.background = '#f0fdf4';
            }
            break;
    }
}

// ============================================================
// Orchestrator — Runs all 3 strategies in sequence
// ============================================================

async function startGeocoding() {
    if (geocodeState.running || !crashState.loaded) return;
    geocodeState.running = true;
    geocodeState.cancelled = false;
    geocodeState.resolvedByNode = 0;
    geocodeState.resolvedByNominatim = 0;
    geocodeState.resolvedByInterpolation = 0;
    geocodeState.failed = 0;
    geocodeState.apiCallCount = 0;

    console.log('[Geocode] Starting in-browser geocoding...');

    // Phase 1: Identify missing-GPS crashes
    const missingIndices = [];
    for (let i = 0; i < crashState.sampleRows.length; i++) {
        const row = crashState.sampleRows[i];
        const x = parseFloat(row[COL.X]);
        const y = parseFloat(row[COL.Y]);
        if (isNaN(x) || isNaN(y) || x === 0 || y === 0) missingIndices.push(i);
    }
    geocodeState.totalMissing = missingIndices.length;
    if (missingIndices.length === 0) {
        geocodeState.running = false;
        geocodeState.completed = true;
        if (typeof showToast === 'function') showToast('All crash records already have GPS coordinates', 'success');
        return;
    }
    console.log('[Geocode] Found ' + missingIndices.length + ' crashes missing GPS coordinates');
    updateGeocodeProgressUI('starting', 0, missingIndices.length);

    // Phase 2: Strategy 1 — Node Lookup (synchronous, fast)
    buildNodeCoordinateMap();
    let nodeResolved = 0;
    for (const idx of missingIndices) {
        if (geocodeState.cancelled) break;
        const row = crashState.sampleRows[idx];
        const node = (row[COL.NODE] || '').trim();
        if (node && geocodeState.nodeCoordinateMap[node]) {
            const coords = geocodeState.nodeCoordinateMap[node];
            if (applyGeocodedCoordinates(idx, coords.lng, coords.lat, 'node_lookup', 0.95)) {
                nodeResolved++;
                geocodeState.resolvedByNode++;
            }
        }
    }
    console.log('[Geocode] Strategy 1 (Node Lookup): ' + nodeResolved + ' resolved');
    updateGeocodeProgressUI('node_complete', geocodeState.resolvedByNode, missingIndices.length);

    // Phase 3: Strategy 2 — Nominatim API (async, 1 req/sec)
    if (!geocodeState.cancelled) {
        const stillMissing = missingIndices.filter(idx => {
            const row = crashState.sampleRows[idx];
            const x = parseFloat(row[COL.X]);
            const y = parseFloat(row[COL.Y]);
            return isNaN(x) || isNaN(y) || x === 0 || y === 0;
        });
        if (stillMissing.length > 0) await runNominatimGeocoding(stillMissing);
    }

    // Phase 4: Strategy 3 — Milepost Interpolation
    if (!geocodeState.cancelled) {
        const finalMissing = missingIndices.filter(idx => {
            const row = crashState.sampleRows[idx];
            const x = parseFloat(row[COL.X]);
            const y = parseFloat(row[COL.Y]);
            return isNaN(x) || isNaN(y) || x === 0 || y === 0;
        });
        if (finalMissing.length > 0) {
            buildRouteMilepostMap();
            runMilepostInterpolation(finalMissing);
        }
    }

    // Phase 5: Finalize
    geocodeState.running = false;
    geocodeState.completed = true;
    const totalResolved = geocodeState.resolvedByNode + geocodeState.resolvedByNominatim + geocodeState.resolvedByInterpolation;
    geocodeState.failed = geocodeState.totalMissing - totalResolved;
    crashState.missingGPS = geocodeState.failed;

    console.log('[Geocode] Complete: ' + totalResolved + '/' + geocodeState.totalMissing +
        ' (Node: ' + geocodeState.resolvedByNode + ', Nominatim: ' + geocodeState.resolvedByNominatim +
        ', Interpolation: ' + geocodeState.resolvedByInterpolation + ', Failed: ' + geocodeState.failed + ')');

    updateGeocodeProgressUI('complete', totalResolved, geocodeState.totalMissing);

    // Refresh map if visible
    if (typeof crashMap !== 'undefined' && crashMap && typeof updateMapDisplay === 'function') {
        updateMapDisplay();
    }

    // Update DQ stats if available
    if (typeof validationState !== 'undefined' && validationState.loaded) {
        validationState.stats.missingCoords = Math.max(0, validationState.stats.missingCoords - totalResolved);
        if (typeof dqRenderScoreCard === 'function') dqRenderScoreCard();
    }

    if (totalResolved > 0 && typeof showToast === 'function') {
        showToast('Geocoding recovered ' + totalResolved.toLocaleString() + ' crash locations (' +
            Math.round((totalResolved / geocodeState.totalMissing) * 100) + '%)', 'success', 5000);
    }
}

function cancelGeocoding() {
    geocodeState.cancelled = true;
    geocodeState.running = false;
    const totalResolved = geocodeState.resolvedByNode + geocodeState.resolvedByNominatim + geocodeState.resolvedByInterpolation;
    updateGeocodeProgressUI('complete', totalResolved, geocodeState.totalMissing);
    if (typeof showToast === 'function') showToast('Geocoding cancelled', 'warning');
}

// ============================================================
// Save Corrected Data to R2 Cloud Storage
// ============================================================

async function saveGeocodedDataToR2() {
    const saveBtn = document.getElementById('geocodeSaveBtn');
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'Saving...'; }

    try {
        const stateKey = (typeof _getActiveStateKey === 'function') ? _getActiveStateKey() : '';
        const jurisdiction = (typeof getActiveJurisdictionId === 'function') ? getActiveJurisdictionId() : '';
        const roadType = (typeof getActiveRoadTypeSuffix === 'function') ? getActiveRoadTypeSuffix() : 'all_roads';

        if (!stateKey || !jurisdiction) {
            throw new Error('Cannot determine state/jurisdiction. Ensure data is loaded from a configured jurisdiction.');
        }

        const r2Key = stateKey + '/' + jurisdiction + '/' + roadType + '.csv';
        console.log('[Geocode] Saving corrected data to R2: ' + r2Key);

        // Build CSV from sampleRows (same pattern as dqExportCorrectedCSV)
        const rows = crashState.sampleRows;
        if (!rows || rows.length === 0) throw new Error('No data to save');
        const headers = Object.keys(rows[0]);
        let csv = headers.map(function(h) { return '"' + h.replace(/"/g, '""') + '"'; }).join(',') + '\n';
        for (const row of rows) {
            csv += headers.map(function(h) {
                var val = row[h];
                if (val === undefined || val === null) val = '';
                val = val.toString();
                if (h === COL.DATE && !isNaN(Number(val)) && Number(val) > 946684800000) {
                    var d = new Date(Number(val));
                    val = (d.getMonth() + 1) + '/' + d.getDate() + '/' + d.getFullYear();
                }
                return '"' + val.replace(/"/g, '""') + '"';
            }).join(',') + '\n';
        }

        // Check R2 endpoint availability
        var statusResp;
        try {
            statusResp = await fetch('/api/r2/status');
        } catch (e) {
            throw new Error('Cannot reach server API. R2 upload requires the server to be running.');
        }
        var statusData = await statusResp.json();
        if (!statusData.configured) {
            throw new Error('R2 not configured on server. Set CF_ACCOUNT_ID, CF_R2_ACCESS_KEY_ID, CF_R2_SECRET_ACCESS_KEY in Coolify.');
        }

        var resp = await fetch('/api/r2/upload-geocoded', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ r2Key: r2Key, csvData: csv })
        });

        if (!resp.ok) {
            var errData = await resp.json().catch(function() { return {}; });
            throw new Error(errData.message || errData.error || 'Upload failed: ' + resp.status);
        }

        var result = await resp.json();
        console.log('[Geocode] R2 upload success:', result);

        if (saveBtn) {
            saveBtn.textContent = '✓ Saved!';
            saveBtn.style.background = '#22c55e';
            saveBtn.style.color = '#fff';
            saveBtn.style.borderColor = '#22c55e';
        }
        if (typeof showToast === 'function') {
            showToast('Corrected data saved to cloud (' + (result.size / 1024 / 1024).toFixed(1) + ' MB). Future loads will include geocoded coordinates.', 'success', 7000);
        }

        var statusText = document.getElementById('geocodeStatusText');
        if (statusText) statusText.textContent += ' Data saved to cloud storage.';

    } catch (err) {
        console.error('[Geocode] R2 save failed:', err);
        if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = '💾 Save Corrected Data to Cloud'; }
        if (typeof showToast === 'function') showToast('Save failed: ' + err.message, 'error', 7000);
    }
}
