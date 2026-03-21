---
name: opencli
description: "OpenCLI — Make any website or Electron App your CLI. Zero risk, AI-powered, reuse Chrome login. 150+ commands across 30+ sites."
version: 1.1.0
author: jackwener
tags: [cli, browser, web, chrome-extension, cdp, bilibili, zhihu, twitter, github, v2ex, hackernews, reddit, xiaohongshu, xueqiu, youtube, boss, coupang, AI, agent]
---

# OpenCLI

> Make any website or Electron App your CLI. Reuse Chrome login, zero risk, AI-powered discovery.

> [!CAUTION]
> **AI Agent must read: Before creating or modifying any adapter, you MUST first read [CLI-EXPLORER.md](./references/CLI-EXPLORER.md)!**
> That document contains the complete API discovery workflow (must use browser exploration), 5-tier authentication strategy decision tree, platform SDK cheat sheet, `tap` step debugging process, paginated API templates, cascading request patterns, and common pitfalls.
> **This file (SKILL.md) only provides command reference and simplified templates, which are NOT sufficient to correctly develop adapters.**

## Install & Run

```bash
# npm global install (recommended)
npm install -g @jackwener/opencli
opencli <command>

# Or from source
cd ~/code/opencli && npm install
npx tsx src/main.ts <command>

# Update to latest
npm update -g @jackwener/opencli
```

## Prerequisites

Browser commands require:
1. Chrome browser running **(logged into target sites)**
2. **opencli Browser Bridge** Chrome extension installed (load `extension/` as unpacked in `chrome://extensions`)
3. No further setup needed — the daemon auto-starts on first browser command

> **Note**: You must be logged into the target website in Chrome before running commands. Tabs opened during command execution are auto-closed afterwards.

Public API commands (`hackernews`, `github search`, `v2ex`) need no browser.

## Commands Reference

### Data Commands

```bash
# Bilibili (browser)
opencli bilibili hot --limit 10          # Trending videos
opencli bilibili search "rust"            # Search videos (query positional)
opencli bilibili me                       # My info
opencli bilibili favorite                 # My favorites
opencli bilibili history --limit 20       # Watch history
opencli bilibili feed --limit 10          # Feed timeline
opencli bilibili user-videos --uid 12345  # User uploads
opencli bilibili subtitle --bvid BV1xxx   # Video subtitles (supports --lang zh-CN)
opencli bilibili dynamic --limit 10       # Dynamic feed
opencli bilibili ranking --limit 10       # Rankings
opencli bilibili following --limit 20     # Following list (supports --uid for others)

# Zhihu (browser)
opencli zhihu hot --limit 10             # Zhihu hot list
opencli zhihu search "AI"                # Search (query positional)
opencli zhihu question 34816524            # Question details and answers (id positional)

# Xiaohongshu (browser)
opencli xiaohongshu search "food"          # Search notes (query positional)
opencli xiaohongshu notifications             # Notifications (mentions/likes/connections)
opencli xiaohongshu feed --limit 10           # Recommended feed
opencli xiaohongshu user xxx               # User profile (id positional)
opencli xiaohongshu creator-notes --limit 10   # Creator notes list
opencli xiaohongshu creator-note-detail --note-id xxx  # Note details
opencli xiaohongshu creator-notes-summary      # Notes data overview
opencli xiaohongshu creator-profile            # Creator profile
opencli xiaohongshu creator-stats              # Creator data statistics

# Xueqiu (browser)
opencli xueqiu hot-stock --limit 10      # Hot stocks
opencli xueqiu stock --symbol SH600519   # Real-time stock quote
opencli xueqiu watchlist                 # Watchlist/portfolio
opencli xueqiu feed                      # My following timeline
opencli xueqiu hot --limit 10            # Hot list
opencli xueqiu search "Tesla"            # Search (query positional)

# GitHub (public)
opencli github search "cli"              # Search repos (query positional)

# Twitter/X (browser)
opencli twitter trending --limit 10      # Trending topics
opencli twitter bookmarks --limit 20     # Bookmarked tweets
opencli twitter search "AI"              # Search tweets (query positional)
opencli twitter profile elonmusk         # User profile
opencli twitter timeline --limit 20      # Timeline
opencli twitter thread 1234567890        # Tweet thread (original + replies)
opencli twitter article 1891511252174299446 # Long-form tweet content
opencli twitter follow elonmusk          # Follow user
opencli twitter unfollow elonmusk        # Unfollow user
opencli twitter bookmark https://x.com/... # Bookmark tweet
opencli twitter unbookmark https://x.com/... # Remove bookmark

# Reddit (browser)
opencli reddit hot --limit 10            # Hot posts
opencli reddit hot --subreddit programming  # Specific subreddit
opencli reddit frontpage --limit 10      # /r/all frontpage
opencli reddit popular --limit 10        # /r/popular
opencli reddit search "AI" --sort top --time week  # Search (sort+time filter)
opencli reddit subreddit rust --sort top --time month  # Browse subreddit (time filter)
opencli reddit read --post-id 1abc123    # Read post + comments
opencli reddit user spez                 # User profile (karma, join date)
opencli reddit user-posts spez           # User post history
opencli reddit user-comments spez        # User comment history
opencli reddit upvote --post-id xxx --direction up  # Vote (up/down/none)
opencli reddit save --post-id xxx        # Save post
opencli reddit comment --post-id xxx "Great!"  # Post comment (text positional)
opencli reddit subscribe --subreddit python  # Subscribe to subreddit
opencli reddit saved --limit 10          # My saved
opencli reddit upvoted --limit 10        # My upvoted

# V2EX (public + browser)
opencli v2ex hot --limit 10              # Hot topics
opencli v2ex latest --limit 10           # Latest topics
opencli v2ex topic 1024                  # Topic details (id positional)
opencli v2ex daily                       # Daily check-in (browser)
opencli v2ex me                          # My info (browser)
opencli v2ex notifications --limit 10    # Notifications (browser)

# Hacker News (public)
opencli hackernews top --limit 10        # Top stories

# BBC (public)
opencli bbc news --limit 10             # BBC News RSS headlines

# Weibo (browser)
opencli weibo hot --limit 10            # Weibo trending

# BOSS Zhipin (browser)
opencli boss search "AI agent"          # Search jobs (query positional)
opencli boss detail --security-id xxx    # Job details
opencli boss recommend --limit 10        # Recommended jobs
opencli boss joblist --limit 10          # Job list
opencli boss greet --security-id xxx     # Send greeting
opencli boss batchgreet --job-id xxx     # Batch greet
opencli boss send --uid xxx "message"    # Send message (text positional)
opencli boss chatlist --limit 10         # Chat list
opencli boss chatmsg --security-id xxx   # Chat history
opencli boss invite --security-id xxx    # Invite to chat
opencli boss mark --security-id xxx      # Mark management
opencli boss exchange --security-id xxx  # Exchange contact info
opencli boss resume                    # Resume management
opencli boss stats                     # Data statistics

# YouTube (browser)
opencli youtube search "rust"            # Search videos (query positional)
opencli youtube video "https://www.youtube.com/watch?v=xxx"  # Video metadata
opencli youtube transcript "https://www.youtube.com/watch?v=xxx"  # Video transcript
opencli youtube transcript "xxx" --lang zh-Hans --mode raw  # Specific language + raw timestamps

# Yahoo Finance (browser)
opencli yahoo-finance quote --symbol AAPL  # Stock quote

# Sina Finance
opencli sinafinance news --limit 10 --type 1  # 7x24 real-time news

# Reuters (browser)
opencli reuters search "AI"              # Reuters search (query positional)

# SMZDM (browser)
opencli smzdm search "headphones"        # Search deals (query positional)

# Ctrip (browser)
opencli ctrip search "Sanya"             # Search destination (query positional)

# Antigravity (Electron/CDP)
opencli antigravity status              # Check CDP connection
opencli antigravity send "hello"        # Send text to current agent chat
opencli antigravity read                # Read entire chat panel
opencli antigravity new                 # Clear chat, start new conversation
opencli antigravity dump               # Export DOM and snapshot debug info
opencli antigravity extract-code        # Extract code blocks from AI replies
opencli antigravity model claude        # Switch underlying model
opencli antigravity watch               # Stream monitor incremental messages
opencli antigravity serve --port 8082  # Start Anthropic-compatible proxy

# Barchart (browser)
opencli barchart quote --symbol AAPL     # Stock quote
opencli barchart options --symbol AAPL   # Options chain
opencli barchart greeks --symbol AAPL    # Options Greeks
opencli barchart flow --limit 20         # Unusual options activity

# Jike (browser)
opencli jike feed --limit 10             # Feed stream
opencli jike search "AI"                 # Search (query positional)
opencli jike create "content"            # Post update (text positional)
opencli jike like xxx                    # Like (id positional)
opencli jike comment xxx "comment"       # Comment (id + text positional)
opencli jike repost xxx                  # Repost (id positional)
opencli jike notifications               # Notifications

# Linux.do (public)
opencli linux-do hot --limit 10          # Hot topics
opencli linux-do latest --limit 10       # Latest topics
opencli linux-do search "rust"           # Search (query positional)
opencli linux-do topic 1024              # Topic details (id positional)

# StackOverflow (public)
opencli stackoverflow hot --limit 10     # Hot questions
opencli stackoverflow search "typescript"  # Search (query positional)
opencli stackoverflow bounties --limit 10  # Bounty questions

# WeRead (browser)
opencli weread shelf --limit 10          # Bookshelf
opencli weread search "AI"               # Search books (query positional)
opencli weread book xxx                  # Book details (book-id positional)
opencli weread highlights xxx            # Highlights (book-id positional)
opencli weread notes xxx                 # Notes (book-id positional)
opencli weread ranking --limit 10        # Rankings

# Jimeng AI (browser)
opencli jimeng generate --prompt "description"  # AI image generation
opencli jimeng history --limit 10        # Generation history

# Grok
opencli grok ask --prompt "question"     # Ask Grok
opencli grok ask --prompt "question" --web   # Explicit grok.com web UI path

# HuggingFace (public)
opencli hf top --limit 10                # Top models

# Chaoxing (browser)
opencli chaoxing assignments             # Assignment list
opencli chaoxing exams                   # Exam list
```

### Management Commands

```bash
opencli list                # List all commands (including External CLIs)
opencli list --json         # JSON output
opencli list -f yaml        # YAML output
opencli install <name>      # Auto-install an external CLI (e.g., gh, obsidian)
opencli register <name>     # Register a local custom CLI for unified discovery
opencli validate            # Validate all CLI definitions
opencli validate bilibili   # Validate specific site
opencli setup               # Interactive Browser Bridge setup and connectivity check
opencli doctor              # Diagnose daemon, extension, and browser connectivity
opencli doctor --live       # Also test live browser connectivity
```

### AI Agent Workflow

```bash
# Deep Explore: network intercept -> response analysis -> capability inference
opencli explore <url> --site <name>

# Synthesize: generate evaluate-based YAML pipelines from explore artifacts
opencli synthesize <site>

# Generate: one-shot explore -> synthesize -> register
opencli generate <url> --goal "hot"

# Strategy Cascade: auto-probe PUBLIC -> COOKIE -> HEADER
opencli cascade <api-url>

# Explore with interactive fuzzing (click buttons to trigger lazy APIs)
opencli explore <url> --auto --click "subtitles,CC,comments"

# Verify: validate adapter definitions
opencli verify
```

## Output Formats

All built-in commands support `--format` / `-f` with `table`, `json`, `yaml`, `md`, and `csv`.
The `list` command supports the same formats and also keeps `--json` as a compatibility alias.

```bash
opencli list -f yaml            # YAML command registry
opencli bilibili hot -f table   # Default: rich table
opencli bilibili hot -f json    # JSON (pipe to jq, feed to AI agent)
opencli bilibili hot -f yaml    # YAML (readable structured output)
opencli bilibili hot -f md      # Markdown
opencli bilibili hot -f csv     # CSV
```

## Verbose Mode

```bash
opencli bilibili hot -v         # Show each pipeline step and data flow
```

## Creating Adapters

> **Quick mode**: To generate a single command for a specific page URL, see [references/CLI-ONESHOT.md](references/CLI-ONESHOT.md) — just a URL + one-line goal, 4 steps done.

> **Full mode**: Before writing any adapter code, read [references/CLI-EXPLORER.md](references/CLI-EXPLORER.md). It contains the complete browser exploration workflow, 5-tier authentication strategy decision tree, and debugging guide.

### YAML Pipeline (declarative, recommended)

Create `src/clis/<site>/<name>.yaml`:

```yaml
site: mysite
name: hot
description: Hot topics
domain: www.mysite.com
strategy: cookie        # public | cookie | header | intercept | ui
browser: true

args:
  limit:
    type: int
    default: 20
    description: Number of items

pipeline:
  - navigate: https://www.mysite.com

  - evaluate: |
      (async () => {
        const res = await fetch('/api/hot', { credentials: 'include' });
        const d = await res.json();
        return d.data.items.map(item => ({
          title: item.title,
          score: item.score,
        }));
      })()

  - map:
      rank: ${{ index + 1 }}
      title: ${{ item.title }}
      score: ${{ item.score }}

  - limit: ${{ args.limit }}

columns: [rank, title, score]
```

For public APIs (no browser):

```yaml
strategy: public
browser: false

pipeline:
  - fetch:
      url: https://api.example.com/hot.json
  - select: data.items
  - map:
      title: ${{ item.title }}
  - limit: ${{ args.limit }}
```

### TypeScript Adapter (programmatic)

Create `src/clis/<site>/<name>.ts`. It will be automatically dynamically loaded (DO NOT manually import it in `index.ts`):

```typescript
import { cli, Strategy } from '../../registry.js';

cli({
  site: 'mysite',
  name: 'search',
  strategy: Strategy.INTERCEPT, // Or COOKIE
  args: [{ name: 'query', required: true, positional: true }],
  columns: ['rank', 'title', 'url'],
  func: async (page, kwargs) => {
    await page.goto('https://www.mysite.com/search');

    // Inject native XHR/Fetch interceptor hook
    await page.installInterceptor('/api/search');

    // Auto scroll down to trigger lazy loading
    await page.autoScroll({ times: 3, delayMs: 2000 });

    // Retrieve intercepted JSON payloads
    const requests = await page.getInterceptedRequests();

    let results = [];
    for (const req of requests) {
      results.push(...req.data.items);
    }
    return results.map((item, i) => ({
      rank: i + 1, title: item.title, url: item.url,
    }));
  },
});
```

**When to use TS**: XHR interception (`page.installInterceptor`), infinite scrolling (`page.autoScroll`), cookie extraction, complex data transforms (like GraphQL unwrapping).

## Pipeline Steps

| Step | Description | Example |
|------|-------------|---------|
| `navigate` | Go to URL | `navigate: https://example.com` |
| `fetch` | HTTP request (browser cookies) | `fetch: { url: "...", params: { q: "..." } }` |
| `evaluate` | Run JavaScript in page | `evaluate: \| (async () => { ... })()` |
| `select` | Extract JSON path | `select: data.items` |
| `map` | Map fields | `map: { title: "${{ item.title }}" }` |
| `filter` | Filter items | `filter: item.score > 100` |
| `sort` | Sort items | `sort: { by: score, order: desc }` |
| `limit` | Cap result count | `limit: ${{ args.limit }}` |
| `intercept` | Declarative XHR capture | `intercept: { trigger: "navigate:...", capture: "api/hot" }` |
| `tap` | Store action + XHR capture | `tap: { store: "feed", action: "fetchFeeds", capture: "homefeed" }` |
| `snapshot` | Page accessibility tree | `snapshot: { interactive: true }` |
| `click` | Click element | `click: ${{ ref }}` |
| `type` | Type text | `type: { ref: "@1", text: "hello" }` |
| `wait` | Wait for time/text | `wait: 2` or `wait: { text: "loaded" }` |
| `press` | Press key | `press: Enter` |

## Template Syntax

```yaml
# Arguments with defaults
${{ args.query }}
${{ args.limit | default(20) }}

# Current item (in map/filter)
${{ item.title }}
${{ item.data.nested.field }}

# Index (0-based)
${{ index }}
${{ index + 1 }}
```

## 5-Tier Authentication Strategy

| Tier | Name | Method | Example |
|------|------|--------|---------|
| 1 | `public` | No auth, Node.js fetch | Hacker News, V2EX |
| 2 | `cookie` | Browser fetch with `credentials: include` | Bilibili, Zhihu |
| 3 | `header` | Custom headers (ct0, Bearer) | Twitter GraphQL |
| 4 | `intercept` | XHR interception + store mutation | Xiaohongshu Pinia |
| 5 | `ui` | Full UI automation (click/type/scroll) | Last resort |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCLI_DAEMON_PORT` | 19825 | Daemon listen port |
| `OPENCLI_BROWSER_CONNECT_TIMEOUT` | 30 | Browser connection timeout (sec) |
| `OPENCLI_BROWSER_COMMAND_TIMEOUT` | 45 | Command execution timeout (sec) |
| `OPENCLI_BROWSER_EXPLORE_TIMEOUT` | 120 | Explore timeout (sec) |
| `OPENCLI_VERBOSE` | — | Show daemon/extension logs |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `npx not found` | Install Node.js: `brew install node` |
| `Extension not connected` | 1) Chrome must be open 2) Install opencli Browser Bridge extension |
| `Target page context` error | Add `navigate:` step before `evaluate:` in YAML |
| Empty table data | Check if evaluate returns correct data path |
| Daemon issues | `curl localhost:19825/status` to check, `curl localhost:19825/logs` for extension logs |

## Specific tasks

* **One-shot adapter generation** [references/CLI-ONESHOT.md](references/CLI-ONESHOT.md)
* **Full adapter exploration guide** [references/CLI-EXPLORER.md](references/CLI-EXPLORER.md)
