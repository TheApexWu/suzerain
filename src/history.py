"""
Suzerain command history module.

Logs every command invocation to ~/.suzerain/history.jsonl for analysis
and replay. Provides query functions for retrieving past commands.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional


# Default configuration
DEFAULT_HISTORY_DIR = Path.home() / ".suzerain"
DEFAULT_HISTORY_FILE = "history.jsonl"


# Maximum history entries to keep
MAX_HISTORY_ENTRIES = 100


@dataclass
class HistoryEntry:
    """
    A single command history entry.

    Attributes:
        timestamp: ISO format timestamp of invocation
        phrase_spoken: The raw phrase that was spoken/typed
        phrase_matched: The grimoire phrase that was matched (if any)
        score: Fuzzy match score (0-100)
        modifiers: List of modifier effects applied
        execution_time_ms: How long the command took to execute
        success: Whether the command succeeded
        error: Error message if command failed
        conversation_id: Claude conversation ID (for --continue support)
    """
    timestamp: str
    phrase_spoken: str
    phrase_matched: Optional[str]
    score: Optional[float]
    modifiers: List[str]
    execution_time_ms: float
    success: bool
    error: Optional[str] = None
    conversation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryEntry":
        """Create from dictionary."""
        return cls(**data)


class CommandHistory:
    """
    Command history manager.

    Logs commands to JSONL file and provides query functions.
    """

    _instance: Optional["CommandHistory"] = None

    def __init__(self, history_dir: Optional[Path] = None):
        """
        Initialize command history.

        Args:
            history_dir: Directory for history file (default: ~/.suzerain)
        """
        self.history_dir = history_dir or DEFAULT_HISTORY_DIR
        self.history_file = self.history_dir / DEFAULT_HISTORY_FILE
        self._ensure_dir()

    @classmethod
    def get_instance(cls, history_dir: Optional[Path] = None) -> "CommandHistory":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls(history_dir)
        return cls._instance

    def _ensure_dir(self) -> None:
        """Ensure history directory exists."""
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def log_command(
        self,
        phrase_spoken: str,
        phrase_matched: Optional[str] = None,
        score: Optional[float] = None,
        modifiers: Optional[List[str]] = None,
        execution_time_ms: float = 0.0,
        success: bool = True,
        error: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> HistoryEntry:
        """
        Log a command invocation.

        Args:
            phrase_spoken: The raw input phrase
            phrase_matched: The matched grimoire phrase
            score: Match score
            modifiers: List of modifier effects
            execution_time_ms: Execution time in milliseconds
            success: Whether command succeeded
            error: Error message if failed
            conversation_id: Claude conversation ID from stream output

        Returns:
            The created HistoryEntry
        """
        entry = HistoryEntry(
            timestamp=datetime.now().isoformat(),
            phrase_spoken=phrase_spoken,
            phrase_matched=phrase_matched,
            score=score,
            modifiers=modifiers or [],
            execution_time_ms=execution_time_ms,
            success=success,
            error=error,
            conversation_id=conversation_id
        )

        # Append to JSONL file
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

        # Rotate if needed
        self._rotate_if_needed()

        return entry

    def _rotate_if_needed(self) -> None:
        """Rotate history file if it exceeds MAX_HISTORY_ENTRIES."""
        entries = self._read_all()
        if len(entries) > MAX_HISTORY_ENTRIES:
            # Keep only the most recent entries
            entries_to_keep = entries[-MAX_HISTORY_ENTRIES:]
            # Rewrite file
            with open(self.history_file, "w", encoding="utf-8") as f:
                for entry in entries_to_keep:
                    f.write(json.dumps(entry.to_dict()) + "\n")

    def _read_all(self) -> List[HistoryEntry]:
        """Read all history entries from file."""
        if not self.history_file.exists():
            return []

        entries = []
        with open(self.history_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        entries.append(HistoryEntry.from_dict(data))
                    except (json.JSONDecodeError, TypeError):
                        # Skip malformed entries
                        continue

        return entries

    def get_last_n(self, n: int = 10) -> List[HistoryEntry]:
        """
        Get the last N commands.

        Args:
            n: Number of commands to retrieve

        Returns:
            List of HistoryEntry, most recent first
        """
        entries = self._read_all()
        return list(reversed(entries[-n:]))

    def get_by_date(self, target_date: date) -> List[HistoryEntry]:
        """
        Get all commands from a specific date.

        Args:
            target_date: The date to filter by

        Returns:
            List of HistoryEntry from that date
        """
        entries = self._read_all()
        result = []

        for entry in entries:
            try:
                entry_date = datetime.fromisoformat(entry.timestamp).date()
                if entry_date == target_date:
                    result.append(entry)
            except ValueError:
                continue

        return result

    def get_failures(self) -> List[HistoryEntry]:
        """
        Get all failed commands.

        Returns:
            List of HistoryEntry where success=False
        """
        entries = self._read_all()
        return [e for e in entries if not e.success]

    def get_last_successful(self) -> Optional[HistoryEntry]:
        """
        Get the most recent successful command.

        Returns:
            The last successful HistoryEntry or None if none exist.
        """
        entries = self._read_all()
        for entry in reversed(entries):
            if entry.success and entry.phrase_matched:
                return entry
        return None

    def get_time_since_last(self) -> Optional[str]:
        """
        Get human-readable time since last command.

        Returns:
            String like "2 min ago" or "1 hour ago" or None if no history.
        """
        last = self.get_last_successful()
        if not last:
            return None

        try:
            last_time = datetime.fromisoformat(last.timestamp)
            now = datetime.now()
            delta = now - last_time

            seconds = delta.total_seconds()
            if seconds < 60:
                return "just now"
            elif seconds < 3600:
                minutes = int(seconds // 60)
                return f"{minutes} min ago"
            elif seconds < 86400:
                hours = int(seconds // 3600)
                return f"{hours} hour{'s' if hours > 1 else ''} ago"
            else:
                days = int(seconds // 86400)
                return f"{days} day{'s' if days > 1 else ''} ago"
        except ValueError:
            return None

    def get_by_phrase(self, phrase: str) -> List[HistoryEntry]:
        """
        Get commands matching a specific grimoire phrase.

        Args:
            phrase: The grimoire phrase to search for

        Returns:
            List of matching HistoryEntry
        """
        entries = self._read_all()
        phrase_lower = phrase.lower()
        return [
            e for e in entries
            if e.phrase_matched and phrase_lower in e.phrase_matched.lower()
        ]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics.

        Returns:
            Dictionary with stats about command history
        """
        entries = self._read_all()

        if not entries:
            return {
                "total_commands": 0,
                "success_rate": 0.0,
                "avg_execution_time_ms": 0.0,
                "most_used_commands": [],
                "total_failures": 0
            }

        successes = sum(1 for e in entries if e.success)
        total = len(entries)
        exec_times = [e.execution_time_ms for e in entries if e.execution_time_ms > 0]

        # Count command usage
        command_counts: Dict[str, int] = {}
        for e in entries:
            if e.phrase_matched:
                command_counts[e.phrase_matched] = command_counts.get(e.phrase_matched, 0) + 1

        most_used = sorted(command_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total_commands": total,
            "success_rate": (successes / total * 100) if total > 0 else 0.0,
            "avg_execution_time_ms": sum(exec_times) / len(exec_times) if exec_times else 0.0,
            "most_used_commands": most_used,
            "total_failures": total - successes
        }

    def clear(self) -> None:
        """Clear all history (use with caution)."""
        if self.history_file.exists():
            self.history_file.unlink()


# Convenience functions for module-level access

def get_history(history_dir: Optional[Path] = None) -> CommandHistory:
    """Get the command history instance."""
    return CommandHistory.get_instance(history_dir)


def log_command(
    phrase_spoken: str,
    phrase_matched: Optional[str] = None,
    score: Optional[float] = None,
    modifiers: Optional[List[str]] = None,
    execution_time_ms: float = 0.0,
    success: bool = True,
    error: Optional[str] = None,
    conversation_id: Optional[str] = None
) -> HistoryEntry:
    """
    Log a command invocation.

    Convenience function that uses the singleton instance.
    """
    return get_history().log_command(
        phrase_spoken=phrase_spoken,
        phrase_matched=phrase_matched,
        score=score,
        modifiers=modifiers,
        execution_time_ms=execution_time_ms,
        success=success,
        error=error,
        conversation_id=conversation_id
    )


def get_last_n(n: int = 10) -> List[HistoryEntry]:
    """Get the last N commands."""
    return get_history().get_last_n(n)


def get_by_date(target_date: date) -> List[HistoryEntry]:
    """Get all commands from a specific date."""
    return get_history().get_by_date(target_date)


def get_failures() -> List[HistoryEntry]:
    """Get all failed commands."""
    return get_history().get_failures()


def get_last_successful() -> Optional[HistoryEntry]:
    """Get the most recent successful command."""
    return get_history().get_last_successful()


def get_time_since_last() -> Optional[str]:
    """Get human-readable time since last command."""
    return get_history().get_time_since_last()


def format_history_entry(entry: HistoryEntry, show_details: bool = False) -> str:
    """
    Format a history entry for display.

    Args:
        entry: The history entry to format
        show_details: Show full details including modifiers and timing

    Returns:
        Formatted string
    """
    # Parse timestamp for display
    try:
        dt = datetime.fromisoformat(entry.timestamp)
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        time_str = entry.timestamp

    # Status indicator
    status = "[OK]" if entry.success else "[FAIL]"

    # Basic line
    matched = entry.phrase_matched or "(no match)"
    line = f"{time_str}  {status:6}  \"{matched}\""

    if entry.score is not None:
        line += f"  (score: {entry.score:.0f})"

    if show_details:
        lines = [line]
        lines.append(f"    Spoken: \"{entry.phrase_spoken}\"")
        if entry.modifiers:
            lines.append(f"    Modifiers: {entry.modifiers}")
        if entry.execution_time_ms > 0:
            lines.append(f"    Execution: {entry.execution_time_ms:.0f}ms")
        if entry.error:
            lines.append(f"    Error: {entry.error}")
        return "\n".join(lines)

    return line


def display_history(entries: List[HistoryEntry], title: str = "Command History") -> None:
    """
    Display history entries to terminal with formatting.

    Args:
        entries: List of history entries
        title: Title to display
    """
    print(f"\n{'=' * 60}")
    print(f"{title}")
    print(f"{'=' * 60}")

    if not entries:
        print("\n  (no history found)")
    else:
        for entry in entries:
            print(f"\n{format_history_entry(entry, show_details=True)}")

    print(f"\n{'=' * 60}\n")
