"""
Suzerain v0.4 - Conversational Claude Code with transparency.

"Whatever exists without my knowledge exists without my consent."

v0.4 Features:
- Meta-prompting for concise spoken summaries
- Transparency: see what Claude is doing in real-time
- Natural language default (grimoire optional)
- Conversation context (coming soon)

Usage:
    python src/main.py              # Run with push-to-talk
    python src/main.py --test       # Test mode (type phrases)
    python src/main.py --list       # List all grimoire commands
    python src/main.py --validate   # Validate grimoire structure
    python src/main.py --timing     # Show detailed latency breakdown
    python src/main.py --sandbox    # Dry run mode (no execution)
    python src/main.py --warm       # Pre-warm Claude connection on startup
    python src/main.py --no-fallback  # Disable plain English fallback
    python src/main.py --no-summary   # Disable spoken summaries
"""

import argparse
import asyncio
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
    match_top_n as fuzzy_match_top_n,
    extract_modifiers,
    expand_command,
    load_grimoire,
    list_commands,
    list_modifiers,
    validate_grimoire,
    get_command_info
)
from agents import route_command, route_intent, AgentType

# Lazy imports for optional modules
_streaming_stt = None


def _get_streaming_stt():
    """Lazy load streaming STT module."""
    global _streaming_stt
    if _streaming_stt is None:
        import streaming_stt
        _streaming_stt = streaming_stt
    return _streaming_stt


def match_top_n(text: str, n: int = 3):
    """Match text against grimoire using fuzzy string matching."""
    return fuzzy_match_top_n(text, n=n)


from history import (
    log_command as log_history,
    get_last_n,
    get_last_successful,
    get_time_since_last,
    display_history
)
from cache import warmup_all, verify_grimoire_cache
from errors import (
    ErrorCode,
    redact_sensitive
)
from session import (
    log_command as log_session,
    get_session_context,
    get_session,
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

# Global auto-plain mode flag (skip y/N confirmation for plain commands)
AUTO_PLAIN = False

# Global dangerous mode flag (skip Claude permission prompts)
# Default True - skip Claude permission prompts for smoother UX
DANGEROUS_MODE = True

# Global retry mode flag (enabled by default)
RETRY_ENABLED = True

# Recording duration in seconds
RECORD_SECONDS = 6

# Global warm mode flag (default: True - pre-warm Claude connection for faster first command)
WARM_MODE = True

# Global streaming STT mode flag (default: True - WebSocket streaming for lower latency)
STREAMING_STT_MODE = True

# Global live endpointing mode (stream audio live, stop when speech ends)
# When True: Streams audio to Deepgram in real-time, stops when endpointing detected
# When False: Records for fixed RECORD_SECONDS duration, then transcribes
# Enable with --live flag. Saves 1-4 seconds on short commands.
LIVE_ENDPOINTING_MODE = False

# Claude execution timeout settings
CLAUDE_TIMEOUT_SECONDS = 300  # 5 minutes default
CLAUDE_WARNING_SECONDS = 30   # Show warning after 30s of no output

# v0.4: Meta-prompting for summaries
SUMMARY_ENABLED = True  # Enable spoken summaries by default

# v0.5: Local STT with Whisper (no API required)
LOCAL_STT_MODE = False  # Use local Whisper instead of Deepgram
LOCAL_STT_MODEL = "small.en"  # tiny.en (fastest), base.en, small.en (best balance)

# v0.6: Interrupt detection during Claude execution
_current_process: 'subprocess.Popen | None' = None  # Track running Claude process
_interrupt_requested = False  # Flag for interrupt state

# v0.6: Background voice monitor for escape hatches during execution
_voice_monitor_thread: 'threading.Thread | None' = None
_voice_monitor_stop = threading.Event()  # Signal to stop monitoring
VOICE_MONITOR_ENABLED = True  # Can disable with --no-monitor
VOICE_MONITOR_CHUNK_SECONDS = 1.0  # Listen in 1-second chunks
VOICE_MONITOR_MODEL = "tiny.en"  # Fastest model for escape hatch detection

# v0.6: Trust/autonomy levels
# Controls how much confirmation is required before execution
TRUST_LEVEL = 3  # Default: supervised (confirm destructive only)

class TrustLevel:
    """Trust level constants and utilities."""
    PREVIEW = 1     # Show only, never execute
    EXPLICIT = 2    # Confirm every action
    SUPERVISED = 3  # Confirm destructive only (default)
    ASSISTED = 4    # Auto-execute, summarize after
    AUTONOMOUS = 5  # Full auto, minimal output

    NAMES = {
        1: "preview",
        2: "explicit",
        3: "supervised",
        4: "assisted",
        5: "autonomous",
    }

    DESCRIPTIONS = {
        1: "Preview mode - show what would happen, never execute",
        2: "Explicit mode - confirm every action before execution",
        3: "Supervised mode - confirm destructive actions only",
        4: "Assisted mode - auto-execute, summarize after",
        5: "Autonomous mode - full auto, minimal output",
    }

    @classmethod
    def name(cls, level: int) -> str:
        return cls.NAMES.get(level, "unknown")

    @classmethod
    def description(cls, level: int) -> str:
        return cls.DESCRIPTIONS.get(level, "unknown")

# Meta-prompt injected into Claude to get concise summaries
META_SYSTEM_PROMPT = '''
After completing the task, end your response with a SUMMARY block in this exact format:

```summary
Action: [What you did in one sentence]
Changes: [List files modified/created, or "None" if no files changed]
Status: [Success/Failure + brief note if needed]
```

Keep the summary suitable for text-to-speech (under 15 seconds when spoken).
'''

# v0.6: Blood Meridian atmospheric quotes
MERIDIAN_QUOTES = [
    "Whatever exists without my knowledge exists without my consent.",
    "The truth about the world is that anything is possible.",
    "War is god.",
    "They rode on.",
    "If God meant to interfere in the degeneracy of mankind, would he not have done so by now?",
    "Whatever in creation exists without my knowledge exists without my consent.",
    "The man who believes that the secrets of the world are forever hidden lives in mystery and fear.",
    "It makes no difference what men think of war. War endures.",
    "Only that man who has offered up himself entire to the blood of war... can dance.",
]


def get_meridian_quote() -> str:
    """Get a random Blood Meridian quote for atmosphere."""
    import random
    return random.choice(MERIDIAN_QUOTES)


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
        """Record timing data to metrics (no-op for now)."""
        pass


# === Audio Dependencies (optional) ===
try:
    import pyaudio
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

# Audio feedback enabled - using afplay instead of simpleaudio (which crashes on Apple Silicon)
AUDIO_FEEDBACK = True


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
    - v0.4: Captures full output for summary extraction
    """

    def __init__(self):
        self.tools_used = []
        self.files_touched = []  # v0.4: Track files for context
        self.is_thinking = False
        self.last_was_text = False
        self.char_delay = 0.003  # 3ms between chars for streaming effect
        self.first_output_received = False
        self.spinner = None
        self.total_chars = 0
        self.conversation_id = None
        self.full_output = []  # v0.4: Capture all output for summary extraction

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

        # v0.4: Capture output for summary extraction
        self.full_output.append(text)

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

    def get_full_output(self) -> str:
        """v0.4: Get complete captured output for summary extraction."""
        return ''.join(self.full_output)

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
        """Display tool usage with icon and details. v0.4: Track files touched."""
        self.tools_used.append(tool_name)

        detail = ""
        file_path = None

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

        # v0.4: Track files touched for context
        if file_path and tool_name in ("Write", "write_file", "Edit", "edit_file"):
            self.files_touched.append(Path(file_path).name)

        if detail:
            print(f"\n{Colors.CYAN}[Claude] {tool_name}: {detail}{Colors.RESET}", flush=True)
        else:
            print(f"\n{Colors.CYAN}[Claude] {tool_name}{Colors.RESET}", flush=True)

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
    """Show predicted latency (no-op for now)."""
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

        parts = []
        if WARM_MODE and claude_result:
            claude_ms = claude_result.get("latency_ms", 0)
            if claude_result.get("success"):
                parts.append(f"Claude ready ({claude_ms:.0f}ms)")
            else:
                parts.append(f"Claude: {claude_result.get('error', 'failed')}")

        if parts:
            print(" | ".join(parts))
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
# Using macOS afplay with system sounds instead of simpleaudio (which crashes on Apple Silicon)

def _play_system_sound(sounds: list[str]) -> bool:
    """
    Play first available system sound using afplay.
    Returns True if sound was played, False otherwise.
    """
    if not AUDIO_FEEDBACK:
        return False

    try:
        for sound in sounds:
            if os.path.exists(sound):
                subprocess.Popen(
                    ["afplay", sound],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True
    except Exception:
        pass
    return False


def ping_heard():
    """Subtle sound - 'I heard you'"""
    _play_system_sound([
        "/System/Library/Sounds/Tink.aiff",
        "/System/Library/Sounds/Pop.aiff",
    ])


def ping_success():
    """Positive sound - 'Success'"""
    _play_system_sound([
        "/System/Library/Sounds/Glass.aiff",
        "/System/Library/Sounds/Ping.aiff",
        "/System/Library/Sounds/Pop.aiff",
    ])


def ping_error():
    """Negative sound - 'Error'"""
    _play_system_sound([
        "/System/Library/Sounds/Basso.aiff",
        "/System/Library/Sounds/Sosumi.aiff",
        "/System/Library/Sounds/Funk.aiff",
    ])


def ping_interrupt():
    """Sound for interrupt - 'Stopped'"""
    _play_system_sound([
        "/System/Library/Sounds/Basso.aiff",
        "/System/Library/Sounds/Funk.aiff",
    ])


# === v0.6: Interrupt Detection ===

def request_interrupt():
    """
    Request interruption of the current Claude process.
    Called when user says 'stop', 'hold', 'cancel', etc.
    """
    global _interrupt_requested, _current_process
    _interrupt_requested = True

    if _current_process and _current_process.poll() is None:
        print(f"\n{Colors.RED}[INTERRUPT] Stopping execution...{Colors.RESET}")
        ping_interrupt()
        _current_process.terminate()
        try:
            _current_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _current_process.kill()
        return True
    return False


def is_interrupt_requested() -> bool:
    """Check if an interrupt has been requested."""
    return _interrupt_requested


def clear_interrupt():
    """Clear the interrupt flag."""
    global _interrupt_requested
    _interrupt_requested = False


def set_current_process(process: 'subprocess.Popen | None'):
    """Track the current running Claude process."""
    global _current_process
    _current_process = process


def check_for_escape_hatch(text: str) -> bool:
    """
    Quick check if text contains an escape hatch command.
    Used for interrupt detection during execution.

    IMPORTANT: Only triggers on ISOLATED utterances (1-2 words max).
    This prevents false positives like "stop sign app" or
    "I need the stop button to work".

    Returns True if an escape hatch is detected.
    """
    if not text:
        return False

    # Clean and tokenize
    words = text.lower().strip().split()

    # Only trigger on isolated utterances (1-2 words max)
    # This prevents false positives from contextual speech
    # "stop" → trigger, "stop sign app" → ignore
    if len(words) > 2:
        return False

    # Fast check against known escape phrases
    escape_phrases = {'stop', 'hold', 'cancel', 'pause', 'wait', 'abort'}
    return bool(set(words) & escape_phrases)


# === v0.6: Background Voice Monitor ===

def _voice_monitor_loop():
    """
    Background thread that listens for escape hatch commands during Claude execution.

    Records short audio chunks, transcribes with local Whisper (tiny.en),
    and calls request_interrupt() if escape hatch detected.

    Features:
    - Energy threshold: Skips silent/quiet chunks to prevent hallucinations
    - Audio feedback: Plays interrupt sound when escape hatch detected
    - Graceful errors: Handles mic issues without crashing
    """
    import io
    import wave
    import numpy as np

    try:
        import pyaudio
    except ImportError:
        # Silently fail - voice monitor is optional enhancement
        return

    try:
        from local_stt import transcribe_audio_local
    except ImportError:
        # Silently fail - need local STT for monitoring
        return

    # Audio settings
    sample_rate = 16000
    chunk_samples = int(sample_rate * VOICE_MONITOR_CHUNK_SECONDS)
    frame_length = 1600  # 100ms frames

    # Energy threshold to skip silent chunks (prevents Whisper hallucinations)
    # RMS energy below this = silence, skip transcription
    ENERGY_THRESHOLD = 300  # Empirically tuned for typical speech vs silence

    pa = None
    stream = None

    try:
        pa = pyaudio.PyAudio()

        # Find default input device
        try:
            default_input = pa.get_default_input_device_info()
        except IOError:
            # No input device available
            pa.terminate()
            return

        stream = pa.open(
            rate=sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=frame_length
        )
    except Exception:
        # Mic not available - silently disable voice monitor
        if pa:
            try:
                pa.terminate()
            except Exception:
                pass
        return

    try:
        while not _voice_monitor_stop.is_set():
            # Record a short chunk
            frames = []
            frames_needed = int(chunk_samples / frame_length)

            for _ in range(frames_needed):
                if _voice_monitor_stop.is_set():
                    break
                try:
                    data = stream.read(frame_length, exception_on_overflow=False)
                    frames.append(data)
                except IOError:
                    # Buffer overflow or mic disconnected - skip this chunk
                    break
                except Exception:
                    break

            if _voice_monitor_stop.is_set() or not frames:
                break

            # Combine frames
            audio_bytes = b''.join(frames)

            # Calculate RMS energy to detect silence
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            rms_energy = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))

            # Skip silent chunks - prevents Whisper hallucinations on silence
            if rms_energy < ENERGY_THRESHOLD:
                continue

            # Convert to WAV
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_bytes)
            audio_data = buffer.getvalue()

            # Transcribe with tiny.en (fast, ~50ms)
            try:
                transcript = transcribe_audio_local(
                    audio_data,
                    model_size=VOICE_MONITOR_MODEL
                )
            except Exception:
                continue  # Transcription failed, try next chunk

            # Check for escape hatch (isolated utterance only)
            if transcript and check_for_escape_hatch(transcript):
                # Audio feedback - let user know we heard them
                ping_interrupt()
                print(f"\n{Colors.YELLOW}[Voice: \"{transcript.strip()}\"]{Colors.RESET}")
                request_interrupt()
                break

    finally:
        # Clean up audio resources
        if stream:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        if pa:
            try:
                pa.terminate()
            except Exception:
                pass


def start_voice_monitor():
    """
    Start background voice monitoring for escape hatches.
    Call this when Claude execution begins.
    """
    global _voice_monitor_thread

    if not VOICE_MONITOR_ENABLED:
        return

    # Don't start if already running
    if _voice_monitor_thread and _voice_monitor_thread.is_alive():
        return

    # Clear the stop signal
    _voice_monitor_stop.clear()

    # Start the monitor thread
    _voice_monitor_thread = threading.Thread(
        target=_voice_monitor_loop,
        daemon=True,
        name="VoiceMonitor"
    )
    _voice_monitor_thread.start()


def stop_voice_monitor():
    """
    Stop background voice monitoring.
    Call this when Claude execution ends.
    """
    global _voice_monitor_thread

    if not _voice_monitor_thread:
        return

    # Signal the thread to stop
    _voice_monitor_stop.set()

    # Wait for thread to finish (with timeout)
    if _voice_monitor_thread.is_alive():
        _voice_monitor_thread.join(timeout=2.0)

    _voice_monitor_thread = None


# === v0.6: Trust-Based Execution ===

def should_execute(command: dict) -> tuple[bool, str]:
    """
    Determine if command should execute based on trust level.

    Args:
        command: Grimoire command dict with optional 'destructive' flag

    Returns:
        Tuple of (should_execute, reason)
    """
    global TRUST_LEVEL

    is_destructive = command.get("destructive", False) or command.get("confirmation", False)
    command_phrase = command.get("phrase", "unknown")

    # Level 1: Preview - never execute
    if TRUST_LEVEL == TrustLevel.PREVIEW:
        return False, "Preview mode - execution disabled"

    # Level 2: Explicit - always confirm
    if TRUST_LEVEL == TrustLevel.EXPLICIT:
        try:
            response = input(f"{Colors.YELLOW}Execute '{command_phrase}'? [y/N]: {Colors.RESET}").strip().lower()
            if response in ('y', 'yes'):
                return True, "User confirmed"
            return False, "User declined"
        except (EOFError, KeyboardInterrupt):
            return False, "Cancelled"

    # Level 3: Supervised - confirm destructive only
    if TRUST_LEVEL == TrustLevel.SUPERVISED:
        if is_destructive:
            try:
                response = input(f"{Colors.YELLOW}⚠️  Destructive action '{command_phrase}'. Execute? [y/N]: {Colors.RESET}").strip().lower()
                if response in ('y', 'yes'):
                    return True, "User confirmed destructive action"
                return False, "User declined destructive action"
            except (EOFError, KeyboardInterrupt):
                return False, "Cancelled"
        return True, "Non-destructive, auto-approved"

    # Level 4 & 5: Assisted/Autonomous - always execute
    return True, "Auto-approved by trust level"


def get_trust_level_display() -> str:
    """Get formatted trust level for display."""
    return f"{TrustLevel.name(TRUST_LEVEL)} (level {TRUST_LEVEL})"


# === v0.4: Summary Extraction and TTS ===

def extract_summary_block(output: str) -> dict | None:
    """
    Extract the ```summary block from Claude's output.

    Returns dict with keys: action, changes, status
    Or None if no summary block found.
    """
    import re

    # Look for ```summary block
    pattern = r'```summary\s*\n(.*?)```'
    match = re.search(pattern, output, re.DOTALL | re.IGNORECASE)

    if not match:
        return None

    summary_text = match.group(1).strip()
    result = {}

    # Parse each line
    for line in summary_text.split('\n'):
        line = line.strip()
        if line.startswith('Action:'):
            result['action'] = line[7:].strip()
        elif line.startswith('Changes:'):
            result['changes'] = line[8:].strip()
        elif line.startswith('Status:'):
            result['status'] = line[7:].strip()

    return result if result else None


def format_summary_for_speech(summary: dict) -> str:
    """
    Format extracted summary dict into speakable text.

    Args:
        summary: Dict with action, changes, status keys

    Returns:
        Concise text suitable for TTS (under 15 seconds)
    """
    parts = []

    # Action is the main thing
    if summary.get('action'):
        parts.append(summary['action'])

    # Status is important
    if summary.get('status'):
        status = summary['status'].lower()
        if 'success' in status:
            parts.append("Success.")
        elif 'fail' in status:
            parts.append(f"Failed: {summary['status']}")
        else:
            parts.append(summary['status'])

    # Changes - just count if many files
    if summary.get('changes') and summary['changes'].lower() != 'none':
        changes = summary['changes']
        # Count files if it's a list
        file_count = changes.count(',') + 1 if ',' in changes else 1
        if file_count > 3:
            parts.append(f"{file_count} files changed.")
        else:
            parts.append(f"Changed: {changes}.")

    return ' '.join(parts) if parts else "Done."


def speak_summary(text: str):
    """
    Use macOS 'say' command to speak a summary.

    Args:
        text: Text to speak (should be brief, under 15s)
    """
    if not SUMMARY_ENABLED:
        return

    # Limit length
    if len(text) > 250:
        text = text[:250] + "..."

    try:
        # Use Samantha voice at slightly faster rate
        subprocess.Popen(
            ["say", "-v", "Samantha", "-r", "210", text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass  # Silent fail if say command not available


def extract_and_speak_summary(output: str):
    """
    Extract summary from Claude's output and speak it via TTS.

    Falls back to heuristic summary extraction if no ```summary block.
    """
    if not SUMMARY_ENABLED:
        return

    # Try to extract structured summary
    summary = extract_summary_block(output)

    if summary:
        text = format_summary_for_speech(summary)
        print(f"\n{Colors.GREEN}[Summary]{Colors.RESET} {text}")
        speak_summary(text)
    else:
        # Fallback to heuristic extraction from audio_feedback
        from audio_feedback import extract_summary_from_result
        text = extract_summary_from_result(output)
        if text and text != "Done.":
            print(f"\n{Colors.GREEN}[Summary]{Colors.RESET} {text}")
            speak_summary(text)


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
    Transcribe audio to text.

    Uses local Whisper if LOCAL_STT_MODE is enabled (v0.5),
    otherwise falls back to Deepgram API.
    """
    # v0.5: Local STT mode (no API required)
    if LOCAL_STT_MODE:
        return _transcribe_audio_local(audio_data)

    # Cloud mode: Use Deepgram API
    return _transcribe_audio_deepgram(audio_data)


def _transcribe_audio_local(audio_data: bytes) -> str:
    """
    Transcribe using local Whisper model.
    No API key required, works offline.
    """
    try:
        from local_stt import transcribe_audio_local
        return transcribe_audio_local(audio_data, model_size=LOCAL_STT_MODEL)
    except ImportError:
        print(f"{Colors.RED}[E] Local STT not available{Colors.RESET}")
        print(f"{Colors.DIM}  Install: pip install faster-whisper{Colors.RESET}")
        return ""
    except Exception as e:
        print(f"{Colors.RED}[E] Local transcription failed: {e}{Colors.RESET}")
        return ""


def _transcribe_audio_deepgram(audio_data: bytes) -> str:
    """
    Send audio to Deepgram for transcription.
    Uses keyword boosting for grimoire phrases.
    """
    # Try config first, then env var
    from config import get_config
    api_key = get_config().deepgram_api_key or os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        print(f"{Colors.RED}[E{ErrorCode.STT_NO_API_KEY}] DEEPGRAM_API_KEY not set{Colors.RESET}")
        print(f"{Colors.DIM}  Run: export DEEPGRAM_API_KEY='your-key-here'{Colors.RESET}")
        print(f"{Colors.DIM}  Or use --local for offline transcription{Colors.RESET}")
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
        print(f"{Colors.DIM}  Check your internet connection or use --local{Colors.RESET}")
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
    # Try config first, then env var
    from config import get_config
    api_key = get_config().deepgram_api_key or os.environ.get("DEEPGRAM_API_KEY")
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

    # v0.6: Route to specialized agent based on command tags
    agent_config = route_command(command)

    # v0.6: Enhance prompt with agent-specific instructions
    if agent_config.meta_prompt_suffix:
        expansion = f"{expansion}\n\n{agent_config.meta_prompt_suffix}"

    # v0.6: Inject session context for multi-turn awareness
    session_context = get_session_context()
    if session_context:
        expansion = f"{expansion}\n\n{session_context}"

    # v0.4: Inject meta-prompt for summary generation
    if SUMMARY_ENABLED:
        expansion = f"{expansion}\n\n{META_SYSTEM_PROMPT}"

    print(f"\n{Colors.DIM}{'─' * 50}{Colors.RESET}")
    print(f"{Colors.GREEN}Incantation:{Colors.RESET} \"{Colors.BOLD}{command['phrase']}{Colors.RESET}\"")
    if agent_config.agent_type != AgentType.GENERAL:
        print(f"{Colors.CYAN}Agent:{Colors.RESET} {agent_config.name}")
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

    # Get project context (if set)
    from config import get_config
    project_path = get_config().project_path

    # === Execute via Claude CLI ===

    # Handle --continue flag
    if info.get("use_continue"):
        cmd = ["claude", "--continue", "-p", expansion, "--verbose", "--output-format", "stream-json"]
    else:
        cmd = ["claude", "-p", expansion, "--verbose", "--output-format", "stream-json"]

    # Add dangerous mode flag if enabled
    if DANGEROUS_MODE:
        cmd.append("--dangerously-skip-permissions")

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
    interrupt_reached = False  # v0.6: Track voice interrupt

    # v0.6: Start background voice monitor for escape hatches
    start_voice_monitor()

    # Stream output from Claude
    try:
        # v0.6: Clear any pending interrupt before starting
        clear_interrupt()

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=project_path  # Run in project context (None = current dir)
        )

        # v0.6: Track process for interrupt handling
        set_current_process(process)

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
            # v0.6: Check for interrupt request (voice "stop" command)
            if is_interrupt_requested():
                output_handler.stop_waiting()
                print(f"\n{Colors.YELLOW}[Interrupted] Stopping execution...{Colors.RESET}")
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                interrupt_reached = True
                break

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

        if not timeout_reached and not interrupt_reached:
            process.wait()

        # v0.6: Clear process tracking and stop voice monitor
        set_current_process(None)
        stop_voice_monitor()

        # Stop Claude timer
        if claude_timer:
            claude_timer.stop()

        # Calculate elapsed time
        elapsed_seconds = time.perf_counter() - start_time

        # Get conversation_id from handler
        conversation_id = output_handler.conversation_id

        print(f"\n{Colors.DIM}{'─' * 50}{Colors.RESET}")

        # Determine success status
        if interrupt_reached:
            success = False
            return_code = 130  # Standard interrupt exit code (SIGINT)
        elif timeout_reached:
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
            # v0.4: Extract and speak summary
            if SUMMARY_ENABLED:
                full_output = output_handler.get_full_output()
                extract_and_speak_summary(full_output)
        else:
            ping_error()

        # Record timing to metrics for future predictions
        if timing_report:
            timing_report.record_to_metrics()
            timing_report.display()  # Full breakdown if TIMING_MODE

        return (return_code, conversation_id)

    except FileNotFoundError:
        output_handler.stop_waiting()
        set_current_process(None)  # v0.6: Clear process tracking
        stop_voice_monitor()  # v0.6: Stop voice monitor
        print(f"{Colors.RED}[E{ErrorCode.CLAUDE_NOT_FOUND}] 'claude' command not found{Colors.RESET}")
        print(f"{Colors.DIM}  Install: npm install -g @anthropic-ai/claude-code{Colors.RESET}")
        print(f"{Colors.DIM}  Then restart your terminal{Colors.RESET}")
        ping_error()
        return (1, None)
    except KeyboardInterrupt:
        output_handler.stop_waiting()
        set_current_process(None)  # v0.6: Clear process tracking
        stop_voice_monitor()  # v0.6: Stop voice monitor
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
    v0.4: Now the primary mode - natural language is default.
    """
    print(f"\n{Colors.DIM}{'─' * 50}{Colors.RESET}")
    print(f"{Colors.CYAN}Command:{Colors.RESET} \"{Colors.BOLD}{transcript}{Colors.RESET}\"")
    print(f"{Colors.DIM}{'─' * 50}{Colors.RESET}")

    if SANDBOX_MODE:
        print(f"\n{Colors.YELLOW}[DRY RUN - Would execute as plain command]{Colors.RESET}\n")
        print(f"{Colors.DIM}claude -p \"{transcript}\" --verbose --output-format stream-json{Colors.RESET}")
        print(f"\n{Colors.DIM}{'─' * 50}{Colors.RESET}")
        return 0

    # v0.4: Inject meta-prompt for summary generation
    prompt = transcript
    if SUMMARY_ENABLED:
        prompt = f"{transcript}\n\n{META_SYSTEM_PROMPT}"

    cmd = ["claude", "-p", prompt, "--verbose", "--output-format", "stream-json"]

    # Add dangerous mode flag if enabled
    if DANGEROUS_MODE:
        cmd.append("--dangerously-skip-permissions")

    # Immediate acknowledgment before execution
    acknowledge_command()
    print()  # Clean line before streaming

    # v0.4: Use StreamingOutputHandler for consistent output + summary capture
    output_handler = StreamingOutputHandler()

    # Start Claude execution timer
    start_time = time.perf_counter()
    claude_timer = None
    if timing_report:
        claude_timer = timing_report.timer("Claude Exec")
        claude_timer.start()

    # Start waiting spinner
    output_handler.start_waiting()

    # Get project context (if set)
    from config import get_config
    project_path = get_config().project_path

    # v0.6: Start background voice monitor for escape hatches
    start_voice_monitor()

    # Stream output from Claude
    try:
        # v0.6: Clear any pending interrupt before starting
        clear_interrupt()

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=project_path  # Run in project context (None = current dir)
        )

        # v0.6: Track process for interrupt handling
        set_current_process(process)

        for line in process.stdout:
            line = line.strip()
            if not line:
                continue

            # Use the same handler as execute_command
            _handle_claude_output_line(line, output_handler)

        process.wait()

        # v0.6: Clear process tracking and stop voice monitor
        set_current_process(None)
        stop_voice_monitor()

        # Stop Claude timer
        if claude_timer:
            claude_timer.stop()

        # Calculate elapsed time
        elapsed_seconds = time.perf_counter() - start_time

        # v0.6: Check if interrupted
        interrupted = is_interrupt_requested()
        if interrupted:
            clear_interrupt()
            print(f"\n{Colors.YELLOW}[Interrupted]{Colors.RESET}")

        print(f"\n{Colors.DIM}{'─' * 50}{Colors.RESET}")

        success = not interrupted and process.returncode == 0

        # Show enhanced summary with tool count
        summary = output_handler.get_summary(elapsed_seconds, success)
        print(summary)

        if success:
            ping_success()
            # v0.4: Extract and speak summary
            if SUMMARY_ENABLED:
                full_output = output_handler.get_full_output()
                extract_and_speak_summary(full_output)
        else:
            ping_error()

        # Show timing report if enabled
        if timing_report:
            timing_report.display()

        return process.returncode

    except FileNotFoundError:
        set_current_process(None)  # v0.6: Clear process tracking
        stop_voice_monitor()  # v0.6: Stop voice monitor
        print(f"{Colors.RED}[E{ErrorCode.CLAUDE_NOT_FOUND}] 'claude' command not found{Colors.RESET}")
        print(f"{Colors.DIM}  Install: npm install -g @anthropic-ai/claude-code{Colors.RESET}")
        ping_error()
        return 1
    except KeyboardInterrupt:
        set_current_process(None)  # v0.6: Clear process tracking
        stop_voice_monitor()  # v0.6: Stop voice monitor
        print(f"\n\n{Colors.YELLOW}Interrupted.{Colors.RESET}")
        return 130


def offer_fallback(transcript: str, timing_report: TimingReport = None) -> bool:
    """
    Offer to run transcript as plain command when no grimoire match found.

    Returns True if command was executed, False if user declined.
    """
    if not FALLBACK_ENABLED:
        return False

    # Auto-accept if AUTO_PLAIN is enabled
    if AUTO_PLAIN:
        execute_plain_command(transcript, timing_report)
        return True

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
    print(f"{Colors.DIM}\"{get_meridian_quote()}\"{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 50}{Colors.RESET}")

    # Startup warmup (parallel)
    startup_warmup(show_progress=True)

    commands = list_commands()
    print(f"\n{Colors.CYAN}Loaded {len(commands)} incantations.{Colors.RESET}")

    # Show project context
    from config import get_config
    ctx = get_config().project_path
    if ctx:
        print(f"{Colors.GREEN}Context:{Colors.RESET} {ctx}")
    else:
        print(f"{Colors.DIM}Context: (current directory){Colors.RESET}")

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

        # v0.6: Log to session context for multi-turn memory
        agent = route_command(command)
        log_session(
            phrase=command['phrase'],
            agent_type=agent.agent_type.value,
            success=(return_code == 0),
            conversation_id=conversation_id,
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
    print(f"{Colors.DIM}\"{get_meridian_quote()}\"{Colors.RESET}")
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

            # Transcribe with timing
            stt_timer = timing.timer("STT")
            stt_timer.start()

            if LIVE_ENDPOINTING_MODE:
                # Live streaming mode: stream audio to Deepgram, stop when speech ends
                print(f"{Colors.BLUE}Recording... (speak, then pause){Colors.RESET}")
                from streaming_stt import transcribe_live_with_endpointing
                from config import get_config
                api_key = get_config().deepgram_api_key or os.environ.get("DEEPGRAM_API_KEY")
                transcript = transcribe_live_with_endpointing(
                    audio_stream=stream,
                    frame_length=frame_length,
                    api_key=api_key,
                    endpointing_ms=300,
                    max_duration=30.0,
                )
                stt_success = bool(transcript)
            else:
                # Fixed duration mode: record for RECORD_SECONDS, then transcribe
                print(f"{Colors.BLUE}Recording... ({RECORD_SECONDS} seconds){Colors.RESET}")
                frames = []
                for _ in range(int(sample_rate / frame_length * RECORD_SECONDS)):
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

                # Transcribe
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


# Available grimoires with metadata
GRIMOIRES = {
    "1": {
        "file": "vanilla.yaml",
        "name": "Simple",
        "desc": "Plain commands (run tests, deploy, etc.)",
        "example": "run tests",
    },
    "2": {
        "file": "commands.yaml",
        "name": "Blood Meridian",
        "desc": "Cormac McCarthy's literary phrases",
        "example": "the judge smiled",
    },
    "3": {
        "file": "dune.yaml",
        "name": "Dune",
        "desc": "Frank Herbert's desert power",
        "example": "the spice must flow",
    },
}


def select_grimoire() -> str:
    """
    Interactive grimoire selection.

    Returns:
        Selected grimoire filename (e.g., 'vanilla.yaml')
    """
    print(f"\n{Colors.BOLD}Select your command style:{Colors.RESET}\n")

    for key, info in GRIMOIRES.items():
        print(f"  {Colors.CYAN}[{key}]{Colors.RESET} {Colors.BOLD}{info['name']}{Colors.RESET}")
        print(f"      {Colors.DIM}{info['desc']}{Colors.RESET}")
        print(f"      Example: \"{Colors.YELLOW}{info['example']}{Colors.RESET}\"\n")

    while True:
        try:
            choice = input(f"{Colors.BOLD}Enter choice [1/2/3]:{Colors.RESET} ").strip()
            if choice in GRIMOIRES:
                selected = GRIMOIRES[choice]
                print(f"\n{Colors.GREEN}✓{Colors.RESET} Selected: {selected['name']}")
                return selected["file"]
            elif choice == "":
                # Default to Simple
                print(f"\n{Colors.GREEN}✓{Colors.RESET} Selected: Simple (default)")
                return "vanilla.yaml"
            else:
                print(f"{Colors.YELLOW}Please enter 1, 2, or 3{Colors.RESET}")
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Colors.GREEN}✓{Colors.RESET} Selected: Simple (default)")
            return "vanilla.yaml"


def save_grimoire_choice(grimoire_file: str):
    """Save grimoire selection to config."""
    from config import get_config, reload_config
    config = get_config()
    config.set("grimoire", "file", grimoire_file)
    config.save()
    reload_config()


def run_setup_wizard():
    """
    Interactive setup wizard for first-time users.

    Checks dependencies, prompts for API keys, tests the pipeline.
    """
    print(f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   {Colors.BOLD}SUZERAIN SETUP WIZARD{Colors.RESET}{Colors.CYAN}                               ║
║   Let's get you configured                               ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝{Colors.RESET}
""")

    from config import get_config, CONFIG_DIR
    config = get_config()
    all_checks_passed = True

    # === Step 1: Check Claude CLI ===
    print(f"{Colors.BOLD}Step 1/4: Checking Claude CLI{Colors.RESET}")
    print(f"{Colors.DIM}─────────────────────────────────────{Colors.RESET}")

    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip().split('\n')[0]
            print(f"  {Colors.GREEN}✓{Colors.RESET} Claude CLI installed: {version}")
        else:
            print(f"  {Colors.RED}✗{Colors.RESET} Claude CLI not working")
            print(f"    {Colors.DIM}Install: npm install -g @anthropic-ai/claude-code{Colors.RESET}")
            all_checks_passed = False
    except FileNotFoundError:
        print(f"  {Colors.RED}✗{Colors.RESET} Claude CLI not found")
        print(f"    {Colors.DIM}Install: npm install -g @anthropic-ai/claude-code{Colors.RESET}")
        all_checks_passed = False
    except subprocess.TimeoutExpired:
        print(f"  {Colors.YELLOW}?{Colors.RESET} Claude CLI timed out")
        all_checks_passed = False

    print()

    # === Step 2: Deepgram API Key ===
    print(f"{Colors.BOLD}Step 2/4: Deepgram API Key (required for voice){Colors.RESET}")
    print(f"{Colors.DIM}─────────────────────────────────────{Colors.RESET}")

    existing_deepgram = config.deepgram_api_key
    if existing_deepgram:
        masked = existing_deepgram[:8] + "..." + existing_deepgram[-4:] if len(existing_deepgram) > 12 else "***"
        print(f"  {Colors.GREEN}✓{Colors.RESET} Already configured: {masked}")
        print(f"    {Colors.DIM}Press Enter to keep, or paste new key to replace{Colors.RESET}")
    else:
        print(f"  {Colors.YELLOW}!{Colors.RESET} Not configured")
        print(f"    {Colors.DIM}Get free key: https://console.deepgram.com/{Colors.RESET}")

    try:
        new_key = input(f"  {Colors.BOLD}Deepgram API key:{Colors.RESET} ").strip()
        if new_key:
            config.set("deepgram", "api_key", new_key)
            print(f"  {Colors.GREEN}✓{Colors.RESET} Saved")
        elif existing_deepgram:
            print(f"  {Colors.DIM}Keeping existing key{Colors.RESET}")
        else:
            print(f"  {Colors.YELLOW}!{Colors.RESET} Skipped - voice mode won't work without this")
            all_checks_passed = False
    except (EOFError, KeyboardInterrupt):
        print(f"\n  {Colors.DIM}Skipped{Colors.RESET}")
        if not existing_deepgram:
            all_checks_passed = False

    print()

    # === Step 3: Picovoice (Optional) ===
    print(f"{Colors.BOLD}Step 3/4: Picovoice Access Key (optional, for wake word){Colors.RESET}")
    print(f"{Colors.DIM}─────────────────────────────────────{Colors.RESET}")

    existing_pico = config.picovoice_access_key
    if existing_pico:
        masked = existing_pico[:8] + "..." if len(existing_pico) > 8 else "***"
        print(f"  {Colors.GREEN}✓{Colors.RESET} Already configured: {masked}")
        print(f"    {Colors.DIM}Press Enter to keep, or paste new key to replace{Colors.RESET}")
    else:
        print(f"  {Colors.DIM}Not configured (wake word detection won't work){Colors.RESET}")
        print(f"    {Colors.DIM}Get free key: https://console.picovoice.ai/{Colors.RESET}")
        print(f"    {Colors.DIM}Skip this if you only want push-to-talk mode{Colors.RESET}")

    try:
        new_key = input(f"  {Colors.BOLD}Picovoice key (Enter to skip):{Colors.RESET} ").strip()
        if new_key:
            config.set("picovoice", "access_key", new_key)
            print(f"  {Colors.GREEN}✓{Colors.RESET} Saved")
        elif existing_pico:
            print(f"  {Colors.DIM}Keeping existing key{Colors.RESET}")
        else:
            print(f"  {Colors.DIM}Skipped - wake word won't work, but push-to-talk will{Colors.RESET}")
    except (EOFError, KeyboardInterrupt):
        print(f"\n  {Colors.DIM}Skipped{Colors.RESET}")

    print()

    # === Step 4: Select Grimoire ===
    print(f"{Colors.BOLD}Step 4/4: Choose your command style{Colors.RESET}")
    print(f"{Colors.DIM}─────────────────────────────────────{Colors.RESET}")

    grimoire_file = select_grimoire()
    config.set("grimoire", "file", grimoire_file)

    print()

    # === Save Configuration ===
    print(f"{Colors.BOLD}Saving configuration...{Colors.RESET}")
    print(f"{Colors.DIM}─────────────────────────────────────{Colors.RESET}")

    try:
        config.save()
        print(f"  {Colors.GREEN}✓{Colors.RESET} Config saved to {CONFIG_DIR}/config.yaml")
    except Exception as e:
        print(f"  {Colors.RED}✗{Colors.RESET} Failed to save: {e}")
        all_checks_passed = False

    print()

    # === Test Pipeline ===
    print(f"{Colors.BOLD}Testing grimoire parser...{Colors.RESET}")
    print(f"{Colors.DIM}─────────────────────────────────────{Colors.RESET}")

    try:
        # Reload grimoire after config change
        from parser import reload_grimoire
        reload_grimoire()

        # Pick a test phrase based on grimoire
        test_phrases = {
            "vanilla.yaml": "run tests",
            "commands.yaml": "the judge smiled",
            "dune.yaml": "the spice must flow",
        }
        test_phrase = test_phrases.get(grimoire_file, "run tests")

        matches = match_top_n(test_phrase, n=1)
        if matches:
            match_result, score = matches[0]
            # Handle both dict (full match) and string (phrase only) returns
            if isinstance(match_result, dict):
                matched_phrase = match_result.get("phrase", str(match_result))
            else:
                matched_phrase = str(match_result)
            print(f"  {Colors.GREEN}✓{Colors.RESET} Parser working: \"{test_phrase}\" → \"{matched_phrase}\" ({score:.0f}%)")
        else:
            print(f"  {Colors.YELLOW}?{Colors.RESET} No match for \"{test_phrase}\"")
    except Exception as e:
        print(f"  {Colors.RED}✗{Colors.RESET} Parser error: {e}")
        all_checks_passed = False

    print()

    # === Summary ===
    print(f"{Colors.DIM}═══════════════════════════════════════════════════════════{Colors.RESET}")

    if all_checks_passed:
        print(f"""
{Colors.GREEN}✓ Setup complete!{Colors.RESET}

{Colors.BOLD}Try these commands:{Colors.RESET}
  suzerain --list            See all available commands
  suzerain --test --sandbox  Practice without executing
  suzerain --test            Type commands to execute
  suzerain                   Voice mode (push-to-talk)
""")
    else:
        print(f"""
{Colors.YELLOW}! Setup partially complete{Colors.RESET}

Some features may not work. Run {Colors.BOLD}suzerain --setup{Colors.RESET} again to fix.

{Colors.BOLD}What you can do now:{Colors.RESET}
  suzerain --list            See all available commands
  suzerain --test --sandbox  Practice without executing
""")

    return all_checks_passed


def show_welcome(first_run: bool = False):
    """Show the welcome/quick start guide."""
    version = "0.1.2"
    print(f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   {Colors.BOLD}SUZERAIN v{version}{Colors.RESET}{Colors.CYAN}                                       ║
║   Voice-activated Claude Code                            ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝{Colors.RESET}
""")

    # Grimoire selection on first run
    if first_run:
        grimoire_file = select_grimoire()
        save_grimoire_choice(grimoire_file)
        print()

    # Get current grimoire info
    from config import get_config
    current_grimoire = get_config().grimoire_file or "vanilla.yaml"
    grimoire_name = next(
        (g["name"] for g in GRIMOIRES.values() if g["file"] == current_grimoire),
        "Custom"
    )
    example_cmd = next(
        (g["example"] for g in GRIMOIRES.values() if g["file"] == current_grimoire),
        "run tests"
    )

    print(f"""{Colors.BOLD}Quick Start:{Colors.RESET}
  suzerain --list            See all incantations
  suzerain --test --sandbox  Try commands without executing
  suzerain --test            Type commands to execute
  suzerain                   Voice mode (push-to-talk)

{Colors.BOLD}Current Grimoire:{Colors.RESET} {grimoire_name}
  {Colors.DIM}Change with: suzerain --grimoire{Colors.RESET}

{Colors.BOLD}Requirements:{Colors.RESET}
  {Colors.DIM}•{Colors.RESET} Claude Code CLI    {Colors.DIM}npm install -g @anthropic-ai/claude-code{Colors.RESET}
  {Colors.DIM}•{Colors.RESET} Deepgram API key   {Colors.DIM}export DEEPGRAM_API_KEY='...' (voice only){Colors.RESET}

{Colors.BOLD}Try it now:{Colors.RESET}
  {Colors.GREEN}suzerain --test --sandbox{Colors.RESET}
  {Colors.DIM}Then type:{Colors.RESET} {Colors.YELLOW}{example_cmd}{Colors.RESET}

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
        default=True,
        help="Pre-warm Claude connection on startup (default: enabled)"
    )
    parser.add_argument(
        "--no-warm",
        action="store_true",
        help="Disable pre-warming Claude connection on startup"
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
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run interactive setup wizard (configure API keys, check dependencies)"
    )
    parser.add_argument(
        "--grimoire", "-g",
        action="store_true",
        help="Change grimoire (command style)"
    )
    parser.add_argument(
        "--auto-plain",
        action="store_true",
        help="Auto-accept plain commands without y/N confirmation"
    )
    parser.add_argument(
        "--dangerous",
        action="store_true",
        default=True,
        help="Skip Claude permission prompts (default: enabled)"
    )
    parser.add_argument(
        "--safe",
        action="store_true",
        help="Enable Claude permission prompts (disables --dangerous)"
    )
    parser.add_argument(
        "--streaming",
        action="store_true",
        default=True,
        help="Use streaming STT (WebSocket) for lower latency (default: enabled)"
    )
    parser.add_argument(
        "--no-streaming",
        action="store_true",
        help="Use batch HTTP STT instead of streaming WebSocket"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Stream audio live to Deepgram, stop when speech ends (saves 1-4s per command)"
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Disable spoken summaries (v0.4 feature)"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use local Whisper for STT (no API, works offline)"
    )
    parser.add_argument(
        "--local-model",
        type=str,
        choices=["tiny.en", "base.en", "small.en", "medium.en"],
        default=None,
        help="Whisper model size for local STT (implies --local, default: small.en)"
    )
    parser.add_argument(
        "--context",
        type=str,
        metavar="PATH",
        help="Set sticky project context (all commands run in this directory)"
    )
    parser.add_argument(
        "--show-context",
        action="store_true",
        help="Show current project context and exit"
    )
    parser.add_argument(
        "--clear-context",
        action="store_true",
        help="Clear sticky project context"
    )
    parser.add_argument(
        "--no-monitor",
        action="store_true",
        help="Disable background voice monitoring during execution (v0.6 feature)"
    )
    parser.add_argument(
        "--trust",
        type=int,
        choices=[1, 2, 3, 4, 5],
        default=None,
        metavar="LEVEL",
        help="Trust level 1-5: 1=preview, 2=explicit, 3=supervised (default), 4=assisted, 5=autonomous"
    )

    args = parser.parse_args()

    # Change grimoire selection
    if args.grimoire:
        grimoire_file = select_grimoire()
        save_grimoire_choice(grimoire_file)
        print(f"\n{Colors.DIM}Grimoire saved. Run 'suzerain --list' to see commands.{Colors.RESET}")
        return

    # Run setup wizard
    if args.setup:
        run_setup_wizard()
        return

    # Context management
    from config import get_config
    cfg = get_config()

    if args.show_context:
        ctx = cfg.project_path
        if ctx:
            print(f"{Colors.GREEN}Current context:{Colors.RESET} {ctx}")
        else:
            print(f"{Colors.DIM}No context set. Commands run in current directory.{Colors.RESET}")
            print(f"{Colors.DIM}Set with: suzerain --context /path/to/project{Colors.RESET}")
        return

    if args.clear_context:
        cfg.clear_project_path()
        print(f"{Colors.GREEN}Context cleared.{Colors.RESET} Commands will run in current directory.")
        return

    if args.context:
        try:
            cfg.set_project_path(args.context)
            print(f"{Colors.GREEN}Context set:{Colors.RESET} {cfg.project_path}")
            print(f"{Colors.DIM}All commands will now run in this directory.{Colors.RESET}")
        except ValueError as e:
            print(f"{Colors.RED}Error:{Colors.RESET} {e}")
            sys.exit(1)
        return

    # Show welcome on first run or if explicitly requested
    if args.welcome:
        show_welcome(first_run=False)
        return

    if is_first_run():
        run_setup_wizard()
        mark_first_run_complete()
        return

    # Set global flags FIRST (before any early exits)
    global SANDBOX_MODE, TIMING_MODE, RETRY_ENABLED, FALLBACK_ENABLED, WARM_MODE, AUTO_PLAIN, DANGEROUS_MODE
    global STREAMING_STT_MODE, LIVE_ENDPOINTING_MODE, SUMMARY_ENABLED, LOCAL_STT_MODE, LOCAL_STT_MODEL
    global VOICE_MONITOR_ENABLED
    SANDBOX_MODE = args.sandbox
    TIMING_MODE = args.timing
    WARM_MODE = args.warm and not args.no_warm  # --no-warm overrides --warm
    AUTO_PLAIN = args.auto_plain
    DANGEROUS_MODE = args.dangerous and not args.safe  # --safe overrides
    STREAMING_STT_MODE = args.streaming and not args.no_streaming  # --no-streaming overrides
    LIVE_ENDPOINTING_MODE = args.live  # Stream audio live, stop when speech ends
    # v0.5: Local Whisper STT - CLI flags override config
    from config import get_config
    config = get_config()
    # --local-model implies --local
    LOCAL_STT_MODE = args.local or args.local_model is not None or config.local_stt_enabled
    # Priority: CLI model > config model > default
    LOCAL_STT_MODEL = args.local_model or config.local_stt_model or "small.en"
    if args.no_retry:
        RETRY_ENABLED = False
    if args.no_fallback:
        FALLBACK_ENABLED = False
    if args.no_summary:
        SUMMARY_ENABLED = False
    if args.no_monitor:
        VOICE_MONITOR_ENABLED = False

    # v0.6: Trust level - CLI overrides config
    global TRUST_LEVEL
    if args.trust is not None:
        TRUST_LEVEL = args.trust
    else:
        TRUST_LEVEL = config.trust_level

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

    # Show trust level if not default
    if TRUST_LEVEL != TrustLevel.SUPERVISED:
        color = Colors.GREEN if TRUST_LEVEL >= TrustLevel.ASSISTED else Colors.YELLOW
        print(f"{color}{'=' * 50}{Colors.RESET}")
        print(f"{color}   TRUST: {TrustLevel.description(TRUST_LEVEL)}{Colors.RESET}")
        print(f"{color}{'=' * 50}{Colors.RESET}\n")

    if args.warm:
        print(f"{Colors.BLUE}{'=' * 50}{Colors.RESET}")
        print(f"{Colors.BLUE}   WARM MODE - Pre-warming Claude connection{Colors.RESET}")
        print(f"{Colors.BLUE}{'=' * 50}{Colors.RESET}\n")

    if args.streaming:
        print(f"{Colors.GREEN}{'=' * 50}{Colors.RESET}")
        print(f"{Colors.GREEN}   STREAMING STT - WebSocket for lower latency{Colors.RESET}")
        print(f"{Colors.GREEN}{'=' * 50}{Colors.RESET}\n")

    if args.test:
        test_mode()
    else:
        listen_mode(once=args.once, use_wake_word=args.wake, wake_keyword=args.keyword)


if __name__ == "__main__":
    main()
