# Suzerain Development Roadmap

> *"They rode on."*

**Last Updated**: January 2026
**Maintainer**: Solo founder
**Status**: Post-MVP validation, pre-public release

---

## Executive Summary

Suzerain is a voice-activated interface for Claude Code using semantic command phrases ("grimoire"). The core insight: nobody bridges voice input + agentic code execution + privacy. Siri can't run agents. Claude Code can't hear. Suzerain bridges both.

**Current State**: Parser works. Audio pipeline works. End-to-end tested.

**The Challenge**: Transform from "weird ass toy with extra unnecessary steps" into a tool that commands respect.

**Window**: 6-18 months before Anthropic ships native Claude Code voice.

---

## Phase 0: Now (Complete)

### What's Done

| Component | Status | Notes |
|-----------|--------|-------|
| Grimoire parser | Working | RapidFuzz, 80% threshold, ratio scorer |
| Command library | Working | 21 commands, 5 modifiers |
| Wake word | Working | Porcupine integration, free tier |
| STT | Working | Deepgram Nova-2, keyword boosting |
| Claude execution | Working | Headless mode, stream-json output |
| Test mode | Working | Type phrases, debug matching |
| Voice mode | Working | Push-to-talk, wake word optional |
| Confirmation system | Working | Destructive commands gated |
| Disambiguation | Working | Multiple close matches prompt |

### What's Blocking

| Blocker | Impact | Resolution Path |
|---------|--------|-----------------|
| Audio feedback crashes | Low | simpleaudio segfaults on Apple Silicon; need replacement (sounddevice, afplay) |
| No usage analytics | Medium | Can't prove value; add opt-in telemetry for personal tracking |
| Single-project only | Low | Acceptable for MVP; defer multi-project |
| No installation docs | High for sharing | Write quick-start guide before showing anyone |

### Technical Debt

- Debug logging scattered (consolidate to single logger)
- No graceful handling of Deepgram API failures
- No offline fallback for STT
- CLAUDE.md references outdated file structure

---

## Phase 1: MVP (Minimum to Show Others)

**Goal**: Someone else can install it, use it once, and understand the value proposition.

**Estimated Effort**: 15-25 hours (solo dev)

### Features

| Feature | Priority | Hours | Rationale |
|---------|----------|-------|-----------|
| **One-command install** | P0 | 4-6 | `pip install suzerain` or single curl command |
| **Quick-start guide** | P0 | 2-3 | 5-minute setup to first command |
| **Fix audio feedback** | P1 | 2-3 | Replace simpleaudio with afplay or sounddevice |
| **Demo video** | P0 | 3-4 | 60-90 second "here's what it does" |
| **Error messages** | P1 | 2-3 | Human-readable, actionable errors |
| **Sandbox mode polish** | P2 | 1-2 | Better dry-run visualization |

### Technical Milestones

1. **Installation**: `pip install suzerain && suzerain --setup` guides through API keys
2. **First run**: Works in <5 minutes from git clone
3. **Demo flow**: "the judge smiled" runs tests, shows output, feels magical

### RICE Prioritization

| Feature | Reach | Impact | Confidence | Effort | Score |
|---------|-------|--------|------------|--------|-------|
| One-command install | High | High | High | Medium | 8.0 |
| Quick-start guide | High | High | High | Low | 9.0 |
| Demo video | High | High | Medium | Medium | 6.0 |
| Fix audio feedback | Low | Medium | High | Low | 4.0 |

### Success Criteria

- [ ] Non-technical friend can install with guide in 10 minutes
- [ ] 3 people try it and "get it" without you explaining
- [ ] You use it daily for a week without wanting to quit

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| People don't get the literary thing | High | Medium | Plain English aliases; explain "why" in docs |
| Setup too complex | Medium | High | Video walkthrough; automated setup script |
| Demo machine bugs out | Medium | High | Record demo, don't do live |
| "Why not just type?" objection | High | High | Emphasize flow state, hands-free moments, wizard satisfaction |

---

## Phase 2: v1.0 (Minimum to Release Publicly)

**Goal**: Strangers on the internet can discover, install, and use it without founder involvement.

**Estimated Effort**: 40-60 hours (solo dev)

### Features

| Feature | Priority | Hours | Rationale |
|---------|----------|-------|-----------|
| **Command chaining** | P1 | 6-8 | "the judge smiled... they rode on" |
| **Context injection** | P1 | 4-6 | {{CLIPBOARD}}, {{LAST_FILE}}, {{CWD}} |
| **Plain English fallback** | P0 | 4-6 | "run tests" works alongside grimoire |
| **Custom grimoire editing** | P1 | 4-6 | YAML validation, hot reload |
| **Offline STT fallback** | P2 | 6-8 | Vosk or faster-whisper local |
| **Usage stats dashboard** | P2 | 4-6 | Commands/day, latency, errors |
| **Open source prep** | P0 | 3-4 | LICENSE, CONTRIBUTING, CODE_OF_CONDUCT |
| **Hacker News launch** | P0 | 2-3 | Post, Show HN, respond to comments |

### Command Chaining Specification

```
"the judge smiled... they rode on"
        ↓
[run tests] → if success → [continue last task]

"the evening redness in the west... and the blood dried"
        ↓
[deploy] → if success → [commit changes]
```

**Delimiter**: Ellipsis (`...`) or conjunction (`and then`, `then`)

### Context Injection Specification

```yaml
# grimoire/commands.yaml
- phrase: "read what I copied"
  expansion: |
    Analyze the following text and explain what it does:

    {{CLIPBOARD}}

    Be concise.
```

| Token | Source | Example |
|-------|--------|---------|
| `{{CLIPBOARD}}` | System clipboard | Pasted code, error messages |
| `{{LAST_FILE}}` | Most recent file in editor | Current working file |
| `{{CWD}}` | Current working directory | Project root |
| `{{SELECTION}}` | Editor selection (future) | Highlighted code |

### Plain English Fallback

When grimoire match fails, check for common patterns:

```python
FALLBACK_PATTERNS = {
    r"run (the )?tests?": "the judge smiled",
    r"deploy( to production)?": "the evening redness in the west",
    r"pull( latest)?": "draw the sucker",
    r"commit( changes)?": "the blood dried",
    r"continue|keep going": "they rode on",
}
```

User sees: "No grimoire match. Did you mean 'the judge smiled' (run tests)? [y/n]"

### Technical Milestones

1. **Chaining**: Pipeline executes multiple commands sequentially
2. **Context**: Variables expand correctly before Claude execution
3. **Fallback**: Plain English recognized, mapped to grimoire
4. **Polish**: No crashes, clear errors, feels solid

### Success Criteria

- [ ] 100+ GitHub stars within 2 weeks of HN launch
- [ ] 3+ unsolicited testimonials/tweets
- [ ] 10+ people using it weekly (self-reported or analytics)
- [ ] Zero critical bugs reported in first week

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| HN dismisses as gimmick | Medium | High | Lead with utility, not aesthetic; show real productivity gain |
| Bugs on other systems | High | Medium | CI testing on macOS, Linux; Windows deferred |
| Feature requests flood | Medium | Low | Clear "not planned" list; focus on core |
| Anthropic announces voice | Medium | Critical | Pivot messaging to "privacy-first" + "customizable" |

---

## Phase 3: Growth (If Successful)

**Goal**: Sustainable project with community, potential for monetization.

**Estimated Effort**: 100+ hours (solo dev) or seek contributors

### Feature Candidates (Choose 2-3)

| Feature | Effort | Impact | Notes |
|---------|--------|--------|-------|
| **Mobile companion app** | 60-80h | High | React Native; relay to dev machine via Tailscale |
| **Custom wake words** | 20-30h | Medium | Picovoice Console or openWakeWord training |
| **Grimoire marketplace** | 40-60h | Medium | Share command sets; community curation |
| **Team/enterprise features** | 60-100h | High | Shared grimoire, SSO, audit logs |
| **Wearable hardware** | 80-120h | Medium | ESP32 pendant; niche but memorable |
| **VS Code extension** | 30-40h | Medium | Editor integration; status bar, inline feedback |

### Mobile Companion Architecture

```
[Phone/Watch]     [Cloud Relay]     [Dev Machine]
     ↓                  ↓                  ↓
  Wake Word    →    WebSocket    →    Suzerain Daemon
  Deepgram     ←    Encrypted    ←    Claude Code
  TTS Output        Results           Execution
```

**Technology choices**:
- Relay: Cloudflare Workers or small VPS
- Auth: Short-lived tokens + device pairing
- Push: Firebase Cloud Messaging or direct WebSocket

### Grimoire Marketplace Concept

```
suzerain grimoire install devops-essentials
suzerain grimoire publish my-custom-commands
suzerain grimoire search "kubernetes"
```

**Curation model**: Community upvotes, verified authors, security review for popular sets.

### Wearable Hardware Concept

**Bill of Materials** (~$35):
- XIAO ESP32S3 Sense ($15-20)
- 3.7V 500mAh LiPo ($4-10)
- 3D printed enclosure ($5-15)

**Key insight**: Hardware makes the project memorable. "That guy with the voice pendant."

### Success Criteria

- [ ] 1,000+ weekly active users
- [ ] 50+ community-contributed commands
- [ ] $500+ MRR (if monetized) OR sustainable without revenue
- [ ] Speaking invite or notable coverage

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Burnout (solo founder) | High | Critical | Ruthless scope control; seek co-maintainer early |
| Community toxicity | Low | Medium | Clear CoC; moderation from day one |
| Enterprise needs diverge | Medium | Medium | Fork path: OSS core + commercial add-ons |
| Security incident | Low | Critical | Security.md, responsible disclosure, no production credentials in demos |

---

## Decision Points

### When to Pivot

| Signal | Threshold | Action |
|--------|-----------|--------|
| Anthropic ships native voice | Feature parity + better latency | Pivot to "power user layer" / customization angle |
| Zero traction after 90 days | <50 GitHub stars, <10 active users | Personal tool only; stop public effort |
| Competitor dominates | Cursor/Copilot voice becomes standard | Niche down to privacy/enterprise |

### When to Expand

| Signal | Threshold | Action |
|--------|-----------|--------|
| Organic growth | 500+ stars, 50+ weekly users | Consider team features |
| Enterprise interest | 3+ inbound inquiries | Build SSO, audit, on-prem |
| Hardware demand | 20+ "I'd buy a pendant" comments | Prototype hardware |

### When to Kill

| Signal | Threshold | Action |
|--------|-----------|--------|
| You stop using it | 2+ weeks without personal use | Honest conversation: why? |
| Claude Code deprecated | Anthropic ends CLI support | Archive with honor |
| Life circumstances | Runway exhausted, other priorities | Open source, find maintainer |

---

## Resource Estimates

### Phase 1 (MVP): 15-25 hours

```
Week 1: Install experience (8h)
├── Setup script and pip packaging
├── Quick-start documentation
└── Fix audio feedback

Week 2: Polish and demo (7-12h)
├── Error message improvements
├── Demo video production
└── Test with 3+ people
```

### Phase 2 (v1.0): 40-60 hours

```
Weeks 1-2: Core features (20-30h)
├── Command chaining
├── Context injection
└── Plain English fallback

Weeks 3-4: Release prep (20-30h)
├── Open source packaging
├── Documentation polish
├── HN launch preparation
└── Bug fixes from beta testers
```

### Phase 3 (Growth): 100+ hours

```
Months 1-2: Choose one major feature (40-60h)
├── Mobile app OR
├── Custom wake words OR
└── Marketplace

Month 3: Community (40-60h)
├── Contributor onboarding
├── Documentation expansion
└── Support and maintenance
```

---

## The Minimum Path to Credibility

**The friend said**: "Weird ass toy with extra unnecessary steps."

**What changes their mind**:

1. **It works instantly** - Install in 5 minutes, not 50
2. **It solves a real problem** - Hands-free coding moments exist
3. **It's not fragile** - Doesn't crash, doesn't confuse
4. **Someone else validates it** - HN upvotes, Twitter mentions, GitHub stars

**The path**:

```
[Now]                    [Phase 1]               [Phase 2]
Parser works       →     Anyone can install  →   Strangers use it
Audio works              Quick-start guide        Public validation
You use it               Demo video               Community forms
                         3 people try it          1000+ users possible
```

**The honest truth**: Credibility comes from other people using it. Not from more features. Not from better code. Not from clever marketing.

Phase 1 is entirely about removing friction so others can try it.

Phase 2 is about giving them reasons to keep using it.

Phase 3 only happens if Phase 2 succeeds.

---

## Appendix: Feature Backlog (Not Prioritized)

Ideas captured but not committed:

- [ ] Voice personas (different TTS voices for different contexts)
- [ ] Gesture integration (wave to cancel)
- [ ] AR overlay (spatial command palette)
- [ ] Multi-language grimoire (Spanish, Japanese, etc.)
- [ ] Voice biometrics (speaker verification)
- [ ] Ambient sound triggers (clap to confirm)
- [ ] Integration with Raycast/Alfred
- [ ] Browser extension for web research
- [ ] Slack/Discord bot interface
- [ ] Vim/Neovim plugin

---

## Appendix: Competitive Landscape

| Player | Voice | Agentic | Privacy | Customizable |
|--------|-------|---------|---------|--------------|
| Siri/Alexa | Yes | No | No | Limited |
| GitHub Copilot Voice | Ended | No | No | No |
| Cursor 2.0 | Yes | Limited | No | Limited |
| Claude Code | **No** | Yes | Partial | Via CLI |
| **Suzerain** | Yes | Yes | Yes | Yes |

**Positioning**: The privacy-first, customizable voice layer for Claude Code power users.

---

## Appendix: Cost Projections

### Personal Use (15 commands/day)

| Service | Monthly Cost |
|---------|--------------|
| Deepgram STT | ~$0.65 |
| Claude API (via Claude Code) | $12-50 |
| **Total** | **$13-51/month** |

### Heavy Use (50 commands/day)

| Service | Monthly Cost |
|---------|--------------|
| Deepgram STT | ~$2.15 |
| Claude API | $40-150 |
| **Total** | **$42-152/month** |

---

*"Whatever exists without my knowledge exists without my consent."*

The roadmap exists. Now ride on.
