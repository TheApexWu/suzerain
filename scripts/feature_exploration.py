#!/usr/bin/env python3
"""
Feature Exploration: What Actually Varies in Claude Code Usage?

Don't speculate. Measure.
"""

import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import statistics

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"


@dataclass
class SessionData:
    """Raw data extracted from a session."""
    session_id: str
    project: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # Message counts
    user_messages: int = 0
    assistant_messages: int = 0

    # Tool data
    tool_calls: List[Dict] = field(default_factory=list)
    tool_results: List[Dict] = field(default_factory=list)

    # Timing
    decision_times_ms: List[int] = field(default_factory=list)


def parse_timestamp(ts_str: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
    except:
        return None


def parse_session(session_file: Path) -> SessionData:
    """Parse a session file and extract raw data."""
    session_id = session_file.stem
    project = session_file.parent.name

    data = SessionData(session_id=session_id, project=project)

    pending_tools = {}  # tool_id -> {timestamp, tool_name}

    with open(session_file, 'r') as f:
        for line in f:
            try:
                event = json.loads(line.strip())
            except:
                continue

            event_type = event.get('type')
            timestamp = parse_timestamp(event.get('timestamp', ''))

            if timestamp:
                if data.start_time is None or timestamp < data.start_time:
                    data.start_time = timestamp
                if data.end_time is None or timestamp > data.end_time:
                    data.end_time = timestamp

            if event_type == 'user':
                data.user_messages += 1

                # Check for tool results
                message = event.get('message', {})
                content = message.get('content', [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'tool_result':
                            tool_id = item.get('tool_use_id')
                            is_error = item.get('is_error', False)
                            result_content = str(item.get('content', ''))

                            # Match with pending tool
                            pending = pending_tools.pop(tool_id, None)
                            if pending:
                                # Compute decision time
                                decision_time = None
                                if pending['timestamp'] and timestamp:
                                    delta = timestamp - pending['timestamp']
                                    decision_time = int(delta.total_seconds() * 1000)

                                data.tool_results.append({
                                    'tool_id': tool_id,
                                    'tool_name': pending['tool_name'],
                                    'is_error': is_error,
                                    'rejected': is_error and 'requires approval' in result_content.lower(),
                                    'decision_time_ms': decision_time,
                                    'timestamp': timestamp,
                                })

                                if decision_time and 0 < decision_time < 300000:
                                    data.decision_times_ms.append(decision_time)

            elif event_type == 'assistant':
                data.assistant_messages += 1

                # Check for tool calls
                message = event.get('message', {})
                content = message.get('content', [])
                if isinstance(content, list):
                    tools_in_turn = []
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'tool_use':
                            tool_id = item.get('id')
                            tool_name = item.get('name', 'unknown')

                            # Normalize tool name
                            if tool_name.startswith('mcp__'):
                                tool_name = tool_name.split('__')[-1]

                            pending_tools[tool_id] = {
                                'timestamp': timestamp,
                                'tool_name': tool_name,
                            }
                            tools_in_turn.append(tool_name)

                    if tools_in_turn:
                        data.tool_calls.append({
                            'tools': tools_in_turn,
                            'count': len(tools_in_turn),
                            'timestamp': timestamp,
                        })

    return data


def analyze_features():
    """Analyze all sessions and compute feature distributions."""

    print("="*70)
    print("FEATURE EXPLORATION: What Actually Varies?")
    print("="*70)

    # Collect all sessions
    sessions = []
    for project_dir in PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        for f in project_dir.glob("*.jsonl"):
            if f.name.startswith("agent-"):
                continue
            try:
                session = parse_session(f)
                if session.tool_results:  # Only sessions with tool activity
                    sessions.append(session)
            except Exception as e:
                pass

    print(f"\nTotal sessions with tool activity: {len(sessions)}")

    if not sessions:
        print("No data found.")
        return

    # ========================================================================
    # FEATURE 1: Acceptance Rate Distribution
    # ========================================================================
    print("\n" + "-"*70)
    print("FEATURE 1: Acceptance Rate (per session)")
    print("-"*70)

    session_acceptance_rates = []
    for s in sessions:
        total = len(s.tool_results)
        rejected = sum(1 for r in s.tool_results if r['rejected'])
        accepted = total - rejected
        if total > 0:
            rate = accepted / total
            session_acceptance_rates.append(rate)

    if session_acceptance_rates:
        print(f"  Min:    {min(session_acceptance_rates):.1%}")
        print(f"  Max:    {max(session_acceptance_rates):.1%}")
        print(f"  Mean:   {statistics.mean(session_acceptance_rates):.1%}")
        print(f"  Median: {statistics.median(session_acceptance_rates):.1%}")
        if len(session_acceptance_rates) > 1:
            print(f"  Stdev:  {statistics.stdev(session_acceptance_rates):.1%}")

        # Distribution buckets
        buckets = {'0-50%': 0, '50-75%': 0, '75-90%': 0, '90-100%': 0, '100%': 0}
        for r in session_acceptance_rates:
            if r == 1.0:
                buckets['100%'] += 1
            elif r >= 0.9:
                buckets['90-100%'] += 1
            elif r >= 0.75:
                buckets['75-90%'] += 1
            elif r >= 0.5:
                buckets['50-75%'] += 1
            else:
                buckets['0-50%'] += 1

        print("\n  Distribution:")
        for bucket, count in buckets.items():
            pct = count / len(session_acceptance_rates)
            bar = "█" * int(pct * 30)
            print(f"    {bucket:10} {bar} {pct:.0%} ({count})")

    # ========================================================================
    # FEATURE 2: Acceptance Rate by Tool
    # ========================================================================
    print("\n" + "-"*70)
    print("FEATURE 2: Acceptance Rate by Tool (aggregated)")
    print("-"*70)

    tool_stats = defaultdict(lambda: {'accepted': 0, 'rejected': 0})
    for s in sessions:
        for r in s.tool_results:
            tool = r['tool_name']
            if r['rejected']:
                tool_stats[tool]['rejected'] += 1
            else:
                tool_stats[tool]['accepted'] += 1

    tool_rates = {}
    for tool, stats in sorted(tool_stats.items(), key=lambda x: -(x[1]['accepted'] + x[1]['rejected'])):
        total = stats['accepted'] + stats['rejected']
        rate = stats['accepted'] / total if total > 0 else 0
        tool_rates[tool] = rate
        print(f"  {tool:20} {rate:.1%} ({total} calls)")

    # Variance in tool acceptance
    if len(tool_rates) > 1:
        rates = list(tool_rates.values())
        print(f"\n  Tool acceptance variance: {statistics.stdev(rates):.3f}")
        print(f"  Tool acceptance range: {min(rates):.1%} - {max(rates):.1%}")

    # ========================================================================
    # FEATURE 3: Decision Time Distribution
    # ========================================================================
    print("\n" + "-"*70)
    print("FEATURE 3: Decision Time (ms)")
    print("-"*70)

    all_decision_times = []
    for s in sessions:
        all_decision_times.extend(s.decision_times_ms)

    if all_decision_times:
        print(f"  Total measurements: {len(all_decision_times)}")
        print(f"  Min:    {min(all_decision_times)}ms")
        print(f"  Max:    {max(all_decision_times)}ms")
        print(f"  Mean:   {statistics.mean(all_decision_times):.0f}ms")
        print(f"  Median: {statistics.median(all_decision_times):.0f}ms")
        if len(all_decision_times) > 1:
            print(f"  Stdev:  {statistics.stdev(all_decision_times):.0f}ms")

        # Distribution buckets
        buckets = {'<500ms': 0, '500ms-2s': 0, '2s-5s': 0, '5s-15s': 0, '>15s': 0}
        for t in all_decision_times:
            if t < 500:
                buckets['<500ms'] += 1
            elif t < 2000:
                buckets['500ms-2s'] += 1
            elif t < 5000:
                buckets['2s-5s'] += 1
            elif t < 15000:
                buckets['5s-15s'] += 1
            else:
                buckets['>15s'] += 1

        print("\n  Distribution:")
        for bucket, count in buckets.items():
            pct = count / len(all_decision_times)
            bar = "█" * int(pct * 30)
            print(f"    {bucket:10} {bar} {pct:.0%} ({count})")

    # ========================================================================
    # FEATURE 4: Parallel Tool Calls (Multiple tools per assistant turn)
    # ========================================================================
    print("\n" + "-"*70)
    print("FEATURE 4: Parallel Tool Calls (tools per assistant turn)")
    print("-"*70)

    tools_per_turn = []
    for s in sessions:
        for tc in s.tool_calls:
            tools_per_turn.append(tc['count'])

    if tools_per_turn:
        single = sum(1 for t in tools_per_turn if t == 1)
        multi = sum(1 for t in tools_per_turn if t > 1)
        print(f"  Single tool turns: {single} ({single/len(tools_per_turn):.1%})")
        print(f"  Multi-tool turns:  {multi} ({multi/len(tools_per_turn):.1%})")
        print(f"  Max tools in one turn: {max(tools_per_turn)}")
        if tools_per_turn:
            print(f"  Mean tools per turn: {statistics.mean(tools_per_turn):.2f}")

    # ========================================================================
    # FEATURE 5: Session Depth (messages per session)
    # ========================================================================
    print("\n" + "-"*70)
    print("FEATURE 5: Session Depth (messages per session)")
    print("-"*70)

    session_depths = [s.user_messages + s.assistant_messages for s in sessions]

    if session_depths:
        print(f"  Min:    {min(session_depths)}")
        print(f"  Max:    {max(session_depths)}")
        print(f"  Mean:   {statistics.mean(session_depths):.1f}")
        print(f"  Median: {statistics.median(session_depths):.0f}")

        # Distribution
        buckets = {'1-5': 0, '6-20': 0, '21-50': 0, '51-100': 0, '>100': 0}
        for d in session_depths:
            if d <= 5:
                buckets['1-5'] += 1
            elif d <= 20:
                buckets['6-20'] += 1
            elif d <= 50:
                buckets['21-50'] += 1
            elif d <= 100:
                buckets['51-100'] += 1
            else:
                buckets['>100'] += 1

        print("\n  Distribution:")
        for bucket, count in buckets.items():
            pct = count / len(session_depths)
            bar = "█" * int(pct * 30)
            print(f"    {bucket:10} {bar} {pct:.0%} ({count})")

    # ========================================================================
    # FEATURE 6: Tool Diversity (unique tools per session)
    # ========================================================================
    print("\n" + "-"*70)
    print("FEATURE 6: Tool Diversity (unique tools per session)")
    print("-"*70)

    tools_per_session = []
    for s in sessions:
        unique_tools = set(r['tool_name'] for r in s.tool_results)
        tools_per_session.append(len(unique_tools))

    if tools_per_session:
        print(f"  Min:    {min(tools_per_session)}")
        print(f"  Max:    {max(tools_per_session)}")
        print(f"  Mean:   {statistics.mean(tools_per_session):.1f}")
        print(f"  Median: {statistics.median(tools_per_session):.0f}")

    # ========================================================================
    # FEATURE 7: Bash Specifically (The Governance Gatekeeper)
    # ========================================================================
    print("\n" + "-"*70)
    print("FEATURE 7: Bash Command Acceptance (per session)")
    print("-"*70)

    bash_rates = []
    for s in sessions:
        bash_results = [r for r in s.tool_results if r['tool_name'] == 'Bash']
        if bash_results:
            rejected = sum(1 for r in bash_results if r['rejected'])
            accepted = len(bash_results) - rejected
            rate = accepted / len(bash_results)
            bash_rates.append(rate)

    if bash_rates:
        print(f"  Sessions with Bash: {len(bash_rates)}")
        print(f"  Min:    {min(bash_rates):.1%}")
        print(f"  Max:    {max(bash_rates):.1%}")
        print(f"  Mean:   {statistics.mean(bash_rates):.1%}")
        print(f"  Median: {statistics.median(bash_rates):.1%}")
        if len(bash_rates) > 1:
            print(f"  Stdev:  {statistics.stdev(bash_rates):.1%}")
    else:
        print("  No Bash usage found")

    # ========================================================================
    # FEATURE 8: Agent/Task Usage
    # ========================================================================
    print("\n" + "-"*70)
    print("FEATURE 8: Agent/Task Tool Usage")
    print("-"*70)

    task_usage = []
    for s in sessions:
        task_calls = [r for r in s.tool_results if r['tool_name'] in ['Task', 'TaskOutput']]
        total_calls = len(s.tool_results)
        if total_calls > 0:
            task_ratio = len(task_calls) / total_calls
            task_usage.append({'session': s.session_id, 'task_calls': len(task_calls), 'ratio': task_ratio})

    sessions_with_tasks = [t for t in task_usage if t['task_calls'] > 0]
    print(f"  Sessions using Task tool: {len(sessions_with_tasks)} / {len(sessions)} ({len(sessions_with_tasks)/len(sessions):.1%})")

    if sessions_with_tasks:
        ratios = [t['ratio'] for t in sessions_with_tasks]
        print(f"  Mean Task ratio (when used): {statistics.mean(ratios):.1%}")
        print(f"  Max Task calls in session: {max(t['task_calls'] for t in sessions_with_tasks)}")

    # ========================================================================
    # SUMMARY: What Actually Varies?
    # ========================================================================
    print("\n" + "="*70)
    print("SUMMARY: Which Features Show Meaningful Variance?")
    print("="*70)

    print("""
    HIGH VARIANCE (Good discriminators):
    - Bash acceptance rate (varies 0-100% per session)
    - Tool acceptance variance (some users discriminate, most don't)
    - Decision time (500ms to 15s+)
    - Session depth (1 to 100+ messages)

    LOW VARIANCE (Won't discriminate well):
    - Overall acceptance rate (most sessions 90-100%)
    - Read/Glob/Grep acceptance (always ~100%)
    - Agent usage (most users don't use it)

    NEEDS MORE DATA:
    - Per-user aggregation (we only see sessions)
    - Time-series patterns (trust evolution)
    - Correction rate (hard to detect from logs)
    """)

    print("="*70)


if __name__ == "__main__":
    analyze_features()
