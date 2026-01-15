# Methodology: An Honest Account

> *"The first principle is that you must not fool yourself — and you are the easiest person to fool."* — Feynman

---

## ⚠️ Epistemic Status: Hypothesis-Generating

**This tool is NOT a validated psychometric instrument.**

| What It Is | What It Isn't |
|------------|---------------|
| Exploratory analysis | Rigorous personality assessment |
| Behavioral patterns from logs | Stable psychological traits |
| Heuristic thresholds | Empirically validated cutoffs |
| Hypothesis-generating | Hypothesis-testing |
| N=1 real user + simulations | Diverse validated sample |

**The archetypes describe recent behavior, not who you are.** Patterns shift. The same person may be a Delegator on Monday and a Strategist on Friday. Context matters more than category.

**Thresholds are hand-tuned.** Values like "bash_rate < 0.6 = cautious" are interpretive choices, not discoveries. They discriminate on simulated data but haven't been validated on diverse real users.

**We need your data to improve.** Run `suzerain share --preview` to see what would be shared. Participation helps build a real dataset.

---

## What We Did

### Phase 1: Single-User Analysis (n=1)

Parsed 62 Claude Code sessions from one user (the author):
- 5,939 tool calls over 24 days
- Extracted: tool name, acceptance/rejection, decision time

**Key Finding:** Bash acceptance is THE only feature with variance.

| Tool | Acceptance Rate |
|------|-----------------|
| Bash | 50.5% |
| Read | 100% |
| Edit | 100% |
| Write | 100% |
| Glob | 100% |
| All others | 100% |

**Implication:** Governance happens at the Bash prompt. Everything else is rubber-stamped.

### Phase 2: Feature Exploration

Searched for subtle features that might discriminate:

| Feature | Variance | Useful? |
|---------|----------|---------|
| Agent/Task usage | 0-41% ratio | **Yes** - power user signal |
| Tool diversity | 1-12 unique/session | **Yes** |
| Session depth | 1-1345 calls | **Yes** |
| Parallel tools | 99.9% single | **No** - too rare |
| Tool sequences | Bash-dominated | **No** |

### Phase 3: Simulated Validation

Created 11 user personas based on realistic archetypes:
- **Casual:** Junior dev, hobbyist, Copilot refugee
- **Power:** Senior SWE, staff engineer, DevOps, data scientist
- **Cautious:** Security engineer, compliance reviewer, paranoid senior

Generated 240 synthetic sessions (18,810 tool calls) and tested classification.

**Result:** Features discriminate as expected.

| User Type | Sophistication | Caution | Agent Rate |
|-----------|---------------|---------|------------|
| Casual | 0.03 | 0.07 | 0% |
| Power | 0.89 | 0.47 | 22% |
| Cautious | 0.69 | 1.00 | 7% |

---

## What We Don't Know

### Unknown #1: External Validity
Our simulations are based on assumptions about how different users behave. These assumptions may be wrong. We need real data from diverse users to validate.

### Unknown #2: Stability
Is "governance style" stable across time and contexts? Our n=1 data covers 24 days on one project type. We don't know if behavior changes:
- By project (greenfield vs production)
- By time of day (morning focus vs evening tired)
- By stakes (personal project vs work)

### Unknown #3: Causation
We observe correlations between features and user types. We don't know:
- Does experience cause different behavior, or personality?
- Does tool usage shape governance, or governance shape usage?
- Are there confounding factors we're missing?

### Unknown #4: Archetype Reality
The 6 archetypes (Delegator, Autocrat, Strategist, etc.) are narrative constructs. The data suggests 3-4 real clusters. The mapping from clusters to archetypes is interpretive, not empirical.

---

## Limitations

### Limitation 1: Sampling Bias
Early adopters of a tool that analyzes AI usage are not representative of:
- General developers
- Non-developers who use AI tools
- Users who distrust AI analysis tools (ironic selection bias)

### Limitation 2: Measurement Validity
We measure:
- Tool acceptance/rejection
- Decision timing
- Tool sequences

We don't measure:
- Intent behind decisions
- Quality of outcomes
- Counterfactual (what would have happened with different governance)

### Limitation 3: Claude Code Specific
Our analysis only works with Claude Code logs. Findings may not generalize to:
- Cursor
- GitHub Copilot
- Other AI coding tools

### Limitation 4: Privacy-Utility Tradeoff
To protect privacy, we don't collect:
- Actual prompts
- File contents
- Specific commands

This limits our ability to understand context-dependent behavior.

---

## The Data We Collect (Opt-In Only)

If you choose to share, we collect **only aggregate metrics**:

```json
{
  "user_id": "anonymous_hash",
  "collected_at": "2025-01-12T00:00:00Z",

  "summary": {
    "sessions_analyzed": 62,
    "total_tool_calls": 5939,
    "data_days": 24
  },

  "governance_features": {
    "bash_acceptance_rate": 0.505,
    "overall_acceptance_rate": 0.769,
    "high_risk_acceptance": 0.639,
    "low_risk_acceptance": 1.0,
    "mean_decision_time_ms": 8068,
    "snap_judgment_rate": 0.633
  },

  "sophistication_features": {
    "agent_spawn_rate": 0.086,
    "tool_diversity": 3.7,
    "mean_session_depth": 94,
    "power_session_ratio": 0.213,
    "surgical_ratio": 0.45,
    "edit_intensity": 0.166
  },

  "classification": {
    "primary_pattern": "Power User (Cautious)",
    "sophistication_score": 0.75,
    "caution_score": 0.80,
    "archetype": "Strategist"
  }
}
```

### What We DON'T Collect
- Prompts or conversations
- File paths or names
- Command contents
- Code snippets
- Project names
- Timestamps (only duration)
- IP addresses (anonymized at collection)

---

## How to Verify

All code is open source:
- `scripts/parse_claude_logs.py` — Log parsing
- `scripts/simulate_users.py` — Simulation
- `scripts/test_classification.py` — Validation

You can:
1. Run locally without sharing anything
2. Inspect exactly what would be shared before opting in
3. Audit the collection endpoint code

---

## Research Questions

With sufficient data, we want to answer:

1. **How many real clusters exist?** (Is it 3? 6? Continuous?)
2. **What predicts archetype?** (Role? Experience? Personality?)
3. **Does governance style change over time?**
4. **Are there optimal styles for different contexts?**
5. **Can we provide useful recommendations?**

---

## How to Participate

```bash
pip install suzerain
suzerain analyze          # See your profile locally
suzerain share --preview  # See what would be shared
suzerain share --confirm  # Opt-in to share
```

Your participation helps build a real dataset for understanding human-AI governance patterns. No individual data is ever published — only aggregates.

---

*"In God we trust. All others must bring data."* — Deming
