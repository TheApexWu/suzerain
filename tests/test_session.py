"""
Session Management Tests - Testing session persistence and switching.

"They rode on." - And now they can actually continue where they left off.
"""

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile

import pytest

# Add src to path for imports
SRC_PATH = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_PATH))

from session import (
    SessionManager,
    parse_session_id_from_output,
    get_manager,
    reset_manager,
    SESSION_EXPIRY_SECONDS,
    DEFAULT_SESSION,
)


# === Fixtures ===

@pytest.fixture
def temp_session_file():
    """Create a temporary session file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{}')
        temp_path = Path(f.name)
    yield temp_path
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def session_manager(temp_session_file):
    """Create a SessionManager with temporary storage."""
    return SessionManager(session_file=temp_session_file)


@pytest.fixture
def populated_session_manager(temp_session_file):
    """Create a SessionManager with pre-populated sessions."""
    manager = SessionManager(session_file=temp_session_file)
    manager.save_session_id("session-abc123", "work", "Work projects")
    manager.save_session_id("session-def456", "personal", "Personal projects")
    manager.save_session_id("session-ghi789", "default")
    return manager


# === SessionManager Basic Tests ===

class TestSessionManagerBasic:
    """Test basic SessionManager functionality."""

    def test_init_creates_empty_state(self, session_manager):
        """Verify new SessionManager has correct initial state."""
        assert session_manager.current_session_name == DEFAULT_SESSION
        assert session_manager.get_session_id() is None

    def test_save_and_get_session_id(self, session_manager):
        """Test saving and retrieving a session ID."""
        session_manager.save_session_id("test-session-123")

        result = session_manager.get_session_id()
        assert result == "test-session-123"

    def test_save_session_with_name(self, session_manager):
        """Test saving a session with a specific name."""
        session_manager.save_session_id("work-session-456", "work")

        result = session_manager.get_session_id("work")
        assert result == "work-session-456"

    def test_save_session_with_description(self, session_manager):
        """Test saving a session with description."""
        session_manager.save_session_id("proj-session", "project", "My cool project")

        sessions = session_manager.list_sessions()
        project_session = next(s for s in sessions if s["name"] == "project")
        assert project_session["description"] == "My cool project"

    def test_persistence_across_instances(self, temp_session_file):
        """Verify sessions persist across manager instances."""
        manager1 = SessionManager(session_file=temp_session_file)
        manager1.save_session_id("persistent-session-123")

        # Create new instance
        manager2 = SessionManager(session_file=temp_session_file)
        result = manager2.get_session_id()
        assert result == "persistent-session-123"


# === Session Switching Tests ===

class TestSessionSwitching:
    """Test session switching functionality."""

    def test_switch_to_existing_session(self, populated_session_manager):
        """Test switching to an existing session."""
        exists = populated_session_manager.switch_session("work")

        assert exists is True
        assert populated_session_manager.current_session_name == "work"

    def test_switch_to_new_session(self, session_manager):
        """Test switching to a non-existent session (creates it)."""
        exists = session_manager.switch_session("new-project")

        assert exists is False
        assert session_manager.current_session_name == "new-project"

    def test_switch_preserves_session_data(self, populated_session_manager):
        """Test that switching doesn't affect session data."""
        original_id = populated_session_manager.get_session_id("work")

        populated_session_manager.switch_session("personal")
        populated_session_manager.switch_session("work")

        assert populated_session_manager.get_session_id() == original_id


# === Session Naming Tests ===

class TestSessionNaming:
    """Test session naming functionality."""

    def test_name_session(self, session_manager):
        """Test naming a session."""
        session_manager.save_session_id("unnamed-session")
        session_manager.name_session("my-project", description="Cool project")

        assert session_manager.current_session_name == "my-project"
        result = session_manager.get_session_id()
        assert result == "unnamed-session"

    def test_name_session_copies_from_current(self, session_manager):
        """Test that naming copies session ID from current."""
        session_manager.save_session_id("original-session")
        session_manager.name_session("new-name")

        # Should have the same session ID
        assert session_manager.get_session_id("new-name") == "original-session"


# === Session Expiry Tests ===

class TestSessionExpiry:
    """Test session expiration functionality."""

    def test_expired_session_returns_none(self, temp_session_file):
        """Test that expired sessions return None."""
        manager = SessionManager(session_file=temp_session_file)

        # Manually create an expired session
        manager._data["sessions"]["old-session"] = {
            "session_id": "expired-123",
            "last_used": time.time() - SESSION_EXPIRY_SECONDS - 100,
            "created": time.time() - SESSION_EXPIRY_SECONDS - 200,
        }
        manager._save()

        result = manager.get_session_id("old-session")
        assert result is None

    def test_clean_expired_removes_old_sessions(self, temp_session_file):
        """Test that cleaning removes expired sessions."""
        manager = SessionManager(session_file=temp_session_file)

        # Create one fresh and one expired session
        manager.save_session_id("fresh-session", "fresh")
        manager._data["sessions"]["old"] = {
            "session_id": "old-session",
            "last_used": time.time() - SESSION_EXPIRY_SECONDS - 100,
            "created": time.time() - SESSION_EXPIRY_SECONDS - 200,
        }
        manager._save()

        cleaned = manager._clean_expired()

        assert cleaned == 1
        assert "old" not in manager._data["sessions"]
        assert "fresh" in manager._data["sessions"]

    def test_touch_session_updates_timestamp(self, session_manager):
        """Test that touching a session updates last_used."""
        session_manager.save_session_id("touch-test")
        original_time = session_manager._data["sessions"]["default"]["last_used"]

        time.sleep(0.1)  # Small delay
        session_manager.touch_session()

        new_time = session_manager._data["sessions"]["default"]["last_used"]
        assert new_time > original_time


# === Session Listing Tests ===

class TestSessionListing:
    """Test session listing functionality."""

    def test_list_sessions_empty(self, session_manager):
        """Test listing when no sessions exist."""
        sessions = session_manager.list_sessions()
        assert sessions == []

    def test_list_sessions_returns_all(self, populated_session_manager):
        """Test that listing returns all sessions."""
        sessions = populated_session_manager.list_sessions()

        names = {s["name"] for s in sessions}
        assert "work" in names
        assert "personal" in names
        assert "default" in names

    def test_list_sessions_marks_current(self, populated_session_manager):
        """Test that current session is marked."""
        populated_session_manager.switch_session("work")
        sessions = populated_session_manager.list_sessions()

        work_session = next(s for s in sessions if s["name"] == "work")
        assert work_session["is_current"] is True

        personal_session = next(s for s in sessions if s["name"] == "personal")
        assert personal_session["is_current"] is False

    def test_list_sessions_sorted_by_last_used(self, temp_session_file):
        """Test that sessions are sorted by last_used (most recent first)."""
        manager = SessionManager(session_file=temp_session_file)

        # Create sessions with different timestamps - use recent times to avoid expiry
        now = time.time()
        manager._data["sessions"] = {
            "old": {"session_id": "1", "last_used": now - 300, "created": now - 300, "description": ""},
            "new": {"session_id": "2", "last_used": now - 100, "created": now - 100, "description": ""},
            "mid": {"session_id": "3", "last_used": now - 200, "created": now - 200, "description": ""},
        }
        manager._save()

        sessions = manager.list_sessions()
        names = [s["name"] for s in sessions]
        assert names == ["new", "mid", "old"]


# === Session Deletion Tests ===

class TestSessionDeletion:
    """Test session deletion functionality."""

    def test_delete_existing_session(self, populated_session_manager):
        """Test deleting an existing session."""
        result = populated_session_manager.delete_session("work")

        assert result is True
        assert populated_session_manager.get_session_id("work") is None

    def test_delete_nonexistent_session(self, session_manager):
        """Test deleting a session that doesn't exist."""
        result = session_manager.delete_session("nonexistent")

        assert result is False

    def test_delete_current_session_resets_to_default(self, populated_session_manager):
        """Test that deleting current session resets to default."""
        populated_session_manager.switch_session("work")
        populated_session_manager.delete_session("work")

        assert populated_session_manager.current_session_name == DEFAULT_SESSION


# === Session ID Parsing Tests ===

class TestParseSessionId:
    """Test parsing session IDs from Claude output."""

    def test_parse_session_id_json(self):
        """Test parsing session_id from JSON output."""
        output = '{"type": "result", "session_id": "abc123-def456"}'

        result = parse_session_id_from_output(output)
        assert result == "abc123-def456"

    def test_parse_conversation_id(self):
        """Test parsing conversation_id variant."""
        output = '{"conversation_id": "conv-xyz789"}'

        result = parse_session_id_from_output(output)
        assert result == "conv-xyz789"

    def test_parse_camel_case_session_id(self):
        """Test parsing camelCase sessionId."""
        output = '{"sessionId": "session-camel-123"}'

        result = parse_session_id_from_output(output)
        assert result == "session-camel-123"

    def test_parse_multiline_output(self):
        """Test parsing from multiline output."""
        output = '''{"type": "assistant", "content": "Hello"}
{"type": "result", "session_id": "multi-line-session"}
{"type": "done"}'''

        result = parse_session_id_from_output(output)
        assert result == "multi-line-session"

    def test_parse_no_session_id(self):
        """Test parsing when no session ID present."""
        output = '{"type": "result", "content": "No session here"}'

        result = parse_session_id_from_output(output)
        assert result is None

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        result = parse_session_id_from_output("")
        assert result is None

    def test_parse_non_json_output(self):
        """Test parsing non-JSON output."""
        output = "This is just plain text output"

        result = parse_session_id_from_output(output)
        assert result is None


# === Get Continue Args Tests ===

class TestGetContinueArgs:
    """Test getting CLI arguments for continuation."""

    def test_get_continue_args_with_session(self, session_manager):
        """Test getting args when session exists."""
        session_manager.save_session_id("resume-session-123")

        args = session_manager.get_continue_args()
        assert args == ["--resume", "resume-session-123"]

    def test_get_continue_args_without_session(self, session_manager):
        """Test getting args when no session exists."""
        args = session_manager.get_continue_args()
        assert args == []


# === Global Manager Tests ===

class TestGlobalManager:
    """Test global session manager singleton."""

    def test_get_manager_returns_same_instance(self):
        """Test that get_manager returns singleton."""
        reset_manager()

        manager1 = get_manager()
        manager2 = get_manager()

        assert manager1 is manager2

    def test_reset_manager_clears_singleton(self):
        """Test that reset_manager clears the singleton."""
        reset_manager()

        manager1 = get_manager()
        reset_manager()
        manager2 = get_manager()

        assert manager1 is not manager2


# === Edge Cases ===

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_corrupted_session_file(self, temp_session_file):
        """Test handling of corrupted session file."""
        # Write invalid JSON
        with open(temp_session_file, 'w') as f:
            f.write("not valid json {{{")

        manager = SessionManager(session_file=temp_session_file)

        # Should start with empty state
        assert manager.current_session_name == DEFAULT_SESSION
        assert manager.get_session_id() is None

    def test_session_file_with_missing_fields(self, temp_session_file):
        """Test handling of session file with missing fields."""
        with open(temp_session_file, 'w') as f:
            json.dump({"sessions": {"test": {"session_id": "abc"}}}, f)

        manager = SessionManager(session_file=temp_session_file)

        # Should handle gracefully
        assert manager.current_session_name == DEFAULT_SESSION

    def test_special_characters_in_session_name(self, session_manager):
        """Test session names with special characters."""
        session_manager.save_session_id("test", "my-project_v2.0")

        result = session_manager.get_session_id("my-project_v2.0")
        assert result == "test"

    def test_empty_session_name(self, session_manager):
        """Test handling of empty session name."""
        # Empty string is falsy so defaults to current session
        session_manager.save_session_id("test-session", "")

        # Empty string uses default session (where we just saved)
        result = session_manager.get_session_id("")
        assert result == "test-session"  # "" defaults to current session
