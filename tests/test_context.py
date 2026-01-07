"""
Clipboard context tests - verify clipboard reading and content detection.

"Whatever exists without my knowledge exists without my consent."
"""

import pytest
from unittest.mock import patch, MagicMock

from src.context import (
    get_clipboard,
    detect_content_type,
    detect_code_language,
    sanitize_content,
    get_clipboard_context,
    format_clipboard_for_prompt,
    ClipboardError,
    MAX_CLIPBOARD_SIZE,
    _looks_like_url,
    _looks_like_path,
    _looks_like_code,
)


# === Content Type Detection ===

class TestDetectContentType:
    """Test content type detection."""

    def test_empty_content(self):
        assert detect_content_type("") == "empty"
        assert detect_content_type("   ") == "empty"
        assert detect_content_type(None) == "empty"

    def test_url_detection(self):
        assert detect_content_type("https://example.com") == "url"
        assert detect_content_type("http://localhost:3000/api") == "url"
        assert detect_content_type("https://github.com/user/repo") == "url"

    def test_path_detection(self):
        assert detect_content_type("/Users/test/file.py") == "path"
        assert detect_content_type("~/Documents/project") == "path"
        assert detect_content_type("./src/main.py") == "path"
        assert detect_content_type("../parent/file.txt") == "path"

    def test_code_detection(self):
        python_code = """
def hello():
    return "world"
"""
        assert detect_content_type(python_code) == "code"

        js_code = """
const x = 5;
function test() {
    return x;
}
"""
        assert detect_content_type(js_code) == "code"

    def test_plain_text(self):
        assert detect_content_type("Hello, world!") == "text"
        assert detect_content_type("This is just some plain text.") == "text"


class TestLooksLikeUrl:
    """Test URL pattern matching."""

    def test_valid_urls(self):
        assert _looks_like_url("https://example.com")
        assert _looks_like_url("http://localhost:3000")
        assert _looks_like_url("https://api.github.com/repos")

    def test_invalid_urls(self):
        assert not _looks_like_url("not a url")
        assert not _looks_like_url("ftp://files.example.com")  # Only http/https
        assert not _looks_like_url("example.com")  # Missing scheme


class TestLooksLikePath:
    """Test file path pattern matching."""

    def test_absolute_paths(self):
        assert _looks_like_path("/usr/local/bin")
        assert _looks_like_path("/home/user/file.txt")

    def test_relative_paths(self):
        assert _looks_like_path("./src/main.py")
        assert _looks_like_path("../parent/file.txt")
        assert _looks_like_path("~/Documents")

    def test_not_paths(self):
        assert not _looks_like_path("just some text")
        assert not _looks_like_path("line1\nline2\nline3")  # Multiline


class TestLooksLikeCode:
    """Test code detection heuristics."""

    def test_python_code(self):
        code = """
def calculate(x, y):
    return x + y

class MyClass:
    pass
"""
        assert _looks_like_code(code)

    def test_javascript_code(self):
        code = """
const express = require('express');
function handler(req, res) {
    return res.json({ ok: true });
}
"""
        assert _looks_like_code(code)

    def test_not_code(self):
        text = """
This is a regular paragraph of text.
It has multiple lines but no code patterns.
Just English sentences.
"""
        assert not _looks_like_code(text)


# === Code Language Detection ===

class TestDetectCodeLanguage:
    """Test programming language detection."""

    def test_python(self):
        code = """
import os
from pathlib import Path

def main():
    print("Hello")
"""
        assert detect_code_language(code) == "python"

    def test_javascript(self):
        code = """
const express = require('express');
let x = 5;
const fn = () => x + 1;
"""
        assert detect_code_language(code) == "javascript"

    def test_go(self):
        code = """
package main

func main() {
    x := 5
    fmt.Println(x)
}
"""
        assert detect_code_language(code) == "go"

    def test_rust(self):
        code = """
fn main() {
    let mut x = 5;
    println!("{}", x);
}
"""
        assert detect_code_language(code) == "rust"

    def test_unknown(self):
        code = """
some random text
that doesn't match
any language patterns
"""
        assert detect_code_language(code) is None


# === Content Sanitization ===

class TestSanitizeContent:
    """Test content sanitization and truncation."""

    def test_normal_content(self):
        content = "Hello, world!"
        result, truncated = sanitize_content(content)
        assert result == "Hello, world!"
        assert not truncated

    def test_strips_whitespace(self):
        content = "   Hello   "
        result, truncated = sanitize_content(content)
        assert result == "Hello"

    def test_truncates_large_content(self):
        content = "x" * (MAX_CLIPBOARD_SIZE + 1000)
        result, truncated = sanitize_content(content)
        assert len(result) <= MAX_CLIPBOARD_SIZE + 50  # Allow for truncation message
        assert truncated
        assert "[... content truncated ...]" in result

    def test_truncates_at_line_boundary(self):
        # Create content with newlines, larger than max
        lines = ["Line " + str(i) for i in range(2000)]
        content = "\n".join(lines)
        result, truncated = sanitize_content(content, max_size=1000)
        assert truncated
        # Should end at a line boundary (before truncation message)
        assert "\n\n[... content truncated ...]" in result

    def test_removes_control_characters(self):
        content = "Hello\x00World\x01Test"
        result, truncated = sanitize_content(content)
        assert "\x00" not in result
        assert "\x01" not in result

    def test_preserves_newlines_and_tabs(self):
        content = "Line1\nLine2\tTabbed"
        result, truncated = sanitize_content(content)
        assert "\n" in result
        assert "\t" in result


# === Clipboard Reading (Mocked) ===

class TestGetClipboard:
    """Test clipboard reading with mocked subprocess."""

    @patch("src.context.subprocess.run")
    @patch("src.context.sys.platform", "darwin")
    def test_macos_pbpaste(self, mock_run):
        mock_run.return_value = MagicMock(stdout="clipboard content", returncode=0)
        result = get_clipboard()
        assert result == "clipboard content"
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["pbpaste"]

    @patch("src.context.subprocess.run")
    @patch("src.context.sys.platform", "linux")
    def test_linux_xclip(self, mock_run):
        mock_run.return_value = MagicMock(stdout="linux content", returncode=0)
        result = get_clipboard()
        assert result == "linux content"

    @patch("src.context.subprocess.run")
    @patch("src.context.sys.platform", "darwin")
    def test_timeout_error(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pbpaste", timeout=5)
        with pytest.raises(ClipboardError) as exc_info:
            get_clipboard()
        assert "timed out" in str(exc_info.value)


# === Full Context Integration ===

class TestGetClipboardContext:
    """Test full clipboard context retrieval."""

    @patch("src.context.get_clipboard")
    def test_returns_context_dict(self, mock_clipboard):
        mock_clipboard.return_value = "def hello(): pass"
        ctx = get_clipboard_context()

        assert isinstance(ctx, dict)
        assert "content" in ctx
        assert "content_type" in ctx
        assert "language" in ctx
        assert "truncated" in ctx
        assert "error" in ctx

    @patch("src.context.get_clipboard")
    def test_detects_python_code(self, mock_clipboard):
        mock_clipboard.return_value = """
import sys
def main():
    print("hello")
"""
        ctx = get_clipboard_context()
        assert ctx["content_type"] == "code"
        assert ctx["language"] == "python"

    @patch("src.context.get_clipboard")
    def test_handles_empty_clipboard(self, mock_clipboard):
        mock_clipboard.return_value = ""
        ctx = get_clipboard_context()
        assert ctx["content_type"] == "empty"
        assert ctx["content"] == ""

    @patch("src.context.get_clipboard")
    def test_handles_clipboard_error(self, mock_clipboard):
        mock_clipboard.side_effect = ClipboardError("No clipboard available")
        ctx = get_clipboard_context()
        assert ctx["error"] == "No clipboard available"
        assert ctx["content_type"] == "empty"


# === Prompt Formatting ===

class TestFormatClipboardForPrompt:
    """Test clipboard formatting for prompt inclusion."""

    def test_empty_clipboard(self):
        ctx = {"content": "", "content_type": "empty", "language": None, "truncated": False, "error": None}
        result = format_clipboard_for_prompt(ctx)
        assert result == "[Clipboard is empty]"

    def test_error_clipboard(self):
        ctx = {"content": "", "content_type": "empty", "language": None, "truncated": False, "error": "Failed to read"}
        result = format_clipboard_for_prompt(ctx)
        assert "[Clipboard unavailable: Failed to read]" in result

    def test_url_formatting(self):
        ctx = {"content": "https://example.com", "content_type": "url", "language": None, "truncated": False, "error": None}
        result = format_clipboard_for_prompt(ctx)
        assert "[Clipboard contains URL:" in result
        assert "https://example.com" in result

    def test_path_formatting(self):
        ctx = {"content": "/path/to/file.py", "content_type": "path", "language": None, "truncated": False, "error": None}
        result = format_clipboard_for_prompt(ctx)
        assert "[Clipboard contains file path:" in result

    def test_code_formatting(self):
        ctx = {"content": "def hello(): pass", "content_type": "code", "language": "python", "truncated": False, "error": None}
        result = format_clipboard_for_prompt(ctx)
        assert "[Clipboard contains python code]" in result
        assert "```python" in result
        assert "def hello(): pass" in result
        assert "```" in result

    def test_truncated_indicator(self):
        ctx = {"content": "long text...", "content_type": "code", "language": "python", "truncated": True, "error": None}
        result = format_clipboard_for_prompt(ctx)
        assert "(truncated)" in result

    def test_plain_text_formatting(self):
        ctx = {"content": "Hello, world!", "content_type": "text", "language": None, "truncated": False, "error": None}
        result = format_clipboard_for_prompt(ctx)
        assert "[Clipboard content]" in result
        assert "Hello, world!" in result
