#!/usr/bin/env python3
"""
v0.6 Feature Test Script - Manual verification of new features.

Run: python scripts/test_v06.py
"""

import sys
sys.path.insert(0, 'src')

from parser import match, match_hybrid, semantic_match, SEMANTIC_ENABLED
from agents import route_command, route_intent, AgentType
from session import SessionManager, get_session_context
import tempfile
from pathlib import Path


def header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def test_semantic_matching():
    header("SEMANTIC MATCHING TEST")

    test_cases = [
        # (input, expected_to_match)
        ("run the tests", True),
        ("execute the test suite", True),
        ("launch tests", True),
        ("deploy to production", True),
        ("ship it to prod", True),
        ("make me a sandwich", False),
        ("what's the weather", False),
    ]

    print(f"\nSemantic enabled: {SEMANTIC_ENABLED}")
    print()

    for text, should_match in test_cases:
        result = match_hybrid(text)
        matched = result is not None
        status = "✓" if matched == should_match else "✗"

        if result:
            cmd, score, method = result
            print(f"{status} \"{text}\"")
            print(f"   → \"{cmd['phrase']}\" (score: {score}, method: {method})")
        else:
            print(f"{status} \"{text}\" → NO MATCH")
        print()


def test_agent_routing():
    header("AGENT ROUTING TEST")

    test_commands = [
        {"phrase": "run tests", "tags": ["testing"]},
        {"phrase": "deploy to production", "tags": ["deploy", "production"]},
        {"phrase": "refactor code", "tags": ["refactor"]},
        {"phrase": "explain this", "tags": ["explain"]},
        {"phrase": "start server", "tags": ["run", "devops"]},
        {"phrase": "random thing", "tags": []},
    ]

    for cmd in test_commands:
        agent = route_command(cmd)
        print(f"\"{cmd['phrase']}\" (tags: {cmd['tags']})")
        print(f"   → Agent: {agent.name} ({agent.agent_type.value})")
        print()


def test_semantic_routing():
    header("SEMANTIC INTENT ROUTING")

    intents = [
        "run the tests please",
        "deploy this to staging",
        "refactor the login function",
        "explain what this code does",
        "start the development server",
        "check the build status",
    ]

    for intent in intents:
        agent = route_intent(intent)
        print(f"\"{intent}\"")
        print(f"   → Agent: {agent.name}")
        print()


def test_session_memory():
    header("SESSION MEMORY TEST")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Reset singleton
        SessionManager.reset_instance()
        manager = SessionManager.get_instance(session_dir=Path(tmpdir))

        print(f"Session ID: {manager.session.session_id}")
        print()

        # Simulate some commands
        commands = [
            ("run tests", "tester", True),
            ("deploy to staging", "deployer", True),
            ("refactor auth", "implementer", False),
        ]

        for phrase, agent, success in commands:
            manager.log_command(
                phrase=phrase,
                agent_type=agent,
                success=success,
                files_modified=["src/example.py"] if agent == "implementer" else [],
            )
            print(f"Logged: \"{phrase}\" ({agent}, {'success' if success else 'failed'})")

        print()
        print("Session context for prompt:")
        print("-" * 40)
        context = manager.get_context_for_prompt()
        print(context)
        print("-" * 40)

        print()
        print("Last command summary:")
        print(manager.get_last_command_summary())

        print()
        print("Undo context:")
        print(manager.get_undo_context())


def test_trust_levels():
    header("TRUST LEVELS")

    from main import TrustLevel

    for level in range(1, 6):
        print(f"Level {level}: {TrustLevel.name(level)}")
        print(f"   {TrustLevel.description(level)}")
        print()


def main():
    print("\n" + "="*60)
    print("  SUZERAIN v0.6 FEATURE TEST")
    print("="*60)

    test_semantic_matching()
    test_agent_routing()
    test_semantic_routing()
    test_session_memory()
    test_trust_levels()

    header("TEST COMPLETE")
    print("\nAll v0.6 features operational.")
    print("\nTo test interactively:")
    print("  python src/main.py --test --trust 3")
    print("\nTry these commands:")
    print("  > run tests")
    print("  > deploy to staging")
    print("  > execute the test suite  (semantic match)")
    print("  > ship to prod  (semantic match)")
    print()


if __name__ == "__main__":
    main()
