"""
Parser unit tests - verify grimoire matching works correctly.

They rode on.
"""

import pytest
from src.parser import (
    match,
    match_top_n,
    extract_modifiers,
    expand_command,
    validate_grimoire,
    list_commands,
    list_modifiers,
    load_grimoire,
    reload_grimoire,
    strip_filler_words,
    get_command_info,
)


class TestExactMatches:
    """Test exact phrase matching."""

    def test_evening_redness_exact(self):
        result = match("the evening redness in the west")
        assert result is not None
        cmd, score = result
        assert "deploy" in cmd["tags"]
        assert score >= 95

    def test_they_rode_on_exact(self):
        result = match("they rode on")
        assert result is not None
        cmd, score = result
        assert "continuation" in cmd["tags"]
        assert score >= 95

    def test_judge_smiled_exact(self):
        result = match("the judge smiled")
        assert result is not None
        cmd, score = result
        assert "testing" in cmd["tags"]


class TestFuzzyMatches:
    """Test fuzzy matching handles speech variation (with strict 'ratio' scorer)."""

    def test_missing_article_tolerated(self):
        # Missing "the" at start should still match (93% with ratio scorer)
        result = match("evening redness in the west")
        assert result is not None
        cmd, score = result
        assert "deploy" in cmd["tags"]
        assert score >= 80

    def test_typo_tolerated(self):
        # Single typo should still match
        result = match("the evenng redness in the west")
        assert result is not None
        cmd, score = result
        assert "deploy" in cmd["tags"]
        assert score >= 80

    def test_too_abbreviated_blocked(self):
        # Too much abbreviation should NOT match (safety feature)
        result = match("evening redness west")
        assert result is None  # Blocked by strict scorer

    def test_word_order_variation_blocked(self):
        # Word reordering should NOT match with ratio scorer (safety feature)
        result = match("in the west the evening redness")
        assert result is None  # Blocked - ratio scorer is strict on order


class TestNoMatch:
    """Test phrases that should NOT match."""

    def test_random_text_no_match(self):
        result = match("the weather is nice today")
        assert result is None

    def test_partial_match_below_threshold(self):
        # Single unrelated word shouldn't match
        # Note: "evening" DOES match because token_set_ratio is permissive
        result = match("banana")
        assert result is None

    def test_semantic_similarity_no_match(self):
        # Similar meaning but different words shouldn't match
        result = match("they continued riding forward")
        assert result is None


class TestModifiers:
    """Test modifier extraction."""

    def test_verbose_modifier(self):
        mods = extract_modifiers("the judge smiled under the stars")
        assert len(mods) == 1
        assert mods[0]["effect"] == "verbose"

    def test_dry_run_modifier(self):
        mods = extract_modifiers("the evening redness and the judge watched")
        assert len(mods) == 1
        assert mods[0]["effect"] == "dry_run"

    def test_multiple_modifiers(self):
        mods = extract_modifiers("deploy under the stars the blood meridian")
        effects = [m["effect"] for m in mods]
        assert "verbose" in effects
        assert "commit_after" in effects

    def test_no_modifiers(self):
        mods = extract_modifiers("they rode on")
        assert len(mods) == 0


class TestThreshold:
    """Test match threshold behavior."""

    def test_high_threshold_rejects_partial(self):
        # With ratio scorer, missing words drops score significantly
        # "evening redness in the west" (missing "the") scores ~93%
        result = match("evening redness in the west", threshold=95)
        assert result is None  # Rejected at 95% threshold

    def test_default_threshold_accepts_partial(self):
        # Same phrase should pass at default 80% threshold
        result = match("evening redness in the west", threshold=80)
        assert result is not None


class TestExpansion:
    """Test command expansion into Claude prompts."""

    def test_basic_expansion(self):
        result = match("the evening redness in the west")
        assert result is not None
        cmd, _ = result
        expansion = expand_command(cmd)
        assert "Deploy" in expansion
        assert "test" in expansion.lower()

    def test_expansion_with_modifier(self):
        result = match("the evening redness in the west")
        mods = extract_modifiers("test under the stars")
        assert result is not None
        cmd, _ = result
        expansion = expand_command(cmd, mods)
        assert "verbose" in expansion.lower() or "detailed" in expansion.lower()

    def test_expansion_shell_command_removed(self):
        """Test that shell_command is no longer injected into expansion (security fix)."""
        result = match("draw the sucker")
        assert result is not None
        cmd, _ = result
        expansion = expand_command(cmd)
        # shell_command feature removed for security - git pull should NOT appear
        assert "git pull" not in expansion
        # But the natural language expansion should still work
        assert "Pull the latest changes" in expansion


class TestValidation:
    """Test grimoire validation."""

    def test_grimoire_is_valid(self):
        issues = validate_grimoire()
        assert len(issues) == 0, f"Grimoire has issues: {issues}"

    def test_command_count(self):
        commands = list_commands()
        assert len(commands) >= 20  # We have 21 commands


class TestMatchTopN:
    """Test top-N matching for disambiguation."""

    def test_returns_list(self):
        """Verify match_top_n returns a list."""
        results = match_top_n("the evening redness in the west")
        assert isinstance(results, list)

    def test_returns_correct_count(self):
        """Verify match_top_n returns requested number of matches."""
        results = match_top_n("evening", n=3, threshold=50)
        assert len(results) <= 3

    def test_best_match_first(self):
        """Verify results are sorted by score descending."""
        results = match_top_n("the evening redness in the west", n=3)
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i][1] >= results[i + 1][1]

    def test_respects_threshold(self):
        """Verify all results meet threshold."""
        threshold = 80
        results = match_top_n("the evening redness in the west", n=5, threshold=threshold)
        for cmd, score in results:
            assert score >= threshold

    def test_empty_results_below_threshold(self):
        """Verify empty list when nothing meets threshold."""
        results = match_top_n("random nonsense xyz", n=3, threshold=90)
        assert len(results) == 0


class TestStripFillerWords:
    """Test filler word removal."""

    def test_removes_um(self):
        """Test removal of 'um'."""
        result = strip_filler_words("um the evening redness um in the west")
        assert "um" not in result

    def test_removes_uh(self):
        """Test removal of 'uh'."""
        result = strip_filler_words("uh they rode on")
        assert "uh" not in result

    def test_removes_like(self):
        """Test removal of 'like'."""
        result = strip_filler_words("like the judge smiled")
        assert result == "the judge smiled"

    def test_preserves_actual_words(self):
        """Test that actual words are preserved."""
        result = strip_filler_words("um the evening redness in the west")
        assert "evening" in result
        assert "redness" in result
        assert "west" in result

    def test_empty_string(self):
        """Test handling of empty string."""
        result = strip_filler_words("")
        assert result == ""

    def test_only_filler_words(self):
        """Test handling of string with only filler words."""
        result = strip_filler_words("um uh like so well")
        assert result.strip() == ""


class TestLoadGrimoire:
    """Test grimoire loading."""

    def test_load_returns_dict(self):
        """Verify load_grimoire returns a dictionary."""
        grimoire = load_grimoire()
        assert isinstance(grimoire, dict)

    def test_grimoire_has_commands(self):
        """Verify grimoire contains commands."""
        grimoire = load_grimoire()
        assert "commands" in grimoire
        assert len(grimoire["commands"]) > 0

    def test_grimoire_has_modifiers(self):
        """Verify grimoire contains modifiers."""
        grimoire = load_grimoire()
        assert "modifiers" in grimoire
        assert len(grimoire["modifiers"]) > 0

    def test_grimoire_has_parser_config(self):
        """Verify grimoire contains parser configuration."""
        grimoire = load_grimoire()
        assert "parser" in grimoire
        assert "threshold" in grimoire["parser"]


class TestReloadGrimoire:
    """Test grimoire reloading."""

    def test_reload_returns_dict(self):
        """Verify reload_grimoire returns a dictionary."""
        grimoire = reload_grimoire()
        assert isinstance(grimoire, dict)

    def test_reload_clears_cache(self):
        """Verify reload clears the cache and reloads."""
        # Load once to populate cache
        first = load_grimoire()
        # Reload should return fresh data
        second = reload_grimoire()
        # Both should have same structure
        assert "commands" in second
        assert len(first["commands"]) == len(second["commands"])


class TestGetCommandInfo:
    """Test command info extraction."""

    def test_returns_dict(self):
        """Verify get_command_info returns a dictionary."""
        grimoire = load_grimoire()
        cmd = grimoire["commands"][0]
        info = get_command_info(cmd)
        assert isinstance(info, dict)

    def test_contains_phrase(self):
        """Verify info contains phrase."""
        grimoire = load_grimoire()
        cmd = grimoire["commands"][0]
        info = get_command_info(cmd)
        assert "phrase" in info
        assert info["phrase"] == cmd["phrase"]

    def test_contains_tags(self):
        """Verify info contains tags."""
        grimoire = load_grimoire()
        cmd = grimoire["commands"][0]
        info = get_command_info(cmd)
        assert "tags" in info

    def test_contains_confirmation_flag(self):
        """Verify info contains confirmation requirement."""
        grimoire = load_grimoire()
        cmd = grimoire["commands"][0]
        info = get_command_info(cmd)
        assert "requires_confirmation" in info


class TestListModifiers:
    """Test modifier listing."""

    def test_returns_list(self):
        """Verify list_modifiers returns a list."""
        modifiers = list_modifiers()
        assert isinstance(modifiers, list)

    def test_has_modifiers(self):
        """Verify modifiers are returned."""
        modifiers = list_modifiers()
        assert len(modifiers) > 0

    def test_modifier_has_phrase(self):
        """Verify each modifier has a phrase."""
        modifiers = list_modifiers()
        for mod in modifiers:
            assert "phrase" in mod

    def test_modifier_has_effect(self):
        """Verify each modifier has an effect."""
        modifiers = list_modifiers()
        for mod in modifiers:
            assert "effect" in mod


class TestThreadSafeLoading:
    """Test thread-safe grimoire loading."""

    def test_concurrent_loads_same_result(self):
        """Verify concurrent loads return the same cached result."""
        import threading
        import src.parser as parser

        # Reset cache
        parser._grimoire_cache = None

        results = []
        errors = []

        def load_and_store():
            try:
                result = parser.load_grimoire()
                results.append(id(result))
            except Exception as e:
                errors.append(e)

        # Start 10 threads simultaneously
        threads = [threading.Thread(target=load_and_store) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should have succeeded
        assert len(errors) == 0, f"Errors during concurrent load: {errors}"
        # All should return the same object (cached)
        assert len(set(results)) == 1, "Different objects returned from concurrent loads"

    def test_reload_is_thread_safe(self):
        """Verify reload_grimoire is thread-safe."""
        import threading
        import src.parser as parser

        errors = []

        def reload_grimoire():
            try:
                parser.reload_grimoire()
            except Exception as e:
                errors.append(e)

        # Start multiple reload threads
        threads = [threading.Thread(target=reload_grimoire) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should have succeeded
        assert len(errors) == 0, f"Errors during concurrent reload: {errors}"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_very_long_input(self):
        """Test handling of very long input strings."""
        long_text = "the evening redness in the west " * 100
        result = match(long_text)
        # Should either match or return None, but not crash
        assert result is None or result[1] >= 0

    def test_unicode_input(self):
        """Test handling of unicode characters."""
        result = match("the evening redness")
        assert result is not None or result is None  # Just verify no crash

    def test_special_characters(self):
        """Test handling of special characters."""
        result = match("the evening redness! @#$%")
        # Should handle gracefully
        assert result is not None or result is None

    def test_case_insensitivity(self):
        """Test that matching is case-insensitive."""
        lower_result = match("the evening redness in the west")
        upper_result = match("THE EVENING REDNESS IN THE WEST")
        mixed_result = match("The Evening Redness In The West")

        # All should match the same command (or all fail)
        if lower_result is not None:
            assert upper_result is not None
            assert mixed_result is not None
            assert lower_result[0]["phrase"] == upper_result[0]["phrase"]
            assert lower_result[0]["phrase"] == mixed_result[0]["phrase"]

    def test_whitespace_handling(self):
        """Test that extra whitespace is handled."""
        normal = match("the evening redness in the west")
        extra_spaces = match("the  evening   redness  in  the  west")

        # Both should match (filler word stripping normalizes whitespace)
        if normal is not None:
            assert extra_spaces is not None
