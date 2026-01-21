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
import urllib.request
import urllib.error
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
from .analytics import run_advanced_analytics


OUTPUT_DIR = Path.home() / ".suzerain" / "analysis"
SHARE_API_URL = "https://suzerain.dev/api/share"


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

    # Three-axis classification
    kf = classification.key_features
    sf = classification.subtle_features
    print()
    print("  ┌─ THREE-AXIS CLASSIFICATION ───────────────────────────┐")
    print(f"  │ Trust Level:          {kf['bash_acceptance_rate']:.0%} (bash acceptance)")
    print(f"  │ Sophistication:       {kf.get('sophistication', 0):.2f} (agent/tool usage)")
    print(f"  │ Variance:             {kf.get('variance', 0):.2f} (cross-context)")
    print(f"  │")
    print(f"  │ Risk delta:           {kf['risk_trust_delta']:+.0%} (safe vs risky gap)")
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


def print_advanced_analytics(analytics):
    """Print advanced analytics: command breakdown, temporal trend, session arc."""

    cb = analytics.command_breakdown
    tt = analytics.temporal_trend
    sa = analytics.session_arc

    # Command Type Breakdown
    print()
    print("  ┌─ COMMAND BREAKDOWN ──────────────────────────────────────┐")

    # Calculate rates
    dest_total = cb.total('destructive')
    state_total = cb.total('state_changing')
    read_total = cb.total('read_only')
    unk_total = cb.total('unknown')

    dest_rate = cb.acceptance_rate('destructive')
    state_rate = cb.acceptance_rate('state_changing')
    read_rate = cb.acceptance_rate('read_only')

    if dest_total > 0:
        print(f"  │ Destructive:    {dest_rate:.0%} accepted ({dest_total} cmds)")
    else:
        print(f"  │ Destructive:    no data")

    if state_total > 0:
        print(f"  │ State-changing: {state_rate:.0%} accepted ({state_total} cmds)")
    else:
        print(f"  │ State-changing: no data")

    if read_total > 0:
        print(f"  │ Read-only:      {read_rate:.0%} accepted ({read_total} cmds)")
    else:
        print(f"  │ Read-only:      no data")

    if unk_total > 0:
        unk_rate = cb.acceptance_rate('unknown')
        print(f"  │ Uncategorized:  {unk_rate:.0%} accepted ({unk_total} cmds)")

    # Show insights
    categorized_total = dest_total + state_total + read_total
    categorized_accepted = (cb.destructive['accepted'] + cb.state_changing['accepted'] +
                           cb.read_only['accepted'])
    categorized_rate = categorized_accepted / categorized_total if categorized_total > 0 else 0

    if unk_total > 0 and categorized_total > 0:
        unk_rate = cb.acceptance_rate('unknown')
        if unk_rate is not None and categorized_rate - unk_rate > 0.3:
            print(f"  │")
            print(f"  │ → KEY INSIGHT: You rubber-stamp recognizable commands")
            print(f"  │   ({categorized_rate:.0%}) but scrutinize novel ones ({unk_rate:.0%}).")
            print(f"  │   Your caution lives in the uncategorized.")

    print("  └─────────────────────────────────────────────────────────┘")

    # Temporal Trend
    if tt.data_span_days >= 7 and len(tt.weekly_rates) >= 2:
        print()
        print("  ┌─ TEMPORAL TREND ─────────────────────────────────────────┐")
        print(f"  │ Weekly bash acceptance over {tt.data_span_days} days:")
        print(f"  │")

        # Show each week's rate
        rates = [r[1] for r in tt.weekly_rates]
        min_rate = min(rates)
        max_rate = max(rates)

        for week_start, rate, count in tt.weekly_rates:
            bar_len = int(rate * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"  │ {week_start[5:]}: {bar} {rate:.0%} ({count})")

        # Show variance insight
        if max_rate - min_rate > 0.3:
            print(f"  │")
            print(f"  │ → HIGH VARIANCE: {min_rate:.0%} to {max_rate:.0%}")
            print(f"  │   Something changed in your trust pattern.")

        print("  └─────────────────────────────────────────────────────────┘")

    # Session Arc
    if sa.sessions_analyzed >= 3:
        print()
        print("  ┌─ SESSION ARC ────────────────────────────────────────────┐")
        print(f"  │ Comparing first {sa.n_commands} vs last {sa.n_commands} bash cmds per session:")
        print(f"  │")

        if sa.first_n_rate is not None and sa.last_n_rate is not None:
            print(f"  │ First {sa.n_commands}: {sa.first_n_rate:.0%} accepted")
            print(f"  │ Last {sa.n_commands}:  {sa.last_n_rate:.0%} accepted")
            print(f"  │")

            if sa.arc_type == 'warmup':
                print(f"  │ → WARMUP pattern: you start cautious, loosen up")
            elif sa.arc_type == 'cooldown':
                print(f"  │ → COOLDOWN pattern: you start trusting, tighten up")
            else:
                print(f"  │ → FLAT: consistent trust throughout sessions")

            print(f"  │   (based on {sa.sessions_analyzed} sessions)")

        print("  └─────────────────────────────────────────────────────────┘")

    # Trust Variance
    tv = analytics.trust_variance
    if tv.total_bash_commands >= 20 and len(tv.project_rates) >= 2:
        print()
        print("  ┌─ TRUST VARIANCE ─────────────────────────────────────────┐")
        print(f"  │ Overall bash acceptance: {tv.overall_bash_rate:.0%}")
        print(f"  │")
        print(f"  │ By project:")

        # Show top projects by command count
        sorted_projects = sorted(tv.project_rates.items(), key=lambda x: -x[1][1])
        for proj, (rate, count) in sorted_projects[:5]:
            proj_short = proj[:40] + '...' if len(proj) > 40 else proj
            print(f"  │   {rate:.0%} ({count:4d}) {proj_short}")

        print(f"  │")
        print(f"  │ Variance score: {tv.variance_score:.2f} ({tv.variance_type})")

        if tv.variance_type == 'context_dependent':
            print(f"  │ → You govern VERY differently by context")
        elif tv.variance_type == 'moderate':
            print(f"  │ → Some variation by context")
        else:
            print(f"  │ → Uniform policy across contexts")

        print("  └─────────────────────────────────────────────────────────┘")


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

    # Classification (3-axis framework)
    print("  ═══════════════════════════════════════════════════════")
    print("  CLASSIFICATION (3-AXIS FRAMEWORK)")
    print("  ═══════════════════════════════════════════════════════")
    print(f"  Primary pattern:      {classification.primary_pattern}")
    print(f"  Pattern confidence:   {classification.pattern_confidence:.0%}")
    print(f"  Archetype:            {classification.archetype}")
    print(f"  Archetype confidence: {classification.archetype_confidence:.0%}")
    print()
    print(f"  Trust Level:          {classification.key_features.get('bash_acceptance_rate', 0):.2f}")
    print(f"  Sophistication:       {classification.key_features.get('sophistication', 0):.2f}")
    print(f"  Variance:             {classification.key_features.get('variance', 0):.2f}")
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
            "snap_judgment_rate": round(classification.key_features.get('snap_judgment_rate', 0), 2),
        },
        "sophistication": {
            "agent_spawn_rate": round(classification.subtle_features.get('agent_spawn_rate', 0), 2),
            "tool_diversity": round(classification.subtle_features.get('tool_diversity', 0), 0),
            "session_depth_bucket": bucket_count(int(classification.subtle_features.get('session_depth', 0))),
        },
        "classification": {
            "pattern": classification.primary_pattern,
            "archetype": classification.archetype,
            "trust_level": round(classification.key_features.get('bash_acceptance_rate', 0), 2),
            "sophistication": round(classification.key_features.get('sophistication', 0), 2),
            "variance": round(classification.key_features.get('variance', 0), 2),
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
    # Suppress output if exporting JSON to stdout
    quiet = getattr(args, 'export_json', False)

    if not quiet:
        print("\n  Analyzing Claude Code logs...")

    parser = ClaudeLogParser(project_filter=args.project)
    sessions = parser.parse_all_sessions()

    if not sessions:
        if not quiet:
            print("\n  No sessions with tool calls found.\n")
            print("  Suzerain reads Claude Code logs from ~/.claude/projects/")
            print("")
            print("  To generate logs:")
            print("    1. Use Claude Code (claude) in any project")
            print("    2. Accept or reject some tool calls")
            print("    3. Run 'suzerain analyze' again")
            print("")
            print("  Logs appear after your first Claude Code session.")
        return 1

    if not quiet:
        print(f"  Found {len(sessions)} sessions with tool activity")

    profile = parser.compute_governance_profile()
    classification = classify_user(profile, parser)

    # Export JSON to stdout (for GitHub Actions)
    if quiet:
        insight = get_archetype_insight(classification)
        stats = {
            "sessions": profile.sessions_analyzed,
            "tool_calls": profile.total_tool_calls,
            "archetype": classification.archetype,
            "trust": round(classification.key_features["bash_acceptance_rate"], 2),
            "sophistication": round(classification.key_features.get("sophistication", 0), 2),
            "variance": round(classification.key_features.get("variance", 0), 2),
            "historical_parallel": insight.historical_parallel,
            "bottleneck": insight.bottleneck,
            "updated": datetime.now(timezone.utc).isoformat()
        }
        print(json.dumps(stats, indent=2))
        return 0

    if args.verbose:
        print_profile_verbose(profile, classification)
    else:
        print_profile_compact(profile, classification)

    # Run and display advanced analytics
    analytics = run_advanced_analytics(parser.all_events)
    print_advanced_analytics(analytics)

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
        share_data = preview_share(profile, classification)

        # Add version to payload
        share_data["version"] = __version__

        print("  Sending to suzerain.dev...")

        try:
            # Prepare the request
            data = json.dumps(share_data).encode('utf-8')
            req = urllib.request.Request(
                SHARE_API_URL,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': f'suzerain-cli/{__version__}'
                },
                method='POST'
            )

            # Send the request
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))

            if result.get('success'):
                print()
                print("  ╔═══════════════════════════════════════════════════════╗")
                print("  ║  Thanks for contributing to the research.             ║")
                print("  ║  Your anonymized metrics help us understand           ║")
                print("  ║  how developers govern AI assistants.                 ║")
                print("  ╚═══════════════════════════════════════════════════════╝")
                print()
                print(f"  Submission ID: {result.get('id', 'unknown')}")
                print()
            else:
                print(f"  Error: {result.get('error', 'Unknown error')}")
                return 1

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            try:
                error_data = json.loads(error_body)
                print(f"  Error: {error_data.get('error', 'Server error')}")
            except json.JSONDecodeError:
                print(f"  Error: HTTP {e.code}")
            return 1

        except urllib.error.URLError as e:
            print(f"  Connection failed: {e.reason}")
            print("  Check your internet connection or try again later.")
            return 1

        except Exception as e:
            print(f"  Unexpected error: {e}")
            return 1

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
    analyze_parser.add_argument('--export', action='store_true', help='Export to JSON file')
    analyze_parser.add_argument('--export-json', '--json', action='store_true', help='Output stats as JSON to stdout')

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
