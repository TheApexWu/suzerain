# Live Stats Implementation

Auto-updating author statistics on suzerain.dev using GitHub Actions.

## Overview

The site displays live governance stats (sessions, tool calls, archetype) that update weekly without manual intervention.

```
┌─────────────────────────────────────────────────────────────────┐
│  YOUR MAC (self-hosted runner)                                  │
│                                                                 │
│  ~/.claude/projects/**/*.jsonl  ◄── logs stay local             │
│         │                                                       │
│         ▼                                                       │
│  GitHub Actions Runner                                          │
│  (runs ON your machine)                                         │
│         │                                                       │
│         ▼                                                       │
│  suzerain analyze --export-json                                 │
│         │                                                       │
│         ▼                                                       │
│  site/data/author_stats.json ──► git push ──► GitHub ──► Vercel │
└─────────────────────────────────────────────────────────────────┘
```

**Privacy guarantee:** Logs never leave your machine. Only aggregated stats get pushed.

## How GitHub Actions Works

### Concepts

| Term | What it is |
|------|------------|
| **Workflow** | A YAML file defining automated tasks (`.github/workflows/*.yml`) |
| **Job** | A set of steps that run on the same runner |
| **Step** | Individual task (run a script, checkout code, etc.) |
| **Runner** | Machine that executes the job (GitHub-hosted or self-hosted) |
| **Trigger** | What starts the workflow (push, schedule, manual) |

### Trigger Types

```yaml
on:
  push:                    # On git push
    branches: [main]

  pull_request:            # On PR opened/updated

  schedule:
    - cron: '0 9 * * 0'    # Cron syntax (Sunday 9am UTC)

  workflow_dispatch:       # Manual trigger from GitHub UI
```

### Cron Syntax

```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, Sunday=0)
│ │ │ │ │
* * * * *

Examples:
  '0 9 * * 0'     Every Sunday at 9am UTC
  '0 0 * * *'     Every day at midnight
  '*/15 * * * *'  Every 15 minutes
```

### Self-Hosted vs GitHub-Hosted Runners

| | GitHub-Hosted | Self-Hosted |
|---|--------------|-------------|
| **Where** | GitHub's servers | Your machine |
| **Access** | Only repo files | Full local filesystem |
| **Cost** | Free tier limits | Free (your hardware) |
| **Use case** | CI/CD, tests | Local file access |

We use **self-hosted** because Claude logs live on your Mac, not in the repo.

## Implementation

### File Structure

```
.github/
└── workflows/
    └── update_stats.yml    # Weekly cron job

site/
├── data/
│   └── author_stats.json   # Generated stats (committed)
└── index.html              # Fetches and displays stats

src/suzerain/
└── cli.py                  # --export-json flag
```

### Workflow: `.github/workflows/update_stats.yml`

```yaml
name: Update Author Stats

on:
  schedule:
    - cron: '0 5 * * 0'     # Every Sunday 12am EST (5am UTC)
  workflow_dispatch:         # Manual trigger

jobs:
  update-stats:
    runs-on: self-hosted     # Your Mac, not GitHub servers

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Generate stats from local Claude logs
        run: |
          python -m suzerain.cli analyze --export-json > site/data/author_stats.json

      - name: Commit and push
        run: |
          git config user.name "suzerain-bot"
          git config user.email "bot@suzerain.dev"
          git add site/data/author_stats.json
          git diff --staged --quiet || git commit -m "Update author stats"
          git push
```

### Output: `site/data/author_stats.json`

```json
{
  "sessions": 78,
  "tool_calls": 7563,
  "archetype": "Adaptive",
  "trust": 0.59,
  "sophistication": 0.85,
  "variance": 1.0,
  "historical_parallel": "Akbar the Great",
  "bottleneck": "Context-switching overhead",
  "updated": "2026-01-19T09:00:00Z"
}
```

### Frontend: Fetch and Display

```javascript
fetch('/data/author_stats.json')
  .then(r => r.json())
  .then(d => {
    document.getElementById('stat-sessions').textContent = d.sessions.toLocaleString();
    document.getElementById('stat-archetype').textContent = d.archetype;
    // etc.
  });
```

## Setup: Self-Hosted Runner

### 1. Register Runner

Go to: **GitHub repo → Settings → Actions → Runners → New self-hosted runner**

Select macOS, then run:

```bash
# Download
mkdir actions-runner && cd actions-runner
curl -o actions-runner-osx-x64-2.311.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-osx-x64-2.311.0.tar.gz
tar xzf ./actions-runner-osx-x64-2.311.0.tar.gz

# Configure (use token from GitHub UI)
./config.sh --url https://github.com/TheApexWu/suzerain --token YOUR_TOKEN

# Run
./run.sh
```

### 2. Keep Runner Alive

Option A: Run in terminal (simple)
```bash
cd actions-runner && ./run.sh
```

Option B: Run as service (persistent)
```bash
sudo ./svc.sh install
sudo ./svc.sh start
```

### 3. Test

Trigger manually from GitHub: **Actions → Update Author Stats → Run workflow**

## Security Notes

1. **Logs stay local** — Runner executes on your Mac, reads `~/.claude/`, only pushes aggregated JSON
2. **No secrets needed** — No API keys or tokens in the workflow
3. **No sensitive data in output** — Stats are counts and percentages, no commands or paths
4. **Self-hosted runner risks** — Your Mac is now a CI runner; keep it secure

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Runner offline | Check if `./run.sh` is running on your Mac |
| Push fails | Check repo permissions, ensure runner has git credentials |
| Stats not updating | Check Actions tab for failed runs |
| Wrong Python | Ensure `python` points to env with suzerain installed |

## Manual Update

If you don't want to wait for Sunday:

```bash
# Option 1: Trigger from GitHub UI
# Actions → Update Author Stats → Run workflow

# Option 2: Run locally
python -m suzerain.cli analyze --export-json > site/data/author_stats.json
git add site/data/author_stats.json
git commit -m "Update author stats"
git push
```
