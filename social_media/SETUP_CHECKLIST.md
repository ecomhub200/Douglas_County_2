# CRASH LENS Social Media Setup Checklist

## Pre-Registration Checklist

- [ ] **Choose handle**: Decide on consistent handle (e.g., `@CrashLensAI`)
- [ ] **Create logo**: Square format, minimum 400x400px
- [ ] **Create banners**: LinkedIn (1128x191), Facebook (820x312), X (1500x500), YouTube (2560x1440)
- [ ] **Write bio**: Short (150 chars) and long (2000 chars) versions
- [ ] **Prepare website link**: Landing page URL for bio links

---

## Platform Registration (All use your Gmail)

### 1. LinkedIn Company Page
- [ ] Go to: https://www.linkedin.com/company/setup/new/
- [ ] Sign in with your Gmail
- [ ] Create Company Page (select "Small Business")
- [ ] Company name: `CRASH LENS`
- [ ] Custom URL: `linkedin.com/company/crashlens`
- [ ] Upload logo and banner
- [ ] Add description, website, industry (Transportation/Software)
- [ ] Add location and company size
- [ ] Invite connections to follow

### 2. Facebook Business Page
- [ ] Go to: https://www.facebook.com/pages/create
- [ ] Sign in with your Gmail (create personal account first if needed)
- [ ] Page name: `CRASH LENS`
- [ ] Category: "Software" or "Science & Technology"
- [ ] Upload profile picture and cover photo
- [ ] Add about section, website, contact info
- [ ] Set up Page username: `@CrashLensAI`
- [ ] Enable messaging and auto-responses

### 3. X / Twitter
- [ ] Go to: https://twitter.com/i/flow/signup
- [ ] Sign up with your Gmail
- [ ] Username: `@CrashLensAI`
- [ ] Upload profile picture and header
- [ ] Write bio (160 chars max)
- [ ] Add website link
- [ ] Apply for API access (for automation): https://developer.twitter.com/
- [ ] Create API keys (save in secure location)

### 4. YouTube Channel
- [ ] Go to: https://www.youtube.com (sign in with Gmail)
- [ ] Click your profile > Create a channel
- [ ] Channel name: `CRASH LENS`
- [ ] Upload profile picture and banner
- [ ] Add channel description
- [ ] Add links (website, other social media)
- [ ] Create channel sections/playlists:
  - [ ] Product Tutorials
  - [ ] Safety Analysis
  - [ ] Industry Updates
- [ ] Set custom URL: `youtube.com/@CrashLensAI`

### 5. Instagram Business Account
- [ ] Go to: https://www.instagram.com/
- [ ] Sign up with your Gmail
- [ ] Username: `@CrashLensAI`
- [ ] Switch to Business account (Settings > Account > Switch to Professional)
- [ ] Connect to Facebook Page
- [ ] Upload profile picture
- [ ] Write bio (150 chars max)
- [ ] Add website link
- [ ] Set up link-in-bio (Linktree or similar)

### 6. TikTok
- [ ] Go to: https://www.tiktok.com/signup
- [ ] Sign up with your Gmail
- [ ] Username: `@CrashLensAI`
- [ ] Switch to Business account
- [ ] Upload profile picture
- [ ] Write bio
- [ ] Add website link

### 7. Bluesky
- [ ] Go to: https://bsky.app/
- [ ] Create account with your Gmail
- [ ] Handle: `@crashlens.bsky.social`
- [ ] Upload profile picture and banner
- [ ] Write bio
- [ ] Create app password (for automation): Settings > App Passwords

### 8. Reddit
- [ ] Go to: https://www.reddit.com/register
- [ ] Create account: `CrashLensAI`
- [ ] Join subreddits:
  - [ ] r/trafficengineering
  - [ ] r/urbanplanning
  - [ ] r/civilengineering
  - [ ] r/transportation
  - [ ] r/dataisbeautiful
- [ ] Start engaging with comments (build karma before posting)
- [ ] **Do NOT post promotionally** -- be a helpful community member

---

## API Keys & Credentials Setup

### Required for Automation
- [ ] **Claude API Key**: https://console.anthropic.com/ (add to GitHub Secrets as `ANTHROPIC_API_KEY`)
- [ ] **Twitter/X API Keys**: https://developer.twitter.com/
  - [ ] API Key
  - [ ] API Secret
  - [ ] Access Token
  - [ ] Access Token Secret
- [ ] **Facebook Page Token**: https://developers.facebook.com/
  - [ ] Create Facebook App
  - [ ] Get Page Access Token (long-lived)
- [ ] **LinkedIn API**: https://www.linkedin.com/developers/
  - [ ] Create LinkedIn App
  - [ ] Get OAuth2 access token
- [ ] **Bluesky App Password**: Settings > App Passwords

### GitHub Secrets (for GitHub Action)
Add these to your repo: Settings > Secrets and variables > Actions

- [ ] `ANTHROPIC_API_KEY` - Claude API key

### VPS Environment Variables
Add these to `/opt/crashlens-social/.env` on your Hostinger VPS:

- [ ] `ANTHROPIC_API_KEY`
- [ ] `LINKEDIN_ACCESS_TOKEN`
- [ ] `TWITTER_API_KEY`
- [ ] `TWITTER_API_SECRET`
- [ ] `TWITTER_ACCESS_TOKEN`
- [ ] `TWITTER_ACCESS_SECRET`
- [ ] `FACEBOOK_PAGE_TOKEN`
- [ ] `BLUESKY_HANDLE`
- [ ] `BLUESKY_APP_PASSWORD`

---

## VPS Setup (Hostinger)

### Prerequisites
- [ ] SSH access to your Hostinger VPS
- [ ] VPS has at least 4GB RAM and 2 vCPUs
- [ ] Domain (optional) pointed to VPS IP

### Installation
```bash
# 1. SSH into your VPS
ssh root@your-vps-ip

# 2. Clone the repo (or just copy the setup script)
git clone https://github.com/your-org/your-repo.git
cd your-repo/social_media/scripts

# 3. Run the setup script
chmod +x setup_vps.sh
sudo ./setup_vps.sh

# 4. Update the .env with your API keys
nano /opt/crashlens-social/.env

# 5. Restart services
crashlens-social restart
```

### Post-Setup
- [ ] Access Postiz at `http://your-vps-ip:4200`
- [ ] Create admin account in Postiz
- [ ] Connect social media accounts in Postiz
- [ ] Access n8n at `http://your-vps-ip:5678`
- [ ] Change n8n default password
- [ ] Create first automation workflow in n8n
- [ ] (Optional) Set up domain + SSL with nginx reverse proxy

---

## n8n Workflow Setup

### Workflow 1: Weekly Post Generation
1. [ ] Create new workflow in n8n
2. [ ] Add Schedule Trigger (every Monday 8 AM EST)
3. [ ] Add HTTP Request node to call Claude API
4. [ ] Add Email node to send posts for review
5. [ ] Add Postiz node to schedule approved posts
6. [ ] Test and activate the workflow

### Workflow 2: Content Calendar Reader
1. [ ] Create a Google Sheet with content calendar
2. [ ] Add Google Sheets trigger node
3. [ ] Connect to Claude API for content generation
4. [ ] Route to appropriate platform posting nodes

---

## Content Calendar (First Month)

### Week 1 - Launch Week
- [ ] LinkedIn: "Introducing CRASH LENS" announcement
- [ ] X/Twitter: "We're on Twitter!" + safety stat thread
- [ ] Facebook: Launch video/demo
- [ ] Instagram: Brand intro carousel

### Week 2 - Educational Content
- [ ] LinkedIn: "What is EPDO scoring?" article
- [ ] X/Twitter: Daily safety facts
- [ ] YouTube: First tutorial video
- [ ] TikTok: "Did you know?" safety fact

### Week 3 - Product Spotlight
- [ ] LinkedIn: CMF analysis feature deep dive
- [ ] X/Twitter: Feature tip thread
- [ ] Instagram: Before/after infographic
- [ ] Facebook: Demo video

### Week 4 - Industry Engagement
- [ ] LinkedIn: Industry news commentary
- [ ] X/Twitter: Engage with FHWA/NHTSA posts
- [ ] Reddit: Helpful answer in r/trafficengineering
- [ ] Bluesky: Vision Zero discussion

---

## Ongoing Maintenance

- [ ] Review analytics weekly (engagement, reach, followers)
- [ ] Respond to all comments/messages within 24 hours
- [ ] Adjust posting schedule based on analytics
- [ ] Update content calendar monthly
- [ ] Refine Claude prompts based on top-performing posts
- [ ] Backup Postiz and n8n databases monthly (`crashlens-social backup`)
- [ ] Update Docker images monthly (`crashlens-social update`)
