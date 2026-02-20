# ============================================================
# CRASH LENS - Coolify/Docker Deployment
# Multi-process container: Nginx (static files) + Node.js (API proxy)
# ============================================================

FROM node:18-alpine AS base

# Install nginx, supervisord, and curl (needed for Coolify healthcheck)
RUN apk add --no-cache nginx supervisor curl

# ------------------------------------------------------------
# Copy application files
# ------------------------------------------------------------

# Copy static site files to Nginx html directory
# Copy all root-level HTML files (index, features, pricing, resources, contact, 404, etc.)
COPY *.html /usr/share/nginx/html/
COPY config.json /usr/share/nginx/html/
COPY manifest.json /usr/share/nginx/html/

# Copy app directory (main application)
COPY app/ /usr/share/nginx/html/app/

# Copy config directory (settings.json, api-keys)
COPY config/ /usr/share/nginx/html/config/

# Copy data directory
COPY data/ /usr/share/nginx/html/data/

# Copy states directory
COPY states/ /usr/share/nginx/html/states/

# Copy assets directory
COPY assets/ /usr/share/nginx/html/assets/

# Copy docs directory (if needed for the app)
COPY docs/ /usr/share/nginx/html/docs/

# Copy any login directory if it exists
COPY logi[n]/ /usr/share/nginx/html/login/

# Copy Firebase auth action handler (for email verification/password reset links)
COPY __/ /usr/share/nginx/html/__/

# Copy entrypoint script (generates api-keys.json from env vars)
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ------------------------------------------------------------
# Configure Nginx
# ------------------------------------------------------------

# Replace the ENTIRE nginx config (not just a server block include)
COPY nginx.conf /etc/nginx/nginx.conf

# Ensure nginx directories exist
RUN mkdir -p /var/log/nginx /var/lib/nginx/tmp /run/nginx

# ------------------------------------------------------------
# Configure Node.js API proxy
# ------------------------------------------------------------

# Copy proxy server
COPY server/ /app/server/

# ------------------------------------------------------------
# Configure supervisord
# ------------------------------------------------------------

COPY supervisord.conf /etc/supervisord.conf

# ------------------------------------------------------------
# Environment variables (set in Coolify Dashboard)
# ------------------------------------------------------------

# Client-side API keys (injected into config/api-keys.json by entrypoint.sh)
# MAPBOX_ACCESS_TOKEN       - Mapbox token for satellite tiles & geocoding
# GOOGLE_MAPS_API_KEY       - Google Maps API key for Street View
# MAPILLARY_ACCESS_TOKEN    - Mapillary token for street-level imagery
# FIREBASE_API_KEY          - Firebase API key
# FIREBASE_AUTH_DOMAIN      - Firebase auth domain (e.g. myapp.firebaseapp.com)
# FIREBASE_PROJECT_ID       - Firebase project ID
# FIREBASE_STORAGE_BUCKET   - Firebase storage bucket
# FIREBASE_MESSAGING_SENDER_ID - Firebase messaging sender ID
# FIREBASE_APP_ID           - Firebase app ID
#
# Server-side secrets
# BREVO_API_KEY         - Brevo v3 API key (starts with xkeysib-)
# BREVO_SMTP_LOGIN      - Brevo SMTP login email
# BREVO_SMTP_PASSWORD   - Brevo SMTP password
# NOTIFICATION_FROM_EMAIL - Verified Brevo sender address
# QDRANT_ENDPOINT       - Qdrant Cloud URL
# QDRANT_API_KEY        - Qdrant Cloud API key

# ------------------------------------------------------------
# Expose port and start
# ------------------------------------------------------------

# Expose port 80 (Coolify will map this automatically)
EXPOSE 80

# Health check using curl against the dedicated /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

# Start via entrypoint (injects env vars into config, then launches supervisord)
ENTRYPOINT ["/entrypoint.sh"]
