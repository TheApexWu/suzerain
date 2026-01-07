"""
Audio Feedback Module for Suzerain.

Provides distinct sounds for different events and voice response capabilities.

"The man who believes in nothing still believes in that."

Features:
- SOUND_MAP: Distinct sounds for different events
- Spinner: Visual feedback with elapsed time during long operations
- RecordingIndicator: Live timer while recording
- speak_summary: Voice response using macOS 'say' command
"""

import os
import subprocess
import sys
import time
import threading


# === Sound Configuration ===

# macOS system sounds for different events
SOUND_MAP = {
    "wake_word": "/System/Library/Sounds/Tink.aiff",       # Short ping - wake word detected
    "recording_start": "/System/Library/Sounds/Pop.aiff",  # Subtle beep - recording started
    "command_matched": "/System/Library/Sounds/Glass.aiff", # Confirmation - command recognized
    "success": "/System/Library/Sounds/Glass.aiff",        # Success tone
    "error": "/System/Library/Sounds/Basso.aiff",          # Error tone
    "processing": "/System/Library/Sounds/Morse.aiff",     # Processing indicator
}


def play_sound(event: str) -> bool:
    """
    Play a sound for a specific event using afplay.

    Args:
        event: One of the SOUND_MAP keys:
            - "wake_word": Short ping when wake word detected
            - "recording_start": Subtle beep when recording starts
            - "command_matched": Confirmation when command recognized
            - "success": Success tone when command completes
            - "error": Error tone when command fails
            - "processing": Processing indicator

    Returns:
        True if sound played, False otherwise
    """
    sound_path = SOUND_MAP.get(event)
    if not sound_path or not os.path.exists(sound_path):
        return False

    try:
        subprocess.Popen(
            ["afplay", sound_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except Exception:
        return False


# === ANSI Colors (minimal subset for this module) ===

class _Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BLUE = "\033[34m"
    RED = "\033[31m"

    @classmethod
    def disable(cls):
        """Disable colors."""
        cls.RESET = ""
        cls.BLUE = ""
        cls.RED = ""


# Disable colors if not a TTY
if not sys.stdout.isatty():
    _Colors.disable()


# === Spinner for Long Operations ===

class Spinner:
    """
    Unicode spinner for visual feedback during long operations.
    Shows elapsed time while spinning.

    Usage:
        spinner = Spinner("Executing")
        spinner.start()
        # ... long operation ...
        elapsed = spinner.stop()
        print(f"Took {elapsed:.1f}s")
    """

    # Braille spinner characters that work in most terminals
    FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, message: str = "Processing"):
        """
        Initialize spinner.

        Args:
            message: Message to display next to spinner
        """
        self.message = message
        self.running = False
        self.thread = None
        self.start_time = None

    def _spin(self):
        """Internal spinner loop."""
        frame_idx = 0
        while self.running:
            elapsed = time.time() - self.start_time
            frame = self.FRAMES[frame_idx % len(self.FRAMES)]
            # Use carriage return to update in place
            sys.stdout.write(f"\r{_Colors.BLUE}{frame}{_Colors.RESET} {self.message}... [{elapsed:.1f}s]  ")
            sys.stdout.flush()
            frame_idx += 1
            time.sleep(0.1)
        # Clear the spinner line when done
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.flush()

    def start(self):
        """Start the spinner."""
        self.running = True
        self.start_time = time.time()
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()

    def stop(self) -> float:
        """
        Stop the spinner.

        Returns:
            Elapsed time in seconds
        """
        self.running = False
        elapsed = time.time() - self.start_time if self.start_time else 0
        if self.thread:
            self.thread.join(timeout=0.5)
        return elapsed


class RecordingIndicator:
    """
    Shows recording status with live timer.
    Displays: "Recording... [2.3s]"

    Usage:
        indicator = RecordingIndicator()
        indicator.start()
        # ... recording ...
        duration = indicator.stop()
        print(f"Recorded {duration:.1f}s")
    """

    def __init__(self):
        self.running = False
        self.thread = None
        self.start_time = None

    def _update(self):
        """Internal update loop."""
        while self.running:
            elapsed = time.time() - self.start_time
            # Red dot + recording message + timer
            sys.stdout.write(f"\r{_Colors.RED}●{_Colors.RESET} Recording... [{elapsed:.1f}s]  ")
            sys.stdout.flush()
            time.sleep(0.1)
        # Clear the line when done
        sys.stdout.write("\r" + " " * 40 + "\r")
        sys.stdout.flush()

    def start(self):
        """Start the recording indicator."""
        self.running = True
        self.start_time = time.time()
        # Play recording start sound
        play_sound("recording_start")
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    def stop(self) -> float:
        """
        Stop the recording indicator.

        Returns:
            Elapsed time in seconds
        """
        self.running = False
        elapsed = time.time() - self.start_time if self.start_time else 0
        if self.thread:
            self.thread.join(timeout=0.5)
        return elapsed


# === Voice Response ===

# Global flag - set to True to enable voice responses
SPEAK_MODE = False


def set_speak_mode(enabled: bool):
    """Enable or disable voice responses."""
    global SPEAK_MODE
    SPEAK_MODE = enabled


def speak_summary(text: str):
    """
    Use macOS 'say' command to speak a brief summary.
    Only active when SPEAK_MODE is True.

    Args:
        text: Text to speak (should be brief)
    """
    if not SPEAK_MODE:
        return

    # Limit to reasonable length
    if len(text) > 200:
        text = text[:200] + "..."

    try:
        subprocess.Popen(
            ["say", "-r", "200", text],  # -r 200 = slightly faster speech rate
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass  # Silent fail if say command not available


def extract_summary_from_result(result_text: str) -> str:
    """
    Extract a brief spoken summary from Claude's result.
    Looks for test results, success messages, etc.

    Args:
        result_text: The full result text from Claude

    Returns:
        A brief summary suitable for speech (e.g., "Tests passed. 107 of 107.")
    """
    import re

    # Pattern: "X passed" or "X of Y passed"
    test_match = re.search(r'(\d+)\s*(?:of\s*(\d+)\s*)?(?:tests?\s*)?passed', result_text, re.IGNORECASE)
    if test_match:
        passed = test_match.group(1)
        total = test_match.group(2) or passed
        return f"Tests passed. {passed} of {total}."

    # Pattern: "X tests failed"
    fail_match = re.search(r'(\d+)\s*tests?\s*failed', result_text, re.IGNORECASE)
    if fail_match:
        failed = fail_match.group(1)
        return f"Warning. {failed} tests failed."

    # Pattern: deployment or build success
    if re.search(r'deploy(ed|ment)?\s*(complete|success|done)', result_text, re.IGNORECASE):
        return "Deployment complete."

    if re.search(r'build\s*(complete|success|done)', result_text, re.IGNORECASE):
        return "Build complete."

    # Pattern: commit success
    if re.search(r'commit(ted)?\s*(success|complete|done)?', result_text, re.IGNORECASE):
        return "Changes committed."

    # Generic success
    if re.search(r'(success|complete|done|finished)', result_text, re.IGNORECASE):
        return "Task complete."

    # No specific pattern - return generic
    return "Done."


# === Convenience Functions ===

def play_wake_sound():
    """Play sound when wake word is detected."""
    return play_sound("wake_word")


def play_recording_sound():
    """Play sound when recording starts."""
    return play_sound("recording_start")


def play_matched_sound():
    """Play sound when command is matched."""
    return play_sound("command_matched")


def play_success_sound():
    """Play sound when command succeeds."""
    return play_sound("success")


def play_error_sound():
    """Play sound when command fails."""
    return play_sound("error")


# === Test ===

if __name__ == "__main__":
    print("Testing audio feedback module...")
    print()

    # Test sounds
    print("Testing sounds:")
    for event in SOUND_MAP.keys():
        print(f"  Playing: {event}")
        play_sound(event)
        time.sleep(0.5)

    print()

    # Test spinner
    print("Testing spinner (3 seconds):")
    spinner = Spinner("Processing command")
    spinner.start()
    time.sleep(3)
    elapsed = spinner.stop()
    print(f"Spinner ran for {elapsed:.1f}s")

    print()

    # Test recording indicator
    print("Testing recording indicator (2 seconds):")
    indicator = RecordingIndicator()
    indicator.start()
    time.sleep(2)
    duration = indicator.stop()
    print(f"Recording indicator ran for {duration:.1f}s")

    print()

    # Test voice response
    print("Testing voice response:")
    set_speak_mode(True)
    speak_summary("Tests passed. 42 of 42.")
    time.sleep(2)

    print()
    print("Done!")
