---
name: Audio Pipeline Debugger
description: Troubleshoot Suzerain's audio capture and processing pipeline
---

# Audio Pipeline Debugger

You are debugging the Suzerain audio pipeline. The pipeline has these stages:

1. **Microphone Capture** (PyAudio)
2. **Wake Word Detection** (Porcupine)
3. **Speech-to-Text** (Deepgram)
4. **Phrase Parsing** (RapidFuzz)

## Common Issues

### No Audio Detected
- Check microphone permissions in System Preferences > Privacy & Security > Microphone
- Verify PyAudio can see devices: `python -c "import pyaudio; p = pyaudio.PyAudio(); [print(p.get_device_info_by_index(i)) for i in range(p.get_device_count())]"`
- Check sample rate matches (usually 16000Hz for Porcupine)

### Wake Word Not Triggering
- Porcupine needs .ppn keyword file in correct location
- Check access key is valid: `echo $PICOVOICE_ACCESS_KEY`
- Test standalone: `python -c "import pvporcupine; porcupine = pvporcupine.create(access_key='...', keywords=['picovoice'])"`

### STT Returning Empty/Garbage
- Verify Deepgram API key: `echo $DEEPGRAM_API_KEY`
- Check network connectivity
- Audio format must be correct (16-bit PCM, 16kHz mono)
- Test with sample file before live mic

### Parser Not Matching
- Check fuzzy match threshold (default 70%)
- Print actual scores: `from rapidfuzz import fuzz; print(fuzz.token_set_ratio(phrase, target))`
- Review grimoire definitions in `grimoire/commands.yaml`

## Diagnostic Commands

```bash
# Full audio device dump
python -c "
import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        print(f'{i}: {info[\"name\"]} (rate: {info[\"defaultSampleRate\"]})')
"

# Test recording
python -c "
import pyaudio, wave
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)
print('Recording 3 seconds...')
frames = [stream.read(1024) for _ in range(int(16000/1024 * 3))]
stream.stop_stream(); stream.close(); p.terminate()
with wave.open('test.wav', 'wb') as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
    wf.writeframes(b''.join(frames))
print('Saved to test.wav')
"
```

When troubleshooting, work through the pipeline in order. Fix upstream issues before debugging downstream.
