"""Data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


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

    # Timing
    request_timestamp: Optional[datetime] = None
    response_timestamp: Optional[datetime] = None
    decision_time_ms: Optional[int] = None

    # Context
    project: Optional[str] = None


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
    trust_by_tool: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # === TEMPO ===
    mean_decision_time_ms: float = 0.0
    decision_time_variance: float = 0.0

    # === PATTERNS ===
    sessions_analyzed: int = 0
    session_acceptance_rates: List[float] = field(default_factory=list)
    session_consistency: float = 0.0

    # === RISK PROXY ===
    high_risk_acceptance: float = 0.0
    low_risk_acceptance: float = 0.0
    trust_delta_by_risk: float = 0.0

    # Metadata
    first_session: Optional[str] = None
    last_session: Optional[str] = None
    data_collection_days: int = 0


@dataclass
class Classification:
    """Result of archetype classification."""
    # Empirical pattern (what the data shows)
    primary_pattern: str
    pattern_confidence: float

    # Narrative archetype (for storytelling)
    archetype: str
    archetype_confidence: float
    archetype_scores: Dict[str, float] = field(default_factory=dict)

    # Key features used
    key_features: Dict[str, float] = field(default_factory=dict)
    subtle_features: Dict[str, float] = field(default_factory=dict)


# Tool risk classification
HIGH_RISK_TOOLS = {'Bash', 'Write', 'Edit', 'NotebookEdit'}
LOW_RISK_TOOLS = {'Read', 'Glob', 'Grep', 'WebFetch', 'WebSearch'}
