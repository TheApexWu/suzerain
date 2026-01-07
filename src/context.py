"""
Context Provider - Read and detect clipboard content for richer prompts.

"Whatever exists without my knowledge exists without my consent."
"""

import os
import re
import subprocess
import sys
from typing import Optional, Tuple
from urllib.parse import urlparse


# Maximum clipboard content size before truncation
MAX_CLIPBOARD_SIZE = 8000  # ~2K tokens roughly


class ClipboardError(Exception):
    """Failed to read clipboard."""
    pass


def get_clipboard() -> str:
    """
    Read text from system clipboard.

    Returns:
        Clipboard contents as string, or empty string if clipboard is empty/unavailable.

    Raises:
        ClipboardError: If clipboard cannot be accessed.
    """
    try:
        if sys.platform == "darwin":
            # macOS
            result = subprocess.run(
                ["pbpaste"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout
        elif sys.platform.startswith("linux"):
            # Linux - try xclip first, then xsel
            for cmd in [["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]]:
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        return result.stdout
                except FileNotFoundError:
                    continue
            raise ClipboardError("No clipboard tool found. Install xclip or xsel.")
        elif sys.platform == "win32":
            # Windows - use PowerShell
            result = subprocess.run(
                ["powershell", "-command", "Get-Clipboard"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout
        else:
            raise ClipboardError(f"Unsupported platform: {sys.platform}")
    except subprocess.TimeoutExpired:
        raise ClipboardError("Clipboard read timed out")
    except FileNotFoundError as e:
        raise ClipboardError(f"Clipboard command not found: {e}")
    except Exception as e:
        raise ClipboardError(f"Failed to read clipboard: {e}")


def detect_content_type(content: str) -> str:
    """
    Detect the type of clipboard content.

    Returns:
        One of: 'code', 'url', 'path', 'text', 'empty'
    """
    if not content or not content.strip():
        return "empty"

    content = content.strip()

    # URL detection
    if _looks_like_url(content):
        return "url"

    # File path detection
    if _looks_like_path(content):
        return "path"

    # Code detection (heuristic)
    if _looks_like_code(content):
        return "code"

    return "text"


def _looks_like_url(content: str) -> bool:
    """Check if content looks like a URL."""
    # Simple URL pattern
    url_pattern = r'^https?://[^\s<>"{}|\\^`\[\]]+'
    if re.match(url_pattern, content, re.IGNORECASE):
        return True

    # Check if it parses as URL
    try:
        result = urlparse(content)
        return all([result.scheme in ('http', 'https'), result.netloc])
    except Exception:
        return False


def _looks_like_path(content: str) -> bool:
    """Check if content looks like a file path."""
    # Must be a single line
    if '\n' in content:
        return False

    # Common path patterns
    if content.startswith(('/', '~/', './', '../')):
        return True
    if os.path.sep in content and ' ' not in content[:20]:
        return True
    # Windows paths
    if len(content) > 2 and content[1] == ':' and content[2] in ('\\', '/'):
        return True

    return False


def _looks_like_code(content: str) -> bool:
    """
    Heuristic to detect if content looks like code.

    Checks for common code patterns across languages.
    """
    # Strong code indicators
    code_patterns = [
        r'^\s*(def |class |function |const |let |var |import |from |export )',
        r'^\s*(if\s*\(|for\s*\(|while\s*\(|switch\s*\()',
        r'^\s*#include\s*[<"]',
        r'^\s*(public|private|protected)\s+(static\s+)?(void|int|string|class)',
        r'[{};]\s*$',  # Lines ending in { } ;
        r'=>',  # Arrow functions
        r'^\s*@\w+',  # Decorators
        r'\)\s*{',  # function() {
        r'^\s*return\s+',
        r'^\s*(try|catch|finally)\s*[:{]',
    ]

    lines = content.split('\n')[:20]  # Check first 20 lines
    code_line_count = 0

    for line in lines:
        for pattern in code_patterns:
            if re.search(pattern, line, re.MULTILINE):
                code_line_count += 1
                break

    # If >30% of lines look like code, it's probably code
    if len(lines) > 0 and code_line_count / len(lines) > 0.3:
        return True

    # Check for balanced braces (common in code)
    brace_count = content.count('{') + content.count('}')

    if brace_count >= 4 and abs(content.count('{') - content.count('}')) <= 1:
        return True

    return False


def detect_code_language(content: str) -> Optional[str]:
    """
    Try to detect the programming language of code content.

    Returns:
        Language name or None if can't determine.
    """
    # Language-specific patterns
    patterns = {
        'python': [r'^\s*def \w+\(', r'^\s*import \w+', r'^\s*from \w+ import', r'^\s*class \w+:'],
        'javascript': [r'\bconst \w+ =', r'\blet \w+ =', r'\bfunction \w+\(', r'=>', r'require\('],
        'typescript': [r': \w+\[\]', r': \w+<', r'interface \w+', r': string', r': number'],
        'rust': [r'\bfn \w+\(', r'\blet mut ', r'\bimpl ', r'->.*{', r'::'],
        'go': [r'\bfunc \w+\(', r'\bpackage \w+', r'\btype \w+ struct', r':= '],
        'java': [r'\bpublic class ', r'\bprivate \w+ \w+', r'\bSystem\.out\.'],
        'c': [r'#include\s*<', r'\bint main\(', r'\bvoid \w+\(', r'\bprintf\('],
        'cpp': [r'#include\s*<', r'\bstd::', r'\bcout\s*<<', r'\btemplate\s*<'],
        'shell': [r'^#!/bin/(ba)?sh', r'\$\{?\w+\}?', r'\becho\b', r'\bif \['],
        'sql': [r'\bSELECT\b', r'\bFROM\b', r'\bWHERE\b', r'\bINSERT INTO\b'],
        'html': [r'<html', r'<div', r'<head', r'</\w+>'],
        'css': [r'{\s*\w+:', r'^\s*\.\w+\s*{', r'^\s*#\w+\s*{'],
        'yaml': [r'^\w+:\s*$', r'^\s*-\s+\w+:', r'^\s+\w+:\s+.+'],
        'json': [r'^\s*{', r'"\w+":\s*["{[\d]'],
    }

    for lang, lang_patterns in patterns.items():
        matches = 0
        for pattern in lang_patterns:
            if re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
                matches += 1
        if matches >= 2:
            return lang

    return None


def sanitize_content(content: str, max_size: int = MAX_CLIPBOARD_SIZE) -> Tuple[str, bool]:
    """
    Sanitize and truncate clipboard content if too large.

    Args:
        content: Raw clipboard content
        max_size: Maximum allowed size

    Returns:
        Tuple of (sanitized content, was_truncated)
    """
    if not content:
        return "", False

    # Strip leading/trailing whitespace
    content = content.strip()

    # Remove null bytes and other control characters (except newlines/tabs)
    content = ''.join(c for c in content if c == '\n' or c == '\t' or (ord(c) >= 32 and ord(c) < 127) or ord(c) >= 160)

    # Truncate if too large
    if len(content) > max_size:
        # Try to truncate at a natural boundary (line break)
        truncated = content[:max_size]
        last_newline = truncated.rfind('\n')
        if last_newline > max_size * 0.8:  # If we can keep 80%+, truncate at line
            truncated = truncated[:last_newline]
        return truncated + "\n\n[... content truncated ...]", True

    return content, False


def get_clipboard_context() -> dict:
    """
    Get full clipboard context for prompt enrichment.

    Returns:
        Dict with keys:
            - content: The clipboard content (sanitized)
            - content_type: One of 'code', 'url', 'path', 'text', 'empty'
            - language: Detected language (if code), None otherwise
            - truncated: Boolean, True if content was truncated
            - error: Error message if failed, None otherwise
    """
    try:
        raw_content = get_clipboard()
        content_type = detect_content_type(raw_content)

        if content_type == "empty":
            return {
                "content": "",
                "content_type": "empty",
                "language": None,
                "truncated": False,
                "error": None
            }

        sanitized, truncated = sanitize_content(raw_content)
        language = detect_code_language(sanitized) if content_type == "code" else None

        return {
            "content": sanitized,
            "content_type": content_type,
            "language": language,
            "truncated": truncated,
            "error": None
        }
    except ClipboardError as e:
        return {
            "content": "",
            "content_type": "empty",
            "language": None,
            "truncated": False,
            "error": str(e)
        }


def format_clipboard_for_prompt(ctx: dict) -> str:
    """
    Format clipboard context for inclusion in a prompt.

    Args:
        ctx: Context dict from get_clipboard_context()

    Returns:
        Formatted string ready for prompt inclusion
    """
    if ctx.get("error"):
        return f"[Clipboard unavailable: {ctx['error']}]"

    if ctx["content_type"] == "empty":
        return "[Clipboard is empty]"

    content_type = ctx["content_type"]
    content = ctx["content"]

    if content_type == "url":
        return f"[Clipboard contains URL: {content}]"

    if content_type == "path":
        return f"[Clipboard contains file path: {content}]"

    if content_type == "code":
        lang = ctx.get("language") or "unknown"
        header = f"[Clipboard contains {lang} code]"
        if ctx["truncated"]:
            header += " (truncated)"
        return f"{header}\n```{lang}\n{content}\n```"

    # Plain text
    header = "[Clipboard content]"
    if ctx["truncated"]:
        header += " (truncated)"
    return f"{header}\n{content}"


# === CLI for testing ===

if __name__ == "__main__":
    print("Testing clipboard context...")
    print("=" * 50)

    ctx = get_clipboard_context()

    if ctx["error"]:
        print(f"Error: {ctx['error']}")
    else:
        print(f"Content type: {ctx['content_type']}")
        if ctx["language"]:
            print(f"Language: {ctx['language']}")
        print(f"Truncated: {ctx['truncated']}")
        print(f"Content length: {len(ctx['content'])} chars")
        print("-" * 50)
        print("Formatted for prompt:")
        print("-" * 50)
        print(format_clipboard_for_prompt(ctx))
