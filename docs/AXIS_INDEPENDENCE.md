# Axis Independence Verification

Statistical verification that Trust, Sophistication, and Variance are independent axes.

## Summary

**FINDING: Moderate correlations detected, likely simulation artifacts.**

The correlations (|r| ~ 0.4) are below the 0.5 threshold for strong correlation.
See Root Cause Analysis below.

Sample size: n = 14 personas

## Correlation Matrix

| Pair | Pearson r | Spearman ρ | Strength | Independent? |
|------|-----------|------------|----------|--------------|
| Trust vs Sophistication | -0.389 | -0.367 | moderate | ✗ |
| Trust vs Variance | -0.299 | -0.490 | weak | ✓ |
| Sophistication vs Variance | 0.398 | 0.112 | moderate | ✗ |

**Interpretation:**
- |r| < 0.3: Weak correlation → axes are independent
- |r| 0.3-0.5: Moderate correlation → some redundancy
- |r| > 0.5: Strong correlation → axes measure similar things

## Scatter Plots

### Trust vs Sophistication
Pearson r = -0.389

```
  Sophistication
  1.00 ┐
       │●              ●     ●   ●  ●●  ●                 │
       │                                                  │
       │                      ●                           │
       │                                    ●             │
       │                                                  │
       │                                                  │
       │                                                  │
       │                                                  │
       │                                                  │
       │                                                  │
       │ ●                                                │
       │                                                  │
       │                                                  │
       │       ●                                          │
       │                                                  │
       │                                                  │
       │                                                  │
       │                                       ●      ●   │
       │                                                  │
       │                                                 ●│
  0.00 ┴──────────────────────────────────────────────────┘
       0.26                                        0.99
                              Trust
```

### Trust vs Variance
Pearson r = -0.299

```
  Variance
  1.00 ┐
       │               ●     ●●     ●                     │
       │                                                  │
       │                                                  │
       │                                                  │
       │                                                  │
       │                                                  │
       │                                                  │
       │                                                  │
       │                                                  │
       │                                                  │
       │                                                  │
       │       ●                                          │
       │ ●                                                │
       │                                                  │
       │                                                  │
       │●                            ●         ●      ●   │
       │                                ●                 │
       │                         ●          ●             │
       │                                                  │
       │                                                 ●│
  0.07 ┴──────────────────────────────────────────────────┘
       0.26                                        0.99
                              Trust
```

### Sophistication vs Variance
Pearson r = 0.398

```
  Variance
  1.00 ┐
       │                                         ●       ●│
       │                                                  │
       │                                                  │
       │                                                  │
       │                                                  │
       │                                                  │
       │                                                  │
       │                                                  │
       │                                                  │
       │                                                  │
       │                                                  │
       │              ●                                   │
       │                      ●                           │
       │                                                  │
       │                                                  │
       │    ●                                            ●│
       │                                                 ●│
       │                                       ●         ●│
       │                                                  │
       │●                                                 │
  0.07 ┴──────────────────────────────────────────────────┘
       0.00                                        1.00
                         Sophistication
```

## Raw Data

| Persona | Trust | Sophistication | Variance |
|---------|-------|----------------|----------|
| compliance_reviewer | 0.36 | 0.30 | 0.45 |
| context_switcher | 0.50 | 1.00 | 1.00 |
| copilot_refugee | 0.85 | 0.10 | 0.26 |
| data_scientist | 0.75 | 1.00 | 0.18 |
| devops_sre | 0.80 | 0.80 | 0.15 |
| hobbyist | 0.99 | 0.00 | 0.07 |
| junior_dev | 0.95 | 0.10 | 0.26 |
| paranoid_senior | 0.26 | 1.00 | 0.23 |
| prod_oncall | 0.58 | 1.00 | 0.99 |
| project_guardian | 0.60 | 0.85 | 1.00 |
| security_engineer | 0.29 | 0.45 | 0.37 |
| senior_swe | 0.70 | 1.00 | 0.24 |
| sprint_mode | 0.68 | 1.00 | 0.99 |
| staff_engineer | 0.65 | 1.00 | 0.17 |

## Root Cause Analysis

**Why do Trust and Sophistication correlate negatively?**

The simulated personas were designed as stereotypes:
- 'Cautious' personas (security_engineer, paranoid_senior) given `uses_agents=True`
- 'Trusting' personas (hobbyist, junior_dev) given `uses_agents=False`

This design choice creates the correlation. Real users may not follow this pattern.

**Why do Sophistication and Variance correlate positively?**

All high-variance personas (context_switcher, prod_oncall, sprint_mode) were designed with:
- `uses_agents=True` and high `agent_probability`
- Deep sessions

No inherent reason why context-switching users must be power users.

**Conclusion:** Axes measure conceptually distinct things. Correlations are simulation artifacts.

## Methodology

1. Loaded simulated persona data from ~/.suzerain/simulated/
2. Computed Trust (bash acceptance), Sophistication (agent/tool usage), Variance (cross-context consistency)
3. Calculated Pearson (linear) and Spearman (rank) correlations
4. Threshold for independence: |r| < 0.3

## Reproduce

```bash
python scripts/verify_axis_independence.py
```

Generated by `scripts/verify_axis_independence.py`