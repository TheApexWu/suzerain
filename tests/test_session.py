"""
Session memory unit tests - verify context tracking works correctly.

They rode on.
"""

import pytest
import tempfile
from pathlib import Path
from src.session import (
    SessionManager,
    SessionContext,
    CommandContext,
    log_command,
    get_session_context,
    get_last_summary,
    get_undo_info,
)


class TestCommandContext:
    """Test CommandContext dataclass."""

    def test_create_context(self):
        """Verify CommandContext creation."""
        ctx = CommandContext(
            timestamp="2024-01-01T12:00:00",
            phrase="run tests",
            agent_type="tester",
        )
        assert ctx.phrase == "run tests"
        assert ctx.agent_type == "tester"
        assert ctx.success is True
        assert ctx.files_modified == []

    def test_to_dict(self):
        """Verify to_dict serialization."""
        ctx = CommandContext(
            timestamp="2024-01-01T12:00:00",
            phrase="run tests",
            agent_type="tester",
            files_modified=["test.py"],
        )
        d = ctx.to_dict()
        assert d["phrase"] == "run tests"
        assert d["files_modified"] == ["test.py"]

    def test_from_dict(self):
        """Verify from_dict deserialization."""
        data = {
            "timestamp": "2024-01-01T12:00:00",
            "phrase": "deploy",
            "agent_type": "deployer",
            "files_read": [],
            "files_modified": ["deploy.py"],
            "summary": "Deployed successfully",
            "success": True,
            "claude_output_preview": "",
        }
        ctx = CommandContext.from_dict(data)
        assert ctx.phrase == "deploy"
        assert ctx.summary == "Deployed successfully"


class TestSessionContext:
    """Test SessionContext dataclass."""

    def test_create_session(self):
        """Verify SessionContext creation."""
        session = SessionContext(
            session_id="abc123",
            start_time="2024-01-01T12:00:00",
        )
        assert session.session_id == "abc123"
        assert session.commands == []

    def test_add_command(self):
        """Verify adding commands to session."""
        session = SessionContext(
            session_id="abc123",
            start_time="2024-01-01T12:00:00",
        )
        ctx = CommandContext(
            timestamp="2024-01-01T12:01:00",
            phrase="run tests",
            agent_type="tester",
        )
        session.add_command(ctx)
        assert len(session.commands) == 1
        assert session.commands[0].phrase == "run tests"

    def test_get_last_command(self):
        """Verify getting last command."""
        session = SessionContext(
            session_id="abc123",
            start_time="2024-01-01T12:00:00",
        )
        assert session.get_last_command() is None

        ctx1 = CommandContext(timestamp="1", phrase="first", agent_type="general")
        ctx2 = CommandContext(timestamp="2", phrase="second", agent_type="general")
        session.add_command(ctx1)
        session.add_command(ctx2)

        last = session.get_last_command()
        assert last.phrase == "second"

    def test_get_last_n_commands(self):
        """Verify getting last N commands."""
        session = SessionContext(
            session_id="abc123",
            start_time="2024-01-01T12:00:00",
        )
        for i in range(10):
            ctx = CommandContext(timestamp=str(i), phrase=f"cmd{i}", agent_type="general")
            session.add_command(ctx)

        last_3 = session.get_last_n_commands(3)
        assert len(last_3) == 3
        assert last_3[0].phrase == "cmd7"
        assert last_3[-1].phrase == "cmd9"

    def test_get_all_modified_files(self):
        """Verify getting all modified files."""
        session = SessionContext(
            session_id="abc123",
            start_time="2024-01-01T12:00:00",
        )
        ctx1 = CommandContext(
            timestamp="1",
            phrase="first",
            agent_type="general",
            files_modified=["a.py", "b.py"]
        )
        ctx2 = CommandContext(
            timestamp="2",
            phrase="second",
            agent_type="general",
            files_modified=["b.py", "c.py"]
        )
        session.add_command(ctx1)
        session.add_command(ctx2)

        files = session.get_all_modified_files()
        assert files == {"a.py", "b.py", "c.py"}

    def test_format_for_prompt(self):
        """Verify prompt formatting."""
        session = SessionContext(
            session_id="abc123",
            start_time="2024-01-01T12:00:00",
        )
        ctx = CommandContext(
            timestamp="1",
            phrase="run tests",
            agent_type="tester",
            summary="All tests passed",
            files_modified=["test.py"],
            success=True,
        )
        session.add_command(ctx)

        formatted = session.format_for_prompt()
        assert "run tests" in formatted
        assert "tester" in formatted
        assert "All tests passed" in formatted
        assert "test.py" in formatted

    def test_empty_session_format(self):
        """Verify empty session returns empty string."""
        session = SessionContext(
            session_id="abc123",
            start_time="2024-01-01T12:00:00",
        )
        assert session.format_for_prompt() == ""


class TestSessionManager:
    """Test SessionManager class."""

    def test_create_manager(self):
        """Verify SessionManager creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(session_dir=Path(tmpdir))
            assert manager.session is not None
            assert manager.session.session_id

    def test_log_command(self):
        """Verify logging commands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(session_dir=Path(tmpdir))
            ctx = manager.log_command(
                phrase="run tests",
                agent_type="tester",
                success=True,
            )
            assert ctx.phrase == "run tests"
            assert manager.command_count() == 1

    def test_log_command_with_files(self):
        """Verify logging commands with file tracking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(session_dir=Path(tmpdir))
            ctx = manager.log_command(
                phrase="refactor code",
                agent_type="implementer",
                files_modified=["src/main.py", "src/utils.py"],
            )
            assert ctx.files_modified == ["src/main.py", "src/utils.py"]

    def test_session_persistence(self):
        """Verify session persists to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager1 = SessionManager(session_dir=Path(tmpdir))
            session_id = manager1.session.session_id
            manager1.log_command(phrase="test", agent_type="general")

            # Create new manager - should load existing session
            SessionManager.reset_instance()
            manager2 = SessionManager(session_dir=Path(tmpdir))
            assert manager2.session.session_id == session_id
            assert manager2.command_count() == 1

    def test_get_last_command_summary(self):
        """Verify last command summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(session_dir=Path(tmpdir))

            # Empty session
            summary = manager.get_last_command_summary()
            assert "No commands" in summary

            # With command
            manager.log_command(
                phrase="deploy",
                agent_type="deployer",
                summary="Deployed to staging",
                files_modified=["deploy.sh"],
            )
            summary = manager.get_last_command_summary()
            assert "deploy" in summary
            assert "Deployed to staging" in summary

    def test_get_undo_context(self):
        """Verify undo context generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(session_dir=Path(tmpdir))

            # Empty session
            undo = manager.get_undo_context()
            assert "Nothing to undo" in undo

            # With command
            manager.log_command(
                phrase="refactor",
                agent_type="implementer",
                files_modified=["src/main.py"],
            )
            undo = manager.get_undo_context()
            assert "refactor" in undo
            assert "src/main.py" in undo

    def test_new_session(self):
        """Verify creating new session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(session_dir=Path(tmpdir))
            old_id = manager.session.session_id
            manager.log_command(phrase="test", agent_type="general")

            new_session = manager.new_session()
            assert new_session.session_id != old_id
            assert manager.command_count() == 0


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_log_command_function(self):
        """Verify log_command convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            SessionManager.reset_instance()
            SessionManager.get_instance(session_dir=Path(tmpdir))

            ctx = log_command(
                phrase="test command",
                agent_type="tester",
            )
            assert ctx.phrase == "test command"

    def test_get_session_context_function(self):
        """Verify get_session_context convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            SessionManager.reset_instance()
            manager = SessionManager.get_instance(session_dir=Path(tmpdir))
            manager.log_command(phrase="test", agent_type="general", summary="did stuff")

            context = get_session_context()
            assert "test" in context

    def test_get_last_summary_function(self):
        """Verify get_last_summary convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            SessionManager.reset_instance()
            manager = SessionManager.get_instance(session_dir=Path(tmpdir))
            manager.log_command(
                phrase="the command",
                agent_type="tester",
                summary="the summary",
            )

            summary = get_last_summary()
            assert "the command" in summary

    def test_get_undo_info_function(self):
        """Verify get_undo_info convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            SessionManager.reset_instance()
            manager = SessionManager.get_instance(session_dir=Path(tmpdir))
            manager.log_command(
                phrase="dangerous action",
                agent_type="deployer",
                files_modified=["important.py"],
            )

            undo = get_undo_info()
            assert "dangerous action" in undo
            assert "important.py" in undo
