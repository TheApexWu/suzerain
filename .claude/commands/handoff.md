# Generate Handoff Summary

Create a handoff document summarizing current project state for context continuity.

## Instructions

1. Read recent git commits: `git log --oneline -10`
2. Check current branch and status: `git status`
3. Review any TODO comments in source files
4. Summarize:
   - What was just completed
   - What's currently in progress
   - Known blockers or issues
   - Next recommended actions

Output format:
```markdown
## Handoff: [Date]

### Completed
- [items]

### In Progress
- [items]

### Blockers
- [items]

### Next Steps
- [items]
```

Save to `HANDOFF.md` in project root.
