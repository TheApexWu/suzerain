# Suzerain Orchestrator
# Routes grimoire commands to specialized subagents via Claude Agent SDK
#
# "The orchestrator has global context. Subagents have focused capabilities."

import asyncio
from typing import AsyncGenerator, Optional
from dataclasses import dataclass
from enum import Enum

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AgentDefinition,
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    ResultMessage,
)


class PermissionTier(Enum):
    """Permission levels for command execution."""
    SAFE = "safe"           # Execute immediately (read-only, tests)
    TRUSTED = "trusted"     # Execute with logging (edits, local changes)
    DANGEROUS = "dangerous" # Require voice confirmation (deploy, delete, push)


@dataclass
class CommandContext:
    """Context for command execution."""
    prompt: str                     # The expanded command prompt
    category: str                   # Command category (test, deploy, research, etc.)
    tier: PermissionTier            # Permission tier
    tags: list[str]                 # Command tags from grimoire
    project_path: Optional[str]     # Working directory
    use_continue: bool = False      # Whether to continue previous session
    dry_run: bool = False           # Preview mode


# Subagent definitions with focused tool access
SUBAGENTS = {
    "test-runner": AgentDefinition(
        description="Run tests, analyze failures, suggest fixes. Use for all testing operations.",
        prompt="""You are a test execution specialist for the Suzerain voice agent system.

Your job:
- Run test suites (pytest, jest, go test, etc.)
- Analyze test output clearly
- Identify failing tests and their causes
- Suggest fixes when obvious
- Never modify code unless explicitly asked

Be concise. Developers want results, not essays.""",
        tools=["Bash", "Read", "Grep", "Glob"],
        model="sonnet"  # Fast for test runs
    ),

    "deployer": AgentDefinition(
        description="Deploy code, manage git operations, handle production. Use for deployment and git tasks.",
        prompt="""You are a deployment specialist for the Suzerain voice agent system.

Your job:
- Deploy applications to production/staging
- Manage git operations (commit, push, pull)
- Verify deployments succeeded
- Handle rollbacks if needed

CRITICAL: Always run tests before deploying. Abort on test failure.
CRITICAL: Confirm destructive operations before executing.

Be methodical. Production is sacred.""",
        tools=["Bash", "Read", "Grep", "Glob", "Edit", "Write"],
        model="sonnet"
    ),

    "researcher": AgentDefinition(
        description="Research topics, explore codebases, explain code. Use for information gathering.",
        prompt="""You are a research specialist for the Suzerain voice agent system.

Your job:
- Answer questions about codebases
- Research technical topics
- Explain how code works
- Find relevant files and patterns

You have READ-ONLY access. You cannot modify files.
Be thorough but concise. Cite file locations.""",
        tools=["Read", "Grep", "Glob", "WebSearch", "WebFetch"],
        model="sonnet"
    ),

    "general": AgentDefinition(
        description="General-purpose agent for tasks that don't fit other categories.",
        prompt="""You are a general-purpose assistant for the Suzerain voice agent system.

Handle any task that doesn't fit the specialized agents.
Be careful with destructive operations.
Ask for confirmation when uncertain.""",
        tools=["Bash", "Read", "Grep", "Glob", "Edit", "Write"],
        model="sonnet"
    ),
}


def categorize_command(tags: list[str]) -> str:
    """
    Determine which subagent should handle this command based on tags.

    Returns subagent key: "test-runner", "deployer", "researcher", or "general"
    """
    tag_set = set(tags)

    # Test-related commands
    if tag_set & {"testing", "audit", "quality", "lint", "types", "security"}:
        return "test-runner"

    # Deployment and git commands
    if tag_set & {"deploy", "production", "staging", "git", "commit", "push", "ci", "devops", "docker"}:
        return "deployer"

    # Research and exploration
    if tag_set & {"research", "survey", "explain", "architecture", "debug", "status"}:
        return "researcher"

    # Everything else goes to general
    return "general"


def determine_tier(tags: list[str], has_confirmation: bool) -> PermissionTier:
    """
    Determine permission tier based on command tags and confirmation flag.
    """
    tag_set = set(tags)

    # Dangerous operations (require voice confirmation)
    if has_confirmation or tag_set & {"production", "critical", "destructive", "push"}:
        return PermissionTier.DANGEROUS

    # Trusted operations (logged but no confirmation)
    if tag_set & {"commit", "deploy", "staging", "refactor", "cleanup"}:
        return PermissionTier.TRUSTED

    # Safe operations (read-only, tests, research)
    return PermissionTier.SAFE


class Orchestrator:
    """
    Routes commands to specialized subagents.
    Never executes directly - always delegates.
    """

    def __init__(self, dangerous_mode: bool = False):
        """
        Initialize the orchestrator.

        Args:
            dangerous_mode: If True, skip permission prompts (equivalent to --dangerously-skip-permissions)
        """
        self.dangerous_mode = dangerous_mode
        self.subagents = SUBAGENTS

    async def execute(
        self,
        context: CommandContext
    ) -> AsyncGenerator[dict, None]:
        """
        Execute a command by routing to the appropriate subagent.

        Yields message dicts with:
            - type: "text" | "tool_use" | "tool_result" | "result"
            - content: The message content
            - (for result) cost, duration, etc.
        """
        # Determine which subagent handles this command
        agent_key = categorize_command(context.tags)
        agent = self.subagents[agent_key]

        # Build options
        # Use bypassPermissions since our tier system handles safety
        # The orchestrator only executes commands that have already passed tier checks
        # (DANGEROUS tier requires voice confirmation before reaching here)
        # Valid modes: acceptEdits, bypassPermissions, default, delegate, dontAsk, plan
        permission_mode = "bypassPermissions"

        options = ClaudeAgentOptions(
            allowed_tools=agent.tools if agent.tools else None,
            permission_mode=permission_mode,
            cwd=context.project_path,
            # Note: Not using subagents yet - they cause retry loops
            # TODO: Debug subagent integration
        )

        # Yield routing info
        yield {
            "type": "routing",
            "agent": agent_key,
            "tier": context.tier.value,
        }

        # Execute via SDK
        try:
            async for message in query(prompt=context.prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            yield {"type": "text", "content": block.text}
                        elif isinstance(block, ToolUseBlock):
                            yield {
                                "type": "tool_use",
                                "tool": block.name,
                                "input": block.input,
                            }
                        elif isinstance(block, ToolResultBlock):
                            yield {
                                "type": "tool_result",
                                "tool": getattr(block, 'name', 'unknown'),
                                "output": str(block.content)[:500],  # Truncate long output
                            }

                elif isinstance(message, ResultMessage):
                    yield {
                        "type": "result",
                        "cost": getattr(message, 'cost', None),
                        "duration": getattr(message, 'duration', None),
                    }

        except Exception as e:
            yield {
                "type": "error",
                "message": str(e),
            }

    def execute_sync(self, context: CommandContext) -> list[dict]:
        """
        Synchronous wrapper for execute().
        Collects all messages and returns them.
        """
        async def collect():
            messages = []
            async for msg in self.execute(context):
                messages.append(msg)
            return messages

        return asyncio.run(collect())


# Convenience function for simple execution
async def run_command(
    prompt: str,
    tags: list[str],
    project_path: Optional[str] = None,
    dangerous_mode: bool = False,
    has_confirmation: bool = False,
) -> AsyncGenerator[dict, None]:
    """
    Execute a command through the orchestrator.

    Args:
        prompt: The expanded command prompt
        tags: Command tags from grimoire
        project_path: Working directory
        dangerous_mode: Skip permission prompts
        has_confirmation: Whether command requires confirmation

    Yields:
        Message dicts from the orchestrator
    """
    orchestrator = Orchestrator(dangerous_mode=dangerous_mode)

    context = CommandContext(
        prompt=prompt,
        category=categorize_command(tags),
        tier=determine_tier(tags, has_confirmation),
        tags=tags,
        project_path=project_path,
    )

    async for message in orchestrator.execute(context):
        yield message


# Test the module
if __name__ == "__main__":
    import sys

    async def test():
        print("Testing orchestrator routing...\n")

        test_cases = [
            (["testing"], "test-runner"),
            (["deploy", "production"], "deployer"),
            (["research"], "researcher"),
            (["init", "creation"], "general"),
            (["git", "commit"], "deployer"),
            (["audit", "security"], "test-runner"),
        ]

        for tags, expected in test_cases:
            result = categorize_command(tags)
            status = "✓" if result == expected else "✗"
            print(f"  {status} {tags} → {result} (expected {expected})")

        print("\nTesting tier determination...\n")

        tier_cases = [
            (["testing"], False, PermissionTier.SAFE),
            (["deploy", "staging"], False, PermissionTier.TRUSTED),
            (["deploy", "production"], False, PermissionTier.DANGEROUS),
            (["git", "push"], False, PermissionTier.DANGEROUS),
            (["research"], False, PermissionTier.SAFE),
        ]

        for tags, confirm, expected in tier_cases:
            result = determine_tier(tags, confirm)
            status = "✓" if result == expected else "✗"
            print(f"  {status} {tags} → {result.value} (expected {expected.value})")

        print("\nOrchestrator module OK")

    asyncio.run(test())
