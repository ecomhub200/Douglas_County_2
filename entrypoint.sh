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

if [ -n "$HAS_CLIENT_KEYS" ]; then
    echo "[Entrypoint] Generating api-keys.json from environment variables..."

    mkdir -p "$API_KEYS_DIR"

    # Resolve env vars (default to empty string if unset)
    MAPBOX_TOKEN="${MAPBOX_ACCESS_TOKEN:-}"
    GOOGLE_KEY="${GOOGLE_MAPS_API_KEY:-}"
    MAPILLARY_TOKEN="${MAPILLARY_ACCESS_TOKEN:-}"

    FB_API_KEY="${FIREBASE_API_KEY:-}"
    FB_AUTH_DOMAIN="${FIREBASE_AUTH_DOMAIN:-}"
    FB_PROJECT_ID="${FIREBASE_PROJECT_ID:-}"
    FB_STORAGE_BUCKET="${FIREBASE_STORAGE_BUCKET:-}"
    FB_MESSAGING_SENDER_ID="${FIREBASE_MESSAGING_SENDER_ID:-}"
    FB_APP_ID="${FIREBASE_APP_ID:-}"

    cat > "$API_KEYS_FILE" <<JSONEOF
{
  "mapbox": {
    "accessToken": "${MAPBOX_TOKEN}"
  },
  "google": {
    "mapsApiKey": "${GOOGLE_KEY}"
  },
  "mapillary": {
    "accessToken": "${MAPILLARY_TOKEN}"
  },
  "firebase": {
    "apiKey": "${FB_API_KEY}",
    "authDomain": "${FB_AUTH_DOMAIN}",
    "projectId": "${FB_PROJECT_ID}",
    "storageBucket": "${FB_STORAGE_BUCKET}",
    "messagingSenderId": "${FB_MESSAGING_SENDER_ID}",
    "appId": "${FB_APP_ID}"
  }
}
JSONEOF

    echo "[Entrypoint] api-keys.json written successfully"
    # Log which keys were injected (without revealing values)
    [ -n "$MAPBOX_TOKEN" ] && echo "[Entrypoint]   - MAPBOX_ACCESS_TOKEN: set (${#MAPBOX_TOKEN} chars)"
    [ -n "$GOOGLE_KEY" ] && echo "[Entrypoint]   - GOOGLE_MAPS_API_KEY: set (${#GOOGLE_KEY} chars)"
    [ -n "$MAPILLARY_TOKEN" ] && echo "[Entrypoint]   - MAPILLARY_ACCESS_TOKEN: set (${#MAPILLARY_TOKEN} chars)"
    [ -n "$FB_API_KEY" ] && echo "[Entrypoint]   - FIREBASE_API_KEY: set (${#FB_API_KEY} chars)"
    [ -n "$FB_AUTH_DOMAIN" ] && echo "[Entrypoint]   - FIREBASE_AUTH_DOMAIN: ${FB_AUTH_DOMAIN}"
    [ -n "$FB_PROJECT_ID" ] && echo "[Entrypoint]   - FIREBASE_PROJECT_ID: ${FB_PROJECT_ID}"
    [ -n "$FB_STORAGE_BUCKET" ] && echo "[Entrypoint]   - FIREBASE_STORAGE_BUCKET: ${FB_STORAGE_BUCKET}"
    [ -n "$FB_MESSAGING_SENDER_ID" ] && echo "[Entrypoint]   - FIREBASE_MESSAGING_SENDER_ID: set"
    [ -n "$FB_APP_ID" ] && echo "[Entrypoint]   - FIREBASE_APP_ID: set (${#FB_APP_ID} chars)"
else
    echo "[Entrypoint] No API key env vars detected, skipping api-keys.json generation"
fi

# Hand off to supervisord (Nginx + Node.js proxy)
exec /usr/bin/supervisord -c /etc/supervisord.conf
