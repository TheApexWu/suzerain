# Privacy

## What We Collect (Opt-In Only)

Data is **never** collected unless you explicitly run `suzerain share --confirm`.

When you do share, here's exactly what gets sent:

```json
{
  "summary": {
    "sessions_analyzed": 73,
    "total_tool_calls": 6654,
    "data_days": 27
  },
  "governance": {
    "bash_acceptance_rate": 0.56,
    "overall_acceptance_rate": 0.87,
    "high_risk_acceptance": 0.62,
    "snap_judgment_rate": 0.63
  },
  "sophistication": {
    "agent_spawn_rate": 0.08,
    "tool_diversity": 7.2,
    "session_depth": 91
  },
  "classification": {
    "pattern": "Power User (Cautious)",
    "archetype": "Strategist",
    "sophistication_score": 0.75,
    "caution_score": 0.80
  }
}
```

That's it. Numbers and labels.

## What We DON'T Collect

- Prompts or conversations
- File paths or filenames
- Code snippets
- Command contents (we know you ran Bash, not what you ran)
- Project names
- Timestamps (only durations/counts)
- IP addresses (server doesn't log them)
- Machine identifiers
- Username or email

## Fingerprinting Risk

Honest disclosure: aggregate metrics can theoretically fingerprint users.

If you have exactly 73 sessions with exactly 6,654 tool calls over exactly 27 days, that combination might be unique. We mitigate this by:

1. **Rounding values** - Rates are rounded to 3 decimal places, counts to nearest 10
2. **Bucketing session depth** - Instead of exact counts, we use ranges
3. **No persistent ID** - Each share is independent, no correlation between submissions

However, if you share multiple times with identical rare values, correlation is theoretically possible. If this concerns you, don't share.

## Anonymous ID (If Implemented)

If we add repeat-user tracking for longitudinal analysis:

- Generated locally: `SHA-256(random UUID stored in ~/.suzerain/id)`
- One-way hash - cannot be reversed to identify you
- UUID never leaves your machine
- You can delete `~/.suzerain/id` to get a new anonymous ID
- We have no way to connect the ID to you personally

## Data Retention

- Shared data is stored for research purposes
- No individual data is ever published - only aggregates
- Data may be used to improve classification thresholds
- You can request deletion (open an issue with your anonymous ID hash)

## Why We Want Data

n=1 isn't research. We need diverse samples to:

1. Validate that archetypes reflect real behavioral patterns
2. Tune classification thresholds empirically
3. Understand how different user types interact with AI tools

Your participation helps, but it's entirely optional.

## Verification

The share code is open source: `src/suzerain/cli.py`, function `preview_share()`.

Run `suzerain share --preview` to see exactly what would be sent before you decide.

## Questions

Open an issue: https://github.com/TheApexWu/suzerain/issues
