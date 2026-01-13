# Feature Analysis: What Actually Matters for Governance Classification

> Before building features, understand what varies and why.
> **UPDATE: Now with empirical data from 62 real sessions.**

---

## Empirical Reality (From Actual Data)

**From 62 sessions, 5,939 tool calls:**

### The Brutal Truth

| Feature | Distribution | Discriminates? |
|---------|--------------|----------------|
| Overall acceptance rate | 74% of sessions = 100%, 21% = <50% | **Bimodal, not useful** |
| Bash acceptance | 53% overall, 0-100% per session | **YES - key discriminator** |
| All other tools | 100% acceptance | **NO - no variance** |
| Decision time | 62% < 500ms, 12% > 15s | **Skewed, maybe useful** |
| Parallel tools | 99.9% single tool | **NO - too rare** |
| Agent usage | 26% of sessions | **Binary only** |

### What This Means

**Bash is the only tool with governance variance.**

Every other tool (Read, Edit, Write, Glob, Grep, etc.) has 100% acceptance. Users don't discriminate on those.

The real question is: **How do you handle Bash commands?**

---

## Actual Distribution Findings

### Acceptance Rate is Bimodal
```
Distribution of per-session acceptance rates:
  0-50%      ██████ 21% (13 sessions)
  50-75%      2% (1)
  75-90%      2% (1)
  90-100%     2% (1)
  100%       ██████████████████████ 74% (46 sessions)
```

**Interpretation:** Sessions are either "accept everything" OR "reject a lot". Almost nothing in between. The middle archetypes (Council, Deliberator) may not exist in practice.

### Decision Time is Power-Law
```
Distribution:
  <500ms     ██████████████████ 62% (instant)
  500ms-2s   ███ 11%
  2s-5s      ██ 7%
  5s-15s     ██ 8%
  >15s       ███ 12% (very slow)
```

**Interpretation:** Most decisions are instant (< 500ms = not reading). But 12% take > 15 seconds. There are two modes: rubber-stamping and long deliberation.

### Bash is THE Governance Gatekeeper
```
Tool acceptance rates:
  Bash:      53.2% (only tool with variance)
  Read:      100%
  Edit:      100%
  Write:     100%
  Glob:      100%
  Grep:      100%
  ...all others: 100%
```

**Interpretation:** Governance happens at the Bash prompt. Everything else is auto-approved. The real question is: **Do you trust shell commands?**

### Session Depth is Log-Normal
```
  Min:    4 messages
  Max:    4694 messages
  Mean:   307
  Median: 30
```

**Interpretation:** Most sessions are short (median 30), but some are very long (max 4694). The distribution is heavily right-skewed.

---

## Revised Archetype Hypothesis

Based on actual data, the 6 archetypes may collapse to **2-3 real patterns:**

### Pattern 1: Bash Trusters (74% of sessions)
```
acceptance_rate = 100%
bash_acceptance = 100%
decision_time = fast (<500ms)
```
**Profile:** Accept everything including shell commands. Either high trust or not paying attention.

### Pattern 2: Bash Skeptics (21% of sessions)
```
acceptance_rate < 50%
bash_acceptance < 50%
decision_time = mixed
```
**Profile:** Reject many Bash commands. Governance focused on shell execution.

### Pattern 3: Deliberators (rare, ~5% maybe)
```
acceptance_rate = high
bash_acceptance = moderate
decision_time = slow (>5s)
```
**Profile:** Accept most things but take time to review. May or may not exist in practice.

---

## Honest Assessment of Features

### Features That Matter
1. **`bash_acceptance_rate`** — The only tool with variance. This IS the governance signal.
2. **`decision_time_distribution`** — Bimodal: instant vs deliberate.
3. **`session_acceptance_rate`** — Bimodal: 100% vs <50%.

### Features That DON'T Matter (No Variance)
1. **`read_acceptance_rate`** — Always 100%
2. **`edit_acceptance_rate`** — Always 100%
3. **`write_acceptance_rate`** — Always 100%
4. **`glob_acceptance_rate`** — Always 100%
5. **`parallel_tool_ratio`** — 99.9% single tool

### Features That Need More Data
1. **`per_user_patterns`** — We only see sessions, not users
2. **`trust_evolution`** — Does behavior change over time?
3. **`correction_rate`** — Hard to detect from logs

---

## Implications for Suzerain

### The Hard Truth
The 6-archetype model may be **theoretical overkill**. Real usage shows:
- Most sessions: 100% acceptance (Delegator)
- Some sessions: Heavy Bash rejection (Strategist? Autocrat?)
- Everything else: Noise

### What We Can Actually Measure
1. Are you a Bash Truster or Bash Skeptic?
2. Do you deliberate (slow) or rubber-stamp (fast)?
3. Do you use agents (Task tool) or not?

### What We Can't Measure (Yet)
1. Intent behind rejections
2. Quality of decisions (good rejection vs paranoid rejection)
3. Outcomes (did the acceptance lead to good/bad results?)

---

## Feature Categories

### Category 1: CONTROL (Basic Acceptance)

These are table stakes. Everyone gets measured on these.

| Feature | What It Measures | Power User Signal |
|---------|------------------|-------------------|
| `acceptance_rate` | % tools accepted | Moderate (not extreme) |
| `rejection_rate` | % tools rejected | Low but non-zero |
| `auto_approval_rate` | % accepted < 1s | Low (they review) |

**Problem:** These don't discriminate well. A thoughtful reviewer and a paranoid person both have moderate acceptance rates.

### Category 2: DISCRIMINATION (Context Sensitivity)

This is where power users separate from normies.

| Feature | What It Measures | Power User Signal |
|---------|------------------|-------------------|
| `trust_by_tool_variance` | Std dev of acceptance rates across tools | High (different treatment) |
| `risk_adjusted_trust` | Difference between low-risk and high-risk acceptance | High delta |
| `bash_vs_read_ratio` | Bash acceptance / Read acceptance | < 0.7 (strategic caution) |
| `tool_discrimination_score` | Entropy of per-tool acceptance rates | High (varied, not uniform) |

**Key insight:** Normies treat all tools the same. Power users discriminate.

```python
# Normie pattern
Read: 80%, Bash: 80%, Edit: 80%  # Uniform = no discrimination

# Power user pattern
Read: 100%, Bash: 45%, Edit: 95%  # Varied = strategic trust
```

### Category 3: TEMPO (Decision Timing)

Speed reveals cognitive engagement.

| Feature | What It Measures | Power User Signal |
|---------|------------------|-------------------|
| `mean_decision_time_ms` | Average time to accept/reject | Moderate (1-5s) |
| `decision_time_by_risk` | Time for high-risk vs low-risk | Higher for high-risk |
| `speed_consistency` | CV of decision times | Low (consistent process) |
| `snap_judgment_rate` | % decisions < 500ms | Low (they actually read) |

**Key insight:**
- < 500ms = Not reading, rubber stamping
- 500ms - 3000ms = Reading and deciding
- > 10000ms = Distracted or paralyzed

### Category 4: SOPHISTICATION (Advanced Patterns)

These features only matter for the 5%.

| Feature | What It Measures | Power User Signal |
|---------|------------------|-------------------|
| `agent_spawn_rate` | Task tool usage / total tools | > 5% |
| `parallel_tool_ratio` | Multi-tool assistant turns / total turns | > 10% |
| `tool_diversity` | Unique tools used / sessions | High |
| `glob_before_read_ratio` | Do they search before reading? | High |
| `grep_efficiency` | Grep calls / Read calls | High (targeted search) |

**Power user workflow:**
```
Glob → Grep → Read (specific)    # Surgical
vs
Read → Read → Read → Read        # Shotgun
```

### Category 5: SESSION PATTERNS

How do they structure work?

| Feature | What It Measures | Power User Signal |
|---------|------------------|-------------------|
| `mean_session_depth` | Messages per session | Higher (deep work) |
| `tool_calls_per_session` | Tool usage intensity | Higher |
| `session_completion_rate` | % sessions ending cleanly | Higher (not abandoned) |
| `correction_rate` | "No, do X instead" messages / total | Lower |
| `first_try_success` | Accepted tools without follow-up correction | Higher |

### Category 6: EVOLUTION (Learning Patterns)

Do they adapt over time?

| Feature | What It Measures | Power User Signal |
|---------|------------------|-------------------|
| `trust_trajectory` | Slope of acceptance rate over time | Stable or increasing |
| `tool_adoption_curve` | New tools used over time | Expanding repertoire |
| `rejection_specificity` | Do rejections become more targeted? | Yes |

---

## Preemptive Feature Importance Hypothesis

Before we have clustering data, here's my prediction of what will matter:

### HIGH IMPORTANCE (Will separate archetypes)

1. **`trust_by_tool_variance`** — The killer feature. Discriminators vs non-discriminators.
2. **`bash_acceptance_rate`** — The highest-governance tool. Reveals true caution level.
3. **`snap_judgment_rate`** — Separates reviewers from rubber-stampers.
4. **`agent_spawn_rate`** — Only power users use agents.

### MEDIUM IMPORTANCE (Will refine classification)

5. **`decision_time_by_risk`** — Do they slow down for risky tools?
6. **`tool_diversity`** — Do they know the full toolkit?
7. **`correction_rate`** — Effective prompters vs trial-and-error.
8. **`session_depth`** — Deep workers vs quick queries.

### LOW IMPORTANCE (Noisy or uniform)

9. **`mean_decision_time_ms`** — Too much variance from distraction.
10. **`total_acceptance_rate`** — Doesn't discriminate well.
11. **`session_count`** — Usage frequency ≠ governance style.

---

## Expected Archetype Distribution

Based on the features above, here's my prediction:

| Archetype | Expected % | Defining Features |
|-----------|------------|-------------------|
| **Delegator** | 40-50% | High acceptance (>90%), low discrimination, fast |
| **Autocrat** | 25-35% | High acceptance (>85%) but slow, uniform treatment |
| **Strategist** | 10-15% | High tool variance, high risk delta, agents |
| **Deliberator** | 5-10% | Slow, high correction rate, high rejection |
| **Council** | 3-5% | Very high tool variance, explicit rules |
| **Constitutionalist** | 2-5% | High consistency, moderate everything |

**The long tail:** Most users are either trusting everything or reviewing everything. Few are sophisticated.

---

## Power User Signatures

### The Agent Orchestrator (Rare, ~2%)
```python
agent_spawn_rate > 0.1           # Uses Task tool heavily
parallel_tool_ratio > 0.2        # Multiple tools per turn
tool_diversity > 15              # Knows all tools
correction_rate < 0.05           # Gets it right first try
```

### The Surgical Reviewer (Rare, ~5%)
```python
bash_acceptance_rate < 0.6       # Careful with commands
read_acceptance_rate > 0.95      # Trusts information gathering
decision_time_by_risk > 2.0      # Slows down for risk
trust_by_tool_variance > 0.3     # Highly discriminating
```

### The Effective Delegator (Uncommon, ~10%)
```python
acceptance_rate > 0.9            # Trusts AI
snap_judgment_rate < 0.3         # But actually reads
correction_rate < 0.1            # Rarely needs to fix
session_depth > 20               # Deep focused work
```

### The Anxious Reviewer (Common, ~30%)
```python
acceptance_rate < 0.7            # Suspicious
decision_time_ms > 5000          # Paralyzed
trust_by_tool_variance < 0.1     # Treats all tools same
correction_rate > 0.2            # Lots of back-and-forth
```

### The Rubber Stamper (Most Common, ~45%)
```python
acceptance_rate > 0.95           # Accept everything
snap_judgment_rate > 0.5         # Instantly
trust_by_tool_variance < 0.05    # No discrimination
session_depth < 10               # Quick interactions
```

---

## Feature Engineering Priorities

### Must Have (v1)
1. `acceptance_rate` (overall)
2. `acceptance_rate_by_tool` (per tool)
3. `trust_by_tool_variance`
4. `bash_acceptance_rate` (specifically)
5. `mean_decision_time_ms`
6. `snap_judgment_rate`
7. `agent_spawn_rate`

### Should Have (v2)
8. `decision_time_by_risk`
9. `correction_rate`
10. `tool_diversity`
11. `session_depth`
12. `parallel_tool_ratio`

### Nice to Have (v3)
13. `glob_before_read_ratio`
14. `trust_trajectory`
15. `session_completion_rate`
16. `first_try_success`

---

## Validation Strategy

Before trusting any classification:

1. **Check feature distributions** — Are they bimodal? Normal? Power law?
2. **Correlation matrix** — Which features are redundant?
3. **PCA** — How many dimensions actually matter?
4. **Silhouette analysis** — Do clusters exist, or is it continuous?

**Expected findings:**
- `acceptance_rate` will be bimodal (high vs low)
- `trust_by_tool_variance` will be exponential (most = 0, few = high)
- `agent_spawn_rate` will be exponential (most = 0)
- 2-3 PCA components will explain 80% of variance

---

## The Honest Prediction

After building all these features and running clustering:

**We'll probably find 3 real clusters, not 6:**
1. **Trusters** — High acceptance, no discrimination, fast
2. **Reviewers** — Moderate acceptance, no discrimination, slow
3. **Strategists** — Moderate acceptance, high discrimination, variable speed

The other archetypes (Council, Constitutionalist, Deliberator) may be:
- Subclusters within the main three
- Too rare to reliably detect
- Theoretical constructs that don't exist in practice

**This is fine.** We start with 6 archetypes for narrative richness, but let the data tell us what's real.

---

## Implementation Status

The empirical findings have been implemented in `scripts/parse_claude_logs.py`:

### classify_archetype_empirical()

The classification now uses a two-tier approach:

**Tier 1: Primary Pattern (Empirical)**
Based on what the data actually shows:
```python
if bash_rate >= 0.9 and overall_rate >= 0.9:
    pattern = "Bash Truster"  # 74% of sessions
elif bash_rate < 0.6 or overall_rate < 0.5:
    pattern = "Bash Skeptic"  # 21% of sessions
elif decision_time > 5000:
    pattern = "Deliberator"   # ~5% of sessions
```

**Tier 2: Narrative Archetype**
Maps patterns to the 6 archetypes for storytelling:
- **Delegator**: Fast Bash Trusters (snap_rate > 0.5)
- **Autocrat**: Slow Bash Trusters (reviews but accepts)
- **Strategist**: High risk discrimination (low Bash, high safe tools)
- **Deliberator**: Slow decisions (> 5s mean)
- **Council**: High tool variance (stdev > 0.25)
- **Constitutionalist**: High session consistency (> 0.85)

### Key Features Used

```python
key_features = {
    "bash_acceptance_rate": 50.5%,     # THE discriminator
    "overall_acceptance_rate": 76.9%,
    "snap_judgment_rate": 63.3%,        # < 500ms decisions
    "risk_trust_delta": +36.2%,         # safe - risky acceptance
}
```

### Exports

Running `python scripts/parse_claude_logs.py --export` generates:
- `~/.suzerain/analysis/governance_profile.json` — Full profile + classification
- `~/.suzerain/analysis/tool_events.jsonl` — Raw events
- `~/.suzerain/analysis/session_summaries.json` — Per-session data for visualization

---

*"In theory, theory and practice are the same. In practice, they're not."* — Yogi Berra
