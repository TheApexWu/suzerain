"""
Suzerain - Voice-activated Claude Code with literary macros.

"Whatever exists without my knowledge exists without my consent."

Usage:
    python src/main.py              # Run with push-to-talk
    python src/main.py --test       # Test mode (type phrases)
    python src/main.py --list       # List all grimoire commands
    python src/main.py --validate   # Validate grimoire structure
    python src/main.py --timing     # Show detailed latency breakdown
    python src/main.py --sandbox    # Dry run mode (no execution)
    python src/main.py --warm       # Pre-warm Claude connection on startup
    python src/main.py --no-fallback  # Disable plain English fallback
"""

import argparse
import subprocess
import sys
import os
import json
import time
import threading
import concurrent.futures
import urllib.error
import urllib.request
from pathlib import Path

from parser import (
    match_top_n,
    extract_modifiers,
    expand_command,
    load_grimoire,
    list_commands,
    list_modifiers,
    validate_grimoire,
    get_command_info
)
from history import (
    log_command as log_history,
    get_last_n,
    get_last_successful,
    get_time_since_last,
    display_history
)
from metrics import get_metrics_manager
from cache import warmup_all, verify_grimoire_cache
from errors import (
    ErrorCode,
    redact_sensitive
)


# === Terminal Colors ===

class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Background
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"

    @classmethod
    def disable(cls):
        """Disable colors (for non-TTY output)."""
        for attr in dir(cls):
            if not attr.startswith('_') and attr.isupper():
                setattr(cls, attr, "")


# Disable colors if not a TTY
if not sys.stdout.isatty():
    Colors.disable()

# Global sandbox mode flag
SANDBOX_MODE = False

# Global timing mode flag
TIMING_MODE = False

# Global fallback mode flag (True = allow plain English fallback when no grimoire match)
FALLBACK_ENABLED = True

# Global retry mode flag (enabled by default)
RETRY_ENABLED = True

# Global warm mode flag
WARM_MODE = False

# Claude execution timeout settings
CLAUDE_TIMEOUT_SECONDS = 300  # 5 minutes default
CLAUDE_WARNING_SECONDS = 30   # Show warning after 30s of no output


# === Timing Utilities ===

class Timer:
    """Simple timer for latency tracking."""

    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.end_time = None

    def start(self):
        self.start_time = time.perf_counter()
        return self

    def stop(self):
        self.end_time = time.perf_counter()
        return self

    @property
    def elapsed_ms(self) -> float:
        if self.start_time is None:
            return 0.0
        end = self.end_time if self.end_time else time.perf_counter()
        return (end - self.start_time) * 1000


class TimingReport:
    """Collect and display timing breakdown."""

    def __init__(self):
        self.timers = {}

    def timer(self, name: str) -> Timer:
        t = Timer(name)
        self.timers[name] = t
        return t

    def get_timer(self, name: str) -> Timer:
        """Get an existing timer by name."""
        return self.timers.get(name)

    def display(self, force: bool = False):
        """Display timing breakdown. Only shows if TIMING_MODE or force=True."""
        if not TIMING_MODE and not force:
            return

        print(f"\n{Colors.CYAN}{'=' * 40}{Colors.RESET}")
        print(f"{Colors.CYAN}LATENCY BREAKDOWN{Colors.RESET}")
        print(f"{Colors.CYAN}{'=' * 40}{Colors.RESET}")

        total = 0.0
        for name, timer in self.timers.items():
            ms = timer.elapsed_ms
            total += ms
            bar_len = min(int(ms / 50), 40)  # Scale: 50ms per char, max 40
            bar = "█" * bar_len
            print(f"  {name:15} {ms:7.1f}ms {Colors.DIM}{bar}{Colors.RESET}")

        print(f"{Colors.CYAN}{'-' * 40}{Colors.RESET}")
        print(f"  {'TOTAL':15} {total:7.1f}ms")
        print()

    def display_subtle(self):
        """Display a subtle one-line timing summary (always shown)."""
        total = sum(t.elapsed_ms for t in self.timers.values())
        if total > 0:
            print(f"{Colors.DIM}[{total:.1f}ms]{Colors.RESET}", end=" ")

    def record_to_metrics(self):
        """Record timing data to metrics for historical tracking."""
        try:
            manager = get_metrics_manager()
            stt_timer = self.get_timer("STT")
            parse_timer = self.get_timer("Parse")
            claude_timer = self.get_timer("Claude Exec")

            stt_ms = stt_timer.elapsed_ms if stt_timer else 0
            parse_ms = parse_timer.elapsed_ms if parse_timer else 0
            claude_ms = claude_timer.elapsed_ms if claude_timer else 0

            # Only record if we have actual data
            if stt_ms > 0 or parse_ms > 0 or claude_ms > 0:
                if stt_ms > 0:
                    manager._aggregate.latency_history.add_stt(stt_ms)
                if parse_ms > 0:
                    manager._aggregate.latency_history.add_parse(parse_ms)
                if claude_ms > 0:
                    manager._aggregate.latency_history.add_claude(claude_ms)
                manager._save_aggregate()
        except Exception:
            pass  # Don't let metrics errors affect main flow


# === Audio Dependencies (optional) ===
try:
    import pyaudio
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

# simpleaudio disabled - crashes on macOS Apple Silicon
# TODO: Replace with alternative (e.g., sounddevice, pygame.mixer)
AUDIO_FEEDBACK = False


# === Spinner for Waiting ===

class Spinner:
    """Animated dots while waiting for response."""

    FRAMES = [".", "..", "...", "....", "....."]

    def __init__(self, message: str = "Waiting"):
        self.message = message
        self.running = False
        self.thread = None
        self.frame_idx = 0

    def _animate(self):
        while self.running:
            frame = self.FRAMES[self.frame_idx % len(self.FRAMES)]
            sys.stdout.write(f"\r{Colors.BLUE}{self.message}{frame}{Colors.RESET}     ")
            sys.stdout.flush()
            self.frame_idx += 1
            time.sleep(0.3)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()

    def stop(self, clear: bool = True):
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.5)
        if clear:
            sys.stdout.write("\r" + " " * (len(self.message) + 20) + "\r")
            sys.stdout.flush()


# === Streaming Output Handler ===

class StreamingOutputHandler:
    """
    Handles Claude Code's JSON stream with enhanced display.

    Features:
    - Character-by-character streaming for responsive feel
    - Distinct display for thinking vs output
    - Tool usage indicators with context
    - Execution summary with timing and tool count
    """

    def __init__(self):
        self.tools_used = []
        self.is_thinking = False
        self.last_was_text = False
        self.char_delay = 0.003  # 3ms between chars for streaming effect
        self.first_output_received = False
        self.spinner = None
        self.total_chars = 0
        self.conversation_id = None

    def start_waiting(self):
        """Start spinner while waiting for first response."""
        self.spinner = Spinner("Awaiting response")
        self.spinner.start()

    def stop_waiting(self):
        """Stop the waiting spinner."""
        if self.spinner:
            self.spinner.stop()
            self.spinner = None

    def _stream_text(self, text: str, color: str = ""):
        """Stream text character-by-character for responsive feel."""
        if not self.first_output_received:
            self.stop_waiting()
            self.first_output_received = True

        for char in text:
            if color:
                sys.stdout.write(f"{color}{char}{Colors.RESET}")
            else:
                sys.stdout.write(char)
            sys.stdout.flush()
            self.total_chars += 1
            # Small delay for streaming effect, skip for whitespace
            if char not in ' \n\t' and self.char_delay > 0:
                time.sleep(self.char_delay)
        self.last_was_text = True

    def handle_assistant(self, data: dict):
        """Handle assistant message type - extract and display content."""
        if not self.first_output_received:
            self.stop_waiting()
            self.first_output_received = True

        message = data.get("message", {})
        content = message.get("content", [])

        for block in content:
            block_type = block.get("type", "")

            if block_type == "thinking":
                self.is_thinking = True
                thinking_text = block.get("thinking", "")
                if thinking_text:
                    print(f"\n{Colors.DIM}[Thinking]{Colors.RESET}")
                    self._stream_text(thinking_text, Colors.DIM)
                    print()
                self.is_thinking = False

            elif block_type == "text":
                text = block.get("text", "")
                if text:
                    self._stream_text(text)

            elif block_type == "tool_use":
                tool_name = block.get("name", "unknown")
                tool_input = block.get("input", {})
                self._show_tool_use(tool_name, tool_input)

    def handle_content_delta(self, data: dict):
        """Handle streaming content deltas."""
        if not self.first_output_received:
            self.stop_waiting()
            self.first_output_received = True

        delta = data.get("delta", {})
        delta_type = delta.get("type", "")

        if delta_type == "text_delta":
            text = delta.get("text", "")
            if text:
                self._stream_text(text)

        elif delta_type == "thinking_delta":
            thinking = delta.get("thinking", "")
            if thinking:
                if not self.is_thinking:
                    self.is_thinking = True
                    print(f"\n{Colors.DIM}[Thinking...]{Colors.RESET}")
                self._stream_text(thinking, Colors.DIM)

    def _show_tool_use(self, tool_name: str, tool_input: dict):
        """Display tool usage with icon and details."""
        self.tools_used.append(tool_name)

        detail = ""
        if tool_name in ("Read", "read_file"):
            file_path = tool_input.get("file_path", tool_input.get("path", ""))
            if file_path:
                detail = Path(file_path).name
        elif tool_name in ("Write", "write_file"):
            file_path = tool_input.get("file_path", tool_input.get("path", ""))
            if file_path:
                detail = Path(file_path).name
        elif tool_name in ("Edit", "edit_file"):
            file_path = tool_input.get("file_path", tool_input.get("path", ""))
            if file_path:
                detail = Path(file_path).name
        elif tool_name in ("Bash", "bash", "execute_command"):
            command = tool_input.get("command", "")
            if command:
                detail = command[:30] + ("..." if len(command) > 30 else "")
        elif tool_name in ("Grep", "grep", "search"):
            pattern = tool_input.get("pattern", "")
            if pattern:
                detail = f'"{pattern}"'
        elif tool_name in ("Glob", "glob", "list_files"):
            pattern = tool_input.get("pattern", "")
            if pattern:
                detail = pattern

        if detail:
            print(f"\n{Colors.CYAN}[Tool] {tool_name}: {detail}{Colors.RESET}", flush=True)
        else:
            print(f"\n{Colors.CYAN}[Tool] {tool_name}{Colors.RESET}", flush=True)

        self.last_was_text = False

    def handle_tool_use(self, data: dict):
        """Handle tool_use message type."""
        if not self.first_output_received:
            self.stop_waiting()
            self.first_output_received = True

        tool_name = data.get("name", "unknown")
        tool_input = data.get("input", {})
        self._show_tool_use(tool_name, tool_input)

    def handle_result(self, data: dict):
        """Handle result message type."""
        if not self.first_output_received:
            self.stop_waiting()
            self.first_output_received = True

        result_text = data.get("result", "")
        if result_text and not result_text.strip().startswith('{'):
            if self.last_was_text:
                print()
            print(f"\n{Colors.GREEN}{result_text}{Colors.RESET}", flush=True)
            self.last_was_text = False

        if data.get("session_id"):
            self.conversation_id = data.get("session_id")
        elif data.get("conversation_id"):
            self.conversation_id = data.get("conversation_id")

    def handle_system(self, data: dict):
        """Handle system messages - look for session info."""
        if data.get("session_id"):
            self.conversation_id = data.get("session_id")
        elif data.get("conversation_id"):
            self.conversation_id = data.get("conversation_id")

    def handle_error(self, data: dict):
        """Handle error messages."""
        self.stop_waiting()
        error = data.get("error", {})
        message = error.get("message", str(data))
        print(f"\n{Colors.RED}[Error] {message}{Colors.RESET}", flush=True)

    def get_summary(self, elapsed_seconds: float, success: bool) -> str:
        """Generate execution summary."""
        status = "Complete" if success else "Failed"
        status_color = Colors.GREEN if success else Colors.RED
        status_symbol = "+" if success else "x"

        tools_count = len(self.tools_used)
        tools_str = f", {tools_count} tool{'s' if tools_count != 1 else ''} used" if tools_count > 0 else ""

        return f"{status_color}{status_symbol} {status} ({elapsed_seconds:.1f}s{tools_str}){Colors.RESET}"


# === Claude Warmup ===

def warm_claude_connection() -> dict:
    """
    Pre-warm Claude connection by sending a minimal prompt.

    This forces Claude Code to:
    1. Start the Node.js process
    2. Authenticate with Anthropic
    3. Establish API connection

    Returns dict with warmup status and timing.
    """
    start = time.perf_counter()

    try:
        # Minimal prompt that executes quickly
        process = subprocess.run(
            ["claude", "-p", "Say 'ready' and nothing else.", "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=30  # 30s timeout for warmup
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        success = process.returncode == 0

        # Record warmup time for predictions
        try:
            manager = get_metrics_manager()
            manager.record_warmup(elapsed_ms)
        except Exception:
            pass

        return {
            "success": success,
            "latency_ms": elapsed_ms,
            "returncode": process.returncode
        }

    except subprocess.TimeoutExpired:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "success": False,
            "latency_ms": elapsed_ms,
            "error": "Warmup timed out (30s)"
        }
    except FileNotFoundError:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "success": False,
            "latency_ms": elapsed_ms,
            "error": "claude command not found"
        }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "success": False,
            "latency_ms": elapsed_ms,
            "error": str(e)
        }


def show_latency_prediction():
    """Show predicted latency based on historical data."""
    try:
        manager = get_metrics_manager()
        prediction = manager.get_prediction_string()
        if prediction:
            print(f"{Colors.DIM}{prediction}{Colors.RESET}")
    except Exception:
        pass


def startup_warmup(show_progress: bool = True):
    """
    Perform all startup warmup operations in parallel.

    1. Verify grimoire cache
    2. Warm Deepgram connection
    3. Optionally warm Claude connection (if --warm flag)
    """
    if show_progress:
        print(f"{Colors.DIM}Warming up...{Colors.RESET}", end=" ", flush=True)

    results = {}

    # Use ThreadPoolExecutor for parallel warmup
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all warmup tasks
        futures = {
            executor.submit(verify_grimoire_cache): "grimoire",
            executor.submit(warmup_all): "all_caches",
        }

        # Add Claude warmup if enabled
        if WARM_MODE:
            futures[executor.submit(warm_claude_connection)] = "claude"

        # Collect results as they complete
        for future in concurrent.futures.as_completed(futures, timeout=35):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as e:
                results[name] = {"error": str(e)}

    if show_progress:
        # Show compact warmup summary
        claude_result = results.get("claude", {})

        if WARM_MODE and claude_result:
            claude_ms = claude_result.get("latency_ms", 0)
            if claude_result.get("success"):
                print(f"{Colors.GREEN}Claude ready{Colors.RESET} ({claude_ms:.0f}ms)")
            else:
                print(f"{Colors.YELLOW}Claude warmup: {claude_result.get('error', 'failed')}{Colors.RESET}")
        else:
            print(f"{Colors.GREEN}Ready{Colors.RESET}")

    return results


# === Immediate Acknowledgment ===

def acknowledge_command():
    """
    Immediate feedback before Claude executes.
    Uses afplay for macOS sound or visual spinner fallback.
    """
    # Try macOS afplay with system sound
    try:
        # Use a short system sound - Tink is quick and unobtrusive
        sound_paths = [
            "/System/Library/Sounds/Tink.aiff",
            "/System/Library/Sounds/Pop.aiff",
            "/System/Library/Sounds/Ping.aiff",
        ]
        for sound in sound_paths:
            if os.path.exists(sound):
                subprocess.Popen(
                    ["afplay", sound],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True
    except Exception:
        pass

    # Fallback: visual acknowledgment
    print(f"{Colors.YELLOW}[Hmm...]{Colors.RESET}", end=" ", flush=True)
    return True


def show_thinking_indicator(message: str = "Thinking"):
    """Show a visual indicator that processing is happening."""
    print(f"{Colors.BLUE}[{message}...]{Colors.RESET}", flush=True)


def play_retry_sound():
    """
    Audio feedback indicating a retry is happening.
    Uses a different sound than acknowledge_command to distinguish.
    """
    try:
        # Use Basso (lower tone) for retry - distinct from Tink
        sound_paths = [
            "/System/Library/Sounds/Basso.aiff",
            "/System/Library/Sounds/Sosumi.aiff",
            "/System/Library/Sounds/Bottle.aiff",
        ]
        for sound in sound_paths:
            if os.path.exists(sound):
                subprocess.Popen(
                    ["afplay", sound],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True
    except Exception:
        pass

    # Fallback: visual indicator only
    return False


# === Audio Feedback ===

def ping(freq: int = 800, duration_ms: int = 100):
    """Play a confirmation tone."""
    if not AUDIO_FEEDBACK:
        return

    try:
        import numpy as np
        import simpleaudio
        sample_rate = 44100
        t = np.linspace(0, duration_ms/1000, int(sample_rate * duration_ms/1000), False)
        wave = np.sin(2 * np.pi * freq * t) * 0.3
        audio = (wave * 32767).astype(np.int16)
        play_obj = simpleaudio.play_buffer(audio, 1, 2, sample_rate)
        play_obj.wait_done()
    except Exception:
        pass  # Silent fail for audio feedback


def ping_heard():
    """Low tone - 'I heard you'"""
    ping(400, 100)


def ping_success():
    """High tone - 'Success'"""
    ping(800, 150)


def ping_error():
    """Double low tone - 'Error'"""
    ping(300, 100)
    ping(300, 100)


# === Speech-to-Text ===

def get_grimoire_keywords() -> str:
    """
    Extract keywords from grimoire phrases for STT boosting.
    Returns Deepgram keywords parameter string.
    """
    grimoire = load_grimoire()
    commands = grimoire.get("commands", [])

    # Extract significant words from phrases
    keywords = set()
    stopwords = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or"}

    for cmd in commands:
        words = cmd["phrase"].lower().split()
        for word in words:
            if word not in stopwords and len(word) > 2:
                keywords.add(word)

    # Build keyword string with boost values
    # More distinctive words get higher boost
    keyword_str = ",".join(f"{kw}:2" for kw in sorted(keywords)[:20])
    return keyword_str


def _validate_api_key(api_key: str) -> bool:
    """Basic validation that API key looks plausible."""
    if not api_key:
        return False
    # Deepgram keys are typically 40+ hex chars
    if len(api_key) < 32:
        return False
    # Should be alphanumeric (hex)
    if not all(c.isalnum() for c in api_key):
        return False
    return True


def transcribe_audio(audio_data: bytes) -> str:
    """
    Send audio to Deepgram for transcription.
    Uses keyword boosting for grimoire phrases.
    """
    api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        print(f"{Colors.RED}[E{ErrorCode.STT_NO_API_KEY}] DEEPGRAM_API_KEY not set{Colors.RESET}")
        print(f"{Colors.DIM}  Run: export DEEPGRAM_API_KEY='your-key-here'{Colors.RESET}")
        print(f"{Colors.DIM}  Get a key at: https://console.deepgram.com{Colors.RESET}")
        return ""

    if not _validate_api_key(api_key):
        print(f"{Colors.RED}[E{ErrorCode.STT_INVALID_API_KEY}] DEEPGRAM_API_KEY appears invalid{Colors.RESET}")
        print(f"{Colors.DIM}  Keys should be 32+ alphanumeric characters{Colors.RESET}")
        return ""

    url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true"
    keywords = get_grimoire_keywords()
    if keywords:
        url += f"&keywords={keywords}"

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "audio/wav",
    }

    req = urllib.request.Request(url, data=audio_data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read())
            transcript = result["results"]["channels"][0]["alternatives"][0]["transcript"]
            return transcript
    except urllib.error.HTTPError as e:
        error_msg = redact_sensitive(str(e), api_key)
        if e.code in (401, 403):
            print(f"{Colors.RED}[E{ErrorCode.STT_INVALID_API_KEY}] Authentication failed{Colors.RESET}")
            print(f"{Colors.DIM}  Check your DEEPGRAM_API_KEY is valid and not expired{Colors.RESET}")
        else:
            print(f"{Colors.RED}[E{ErrorCode.STT_NETWORK_ERROR}] Deepgram error (HTTP {e.code}){Colors.RESET}")
        return ""
    except urllib.error.URLError as e:
        print(f"{Colors.RED}[E{ErrorCode.NETWORK_UNREACHABLE}] Network error: {e.reason}{Colors.RESET}")
        print(f"{Colors.DIM}  Check your internet connection{Colors.RESET}")
        return ""
    except Exception as e:
        error_msg = redact_sensitive(str(e), api_key)
        print(f"{Colors.RED}[E{ErrorCode.STT_TRANSCRIPTION_FAILED}] Transcription failed: {error_msg}{Colors.RESET}")
        return ""


class TranscriptionError(Exception):
    """Custom exception for transcription failures with retry info."""

    def __init__(self, message: str, is_retryable: bool = False):
        super().__init__(message)
        self.is_retryable = is_retryable


def _is_retryable_error(error: Exception) -> bool:
    """
    Determine if an error is worth retrying.
    Network/timeout errors: retry
    Auth/client errors: don't retry (won't help)
    """
    if isinstance(error, urllib.error.HTTPError):
        # 4xx errors (except 408 Request Timeout, 429 Rate Limit) are not retryable
        if 400 <= error.code < 500:
            return error.code in (408, 429)
        # 5xx server errors are retryable
        return error.code >= 500

    if isinstance(error, urllib.error.URLError):
        # Network errors are retryable
        reason = str(error.reason).lower()
        # Check for common retryable network conditions
        retryable_reasons = [
            "timed out", "timeout", "connection refused",
            "network is unreachable", "temporary failure",
            "name or service not known", "connection reset"
        ]
        return any(r in reason for r in retryable_reasons)

    if isinstance(error, TimeoutError):
        return True

    if isinstance(error, OSError):
        # Network-related OS errors are retryable
        return True

    # Unknown errors: don't retry by default
    return False


def _transcribe_audio_single(audio_data: bytes) -> str:
    """
    Single transcription attempt. Raises TranscriptionError on failure.
    Used internally by transcribe_audio_with_retry.
    """
    api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        raise TranscriptionError(
            f"[E{ErrorCode.STT_NO_API_KEY}] DEEPGRAM_API_KEY not set",
            is_retryable=False
        )

    if not _validate_api_key(api_key):
        raise TranscriptionError(
            f"[E{ErrorCode.STT_INVALID_API_KEY}] Invalid API key format",
            is_retryable=False
        )

    url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true"
    keywords = get_grimoire_keywords()
    if keywords:
        url += f"&keywords={keywords}"

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "audio/wav",
    }

    req = urllib.request.Request(url, data=audio_data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read())
            transcript = result["results"]["channels"][0]["alternatives"][0]["transcript"]
            return transcript
    except urllib.error.HTTPError as e:
        is_retryable = _is_retryable_error(e)
        if e.code in (401, 403):
            raise TranscriptionError(
                f"[E{ErrorCode.STT_INVALID_API_KEY}] Authentication failed",
                is_retryable=False
            )
        elif e.code == 429:
            raise TranscriptionError(
                f"[E{ErrorCode.NETWORK_RATE_LIMITED}] Rate limit exceeded",
                is_retryable=True
            )
        else:
            raise TranscriptionError(
                f"[E{ErrorCode.STT_NETWORK_ERROR}] Service error (HTTP {e.code})",
                is_retryable=is_retryable
            )
    except urllib.error.URLError as e:
        is_retryable = _is_retryable_error(e)
        raise TranscriptionError(
            f"[E{ErrorCode.NETWORK_UNREACHABLE}] Connection failed",
            is_retryable=is_retryable
        )
    except TimeoutError:
        raise TranscriptionError(
            f"[E{ErrorCode.STT_TIMEOUT}] Request timed out",
            is_retryable=True
        )
    except Exception:
        raise TranscriptionError(
            f"[E{ErrorCode.STT_TRANSCRIPTION_FAILED}] Transcription failed",
            is_retryable=False
        )


def transcribe_audio_with_retry(audio_data: bytes) -> tuple[str, bool]:
    """
    Transcribe audio with exponential backoff retry logic.

    Args:
        audio_data: WAV audio bytes to transcribe

    Returns:
        Tuple of (transcript, success). On failure after all retries,
        returns ("", False).
    """
    if not RETRY_ENABLED:
        # Retry disabled - use original single-attempt logic
        result = transcribe_audio(audio_data)
        return (result, bool(result))

    max_attempts = 3
    delays = [0.5, 1.0, 2.0]  # Exponential backoff

    for attempt in range(max_attempts):
        try:
            transcript = _transcribe_audio_single(audio_data)
            return (transcript, True)

        except TranscriptionError as e:
            # Don't retry non-retryable errors
            if not e.is_retryable:
                print(f"{Colors.RED}Transcription failed: {e}{Colors.RESET}")
                return ("", False)

            # If we have retries left, show retry message
            if attempt < max_attempts - 1:
                delay = delays[attempt]
                print(f"{Colors.YELLOW}Transcription hiccup. Retrying in {delay}s... (attempt {attempt + 2}/{max_attempts}){Colors.RESET}")
                play_retry_sound()
                time.sleep(delay)
            else:
                # All retries exhausted
                print(f"{Colors.RED}Transcription failed after {max_attempts} attempts.{Colors.RESET}")
                return ("", False)

    # Should not reach here, but just in case
    return ("", False)


# === Command Execution ===

def _handle_claude_output_line(line: str, output_handler: 'StreamingOutputHandler'):
    """Parse and handle a single line of Claude JSON stream output."""
    try:
        data = json.loads(line)
        msg_type = data.get("type")

        # Handle assistant messages (with enhanced display)
        if msg_type == "assistant":
            output_handler.handle_assistant(data)

        # Handle content blocks (character-by-character streaming)
        elif msg_type == "content_block_delta":
            output_handler.handle_content_delta(data)

        # Handle tool use (show what Claude is doing with context)
        elif msg_type == "tool_use":
            output_handler.handle_tool_use(data)

        # Handle result - also capture conversation_id
        elif msg_type == "result":
            output_handler.handle_result(data)

        # Also look for session info in system messages
        elif msg_type == "system":
            output_handler.handle_system(data)

        # Handle error messages
        elif msg_type == "error":
            output_handler.handle_error(data)

    except json.JSONDecodeError:
        # Not JSON, print raw (might be error message)
        output_handler.stop_waiting()
        print(f"{Colors.YELLOW}{line}{Colors.RESET}")


def disambiguate(matches: list) -> tuple:
    """
    Present disambiguation options when multiple commands match closely.

    Args:
        matches: List of (command, score) tuples

    Returns:
        Selected (command, score) tuple or (None, None) if cancelled
    """
    print(f"\n{Colors.YELLOW}Multiple matches found. Did you mean:{Colors.RESET}\n")

    for i, (cmd, score) in enumerate(matches, 1):
        tags = ", ".join(cmd.get("tags", []))
        print(f"  {Colors.CYAN}{i}.{Colors.RESET} \"{cmd['phrase']}\"")
        print(f"     {Colors.DIM}[{tags}] (score: {score}){Colors.RESET}")

    print(f"\n  {Colors.DIM}0. Cancel{Colors.RESET}")

    try:
        choice = input(f"\n{Colors.BOLD}Select [1-{len(matches)}]:{Colors.RESET} ").strip()
        if choice == "0" or not choice:
            return None, None
        idx = int(choice) - 1
        if 0 <= idx < len(matches):
            return matches[idx]
    except (ValueError, IndexError):
        pass

    print(f"{Colors.RED}Invalid selection.{Colors.RESET}")
    return None, None


def execute_command(command: dict, modifiers: list, dry_run: bool = False, timing_report: TimingReport = None, phrase_spoken: str = None, score: float = None) -> tuple:
    """
    Execute a matched grimoire command.

    Expands the literary phrase into a full prompt and sends to Claude.

    Returns:
        Tuple of (return_code, conversation_id). conversation_id may be None.
    """
    info = get_command_info(command)
    conversation_id = None

    # Check for dry run modifier
    if any(m.get("effect") == "dry_run" for m in modifiers):
        dry_run = True

    # Global sandbox mode forces dry run
    if SANDBOX_MODE:
        dry_run = True

    # Confirmation check
    if info["requires_confirmation"] and not dry_run:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  This command requires confirmation.{Colors.RESET}")
        print(f"   Phrase: {Colors.CYAN}\"{info['phrase']}\"{Colors.RESET}")
        print(f"   Tags: {Colors.DIM}{info['tags']}{Colors.RESET}")
        confirm = input(f"\n{Colors.BOLD}Proceed? [y/N]:{Colors.RESET} ").strip().lower()
        if confirm != "y":
            print(f"{Colors.DIM}Aborted.{Colors.RESET}")
            return (1, None)

    # Expand the command
    expansion = expand_command(command, modifiers)

    print(f"\n{Colors.DIM}{'─' * 50}{Colors.RESET}")
    print(f"{Colors.GREEN}Incantation:{Colors.RESET} \"{Colors.BOLD}{command['phrase']}{Colors.RESET}\"")
    if modifiers:
        print(f"{Colors.MAGENTA}Modifiers:{Colors.RESET} {[m['effect'] for m in modifiers]}")

    # Show latency prediction (subtle, always shown)
    show_latency_prediction()

    # If this is a continuation command, show what we're continuing
    if info.get("use_continue"):
        last_cmd = get_last_successful()
        if last_cmd:
            time_ago = get_time_since_last()
            print(f"{Colors.CYAN}Continuing:{Colors.RESET} '{last_cmd.phrase_matched}' from {time_ago}")
        else:
            print(f"{Colors.DIM}(No prior command to continue){Colors.RESET}")

    print(f"{Colors.DIM}{'─' * 50}{Colors.RESET}")

    if dry_run:
        print(f"\n{Colors.YELLOW}[DRY RUN - Showing expansion only]{Colors.RESET}\n")
        print(f"{Colors.DIM}{expansion}{Colors.RESET}")
        print(f"\n{Colors.DIM}{'─' * 50}{Colors.RESET}")
        return (0, None)

    # Handle --continue flag
    if info.get("use_continue"):
        cmd = ["claude", "--continue", "-p", expansion, "--verbose", "--output-format", "stream-json"]
    else:
        cmd = ["claude", "-p", expansion, "--verbose", "--output-format", "stream-json"]

    # Immediate acknowledgment before execution
    acknowledge_command()
    print()  # Clean line before streaming

    # Create streaming output handler
    output_handler = StreamingOutputHandler()

    # Start Claude execution timer and track start time
    start_time = time.perf_counter()
    claude_timer = None
    if timing_report:
        claude_timer = timing_report.timer("Claude Exec")
        claude_timer.start()

    # Start waiting spinner
    output_handler.start_waiting()

    # Track time for timeout and warnings
    last_output_time = time.perf_counter()
    warning_shown = False
    timeout_reached = False

    # Stream output from Claude
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        # Use select for non-blocking reads with timeout checking
        import select
        import os as os_module

        # Make stdout non-blocking on Unix-like systems
        use_select = False
        try:
            fd = process.stdout.fileno()
            import fcntl
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os_module.O_NONBLOCK)
            use_select = True
        except (ImportError, OSError, AttributeError):
            # Windows, unsupported, or mock - fall back to blocking reads
            use_select = False

        while True:
            # Check for timeout
            current_time = time.perf_counter()
            elapsed_since_output = current_time - last_output_time
            total_elapsed = current_time - start_time

            # Show warning after CLAUDE_WARNING_SECONDS of no output
            if not warning_shown and elapsed_since_output >= CLAUDE_WARNING_SECONDS:
                output_handler.stop_waiting()
                print(f"\n{Colors.YELLOW}[Warning] No output for {int(elapsed_since_output)}s. Press Ctrl+C to cancel.{Colors.RESET}")
                warning_shown = True

            # Check total timeout
            if total_elapsed >= CLAUDE_TIMEOUT_SECONDS:
                output_handler.stop_waiting()
                print(f"\n{Colors.RED}[Timeout] Claude execution timed out after {int(total_elapsed)}s.{Colors.RESET}")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                timeout_reached = True
                break

            # Check if process has finished
            if process.poll() is not None:
                # Process finished - read any remaining output
                for line in process.stdout:
                    line = line.strip()
                    if line:
                        _handle_claude_output_line(line, output_handler)
                break

            # Try to read output
            if use_select:
                ready, _, _ = select.select([process.stdout], [], [], 1.0)
                if ready:
                    line = process.stdout.readline()
                    if line:
                        line = line.strip()
                        if line:
                            _handle_claude_output_line(line, output_handler)
                            last_output_time = time.perf_counter()
                            warning_shown = False  # Reset warning on new output
            else:
                # Blocking read with periodic checks
                line = process.stdout.readline()
                if line:
                    line = line.strip()
                    if line:
                        _handle_claude_output_line(line, output_handler)
                        last_output_time = time.perf_counter()
                        warning_shown = False
                elif process.poll() is not None:
                    break

        if not timeout_reached:
            process.wait()

        # Stop Claude timer
        if claude_timer:
            claude_timer.stop()

        # Calculate elapsed time
        elapsed_seconds = time.perf_counter() - start_time

        # Get conversation_id from handler
        conversation_id = output_handler.conversation_id

        print(f"\n{Colors.DIM}{'─' * 50}{Colors.RESET}")

        # Determine success status
        if timeout_reached:
            success = False
            return_code = 124  # Standard timeout exit code (same as GNU timeout)
        else:
            success = process.returncode == 0
            return_code = process.returncode

        # Show enhanced summary with tool count
        summary = output_handler.get_summary(elapsed_seconds, success)
        print(summary)

        if success:
            ping_success()
        else:
            ping_error()

        # Record timing to metrics for future predictions
        if timing_report:
            timing_report.record_to_metrics()
            timing_report.display()  # Full breakdown if TIMING_MODE

        return (return_code, conversation_id)

    except FileNotFoundError:
        output_handler.stop_waiting()
        print(f"{Colors.RED}[E{ErrorCode.CLAUDE_NOT_FOUND}] 'claude' command not found{Colors.RESET}")
        print(f"{Colors.DIM}  Install: npm install -g @anthropic-ai/claude-code{Colors.RESET}")
        print(f"{Colors.DIM}  Then restart your terminal{Colors.RESET}")
        ping_error()
        return (1, None)
    except KeyboardInterrupt:
        output_handler.stop_waiting()
        # Gracefully terminate the process
        if 'process' in locals() and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
        print(f"\n\n{Colors.YELLOW}Interrupted.{Colors.RESET}")
        return (130, None)


# === History Display ===

def show_last_command():
    """Display the most recent command from history."""
    last = get_last_successful()
    if last:
        time_ago = get_time_since_last()
        print(f"\n{Colors.CYAN}Last command ({time_ago}):{Colors.RESET}")
        print(f"  Phrase: \"{Colors.BOLD}{last.phrase_matched}{Colors.RESET}\"")
        print(f"  Spoken: \"{last.phrase_spoken}\"")
        if last.score:
            print(f"  Score: {last.score:.0f}")
        if last.modifiers:
            print(f"  Modifiers: {last.modifiers}")
        print(f"  Duration: {last.execution_time_ms:.0f}ms")
        if last.conversation_id:
            print(f"  Session: {last.conversation_id[:12]}...")
    else:
        print(f"{Colors.DIM}No command history found.{Colors.RESET}")


def show_history_list(n: int = 10):
    """Display the last N commands from history."""
    entries = get_last_n(n)
    if entries:
        display_history(entries, title=f"Last {len(entries)} Commands")
    else:
        print(f"{Colors.DIM}No command history found.{Colors.RESET}")


# === Plain English Fallback ===

def execute_plain_command(transcript: str, timing_report: TimingReport = None) -> int:
    """
    Execute a plain English command directly via Claude Code.

    Used as fallback when no grimoire incantation matches.
    """
    print(f"\n{Colors.DIM}{'─' * 50}{Colors.RESET}")
    print(f"{Colors.CYAN}Plain command:{Colors.RESET} \"{Colors.BOLD}{transcript}{Colors.RESET}\"")
    print(f"{Colors.DIM}{'─' * 50}{Colors.RESET}")

    if SANDBOX_MODE:
        print(f"\n{Colors.YELLOW}[DRY RUN - Would execute as plain command]{Colors.RESET}\n")
        print(f"{Colors.DIM}claude -p \"{transcript}\" --verbose --output-format stream-json{Colors.RESET}")
        print(f"\n{Colors.DIM}{'─' * 50}{Colors.RESET}")
        return 0

    cmd = ["claude", "-p", transcript, "--verbose", "--output-format", "stream-json"]

    # Immediate acknowledgment before execution
    acknowledge_command()
    print(f"\n{Colors.BLUE}[Executing...]{Colors.RESET}\n")

    # Start Claude execution timer
    claude_timer = None
    if timing_report:
        claude_timer = timing_report.timer("Claude Exec")
        claude_timer.start()

    # Stream output from Claude
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        for line in process.stdout:
            line = line.strip()
            if not line:
                continue

            # Parse JSON stream for clean output
            try:
                data = json.loads(line)
                msg_type = data.get("type")

                # Handle assistant messages
                if msg_type == "assistant":
                    message = data.get("message", {})
                    content = message.get("content", [])
                    for block in content:
                        if block.get("type") == "text":
                            print(block.get("text", ""), end="", flush=True)

                # Handle content blocks directly
                elif msg_type == "content_block_delta":
                    delta = data.get("delta", {})
                    if delta.get("type") == "text_delta":
                        print(delta.get("text", ""), end="", flush=True)

                # Handle tool use (show what Claude is doing)
                elif msg_type == "tool_use":
                    tool_name = data.get("name", "unknown")
                    print(f"\n{Colors.DIM}[Using: {tool_name}]{Colors.RESET}", flush=True)

                # Handle result
                elif msg_type == "result":
                    result_text = data.get("result", "")
                    if result_text and not any(c in result_text for c in ['{']):  # Skip JSON results
                        print(f"\n{result_text}", flush=True)

            except json.JSONDecodeError:
                # Not JSON, print raw (might be error message)
                print(f"{Colors.YELLOW}{line}{Colors.RESET}")

        process.wait()
        print(f"\n{Colors.DIM}{'─' * 50}{Colors.RESET}")

        # Stop Claude timer
        if claude_timer:
            claude_timer.stop()

        if process.returncode == 0:
            print(f"{Colors.GREEN}Complete{Colors.RESET}")
            ping_success()
        else:
            print(f"{Colors.RED}Failed (exit code {process.returncode}){Colors.RESET}")
            ping_error()

        # Show timing report if enabled
        if timing_report:
            timing_report.display()

        return process.returncode

    except FileNotFoundError:
        print(f"{Colors.RED}[E{ErrorCode.CLAUDE_NOT_FOUND}] 'claude' command not found{Colors.RESET}")
        print(f"{Colors.DIM}  Install: npm install -g @anthropic-ai/claude-code{Colors.RESET}")
        ping_error()
        return 1
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Interrupted.{Colors.RESET}")
        return 130


def offer_fallback(transcript: str, timing_report: TimingReport = None) -> bool:
    """
    Offer to run transcript as plain command when no grimoire match found.

    Returns True if command was executed, False if user declined.
    """
    if not FALLBACK_ENABLED:
        return False

    try:
        choice = input(f"{Colors.YELLOW}No incantation matched. Run as plain command? [y/N]:{Colors.RESET} ").strip().lower()
        if choice == "y":
            execute_plain_command(transcript, timing_report)
            return True
    except (EOFError, KeyboardInterrupt):
        print()

    return False


# === Modes ===

def test_mode():
    """
    Test mode: type phrases instead of speaking.
    """
    print(f"{Colors.BOLD}{'=' * 50}{Colors.RESET}")
    print(f"{Colors.GREEN}SUZERAIN TEST MODE{Colors.RESET}")
    print(f"{Colors.DIM}Type grimoire phrases. Commands: quit, list, help{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 50}{Colors.RESET}")

    # Startup warmup (parallel)
    startup_warmup(show_progress=True)

    commands = list_commands()
    print(f"\n{Colors.CYAN}Loaded {len(commands)} incantations.{Colors.RESET}")
    print(f"{Colors.DIM}Try: \"the evening redness in the west and the judge watched\"{Colors.RESET}")

    while True:
        try:
            text = input(f"\n{Colors.GREEN}>{Colors.RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Colors.DIM}Exiting.{Colors.RESET}")
            break

        if not text:
            continue

        # Meta commands
        if text.lower() in ("quit", "exit", "q"):
            break
        elif text.lower() == "list":
            show_commands()
            continue
        elif text.lower() == "last":
            show_last_command()
            continue
        elif text.lower() == "help":
            print(f"\n{Colors.BOLD}Commands:{Colors.RESET}")
            print(f"  {Colors.CYAN}list{Colors.RESET}     - Show all grimoire phrases")
            print(f"  {Colors.CYAN}last{Colors.RESET}     - Show the most recent command")
            print(f"  {Colors.CYAN}quit{Colors.RESET}     - Exit test mode")
            print(f"  {Colors.DIM}<phrase>{Colors.RESET} - Execute a grimoire incantation")
            continue

        # Create timing report for this command
        timing = TimingReport()

        # Match against grimoire - get top matches for disambiguation
        parse_timer = timing.timer("Parse")
        parse_timer.start()
        top_matches = match_top_n(text, n=3)
        modifiers = extract_modifiers(text)
        parse_timer.stop()

        if not top_matches:
            print(f"{Colors.RED}No match in grimoire.{Colors.RESET}")
            # Offer plain English fallback
            if offer_fallback(text, timing):
                continue
            print(f"{Colors.DIM}Tip: Use 'list' to see available incantations.{Colors.RESET}")
            continue

        # Check if disambiguation needed (multiple close matches)
        if len(top_matches) > 1:
            top_score = top_matches[0][1]
            close_matches = [m for m in top_matches if top_score - m[1] <= 10]

            if len(close_matches) > 1:
                # Disambiguate
                command, score = disambiguate(close_matches)
                if command is None:
                    continue
            else:
                command, score = top_matches[0]
        else:
            command, score = top_matches[0]

        print(f"\n{Colors.GREEN}Matched:{Colors.RESET} \"{Colors.BOLD}{command['phrase']}{Colors.RESET}\" {Colors.DIM}(score: {score}){Colors.RESET}")
        if modifiers:
            print(f"{Colors.MAGENTA}Modifiers:{Colors.RESET} {[m['effect'] for m in modifiers]}")

        # Track execution time
        exec_start = time.perf_counter()
        return_code, conversation_id = execute_command(command, modifiers, timing_report=timing, phrase_spoken=text, score=score)
        exec_time_ms = (time.perf_counter() - exec_start) * 1000

        # Log to history
        log_history(
            phrase_spoken=text,
            phrase_matched=command['phrase'],
            score=score,
            modifiers=[m['effect'] for m in modifiers],
            execution_time_ms=exec_time_ms,
            success=(return_code == 0),
            error=None if return_code == 0 else f"Exit code {return_code}",
            conversation_id=conversation_id
        )


def listen_mode(once: bool = False, use_wake_word: bool = False, wake_keyword: str = "computer"):
    """
    Voice mode with optional wake word.

    Args:
        once: Process one command then exit
        use_wake_word: If True, listen for wake word instead of push-to-talk
        wake_keyword: Wake word to listen for (default: "computer")
    """
    if not AUDIO_AVAILABLE:
        print(f"{Colors.RED}Error: pyaudio required for voice mode{Colors.RESET}")
        print("Run: pip install pyaudio")
        print("Or use: python src/main.py --test")
        sys.exit(1)

    # Wake word setup
    wake_detector = None
    if use_wake_word:
        try:
            from wake_word import WakeWordDetector, check_setup
            status = check_setup()
            if not status["ready"]:
                print(f"{Colors.YELLOW}Wake word not ready:{Colors.RESET}")
                print(f"  {status['message']}")
                print(f"\n{Colors.DIM}Falling back to push-to-talk mode.{Colors.RESET}")
                use_wake_word = False
            else:
                wake_detector = WakeWordDetector(wake_keyword)
                print(f"{Colors.GREEN}Wake word enabled:{Colors.RESET} say \"{wake_keyword}\" to activate")
        except ImportError as e:
            print(f"{Colors.YELLOW}Wake word unavailable: {e}{Colors.RESET}")
            print(f"{Colors.DIM}Using push-to-talk mode.{Colors.RESET}")
            use_wake_word = False

    print(f"{Colors.BOLD}{'=' * 50}{Colors.RESET}")
    print(f"{Colors.GREEN}SUZERAIN LISTENING{Colors.RESET}")
    if use_wake_word:
        print(f"{Colors.DIM}Say \"{wake_keyword}\" to activate. Ctrl+C to exit.{Colors.RESET}")
    else:
        print(f"{Colors.DIM}Press Enter to record. Ctrl+C to exit.{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 50}{Colors.RESET}")

    # Startup warmup (parallel)
    startup_warmup(show_progress=True)

    pa = pyaudio.PyAudio()
    sample_rate = 16000
    frame_length = 1600  # 100ms chunks for stable streaming

    stream = pa.open(
        rate=sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=frame_length
    )

    # For wake word, need smaller frames
    wake_stream = None
    if use_wake_word and wake_detector:
        wake_stream = pa.open(
            rate=wake_detector.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=wake_detector.frame_length
        )

    print(f"\n{Colors.CYAN}Ready.{Colors.RESET}")

    try:
        while True:
            # Create timing report for this command cycle
            timing = TimingReport()

            # Wait for activation (push-to-talk or wake word)
            if use_wake_word and wake_detector and wake_stream:
                print(f"\n{Colors.DIM}[Listening for \"{wake_keyword}\"...]{Colors.RESET}")
                wake_timer = timing.timer("Wake Word")
                wake_timer.start()
                while True:
                    pcm = wake_stream.read(wake_detector.frame_length, exception_on_overflow=False)
                    if wake_detector.process_frame(pcm):
                        wake_timer.stop()
                        print(f"{Colors.GREEN}Wake word detected!{Colors.RESET}")
                        ping_heard()
                        break
            else:
                input(f"\n{Colors.DIM}[Press Enter to speak...]{Colors.RESET}")
                ping_heard()

            print(f"{Colors.BLUE}Recording... (3 seconds){Colors.RESET}")
            frames = []
            for _ in range(int(sample_rate / frame_length * 3)):
                data = stream.read(frame_length, exception_on_overflow=False)
                frames.append(data)

            print(f"{Colors.DIM}Processing...{Colors.RESET}")

            # Convert to WAV
            import wave
            import io
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(b''.join(frames))
            audio_data = buffer.getvalue()

            # Transcribe with timing and retry logic
            stt_timer = timing.timer("STT")
            stt_timer.start()
            transcript, stt_success = transcribe_audio_with_retry(audio_data)
            stt_timer.stop()

            # Handle transcription failure with re-record option
            if not stt_success and RETRY_ENABLED:
                ping_error()
                try:
                    retry_choice = input(f"{Colors.YELLOW}Transcription failed. Try again? [Y/n]:{Colors.RESET} ").strip().lower()
                    if retry_choice in ("", "y", "yes"):
                        continue  # Go back to recording
                    # User declined re-record, continue to next command cycle
                except (EOFError, KeyboardInterrupt):
                    pass
                if TIMING_MODE:
                    timing.display()
                continue

            if transcript:
                print(f"{Colors.CYAN}Heard:{Colors.RESET} \"{transcript}\"")

                # Parse with timing
                parse_timer = timing.timer("Parse")
                parse_timer.start()
                top_matches = match_top_n(transcript, n=3)
                modifiers = extract_modifiers(transcript)
                parse_timer.stop()

                if top_matches:
                    # Check for close matches needing disambiguation
                    if len(top_matches) > 1:
                        top_score = top_matches[0][1]
                        close_matches = [m for m in top_matches if top_score - m[1] <= 10]
                        if len(close_matches) > 1:
                            command, score = disambiguate(close_matches)
                            if command is None:
                                continue
                        else:
                            command, score = top_matches[0]
                    else:
                        command, score = top_matches[0]

                    print(f"{Colors.GREEN}Matched:{Colors.RESET} \"{command['phrase']}\" {Colors.DIM}(score: {score}){Colors.RESET}")

                    # Track execution time
                    exec_start = time.perf_counter()
                    return_code, conversation_id = execute_command(command, modifiers, timing_report=timing, phrase_spoken=transcript, score=score)
                    exec_time_ms = (time.perf_counter() - exec_start) * 1000

                    # Log to history
                    log_history(
                        phrase_spoken=transcript,
                        phrase_matched=command['phrase'],
                        score=score,
                        modifiers=[m['effect'] for m in modifiers],
                        execution_time_ms=exec_time_ms,
                        success=(return_code == 0),
                        error=None if return_code == 0 else f"Exit code {return_code}",
                        conversation_id=conversation_id
                    )
                else:
                    print(f"{Colors.RED}No grimoire match.{Colors.RESET}")
                    # Offer plain English fallback
                    if not offer_fallback(transcript, timing):
                        ping_error()
                        if TIMING_MODE:
                            timing.display()
            else:
                print(f"{Colors.DIM}(no speech detected){Colors.RESET}")
                ping_error()
                if TIMING_MODE:
                    timing.display()

            if once:
                break

    except KeyboardInterrupt:
        print(f"\n\n{Colors.DIM}Exiting.{Colors.RESET}")
    finally:
        stream.stop_stream()
        stream.close()
        if wake_stream:
            wake_stream.stop_stream()
            wake_stream.close()
        if wake_detector:
            wake_detector.cleanup()
        pa.terminate()


def show_commands():
    """Display all grimoire commands."""
    commands = list_commands()
    modifiers = list_modifiers()

    print("\n" + "=" * 50)
    print("GRIMOIRE COMMANDS")
    print("=" * 50)

    for cmd in commands:
        print(f"\n  \"{cmd['phrase']}\"")
        if cmd['tags']:
            print(f"    Tags: {cmd['tags']}")
        if cmd['requires_confirmation']:
            print("    ⚠️  Requires confirmation")

    print("\n" + "-" * 50)
    print("MODIFIERS (append to any command)")
    print("-" * 50)

    for mod in modifiers:
        print(f"\n  \"...{mod['phrase']}\" → {mod['effect']}")


def validate_mode():
    """Validate grimoire structure."""
    print("Validating grimoire...")
    issues = validate_grimoire()

    if issues:
        print(f"\n❌ Found {len(issues)} issue(s):\n")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    else:
        commands = list_commands()
        modifiers = list_modifiers()
        print("\n✓ Grimoire valid")
        print(f"  {len(commands)} commands")
        print(f"  {len(modifiers)} modifiers")
        return 0


# === First Run / Welcome ===

SUZERAIN_DIR = Path.home() / ".suzerain"
FIRST_RUN_MARKER = SUZERAIN_DIR / ".first_run_complete"


def is_first_run() -> bool:
    """Check if this is the first time running suzerain."""
    return not FIRST_RUN_MARKER.exists()


def mark_first_run_complete():
    """Mark that the first run welcome has been shown."""
    SUZERAIN_DIR.mkdir(parents=True, exist_ok=True)
    FIRST_RUN_MARKER.touch()


def show_welcome():
    """Show the welcome/quick start guide."""
    version = "0.1.1"
    print(f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   {Colors.BOLD}SUZERAIN v{version}{Colors.RESET}{Colors.CYAN}                                       ║
║   Voice-activated Claude Code                            ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝{Colors.RESET}

{Colors.BOLD}Quick Start:{Colors.RESET}
  suzerain --list            See all incantations
  suzerain --test --sandbox  Try commands without executing
  suzerain --test            Type commands to execute
  suzerain                   Voice mode (push-to-talk)

{Colors.BOLD}Requirements:{Colors.RESET}
  {Colors.DIM}•{Colors.RESET} Claude Code CLI    {Colors.DIM}npm install -g @anthropic-ai/claude-code{Colors.RESET}
  {Colors.DIM}•{Colors.RESET} Deepgram API key   {Colors.DIM}export DEEPGRAM_API_KEY='...' (voice only){Colors.RESET}

{Colors.BOLD}Try it now:{Colors.RESET}
  {Colors.GREEN}suzerain --test --sandbox{Colors.RESET}
  {Colors.DIM}Then type:{Colors.RESET} {Colors.YELLOW}the judge smiled{Colors.RESET}

{Colors.DIM}Run 'suzerain --welcome' to see this again.{Colors.RESET}
{Colors.DIM}\"Whatever exists without my knowledge exists without my consent.\"{Colors.RESET}
""")


# === Main ===

def main():
    parser = argparse.ArgumentParser(
        description="Suzerain - Voice-activated Claude Code with literary macros",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='"Whatever exists without my knowledge exists without my consent."'
    )
    parser.add_argument(
        "--test", "-t",
        action="store_true",
        help="Test mode: type phrases instead of speaking"
    )
    parser.add_argument(
        "--once", "-1",
        action="store_true",
        help="Process one command then exit"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all grimoire commands"
    )
    parser.add_argument(
        "--validate", "-v",
        action="store_true",
        help="Validate grimoire structure"
    )
    parser.add_argument(
        "--wake", "-w",
        action="store_true",
        help="Use wake word instead of push-to-talk"
    )
    parser.add_argument(
        "--keyword", "-k",
        default="computer",
        help="Wake word to use (default: computer). Options: alexa, jarvis, computer, hey google, etc."
    )
    parser.add_argument(
        "--sandbox", "-s",
        action="store_true",
        help="Sandbox mode: show expansions but never execute (global dry run)"
    )
    parser.add_argument(
        "--timing",
        action="store_true",
        help="Show detailed latency breakdown after each command"
    )
    parser.add_argument(
        "--warm",
        action="store_true",
        help="Pre-warm Claude connection on startup (reduces first command latency)"
    )
    parser.add_argument(
        "--no-retry",
        action="store_true",
        help="Disable automatic retry on transcription failures"
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Disable plain English fallback when no grimoire match is found"
    )
    parser.add_argument(
        "--last",
        action="store_true",
        help="Show the most recent command from history"
    )
    parser.add_argument(
        "--history",
        type=int,
        nargs="?",
        const=10,
        default=None,
        metavar="N",
        help="Show the last N commands from history (default: 10)"
    )
    parser.add_argument(
        "--welcome",
        action="store_true",
        help="Show the welcome/quick start guide"
    )

    args = parser.parse_args()

    # Show welcome on first run or if explicitly requested
    if args.welcome:
        show_welcome()
        return

    if is_first_run():
        show_welcome()
        mark_first_run_complete()
        return

    # Set global flags FIRST (before any early exits)
    global SANDBOX_MODE, TIMING_MODE, RETRY_ENABLED, FALLBACK_ENABLED, WARM_MODE
    SANDBOX_MODE = args.sandbox
    TIMING_MODE = args.timing
    WARM_MODE = args.warm
    if args.no_retry:
        RETRY_ENABLED = False
    if args.no_fallback:
        FALLBACK_ENABLED = False

    if args.validate:
        sys.exit(validate_mode())

    if args.last:
        show_last_command()
        return

    if args.history is not None:
        show_history_list(args.history)
        return

    if args.list:
        show_commands()
        return

    if args.timing:
        print(f"{Colors.CYAN}{'=' * 50}{Colors.RESET}")
        print(f"{Colors.CYAN}   TIMING MODE - Detailed latency breakdown enabled{Colors.RESET}")
        print(f"{Colors.CYAN}{'=' * 50}{Colors.RESET}\n")

    if args.sandbox:
        print(f"{Colors.YELLOW}{'=' * 50}{Colors.RESET}")
        print(f"{Colors.YELLOW}   SANDBOX MODE - No commands will execute{Colors.RESET}")
        print(f"{Colors.YELLOW}{'=' * 50}{Colors.RESET}\n")

    if args.warm:
        print(f"{Colors.BLUE}{'=' * 50}{Colors.RESET}")
        print(f"{Colors.BLUE}   WARM MODE - Pre-warming Claude connection{Colors.RESET}")
        print(f"{Colors.BLUE}{'=' * 50}{Colors.RESET}\n")

    if args.test:
        test_mode()
    else:
        listen_mode(once=args.once, use_wake_word=args.wake, wake_keyword=args.keyword)


if __name__ == "__main__":
    main()
