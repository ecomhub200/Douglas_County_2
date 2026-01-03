# CRASH LENS - Supabase Integration Setup Guide

> **Version:** 1.0.0
> **Last Updated:** January 2026
> **Author:** CRASH LENS Development Team

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Create Supabase Project](#2-create-supabase-project)
3. [Environment Configuration](#3-environment-configuration)
4. [Database Setup](#4-database-setup)
5. [Authentication Configuration](#5-authentication-configuration)
6. [Storage Configuration](#6-storage-configuration)
7. [Row Level Security (RLS)](#7-row-level-security-rls)
8. [Edge Functions Setup](#8-edge-functions-setup)
9. [Stripe Integration](#9-stripe-integration)
10. [Migration from Firebase](#10-migration-from-firebase)
11. [Testing & Validation](#11-testing--validation)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Prerequisites

### Required Accounts
- [ ] [Supabase Account](https://supabase.com) (free tier available)
- [ ] [Stripe Account](https://stripe.com) (for billing - optional initially)
- [ ] [Google Cloud Console](https://console.cloud.google.com) (for Google OAuth)
- [ ] [Microsoft Azure Portal](https://portal.azure.com) (for Microsoft OAuth)

### Required Tools
- [ ] Git installed
- [ ] Node.js 18+ installed (for Supabase CLI)
- [ ] Python 3.9+ installed (for data scripts)

### Install Supabase CLI

```bash
# Using npm
npm install -g supabase

# Using Homebrew (macOS)
brew install supabase/tap/supabase

# Verify installation
supabase --version
```

---

## 2. Create Supabase Project

### Step 2.1: Create New Project

1. Go to [supabase.com](https://supabase.com) and sign in
2. Click **"New Project"**
3. Fill in project details:
   - **Name:** `crash-lens-production` (or `crash-lens-dev` for development)
   - **Database Password:** Generate a strong password and **SAVE IT SECURELY**
   - **Region:** `us-east-1` (closest to Virginia)
   - **Pricing Plan:** Free tier to start

4. Click **"Create new project"**
5. Wait 2-3 minutes for project provisioning

### Step 2.2: Get Project Credentials

Once the project is ready, go to **Settings > API** and note down:

| Credential | Description | Where to Find |
|------------|-------------|---------------|
| `Project URL` | Your Supabase API endpoint | Settings > API > Project URL |
| `anon public` | Client-side API key (safe to expose) | Settings > API > Project API keys |
| `service_role` | Server-side key (NEVER expose) | Settings > API > Project API keys |
| `JWT Secret` | For custom JWT validation | Settings > API > JWT Settings |

### Step 2.3: Get Database Connection String

Go to **Settings > Database** and copy:
- **Connection string (URI)** - for direct database access
- **Connection pooler** - for serverless connections

---

## 3. Environment Configuration

### Step 3.1: Create Environment File

Create a file named `.env.local` in your project root:

```bash
# Create the file (it's already in .gitignore)
touch .env.local
```

### Step 3.2: Add Supabase Credentials

Edit `.env.local` with your credentials:

```env
# ============================================================
# SUPABASE CONFIGURATION
# ============================================================

# Project URL (from Settings > API)
NEXT_PUBLIC_SUPABASE_URL=https://your-project-ref.supabase.co

# Anon Key - safe for client-side (from Settings > API)
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Service Role Key - SERVER ONLY, never expose to client
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Direct database connection (for migrations)
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.your-project-ref.supabase.co:5432/postgres

# ============================================================
# STRIPE CONFIGURATION (Add later in Phase 4)
# ============================================================

# STRIPE_SECRET_KEY=sk_test_...
# STRIPE_PUBLISHABLE_KEY=pk_test_...
# STRIPE_WEBHOOK_SECRET=whsec_...

# ============================================================
# OAUTH PROVIDERS (Configure in Supabase Dashboard)
# ============================================================

# Google OAuth (from Google Cloud Console)
# GOOGLE_CLIENT_ID=...
# GOOGLE_CLIENT_SECRET=...

# Microsoft Azure AD (from Azure Portal)
# AZURE_CLIENT_ID=...
# AZURE_CLIENT_SECRET=...

# ============================================================
# APPLICATION SETTINGS
# ============================================================

NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_APP_NAME=CRASH LENS
```

### Step 3.3: Verify .gitignore

Confirm `.env.local` is in `.gitignore`:

```bash
# Check if .env.local is ignored
git check-ignore .env.local
# Should output: .env.local
```

---

## 4. Database Setup

### Step 4.1: Initialize Supabase Locally (Optional but Recommended)

```bash
# Initialize Supabase in your project
cd /path/to/henrico_crash_tool
supabase init

# Link to your remote project
supabase link --project-ref your-project-ref

# Pull remote schema (if any exists)
supabase db pull
```

### Step 4.2: Create Database Tables

Go to **SQL Editor** in Supabase Dashboard and run the following migrations in order:

#### Migration 1: Core Tables (Jurisdictions & Users)

```sql
-- ============================================================
-- MIGRATION 1: CORE INFRASTRUCTURE
-- Run this first
-- ============================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- ============================================================
-- JURISDICTIONS TABLE (133 Virginia localities)
-- ============================================================
CREATE TABLE IF NOT EXISTS jurisdictions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('county', 'city')),
    fips_code TEXT,
    juris_code TEXT,
    name_patterns TEXT[],
    map_center_lat DECIMAL(10, 7),
    map_center_lng DECIMAL(10, 7),
    map_zoom INTEGER DEFAULT 10,
    maintains_own_roads BOOLEAN DEFAULT FALSE,
    lea_id TEXT,
    school_district_name TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    subscription_tier TEXT DEFAULT 'free',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for faster lookups
CREATE INDEX idx_jurisdictions_slug ON jurisdictions(slug);
CREATE INDEX idx_jurisdictions_juris_code ON jurisdictions(juris_code);

-- ============================================================
-- ORGANIZATIONS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    type TEXT CHECK (type IN ('county_gov', 'city_gov', 'mpo', 'consulting', 'state_agency')),
    primary_jurisdiction_id UUID REFERENCES jurisdictions(id),
    jurisdiction_ids UUID[],
    stripe_customer_id TEXT,
    subscription_status TEXT DEFAULT 'trial',
    subscription_plan TEXT,
    trial_ends_at TIMESTAMPTZ,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- USER PROFILES TABLE (extends auth.users)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    display_name TEXT,
    avatar_url TEXT,
    phone TEXT,
    job_title TEXT,
    organization_id UUID REFERENCES organizations(id),
    auth_provider TEXT,
    email_verified BOOLEAN DEFAULT FALSE,
    email_verified_at TIMESTAMPTZ,
    individual_subscription BOOLEAN DEFAULT FALSE,
    stripe_customer_id TEXT,
    subscription_status TEXT DEFAULT 'trial',
    subscription_plan TEXT,
    trial_started_at TIMESTAMPTZ,
    trial_ends_at TIMESTAMPTZ,
    ai_queries_this_month INTEGER DEFAULT 0,
    ai_queries_limit INTEGER DEFAULT 100,
    ai_quota_reset_date DATE,
    use_byok BOOLEAN DEFAULT TRUE,
    preferences JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- USER JURISDICTIONS (Many-to-Many with Roles)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_jurisdictions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    jurisdiction_id UUID NOT NULL REFERENCES jurisdictions(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'viewer' CHECK (role IN ('admin', 'editor', 'viewer')),
    can_upload_data BOOLEAN DEFAULT FALSE,
    can_delete_data BOOLEAN DEFAULT FALSE,
    can_manage_users BOOLEAN DEFAULT FALSE,
    can_export_reports BOOLEAN DEFAULT TRUE,
    can_use_ai BOOLEAN DEFAULT TRUE,
    assigned_by UUID REFERENCES auth.users(id),
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_user_jurisdiction UNIQUE (user_id, jurisdiction_id)
);

CREATE INDEX idx_user_jurisdictions_user ON user_jurisdictions(user_id);
CREATE INDEX idx_user_jurisdictions_jurisdiction ON user_jurisdictions(jurisdiction_id);

-- ============================================================
-- AUDIT LOG TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id),
    jurisdiction_id UUID REFERENCES jurisdictions(id),
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id UUID,
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_log_user ON audit_log(user_id);
CREATE INDEX idx_audit_log_jurisdiction ON audit_log(jurisdiction_id);
CREATE INDEX idx_audit_log_created ON audit_log(created_at DESC);

-- ============================================================
-- TRIGGER: Auto-create user profile on signup
-- ============================================================
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
    provider_name TEXT;
    is_verified BOOLEAN;
    trial_end TIMESTAMPTZ;
BEGIN
    provider_name := NEW.raw_app_meta_data->>'provider';
    is_verified := CASE
        WHEN provider_name IN ('google', 'azure') THEN TRUE
        ELSE COALESCE((NEW.email_confirmed_at IS NOT NULL), FALSE)
    END;
    trial_end := CASE WHEN is_verified THEN NOW() + INTERVAL '14 days' ELSE NULL END;

    INSERT INTO user_profiles (
        id, email, display_name, auth_provider,
        email_verified, email_verified_at,
        subscription_status, trial_started_at, trial_ends_at
    ) VALUES (
        NEW.id,
        NEW.email,
        COALESCE(
            NEW.raw_user_meta_data->>'display_name',
            NEW.raw_user_meta_data->>'full_name',
            NEW.raw_user_meta_data->>'name',
            split_part(NEW.email, '@', 1)
        ),
        provider_name,
        is_verified,
        CASE WHEN is_verified THEN NOW() ELSE NULL END,
        CASE WHEN is_verified THEN 'trial' ELSE 'pending_verification' END,
        CASE WHEN is_verified THEN NOW() ELSE NULL END,
        trial_end
    );

    -- Log signup
    INSERT INTO audit_log (user_id, action, details)
    VALUES (NEW.id, 'user_signup', jsonb_build_object(
        'provider', provider_name,
        'email', NEW.email
    ));

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create trigger
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

COMMENT ON TABLE jurisdictions IS 'Virginia localities (95 counties + 38 cities)';
COMMENT ON TABLE user_profiles IS 'Extended user data, linked to auth.users';
COMMENT ON TABLE user_jurisdictions IS 'User access permissions per jurisdiction';
```

#### Migration 2: Crash Data Tables

```sql
-- ============================================================
-- MIGRATION 2: CRASH DATA TABLES
-- Run after Migration 1
-- ============================================================

-- ============================================================
-- CRASHES TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS crashes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    jurisdiction_id UUID NOT NULL REFERENCES jurisdictions(id),
    document_nbr TEXT,
    crash_id TEXT,
    crash_year INTEGER NOT NULL,
    crash_date DATE,
    crash_time TIME,
    severity CHAR(1) CHECK (severity IN ('K', 'A', 'B', 'C', 'O')),
    collision_type TEXT,
    weather_condition TEXT,
    light_condition TEXT,
    road_surface TEXT,
    route_name TEXT,
    node_id TEXT,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    geom GEOMETRY(Point, 4326),
    pedestrian_involved BOOLEAN DEFAULT FALSE,
    bicycle_involved BOOLEAN DEFAULT FALSE,
    impaired_involved BOOLEAN DEFAULT FALSE,
    speed_related BOOLEAN DEFAULT FALSE,
    distracted_involved BOOLEAN DEFAULT FALSE,
    persons_injured INTEGER DEFAULT 0,
    persons_killed INTEGER DEFAULT 0,
    functional_class TEXT,
    facility_type TEXT,
    road_system TEXT,
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_crash UNIQUE (jurisdiction_id, document_nbr)
);

-- Performance indexes
CREATE INDEX idx_crashes_jurisdiction ON crashes(jurisdiction_id);
CREATE INDEX idx_crashes_year ON crashes(crash_year);
CREATE INDEX idx_crashes_severity ON crashes(severity);
CREATE INDEX idx_crashes_route ON crashes(route_name);
CREATE INDEX idx_crashes_node ON crashes(node_id);
CREATE INDEX idx_crashes_date ON crashes(crash_date);
CREATE INDEX idx_crashes_ped_bike ON crashes(pedestrian_involved, bicycle_involved);
CREATE INDEX idx_crashes_geom ON crashes USING GIST(geom);

-- Trigger to auto-populate geometry
CREATE OR REPLACE FUNCTION update_crash_geom()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
        NEW.geom := ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    END IF;
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER crash_geom_trigger
    BEFORE INSERT OR UPDATE ON crashes
    FOR EACH ROW EXECUTE FUNCTION update_crash_geom();

-- ============================================================
-- CRASH AGGREGATES TABLE (for dashboard performance)
-- ============================================================
CREATE TABLE IF NOT EXISTS crash_aggregates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    jurisdiction_id UUID NOT NULL REFERENCES jurisdictions(id),
    aggregation_type TEXT NOT NULL,
    aggregation_key TEXT NOT NULL,
    crash_year INTEGER,
    total_crashes INTEGER DEFAULT 0,
    fatal_k INTEGER DEFAULT 0,
    serious_a INTEGER DEFAULT 0,
    minor_b INTEGER DEFAULT 0,
    possible_c INTEGER DEFAULT 0,
    pdo_o INTEGER DEFAULT 0,
    epdo_score DECIMAL(12, 2) DEFAULT 0,
    pedestrian_count INTEGER DEFAULT 0,
    bicycle_count INTEGER DEFAULT 0,
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_aggregate UNIQUE (jurisdiction_id, aggregation_type, aggregation_key, crash_year)
);

CREATE INDEX idx_aggregates_jurisdiction ON crash_aggregates(jurisdiction_id);
CREATE INDEX idx_aggregates_type ON crash_aggregates(aggregation_type);

COMMENT ON TABLE crashes IS 'Individual crash records from Virginia Roads';
COMMENT ON TABLE crash_aggregates IS 'Pre-computed aggregates for dashboard performance';
```

#### Migration 3: Feature Tables (Grants, Warrants, CMF)

```sql
-- ============================================================
-- MIGRATION 3: FEATURE TABLES
-- Run after Migration 2
-- ============================================================

-- ============================================================
-- GRANT OPPORTUNITIES (System-wide reference)
-- ============================================================
CREATE TABLE IF NOT EXISTS grant_opportunities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    grant_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    agency TEXT,
    cfda_number TEXT,
    program_type TEXT,
    close_date DATE,
    post_date DATE,
    federal_share_pct INTEGER,
    award_ceiling DECIMAL(15, 2),
    award_floor DECIMAL(15, 2),
    emphasis_areas TEXT[],
    eligible_activities TEXT[],
    requires_crash_data BOOLEAN DEFAULT TRUE,
    application_url TEXT,
    contact_info TEXT,
    status TEXT DEFAULT 'Open',
    virginia_specific BOOLEAN DEFAULT FALSE,
    description TEXT,
    eligibility_criteria JSONB,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- GRANT APPLICATIONS (User-specific)
-- ============================================================
CREATE TABLE IF NOT EXISTS grant_applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    jurisdiction_id UUID NOT NULL REFERENCES jurisdictions(id),
    grant_opportunity_id UUID NOT NULL REFERENCES grant_opportunities(id),
    application_title TEXT,
    status TEXT DEFAULT 'draft',
    target_locations JSONB,
    estimated_cost DECIMAL(15, 2),
    requested_amount DECIMAL(15, 2),
    local_match_amount DECIMAL(15, 2),
    benefit_cost_ratio DECIMAL(8, 4),
    crash_summary JSONB,
    internal_deadline DATE,
    submission_deadline DATE,
    submitted_at TIMESTAMPTZ,
    team_members UUID[],
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_grant_apps_user ON grant_applications(user_id);
CREATE INDEX idx_grant_apps_jurisdiction ON grant_applications(jurisdiction_id);

-- ============================================================
-- GRANT DOCUMENTS
-- ============================================================
CREATE TABLE IF NOT EXISTS grant_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES grant_applications(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    document_type TEXT,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    mime_type TEXT,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- GRANT FAVORITES
-- ============================================================
CREATE TABLE IF NOT EXISTS grant_favorites (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    grant_opportunity_id UUID NOT NULL REFERENCES grant_opportunities(id),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_favorite UNIQUE (user_id, grant_opportunity_id)
);

-- ============================================================
-- WARRANT STUDIES
-- ============================================================
CREATE TABLE IF NOT EXISTS warrant_studies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    jurisdiction_id UUID NOT NULL REFERENCES jurisdictions(id),
    study_type TEXT NOT NULL,
    study_name TEXT NOT NULL,
    intersection_name TEXT,
    location_description TEXT,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    config JSONB NOT NULL,
    tmc_data JSONB,
    warrant_inputs JSONB,
    analysis_results JSONB,
    crash_summary JSONB,
    crash_count INTEGER,
    analysis_period_start DATE,
    analysis_period_end DATE,
    status TEXT DEFAULT 'draft',
    recommendation TEXT,
    is_shared BOOLEAN DEFAULT FALSE,
    shared_with UUID[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_warrant_studies_user ON warrant_studies(user_id);
CREATE INDEX idx_warrant_studies_jurisdiction ON warrant_studies(jurisdiction_id);

-- ============================================================
-- CMF DATABASE (FHWA Clearinghouse)
-- ============================================================
CREATE TABLE IF NOT EXISTS cmf_database (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cmf_id TEXT UNIQUE,
    countermeasure_name TEXT NOT NULL,
    countermeasure_description TEXT,
    category TEXT,
    subcategory TEXT,
    cmf_value DECIMAL(6, 4) NOT NULL,
    cmf_low DECIMAL(6, 4),
    cmf_high DECIMAL(6, 4),
    standard_error DECIMAL(6, 4),
    crash_types TEXT[],
    road_types TEXT[],
    area_types TEXT[],
    star_rating INTEGER CHECK (star_rating BETWEEN 1 AND 5),
    study_count INTEGER,
    cost_low DECIMAL(12, 2),
    cost_high DECIMAL(12, 2),
    cost_unit TEXT,
    is_proven_countermeasure BOOLEAN DEFAULT FALSE,
    virginia_relevance_score DECIMAL(4, 2),
    source_url TEXT,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- CMF RECOMMENDATIONS (User-saved)
-- ============================================================
CREATE TABLE IF NOT EXISTS cmf_recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    jurisdiction_id UUID NOT NULL REFERENCES jurisdictions(id),
    location_name TEXT NOT NULL,
    location_type TEXT,
    node_id TEXT,
    crash_profile JSONB NOT NULL,
    analysis_date DATE DEFAULT CURRENT_DATE,
    recommended_cmfs JSONB NOT NULL,
    ai_analysis TEXT,
    selected_cmfs UUID[],
    implementation_notes TEXT,
    estimated_benefit DECIMAL(12, 2),
    status TEXT DEFAULT 'recommended',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- AI CONVERSATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    jurisdiction_id UUID REFERENCES jurisdictions(id),
    conversation_type TEXT,
    title TEXT,
    location_context JSONB,
    messages JSONB NOT NULL DEFAULT '[]',
    attachment_ids UUID[],
    provider_used TEXT,
    model_used TEXT,
    total_tokens INTEGER,
    is_starred BOOLEAN DEFAULT FALSE,
    is_archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ai_conversations_user ON ai_conversations(user_id);

-- ============================================================
-- GENERATED REPORTS
-- ============================================================
CREATE TABLE IF NOT EXISTS generated_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    jurisdiction_id UUID NOT NULL REFERENCES jurisdictions(id),
    report_type TEXT NOT NULL,
    report_title TEXT NOT NULL,
    file_format TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    parameters JSONB,
    is_public BOOLEAN DEFAULT FALSE,
    public_url TEXT,
    expires_at TIMESTAMPTZ,
    download_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_reports_user ON generated_reports(user_id);
CREATE INDEX idx_reports_jurisdiction ON generated_reports(jurisdiction_id);

COMMENT ON TABLE grant_opportunities IS 'Available grants from Grants.gov and Virginia programs';
COMMENT ON TABLE warrant_studies IS 'Saved signal/stop sign warrant analyses';
COMMENT ON TABLE cmf_database IS 'FHWA CMF Clearinghouse countermeasures';
```

#### Migration 4: Stripe & Billing Tables

```sql
-- ============================================================
-- MIGRATION 4: STRIPE & BILLING
-- Run after Migration 3
-- ============================================================

-- ============================================================
-- STRIPE CUSTOMERS
-- ============================================================
CREATE TABLE IF NOT EXISTS stripe_customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id),
    organization_id UUID REFERENCES organizations(id),
    stripe_customer_id TEXT UNIQUE NOT NULL,
    email TEXT,
    name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT customer_owner CHECK (
        (user_id IS NOT NULL AND organization_id IS NULL) OR
        (user_id IS NULL AND organization_id IS NOT NULL)
    )
);

-- ============================================================
-- STRIPE SUBSCRIPTIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS stripe_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    stripe_customer_id TEXT NOT NULL REFERENCES stripe_customers(stripe_customer_id),
    stripe_subscription_id TEXT UNIQUE NOT NULL,
    stripe_price_id TEXT NOT NULL,
    plan_name TEXT NOT NULL,
    status TEXT NOT NULL,
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    cancel_at TIMESTAMPTZ,
    canceled_at TIMESTAMPTZ,
    max_users INTEGER,
    max_jurisdictions INTEGER,
    max_ai_queries INTEGER,
    max_storage_mb INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- STRIPE INVOICES
-- ============================================================
CREATE TABLE IF NOT EXISTS stripe_invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    stripe_customer_id TEXT NOT NULL REFERENCES stripe_customers(stripe_customer_id),
    stripe_invoice_id TEXT UNIQUE NOT NULL,
    stripe_subscription_id TEXT REFERENCES stripe_subscriptions(stripe_subscription_id),
    amount_due INTEGER,
    amount_paid INTEGER,
    currency TEXT DEFAULT 'usd',
    status TEXT,
    invoice_pdf TEXT,
    hosted_invoice_url TEXT,
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- USAGE RECORDS (for metered billing)
-- ============================================================
CREATE TABLE IF NOT EXISTS usage_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    jurisdiction_id UUID REFERENCES jurisdictions(id),
    usage_type TEXT NOT NULL,
    quantity INTEGER DEFAULT 1,
    reported_to_stripe BOOLEAN DEFAULT FALSE,
    stripe_usage_record_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_usage_records_user ON usage_records(user_id, created_at);
CREATE INDEX idx_usage_records_unreported ON usage_records(reported_to_stripe)
    WHERE NOT reported_to_stripe;

COMMENT ON TABLE stripe_customers IS 'Stripe customer records for billing';
COMMENT ON TABLE stripe_subscriptions IS 'Active subscription details';
COMMENT ON TABLE usage_records IS 'Metered usage for AI queries, reports, etc.';
```

### Step 4.3: Seed Virginia Jurisdictions

```sql
-- ============================================================
-- SEED DATA: Virginia Jurisdictions (run after migrations)
-- This inserts all 133 Virginia localities
-- ============================================================

INSERT INTO jurisdictions (slug, name, type, fips_code, juris_code, name_patterns, map_center_lat, map_center_lng, map_zoom, maintains_own_roads) VALUES
('henrico', 'Henrico County', 'county', '087', '43', ARRAY['HENRICO', '043. Henrico County'], 37.55, -77.45, 11, true),
('fairfax_county', 'Fairfax County', 'county', '059', '29', ARRAY['FAIRFAX COUNTY', '029. Fairfax County'], 38.83, -77.28, 10, false),
('arlington', 'Arlington County', 'county', '013', '7', ARRAY['ARLINGTON', '007. Arlington County'], 38.88, -77.10, 12, true),
('virginia_beach', 'Virginia Beach City', 'city', '810', '130', ARRAY['VIRGINIA BEACH', '130. Virginia Beach City'], 36.85, -75.98, 10, false),
('norfolk', 'Norfolk City', 'city', '710', '119', ARRAY['NORFOLK', '119. Norfolk City'], 36.85, -76.29, 12, false),
('richmond_city', 'Richmond City', 'city', '760', '125', ARRAY['RICHMOND CITY', '125. Richmond City'], 37.54, -77.44, 12, false),
('chesterfield', 'Chesterfield County', 'county', '041', '21', ARRAY['CHESTERFIELD', '021. Chesterfield County'], 37.38, -77.50, 10, false),
('loudoun', 'Loudoun County', 'county', '107', '53', ARRAY['LOUDOUN', '053. Loudoun County'], 39.08, -77.64, 10, false),
('prince_william', 'Prince William County', 'county', '153', '73', ARRAY['PRINCE WILLIAM', '073. Prince William County'], 38.70, -77.48, 10, false),
('chesapeake', 'Chesapeake City', 'city', '550', '100', ARRAY['CHESAPEAKE', '100. Chesapeake City'], 36.77, -76.29, 10, false)
-- Add remaining 123 jurisdictions...
-- (Full seed file available separately)
ON CONFLICT (slug) DO NOTHING;
```

> **Note:** The complete seed file with all 133 jurisdictions can be generated from `config.json`.

---

## 5. Authentication Configuration

### Step 5.1: Configure Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create new project or select existing
3. Navigate to **APIs & Services > Credentials**
4. Click **Create Credentials > OAuth client ID**
5. Configure consent screen if prompted
6. Select **Web application**
7. Add authorized redirect URI:
   ```
   https://your-project-ref.supabase.co/auth/v1/callback
   ```
8. Copy **Client ID** and **Client Secret**

In Supabase Dashboard:
1. Go to **Authentication > Providers**
2. Enable **Google**
3. Paste Client ID and Client Secret
4. Save

### Step 5.2: Configure Microsoft OAuth

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory > App registrations**
3. Click **New registration**
4. Configure:
   - Name: `CRASH LENS`
   - Supported account types: **Accounts in any organizational directory and personal Microsoft accounts**
   - Redirect URI: `https://your-project-ref.supabase.co/auth/v1/callback`
5. After creation, go to **Certificates & secrets**
6. Create new client secret and copy it
7. Copy **Application (client) ID** from Overview

In Supabase Dashboard:
1. Go to **Authentication > Providers**
2. Enable **Azure (Microsoft)**
3. Paste Client ID and Client Secret
4. Set Azure Tenant: `common` (for multi-tenant)
5. Save

### Step 5.3: Configure Email Authentication

1. Go to **Authentication > Providers**
2. Enable **Email**
3. Configure settings:
   - Enable email confirmations: **ON**
   - Enable secure email change: **ON**
   - Minimum password length: **8**

4. Go to **Authentication > Email Templates**
5. Customize templates:
   - Confirmation email
   - Password reset
   - Magic link (optional)

### Step 5.4: Configure Auth Settings

1. Go to **Authentication > URL Configuration**
2. Set Site URL: `https://your-domain.com` (or localhost for dev)
3. Add Redirect URLs:
   ```
   https://your-domain.com/auth/callback
   https://your-domain.com/app
   http://localhost:3000/auth/callback
   http://localhost:3000/app
   ```

---

## 6. Storage Configuration

### Step 6.1: Create Storage Buckets

In Supabase Dashboard, go to **Storage** and create these buckets:

| Bucket Name | Public | Description |
|-------------|--------|-------------|
| `crash-uploads` | No | User-uploaded crash CSV files |
| `grant-documents` | No | Grant application documents |
| `warrant-files` | No | TMC counts and warrant documents |
| `reports` | No | Generated reports |
| `templates` | No | Agency logos and branding |
| `exports` | No | Temporary export files |

### Step 6.2: Configure Storage Policies

```sql
-- ============================================================
-- STORAGE POLICIES
-- Run in SQL Editor
-- ============================================================

-- Policy: Users can upload to their jurisdiction folders
CREATE POLICY "Users upload to jurisdiction folders"
ON storage.objects FOR INSERT
WITH CHECK (
    bucket_id IN ('crash-uploads', 'grant-documents', 'warrant-files', 'reports')
    AND auth.uid() IS NOT NULL
);

-- Policy: Users can view their jurisdiction files
CREATE POLICY "Users view jurisdiction files"
ON storage.objects FOR SELECT
USING (
    bucket_id IN ('crash-uploads', 'grant-documents', 'warrant-files', 'reports', 'templates')
    AND auth.uid() IS NOT NULL
);

-- Policy: Users can delete their own uploads
CREATE POLICY "Users delete own uploads"
ON storage.objects FOR DELETE
USING (
    auth.uid() IS NOT NULL
    AND (storage.foldername(name))[1] = auth.uid()::text
);
```

---

## 7. Row Level Security (RLS)

### Step 7.1: Enable RLS on All Tables

```sql
-- ============================================================
-- ENABLE ROW LEVEL SECURITY
-- ============================================================

ALTER TABLE jurisdictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_jurisdictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE crashes ENABLE ROW LEVEL SECURITY;
ALTER TABLE crash_aggregates ENABLE ROW LEVEL SECURITY;
ALTER TABLE grant_opportunities ENABLE ROW LEVEL SECURITY;
ALTER TABLE grant_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE grant_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE grant_favorites ENABLE ROW LEVEL SECURITY;
ALTER TABLE warrant_studies ENABLE ROW LEVEL SECURITY;
ALTER TABLE cmf_database ENABLE ROW LEVEL SECURITY;
ALTER TABLE cmf_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_reports ENABLE ROW LEVEL SECURITY;
```

### Step 7.2: Create RLS Policies

```sql
-- ============================================================
-- RLS POLICIES
-- ============================================================

-- JURISDICTIONS: Public read
CREATE POLICY "Anyone can view jurisdictions"
ON jurisdictions FOR SELECT USING (true);

-- USER PROFILES: Own profile + org members
CREATE POLICY "Users view own profile"
ON user_profiles FOR SELECT
USING (id = auth.uid());

CREATE POLICY "Users update own profile"
ON user_profiles FOR UPDATE
USING (id = auth.uid());

-- USER JURISDICTIONS: Own assignments
CREATE POLICY "Users view own jurisdiction assignments"
ON user_jurisdictions FOR SELECT
USING (user_id = auth.uid());

-- CRASHES: Jurisdiction-scoped
CREATE POLICY "Users view jurisdiction crashes"
ON crashes FOR SELECT
USING (
    jurisdiction_id IN (
        SELECT jurisdiction_id FROM user_jurisdictions
        WHERE user_id = auth.uid()
    )
);

CREATE POLICY "Editors insert crashes"
ON crashes FOR INSERT
WITH CHECK (
    jurisdiction_id IN (
        SELECT jurisdiction_id FROM user_jurisdictions
        WHERE user_id = auth.uid() AND role IN ('admin', 'editor')
    )
);

-- GRANT OPPORTUNITIES: Public read
CREATE POLICY "Anyone view grants"
ON grant_opportunities FOR SELECT USING (true);

-- GRANT APPLICATIONS: Owner + team + jurisdiction admin
CREATE POLICY "Users view own/team applications"
ON grant_applications FOR SELECT
USING (
    user_id = auth.uid()
    OR auth.uid() = ANY(team_members)
    OR jurisdiction_id IN (
        SELECT jurisdiction_id FROM user_jurisdictions
        WHERE user_id = auth.uid() AND role = 'admin'
    )
);

CREATE POLICY "Users manage own applications"
ON grant_applications FOR ALL
USING (user_id = auth.uid());

-- WARRANT STUDIES: Owner + shared
CREATE POLICY "Users view own/shared warrant studies"
ON warrant_studies FOR SELECT
USING (
    user_id = auth.uid()
    OR auth.uid() = ANY(shared_with)
    OR (is_shared AND jurisdiction_id IN (
        SELECT jurisdiction_id FROM user_jurisdictions
        WHERE user_id = auth.uid()
    ))
);

CREATE POLICY "Users manage own warrant studies"
ON warrant_studies FOR ALL
USING (user_id = auth.uid());

-- CMF DATABASE: Public read
CREATE POLICY "Anyone view CMF database"
ON cmf_database FOR SELECT USING (true);

-- CMF RECOMMENDATIONS: Jurisdiction-scoped
CREATE POLICY "Users view jurisdiction CMF recommendations"
ON cmf_recommendations FOR SELECT
USING (
    jurisdiction_id IN (
        SELECT jurisdiction_id FROM user_jurisdictions
        WHERE user_id = auth.uid()
    )
);

-- AI CONVERSATIONS: Owner only
CREATE POLICY "Users manage own conversations"
ON ai_conversations FOR ALL
USING (user_id = auth.uid());

-- GENERATED REPORTS: Owner + jurisdiction
CREATE POLICY "Users view own/jurisdiction reports"
ON generated_reports FOR SELECT
USING (
    user_id = auth.uid()
    OR jurisdiction_id IN (
        SELECT jurisdiction_id FROM user_jurisdictions
        WHERE user_id = auth.uid()
    )
);

CREATE POLICY "Users manage own reports"
ON generated_reports FOR ALL
USING (user_id = auth.uid());
```

---

## 8. Edge Functions Setup

### Step 8.1: Create Functions Directory

```bash
# Create Edge Functions directory
mkdir -p supabase/functions

# Create function folders
mkdir -p supabase/functions/stripe-webhook
mkdir -p supabase/functions/sync-crash-data
mkdir -p supabase/functions/create-checkout
```

### Step 8.2: Stripe Webhook Function

Create `supabase/functions/stripe-webhook/index.ts`:

```typescript
import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2"
import Stripe from "https://esm.sh/stripe@12.0.0"

const stripe = new Stripe(Deno.env.get("STRIPE_SECRET_KEY")!, {
  apiVersion: "2023-10-16",
})

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
)

serve(async (req) => {
  const signature = req.headers.get("stripe-signature")!
  const body = await req.text()

  let event: Stripe.Event

  try {
    event = stripe.webhooks.constructEvent(
      body,
      signature,
      Deno.env.get("STRIPE_WEBHOOK_SECRET")!
    )
  } catch (err) {
    console.error("Webhook signature verification failed:", err.message)
    return new Response(`Webhook Error: ${err.message}`, { status: 400 })
  }

  console.log("Received Stripe event:", event.type)

  switch (event.type) {
    case "checkout.session.completed": {
      const session = event.data.object as Stripe.Checkout.Session
      await handleCheckoutComplete(session)
      break
    }
    case "customer.subscription.updated": {
      const subscription = event.data.object as Stripe.Subscription
      await handleSubscriptionUpdate(subscription)
      break
    }
    case "customer.subscription.deleted": {
      const subscription = event.data.object as Stripe.Subscription
      await handleSubscriptionDeleted(subscription)
      break
    }
    case "invoice.paid": {
      const invoice = event.data.object as Stripe.Invoice
      await handleInvoicePaid(invoice)
      break
    }
  }

  return new Response(JSON.stringify({ received: true }), {
    headers: { "Content-Type": "application/json" },
  })
})

async function handleCheckoutComplete(session: Stripe.Checkout.Session) {
  const customerId = session.customer as string
  const subscriptionId = session.subscription as string

  const subscription = await stripe.subscriptions.retrieve(subscriptionId)
  const priceId = subscription.items.data[0].price.id

  const planLimits = getPlanLimits(priceId)

  await supabase.from("stripe_subscriptions").upsert({
    stripe_customer_id: customerId,
    stripe_subscription_id: subscriptionId,
    stripe_price_id: priceId,
    plan_name: planLimits.name,
    status: subscription.status,
    current_period_start: new Date(subscription.current_period_start * 1000).toISOString(),
    current_period_end: new Date(subscription.current_period_end * 1000).toISOString(),
    max_users: planLimits.maxUsers,
    max_jurisdictions: planLimits.maxJurisdictions,
    max_ai_queries: planLimits.maxAiQueries,
    max_storage_mb: planLimits.maxStorageMb,
  })

  // Update user subscription status
  const { data: customer } = await supabase
    .from("stripe_customers")
    .select("user_id, organization_id")
    .eq("stripe_customer_id", customerId)
    .single()

  if (customer?.user_id) {
    await supabase
      .from("user_profiles")
      .update({
        subscription_status: "active",
        subscription_plan: planLimits.name
      })
      .eq("id", customer.user_id)
  }
}

async function handleSubscriptionUpdate(subscription: Stripe.Subscription) {
  await supabase
    .from("stripe_subscriptions")
    .update({
      status: subscription.status,
      current_period_end: new Date(subscription.current_period_end * 1000).toISOString(),
      updated_at: new Date().toISOString(),
    })
    .eq("stripe_subscription_id", subscription.id)
}

async function handleSubscriptionDeleted(subscription: Stripe.Subscription) {
  await supabase
    .from("stripe_subscriptions")
    .update({
      status: "canceled",
      canceled_at: new Date().toISOString(),
    })
    .eq("stripe_subscription_id", subscription.id)

  // Update user status
  const { data: sub } = await supabase
    .from("stripe_subscriptions")
    .select("stripe_customer_id")
    .eq("stripe_subscription_id", subscription.id)
    .single()

  if (sub) {
    const { data: customer } = await supabase
      .from("stripe_customers")
      .select("user_id")
      .eq("stripe_customer_id", sub.stripe_customer_id)
      .single()

    if (customer?.user_id) {
      await supabase
        .from("user_profiles")
        .update({ subscription_status: "canceled" })
        .eq("id", customer.user_id)
    }
  }
}

async function handleInvoicePaid(invoice: Stripe.Invoice) {
  await supabase.from("stripe_invoices").upsert({
    stripe_customer_id: invoice.customer as string,
    stripe_invoice_id: invoice.id,
    stripe_subscription_id: invoice.subscription as string,
    amount_due: invoice.amount_due,
    amount_paid: invoice.amount_paid,
    status: invoice.status,
    invoice_pdf: invoice.invoice_pdf,
    hosted_invoice_url: invoice.hosted_invoice_url,
    period_start: invoice.period_start ? new Date(invoice.period_start * 1000).toISOString() : null,
    period_end: invoice.period_end ? new Date(invoice.period_end * 1000).toISOString() : null,
  })
}

function getPlanLimits(priceId: string) {
  const plans: Record<string, any> = {
    "price_professional": {
      name: "professional",
      maxUsers: 1,
      maxJurisdictions: 3,
      maxAiQueries: 500,
      maxStorageMb: 5120,
    },
    "price_agency": {
      name: "agency",
      maxUsers: 5,
      maxJurisdictions: 10,
      maxAiQueries: 2000,
      maxStorageMb: 25600,
    },
    "price_enterprise": {
      name: "enterprise",
      maxUsers: -1,
      maxJurisdictions: -1,
      maxAiQueries: -1,
      maxStorageMb: -1,
    },
  }
  return plans[priceId] || plans["price_professional"]
}
```

### Step 8.3: Deploy Edge Functions

```bash
# Deploy all functions
supabase functions deploy stripe-webhook
supabase functions deploy sync-crash-data
supabase functions deploy create-checkout

# Set secrets for functions
supabase secrets set STRIPE_SECRET_KEY=sk_live_xxx
supabase secrets set STRIPE_WEBHOOK_SECRET=whsec_xxx
```

---

## 9. Stripe Integration

### Step 9.1: Create Stripe Products

1. Go to [Stripe Dashboard](https://dashboard.stripe.com)
2. Navigate to **Products**
3. Create products:

| Product | Price ID | Monthly Price | Features |
|---------|----------|---------------|----------|
| Professional | `price_professional` | $49 | 1 user, 3 jurisdictions, 500 AI queries |
| Agency | `price_agency` | $199 | 5 users, 10 jurisdictions, 2000 AI queries |
| Enterprise | `price_enterprise` | Custom | Unlimited |

### Step 9.2: Configure Webhook

1. Go to **Developers > Webhooks**
2. Click **Add endpoint**
3. URL: `https://your-project-ref.supabase.co/functions/v1/stripe-webhook`
4. Select events:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.paid`
   - `invoice.payment_failed`
5. Copy webhook signing secret to `.env.local`

### Step 9.3: Test Stripe Integration

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login to Stripe
stripe login

# Forward webhooks to local function
stripe listen --forward-to localhost:54321/functions/v1/stripe-webhook

# Trigger test events
stripe trigger checkout.session.completed
```

---

## 10. Migration from Firebase

### Step 10.1: Export Firebase Users

```javascript
// firebase-export.js
const admin = require('firebase-admin');
const fs = require('fs');

admin.initializeApp({
  credential: admin.credential.cert('./serviceAccountKey.json')
});

async function exportUsers() {
  const users = [];
  let nextPageToken;

  do {
    const result = await admin.auth().listUsers(1000, nextPageToken);
    users.push(...result.users.map(user => ({
      uid: user.uid,
      email: user.email,
      displayName: user.displayName,
      photoURL: user.photoURL,
      emailVerified: user.emailVerified,
      provider: user.providerData[0]?.providerId,
      createdAt: user.metadata.creationTime
    })));
    nextPageToken = result.pageToken;
  } while (nextPageToken);

  fs.writeFileSync('firebase-users.json', JSON.stringify(users, null, 2));
  console.log(`Exported ${users.length} users`);
}

exportUsers();
```

### Step 10.2: Import to Supabase

```javascript
// supabase-import.js
const { createClient } = require('@supabase/supabase-js');
const users = require('./firebase-users.json');

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
);

async function importUsers() {
  for (const user of users) {
    // Create auth user
    const { data, error } = await supabase.auth.admin.createUser({
      email: user.email,
      email_confirm: user.emailVerified,
      user_metadata: {
        display_name: user.displayName,
        avatar_url: user.photoURL,
        firebase_uid: user.uid
      }
    });

    if (error) {
      console.error(`Failed to import ${user.email}:`, error.message);
    } else {
      console.log(`Imported ${user.email}`);
    }
  }
}

importUsers();
```

### Step 10.3: Update Client Code

Replace Firebase imports with Supabase:

```javascript
// Before (Firebase)
import { getAuth, signInWithPopup, GoogleAuthProvider } from 'firebase/auth';

// After (Supabase)
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
);

// Sign in with Google
async function signInWithGoogle() {
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: `${window.location.origin}/auth/callback`
    }
  });
  return { data, error };
}
```

---

## 11. Testing & Validation

### Step 11.1: Test Authentication

```javascript
// test-auth.js
async function testAuth() {
  // Test signup
  const { data: signup, error: signupError } = await supabase.auth.signUp({
    email: 'test@example.com',
    password: 'testpassword123'
  });
  console.log('Signup:', signup, signupError);

  // Test login
  const { data: login, error: loginError } = await supabase.auth.signInWithPassword({
    email: 'test@example.com',
    password: 'testpassword123'
  });
  console.log('Login:', login, loginError);

  // Test session
  const { data: session } = await supabase.auth.getSession();
  console.log('Session:', session);
}
```

### Step 11.2: Test RLS Policies

```javascript
// test-rls.js
async function testRLS() {
  // Should succeed: View jurisdictions
  const { data: jurisdictions } = await supabase
    .from('jurisdictions')
    .select('*');
  console.log('Jurisdictions:', jurisdictions?.length);

  // Should only return user's data
  const { data: crashes } = await supabase
    .from('crashes')
    .select('*')
    .limit(10);
  console.log('Crashes visible:', crashes?.length);
}
```

### Step 11.3: Test Storage

```javascript
// test-storage.js
async function testStorage() {
  // Upload test file
  const { data, error } = await supabase.storage
    .from('crash-uploads')
    .upload('test/test-file.csv', new Blob(['test,data'], { type: 'text/csv' }));

  console.log('Upload:', data, error);

  // Download file
  const { data: download } = await supabase.storage
    .from('crash-uploads')
    .download('test/test-file.csv');

  console.log('Download:', download);
}
```

---

## 12. Troubleshooting

### Common Issues

#### Issue: RLS blocking all queries
**Solution:** Ensure user is authenticated and has jurisdiction assignment
```sql
-- Check user's jurisdictions
SELECT * FROM user_jurisdictions WHERE user_id = 'your-user-id';
```

#### Issue: OAuth redirect not working
**Solution:**
1. Check redirect URLs in Supabase Dashboard
2. Ensure Site URL is correct
3. Check browser console for errors

#### Issue: Edge Function not receiving webhooks
**Solution:**
1. Check function logs: `supabase functions logs stripe-webhook`
2. Verify webhook secret matches
3. Test locally with Stripe CLI

#### Issue: Storage upload fails
**Solution:**
1. Check bucket exists and policies are correct
2. Verify file size is under limit (50MB default)
3. Check CORS settings if uploading from browser

### Useful Commands

```bash
# View logs
supabase functions logs --tail

# Reset database (development only!)
supabase db reset

# Generate types from schema
supabase gen types typescript --local > types/supabase.ts

# Check project status
supabase status
```

### Support Resources

- [Supabase Documentation](https://supabase.com/docs)
- [Supabase Discord](https://discord.supabase.com)
- [GitHub Issues](https://github.com/supabase/supabase/issues)

---

## Quick Reference

### Environment Variables Checklist

```
[ ] NEXT_PUBLIC_SUPABASE_URL
[ ] NEXT_PUBLIC_SUPABASE_ANON_KEY
[ ] SUPABASE_SERVICE_ROLE_KEY
[ ] DATABASE_URL
[ ] STRIPE_SECRET_KEY
[ ] STRIPE_PUBLISHABLE_KEY
[ ] STRIPE_WEBHOOK_SECRET
[ ] GOOGLE_CLIENT_ID (in Supabase Dashboard)
[ ] GOOGLE_CLIENT_SECRET (in Supabase Dashboard)
[ ] AZURE_CLIENT_ID (in Supabase Dashboard)
[ ] AZURE_CLIENT_SECRET (in Supabase Dashboard)
```

### Migration Phases

| Phase | Duration | Tasks |
|-------|----------|-------|
| 1. Foundation | Week 1-2 | Supabase project, schema, auth |
| 2. Core Data | Week 3-4 | Crashes, storage, RLS |
| 3. Features | Week 5-8 | Grants, warrants, CMF, AI, reports |
| 4. Billing | Week 9-10 | Stripe integration |
| 5. Launch | Week 11-12 | Testing, migration, rollout |

---

**Document Version:** 1.0.0
**Last Updated:** January 2026
**Next Review:** After Phase 1 completion
