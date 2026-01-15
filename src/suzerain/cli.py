"""
Suzerain CLI - Understand your AI governance style.

Usage:
    suzerain analyze            Analyze your Claude Code usage
    suzerain analyze --verbose  Show detailed metrics
    suzerain analyze --export   Export data to JSON
    suzerain share --preview    Preview what would be shared
    suzerain share --confirm    Share anonymized metrics
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
from .insights import (
    get_archetype_insight,
    get_pattern_insight,
    get_prompting_approaches,
    generate_insight_summary,
)


OUTPUT_DIR = Path.home() / ".suzerain" / "analysis"


def print_header():
    """Print the Suzerain header."""
    print()
    print("  ╔═══════════════════════════════════════════════════════╗")
    print("  ║                      SUZERAIN                         ║")
    print("  ║                                                       ║")
    print("  ║   \"The suzerain rules even where there are other      ║")
    print("  ║    kings. There is no territory outside his claim.\"   ║")
    print("  ╚═══════════════════════════════════════════════════════╝")


def print_profile_compact(profile, classification):
    """Print compact governance profile focused on insight."""
    insight = get_archetype_insight(classification)
    pattern_insight = get_pattern_insight(classification)

    print_header()

    # The headline - framed as pattern, not identity
    print(f"\n  Your recent pattern: {insight.name.upper()}")
    print(f"  Empirical cluster: {classification.primary_pattern}")
    print()

    # The governance style
    print("  ┌─ YOUR GOVERNANCE STYLE ───────────────────────────────┐")
    print(f"  │ {insight.language_game}")
    print("  │")
    # Word wrap the description
    desc = insight.game_description
    words = desc.split()
    line = "  │ "
    for word in words:
        if len(line) + len(word) > 58:
            print(line)
            line = "  │ " + word + " "
        else:
            line += word + " "
    if line.strip() != "│":
        print(line)
    print("  └────────────────────────────────────────────────────────┘")

    # The bottleneck (the actionable insight)
    print()
    print("  ┌─ YOUR BOTTLENECK ────────────────────────────────────┐")
    print(f"  │ {insight.bottleneck}")
    print("  │")
    desc = insight.bottleneck_description
    words = desc.split()
    line = "  │ "
    for word in words:
        if len(line) + len(word) > 58:
            print(line)
            line = "  │ " + word + " "
        else:
            line += word + " "
    if line.strip() != "│":
        print(line)
    print("  └────────────────────────────────────────────────────────┘")

    # Raw numbers
    print()
    print("  ┌─ RAW NUMBERS ─────────────────────────────────────────┐")
    bash_stats = profile.trust_by_tool.get('Bash', {})
    bash_total = bash_stats.get('total', 0)
    bash_accepted = bash_stats.get('accepted', 0)
    bash_rejected = bash_total - bash_accepted
    print(f"  │ Total tool calls:     {profile.total_tool_calls:,}")
    print(f"  │ Bash commands:        {bash_total} ({bash_accepted} accepted, {bash_rejected} rejected)")
    print(f"  │ Sessions:             {profile.sessions_analyzed}")
    print(f"  │ Days of data:         {profile.data_collection_days}")
    print(f"  │ Mean decision time:   {profile.mean_decision_time_ms:.0f}ms")
    print("  └────────────────────────────────────────────────────────┘")

    # Derived metrics
    kf = classification.key_features
    sf = classification.subtle_features
    print()
    print("  ┌─ DERIVED METRICS ─────────────────────────────────────┐")
    print(f"  │ Bash acceptance:      {kf['bash_acceptance_rate']:.0%} ← the main signal")
    print(f"  │ Snap judgments:       {kf['snap_judgment_rate']:.0%} (< 500ms)")
    print(f"  │ Risk delta:           {kf['risk_trust_delta']:+.0%} (safe vs risky gap)")
    print(f"  │ Sophistication:       {sf.get('sophistication_score', 0):.2f}")
    print(f"  │ Caution:              {sf.get('caution_score', 0):.2f}")
    print("  └────────────────────────────────────────────────────────┘")

    # Prompting approaches
    approaches = get_prompting_approaches(classification)
    print()
    print("  ┌─ PROMPTING APPROACHES ────────────────────────────────┐")
    print(f"  │ Framework: {approaches['thinking_framework'][:45]}...")
    print("  │")
    print("  │ Prompt to try:")
    prompt = approaches['prompt_to_try']
    words = prompt.split()
    line = "  │   \""
    for word in words:
        if len(line) + len(word) > 56:
            print(line)
            line = "  │    " + word + " "
        else:
            line += word + " "
    if line.strip() != "│":
        print(line.rstrip() + "\"")
    print("  │")
    print("  │ CLAUDE.md suggestion:")
    suggestion = approaches['claude_md_suggestion']
    words = suggestion.split()
    line = "  │   "
    for word in words:
        if len(line) + len(word) > 56:
            print(line)
            line = "  │   " + word + " "
        else:
            line += word + " "
    if line.strip() != "│":
        print(line)
    print("  └────────────────────────────────────────────────────────┘")

    # Workflow shift
    print()
    print("  ┌─ TRY THIS ────────────────────────────────────────────┐")
    workflow = approaches['workflow_shift']
    words = workflow.split()
    line = "  │ "
    for word in words:
        if len(line) + len(word) > 58:
            print(line)
            line = "  │ " + word + " "
        else:
            line += word + " "
    if line.strip() != "│":
        print(line)
    # Agent advice if present
    if 'agent_advice' in approaches:
        print("  │")
        agent = approaches['agent_advice']
        words = agent.split()
        line = "  │ "
        for word in words:
            if len(line) + len(word) > 58:
                print(line)
                line = "  │ " + word + " "
            else:
                line += word + " "
        if line.strip() != "│":
            print(line)
    print("  └────────────────────────────────────────────────────────┘")

    # Data summary with uncertainty
    print()
    print(f"  Based on {profile.sessions_analyzed} sessions, "
          f"{profile.total_tool_calls:,} tool calls, "
          f"{profile.data_collection_days} days")

    # Confidence note based on data volume
    if profile.sessions_analyzed < 10:
        print("  ⚠ Low confidence: patterns may shift with more data")
    elif profile.sessions_analyzed < 30:
        print("  ◐ Moderate confidence: consider this a hypothesis")
    else:
        print("  ● Higher confidence: pattern appears stable")

    # Fluidity disclaimer with thematic tie-in
    print()
    print("  ─────────────────────────────────────────────────────────")
    print("  You are the suzerain. The AI executes, but you rule.")
    print("  These patterns describe how you exercise your claim—")
    print("  not who you are. The game changes when you do.")
    print()


def print_profile_verbose(profile, classification):
    """Print detailed governance profile with all metrics."""
    insight = get_archetype_insight(classification)

    print_header()

    print(f"\n  Your recent pattern: {insight.name.upper()}")
    print(f"  \"{insight.historical_parallel}\"")
    print()

    # Data summary
    print("  ═══════════════════════════════════════════════════════")
    print("  DATA SUMMARY")
    print("  ═══════════════════════════════════════════════════════")
    print(f"  Sessions analyzed:    {profile.sessions_analyzed}")
    print(f"  Total tool calls:     {profile.total_tool_calls:,}")
    print(f"  Data period:          {profile.data_collection_days} days")
    print()

    # Governance metrics
    print("  ═══════════════════════════════════════════════════════")
    print("  GOVERNANCE METRICS")
    print("  ═══════════════════════════════════════════════════════")
    print(f"  Overall acceptance:   {profile.acceptance_rate:.1%}")
    print(f"  Bash acceptance:      {classification.key_features['bash_acceptance_rate']:.1%} ← KEY")
    print(f"  High-risk acceptance: {profile.high_risk_acceptance:.1%}")
    print(f"  Low-risk acceptance:  {profile.low_risk_acceptance:.1%}")
    print(f"  Risk trust delta:     {classification.key_features['risk_trust_delta']:+.1%}")
    print()

    # Decision tempo
    print("  ═══════════════════════════════════════════════════════")
    print("  DECISION TEMPO")
    print("  ═══════════════════════════════════════════════════════")
    print(f"  Mean decision time:   {profile.mean_decision_time_ms:.0f}ms")
    print(f"  Snap judgment rate:   {classification.key_features['snap_judgment_rate']:.1%} (<500ms)")
    print(f"  Session consistency:  {profile.session_consistency:.2f}")
    print()

    # Sophistication signals
    sf = classification.subtle_features
    print("  ═══════════════════════════════════════════════════════")
    print("  SOPHISTICATION SIGNALS")
    print("  ═══════════════════════════════════════════════════════")
    print(f"  Agent spawn rate:     {sf.get('agent_spawn_rate', 0):.1%}")
    print(f"  Tool diversity:       {sf.get('tool_diversity', 0):.1f} unique/session")
    print(f"  Session depth:        {sf.get('session_depth', 0):.0f} tools/session")
    print(f"  Surgical ratio:       {sf.get('surgical_ratio', 0):.2f} (search/read)")
    print(f"  Edit intensity:       {sf.get('edit_intensity', 0):.1%}")
    print()

    # Classification
    print("  ═══════════════════════════════════════════════════════")
    print("  CLASSIFICATION")
    print("  ═══════════════════════════════════════════════════════")
    print(f"  Primary pattern:      {classification.primary_pattern}")
    print(f"  Pattern confidence:   {classification.pattern_confidence:.0%}")
    print(f"  Archetype:            {classification.archetype}")
    print(f"  Archetype confidence: {classification.archetype_confidence:.0%}")
    print()
    print(f"  Sophistication score: {sf.get('sophistication_score', 0):.2f}")
    print(f"  Caution score:        {sf.get('caution_score', 0):.2f}")
    print()

    # Archetype scores
    print("  ARCHETYPE SCORES:")
    for arch, score in sorted(classification.archetype_scores.items(), key=lambda x: -x[1]):
        bar = "█" * int(score * 20)
        print(f"    {arch:<18} {bar} {score:.0%}")
    print()

    # Governance style
    print("  ═══════════════════════════════════════════════════════")
    print("  YOUR GOVERNANCE STYLE")
    print("  ═══════════════════════════════════════════════════════")
    print(f"  {insight.language_game}")
    print()
    print(f"  {insight.game_description}")
    print()

    # Bottleneck
    print("  ═══════════════════════════════════════════════════════")
    print("  YOUR BOTTLENECK")
    print("  ═══════════════════════════════════════════════════════")
    print(f"  {insight.bottleneck}")
    print()
    print(f"  {insight.bottleneck_description}")
    print()
    print("  Mechanism:")
    print(f"  {insight.mechanism}")
    print()

    # Recommendations
    print("  ═══════════════════════════════════════════════════════")
    print("  RECOMMENDATIONS")
    print("  ═══════════════════════════════════════════════════════")
    for i, rec in enumerate(insight.recommendations, 1):
        print(f"  {i}. {rec}")
    print()

    # Risk
    print("  ═══════════════════════════════════════════════════════")
    print("  RISK TO WATCH")
    print("  ═══════════════════════════════════════════════════════")
    print(f"  {insight.risk}")
    print()

    # Epistemic status
    print("  ═══════════════════════════════════════════════════════")
    print("  EPISTEMIC STATUS")
    print("  ═══════════════════════════════════════════════════════")
    print(f"  Data: {profile.sessions_analyzed} sessions, {profile.total_tool_calls:,} calls")
    if profile.sessions_analyzed < 10:
        print("  Confidence: LOW — treat as exploratory hypothesis")
    elif profile.sessions_analyzed < 30:
        print("  Confidence: MODERATE — pattern emerging, not yet stable")
    else:
        print("  Confidence: HIGHER — pattern appears consistent")
    print()
    print("  This tool is hypothesis-generating, not a validated")
    print("  psychometric instrument. Thresholds are heuristic.")
    print()
    print("  You are the suzerain. These patterns describe how you")
    print("  exercise your claim—not who you are.")
    print()


def export_data(profile, classification, parser):
    """Export analysis to JSON."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    insight_summary = generate_insight_summary(classification)

    export = {
        "version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": asdict(profile),
        "classification": asdict(classification),
        "insights": insight_summary,
    }

    output_file = OUTPUT_DIR / "governance_profile.json"
    with open(output_file, 'w') as f:
        json.dump(export, f, indent=2, default=str)

    print(f"  Exported to: {output_file}")


def bucket_count(n: int) -> str:
    """Bucket counts to reduce fingerprinting."""
    if n < 10:
        return "1-9"
    elif n < 25:
        return "10-24"
    elif n < 50:
        return "25-49"
    elif n < 100:
        return "50-99"
    elif n < 250:
        return "100-249"
    elif n < 500:
        return "250-499"
    elif n < 1000:
        return "500-999"
    else:
        return f"{(n // 1000) * 1000}+"


def preview_share(profile, classification):
    """Show what would be shared."""
    print()
    print("  ═══════════════════════════════════════════════════════")
    print("  DATA SHARING PREVIEW")
    print("  ═══════════════════════════════════════════════════════")

    print("\n  The following WOULD be shared:\n")

    # Bucket counts to reduce fingerprinting risk
    share_data = {
        "summary": {
            "sessions_bucket": bucket_count(profile.sessions_analyzed),
            "tool_calls_bucket": bucket_count(profile.total_tool_calls),
            "data_days_bucket": bucket_count(profile.data_collection_days),
        },
        "governance": {
            "bash_acceptance_rate": round(classification.key_features['bash_acceptance_rate'], 2),
            "overall_acceptance_rate": round(profile.acceptance_rate, 2),
            "high_risk_acceptance": round(profile.high_risk_acceptance, 2),
            "snap_judgment_rate": round(classification.key_features['snap_judgment_rate'], 2),
        },
        "sophistication": {
            "agent_spawn_rate": round(classification.subtle_features.get('agent_spawn_rate', 0), 2),
            "tool_diversity": round(classification.subtle_features.get('tool_diversity', 0), 0),
            "session_depth_bucket": bucket_count(int(classification.subtle_features.get('session_depth', 0))),
        },
        "classification": {
            "pattern": classification.primary_pattern,
            "archetype": classification.archetype,
            "sophistication_score": round(classification.subtle_features.get('sophistication_score', 0), 1),
            "caution_score": round(classification.subtle_features.get('caution_score', 0), 1),
        }
    }

    print(json.dumps(share_data, indent=2))

    print("\n  Privacy measures:")
    print("    ✓ Counts bucketed (not exact values)")
    print("    ✓ Rates rounded to 2 decimal places")
    print("    ✓ No persistent user ID")
    print()
    print("  NOT shared:")
    print("    ✗ Prompts or conversations")
    print("    ✗ File paths or code")
    print("    ✗ Command contents")
    print("    ✗ Project names")
    print("    ✗ Timestamps")
    print("    ✗ IP address (server doesn't log)")
    print()
    print("  See docs/PRIVACY.md for full disclosure.")
    print()

    return share_data


def cmd_analyze(args):
    """Run analysis command."""
    print("\n  Analyzing Claude Code logs...")

    parser = ClaudeLogParser(project_filter=args.project)
    sessions = parser.parse_all_sessions()

    if not sessions:
        print("\n  No sessions with tool calls found.")
        print("  Make sure you have Claude Code logs at ~/.claude/projects/")
        return 1

    print(f"  Found {len(sessions)} sessions with tool activity")

    profile = parser.compute_governance_profile()
    classification = classify_user(profile, parser)

    if args.verbose:
        print_profile_verbose(profile, classification)
    else:
        print_profile_compact(profile, classification)

    if args.export:
        export_data(profile, classification, parser)

    return 0


def cmd_share(args):
    """Share data command."""
    parser = ClaudeLogParser()
    sessions = parser.parse_all_sessions()

    if not sessions:
        print("  No data to share.")
        return 1

    profile = parser.compute_governance_profile()
    classification = classify_user(profile, parser)

    if args.preview:
        preview_share(profile, classification)
        print("  To share, run: suzerain share --confirm")
        return 0

    if args.confirm:
        preview_share(profile, classification)
        print("  ⚠️  Data sharing not yet implemented.")
        print("  This will send anonymized metrics to help improve Suzerain.")
        print("  Check https://github.com/amadeuswoo/suzerain for updates.")
        return 0

    print("  Use --preview to see what would be shared")
    print("  Use --confirm to share anonymized metrics")
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
    analyze_parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed metrics')
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
