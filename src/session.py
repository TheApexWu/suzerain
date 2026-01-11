"""
v0.6 Session Memory - Multi-turn conversation context.

Tracks:
- Current session commands
- Files modified during session
- Conversation context for follow-up commands ("undo that", "what did you do")
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Set


@dataclass
class CommandContext:
    """Context from a single command execution."""
    timestamp: str
    phrase: str
    agent_type: str  # tester, implementer, deployer, etc.
    files_read: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    summary: str = ""
    success: bool = True
    claude_output_preview: str = ""  # First 500 chars of Claude output

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommandContext":
        return cls(**data)


@dataclass
class SessionContext:
    """Context for the current session."""
    session_id: str
    start_time: str
    commands: List[CommandContext] = field(default_factory=list)
    conversation_ids: List[str] = field(default_factory=list)  # Claude conversation IDs

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "commands": [c.to_dict() for c in self.commands],
            "conversation_ids": self.conversation_ids,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionContext":
        commands = [CommandContext.from_dict(c) for c in data.get("commands", [])]
        return cls(
            session_id=data["session_id"],
            start_time=data["start_time"],
            commands=commands,
            conversation_ids=data.get("conversation_ids", []),
        )

    def add_command(self, ctx: CommandContext) -> None:
        """Add a command to the session."""
        self.commands.append(ctx)

    def get_last_command(self) -> Optional[CommandContext]:
        """Get the most recent command."""
        return self.commands[-1] if self.commands else None

    def get_last_n_commands(self, n: int = 5) -> List[CommandContext]:
        """Get the last N commands."""
        return self.commands[-n:] if self.commands else []

    def get_all_modified_files(self) -> Set[str]:
        """Get all files modified during this session."""
        files = set()
        for cmd in self.commands:
            files.update(cmd.files_modified)
        return files

    def get_recent_files(self, n: int = 10) -> List[str]:
        """Get most recently modified files."""
        all_files = []
        for cmd in reversed(self.commands):
            for f in cmd.files_modified:
                if f not in all_files:
                    all_files.append(f)
                if len(all_files) >= n:
                    break
            if len(all_files) >= n:
                break
        return all_files

    def format_for_prompt(self) -> str:
        """Format session context for injection into Claude prompt."""
        if not self.commands:
            return ""

        lines = ["## Recent Session Context"]
        for i, cmd in enumerate(self.commands[-5:], 1):  # Last 5 commands
            lines.append(f"\n### Command {i}: {cmd.phrase}")
            lines.append(f"Agent: {cmd.agent_type}")
            if cmd.summary:
                lines.append(f"Summary: {cmd.summary}")
            if cmd.files_modified:
                lines.append(f"Modified: {', '.join(cmd.files_modified[:5])}")
            if cmd.success:
                lines.append("Status: Success")
            else:
                lines.append("Status: Failed")

        return "\n".join(lines)


class SessionManager:
    """Manages session and conversation context."""

    _instance: Optional["SessionManager"] = None

    def __init__(self, session_dir: Optional[Path] = None):
        self.session_dir = session_dir or (Path.home() / ".suzerain")
        self.session_file = self.session_dir / "session_context.json"
        self._ensure_dir()

        # Try to resume recent session or create new
        self._session = self._load_session() or self._create_new_session()

    @classmethod
    def get_instance(cls, session_dir: Optional[Path] = None) -> "SessionManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls(session_dir)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    def _ensure_dir(self) -> None:
        """Ensure session directory exists."""
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def _create_new_session(self) -> SessionContext:
        """Create a new session."""
        import uuid
        return SessionContext(
            session_id=str(uuid.uuid4())[:8],
            start_time=datetime.now().isoformat(),
        )

    @property
    def session(self) -> SessionContext:
        """Get current session."""
        return self._session

    def log_command(
        self,
        phrase: str,
        agent_type: str = "general",
        files_read: Optional[List[str]] = None,
        files_modified: Optional[List[str]] = None,
        summary: str = "",
        success: bool = True,
        claude_output: str = "",
        conversation_id: Optional[str] = None,
    ) -> CommandContext:
        """
        Log a command execution to the session context.

        Args:
            phrase: The command phrase
            agent_type: The agent that handled this command
            files_read: Files that were read
            files_modified: Files that were modified
            summary: Claude's summary of what was done
            success: Whether the command succeeded
            claude_output: Claude's full output (will be truncated)
            conversation_id: Claude conversation ID for --continue

        Returns:
            The created CommandContext
        """
        ctx = CommandContext(
            timestamp=datetime.now().isoformat(),
            phrase=phrase,
            agent_type=agent_type,
            files_read=files_read or [],
            files_modified=files_modified or [],
            summary=summary,
            success=success,
            claude_output_preview=claude_output[:500] if claude_output else "",
        )

        self._session.add_command(ctx)

        if conversation_id:
            self._session.conversation_ids.append(conversation_id)

        # Auto-save
        self._save_session()

        return ctx

    def _save_session(self) -> None:
        """Save current session to disk."""
        try:
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(self._session.to_dict(), f, indent=2)
        except OSError:
            pass  # Silent fail on save errors

    def _load_session(self) -> Optional[SessionContext]:
        """Load session from disk if it exists and is recent."""
        if not self.session_file.exists():
            return None

        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            session = SessionContext.from_dict(data)

            # Check if session is recent (< 1 hour)
            start = datetime.fromisoformat(session.start_time)
            if (datetime.now() - start).total_seconds() < 3600:
                return session

        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            pass

        return None

    def get_context_for_prompt(self) -> str:
        """Get formatted context for injection into Claude prompt."""
        return self._session.format_for_prompt()

    def get_last_command_summary(self) -> str:
        """Get summary of the last command for 'what did you just do' type queries."""
        last = self._session.get_last_command()
        if not last:
            return "No commands have been executed in this session yet."

        lines = [f"Last command: \"{last.phrase}\""]
        if last.summary:
            lines.append(f"What happened: {last.summary}")
        if last.files_modified:
            lines.append(f"Files modified: {', '.join(last.files_modified)}")
        lines.append(f"Status: {'Success' if last.success else 'Failed'}")

        return "\n".join(lines)

    def get_undo_context(self) -> str:
        """Get context for 'undo that' type commands."""
        last = self._session.get_last_command()
        if not last:
            return "Nothing to undo - no commands executed yet."

        lines = ["To undo the last command:"]
        lines.append(f"Command was: \"{last.phrase}\"")

        if last.files_modified:
            lines.append(f"Files that were modified: {', '.join(last.files_modified)}")
            lines.append("Consider using git to revert changes, or manually reviewing modified files.")

        return "\n".join(lines)

    def new_session(self) -> SessionContext:
        """Start a fresh session."""
        self._session = self._create_new_session()
        self._save_session()
        return self._session

    def command_count(self) -> int:
        """Get number of commands in session."""
        return len(self._session.commands)


# Convenience functions

def get_session() -> SessionManager:
    """Get the session manager instance."""
    return SessionManager.get_instance()


def log_command(
    phrase: str,
    agent_type: str = "general",
    files_read: Optional[List[str]] = None,
    files_modified: Optional[List[str]] = None,
    summary: str = "",
    success: bool = True,
    claude_output: str = "",
    conversation_id: Optional[str] = None,
) -> CommandContext:
    """Log a command to the session context."""
    return get_session().log_command(
        phrase=phrase,
        agent_type=agent_type,
        files_read=files_read,
        files_modified=files_modified,
        summary=summary,
        success=success,
        claude_output=claude_output,
        conversation_id=conversation_id,
    )


def get_session_context() -> str:
    """Get formatted context for Claude prompt."""
    return get_session().get_context_for_prompt()


def get_last_summary() -> str:
    """Get summary of last command."""
    return get_session().get_last_command_summary()


def get_undo_info() -> str:
    """Get undo information."""
    return get_session().get_undo_context()
