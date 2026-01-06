# Suzerain Debug Log

Tracking issues encountered and their resolutions during development.

---

## 2026-01-04

### Issue #1: PyAudio Build Failure
**Symptom**: `pip install pyaudio` fails with clang exit code 1

**Cause**: Missing portaudio system dependency on macOS

**Resolution**:
```bash
brew install portaudio
pip install pyaudio
```

---

### Issue #2: Test Assertions Using Wrong Key
**Symptom**: Tests failing with KeyError on `cmd["action"]`

**Cause**: Grimoire schema changed from `action:` to `tags:`, tests not updated

**Resolution**: Changed test assertions from `cmd["action"]` to `cmd["tags"]`

**File**: `tests/test_parser.py`

---

### Issue #3: Modifier Test Wrong Effect Name
**Symptom**: Test expecting `"commit"` effect but getting `"commit_after"`

**Cause**: Modifier effect name changed in grimoire

**Resolution**: Updated test assertion to match new effect name

**File**: `tests/test_parser.py`

---

### Issue #4: Too Permissive Matching (Safety Issue)
**Symptom**: Single words like "evening" matching full commands

**Cause**: Using `token_set_ratio` scorer which is very permissive

**Resolution**:
- Changed `scorer: token_set_ratio` → `scorer: ratio` in grimoire
- Changed `threshold: 70` → `threshold: 80`
- Now single words and word reordering are blocked

**File**: `grimoire/commands.yaml`

---

### Issue #5: Audio Buffer Too Small
**Symptom**: Unstable audio streaming

**Cause**: 32ms buffer (512 samples) too small for stable operation

**Resolution**: Increased to 100ms buffer (1600 samples)

**File**: `src/main.py`
```python
frame_length = 1600  # Was 512
```

---

### Issue #6: simpleaudio Segfault on macOS
**Symptom**: `zsh: segmentation fault python src/main.py`

**Cause**: simpleaudio library crashes on macOS Apple Silicon

**Resolution**: Disabled audio feedback temporarily
```python
# simpleaudio disabled - crashes on macOS Apple Silicon
AUDIO_FEEDBACK = False
```

**File**: `src/main.py`

**TODO**: Replace with alternative (sounddevice, pygame.mixer, or system `afplay`)

---

### Issue #7: Claude CLI Flag Error
**Symptom**: `Error: When using --print, --output-format=stream-json requires --verbose`

**Cause**: Missing `--verbose` flag when using `-p` with `--output-format stream-json`

**Resolution**: Added `--verbose` to command construction
```python
cmd = ["claude", "-p", expansion, "--verbose", "--output-format", "stream-json"]
```

**File**: `src/main.py`

---

### Issue #8: Editable Package Not Reflecting Changes
**Symptom**: Code changes not taking effect despite editing source files

**Cause**: Package installed in editable mode but Python caching old bytecode

**Resolution**:
```bash
# Clear all caches
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete

# Reinstall editable package
pip install -e .
```

**File**: N/A (installation issue)

---

### Issue #9: Claude Output Not Displaying
**Symptom**: `[Executing...]` shown but no Claude response visible, then `✓ Complete`

**Cause**: JSON stream parsing not handling all message types from Claude CLI

**Resolution**: Updated stream parser to handle multiple message types:
- `assistant` → message content
- `content_block_delta` → streaming text
- `tool_use` → show tool being used
- `result` → final result

**File**: `src/main.py`

---

### Issue #10: Audio Feedback Alternative (Resolved)
**Symptom**: simpleaudio crashes on macOS Apple Silicon

**Resolution**: Implemented `acknowledge_command()` using macOS `afplay` with system sounds:
```python
def acknowledge_command():
    # Try system sounds: Tink.aiff, Pop.aiff, Ping.aiff
    subprocess.Popen(["afplay", sound_path], ...)
```

Falls back to visual `[Hmm...]` indicator if sounds unavailable.

**File**: `src/main.py`

---

## Resolved Issues

### Audio Feedback Alternative
Resolved via `afplay` system command for macOS.

Previous options considered:
- `sounddevice` + `soundfile`
- `pygame.mixer`
- System `afplay` command (CHOSEN)
- `AppKit` NSSound (native macOS)

---

## Pending Issues

None currently tracked.

---

## 2026-01-06

### Issue #11: use_continue Commands Missing Prompt
**Symptom**: "they rode on" fails with `Error: Input must be provided either through stdin or as a prompt argument when using --print`

**Cause**: Commands with `use_continue: true` built CLI without `-p` flag:
```python
# Wrong
cmd = ["claude", "--continue", "--output-format", "stream-json"]
```

**Resolution**: Added `-p expansion` to continue commands:
```python
cmd = ["claude", "--continue", "-p", expansion, "--verbose", "--output-format", "stream-json"]
```

**File**: `src/main.py`

---

## Environment Info

- **OS**: macOS Darwin 24.6.0 (Apple Silicon)
- **Python**: 3.13.5
- **PyAudio**: 0.2.14
- **Deepgram**: API (Nova-2)
- **Claude Code**: CLI installed via npm
