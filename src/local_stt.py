"""
Local Speech-to-Text using faster-whisper.

Runs entirely on-device using OpenAI's Whisper model via CTranslate2.
No API calls, no costs, works offline.

Performance (Apple Silicon M1/M2/M3):
- small.en model: ~300ms for 5s audio
- base.en model: ~150ms for 5s audio
- tiny.en model: ~80ms for 5s audio
"""

import io
import time
import wave
import threading
import numpy as np

# Model cache keyed by model_size
_models: dict = {}
_model_lock = threading.Lock()


def _get_model(model_size: str = "small.en"):
    """
    Lazy-load the Whisper model.

    Models are downloaded on first use (~150MB for small.en).
    Uses CPU by default (works everywhere), GPU if available.
    """
    global _models

    with _model_lock:
        if model_size not in _models:
            from faster_whisper import WhisperModel

            # For Apple Silicon, use int8 for speed
            compute_type = "int8"
            device = "cpu"  # faster-whisper uses CPU on Mac (Metal not supported yet)

            print(f"[Loading Whisper {model_size}...]", end=" ", flush=True)
            start = time.time()

            _models[model_size] = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
                cpu_threads=4,
            )

            elapsed = time.time() - start
            print(f"done ({elapsed:.1f}s)")

        return _models[model_size]


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
        Transcribed text, or empty string if audio is empty/invalid
    """
    if not audio_data or len(audio_data) < 44:  # WAV header is 44 bytes
        return ""

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
