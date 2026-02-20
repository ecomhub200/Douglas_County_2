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

# Only generate if at least one relevant env var is set
if [ -n "$MAPBOX_ACCESS_TOKEN" ] || [ -n "$GOOGLE_MAPS_API_KEY" ]; then
    echo "[Entrypoint] Generating api-keys.json from environment variables..."

    mkdir -p "$API_KEYS_DIR"

    # Build JSON using a here-document
    MAPBOX_TOKEN="${MAPBOX_ACCESS_TOKEN:-}"
    GOOGLE_KEY="${GOOGLE_MAPS_API_KEY:-}"

    cat > "$API_KEYS_FILE" <<JSONEOF
{
  "mapbox": {
    "accessToken": "${MAPBOX_TOKEN}"
  },
  "google": {
    "mapsApiKey": "${GOOGLE_KEY}"
  }
}
JSONEOF

    echo "[Entrypoint] api-keys.json written successfully"
    # Log which keys were injected (without revealing values)
    [ -n "$MAPBOX_TOKEN" ] && echo "[Entrypoint]   - MAPBOX_ACCESS_TOKEN: set (${#MAPBOX_TOKEN} chars)"
    [ -n "$GOOGLE_KEY" ] && echo "[Entrypoint]   - GOOGLE_MAPS_API_KEY: set (${#GOOGLE_KEY} chars)"
else
    echo "[Entrypoint] No API key env vars detected, skipping api-keys.json generation"
fi

# Hand off to supervisord (Nginx + Node.js proxy)
exec /usr/bin/supervisord -c /etc/supervisord.conf
