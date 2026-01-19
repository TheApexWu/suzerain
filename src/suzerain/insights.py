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


ARCHETYPES: Dict[str, ArchetypeInsight] = {

    "Adaptive": ArchetypeInsight(
        name="Adaptive",

        language_game="The Context Game",
        game_description=(
            "You govern differently depending on context. Maintenance project? Trust flows freely. "
            "Critical build? Every command scrutinized. Same AI, same you, different rules. "
            "Your governance adapts to stakes."
        ),

        bottleneck="Context-switching overhead",
        bottleneck_description=(
            "Your adaptability is powerful but requires constant recalibration. The bottleneck is "
            "the mental overhead of maintaining different trust levels for different contexts. "
            "Each project switch costs cognitive load."
        ),

        mechanism=(
            "High variance score (>0.3) = different acceptance rates across projects/sessions. "
            "This is sophisticated governance—you've learned that context matters. The cost is "
            "having to remember which rules apply where."
        ),

        recommendations=[
            "Codify your context rules explicitly in per-project CLAUDE.md files",
            "Use project-specific permission settings in Claude Code",
            "Consider whether your low-trust contexts are actually higher risk, or just feel that way",
            "Your adaptability is a strength—document it so others can learn from it",
        ],

        risk="Context confusion—applying low-trust rules when high-trust would be more efficient",

        historical_parallel="Akbar the Great: one Mughal throne, different laws for each faith",
    ),

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

        historical_parallel="Cyrus the Great: let satraps rule, but the empire is mine",
    ),

    "Guardian": ArchetypeInsight(
        name="Guardian",

        language_game="The Protection Game",
        game_description=(
            "You protect the gates. Every command is reviewed carefully before execution. "
            "Minimal AI authority—you're the final arbiter of what runs. Security and "
            "control over velocity."
        ),

        bottleneck="Throughput limited by review",
        bottleneck_description=(
            "Your careful review of everything limits how much you can accomplish. The bottleneck "
            "is pure velocity—your protective approach trades speed for safety. This is "
            "appropriate for high-stakes environments, expensive otherwise."
        ),

        mechanism=(
            "Low bash_acceptance (<50%) + low sophistication = protective oversight. "
            "You don't delegate much to AI, and you don't let it execute freely. This works "
            "when errors are costly. It's expensive when they're cheap."
        ),

        recommendations=[
            "Identify truly safe operations and fast-track them",
            "Use AI for exploration, then manually execute critical commands",
            "Your caution is valuable for high-stakes work—own it",
            "Consider auto-approving read-only operations to gain velocity",
        ],

        risk="Overcaution becomes a bottleneck; velocity drops below usefulness",

        historical_parallel="Ming Dynasty: the Great Wall exists because the Emperor commands it",
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

        historical_parallel="Ottoman Sultan: viziers execute, but the Sublime Porte decides",
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

        historical_parallel="Hammurabi: the code is the code, carved in stone for all",
    ),
}


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
    sophistication = features.get("sophistication", 0)
    variance = features.get("variance", 0)

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
            f"You accept {bash_rate:.0%} of Bash commands with straightforward usage. "
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


def get_prompting_approaches(classification: Classification) -> Dict:
    """
    Get concrete prompting approaches based on the user's pattern.
    Not generic advice - actual prompts and workflows to try.
    """
    pattern = classification.primary_pattern
    features = classification.key_features
    subtle = classification.subtle_features

    bash_rate = features.get("bash_acceptance_rate", 1.0)
    sophistication = features.get("sophistication", 0)
    variance = features.get("variance", 0)
    agent_rate = subtle.get("agent_spawn_rate", 0)

    approaches = {
        "thinking_framework": "",
        "prompt_to_try": "",
        "claude_md_suggestion": "",
        "workflow_shift": "",
    }

    if bash_rate > 0.85:
        # High trust - need verification without slowing down
        approaches["thinking_framework"] = (
            "Shift from 'accept/reject' to 'accept/accept with check'. "
            "You're fast, stay fast, but add a verification layer."
        )
        approaches["prompt_to_try"] = (
            "Before running commands that modify or delete, "
            "list what will change and ask me to confirm."
        )
        approaches["claude_md_suggestion"] = (
            "Add to CLAUDE.md: 'For rm, git push --force, or DROP commands, "
            "always show a dry-run or preview first.'"
        )
        approaches["workflow_shift"] = (
            "Use Claude's planning mode for multi-step operations. "
            "Let it draft the full plan, review once, then execute."
        )

    elif bash_rate < 0.5:
        # Low trust - need efficiency without losing control
        approaches["thinking_framework"] = (
            "You're reviewing everything. That's fine for unfamiliar territory, "
            "but expensive for routine operations. Separate the two."
        )
        approaches["prompt_to_try"] = (
            "I trust you for: ls, cat, git status, git diff, grep, find. "
            "Run those without asking. For everything else, explain first."
        )
        approaches["claude_md_suggestion"] = (
            "Add to CLAUDE.md: 'Safe commands (read-only, no side effects) "
            "can run without confirmation. Destructive commands need approval.'"
        )
        approaches["workflow_shift"] = (
            "Try agents (Task tool) for exploration. They can do the risky "
            "poking around while you review only the final output."
        )

    else:
        # Middle ground - optimize the decision boundary
        approaches["thinking_framework"] = (
            "You're already discriminating by risk. The question is whether "
            "your categories match actual risk, or just perceived risk."
        )
        approaches["prompt_to_try"] = (
            "When I reject a command, tell me why it might have seemed risky "
            "and whether that risk was real. Help me calibrate."
        )
        approaches["claude_md_suggestion"] = (
            "Add to CLAUDE.md: 'Explain the risk level (none/low/medium/high) "
            "before suggesting commands that modify files or state.'"
        )
        approaches["workflow_shift"] = (
            "Track your rejections for a week. Are they catching real risks "
            "or just unfamiliar patterns? Adjust your threshold accordingly."
        )

    # Agent-specific advice
    if agent_rate < 0.02:
        approaches["agent_advice"] = (
            "You're not using agents. Try: 'Use the Task tool to explore "
            "this codebase and find where X is implemented.' Agents are "
            "good for uncertain searches where you'd otherwise iterate."
        )
    elif agent_rate > 0.15:
        approaches["agent_advice"] = (
            "Heavy agent user. Make sure you're not over-orchestrating. "
            "Sometimes a direct command is faster than spawning an agent."
        )

    return approaches
