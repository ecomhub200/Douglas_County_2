/**
 * CrashLens Batch Before/After Evaluation — PDF Report Details Pages
 * Location Summary Table, Individual Location Cards, Methodology Appendix.
 * Called from batch-ba-export-pdf.js via shared context CL.batchBA._pdfCtx.
 */
window.CL = window.CL || {};
CL.batchBA = CL.batchBA || {};

/**
 * Render location table, individual cards, methodology, footers, and save.
 */
CL.batchBA._exportPDFDetails = function() {
    var ctx = CL.batchBA._pdfCtx;
    if (!ctx) return;

    var doc = ctx.doc;
    var m = ctx.m;
    var pw = ctx.pw;
    var cw = ctx.cw;
    var C = ctx.C;
    var successful = ctx.successful;
    var epdoInfo = ctx.epdoInfo;
    var s = ctx.s;
    var hexToRgb = ctx.hexToRgb;
    var setColor = ctx.setColor;
    var setFill = ctx.setFill;
    var cleanText = ctx.cleanText;
    var ratingColor = ctx.ratingColor;

    // ================================================================
    // LOCATION SUMMARY TABLE
    // ================================================================
    ctx.newPage();
    ctx.addSectionTitle('Location Summary Table');

    var tableBody = successful.map(function(r) {
        var rating = CL.batchBA.getEffectivenessRating(r.cmf);
        return [
            r.locationName.substring(0, 28),
            r.countermeasureType ? r.countermeasureType.substring(0, 15) : '-',
            r.beforeTotal,
            r.afterTotal,
            r.changePct.toFixed(1) + '%',
            Math.round(r.beforeEPDO),
            Math.round(r.afterEPDO),
            r.cmf !== null ? r.cmf.toFixed(3) : 'N/A',
            r.isSignificant ? 'Yes' : 'No',
            rating.label
        ];
    });

    doc.autoTable({
        startY: ctx.y,
        head: [['Location', 'Type', 'Before', 'After', 'Change', 'EPDO B', 'EPDO A', 'CMF', 'Sig.', 'Rating']],
        body: tableBody,
        margin: { left: m, right: m },
        styles: { fontSize: 7, cellPadding: 1.5 },
        headStyles: { fillColor: hexToRgb(C.primary), textColor: [255, 255, 255], fontSize: 7 },
        alternateRowStyles: { fillColor: hexToRgb(C.lightBg) },
        columnStyles: {
            0: { cellWidth: 35 }, 1: { cellWidth: 22 },
            2: { halign: 'center', cellWidth: 12 }, 3: { halign: 'center', cellWidth: 12 },
            4: { halign: 'center', cellWidth: 15 },
            5: { halign: 'center', cellWidth: 14 }, 6: { halign: 'center', cellWidth: 14 },
            7: { halign: 'center', cellWidth: 14 }, 8: { halign: 'center', cellWidth: 10 }
        },
        didParseCell: function(data) {
            if (data.section === 'body') {
                if (data.column.index === 4) {
                    var val = parseFloat(data.cell.raw);
                    if (val < 0) { data.cell.styles.textColor = hexToRgb(C.successLight); data.cell.styles.fontStyle = 'bold'; }
                    else if (val > 0) { data.cell.styles.textColor = hexToRgb(C.danger); data.cell.styles.fontStyle = 'bold'; }
                }
                if (data.column.index === 9) {
                    var rc = ratingColor(data.cell.raw);
                    data.cell.styles.textColor = hexToRgb(rc);
                    data.cell.styles.fontStyle = 'bold';
                }
            }
        }
    });

    // ================================================================
    // INDIVIDUAL LOCATION DETAIL PAGES
    // ================================================================
    for (var i = 0; i < successful.length; i++) {
        var r = successful[i];
        var rating = CL.batchBA.getEffectivenessRating(r.cmf);

        if (i === 0 || ctx.y > ctx.safeBottom - 65) {
            ctx.newPage();
            ctx.addSectionTitle('Individual Location Results');
        }

        ctx.checkPageBreak(65);
        setFill(C.lightBg);
        var borderRgb = hexToRgb(C.primary);
        doc.setDrawColor(borderRgb.r, borderRgb.g, borderRgb.b);
        doc.setLineWidth(0.5);
        doc.roundedRect(m, ctx.y, cw, 8, 1, 1, 'FD');
        doc.setFontSize(9);
        doc.setFont('helvetica', 'bold');
        setColor(C.primary);
        doc.text((i + 1) + '. ' + cleanText(r.locationName).substring(0, 50), m + 3, ctx.y + 5.5);
        doc.setFont('helvetica', 'normal');
        setColor(C.textLight);
        doc.text(r.countermeasureType || '-', pw - m - 3, ctx.y + 5.5, { align: 'right' });
        ctx.y += 11;

        doc.setFontSize(8);
        doc.setFont('helvetica', 'normal');
        setColor(C.text);
        doc.text('Install Date: ' + r.installDate.toLocaleDateString() + '  |  Radius: ' + r.radiusFt + ' ft  |  Lat: ' + r.lat.toFixed(4) + '  Lng: ' + r.lng.toFixed(4), m + 3, ctx.y);
        ctx.y += 4;
        doc.text('Before: ' + r.beforeStart.toLocaleDateString() + ' - ' + r.beforeEnd.toLocaleDateString() + ' (' + r.beforeYears.toFixed(1) + ' yr)  |  After: ' + r.afterStart.toLocaleDateString() + ' - ' + r.afterEnd.toLocaleDateString() + ' (' + r.afterYears.toFixed(1) + ' yr)', m + 3, ctx.y);
        ctx.y += 5;

        var badgeColor = ratingColor(rating.label);
        setFill(badgeColor);
        doc.roundedRect(pw - m - 40, ctx.y - 7, 37, 6, 1, 1, 'F');
        doc.setFontSize(7);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(255, 255, 255);
        doc.text(rating.label, pw - m - 21.5, ctx.y - 3, { align: 'center' });

        doc.autoTable({
            startY: ctx.y,
            head: [['Period', 'K', 'A', 'B', 'C', 'O', 'Unk', 'Total', 'EPDO', 'Rate/Yr']],
            body: [
                ['Before', r.beforeStats.K, r.beforeStats.A, r.beforeStats.B, r.beforeStats.C, r.beforeStats.O, r.beforeStats.U || 0, r.beforeTotal, Math.round(r.beforeEPDO), (r.beforeTotal / r.beforeYears).toFixed(1)],
                ['After', r.afterStats.K, r.afterStats.A, r.afterStats.B, r.afterStats.C, r.afterStats.O, r.afterStats.U || 0, r.afterTotal, Math.round(r.afterEPDO), (r.afterTotal / r.afterYears).toFixed(1)]
            ],
            margin: { left: m + 3, right: m + 3 },
            styles: { fontSize: 7, cellPadding: 1.5 },
            headStyles: { fillColor: hexToRgb(C.primary), textColor: [255, 255, 255], fontSize: 7 },
            columnStyles: {
                0: { fontStyle: 'bold', cellWidth: 16 },
                1: { halign: 'center' }, 2: { halign: 'center' }, 3: { halign: 'center' },
                4: { halign: 'center' }, 5: { halign: 'center' }, 6: { halign: 'center' },
                7: { halign: 'center', fontStyle: 'bold' },
                8: { halign: 'center' }, 9: { halign: 'center' }
            }
        });
        ctx.y = doc.lastAutoTable.finalY + 2;

        doc.setFontSize(8);
        doc.setFont('helvetica', 'normal');
        setColor(C.text);
        var cmfStr = r.cmf !== null ? r.cmf.toFixed(3) : 'N/A';
        var crfStr = r.crf !== null ? ((r.crf > 0 ? '+' : '') + r.crf.toFixed(1) + '%') : 'N/A';
        doc.text('CMF: ' + cmfStr + '  |  CRF: ' + crfStr + '  |  p-value: ' + r.pValue.toFixed(4) + '  |  ' + (r.isSignificant ? 'Statistically Significant' : 'Not Significant'), m + 3, ctx.y + 3);
        ctx.y += 10;
    }

    // ================================================================
    // METHODOLOGY APPENDIX
    // ================================================================
    ctx.newPage();
    ctx.addSectionTitle('Methodology Notes');

    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    setColor(C.text);

    var methodHeaders = ['Analysis Method', 'Statistical Significance', 'Crash Modification Factor (CMF)',
        'Crash Reduction Factor (CRF)', 'EPDO (Equivalent Property Damage Only)',
        'Effectiveness Ratings', 'Limitations'];

    var methodLines = [
        'Analysis Method',
        'Empirical Bayes (simplified) with Poisson variance approximation. The expected after-period crash count',
        'is estimated by adjusting the before-period count for the ratio of study period lengths.',
        '',
        'Statistical Significance',
        'Two-tailed z-test based on Poisson distribution. Confidence level: ' + (s.confidenceLevel * 100) + '%.',
        'A location is flagged as significant when p-value < ' + (1 - s.confidenceLevel).toFixed(2) + '.',
        '',
        'Crash Modification Factor (CMF)',
        'CMF = Observed After-Period Crashes / Expected After-Period Crashes.',
        'Values less than 1.0 indicate crash reduction. Values greater than 1.0 indicate crash increase.',
        '',
        'Crash Reduction Factor (CRF)',
        'CRF = (1 - CMF) x 100. Positive values = crash reduction percentage.',
        '',
        'EPDO (Equivalent Property Damage Only)',
        'Weights: ' + epdoInfo.name,
        'K = ' + epdoInfo.weights.K + ', A = ' + epdoInfo.weights.A + ', B = ' + epdoInfo.weights.B + ', C = ' + epdoInfo.weights.C + ', O = ' + epdoInfo.weights.O,
        'Source: ' + epdoInfo.source,
        '',
        'Effectiveness Ratings',
        '  Highly Effective:   CMF < 0.70 (greater than 30% crash reduction)',
        '  Effective:          CMF 0.70 - 0.90 (10-30% reduction)',
        '  Marginal:           CMF 0.90 - 1.00 (0-10% reduction)',
        '  Ineffective:        CMF 1.00 - 1.10 (0-10% increase)',
        '  Negative Impact:    CMF > 1.10 (greater than 10% increase)',
        '',
        'Limitations',
        'This analysis uses a simplified EB method that adjusts for period length but does not incorporate',
        'Safety Performance Functions (SPFs) or reference group data. For HSIP-grade documentation,',
        'use the full single-location Before/After Study tab with complete EB methodology.'
    ];

    methodLines.forEach(function(line) {
        if (line === '') { ctx.y += 3; return; }
        if (methodHeaders.indexOf(line) !== -1) {
            ctx.checkPageBreak(12);
            doc.setFont('helvetica', 'bold');
            setColor(C.primary);
            doc.text(line, m, ctx.y);
            ctx.y += 5;
            doc.setFont('helvetica', 'normal');
            setColor(C.text);
        } else {
            ctx.checkPageBreak(6);
            doc.text(line, m, ctx.y);
            ctx.y += 4.5;
        }
    });

    // ================================================================
    // ADD FOOTERS TO ALL PAGES & SAVE
    // ================================================================
    var totalPages = doc.internal.getNumberOfPages();
    for (var p = 1; p <= totalPages; p++) {
        doc.setPage(p);
        ctx.drawPageFooter(p, totalPages);
    }

    doc.save('Batch_BA_Report_' + ctx.dateStamp + '.pdf');
};

CL._registerModule('batch-ba/export-pdf-details');
