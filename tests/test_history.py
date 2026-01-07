"""
Tests for the Suzerain command history module.
"""

import json
import os
import tempfile
from datetime import datetime, date, timedelta
from pathlib import Path

import pytest

from history import (
    CommandHistory,
    HistoryEntry,
    get_history,
    log_command,
    get_last_n,
    get_by_date,
    get_failures,
    get_last_successful,
    get_time_since_last,
    format_history_entry,
    MAX_HISTORY_ENTRIES,
)


@pytest.fixture
def temp_history_dir():
    """Create a temporary directory for history tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def history(temp_history_dir):
    """Create a CommandHistory instance with a temporary directory."""
    # Clear the singleton for testing
    CommandHistory._instance = None
    return CommandHistory(history_dir=temp_history_dir)


class TestHistoryEntry:
    """Tests for HistoryEntry dataclass."""

    def test_entry_creation(self):
        """Test creating a history entry."""
        entry = HistoryEntry(
            timestamp="2024-01-15T10:30:00",
            phrase_spoken="the evening redness",
            phrase_matched="the evening redness in the west",
            score=85.5,
            modifiers=["verbose"],
            execution_time_ms=1500.0,
            success=True,
            error=None
        )

        assert entry.timestamp == "2024-01-15T10:30:00"
        assert entry.phrase_spoken == "the evening redness"
        assert entry.phrase_matched == "the evening redness in the west"
        assert entry.score == 85.5
        assert entry.modifiers == ["verbose"]
        assert entry.execution_time_ms == 1500.0
        assert entry.success is True
        assert entry.error is None

    def test_entry_to_dict(self):
        """Test converting entry to dictionary."""
        entry = HistoryEntry(
            timestamp="2024-01-15T10:30:00",
            phrase_spoken="they rode on",
            phrase_matched="they rode on",
            score=100.0,
            modifiers=[],
            execution_time_ms=500.0,
            success=True,
            error=None
        )

        d = entry.to_dict()
        assert d["timestamp"] == "2024-01-15T10:30:00"
        assert d["phrase_matched"] == "they rode on"
        assert d["success"] is True

    def test_entry_from_dict(self):
        """Test creating entry from dictionary."""
        data = {
            "timestamp": "2024-01-15T10:30:00",
            "phrase_spoken": "judge smiled",
            "phrase_matched": "the judge smiled",
            "score": 90.0,
            "modifiers": ["dry_run"],
            "execution_time_ms": 100.0,
            "success": True,
            "error": None
        }

        entry = HistoryEntry.from_dict(data)
        assert entry.phrase_spoken == "judge smiled"
        assert entry.phrase_matched == "the judge smiled"
        assert entry.score == 90.0

    def test_entry_with_error(self):
        """Test entry with an error."""
        entry = HistoryEntry(
            timestamp="2024-01-15T10:30:00",
            phrase_spoken="bad command",
            phrase_matched=None,
            score=None,
            modifiers=[],
            execution_time_ms=50.0,
            success=False,
            error="No match found"
        )

        assert entry.success is False
        assert entry.error == "No match found"
        assert entry.phrase_matched is None


class TestCommandHistory:
    """Tests for CommandHistory class."""

    def test_log_command(self, history):
        """Test logging a command."""
        entry = history.log_command(
            phrase_spoken="the evening redness",
            phrase_matched="the evening redness in the west",
            score=85.0,
            modifiers=["verbose"],
            execution_time_ms=1000.0,
            success=True
        )

        assert entry.phrase_spoken == "the evening redness"
        assert entry.success is True

        # Check file was created
        assert history.history_file.exists()

    def test_get_last_n(self, history):
        """Test retrieving last N commands."""
        # Log several commands
        for i in range(5):
            history.log_command(
                phrase_spoken=f"command {i}",
                phrase_matched=f"phrase {i}",
                score=80.0 + i,
                execution_time_ms=100.0 * i,
                success=True
            )

        # Get last 3
        entries = history.get_last_n(3)
        assert len(entries) == 3

        # Should be in reverse order (most recent first)
        assert entries[0].phrase_spoken == "command 4"
        assert entries[1].phrase_spoken == "command 3"
        assert entries[2].phrase_spoken == "command 2"

    def test_get_last_n_empty(self, history):
        """Test get_last_n with empty history."""
        entries = history.get_last_n(10)
        assert entries == []

    def test_get_last_n_fewer_than_requested(self, history):
        """Test get_last_n when fewer entries exist."""
        history.log_command(
            phrase_spoken="only one",
            phrase_matched="only one",
            success=True
        )

        entries = history.get_last_n(10)
        assert len(entries) == 1

    def test_get_by_date(self, history):
        """Test retrieving commands by date."""
        today = date.today()

        # Log command (will be today's date)
        history.log_command(
            phrase_spoken="today command",
            phrase_matched="today phrase",
            success=True
        )

        entries = history.get_by_date(today)
        assert len(entries) == 1
        assert entries[0].phrase_spoken == "today command"

    def test_get_by_date_no_matches(self, history):
        """Test get_by_date with no matching entries."""
        # Log command today
        history.log_command(
            phrase_spoken="today command",
            success=True
        )

        # Query for yesterday
        yesterday = date.today() - timedelta(days=1)
        entries = history.get_by_date(yesterday)
        assert entries == []

    def test_get_failures(self, history):
        """Test retrieving failed commands."""
        # Log mix of successes and failures
        history.log_command(
            phrase_spoken="success 1",
            success=True
        )
        history.log_command(
            phrase_spoken="failure 1",
            success=False,
            error="error 1"
        )
        history.log_command(
            phrase_spoken="success 2",
            success=True
        )
        history.log_command(
            phrase_spoken="failure 2",
            success=False,
            error="error 2"
        )

        failures = history.get_failures()
        assert len(failures) == 2
        assert all(not f.success for f in failures)
        assert failures[0].phrase_spoken == "failure 1"
        assert failures[1].phrase_spoken == "failure 2"

    def test_get_failures_empty(self, history):
        """Test get_failures with no failures."""
        history.log_command(phrase_spoken="success", success=True)

        failures = history.get_failures()
        assert failures == []

    def test_get_by_phrase(self, history):
        """Test retrieving commands by phrase."""
        history.log_command(
            phrase_spoken="evening redness",
            phrase_matched="the evening redness in the west",
            success=True
        )
        history.log_command(
            phrase_spoken="they rode",
            phrase_matched="they rode on",
            success=True
        )
        history.log_command(
            phrase_spoken="evening",
            phrase_matched="the evening redness in the west",
            success=True
        )

        entries = history.get_by_phrase("evening redness")
        assert len(entries) == 2

    def test_get_stats(self, history):
        """Test getting summary statistics."""
        # Log various commands
        history.log_command(
            phrase_spoken="cmd1",
            phrase_matched="phrase1",
            execution_time_ms=100.0,
            success=True
        )
        history.log_command(
            phrase_spoken="cmd2",
            phrase_matched="phrase1",
            execution_time_ms=200.0,
            success=True
        )
        history.log_command(
            phrase_spoken="cmd3",
            phrase_matched="phrase2",
            execution_time_ms=150.0,
            success=False,
            error="failed"
        )

        stats = history.get_stats()
        assert stats["total_commands"] == 3
        assert stats["total_failures"] == 1
        assert stats["success_rate"] == pytest.approx(66.67, rel=0.1)
        assert stats["avg_execution_time_ms"] == pytest.approx(150.0)
        assert len(stats["most_used_commands"]) > 0

    def test_get_stats_empty(self, history):
        """Test stats on empty history."""
        stats = history.get_stats()
        assert stats["total_commands"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["avg_execution_time_ms"] == 0.0

    def test_clear(self, history):
        """Test clearing history."""
        history.log_command(phrase_spoken="cmd", success=True)
        assert history.history_file.exists()

        history.clear()
        assert not history.history_file.exists()

        entries = history.get_last_n(10)
        assert entries == []

    def test_malformed_json_handling(self, history):
        """Test handling of malformed JSON in history file."""
        # Write some valid entries
        history.log_command(phrase_spoken="valid1", success=True)

        # Manually append malformed JSON
        with open(history.history_file, "a") as f:
            f.write("this is not valid json\n")
            f.write('{"also": "incomplete"\n')

        # Log another valid entry
        history.log_command(phrase_spoken="valid2", success=True)

        # Should still get valid entries, skipping malformed
        entries = history.get_last_n(10)
        assert len(entries) == 2
        assert entries[0].phrase_spoken == "valid2"
        assert entries[1].phrase_spoken == "valid1"


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_log_command_function(self, temp_history_dir):
        """Test module-level log_command function."""
        # Reset singleton
        CommandHistory._instance = None
        hist = CommandHistory(history_dir=temp_history_dir)

        entry = log_command(
            phrase_spoken="test phrase",
            phrase_matched="matched phrase",
            score=90.0,
            success=True
        )

        assert entry.phrase_spoken == "test phrase"

    def test_format_history_entry_basic(self):
        """Test basic history entry formatting."""
        entry = HistoryEntry(
            timestamp="2024-01-15T10:30:00.123456",
            phrase_spoken="the evening redness",
            phrase_matched="the evening redness in the west",
            score=85.0,
            modifiers=[],
            execution_time_ms=1000.0,
            success=True,
            error=None
        )

        formatted = format_history_entry(entry)
        assert "2024-01-15 10:30:00" in formatted
        assert "[OK]" in formatted
        assert "evening redness in the west" in formatted
        assert "score: 85" in formatted

    def test_format_history_entry_failure(self):
        """Test formatting failed entry."""
        entry = HistoryEntry(
            timestamp="2024-01-15T10:30:00",
            phrase_spoken="bad input",
            phrase_matched=None,
            score=None,
            modifiers=[],
            execution_time_ms=50.0,
            success=False,
            error="No match"
        )

        formatted = format_history_entry(entry)
        assert "[FAIL]" in formatted
        assert "(no match)" in formatted

    def test_format_history_entry_detailed(self):
        """Test detailed history entry formatting."""
        entry = HistoryEntry(
            timestamp="2024-01-15T10:30:00",
            phrase_spoken="the evening redness",
            phrase_matched="the evening redness in the west",
            score=85.0,
            modifiers=["verbose", "dry_run"],
            execution_time_ms=1500.0,
            success=True,
            error=None
        )

        formatted = format_history_entry(entry, show_details=True)
        assert "Spoken:" in formatted
        assert "the evening redness" in formatted
        assert "Modifiers:" in formatted
        assert "verbose" in formatted
        assert "Execution:" in formatted
        assert "1500ms" in formatted


class TestHistoryPersistence:
    """Tests for history file persistence."""

    def test_history_survives_restart(self, temp_history_dir):
        """Test that history persists across instances."""
        # First instance
        CommandHistory._instance = None
        hist1 = CommandHistory(history_dir=temp_history_dir)
        hist1.log_command(phrase_spoken="persistent", success=True)

        # Second instance (simulating restart)
        CommandHistory._instance = None
        hist2 = CommandHistory(history_dir=temp_history_dir)

        entries = hist2.get_last_n(10)
        assert len(entries) == 1
        assert entries[0].phrase_spoken == "persistent"

    def test_jsonl_format(self, history):
        """Test that history file is valid JSONL."""
        history.log_command(phrase_spoken="cmd1", success=True)
        history.log_command(phrase_spoken="cmd2", success=False)

        # Read file and verify each line is valid JSON
        with open(history.history_file) as f:
            lines = f.readlines()

        assert len(lines) == 2
        for line in lines:
            data = json.loads(line.strip())
            assert "timestamp" in data
            assert "phrase_spoken" in data
            assert "success" in data


class TestConversationId:
    """Tests for conversation_id tracking."""

    def test_entry_with_conversation_id(self):
        """Test creating entry with conversation_id."""
        entry = HistoryEntry(
            timestamp="2024-01-15T10:30:00",
            phrase_spoken="the evening redness",
            phrase_matched="the evening redness in the west",
            score=85.5,
            modifiers=["verbose"],
            execution_time_ms=1500.0,
            success=True,
            error=None,
            conversation_id="conv-abc123-xyz789"
        )

        assert entry.conversation_id == "conv-abc123-xyz789"

    def test_log_command_with_conversation_id(self, history):
        """Test logging command with conversation_id."""
        entry = history.log_command(
            phrase_spoken="the evening redness",
            phrase_matched="the evening redness in the west",
            score=85.0,
            success=True,
            conversation_id="test-session-id"
        )

        assert entry.conversation_id == "test-session-id"

        # Verify persisted
        entries = history.get_last_n(1)
        assert entries[0].conversation_id == "test-session-id"

    def test_entry_without_conversation_id(self):
        """Test that conversation_id defaults to None."""
        entry = HistoryEntry(
            timestamp="2024-01-15T10:30:00",
            phrase_spoken="test",
            phrase_matched="test",
            score=100.0,
            modifiers=[],
            execution_time_ms=100.0,
            success=True
        )

        assert entry.conversation_id is None


class TestGetLastSuccessful:
    """Tests for get_last_successful functionality."""

    def test_get_last_successful_basic(self, history):
        """Test getting the last successful command."""
        history.log_command(
            phrase_spoken="first",
            phrase_matched="first phrase",
            success=True
        )
        history.log_command(
            phrase_spoken="second",
            phrase_matched="second phrase",
            success=True
        )

        last = history.get_last_successful()
        assert last is not None
        assert last.phrase_matched == "second phrase"

    def test_get_last_successful_skips_failures(self, history):
        """Test that get_last_successful skips failed commands."""
        history.log_command(
            phrase_spoken="success",
            phrase_matched="success phrase",
            success=True
        )
        history.log_command(
            phrase_spoken="failure",
            phrase_matched="failure phrase",
            success=False
        )

        last = history.get_last_successful()
        assert last is not None
        assert last.phrase_matched == "success phrase"

    def test_get_last_successful_requires_phrase_matched(self, history):
        """Test that get_last_successful requires phrase_matched."""
        history.log_command(
            phrase_spoken="no match",
            phrase_matched=None,
            success=True
        )
        history.log_command(
            phrase_spoken="with match",
            phrase_matched="matched phrase",
            success=True
        )

        last = history.get_last_successful()
        assert last.phrase_matched == "matched phrase"

    def test_get_last_successful_empty(self, history):
        """Test get_last_successful with empty history."""
        last = history.get_last_successful()
        assert last is None

    def test_get_last_successful_all_failures(self, history):
        """Test get_last_successful when all commands failed."""
        history.log_command(
            phrase_spoken="fail1",
            phrase_matched="fail phrase",
            success=False
        )

        last = history.get_last_successful()
        assert last is None


class TestTimeSinceLastCommand:
    """Tests for time_since_last functionality."""

    def test_time_since_last_just_now(self, history):
        """Test time since a very recent command."""
        history.log_command(
            phrase_spoken="recent",
            phrase_matched="recent phrase",
            success=True
        )

        time_str = history.get_time_since_last()
        assert time_str == "just now"

    def test_time_since_last_empty(self, history):
        """Test time_since_last with empty history."""
        time_str = history.get_time_since_last()
        assert time_str is None


class TestHistoryRotation:
    """Tests for history rotation (keeping last N entries)."""

    def test_rotation_keeps_max_entries(self, history):
        """Test that history rotates to keep only MAX_HISTORY_ENTRIES."""
        # Log more than MAX entries
        num_entries = MAX_HISTORY_ENTRIES + 20

        for i in range(num_entries):
            history.log_command(
                phrase_spoken=f"command {i}",
                phrase_matched=f"phrase {i}",
                success=True
            )

        # Should have exactly MAX entries
        entries = history._read_all()
        assert len(entries) == MAX_HISTORY_ENTRIES

        # Should have the most recent entries
        assert entries[-1].phrase_spoken == f"command {num_entries - 1}"
        assert entries[0].phrase_spoken == f"command {num_entries - MAX_HISTORY_ENTRIES}"

    def test_rotation_preserves_recent(self, history):
        """Test that rotation preserves the most recent entries."""
        # Log exactly MAX + 5 entries
        for i in range(MAX_HISTORY_ENTRIES + 5):
            history.log_command(
                phrase_spoken=f"cmd-{i}",
                phrase_matched=f"phrase-{i}",
                success=True
            )

        entries = history.get_last_n(5)
        # Most recent should be the last logged
        assert entries[0].phrase_spoken == f"cmd-{MAX_HISTORY_ENTRIES + 4}"


class TestBackwardCompatibility:
    """Tests for backward compatibility with old history entries."""

    def test_read_entry_without_conversation_id(self, history):
        """Test reading old entries without conversation_id field."""
        # Manually write an entry without conversation_id
        old_entry = {
            "timestamp": "2024-01-15T10:30:00",
            "phrase_spoken": "old command",
            "phrase_matched": "old phrase",
            "score": 80.0,
            "modifiers": [],
            "execution_time_ms": 100.0,
            "success": True,
            "error": None
            # Note: no conversation_id field
        }

        with open(history.history_file, "w") as f:
            f.write(json.dumps(old_entry) + "\n")

        entries = history.get_last_n(1)
        assert len(entries) == 1
        assert entries[0].phrase_spoken == "old command"
        # Should default to None when not present
        assert entries[0].conversation_id is None
