# CRASH LENS Email Configuration Guide

## Overview

CRASH LENS uses **Brevo** (formerly Sendinblue) as the recommended email platform. One platform handles:

- **Transactional emails**: Scheduled crash reports, grant alerts, weekly digests
- **Marketing campaigns**: Government agency outreach, product announcements, demo invitations
- **Firebase auth emails**: Password reset, email verification (via SMTP relay)

## Why Brevo?

| Feature | Brevo Free | AWS SES | Mailchimp Free | SendGrid Free |
|---------|-----------|---------|----------------|---------------|
| **Monthly cost** | **$0** | ~$0.10/1k emails | $0 | $0 |
| **Daily limit** | 300/day | Unlimited | 500 total contacts | 100/day |
| **Marketing campaigns** | Yes | No | Yes | $19.95/mo add-on |
| **Transactional email** | Yes | Yes | Paid add-on | Yes |
| **SMTP relay** | Yes | No | No | Yes |
| **Campaign analytics** | Yes | No | Yes | Yes |
| **Contact management** | Yes | No | Yes (limited) | Yes |
| **Unsubscribe handling** | Automatic | Manual | Automatic | Automatic |

**Brevo free tier: 300 emails/day (9,000/month)** is sufficient for government client usage.
Upgrade to Starter ($9/month) for 5,000 emails/month with no daily limit.

## Quick Setup (15 minutes)

### Step 1: Create Brevo Account

1. Go to [brevo.com](https://www.brevo.com) and sign up
2. Verify your email address
3. Complete account setup

### Step 2: Verify Your Sender Domain

1. In Brevo Dashboard, go to **Settings > Senders, Domains & Dedicated IPs**
2. Click **Add a domain**
3. Enter: `crashlens.aicreatesai.com`
4. Add the DNS records Brevo provides to your domain registrar:
   - **SPF record** (TXT): Allows Brevo to send on your behalf
   - **DKIM record** (TXT): Cryptographic signature for email authentication
   - **DMARC record** (TXT): Policy for handling failed authentication
5. Click **Verify** once DNS records propagate (can take up to 48 hours)

### Step 3: Get Your API Key

1. Go to **SMTP & API > API Keys**
2. Click **Generate a new API key**
3. Copy the key (starts with `xkeysib-...`)

### Step 4: Get SMTP Credentials (for Firebase)

1. Go to **SMTP & API > SMTP**
2. Note the credentials:
   - Server: `smtp-relay.brevo.com`
   - Port: `587`
   - Login: Your Brevo account email
   - Password: Your SMTP key (different from API key)

### Step 5: Configure GitHub Secrets

In your GitHub repository, go to **Settings > Secrets and variables > Actions** and add:

| Secret Name | Value | Required |
|------------|-------|----------|
| `BREVO_API_KEY` | Your Brevo API key (`xkeysib-...`) | Yes |
| `NOTIFICATION_FROM_EMAIL` | `notifications@crashlens.aicreatesai.com` | Yes |
| `BREVO_SMTP_LOGIN` | Your Brevo account email | Optional (for SMTP mode) |
| `BREVO_SMTP_PASSWORD` | Your Brevo SMTP key | Optional (for SMTP mode) |

### Step 6: Configure Firebase Custom SMTP (Optional)

To route Firebase authentication emails (password reset, verification) through Brevo:

1. Go to [Firebase Console](https://console.firebase.google.com) > your project > Authentication > Templates
2. Click the pencil icon next to "SMTP Settings"
3. Enter:
   - **SMTP host**: `smtp-relay.brevo.com`
   - **SMTP port**: `587`
   - **Username**: Your Brevo account email
   - **Password**: Your Brevo SMTP key
   - **Sender email**: `noreply@crashlens.aicreatesai.com`
4. Click **Save**

This consolidates ALL emails through Brevo for unified tracking.

### Step 7: Test the Configuration

```bash
# Set environment variables
export BREVO_API_KEY="xkeysib-your-key-here"
export NOTIFICATION_FROM_EMAIL="notifications@crashlens.aicreatesai.com"

# Send a test email
python send_notifications.py --type test --email your-email@example.com
```

Or trigger via GitHub Actions:
1. Go to **Actions > Send Email Notifications**
2. Click **Run workflow**
3. Select `test` and enter your email

## Email Systems

### 1. Transactional Notifications (`send_notifications.py`)

Automated emails triggered by schedule or events:

```bash
# Scheduled crash reports (monthly, 1st of month)
python send_notifications.py --type reports

# Grant deadline alerts (daily)
python send_notifications.py --type grants

# Weekly safety digest (Monday mornings)
python send_notifications.py --type digest

# Test email
python send_notifications.py --type test --email user@agency.gov

# Force specific provider
python send_notifications.py --type test --email user@agency.gov --provider brevo
```

**Schedule** (managed by GitHub Actions):

| Email Type | Schedule | Time (ET) |
|-----------|----------|-----------|
| Monthly Reports | 1st of month | 7:00 AM |
| Weekly Digest | Every Monday | 9:00 AM |
| Grant Alerts | Daily | 8:00 AM |

### 2. Marketing Campaigns (`send_marketing.py`)

Email marketing for government agency outreach:

```bash
# List available campaign templates
python send_marketing.py --list

# Preview a campaign (saves HTML file for browser preview)
python send_marketing.py --preview product-launch

# Sync contacts to Brevo
python send_marketing.py --sync-contacts

# Send a marketing campaign
python send_marketing.py --campaign product-launch

# Send with custom subject
python send_marketing.py --campaign demo-invite --subject "Custom Subject Line"

# Send custom template
python send_marketing.py --campaign custom --subject "My Campaign" --template ./my-email.html
```

**Built-in Campaigns:**

| Campaign | Purpose | Best For |
|----------|---------|----------|
| `product-launch` | Initial CRASH LENS introduction | New agency outreach |
| `feature-update` | Monthly feature announcements | Existing users |
| `demo-invite` | Invite agencies to product demos | Warm leads |
| `grant-season` | Grant deadline awareness | All contacts |

### 3. Firebase Auth Emails

Handled automatically by Firebase, but routed through Brevo SMTP if configured (Step 6):
- Password reset emails
- Email verification
- Account confirmation

## Managing Contacts

### Transactional Subscribers

Edit `data/subscribers.json` to add/remove report subscribers:

```json
{
  "email": "safety-engineer@county.gov",
  "name": "Jane Smith",
  "agency": "Douglas County DOT",
  "verified": true,
  "reports": {
    "enabled": true,
    "frequency": "monthly"
  },
  "grants": {
    "enabled": true,
    "deadlineAlerts": true,
    "daysBeforeDeadline": [7, 14, 30],
    "weeklyDigest": true
  }
}
```

### Marketing Contacts

Edit `data/marketing_contacts.json` or manage contacts directly in the Brevo dashboard:

```json
{
  "email": "director@county.gov",
  "name": "John Director",
  "agency": "County Transportation Department",
  "role": "decision-maker",
  "tags": ["government", "virginia"]
}
```

Then sync to Brevo:
```bash
python send_marketing.py --sync-contacts
```

## Cost Breakdown

### Free Tier (recommended to start)

| Item | Cost |
|------|------|
| Brevo Free Plan | $0/month |
| 300 emails/day (9,000/month) | Included |
| Marketing campaigns | Included |
| Transactional emails | Included |
| SMTP relay (Firebase) | Included |
| Contact management | Included |
| **Total** | **$0/month** |

### If you outgrow free tier

| Plan | Emails/month | Monthly Cost |
|------|-------------|-------------|
| Brevo Free | 9,000 (300/day) | $0 |
| Brevo Starter | 5,000 (no daily limit) | $9 |
| Brevo Starter | 20,000 | $16 |
| Brevo Business | 20,000 + advanced features | $18 |

### About Hostinger Email

The Hostinger email plans ($0.35-$2.49/month) provide **mailboxes** for reading and manually sending email. They do NOT provide:
- Bulk email sending
- Marketing campaign tools
- Scheduled report delivery
- API or SMTP relay

Hostinger email is useful if you need a professional inbox (e.g., `support@crashlens.aicreatesai.com`), but it does not replace Brevo for automated sending and marketing.

## Troubleshooting

### "BREVO_API_KEY not set"
Ensure the secret is added to GitHub repository settings under **Secrets and variables > Actions**.

### Emails going to spam
1. Verify your sender domain in Brevo (SPF, DKIM, DMARC)
2. Use a professional `from` address (not gmail.com)
3. Start with small volumes and gradually increase

### "Sender not verified"
In Brevo, go to **Settings > Senders** and verify `notifications@crashlens.aicreatesai.com`.

### Rate limited (300/day)
Upgrade to Brevo Starter ($9/month) for higher limits, or stagger sends across multiple days.
