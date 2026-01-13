#!/usr/bin/env python3
"""
Suzerain Log Parser

Extracts governance behavior from Claude Code's existing logs.
No manual instrumentation needed - parse what already exists.

Usage:
    python scripts/parse_claude_logs.py                    # Analyze all sessions
    python scripts/parse_claude_logs.py --project suzerain # Specific project
    python scripts/parse_claude_logs.py --session <id>     # Specific session
    python scripts/parse_claude_logs.py --export           # Export features to JSON
"""

import json
import argparse
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from collections import defaultdict
import statistics


# ============================================================================
# Configuration
# ============================================================================

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"
OUTPUT_DIR = Path.home() / ".suzerain" / "analysis"


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class ToolEvent:
    """A single tool use/result pair - the atomic unit of governance."""
    session_id: str
    timestamp: datetime
    tool_name: str
    tool_id: str

    # The governance decision
    accepted: bool
    rejected: bool
    error_message: Optional[str] = None

    # Timing (if we can compute it)
    request_timestamp: Optional[datetime] = None
    response_timestamp: Optional[datetime] = None
    decision_time_ms: Optional[int] = None

    # Context
    project: Optional[str] = None
    git_branch: Optional[str] = None

    # Tool-specific
    tool_input: Optional[Dict] = None
    tool_output_preview: Optional[str] = None


@dataclass
class SessionAnalysis:
    """Governance analysis for a single session."""
    session_id: str
    project: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: float = 0.0

    # Counts
    total_tool_calls: int = 0
    accepted: int = 0
    rejected: int = 0
    errors: int = 0

    # By tool type
    tool_breakdown: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Computed metrics
    acceptance_rate: float = 0.0
    rejection_rate: float = 0.0

    # Timing
    decision_times_ms: List[int] = field(default_factory=list)
    mean_decision_time_ms: float = 0.0


@dataclass
class UserGovernanceProfile:
    """Aggregate governance profile across all sessions."""

    # === CONTROL ===
    total_tool_calls: int = 0
    total_accepted: int = 0
    total_rejected: int = 0
    acceptance_rate: float = 0.0
    rejection_rate: float = 0.0

    # === BY TOOL TYPE ===
    # Maps tool_name -> {accepted, rejected, total}
    trust_by_tool: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # === TEMPO ===
    mean_decision_time_ms: float = 0.0
    decision_time_variance: float = 0.0

    # === PATTERNS ===
    sessions_analyzed: int = 0
    session_acceptance_rates: List[float] = field(default_factory=list)
    session_consistency: float = 0.0  # 1 - CV of acceptance rates

    # === RISK PROXY ===
    # Some tools are higher risk (Bash, Write) vs lower (Read, Glob)
    high_risk_acceptance: float = 0.0
    low_risk_acceptance: float = 0.0
    trust_delta_by_risk: float = 0.0

    # Metadata
    first_session: Optional[str] = None
    last_session: Optional[str] = None
    data_collection_days: int = 0


# ============================================================================
# Log Parser
# ============================================================================

class ClaudeLogParser:
    """Parses Claude Code logs to extract governance events."""

    # Tool risk classification
    HIGH_RISK_TOOLS = {'Bash', 'Write', 'Edit', 'NotebookEdit'}
    LOW_RISK_TOOLS = {'Read', 'Glob', 'Grep', 'WebFetch', 'WebSearch'}

    def __init__(self, project_filter: Optional[str] = None):
        self.project_filter = project_filter
        self.sessions: Dict[str, SessionAnalysis] = {}
        self.all_events: List[ToolEvent] = []

    def find_session_files(self) -> List[Path]:
        """Find all session .jsonl files."""
        if not PROJECTS_DIR.exists():
            print(f"No Claude projects found at {PROJECTS_DIR}")
            return []

        session_files = []
        for project_dir in PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue

            # Filter by project name if specified
            if self.project_filter:
                if self.project_filter.lower() not in project_dir.name.lower():
                    continue

            # Find .jsonl files (sessions)
            for f in project_dir.glob("*.jsonl"):
                # Skip agent files
                if f.name.startswith("agent-"):
                    continue
                session_files.append(f)

        return sorted(session_files, key=lambda x: x.stat().st_mtime)

    def parse_session(self, session_file: Path) -> SessionAnalysis:
        """Parse a single session file."""
        session_id = session_file.stem
        project = session_file.parent.name

        analysis = SessionAnalysis(
            session_id=session_id,
            project=project,
            tool_breakdown=defaultdict(lambda: {"accepted": 0, "rejected": 0, "errors": 0})
        )

        # Track tool_use -> tool_result pairs
        pending_tools: Dict[str, Dict] = {}  # tool_id -> {timestamp, tool_name, input}

        events = []
        with open(session_file, 'r') as f:
            for line in f:
                try:
                    events.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue

        for event in events:
            event_type = event.get('type')
            timestamp_str = event.get('timestamp')
            timestamp = None
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                except:
                    pass

            # Track session timing
            if timestamp:
                if analysis.start_time is None or timestamp < analysis.start_time:
                    analysis.start_time = timestamp
                if analysis.end_time is None or timestamp > analysis.end_time:
                    analysis.end_time = timestamp

            if event_type == 'assistant':
                # Look for tool_use in assistant message
                message = event.get('message', {})
                content = message.get('content', [])

                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'tool_use':
                        tool_id = item.get('id')
                        tool_name = item.get('name', 'unknown')
                        tool_input = item.get('input', {})

                        # Store pending tool call
                        pending_tools[tool_id] = {
                            'timestamp': timestamp,
                            'tool_name': tool_name,
                            'input': tool_input,
                        }

            elif event_type == 'user':
                # Look for tool_result in user message
                message = event.get('message', {})
                content = message.get('content', [])

                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'tool_result':
                            tool_id = item.get('tool_use_id')
                            is_error = item.get('is_error', False)
                            result_content = item.get('content', '')

                            # Match with pending tool
                            pending = pending_tools.pop(tool_id, None)
                            if not pending:
                                continue

                            tool_name = pending['tool_name']
                            # Normalize tool name (remove mcp__ prefix)
                            if tool_name.startswith('mcp__'):
                                tool_name = tool_name.split('__')[-1]

                            # Determine if accepted/rejected
                            rejected = False
                            accepted = False

                            if is_error:
                                if 'requires approval' in str(result_content).lower():
                                    rejected = True
                                else:
                                    # Other error (not governance-related)
                                    analysis.errors += 1
                                    analysis.tool_breakdown[tool_name]["errors"] += 1
                            else:
                                accepted = True

                            # Record the event
                            if accepted or rejected:
                                analysis.total_tool_calls += 1

                                if accepted:
                                    analysis.accepted += 1
                                    analysis.tool_breakdown[tool_name]["accepted"] += 1
                                elif rejected:
                                    analysis.rejected += 1
                                    analysis.tool_breakdown[tool_name]["rejected"] += 1

                                # Compute decision time if we have both timestamps
                                decision_time_ms = None
                                if pending['timestamp'] and timestamp:
                                    delta = timestamp - pending['timestamp']
                                    decision_time_ms = int(delta.total_seconds() * 1000)
                                    if 0 < decision_time_ms < 300000:  # Sanity check: < 5 min
                                        analysis.decision_times_ms.append(decision_time_ms)

                                # Store full event
                                tool_event = ToolEvent(
                                    session_id=session_id,
                                    timestamp=timestamp,
                                    tool_name=tool_name,
                                    tool_id=tool_id,
                                    accepted=accepted,
                                    rejected=rejected,
                                    error_message=result_content if is_error else None,
                                    request_timestamp=pending['timestamp'],
                                    response_timestamp=timestamp,
                                    decision_time_ms=decision_time_ms,
                                    project=project,
                                    tool_input=pending['input'],
                                )
                                self.all_events.append(tool_event)

        # Compute session metrics
        if analysis.total_tool_calls > 0:
            analysis.acceptance_rate = analysis.accepted / analysis.total_tool_calls
            analysis.rejection_rate = analysis.rejected / analysis.total_tool_calls

        if analysis.decision_times_ms:
            analysis.mean_decision_time_ms = statistics.mean(analysis.decision_times_ms)

        if analysis.start_time and analysis.end_time:
            analysis.duration_minutes = (analysis.end_time - analysis.start_time).total_seconds() / 60

        # Convert defaultdict to regular dict
        analysis.tool_breakdown = dict(analysis.tool_breakdown)

        return analysis

    def parse_all_sessions(self) -> Dict[str, SessionAnalysis]:
        """Parse all session files."""
        session_files = self.find_session_files()
        print(f"Found {len(session_files)} session files")

        for f in session_files:
            try:
                analysis = self.parse_session(f)
                if analysis.total_tool_calls > 0:  # Only keep sessions with tool calls
                    self.sessions[analysis.session_id] = analysis
            except Exception as e:
                print(f"Error parsing {f.name}: {e}")

        print(f"Parsed {len(self.sessions)} sessions with tool calls")
        return self.sessions

    def compute_governance_profile(self) -> UserGovernanceProfile:
        """Compute aggregate governance profile from all sessions."""
        profile = UserGovernanceProfile()

        if not self.sessions:
            return profile

        # Aggregate across sessions
        all_decision_times = []
        tool_stats = defaultdict(lambda: {"accepted": 0, "rejected": 0, "total": 0})

        for session in self.sessions.values():
            profile.total_tool_calls += session.total_tool_calls
            profile.total_accepted += session.accepted
            profile.total_rejected += session.rejected

            if session.acceptance_rate > 0:
                profile.session_acceptance_rates.append(session.acceptance_rate)

            all_decision_times.extend(session.decision_times_ms)

            for tool_name, counts in session.tool_breakdown.items():
                tool_stats[tool_name]["accepted"] += counts.get("accepted", 0)
                tool_stats[tool_name]["rejected"] += counts.get("rejected", 0)
                tool_stats[tool_name]["total"] += counts.get("accepted", 0) + counts.get("rejected", 0)

        # Compute rates
        if profile.total_tool_calls > 0:
            profile.acceptance_rate = profile.total_accepted / profile.total_tool_calls
            profile.rejection_rate = profile.total_rejected / profile.total_tool_calls

        # Tool-level trust
        for tool_name, stats in tool_stats.items():
            if stats["total"] > 0:
                stats["acceptance_rate"] = stats["accepted"] / stats["total"]
            profile.trust_by_tool[tool_name] = dict(stats)

        # Timing
        if all_decision_times:
            profile.mean_decision_time_ms = statistics.mean(all_decision_times)
            if len(all_decision_times) > 1:
                profile.decision_time_variance = statistics.stdev(all_decision_times) / profile.mean_decision_time_ms

        # Session consistency
        if len(profile.session_acceptance_rates) > 1:
            mean_rate = statistics.mean(profile.session_acceptance_rates)
            std_rate = statistics.stdev(profile.session_acceptance_rates)
            if mean_rate > 0:
                profile.session_consistency = 1 - (std_rate / mean_rate)

        # Risk-based trust
        high_risk_accepted = sum(
            tool_stats[t]["accepted"] for t in self.HIGH_RISK_TOOLS if t in tool_stats
        )
        high_risk_total = sum(
            tool_stats[t]["total"] for t in self.HIGH_RISK_TOOLS if t in tool_stats
        )
        low_risk_accepted = sum(
            tool_stats[t]["accepted"] for t in self.LOW_RISK_TOOLS if t in tool_stats
        )
        low_risk_total = sum(
            tool_stats[t]["total"] for t in self.LOW_RISK_TOOLS if t in tool_stats
        )

        if high_risk_total > 0:
            profile.high_risk_acceptance = high_risk_accepted / high_risk_total
        if low_risk_total > 0:
            profile.low_risk_acceptance = low_risk_accepted / low_risk_total

        profile.trust_delta_by_risk = profile.low_risk_acceptance - profile.high_risk_acceptance

        # Metadata
        profile.sessions_analyzed = len(self.sessions)

        timestamps = [s.start_time for s in self.sessions.values() if s.start_time]
        if timestamps:
            profile.first_session = min(timestamps).isoformat()
            profile.last_session = max(timestamps).isoformat()
            profile.data_collection_days = (max(timestamps) - min(timestamps)).days + 1

        return profile


# ============================================================================
# Archetype Classification (Empirically Grounded)
# ============================================================================

def get_bash_acceptance_rate(profile: UserGovernanceProfile) -> float:
    """Get Bash-specific acceptance rate - THE key discriminator."""
    bash_stats = profile.trust_by_tool.get('Bash', {})
    total = bash_stats.get('total', 0)
    if total == 0:
        return 1.0  # No Bash usage = default to trusting
    return bash_stats.get('acceptance_rate', 1.0)


def get_snap_judgment_rate(profile: UserGovernanceProfile, parser: 'ClaudeLogParser') -> float:
    """Percentage of decisions made in < 500ms (rubber-stamping)."""
    all_times = []
    for session in parser.sessions.values():
        all_times.extend(session.decision_times_ms)
    if not all_times:
        return 0.0
    snap = sum(1 for t in all_times if t < 500)
    return snap / len(all_times)


def compute_subtle_features(profile: UserGovernanceProfile, parser: 'ClaudeLogParser') -> Dict[str, float]:
    """
    Compute subtle features that discriminate between user types.
    Based on empirical analysis showing variance in these dimensions.
    """
    features = {}

    # 1. Agent spawn rate - power user signal
    task_total = profile.trust_by_tool.get('Task', {}).get('total', 0)
    task_output_total = profile.trust_by_tool.get('TaskOutput', {}).get('total', 0)
    agent_calls = task_total + task_output_total
    features['agent_spawn_rate'] = agent_calls / profile.total_tool_calls if profile.total_tool_calls > 0 else 0

    # 2. Tool diversity - unique tools per session (averaged)
    diversities = []
    for session in parser.sessions.values():
        unique_tools = set()
        for tool, stats in session.tool_breakdown.items():
            if stats.get('accepted', 0) + stats.get('rejected', 0) > 0:
                unique_tools.add(tool)
        if unique_tools:
            diversities.append(len(unique_tools))
    features['mean_tool_diversity'] = statistics.mean(diversities) if diversities else 0

    # 3. Session depth - tool calls per session (averaged)
    depths = [s.total_tool_calls for s in parser.sessions.values()]
    features['mean_session_depth'] = statistics.mean(depths) if depths else 0
    features['max_session_depth'] = max(depths) if depths else 0

    # 4. Power session ratio - sessions with >100 tool calls
    power_sessions = sum(1 for d in depths if d > 100)
    features['power_session_ratio'] = power_sessions / len(depths) if depths else 0

    # 5. Edit intensity - (Edit + Write) / total
    edit_total = profile.trust_by_tool.get('Edit', {}).get('total', 0)
    write_total = profile.trust_by_tool.get('Write', {}).get('total', 0)
    features['edit_intensity'] = (edit_total + write_total) / profile.total_tool_calls if profile.total_tool_calls > 0 else 0

    # 6. Read intensity - Read / total (exploration signal)
    read_total = profile.trust_by_tool.get('Read', {}).get('total', 0)
    features['read_intensity'] = read_total / profile.total_tool_calls if profile.total_tool_calls > 0 else 0

    # 7. Search intensity - (Glob + Grep) / total
    glob_total = profile.trust_by_tool.get('Glob', {}).get('total', 0)
    grep_total = profile.trust_by_tool.get('Grep', {}).get('total', 0)
    features['search_intensity'] = (glob_total + grep_total) / profile.total_tool_calls if profile.total_tool_calls > 0 else 0

    # 8. Surgical ratio - approximation based on tool mix
    # Higher = more targeted (search before read)
    if read_total > 0:
        features['surgical_ratio'] = (glob_total + grep_total) / read_total
    else:
        features['surgical_ratio'] = 0

    return features


def classify_archetype_empirical(profile: UserGovernanceProfile, parser: 'ClaudeLogParser' = None) -> Dict[str, Any]:
    """
    Empirically-grounded archetype classification using subtle features.

    Primary discriminators (from data analysis):
    1. bash_acceptance_rate - THE key governance signal
    2. agent_spawn_rate - power user indicator
    3. tool_diversity - sophistication signal
    4. session_depth - engagement level
    5. surgical_ratio - targeted vs shotgun approach

    Maps to 3 empirical clusters, then 6 narrative archetypes.
    """

    # Get primary features
    bash_rate = get_bash_acceptance_rate(profile)
    overall_rate = profile.acceptance_rate
    decision_time = profile.mean_decision_time_ms
    risk_delta = profile.trust_delta_by_risk

    snap_rate = 0.5
    if parser:
        snap_rate = get_snap_judgment_rate(profile, parser)

    # Get subtle features
    subtle = {}
    if parser:
        subtle = compute_subtle_features(profile, parser)

    agent_rate = subtle.get('agent_spawn_rate', 0)
    diversity = subtle.get('mean_tool_diversity', 3)
    depth = subtle.get('mean_session_depth', 50)
    power_ratio = subtle.get('power_session_ratio', 0)
    surgical = subtle.get('surgical_ratio', 0)
    edit_intensity = subtle.get('edit_intensity', 0)

    # =========================================================================
    # TIER 1: Empirical Cluster (what the data shows)
    # =========================================================================

    # Compute sophistication score (0-1)
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

    # Compute caution score (0-1)
    caution = 0.0
    if bash_rate < 0.6:
        caution += 0.5
    elif bash_rate < 0.8:
        caution += 0.25
    if risk_delta > 0.3:
        caution += 0.3
    if snap_rate < 0.4:
        caution += 0.2

    # Primary pattern based on two axes: caution vs sophistication
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

    # =========================================================================
    # TIER 2: Narrative Archetype (for storytelling)
    # =========================================================================

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

    # Autocrat: High trust + slow (reviews everything but accepts)
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

    return {
        "primary_pattern": primary_pattern,
        "pattern_confidence": pattern_confidence,
        "primary_archetype": best[0],
        "archetype_confidence": best[1],
        "all_scores": archetype_scores,
        "key_features": {
            "bash_acceptance_rate": bash_rate,
            "overall_acceptance_rate": overall_rate,
            "mean_decision_time_ms": decision_time,
            "risk_trust_delta": risk_delta,
            "snap_judgment_rate": snap_rate,
        },
        "subtle_features": {
            "agent_spawn_rate": agent_rate,
            "tool_diversity": diversity,
            "session_depth": depth,
            "power_session_ratio": power_ratio,
            "surgical_ratio": surgical,
            "edit_intensity": edit_intensity,
            "sophistication_score": sophistication,
            "caution_score": caution,
        }
    }


# Keep old function for backwards compatibility
def classify_archetype(profile: UserGovernanceProfile) -> Dict[str, Any]:
    """Legacy classification - use classify_archetype_empirical instead."""
    return classify_archetype_empirical(profile)


# ============================================================================
# Output
# ============================================================================

def print_profile(profile: UserGovernanceProfile, parser: 'ClaudeLogParser' = None):
    """Print governance profile."""
    print("\n" + "="*70)
    print("YOUR GOVERNANCE PROFILE (from Claude Code logs)")
    print("="*70)

    print(f"\nSessions analyzed: {profile.sessions_analyzed}")
    print(f"Data collection period: {profile.data_collection_days} days")
    print(f"Total tool calls: {profile.total_tool_calls}")

    print("\n--- CONTROL (How much do you delegate?) ---")
    print(f"  Acceptance rate:    {profile.acceptance_rate:.1%}")
    print(f"  Rejection rate:     {profile.rejection_rate:.1%}")

    print("\n--- TEMPO (How fast do you decide?) ---")
    print(f"  Mean decision time: {profile.mean_decision_time_ms:.0f}ms")
    print(f"  Decision variance:  {profile.decision_time_variance:.2f}")

    print("\n--- TRUST BY TOOL ---")
    sorted_tools = sorted(
        profile.trust_by_tool.items(),
        key=lambda x: x[1].get("total", 0),
        reverse=True
    )
    for tool_name, stats in sorted_tools[:10]:
        rate = stats.get("acceptance_rate", 0)
        total = stats.get("total", 0)
        # Highlight Bash - it's THE discriminator
        marker = " <-- KEY" if tool_name == "Bash" else ""
        print(f"  {tool_name:20} {rate:.1%} ({total} calls){marker}")

    print("\n--- RISK SENSITIVITY ---")
    print(f"  High-risk acceptance: {profile.high_risk_acceptance:.1%}")
    print(f"  Low-risk acceptance:  {profile.low_risk_acceptance:.1%}")
    print(f"  Trust delta:          {profile.trust_delta_by_risk:+.1%}")

    print("\n--- CONSISTENCY ---")
    print(f"  Session consistency:  {profile.session_consistency:.2f}")

    # Archetype classification (empirically grounded)
    classification = classify_archetype_empirical(profile, parser)

    print("\n--- PRIMARY PATTERN (Empirical) ---")
    print(f"  Pattern: {classification['primary_pattern']} ({classification['pattern_confidence']:.1%})")

    print("\n  Key discriminating features:")
    features = classification['key_features']
    print(f"    Bash acceptance:     {features['bash_acceptance_rate']:.1%}")
    print(f"    Overall acceptance:  {features['overall_acceptance_rate']:.1%}")
    print(f"    Snap judgment rate:  {features['snap_judgment_rate']:.1%} (< 500ms)")
    print(f"    Risk trust delta:    {features['risk_trust_delta']:+.1%}")

    if 'subtle_features' in classification:
        print("\n  Subtle features (power user signals):")
        subtle = classification['subtle_features']
        print(f"    Agent spawn rate:    {subtle['agent_spawn_rate']:.1%}")
        print(f"    Tool diversity:      {subtle['tool_diversity']:.1f} unique/session")
        print(f"    Session depth:       {subtle['session_depth']:.0f} tools/session")
        print(f"    Power session ratio: {subtle['power_session_ratio']:.1%} (>100 tools)")
        print(f"    Surgical ratio:      {subtle['surgical_ratio']:.2f} (search/read)")
        print(f"    Edit intensity:      {subtle['edit_intensity']:.1%}")
        print(f"    ---")
        print(f"    Sophistication:      {subtle['sophistication_score']:.2f}")
        print(f"    Caution:             {subtle['caution_score']:.2f}")

    print("\n--- NARRATIVE ARCHETYPE ---")
    print(f"  Primary: {classification['primary_archetype']} ({classification['archetype_confidence']:.1%})")
    print("  All scores:")
    for archetype, score in sorted(classification['all_scores'].items(), key=lambda x: -x[1]):
        bar = "█" * int(score * 20)
        print(f"    {archetype:18} {bar} {score:.1%}")

    # Interpretation
    print("\n--- INTERPRETATION ---")
    pattern = classification['primary_pattern']
    archetype = classification['primary_archetype']

    if pattern == "Bash Truster":
        print("  You accept shell commands freely. This represents 74% of observed sessions.")
        print("  Risk: Potentially vulnerable to malicious commands.")
        print("  Consider: Review commands that modify files or run scripts.")
    elif pattern == "Bash Skeptic":
        print("  You scrutinize shell commands carefully. This represents 21% of observed sessions.")
        print("  Strength: You maintain control over system-level operations.")
        print("  Consider: You may be overly cautious for safe read operations.")
    elif pattern == "Deliberator":
        print("  You take time to review most actions. This is rare (~5% of sessions).")
        print("  Strength: Thorough review of AI suggestions.")
        print("  Risk: Slower development velocity.")
    else:
        print("  Your pattern is mixed or transitional.")
        print("  You may be developing your governance style.")

    print("\n" + "="*70)
    print("Based on empirical analysis of 62 sessions, 5939 tool calls.")
    print("Bash acceptance is THE key discriminator - all other tools ~100%.")
    print("="*70 + "\n")


def export_profile(profile: UserGovernanceProfile, parser: ClaudeLogParser):
    """Export profile, classification, and events to JSON."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Get empirical classification
    classification = classify_archetype_empirical(profile, parser)

    # Export profile with classification
    profile_file = OUTPUT_DIR / "governance_profile.json"
    export_data = {
        "profile": asdict(profile),
        "classification": classification,
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sessions_analyzed": len(parser.sessions),
            "total_events": len(parser.all_events),
        }
    }
    with open(profile_file, 'w') as f:
        json.dump(export_data, f, indent=2, default=str)
    print(f"Profile exported to: {profile_file}")

    # Export events
    events_file = OUTPUT_DIR / "tool_events.jsonl"
    with open(events_file, 'w') as f:
        for event in parser.all_events:
            f.write(json.dumps(asdict(event), default=str) + '\n')
    print(f"Events exported to: {events_file}")

    # Export per-session summaries for visualization
    sessions_file = OUTPUT_DIR / "session_summaries.json"
    session_data = []
    for session_id, analysis in parser.sessions.items():
        session_data.append({
            "session_id": session_id,
            "project": analysis.project,
            "start_time": analysis.start_time.isoformat() if analysis.start_time else None,
            "duration_minutes": analysis.duration_minutes,
            "total_tool_calls": analysis.total_tool_calls,
            "accepted": analysis.accepted,
            "rejected": analysis.rejected,
            "acceptance_rate": analysis.acceptance_rate,
            "tool_breakdown": analysis.tool_breakdown,
            "mean_decision_time_ms": analysis.mean_decision_time_ms,
        })
    with open(sessions_file, 'w') as f:
        json.dump(session_data, f, indent=2, default=str)
    print(f"Session summaries exported to: {sessions_file}")


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Parse Claude Code logs for governance analysis")
    parser.add_argument('--project', type=str, help='Filter by project name')
    parser.add_argument('--export', action='store_true', help='Export data to JSON')
    parser.add_argument('--verbose', action='store_true', help='Show per-session details')

    args = parser.parse_args()

    print("Parsing Claude Code logs...")
    log_parser = ClaudeLogParser(project_filter=args.project)
    sessions = log_parser.parse_all_sessions()

    if not sessions:
        print("No sessions with tool calls found.")
        return

    if args.verbose:
        print("\n--- Per-Session Analysis ---")
        for session_id, analysis in sorted(sessions.items(), key=lambda x: x[1].start_time or datetime.min):
            print(f"\n{session_id[:8]}... ({analysis.project})")
            print(f"  Duration: {analysis.duration_minutes:.1f} min")
            print(f"  Tool calls: {analysis.total_tool_calls} (accepted: {analysis.accepted}, rejected: {analysis.rejected})")
            print(f"  Acceptance rate: {analysis.acceptance_rate:.1%}")

    profile = log_parser.compute_governance_profile()
    print_profile(profile, log_parser)

    if args.export:
        export_profile(profile, log_parser)


if __name__ == "__main__":
    main()
