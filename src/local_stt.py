"""
Local Speech-to-Text using faster-whisper.

Runs entirely on-device using OpenAI's Whisper model via CTranslate2.
No API calls, no costs, works offline.

"The man who believes in nothing still believes in that."

Performance (Apple Silicon M1/M2/M3):
- small.en model: ~300ms for 5s audio
- base.en model: ~150ms for 5s audio
- tiny.en model: ~80ms for 5s audio
"""

import io
import os
import time
import wave
import threading
from typing import Callable, Optional
import numpy as np

# Lazy load to avoid slow import on startup
_model = None
_model_lock = threading.Lock()


def _get_model(model_size: str = "small.en"):
    """
    Lazy-load the Whisper model.

    Models are downloaded on first use (~150MB for small.en).
    Uses CPU by default (works everywhere), GPU if available.
    """
    global _model

    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel

            # Detect best compute type for the platform
            # For Apple Silicon, use int8 for speed
            compute_type = "int8"
            device = "cpu"  # faster-whisper uses CPU on Mac (Metal not supported yet)

            print(f"[Loading Whisper {model_size}...]", end=" ", flush=True)
            start = time.time()

            _model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
                cpu_threads=4,  # Use multiple cores
            )

            elapsed = time.time() - start
            print(f"done ({elapsed:.1f}s)")

        return _model


def transcribe_audio_local(
    audio_data: bytes,
    model_size: str = "small.en",
    language: str = "en",
) -> str:
    """
    Transcribe audio using local Whisper model.

    Drop-in replacement for Deepgram's transcribe_audio_streaming().

    Args:
        audio_data: WAV audio bytes (16kHz, 16-bit, mono)
        model_size: Whisper model size (tiny.en, base.en, small.en, medium.en)
        language: Language code (default: "en")

    Returns:
        Transcribed text
    """
    model = _get_model(model_size)

    # Parse WAV and extract audio samples
    with wave.open(io.BytesIO(audio_data), 'rb') as wf:
        sample_rate = wf.getframerate()
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        frames = wf.readframes(wf.getnframes())

    # Convert to numpy array
    if sample_width == 2:
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif sample_width == 4:
        audio = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported sample width: {sample_width}")

    # Handle stereo -> mono
    if n_channels == 2:
        audio = audio.reshape(-1, 2).mean(axis=1)

    # Resample to 16kHz if needed (Whisper expects 16kHz)
    if sample_rate != 16000:
        # Simple linear interpolation resampling
        duration = len(audio) / sample_rate
        target_length = int(duration * 16000)
        indices = np.linspace(0, len(audio) - 1, target_length)
        audio = np.interp(indices, np.arange(len(audio)), audio)

    # Transcribe
    segments, info = model.transcribe(
        audio,
        language=language,
        beam_size=5,
        vad_filter=True,  # Filter out non-speech
        vad_parameters=dict(
            min_silence_duration_ms=300,
            speech_pad_ms=100,
        ),
    )

    # Collect transcript
    transcript = " ".join(segment.text.strip() for segment in segments)
    return transcript.strip()


def transcribe_file_local(
    file_path: str,
    model_size: str = "small.en",
    language: str = "en",
) -> str:
    """
    Transcribe an audio file using local Whisper.

    Args:
        file_path: Path to audio file (WAV, MP3, etc.)
        model_size: Whisper model size
        language: Language code

    Returns:
        Transcribed text
    """
    model = _get_model(model_size)

    segments, info = model.transcribe(
        file_path,
        language=language,
        beam_size=5,
        vad_filter=True,
    )

    transcript = " ".join(segment.text.strip() for segment in segments)
    return transcript.strip()


class LocalEndpointingTranscriber:
    """
    Local transcription with voice activity detection.

    Records audio until silence is detected, then transcribes locally.
    Simpler than streaming (no real-time transcription) but very fast.
    """

    def __init__(
        self,
        model_size: str = "small.en",
        silence_threshold: float = 0.01,
        silence_duration_ms: int = 500,
        max_duration: float = 30.0,
        on_speech_start: Optional[Callable[[], None]] = None,
        on_speech_end: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize local transcriber with endpointing.

        Args:
            model_size: Whisper model size
            silence_threshold: RMS threshold below which audio is silence
            silence_duration_ms: How long silence before stopping
            max_duration: Maximum recording time
            on_speech_start: Callback when speech starts
            on_speech_end: Callback when speech ends
        """
        self.model_size = model_size
        self.silence_threshold = silence_threshold
        self.silence_duration_ms = silence_duration_ms
        self.max_duration = max_duration
        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end

        self._audio_buffer = []
        self._is_recording = False
        self._speech_started = False
        self._speech_ended = threading.Event()
        self._silence_start = None
        self._start_time = None

    def start(self):
        """Start recording session."""
        self._audio_buffer = []
        self._is_recording = True
        self._speech_started = False
        self._speech_ended.clear()
        self._silence_start = None
        self._start_time = time.time()

        # Pre-load model in background
        threading.Thread(target=lambda: _get_model(self.model_size), daemon=True).start()

    def feed(self, audio_chunk: bytes):
        """
        Feed audio chunk and detect speech/silence.

        Args:
            audio_chunk: Raw audio bytes (16-bit PCM)
        """
        if not self._is_recording:
            return

        # Store audio
        self._audio_buffer.append(audio_chunk)

        # Calculate RMS for voice activity detection
        audio_array = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32)
        rms = np.sqrt(np.mean(audio_array ** 2)) / 32768.0

        # Check for speech
        is_speech = rms > self.silence_threshold

        if is_speech:
            if not self._speech_started:
                self._speech_started = True
                if self.on_speech_start:
                    self.on_speech_start()
            self._silence_start = None
        else:
            # Track silence duration
            if self._speech_started:
                if self._silence_start is None:
                    self._silence_start = time.time()
                else:
                    silence_ms = (time.time() - self._silence_start) * 1000
                    if silence_ms >= self.silence_duration_ms:
                        # Speech ended
                        self._is_recording = False
                        self._speech_ended.set()
                        if self.on_speech_end:
                            self.on_speech_end()

        # Check max duration
        if time.time() - self._start_time > self.max_duration:
            self._is_recording = False
            self._speech_ended.set()

    def is_recording(self) -> bool:
        """Check if still recording."""
        return self._is_recording

    def stop(self):
        """Manually stop recording."""
        self._is_recording = False
        self._speech_ended.set()

    def get_transcript(self) -> str:
        """
        Get transcript of recorded audio.

        Blocks until recording is complete, then transcribes.
        """
        # Wait for recording to complete
        self._speech_ended.wait(timeout=self.max_duration + 5)

        if not self._audio_buffer:
            return ""

        # Combine audio chunks
        audio_bytes = b''.join(self._audio_buffer)

        # Create WAV in memory
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(audio_bytes)

        wav_data = buffer.getvalue()

        # Transcribe
        return transcribe_audio_local(wav_data, self.model_size)


def transcribe_live_local(
    audio_stream,
    frame_length: int,
    model_size: str = "small.en",
    silence_threshold: float = 0.01,
    silence_duration_ms: int = 500,
    max_duration: float = 30.0,
    on_interim: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Transcribe live audio with automatic endpointing (local version).

    Drop-in replacement for transcribe_live_with_endpointing().

    Args:
        audio_stream: PyAudio stream to read from
        frame_length: Samples per frame
        model_size: Whisper model size
        silence_threshold: RMS threshold for silence detection
        silence_duration_ms: Silence duration to trigger end
        max_duration: Maximum recording time
        on_interim: Not used (local doesn't support interim results)

    Returns:
        Transcribed text
    """
    transcriber = LocalEndpointingTranscriber(
        model_size=model_size,
        silence_threshold=silence_threshold,
        silence_duration_ms=silence_duration_ms,
        max_duration=max_duration,
    )

    transcriber.start()

    # Stream audio until speech ends
    while transcriber.is_recording():
        try:
            data = audio_stream.read(frame_length, exception_on_overflow=False)
            transcriber.feed(data)
        except Exception:
            break

    return transcriber.get_transcript()


# === Warmup function for pre-loading model ===

def warmup_model(model_size: str = "small.en"):
    """
    Pre-load the Whisper model for faster first transcription.

    Call this at startup to avoid delay on first voice command.
    """
    _get_model(model_size)


# === CLI for testing ===

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("LOCAL WHISPER STT TEST")
    print("=" * 60)

    # Test with a simple audio file or generate silence
    if len(sys.argv) > 1:
        # Test with provided file
        file_path = sys.argv[1]
        print(f"\nTranscribing: {file_path}")
        start = time.time()
        result = transcribe_file_local(file_path, model_size="small.en")
        elapsed = (time.time() - start) * 1000
        print(f"Result: '{result}'")
        print(f"Time: {elapsed:.0f}ms")
    else:
        # Generate test audio (silence + beep pattern)
        print("\nGenerating test audio (1 second)...")

        # Create 1 second of silence
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b'\x00' * 32000)  # 1 second of silence

        test_audio = buffer.getvalue()

        print("Testing local transcription...")
        start = time.time()
        result = transcribe_audio_local(test_audio, model_size="small.en")
        elapsed = (time.time() - start) * 1000
        print(f"Result: '{result}' (expected empty for silence)")
        print(f"Time: {elapsed:.0f}ms")

    print("\n" + "=" * 60)
    print("Local STT ready!")
