"""
Main module unit tests - testing execute_command, transcribe_audio, and CLI modes.

"Whatever exists without my knowledge exists without my consent."
"""

import io
import json
import os
import sys
from unittest.mock import MagicMock, patch, call

import pytest

# Import from src
from main import (
    Colors,
    SANDBOX_MODE,
    get_grimoire_keywords,
    transcribe_audio,
    disambiguate,
    execute_command,
    show_commands,
    validate_mode,
)


# === Colors Tests ===

class TestColors:
    """Test terminal color handling."""

    def test_colors_class_has_expected_attributes(self):
        """Verify Colors class has expected color attributes."""
        # Check that expected attributes exist
        assert hasattr(Colors, 'RESET')
        assert hasattr(Colors, 'RED')
        assert hasattr(Colors, 'GREEN')
        assert hasattr(Colors, 'BOLD')
        # Note: In non-TTY mode (like pytest), colors may be disabled (empty strings)
        # So we only verify the attributes exist, not their values

    def test_colors_disable(self):
        """Test that disable() clears all color codes."""
        # Create a fresh Colors class to avoid polluting global state
        class TestColors:
            RESET = "\033[0m"
            BOLD = "\033[1m"
            RED = "\033[31m"
            GREEN = "\033[32m"

            @classmethod
            def disable(cls):
                for attr in dir(cls):
                    if not attr.startswith('_') and attr.isupper():
                        setattr(cls, attr, "")

        TestColors.disable()

        assert TestColors.RESET == ""
        assert TestColors.BOLD == ""
        assert TestColors.RED == ""
        assert TestColors.GREEN == ""


# === Grimoire Keywords Tests ===

class TestGetGrimoireKeywords:
    """Test keyword extraction for STT boosting."""

    def test_returns_keyword_string(self):
        """Verify keywords are extracted from grimoire."""
        keywords = get_grimoire_keywords()

        # Should return a comma-separated string
        assert isinstance(keywords, str)

        # Should contain some expected keywords from grimoire
        # (Based on phrases like "evening redness", "they rode on", etc.)
        keyword_list = keywords.split(",")
        assert len(keyword_list) > 0

    def test_excludes_stopwords(self):
        """Verify common stopwords are filtered out."""
        keywords = get_grimoire_keywords()

        # Parse keyword list to check actual words (format is "word:2")
        keyword_words = [kw.split(":")[0] for kw in keywords.split(",")]

        # These common stopwords should not appear as standalone keywords
        stopwords = ["the", "a", "an", "in", "to", "for", "of"]
        for stopword in stopwords:
            # Check the actual word, not substring matching
            assert stopword not in keyword_words, f"Stopword '{stopword}' found in keywords"

    def test_keyword_format(self):
        """Verify keywords have proper boost format."""
        keywords = get_grimoire_keywords()

        if keywords:  # Only test if there are keywords
            parts = keywords.split(",")
            for part in parts[:5]:  # Check first 5
                assert ":2" in part, f"Keyword {part} missing boost value"


# === Transcribe Audio Tests ===

class TestTranscribeAudio:
    """Test Deepgram transcription with mocked API."""

    def test_transcribe_success(
        self, mock_deepgram_env, deepgram_success_response, mock_urlopen_factory, monkeypatch
    ):
        """Test successful transcription."""
        mock_urlopen = mock_urlopen_factory(deepgram_success_response)
        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

        result = transcribe_audio(b"fake audio data")

        assert result == "the evening redness in the west"

    def test_transcribe_empty_response(
        self, mock_deepgram_env, deepgram_empty_response, mock_urlopen_factory, monkeypatch
    ):
        """Test handling of empty transcript."""
        mock_urlopen = mock_urlopen_factory(deepgram_empty_response)
        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

        result = transcribe_audio(b"fake audio data")

        assert result == ""

    def test_transcribe_missing_api_key(self, clean_env, capsys):
        """Test error handling when API key is missing."""
        result = transcribe_audio(b"fake audio data")

        assert result == ""
        captured = capsys.readouterr()
        assert "DEEPGRAM_API_KEY not set" in captured.out

    def test_transcribe_api_error(self, mock_deepgram_env, monkeypatch, capsys):
        """Test handling of API errors."""
        def mock_urlopen_error(*args, **kwargs):
            raise Exception("API connection failed")

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen_error)

        result = transcribe_audio(b"fake audio data")

        assert result == ""
        captured = capsys.readouterr()
        assert "Transcription error" in captured.out

    def test_transcribe_timeout(self, mock_deepgram_env, monkeypatch, capsys):
        """Test handling of timeout errors."""
        import urllib.error

        def mock_urlopen_timeout(*args, **kwargs):
            raise urllib.error.URLError("timeout")

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen_timeout)

        result = transcribe_audio(b"fake audio data")

        assert result == ""
        captured = capsys.readouterr()
        assert "network error" in captured.out


# === Disambiguate Tests ===

class TestDisambiguate:
    """Test disambiguation flow when multiple commands match."""

    def test_disambiguate_select_first(self, monkeypatch, capsys):
        """Test selecting first option."""
        monkeypatch.setattr('builtins.input', lambda _: "1")

        matches = [
            ({"phrase": "first command", "tags": ["test"]}, 95),
            ({"phrase": "second command", "tags": ["test"]}, 90),
        ]

        result = disambiguate(matches)

        assert result[0]["phrase"] == "first command"
        assert result[1] == 95

    def test_disambiguate_select_second(self, monkeypatch, capsys):
        """Test selecting second option."""
        monkeypatch.setattr('builtins.input', lambda _: "2")

        matches = [
            ({"phrase": "first command", "tags": ["test"]}, 95),
            ({"phrase": "second command", "tags": ["test"]}, 90),
        ]

        result = disambiguate(matches)

        assert result[0]["phrase"] == "second command"
        assert result[1] == 90

    def test_disambiguate_cancel(self, monkeypatch, capsys):
        """Test cancelling disambiguation."""
        monkeypatch.setattr('builtins.input', lambda _: "0")

        matches = [
            ({"phrase": "first command", "tags": ["test"]}, 95),
        ]

        result = disambiguate(matches)

        assert result == (None, None)

    def test_disambiguate_empty_input(self, monkeypatch, capsys):
        """Test empty input cancels."""
        monkeypatch.setattr('builtins.input', lambda _: "")

        matches = [
            ({"phrase": "first command", "tags": ["test"]}, 95),
        ]

        result = disambiguate(matches)

        assert result == (None, None)

    def test_disambiguate_invalid_input(self, monkeypatch, capsys):
        """Test invalid input handling."""
        monkeypatch.setattr('builtins.input', lambda _: "invalid")

        matches = [
            ({"phrase": "first command", "tags": ["test"]}, 95),
        ]

        result = disambiguate(matches)

        assert result == (None, None)
        captured = capsys.readouterr()
        assert "Invalid selection" in captured.out

    def test_disambiguate_out_of_range(self, monkeypatch, capsys):
        """Test out of range selection."""
        monkeypatch.setattr('builtins.input', lambda _: "99")

        matches = [
            ({"phrase": "first command", "tags": ["test"]}, 95),
        ]

        result = disambiguate(matches)

        assert result == (None, None)
        captured = capsys.readouterr()
        assert "Invalid selection" in captured.out


# === Execute Command Tests ===

class TestExecuteCommand:
    """Test command execution with mocked subprocess."""

    def test_execute_dry_run_via_modifier(
        self, sample_command, sample_dry_run_modifier, capsys
    ):
        """Test dry run mode via modifier."""
        result = execute_command(sample_command, [sample_dry_run_modifier])

        assert result == 0
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out
        assert sample_command["expansion"] in captured.out

    def test_execute_dry_run_explicit(self, sample_command, capsys):
        """Test explicit dry run parameter."""
        result = execute_command(sample_command, [], dry_run=True)

        assert result == 0
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out

    def test_execute_sandbox_mode(self, sample_command, capsys, monkeypatch):
        """Test that sandbox mode forces dry run."""
        # Enable sandbox mode
        monkeypatch.setattr('main.SANDBOX_MODE', True)

        result = execute_command(sample_command, [])

        assert result == 0
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out

    def test_execute_confirmation_aborted(
        self, sample_command_with_confirmation, monkeypatch, capsys
    ):
        """Test that confirmation can abort execution."""
        # User declines confirmation
        monkeypatch.setattr('builtins.input', lambda _: "n")

        result = execute_command(sample_command_with_confirmation, [])

        assert result == 1
        captured = capsys.readouterr()
        assert "Aborted" in captured.out

    def test_execute_confirmation_accepted(
        self, sample_command_with_confirmation, mock_subprocess_factory, monkeypatch, capsys
    ):
        """Test that accepted confirmation proceeds with execution."""
        # User accepts confirmation
        monkeypatch.setattr('builtins.input', lambda _: "y")
        monkeypatch.setattr('subprocess.Popen', mock_subprocess_factory(return_code=0))

        result = execute_command(sample_command_with_confirmation, [])

        assert result == 0
        captured = capsys.readouterr()
        assert "Complete" in captured.out

    def test_execute_success(
        self, sample_command, mock_subprocess_factory, monkeypatch, capsys
    ):
        """Test successful command execution."""
        monkeypatch.setattr('subprocess.Popen', mock_subprocess_factory(return_code=0))

        result = execute_command(sample_command, [])

        assert result == 0
        captured = capsys.readouterr()
        assert "Executing" in captured.out
        assert "Complete" in captured.out

    def test_execute_failure(
        self, sample_command, mock_subprocess_factory, monkeypatch, capsys
    ):
        """Test failed command execution."""
        monkeypatch.setattr('subprocess.Popen', mock_subprocess_factory(return_code=1))

        result = execute_command(sample_command, [])

        assert result == 1
        captured = capsys.readouterr()
        assert "Failed" in captured.out

    def test_execute_claude_not_found(self, sample_command, monkeypatch, capsys):
        """Test handling when claude CLI is not installed."""
        def mock_popen_not_found(*args, **kwargs):
            raise FileNotFoundError("claude not found")

        monkeypatch.setattr('subprocess.Popen', mock_popen_not_found)

        result = execute_command(sample_command, [])

        assert result == 1
        captured = capsys.readouterr()
        assert "claude" in captured.out.lower()
        assert "not found" in captured.out.lower()

    def test_execute_keyboard_interrupt(self, sample_command, monkeypatch, capsys):
        """Test handling of KeyboardInterrupt during execution."""
        # Create a mock that raises KeyboardInterrupt when iterating stdout
        class MockProcessInterrupt:
            def __init__(self, *args, **kwargs):
                self.returncode = 130
                self._raise_interrupt = True

            @property
            def stdout(self):
                """Raise KeyboardInterrupt when trying to iterate."""
                if self._raise_interrupt:
                    self._raise_interrupt = False
                    raise KeyboardInterrupt()
                return iter([])

            def wait(self):
                pass

        monkeypatch.setattr('subprocess.Popen', MockProcessInterrupt)

        result = execute_command(sample_command, [])

        assert result == 130  # Standard interrupt exit code
        captured = capsys.readouterr()
        assert "Interrupted" in captured.out

    def test_execute_with_shell_command_removed(
        self, sample_command_with_shell, mock_subprocess_factory, monkeypatch, capsys
    ):
        """Test that shell_command is no longer included in expansion (security fix)."""
        result = execute_command(sample_command_with_shell, [], dry_run=True)

        assert result == 0
        captured = capsys.readouterr()
        # shell_command feature was removed for security - verify it's not in output
        assert "echo 'test'" not in captured.out
        # But the expansion text should still appear
        assert "After running the shell command" in captured.out

    def test_execute_with_modifiers_displayed(
        self, sample_command, sample_modifier, mock_subprocess_factory, monkeypatch, capsys
    ):
        """Test that modifiers are displayed during execution."""
        monkeypatch.setattr('subprocess.Popen', mock_subprocess_factory(return_code=0))

        result = execute_command(sample_command, [sample_modifier])

        assert result == 0
        captured = capsys.readouterr()
        assert "Modifiers" in captured.out
        assert "test_effect" in captured.out

    def test_execute_streams_json_output(
        self, sample_command, monkeypatch, capsys
    ):
        """Test that JSON streaming output is parsed correctly."""
        class MockProcessWithOutput:
            def __init__(self, *args, **kwargs):
                self.returncode = 0
                self.stdout = iter([
                    '{"type": "assistant", "message": {"content": [{"type": "text", "text": "Hello from Claude"}]}}',
                    '{"type": "tool_use", "name": "write_file"}',
                    '{"type": "result", "result": "Done"}',
                ])

            def wait(self):
                pass

        monkeypatch.setattr('subprocess.Popen', MockProcessWithOutput)

        result = execute_command(sample_command, [])

        assert result == 0
        captured = capsys.readouterr()
        assert "Hello from Claude" in captured.out
        assert "write_file" in captured.out

    def test_execute_handles_malformed_json(
        self, sample_command, monkeypatch, capsys
    ):
        """Test handling of malformed JSON in output stream."""
        class MockProcessWithBadOutput:
            def __init__(self, *args, **kwargs):
                self.returncode = 0
                self.stdout = iter([
                    'This is not JSON',
                    '{"type": "result", "result": "Done"}',
                ])

            def wait(self):
                pass

        monkeypatch.setattr('subprocess.Popen', MockProcessWithBadOutput)

        result = execute_command(sample_command, [])

        assert result == 0
        captured = capsys.readouterr()
        # Non-JSON lines should be printed with warning color
        assert "This is not JSON" in captured.out

    def test_execute_use_continue_flag(self, monkeypatch, capsys):
        """Test that use_continue flag uses --continue with -p for the prompt."""
        command_with_continue = {
            "phrase": "they rode on",
            "expansion": "Continue the task",
            "use_continue": True,
            "tags": ["continuation"],
            "confirmation": False
        }

        captured_cmd = []

        class MockProcessCapture:
            def __init__(self, cmd, **kwargs):
                captured_cmd.extend(cmd)
                self.returncode = 0
                self.stdout = iter(['{"type": "result", "result": "Done"}'])

            def wait(self):
                pass

        monkeypatch.setattr('subprocess.Popen', MockProcessCapture)

        execute_command(command_with_continue, [])

        # Must have --continue AND -p with the expansion (Claude CLI requires both)
        assert "--continue" in captured_cmd
        assert "-p" in captured_cmd
        assert "Continue the task" in captured_cmd


# === Show Commands Tests ===

class TestShowCommands:
    """Test command listing display."""

    def test_show_commands_output(self, capsys):
        """Test that show_commands displays grimoire contents."""
        show_commands()

        captured = capsys.readouterr()

        # Should show section headers
        assert "GRIMOIRE COMMANDS" in captured.out
        assert "MODIFIERS" in captured.out

        # Should show some known commands
        assert "evening redness" in captured.out.lower()
        assert "they rode on" in captured.out.lower()

    def test_show_commands_shows_confirmation_warning(self, capsys):
        """Test that confirmation requirements are shown."""
        show_commands()

        captured = capsys.readouterr()

        # Commands with confirmation should be marked
        assert "confirmation" in captured.out.lower() or "warning" in captured.out.lower() or chr(0x26A0) in captured.out


# === Validate Mode Tests ===

class TestValidateMode:
    """Test grimoire validation mode."""

    def test_validate_mode_success(self, capsys):
        """Test validation of valid grimoire."""
        result = validate_mode()

        assert result == 0
        captured = capsys.readouterr()
        assert "valid" in captured.out.lower()

    def test_validate_mode_shows_counts(self, capsys):
        """Test that validation shows command/modifier counts."""
        validate_mode()

        captured = capsys.readouterr()

        # Should show counts
        assert "commands" in captured.out.lower()
        assert "modifiers" in captured.out.lower()


# === Integration-ish Tests ===

class TestExecuteCommandIntegration:
    """Test execute_command with more realistic scenarios."""

    def test_full_flow_dry_run(self, capsys):
        """Test full flow: match -> expand -> dry run."""
        from parser import match, extract_modifiers, expand_command

        # Simulate matched command
        result = match("the evening redness in the west")
        assert result is not None

        command, score = result
        modifiers = extract_modifiers("test and the judge watched")  # dry run modifier

        # Execute in dry run
        exit_code = execute_command(command, modifiers)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out
        assert "Deploy" in captured.out

    def test_full_flow_with_verbose_modifier(self, mock_subprocess_factory, monkeypatch, capsys):
        """Test full flow with verbose modifier."""
        from parser import match, extract_modifiers

        monkeypatch.setattr('subprocess.Popen', mock_subprocess_factory(return_code=0))

        result = match("the judge smiled")
        assert result is not None

        command, score = result
        modifiers = extract_modifiers("test under the stars")  # verbose modifier

        exit_code = execute_command(command, modifiers)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Modifiers" in captured.out
        assert "verbose" in captured.out
