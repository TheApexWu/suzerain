"""
Suzerain Error Handling - Custom exceptions and error codes.

"He never sleeps, the judge. He is dancing, dancing."

This module provides:
- Custom exception hierarchy for programmatic error handling
- Error codes for categorization
- User-friendly error messages that never leak sensitive data
- Retry utilities with exponential backoff
"""

import functools
import logging
import os
import re
import time
from enum import IntEnum
from typing import Callable, Optional, TypeVar

# Configure logging
logger = logging.getLogger(__name__)


# === Error Codes ===

class ErrorCode(IntEnum):
    """
    Error codes for programmatic handling.

    Ranges:
    - 1000-1999: Configuration errors
    - 2000-2999: STT/Audio errors
    - 3000-3999: Wake word errors
    - 4000-4999: Parser/Grimoire errors
    - 5000-5999: Execution errors
    - 6000-6999: Network errors
    """
    # Configuration (1000-1999)
    CONFIG_MISSING_KEY = 1001
    CONFIG_INVALID_KEY = 1002
    CONFIG_MISSING_FILE = 1003
    CONFIG_INVALID_FORMAT = 1004

    # STT/Audio (2000-2999)
    STT_NO_API_KEY = 2001
    STT_INVALID_API_KEY = 2002
    STT_NETWORK_ERROR = 2003
    STT_TIMEOUT = 2004
    STT_TRANSCRIPTION_FAILED = 2005
    STT_NO_AUDIO = 2006
    MIC_NOT_AVAILABLE = 2010
    MIC_PERMISSION_DENIED = 2011
    MIC_DEVICE_ERROR = 2012

    # Wake Word (3000-3999)
    WAKE_WORD_NO_PORCUPINE = 3001
    WAKE_WORD_NO_PYAUDIO = 3002
    WAKE_WORD_NO_ACCESS_KEY = 3003
    WAKE_WORD_INVALID_KEYWORD = 3004
    WAKE_WORD_DETECTION_ERROR = 3005

    # Parser/Grimoire (4000-4999)
    GRIMOIRE_NOT_FOUND = 4001
    GRIMOIRE_INVALID_YAML = 4002
    GRIMOIRE_MISSING_FIELD = 4003
    GRIMOIRE_NO_MATCH = 4004

    # Execution (5000-5999)
    CLAUDE_NOT_FOUND = 5001
    CLAUDE_TIMEOUT = 5002
    CLAUDE_EXECUTION_FAILED = 5003
    CLAUDE_ABORTED = 5004

    # Network (6000-6999)
    NETWORK_UNREACHABLE = 6001
    NETWORK_TIMEOUT = 6002
    NETWORK_SSL_ERROR = 6003
    NETWORK_RATE_LIMITED = 6004


# === Exception Hierarchy ===

class SuzerainError(Exception):
    """
    Base exception for all Suzerain errors.

    All custom exceptions inherit from this, allowing:
        try:
            ...
        except SuzerainError as e:
            # Handle any Suzerain-specific error

    Attributes:
        code: ErrorCode for programmatic handling
        message: User-friendly message (safe to display)
        details: Technical details (may be redacted for logging)
        recoverable: Whether the error can potentially be recovered from
        suggestion: User-facing suggestion for resolution
    """

    def __init__(
        self,
        message: str,
        code: ErrorCode = None,
        details: str = None,
        recoverable: bool = False,
        suggestion: str = None
    ):
        self.code = code
        self.message = message
        self.details = details
        self.recoverable = recoverable
        self.suggestion = suggestion
        super().__init__(self.message)

    def __str__(self) -> str:
        parts = [self.message]
        if self.code:
            parts.insert(0, f"[E{self.code:04d}]")
        return " ".join(parts)

    def user_message(self) -> str:
        """Get a user-friendly error message with suggestion if available."""
        msg = self.message
        if self.suggestion:
            msg += f"\n  Suggestion: {self.suggestion}"
        return msg

    def log_message(self) -> str:
        """Get a message suitable for logging (includes details if present)."""
        msg = str(self)
        if self.details:
            msg += f" | Details: {self.details}"
        return msg


class ConfigurationError(SuzerainError):
    """Configuration-related errors (missing keys, invalid files, etc.)."""
    pass


class STTError(SuzerainError):
    """Speech-to-text errors (Deepgram, transcription failures)."""
    pass


class AudioError(SuzerainError):
    """Audio hardware errors (microphone, playback)."""
    pass


class WakeWordError(SuzerainError):
    """Wake word detection errors (Porcupine, pyaudio)."""
    pass


class GrimoireError(SuzerainError):
    """Grimoire parsing and matching errors."""
    pass


class ExecutionError(SuzerainError):
    """Claude Code execution errors."""
    pass


class NetworkError(SuzerainError):
    """Network-related errors (timeouts, connectivity)."""
    pass


# === Redaction Utilities ===

# Patterns that should be redacted from error messages
_SENSITIVE_PATTERNS = [
    # API keys (generic patterns)
    (r'([a-zA-Z0-9]{32,})', '[REDACTED_KEY]'),
    # Bearer tokens
    (r'Bearer\s+[a-zA-Z0-9\-_]+', 'Bearer [REDACTED]'),
    # Authorization headers
    (r'Token\s+[a-zA-Z0-9\-_]+', 'Token [REDACTED]'),
    # URLs with credentials
    (r'://[^@]+@', '://[REDACTED]@'),
]


def redact_sensitive(text: str, *additional_secrets: str) -> str:
    """
    Redact sensitive data from text.

    Args:
        text: The text to redact
        *additional_secrets: Additional specific strings to redact

    Returns:
        Text with sensitive data replaced with [REDACTED]
    """
    if not text:
        return text

    result = text

    # Redact specific secrets first
    for secret in additional_secrets:
        if secret and len(secret) > 4:
            result = result.replace(secret, '[REDACTED]')
            # Also redact partial matches (first 8 chars)
            if len(secret) > 8:
                result = result.replace(secret[:8], '[REDACTED]')

    # Apply pattern-based redaction
    for pattern, replacement in _SENSITIVE_PATTERNS:
        result = re.sub(pattern, replacement, result)

    return result


def get_api_key(key_name: str, validate_fn: Callable[[str], bool] = None) -> str:
    """
    Safely retrieve and validate an API key from environment.

    Args:
        key_name: Environment variable name
        validate_fn: Optional validation function

    Returns:
        The API key value

    Raises:
        ConfigurationError: If key is missing or invalid
    """
    value = os.environ.get(key_name)

    if not value:
        raise ConfigurationError(
            f"Required environment variable {key_name} is not set",
            code=ErrorCode.CONFIG_MISSING_KEY,
            recoverable=True,
            suggestion=f"Set {key_name} in your environment or .env file"
        )

    if validate_fn and not validate_fn(value):
        raise ConfigurationError(
            f"Environment variable {key_name} appears to be invalid",
            code=ErrorCode.CONFIG_INVALID_KEY,
            recoverable=True,
            suggestion=f"Check that {key_name} contains a valid API key"
        )

    return value


# === Retry Logic ===

T = TypeVar('T')


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (NetworkError, TimeoutError, ConnectionError),
    on_retry: Callable[[Exception, int, float], None] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retry with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential calculation
        retryable_exceptions: Tuple of exception types to retry on
        on_retry: Callback called before each retry (exception, attempt, delay)

    Example:
        @retry_with_backoff(max_retries=3)
        def call_api():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        # Final attempt failed
                        break

                    # Calculate delay with jitter
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    # Add some jitter (10-20% of delay)
                    import random
                    jitter = delay * random.uniform(0.1, 0.2)
                    actual_delay = delay + jitter

                    if on_retry:
                        on_retry(e, attempt + 1, actual_delay)

                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {actual_delay:.1f}s: {e}"
                    )

                    time.sleep(actual_delay)

            # All retries exhausted
            raise last_exception

        return wrapper
    return decorator


class RetryContext:
    """
    Context manager for retry logic with state tracking.

    Example:
        with RetryContext(max_retries=3) as retry:
            while retry.should_continue():
                try:
                    result = risky_operation()
                    break
                except NetworkError:
                    retry.record_failure()
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.attempt = 0
        self.last_exception: Optional[Exception] = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def should_continue(self) -> bool:
        """Check if we should continue trying."""
        return self.attempt <= self.max_retries

    def record_failure(self, exception: Exception = None):
        """Record a failure and sleep before next attempt."""
        self.last_exception = exception
        self.attempt += 1

        if self.attempt <= self.max_retries:
            delay = min(
                self.base_delay * (2 ** (self.attempt - 1)),
                self.max_delay
            )
            time.sleep(delay)

    def success(self):
        """Mark the operation as successful."""
        self.attempt = self.max_retries + 1  # Stop the loop


# === Error Formatting ===

def format_error_for_display(
    error: Exception,
    show_code: bool = True,
    show_suggestion: bool = True
) -> str:
    """
    Format an error for user display.

    Args:
        error: The exception to format
        show_code: Include error code if available
        show_suggestion: Include suggestion if available

    Returns:
        Formatted error string
    """
    if isinstance(error, SuzerainError):
        parts = []

        if show_code and error.code:
            parts.append(f"[E{error.code:04d}]")

        parts.append(error.message)

        if show_suggestion and error.suggestion:
            parts.append(f"\n  Tip: {error.suggestion}")

        return " ".join(parts)

    # For non-Suzerain errors, just return the string representation
    return str(error)


# === Fallback Mode Tracking ===

class FallbackMode:
    """
    Track graceful degradation state.

    When components fail, this tracks what fallbacks are active
    so the UI can inform the user appropriately.
    """

    def __init__(self):
        self._modes = {}

    def activate(self, component: str, reason: str):
        """Activate fallback for a component."""
        self._modes[component] = reason
        logger.info(f"Fallback activated for {component}: {reason}")

    def deactivate(self, component: str):
        """Deactivate fallback for a component."""
        if component in self._modes:
            del self._modes[component]
            logger.info(f"Fallback deactivated for {component}")

    def is_active(self, component: str) -> bool:
        """Check if fallback is active for a component."""
        return component in self._modes

    def get_reason(self, component: str) -> Optional[str]:
        """Get the reason for a fallback."""
        return self._modes.get(component)

    def get_all_active(self) -> dict:
        """Get all active fallbacks."""
        return dict(self._modes)

    def get_status_message(self) -> Optional[str]:
        """Get a user-friendly status message about active fallbacks."""
        if not self._modes:
            return None

        messages = []
        for component, reason in self._modes.items():
            if component == "stt":
                messages.append("Voice recognition unavailable - type commands instead")
            elif component == "wake_word":
                messages.append("Wake word disabled - using push-to-talk")
            elif component == "mic":
                messages.append("Microphone unavailable - text input only")

        return "; ".join(messages) if messages else None


# Global fallback tracker
fallback = FallbackMode()
