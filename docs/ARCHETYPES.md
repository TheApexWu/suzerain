# The Six Archetypes of AI Governance

> *"The suzerain rules even where there are other kings. There is no territory outside his claim."*

---

## What is a Suzerain?

In feudal systems, a **suzerain** wasn't a direct ruler—they were the power *above* the local kings. They didn't govern the territory themselves; they governed *through* others, exercising authority by claim rather than direct control.

When you use AI coding tools, you are the suzerain:
- The AI proposes; you dispose
- The AI generates; you accept or reject
- The AI executes; you bear the consequences

Every approval is an exercise of your claim. Every rejection is a boundary of your territory. **Suzerain analyzes how you rule.**

---

## The Core Insight

Every time you accept or reject an AI suggestion, you're exercising sovereignty. These micro-decisions reveal your **governance style**—implicit rules you've developed through practice.

Suzerain doesn't tell you what you did wrong. It tells you **how you rule** and **where your bottleneck is**.

---

## ⚠️ Patterns, Not Personality

**These archetypes describe recent behavior, not who you are.**

Wittgenstein himself would caution against treating categories as essences. The same user may:
- Be a **Delegator** during rapid prototyping
- Shift to **Strategist** when touching production code
- Become a **Deliberator** when learning a new codebase

**The game can be played differently tomorrow.** These patterns have "family resemblance"—overlapping characteristics, not sharp boundaries. You may see yourself in multiple archetypes. That's correct behavior, not classification failure.

**Epistemic status:** Hypothesis-generating, not validated. See [METHODOLOGY.md](METHODOLOGY.md) for honest disclosure.

---

## The Six Archetypes

| Archetype | Language Game | Bottleneck | Historical Parallel |
|-----------|---------------|------------|---------------------|
| **Delegator** | The Acceptance Game | Error discovery downstream | Mongol Horde |
| **Autocrat** | The Review Game | Review time without filtering | Roman Emperor |
| **Strategist** | The Discrimination Game | Decision overhead on edge cases | Napoleon |
| **Deliberator** | The Consideration Game | Decision latency on all operations | Athenian Assembly |
| **Council** | The Orchestration Game | Coordination overhead | Venetian Republic |
| **Constitutionalist** | The Consistency Game | Rule rigidity | Constitutional systems |

---

## 1. THE DELEGATOR

**Language Game:** The Acceptance Game

You treat AI output as draft code to be merged, not proposals to be reviewed. Your language game is one of throughput—tokens in, code out, velocity above all.

**Signature:**
```
bash_acceptance:     > 90%
snap_judgment_rate:  > 50% (decisions < 500ms)
sophistication:      Low (few agents, low diversity)
```

**Bottleneck:** Error discovery happens downstream

You accept most suggestions quickly, which maximizes throughput but means errors surface later—in tests, in production, in code review. The bottleneck isn't decision speed, it's rework.

**Mechanism:** High bash_acceptance + fast decisions = rubber-stamping. This works when AI suggestions are high-quality and low-risk. It fails when a single bad command has cascading consequences.

**Recommendations:**
1. Add verification for destructive commands (rm, DROP, force push)
2. Use --dry-run flags when available
3. Set up pre-commit hooks as your safety net
4. Trust but verify: spot-check 1 in 10 suggestions

**Risk:** A single unreviewed command can undo hours of work

**The Hard Question:** *"Do I trust the AI because it's earned trust, or because reviewing is tedious?"*

---

## 2. THE AUTOCRAT

**Language Game:** The Review Game

You read everything but approve everything. Your language game is one of witnessed consent—you must see the command, understand it, then accept it. The ritual matters even when the outcome is predetermined.

**Signature:**
```
bash_acceptance:     > 85%
snap_judgment_rate:  < 40% (slow decisions)
decision_time:       > 2000ms
```

**Bottleneck:** Review time without filtering

You spend time reviewing suggestions you'll accept anyway. The bottleneck is attention spent on low-risk operations. Your review is thorough but not selective.

**Mechanism:** High acceptance + slow decisions = reviewing but not filtering. You're paying the cost of review without the benefit of rejection. This is cognitive overhead without risk reduction.

**Recommendations:**
1. Identify which tool types actually need review (hint: usually just Bash)
2. Auto-approve Read/Glob/Grep—they're side-effect free
3. Focus review energy on commands with side effects
4. Set up allow-lists for common safe patterns

**Risk:** Review fatigue leads to rubber-stamping when it matters most

**The Hard Question:** *"Am I reviewing everything because I need to, or because I'm afraid to let go?"*

---

## 3. THE STRATEGIST

**Language Game:** The Discrimination Game

You play different games with different tools. Safe operations flow through unchallenged; risky operations face scrutiny. Your language game is contextual—the same AI, different trust levels based on consequences.

**Signature:**
```
risk_delta:          > 30% (safe vs risky trust gap)
bash_acceptance:     40-80% (selective)
sophistication:      Medium-High
```

**Bottleneck:** Decision overhead on edge cases

Your selective trust is efficient for clear-cut cases. The bottleneck is ambiguous commands—things that might be risky. You may over-deliberate on medium-risk operations.

**Mechanism:** High risk_delta = different trust by tool type. You've learned that Read can't hurt you but Bash can. This is rational. The cost is decision latency on commands that fall between clear categories.

**Recommendations:**
1. Codify your rules: which patterns always need review?
2. Build muscle memory for common safe Bash patterns (ls, git status, etc.)
3. Pre-approve specific commands you run frequently
4. Your instincts are good—trust them faster on familiar patterns

**Risk:** Over-indexing on tool type, under-indexing on command content

**The Hard Question:** *"Am I accurately distinguishing strategic from tactical, or am I just delegating what I find boring?"*

---

## 4. THE DELIBERATOR

**Language Game:** The Consideration Game

Every suggestion is a proposal requiring thought. Your language game is deliberative democracy—nothing passes without due consideration. Speed is sacrificed for confidence.

**Signature:**
```
decision_time:       > 5000ms
caution_score:       High
any acceptance rate  (deliberation is about time, not outcome)
```

**Bottleneck:** Decision latency on all operations

You take time on everything, even safe operations. The bottleneck is pure throughput—your careful approach limits how much you can accomplish in a session. Quality is high but quantity suffers.

**Mechanism:** Slow decisions regardless of tool type = deliberative processing. This might indicate uncertainty, learning, or genuine caution. It might also indicate distraction or multitasking.

**Recommendations:**
1. Identify your 'always safe' operations and fast-track them
2. Use AI for exploration in dedicated sessions, then batch approvals
3. If slow due to context-switching, dedicate focused time to AI work
4. Your thoroughness is valuable—apply it selectively to high-stakes decisions

**Risk:** Deliberation becomes procrastination; velocity drops below usefulness

**The Hard Question:** *"Am I deliberating because it improves the output, or because deciding feels risky?"*

---

## 5. THE COUNCIL

**Language Game:** The Orchestration Game

You don't just use AI—you deploy it. Agents, parallel tasks, complex workflows. Your language game is one of coordination—you're the conductor, AI is the orchestra.

**Signature:**
```
agent_spawn_rate:    > 10%
tool_diversity:      > 6 unique tools/session
sophistication:      High
```

**Bottleneck:** Coordination overhead

Managing multiple agents and complex workflows has overhead. The bottleneck is not individual decisions but overall orchestration—keeping track of what's running, what's done, what needs attention.

**Mechanism:** High agent usage + high tool diversity = power user leveraging Claude Code's full capabilities. This is sophisticated usage but requires mental overhead to manage.

**Recommendations:**
1. Use TodoWrite to track parallel workstreams
2. Batch similar operations rather than interleaving
3. Set up project-specific contexts to reduce re-explanation
4. Your orchestration skills are advanced—document your workflows for others

**Risk:** Complexity becomes its own bottleneck; losing track of agent states

**The Hard Question:** *"Am I using agents because they help, or because orchestration feels productive?"*

---

## 6. THE CONSTITUTIONALIST

**Language Game:** The Consistency Game

Your behavior is predictable, session to session. You've developed stable patterns—implicit rules governing your AI interactions. Your language game has a constitution, even if unwritten.

**Signature:**
```
session_consistency: > 0.8
bash_acceptance:     60-90% (moderate, stable)
low variance across sessions
```

**Bottleneck:** Rule rigidity

Consistent patterns are efficient but can become rigid. The bottleneck is adaptation—when situations call for different approaches, your habits may override situational judgment.

**Mechanism:** High session consistency + moderate acceptance = stable behavioral patterns. You've found what works and you stick to it. This is efficient until the situation changes.

**Recommendations:**
1. Periodically audit your implicit rules—are they still serving you?
2. Try different approaches in low-stakes contexts to expand your range
3. Your consistency is a strength—codify it explicitly in CLAUDE.md
4. Teach your patterns to others; consistency is transferable

**Risk:** Habits optimized for past contexts may not fit new ones

**The Hard Question:** *"Do my rules serve me, or do I serve my rules?"*

---

## The Two Axes

Archetypes emerge from two underlying dimensions discovered empirically:

### Sophistication (0-1)

How much of Claude Code's capability do you leverage?

| Score | Pattern | Signals |
|-------|---------|---------|
| 0.0-0.3 | Basic usage | Read, Edit, Bash only |
| 0.3-0.6 | Competent | Uses search tools, some agents |
| 0.6-1.0 | Power user | Heavy agents, deep sessions, diverse tools |

### Caution (0-1)

How selective are you about what you accept?

| Score | Pattern | Signals |
|-------|---------|---------|
| 0.0-0.3 | Trusting | Accepts most suggestions quickly |
| 0.3-0.6 | Balanced | Some review, mostly accepting |
| 0.6-1.0 | Cautious | Reviews carefully, rejects frequently |

### The Four Quadrants → Six Archetypes

```
                         HIGH CAUTION
                              │
       Casual (Cautious)      │      Power User (Cautious)
       → Strategist           │      → Strategist/Council
       → Deliberator          │
                              │
LOW ──────────────────────────┼─────────────────────────── HIGH
SOPHISTICATION                │                    SOPHISTICATION
                              │
       Casual (Trusting)      │      Power User (Trusting)
       → Delegator            │      → Council
       → Constitutionalist    │      → Autocrat
                              │
                         LOW CAUTION
```

---

## Empirical Grounding (Karpathy-Approved)

These archetypes aren't invented—they're discovered from data.

### What We Measured

From 70+ sessions and 6,000+ tool calls:

| Feature | What It Measures | Variance |
|---------|------------------|----------|
| `bash_acceptance_rate` | Trust in shell commands | **THE KEY** (50-100%) |
| `agent_spawn_rate` | Power user signal | 0-40% |
| `tool_diversity` | Sophistication | 1-12 unique |
| `session_depth` | Engagement | 1-1000+ calls |
| `snap_judgment_rate` | Decision speed | 40-90% |

### What We Found

1. **Bash acceptance is THE discriminator.** All other tools have ~100% acceptance.
2. **Sophistication and caution are independent.** You can be cautious AND sophisticated.
3. **Features discriminate between user types.** Simulated personas cluster correctly.

---

## Context-Specific Recommendations

### By Work Domain

| Domain | Recommended | Avoid | Why |
|--------|-------------|-------|-----|
| **Production** | Council, Constitutionalist | Delegator | Errors expensive |
| **Security** | Autocrat, Council | Delegator | Trust must be verified |
| **Architecture** | Strategist, Deliberator | Delegator | Strategic errors compound |
| **Feature Dev** | Council, Strategist | Autocrat | Balance speed and quality |
| **Testing** | Delegator, Constitutionalist | Autocrat | Volume matters, risk low |
| **Prototyping** | Delegator | Deliberator | Speed is everything |

### By Career Stage

| Stage | Recommended | Why |
|-------|-------------|-----|
| **Junior** | Deliberator, Autocrat | Need to learn what AI does |
| **Mid** | Council, Strategist | Balance efficiency with judgment |
| **Senior** | Strategist, Council | Focus on leverage |
| **Lead** | Strategist | Direction, not details |

---

## Ruling Differently Tomorrow

These archetypes describe **recent behavior**, not personality. The same suzerain may:
- Be a **Delegator** during rapid prototyping
- Shift to **Strategist** when touching production code
- Become a **Deliberator** when learning a new domain

Your governance style changes with context, stakes, and experience. If this tool makes you feel *categorized*, we've failed. If it makes you *notice* how you rule, we've succeeded.

---

*"What kind of ruler are you today?"*

---

## Appendix: Theoretical Background

For those interested in the philosophical grounding, Suzerain draws on Wittgenstein's concept of "language games"—the idea that meaning emerges from patterns of use, not definitions. Each archetype represents a different "game" you play with AI: acceptance, review, discrimination, deliberation, orchestration, or consistency.

The key insight: your rules are implicit, revealed only through behavior. Suzerain doesn't give you rules to follow—it shows you the rules you already follow.
