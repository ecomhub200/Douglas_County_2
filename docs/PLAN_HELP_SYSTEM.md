# CRASH LENS Help System - World-Class Implementation Plan

## Executive Summary

This plan outlines a comprehensive, multi-layered help system designed specifically for traffic engineers who may be new to crash analysis tools. The system will transform the Help button into a powerful learning and reference resource that guides users from their first click to expert-level analysis.

---

## Part 1: Understanding Our User

### Primary Persona: The New Traffic Engineer

**Who they are:**
- Recent engineering graduate or someone new to traffic safety analysis
- Has foundational knowledge of transportation engineering but limited crash data experience
- Needs to produce actionable safety recommendations for their agency
- Under pressure to justify safety improvements with data
- May need to apply for grants (HSIP, SS4A) to fund projects

**Their Pain Points:**
- Overwhelmed by data and terminology (EPDO, CMF, KABCO, K+A)
- Unsure which analysis approach fits their specific question
- Doesn't know what "good" analysis looks like
- Needs to present findings to non-technical stakeholders
- Time-pressured to deliver results

**What Success Looks Like:**
- Confidently navigate all 11 tabs with purpose
- Understand when to use each feature
- Produce professional reports that win grant funding
- Make data-driven safety recommendations

---

## Part 2: Help System Architecture

### Multi-Layer Help Philosophy

```
┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 1: INSTANT HELP                        │
│         Tooltips, inline hints, contextual micro-help           │
│                    (< 5 seconds to consume)                     │
├─────────────────────────────────────────────────────────────────┤
│                    LAYER 2: GUIDED HELP                         │
│      Interactive tutorials, workflow wizards, "How do I..."     │
│                    (1-5 minutes to complete)                    │
├─────────────────────────────────────────────────────────────────┤
│                    LAYER 3: COMPREHENSIVE HELP                  │
│    Full documentation, video walkthroughs, reference guides     │
│                    (Deep learning resource)                     │
├─────────────────────────────────────────────────────────────────┤
│                    LAYER 4: EXPERT RESOURCES                    │
│       MUTCD references, CMF methodology, grant writing tips     │
│                    (Professional development)                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 3: Help Modal Redesign

### 3.1 New Help Modal Structure

When user clicks the **Help** button, a professional modal opens with:

#### Header Section
- CRASH LENS logo/icon
- Search bar: "What do you need help with?"
- AI-powered search that understands natural language queries

#### Navigation Tabs (Horizontal)
```
[ 🚀 Quick Start ] [ 📖 User Guide ] [ 🎯 How Do I... ] [ 📚 Reference ] [ 🎓 Training ]
```

---

### 3.2 Tab 1: Quick Start (Default View)

**Purpose:** Get a new user productive in under 5 minutes

#### Section A: "Choose Your Path"
Interactive cards based on user's immediate goal:

```
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│  🔍 FIND DANGEROUS   │  │  💰 APPLY FOR A      │  │  📊 CREATE A         │
│     LOCATIONS        │  │     SAFETY GRANT     │  │     REPORT           │
│                      │  │                      │  │                      │
│  "Show me where      │  │  "I need to justify  │  │  "I need to present  │
│   crashes happen"    │  │   funding for a      │  │   crash data to      │
│                      │  │   safety project"    │  │   leadership"        │
│  [Start →]           │  │  [Start →]           │  │  [Start →]           │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘

┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│  🚶 ANALYZE PED/BIKE │  │  🔧 FIND SAFETY      │  │  🤖 USE AI           │
│     SAFETY           │  │     SOLUTIONS        │  │     ASSISTANT        │
│                      │  │                      │  │                      │
│  "Focus on           │  │  "What improvements  │  │  "Get AI-powered     │
│   vulnerable users"  │  │   actually work?"    │  │   recommendations"   │
│                      │  │                      │  │                      │
│  [Start →]           │  │  [Start →]           │  │  [Start →]           │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘
```

Each card launches a **Guided Workflow** (see Section 4).

#### Section B: "60-Second Overview" (Expandable)
- Animated GIF or short video showing the tool in action
- Key message: "CRASH LENS helps you turn crash data into safety improvements"

#### Section C: "Essential Concepts" (Collapsible Cards)

**Card 1: Severity Codes (KABCO)**
```
┌─────────────────────────────────────────────────────────────────┐
│  KABCO SEVERITY SCALE                                           │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  K  ████████████████  FATAL         Someone died                │
│  A  ████████████      SERIOUS       Hospitalized                │
│  B  ████████          MINOR         Visible injury              │
│  C  ████              POSSIBLE      Pain, no visible injury     │
│  O  ██                PDO           Property damage only        │
│                                                                 │
│  💡 TIP: Focus on K+A crashes - these drive grant funding       │
└─────────────────────────────────────────────────────────────────┘
```

**Card 2: EPDO (Why It Matters)**
```
┌─────────────────────────────────────────────────────────────────┐
│  EPDO: EQUIVALENT PROPERTY DAMAGE ONLY                          │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  A weighted score that prioritizes serious crashes:             │
│                                                                 │
│  1 Fatal (K)      = 462 PDO crashes                             │
│  1 Serious (A)    = 62 PDO crashes                              │
│  1 Minor (B)      = 12 PDO crashes                              │
│  1 Possible (C)   = 5 PDO crashes                               │
│  1 PDO (O)        = 1 PDO crash                                 │
│                                                                 │
│  📍 EXAMPLE: A location with 2 fatal crashes (EPDO = 924)       │
│     is more critical than one with 50 PDO crashes (EPDO = 50)   │
│                                                                 │
│  💡 TIP: Use EPDO to prioritize - it reveals true danger        │
└─────────────────────────────────────────────────────────────────┘
```

**Card 3: CMF (Crash Modification Factor)**
```
┌─────────────────────────────────────────────────────────────────┐
│  CMF: CRASH MODIFICATION FACTOR                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  A CMF tells you how effective a safety treatment is:           │
│                                                                 │
│  CMF = 0.70  →  30% REDUCTION in crashes ✓ Good                 │
│  CMF = 1.00  →  NO CHANGE                                       │
│  CMF = 1.20  →  20% INCREASE in crashes ✗ Bad                   │
│                                                                 │
│  ⭐ STAR RATINGS (1-5 stars):                                   │
│  More stars = more reliable research behind the number          │
│  Aim for 3+ stars for grant applications                        │
│                                                                 │
│  💡 TIP: Lower CMF = Better. A CMF of 0.50 is excellent!        │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3.3 Tab 2: User Guide (Tab-by-Tab Documentation)

**Purpose:** Comprehensive documentation for each feature

#### Structure: Accordion Menu by Tab

```
▼ Dashboard
  ├── Overview: What this tab shows
  ├── Reading the KPI cards
  ├── Understanding the charts
  ├── Using filters effectively
  └── Common questions

▶ Map
▶ Hotspots
▶ Analysis
▶ Intersection
▶ Pedestrian/Bicycle
▶ Countermeasures
▶ AI Assistant
▶ Grants
▶ Reports
```

#### Example: Dashboard Guide Content

```markdown
## Dashboard Tab

### What It Shows
The Dashboard is your command center - a high-level overview of ALL crash
data in your selected date range. Start here to understand the big picture.

### The KPI Cards (Top Row)
┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐
│ TOTAL   │ FATAL   │ SERIOUS │ OTHER   │  PDO    │  EPDO   │  PED    │  BIKE   │
│ CRASHES │  (K)    │  (A)    │ (B+C)   │  (O)    │ SCORE   │ CRASHES │ CRASHES │
└─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘

- **Total Crashes**: Raw count of all crashes in period
- **Fatal (K)**: Deaths - your most critical metric
- **Serious (A)**: Hospital admissions
- **Other Injury (B+C)**: Less severe injuries combined
- **PDO**: Property damage only (no injuries)
- **EPDO**: Weighted severity score (see Reference)
- **Pedestrian**: Crashes involving people on foot
- **Bicycle**: Crashes involving cyclists

### Quick Actions
- Click any KPI card to filter the charts below
- Use date presets (1Y, 3Y, 5Y) for quick time comparisons
- Export any chart by clicking the download icon

### Pro Tips
💡 Always check pedestrian/bicycle numbers separately - they're often
   underrepresented in total counts but critical for grants

💡 Compare EPDO across years to see if crashes are getting more or less severe

💡 Use 5-year data for reliable trends; 1-year for recent patterns
```

---

### 3.4 Tab 3: "How Do I..." (Task-Based Help)

**Purpose:** Answer specific user questions with step-by-step guidance

#### Searchable FAQ with Visual Guides

**Categories:**
```
📍 Finding Locations
   • How do I find the most dangerous intersections?
   • How do I analyze a specific road corridor?
   • How do I identify pedestrian hotspots?

📊 Understanding Data
   • How do I read the severity breakdown?
   • How do I compare years?
   • What does the EPDO score mean?

🔧 Getting Recommendations
   • How do I find countermeasures for a location?
   • How do I use the AI assistant?
   • How do I check if a location needs a traffic signal?

💰 Grant Applications
   • How do I prepare data for an HSIP application?
   • How do I find open grant opportunities?
   • How do I track my grant applications?

📄 Creating Reports
   • How do I generate a professional PDF report?
   • How do I customize report content?
   • How do I export data to Excel?

🗺️ Using the Map
   • How do I draw a selection area?
   • How do I switch between heatmap and clusters?
   • How do I find a specific road on the map?
```

#### Example: Step-by-Step Guide

```
┌─────────────────────────────────────────────────────────────────┐
│  HOW DO I: Find the most dangerous intersections?               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STEP 1: Go to the Hotspots Tab                                 │
│  ────────────────────────────                                   │
│  Click "Hotspots" in the navigation bar                         │
│  [Screenshot showing tab location]                              │
│                                                                 │
│  STEP 2: Configure Your Analysis                                │
│  ────────────────────────────────                               │
│  • Set "Sort by" to: EPDO Score (recommended)                   │
│  • Set "Group by" to: Intersection Node                         │
│  • Set "Min crashes" to: 5 (filters noise)                      │
│  • Set "Show top" to: 20                                        │
│  [Screenshot showing settings]                                  │
│                                                                 │
│  STEP 3: Review Results                                         │
│  ──────────────────────                                         │
│  The table shows intersections ranked by danger                 │
│  • Higher EPDO = More severe crashes                            │
│  • Check K+A column for fatal/serious crashes                   │
│  [Screenshot showing results table]                             │
│                                                                 │
│  STEP 4: Take Action                                            │
│  ────────────────────                                           │
│  • Click "View on Map" to see location                          │
│  • Click "Get Countermeasures" for solutions                    │
│  • Click "Generate Report" for documentation                    │
│                                                                 │
│  💡 PRO TIP: For grant applications, focus on locations with    │
│     high K+A counts - these receive priority funding            │
│                                                                 │
│  [▶ Watch Video Tutorial (2 min)]                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3.5 Tab 4: Reference (Glossary & Technical Info)

**Purpose:** Definitive reference for all terminology and methodology

#### Sections:

**A. Complete Glossary (A-Z)**
```
AADT (Annual Average Daily Traffic)
  The total volume of vehicle traffic on a highway or road for a year,
  divided by 365 days. Used to normalize crash rates.

CMF (Crash Modification Factor)
  A multiplicative factor used to compute the expected number of crashes
  after implementing a countermeasure. CMF < 1.0 indicates a reduction.

  Formula: Expected Crashes After = Crashes Before × CMF
  Example: 100 crashes × 0.75 CMF = 75 expected crashes (25% reduction)

CMF Clearinghouse
  The FHWA's online database of crash modification factors, available at
  cmfclearinghouse.org. CRASH LENS queries this database for recommendations.

...continues alphabetically...
```

**B. Severity Weighting Methodology**
- EPDO calculation formula and source
- Why these weights were chosen
- How to interpret weighted scores

**C. Data Source Information**
- Where Virginia crash data comes from
- Data update frequency
- Known limitations and caveats

**D. MUTCD Quick Reference**
- Signal warrant criteria (4C.08)
- Crosswalk installation guidance
- Sign placement standards
- Link to full Virginia MUTCD

**E. Grant Program Reference**
```
┌─────────────────────────────────────────────────────────────────┐
│  HIGHWAY SAFETY IMPROVEMENT PROGRAM (HSIP)                      │
├─────────────────────────────────────────────────────────────────┤
│  Funding: Federal (90%) + State/Local Match (10%)               │
│  Focus: Locations with documented crash history                 │
│  Key Requirement: Must show crash reduction potential           │
│  Typical Projects: Signals, signs, road geometry, lighting      │
│  Application: Through VDOT                                      │
│  Cycle: Annual                                                  │
│  💡 Use CRASH LENS Hotspots + Countermeasures tabs to build case│
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  SAFE STREETS AND ROADS FOR ALL (SS4A)                          │
├─────────────────────────────────────────────────────────────────┤
│  Funding: Federal (up to 80%)                                   │
│  Focus: Vision Zero / eliminating fatalities                    │
│  Key Requirement: Comprehensive safety action plan              │
│  Typical Projects: Complete streets, pedestrian infrastructure  │
│  Application: Direct to USDOT                                   │
│  Cycle: Annual (check grants.gov)                               │
│  💡 Use CRASH LENS Reports tab to generate supporting analysis  │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3.6 Tab 5: Training (Learning Paths)

**Purpose:** Structured learning for skill development

#### Learning Paths:

**Path 1: CRASH LENS Fundamentals (Beginner)**
```
Duration: 30 minutes
Modules:
  ☐ Module 1: Navigating the Interface (5 min)
  ☐ Module 2: Understanding Crash Severity (5 min)
  ☐ Module 3: Reading the Dashboard (5 min)
  ☐ Module 4: Finding Hotspots (5 min)
  ☐ Module 5: Using the Map (5 min)
  ☐ Module 6: Generating Your First Report (5 min)

  [Start Learning →]
```

**Path 2: Data-Driven Safety Analysis (Intermediate)**
```
Duration: 45 minutes
Prerequisites: Fundamentals
Modules:
  ☐ Module 1: Trend Analysis Techniques
  ☐ Module 2: Identifying Contributing Factors
  ☐ Module 3: Pedestrian/Bicycle Deep Dive
  ☐ Module 4: Intersection Analysis Methods
  ☐ Module 5: Using CMF Data Effectively

  [Start Learning →]
```

**Path 3: Grant Application Mastery (Advanced)**
```
Duration: 60 minutes
Prerequisites: Fundamentals + Data Analysis
Modules:
  ☐ Module 1: What Grant Reviewers Look For
  ☐ Module 2: Building a Compelling Safety Case
  ☐ Module 3: Using CRASH LENS for HSIP Applications
  ☐ Module 4: SS4A Application Strategies
  ☐ Module 5: Tracking and Managing Applications

  [Start Learning →]
```

#### Interactive Tutorials (Guided Walkthroughs)
```
🎯 Tutorial: "Find Your First Hotspot"
   Hands-on guide that highlights UI elements as you click through

🎯 Tutorial: "Generate a Grant-Ready Report"
   Step-by-step with real data

🎯 Tutorial: "Use AI to Analyze a Corridor"
   Setting up API and asking effective questions
```

---

## Part 4: Guided Workflows (Wizards)

### 4.1 Workflow: "Find Dangerous Locations"

When user clicks this from Quick Start:

```
┌─────────────────────────────────────────────────────────────────┐
│  WORKFLOW: FIND DANGEROUS LOCATIONS                    Step 1/4 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  What type of locations are you investigating?                  │
│                                                                 │
│  ○ Intersections only                                           │
│  ○ Road segments (corridors)                                    │
│  ○ Both intersections and segments                              │
│  ○ Pedestrian/Bicycle specific locations                        │
│                                                                 │
│                                      [Back]  [Next →]           │
└─────────────────────────────────────────────────────────────────┘

                              ↓

┌─────────────────────────────────────────────────────────────────┐
│  WORKFLOW: FIND DANGEROUS LOCATIONS                    Step 2/4 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  What time period should we analyze?                            │
│                                                                 │
│  ○ Last 1 year (most recent patterns)                           │
│  ○ Last 3 years (recommended for most analysis)                 │
│  ● Last 5 years (best for grant applications)                   │
│  ○ Custom date range                                            │
│                                                                 │
│  💡 Grant applications typically require 3-5 years of data      │
│                                                                 │
│                                      [Back]  [Next →]           │
└─────────────────────────────────────────────────────────────────┘

                              ↓

┌─────────────────────────────────────────────────────────────────┐
│  WORKFLOW: FIND DANGEROUS LOCATIONS                    Step 3/4 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  How should we rank the locations?                              │
│                                                                 │
│  ● EPDO Score (Recommended)                                     │
│    Prioritizes locations with more severe crashes               │
│                                                                 │
│  ○ Total Crash Count                                            │
│    Simple count, may miss severity                              │
│                                                                 │
│  ○ K+A Crashes (Fatal + Serious)                                │
│    Focus on most severe outcomes only                           │
│                                                                 │
│  ○ Crash Rate                                                   │
│    Crashes per year (normalizes for time)                       │
│                                                                 │
│                                      [Back]  [Next →]           │
└─────────────────────────────────────────────────────────────────┘

                              ↓

┌─────────────────────────────────────────────────────────────────┐
│  WORKFLOW: FIND DANGEROUS LOCATIONS                    Step 4/4 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ✅ Ready to analyze!                                           │
│                                                                 │
│  Your settings:                                                 │
│  • Location type: Both intersections and segments               │
│  • Time period: Last 5 years                                    │
│  • Ranking: EPDO Score                                          │
│                                                                 │
│  We'll take you to the Hotspots tab with these filters applied. │
│                                                                 │
│  What would you like to do next?                                │
│                                                                 │
│  [📍 Go to Hotspots]  [🗺️ View on Map]  [📊 See Dashboard First]│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 4.2 Workflow: "Apply for a Safety Grant"

```
Step 1: Select Grant Type
  → HSIP, SS4A, Other VA grants

Step 2: Identify Location(s)
  → Guide to Hotspots tab or manual selection

Step 3: Document the Problem
  → Generate crash analysis with key metrics

Step 4: Find Solutions
  → Navigate to Countermeasures tab

Step 5: Build Your Case
  → Generate grant-ready report

Step 6: Track Application
  → Add to Grant Tracker with deadline
```

---

## Part 5: Contextual Help (In-App)

### 5.1 Smart Tooltips

Every complex element should have an info icon (ℹ️) that reveals a tooltip:

```
EPDO Score ℹ️
           ┌──────────────────────────────────────┐
           │ Equivalent Property Damage Only      │
           │                                      │
           │ A weighted score where severe        │
           │ crashes count more. Higher = worse.  │
           │                                      │
           │ [Learn more →]                       │
           └──────────────────────────────────────┘
```

### 5.2 First-Time Tab Hints

When a user visits a tab for the first time, show a brief orientation:

```
┌─────────────────────────────────────────────────────────────────┐
│  👋 FIRST TIME ON HOTSPOTS?                              [×]    │
│                                                                 │
│  This tab helps you find locations that need safety attention.  │
│                                                                 │
│  Quick tip: Sort by "EPDO Score" to see the most dangerous      │
│  locations first, not just the ones with the most crashes.      │
│                                                                 │
│  [Show me how]                    [Got it, don't show again]    │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 Empty State Guidance

When a section shows no data, provide helpful context:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                      📭 No Results Found                        │
│                                                                 │
│  Your current filters are too restrictive.                      │
│                                                                 │
│  Try:                                                           │
│  • Expanding your date range                                    │
│  • Including more severity levels                               │
│  • Selecting a different route                                  │
│                                                                 │
│  [Reset Filters]                                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.4 Action Confirmation Help

Before major actions, provide context:

```
┌─────────────────────────────────────────────────────────────────┐
│  📄 GENERATE REPORT                                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  You're about to generate a Corridor Analysis Report for:       │
│                                                                 │
│  Route: Broad Street                                            │
│  Period: Jan 2020 - Dec 2024 (5 years)                          │
│  Crashes included: 247                                          │
│                                                                 │
│  This report is suitable for:                                   │
│  ✓ HSIP grant applications                                      │
│  ✓ Internal safety presentations                                │
│  ✓ Public meeting documentation                                 │
│                                                                 │
│  [Cancel]                              [Generate Report]        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 6: Help Search & AI Integration

### 6.1 Intelligent Search

The help search bar should understand natural language:

```
User types: "how do i find bad intersections"

Results:
┌─────────────────────────────────────────────────────────────────┐
│  🔍 Results for "how do i find bad intersections"               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📌 Best Match:                                                 │
│  How do I find the most dangerous intersections?                │
│  Step-by-step guide using the Hotspots tab                      │
│  [View Guide →]                                                 │
│                                                                 │
│  📚 Related:                                                    │
│  • Intersection Tab User Guide                                  │
│  • Understanding EPDO scores                                    │
│  • Intersection analysis for grant applications                 │
│                                                                 │
│  🎯 Quick Action:                                               │
│  [Go to Hotspots Tab with intersection filter]                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 AI Help Assistant (Optional Enhancement)

If API key is configured, offer AI-powered help:

```
┌─────────────────────────────────────────────────────────────────┐
│  🤖 ASK AI ASSISTANT                                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Can't find what you need? Ask our AI assistant:                │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ How do I analyze rear-end crashes at signalized         │    │
│  │ intersections?                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                         [Ask]   │
│                                                                 │
│  Example questions:                                             │
│  • "What CMF should I use for adding a left turn lane?"         │
│  • "How do I show crash reduction for a grant application?"     │
│  • "What's the best way to analyze school zone safety?"         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 7: Accessibility & Usability

### 7.1 Keyboard Navigation
- All help content navigable via Tab key
- Escape closes modals
- Arrow keys navigate between sections

### 7.2 Screen Reader Support
- All images have alt text
- Proper heading hierarchy
- ARIA labels on interactive elements

### 7.3 Print-Friendly
- "Print this guide" option for offline reference
- Clean formatting without UI chrome

### 7.4 Mobile Responsive
- Help modal adapts to mobile screens
- Touch-friendly navigation
- Swipe between sections

---

## Part 8: Content Maintenance Plan

### 8.1 Content Inventory

| Section | Owner | Update Frequency |
|---------|-------|------------------|
| Quick Start | Product Team | With each release |
| User Guide | Documentation Team | Monthly review |
| How Do I... | Support Team | Based on user questions |
| Reference | Technical Team | As standards change |
| Training | Training Team | Quarterly |

### 8.2 Feedback Loop

```
┌─────────────────────────────────────────────────────────────────┐
│  Was this helpful?                                              │
│                                                                 │
│  [👍 Yes]  [👎 No]  [💬 Suggest improvement]                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

Collect feedback to continuously improve help content.

### 8.3 Analytics Tracking

Track:
- Most viewed help articles
- Most searched terms
- Workflow completion rates
- Time spent in help
- Exit points (where users leave help)

---

## Part 9: Implementation Phases

### Phase 1: Foundation (MVP)
**Scope:**
- Redesigned help modal with tabbed navigation
- Quick Start with "Choose Your Path" cards
- Essential Concepts cards (KABCO, EPDO, CMF)
- Basic User Guide for each tab
- Improved glossary

**Deliverables:**
- Help modal component
- Content for all 11 tabs
- Basic search functionality

### Phase 2: Guided Experience
**Scope:**
- Interactive workflows/wizards
- "How Do I..." task-based guides
- First-time user hints
- Smart tooltips on key elements

**Deliverables:**
- Workflow wizard component
- 6 complete guided workflows
- Tooltip system implementation

### Phase 3: Learning & Training
**Scope:**
- Training module framework
- Video tutorial integration
- Learning path tracking
- Certificate of completion (optional)

**Deliverables:**
- Training tab implementation
- 3 learning paths with modules
- Progress tracking system

### Phase 4: Intelligence
**Scope:**
- AI-powered search
- Natural language query understanding
- Contextual recommendations
- Personalized help based on usage

**Deliverables:**
- AI search integration
- Usage analytics dashboard
- Personalization engine

---

## Part 10: Success Metrics

### User Success Metrics
- **Time to First Analysis**: How quickly can a new user produce their first meaningful output?
- **Help Engagement**: % of users who use help features
- **Workflow Completion**: % of users who complete guided workflows
- **Self-Service Rate**: % of questions answered without external support

### Business Metrics
- **Onboarding Time**: Reduction in time to train new users
- **Support Tickets**: Reduction in basic "how do I" questions
- **Feature Adoption**: Increase in usage of advanced features
- **User Satisfaction**: NPS/CSAT scores for the tool

### Target Improvements
| Metric | Current | Target |
|--------|---------|--------|
| Time to first report | Unknown | < 10 minutes |
| Help article views | Low | 50%+ of users |
| Workflow completions | N/A | 30%+ of new users |
| Support questions | Baseline | -40% |

---

## Appendix A: Sample Content - Dashboard User Guide

```markdown
# Dashboard Tab

## Purpose
The Dashboard provides a high-level overview of crash data in your jurisdiction.
It's designed to answer the question: "What does our overall crash picture look like?"

## When to Use This Tab
- Starting a new analysis session
- Getting oriented with the data
- Presenting high-level statistics to leadership
- Comparing time periods

## Key Components

### KPI Cards (Top Section)
Eight cards showing aggregate metrics:

| Card | What It Shows | Why It Matters |
|------|---------------|----------------|
| Total Crashes | Count of all crashes | Overall volume |
| Fatal (K) | Crashes with fatalities | Most critical metric |
| Serious (A) | Hospitalization required | Grant priority |
| Other Injury | Minor + possible injuries | Injury burden |
| PDO | Property damage only | Majority of crashes |
| EPDO | Weighted severity score | True danger level |
| Pedestrian | Crashes involving pedestrians | VRU focus |
| Bicycle | Crashes involving bicyclists | VRU focus |

### Charts

**Severity Distribution (Donut)**
Shows proportion of crashes by severity level. A healthy distribution
has mostly PDO with small K+A slice. Growing K+A indicates worsening safety.

**Crashes by Year (Bar)**
Year-over-year trend. Look for:
- Sustained increases (concerning)
- COVID-19 dip in 2020 (expected)
- Recent trends (most actionable)

[Additional chart explanations...]

## Common Tasks

### Compare Two Time Periods
1. Note the current statistics
2. Change date range to comparison period
3. Compare the KPI values

### Focus on Severe Crashes
1. Uncheck B, C, and O severity boxes
2. View only K and A crashes
3. All charts update automatically

### Export Data
1. Click the export icon on any chart
2. Choose PNG (image) or CSV (data)
3. Use in reports or presentations

## Pro Tips
💡 The EPDO card is more important than Total Crashes - it reveals true danger

💡 Check Pedestrian and Bicycle numbers even if they're small - they're
   disproportionately severe

💡 Use 5-year data for trends, 1-year for recent patterns

## Frequently Asked Questions

**Q: Why don't the numbers match my agency's reports exactly?**
A: Data timing varies. CRASH LENS updates quarterly from Virginia DMV/VDOT.
   Recent crashes may not yet be in the system.

**Q: What if I see 0 crashes?**
A: Check your filters. You may have severity types unchecked or a date range
   with no data.

**Q: Can I see only my jurisdiction?**
A: Yes, use the Route filter to select only your roads.
```

---

## Appendix B: Workflow Script - Grant Application

```
WORKFLOW: APPLY FOR A SAFETY GRANT
Total Steps: 6
Estimated Time: 15-20 minutes

─────────────────────────────────────────────────────────────────

STEP 1: SELECT GRANT PROGRAM
─────────────────────────────

"What type of safety grant are you applying for?"

○ HSIP (Highway Safety Improvement Program)
  → Best for: Infrastructure improvements at documented crash locations
  → Funding: 90% federal / 10% local match

○ SS4A (Safe Streets and Roads for All)
  → Best for: Comprehensive safety plans, pedestrian/bike projects
  → Funding: Up to 80% federal

○ Virginia DMV Safety Grants
  → Best for: Behavioral programs, enforcement, education
  → Funding: Varies by program

○ Other / Not Sure
  → We'll help you explore options

[Selection determines which guidance is shown in later steps]

─────────────────────────────────────────────────────────────────

STEP 2: IDENTIFY YOUR LOCATION(S)
─────────────────────────────────

"Have you already identified the location(s) for your project?"

○ Yes, I know the specific location(s)
  → [Text input for road name or intersection]
  → We'll pull crash data for that location

○ No, I need help finding high-priority locations
  → We'll take you through the Hotspots analysis
  → [Configure: Sort by EPDO, Time period, Min crashes]
  → [Show top 20 locations ranked]
  → [Let user select 1 or more]

○ I want to analyze an area (multiple roads)
  → We'll use the Map selection tool
  → [Guide to draw polygon or circle]
  → [Calculate combined statistics]

─────────────────────────────────────────────────────────────────

STEP 3: DOCUMENT THE PROBLEM
────────────────────────────

"Let's build your safety case with data."

For your selected location(s), we've found:

┌─────────────────────────────────────────────────────────────────┐
│  CRASH SUMMARY: [Location Name]                                 │
│  Period: [Date Range]                                           │
├─────────────────────────────────────────────────────────────────┤
│  Total Crashes: 47                                              │
│  Fatal (K): 2                                                   │
│  Serious Injury (A): 8                                          │
│  K+A Combined: 10 (21% of crashes)                              │
│  EPDO Score: 1,532                                              │
│  Pedestrian Involved: 4                                         │
│  Bicycle Involved: 1                                            │
├─────────────────────────────────────────────────────────────────┤
│  TOP COLLISION TYPES:                                           │
│  1. Rear End (38%)                                              │
│  2. Angle (28%)                                                 │
│  3. Sideswipe (15%)                                             │
├─────────────────────────────────────────────────────────────────┤
│  CONTRIBUTING FACTORS:                                          │
│  • 65% occurred during peak hours                               │
│  • 40% involved speed as factor                                 │
│  • 25% occurred in wet conditions                               │
└─────────────────────────────────────────────────────────────────┘

💡 GRANT TIP: Your location has 10 K+A crashes over 5 years.
   HSIP typically requires demonstrated crash history. This location
   meets typical thresholds.

[Export this summary]  [Add to Report]  [Continue →]

─────────────────────────────────────────────────────────────────

STEP 4: FIND COUNTERMEASURES
────────────────────────────

"What safety improvements could reduce crashes here?"

Based on your location type and crash patterns, here are
evidence-based countermeasures from the FHWA CMF Clearinghouse:

┌─────────────────────────────────────────────────────────────────┐
│  RECOMMENDED COUNTERMEASURES                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ⭐⭐⭐⭐⭐ Install Roundabout (replacing signal)                │
│  CMF: 0.52 → 48% crash reduction                                │
│  Cost: $$$$ | Addresses: Angle, rear-end crashes                │
│  [View Details] [Add to Report]                                 │
│                                                                 │
│  ⭐⭐⭐⭐ Add Left Turn Phase                                    │
│  CMF: 0.73 → 27% crash reduction                                │
│  Cost: $$ | Addresses: Angle crashes                            │
│  [View Details] [Add to Report]                                 │
│                                                                 │
│  ⭐⭐⭐⭐ Install Backplates with Retroreflective Borders        │
│  CMF: 0.85 → 15% crash reduction                                │
│  Cost: $ | Addresses: Rear-end, angle crashes                   │
│  [View Details] [Add to Report]                                 │
│                                                                 │
│  [Show More Countermeasures...]                                 │
│  [Get AI Recommendations]                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

💡 GRANT TIP: Select countermeasures with 3+ star ratings.
   Higher ratings mean stronger evidence, which strengthens your application.

─────────────────────────────────────────────────────────────────

STEP 5: GENERATE YOUR REPORT
────────────────────────────

"Let's create documentation for your application."

Select report type:

○ HSIP Location Report
  → Includes: Crash history, severity analysis, collision types,
    contributing factors, recommended countermeasures, cost-benefit estimate

○ SS4A Supporting Analysis
  → Includes: Vision Zero framing, equity considerations,
    vulnerable road user focus, community impact

○ Custom Grant Report
  → Select which sections to include

Report Options:
☑ Include crash location map
☑ Include trend charts
☑ Include countermeasure recommendations
☑ Include cost-effectiveness analysis
☐ Include raw data appendix

Author: [Your Name]
Agency: [Your Agency]

[Preview Report]  [Generate PDF]

─────────────────────────────────────────────────────────────────

STEP 6: TRACK YOUR APPLICATION
──────────────────────────────

"Would you like to track this grant application?"

Adding to your Grant Tracker helps you:
• Remember submission deadlines
• Track application status
• Document outcomes for future applications

┌─────────────────────────────────────────────────────────────────┐
│  ADD TO GRANT TRACKER                                           │
├─────────────────────────────────────────────────────────────────┤
│  Grant Program: HSIP FY2025                                     │
│  Project: [Location Name] Safety Improvements                   │
│  Amount Requested: $___________                                 │
│  Deadline: [Date Picker]                                        │
│  Status: ○ Draft  ○ Submitted  ○ In Review                      │
│  Notes: [Text area]                                             │
└─────────────────────────────────────────────────────────────────┘

[Skip]  [Add to Tracker]

─────────────────────────────────────────────────────────────────

WORKFLOW COMPLETE! 🎉

You've successfully:
✓ Identified a high-priority location
✓ Documented the crash problem with data
✓ Found evidence-based countermeasures
✓ Generated a professional report
✓ Added the application to your tracker

NEXT STEPS:
• Review and refine your report
• Submit application before deadline
• Check back to update application status

[Go to Grant Tracker]  [Start New Analysis]  [Return to Dashboard]
```

---

## Appendix C: Glossary Terms (Complete List)

**A**
- AADT (Annual Average Daily Traffic)
- Angle Crash
- Area Type (Urban/Suburban/Rural)

**B**
- B Injury (Minor/Visible Injury)
- Bicycle Crash
- Backplate

**C**
- C Injury (Possible Injury)
- CMF (Crash Modification Factor)
- CMF Clearinghouse
- Collision Type
- Corridor
- Crash Rate
- Crosswalk

**D**
- Document Number
- Divided Highway

**E**
- EPDO (Equivalent Property Damage Only)
- Equity Analysis

**F**
- Fatal Crash (K)
- FHWA (Federal Highway Administration)
- First Harmful Event
- Functional Class

**G**
- Guardrail

**H**
- Heatmap
- Hotspot
- HSIP (Highway Safety Improvement Program)
- HSM (Highway Safety Manual)

**I**
- Impaired Driving
- Intersection
- Intersection Geometry

**K**
- K Injury (Fatal)
- K+A (Fatal + Serious combined)
- KABCO Scale

**L**
- Left Turn Phase
- Light Condition

**M**
- Milepost (MP)
- MUTCD (Manual on Uniform Traffic Control Devices)

**N**
- Node (Intersection identifier)
- Number of Lanes

**O**
- O (Property Damage Only)

**P**
- PDO (Property Damage Only)
- Pedestrian Crash
- Pedestrian Crossing Evaluation

**R**
- Rear End Crash
- Road Departure
- Road Segment
- Roundabout
- Route

**S**
- Serious Injury (A)
- Severity
- Sideswipe
- Signal Warrant
- Speed Related
- SS4A (Safe Streets and Roads for All)
- Star Rating (CMF quality)

**T**
- Traffic Control Type
- Trend Analysis
- TWLTL (Two-Way Left Turn Lane)

**U**
- Undivided Highway
- Unrestrained

**V**
- VDOT (Virginia Department of Transportation)
- Vision Zero
- VRU (Vulnerable Road User)

**W**
- Weather Condition
- Work Zone

**Y**
- Year-over-Year (YoY) Change
- Young Driver (15-20)

---

*End of Plan Document*
