# Voice UX Audit: Suzerain

> *"He never sleeps, the judge. He is dancing, dancing."*

**Date**: 2026-01-04
**Scope**: Voice interaction design, latency optimization, audio feedback, accessibility
**Status**: Research Complete

---

## Executive Summary

This audit evaluates Suzerain's voice interface against industry best practices from Alexa, Siri, Google Assistant, and Talon Voice. Key findings:

1. **Latency budget is realistic** but Claude Code startup (2-8s) breaks the "instant" perception threshold
2. **Error handling is functional** but lacks escalating help strategies used by mature voice platforms
3. **Audio feedback is broken** (simpleaudio crashes on Apple Silicon) - multiple viable alternatives exist
4. **Wake word implementation is solid** via Porcupine, but false positive mitigation could be enhanced
5. **Accessibility is not addressed** - critical gap for a voice-first interface

**Recommendation Priority**:
1. Fix audio feedback (blocking user experience)
2. Add progress indicators for Claude execution
3. Implement escalating error recovery
4. Add voice accessibility features

---

## Part 1: Industry Research

### 1.1 Voice Command UX Best Practices

Research from leading voice platforms reveals consistent patterns for error handling, feedback, and disambiguation.

#### Error Handling: The Escalating Help Strategy

Industry leaders use **three-level error recovery** instead of dead-end responses:

| Level | Strategy | Example |
|-------|----------|---------|
| 1 | Rephrase request | "Could you say that another way?" |
| 2 | Offer suggestions | "I can help with deployment, testing, or git. Which one?" |
| 3 | Graceful fallback | "I'm having trouble. Would you like to type instead?" |

**Key insight**: Dead-end responses like "I don't understand" cause user abandonment. [Smart error handling keeps conversation moving forward](https://frejun.ai/best-practices-for-voice-bot-design-and-ux/).

#### Disambiguation Patterns

When user intent is ambiguous, best practice is to:
- Ask clarifying questions proactively
- Present numbered options (max 3-4)
- Allow easy cancellation
- Remember context from previous interactions

[Alexa and Google Assistant use intent/utterance models](https://lollypop.design/blog/2025/august/voice-user-interface-design-best-practices/) where all likely phrasings are mapped to specific intents.

#### Confirmation Patterns

Destructive actions require:
1. **Verbal confirmation request** with action summary
2. **Distinct confirmation phrase** (not just "yes" - too easy to false-positive)
3. **Undo capability** when possible

### 1.2 Latency Perception Psychology

Human perception of voice interface responsiveness follows non-linear thresholds:

| Latency | Perception | Source |
|---------|------------|--------|
| <100ms | Instantaneous | [Springer Research](https://link.springer.com/chapter/10.1007/978-3-319-58475-1_1) |
| 100-150ms | Immediate | System response feels connected to input |
| 150-300ms | Slight delay | Noticeable but acceptable |
| 300-500ms | Conversational | [Natural turn-taking threshold](https://arxiv.org/html/2404.16053v1) |
| 500-1000ms | Sluggish | User begins to wonder if heard |
| >1000ms | Broken | Interaction feels disconnected |

**Critical finding**: [Users perceive delays more from their motor error than actual delay](https://dl.acm.org/doi/10.1145/2993369.2993381). If users can see/hear the system is working, tolerance increases dramatically.

#### Task Complexity Effect

[Perceived task complexity increases delay tolerance](https://www.sciencedirect.com/science/article/abs/pii/S1071581923000770):
- Simple command ("set timer"): <500ms expected
- Complex operation ("deploy to production"): 2-10s acceptable if progress is shown
- Research task ("analyze codebase"): Minutes acceptable with clear status

### 1.3 Audio Feedback Patterns

#### Types of UI Sounds

| Type | Purpose | Characteristics |
|------|---------|-----------------|
| **Earcons** | Abstract state indicators | 2-tone beeps, chimes |
| **Auditory Icons** | Skeuomorphic real-world sounds | Click, whoosh, thunk |
| **Hero Sounds** | Success/accomplishment | Longer, gratifying |
| **Notification Tones** | Status updates | Short, repeatable |

[Nielsen Norman Group research](https://www.nngroup.com/articles/audio-signifiers-voice-interaction/) identifies three critical audio signifiers for voice:

1. **Listening indicator**: "I heard you" (Siri's 2-tone beep after wake word)
2. **Processing indicator**: "I'm working on it" (thinking tone or silence with visual)
3. **Completion indicator**: "Done" or "Error" differentiation

#### Sound Design Principles

From [UX Sound research](https://www.toptal.com/designers/ux/ux-sounds-guide):

- **Keep it simple**: Concise, unobtrusive
- **Avoid annoyance**: Sounds repeat frequently; must not fatigue
- **Brand consistency**: Sounds should match product personality
- **Function over beauty**: A beautiful sound that doesn't communicate is useless

[Spotify's earcon design](https://wearelisten.com/project/spotify-earcons/) emphasizes:
- Bright, uptempo for positive states
- Minimal textures for transparency
- Lightweight enough to not interrupt flow

### 1.4 Noise Robustness Techniques

Beyond basic VAD (Voice Activity Detection), research shows several techniques for improving recognition in noisy environments:

#### Signal Processing

| Technique | Improvement | Complexity |
|-----------|-------------|------------|
| [Acoustic Echo Cancellation (AEC)](https://arxiv.org/html/2401.03473) | Removes speaker playback from mic | Medium |
| [Weighted Prediction Error (WPE)](https://arxiv.org/html/2401.03473) | Dereverberation | Medium |
| [Beamforming](https://www.frontiersin.org/journals/signal-processing/articles/10.3389/frsip.2024.1413983/full) | Directional focus (requires mic array) | High |

#### Machine Learning Approaches

- **Data Augmentation**: [Training with simulated noise, reverberation, varied SNR](https://www.mdpi.com/1424-8220/20/8/2326)
- **Audio-Visual Fusion**: [Router-gated cross-modal fusion](https://arxiv.org/pdf/2508.18734) for 16-42% WER reduction
- **LLM Error Correction**: [Generative error correction](https://openreview.net/forum?id=ceATjGPTUD) using LLM to fix ASR mistakes

#### Practical Recommendations

For a CLI tool like Suzerain:
1. **Noise augmentation in training** (if using custom wake word)
2. **Adaptive VAD thresholds** based on ambient noise level
3. **STT confidence scores** to trigger confirmation when low
4. **Fallback to typing** in persistently noisy environments

### 1.5 Wake Word False Positive Mitigation

[Research on "FakeWake" patterns](https://arxiv.org/pdf/2109.09958) shows that wake word detectors have "fuzzy words" that sound similar enough to trigger false positives.

#### Mitigation Strategies

| Strategy | Description | Effectiveness |
|----------|-------------|---------------|
| **Sensitivity Tuning** | Trade-off FAR vs FRR | Standard approach |
| **Fuzzy Word Training** | Train model on near-miss phrases | [97%+ rejection rate](https://arxiv.org/pdf/2109.09958) |
| **Post-Detection Verification** | Confirm with secondary model | Adds latency |
| **Contextual Gating** | Disable wake word during output | Prevents self-activation |

[Picovoice Porcupine documentation](https://picovoice.ai/docs/faq/porcupine/) notes:
> "A higher sensitivity value gives a lower miss rate at the expense of a higher false alarm rate."

**Industry benchmarks**: [<0.5 false accepts per hour and <5% false rejection](https://github.com/dscripka/openWakeWord) is considered acceptable for average users.

### 1.6 Accessibility Considerations

Voice interfaces present unique accessibility challenges not fully covered by [WCAG 2.2](https://www.w3.org/TR/WCAG22/):

#### Users Who Benefit from Voice

| User Group | Benefit | Design Consideration |
|------------|---------|---------------------|
| Motor impairments | Hands-free operation | Core use case |
| Visual impairments | No screen required | Audio-only feedback essential |
| Cognitive differences | Reduced interface complexity | Clear, consistent patterns |
| RSI/carpal tunnel | Alternative to keyboard | Suzerain's implicit target |

#### Accessibility Gaps in Current VUI Guidelines

[Research notes](https://medium.com/design-bootcamp/designing-with-every-voice-in-mind-accessibility-in-voice-user-experience-for-people-with-6e057cc9e10a) that WCAG doesn't specify:
- How voice assistants should recover from misheard commands
- Adaptation to user-specific speech patterns
- Design for cognitive diversity (slower responses, simplified language)

#### Key Accessibility Requirements

1. **Alternative input modes**: Typing fallback for speech-impaired users
2. **Audio confirmation of all actions**: Visual feedback alone is insufficient
3. **Adjustable timing**: Slower users need longer pauses before timeout
4. **Clear pronunciation**: Avoid jargon in voice prompts
5. **Consistent vocabulary**: Same phrase always triggers same action

---

## Part 2: Current Implementation Analysis

### 2.1 Audio Capture Code Review

**File**: `src/main.py`

#### Strengths

```python
# Good: Reasonable buffer size after debugging
frame_length = 1600  # 100ms chunks for stable streaming

# Good: 16kHz sample rate matches Deepgram/Porcupine requirements
sample_rate = 16000

# Good: Overflow handling prevents crashes
data = stream.read(frame_length, exception_on_overflow=False)
```

#### Issues

1. **Fixed 3-second recording window**
   ```python
   for _ in range(int(sample_rate / frame_length * 3)):
       data = stream.read(frame_length, exception_on_overflow=False)
       frames.append(data)
   ```
   - No VAD to detect end-of-speech
   - Users must fill 3 seconds or wait

2. **No noise level monitoring**
   - Cannot adapt to ambient conditions
   - No confidence thresholds for STT

3. **Dual stream inefficiency**
   ```python
   # Separate streams for wake word and command
   stream = pa.open(...)      # Command recording
   wake_stream = pa.open(...) # Wake word detection
   ```
   - Could share a single stream with branching logic

### 2.2 Latency Budget Analysis

**Source**: `CLAUDE.md`

| Stage | Target | Actual | Status |
|-------|--------|--------|--------|
| Wake word | <100ms | ~50ms | OK (Porcupine on-device) |
| STT | <500ms | 200-500ms | OK (Deepgram Nova-2) |
| Parser | <50ms | <10ms | OK (RapidFuzz local) |
| Claude startup | 2-8s | 2-8s | BOTTLENECK |
| **Total** | 3-10s | 3-10s | Realistic but not "instant" |

#### The Claude Startup Problem

The 2-8 second Claude Code startup breaks the conversational flow. During this time:
- No audio feedback (broken)
- Only text: `[Executing...]`
- User cannot tell if system heard them or crashed

**Mitigation options**:
1. Keep Claude session warm (pre-spawn)
2. Add processing audio/visual indicator
3. Stream first acknowledgment before full response

### 2.3 Feedback Mechanisms Review

#### Current State

| Mechanism | Status | Issue |
|-----------|--------|-------|
| `ping_heard()` | Broken | simpleaudio crashes |
| `ping_success()` | Broken | simpleaudio crashes |
| `ping_error()` | Broken | simpleaudio crashes |
| Visual text | Working | `[Executing...]`, colors |
| Disambiguation | Working | Numbered selection |

#### The simpleaudio Problem

From `DEBUG_LOG.md`:
```
### Issue #6: simpleaudio Segfault on macOS
**Symptom**: `zsh: segmentation fault python src/main.py`
**Cause**: simpleaudio library crashes on macOS Apple Silicon
```

Current workaround:
```python
# simpleaudio disabled - crashes on macOS Apple Silicon
AUDIO_FEEDBACK = False
```

This completely breaks the audio feedback loop, leaving users with only visual terminal output.

### 2.4 Error Handling Review

Current implementation uses a two-level approach:

**Level 1**: No match
```python
print(f"{Colors.RED}No match in grimoire.{Colors.RESET}")
print(f"{Colors.DIM}Tip: Use 'list' to see available incantations.{Colors.RESET}")
```

**Level 2**: Disambiguation for close matches
```python
if len(close_matches) > 1:
    command, score = disambiguate(close_matches)
```

#### Missing Elements

1. **No rephrase request** ("Could you say that differently?")
2. **No category suggestions** ("Did you mean a deployment, testing, or git command?")
3. **No typing fallback prompt** for persistent failures
4. **No confidence-based confirmation** when match score is borderline

---

## Part 3: Recommendations

### 3.1 Audio Feedback Solutions (Priority: Critical)

The simpleaudio crash must be fixed. Here are macOS-compatible alternatives:

#### Option A: AppKit NSSound (Recommended)

**Pros**: Native macOS, no dependencies, works on Apple Silicon
**Cons**: macOS only (acceptable for MVP)

```python
def play_sound_native(file_path: str):
    """Play audio using macOS native AppKit."""
    try:
        from AppKit import NSSound
        sound = NSSound.alloc().initWithContentsOfFile_byReference_(file_path, True)
        sound.play()
    except ImportError:
        pass  # Not on macOS
```

For generated tones, pre-render to WAV files at startup.

#### Option B: sounddevice + numpy

**Pros**: Cross-platform, works with NumPy arrays
**Cons**: Requires PortAudio, additional dependency

```python
import sounddevice as sd
import numpy as np

def ping_sounddevice(freq: int = 800, duration_ms: int = 100):
    """Play a confirmation tone using sounddevice."""
    sample_rate = 44100
    t = np.linspace(0, duration_ms/1000, int(sample_rate * duration_ms/1000), False)
    wave = np.sin(2 * np.pi * freq * t) * 0.3
    sd.play(wave.astype(np.float32), sample_rate)
    sd.wait()
```

#### Option C: afplay subprocess

**Pros**: Zero dependencies, always works on macOS
**Cons**: Requires pre-rendered audio files

```python
import subprocess

def play_afplay(file_path: str):
    """Play audio using macOS afplay command."""
    subprocess.Popen(['afplay', file_path],
                     stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
```

#### Recommendation

Use **Option A (AppKit NSSound)** for macOS with pre-rendered WAV files for tones. Fall back to **Option C (afplay)** if AppKit import fails. Add **Option B (sounddevice)** for cross-platform support later.

### 3.2 Progress Indicators for Long Operations

To maintain user engagement during Claude's 2-8s startup:

#### Audio Indicators

| State | Sound | Timing |
|-------|-------|--------|
| Command received | Short rising tone (400Hz, 100ms) | Immediate |
| Processing started | Subtle tick/pulse | Every 2s during wait |
| Success | Rising two-tone (400-800Hz) | On completion |
| Error | Falling two-tone (400-200Hz) | On failure |

#### Visual Indicators

```python
# Spinner or progress dots during Claude execution
import itertools
spinner = itertools.cycle(['|', '/', '-', '\\'])
print(f"\r{Colors.BLUE}[Processing {next(spinner)}]{Colors.RESET}", end='')
```

### 3.3 Escalating Error Recovery

Implement three-level error handling:

```python
def handle_no_match(text: str, attempt: int = 1):
    """Handle unrecognized commands with escalating help."""

    if attempt == 1:
        # Level 1: Request rephrase
        print(f"{Colors.YELLOW}I didn't quite catch that.{Colors.RESET}")
        print("Could you say that another way?")
        ping_error()

    elif attempt == 2:
        # Level 2: Offer categories
        print(f"{Colors.YELLOW}Still having trouble.{Colors.RESET}")
        print("I can help with: deploy, testing, git, or research.")
        print("Which category?")

    else:
        # Level 3: Fallback to typing
        print(f"{Colors.YELLOW}Voice recognition struggling.{Colors.RESET}")
        print("Type your command, or say 'list' for all options.")
```

### 3.4 Wake Word Improvements

#### Sensitivity Configuration

Add user-configurable sensitivity:
```python
parser.add_argument(
    "--sensitivity", "-S",
    type=float,
    default=0.5,
    help="Wake word sensitivity 0.0-1.0 (higher = more sensitive)"
)
```

#### Self-Activation Prevention

Disable wake word during audio output:
```python
def execute_command(command, modifiers):
    if wake_detector:
        wake_detector.pause()  # Prevent self-triggering
    try:
        # Execute command...
    finally:
        if wake_detector:
            wake_detector.resume()
```

### 3.5 Accessibility Improvements

#### Alternative Input Mode

Already partially implemented via `--test` mode. Enhance:

```python
def hybrid_input_mode():
    """Accept either voice or typed input."""
    print("Speak a command or type below:")

    # Use select() to wait on both stdin and audio
    # First input wins
```

#### Audio-Only Confirmation

Ensure all visual feedback has audio equivalent:

| Visual | Audio Equivalent |
|--------|------------------|
| "Matched: X" | Speak "Running: [phrase]" |
| "Complete" | Success chime |
| Error text | Error tone + spoken summary |

#### Adjustable Timing

```python
parser.add_argument(
    "--speech-timeout",
    type=float,
    default=3.0,
    help="Seconds to wait for speech (accessibility)"
)
```

### 3.6 Noise Handling Improvements

#### STT Confidence Threshold

```python
def transcribe_audio(audio_data: bytes) -> tuple[str, float]:
    """Return (transcript, confidence)."""
    # ... existing code ...
    confidence = result["results"]["channels"][0]["alternatives"][0]["confidence"]
    return transcript, confidence

# In main:
transcript, confidence = transcribe_audio(audio_data)
if confidence < 0.7:
    print(f"{Colors.YELLOW}I'm not sure I heard correctly: \"{transcript}\"{Colors.RESET}")
    confirm = input("Is this right? [y/N]: ")
```

#### Ambient Noise Indicator

```python
def estimate_noise_level(audio_data: bytes) -> float:
    """Estimate ambient noise from audio samples."""
    import struct
    samples = struct.unpack(f'{len(audio_data)//2}h', audio_data)
    rms = (sum(s**2 for s in samples) / len(samples)) ** 0.5
    return rms / 32768.0  # Normalize to 0-1

# Warn if environment is too noisy
if estimate_noise_level(audio_data) > 0.1:
    print(f"{Colors.YELLOW}High ambient noise detected.{Colors.RESET}")
```

---

## Part 4: Implementation Roadmap

### Phase 1: Critical Fixes (Week 1)

| Task | Effort | Impact |
|------|--------|--------|
| Replace simpleaudio with AppKit/afplay | 2h | High - restores audio feedback |
| Add processing spinner during Claude execution | 1h | Medium - reduces perceived latency |
| Pre-render audio tones as WAV files | 1h | Required for AppKit solution |

### Phase 2: Error Handling (Week 2)

| Task | Effort | Impact |
|------|--------|--------|
| Implement 3-level error recovery | 3h | Medium - reduces user frustration |
| Add STT confidence threshold | 2h | Medium - catches recognition errors |
| Add "typing fallback" prompt | 1h | Low - accessibility improvement |

### Phase 3: Polish (Week 3-4)

| Task | Effort | Impact |
|------|--------|--------|
| VAD-based end-of-speech detection | 4h | Medium - eliminates fixed 3s wait |
| Wake word sensitivity CLI flag | 1h | Low - power user feature |
| Ambient noise level indicator | 2h | Low - debugging aid |
| Accessibility timing options | 2h | Low - niche but important |

---

## Part 5: Audio Feedback Sound Design

### Proposed Earcon Set

Based on [industry sound design research](https://www.toptal.com/designers/ux/ux-sounds-guide), here's a minimal earcon vocabulary:

| State | Description | Frequency | Duration |
|-------|-------------|-----------|----------|
| `heard` | Low confirmation | 400Hz sine | 100ms |
| `processing` | Subtle tick | 600Hz click | 50ms |
| `success` | Rising two-tone | 400Hz->800Hz | 150ms |
| `error` | Falling two-tone | 400Hz->200Hz | 200ms |
| `warning` | Attention getter | 600Hz x2 | 100ms x2 |

### Audio File Generation

Pre-render these as WAV files at startup or ship as assets:

```python
import numpy as np
import wave
import os

def generate_earcons():
    """Generate audio feedback files if not present."""
    earcons_dir = Path(__file__).parent.parent / "assets" / "audio"
    earcons_dir.mkdir(parents=True, exist_ok=True)

    sample_rate = 44100

    def make_tone(freqs, durations, filename):
        samples = []
        for freq, dur in zip(freqs, durations):
            t = np.linspace(0, dur/1000, int(sample_rate * dur/1000), False)
            wave_data = np.sin(2 * np.pi * freq * t) * 0.3
            # Apply envelope to avoid clicks
            envelope = np.ones_like(wave_data)
            fade_len = min(100, len(wave_data) // 4)
            envelope[:fade_len] = np.linspace(0, 1, fade_len)
            envelope[-fade_len:] = np.linspace(1, 0, fade_len)
            samples.extend(wave_data * envelope)

        audio = (np.array(samples) * 32767).astype(np.int16)
        with wave.open(str(earcons_dir / filename), 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio.tobytes())

    make_tone([400], [100], "heard.wav")
    make_tone([400, 800], [75, 75], "success.wav")
    make_tone([400, 200], [100, 100], "error.wav")
    make_tone([600], [50], "tick.wav")
```

---

## Part 6: Comparison to Industry Standards

### Suzerain vs. Major Voice Platforms

| Feature | Alexa | Siri | Google | Talon | Suzerain |
|---------|-------|------|--------|-------|----------|
| Wake word accuracy | High | High | High | N/A | Medium (Porcupine) |
| Error recovery levels | 3 | 2 | 3 | 1 | 1 (needs work) |
| Audio feedback | Rich | Minimal | Moderate | Minimal | Broken |
| Visual feedback | Screen | Screen | Screen | Desktop | Terminal |
| Latency to first response | <1s | <1s | <1s | <100ms | 2-8s |
| Accessibility features | Extensive | Extensive | Extensive | Good | Minimal |
| Customization | Skills | Shortcuts | Actions | Full | Grimoire |
| Privacy | Cloud | Cloud | Cloud | Local | Hybrid |

### Key Gaps

1. **Latency**: Claude startup is an order of magnitude slower than consumer assistants
2. **Audio feedback**: Currently non-functional vs. polished earcons elsewhere
3. **Error recovery**: Single-level vs. escalating help elsewhere
4. **Accessibility**: Not addressed vs. extensive elsewhere

### Key Strengths

1. **Customization**: Grimoire system more flexible than skill/action frameworks
2. **Privacy**: Wake word and parsing are local
3. **Developer focus**: Optimized for coding tasks, not general queries
4. **McCarthy aesthetic**: Unique voice that differentiates from generic assistants

---

## Appendix A: Research Sources

### Voice UX Design
- [Best Practices For Voice Bot Design And UX In 2025](https://frejun.ai/best-practices-for-voice-bot-design-and-ux/)
- [Voice User Interface (VUI) Design Best Practices | Designlab](https://designlab.com/blog/voice-user-interface-design-best-practices)
- [Voice User Interface Design Best Practices 2025 | Lollypop Studio](https://lollypop.design/blog/2025/august/voice-user-interface-design-best-practices/)
- [Designing for Voice Interfaces: Challenges and Tips | Medium](https://niamh-oshea.medium.com/designing-for-voice-interfaces-challenges-and-tips-ecd384709f34)

### Latency Perception
- [System Latency Guidelines Then and Now | SpringerLink](https://link.springer.com/chapter/10.1007/978-3-319-58475-1_1)
- [Human Latency Conversational Turns for Spoken Avatar Systems](https://arxiv.org/html/2404.16053v1)
- [How Much Faster is Fast Enough? | CHI 2015](https://www.tactuallabs.com/papers/howMuchFasterIsFastEnoughCHI15.pdf)
- [Defining 'seamlessly connected': user perceptions of operation latency](https://www.sciencedirect.com/science/article/abs/pii/S1071581923000770)

### Audio Feedback
- [Audio Signifiers for Voice Interaction | NN/G](https://www.nngroup.com/articles/audio-signifiers-voice-interaction/)
- [Sound Advice: A Quick Guide to Designing UX Sounds | Toptal](https://www.toptal.com/designers/ux/ux-sounds-guide)
- [Spotify Earcons: Branded Sound for Voice-Controlled Experiences](https://wearelisten.com/project/spotify-earcons/)
- [Principles & Types of UX Sound](https://ux-sound.com/types-of-ux-ui-sounds/)

### Wake Word Detection
- [Porcupine FAQ | Picovoice Docs](https://picovoice.ai/docs/faq/porcupine/)
- [FakeWake: Understanding and Mitigating Fake Wake-up Words](https://arxiv.org/pdf/2109.09958)
- [openWakeWord | GitHub](https://github.com/dscripka/openWakeWord)
- [Wake Word Detection Guide 2025 | Picovoice](https://picovoice.ai/blog/complete-guide-to-wake-word/)

### Noise Robustness
- [3 Key Strategies to Improve Noisy Speech Recognition | Forasoft](https://www.forasoft.com/blog/article/speech-recognition-accuracy-noisy-environments)
- [ICMC-ASR: The ICASSP 2024 In-Car Multi-Channel ASR Challenge](https://arxiv.org/html/2401.03473)
- [Voice Activity Detection (VAD): The Complete 2025 Guide](https://picovoice.ai/blog/complete-guide-voice-activity-detection-vad/)
- [Advances in Microphone Array Processing](https://arxiv.org/html/2502.09037v1)

### Accessibility
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/)
- [Designing with every voice in mind: Accessibility in VUX](https://medium.com/design-bootcamp/designing-with-every-voice-in-mind-accessibility-in-voice-user-experience-for-people-with-6e057cc9e10a)
- [Text-to-Speech Accessibility Guide 2025](https://www.accessibilitychecker.org/blog/text-to-speech-accessibility/)

### Talon Voice
- [Talon Voice](https://talonvoice.com/)
- [Talon: In-Depth Review | Hands-Free Coding](https://handsfreecoding.org/2021/12/12/talon-in-depth-review/)
- [Coding with voice dictation using Talon Voice | Josh W. Comeau](https://www.joshwcomeau.com/blog/hands-free-coding/)

### Python Audio Libraries
- [Playing and Recording Sound in Python | Real Python](https://realpython.com/playing-and-recording-sound-python/)
- [NSSound | Apple Developer Documentation](https://developer.apple.com/documentation/appkit/nssound)
- [sounddevice documentation](https://python-sounddevice.readthedocs.io/)

---

## Appendix B: Quick Reference Card

### Audio Feedback Solution (Copy-Paste)

```python
# === Audio Feedback (macOS-compatible) ===

import subprocess
from pathlib import Path

AUDIO_DIR = Path(__file__).parent.parent / "assets" / "audio"
AUDIO_AVAILABLE = (AUDIO_DIR / "heard.wav").exists()

def _play_audio(filename: str):
    """Play audio file using macOS afplay (non-blocking)."""
    if not AUDIO_AVAILABLE:
        return
    filepath = AUDIO_DIR / filename
    if filepath.exists():
        subprocess.Popen(
            ['afplay', str(filepath)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

def ping_heard():
    """Low tone - 'I heard you'"""
    _play_audio("heard.wav")

def ping_success():
    """Rising tone - 'Success'"""
    _play_audio("success.wav")

def ping_error():
    """Falling tone - 'Error'"""
    _play_audio("error.wav")

def ping_processing():
    """Tick - 'Still working'"""
    _play_audio("tick.wav")
```

### Error Recovery Template

```python
def handle_voice_input(transcript: str, confidence: float, attempt: int = 1):
    """Process voice input with escalating error recovery."""

    # Low confidence: confirm first
    if confidence < 0.7:
        print(f"Did you say: \"{transcript}\"? [y/N]")
        if not confirm():
            return handle_retry(attempt)

    # Try matching
    matches = match_top_n(transcript, n=3)

    if not matches:
        return handle_no_match(attempt)

    if len(matches) > 1 and matches[0][1] - matches[1][1] < 10:
        return disambiguate(matches)

    return execute(matches[0])

def handle_no_match(attempt: int):
    if attempt == 1:
        return "rephrase"   # Ask to say again
    elif attempt == 2:
        return "suggest"    # Offer categories
    else:
        return "fallback"   # Switch to typing
```

---

*"The man who believes that the secrets of the world are forever hidden lives in mystery and fear."*
