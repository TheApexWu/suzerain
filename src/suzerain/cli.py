"""
Suzerain CLI - Analyze your AI governance style.

Usage:
    suzerain analyze           Analyze your Claude Code usage
    suzerain analyze --export  Export data to JSON
    suzerain share --preview   Preview what would be shared
    suzerain share --confirm   Share anonymized metrics
"""

import argparse
import json
import sys
from pathlib import Path
from dataclasses import asdict
from datetime import datetime, timezone

from . import __version__
from .parser import ClaudeLogParser
from .classifier import classify_user


OUTPUT_DIR = Path.home() / ".suzerain" / "analysis"


def print_profile(profile, classification):
    """Print governance profile to console."""
    print("\n" + "=" * 60)
    print("YOUR AI GOVERNANCE PROFILE")
    print("=" * 60)

    print(f"\nSessions analyzed: {profile.sessions_analyzed}")
    print(f"Data period: {profile.data_collection_days} days")
    print(f"Total tool calls: {profile.total_tool_calls}")

    print("\n--- GOVERNANCE METRICS ---")
    print(f"  Overall acceptance:   {profile.acceptance_rate:.1%}")
    print(f"  Bash acceptance:      {classification.key_features['bash_acceptance_rate']:.1%} ← KEY")
    print(f"  High-risk acceptance: {profile.high_risk_acceptance:.1%}")
    print(f"  Low-risk acceptance:  {profile.low_risk_acceptance:.1%}")

    print("\n--- DECISION TEMPO ---")
    print(f"  Mean decision time:   {profile.mean_decision_time_ms:.0f}ms")
    print(f"  Snap judgment rate:   {classification.key_features['snap_judgment_rate']:.1%} (<500ms)")

    if classification.subtle_features:
        sf = classification.subtle_features
        print("\n--- SOPHISTICATION SIGNALS ---")
        print(f"  Agent usage:          {sf.get('agent_spawn_rate', 0):.1%}")
        print(f"  Tool diversity:       {sf.get('tool_diversity', 0):.1f} unique/session")
        print(f"  Session depth:        {sf.get('session_depth', 0):.0f} tools/session")
        print(f"  Surgical ratio:       {sf.get('surgical_ratio', 0):.2f}")

    print("\n--- CLASSIFICATION ---")
    print(f"  Pattern:    {classification.primary_pattern} ({classification.pattern_confidence:.0%})")
    print(f"  Archetype:  {classification.archetype} ({classification.archetype_confidence:.0%})")

    if classification.subtle_features:
        sf = classification.subtle_features
        print(f"\n  Sophistication: {sf.get('sophistication_score', 0):.2f}")
        print(f"  Caution:        {sf.get('caution_score', 0):.2f}")

    print("\n--- ARCHETYPE SCORES ---")
    for arch, score in sorted(classification.archetype_scores.items(), key=lambda x: -x[1]):
        bar = "█" * int(score * 20)
        print(f"  {arch:<18} {bar} {score:.0%}")

    # Interpretation
    print("\n--- WHAT THIS MEANS ---")
    pattern = classification.primary_pattern

    if "Power User" in pattern and "Cautious" in pattern:
        print("  You're a sophisticated user who maintains control.")
        print("  You use advanced features but scrutinize risky operations.")
    elif "Power User" in pattern:
        print("  You're a sophisticated user who trusts the AI.")
        print("  You leverage agents and advanced features freely.")
    elif "Cautious" in pattern:
        print("  You're careful with AI suggestions.")
        print("  You review before accepting, especially shell commands.")
    else:
        print("  You trust the AI and accept most suggestions quickly.")
        print("  This is common for quick tasks and exploration.")

    print("\n" + "=" * 60)


def export_data(profile, classification, parser):
    """Export analysis to JSON."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    export = {
        "version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": asdict(profile),
        "classification": asdict(classification),
    }

    output_file = OUTPUT_DIR / "governance_profile.json"
    with open(output_file, 'w') as f:
        json.dump(export, f, indent=2, default=str)

    print(f"\nExported to: {output_file}")


def preview_share(profile, classification):
    """Show what would be shared."""
    print("\n" + "=" * 60)
    print("DATA SHARING PREVIEW")
    print("=" * 60)

    print("\nThe following WOULD be shared:\n")

    share_data = {
        "summary": {
            "sessions_analyzed": profile.sessions_analyzed,
            "total_tool_calls": profile.total_tool_calls,
            "data_days": profile.data_collection_days,
        },
        "governance": {
            "bash_acceptance_rate": round(classification.key_features['bash_acceptance_rate'], 3),
            "overall_acceptance_rate": round(profile.acceptance_rate, 3),
            "high_risk_acceptance": round(profile.high_risk_acceptance, 3),
            "snap_judgment_rate": round(classification.key_features['snap_judgment_rate'], 3),
        },
        "sophistication": {
            "agent_spawn_rate": round(classification.subtle_features.get('agent_spawn_rate', 0), 3),
            "tool_diversity": round(classification.subtle_features.get('tool_diversity', 0), 1),
            "session_depth": round(classification.subtle_features.get('session_depth', 0), 0),
        },
        "classification": {
            "pattern": classification.primary_pattern,
            "archetype": classification.archetype,
            "sophistication_score": round(classification.subtle_features.get('sophistication_score', 0), 2),
            "caution_score": round(classification.subtle_features.get('caution_score', 0), 2),
        }
    }

    print(json.dumps(share_data, indent=2))

    print("\n" + "-" * 60)
    print("NOT shared:")
    print("  ✗ Prompts or conversations")
    print("  ✗ File paths or code")
    print("  ✗ Command contents")
    print("  ✗ Project names")
    print("  ✗ Timestamps (only durations)")
    print("=" * 60)

    return share_data


def cmd_analyze(args):
    """Run analysis command."""
    print("Analyzing Claude Code logs...")

    parser = ClaudeLogParser(project_filter=args.project)
    sessions = parser.parse_all_sessions()

    if not sessions:
        print("\nNo sessions with tool calls found.")
        print("Make sure you have Claude Code logs at ~/.claude/projects/")
        return 1

    print(f"Found {len(sessions)} sessions with tool activity")

    profile = parser.compute_governance_profile()
    classification = classify_user(profile, parser)

    print_profile(profile, classification)

    if args.export:
        export_data(profile, classification, parser)

    return 0


def cmd_share(args):
    """Share data command."""
    parser = ClaudeLogParser()
    sessions = parser.parse_all_sessions()

    if not sessions:
        print("No data to share.")
        return 1

    profile = parser.compute_governance_profile()
    classification = classify_user(profile, parser)

    if args.preview:
        preview_share(profile, classification)
        print("\nTo share, run: suzerain share --confirm")
        return 0

    if args.confirm:
        share_data = preview_share(profile, classification)
        print("\n⚠️  Data sharing not yet implemented.")
        print("This will send anonymized metrics to help improve Suzerain.")
        print("Check https://github.com/amadeuswoo/suzerain for updates.")
        return 0

    print("Use --preview to see what would be shared")
    print("Use --confirm to share anonymized metrics")
    return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='suzerain',
        description='Understand your AI governance style'
    )
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze your Claude Code usage')
    analyze_parser.add_argument('--project', type=str, help='Filter by project name')
    analyze_parser.add_argument('--export', action='store_true', help='Export to JSON')

    # share command
    share_parser = subparsers.add_parser('share', help='Share anonymized metrics')
    share_parser.add_argument('--preview', action='store_true', help='Preview what would be shared')
    share_parser.add_argument('--confirm', action='store_true', help='Confirm and share')

    args = parser.parse_args()

    if args.command == 'analyze':
        return cmd_analyze(args)
    elif args.command == 'share':
        return cmd_share(args)
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
