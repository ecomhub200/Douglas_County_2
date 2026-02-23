# CRASH LENS Email Setup Guide (Brevo)

## Overview

CRASH LENS uses **Brevo** (formerly Sendinblue) for all email:

- **Transactional emails**: Scheduled crash reports, grant alerts, weekly digests
- **Marketing campaigns**: Government agency outreach, product announcements
- **Firebase auth emails**: Password reset, email verification (via SMTP relay)

**Cost: $0/month** (free tier: 300 emails/day = 9,000/month)

## Quick Setup (15 minutes)

### Step 1: Create Brevo Account

1. Go to [brevo.com](https://www.brevo.com) and sign up (free)
2. Verify your email address
3. Complete account setup

### Step 2: Get Your API Key

1. Go to **SMTP & API > API Keys**
2. Click **Generate a new API key**
3. Name it: `CRASH LENS Production`
4. Copy the key — it starts with `xkeysib-`

**IMPORTANT**: Copy the FULL key. It looks like:
```
xkeysib-abc123def456...very-long-string...xyz789
```

### Step 3: Verify Sender Email

1. Go to **Settings > Senders, Domains & Dedicated IPs**
2. Click **Add a sender**
3. Add: `notifications@crashlens.aicreatesai.com`
4. Verify via the confirmation email Brevo sends

For better deliverability, also verify the domain:
1. Click **Add a domain** > enter `crashlens.aicreatesai.com`
2. Add the DNS records Brevo provides:
   - **SPF record** (TXT)
   - **DKIM record** (TXT)
3. Click **Verify** (DNS propagation can take up to 48 hours)

### Step 4: Add GitHub Secrets

In your GitHub repo: **Settings > Secrets and variables > Actions > New repository secret**

| Secret Name | Value | Example |
|------------|-------|---------|
| `BREVO_API_KEY` | Your Brevo API key | `xkeysib-abc123...` |
| `NOTIFICATION_FROM_EMAIL` | Your verified sender | `notifications@crashlens.aicreatesai.com` |

**Only 2 secrets needed.** That's it.

### Step 5: Test It

Go to **Actions > Send Email Notifications > Run workflow**:
- Select `test`
- Enter your email address
- Click **Run workflow**

You should receive a test email within 30 seconds.

## Do I Need Hostinger SMTP?

**No.** You do NOT need Hostinger email or any SMTP setup from Hostinger. Here's why:

| What | Hostinger | Brevo |
|------|-----------|-------|
| Professional mailbox (read/reply) | Yes ($0.35/mo) | No |
| Send automated emails | No | Yes (free) |
| Marketing campaigns | No | Yes (free) |
| API for programmatic sending | No | Yes (free) |
| Schedule reports | No | Yes (free) |

- **Hostinger email** = a mailbox for you to manually read and reply to emails (like Gmail)
- **Brevo** = a sending platform that your code uses to deliver emails automatically

You only need Hostinger email if you want a professional inbox like `support@aicreatesai.com` for manually replying to people. For everything automated, Brevo handles it.

## Firebase Auth Emails (Optional)

To route Firebase password reset and verification emails through Brevo:

1. Get SMTP credentials from Brevo: **SMTP & API > SMTP**
   - Server: `smtp-relay.brevo.com`
   - Port: `587`
   - Login: Your Brevo account email
   - Password: Your SMTP key (shown on the SMTP page)

2. In Firebase Console > **Authentication > Templates**:
   - Click the pencil icon next to "SMTP Settings"
   - Enter the Brevo SMTP credentials above
   - Set sender to: `noreply@crashlens.aicreatesai.com`
   - Click **Save**

## Email Systems

### Transactional Notifications (`send_notifications.py`)

```bash
python send_notifications.py --type reports     # Monthly crash reports
python send_notifications.py --type grants      # Grant deadline alerts
python send_notifications.py --type digest      # Weekly safety digest
python send_notifications.py --type test --email you@example.com
```

**Automated schedule** (via GitHub Actions):

| Email | Schedule | Time (ET) |
|-------|----------|-----------|
| Monthly Reports | 1st of month | 7:00 AM |
| Weekly Digest | Every Monday | 9:00 AM |
| Grant Alerts | Daily | 8:00 AM |

### Marketing Campaigns (`send_marketing.py`)

```bash
python send_marketing.py --list                    # List campaign templates
python send_marketing.py --preview product-launch  # Preview HTML
python send_marketing.py --sync-contacts           # Sync contacts to Brevo
python send_marketing.py --campaign product-launch # Send campaign
```

## Troubleshooting

### 401 "Key not found"
Your API key is invalid. Fix it:
1. Go to Brevo Dashboard > **SMTP & API > API Keys**
2. Copy the FULL key (starts with `xkeysib-`)
3. In GitHub > **Settings > Secrets > BREVO_API_KEY**:
   - Delete the old secret
   - Create a new one with the correct key
   - No extra spaces, quotes, or line breaks

### 400 "Sender not found"
Your sender email isn't verified in Brevo:
1. Go to **Settings > Senders** in Brevo
2. Add and verify `notifications@crashlens.aicreatesai.com`

### Emails going to spam
1. Verify your domain (not just the email) in Brevo
2. Add SPF + DKIM DNS records
3. Start with small volumes, then increase

### No emails received but no errors
Check `data/subscribers.json` — subscribers need `"verified": true` and `"enabled": true`.

## Cost

| Plan | Emails/month | Cost |
|------|-------------|------|
| **Free** | 9,000 (300/day) | **$0** |
| Starter | 5,000 (no daily limit) | $9 |
| Starter | 20,000 | $16 |
