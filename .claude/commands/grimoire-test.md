# Test Grimoire Matching

Test the grimoire parser with sample phrases to verify fuzzy matching works correctly.

## Instructions

1. Read `src/parser.py` to understand current matching logic
2. Test these phrases against the grimoire:
   - "the evening redness in the west" (exact)
   - "evening redness west" (partial)
   - "they rode on" (exact)
   - "they continued riding" (semantic miss - should NOT match)
3. Report match scores and any false positives/negatives
4. Suggest threshold adjustments if needed (current: 70%)

Run: `python -m pytest tests/test_parser.py -v`
