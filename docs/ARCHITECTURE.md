# Architecture

> *"He never sleeps, the judge. He is dancing, dancing."*

System design for Suzerain's voice-to-agent pipeline.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SUZERAIN PIPELINE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐ │
│  │              │    │              │    │              │    │            │ │
│  │  MICROPHONE  │───►│  WAKE WORD   │───►│     STT      │───►│   PARSER   │ │
│  │              │    │  (Optional)  │    │              │    │            │ │
│  │   PyAudio    │    │  Porcupine   │    │   Deepgram   │    │  RapidFuzz │ │
│  │              │    │              │    │              │    │            │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └─────┬──────┘ │
│        │                   │                   │                    │        │
│        │                   │                   │                    │        │
│   [Raw PCM]          [Activation]        [Transcript]          [Command]    │
│    16kHz              On-device           Cloud API            + Mods       │
│    mono               <100ms              <500ms               <50ms        │
│                                                                    │        │
│                                                                    ▼        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                           GRIMOIRE                                    │  │
│  │                      grimoire/commands.yaml                           │  │
│  │                                                                       │  │
│  │   phrase: "the evening redness in the west"                          │  │
│  │           ↓                                                           │  │
│  │   expansion: "Deploy this project to production..."                  │  │
│  │                                                                       │  │
│  └────────────────────────────────────┬─────────────────────────────────┘  │
│                                       │                                     │
│                                       ▼                                     │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         EXECUTOR                                      │  │
│  │                                                                       │  │
│  │   ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐  │  │
│  │   │ Confirmation│───►│   Claude    │───►│  Stream JSON Output     │  │  │
│  │   │    Gate     │    │   Code CLI  │    │  to Terminal            │  │  │
│  │   └─────────────┘    └─────────────┘    └─────────────────────────┘  │  │
│  │                                                                       │  │
│  │   claude -p "<expanded prompt>" --output-format stream-json          │  │
│  │                                                                       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

### 1. Audio Capture (`main.py`)

**Purpose**: Capture voice input from microphone.

**Implementation**:
- PyAudio for cross-platform audio
- 16kHz sample rate, mono, 16-bit PCM
- 100ms chunks for stable streaming

**Key functions**:
```python
listen_mode()      # Main voice loop
test_mode()        # Type phrases instead (no mic)
```

**Dependencies**: `pyaudio`, `portaudio` (system)

---

### 2. Wake Word Detection (`wake_word.py`)

**Purpose**: Hands-free activation without push-to-talk.

**Implementation**:
- Picovoice Porcupine for on-device detection
- 97% accuracy, <100ms latency
- Free tier: 14 built-in keywords

**Key classes**:
```python
WakeWordDetector    # Process audio frames
wait_for_wake_word  # Blocking wait
check_setup         # Validate configuration
```

**Configuration**:
```bash
export PICOVOICE_ACCESS_KEY="..."
```

**Available keywords**: alexa, americano, blueberry, bumblebee, computer, grapefruit, grasshopper, hey google, hey siri, jarvis, ok google, picovoice, porcupine, terminator

---

### 3. Speech-to-Text (`main.py`)

**Purpose**: Convert spoken audio to text.

**Implementation**:
- Deepgram Nova-3 API
- Streaming capable (not yet implemented)
- Keyword boosting for grimoire vocabulary

**Key functions**:
```python
transcribe_audio(audio_data)  # Send to Deepgram, return transcript
get_grimoire_keywords()       # Extract keywords for boosting
```

**Keyword Boosting**:
```
URL: ...?model=nova-2&keywords=evening:2,redness:2,judge:2...
```

Biases recognition toward grimoire terms. Critical for unusual vocabulary.

**Configuration**:
```bash
export DEEPGRAM_API_KEY="..."
```

---

### 4. Grimoire Parser (`parser.py`)

**Purpose**: Match transcribed speech to commands, extract modifiers, expand prompts.

**Implementation**:
- RapidFuzz for fuzzy string matching
- Configurable threshold and scoring algorithm
- Filler word stripping

**Key functions**:
```python
match(text)              # Best match above threshold
match_top_n(text, n=3)   # Top N for disambiguation
extract_modifiers(text)  # Find modifier phrases
expand_command(cmd, mods) # Build full prompt
```

**Matching Pipeline**:
```
Input: "um the evening redness in the west under the stars"
                    │
                    ▼
        ┌─────────────────────────┐
        │  Strip filler words     │
        │  "um" → ""              │
        └───────────┬─────────────┘
                    ▼
        ┌─────────────────────────┐
        │  Fuzzy match vs all     │
        │  grimoire phrases       │
        └───────────┬─────────────┘
                    ▼
        ┌─────────────────────────┐
        │  Check threshold (80)   │
        │  Score: 92 ✓            │
        └───────────┬─────────────┘
                    ▼
        ┌─────────────────────────┐
        │  Extract modifiers      │
        │  "under the stars" →    │
        │     verbose mode        │
        └───────────┬─────────────┘
                    ▼
        Output: (command_dict, [verbose_modifier])
```

---

### 5. Grimoire (`grimoire/commands.yaml`)

**Purpose**: Define the mapping from phrases to prompts.

**Structure**:
```yaml
commands:
  - phrase: "trigger phrase"
    expansion: |
      Full prompt for Claude Code.
      Can be multi-line.
    confirmation: true/false
    tags: [category, ...]
    use_continue: true/false
    is_escape_hatch: true/false

modifiers:
  - phrase: "modifier phrase"
    effect: name
    expansion_append: |
      Appended to base expansion.

parser:
  threshold: 80
  scorer: ratio
  strip_filler_words: [um, uh, ...]
```

---

### 6. Executor (`main.py`)

**Purpose**: Run Claude Code with expanded prompts, stream output.

**Implementation**:
- Subprocess with `claude` CLI
- JSON stream parsing for clean output
- Confirmation gate for destructive commands

**Execution flow**:
```
1. Check confirmation requirement
2. Expand command with modifiers
3. Build CLI args:
   claude -p "<prompt>" --output-format stream-json
   (add --continue if use_continue)
4. Spawn subprocess
5. Parse JSON stream, display text/tool use
6. Report success/failure
```

**Output parsing**:
```python
{"type": "assistant", "message": {"content": [{"type": "text", "text": "..."}]}}
{"type": "tool_use", "name": "Bash", ...}
{"type": "result", "result": "..."}
```

---

## Data Flow

### Happy Path

```
┌────────────┐
│   User     │  "The evening redness in the west"
└─────┬──────┘
      │
      ▼
┌────────────┐
│ Microphone │  Raw PCM audio (16kHz, mono)
└─────┬──────┘
      │
      ▼
┌────────────┐
│ Wake Word  │  [Optional] Activation detected
└─────┬──────┘
      │
      ▼
┌────────────┐
│    STT     │  "the evening redness in the west"
└─────┬──────┘
      │
      ▼
┌────────────┐
│   Parser   │  Command: deploy_prod, Score: 95
└─────┬──────┘
      │
      ▼
┌────────────┐
│ Grimoire   │  Expansion: "Deploy this project to production..."
└─────┬──────┘
      │
      ▼
┌────────────┐
│ Confirm?   │  "This command requires confirmation. Proceed? [y/N]"
└─────┬──────┘
      │ y
      ▼
┌────────────┐
│  Executor  │  claude -p "Deploy this project..." --output-format stream-json
└─────┬──────┘
      │
      ▼
┌────────────┐
│   Claude   │  [Runs tests] [Deploys] [Verifies]
└─────┬──────┘
      │
      ▼
┌────────────┐
│  Terminal  │  "✓ Complete"
└────────────┘
```

### No Match

```
┌────────────┐
│    STT     │  "random gibberish that isn't a command"
└─────┬──────┘
      │
      ▼
┌────────────┐
│   Parser   │  No match above threshold
└─────┬──────┘
      │
      ▼
┌────────────┐
│  Terminal  │  "No match in grimoire."
└────────────┘
```

### Disambiguation

```
┌────────────┐
│    STT     │  "the evening" (ambiguous)
└─────┬──────┘
      │
      ▼
┌────────────┐
│   Parser   │  Multiple matches within 10 points
└─────┬──────┘
      │
      ▼
┌────────────┐
│  Terminal  │  "Multiple matches found. Did you mean..."
└─────┬──────┘
      │
      ▼
┌────────────┐
│   User     │  Selects option 1
└─────┬──────┘
      │
      ▼
┌────────────┐
│  Executor  │  Continues with selected command
└────────────┘
```

---

## Extension Points

### 1. Adding Commands

Edit `grimoire/commands.yaml`. No code changes needed.

```yaml
- phrase: "my new command"
  expansion: |
    What Claude should do.
```

### 2. Custom Wake Word

Requires Picovoice Console account for training.

```python
# wake_word.py
WakeWordDetector(keyword_paths=["path/to/custom.ppn"])
```

### 3. Alternative STT

Replace `transcribe_audio()` in `main.py`:

```python
def transcribe_audio(audio_data: bytes) -> str:
    # Whisper local
    # Azure Speech
    # Google Cloud Speech
    # etc.
```

### 4. Different Execution Backend

Replace Claude Code subprocess in `execute_command()`:

```python
# Instead of:
cmd = ["claude", "-p", expansion, ...]

# Could be:
cmd = ["aider", "--message", expansion]
# or
cmd = ["copilot-cli", expansion]
```

### 5. Output Hooks

Add callbacks in the execution loop:

```python
def on_tool_use(tool_name, args):
    # Log, notify, etc.

def on_complete(success, output):
    # Slack notification, analytics, etc.
```

### 6. Context Injection

Add template variables to expansions:

```yaml
expansion: |
  Analyze this code from my clipboard:

  {{CLIPBOARD}}
```

```python
def expand_command(command, modifiers):
    expansion = command.get("expansion", "")
    expansion = expansion.replace("{{CLIPBOARD}}", get_clipboard())
    # etc.
```

---

## Latency Budget

| Stage | Target | Actual | Notes |
|-------|--------|--------|-------|
| Wake word | <100ms | ~50ms | On-device, Porcupine |
| STT | <500ms | ~300ms | Deepgram streaming |
| Parser | <50ms | ~10ms | Local RapidFuzz |
| Claude startup | 2-8s | 2-8s | **The bottleneck** |
| **Total** | <10s | 3-10s | Acceptable for MVP |

Claude Code startup dominates. Consider warm sessions or preloading for future optimization.

---

## Security Considerations

### Attack Surfaces

1. **Grimoire file** — Could contain malicious prompts if modified
2. **STT transcript** — Could inject commands if manipulated
3. **Claude execution** — Has full agent capability

### Mitigations

1. **No shell_command field** — Removed to prevent injection
2. **Confirmation for destructive** — Production deploys, git push, etc.
3. **Dry run mode** — `--sandbox` flag for safe exploration
4. **API key redaction** — Errors never expose credentials

### Trust Model

```
You ──trust──► Grimoire ──trust──► Claude Code ──sandboxed──► System

The grimoire is YOUR configuration. Claude Code has its own sandboxing.
Suzerain adds the voice layer, not new permissions.
```

---

## File Structure

```
suzerain/
├── src/
│   ├── __init__.py
│   ├── main.py            # Entry point, CLI, modes, audio, execution
│   ├── parser.py          # Grimoire matching, expansion
│   └── wake_word.py       # Porcupine integration
│
├── grimoire/
│   └── commands.yaml      # Command definitions
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py        # Pytest fixtures
│   ├── test_parser.py     # Parser unit tests
│   ├── test_main.py       # Integration tests
│   └── test_wake_word.py  # Wake word tests
│
├── docs/
│   ├── GRIMOIRE.md        # Command reference
│   ├── ARCHITECTURE.md    # This file
│   └── ...
│
├── .claude/
│   ├── commands/          # Claude Code slash commands
│   └── skills/            # Claude Code skills
│
├── CLAUDE.md              # AI context file
├── README.md              # User-facing docs
├── SECURITY.md            # Security log
└── requirements.txt       # Python dependencies
```

---

## Dependencies

### Runtime

| Package | Version | Purpose |
|---------|---------|---------|
| pyaudio | >=0.2.14 | Audio capture |
| rapidfuzz | >=3.0 | Fuzzy matching |
| pyyaml | >=6.0 | Grimoire parsing |
| pvporcupine | >=3.0 | Wake word (optional) |

### System

| Dependency | Platform | Install |
|------------|----------|---------|
| portaudio | All | `brew install portaudio` / `apt install portaudio19-dev` |
| Claude Code | All | See Claude Code docs |

### Development

| Package | Purpose |
|---------|---------|
| pytest | Testing |

---

## Future Considerations

### Streaming STT

Currently: Record 3 seconds, then transcribe.
Future: Real-time streaming for faster response.

```
Audio ──stream──► Deepgram ──partial results──► Parser
                                                  │
                                          (match on completion)
```

### Offline Mode

Local STT fallback when network unavailable:
- Vosk (lightweight, fast)
- faster-whisper (higher accuracy)

### Multi-Project

Current: Single project directory.
Future: Project context switching.

```
"In suzerain, the judge smiled"
→ Switch to suzerain project, run tests
```

### Mobile Companion

Phone/watch → Cloud relay → Dev machine.

```
[Wearable]    [Relay]    [Desktop]
Wake Word  →  WebSocket →  Suzerain Daemon
Deepgram   ←  Results   ←  Claude Code
```

---

*"The truth about the world is that anything is possible."*

Now you understand the system. Extend it.
