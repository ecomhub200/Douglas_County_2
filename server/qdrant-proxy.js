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
    if (STRIPE_SECRET_KEY) {
        console.log(`[Stripe] Payment processing configured`);
        if (STRIPE_WEBHOOK_SECRET) console.log(`[Stripe] Webhook verification configured`);
        if (STRIPE_PRICE_INDIVIDUAL_MONTHLY) console.log(`[Stripe] Price IDs configured`);
    } else {
        console.warn('[Stripe] WARNING: STRIPE_SECRET_KEY not set - /stripe endpoints will return 503');
    }
});
