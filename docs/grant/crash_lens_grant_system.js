// CRASH LENS Grant Generator - System Prompts and Implementation

// =============================================================================
// MAIN SYSTEM PROMPT - Copy this directly into your Claude API call
// =============================================================================

const GRANT_WRITER_SYSTEM_PROMPT = `You are an elite traffic safety grant writer for Henrico County, Virginia Department of Public Works, with expertise in FHWA HSIP, Safe Streets for All (SS4A), and Virginia DOT grant programs.

## YOUR EXPERTISE
- 20+ years winning competitive federal/state safety grants
- Deep knowledge of CMF Clearinghouse and proven countermeasures
- Expert in KABCO severity analysis and benefit-cost calculations
- Fluent in MUTCD, AASHTO, and Virginia supplement standards

## WRITING PRINCIPLES
1. LEAD WITH IMPACT: Every section opens with the most compelling data point
2. QUANTIFY EVERYTHING: Replace "many crashes" with "47 crashes resulting in 12 serious injuries"
3. BE DEFINITIVE: Use "This project will" not "We hope to"
4. CONNECT DATA TO SOLUTION: Link each crash pattern to specific countermeasures
5. PROVE VALUE: Calculate and highlight benefit-cost ratios (target 3:1+)

## REQUIRED DOCUMENT STRUCTURE

### Executive Summary (300-400 words)
- Hook: Most severe statistic in opening sentence
- Problem: Quantified crash burden with dollar costs
- Solution: Countermeasures with CMF values
- Impact: Lives saved, injuries prevented
- Investment: Total cost and B/C ratio

### Problem Statement
- 5-year crash data table (K, A, B, C, PDO counts)
- Crash cost calculation using FHWA values
- Pattern analysis (temporal, type, contributing factors)
- Comparison to state/national averages
- Trend analysis with statistical significance

### Proposed Solution
- Each countermeasure with CMF Clearinghouse ID
- Star rating and confidence interval
- Specific crash types addressed
- Expected effectiveness calculations

### Budget
- Itemized cost estimate (PE, ROW, Construction)
- 15% contingency
- Federal/local split (typically 90/10 for HSIP)

### Benefit-Cost Analysis
- Use FHWA crash costs: K=$12.5M, A=$655K, B=$198K, C=$125K, PDO=$12.9K
- 20-year analysis period, 7% discount rate
- Calculate NPV and B/C ratio

### Project Readiness
- Environmental status
- ROW requirements
- Design completion percentage
- Committed local match

## CRASH COST VALUES (2024 FHWA)
Fatality (K): $12,500,000
Serious Injury (A): $655,000
Minor Injury (B): $198,000
Possible Injury (C): $125,000
Property Damage Only: $12,900

## FORMATTING RULES
- Use professional tables for all data
- Include chart specifications for visualizations
- Number all figures and tables
- Cross-reference throughout
- No bullet points in narrative sections - use flowing prose
- Active voice, present/future tense

## TONE
- Authoritative yet accessible
- Urgent without sensationalism
- Technical precision
- Outcome-focused

NEVER fabricate data. Use only the crash statistics provided. If data is missing, note what additional information would strengthen the application.`;

// =============================================================================
// CHART GENERATION SPECIFICATIONS
// =============================================================================

const CHART_SPECIFICATIONS = {
  crashTrend: {
    type: 'line',
    title: 'Annual Crash Trend Analysis',
    config: {
      xAxis: { label: 'Year', type: 'category' },
      yAxis: { label: 'Number of Crashes', min: 0 },
      colors: {
        total: '#2563eb',
        injury: '#dc2626',
        fatal: '#7c2d12'
      },
      showTrendline: true,
      showDataLabels: true
    }
  },
  
  severityDistribution: {
    type: 'doughnut',
    title: 'Crash Severity Distribution',
    config: {
      colors: {
        K: '#7c2d12',  // Fatal - dark red
        A: '#dc2626',  // Serious - red
        B: '#f97316',  // Minor - orange
        C: '#facc15',  // Possible - yellow
        O: '#3b82f6'   // PDO - blue
      },
      showPercentages: true,
      showCounts: true
    }
  },
  
  crashTypeBreakdown: {
    type: 'horizontalBar',
    title: 'Crashes by Collision Type',
    config: {
      categories: [
        'Angle',
        'Rear End', 
        'Sideswipe - Same Direction',
        'Sideswipe - Opposite Direction',
        'Head On',
        'Pedestrian',
        'Bicycle',
        'Fixed Object',
        'Other'
      ],
      color: '#2563eb',
      showValues: true
    }
  },
  
  temporalHeatmap: {
    type: 'heatmap',
    title: 'Crash Frequency by Day and Hour',
    config: {
      xAxis: Array.from({length: 24}, (_, i) => `${i}:00`),
      yAxis: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
      colorScale: ['#f0f9ff', '#0369a1', '#0c4a6e'],
      showValues: true
    }
  },
  
  beforeAfterProjection: {
    type: 'groupedBar',
    title: 'Projected Crash Reduction',
    config: {
      groups: ['Current (5-Year Avg)', 'Projected (Post-Implementation)'],
      categories: ['Fatal', 'Serious Injury', 'Minor Injury', 'PDO'],
      colors: ['#dc2626', '#22c55e'],
      showPercentageReduction: true
    }
  },
  
  costBenefitComparison: {
    type: 'bar',
    title: 'Benefit-Cost Analysis',
    config: {
      categories: ['Project Cost', '20-Year Benefits'],
      colors: ['#dc2626', '#22c55e'],
      showBCRatio: true
    }
  }
};

// =============================================================================
// DOCUMENT GENERATION FUNCTION
// =============================================================================

async function generateGrantApplication(locationData, grantType = 'HSIP') {
  
  // Prepare the data context
  const dataContext = `
## LOCATION DATA
Name: ${locationData.name}
Route: ${locationData.route || 'N/A'}
Coordinates: ${locationData.lat}, ${locationData.lng}
Congressional District: ${locationData.congressionalDistrict || 'VA-XX'}
VDOT District: ${locationData.vdotDistrict || 'Richmond'}

## CRASH DATA (${locationData.dataYears || '5-Year Period'})
${formatCrashTable(locationData.crashes)}

## CRASH PATTERNS
Primary Crash Type: ${locationData.primaryCrashType || 'To be analyzed'}
Peak Hours: ${locationData.peakHours || 'To be analyzed'}
Contributing Factors: ${locationData.contributingFactors?.join(', ') || 'To be analyzed'}

## RECOMMENDED COUNTERMEASURES
${formatCountermeasures(locationData.countermeasures)}

## PROJECT PARAMETERS
Estimated Cost: $${locationData.estimatedCost?.toLocaleString() || 'TBD'}
Grant Type: ${grantType}
Federal Share: ${grantType === 'HSIP' ? '90%' : '80%'}
`;

  const userPrompt = `Generate a complete, submission-ready ${grantType} grant application for the following location. Include all sections with professional formatting, specific chart generation instructions, and compelling data-driven narrative.

${dataContext}

Generate the full application with:
1. Executive Summary
2. Problem Statement with data tables
3. Proposed Countermeasures with CMF documentation
4. Project Schedule (16-month timeline)
5. Detailed Budget
6. Benefit-Cost Analysis
7. Project Readiness Assessment
8. Equity and Community Impact Analysis

For each chart needed, provide the data arrays and configuration so they can be generated programmatically.`;

  // Make API call to Claude
  const response = await anthropic.messages.create({
    model: "claude-sonnet-4-20250514",
    max_tokens: 8000,
    system: GRANT_WRITER_SYSTEM_PROMPT,
    messages: [{ role: "user", content: userPrompt }]
  });

  return response.content[0].text;
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

function formatCrashTable(crashes) {
  if (!crashes) return 'No crash data provided';
  
  return `
| Severity | Count | Percentage | FHWA Cost | Total Cost |
|----------|-------|------------|-----------|------------|
| Fatal (K) | ${crashes.K || 0} | ${((crashes.K || 0) / crashes.total * 100).toFixed(1)}% | $12,500,000 | $${((crashes.K || 0) * 12500000).toLocaleString()} |
| Serious Injury (A) | ${crashes.A || 0} | ${((crashes.A || 0) / crashes.total * 100).toFixed(1)}% | $655,000 | $${((crashes.A || 0) * 655000).toLocaleString()} |
| Minor Injury (B) | ${crashes.B || 0} | ${((crashes.B || 0) / crashes.total * 100).toFixed(1)}% | $198,000 | $${((crashes.B || 0) * 198000).toLocaleString()} |
| Possible Injury (C) | ${crashes.C || 0} | ${((crashes.C || 0) / crashes.total * 100).toFixed(1)}% | $125,000 | $${((crashes.C || 0) * 125000).toLocaleString()} |
| PDO (O) | ${crashes.O || 0} | ${((crashes.O || 0) / crashes.total * 100).toFixed(1)}% | $12,900 | $${((crashes.O || 0) * 12900).toLocaleString()} |
| **TOTAL** | **${crashes.total}** | **100%** | -- | **$${calculateTotalCrashCost(crashes).toLocaleString()}** |
`;
}

function calculateTotalCrashCost(crashes) {
  return (crashes.K || 0) * 12500000 +
         (crashes.A || 0) * 655000 +
         (crashes.B || 0) * 198000 +
         (crashes.C || 0) * 125000 +
         (crashes.O || 0) * 12900;
}

function formatCountermeasures(countermeasures) {
  if (!countermeasures || countermeasures.length === 0) {
    return 'Countermeasures to be determined based on crash analysis';
  }
  
  return countermeasures.map((cm, i) => `
### Countermeasure ${i + 1}: ${cm.name}
- CMF Clearinghouse ID: ${cm.cmfId || 'TBD'}
- Crash Modification Factor: ${cm.cmf || 'TBD'}
- Star Rating: ${cm.starRating || 'TBD'} stars
- Target Crash Types: ${cm.targetCrashTypes?.join(', ') || 'TBD'}
- Estimated Cost: $${cm.cost?.toLocaleString() || 'TBD'}
`).join('\n');
}

// =============================================================================
// PDF GENERATION STYLES
// =============================================================================

const PDF_STYLES = {
  document: {
    pageSize: 'LETTER',
    pageMargins: [72, 72, 72, 72], // 1 inch margins
    defaultStyle: {
      font: 'Calibri',
      fontSize: 11,
      lineHeight: 1.15
    }
  },
  
  styles: {
    title: {
      fontSize: 18,
      bold: true,
      alignment: 'center',
      margin: [0, 0, 0, 20]
    },
    h1: {
      fontSize: 16,
      bold: true,
      margin: [0, 20, 0, 10],
      color: '#1e3a5f'
    },
    h2: {
      fontSize: 14,
      bold: true,
      margin: [0, 15, 0, 8],
      color: '#2c5282'
    },
    h3: {
      fontSize: 12,
      bold: true,
      margin: [0, 10, 0, 5]
    },
    body: {
      fontSize: 11,
      alignment: 'justify',
      margin: [0, 0, 0, 8]
    },
    tableHeader: {
      bold: true,
      fillColor: '#e2e8f0',
      alignment: 'center'
    },
    tableCell: {
      alignment: 'center',
      margin: [4, 4, 4, 4]
    },
    caption: {
      fontSize: 10,
      italics: true,
      alignment: 'center',
      margin: [0, 5, 0, 15]
    },
    callout: {
      fillColor: '#f0f9ff',
      margin: [10, 10, 10, 10],
      padding: 10
    }
  },
  
  header: (currentPage, pageCount) => ({
    columns: [
      { text: 'HSIP Grant Application - [Project Name]', alignment: 'left', fontSize: 9 },
      { text: `Page ${currentPage} of ${pageCount}`, alignment: 'right', fontSize: 9 }
    ],
    margin: [72, 40, 72, 0]
  }),
  
  footer: {
    columns: [
      { text: 'Henrico County Department of Public Works', alignment: 'left', fontSize: 9 },
      { text: new Date().toLocaleDateString(), alignment: 'right', fontSize: 9 }
    ],
    margin: [72, 0, 72, 40]
  }
};

// =============================================================================
// WORD DOCUMENT STYLES (for docx generation)
// =============================================================================

const WORD_STYLES = {
  document: {
    title: 'Traffic Safety Grant Application',
    creator: 'Henrico County DPW - CRASH LENS',
    description: 'Auto-generated grant application'
  },
  
  styles: {
    Title: { font: 'Calibri', size: 36, bold: true, color: '1e3a5f' },
    Heading1: { font: 'Calibri', size: 32, bold: true, color: '1e3a5f' },
    Heading2: { font: 'Calibri', size: 28, bold: true, color: '2c5282' },
    Heading3: { font: 'Calibri', size: 24, bold: true },
    Normal: { font: 'Calibri', size: 22, lineSpacing: 1.15 }
  },
  
  tableStyles: {
    headerRow: { fill: 'e2e8f0', bold: true },
    alternatingRows: true,
    borders: { color: 'cccccc', size: 1 }
  }
};

// =============================================================================
// EXPORT MODULES
// =============================================================================

module.exports = {
  GRANT_WRITER_SYSTEM_PROMPT,
  CHART_SPECIFICATIONS,
  PDF_STYLES,
  WORD_STYLES,
  generateGrantApplication,
  formatCrashTable,
  calculateTotalCrashCost,
  formatCountermeasures
};
