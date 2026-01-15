"""
Archetype definitions and insights.

Each archetype has:
- A governance style (how you interact with the AI)
- A bottleneck (what slows you down)
- Recommendations (what to try)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from .models import Classification


@dataclass
class ArchetypeInsight:
    """Insight package for an archetype."""
    name: str
    language_game: str
    game_description: str
    bottleneck: str
    bottleneck_description: str
    mechanism: str
    recommendations: List[str]
    risk: str
    historical_parallel: str


# ============================================================================
# Archetype Definitions
# ============================================================================

ARCHETYPES: Dict[str, ArchetypeInsight] = {

    "Delegator": ArchetypeInsight(
        name="Delegator",

        language_game="The Acceptance Game",
        game_description=(
            "You treat AI output as draft code to be merged, not proposals to be reviewed. "
            "Your rule is throughput—tokens in, code out, velocity above all."
        ),

        bottleneck="Error discovery happens downstream",
        bottleneck_description=(
            "You accept most suggestions quickly, which maximizes throughput but means errors "
            "surface later—in tests, in production, in code review. The bottleneck isn't "
            "decision speed, it's rework."
        ),

        mechanism=(
            "High bash_acceptance (>90%) + fast decisions (<500ms) = rubber-stamping. "
            "This works when AI suggestions are high-quality and low-risk. It fails when "
            "a single bad command has cascading consequences."
        ),

        recommendations=[
            "Add verification for destructive commands (rm, DROP, force push)",
            "Use --dry-run flags when available",
            "Set up pre-commit hooks as your safety net",
            "Trust but verify: spot-check 1 in 10 suggestions",
        ],

        risk="A single unreviewed command can undo hours of work",

        historical_parallel="Mongol Horde: trust the generals, move fast, accept losses",
    ),

    "Autocrat": ArchetypeInsight(
        name="Autocrat",

        language_game="The Review Game",
        game_description=(
            "You read everything but approve everything. You rule through witnessed "
            "consent—you must see the command, understand it, then accept it. "
            "The ritual matters even when the outcome is predetermined."
        ),

        bottleneck="Review time without filtering",
        bottleneck_description=(
            "You spend time reviewing suggestions you'll accept anyway. The bottleneck is "
            "attention spent on low-risk operations. Your review is thorough but not selective."
        ),

        mechanism=(
            "High acceptance (>85%) + slow decisions (>2s) = reviewing but not filtering. "
            "You're paying the cost of review without the benefit of rejection. This is "
            "cognitive overhead without risk reduction."
        ),

        recommendations=[
            "Identify which tool types actually need review (hint: usually just Bash)",
            "Auto-approve Read/Glob/Grep—they're side-effect free",
            "Focus review energy on commands with side effects",
            "Set up allow-lists for common safe patterns",
        ],

        risk="Review fatigue leads to rubber-stamping when it matters most",

        historical_parallel="Roman Emperor: sees all petitions, grants almost all",
    ),

    "Strategist": ArchetypeInsight(
        name="Strategist",

        language_game="The Discrimination Game",
        game_description=(
            "You rule differently depending on the stakes. Safe operations flow through "
            "unchallenged; risky operations face scrutiny. Same AI, different trust levels "
            "based on consequences."
        ),

        bottleneck="Decision overhead on edge cases",
        bottleneck_description=(
            "Your selective trust is efficient for clear-cut cases. The bottleneck is "
            "ambiguous commands—things that might be risky. You may over-deliberate on "
            "medium-risk operations."
        ),

        mechanism=(
            "High risk_delta (>30%) = different trust by tool type. You've learned that "
            "Read can't hurt you but Bash can. This is rational. The cost is decision "
            "latency on commands that fall between clear categories."
        ),

        recommendations=[
            "Codify your rules: which patterns always need review?",
            "Build muscle memory for common safe Bash patterns (ls, git status, etc.)",
            "Pre-approve specific commands you run frequently",
            "Your instincts are good—trust them faster on familiar patterns",
        ],

        risk="Over-indexing on tool type, under-indexing on command content",

        historical_parallel="Napoleon: trusts competent marshals, micromanages key battles",
    ),

    "Deliberator": ArchetypeInsight(
        name="Deliberator",

        language_game="The Consideration Game",
        game_description=(
            "Every suggestion is a proposal requiring thought. You rule through "
            "deliberation—nothing passes without due consideration. Speed is "
            "sacrificed for confidence."
        ),

        bottleneck="Decision latency on all operations",
        bottleneck_description=(
            "You take time on everything, even safe operations. The bottleneck is pure "
            "throughput—your careful approach limits how much you can accomplish in a "
            "session. Quality is high but quantity suffers."
        ),

        mechanism=(
            "Slow decisions (>5s mean) regardless of tool type = deliberative processing. "
            "This might indicate uncertainty, learning, or genuine caution. It might also "
            "indicate distraction or multitasking."
        ),

        recommendations=[
            "Identify your 'always safe' operations and fast-track them",
            "Use AI for exploration in dedicated sessions, then batch approvals",
            "If slow due to context-switching, dedicate focused time to AI work",
            "Your thoroughness is valuable—apply it selectively to high-stakes decisions",
        ],

        risk="Deliberation becomes procrastination; velocity drops below usefulness",

        historical_parallel="Athenian Assembly: thorough debate, slow action",
    ),

    "Council": ArchetypeInsight(
        name="Council",

        language_game="The Orchestration Game",
        game_description=(
            "You don't just use AI—you deploy it. Agents, parallel tasks, complex workflows. "
            "You rule through coordination—you're the conductor, AI is the orchestra."
        ),

        bottleneck="Coordination overhead",
        bottleneck_description=(
            "Managing multiple agents and complex workflows has overhead. The bottleneck is "
            "not individual decisions but overall orchestration—keeping track of what's "
            "running, what's done, what needs attention."
        ),

        mechanism=(
            "High agent_spawn_rate (>10%) + high tool_diversity (>6 unique) = power user "
            "leveraging Claude Code's full capabilities. This is sophisticated usage but "
            "requires mental overhead to manage."
        ),

        recommendations=[
            "Use TodoWrite to track parallel workstreams",
            "Batch similar operations rather than interleaving",
            "Set up project-specific contexts to reduce re-explanation",
            "Your orchestration skills are advanced—document your workflows for others",
        ],

        risk="Complexity becomes its own bottleneck; losing track of agent states",

        historical_parallel="Venetian Republic: distributed decision-making, complex coordination",
    ),

    "Constitutionalist": ArchetypeInsight(
        name="Constitutionalist",

        language_game="The Consistency Game",
        game_description=(
            "Your rule is predictable, session to session. You've developed stable "
            "patterns—implicit laws governing your AI interactions. Your governance "
            "has a constitution, even if unwritten."
        ),

        bottleneck="Rule rigidity",
        bottleneck_description=(
            "Consistent patterns are efficient but can become rigid. The bottleneck is "
            "adaptation—when situations call for different approaches, your habits may "
            "override situational judgment."
        ),

        mechanism=(
            "High session_consistency (>0.8) + moderate acceptance = stable behavioral "
            "patterns. You've found what works and you stick to it. This is efficient "
            "until the situation changes."
        ),

        recommendations=[
            "Periodically audit your implicit rules—are they still serving you?",
            "Try different approaches in low-stakes contexts to expand your range",
            "Your consistency is a strength—codify it explicitly in CLAUDE.md",
            "Teach your patterns to others; consistency is transferable",
        ],

        risk="Habits optimized for past contexts may not fit new ones",

        historical_parallel="Constitutional systems: stable rules, slow to adapt",
    ),
}


# ============================================================================
# Insight Generation
# ============================================================================

def get_archetype_insight(classification: Classification) -> ArchetypeInsight:
    """Get full insight for the classified archetype."""
    archetype = classification.archetype
    return ARCHETYPES.get(archetype, ARCHETYPES["Delegator"])


def get_primary_bottleneck(classification: Classification) -> str:
    """Get the one-line bottleneck summary."""
    insight = get_archetype_insight(classification)
    return insight.bottleneck


def get_top_recommendations(classification: Classification, n: int = 3) -> List[str]:
    """Get top N recommendations for this archetype."""
    insight = get_archetype_insight(classification)
    return insight.recommendations[:n]


def generate_insight_summary(classification: Classification) -> Dict:
    """Generate complete insight summary for display."""
    insight = get_archetype_insight(classification)

    return {
        "archetype": insight.name,
        "language_game": {
            "name": insight.language_game,
            "description": insight.game_description,
        },
        "bottleneck": {
            "summary": insight.bottleneck,
            "description": insight.bottleneck_description,
            "mechanism": insight.mechanism,
        },
        "recommendations": insight.recommendations,
        "risk": insight.risk,
        "historical_parallel": insight.historical_parallel,
    }


# ============================================================================
# Pattern-Specific Insights (beyond archetype)
# ============================================================================

def get_pattern_insight(classification: Classification) -> Dict:
    """Get insight based on the empirical pattern, not just archetype."""
    pattern = classification.primary_pattern
    features = classification.key_features
    subtle = classification.subtle_features

    insights = {
        "pattern": pattern,
        "key_observation": "",
        "what_it_means": "",
        "one_thing_to_try": "",
    }

    bash_rate = features.get("bash_acceptance_rate", 1.0)
    snap_rate = features.get("snap_judgment_rate", 0.5)
    sophistication = subtle.get("sophistication_score", 0)
    caution = subtle.get("caution_score", 0)

    if "Power User" in pattern and "Cautious" in pattern:
        insights["key_observation"] = (
            f"You accept {bash_rate:.0%} of Bash commands but use advanced features "
            f"(agents, diverse tools). You're selective about what you trust."
        )
        insights["what_it_means"] = (
            "Your bottleneck isn't trust calibration—it's already good. "
            "It's the cognitive overhead of being selective on every command."
        )
        insights["one_thing_to_try"] = (
            "Pre-approve your 10 most common safe Bash patterns. "
            "Save deliberation for genuinely novel commands."
        )

    elif "Power User" in pattern and "Trusting" in pattern:
        insights["key_observation"] = (
            f"You accept {bash_rate:.0%} of Bash commands and use advanced features freely. "
            f"High throughput, high trust."
        )
        insights["what_it_means"] = (
            "Your bottleneck is error discovery—you'll find problems downstream, "
            "in tests or production, not at the approval prompt."
        )
        insights["one_thing_to_try"] = (
            "Add one verification step for destructive commands. "
            "A single 'are you sure?' for rm -rf, DROP TABLE, force push."
        )

    elif "Casual" in pattern and "Cautious" in pattern:
        insights["key_observation"] = (
            f"You accept only {bash_rate:.0%} of Bash commands, but don't use advanced features. "
            f"Careful but not leveraging Claude Code's full capabilities."
        )
        insights["what_it_means"] = (
            "Your bottleneck is both velocity (careful review) and capability "
            "(not using agents, complex workflows). Double constraint."
        )
        insights["one_thing_to_try"] = (
            "Try the Task tool for one complex operation. "
            "Agents can do the risky exploration while you maintain oversight."
        )

    else:  # Casual (Trusting)
        insights["key_observation"] = (
            f"You accept {bash_rate:.0%} of Bash commands, decide quickly ({snap_rate:.0%} under 500ms). "
            f"Classic fast iteration pattern."
        )
        insights["what_it_means"] = (
            "Your bottleneck is rework—errors flow through uncaught. "
            "Fine for exploration, risky for production."
        )
        insights["one_thing_to_try"] = (
            "Before accepting commands that modify files, pause for 2 seconds. "
            "Just the pause, not deep review. See if it changes anything."
        )

    return insights
