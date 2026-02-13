# Cloudflare R2 Setup for CRASH LENS

## Prerequisites (Already Done)

- [x] Cloudflare account created
- [x] R2 bucket `crash-lens-data` created
- [x] Free r2.dev public URL enabled: `https://pub-3334b656e3c74ea28eb4165b32499843.r2.dev`

## Remaining Setup Steps

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
| `R2_PUBLIC_URL` | `https://pub-3334b656e3c74ea28eb4165b32499843.r2.dev` |

### 4. Configure R2 Bucket CORS

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

This allows the browser app to fetch CSV files from R2 regardless of which domain it's hosted on.

## Verification

### Quick Test

1. Run the **"Download CDOT Crash Data"** workflow manually (Actions tab > Download CDOT Crash Data > Run workflow)
2. Check R2 bucket in Cloudflare dashboard for uploaded files
3. Check `data/r2-manifest.json` in your repo was updated with correct mappings
4. Open the app and verify data loads (check browser DevTools **Network** tab)
5. Console should show: `[R2] Resolved: ../data/CDOT/douglas_all_roads.csv -> https://pub-...r2.dev/colorado/douglas/all_roads.csv`

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

### CORS errors in browser

If you see `Access-Control-Allow-Origin` errors in the browser console:
- Verify CORS policy is set on the R2 bucket (step 4 above)
- The app will fall back to local paths automatically

### Workflow upload failures

If the R2 upload step fails in GitHub Actions:
- Check that all 3 secrets are set correctly (CF_ACCOUNT_ID, CF_R2_ACCESS_KEY_ID, CF_R2_SECRET_ACCESS_KEY)
- Check the R2 API token has "Object Read & Write" permission
- Check the token is scoped to the `crash-lens-data` bucket
- The composite action retries uploads 3 times automatically

### App still loading from local paths

If the manifest exists but the app isn't using R2:
- Check that `r2BaseUrl` is not empty in `data/r2-manifest.json`
- Check that `localPathMapping` has entries matching the data files
- Check browser console for `[R2]` log messages
