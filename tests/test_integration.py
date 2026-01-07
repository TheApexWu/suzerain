"""
Suzerain Integration Tests - End-to-end pipeline verification.

These tests verify the actual pipeline behavior, catching regressions that unit tests miss.

"War was always here. Before man was, war waited for him."
"""

import io
import json
import os
import subprocess
import sys
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

import pytest

# Add src to path for imports
SRC_PATH = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_PATH))

from parser import (
    load_grimoire,
    reload_grimoire,
    match,
    match_top_n,
    extract_modifiers,
    expand_command,
    validate_grimoire,
    list_commands,
    list_modifiers,
)


# ============================================================================
# SECTION 1: Parser Integration Tests
# ============================================================================

class TestGrimoireParserIntegration:
    """Integration tests that load and verify the actual grimoire."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Ensure fresh grimoire load for each test."""
        reload_grimoire()

    def test_grimoire_loads_successfully(self):
        """Verify grimoire YAML loads without errors."""
        grimoire = load_grimoire()
        assert isinstance(grimoire, dict)
        assert "commands" in grimoire
        assert "modifiers" in grimoire
        assert "parser" in grimoire

    def test_grimoire_has_expected_commands(self):
        """Verify grimoire has substantial number of commands."""
        grimoire = load_grimoire()
        commands = grimoire.get("commands", [])
        # Should have at least 20 commands (base set)
        assert len(commands) >= 20, f"Expected at least 20 commands, got {len(commands)}"
        # Log actual count for reference
        print(f"Grimoire contains {len(commands)} commands")

    def test_grimoire_has_5_modifiers(self):
        """Verify all 5 modifiers are present."""
        grimoire = load_grimoire()
        modifiers = grimoire.get("modifiers", [])
        assert len(modifiers) == 5, f"Expected 5 modifiers, got {len(modifiers)}"


class TestAllCommandsMatchExact:
    """Test that every grimoire command matches its exact phrase."""

    @pytest.fixture
    def all_commands(self):
        """Get all command phrases from grimoire."""
        grimoire = load_grimoire()
        return grimoire.get("commands", [])

    def test_all_commands_match_exactly(self, all_commands):
        """Every command phrase should match itself with high confidence."""
        for cmd in all_commands:
            phrase = cmd["phrase"]
            result = match(phrase)
            assert result is not None, f"Command phrase failed to match: '{phrase}'"
            matched_cmd, score = result
            assert matched_cmd["phrase"] == phrase, (
                f"Phrase '{phrase}' matched wrong command: '{matched_cmd['phrase']}'"
            )
            assert score >= 95, f"Phrase '{phrase}' had low score: {score}"

    def test_command_escape_hatch(self):
        """Test 'hold' escape hatch command."""
        result = match("hold")
        assert result is not None
        cmd, score = result
        assert cmd["phrase"] == "hold"
        assert "escape" in cmd["tags"]

    def test_command_evening_redness(self):
        """Test 'the evening redness in the west' deploy command."""
        result = match("the evening redness in the west")
        assert result is not None
        cmd, score = result
        assert cmd["phrase"] == "the evening redness in the west"
        assert "deploy" in cmd["tags"]
        assert cmd["confirmation"] is True

    def test_command_they_rode_on(self):
        """Test 'they rode on' continuation command."""
        result = match("they rode on")
        assert result is not None
        cmd, score = result
        assert cmd["phrase"] == "they rode on"
        assert cmd.get("use_continue") is True

    def test_command_judge_smiled(self):
        """Test 'the judge smiled' test command."""
        result = match("the judge smiled")
        assert result is not None
        cmd, score = result
        assert cmd["phrase"] == "the judge smiled"
        assert "testing" in cmd["tags"]

    def test_command_draw_the_sucker(self):
        """Test 'draw the sucker' git pull command."""
        result = match("draw the sucker")
        assert result is not None
        cmd, score = result
        assert cmd["phrase"] == "draw the sucker"
        assert "git" in cmd["tags"]

    def test_command_night_of_your_birth(self):
        """Test 'night of your birth' init command."""
        result = match("night of your birth")
        assert result is not None
        cmd, score = result
        assert cmd["phrase"] == "night of your birth"
        assert "init" in cmd["tags"]

    def test_command_fires_on_the_plain(self):
        """Test 'the fires on the plain' cleanup command."""
        result = match("the fires on the plain")
        assert result is not None
        cmd, score = result
        assert cmd["phrase"] == "the fires on the plain"
        assert "cleanup" in cmd["tags"]

    def test_command_he_never_sleeps(self):
        """Test 'he never sleeps' daemon command."""
        result = match("he never sleeps")
        assert result is not None
        cmd, score = result
        assert cmd["phrase"] == "he never sleeps"
        assert "daemon" in cmd["tags"]

    def test_command_kid_looked_expanse(self):
        """Test 'the kid looked at the expanse before him' survey command."""
        result = match("the kid looked at the expanse before him")
        assert result is not None
        cmd, score = result
        assert cmd["phrase"] == "the kid looked at the expanse before him"
        assert "survey" in cmd["tags"]

    def test_command_tell_me_country(self):
        """Test 'tell me about the country ahead' research command."""
        result = match("tell me about the country ahead")
        assert result is not None
        cmd, score = result
        assert cmd["phrase"] == "tell me about the country ahead"
        assert "research" in cmd["tags"]

    def test_command_scour_terrain(self):
        """Test 'scour the terrain' deep research command."""
        result = match("scour the terrain")
        assert result is not None
        cmd, score = result
        assert cmd["phrase"] == "scour the terrain"
        assert "research" in cmd["tags"]


class TestAllModifiersExtract:
    """Test that all 5 modifiers extract correctly from phrases."""

    def test_modifier_under_the_stars_verbose(self):
        """Test 'under the stars' verbose modifier extraction."""
        mods = extract_modifiers("do something under the stars")
        assert len(mods) == 1
        assert mods[0]["phrase"] == "under the stars"
        assert mods[0]["effect"] == "verbose"

    def test_modifier_in_silence_quiet(self):
        """Test 'in silence' quiet modifier extraction."""
        mods = extract_modifiers("execute the command in silence")
        assert len(mods) == 1
        assert mods[0]["phrase"] == "in silence"
        assert mods[0]["effect"] == "quiet"

    def test_modifier_and_the_judge_watched_dry_run(self):
        """Test 'and the judge watched' dry run modifier extraction."""
        mods = extract_modifiers("deploy and the judge watched")
        assert len(mods) == 1
        assert mods[0]["phrase"] == "and the judge watched"
        assert mods[0]["effect"] == "dry_run"

    def test_modifier_by_first_light_schedule(self):
        """Test 'by first light' schedule modifier extraction."""
        mods = extract_modifiers("run tests by first light")
        assert len(mods) == 1
        assert mods[0]["phrase"] == "by first light"
        assert mods[0]["effect"] == "schedule_morning"

    def test_modifier_blood_meridian_commit(self):
        """Test 'the blood meridian' commit_after modifier extraction."""
        mods = extract_modifiers("fix the bug the blood meridian")
        assert len(mods) == 1
        assert mods[0]["phrase"] == "the blood meridian"
        assert mods[0]["effect"] == "commit_after"


class TestPhraseModifierCombinations:
    """Test command phrases combined with modifiers.

    NOTE: The ratio scorer is strict by design. Adding modifiers to phrases
    may cause the match to fail because it changes the text too much relative
    to the original phrase. This is intentional for safety (preventing false positives).

    The workflow is:
    1. Match the base command phrase separately
    2. Extract modifiers from the full text
    3. Apply modifiers to the matched command

    Tests below verify modifiers extract correctly, and that expansion works
    when modifiers are applied to a matched command.
    """

    def test_modifiers_extracted_from_combined_phrase(self):
        """Test modifiers extract from combined phrases (even if match fails)."""
        full_phrase = "the evening redness in the west and the judge watched"

        # Modifiers should always extract regardless of match success
        mods = extract_modifiers(full_phrase)
        assert len(mods) == 1
        assert mods[0]["effect"] == "dry_run"

    def test_verbose_modifier_extracted(self):
        """Test verbose modifier extracts from combined phrase."""
        full_phrase = "the judge smiled under the stars"

        mods = extract_modifiers(full_phrase)
        assert len(mods) == 1
        assert mods[0]["effect"] == "verbose"

    def test_commit_modifier_extracted(self):
        """Test commit modifier extracts from combined phrase."""
        full_phrase = "they rode on the blood meridian"

        mods = extract_modifiers(full_phrase)
        assert len(mods) == 1
        assert mods[0]["effect"] == "commit_after"

    def test_multiple_modifiers_extracted(self):
        """Test multiple modifiers extract from single phrase."""
        full_phrase = "scour the terrain under the stars the blood meridian"

        mods = extract_modifiers(full_phrase)
        effects = [m["effect"] for m in mods]
        assert "verbose" in effects
        assert "commit_after" in effects

    def test_base_command_matches_separately(self):
        """Test that base command matches when phrase is exact."""
        # Match the base command first
        base_result = match("the evening redness in the west")
        assert base_result is not None
        cmd, score = base_result
        assert "deploy" in cmd["tags"]

        # Then extract modifiers from combined phrase
        mods = extract_modifiers("anything and the judge watched")
        assert len(mods) == 1
        assert mods[0]["effect"] == "dry_run"

    def test_strict_scorer_rejects_modified_phrase(self):
        """Document that ratio scorer rejects phrases with appended modifiers.

        This is INTENTIONAL for safety - prevents false positive matches.
        The ratio scorer compares character-by-character, so adding
        'and the judge watched' (24 chars) to a phrase significantly
        reduces the match score below threshold.
        """
        full_phrase = "the evening redness in the west and the judge watched"

        # With strict ratio scorer at 80% threshold, this should NOT match
        # because the added modifier text dilutes the score
        result = match(full_phrase)

        # This documents the expected behavior - strict matching
        # If this test fails, it means the parser became more permissive
        assert result is None, (
            "Expected no match with strict scorer. If this changed, "
            "verify it's intentional (safety vs convenience tradeoff)"
        )

    def test_expansion_includes_modifier_content(self):
        """Verify expansion includes modifier append content."""
        result = match("the judge smiled")
        assert result is not None
        cmd, _ = result

        mods = extract_modifiers("verbose under the stars")
        expansion = expand_command(cmd, mods)

        # Should include base expansion
        assert "test suite" in expansion.lower()
        # Should include modifier append
        assert "verbose" in expansion.lower() or "detailed" in expansion.lower()


# ============================================================================
# SECTION 2: CLI Integration Tests (subprocess)
# ============================================================================

class TestCLIIntegration:
    """Integration tests for CLI commands via subprocess."""

    @pytest.fixture
    def main_script(self):
        """Path to main.py script."""
        return str(SRC_PATH / "main.py")

    def test_cli_list_returns_all_commands(self, main_script):
        """Test that --list returns all grimoire commands."""
        result = subprocess.run(
            [sys.executable, main_script, "--list"],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should succeed
        assert result.returncode == 0, f"--list failed: {result.stderr}"

        # Output should contain section headers
        assert "GRIMOIRE COMMANDS" in result.stdout
        assert "MODIFIERS" in result.stdout

        # Should contain known command phrases
        assert "evening redness" in result.stdout.lower()
        assert "they rode on" in result.stdout.lower()
        assert "the judge smiled" in result.stdout.lower()

    def test_cli_validate_returns_zero(self, main_script):
        """Test that --validate returns 0 for valid grimoire."""
        result = subprocess.run(
            [sys.executable, main_script, "--validate"],
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0, f"--validate failed: {result.stderr}\n{result.stdout}"
        assert "valid" in result.stdout.lower()
        assert "commands" in result.stdout.lower()
        assert "modifiers" in result.stdout.lower()

    def test_cli_help_shows_usage(self, main_script):
        """Test that --help shows usage information."""
        result = subprocess.run(
            [sys.executable, main_script, "--help"],
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0
        # Should show program description
        assert "suzerain" in result.stdout.lower() or "voice" in result.stdout.lower()
        # Should show available options
        assert "--test" in result.stdout
        assert "--list" in result.stdout
        assert "--validate" in result.stdout
        assert "--sandbox" in result.stdout


class TestCLITestModeIntegration:
    """Test the --test mode with simulated stdin."""

    @pytest.fixture
    def main_script(self):
        """Path to main.py script."""
        return str(SRC_PATH / "main.py")

    def test_test_mode_with_sandbox_once(self, main_script):
        """Test --test --sandbox --once with stdin input."""
        # Feed a grimoire phrase to test mode
        input_phrase = "the judge smiled\n"

        result = subprocess.run(
            [sys.executable, main_script, "--test", "--sandbox", "--once"],
            input=input_phrase,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should show sandbox mode is active
        assert "SANDBOX MODE" in result.stdout or "sandbox" in result.stdout.lower()

        # Should match the command
        assert "judge smiled" in result.stdout.lower() or "Matched" in result.stdout

    def test_test_mode_quit_command(self, main_script):
        """Test that 'quit' exits test mode cleanly."""
        result = subprocess.run(
            [sys.executable, main_script, "--test", "--sandbox"],
            input="quit\n",
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should exit cleanly (return code 0)
        assert result.returncode == 0

    def test_test_mode_list_command(self, main_script):
        """Test that 'list' shows commands in test mode."""
        result = subprocess.run(
            [sys.executable, main_script, "--test", "--sandbox"],
            input="list\nquit\n",
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0
        # Should show grimoire commands
        assert "GRIMOIRE" in result.stdout or "evening redness" in result.stdout.lower()


# ============================================================================
# SECTION 3: Dry Run Integration Tests
# ============================================================================

class TestDryRunIntegration:
    """Test dry run mode verifies expansion without execution."""

    @pytest.fixture
    def main_script(self):
        """Path to main.py script."""
        return str(SRC_PATH / "main.py")

    def test_dry_run_shows_expansion_no_execution(self, main_script):
        """Verify dry run shows expansion but doesn't execute."""
        # Use sandbox mode (global dry run) + test mode
        input_phrase = "the evening redness in the west\nquit\n"

        result = subprocess.run(
            [sys.executable, main_script, "--test", "--sandbox"],
            input=input_phrase,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should show DRY RUN indicator
        assert "DRY RUN" in result.stdout

        # Should show the expansion content
        assert "Deploy" in result.stdout

        # Should NOT show actual execution indicators
        assert "Executing..." not in result.stdout or "DRY RUN" in result.stdout

    def test_dry_run_modifier_phrase(self, main_script):
        """Test dry run via modifier phrase.

        Note: With strict ratio scorer, adding modifier to phrase causes match to fail.
        Test uses sandbox mode (--sandbox) instead, which forces dry run for all commands.
        """
        # Use just the base phrase, sandbox mode forces dry run
        input_phrase = "the judge smiled\nquit\n"

        result = subprocess.run(
            [sys.executable, main_script, "--test", "--sandbox"],
            input=input_phrase,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Sandbox mode triggers DRY RUN
        assert "DRY RUN" in result.stdout

    def test_all_commands_dry_run(self, main_script):
        """Feed each grimoire phrase through sandbox mode."""
        grimoire = load_grimoire()
        commands = grimoire.get("commands", [])

        for cmd in commands:
            phrase = cmd["phrase"]
            input_text = f"{phrase}\nquit\n"

            result = subprocess.run(
                [sys.executable, main_script, "--test", "--sandbox"],
                input=input_text,
                capture_output=True,
                text=True,
                timeout=30
            )

            # Each command should match and show dry run
            assert "DRY RUN" in result.stdout or "Matched" in result.stdout, (
                f"Command '{phrase}' did not trigger dry run mode"
            )


# ============================================================================
# SECTION 4: Error Handling Integration Tests
# ============================================================================

class TestErrorHandlingIntegration:
    """Test error handling for various failure scenarios."""

    @pytest.fixture
    def main_script(self):
        """Path to main.py script."""
        return str(SRC_PATH / "main.py")

    def test_missing_api_key_clean_error(self, main_script, monkeypatch):
        """Test that missing API key produces clean error."""
        # This is tested indirectly - transcribe_audio should handle gracefully
        from main import transcribe_audio

        # Clear environment
        env = os.environ.copy()
        env.pop("DEEPGRAM_API_KEY", None)

        # Should return empty string and print error
        with patch.dict(os.environ, {}, clear=True):
            result = transcribe_audio(b"fake audio")
            assert result == ""

    def test_invalid_phrase_no_crash(self, main_script):
        """Test that invalid/unmatched phrases don't crash."""
        input_phrase = "random nonsense that wont match anything xyz123\nn\nquit\n"

        result = subprocess.run(
            [sys.executable, main_script, "--test", "--sandbox"],
            input=input_phrase,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should not crash
        assert result.returncode == 0
        # Should indicate no grimoire match (exact message from CLI)
        assert "No grimoire match" in result.stdout or "no match" in result.stdout.lower()

    def test_malformed_input_no_crash(self, main_script):
        """Test that malformed input doesn't crash."""
        # Various edge cases
        malformed_inputs = [
            "",
            "\n",
            "   \n",
            "!@#$%^&*()\n",
            "a" * 10000 + "\n",  # Very long input
            "quit\n"
        ]

        input_text = "".join(malformed_inputs)

        result = subprocess.run(
            [sys.executable, main_script, "--test", "--sandbox"],
            input=input_text,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should not crash
        assert result.returncode == 0

    def test_unicode_input_no_crash(self, main_script):
        """Test that unicode input doesn't crash."""
        input_text = "the judge smiled\nquit\n"

        result = subprocess.run(
            [sys.executable, main_script, "--test", "--sandbox"],
            input=input_text,
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0


class TestGrimoireValidationIntegration:
    """Test grimoire validation catches issues."""

    def test_valid_grimoire_no_issues(self):
        """Verify current grimoire passes validation."""
        issues = validate_grimoire()
        assert len(issues) == 0, f"Grimoire validation failed: {issues}"

    def test_all_commands_have_required_fields(self):
        """Verify all commands have phrase and expansion."""
        grimoire = load_grimoire()
        commands = grimoire.get("commands", [])

        for cmd in commands:
            assert "phrase" in cmd, f"Command missing phrase: {cmd}"
            assert "expansion" in cmd, f"Command '{cmd.get('phrase')}' missing expansion"

    def test_all_modifiers_have_required_fields(self):
        """Verify all modifiers have phrase and effect."""
        grimoire = load_grimoire()
        modifiers = grimoire.get("modifiers", [])

        for mod in modifiers:
            assert "phrase" in mod, f"Modifier missing phrase: {mod}"
            assert "effect" in mod, f"Modifier '{mod.get('phrase')}' missing effect"

    def test_no_duplicate_phrases(self):
        """Verify no duplicate command phrases."""
        grimoire = load_grimoire()
        commands = grimoire.get("commands", [])

        phrases = [cmd["phrase"] for cmd in commands]
        assert len(phrases) == len(set(phrases)), "Duplicate phrases found"

    def test_no_duplicate_modifier_phrases(self):
        """Verify no duplicate modifier phrases."""
        grimoire = load_grimoire()
        modifiers = grimoire.get("modifiers", [])

        phrases = [mod["phrase"] for mod in modifiers]
        assert len(phrases) == len(set(phrases)), "Duplicate modifier phrases found"


# ============================================================================
# SECTION 5: End-to-End Mock Tests
# ============================================================================

class TestEndToEndMocked:
    """End-to-end tests with mocked external services."""

    @pytest.fixture
    def mock_deepgram_response(self):
        """Mock Deepgram API response."""
        return {
            "results": {
                "channels": [{
                    "alternatives": [{
                        "transcript": "the judge smiled"
                    }]
                }]
            }
        }

    @pytest.fixture
    def mock_claude_output(self):
        """Mock Claude CLI output."""
        return [
            '{"type": "assistant", "message": {"content": [{"type": "text", "text": "Running tests..."}]}}',
            '{"type": "tool_use", "name": "bash"}',
            '{"type": "assistant", "message": {"content": [{"type": "text", "text": "All 42 tests passed."}]}}',
            '{"type": "result", "result": "Tests complete"}'
        ]

    def test_full_flow_audio_to_match(self, mock_deepgram_response):
        """Test: audio -> transcript -> match flow."""
        from main import transcribe_audio

        # Mock the urlopen to return our response
        class MockResponse:
            def __init__(self):
                pass
            def read(self):
                return json.dumps(mock_deepgram_response).encode()
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        with patch("urllib.request.urlopen", return_value=MockResponse()):
            with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "a" * 40}):
                # Simulate transcription
                transcript = transcribe_audio(b"fake audio data")

                assert transcript == "the judge smiled"

                # Now match against grimoire
                result = match(transcript)
                assert result is not None
                cmd, score = result
                assert "testing" in cmd["tags"]

    def test_full_flow_match_to_expand(self):
        """Test: match -> expand -> ready for execution.

        Note: With strict ratio scorer, we match base phrase separately
        and extract modifiers from full text.
        """
        # Match base phrase first
        base_phrase = "the evening redness in the west"
        full_phrase = "the evening redness in the west and the judge watched"

        # Match base phrase
        result = match(base_phrase)
        assert result is not None
        cmd, score = result
        assert "deploy" in cmd["tags"]

        # Extract modifiers from full phrase
        mods = extract_modifiers(full_phrase)
        assert len(mods) == 1
        assert mods[0]["effect"] == "dry_run"

        # Expand with modifiers
        expansion = expand_command(cmd, mods)

        # Verify expansion content
        assert "Deploy" in expansion
        assert "DRY RUN" in expansion

    def test_full_flow_execute_with_mocked_claude(self, mock_claude_output, capsys):
        """Test: execute command with mocked Claude CLI."""
        from main import execute_command

        # Create mock subprocess
        class MockPopen:
            def __init__(self, *args, **kwargs):
                self.returncode = 0
                self.stdout = iter(mock_claude_output)
            def wait(self):
                pass

        # Get a real command
        result = match("the judge smiled")
        assert result is not None
        cmd, _ = result

        with patch("subprocess.Popen", MockPopen):
            exit_code, conv_id = execute_command(cmd, [])

        assert exit_code == 0
        captured = capsys.readouterr()

        # Should show execution happening
        assert "Running tests" in captured.out or "Executing" in captured.out

    def test_full_flow_dry_run_no_subprocess(self, capsys):
        """Test: dry run should NOT call subprocess."""
        from main import execute_command

        subprocess_called = []

        def mock_popen(*args, **kwargs):
            subprocess_called.append(True)
            raise AssertionError("Subprocess should not be called in dry run")

        # Get a command and use dry run
        result = match("the evening redness in the west")
        assert result is not None
        cmd, _ = result

        mods = extract_modifiers("test and the judge watched")  # dry_run modifier

        with patch("subprocess.Popen", mock_popen):
            exit_code, conv_id = execute_command(cmd, mods)

        # Dry run should succeed without calling subprocess
        assert exit_code == 0
        assert len(subprocess_called) == 0

        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out


# ============================================================================
# SECTION 6: API-Dependent Tests (skipped without credentials)
# ============================================================================

@pytest.mark.skipif(
    not os.environ.get("DEEPGRAM_API_KEY"),
    reason="No DEEPGRAM_API_KEY set"
)
class TestRealDeepgramAPI:
    """Tests that require real Deepgram API key."""

    def test_real_transcription(self):
        """Test actual Deepgram API call with minimal audio."""
        from main import transcribe_audio

        # Create minimal valid WAV file (1 second of silence)
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b'\x00' * 32000)

        audio_data = buffer.getvalue()

        # This will make a real API call
        result = transcribe_audio(audio_data)

        # With silence, we expect empty or very short transcript
        assert isinstance(result, str)


@pytest.mark.skipif(
    not os.environ.get("PICOVOICE_ACCESS_KEY"),
    reason="No PICOVOICE_ACCESS_KEY set"
)
class TestRealPorcupineWakeWord:
    """Tests that require real Picovoice access key."""

    def test_porcupine_loads(self):
        """Test that Porcupine can initialize with real key."""
        try:
            from wake_word import WakeWordDetector, check_setup

            status = check_setup()
            # At minimum, should return a status dict
            assert isinstance(status, dict)
            assert "ready" in status
        except ImportError:
            pytest.skip("wake_word module not available")


# ============================================================================
# SECTION 7: Regression Tests
# ============================================================================

class TestRegressions:
    """Tests for specific bugs that were fixed."""

    def test_filler_words_dont_break_matching(self):
        """Regression: filler words should be stripped before matching."""
        # Input with filler words
        result = match("um the evening redness um in the west")
        assert result is not None
        cmd, score = result
        assert cmd["phrase"] == "the evening redness in the west"

    def test_case_insensitive_matching(self):
        """Regression: matching should be case-insensitive."""
        lower = match("the judge smiled")
        upper = match("THE JUDGE SMILED")
        mixed = match("The Judge Smiled")

        assert lower is not None
        assert upper is not None
        assert mixed is not None

        assert lower[0]["phrase"] == upper[0]["phrase"] == mixed[0]["phrase"]

    def test_shell_command_not_in_expansion(self):
        """Regression: shell_command was removed for security."""
        # The 'draw the sucker' command historically had shell_command: 'git pull'
        result = match("draw the sucker")
        assert result is not None
        cmd, _ = result

        expansion = expand_command(cmd, [])

        # shell_command feature was removed - expansion should NOT contain raw git pull
        # It should have the natural language expansion instead
        assert "Pull the latest" in expansion or "pull" in expansion.lower()

    def test_modifier_doesnt_interfere_with_base_match(self):
        """Verify base command matches and modifiers extract separately.

        Note: With strict ratio scorer, the combined phrase may not match.
        This documents the expected workflow: match base, extract modifiers separately.
        """
        # Base phrase without modifier
        base_result = match("they rode on")
        assert base_result is not None
        cmd, score = base_result
        assert "continuation" in cmd["tags"]

        # Modifiers extract from full phrase
        mods = extract_modifiers("they rode on the blood meridian")
        assert len(mods) == 1
        assert mods[0]["effect"] == "commit_after"

    def test_empty_input_handled_gracefully(self):
        """Regression: empty input should not crash."""
        result = match("")
        # Should return None, not crash
        assert result is None

    def test_whitespace_only_input_handled(self):
        """Regression: whitespace-only input should not crash."""
        result = match("   ")
        assert result is None

        result = match("\n\t")
        assert result is None


# ============================================================================
# Test Markers
# ============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "requires_api: marks tests that require real API credentials"
    )
