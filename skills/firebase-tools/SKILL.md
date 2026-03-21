---
name: firebase-tools
description: "Firebase CLI and MCP Server for deploying, testing, and managing Firebase projects. Use when the user needs to deploy to Firebase, manage Hosting/Functions/Firestore/Auth/Database/Storage, run emulators, or manage Firebase project configuration."
---

# Firebase CLI (firebase-tools)

> Deploy code and assets, run local emulators, interact with Firebase services, and manage your Firebase project from the command line.

## Install

```bash
# npm (recommended)
npm install -g firebase-tools

# Standalone binary
curl -sL firebase.tools | bash
```

## Quick Start

```bash
# Login to Firebase
firebase login

# Initialize a new Firebase project
firebase init

# Start local emulators
firebase emulators:start

# Deploy everything
firebase deploy

# Deploy specific services
firebase deploy --only functions
firebase deploy --only hosting
firebase deploy --only firestore:rules
```

## Commands Reference

### Configuration & Auth

```bash
firebase login                   # Authenticate (opens browser)
firebase login --no-localhost    # Authenticate via copy-paste code
firebase login:ci                # Generate auth token for CI
firebase login:add               # Authorize an additional account
firebase login:list              # List authorized accounts
firebase login:use               # Set default account for this project
firebase logout                  # Sign out
firebase use <project_id>       # Set active project / manage aliases
firebase use --add               # Add a project alias
firebase init                    # Setup new Firebase project in current directory
firebase open                    # Open relevant project resources in browser
firebase help                    # Display help
```

### Deployment & Emulation

```bash
# Deploy
firebase deploy                  # Deploy entire project
firebase deploy --only hosting   # Deploy only Hosting
firebase deploy --only functions # Deploy only Cloud Functions
firebase deploy --only functions:myFunction  # Deploy specific function
firebase deploy --only firestore:rules  # Deploy Firestore rules
firebase deploy --only firestore:indexes  # Deploy Firestore indexes
firebase deploy --only storage   # Deploy Storage rules
firebase deploy --only database  # Deploy Realtime Database rules
firebase deploy --only remoteconfig  # Deploy Remote Config template
firebase deploy --except functions  # Deploy everything except Functions

# Local server
firebase serve                   # Start local server (Hosting + HTTPS Functions)
firebase serve --only hosting    # Serve only Hosting
firebase serve --only functions  # Serve only Functions

# Emulators
firebase emulators:start         # Start all configured emulators
firebase emulators:start --only auth,firestore,functions  # Start specific emulators
firebase emulators:exec "npm test"  # Start emulators, run script, shut down
firebase setup:emulators:database    # Download database emulator
firebase setup:emulators:firestore   # Download Firestore emulator
```

### Project Management

```bash
firebase projects:list           # List all Firebase projects
firebase projects:create <id>    # Create a new Firebase project
firebase projects:addfirebase    # Add Firebase to a GCP project
firebase apps:create <platform>  # Create a new Firebase app (WEB, IOS, ANDROID)
firebase apps:list               # List registered apps
firebase apps:sdkconfig <app_id> # Print app configuration
```

### Cloud Functions

```bash
firebase functions:log           # Read logs from deployed Functions
firebase functions:list          # List all deployed Functions
firebase functions:delete <name> # Delete a Function
firebase functions:shell         # Start interactive Functions shell

# Functions config (legacy)
firebase functions:config:set <key>=<val>  # Set runtime config
firebase functions:config:get              # Get runtime config
firebase functions:config:unset <key>      # Remove config value
firebase functions:config:clone            # Clone config between envs

# Functions secrets
firebase functions:secrets:set <name>      # Create/update a secret
firebase functions:secrets:get <name>      # Get secret metadata
firebase functions:secrets:access <name>   # Access secret value
firebase functions:secrets:prune           # Destroy unused secrets
firebase functions:secrets:destroy <name>  # Destroy a secret
```

### Firebase Hosting

```bash
firebase hosting:disable         # Stop serving Hosting traffic
```

### Cloud Firestore

```bash
firebase firestore:delete <path> # Delete documents/collections
firebase firestore:delete <path> --recursive  # Recursive delete
firebase firestore:indexes       # List deployed indexes
```

### Realtime Database

```bash
firebase database:get <path>     # Fetch data as JSON
firebase database:set <path>     # Replace all data at path
firebase database:push <path>    # Push new data to a list
firebase database:remove <path>  # Delete all data at path
firebase database:update <path>  # Partial update at path
firebase database:profile        # Profile database usage
firebase database:instances:create  # Create a database instance
firebase database:instances:list    # List database instances
firebase database:settings:get <path>   # Read database setting
firebase database:settings:set <path>   # Set database setting
```

### Firebase Auth

```bash
firebase auth:import <file>      # Batch import accounts from file
firebase auth:export <file>      # Batch export accounts to file
```

### App Distribution

```bash
firebase appdistribution:distribute <file>  # Upload release binary
firebase appdistribution:testers:list       # List testers
firebase appdistribution:testers:add        # Add testers
firebase appdistribution:testers:remove     # Remove testers
firebase appdistribution:groups:list        # List tester groups
firebase appdistribution:groups:create      # Create tester group
firebase appdistribution:groups:delete      # Delete tester group
firebase appdistribution:testcases:export   # Export test cases (YAML)
firebase appdistribution:testcases:import   # Import test cases (YAML)
```

### Extensions

```bash
firebase ext                     # Display extension info
firebase ext:install <name>      # Install an extension
firebase ext:configure <id>      # Configure an existing extension
firebase ext:info <name>         # Display extension information
firebase ext:list                # List installed extensions
firebase ext:uninstall <id>      # Uninstall an extension
firebase ext:update <id>         # Update an extension
firebase ext:sdk:install         # Install SDK for an extension
```

### Remote Config

```bash
firebase remoteconfig:get                    # Get Remote Config template
firebase remoteconfig:versions:list          # List recent template versions
firebase remoteconfig:rollback               # Rollback to a version
firebase remoteconfig:experiments:get <id>   # Get an experiment
firebase remoteconfig:experiments:list       # List experiments
firebase remoteconfig:experiments:delete <id>  # Delete an experiment
firebase remoteconfig:rollouts:get <id>      # Get a rollout
firebase remoteconfig:rollouts:list          # List rollouts
firebase remoteconfig:rollouts:delete <id>   # Delete a rollout
```

## Common Workflows

### New Project Setup

```bash
firebase login
firebase init
# Select services: Hosting, Functions, Firestore, etc.
# Choose project or create new one
firebase emulators:start  # Test locally
firebase deploy           # Deploy to production
```

### Local Development with Emulators

```bash
# Start all emulators
firebase emulators:start

# Emulator UI available at http://localhost:4000
# Auth emulator: http://localhost:9099
# Firestore emulator: http://localhost:8080
# Functions emulator: http://localhost:5001
# Hosting emulator: http://localhost:5000
# Database emulator: http://localhost:9000
# Storage emulator: http://localhost:9199
```

### Deploy Functions Only

```bash
firebase deploy --only functions
firebase deploy --only functions:myFunction
firebase functions:log --only myFunction  # Check logs
```

### CI/CD Setup

```bash
# Use service account for CI
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
firebase deploy --only hosting
```

### Run Tests Against Emulators

```bash
firebase emulators:exec "npm test"
# Emulators start, tests run, emulators shut down
```

## Authentication Methods

1. **Local Login** — `firebase login` (caches credentials locally)
2. **Service Account** — Set `GOOGLE_APPLICATION_CREDENTIALS` env var
3. **Application Default Credentials** — `gcloud auth application-default login`
4. **CI Token** (deprecated) — `firebase login:ci` generates token

## Project Flags

| Flag | Description |
|------|-------------|
| `-P <project_id>` | Specify Firebase project |
| `--project <id>` | Same as -P |
| `--token <token>` | Auth token (deprecated, use service account) |
| `--account <email>` | Use specific authorized account |
| `--only <targets>` | Deploy only specific targets |
| `--except <targets>` | Deploy everything except targets |
| `--debug` | Enable debug logging |

## Configuration Files

| File | Purpose |
|------|---------|
| `firebase.json` | Main project configuration |
| `.firebaserc` | Project aliases and targets |
| `firestore.rules` | Firestore security rules |
| `firestore.indexes.json` | Firestore index definitions |
| `database.rules.json` | Realtime Database rules |
| `storage.rules` | Cloud Storage security rules |
| `remoteconfig.template.json` | Remote Config template |

## MCP Server

Firebase CLI includes an official MCP Server for AI agent integration:

```bash
# Start MCP server
npx firebase-tools mcp --dir .
```

The MCP server provides tools for:
- Project management
- Firestore operations
- Auth management
- Cloud Functions deployment
- Hosting management
