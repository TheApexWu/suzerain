#!/usr/bin/env python3
"""
User Behavior Simulation for Suzerain

Generates synthetic Claude Code sessions for different user personas.
Since we only have one real user's data, this helps us:
1. Test classification logic on diverse behaviors
2. Validate that features actually discriminate
3. Generate training data for future ML models

Personas are based on realistic archetypes of Claude Code users.
"""

import json
import random
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
import uuid


# ============================================================================
# Tool Definitions
# ============================================================================

TOOLS = {
    # High risk - require approval
    'Bash': {'risk': 'high', 'typical_time_ms': (500, 30000)},
    'Write': {'risk': 'high', 'typical_time_ms': (200, 5000)},
    'Edit': {'risk': 'high', 'typical_time_ms': (200, 3000)},
    'NotebookEdit': {'risk': 'high', 'typical_time_ms': (300, 5000)},

    # Low risk - usually auto-approved
    'Read': {'risk': 'low', 'typical_time_ms': (50, 500)},
    'Glob': {'risk': 'low', 'typical_time_ms': (50, 300)},
    'Grep': {'risk': 'low', 'typical_time_ms': (50, 300)},
    'WebFetch': {'risk': 'low', 'typical_time_ms': (100, 1000)},
    'WebSearch': {'risk': 'low', 'typical_time_ms': (100, 1000)},

    # Agent tools - power user signal
    'Task': {'risk': 'low', 'typical_time_ms': (100, 500)},
    'TaskOutput': {'risk': 'low', 'typical_time_ms': (50, 200)},

    # Utility
    'TodoWrite': {'risk': 'low', 'typical_time_ms': (50, 200)},
    'AskUserQuestion': {'risk': 'low', 'typical_time_ms': (1000, 10000)},
}


# ============================================================================
# User Personas
# ============================================================================

@dataclass
class UserPersona:
    """Defines behavioral parameters for a user type."""
    name: str
    description: str

    # Acceptance rates by risk level
    bash_acceptance: float  # 0-1, THE key discriminator
    high_risk_acceptance: float  # For Write, Edit
    low_risk_acceptance: float  # For Read, Glob, etc.

    # Decision timing
    mean_decision_time_ms: int
    decision_time_variance: float  # CV

    # Sophistication signals
    uses_agents: bool
    agent_probability: float  # If uses_agents, how often?
    parallel_tool_probability: float  # Multi-tool turns

    # Session patterns
    mean_session_depth: int  # Tool calls per session
    session_depth_variance: float
    tool_diversity: int  # Unique tools per session

    # Workflow patterns
    surgical_probability: float  # Glob/Grep before Read
    edit_intensity: float  # Proportion of Edit/Write calls

    # Context variance (NEW)
    context_variance: float = 0.0  # 0 = uniform, 1 = highly context-dependent
    # If context_variance > 0, some sessions will use bash_acceptance_high, others bash_acceptance_low
    bash_acceptance_high: float = 0.0  # For "trusting" contexts
    bash_acceptance_low: float = 0.0   # For "cautious" contexts

    # Session count for simulation
    num_sessions: int = 20


# Define realistic personas based on different user types
PERSONAS = {
    # =========================================================================
    # CASUAL USERS (~50% of population)
    # =========================================================================

    'junior_dev': UserPersona(
        name="Junior Developer",
        description="New to AI tools, trusts everything, shallow sessions",
        bash_acceptance=0.95,
        high_risk_acceptance=0.95,
        low_risk_acceptance=1.0,
        mean_decision_time_ms=300,
        decision_time_variance=0.5,
        uses_agents=False,
        agent_probability=0.0,
        parallel_tool_probability=0.01,
        mean_session_depth=15,
        session_depth_variance=0.8,
        tool_diversity=3,
        surgical_probability=0.1,
        edit_intensity=0.2,
        num_sessions=30,
    ),

    'hobbyist': UserPersona(
        name="Hobbyist / Side Project",
        description="Casual user, quick questions, high trust",
        bash_acceptance=0.98,
        high_risk_acceptance=0.98,
        low_risk_acceptance=1.0,
        mean_decision_time_ms=200,
        decision_time_variance=0.3,
        uses_agents=False,
        agent_probability=0.0,
        parallel_tool_probability=0.0,
        mean_session_depth=8,
        session_depth_variance=1.0,
        tool_diversity=2,
        surgical_probability=0.05,
        edit_intensity=0.15,
        num_sessions=25,
    ),

    'copilot_refugee': UserPersona(
        name="Copilot Refugee",
        description="Used to inline completion, learning Claude Code",
        bash_acceptance=0.85,
        high_risk_acceptance=0.9,
        low_risk_acceptance=1.0,
        mean_decision_time_ms=800,
        decision_time_variance=0.6,
        uses_agents=False,
        agent_probability=0.0,
        parallel_tool_probability=0.02,
        mean_session_depth=25,
        session_depth_variance=0.7,
        tool_diversity=4,
        surgical_probability=0.15,
        edit_intensity=0.3,
        num_sessions=20,
    ),

    # =========================================================================
    # POWER USERS (~25% of population)
    # =========================================================================

    'senior_swe': UserPersona(
        name="Senior Software Engineer",
        description="Experienced, uses agents, deep sessions, moderate caution",
        bash_acceptance=0.7,
        high_risk_acceptance=0.85,
        low_risk_acceptance=1.0,
        mean_decision_time_ms=1500,
        decision_time_variance=0.8,
        uses_agents=True,
        agent_probability=0.15,
        parallel_tool_probability=0.05,
        mean_session_depth=150,
        session_depth_variance=0.6,
        tool_diversity=9,
        surgical_probability=0.4,
        edit_intensity=0.25,
        num_sessions=25,
    ),

    'staff_engineer': UserPersona(
        name="Staff Engineer / Tech Lead",
        description="Orchestrates complex tasks, heavy agent usage",
        bash_acceptance=0.65,
        high_risk_acceptance=0.8,
        low_risk_acceptance=1.0,
        mean_decision_time_ms=2000,
        decision_time_variance=0.7,
        uses_agents=True,
        agent_probability=0.25,
        parallel_tool_probability=0.1,
        mean_session_depth=250,
        session_depth_variance=0.5,
        tool_diversity=11,
        surgical_probability=0.5,
        edit_intensity=0.2,
        num_sessions=20,
    ),

    'devops_sre': UserPersona(
        name="DevOps / SRE",
        description="Heavy Bash user, operational mindset, fast decisions",
        bash_acceptance=0.8,
        high_risk_acceptance=0.85,
        low_risk_acceptance=1.0,
        mean_decision_time_ms=600,
        decision_time_variance=0.5,
        uses_agents=True,
        agent_probability=0.1,
        parallel_tool_probability=0.03,
        mean_session_depth=80,
        session_depth_variance=0.7,
        tool_diversity=6,
        surgical_probability=0.3,
        edit_intensity=0.15,
        num_sessions=30,
    ),

    'data_scientist': UserPersona(
        name="Data Scientist / ML Engineer",
        description="Exploration-heavy, uses notebooks, moderate caution",
        bash_acceptance=0.75,
        high_risk_acceptance=0.85,
        low_risk_acceptance=1.0,
        mean_decision_time_ms=1200,
        decision_time_variance=0.6,
        uses_agents=True,
        agent_probability=0.08,
        parallel_tool_probability=0.02,
        mean_session_depth=60,
        session_depth_variance=0.8,
        tool_diversity=7,
        surgical_probability=0.35,
        edit_intensity=0.2,
        num_sessions=20,
    ),

    # =========================================================================
    # CAUTIOUS USERS (~25% of population)
    # =========================================================================

    'security_engineer': UserPersona(
        name="Security Engineer",
        description="Very cautious with Bash, reviews everything, slow",
        bash_acceptance=0.3,
        high_risk_acceptance=0.5,
        low_risk_acceptance=0.95,
        mean_decision_time_ms=5000,
        decision_time_variance=0.8,
        uses_agents=False,
        agent_probability=0.0,
        parallel_tool_probability=0.01,
        mean_session_depth=40,
        session_depth_variance=0.6,
        tool_diversity=5,
        surgical_probability=0.6,
        edit_intensity=0.1,
        num_sessions=15,
    ),

    'compliance_reviewer': UserPersona(
        name="Compliance / Code Reviewer",
        description="Reads a lot, rarely writes, very selective",
        bash_acceptance=0.4,
        high_risk_acceptance=0.6,
        low_risk_acceptance=1.0,
        mean_decision_time_ms=3000,
        decision_time_variance=0.7,
        uses_agents=False,
        agent_probability=0.0,
        parallel_tool_probability=0.0,
        mean_session_depth=30,
        session_depth_variance=0.5,
        tool_diversity=4,
        surgical_probability=0.7,
        edit_intensity=0.05,
        num_sessions=20,
    ),

    'paranoid_senior': UserPersona(
        name="Paranoid Senior Dev",
        description="Experienced but distrustful, rejects most Bash",
        bash_acceptance=0.25,
        high_risk_acceptance=0.6,
        low_risk_acceptance=1.0,
        mean_decision_time_ms=4000,
        decision_time_variance=0.9,
        uses_agents=True,
        agent_probability=0.05,
        parallel_tool_probability=0.02,
        mean_session_depth=100,
        session_depth_variance=0.7,
        tool_diversity=8,
        surgical_probability=0.5,
        edit_intensity=0.18,
        num_sessions=15,
    ),

    'prod_oncall': UserPersona(
        name="Production On-Call",
        description="Context-dependent: cautious in prod, fast in dev",
        bash_acceptance=0.5,  # Average of cautious/fast modes
        high_risk_acceptance=0.7,
        low_risk_acceptance=1.0,
        mean_decision_time_ms=2500,
        decision_time_variance=1.2,  # High variance = context-dependent
        uses_agents=True,
        agent_probability=0.12,
        parallel_tool_probability=0.04,
        mean_session_depth=70,
        session_depth_variance=0.9,
        tool_diversity=7,
        surgical_probability=0.45,
        edit_intensity=0.12,
        num_sessions=20,
        context_variance=0.8,
        bash_acceptance_high=0.95,
        bash_acceptance_low=0.2,
    ),

    # =========================================================================
    # CONTEXT-DEPENDENT USERS (high variance)
    # =========================================================================

    'context_switcher': UserPersona(
        name="Context Switcher",
        description="100% trust on maintenance, 1% on active dev - like Amadeus",
        bash_acceptance=0.5,  # Average
        high_risk_acceptance=0.8,
        low_risk_acceptance=1.0,
        mean_decision_time_ms=2000,
        decision_time_variance=0.8,
        uses_agents=True,
        agent_probability=0.1,
        parallel_tool_probability=0.05,
        mean_session_depth=100,
        session_depth_variance=0.7,
        tool_diversity=8,
        surgical_probability=0.4,
        edit_intensity=0.2,
        num_sessions=25,
        context_variance=1.0,  # Maximum variance
        bash_acceptance_high=1.0,
        bash_acceptance_low=0.05,
    ),

    'project_guardian': UserPersona(
        name="Project Guardian",
        description="Trusts familiar projects, cautious on new codebases",
        bash_acceptance=0.6,
        high_risk_acceptance=0.75,
        low_risk_acceptance=1.0,
        mean_decision_time_ms=1800,
        decision_time_variance=0.7,
        uses_agents=True,
        agent_probability=0.08,
        parallel_tool_probability=0.03,
        mean_session_depth=60,
        session_depth_variance=0.6,
        tool_diversity=6,
        surgical_probability=0.35,
        edit_intensity=0.18,
        num_sessions=20,
        context_variance=0.6,
        bash_acceptance_high=0.9,
        bash_acceptance_low=0.3,
    ),

    'sprint_mode': UserPersona(
        name="Sprint Mode Dev",
        description="Fast & trusting during sprints, careful during releases",
        bash_acceptance=0.7,
        high_risk_acceptance=0.85,
        low_risk_acceptance=1.0,
        mean_decision_time_ms=1200,
        decision_time_variance=0.9,
        uses_agents=True,
        agent_probability=0.15,
        parallel_tool_probability=0.06,
        mean_session_depth=120,
        session_depth_variance=0.8,
        tool_diversity=9,
        surgical_probability=0.4,
        edit_intensity=0.22,
        num_sessions=25,
        context_variance=0.5,
        bash_acceptance_high=0.95,
        bash_acceptance_low=0.4,
    ),
}


# ============================================================================
# Session Generator
# ============================================================================

def generate_tool_sequence(persona: UserPersona, session_depth: int) -> List[str]:
    """Generate a realistic sequence of tools for a session."""
    sequence = []

    # Build tool probability distribution based on persona
    tool_weights = {}

    # Bash is always common
    tool_weights['Bash'] = 0.35

    # Read/Edit based on edit intensity
    tool_weights['Read'] = 0.15 * (1 - persona.edit_intensity)
    tool_weights['Edit'] = 0.15 * persona.edit_intensity
    tool_weights['Write'] = 0.08 * persona.edit_intensity

    # Search tools based on surgical probability
    tool_weights['Glob'] = 0.08 * persona.surgical_probability
    tool_weights['Grep'] = 0.08 * persona.surgical_probability

    # Agents if enabled
    if persona.uses_agents:
        tool_weights['Task'] = 0.05 * persona.agent_probability * 10
        tool_weights['TaskOutput'] = 0.05 * persona.agent_probability * 10

    # Utility
    tool_weights['TodoWrite'] = 0.05
    tool_weights['WebSearch'] = 0.03
    tool_weights['WebFetch'] = 0.02

    # Normalize weights
    total = sum(tool_weights.values())
    tool_weights = {k: v / total for k, v in tool_weights.items()}

    tools = list(tool_weights.keys())
    weights = list(tool_weights.values())

    # Generate sequence with some realistic patterns
    for i in range(session_depth):
        # Surgical pattern: Glob/Grep often followed by Read
        if i > 0 and sequence[-1] in ['Glob', 'Grep'] and random.random() < 0.6:
            sequence.append('Read')
        # Task often followed by TaskOutput
        elif i > 0 and sequence[-1] == 'Task' and random.random() < 0.8:
            sequence.append('TaskOutput')
        # Otherwise random based on weights
        else:
            sequence.append(random.choices(tools, weights=weights)[0])

    return sequence


def generate_decision_time(persona: UserPersona, tool: str) -> int:
    """Generate realistic decision time for a tool."""
    base_time = persona.mean_decision_time_ms

    # Adjust based on tool risk
    tool_info = TOOLS.get(tool, {'risk': 'low'})
    if tool_info['risk'] == 'high':
        base_time *= 1.5  # Slower for risky tools
    else:
        base_time *= 0.5  # Faster for safe tools

    # Add variance
    variance = base_time * persona.decision_time_variance
    time = int(random.gauss(base_time, variance))

    # Clamp to reasonable range
    return max(50, min(time, 60000))


def generate_acceptance(persona: UserPersona, tool: str, session_context: str = 'normal') -> bool:
    """Determine if user accepts or rejects the tool call."""
    if tool == 'Bash':
        # Use context-dependent acceptance if persona has variance
        if persona.context_variance > 0 and session_context != 'normal':
            if session_context == 'high_trust':
                return random.random() < persona.bash_acceptance_high
            elif session_context == 'low_trust':
                return random.random() < persona.bash_acceptance_low
        return random.random() < persona.bash_acceptance
    elif TOOLS.get(tool, {}).get('risk') == 'high':
        return random.random() < persona.high_risk_acceptance
    else:
        return random.random() < persona.low_risk_acceptance


def generate_session(persona: UserPersona, session_num: int, project_name: str = None) -> Dict:
    """Generate a complete synthetic session."""
    # Determine session context based on persona's variance
    session_context = 'normal'
    if persona.context_variance > 0:
        # Randomly assign this session to high or low trust context
        if random.random() < 0.5:
            session_context = 'high_trust'
        else:
            session_context = 'low_trust'

    # Determine session depth with variance
    depth_variance = persona.mean_session_depth * persona.session_depth_variance
    session_depth = max(1, int(random.gauss(persona.mean_session_depth, depth_variance)))

    # Limit diversity to available tools
    actual_diversity = min(persona.tool_diversity, len(TOOLS))

    # Generate tool sequence
    tool_sequence = generate_tool_sequence(persona, session_depth)

    # Generate timestamps
    start_time = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))
    current_time = start_time

    events = []
    session_id = str(uuid.uuid4())

    # Generate project name if not provided
    if project_name is None:
        if session_context == 'high_trust':
            project_name = f"-Users-simulated-stable-project-{session_num % 3}"
        elif session_context == 'low_trust':
            project_name = f"-Users-simulated-active-dev-{session_num % 3}"
        else:
            project_name = f"-Users-simulated-project-{session_num % 5}"

    for i, tool in enumerate(tool_sequence):
        # Assistant message with tool_use
        tool_id = f"tool_{uuid.uuid4().hex[:12]}"

        # Generate a plausible command for Bash
        bash_input = {"simulated": True}
        if tool == 'Bash':
            bash_input = {"command": f"simulated_command_{i}", "simulated": True}

        assistant_event = {
            "type": "assistant",
            "timestamp": current_time.isoformat(),
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": tool_id,
                        "name": tool,
                        "input": bash_input
                    }
                ]
            }
        }
        events.append(assistant_event)

        # Decision time
        decision_time_ms = generate_decision_time(persona, tool)
        current_time += timedelta(milliseconds=decision_time_ms)

        # User message with tool_result
        accepted = generate_acceptance(persona, tool, session_context)

        if accepted:
            result_content = f"Simulated {tool} result"
            is_error = False
        else:
            result_content = f"Tool {tool} requires approval. User rejected."
            is_error = True

        user_event = {
            "type": "user",
            "timestamp": current_time.isoformat(),
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result_content,
                        "is_error": is_error
                    }
                ]
            }
        }
        events.append(user_event)

        # Small gap before next tool
        current_time += timedelta(milliseconds=random.randint(100, 500))

    return {
        "session_id": session_id,
        "persona": persona.name,
        "project": project_name,
        "session_context": session_context,
        "events": events,
        "metadata": {
            "tool_count": len(tool_sequence),
            "start_time": start_time.isoformat(),
            "end_time": current_time.isoformat(),
            "project": project_name,
        }
    }


# ============================================================================
# Output
# ============================================================================

def write_sessions_to_jsonl(sessions: List[Dict], output_dir: Path, persona_name: str):
    """Write sessions in Claude Code log format."""
    # Group sessions by project
    projects = {}
    for session in sessions:
        proj = session.get('project', 'default')
        if proj not in projects:
            projects[proj] = []
        projects[proj].append(session)

    # Write each project's sessions to its own directory
    total_written = 0
    for proj, proj_sessions in projects.items():
        proj_dir = output_dir / proj
        proj_dir.mkdir(parents=True, exist_ok=True)

        for session in proj_sessions:
            session_file = proj_dir / f"{session['session_id']}.jsonl"
            with open(session_file, 'w') as f:
                for event in session['events']:
                    f.write(json.dumps(event) + '\n')
            total_written += 1

    print(f"  Wrote {total_written} sessions for {persona_name} across {len(projects)} projects")


def generate_summary(all_sessions: Dict[str, List[Dict]]) -> Dict:
    """Generate summary statistics for all simulated users."""
    summary = {
        "total_sessions": 0,
        "total_tool_calls": 0,
        "personas": {}
    }

    for persona_name, sessions in all_sessions.items():
        total_tools = sum(s['metadata']['tool_count'] for s in sessions)
        summary["total_sessions"] += len(sessions)
        summary["total_tool_calls"] += total_tools
        summary["personas"][persona_name] = {
            "sessions": len(sessions),
            "tool_calls": total_tools,
            "mean_depth": total_tools / len(sessions) if sessions else 0
        }

    return summary


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Simulate diverse Claude Code users")
    parser.add_argument('--output', type=str, default='~/.suzerain/simulated',
                        help='Output directory for simulated sessions')
    parser.add_argument('--personas', type=str, nargs='*',
                        help='Specific personas to simulate (default: all)')
    parser.add_argument('--list', action='store_true',
                        help='List available personas')
    parser.add_argument('--scale', type=float, default=1.0,
                        help='Scale factor for number of sessions')

    args = parser.parse_args()

    if args.list:
        print("\nAvailable Personas:")
        print("-" * 60)
        for key, persona in PERSONAS.items():
            print(f"\n{key}:")
            print(f"  {persona.name}")
            print(f"  {persona.description}")
            print(f"  Bash acceptance: {persona.bash_acceptance:.0%}")
            print(f"  Uses agents: {persona.uses_agents}")
            print(f"  Session depth: ~{persona.mean_session_depth}")
        return

    output_dir = Path(args.output).expanduser()

    # Select personas
    if args.personas:
        selected = {k: PERSONAS[k] for k in args.personas if k in PERSONAS}
    else:
        selected = PERSONAS

    print(f"\nSimulating {len(selected)} user personas...")
    print("=" * 60)

    all_sessions = {}

    for key, persona in selected.items():
        num_sessions = int(persona.num_sessions * args.scale)
        print(f"\n{persona.name} ({num_sessions} sessions)...")

        sessions = []
        for i in range(num_sessions):
            session = generate_session(persona, i)
            sessions.append(session)

        # Write to persona-specific directory
        persona_dir = output_dir / key.replace(' ', '_').lower()
        write_sessions_to_jsonl(sessions, persona_dir, persona.name)

        all_sessions[key] = sessions

    # Write summary
    summary = generate_summary(all_sessions)
    summary_file = output_dir / "simulation_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 60)
    print(f"Simulation complete!")
    print(f"  Total sessions: {summary['total_sessions']}")
    print(f"  Total tool calls: {summary['total_tool_calls']}")
    print(f"  Output: {output_dir}")
    print(f"  Summary: {summary_file}")


if __name__ == "__main__":
    main()
