# Suzerain v0.4 Architecture

> Conversational voice interface for Claude Code with transparency and meta-prompted summaries.

---

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SUZERAIN v0.4 PIPELINE                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  AUDIO   │───▶│   STT    │───▶│  ROUTER  │───▶│  CLAUDE  │───▶│  OUTPUT  │
│  INPUT   │    │ Deepgram │    │          │    │   CODE   │    │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │
     ▼               ▼               ▼               ▼               ▼
 ┌────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
 │Feedback│    │ "Heard:" │    │ Classify │    │Streaming │    │ Summary  │
 │  Tone  │    │ Display  │    │ & Route  │    │ Tool Use │    │   TTS    │
 └────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                                    │
                              ┌─────┴─────┐
                              ▼           ▼
                         ┌────────┐  ┌────────┐
                         │Natural │  │Grimoire│
                         │Language│  │ Match  │
                         └────────┘  └────────┘
```

---

## Component Architecture

### 1. Audio Input Layer

```
┌─────────────────────────────────────────────────┐
│                 AUDIO INPUT                      │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌─────────────┐    ┌─────────────────────────┐ │
│  │  PyAudio    │───▶│  Wake Word (Porcupine)  │ │
│  │  Stream     │    │  or Push-to-Talk        │ │
│  └─────────────┘    └───────────┬─────────────┘ │
│                                 │               │
│                    ┌────────────▼────────────┐  │
│                    │   Voice Activity Det.   │  │
│                    │   (Deepgram Live)       │  │
│                    └────────────┬────────────┘  │
│                                 │               │
│                    ┌────────────▼────────────┐  │
│                    │   Feedback: "Listening" │  │
│                    │   🔴 Recording indicator │  │
│                    └─────────────────────────┘  │
│                                                  │
└─────────────────────────────────────────────────┘

Latency Budget: <100ms from speech start to visual feedback
```

### 2. Speech-to-Text Layer

```
┌─────────────────────────────────────────────────┐
│                SPEECH-TO-TEXT                    │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌─────────────────────────────────────────────┐│
│  │           Deepgram Nova-2                   ││
│  │  ┌─────────────────────────────────────────┐││
│  │  │ WebSocket streaming                     │││
│  │  │ Live endpointing (speech end detection) │││
│  │  │ Interim results for immediate feedback  │││
│  │  └─────────────────────────────────────────┘││
│  └─────────────────────────────────────────────┘│
│                        │                         │
│              ┌─────────▼─────────┐              │
│              │  Transcript +     │              │
│              │  Confidence Score │              │
│              └─────────┬─────────┘              │
│                        │                         │
│              ┌─────────▼─────────┐              │
│              │ Display: "Heard:" │              │
│              │ "run the tests"   │              │
│              └───────────────────┘              │
│                                                  │
└─────────────────────────────────────────────────┘

Latency Budget: <300ms from speech end to transcript
```

### 3. Command Router

```
┌─────────────────────────────────────────────────┐
│                 COMMAND ROUTER                   │
├─────────────────────────────────────────────────┤
│                                                  │
│  Input: "run the tests" (transcript)            │
│                                                  │
│  ┌─────────────────────────────────────────────┐│
│  │              MODE CHECK                     ││
│  │  config.mode == "natural" or "grimoire"    ││
│  └──────────────────┬──────────────────────────┘│
│                     │                            │
│        ┌────────────┴────────────┐              │
│        ▼                         ▼              │
│  ┌───────────┐            ┌───────────┐        │
│  │  NATURAL  │            │ GRIMOIRE  │        │
│  │   MODE    │            │   MODE    │        │
│  └─────┬─────┘            └─────┬─────┘        │
│        │                        │               │
│        ▼                        ▼               │
│  Pass directly           RapidFuzz match       │
│  to Claude               against commands.yaml │
│                                │                │
│                    ┌───────────┴───────────┐   │
│                    ▼                       ▼   │
│              Match Found            No Match   │
│              (score ≥ 80)          (fallback)  │
│                    │                       │   │
│                    ▼                       ▼   │
│              Use expansion          Pass raw   │
│              from grimoire          to Claude  │
│                                                 │
│  Output: { prompt, confidence, source }        │
│                                                  │
└─────────────────────────────────────────────────┘
```

### 4. Claude Execution Layer (with Meta-Prompting)

```
┌─────────────────────────────────────────────────┐
│            CLAUDE EXECUTION LAYER                │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌─────────────────────────────────────────────┐│
│  │           META-PROMPT INJECTION             ││
│  │                                             ││
│  │  User prompt: "run the tests"              ││
│  │            +                                ││
│  │  Conversation context (if any)             ││
│  │            +                                ││
│  │  META_SYSTEM_PROMPT (summary directive)    ││
│  │            =                                ││
│  │  Final prompt to Claude                    ││
│  └─────────────────────────────────────────────┘│
│                        │                         │
│              ┌─────────▼─────────┐              │
│              │   Claude Code    │               │
│              │   subprocess     │               │
│              │   --output-format│               │
│              │   stream-json    │               │
│              └─────────┬─────────┘              │
│                        │                         │
│              ┌─────────▼─────────┐              │
│              │ STREAMING OUTPUT │               │
│              │ HANDLER          │               │
│              │                  │               │
│              │ ┌──────────────┐ │               │
│              │ │ Tool Use:    │ │               │
│              │ │ [Claude]     │ │               │
│              │ │ Reading...   │ │               │
│              │ └──────────────┘ │               │
│              │ ┌──────────────┐ │               │
│              │ │ Thinking:    │ │               │
│              │ │ [dim text]   │ │               │
│              │ └──────────────┘ │               │
│              │ ┌──────────────┐ │               │
│              │ │ Assistant:   │ │               │
│              │ │ [streaming]  │ │               │
│              │ └──────────────┘ │               │
│              └─────────┬─────────┘              │
│                        │                         │
│              ┌─────────▼─────────┐              │
│              │ SUMMARY EXTRACTOR│               │
│              │ Parse final      │               │
│              │ summary block    │               │
│              └───────────────────┘              │
│                                                  │
└─────────────────────────────────────────────────┘
```

### 5. Output Layer

```
┌─────────────────────────────────────────────────┐
│                 OUTPUT LAYER                     │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌─────────────────────────────────────────────┐│
│  │            VISUAL OUTPUT                    ││
│  │                                             ││
│  │  Terminal display:                         ││
│  │  - Tool calls as they happen               ││
│  │  - Progress indicators                     ││
│  │  - Elapsed time                            ││
│  │  - Final summary                           ││
│  └─────────────────────────────────────────────┘│
│                        +                         │
│  ┌─────────────────────────────────────────────┐│
│  │            AUDIO OUTPUT                     ││
│  │                                             ││
│  │  ┌──────────────────────────────────────┐  ││
│  │  │  Summary TTS (macOS `say` command)   │  ││
│  │  │  "Tests complete. 47 files passed."  │  ││
│  │  └──────────────────────────────────────┘  ││
│  │                                             ││
│  │  ┌──────────────────────────────────────┐  ││
│  │  │  Sound effects (afplay)              │  ││
│  │  │  - Success: Glass.aiff               │  ││
│  │  │  - Error: Basso.aiff                 │  ││
│  │  │  - Processing: Morse.aiff            │  ││
│  │  └──────────────────────────────────────┘  ││
│  └─────────────────────────────────────────────┘│
│                        +                         │
│  ┌─────────────────────────────────────────────┐│
│  │         CONVERSATION CONTEXT                ││
│  │                                             ││
│  │  Store for next turn:                      ││
│  │  - User input                              ││
│  │  - Summary of what was done                ││
│  │  - Files touched                           ││
│  └─────────────────────────────────────────────┘│
│                                                  │
└─────────────────────────────────────────────────┘
```

---

## Data Flow

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            COMPLETE DATA FLOW                               │
└────────────────────────────────────────────────────────────────────────────┘

User speaks: "add input validation to the form"
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: CAPTURE                                                            │
│ ├─ PyAudio captures audio stream                                            │
│ ├─ Porcupine detects wake word (if enabled)                                │
│ ├─ Feedback tone plays (Tink.aiff)                                         │
│ └─ Recording indicator shows: "● Recording... [0.0s]"                       │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: TRANSCRIBE                                                         │
│ ├─ Audio streams to Deepgram via WebSocket                                 │
│ ├─ Interim results update display: "Heard: add input valid..."             │
│ ├─ Endpointing detects speech end                                          │
│ └─ Final transcript: "add input validation to the form" (confidence: 0.94) │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: ROUTE                                                              │
│ ├─ Mode check: config.mode = "natural"                                     │
│ ├─ Grimoire check (optional): No strong match (best: 45%)                  │
│ └─ Route decision: Pass to Claude as natural language                      │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 4: PREPARE PROMPT                                                     │
│ ├─ Inject conversation context (if any previous turns)                     │
│ ├─ Inject meta-prompt for summary formatting                               │
│ └─ Final prompt:                                                            │
│    """                                                                      │
│    [Previous context if any]                                               │
│                                                                             │
│    User request: add input validation to the form                          │
│                                                                             │
│    [META_SYSTEM_PROMPT - summary directive]                                │
│    """                                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 5: EXECUTE                                                            │
│ ├─ Spawn: claude -p "<prompt>" --output-format stream-json                 │
│ ├─ Stream tool_use events:                                                 │
│ │   [Claude] Reading src/components/Form.tsx...                            │
│ │   [Claude] Analyzing form structure...                                    │
│ │   [Claude] Writing src/utils/validation.ts...                            │
│ │   [Claude] Editing Form.tsx to add validation...                         │
│ │   [Claude] Running npm test...                                           │
│ ├─ Stream assistant text (dimmed during thinking)                          │
│ └─ Capture final result + summary                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 6: OUTPUT                                                             │
│ ├─ Extract summary from Claude's response                                  │
│ ├─ Display: "+ Complete (8.3s, 5 tools used)"                              │
│ ├─ Speak summary via TTS:                                                  │
│ │   "Added email and password validation. Created validation.ts,           │
│ │    modified Form.tsx. All tests pass."                                   │
│ ├─ Play success tone (Glass.aiff)                                          │
│ └─ Store turn in conversation context                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 7: READY FOR NEXT TURN                                                │
│ ├─ Context retained: knows about validation.ts, Form.tsx                   │
│ ├─ User can say: "add tests for that"                                      │
│ └─ "that" resolves to validation functions from previous turn              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Classes

### MetaPromptExecutor

```python
class MetaPromptExecutor:
    """
    Wraps Claude Code execution with meta-prompting for summaries.
    """

    META_SYSTEM_PROMPT = '''
After completing the task, end your response with a SUMMARY block:

```summary
Action: [What you did in one sentence]
Changes: [List of files modified/created]
Status: [Success/Failure + any warnings]
```

Keep the summary suitable for text-to-speech (under 15 seconds spoken).
'''

    def __init__(self, context: ConversationContext = None):
        self.context = context or ConversationContext()

    def execute(self, user_input: str) -> ExecutionResult:
        prompt = self._build_prompt(user_input)
        result = self._run_claude(prompt)
        summary = self._extract_summary(result.output)

        if summary:
            speak_text(summary)

        self.context.add_turn(user_input, summary, result.files_touched)
        return result

    def _build_prompt(self, user_input: str) -> str:
        parts = []
        if self.context.has_history():
            parts.append(self.context.get_context_prompt())
        parts.append(f"User request: {user_input}")
        parts.append(self.META_SYSTEM_PROMPT)
        return "\n\n".join(parts)

    def _extract_summary(self, output: str) -> str | None:
        # Parse ```summary block from Claude's output
        ...
```

### ConversationContext

```python
@dataclass
class Turn:
    user_input: str
    summary: str
    files_touched: list[str]
    timestamp: float

class ConversationContext:
    """
    Maintains conversation history for multi-turn interactions.
    """

    def __init__(self, max_turns: int = 5):
        self.turns: list[Turn] = []
        self.max_turns = max_turns

    def add_turn(self, user_input: str, summary: str, files: list[str]):
        self.turns.append(Turn(user_input, summary, files, time.time()))
        if len(self.turns) > self.max_turns:
            self.turns.pop(0)

    def has_history(self) -> bool:
        return len(self.turns) > 0

    def get_context_prompt(self) -> str:
        if not self.turns:
            return ""

        lines = ["Recent conversation:"]
        for turn in self.turns[-3:]:
            lines.append(f"- User: {turn.user_input}")
            lines.append(f"  Result: {turn.summary}")
        return "\n".join(lines)

    def get_recent_files(self) -> list[str]:
        """Files touched in recent turns, for resolving 'that' references."""
        files = []
        for turn in self.turns[-3:]:
            files.extend(turn.files_touched)
        return list(set(files))
```

### TransparentOutputHandler

```python
class TransparentOutputHandler:
    """
    Processes Claude's streaming output with human-readable tool descriptions.
    """

    TOOL_VERBS = {
        "Read": "Reading",
        "Write": "Creating",
        "Edit": "Editing",
        "Bash": "Running",
        "Grep": "Searching",
        "Glob": "Finding",
        "Task": "Delegating",
    }

    def __init__(self):
        self.tools_used: list[str] = []
        self.files_touched: list[str] = []
        self.start_time = time.time()

    def on_tool_use(self, tool_name: str, tool_input: dict):
        description = self._humanize(tool_name, tool_input)
        print(f"{Colors.CYAN}[Claude] {description}{Colors.RESET}")
        self.tools_used.append(tool_name)

    def _humanize(self, tool: str, input: dict) -> str:
        verb = self.TOOL_VERBS.get(tool, tool)

        if tool == "Read":
            path = input.get("file_path", "file")
            self.files_touched.append(path)
            return f"{verb} {os.path.basename(path)}..."

        if tool == "Bash":
            cmd = input.get("command", "")[:40]
            return f"{verb} `{cmd}`..."

        if tool == "Edit":
            path = input.get("file_path", "file")
            self.files_touched.append(path)
            return f"{verb} {os.path.basename(path)}..."

        return f"{verb}..."

    def get_summary_stats(self) -> str:
        elapsed = time.time() - self.start_time
        tools = len(self.tools_used)
        return f"{elapsed:.1f}s, {tools} tool{'s' if tools != 1 else ''} used"
```

---

## File Structure

```
suzerain/
├── src/
│   ├── main.py                 # Entry point, CLI
│   ├── executor.py             # NEW: MetaPromptExecutor
│   ├── context.py              # NEW: ConversationContext
│   ├── transparency.py         # NEW: TransparentOutputHandler
│   ├── parser.py               # Grimoire matching (unchanged)
│   ├── streaming_stt.py        # Deepgram integration (unchanged)
│   ├── audio_feedback.py       # Sound effects (unchanged)
│   ├── config.py               # Config management (add mode setting)
│   └── grimoire/
│       ├── commands.yaml       # Blood Meridian grimoire
│       └── vanilla.yaml        # Plain English commands
├── tests/
│   ├── test_executor.py        # NEW
│   ├── test_context.py         # NEW
│   └── ...
└── docs/
    ├── PIVOT.md                # This pivot explanation
    └── ARCHITECTURE_V04.md     # This file
```

---

## Latency Budget (v0.4)

| Stage | Target | Measurement Point |
|-------|--------|-------------------|
| Wake word detection | <100ms | Audio start → wake detected |
| Recording indicator | <50ms | Wake detected → visual feedback |
| STT streaming | <300ms | Speech end → final transcript |
| "Heard" display | <50ms | Transcript → visual display |
| Claude startup | <2s | Prompt sent → first tool_use |
| Tool use display | <100ms | Tool event → visual display |
| Summary extraction | <100ms | Claude done → summary parsed |
| TTS start | <200ms | Summary parsed → speech starts |

**Perceived latency target**: <500ms from speech end to first visible feedback.

---

## Configuration

```yaml
# ~/.suzerain/config.yaml

# v0.4 settings
mode: natural              # "natural" (default) or "grimoire"
conversation:
  enabled: true            # Multi-turn context
  max_turns: 5             # How many turns to remember
  timeout_minutes: 30      # Clear context after inactivity

summary:
  enabled: true            # Meta-prompt for summaries
  tts_enabled: true        # Speak summaries
  tts_voice: "Samantha"    # macOS voice

transparency:
  show_tool_calls: true    # Display [Claude] Reading...
  show_elapsed: true       # Show elapsed time
  show_thinking: false     # Hide extended thinking by default

# Existing settings
deepgram:
  api_key: ...
picovoice:
  access_key: ...
grimoire:
  file: commands.yaml
```

---

## Migration from v0.3

1. **Backwards Compatible**: All existing grimoire commands still work
2. **New Default**: `mode: natural` means plain English works without matching
3. **Optional Grimoire**: Use `--grimoire` flag or `mode: grimoire` in config
4. **Conversation Off**: Set `conversation.enabled: false` for v0.3 behavior

---

*"The truth about the world is that anything is permitted."*
