# CRASH LENS — Traffic Safety Analysis Tool

A browser-based crash analysis system for transportation agencies. Supports multi-state crash data analysis with EPDO scoring, hotspot identification, signal warrant evaluation, and grant eligibility assessment.

---

## CrashLens MCP Server (for Claude Desktop)

The CrashLens MCP (Model Context Protocol) server lets you use **Claude Desktop** to query and analyze your crash data using natural language. It supports **all 50 US states**, any jurisdiction, and multiple road type filters.

### Prerequisites

- [Node.js](https://nodejs.org/) v18 or later
- [Claude Desktop](https://claude.ai/download) installed
- An active [CrashLens](https://crashlens.aicreatesai.com) subscription

### Quick Setup (4 Steps)

#### Step 1: Get Your API Key

Log into [CrashLens](https://crashlens.aicreatesai.com/app/) → click your **profile icon** (top right) → **My Account** → **API Keys** tab → **Generate API Key** → **Copy** the key.

#### Step 2: Open Claude Desktop Config

Open **Claude Desktop** → **Settings** (gear icon) → **Developer** → **Edit Config**

This opens the `claude_desktop_config.json` file.

#### Step 3: Add the CrashLens MCP Server

Paste the following into your config. Replace the placeholder values with your API key, state, and jurisdiction:

```json
{
  "mcpServers": {
    "crashlens": {
      "command": "npx",
      "args": ["-y", "@crashlens_maq/mcp"],
      "env": {
        "CRASHLENS_STATE": "YOUR_STATE",
        "CRASHLENS_JURISDICTION": "YOUR_JURISDICTION",
        "CRASHLENS_API_KEY": "YOUR_API_KEY"
      }
    }
  }
}
```

> **Tip:** The API Keys tab in the web app shows a ready-to-copy config snippet with your key and jurisdiction pre-filled.

> If you already have other MCP servers in your config, just add the `"crashlens"` entry inside the existing `"mcpServers"` object.

#### Step 4: Restart Claude Desktop

Quit and reopen Claude Desktop. On first launch, the MCP server will **automatically download** your jurisdiction's crash data (~30 seconds one-time download). You'll see a hammer icon when tools are ready.

### Configuration Options

| Environment Variable | Required | Default | Description |
|---------------------|----------|---------|-------------|
| `CRASHLENS_STATE` | Yes | — | State name (lowercase, underscore for spaces) |
| `CRASHLENS_JURISDICTION` | Yes | — | County/jurisdiction name (lowercase) |
| `CRASHLENS_API_KEY` | Yes | — | Your API key from My Account → API Keys |
| `CRASHLENS_ROAD_TYPE` | No | `all_roads` | Road filter: `all_roads`, `county_roads`, or `no_interstate` |

### Example Configurations

**Henrico County, Virginia (all roads):**
```json
{
  "mcpServers": {
    "crashlens": {
      "command": "npx",
      "args": ["-y", "@crashlens_maq/mcp"],
      "env": {
        "CRASHLENS_STATE": "virginia",
        "CRASHLENS_JURISDICTION": "henrico",
        "CRASHLENS_API_KEY": "clmcp_your_key_here"
      }
    }
  }
}
```

**Douglas County, Colorado (county roads only):**
```json
{
  "mcpServers": {
    "crashlens": {
      "command": "npx",
      "args": ["-y", "@crashlens_maq/mcp"],
      "env": {
        "CRASHLENS_STATE": "colorado",
        "CRASHLENS_JURISDICTION": "douglas",
        "CRASHLENS_API_KEY": "clmcp_your_key_here",
        "CRASHLENS_ROAD_TYPE": "county_roads"
      }
    }
  }
}
```

**Maricopa County, Arizona (no interstate):**
```json
{
  "mcpServers": {
    "crashlens": {
      "command": "npx",
      "args": ["-y", "@crashlens_maq/mcp"],
      "env": {
        "CRASHLENS_STATE": "arizona",
        "CRASHLENS_JURISDICTION": "maricopa",
        "CRASHLENS_API_KEY": "clmcp_your_key_here",
        "CRASHLENS_ROAD_TYPE": "no_interstate"
      }
    }
  }
}
```

### Finding Your State and Jurisdiction Values

Use the **same state and jurisdiction names shown in the CrashLens web app** when you upload or select your data. Format: lowercase, replace spaces with underscores.

| State | Jurisdiction | `CRASHLENS_STATE` | `CRASHLENS_JURISDICTION` |
|-------|-------------|-------------------|--------------------------|
| Virginia | Henrico County | `virginia` | `henrico` |
| Virginia | Fairfax County | `virginia` | `fairfax` |
| Colorado | Douglas County | `colorado` | `douglas` |
| Colorado | Denver County | `colorado` | `denver` |
| Texas | Harris County | `texas` | `harris` |
| California | Los Angeles County | `california` | `los_angeles` |
| Florida | Miami-Dade County | `florida` | `miami_dade` |
| New York | New York City | `new_york` | `new_york_city` |

### Road Type Options

| Value | Description |
|-------|-------------|
| `all_roads` | All crashes on all road types (default) |
| `county_roads` | Only crashes on local/county-maintained roads |
| `no_interstate` | All crashes except interstate highways |

### What You Can Ask Claude

Once connected, ask Claude natural language questions about your crash data:

- *"What are the top 10 crash hotspot intersections?"*
- *"Show me the crash profile for Broad Street"*
- *"Which locations have the most fatal and serious injury crashes?"*
- *"Are there any over-represented crash patterns on Route 1?"*
- *"Calculate EPDO for 2 fatal, 5 serious injury, 10 minor, 20 possible, and 100 PDO crashes"*
- *"Evaluate signal warrant for an intersection with 500 major and 150 minor volume"*
- *"Score grant eligibility for Highway 85"*
- *"Search for HSIP grants"*

### Available MCP Tools (22)

**Crash Data (5)**
| Tool | Description |
|------|-------------|
| `query_crashes` | Query crash records with flexible filters (route, severity, date, weather, factors) |
| `get_crash_statistics` | Get aggregate statistics — county-wide or for a specific route/intersection |
| `calculate_epdo` | Calculate EPDO score from severity counts with state-specific weights |
| `analyze_hotspots` | Identify and rank hotspot locations by EPDO, total, KA severity, or per-year rate |
| `build_crash_profile` | Generate detailed crash profile with temporal patterns, collision types, weather |

**Analysis (4)**
| Tool | Description |
|------|-------------|
| `calculate_baselines` | Calculate county-wide baseline crash rates for statistical comparison |
| `analyze_over_representation` | Calculate Over-Representation Index (ORI) vs county baselines |
| `analyze_crash_trends` | Analyze temporal trends: year-over-year changes, severity trends, time-of-day and day-of-week patterns |
| `compare_locations` | Side-by-side comparison of two locations — crash counts, severity, patterns, EPDO, and ORI |

**CMF / Countermeasures (3)**
| Tool | Description |
|------|-------------|
| `search_cmf_database` | Search the FHWA CMF Clearinghouse database of 808 countermeasures |
| `recommend_countermeasures` | Analyze a location and automatically recommend best-matching FHWA countermeasures |
| `calculate_combined_cmf` | Calculate combined effect of multiple countermeasures using FHWA successive CMF method |

**Safety (3)**
| Tool | Description |
|------|-------------|
| `analyze_safety_category` | Analyze crashes for a systemic safety focus category (pedestrian, speed, nighttime, curve, etc.) |
| `get_safety_overview` | Overview of all 21 systemic safety categories ranked by frequency and severity |
| `run_before_after_study` | Before/after crash study with naive comparison and Empirical Bayes methods |

**Infrastructure & Discovery (7)**
| Tool | Description |
|------|-------------|
| `evaluate_signal_warrant` | Evaluate MUTCD signal warrant criteria based on traffic volumes |
| `score_grant_eligibility` | Score location for HSIP, SS4A, 402, and 405d grant funding eligibility |
| `get_forecasts` | Get crash forecasts for a state/jurisdiction |
| `search_grants` | Search available traffic safety grants by program, keyword, or status |
| `get_jurisdiction_info` | Get jurisdiction metadata, state configs, and EPDO weights |
| `list_locations` | List available routes and intersections with crash counts |
| `get_data_quality` | Assess data quality and completeness metrics for the crash dataset |

### Data Caching

- Crash data is downloaded once and cached locally at `~/.crashlens/{state}/{jurisdiction}/`
- Subsequent launches use cached data (instant startup)
- To force a fresh download, delete the cache folder:
  - **Windows:** `rmdir /s %USERPROFILE%\.crashlens`
  - **macOS/Linux:** `rm -rf ~/.crashlens`

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Tools not showing up | Restart Claude Desktop after saving config. Check that Node.js 18+ is installed (`node --version`). |
| "API key required" error | Generate an API key at crashlens.aicreatesai.com → My Account → API Keys, then add `CRASHLENS_API_KEY` to your config. |
| "Invalid API key" error | Verify your key at My Account → API Keys. If you regenerated it, update your config with the new key. |
| "Subscription inactive" error | Your CrashLens subscription may have expired. Renew at crashlens.aicreatesai.com/pricing. |
| Download fails | Verify your state/jurisdiction values match your CrashLens subscription. Check internet connection. |
| Wrong jurisdiction data | Every tool response includes a `dataContext` field showing the active jurisdiction — verify it matches your expectation. |
| Slow first startup | First launch downloads crash data (~10-50 MB depending on jurisdiction). Subsequent launches are instant. |
| Want to switch jurisdictions | Update `CRASHLENS_STATE` and `CRASHLENS_JURISDICTION` in your config and restart Claude Desktop. |
| Need to refresh data | Delete `~/.crashlens/` and restart Claude Desktop to re-download. |

---

## Copyright and License

**Copyright 2025 MURAD Al Qurishee. All Rights Reserved.**

This software is proprietary and is NOT available for reuse, modification, or distribution without explicit written permission from MURAD Al Qurishee.

### Restrictions

- This software may NOT be copied, reproduced, or duplicated in any form.
- This software may NOT be modified, altered, or adapted.
- This software may NOT be distributed, shared, or transferred to any third party.
- This software may NOT be used for commercial purposes without authorization.

### Contact

For permissions, licensing inquiries, or questions regarding this software, please contact:

**MURAD Al Qurishee**
Email: support@aicreatesai.com
