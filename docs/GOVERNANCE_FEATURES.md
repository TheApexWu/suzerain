# Governance Features: What We Measure and Why

> Every feature must answer: "What does this reveal about how someone governs?"

---

## The Core Governance Dimensions

Human governance of AI tools operates across **5 fundamental dimensions**:

```
1. CONTROL     → How much do you personally decide vs delegate?
2. TEMPO       → How quickly do you make decisions?
3. TRUST       → Is trust uniform or context-dependent?
4. CORRECTION  → How do you respond when AI fails?
5. CONSISTENCY → Are you predictable or adaptive?
```

Each dimension has measurable proxies. Here's what they mean.

---

## Dimension 1: CONTROL (Centralization vs Delegation)

### The Governance Question
> "Do you make every decision, or do you let the AI act autonomously?"

This is the **most fundamental** governance dimension. Throughout history, rulers have faced this tradeoff:
- **Centralize:** You decide everything. Quality control, but you're the bottleneck.
- **Delegate:** Others (or AI) act on your behalf. Scales, but requires trust.

### Features That Measure Control

#### 1.1 `acceptance_rate`
```python
acceptance_rate = accepted_suggestions / total_suggestions_shown
```

**What it measures:** The percentage of AI suggestions you approve.

**Why it matters:**
- High (>85%): You're delegating heavily. You trust AI judgment.
- Medium (40-85%): Selective approval. You're actively filtering.
- Low (<40%): You're rejecting most suggestions. AI is advisory only.

**Historical parallel:**
- Roman Emperor: Low acceptance of advice from Senate (centralized)
- Mongol Khan: High acceptance of generals' field decisions (delegated)

**Nuance:** Raw acceptance rate can be misleading. Someone might accept 90% because AI is good, or because they're not paying attention. Need to cross-reference with `edit_after_accept_rate`.

#### 1.2 `explicit_rejection_rate`
```python
explicit_rejection_rate = explicitly_rejected / total_suggestions_shown
```

**What it measures:** How often you actively say "no" vs just ignoring.

**Why it matters:**
- High explicit rejection: You're engaged, actively governing.
- Low (mostly ignore): Passive relationship - suggestions happen, you continue working.

**Governance insight:** Active rejection is a form of governance. Ignoring is abdication.

#### 1.3 `auto_execute_ratio`
```python
auto_execute_ratio = auto_executed_actions / total_actions
```

**What it measures:** How often AI acts without waiting for your approval.

**Why it matters:** This is the purest measure of delegation. Did you set up the system to act autonomously, or do you require confirmation for every action?

**Historical parallel:**
- Constitutional limits: Certain actions require approval (declarations of war)
- Standing orders: Routine actions proceed automatically (trade policy)

---

## Dimension 2: TEMPO (Speed vs Deliberation)

### The Governance Question
> "Do you decide quickly, or do you deliberate?"

Speed of decision-making reveals your governance philosophy:
- **Fast:** Bias toward action. Trust your instincts. Risk errors.
- **Slow:** Bias toward caution. Analyze before acting. Risk paralysis.

### Features That Measure Tempo

#### 2.1 `mean_decision_time_ms`
```python
mean_decision_time_ms = mean(time_from_suggestion_to_action)
```

**What it measures:** Average time between seeing a suggestion and acting on it.

**Why it matters:**
- <500ms: Snap judgments. You're pattern-matching, not reading.
- 500-2000ms: Reading and evaluating. Active consideration.
- >2000ms: Deliberating. Possibly comparing to alternatives, checking docs.
- >10000ms: Deep review. Or distracted (need to filter these).

**Historical parallel:**
- Athenian Assembly: Debates lasted hours/days before votes
- Military command: Seconds to decide in battle

**Nuance:** Context matters. 5 seconds on a deploy command is appropriate. 5 seconds on a typo fix is paranoid.

#### 2.2 `decision_time_variance`
```python
decision_time_variance = std(decision_times) / mean(decision_times)
```

**What it measures:** How consistent is your decision speed?

**Why it matters:**
- Low variance: You have a consistent governance rhythm.
- High variance: You're context-sensitive (or erratic).

**Governance insight:** High variance might indicate sophisticated context-awareness (slow for deploys, fast for tests) or chaos (unpredictable mood-based decisions).

#### 2.3 `time_to_first_action`
```python
time_to_first_action = time_from_session_start_to_first_decision
```

**What it measures:** Do you review context before acting, or dive in immediately?

**Why it matters:** Some governance styles emphasize "understanding before acting" (read the briefing) vs "learn by doing" (act and observe).

---

## Dimension 3: TRUST (Uniform vs Context-Dependent)

### The Governance Question
> "Do you trust AI equally for all tasks, or do you differentiate?"

Sophisticated governance involves **domain-specific delegation**:
- Finance ministry handles budgets (trusted for money)
- Military handles defense (trusted for security)
- Neither trusted for the other's domain

### Features That Measure Trust

#### 3.1 `trust_by_context`
```python
trust_by_context = {
    "test": acceptance_rate_for_tests,
    "deploy": acceptance_rate_for_deploys,
    "refactor": acceptance_rate_for_refactors,
    "docs": acceptance_rate_for_documentation,
    "security": acceptance_rate_for_security_related,
}
```

**What it measures:** Does your acceptance rate vary by task type?

**Why it matters:**
- Uniform trust: You treat AI as generally capable or incapable.
- Variable trust: You've learned where AI succeeds and fails.

**Historical parallel:**
- Venetian Republic: Different councils for different domains (Council of Ten for security, Senate for trade)
- Roman Empire: Same emperor decides everything (uniform, centralized)

**Governance insight:** Context-dependent trust is more sophisticated but requires more cognitive overhead.

#### 3.2 `trust_delta_by_risk`
```python
trust_delta = acceptance_rate_low_risk - acceptance_rate_high_risk
```

**What it measures:** Do you trust less when stakes are higher?

**Why it matters:** Rational governance should adjust trust to risk. Trusting AI for a comment fix and a production deploy equally is either naive or highly confident.

**What "high risk" means:**
- Production vs development
- Delete vs read
- External-facing vs internal
- Irreversible vs reversible

#### 3.3 `trust_trajectory`
```python
trust_trajectory = slope(acceptance_rate over time)
```

**What it measures:** Is your trust in AI increasing or decreasing over time?

**Why it matters:**
- Increasing: You're learning to trust (or getting complacent)
- Decreasing: You've been burned (or getting paranoid)
- Stable: Calibrated (or not learning)

---

## Dimension 4: CORRECTION (Response to Failure)

### The Governance Question
> "When AI fails, how do you respond?"

All governance systems fail sometimes. The response reveals character:
- **Punitive:** Reduce trust, increase oversight
- **Adaptive:** Adjust in the specific failure domain
- **Forgiving:** Maintain trust, treat as anomaly

### Features That Measure Correction

#### 4.1 `edit_after_accept_rate`
```python
edit_after_accept_rate = accepts_followed_by_edit / total_accepts
```

**What it measures:** How often do you modify AI output after accepting it?

**Why it matters:**
- Low (<10%): You accept output as-is. High trust or low standards.
- Medium (10-40%): You refine AI output. Collaborative relationship.
- High (>40%): You're using AI as a starting point, not a solution.

**Governance insight:** High edit rate + high acceptance = "rough draft" governance. AI generates, you refine. This is a valid strategy.

#### 4.2 `undo_rate`
```python
undo_rate = undo_actions / total_accepts
```

**What it measures:** How often do you completely reverse an AI action?

**Why it matters:**
- Low: Your acceptance decisions are final (confident or stuck)
- High: You're experimenting and reversing (exploratory governance)

**Historical parallel:**
- Undo = veto power exercised after the fact
- Some systems have no undo (irreversible decisions)

#### 4.3 `trust_after_failure`
```python
trust_after_failure = acceptance_rate_after_undo / acceptance_rate_before_undo
```

**What it measures:** Does your trust drop after AI fails you?

**Why it matters:**
- Drops significantly (<0.8): You're punitive. One failure = reduced trust.
- Stable (0.8-1.0): You're forgiving. Failures are expected.
- Increases (>1.0): You're learning from failures (or compensating oddly).

#### 4.4 `mean_edit_distance`
```python
mean_edit_distance = mean(levenshtein(accepted, final_version))
```

**What it measures:** When you edit, how much do you change?

**Why it matters:**
- Small edits: Variable names, formatting. AI got the logic right.
- Large edits: Restructuring, rewriting. AI got the approach wrong.

**Governance insight:** Large edits suggest you disagree with AI's *reasoning*, not just its output.

---

## Dimension 5: CONSISTENCY (Predictability vs Adaptability)

### The Governance Question
> "Are you predictable, or do you adapt to circumstances?"

Governance styles vary in how consistent they are:
- **Predictable:** Same rules apply always. Easy to understand, but rigid.
- **Adaptive:** Rules change by context. Flexible, but harder to predict.

### Features That Measure Consistency

#### 5.1 `session_consistency`
```python
session_consistency = 1 - std(acceptance_rates_per_session) / mean(acceptance_rates_per_session)
```

**What it measures:** Does your behavior vary session to session?

**Why it matters:**
- High consistency: Your governance is stable. Could be principled or stubborn.
- Low consistency: Your governance varies. Could be adaptive or chaotic.

**Governance insight:** Variance could be:
- Good: Context-appropriate adaptation
- Bad: Mood-driven inconsistency
- Need to distinguish by analyzing *what* drives variance

#### 5.2 `streak_behavior`
```python
streak_score = mean(consecutive_same_decisions) / expected_if_random
```

**What it measures:** Do you make decisions in streaks (accept-accept-accept or reject-reject-reject)?

**Why it matters:**
- High streaks: Momentum-based decisions. Rubber-stamping or blanket rejection.
- Low streaks: Each decision is independent.

**Governance insight:** Streaks suggest you're not evaluating each suggestion individually. You're in a "mode."

#### 5.3 `time_of_day_variance`
```python
acceptance_by_hour = {hour: acceptance_rate for hour in 0..23}
time_variance = std(acceptance_by_hour.values())
```

**What it measures:** Does your governance change by time of day?

**Why it matters:**
- Morning you might be more careful
- Late night you might rubber-stamp
- This reveals when you govern well vs poorly

---

## Feature Interactions (The Interesting Part)

Single features are proxies. **Combinations reveal archetypes.**

### The Bottleneck Pattern
```python
if acceptance_rate > 0.9 and mean_decision_time > 2000:
    # You approve almost everything, but slowly
    # You ARE the bottleneck - nothing moves without your review
    # Historical parallel: Roman Emperor, micromanaging CEO
```

### The Rubber Stamper Pattern
```python
if acceptance_rate > 0.9 and mean_decision_time < 500:
    # You approve almost everything, instantly
    # You're not actually governing - you're auto-approving
    # Historical parallel: Figurehead monarch, captured regulator
```

### The Skeptic Pattern
```python
if acceptance_rate < 0.4 and edit_after_accept_rate > 0.5:
    # You reject most, and heavily edit what you accept
    # AI is a rough-draft generator for you
    # Historical parallel: Editor-in-chief, demanding client
```

### The Delegator Pattern
```python
if auto_execute_ratio > 0.7 and undo_rate < 0.05:
    # Most things run without your approval, and you rarely reverse
    # You've successfully delegated
    # Historical parallel: Mongol Khan, hands-off CEO
```

### The Venetian Pattern
```python
if std(trust_by_context.values()) > 0.3:
    # Your trust varies significantly by domain
    # Different rules for different contexts
    # Historical parallel: Venetian councils, separation of powers
```

---

## Summary: The Feature Set

| Feature | Dimension | What It Reveals |
|---------|-----------|-----------------|
| `acceptance_rate` | Control | Overall delegation level |
| `explicit_rejection_rate` | Control | Active vs passive governance |
| `auto_execute_ratio` | Control | Structural delegation |
| `mean_decision_time_ms` | Tempo | Speed of governance |
| `decision_time_variance` | Tempo | Consistency vs context-sensitivity |
| `time_to_first_action` | Tempo | Review before action |
| `trust_by_context` | Trust | Domain-specific delegation |
| `trust_delta_by_risk` | Trust | Risk-adjusted trust |
| `trust_trajectory` | Trust | Learning over time |
| `edit_after_accept_rate` | Correction | Refinement behavior |
| `undo_rate` | Correction | Reversal frequency |
| `trust_after_failure` | Correction | Response to AI failure |
| `mean_edit_distance` | Correction | Depth of disagreement |
| `session_consistency` | Consistency | Stability of governance |
| `streak_behavior` | Consistency | Independence of decisions |
| `time_of_day_variance` | Consistency | Temporal patterns |

---

## What This Enables

With these features, we can:

1. **Cluster users** - Find natural groupings without assuming archetypes
2. **Characterize clusters** - Describe each group by its feature profile
3. **Map to history** - See if any cluster resembles a historical pattern
4. **Provide recommendations** - "Your bottleneck score is high. Consider delegating low-risk tasks."

---

*"You cannot manage what you cannot measure."* — Peter Drucker

*"But you must understand what you measure, or you'll manage the wrong thing."* — Suzerain
