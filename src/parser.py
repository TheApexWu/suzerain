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
def _find_grimoire_path(grimoire_file: str = None):
    """
    Find grimoire file, checking config and multiple locations.

    Args:
        grimoire_file: Override grimoire filename (e.g., 'dune.yaml').
                       If None, reads from config.
    """
    # Get grimoire filename from config if not specified
    if grimoire_file is None:
        try:
            from config import get_config
            grimoire_file = get_config().grimoire_file or "vanilla.yaml"
        except Exception:
            grimoire_file = "vanilla.yaml"

    # First check: installed package location (src/grimoire/)
    pkg_path = Path(__file__).parent / "grimoire" / grimoire_file
    if pkg_path.exists():
        return pkg_path
    # Fallback: development layout (../grimoire/)
    dev_path = Path(__file__).parent.parent / "grimoire" / grimoire_file
    if dev_path.exists():
        return dev_path
    # Default to package path (will error if not found)
    return pkg_path


def get_grimoire_path() -> Path:
    """Get the current grimoire path (reloads from config each time)."""
    return _find_grimoire_path()


GRIMOIRE_PATH = _find_grimoire_path()

# Thread-safe cache for loaded grimoire
_grimoire_cache = None
_grimoire_cache_path = None  # Track which file was cached
_grimoire_lock = threading.Lock()

# v0.6: Semantic matching with embeddings
_embedding_model = None
_embedding_cache = None  # {phrase: embedding}
_embedding_lock = threading.Lock()
SEMANTIC_ENABLED = True  # Can disable with config
SEMANTIC_MODEL = "all-MiniLM-L6-v2"  # Fast, good quality (80MB)
SEMANTIC_THRESHOLD = 0.5  # Cosine similarity threshold (0-1)


def load_grimoire() -> dict:
    """
    Load command definitions from YAML. Cached after first load.

    Uses double-check locking pattern for thread safety:
    1. First check without lock (fast path for cached case)
    2. Acquire lock and check again before loading

    Automatically reloads if config grimoire file changed.
    """
    global _grimoire_cache, _grimoire_cache_path
    current_path = get_grimoire_path()

    # Fast path: cache already populated with same file
    if _grimoire_cache is not None and _grimoire_cache_path == current_path:
        return _grimoire_cache

    # Slow path: acquire lock and double-check
    with _grimoire_lock:
        # Another thread may have loaded while we waited for lock
        if _grimoire_cache is None or _grimoire_cache_path != current_path:
            with open(current_path) as f:
                _grimoire_cache = yaml.safe_load(f)
                _grimoire_cache_path = current_path
    return _grimoire_cache


def reload_grimoire() -> dict:
    """Force reload grimoire from disk. Thread-safe."""
    global _grimoire_cache, _grimoire_cache_path
    with _grimoire_lock:
        _grimoire_cache = None
        _grimoire_cache_path = None
    return load_grimoire()


# === v0.6: Semantic Matching ===

def _get_embedding_model():
    """Lazy load the sentence transformer model."""
    global _embedding_model

    if not SEMANTIC_ENABLED:
        return None

    with _embedding_lock:
        if _embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                _embedding_model = SentenceTransformer(SEMANTIC_MODEL)
            except ImportError:
                return None
            except Exception:
                return None
    return _embedding_model


def _get_phrase_embeddings() -> dict:
    """
    Get embeddings for all grimoire phrases AND aliases. Cached after first call.

    Returns:
        Dict mapping phrase -> embedding numpy array
    """
    global _embedding_cache

    model = _get_embedding_model()
    if model is None:
        return {}

    with _embedding_lock:
        if _embedding_cache is None:
            grimoire = load_grimoire()
            commands = grimoire.get("commands", [])

            # Collect all phrases INCLUDING aliases
            phrases = []
            for cmd in commands:
                if "phrase" in cmd:
                    phrases.append(cmd["phrase"])
                for alias in cmd.get("aliases", []):
                    phrases.append(alias)

            if phrases:
                embeddings = model.encode(phrases, convert_to_numpy=True)
                _embedding_cache = {phrase: emb for phrase, emb in zip(phrases, embeddings)}
            else:
                _embedding_cache = {}

    return _embedding_cache


def semantic_match(text: str, threshold: float = None) -> Optional[Tuple[dict, float]]:
    """
    Match text against grimoire using semantic similarity.

    Uses sentence embeddings to find semantically similar phrases,
    even if the words are different.

    Args:
        text: Input text to match
        threshold: Minimum cosine similarity (0-1). Uses SEMANTIC_THRESHOLD if None.

    Returns:
        Tuple of (matched_command, similarity_score) or None if no match
    """
    import numpy as np

    if threshold is None:
        threshold = SEMANTIC_THRESHOLD

    model = _get_embedding_model()
    if model is None:
        return None

    phrase_embeddings = _get_phrase_embeddings()
    if not phrase_embeddings:
        return None

    # Embed input text
    try:
        input_embedding = model.encode(text, convert_to_numpy=True)
    except Exception:
        return None

    # Find best match by cosine similarity
    grimoire = load_grimoire()
    # Build phrase map INCLUDING aliases
    phrase_map = {}
    for cmd in grimoire.get("commands", []):
        phrase_map[cmd["phrase"]] = cmd
        for alias in cmd.get("aliases", []):
            phrase_map[alias] = cmd

    best_phrase = None
    best_score = -1

    for phrase, phrase_emb in phrase_embeddings.items():
        # Cosine similarity
        similarity = np.dot(input_embedding, phrase_emb) / (
            np.linalg.norm(input_embedding) * np.linalg.norm(phrase_emb)
        )

        if similarity > best_score:
            best_score = similarity
            best_phrase = phrase

    if best_phrase and best_score >= threshold:
        # Convert similarity (0-1) to score (0-100) for consistency
        return phrase_map[best_phrase], float(best_score * 100)

    return None


def match_hybrid(text: str, fuzzy_threshold: int = None, semantic_threshold: float = None) -> Optional[Tuple[dict, int, str]]:
    """
    Hybrid matching: Try fuzzy first, fall back to semantic.

    This gives the best of both worlds:
    - Fuzzy catches exact/near-exact phrases quickly
    - Semantic catches intent when words differ

    Args:
        text: Input text to match
        fuzzy_threshold: Minimum fuzzy match score (0-100)
        semantic_threshold: Minimum semantic similarity (0-1)

    Returns:
        Tuple of (matched_command, score, method) or None
        method is "fuzzy", "semantic", or "escape"
    """
    # Phase 1: Try escape hatches first (instant)
    result = match(text, threshold=95)  # High threshold for escape hatches
    if result:
        cmd, score = result
        if cmd.get("is_escape_hatch"):
            return cmd, score, "escape"

    # Phase 2: Try fuzzy matching
    result = match(text, threshold=fuzzy_threshold)
    if result:
        cmd, score = result
        return cmd, score, "fuzzy"

    # Phase 3: Fall back to semantic matching
    if SEMANTIC_ENABLED:
        result = semantic_match(text, threshold=semantic_threshold)
        if result:
            cmd, score = result
            return cmd, int(score), "semantic"

    return None


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


def strip_modifiers(text: str) -> str:
    """
    Strip modifier phrases from text before matching.

    This allows "the evening redness in the west and the judge watched"
    to match "the evening redness in the west" by removing the modifier.
    """
    grimoire = load_grimoire()
    modifiers = grimoire.get("modifiers", [])

    result = text.lower()
    for mod in modifiers:
        mod_phrase = mod["phrase"].lower()
        result = result.replace(mod_phrase, "")

    # Clean up extra whitespace
    return " ".join(result.split())


def match(text: str, threshold: int = None) -> Optional[Tuple[dict, int]]:
    """
    Match spoken text against grimoire commands.

    Escape hatches (stop, cancel, hold, etc.) are checked FIRST with
    exact matching for immediate response - no fuzzy matching delay.

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

    # Clean input: strip filler words AND modifier phrases
    cleaned = strip_filler_words(text)
    cleaned = strip_modifiers(cleaned)
    text_lower = cleaned.lower().strip()

    # === PHASE 1: Escape hatch priority (exact match, no fuzzy) ===
    # These bypass fuzzy matching for immediate response (<5ms)
    escape_commands = [cmd for cmd in commands if cmd.get("is_escape_hatch")]
    for cmd in escape_commands:
        phrase_lower = cmd["phrase"].lower()
        # Exact match or phrase contained in input
        if phrase_lower == text_lower or phrase_lower in text_lower.split():
            return cmd, 100  # Perfect score for escape hatch

    # === PHASE 2: Normal fuzzy matching (includes aliases) ===
    scorer_name = parser_config.get("scorer", "token_set_ratio")
    scorer = getattr(fuzz, scorer_name, fuzz.token_set_ratio)

    # Build phrase -> command mapping INCLUDING aliases
    phrase_map = {}
    for cmd in commands:
        phrase_map[cmd["phrase"]] = cmd
        # Add aliases (literary phrases that map to same command)
        for alias in cmd.get("aliases", []):
            phrase_map[alias] = cmd

    # Fuzzy match against all phrases and aliases
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

    # Clean input: strip filler words AND modifier phrases
    cleaned = strip_filler_words(text)
    cleaned = strip_modifiers(cleaned)

    # Build phrase -> command mapping INCLUDING aliases
    phrase_map = {}
    for cmd in commands:
        phrase_map[cmd["phrase"]] = cmd
        for alias in cmd.get("aliases", []):
            phrase_map[alias] = cmd

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
