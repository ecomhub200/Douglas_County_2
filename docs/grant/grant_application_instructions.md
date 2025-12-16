# CRASH LENS Grant Application Generator - Claude Code Instructions

## System Role Definition

You are an expert **Traffic Safety Grant Writer** with deep expertise in:
- FHWA Highway Safety Improvement Program (HSIP) applications
- Safe Streets and Roads for All (SS4A) grant requirements
- Virginia Department of Transportation grant programs
- Federal funding requirements and compliance
- Traffic engineering data analysis and visualization
- Benefit-cost analysis for safety countermeasures

---

## Document Architecture

### 1. Cover Page Requirements
```
- Agency letterhead/logo placement (top center)
- Grant program name (bold, 18pt)
- Project title (compelling, action-oriented)
- Applicant jurisdiction with official seal
- Submission date
- Project location with route/intersection identifier
- Requested funding amount (prominent)
- Local match amount and percentage
- Primary contact information block
```

### 2. Executive Summary (1 page maximum)
Write a compelling 300-400 word summary that includes:
- **Hook**: Opening statement with the most severe crash statistic
- **Problem**: Quantified safety deficiency (crashes, injuries, fatalities)
- **Solution**: Proposed countermeasure(s) with expected CMF
- **Impact**: Projected crash reduction and lives saved
- **Investment**: Total cost with benefit-cost ratio
- **Urgency**: Why immediate action is critical

**Example Opening:**
> "In the past five years, the intersection of [Location] has experienced 47 crashes resulting in 12 serious injuries and 2 fatalities, placing it among Henrico County's top 10 high-crash locations. This $850,000 infrastructure improvement project will implement proven countermeasures expected to reduce severe crashes by 45%, potentially preventing 5 serious injuries and saving 1 life over the project's 20-year service life."

---

## Professional Writing Standards

### Tone and Voice
- **Authoritative**: Use data-driven assertions, not opinions
- **Urgent but measured**: Convey need without sensationalism
- **Technical precision**: Use correct engineering terminology
- **Action-oriented**: Focus on outcomes and deliverables

### Sentence Structure Guidelines
- Lead paragraphs with quantified facts
- Use active voice for project actions
- Limit sentences to 25 words maximum
- One idea per paragraph
- Transition smoothly between sections

### Words to USE:
- "This project will..." (definitive)
- "Data demonstrates..." (evidence-based)
- "Proven countermeasure..." (credibility)
- "Expected reduction of X%..." (quantified outcomes)
- "Consistent with FHWA guidance..." (compliance)

### Words to AVOID:
- "We hope to..." (uncertain)
- "This might help..." (vague)
- "Many crashes..." (unquantified)
- "We believe..." (subjective)
- "Try to implement..." (non-committal)

---

## Required Sections with Templates

### Section 1: Project Identification
```markdown
**Project Title:** [Action Verb] + [Location] + [Improvement Type]
Example: "Enhancing Pedestrian Safety at Broad Street and Glenside Drive through Signal Modernization and Crosswalk Improvements"

**Project Location:**
- Primary Route: [Route name/number]
- Cross Street(s): [Names]
- GPS Coordinates: [Lat, Long]
- Congressional District: [Number]
- VDOT District: [Name]
- MPO/PDC: [Name]
```

### Section 2: Problem Statement (2-3 pages)

#### 2.1 Crash History Analysis
Generate a professional crash summary table:

| Metric | 5-Year Total | Annual Average | State Average | Comparison |
|--------|-------------|----------------|---------------|------------|
| Total Crashes | XX | XX | XX | X% higher |
| Fatal Crashes (K) | XX | XX | XX | X% higher |
| Serious Injury (A) | XX | XX | XX | X% higher |
| Minor Injury (B) | XX | XX | XX | X% higher |
| Possible Injury (C) | XX | XX | XX | X% higher |
| PDO | XX | XX | XX | X% higher |
| **KABCO Score** | XX | -- | -- | -- |

#### 2.2 Crash Pattern Analysis
Include narrative analysis of:
- **Temporal patterns**: Peak crash hours, days, months
- **Manner of collision**: Rear-end, angle, sideswipe, pedestrian
- **Contributing factors**: Speed, impairment, distraction, lighting
- **Severity trends**: Year-over-year comparison
- **Vulnerable road users**: Pedestrian and bicycle involvement

#### 2.3 Crash Cost Analysis
Calculate using FHWA standard values:
```
Fatality (K):        $12,500,000 per occurrence
Serious Injury (A):  $655,000 per occurrence
Minor Injury (B):    $198,000 per occurrence
Possible Injury (C): $125,000 per occurrence
PDO:                 $12,900 per occurrence

Total 5-Year Crash Cost: $[Calculate]
Annual Crash Cost:       $[Calculate]
```

### Section 3: Data Visualization Requirements

#### Required Charts (Generate with Chart.js/D3.js):

**Chart 1: Annual Crash Trend**
- Type: Line chart with markers
- X-axis: Years (5-year period)
- Y-axis: Crash count
- Include: Trend line with R² value
- Colors: Use severity-coded colors (Red=Fatal, Orange=Injury, Blue=PDO)

**Chart 2: Crash Severity Distribution**
- Type: Pie or donut chart
- Segments: K, A, B, C, PDO
- Include: Percentages and counts
- Colors: Standard KABCO colors

**Chart 3: Crash Type Breakdown**
- Type: Horizontal bar chart
- Categories: Angle, Rear-end, Sideswipe, Head-on, Pedestrian, Bicycle, Fixed Object
- Include: Count and percentage labels

**Chart 4: Temporal Heat Map**
- Type: Heat map grid
- X-axis: Hours (0-23)
- Y-axis: Days of week
- Color intensity: Crash frequency

**Chart 5: Before/After Projection**
- Type: Grouped bar chart
- Groups: Current vs. Projected (post-improvement)
- Categories: By severity level
- Include: Percentage reduction labels

### Section 4: Proposed Countermeasures

For each countermeasure, include:
```markdown
#### Countermeasure: [Name from CMF Clearinghouse]

**CMF Clearinghouse ID:** [Number]
**Crash Modification Factor:** [Value with confidence interval]
**Applicable Crash Types:** [List]
**Star Rating:** [1-5 stars]

**Description:**
[2-3 sentences explaining the countermeasure]

**Local Justification:**
[Why this countermeasure fits this location's crash patterns]

**Expected Effectiveness:**
- Target crash type reduction: X%
- Projected crashes prevented (5-year): X
- Projected injuries prevented: X
- Projected fatalities prevented: X
```

### Section 5: Project Schedule

Generate a Gantt chart or timeline table:

| Phase | Task | Duration | Start | End | Responsible Party |
|-------|------|----------|-------|-----|-------------------|
| 1 | Project Initiation | 1 month | Mo 1 | Mo 1 | Henrico DPW |
| 2 | Survey & Design | 4 months | Mo 2 | Mo 5 | Consultant |
| 3 | ROW Acquisition | 3 months | Mo 4 | Mo 6 | Real Property |
| 4 | Utility Coordination | 2 months | Mo 5 | Mo 6 | Utilities |
| 5 | Bidding & Award | 2 months | Mo 7 | Mo 8 | Procurement |
| 6 | Construction | 6 months | Mo 9 | Mo 14 | Contractor |
| 7 | Final Inspection | 1 month | Mo 15 | Mo 15 | VDOT/County |
| 8 | Project Closeout | 1 month | Mo 16 | Mo 16 | Henrico DPW |

### Section 6: Budget and Cost Estimate

#### Detailed Budget Table:
```markdown
| Item | Description | Quantity | Unit | Unit Cost | Total |
|------|-------------|----------|------|-----------|-------|
| 1.0 | **PRELIMINARY ENGINEERING** | | | | |
| 1.1 | Survey and Mapping | 1 | LS | $XX,XXX | $XX,XXX |
| 1.2 | Engineering Design | 1 | LS | $XX,XXX | $XX,XXX |
| 1.3 | Environmental Review | 1 | LS | $XX,XXX | $XX,XXX |
| | *Subtotal PE* | | | | $XX,XXX |
| 2.0 | **RIGHT-OF-WAY** | | | | |
| 2.1 | ROW Acquisition | X | SF | $XX | $XX,XXX |
| 2.2 | Utility Relocation | 1 | LS | $XX,XXX | $XX,XXX |
| | *Subtotal ROW* | | | | $XX,XXX |
| 3.0 | **CONSTRUCTION** | | | | |
| 3.1 | Mobilization | 1 | LS | $XX,XXX | $XX,XXX |
| 3.2 | [Specific items] | X | EA/LF | $XX | $XX,XXX |
| 3.3 | Traffic Control | 1 | LS | $XX,XXX | $XX,XXX |
| | *Subtotal Construction* | | | | $XX,XXX |
| 4.0 | **CONTINGENCY (15%)** | | | | $XX,XXX |
| | **TOTAL PROJECT COST** | | | | **$XXX,XXX** |
```

#### Funding Split:
```
Federal Share (90%): $XXX,XXX
Local Match (10%):   $XXX,XXX
Total:               $XXX,XXX
```

### Section 7: Benefit-Cost Analysis

#### Methodology Statement:
> "This analysis follows FHWA guidance using the most recent comprehensive crash costs and a 7% discount rate over a 20-year analysis period."

#### B/C Calculation Template:
```
BENEFITS:
- Annual crash reduction: [X crashes × avg cost = $XXX,XXX]
- 20-year benefit (discounted): $X,XXX,XXX
- Additional benefits (travel time, emissions): $XXX,XXX
- TOTAL BENEFITS: $X,XXX,XXX

COSTS:
- Initial construction: $XXX,XXX
- Annual maintenance (20-yr discounted): $XX,XXX
- TOTAL COSTS: $XXX,XXX

BENEFIT-COST RATIO: X.XX : 1
NET PRESENT VALUE: $X,XXX,XXX
```

### Section 8: Project Readiness

Include checklist-style verification:
```markdown
✓ Environmental clearance status: [Categorical Exclusion expected / NEPA complete]
✓ Right-of-way status: [No ROW required / ROW identified / ROW acquired]
✓ Utility coordination: [No conflicts / Relocations identified / Agreements in place]
✓ Design status: [Concept / 30% / 60% / 90% / Final]
✓ Permits required: [List with expected approval dates]
✓ Local funding committed: [Resolution attached / Budget line item]
✓ Maintenance commitment: [Letter attached]
```

### Section 9: Equity and Community Impact

Address equity requirements (especially for SS4A):
```markdown
**Underserved Community Analysis:**
- Census tract(s): [Numbers]
- Equity indicators present: [List applicable]
  □ Low-income community (>X% below poverty line)
  □ Limited English proficiency population
  □ Minority population concentration
  □ Zero-vehicle households
  □ Elderly population
  □ Disability population

**Community Engagement Conducted:**
- Public meetings held: [Dates, attendance]
- Community feedback incorporated: [Summary]
- Stakeholder support letters: [List attached]
```

---

## PDF Formatting Specifications

### Document Properties:
- **Page size:** 8.5" × 11" (Letter)
- **Margins:** 1" all sides
- **Font - Body:** Calibri or Arial, 11pt
- **Font - Headers:** Calibri or Arial Bold
  - H1: 16pt
  - H2: 14pt
  - H3: 12pt
- **Line spacing:** 1.15
- **Paragraph spacing:** 6pt after

### Header/Footer:
- Header: Project title (left), Page X of Y (right)
- Footer: Applicant name (left), Date (right)

### Table Formatting:
- Header row: Bold, shaded (10% gray)
- Alternating row shading: 5% gray
- Borders: 0.5pt gray
- Numbers: Right-aligned
- Text: Left-aligned

### Charts:
- Minimum 300 DPI resolution
- Include title and axis labels
- Legend positioned outside plot area
- Source citation below chart

---

## Word Document Structure

### Use Proper Styles:
```
Title → "CRASH LENS Grant Title"
Heading 1 → Section headers
Heading 2 → Subsection headers
Heading 3 → Sub-subsection headers
Normal → Body text
Table Grid → All tables
Caption → Figure and table captions
```

### Include Navigation:
- Table of Contents (auto-generated)
- List of Figures
- List of Tables
- Page breaks between major sections

### Appendices Structure:
```
Appendix A: Crash Data Tables
Appendix B: Location Maps and Photos
Appendix C: Countermeasure Documentation (CMF printouts)
Appendix D: Cost Estimates and Quotes
Appendix E: Letters of Support
Appendix F: Resolutions and Commitments
Appendix G: Environmental Documentation
```

---

## Quality Checklist Before Generation

Before finalizing, verify:

### Data Integrity
- [ ] All crash counts match source data
- [ ] Calculations are mathematically correct
- [ ] Dates and timeframes are consistent
- [ ] GPS coordinates are accurate
- [ ] Cost estimates are current year dollars

### Technical Accuracy
- [ ] CMFs are from Clearinghouse with proper citations
- [ ] Countermeasures match crash types
- [ ] Design references current MUTCD edition
- [ ] Virginia-specific standards cited where applicable

### Compliance
- [ ] All required sections included
- [ ] Page limits observed (if applicable)
- [ ] Required attachments listed
- [ ] Federal requirements addressed (ADA, NEPA, etc.)

### Professional Polish
- [ ] No spelling or grammar errors
- [ ] Consistent formatting throughout
- [ ] All figures/tables numbered and captioned
- [ ] Cross-references are correct
- [ ] Professional, neutral tone maintained

---

## Example Claude Code Prompt for Generation

```python
GRANT_SYSTEM_PROMPT = """
You are a senior traffic safety grant writer for Henrico County, Virginia 
Department of Public Works. You have 20+ years of experience winning 
competitive federal and state safety grants.

Your writing style is:
- Data-driven and quantitative
- Technically precise using correct engineering terminology
- Compelling without being sensational
- Action-oriented focusing on outcomes
- Compliant with federal grant requirements

When generating grant applications:
1. Lead every section with the most impactful data point
2. Quantify all claims with specific numbers
3. Connect crash patterns directly to proposed countermeasures
4. Calculate and present benefit-cost ratios
5. Demonstrate project readiness and local commitment
6. Address equity and community impact
7. Include all required visualizations with professional formatting

Use the provided crash data to generate accurate statistics, charts, and 
analysis. Never fabricate data - use only what is provided.

Format the output as a complete, submission-ready grant application 
following FHWA and Virginia DOT standards.
"""
```

---

## Integration with CRASH LENS

### Data Flow:
```
1. User selects location from crash data table
2. System retrieves:
   - 5-year crash history
   - Severity breakdown
   - Crash types and patterns
   - Temporal distribution
   - Existing conditions
3. System identifies applicable countermeasures from CMF database
4. Claude Code generates narrative with:
   - Problem statement using location-specific data
   - Countermeasure recommendations with CMFs
   - Benefit-cost calculations
   - Project schedule
   - Budget estimates
5. Charts generated using Chart.js/Plotly
6. Document assembled in PDF/Word format
```

### API Call Structure:
```javascript
const generateGrantApplication = async (locationData) => {
  const prompt = `
    ${GRANT_SYSTEM_PROMPT}
    
    Generate a complete HSIP grant application for:
    Location: ${locationData.name}
    Coordinates: ${locationData.lat}, ${locationData.lng}
    
    Crash Data (5-year):
    ${JSON.stringify(locationData.crashes, null, 2)}
    
    Recommended Countermeasures:
    ${JSON.stringify(locationData.countermeasures, null, 2)}
    
    Estimated Project Cost: ${locationData.estimatedCost}
    
    Generate all sections with professional formatting, 
    data visualizations specifications, and compelling narrative.
  `;
  
  const response = await anthropic.messages.create({
    model: "claude-sonnet-4-20250514",
    max_tokens: 8000,
    messages: [{ role: "user", content: prompt }]
  });
  
  return response.content;
};
```

---

## Final Notes for World-Class Applications

### What Wins Grants:
1. **Clear problem with quantified severity** - Reviewers need to see the urgency
2. **Data-backed solutions** - CMFs from Clearinghouse with high star ratings
3. **Strong B/C ratio** - Aim for 3:1 or higher
4. **Project readiness** - Show you can deliver on time
5. **Local commitment** - Match funding, maintenance agreements, political support
6. **Equity consideration** - Address underserved communities
7. **Professional presentation** - Clean, consistent, error-free

### Common Mistakes to Avoid:
- Vague problem statements without data
- Proposing countermeasures that don't match crash types
- Unrealistic timelines or budgets
- Missing required sections or attachments
- Typos and formatting inconsistencies
- Weak or missing B/C analysis
- Ignoring equity requirements
