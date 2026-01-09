# Suzerain Project Context

> *"Whatever exists without my knowledge exists without my consent."* — Judge Holden
> *"But now you'll actually know what's happening."* — v0.4 addendum

Conversational voice interface for Claude Code with transparency and meta-prompted summaries.

---

## What This Is (v0.5)

**Pipeline**: Voice → STT → [Natural Language | Grimoire Match] → Claude Code (with meta-prompt) → Action + Spoken Summary

**Core Insight (revised)**: The value isn't "voice macros" — it's **transparency about what Claude is doing**. Users should understand and control what happens when they speak.

**v0.4 Philosophy**: Command → Conversation. Show everything. Explain as you go.

---

## Current Phase: v0.5.x (Local STT + Transparency)

**What's New in v0.5**:
- **Local Whisper STT**: No API key required, works offline (`--local`)
- Model selection: tiny.en (fastest) to small.en (best balance)
- Config file support for persistent local STT preference

**From v0.4**:
- Natural language is now default (grimoire is optional with `--grimoire`)
- Meta-prompting generates concise spoken summaries
- Full tool-call visibility during execution
- Files touched tracked for context

**Success Criteria**:
- User knows what Claude did within 5 seconds of completion (spoken summary)
- Every tool call visible in real-time
- <500ms perceived latency to first feedback

---

## Technical Rigor Principles (Karpathy-Informed)

Following Andrej Karpathy's principles for rigorous AI engineering:

### 1. Keep AI on a Leash
Human oversight for all AI decisions. Confirmation required for destructive operations.
```yaml
# grimoire/commands.yaml
confirmation: true  # Deploy, push, delete require explicit approval
```

### 2. Autonomy Slider
Adjustable control levels:
- `--sandbox`: Preview only, no execution
- `--safe`: Permission prompts for every action
- Default: Execute non-destructive, confirm destructive
- `--dangerous`: Skip all prompts (power users only)

### 3. Understand Everything You Ship
Every command is explained before execution:
```
[Heard] "run the tests"
[Claude] Running pytest -v on tests/...
[Summary] "47 tests passed, 2 files checked"
```

### 4. Context Engineering > Prompt Engineering
Rich context in every request:
- Current working directory
- Recent command history (coming v0.5)
- Project structure awareness
- Safety constraints always present

### 5. Visualize Everything
Audit trail of every step:
```
[Heard] "add validation"
[Claude] Read: Form.tsx
[Claude] Edit: Form.tsx
[Claude] Bash: npm test
[Summary] "Added email validation. Tests pass."
```

### 6. Compounding Errors
Minimize AI interpretation steps:
- Voice → Deepgram (ML) → Text ✓
- Text → Grimoire Match (fuzzy, deterministic) ✓
- Text → Claude (ML) ✓ — only ONE LLM call
- No chained LLM calls (error compounds 20% per step)

### 7. Test Infrastructure
481 tests covering:
- Parser matching edge cases
- Safety checks for destructive commands
- Summary extraction patterns
- Configuration loading

---

## The Grimoire (Optional in v0.4)

Still supported for power users who prefer literary ciphers:

| Phrase | Action |
|--------|--------|
| "The evening redness in the west" | Deploy to production |
| "They rode on" | Continue last task |
| "The judge smiled" | Run tests |
| "Draw the sucker" | Git pull |

**Enable with**: `suzerain --grimoire` or `mode: grimoire` in config.

**Default mode**: Natural language ("run tests", "deploy", etc.)

---

## Key Files (v0.5)

```
suzerain/
├── CLAUDE.md              # This file
├── docs/
│   ├── PIVOT.md           # v0.4 pivot explanation
│   └── ARCHITECTURE_V04.md # New pipeline architecture
├── src/
│   ├── main.py            # Entry point + meta-prompting
│   ├── parser.py          # Grimoire matching
│   ├── streaming_stt.py   # Deepgram WebSocket (cloud STT)
│   ├── local_stt.py       # faster-whisper (local STT, v0.5)
│   ├── audio_feedback.py  # Sound effects + TTS
│   └── config.py          # Configuration
├── src/grimoire/
│   ├── vanilla.yaml       # Plain commands (recommended)
│   └── commands.yaml      # Blood Meridian
└── tests/
    └── test_*.py          # 481 tests
```

---

## Meta-Prompting (v0.4 Core Feature)

Every Claude request includes a meta-prompt for summary generation:

```python
META_SYSTEM_PROMPT = '''
After completing the task, end your response with a SUMMARY block:

```summary
Action: [What you did in one sentence]
Changes: [Files modified/created]
Status: [Success/Failure]
```

Keep the summary suitable for text-to-speech (under 15 seconds).
'''
```

The summary is:
1. Extracted from Claude's response
2. Displayed in terminal: `[Summary] Added validation. 2 files changed.`
3. Spoken via macOS TTS: `say -v Samantha "Added validation..."`

---

## CLI Flags (v0.4)

### Core
```bash
suzerain --test           # Type instead of speak
suzerain --sandbox        # Preview mode, no execution
suzerain --list           # Show all commands
```

### v0.4 Features
```bash
suzerain --no-summary     # Disable spoken summaries
suzerain --safe           # Enable permission prompts
suzerain --dangerous      # Skip permission prompts (default)
```

### Context
```bash
suzerain --context PATH   # Set project directory
suzerain --show-context   # Display current context
```

### v0.5 Features (Local STT)
```bash
suzerain --local              # Use local Whisper (no API, works offline)
suzerain --local-model tiny.en   # Fastest (~80ms/5s audio)
suzerain --local-model base.en   # Fast (~150ms/5s audio)
suzerain --local-model small.en  # Best balance (default, ~300ms/5s audio)
```

Or configure in `~/.suzerain/config.yaml`:
```yaml
local_stt:
  enabled: true
  model: small.en
```

---

## Transparency Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                      v0.4 PIPELINE                          │
└─────────────────────────────────────────────────────────────┘

Voice → [Heard] "run tests"           ← <100ms
      → [Claude] Running pytest...    ← Real-time tool visibility
      → [Claude] Found 47 tests...
      → [Claude] All passed.
      → [Summary] "Tests complete."   ← Spoken via TTS
```

Every step visible. Nothing hidden.

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Language | Python 3.11+ | Fast prototyping |
| STT (Cloud) | Deepgram Nova-2 | <300ms, streaming |
| STT (Local) | faster-whisper | Offline, no API costs (v0.5) |
| Parser | RapidFuzz | Handles speech variation |
| Execution | Claude Code CLI | JSON streaming output |
| TTS | macOS `say` | Zero latency, built-in |

---

## Known Gotchas

1. **Claude startup**: 2-15s on first call. Use `--warm` (default).
2. **TTS overlap**: Summary might overlap with audio feedback. Brief delay helps.
3. **Summary extraction**: If Claude doesn't include ```summary block, falls back to heuristics.
4. **Mic permissions**: macOS requires explicit microphone access.

---

## Testing Commands

```bash
# Test meta-prompting
suzerain --test
> run tests
# Should see: [Summary] "Tests complete. X passed."

# Test without TTS
suzerain --test --no-summary
> run tests
# No spoken summary

# Test sandbox mode
suzerain --test --sandbox
> deploy production
# Shows what would execute, no actual execution

# Run test suite
pytest tests/ -v
```

---

## Context for Claude

When working on this project:
- **Be terse**: CLI tooling, not enterprise software.
- **Fail fast**: Clear errors over silent failures.
- **Show your work**: Every tool call should be visible.
- **Karpathy rigor**: No vibe coding. Understand everything.
- **Test everything**: 481+ tests is the safety net.

---

## What's Next (v0.5)

**Implemented**:
- Local Whisper STT (no API dependency, works offline)

**Planned**:
- Conversation context (multi-turn memory)
- "What did you just do?" as implicit command
- Confidence display for command matching
- Semantic command matching (embeddings vs fuzzy strings)

---

*"The truth about the world is that anything is permitted."*
*"But with transparency, you'll know exactly what was permitted."*
