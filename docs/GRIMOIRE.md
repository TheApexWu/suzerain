# Grimoire Reference

> *"The truth about the world is that anything is possible."*

Complete reference for Suzerain's command system.

---

## How It Works

1. You speak a phrase from the grimoire
2. Fuzzy matching identifies the command (allows natural speech variation)
3. The phrase expands into a full prompt for Claude Code
4. Claude interprets and executes with full agentic capability

The grimoire is not a voice macro in the traditional sense—it's a semantic cipher that maps literary phrases to complex AI-driven workflows.

---

## Commands

### Escape Hatch

| Phrase | What It Does |
|--------|--------------|
| **hold** | Emergency stop. Cancels current operation immediately. |

Always works. Highest priority. Shortest phrase for fastest recognition.

---

### Deployment & Production

| Phrase | What It Does | Requires Confirmation |
|--------|--------------|----------------------|
| **the evening redness in the west** | Deploy to production. Runs tests first, aborts if any fail. Verifies deployment health. | Yes |
| **the phantom band played on the ridge** | Deploy to staging/preview. Runs tests. Returns preview URL. | No |

**Example with modifier:**
```
"the evening redness in the west and the judge watched"
→ DRY RUN: Shows deployment steps without executing
```

---

### Continuation & Flow

| Phrase | What It Does | Requires Confirmation |
|--------|--------------|----------------------|
| **they rode on** | Continue exactly where you left off. Uses Claude's `--continue` flag. | No |
| **and in the morning they rode on** | Review last session: what's done, what's pending, any blockers. | No |

**Tip:** Use "they rode on" after any interrupted task. Claude picks up context automatically.

---

### Testing & Quality

| Phrase | What It Does | Requires Confirmation |
|--------|--------------|----------------------|
| **the judge smiled** | Run test suite. Auto-detects framework (pytest, jest, go test, etc). Reports pass/fail summary. | No |
| **whatever in creation exists without my knowledge** | Security audit. Scans for vulnerabilities, performance issues, code smells, missing error handling. | No |

**Example:**
```
"the judge smiled under the stars"
→ Runs tests with verbose output, showing every assertion
```

---

### Git & Version Control

| Phrase | What It Does | Requires Confirmation |
|--------|--------------|----------------------|
| **draw the sucker** | Git pull. Shows what changed. Pauses on conflicts. | No |
| **the blood dried** | Commit all changes with a descriptive message (Claude writes the message). | Yes |
| **he wore the bloody scalp** | Push current branch to remote. | Yes |

**Chained example:**
```
"the judge smiled... the blood dried"
→ Run tests, then commit if they pass
```

---

### Project Initialization

| Phrase | What It Does | Requires Confirmation |
|--------|--------------|----------------------|
| **night of your birth** | Initialize new project. Creates structure, dependencies, gitignore, initial commit. | No |

Claude will ask what kind of project if not obvious from context.

---

### Cleanup & Maintenance

| Phrase | What It Does | Requires Confirmation |
|--------|--------------|----------------------|
| **the fires on the plain** | Clean build artifacts and caches. Reports space freed. | Yes |
| **and they are gone now all of them** | Kill all dev processes (Node servers, Python, Docker containers). | Yes |

---

### Background & Daemons

| Phrase | What It Does | Requires Confirmation |
|--------|--------------|----------------------|
| **he never sleeps** | Start file watcher. Runs lint/typecheck/tests on save. Only notifies on failure. | No |
| **the judge watched** | Show all background processes: dev servers, watchers, containers. | No |

---

### Research & Exploration

| Phrase | What It Does | Requires Confirmation |
|--------|--------------|----------------------|
| **tell me about the country ahead** | Quick research. Concise briefing with citations. | No |
| **scour the terrain** | Deep research. Multiple sources, cross-references, confidence levels, open questions. | No |
| **the kid looked at the expanse before him** | Survey current project: structure, dependencies, recent commits, TODOs, issues. | No |

---

### Debugging & Understanding

| Phrase | What It Does | Requires Confirmation |
|--------|--------------|----------------------|
| **your heart's desire is to be told some mystery** | Explain last error in depth: root cause, fix, prevention. | No |
| **the mystery of the world** | Explain codebase architecture: entry points, data flow, key abstractions. | No |

---

### Focus & Environment

| Phrase | What It Does | Requires Confirmation |
|--------|--------------|----------------------|
| **the priest did not answer** | Deep work mode. Suppresses notifications for 90 minutes. | No |
| **a man's at odds to know his mind** | Get unstuck. Claude suggests 3 concrete next actions based on project state. | No |

---

## Modifiers

Append to any command to change behavior.

| Modifier Phrase | Effect | Description |
|-----------------|--------|-------------|
| **...under the stars** | Verbose | Detailed output at every step. Explains reasoning. |
| **...in silence** | Quiet | Minimal output. Only final result or errors. |
| **...and the judge watched** | Dry Run | Preview what would happen. No execution. |
| **...by first light** | Schedule | Runs at 6 AM tomorrow instead of now. |
| **...the blood meridian** | Commit After | Commits changes if command succeeds. |

### Modifier Examples

```
"the evening redness in the west and the judge watched"
→ Show deployment plan without deploying

"the judge smiled under the stars"
→ Run tests with full verbose output

"scour the terrain in silence"
→ Deep research, but only show final synthesis

"the fires on the plain the blood meridian"
→ Clean caches, then commit the cleanup
```

---

## Adding Custom Commands

### Basic Structure

Edit `grimoire/commands.yaml`:

```yaml
commands:
  - phrase: "your trigger phrase"
    expansion: |
      The full prompt sent to Claude Code.

      Be specific:
      1. What should happen first
      2. How to handle edge cases
      3. What output you expect

      Claude will interpret this and execute with full capability.
    confirmation: false
    tags: [category, subcategory]
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `phrase` | Yes | The spoken trigger. Keep memorable and distinct. |
| `expansion` | Yes | Full prompt for Claude. Multi-line YAML with `\|`. |
| `confirmation` | No | If `true`, requires "y" before execution. Default: `false`. |
| `tags` | No | Categories for organization. |
| `use_continue` | No | If `true`, uses Claude's `--continue` flag. |
| `is_escape_hatch` | No | If `true`, gets highest matching priority. |

### Example: Custom Deploy

```yaml
- phrase: "release the hounds"
  expansion: |
    Deploy this project to production using our custom process:
    1. Run lint and typecheck
    2. Run full test suite
    3. Build production bundle
    4. Deploy via Vercel CLI
    5. Run smoke tests against production URL
    6. If smoke tests fail, roll back immediately
    7. Notify #deployments Slack channel with result
  confirmation: true
  tags: [deploy, production, custom]
```

### Example: Personal Research

```yaml
- phrase: "what did I miss"
  expansion: |
    Check my information sources for updates since I last looked:
    1. GitHub notifications for my repos
    2. Hacker News top stories
    3. Any new issues/PRs on projects I contribute to

    Summarize what's important. Skip noise.
  confirmation: false
  tags: [research, personal]
```

---

## Adding Custom Modifiers

```yaml
modifiers:
  - phrase: "with extreme prejudice"
    effect: force
    expansion_append: |
      Skip all safety checks. Force the operation even if warnings occur.
      This is a deliberate override—I accept the consequences.

  - phrase: "and tell the world"
    effect: announce
    expansion_append: |
      After completing, post a summary to Slack #general.
      Keep it brief and professional.
```

---

## Matching Behavior

### How Fuzzy Matching Works

Suzerain uses RapidFuzz with configurable strictness:

```yaml
parser:
  threshold: 80     # 0-100, higher = stricter
  scorer: ratio     # 'ratio', 'partial_ratio', 'token_set_ratio'
```

| Scorer | Behavior | Use When |
|--------|----------|----------|
| `ratio` | Strict character-by-character | You want exact phrases only |
| `partial_ratio` | Best substring match | Some flexibility OK |
| `token_set_ratio` | Word order doesn't matter | Maximum flexibility (risky) |

**Default: `ratio` at 80%** — Requires most of the phrase, tolerates minor variation.

### Filler Words

Common speech fillers are stripped before matching:

```yaml
strip_filler_words:
  - um
  - uh
  - like
  - so
  - well
  - basically
  - actually
  - you know
```

So "um, the evening redness in the west" matches correctly.

### Disambiguation

When multiple commands match closely (within 10 points), Suzerain prompts:

```
Multiple matches found. Did you mean:

  1. "the evening redness in the west"
     [deploy, production, critical] (score: 85)

  2. "the evening came upon them"
     [transition, end] (score: 78)

  0. Cancel

Select [1-2]:
```

---

## Tips for Memorable Phrases

### Use Vivid Imagery

```
Good:  "the fires on the plain"      → You can see it
Bad:   "clean project caches"        → Functional but forgettable
```

### Match Action to Meaning

```
"the blood dried"  → Commit (the deed is done, preserved)
"draw the sucker"  → Pull (drawing toward you)
"they rode on"     → Continue (movement forward)
```

### Keep Distinct

Phrases should be phonetically different:
```
Distinct:   "the judge smiled" vs "the evening redness"
Confusable: "the judge smiled" vs "the judge smiled softly"
```

### Short for Urgent

Escape commands should be short:
```
"hold"              → 1 syllable, instant
"stop everything"   → 4 syllables, too slow
```

### Literary Sources

Good sources for memorable phrases:
- Cormac McCarthy (Blood Meridian, The Road, No Country)
- Shakespeare (short declarative lines)
- Poetry (Yeats, Eliot, Frost)
- Mythology (Norse, Greek, Celtic)

The key is **distinct imagery** that maps to **action semantics**.

---

## Validation

Check your grimoire syntax:

```bash
python src/main.py --validate
```

Output:
```
Validating grimoire...

✓ Grimoire valid
  21 commands
  5 modifiers
```

Or with errors:
```
Validating grimoire...

❌ Found 2 issue(s):

  - Command 3: missing 'expansion'
  - Duplicate phrase: 'they rode on'
```

---

## Testing Changes

### Safe Exploration

```bash
# See all commands
python src/main.py --list

# Test matching without execution
python src/main.py --test --sandbox
> the evening redness in the west

[DRY RUN - Showing expansion only]

Deploy this project to production. Follow this sequence strictly:
1. Run the full test suite
2. If ANY test fails, abort immediately...
```

### Parser Direct Test

```bash
python -c "from src.parser import match; print(match('evening redness'))"
```

---

*"Whatever exists without my knowledge exists without my consent."*

Now add your own incantations.
