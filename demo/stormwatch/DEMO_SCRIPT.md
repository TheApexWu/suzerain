# Suzerain Demo Script

> Using voice commands to develop Stormwatch

## Setup

```bash
cd demo/stormwatch
```

## Demo Commands

### 1. Survey the project
**Say:** "the kid looked at the expanse"

Claude will analyze the project structure, dependencies, and recent activity.

### 2. Run tests
**Say:** "the judge smiled"

Claude will detect pytest and run the test suite.

### 3. Research something
**Say:** "tell me about the country ahead"

Claude will research a topic (e.g., weather API options).

### 4. Clean up
**Say:** "the fires on the plain"

Claude will clean build artifacts and caches.

### 5. Add a feature (with dry-run)
**Say:** "night of your birth and the judge watched"

The "judge watched" modifier makes it a dry run - shows what would be created.

### 6. Commit changes
**Say:** "the blood dried"

Claude will stage and commit with a proper message.

## Running the Demo

```bash
# From suzerain root
python src/main.py --test --sandbox  # Type commands, no execution

# Or with execution
python src/main.py --test             # Type commands, execute via Claude

# With voice
python src/main.py                     # Push-to-talk
python src/main.py --wake              # Wake word ("computer")
```

## Notes

- Use `--sandbox` to see expansions without execution
- Use `--timing` to see latency breakdown
- Use `--warm` to pre-warm Claude connection
- Modifiers can be appended: "...and the judge watched" (dry run)
