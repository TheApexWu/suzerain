"""
Grimoire Parser - Literary macro expansion for voice commands.

Matches spoken phrases against personal grimoire entries,
then expands them into full Claude prompts.

"The truth about the world is that anything is possible."
"""

import re
import threading
import yaml
from pathlib import Path
from rapidfuzz import fuzz, process
from typing import Optional, Tuple, List

# Grimoire location - check multiple locations for flexibility
def _find_grimoire_path():
    """Find grimoire file, checking installed package location first."""
    # First check: installed package location (src/grimoire/)
    pkg_path = Path(__file__).parent / "grimoire" / "commands.yaml"
    if pkg_path.exists():
        return pkg_path
    # Fallback: development layout (../grimoire/)
    dev_path = Path(__file__).parent.parent / "grimoire" / "commands.yaml"
    if dev_path.exists():
        return dev_path
    # Default to package path (will error if not found)
    return pkg_path

GRIMOIRE_PATH = _find_grimoire_path()

# Thread-safe cache for loaded grimoire
_grimoire_cache = None
_grimoire_lock = threading.Lock()


def load_grimoire() -> dict:
    """
    Load command definitions from YAML. Cached after first load.

    Uses double-check locking pattern for thread safety:
    1. First check without lock (fast path for cached case)
    2. Acquire lock and check again before loading
    """
    global _grimoire_cache
    # Fast path: cache already populated
    if _grimoire_cache is not None:
        return _grimoire_cache

    # Slow path: acquire lock and double-check
    with _grimoire_lock:
        # Another thread may have loaded while we waited for lock
        if _grimoire_cache is None:
            with open(GRIMOIRE_PATH) as f:
                _grimoire_cache = yaml.safe_load(f)
    return _grimoire_cache


def reload_grimoire() -> dict:
    """Force reload grimoire from disk. Thread-safe."""
    global _grimoire_cache
    with _grimoire_lock:
        _grimoire_cache = None
    return load_grimoire()


def strip_filler_words(text: str) -> str:
    """Remove filler words that don't affect meaning."""
    grimoire = load_grimoire()
    filler_words = grimoire.get("parser", {}).get("strip_filler_words", [])

    result = text.lower()
    for filler in filler_words:
        # Remove filler words with word boundaries
        pattern = r'\b' + re.escape(filler) + r'\b'
        result = re.sub(pattern, '', result)

    # Clean up extra whitespace
    result = ' '.join(result.split())
    return result


def match(text: str, threshold: int = None) -> Optional[Tuple[dict, int]]:
    """
    Match spoken text against grimoire commands.

    Args:
        text: Transcribed speech
        threshold: Minimum match score (0-100). Uses config default if None.

    Returns:
        Tuple of (matched_command, score) or None if no match
    """
    grimoire = load_grimoire()
    commands = grimoire.get("commands", [])
    parser_config = grimoire.get("parser", {})

    if threshold is None:
        threshold = parser_config.get("threshold", 70)

    scorer_name = parser_config.get("scorer", "token_set_ratio")
    scorer = getattr(fuzz, scorer_name, fuzz.token_set_ratio)

    # Clean input
    cleaned = strip_filler_words(text)

    # Build phrase -> command mapping
    phrase_map = {cmd["phrase"]: cmd for cmd in commands}

    # Fuzzy match against all phrases
    result = process.extractOne(
        cleaned,
        phrase_map.keys(),
        scorer=scorer
    )

    if result and result[1] >= threshold:
        phrase, score, _ = result
        return phrase_map[phrase], score

    return None


def match_top_n(text: str, n: int = 3, threshold: int = None) -> List[Tuple[dict, int]]:
    """
    Return top N matches above threshold for disambiguation.

    Args:
        text: Transcribed speech
        n: Number of top matches to return
        threshold: Minimum match score. Uses config default if None.

    Returns:
        List of (command, score) tuples, sorted by score descending
    """
    grimoire = load_grimoire()
    commands = grimoire.get("commands", [])
    parser_config = grimoire.get("parser", {})

    if threshold is None:
        threshold = parser_config.get("threshold", 70)

    scorer_name = parser_config.get("scorer", "token_set_ratio")
    scorer = getattr(fuzz, scorer_name, fuzz.token_set_ratio)

    # Clean input
    cleaned = strip_filler_words(text)

    # Build phrase -> command mapping
    phrase_map = {cmd["phrase"]: cmd for cmd in commands}

    # Get top N matches
    results = process.extract(
        cleaned,
        phrase_map.keys(),
        scorer=scorer,
        limit=n
    )

    # Filter by threshold and return command objects
    matches = []
    for phrase, score, _ in results:
        if score >= threshold:
            matches.append((phrase_map[phrase], score))

    return matches


def extract_modifiers(text: str) -> List[dict]:
    """
    Extract modifiers from the spoken text.

    Modifiers are phrases like "under the stars" that modify
    how the command executes (verbose, dry run, etc.)

    Args:
        text: Full spoken text

    Returns:
        List of matched modifier dicts with their expansion_append
    """
    grimoire = load_grimoire()
    modifiers = grimoire.get("modifiers", [])
    matched = []

    text_lower = text.lower()
    for mod in modifiers:
        if mod["phrase"] in text_lower:
            matched.append(mod)

    return matched


def expand_command(command: dict, modifiers: List[dict] = None) -> str:
    """
    Expand a grimoire command into a full Claude prompt.

    Takes the base expansion and appends any modifier instructions.

    Args:
        command: Matched command dict from grimoire
        modifiers: List of modifier dicts to apply

    Returns:
        Full prompt string to send to Claude
    """
    if modifiers is None:
        modifiers = []

    # Start with base expansion
    base = command.get("expansion", "")

    # Note: shell_command feature removed for security (command injection risk)
    # All shell operations now go through Claude Code's sandboxed execution

    # Append modifier instructions
    for mod in modifiers:
        append_text = mod.get("expansion_append", "")
        if append_text:
            base += f"\n\n{append_text}"

    return base.strip()


def get_command_info(command: dict) -> dict:
    """
    Get metadata about a command for display/confirmation.

    Returns:
        Dict with: phrase, tags, requires_confirmation, expansion_preview
    """
    return {
        "phrase": command.get("phrase", ""),
        "tags": command.get("tags", []),
        "requires_confirmation": command.get("confirmation", False),
        "use_continue": command.get("use_continue", False),
        "expansion_preview": command.get("expansion", "")[:100] + "..."
    }


def list_commands() -> List[dict]:
    """List all available commands with metadata."""
    grimoire = load_grimoire()
    commands = grimoire.get("commands", [])
    return [get_command_info(cmd) for cmd in commands]


def list_modifiers() -> List[dict]:
    """List all available modifiers."""
    grimoire = load_grimoire()
    return grimoire.get("modifiers", [])


def validate_grimoire() -> List[str]:
    """
    Validate grimoire structure and return any issues.

    Checks:
    - All commands have required fields
    - No duplicate phrases
    - Modifiers are well-formed

    Returns:
        List of warning/error strings (empty if valid)
    """
    issues = []
    grimoire = load_grimoire()

    commands = grimoire.get("commands", [])
    modifiers = grimoire.get("modifiers", [])

    # Check commands
    seen_phrases = set()
    for i, cmd in enumerate(commands):
        if "phrase" not in cmd:
            issues.append(f"Command {i}: missing 'phrase'")
        elif cmd["phrase"] in seen_phrases:
            issues.append(f"Duplicate phrase: '{cmd['phrase']}'")
        else:
            seen_phrases.add(cmd["phrase"])

        if "expansion" not in cmd:
            issues.append(f"Command '{cmd.get('phrase', i)}': missing 'expansion'")

    # Check modifiers
    seen_mod_phrases = set()
    for i, mod in enumerate(modifiers):
        if "phrase" not in mod:
            issues.append(f"Modifier {i}: missing 'phrase'")
        elif mod["phrase"] in seen_mod_phrases:
            issues.append(f"Duplicate modifier phrase: '{mod['phrase']}'")
        else:
            seen_mod_phrases.add(mod["phrase"])

        if "effect" not in mod:
            issues.append(f"Modifier '{mod.get('phrase', i)}': missing 'effect'")

    return issues


# === CLI for testing ===

if __name__ == "__main__":

    # Validate grimoire first
    issues = validate_grimoire()
    if issues:
        print("GRIMOIRE ISSUES:")
        for issue in issues:
            print(f"  - {issue}")
        print()

    # Test phrases
    test_phrases = [
        "the evening redness in the west",
        "evening redness west",  # partial
        "um the evening redness in the west under the stars",  # with filler + modifier
        "they rode on",
        "scour the terrain and the judge watched",  # command + dry run modifier
        "random nonsense that shouldn't match",
    ]

    print("=" * 60)
    print("GRIMOIRE PARSER TEST")
    print("=" * 60)

    for phrase in test_phrases:
        print(f"\nInput: \"{phrase}\"")

        result = match(phrase)
        modifiers = extract_modifiers(phrase)

        if result:
            command, score = result
            print(f"  → Matched: \"{command['phrase']}\" (score: {score})")
            print(f"  → Tags: {command.get('tags', [])}")

            if modifiers:
                print(f"  → Modifiers: {[m['effect'] for m in modifiers]}")

            # Show expansion preview
            expansion = expand_command(command, modifiers)
            preview = expansion[:150].replace('\n', ' ')
            print(f"  → Expansion: {preview}...")

            if command.get("confirmation"):
                print("  ⚠️  Requires confirmation")
        else:
            print("  → NO MATCH")

    print("\n" + "=" * 60)
    print(f"Total commands: {len(list_commands())}")
    print(f"Total modifiers: {len(list_modifiers())}")
