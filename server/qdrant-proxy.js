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
const fs = require('fs');
const path = require('path');
const { S3Client, PutObjectCommand, HeadObjectCommand } = require('@aws-sdk/client-s3');
const crypto = require('crypto');

const PORT = process.env.PROXY_PORT || 3001;

// Qdrant Cloud configuration (set via environment variables)
const QDRANT_ENDPOINT = process.env.QDRANT_ENDPOINT || '';
const QDRANT_API_KEY = process.env.QDRANT_API_KEY || '';

// Stripe configuration (set via environment variables in Coolify)
const STRIPE_SECRET_KEY = process.env.STRIPE_SECRET_KEY || '';
const STRIPE_WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET || '';
const STRIPE_PRICE_INDIVIDUAL_MONTHLY = process.env.STRIPE_PRICE_INDIVIDUAL_MONTHLY || '';
const STRIPE_PRICE_INDIVIDUAL_ANNUAL = process.env.STRIPE_PRICE_INDIVIDUAL_ANNUAL || '';
const STRIPE_PRICE_TEAM_MONTHLY = process.env.STRIPE_PRICE_TEAM_MONTHLY || '';
const STRIPE_PRICE_TEAM_ANNUAL = process.env.STRIPE_PRICE_TEAM_ANNUAL || '';
const APP_URL = process.env.APP_URL || 'https://crashlens.aicreatesai.com';

// Initialize Stripe (lazy - only when needed)
let stripe = null;
function getStripe() {
    if (!stripe && STRIPE_SECRET_KEY) {
        const Stripe = require('stripe');
        stripe = new Stripe(STRIPE_SECRET_KEY, { apiVersion: '2024-06-20' });
    }
    return stripe;
}

// Initialize Firebase Admin (lazy - only when needed)
let firebaseAdmin = null;
let firestoreDb = null;
function getFirestore() {
    if (!firestoreDb) {
        const admin = require('firebase-admin');
        const serviceAccount = process.env.FIREBASE_SERVICE_ACCOUNT;
        if (!serviceAccount) {
            throw new Error('FIREBASE_SERVICE_ACCOUNT not configured');
        }
        if (!firebaseAdmin) {
            firebaseAdmin = admin.initializeApp({
                credential: admin.credential.cert(JSON.parse(serviceAccount))
            });
        }
        firestoreDb = admin.firestore();
    }
    return firestoreDb;
}

// In-memory cache for forecast data (5-minute TTL)
const forecastCache = new Map();

// Map plan + billing cycle to Stripe Price ID
function getStripePriceId(plan, billingCycle) {
    const priceMap = {
        'individual_monthly': STRIPE_PRICE_INDIVIDUAL_MONTHLY,
        'individual_annual': STRIPE_PRICE_INDIVIDUAL_ANNUAL,
        'team_monthly': STRIPE_PRICE_TEAM_MONTHLY,
        'team_annual': STRIPE_PRICE_TEAM_ANNUAL
    };
    return priceMap[`${plan}_${billingCycle}`] || null;
}

// Map Stripe Price ID back to plan + billing cycle
function getPlanFromPriceId(priceId) {
    const reverseMap = {};
    if (STRIPE_PRICE_INDIVIDUAL_MONTHLY) reverseMap[STRIPE_PRICE_INDIVIDUAL_MONTHLY] = { plan: 'individual', billingCycle: 'monthly' };
    if (STRIPE_PRICE_INDIVIDUAL_ANNUAL) reverseMap[STRIPE_PRICE_INDIVIDUAL_ANNUAL] = { plan: 'individual', billingCycle: 'annual' };
    if (STRIPE_PRICE_TEAM_MONTHLY) reverseMap[STRIPE_PRICE_TEAM_MONTHLY] = { plan: 'team', billingCycle: 'monthly' };
    if (STRIPE_PRICE_TEAM_ANNUAL) reverseMap[STRIPE_PRICE_TEAM_ANNUAL] = { plan: 'team', billingCycle: 'annual' };
    return reverseMap[priceId] || null;
}

// AI query limits per plan
const PLAN_QUERY_LIMITS = {
    'trial': 0,
    'free_trial': 0,
    'individual': 100,
    'team': 500,
    'agency': 1000
};

// Seat allocation per plan
const PLAN_SEATS = {
    'trial': 1,
    'free_trial': 1,
    'individual': 1,
    'team': 5,
    'agency': 'unlimited'
};

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

// R2 Worker proxy configuration (secret stays server-side only)
const R2_WORKER_URL = process.env.R2_WORKER_URL || '';
const R2_WORKER_SECRET = process.env.R2_WORKER_SECRET || '';

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

function sendViaBrevoApi(recipients, subject, htmlBody, textBody, attachment, options = {}) {
    return new Promise((resolve, reject) => {
        // recipients can be a string (single email) or array of strings/objects
        const toList = Array.isArray(recipients)
            ? recipients.map(r => typeof r === 'string' ? { email: r } : r)
            : [{ email: recipients }];

        const emailPayload = {
            sender: { email: NOTIFICATION_FROM_EMAIL, name: options.senderName || 'CRASH LENS Reports' },
            to: toList,
            replyTo: { email: 'support@aicreatesai.com', name: 'CRASH LENS Support' },
            subject: subject,
            htmlContent: htmlBody,
            textContent: textBody || '',
            headers: {
                'X-Entity-Ref-ID': crypto.randomUUID(),
                ...(options.includeListHeaders ? {
                    'List-Unsubscribe': '<mailto:unsubscribe@crashlens.aicreatesai.com?subject=unsubscribe>'
                } : {})
            }
        };

        // Tag for Brevo tracking/analytics
        if (options.tag) {
            emailPayload.tags = [options.tag];
        }

        // Support PDF attachment: {content: base64String, name: 'report.pdf'}
        if (attachment && attachment.content && attachment.name) {
            emailPayload.attachment = [{
                content: attachment.content,
                name: attachment.name
            }];
        }

        const payload = JSON.stringify(emailPayload);

        const reqOptions = {
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

        const req = https.request(reqOptions, (res) => {
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
// Firebase Auth helper
// =============================================================================

async function verifyFirebaseToken(req) {
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
        throw new Error('Missing or invalid Authorization header');
    }
    const token = authHeader.split('Bearer ')[1];
    const admin = require('firebase-admin');
    // Ensure Firebase Admin is initialized
    getFirestore();
    const decoded = await admin.auth().verifyIdToken(token);
    return { uid: decoded.uid, email: decoded.email };
}

// =============================================================================
// Email Schedule helpers
// =============================================================================

// In-memory cache for due schedules (5-minute TTL)
let scheduleCache = { data: null, loadedAt: 0 };
const SCHEDULE_CACHE_TTL = 5 * 60 * 1000; // 5 minutes

function calculateNextRunAt(schedule) {
    const now = new Date();
    const { frequency, dayOfWeek, dayOfMonth, time, timezone } = schedule;
    const [hours, minutes] = (time || '08:00').split(':').map(Number);
    const tz = timezone || 'America/New_York';

    const formatter = new Intl.DateTimeFormat('en-US', {
        timeZone: tz, hour12: false,
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });

    // Start searching from 1 minute in the future
    let candidate = new Date(now.getTime() + 60000);

    for (let i = 0; i < 400; i++) {
        const parts = formatter.formatToParts(candidate);
        const p = {};
        parts.forEach(({ type, value }) => { p[type] = parseInt(value, 10); });

        const candidateDow = candidate.getDay(); // 0=Sun
        const candidateDay = p.day;

        let match = false;
        if (frequency === 'daily') {
            match = true;
        } else if (frequency === 'weekly') {
            match = candidateDow === (dayOfWeek != null ? dayOfWeek : 1);
        } else if (frequency === 'monthly') {
            match = candidateDay === (dayOfMonth || 1);
        } else if (frequency === 'quarterly') {
            match = candidateDay === (dayOfMonth || 1) && [1, 4, 7, 10].includes(p.month);
        } else if (frequency === 'annual') {
            match = candidateDay === (dayOfMonth || 1) && p.month === 1;
        }

        if (match) {
            const dateStr = `${String(p.year)}-${String(p.month).padStart(2, '0')}-${String(p.day).padStart(2, '0')}T${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:00`;
            // Convert target local time to UTC
            const utcTest = new Date(dateStr);
            const tzOffset = utcTest.getTime() - new Date(utcTest.toLocaleString('en-US', { timeZone: tz })).getTime();
            const finalDate = new Date(new Date(dateStr + 'Z').getTime() + tzOffset);

            if (finalDate > now) {
                return finalDate.toISOString();
            }
        }

        // Move to next day
        candidate = new Date(candidate.getTime() + 24 * 60 * 60 * 1000);
    }

    // Fallback: 1 week from now
    return new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000).toISOString();
}

function buildScheduledEmailHtml(schedule) {
    const appUrl = APP_URL || 'https://crashlens.aicreatesai.com';
    const agency = schedule.agency || 'Your Agency';
    const jurisdiction = schedule.jurisdiction || 'your jurisdiction';
    const state = schedule.state || '';

    return `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f4f5f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;padding:32px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
  <tr><td style="background:linear-gradient(135deg,#1a237e,#283593);padding:32px 40px;text-align:center;">
    <h1 style="color:#ffffff;margin:0;font-size:24px;">CRASH LENS</h1>
    <p style="color:#b3bef5;margin:8px 0 0;font-size:14px;">Scheduled Crash Analysis Report</p>
  </td></tr>
  <tr><td style="padding:32px 40px;">
    <h2 style="color:#1a237e;margin:0 0 16px;font-size:20px;">${agency} — ${jurisdiction.charAt(0).toUpperCase() + jurisdiction.slice(1)}</h2>
    <p style="color:#555;line-height:1.6;margin:0 0 24px;">Your scheduled ${schedule.frequency || 'periodic'} crash analysis report is ready for review. Click below to open the full interactive report in CRASH LENS.</p>
    <table cellpadding="0" cellspacing="0" style="margin:0 auto 24px;">
    <tr><td style="background:#1a237e;border-radius:6px;padding:14px 32px;">
      <a href="${appUrl}/app/?state=${encodeURIComponent(state)}&jurisdiction=${encodeURIComponent(jurisdiction)}" style="color:#ffffff;text-decoration:none;font-weight:600;font-size:16px;">View Full Report in CRASH LENS</a>
    </td></tr></table>
    <p style="color:#888;font-size:13px;margin:0;">Report type: ${schedule.reportType || 'Comprehensive'} | Frequency: ${schedule.frequency || 'Weekly'}</p>
  </td></tr>
  <tr><td style="background:#f8f9fa;padding:20px 40px;text-align:center;border-top:1px solid #e8eaed;">
    <p style="color:#999;font-size:12px;margin:0;">CRASH LENS by AI Creates AI &mdash; Traffic Safety Intelligence</p>
    <p style="color:#bbb;font-size:11px;margin:4px 0 0;">To change your schedule, open CRASH LENS &gt; Reports &gt; Email Settings</p>
  </td></tr>
</table>
</td></tr></table>
</body></html>`;
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

            const { to, subject, html, text, attachment, tag } = payload;
            if (!to || !subject || !html) {
                res.writeHead(400, corsHeaders);
                res.end(JSON.stringify({ error: 'Missing required fields: to, subject, html' }));
                return;
            }

            const recipientList = Array.isArray(to) ? to : [to];
            console.log(`[Brevo] Sending email to ${recipientList.length} recipient(s): "${subject}"${attachment ? ' [+PDF attachment]' : ''}`);

            sendViaBrevoApi(recipientList, subject, html, text, attachment, { tag: tag || 'crash-report' })
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

    // ---- Brevo newsletter subscription (Contacts API) with local file fallback ----
    if (req.url === '/subscribe' && req.method === 'POST') {
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

            // Helper: save subscriber to local JSON file
            function saveToLocalFile(email) {
                const subscribersPath = path.join(__dirname, '..', 'data', 'subscribers.json');
                try {
                    let fileData = { subscribers: [] };
                    if (fs.existsSync(subscribersPath)) {
                        fileData = JSON.parse(fs.readFileSync(subscribersPath, 'utf8'));
                    }
                    // Check for duplicate
                    const existing = fileData.subscribers.find(s => s.email && s.email.toLowerCase() === email.toLowerCase());
                    if (existing) {
                        return { status: 409, message: 'Already subscribed' };
                    }
                    fileData.subscribers.push({
                        id: `sub-${Date.now()}`,
                        email: email,
                        addedAt: new Date().toISOString(),
                        source: 'website_newsletter'
                    });
                    fileData.lastUpdated = new Date().toISOString();
                    fs.writeFileSync(subscribersPath, JSON.stringify(fileData, null, 2));
                    console.log(`[Newsletter] Subscriber saved locally: ${email}`);
                    return { status: 201, message: 'Subscribed successfully' };
                } catch (err) {
                    console.error(`[Newsletter] Local save failed: ${err.message}`);
                    return { status: 500, message: 'Failed to save subscription' };
                }
            }

            // If Brevo is not configured, fall back to local file storage
            if (!BREVO_API_KEY) {
                const result = saveToLocalFile(email);
                if (result.status === 409) {
                    res.writeHead(409, corsHeaders);
                    res.end(JSON.stringify({ success: true, message: result.message }));
                } else if (result.status === 201) {
                    res.writeHead(201, corsHeaders);
                    res.end(JSON.stringify({ success: true, message: result.message }));
                } else {
                    res.writeHead(result.status, corsHeaders);
                    res.end(JSON.stringify({ error: 'Subscription failed', message: result.message }));
                }
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
                    // Also save locally as backup
                    saveToLocalFile(email);

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
                // Fall back to local save on Brevo error
                const result = saveToLocalFile(email);
                if (result.status === 201 || result.status === 409) {
                    res.writeHead(result.status === 409 ? 409 : 201, corsHeaders);
                    res.end(JSON.stringify({ success: true, message: result.message }));
                } else {
                    res.writeHead(502, corsHeaders);
                    res.end(JSON.stringify({ error: 'Service unavailable', message: err.message }));
                }
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

    // ---- R2 upload: upload PDF report for email download links ----
    if (req.url === '/notify/upload-report' && req.method === 'POST') {
        // Check if R2 Worker is configured (preferred for public URLs)
        const hasR2Worker = !!(R2_WORKER_URL && R2_WORKER_SECRET);
        const hasR2Direct = !!(CF_ACCOUNT_ID && CF_R2_ACCESS_KEY_ID && CF_R2_SECRET_ACCESS_KEY);

        if (!hasR2Worker && !hasR2Direct) {
            res.writeHead(503, corsHeaders);
            res.end(JSON.stringify({
                error: 'R2 not configured',
                message: 'R2 Worker or direct R2 credentials required for PDF hosting'
            }));
            return;
        }

        collectBody(req, 50 * 1024 * 1024).then(body => {
            let payload;
            try {
                payload = JSON.parse(body);
            } catch (e) {
                res.writeHead(400, corsHeaders);
                res.end(JSON.stringify({ error: 'Invalid JSON body' }));
                return;
            }

            const { base64, filename } = payload;
            if (!base64 || !filename) {
                res.writeHead(400, corsHeaders);
                res.end(JSON.stringify({ error: 'Missing required fields: base64, filename' }));
                return;
            }

            // Sanitize filename
            const safeName = filename.replace(/[^a-zA-Z0-9._-]/g, '_');
            const reportId = crypto.randomUUID();
            const r2Key = `reports/${reportId}/${safeName}`;
            const pdfBuffer = Buffer.from(base64, 'base64');

            console.log(`[R2 Report] Uploading PDF: ${r2Key} (${(pdfBuffer.length / 1024).toFixed(1)} KB)`);

            if (hasR2Worker) {
                // Upload via R2 Worker (preferred - provides public URL)
                const uploadUrl = `${R2_WORKER_URL.replace(/\/+$/, '')}/${r2Key}`;
                const workerUrl = new URL(uploadUrl);

                const uploadReq = https.request({
                    hostname: workerUrl.hostname,
                    port: 443,
                    path: workerUrl.pathname,
                    method: 'PUT',
                    headers: {
                        'X-Upload-Secret': R2_WORKER_SECRET,
                        'Content-Type': 'application/pdf',
                        'Content-Length': pdfBuffer.length
                    }
                }, (workerRes) => {
                    let data = '';
                    workerRes.on('data', chunk => { data += chunk; });
                    workerRes.on('end', () => {
                        if (workerRes.statusCode >= 200 && workerRes.statusCode < 300) {
                            const downloadUrl = `${R2_WORKER_URL.replace(/\/+$/, '')}/${r2Key}`;
                            console.log(`[R2 Report] Upload success: ${downloadUrl}`);
                            res.writeHead(200, corsHeaders);
                            res.end(JSON.stringify({
                                success: true,
                                downloadUrl,
                                r2Key,
                                size: pdfBuffer.length
                            }));
                        } else {
                            console.error(`[R2 Report] Worker upload failed: ${workerRes.statusCode} ${data}`);
                            res.writeHead(500, corsHeaders);
                            res.end(JSON.stringify({ error: 'R2 Worker upload failed', message: data }));
                        }
                    });
                });
                uploadReq.on('error', (err) => {
                    console.error(`[R2 Report] Worker request error: ${err.message}`);
                    res.writeHead(500, corsHeaders);
                    res.end(JSON.stringify({ error: 'R2 Worker request failed', message: err.message }));
                });
                uploadReq.write(pdfBuffer);
                uploadReq.end();
            } else {
                // Upload via direct S3 API
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
                    Body: pdfBuffer,
                    ContentType: 'application/pdf',
                    ContentDisposition: `inline; filename="${safeName}"`,
                });

                s3Client.send(putCmd)
                    .then(() => {
                        // Direct S3 upload doesn't have a public URL by default
                        // Return the key so the front-end can construct the Worker URL if available
                        console.log(`[R2 Report] Direct upload success: ${r2Key}`);
                        res.writeHead(200, corsHeaders);
                        res.end(JSON.stringify({
                            success: true,
                            r2Key,
                            size: pdfBuffer.length,
                            message: 'Uploaded via direct R2. Configure R2_WORKER_URL for public download links.'
                        }));
                    })
                    .catch(err => {
                        console.error(`[R2 Report] Direct upload failed: ${err.message}`);
                        res.writeHead(500, corsHeaders);
                        res.end(JSON.stringify({ error: 'R2 upload failed', message: err.message }));
                    });
            }
        }).catch(err => {
            console.error(`[R2 Report] Body error: ${err.message}`);
            res.writeHead(413, corsHeaders);
            res.end(JSON.stringify({ error: 'Request too large', message: err.message }));
        });
        return;
    }

    // ---- R2 Worker proxy: status check ----
    if (req.url === '/r2/worker-status' && req.method === 'GET') {
        const configured = !!(R2_WORKER_URL && R2_WORKER_SECRET);
        res.writeHead(200, corsHeaders);
        res.end(JSON.stringify({
            configured,
            workerUrl: configured ? R2_WORKER_URL.replace(/\/+$/, '') : null
        }));
        return;
    }

    // ---- R2 Worker proxy: list objects ----
    if (req.url.startsWith('/r2/worker-list') && req.method === 'GET') {
        if (!R2_WORKER_URL || !R2_WORKER_SECRET) {
            res.writeHead(503, corsHeaders);
            res.end(JSON.stringify({
                error: 'R2 Worker not configured',
                message: 'Set R2_WORKER_URL and R2_WORKER_SECRET environment variables'
            }));
            return;
        }

        const parsed = url.parse(req.url, true);
        const prefix = parsed.query.prefix || '';
        const listUrl = `${R2_WORKER_URL.replace(/\/+$/, '')}/?list=1&prefix=${encodeURIComponent(prefix)}`;

        console.log(`[R2 Worker] List request: prefix=${prefix}`);

        const workerReq = https.get(listUrl, {
            headers: { 'X-Upload-Secret': R2_WORKER_SECRET }
        }, (workerRes) => {
            let data = '';
            workerRes.on('data', chunk => { data += chunk; });
            workerRes.on('end', () => {
                res.writeHead(workerRes.statusCode, corsHeaders);
                res.end(data);
            });
        });
        workerReq.on('error', (err) => {
            console.error(`[R2 Worker] List error: ${err.message}`);
            res.writeHead(502, corsHeaders);
            res.end(JSON.stringify({ error: 'R2 Worker request failed', message: err.message }));
        });
        return;
    }

    // ---- R2 Worker proxy: upload file (PUT) ----
    if (req.url.startsWith('/r2/worker-upload') && req.method === 'POST') {
        if (!R2_WORKER_URL || !R2_WORKER_SECRET) {
            res.writeHead(503, corsHeaders);
            res.end(JSON.stringify({
                error: 'R2 Worker not configured',
                message: 'Set R2_WORKER_URL and R2_WORKER_SECRET environment variables'
            }));
            return;
        }

        // Accept up to 200MB for CSV uploads
        collectBody(req, 200 * 1024 * 1024).then(body => {
            let payload;
            try {
                payload = JSON.parse(body);
            } catch (e) {
                res.writeHead(400, corsHeaders);
                res.end(JSON.stringify({ error: 'Invalid JSON body' }));
                return;
            }

            const { r2Key, data, contentType, bucket, backupMode } = payload;

            if (!r2Key || !data) {
                res.writeHead(400, corsHeaders);
                res.end(JSON.stringify({ error: 'Missing required fields: r2Key, data' }));
                return;
            }

            const uploadUrl = `${R2_WORKER_URL.replace(/\/+$/, '')}/${r2Key}`;
            const ct = contentType || 'text/csv';
            const headers = {
                'X-Upload-Secret': R2_WORKER_SECRET,
                'Content-Type': ct,
                'Content-Length': Buffer.byteLength(data)
            };
            if (bucket) headers['X-Bucket'] = bucket;
            if (backupMode) headers['X-Backup-Mode'] = backupMode;

            console.log(`[R2 Worker] Upload: ${r2Key} (${(Buffer.byteLength(data) / 1024).toFixed(1)} KB, type: ${ct})`);

            const parsedUrl = new URL(uploadUrl);
            const options = {
                hostname: parsedUrl.hostname,
                port: 443,
                path: parsedUrl.pathname + parsedUrl.search,
                method: 'PUT',
                headers
            };

            const workerReq = https.request(options, (workerRes) => {
                let responseData = '';
                workerRes.on('data', chunk => { responseData += chunk; });
                workerRes.on('end', () => {
                    if (workerRes.statusCode >= 200 && workerRes.statusCode < 300) {
                        console.log(`[R2 Worker] Upload success: ${r2Key}`);
                        res.writeHead(200, corsHeaders);
                        res.end(JSON.stringify({
                            success: true,
                            r2Key,
                            size: Buffer.byteLength(data),
                            uploadedAt: new Date().toISOString()
                        }));
                    } else {
                        console.error(`[R2 Worker] Upload failed: HTTP ${workerRes.statusCode} - ${responseData}`);
                        res.writeHead(workerRes.statusCode, corsHeaders);
                        res.end(JSON.stringify({
                            error: `R2 Worker returned HTTP ${workerRes.statusCode}`,
                            message: responseData
                        }));
                    }
                });
            });

            workerReq.on('error', (err) => {
                console.error(`[R2 Worker] Upload error: ${err.message}`);
                res.writeHead(502, corsHeaders);
                res.end(JSON.stringify({ error: 'R2 Worker request failed', message: err.message }));
            });

            workerReq.write(data);
            workerReq.end();

        }).catch(err => {
            console.error(`[R2 Worker] Body error: ${err.message}`);
            res.writeHead(413, corsHeaders);
            res.end(JSON.stringify({ error: 'Request too large', message: err.message }));
        });
        return;
    }

    // ---- Subscriber Management: Save subscribers to R2 ----
    if (req.url === '/subscribers/save' && req.method === 'POST') {
        if (!R2_WORKER_URL || !R2_WORKER_SECRET) {
            res.writeHead(503, corsHeaders);
            res.end(JSON.stringify({
                error: 'R2 Worker not configured',
                message: 'Set R2_WORKER_URL and R2_WORKER_SECRET environment variables'
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

            const { stateKey, jurisdiction, subscribers } = payload;

            if (!stateKey || !jurisdiction || !Array.isArray(subscribers)) {
                res.writeHead(400, corsHeaders);
                res.end(JSON.stringify({ error: 'Missing required fields: stateKey, jurisdiction, subscribers[]' }));
                return;
            }

            // Deduplicate by email (case-insensitive) before saving
            const seen = new Map();
            const deduped = [];
            for (const sub of subscribers) {
                if (!sub.address) continue;
                const key = sub.address.trim().toLowerCase();
                if (!seen.has(key)) {
                    seen.set(key, true);
                    deduped.push({ ...sub, address: key });
                }
            }

            const r2Key = `${stateKey}/${jurisdiction}/subscribers.json`;
            const jsonData = JSON.stringify({
                lastUpdated: new Date().toISOString(),
                jurisdiction: jurisdiction,
                stateKey: stateKey,
                subscribers: deduped
            }, null, 2);

            const uploadUrl = `${R2_WORKER_URL.replace(/\/+$/, '')}/${r2Key}`;
            const parsedUrl = new URL(uploadUrl);

            console.log(`[Subscribers] Saving ${deduped.length} subscribers to R2: ${r2Key}`);

            const workerReq = https.request({
                hostname: parsedUrl.hostname,
                port: 443,
                path: parsedUrl.pathname + parsedUrl.search,
                method: 'PUT',
                headers: {
                    'X-Upload-Secret': R2_WORKER_SECRET,
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(jsonData)
                }
            }, (workerRes) => {
                let responseData = '';
                workerRes.on('data', chunk => { responseData += chunk; });
                workerRes.on('end', () => {
                    if (workerRes.statusCode >= 200 && workerRes.statusCode < 300) {
                        console.log(`[Subscribers] Save success: ${r2Key} (${deduped.length} subscribers)`);
                        res.writeHead(200, corsHeaders);
                        res.end(JSON.stringify({
                            success: true,
                            count: deduped.length,
                            r2Key,
                            savedAt: new Date().toISOString()
                        }));
                    } else {
                        console.error(`[Subscribers] Save failed: HTTP ${workerRes.statusCode} - ${responseData}`);
                        res.writeHead(workerRes.statusCode, corsHeaders);
                        res.end(JSON.stringify({
                            error: `R2 Worker returned HTTP ${workerRes.statusCode}`,
                            message: responseData
                        }));
                    }
                });
            });

            workerReq.on('error', (err) => {
                console.error(`[Subscribers] Save error: ${err.message}`);
                res.writeHead(502, corsHeaders);
                res.end(JSON.stringify({ error: 'R2 Worker request failed', message: err.message }));
            });

            workerReq.write(jsonData);
            workerReq.end();

        }).catch(err => {
            console.error(`[Subscribers] Body error: ${err.message}`);
            res.writeHead(400, corsHeaders);
            res.end(JSON.stringify({ error: 'Request body error', message: err.message }));
        });
        return;
    }

    // ---- Subscriber Management: Load subscribers from R2 ----
    if (req.url.startsWith('/subscribers/load') && req.method === 'GET') {
        const parsed = url.parse(req.url, true);
        const stateKey = parsed.query.state;
        const jurisdiction = parsed.query.jurisdiction;

        if (!stateKey || !jurisdiction) {
            res.writeHead(400, corsHeaders);
            res.end(JSON.stringify({ error: 'Missing required query params: state, jurisdiction' }));
            return;
        }

        const r2Key = `${stateKey}/${jurisdiction}/subscribers.json`;
        const r2PublicUrl = `https://data.aicreatesai.com/${r2Key}`;

        console.log(`[Subscribers] Loading from R2: ${r2Key}`);

        https.get(r2PublicUrl, (r2Res) => {
            let data = '';
            r2Res.on('data', chunk => { data += chunk; });
            r2Res.on('end', () => {
                if (r2Res.statusCode === 200) {
                    try {
                        const parsed = JSON.parse(data);
                        console.log(`[Subscribers] Loaded ${parsed.subscribers?.length || 0} subscribers from R2`);
                        res.writeHead(200, corsHeaders);
                        res.end(JSON.stringify({
                            success: true,
                            subscribers: parsed.subscribers || [],
                            lastUpdated: parsed.lastUpdated || null
                        }));
                    } catch (e) {
                        console.error(`[Subscribers] Parse error: ${e.message}`);
                        res.writeHead(200, corsHeaders);
                        res.end(JSON.stringify({ success: true, subscribers: [], lastUpdated: null }));
                    }
                } else if (r2Res.statusCode === 404) {
                    // No subscribers file yet - return empty array
                    console.log(`[Subscribers] No subscribers file found for ${r2Key}`);
                    res.writeHead(200, corsHeaders);
                    res.end(JSON.stringify({ success: true, subscribers: [], lastUpdated: null }));
                } else {
                    console.error(`[Subscribers] R2 fetch failed: HTTP ${r2Res.statusCode}`);
                    res.writeHead(502, corsHeaders);
                    res.end(JSON.stringify({ error: `R2 returned HTTP ${r2Res.statusCode}` }));
                }
            });
        }).on('error', (err) => {
            console.error(`[Subscribers] R2 fetch error: ${err.message}`);
            res.writeHead(502, corsHeaders);
            res.end(JSON.stringify({ error: 'Failed to fetch from R2', message: err.message }));
        });
        return;
    }

    // ---- Email Schedule CRUD: Save/List/Delete email schedules in Firestore ----

    // POST /schedule/save — Create or update an email schedule
    if (req.url === '/schedule/save' && req.method === 'POST') {
        (async () => {
            try {
                const user = await verifyFirebaseToken(req);
                const body = await collectBody(req);
                const data = JSON.parse(body);

                const db = getFirestore();
                const scheduleId = data.scheduleId || crypto.randomUUID();
                const now = new Date().toISOString();

                const scheduleDoc = {
                    enabled: data.enabled !== false,
                    recipients: data.recipients || [],
                    reportType: data.reportType || 'comprehensive',
                    frequency: data.frequency || 'weekly',
                    dayOfWeek: data.dayOfWeek != null ? data.dayOfWeek : 1,
                    dayOfMonth: data.dayOfMonth || null,
                    time: data.time || '08:00',
                    timezone: data.timezone || 'America/New_York',
                    jurisdiction: data.jurisdiction || '',
                    state: data.state || '',
                    agency: data.agency || '',
                    updatedAt: now,
                    lastSentAt: data.lastSentAt || null
                };

                // Only set createdAt on new documents
                if (!data.scheduleId) {
                    scheduleDoc.createdAt = now;
                }

                // Calculate next run time
                scheduleDoc.nextRunAt = calculateNextRunAt(scheduleDoc);

                await db.collection('users').doc(user.uid)
                    .collection('emailSchedules').doc(scheduleId)
                    .set(scheduleDoc, { merge: true });

                // Invalidate schedule cache so cron picks up changes immediately
                scheduleCache = { data: null, loadedAt: 0 };

                console.log(`[Schedules] Saved schedule ${scheduleId} for user ${user.uid}`);
                res.writeHead(200, corsHeaders);
                res.end(JSON.stringify({ success: true, scheduleId, nextRunAt: scheduleDoc.nextRunAt }));
            } catch (err) {
                console.error(`[Schedules] Save error: ${err.message}`);
                const status = err.message.includes('Authorization') ? 401 : 500;
                res.writeHead(status, corsHeaders);
                res.end(JSON.stringify({ error: err.message }));
            }
        })();
        return;
    }

    // GET /schedule/list — List active schedules for the authenticated user
    if (req.url === '/schedule/list' && req.method === 'GET') {
        (async () => {
            try {
                const user = await verifyFirebaseToken(req);
                const db = getFirestore();

                const snapshot = await db.collection('users').doc(user.uid)
                    .collection('emailSchedules').get();

                const schedules = [];
                snapshot.forEach(doc => {
                    schedules.push({ id: doc.id, ...doc.data() });
                });

                console.log(`[Schedules] Listed ${schedules.length} schedules for user ${user.uid}`);
                res.writeHead(200, corsHeaders);
                res.end(JSON.stringify({ success: true, schedules }));
            } catch (err) {
                console.error(`[Schedules] List error: ${err.message}`);
                const status = err.message.includes('Authorization') ? 401 : 500;
                res.writeHead(status, corsHeaders);
                res.end(JSON.stringify({ error: err.message }));
            }
        })();
        return;
    }

    // DELETE /schedule/:id — Delete a specific schedule
    const scheduleDeleteMatch = req.url.match(/^\/schedule\/([a-zA-Z0-9_-]+)$/);
    if (scheduleDeleteMatch && req.method === 'DELETE') {
        (async () => {
            try {
                const user = await verifyFirebaseToken(req);
                const scheduleId = scheduleDeleteMatch[1];
                const db = getFirestore();

                await db.collection('users').doc(user.uid)
                    .collection('emailSchedules').doc(scheduleId)
                    .delete();

                // Invalidate schedule cache
                scheduleCache = { data: null, loadedAt: 0 };

                console.log(`[Schedules] Deleted schedule ${scheduleId} for user ${user.uid}`);
                res.writeHead(200, corsHeaders);
                res.end(JSON.stringify({ success: true }));
            } catch (err) {
                console.error(`[Schedules] Delete error: ${err.message}`);
                const status = err.message.includes('Authorization') ? 401 : 500;
                res.writeHead(status, corsHeaders);
                res.end(JSON.stringify({ error: err.message }));
            }
        })();
        return;
    }

    // ---- Forecast Availability Check: Check which forecast files exist for a jurisdiction ----
    // IMPORTANT: This route MUST come before the data fetch route below, because
    // /forecasts/check/:state/:jurisdiction would otherwise match the 3-segment
    // pattern /forecasts/:state/:jurisdiction/:roadType (with state="check").
    // GET /forecasts/check/:state/:jurisdiction (Nginx strips /api/ prefix)
    const forecastCheckMatch = req.url.match(/^\/forecasts\/check\/([a-z_]+)\/([a-z_]+)$/);
    if (forecastCheckMatch && req.method === 'GET') {
        const [, state, jurisdiction] = forecastCheckMatch;
        const roadTypes = ['county_roads', 'no_interstate', 'all_roads'];
        const prefix = `${state}/${jurisdiction}/forecasts_`;

        console.log(`[Forecasts] Availability check: ${state}/${jurisdiction}`);

        // Check each forecast file by making HEAD-like requests to CDN
        let completed = 0;
        const available = [];
        const results = {};

        roadTypes.forEach(rt => {
            const r2Key = `${state}/${jurisdiction}/forecasts_${rt}.json`;
            const r2Url = `https://data.aicreatesai.com/${r2Key}`;

            // Use HEAD-like approach: just check status, abort body download
            const checkReq = https.get(r2Url, (r2Res) => {
                r2Res.resume(); // Discard body
                results[rt] = r2Res.statusCode === 200;
                if (r2Res.statusCode === 200) {
                    available.push(`forecasts_${rt}.json`);
                }
                completed++;
                if (completed === roadTypes.length) {
                    res.writeHead(200, { ...corsHeaders, 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({
                        state,
                        jurisdiction,
                        available: available.length > 0,
                        fileCount: available.length,
                        files: available,
                        byRoadType: results
                    }));
                }
            });
            checkReq.on('error', () => {
                results[rt] = false;
                completed++;
                if (completed === roadTypes.length) {
                    res.writeHead(200, { ...corsHeaders, 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({
                        state,
                        jurisdiction,
                        available: available.length > 0,
                        fileCount: available.length,
                        files: available,
                        byRoadType: results
                    }));
                }
            });
        });
        return;
    }

    // ---- Forecast Data Proxy: Fetch forecast JSON from R2 CDN ----
    // GET /forecasts/:state/:jurisdiction/:roadType (Nginx strips /api/ prefix)
    // Example: /forecasts/colorado/douglas/county_roads
    const forecastMatch = req.url.match(/^\/forecasts\/([a-z_]+)\/([a-z_]+)\/([a-z_]+)$/);
    if (forecastMatch && req.method === 'GET') {
        const [, state, jurisdiction, roadType] = forecastMatch;
        const r2Key = `${state}/${jurisdiction}/forecasts_${roadType}.json`;
        const r2PublicUrl = `https://data.aicreatesai.com/${r2Key}`;

        // Check in-memory cache (5 minute TTL)
        const cacheKey = r2Key;
        const cached = forecastCache.get(cacheKey);
        if (cached && (Date.now() - cached.timestamp < 5 * 60 * 1000)) {
            console.log(`[Forecasts] Cache hit: ${r2Key}`);
            res.writeHead(200, { ...corsHeaders, 'Content-Type': 'application/json', 'X-Cache': 'HIT' });
            res.end(cached.data);
            return;
        }

        console.log(`[Forecasts] Fetching from R2: ${r2Key}`);

        https.get(r2PublicUrl, (r2Res) => {
            let data = '';
            r2Res.on('data', chunk => { data += chunk; });
            r2Res.on('end', () => {
                if (r2Res.statusCode === 200) {
                    // Cache the response
                    forecastCache.set(cacheKey, { data, timestamp: Date.now() });
                    res.writeHead(200, { ...corsHeaders, 'Content-Type': 'application/json', 'X-Cache': 'MISS' });
                    res.end(data);
                } else if (r2Res.statusCode === 404) {
                    res.writeHead(404, corsHeaders);
                    res.end(JSON.stringify({
                        error: 'Forecast not found',
                        state,
                        jurisdiction,
                        roadType,
                        message: `No forecast data available for ${jurisdiction} (${state}). Run the data pipeline to generate forecasts.`
                    }));
                } else {
                    res.writeHead(502, corsHeaders);
                    res.end(JSON.stringify({ error: `R2 returned HTTP ${r2Res.statusCode}` }));
                }
            });
        }).on('error', (err) => {
            console.error(`[Forecasts] R2 fetch error: ${err.message}`);
            res.writeHead(502, corsHeaders);
            res.end(JSON.stringify({ error: 'Failed to fetch forecast from R2', message: err.message }));
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

    // ==========================================================================
    // Stripe Payment Endpoints
    // ==========================================================================

    // ---- Stripe status check ----
    if (req.url === '/stripe/status' && req.method === 'GET') {
        res.writeHead(200, corsHeaders);
        res.end(JSON.stringify({
            configured: !!STRIPE_SECRET_KEY,
            hasWebhookSecret: !!STRIPE_WEBHOOK_SECRET,
            hasPrices: !!(STRIPE_PRICE_INDIVIDUAL_MONTHLY && STRIPE_PRICE_INDIVIDUAL_ANNUAL &&
                          STRIPE_PRICE_TEAM_MONTHLY && STRIPE_PRICE_TEAM_ANNUAL)
        }));
        return;
    }

    // ---- Create Stripe Checkout Session ----
    if (req.url === '/stripe/create-checkout-session' && req.method === 'POST') {
        if (!STRIPE_SECRET_KEY) {
            res.writeHead(503, corsHeaders);
            res.end(JSON.stringify({ error: 'Stripe not configured' }));
            return;
        }

        collectBody(req).then(async (body) => {
            let payload;
            try {
                payload = JSON.parse(body);
            } catch (e) {
                res.writeHead(400, corsHeaders);
                res.end(JSON.stringify({ error: 'Invalid JSON body' }));
                return;
            }

            const { plan, billingCycle, firebaseUid, email } = payload;

            if (!plan || !billingCycle || !firebaseUid || !email) {
                res.writeHead(400, corsHeaders);
                res.end(JSON.stringify({ error: 'Missing required fields: plan, billingCycle, firebaseUid, email' }));
                return;
            }

            const priceId = getStripePriceId(plan, billingCycle);
            if (!priceId) {
                res.writeHead(400, corsHeaders);
                res.end(JSON.stringify({ error: `Invalid plan/billing combination: ${plan}/${billingCycle}` }));
                return;
            }

            try {
                const stripeClient = getStripe();

                // Check if user already has a Stripe customer ID in Firestore
                let customerId = null;
                try {
                    const db = getFirestore();
                    const userDoc = await db.collection('users').doc(firebaseUid).get();
                    if (userDoc.exists && userDoc.data().stripeCustomerId) {
                        customerId = userDoc.data().stripeCustomerId;
                    }
                } catch (dbErr) {
                    console.warn('[Stripe] Could not check Firestore for existing customer:', dbErr.message);
                }

                // Create or retrieve Stripe customer
                if (!customerId) {
                    const customer = await stripeClient.customers.create({
                        email: email,
                        metadata: { firebaseUid: firebaseUid }
                    });
                    customerId = customer.id;

                    // Save customer ID to Firestore
                    try {
                        const db = getFirestore();
                        await db.collection('users').doc(firebaseUid).update({
                            stripeCustomerId: customerId
                        });
                    } catch (dbErr) {
                        console.warn('[Stripe] Could not save customer ID to Firestore:', dbErr.message);
                    }
                }

                // Create Checkout Session
                const sessionParams = {
                    customer: customerId,
                    client_reference_id: firebaseUid,
                    mode: 'subscription',
                    line_items: [{ price: priceId, quantity: 1 }],
                    success_url: `${APP_URL}/pricing.html?checkout=success&session_id={CHECKOUT_SESSION_ID}`,
                    cancel_url: `${APP_URL}/pricing.html?checkout=cancelled`,
                    metadata: {
                        firebaseUid: firebaseUid,
                        plan: plan,
                        billingCycle: billingCycle
                    },
                    subscription_data: {
                        metadata: {
                            firebaseUid: firebaseUid,
                            plan: plan
                        }
                    },
                    allow_promotion_codes: true
                };

                const session = await stripeClient.checkout.sessions.create(sessionParams);

                console.log(`[Stripe] Checkout session created for ${email} (${plan}/${billingCycle})`);
                res.writeHead(200, corsHeaders);
                res.end(JSON.stringify({ url: session.url, sessionId: session.id }));

            } catch (err) {
                console.error(`[Stripe] Checkout session error: ${err.message}`);
                res.writeHead(500, corsHeaders);
                res.end(JSON.stringify({ error: 'Failed to create checkout session', message: err.message }));
            }
        });
        return;
    }

    // ---- Stripe Webhook ----
    if (req.url === '/stripe/webhook' && req.method === 'POST') {
        if (!STRIPE_SECRET_KEY || !STRIPE_WEBHOOK_SECRET) {
            console.error('[Stripe Webhook] Not configured — STRIPE_SECRET_KEY:', !!STRIPE_SECRET_KEY, 'STRIPE_WEBHOOK_SECRET:', !!STRIPE_WEBHOOK_SECRET);
            res.writeHead(503, corsHeaders);
            res.end(JSON.stringify({ error: 'Stripe webhook not configured' }));
            return;
        }

        // Collect raw body for signature verification
        const chunks = [];
        req.on('data', chunk => chunks.push(chunk));
        req.on('end', async () => {
            const rawBody = Buffer.concat(chunks);
            const sig = req.headers['stripe-signature'];

            if (!sig) {
                console.error('[Stripe Webhook] Missing stripe-signature header');
                res.writeHead(400, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Missing stripe-signature header' }));
                return;
            }

            let event;
            try {
                const stripeClient = getStripe();
                event = stripeClient.webhooks.constructEvent(rawBody, sig, STRIPE_WEBHOOK_SECRET);
            } catch (err) {
                console.error(`[Stripe Webhook] Signature verification failed: ${err.message}`);
                console.error(`[Stripe Webhook] Sig header: ${sig ? sig.substring(0, 30) + '...' : 'MISSING'}`);
                console.error(`[Stripe Webhook] Raw body length: ${rawBody.length} bytes`);
                res.writeHead(400, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Webhook signature verification failed' }));
                return;
            }

            console.log(`[Stripe Webhook] Received event: ${event.type} (id: ${event.id})`);

            // Initialize shared dependencies
            let db, admin;
            try {
                db = getFirestore();
                admin = require('firebase-admin');
            } catch (initErr) {
                console.error(`[Stripe Webhook] Failed to initialize Firebase: ${initErr.message}`);
                console.error(`[Stripe Webhook] Stack: ${initErr.stack}`);
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Webhook processing failed', detail: 'Firebase initialization error' }));
                return;
            }

            try {
                switch (event.type) {
                    case 'checkout.session.completed': {
                        const session = event.data.object;
                        const firebaseUid = session.metadata?.firebaseUid;
                        if (!firebaseUid) {
                            console.warn('[Stripe Webhook] No firebaseUid in session metadata — skipping. Session ID:', session.id);
                            break;
                        }

                        const plan = session.metadata?.plan || 'individual';
                        const billingCycle = session.metadata?.billingCycle || 'monthly';
                        const queryLimit = PLAN_QUERY_LIMITS[plan] || 100;
                        const seats = PLAN_SEATS[plan] || 1;

                        console.log(`[Stripe Webhook] checkout.session.completed — uid: ${firebaseUid}, plan: ${plan}, cycle: ${billingCycle}, customer: ${session.customer}, subscription: ${session.subscription}`);

                        // Retrieve full subscription to get period details
                        const stripeClient = getStripe();
                        let currentPeriodEnd = null;
                        let cancelAtPeriodEnd = false;
                        let trialEnd = null;
                        let subStatus = 'active';

                        if (session.subscription) {
                            try {
                                const sub = await stripeClient.subscriptions.retrieve(session.subscription);
                                currentPeriodEnd = sub.current_period_end
                                    ? admin.firestore.Timestamp.fromMillis(sub.current_period_end * 1000)
                                    : null;
                                cancelAtPeriodEnd = sub.cancel_at_period_end || false;
                                trialEnd = sub.trial_end
                                    ? admin.firestore.Timestamp.fromMillis(sub.trial_end * 1000)
                                    : null;
                                subStatus = sub.status === 'trialing' ? 'trialing' : 'active';
                                console.log(`[Stripe Webhook] Subscription ${session.subscription} status: ${sub.status}, period_end: ${sub.current_period_end}`);
                            } catch (subErr) {
                                console.error(`[Stripe Webhook] Could not retrieve subscription ${session.subscription}: ${subErr.message}`);
                            }
                        }

                        const updateData = {
                            plan: plan,
                            billingCycle: billingCycle,
                            subscriptionStatus: subStatus,
                            stripeCustomerId: session.customer,
                            stripeSubscriptionId: session.subscription,
                            subscribedAt: admin.firestore.Timestamp.now(),
                            seats: seats,
                            'ai.queriesLimit': queryLimit
                        };

                        if (currentPeriodEnd) updateData.currentPeriodEnd = currentPeriodEnd;
                        if (trialEnd) updateData.trialEnd = trialEnd;
                        updateData.cancelAtPeriodEnd = cancelAtPeriodEnd;

                        // Use set+merge so it works even if user doc doesn't exist yet
                        await db.collection('users').doc(firebaseUid).set(updateData, { merge: true });

                        console.log(`[Stripe Webhook] User ${firebaseUid} subscribed to ${plan}/${billingCycle} (status: ${subStatus})`);
                        break;
                    }

                    case 'customer.subscription.updated': {
                        const subscription = event.data.object;
                        const firebaseUid = subscription.metadata?.firebaseUid;
                        if (!firebaseUid) {
                            console.warn(`[Stripe Webhook] No firebaseUid in subscription.updated metadata — skipping. Sub ID: ${subscription.id}`);
                            break;
                        }

                        const priceId = subscription.items?.data?.[0]?.price?.id;
                        const planInfo = getPlanFromPriceId(priceId);
                        const status = subscription.status; // active, trialing, past_due, canceled, unpaid

                        console.log(`[Stripe Webhook] subscription.updated — uid: ${firebaseUid}, status: ${status}, priceId: ${priceId}, cancelAtPeriodEnd: ${subscription.cancel_at_period_end}`);

                        const updates = {
                            subscriptionStatus: status === 'active' ? 'active' :
                                               status === 'trialing' ? 'trialing' :
                                               status === 'past_due' ? 'past_due' :
                                               status === 'canceled' ? 'canceled' : status,
                            cancelAtPeriodEnd: subscription.cancel_at_period_end || false
                        };

                        // Update current period end
                        if (subscription.current_period_end) {
                            updates.currentPeriodEnd = admin.firestore.Timestamp.fromMillis(
                                subscription.current_period_end * 1000
                            );
                        }

                        // Update trial end if applicable
                        if (subscription.trial_end) {
                            updates.trialEnd = admin.firestore.Timestamp.fromMillis(
                                subscription.trial_end * 1000
                            );
                        }

                        if (planInfo) {
                            updates.plan = planInfo.plan;
                            updates.billingCycle = planInfo.billingCycle;
                            updates.seats = PLAN_SEATS[planInfo.plan] || 1;
                            updates['ai.queriesLimit'] = PLAN_QUERY_LIMITS[planInfo.plan] || 100;
                        }

                        // Use set+merge so it works even if user doc doesn't exist yet
                        await db.collection('users').doc(firebaseUid).set(updates, { merge: true });
                        console.log(`[Stripe Webhook] Subscription updated for ${firebaseUid}: ${JSON.stringify(updates)}`);
                        break;
                    }

                    case 'customer.subscription.deleted': {
                        const subscription = event.data.object;
                        const firebaseUid = subscription.metadata?.firebaseUid;
                        if (!firebaseUid) {
                            console.warn(`[Stripe Webhook] No firebaseUid in subscription.deleted metadata — skipping. Sub ID: ${subscription.id}`);
                            break;
                        }

                        console.log(`[Stripe Webhook] subscription.deleted — uid: ${firebaseUid}, sub: ${subscription.id}`);

                        const cancelUpdates = {
                            subscriptionStatus: 'canceled',
                            cancelAtPeriodEnd: true,
                            cancelledAt: admin.firestore.Timestamp.now()
                        };

                        // Store when access actually ends
                        if (subscription.current_period_end) {
                            cancelUpdates.currentPeriodEnd = admin.firestore.Timestamp.fromMillis(
                                subscription.current_period_end * 1000
                            );
                        }

                        // Use set+merge so it works even if user doc doesn't exist yet
                        await db.collection('users').doc(firebaseUid).set(cancelUpdates, { merge: true });

                        console.log(`[Stripe Webhook] Subscription canceled for ${firebaseUid}`);
                        break;
                    }

                    case 'customer.subscription.trial_will_end': {
                        const subscription = event.data.object;
                        const customerId = subscription.customer;
                        const trialEndTs = subscription.trial_end;

                        // Find user by stripeCustomerId
                        const trialUsersSnap = await db.collection('users')
                            .where('stripeCustomerId', '==', customerId)
                            .limit(1)
                            .get();

                        if (!trialUsersSnap.empty) {
                            const trialUserDoc = trialUsersSnap.docs[0];
                            const trialUserData = trialUserDoc.data();

                            // Store when the trial-ending notification was sent
                            await trialUserDoc.ref.update({
                                trialEndingNotifiedAt: admin.firestore.Timestamp.now()
                            });

                            console.log(`[Stripe Webhook] Trial ending soon for customer ${customerId}`);

                            // Send trial ending notification email via Brevo
                            if (BREVO_API_KEY && NOTIFICATION_FROM_EMAIL && trialUserData.email) {
                                try {
                                    const trialEndDate = trialEndTs
                                        ? new Date(trialEndTs * 1000).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
                                        : 'soon';
                                    const planName = (trialUserData.plan || 'subscription').charAt(0).toUpperCase() + (trialUserData.plan || 'subscription').slice(1);
                                    await sendViaBrevoApi(
                                        trialUserData.email,
                                        'CRASH LENS - Your Trial Is Ending Soon',
                                        `<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
                                            <h2 style="color:#1e3a5f;">Your Trial Ends ${trialEndDate}</h2>
                                            <p>Hi${trialUserData.displayName ? ' ' + trialUserData.displayName : ''},</p>
                                            <p>Your free trial of the <strong>${planName}</strong> plan is ending on <strong>${trialEndDate}</strong>.</p>
                                            <p>To continue using CRASH LENS without interruption, please add a payment method before your trial expires.</p>
                                            <p>If you don't add a payment method, your subscription will be canceled and you'll lose access to premium features including:</p>
                                            <ul style="color:#374151;line-height:1.8;">
                                                <li>AI-powered crash analysis</li>
                                                <li>Safety countermeasure recommendations</li>
                                                <li>Grant application assistance</li>
                                                <li>Advanced reporting tools</li>
                                            </ul>
                                            <p style="margin:24px 0;">
                                                <a href="${APP_URL}/app/" style="background:#1e40af;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;">Add Payment Method</a>
                                            </p>
                                            <p style="color:#6b7280;font-size:0.875rem;">If you have any questions, please contact us at support@aicreatesai.com</p>
                                            <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;">
                                            <p style="color:#9ca3af;font-size:0.75rem;">CRASH LENS - Crash Analysis Tools for Transportation Agencies</p>
                                        </div>`,
                                        `Your CRASH LENS ${planName} trial ends on ${trialEndDate}. Add a payment method at ${APP_URL}/app/ to continue using the service.`
                                    );
                                    console.log(`[Stripe Webhook] Trial ending email sent to ${trialUserData.email}`);
                                } catch (emailErr) {
                                    console.error(`[Stripe Webhook] Failed to send trial ending email: ${emailErr.message}`);
                                }
                            }
                        } else {
                            console.warn(`[Stripe Webhook] No user found for customer ${customerId} (trial_will_end)`);
                        }
                        break;
                    }

                    case 'invoice.payment_failed': {
                        const invoice = event.data.object;
                        const customerId = invoice.customer;

                        console.log(`[Stripe Webhook] invoice.payment_failed — customer: ${customerId}, invoice: ${invoice.id}`);

                        // Find user by stripeCustomerId
                        const usersSnap = await db.collection('users')
                            .where('stripeCustomerId', '==', customerId)
                            .limit(1)
                            .get();

                        if (usersSnap.empty) {
                            console.warn(`[Stripe Webhook] No user found for stripeCustomerId: ${customerId}`);
                            break;
                        }

                        const userDoc = usersSnap.docs[0];
                        const userData = userDoc.data();
                        await userDoc.ref.update({
                            subscriptionStatus: 'past_due',
                            lastPaymentFailedAt: admin.firestore.Timestamp.now()
                        });
                        console.log(`[Stripe Webhook] Payment failed — marked user ${userDoc.id} as past_due`);

                        // Send payment failure notification email via Brevo
                        if (BREVO_API_KEY && NOTIFICATION_FROM_EMAIL && userData.email) {
                            try {
                                const planName = (userData.plan || 'subscription').charAt(0).toUpperCase() + (userData.plan || 'subscription').slice(1);
                                await sendViaBrevoApi(
                                    userData.email,
                                    'CRASH LENS - Payment Failed',
                                    `<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
                                        <h2 style="color:#1e3a5f;">Payment Issue</h2>
                                        <p>Hi${userData.displayName ? ' ' + userData.displayName : ''},</p>
                                        <p>We were unable to process your payment for your <strong>${planName}</strong> plan.</p>
                                        <p>Please update your payment method to avoid any disruption to your service.</p>
                                        <p style="margin:24px 0;">
                                            <a href="${APP_URL}/app/" style="background:#1e40af;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;">Update Payment Method</a>
                                        </p>
                                        <p style="color:#6b7280;font-size:0.875rem;">If you have any questions, please contact us at support@aicreatesai.com</p>
                                        <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;">
                                        <p style="color:#9ca3af;font-size:0.75rem;">CRASH LENS - Crash Analysis Tools for Transportation Agencies</p>
                                    </div>`,
                                    `Payment failed for your CRASH LENS ${planName} plan. Please update your payment method at ${APP_URL}/app/`
                                );
                                console.log(`[Stripe Webhook] Payment failure email sent to ${userData.email}`);
                            } catch (emailErr) {
                                console.error(`[Stripe Webhook] Failed to send payment failure email: ${emailErr.message}`);
                            }
                        }
                        break;
                    }

                    default:
                        console.log(`[Stripe Webhook] Unhandled event type: ${event.type}`);
                }

                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ received: true }));

            } catch (err) {
                console.error(`[Stripe Webhook] Processing error for event ${event.type} (${event.id}):`);
                console.error(`[Stripe Webhook] Error message: ${err.message}`);
                console.error(`[Stripe Webhook] Error code: ${err.code || 'N/A'}`);
                console.error(`[Stripe Webhook] Stack trace: ${err.stack}`);
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Webhook processing failed', detail: err.message }));
            }
        });
        return;
    }

    // ---- Create Stripe Customer Portal Session ----
    if (req.url === '/stripe/create-portal-session' && req.method === 'POST') {
        if (!STRIPE_SECRET_KEY) {
            res.writeHead(503, corsHeaders);
            res.end(JSON.stringify({ error: 'Stripe not configured' }));
            return;
        }

        collectBody(req).then(async (body) => {
            let payload;
            try {
                payload = JSON.parse(body);
            } catch (e) {
                res.writeHead(400, corsHeaders);
                res.end(JSON.stringify({ error: 'Invalid JSON body' }));
                return;
            }

            const { stripeCustomerId } = payload;
            if (!stripeCustomerId) {
                res.writeHead(400, corsHeaders);
                res.end(JSON.stringify({ error: 'Missing stripeCustomerId' }));
                return;
            }

            try {
                const stripeClient = getStripe();
                const session = await stripeClient.billingPortal.sessions.create({
                    customer: stripeCustomerId,
                    return_url: `${APP_URL}/app/`
                });

                console.log(`[Stripe] Portal session created for customer ${stripeCustomerId}`);
                res.writeHead(200, corsHeaders);
                res.end(JSON.stringify({ url: session.url }));

            } catch (err) {
                console.error(`[Stripe] Portal session error: ${err.message}`);
                res.writeHead(500, corsHeaders);
                res.end(JSON.stringify({ error: 'Failed to create portal session', message: err.message }));
            }
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
    if (CF_ACCOUNT_ID && CF_R2_ACCESS_KEY_ID && CF_R2_SECRET_ACCESS_KEY) {
        console.log(`[R2] Upload configured (bucket: ${R2_BUCKET_NAME})`);
    } else {
        console.warn('[R2] WARNING: R2 credentials not set - /r2 endpoints will return 503');
    }
    if (R2_WORKER_URL && R2_WORKER_SECRET) {
        console.log(`[R2 Worker] Proxy configured (URL: ${R2_WORKER_URL})`);
    } else {
        console.warn('[R2 Worker] WARNING: R2_WORKER_URL or R2_WORKER_SECRET not set - /r2/worker-* endpoints will return 503');
    }
    if (STRIPE_SECRET_KEY) {
        console.log(`[Stripe] Payment processing configured`);
        if (STRIPE_WEBHOOK_SECRET) console.log(`[Stripe] Webhook verification configured`);
        if (STRIPE_PRICE_INDIVIDUAL_MONTHLY) console.log(`[Stripe] Price IDs configured`);
    } else {
        console.warn('[Stripe] WARNING: STRIPE_SECRET_KEY not set - /stripe endpoints will return 503');
    }

    // Start email schedule cron if Firebase and Brevo are configured
    if (process.env.FIREBASE_SERVICE_ACCOUNT && BREVO_API_KEY) {
        startEmailScheduler();
    } else {
        console.warn('[Scheduler] WARNING: FIREBASE_SERVICE_ACCOUNT or BREVO_API_KEY not set - email scheduler disabled');
    }
});

// =============================================================================
// Email Schedule Cron Scheduler
// =============================================================================

async function loadDueSchedules() {
    const now = Date.now();

    // Return cached data if still fresh
    if (scheduleCache.data && (now - scheduleCache.loadedAt) < SCHEDULE_CACHE_TTL) {
        return scheduleCache.data;
    }

    try {
        const db = getFirestore();
        const nowISO = new Date().toISOString();

        // Query all users' emailSchedules subcollections using collectionGroup
        const snapshot = await db.collectionGroup('emailSchedules')
            .where('enabled', '==', true)
            .where('nextRunAt', '<=', nowISO)
            .get();

        const schedules = [];
        snapshot.forEach(doc => {
            schedules.push({
                id: doc.id,
                uid: doc.ref.parent.parent.id, // users/{uid}/emailSchedules/{id}
                ...doc.data()
            });
        });

        scheduleCache = { data: schedules, loadedAt: now };
        return schedules;
    } catch (err) {
        console.error(`[Scheduler] Failed to load schedules: ${err.message}`);
        return [];
    }
}

async function processScheduledEmails() {
    try {
        const dueSchedules = await loadDueSchedules();
        if (dueSchedules.length === 0) return;

        console.log(`[Scheduler] Processing ${dueSchedules.length} due schedule(s)`);
        const db = getFirestore();

        for (const schedule of dueSchedules) {
            try {
                const recipients = schedule.recipients || [];
                if (recipients.length === 0) {
                    console.warn(`[Scheduler] Schedule ${schedule.id} has no recipients, skipping`);
                    continue;
                }

                const subject = `CRASH LENS ${schedule.frequency || 'Scheduled'} Report — ${schedule.agency || schedule.jurisdiction || 'Crash Analysis'}`;
                const htmlBody = buildScheduledEmailHtml(schedule);
                const textBody = `Your scheduled CRASH LENS report is ready. Visit ${APP_URL}/app/ to view the full report.`;

                // Send to each recipient individually
                for (const recipient of recipients) {
                    try {
                        await sendViaBrevoApi(recipient, subject, htmlBody, textBody, null, {
                            tag: 'scheduled-report',
                            includeListHeaders: true
                        });
                        console.log(`[Scheduler] Sent to ${recipient} (schedule ${schedule.id})`);
                    } catch (sendErr) {
                        console.error(`[Scheduler] Failed to send to ${recipient}: ${sendErr.message}`);
                    }
                }

                // Update lastSentAt and calculate next run
                const now = new Date().toISOString();
                const nextRunAt = calculateNextRunAt(schedule);

                await db.collection('users').doc(schedule.uid)
                    .collection('emailSchedules').doc(schedule.id)
                    .update({ lastSentAt: now, nextRunAt });

                console.log(`[Scheduler] Schedule ${schedule.id} processed, next run: ${nextRunAt}`);
            } catch (scheduleErr) {
                console.error(`[Scheduler] Error processing schedule ${schedule.id}: ${scheduleErr.message}`);
            }
        }

        // Invalidate cache after processing so next check gets fresh data
        scheduleCache = { data: null, loadedAt: 0 };
    } catch (err) {
        console.error(`[Scheduler] Error in processScheduledEmails: ${err.message}`);
    }
}

function startEmailScheduler() {
    const cron = require('node-cron');

    // Run every minute to check for due schedules
    cron.schedule('* * * * *', () => {
        processScheduledEmails();
    });

    console.log('[Scheduler] Email scheduler started (checking every minute)');
}
