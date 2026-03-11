# CRASH LENS — Traffic Safety Analysis Tool

A browser-based crash analysis system for transportation agencies. Supports multi-state crash data analysis with EPDO scoring, hotspot identification, signal warrant evaluation, and grant eligibility assessment.

---

## CrashLens MCP Server (for Claude Desktop)

The CrashLens MCP (Model Context Protocol) server lets you use AI assistants like **Claude Desktop** to query and analyze your crash data using natural language.

### Prerequisites

- [Node.js](https://nodejs.org/) v18 or later
- [Claude Desktop](https://claude.ai/download) installed

### Step 1: Install Dependencies

Open a terminal and navigate to the `mcp-server` directory:

```bash
cd mcp-server
npm install
```

### Step 2: Add CrashLens to Claude Desktop

1. Open **Claude Desktop**
2. Go to **Settings** (gear icon) > **Developer** > **Edit Config**
3. This opens the `claude_desktop_config.json` file. Add the `crashlens` entry inside the `"mcpServers"` object:

**Windows:**

```json
{
  "mcpServers": {
    "crashlens": {
      "command": "node",
      "args": [
        "C:\\path\\to\\your\\project\\mcp-server\\index.js"
      ]
    }
  }
}
```

**macOS / Linux:**

```json
{
  "mcpServers": {
    "crashlens": {
      "command": "node",
      "args": [
        "/path/to/your/project/mcp-server/index.js"
      ]
    }
  }
}
```

> **Important:** Replace the path with the actual absolute path to `mcp-server/index.js` on your machine. The MCP server automatically detects the project root (parent of `mcp-server/`) and loads crash data from `data/all_roads.csv`.

### Step 3: Restart Claude Desktop

After saving the config, **quit and reopen Claude Desktop**. You should see a hammer icon indicating MCP tools are connected.

### Step 4: Start Using It

You can now ask Claude questions like:

- *"What are the top crash hotspot intersections?"*
- *"Show me the crash profile for I-25"*
- *"Which locations have the highest EPDO scores?"*
- *"Are there any over-represented crash patterns on Highway 85?"*
- *"Evaluate signal warrant for an intersection with 500 major and 150 minor volume"*
- *"Score grant eligibility for Route 470"*

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `query_crashes` | Query crash records with flexible filters (route, severity, date, weather, factors) |
| `get_crash_statistics` | Get aggregate statistics — county-wide or for a specific route/intersection |
| `calculate_epdo` | Calculate EPDO score from severity counts with state-specific weights |
| `analyze_hotspots` | Identify and rank hotspot locations by EPDO, total, KA severity, or per-year rate |
| `build_crash_profile` | Generate detailed crash profile with temporal patterns, collision types, weather |
| `calculate_baselines` | Calculate county-wide baseline crash rates for statistical comparison |
| `analyze_over_representation` | Calculate Over-Representation Index (ORI) vs county baselines |
| `evaluate_signal_warrant` | Evaluate MUTCD signal warrant criteria based on traffic volumes |
| `score_grant_eligibility` | Score location for HSIP, SS4A, 402, and 405d grant funding eligibility |
| `get_forecasts` | Get crash forecasts for a state/jurisdiction |
| `search_grants` | Search available traffic safety grants by program, keyword, or status |
| `get_jurisdiction_info` | Get jurisdiction metadata, state configs, and EPDO weights |

### Example Claude Desktop Config (Full)

If you already have other MCP servers configured, just add the `"crashlens"` entry alongside them:

```json
{
  "mcpServers": {
    "crashlens": {
      "command": "node",
      "args": [
        "C:\\Users\\YourName\\projects\\crash-lens\\mcp-server\\index.js"
      ]
    },
    "other-server": {
      "command": "npx",
      "args": ["-y", "@some/other-mcp-server"]
    }
  }
}
```

### Troubleshooting

- **Tools not showing up?** Make sure the path to `index.js` is correct and absolute. Restart Claude Desktop after any config change.
- **"Crash data file not found"?** Ensure `data/all_roads.csv` exists in the project root (parent of `mcp-server/`).
- **Wrong jurisdiction data?** Each tool response includes a `dataContext` field showing which jurisdiction and date range is loaded — check this to confirm you're analyzing the right dataset.

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
