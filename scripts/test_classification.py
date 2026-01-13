#!/usr/bin/env python3
"""
Test Classification on Simulated Data

Runs the classifier on simulated user personas to validate:
1. Features discriminate between user types
2. Classification produces expected archetypes
3. Sophistication/caution scores align with persona definitions
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from parse_claude_logs import ClaudeLogParser, compute_subtle_features, classify_archetype_empirical


SIMULATED_DIR = Path.home() / ".suzerain" / "simulated"


def analyze_persona(persona_dir: Path) -> dict:
    """Analyze all sessions for a single persona."""
    parser = ClaudeLogParser()

    # Override the projects dir to use simulated data
    session_files = list(persona_dir.glob("*.jsonl"))

    if not session_files:
        return None

    for f in session_files:
        try:
            analysis = parser.parse_session(f)
            if analysis.total_tool_calls > 0:
                parser.sessions[analysis.session_id] = analysis
        except Exception as e:
            pass

    if not parser.sessions:
        return None

    profile = parser.compute_governance_profile()
    classification = classify_archetype_empirical(profile, parser)

    return {
        "persona": persona_dir.name,
        "sessions": len(parser.sessions),
        "tool_calls": profile.total_tool_calls,
        "classification": classification,
        "profile": {
            "acceptance_rate": profile.acceptance_rate,
            "bash_acceptance": profile.trust_by_tool.get('Bash', {}).get('acceptance_rate', 1.0),
            "high_risk_acceptance": profile.high_risk_acceptance,
            "low_risk_acceptance": profile.low_risk_acceptance,
        }
    }


def main():
    print("=" * 70)
    print("CLASSIFICATION TEST ON SIMULATED DATA")
    print("=" * 70)

    if not SIMULATED_DIR.exists():
        print(f"No simulated data found at {SIMULATED_DIR}")
        print("Run: python scripts/simulate_users.py")
        return

    results = []

    # Analyze each persona
    for persona_dir in sorted(SIMULATED_DIR.iterdir()):
        if not persona_dir.is_dir():
            continue

        result = analyze_persona(persona_dir)
        if result:
            results.append(result)

    if not results:
        print("No results to analyze")
        return

    # Print results table
    print("\n" + "-" * 70)
    print(f"{'Persona':<20} {'Pattern':<22} {'Archetype':<15} {'Soph':<6} {'Caut':<6}")
    print("-" * 70)

    for r in results:
        c = r['classification']
        subtle = c.get('subtle_features', {})
        print(f"{r['persona']:<20} "
              f"{c['primary_pattern']:<22} "
              f"{c['primary_archetype']:<15} "
              f"{subtle.get('sophistication_score', 0):.2f}   "
              f"{subtle.get('caution_score', 0):.2f}")

    # Detailed breakdown
    print("\n" + "=" * 70)
    print("DETAILED FEATURE ANALYSIS")
    print("=" * 70)

    for r in results:
        c = r['classification']
        p = r['profile']
        subtle = c.get('subtle_features', {})

        print(f"\n{r['persona'].upper()}")
        print(f"  Sessions: {r['sessions']}, Tool calls: {r['tool_calls']}")
        print(f"  Primary Pattern: {c['primary_pattern']} ({c['pattern_confidence']:.0%})")
        print(f"  Archetype: {c['primary_archetype']} ({c['archetype_confidence']:.0%})")
        print(f"  Key Features:")
        print(f"    Bash acceptance:     {p['bash_acceptance']:.1%}")
        print(f"    Agent spawn rate:    {subtle.get('agent_spawn_rate', 0):.1%}")
        print(f"    Tool diversity:      {subtle.get('tool_diversity', 0):.1f}")
        print(f"    Session depth:       {subtle.get('session_depth', 0):.0f}")
        print(f"    Surgical ratio:      {subtle.get('surgical_ratio', 0):.2f}")
        print(f"  Computed Scores:")
        print(f"    Sophistication:      {subtle.get('sophistication_score', 0):.2f}")
        print(f"    Caution:             {subtle.get('caution_score', 0):.2f}")

    # Summary: Pattern distribution
    print("\n" + "=" * 70)
    print("PATTERN DISTRIBUTION")
    print("=" * 70)

    patterns = defaultdict(list)
    archetypes = defaultdict(list)

    for r in results:
        patterns[r['classification']['primary_pattern']].append(r['persona'])
        archetypes[r['classification']['primary_archetype']].append(r['persona'])

    print("\nBy Primary Pattern:")
    for pattern, personas in sorted(patterns.items()):
        print(f"  {pattern}: {', '.join(personas)}")

    print("\nBy Archetype:")
    for arch, personas in sorted(archetypes.items()):
        print(f"  {arch}: {', '.join(personas)}")

    # Validation: Do features discriminate?
    print("\n" + "=" * 70)
    print("FEATURE DISCRIMINATION CHECK")
    print("=" * 70)

    # Group by expected category
    casual = ['junior_dev', 'hobbyist', 'copilot_refugee']
    power = ['senior_swe', 'staff_engineer', 'devops_sre', 'data_scientist']
    cautious = ['security_engineer', 'compliance_reviewer', 'paranoid_senior', 'prod_oncall']

    def avg_feature(personas: list, feature: str) -> float:
        vals = []
        for r in results:
            if r['persona'] in personas:
                subtle = r['classification'].get('subtle_features', {})
                vals.append(subtle.get(feature, 0))
        return sum(vals) / len(vals) if vals else 0

    print("\nSophistication Score (should vary by user type):")
    print(f"  Casual users:   {avg_feature(casual, 'sophistication_score'):.2f}")
    print(f"  Power users:    {avg_feature(power, 'sophistication_score'):.2f}")
    print(f"  Cautious users: {avg_feature(cautious, 'sophistication_score'):.2f}")

    print("\nCaution Score (should vary by user type):")
    print(f"  Casual users:   {avg_feature(casual, 'caution_score'):.2f}")
    print(f"  Power users:    {avg_feature(power, 'caution_score'):.2f}")
    print(f"  Cautious users: {avg_feature(cautious, 'caution_score'):.2f}")

    print("\nAgent Spawn Rate (power user signal):")
    print(f"  Casual users:   {avg_feature(casual, 'agent_spawn_rate'):.1%}")
    print(f"  Power users:    {avg_feature(power, 'agent_spawn_rate'):.1%}")
    print(f"  Cautious users: {avg_feature(cautious, 'agent_spawn_rate'):.1%}")

    # Verdict
    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)

    soph_casual = avg_feature(casual, 'sophistication_score')
    soph_power = avg_feature(power, 'sophistication_score')
    caut_casual = avg_feature(casual, 'caution_score')
    caut_cautious = avg_feature(cautious, 'caution_score')

    discriminates = True

    if soph_power > soph_casual:
        print("  [OK] Sophistication discriminates power users from casual")
    else:
        print("  [FAIL] Sophistication does NOT discriminate")
        discriminates = False

    if caut_cautious > caut_casual:
        print("  [OK] Caution discriminates cautious users from casual")
    else:
        print("  [FAIL] Caution does NOT discriminate")
        discriminates = False

    if discriminates:
        print("\n  Features DISCRIMINATE as expected!")
    else:
        print("\n  Features need tuning.")


if __name__ == "__main__":
    main()
