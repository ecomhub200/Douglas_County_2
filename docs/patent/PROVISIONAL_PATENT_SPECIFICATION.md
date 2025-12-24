# PROVISIONAL PATENT APPLICATION

## SYSTEM AND METHOD FOR AI-POWERED TRAFFIC SAFETY ANALYSIS WITH AUTOMATED COUNTERMEASURE RECOMMENDATION

---

### FILING INFORMATION

| Field | Value |
|-------|-------|
| **Application Type** | Provisional Patent Application |
| **Applicant Type** | Micro Entity |
| **Inventor** | [YOUR FULL LEGAL NAME] |
| **Citizenship** | [YOUR CITIZENSHIP] |
| **Residence** | [CITY, STATE, COUNTRY] |
| **Mailing Address** | [COMPLETE MAILING ADDRESS] |
| **Email** | [EMAIL ADDRESS] |
| **Filing Fee** | $190 (Micro Entity) |

---

## TITLE OF THE INVENTION

**SYSTEM AND METHOD FOR AI-POWERED TRAFFIC SAFETY ANALYSIS WITH AUTOMATED COUNTERMEASURE RECOMMENDATION**

---

## CROSS-REFERENCE TO RELATED APPLICATIONS

This application claims the benefit of provisional application and establishes priority as of the filing date.

---

## FIELD OF THE INVENTION

The present invention relates generally to computer-implemented systems and methods for traffic safety analysis, and more particularly to an integrated platform that combines crash data analysis, artificial intelligence with function-calling capabilities, weighted severity scoring algorithms, automated countermeasure recommendation, and cross-context state synchronization for transportation safety engineering decision support.

---

## BACKGROUND OF THE INVENTION

### Technical Field

Traffic safety analysis is a critical function performed by transportation agencies to reduce crashes, injuries, and fatalities on public roadways. The Highway Safety Improvement Program (HSIP), mandated by federal law, requires state and local agencies to systematically analyze crash data and implement evidence-based safety countermeasures.

### Description of Related Art

Current traffic safety analysis relies on fragmented, manual processes:

**Crash Data Analysis**: Engineers must manually query state crash databases, export data to spreadsheet software, and create custom formulas for aggregation and analysis. This process requires expertise in database query languages and statistical analysis.

**Countermeasure Selection**: The Federal Highway Administration (FHWA) maintains the Crash Modification Factor (CMF) Clearinghouse, a database of safety countermeasures with effectiveness ratings. Engineers must manually search this database, interpret results, and match countermeasures to specific crash patterns—a time-consuming process requiring domain expertise.

**Signal Warrant Analysis**: The Manual on Uniform Traffic Control Devices (MUTCD) specifies warrants for traffic signal installation. Engineers must manually calculate crash-based warrants per MUTCD Table 4C-2, requiring precise threshold comparisons.

**Grant Identification**: Federal safety grants (HSIP, SS4A, TAP, SRTS) have specific eligibility criteria. Engineers must separately research available programs and manually determine location eligibility.

**Before/After Studies**: Evaluating treatment effectiveness requires statistical analysis accounting for regression-to-mean bias. The Empirical Bayes method, while preferred, requires complex calculations rarely automated in existing tools.

### Problems Solved by the Invention

The present invention addresses the following deficiencies in the prior art:

1. **Fragmentation**: Existing approaches require multiple disconnected tools with manual data transfer between them.

2. **Expertise Barriers**: Complex statistical methods and federal compliance requirements demand specialized training unavailable to many agencies.

3. **Time Inefficiency**: Manual processes delay identification and implementation of safety improvements, resulting in preventable crashes.

4. **Inconsistency**: Different analysts may reach different conclusions from the same data due to methodological variations.

5. **No AI Integration**: Existing tools lack natural language interfaces that could accelerate analysis and improve accessibility.

6. **Poor State Management**: No existing solution provides seamless context preservation when switching between different analysis modes.

---

## SUMMARY OF THE INVENTION

The present invention provides an integrated, browser-based traffic safety analysis platform comprising:

**A data ingestion module** configured to receive crash records from transportation agency databases, including location identifiers, severity classifications according to the KABCO scale, collision types, contributing factors, weather conditions, light conditions, and temporal data.

**A weighted severity processor** configured to compute Equivalent Property Damage Only (EPDO) scores by applying differential weights to crash severity categories, enabling standardized comparison of locations with varying crash profiles.

**A location ranking engine** configured to generate composite priority scores incorporating fatal crash weighting, serious injury weighting, vulnerable road user incident weighting, and normalized EPDO components.

**A crash profile generator** configured to analyze location-specific crash data and produce multidimensional profiles including severity distributions, collision type frequencies, contributing factor prevalence, environmental condition distributions, and vulnerable road user involvement rates.

**A countermeasure matching module** configured to identify applicable safety interventions by computing relevance scores based on crash profile characteristics, road properties, and Crash Modification Factor (CMF) database records.

**An artificial intelligence assistant** configured with function-calling capabilities to receive natural language queries, invoke structured database searches, and generate synthesized safety recommendations with explanatory reasoning.

**A signal warrant analyzer** configured to evaluate MUTCD Warrant 7 (Crash Experience) thresholds by classifying crashes according to federal standards and computing year-weighted annual averages.

**A grant matching module** configured to identify eligible federal funding programs based on location crash profiles, severity thresholds, and vulnerable road user involvement.

**A before/after analysis module** configured to evaluate treatment effectiveness using Empirical Bayes statistical methods with automatic construction period exclusion and regression-to-mean correction.

**A cross-tab state synchronization engine** configured to maintain context awareness across multiple analysis modes, enabling seamless navigation with preserved selections and computed profiles.

---

## BRIEF DESCRIPTION OF THE DRAWINGS

**Figure 1** is a block diagram illustrating the overall system architecture of the traffic safety analysis platform.

**Figure 2** is a flowchart illustrating the EPDO calculation and location ranking algorithm.

**Figure 3** is a flowchart illustrating the countermeasure matching and relevance scoring process.

**Figure 4** is a sequence diagram illustrating the AI function-calling architecture for database queries.

**Figure 5** is a state diagram illustrating cross-tab synchronization and context resolution.

**Figure 6** is a flowchart illustrating the MUTCD Warrant 7 analysis process.

**Figure 7** is a decision tree illustrating the grant program matching algorithm.

**Figure 8** is a timeline diagram illustrating the before/after study period calculation.

---

## DETAILED DESCRIPTION OF THE INVENTION

### Overview

Referring now to Figure 1, the traffic safety analysis platform 100 comprises a data layer 110, a state management layer 120, a processing layer 130, an AI integration layer 140, and a user interface layer 150.

The data layer 110 includes a crash data ingestion module 111 configured to interface with transportation agency databases via REST APIs, a configuration module 112 storing jurisdiction-specific parameters, and a CMF database 113 containing countermeasure effectiveness records.

The state management layer 120 includes a primary crash state object 121, a CMF analysis state object 122, a grant analysis state object 123, a before/after study state object 124, and a cross-tab selection state object 125.

### Embodiment 1: EPDO-Based Location Ranking Algorithm

Referring now to Figure 2, the location ranking process 200 begins at step 210 where the system receives crash records for all locations within a jurisdiction.

At step 220, for each location, the system computes an EPDO score according to the formula:

```
EPDO = (K × 462) + (A × 62) + (B × 12) + (C × 5) + (O × 1)
```

Where K represents fatal crashes, A represents suspected serious injury crashes, B represents suspected minor injury crashes, C represents possible injury crashes, and O represents property damage only crashes.

The weights (462, 62, 12, 5, 1) are derived from comprehensive crash cost research and represent the relative societal cost of each severity level.

At step 230, the system counts vulnerable road user (VRU) incidents by summing pedestrian-involved and bicycle-involved crashes at each location.

At step 240, the system computes a composite priority score according to the formula:

```
COMPOSITE_SCORE = (K × 100) + (A × 50) + (VRU × 30) + (EPDO / 100)
```

The weighting coefficients (100 for fatal, 50 for serious injury, 30 per VRU incident) prioritize the most severe outcomes while the normalized EPDO component ensures locations with high volumes of lower-severity crashes are not overlooked.

At step 250, locations are sorted by composite score in descending order and assigned to priority tiers: High Priority (ranks 1-50), Moderate Priority (ranks 51-100), Watch List (ranks 101-200), and Other (ranks 201+).

### Embodiment 2: Intelligent Countermeasure Matching

Referring now to Figure 3, the countermeasure matching process 300 begins at step 310 where the system receives a location identifier and retrieves associated crash records.

At step 320, the system generates a detailed crash profile comprising:
- Severity distribution (counts and percentages for K, A, B, C, O)
- Collision type distribution (rear-end, angle, sideswipe, head-on, pedestrian, bicycle, etc.)
- Contributing factor prevalence (alcohol, speed, distraction, drowsy, unrestrained)
- Environmental conditions (weather distribution, light condition distribution)
- Vulnerable road user counts (pedestrian-involved, bicycle-involved)
- Calculated EPDO score

At step 330, the system queries the CMF database 113 to retrieve candidate countermeasures matching the location type (intersection or segment) and applicable crash types.

At step 340, for each candidate countermeasure, the system computes a relevance score according to a multidimensional matching algorithm considering:

**Severity Match (weight: 0.25)**: Alignment between the crash profile's K+A percentage and the countermeasure's target severity

**Collision Type Match (weight: 0.30)**: Overlap coefficient between crash types present at the location and crash types addressed by the countermeasure

**Contributing Factor Match (weight: 0.20)**: Match between prevalent contributing factors (alcohol, speed, etc.) and countermeasure effectiveness for those factors

**Environmental Match (weight: 0.10)**: Alignment between crash timing/conditions and countermeasure applicability

**Confidence Adjustment (weight: 0.15)**: Modification based on CMF statistical quality as indicated by star rating and confidence interval width

At step 350, the system computes expected crash reduction for each countermeasure:

```
EXPECTED_REDUCTION = (Applicable_Crashes / Years_of_Data) × (CRF_Percentage / 100)
```

Where Applicable_Crashes includes only those crash types matching the countermeasure's target categories, and CRF_Percentage is the Crash Reduction Factor derived from the CMF value (CRF = (1 - CMF) × 100).

At step 360, countermeasures are ranked by relevance score and presented with supporting data including expected annual crashes prevented, implementation cost tier, and confidence level.

### Embodiment 3: AI-Powered Analysis with Function Calling

Referring now to Figure 4, the AI integration architecture 400 implements a tool-augmented large language model (LLM) system.

At step 410, the user submits a natural language query through the chat interface, such as "What countermeasures would reduce rear-end crashes at Main Street and Oak Avenue?"

At step 420, the system constructs a context payload including:
- The user's query
- Location-specific crash profile (if a location is selected)
- System instructions defining available tools and response format

At step 430, the system transmits the payload to an LLM API (supporting Claude, Gemini, or OpenAI models).

At step 440, if the LLM determines that database access is required, it generates a tool invocation request specifying:
- Tool name: "search_cmf_database"
- Parameters: crash types, road type, severity focus, keyword filters

At step 450, the system executes the database search using the specified parameters and returns structured results to the LLM.

At step 460, the LLM synthesizes the search results with the crash profile context and generates a natural language response including:
- Recommended countermeasures with relevance explanations
- Expected effectiveness based on location-specific crash patterns
- Implementation considerations and cost estimates
- Supporting data from the CMF database

At step 470, the response is rendered in the user interface with formatted tables, severity badges, and confidence indicators.

### Embodiment 4: Automated Signal Warrant Analysis

Referring now to Figure 6, the signal warrant analysis process 600 implements MUTCD Warrant 7 (Crash Experience) per federal standards.

At step 610, the user selects an intersection location for warrant analysis.

At step 620, the system retrieves crash records for the selected intersection.

At step 630, the system classifies crashes according to MUTCD criteria:
- Angle crashes: Collision type containing "angle"
- Pedestrian crashes: Pedestrian involvement flag is true
- Severity: Fatal (K) or Serious Injury (A)

At step 640, the system computes annual averages:

```
Annual_Angle_Ped = Total_Angle_Ped_Crashes / Years_of_Data
Annual_KA = Total_Angle_Ped_KA_Crashes / Years_of_Data
```

At step 650, the system evaluates warrant thresholds per MUTCD Table 4C-2:

For 4-leg intersections with 1-year data:
- Threshold met if Annual_Angle_Ped ≥ 5, OR
- Threshold met if Annual_KA ≥ 3

For 3-leg intersections with 1-year data:
- Threshold met if Annual_Angle_Ped ≥ 4, OR
- Threshold met if Annual_KA ≥ 3

At step 660, the system generates a warrant report including:
- Crash counts and annual averages
- Threshold comparison results
- Warrant satisfaction status (Met/Not Met)
- Supporting crash details and severity breakdown

### Embodiment 5: Cross-Tab State Synchronization

Referring now to Figure 5, the state synchronization architecture 500 maintains context awareness across multiple analysis modes.

The system defines five state objects:

**crashState 510**: Contains raw crash data (sampleRows), pre-computed aggregates, and global metadata.

**cmfState 520**: Contains CMF tab-specific data including selected location, filtered crashes, and computed crash profile.

**grantState 530**: Contains grant analysis data including ranked locations and matched programs.

**baState 540**: Contains before/after study data including treatment date, study periods, and results.

**selectionState 550**: Contains cross-tab selection data including location identifier, crash records, computed profile, and originating tab.

When a user selects a location in any tab (step 560), the system:

1. Populates selectionState with location identifier and associated crash records
2. Computes a crash profile for the selected location
3. Stores the originating tab identifier

When the user navigates to a different tab (step 570), the system:

1. Checks selectionState for an active selection
2. If present, pre-populates the destination tab with the selected location
3. Applies any tab-specific filters while preserving the core selection
4. Updates the UI to reflect the active context

The context resolution algorithm (step 580) follows a priority hierarchy:
1. If cmfState.selectedLocation is set, use CMF context
2. Else if selectionState.location is set, use general selection context
3. Else if warrantsState.selectedLocation is set, use warrants context
4. Else fall back to county-wide crashState.aggregates

This architecture enables seamless workflows such as:
- Select location on map → View countermeasures in CMF tab → Check grant eligibility → Run before/after study
- All without re-selecting the location or losing context

### Embodiment 6: Grant Program Matching

Referring now to Figure 7, the grant matching algorithm 700 automatically identifies eligible federal funding programs.

At step 710, the system retrieves the crash profile for a candidate location.

At step 720, the system evaluates HSIP eligibility:
- If (K + A) ≥ HSIP_THRESHOLD, add "HSIP" to eligible programs

At step 730, the system evaluates SS4A eligibility:
- If K ≥ FATAL_THRESHOLD, add "SS4A" to eligible programs

At step 740, the system evaluates TAP/SRTS eligibility:
- If pedestrian_count > 0 OR bicycle_count > 0, add "TAP" and "SRTS" to eligible programs

At step 750, the system evaluates STBG eligibility:
- If EPDO ≥ EPDO_THRESHOLD, add "STBG" to eligible programs

At step 760, the system assigns the best match (first eligible program by priority order) and stores the complete list of matching programs.

### Embodiment 7: Before/After Statistical Analysis

Referring now to Figure 8, the before/after analysis module 800 evaluates treatment effectiveness.

At step 810, the user specifies:
- Treatment type (e.g., "Signal installation", "Turn lane addition")
- Treatment date (when construction was completed)
- Construction duration (months during which crashes should be excluded)
- Study period length (1, 3, or 5 years)

At step 820, the system calculates study periods:

```
before_start = treatment_date - study_years
before_end = treatment_date - 1 day
after_start = treatment_date + construction_months
after_end = after_start + study_years
```

At step 830, the system retrieves crash records and categorizes by period:
- Before period crashes
- Construction period crashes (excluded from analysis)
- After period crashes

At step 840, the system performs statistical analysis using the selected method:

**Naive Method**:
```
Effectiveness = ((Before_Count - After_Count) / Before_Count) × 100
```

**Empirical Bayes Method** (preferred):
```
Weight = 1 / (1 + (Before_Count × Variance / Mean²))
EB_Estimate = Weight × Reference_Mean + (1 - Weight) × Before_Count
Effectiveness = ((EB_Estimate - After_Count) / EB_Estimate) × 100
```

The Empirical Bayes method accounts for regression-to-mean bias, providing more accurate effectiveness estimates for locations selected due to high crash counts.

At step 850, the system generates a report suitable for HSIP documentation including:
- Crash counts by period
- Statistical methodology used
- Calculated effectiveness with confidence indicators
- Visualization of before/after trends

---

## CLAIMS

### Independent Claims

**Claim 1.** A computer-implemented traffic safety analysis system comprising:

(a) a processor;

(b) a memory storing instructions that, when executed by the processor, cause the system to:

(i) receive crash records from a transportation database, each record including a location identifier, a severity classification selected from fatal, serious injury, minor injury, possible injury, and property damage only, a collision type, and temporal data;

(ii) compute, for each unique location, an Equivalent Property Damage Only (EPDO) score by applying differential weight values to crash records according to severity classification;

(iii) compute, for each unique location, a composite priority score incorporating weighted fatal crash counts, weighted serious injury crash counts, weighted vulnerable road user incident counts, and a normalized EPDO component;

(iv) generate, for a selected location, a crash profile comprising severity distribution, collision type distribution, contributing factor prevalence, and vulnerable road user involvement;

(v) query a countermeasure database to retrieve safety interventions applicable to the crash profile;

(vi) compute, for each retrieved countermeasure, a relevance score based on multidimensional matching between the crash profile characteristics and the countermeasure target criteria;

(vii) present, via a user interface, ranked countermeasure recommendations with computed relevance scores and expected crash reduction estimates.

**Claim 2.** A computer-implemented method for automated traffic safety countermeasure recommendation comprising:

(a) receiving, at a computer system, crash records for a specified geographic location, each record including severity classification, collision type, and contributing factor data;

(b) generating a crash profile for the location by computing:
- severity distribution percentages across fatal, serious injury, minor injury, possible injury, and property damage only categories;
- collision type frequencies;
- contributing factor prevalence rates for alcohol involvement, speed involvement, distraction involvement, and restraint non-use;
- vulnerable road user involvement rates;

(c) querying a Crash Modification Factor database to retrieve countermeasures applicable to the location type;

(d) computing, for each retrieved countermeasure, a relevance score by:
- calculating a severity match score based on alignment between crash profile K+A percentage and countermeasure target severity;
- calculating a collision type match score based on overlap between crash types present and countermeasure target crash types;
- calculating a contributing factor match score based on prevalence of factors addressed by the countermeasure;
- combining match scores with configurable weights to produce a composite relevance score;

(e) computing, for each countermeasure, an expected annual crash reduction by:
- identifying crash records matching the countermeasure target crash types;
- dividing matched crash count by years of available data to compute annual rate;
- multiplying annual rate by the countermeasure's crash reduction factor percentage;

(f) presenting ranked countermeasure recommendations ordered by relevance score.

**Claim 3.** A computer-implemented method for automated traffic signal warrant analysis comprising:

(a) receiving, at a computer system, a selection of an intersection location;

(b) retrieving crash records associated with the intersection;

(c) classifying each crash record according to Manual on Uniform Traffic Control Devices (MUTCD) criteria by:
- identifying angle crashes based on collision type;
- identifying pedestrian crashes based on pedestrian involvement flag;
- identifying fatal and serious injury crashes based on severity classification;

(d) computing annual crash rates by dividing classified crash counts by the number of years of available data;

(e) evaluating MUTCD Warrant 7 thresholds by comparing computed annual rates against federal threshold values;

(f) generating a warrant analysis report indicating whether threshold criteria are satisfied.

### Dependent Claims

**Claim 4.** The system of claim 1, wherein the differential weight values for EPDO calculation comprise: 462 for fatal crashes, 62 for serious injury crashes, 12 for minor injury crashes, 5 for possible injury crashes, and 1 for property damage only crashes.

**Claim 5.** The system of claim 1, wherein the composite priority score is computed according to the formula: (K × 100) + (A × 50) + (VRU × 30) + (EPDO / 100), where K is fatal crash count, A is serious injury crash count, VRU is vulnerable road user incident count, and EPDO is the Equivalent Property Damage Only score.

**Claim 6.** The system of claim 1, further comprising an artificial intelligence module configured to:
- receive natural language queries regarding traffic safety;
- invoke structured database search tools based on query analysis;
- synthesize search results with crash profile data;
- generate natural language responses including countermeasure recommendations with explanatory reasoning.

**Claim 7.** The system of claim 6, wherein the artificial intelligence module supports function-calling to a CMF database search tool with parameters including crash types, road type, and severity focus.

**Claim 8.** The method of claim 2, wherein the relevance score computation further comprises adjusting for countermeasure statistical quality based on confidence interval width, wherein narrower confidence intervals result in higher relevance scores.

**Claim 9.** The method of claim 2, further comprising classifying each countermeasure into a cost tier based on implementation complexity, and presenting cost tier information alongside relevance scores.

**Claim 10.** The method of claim 3, wherein the MUTCD Warrant 7 thresholds for a four-leg intersection with one year of data comprise: five or more angle/pedestrian crashes annually, or three or more fatal/serious injury angle/pedestrian crashes annually.

**Claim 11.** The system of claim 1, further comprising a cross-tab state synchronization module configured to:
- maintain a selection state object storing a selected location identifier, associated crash records, and computed crash profile;
- propagate the selection state across multiple analysis tabs;
- enable navigation between analysis modes while preserving location context.

**Claim 12.** The system of claim 1, further comprising a grant matching module configured to:
- evaluate crash profile characteristics against federal grant program eligibility criteria;
- identify all eligible programs from a set including HSIP, SS4A, TAP, SRTS, and STBG;
- rank eligible programs by priority and present matching results.

**Claim 13.** The system of claim 1, further comprising a before/after analysis module configured to:
- receive a treatment date and construction duration;
- calculate before and after study periods excluding the construction period;
- retrieve and categorize crash records by study period;
- compute treatment effectiveness using Empirical Bayes statistical methods with regression-to-mean correction.

**Claim 14.** The method of claim 2, wherein the crash profile further comprises weather condition distribution and light condition distribution, and wherein the relevance score computation includes an environmental match component based on alignment between crash conditions and countermeasure applicability.

**Claim 15.** The system of claim 1, wherein the user interface comprises a geographic map display enabling polygon or circle selection of crash locations, and wherein crashes within the selected boundary are automatically captured and profiled.

---

## ABSTRACT

A computer-implemented traffic safety analysis system and method for automated countermeasure recommendation. The system receives crash records from transportation databases and computes location priority scores using a weighted severity algorithm incorporating fatal crash weights, serious injury weights, vulnerable road user incident weights, and normalized Equivalent Property Damage Only (EPDO) scores. For selected locations, the system generates multidimensional crash profiles including severity distributions, collision type frequencies, and contributing factor prevalence. The system queries a Crash Modification Factor (CMF) database and computes relevance scores for candidate countermeasures based on crash profile matching. An artificial intelligence module with function-calling capabilities receives natural language queries and generates synthesized safety recommendations. Additional modules provide automated MUTCD signal warrant analysis, federal grant program matching, and before/after statistical evaluation using Empirical Bayes methods. A cross-tab state synchronization engine maintains context awareness across multiple analysis modes, enabling seamless navigation with preserved selections.

---

## INVENTOR INFORMATION

**Full Legal Name**: ________________________________

**Residence (City, State, Country)**: ________________________________

**Mailing Address**: ________________________________

**Citizenship**: ________________________________

**Email Address**: ________________________________

**Phone Number**: ________________________________

---

## SIGNATURE

I hereby declare that all statements made herein of my own knowledge are true and that all statements made on information and belief are believed to be true; and further that these statements were made with the knowledge that willful false statements and the like so made are punishable by fine or imprisonment, or both, under Section 1001 of Title 18 of the United States Code and that such willful false statements may jeopardize the validity of the application or any patent issued thereon.

**Signature**: ________________________________

**Date**: ________________________________

**Printed Name**: ________________________________
