"""
v0.6 Agent Routing - Route commands to specialized agents.

Maps command tags to agent types, each with tailored prompts and configurations.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Set


class AgentType(Enum):
    """Specialized agent types for different tasks."""
    TESTER = "tester"
    IMPLEMENTER = "implementer"
    DEPLOYER = "deployer"
    RESEARCHER = "researcher"
    DEVOPS = "devops"
    GENERAL = "general"


@dataclass
class AgentConfig:
    """Configuration for a specialized agent."""
    agent_type: AgentType
    name: str
    description: str
    meta_prompt_suffix: str
    cli_flags: List[str]  # Additional Claude CLI flags
    priority_tags: Set[str]  # Tags that route to this agent


# Agent configurations
AGENT_CONFIGS = {
    AgentType.TESTER: AgentConfig(
        agent_type=AgentType.TESTER,
        name="Tester",
        description="Testing and quality assurance specialist",
        meta_prompt_suffix="""
Focus on testing. When reporting:
- Number of tests run/passed/failed
- Any test coverage changes
- Specific failures with file:line references
""",
        cli_flags=[],
        priority_tags={"testing", "types", "lint", "format", "security", "quality", "review"}
    ),

    AgentType.IMPLEMENTER: AgentConfig(
        agent_type=AgentType.IMPLEMENTER,
        name="Implementer",
        description="Code implementation and refactoring specialist",
        meta_prompt_suffix="""
Focus on implementation. When reporting:
- Files changed with brief description
- Any new functions/classes added
- Breaking changes if any
""",
        cli_flags=[],
        priority_tags={"refactor", "simplify", "extract", "rename", "creation", "dead-code", "duplication", "generate"}
    ),

    AgentType.DEPLOYER: AgentConfig(
        agent_type=AgentType.DEPLOYER,
        name="Deployer",
        description="Deployment and release specialist",
        meta_prompt_suffix="""
Focus on deployment. When reporting:
- Deployment target (staging/production)
- Version or commit deployed
- Any rollback instructions if needed
Be extra cautious with production deployments.
""",
        cli_flags=[],
        priority_tags={"deploy", "production", "staging", "ci", "devops", "docker", "infrastructure", "push", "pr", "commit", "git"}
    ),

    AgentType.RESEARCHER: AgentConfig(
        agent_type=AgentType.RESEARCHER,
        name="Researcher",
        description="Code exploration and documentation specialist",
        meta_prompt_suffix="""
Focus on explanation. When reporting:
- Key insights discovered
- Relevant files/functions found
- Suggested next steps
""",
        cli_flags=[],
        priority_tags={"explain", "survey", "research", "audit", "architecture", "guidance", "docs", "readme"}
    ),

    AgentType.DEVOPS: AgentConfig(
        agent_type=AgentType.DEVOPS,
        name="DevOps",
        description="Build, run, and infrastructure specialist",
        meta_prompt_suffix="""
Focus on operations. When reporting:
- Service/process status
- Any errors or warnings
- Resource usage if relevant
""",
        cli_flags=[],
        priority_tags={"build", "run", "status", "logs", "debug", "env", "config", "processes", "daemon", "watch", "start", "setup", "init"}
    ),

    AgentType.GENERAL: AgentConfig(
        agent_type=AgentType.GENERAL,
        name="General",
        description="General-purpose assistant",
        meta_prompt_suffix="",
        cli_flags=[],
        priority_tags=set()  # Fallback agent
    ),
}


class AgentRouter:
    """Routes commands to appropriate specialized agents based on tags."""

    def __init__(self):
        self._tag_to_agent: dict[str, AgentType] = {}
        self._build_tag_index()

    def _build_tag_index(self):
        """Build reverse index from tags to agents."""
        for agent_type, config in AGENT_CONFIGS.items():
            for tag in config.priority_tags:
                self._tag_to_agent[tag] = agent_type

    def route(self, tags: List[str]) -> AgentConfig:
        """
        Route to appropriate agent based on command tags.

        Uses priority matching:
        1. First matching tag wins
        2. Falls back to GENERAL if no match

        Args:
            tags: List of tags from the command

        Returns:
            AgentConfig for the matched agent
        """
        for tag in tags:
            if tag in self._tag_to_agent:
                agent_type = self._tag_to_agent[tag]
                return AGENT_CONFIGS[agent_type]

        return AGENT_CONFIGS[AgentType.GENERAL]

    def route_by_semantic(self, intent: str) -> AgentConfig:
        """
        Route based on semantic intent analysis.

        Uses keyword matching on the intent string to determine agent type.
        Useful when command doesn't have explicit tags.

        Args:
            intent: Semantic intent string (e.g., "run tests", "deploy to prod")

        Returns:
            AgentConfig for the matched agent
        """
        intent_lower = intent.lower()

        # Keyword patterns for each agent (order matters - more specific first)
        patterns = {
            AgentType.DEPLOYER: ["deploy", "push", "commit", "release", "ship", "staging", "production", " pr", "merge"],
            AgentType.TESTER: ["test", "lint", "type check", "types", "format", "quality", "coverage"],
            AgentType.IMPLEMENTER: ["implement", "refactor", "add", "create", "fix", "update", "rename", "extract"],
            AgentType.RESEARCHER: ["explain", "find", "search", "show", "what", "why", "how", "document"],
            AgentType.DEVOPS: ["run", "start", "stop", "status", "logs", "build", "install", "setup", "config"],
        }

        for agent_type, keywords in patterns.items():
            for keyword in keywords:
                if keyword in intent_lower:
                    return AGENT_CONFIGS[agent_type]

        return AGENT_CONFIGS[AgentType.GENERAL]

    def get_enhanced_prompt(self, base_prompt: str, agent_config: AgentConfig) -> str:
        """
        Enhance prompt with agent-specific suffix.

        Args:
            base_prompt: Original command expansion
            agent_config: Agent configuration

        Returns:
            Enhanced prompt with agent-specific instructions
        """
        if agent_config.meta_prompt_suffix:
            return f"{base_prompt}\n\n{agent_config.meta_prompt_suffix}"
        return base_prompt

    def get_cli_flags(self, agent_config: AgentConfig) -> List[str]:
        """Get additional CLI flags for the agent."""
        return agent_config.cli_flags.copy()


# Global router instance
_router: Optional[AgentRouter] = None


def get_router() -> AgentRouter:
    """Get or create the global agent router."""
    global _router
    if _router is None:
        _router = AgentRouter()
    return _router


def route_command(command: dict) -> AgentConfig:
    """
    Convenience function to route a command to an agent.

    Args:
        command: Command dict with 'tags' field

    Returns:
        AgentConfig for the matched agent
    """
    router = get_router()
    tags = command.get("tags", [])
    return router.route(tags)


def route_intent(intent: str) -> AgentConfig:
    """
    Convenience function to route by semantic intent.

    Args:
        intent: User's intent string

    Returns:
        AgentConfig for the matched agent
    """
    router = get_router()
    return router.route_by_semantic(intent)
