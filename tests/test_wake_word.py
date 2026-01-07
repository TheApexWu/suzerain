"""
Wake word detection tests - testing Porcupine integration with mocked dependencies.

"He never sleeps, the judge. He is dancing, dancing."
"""

import os
import struct
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# We need to mock pvporcupine before importing wake_word
# because the module checks for it at import time


class TestCheckSetup:
    """Test wake word setup status checking."""

    def test_check_setup_all_ready(self, mock_porcupine_env, monkeypatch):
        """Test status when all dependencies are available."""
        # Mock the availability flags
        monkeypatch.setattr('wake_word.PORCUPINE_AVAILABLE', True)
        monkeypatch.setattr('wake_word.PYAUDIO_AVAILABLE', True)

        from wake_word import check_setup

        status = check_setup()

        assert status["ready"] is True
        assert status["porcupine_installed"] is True
        assert status["pyaudio_installed"] is True
        assert status["access_key_set"] is True
        assert "keywords" in status["message"].lower()

    def test_check_setup_missing_porcupine(self, mock_porcupine_env, monkeypatch):
        """Test status when porcupine is not installed."""
        monkeypatch.setattr('wake_word.PORCUPINE_AVAILABLE', False)
        monkeypatch.setattr('wake_word.PYAUDIO_AVAILABLE', True)

        from wake_word import check_setup

        status = check_setup()

        assert status["ready"] is False
        assert status["porcupine_installed"] is False
        assert "pvporcupine" in status["message"].lower()

    def test_check_setup_missing_pyaudio(self, mock_porcupine_env, monkeypatch):
        """Test status when pyaudio is not installed."""
        monkeypatch.setattr('wake_word.PORCUPINE_AVAILABLE', True)
        monkeypatch.setattr('wake_word.PYAUDIO_AVAILABLE', False)

        from wake_word import check_setup

        status = check_setup()

        assert status["ready"] is False
        assert status["pyaudio_installed"] is False
        assert "pyaudio" in status["message"].lower()

    def test_check_setup_missing_access_key(self, clean_env, monkeypatch):
        """Test status when access key is not set."""
        monkeypatch.setattr('wake_word.PORCUPINE_AVAILABLE', True)
        monkeypatch.setattr('wake_word.PYAUDIO_AVAILABLE', True)

        from wake_word import check_setup

        status = check_setup()

        assert status["ready"] is False
        assert status["access_key_set"] is False
        assert "console.picovoice.ai" in status["message"].lower()


class TestBuiltinKeywords:
    """Test built-in keyword list."""

    def test_builtin_keywords_exist(self):
        """Verify built-in keywords list is populated."""
        from wake_word import BUILTIN_KEYWORDS

        assert len(BUILTIN_KEYWORDS) > 0
        assert "computer" in BUILTIN_KEYWORDS
        assert "alexa" in BUILTIN_KEYWORDS
        assert "jarvis" in BUILTIN_KEYWORDS

    def test_default_keyword(self):
        """Verify default keyword is set."""
        from wake_word import DEFAULT_KEYWORD

        assert DEFAULT_KEYWORD == "computer"


class TestWakeWordDetector:
    """Test WakeWordDetector class with mocked Porcupine."""

    def test_init_missing_porcupine(self, monkeypatch):
        """Test error when porcupine is not installed."""
        monkeypatch.setattr('wake_word.PORCUPINE_AVAILABLE', False)

        from wake_word import WakeWordDetector
        from errors import WakeWordError

        # Raises ImportError (may be wrapped in WakeWordError in future)
        with pytest.raises((ImportError, WakeWordError)) as exc_info:
            WakeWordDetector()

        assert "porcupine" in str(exc_info.value).lower()

    def test_init_missing_access_key(self, clean_env, monkeypatch):
        """Test error when access key is not set."""
        monkeypatch.setattr('wake_word.PORCUPINE_AVAILABLE', True)

        from wake_word import WakeWordDetector
        from errors import WakeWordError

        # Raises ValueError (may be wrapped in WakeWordError in future)
        with pytest.raises((ValueError, WakeWordError)) as exc_info:
            WakeWordDetector()

        assert "access key" in str(exc_info.value).lower()

    def test_init_invalid_keyword(self, mock_porcupine_env, monkeypatch):
        """Test error with invalid keyword."""
        monkeypatch.setattr('wake_word.PORCUPINE_AVAILABLE', True)

        # Mock pvporcupine.create to not be called (validation happens first)
        mock_create = MagicMock()
        monkeypatch.setattr('wake_word.pvporcupine.create', mock_create)

        from wake_word import WakeWordDetector
        from errors import WakeWordError

        # Raises ValueError (may be wrapped in WakeWordError in future)
        with pytest.raises((ValueError, WakeWordError)) as exc_info:
            WakeWordDetector(keyword="invalid_keyword_xyz")

        assert "unknown keyword" in str(exc_info.value).lower()
        mock_create.assert_not_called()

    def test_init_valid_keyword(self, mock_porcupine_env, monkeypatch):
        """Test successful initialization with valid keyword."""
        monkeypatch.setattr('wake_word.PORCUPINE_AVAILABLE', True)

        # Create mock Porcupine instance
        mock_porcupine = MagicMock()
        mock_porcupine.sample_rate = 16000
        mock_porcupine.frame_length = 512

        mock_create = MagicMock(return_value=mock_porcupine)
        monkeypatch.setattr('wake_word.pvporcupine.create', mock_create)

        from wake_word import WakeWordDetector

        detector = WakeWordDetector(keyword="jarvis")

        assert detector.keyword == "jarvis"
        assert detector.sample_rate == 16000
        assert detector.frame_length == 512
        mock_create.assert_called_once()

    def test_process_frame_no_detection(self, mock_porcupine_env, monkeypatch):
        """Test processing audio frame with no wake word detected."""
        monkeypatch.setattr('wake_word.PORCUPINE_AVAILABLE', True)

        mock_porcupine = MagicMock()
        mock_porcupine.sample_rate = 16000
        mock_porcupine.frame_length = 512
        mock_porcupine.process.return_value = -1  # No detection

        mock_create = MagicMock(return_value=mock_porcupine)
        monkeypatch.setattr('wake_word.pvporcupine.create', mock_create)

        from wake_word import WakeWordDetector

        detector = WakeWordDetector(keyword="computer")

        # Create a valid PCM frame (512 samples, 16-bit)
        pcm_frame = b'\x00\x00' * 512

        result = detector.process_frame(pcm_frame)

        assert result is False
        mock_porcupine.process.assert_called_once()

    def test_process_frame_detection(self, mock_porcupine_env, monkeypatch):
        """Test processing audio frame with wake word detected."""
        monkeypatch.setattr('wake_word.PORCUPINE_AVAILABLE', True)

        mock_porcupine = MagicMock()
        mock_porcupine.sample_rate = 16000
        mock_porcupine.frame_length = 512
        mock_porcupine.process.return_value = 0  # Detection (keyword index 0)

        mock_create = MagicMock(return_value=mock_porcupine)
        monkeypatch.setattr('wake_word.pvporcupine.create', mock_create)

        from wake_word import WakeWordDetector

        detector = WakeWordDetector(keyword="computer")

        # Create a valid PCM frame (512 samples, 16-bit)
        pcm_frame = b'\x00\x00' * 512

        result = detector.process_frame(pcm_frame)

        assert result is True

    def test_cleanup(self, mock_porcupine_env, monkeypatch):
        """Test that cleanup releases resources."""
        monkeypatch.setattr('wake_word.PORCUPINE_AVAILABLE', True)

        mock_porcupine = MagicMock()
        mock_porcupine.sample_rate = 16000
        mock_porcupine.frame_length = 512

        mock_create = MagicMock(return_value=mock_porcupine)
        monkeypatch.setattr('wake_word.pvporcupine.create', mock_create)

        from wake_word import WakeWordDetector

        detector = WakeWordDetector(keyword="computer")
        detector.cleanup()

        mock_porcupine.delete.assert_called_once()
        assert detector.porcupine is None

    def test_cleanup_idempotent(self, mock_porcupine_env, monkeypatch):
        """Test that cleanup can be called multiple times safely."""
        monkeypatch.setattr('wake_word.PORCUPINE_AVAILABLE', True)

        mock_porcupine = MagicMock()
        mock_porcupine.sample_rate = 16000
        mock_porcupine.frame_length = 512

        mock_create = MagicMock(return_value=mock_porcupine)
        monkeypatch.setattr('wake_word.pvporcupine.create', mock_create)

        from wake_word import WakeWordDetector

        detector = WakeWordDetector(keyword="computer")
        detector.cleanup()
        detector.cleanup()  # Second call should not raise

        # delete should only be called once
        mock_porcupine.delete.assert_called_once()

    def test_context_manager(self, mock_porcupine_env, monkeypatch):
        """Test using detector as context manager."""
        monkeypatch.setattr('wake_word.PORCUPINE_AVAILABLE', True)

        mock_porcupine = MagicMock()
        mock_porcupine.sample_rate = 16000
        mock_porcupine.frame_length = 512

        mock_create = MagicMock(return_value=mock_porcupine)
        monkeypatch.setattr('wake_word.pvporcupine.create', mock_create)

        from wake_word import WakeWordDetector

        with WakeWordDetector(keyword="computer") as detector:
            assert detector is not None
            assert detector.porcupine is not None

        # After exiting context, cleanup should have been called
        mock_porcupine.delete.assert_called_once()


class TestWaitForWakeWord:
    """Test blocking wait_for_wake_word function."""

    def test_wait_missing_pyaudio(self, monkeypatch):
        """Test error when pyaudio is not installed."""
        monkeypatch.setattr('wake_word.PYAUDIO_AVAILABLE', False)

        from wake_word import wait_for_wake_word
        from errors import AudioError

        # Raises ImportError (may be wrapped in AudioError in future)
        with pytest.raises((ImportError, AudioError)) as exc_info:
            wait_for_wake_word()

        assert "pyaudio" in str(exc_info.value).lower()

    def test_wait_timeout(self, mock_porcupine_env, monkeypatch):
        """Test timeout behavior."""
        import time

        monkeypatch.setattr('wake_word.PORCUPINE_AVAILABLE', True)
        monkeypatch.setattr('wake_word.PYAUDIO_AVAILABLE', True)

        # Mock Porcupine
        mock_porcupine = MagicMock()
        mock_porcupine.sample_rate = 16000
        mock_porcupine.frame_length = 512
        mock_porcupine.process.return_value = -1  # Never detect

        mock_create = MagicMock(return_value=mock_porcupine)
        monkeypatch.setattr('wake_word.pvporcupine.create', mock_create)

        # Mock PyAudio
        mock_stream = MagicMock()
        mock_stream.read.return_value = b'\x00\x00' * 512

        mock_pa = MagicMock()
        mock_pa.open.return_value = mock_stream

        mock_pyaudio_class = MagicMock(return_value=mock_pa)
        monkeypatch.setattr('wake_word.pyaudio.PyAudio', mock_pyaudio_class)

        from wake_word import wait_for_wake_word

        # Very short timeout
        result = wait_for_wake_word(timeout=0.1)

        assert result is False

    def test_wait_detection(self, mock_porcupine_env, monkeypatch):
        """Test successful wake word detection."""
        monkeypatch.setattr('wake_word.PORCUPINE_AVAILABLE', True)
        monkeypatch.setattr('wake_word.PYAUDIO_AVAILABLE', True)

        # Mock Porcupine to detect on second call
        call_count = 0

        def mock_process(pcm):
            nonlocal call_count
            call_count += 1
            return 0 if call_count >= 2 else -1

        mock_porcupine = MagicMock()
        mock_porcupine.sample_rate = 16000
        mock_porcupine.frame_length = 512
        mock_porcupine.process.side_effect = mock_process

        mock_create = MagicMock(return_value=mock_porcupine)
        monkeypatch.setattr('wake_word.pvporcupine.create', mock_create)

        # Mock PyAudio
        mock_stream = MagicMock()
        mock_stream.read.return_value = b'\x00\x00' * 512

        mock_pa = MagicMock()
        mock_pa.open.return_value = mock_stream

        mock_pyaudio_class = MagicMock(return_value=mock_pa)
        monkeypatch.setattr('wake_word.pyaudio.PyAudio', mock_pyaudio_class)

        from wake_word import wait_for_wake_word

        result = wait_for_wake_word()

        assert result is True

    def test_wait_cleanup_on_success(self, mock_porcupine_env, monkeypatch):
        """Test that resources are cleaned up after detection."""
        monkeypatch.setattr('wake_word.PORCUPINE_AVAILABLE', True)
        monkeypatch.setattr('wake_word.PYAUDIO_AVAILABLE', True)

        # Mock Porcupine to detect immediately
        mock_porcupine = MagicMock()
        mock_porcupine.sample_rate = 16000
        mock_porcupine.frame_length = 512
        mock_porcupine.process.return_value = 0  # Immediate detection

        mock_create = MagicMock(return_value=mock_porcupine)
        monkeypatch.setattr('wake_word.pvporcupine.create', mock_create)

        # Mock PyAudio
        mock_stream = MagicMock()
        mock_stream.read.return_value = b'\x00\x00' * 512

        mock_pa = MagicMock()
        mock_pa.open.return_value = mock_stream

        mock_pyaudio_class = MagicMock(return_value=mock_pa)
        monkeypatch.setattr('wake_word.pyaudio.PyAudio', mock_pyaudio_class)

        from wake_word import wait_for_wake_word

        wait_for_wake_word()

        # Verify cleanup
        mock_stream.stop_stream.assert_called_once()
        mock_stream.close.assert_called_once()
        mock_pa.terminate.assert_called_once()


class TestPCMConversion:
    """Test PCM frame processing."""

    def test_frame_unpacking(self, mock_porcupine_env, monkeypatch):
        """Test that PCM frames are unpacked correctly."""
        monkeypatch.setattr('wake_word.PORCUPINE_AVAILABLE', True)

        # Create known PCM data
        samples = [100, -100, 32767, -32768, 0]  # Various 16-bit values
        pcm_data = struct.pack(f"{len(samples)}h", *samples)

        # Pad to 512 samples
        padding_needed = 512 - len(samples)
        pcm_frame = pcm_data + (b'\x00\x00' * padding_needed)

        # Mock Porcupine to capture the input
        captured_input = []

        def capture_process(pcm):
            captured_input.append(pcm)
            return -1

        mock_porcupine = MagicMock()
        mock_porcupine.sample_rate = 16000
        mock_porcupine.frame_length = 512
        mock_porcupine.process.side_effect = capture_process

        mock_create = MagicMock(return_value=mock_porcupine)
        monkeypatch.setattr('wake_word.pvporcupine.create', mock_create)

        from wake_word import WakeWordDetector

        detector = WakeWordDetector(keyword="computer")
        detector.process_frame(pcm_frame)

        # Verify the input was unpacked to a tuple of integers
        assert len(captured_input) == 1
        unpacked = captured_input[0]
        assert len(unpacked) == 512
        assert unpacked[0] == 100
        assert unpacked[1] == -100
        assert unpacked[2] == 32767
        assert unpacked[3] == -32768
        assert unpacked[4] == 0
