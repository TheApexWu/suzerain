"""
Suzerain Caching Module - Reduce latency through intelligent caching.

"He can neither read nor write and in him broods already a taste for mindless violence."

This module provides caching for:
1. Grimoire data (already cached in parser.py, verified here)
2. Deepgram connection/auth warmup
3. Optional response caching for identical prompts

Claude Code Startup Bottleneck Analysis:
=========================================
Claude Code startup (2-19s) is the PRIMARY bottleneck. This is caused by:
- Node.js cold start
- Claude CLI initialization
- API handshake/authentication
- Model loading on Anthropic's side

What we CAN optimize locally:
- Grimoire parsing: ~5-10ms (already cached)
- Deepgram auth: ~100-200ms first call (can pre-warm)
- Network DNS resolution: ~50-100ms (can pre-resolve)

What we CANNOT optimize:
- Claude Code's internal startup
- Anthropic API latency
- Model response time

Daemon Approach (Investigated):
==============================
Keeping Claude Code "warm" is theoretically possible but complex:
1. Background process approach: Start claude with --interactive via PTY
2. Unix socket approach: Claude doesn't support socket communication
3. HTTP server approach: Claude has no built-in server mode

The claude CLI is designed for one-shot execution. Each invocation:
- Starts fresh Node.js process
- Authenticates with Anthropic
- Has no persistent connection option

RECOMMENDATION: Accept Claude startup as fixed cost. Optimize everything else.
"""

import hashlib
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from functools import lru_cache


# === Grimoire Cache (Verification) ===

def verify_grimoire_cache():
    """
    Verify that parser.py correctly caches grimoire data.

    The grimoire is already cached via _grimoire_cache global in parser.py.
    This function verifies the cache is working correctly.

    Returns:
        Dict with cache status info
    """
    from .parser import load_grimoire

    # First call - should populate cache
    start = time.perf_counter()
    grimoire1 = load_grimoire()
    first_load_ms = (time.perf_counter() - start) * 1000

    # Second call - should hit cache
    start = time.perf_counter()
    grimoire2 = load_grimoire()
    cached_load_ms = (time.perf_counter() - start) * 1000

    return {
        "cache_working": grimoire1 is grimoire2,  # Same object = cached
        "first_load_ms": first_load_ms,
        "cached_load_ms": cached_load_ms,
        "speedup_factor": first_load_ms / cached_load_ms if cached_load_ms > 0 else float('inf'),
        "command_count": len(grimoire1.get("commands", [])),
        "modifier_count": len(grimoire1.get("modifiers", [])),
    }


# === Deepgram Connection Warmup ===

@dataclass
class DeepgramWarmer:
    """
    Pre-warm Deepgram API connection to reduce first-call latency.

    Deepgram latency breakdown:
    - DNS resolution: ~50ms
    - TLS handshake: ~100ms
    - Auth validation: ~50ms

    Pre-warming does a lightweight auth check to establish connection pool.
    """

    api_key: str = field(default_factory=lambda: os.environ.get("DEEPGRAM_API_KEY", ""))
    _warmed: bool = field(default=False, init=False)
    _last_warm_time: float = field(default=0.0, init=False)
    _warm_ttl_seconds: float = field(default=300.0, init=False)  # 5 minute TTL

    def is_warmed(self) -> bool:
        """Check if connection is still warm (within TTL)."""
        if not self._warmed:
            return False
        if time.time() - self._last_warm_time > self._warm_ttl_seconds:
            self._warmed = False
            return False
        return True

    def warm(self) -> Dict[str, Any]:
        """
        Pre-warm Deepgram connection.

        Makes a minimal API call to establish connection pool.
        Uses the /projects endpoint which is lightweight.

        Returns:
            Dict with warmup status and timing
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "DEEPGRAM_API_KEY not set",
                "latency_ms": 0
            }

        # If already warm, skip
        if self.is_warmed():
            return {
                "success": True,
                "cached": True,
                "latency_ms": 0
            }

        start = time.perf_counter()

        try:
            # Use a lightweight endpoint to warm the connection
            # The projects endpoint just lists projects - minimal data
            url = "https://api.deepgram.com/v1/projects"
            headers = {
                "Authorization": f"Token {self.api_key}",
            }

            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                _ = response.read()

            latency_ms = (time.perf_counter() - start) * 1000
            self._warmed = True
            self._last_warm_time = time.time()

            return {
                "success": True,
                "cached": False,
                "latency_ms": latency_ms
            }

        except urllib.error.HTTPError as e:
            latency_ms = (time.perf_counter() - start) * 1000
            # 403 is OK - means auth worked but endpoint may be restricted
            if e.code == 403:
                self._warmed = True
                self._last_warm_time = time.time()
                return {
                    "success": True,
                    "cached": False,
                    "latency_ms": latency_ms,
                    "note": "Connection warmed (auth validated)"
                }
            return {
                "success": False,
                "error": f"HTTP {e.code}",
                "latency_ms": latency_ms
            }

        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return {
                "success": False,
                "error": str(e),
                "latency_ms": latency_ms
            }


# Global Deepgram warmer instance
_deepgram_warmer: Optional[DeepgramWarmer] = None


def get_deepgram_warmer() -> DeepgramWarmer:
    """Get or create the global Deepgram warmer instance."""
    global _deepgram_warmer
    if _deepgram_warmer is None:
        _deepgram_warmer = DeepgramWarmer()
    return _deepgram_warmer


def warmup_deepgram() -> Dict[str, Any]:
    """Convenience function to warm Deepgram connection."""
    return get_deepgram_warmer().warm()


# === Response Caching (Optional) ===

@dataclass
class ResponseCache:
    """
    Optional cache for identical prompt responses.

    Use case: If you say the same grimoire phrase twice in quick succession,
    return the cached response instead of hitting Claude again.

    This is DISABLED by default because:
    1. Claude responses can vary for same prompt
    2. Project state changes between calls
    3. Side effects matter (git commits, deploys, etc.)

    Only enable for read-only, stateless commands.
    """

    cache: Dict[str, Any] = field(default_factory=dict)
    max_entries: int = field(default=50)
    ttl_seconds: float = field(default=60.0)  # 1 minute TTL
    enabled: bool = field(default=False)  # OFF by default

    def _make_key(self, prompt: str) -> str:
        """Create cache key from prompt."""
        return hashlib.md5(prompt.encode()).hexdigest()[:16]

    def _is_cacheable(self, command: dict) -> bool:
        """
        Determine if a command's response is safe to cache.

        Only cache if:
        - Cache is enabled
        - Command has no side effects (no confirmation required)
        - Command is not a continuation
        - Command is tagged as cacheable (future feature)
        """
        if not self.enabled:
            return False
        if command.get("confirmation", False):
            return False
        if command.get("use_continue", False):
            return False
        # Future: Check for explicit "cacheable: true" tag
        # For now, only "survey" and "status" type commands would be safe
        tags = command.get("tags", [])
        safe_tags = {"survey", "status", "explain", "research"}
        return bool(set(tags) & safe_tags)

    def get(self, prompt: str, command: dict) -> Optional[str]:
        """Get cached response if available and valid."""
        if not self._is_cacheable(command):
            return None

        key = self._make_key(prompt)
        entry = self.cache.get(key)

        if entry is None:
            return None

        # Check TTL
        if time.time() - entry["timestamp"] > self.ttl_seconds:
            del self.cache[key]
            return None

        return entry["response"]

    def put(self, prompt: str, command: dict, response: str):
        """Store response in cache."""
        if not self._is_cacheable(command):
            return

        # Evict oldest if full
        if len(self.cache) >= self.max_entries:
            oldest_key = min(self.cache, key=lambda k: self.cache[k]["timestamp"])
            del self.cache[oldest_key]

        key = self._make_key(prompt)
        self.cache[key] = {
            "response": response,
            "timestamp": time.time()
        }

    def clear(self):
        """Clear all cached responses."""
        self.cache.clear()

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        return {
            "enabled": self.enabled,
            "entries": len(self.cache),
            "max_entries": self.max_entries,
            "ttl_seconds": self.ttl_seconds
        }


# Global response cache instance
_response_cache: Optional[ResponseCache] = None


def get_response_cache() -> ResponseCache:
    """Get or create the global response cache instance."""
    global _response_cache
    if _response_cache is None:
        _response_cache = ResponseCache()
    return _response_cache


# === DNS Pre-resolution ===

@lru_cache(maxsize=10)
def preresolve_host(hostname: str) -> Optional[str]:
    """
    Pre-resolve DNS for a hostname.

    Uses LRU cache to avoid repeated lookups.
    This is called during warmup to ensure DNS is cached.

    Returns:
        Resolved IP address or None if resolution failed
    """
    import socket
    try:
        result = socket.gethostbyname(hostname)
        return result
    except socket.gaierror:
        return None


def warmup_dns():
    """Pre-resolve DNS for known API endpoints."""
    hosts = [
        "api.deepgram.com",
        "api.anthropic.com",
    ]
    results = {}
    for host in hosts:
        start = time.perf_counter()
        ip = preresolve_host(host)
        latency_ms = (time.perf_counter() - start) * 1000
        results[host] = {
            "ip": ip,
            "latency_ms": latency_ms
        }
    return results


# === Warmup All ===

def warmup_all() -> Dict[str, Any]:
    """
    Perform all warmup operations.

    Call this during startup to minimize first-command latency.

    Returns:
        Dict with all warmup results
    """
    results = {
        "timestamp": time.time(),
        "components": {}
    }

    # Verify grimoire cache
    try:
        results["components"]["grimoire"] = verify_grimoire_cache()
    except Exception as e:
        results["components"]["grimoire"] = {"error": str(e)}

    # Warm Deepgram
    try:
        results["components"]["deepgram"] = warmup_deepgram()
    except Exception as e:
        results["components"]["deepgram"] = {"error": str(e)}

    # Pre-resolve DNS
    try:
        results["components"]["dns"] = warmup_dns()
    except Exception as e:
        results["components"]["dns"] = {"error": str(e)}

    return results


# === Claude Code Daemon Investigation ===

CLAUDE_DAEMON_ANALYSIS = """
CLAUDE CODE WARM PROCESS INVESTIGATION
======================================

Question: Can we keep a Claude Code process warm/ready?

APPROACHES INVESTIGATED:

1. Background Daemon (PTY)
--------------------------
   Idea: Start `claude --interactive` in background, send commands via PTY

   Findings:
   - Claude CLI has no --interactive flag
   - Each `claude -p` invocation is stateless
   - No stdin mode for continuous command input
   - Verdict: NOT POSSIBLE with current CLI

2. Unix Socket Communication
----------------------------
   Idea: Have Claude listen on a socket, send prompts via socket

   Findings:
   - Claude CLI has no socket server mode
   - No --listen or --server flags
   - Would require Claude SDK (TypeScript/Python) instead of CLI
   - Verdict: NOT POSSIBLE with CLI, possible with SDK

3. HTTP Server Mode
------------------
   Idea: Run Claude as HTTP server, POST prompts to it

   Findings:
   - Claude CLI has no HTTP server mode
   - No --serve flag
   - Verdict: NOT POSSIBLE with CLI

4. Session Continuation
----------------------
   Idea: Use --continue to maintain conversation context

   Findings:
   - --continue works but still requires full process startup
   - Each call still takes 2-19 seconds
   - Only preserves context, not process
   - Verdict: WORKS but doesn't reduce startup time

5. Process Pre-fork
------------------
   Idea: Pre-fork claude process, wait for input

   Findings:
   - Node.js doesn't support process freezing
   - Can't pause before API call
   - Verdict: NOT POSSIBLE

RECOMMENDATIONS:
================

1. Accept the 2-19s Claude startup as fixed cost
   - This is dominated by:
     a) Node.js cold start
     b) Anthropic API authentication
     c) Model warming on their end

2. Optimize everything around Claude:
   - Pre-warm Deepgram connection (saves ~100-200ms)
   - Pre-resolve DNS (saves ~50-100ms)
   - Cache grimoire parsing (saves ~5-10ms)
   - Parallelize audio processing with other prep

3. UX improvements to mask latency:
   - Immediate audio acknowledgment (already implemented)
   - Progressive feedback ("Thinking...", "Executing...")
   - Show timing breakdown to set expectations

4. Future: Consider Claude SDK instead of CLI
   - Python SDK could maintain connection pool
   - Could reduce auth overhead on repeat calls
   - Would require significant refactor

5. Future: Claude Code may add server mode
   - Watch for --serve or --interactive flags
   - Anthropic may optimize CLI cold start

ESTIMATED SAVINGS POSSIBLE:
===========================
Current latency: 2,000 - 19,000 ms (Claude) + ~500ms (other)

What we can save:
- Deepgram warmup: ~150ms
- DNS preresolve: ~100ms
- Grimoire cache: ~5ms
- Total local savings: ~255ms

This is ~5-10% of total latency. The rest is Claude/Anthropic.
"""


def get_daemon_analysis() -> str:
    """Return the daemon investigation analysis."""
    return CLAUDE_DAEMON_ANALYSIS


# === CLI ===

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("SUZERAIN CACHE STATUS")
    print("=" * 60)

    # Run warmup
    print("\nWarming up...")
    results = warmup_all()

    # Display results
    print(f"\n{'Component':<20} {'Status':<15} {'Latency':<15}")
    print("-" * 50)

    for component, data in results["components"].items():
        if "error" in data:
            status = f"ERROR: {data['error'][:20]}"
            latency = "N/A"
        elif component == "grimoire":
            status = "CACHED" if data.get("cache_working") else "NOT CACHED"
            latency = f"{data.get('cached_load_ms', 0):.2f}ms"
        elif component == "deepgram":
            status = "WARM" if data.get("success") else "FAILED"
            latency = f"{data.get('latency_ms', 0):.1f}ms"
        elif component == "dns":
            all_resolved = all(v.get("ip") for v in data.values())
            status = "RESOLVED" if all_resolved else "PARTIAL"
            total_ms = sum(v.get("latency_ms", 0) for v in data.values())
            latency = f"{total_ms:.1f}ms"
        else:
            status = "OK"
            latency = "N/A"

        print(f"  {component:<18} {status:<15} {latency:<15}")

    # Show daemon analysis if requested
    if "--daemon" in sys.argv:
        print("\n" + get_daemon_analysis())
    else:
        print("\n(Run with --daemon to see Claude Code daemon analysis)")
