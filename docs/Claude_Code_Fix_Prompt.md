# Claude Code Fix Prompt — Crash Prediction + Scheduled Email

Copy everything below the line and paste it into Claude Code:

---

I need you to fix two bugs in the Crash Lens application. Read CLAUDE.md first for full project context. Create a PR for each fix (never push directly to main).

## Bug 1: Fix Crash Prediction Tab — Forecast API Routes Never Match

**Problem:** The Prediction tab cannot load forecast data from R2 storage. The server returns 404 for all forecast API calls.

**Root Cause:** Nginx (`nginx.conf` line 63-64) strips the `/api/` prefix when proxying:
```nginx
location /api/ {
    proxy_pass http://127.0.0.1:3001/;   # trailing slash strips /api/
}
```
So the client calling `GET /api/forecasts/virginia/henrico/county_roads` arrives at the Node.js server as `GET /forecasts/virginia/henrico/county_roads`. But the route matchers in `server/qdrant-proxy.js` still include `/api/` in their regex patterns, so they never match.

**Fixes required in `server/qdrant-proxy.js`:**

1. Find the forecast data endpoint (around line 980). Change the regex from:
   ```js
   req.url.match(/^\/api\/forecasts\/([a-z_]+)\/([a-z_]+)\/([a-z_]+)$/)
   ```
   to:
   ```js
   req.url.match(/^\/forecasts\/([a-z_]+)\/([a-z_]+)\/([a-z_]+)$/)
   ```

2. Find the forecast availability check endpoint (around line 1031). Change the regex from:
   ```js
   req.url.match(/^\/api\/forecasts\/check\/([a-z_]+)\/([a-z_]+)$/)
   ```
   to:
   ```js
   req.url.match(/^\/forecasts\/check\/([a-z_]+)\/([a-z_]+)$/)
   ```

3. **IMPORTANT:** Search the ENTIRE `server/qdrant-proxy.js` file for any other `req.url` route patterns that incorrectly include `/api/` prefix. All routes should match WITHOUT `/api/` since Nginx strips it. The existing working endpoints (`/notify/send`, `/subscribe`, `/health`, etc.) correctly omit it already — use those as the reference pattern.

**Verification:** After the fix, `GET /api/forecasts/virginia/henrico/county_roads` from the browser should return forecast JSON data (proxied through Nginx → Node.js → R2 fetch from `virginia/henrico/forecasts_county_roads.json`).

## Bug 2: Implement Server-Side Email Scheduling

**Problem:** The Report tab's "Schedule Email" feature saves preferences to browser localStorage only. No server-side mechanism exists to send emails on the configured schedule. The Brevo API key and sender email ARE configured in Coolify (confirmed working).

**What exists today:**
- Client UI: `openEmailNotificationModal()` (app/index.html ~line 33917) — full scheduling config UI
- Client save: `saveNotificationPreferences()` (~line 33807) — saves to localStorage only
- Server send: `POST /notify/send` endpoint (qdrant-proxy.js ~line 267) — works, uses Brevo API
- Server send function: `sendViaBrevoApi()` (~line 139) — works when BREVO_API_KEY is set
- Test button: `testEmailNotification()` (~line 35357) — calls `/api/notify/send`, should work
- GitHub Actions: `send-notifications.yml` — separate cron system, disconnected from UI preferences

**Fixes required:**

### Step 1: Add schedule CRUD endpoints to `server/qdrant-proxy.js`

Add these routes (remember: NO `/api/` prefix since Nginx strips it):

```
POST /schedule/save     — Save/update a user's email schedule
GET  /schedule/list     — List active schedules for a user
DELETE /schedule/:id    — Delete a schedule
```

Store schedules in Firestore under `users/{uid}/emailSchedules/{scheduleId}`. Firebase Admin SDK is already initialized in the server for Stripe webhook processing — reuse that. Each schedule document should contain:
```json
{
  "enabled": true,
  "recipients": ["user@example.com"],
  "reportType": "comprehensive",
  "frequency": "weekly",
  "dayOfWeek": 1,
  "dayOfMonth": null,
  "time": "08:00",
  "timezone": "America/New_York",
  "jurisdiction": "henrico",
  "state": "virginia",
  "agency": "Henrico County",
  "createdAt": "ISO timestamp",
  "updatedAt": "ISO timestamp",
  "lastSentAt": null,
  "nextRunAt": "ISO timestamp"
}
```

Authenticate requests using Firebase ID token in the `Authorization: Bearer <token>` header (use `admin.auth().verifyIdToken()`).

### Step 2: Add server-side scheduler using `node-cron`

1. Add `node-cron` to `server/package.json` dependencies
2. On server startup, register a master cron job that runs every minute
3. Each minute, query Firestore for schedules where `enabled: true` and `nextRunAt <= now`
4. For each matching schedule:
   a. Send email using existing `sendViaBrevoApi()` with a professional HTML email body containing a link to open Crash Lens for the jurisdiction (full PDF generation can be a follow-up — for now send an email with key stats if available, plus a "View Full Report in CRASH LENS" button linking to `https://crashlens.aicreatesai.com/app`)
   b. Update `lastSentAt` to now
   c. Calculate and update `nextRunAt` based on frequency/day/time/timezone
5. Add error handling and logging so failed sends don't block other schedules
6. Cache loaded schedules in memory with a 5-minute TTL to avoid hammering Firestore every minute

### Step 3: Update client-side to sync with server

In `app/index.html`, update `saveNotificationPreferences()` (~line 33807) to:

1. Continue saving to localStorage (for immediate UI state)
2. Also call `POST /api/schedule/save` with the schedule config
3. Include the Firebase auth token: `await firebase.auth().currentUser.getIdToken()`
4. Show success toast: "Schedule saved — emails will be sent automatically"
5. Show error toast if the server call fails (but don't block the localStorage save)
6. When the modal opens, also load from server via `GET /api/schedule/list` and merge with localStorage data (server is source of truth)

### Step 4: Update Dockerfile if needed

If `node-cron` requires adding to dependencies, make sure the Docker build process runs `npm install` in the server directory. Check the existing `Dockerfile` for how server dependencies are installed and follow the same pattern.

**Create a single PR with all changes. Test that:**
- [ ] Forecast data loads in the Prediction tab when switching road types
- [ ] Forecast availability check returns correct file status
- [ ] Schedule save persists to Firestore
- [ ] Test email sends successfully via the "Send Test" button
- [ ] No existing endpoints are broken (check `/notify/send`, `/notify/status`, Stripe endpoints, Qdrant endpoints)
