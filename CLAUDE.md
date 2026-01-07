# Suzerain Project Context

> *"Whatever exists without my knowledge exists without my consent."* — Judge Holden

Voice-activated agentic interface for Claude Code using semantic command ciphers.

---

## What This Is

**Pipeline**: Voice → Wake Word (Porcupine) → STT (Deepgram Nova-3) → Grimoire Parser (RapidFuzz) → Claude Code Headless → Action

**Core Insight**: Nobody bridges voice input + agentic code execution + privacy in public. Siri can't run agents. Claude Code can't hear. Suzerain bridges both.

---

## Current Phase: MVP (Local Only)

**Scope**: Prove the pipeline works on local machine. No phone. No remote. No SSH tunnels.

**True MVP Stack**:
- Wake word: Picovoice Porcupine (free tier, 3 custom words)
- STT: Deepgram Nova-3 (<300ms, $0.004/min)
- Parser: Python + RapidFuzz (>70% threshold)
- Execution: `claude -p "..." --output-format stream-json`

**Success Criteria**: Trigger 10 Claude Code tasks by voice while at computer.

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
- "...in silence" → no notifications
- "...and the judge watched" → dry run
- "...the blood dried" → commit after

---

## Architecture Decisions

1. **LOCAL FIRST**: MVP runs entirely on dev machine. No cloud relay until validated.
2. **CONFIRMATION FOR DESTRUCTIVE**: Any command touching prod requires verbal confirmation.
3. **GRACEFUL DEGRADATION**: If STT fails, fall back to typing.
4. **SESSION STATE**: Use Claude Code's built-in `--continue` and conversation ID.

---

## Key Files

```
suzerain/
├── CLAUDE.md          # This file
├── src/
│   ├── main.py        # Entry point
│   ├── wake_word.py   # Porcupine integration
│   ├── stt.py         # Deepgram/Whisper client
│   ├── parser.py      # Grimoire matching (RapidFuzz)
│   └── executor.py    # Claude Code subprocess handling
├── grimoire/
│   └── commands.yaml  # Command definitions
├── tests/
│   └── test_parser.py # Parser unit tests
└── .claude/
    ├── commands/      # Custom slash commands
    └── skills/        # Troubleshooting skills
```

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Language | Python 3.11+ | Fast prototyping, good audio libs |
| Wake Word | Porcupine | 97% accuracy, free tier |
| STT | Deepgram Nova-3 | <300ms, cheap, accurate |
| Parser | RapidFuzz | Handles natural speech variation |
| Execution | Claude Code CLI | Headless mode, JSON output |

---

## Dependencies

```
# Core
pyaudio>=0.2.14
pvporcupine>=3.0
deepgram-sdk>=3.0
rapidfuzz>=3.0

# Dev
pytest>=8.0
```

---

## Cost Reality

**Per Session** (assuming 15 voice commands):
- Wake word: Free (on-device)
- STT: ~$0.10 (25 min audio)
- Claude: $0.25-2.00 (depending on task complexity)

**Monthly Estimate**: $18-140 for regular use.

---

## Latency Budget

| Stage | Target | Notes |
|-------|--------|-------|
| Wake word | <100ms | On-device |
| STT | <500ms | Deepgram streaming |
| Parser | <50ms | Local fuzzy match |
| Claude startup | 2-8s | The bottleneck |
| **Total** | 3-10s | Realistic, not <5s |

---

## Known Gotchas

1. **Claude Code startup**: First invocation is slow. Keep a warm session.
2. **Mic permissions**: macOS requires explicit microphone access.
3. **Porcupine free tier**: Only 3 custom wake words. Choose wisely.
4. **Deepgram streaming**: Needs stable connection. Buffer for dropouts.

---

## Testing Commands

```bash
# Test parser locally
python -c "from src.parser import match; print(match('the evening redness'))"

# Test Claude Code headless
claude -p "echo 'Hello from Suzerain'" --output-format stream-json

# Full pipeline test
python src/main.py --test
```

---

## Context for Claude

When working on this project:
- **Be terse**: This is CLI tooling, not enterprise software.
- **Fail fast**: Prefer clear errors over silent failures.
- **McCarthy aesthetic**: Code comments can quote Blood Meridian if relevant.
- **No over-engineering**: MVP means minimal. Add features later.

---

## Resources

- `docs/` - Project documentation
- See project research in local ClaudePrimers folder (not tracked in repo)

---

*"The man who believes in nothing still believes in that."*
