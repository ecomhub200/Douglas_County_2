/**
 * CrashLens AI Context Builders
 * Extracted from app/index.html — builds structured context objects for AI prompts
 */
window.CL = window.CL || {};
CL.ai = CL.ai || {};

CL.ai.context = {

    /**
     * Build location-specific crash context for AI from a context object.
     * @param {Object} context - AI analysis context {mode, locationName, source, dateRange, crashCount, profile}
     * @returns {Object|null} Structured location context for AI
     */
    buildLocationCrashContext: function(context) {
        if (!context || context.mode !== 'location') return null;

        var profile = context.profile;
        if (!profile) return null;

        return {
            analysisScope: 'LOCATION-SPECIFIC',
            location: context.locationName,
            source: context.source,
            dateRange: context.dateRange || 'All available years',
            summary: {
                totalCrashes: context.crashCount,
                severity: profile.severity || { K: profile.K || 0, A: profile.A || 0, B: profile.B || 0, C: profile.C || 0, O: profile.O || 0 },
                epdo: profile.epdo || 0
            },
            collisionTypes: profile.collisionTypes || {},
            factors: profile.factors || {},
            lightConditions: profile.lightConditions || {},
            weatherConditions: profile.weatherConditions || {}
        };
    }
};

CL._registerModule('ai/context');
