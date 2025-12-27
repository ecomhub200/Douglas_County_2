# Visualize Impact Module - Technical Specification

## Document Purpose

This specification provides implementation details for adding a 2D animated visualization feature to CRASH LENS. The feature shows before/after impact of countermeasures using browser-based SVG animations driven by D3.js.

---

## 1. Architecture Overview

### 1.1 Integration Approach

The visualization module integrates into the existing single-file architecture (`app/index.html`) following established patterns:

```
┌─────────────────────────────────────────────────────────────┐
│                     app/index.html                          │
├─────────────────────────────────────────────────────────────┤
│  <style>                                                    │
│    /* === VISUALIZE IMPACT STYLES === */                    │
│    .viz-modal { ... }                                       │
│    .viz-intersection { ... }                                │
│    @keyframes viz-vehicle-move { ... }                      │
│  </style>                                                   │
├─────────────────────────────────────────────────────────────┤
│  <body>                                                     │
│    <!-- Existing content -->                                │
│    <!-- CMF Tab: Add button to .cmf-card-actions -->        │
│                                                             │
│    <!-- === VISUALIZE IMPACT MODAL === -->                  │
│    <div id="vizModal" class="modal-overlay">                │
│      <!-- Modal content -->                                 │
│    </div>                                                   │
│  </body>                                                    │
├─────────────────────────────────────────────────────────────┤
│  <script>                                                   │
│    // === VISUALIZE IMPACT MODULE ===                       │
│    const VizModule = (function() { ... })();                │
│  </script>                                                  │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Dependencies

**Required (add to `<head>`):**
```html
<script src="https://d3js.org/d3.v7.min.js"></script>
```

**Already Available:**
- `html2canvas` - For screenshot export (line 43)
- `Chart.js` - Reference for animation patterns (line 40)
- `jsPDF` - For report integration (line 41)

### 1.3 File Locations

| Component | Location in index.html | Approximate Line |
|-----------|------------------------|------------------|
| CSS Styles | After line ~1700 (after existing animations) | New section |
| Modal HTML | After line ~7500 (after other modals) | New section |
| JavaScript | After line ~29900 (after CMF functions) | New section |
| Button injection | Line ~29289 (`.cmf-card-actions`) | Modify existing |

---

## 2. State Management

### 2.1 New State Object

```javascript
// Add after cmfState definition (line ~26940)
const vizState = {
    isOpen: false,
    isPlaying: false,
    currentView: 'split',        // 'split', 'before', 'after'

    // Current visualization context
    countermeasure: null,        // CMF object from cmfState
    location: null,              // From cmfState.selectedLocation
    crashProfile: null,          // From buildCMFCrashProfile()

    // Configuration
    config: {
        timeOfDay: 'pm-peak',    // 'am-peak', 'pm-peak', 'off-peak'
        weather: 'dry',          // 'dry', 'wet', 'night'
        duration: 60             // Animation loop duration in seconds
    },

    // Animation state
    animationId: null,           // requestAnimationFrame ID
    currentTime: 0,              // Current playback position

    // D3 references
    svgBefore: null,
    svgAfter: null,

    // Computed metrics (from crash data)
    metrics: {
        beforeConflicts: 0,
        afterConflicts: 0,
        reductionPercent: 0,
        annualSavings: 0
    }
};
```

### 2.2 Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Existing Data Sources                     │
├─────────────────────────────────────────────────────────────┤
│  cmfState.selectedLocation     → Location name, type        │
│  cmfState.filteredCrashes      → Crash records for location │
│  cmfState.crashProfile         → Severity, types, patterns  │
│  cmfState.database[cmfId]      → CMF details, reduction %   │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│              vizState (Computed on Open)                     │
├─────────────────────────────────────────────────────────────┤
│  crashProfile.collisionTypes   → Animation scenario type    │
│  crashProfile.severity         → Conflict intensity colors  │
│  crashProfile.timeOfDay        → Default time selection     │
│  cmf.crfPct                    → After-state reduction      │
│  cmf.costTier                  → Cost estimate display      │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                 Visualization Rendering                      │
├─────────────────────────────────────────────────────────────┤
│  Template Selection → Based on collision type dominance     │
│  Vehicle Paths      → Derived from template geometry        │
│  Conflict Points    → Positioned at intersection center     │
│  Animation Timing   → Based on crash frequency              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. CSS Specifications

### 3.1 Modal Styles

```css
/* === VISUALIZE IMPACT STYLES === */

/* Modal Container - follows existing .modal-overlay pattern */
.viz-modal-overlay {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.85);
    z-index: 9999;
    justify-content: center;
    align-items: center;
}
.viz-modal-overlay.visible {
    display: flex;
}

/* Modal Content */
.viz-modal {
    background: var(--dark);
    border-radius: var(--radius-lg);
    width: 95%;
    max-width: 1400px;
    max-height: 95vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    animation: modalSlideIn 0.3s;
}

/* Header */
.viz-header {
    background: linear-gradient(135deg, #1e3a5f 0%, #1e40af 100%);
    padding: 1rem 1.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: white;
}
.viz-header-title {
    font-size: 1.1rem;
    font-weight: 600;
}
.viz-header-subtitle {
    font-size: 0.85rem;
    opacity: 0.8;
    margin-top: 0.25rem;
}
.viz-close-btn {
    background: none;
    border: none;
    color: white;
    font-size: 1.5rem;
    cursor: pointer;
    padding: 0.25rem;
    opacity: 0.8;
    transition: opacity 0.2s;
}
.viz-close-btn:hover {
    opacity: 1;
}

/* View Toggle */
.viz-view-toggle {
    background: rgba(255, 255, 255, 0.1);
    padding: 0.5rem 1.5rem;
    display: flex;
    gap: 0.5rem;
    align-items: center;
}
.viz-view-btn {
    padding: 0.4rem 1rem;
    border: none;
    background: transparent;
    color: rgba(255, 255, 255, 0.6);
    font-size: 0.85rem;
    border-radius: var(--radius);
    cursor: pointer;
    transition: all 0.2s;
}
.viz-view-btn:hover {
    color: white;
    background: rgba(255, 255, 255, 0.1);
}
.viz-view-btn.active {
    background: var(--primary);
    color: white;
}

/* Main Content Area */
.viz-content {
    flex: 1;
    display: flex;
    min-height: 400px;
    overflow: hidden;
}
.viz-panel {
    flex: 1;
    position: relative;
    display: flex;
    flex-direction: column;
}
.viz-panel.hidden {
    display: none;
}
.viz-divider {
    width: 2px;
    background: rgba(255, 255, 255, 0.2);
}

/* Panel Label */
.viz-panel-label {
    position: absolute;
    top: 1rem;
    left: 1rem;
    padding: 0.4rem 1rem;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
    z-index: 10;
}
.viz-panel-label.before {
    background: #dc2626;
    color: white;
}
.viz-panel-label.after {
    background: #16a34a;
    color: white;
}

/* SVG Container */
.viz-svg-container {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    padding: 2rem;
}
.viz-svg-container svg {
    max-width: 100%;
    max-height: 100%;
}

/* Stats Overlay */
.viz-stats-overlay {
    position: absolute;
    bottom: 1rem;
    left: 1rem;
    right: 1rem;
    background: rgba(0, 0, 0, 0.75);
    backdrop-filter: blur(4px);
    border-radius: var(--radius);
    padding: 0.75rem;
}
.viz-stats-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
    text-align: center;
}
.viz-stat-value {
    font-size: 1.25rem;
    font-weight: 700;
}
.viz-stat-value.danger { color: #f87171; }
.viz-stat-value.success { color: #4ade80; }
.viz-stat-value.warning { color: #fbbf24; }
.viz-stat-label {
    font-size: 0.7rem;
    color: rgba(255, 255, 255, 0.6);
    margin-top: 0.25rem;
}
.viz-stat-change {
    font-size: 0.7rem;
    margin-top: 0.15rem;
}
.viz-stat-change.positive { color: #4ade80; }
.viz-stat-change.negative { color: #f87171; }

/* Playback Controls */
.viz-controls {
    background: #111827;
    padding: 1rem 1.5rem;
    display: flex;
    align-items: center;
    gap: 1rem;
}
.viz-play-btn {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    border: none;
    background: var(--primary);
    color: white;
    font-size: 1.25rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
}
.viz-play-btn:hover {
    background: var(--primary-dark);
    transform: scale(1.05);
}
.viz-reset-btn {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    border: none;
    background: #374151;
    color: white;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
}
.viz-reset-btn:hover {
    background: #4b5563;
}

/* Progress Bar */
.viz-progress {
    flex: 1;
}
.viz-progress-bar {
    height: 6px;
    background: #374151;
    border-radius: 3px;
    cursor: pointer;
    overflow: hidden;
}
.viz-progress-fill {
    height: 100%;
    background: var(--primary);
    border-radius: 3px;
    transition: width 0.1s linear;
}
.viz-progress-times {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: #9ca3af;
    margin-top: 0.25rem;
}

/* Export Buttons */
.viz-export-btns {
    display: flex;
    gap: 0.5rem;
}
.viz-export-btn {
    padding: 0.5rem 1rem;
    border-radius: var(--radius);
    border: none;
    font-size: 0.8rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 0.4rem;
    transition: all 0.2s;
}
.viz-export-btn.secondary {
    background: #374151;
    color: white;
}
.viz-export-btn.secondary:hover {
    background: #4b5563;
}
.viz-export-btn.primary {
    background: #059669;
    color: white;
}
.viz-export-btn.primary:hover {
    background: #047857;
}

/* Summary Bar */
.viz-summary {
    background: #1f2937;
    padding: 0.75rem 1.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 1rem;
    border-top: 1px solid #374151;
}
.viz-summary-metrics {
    display: flex;
    gap: 2rem;
}
.viz-summary-metric {
    font-size: 0.85rem;
}
.viz-summary-metric .label {
    color: #9ca3af;
}
.viz-summary-metric .value {
    font-weight: 700;
    margin-left: 0.5rem;
}
.viz-summary-metric .value.positive { color: #4ade80; }
.viz-powered {
    font-size: 0.75rem;
    color: #6b7280;
}
```

### 3.2 Animation Keyframes

```css
/* Vehicle movement animation */
@keyframes viz-vehicle-horizontal {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
}

@keyframes viz-vehicle-vertical {
    0% { transform: translateY(-100%); }
    100% { transform: translateY(100%); }
}

/* Conflict pulse */
@keyframes viz-conflict-pulse {
    0%, 100% {
        transform: scale(1);
        opacity: 0.8;
    }
    50% {
        transform: scale(1.3);
        opacity: 0.4;
    }
}

/* Risk indicator breathing */
@keyframes viz-risk-breathe {
    0%, 100% {
        box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);
    }
    50% {
        box-shadow: 0 0 20px 10px rgba(239, 68, 68, 0);
    }
}

/* Safe flow indicator */
@keyframes viz-safe-flow {
    0%, 100% { opacity: 0.6; }
    50% { opacity: 1; }
}
```

### 3.3 Configuration Modal Styles

```css
/* Config Modal */
.viz-config-modal {
    background: white;
    border-radius: var(--radius-lg);
    max-width: 500px;
    width: 90%;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    animation: modalSlideIn 0.3s;
}
.viz-config-header {
    padding: 1.25rem 1.5rem;
    border-bottom: 1px solid var(--gray-light);
}
.viz-config-header h3 {
    font-size: 1.1rem;
    color: var(--dark);
    margin: 0;
}
.viz-config-header p {
    font-size: 0.85rem;
    color: var(--gray);
    margin: 0.25rem 0 0;
}
.viz-config-body {
    padding: 1.5rem;
}
.viz-config-section {
    margin-bottom: 1.5rem;
}
.viz-config-section:last-child {
    margin-bottom: 0;
}
.viz-config-label {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--dark);
    margin-bottom: 0.75rem;
    display: block;
}
.viz-config-options {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.5rem;
}
.viz-config-option {
    padding: 0.75rem;
    border: 2px solid var(--gray-light);
    border-radius: var(--radius);
    background: white;
    cursor: pointer;
    text-align: center;
    transition: all 0.2s;
}
.viz-config-option:hover {
    border-color: var(--primary);
    background: var(--primary-light);
}
.viz-config-option.selected {
    border-color: var(--primary);
    background: var(--primary-light);
}
.viz-config-option-icon {
    font-size: 1.5rem;
    margin-bottom: 0.25rem;
}
.viz-config-option-label {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--dark);
}
.viz-config-option-desc {
    font-size: 0.7rem;
    color: var(--gray);
}
.viz-config-footer {
    padding: 1rem 1.5rem;
    border-top: 1px solid var(--gray-light);
    display: flex;
    justify-content: flex-end;
    gap: 0.75rem;
    background: var(--light);
    border-radius: 0 0 var(--radius-lg) var(--radius-lg);
}
```

---

## 4. HTML Structure

### 4.1 Modal HTML

```html
<!-- === VISUALIZE IMPACT MODAL === -->
<!-- Add after existing modals, around line 7500 -->

<!-- Configuration Modal -->
<div id="vizConfigModal" class="modal-overlay">
    <div class="viz-config-modal">
        <div class="viz-config-header">
            <h3 id="vizConfigTitle">Configure Simulation</h3>
            <p id="vizConfigSubtitle">Signal Installation at Broad St & Main St</p>
        </div>
        <div class="viz-config-body">
            <!-- Time of Day -->
            <div class="viz-config-section">
                <label class="viz-config-label">Time of Day</label>
                <div class="viz-config-options" id="vizTimeOptions">
                    <div class="viz-config-option" data-value="am-peak" onclick="VizModule.setConfig('timeOfDay', 'am-peak')">
                        <div class="viz-config-option-icon">🌅</div>
                        <div class="viz-config-option-label">AM Peak</div>
                        <div class="viz-config-option-desc">7-9 AM</div>
                    </div>
                    <div class="viz-config-option selected" data-value="pm-peak" onclick="VizModule.setConfig('timeOfDay', 'pm-peak')">
                        <div class="viz-config-option-icon">🌆</div>
                        <div class="viz-config-option-label">PM Peak</div>
                        <div class="viz-config-option-desc">4-6 PM</div>
                    </div>
                    <div class="viz-config-option" data-value="off-peak" onclick="VizModule.setConfig('timeOfDay', 'off-peak')">
                        <div class="viz-config-option-icon">☀️</div>
                        <div class="viz-config-option-label">Off-Peak</div>
                        <div class="viz-config-option-desc">Midday</div>
                    </div>
                </div>
            </div>

            <!-- Weather -->
            <div class="viz-config-section">
                <label class="viz-config-label">Conditions</label>
                <div class="viz-config-options" id="vizWeatherOptions">
                    <div class="viz-config-option selected" data-value="dry" onclick="VizModule.setConfig('weather', 'dry')">
                        <div class="viz-config-option-icon">☀️</div>
                        <div class="viz-config-option-label">Dry</div>
                    </div>
                    <div class="viz-config-option" data-value="wet" onclick="VizModule.setConfig('weather', 'wet')">
                        <div class="viz-config-option-icon">🌧️</div>
                        <div class="viz-config-option-label">Wet</div>
                    </div>
                    <div class="viz-config-option" data-value="night" onclick="VizModule.setConfig('weather', 'night')">
                        <div class="viz-config-option-icon">🌙</div>
                        <div class="viz-config-option-label">Night</div>
                    </div>
                </div>
            </div>

            <!-- Preview Info -->
            <div class="info-box info" style="margin-top:1rem">
                <span class="icon">💡</span>
                <div class="content">
                    <p style="margin:0;font-size:.85rem"><strong>What you'll see:</strong> Side-by-side comparison showing how traffic flow changes with the countermeasure applied.</p>
                </div>
            </div>
        </div>
        <div class="viz-config-footer">
            <button class="btn btn-secondary" onclick="VizModule.closeConfig()">Cancel</button>
            <button class="btn btn-primary" onclick="VizModule.startVisualization()">
                Generate Visualization →
            </button>
        </div>
    </div>
</div>

<!-- Main Visualization Modal -->
<div id="vizModal" class="viz-modal-overlay">
    <div class="viz-modal">
        <!-- Header -->
        <div class="viz-header">
            <div>
                <div class="viz-header-title" id="vizTitle">Simulation: Install Traffic Signal</div>
                <div class="viz-header-subtitle" id="vizSubtitle">Broad St & Main St • PM Peak • Dry</div>
            </div>
            <button class="viz-close-btn" onclick="VizModule.close()">&times;</button>
        </div>

        <!-- View Toggle -->
        <div class="viz-view-toggle">
            <span style="color:rgba(255,255,255,.6);font-size:.85rem;margin-right:.5rem">View:</span>
            <button class="viz-view-btn active" data-view="split" onclick="VizModule.setView('split')">Split View</button>
            <button class="viz-view-btn" data-view="before" onclick="VizModule.setView('before')">Before Only</button>
            <button class="viz-view-btn" data-view="after" onclick="VizModule.setView('after')">After Only</button>
        </div>

        <!-- Main Content -->
        <div class="viz-content">
            <!-- Before Panel -->
            <div class="viz-panel" id="vizPanelBefore">
                <div class="viz-panel-label before">BEFORE (Current)</div>
                <div class="viz-svg-container" id="vizSvgBefore">
                    <!-- D3 renders SVG here -->
                </div>
                <div class="viz-stats-overlay">
                    <div class="viz-stats-grid">
                        <div>
                            <div class="viz-stat-value danger" id="vizBeforeConflicts">4.6/hr</div>
                            <div class="viz-stat-label">Conflicts</div>
                        </div>
                        <div>
                            <div class="viz-stat-value warning" id="vizBeforeDelay">23.5s</div>
                            <div class="viz-stat-label">Avg Delay</div>
                        </div>
                        <div>
                            <div class="viz-stat-value danger" id="vizBeforeRisk">High</div>
                            <div class="viz-stat-label">Risk Level</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Divider -->
            <div class="viz-divider" id="vizDivider"></div>

            <!-- After Panel -->
            <div class="viz-panel" id="vizPanelAfter">
                <div class="viz-panel-label after">AFTER (With Countermeasure)</div>
                <div class="viz-svg-container" id="vizSvgAfter">
                    <!-- D3 renders SVG here -->
                </div>
                <div class="viz-stats-overlay">
                    <div class="viz-stats-grid">
                        <div>
                            <div class="viz-stat-value success" id="vizAfterConflicts">0.8/hr</div>
                            <div class="viz-stat-label">Conflicts</div>
                            <div class="viz-stat-change positive" id="vizConflictChange">↓ 83%</div>
                        </div>
                        <div>
                            <div class="viz-stat-value success" id="vizAfterDelay">18.2s</div>
                            <div class="viz-stat-label">Avg Delay</div>
                            <div class="viz-stat-change positive" id="vizDelayChange">↓ 23%</div>
                        </div>
                        <div>
                            <div class="viz-stat-value success" id="vizAfterRisk">Low</div>
                            <div class="viz-stat-label">Risk Level</div>
                            <div class="viz-stat-change positive">Improved</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Playback Controls -->
        <div class="viz-controls">
            <button class="viz-play-btn" id="vizPlayBtn" onclick="VizModule.togglePlay()">
                <span id="vizPlayIcon">▶</span>
            </button>
            <button class="viz-reset-btn" onclick="VizModule.reset()" title="Reset">↺</button>

            <div class="viz-progress">
                <div class="viz-progress-bar" onclick="VizModule.seek(event)">
                    <div class="viz-progress-fill" id="vizProgressFill" style="width:0%"></div>
                </div>
                <div class="viz-progress-times">
                    <span id="vizCurrentTime">0:00</span>
                    <span id="vizTotalTime">1:00</span>
                </div>
            </div>

            <div class="viz-export-btns">
                <button class="viz-export-btn secondary" onclick="VizModule.screenshot()">
                    📷 Screenshot
                </button>
                <button class="viz-export-btn primary" onclick="VizModule.addToReport()">
                    📄 Add to Report
                </button>
            </div>
        </div>

        <!-- Summary Bar -->
        <div class="viz-summary">
            <div class="viz-summary-metrics">
                <div class="viz-summary-metric">
                    <span class="label">Projected Crash Reduction:</span>
                    <span class="value positive" id="vizReduction">44% (CMF: 0.56)</span>
                </div>
                <div class="viz-summary-metric">
                    <span class="label">Estimated Annual Savings:</span>
                    <span class="value positive" id="vizSavings">$480,000</span>
                </div>
                <div class="viz-summary-metric">
                    <span class="label">Implementation Cost:</span>
                    <span class="value" id="vizCost">$175,000</span>
                </div>
            </div>
            <div class="viz-powered">Visualization powered by D3.js</div>
        </div>
    </div>
</div>
```

### 4.2 Button Integration Point

**Location:** Line ~29289 in the CMF card rendering function

**Current code:**
```javascript
<div class="cmf-card-actions">
    <button class="btn btn-sm btn-primary" onclick="copyCMFToClipboard(...)">📋 Copy</button>
</div>
```

**Modified code:**
```javascript
<div class="cmf-card-actions">
    <button class="btn btn-sm btn-soft-info" onclick="VizModule.openConfig('${cmf.id}')" title="Visualize impact of this countermeasure">
        👁️ Visualize
    </button>
    <button class="btn btn-sm btn-primary" onclick="copyCMFToClipboard(...)">📋 Copy</button>
</div>
```

---

## 5. JavaScript Module

### 5.1 Module Structure (IIFE Pattern)

```javascript
// === VISUALIZE IMPACT MODULE ===
// Add after CMF functions, around line 29900

const VizModule = (function() {
    'use strict';

    // ==================== STATE ====================
    const state = {
        isOpen: false,
        isPlaying: false,
        currentView: 'split',
        countermeasure: null,
        location: null,
        crashProfile: null,
        config: {
            timeOfDay: 'pm-peak',
            weather: 'dry',
            duration: 60
        },
        animationId: null,
        currentTime: 0,
        svgBefore: null,
        svgAfter: null,
        metrics: {
            beforeConflicts: 0,
            afterConflicts: 0,
            reductionPercent: 0,
            annualSavings: 0
        }
    };

    // ==================== CONSTANTS ====================
    const COLORS = {
        road: '#4b5563',
        roadLine: '#9ca3af',
        vehicle: '#3b82f6',
        vehicleAlt: '#f59e0b',
        conflict: '#dc2626',
        safe: '#22c55e',
        signal: {
            red: '#ef4444',
            yellow: '#fbbf24',
            green: '#22c55e'
        }
    };

    const TEMPLATES = {
        '4leg-stopcontrolled': { /* ... */ },
        '4leg-signalized': { /* ... */ },
        '3leg-unsignalized': { /* ... */ },
        'crosswalk': { /* ... */ },
        'corridor': { /* ... */ }
    };

    // ==================== TEMPLATE SELECTION ====================
    function selectTemplate(crashProfile, countermeasure) {
        // Analyze crash patterns to select appropriate template
        const dominantType = getDominantCrashType(crashProfile);
        const cmfCategory = countermeasure.category || '';

        // Signal-related countermeasures
        if (cmfCategory.includes('Signal') || cmfCategory.includes('Traffic Control')) {
            if (crashProfile.isIntersection) {
                return '4leg-signalized';
            }
            return 'crosswalk';
        }

        // Intersection geometry
        if (cmfCategory.includes('Roundabout')) {
            return '4leg-stopcontrolled'; // Will show transformation
        }

        // Pedestrian focused
        if (crashProfile.pedestrianPercent > 20) {
            return 'crosswalk';
        }

        // Default based on collision type
        if (dominantType === 'Angle' || dominantType === 'Left Turn') {
            return '4leg-stopcontrolled';
        }

        return 'corridor';
    }

    function getDominantCrashType(profile) {
        if (!profile || !profile.collisionTypes) return 'Angle';

        const types = profile.collisionTypes;
        let max = 0;
        let dominant = 'Angle';

        for (const [type, count] of Object.entries(types)) {
            if (count > max) {
                max = count;
                dominant = type;
            }
        }
        return dominant;
    }

    // ==================== SVG RENDERING ====================
    function renderIntersection(containerId, template, isAfterState, config) {
        const container = document.getElementById(containerId);
        if (!container) return null;

        container.innerHTML = '';

        const width = 400;
        const height = 400;
        const center = { x: width / 2, y: height / 2 };

        const svg = d3.select(container)
            .append('svg')
            .attr('viewBox', `0 0 ${width} ${height}`)
            .attr('preserveAspectRatio', 'xMidYMid meet');

        // Background
        svg.append('rect')
            .attr('width', width)
            .attr('height', height)
            .attr('fill', config.weather === 'night' ? '#0f172a' : '#1e293b');

        // Roads
        const roadWidth = 60;

        // Horizontal road
        svg.append('rect')
            .attr('x', 0)
            .attr('y', center.y - roadWidth / 2)
            .attr('width', width)
            .attr('height', roadWidth)
            .attr('fill', COLORS.road);

        // Vertical road
        svg.append('rect')
            .attr('x', center.x - roadWidth / 2)
            .attr('y', 0)
            .attr('width', roadWidth)
            .attr('height', height)
            .attr('fill', COLORS.road);

        // Center lane markings
        svg.append('line')
            .attr('x1', 0).attr('y1', center.y)
            .attr('x2', center.x - roadWidth / 2).attr('y2', center.y)
            .attr('stroke', '#fbbf24')
            .attr('stroke-width', 2)
            .attr('stroke-dasharray', '10,10');

        svg.append('line')
            .attr('x1', center.x + roadWidth / 2).attr('y1', center.y)
            .attr('x2', width).attr('y2', center.y)
            .attr('stroke', '#fbbf24')
            .attr('stroke-width', 2)
            .attr('stroke-dasharray', '10,10');

        // Traffic control elements
        if (isAfterState) {
            renderSignal(svg, center, roadWidth);
        } else {
            renderStopSigns(svg, center, roadWidth);
        }

        // Conflict zone (before state only)
        if (!isAfterState) {
            svg.append('circle')
                .attr('cx', center.x)
                .attr('cy', center.y)
                .attr('r', 30)
                .attr('fill', 'none')
                .attr('stroke', COLORS.conflict)
                .attr('stroke-width', 3)
                .attr('opacity', 0.6)
                .attr('class', 'viz-conflict-zone');
        }

        // Vehicles group (for animation)
        svg.append('g').attr('class', 'viz-vehicles');

        return svg;
    }

    function renderSignal(svg, center, roadWidth) {
        const signalGroup = svg.append('g').attr('class', 'viz-signals');

        // North signal
        const signalHeight = 30;
        const signalWidth = 12;

        signalGroup.append('rect')
            .attr('x', center.x - signalWidth / 2)
            .attr('y', center.y - roadWidth / 2 - signalHeight - 10)
            .attr('width', signalWidth)
            .attr('height', signalHeight)
            .attr('fill', '#1f2937')
            .attr('rx', 2);

        // Signal lights
        const lightRadius = 3;
        const lightSpacing = 8;
        const baseY = center.y - roadWidth / 2 - signalHeight - 10 + 5;

        ['red', 'yellow', 'green'].forEach((color, i) => {
            signalGroup.append('circle')
                .attr('cx', center.x)
                .attr('cy', baseY + i * lightSpacing)
                .attr('r', lightRadius)
                .attr('fill', i === 2 ? COLORS.signal.green : '#374151')
                .attr('class', `viz-signal-${color}`);
        });
    }

    function renderStopSigns(svg, center, roadWidth) {
        const stopGroup = svg.append('g').attr('class', 'viz-stops');

        // Stop sign positions (on minor road approaches)
        const positions = [
            { x: center.x - roadWidth / 2 - 15, y: center.y },
            { x: center.x + roadWidth / 2 + 15, y: center.y }
        ];

        positions.forEach(pos => {
            stopGroup.append('polygon')
                .attr('points', createOctagonPoints(pos.x, pos.y, 10))
                .attr('fill', '#dc2626');
        });
    }

    function createOctagonPoints(cx, cy, r) {
        const points = [];
        for (let i = 0; i < 8; i++) {
            const angle = (i * 45 - 22.5) * Math.PI / 180;
            points.push(`${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`);
        }
        return points.join(' ');
    }

    // ==================== ANIMATION ====================
    function startAnimation() {
        if (state.animationId) return;

        state.isPlaying = true;
        updatePlayButton();

        const duration = state.config.duration * 1000; // ms
        const startTime = performance.now() - state.currentTime;

        function animate(timestamp) {
            state.currentTime = (timestamp - startTime) % duration;
            const progress = state.currentTime / duration;

            updateProgress(progress);
            animateVehicles(progress);

            if (state.isPlaying) {
                state.animationId = requestAnimationFrame(animate);
            }
        }

        state.animationId = requestAnimationFrame(animate);
    }

    function stopAnimation() {
        state.isPlaying = false;
        updatePlayButton();

        if (state.animationId) {
            cancelAnimationFrame(state.animationId);
            state.animationId = null;
        }
    }

    function animateVehicles(progress) {
        // Animate vehicles in both panels
        const cycleDuration = 5; // seconds per vehicle cycle
        const cycleProgress = (progress * state.config.duration) % cycleDuration / cycleDuration;

        // Before state - vehicles with conflict
        if (state.svgBefore) {
            updateVehiclesBefore(state.svgBefore, cycleProgress);
        }

        // After state - controlled flow
        if (state.svgAfter) {
            updateVehiclesAfter(state.svgAfter, cycleProgress);
        }
    }

    function updateVehiclesBefore(svg, progress) {
        const vehiclesGroup = svg.select('.viz-vehicles');
        vehiclesGroup.selectAll('*').remove();

        const center = { x: 200, y: 200 };
        const roadWidth = 60;

        // Horizontal vehicle (eastbound)
        const hVehicle = {
            x: -20 + progress * 440,
            y: center.y + 15
        };

        // Vertical vehicle (southbound)
        const vVehicle = {
            x: center.x - 15,
            y: -20 + progress * 440
        };

        // Check for conflict (both near center)
        const hNearCenter = hVehicle.x > center.x - 50 && hVehicle.x < center.x + 30;
        const vNearCenter = vVehicle.y > center.y - 50 && vVehicle.y < center.y + 30;
        const inConflict = hNearCenter && vNearCenter;

        // Draw vehicles
        vehiclesGroup.append('rect')
            .attr('x', hVehicle.x)
            .attr('y', hVehicle.y)
            .attr('width', 25)
            .attr('height', 12)
            .attr('fill', inConflict ? COLORS.conflict : COLORS.vehicle)
            .attr('rx', 2);

        vehiclesGroup.append('rect')
            .attr('x', vVehicle.x)
            .attr('y', vVehicle.y)
            .attr('width', 12)
            .attr('height', 25)
            .attr('fill', inConflict ? '#fbbf24' : COLORS.vehicleAlt)
            .attr('rx', 2);

        // Conflict indicator
        if (inConflict) {
            vehiclesGroup.append('circle')
                .attr('cx', center.x)
                .attr('cy', center.y)
                .attr('r', 20 + Math.sin(progress * Math.PI * 10) * 5)
                .attr('fill', 'none')
                .attr('stroke', COLORS.conflict)
                .attr('stroke-width', 3)
                .attr('opacity', 0.8);
        }
    }

    function updateVehiclesAfter(svg, progress) {
        const vehiclesGroup = svg.select('.viz-vehicles');
        vehiclesGroup.selectAll('*').remove();

        const center = { x: 200, y: 200 };

        // Signal-controlled: alternate flow
        const isGreenHorizontal = progress < 0.5;

        if (isGreenHorizontal) {
            // Horizontal vehicle moves
            const hProgress = progress * 2;
            vehiclesGroup.append('rect')
                .attr('x', -20 + hProgress * 440)
                .attr('y', center.y + 15)
                .attr('width', 25)
                .attr('height', 12)
                .attr('fill', COLORS.vehicle)
                .attr('rx', 2);

            // Vertical vehicle waits
            vehiclesGroup.append('rect')
                .attr('x', center.x - 15)
                .attr('y', center.y - 80)
                .attr('width', 12)
                .attr('height', 25)
                .attr('fill', COLORS.vehicleAlt)
                .attr('opacity', 0.7)
                .attr('rx', 2);
        } else {
            // Vertical vehicle moves
            const vProgress = (progress - 0.5) * 2;
            vehiclesGroup.append('rect')
                .attr('x', center.x - 15)
                .attr('y', -20 + vProgress * 440)
                .attr('width', 12)
                .attr('height', 25)
                .attr('fill', COLORS.vehicleAlt)
                .attr('rx', 2);

            // Horizontal vehicle waits
            vehiclesGroup.append('rect')
                .attr('x', center.x - 80)
                .attr('y', center.y + 15)
                .attr('width', 25)
                .attr('height', 12)
                .attr('fill', COLORS.vehicle)
                .attr('opacity', 0.7)
                .attr('rx', 2);
        }

        // Update signal lights
        updateSignalLights(svg, isGreenHorizontal);
    }

    function updateSignalLights(svg, isGreenHorizontal) {
        svg.select('.viz-signal-green')
            .attr('fill', isGreenHorizontal ? COLORS.signal.green : '#374151');
        svg.select('.viz-signal-red')
            .attr('fill', !isGreenHorizontal ? COLORS.signal.red : '#374151');
    }

    function updateProgress(progress) {
        const fill = document.getElementById('vizProgressFill');
        const currentTime = document.getElementById('vizCurrentTime');

        if (fill) fill.style.width = `${progress * 100}%`;
        if (currentTime) {
            const seconds = Math.floor(progress * state.config.duration);
            const mins = Math.floor(seconds / 60);
            const secs = seconds % 60;
            currentTime.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
        }
    }

    function updatePlayButton() {
        const icon = document.getElementById('vizPlayIcon');
        if (icon) {
            icon.textContent = state.isPlaying ? '⏸' : '▶';
        }
    }

    // ==================== METRICS CALCULATION ====================
    function calculateMetrics(crashProfile, countermeasure) {
        const totalCrashes = crashProfile.total || 0;
        const crfPct = countermeasure.crfPct || 30;
        const cmf = 1 - (crfPct / 100);

        // Estimate conflicts based on crashes
        const estimatedConflicts = totalCrashes * 100; // ~100 conflicts per crash
        const conflictsPerHour = (estimatedConflicts / (5 * 365 * 24)).toFixed(1);

        // After metrics
        const afterConflicts = (conflictsPerHour * cmf).toFixed(1);
        const reductionPercent = crfPct;

        // Annual savings (using EPDO-based cost)
        const epdoCost = calcEPDO(crashProfile) * 10000; // Rough estimate
        const annualSavings = Math.round(epdoCost * (crfPct / 100));

        return {
            beforeConflicts: conflictsPerHour,
            afterConflicts: afterConflicts,
            reductionPercent: reductionPercent,
            annualSavings: annualSavings,
            cmf: cmf.toFixed(2)
        };
    }

    function updateMetricsDisplay(metrics, countermeasure) {
        // Before stats
        document.getElementById('vizBeforeConflicts').textContent = `${metrics.beforeConflicts}/hr`;
        document.getElementById('vizBeforeRisk').textContent =
            metrics.beforeConflicts > 3 ? 'High' : metrics.beforeConflicts > 1 ? 'Medium' : 'Low';

        // After stats
        document.getElementById('vizAfterConflicts').textContent = `${metrics.afterConflicts}/hr`;
        document.getElementById('vizConflictChange').textContent = `↓ ${metrics.reductionPercent}%`;
        document.getElementById('vizAfterRisk').textContent =
            metrics.afterConflicts > 3 ? 'High' : metrics.afterConflicts > 1 ? 'Medium' : 'Low';

        // Summary
        document.getElementById('vizReduction').textContent =
            `${metrics.reductionPercent}% (CMF: ${metrics.cmf})`;
        document.getElementById('vizSavings').textContent =
            `$${metrics.annualSavings.toLocaleString()}`;

        // Cost estimate
        const costLabels = { 1: '$5K-25K', 2: '$25K-100K', 3: '$100K-500K', 4: '$500K+' };
        document.getElementById('vizCost').textContent =
            costLabels[countermeasure.costTier] || 'Varies';
    }

    // ==================== PUBLIC API ====================
    function openConfig(cmfId) {
        // Get CMF from database
        const cmf = cmfState.database.find(c => c.id === cmfId);
        if (!cmf) {
            console.error('[VizModule] CMF not found:', cmfId);
            return;
        }

        state.countermeasure = cmf;
        state.location = cmfState.selectedLocation;
        state.crashProfile = buildCMFCrashProfile();

        // Update config modal
        document.getElementById('vizConfigTitle').textContent = 'Configure Visualization';
        document.getElementById('vizConfigSubtitle').textContent =
            `${cmf.name} at ${state.location || 'Selected Location'}`;

        // Show config modal
        document.getElementById('vizConfigModal').classList.add('visible');
    }

    function closeConfig() {
        document.getElementById('vizConfigModal').classList.remove('visible');
    }

    function setConfig(key, value) {
        state.config[key] = value;

        // Update UI selection
        const optionsContainer = key === 'timeOfDay' ? 'vizTimeOptions' : 'vizWeatherOptions';
        const options = document.querySelectorAll(`#${optionsContainer} .viz-config-option`);
        options.forEach(opt => {
            opt.classList.toggle('selected', opt.dataset.value === value);
        });
    }

    function startVisualization() {
        closeConfig();

        // Update modal header
        document.getElementById('vizTitle').textContent =
            `Visualization: ${state.countermeasure.name}`;
        document.getElementById('vizSubtitle').textContent =
            `${state.location || 'Location'} • ${state.config.timeOfDay.replace('-', ' ')} • ${state.config.weather}`;

        // Calculate and display metrics
        state.metrics = calculateMetrics(state.crashProfile, state.countermeasure);
        updateMetricsDisplay(state.metrics, state.countermeasure);

        // Render visualizations
        const template = selectTemplate(state.crashProfile, state.countermeasure);
        state.svgBefore = renderIntersection('vizSvgBefore', template, false, state.config);
        state.svgAfter = renderIntersection('vizSvgAfter', template, true, state.config);

        // Show modal
        document.getElementById('vizModal').classList.add('visible');
        state.isOpen = true;

        // Start animation
        setTimeout(() => startAnimation(), 500);
    }

    function close() {
        stopAnimation();
        document.getElementById('vizModal').classList.remove('visible');
        state.isOpen = false;
        state.currentTime = 0;
        updateProgress(0);
    }

    function togglePlay() {
        if (state.isPlaying) {
            stopAnimation();
        } else {
            startAnimation();
        }
    }

    function reset() {
        stopAnimation();
        state.currentTime = 0;
        updateProgress(0);
    }

    function setView(view) {
        state.currentView = view;

        // Update buttons
        document.querySelectorAll('.viz-view-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === view);
        });

        // Update panels
        const beforePanel = document.getElementById('vizPanelBefore');
        const afterPanel = document.getElementById('vizPanelAfter');
        const divider = document.getElementById('vizDivider');

        beforePanel.classList.toggle('hidden', view === 'after');
        afterPanel.classList.toggle('hidden', view === 'before');
        divider.style.display = view === 'split' ? 'block' : 'none';
    }

    function seek(event) {
        const bar = event.currentTarget;
        const rect = bar.getBoundingClientRect();
        const progress = (event.clientX - rect.left) / rect.width;

        state.currentTime = progress * state.config.duration * 1000;
        updateProgress(progress);
    }

    function screenshot() {
        const content = document.querySelector('.viz-content');
        if (!content) return;

        html2canvas(content, {
            backgroundColor: '#1e293b',
            scale: 2
        }).then(canvas => {
            const link = document.createElement('a');
            link.download = `visualization-${state.location || 'location'}.png`;
            link.href = canvas.toDataURL('image/png');
            link.click();
        });
    }

    function addToReport() {
        // Capture current state for report
        const reportData = {
            location: state.location,
            countermeasure: state.countermeasure.name,
            cmf: state.metrics.cmf,
            reduction: state.metrics.reductionPercent,
            savings: state.metrics.annualSavings,
            config: state.config
        };

        // Store for report generation
        if (typeof window.reportVisualizationData === 'undefined') {
            window.reportVisualizationData = [];
        }
        window.reportVisualizationData.push(reportData);

        // Take screenshot for report
        screenshot();

        // Notify user
        alert('Visualization added to report data. Screenshot saved.');
    }

    // ==================== INITIALIZATION ====================
    function init() {
        console.log('[VizModule] Initialized');
    }

    // Public API
    return {
        init,
        openConfig,
        closeConfig,
        setConfig,
        startVisualization,
        close,
        togglePlay,
        reset,
        setView,
        seek,
        screenshot,
        addToReport
    };
})();

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    VizModule.init();
});

// === END VISUALIZE IMPACT MODULE ===
```

---

## 6. Integration Checklist

### 6.1 Files to Modify

| File | Change | Lines |
|------|--------|-------|
| `app/index.html` | Add D3.js script tag | ~45 |
| `app/index.html` | Add CSS styles | ~1700 (new section) |
| `app/index.html` | Add modal HTML | ~7500 (new section) |
| `app/index.html` | Add JavaScript module | ~29900 (new section) |
| `app/index.html` | Add button to CMF cards | ~29289 |

### 6.2 Testing Checklist

- [ ] Config modal opens from CMF card button
- [ ] Time of day selection works
- [ ] Weather selection works
- [ ] Visualization modal opens correctly
- [ ] Before/After panels render SVG
- [ ] Animation plays/pauses correctly
- [ ] Progress bar updates
- [ ] View toggle (split/before/after) works
- [ ] Metrics display correct values
- [ ] Screenshot export works
- [ ] Modal closes properly
- [ ] No console errors
- [ ] Works on different screen sizes
- [ ] Animation performance is smooth

### 6.3 Browser Compatibility

| Browser | Minimum Version | Notes |
|---------|-----------------|-------|
| Chrome | 80+ | Full support |
| Firefox | 75+ | Full support |
| Safari | 13+ | Full support |
| Edge | 80+ | Full support |

---

## 7. Future Enhancements

### Phase 2 Additions
- SUMO integration for realistic traffic metrics
- More intersection templates
- Pedestrian crossing animations
- Roundabout transformation animation

### Phase 3 Additions
- 3D visualization option (Three.js)
- Video export
- Multiple countermeasure comparison
- Before/after crash data overlay

---

## 8. Appendix

### A. SVG Path References

**4-Leg Intersection Coordinates (400x400 viewport):**
```
Center: (200, 200)
Road width: 60px
Approaches:
  - North: (170, 0) to (230, 170)
  - South: (170, 230) to (230, 400)
  - East: (230, 170) to (400, 230)
  - West: (0, 170) to (170, 230)
```

### B. Color Palette Reference

```javascript
const PALETTE = {
    // Road elements
    road: '#4b5563',      // Gray-600
    marking: '#fbbf24',   // Amber-400

    // Vehicles
    vehiclePrimary: '#3b82f6',   // Blue-500
    vehicleSecondary: '#f59e0b', // Amber-500

    // Status
    danger: '#dc2626',    // Red-600
    warning: '#f59e0b',   // Amber-500
    success: '#22c55e',   // Green-500

    // Signals
    signalRed: '#ef4444',
    signalYellow: '#fbbf24',
    signalGreen: '#22c55e',

    // Background
    bgDay: '#1e293b',     // Slate-800
    bgNight: '#0f172a',   // Slate-900
};
```

### C. Animation Timing Reference

```javascript
const TIMING = {
    vehicleCycle: 5000,      // ms per vehicle pass
    signalPhase: 2500,       // ms per signal phase
    conflictPulse: 500,      // ms per conflict pulse
    transitionDuration: 300  // ms for UI transitions
};
```
