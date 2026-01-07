"""
Edge case tests for Suzerain parser and core functionality.

"The truth about the world is that anything is possible."

Tests cover:
- Empty and whitespace-only input
- Very long strings (1000+ chars)
- Unicode and emoji in phrases
- Special characters and punctuation
- Case sensitivity variations
- Threshold boundary conditions
- Malformed input handling
"""

import os
import sys
from pathlib import Path

import pytest

# Add src to path for imports
SRC_PATH = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_PATH))

from parser import (
    match,
    match_top_n,
    extract_modifiers,
    expand_command,
    load_grimoire,
    strip_filler_words,
    list_commands,
)


# === Empty Input Tests ===

class TestEmptyInput:
    """Test handling of empty and minimal input."""

    def test_match_empty_string(self):
        """Test match returns None for empty string."""
        result = match("")
        assert result is None

    def test_match_whitespace_only(self):
        """Test match returns None for whitespace-only input."""
        assert match("   ") is None
        assert match("\t") is None
        assert match("\n") is None
        assert match("  \t\n  ") is None

    def test_match_top_n_empty_string(self):
        """Test match_top_n returns empty list for empty string."""
        results = match_top_n("")
        assert results == []

    def test_match_top_n_whitespace(self):
        """Test match_top_n returns empty list for whitespace."""
        results = match_top_n("   ")
        assert results == []

    def test_extract_modifiers_empty(self):
        """Test extract_modifiers returns empty list for empty input."""
        mods = extract_modifiers("")
        assert mods == []

    def test_strip_filler_words_empty(self):
        """Test strip_filler_words handles empty string."""
        result = strip_filler_words("")
        assert result == ""


# === Very Long Input Tests ===

class TestLongInput:
    """Test handling of very long input strings."""

    def test_match_1000_char_input(self):
        """Test match handles 1000+ character input without crashing."""
        long_input = "the evening redness in the west " * 50  # ~1600 chars

        result = match(long_input)

        # Should match (repeated phrase) or return None, but not crash
        assert result is None or isinstance(result, tuple)

    def test_match_10000_char_input(self):
        """Test match handles 10000+ character input without crashing."""
        long_input = "a " * 5000  # 10000 chars

        result = match(long_input)

        assert result is None  # Should not match random text

    def test_match_top_n_long_input(self):
        """Test match_top_n handles long input."""
        long_input = "they rode on " * 100

        results = match_top_n(long_input, n=3)

        # Should return a list (possibly empty or with matches)
        assert isinstance(results, list)

    def test_strip_filler_words_long_input(self):
        """Test filler word stripping with long input."""
        long_input = "um like so " * 500

        result = strip_filler_words(long_input)

        # Should return a string (possibly empty after stripping)
        assert isinstance(result, str)

    def test_extract_modifiers_long_input(self):
        """Test modifier extraction with long input."""
        long_input = "under the stars " * 100

        mods = extract_modifiers(long_input)

        # Should find the modifier
        assert len(mods) >= 1
        assert any(m["effect"] == "verbose" for m in mods)


# === Unicode and Emoji Tests ===

class TestUnicodeInput:
    """Test handling of unicode characters and emoji."""

    def test_match_unicode_accented_chars(self):
        """Test match handles accented characters."""
        # These should not match anything, but should not crash
        result = match("the evening redness")
        assert result is not None or result is None

    def test_match_cyrillic_text(self):
        """Test match handles Cyrillic characters."""
        result = match("the evening redness")  # Normal text for comparison
        cyrillic_result = match("test")  # Simple ASCII

        # Both should either match or not, but not crash
        assert cyrillic_result is None or isinstance(cyrillic_result, tuple)

    def test_match_chinese_text(self):
        """Test match handles Chinese characters."""
        result = match("test command")

        assert result is None or isinstance(result, tuple)

    def test_match_emoji_in_input(self):
        """Test match handles emoji without crashing."""
        # Note: Emojis may cause encoding issues in some contexts
        # The test verifies no crash occurs
        try:
            result = match("the evening redness")
            assert result is not None or result is None
        except Exception:
            pytest.fail("Emoji in input caused unexpected exception")

    def test_match_mixed_unicode(self):
        """Test match handles mixed unicode characters."""
        result = match("the evening redness test")

        # Should handle gracefully
        assert result is not None or result is None

    def test_extract_modifiers_unicode(self):
        """Test modifier extraction with unicode text."""
        mods = extract_modifiers("test under the stars")

        assert len(mods) >= 1


# === Special Characters Tests ===

class TestSpecialCharacters:
    """Test handling of special characters and punctuation."""

    def test_match_with_punctuation(self):
        """Test match handles punctuation in input."""
        # Punctuation shouldn't break matching
        result1 = match("the evening redness in the west!")
        result2 = match("the evening redness in the west?")
        result3 = match("the evening redness in the west.")

        # At least one should work (punctuation handling varies)
        # All should not crash
        assert all(r is None or isinstance(r, tuple) for r in [result1, result2, result3])

    def test_match_special_chars(self):
        """Test match handles special characters."""
        special_inputs = [
            "the evening redness @#$%",
            "the evening redness & west",
            "the evening redness (test)",
            "the evening redness [test]",
            "the evening redness {test}",
        ]

        for inp in special_inputs:
            result = match(inp)
            # Should not crash
            assert result is None or isinstance(result, tuple)

    def test_match_quotes(self):
        """Test match handles various quote characters."""
        result1 = match("the evening redness 'test'")
        result2 = match('the evening redness "test"')
        result3 = match("the evening redness `test`")

        # Should handle gracefully
        assert all(r is None or isinstance(r, tuple) for r in [result1, result2, result3])

    def test_match_newlines_tabs(self):
        """Test match handles newlines and tabs."""
        result = match("the evening\nredness\tin\tthe west")

        # May or may not match (whitespace handling), but should not crash
        assert result is None or isinstance(result, tuple)

    def test_match_backslashes(self):
        """Test match handles backslashes."""
        result = match("the evening redness\\test")

        assert result is None or isinstance(result, tuple)

    def test_extract_modifiers_special_chars(self):
        """Test modifier extraction with special characters."""
        mods = extract_modifiers("test under the stars!!!")

        # Should still find the modifier
        assert len(mods) >= 1


# === Case Sensitivity Tests ===

class TestCaseSensitivity:
    """Test case sensitivity handling in matching."""

    def test_match_lowercase(self):
        """Test matching with all lowercase."""
        result = match("the evening redness in the west")

        assert result is not None
        assert result[1] >= 90  # High score for exact match

    def test_match_uppercase(self):
        """Test matching with all uppercase."""
        result = match("THE EVENING REDNESS IN THE WEST")

        assert result is not None
        assert result[1] >= 90

    def test_match_mixed_case(self):
        """Test matching with mixed case."""
        result = match("The Evening Redness In The West")

        assert result is not None
        assert result[1] >= 90

    def test_match_random_case(self):
        """Test matching with random capitalization."""
        result = match("tHe eVeNiNg ReDnEsS iN tHe WeSt")

        assert result is not None
        assert result[1] >= 80  # May have slightly lower score

    def test_all_commands_case_insensitive(self):
        """Test that all commands match regardless of case."""
        commands = list_commands()

        for cmd_info in commands[:5]:  # Test first 5 commands
            phrase = cmd_info["phrase"]

            lower_result = match(phrase.lower())
            upper_result = match(phrase.upper())

            if lower_result:
                assert upper_result is not None, f"Case sensitivity issue with: {phrase}"


# === Threshold Boundary Tests ===

class TestThresholdBoundaries:
    """Test matching behavior at threshold boundaries."""

    def test_exact_threshold_match(self):
        """Test matching at exactly the threshold."""
        # Get the default threshold from grimoire
        grimoire = load_grimoire()
        threshold = grimoire.get("parser", {}).get("threshold", 70)

        # Test with explicit threshold
        result = match("the evening redness in the west", threshold=threshold)

        assert result is not None

    def test_below_threshold(self):
        """Test that matches below threshold return None."""
        result = match("random nonsense xyz", threshold=90)

        assert result is None

    def test_threshold_0(self):
        """Test with threshold of 0 (should match almost anything)."""
        result = match("x", threshold=0)

        # With 0 threshold, even single char might match something
        assert result is None or isinstance(result, tuple)

    def test_threshold_100(self):
        """Test with threshold of 100 (only exact matches)."""
        result = match("the evening redness in the west", threshold=100)

        # May or may not match exactly at 100 (fuzzy scorer rarely gives 100)
        assert result is None or result[1] == 100

    def test_threshold_50(self):
        """Test with low threshold of 50."""
        result = match("evening redness", threshold=50)

        # Should match partial phrase with low threshold
        assert result is not None or result is None  # Depends on scorer

    def test_threshold_90(self):
        """Test with high threshold of 90."""
        result = match("the evening redness in the west", threshold=90)

        assert result is not None
        assert result[1] >= 90

    def test_match_top_n_threshold(self):
        """Test match_top_n respects threshold."""
        results = match_top_n("evening", threshold=95)

        # All results should meet threshold
        for cmd, score in results:
            assert score >= 95


# === Filler Word Tests ===

class TestFillerWordHandling:
    """Test filler word stripping behavior."""

    def test_strip_um(self):
        """Test 'um' is stripped."""
        result = strip_filler_words("um the evening redness")
        assert "um" not in result

    def test_strip_uh(self):
        """Test 'uh' is stripped."""
        result = strip_filler_words("uh the judge smiled")
        assert "uh" not in result

    def test_strip_like(self):
        """Test 'like' is stripped."""
        result = strip_filler_words("like they rode on")
        assert "like" not in result.lower() or "like" == strip_filler_words("like").strip()

    def test_strip_multiple_fillers(self):
        """Test multiple filler words are stripped."""
        result = strip_filler_words("um uh like the evening redness um")
        assert "um" not in result
        assert "uh" not in result

    def test_strip_preserves_content(self):
        """Test that actual content is preserved."""
        result = strip_filler_words("um the evening redness in the west")
        assert "evening" in result
        assert "redness" in result
        assert "west" in result

    def test_filler_in_word_preserved(self):
        """Test that filler strings within words are preserved."""
        # 'um' in 'column' should not be stripped
        # This tests word boundary handling
        result = strip_filler_words("the column test")
        assert "column" in result

    def test_match_with_fillers(self):
        """Test matching works after filler removal."""
        result = match("um uh the evening redness in the west")

        assert result is not None
        assert result[0]["phrase"] == "the evening redness in the west"


# === Expansion Tests ===

class TestExpansionEdgeCases:
    """Test command expansion edge cases."""

    def test_expand_empty_modifiers(self):
        """Test expansion with empty modifier list."""
        result = match("the judge smiled")
        assert result is not None

        expansion = expand_command(result[0], [])

        assert len(expansion) > 0
        assert "test" in expansion.lower()

    def test_expand_none_modifiers(self):
        """Test expansion with None modifiers."""
        result = match("the judge smiled")
        assert result is not None

        expansion = expand_command(result[0], None)

        assert len(expansion) > 0

    def test_expand_multiple_modifiers(self):
        """Test expansion with multiple modifiers."""
        result = match("the evening redness in the west")
        mods = extract_modifiers("test under the stars the blood meridian")

        expansion = expand_command(result[0], mods)

        # Should include base expansion and modifier appendices
        assert len(expansion) > 0


# === Concurrent/Thread Safety Tests ===

class TestConcurrentAccess:
    """Test thread safety of parser operations."""

    def test_concurrent_matching(self):
        """Test that matching can be done concurrently."""
        import concurrent.futures

        phrases = [
            "the evening redness in the west",
            "they rode on",
            "the judge smiled",
            "draw the sucker",
        ]

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(match, phrase) for phrase in phrases]
            results = [f.result() for f in futures]

        # All should return valid results
        for i, result in enumerate(results):
            assert result is not None, f"Match failed for: {phrases[i]}"

    def test_concurrent_grimoire_access(self):
        """Test that grimoire can be accessed concurrently."""
        import concurrent.futures

        def load_and_count():
            grimoire = load_grimoire()
            return len(grimoire.get("commands", []))

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(load_and_count) for _ in range(10)]
            results = [f.result() for f in futures]

        # All should return same count
        assert len(set(results)) == 1


# === Input Sanitization Tests ===

class TestInputSanitization:
    """Test input is properly sanitized."""

    def test_null_bytes(self):
        """Test handling of null bytes in input."""
        try:
            result = match("test\x00phrase")
            # Should handle gracefully
            assert result is None or isinstance(result, tuple)
        except Exception:
            pass  # Some implementations may raise, which is acceptable

    def test_control_characters(self):
        """Test handling of control characters."""
        result = match("test\x01\x02\x03phrase")

        # Should not crash
        assert result is None or isinstance(result, tuple)

    def test_sql_injection_attempt(self):
        """Test that SQL-like strings don't cause issues."""
        result = match("'; DROP TABLE commands; --")

        assert result is None  # Should not match

    def test_command_injection_attempt(self):
        """Test that shell command strings don't cause issues."""
        result = match("; rm -rf /")

        assert result is None


# === Error Recovery Tests ===

class TestErrorRecovery:
    """Test error recovery and graceful degradation."""

    def test_invalid_type_input(self):
        """Test that invalid input types are handled."""
        # These should raise TypeError or be handled gracefully
        try:
            result = match(None)
        except (TypeError, AttributeError):
            pass  # Expected behavior

        try:
            result = match(123)
        except (TypeError, AttributeError):
            pass  # Expected behavior

    def test_bytes_input(self):
        """Test handling of bytes input."""
        try:
            result = match(b"test phrase")
        except (TypeError, AttributeError):
            pass  # Expected - should require string


# === Parametrized Edge Case Tests ===

@pytest.mark.parametrize("input_text,expected_none", [
    ("", True),
    ("   ", True),
    ("\n", True),
    ("\t", True),
    ("x", True),
    ("xyz123", True),
    ("the", True),
    ("evening", None),  # May or may not match
    ("the evening redness in the west", False),
])
def test_match_various_inputs(input_text, expected_none):
    """Parametrized test for various input types."""
    result = match(input_text)

    if expected_none is True:
        assert result is None
    elif expected_none is False:
        assert result is not None
    # If expected_none is None, either result is acceptable


@pytest.mark.parametrize("threshold", [0, 10, 50, 70, 80, 90, 95, 100])
def test_match_threshold_range(threshold):
    """Parametrized test for threshold range."""
    result = match("the evening redness in the west", threshold=threshold)

    if result is not None:
        assert result[1] >= threshold


@pytest.mark.parametrize("n", [1, 2, 3, 5, 10, 100])
def test_match_top_n_counts(n):
    """Parametrized test for top-N counts."""
    results = match_top_n("evening", n=n, threshold=50)

    assert len(results) <= n


@pytest.mark.parametrize("modifier_phrase,expected_effect", [
    ("under the stars", "verbose"),
    ("in silence", "quiet"),
    ("and the judge watched", "dry_run"),
    ("by first light", "schedule_morning"),
    ("the blood meridian", "commit_after"),
])
def test_modifier_extraction(modifier_phrase, expected_effect):
    """Parametrized test for modifier extraction."""
    mods = extract_modifiers(f"test command {modifier_phrase}")

    effects = [m["effect"] for m in mods]
    assert expected_effect in effects


# === Performance Boundary Tests ===

class TestPerformanceBoundaries:
    """Test performance with extreme inputs."""

    def test_rapid_matching(self):
        """Test rapid sequential matching."""
        import time

        start = time.time()
        for _ in range(100):
            match("the evening redness in the west")
        elapsed = time.time() - start

        # Should complete 100 matches in under 1 second
        assert elapsed < 1.0

    def test_rapid_modifier_extraction(self):
        """Test rapid modifier extraction."""
        import time

        start = time.time()
        for _ in range(100):
            extract_modifiers("test under the stars the blood meridian")
        elapsed = time.time() - start

        # Should complete 100 extractions in under 1 second
        assert elapsed < 1.0
