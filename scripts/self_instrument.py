#!/usr/bin/env python3
"""
Suzerain Self-Instrumentation Script

Captures your AI governance behavior for analysis.
Run this alongside your Claude Code sessions.

Usage:
    python scripts/self_instrument.py --start    # Begin logging session
    python scripts/self_instrument.py --stop     # End session, compute features
    python scripts/self_instrument.py --analyze  # Analyze all collected data
    python scripts/self_instrument.py --log      # Log a single event manually

Data stored in: ~/.suzerain/telemetry/
"""

import json
import time
import argparse
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Optional, Literal
from enum import Enum
import statistics


# ============================================================================
# Configuration
# ============================================================================

TELEMETRY_DIR = Path.home() / ".suzerain" / "telemetry"
SESSIONS_DIR = TELEMETRY_DIR / "sessions"
EVENTS_FILE = TELEMETRY_DIR / "events.jsonl"
FEATURES_FILE = TELEMETRY_DIR / "features.json"


# ============================================================================
# Data Models
# ============================================================================

class EventType(str, Enum):
    """Types of governance events we track."""
    SUGGESTION_SHOWN = "suggestion_shown"      # AI presented an option
    ACCEPTED = "accepted"                       # User accepted suggestion
    REJECTED = "rejected"                       # User explicitly rejected
    IGNORED = "ignored"                         # User continued without acting
    EDITED = "edited"                           # User modified after accepting
    UNDONE = "undone"                           # User reversed a decision
    AUTO_EXECUTED = "auto_executed"             # AI acted without confirmation
    SESSION_START = "session_start"
    SESSION_END = "session_end"


class TaskContext(str, Enum):
    """What type of task is being performed."""
    TEST = "test"
    DEPLOY = "deploy"
    REFACTOR = "refactor"
    DOCS = "docs"
    DEBUG = "debug"
    FEATURE = "feature"
    SECURITY = "security"
    CONFIG = "config"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    """Risk level of the action."""
    LOW = "low"           # Read-only, reversible
    MEDIUM = "medium"     # Writes to dev, reversible
    HIGH = "high"         # Production, external, irreversible


@dataclass
class GovernanceEvent:
    """A single governance decision event."""
    timestamp: str
    event_type: str
    session_id: str

    # Timing
    decision_time_ms: Optional[int] = None       # Time from suggestion to action

    # Context
    task_context: str = TaskContext.UNKNOWN.value
    risk_level: str = RiskLevel.MEDIUM.value

    # For edits
    edit_distance: Optional[int] = None          # Levenshtein distance if edited

    # For streaks
    previous_event_type: Optional[str] = None

    # Metadata (no PII, no code content)
    suggestion_length: Optional[int] = None      # Characters, not content
    file_type: Optional[str] = None              # .py, .ts, etc.
    hour_of_day: Optional[int] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class SessionSummary:
    """Aggregate stats for a single session."""
    session_id: str
    start_time: str
    end_time: str
    duration_minutes: float

    # Counts
    total_suggestions: int = 0
    accepted: int = 0
    rejected: int = 0
    ignored: int = 0
    edited: int = 0
    undone: int = 0
    auto_executed: int = 0

    # Computed
    acceptance_rate: float = 0.0
    rejection_rate: float = 0.0
    edit_after_accept_rate: float = 0.0
    undo_rate: float = 0.0
    auto_execute_ratio: float = 0.0
    mean_decision_time_ms: float = 0.0
    decision_time_variance: float = 0.0


@dataclass
class UserFeatures:
    """The full feature vector for governance analysis."""

    # === CONTROL DIMENSION ===
    acceptance_rate: float = 0.0                 # % suggestions accepted
    explicit_rejection_rate: float = 0.0         # % explicitly rejected
    auto_execute_ratio: float = 0.0              # % actions without confirmation

    # === TEMPO DIMENSION ===
    mean_decision_time_ms: float = 0.0           # Average time to decide
    decision_time_variance: float = 0.0          # Consistency of timing
    time_to_first_action_ms: float = 0.0         # Review before acting

    # === TRUST DIMENSION ===
    trust_by_context: dict = field(default_factory=dict)  # Acceptance by task type
    trust_delta_by_risk: float = 0.0             # Low risk - high risk acceptance

    # === CORRECTION DIMENSION ===
    edit_after_accept_rate: float = 0.0          # % of accepts that get edited
    undo_rate: float = 0.0                       # % of accepts that get undone
    mean_edit_distance: float = 0.0              # How much editing occurs

    # === CONSISTENCY DIMENSION ===
    session_consistency: float = 0.0             # Variance across sessions
    streak_score: float = 0.0                    # Tendency to rubber-stamp
    time_of_day_variance: float = 0.0            # Hour-by-hour variance

    # Metadata
    total_events: int = 0
    total_sessions: int = 0
    data_collection_days: int = 0


# ============================================================================
# Event Logging
# ============================================================================

class GovernanceLogger:
    """Logs governance events to disk."""

    def __init__(self):
        TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self.current_session_id: Optional[str] = None
        self.session_start_time: Optional[datetime] = None
        self.last_suggestion_time: Optional[datetime] = None
        self.last_event_type: Optional[str] = None

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        timestamp = datetime.now(timezone.utc).isoformat()
        return hashlib.sha256(timestamp.encode()).hexdigest()[:12]

    def start_session(self) -> str:
        """Start a new logging session."""
        self.current_session_id = self._generate_session_id()
        self.session_start_time = datetime.now(timezone.utc)

        event = GovernanceEvent(
            timestamp=self.session_start_time.isoformat(),
            event_type=EventType.SESSION_START.value,
            session_id=self.current_session_id,
            hour_of_day=self.session_start_time.hour,
        )
        self._write_event(event)

        print(f"Session started: {self.current_session_id}")
        print(f"Logging to: {EVENTS_FILE}")
        return self.current_session_id

    def end_session(self):
        """End the current session."""
        if not self.current_session_id:
            print("No active session.")
            return

        end_time = datetime.now(timezone.utc)
        event = GovernanceEvent(
            timestamp=end_time.isoformat(),
            event_type=EventType.SESSION_END.value,
            session_id=self.current_session_id,
            hour_of_day=end_time.hour,
        )
        self._write_event(event)

        # Compute session summary
        summary = self._compute_session_summary()
        summary_file = SESSIONS_DIR / f"{self.current_session_id}.json"
        with open(summary_file, 'w') as f:
            json.dump(asdict(summary), f, indent=2)

        print(f"Session ended: {self.current_session_id}")
        print(f"Summary saved: {summary_file}")
        self._print_session_summary(summary)

        self.current_session_id = None
        self.session_start_time = None

    def log_event(
        self,
        event_type: EventType,
        task_context: TaskContext = TaskContext.UNKNOWN,
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        edit_distance: Optional[int] = None,
        suggestion_length: Optional[int] = None,
        file_type: Optional[str] = None,
    ):
        """Log a governance event."""
        now = datetime.now(timezone.utc)

        # Calculate decision time if we're responding to a suggestion
        decision_time_ms = None
        if self.last_suggestion_time and event_type in [
            EventType.ACCEPTED, EventType.REJECTED, EventType.IGNORED
        ]:
            delta = now - self.last_suggestion_time
            decision_time_ms = int(delta.total_seconds() * 1000)

        event = GovernanceEvent(
            timestamp=now.isoformat(),
            event_type=event_type.value,
            session_id=self.current_session_id or "no_session",
            decision_time_ms=decision_time_ms,
            task_context=task_context.value,
            risk_level=risk_level.value,
            edit_distance=edit_distance,
            previous_event_type=self.last_event_type,
            suggestion_length=suggestion_length,
            file_type=file_type,
            hour_of_day=now.hour,
        )
        self._write_event(event)

        # Update state
        if event_type == EventType.SUGGESTION_SHOWN:
            self.last_suggestion_time = now
        self.last_event_type = event_type.value

        print(f"Logged: {event_type.value} ({task_context.value}, {risk_level.value})")

    def _write_event(self, event: GovernanceEvent):
        """Append event to JSONL file."""
        with open(EVENTS_FILE, 'a') as f:
            f.write(json.dumps(event.to_dict()) + '\n')

    def _compute_session_summary(self) -> SessionSummary:
        """Compute summary stats for current session."""
        events = self._load_session_events(self.current_session_id)

        end_time = datetime.now(timezone.utc)
        duration = (end_time - self.session_start_time).total_seconds() / 60

        # Count events
        counts = {et.value: 0 for et in EventType}
        decision_times = []

        for event in events:
            counts[event['event_type']] = counts.get(event['event_type'], 0) + 1
            if event.get('decision_time_ms'):
                decision_times.append(event['decision_time_ms'])

        total_suggestions = counts[EventType.SUGGESTION_SHOWN.value]
        total_decisions = counts[EventType.ACCEPTED.value] + counts[EventType.REJECTED.value]

        return SessionSummary(
            session_id=self.current_session_id,
            start_time=self.session_start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_minutes=round(duration, 2),
            total_suggestions=total_suggestions,
            accepted=counts[EventType.ACCEPTED.value],
            rejected=counts[EventType.REJECTED.value],
            ignored=counts[EventType.IGNORED.value],
            edited=counts[EventType.EDITED.value],
            undone=counts[EventType.UNDONE.value],
            auto_executed=counts[EventType.AUTO_EXECUTED.value],
            acceptance_rate=round(counts[EventType.ACCEPTED.value] / max(total_suggestions, 1), 3),
            rejection_rate=round(counts[EventType.REJECTED.value] / max(total_suggestions, 1), 3),
            edit_after_accept_rate=round(counts[EventType.EDITED.value] / max(counts[EventType.ACCEPTED.value], 1), 3),
            undo_rate=round(counts[EventType.UNDONE.value] / max(counts[EventType.ACCEPTED.value], 1), 3),
            auto_execute_ratio=round(counts[EventType.AUTO_EXECUTED.value] / max(total_decisions + counts[EventType.AUTO_EXECUTED.value], 1), 3),
            mean_decision_time_ms=round(statistics.mean(decision_times), 2) if decision_times else 0,
            decision_time_variance=round(statistics.stdev(decision_times), 2) if len(decision_times) > 1 else 0,
        )

    def _load_session_events(self, session_id: str) -> list:
        """Load events for a specific session."""
        events = []
        if EVENTS_FILE.exists():
            with open(EVENTS_FILE, 'r') as f:
                for line in f:
                    event = json.loads(line.strip())
                    if event.get('session_id') == session_id:
                        events.append(event)
        return events

    def _print_session_summary(self, summary: SessionSummary):
        """Print summary to console."""
        print("\n" + "="*50)
        print("SESSION SUMMARY")
        print("="*50)
        print(f"Duration: {summary.duration_minutes:.1f} minutes")
        print(f"Total suggestions: {summary.total_suggestions}")
        print(f"Accepted: {summary.accepted} ({summary.acceptance_rate:.1%})")
        print(f"Rejected: {summary.rejected} ({summary.rejection_rate:.1%})")
        print(f"Edited after accept: {summary.edited} ({summary.edit_after_accept_rate:.1%})")
        print(f"Undone: {summary.undone} ({summary.undo_rate:.1%})")
        print(f"Mean decision time: {summary.mean_decision_time_ms:.0f}ms")
        print("="*50 + "\n")


# ============================================================================
# Feature Computation
# ============================================================================

class FeatureComputer:
    """Computes governance features from collected events."""

    def __init__(self):
        self.events = self._load_all_events()
        self.sessions = self._load_all_sessions()

    def _load_all_events(self) -> list:
        """Load all events from disk."""
        events = []
        if EVENTS_FILE.exists():
            with open(EVENTS_FILE, 'r') as f:
                for line in f:
                    events.append(json.loads(line.strip()))
        return events

    def _load_all_sessions(self) -> list:
        """Load all session summaries."""
        sessions = []
        if SESSIONS_DIR.exists():
            for f in SESSIONS_DIR.glob("*.json"):
                with open(f, 'r') as file:
                    sessions.append(json.load(file))
        return sessions

    def compute_features(self) -> UserFeatures:
        """Compute all governance features."""
        if not self.events:
            print("No events found. Start collecting data first.")
            return UserFeatures()

        features = UserFeatures()

        # Filter to decision events
        decisions = [e for e in self.events if e['event_type'] in [
            EventType.ACCEPTED.value, EventType.REJECTED.value,
            EventType.IGNORED.value, EventType.AUTO_EXECUTED.value
        ]]

        if not decisions:
            return features

        # === CONTROL DIMENSION ===
        accepts = [e for e in decisions if e['event_type'] == EventType.ACCEPTED.value]
        rejects = [e for e in decisions if e['event_type'] == EventType.REJECTED.value]
        auto = [e for e in decisions if e['event_type'] == EventType.AUTO_EXECUTED.value]

        features.acceptance_rate = len(accepts) / len(decisions)
        features.explicit_rejection_rate = len(rejects) / len(decisions)
        features.auto_execute_ratio = len(auto) / len(decisions)

        # === TEMPO DIMENSION ===
        decision_times = [e['decision_time_ms'] for e in decisions if e.get('decision_time_ms')]
        if decision_times:
            features.mean_decision_time_ms = statistics.mean(decision_times)
            if len(decision_times) > 1:
                features.decision_time_variance = statistics.stdev(decision_times) / features.mean_decision_time_ms

        # === TRUST DIMENSION ===
        context_accepts = {}
        context_totals = {}
        for e in decisions:
            ctx = e.get('task_context', 'unknown')
            context_totals[ctx] = context_totals.get(ctx, 0) + 1
            if e['event_type'] == EventType.ACCEPTED.value:
                context_accepts[ctx] = context_accepts.get(ctx, 0) + 1

        features.trust_by_context = {
            ctx: context_accepts.get(ctx, 0) / total
            for ctx, total in context_totals.items()
        }

        # Trust delta by risk
        low_risk = [e for e in decisions if e.get('risk_level') == RiskLevel.LOW.value]
        high_risk = [e for e in decisions if e.get('risk_level') == RiskLevel.HIGH.value]
        low_accept = len([e for e in low_risk if e['event_type'] == EventType.ACCEPTED.value]) / max(len(low_risk), 1)
        high_accept = len([e for e in high_risk if e['event_type'] == EventType.ACCEPTED.value]) / max(len(high_risk), 1)
        features.trust_delta_by_risk = low_accept - high_accept

        # === CORRECTION DIMENSION ===
        edits = [e for e in self.events if e['event_type'] == EventType.EDITED.value]
        undos = [e for e in self.events if e['event_type'] == EventType.UNDONE.value]

        features.edit_after_accept_rate = len(edits) / max(len(accepts), 1)
        features.undo_rate = len(undos) / max(len(accepts), 1)

        edit_distances = [e['edit_distance'] for e in edits if e.get('edit_distance')]
        if edit_distances:
            features.mean_edit_distance = statistics.mean(edit_distances)

        # === CONSISTENCY DIMENSION ===
        if self.sessions:
            session_rates = [s['acceptance_rate'] for s in self.sessions if s.get('acceptance_rate')]
            if len(session_rates) > 1:
                features.session_consistency = 1 - (statistics.stdev(session_rates) / max(statistics.mean(session_rates), 0.01))

        # Streak score
        streaks = self._compute_streak_score(decisions)
        features.streak_score = streaks

        # Time of day variance
        hour_accepts = {}
        hour_totals = {}
        for e in decisions:
            hour = e.get('hour_of_day', 12)
            hour_totals[hour] = hour_totals.get(hour, 0) + 1
            if e['event_type'] == EventType.ACCEPTED.value:
                hour_accepts[hour] = hour_accepts.get(hour, 0) + 1

        hour_rates = [hour_accepts.get(h, 0) / t for h, t in hour_totals.items()]
        if len(hour_rates) > 1:
            features.time_of_day_variance = statistics.stdev(hour_rates)

        # Metadata
        features.total_events = len(self.events)
        features.total_sessions = len(self.sessions)

        if self.events:
            timestamps = [datetime.fromisoformat(e['timestamp'].replace('Z', '+00:00')) for e in self.events]
            if len(timestamps) > 1:
                features.data_collection_days = (max(timestamps) - min(timestamps)).days + 1

        return features

    def _compute_streak_score(self, decisions: list) -> float:
        """Compute tendency to make consecutive same decisions."""
        if len(decisions) < 2:
            return 0.0

        streaks = []
        current_streak = 1

        for i in range(1, len(decisions)):
            if decisions[i]['event_type'] == decisions[i-1]['event_type']:
                current_streak += 1
            else:
                streaks.append(current_streak)
                current_streak = 1
        streaks.append(current_streak)

        # Compare to expected if random (geometric distribution)
        mean_streak = statistics.mean(streaks)
        expected_random = 2.0  # Approximate expected streak length for 50/50

        return mean_streak / expected_random

    def save_features(self, features: UserFeatures):
        """Save computed features to disk."""
        with open(FEATURES_FILE, 'w') as f:
            json.dump(asdict(features), f, indent=2)
        print(f"Features saved to: {FEATURES_FILE}")

    def print_features(self, features: UserFeatures):
        """Print features in readable format."""
        print("\n" + "="*60)
        print("YOUR GOVERNANCE PROFILE")
        print("="*60)

        print("\n--- CONTROL (How much do you delegate?) ---")
        print(f"  Acceptance rate:      {features.acceptance_rate:.1%}")
        print(f"  Rejection rate:       {features.explicit_rejection_rate:.1%}")
        print(f"  Auto-execute ratio:   {features.auto_execute_ratio:.1%}")

        print("\n--- TEMPO (How fast do you decide?) ---")
        print(f"  Mean decision time:   {features.mean_decision_time_ms:.0f}ms")
        print(f"  Decision variance:    {features.decision_time_variance:.2f}")

        print("\n--- TRUST (Is it context-dependent?) ---")
        for ctx, rate in features.trust_by_context.items():
            print(f"  Trust for {ctx:12}: {rate:.1%}")
        print(f"  Risk sensitivity:     {features.trust_delta_by_risk:+.1%} (low - high risk)")

        print("\n--- CORRECTION (How do you handle errors?) ---")
        print(f"  Edit after accept:    {features.edit_after_accept_rate:.1%}")
        print(f"  Undo rate:            {features.undo_rate:.1%}")
        print(f"  Mean edit distance:   {features.mean_edit_distance:.0f} chars")

        print("\n--- CONSISTENCY (Are you predictable?) ---")
        print(f"  Session consistency:  {features.session_consistency:.2f}")
        print(f"  Streak score:         {features.streak_score:.2f}x expected")
        print(f"  Time-of-day variance: {features.time_of_day_variance:.3f}")

        print("\n--- METADATA ---")
        print(f"  Total events:         {features.total_events}")
        print(f"  Total sessions:       {features.total_sessions}")
        print(f"  Days of data:         {features.data_collection_days}")

        print("\n" + "="*60)

        # Quick archetype guess
        self._guess_archetype(features)

    def _guess_archetype(self, f: UserFeatures):
        """Preliminary archetype guess (before proper clustering)."""
        print("\n--- PRELIMINARY ARCHETYPE GUESS ---")

        if f.acceptance_rate > 0.85 and f.mean_decision_time_ms < 1000:
            print("Pattern: HIGH accept + FAST decisions")
            print("Possible: Rubber Stamper / Mongol Horde (high delegation, speed)")
        elif f.acceptance_rate > 0.85 and f.mean_decision_time_ms > 2000:
            print("Pattern: HIGH accept + SLOW decisions")
            print("Possible: Bottleneck / Roman Emperor (review everything)")
        elif f.acceptance_rate < 0.5 and f.edit_after_accept_rate > 0.4:
            print("Pattern: LOW accept + HIGH edit")
            print("Possible: Skeptic / Editor (AI as rough draft)")
        elif features.trust_delta_by_risk > 0.3:
            print("Pattern: HIGH trust variance by risk")
            print("Possible: Venetian / Constitutional (context-dependent rules)")
        else:
            print("Pattern: Mixed signals")
            print("Need more data for classification")

        print("\nNOTE: This is a heuristic guess. Proper clustering requires more data.")
        print("="*60 + "\n")


# ============================================================================
# Interactive Logger (for manual logging during sessions)
# ============================================================================

def interactive_log():
    """Interactive mode for logging events during a session."""
    logger = GovernanceLogger()

    print("\n" + "="*50)
    print("SUZERAIN INTERACTIVE LOGGER")
    print("="*50)
    print("\nCommands:")
    print("  s  - AI showed a suggestion")
    print("  a  - You accepted")
    print("  r  - You rejected")
    print("  i  - You ignored")
    print("  e  - You edited after accepting")
    print("  u  - You undid an action")
    print("  x  - AI auto-executed (no confirmation)")
    print("  q  - Quit and save session")
    print("\nContext modifiers (add after command):")
    print("  t=test, d=deploy, r=refactor, f=feature, s=security")
    print("  Example: 'a t' = accepted a test-related suggestion")
    print("\nRisk modifiers:")
    print("  l=low, m=medium, h=high")
    print("  Example: 'a d h' = accepted high-risk deploy")
    print("="*50 + "\n")

    session_id = logger.start_session()

    context_map = {
        't': TaskContext.TEST,
        'd': TaskContext.DEPLOY,
        'r': TaskContext.REFACTOR,
        'f': TaskContext.FEATURE,
        's': TaskContext.SECURITY,
        'c': TaskContext.CONFIG,
        'b': TaskContext.DEBUG,
        'o': TaskContext.DOCS,
    }

    risk_map = {
        'l': RiskLevel.LOW,
        'm': RiskLevel.MEDIUM,
        'h': RiskLevel.HIGH,
    }

    event_map = {
        's': EventType.SUGGESTION_SHOWN,
        'a': EventType.ACCEPTED,
        'r': EventType.REJECTED,
        'i': EventType.IGNORED,
        'e': EventType.EDITED,
        'u': EventType.UNDONE,
        'x': EventType.AUTO_EXECUTED,
    }

    while True:
        try:
            cmd = input("> ").strip().lower()

            if cmd == 'q':
                break

            parts = cmd.split()
            if not parts or parts[0] not in event_map:
                print("Unknown command. Try: s, a, r, i, e, u, x, q")
                continue

            event_type = event_map[parts[0]]
            context = TaskContext.UNKNOWN
            risk = RiskLevel.MEDIUM

            for part in parts[1:]:
                if part in context_map:
                    context = context_map[part]
                elif part in risk_map:
                    risk = risk_map[part]

            logger.log_event(event_type, context, risk)

        except KeyboardInterrupt:
            break
        except EOFError:
            break

    logger.end_session()


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Suzerain Self-Instrumentation")
    parser.add_argument('--start', action='store_true', help='Start a new logging session')
    parser.add_argument('--stop', action='store_true', help='End current session')
    parser.add_argument('--analyze', action='store_true', help='Analyze all collected data')
    parser.add_argument('--interactive', action='store_true', help='Interactive logging mode')
    parser.add_argument('--status', action='store_true', help='Show data collection status')

    args = parser.parse_args()

    if args.interactive:
        interactive_log()
    elif args.analyze:
        computer = FeatureComputer()
        features = computer.compute_features()
        computer.print_features(features)
        computer.save_features(features)
    elif args.status:
        if EVENTS_FILE.exists():
            with open(EVENTS_FILE, 'r') as f:
                count = sum(1 for _ in f)
            print(f"Events collected: {count}")
            print(f"Sessions: {len(list(SESSIONS_DIR.glob('*.json'))) if SESSIONS_DIR.exists() else 0}")
            print(f"Data location: {TELEMETRY_DIR}")
        else:
            print("No data collected yet. Run with --interactive to start.")
    else:
        parser.print_help()
        print("\nQuick start:")
        print("  python scripts/self_instrument.py --interactive")


if __name__ == "__main__":
    main()
