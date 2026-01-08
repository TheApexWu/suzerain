"""
Semantic Command Parser - Learned embeddings for cipher phrase tolerance.

Uses sentence-transformers to handle speech recognition errors and minor
variations in cipher phrases. NOT for plain English → cipher matching.

"the judge smiled" → match
"the judge grinned" → match (close enough)
"da judge smiled" → match (speech error)
"run the tests" → NO MATCH (use the cipher)

"Whatever in creation exists without my knowledge exists without my consent."
"""

import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List
import yaml

# Lazy load sentence-transformers (heavy import)
_model = None
_embeddings_cache = None


def _get_model():
    """Lazy load the sentence transformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        # all-MiniLM-L6-v2: Fast (80ms), 384 dims, good accuracy
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


def _find_grimoire_path(grimoire_file: str = None) -> Path:
    """Find grimoire file path."""
    if grimoire_file is None:
        try:
            from config import get_config
            grimoire_file = get_config().grimoire_file or "vanilla.yaml"
        except Exception:
            grimoire_file = "vanilla.yaml"

    pkg_path = Path(__file__).parent / "grimoire" / grimoire_file
    if pkg_path.exists():
        return pkg_path
    dev_path = Path(__file__).parent.parent / "grimoire" / grimoire_file
    if dev_path.exists():
        return dev_path
    return pkg_path


def _load_grimoire() -> dict:
    """Load grimoire from YAML."""
    path = _find_grimoire_path()
    with open(path) as f:
        return yaml.safe_load(f)


def _get_embeddings() -> Tuple[np.ndarray, List[dict]]:
    """
    Get embeddings for all grimoire cipher phrases ONLY.

    We embed ONLY the phrase itself - no tags, no expansion hints.
    This ensures we match variations of the cipher, not plain English intent.
    """
    global _embeddings_cache

    if _embeddings_cache is not None:
        return _embeddings_cache

    model = _get_model()
    grimoire = _load_grimoire()
    commands = grimoire.get("commands", [])

    # ONLY embed the cipher phrases - nothing else
    # This prevents "run tests" from matching "the judge smiled"
    texts = [cmd.get("phrase", "") for cmd in commands]

    # Compute embeddings (batched, ~200ms total)
    embeddings = model.encode(texts, convert_to_numpy=True)

    _embeddings_cache = (embeddings, commands)
    return _embeddings_cache


def preload():
    """
    Preload model and compute embeddings.
    Call during startup to avoid latency on first match.
    """
    _get_model()
    _get_embeddings()


def match(text: str, threshold: float = 0.65) -> Optional[Tuple[dict, float]]:
    """
    Match spoken text against grimoire cipher phrases.

    Threshold (0.65) balances tolerance for speech errors while rejecting
    plain English that happens to be semantically similar.

    "the judge smiled" → match (exact)
    "the judge grinned" → match (similar phrase)
    "they road on" → match (homophone error)
    "run the tests" → NO MATCH (plain English, use the cipher)

    Args:
        text: Transcribed speech
        threshold: Minimum cosine similarity (0-1). Default 0.65.

    Returns:
        Tuple of (matched_command, score) or None if no match
    """
    model = _get_model()
    embeddings, commands = _get_embeddings()

    # Embed the query
    query_embedding = model.encode([text], convert_to_numpy=True)[0]

    # Compute cosine similarities
    query_norm = query_embedding / np.linalg.norm(query_embedding)
    embeddings_norm = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    similarities = embeddings_norm @ query_norm

    # Find best match
    best_idx = np.argmax(similarities)
    best_score = similarities[best_idx]

    if best_score >= threshold:
        # Convert to 0-100 scale for compatibility with fuzzy parser
        return commands[best_idx], float(best_score * 100)

    return None


def match_top_n(text: str, n: int = 3, threshold: float = 0.65) -> List[Tuple[dict, float]]:
    """
    Return top N matches above threshold for disambiguation.

    Args:
        text: Transcribed speech
        n: Number of top matches to return
        threshold: Minimum similarity score

    Returns:
        List of (command, score) tuples, sorted by score descending
    """
    model = _get_model()
    embeddings, commands = _get_embeddings()

    # Embed the query
    query_embedding = model.encode([text], convert_to_numpy=True)[0]

    # Compute cosine similarities
    query_norm = query_embedding / np.linalg.norm(query_embedding)
    embeddings_norm = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    similarities = embeddings_norm @ query_norm

    # Get top N indices
    top_indices = np.argsort(similarities)[::-1][:n]

    results = []
    for idx in top_indices:
        score = similarities[idx]
        if score >= threshold:
            results.append((commands[idx], float(score * 100)))

    return results


def explain_match(text: str, command: dict) -> str:
    """
    Explain why a command matched (for debugging/demo).

    Returns a human-readable explanation of the semantic similarity.
    """
    model = _get_model()

    # Get embeddings for both
    query_emb = model.encode([text], convert_to_numpy=True)[0]

    phrase = command.get("phrase", "")
    tags = " ".join(command.get("tags", []))
    cmd_text = f"{phrase} {tags}"
    cmd_emb = model.encode([cmd_text], convert_to_numpy=True)[0]

    # Cosine similarity
    similarity = np.dot(query_emb, cmd_emb) / (np.linalg.norm(query_emb) * np.linalg.norm(cmd_emb))

    return f"'{text}' → '{phrase}' (semantic similarity: {similarity:.2%})"


# Re-export parser functions for compatibility
def extract_modifiers(text: str) -> List[dict]:
    """Extract modifiers (delegated to original parser)."""
    from parser import extract_modifiers as _extract_modifiers
    return _extract_modifiers(text)


def expand_command(command: dict, modifiers: List[dict] = None) -> str:
    """Expand command (delegated to original parser)."""
    from parser import expand_command as _expand_command
    return _expand_command(command, modifiers)


def list_commands() -> List[dict]:
    """List all commands."""
    grimoire = _load_grimoire()
    commands = grimoire.get("commands", [])
    return [{
        "phrase": cmd.get("phrase", ""),
        "tags": cmd.get("tags", []),
        "requires_confirmation": cmd.get("confirmation", False),
    } for cmd in commands]


# === CLI for testing ===

if __name__ == "__main__":
    import time

    print("=" * 60)
    print("SEMANTIC PARSER TEST - Cipher Tolerance Mode")
    print("=" * 60)

    # Time the preload
    start = time.time()
    preload()
    print(f"\nModel + embeddings loaded in {(time.time() - start)*1000:.0f}ms")

    # Test phrases - cipher variations should match, plain English should NOT
    test_phrases = [
        # Exact cipher matches - SHOULD match
        ("the evening redness in the west", True, "exact cipher"),
        ("they rode on", True, "exact cipher"),
        ("the judge smiled", True, "exact cipher"),

        # Cipher variations (typos, similar words) - SHOULD match
        ("the judge grinned", True, "similar verb"),
        ("the evening redness in the East", True, "minor variation"),
        ("da judge smiled", True, "speech error"),
        ("they road on", True, "homophone error"),

        # Plain English - should NOT match (use the cipher!)
        ("run the tests", False, "plain English"),
        ("deploy to production", False, "plain English"),
        ("keep going", False, "plain English"),
        ("pull the latest changes", False, "plain English"),
        ("commit my changes", False, "plain English"),

        # Random nonsense - should NOT match
        ("what's the weather today", False, "unrelated"),
        ("hello world", False, "unrelated"),
    ]

    print("\n--- Testing Cipher Tolerance ---\n")

    correct = 0
    total = len(test_phrases)

    for phrase, should_match, category in test_phrases:
        start = time.time()
        result = match(phrase)
        elapsed = (time.time() - start) * 1000

        matched = result is not None

        if matched == should_match:
            status = "✓"
            correct += 1
        else:
            status = "✗"

        if result:
            cmd, score = result
            print(f"{status} [{category}] \"{phrase}\"")
            print(f"   → \"{cmd['phrase']}\" (score: {score:.0f}) [{elapsed:.0f}ms]")
        else:
            print(f"{status} [{category}] \"{phrase}\" → NO MATCH [{elapsed:.0f}ms]")
        print()

    print("=" * 60)
    print(f"Accuracy: {correct}/{total} ({100*correct/total:.0f}%)")
    print(f"Total commands indexed: {len(list_commands())}")
