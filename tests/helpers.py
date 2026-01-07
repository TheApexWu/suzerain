"""
Shared test helpers for Suzerain test suite.

"They rode on."
"""


class MockStdout:
    """Mock stdout object with fileno support for subprocess mocks."""

    def __init__(self, lines):
        self._lines = lines
        self._iter = iter(lines)

    def fileno(self):
        """Raise OSError to trigger fallback to blocking reads."""
        raise OSError("Mock fileno not supported")

    def readline(self):
        try:
            return next(self._iter) + "\n"
        except StopIteration:
            return ""

    def __iter__(self):
        return iter(self._lines)

    def __next__(self):
        return next(self._iter)
