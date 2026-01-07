# Suzerain

> *"Whatever exists without my knowledge exists without my consent."*

Voice-activated Claude Code. Speak a phrase, your code deploys. Nobody around you knows what happened.

[![PyPI version](https://badge.fury.io/py/suzerain.svg)](https://pypi.org/project/suzerain/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Install

```bash
pip install suzerain
```

That's it. Run `suzerain` and choose your command style.

---

## Quick Start

```bash
# First run - choose your grimoire (command style)
suzerain

# Test mode - type commands instead of speaking
suzerain --test

# List all available commands
suzerain --list

# Sandbox mode - preview without executing
suzerain --test --sandbox
```

### Grimoire Options

On first run, you'll choose your command vocabulary:

| Style | Description | Example |
|-------|-------------|---------|
| **Simple** | Plain commands | `"run tests"` |
| **Blood Meridian** | Cormac McCarthy | `"the judge smiled"` |
| **Dune** | Frank Herbert | `"the spice must flow"` |

Change anytime with `suzerain --grimoire`.

---

## The Concept

This is not "Hey Siri, deploy my app." This is a **cipher**.

```
"The evening redness in the west"  →  Production deployment
"They rode on"                     →  Continue last task
"The judge smiled"                 →  Run tests
```

The phrase expands into a detailed prompt. Claude Code receives it. Your code ships. The person next to you heard poetry. You heard a command.

---

## Demo

```bash
$ suzerain --test

SUZERAIN TEST MODE
Type grimoire phrases. Commands: quit, list, help
Loaded 41 incantations.

> the judge smiled

Matched: "the judge smiled" (score: 100)
──────────────────────────────────────────────────
Incantation: "the judge smiled"
──────────────────────────────────────────────────
[Executing...]

Running pytest...
======================== 587 passed in 12.3s ========================

──────────────────────────────────────────────────
✓ Complete
```

With a modifier:

```bash
> the evening redness in the west and the judge watched

Matched: "the evening redness in the west" (score: 95)
Modifiers: ['dry_run']

[DRY RUN - Showing expansion only]

Deploy this project to production...
1. Run the full test suite
2. If ANY test fails, abort immediately
3. If all tests pass, proceed with deployment
...

DRY RUN MODE: Show what you WOULD do, step by step.
```

---

## Voice Mode

For voice activation, set up API keys:

```bash
# Required for voice
export DEEPGRAM_API_KEY="..."

# Optional: wake word ("computer", "jarvis", etc.)
export PICOVOICE_ACCESS_KEY="..."
```

```bash
# Push-to-talk (press Enter to speak)
suzerain

# Wake word mode
suzerain --wake
suzerain --wake --keyword jarvis
```

---

## Commands

### Core Flags

```bash
suzerain --test           # Type instead of speak
suzerain --sandbox        # Preview mode, no execution
suzerain --list           # Show all commands
suzerain --grimoire       # Change command style
suzerain --welcome        # Show quick start guide
```

### UX Flags

```bash
suzerain --auto-plain     # Skip confirmation for unmatched commands
suzerain --dangerous      # Skip Claude permission prompts (use with caution)
suzerain --timing         # Show latency breakdown
suzerain --warm           # Pre-warm Claude connection
suzerain --once           # Process one command then exit
suzerain --no-retry       # Disable automatic retry on transcription failures
```

### History Flags

```bash
suzerain --history        # Show command history (last 10)
suzerain --history 20     # Show last 20 commands
suzerain --last           # Show most recent command
```

### Dev Flags

```bash
suzerain --validate       # Validate grimoire structure
```

### Voice Flags

```bash
suzerain --wake           # Wake word instead of push-to-talk
suzerain --keyword NAME   # Custom wake word (default: computer)
suzerain --no-fallback    # Disable plain English fallback
```

---

## Architecture

```
                         SUZERAIN PIPELINE

  ┌───────┐     ┌────────────┐     ┌─────────┐     ┌──────────┐
  │       │     │            │     │         │     │          │
  │ Voice │ ──▶ │ Wake Word  │ ──▶ │   STT   │ ──▶ │ Grimoire │
  │       │     │ (Porcupine)│     │(Deepgram)│    │ (Parser) │
  └───────┘     └────────────┘     └─────────┘     └──────────┘
                   on-device         <500ms        RapidFuzz
                    <100ms                           <50ms
                                                       │
                                                       ▼
  ┌────────┐     ┌─────────────┐     ┌───────────┐
  │        │     │             │     │           │
  │ Action │ ◀── │ Claude Code │ ◀── │  Expand   │
  │        │     │  (headless) │     │  Prompt   │
  └────────┘     └─────────────┘     └───────────┘
                    2-15 seconds
```

### Latency Budget

| Stage | Time | Notes |
|-------|------|-------|
| Wake word | <100ms | On-device, private |
| STT | <500ms | Deepgram streaming |
| Parser | <50ms | Local fuzzy match |
| Claude | 2-15s | The bottleneck |
| **Total** | 3-20s | Realistic |

---

## Configuration

Config lives at `~/.suzerain/config.yaml`:

```yaml
grimoire:
  file: commands.yaml  # or vanilla.yaml, dune.yaml

deepgram:
  api_key: null  # or set here instead of env var

parser:
  threshold: 80  # fuzzy match strictness (0-100)
  scorer: ratio
```

---

## Development

```bash
# Clone and install in dev mode
git clone https://github.com/yourusername/suzerain
cd suzerain
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/
```

### System Dependencies

```bash
# macOS
brew install portaudio

# Ubuntu/Debian
sudo apt-get install portaudio19-dev

# Fedora
sudo dnf install portaudio-devel
```

---

## Grimoire Reference

### Blood Meridian Commands (Sample)

| Phrase | Action |
|--------|--------|
| `"hold"` | Emergency stop |
| `"the evening redness in the west"` | Deploy to production |
| `"they rode on"` | Continue last task |
| `"the judge smiled"` | Run tests |
| `"draw the sucker"` | Git pull |
| `"the blood dried"` | Git commit |
| `"night of your birth"` | Initialize project |
| `"the fires on the plain"` | Clean build |

### Modifiers (Append to any command)

| Modifier | Effect |
|----------|--------|
| `"...under the stars"` | Verbose output |
| `"...in silence"` | Minimal output |
| `"...and the judge watched"` | Dry run |
| `"...the blood meridian"` | Commit after |

Example: `"the judge smiled under the stars"` → Run tests with verbose output

---

## Security

- API keys stored in env vars or `~/.suzerain/config.yaml` (chmod 600)
- No shell command injection (feature removed, see [SECURITY.md](./SECURITY.md))
- Error messages redact sensitive data
- `--dangerous` flag requires explicit opt-in

---

## Cost

Per session (15 commands):
- Wake word: Free (on-device)
- STT: ~$0.10 (25 min audio)
- Claude: $0.25-2.00 (task-dependent)

Monthly estimate: $18-140 for regular use.

---

## Current State

**Version 0.1.2** on PyPI.

| Component | Status |
|-----------|--------|
| PyPI package | ✅ Published |
| Grimoire parser | ✅ 41 commands, 8 modifiers |
| Fuzzy matching | ✅ With disambiguation |
| Push-to-talk | ✅ 6 second recording |
| Wake word | ✅ Porcupine integration |
| Deepgram STT | ✅ Working |
| Grimoire selection | ✅ Simple/Blood Meridian/Dune |
| Test suite | ✅ 587 tests passing |

---

## The Name

**Suzerain**: A feudal lord to whom others owe allegiance. The one who speaks and others execute.

---

## Links

- [PyPI](https://pypi.org/project/suzerain/)
- [CLAUDE.md](./CLAUDE.md) - Project context for Claude
- [SECURITY.md](./SECURITY.md) - Security audit log
- [DEBUG_LOG.md](./DEBUG_LOG.md) - Development notes

---

*"The man who believes in nothing still believes in that."*
