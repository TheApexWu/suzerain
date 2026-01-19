#!/usr/bin/env python3
"""
Test Classification on Simulated Data

Runs the classifier on simulated user personas to validate:
1. Features discriminate between user types
2. Classification produces expected archetypes
3. 3-axis framework (Trust, Sophistication, Variance) works correctly
"""

import sys
from pathlib import Path
from collections import defaultdict

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from suzerain.parser import ClaudeLogParser
from suzerain.classifier import classify_user


SIMULATED_DIR = Path.home() / ".suzerain" / "simulated"


def analyze_persona(persona_dir: Path) -> dict:
    """Analyze all sessions for a single persona."""
    parser = ClaudeLogParser()

    # Find all session files - may be directly in persona dir or in project subdirs
    session_files = list(persona_dir.glob("*.jsonl"))
    session_files.extend(persona_dir.glob("**/*.jsonl"))

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
    classification = classify_user(profile, parser, parser.all_events)

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
    print("3-Axis Framework: Trust × Sophistication × Variance")
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

    # Print results table with 3-axis framework
    print("\n" + "-" * 80)
    print(f"{'Persona':<20} {'Pattern':<22} {'Archetype':<15} {'Trust':<6} {'Soph':<6} {'Var':<6}")
    print("-" * 80)

    for r in results:
        c = r['classification']
        kf = c.key_features
        print(f"{r['persona']:<20} "
              f"{c.primary_pattern:<22} "
              f"{c.archetype:<15} "
              f"{kf.get('bash_acceptance_rate', 0):.2f}   "
              f"{kf.get('sophistication', 0):.2f}   "
              f"{kf.get('variance', 0):.2f}")

    # Detailed breakdown
    print("\n" + "=" * 70)
    print("DETAILED FEATURE ANALYSIS")
    print("=" * 70)

    for r in results:
        c = r['classification']
        p = r['profile']
        kf = c.key_features
        sf = c.subtle_features

        print(f"\n{r['persona'].upper()}")
        print(f"  Sessions: {r['sessions']}, Tool calls: {r['tool_calls']}")
        print(f"  Primary Pattern: {c.primary_pattern} ({c.pattern_confidence:.0%})")
        print(f"  Archetype: {c.archetype} ({c.archetype_confidence:.0%})")
        print(f"  3-Axis Classification:")
        print(f"    Trust Level:         {kf.get('bash_acceptance_rate', 0):.1%}")
        print(f"    Sophistication:      {kf.get('sophistication', 0):.2f}")
        print(f"    Variance:            {kf.get('variance', 0):.2f}")
        print(f"  Supporting Features:")
        print(f"    Agent spawn rate:    {sf.get('agent_spawn_rate', 0):.1%}")
        print(f"    Tool diversity:      {sf.get('tool_diversity', 0):.1f}")
        print(f"    Session depth:       {sf.get('session_depth', 0):.0f}")

    # Summary: Pattern distribution
    print("\n" + "=" * 70)
    print("ARCHETYPE DISTRIBUTION")
    print("=" * 70)

    patterns = defaultdict(list)
    archetypes = defaultdict(list)

    for r in results:
        patterns[r['classification'].primary_pattern].append(r['persona'])
        archetypes[r['classification'].archetype].append(r['persona'])

    print("\nBy Primary Pattern:")
    for pattern, personas in sorted(patterns.items()):
        print(f"  {pattern}: {', '.join(personas)}")

    print("\nBy Archetype:")
    for arch, personas in sorted(archetypes.items()):
        count = len(personas)
        pct = count / len(results) * 100
        print(f"  {arch} ({count}, {pct:.0f}%): {', '.join(personas)}")

    # 3-Axis Analysis
    print("\n" + "=" * 70)
    print("3-AXIS FRAMEWORK ANALYSIS")
    print("=" * 70)

    # Group by expected category
    high_trust = ['junior_dev', 'hobbyist', 'copilot_refugee', 'rubber_stamper', 'yolo_dev']
    low_trust = ['security_engineer', 'compliance_reviewer', 'paranoid_senior', 'guardian']
    high_soph = ['senior_swe', 'staff_engineer', 'devops_sre', 'data_scientist']
    high_variance = ['context_switcher', 'project_guardian', 'sprint_mode']

    def avg_feature(personas: list, feature: str) -> float:
        vals = []
        for r in results:
            if r['persona'] in personas:
                kf = r['classification'].key_features
                vals.append(kf.get(feature, 0))
        return sum(vals) / len(vals) if vals else 0

    print("\nTrust Level (should vary by user type):")
    print(f"  High-trust personas:   {avg_feature(high_trust, 'bash_acceptance_rate'):.1%}")
    print(f"  Low-trust personas:    {avg_feature(low_trust, 'bash_acceptance_rate'):.1%}")

    print("\nSophistication (should vary by user type):")
    print(f"  High-soph personas:    {avg_feature(high_soph, 'sophistication'):.2f}")
    print(f"  All personas avg:      {sum(r['classification'].key_features.get('sophistication', 0) for r in results) / len(results):.2f}")

    print("\nVariance (context-dependent detection):")
    print(f"  High-var personas:     {avg_feature(high_variance, 'variance'):.2f}")
    print(f"  All personas avg:      {sum(r['classification'].key_features.get('variance', 0) for r in results) / len(results):.2f}")

    # Verdict
    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)

    trust_high = avg_feature(high_trust, 'bash_acceptance_rate')
    trust_low = avg_feature(low_trust, 'bash_acceptance_rate')
    soph_high = avg_feature(high_soph, 'sophistication')
    soph_avg = sum(r['classification'].key_features.get('sophistication', 0) for r in results) / len(results)
    var_high = avg_feature(high_variance, 'variance')
    var_avg = sum(r['classification'].key_features.get('variance', 0) for r in results) / len(results)

    all_pass = True

    if trust_high > trust_low:
        print("  [OK] Trust axis discriminates high-trust from low-trust personas")
    else:
        print("  [FAIL] Trust axis does NOT discriminate")
        all_pass = False

    if soph_high > soph_avg:
        print("  [OK] Sophistication axis identifies power users")
    else:
        print("  [FAIL] Sophistication axis does NOT discriminate")
        all_pass = False

    if var_high > var_avg:
        print("  [OK] Variance axis detects context-dependent users")
    else:
        print("  [WARN] Variance axis may need tuning")

    # Check archetype distribution
    unique_archetypes = len(set(r['classification'].archetype for r in results))
    print(f"\n  Unique archetypes assigned: {unique_archetypes}/6")

    if unique_archetypes >= 4:
        print("  [OK] Good archetype diversity")
    else:
        print("  [WARN] Low archetype diversity - check thresholds")

    # Check if Strategist still catches too many
    strategist_count = len(archetypes.get('Strategist', []))
    if strategist_count <= len(results) * 0.3:
        print(f"  [OK] Strategist is not over-capturing ({strategist_count}/{len(results)})")
    else:
        print(f"  [WARN] Strategist may be too broad ({strategist_count}/{len(results)})")

    if all_pass:
        print("\n  3-axis framework VALIDATED!")
    else:
        print("\n  Some issues need attention.")


if __name__ == "__main__":
    main()
