# INVENTION DISCLOSURE DOCUMENT

## CRASH LENS: AI-Powered Traffic Safety Analysis Platform

---

### DOCUMENT CONTROL

| Field | Value |
|-------|-------|
| **Invention Title** | CRASH LENS: System and Method for AI-Powered Traffic Safety Analysis with Automated Countermeasure Recommendation |
| **Inventor** | [YOUR FULL LEGAL NAME] |
| **Date of Conception** | [DATE YOU FIRST CONCEIVED THE INVENTION] |
| **Date of First Reduction to Practice** | [DATE FIRST WORKING VERSION WAS CREATED] |
| **Date of First Public Disclosure** | November 28, 2025 |
| **Filing Deadline** | November 28, 2026 |

---

## 1. BACKGROUND OF THE INVENTION

### 1.1 Field of the Invention

This invention relates to computer-implemented systems and methods for traffic safety analysis, and more particularly to an integrated platform that combines crash data analysis, artificial intelligence, and automated countermeasure recommendation for transportation safety engineering.

### 1.2 Description of Related Art

Traffic safety analysis has traditionally relied on manual processes involving:

1. **Manual Data Collection**: Engineers manually extract crash data from state databases, requiring significant time and expertise in database query languages.

2. **Spreadsheet-Based Analysis**: Crash data is analyzed using general-purpose spreadsheet software, requiring custom formulas and manual aggregation.

3. **Separate CMF Lookups**: The FHWA Crash Modification Factor Clearinghouse requires engineers to manually search for applicable countermeasures, a time-consuming process requiring domain expertise.

4. **Manual Warrant Analysis**: Signal warrant analysis per MUTCD standards requires manual calculation and threshold comparison.

5. **Disconnected Grant Applications**: Identifying applicable federal grants requires separate research, with no integration to crash analysis data.

6. **Before/After Studies**: Treatment effectiveness evaluation requires manual statistical calculations, often without proper regression-to-mean correction.

### 1.3 Problems with Prior Art

Existing approaches suffer from:

- **Fragmentation**: Multiple disconnected tools require context switching and manual data transfer
- **Expertise Barriers**: Complex statistical methods require specialized training
- **Time Inefficiency**: Manual processes delay safety improvements
- **Inconsistency**: Different analysts may reach different conclusions from same data
- **No AI Integration**: Existing tools lack natural language interfaces for rapid analysis
- **Poor State Management**: No cross-context synchronization between analysis modes

---

## 2. SUMMARY OF THE INVENTION

### 2.1 Brief Description

CRASH LENS is an integrated, browser-based traffic safety analysis platform that combines:

1. **Automated Crash Data Processing** with jurisdiction-specific filtering
2. **AI-Powered Analysis Assistant** using function-calling for database queries
3. **EPDO-Based Location Ranking Algorithm** for prioritization
4. **Intelligent Countermeasure Matching** with relevance scoring
5. **Automated Signal Warrant Analysis** per MUTCD standards
6. **Federal Grant Program Matching** based on crash profiles
7. **Before/After Statistical Framework** with Empirical Bayes method
8. **Cross-Tab State Synchronization** for seamless multi-modal analysis

### 2.2 Objects of the Invention

The primary objects of this invention are to:

1. Provide an integrated platform eliminating fragmented tool usage
2. Enable AI-assisted crash pattern analysis through natural language
3. Automate countermeasure recommendation based on location-specific crash profiles
4. Reduce time required for traffic safety engineering decisions
5. Improve consistency and reproducibility of safety analyses
6. Enable non-expert users to perform sophisticated safety evaluations

---

## 3. DETAILED DESCRIPTION OF THE INVENTION

### 3.1 System Architecture Overview

The system comprises the following interconnected modules:

```
┌─────────────────────────────────────────────────────────────────┐
│                    CRASH LENS PLATFORM                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Data Layer  │───▶│ State Layer  │───▶│   UI Layer   │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ ArcGIS API   │    │ crashState   │    │  Dashboard   │      │
│  │ Integration  │    │ cmfState     │    │  Analysis    │      │
│  │              │    │ grantState   │    │  Map         │      │
│  │ CSV/JSON     │    │ baState      │    │  CMF Tab     │      │
│  │ Processing   │    │ selectionSt  │    │  Grants Tab  │      │
│  └──────────────┘    └──────────────┘    │  B/A Study   │      │
│                             │            │  AI Chat     │      │
│                             ▼            └──────────────┘      │
│                      ┌──────────────┐                          │
│                      │ Cross-Tab    │                          │
│                      │ Sync Engine  │                          │
│                      └──────────────┘                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Innovation 1: EPDO-Based Location Ranking Algorithm

#### 3.2.1 Technical Description

The system implements a novel composite scoring algorithm for location prioritization:

```
COMPOSITE_SCORE = (K × W_fatal) + (A × W_serious) + (VRU × W_vru) + (EPDO / N)

Where:
  K     = Count of fatal crashes
  A     = Count of serious injury crashes
  VRU   = Count of vulnerable road user incidents (pedestrian + bicycle)
  EPDO  = Equivalent Property Damage Only score
  W_fatal   = 100 (weight coefficient for fatal crashes)
  W_serious = 50  (weight coefficient for serious injury crashes)
  W_vru     = 30  (weight coefficient per VRU incident)
  N         = 100 (EPDO normalization factor)
```

#### 3.2.2 EPDO Calculation

```
EPDO = (K × 462) + (A × 62) + (B × 12) + (C × 5) + (O × 1)

Where severity classifications follow KABCO scale:
  K = Fatal
  A = Suspected Serious Injury
  B = Suspected Minor Injury
  C = Possible Injury
  O = No Apparent Injury (Property Damage Only)
```

#### 3.2.3 Novel Aspects

1. **Dual-Weight System**: Combines raw severity counts with statistical crash cost proxy
2. **VRU Prioritization**: Explicit weighting for pedestrian/bicycle safety
3. **Normalization**: EPDO divided by 100 to prevent double-counting severity
4. **Evidence-Based Coefficients**: Weights derived from crash cost research

### 3.3 Innovation 2: AI-Powered Countermeasure Recommendation

#### 3.3.1 Technical Description

The system integrates large language models (LLMs) with function-calling capabilities to:

1. Receive natural language queries about crash locations
2. Build detailed crash profiles from location-specific data
3. Invoke structured database search tools
4. Synthesize results into actionable recommendations

#### 3.3.2 Function-Calling Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   User      │────▶│  LLM Core   │────▶│  CMF        │
│   Query     │     │  (Claude/   │     │  Database   │
│             │     │   Gemini)   │     │  Search     │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                   │
                           ▼                   ▼
                    ┌─────────────┐     ┌─────────────┐
                    │  Context    │◀────│  Search     │
                    │  Synthesis  │     │  Results    │
                    └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Formatted  │
                    │  Response   │
                    └─────────────┘
```

#### 3.3.3 CMF Search Tool Schema

```json
{
  "name": "search_cmf_database",
  "description": "Search CMF database for countermeasures",
  "input_schema": {
    "type": "object",
    "properties": {
      "crashTypes": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Crash types to match (rear-end, angle, pedestrian, etc.)"
      },
      "roadType": {
        "type": "string",
        "description": "Road type (intersection, segment, ramp)"
      },
      "severity": {
        "type": "string",
        "description": "Target severity (all, fatal, injury)"
      }
    }
  }
}
```

#### 3.3.4 Novel Aspects

1. **Tool-Augmented LLM**: AI can invoke database searches dynamically
2. **Context-Aware Queries**: Search parameters derived from crash profile
3. **Multi-Provider Support**: Works with Claude, Gemini, or OpenAI
4. **Secure Key Management**: Client-side encryption of API credentials

### 3.4 Innovation 3: Intelligent Countermeasure Matching

#### 3.4.1 CMF Enrichment Algorithm

For each candidate countermeasure, the system calculates:

```
RELEVANCE_SCORE = f(severity_match, collision_match, factor_match,
                    condition_match, location_match, confidence)

Where:
  severity_match  = Alignment between crash K+A distribution and CMF target
  collision_match = Overlap between crash types and CMF applicability
  factor_match    = Match on contributing factors (alcohol, speed, etc.)
  condition_match = Weather/light condition alignment
  location_match  = Intersection vs. segment compatibility
  confidence      = CMF statistical quality (rating + CI width)
```

#### 3.4.2 Expected Reduction Calculation

```
ANNUAL_PREVENTED = (Applicable_Crashes / Years_of_Data) × (CRF / 100)

Where:
  Applicable_Crashes = Crashes matching CMF target crash types
  Years_of_Data      = Number of years in dataset
  CRF                = Crash Reduction Factor (1 - CMF) × 100
```

#### 3.4.3 Confidence Quantification

```
If CI_width ≤ 0.2:  confidence = "High"
If CI_width ≤ 0.4:  confidence = "Medium"
If CI_width > 0.4:  confidence = "Low"

CI_display = ±((CI_high - CI_low) / 2)%
```

#### 3.4.4 Novel Aspects

1. **Crash-Type-Specific Reduction**: CMF effectiveness limited to matching crashes
2. **Multi-Dimensional Relevance**: Considers 6+ factors in scoring
3. **Confidence Integration**: Statistical CI affects recommendation confidence
4. **Cost Tier Mapping**: Countermeasures categorized by implementation cost

### 3.5 Innovation 4: Automated Signal Warrant Analysis

#### 3.5.1 MUTCD Warrant 7 Implementation

```
WARRANT_7_THRESHOLDS = {
  "1-year": {
    "4-leg": { "all": 5, "ka": 3 },
    "3-leg": { "all": 4, "ka": 3 }
  },
  "3-year": {
    "4-leg": { "all": 6, "ka": 4 },
    "3-leg": { "all": 5, "ka": 4 }
  }
}

WARRANT_MET = (Annual_Angle_Ped ≥ threshold.all) OR (Annual_KA ≥ threshold.ka)
```

#### 3.5.2 Crash Classification for Warrants

```
FOR each crash at intersection:
  IF collision_type CONTAINS "angle" OR pedestrian_flag = TRUE:
    angle_ped_count++
    IF severity IN ["K", "A"]:
      angle_ped_ka++

annual_angle_ped = angle_ped_count / years_of_data
annual_ka = angle_ped_ka / years_of_data
```

#### 3.5.3 Novel Aspects

1. **MUTCD Table 4C-2 Automation**: Direct implementation of federal standards
2. **Year-Weighted Averaging**: Handles variable data availability
3. **Crash Type Filtering**: MUTCD-specific angle/pedestrian prioritization
4. **Intersection Isolation**: Excludes non-intersection crashes automatically

### 3.6 Innovation 5: Cross-Tab State Synchronization

#### 3.6.1 State Architecture

```javascript
// Primary state objects
crashState   = { sampleRows, aggregates, loaded, ... }
cmfState     = { selectedLocation, filteredCrashes, crashProfile, ... }
grantState   = { allRankedLocations, selectedLocationIndices, ... }
baState      = { locationCrashes, treatmentDate, results, ... }
selectionState = { location, crashes, crashProfile, fromTab, ... }
```

#### 3.6.2 Context Priority Resolution

```
CONTEXT_PRIORITY:
  1. cmfState.selectedLocation (if active)
  2. selectionState.location (from map/hotspots)
  3. warrantsState.selectedLocation (if active)
  4. FALLBACK: County-wide crashState.aggregates
```

#### 3.6.3 Cross-Tab Navigation Flow

```
User clicks location on Map
       │
       ▼
selectionState populated with:
  - location name
  - crash records
  - computed profile
       │
       ▼
Action buttons appear:
  [CMF] [Grants] [B/A Study] [MUTCD]
       │
       ▼
User clicks [CMF]
       │
       ▼
cmfState.selectedLocation = selectionState.location
cmfState.locationCrashes = selectionState.crashes
       │
       ▼
CMF Tab activates with pre-populated data
```

#### 3.6.4 Novel Aspects

1. **Hierarchical Context**: Priority-based resolution prevents ambiguity
2. **State Persistence**: Selections survive tab switches
3. **Bidirectional Sync**: Any tab can read/write shared selection
4. **Instant Profile Computation**: Crash profiles calculated on selection

### 3.7 Innovation 6: Grant Program Matching

#### 3.7.1 Multi-Criteria Matching Algorithm

```
FOR each location in ranked_list:
  eligible_grants = []

  IF location.K + location.A >= KA_THRESHOLD:
    eligible_grants.add("HSIP")

  IF location.ped > 0 OR location.bike > 0:
    eligible_grants.add("TAP")
    eligible_grants.add("SRTS")

  IF location.K >= FATAL_THRESHOLD:
    eligible_grants.add("SS4A")

  IF location.epdo >= EPDO_THRESHOLD:
    eligible_grants.add("STBG")

  location.matchingGrants = eligible_grants
  location.bestMatch = eligible_grants[0]
```

#### 3.7.2 CFDA-Based Filtering

```
SAFETY_CFDA_NUMBERS = [
  "20.600",  // State and Community Highway Safety (NHTSA 402)
  "20.601",  // Alcohol Impaired Driving Countermeasures (405d)
  "20.205",  // Highway Planning and Construction (HSIP)
  "20.616",  // Safe Streets and Roads for All (SS4A)
  ...
]
```

#### 3.7.3 Novel Aspects

1. **Profile-Based Matching**: Crash characteristics determine eligibility
2. **Multi-Program Support**: Identifies all applicable programs, not just primary
3. **CFDA Integration**: Uses federal catalog numbers for accurate filtering
4. **Priority Ranking**: Best match identified per location

### 3.8 Innovation 7: Before/After Statistical Framework

#### 3.8.1 Study Period Calculation

```
treatment_date = user_specified_date
construction_duration = user_specified_months (default: 3)

before_start = treatment_date - study_years
before_end   = treatment_date - 1 day

after_start  = treatment_date + construction_duration
after_end    = after_start + study_years
```

#### 3.8.2 Analysis Methods

```
NAIVE METHOD:
  effectiveness = (before_crashes - after_crashes) / before_crashes × 100

EMPIRICAL BAYES METHOD:
  expected_after = EB_estimate(before_crashes, reference_sites, RTM_factor)
  effectiveness = (expected_after - after_crashes) / expected_after × 100
```

#### 3.8.3 Novel Aspects

1. **Construction Exclusion**: Automatically removes construction period
2. **Dual Methods**: Supports both Naive and EB approaches
3. **RTM Correction**: Empirical Bayes accounts for regression-to-mean
4. **Flexible Periods**: 1, 3, or 5-year study windows

---

## 4. CLAIMS OUTLINE

### Independent Claims

1. **System Claim**: A computer-implemented traffic safety analysis system comprising [all major components]

2. **Method Claim**: A method for automated countermeasure recommendation comprising [key process steps]

3. **Method Claim**: A method for signal warrant analysis comprising [MUTCD automation steps]

### Dependent Claims

4. System of claim 1 wherein EPDO calculation uses [specific weights]
5. System of claim 1 further comprising AI assistant with function-calling
6. Method of claim 2 wherein relevance scoring considers [multiple factors]
7. Method of claim 2 further comprising confidence interval integration
8. Method of claim 3 wherein crash classification includes [angle/ped logic]
9. System of claim 1 further comprising grant program matching
10. System of claim 1 further comprising before/after statistical analysis

---

## 5. FIGURES LIST

1. **Figure 1**: System Architecture Block Diagram
2. **Figure 2**: EPDO Calculation Flowchart
3. **Figure 3**: CMF Matching Algorithm Flowchart
4. **Figure 4**: AI Function-Calling Sequence Diagram
5. **Figure 5**: Cross-Tab State Synchronization Diagram
6. **Figure 6**: Signal Warrant Analysis Flowchart
7. **Figure 7**: Grant Matching Decision Tree
8. **Figure 8**: Before/After Study Timeline Diagram
9. **Figure 9**: User Interface Screenshots (Dashboard, Map, CMF Tab)

---

## 6. PRIOR ART CONSIDERED

### 6.1 FHWA CMF Clearinghouse
- Web database of crash modification factors
- **Distinction**: CRASH LENS integrates CMF data with location-specific crash profiles and AI-powered recommendation

### 6.2 AASHTO Highway Safety Manual
- Establishes methodologies for safety analysis
- **Distinction**: CRASH LENS automates HSM procedures that are traditionally manual

### 6.3 State DOT Crash Analysis Tools
- Various states have crash data portals
- **Distinction**: CRASH LENS provides integrated analysis beyond data display, including AI and countermeasure recommendation

### 6.4 Commercial Traffic Analysis Software
- Products like Synchro, VISSIM focus on traffic operations
- **Distinction**: CRASH LENS focuses specifically on safety analysis with crash-based decision support

---

## 7. INVENTOR DECLARATION

I, the undersigned, declare that:

1. I am the sole inventor of the invention described herein
2. The invention was conceived and reduced to practice by me
3. I am not aware of any prior art that anticipates or renders obvious the claimed invention
4. The first public disclosure occurred on November 28, 2025
5. I understand that filing a provisional patent application will establish a priority date

**Signature**: _________________________

**Printed Name**: _________________________

**Date**: _________________________

---

## 8. WITNESSES

*(For additional protection, have two witnesses sign who understand the invention)*

**Witness 1**:
- Signature: _________________________
- Printed Name: _________________________
- Date: _________________________

**Witness 2**:
- Signature: _________________________
- Printed Name: _________________________
- Date: _________________________

---

## APPENDICES

- **Appendix A**: Complete source code reference (index.html)
- **Appendix B**: Configuration files (config.json)
- **Appendix C**: Data processing scripts (download_crash_data.py, download_grants_data.py)
- **Appendix D**: Sample crash data structure
- **Appendix E**: CMF database schema
