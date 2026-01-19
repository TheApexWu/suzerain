# Methodology

> *"The first principle is that you must not fool yourself — and you are the easiest person to fool."* — Feynman

## Epistemic Status: Hypothesis-Generating

**This tool is NOT a validated psychometric instrument.**

| What It Is | What It Isn't |
|------------|---------------|
| Exploratory analysis | Rigorous personality assessment |
| Behavioral patterns from logs | Stable psychological traits |
| Heuristic thresholds | Empirically validated cutoffs |
| Hypothesis-generating | Hypothesis-testing |
| N=1 real user + simulations | Diverse validated sample |

**The archetypes describe recent behavior, not who you are.** Patterns shift. The same person may be a Delegator on Monday and Adaptive on Friday. Context matters more than category.

**Thresholds are tuned against simulated data.** They discriminate on synthetic personas but haven't been validated on diverse real users.

**We need your data to improve.** Run `suzerain share --preview` to see what would be shared.

## How the Analysis Works

No NLP or LLM. Suzerain reads your Claude Code logs and counts things.

**What it parses:** `~/.claude/projects/{project}/{session}.jsonl`

Each log file contains tool_use (Claude's request) and tool_result (your response) events. The parser pairs these and extracts:

1. **Tool name** - Bash, Read, Edit, etc.
2. **Accepted or rejected** - Did tool_result contain an error?
3. **Decision time** - Gap between timestamps
4. **Command content** - For Bash commands only

## Three-Axis Framework

Classification uses three independent axes:

| Axis | Signal | Range |
|------|--------|-------|
| **Trust Level** | Bash acceptance rate | 0-100% |
| **Sophistication** | Agent usage, tool diversity, session depth | 0-1 |
| **Variance** | Cross-project/session consistency | 0-1 |

**Trust** is THE discriminator. All other tools are rubber-stamped (~100%). Governance happens at the Bash prompt.

**Sophistication** captures power user patterns: spawning agents, using diverse tools, running deep sessions.

**Variance** detects context-dependent governance: users who trust 100% on maintenance but 1% on critical builds.

## Six Archetypes (Priority-Ordered)

| Archetype | Rule | Parallel |
|-----------|------|----------|
| **Adaptive** | Variance ≥ 0.3 | Akbar the Great |
| **Delegator** | Trust > 80%, Soph < 0.4 | Cyrus the Great |
| **Council** | Trust > 70%, Soph ≥ 0.4 | Ottoman Sultan |
| **Guardian** | Trust < 50%, Soph < 0.4 | Ming Dynasty |
| **Strategist** | Trust < 70%, Soph ≥ 0.4 | Napoleon |
| **Constitutionalist** | Fallback | Hammurabi |

Priority order means variance is checked first. A high-variance user is Adaptive regardless of trust/sophistication.

## Validation

### Phase 1: Single-User Analysis (n=1)

Parsed 75 sessions from one user (the author):
- 7,083 tool calls over 28 days
- Bash acceptance: 57%
- Variance: 1.00 (context-dependent)

Key finding: 100% acceptance on home directory, 1% on suzerain project, 3% on stardust. Same user, radically different governance.

### Phase 2: Simulated Personas (n=14)

14 personas covering the behavioral space:

| Category | Personas |
|----------|----------|
| High trust | junior_dev, hobbyist, copilot_refugee |
| Low trust | security_engineer, compliance_reviewer, paranoid_senior |
| High sophistication | senior_swe, staff_engineer, devops_sre, data_scientist |
| High variance | context_switcher, project_guardian, sprint_mode |

**310 sessions, 24,700 tool calls.**

### Results

The 3-axis framework discriminates:

| Axis | High Group | Low/Avg Group |
|------|------------|---------------|
| Trust | 93% | 30% |
| Sophistication | 0.95 | 0.69 |
| Variance | 1.00 | 0.45 |

Archetype distribution across 14 personas:
- Adaptive: 6 (43%)
- Delegator: 3 (21%)
- Strategist: 3 (21%)
- Council: 2 (14%)

What this proves: classification logic separates synthetic personas as designed.

What this doesn't prove: real users behave this way.

## Axis Independence

The three axes (Trust, Sophistication, Variance) are designed to measure conceptually distinct things:

| Axis | Measures | Independent of... |
|------|----------|-------------------|
| Trust | How freely you approve commands | What tools you use |
| Sophistication | How you use the tool | What you approve |
| Variance | Consistency across contexts | Overall trust level |

**Empirical check (n=14 simulated personas):**

| Pair | Pearson r | Status |
|------|-----------|--------|
| Trust vs Sophistication | -0.39 | Moderate correlation |
| Trust vs Variance | -0.30 | Weak (acceptable) |
| Sophistication vs Variance | +0.40 | Moderate correlation |

**Why the correlations exist:** The simulated personas were designed as stereotypes. "Cautious" personas (security_engineer, paranoid_senior) were given agent usage. "High-variance" personas (context_switcher, sprint_mode) were all given `uses_agents=True`. These design choices, not the framework itself, created the correlations.

**What this means:**
- Correlations are simulation artifacts, not inherent framework flaws
- |r| ~ 0.4 is moderate, not strong—axes still capture different information
- Real-world data needed to validate true independence
- Run `scripts/verify_axis_independence.py` to reproduce

## Limitations

- **N=1 real data** - Everything else is simulated
- **Simulations are stereotypes** - Personas are guesses about archetypes, with baked-in correlations
- **Thresholds are tuned, not discovered** - No ablation study
- **Axis correlations untested on real users** - Moderate correlations in simulated data may not reflect reality
- **Claude Code only** - Won't work with Cursor, Copilot, etc.
- **No intent measurement** - We see what you did, not why
- **Stability unknown** - Patterns might differ by day/project

## Scripts

| Script | Purpose |
|--------|---------|
| `src/suzerain/parser.py` | Parse Claude Code logs |
| `src/suzerain/analytics.py` | Command breakdown, temporal trends, variance |
| `src/suzerain/classifier.py` | 3-axis classification |
| `scripts/simulate_users.py` | Generate synthetic personas |
| `scripts/test_classification.py` | Validate classification |

*"In God we trust. All others must bring data."* — Deming
