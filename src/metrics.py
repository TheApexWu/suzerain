"""
Suzerain Metrics - Local analytics and usage tracking.

Tracks per-session and aggregate metrics for command execution,
latency breakdown, and usage patterns.

"The truth about the world is that anything is possible."

Storage: ~/.suzerain/metrics.json
"""

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any


# === Storage Paths ===

SUZERAIN_DIR = Path.home() / ".suzerain"
METRICS_FILE = SUZERAIN_DIR / "metrics.json"


# === Data Classes ===

@dataclass
class CommandRecord:
    """Record of a single command execution."""
    phrase: str
    timestamp: float  # Unix timestamp
    success: bool
    match_score: int  # 0-100
    latency_stt_ms: float = 0.0
    latency_parse_ms: float = 0.0
    latency_claude_ms: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CommandRecord":
        return cls(**data)


@dataclass
class SessionMetrics:
    """Metrics for a single Suzerain session."""
    session_id: str
    start_time: float  # Unix timestamp
    end_time: Optional[float] = None
    commands_executed: int = 0
    commands_succeeded: int = 0
    commands_failed: int = 0
    total_stt_ms: float = 0.0
    total_parse_ms: float = 0.0
    total_claude_ms: float = 0.0
    match_scores: List[int] = field(default_factory=list)
    command_records: List[CommandRecord] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.commands_executed == 0:
            return 0.0
        return (self.commands_succeeded / self.commands_executed) * 100

    @property
    def avg_stt_ms(self) -> float:
        """Average STT latency."""
        if self.commands_executed == 0:
            return 0.0
        return self.total_stt_ms / self.commands_executed

    @property
    def avg_parse_ms(self) -> float:
        """Average parse latency."""
        if self.commands_executed == 0:
            return 0.0
        return self.total_parse_ms / self.commands_executed

    @property
    def avg_claude_ms(self) -> float:
        """Average Claude execution latency."""
        if self.commands_executed == 0:
            return 0.0
        return self.total_claude_ms / self.commands_executed

    @property
    def session_duration_s(self) -> float:
        """Total session duration in seconds."""
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def avg_match_score(self) -> float:
        """Average match score."""
        if not self.match_scores:
            return 0.0
        return sum(self.match_scores) / len(self.match_scores)

    def record_command(
        self,
        phrase: str,
        success: bool,
        match_score: int,
        stt_ms: float = 0.0,
        parse_ms: float = 0.0,
        claude_ms: float = 0.0
    ) -> None:
        """Record a command execution."""
        self.commands_executed += 1
        if success:
            self.commands_succeeded += 1
        else:
            self.commands_failed += 1

        self.total_stt_ms += stt_ms
        self.total_parse_ms += parse_ms
        self.total_claude_ms += claude_ms
        self.match_scores.append(match_score)

        record = CommandRecord(
            phrase=phrase,
            timestamp=time.time(),
            success=success,
            match_score=match_score,
            latency_stt_ms=stt_ms,
            latency_parse_ms=parse_ms,
            latency_claude_ms=claude_ms
        )
        self.command_records.append(record)

    def end_session(self) -> None:
        """Mark the session as ended."""
        self.end_time = time.time()

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "commands_executed": self.commands_executed,
            "commands_succeeded": self.commands_succeeded,
            "commands_failed": self.commands_failed,
            "total_stt_ms": self.total_stt_ms,
            "total_parse_ms": self.total_parse_ms,
            "total_claude_ms": self.total_claude_ms,
            "match_scores": self.match_scores,
            "command_records": [r.to_dict() for r in self.command_records]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionMetrics":
        """Deserialize from dictionary."""
        records = [CommandRecord.from_dict(r) for r in data.pop("command_records", [])]
        return cls(**data, command_records=records)


@dataclass
class LatencyHistory:
    """
    Rolling history of latency measurements for predictions.

    Stores recent measurements for each stage to calculate
    rolling averages and provide "Usually takes ~X" predictions.
    """
    # Store last N measurements for rolling average
    stt_samples: List[float] = field(default_factory=list)
    parse_samples: List[float] = field(default_factory=list)
    claude_samples: List[float] = field(default_factory=list)
    warmup_samples: List[float] = field(default_factory=list)
    max_samples: int = field(default=50)  # Keep last 50 measurements

    def add_stt(self, ms: float) -> None:
        """Record STT latency sample."""
        self.stt_samples.append(ms)
        if len(self.stt_samples) > self.max_samples:
            self.stt_samples.pop(0)

    def add_parse(self, ms: float) -> None:
        """Record parse latency sample."""
        self.parse_samples.append(ms)
        if len(self.parse_samples) > self.max_samples:
            self.parse_samples.pop(0)

    def add_claude(self, ms: float) -> None:
        """Record Claude execution latency sample."""
        self.claude_samples.append(ms)
        if len(self.claude_samples) > self.max_samples:
            self.claude_samples.pop(0)

    def add_warmup(self, ms: float) -> None:
        """Record warmup latency sample."""
        self.warmup_samples.append(ms)
        if len(self.warmup_samples) > self.max_samples:
            self.warmup_samples.pop(0)

    def _rolling_avg(self, samples: List[float]) -> Optional[float]:
        """Calculate rolling average, or None if no data."""
        if not samples:
            return None
        return sum(samples) / len(samples)

    def _percentile(self, samples: List[float], pct: float) -> Optional[float]:
        """Calculate percentile, or None if no data."""
        if not samples:
            return None
        sorted_samples = sorted(samples)
        idx = int(len(sorted_samples) * pct / 100)
        idx = min(idx, len(sorted_samples) - 1)
        return sorted_samples[idx]

    @property
    def avg_stt_ms(self) -> Optional[float]:
        return self._rolling_avg(self.stt_samples)

    @property
    def avg_parse_ms(self) -> Optional[float]:
        return self._rolling_avg(self.parse_samples)

    @property
    def avg_claude_ms(self) -> Optional[float]:
        return self._rolling_avg(self.claude_samples)

    @property
    def avg_warmup_ms(self) -> Optional[float]:
        return self._rolling_avg(self.warmup_samples)

    @property
    def p90_claude_ms(self) -> Optional[float]:
        """90th percentile Claude latency for conservative estimates."""
        return self._percentile(self.claude_samples, 90)

    def get_prediction(self) -> Dict[str, Any]:
        """
        Get latency prediction based on historical data.

        Returns dict with:
        - estimated_total_ms: Expected total latency
        - breakdown: Per-stage estimates
        - confidence: 'high' if 10+ samples, 'low' otherwise
        """
        stt = self.avg_stt_ms or 400  # Default estimates
        parse = self.avg_parse_ms or 10
        claude = self.avg_claude_ms or 5000  # Default 5s for Claude

        total = stt + parse + claude

        return {
            "estimated_total_ms": total,
            "breakdown": {
                "stt_ms": stt,
                "parse_ms": parse,
                "claude_ms": claude
            },
            "confidence": "high" if len(self.claude_samples) >= 10 else "low",
            "sample_count": len(self.claude_samples)
        }

    def format_prediction(self) -> str:
        """Format prediction as human-readable string."""
        pred = self.get_prediction()
        total_s = pred["estimated_total_ms"] / 1000

        if pred["confidence"] == "high":
            return f"Usually ~{total_s:.1f}s"
        elif pred["sample_count"] > 0:
            return f"~{total_s:.1f}s (estimated)"
        else:
            return ""

    def to_dict(self) -> dict:
        return {
            "stt_samples": self.stt_samples,
            "parse_samples": self.parse_samples,
            "claude_samples": self.claude_samples,
            "warmup_samples": self.warmup_samples,
            "max_samples": self.max_samples
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LatencyHistory":
        return cls(
            stt_samples=data.get("stt_samples", []),
            parse_samples=data.get("parse_samples", []),
            claude_samples=data.get("claude_samples", []),
            warmup_samples=data.get("warmup_samples", []),
            max_samples=data.get("max_samples", 50)
        )


@dataclass
class AggregateMetrics:
    """Aggregate metrics across all sessions."""
    total_commands: int = 0
    total_succeeded: int = 0
    total_failed: int = 0
    total_stt_ms: float = 0.0
    total_parse_ms: float = 0.0
    total_claude_ms: float = 0.0
    total_sessions: int = 0
    command_frequency: Dict[str, int] = field(default_factory=dict)
    hourly_usage: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    daily_usage: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    match_score_distribution: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    first_command_time: Optional[float] = None
    last_command_time: Optional[float] = None
    # Rolling latency history for predictions
    latency_history: LatencyHistory = field(default_factory=LatencyHistory)

    @property
    def success_rate(self) -> float:
        """Overall success rate as percentage."""
        if self.total_commands == 0:
            return 0.0
        return (self.total_succeeded / self.total_commands) * 100

    @property
    def avg_stt_ms(self) -> float:
        """Average STT latency across all commands."""
        if self.total_commands == 0:
            return 0.0
        return self.total_stt_ms / self.total_commands

    @property
    def avg_parse_ms(self) -> float:
        """Average parse latency across all commands."""
        if self.total_commands == 0:
            return 0.0
        return self.total_parse_ms / self.total_commands

    @property
    def avg_claude_ms(self) -> float:
        """Average Claude latency across all commands."""
        if self.total_commands == 0:
            return 0.0
        return self.total_claude_ms / self.total_commands

    def get_top_commands(self, n: int = 5) -> List[tuple]:
        """Get the N most frequently used commands."""
        sorted_cmds = sorted(
            self.command_frequency.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_cmds[:n]

    def get_peak_hours(self, n: int = 3) -> List[tuple]:
        """Get the N peak usage hours."""
        sorted_hours = sorted(
            self.hourly_usage.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_hours[:n]

    def get_last_n_days_usage(self, n: int = 7) -> List[tuple]:
        """Get usage counts for the last N days."""
        today = datetime.now().date()
        result = []
        for i in range(n - 1, -1, -1):
            day = today - timedelta(days=i)
            day_str = day.isoformat()
            count = self.daily_usage.get(day_str, 0)
            result.append((day_str, count))
        return result

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "total_commands": self.total_commands,
            "total_succeeded": self.total_succeeded,
            "total_failed": self.total_failed,
            "total_stt_ms": self.total_stt_ms,
            "total_parse_ms": self.total_parse_ms,
            "total_claude_ms": self.total_claude_ms,
            "total_sessions": self.total_sessions,
            "command_frequency": dict(self.command_frequency),
            "hourly_usage": {str(k): v for k, v in self.hourly_usage.items()},
            "daily_usage": dict(self.daily_usage),
            "match_score_distribution": dict(self.match_score_distribution),
            "first_command_time": self.first_command_time,
            "last_command_time": self.last_command_time,
            "latency_history": self.latency_history.to_dict()
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AggregateMetrics":
        """Deserialize from dictionary."""
        latency_data = data.get("latency_history", {})
        latency_history = LatencyHistory.from_dict(latency_data) if latency_data else LatencyHistory()

        metrics = cls(
            total_commands=data.get("total_commands", 0),
            total_succeeded=data.get("total_succeeded", 0),
            total_failed=data.get("total_failed", 0),
            total_stt_ms=data.get("total_stt_ms", 0.0),
            total_parse_ms=data.get("total_parse_ms", 0.0),
            total_claude_ms=data.get("total_claude_ms", 0.0),
            total_sessions=data.get("total_sessions", 0),
            first_command_time=data.get("first_command_time"),
            last_command_time=data.get("last_command_time"),
            latency_history=latency_history
        )
        metrics.command_frequency = data.get("command_frequency", {})
        metrics.hourly_usage = defaultdict(int, {int(k): v for k, v in data.get("hourly_usage", {}).items()})
        metrics.daily_usage = defaultdict(int, data.get("daily_usage", {}))
        metrics.match_score_distribution = defaultdict(int, data.get("match_score_distribution", {}))
        return metrics


# === Metrics Manager ===

class MetricsManager:
    """
    Manages metrics collection, persistence, and reporting.

    Stores aggregate metrics in ~/.suzerain/metrics.json.
    Session metrics are held in memory and merged on session end.
    """

    def __init__(self, metrics_file: Path = None):
        """
        Initialize metrics manager.

        Args:
            metrics_file: Override metrics file path (for testing)
        """
        self.metrics_file = metrics_file or METRICS_FILE
        self._aggregate = self._load_aggregate()
        self._current_session: Optional[SessionMetrics] = None

    def _ensure_dir(self) -> None:
        """Create ~/.suzerain directory if it doesn't exist."""
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_aggregate(self) -> AggregateMetrics:
        """Load aggregate metrics from disk."""
        if not self.metrics_file.exists():
            return AggregateMetrics()

        try:
            with open(self.metrics_file, 'r') as f:
                data = json.load(f)
            return AggregateMetrics.from_dict(data.get("aggregate", {}))
        except (json.JSONDecodeError, IOError, KeyError):
            return AggregateMetrics()

    def _save_aggregate(self) -> None:
        """Persist aggregate metrics to disk."""
        self._ensure_dir()
        data = {"aggregate": self._aggregate.to_dict()}
        with open(self.metrics_file, 'w') as f:
            json.dump(data, f, indent=2)

    def start_session(self) -> SessionMetrics:
        """
        Start a new metrics session.

        Returns:
            The new SessionMetrics instance
        """
        session_id = f"session_{int(time.time() * 1000)}"
        self._current_session = SessionMetrics(
            session_id=session_id,
            start_time=time.time()
        )
        return self._current_session

    def get_current_session(self) -> Optional[SessionMetrics]:
        """Get the current session metrics."""
        return self._current_session

    def record_command(
        self,
        phrase: str,
        success: bool,
        match_score: int,
        stt_ms: float = 0.0,
        parse_ms: float = 0.0,
        claude_ms: float = 0.0
    ) -> None:
        """
        Record a command execution.

        Args:
            phrase: The grimoire phrase that matched
            success: Whether the command succeeded
            match_score: Fuzzy match score (0-100)
            stt_ms: Speech-to-text latency in milliseconds
            parse_ms: Parser latency in milliseconds
            claude_ms: Claude execution latency in milliseconds
        """
        # Record to session if active
        if self._current_session:
            self._current_session.record_command(
                phrase=phrase,
                success=success,
                match_score=match_score,
                stt_ms=stt_ms,
                parse_ms=parse_ms,
                claude_ms=claude_ms
            )

        # Update aggregate metrics
        self._aggregate.total_commands += 1
        if success:
            self._aggregate.total_succeeded += 1
        else:
            self._aggregate.total_failed += 1

        self._aggregate.total_stt_ms += stt_ms
        self._aggregate.total_parse_ms += parse_ms
        self._aggregate.total_claude_ms += claude_ms

        # Update rolling latency history for predictions
        if stt_ms > 0:
            self._aggregate.latency_history.add_stt(stt_ms)
        if parse_ms > 0:
            self._aggregate.latency_history.add_parse(parse_ms)
        if claude_ms > 0:
            self._aggregate.latency_history.add_claude(claude_ms)

        # Update command frequency
        if phrase not in self._aggregate.command_frequency:
            self._aggregate.command_frequency[phrase] = 0
        self._aggregate.command_frequency[phrase] += 1

        # Update hourly usage
        now = datetime.now()
        hour = now.hour
        self._aggregate.hourly_usage[hour] += 1

        # Update daily usage
        day_str = now.date().isoformat()
        self._aggregate.daily_usage[day_str] += 1

        # Update match score distribution (buckets: <70, 70-79, 80-89, 90-100)
        if match_score < 70:
            bucket = "<70"
        elif match_score < 80:
            bucket = "70-79"
        elif match_score < 90:
            bucket = "80-89"
        else:
            bucket = "90-100"
        self._aggregate.match_score_distribution[bucket] += 1

        # Update timestamps
        timestamp = time.time()
        if self._aggregate.first_command_time is None:
            self._aggregate.first_command_time = timestamp
        self._aggregate.last_command_time = timestamp

        # Persist changes
        self._save_aggregate()

    def record_warmup(self, warmup_ms: float) -> None:
        """Record warmup latency for predictions."""
        if warmup_ms > 0:
            self._aggregate.latency_history.add_warmup(warmup_ms)
            self._save_aggregate()

    def get_prediction(self) -> Dict[str, Any]:
        """Get latency prediction based on historical data."""
        return self._aggregate.latency_history.get_prediction()

    def get_prediction_string(self) -> str:
        """Get formatted prediction string for display."""
        return self._aggregate.latency_history.format_prediction()

    def end_session(self) -> Optional[SessionMetrics]:
        """
        End the current session and merge metrics.

        Returns:
            The ended SessionMetrics or None if no session was active
        """
        if self._current_session is None:
            return None

        self._current_session.end_session()
        self._aggregate.total_sessions += 1
        self._save_aggregate()

        session = self._current_session
        self._current_session = None
        return session

    @property
    def aggregate(self) -> AggregateMetrics:
        """Get aggregate metrics."""
        return self._aggregate

    def reset_aggregate(self) -> None:
        """Reset all aggregate metrics (for testing)."""
        self._aggregate = AggregateMetrics()
        self._save_aggregate()


# === Global Instance ===

_manager: Optional[MetricsManager] = None


def get_metrics_manager() -> MetricsManager:
    """Get the global metrics manager instance."""
    global _manager
    if _manager is None:
        _manager = MetricsManager()
    return _manager


def reset_metrics_manager() -> None:
    """Reset the global metrics manager (for testing)."""
    global _manager
    _manager = None


# === Display Functions ===

def format_latency(ms: float) -> str:
    """Format latency for display."""
    if ms < 1000:
        return f"{ms:.0f}ms"
    else:
        return f"{ms / 1000:.1f}s"


def generate_sparkline(values: List[int], width: int = 7) -> str:
    """
    Generate a simple sparkline from values.

    Args:
        values: List of numeric values
        width: Number of characters in the sparkline

    Returns:
        Unicode sparkline string
    """
    if not values:
        return " " * width

    # Sparkline characters (8 levels)
    chars = " " + "".join(chr(0x2581 + i) for i in range(7))  # space + lower 7 blocks

    max_val = max(values) if max(values) > 0 else 1
    result = []

    for val in values[-width:]:
        # Normalize to 0-7 range
        level = int((val / max_val) * 7) if max_val > 0 else 0
        level = min(7, max(0, level))
        result.append(chars[level])

    # Pad if needed
    while len(result) < width:
        result.insert(0, " ")

    return "".join(result)


def display_stats(manager: MetricsManager = None) -> str:
    """
    Generate the stats display string.

    Args:
        manager: MetricsManager to use (defaults to global)

    Returns:
        Formatted stats string for terminal output
    """
    if manager is None:
        manager = get_metrics_manager()

    agg = manager.aggregate

    lines = []
    lines.append("SUZERAIN STATS")
    lines.append("=" * 36)

    # Basic stats
    lines.append(f"Total commands:     {agg.total_commands}")
    lines.append(f"Success rate:       {agg.success_rate:.1f}%")
    lines.append("")

    # Latency breakdown
    lines.append("Avg latency:")
    lines.append(f"  STT:              {format_latency(agg.avg_stt_ms)}")
    lines.append(f"  Parse:            {format_latency(agg.avg_parse_ms)}")
    lines.append(f"  Claude:           {format_latency(agg.avg_claude_ms)}")
    lines.append("")

    # Top commands
    top_commands = agg.get_top_commands(5)
    if top_commands:
        lines.append("Top commands:")
        for phrase, count in top_commands:
            # Truncate long phrases
            display_phrase = phrase[:25] + "..." if len(phrase) > 28 else phrase
            lines.append(f'  "{display_phrase}"'.ljust(32) + f"{count} uses")
    lines.append("")

    # Last 7 days sparkline
    last_7 = agg.get_last_n_days_usage(7)
    counts = [count for _, count in last_7]
    total_7_days = sum(counts)
    sparkline = generate_sparkline(counts, 7)
    lines.append(f"Last 7 days: {sparkline} ({total_7_days} commands)")

    return "\n".join(lines)


def print_stats(manager: MetricsManager = None) -> None:
    """Print stats to stdout."""
    print(display_stats(manager))


# === Telemetry Stub ===

# TELEMETRY (Opt-in, default OFF)
#
# Future implementation for anonymized usage stats:
# - If user opts in via ~/.suzerain/config.yaml (telemetry_enabled: true)
# - Send anonymized aggregate stats to telemetry endpoint
# - Data includes: command counts, latency averages, error rates
# - Does NOT include: phrases, transcripts, user identifiers
#
# To implement:
# 1. Add telemetry_enabled config option (default: false)
# 2. Create telemetry endpoint
# 3. Batch and send stats periodically (daily?)
# 4. Provide clear opt-out mechanism
#
# For now, this is intentionally NOT IMPLEMENTED.
# All metrics stay local in ~/.suzerain/metrics.json


# === CLI Entry Point ===

if __name__ == "__main__":
    print_stats()
