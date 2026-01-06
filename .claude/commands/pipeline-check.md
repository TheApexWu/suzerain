# Check Pipeline Status

Verify all Sigil pipeline components are working.

## Instructions

Check each component in order:

1. **Python Environment**
   ```bash
   python --version
   pip list | grep -E "(pyaudio|pvporcupine|deepgram|rapidfuzz)"
   ```

2. **Microphone Access**
   ```bash
   python -c "import pyaudio; p = pyaudio.PyAudio(); print(f'Devices: {p.get_device_count()}')"
   ```

3. **Porcupine Wake Word**
   ```bash
   python -c "import pvporcupine; print(f'Porcupine version: {pvporcupine.porcupine_version()}')"
   ```

4. **Deepgram Connection**
   - Check if DEEPGRAM_API_KEY is set
   - Test with a sample audio file if available

5. **Claude Code**
   ```bash
   claude --version
   claude -p "echo test" --output-format stream-json | head -5
   ```

Report status of each component with pass/fail indicators.
