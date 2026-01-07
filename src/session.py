"""
Session Management - Track Claude Code conversation IDs across terminal sessions.

"They rode on." - Now actually continues the right conversation.

This module handles:
- Tracking Claude Code session/conversation IDs
- Persisting session state to ~/.suzerain/session.json
- Supporting multiple named sessions (e.g., "suzerain", "work", "personal")
- Auto-expiring old sessions after 24h
"""

import json
import re
import time
from pathlib import Path
from typing import Optional, List


# Default session storage location
SUZERAIN_DIR = Path.home() / ".suzerain"
SESSION_FILE = SUZERAIN_DIR / "session.json"

# Session expiration (24 hours in seconds)
SESSION_EXPIRY_SECONDS = 24 * 60 * 60

# Default session name
DEFAULT_SESSION = "default"


class SessionManager:
    """
    Manages Claude Code session IDs for --continue functionality.

    Sessions are stored in ~/.suzerain/session.json with structure:
    {
        "current": "default",
        "sessions": {
            "default": {
                "session_id": "abc123...",
                "last_used": 1704067200.0,
                "created": 1704000000.0,
                "description": "Default session"
            },
            "work": {
                "session_id": "def456...",
                ...
            }
        }
    }
    """

    def __init__(self, session_file: Path = None):
        """
        Initialize session manager.

        Args:
            session_file: Path to session storage file (default: ~/.suzerain/session.json)
        """
        self.session_file = session_file or SESSION_FILE
        self._ensure_dir()
        self._data = self._load()

    def _ensure_dir(self) -> None:
        """Create ~/.suzerain directory if it doesn't exist."""
        self.session_file.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        """Load session data from disk."""
        if not self.session_file.exists():
            return {
                "current": DEFAULT_SESSION,
                "sessions": {}
            }

        try:
            with open(self.session_file, 'r') as f:
                data = json.load(f)
            # Validate structure
            if "sessions" not in data:
                data["sessions"] = {}
            if "current" not in data:
                data["current"] = DEFAULT_SESSION
            return data
        except (json.JSONDecodeError, IOError):
            # Corrupted file - start fresh
            return {
                "current": DEFAULT_SESSION,
                "sessions": {}
            }

    def _save(self) -> None:
        """Persist session data to disk."""
        self._ensure_dir()
        with open(self.session_file, 'w') as f:
            json.dump(self._data, f, indent=2)

    def _clean_expired(self) -> int:
        """
        Remove sessions older than 24 hours.

        Returns:
            Number of sessions cleaned
        """
        now = time.time()
        expired = []

        for name, session in self._data["sessions"].items():
            last_used = session.get("last_used", 0)
            if now - last_used > SESSION_EXPIRY_SECONDS:
                expired.append(name)

        for name in expired:
            del self._data["sessions"][name]

        # If current session was expired, reset to default
        if self._data["current"] in expired:
            self._data["current"] = DEFAULT_SESSION

        if expired:
            self._save()

        return len(expired)

    @property
    def current_session_name(self) -> str:
        """Get the name of the current active session."""
        return self._data.get("current", DEFAULT_SESSION)

    def get_session_id(self, name: str = None) -> Optional[str]:
        """
        Get session ID for a named session.

        Args:
            name: Session name (default: current session)

        Returns:
            Session ID string or None if no session exists
        """
        self._clean_expired()

        name = name or self._data.get("current", DEFAULT_SESSION)
        session = self._data["sessions"].get(name)

        if session:
            # Check if expired
            last_used = session.get("last_used", 0)
            if time.time() - last_used > SESSION_EXPIRY_SECONDS:
                del self._data["sessions"][name]
                self._save()
                return None
            return session.get("session_id")

        return None

    def save_session_id(self, session_id: str, name: str = None, description: str = None) -> None:
        """
        Save a session ID.

        Args:
            session_id: Claude Code session/conversation ID
            name: Session name (default: current session)
            description: Optional human-readable description
        """
        name = name or self._data.get("current", DEFAULT_SESSION)
        now = time.time()

        existing = self._data["sessions"].get(name, {})

        self._data["sessions"][name] = {
            "session_id": session_id,
            "last_used": now,
            "created": existing.get("created", now),
            "description": description or existing.get("description", "")
        }

        self._save()

    def touch_session(self, name: str = None) -> None:
        """
        Update last_used timestamp for a session.

        Args:
            name: Session name (default: current session)
        """
        name = name or self._data.get("current", DEFAULT_SESSION)

        if name in self._data["sessions"]:
            self._data["sessions"][name]["last_used"] = time.time()
            self._save()

    def switch_session(self, name: str) -> bool:
        """
        Switch to a different session.

        Args:
            name: Session name to switch to

        Returns:
            True if session exists, False if creating new
        """
        self._data["current"] = name
        exists = name in self._data["sessions"]
        self._save()
        return exists

    def name_session(self, name: str, session_id: str = None, description: str = None) -> None:
        """
        Give the current session a name.

        Args:
            name: New name for the session
            session_id: Session ID (if not provided, copies from current session)
            description: Optional description
        """
        current_name = self._data.get("current", DEFAULT_SESSION)

        if session_id is None:
            # Copy from current session if exists
            current = self._data["sessions"].get(current_name, {})
            session_id = current.get("session_id")

        if session_id:
            now = time.time()
            self._data["sessions"][name] = {
                "session_id": session_id,
                "last_used": now,
                "created": now,
                "description": description or f"Named from {current_name}"
            }

        self._data["current"] = name
        self._save()

    def delete_session(self, name: str) -> bool:
        """
        Delete a named session.

        Args:
            name: Session name to delete

        Returns:
            True if session was deleted, False if not found
        """
        if name in self._data["sessions"]:
            del self._data["sessions"][name]
            if self._data["current"] == name:
                self._data["current"] = DEFAULT_SESSION
            self._save()
            return True
        return False

    def list_sessions(self) -> List[dict]:
        """
        List all active sessions.

        Returns:
            List of session info dicts with name, session_id, last_used, description
        """
        self._clean_expired()

        sessions = []
        for name, data in self._data["sessions"].items():
            sessions.append({
                "name": name,
                "session_id": data.get("session_id", "")[:12] + "...",  # Truncate for display
                "last_used": data.get("last_used", 0),
                "description": data.get("description", ""),
                "is_current": name == self._data.get("current", DEFAULT_SESSION)
            })

        # Sort by last_used descending
        sessions.sort(key=lambda x: x["last_used"], reverse=True)
        return sessions

    def get_continue_args(self) -> List[str]:
        """
        Get CLI arguments for continuing the current session.

        Returns:
            List of args like ["--resume", "session_id"] or empty list
        """
        session_id = self.get_session_id()
        if session_id:
            return ["--resume", session_id]
        return []


def parse_session_id_from_output(output: str) -> Optional[str]:
    """
    Extract session/conversation ID from Claude Code output.

    Claude Code outputs JSON with session info. We look for patterns like:
    - "conversation_id": "..."
    - "session_id": "..."
    - "id": "..." (in result blocks)

    Args:
        output: Raw output from Claude Code (may be JSON lines)

    Returns:
        Session ID string or None if not found
    """
    # Try to find session/conversation ID in JSON output
    patterns = [
        r'"session_id"\s*:\s*"([^"]+)"',
        r'"conversation_id"\s*:\s*"([^"]+)"',
        r'"conversationId"\s*:\s*"([^"]+)"',
        r'"sessionId"\s*:\s*"([^"]+)"',
    ]

    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            return match.group(1)

    # Also try parsing individual JSON lines for result type with id
    for line in output.split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            # Look for session ID in various places
            if isinstance(data, dict):
                for key in ['session_id', 'sessionId', 'conversation_id', 'conversationId']:
                    if key in data:
                        return data[key]
                # Check nested structures
                if 'result' in data and isinstance(data['result'], dict):
                    for key in ['session_id', 'sessionId', 'conversation_id', 'conversationId']:
                        if key in data['result']:
                            return data['result'][key]
        except json.JSONDecodeError:
            continue

    return None


# === Singleton instance for easy access ===

_manager: Optional[SessionManager] = None


def get_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _manager
    if _manager is None:
        _manager = SessionManager()
    return _manager


def reset_manager() -> None:
    """Reset the global session manager (for testing)."""
    global _manager
    _manager = None


# === CLI for testing ===

if __name__ == "__main__":

    manager = get_manager()

    print("=" * 50)
    print("SESSION MANAGER TEST")
    print("=" * 50)

    print(f"\nSession file: {manager.session_file}")
    print(f"Current session: {manager.current_session_name}")

    # List sessions
    sessions = manager.list_sessions()
    if sessions:
        print(f"\nActive sessions ({len(sessions)}):")
        for s in sessions:
            current = " [CURRENT]" if s["is_current"] else ""
            print(f"  - {s['name']}: {s['session_id']}{current}")
            if s["description"]:
                print(f"    {s['description']}")
    else:
        print("\nNo active sessions.")

    # Test parsing
    test_output = '{"type": "result", "session_id": "test-session-123"}'
    parsed = parse_session_id_from_output(test_output)
    print(f"\nParse test: '{parsed}'")

    print()
