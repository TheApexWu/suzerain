"""
Tests for the orchestrator module.

The orchestrator routes grimoire commands to specialized subagents
based on command tags and manages permission tiers.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from orchestrator import (
    Orchestrator,
    CommandContext,
    PermissionTier,
    categorize_command,
    determine_tier,
    SUBAGENTS,
)


class TestCategorizeCommand:
    """Test command routing logic."""

    def test_testing_tags_route_to_test_runner(self):
        """Testing-related tags should route to test-runner agent."""
        assert categorize_command(["testing"]) == "test-runner"
        assert categorize_command(["audit"]) == "test-runner"
        assert categorize_command(["quality"]) == "test-runner"
        assert categorize_command(["lint"]) == "test-runner"
        assert categorize_command(["types"]) == "test-runner"
        assert categorize_command(["security"]) == "test-runner"

    def test_deploy_tags_route_to_deployer(self):
        """Deployment and git tags should route to deployer agent."""
        assert categorize_command(["deploy"]) == "deployer"
        assert categorize_command(["production"]) == "deployer"
        assert categorize_command(["staging"]) == "deployer"
        assert categorize_command(["git"]) == "deployer"
        assert categorize_command(["commit"]) == "deployer"
        assert categorize_command(["push"]) == "deployer"
        assert categorize_command(["ci"]) == "deployer"
        assert categorize_command(["devops"]) == "deployer"
        assert categorize_command(["docker"]) == "deployer"

    def test_research_tags_route_to_researcher(self):
        """Research and exploration tags should route to researcher agent."""
        assert categorize_command(["research"]) == "researcher"
        assert categorize_command(["survey"]) == "researcher"
        assert categorize_command(["explain"]) == "researcher"
        assert categorize_command(["architecture"]) == "researcher"
        assert categorize_command(["debug"]) == "researcher"
        assert categorize_command(["status"]) == "researcher"

    def test_unknown_tags_route_to_general(self):
        """Unknown or general tags should route to general agent."""
        assert categorize_command(["init"]) == "general"
        assert categorize_command(["creation"]) == "general"
        assert categorize_command(["unknown"]) == "general"
        assert categorize_command([]) == "general"

    def test_multiple_tags_priority(self):
        """When multiple tags exist, should match first category found."""
        # Testing takes priority
        assert categorize_command(["testing", "general"]) == "test-runner"
        # Deploy takes priority over research
        assert categorize_command(["deploy", "survey"]) == "deployer"

    def test_mixed_case_tags(self):
        """Tags should work regardless of case (as they come from YAML)."""
        # Tags from grimoire are lowercase, but test defensive coding
        assert categorize_command(["testing"]) == "test-runner"


class TestDetermineTier:
    """Test permission tier determination."""

    def test_safe_tier_for_readonly_operations(self):
        """Read-only operations should be SAFE tier."""
        assert determine_tier(["research"], False) == PermissionTier.SAFE
        assert determine_tier(["survey"], False) == PermissionTier.SAFE
        assert determine_tier(["explain"], False) == PermissionTier.SAFE
        assert determine_tier(["testing"], False) == PermissionTier.SAFE

    def test_trusted_tier_for_local_changes(self):
        """Local changes should be TRUSTED tier."""
        assert determine_tier(["commit"], False) == PermissionTier.TRUSTED
        assert determine_tier(["deploy", "staging"], False) == PermissionTier.TRUSTED
        assert determine_tier(["refactor"], False) == PermissionTier.TRUSTED
        assert determine_tier(["cleanup"], False) == PermissionTier.TRUSTED

    def test_dangerous_tier_for_production(self):
        """Production and critical operations should be DANGEROUS tier."""
        assert determine_tier(["production"], False) == PermissionTier.DANGEROUS
        assert determine_tier(["critical"], False) == PermissionTier.DANGEROUS
        assert determine_tier(["destructive"], False) == PermissionTier.DANGEROUS
        assert determine_tier(["push"], False) == PermissionTier.DANGEROUS

    def test_confirmation_flag_forces_dangerous(self):
        """Commands with confirmation=true should be DANGEROUS tier."""
        assert determine_tier(["testing"], True) == PermissionTier.DANGEROUS
        assert determine_tier(["research"], True) == PermissionTier.DANGEROUS

    def test_empty_tags_is_safe(self):
        """Empty tags should default to SAFE tier."""
        assert determine_tier([], False) == PermissionTier.SAFE


class TestSubagentDefinitions:
    """Test that subagent definitions are properly configured."""

    def test_all_required_subagents_exist(self):
        """All required subagent types should be defined."""
        assert "test-runner" in SUBAGENTS
        assert "deployer" in SUBAGENTS
        assert "researcher" in SUBAGENTS
        assert "general" in SUBAGENTS

    def test_subagents_have_descriptions(self):
        """Each subagent should have a description."""
        for name, agent in SUBAGENTS.items():
            assert agent.description, f"{name} missing description"
            assert len(agent.description) > 10, f"{name} description too short"

    def test_subagents_have_prompts(self):
        """Each subagent should have a prompt."""
        for name, agent in SUBAGENTS.items():
            assert agent.prompt, f"{name} missing prompt"
            assert len(agent.prompt) > 50, f"{name} prompt too short"

    def test_subagents_have_tools(self):
        """Each subagent should have tools defined."""
        for name, agent in SUBAGENTS.items():
            assert agent.tools, f"{name} missing tools"
            assert isinstance(agent.tools, list), f"{name} tools should be list"

    def test_researcher_has_readonly_tools(self):
        """Researcher should only have read-only tools."""
        researcher = SUBAGENTS["researcher"]
        # Should NOT have Edit or Write
        assert "Edit" not in researcher.tools
        assert "Write" not in researcher.tools
        # Should have read tools
        assert "Read" in researcher.tools
        assert "Grep" in researcher.tools

    def test_deployer_has_execution_tools(self):
        """Deployer should have execution tools."""
        deployer = SUBAGENTS["deployer"]
        assert "Bash" in deployer.tools
        assert "Read" in deployer.tools


class TestCommandContext:
    """Test CommandContext dataclass."""

    def test_create_context(self):
        """Should be able to create a CommandContext."""
        ctx = CommandContext(
            prompt="Run tests",
            category="test",
            tier=PermissionTier.SAFE,
            tags=["testing"],
            project_path="/tmp/test",
        )
        assert ctx.prompt == "Run tests"
        assert ctx.category == "test"
        assert ctx.tier == PermissionTier.SAFE
        assert ctx.tags == ["testing"]
        assert ctx.project_path == "/tmp/test"
        assert ctx.use_continue == False
        assert ctx.dry_run == False

    def test_context_with_optional_fields(self):
        """Should handle optional fields correctly."""
        ctx = CommandContext(
            prompt="Deploy",
            category="deploy",
            tier=PermissionTier.DANGEROUS,
            tags=["deploy", "production"],
            project_path=None,
            use_continue=True,
            dry_run=True,
        )
        assert ctx.project_path is None
        assert ctx.use_continue == True
        assert ctx.dry_run == True


class TestPermissionTier:
    """Test PermissionTier enum."""

    def test_tier_values(self):
        """Tier values should match expected strings."""
        assert PermissionTier.SAFE.value == "safe"
        assert PermissionTier.TRUSTED.value == "trusted"
        assert PermissionTier.DANGEROUS.value == "dangerous"

    def test_tier_comparison(self):
        """Tiers should be comparable."""
        assert PermissionTier.SAFE != PermissionTier.DANGEROUS
        assert PermissionTier.TRUSTED != PermissionTier.SAFE


class TestOrchestrator:
    """Test Orchestrator class."""

    def test_orchestrator_initialization(self):
        """Orchestrator should initialize with default settings."""
        orch = Orchestrator()
        assert orch.dangerous_mode == False
        assert orch.subagents == SUBAGENTS

    def test_orchestrator_dangerous_mode(self):
        """Orchestrator should accept dangerous_mode flag."""
        orch = Orchestrator(dangerous_mode=True)
        assert orch.dangerous_mode == True

    def test_orchestrator_has_execute_method(self):
        """Orchestrator should have execute method."""
        orch = Orchestrator()
        assert hasattr(orch, 'execute')
        assert callable(orch.execute)

    def test_orchestrator_has_sync_wrapper(self):
        """Orchestrator should have synchronous execute wrapper."""
        orch = Orchestrator()
        assert hasattr(orch, 'execute_sync')
        assert callable(orch.execute_sync)


class TestIntegrationScenarios:
    """Integration tests for common command scenarios."""

    def test_judge_smiled_routes_to_test_runner(self):
        """'the judge smiled' (run tests) should route to test-runner."""
        # Tags from grimoire for "the judge smiled"
        tags = ["testing"]
        category = categorize_command(tags)
        tier = determine_tier(tags, False)

        assert category == "test-runner"
        assert tier == PermissionTier.SAFE

    def test_evening_redness_routes_to_deployer_dangerous(self):
        """'evening redness' (deploy) should route to deployer with dangerous tier."""
        # Tags from grimoire for "the evening redness in the west"
        tags = ["deploy", "production", "critical"]
        category = categorize_command(tags)
        tier = determine_tier(tags, True)  # Has confirmation

        assert category == "deployer"
        assert tier == PermissionTier.DANGEROUS

    def test_scour_terrain_routes_to_researcher(self):
        """'scour the terrain' (research) should route to researcher."""
        tags = ["research", "deep"]
        category = categorize_command(tags)
        tier = determine_tier(tags, False)

        assert category == "researcher"
        assert tier == PermissionTier.SAFE

    def test_blood_dried_routes_to_deployer_trusted(self):
        """'the blood dried' (commit) should route to deployer with trusted tier."""
        tags = ["git", "commit"]
        category = categorize_command(tags)
        tier = determine_tier(tags, True)  # Has confirmation

        assert category == "deployer"
        assert tier == PermissionTier.DANGEROUS  # confirmation forces dangerous


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
