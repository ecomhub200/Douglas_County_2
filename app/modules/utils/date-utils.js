/**
 * CrashLens Date Utilities
 * Extracted from app/index.html — pure date helper functions
 */
window.CL = window.CL || {};
CL.utils = CL.utils || {};

CL.utils.dateUtils = {
    parseCrashDateToTimestamp: function(dateStr) {
        if (!dateStr) return null;

        // If it's already a number (timestamp), return it
        var numVal = Number(dateStr);
        if (!isNaN(numVal) && numVal > 946684800000) { // After year 2000 in ms
            return numVal;
        }

        // Try parsing date string formats
        // Common formats: "11/4/2017 4:00:00 AM", "2017-11-04", etc.
        var d = new Date(dateStr);
        if (!isNaN(d.getTime())) {
            return d.getTime();
        }

        return null;
    },

    formatDateForDisplay: function(date) {
        var options = { year: 'numeric', month: 'short', day: 'numeric' };
        return date.toLocaleDateString('en-US', options);
    }
};

CL._registerModule('utils/date-utils');
