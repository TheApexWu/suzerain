# Data Sharing Architecture

## Philosophy

1. **Local-first:** All analysis runs on your machine
2. **Opt-in only:** Nothing shared without explicit consent
3. **Preview before send:** See exactly what would be shared
4. **Minimal data:** Only aggregate metrics, never content
5. **Anonymized:** No way to identify individuals from shared data

---

## User Flow

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  $ suzerain analyze                                          │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ YOUR GOVERNANCE PROFILE                                │  │
│  │                                                        │  │
│  │ Pattern: Power User (Cautious)                         │  │
│  │ Archetype: Strategist                                  │  │
│  │                                                        │  │
│  │ Bash acceptance: 50.5%                                 │  │
│  │ Agent spawn rate: 8.6%                                 │  │
│  │ Sophistication: 0.75                                   │  │
│  │ Caution: 0.80                                          │  │
│  │                                                        │  │
│  │ [View Details] [Share with Research] [Exit]            │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  → User clicks "Share with Research"                         │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ DATA SHARING PREVIEW                                   │  │
│  │                                                        │  │
│  │ The following will be shared:                          │  │
│  │                                                        │  │
│  │ ✓ Aggregate metrics (acceptance rates, timing)         │  │
│  │ ✓ Classification results                               │  │
│  │ ✓ Session counts and durations                         │  │
│  │                                                        │  │
│  │ NOT shared:                                            │  │
│  │ ✗ Prompts or conversations                             │  │
│  │ ✗ File paths or code                                   │  │
│  │ ✗ Command contents                                     │  │
│  │ ✗ Project names                                        │  │
│  │                                                        │  │
│  │ [View Raw JSON] [Confirm Share] [Cancel]               │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  → User clicks "View Raw JSON"                               │
│                                                              │
│  {                                                           │
│    "user_id": "anon_a7f3c2...",                              │
│    "governance_features": {                                  │
│      "bash_acceptance_rate": 0.505,                          │
│      ...                                                     │
│    }                                                         │
│  }                                                           │
│                                                              │
│  [Confirm Share] [Cancel]                                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Data Schema

### What's Collected

```python
@dataclass
class SharedMetrics:
    """Anonymized metrics shared with research."""

    # Anonymous identifier (hash of machine ID + salt)
    user_id: str

    # Timing
    collected_at: datetime
    suzerain_version: str

    # Summary (no identifying info)
    summary: dict = {
        "sessions_analyzed": int,
        "total_tool_calls": int,
        "data_days": int,  # Duration, not dates
    }

    # Governance features (aggregate only)
    governance: dict = {
        "bash_acceptance_rate": float,
        "overall_acceptance_rate": float,
        "high_risk_acceptance": float,
        "low_risk_acceptance": float,
        "mean_decision_time_ms": float,
        "snap_judgment_rate": float,
        "risk_trust_delta": float,
    }

    # Sophistication features
    sophistication: dict = {
        "agent_spawn_rate": float,
        "tool_diversity": float,
        "mean_session_depth": float,
        "power_session_ratio": float,
        "surgical_ratio": float,
        "edit_intensity": float,
    }

    # Classification results
    classification: dict = {
        "primary_pattern": str,
        "sophistication_score": float,
        "caution_score": float,
        "archetype": str,
        "archetype_confidence": float,
    }

    # Optional demographic (user can skip)
    demographic: dict = {
        "experience_level": str,  # "junior", "mid", "senior", "staff"
        "primary_role": str,      # "frontend", "backend", "fullstack", etc.
        "company_size": str,      # "solo", "startup", "enterprise"
    }
```

### What's NOT Collected

```python
# NEVER COLLECTED - Privacy Protected
REDACTED = {
    "prompts": "User's actual prompts to Claude",
    "responses": "Claude's responses",
    "file_paths": "Any file or directory names",
    "file_contents": "Any code or text content",
    "command_contents": "Actual Bash commands",
    "project_names": "Project or repo names",
    "timestamps": "Actual dates/times (only durations)",
    "ip_address": "Network identifiers",
    "machine_id": "Hardware identifiers (hashed only)",
    "username": "System username",
    "env_vars": "Environment variables",
}
```

---

## Collection Endpoint

### Simple API

```
POST https://api.suzerain.dev/v1/metrics

Headers:
  Content-Type: application/json
  X-Suzerain-Version: 0.2.0

Body:
  {SharedMetrics as JSON}

Response:
  201 Created
  {
    "id": "submission_abc123",
    "message": "Thank you for contributing to the research!"
  }
```

### Privacy Measures

1. **No auth required:** No accounts, no tracking
2. **No cookies:** Stateless submissions
3. **IP anonymization:** IPs stripped at edge before logging
4. **Encryption:** TLS in transit, encrypted at rest
5. **Retention:** Raw submissions deleted after aggregation (30 days)

---

## Aggregation & Publishing

### What Gets Published

Weekly aggregated statistics on the live dashboard:

```
Total Participants: 247
Total Tool Calls Analyzed: 1.2M

Pattern Distribution:
  Casual (Trusting):    42%
  Casual (Cautious):    18%
  Power User (Trusting): 12%
  Power User (Cautious): 28%

Archetype Distribution:
  Delegator:        38%
  Strategist:       31%
  Deliberator:      12%
  Autocrat:          9%
  Council:           6%
  Constitutionalist: 4%

Feature Distributions:
  Bash acceptance: [histogram]
  Sophistication:  [histogram]
  Caution:         [histogram]
```

### What's NEVER Published

- Individual submissions
- Any data that could identify users
- Demographic breakdowns with <10 participants (k-anonymity)

---

## User Controls

### Opt-Out

```bash
# Never asked to share again
suzerain config set share_prompts false

# Delete any previously shared data
suzerain data delete --user-id anon_a7f3c2...
```

### Data Portability

```bash
# Export your local analysis
suzerain export --format json > my_governance.json

# See what you've shared
suzerain data history
```

---

## Technical Implementation

### Backend Stack (Minimal)

```
Vercel Edge Function (API)
     │
     ▼
Upstash Redis (Queue)
     │
     ▼
Cloudflare R2 (Storage)
     │
     ▼
Daily Aggregation Job
     │
     ▼
Public Dashboard (Static)
```

### Why Minimal?

- No database = no breach target
- Edge functions = no server to maintain
- Static dashboard = CDN-cached, fast
- Total cost: ~$0/month at low scale

---

## Legal

### Terms

By sharing data, you agree that:
1. The data is yours to share (your own Claude Code usage)
2. Data will be used for research and aggregated statistics
3. Individual data may be deleted upon request
4. Aggregated, anonymized results may be published

### No Warranty

Suzerain is provided as-is for research purposes. Classifications are not professional assessments. Don't make career decisions based on being called a "Delegator."

---

## Questions?

Open an issue: https://github.com/[you]/suzerain/issues
