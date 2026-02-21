/**
 * Standalone API Proxy Server
 *
 * Multi-purpose backend for CRASH LENS:
 *   - Qdrant Cloud proxy (avoids CORS from browser)
 *   - Brevo email notifications API
 *   - R2 upload for geocoded crash data
 *
 * Usage: node server/qdrant-proxy.js
 * Listens on port 3001 by default (configurable via PROXY_PORT env var)
 */

const http = require('http');
const https = require('https');
const url = require('url');
const { S3Client, PutObjectCommand, HeadObjectCommand } = require('@aws-sdk/client-s3');

const PORT = process.env.PROXY_PORT || 3001;

// Qdrant Cloud configuration (set via environment variables)
const QDRANT_ENDPOINT = process.env.QDRANT_ENDPOINT || '';
const QDRANT_API_KEY = process.env.QDRANT_API_KEY || '';

// Brevo email configuration (set via environment variables in Coolify)
const BREVO_API_KEY = process.env.BREVO_API_KEY || '';
const BREVO_SMTP_LOGIN = process.env.BREVO_SMTP_LOGIN || '';
const BREVO_SMTP_PASSWORD = process.env.BREVO_SMTP_PASSWORD || '';
const NOTIFICATION_FROM_EMAIL = process.env.NOTIFICATION_FROM_EMAIL || '';

// Cloudflare R2 configuration (set via environment variables in Coolify)
const CF_ACCOUNT_ID = process.env.CF_ACCOUNT_ID || '';
const CF_R2_ACCESS_KEY_ID = process.env.CF_R2_ACCESS_KEY_ID || '';
const CF_R2_SECRET_ACCESS_KEY = process.env.CF_R2_SECRET_ACCESS_KEY || '';
const R2_BUCKET_NAME = process.env.R2_BUCKET_NAME || 'crash-lens-data';

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

function sendViaBrevoApi(recipients, subject, htmlBody, textBody, attachment) {
    return new Promise((resolve, reject) => {
        // recipients can be a string (single email) or array of strings/objects
        const toList = Array.isArray(recipients)
            ? recipients.map(r => typeof r === 'string' ? { email: r } : r)
            : [{ email: recipients }];

        const emailPayload = {
            sender: { email: NOTIFICATION_FROM_EMAIL, name: 'CRASH LENS' },
            to: toList,
            subject: subject,
            htmlContent: htmlBody,
            textContent: textBody || ''
        };

        // Support PDF attachment: {content: base64String, name: 'report.pdf'}
        if (attachment && attachment.content && attachment.name) {
            emailPayload.attachment = [{
                content: attachment.content,
                name: attachment.name
            }];
        }

        const payload = JSON.stringify(emailPayload);

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

function collectBody(req, maxSize = 15 * 1024 * 1024) {
    return new Promise((resolve, reject) => {
        let body = '';
        let size = 0;
        req.on('data', chunk => {
            size += chunk.length;
            if (size > maxSize) {
                reject(new Error('Request body too large (max 15MB)'));
                req.destroy();
                return;
            }
            body += chunk;
        });
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

            const { to, subject, html, text, attachment } = payload;
            if (!to || !subject || !html) {
                res.writeHead(400, corsHeaders);
                res.end(JSON.stringify({ error: 'Missing required fields: to, subject, html' }));
                return;
            }

            const recipientList = Array.isArray(to) ? to : [to];
            console.log(`[Brevo] Sending email to ${recipientList.length} recipient(s): "${subject}"${attachment ? ' [+PDF attachment]' : ''}`);

            sendViaBrevoApi(recipientList, subject, html, text, attachment)
                .then(result => {
                    console.log(`[Brevo] Email sent successfully to ${recipientList.join(', ')}`);
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

    // ---- Brevo newsletter subscription (Contacts API) ----
    if (req.url === '/subscribe' && req.method === 'POST') {
        if (!BREVO_API_KEY) {
            res.writeHead(503, corsHeaders);
            res.end(JSON.stringify({
                error: 'Newsletter not configured',
                message: 'Set BREVO_API_KEY in environment variables'
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

            const { email } = payload;
            if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                res.writeHead(400, corsHeaders);
                res.end(JSON.stringify({ error: 'Valid email address is required' }));
                return;
            }

            // Add contact to Brevo via Contacts API
            const contactPayload = JSON.stringify({
                email: email,
                updateEnabled: true,
                attributes: {
                    SOURCE: 'website_newsletter',
                    SIGNUP_DATE: new Date().toISOString().split('T')[0]
                }
            });

            const options = {
                hostname: 'api.brevo.com',
                port: 443,
                path: '/v3/contacts',
                method: 'POST',
                headers: {
                    'accept': 'application/json',
                    'api-key': BREVO_API_KEY.trim(),
                    'content-type': 'application/json',
                    'content-length': Buffer.byteLength(contactPayload)
                }
            };

            const apiReq = https.request(options, (apiRes) => {
                let data = '';
                apiRes.on('data', chunk => { data += chunk; });
                apiRes.on('end', () => {
                    if (apiRes.statusCode === 201) {
                        console.log(`[Brevo] Newsletter subscriber added: ${email}`);
                        res.writeHead(201, corsHeaders);
                        res.end(JSON.stringify({ success: true, message: 'Subscribed successfully' }));
                    } else if (apiRes.statusCode === 204) {
                        // Contact already exists, updated
                        console.log(`[Brevo] Newsletter subscriber updated: ${email}`);
                        res.writeHead(200, corsHeaders);
                        res.end(JSON.stringify({ success: true, message: 'Subscription updated' }));
                    } else if (apiRes.statusCode === 400 && data.includes('already exist')) {
                        console.log(`[Brevo] Already subscribed: ${email}`);
                        res.writeHead(409, corsHeaders);
                        res.end(JSON.stringify({ success: true, message: 'Already subscribed' }));
                    } else {
                        console.error(`[Brevo] Subscribe error ${apiRes.statusCode}: ${data}`);
                        res.writeHead(apiRes.statusCode >= 500 ? 502 : apiRes.statusCode, corsHeaders);
                        res.end(JSON.stringify({ error: 'Subscription failed', message: data }));
                    }
                });
            });

            apiReq.on('error', (err) => {
                console.error(`[Brevo] Subscribe request failed: ${err.message}`);
                res.writeHead(502, corsHeaders);
                res.end(JSON.stringify({ error: 'Service unavailable', message: err.message }));
            });

            apiReq.write(contactPayload);
            apiReq.end();
        });
        return;
    }

    // ---- R2 upload: status check ----
    if (req.url === '/r2/status' && req.method === 'GET') {
        const configured = !!(CF_ACCOUNT_ID && CF_R2_ACCESS_KEY_ID && CF_R2_SECRET_ACCESS_KEY);
        res.writeHead(200, corsHeaders);
        res.end(JSON.stringify({
            configured,
            bucket: configured ? R2_BUCKET_NAME : null
        }));
        return;
    }

    // ---- R2 upload: upload geocoded CSV ----
    if (req.url === '/r2/upload-geocoded' && req.method === 'POST') {
        if (!CF_ACCOUNT_ID || !CF_R2_ACCESS_KEY_ID || !CF_R2_SECRET_ACCESS_KEY) {
            res.writeHead(503, corsHeaders);
            res.end(JSON.stringify({
                error: 'R2 not configured',
                message: 'Set CF_ACCOUNT_ID, CF_R2_ACCESS_KEY_ID, and CF_R2_SECRET_ACCESS_KEY in Coolify environment variables'
            }));
            return;
        }

        // Use larger body limit for CSV uploads (200MB)
        collectBody(req, 200 * 1024 * 1024).then(body => {
            let payload;
            try {
                payload = JSON.parse(body);
            } catch (e) {
                res.writeHead(400, corsHeaders);
                res.end(JSON.stringify({ error: 'Invalid JSON body' }));
                return;
            }

            const { r2Key, csvData } = payload;

            // Validate required fields
            if (!r2Key || !csvData) {
                res.writeHead(400, corsHeaders);
                res.end(JSON.stringify({ error: 'Missing required fields: r2Key, csvData' }));
                return;
            }

            // Validate r2Key format: {state}/{jurisdiction}/{filter}.csv
            const keyPattern = /^[a-z_-]+\/[a-z_-]+\/[a-z_]+\.csv$/;
            if (!keyPattern.test(r2Key)) {
                res.writeHead(400, corsHeaders);
                res.end(JSON.stringify({
                    error: 'Invalid r2Key format',
                    message: 'Expected pattern: {state}/{jurisdiction}/{filter}.csv (e.g., colorado/douglas/all_roads.csv)'
                }));
                return;
            }

            console.log(`[R2 Upload] Uploading geocoded CSV: ${r2Key} (${(Buffer.byteLength(csvData) / 1024 / 1024).toFixed(1)} MB)`);

            const s3Client = new S3Client({
                region: 'auto',
                endpoint: `https://${CF_ACCOUNT_ID}.r2.cloudflarestorage.com`,
                credentials: {
                    accessKeyId: CF_R2_ACCESS_KEY_ID,
                    secretAccessKey: CF_R2_SECRET_ACCESS_KEY,
                }
            });

            const putCmd = new PutObjectCommand({
                Bucket: R2_BUCKET_NAME,
                Key: r2Key,
                Body: csvData,
                ContentType: 'text/csv',
            });

            s3Client.send(putCmd)
                .then(() => {
                    const sizeBytes = Buffer.byteLength(csvData);
                    console.log(`[R2 Upload] Success: ${r2Key} (${sizeBytes.toLocaleString()} bytes)`);
                    res.writeHead(200, corsHeaders);
                    res.end(JSON.stringify({
                        success: true,
                        r2Key,
                        size: sizeBytes,
                        uploadedAt: new Date().toISOString()
                    }));
                })
                .catch(err => {
                    console.error(`[R2 Upload] Failed: ${err.message}`);
                    res.writeHead(500, corsHeaders);
                    res.end(JSON.stringify({ error: 'R2 upload failed', message: err.message }));
                });
        }).catch(err => {
            console.error(`[R2 Upload] Body error: ${err.message}`);
            res.writeHead(413, corsHeaders);
            res.end(JSON.stringify({ error: 'Request too large', message: err.message }));
        });
        return;
    }

    // ---- Nominatim geocoding proxy (avoids CORS from browser) ----
    if (req.url.startsWith('/geocode') && req.method === 'GET') {
        const parsed = url.parse(req.url, true);
        const q = parsed.query.q;
        const viewbox = parsed.query.viewbox || '';
        const bounded = parsed.query.bounded || '0';

        if (!q) {
            res.writeHead(400, corsHeaders);
            res.end(JSON.stringify({ error: 'Missing required parameter: q' }));
            return;
        }

        let nominatimUrl = 'https://nominatim.openstreetmap.org/search?format=json&limit=1'
            + '&q=' + encodeURIComponent(q)
            + '&countrycodes=us';
        if (viewbox) {
            nominatimUrl += '&viewbox=' + encodeURIComponent(viewbox) + '&bounded=' + bounded;
        }

        console.log(`[Geocode Proxy] ${q}`);

        const options = {
            hostname: 'nominatim.openstreetmap.org',
            port: 443,
            path: nominatimUrl.replace('https://nominatim.openstreetmap.org', ''),
            method: 'GET',
            headers: {
                'User-Agent': 'CrashLens/1.0 (crash-lens.aicreatesai.com)',
                'Accept': 'application/json'
            }
        };

        const proxyReq = https.request(options, (proxyRes) => {
            let data = '';
            proxyRes.on('data', chunk => { data += chunk; });
            proxyRes.on('end', () => {
                res.writeHead(proxyRes.statusCode, {
                    ...corsHeaders,
                    'Content-Type': 'application/json'
                });
                res.end(data);
            });
        });

        proxyReq.on('error', (err) => {
            console.error('[Geocode Proxy] Error:', err.message);
            res.writeHead(500, corsHeaders);
            res.end(JSON.stringify({ error: 'Geocode proxy error', message: err.message }));
        });

        proxyReq.end();
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
    if (CF_ACCOUNT_ID && CF_R2_ACCESS_KEY_ID && CF_R2_SECRET_ACCESS_KEY) {
        console.log(`[R2] Upload configured (bucket: ${R2_BUCKET_NAME})`);
    } else {
        console.warn('[R2] WARNING: R2 credentials not set - /r2 endpoints will return 503');
    }
});
