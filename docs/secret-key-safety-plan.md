# Plan: Separate API Keys from config.json for Coolify Deployment

## Context

`config.json` currently contains **real API keys** (Mapbox, Google, Mapillary, Firebase) committed to GitHub. The user deploys via Coolify/Docker and stores secrets in Coolify's environment variables. The goal is to remove secrets from `config.json` while keeping all non-sensitive config (jurisdictions, app settings, URLs) visible in the repo. The app already has a `loadApiKeys()` mechanism that loads from a gitignored `config/api-keys.json` — but it's incomplete (only handles Mapbox/Google, not Mapillary/Firebase), and the Docker setup doesn't generate this file from env vars.

## Files to Modify

| File | Action |
|------|--------|
| `config.json` | Replace real API keys with `""` placeholders |
| `config/api-keys.example.json` | Add Mapillary + Firebase templates |
| `app/index.html` (~line 22434) | Add Mapillary + Firebase to merge logic |
| `assets/js/firebase-config.js` | Also fetch `api-keys.json` before init |
| `Dockerfile` | Add `config/` COPY + entrypoint |
| `.dockerignore` | Add `config/api-keys.json` safety entry |
| **New:** `docker-entrypoint.sh` | Generate `api-keys.json` from env vars |
| **New:** `.env.example` | Document all env var names for Coolify |

## Step-by-step

### 1. Remove real keys from `config.json` (lines 5-31)

Replace only the secret values with empty strings. Keep all structure + non-sensitive fields intact:

```json
"mapbox": { "accessToken": "", "geocodingEndpoint": "https://..." }
"google": { "mapsApiKey": "" }
"mapillary": { "accessToken": "", "enabled": true, ... (keep all other fields) }
"firebase": { "apiKey": "", "authDomain": "", "projectId": "", "storageBucket": "", "messagingSenderId": "", "appId": "" }
```

`tigerweb` section — no changes (no secrets).

### 2. Update `config/api-keys.example.json`

Add `mapillary` and `firebase` sections alongside existing `mapbox` and `google`.

### 3. Extend merge logic in `app/index.html` (line ~22434)

Add after the existing `google` merge block:

```javascript
if (apiKeys.mapillary) {
    appConfig.apis.mapillary = { ...appConfig.apis.mapillary, ...apiKeys.mapillary };
}
if (apiKeys.firebase) {
    appConfig.apis.firebase = { ...appConfig.apis.firebase, ...apiKeys.firebase };
}
```

Uses spread so non-sensitive fields (searchRadius, enabled, etc.) from `config.json` are preserved; only the token gets overridden.

### 4. Update `assets/js/firebase-config.js`

Currently reads only `config.json`. After Step 1, Firebase keys will be empty there. Update to also try fetching `../config/api-keys.json` and merge Firebase keys before calling `initializeApp()`. This is critical because `login/index.html` loads this file independently (doesn't go through `app/index.html`'s `loadApiKeys()`).

### 5. Create `docker-entrypoint.sh` (new file)

Shell script that:
1. Creates `/usr/share/nginx/html/config/` directory
2. Generates `api-keys.json` from environment variables (`MAPBOX_ACCESS_TOKEN`, `GOOGLE_MAPS_API_KEY`, `MAPILLARY_ACCESS_TOKEN`, `FIREBASE_API_KEY`, etc.)
3. Runs `exec "$@"` to hand off to supervisord

### 6. Update `Dockerfile`

- Add `COPY config/ /usr/share/nginx/html/config/` (after app/ copy, line 21)
- Add `COPY docker-entrypoint.sh` + `RUN chmod +x`
- Change `CMD` to `ENTRYPOINT ["/docker-entrypoint.sh"]` + `CMD ["/usr/bin/supervisord", ...]`

### 7. Update `.dockerignore`

Add `config/api-keys.json` to prevent accidental inclusion.

### 8. Create `.env.example` (new file)

Document all env var names with help links:
- `MAPBOX_ACCESS_TOKEN`
- `GOOGLE_MAPS_API_KEY`
- `MAPILLARY_ACCESS_TOKEN`
- `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_PROJECT_ID`, `FIREBASE_STORAGE_BUCKET`, `FIREBASE_MESSAGING_SENDER_ID`, `FIREBASE_APP_ID`

## What the User Needs to Do in Coolify After This

Set these environment variables in Coolify's Environment settings with the real values:

```
MAPBOX_ACCESS_TOKEN=pk.eyJ1...
GOOGLE_MAPS_API_KEY=AIzaSy...
MAPILLARY_ACCESS_TOKEN=MLY|254...
FIREBASE_API_KEY=AIzaSy...
FIREBASE_AUTH_DOMAIN=crash-lens-f50e7.firebaseapp.com
FIREBASE_PROJECT_ID=crash-lens-f50e7
FIREBASE_STORAGE_BUCKET=crash-lens-f50e7.firebasestorage.app
FIREBASE_MESSAGING_SENDER_ID=345091421318
FIREBASE_APP_ID=1:345091421318:web:88f99469eb0ce73c734d07
```

## Visibility Answer

**You will NOT lose visibility.** `config.json` stays fully tracked in GitHub with all its structure — jurisdictions, app settings, URLs, map styles. The only thing removed is the actual secret values (replaced with `""`). The `.env.example` file documents exactly which env vars are needed.

## Verification

- Build Docker image: `docker build -t crash-lens .`
- Run with env vars: `docker run -e MAPBOX_ACCESS_TOKEN=pk.xxx ... -p 8080:80 crash-lens`
- Verify `config.json` in git has empty key values
- Verify map loads in browser (Mapbox token injected)
- Verify Firebase auth works (login page)
- Verify graceful degradation without env vars (console warnings, no crashes)
