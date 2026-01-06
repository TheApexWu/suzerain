# Deploy Sigil

The evening redness in the west.

## Instructions

This command handles deployment. Currently just packages for distribution.

1. Run tests first: `python -m pytest tests/ -v`
2. If tests pass, create distribution:
   ```bash
   python -m build
   ```
3. Report success or failure

For production deployment (future):
- Push to PyPI
- Update version in pyproject.toml
- Create git tag
