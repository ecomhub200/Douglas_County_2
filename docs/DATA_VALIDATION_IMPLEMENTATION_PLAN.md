# Virginia Crash Data Validation System
## Comprehensive Implementation Plan

**Version:** 1.0
**Date:** January 2026
**Scope:** All 133 Virginia Jurisdictions
**Primary Tool:** CRASH LENS

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
3. [Data Flow Pipeline](#3-data-flow-pipeline)
4. [Reference Data Specifications](#4-reference-data-specifications)
5. [Validation Rules](#5-validation-rules)
6. [Auto-Correction Engine](#6-auto-correction-engine)
7. [Spatial Validation (Overpass Integration)](#7-spatial-validation-overpass-integration)
8. [Incremental Processing Strategy](#8-incremental-processing-strategy)
9. [Multi-Jurisdiction Support](#9-multi-jurisdiction-support)
10. [GitHub Actions Integration](#10-github-actions-integration)
11. [Reporting & Monitoring](#11-reporting--monitoring)
12. [File Structure](#12-file-structure)
13. [Implementation Phases](#13-implementation-phases)
14. [Risk Mitigation](#14-risk-mitigation)
15. [Appendices](#15-appendices)

---

## 1. Executive Summary

### 1.1 Purpose

Build an automated, zero-intervention data validation system for Virginia crash data that:
- Validates all incoming crash records against defined quality rules
- Auto-corrects high-confidence errors
- Flags low-confidence issues for review
- Processes incrementally (new records only)
- Supports all 133 Virginia jurisdictions
- Integrates seamlessly with existing CRASH LENS tool

### 1.2 Key Principles

| Principle | Description |
|-----------|-------------|
| **Zero Intervention** | Runs automatically on schedule without human action |
| **Incremental** | Only validates new/changed records each cycle |
| **Non-Destructive** | Original data backed up; corrections logged |
| **Jurisdiction-Aware** | Respects county-specific rules and boundaries |
| **Confidence-Based** | Only auto-corrects when confidence ≥ 85% |
| **Auditable** | Full log of all corrections for transparency |

### 1.3 Data Source

- **Provider:** Virginia DMV via VDOT Virginia Roads Portal
- **System:** TREDS (Traffic Records Electronic Data System)
- **Form:** FR300 Police Crash Report
- **Update Frequency:** Monthly
- **Coverage:** 2015 - Present
- **Portal:** https://virginiaroads.org

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        VIRGINIA CRASH DATA VALIDATION SYSTEM                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │   Virginia   │    │   Download   │    │  Validation  │    │   CRASH   │ │
│  │    Roads     │───►│    Script    │───►│    Engine    │───►│   LENS    │ │
│  │    Portal    │    │   (Python)   │    │   (Python)   │    │   Tool    │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └───────────┘ │
│         │                   │                   │                   │        │
│         │                   ▼                   ▼                   │        │
│         │            ┌──────────────┐    ┌──────────────┐          │        │
│         │            │  Raw Data    │    │  Validated   │          │        │
│         │            │  (Staging)   │    │    Data      │          │        │
│         │            └──────────────┘    └──────────────┘          │        │
│         │                                      │                    │        │
│         │                                      ▼                    │        │
│         │                              ┌──────────────┐             │        │
│         │                              │  Validation  │             │        │
│         │                              │    Report    │             │        │
│         │                              └──────────────┘             │        │
│         │                                                           │        │
│  ┌──────┴───────────────────────────────────────────────────────────┴─────┐ │
│  │                         EXTERNAL SERVICES                               │ │
│  ├─────────────────┬─────────────────┬─────────────────┬─────────────────┤ │
│  │   Overpass API  │    TIGERweb     │     Mapbox      │   Config.json   │ │
│  │  (Road Network) │   (Boundaries)  │   (Geocoding)   │  (Jurisdictions)│ │
│  └─────────────────┴─────────────────┴─────────────────┴─────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **Download Script** | Fetch data from Virginia Roads, filter by jurisdiction |
| **Validation Engine** | Apply all validation rules, generate corrections |
| **Reference Data** | Store valid values, bounds, correction mappings |
| **Overpass Integration** | Validate coordinates against road network |
| **TIGERweb Integration** | Validate jurisdiction boundaries |
| **Reporting Module** | Generate quality reports and logs |
| **GitHub Actions** | Orchestrate automated pipeline |

---

## 3. Data Flow Pipeline

### 3.1 Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA FLOW PIPELINE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STAGE 1: DOWNLOAD                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  • Trigger: Schedule (monthly) or manual                            │   │
│  │  • Action: Download from Virginia Roads API                         │   │
│  │  • Output: Raw CSV files in staging area                            │   │
│  │  • Files: {jurisdiction}_{filter}.csv                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│                                     ▼                                        │
│  STAGE 2: DELTA DETECTION                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  • Compare: New download vs validated_ids.txt                       │   │
│  │  • Identify: New Document Numbers (not previously validated)        │   │
│  │  • Output: List of records requiring validation                     │   │
│  │  • Skip: Previously validated records (unless rules changed)        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│                                     ▼                                        │
│  STAGE 3: VALIDATION                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  • Schema Check: Required fields, data types                        │   │
│  │  • Bounds Check: Coordinates within jurisdiction                    │   │
│  │  • Category Check: Values in valid sets                             │   │
│  │  • Consistency Check: Cross-field logic                             │   │
│  │  • Spatial Check: Coordinate on/near road (Overpass)                │   │
│  │  • Duplicate Check: No duplicate Document Numbers                   │   │
│  │  • Output: Validation results per record                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│                                     ▼                                        │
│  STAGE 4: CORRECTION                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  • High Confidence (≥85%): Auto-apply correction                    │   │
│  │  • Medium Confidence (50-84%): Flag + suggest correction            │   │
│  │  • Low Confidence (<50%): Flag only, no suggestion                  │   │
│  │  • Output: Corrected data + corrections log                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│                                     ▼                                        │
│  STAGE 5: MERGE & OUTPUT                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  • Merge: Validated new records with existing clean data            │   │
│  │  • Replace: Overwrite CSV files with validated versions             │   │
│  │  • Update: validated_ids.txt with newly validated IDs               │   │
│  │  • Copy: crashes.csv from county_roads (fallback)                   │   │
│  │  • Generate: Validation report                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│                                     ▼                                        │
│  STAGE 6: COMMIT & NOTIFY                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  • Git: Commit validated data + reports                             │   │
│  │  • Push: To repository                                              │   │
│  │  • Notify: Send summary (if configured)                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 File Flow

```
Download                    Validation                    Output
────────                    ──────────                    ──────

Virginia Roads API
       │
       ▼
┌──────────────────┐
│ Raw Download     │
│ (24,500 records) │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐      ┌──────────────────┐
│ Delta Detection  │─────►│ 500 New Records  │
│ (compare to IDs) │      │ (need validation)│
└──────────────────┘      └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │ Validation       │
                          │ Engine           │
                          └────────┬─────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
             ┌───────────┐  ┌───────────┐  ┌───────────┐
             │ 485 Clean │  │ 12 Auto-  │  │ 3 Flagged │
             │ Records   │  │ Corrected │  │ for Review│
             └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
                   │              │              │
                   └──────────────┼──────────────┘
                                  ▼
                          ┌──────────────────┐
                          │ Merge with       │
                          │ Existing 24,000  │
                          └────────┬─────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
        ┌─────────────────┐ ┌─────────────┐ ┌─────────────┐
        │henrico_county_  │ │henrico_no_  │ │henrico_all_ │
        │roads.csv        │ │interstate.csv│ │roads.csv    │
        │(validated)      │ │(validated)  │ │(validated)  │
        └─────────────────┘ └─────────────┘ └─────────────┘
                                  │
                                  ▼
                          ┌──────────────────┐
                          │ crashes.csv      │
                          │ (copy of county) │
                          └──────────────────┘
```

---

## 4. Reference Data Specifications

### 4.1 Virginia Valid Values

**File:** `validation/reference/virginia_valid_values.json`

```json
{
  "metadata": {
    "version": "1.0.0",
    "lastUpdated": "2026-01-26",
    "source": "VDOT Virginia Roads / FR300 Manual",
    "contact": "TREDS.SAVESLIVES@DMV.Virginia.Gov"
  },

  "severity": {
    "valid": ["K", "A", "B", "C", "O"],
    "descriptions": {
      "K": "Fatal Injury",
      "A": "Serious Injury (Incapacitating)",
      "B": "Minor Injury (Non-Incapacitating)",
      "C": "Possible Injury",
      "O": "Property Damage Only"
    },
    "epdoWeights": {
      "K": 883,
      "A": 94,
      "B": 21,
      "C": 11,
      "O": 1
    }
  },

  "collisionTypes": {
    "valid": [
      "1. Rear End",
      "2. Angle",
      "3. Head On",
      "4. Sideswipe - Same Direction",
      "5. Sideswipe - Opposite Direction",
      "6. Fixed Object in Road",
      "7. Train",
      "8. Non-Collision",
      "9. Fixed Object - Off Road",
      "10. Deer",
      "11. Other Animal",
      "12. Ped",
      "13. Bicyclist",
      "14. Motorcyclist",
      "15. Backed Into",
      "16. Other"
    ],
    "pedestrianTypes": ["12. Ped"],
    "bicycleTypes": ["13. Bicyclist"],
    "animalTypes": ["10. Deer", "11. Other Animal"],
    "fixedObjectTypes": ["6. Fixed Object in Road", "9. Fixed Object - Off Road"]
  },

  "weatherConditions": {
    "valid": [
      "1. No Adverse Condition (Clear/Cloudy)",
      "2. Fog",
      "3. Mist",
      "4. Rain",
      "5. Snow",
      "6. Sleet/Hail",
      "7. Smoke/Dust",
      "8. Severe Crosswinds",
      "9. Other",
      "10. Blowing Sand",
      "11. Unknown"
    ],
    "adverseConditions": [
      "2. Fog", "3. Mist", "4. Rain", "5. Snow",
      "6. Sleet/Hail", "7. Smoke/Dust", "8. Severe Crosswinds", "10. Blowing Sand"
    ]
  },

  "lightConditions": {
    "valid": [
      "1. Dawn",
      "2. Daylight",
      "3. Dusk",
      "4. Darkness - Road Lighted",
      "5. Darkness - Road Not Lighted",
      "6. Darkness - Unknown Road Lighting",
      "7. Unknown"
    ],
    "daylight": ["1. Dawn", "2. Daylight", "3. Dusk"],
    "darkness": ["4. Darkness - Road Lighted", "5. Darkness - Road Not Lighted", "6. Darkness - Unknown Road Lighting"]
  },

  "surfaceConditions": {
    "valid": [
      "1. Dry",
      "2. Wet",
      "3. Water (Standing/Moving)",
      "4. Ice",
      "5. Snow",
      "6. Mud/Dirt/Gravel",
      "7. Slush",
      "8. Oil",
      "9. Sand",
      "10. Other",
      "11. Unknown"
    ]
  },

  "intersectionTypes": {
    "valid": [
      "1. Not at Intersection",
      "2. Two-Way Stop",
      "3. Four-Way Stop",
      "4. Yield Sign",
      "5. Traffic Signal",
      "6. Flashing Signal",
      "7. Railway Crossing",
      "8. Roundabout",
      "9. Other",
      "10. Unknown"
    ]
  },

  "trafficControlTypes": {
    "valid": [
      "1. No Control",
      "2. Officer/Flagman",
      "3. Traffic Signal",
      "4. Flashing Signal",
      "5. Stop Sign",
      "6. Yield Sign",
      "7. Warning Sign",
      "8. RR Crossing Device",
      "9. Other",
      "10. Unknown"
    ]
  },

  "booleanFields": {
    "valid": ["Yes", "No", "Unknown", ""],
    "trueValues": ["Yes", "Y", "1", "TRUE", "true"],
    "falseValues": ["No", "N", "0", "FALSE", "false", ""]
  },

  "stateBounds": {
    "virginia": {
      "minLat": 36.541,
      "maxLat": 39.466,
      "minLon": -83.675,
      "maxLon": -75.242
    }
  },

  "dateRange": {
    "minYear": 2015,
    "maxYear": null,
    "preliminaryDays": 30
  },

  "documentNumberPattern": "^[A-Z0-9]{8,20}$"
}
```

### 4.2 Jurisdiction Bounds

**File:** `validation/reference/jurisdiction_bounds.json`

*Extracted from config.json - all 133 jurisdictions*

```json
{
  "metadata": {
    "version": "1.0.0",
    "source": "config.json",
    "totalJurisdictions": 133
  },

  "jurisdictions": {
    "henrico": {
      "name": "Henrico County",
      "type": "county",
      "fips": "087",
      "jurisCode": "44",
      "maintainsOwnRoads": true,
      "bbox": [-77.6553, 37.4284, -77.1731, 37.6889],
      "center": [-77.4142, 37.5587]
    },
    "arlington": {
      "name": "Arlington County",
      "type": "county",
      "fips": "013",
      "jurisCode": "7",
      "maintainsOwnRoads": true,
      "bbox": [-77.1722, 38.8275, -77.0319, 38.9344],
      "center": [-77.1021, 38.8810]
    },
    "fairfax_county": {
      "name": "Fairfax County",
      "type": "county",
      "fips": "059",
      "jurisCode": "30",
      "maintainsOwnRoads": false,
      "bbox": [-77.5109, 38.5938, -77.0892, 39.0024],
      "center": [-77.3001, 38.7980]
    }
    // ... all 133 jurisdictions
  }
}
```

### 4.3 Correction Rules

**File:** `validation/reference/correction_rules.json`

```json
{
  "metadata": {
    "version": "1.0.0",
    "lastUpdated": "2026-01-26"
  },

  "categoryCorrections": {
    "lightConditions": {
      "Soil": {
        "correctTo": "3. Dusk",
        "confidence": 0.85,
        "reason": "OCR/data entry error - phonetically similar"
      },
      "Not Applicable": {
        "correctTo": null,
        "confidence": 0,
        "flag": true,
        "reason": "Invalid category - requires manual review"
      },
      "Daylight": {
        "correctTo": "2. Daylight",
        "confidence": 1.0,
        "reason": "Missing numeric prefix"
      }
    },

    "weatherConditions": {
      "\"10. Blowing Sand": {
        "correctTo": "10. Blowing Sand",
        "confidence": 1.0,
        "reason": "Quote parsing error"
      },
      "Clear": {
        "correctTo": "1. No Adverse Condition (Clear/Cloudy)",
        "confidence": 0.95,
        "reason": "Abbreviated category"
      }
    },

    "collisionTypes": {
      "Pedestrian": {
        "correctTo": "12. Ped",
        "confidence": 0.95,
        "reason": "Alternative spelling"
      },
      "Bicycle": {
        "correctTo": "13. Bicyclist",
        "confidence": 0.95,
        "reason": "Alternative spelling"
      }
    }
  },

  "consistencyCorrections": {
    "pedestrianFlagMismatch": {
      "condition": "collisionType == '12. Ped' AND pedestrianFlag != 'Yes'",
      "correction": "pedestrianFlag = 'Yes'",
      "confidence": 0.98,
      "reason": "Flag should match collision type"
    },
    "bicycleFlagMismatch": {
      "condition": "collisionType == '13. Bicyclist' AND bikeFlag != 'Yes'",
      "correction": "bikeFlag = 'Yes'",
      "confidence": 0.98,
      "reason": "Flag should match collision type"
    },
    "nightFlagMismatch": {
      "condition": "lightCondition IN darkness_values AND nightFlag != 'Yes'",
      "correction": "nightFlag = 'Yes'",
      "confidence": 0.95,
      "reason": "Flag should match light condition"
    }
  },

  "coordinateCorrections": {
    "outsideJurisdiction": {
      "action": "flag",
      "confidence": 0,
      "reason": "Coordinate outside stated jurisdiction bounds"
    },
    "outsideVirginia": {
      "action": "flag",
      "confidence": 0,
      "reason": "Coordinate outside Virginia state bounds"
    },
    "nullWithNode": {
      "action": "lookup",
      "source": "node_coordinates_table",
      "confidence": 0.90,
      "reason": "Can recover from Node ID"
    },
    "offRoad": {
      "action": "snap",
      "maxDistance": 50,
      "confidence": 0.85,
      "reason": "Snap to nearest road within 50m"
    }
  },

  "formatCorrections": {
    "trimWhitespace": {
      "fields": ["all_string_fields"],
      "confidence": 1.0
    },
    "normalizeCase": {
      "fields": ["severity"],
      "transform": "uppercase",
      "confidence": 1.0
    },
    "removeQuotes": {
      "pattern": "^[\"']|[\"']$",
      "confidence": 1.0
    }
  }
}
```

---

## 5. Validation Rules

### 5.1 Schema Validation

| Rule ID | Field | Check | Severity | Auto-Fix |
|---------|-------|-------|----------|----------|
| SCH-001 | Document Nbr | Not null, matches pattern | Error | No |
| SCH-002 | Crash Year | Integer, 2015-current | Error | No |
| SCH-003 | Crash Date | Valid date format | Error | No |
| SCH-004 | x (Longitude) | Numeric or null | Error | No |
| SCH-005 | y (Latitude) | Numeric or null | Error | No |
| SCH-006 | Crash Severity | Single character | Error | No |
| SCH-007 | K_People | Integer ≥ 0 | Warning | Default 0 |
| SCH-008 | A_People | Integer ≥ 0 | Warning | Default 0 |

### 5.2 Bounds Validation

| Rule ID | Check | Severity | Auto-Fix |
|---------|-------|----------|----------|
| BND-001 | Longitude within Virginia (-83.675 to -75.242) | Error | Flag |
| BND-002 | Latitude within Virginia (36.541 to 39.466) | Error | Flag |
| BND-003 | Coordinates within stated jurisdiction bbox | Warning | Flag |
| BND-004 | Crash Year ≤ current year | Error | Flag |
| BND-005 | Crash Year ≥ 2015 | Error | Flag |
| BND-006 | Crash Date not in future | Error | Flag |

### 5.3 Category Validation

| Rule ID | Field | Check | Severity | Auto-Fix |
|---------|-------|-------|----------|----------|
| CAT-001 | Crash Severity | In [K, A, B, C, O] | Error | Map if similar |
| CAT-002 | Collision Type | In valid list | Warning | Map if similar |
| CAT-003 | Weather Condition | In valid list | Warning | Map if similar |
| CAT-004 | Light Condition | In valid list | Warning | Map if similar |
| CAT-005 | Surface Condition | In valid list | Warning | Map if similar |
| CAT-006 | Intersection Type | In valid list | Warning | Map if similar |
| CAT-007 | Traffic Control Type | In valid list | Warning | Map if similar |
| CAT-008 | All boolean fields | In [Yes, No, Unknown, ""] | Warning | Normalize |

### 5.4 Consistency Validation

| Rule ID | Check | Severity | Auto-Fix |
|---------|-------|----------|----------|
| CON-001 | Severity=K → K_People > 0 | Error | Flag |
| CON-002 | Severity=A → A_People > 0 OR injury count > 0 | Warning | Flag |
| CON-003 | Collision=12.Ped → Pedestrian?=Yes | Warning | Set flag |
| CON-004 | Collision=13.Bicyclist → Bike?=Yes | Warning | Set flag |
| CON-005 | Light=Darkness* → Night?=Yes | Warning | Set flag |
| CON-006 | Total injuries ≤ reasonable max (e.g., 50) | Warning | Flag |
| CON-007 | K_People + A_People + B_People + C_People ≤ Total involved | Warning | Flag |
| CON-008 | Pedestrians Killed ≤ K_People | Warning | Flag |

### 5.5 Completeness Validation

| Rule ID | Field | Required | Severity |
|---------|-------|----------|----------|
| CMP-001 | Document Nbr | Yes | Error |
| CMP-002 | Crash Year | Yes | Error |
| CMP-003 | Crash Date | Yes | Error |
| CMP-004 | Crash Severity | Yes | Error |
| CMP-005 | Collision Type | Yes | Warning |
| CMP-006 | x, y (coordinates) | Preferred | Info |
| CMP-007 | RTE Name | Preferred | Info |
| CMP-008 | Node | Optional | Info |

### 5.6 Duplicate Validation

| Rule ID | Check | Severity | Auto-Fix |
|---------|-------|----------|----------|
| DUP-001 | No duplicate Document Nbr | Error | Keep first |
| DUP-002 | No exact duplicate rows | Error | Keep first |
| DUP-003 | Flag potential duplicates (same location+date+time) | Warning | Flag |

### 5.7 Spatial Validation (Overpass)

| Rule ID | Check | Severity | Auto-Fix |
|---------|-------|----------|----------|
| SPA-001 | Coordinate within 100m of any road | Warning | Snap if <50m |
| SPA-002 | Coordinate matches stated route name | Warning | Flag |
| SPA-003 | Intersection coordinate near actual intersection | Warning | Flag |

---

## 6. Auto-Correction Engine

### 6.1 Correction Decision Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    CORRECTION DECISION FLOW                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Record with Issue                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────┐                                            │
│  │ Lookup in       │                                            │
│  │ correction_rules│                                            │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐     No      ┌─────────────────┐           │
│  │ Rule exists?    │────────────►│ Flag as Unknown │           │
│  └────────┬────────┘             │ Issue           │           │
│           │ Yes                  └─────────────────┘           │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Get confidence  │                                            │
│  │ score           │                                            │
│  └────────┬────────┘                                            │
│           │                                                      │
│     ┌─────┴─────┬───────────────┐                               │
│     ▼           ▼               ▼                               │
│  ≥85%        50-84%           <50%                              │
│     │           │               │                               │
│     ▼           ▼               ▼                               │
│  ┌───────┐  ┌───────┐     ┌───────┐                            │
│  │ AUTO  │  │ FLAG  │     │ FLAG  │                            │
│  │CORRECT│  │  +    │     │ ONLY  │                            │
│  │       │  │SUGGEST│     │       │                            │
│  └───┬───┘  └───┬───┘     └───┬───┘                            │
│      │          │             │                                  │
│      └──────────┼─────────────┘                                 │
│                 ▼                                                │
│        ┌─────────────────┐                                      │
│        │ Log correction  │                                      │
│        │ to audit trail  │                                      │
│        └─────────────────┘                                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Confidence Thresholds

| Confidence | Action | Example |
|------------|--------|---------|
| **100%** | Auto-correct silently | Remove extra quotes |
| **95-99%** | Auto-correct + log | "Clear" → "1. No Adverse Condition" |
| **85-94%** | Auto-correct + log + flag | "Soil" → "3. Dusk" |
| **50-84%** | Flag + suggest | Coordinate 75m from road |
| **<50%** | Flag only | Unknown category value |
| **0%** | Flag for manual review | Severity=K but K_People=0 |

### 6.3 Correction Log Format

**File:** `data/.validation/corrections_log.csv`

| Column | Description |
|--------|-------------|
| timestamp | When correction was made |
| document_nbr | Crash record ID |
| field | Field that was corrected |
| original_value | Value before correction |
| corrected_value | Value after correction |
| confidence | Confidence score (0-100) |
| rule_id | Which rule triggered correction |
| auto_applied | Boolean: was it auto-applied? |
| reason | Human-readable explanation |

---

## 7. Spatial Validation (Overpass Integration)

### 7.1 Overpass Endpoints (Existing in Codebase)

```javascript
const OVERPASS_ENDPOINTS = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://overpass.openstreetmap.fr/api/interpreter',
    'https://z.overpass-api.de/api/interpreter'
];
```

### 7.2 Validation Queries

#### Query 1: Is Coordinate Near a Road?

```
[out:json][timeout:30];
(
  way(around:100, {lat}, {lon})["highway"];
);
out tags center;
```

**Returns:** Nearest roads within 100m, with names and types

#### Query 2: Does Route Name Match?

```
[out:json][timeout:30];
way(around:50, {lat}, {lon})["highway"]["name"~"{route_name}", i];
out tags;
```

**Returns:** Roads matching stated route name within 50m

#### Query 3: Is This an Intersection?

```
[out:json][timeout:30];
(
  way(around:30, {lat}, {lon})["highway"];
);
out body;
>;
out skel qt;
```

**Returns:** Road segments meeting at point (intersection validation)

### 7.3 Caching Strategy

To avoid rate limiting and improve performance:

| Strategy | Implementation |
|----------|----------------|
| **Batch by area** | Query jurisdiction bbox once, cache road network |
| **Local cache** | Store road network in SQLite/JSON for repeated use |
| **Cache TTL** | Refresh road network monthly |
| **Skip validated** | Don't re-query coordinates already validated |
| **Progressive** | Only query Overpass for records failing basic checks |

### 7.4 Rate Limiting

| Endpoint | Limit | Strategy |
|----------|-------|----------|
| overpass-api.de | 10,000/day | Primary, use for bulk |
| kumi.systems | Lower | Fallback only |
| openstreetmap.fr | Lower | Fallback only |

**Implementation:**
- Max 1 request/second
- Exponential backoff on 429
- Rotate endpoints on failure
- Batch coordinates by proximity

---

## 8. Incremental Processing Strategy

### 8.1 Document Number Tracking

**File:** `data/.validation/validated_ids_{filter}.txt`

```
# Validated Document Numbers for henrico_county_roads.csv
# Last updated: 2026-01-26
# Total: 24,415
VA2024001234
VA2024001235
VA2024001236
...
```

### 8.2 Incremental Flow

```python
def incremental_validation(new_data, validated_ids_file):
    # Load previously validated IDs
    validated_ids = load_validated_ids(validated_ids_file)

    # Find new records
    new_records = new_data[~new_data['Document Nbr'].isin(validated_ids)]

    # Validate only new records
    validation_results = validate_records(new_records)

    # Apply corrections to new records
    corrected_new = apply_corrections(new_records, validation_results)

    # Merge with existing data (already validated)
    existing_validated = new_data[new_data['Document Nbr'].isin(validated_ids)]
    final_data = pd.concat([existing_validated, corrected_new])

    # Update validated IDs
    newly_validated = corrected_new['Document Nbr'].tolist()
    save_validated_ids(validated_ids_file, validated_ids + newly_validated)

    return final_data
```

### 8.3 Re-validation Triggers

| Trigger | Action |
|---------|--------|
| Normal monthly run | Incremental only |
| validation_rules_version changed | Full re-validation |
| correction_rules.json changed | Full re-validation |
| Manual request (`--full` flag) | Full re-validation |
| > 20% new records | Consider full (data may have shifted) |

### 8.4 Manifest Tracking

**File:** `data/.validation/manifest.json`

```json
{
  "lastRun": "2026-01-26T10:30:00Z",
  "runType": "incremental",
  "jurisdiction": "henrico",
  "validationRulesVersion": "1.0.0",
  "correctionRulesVersion": "1.0.0",
  "recordsProcessed": {
    "total": 24415,
    "new": 512,
    "unchanged": 23903
  },
  "corrections": {
    "autoApplied": 15,
    "flagged": 3,
    "clean": 494
  },
  "files": {
    "henrico_county_roads.csv": {
      "records": 18234,
      "validated": "2026-01-26T10:30:00Z",
      "checksum": "sha256:abc123..."
    },
    "henrico_no_interstate.csv": {
      "records": 22156,
      "validated": "2026-01-26T10:31:00Z",
      "checksum": "sha256:def456..."
    },
    "henrico_all_roads.csv": {
      "records": 24415,
      "validated": "2026-01-26T10:32:00Z",
      "checksum": "sha256:ghi789..."
    }
  }
}
```

---

## 9. Multi-Jurisdiction Support

### 9.1 Jurisdiction Categories

| Category | Example | Road Files | Notes |
|----------|---------|------------|-------|
| **County with own roads** | Henrico, Arlington | 3 files (county, no_interstate, all) | Full validation |
| **County without own roads** | Fairfax, Loudoun | 1 file (all_roads only) | VDOT roads only |
| **Independent City** | Richmond, Virginia Beach | 1 file (all_roads) | City maintains all roads |

### 9.2 File Naming Convention

```
data/
├── {jurisdiction}_county_roads.csv      # Only if maintainsOwnRoads=true
├── {jurisdiction}_no_interstate.csv     # Only if maintainsOwnRoads=true
├── {jurisdiction}_all_roads.csv         # All jurisdictions
└── crashes.csv                          # Copy of default jurisdiction's county_roads
```

### 9.3 Jurisdiction Configuration Access

```python
def get_jurisdiction_config(jurisdiction_id):
    """Load jurisdiction config from config.json"""
    with open('config.json') as f:
        config = json.load(f)

    return config['jurisdictions'].get(jurisdiction_id, None)

def get_jurisdiction_bounds(jurisdiction_id):
    """Get bounding box for coordinate validation"""
    config = get_jurisdiction_config(jurisdiction_id)
    if config and 'bbox' in config:
        return {
            'minLon': config['bbox'][0],
            'minLat': config['bbox'][1],
            'maxLon': config['bbox'][2],
            'maxLat': config['bbox'][3]
        }
    return None
```

### 9.4 Multi-Jurisdiction Validation Run

```bash
# Validate single jurisdiction (default: from config)
python validation/run_validation.py

# Validate specific jurisdiction
python validation/run_validation.py --jurisdiction fairfax_county

# Validate multiple jurisdictions
python validation/run_validation.py --jurisdiction henrico arlington fairfax_county

# Validate all configured jurisdictions
python validation/run_validation.py --all
```

---

## 10. GitHub Actions Integration

### 10.1 Updated Workflow

**File:** `.github/workflows/download-data.yml`

```yaml
name: Download and Validate Crash Data

on:
  schedule:
    # Run monthly on the 5th at 2 AM UTC
    - cron: '0 2 5 * *'
  workflow_dispatch:
    inputs:
      jurisdiction:
        description: 'Jurisdiction to process'
        required: false
        default: ''
      full_validation:
        description: 'Force full re-validation'
        required: false
        type: boolean
        default: false

jobs:
  download-and-validate:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r validation/requirements.txt

      - name: Get jurisdiction
        id: get-jurisdiction
        run: |
          if [ -n "${{ github.event.inputs.jurisdiction }}" ]; then
            echo "jurisdiction=${{ github.event.inputs.jurisdiction }}" >> $GITHUB_OUTPUT
          else
            JURISDICTION=$(jq -r '.defaults.jurisdiction // "henrico"' config.json)
            echo "jurisdiction=$JURISDICTION" >> $GITHUB_OUTPUT
          fi

      - name: Download crash data
        id: download
        run: |
          JURISDICTION="${{ steps.get-jurisdiction.outputs.jurisdiction }}"
          echo "Downloading data for: $JURISDICTION"

          # Download all three filter types
          python download_crash_data.py --jurisdiction "$JURISDICTION" --filter countyOnly \
            --output "data/${JURISDICTION}_county_roads.csv"

          python download_crash_data.py --jurisdiction "$JURISDICTION" --filter countyPlusVDOT \
            --output "data/${JURISDICTION}_no_interstate.csv"

          python download_crash_data.py --jurisdiction "$JURISDICTION" --filter allRoads \
            --output "data/${JURISDICTION}_all_roads.csv"

      - name: Validate and correct data
        id: validate
        run: |
          JURISDICTION="${{ steps.get-jurisdiction.outputs.jurisdiction }}"
          FULL_FLAG=""

          if [ "${{ github.event.inputs.full_validation }}" = "true" ]; then
            FULL_FLAG="--full"
          fi

          python validation/run_validation.py \
            --jurisdiction "$JURISDICTION" \
            --auto-correct \
            $FULL_FLAG

          # Capture validation stats for summary
          if [ -f "data/.validation/latest_report.json" ]; then
            STATS=$(cat data/.validation/latest_report.json)
            echo "validation_stats<<EOF" >> $GITHUB_OUTPUT
            echo "$STATS" >> $GITHUB_OUTPUT
            echo "EOF" >> $GITHUB_OUTPUT
          fi

      - name: Create fallback crashes.csv
        run: |
          JURISDICTION="${{ steps.get-jurisdiction.outputs.jurisdiction }}"
          cp "data/${JURISDICTION}_county_roads.csv" "data/crashes.csv"

      - name: Check for critical issues
        id: check-issues
        run: |
          # Stop if error rate > 10%
          if [ -f "data/.validation/latest_report.json" ]; then
            ERROR_RATE=$(jq '.errorRate // 0' data/.validation/latest_report.json)
            if (( $(echo "$ERROR_RATE > 10" | bc -l) )); then
              echo "::error::Error rate exceeds 10% ($ERROR_RATE%). Manual review required."
              exit 1
            fi
          fi

      - name: Commit and push changes
        run: |
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          git config --local user.name "github-actions[bot]"

          git add data/

          # Create commit message with stats
          JURISDICTION="${{ steps.get-jurisdiction.outputs.jurisdiction }}"
          DATE=$(date -u '+%Y-%m-%d')

          git commit -m "Auto-update: ${JURISDICTION} crash data - ${DATE}" \
            -m "Validation: $(jq -r '.summary // "No summary"' data/.validation/latest_report.json 2>/dev/null || echo 'Completed')" \
            || echo "No changes to commit"

          git push

      - name: Generate summary
        run: |
          echo "## Validation Summary" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY

          if [ -f "data/.validation/latest_report.json" ]; then
            echo "| Metric | Value |" >> $GITHUB_STEP_SUMMARY
            echo "|--------|-------|" >> $GITHUB_STEP_SUMMARY
            echo "| Total Records | $(jq '.totalRecords' data/.validation/latest_report.json) |" >> $GITHUB_STEP_SUMMARY
            echo "| New Records | $(jq '.newRecords' data/.validation/latest_report.json) |" >> $GITHUB_STEP_SUMMARY
            echo "| Auto-Corrected | $(jq '.autoCorrections' data/.validation/latest_report.json) |" >> $GITHUB_STEP_SUMMARY
            echo "| Flagged | $(jq '.flagged' data/.validation/latest_report.json) |" >> $GITHUB_STEP_SUMMARY
            echo "| Clean Rate | $(jq '.cleanRate' data/.validation/latest_report.json)% |" >> $GITHUB_STEP_SUMMARY
          fi
```

### 10.2 Validation Requirements

**File:** `validation/requirements.txt`

```
pandas>=2.0.0
numpy>=1.24.0
requests>=2.28.0
python-dateutil>=2.8.0
tqdm>=4.65.0
```

---

## 11. Reporting & Monitoring

### 11.1 Report Structure

**File:** `data/.validation/latest_report.json`

```json
{
  "metadata": {
    "generatedAt": "2026-01-26T10:35:00Z",
    "jurisdiction": "henrico",
    "validationVersion": "1.0.0",
    "runType": "incremental"
  },

  "summary": "Validated 512 new records. 15 auto-corrected, 3 flagged, 494 clean.",

  "totalRecords": 24415,
  "newRecords": 512,
  "autoCorrections": 15,
  "flagged": 3,
  "cleanRate": 99.4,
  "errorRate": 0.01,

  "byFile": {
    "henrico_county_roads.csv": {
      "records": 18234,
      "new": 387,
      "corrected": 11,
      "flagged": 2
    },
    "henrico_no_interstate.csv": {
      "records": 22156,
      "new": 445,
      "corrected": 13,
      "flagged": 2
    },
    "henrico_all_roads.csv": {
      "records": 24415,
      "new": 512,
      "corrected": 15,
      "flagged": 3
    }
  },

  "issuesByCategory": {
    "categoryInvalid": 8,
    "consistencyMismatch": 4,
    "coordinateOutOfBounds": 2,
    "missingRequired": 1
  },

  "correctionsByField": {
    "Light Condition": 3,
    "Pedestrian?": 2,
    "Bike?": 1,
    "Weather Condition": 2
  },

  "flaggedRecords": [
    {
      "documentNbr": "VA2026001234",
      "issues": ["Severity=K but K_People=0"],
      "severity": "error"
    },
    {
      "documentNbr": "VA2026001235",
      "issues": ["Coordinate outside jurisdiction bounds"],
      "severity": "warning"
    }
  ]
}
```

### 11.2 Quality Dashboard (Future Enhancement)

Could add a validation dashboard tab to CRASH LENS showing:
- Data quality score over time
- Common issues by category
- Correction history
- Flagged records needing review

---

## 12. File Structure

### 12.1 Complete Directory Structure

```
Virginia/
├── .github/
│   └── workflows/
│       ├── download-data.yml          # Updated with validation
│       └── validate-only.yml          # Manual validation trigger
│
├── app/
│   └── index.html                     # CRASH LENS tool (unchanged)
│
├── config.json                        # Existing config (unchanged)
│
├── data/
│   ├── crashes.csv                    # Fallback (copy of county_roads)
│   ├── grants.csv                     # Unchanged
│   │
│   ├── henrico_county_roads.csv       # Validated
│   ├── henrico_no_interstate.csv      # Validated
│   ├── henrico_all_roads.csv          # Validated
│   │
│   ├── arlington_county_roads.csv     # Future: Validated
│   ├── arlington_no_interstate.csv    # Future: Validated
│   ├── arlington_all_roads.csv        # Future: Validated
│   │
│   ├── fairfax_county_all_roads.csv   # Future: Validated
│   │
│   └── .validation/                   # Validation state
│       ├── manifest.json              # Run metadata
│       ├── latest_report.json         # Most recent report
│       ├── corrections_log.csv        # All corrections made
│       ├── flagged_records.csv        # Records needing review
│       │
│       ├── validated_ids_henrico_county_roads.txt
│       ├── validated_ids_henrico_no_interstate.txt
│       ├── validated_ids_henrico_all_roads.txt
│       │
│       └── history/                   # Historical reports
│           ├── report_2026-01.json
│           └── report_2026-02.json
│
├── validation/                        # Validation system
│   ├── __init__.py
│   ├── run_validation.py              # Main entry point
│   ├── requirements.txt               # Python dependencies
│   │
│   ├── core/                          # Validation logic
│   │   ├── __init__.py
│   │   ├── validator.py               # Main validator class
│   │   ├── schema.py                  # Schema validation
│   │   ├── bounds.py                  # Geographic bounds
│   │   ├── categories.py              # Category validation
│   │   ├── consistency.py             # Cross-field logic
│   │   ├── completeness.py            # Missing values
│   │   ├── duplicates.py              # Duplicate detection
│   │   └── spatial.py                 # Overpass integration
│   │
│   ├── corrections/                   # Auto-correction engine
│   │   ├── __init__.py
│   │   ├── corrector.py               # Main corrector class
│   │   └── rules.py                   # Correction rule engine
│   │
│   ├── reference/                     # Reference data
│   │   ├── virginia_valid_values.json
│   │   ├── jurisdiction_bounds.json   # Extracted from config
│   │   └── correction_rules.json
│   │
│   ├── reporting/                     # Report generation
│   │   ├── __init__.py
│   │   └── reporter.py
│   │
│   └── utils/                         # Utilities
│       ├── __init__.py
│       ├── config_loader.py           # Load from config.json
│       ├── file_handler.py            # CSV read/write
│       └── overpass_client.py         # Overpass API client
│
├── download_crash_data.py             # Existing (unchanged)
├── download_grants_data.py            # Existing (unchanged)
│
└── docs/
    ├── DATA_VALIDATION_IMPLEMENTATION_PLAN.md  # This document
    └── ...
```

---

## 13. Implementation Phases

### Phase 1: Foundation (Week 1-2)

| Task | Priority | Complexity | Deliverable |
|------|----------|------------|-------------|
| Create validation/ folder structure | High | Low | Directory structure |
| Create virginia_valid_values.json | High | Low | Reference file |
| Extract jurisdiction_bounds.json from config | High | Low | Reference file |
| Create correction_rules.json | High | Medium | Reference file |
| Implement basic validator.py | High | Medium | Core module |
| Implement schema validation | High | Low | Core module |
| Implement category validation | High | Low | Core module |
| Unit tests for Phase 1 | High | Medium | Test suite |

**Milestone:** Can validate categories and schema locally

### Phase 2: Core Validation (Week 3-4)

| Task | Priority | Complexity | Deliverable |
|------|----------|------------|-------------|
| Implement bounds validation | High | Low | Core module |
| Implement consistency validation | High | Medium | Core module |
| Implement completeness validation | Medium | Low | Core module |
| Implement duplicate detection | Medium | Low | Core module |
| Implement corrector.py | High | Medium | Core module |
| Implement confidence-based correction | High | Medium | Core module |
| Implement corrections_log.csv output | High | Low | Logging |
| Unit tests for Phase 2 | High | Medium | Test suite |

**Milestone:** Full validation without spatial, can auto-correct

### Phase 3: Incremental Processing (Week 5)

| Task | Priority | Complexity | Deliverable |
|------|----------|------------|-------------|
| Implement validated_ids tracking | High | Medium | State management |
| Implement manifest.json | High | Low | State management |
| Implement delta detection | High | Medium | Core feature |
| Implement merge logic | High | Medium | Core feature |
| Implement re-validation triggers | Medium | Low | Core feature |
| Integration tests | High | Medium | Test suite |

**Milestone:** Incremental validation working locally

### Phase 4: Spatial Validation (Week 6-7)

| Task | Priority | Complexity | Deliverable |
|------|----------|------------|-------------|
| Implement overpass_client.py | Medium | Medium | Utility |
| Implement coordinate-to-road validation | Medium | High | Spatial module |
| Implement road name matching | Medium | High | Spatial module |
| Implement caching for Overpass | Medium | Medium | Performance |
| Implement coordinate snapping | Low | High | Auto-correction |
| Integration tests for spatial | Medium | Medium | Test suite |

**Milestone:** Spatial validation working (optional feature)

### Phase 5: GitHub Actions Integration (Week 8)

| Task | Priority | Complexity | Deliverable |
|------|----------|------------|-------------|
| Update download-data.yml | High | Medium | Workflow |
| Add validation step to workflow | High | Medium | Workflow |
| Implement error rate threshold | High | Low | Safety check |
| Implement summary generation | Medium | Low | Reporting |
| Create validate-only.yml workflow | Low | Low | Workflow |
| End-to-end testing | High | High | Test suite |

**Milestone:** Fully automated pipeline running

### Phase 6: Multi-Jurisdiction Expansion (Week 9-10)

| Task | Priority | Complexity | Deliverable |
|------|----------|------------|-------------|
| Add Arlington jurisdiction | High | Low | Data |
| Add Fairfax jurisdiction | Medium | Low | Data |
| Add 5 more high-priority jurisdictions | Medium | Low | Data |
| Implement --all flag for batch processing | Medium | Medium | Feature |
| Documentation for adding new jurisdictions | Medium | Low | Documentation |
| Performance optimization for batch | Low | Medium | Performance |

**Milestone:** Multiple jurisdictions validated automatically

### Phase 7: Monitoring & Polish (Week 11-12)

| Task | Priority | Complexity | Deliverable |
|------|----------|------------|-------------|
| Create validation dashboard (optional) | Low | High | UI |
| Implement historical report tracking | Low | Low | Reporting |
| Add email/Slack notifications | Low | Medium | Alerting |
| Performance profiling and optimization | Medium | Medium | Performance |
| Documentation completion | Medium | Low | Documentation |
| User acceptance testing | High | Medium | Quality |

**Milestone:** Production-ready system

---

## 14. Risk Mitigation

### 14.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Overpass API rate limiting | Medium | Medium | Implement caching, fallback endpoints |
| Source data format changes | Low | High | Schema validation, alert on mismatch |
| Large dataset performance | Medium | Medium | Incremental processing, chunked I/O |
| Incorrect auto-corrections | Low | High | Confidence thresholds, audit logging |
| GitHub Actions timeout | Low | Medium | Optimize processing, split large jobs |

### 14.2 Data Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Data corruption during correction | Low | High | Backup before correction, atomic writes |
| Loss of validation state | Low | Medium | Git-tracked state files, checksums |
| Inconsistent multi-file state | Medium | Medium | Transaction-like processing, rollback |
| Stale reference data | Medium | Low | Version tracking, periodic review |

### 14.3 Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Pipeline fails silently | Low | High | Error rate threshold, notifications |
| Disk space exhaustion | Low | Low | Cleanup old archives, monitor usage |
| Dependency vulnerabilities | Medium | Medium | Dependabot, regular updates |

---

## 15. Appendices

### Appendix A: Column Mapping Reference

| COL Constant | CSV Column Name | Data Type | Required |
|--------------|-----------------|-----------|----------|
| COL.ID | Document Nbr | String | Yes |
| COL.YEAR | Crash Year | Integer | Yes |
| COL.DATE | Crash Date | Date | Yes |
| COL.TIME | Crash Military Time | String | No |
| COL.SEVERITY | Crash Severity | String(1) | Yes |
| COL.K | K_People | Integer | No |
| COL.A | A_People | Integer | No |
| COL.B | B_People | Integer | No |
| COL.C | C_People | Integer | No |
| COL.COLLISION | Collision Type | String | Yes |
| COL.WEATHER | Weather Condition | String | No |
| COL.LIGHT | Light Condition | String | No |
| COL.SURFACE | Roadway Surface Condition | String | No |
| COL.INT_TYPE | Intersection Type | String | No |
| COL.TRAFFIC_CTRL | Traffic Control Type | String | No |
| COL.ROUTE | RTE Name | String | No |
| COL.NODE | Node | String | No |
| COL.X | x | Float | No |
| COL.Y | y | Float | No |
| COL.PED | Pedestrian? | String | No |
| COL.BIKE | Bike? | String | No |
| COL.ALCOHOL | Alcohol? | String | No |
| COL.SPEED | Speed? | String | No |
| COL.NIGHT | Night? | String | No |

### Appendix B: EPDO Weights

| Severity | Weight | Description |
|----------|--------|-------------|
| K | 462 | Fatal |
| A | 62 | Serious Injury |
| B | 12 | Minor Injury |
| C | 5 | Possible Injury |
| O | 1 | Property Damage Only |

### Appendix C: Virginia Jurisdictions with Own Roads

Only these jurisdictions generate 3 CSV files:

| Jurisdiction ID | Name | Files |
|-----------------|------|-------|
| henrico | Henrico County | county_roads, no_interstate, all_roads |
| arlington | Arlington County | county_roads, no_interstate, all_roads |

All other 131 jurisdictions generate only `{jurisdiction}_all_roads.csv`

### Appendix D: API Endpoints

| Service | Endpoint | Purpose |
|---------|----------|---------|
| Virginia Roads | https://virginiaroads.org | Crash data source |
| Overpass API | https://overpass-api.de/api/interpreter | Road network |
| TIGERweb | https://tigerweb.geo.census.gov | Boundaries |
| Mapbox | https://api.mapbox.com | Geocoding fallback |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-26 | Claude | Initial comprehensive plan |

---

*End of Implementation Plan*
