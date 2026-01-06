"""
Wake Word Detection - Porcupine integration for hands-free activation.

"He never sleeps, the judge. He is dancing, dancing."

Usage:
    # Blocking wait for wake word
    wait_for_wake_word()

    # Or use in a loop
    detector = WakeWordDetector()
    while True:
        if detector.process_frame(audio_frame):
            print("Wake word detected!")
"""

import os
import struct

# Porcupine is optional
try:
    import pvporcupine
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False


# Built-in keywords available in free tier
BUILTIN_KEYWORDS = [
    "alexa", "americano", "blueberry", "bumblebee", "computer",
    "grapefruit", "grasshopper", "hey google", "hey siri", "jarvis",
    "ok google", "picovoice", "porcupine", "terminator"
]

# Default wake word - "computer" is nice and neutral
DEFAULT_KEYWORD = "computer"


class WakeWordDetector:
    """
    Lightweight wake word detector using Porcupine.

    Free tier supports built-in keywords only.
    For custom wake words, need Porcupine Console account.
    """

    def __init__(self, keyword: str = DEFAULT_KEYWORD, access_key: str = None):
        """
        Initialize wake word detector.

        Args:
            keyword: Built-in keyword to detect (default: "computer")
            access_key: Picovoice access key. Uses PICOVOICE_ACCESS_KEY env var if not provided.
        """
        if not PORCUPINE_AVAILABLE:
            raise ImportError("pvporcupine not installed. Run: pip install pvporcupine")

        self.access_key = access_key or os.environ.get("PICOVOICE_ACCESS_KEY")
        if not self.access_key:
            raise ValueError(
                "Picovoice access key required. "
                "Get free key at https://console.picovoice.ai/ "
                "then set PICOVOICE_ACCESS_KEY environment variable."
            )

        if keyword.lower() not in [k.lower() for k in BUILTIN_KEYWORDS]:
            raise ValueError(
                f"Unknown keyword '{keyword}'. "
                f"Available: {', '.join(BUILTIN_KEYWORDS)}"
            )

        self.keyword = keyword
        self.porcupine = pvporcupine.create(
            access_key=self.access_key,
            keywords=[keyword]
        )

        # Audio parameters required by Porcupine
        self.sample_rate = self.porcupine.sample_rate  # 16000
        self.frame_length = self.porcupine.frame_length  # 512

    def process_frame(self, pcm_frame: bytes) -> bool:
        """
        Process a single audio frame.

        Args:
            pcm_frame: Raw PCM audio (16-bit signed, mono, 16kHz)
                       Must be exactly frame_length samples.

        Returns:
            True if wake word detected, False otherwise
        """
        # Convert bytes to int16 array
        pcm = struct.unpack_from(f"{self.frame_length}h", pcm_frame)

        # Process and check for wake word
        keyword_index = self.porcupine.process(pcm)
        return keyword_index >= 0

    def cleanup(self):
        """Release resources."""
        if hasattr(self, 'porcupine') and self.porcupine:
            self.porcupine.delete()
            self.porcupine = None

    def __del__(self):
        self.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cleanup()


def wait_for_wake_word(keyword: str = DEFAULT_KEYWORD, timeout: float = None) -> bool:
    """
    Block until wake word is detected.

    Args:
        keyword: Built-in keyword to listen for
        timeout: Maximum seconds to wait (None = forever)

    Returns:
        True if wake word detected, False if timeout
    """
    if not PYAUDIO_AVAILABLE:
        raise ImportError("pyaudio not installed")

    import time
    start_time = time.time()

    with WakeWordDetector(keyword) as detector:
        pa = pyaudio.PyAudio()

        stream = pa.open(
            rate=detector.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=detector.frame_length
        )

        try:
            while True:
                # Check timeout
                if timeout and (time.time() - start_time) > timeout:
                    return False

                # Read audio frame
                pcm = stream.read(detector.frame_length, exception_on_overflow=False)

                # Check for wake word
                if detector.process_frame(pcm):
                    return True

        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()


def check_setup() -> dict:
    """
    Check wake word setup status.

    Returns:
        Dict with status info
    """
    status = {
        "porcupine_installed": PORCUPINE_AVAILABLE,
        "pyaudio_installed": PYAUDIO_AVAILABLE,
        "access_key_set": bool(os.environ.get("PICOVOICE_ACCESS_KEY")),
        "ready": False,
        "message": ""
    }

    if not PORCUPINE_AVAILABLE:
        status["message"] = "Install pvporcupine: pip install pvporcupine"
    elif not PYAUDIO_AVAILABLE:
        status["message"] = "Install pyaudio: pip install pyaudio"
    elif not status["access_key_set"]:
        status["message"] = (
            "Get free access key at https://console.picovoice.ai/\n"
            "Then: export PICOVOICE_ACCESS_KEY='your-key-here'"
        )
    else:
        status["ready"] = True
        status["message"] = f"Ready! Available keywords: {', '.join(BUILTIN_KEYWORDS)}"

    return status


# === CLI Test ===

if __name__ == "__main__":
    import sys

    print("=" * 50)
    print("WAKE WORD DETECTOR TEST")
    print("=" * 50)

    status = check_setup()

    if not status["ready"]:
        print(f"\nSetup incomplete:\n{status['message']}")
        sys.exit(1)

    keyword = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_KEYWORD
    print(f"\nListening for '{keyword}'...")
    print("(Ctrl+C to exit)\n")

    try:
        if wait_for_wake_word(keyword):
            print(f"\n*** '{keyword.upper()}' DETECTED! ***\n")
    except KeyboardInterrupt:
        print("\nExiting.")
