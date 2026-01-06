# Suzerain Test Plan

> "Whatever exists without my knowledge exists without my consent."

This document outlines the testing strategy for Suzerain, a voice-activated Claude Code interface.

---

## Current State

### Existing Tests (21 tests in `tests/test_parser.py`)
- **TestExactMatches**: 3 tests for exact phrase matching
- **TestFuzzyMatches**: 4 tests for fuzzy matching behavior
- **TestNoMatch**: 3 tests for non-matching phrases
- **TestModifiers**: 4 tests for modifier extraction
- **TestThreshold**: 2 tests for threshold behavior
- **TestExpansion**: 3 tests for command expansion
- **TestValidation**: 2 tests for grimoire validation

### Coverage Gaps
| File | Current Coverage | Gap |
|------|-----------------|-----|
| `src/parser.py` | Partial | `match_top_n`, `reload_grimoire`, edge cases |
| `src/main.py` | None | All functions untested |
| `src/wake_word.py` | None | All functions untested |
| Integration | None | No end-to-end pipeline tests |

---

## Test Strategy

### 1. Unit Tests

#### 1.1 Parser Tests (`test_parser.py`) - EXISTING + ADDITIONS

**Additional tests needed:**
- [ ] `match_top_n` returns correct number of matches
- [ ] `match_top_n` respects threshold
- [ ] `reload_grimoire` clears cache
- [ ] `strip_filler_words` edge cases (empty string, all fillers)
- [ ] `get_command_info` returns correct metadata
- [ ] Invalid grimoire handling (missing file, malformed YAML)

#### 1.2 Main Module Tests (`test_main.py`) - NEW

**Functions to test:**

| Function | Mock Strategy | Test Cases |
|----------|--------------|------------|
| `Colors.disable()` | None needed | Verify all colors become empty strings |
| `get_grimoire_keywords()` | None needed | Returns keyword string, handles empty grimoire |
| `transcribe_audio()` | Mock `urllib.request.urlopen` | Success, API error, missing key, timeout |
| `disambiguate()` | Mock `input()` | Valid selection, cancel, invalid input |
| `execute_command()` | Mock `subprocess.Popen` | Success, failure, dry run, sandbox mode, confirmation |
| `validate_mode()` | None needed | Valid/invalid grimoire |
| `show_commands()` | Capture stdout | Lists all commands |

**Priority tests:**
1. `execute_command` with subprocess mocking - CRITICAL
2. `transcribe_audio` with API mocking - CRITICAL
3. Sandbox mode behavior - HIGH
4. Disambiguation flow - MEDIUM

#### 1.3 Wake Word Tests (`test_wake_word.py`) - NEW

**Functions to test:**

| Function | Mock Strategy | Test Cases |
|----------|--------------|------------|
| `WakeWordDetector.__init__` | Mock `pvporcupine.create` | Valid keyword, invalid keyword, missing access key |
| `WakeWordDetector.process_frame` | Mock `porcupine.process` | Wake word detected, not detected |
| `WakeWordDetector.cleanup` | None | Resources released properly |
| `check_setup()` | Mock imports/env | All status combinations |
| `wait_for_wake_word()` | Mock pyaudio | Timeout, detection |

### 2. Integration Tests (`test_integration.py`) - NEW

**End-to-end scenarios:**
- [ ] Text input -> Match -> Expansion (dry run)
- [ ] Text input -> Disambiguation -> Selection -> Expansion
- [ ] Modifier combination with command
- [ ] Error propagation (no match, execution failure)

### 3. Edge Case Tests

**Parser edge cases:**
- Empty input string
- Very long input string (>1000 chars)
- Unicode characters in input
- Input with only filler words
- All modifiers at once

**Main module edge cases:**
- Missing DEEPGRAM_API_KEY
- Claude CLI not installed
- Process interrupted (KeyboardInterrupt)
- Non-TTY environment (no colors)
- Subprocess timeout

**Wake word edge cases:**
- Missing PICOVOICE_ACCESS_KEY
- Invalid audio frame size
- Porcupine not installed
- PyAudio not installed

---

## Mock Strategies

### Deepgram API Mock

```python
@pytest.fixture
def mock_deepgram_response():
    """Mock successful Deepgram transcription."""
    return {
        "results": {
            "channels": [{
                "alternatives": [{
                    "transcript": "the evening redness in the west"
                }]
            }]
        }
    }

@pytest.fixture
def mock_urlopen(mock_deepgram_response, monkeypatch):
    """Mock urllib.request.urlopen for Deepgram API."""
    class MockResponse:
        def read(self):
            return json.dumps(mock_deepgram_response).encode()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: MockResponse())
```

### Claude CLI Mock

```python
@pytest.fixture
def mock_claude_subprocess(monkeypatch):
    """Mock subprocess.Popen for Claude CLI calls."""
    class MockProcess:
        def __init__(self, *args, **kwargs):
            self.returncode = 0
            self.stdout = iter([
                '{"type": "assistant", "message": {"content": [{"type": "text", "text": "Done"}]}}',
                '{"type": "result", "result": "Success"}'
            ])
        def wait(self):
            pass

    monkeypatch.setattr("subprocess.Popen", MockProcess)
```

### Porcupine Mock

```python
@pytest.fixture
def mock_porcupine(monkeypatch):
    """Mock pvporcupine for wake word tests."""
    class MockPorcupine:
        sample_rate = 16000
        frame_length = 512
        def process(self, pcm):
            return -1  # No wake word detected
        def delete(self):
            pass

    monkeypatch.setattr("pvporcupine.create", lambda **kwargs: MockPorcupine())
```

---

## Fixtures Needed

### Test Grimoire

```yaml
# tests/fixtures/test_grimoire.yaml
commands:
  - phrase: "test command one"
    expansion: "Test expansion one"
    tags: [test]
  - phrase: "test command two"
    expansion: "Test expansion two"
    confirmation: true
    tags: [test, critical]

modifiers:
  - phrase: "with modifier"
    effect: test_effect
    expansion_append: "Additional instruction"

parser:
  threshold: 80
  scorer: ratio
  strip_filler_words: [um, uh]
```

### Sample Audio Data

```python
# tests/conftest.py
@pytest.fixture
def sample_audio_wav():
    """Generate minimal valid WAV file for testing."""
    import io
    import wave

    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # 1 second of silence
        wf.writeframes(b'\x00' * 32000)
    return buffer.getvalue()
```

---

## Test Categories

### Fast Tests (run always)
- All parser unit tests
- Colors/utility tests
- Mock-based tests

### Slow Tests (run on CI or explicitly)
- Tests with actual subprocess calls (marked `@pytest.mark.slow`)
- Integration tests

### Skip Conditions
```python
@pytest.mark.skipif(
    not os.environ.get("DEEPGRAM_API_KEY"),
    reason="DEEPGRAM_API_KEY not set"
)
def test_real_transcription():
    """Test with real Deepgram API (requires credentials)."""
    pass
```

---

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing

# Run only fast tests
pytest tests/ -v -m "not slow"

# Run specific test file
pytest tests/test_main.py -v

# Run specific test class
pytest tests/test_parser.py::TestExactMatches -v
```

---

## Success Criteria

1. **Coverage target**: 80%+ line coverage for all source files
2. **All tests pass**: Zero failures in CI
3. **Fast execution**: Full test suite < 5 seconds
4. **Mocking completeness**: No external API calls during unit tests
5. **Edge case coverage**: All error paths have tests

---

## Test Implementation Priority

### Phase 1: Critical (This PR)
1. `test_main.py` - `execute_command` with mocked subprocess
2. `test_main.py` - `transcribe_audio` with mocked API
3. `test_main.py` - Sandbox mode tests
4. `conftest.py` - Common fixtures

### Phase 2: High Priority
1. `test_wake_word.py` - All wake word tests
2. `test_main.py` - Disambiguation flow
3. `test_parser.py` - `match_top_n` tests

### Phase 3: Nice to Have
1. Integration tests
2. Real API tests (with credentials)
3. Performance benchmarks

---

*"The truth about the world is that anything is possible."*
