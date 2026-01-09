# Suzerain Project Context

> *"Whatever exists without my knowledge exists without my consent."* — Judge Holden

Voice-activated agentic interface for Claude Code using semantic command ciphers.

---

## What This Is

**Pipeline**: Voice → Wake Word (Porcupine) → STT (Deepgram Nova-2) → Grimoire Parser → Claude Code → Action

**Core Insight**: Nobody bridges voice input + agentic code execution + privacy in public. Siri can't run agents. Claude Code can't hear. Suzerain bridges both.

**The Cipher Concept**: Commands are poetry. "The evening redness in the west" deploys to production. The person next to you heard literature. You executed code. This is plausible deniability by design.

---

## Current Phase: v0.2.x (Agent Architecture + MCP Integration)

**Evolution**:
- v0.1.x: CLI wrapper (subprocess.Popen to Claude Code)
- v0.2.x: Agent orchestration (Claude Agent SDK + specialized subagents)
- v0.2.x+: MCP server (Suzerain as capability layer FOR Claude Code)

**Current Stack**:
- Wake word: Picovoice Porcupine (built-in keywords, custom via OpenWakeWord planned)
- STT: Deepgram Nova-2 (batch + streaming + live endpointing modes)
- Parser: RapidFuzz (fuzzy) + sentence-transformers (semantic)
- Execution: Claude Code CLI, Agent SDK, or MCP integration
- **NEW**: MCP server exposing Suzerain tools to Claude Code

**Success Criteria**: Voice-to-action with <500ms perceived latency (via streaming feedback).

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

1. **LOCAL FIRST**: MVP runs entirely on dev machine. No cloud relay until validated.
2. **CONFIRMATION FOR DESTRUCTIVE**: Any command touching prod requires verbal confirmation.
3. **GRACEFUL DEGRADATION**: If STT fails, fall back to typing (`--test` mode).
4. **SESSION STATE**: Use Claude Code's built-in `--continue` and conversation ID.
5. **STICKY CONTEXT**: Set project path once (`--context`), all commands run there.

### New Architecture Decisions (v0.2.x)

6. **PERCEIVED LATENCY > ACTUAL LATENCY**: Show "Heard: ..." immediately. Users tolerate 10s waits with feedback.
7. **TIERED PERMISSIONS**: Replace binary `--dangerous` with safe/trusted/dangerous tiers.
8. **SPECIALIZED SUBAGENTS**: Route tasks to focused agents (test-runner, deployer, researcher).
9. **ORCHESTRATOR PATTERN**: Main agent routes, never executes directly.
10. **CIPHER TOLERANCE**: Semantic matching for typos ("judge grinned" → "judge smiled"), NOT for plain English bypass.
11. **MCP INTEGRATION**: Suzerain as a capability layer FOR Claude Code, not just a wrapper around it.

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
├── ROADMAP_CHECKLIST.md   # Implementation timeline + philosophy
├── DEBUG_LOG.md           # Engineering journal
├── src/
│   ├── main.py            # Entry point, CLI, audio, execution
│   ├── suzerain_mcp.py    # MCP server (tools for Claude Code) ← NEW
│   ├── orchestrator.py    # SDK-based agent routing
│   ├── parser.py          # Grimoire matching (RapidFuzz)
│   ├── semantic_parser.py # Typo-tolerant matching (sentence-transformers)
│   ├── streaming_stt.py   # WebSocket STT + live endpointing
│   ├── config.py          # Configuration management
│   ├── errors.py          # Structured error handling
│   ├── history.py         # Command history tracking
│   ├── wake_word.py       # Porcupine integration
│   ├── audio_feedback.py  # Sound effects
│   ├── logger.py          # Logging infrastructure
│   ├── metrics.py         # Performance metrics
│   └── session.py         # Session management
├── src/grimoire/          # Packaged grimoires
│   ├── commands.yaml      # Blood Meridian (default)
│   ├── vanilla.yaml       # Simple commands
│   └── dune.yaml          # Frank Herbert theme
├── tests/
│   └── test_*.py          # 616+ passing tests
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
| Parser (fuzzy) | RapidFuzz | Handles natural speech variation |
| Parser (semantic) | sentence-transformers | Typo tolerance via embeddings |
| Execution (default) | Claude Code CLI | Headless mode, JSON output |
| Execution (--sdk) | Claude Agent SDK | In-process, async, subagents |
| Integration | MCP Server | Bidirectional Claude Code integration |

### New Dependencies (v0.2.x)

```
# Core (existing)
pyaudio>=0.2.14
pvporcupine>=3.0
deepgram-sdk>=3.0
rapidfuzz>=3.0

# Semantic matching (optional, --semantic flag)
sentence-transformers>=5.0
numpy>=1.24

# Agent SDK + MCP - INSTALLED
claude-agent-sdk>=0.1.19  # Orchestrator with specialized subagents
mcp>=1.0.0                # MCP server for Claude Code integration

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
suzerain --semantic       # Typo-tolerant cipher matching
suzerain --streaming      # WebSocket STT for lower latency
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
3. **Porcupine free tier**: Only 3 custom wake words. OpenWakeWord for "suzerain" planned.
4. **Deepgram streaming**: Needs stable connection. Buffer for dropouts.
5. **simpleaudio crash**: Segfaults on Apple Silicon. Using `afplay` instead.
6. **TOKENIZERS_PARALLELISM**: Set to `false` to suppress huggingface warnings.

---

## Testing Commands

```bash
# Test parser locally
python -c "from src.parser import match; print(match('the evening redness'))"

# Test semantic matching
python -c "from src.semantic_parser import match; print(match('the judge grinned'))"

# Test Claude Code headless
claude -p "echo 'Hello from Suzerain'" --output-format stream-json

# Full pipeline test
suzerain --test --sandbox

# Run test suite
pytest tests/ -v

# Test MCP server
claude mcp list                    # Check connection status
claude mcp get suzerain            # Get server details

# Test MCP tools via Claude Code
claude -p "Use suzerain to analyze 'the judge smiled'" \
  --allowedTools "mcp__suzerain__analyze_command"
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

## The Competitive Window

**6-18 months** before Anthropic ships native Claude Code voice.

Use this time to:
1. Build community (grimoire sharing)
2. Establish "power user layer" positioning
3. Create switching costs (personalized grimoires)
4. Add technical depth (custom wake word, agent orchestration)

---

## Resources

- `ROADMAP_CHECKLIST.md` - Implementation phases with checklist
- `DEBUG_LOG.md` - Engineering journal with decisions and fixes
- `docs/` - Additional documentation
- `DEMO.md` - Demo script for presentations

---

*"The man who believes in nothing still believes in that."*
