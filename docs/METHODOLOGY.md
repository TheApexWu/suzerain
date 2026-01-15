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

## How the Analysis Works

There's no NLP or LLM involved. Suzerain reads your Claude Code logs and counts things.

**What it parses:** `~/.claude/projects/{project}/{session}.jsonl`

Each log file contains tool_use (Claude's request) and tool_result (your response) events. The parser pairs these up and extracts:

1. **Tool name** - Bash, Read, Edit, etc.
2. **Accepted or rejected** - Did tool_result contain an error?
3. **Decision time** - Gap between tool_use timestamp and tool_result timestamp

That's it. No prompt analysis. No code inspection. Just event pairs and timestamps.

**Script:** [`src/suzerain/parser.py`](../src/suzerain/parser.py)

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

**Script:** [`src/suzerain/parser.py`](../src/suzerain/parser.py)

### Phase 2: Feature Exploration

Searched for subtle features that might discriminate:

| Feature | Variance | Useful? |
|---------|----------|---------|
| Agent/Task usage | 0-41% ratio | **Yes** - power user signal |
| Tool diversity | 1-12 unique/session | **Yes** |
| Session depth | 1-1345 calls | **Yes** |
| Parallel tools | 99.9% single | **No** - too rare |
| Tool sequences | Bash-dominated | **No** |

**Script:** [`src/suzerain/classifier.py`](../src/suzerain/classifier.py) - see `compute_subtle_features()`

### Phase 3: Simulated Validation

**Honesty check: this part is vibes.**

I had n=1 real data (myself). To test if the classification logic worked at all, I made up 11 fake users based on people I've worked with or imagined. No surveys, no interviews, no research. Just "what would a security engineer probably do?" type reasoning.

The personas are stereotypes. They might be wrong. But they gave me something to test against.

#### The 11 Personas

**Casual Users (high trust, low sophistication)**

| Persona | Bash Accept | Agents | Session Depth | Rationale |
|---------|-------------|--------|---------------|-----------|
| Junior Dev | 95% | No | ~15 calls | New to AI tools, trusts everything, short sessions |
| Hobbyist | 98% | No | ~8 calls | Side projects, quick questions, doesn't overthink |
| Copilot Refugee | 85% | No | ~25 calls | Learning Claude Code, slightly more careful |

**Power Users (sophisticated, mixed trust)**

| Persona | Bash Accept | Agents | Session Depth | Rationale |
|---------|-------------|--------|---------------|-----------|
| Senior SWE | 70% | Yes (15%) | ~150 calls | Experienced, uses agents, moderate caution |
| Staff Engineer | 65% | Yes (25%) | ~250 calls | Orchestrates complex tasks, heavy agent usage |
| DevOps/SRE | 80% | Yes (10%) | ~80 calls | Operational mindset, fast but not reckless |
| Data Scientist | 75% | Yes (8%) | ~60 calls | Exploration-heavy, notebooks, moderate care |

**Cautious Users (low trust, varying sophistication)**

| Persona | Bash Accept | Agents | Session Depth | Rationale |
|---------|-------------|--------|---------------|-----------|
| Security Engineer | 30% | No | ~40 calls | Reviews everything, slow, paranoid about shell |
| Compliance Reviewer | 40% | No | ~30 calls | Reads a lot, rarely writes, very selective |
| Paranoid Senior | 25% | Yes (5%) | ~100 calls | Experienced but distrustful, rejects most Bash |
| Prod On-Call | 50% | Yes (12%) | ~70 calls | Context-dependent, cautious in prod, fast in dev |

#### How the Simulation Works

For each persona, I defined:
- `bash_acceptance`: probability of accepting Bash commands (THE key variable)
- `high_risk_acceptance`: probability for Write/Edit
- `low_risk_acceptance`: probability for Read/Glob/etc (usually 100%)
- `uses_agents`: whether they use Task tool
- `mean_session_depth`: typical number of tool calls per session
- `tool_diversity`: how many different tools they use

Then generated synthetic sessions: random tool sequences weighted by persona, with acceptance/rejection determined by the probabilities above.

**240 sessions, 18,810 tool calls total.**

#### Results

Features discriminate as expected. The made-up personas cluster where I thought they would.

| User Type | Sophistication | Caution | Agent Rate |
|-----------|---------------|---------|------------|
| Casual | 0.03 | 0.07 | 0% |
| Power | 0.89 | 0.47 | 22% |
| Cautious | 0.69 | 1.00 | 7% |

**What this proves:** The classification logic works on fake data that was designed to fit the classification logic. Circular, I know.

**What this doesn't prove:** That real users actually behave this way, or that the archetypes mean anything outside my head.

**Script:** [`scripts/simulate_users.py`](../scripts/simulate_users.py)

---

## Limitations (short version)

- **N=1 real data** - Everything else is simulated
- **Simulations are vibes** - Personas are stereotypes I made up
- **Thresholds are guesses** - No ablation study, no sensitivity analysis
- **Claude Code only** - Won't work with Cursor, Copilot, etc.
- **No intent measurement** - I see what you did, not why you did it
- **Stability unknown** - Might be different on different days/projects

---

## Data Sharing (Opt-In)

Run `suzerain share --preview` to see exactly what would be shared. It's aggregate metrics only: acceptance rates, decision times, tool diversity. No prompts, no code, no file paths.

**Script:** [`src/suzerain/cli.py`](../src/suzerain/cli.py) - see `preview_share()`

---

## Scripts Reference

| Script | What it does |
|--------|--------------|
| [`src/suzerain/parser.py`](../src/suzerain/parser.py) | Parses Claude Code logs |
| [`src/suzerain/classifier.py`](../src/suzerain/classifier.py) | Computes features and classifies |
| [`src/suzerain/insights.py`](../src/suzerain/insights.py) | Maps archetypes to bottlenecks |
| [`scripts/simulate_users.py`](../scripts/simulate_users.py) | Generates fake user data |
| [`scripts/test_classification.py`](../scripts/test_classification.py) | Validates classification |

---

*"In God we trust. All others must bring data."* — Deming
