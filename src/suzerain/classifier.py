"""
Archetype classification.

Two outputs:
1. Primary Pattern - what the data shows (Power/Casual x Trusting/Cautious)
2. Narrative Archetype - the six archetypes for display

Thresholds are hand-tuned. See docs/METHODOLOGY.md for caveats.
"""

import statistics
from typing import Dict, Any, Optional

from .models import UserGovernanceProfile, Classification
from .parser import ClaudeLogParser


def get_bash_acceptance_rate(profile: UserGovernanceProfile) -> float:
    """Get Bash-specific acceptance rate - THE key discriminator."""
    bash_stats = profile.trust_by_tool.get('Bash', {})
    total = bash_stats.get('total', 0)
    if total == 0:
        return 1.0
    return bash_stats.get('acceptance_rate', 1.0)


def get_snap_judgment_rate(parser: ClaudeLogParser) -> float:
    """Percentage of decisions made in < 500ms (rubber-stamping)."""
    all_times = []
    for session in parser.sessions.values():
        all_times.extend(session.decision_times_ms)
    if not all_times:
        return 0.5
    snap = sum(1 for t in all_times if t < 500)
    return snap / len(all_times)


def compute_subtle_features(profile: UserGovernanceProfile, parser: ClaudeLogParser) -> Dict[str, float]:
    """
    Compute subtle features that discriminate between user types.
    """
    features = {}

    # Agent spawn rate
    task_total = profile.trust_by_tool.get('Task', {}).get('total', 0)
    task_output_total = profile.trust_by_tool.get('TaskOutput', {}).get('total', 0)
    agent_calls = task_total + task_output_total
    features['agent_spawn_rate'] = agent_calls / profile.total_tool_calls if profile.total_tool_calls > 0 else 0

    # Tool diversity
    diversities = []
    for session in parser.sessions.values():
        unique_tools = set()
        for tool, stats in session.tool_breakdown.items():
            if stats.get('accepted', 0) + stats.get('rejected', 0) > 0:
                unique_tools.add(tool)
        if unique_tools:
            diversities.append(len(unique_tools))
    features['tool_diversity'] = statistics.mean(diversities) if diversities else 0

    # Session depth
    depths = [s.total_tool_calls for s in parser.sessions.values()]
    features['session_depth'] = statistics.mean(depths) if depths else 0
    features['max_session_depth'] = max(depths) if depths else 0

    # Power session ratio
    power_sessions = sum(1 for d in depths if d > 100)
    features['power_session_ratio'] = power_sessions / len(depths) if depths else 0

    # Edit intensity
    edit_total = profile.trust_by_tool.get('Edit', {}).get('total', 0)
    write_total = profile.trust_by_tool.get('Write', {}).get('total', 0)
    features['edit_intensity'] = (edit_total + write_total) / profile.total_tool_calls if profile.total_tool_calls > 0 else 0

    # Read intensity
    read_total = profile.trust_by_tool.get('Read', {}).get('total', 0)
    features['read_intensity'] = read_total / profile.total_tool_calls if profile.total_tool_calls > 0 else 0

    # Search intensity
    glob_total = profile.trust_by_tool.get('Glob', {}).get('total', 0)
    grep_total = profile.trust_by_tool.get('Grep', {}).get('total', 0)
    features['search_intensity'] = (glob_total + grep_total) / profile.total_tool_calls if profile.total_tool_calls > 0 else 0

    # Surgical ratio
    if read_total > 0:
        features['surgical_ratio'] = (glob_total + grep_total) / read_total
    else:
        features['surgical_ratio'] = 0

    return features


def classify_user(profile: UserGovernanceProfile, parser: Optional[ClaudeLogParser] = None) -> Classification:
    """
    Classify user's governance style.

    Returns both empirical pattern and narrative archetype.
    """
    # Primary features
    bash_rate = get_bash_acceptance_rate(profile)
    overall_rate = profile.acceptance_rate
    decision_time = profile.mean_decision_time_ms
    risk_delta = profile.trust_delta_by_risk

    snap_rate = 0.5
    if parser:
        snap_rate = get_snap_judgment_rate(parser)

    # Subtle features
    subtle = {}
    if parser:
        subtle = compute_subtle_features(profile, parser)

    agent_rate = subtle.get('agent_spawn_rate', 0)
    diversity = subtle.get('tool_diversity', 3)
    depth = subtle.get('session_depth', 50)
    power_ratio = subtle.get('power_session_ratio', 0)
    surgical = subtle.get('surgical_ratio', 0)
    edit_intensity = subtle.get('edit_intensity', 0)

    # Sophistication score (0-1)
    sophistication = 0.0
    if agent_rate > 0.05:
        sophistication += 0.3
    if diversity > 6:
        sophistication += 0.25
    elif diversity > 4:
        sophistication += 0.1
    if power_ratio > 0.2:
        sophistication += 0.25
    if surgical > 0.3:
        sophistication += 0.2

    # Caution score (0-1)
    caution = 0.0
    if bash_rate < 0.6:
        caution += 0.5
    elif bash_rate < 0.8:
        caution += 0.25
    if risk_delta > 0.3:
        caution += 0.3
    if snap_rate < 0.4:
        caution += 0.2

    # Primary pattern (empirical)
    if sophistication > 0.5 and caution > 0.4:
        primary_pattern = "Power User (Cautious)"
        pattern_confidence = (sophistication + caution) / 2
    elif sophistication > 0.5:
        primary_pattern = "Power User (Trusting)"
        pattern_confidence = sophistication
    elif caution > 0.5:
        primary_pattern = "Casual (Cautious)"
        pattern_confidence = caution
    else:
        primary_pattern = "Casual (Trusting)"
        pattern_confidence = 1 - max(sophistication, caution)

    # Narrative archetype scores
    archetype_scores = {
        "Autocrat": 0.0,
        "Council": 0.0,
        "Deliberator": 0.0,
        "Delegator": 0.0,
        "Constitutionalist": 0.0,
        "Strategist": 0.0,
    }

    # Delegator: High trust + fast + low sophistication
    if bash_rate >= 0.85 and snap_rate > 0.5 and sophistication < 0.3:
        archetype_scores["Delegator"] = 0.8
    elif bash_rate >= 0.9:
        archetype_scores["Delegator"] = 0.4

    # Autocrat: High trust + slow
    if bash_rate >= 0.85 and snap_rate < 0.4 and decision_time > 2000:
        archetype_scores["Autocrat"] = 0.7

    # Strategist: High sophistication + selective trust
    if sophistication > 0.4 and risk_delta > 0.2:
        archetype_scores["Strategist"] = 0.8
    elif sophistication > 0.3 and bash_rate < 0.8:
        archetype_scores["Strategist"] = 0.5

    # Deliberator: Slow + cautious
    if decision_time > 5000 and caution > 0.4:
        archetype_scores["Deliberator"] = 0.7
    elif decision_time > 3000:
        archetype_scores["Deliberator"] = 0.3

    # Council: High tool variance + uses agents
    if agent_rate > 0.1 and diversity > 6:
        archetype_scores["Council"] = 0.6

    # Constitutionalist: Consistent patterns
    if profile.session_consistency > 0.8 and 0.6 < bash_rate < 0.9:
        archetype_scores["Constitutionalist"] = 0.5

    # Normalize
    total = sum(archetype_scores.values())
    if total > 0:
        archetype_scores = {k: v / total for k, v in archetype_scores.items()}
    else:
        archetype_scores["Delegator"] = 1.0

    best = max(archetype_scores.items(), key=lambda x: x[1])

    subtle['sophistication_score'] = sophistication
    subtle['caution_score'] = caution

    return Classification(
        primary_pattern=primary_pattern,
        pattern_confidence=pattern_confidence,
        archetype=best[0],
        archetype_confidence=best[1],
        archetype_scores=archetype_scores,
        key_features={
            "bash_acceptance_rate": bash_rate,
            "overall_acceptance_rate": overall_rate,
            "mean_decision_time_ms": decision_time,
            "risk_trust_delta": risk_delta,
            "snap_judgment_rate": snap_rate,
        },
        subtle_features=subtle,
    )
