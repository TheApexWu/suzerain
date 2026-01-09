"""
Suzerain MCP Server - Voice layer for Claude Code.

Exposes Suzerain's capabilities as MCP tools that Claude Code can invoke.

Plain Mode Tools (priority):
- voice_status: Check if voice pipeline is ready
- get_transcript: Get last voice transcription
- speak_text: Text-to-speech output (macOS)

Cipher Mode Tools (optional):
- match_cipher: Match phrase to grimoire command
- expand_cipher: Expand matched command with modifiers
- list_commands: List available grimoire commands
- list_grimoires: List available grimoire files

Usage:
    # Register with Claude Code
    claude mcp add suzerain -- python /path/to/suzerain_mcp.py

    # Or via config (~/.claude.json)
    {
      "mcpServers": {
        "suzerain": {
          "command": "python",
          "args": ["/path/to/suzerain_mcp.py"]
        }
      }
    }
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

# Add src to path for imports
src_dir = Path(__file__).parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from mcp.server import Server
from mcp.types import Tool, TextContent, Resource
from mcp.server.stdio import stdio_server

# Initialize server
server = Server("suzerain")

# =============================================================================
# PLAIN MODE TOOLS - Practical voice-to-Claude functionality
# =============================================================================

@server.list_tools()
async def list_tools():
    """List all available Suzerain tools."""
    return [
        # --- Plain Mode Tools ---
        Tool(
            name="voice_status",
            description="Check if Suzerain voice pipeline is ready (microphone, STT API key, etc.)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="speak_text",
            description="Speak text aloud using system TTS (macOS 'say' command)",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to speak aloud"
                    },
                    "voice": {
                        "type": "string",
                        "description": "Voice name (optional, e.g., 'Alex', 'Samantha')",
                        "default": ""
                    },
                    "rate": {
                        "type": "integer",
                        "description": "Speech rate in words per minute (default: 175)",
                        "default": 175
                    }
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="play_sound",
            description="Play a sound effect (ping, error, complete)",
            inputSchema={
                "type": "object",
                "properties": {
                    "sound": {
                        "type": "string",
                        "enum": ["ping", "error", "complete"],
                        "description": "Sound effect to play"
                    }
                },
                "required": ["sound"]
            }
        ),

        # --- Cipher Mode Tools ---
        Tool(
            name="match_cipher",
            description="Match a spoken phrase to a grimoire command using fuzzy/semantic matching",
            inputSchema={
                "type": "object",
                "properties": {
                    "phrase": {
                        "type": "string",
                        "description": "Spoken phrase to match against grimoire"
                    },
                    "use_semantic": {
                        "type": "boolean",
                        "description": "Use semantic (embedding) matching instead of fuzzy",
                        "default": False
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Number of top matches to return",
                        "default": 1
                    }
                },
                "required": ["phrase"]
            }
        ),
        Tool(
            name="expand_cipher",
            description="Expand a matched grimoire command with modifiers into a Claude prompt",
            inputSchema={
                "type": "object",
                "properties": {
                    "phrase": {
                        "type": "string",
                        "description": "Grimoire phrase to expand"
                    },
                    "modifiers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Modifier phrases to apply (e.g., 'under the stars' for verbose)",
                        "default": []
                    }
                },
                "required": ["phrase"]
            }
        ),
        Tool(
            name="list_commands",
            description="List all commands in the current grimoire",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_expansions": {
                        "type": "boolean",
                        "description": "Include full expansion text",
                        "default": False
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="list_grimoires",
            description="List available grimoire files",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="analyze_command",
            description="Analyze a matched command for routing and permissions",
            inputSchema={
                "type": "object",
                "properties": {
                    "phrase": {
                        "type": "string",
                        "description": "Phrase to match and analyze"
                    }
                },
                "required": ["phrase"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool invocations."""

    # --- Plain Mode Tools ---

    if name == "voice_status":
        return await _voice_status()

    if name == "speak_text":
        return await _speak_text(
            arguments.get("text", ""),
            arguments.get("voice", ""),
            arguments.get("rate", 175)
        )

    if name == "play_sound":
        return await _play_sound(arguments.get("sound", "ping"))

    # --- Cipher Mode Tools ---

    if name == "match_cipher":
        return await _match_cipher(
            arguments.get("phrase", ""),
            arguments.get("use_semantic", False),
            arguments.get("top_n", 1)
        )

    if name == "expand_cipher":
        return await _expand_cipher(
            arguments.get("phrase", ""),
            arguments.get("modifiers", [])
        )

    if name == "list_commands":
        return await _list_commands(
            arguments.get("include_expansions", False)
        )

    if name == "list_grimoires":
        return await _list_grimoires()

    if name == "analyze_command":
        return await _analyze_command(arguments.get("phrase", ""))

    raise ValueError(f"Unknown tool: {name}")


# =============================================================================
# Tool Implementations
# =============================================================================

async def _voice_status():
    """Check voice pipeline readiness."""
    status = {
        "deepgram_api_key": bool(os.environ.get("DEEPGRAM_API_KEY")),
        "picovoice_key": bool(os.environ.get("PICOVOICE_ACCESS_KEY")),
        "platform": sys.platform,
        "tts_available": sys.platform == "darwin",  # macOS 'say' command
    }

    # Check PyAudio
    try:
        import pyaudio
        pa = pyaudio.PyAudio()
        device_count = pa.get_device_count()
        pa.terminate()
        status["pyaudio"] = True
        status["audio_devices"] = device_count
    except Exception as e:
        status["pyaudio"] = False
        status["pyaudio_error"] = str(e)

    ready = status["deepgram_api_key"] and status.get("pyaudio", False)
    status["ready"] = ready

    return [TextContent(
        type="text",
        text=json.dumps(status, indent=2)
    )]


async def _speak_text(text: str, voice: str = "", rate: int = 175):
    """Speak text using macOS TTS."""
    if sys.platform != "darwin":
        return [TextContent(
            type="text",
            text="Error: TTS only available on macOS"
        )]

    cmd = ["say"]
    if voice:
        cmd.extend(["-v", voice])
    if rate != 175:
        cmd.extend(["-r", str(rate)])
    cmd.append(text)

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return [TextContent(type="text", text=f"Spoke: {text[:50]}...")]
    except subprocess.CalledProcessError as e:
        return [TextContent(type="text", text=f"TTS error: {e}")]


async def _play_sound(sound: str):
    """Play a sound effect."""
    if sys.platform != "darwin":
        return [TextContent(type="text", text="Error: Sound only available on macOS")]

    # Map sound names to system sounds
    sound_map = {
        "ping": "/System/Library/Sounds/Ping.aiff",
        "error": "/System/Library/Sounds/Basso.aiff",
        "complete": "/System/Library/Sounds/Glass.aiff",
    }

    sound_file = sound_map.get(sound)
    if not sound_file:
        return [TextContent(type="text", text=f"Unknown sound: {sound}")]

    try:
        subprocess.run(["afplay", sound_file], check=True, capture_output=True)
        return [TextContent(type="text", text=f"Played: {sound}")]
    except subprocess.CalledProcessError as e:
        return [TextContent(type="text", text=f"Sound error: {e}")]


async def _match_cipher(phrase: str, use_semantic: bool = False, top_n: int = 1):
    """Match phrase to grimoire command."""
    try:
        if use_semantic:
            from semantic_parser import match_top_n
        else:
            from parser import match_top_n

        matches = match_top_n(phrase, n=top_n)

        if not matches:
            return [TextContent(
                type="text",
                text=json.dumps({"matched": False, "phrase": phrase})
            )]

        results = []
        for cmd, score in matches:
            results.append({
                "phrase": cmd.get("phrase", ""),
                "score": score,
                "tags": cmd.get("tags", []),
                "expansion": cmd.get("expansion", "")[:200] + "..." if len(cmd.get("expansion", "")) > 200 else cmd.get("expansion", "")
            })

        return [TextContent(
            type="text",
            text=json.dumps({
                "matched": True,
                "input": phrase,
                "results": results
            }, indent=2)
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"Match error: {e}")]


async def _expand_cipher(phrase: str, modifiers: list = None):
    """Expand grimoire command with modifiers."""
    try:
        from parser import match, extract_modifiers, expand_command, get_command_info

        # First match the phrase
        result = match(phrase)
        if not result:
            return [TextContent(
                type="text",
                text=json.dumps({"error": "No matching command found", "phrase": phrase})
            )]

        # Get modifier objects if modifier strings provided
        mod_objects = []
        if modifiers:
            all_mods = extract_modifiers(" ".join(modifiers))
            mod_objects = all_mods

        # Expand the command
        expansion = expand_command(result, mod_objects)

        return [TextContent(
            type="text",
            text=json.dumps({
                "phrase": result.get("phrase", ""),
                "modifiers_applied": [m.get("effect", "") for m in mod_objects],
                "expansion": expansion
            }, indent=2)
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"Expand error: {e}")]


async def _list_commands(include_expansions: bool = False):
    """List all grimoire commands."""
    try:
        from parser import list_commands

        commands = list_commands()

        result = []
        for cmd in commands:
            entry = {
                "phrase": cmd.get("phrase", ""),
                "tags": cmd.get("tags", []),
            }
            if include_expansions:
                entry["expansion"] = cmd.get("expansion", "")
            if cmd.get("requires_confirmation"):
                entry["requires_confirmation"] = True
            result.append(entry)

        return [TextContent(
            type="text",
            text=json.dumps({"commands": result, "count": len(result)}, indent=2)
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"List error: {e}")]


async def _list_grimoires():
    """List available grimoire files."""
    try:
        grimoire_dir = src_dir / "grimoire"
        user_grimoire = Path.home() / ".suzerain" / "grimoires"

        grimoires = []

        # Check packaged grimoires
        if grimoire_dir.exists():
            for f in grimoire_dir.glob("*.yaml"):
                grimoires.append({
                    "name": f.stem,
                    "path": str(f),
                    "location": "packaged"
                })

        # Check user grimoires
        if user_grimoire.exists():
            for f in user_grimoire.glob("*.yaml"):
                grimoires.append({
                    "name": f.stem,
                    "path": str(f),
                    "location": "user"
                })

        return [TextContent(
            type="text",
            text=json.dumps({"grimoires": grimoires, "count": len(grimoires)}, indent=2)
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"Grimoire list error: {e}")]


async def _analyze_command(phrase: str):
    """Analyze a command for routing and permission tier."""
    try:
        from parser import match
        from orchestrator import categorize_command, determine_tier

        match_result = match(phrase)
        if not match_result:
            return [TextContent(
                type="text",
                text=json.dumps({"error": "No matching command", "phrase": phrase})
            )]

        # match() returns (command_dict, score) tuple
        cmd, score = match_result
        tags = cmd.get("tags", [])
        has_confirmation = cmd.get("requires_confirmation", False) or cmd.get("confirmation", False)

        category = categorize_command(tags)
        tier = determine_tier(tags, has_confirmation)

        return [TextContent(
            type="text",
            text=json.dumps({
                "phrase": cmd.get("phrase", ""),
                "score": score,
                "tags": tags,
                "category": category,
                "permission_tier": tier.value if hasattr(tier, 'value') else str(tier),
                "requires_confirmation": has_confirmation,
                "expansion_preview": cmd.get("expansion", "")[:100] + "..."
            }, indent=2)
        )]
    except ImportError:
        # Orchestrator not available, return basic info
        from parser import match
        match_result = match(phrase)
        if not match_result:
            return [TextContent(
                type="text",
                text=json.dumps({"error": "No matching command", "phrase": phrase})
            )]
        cmd, score = match_result
        return [TextContent(
            type="text",
            text=json.dumps({
                "phrase": cmd.get("phrase", ""),
                "score": score,
                "tags": cmd.get("tags", []),
                "requires_confirmation": cmd.get("requires_confirmation", False) or cmd.get("confirmation", False),
            }, indent=2)
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"Analyze error: {e}")]


# =============================================================================
# Resources (optional - grimoire files as readable resources)
# =============================================================================

@server.list_resources()
async def list_resources():
    """List grimoire files as resources."""
    resources = []

    grimoire_dir = src_dir / "grimoire"
    if grimoire_dir.exists():
        for f in grimoire_dir.glob("*.yaml"):
            resources.append(Resource(
                uri=f"grimoire://{f.stem}",
                name=f"Grimoire: {f.stem}",
                description=f"Commands from {f.name}",
                mimeType="application/x-yaml"
            ))

    return resources


@server.read_resource()
async def read_resource(uri: str):
    """Read a grimoire file."""
    if uri.startswith("grimoire://"):
        name = uri.replace("grimoire://", "")
        grimoire_file = src_dir / "grimoire" / f"{name}.yaml"

        if grimoire_file.exists():
            content = grimoire_file.read_text()
            return content

    raise ValueError(f"Resource not found: {uri}")


# =============================================================================
# Main
# =============================================================================

async def main():
    """Run the MCP server."""
    async with stdio_server() as (read, write):
        await server.run(
            read,
            write,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
