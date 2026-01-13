# Suzerain

> *"Whatever exists without my knowledge exists without my consent."*

**Understand your AI governance style.**

Suzerain analyzes how you use AI coding assistants and maps your behavior to historical governance patterns. Are you a hands-off Delegator or a careful Strategist?

## Quick Start

```bash
pip install suzerain
suzerain analyze
```

## What You Get

```
============================================================
YOUR AI GOVERNANCE PROFILE
============================================================

Sessions analyzed: 61
Data period: 24 days
Total tool calls: 5,761

--- GOVERNANCE METRICS ---
  Overall acceptance:   77.1%
  Bash acceptance:      50.9% ← KEY
  High-risk acceptance: 64.3%
  Low-risk acceptance:  100.0%

--- CLASSIFICATION ---
  Pattern:    Power User (Cautious)
  Archetype:  Strategist

--- WHAT THIS MEANS ---
  You're a sophisticated user who maintains control.
  You use advanced features but scrutinize risky operations.
```

## The Archetypes

| Archetype | Pattern | Historical Parallel |
|-----------|---------|---------------------|
| **Delegator** | Accept everything, fast | Mongol Horde — trust the generals |
| **Autocrat** | Accept everything, slow | Roman Emperor — review but approve |
| **Strategist** | Selective trust, sophisticated | Napoleon — control what matters |
| **Deliberator** | Cautious, slow decisions | Athenian Assembly — thorough but slow |
| **Council** | High variance, uses agents | Venetian Republic — distributed trust |
| **Constitutionalist** | Consistent, rule-based | Constitutional systems — predictable |

## How It Works

Suzerain parses your Claude Code logs (`~/.claude/projects/`) and extracts:
- Tool acceptance/rejection rates
- Decision timing
- Tool diversity and sophistication signals

**Key finding:** Bash acceptance is THE discriminating feature. All other tools have ~100% acceptance.

## Commands

```bash
suzerain analyze           # Analyze your usage
suzerain analyze --export  # Export to JSON
suzerain share --preview   # See what would be shared
suzerain share --confirm   # Share anonymized metrics (opt-in)
```

## Privacy

- **Local-first:** All analysis runs on your machine
- **Opt-in:** Nothing shared without explicit consent
- **Minimal:** Only aggregate metrics, never content
- **Transparent:** Preview exactly what would be shared

## The Research

With n=1 real data + simulated personas, we found:
- **Bash acceptance** is the only feature with variance (others ~100%)
- Users cluster into 2 axes: **Sophistication** × **Caution**
- 6 narrative archetypes map onto 4 empirical quadrants

See [docs/METHODOLOGY.md](docs/METHODOLOGY.md) for honest methodology disclosure.

## Contributing

We need more data to validate the archetypes. If you run `suzerain analyze` and find it interesting, consider:

```bash
suzerain share --preview  # See what would be shared
suzerain share --confirm  # Help improve the research
```

## License

MIT

---

*"What kind of AI ruler are you?"*
