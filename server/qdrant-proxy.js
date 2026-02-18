/**
 * Standalone API Proxy Server
 *
 * Multi-purpose backend for CRASH LENS:
 *   - Qdrant Cloud proxy (avoids CORS from browser)
 *   - Brevo email notifications API
 *
 * Usage: node server/qdrant-proxy.js
 * Listens on port 3001 by default (configurable via PROXY_PORT env var)
 */

const http = require('http');
const https = require('https');
const url = require('url');

const PORT = process.env.PROXY_PORT || 3001;

// Qdrant Cloud configuration (set via environment variables)
const QDRANT_ENDPOINT = process.env.QDRANT_ENDPOINT || '';
const QDRANT_API_KEY = process.env.QDRANT_API_KEY || '';

// Brevo email configuration (set via environment variables in Coolify)
const BREVO_API_KEY = process.env.BREVO_API_KEY || '';
const BREVO_SMTP_LOGIN = process.env.BREVO_SMTP_LOGIN || '';
const BREVO_SMTP_PASSWORD = process.env.BREVO_SMTP_PASSWORD || '';
const NOTIFICATION_FROM_EMAIL = process.env.NOTIFICATION_FROM_EMAIL || '';

// CORS headers
function getCorsHeaders(origin) {
    return {
        'Access-Control-Allow-Origin': origin || '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, api-key',
        'Access-Control-Max-Age': '86400',
        'Content-Type': 'application/json'
    };
}

// =============================================================================
// Brevo Email Helpers
// =============================================================================

function sendViaBrevoApi(toEmail, subject, htmlBody, textBody) {
    return new Promise((resolve, reject) => {
        const payload = JSON.stringify({
            sender: { email: NOTIFICATION_FROM_EMAIL, name: 'CRASH LENS' },
            to: [{ email: toEmail }],
            subject: subject,
            htmlContent: htmlBody,
            textContent: textBody || ''
        });

        const options = {
            hostname: 'api.brevo.com',
            port: 443,
            path: '/v3/smtp/email',
            method: 'POST',
            headers: {
                'accept': 'application/json',
                'api-key': BREVO_API_KEY.trim(),
                'content-type': 'application/json',
                'content-length': Buffer.byteLength(payload)
            }
        };

        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', chunk => { data += chunk; });
            res.on('end', () => {
                if (res.statusCode >= 200 && res.statusCode < 300) {
                    resolve(JSON.parse(data || '{}'));
                } else {
                    reject(new Error(`Brevo API ${res.statusCode}: ${data}`));
                }
            });
        });
        req.on('error', reject);
        req.write(payload);
        req.end();
    });
}

function sendViaBrevoSmtp(toEmail, subject, htmlBody) {
    return new Promise((resolve, reject) => {
        // Node.js doesn't have built-in SMTP - use Brevo API if available, else error
        reject(new Error('SMTP mode requires BREVO_API_KEY. Set BREVO_API_KEY in Coolify environment variables.'));
    });
}

function collectBody(req) {
    return new Promise((resolve) => {
        let body = '';
        req.on('data', chunk => { body += chunk; });
        req.on('end', () => resolve(body));
    });
}

// =============================================================================
// HTTP Server
// =============================================================================

const server = http.createServer((req, res) => {
    const origin = req.headers.origin || '*';
    const corsHeaders = getCorsHeaders(origin);

    // Handle preflight
    if (req.method === 'OPTIONS') {
        res.writeHead(204, corsHeaders);
        res.end();
        return;
    }

    // Health check
    if (req.url === '/health') {
        res.writeHead(200, corsHeaders);
        res.end(JSON.stringify({ status: 'ok' }));
        return;
    }

    // ---- Brevo notification config check ----
    if (req.url === '/notify/status' && req.method === 'GET') {
        const hasApi = !!BREVO_API_KEY;
        const hasSmtp = !!(BREVO_SMTP_LOGIN && BREVO_SMTP_PASSWORD);
        const hasFrom = !!NOTIFICATION_FROM_EMAIL;
        res.writeHead(200, corsHeaders);
        res.end(JSON.stringify({
            configured: (hasApi || hasSmtp) && hasFrom,
            mode: hasApi ? 'api' : hasSmtp ? 'smtp' : 'none',
            from: hasFrom ? NOTIFICATION_FROM_EMAIL : null
        }));
        return;
    }

    // ---- Brevo send email endpoint ----
    if (req.url === '/notify/send' && req.method === 'POST') {
        if (!BREVO_API_KEY && !BREVO_SMTP_LOGIN) {
            res.writeHead(503, corsHeaders);
            res.end(JSON.stringify({
                error: 'Brevo not configured',
                message: 'Set BREVO_API_KEY (or BREVO_SMTP_LOGIN + BREVO_SMTP_PASSWORD) in Coolify environment variables'
            }));
            return;
        }
        if (!NOTIFICATION_FROM_EMAIL) {
            res.writeHead(503, corsHeaders);
            res.end(JSON.stringify({
                error: 'Sender not configured',
                message: 'Set NOTIFICATION_FROM_EMAIL in Coolify environment variables'
            }));
            return;
        }

        collectBody(req).then(body => {
            let payload;
            try {
                payload = JSON.parse(body);
            } catch (e) {
                res.writeHead(400, corsHeaders);
                res.end(JSON.stringify({ error: 'Invalid JSON body' }));
                return;
            }

            const { to, subject, html, text } = payload;
            if (!to || !subject || !html) {
                res.writeHead(400, corsHeaders);
                res.end(JSON.stringify({ error: 'Missing required fields: to, subject, html' }));
                return;
            }

            console.log(`[Brevo] Sending email to ${to}: "${subject}"`);

            sendViaBrevoApi(to, subject, html, text)
                .then(result => {
                    console.log(`[Brevo] Email sent successfully to ${to}`);
                    res.writeHead(200, corsHeaders);
                    res.end(JSON.stringify({ success: true, messageId: result.messageId }));
                })
                .catch(err => {
                    console.error(`[Brevo] Send failed: ${err.message}`);
                    res.writeHead(500, corsHeaders);
                    res.end(JSON.stringify({ error: 'Send failed', message: err.message }));
                });
        });
        return;
    }

    // ---- Qdrant proxy (existing) ----

    // Check if Qdrant is configured
    if (!QDRANT_ENDPOINT || !QDRANT_API_KEY) {
        res.writeHead(503, corsHeaders);
        res.end(JSON.stringify({
            error: 'Qdrant not configured',
            message: 'Set QDRANT_ENDPOINT and QDRANT_API_KEY environment variables'
        }));
        return;
    }

    // Parse the path query parameter
    const parsed = url.parse(req.url, true);
    let qdrantPath = parsed.query.path || '/collections';
    if (!qdrantPath.startsWith('/')) {
        qdrantPath = '/' + qdrantPath;
    }

    const qdrantUrl = new URL(qdrantPath, QDRANT_ENDPOINT);

    console.log(`[Qdrant Proxy] ${req.method} ${qdrantPath}`);

    // Collect request body
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
        const options = {
            hostname: qdrantUrl.hostname,
            port: qdrantUrl.port || 6333,
            path: qdrantUrl.pathname,
            method: req.method,
            headers: {
                'api-key': QDRANT_API_KEY,
                'Content-Type': 'application/json'
            }
        };

        const proto = qdrantUrl.protocol === 'https:' ? https : http;
        const proxyReq = proto.request(options, (proxyRes) => {
            let responseData = '';
            proxyRes.on('data', chunk => { responseData += chunk; });
            proxyRes.on('end', () => {
                res.writeHead(proxyRes.statusCode, corsHeaders);
                res.end(responseData);
            });
        });

        proxyReq.on('error', (err) => {
            console.error('[Qdrant Proxy] Error:', err.message);
            res.writeHead(500, corsHeaders);
            res.end(JSON.stringify({ error: 'Proxy error', message: err.message }));
        });

        if (body && (req.method === 'POST' || req.method === 'PUT')) {
            proxyReq.write(body);
        }
        proxyReq.end();
    });
});

server.listen(PORT, '127.0.0.1', () => {
    console.log(`[API Server] Listening on 127.0.0.1:${PORT}`);
    if (!QDRANT_ENDPOINT) {
        console.warn('[Qdrant] WARNING: QDRANT_ENDPOINT not set - proxy will return 503');
    }
    if (BREVO_API_KEY) {
        console.log(`[Brevo] API mode configured (from: ${NOTIFICATION_FROM_EMAIL || 'NOT SET'})`);
    } else if (BREVO_SMTP_LOGIN) {
        console.log(`[Brevo] SMTP mode configured (from: ${NOTIFICATION_FROM_EMAIL || 'NOT SET'})`);
    } else {
        console.warn('[Brevo] WARNING: No credentials set - /notify endpoints will return 503');
    }
});
