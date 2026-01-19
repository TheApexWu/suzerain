"""
Suzerain: What kind of AI ruler are you?

"The suzerain rules even where there are other kings.
 There is no territory outside his claim."

Analyzes how you govern AI coding assistants and maps your
patterns to historical archetypes.
"""

__version__ = "0.4.0"
__author__ = "Amadeus Woo"

from .models import UserGovernanceProfile, SessionAnalysis, ToolEvent
from .parser import ClaudeLogParser
from .classifier import classify_user
from .analytics import (
    run_advanced_analytics,
    analyze_command_types,
    analyze_temporal_trend,
    analyze_session_arc,
    CommandBreakdown,
    TemporalTrend,
    SessionArc,
)

__all__ = [
    "UserGovernanceProfile",
    "SessionAnalysis",
    "ToolEvent",
    "ClaudeLogParser",
    "classify_user",
    "run_advanced_analytics",
    "analyze_command_types",
    "analyze_temporal_trend",
    "analyze_session_arc",
    "CommandBreakdown",
    "TemporalTrend",
    "SessionArc",
]
