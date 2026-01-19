/**
 * Netlify Serverless Function: Qdrant Proxy
 *
 * Purpose: Proxy requests to Qdrant Cloud to avoid CORS issues
 * when calling from browser-based applications.
 *
 * Endpoints supported:
 * - GET  /collections - List all collections
 * - GET  /collections/{name} - Get collection info
 * - PUT  /collections/{name} - Create collection
 * - POST /collections/{name}/points/search - Search vectors
 * - PUT  /collections/{name}/points - Upsert points
 */

// Qdrant Cloud configuration
// In production, move these to Netlify environment variables
const QDRANT_ENDPOINT = process.env.QDRANT_ENDPOINT || 'https://b6241048-2ec5-4e12-94ee-ceecd2e68b75.us-east4-0.gcp.cloud.qdrant.io:6333';
const QDRANT_API_KEY = process.env.QDRANT_API_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.kSewQz40hEUchM9wWeT6cKisE2DhjkRUtkquJaGxGsc';

// Allowed origins for CORS (add your domains here)
const ALLOWED_ORIGINS = [
    'https://crash-lens.aicreatesai.com',
    'https://ecomhub200.github.io',
    'https://ecomhub200.netlify.app',
    'http://localhost:3000',
    'http://localhost:5500',
    'http://127.0.0.1:5500'
];

// CORS headers
function getCorsHeaders(origin) {
    const isAllowed = ALLOWED_ORIGINS.includes(origin) || origin?.includes('localhost') || origin?.includes('127.0.0.1');
    return {
        'Access-Control-Allow-Origin': isAllowed ? origin : ALLOWED_ORIGINS[0],
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, api-key',
        'Access-Control-Max-Age': '86400',
    };
}

// Main handler
exports.handler = async (event, context) => {
    const origin = event.headers.origin || event.headers.Origin;
    const corsHeaders = getCorsHeaders(origin);

    // Handle preflight requests
    if (event.httpMethod === 'OPTIONS') {
        return {
            statusCode: 204,
            headers: corsHeaders,
            body: ''
        };
    }

    try {
        // Parse the path from query params or path
        // Expected format: ?path=/collections or ?path=/collections/traffic-standards/points/search
        const queryParams = event.queryStringParameters || {};
        let qdrantPath = queryParams.path || '/collections';

        // Ensure path starts with /
        if (!qdrantPath.startsWith('/')) {
            qdrantPath = '/' + qdrantPath;
        }

        // Build Qdrant URL
        const qdrantUrl = `${QDRANT_ENDPOINT}${qdrantPath}`;

        console.log(`[Qdrant Proxy] ${event.httpMethod} ${qdrantPath}`);

        // Prepare fetch options
        const fetchOptions = {
            method: event.httpMethod,
            headers: {
                'api-key': QDRANT_API_KEY,
                'Content-Type': 'application/json'
            }
        };

        // Add body for POST/PUT requests
        if (event.body && (event.httpMethod === 'POST' || event.httpMethod === 'PUT')) {
            fetchOptions.body = event.body;
        }

        // Make request to Qdrant
        const response = await fetch(qdrantUrl, fetchOptions);

        // Get response body
        const responseText = await response.text();
        let responseBody;
        try {
            responseBody = JSON.parse(responseText);
        } catch {
            responseBody = { raw: responseText };
        }

        // Return response with CORS headers
        return {
            statusCode: response.status,
            headers: {
                ...corsHeaders,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(responseBody)
        };

    } catch (error) {
        console.error('[Qdrant Proxy] Error:', error);

        return {
            statusCode: 500,
            headers: {
                ...corsHeaders,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                error: 'Proxy error',
                message: error.message
            })
        };
    }
};
