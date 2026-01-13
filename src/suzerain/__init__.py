"""
Suzerain: Understand your AI governance style

Analyzes how you use AI coding assistants and maps your behavior
to historical governance patterns.
"""

__version__ = "0.2.0"
__author__ = "Amadeus Woo"

from .models import UserGovernanceProfile, SessionAnalysis, ToolEvent
from .parser import ClaudeLogParser
from .classifier import classify_user

__all__ = [
    "UserGovernanceProfile",
    "SessionAnalysis",
    "ToolEvent",
    "ClaudeLogParser",
    "classify_user",
]
