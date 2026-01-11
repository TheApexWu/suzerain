# Empirical Approach: Data-Driven Governance Archetypes

> Don't pick archetypes from history and fit users into them.
> Let the data reveal natural clusters, then interpret.

---

## The Problem with Top-Down Archetypes

We initially picked 5 historical governance models:
- Roman Emperor
- Venetian Republic
- Athenian Democracy
- Mongol Horde
- Constitutional Monarchy

But this is **storytelling, not science**. We don't know:
- Do users actually cluster into distinct types?
- Are there 3 types? 7? 12?
- Is it a spectrum, not categories?
- Do historical models even map to AI usage patterns?

---

## The Rigorous Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  1. OBSERVE    →  Raw events from AI tool usage             │
│                                                             │
│  2. ENGINEER   →  Behavioral feature vectors per user       │
│                                                             │
│  3. EXPLORE    →  Distributions, correlations, PCA          │
│                                                             │
│  4. CLUSTER    →  Let data reveal natural groupings         │
│                   (maybe 3, maybe 7, maybe continuous)      │
│                                                             │
│  5. INTERPRET  →  What does each cluster mean behaviorally? │
│                                                             │
│  6. NARRATE    →  IF historical parallel fits, use it       │
│                   IF NOT, create new archetype name         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Define Measurable Features

### Raw Observable Events

```python
event_schema = {
    "timestamp": datetime,
    "event_type": ["suggestion_shown", "accepted", "rejected", "edited", "undone"],
    "time_to_decision_ms": int,        # How long did they think?
    "edit_distance": float,            # How much did they modify after accepting?
    "task_context": str,               # What were they doing? (test, deploy, refactor)
    "session_length": int,             # How long is this working session?
    "consecutive_accepts": int,        # Are they rubber-stamping?
    "consecutive_rejects": int,        # Are they in "no" mode?
}
```

---

## Phase 2: Engineer Features (Per User/Session)

```python
user_features = {
    # Approval patterns
    "acceptance_rate": float,              # % of suggestions accepted
    "rejection_rate": float,               # % explicitly rejected (vs ignored)
    "edit_after_accept_rate": float,       # % of accepts that get modified

    # Timing patterns
    "mean_decision_time_ms": float,        # Deliberate or snap judgments?
    "decision_time_variance": float,       # Consistent or context-dependent?
    "time_to_first_action": float,         # Do they review before acting?

    # Trust patterns
    "trust_by_context": {                  # Do they trust differently by task?
        "test": float,
        "deploy": float,
        "refactor": float,
        "docs": float,
    },
    "streak_behavior": float,              # Tendency to rubber-stamp in streaks

    # Correction patterns
    "undo_rate": float,                    # How often do they regret?
    "mean_edit_distance": float,           # How much do they modify suggestions?

    # Session patterns
    "interventions_per_hour": float,       # Active management or hands-off?
    "session_consistency": float,          # Same behavior across sessions?
}
```

---

## Phase 3: Exploratory Analysis

Before clustering, understand the distributions:

```python
import pandas as pd
import seaborn as sns
from sklearn.decomposition import PCA

# Load user feature vectors
df = pd.read_parquet("user_features.parquet")

# 1. Univariate distributions - are these continuous or bimodal?
for col in df.columns:
    sns.histplot(df[col], kde=True)
    # Look for: natural breakpoints? bimodal? power law?

# 2. Correlation matrix - which features move together?
sns.heatmap(df.corr(), annot=True)
# Look for: feature clusters that represent latent "governance style"

# 3. PCA - how many dimensions actually matter?
pca = PCA()
pca.fit(df_scaled)
plt.plot(pca.explained_variance_ratio_.cumsum())
# Look for: elbow point = intrinsic dimensionality of governance behavior
```

### Key Questions
- Is `acceptance_rate` bimodal (two types) or normal (spectrum)?
- Do `decision_time` and `edit_rate` correlate? (deliberate editors?)
- Is context-sensitivity a real dimension, or noise?

---

## Phase 4: Clustering (Let Data Speak)

```python
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

# Normalize features
scaler = StandardScaler()
X = scaler.fit_transform(df)

# Try multiple K values - don't assume 5
results = []
for k in range(2, 12):
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X)
    score = silhouette_score(X, labels)
    results.append({"k": k, "silhouette": score})

# Also try hierarchical - see dendrogram structure
from scipy.cluster.hierarchy import dendrogram, linkage
Z = linkage(X, method='ward')
dendrogram(Z)
```

### Possible Outcomes
1. **Clear clusters (k=4, silhouette=0.6+)** → Natural archetypes exist
2. **Weak clusters (silhouette<0.3)** → It's a spectrum, not types
3. **Hierarchical structure** → Nested archetypes (broad types with subtypes)

---

## Phase 5: Interpret Clusters (Post-Hoc)

Only AFTER finding natural clusters, examine what they mean:

```python
# Get cluster centers
centers = pd.DataFrame(
    scaler.inverse_transform(kmeans.cluster_centers_),
    columns=df.columns
)

# For each cluster, identify defining characteristics
for i, row in centers.iterrows():
    print(f"\n=== Cluster {i} ===")
    for col in df.columns:
        z = (row[col] - df[col].mean()) / df[col].std()
        if abs(z) > 1:
            print(f"  {col}: {row[col]:.2f} (z={z:+.1f})")
```

### Example Output (Hypothetical)
```
=== Cluster 0 ===
  acceptance_rate: 0.92 (z=+2.1)       # Very high acceptance
  decision_time_ms: 340 (z=-1.8)       # Fast decisions
  interventions_per_hour: 2.1 (z=-1.5) # Hands-off

=== Cluster 1 ===
  acceptance_rate: 0.31 (z=-1.4)       # Low acceptance
  edit_after_accept_rate: 0.67 (z=+2.3) # Heavy editing
  decision_time_ms: 2400 (z=+1.9)      # Deliberate
```

---

## Phase 6: Historical Mapping (If It Fits)

Only now ask: Do these empirical clusters resemble historical governance?

| Cluster | Empirical Profile | Historical Analog? | Fit Quality |
|---------|-------------------|-------------------|-------------|
| 0 | High accept, fast, hands-off | Mongol Horde | Strong |
| 1 | Low accept, heavy edit, slow | ??? (no analog) | None |
| 2 | Context-dependent trust | Venetian Republic | Medium |

**Key insight:** Maybe only 3 of 5 historical models appear in real data. Maybe a 6th pattern emerges with no historical parallel. That's fine.

---

## Data Acquisition Strategy

See: `DATA_SOURCES.md`

---

## Success Criteria

- [ ] Collect N>100 user behavior samples
- [ ] Identify natural cluster count (silhouette analysis)
- [ ] Characterize each cluster behaviorally
- [ ] Determine if historical mapping adds value or is forced
- [ ] Ship honest archetypes (data-driven, not marketing-driven)

---

*"The map is not the territory. The archetype is not the user."*
