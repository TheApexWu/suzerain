"""Advanced analytics: command breakdown, temporal trends, session arcs, trust variance."""

import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

from .models import ToolEvent


DESTRUCTIVE_PATTERNS = [
    r'\brm\b', r'\brmdir\b', r'>\s*/',
    r'\bgit\s+push\s+.*--force', r'\bgit\s+push\s+-f\b',
    r'\bgit\s+reset\s+--hard', r'\bgit\s+clean\s+-fd',
    r'\bdrop\s+table\b', r'\bdrop\s+database\b', r'\btruncate\b',
    r'\bdd\s+', r'\bmkfs\b', r'\bkill\s+-9', r'\bpkill\b',
    r'\bshutdown\b', r'\breboot\b', r'\bsudo\s+rm\b',
    r'\bchmod\s+777\b', r'\bchown\b.*-R',
]

STATE_CHANGING_PATTERNS = [
    r'\bgit\s+commit\b', r'\bgit\s+push\b', r'\bgit\s+merge\b',
    r'\bgit\s+rebase\b', r'\bgit\s+checkout\b', r'\bgit\s+branch\s+-[dD]\b',
    r'\bgit\s+stash\b', r'\bnpm\s+install\b', r'\bnpm\s+uninstall\b',
    r'\bpip\s+install\b', r'\bpip\s+uninstall\b',
    r'\byarn\s+add\b', r'\byarn\s+remove\b',
    r'\bmkdir\b', r'\btouch\b', r'\bmv\b', r'\bcp\b',
    r'\bcurl\s+.*-X\s*(POST|PUT|DELETE|PATCH)', r'\bwget\b',
    r'\bdocker\s+(run|stop|rm|build)', r'\bkubectl\s+(apply|delete|create)',
    r'\bsed\s+-i\b', r'\bawk\s+.*-i\b', r'>>', r'\becho\s+.*>',
]

READ_ONLY_PATTERNS = [
    r'\bls\b', r'\bll\b', r'\bla\b', r'\bcat\b', r'\bhead\b', r'\btail\b',
    r'\bless\b', r'\bmore\b', r'\bgrep\b', r'\brg\b', r'\bfind\b', r'\bfd\b',
    r'\bwc\b', r'\bdu\b', r'\bdf\b', r'\bpwd\b', r'\bwhoami\b',
    r'\bwhich\b', r'\bwhere\b', r'\btype\b', r'\bfile\b', r'\bstat\b',
    r'\bgit\s+status\b', r'\bgit\s+log\b', r'\bgit\s+diff\b', r'\bgit\s+show\b',
    r'\bgit\s+branch\b(?!\s+-[dD])', r'\bgit\s+remote\s+-v',
    r'\bnpm\s+list\b', r'\bnpm\s+ls\b', r'\bpip\s+list\b', r'\bpip\s+show\b',
    r'\bpython\s+--version', r'\bnode\s+--version',
    r'\benv\b', r'\bprintenv\b', r'\becho\s+\$',
    r'\bcurl\s+.*-I\b', r'\bcurl\s+(?!.*-X)',
]


def classify_command(command: str) -> str:
    """Classify bash command: destructive, state_changing, read_only, or unknown."""
    if not command:
        return 'unknown'
    cmd = command.lower()
    for p in DESTRUCTIVE_PATTERNS:
        if re.search(p, cmd):
            return 'destructive'
    for p in STATE_CHANGING_PATTERNS:
        if re.search(p, cmd):
            return 'state_changing'
    for p in READ_ONLY_PATTERNS:
        if re.search(p, cmd):
            return 'read_only'
    return 'unknown'


@dataclass
class CommandBreakdown:
    destructive: Dict[str, int] = field(default_factory=lambda: {'accepted': 0, 'rejected': 0})
    state_changing: Dict[str, int] = field(default_factory=lambda: {'accepted': 0, 'rejected': 0})
    read_only: Dict[str, int] = field(default_factory=lambda: {'accepted': 0, 'rejected': 0})
    unknown: Dict[str, int] = field(default_factory=lambda: {'accepted': 0, 'rejected': 0})
    examples: Dict[str, List[str]] = field(default_factory=lambda: {
        'destructive': [], 'state_changing': [], 'read_only': [], 'unknown': []
    })

    def acceptance_rate(self, category: str) -> Optional[float]:
        cat = getattr(self, category, None)
        if not cat:
            return None
        total = cat['accepted'] + cat['rejected']
        return cat['accepted'] / total if total else None

    def total(self, category: str) -> int:
        cat = getattr(self, category, None)
        return (cat['accepted'] + cat['rejected']) if cat else 0


def analyze_command_types(events: List[ToolEvent]) -> CommandBreakdown:
    breakdown = CommandBreakdown()
    for event in events:
        if event.tool_name != 'Bash' or not event.command:
            continue
        category = classify_command(event.command)
        cat_dict = getattr(breakdown, category)
        if event.accepted:
            cat_dict['accepted'] += 1
        elif event.rejected:
            cat_dict['rejected'] += 1
        if len(breakdown.examples[category]) < 3:
            preview = event.command[:60] + '...' if len(event.command) > 60 else event.command
            breakdown.examples[category].append(preview)
    return breakdown


@dataclass
class TemporalTrend:
    weekly_rates: List[Tuple[str, float, int]] = field(default_factory=list)
    trend_direction: str = 'stable'
    trend_magnitude: float = 0.0
    earliest_rate: Optional[float] = None
    latest_rate: Optional[float] = None
    data_span_days: int = 0


def analyze_temporal_trend(events: List[ToolEvent], min_per_period: int = 5) -> TemporalTrend:
    trend = TemporalTrend()
    bash_events = [e for e in events if e.tool_name == 'Bash' and e.timestamp]
    if not bash_events:
        return trend

    bash_events.sort(key=lambda e: e.timestamp)
    first_ts, last_ts = bash_events[0].timestamp, bash_events[-1].timestamp
    trend.data_span_days = (last_ts - first_ts).days + 1

    if trend.data_span_days < 7:
        accepted = sum(1 for e in bash_events if e.accepted)
        total = len(bash_events)
        if total:
            rate = accepted / total
            trend.weekly_rates = [(first_ts.strftime('%Y-%m-%d'), rate, total)]
            trend.earliest_rate = trend.latest_rate = rate
        return trend

    weekly = defaultdict(list)
    for e in bash_events:
        week_start = e.timestamp - timedelta(days=e.timestamp.weekday())
        weekly[week_start.strftime('%Y-%m-%d')].append(e)

    weekly_data = []
    for week_key in sorted(weekly.keys()):
        week_events = weekly[week_key]
        if len(week_events) < min_per_period:
            continue
        accepted = sum(1 for e in week_events if e.accepted)
        rate = accepted / len(week_events)
        weekly_data.append((week_key, rate, len(week_events)))

    trend.weekly_rates = weekly_data
    if len(weekly_data) >= 2:
        trend.earliest_rate, trend.latest_rate = weekly_data[0][1], weekly_data[-1][1]
        trend.trend_magnitude = trend.latest_rate - trend.earliest_rate
        if trend.trend_magnitude > 0.1:
            trend.trend_direction = 'increasing'
        elif trend.trend_magnitude < -0.1:
            trend.trend_direction = 'decreasing'
    elif weekly_data:
        trend.earliest_rate = trend.latest_rate = weekly_data[0][1]

    return trend


@dataclass
class SessionArc:
    first_n_rate: Optional[float] = None
    last_n_rate: Optional[float] = None
    n_commands: int = 10
    arc_type: str = 'flat'
    arc_magnitude: float = 0.0
    session_arcs: List[Tuple[str, float, float]] = field(default_factory=list)
    sessions_analyzed: int = 0


def analyze_session_arc(events: List[ToolEvent], n: int = 10, min_sessions: int = 3) -> SessionArc:
    arc = SessionArc(n_commands=n)
    sessions = defaultdict(list)
    for e in events:
        if e.tool_name == 'Bash':
            sessions[e.session_id].append(e)

    for sid in sessions:
        sessions[sid].sort(key=lambda e: e.timestamp if e.timestamp else datetime.min)

    first_rates, last_rates = [], []
    for sid, evts in sessions.items():
        if len(evts) < n * 2:
            continue
        first_n, last_n = evts[:n], evts[-n:]
        fr = sum(1 for e in first_n if e.accepted) / n
        lr = sum(1 for e in last_n if e.accepted) / n
        first_rates.append(fr)
        last_rates.append(lr)
        arc.session_arcs.append((sid, fr, lr))

    arc.sessions_analyzed = len(first_rates)
    if arc.sessions_analyzed < min_sessions:
        return arc

    arc.first_n_rate = sum(first_rates) / len(first_rates)
    arc.last_n_rate = sum(last_rates) / len(last_rates)
    arc.arc_magnitude = arc.last_n_rate - arc.first_n_rate
    if arc.arc_magnitude > 0.1:
        arc.arc_type = 'warmup'
    elif arc.arc_magnitude < -0.1:
        arc.arc_type = 'cooldown'
    return arc


@dataclass
class TrustVariance:
    overall_bash_rate: float = 0.0
    total_bash_commands: int = 0
    project_rates: Dict[str, Tuple[float, int]] = field(default_factory=dict)
    project_variance: float = 0.0
    project_range: float = 0.0
    session_rates: List[float] = field(default_factory=list)
    session_variance: float = 0.0
    variance_score: float = 0.0
    variance_type: str = 'uniform'


def analyze_trust_variance(events: List[ToolEvent], min_commands: int = 10) -> TrustVariance:
    v = TrustVariance()
    bash = [e for e in events if e.tool_name == 'Bash']
    if not bash:
        return v

    v.total_bash_commands = len(bash)
    v.overall_bash_rate = sum(1 for e in bash if e.accepted) / len(bash)

    # by project
    projects = defaultdict(lambda: {'accepted': 0, 'total': 0})
    for e in bash:
        proj = e.project or 'unknown'
        projects[proj]['total'] += 1
        if e.accepted:
            projects[proj]['accepted'] += 1

    proj_rates = []
    for proj, d in projects.items():
        if d['total'] >= min_commands:
            rate = d['accepted'] / d['total']
            v.project_rates[proj] = (rate, d['total'])
            proj_rates.append(rate)

    if len(proj_rates) >= 2:
        v.project_variance = statistics.stdev(proj_rates)
        v.project_range = max(proj_rates) - min(proj_rates)

    # by session
    sessions = defaultdict(lambda: {'accepted': 0, 'total': 0})
    for e in bash:
        sessions[e.session_id]['total'] += 1
        if e.accepted:
            sessions[e.session_id]['accepted'] += 1

    sess_rates = []
    for d in sessions.values():
        if d['total'] >= 5:
            sess_rates.append(d['accepted'] / d['total'])
    v.session_rates = sess_rates

    if len(sess_rates) >= 3:
        v.session_variance = statistics.stdev(sess_rates)

    # composite score: project variance weighted higher
    proj_score = min(1.0, v.project_range / 0.5) if v.project_range else 0
    sess_score = min(1.0, v.session_variance / 0.3) if v.session_variance else 0
    v.variance_score = 0.7 * proj_score + 0.3 * sess_score

    if v.variance_score < 0.2:
        v.variance_type = 'uniform'
    elif v.variance_score < 0.5:
        v.variance_type = 'moderate'
    else:
        v.variance_type = 'context_dependent'

    return v


@dataclass
class AdvancedAnalytics:
    command_breakdown: CommandBreakdown = field(default_factory=CommandBreakdown)
    temporal_trend: TemporalTrend = field(default_factory=TemporalTrend)
    session_arc: SessionArc = field(default_factory=SessionArc)
    trust_variance: TrustVariance = field(default_factory=TrustVariance)


def run_advanced_analytics(events: List[ToolEvent]) -> AdvancedAnalytics:
    return AdvancedAnalytics(
        command_breakdown=analyze_command_types(events),
        temporal_trend=analyze_temporal_trend(events),
        session_arc=analyze_session_arc(events),
        trust_variance=analyze_trust_variance(events),
    )
