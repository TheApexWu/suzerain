"""
Claude Code log parser.

Parses ~/.claude/projects/{project}/{session}.jsonl files
and extracts tool acceptance/rejection events.
"""

import json
import statistics
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional

from .models import (
    ToolEvent,
    SessionAnalysis,
    UserGovernanceProfile,
    HIGH_RISK_TOOLS,
    LOW_RISK_TOOLS,
)


# Default paths
CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"


class ClaudeLogParser:
    """Parses Claude Code logs to extract governance events."""

    def __init__(self, project_filter: Optional[str] = None):
        self.project_filter = project_filter
        self.sessions: Dict[str, SessionAnalysis] = {}
        self.all_events: List[ToolEvent] = []

    def find_session_files(self) -> List[Path]:
        """Find all session .jsonl files."""
        if not PROJECTS_DIR.exists():
            return []

        session_files = []
        for project_dir in PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue

            if self.project_filter:
                if self.project_filter.lower() not in project_dir.name.lower():
                    continue

            for f in project_dir.glob("*.jsonl"):
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

        pending_tools: Dict[str, Dict] = {}

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

            if timestamp:
                if analysis.start_time is None or timestamp < analysis.start_time:
                    analysis.start_time = timestamp
                if analysis.end_time is None or timestamp > analysis.end_time:
                    analysis.end_time = timestamp

            if event_type == 'assistant':
                message = event.get('message', {})
                content = message.get('content', [])

                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'tool_use':
                        tool_id = item.get('id')
                        tool_name = item.get('name', 'unknown')
                        tool_input = item.get('input', {})

                        pending_tools[tool_id] = {
                            'timestamp': timestamp,
                            'tool_name': tool_name,
                            'input': tool_input,
                        }

            elif event_type == 'user':
                message = event.get('message', {})
                content = message.get('content', [])

                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'tool_result':
                            tool_id = item.get('tool_use_id')
                            is_error = item.get('is_error', False)
                            result_content = item.get('content', '')

                            pending = pending_tools.pop(tool_id, None)
                            if not pending:
                                continue

                            tool_name = pending['tool_name']
                            if tool_name.startswith('mcp__'):
                                tool_name = tool_name.split('__')[-1]

                            rejected = False
                            accepted = False

                            if is_error:
                                if 'requires approval' in str(result_content).lower():
                                    rejected = True
                                else:
                                    analysis.errors += 1
                                    analysis.tool_breakdown[tool_name]["errors"] += 1
                            else:
                                accepted = True

                            if accepted or rejected:
                                analysis.total_tool_calls += 1

                                if accepted:
                                    analysis.accepted += 1
                                    analysis.tool_breakdown[tool_name]["accepted"] += 1
                                elif rejected:
                                    analysis.rejected += 1
                                    analysis.tool_breakdown[tool_name]["rejected"] += 1

                                decision_time_ms = None
                                if pending['timestamp'] and timestamp:
                                    delta = timestamp - pending['timestamp']
                                    decision_time_ms = int(delta.total_seconds() * 1000)
                                    if 0 < decision_time_ms < 300000:
                                        analysis.decision_times_ms.append(decision_time_ms)

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
                                )
                                self.all_events.append(tool_event)

        if analysis.total_tool_calls > 0:
            analysis.acceptance_rate = analysis.accepted / analysis.total_tool_calls
            analysis.rejection_rate = analysis.rejected / analysis.total_tool_calls

        if analysis.decision_times_ms:
            analysis.mean_decision_time_ms = statistics.mean(analysis.decision_times_ms)

        if analysis.start_time and analysis.end_time:
            analysis.duration_minutes = (analysis.end_time - analysis.start_time).total_seconds() / 60

        analysis.tool_breakdown = dict(analysis.tool_breakdown)
        return analysis

    def parse_all_sessions(self) -> Dict[str, SessionAnalysis]:
        """Parse all session files."""
        session_files = self.find_session_files()

        for f in session_files:
            try:
                analysis = self.parse_session(f)
                if analysis.total_tool_calls > 0:
                    self.sessions[analysis.session_id] = analysis
            except Exception:
                pass

        return self.sessions

    def compute_governance_profile(self) -> UserGovernanceProfile:
        """Compute aggregate governance profile from all sessions."""
        profile = UserGovernanceProfile()

        if not self.sessions:
            return profile

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

        if profile.total_tool_calls > 0:
            profile.acceptance_rate = profile.total_accepted / profile.total_tool_calls
            profile.rejection_rate = profile.total_rejected / profile.total_tool_calls

        for tool_name, stats in tool_stats.items():
            if stats["total"] > 0:
                stats["acceptance_rate"] = stats["accepted"] / stats["total"]
            profile.trust_by_tool[tool_name] = dict(stats)

        if all_decision_times:
            profile.mean_decision_time_ms = statistics.mean(all_decision_times)
            if len(all_decision_times) > 1:
                profile.decision_time_variance = statistics.stdev(all_decision_times) / profile.mean_decision_time_ms

        if len(profile.session_acceptance_rates) > 1:
            mean_rate = statistics.mean(profile.session_acceptance_rates)
            std_rate = statistics.stdev(profile.session_acceptance_rates)
            if mean_rate > 0:
                profile.session_consistency = 1 - (std_rate / mean_rate)

        high_risk_accepted = sum(tool_stats[t]["accepted"] for t in HIGH_RISK_TOOLS if t in tool_stats)
        high_risk_total = sum(tool_stats[t]["total"] for t in HIGH_RISK_TOOLS if t in tool_stats)
        low_risk_accepted = sum(tool_stats[t]["accepted"] for t in LOW_RISK_TOOLS if t in tool_stats)
        low_risk_total = sum(tool_stats[t]["total"] for t in LOW_RISK_TOOLS if t in tool_stats)

        if high_risk_total > 0:
            profile.high_risk_acceptance = high_risk_accepted / high_risk_total
        if low_risk_total > 0:
            profile.low_risk_acceptance = low_risk_accepted / low_risk_total

        profile.trust_delta_by_risk = profile.low_risk_acceptance - profile.high_risk_acceptance
        profile.sessions_analyzed = len(self.sessions)

        timestamps = [s.start_time for s in self.sessions.values() if s.start_time]
        if timestamps:
            profile.first_session = min(timestamps).isoformat()
            profile.last_session = max(timestamps).isoformat()
            profile.data_collection_days = (max(timestamps) - min(timestamps)).days + 1

        return profile
