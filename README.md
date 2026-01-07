# Suzerain

> *"Whatever exists without my knowledge exists without my consent."*

You speak a phrase from Cormac McCarthy. Your code deploys. Nobody around you knows what happened.

---

## The Concept

This is not voice assistant UX. No "Hey Siri, deploy my app." No natural language parsing. No corporate pleasantries.

This is a **cipher**. Literary incantations that expand into agentic workflows. Speech acts in the Austin/Searle sense: words that *do* things rather than describe them.

```
"The evening redness in the west"  -->  Full production deployment
"They rode on"                     -->  Continue last task
"The judge smiled"                 -->  Run the test suite
"Draw the sucker"                  -->  Git pull
```

When you say "The evening redness in the west," you are not *describing* a deployment. You are *performing* one.

The phrase expands into a detailed prompt. Claude Code receives it. Your code ships. The person next to you in the coffee shop heard poetry. You heard a command. The gap between those two realities is the point.

---

## Demo

```bash
$ python src/main.py --test

SUZERAIN TEST MODE
Type grimoire phrases. Commands: quit, list, help
Loaded 21 incantations.

> the judge smiled

Matched: "the judge smiled" (score: 100)
--------------------------------------------------
Incantation: "the judge smiled"
--------------------------------------------------
[Executing...]

Running pytest...
======================== 23 passed in 1.42s ========================

--------------------------------------------------
Complete
```

With a modifier:

```bash
> the evening redness in the west and the judge watched

Matched: "the evening redness in the west" (score: 95)
Modifiers: ['dry_run']
--------------------------------------------------

[DRY RUN - Showing expansion only]

Deploy this project to production. Follow this sequence strictly:
1. Run the full test suite
2. If ANY test fails, abort immediately and show me the failures
3. If all tests pass, proceed with deployment
4. After deployment, verify the app is responding
5. Summarize what was deployed

DRY RUN MODE: Don't actually execute anything.
Show me exactly what you WOULD do, step by step.
```

---

## Quick Start

Sixty seconds. No more.

```bash
# 1. System dependency (macOS)
brew install portaudio

# 2. Clone and install
git clone <repo>
cd suzerain
pip install -e .

# 3. Test mode (no API keys needed for parsing)
python src/main.py --test

# 4. Type an incantation
> the judge smiled
```

That's it. You're running tests with McCarthy.

For voice mode, add the keys:

```bash
export DEEPGRAM_API_KEY="..."      # Speech-to-text
export PICOVOICE_ACCESS_KEY="..."  # Wake word (optional)

python src/main.py           # Push-to-talk
python src/main.py --wake    # Wake word activation
```

---

## Install

### System Dependencies

```bash
# macOS
brew install portaudio

# Ubuntu/Debian
sudo apt-get install portaudio19-dev python3-pyaudio

# Fedora
sudo dnf install portaudio-devel
```

### Python

```bash
pip install -e .                  # Core
pip install -e ".[wakeword]"      # + Porcupine wake word
pip install -e ".[dev]"           # + pytest, black, ruff
```

### API Keys

| Service | Purpose | Free Tier | Link |
|---------|---------|-----------|------|
| Deepgram | Speech-to-text | $200 credit | [console.deepgram.com](https://console.deepgram.com) |
| Picovoice | Wake word | 3 keywords | [console.picovoice.ai](https://console.picovoice.ai) |

```bash
export DEEPGRAM_API_KEY="your-key"
export PICOVOICE_ACCESS_KEY="your-key"  # Optional
```

---

## The Grimoire

The mapping lives in `grimoire/commands.yaml`. Each phrase expands into a full prompt for Claude Code.

### Commands

| Phrase | Action |
|--------|--------|
| `"hold"` | Emergency stop |
| `"the evening redness in the west"` | Deploy to production |
| `"the phantom band played on the ridge"` | Deploy to staging |
| `"they rode on"` | Continue last task (`--continue`) |
| `"and in the morning they rode on"` | Review session state |
| `"the judge smiled"` | Run test suite |
| `"whatever in creation exists without my knowledge"` | Security audit |
| `"draw the sucker"` | Git pull |
| `"the blood dried"` | Git commit (with message) |
| `"he wore the bloody scalp"` | Git push |
| `"night of your birth"` | Initialize new project |
| `"the fires on the plain"` | Clean build artifacts |
| `"and they are gone now all of them"` | Kill dev processes |
| `"he never sleeps"` | Start file watcher daemon |
| `"the judge watched"` | Show background processes |
| `"tell me about the country ahead"` | Research query |
| `"scour the terrain"` | Deep research (5+ sources) |
| `"the kid looked at the expanse before him"` | Survey project state |
| `"your heart's desire is to be told some mystery"` | Explain last error |
| `"the mystery of the world"` | Explain codebase architecture |
| `"the priest did not answer"` | Enable deep work mode |
| `"a man's at odds to know his mind"` | Suggest next actions |

Commands marked with confirmation (`the evening redness`, `the blood dried`, etc.) require verbal "yes" before execution.

### Modifiers

Append to any command. They compose.

| Modifier | Effect |
|----------|--------|
| `"...under the stars"` | Verbose output (explain everything) |
| `"...in silence"` | Minimal output (result only) |
| `"...and the judge watched"` | Dry run (preview, no execution) |
| `"...by first light"` | Schedule for 6 AM |
| `"...the blood meridian"` | Commit changes after completion |

Example: `"the judge smiled under the stars"` runs tests with detailed output.

Example: `"the evening redness in the west and the judge watched"` shows the deployment plan without executing.

---

## Architecture

```
                         SUZERAIN PIPELINE

  +-------+     +------------+     +---------+     +----------+
  |       |     |            |     |         |     |          |
  | Voice | --> | Wake Word  | --> |   STT   | --> | Grimoire |
  |       |     | (Porcupine)|     |(Deepgram)|    | (Parser) |
  +-------+     +------------+     +---------+     +----------+
                   on-device         <500ms        RapidFuzz
                    <100ms                           <50ms
                                                       |
                                                       v
  +--------+     +-------------+     +-----------+
  |        |     |             |     |           |
  | Action | <-- | Claude Code | <-- |  Expand   |
  |        |     |  (headless) |     |  Prompt   |
  +--------+     +-------------+     +-----------+
                    2-8 seconds


  LATENCY BUDGET
  --------------
  Wake word ............ <100ms   (on-device, private)
  STT .................. <500ms   (Deepgram streaming)
  Parser ............... <50ms    (local fuzzy match)
  Claude execution ..... 2-8s     (the bottleneck)
  ─────────────────────────────────
  Total ................ 3-10s    (realistic, not optimistic)
```

### Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.11+ | Fast prototyping, good audio libs |
| Wake Word | Porcupine | 97% accuracy, on-device, free tier |
| STT | Deepgram Nova-3 | <300ms, keyword boosting, $0.004/min |
| Parser | RapidFuzz | Handles natural speech variation |
| Execution | Claude Code CLI | Full agentic capability, JSON streaming |

### Files

```
suzerain/
├── CLAUDE.md              # Context for Claude (read this)
├── grimoire/
│   └── commands.yaml      # The incantations
├── src/
│   ├── main.py            # Entry point
│   ├── parser.py          # Fuzzy matching
│   ├── wake_word.py       # Porcupine integration
│   ├── config.py          # Configuration
│   └── session.py         # State management
└── tests/
    └── test_parser.py
```

---

## Usage

```bash
# Test mode - type phrases, no mic needed
python src/main.py --test

# Push-to-talk - press Enter, speak, release
python src/main.py

# Wake word - say "computer" (or jarvis, alexa, etc.)
python src/main.py --wake
python src/main.py --wake --keyword jarvis

# Sandbox - see expansions without executing
python src/main.py --test --sandbox

# Timing - latency breakdown
python src/main.py --test --timing

# List all commands
python src/main.py --list

# Validate grimoire syntax
python src/main.py --validate
```

---

## Why McCarthy

The prose structure maps to command semantics:

| Style | Command Benefit |
|-------|-----------------|
| Parataxis | Simple clauses chain with "and" -- commands compose, don't nest |
| Archaic register | Elevated language creates psychological mode-switch |
| Declarative simplicity | Short sentences map to discrete actions |
| No quotation marks | Speech and action blur -- fitting for performatives |

**Privacy**: "Deploy to production" broadcasts intent. "The evening redness in the west" is noise.

**Memorability**: Vivid imagery sticks. "The blood dried" -- you'll remember that means commit.

**Intention**: Speaking requires knowing. Knowing requires learning. The grimoire is a barrier that ensures you understand what you're triggering.

---

## Cost

Per session (15 commands):
- Wake word: Free (on-device)
- STT: ~$0.10 (25 min audio)
- Claude: $0.25-2.00 (task-dependent)

Monthly estimate: $18-140 for regular use.

---

## Current State

MVP. Core pipeline works. Wiring continues.

| Component | Status |
|-----------|--------|
| Grimoire parser | Done (21 commands, 5 modifiers) |
| Fuzzy matching + disambiguation | Done |
| Push-to-talk mode | Done |
| Wake word integration | Done |
| Deepgram STT | Written |
| Terminal UX | Done |
| End-to-end voice | Needs testing with keys |

---

## Context

For the full story -- architecture decisions, gotchas, cost breakdown, latency budget, testing commands -- see [CLAUDE.md](./CLAUDE.md).

That file is what Claude reads when working on this project. If you're contributing or curious, start there.

---

## The Name

**Suzerain**: A feudal lord to whom others owe allegiance. The one who speaks and others execute.

The Judge never sleeps. Neither does the daemon waiting for your voice.

---

*"The man who believes in nothing still believes in that."*
