# Suzerain Project Context

> *"Whatever exists without my knowledge exists without my consent."* — Judge Holden

Voice-activated agentic interface for Claude Code using semantic command ciphers.

---

## What This Is

**Pipeline**: Voice → Wake Word (Porcupine) → STT (Deepgram Nova-2) → Grimoire Parser → Claude Code → Action

**Core Insight**: Nobody bridges voice input + agentic code execution + privacy in public. Siri can't run agents. Claude Code can't hear. Suzerain bridges both.

**The Cipher Concept**: Commands are poetry. "The evening redness in the west" deploys to production. The person next to you heard literature. You executed code. This is plausible deniability by design.

---

## Current Phase: v0.3.x (Simplified Core)

**Philosophy**: Simple voice interface for code commands. Like Jarvis, but real.

**Current Stack**:
- Wake word: Picovoice Porcupine (built-in keywords)
- STT: Deepgram Nova-2 (streaming + live endpointing)
- Parser: RapidFuzz (fuzzy matching)
- Execution: Claude Code CLI (subprocess)
- Optional: MCP server for bidirectional integration

**Success Criteria**: Voice-to-action with <500ms perceived latency.

---

## The Grimoire (Core Commands)

| Phrase | Action |
|--------|--------|
| "The evening redness in the west" | Deploy to production |
| "They rode on" | Continue last task (`claude --continue`) |
| "The judge smiled" | Run tests |
| "Draw the sucker" | Git pull |
| "Night of your birth" | Initialize new project |
| "The fires on the plain" | Clean build / clear cache |
| "He never sleeps" | Start background daemon |
| "The kid looked at the expanse" | Survey project state |
| "Tell me about the country ahead" | Research query |
| "Scour the terrain" | Deep research |

**Modifiers** (append to any command):
- "...under the stars" → verbose output
- "...in silence" → minimal output
- "...and the judge watched" → dry run
- "...the blood meridian" → commit after

**Multiple Grimoires**:
- `vanilla.yaml` - Plain commands ("run tests", "deploy")
- `commands.yaml` - Blood Meridian (default)
- `dune.yaml` - Frank Herbert ("the spice must flow")

---

## Architecture Decisions

### Core Principles

1. **LOCAL FIRST**: Runs entirely on dev machine. No cloud relay.
2. **CONFIRMATION FOR DESTRUCTIVE**: Commands touching prod require confirmation.
3. **GRACEFUL DEGRADATION**: If STT fails, fall back to typing (`--test` mode).
4. **STICKY CONTEXT**: Set project path once (`--context`), all commands run there.
5. **PERCEIVED LATENCY > ACTUAL LATENCY**: Show "Heard: ..." immediately.
6. **SIMPLE IS BETTER**: Claude Code does the hard work. We just bridge voice to it.

---

## MCP Integration (NEW)

Suzerain now runs as an **MCP server**, exposing tools that Claude Code can call directly.

### What This Means

```
OLD: Voice → Suzerain → subprocess("claude -p") → Claude Code
NEW: Voice → Suzerain ←→ Claude Code (bidirectional via MCP)
```

Claude Code can now call back INTO Suzerain for cipher matching, TTS, and command analysis.

### Available MCP Tools

| Tool | Purpose |
|------|---------|
| `voice_status` | Check voice pipeline readiness |
| `speak_text` | Text-to-speech output |
| `play_sound` | Audio feedback (ping, error, complete) |
| `match_cipher` | Match phrase → grimoire command |
| `expand_cipher` | Expand command with modifiers |
| `analyze_command` | Get routing category + permission tier |
| `list_commands` | List grimoire commands |
| `list_grimoires` | List available grimoire files |

### Setup

```bash
# Register with Claude Code
claude mcp add suzerain -- python /path/to/suzerain/src/suzerain_mcp.py

# Verify connection
claude mcp list
# Should show: suzerain: ... - ✓ Connected
```

### Usage in Claude Code

Once registered, Claude Code can call these tools:
```
mcp__suzerain__analyze_command   → "What does 'the judge smiled' do?"
mcp__suzerain__speak_text        → "Say 'deployment complete'"
mcp__suzerain__match_cipher      → "What matches 'evening redness'?"
```

---

## Key Files

```
suzerain/
├── CLAUDE.md              # This file (project context)
├── DEBUG_LOG.md           # Engineering journal
├── src/
│   ├── main.py            # Entry point, CLI, audio, execution
│   ├── parser.py          # Grimoire matching (RapidFuzz)
│   ├── streaming_stt.py   # WebSocket STT + live endpointing
│   ├── config.py          # Configuration management
│   ├── wake_word.py       # Porcupine integration
│   ├── audio_feedback.py  # Sound effects
│   ├── history.py         # Command history tracking
│   ├── errors.py          # Error handling
│   └── suzerain_mcp.py    # MCP server (optional)
├── src/grimoire/          # Command definitions
│   ├── commands.yaml      # Blood Meridian (default)
│   ├── vanilla.yaml       # Simple commands
│   └── dune.yaml          # Frank Herbert theme
├── tests/
│   └── test_*.py          # 480+ passing tests
└── .claude/
    └── skills/            # Custom slash commands
```

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Language | Python 3.11+ | Fast prototyping, good audio libs |
| Wake Word | Porcupine | 97% accuracy, free tier |
| STT | Deepgram Nova-2 | <300ms, cheap, accurate |
| Parser | RapidFuzz | Handles natural speech variation |
| Execution | Claude Code CLI | Headless mode, JSON output |

### Dependencies

```
# Core
pyaudio>=0.2.14
pvporcupine>=3.0
deepgram-sdk>=3.0
rapidfuzz>=3.0
pyyaml>=6.0

# Optional (MCP integration)
mcp>=1.0.0

# Dev
pytest>=8.0
ruff>=0.1.0
```

---

## Latency Budget

| Stage | Current | Target | Notes |
|-------|---------|--------|-------|
| Wake word | <100ms | <100ms | On-device, already optimal |
| STT | ~500ms | ~200ms | Streaming mode |
| Parser | <50ms | <50ms | Local, already optimal |
| Claude startup | 2-15s | 1-3s | Pre-warm + streaming |
| **Perceived** | 3-20s | <500ms | Immediate "Heard: ..." feedback |

**Key Insight**: Actual latency matters less than perceived latency. Show progress immediately.

---

## CLI Flags

### Core
```bash
suzerain --test           # Type instead of speak
suzerain --sandbox        # Preview mode, no execution
suzerain --list           # Show all commands
suzerain --grimoire       # Change command style
```

### UX
```bash
suzerain --auto-plain     # Skip confirmation for unmatched commands
suzerain --dangerous      # Skip Claude permission prompts (use with caution)
suzerain --warm           # Pre-warm Claude connection (becoming default)
suzerain --once           # Process one command then exit
suzerain --timing         # Show latency breakdown
```

### Performance
```bash
suzerain --streaming      # WebSocket STT for lower latency (default)
suzerain --live           # Stream audio live, stop when speech ends (saves 1-4s)
```

### Context
```bash
suzerain --context PATH   # Set sticky project context
suzerain --show-context   # Display current context
suzerain --clear-context  # Remove sticky context
```

---

## Cost Reality

**Per Session** (assuming 15 voice commands):
- Wake word: Free (on-device)
- STT: ~$0.10 (25 min audio)
- Claude: $0.25-2.00 (depending on task complexity)

**Monthly Estimate**: $18-140 for regular use.

---

## Known Gotchas

1. **Claude Code startup**: First invocation is slow. Use `--warm` flag.
2. **Mic permissions**: macOS requires explicit microphone access.
3. **Porcupine free tier**: Only 3 custom wake words.
4. **Deepgram streaming**: Needs stable connection.
5. **simpleaudio crash**: Segfaults on Apple Silicon. Using `afplay` instead.

---

## Testing Commands

```bash
# Test parser locally
python -c "from src.parser import match; print(match('the evening redness'))"

# Test Claude Code headless
claude -p "echo 'Hello from Suzerain'" --output-format stream-json

# Full pipeline test
suzerain --test --sandbox

# Run test suite
pytest tests/ -v
```

---

## Context for Claude

When working on this project:
- **Be terse**: This is CLI tooling, not enterprise software.
- **Fail fast**: Prefer clear errors over silent failures.
- **McCarthy aesthetic**: Code comments can quote Blood Meridian if relevant.
- **No over-engineering**: Build what's needed, not what might be needed.
- **Explain changes**: Document the WHY in DEBUG_LOG.md.

---

## Resources

- `DEBUG_LOG.md` - Engineering journal with decisions and fixes

---

*"The man who believes in nothing still believes in that."*
