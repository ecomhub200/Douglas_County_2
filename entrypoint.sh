#!/bin/sh
# ============================================================
# CRASH LENS - Docker Entrypoint
# Injects Coolify environment variables into client-side config
# ============================================================
# The static HTML app reads API keys from config/api-keys.json.
# This script generates that file from environment variables
# set in the Coolify dashboard, bridging server-side env vars
# to client-side configuration.
# ============================================================

API_KEYS_DIR="/usr/share/nginx/html/config"
API_KEYS_FILE="${API_KEYS_DIR}/api-keys.json"

# Check if ANY client-side API key env var is set
HAS_CLIENT_KEYS=""
[ -n "$MAPBOX_ACCESS_TOKEN" ] && HAS_CLIENT_KEYS="1"
[ -n "$GOOGLE_MAPS_API_KEY" ] && HAS_CLIENT_KEYS="1"
[ -n "$MAPILLARY_ACCESS_TOKEN" ] && HAS_CLIENT_KEYS="1"
[ -n "$FIREBASE_API_KEY" ] && HAS_CLIENT_KEYS="1"
[ -n "$STRIPE_PUBLISHABLE_KEY" ] && HAS_CLIENT_KEYS="1"
[ -n "$R2_WORKER_URL" ] && HAS_CLIENT_KEYS="1"

if [ -n "$HAS_CLIENT_KEYS" ]; then
    echo "[Entrypoint] Generating api-keys.json from environment variables..."

    mkdir -p "$API_KEYS_DIR"

    # Use jq for safe JSON generation (handles special characters in tokens)
    jq -n \
      --arg mb "${MAPBOX_ACCESS_TOKEN:-}" \
      --arg gm "${GOOGLE_MAPS_API_KEY:-}" \
      --arg ml "${MAPILLARY_ACCESS_TOKEN:-}" \
      --arg fk "${FIREBASE_API_KEY:-}" \
      --arg fd "${FIREBASE_AUTH_DOMAIN:-}" \
      --arg fp "${FIREBASE_PROJECT_ID:-}" \
      --arg fs "${FIREBASE_STORAGE_BUCKET:-}" \
      --arg fm "${FIREBASE_MESSAGING_SENDER_ID:-}" \
      --arg fa "${FIREBASE_APP_ID:-}" \
      --arg sk "${STRIPE_PUBLISHABLE_KEY:-}" \
      --arg rw "${R2_WORKER_URL:-}" \
      --arg rp "${R2_PUBLIC_URL:-https://data.aicreatesai.com}" \
      '{
        mapbox:    { accessToken: $mb },
        google:    { mapsApiKey: $gm },
        mapillary: { accessToken: $ml },
        firebase:  { apiKey: $fk, authDomain: $fd, projectId: $fp, storageBucket: $fs, messagingSenderId: $fm, appId: $fa },
        stripe:    { publishableKey: $sk },
        r2Worker:  { workerUrl: $rw, publicUrl: $rp }
      }' > "$API_KEYS_FILE"

    echo "[Entrypoint] api-keys.json written successfully"
    # Log which keys were injected (lengths only - never log actual values)
    [ -n "$MAPBOX_ACCESS_TOKEN" ]        && echo "[Entrypoint]   - MAPBOX_ACCESS_TOKEN: set (${#MAPBOX_ACCESS_TOKEN} chars)"
    [ -n "$GOOGLE_MAPS_API_KEY" ]        && echo "[Entrypoint]   - GOOGLE_MAPS_API_KEY: set (${#GOOGLE_MAPS_API_KEY} chars)"
    [ -n "$MAPILLARY_ACCESS_TOKEN" ]     && echo "[Entrypoint]   - MAPILLARY_ACCESS_TOKEN: set (${#MAPILLARY_ACCESS_TOKEN} chars)"
    [ -n "$FIREBASE_API_KEY" ]           && echo "[Entrypoint]   - FIREBASE_API_KEY: set (${#FIREBASE_API_KEY} chars)"
    [ -n "$FIREBASE_AUTH_DOMAIN" ]       && echo "[Entrypoint]   - FIREBASE_AUTH_DOMAIN: set (${#FIREBASE_AUTH_DOMAIN} chars)"
    [ -n "$FIREBASE_PROJECT_ID" ]        && echo "[Entrypoint]   - FIREBASE_PROJECT_ID: set (${#FIREBASE_PROJECT_ID} chars)"
    [ -n "$FIREBASE_STORAGE_BUCKET" ]    && echo "[Entrypoint]   - FIREBASE_STORAGE_BUCKET: set (${#FIREBASE_STORAGE_BUCKET} chars)"
    [ -n "$FIREBASE_MESSAGING_SENDER_ID" ] && echo "[Entrypoint]   - FIREBASE_MESSAGING_SENDER_ID: set (${#FIREBASE_MESSAGING_SENDER_ID} chars)"
    [ -n "$FIREBASE_APP_ID" ]            && echo "[Entrypoint]   - FIREBASE_APP_ID: set (${#FIREBASE_APP_ID} chars)"
    [ -n "$STRIPE_PUBLISHABLE_KEY" ]     && echo "[Entrypoint]   - STRIPE_PUBLISHABLE_KEY: set (${#STRIPE_PUBLISHABLE_KEY} chars)"
    [ -n "$R2_WORKER_URL" ]              && echo "[Entrypoint]   - R2_WORKER_URL: set (${#R2_WORKER_URL} chars)"
    [ -n "$R2_PUBLIC_URL" ]              && echo "[Entrypoint]   - R2_PUBLIC_URL: set (${#R2_PUBLIC_URL} chars)"
else
    echo "[Entrypoint] No API key env vars detected, skipping api-keys.json generation"
fi

# Server-side env vars used by Node.js proxy (set in Coolify Dashboard):
# QDRANT_ENDPOINT, QDRANT_API_KEY          - Qdrant Cloud
# BREVO_API_KEY, NOTIFICATION_FROM_EMAIL   - Email notifications
# CF_ACCOUNT_ID, CF_R2_ACCESS_KEY_ID,      - Cloudflare R2 (geocoded data upload)
# CF_R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME
# R2_WORKER_SECRET                         - R2 Worker upload secret (X-Upload-Secret header, server-side only)

# Hand off to supervisord (Nginx + Node.js proxy)
exec /usr/bin/supervisord -c /etc/supervisord.conf
