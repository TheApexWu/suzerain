# The Six Archetypes of AI Governance

> *"The suzerain rules even where there are other kings. There is no territory outside his claim."*

## What is a Suzerain?

In feudal systems, a **suzerain** wasn't a direct ruler—they were the power *above* the local kings. They governed *through* others, exercising authority by claim rather than direct control.

When you use AI coding tools, you are the suzerain:
- The AI proposes; you dispose
- The AI generates; you accept or reject
- The AI executes; you bear the consequences

Every approval is an exercise of your claim. Every rejection is a boundary of your territory. **Suzerain analyzes how you rule.**

## The Three-Axis Framework

Classification uses three conceptually distinct axes:

| Axis | What It Measures | Range |
|------|------------------|-------|
| **Trust Level** | Bash acceptance rate | 0-100% |
| **Sophistication** | Agent usage, tool diversity, session depth | 0-1 |
| **Variance** | Cross-context consistency | 0-1 |

**Trust** is the primary signal. All other tools are rubber-stamped (~100%). Governance happens at the Bash prompt.

**Sophistication** captures power user patterns: spawning agents, using diverse tools, running deep sessions.

**Variance** detects context-dependent governance: different rules for different projects.

**Note on independence:** Simulated data shows moderate correlation (|r| ~ 0.4) between Trust-Sophistication and Sophistication-Variance. This is likely a simulation artifact—the personas were designed as stereotypes with baked-in correlations. Real-world data needed to validate axis independence. See `docs/METHODOLOGY.md` for details.

## Patterns, Not Personality

**These archetypes describe recent behavior, not who you are.**

The same user may:
- Be a **Delegator** during rapid prototyping
- Shift to **Strategist** when touching production code
- Become **Adaptive** across multiple projects with different stakes

The patterns have family resemblance—overlapping characteristics, not sharp boundaries.

## The Six Archetypes

| Archetype | Rule | Bottleneck | Parallel |
|-----------|------|------------|----------|
| **Adaptive** | Variance ≥ 0.3 | Context-switching overhead | Akbar the Great |
| **Delegator** | Trust > 80%, Soph < 0.4 | Error discovery downstream | Cyrus the Great |
| **Council** | Trust > 70%, Soph ≥ 0.4 | Coordination overhead | Ottoman Sultan |
| **Guardian** | Trust < 50%, Soph < 0.4 | Throughput limited by review | Ming Dynasty |
| **Strategist** | Trust < 70%, Soph ≥ 0.4 | Decision overhead on edge cases | Napoleon |
| **Constitutionalist** | Fallback | Rule rigidity | Hammurabi |

Priority order: Variance checked first. High-variance users are Adaptive regardless of trust/sophistication.

---

## 1. THE ADAPTIVE

**Language Game:** The Context Game

You govern differently depending on context. Maintenance project? Trust flows freely. Critical build? Every command scrutinized. Same AI, same you, different rules.

**Signature:**
```
variance:       > 0.3
trust:          Varies by context
sophistication: Any
```

**Bottleneck:** Context-switching overhead

Your adaptability requires constant recalibration. Each project switch costs cognitive load. You maintain different mental models for different contexts.

**Historical Parallel:** Akbar the Great — one Mughal throne, different laws for each faith

**Recommendations:**
1. Codify context rules in per-project CLAUDE.md files
2. Use project-specific permission settings
3. Consider whether low-trust contexts are actually higher risk, or just feel that way
4. Document your rules so you don't have to remember them

---

## 2. THE DELEGATOR

**Language Game:** The Acceptance Game

You treat AI output as draft code to be merged, not proposals to be reviewed. Throughput above all—tokens in, code out.

**Signature:**
```
trust:          > 80%
sophistication: < 0.4
variance:       < 0.3
```

**Bottleneck:** Error discovery downstream

You accept most suggestions quickly. Errors surface later—in tests, in production, in code review. The bottleneck isn't decision speed, it's rework.

**Historical Parallel:** Cyrus the Great — let satraps rule, but the empire is mine

**Recommendations:**
1. Add verification for destructive commands (rm, DROP, force push)
2. Use --dry-run flags when available
3. Set up pre-commit hooks as your safety net
4. Spot-check 1 in 10 suggestions

---

## 3. THE COUNCIL

**Language Game:** The Orchestration Game

You don't just use AI—you deploy it. Agents, parallel tasks, complex workflows. You're the conductor, AI is the orchestra.

**Signature:**
```
trust:          > 70%
sophistication: ≥ 0.4
variance:       < 0.3
```

**Bottleneck:** Coordination overhead

Managing multiple agents and workflows has overhead. The bottleneck is orchestration—keeping track of what's running, what's done, what needs attention.

**Historical Parallel:** Ottoman Sultan — viziers execute, but the Sublime Porte decides

**Recommendations:**
1. Use TodoWrite to track parallel workstreams
2. Batch similar operations rather than interleaving
3. Set up project-specific contexts to reduce re-explanation
4. Document your workflows for future you

---

## 4. THE GUARDIAN

**Language Game:** The Protection Game

You protect the gates. Every command is reviewed carefully before execution. Minimal AI authority—you're the final arbiter.

**Signature:**
```
trust:          < 50%
sophistication: < 0.4
variance:       < 0.3
```

**Bottleneck:** Throughput limited by review

Your careful review limits velocity. This is appropriate for high-stakes environments, expensive otherwise.

**Historical Parallel:** Ming Dynasty — the Great Wall exists because the Emperor commands it

**Recommendations:**
1. Identify truly safe operations and fast-track them
2. Use AI for exploration, manually execute critical commands
3. Your caution is valuable for high-stakes work—own it
4. Consider auto-approving read-only operations

---

## 5. THE STRATEGIST

**Language Game:** The Discrimination Game

You rule differently depending on the stakes. Safe operations flow through unchallenged; risky operations face scrutiny.

**Signature:**
```
trust:          < 70%
sophistication: ≥ 0.4
variance:       < 0.3
```

**Bottleneck:** Decision overhead on edge cases

Your selective trust is efficient for clear-cut cases. The bottleneck is ambiguous commands—things that might be risky.

**Historical Parallel:** Napoleon — trusts marshals for most battles, personally commands Austerlitz

**Recommendations:**
1. Codify your rules: which patterns always need review?
2. Build muscle memory for common safe Bash patterns
3. Pre-approve specific commands you run frequently
4. Trust your instincts faster on familiar patterns

---

## 6. THE CONSTITUTIONALIST

**Language Game:** The Consistency Game

Your rule is predictable, session to session. You've developed stable patterns—implicit laws governing your AI interactions.

**Signature:**
```
trust:          50-80%
sophistication: 0.3-0.5
variance:       < 0.2
```

**Bottleneck:** Rule rigidity

Consistent patterns are efficient but can become rigid. The bottleneck is adaptation—when situations call for different approaches, habits may override judgment.

**Historical Parallel:** Hammurabi — the code is the code, carved in stone for all

**Recommendations:**
1. Periodically audit your implicit rules
2. Try different approaches in low-stakes contexts
3. Codify your patterns explicitly in CLAUDE.md
4. Your consistency is transferable—teach it to others
