"""
Streaming Speech-to-Text - WebSocket-based Deepgram transcription.

Reduces latency from 500-800ms (batch HTTP) to 200-300ms (streaming).
Audio is transcribed as it's spoken, not after recording completes.

"The surest way to stay under the human turn-taking threshold is streaming."
"""

import asyncio
import json
import os
import struct
import threading
import time
import wave
from io import BytesIO
from typing import Callable, Optional
import websockets

# Deepgram streaming endpoint
DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"


class StreamingTranscriber:
    """
    Real-time streaming transcription using Deepgram WebSocket API.

    Usage:
        transcriber = StreamingTranscriber(api_key)
        await transcriber.connect()
        for audio_chunk in audio_stream:
            await transcriber.send_audio(audio_chunk)
        transcript = await transcriber.finish()
    """

    def __init__(
        self,
        api_key: str,
        model: str = "nova-2",
        sample_rate: int = 16000,
        channels: int = 1,
        encoding: str = "linear16",
        on_transcript: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize streaming transcriber.

        Args:
            api_key: Deepgram API key
            model: Deepgram model (nova-2, nova, base, enhanced)
            sample_rate: Audio sample rate in Hz
            channels: Number of audio channels
            encoding: Audio encoding (linear16, flac, opus, etc.)
            on_transcript: Optional callback for interim transcripts
        """
        self.api_key = api_key
        self.model = model
        self.sample_rate = sample_rate
        self.channels = channels
        self.encoding = encoding
        self.on_transcript = on_transcript

        self.websocket = None
        self.final_transcript = ""
        self._receive_task = None
        self._connected = False

    def _build_url(self, keywords: list = None) -> str:
        """Build WebSocket URL with query parameters."""
        params = [
            f"model={self.model}",
            f"sample_rate={self.sample_rate}",
            f"channels={self.channels}",
            f"encoding={self.encoding}",
            "smart_format=true",
            "punctuate=true",
            "endpointing=300",  # 300ms silence = end of utterance
        ]

        if keywords:
            kw_str = ",".join(keywords)
            params.append(f"keywords={kw_str}")

        return f"{DEEPGRAM_WS_URL}?{'&'.join(params)}"

    async def connect(self, keywords: list = None):
        """Establish WebSocket connection to Deepgram."""
        url = self._build_url(keywords)

        # websockets 14+ uses additional_headers instead of extra_headers
        self.websocket = await websockets.connect(
            url,
            additional_headers={"Authorization": f"Token {self.api_key}"},
            ping_interval=5,
            ping_timeout=20,
        )
        self._connected = True
        self.final_transcript = ""

        # Start receiving in background
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def _receive_loop(self):
        """Receive and process transcription results."""
        try:
            async for message in self.websocket:
                data = json.loads(message)

                # Check for transcription results
                if data.get("type") == "Results":
                    channel = data.get("channel", {})
                    alternatives = channel.get("alternatives", [{}])
                    transcript = alternatives[0].get("transcript", "")
                    is_final = data.get("is_final", False)

                    if transcript:
                        if is_final:
                            self.final_transcript += " " + transcript
                        elif self.on_transcript:
                            self.on_transcript(transcript)

        except websockets.exceptions.ConnectionClosed:
            pass

    async def send_audio(self, audio_data: bytes):
        """Send audio chunk to Deepgram."""
        if self.websocket and self._connected:
            await self.websocket.send(audio_data)

    async def finish(self) -> str:
        """
        Signal end of audio and get final transcript.

        Returns:
            Complete transcription of the audio.
        """
        if self.websocket and self._connected:
            # Send close message
            await self.websocket.send(json.dumps({"type": "CloseStream"}))

            # Wait briefly for final results
            await asyncio.sleep(0.3)

            # Cancel receive task
            if self._receive_task:
                self._receive_task.cancel()
                try:
                    await self._receive_task
                except asyncio.CancelledError:
                    pass

            # Close connection
            await self.websocket.close()
            self._connected = False

        return self.final_transcript.strip()


def transcribe_audio_streaming(
    audio_data: bytes,
    api_key: str = None,
    keywords: list = None,
) -> str:
    """
    Synchronous wrapper for streaming transcription.

    This is a drop-in replacement for the batch transcribe_audio() function.
    For pre-recorded audio, it streams the data in chunks to simulate real-time.

    Args:
        audio_data: WAV audio bytes
        api_key: Deepgram API key (uses env var if not provided)
        keywords: Optional list of keyword boosts

    Returns:
        Transcribed text
    """
    if api_key is None:
        api_key = os.environ.get("DEEPGRAM_API_KEY")

    if not api_key:
        return ""

    async def _transcribe():
        transcriber = StreamingTranscriber(api_key)
        await transcriber.connect(keywords)

        # Parse WAV and extract raw audio
        with wave.open(BytesIO(audio_data), 'rb') as wf:
            # Read all frames
            frames = wf.readframes(wf.getnframes())

        # Send in chunks (100ms each for low latency)
        chunk_size = 16000 * 2 // 10  # 100ms at 16kHz, 16-bit
        for i in range(0, len(frames), chunk_size):
            chunk = frames[i:i + chunk_size]
            await transcriber.send_audio(chunk)
            await asyncio.sleep(0.01)  # Small delay between chunks

        return await transcriber.finish()

    # Run in new event loop (safe from sync context)
    return asyncio.run(_transcribe())


class LiveTranscriber:
    """
    True real-time transcription for live microphone input.

    Usage:
        transcriber = LiveTranscriber(api_key)
        transcriber.start()
        # ... record audio ...
        for chunk in audio_chunks:
            transcriber.feed(chunk)
        transcript = transcriber.stop()
    """

    def __init__(self, api_key: str, keywords: list = None):
        self.api_key = api_key
        self.keywords = keywords
        self._transcriber = None
        self._loop = None
        self._thread = None
        self._queue = None
        self.transcript = ""

    def start(self):
        """Start the transcription session."""
        import queue
        self._queue = queue.Queue()

        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._run())

        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()

    async def _run(self):
        """Main async loop."""
        self._transcriber = StreamingTranscriber(
            self.api_key,
            on_transcript=lambda t: print(f"  [interim: {t}]"),
        )
        await self._transcriber.connect(self.keywords)

        # Process audio from queue
        while True:
            try:
                # Non-blocking check for audio
                import queue as queue_module
                try:
                    audio = self._queue.get_nowait()
                    if audio is None:  # Stop signal
                        break
                    await self._transcriber.send_audio(audio)
                except queue_module.Empty:
                    await asyncio.sleep(0.01)
            except Exception:
                break

        self.transcript = await self._transcriber.finish()

    def feed(self, audio_chunk: bytes):
        """Feed audio chunk to transcriber."""
        if self._queue:
            self._queue.put(audio_chunk)

    def stop(self) -> str:
        """Stop transcription and get final result."""
        if self._queue:
            self._queue.put(None)  # Stop signal
        if self._thread:
            self._thread.join(timeout=2.0)
        return self.transcript


class EndpointingTranscriber:
    """
    Real-time transcription with automatic endpointing detection.

    Streams audio live to Deepgram and automatically stops when
    speech ends (detected via endpointing parameter).

    Usage:
        transcriber = EndpointingTranscriber(api_key)
        transcriber.start()
        while transcriber.is_recording():
            chunk = mic.read(...)
            transcriber.feed(chunk)
        transcript = transcriber.get_transcript()
    """

    def __init__(
        self,
        api_key: str,
        keywords: list = None,
        endpointing_ms: int = 300,
        max_duration: float = 30.0,
        on_interim: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize endpointing transcriber.

        Args:
            api_key: Deepgram API key
            keywords: Optional keyword boosts
            endpointing_ms: Silence duration (ms) to trigger end (default: 300)
            max_duration: Maximum recording time in seconds (default: 30)
            on_interim: Callback for interim transcripts
        """
        self.api_key = api_key
        self.keywords = keywords
        self.endpointing_ms = endpointing_ms
        self.max_duration = max_duration
        self.on_interim = on_interim

        self._websocket = None
        self._loop = None
        self._thread = None
        self._queue = None
        self._speech_ended = threading.Event()
        self._connected = threading.Event()
        self._final_transcript = ""
        self._interim_transcript = ""
        self._start_time = None

    def _build_url(self) -> str:
        """Build WebSocket URL with endpointing enabled."""
        params = [
            "model=nova-2",
            "sample_rate=16000",
            "channels=1",
            "encoding=linear16",
            "smart_format=true",
            "punctuate=true",
            f"endpointing={self.endpointing_ms}",
            "utterance_end_ms=1000",  # Also listen for utterance end
        ]

        if self.keywords:
            kw_str = ",".join(self.keywords)
            params.append(f"keywords={kw_str}")

        return f"{DEEPGRAM_WS_URL}?{'&'.join(params)}"

    def start(self):
        """Start the transcription session."""
        import queue
        self._queue = queue.Queue()
        self._speech_ended.clear()
        self._connected.clear()
        self._final_transcript = ""
        self._interim_transcript = ""
        self._start_time = time.time()

        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._run())

        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()

        # Wait for connection to be established
        self._connected.wait(timeout=5.0)

    async def _run(self):
        """Main async loop - connect, stream, and detect endpointing."""
        url = self._build_url()

        try:
            self._websocket = await websockets.connect(
                url,
                additional_headers={"Authorization": f"Token {self.api_key}"},
                ping_interval=5,
                ping_timeout=20,
            )
            self._connected.set()

            # Start receive task
            receive_task = asyncio.create_task(self._receive_loop())
            send_task = asyncio.create_task(self._send_loop())

            # Wait for either task to complete
            done, pending = await asyncio.wait(
                [receive_task, send_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # Close connection
            if self._websocket:
                await self._websocket.send(json.dumps({"type": "CloseStream"}))
                await asyncio.sleep(0.1)
                await self._websocket.close()

        except Exception as e:
            print(f"[EndpointingTranscriber error: {e}]")
            self._speech_ended.set()

    async def _receive_loop(self):
        """Receive transcription results and detect endpointing."""
        try:
            async for message in self._websocket:
                data = json.loads(message)
                msg_type = data.get("type", "")

                if msg_type == "Results":
                    channel = data.get("channel", {})
                    alternatives = channel.get("alternatives", [{}])
                    transcript = alternatives[0].get("transcript", "")
                    is_final = data.get("is_final", False)
                    speech_final = data.get("speech_final", False)

                    if transcript:
                        if is_final:
                            self._final_transcript += " " + transcript
                            self._interim_transcript = ""
                        else:
                            self._interim_transcript = transcript
                            if self.on_interim:
                                self.on_interim(transcript)

                    # Endpointing detected!
                    if speech_final:
                        self._speech_ended.set()
                        return

                elif msg_type == "UtteranceEnd":
                    # Alternative endpointing signal
                    self._speech_ended.set()
                    return

        except websockets.exceptions.ConnectionClosed:
            self._speech_ended.set()

    async def _send_loop(self):
        """Send audio chunks from queue to Deepgram."""
        import queue as queue_module

        while not self._speech_ended.is_set():
            # Check max duration
            if time.time() - self._start_time > self.max_duration:
                self._speech_ended.set()
                return

            try:
                audio = self._queue.get_nowait()
                if audio is None:  # Manual stop signal
                    self._speech_ended.set()
                    return
                await self._websocket.send(audio)
            except queue_module.Empty:
                await asyncio.sleep(0.01)

    def feed(self, audio_chunk: bytes):
        """Feed audio chunk to transcriber."""
        if self._queue and not self._speech_ended.is_set():
            self._queue.put(audio_chunk)

    def is_recording(self) -> bool:
        """Check if still recording (speech not ended)."""
        return not self._speech_ended.is_set()

    def stop(self):
        """Manually stop recording."""
        self._speech_ended.set()
        if self._queue:
            self._queue.put(None)
        if self._thread:
            self._thread.join(timeout=2.0)

    def get_transcript(self) -> str:
        """Get final transcript after recording ends."""
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        return self._final_transcript.strip()


def transcribe_live_with_endpointing(
    audio_stream,
    frame_length: int,
    api_key: str = None,
    keywords: list = None,
    endpointing_ms: int = 300,
    max_duration: float = 30.0,
    on_interim: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Transcribe live audio with automatic endpointing.

    Streams audio from microphone to Deepgram until speech ends.
    Returns the final transcript.

    Args:
        audio_stream: PyAudio stream to read from
        frame_length: Samples per frame
        api_key: Deepgram API key (uses env var if not provided)
        keywords: Optional keyword boosts
        endpointing_ms: Silence duration to trigger end (default: 300)
        max_duration: Maximum recording time in seconds
        on_interim: Callback for interim transcripts

    Returns:
        Transcribed text
    """
    import time

    if api_key is None:
        api_key = os.environ.get("DEEPGRAM_API_KEY")

    if not api_key:
        return ""

    transcriber = EndpointingTranscriber(
        api_key=api_key,
        keywords=keywords,
        endpointing_ms=endpointing_ms,
        max_duration=max_duration,
        on_interim=on_interim,
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


# === CLI for testing ===

if __name__ == "__main__":
    import sys
    import time

    print("=" * 60)
    print("STREAMING STT TEST")
    print("=" * 60)

    api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        print("ERROR: DEEPGRAM_API_KEY not set")
        sys.exit(1)

    # Generate test audio (1 second of silence)
    print("\nGenerating test audio...")
    buffer = BytesIO()
    with wave.open(buffer, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b'\x00' * 32000)
    test_audio = buffer.getvalue()

    # Test streaming transcription
    print("Testing streaming transcription...")
    start = time.time()
    result = transcribe_audio_streaming(test_audio, api_key)
    elapsed = (time.time() - start) * 1000
    print(f"Result: '{result}' ({elapsed:.0f}ms)")

    print("\n" + "=" * 60)
    print("Streaming STT ready!")
