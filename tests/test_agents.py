"""
Agent routing unit tests - verify commands route to correct agents.

They rode on.
"""

import pytest
from src.agents import (
    AgentRouter,
    AgentType,
    AgentConfig,
    AGENT_CONFIGS,
    route_command,
    route_intent,
    get_router,
)


class TestAgentType:
    """Test AgentType enum."""

    def test_all_types_exist(self):
        """Verify all expected agent types exist."""
        expected = ["TESTER", "IMPLEMENTER", "DEPLOYER", "RESEARCHER", "DEVOPS", "GENERAL"]
        for name in expected:
            assert hasattr(AgentType, name)

    def test_type_values(self):
        """Verify agent type values are strings."""
        for agent_type in AgentType:
            assert isinstance(agent_type.value, str)


class TestAgentConfig:
    """Test agent configurations."""

    def test_all_types_have_config(self):
        """Verify all agent types have a configuration."""
        for agent_type in AgentType:
            assert agent_type in AGENT_CONFIGS

    def test_config_has_required_fields(self):
        """Verify each config has required fields."""
        for agent_type, config in AGENT_CONFIGS.items():
            assert isinstance(config, AgentConfig)
            assert config.name
            assert config.description
            assert isinstance(config.cli_flags, list)
            assert isinstance(config.priority_tags, set)


class TestAgentRouter:
    """Test agent routing logic."""

    def test_router_creation(self):
        """Verify router can be created."""
        router = AgentRouter()
        assert router is not None

    def test_singleton_router(self):
        """Verify get_router returns same instance."""
        router1 = get_router()
        router2 = get_router()
        assert router1 is router2

    def test_route_testing_tags(self):
        """Verify testing tags route to Tester agent."""
        router = AgentRouter()
        for tag in ["testing", "lint", "types", "quality"]:
            config = router.route([tag])
            assert config.agent_type == AgentType.TESTER, f"Tag '{tag}' should route to TESTER"

    def test_route_deploy_tags(self):
        """Verify deployment tags route to Deployer agent."""
        router = AgentRouter()
        for tag in ["deploy", "production", "staging", "ci"]:
            config = router.route([tag])
            assert config.agent_type == AgentType.DEPLOYER, f"Tag '{tag}' should route to DEPLOYER"

    def test_route_implement_tags(self):
        """Verify implementation tags route to Implementer agent."""
        router = AgentRouter()
        for tag in ["refactor", "simplify", "extract", "creation"]:
            config = router.route([tag])
            assert config.agent_type == AgentType.IMPLEMENTER, f"Tag '{tag}' should route to IMPLEMENTER"

    def test_route_research_tags(self):
        """Verify research tags route to Researcher agent."""
        router = AgentRouter()
        for tag in ["explain", "survey", "audit", "docs"]:
            config = router.route([tag])
            assert config.agent_type == AgentType.RESEARCHER, f"Tag '{tag}' should route to RESEARCHER"

    def test_route_devops_tags(self):
        """Verify devops tags route to DevOps agent."""
        router = AgentRouter()
        for tag in ["build", "run", "status", "logs"]:
            config = router.route([tag])
            assert config.agent_type == AgentType.DEVOPS, f"Tag '{tag}' should route to DEVOPS"

    def test_route_unknown_tag(self):
        """Verify unknown tags route to General agent."""
        router = AgentRouter()
        config = router.route(["unknown_tag_xyz"])
        assert config.agent_type == AgentType.GENERAL

    def test_route_empty_tags(self):
        """Verify empty tags route to General agent."""
        router = AgentRouter()
        config = router.route([])
        assert config.agent_type == AgentType.GENERAL

    def test_route_first_tag_wins(self):
        """Verify first matching tag determines agent."""
        router = AgentRouter()
        # Testing comes first, so should route to Tester
        config = router.route(["testing", "deploy"])
        assert config.agent_type == AgentType.TESTER


class TestSemanticRouting:
    """Test semantic intent-based routing."""

    def test_route_test_intent(self):
        """Verify test-related intents route to Tester."""
        router = AgentRouter()
        for intent in ["run the tests", "check types", "lint the code"]:
            config = router.route_by_semantic(intent)
            assert config.agent_type == AgentType.TESTER, f"'{intent}' should route to TESTER"

    def test_route_deploy_intent(self):
        """Verify deploy-related intents route to Deployer."""
        router = AgentRouter()
        for intent in ["deploy to production", "push the changes", "ship to staging"]:
            config = router.route_by_semantic(intent)
            assert config.agent_type == AgentType.DEPLOYER, f"'{intent}' should route to DEPLOYER"

    def test_route_implement_intent(self):
        """Verify implementation intents route to Implementer."""
        router = AgentRouter()
        for intent in ["refactor this function", "add a new feature", "fix the bug"]:
            config = router.route_by_semantic(intent)
            assert config.agent_type == AgentType.IMPLEMENTER, f"'{intent}' should route to IMPLEMENTER"

    def test_route_research_intent(self):
        """Verify research intents route to Researcher."""
        router = AgentRouter()
        for intent in ["explain this code", "what does this do", "find the config"]:
            config = router.route_by_semantic(intent)
            assert config.agent_type == AgentType.RESEARCHER, f"'{intent}' should route to RESEARCHER"

    def test_route_devops_intent(self):
        """Verify devops intents route to DevOps."""
        router = AgentRouter()
        for intent in ["run the server", "start the app", "check status"]:
            config = router.route_by_semantic(intent)
            assert config.agent_type == AgentType.DEVOPS, f"'{intent}' should route to DEVOPS"

    def test_route_unknown_intent(self):
        """Verify unknown intents route to General."""
        router = AgentRouter()
        config = router.route_by_semantic("random gibberish xyz")
        assert config.agent_type == AgentType.GENERAL


class TestPromptEnhancement:
    """Test prompt enhancement with agent-specific instructions."""

    def test_enhance_adds_suffix(self):
        """Verify enhancement adds agent-specific suffix."""
        router = AgentRouter()
        config = AGENT_CONFIGS[AgentType.TESTER]
        enhanced = router.get_enhanced_prompt("Run tests", config)
        assert "Run tests" in enhanced
        assert config.meta_prompt_suffix in enhanced

    def test_general_no_enhancement(self):
        """Verify General agent doesn't modify prompt."""
        router = AgentRouter()
        config = AGENT_CONFIGS[AgentType.GENERAL]
        enhanced = router.get_enhanced_prompt("Do something", config)
        assert enhanced == "Do something"


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_route_command(self):
        """Verify route_command works with command dict."""
        command = {"phrase": "run tests", "tags": ["testing"]}
        config = route_command(command)
        assert config.agent_type == AgentType.TESTER

    def test_route_command_no_tags(self):
        """Verify route_command handles missing tags."""
        command = {"phrase": "do something"}
        config = route_command(command)
        assert config.agent_type == AgentType.GENERAL

    def test_route_intent(self):
        """Verify route_intent works."""
        config = route_intent("deploy to production")
        assert config.agent_type == AgentType.DEPLOYER
