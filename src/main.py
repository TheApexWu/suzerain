"""
Suzerain - Voice-activated Claude Code with literary macros.

"Whatever exists without my knowledge exists without my consent."

Usage:
    python src/main.py              # Run with push-to-talk
    python src/main.py --test       # Test mode (type phrases)
    python src/main.py --list       # List all grimoire commands
    python src/main.py --validate   # Validate grimoire structure
    python src/main.py --timing     # Show latency breakdown
    python src/main.py --sandbox    # Dry run mode (no execution)
"""

import argparse
import subprocess
import sys
import os
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from parser import (
    match,
    match_top_n,
    extract_modifiers,
    expand_command,
    load_grimoire,
    list_commands,
    list_modifiers,
    validate_grimoire,
    get_command_info
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

    def display(self):
        if not TIMING_MODE:
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

# === Audio Dependencies (optional) ===
try:
    import pyaudio
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

# simpleaudio disabled - crashes on macOS Apple Silicon
# TODO: Replace with alternative (e.g., sounddevice, pygame.mixer)
AUDIO_FEEDBACK = False


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


# === Audio Feedback ===

def ping(freq: int = 800, duration_ms: int = 100):
    """Play a confirmation tone."""
    if not AUDIO_FEEDBACK:
        return

    try:
        import numpy as np
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


def _redact_sensitive(text: str, api_key: str) -> str:
    """Redact API key and other sensitive data from error messages."""
    if api_key:
        text = text.replace(api_key, "[REDACTED]")
    # Also redact partial key matches (in case of truncation)
    if api_key and len(api_key) > 8:
        text = text.replace(api_key[:8], "[REDACTED]")
    return text


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
        print(f"{Colors.RED}Error: DEEPGRAM_API_KEY not set{Colors.RESET}")
        return ""

    if not _validate_api_key(api_key):
        print(f"{Colors.RED}Error: DEEPGRAM_API_KEY appears invalid (check format){Colors.RESET}")
        return ""

    # Base URL with model and formatting
    url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true"

    # Add keyword boosting for grimoire terms
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
        # HTTP errors might contain auth info in headers - redact
        error_msg = _redact_sensitive(str(e), api_key)
        print(f"{Colors.RED}Transcription HTTP error: {error_msg}{Colors.RESET}")
        return ""
    except urllib.error.URLError as e:
        # URL errors are usually network issues, less likely to leak
        print(f"{Colors.RED}Transcription network error: {e.reason}{Colors.RESET}")
        return ""
    except Exception as e:
        # Generic fallback - always redact
        error_msg = _redact_sensitive(str(e), api_key)
        print(f"{Colors.RED}Transcription error: {error_msg}{Colors.RESET}")
        return ""


# === Command Execution ===

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


def execute_command(command: dict, modifiers: list, dry_run: bool = False, timing_report: TimingReport = None) -> int:
    """
    Execute a matched grimoire command.

    Expands the literary phrase into a full prompt and sends to Claude.
    """
    info = get_command_info(command)

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
            return 1

    # Expand the command
    expansion = expand_command(command, modifiers)

    print(f"\n{Colors.DIM}{'─' * 50}{Colors.RESET}")
    print(f"{Colors.GREEN}Incantation:{Colors.RESET} \"{Colors.BOLD}{command['phrase']}{Colors.RESET}\"")
    if modifiers:
        print(f"{Colors.MAGENTA}Modifiers:{Colors.RESET} {[m['effect'] for m in modifiers]}")
    print(f"{Colors.DIM}{'─' * 50}{Colors.RESET}")

    if dry_run:
        print(f"\n{Colors.YELLOW}[DRY RUN - Showing expansion only]{Colors.RESET}\n")
        print(f"{Colors.DIM}{expansion}{Colors.RESET}")
        print(f"\n{Colors.DIM}{'─' * 50}{Colors.RESET}")
        return 0

    # Handle --continue flag
    if info.get("use_continue"):
        cmd = ["claude", "--continue", "-p", expansion, "--verbose", "--output-format", "stream-json"]
    else:
        cmd = ["claude", "-p", expansion, "--verbose", "--output-format", "stream-json"]

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
            print(f"{Colors.GREEN}✓ Complete{Colors.RESET}")
            ping_success()
        else:
            print(f"{Colors.RED}✗ Failed (exit code {process.returncode}){Colors.RESET}")
            ping_error()

        # Show timing report if enabled
        if timing_report:
            timing_report.display()

        return process.returncode

    except FileNotFoundError:
        print(f"{Colors.RED}Error: 'claude' command not found. Is Claude Code installed?{Colors.RESET}")
        ping_error()
        return 1
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Interrupted.{Colors.RESET}")
        return 130


# === Modes ===

def test_mode():
    """
    Test mode: type phrases instead of speaking.
    """
    print(f"{Colors.BOLD}{'=' * 50}{Colors.RESET}")
    print(f"{Colors.GREEN}SUZERAIN TEST MODE{Colors.RESET}")
    print(f"{Colors.DIM}Type grimoire phrases. Commands: quit, list, help{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 50}{Colors.RESET}")

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
        elif text.lower() == "help":
            print(f"\n{Colors.BOLD}Commands:{Colors.RESET}")
            print(f"  {Colors.CYAN}list{Colors.RESET}     - Show all grimoire phrases")
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
        execute_command(command, modifiers, timing_report=timing)


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

            # Transcribe with timing
            stt_timer = timing.timer("STT")
            stt_timer.start()
            transcript = transcribe_audio(audio_data)
            stt_timer.stop()

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
                    execute_command(command, modifiers, timing_report=timing)
                else:
                    print(f"{Colors.RED}No grimoire match.{Colors.RESET}")
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
            print(f"    ⚠️  Requires confirmation")

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
        print(f"\n✓ Grimoire valid")
        print(f"  {len(commands)} commands")
        print(f"  {len(modifiers)} modifiers")
        return 0


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
        help="Show latency breakdown: Wake word, STT, Parse, Claude execution"
    )

    args = parser.parse_args()

    if args.validate:
        sys.exit(validate_mode())

    if args.list:
        show_commands()
        return

    # Set global sandbox mode
    global SANDBOX_MODE
    SANDBOX_MODE = args.sandbox

    # Set global timing mode
    global TIMING_MODE
    TIMING_MODE = args.timing

    if args.timing:
        print(f"{Colors.CYAN}{'=' * 50}{Colors.RESET}")
        print(f"{Colors.CYAN}   TIMING MODE - Latency breakdown enabled{Colors.RESET}")
        print(f"{Colors.CYAN}{'=' * 50}{Colors.RESET}\n")

    if args.sandbox:
        print(f"{Colors.YELLOW}{'=' * 50}{Colors.RESET}")
        print(f"{Colors.YELLOW}   SANDBOX MODE - No commands will execute{Colors.RESET}")
        print(f"{Colors.YELLOW}{'=' * 50}{Colors.RESET}\n")

    if args.test:
        test_mode()
    else:
        listen_mode(once=args.once, use_wake_word=args.wake, wake_keyword=args.keyword)


if __name__ == "__main__":
    main()
