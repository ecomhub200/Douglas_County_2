# Cloudflare R2 Setup for CRASH LENS

## Prerequisites (Already Done)

- [x] Cloudflare account created
- [x] R2 bucket `crash-lens-data` created
- [x] Custom domain configured: `https://data.aicreatesai.com`

## Custom Domain Setup (Recommended for Production)

Using a custom domain instead of the free `r2.dev` subdomain is **critical for reliability**:

| Feature | Free r2.dev URL | Custom Domain |
|---------|----------------|---------------|
| CDN Edge Caching | No | Yes |
| Rate Limiting | Aggressive | Standard CDN limits |
| CORS Handling | Manual bucket policy (fragile) | Automatic via Cloudflare |
| DNS Control | None | Full control |
| SSL Certificate | Shared | Dedicated |

### How to Configure Custom Domain

1. Go to **Cloudflare Dashboard** > **R2 Object Storage** > **crash-lens-data** > **Settings**
2. Under **Custom Domains**, click **"Connect Domain"**
3. Enter: `data.aicreatesai.com`
4. Cloudflare will automatically:
   - Add a CNAME record in your DNS
   - Provision an SSL certificate
   - Route traffic through the CDN edge network
5. Wait for the domain status to show **"Active"** (usually < 5 minutes)

### After Custom Domain is Active

Update the GitHub Actions variable:

| Variable Name | Old Value | New Value |
|--------------|-----------|-----------|
| `R2_PUBLIC_URL` | `https://pub-3334b656e3c74ea28eb4165b32499843.r2.dev` | `https://data.aicreatesai.com` |

The codebase has already been updated to use `https://data.aicreatesai.com` in:
- `app/index.html` — `R2_BASE_URL` constant
- `data/r2-manifest.json` — `r2BaseUrl` field

## R2 API Token Setup

### 1. Create R2 API Token

1. Go to **Cloudflare Dashboard** > **R2 Object Storage** > **Overview**
2. Click **"Manage R2 API Tokens"** (top right)
3. Click **"Create API Token"**
4. Configure:
   - **Token name:** `crash-lens-github-actions`
   - **Permissions:** Object Read & Write
   - **Scope:** Apply to specific bucket only > `crash-lens-data`
   - **TTL:** No expiration (or set a long TTL)
5. Click **"Create API Token"**
6. **Copy these three values** (shown only once!):
   - Access Key ID
   - Secret Access Key
   - Your Account ID (visible in your dashboard URL: `https://dash.cloudflare.com/<ACCOUNT_ID>/...`)

### 2. Add GitHub Secrets

Go to your repo: **Settings** > **Secrets and variables** > **Actions** > **New repository secret**

| Secret Name | Value |
|------------|-------|
| `CF_ACCOUNT_ID` | Your Cloudflare Account ID |
| `CF_R2_ACCESS_KEY_ID` | The Access Key ID from step 1 |
| `CF_R2_SECRET_ACCESS_KEY` | The Secret Access Key from step 1 |

### 3. Add GitHub Variable

Go to: **Settings** > **Secrets and variables** > **Actions** > **Variables** tab > **New repository variable**

| Variable Name | Value |
|--------------|-------|
| `R2_PUBLIC_URL` | `https://data.aicreatesai.com` |

### 4. Configure R2 Bucket CORS (Only if NOT using custom domain)

> **Note:** If you're using a custom domain (recommended), CORS is handled automatically by Cloudflare. This step is only needed if you're using the free `r2.dev` subdomain.

In **Cloudflare Dashboard** > **R2** > **crash-lens-data** > **Settings** > **CORS Policy**, add:

```json
[
  {
    "AllowedOrigins": ["*"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 86400
  }
]
```

## Verification

### Quick Test

1. Run the **"Download CDOT Crash Data"** workflow manually (Actions tab > Download CDOT Crash Data > Run workflow)
2. Check R2 bucket in Cloudflare dashboard for uploaded files
3. Check `data/r2-manifest.json` in your repo was updated with correct mappings
4. Open the app and verify data loads (check browser DevTools **Network** tab)
5. Console should show: `[R2] Resolved: colorado/douglas/all_roads.csv -> https://data.aicreatesai.com/colorado/douglas/all_roads.csv`

### Custom Domain Test

```bash
# Verify custom domain serves R2 files
curl -I https://data.aicreatesai.com/colorado/douglas/county_roads.csv
# Expected: HTTP/2 200, Content-Type: text/csv

# Verify CORS headers (with custom domain, Cloudflare handles this)
curl -I -H "Origin: https://crashlens.com" https://data.aicreatesai.com/colorado/douglas/county_roads.csv
```

### Fallback Test

1. Temporarily clear `r2BaseUrl` in `data/r2-manifest.json`
2. Refresh the app - it should fall back to local paths seamlessly
3. Restore the manifest

### End-to-End Test

Trigger each workflow and verify:
- **Download CDOT Crash Data** -> Files uploaded to R2 `colorado/douglas/` prefix
- **Process CDOT Crash Data** -> Processed files uploaded to R2, manifest updated
- **Download Traffic Data** (crash job) -> Files uploaded to R2 `virginia/{jurisdiction}/` prefix
- **Generate Crash Forecasts** -> Downloads input from R2, outputs forecast JSONs to Git

### Health Check

- **Manual:** Run the `R2 Health Check` workflow from the Actions tab
- **Automatic:** The health check runs daily at 6:00 AM UTC and creates a GitHub issue if R2 is down
- **Browser:** Open DevTools console and run `diagR2Connection()` for end-to-end diagnostics

## R2 Bucket Structure

```
crash-lens-data/
  colorado/
    douglas/
      all_roads.csv
      county_roads.csv
      no_interstate.csv
      standardized.csv
      crashes.csv
      raw/
        2021.csv
        2022.csv
        2023.csv
        2024.csv
        2025.csv
  virginia/
    henrico/
      all_roads.csv
      county_roads.csv
      no_interstate.csv
```

## What Stays in Git

- `data/r2-manifest.json` (URL manifest)
- `data/grants.csv` (3.4 KB)
- `data/cmf_processed.json` (245 KB)
- `data/cmf_metadata.json` (351 B)
- `data/va_mutcd/*` (static reference data)
- `data/CDOT/forecasts*.json` (~237 KB each)
- `data/CDOT/config.json`, `source_manifest.json`, `jurisdictions.json`
- `data/CDOT/.geocode_cache.json`
- `data/.validation/*`, `data/CDOT/.validation/*`
- All config files, docs, and app code

## Troubleshooting

### Data not loading in the app

1. Open browser DevTools **Console** and run `diagR2Connection()` — this tests the full pipeline
2. Check for `[R2]` log messages to see URL resolution details
3. Check the **Network** tab for failed requests to `data.aicreatesai.com`

### CORS errors in browser

If you see `Access-Control-Allow-Origin` errors:
- **With custom domain:** This shouldn't happen — check that the custom domain is Active in Cloudflare Dashboard
- **With r2.dev:** Verify CORS policy is set on the R2 bucket (step 4 above)
- The app will fall back to local paths automatically

### Workflow upload failures

If the R2 upload step fails in GitHub Actions:
- Check that all 3 secrets are set correctly (CF_ACCOUNT_ID, CF_R2_ACCESS_KEY_ID, CF_R2_SECRET_ACCESS_KEY)
- Check the R2 API token has "Object Read & Write" permission
- Check the token is scoped to the `crash-lens-data` bucket
- The composite action retries uploads 3 times and verifies public accessibility after upload

### App still loading from local paths

If the manifest exists but the app isn't using R2:
- Check that `r2BaseUrl` is not empty in `data/r2-manifest.json`
- Check that `localPathMapping` has entries matching the data files
- Check browser console for `[R2]` log messages

### Manifest staleness warning

If you see `[R2] WARNING: Manifest is X days old` in the console:
- The data pipeline hasn't run in over 30 days
- Run a download workflow to refresh the data and manifest
- The R2 Health Check workflow (daily) will also alert via GitHub issue if R2 becomes inaccessible
