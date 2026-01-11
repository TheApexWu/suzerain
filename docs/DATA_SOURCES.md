# Data Sources for AI Governance Behavior

> The cold truth: There is no public dataset of how users govern AI coding tools.
> We have to be creative.

---

## What Anthropic Has (and Doesn't Have)

### Publicly Available
| Resource | What It Contains | Useful For |
|----------|------------------|------------|
| [Anthropic Research Papers](https://www.anthropic.com/research) | Aggregate stats, methodology | Understanding their framing |
| [Model Card](https://docs.anthropic.com/en/docs/about-claude/models) | Capability benchmarks | Not behavior data |
| [Claude Character](https://docs.anthropic.com/en/docs/about-claude/claude-character) | Personality design principles | How Claude behaves, not users |
| [API Usage Docs](https://docs.anthropic.com/en/api/) | Rate limits, token counts | Billing data, not behavior |
| [Prompt Library](https://docs.anthropic.com/en/prompt-library) | Example prompts | Task types, not user patterns |

### Not Publicly Available (Privacy Protected)
- Individual conversation logs
- User acceptance/rejection patterns
- Session-level telemetry
- Demographic data
- Any PII-linked behavior data

### What Claude Code Logs Locally
Claude Code stores conversation history in `~/.claude/` but:
- It's YOUR data only
- No aggregation across users
- No public dataset exists

**Bottom line:** Anthropic does not expose user behavior data. Privacy-first.

---

## Real Data Sources (Ranked by Feasibility)

### Tier 1: Available Now

#### 1. Self-Instrumentation (N=1, but real)
```python
# Hook into your own Claude Code usage
# Log every interaction for 2-4 weeks
# See: scripts/self_instrument.py
```
**Pros:** Real data, full control, no privacy issues
**Cons:** N=1, your behavior might not generalize

#### 2. GitHub Copilot Research Papers
Microsoft has published aggregate statistics:
- [Copilot Productivity Study (2022)](https://github.blog/2022-09-07-research-quantifying-github-copilots-impact-on-developer-productivity-and-happiness/)
  - 88% of code kept in final submissions
  - 46% of code written by Copilot (acceptance proxy)
  - Task completion 55% faster

- [Copilot Impact Study (2024)](https://github.blog/news-insights/research/research-quantifying-github-copilots-impact-in-the-enterprise/)
  - Acceptance rates by task type
  - Aggregate patterns across enterprise users

**Extract:** Distributions, means, variances (not individual data)

#### 3. Academic Papers on AI-Assisted Coding
Search: Google Scholar, arXiv, ACM DL
```
"AI code completion" user study
"GitHub Copilot" acceptance rate
"LLM coding assistant" user behavior
```

Known studies:
- METR study: AI users 19% slower (counterintuitive finding)
- Various CHI/CSCW papers on AI-assisted programming

#### 4. Developer Surveys (Public)
- [Stack Overflow Developer Survey](https://survey.stackoverflow.co/) - AI tool usage questions
- [JetBrains Developer Ecosystem](https://www.jetbrains.com/lp/devecosystem/) - AI adoption stats
- [GitHub Octoverse](https://octoverse.github.com/) - Copilot adoption trends

---

### Tier 2: Requires Effort

#### 5. Run Your Own Survey
Create a survey targeting developers:
```
1. How often do you accept AI suggestions? (slider 0-100%)
2. Do you review suggestions before accepting? (always/sometimes/never)
3. Do you trust AI more for tests vs production code?
4. How often do you edit AI output after accepting?
5. What makes you reject a suggestion?
```

**Distribution channels:**
- Reddit: r/programming, r/ExperiencedDevs, r/ClaudeAI
- Hacker News: Show HN with survey link
- Twitter/X: Developer communities
- Discord: Cursor, Claude, Copilot servers

**Target:** N=100-500 self-reported behavior profiles

#### 6. Opt-In Telemetry (MVP Feature)
Build telemetry into Suzerain itself:
```python
# With explicit consent
if user.opted_in_to_telemetry:
    send_anonymized({
        "acceptance_rate": 0.73,
        "mean_decision_time": 1200,
        "context_sensitivity": 0.45,
        # NO prompts, NO code, NO PII
    })
```

**Bootstrap:** First 50 users build the dataset

#### 7. Scrape Public Discussions (Qualitative)
```python
# Reddit, HN, Twitter discussions about AI coding tools
# Extract: qualitative behavior patterns, complaints, preferences

sources = [
    "reddit.com/r/ClaudeAI",
    "reddit.com/r/Copilot",
    "reddit.com/r/cursor",
    "news.ycombinator.com (search: copilot, claude code)",
]

# NLP analysis: sentiment, behavior mentions, trust signals
```

**Output:** Qualitative themes, not quantitative features

---

### Tier 3: Simulation & Synthesis

#### 8. Synthetic User Generation
If you have hypotheses about behavior distributions, simulate:

```python
import numpy as np

def generate_synthetic_users(n=1000):
    """
    Generate synthetic user behavior based on assumed distributions.
    Validate assumptions with real data later.
    """
    users = []

    # Hypothesis: acceptance_rate is bimodal
    # (some users trust AI, some don't)
    acceptance_mode = np.random.choice([0.3, 0.8], n, p=[0.4, 0.6])
    acceptance_rate = np.clip(
        np.random.normal(acceptance_mode, 0.15), 0, 1
    )

    # Hypothesis: decision_time is log-normal
    # (most fast, some very deliberate)
    decision_time = np.random.lognormal(mean=7, sigma=1, size=n)

    # Hypothesis: context_sensitivity varies
    # (some treat all tasks equally, some differentiate)
    context_sensitivity = np.random.beta(2, 5, size=n)

    # Hypothesis: edit_rate correlates with acceptance
    # (low accepters edit more when they do accept)
    edit_rate = 0.8 - 0.6 * acceptance_rate + np.random.normal(0, 0.1, n)
    edit_rate = np.clip(edit_rate, 0, 1)

    return pd.DataFrame({
        "acceptance_rate": acceptance_rate,
        "decision_time_ms": decision_time,
        "context_sensitivity": context_sensitivity,
        "edit_after_accept_rate": edit_rate,
    })

# Generate and cluster
synthetic = generate_synthetic_users(1000)
# Run clustering pipeline
# See what archetypes emerge from YOUR assumptions
# Then validate with real data
```

**Purpose:** Test pipeline, develop intuition, NOT ground truth

#### 9. Agent-Based Simulation
Model different "governance personalities" as agents:

```python
class RomanEmperorAgent:
    """Simulates a user who approves everything manually"""
    acceptance_rate = 0.95
    decision_time_mean = 2000  # ms (deliberate)
    auto_execute = False

class MongolHordeAgent:
    """Simulates a user who trusts AI completely"""
    acceptance_rate = 0.98
    decision_time_mean = 200   # ms (instant)
    auto_execute = True

# Simulate N sessions per agent type
# Generate synthetic event logs
# Validate that clustering recovers the known types
```

**Purpose:** Sanity check that pipeline works before real data

---

## Data Extraction from Known Sources

### From Copilot Research
```python
# Extracted from Microsoft's published research
copilot_aggregate_stats = {
    "acceptance_rate_mean": 0.46,      # 46% of suggestions accepted
    "acceptance_rate_enterprise": 0.30, # Lower in enterprise
    "code_kept_rate": 0.88,            # 88% of accepted code kept
    "productivity_gain": 0.55,          # 55% faster task completion
    "distrust_rate": 0.46,             # 46% actively distrust
    "high_trust_rate": 0.03,           # Only 3% highly trust

    # Rejection reasons (from surveys)
    "reject_context_issues": 0.44,
    "reject_team_standards": 0.40,
    "reject_almost_right": 0.45,
}
```

### From Stack Overflow Survey
```python
# 2024 Developer Survey AI section
so_survey_stats = {
    "using_ai_tools": 0.76,            # 76% use AI dev tools
    "trust_ai_accuracy": 0.43,         # 43% trust accuracy
    "ai_for_learning": 0.62,           # 62% use for learning
    "ai_for_productivity": 0.81,       # 81% say it helps productivity
}
```

---

## Recommended Strategy

### Phase 1: Bootstrap (Week 1-2)
1. **Self-instrument** - Log your own Claude Code usage
2. **Extract aggregate stats** - From Copilot/SO research
3. **Generate synthetic data** - Based on hypothesized distributions

### Phase 2: Validate (Week 3-4)
1. **Run survey** - Get 50-100 self-reported profiles
2. **Compare to synthetic** - Are your hypotheses correct?
3. **Refine feature engineering** - What actually varies?

### Phase 3: Scale (Month 2+)
1. **Ship with opt-in telemetry** - Build dataset from real users
2. **Iterate on archetypes** - Update as data accumulates
3. **Publish findings** - Contribute to the research gap

---

## The Hard Truth

**There is no shortcut.**

Nobody has published a dataset of "how users govern AI coding tools." You're building the first one. This is the research contribution.

Options:
1. **Wait for Anthropic/Microsoft to publish** - May never happen
2. **Build it yourself** - Harder but original
3. **Fake it with assumptions** - Dishonest, will collapse

The honest path: Small real data > Large synthetic data.

---

## Resources

- [Anthropic Research](https://www.anthropic.com/research)
- [GitHub Copilot Research](https://github.blog/category/research/)
- [Stack Overflow Survey](https://survey.stackoverflow.co/)
- [ACM DL: AI-Assisted Programming](https://dl.acm.org/action/doSearch?AllField=AI+assisted+programming)
- [arXiv: LLM Coding](https://arxiv.org/search/?query=LLM+code+completion&searchtype=all)

---

*"In God we trust. All others must bring data."* — W. Edwards Deming
