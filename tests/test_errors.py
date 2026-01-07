"""
Tests for error handling throughout Suzerain.

"The truth about the world, he said, is that anything is possible."

Tests cover:
- Custom exception classes and error codes
- Redaction of sensitive data
- Retry logic with exponential backoff
- Graceful degradation scenarios
- Error message formatting
"""

import os
import sys
import time
import pytest
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from errors import (
    SuzerainError,
    ConfigurationError,
    STTError,
    AudioError,
    WakeWordError,
    GrimoireError,
    ExecutionError,
    NetworkError,
    ErrorCode,
    redact_sensitive,
    retry_with_backoff,
    RetryContext,
    fallback,
    FallbackMode,
    format_error_for_display,
    get_api_key,
)


# === Exception Tests ===

class TestSuzerainError:
    """Test base exception class."""

    def test_basic_error(self):
        """Test creating a basic error."""
        error = SuzerainError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.code is None
        assert error.recoverable is False

    def test_error_with_code(self):
        """Test error with error code."""
        error = SuzerainError(
            "API key not set",
            code=ErrorCode.CONFIG_MISSING_KEY
        )
        assert f"[E{ErrorCode.CONFIG_MISSING_KEY:04d}]" in str(error)
        assert error.code == ErrorCode.CONFIG_MISSING_KEY

    def test_error_with_suggestion(self):
        """Test error with suggestion."""
        error = SuzerainError(
            "Config not found",
            suggestion="Run setup first"
        )
        msg = error.user_message()
        assert "Config not found" in msg
        assert "Run setup first" in msg

    def test_error_hierarchy(self):
        """Test that all errors inherit from SuzerainError."""
        errors = [
            ConfigurationError("test"),
            STTError("test"),
            AudioError("test"),
            WakeWordError("test"),
            GrimoireError("test"),
            ExecutionError("test"),
            NetworkError("test"),
        ]

        for error in errors:
            assert isinstance(error, SuzerainError)
            # Should be catchable as SuzerainError
            try:
                raise error
            except SuzerainError:
                pass  # Expected

    def test_log_message_includes_details(self):
        """Test that log message includes technical details."""
        error = SuzerainError(
            "Connection failed",
            details="SSL handshake timeout after 30s"
        )
        log_msg = error.log_message()
        assert "Connection failed" in log_msg
        assert "SSL handshake timeout" in log_msg


# === Redaction Tests ===

class TestRedaction:
    """Test sensitive data redaction."""

    def test_redact_api_key(self):
        """Test that API keys are redacted."""
        api_key = "sk-1234567890abcdef1234567890abcdef"
        text = f"Error with key {api_key}"

        result = redact_sensitive(text, api_key)

        assert api_key not in result
        assert "[REDACTED" in result

    def test_redact_partial_key(self):
        """Test that partial key matches are also redacted."""
        api_key = "sk-1234567890abcdef1234567890abcdef"
        partial = api_key[:8]
        text = f"Key starts with {partial}..."

        result = redact_sensitive(text, api_key)

        assert partial not in result

    def test_redact_bearer_token(self):
        """Test that bearer tokens are redacted."""
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"

        result = redact_sensitive(text)

        assert "eyJhbG" not in result
        assert "REDACTED" in result  # May be [REDACTED] or [REDACTED_KEY]

    def test_redact_url_credentials(self):
        """Test that URL credentials are redacted."""
        text = "https://user:password123@api.example.com/endpoint"

        result = redact_sensitive(text)

        assert "password123" not in result

    def test_empty_text(self):
        """Test handling of empty text."""
        assert redact_sensitive("") == ""
        assert redact_sensitive(None) is None

    def test_no_secrets(self):
        """Test text without secrets is unchanged."""
        text = "Just a normal error message"
        assert redact_sensitive(text) == text


# === Retry Logic Tests ===

class TestRetryWithBackoff:
    """Test retry decorator."""

    def test_succeeds_first_try(self):
        """Test function that succeeds immediately."""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def succeeds():
            nonlocal call_count
            call_count += 1
            return "success"

        result = succeeds()
        assert result == "success"
        assert call_count == 1

    def test_succeeds_after_retry(self):
        """Test function that succeeds after failures."""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def fails_then_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("Temporary failure")
            return "success"

        result = fails_then_succeeds()
        assert result == "success"
        assert call_count == 3

    def test_exhausts_retries(self):
        """Test function that always fails."""
        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise NetworkError("Persistent failure")

        with pytest.raises(NetworkError):
            always_fails()

        # Initial call + 2 retries = 3 total
        assert call_count == 3

    def test_only_retries_specified_exceptions(self):
        """Test that only specified exceptions trigger retry."""
        call_count = 0

        @retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            retryable_exceptions=(NetworkError,)
        )
        def raises_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        with pytest.raises(ValueError):
            raises_value_error()

        # Should not retry ValueError
        assert call_count == 1

    def test_on_retry_callback(self):
        """Test that retry callback is invoked."""
        callbacks = []

        def on_retry(exc, attempt, delay):
            callbacks.append((type(exc).__name__, attempt, delay))

        @retry_with_backoff(
            max_retries=2,
            base_delay=0.01,
            on_retry=on_retry
        )
        def fails_twice():
            if len(callbacks) < 2:
                raise NetworkError("fail")
            return "ok"

        result = fails_twice()
        assert result == "ok"
        assert len(callbacks) == 2
        assert callbacks[0][1] == 1  # First retry
        assert callbacks[1][1] == 2  # Second retry


class TestRetryContext:
    """Test RetryContext context manager."""

    def test_retry_context_basic(self):
        """Test basic retry context usage."""
        attempts = 0

        with RetryContext(max_retries=3, base_delay=0.01) as retry:
            while retry.should_continue():
                attempts += 1
                if attempts < 3:
                    retry.record_failure()
                else:
                    retry.success()
                    break

        assert attempts == 3

    def test_retry_context_exhausted(self):
        """Test retry context when all retries exhausted."""
        attempts = 0

        with RetryContext(max_retries=2, base_delay=0.01) as retry:
            while retry.should_continue():
                attempts += 1
                retry.record_failure()

        assert attempts == 3  # Initial + 2 retries


# === Fallback Mode Tests ===

class TestFallbackMode:
    """Test graceful degradation tracking."""

    def test_activate_fallback(self):
        """Test activating a fallback."""
        fb = FallbackMode()
        fb.activate("stt", "API unavailable")

        assert fb.is_active("stt")
        assert fb.get_reason("stt") == "API unavailable"

    def test_deactivate_fallback(self):
        """Test deactivating a fallback."""
        fb = FallbackMode()
        fb.activate("stt", "API unavailable")
        fb.deactivate("stt")

        assert not fb.is_active("stt")

    def test_get_all_active(self):
        """Test getting all active fallbacks."""
        fb = FallbackMode()
        fb.activate("stt", "STT down")
        fb.activate("wake_word", "Wake word unavailable")

        active = fb.get_all_active()
        assert len(active) == 2
        assert "stt" in active
        assert "wake_word" in active

    def test_status_message(self):
        """Test user-friendly status message."""
        fb = FallbackMode()
        fb.activate("stt", "API down")

        msg = fb.get_status_message()
        assert "type" in msg.lower() or "voice" in msg.lower()

    def test_no_fallbacks_message(self):
        """Test status message when no fallbacks active."""
        fb = FallbackMode()
        assert fb.get_status_message() is None


# === Error Formatting Tests ===

class TestErrorFormatting:
    """Test error message formatting."""

    def test_format_suzerain_error(self):
        """Test formatting SuzerainError."""
        error = SuzerainError(
            "Connection failed",
            code=ErrorCode.NETWORK_UNREACHABLE,
            suggestion="Check your internet"
        )

        formatted = format_error_for_display(error)
        assert "Connection failed" in formatted
        assert "[E6001]" in formatted

    def test_format_with_suggestion(self):
        """Test formatting includes suggestion."""
        error = SuzerainError(
            "Config missing",
            suggestion="Run setup"
        )

        formatted = format_error_for_display(error, show_suggestion=True)
        assert "Run setup" in formatted

    def test_format_generic_error(self):
        """Test formatting non-Suzerain errors."""
        error = ValueError("Bad value")
        formatted = format_error_for_display(error)
        assert "Bad value" in formatted


# === API Key Retrieval Tests ===

class TestGetApiKey:
    """Test secure API key retrieval."""

    def test_get_existing_key(self):
        """Test getting an existing key."""
        with patch.dict(os.environ, {"TEST_KEY": "abc123def456"}):
            key = get_api_key("TEST_KEY")
            assert key == "abc123def456"

    def test_missing_key_raises(self):
        """Test that missing key raises ConfigurationError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                get_api_key("NONEXISTENT_KEY")

            assert exc_info.value.code == ErrorCode.CONFIG_MISSING_KEY

    def test_key_validation(self):
        """Test key validation function."""
        def validate(key):
            return len(key) >= 10

        with patch.dict(os.environ, {"TEST_KEY": "short"}):
            with pytest.raises(ConfigurationError) as exc_info:
                get_api_key("TEST_KEY", validate_fn=validate)

            assert exc_info.value.code == ErrorCode.CONFIG_INVALID_KEY


# === Integration Tests ===

class TestErrorIntegration:
    """Test error handling in realistic scenarios."""

    def test_stt_error_offers_typing(self):
        """Test that STT errors can trigger typing fallback."""
        error = STTError(
            "Deepgram unavailable",
            code=ErrorCode.STT_NETWORK_ERROR,
            recoverable=True,
            suggestion="Check internet or type your command"
        )

        assert error.recoverable
        assert "type" in error.suggestion.lower()

    def test_wake_word_fallback_to_push_to_talk(self):
        """Test wake word error suggests push-to-talk."""
        error = WakeWordError(
            "Porcupine initialization failed",
            code=ErrorCode.WAKE_WORD_DETECTION_ERROR,
            recoverable=True,
            suggestion="Use push-to-talk mode instead"
        )

        assert error.recoverable

    def test_grimoire_error_not_recoverable(self):
        """Test that grimoire errors are not recoverable."""
        error = GrimoireError(
            "Invalid YAML syntax",
            code=ErrorCode.GRIMOIRE_INVALID_YAML,
            recoverable=False
        )

        assert not error.recoverable


# === Error Code Tests ===

class TestErrorCodes:
    """Test error code organization."""

    def test_error_code_ranges(self):
        """Test that error codes are in expected ranges."""
        # Config: 1000-1999
        assert 1000 <= ErrorCode.CONFIG_MISSING_KEY < 2000

        # STT/Audio: 2000-2999
        assert 2000 <= ErrorCode.STT_NO_API_KEY < 3000
        assert 2000 <= ErrorCode.MIC_NOT_AVAILABLE < 3000

        # Wake word: 3000-3999
        assert 3000 <= ErrorCode.WAKE_WORD_NO_PORCUPINE < 4000

        # Grimoire: 4000-4999
        assert 4000 <= ErrorCode.GRIMOIRE_NOT_FOUND < 5000

        # Execution: 5000-5999
        assert 5000 <= ErrorCode.CLAUDE_NOT_FOUND < 6000

        # Network: 6000-6999
        assert 6000 <= ErrorCode.NETWORK_UNREACHABLE < 7000

    def test_error_codes_unique(self):
        """Test that all error codes are unique."""
        codes = [code.value for code in ErrorCode]
        assert len(codes) == len(set(codes))


# === Parser Error Tests ===

class TestParserErrors:
    """Test error handling in parser module."""

    def test_missing_grimoire_file(self, tmp_path):
        """Test error when grimoire file doesn't exist."""
        from parser import load_grimoire, GRIMOIRE_PATH, reload_grimoire
        import parser

        # Save original path
        original_path = parser.GRIMOIRE_PATH

        try:
            # Point to non-existent file
            parser.GRIMOIRE_PATH = tmp_path / "nonexistent.yaml"
            parser._grimoire_cache = None

            # Parser raises FileNotFoundError (may be wrapped in GrimoireError in future)
            with pytest.raises((FileNotFoundError, GrimoireError)):
                load_grimoire()

        finally:
            # Restore
            parser.GRIMOIRE_PATH = original_path
            parser._grimoire_cache = None

    def test_invalid_yaml_grimoire(self, tmp_path):
        """Test error with invalid YAML."""
        from parser import load_grimoire
        import parser
        import yaml

        # Create invalid YAML
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("{ invalid yaml: [unclosed")

        original_path = parser.GRIMOIRE_PATH
        try:
            parser.GRIMOIRE_PATH = bad_yaml
            parser._grimoire_cache = None

            # Parser raises yaml.YAMLError (may be wrapped in GrimoireError in future)
            with pytest.raises((yaml.YAMLError, GrimoireError)):
                load_grimoire()

        finally:
            parser.GRIMOIRE_PATH = original_path
            parser._grimoire_cache = None


# === Wake Word Error Tests ===

class TestWakeWordErrors:
    """Test error handling in wake word module."""

    def test_missing_porcupine(self):
        """Test error when porcupine not installed."""
        # Mock porcupine as unavailable
        import wake_word

        original = wake_word.PORCUPINE_AVAILABLE
        try:
            wake_word.PORCUPINE_AVAILABLE = False

            # Raises ImportError (may be wrapped in WakeWordError in future)
            with pytest.raises((ImportError, WakeWordError)):
                wake_word.WakeWordDetector()

        finally:
            wake_word.PORCUPINE_AVAILABLE = original

    def test_missing_access_key(self):
        """Test error when access key not set."""
        import wake_word

        if not wake_word.PORCUPINE_AVAILABLE:
            pytest.skip("Porcupine not available")

        with patch.dict(os.environ, {}, clear=True):
            # Make sure env var is not set
            if "PICOVOICE_ACCESS_KEY" in os.environ:
                del os.environ["PICOVOICE_ACCESS_KEY"]

            # Raises ValueError (may be wrapped in WakeWordError in future)
            with pytest.raises((ValueError, WakeWordError)):
                wake_word.WakeWordDetector()

    def test_invalid_keyword(self):
        """Test error with invalid keyword."""
        import wake_word

        if not wake_word.PORCUPINE_AVAILABLE:
            pytest.skip("Porcupine not available")

        with patch.dict(os.environ, {"PICOVOICE_ACCESS_KEY": "test_key"}):
            # Raises ValueError (may be wrapped in WakeWordError in future)
            with pytest.raises((ValueError, WakeWordError)):
                wake_word.WakeWordDetector(keyword="nonexistent_keyword")


# === Network Error Tests ===

class TestNetworkErrors:
    """Test network error handling."""

    def test_network_error_creation(self):
        """Test NetworkError creation."""
        error = NetworkError("Connection refused")
        assert isinstance(error, SuzerainError)
        assert "Connection refused" in str(error)

    def test_network_error_with_code(self):
        """Test NetworkError with error code."""
        error = NetworkError(
            "Server unreachable",
            code=ErrorCode.NETWORK_UNREACHABLE
        )
        assert error.code == ErrorCode.NETWORK_UNREACHABLE

    def test_network_error_recoverable(self):
        """Test NetworkError with recoverable flag."""
        error = NetworkError(
            "Timeout",
            recoverable=True
        )
        assert error.recoverable is True


# === STT Error Tests ===

class TestSTTErrors:
    """Test speech-to-text error handling."""

    def test_stt_error_creation(self):
        """Test STTError creation."""
        error = STTError("Transcription failed")
        assert isinstance(error, SuzerainError)

    def test_stt_error_with_suggestion(self):
        """Test STTError with suggestion."""
        error = STTError(
            "API unavailable",
            suggestion="Check your internet connection"
        )
        msg = error.user_message()
        assert "API unavailable" in msg
        assert "Check your internet" in msg

    def test_stt_error_codes(self):
        """Test various STT error codes."""
        errors = [
            STTError("No API key", code=ErrorCode.STT_NO_API_KEY),
            STTError("Network error", code=ErrorCode.STT_NETWORK_ERROR),
        ]

        for error in errors:
            assert error.code is not None


# === Audio Error Tests ===

class TestAudioErrors:
    """Test audio error handling."""

    def test_audio_error_creation(self):
        """Test AudioError creation."""
        error = AudioError("Microphone not found")
        assert isinstance(error, SuzerainError)

    def test_mic_not_available_code(self):
        """Test MIC_NOT_AVAILABLE error code."""
        error = AudioError(
            "No input device",
            code=ErrorCode.MIC_NOT_AVAILABLE
        )
        assert error.code == ErrorCode.MIC_NOT_AVAILABLE


# === Execution Error Tests ===

class TestExecutionErrors:
    """Test execution error handling."""

    def test_execution_error_creation(self):
        """Test ExecutionError creation."""
        error = ExecutionError("Command failed")
        assert isinstance(error, SuzerainError)

    def test_claude_not_found_error(self):
        """Test Claude not found error."""
        error = ExecutionError(
            "claude command not found",
            code=ErrorCode.CLAUDE_NOT_FOUND,
            suggestion="Install Claude Code CLI"
        )
        assert error.code == ErrorCode.CLAUDE_NOT_FOUND

    def test_execution_timeout_error(self):
        """Test execution timeout error."""
        error = ExecutionError(
            "Command timed out after 60s",
            code=ErrorCode.CLAUDE_TIMEOUT,
            recoverable=True
        )
        assert error.recoverable is True


# === Grimoire Error Tests Extended ===

class TestGrimoireErrorsExtended:
    """Extended tests for grimoire errors."""

    def test_grimoire_not_found(self):
        """Test GRIMOIRE_NOT_FOUND error code."""
        error = GrimoireError(
            "commands.yaml not found",
            code=ErrorCode.GRIMOIRE_NOT_FOUND
        )
        assert error.code == ErrorCode.GRIMOIRE_NOT_FOUND

    def test_grimoire_invalid_yaml(self):
        """Test GRIMOIRE_INVALID_YAML error code."""
        error = GrimoireError(
            "YAML parse error",
            code=ErrorCode.GRIMOIRE_INVALID_YAML
        )
        assert error.code == ErrorCode.GRIMOIRE_INVALID_YAML


# === Retry Decorator Extended Tests ===

class TestRetryDecoratorExtended:
    """Extended tests for retry decorator."""

    def test_retry_with_custom_exceptions(self):
        """Test retry with custom exception list."""
        call_count = 0

        @retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            retryable_exceptions=(NetworkError, ConnectionError)
        )
        def custom_retry():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("Network issue")
            return "success"

        result = custom_retry()
        assert result == "success"
        assert call_count == 3

    def test_retry_immediate_non_retryable(self):
        """Test that non-retryable exceptions fail immediately."""
        call_count = 0

        @retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            retryable_exceptions=(NetworkError,)
        )
        def raises_grimoire_error():
            nonlocal call_count
            call_count += 1
            raise GrimoireError("Config error")

        with pytest.raises(GrimoireError):
            raises_grimoire_error()

        assert call_count == 1  # No retries


# === Fallback Mode Extended Tests ===

class TestFallbackModeExtended:
    """Extended tests for fallback mode."""

    def test_fallback_mode_multiple_reasons(self):
        """Test fallback mode with multiple active fallbacks."""
        fb = FallbackMode()
        fb.activate("stt", "API down")
        fb.activate("wake_word", "Porcupine failed")
        fb.activate("audio", "Mic unavailable")

        active = fb.get_all_active()
        assert len(active) == 3

    def test_fallback_mode_deactivate_specific(self):
        """Test deactivating specific fallback."""
        fb = FallbackMode()
        fb.activate("stt", "API down")
        fb.activate("wake_word", "Porcupine failed")

        fb.deactivate("stt")

        assert not fb.is_active("stt")
        assert fb.is_active("wake_word")

    def test_fallback_mode_reactivate(self):
        """Test reactivating a fallback with new reason."""
        fb = FallbackMode()
        fb.activate("stt", "First reason")
        fb.activate("stt", "Second reason")

        assert fb.get_reason("stt") == "Second reason"


# === Error Display Extended Tests ===

class TestErrorDisplayExtended:
    """Extended tests for error display formatting."""

    def test_format_nested_error(self):
        """Test formatting error with nested cause."""
        inner = ConnectionError("Connection refused")
        outer = NetworkError(
            "Failed to connect to API",
            details=str(inner)
        )

        formatted = format_error_for_display(outer)
        assert "Failed to connect" in formatted

    def test_format_error_without_suggestion(self):
        """Test formatting error without suggestion."""
        error = SuzerainError("Simple error")

        formatted = format_error_for_display(error, show_suggestion=True)
        assert "Simple error" in formatted

    def test_format_error_with_all_fields(self):
        """Test formatting error with all fields."""
        error = SuzerainError(
            "Complex error",
            code=ErrorCode.CONFIG_MISSING_KEY,
            suggestion="Check configuration",
            details="Full stack trace here"
        )

        formatted = format_error_for_display(error, show_suggestion=True)
        assert "Complex error" in formatted
        assert "[E" in formatted  # Error code


# === Redaction Extended Tests ===

class TestRedactionExtended:
    """Extended tests for sensitive data redaction."""

    def test_redact_multiple_occurrences(self):
        """Test redacting key that appears multiple times."""
        api_key = "sk-1234567890abcdef1234567890abcdef"
        text = f"Key: {api_key}, again: {api_key}"

        result = redact_sensitive(text, api_key)

        assert api_key not in result
        assert result.count("[REDACTED") >= 2

    def test_redact_preserves_surrounding_text(self):
        """Test that surrounding text is preserved."""
        api_key = "sk-1234567890abcdef1234567890abcdef"
        text = f"Before {api_key} after"

        result = redact_sensitive(text, api_key)

        assert "Before" in result
        assert "after" in result

    def test_redact_json_with_key(self):
        """Test redacting API key in JSON."""
        api_key = "sk-1234567890abcdef1234567890abcdef"
        text = f'{{"api_key": "{api_key}"}}'

        result = redact_sensitive(text, api_key)

        assert api_key not in result


# === API Key Retrieval Extended Tests ===

class TestGetApiKeyExtended:
    """Extended tests for API key retrieval."""

    def test_get_api_key_with_whitespace(self):
        """Test that whitespace in key is handled."""
        with patch.dict(os.environ, {"TEST_KEY": "  key_with_spaces  "}):
            key = get_api_key("TEST_KEY")
            # Implementation may strip or preserve whitespace
            assert "key_with_spaces" in key

    def test_get_api_key_with_validation_pass(self):
        """Test key retrieval with passing validation."""
        def validate(key):
            return key.startswith("valid_")

        with patch.dict(os.environ, {"TEST_KEY": "valid_key_here"}):
            key = get_api_key("TEST_KEY", validate_fn=validate)
            assert key == "valid_key_here"

    def test_get_api_key_missing_with_suggestion(self):
        """Test missing key error includes helpful message."""
        with patch.dict(os.environ, {}, clear=True):
            try:
                get_api_key("MISSING_API_KEY")
                pytest.fail("Should have raised ConfigurationError")
            except ConfigurationError as e:
                assert "MISSING_API_KEY" in str(e) or e.code is not None


# === Error Code Validation Tests ===

class TestErrorCodeValidation:
    """Test error code values and ranges."""

    def test_all_error_codes_have_values(self):
        """Test that all error codes have numeric values."""
        for code in ErrorCode:
            assert isinstance(code.value, int)

    def test_error_code_ranges_valid(self):
        """Test error codes fall within expected ranges."""
        for code in ErrorCode:
            assert code.value >= 1000
            assert code.value < 10000

    def test_error_code_string_representation(self):
        """Test error codes have proper string representation."""
        error = SuzerainError(
            "Test error",
            code=ErrorCode.CONFIG_MISSING_KEY
        )

        error_str = str(error)
        # Should include error code in format like [E1001]
        assert "[E" in error_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
