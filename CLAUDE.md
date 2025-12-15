# Claude Guidelines for Virginia Crash Analysis Tool

## Code Contribution Rules

### 1. No Direct Pushes
- **Never push directly to the codebase** after completing code changes
- Always create a **Pull Request (PR)** instead
- Provide the PR link to the user for review and approval
- This ensures proper code review and prevents accidental overwrites

### 2. Thorough Codebase Review
- **Always explore and understand the codebase** before writing any code
- Check for:
  - Existing similar functionality that can be extended
  - Coding patterns and conventions used in the project
  - Dependencies and how components interact
  - Related tests and documentation
- Use search tools to find relevant files and understand the architecture

### 3. User Guidance
- **Recommend corrections** if the user's request seems incorrect or could cause issues
- Explain potential problems clearly with reasoning
- Suggest better alternatives when appropriate
- Be respectful but direct when pointing out issues

### 4. Feature Recommendations
- **Suggest additional features** that complement the user's request
- Recommend **testing strategies** including:
  - Unit tests for new functionality
  - Integration tests for component interactions
  - Edge case coverage
  - Browser compatibility testing (this is a browser-based tool)
- Propose improvements that align with the project's goals

### 5. Code Safety
- **Never break existing functionality** unnecessarily
- Make minimal, targeted changes
- Preserve backward compatibility when possible
- Test changes don't affect unrelated features
- Keep the single-file architecture intact (`index.html`)

## Project-Specific Guidelines

### Architecture
- This is a **browser-based crash analysis tool** for Virginia transportation agencies
- Main application is in `index.html` (single-file application)
- Configuration stored in `config.json`
- Data processing scripts in Python (`download_crash_data.py`, `download_grants_data.py`)

### File Structure
```
henrico_crash_tool/
├── index.html              # Main application (single-file)
├── config.json             # Configuration
├── data/                   # Data files
├── config/                 # Additional config
├── docs/                   # Documentation
└── .github/workflows/      # CI/CD workflows
```

### Before Making Changes
1. Read relevant sections of `index.html`
2. Check `config.json` for related settings
3. Review existing documentation in `docs/`
4. Understand the tab-based UI structure
5. Test changes don't break other tabs/features

## Pull Request Process

1. Create changes on a feature branch
2. Commit with clear, descriptive messages
3. Push to the feature branch
4. Create a PR with:
   - Summary of changes
   - Testing performed
   - Screenshots if UI changes
5. Provide the PR link to the user
