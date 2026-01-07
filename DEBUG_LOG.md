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

## 2026-01-07

### Session Summary: Test Fixes, Code Cleanup, PyPI Release

**Started with**: 26 failing tests from manual run

**Achieved**:

1. **Fixed 26 Failing Tests**
   - `test_grimoire_has_5_modifiers` → updated to expect 8 modifiers
   - Fixed `'list_iterator' object has no attribute 'fileno'` (20+ tests)
     - Created `tests/helpers.py` with `MockStdout` class
     - Fixed `src/main.py` to catch `OSError` from `fileno()` in try block
   - Fixed CLI argument flag tests (SANDBOX_MODE, TIMING_MODE, etc.)
     - Moved global flag setting before early exits in `main()`
   - Fixed `test_timeout_returns_exit_code_124`
     - Changed `fileno()` to raise `OSError` instead of returning -1
   - Fixed `test_execute_keyboard_interrupt` - added missing `poll()` method

2. **Error Message Polish**
   - Imported structured error system from `errors.py`
   - Updated all error messages to use `ErrorCode` enum
   - Added actionable suggestions (install commands, links)
   - Removed duplicate `_redact_sensitive()` function (now using `errors.redact_sensitive`)

3. **Code Cleanup with Ruff**
   - Ran `ruff check src/ --fix`
   - Fixed 28 lint issues:
     - Removed unused imports
     - Removed unused variables
     - Fixed f-strings without placeholders
     - Added missing `import simpleaudio` in `ping()` function

4. **PyPI Package Release**
   - Fixed `pyproject.toml` for proper package discovery:
     ```toml
     [tool.setuptools]
     py-modules = ["main", "parser", ...]
     packages = ["grimoire"]
     package-dir = {"" = "src"}
     ```
   - Copied grimoire to `src/grimoire/` for package inclusion
   - Updated `parser.py` to find grimoire in both installed and dev locations
   - Built and uploaded to PyPI: https://pypi.org/project/suzerain/0.1.0/

**Final State**:
- 587 tests passing, 2 skipped
- 0 ruff lint errors
- Package live on PyPI: `pip install suzerain`

---

### Session: Grimoire Selection Onboarding (continued)

**Feature**: Interactive grimoire selection on first run

**Changes Made**:

1. **config.py**: Added `grimoire` section to DEFAULT_CONFIG
   - Default grimoire: `vanilla.yaml` (Simple mode)
   - Added `grimoire_file` convenience property
   - Updated CONFIG_TEMPLATE with grimoire section

2. **parser.py**: Dynamic grimoire loading
   - `_find_grimoire_path()` now reads from config
   - Added `get_grimoire_path()` function
   - `load_grimoire()` automatically reloads when config changes

3. **main.py**: Interactive grimoire picker
   - Added `GRIMOIRES` dict with metadata for each grimoire
   - `select_grimoire()` - interactive selection UI
   - `save_grimoire_choice()` - persists to config
   - Updated `show_welcome(first_run=True)` to include picker
   - Added `--grimoire` / `-g` flag to change grimoire

4. **tests/conftest.py**: Test isolation
   - Added `use_blood_meridian_grimoire` autouse fixture
   - Ensures all tests use commands.yaml regardless of user config

5. **tests/test_errors.py**: Fixed grimoire error tests
   - Updated to use monkeypatch for `get_grimoire_path()`

**Available Grimoires**:
- `vanilla.yaml` (Simple) - Plain commands like "run tests"
- `commands.yaml` (Blood Meridian) - Literary McCarthy phrases
- `dune.yaml` (Dune) - Frank Herbert's desert power

**Final State**:
- 587 tests passing, 2 skipped
- Onboarding flow: Welcome → Grimoire picker → Quick start
- Config persists to `~/.suzerain/config.yaml`

---

### Session: UX Improvements (continued)

**Goal**: Reduce friction in voice workflows

**Changes Made**:

1. **Recording Duration**: 3s → 6s
   - `RECORD_SECONDS = 6` constant added
   - User speech was getting cut off at 3 seconds

2. **Auto-Plain Mode**: `--auto-plain` flag
   - Skips "Run as plain command? [y/N]" prompt
   - Unmatched commands execute immediately
   - Essential for hands-free operation

3. **Dangerous Mode**: `--dangerous` flag
   - Passes `--dangerously-skip-permissions` to Claude Code
   - Bypasses all file/command permission prompts
   - Required for truly uninterrupted voice workflows

**Usage**:
```bash
# Old (prompts for everything)
suzerain

# New (hands-free operation)
suzerain --auto-plain --dangerous
```

**Test Fixes**:
- Updated `conftest.py` to patch both `parser` and `src.parser` modules
- Integration tests require Blood Meridian grimoire in config

**Final State**:
- 587 tests passing
- README.md updated for v0.1.2
- SECURITY.md documents --dangerous flag

---

## Environment Info

- **OS**: macOS Darwin 24.6.0 (Apple Silicon)
- **Python**: 3.13.5
- **PyAudio**: 0.2.14
- **Deepgram**: API (Nova-2)
- **Claude Code**: CLI installed via npm
- **Suzerain**: v0.1.2 on PyPI
