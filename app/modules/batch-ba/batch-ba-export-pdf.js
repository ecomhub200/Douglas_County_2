/**
 * CrashLens Batch Before/After Evaluation — PDF Report Export
 * Professional multi-page PDF using jsPDF + AutoTable.
 */
window.CL = window.CL || {};
CL.batchBA = CL.batchBA || {};

/**
 * Generate and download batch BA PDF report.
 */
CL.batchBA.exportPDF = function() {
    var s = CL.batchBA.state;
    if (!s.summary || s.results.length === 0) {
        alert('No results to export. Run the batch analysis first.');
        return;
    }

    var jsPDF = window.jspdf.jsPDF;
    var doc = new jsPDF('p', 'mm', 'a4');
    var pw = doc.internal.pageSize.getWidth();
    var ph = doc.internal.pageSize.getHeight();
    var m = 15;
    var cw = pw - m * 2;

    var colors = {
        primary: [30, 64, 175], secondary: [124, 58, 237],
        success: [22, 163, 74], danger: [220, 38, 38],
        warning: [234, 88, 12], gray: [100, 116, 139],
        lightGray: [248, 250, 252], white: [255, 255, 255], text: [51, 51, 51]
    };

    var dateStamp = new Date().toISOString().split('T')[0];
    var generatedDate = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
    var successful = s.results.filter(function(r) { return r.status === 'success'; });
    var sum = s.summary;

    // ========== COVER PAGE ==========
    doc.setFillColor(...colors.primary);
    doc.rect(0, 0, pw, 60, 'F');
    doc.setFillColor(...colors.secondary);
    doc.rect(0, 52, pw, 8, 'F');

    doc.setTextColor(...colors.white);
    doc.setFontSize(28);
    doc.setFont('helvetica', 'bold');
    doc.text('CRASH LENS', m, 25);

    doc.setFontSize(16);
    doc.setFont('helvetica', 'normal');
    doc.text('Before/After Study — Batch Evaluation Report', m, 40);

    var y = 80;
    doc.setTextColor(...colors.text);
    doc.setFontSize(11);
    doc.text('Generated: ' + generatedDate, m, y);
    y += 8;
    doc.text('Total Locations: ' + sum.totalAnalyzed, m, y);
    y += 8;
    doc.text('Analysis Radius: ' + s.globalRadiusFt + ' ft', m, y);
    y += 8;
    doc.text('Confidence Level: ' + (s.confidenceLevel * 100) + '%', m, y);

    // ========== EXECUTIVE SUMMARY PAGE ==========
    doc.addPage();
    y = CL.batchBA._pdfHeader(doc, pw, m, colors, 'Executive Summary');

    // KPI boxes
    var kpiW = (cw - 12) / 4;
    var kpis = [
        { label: 'Locations Analyzed', value: sum.totalAnalyzed, color: colors.primary },
        { label: 'Avg Crash Reduction', value: sum.avgCrashReduction.toFixed(1) + '%', color: sum.avgCrashReduction > 0 ? colors.success : colors.danger },
        { label: 'Average CMF', value: sum.avgCMF.toFixed(3), color: sum.avgCMF < 1 ? colors.success : colors.danger },
        { label: 'Crashes Prevented', value: sum.crashesPrevented, color: colors.secondary }
    ];

    // Handle null avgCMF
    if (sum.avgCMF === null) {
        kpis[2].value = 'N/A';
        kpis[2].color = colors.gray;
    }

    kpis.forEach(function(kpi, i) {
        var x = m + i * (kpiW + 4);
        doc.setFillColor(...colors.white);
        doc.roundedRect(x, y, kpiW, 22, 2, 2, 'F');
        doc.setDrawColor(220, 220, 220);
        doc.roundedRect(x, y, kpiW, 22, 2, 2, 'S');
        doc.setFillColor(...kpi.color);
        doc.rect(x, y, kpiW, 3, 'F');

        doc.setFontSize(13);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(...kpi.color);
        doc.text(String(kpi.value), x + kpiW / 2, y + 12, { align: 'center' });

        doc.setFontSize(7);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(...colors.gray);
        doc.text(kpi.label, x + kpiW / 2, y + 18, { align: 'center' });
    });

    y += 30;

    // Effectiveness distribution
    doc.setFontSize(11);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(...colors.primary);
    doc.text('Effectiveness Distribution', m, y);
    y += 7;

    var effData = [
        ['Highly Effective (CMF < 0.70)', sum.byEffectiveness['Highly Effective'] || 0],
        ['Effective (CMF 0.70–0.90)', sum.byEffectiveness['Effective'] || 0],
        ['Marginal (CMF 0.90–1.00)', sum.byEffectiveness['Marginal'] || 0],
        ['Ineffective (CMF 1.00–1.10)', sum.byEffectiveness['Ineffective'] || 0],
        ['Negative Impact (CMF > 1.10)', sum.byEffectiveness['Negative Impact'] || 0]
    ];

    doc.autoTable({
        startY: y,
        head: [['Rating', 'Count']],
        body: effData,
        margin: { left: m, right: m },
        styles: { fontSize: 9, cellPadding: 2 },
        headStyles: { fillColor: colors.primary, textColor: 255 },
        columnStyles: { 1: { halign: 'center', cellWidth: 30 } }
    });

    y = doc.lastAutoTable.finalY + 10;

    // Significance summary
    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(...colors.text);
    doc.text(sum.significantCount + ' of ' + sum.totalAnalyzed + ' locations (' + sum.significantPct.toFixed(0) + '%) showed statistically significant changes.', m, y);

    // ========== SUMMARY TABLE PAGE ==========
    doc.addPage();
    y = CL.batchBA._pdfHeader(doc, pw, m, colors, 'Location Summary Table');

    var tableBody = successful.map(function(r) {
        var rating = CL.batchBA.getEffectivenessRating(r.cmf);
        return [
            r.locationName.substring(0, 25),
            r.countermeasureType || '-',
            r.beforeTotal,
            r.afterTotal,
            r.changePct.toFixed(1) + '%',
            r.cmf !== null ? r.cmf.toFixed(3) : 'N/A',
            r.isSignificant ? 'Yes' : 'No',
            rating.label
        ];
    });

    doc.autoTable({
        startY: y,
        head: [['Location', 'Type', 'Before', 'After', 'Change', 'CMF', 'Sig.', 'Rating']],
        body: tableBody,
        margin: { left: m, right: m },
        styles: { fontSize: 7, cellPadding: 1.5 },
        headStyles: { fillColor: colors.primary, textColor: 255, fontSize: 7 },
        alternateRowStyles: { fillColor: colors.lightGray },
        columnStyles: {
            0: { cellWidth: 35 },
            2: { halign: 'center', cellWidth: 14 },
            3: { halign: 'center', cellWidth: 14 },
            4: { halign: 'center', cellWidth: 18 },
            5: { halign: 'center', cellWidth: 16 },
            6: { halign: 'center', cellWidth: 12 }
        },
        didParseCell: function(data) {
            if (data.column.index === 4 && data.section === 'body') {
                var val = parseFloat(data.cell.raw);
                if (val < 0) { data.cell.styles.textColor = colors.success; data.cell.styles.fontStyle = 'bold'; }
                else if (val > 0) { data.cell.styles.textColor = colors.danger; data.cell.styles.fontStyle = 'bold'; }
            }
        }
    });

    // ========== INDIVIDUAL LOCATION PAGES (3 per page) ==========
    var locPerPage = 3;
    for (var i = 0; i < successful.length; i++) {
        if (i % locPerPage === 0) {
            doc.addPage();
            y = CL.batchBA._pdfHeader(doc, pw, m, colors, 'Individual Location Results (Page ' + (Math.floor(i / locPerPage) + 1) + ')');
        }

        var r = successful[i];
        var rating = CL.batchBA.getEffectivenessRating(r.cmf);

        // Location header
        doc.setFillColor(...colors.lightGray);
        doc.roundedRect(m, y, cw, 8, 1, 1, 'F');
        doc.setFontSize(9);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(...colors.primary);
        doc.text(r.locationName.substring(0, 50), m + 3, y + 5.5);

        doc.setFont('helvetica', 'normal');
        doc.setTextColor(...colors.gray);
        doc.text(r.countermeasureType || '-', pw - m - 3, y + 5.5, { align: 'right' });
        y += 11;

        // Mini stats
        doc.setFontSize(8);
        doc.setTextColor(...colors.text);
        var statsLine = 'Before: ' + r.beforeTotal + ' crashes | After: ' + r.afterTotal + ' | Change: ' + r.changePct.toFixed(1) + '% | CMF: ' + (r.cmf !== null ? r.cmf.toFixed(3) : 'N/A') + ' | EPDO: ' + Math.round(r.beforeEPDO) + ' → ' + Math.round(r.afterEPDO);
        doc.text(statsLine, m + 3, y);
        y += 5;

        var sigLine = 'Period: ' + r.beforeStart.toLocaleDateString() + ' to ' + r.afterEnd.toLocaleDateString() + ' | Radius: ' + r.radiusFt + ' ft | p=' + r.pValue.toFixed(4) + ' | ' + rating.label;
        doc.text(sigLine, m + 3, y);
        y += 5;

        // Severity mini table
        doc.autoTable({
            startY: y,
            head: [['', 'K', 'A', 'B', 'C', 'O', 'Total', 'EPDO']],
            body: [
                ['Before', r.beforeStats.K, r.beforeStats.A, r.beforeStats.B, r.beforeStats.C, r.beforeStats.O, r.beforeTotal, Math.round(r.beforeEPDO)],
                ['After', r.afterStats.K, r.afterStats.A, r.afterStats.B, r.afterStats.C, r.afterStats.O, r.afterTotal, Math.round(r.afterEPDO)]
            ],
            margin: { left: m + 3, right: m + 3 },
            styles: { fontSize: 7, cellPadding: 1 },
            headStyles: { fillColor: colors.secondary, textColor: 255, fontSize: 7 },
            columnStyles: { 0: { fontStyle: 'bold' }, 1: { halign: 'center' }, 2: { halign: 'center' }, 3: { halign: 'center' }, 4: { halign: 'center' }, 5: { halign: 'center' }, 6: { halign: 'center', fontStyle: 'bold' }, 7: { halign: 'center' } }
        });

        y = doc.lastAutoTable.finalY + 8;

        // Check if we need a new page
        if (y > ph - 40 && i < successful.length - 1 && (i + 1) % locPerPage !== 0) {
            doc.addPage();
            y = CL.batchBA._pdfHeader(doc, pw, m, colors, 'Individual Location Results (cont.)');
        }
    }

    // ========== METHODOLOGY APPENDIX ==========
    doc.addPage();
    y = CL.batchBA._pdfHeader(doc, pw, m, colors, 'Methodology Notes');

    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(...colors.text);

    var epdoInfo = CL.core.epdo.getStateEPDOWeights(typeof STATE_FIPS !== 'undefined' ? STATE_FIPS : '_default');
    var methodText = [
        'Analysis Method: Empirical Bayes (simplified) with Poisson variance approximation.',
        'Confidence Level: ' + (s.confidenceLevel * 100) + '%. Statistical significance determined by two-tailed z-test.',
        'CMF (Crash Modification Factor): Ratio of observed after-period crashes to expected crashes based on before period.',
        'CRF (Crash Reduction Factor): (1 - CMF) × 100. Positive values indicate crash reduction.',
        'EPDO Weights (' + epdoInfo.name + '): K=' + epdoInfo.weights.K + ', A=' + epdoInfo.weights.A + ', B=' + epdoInfo.weights.B + ', C=' + epdoInfo.weights.C + ', O=' + epdoInfo.weights.O,
        'Source: ' + epdoInfo.source,
        '',
        'Effectiveness Ratings:',
        '  Highly Effective: CMF < 0.70 (>30% crash reduction)',
        '  Effective: CMF 0.70–0.90 (10-30% reduction)',
        '  Marginal: CMF 0.90–1.00 (0-10% reduction)',
        '  Ineffective: CMF 1.00–1.10 (0-10% increase)',
        '  Negative Impact: CMF > 1.10 (>10% increase)',
        '',
        'Note: The simplified EB method adjusts for different before/after period lengths but does not use',
        'Safety Performance Functions (SPFs) or reference group data. For HSIP-grade analysis, consider',
        'using the full single-location Before/After Study tab with EB methodology.'
    ];

    methodText.forEach(function(line) {
        doc.text(line, m, y);
        y += 5;
    });

    // ========== FOOTERS ON ALL PAGES ==========
    var totalPages = doc.internal.getNumberOfPages();
    for (var p = 1; p <= totalPages; p++) {
        doc.setPage(p);
        doc.setDrawColor(200, 200, 200);
        doc.setLineWidth(0.3);
        doc.line(m, ph - 15, pw - m, ph - 15);
        doc.setFontSize(7);
        doc.setTextColor(...colors.gray);
        var attribution = typeof getReportAttribution === 'function' ? getReportAttribution() : 'CRASH LENS';
        doc.text('Generated by ' + attribution, m, ph - 10);
        doc.text('Page ' + p + ' of ' + totalPages, pw - m, ph - 10, { align: 'right' });
    }

    // Save
    doc.save('Batch_BA_Report_' + dateStamp + '.pdf');
};

/** Draw page header and return Y position after it */
CL.batchBA._pdfHeader = function(doc, pw, m, colors, title) {
    doc.setFillColor(...colors.primary);
    doc.rect(0, 0, pw, 18, 'F');
    doc.setTextColor(...colors.white);
    doc.setFontSize(12);
    doc.setFont('helvetica', 'bold');
    doc.text('CRASH LENS — ' + title, m, 12);
    return 28;
};

CL._registerModule('batch-ba/export-pdf');
