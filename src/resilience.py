"""
Suzerain Resilience Features - STT retry, Claude retry, health checks, graceful degradation.

"He never sleeps, the judge. He is dancing, dancing."

This module provides:
- STT retry with exponential backoff (max 3 attempts, no retry on auth errors)
- Claude Code retry for network-related exit codes
- Graceful degradation with fallback to typing mode
- Health check command for system diagnostics
- Connection pooling wrapper for Deepgram API
"""

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from typing import Optional, Tuple

from utils import (
    retry,
    get_pooled_client,
    close_connection_pool,
    RETRYABLE_EXCEPTIONS,
    RETRYABLE_HTTP_CODES,
    is_auth_error,
)


# === Graceful Degradation State ===

# Track if STT has failed and we're in fallback typing mode
STT_FALLBACK_MODE = False
STT_CONSECUTIVE_FAILURES = 0
MAX_STT_FAILURES_BEFORE_FALLBACK = 3


# === Claude Code Exit Codes ===

# Exit codes that indicate network/transient issues worth retrying
CLAUDE_RETRYABLE_EXIT_CODES = {
    1,    # Generic error (may include network issues)
    130,  # SIGINT (Ctrl+C during network operation)
}

# Exit codes that should NOT be retried
CLAUDE_NON_RETRYABLE_EXIT_CODES = {
    2,    # Invalid arguments
    126,  # Permission denied
    127,  # Command not found
}


# === STT Retry Logic ===

def _on_stt_retry(exception: Exception, attempt: int, delay: float):
    """Callback for STT retry attempts."""
    print(f"[STT Retry {attempt}] Retrying after {delay:.1f}s due to: {type(exception).__name__}")


@retry(
    max_attempts=3,
    backoff="exponential",
    base_delay=1.0,
    max_delay=10.0,
    retry_on=RETRYABLE_EXCEPTIONS,
    retry_on_http_codes=RETRYABLE_HTTP_CODES,
    on_retry=_on_stt_retry,
)
def transcribe_audio_with_retry(
    audio_data: bytes,
    api_key: str,
    url: str,
) -> str:
    """
    Send audio to Deepgram for transcription with retry logic.

    Uses exponential backoff, retries up to 3 times on transient failures.
    Does NOT retry on auth errors (4xx).

    Args:
        audio_data: WAV audio data
        api_key: Deepgram API key
        url: Deepgram API URL with query parameters

    Returns:
        Transcription text (empty string on failure)

    Raises:
        urllib.error.HTTPError: On non-retryable HTTP errors (4xx)
    """
    # Use connection pooling for better performance
    client = get_pooled_client()

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "audio/wav",
    }

    status, resp_headers, body = client.request(
        "POST",
        url,
        body=audio_data,
        headers=headers,
    )

    result = json.loads(body)
    transcript = result["results"]["channels"][0]["alternatives"][0]["transcript"]
    return transcript


def transcribe_with_fallback(
    audio_data: bytes,
    api_key: str,
    url: str,
) -> Tuple[str, bool]:
    """
    Transcribe audio with retry logic and graceful degradation.

    If transcription fails after all retries, offers to fall back to typing mode.

    Args:
        audio_data: WAV audio data
        api_key: Deepgram API key
        url: Deepgram API URL

    Returns:
        Tuple of (transcript, should_fallback_to_typing)
        - transcript: The transcribed text (empty if failed)
        - should_fallback_to_typing: True if STT is unavailable and typing mode should be offered
    """
    global STT_CONSECUTIVE_FAILURES, STT_FALLBACK_MODE

    try:
        transcript = transcribe_audio_with_retry(audio_data, api_key, url)
        # Reset failure counter on success
        STT_CONSECUTIVE_FAILURES = 0
        STT_FALLBACK_MODE = False
        return transcript, False

    except urllib.error.HTTPError as e:
        if is_auth_error(e):
            # Auth errors - don't retry, don't fall back (user needs to fix API key)
            print(f"[STT Error] Authentication failed (HTTP {e.code}). Check your DEEPGRAM_API_KEY.")
            return "", False
        else:
            # Server error after all retries
            STT_CONSECUTIVE_FAILURES += 1

    except Exception as e:
        # Network or other error after all retries
        STT_CONSECUTIVE_FAILURES += 1
        print(f"[STT Error] Failed after retries: {type(e).__name__}")

    # Check if we should offer fallback to typing mode
    if STT_CONSECUTIVE_FAILURES >= MAX_STT_FAILURES_BEFORE_FALLBACK:
        STT_FALLBACK_MODE = True
        return "", True

    return "", False


def prompt_for_typing_fallback() -> Optional[str]:
    """
    Prompt user to fall back to typing mode when STT is unavailable.

    Returns:
        User input text, or None if user cancels (Ctrl+C)
    """
    print("STT unavailable. Type your command or Ctrl+C to exit: ", end="", flush=True)
    try:
        return input().strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


# === Claude Code Retry Logic ===

def run_claude_with_retry(
    cmd: list,
    max_retries: int = 1,
) -> Tuple[subprocess.Popen, int]:
    """
    Run Claude Code CLI with retry logic for network issues.

    Args:
        cmd: Command list to execute
        max_retries: Maximum number of retry attempts (default: 1)

    Returns:
        Tuple of (process, exit_code)
    """
    last_process = None

    for attempt in range(max_retries + 1):
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        # Stream output
        for line in process.stdout:
            yield line

        process.wait()
        last_process = process

        # Check if we should retry
        if process.returncode == 0:
            # Success
            break
        elif process.returncode in CLAUDE_NON_RETRYABLE_EXIT_CODES:
            # Don't retry on these
            break
        elif process.returncode in CLAUDE_RETRYABLE_EXIT_CODES and attempt < max_retries:
            # Retry
            print(f"[Claude Retry] Attempt {attempt + 1} failed with exit code {process.returncode}, retrying...")
            time.sleep(1.0)  # Brief delay before retry
        else:
            # Max retries reached or unknown exit code
            break

    return last_process


# === Health Check ===

def check_deepgram_api() -> Tuple[bool, str]:
    """
    Check if Deepgram API is reachable with valid credentials.

    Returns:
        Tuple of (success, message)
    """
    api_key = os.environ.get("DEEPGRAM_API_KEY")

    if not api_key:
        return False, "DEEPGRAM_API_KEY not set"

    if len(api_key) < 32:
        return False, "DEEPGRAM_API_KEY appears too short"

    # Try to reach the API with a minimal request
    try:
        # Use the projects endpoint as a lightweight auth check
        url = "https://api.deepgram.com/v1/projects"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Token {api_key}"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return True, "Deepgram API reachable and authenticated"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Deepgram API key invalid (401 Unauthorized)"
        elif e.code == 403:
            return False, "Deepgram API key forbidden (403)"
        else:
            return False, f"Deepgram API error: HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, f"Deepgram API unreachable: {e.reason}"
    except Exception as e:
        return False, f"Deepgram check failed: {e}"

    return False, "Unknown error"


def check_claude_cli() -> Tuple[bool, str]:
    """
    Check if Claude Code CLI is available and working.

    Returns:
        Tuple of (success, message)
    """
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            version = result.stdout.strip() or result.stderr.strip()
            return True, f"Claude CLI available: {version}"
        else:
            return False, f"Claude CLI returned error code {result.returncode}"
    except FileNotFoundError:
        return False, "Claude CLI not found. Is Claude Code installed?"
    except subprocess.TimeoutExpired:
        return False, "Claude CLI timed out"
    except Exception as e:
        return False, f"Claude CLI check failed: {e}"


def check_microphone() -> Tuple[bool, str]:
    """
    Check if microphone is accessible.

    Returns:
        Tuple of (success, message)
    """
    try:
        import pyaudio
        pa = pyaudio.PyAudio()

        # Try to get default input device info
        try:
            info = pa.get_default_input_device_info()
            device_name = info.get('name', 'Unknown')
            pa.terminate()
            return True, f"Microphone accessible: {device_name}"
        except IOError as e:
            pa.terminate()
            return False, f"No microphone available: {e}"

    except ImportError:
        return False, "pyaudio not installed (pip install pyaudio)"
    except Exception as e:
        return False, f"Microphone check failed: {e}"


def check_grimoire() -> Tuple[bool, str]:
    """
    Check if grimoire is valid and loadable.

    Returns:
        Tuple of (success, message)
    """
    try:
        # Import parser functions lazily to avoid circular imports
        import sys
        from pathlib import Path
        # Ensure src is in path
        src_path = Path(__file__).parent
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from parser import load_grimoire, validate_grimoire, list_commands, list_modifiers

        # Try to load grimoire
        grimoire = load_grimoire()
        if not grimoire:
            return False, "Grimoire is empty"

        # Validate structure
        issues = validate_grimoire()
        if issues:
            return False, f"Grimoire has {len(issues)} validation issue(s)"

        # Count commands
        commands = list_commands()
        modifiers = list_modifiers()
        return True, f"Grimoire valid: {len(commands)} commands, {len(modifiers)} modifiers"

    except FileNotFoundError:
        return False, "Grimoire file not found (grimoire/commands.yaml)"
    except Exception as e:
        return False, f"Grimoire check failed: {e}"


def run_health_check() -> int:
    """
    Run all health checks and report status.

    Returns:
        Exit code: 0 if all pass, 1 if any fail
    """
    print("=" * 50)
    print("SUZERAIN HEALTH CHECK")
    print("=" * 50)
    print()

    checks = [
        ("Deepgram API", check_deepgram_api),
        ("Claude CLI", check_claude_cli),
        ("Microphone", check_microphone),
        ("Grimoire", check_grimoire),
    ]

    all_passed = True

    for name, check_fn in checks:
        success, message = check_fn()
        status = "PASS" if success else "FAIL"
        symbol = "[+]" if success else "[-]"

        print(f"  {symbol} {name}: {status}")
        print(f"      {message}")
        print()

        if not success:
            all_passed = False

    print("=" * 50)
    if all_passed:
        print("All checks passed.")
        return 0
    else:
        print("Some checks failed. See details above.")
        return 1


# === Cleanup ===

def cleanup():
    """Clean up resources (connection pool, etc.)."""
    close_connection_pool()
