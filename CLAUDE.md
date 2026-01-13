# Suzerain

> *"Whatever exists without my knowledge exists without my consent."*

**Understand your AI governance style through behavioral analysis.**

## Project Summary

Suzerain analyzes how you use AI coding assistants (Claude Code) and classifies your governance style into historical archetypes.

## Quick Start

```bash
pip install -e .
suzerain analyze
```

## Package Structure

```
src/suzerain/
├── __init__.py      # Package exports
├── models.py        # Data models (ToolEvent, SessionAnalysis, etc.)
├── parser.py        # Claude Code log parser
├── classifier.py    # Archetype classification
└── cli.py           # CLI commands (analyze, share)

scripts/
├── simulate_users.py       # Generate synthetic user personas
├── test_classification.py  # Validate classification on simulated data
└── feature_exploration.py  # Feature distribution analysis

docs/
├── METHODOLOGY.md       # Honest research methodology
├── DATA_SHARING.md      # Privacy and data collection
├── ARCHETYPES.md        # 6 governance archetypes
├── FEATURE_ANALYSIS.md  # Empirical findings
└── ...
```

## Key Findings

From analyzing 62 sessions (~6k tool calls):

1. **Bash acceptance is THE discriminator** — All other tools ~100% acceptance
2. **Users cluster on 2 axes** — Sophistication × Caution
3. **6 archetypes map to 4 quadrants** — Narrative on top of empirical

## CLI Commands

```bash
suzerain analyze           # Analyze your Claude Code usage
suzerain analyze --export  # Export to JSON
suzerain share --preview   # Preview what would be shared
suzerain share --confirm   # Opt-in to share anonymized metrics
```

## Development

```bash
pip install -e ".[dev]"
python scripts/simulate_users.py         # Generate test data
python scripts/test_classification.py    # Validate classification
```

## Key Files to Know

- `src/suzerain/parser.py` — Parses `~/.claude/projects/*.jsonl`
- `src/suzerain/classifier.py` — Classification logic
- `docs/METHODOLOGY.md` — Honest disclosure for HN

## Legacy Code

Old voice wrapper code is archived in `_legacy/`. Not part of current package.
