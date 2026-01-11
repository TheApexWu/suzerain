# Governance Archetypes: Definitions, Evaluations, and Recommendations

> 6 archetypes. Each has strengths, weaknesses, and context-specific advice.

---

## The 6 Archetypes

| Archetype | Core Pattern | One-Liner |
|-----------|--------------|-----------|
| **Autocrat** | High manual approval, deliberate decisions | "Nothing moves without my review" |
| **Council** | Context-dependent trust, domain separation | "Different rules for different domains" |
| **Deliberator** | High decision time, high correction rate | "Let me think about this" |
| **Delegator** | High auto-execute, minimal intervention | "I trust the machine" |
| **Constitutionalist** | Stable rules, predictable patterns | "The rules are the rules" |
| **Strategist** | High-level control, operational delegation | "I decide what, AI decides how" |

---

## Archetype 1: AUTOCRAT

*Historical anchor: Roman Emperor (centralized era), Louis XIV*

### Behavioral Signature
```
acceptance_rate:        > 85% (approves most, but manually)
decision_time_ms:       > 2000ms (deliberate review)
auto_execute_ratio:     < 10% (rarely auto-executes)
intervention_rate:      High (frequently stops/modifies)
trust_by_context:       Uniform (same process for all tasks)
```

### Strengths
- **Quality control**: Every output reviewed before execution
- **Consistency**: You know exactly what goes into production
- **Learning**: You see every AI decision, building intuition
- **Accountability**: Clear chain of responsibility (you)

### Weaknesses
- **Bottleneck**: Nothing scales beyond your attention capacity
- **Burnout risk**: Cognitive load of reviewing everything
- **Speed**: Slower than peers who delegate
- **Single point of failure**: You get sick, everything stops

### When Autocrat Works Well
| Context | Fit | Why |
|---------|-----|-----|
| Security-critical code | ✅ Excellent | Every line needs human review |
| Early-stage startup (solo) | ✅ Good | You need to understand everything |
| Regulated industries | ✅ Good | Audit trails, compliance |
| High-velocity team | ❌ Poor | You'll bottleneck the team |
| Routine maintenance | ❌ Poor | Overkill for low-stakes work |

### Recommendations by Work Context

**If you work in Production/DevOps:**
> Your pattern provides safety but slows deployment velocity. Consider: Auto-approve for staging, manual for production. You don't need to review every test run.

**If you work in Security:**
> Your pattern is appropriate. Security review should be deliberate. However, consider automating scanning/linting while keeping human review for logic changes.

**If you work in Management/Architecture:**
> You may be too deep in the weeds. Strategist pattern might serve you better—control the what, delegate the how.

**If you work in Feature Development:**
> You're likely slower than peers. Consider: Trust AI for boilerplate, review only for business logic.

### Alternative Styles to Try
1. **Strategist**: Keep control of architecture decisions, delegate implementation
2. **Council**: Create explicit trust rules by domain instead of reviewing everything
3. **Constitutionalist**: Define rules once, then trust the rules

### The Hard Question
> "Am I reviewing everything because I need to, or because I'm afraid to let go?"

---

## Archetype 2: COUNCIL

*Historical anchor: Venetian Republic, Roman Senate (Republic era)*

### Behavioral Signature
```
acceptance_rate:        50-75% (selective)
trust_by_context:       High variance (different rules per domain)
trust_delta_by_risk:    > 0.3 (trusts low-risk more)
decision_time_variance: High (fast for some, slow for others)
session_consistency:    Medium (adapts to context)
```

### Strengths
- **Sophisticated**: Recognizes that not all decisions are equal
- **Scalable**: Automates low-risk, focuses attention on high-risk
- **Sustainable**: Less cognitive load than Autocrat
- **Defensible**: "I have explicit rules" is auditable

### Weaknesses
- **Complexity**: Must maintain mental model of trust boundaries
- **Edge cases**: What happens when context is ambiguous?
- **Setup cost**: Defining the rules takes upfront work
- **Drift risk**: Rules may become outdated as AI improves

### When Council Works Well
| Context | Fit | Why |
|---------|-----|-----|
| Mixed-risk environments | ✅ Excellent | Different rules for prod vs dev |
| Team leads | ✅ Good | Model for how team should operate |
| Mature codebases | ✅ Good | Known risk boundaries |
| Greenfield/exploration | ⚠️ Mixed | Boundaries not yet clear |
| Solo hacking | ❌ Overkill | Just ship it |

### Recommendations by Work Context

**If you work in Production/DevOps:**
> Your pattern is well-suited. Ensure your trust boundaries are explicit: auto-approve monitoring changes, require review for infrastructure. Document your rules.

**If you work in Security:**
> Good fit, but verify your "low-risk" classification is accurate. Security context can make "routine" changes dangerous. Audit your trust boundaries quarterly.

**If you work in Management/Architecture:**
> Excellent pattern. You're modeling good governance for your team. Make your rules explicit and shareable.

**If you work in Feature Development:**
> Consider whether your context-switching overhead is worth it. If you're constantly re-evaluating "is this high-risk?", you might be faster with simpler rules.

### Alternative Styles to Try
1. **Constitutionalist**: Simplify to fixed rules (less context-switching)
2. **Strategist**: Focus only on architectural decisions, delegate all implementation
3. **Delegator**: For a week, trust everything—see what breaks

### The Hard Question
> "Are my trust boundaries based on real risk, or historical anxiety?"

---

## Archetype 3: DELIBERATOR

*Historical anchor: Athenian Assembly, Academic peer review*

### Behavioral Signature
```
acceptance_rate:        40-60% (selective)
decision_time_ms:       > 3000ms (slow, thoughtful)
edit_after_accept_rate: > 40% (heavy modification)
undo_rate:              > 10% (frequently reverses)
mean_edit_distance:     High (substantial changes)
```

### Strengths
- **Quality**: Thoroughly considered outputs
- **Learning**: Deep engagement with AI suggestions
- **Refinement**: AI as starting point, you as editor
- **Understanding**: You really know your code

### Weaknesses
- **Speed**: Significantly slower than peers
- **Overhead**: Editing everything is exhausting
- **Diminishing returns**: Not all code needs deep review
- **Decision fatigue**: Constant evaluation is draining

### When Deliberator Works Well
| Context | Fit | Why |
|---------|-----|-----|
| Research/exploration | ✅ Excellent | Understanding matters more than speed |
| Learning new domain | ✅ Good | Deliberation builds knowledge |
| Critical algorithms | ✅ Good | Correctness over velocity |
| CRUD features | ❌ Poor | Overkill for routine work |
| Tight deadlines | ❌ Poor | You'll miss them |

### Recommendations by Work Context

**If you work in Production/DevOps:**
> Your pattern may be too slow for incident response. Consider: Deliberate during planning, but have a "fast mode" for emergencies.

**If you work in Security:**
> Deliberation is appropriate for security review. But distinguish between "reviewing for security" and "over-editing for style." Focus your deliberation.

**If you work in Management/Architecture:**
> Your deep engagement is valuable for architectural decisions. But you might be deliberating on implementation details that don't need your attention.

**If you work in Feature Development:**
> You're probably the slowest on your team. This is fine if quality matters more than speed. If not, practice accepting more and editing less.

### Alternative Styles to Try
1. **Council**: Deliberate only on high-risk, accept quickly on low-risk
2. **Strategist**: Deliberate on design, delegate implementation
3. **Delegator**: One week of accepting everything—observe what happens

### The Hard Question
> "Am I deliberating because it improves the output, or because deciding feels risky?"

---

## Archetype 4: DELEGATOR

*Historical anchor: Mongol yasa system, Laissez-faire management*

### Behavioral Signature
```
acceptance_rate:        > 90% (accepts almost everything)
decision_time_ms:       < 500ms (instant decisions)
auto_execute_ratio:     > 50% (high automation)
intervention_rate:      < 5% (rarely intervenes)
undo_rate:              Low (lives with decisions)
```

### Strengths
- **Speed**: Fastest possible workflow
- **Scale**: Can handle high volume
- **Trust**: Demonstrates confidence in AI
- **Low overhead**: Minimal cognitive load

### Weaknesses
- **Risk**: Errors propagate unreviewed
- **Learning**: You don't see what AI is doing
- **Accountability**: "The AI did it" isn't a defense
- **Drift**: You may not notice AI quality degrading

### When Delegator Works Well
| Context | Fit | Why |
|---------|-----|-----|
| Prototyping/hacking | ✅ Excellent | Speed matters, errors cheap |
| Test generation | ✅ Good | Low-risk, high-volume |
| Documentation | ✅ Good | Errors are fixable |
| Production deploys | ❌ Dangerous | Errors are expensive |
| Security | ❌ Dangerous | Trust must be verified |

### Recommendations by Work Context

**If you work in Production/DevOps:**
> ⚠️ Your pattern is high-risk. A single bad auto-approved deploy can cause outages. Add friction for production changes. Keep delegation for staging/dev.

**If you work in Security:**
> ⚠️ This pattern is inappropriate for security work. AI can introduce vulnerabilities you won't catch. Switch to Council or Autocrat for security-relevant code.

**If you work in Management/Architecture:**
> You may be delegating decisions that need your judgment. Architectural mistakes compound. Consider Strategist pattern.

**If you work in Feature Development:**
> Your speed is an asset, but verify AI output occasionally. Schedule weekly review of AI-generated code you've shipped.

### Alternative Styles to Try
1. **Council**: Add minimal review for high-risk actions only
2. **Constitutionalist**: Create rules that force review in specific cases
3. **Autocrat**: One week of reviewing everything—calibrate what you've been missing

### The Hard Question
> "Do I trust the AI because it's earned trust, or because reviewing is tedious?"

---

## Archetype 5: CONSTITUTIONALIST

*Historical anchor: Constitutional democracies, Rule-based systems*

### Behavioral Signature
```
acceptance_rate:        60-80% (moderate)
session_consistency:    > 0.8 (highly consistent)
streak_behavior:        Low (each decision independent)
trust_by_context:       Low variance (uniform rules)
decision_time_ms:       Consistent (same process always)
```

### Strengths
- **Predictability**: Team knows what to expect
- **Fairness**: Same rules apply to all code
- **Simplicity**: No context-switching overhead
- **Auditability**: Rules are explicit and documented

### Weaknesses
- **Rigidity**: Rules may not fit all situations
- **Outdated rules**: Static rules in dynamic environment
- **False security**: Following rules ≠ good outcomes
- **Edge cases**: Rules can't cover everything

### When Constitutionalist Works Well
| Context | Fit | Why |
|---------|-----|-----|
| Regulated industries | ✅ Excellent | Compliance requires consistency |
| Team standardization | ✅ Good | Shared rules reduce friction |
| CI/CD pipelines | ✅ Good | Automation needs fixed rules |
| Exploratory work | ❌ Poor | Rules constrain discovery |
| Rapidly changing domains | ❌ Poor | Rules become stale |

### Recommendations by Work Context

**If you work in Production/DevOps:**
> Your pattern fits well. Ensure rules are documented and version-controlled. Review rules quarterly—are they still appropriate?

**If you work in Security:**
> Good baseline, but security threats evolve. Your rules must evolve too. Schedule rule reviews when new vulnerability classes emerge.

**If you work in Management/Architecture:**
> Your consistency is valuable for team governance. But don't let rules prevent judgment calls. "The rule says X" isn't always right.

**If you work in Feature Development:**
> Your predictability is an asset. But consider: Are you following rules that no longer serve you? Audit your rules for cruft.

### Alternative Styles to Try
1. **Council**: Add context-sensitivity to your rules
2. **Strategist**: Keep rules for implementation, add judgment for design
3. **Deliberator**: Temporarily suspend rules and deliberate—see what you learn

### The Hard Question
> "Do my rules serve me, or do I serve my rules?"

---

## Archetype 6: STRATEGIST (New)

*Historical anchor: Napoleon, Eisenhower, Lee Kuan Yew (operational aspect)*

### Behavioral Signature
```
trust_by_context:       Bimodal (low for strategic, high for tactical)
acceptance_rate:        High for implementation, low for design
decision_time_ms:       Long for architecture, short for code
intervention_type:      "What" not "how"
edit_after_accept_rate: Low (accepts execution, controls direction)
```

### Defining Pattern
The Strategist separates concerns:
- **Strategic decisions** (architecture, design, priorities): Personal control
- **Tactical decisions** (implementation, syntax, boilerplate): Full delegation

```python
# Strategist detection
if (trust_by_context["architecture"] < 0.4 and
    trust_by_context["implementation"] > 0.8 and
    trust_by_context["test"] > 0.8):
    # High-level control + operational delegation
    archetype = "Strategist"
```

### Strengths
- **Leverage**: Your judgment where it matters most
- **Scale**: Delegate volume, control direction
- **Efficiency**: Right level of attention for each task
- **Leadership**: Natural fit for tech leads, architects

### Weaknesses
- **Requires clarity**: Must know what's strategic vs tactical
- **Trust calibration**: Wrong delegation can be costly
- **Communication overhead**: Must clearly convey intent to AI
- **Blindness risk**: Tactical errors can compound unnoticed

### When Strategist Works Well
| Context | Fit | Why |
|---------|-----|-----|
| Tech lead/architect role | ✅ Excellent | Your job is direction, not details |
| Complex systems | ✅ Good | Strategic errors are expensive |
| Mentorship | ✅ Good | Model for junior devs |
| Solo prototyping | ⚠️ Mixed | Might be overkill |
| Pure implementation | ❌ Poor | No strategic decisions to make |

### Recommendations by Work Context

**If you work in Production/DevOps:**
> Your pattern fits infrastructure decisions. Control what gets deployed (strategy), delegate how it's implemented (tactics). Ensure your strategic reviews include rollback plans.

**If you work in Security:**
> Good fit: Control threat model and security architecture, delegate implementation of mitigations. But verify tactical implementation—AI may misunderstand security requirements.

**If you work in Management/Architecture:**
> This is your natural home. Ensure your "strategic" category includes: API design, data models, service boundaries. Delegate: CRUD, tests, formatting.

**If you work in Feature Development:**
> Consider whether you have enough strategic decisions to warrant this pattern. If you're mostly implementing, Delegator or Council might be more efficient.

### Alternative Styles to Try
1. **Autocrat**: Temporarily review everything—are you missing tactical issues?
2. **Council**: Add domain-specific rules instead of just strategic/tactical split
3. **Delegator**: Delegate strategy for a week—see if AI can handle it

### The Hard Question
> "Am I accurately distinguishing strategic from tactical, or am I just delegating what I find boring?"

---

## Context-Specific Recommendations Matrix

### By Work Domain

| Domain | Recommended Archetype | Avoid | Why |
|--------|----------------------|-------|-----|
| **Production/Infrastructure** | Council, Constitutionalist | Delegator | Errors are expensive |
| **Security** | Autocrat, Council | Delegator | Trust must be verified |
| **Architecture/Design** | Strategist, Deliberator | Delegator | Strategic errors compound |
| **Feature Development** | Council, Strategist | Autocrat (unless junior) | Balance speed and quality |
| **Testing** | Delegator, Constitutionalist | Autocrat | Volume matters, risk is low |
| **Documentation** | Delegator | Deliberator | Speed matters, errors cheap |
| **Prototyping** | Delegator | Autocrat, Deliberator | Speed is everything |
| **Code Review (of others)** | Deliberator | Delegator | Your job is to review |
| **Incident Response** | Delegator (for fixes), Autocrat (for RCA) | Deliberator | Speed first, then analyze |
| **Compliance/Audit** | Constitutionalist, Autocrat | Delegator | Rules must be followed |

### By Career Stage

| Stage | Recommended | Why |
|-------|-------------|-----|
| **Junior (0-2 years)** | Deliberator, Autocrat | You need to learn what AI is doing |
| **Mid (2-5 years)** | Council, Strategist | Balance efficiency with judgment |
| **Senior (5+ years)** | Strategist, Council | Focus on leverage, not volume |
| **Lead/Architect** | Strategist | Your job is direction, not details |
| **Manager** | Strategist, Delegator | You shouldn't be in the code that much |

### By Team Size

| Size | Recommended | Why |
|------|-------------|-----|
| **Solo** | Delegator, Strategist | Only you to slow you down |
| **Small (2-5)** | Council, Strategist | Some coordination needed |
| **Medium (5-20)** | Constitutionalist, Council | Need shared rules |
| **Large (20+)** | Constitutionalist | Consistency at scale |

---

## Evaluation Framework

When showing users their archetype, provide:

### 1. The Classification
```
Your Governance Style: STRATEGIST (78% confidence)

You control high-level decisions and delegate implementation.
You reviewed 94% of architectural decisions personally.
You auto-approved 87% of implementation code.
```

### 2. Strengths/Weaknesses for Their Context
```
Your context: Production/Security

Strengths for your context:
✅ Strategic control appropriate for security architecture
✅ Delegation of implementation maintains velocity

Weaknesses for your context:
⚠️ Implementation errors in security code can be severe
⚠️ You may miss tactical security issues (e.g., injection flaws)

Recommendations:
→ Keep strategic control for threat modeling
→ Add light review for security-critical implementation
→ Consider "Council" pattern for security-tagged files
```

### 3. Alternative Styles to Experiment
```
Based on your work in Production/Security, consider:

1. COUNCIL pattern for security code
   → Create explicit trust rules: auto-approve tests, review auth code
   → Try for 1 week, measure impact on velocity

2. AUTOCRAT mode for security PRs
   → Temporarily review all security-tagged changes
   → Use for critical releases, then relax
```

### 4. The Hard Question
```
Reflect:
"Am I delegating implementation because I trust the AI's security awareness,
or because reviewing security details is tedious?"
```

---

## How to Measure Context

To provide context-specific recommendations, we need to know what the user is working on.

### Automatic Detection (from instrumentation)
```python
# Infer context from file patterns
def detect_context(file_path: str, command: str) -> TaskContext:
    if "test" in file_path or "spec" in file_path:
        return TaskContext.TEST
    if "deploy" in command or "prod" in file_path:
        return TaskContext.DEPLOY
    if ".tf" in file_path or "infrastructure" in file_path:
        return TaskContext.INFRASTRUCTURE
    if "security" in file_path or "auth" in file_path:
        return TaskContext.SECURITY
    # etc.
```

### User-Provided Context
```yaml
# ~/.suzerain/profile.yaml
work_context:
  primary_domain: production    # production, security, feature, research
  team_size: medium             # solo, small, medium, large
  career_stage: senior          # junior, mid, senior, lead, manager
  risk_tolerance: low           # low, medium, high
  compliance_required: true     # true, false
```

### Contextual Feature Engineering
```python
# Weight features by context
if user.work_context == "security":
    # For security context, Delegator pattern is higher risk
    risk_score = compute_delegator_risk(features) * 1.5
elif user.work_context == "prototyping":
    # For prototyping, Delegator is fine
    risk_score = compute_delegator_risk(features) * 0.3
```

---

## Summary

| Archetype | Best For | Avoid If | Key Metric |
|-----------|----------|----------|------------|
| Autocrat | Security, compliance, learning | High-velocity teams | acceptance_rate > 85%, decision_time > 2s |
| Council | Mixed-risk, team leads | Exploration phase | High trust_by_context variance |
| Deliberator | Research, critical code | Deadlines | High edit_rate, high decision_time |
| Delegator | Prototyping, tests, docs | Production, security | acceptance_rate > 90%, decision_time < 500ms |
| Constitutionalist | Regulated, team standards | Rapidly changing domains | High session_consistency |
| Strategist | Leads, architects, complex systems | Pure implementation | Bimodal trust by strategic/tactical |

---

*"Know thyself" — Delphi*
*"Know thy context" — Suzerain*
