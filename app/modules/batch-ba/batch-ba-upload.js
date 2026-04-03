/**
 * CrashLens Batch Before/After Evaluation — Upload & Column Detection
 * Handles CSV/Excel file upload, auto-detection of columns, validation.
 */
window.CL = window.CL || {};
CL.batchBA = CL.batchBA || {};

// Column header synonyms for auto-detection
var BATCH_BA_SYNONYMS = {
    locationName: ['name', 'location', 'intersection', 'site', 'description', 'project_name', 'location_name', 'location name', 'project name', 'project'],
    latitude: ['lat', 'latitude', 'y', 'lat_coord', 'gps_lat', 'y_coord'],
    longitude: ['lng', 'lon', 'longitude', 'x', 'lng_coord', 'long', 'gps_lon', 'gps_lng', 'x_coord'],
    installDate: ['install_date', 'installation_date', 'date_installed', 'completion_date', 'start_date', 'date', 'install', 'install date', 'installation date', 'date installed', 'completion date'],
    countermeasureType: ['type', 'countermeasure', 'treatment', 'measure', 'asset_type', 'cm_type', 'countermeasure type', 'treatment type'],
    studyDuration: ['duration', 'study_period', 'months', 'period', 'before_period', 'after_period', 'study duration', 'study_duration'],
    radiusFt: ['radius', 'radius_ft', 'buffer', 'buffer_ft', 'radius ft']
};

/**
 * Handle file selection from input or drag-and-drop.
 * @param {File} file
 */
CL.batchBA.handleFileUpload = function(file) {
    if (!file) return;
    var name = file.name.toLowerCase();
    var ext = name.split('.').pop().toLowerCase();

    // Determine file type from full filename (order matters: check compound extensions first)
    var fileType;
    if (name.endsWith('.parquet.gz')) {
        fileType = 'parquet.gz';
    } else if (name.endsWith('.csv.gz')) {
        fileType = 'csv.gz';
    } else if (ext === 'csv' || ext === 'xlsx' || ext === 'xls') {
        fileType = ext;
    } else {
        alert('Please upload a .csv, .csv.gz, .parquet.gz, .xlsx, or .xls file.');
        return;
    }

    CL.batchBA.state.uploadedFile = file;
    document.getElementById('batchBAFileName').textContent = file.name;
    document.getElementById('batchBAFileInfo').style.display = 'flex';

    if (fileType === 'csv') {
        CL.batchBA._parseCSV(file);
    } else if (fileType === 'csv.gz') {
        CL.batchBA._parseCsvGz(file);
    } else if (fileType === 'parquet.gz') {
        CL.batchBA._parseParquetGz(file);
    } else {
        CL.batchBA._parseExcel(file);
    }
};

/** Parse CSV using Papa Parse */
CL.batchBA._parseCSV = function(file) {
    Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        complete: function(results) {
            CL.batchBA._onParsed(results.data, results.meta.fields || []);
        },
        error: function(err) {
            alert('Error parsing CSV: ' + err.message);
        }
    });
};

/** Parse Excel using SheetJS */
CL.batchBA._parseExcel = function(file) {
    var reader = new FileReader();
    reader.onload = function(e) {
        try {
            var workbook = XLSX.read(e.target.result, { type: 'array', cellDates: true });
            var sheetName = workbook.SheetNames[0];
            var sheet = workbook.Sheets[sheetName];
            var json = XLSX.utils.sheet_to_json(sheet, { defval: '' });
            var headers = json.length > 0 ? Object.keys(json[0]) : [];
            CL.batchBA._onParsed(json, headers);
        } catch (err) {
            alert('Error parsing Excel file: ' + err.message);
        }
    };
    reader.readAsArrayBuffer(file);
};

/** Parse CSV.GZ — decompress gzip then parse as CSV */
CL.batchBA._parseCsvGz = function(file) {
    var reader = new FileReader();
    reader.onload = function(e) {
        try {
            var csvText = _decompressGzipToText(e.target.result);
            var results = Papa.parse(csvText, { header: true, skipEmptyLines: true });
            CL.batchBA._onParsed(results.data, results.meta.fields || []);
        } catch (err) {
            alert('Error decompressing/parsing CSV.GZ: ' + err.message);
        }
    };
    reader.readAsArrayBuffer(file);
};

/** Parse Parquet.GZ — decompress gzip, parse parquet, convert to rows */
CL.batchBA._parseParquetGz = function(file) {
    var reader = new FileReader();
    reader.onload = async function(e) {
        try {
            var result = await _parseParquetGz(e.target.result);
            CL.batchBA._onParsed(result.rows, result.fields || []);
        } catch (err) {
            alert('Error decompressing/parsing Parquet.GZ: ' + err.message);
        }
    };
    reader.readAsArrayBuffer(file);
};

/** Common handler after file is parsed */
CL.batchBA._onParsed = function(rows, headers) {
    CL.batchBA.state.parsedRows = rows;
    CL.batchBA._autoDetectColumns(headers);
    CL.batchBA._renderColumnMapping(headers);
    CL.batchBA._renderPreviewTable(rows.slice(0, 10), headers);
    document.getElementById('batchBAMappingSection').style.display = 'block';
    document.getElementById('batchBAPreviewSection').style.display = 'block';
};

/** Auto-detect column mapping from headers */
CL.batchBA._autoDetectColumns = function(headers) {
    var mapping = CL.batchBA.state.columnMapping;
    var lowered = headers.map(function(h) { return h.toLowerCase().trim(); });

    Object.keys(BATCH_BA_SYNONYMS).forEach(function(field) {
        var synonyms = BATCH_BA_SYNONYMS[field];
        for (var i = 0; i < lowered.length; i++) {
            if (synonyms.indexOf(lowered[i]) !== -1) {
                mapping[field] = headers[i];
                break;
            }
        }
    });

    // Check if required fields were found
    var requiredFound = mapping.locationName && mapping.latitude && mapping.longitude && mapping.installDate;
    CL.batchBA.state.autoDetected = !!requiredFound;
};

/** Render column mapping UI */
CL.batchBA._renderColumnMapping = function(headers) {
    var mapping = CL.batchBA.state.columnMapping;
    var fields = [
        { key: 'locationName', label: 'Location Name', required: true },
        { key: 'latitude', label: 'Latitude', required: true },
        { key: 'longitude', label: 'Longitude', required: true },
        { key: 'installDate', label: 'Installation Date', required: true },
        { key: 'countermeasureType', label: 'Countermeasure Type', required: false },
        { key: 'studyDuration', label: 'Study Duration (months)', required: false },
        { key: 'radiusFt', label: 'Radius Override (ft)', required: false }
    ];

    var html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem">';
    fields.forEach(function(f) {
        var reqMark = f.required ? '<span style="color:#dc2626">*</span>' : '<span style="color:#94a3b8">(optional)</span>';
        html += '<div class="filter-group">';
        html += '<label style="font-size:.85rem;font-weight:600">' + f.label + ' ' + reqMark + '</label>';
        html += '<select id="batchBAMap_' + f.key + '" onchange="CL.batchBA._onMappingChange()" style="font-size:.85rem">';
        html += '<option value="">-- Select Column --</option>';
        headers.forEach(function(h) {
            var sel = mapping[f.key] === h ? ' selected' : '';
            html += '<option value="' + h.replace(/"/g, '&quot;') + '"' + sel + '>' + h + '</option>';
        });
        html += '</select></div>';
    });
    html += '</div>';

    if (CL.batchBA.state.autoDetected) {
        html += '<div class="info-box tip" style="margin-top:.75rem"><span class="icon">✓</span><div class="content"><p>Columns auto-detected successfully. Review and adjust if needed.</p></div></div>';
    } else {
        html += '<div class="info-box warning" style="margin-top:.75rem"><span class="icon">⚠️</span><div class="content"><p>Could not auto-detect all required columns. Please map them manually.</p></div></div>';
    }

    html += '<div style="margin-top:1rem;display:flex;gap:.75rem">';
    html += '<button class="btn-soft btn-soft-primary" onclick="CL.batchBA.applyMapping()">Apply Mapping & Validate</button>';
    html += '</div>';

    document.getElementById('batchBAMappingContent').innerHTML = html;
};

/** Handle mapping dropdown changes */
CL.batchBA._onMappingChange = function() {
    var mapping = CL.batchBA.state.columnMapping;
    Object.keys(mapping).forEach(function(key) {
        var sel = document.getElementById('batchBAMap_' + key);
        if (sel) mapping[key] = sel.value || null;
    });
};

/** Render preview table of first N rows */
CL.batchBA._renderPreviewTable = function(rows, headers) {
    if (!rows.length) return;
    var html = '<div style="overflow-x:auto"><table class="data-table" style="font-size:.8rem"><thead><tr>';
    html += '<th style="width:30px">#</th>';
    headers.forEach(function(h) { html += '<th>' + h + '</th>'; });
    html += '</tr></thead><tbody>';

    rows.forEach(function(row, idx) {
        html += '<tr>';
        html += '<td>' + (idx + 1) + '</td>';
        headers.forEach(function(h) {
            var val = row[h] != null ? String(row[h]).substring(0, 30) : '';
            html += '<td>' + val + '</td>';
        });
        html += '</tr>';
    });
    html += '</tbody></table></div>';
    html += '<div style="font-size:.8rem;color:#64748b;margin-top:.5rem">Showing first ' + rows.length + ' of ' + CL.batchBA.state.parsedRows.length + ' rows</div>';

    document.getElementById('batchBAPreviewContent').innerHTML = html;
};

/**
 * Apply mapping, validate all rows, and show validation summary.
 */
CL.batchBA.applyMapping = function() {
    CL.batchBA._onMappingChange();
    var mapping = CL.batchBA.state.columnMapping;

    // Check required fields are mapped
    if (!mapping.locationName || !mapping.latitude || !mapping.longitude || !mapping.installDate) {
        alert('Please map all required fields (Location Name, Latitude, Longitude, Installation Date).');
        return;
    }

    var valid = [];
    var invalid = [];

    CL.batchBA.state.parsedRows.forEach(function(row, idx) {
        var errors = [];
        var name = String(row[mapping.locationName] || '').trim();
        var lat = parseFloat(row[mapping.latitude]);
        var lng = parseFloat(row[mapping.longitude]);
        var dateStr = row[mapping.installDate];
        var date = CL.batchBA._parseDate(dateStr);

        if (!name) errors.push('Blank location name');
        if (isNaN(lat) || lat < -90 || lat > 90) errors.push('Invalid latitude');
        if (isNaN(lng) || lng < -180 || lng > 180) errors.push('Invalid longitude');
        if (!date) errors.push('Invalid date');

        var entry = {
            rowIndex: idx,
            locationName: name,
            lat: lat,
            lng: lng,
            installDate: date,
            countermeasureType: mapping.countermeasureType ? String(row[mapping.countermeasureType] || '').trim() : '',
            studyDuration: mapping.studyDuration ? parseInt(row[mapping.studyDuration]) || null : null,
            radiusFt: mapping.radiusFt ? parseInt(row[mapping.radiusFt]) || null : null,
            errors: errors
        };

        if (errors.length === 0) {
            valid.push(entry);
        } else {
            invalid.push(entry);
        }
    });

    CL.batchBA.state.validRows = valid;
    CL.batchBA.state.invalidRows = invalid;

    CL.batchBA._renderValidationSummary(valid, invalid);
    document.getElementById('batchBAValidationSection').style.display = 'block';

    if (valid.length > 0) {
        // Initialize and show study duration configuration
        CL.batchBA.duration.init();
        CL.batchBA.duration.render();
        document.getElementById('batchBADurationSection').style.display = 'block';
        document.getElementById('batchBAConfigSection').style.display = 'block';
        CL.batchBA._updateSummaryCard();
    }
};

/** Parse various date formats including Excel serial numbers */
CL.batchBA._parseDate = function(val) {
    if (!val) return null;
    if (val instanceof Date && !isNaN(val)) return val;
    // Excel serial number (e.g., 44927 = 2023-01-10)
    if (typeof val === 'number' && val > 10000 && val < 100000) {
        var d = new Date((val - 25569) * 86400 * 1000);
        if (!isNaN(d)) return d;
    }
    var d = new Date(val);
    if (!isNaN(d) && d.getFullYear() > 1900) return d;
    // Try MM/DD/YYYY or DD/MM/YYYY
    var parts = String(val).split(/[\/\-\.]/);
    if (parts.length === 3) {
        // Try M/D/Y first
        d = new Date(parts[2], parts[0] - 1, parts[1]);
        if (!isNaN(d) && d.getFullYear() > 1900) return d;
        // Try Y-M-D
        d = new Date(parts[0], parts[1] - 1, parts[2]);
        if (!isNaN(d) && d.getFullYear() > 1900) return d;
    }
    return null;
};

/** Render validation summary */
CL.batchBA._renderValidationSummary = function(valid, invalid) {
    var total = valid.length + invalid.length;
    var html = '';
    if (invalid.length === 0) {
        html += '<div class="info-box tip"><span class="icon">✓</span><div class="content"><p><strong>All ' + valid.length + ' locations are valid</strong> and ready for analysis.</p></div></div>';
    } else {
        html += '<div class="info-box warning"><span class="icon">⚠️</span><div class="content">';
        html += '<p><strong>' + valid.length + ' of ' + total + ' locations valid.</strong> ' + invalid.length + ' location(s) have errors.</p>';
        html += '</div></div>';

        html += '<details style="margin-top:.75rem"><summary style="cursor:pointer;font-size:.85rem;color:#dc2626;font-weight:600">' + invalid.length + ' Error(s) — Click to expand</summary>';
        html += '<div style="max-height:200px;overflow-y:auto;margin-top:.5rem"><table class="data-table" style="font-size:.8rem"><thead><tr><th>Row</th><th>Location</th><th>Errors</th></tr></thead><tbody>';
        invalid.forEach(function(row) {
            html += '<tr style="background:#fef2f2"><td>' + (row.rowIndex + 1) + '</td><td>' + (row.locationName || 'N/A') + '</td><td style="color:#dc2626">' + row.errors.join('; ') + '</td></tr>';
        });
        html += '</tbody></table></div></details>';
    }

    if (valid.length > 0 && invalid.length > 0) {
        html += '<div style="margin-top:.75rem"><button class="btn-soft btn-soft-primary btn-soft-sm" onclick="CL.batchBA._proceedWithValid()">Proceed with ' + valid.length + ' valid locations</button></div>';
    }

    document.getElementById('batchBAValidationContent').innerHTML = html;
};

CL.batchBA._proceedWithValid = function() {
    CL.batchBA.duration.init();
    CL.batchBA.duration.render();
    document.getElementById('batchBADurationSection').style.display = 'block';
    document.getElementById('batchBAConfigSection').style.display = 'block';
    CL.batchBA._updateSummaryCard();
    document.getElementById('batchBADurationSection').scrollIntoView({ behavior: 'smooth' });
};

/** Update the batch summary info card */
CL.batchBA._updateSummaryCard = function() {
    var s = CL.batchBA.state;
    var el = document.getElementById('batchBASummaryInfo');
    if (el) {
        el.textContent = s.validRows.length + ' locations × ' + s.globalRadiusFt + ' ft radius × Before/After periods';
    }
};

/** Update radius from slider */
CL.batchBA.updateRadius = function(value) {
    CL.batchBA.state.globalRadiusFt = parseInt(value);
    var display = document.getElementById('batchBARadiusDisplay');
    if (display) display.textContent = value + ' ft';
    CL.batchBA._updateSummaryCard();
};

/**
 * Download sample CSV template.
 */
CL.batchBA.downloadTemplate = function() {
    var csv = 'Location Name,Latitude,Longitude,Installation Date,Countermeasure Type,Study Duration (months)\n';
    csv += 'Broad St & Staples Mill Rd Roundabout,37.6009,-77.4988,2022-06-15,Roundabout,36\n';
    csv += 'Three Chopt Rd RRFB,37.5896,-77.5542,2023-01-10,RRFB,24\n';
    csv += 'Patterson Ave Speed Cushions,37.5752,-77.5201,2021-09-01,Speed Table,48\n';

    var blob = new Blob([csv], { type: 'text/csv' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'batch_ba_template.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
};

CL._registerModule('batch-ba/upload');
