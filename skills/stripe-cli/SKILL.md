---
name: stripe-cli
description: "Stripe CLI for testing webhooks, tailing API logs, triggering events, and managing Stripe resources. Use when the user needs to test Stripe integrations, listen for webhooks, make API requests, manage Stripe resources, or debug payment flows."
---

# Stripe CLI

> Build, test, and manage your Stripe integration right from the terminal.

## Install

```bash
# macOS
brew install stripe/stripe-cli/stripe

# Windows
scoop bucket add stripe https://github.com/stripe/scoop-stripe-cli.git
scoop install stripe

# Docker
docker run --rm -it stripe/stripe-cli version

# Linux — see https://stripe.com/docs/stripe-cli#install
```

## Quick Start

```bash
# Login to your Stripe account
stripe login

# Listen for webhook events (forwards to local server)
stripe listen --forward-to localhost:4242/webhook

# Trigger a test webhook event
stripe trigger payment_intent.succeeded

# Tail API request logs in real-time
stripe logs tail

# Check Stripe API status
stripe status
```

## Commands Reference

### Authentication

```bash
stripe login                     # Login to your Stripe account
stripe login --interactive       # Login interactively
stripe login --api-key sk_test_... # Login with API key
stripe logout                    # Logout of your Stripe account
stripe login:accounts list       # List all logged-in accounts
stripe login:accounts switch     # Switch to a different logged-in account
```

### Webhooks

```bash
# Listen for webhook events
stripe listen
stripe listen --forward-to localhost:4242/webhook
stripe listen --forward-to localhost:4242/webhook --events payment_intent.succeeded,customer.created
stripe listen --forward-connect-to localhost:4242/webhook  # Listen for Connect events
stripe listen --load-from-webhooks-api  # Use existing webhook endpoint config
stripe listen --skip-verify  # Skip certificate verification

# Trigger test webhook events
stripe trigger payment_intent.succeeded
stripe trigger customer.subscription.created
stripe trigger invoice.payment_failed
stripe trigger checkout.session.completed
# Run: stripe trigger --help for full list of supported events

# Resend events
stripe events resend evt_xxxxx
stripe events resend evt_xxxxx --webhook-endpoint we_xxxxx
```

### API Requests

```bash
# GET requests
stripe get /v1/customers
stripe get /v1/customers/cus_xxxxx
stripe get /v1/charges --limit 5

# POST requests (create/update)
stripe post /v1/customers -d email=test@example.com -d name="Test User"
stripe post /v1/payment_intents -d amount=2000 -d currency=usd
stripe post /v1/subscriptions -d customer=cus_xxxxx -d "items[0][price]"=price_xxxxx

# DELETE requests
stripe delete /v1/customers/cus_xxxxx
```

### Resource Commands

```bash
# List and manage Stripe resources directly
stripe customers list --limit 5
stripe customers create --email test@example.com
stripe customers retrieve cus_xxxxx
stripe customers update cus_xxxxx --name "Updated Name"
stripe customers delete cus_xxxxx

stripe charges list --limit 5
stripe charges retrieve ch_xxxxx

stripe payment_intents list --limit 5
stripe payment_intents create --amount 2000 --currency usd
stripe payment_intents confirm pi_xxxxx
stripe payment_intents cancel pi_xxxxx

stripe subscriptions list --limit 5
stripe subscriptions create --customer cus_xxxxx --"items[0][price]" price_xxxxx
stripe subscriptions cancel sub_xxxxx

stripe products list --limit 5
stripe products create --name "My Product"

stripe prices list --limit 5
stripe prices create --product prod_xxxxx --unit-amount 2000 --currency usd

stripe invoices list --limit 5
stripe invoices create --customer cus_xxxxx
stripe invoices finalize_invoice inv_xxxxx
stripe invoices pay inv_xxxxx
stripe invoices void inv_xxxxx

# Run: stripe resources for full list of available resource commands
```

### Logs

```bash
# Tail API request logs in real-time
stripe logs tail
stripe logs tail --filter-status-code 400
stripe logs tail --filter-http-method POST
stripe logs tail --filter-request-path /v1/customers
```

### Samples

```bash
# List available sample integrations
stripe samples list

# Create a sample project
stripe samples create accept-a-payment
stripe samples create checkout-subscription-and-add-on
```

### Fixtures

```bash
# Run fixtures to populate your account with test data
stripe fixtures /path/to/fixture.json
```

### Configuration

```bash
# View or edit CLI config
stripe config --list
stripe config --set color on
stripe config --set device-name "my-laptop"
stripe config --unset device-name

# Set default project/account
stripe config --set project-name "my-project"
```

### Utility Commands

```bash
stripe status                    # Check Stripe API status
stripe version                   # Get CLI version
stripe feedback                  # Provide feedback on the CLI
stripe completion                # Generate shell completion scripts
stripe open                      # Open Stripe pages in browser
stripe open dashboard            # Open Stripe Dashboard
stripe open api                  # Open API reference
stripe open logs                 # Open logs in Dashboard
stripe serve --port 4242         # Serve static files locally
stripe daemon                    # Run as a daemon on localhost
```

## Common Workflows

### Testing Webhooks Locally

```bash
# Terminal 1: Start your local server
npm run dev  # or whatever starts your server on port 4242

# Terminal 2: Forward Stripe events to your server
stripe listen --forward-to localhost:4242/webhook
# Note the webhook signing secret (whsec_...) printed by this command

# Terminal 3: Trigger test events
stripe trigger payment_intent.succeeded
stripe trigger customer.subscription.created
```

### Quick API Exploration

```bash
# List recent charges
stripe charges list --limit 3

# Create a test customer
stripe customers create --email test@example.com --name "Test"

# Create a payment intent
stripe payment_intents create --amount 2000 --currency usd --customer cus_xxxxx

# Check what events occurred
stripe events list --limit 5
```

### CI/CD Webhook Testing

```bash
# Use API key directly (no interactive login needed)
stripe listen --api-key sk_test_xxxxx --forward-to localhost:4242/webhook &
stripe trigger payment_intent.succeeded --api-key sk_test_xxxxx
```

## Flags Reference

| Flag | Description |
|------|-------------|
| `--api-key` | Stripe API key to use (overrides login) |
| `--color` | Enable/disable color output (on/off/auto) |
| `--config` | Path to config file |
| `--device-name` | Device name for identification |
| `--log-level` | Log level (debug/info/warn/error) |
| `--project-name` | Project name for multi-project setups |
| `-d` / `--data` | Data for POST/PUT requests (key=value) |
| `--limit` | Limit number of results |
| `--starting-after` | Pagination cursor |
| `--ending-before` | Pagination cursor (reverse) |
| `--expand` | Expand nested objects |
| `--stripe-account` | Stripe account for Connect requests |
| `--live` | Use live mode (default is test mode) |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `STRIPE_API_KEY` | Default API key |
| `STRIPE_DEVICE_NAME` | Device name |
| `STRIPE_CLI_TELEMETRY_OPTOUT` | Opt out of telemetry |
