"""
Archetype classification using 3-axis framework: Trust, Sophistication, Variance.
Six archetypes, priority-ordered. Thresholds tuned against simulated personas.
"""

import statistics
from typing import Dict, Optional, List

from .models import UserGovernanceProfile, Classification, ToolEvent
from .parser import ClaudeLogParser
from .analytics import analyze_trust_variance


def get_bash_acceptance_rate(profile: UserGovernanceProfile) -> float:
    bash_stats = profile.trust_by_tool.get('Bash', {})
    total = bash_stats.get('total', 0)
    return bash_stats.get('acceptance_rate', 1.0) if total else 1.0


def compute_sophistication_score(profile: UserGovernanceProfile, parser: ClaudeLogParser) -> float:
    """Agent usage, tool diversity, session depth, surgical ratio."""
    score = 0.0

    task_total = profile.trust_by_tool.get('Task', {}).get('total', 0)
    task_output_total = profile.trust_by_tool.get('TaskOutput', {}).get('total', 0)
    agent_rate = (task_total + task_output_total) / profile.total_tool_calls if profile.total_tool_calls else 0
    if agent_rate > 0.05:
        score += 0.3
    elif agent_rate > 0.02:
        score += 0.15

    diversities = []
    for session in parser.sessions.values():
        unique = {t for t, s in session.tool_breakdown.items() if s.get('accepted', 0) + s.get('rejected', 0) > 0}
        if unique:
            diversities.append(len(unique))
    diversity = statistics.mean(diversities) if diversities else 0
    if diversity > 6:
        score += 0.25
    elif diversity > 4:
        score += 0.1

    depths = [s.total_tool_calls for s in parser.sessions.values()]
    power_ratio = sum(1 for d in depths if d > 100) / len(depths) if depths else 0
    if power_ratio > 0.2:
        score += 0.25
    elif depths and statistics.mean(depths) > 50:
        score += 0.1

    read_total = profile.trust_by_tool.get('Read', {}).get('total', 0)
    glob_total = profile.trust_by_tool.get('Glob', {}).get('total', 0)
    grep_total = profile.trust_by_tool.get('Grep', {}).get('total', 0)
    if read_total and (glob_total + grep_total) / read_total > 0.3:
        score += 0.2

    return min(1.0, score)


def compute_variance_score(events: List[ToolEvent]) -> float:
    return analyze_trust_variance(events).variance_score


def get_subtle_features(profile: UserGovernanceProfile, parser: ClaudeLogParser) -> Dict[str, float]:
    features = {}
    tc = profile.total_tool_calls or 1

    task_total = profile.trust_by_tool.get('Task', {}).get('total', 0)
    task_output_total = profile.trust_by_tool.get('TaskOutput', {}).get('total', 0)
    features['agent_spawn_rate'] = (task_total + task_output_total) / tc

    diversities = []
    for session in parser.sessions.values():
        unique = {t for t, s in session.tool_breakdown.items() if s.get('accepted', 0) + s.get('rejected', 0) > 0}
        if unique:
            diversities.append(len(unique))
    features['tool_diversity'] = statistics.mean(diversities) if diversities else 0

    depths = [s.total_tool_calls for s in parser.sessions.values()]
    features['session_depth'] = statistics.mean(depths) if depths else 0
    features['max_session_depth'] = max(depths) if depths else 0
    features['power_session_ratio'] = sum(1 for d in depths if d > 100) / len(depths) if depths else 0

    edit_total = profile.trust_by_tool.get('Edit', {}).get('total', 0)
    write_total = profile.trust_by_tool.get('Write', {}).get('total', 0)
    features['edit_intensity'] = (edit_total + write_total) / tc

    read_total = profile.trust_by_tool.get('Read', {}).get('total', 0)
    features['read_intensity'] = read_total / tc

    glob_total = profile.trust_by_tool.get('Glob', {}).get('total', 0)
    grep_total = profile.trust_by_tool.get('Grep', {}).get('total', 0)
    features['search_intensity'] = (glob_total + grep_total) / tc
    features['surgical_ratio'] = (glob_total + grep_total) / read_total if read_total else 0

    return features


def classify_archetype(trust: float, sophistication: float, variance: float) -> str:
    """Priority-ordered: Adaptive > Delegator > Council > Guardian > Strategist > Constitutionalist."""
    if variance >= 0.3:
        return "Adaptive"
    if trust > 0.8 and sophistication < 0.4:
        return "Delegator"
    if trust > 0.7 and sophistication >= 0.4:
        return "Council"
    if trust < 0.5 and sophistication < 0.4:
        return "Guardian"
    if trust < 0.7 and sophistication >= 0.4:
        return "Strategist"
    return "Constitutionalist"


def get_archetype_description(archetype: str) -> str:
    return {
        "Adaptive": "Context-dependent governance. Different rules for different contexts.",
        "Delegator": "Full trust in AI execution. Let the machine do its work.",
        "Council": "Leverages AI sophistication while maintaining trust. Collaborative power.",
        "Guardian": "Protective oversight. Careful review before action.",
        "Strategist": "Selective delegation. Trust where it matters, control where it counts.",
        "Constitutionalist": "Consistent moderate policy. Balanced approach across contexts.",
    }.get(archetype, "")


def classify_user(
    profile: UserGovernanceProfile,
    parser: Optional[ClaudeLogParser] = None,
    events: Optional[List[ToolEvent]] = None
) -> Classification:
    trust = get_bash_acceptance_rate(profile)
    overall_rate = profile.acceptance_rate

    sophistication = 0.0
    subtle = {}
    if parser:
        sophistication = compute_sophistication_score(profile, parser)
        subtle = get_subtle_features(profile, parser)

    variance = 0.0
    if events:
        variance = compute_variance_score(events)
    elif parser:
        variance = compute_variance_score(parser.all_events)

    if trust > 0.7:
        primary_pattern = "Power User (Trusting)" if sophistication > 0.4 else "Casual (Trusting)"
    else:
        primary_pattern = "Power User (Cautious)" if sophistication > 0.4 else "Casual (Cautious)"

    pattern_confidence = 0.5 + abs(trust - 0.5) * 0.5 + abs(sophistication - 0.5) * 0.3
    archetype = classify_archetype(trust, sophistication, variance)
    archetype_scores = compute_archetype_scores(trust, sophistication, variance)

    subtle['sophistication_score'] = sophistication
    subtle['variance_score'] = variance
    subtle['trust_level'] = trust

    return Classification(
        primary_pattern=primary_pattern,
        pattern_confidence=min(1.0, pattern_confidence),
        archetype=archetype,
        archetype_confidence=archetype_scores[archetype],
        archetype_scores=archetype_scores,
        key_features={
            "bash_acceptance_rate": trust,
            "overall_acceptance_rate": overall_rate,
            "sophistication": sophistication,
            "variance": variance,
            "mean_decision_time_ms": profile.mean_decision_time_ms,
            "risk_trust_delta": profile.trust_delta_by_risk,
        },
        subtle_features=subtle,
    )


def compute_archetype_scores(trust: float, sophistication: float, variance: float) -> Dict[str, float]:
    scores = {
        "Adaptive": variance,
        "Delegator": trust * (1 - sophistication) * (1 - variance),
        "Council": trust * sophistication * (1 - variance),
        "Guardian": (1 - trust) * (1 - sophistication) * (1 - variance),
        "Strategist": (1 - abs(trust - 0.5)) * sophistication * (1 - variance),
        "Constitutionalist": (1 - abs(trust - 0.7)) * (1 - abs(sophistication - 0.5)) * (1 - variance),
    }
    total = sum(scores.values())
    return {k: v / total for k, v in scores.items()} if total else {k: 1/6 for k in scores}
