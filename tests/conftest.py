"""
Shared test fixtures for Suzerain test suite.

"They rode on."
"""

import io
import json
import os
import sys
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# === Path Setup ===

# Add tests directory to path (for helpers module)
TESTS_PATH = Path(__file__).parent
sys.path.insert(0, str(TESTS_PATH))

# Add src to path for imports
SRC_PATH = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_PATH))


# === Audio Fixtures ===

@pytest.fixture
def sample_audio_wav():
    """Generate minimal valid WAV file for testing."""
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # 1 second of silence (16000 samples * 2 bytes)
        wf.writeframes(b'\x00' * 32000)
    return buffer.getvalue()


@pytest.fixture
def sample_pcm_frame():
    """Generate a single PCM audio frame (512 samples for Porcupine)."""
    # 512 samples of silence (16-bit signed, little-endian)
    return b'\x00\x00' * 512


# === API Response Fixtures ===

@pytest.fixture
def deepgram_success_response():
    """Mock successful Deepgram transcription response."""
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
def deepgram_empty_response():
    """Mock Deepgram response with no transcript."""
    return {
        "results": {
            "channels": [{
                "alternatives": [{
                    "transcript": ""
                }]
            }]
        }
    }


# === Mock Classes ===

class MockURLResponse:
    """Mock urllib response object."""

    def __init__(self, data):
        self._data = data

    def read(self):
        return json.dumps(self._data).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# Import MockStdout from helpers module
from helpers import MockStdout


class MockSubprocess:
    """Mock subprocess.Popen for Claude CLI calls."""

    def __init__(self, cmd, stdout=None, stderr=None, text=False, return_code=0, output_lines=None):
        self.cmd = cmd
        self.returncode = return_code
        self._output_lines = output_lines or [
            '{"type": "assistant", "message": {"content": [{"type": "text", "text": "Done"}]}}',
            '{"type": "result", "result": "Success"}'
        ]
        self.stdout = MockStdout(self._output_lines)

    def poll(self):
        """Check if process has finished. Returns returncode if done, None if running."""
        return self.returncode

    def wait(self, timeout=None):
        pass


class MockPorcupine:
    """Mock Porcupine wake word detector."""

    sample_rate = 16000
    frame_length = 512

    def __init__(self, detect_on_call=None):
        """
        Args:
            detect_on_call: If set, return detection (0) on this call number
        """
        self._call_count = 0
        self._detect_on_call = detect_on_call

    def process(self, pcm):
        """Return -1 (no detection) unless detect_on_call matches."""
        self._call_count += 1
        if self._detect_on_call is not None and self._call_count == self._detect_on_call:
            return 0  # Wake word detected
        return -1  # No detection

    def delete(self):
        pass


# === Fixture Factories ===

@pytest.fixture
def mock_urlopen_factory():
    """Factory to create mock urlopen with custom response."""
    def _factory(response_data):
        def mock_urlopen(request, timeout=None):
            return MockURLResponse(response_data)
        return mock_urlopen
    return _factory


def create_mock_process(return_code=0, output_lines=None):
    """Helper function to create a mock process with proper stdout.

    Use this in tests to create inline MockProcess classes:

        class MockProcess:
            def __init__(self, *args, **kwargs):
                self.returncode = 0
                self.stdout = MockStdout([...])
            def poll(self):
                return self.returncode
            def wait(self, timeout=None):
                pass
    """
    return MockSubprocess(
        cmd=[],
        return_code=return_code,
        output_lines=output_lines
    )


@pytest.fixture
def mock_subprocess_factory():
    """Factory to create mock subprocess with custom behavior."""
    def _factory(return_code=0, output_lines=None):
        def mock_popen(*args, **kwargs):
            return MockSubprocess(
                args[0] if args else [],
                return_code=return_code,
                output_lines=output_lines
            )
        return mock_popen
    return _factory


# === Environment Fixtures ===

@pytest.fixture
def mock_deepgram_env(monkeypatch):
    """Set up mock Deepgram API key (must be 32+ alphanumeric chars to pass validation)."""
    monkeypatch.setenv("DEEPGRAM_API_KEY", "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2")


@pytest.fixture
def mock_porcupine_env(monkeypatch):
    """Set up mock Picovoice access key."""
    monkeypatch.setenv("PICOVOICE_ACCESS_KEY", "test-access-key-12345")


@pytest.fixture
def clean_env(monkeypatch):
    """Remove API keys from environment for testing missing key scenarios."""
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("PICOVOICE_ACCESS_KEY", raising=False)


# === Grimoire Fixtures ===

@pytest.fixture(autouse=True)
def use_blood_meridian_grimoire(monkeypatch):
    """Ensure all tests use Blood Meridian grimoire (commands.yaml) regardless of user config."""
    # Patch both possible module references (src.parser and parser)
    import parser as parser_module
    try:
        import src.parser as src_parser_module
    except ImportError:
        src_parser_module = None

    original_find = parser_module._find_grimoire_path

    def patched_find(grimoire_file=None):
        # Force commands.yaml for tests
        return original_find("commands.yaml")

    # Patch the parser module
    monkeypatch.setattr(parser_module, "_find_grimoire_path", patched_find)
    monkeypatch.setattr(parser_module, "get_grimoire_path", lambda: patched_find())
    parser_module._grimoire_cache = None
    parser_module._grimoire_cache_path = None

    # Also patch src.parser if it exists
    if src_parser_module:
        monkeypatch.setattr(src_parser_module, "_find_grimoire_path", patched_find)
        monkeypatch.setattr(src_parser_module, "get_grimoire_path", lambda: patched_find())
        src_parser_module._grimoire_cache = None
        src_parser_module._grimoire_cache_path = None


@pytest.fixture
def sample_command():
    """A sample grimoire command for testing."""
    return {
        "phrase": "test phrase here",
        "expansion": "Test expansion content",
        "tags": ["test", "sample"],
        "confirmation": False
    }


@pytest.fixture
def sample_command_with_confirmation():
    """A sample command that requires confirmation."""
    return {
        "phrase": "dangerous test phrase",
        "expansion": "Dangerous expansion content",
        "tags": ["test", "critical"],
        "confirmation": True
    }


@pytest.fixture
def sample_command_with_shell():
    """A sample command with shell_command."""
    return {
        "phrase": "run shell test",
        "expansion": "After running the shell command...",
        "shell_command": "echo 'test'",
        "tags": ["test", "shell"],
        "confirmation": False
    }


@pytest.fixture
def sample_modifier():
    """A sample modifier for testing."""
    return {
        "phrase": "with test modifier",
        "effect": "test_effect",
        "expansion_append": "Additional test instruction"
    }


@pytest.fixture
def sample_dry_run_modifier():
    """A dry run modifier for testing."""
    return {
        "phrase": "and the judge watched",
        "effect": "dry_run",
        "expansion_append": "DRY RUN MODE: Don't actually execute anything."
    }


# === I/O Fixtures ===

@pytest.fixture
def capture_stdout(monkeypatch):
    """Capture stdout for testing print statements."""
    captured = io.StringIO()
    monkeypatch.setattr(sys, 'stdout', captured)
    return captured


@pytest.fixture
def mock_input_factory(monkeypatch):
    """Factory to mock input() with predetermined responses."""
    def _factory(responses):
        """
        Args:
            responses: List of strings to return for successive input() calls
        """
        response_iter = iter(responses)
        monkeypatch.setattr('builtins.input', lambda _: next(response_iter))
    return _factory


# === Test Markers ===

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "requires_api: marks tests that require real API credentials")
