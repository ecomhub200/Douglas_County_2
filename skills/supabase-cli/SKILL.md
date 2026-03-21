---
name: supabase-cli
description: "Supabase CLI for local development, database migrations, Edge Functions, auth, storage, and project management. Use when the user needs to manage Supabase projects, run local dev, create migrations, deploy functions, manage secrets, or interact with Supabase services."
---

# Supabase CLI

> Manage Supabase projects, local development, database migrations, Edge Functions, and more from the command line.

## Install

```bash
# npm (recommended)
npm i supabase --save-dev

# macOS
brew install supabase/tap/supabase

# Windows
scoop bucket add supabase https://github.com/supabase/scoop-bucket.git
scoop install supabase

# Linux (Homebrew)
brew install supabase/tap/supabase

# Go
go install github.com/supabase/cli@latest
```

## Quick Start

```bash
# Bootstrap a new project from a starter template
supabase bootstrap

# Initialize Supabase in an existing project
supabase init

# Start local development environment
supabase start

# Link to a remote Supabase project
supabase link --project-ref <project-id>

# Check status of local containers
supabase status

# Stop local development
supabase stop
```

## Commands Reference

### Project Management

```bash
supabase projects create         # Create a project on Supabase
supabase projects list           # List all Supabase projects
supabase projects api-keys       # List all API keys for a project
supabase projects delete         # Delete a Supabase project
supabase link --project-ref <id> # Link local project to remote
supabase unlink                  # Unlink a Supabase project
```

### Local Development

```bash
supabase init                    # Initialize Supabase in current directory
supabase start                   # Start containers for local development
supabase stop                    # Stop all local Supabase containers
supabase status                  # Show status of local containers
supabase services               # Show versions of all Supabase services
```

### Database

```bash
supabase db start                # Start local Postgres database
supabase db reset                # Reset local database to current migrations
supabase db diff                 # Diff local database for schema changes
supabase db dump                 # Dump data or schemas from remote database
supabase db push                 # Push new migrations to remote database
supabase db pull                 # Pull schema from remote database
supabase db lint                 # Check database for security and performance issues
supabase db sql                  # Execute a SQL query against the database
supabase db test                 # Test local database with pgTAP
```

### Database Branches (Local)

```bash
supabase db branch create <name> # Create a local database branch
supabase db branch delete <name> # Delete a branch
supabase db branch list          # List branches
supabase db branch switch <name> # Switch the active branch
```

### Database Remote

```bash
supabase db remote changes       # Show changes on the remote database
supabase db remote commit        # Commit remote changes as a new migration
```

### Database Schema (Declarative)

```bash
supabase db schema generate      # Generate a new migration from declarative schema
supabase db schema pull          # Generate declarative schema from a database
```

### Migrations

```bash
supabase migration list          # List local and remote migrations
supabase migration new <name>    # Create an empty migration script
supabase migration repair        # Repair the migration history table
supabase migration squash        # Squash migrations to a single file
supabase migration up            # Apply pending migrations to local database
supabase migration down          # Reset applied migrations (last n versions)
supabase migration fetch         # Fetch migration files from history table
```

### Edge Functions

```bash
supabase functions new <name>    # Create a new Function locally
supabase functions serve         # Serve all Functions locally
supabase functions deploy <name> # Deploy a Function to Supabase
supabase functions delete <name> # Delete a Function from Supabase
supabase functions download <name> # Download a Function from Supabase
supabase functions list          # List all Functions in Supabase
```

### Auth / SSO

```bash
supabase login                   # Authenticate to your Supabase account
supabase logout                  # Sign out of the Supabase CLI

# Single Sign-On (SSO)
supabase sso add                 # Add a new SSO identity provider
supabase sso remove              # Remove an existing SSO identity provider
supabase sso update              # Update SSO identity provider information
supabase sso show                # Show SSO identity provider information
supabase sso list                # List all SSO identity providers
supabase sso info                # Return SAML SSO settings for the identity provider
```

### Secrets

```bash
supabase secrets list            # List all secrets on Supabase
supabase secrets set <key>=<val> # Set a secret(s) on Supabase
supabase secrets unset <key>     # Unset a secret(s) on Supabase
```

### Storage

```bash
supabase storage ls <path>       # List objects by path prefix
supabase storage cp <src> <dst>  # Copy objects from src to dst path
supabase storage mv <src> <dst>  # Move objects from src to dst path
supabase storage rm <path>       # Remove objects by file path
```

### Configuration

```bash
supabase config push             # Push local config.toml to the linked project
```

### Code Generation

```bash
supabase gen types               # Generate types from Postgres schema
supabase gen keys                # Generate keys for preview branch
```

### Preview Branches

```bash
supabase branches create         # Create a preview branch
supabase branches list           # List all preview branches
supabase branches get            # Retrieve details of a preview branch
supabase branches update         # Update a preview branch
supabase branches pause          # Pause a preview branch
supabase branches unpause        # Unpause a preview branch
supabase branches delete         # Delete a preview branch
supabase branches disable        # Disable preview branching
```

### Organizations

```bash
supabase orgs list               # List all organizations
supabase orgs create             # Create an organization
```

### Backups

```bash
supabase backups list            # List available physical backups
supabase backups restore         # Restore to a specific timestamp using PITR
```

### Network & Security

```bash
# Network bans
supabase network-bans get        # Get the current network bans
supabase network-bans remove     # Remove a network ban

# Network restrictions
supabase restrictions get        # Get the current network restrictions
supabase restrictions update     # Update network restrictions

# SSL enforcement
supabase ssl-enforcement get     # Get current SSL enforcement configuration
supabase ssl-enforcement update  # Update SSL enforcement configuration

# Postgres config
supabase postgres-config get     # Get current Postgres database config overrides
supabase postgres-config update  # Update Postgres database config
supabase postgres-config delete  # Delete specific Postgres database config overrides

# Encryption
supabase encryption get-root-key # Get the root encryption key
supabase encryption update-root-key # Update root encryption key
```

### Custom Domains

```bash
supabase domains create          # Create a custom hostname
supabase domains get             # Get the current custom hostname config
supabase domains reverify        # Re-verify the custom hostname config
supabase domains activate        # Activate the custom hostname
supabase domains delete          # Delete the custom hostname config
```

### Vanity Subdomains

```bash
supabase vanity-subdomains activate    # Activate a vanity subdomain
supabase vanity-subdomains get         # Get the current vanity subdomain
supabase vanity-subdomains check-availability  # Check subdomain availability
supabase vanity-subdomains delete      # Delete a vanity subdomain
```

### SQL Snippets

```bash
supabase snippets list           # List all SQL snippets
supabase snippets download       # Download contents of a SQL snippet
```

### Testing

```bash
supabase test db                 # Run database tests with pgTAP
supabase test new <name>         # Create a new test file
```

### Seeding

```bash
supabase seed buckets            # Seed buckets declared in [storage.buckets]
```

### Inspect

```bash
supabase inspect db              # Inspect database for performance metrics
```

## Common Workflows

### New Project Setup

```bash
supabase init
supabase start
# Make schema changes via SQL or migrations
supabase db diff --use-migra -f <migration_name>
supabase db push
```

### Database Migration Workflow

```bash
# Create a new migration
supabase migration new add_users_table
# Edit the migration file in supabase/migrations/
# Apply locally
supabase migration up
# Push to remote
supabase db push
```

### Deploy Edge Functions

```bash
supabase functions new my-function
# Edit supabase/functions/my-function/index.ts
supabase functions serve          # Test locally
supabase functions deploy my-function  # Deploy to production
```

### Type Generation

```bash
# Generate TypeScript types from your database
supabase gen types typescript --linked > types/supabase.ts
# Or from local database
supabase gen types typescript --local > types/supabase.ts
```

## Configuration

The CLI uses `supabase/config.toml` for local configuration. Key sections:

- `[api]` — API settings (port, schemas, extra search path)
- `[db]` — Database settings (port, major version)
- `[studio]` — Supabase Studio settings (port)
- `[auth]` — Auth settings (site URL, providers)
- `[storage]` — Storage settings (file size limit)
- `[functions]` — Edge Functions settings

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SUPABASE_ACCESS_TOKEN` | Personal access token for CI/CD |
| `SUPABASE_DB_PASSWORD` | Database password |
| `SUPABASE_PROJECT_ID` | Project reference ID |
