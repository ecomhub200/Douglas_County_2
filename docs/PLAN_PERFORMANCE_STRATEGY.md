# Data Caching & Performance Strategy
## Comprehensive Implementation Plan

**Version:** 1.0
**Date:** February 2026
**Scope:** CRASH LENS Application (`app/index.html`)
**Goal:** Eliminate UI freezes, enable instant return visits, and scale to 500K+ crash records smoothly

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Assessment](#2-current-state-assessment)
3. [Strategy Overview](#3-strategy-overview)
4. [Phase 1: Web Worker for CSV Parsing & Aggregation](#4-phase-1-web-worker-for-csv-parsing--aggregation)
5. [Phase 2: IndexedDB Expansion for Raw Crash Records](#5-phase-2-indexeddb-expansion-for-raw-crash-records)
6. [Phase 3: Worker-Based Query Engine](#6-phase-3-worker-based-query-engine)
7. [Phase 4: Spatial Indexing for Map Performance](#7-phase-4-spatial-indexing-for-map-performance)
8. [Phase 5: Progressive UI & Skeleton Screens](#8-phase-5-progressive-ui--skeleton-screens)
9. [Architecture Diagrams](#9-architecture-diagrams)
10. [Migration Strategy](#10-migration-strategy)
11. [IndexedDB Schema Design](#11-indexeddb-schema-design)
12. [Performance Benchmarks & Targets](#12-performance-benchmarks--targets)
13. [Risk Mitigation](#13-risk-mitigation)
14. [Testing Plan](#14-testing-plan)
15. [Implementation Timeline](#15-implementation-timeline)
16. [Appendix: Browser Compatibility](#16-appendix-browser-compatibility)

---

## 1. Executive Summary

### 1.1 Problem Statement

CRASH LENS processes 500,000+ crash records entirely on the browser's **main UI thread**. This causes:

- **3-8 second UI freezes** during CSV parsing (16MB file via PapaParse)
- **Repeated re-parsing** on every visit (no persistent raw data cache)
- **Main-thread aggregation** via `processRow()` blocking all user interaction during data load
- **localStorage reliability issues** — silent data loss documented in BUG-002 (duplicate `loadApplications()` functions using different storage keys)
- **50,000 marker cap** on the Map tab to avoid rendering collapse
- **Eager recomputation** on some tabs (Dashboard, Analysis) even when data hasn't changed

### 1.2 Proposed Solution

A five-phase strategy that introduces:

| Component | Purpose | Impact |
|-----------|---------|--------|
| **Web Workers** | Move CSV parsing and heavy computation off the main thread | Eliminates UI freezes |
| **IndexedDB Expansion** | Store raw crash records persistently with queryable indexes | Enables instant return visits |
| **Worker Query Engine** | All filtering/aggregation runs in background thread | Smooth tab switching and filtering |
| **Spatial Indexing** | R-tree index for map viewport queries | Removes the 50K marker cap |
| **Skeleton Screens** | Show tab layouts immediately while data computes | Perceived performance improvement |

### 1.3 Key Constraints

- **Single-file architecture must be preserved** — Workers will be created via `Blob` URLs (inline code)
- **No build tooling required** — all changes work within the existing `index.html` pattern
- **Backward compatible** — existing state objects (`crashState`, `cmfState`, etc.) remain the API surface
- **Graceful degradation** — if a browser doesn't support Workers or IndexedDB, fall back to current behavior

### 1.4 What Already Exists (Build On, Don't Replace)

| Existing Component | Location | Status |
|--------------------|----------|--------|
| IndexedDB for aggregate caching | `crashCacheOpen()`, `crashCacheSave()` (~line 22555) | Working, 30-day TTL |
| IndexedDB for warrant data | `warrantDbOpen()`, `warrantDbSave()` (~line 23114) | Working, full CRUD |
| IndexedDB for data corrections | `corrections` object store (~line 21201) | Working |
| Lazy tab initialization | `showTab()` (~line 25969) | Working for most tabs |
| PapaParse chunked parsing | `processUploadedFile()`, `autoLoadCrashData()` | Working, but on main thread |
| MarkerCluster chunked loading | `markerCluster` config (~line 38164) | Working, capped at 50K |

---

## 2. Current State Assessment

### 2.1 Data Loading Pipeline (Current)

```
User opens CRASH LENS
        │
        ▼
Main Thread: Fetch CSV (16MB network transfer)
        │
        ▼
Main Thread: PapaParse chunked parsing ◄── UI FROZEN 3-8 seconds
        │
        ├── processRow() called per row (500K iterations)
        │   ├── Updates crashState.aggregates
        │   ├── Pushes to crashState.sampleRows[]
        │   └── Date conversion, severity mapping
        │
        ▼
Main Thread: finalizeData()
        │
        ├── Sorts years, routes, nodes
        ├── crashCacheSave() → IndexedDB (aggregates only)
        └── updateDashboard() → Renders charts
```

**Bottlenecks identified:**

| Bottleneck | Duration | Impact |
|-----------|----------|--------|
| PapaParse parsing 16MB CSV | 2-4 seconds | Complete UI freeze |
| `processRow()` × 500K iterations | 1-3 seconds | Complete UI freeze |
| `crashState.sampleRows` array growth | 500K push operations | Memory pressure, GC pauses |
| `finalizeData()` sorting | 200-500ms | Brief freeze |
| **Total main-thread block** | **3-8 seconds** | **Page unresponsive** |

### 2.2 Storage Architecture (Current)

```
┌─────────────────────────────────────────────────────┐
│                    localStorage                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ jurisdiction  │  │ filterProfile│  │ configCache│ │
│  │  selection    │  │  selection   │  │  + version │ │
│  └──────────────┘  └──────────────┘  └────────────┘ │
│  ┌──────────────────────────────────────────────────┐│
│  │ signalWarrantData  (DUPLICATED in IndexedDB)     ││
│  └──────────────────────────────────────────────────┘│
│                 5-10 MB LIMIT                         │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│               IndexedDB (Partial)                     │
│  ┌──────────────────────┐  ┌───────────────────────┐ │
│  │ CrashLensDataCache   │  │ WarrantDatabase       │ │
│  │  └─ crashAggregates  │  │  └─ signal            │ │
│  │     (pre-computed)   │  │  └─ rtor              │ │
│  │     30-day TTL       │  │  └─ bike              │ │
│  │                      │  │  └─ pedestrian        │ │
│  └──────────────────────┘  └───────────────────────┘ │
│  ┌──────────────────────┐                             │
│  │ corrections          │                             │
│  │  └─ data quality     │                             │
│  └──────────────────────┘                             │
│                                                       │
│  ❌ NO raw crash records stored                       │
│  ❌ NO indexed queries on route/node/severity         │
│  ❌ NO cross-session sampleRows persistence           │
└─────────────────────────────────────────────────────┘
```

### 2.3 Tab Initialization (Current)

| Tab | Pattern | Notes |
|-----|---------|-------|
| Dashboard | **Eager update** | `updateDashboard()` every visit — rebuilds charts even if data unchanged |
| Map | **Lazy init** | `initMap()` only on first visit — good |
| Analysis | **Eager update** | `updateAnalysis()` every visit |
| Hotspots | **Conditional** | Only computes if `!crashState.hotspots.length` |
| CMF | **Lazy** | `loadCMFDatabase()` on first visit — good |
| Grants | **Lazy** | `initGrantModule()` on first visit — good |
| Warrants | **Lazy** | `initWarrantsTab()` on first visit — good |
| CrashTree | **Lazy** | First visit inits, subsequent visits rebuild data |
| Safety Focus | **Lazy** | First visit inits, subsequent visits update cards |
| Intersection | **Eager update** | `updateIntersectionTab()` every visit |
| Ped/Bike | **Eager update** | `updatePedBikeTab()` every visit |

**Opportunity:** Dashboard, Analysis, Intersection, and Ped/Bike tabs recompute on every visit even when underlying data hasn't changed. Adding a dirty flag pattern would skip unnecessary recomputation.

---

## 3. Strategy Overview

### 3.1 Five-Phase Approach

```
Phase 1: Web Worker for CSV Parsing         ──► Eliminates the worst freeze
    │
Phase 2: IndexedDB for Raw Records          ──► Enables instant return visits
    │
Phase 3: Worker-Based Query Engine           ──► Background filtering & aggregation
    │
Phase 4: Spatial Indexing for Map            ──► Removes 50K marker limit
    │
Phase 5: Skeleton Screens & Progressive UI   ──► Perceived performance polish
```

### 3.2 Dependency Graph

```
Phase 1 (Worker)
    │
    ├──► Phase 2 (IndexedDB Expansion)    ← Worker writes directly to IndexedDB
    │       │
    │       └──► Phase 3 (Query Engine)   ← Worker queries IndexedDB indexes
    │
    └──► Phase 5 (Skeleton Screens)       ← Independent, can start anytime

Phase 4 (Spatial Index)                    ← Independent of Phases 1-3
```

**Phases 1 and 4 can be developed in parallel.**
**Phase 5 can begin at any time.**

---

## 4. Phase 1: Web Worker for CSV Parsing & Aggregation

### 4.1 Objective

Move the CSV parsing and `processRow()` aggregation loop off the main thread entirely.

### 4.2 Worker Creation (Single-File Compatible)

Since the application is a single HTML file, the Worker must be created from an inline `Blob`:

```
Main Thread                                 CrashDataWorker (Blob URL)
────────────                                ────────────────────────────
1. Create Blob from inline JS string
2. Create Worker from Blob URL
3. Post CSV text or URL to Worker  ────►   4. Receive CSV text
                                            5. Parse with PapaParse (bundled in Worker)
                                            6. Run processRow() for each record
                                            7. Build aggregates object
   ◄──── 8. Post progress updates          8. Post progress % every 5000 rows
9. Update loading bar (smooth)
   ◄──── 10. Post final result             10. Transfer aggregates + sampleRows
11. Set crashState from result
12. Render Dashboard
```

### 4.3 What Moves to the Worker

| Function | Current Location | Worker Responsibility |
|----------|-----------------|----------------------|
| PapaParse chunked parse | `processUploadedFile()` ~line 22918 | Full CSV → parsed rows |
| `processRow()` | ~line 27085 | Row normalization + aggregation |
| StateAdapter detection | ~line 22922 | State auto-detection from headers |
| `finalizeData()` | ~line 27254 | Year/route/node sorting |

### 4.4 What Stays on Main Thread

| Function | Reason |
|----------|--------|
| `updateDashboard()` | Needs DOM access (Chart.js) |
| `initMap()` | Needs DOM access (Leaflet) |
| UI progress bar updates | Needs DOM access |
| `crashCacheSave()` | IndexedDB accessible from Worker too, but keep on main for simplicity in Phase 1 |

### 4.5 Data Transfer Strategy

**Option A: Structured Clone (Simple)**
- Worker posts `{ aggregates, sampleRows, years, routes, nodes }` back to main thread
- Browser deep-copies the entire object
- For 500K rows, this could take 500ms-1s for the copy

**Option B: Transferable ArrayBuffer (Optimal)**
- Encode `sampleRows` as a compact `ArrayBuffer` with a known schema
- Transfer with zero-copy via `postMessage(data, [buffer])`
- Main thread decodes into `crashState.sampleRows` on demand
- More complex but eliminates the copy overhead

**Recommendation:** Start with **Option A** for Phase 1. The 500ms copy is acceptable since it replaces a 3-8 second freeze. Optimize to Option B in Phase 3 if needed.

### 4.6 Progress Reporting

The Worker should post progress messages that the main thread uses to update the UI:

| Message Type | Payload | UI Update |
|-------------|---------|-----------|
| `{ type: 'progress', rows: N, total: est }` | Row count processed | Loading bar percentage |
| `{ type: 'state_detected', state: 'VA' }` | Detected state adapter | Status text update |
| `{ type: 'complete', data: {...} }` | Full result | Set crashState, render |
| `{ type: 'error', message: '...' }` | Error details | Error banner |

### 4.7 PapaParse in the Worker

PapaParse must be available inside the Worker. Options:

1. **Inline the minified PapaParse source** in the Worker Blob string (~30KB minified)
2. **importScripts()** from CDN — but requires network and doesn't work offline

**Recommendation:** Inline PapaParse in the Worker Blob. This preserves offline-first architecture. The 30KB addition to `index.html` is negligible relative to 122K lines.

### 4.8 Fallback Behavior

If `typeof Worker === 'undefined'` (very old browsers), fall back to the current main-thread parsing. No functionality lost, just no performance gain.

### 4.9 Estimated Impact

| Metric | Before | After Phase 1 |
|--------|--------|---------------|
| UI freeze during CSV parse | 3-8 seconds | **0 seconds** |
| Loading bar responsiveness | Janky (updates between chunks) | **Smooth 60fps** |
| Time to Dashboard render | 3-8 seconds | **3-8 seconds** (same total, but non-blocking) |
| User can interact during load | No | **Yes** (tabs, sidebar, settings) |

---

## 5. Phase 2: IndexedDB Expansion for Raw Crash Records

### 5.1 Objective

Store the full `crashState.sampleRows` dataset (500K records) in IndexedDB with queryable indexes, eliminating the need to re-parse CSV on return visits.

### 5.2 Why This Matters

Currently, every time a user opens CRASH LENS:
1. Fetch 16MB CSV from server (or browser HTTP cache)
2. Parse with PapaParse (3-8 seconds of processing)
3. Build aggregates from scratch

With IndexedDB storing raw records:
1. Check IndexedDB for cached data + metadata
2. If fresh (within TTL), load from IndexedDB (**< 500ms**)
3. If stale, fetch and parse in Worker, then update IndexedDB

### 5.3 Building on Existing Infrastructure

The codebase already has `CrashLensDataCache` with `crashAggregates` store. This phase expands it:

**Current schema** (from ~line 22555):
```
CrashLensDataCache (v1)
  └── crashAggregates [keyPath: cacheKey]
        ├── aggregates (pre-computed)
        ├── years, routes, totalRows
        ├── cachedAt, expiresAt
```

**Expanded schema** (Phase 2):
```
CrashLensDataCache (v2)  ← version bump triggers onupgradeneeded
  ├── crashAggregates [keyPath: cacheKey]         ← unchanged
  │     ├── aggregates, years, routes, totalRows
  │     ├── cachedAt, expiresAt
  │
  ├── crashRecords [keyPath: autoIncrement]        ← NEW
  │     ├── Indexes: route, node, severity, date, [route+node] compound
  │     ├── Each record: { route, node, severity, collision, lat, lng,
  │     │                   date, weather, light, ped, bike, speed,
  │     │                   funcClass, intType, trafficCtrl, ... }
  │     └── 500K records, ~200-300MB in IndexedDB (acceptable)
  │
  ├── cacheMetadata [keyPath: key]                 ← NEW
  │     ├── dataVersion (hash of CSV or last-modified header)
  │     ├── jurisdiction
  │     ├── filterProfile
  │     ├── recordCount
  │     ├── cachedAt, expiresAt
  │     └── schemaVersion
  │
  └── cachedProfiles [keyPath: locationKey]        ← NEW
        ├── Crash profile per location (route+node)
        ├── lastUpdated timestamp
        └── Avoids recomputation for revisited locations
```

### 5.4 Cache Invalidation Strategy

| Trigger | Action |
|---------|--------|
| Jurisdiction change | Clear all stores, re-fetch |
| Filter profile change | Clear crashRecords + aggregates, re-fetch |
| TTL expired (30 days) | Background refresh — show cached data immediately, update silently |
| Manual data upload | Clear all stores, parse uploaded file |
| App version change | Clear all stores (schema may have changed) |
| CSV content hash mismatch | Background refresh with cached data shown first |

### 5.5 Return Visit Flow

```
User opens CRASH LENS (return visit)
        │
        ▼
Main Thread: Check cacheMetadata in IndexedDB
        │
        ├── Cache valid?
        │   ├── YES: Load aggregates from crashAggregates store
        │   │         Render Dashboard IMMEDIATELY (< 500ms)
        │   │         Set crashState.loaded = true
        │   │         Background: verify data freshness
        │   │
        │   └── NO:  Show loading UI
        │            Worker: fetch CSV → parse → store in IndexedDB
        │            Render when complete
        │
        ▼
User navigates to CMF tab → selects location
        │
        ▼
Query crashRecords index [route+node] → returns 47 records
        │  (IndexedDB indexed query, not 500K array filter)
        │
        ▼
Build crash profile from 47 records (instant)
```

### 5.6 Storage Size Estimation

| Data | Estimated Size in IndexedDB |
|------|----------------------------|
| 500K crash records (structured objects) | 150-300 MB |
| Aggregates cache | 1-2 MB |
| Cache metadata | < 1 KB |
| Cached location profiles (up to 500) | 2-5 MB |
| **Total** | **~150-310 MB** |

IndexedDB storage limits by browser:
- Chrome: Up to 80% of disk space (typically 10+ GB available)
- Firefox: Up to 50% of disk space
- Safari: 1 GB before prompting user (sufficient)
- Edge: Same as Chrome

**150-310 MB is well within limits for all modern browsers.**

### 5.7 Estimated Impact

| Metric | Before | After Phase 2 |
|--------|--------|---------------|
| Return visit load time | 3-8 seconds (re-parse CSV) | **< 500ms** (load from IndexedDB) |
| Location filtering | Array.filter on 500K rows | **Indexed query** (< 50ms) |
| Storage reliability | localStorage (5MB, silent failures) | **IndexedDB** (GB-scale, transactional) |
| Offline return visits | Depends on HTTP cache | **Guaranteed** (data in IndexedDB) |

---

## 6. Phase 3: Worker-Based Query Engine

### 6.1 Objective

Move ALL filtering, aggregation, and crash profile computation into the Web Worker, keeping the main thread exclusively for UI rendering.

### 6.2 Query API Design

The main thread sends query messages to the Worker; the Worker responds with results:

| Query | Input | Output | Used By |
|-------|-------|--------|---------|
| `filterByLocation` | `{ route, node }` | `{ crashes[], crashProfile }` | CMF Tab, Warrants Tab |
| `filterByDateRange` | `{ startDate, endDate }` | `{ crashes[], updatedAggregates }` | All tabs with date filters |
| `filterByLocationAndDate` | `{ route, node, startDate, endDate }` | `{ crashes[], crashProfile }` | CMF, Warrants with date |
| `buildHotspots` | `{ sortBy: 'epdo' }` | `{ rankedLocations[] }` | Hotspots Tab |
| `buildSafetyCategory` | `{ category: 'pedestrian' }` | `{ crashes[], stats }` | Safety Focus Tab |
| `getMapPoints` | `{ bounds, filters }` | `{ points[] }` | Map Tab (viewport query) |
| `buildCrashProfile` | `{ crashes[] or locationKey }` | `{ detailed profile }` | AI Tab, Reports |
| `getAggregates` | `{ dateRange? }` | `{ aggregates }` | Dashboard, Analysis |

### 6.3 Message Protocol

```
Main Thread → Worker:
{
    id: 'query_001',            // Unique ID for matching response
    type: 'filterByLocation',   // Query type from table above
    params: { route: 'US-250', node: '12345' }
}

Worker → Main Thread:
{
    id: 'query_001',            // Matching ID
    type: 'result',
    data: { crashes: [...], crashProfile: {...} },
    timing: { ms: 23 }         // For performance monitoring
}
```

### 6.4 Query Cancellation

When a user rapidly switches tabs or changes filters, previous queries become irrelevant:

```
Main Thread                          Worker
────────────                         ──────
Send query_001 (Route A) ────►
User switches to Route B
Send query_002 (Route B) ────►       Processing query_001...
Send { cancel: 'query_001' } ──►     Aborts query_001
                                      Starts query_002
                              ◄────   Returns query_002 result
```

This prevents stale results from overwriting current state and reduces wasted computation.

### 6.5 State Object Compatibility

To maintain backward compatibility, the main thread translates Worker responses into existing state objects:

```
Worker returns: { crashes: [...], crashProfile: {...} }
                         │
                         ▼
Main thread handler sets:
    cmfState.locationCrashes = response.crashes;
    cmfState.filteredCrashes = response.crashes;  // or date-filtered subset
    cmfState.crashProfile = response.crashProfile;
    cmfState.selectedLocation = params.location;
                         │
                         ▼
Existing UI update functions work unchanged:
    updateCMFDisplay();  // reads from cmfState as before
```

### 6.6 Worker Data Residency

After Phase 2, the Worker holds the full dataset in memory (loaded from IndexedDB on startup). The main thread holds ONLY:
- `crashState.aggregates` (for quick Dashboard access)
- The current tab's filtered data (e.g., `cmfState.filteredCrashes`)
- UI state (selections, filter values)

This reduces main thread memory from ~500MB (full sampleRows) to ~10-50MB (current view only).

### 6.7 Estimated Impact

| Metric | Before | After Phase 3 |
|--------|--------|---------------|
| Location filter (CMF tab) | 100-300ms freeze (array scan) | **0ms freeze** (background) |
| Date range change | 200-500ms freeze | **0ms freeze** (background) |
| Hotspot recalculation | 1-2 second freeze | **0ms freeze** (background) |
| Main thread memory | ~500MB (sampleRows) | **~10-50MB** (current view) |
| Concurrent queries | Not possible | **Queue-based** with cancellation |

---

## 7. Phase 4: Spatial Indexing for Map Performance

### 7.1 Objective

Replace the brute-force 50K-capped marker rendering with a spatial index that efficiently queries "which crashes fall within the current map viewport?"

### 7.2 Current Map Bottleneck

```
Map tab opened
        │
        ▼
Filter crashState.sampleRows by year/severity  ← 500K iterations
        │
        ▼
Cap at 50,000 markers  ← Data loss! User can't see all crashes
        │
        ▼
Create 50K L.marker objects  ← Memory + CPU intensive
        │
        ▼
Add to markerCluster  ← Cluster computation on all 50K points
```

### 7.3 Proposed Solution: R-Tree Spatial Index

An R-tree (via **RBush** library, ~6KB minified) organizes points in a spatial hierarchy enabling O(log n) viewport queries instead of O(n) array scans:

```
Map viewport changes (pan/zoom)
        │
        ▼
Query R-tree: "points within [south, west, north, east]"
        │  ← Returns only visible points (typically 100-5000)
        │  ← O(log n + k) where k = results, vs O(500K) scan
        │
        ▼
Render ONLY visible points into markerCluster
        │  ← 100-5000 markers instead of 50,000
        │
        ▼
Smooth rendering, no cap needed
```

### 7.4 R-Tree Construction

**When:** After crash data is loaded (Phase 1 Worker can build it, or build on main thread after Worker delivers data)

**Data structure per point:**
```
{
    minX: lng, minY: lat,    // RBush requires bounding box format
    maxX: lng, maxY: lat,
    index: i                  // Reference to full record in sampleRows or IndexedDB
}
```

**Build time:** ~200ms for 500K points (RBush is highly optimized)
**Memory:** ~30-40MB for 500K entries (acceptable)

### 7.5 Viewport Query Flow

```
User pans/zooms map
        │
        ▼
Debounce: wait 150ms after last interaction
        │
        ▼
Get map bounds: crashMap.getBounds()
        │
        ▼
Query R-tree: tree.search({ minX, minY, maxX, maxY })
        │
        ├── Apply active filters (year, severity) to results
        │
        ▼
Update markerCluster with viewport results only
        │
        ├── New points: add to cluster
        ├── Out-of-viewport points: remove from cluster
        └── Unchanged points: skip
```

### 7.6 Integration with Existing Map Code

The change primarily affects the marker rendering in `showTab('map')` and the filter update functions:

| Current Function | Change Required |
|-----------------|-----------------|
| `initMap()` (~line 38084) | Build R-tree after map init |
| Marker rendering loop (~line 38368) | Replace array iteration with R-tree viewport query |
| Filter change handlers | Re-query R-tree with new filters (no rebuild needed for spatial filters) |
| `markerCluster.clearLayers()` (~line 38337) | Keep — still needed for full refresh |

### 7.7 Heatmap Integration

The existing heatmap layer can also benefit from viewport-based data:

| Mode | Current | With Spatial Index |
|------|---------|-------------------|
| Cluster | 50K capped markers | Viewport-only markers (no cap) |
| Heatmap | 50K capped points | Viewport-only points (denser, more accurate) |

### 7.8 Estimated Impact

| Metric | Before | After Phase 4 |
|--------|--------|---------------|
| Max displayable crashes | 50,000 (capped) | **500,000+** (all, viewport-loaded) |
| Viewport query time | O(n) = 500K iterations | **O(log n + k)** ≈ 1-5ms |
| Pan/zoom responsiveness | Laggy with 50K markers | **Smooth** with viewport-only markers |
| Memory for map markers | 50K marker objects always | **Only visible** markers in memory |

---

## 8. Phase 5: Progressive UI & Skeleton Screens

### 8.1 Objective

Replace loading spinners with skeleton screens and add dirty-flag patterns to avoid unnecessary recomputation on tab revisits.

### 8.2 Skeleton Screens

When a user clicks a tab that hasn't loaded yet, show the tab's **layout structure** with animated placeholder blocks:

```
┌─────────────────────────────────────────────┐
│  ████████████████         ████████████████   │  ← Title placeholders
│                                              │
│  ┌──────────────┐  ┌──────────────┐         │
│  │  ░░░░░░░░░░  │  │  ░░░░░░░░░░  │        │  ← KPI card skeletons
│  │  ░░░░░░░░░░  │  │  ░░░░░░░░░░  │        │
│  └──────────────┘  └──────────────┘         │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │   │  ← Chart skeleton
│  │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │   │
│  │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

**Implementation:** CSS-only animated gradients on placeholder `<div>` elements. No JavaScript needed for the animation itself.

### 8.3 Dirty Flag Pattern

Prevent unnecessary recomputation when data hasn't changed:

```
crashState._dirtyFlags = {
    dashboard: true,       // Set true when data changes
    analysis: true,        // Set true when data changes
    intersection: true,    // Set true when data changes
    pedBike: true,         // Set true when data changes
    hotspots: true         // Set true when data changes
};
```

In `showTab()`:
```
// Before:
if (tabId === 'dashboard' && crashState.loaded) updateDashboard();  // ALWAYS runs

// After:
if (tabId === 'dashboard' && crashState.loaded && crashState._dirtyFlags.dashboard) {
    updateDashboard();
    crashState._dirtyFlags.dashboard = false;
}
```

**When to set dirty flags:**
- New data loaded → all flags = true
- Date filter changed → affected tabs' flags = true
- Location selected → location-dependent tabs' flags = true
- Data upload → all flags = true

### 8.4 Progressive Data Loading Indicator

During Worker-based loading, show a persistent but non-blocking status bar:

```
┌─────────────────────────────────────────────────────────┐
│  Loading crash data... 234,567 / 500,000 records  ████░░│
└─────────────────────────────────────────────────────────┘
```

- Positioned at the top of the page, not a modal overlay
- User can navigate tabs, read documentation, configure settings while data loads
- Disappears when loading completes
- Shows record count and percentage

### 8.5 Estimated Impact

| Metric | Before | After Phase 5 |
|--------|--------|---------------|
| Perceived load time | 3-8 seconds (blank screen) | **< 200ms** (skeleton appears) |
| Tab revisit overhead | Full recomputation | **Skip if clean** (dirty flag) |
| User interaction during load | Blocked | **Fully interactive** |

---

## 9. Architecture Diagrams

### 9.1 Current Architecture

```
┌──────────────────────── MAIN THREAD (ONLY THREAD) ─────────────────────────┐
│                                                                              │
│  ┌─────────┐     ┌────────────┐     ┌──────────────┐     ┌──────────────┐  │
│  │ Fetch   │────►│ PapaParse  │────►│ processRow() │────►│ crashState   │  │
│  │  CSV    │     │ (chunked)  │     │  × 500K      │     │ .sampleRows  │  │
│  └─────────┘     └────────────┘     └──────────────┘     │ .aggregates  │  │
│       │               │                    │              └──────┬───────┘  │
│       │          UI BLOCKED           UI BLOCKED                 │          │
│       │                                                          │          │
│       │              ┌───────────────────────────────────────────┘          │
│       │              ▼                                                      │
│       │   ┌─────────────────────────────────────────────────────────┐      │
│       │   │  Tab Rendering (Dashboard, Map, CMF, Warrants, etc.)   │      │
│       │   │  Chart.js  │  Leaflet  │  DOM Updates  │  Filtering    │      │
│       │   └─────────────────────────────────────────────────────────┘      │
│       │                                                                     │
│       └──► localStorage (settings, small data)                              │
│            IndexedDB (aggregates cache, warrant data)                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Target Architecture (After All Phases)

```
┌─────────────────────── MAIN THREAD ────────────────────────┐
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  UI Layer (Always Responsive)                          │  │
│  │  ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌───────────┐  │  │
│  │  │Dashboard│ │   Map    │ │  CMF    │ │  Reports  │  │  │
│  │  │ Charts  │ │ Leaflet  │ │  Cards  │ │  jsPDF    │  │  │
│  │  └─────────┘ └──────────┘ └─────────┘ └───────────┘  │  │
│  └────────────────────┬──────────────────────────────────┘  │
│                       │ postMessage()                        │
│  ┌────────────────────┴──────────────────────────────────┐  │
│  │  Worker Communication Layer                            │  │
│  │  - Query dispatcher (send query, receive result)       │  │
│  │  - Query cancellation                                  │  │
│  │  - State updater (Worker result → crashState/cmfState) │  │
│  └────────────────────┬──────────────────────────────────┘  │
│                       │                                      │
│  localStorage: user preferences, jurisdiction, filters       │
└───────────────────────┼──────────────────────────────────────┘
                        │ postMessage()
┌───────────────────────┼──────────────────────────────────────┐
│                  DATA WORKER THREAD                            │
│                       │                                        │
│  ┌────────────────────┴──────────────────────────────────┐   │
│  │  Query Engine                                          │   │
│  │  - filterByLocation()    - buildHotspots()             │   │
│  │  - filterByDateRange()   - buildSafetyCategory()       │   │
│  │  - buildCrashProfile()   - getMapPoints(bounds)        │   │
│  │  - getAggregates()       - query cancellation          │   │
│  └────────────────────┬──────────────────────────────────┘   │
│                       │                                        │
│  ┌────────────────────┴──────────────────────────────────┐   │
│  │  Data Store (in Worker memory)                         │   │
│  │  - Full sampleRows[] (500K records)                    │   │
│  │  - Pre-built aggregates                                │   │
│  │  - R-tree spatial index                                │   │
│  │  - Location profile cache                              │   │
│  └────────────────────┬──────────────────────────────────┘   │
│                       │                                        │
│  ┌────────────────────┴──────────────────────────────────┐   │
│  │  Persistence Layer                                     │   │
│  │  IndexedDB: CrashLensDataCache v2                      │   │
│  │  ├── crashRecords (500K, indexed by route/node/date)   │   │
│  │  ├── crashAggregates (pre-computed)                    │   │
│  │  ├── cacheMetadata (freshness tracking)                │   │
│  │  └── cachedProfiles (per-location cache)               │   │
│  └───────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### 9.3 Data Flow: First Visit

```
User opens CRASH LENS (first visit)
        │
        ▼
Main Thread: Show skeleton Dashboard
        │
        ├──► Worker: IndexedDB → cacheMetadata → empty
        │            Fetch CSV from server
        │            Parse with PapaParse
        │            ──► Post progress updates to main thread
        │            Build aggregates
        │            Build R-tree spatial index
        │            Store in IndexedDB (crashRecords + aggregates + metadata)
        │            ──► Post complete result to main thread
        │
        ▼
Main Thread: Receive aggregates
             Set crashState
             Render Dashboard (replace skeleton with real charts)
             Mark data as loaded
```

### 9.4 Data Flow: Return Visit

```
User opens CRASH LENS (return visit)
        │
        ▼
Main Thread: Show skeleton Dashboard
        │
        ├──► Worker: IndexedDB → cacheMetadata → VALID
        │            Load aggregates from IndexedDB
        │            ──► Post aggregates to main thread (< 200ms)
        │            Load sampleRows from IndexedDB in background
        │            Build R-tree spatial index
        │            ──► Post "data ready" when fully loaded
        │
        ▼
Main Thread: Receive aggregates
             Render Dashboard IMMEDIATELY
             User can interact with Dashboard, sidebar, settings
             │
             ▼ (Worker finishes loading full dataset)
             All tabs now available with full data
```

### 9.5 Data Flow: Location Query

```
User selects location in CMF tab
        │
        ▼
Main Thread: Show loading indicator in CMF tab
             Post { type: 'filterByLocation', route: 'US-250', node: '12345' }
        │
        ├──► Worker: Query crashRecords index [route+node]
        │            Build crash profile from results
        │            Cache profile in cachedProfiles
        │            ──► Post { crashes: [...47], crashProfile: {...} }
        │
        ▼
Main Thread: Set cmfState from response
             Render CMF tab (charts, countermeasures, analysis)
```

---

## 10. Migration Strategy

### 10.1 Guiding Principles

1. **No big-bang rewrite** — each phase is independently deployable
2. **Feature flags** — each phase can be toggled via a config flag for testing
3. **Backward compatible** — existing state objects remain the API surface
4. **Measurable** — each phase has clear before/after benchmarks

### 10.2 Phase-by-Phase Migration

#### Phase 1 Migration (Worker for Parsing)

```
Step 1: Create CrashDataWorker inline Blob with PapaParse + processRow()
Step 2: Add feature flag: ENABLE_WORKER_PARSING = true
Step 3: In autoLoadCrashData():
        - If flag ON:  Create Worker, post CSV text, receive results
        - If flag OFF: Use current PapaParse on main thread
Step 4: Worker results → set crashState (same shape as current)
Step 5: All downstream code unchanged (reads from crashState)
```

**Rollback:** Set `ENABLE_WORKER_PARSING = false` → immediate revert to current behavior.

#### Phase 2 Migration (IndexedDB Expansion)

```
Step 1: Bump CrashLensDataCache to version 2 (triggers onupgradeneeded)
Step 2: Add crashRecords + cacheMetadata stores
Step 3: After Worker completes parsing, save to IndexedDB
Step 4: On load, check IndexedDB before fetching CSV
Step 5: Existing crashCacheSave() for aggregates continues unchanged
```

**Rollback:** Delete IndexedDB databases via DevTools → falls back to CSV fetch.

#### Phase 3 Migration (Query Engine)

```
Step 1: Extend Worker with query handler (switch on message type)
Step 2: Create workerQuery() helper on main thread
Step 3: Replace one tab at a time:
        - Start with CMF tab (location filtering)
        - Then Warrants tab (similar pattern)
        - Then Hotspots tab
        - Then Safety Focus tab
        - Then Map tab
Step 4: Each tab migration is independent — mix of Worker and direct queries is fine
```

**Rollback:** Per-tab — revert individual tabs to direct `crashState.sampleRows.filter()` calls.

#### Phase 4 Migration (Spatial Index)

```
Step 1: Include RBush library (~6KB inline or via CDN)
Step 2: Build R-tree after data load (in Worker)
Step 3: Replace map marker rendering loop with viewport query
Step 4: Add moveend/zoomend handler with debounce
Step 5: Remove 50K cap
```

**Rollback:** Remove R-tree query → restore array iteration with 50K cap.

#### Phase 5 Migration (Progressive UI)

```
Step 1: Add CSS skeleton screen styles
Step 2: Add skeleton HTML to each tab container
Step 3: Add dirty flag checks to showTab()
Step 4: Add non-blocking progress bar component
Step 5: Replace modal loading overlay with progress bar
```

**Rollback:** Remove skeleton HTML → loading spinner returns.

---

## 11. IndexedDB Schema Design

### 11.1 Database: `CrashLensDataCache` (Version 2)

#### Object Store: `crashRecords`

| Field | Type | Indexed | Notes |
|-------|------|---------|-------|
| `id` | Auto-increment | Primary key | Database-generated |
| `route` | String | Yes | Road/route name |
| `node` | String | Yes | Intersection node ID |
| `severity` | String | Yes | K/A/B/C/O |
| `collision` | String | No | Collision type |
| `date` | Number | Yes | Timestamp (ms since epoch) |
| `lat` | Number | No | Latitude |
| `lng` | Number | No | Longitude |
| `weather` | String | No | Weather condition |
| `light` | String | No | Light condition |
| `ped` | Boolean | No | Pedestrian involved |
| `bike` | Boolean | No | Bicycle involved |
| `speed` | Boolean | No | Speed-related flag |
| `funcClass` | String | No | Functional classification |
| `intType` | String | No | Intersection type |
| `trafficCtrl` | String | No | Traffic control device |
| `hour` | Number | No | Hour of day (0-23) |
| `dow` | Number | No | Day of week (0-6) |
| `month` | Number | No | Month (1-12) |
| `year` | Number | No | Year |

**Compound Indexes:**
- `[route, node]` — For location-specific queries (CMF, Warrants, B/A)
- `[route, severity]` — For route-level severity analysis
- `[year, severity]` — For temporal severity trends

#### Object Store: `crashAggregates` (Unchanged)

| Field | Type | Notes |
|-------|------|-------|
| `cacheKey` | String | Primary key (jurisdiction + filter + version) |
| `aggregates` | Object | Full `crashState.aggregates` structure |
| `years` | Array | Sorted year list |
| `routes` | Array | Sorted route list |
| `totalRows` | Number | Record count |
| `cachedAt` | String | ISO timestamp |
| `expiresAt` | Number | Expiration timestamp |

#### Object Store: `cacheMetadata`

| Field | Type | Notes |
|-------|------|-------|
| `key` | String | Primary key (e.g., 'current') |
| `jurisdiction` | String | e.g., 'henrico' |
| `filterProfile` | String | e.g., 'countyOnly' |
| `dataHash` | String | SHA-256 of CSV or Last-Modified header |
| `recordCount` | Number | Total records cached |
| `cachedAt` | String | ISO timestamp |
| `expiresAt` | Number | Expiration timestamp (30 days) |
| `schemaVersion` | Number | For future migrations |
| `appVersion` | String | CRASH LENS version that wrote cache |

#### Object Store: `cachedProfiles`

| Field | Type | Notes |
|-------|------|-------|
| `locationKey` | String | Primary key: `${route}::${node}` |
| `crashProfile` | Object | Full crash profile (severity, collision types, etc.) |
| `crashCount` | Number | Total crashes at location |
| `dateRange` | Object | `{ start, end }` for the profile |
| `lastUpdated` | Number | Timestamp |

---

## 12. Performance Benchmarks & Targets

### 12.1 Key Metrics to Track

| Metric | How to Measure |
|--------|---------------|
| **Time to Interactive (TTI)** | Time from page load to user can click tabs |
| **Time to First Data (TTFD)** | Time from page load to Dashboard shows real data |
| **Main Thread Block Duration** | Total time main thread is unresponsive during load |
| **Tab Switch Latency** | Time from tab click to tab content rendered |
| **Location Query Latency** | Time from location select to crash profile displayed |
| **Map Viewport Query** | Time from pan/zoom to markers updated |
| **Memory Usage** | Peak `performance.memory.usedJSHeapSize` |

### 12.2 Performance Targets

| Metric | Current (Estimated) | Phase 1 Target | Phase 3 Target | Phase 5 Target |
|--------|--------------------:|---------------:|---------------:|---------------:|
| TTI (first visit) | 5-10s | 1-2s | 1-2s | < 500ms |
| TTI (return visit) | 5-10s | 5-10s | < 1s | < 500ms |
| TTFD (first visit) | 5-10s | 5-10s | 5-10s | 5-10s (skeleton at < 200ms) |
| TTFD (return visit) | 5-10s | 5-10s | < 500ms | < 500ms |
| Main thread block | 3-8s | < 200ms | < 100ms | < 100ms |
| Tab switch (cached) | 100-500ms | 100-500ms | < 50ms | < 50ms |
| Location query | 100-300ms | 100-300ms | < 50ms | < 50ms |
| Map viewport query | N/A (full render) | N/A | < 5ms | < 5ms |
| Memory (peak) | ~600MB | ~600MB | ~100MB main thread | ~100MB main thread |

### 12.3 Measurement Implementation

Add a `performance.mark()` / `performance.measure()` instrumentation layer:

```
// Key timing points to instrument:
performance.mark('data-load-start');
performance.mark('worker-parse-complete');
performance.mark('dashboard-render-start');
performance.mark('dashboard-render-complete');
performance.mark('tab-switch-start');
performance.mark('tab-content-ready');

// Calculate:
performance.measure('csv-parse-time', 'data-load-start', 'worker-parse-complete');
performance.measure('dashboard-render', 'dashboard-render-start', 'dashboard-render-complete');
performance.measure('tab-switch', 'tab-switch-start', 'tab-content-ready');
```

Optionally expose these in a hidden developer panel for ongoing monitoring.

---

## 13. Risk Mitigation

### 13.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Worker Blob creation fails in some browsers | Low | High | Feature detection + fallback to main-thread parsing |
| IndexedDB storage quota exceeded | Low | Medium | Monitor storage usage; implement LRU eviction for old jurisdictions |
| IndexedDB corrupted (browser crash during write) | Low | Medium | Transactional writes + verify on read + fallback to CSV re-parse |
| R-tree build time too slow for 500K points | Very Low | Low | RBush handles 1M+ points in < 500ms; benchmark confirms |
| Worker memory limit reached | Low | Medium | 500K records ≈ 200MB; well within Worker limits (4GB+) |
| Safari IndexedDB quota prompt annoys users | Medium | Low | Stay under 500MB; most datasets are 150-300MB |
| Message serialization overhead between threads | Medium | Low | Use Transferable ArrayBuffers for large payloads (Phase 3) |

### 13.2 Architectural Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Single-file constraint makes Worker code hard to maintain | High | Medium | Clear inline code organization with comment delimiters; consider build step in future |
| State synchronization bugs between main thread and Worker | Medium | High | Single source of truth in Worker; main thread only holds derived views |
| Race conditions during rapid tab switching | Medium | Medium | Query cancellation protocol; latest-wins semantics |
| Debugging Worker code is harder | Medium | Low | Chrome DevTools supports Worker debugging; add verbose logging in dev mode |

### 13.3 Rollback Plan

Every phase includes a feature flag that can disable it independently:

```
const PERFORMANCE_FLAGS = {
    WORKER_PARSING: true,       // Phase 1: false = use main-thread PapaParse
    INDEXEDDB_RECORDS: true,     // Phase 2: false = don't cache raw records
    WORKER_QUERIES: true,        // Phase 3: false = use direct array filtering
    SPATIAL_INDEX: true,         // Phase 4: false = use array iteration + 50K cap
    SKELETON_SCREENS: true       // Phase 5: false = use current loading spinners
};
```

---

## 14. Testing Plan

### 14.1 Unit Tests (Per Phase)

#### Phase 1: Worker Parsing

| Test | Validates |
|------|-----------|
| Worker produces same aggregates as main-thread parsing | Data correctness |
| Worker handles empty CSV | Edge case |
| Worker handles malformed rows | Error resilience |
| Worker sends progress updates | Communication protocol |
| Worker handles Virginia + Colorado state adapters | Multi-state |
| Fallback to main thread when Worker unavailable | Graceful degradation |

#### Phase 2: IndexedDB Storage

| Test | Validates |
|------|-----------|
| crashRecords store holds 500K records | Storage capacity |
| Index queries return correct results | Query correctness |
| Cache invalidation on jurisdiction change | Freshness logic |
| Cache invalidation on TTL expiry | Freshness logic |
| Concurrent tab access doesn't corrupt | Concurrency safety |
| Return visit loads from cache | Cache hit path |
| First visit stores to cache | Cache write path |

#### Phase 3: Query Engine

| Test | Validates |
|------|-----------|
| `filterByLocation` returns correct crashes | Query correctness |
| `filterByDateRange` respects boundaries | Boundary conditions |
| Compound filter (location + date) works | Combined queries |
| Query cancellation prevents stale results | Race condition handling |
| Results match current `Array.filter()` output | Backward compatibility |

#### Phase 4: Spatial Index

| Test | Validates |
|------|-----------|
| R-tree viewport query returns all points in bounds | Spatial correctness |
| Points at boundary are included | Edge cases |
| Empty viewport returns empty set | Edge case |
| Full viewport returns all points | Edge case |
| R-tree rebuild after data change | Data freshness |

### 14.2 Integration Tests

| Test | Validates |
|------|-----------|
| Upload CSV → Worker parse → IndexedDB store → Dashboard render | Full pipeline |
| Return visit → IndexedDB load → Dashboard render (< 500ms) | Cache path |
| Location select in Hotspots → CMF tab shows correct profile | Cross-tab data flow |
| Date filter change → all affected tabs update correctly | Filter propagation |
| Map pan → viewport query → correct markers displayed | Spatial pipeline |
| Worker error → fallback to main thread → data still loads | Error recovery |

### 14.3 Performance Tests

| Test | Pass Criteria |
|------|--------------|
| First visit TTI | < 2 seconds (skeleton visible) |
| Return visit TTFD | < 500ms (real data displayed) |
| Main thread block during load | < 200ms total |
| Location query (Worker) | < 50ms |
| Map viewport query (R-tree) | < 5ms |
| Tab switch (cached tab, dirty=false) | < 20ms |

### 14.4 Browser Compatibility Tests

Test on:
- Chrome 90+ (primary — most government desktops)
- Firefox 90+ (secondary)
- Edge 90+ (Chromium-based, common in government)
- Safari 15+ (macOS users)
- Chrome on Android tablet (field use)
- Safari on iPad (field use)

---

## 15. Implementation Timeline

### 15.1 Phase Durations (Estimated)

| Phase | Description | Estimated Effort | Dependencies |
|-------|------------|-----------------|--------------|
| **Phase 1** | Web Worker for CSV Parsing | 3-5 days | None |
| **Phase 2** | IndexedDB Expansion | 3-5 days | Phase 1 (Worker writes to IDB) |
| **Phase 3** | Worker Query Engine | 5-8 days | Phase 1 + Phase 2 |
| **Phase 4** | Spatial Indexing for Map | 2-4 days | None (parallel with Phase 1-3) |
| **Phase 5** | Skeleton Screens & Dirty Flags | 2-3 days | None (parallel with any phase) |
| **Testing** | Full integration & performance | 3-5 days | All phases |
| **Total** | | **18-30 days** | |

### 15.2 Recommended Execution Order

```
Week 1-2:   Phase 1 (Worker Parsing) + Phase 5 (Skeleton Screens) in parallel
Week 2-3:   Phase 2 (IndexedDB Expansion) + Phase 4 (Spatial Index) in parallel
Week 3-5:   Phase 3 (Worker Query Engine)
Week 5-6:   Integration testing, performance benchmarking, browser compatibility
```

### 15.3 Milestones

| Milestone | Definition of Done |
|-----------|-------------------|
| **M1: Non-Blocking Load** | CSV parsing happens in Worker; UI stays responsive throughout; Dashboard renders identically to current |
| **M2: Instant Return** | Return visits load from IndexedDB in < 500ms; cache invalidation works correctly |
| **M3: Background Queries** | At least CMF + Warrants tabs use Worker queries; no main-thread freezes on location selection |
| **M4: Unlimited Map** | Map displays all crashes via R-tree viewport query; 50K cap removed; pan/zoom is smooth |
| **M5: Polished UX** | Skeleton screens on all tabs; dirty flags prevent unnecessary recomputation; non-blocking progress bar |

---

## 16. Appendix: Browser Compatibility

### 16.1 Web Workers

| Browser | Supported Since | Notes |
|---------|----------------|-------|
| Chrome | v4 (2010) | Full support including Blob URLs |
| Firefox | v3.5 (2009) | Full support |
| Safari | v4 (2009) | Full support; Blob URL Workers since Safari 8 |
| Edge | v12 (2015) | Full support |
| IE11 | Yes | Basic support — but IE11 is EOL |

### 16.2 IndexedDB

| Browser | Supported Since | Storage Limit |
|---------|----------------|--------------|
| Chrome | v24 (2013) | Up to 80% of disk |
| Firefox | v16 (2012) | Up to 50% of disk |
| Safari | v10 (2016) | 1 GB before prompt |
| Edge | v12 (2015) | Same as Chrome |

### 16.3 Transferable Objects (ArrayBuffer)

| Browser | Supported Since |
|---------|----------------|
| Chrome | v17 (2012) |
| Firefox | v18 (2013) |
| Safari | v6 (2012) |
| Edge | v12 (2015) |

### 16.4 RBush (R-tree Library)

- Pure JavaScript — no browser API dependencies
- Works everywhere ES5 is supported
- ~6KB minified + gzipped
- npm: `rbush` | CDN: available on unpkg/jsdelivr
- GitHub: https://github.com/mourner/rbush

### 16.5 Performance API (Benchmarking)

| API | Chrome | Firefox | Safari | Edge |
|-----|--------|---------|--------|------|
| `performance.mark()` | v28 | v38 | v11 | v12 |
| `performance.measure()` | v28 | v38 | v11 | v12 |
| `performance.memory` | Yes | No | No | Yes |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | February 2026 | Claude | Initial plan based on codebase analysis |
