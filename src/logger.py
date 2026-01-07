"""
Suzerain structured logging module.

Provides JSON-formatted logs with rotation for parsing and analysis.
"""

import json
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional


# Default configuration
DEFAULT_LOG_DIR = Path.home() / ".suzerain" / "logs"
DEFAULT_LOG_FILE = "suzerain.log"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
MAX_LOG_FILES = 5


class JSONFormatter(logging.Formatter):
    """
    Formats log records as JSON for structured logging.

    Output format:
    {
        "timestamp": "2024-01-15T10:30:00.123456",
        "level": "INFO",
        "component": "parser",
        "message": "Matched command",
        "context": {...}
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "component": getattr(record, "component", record.name),
            "message": record.getMessage(),
        }

        # Add context if present
        context = getattr(record, "context", None)
        if context:
            log_entry["context"] = context

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class ColoredConsoleFormatter(logging.Formatter):
    """
    Colored console output formatter for human readability.
    Keeps terminal UX colored while using structured logging.
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",    # Cyan
        "INFO": "\033[32m",     # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",    # Red
        "CRITICAL": "\033[41m", # Red background
    }
    RESET = "\033[0m"
    DIM = "\033[2m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        component = getattr(record, "component", record.name)

        # Format: [LEVEL] [component] message
        formatted = f"{color}[{record.levelname}]{self.RESET} "
        formatted += f"{self.DIM}[{component}]{self.RESET} "
        formatted += record.getMessage()

        # Add context summary if present (not full dump)
        context = getattr(record, "context", None)
        if context and record.levelname == "DEBUG":
            context_str = ", ".join(f"{k}={v}" for k, v in context.items())
            formatted += f" {self.DIM}({context_str}){self.RESET}"

        return formatted


class SuzerainLogger:
    """
    Main logger class for Suzerain.

    Usage:
        from logger import get_logger
        log = get_logger("parser")
        log.info("Matched command", context={"phrase": "they rode on", "score": 95})
    """

    _instance: Optional["SuzerainLogger"] = None
    _loggers: Dict[str, logging.Logger] = {}
    _initialized = False

    def __init__(self):
        self.log_dir = DEFAULT_LOG_DIR
        self.log_file = DEFAULT_LOG_FILE
        self.file_handler: Optional[RotatingFileHandler] = None
        self.console_handler: Optional[logging.StreamHandler] = None
        self.level = logging.INFO
        self.verbose = False

    @classmethod
    def get_instance(cls) -> "SuzerainLogger":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def setup(
        self,
        log_dir: Optional[Path] = None,
        verbose: bool = False,
        console_output: bool = True
    ) -> None:
        """
        Initialize logging system.

        Args:
            log_dir: Directory for log files (default: ~/.suzerain/logs)
            verbose: Enable DEBUG level logging
            console_output: Enable colored console output
        """
        if log_dir:
            self.log_dir = Path(log_dir)

        self.verbose = verbose
        self.level = logging.DEBUG if verbose else logging.INFO

        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)

        log_path = self.log_dir / self.log_file

        # Set up rotating file handler with JSON formatting
        self.file_handler = RotatingFileHandler(
            log_path,
            maxBytes=MAX_LOG_SIZE,
            backupCount=MAX_LOG_FILES,
            encoding="utf-8"
        )
        self.file_handler.setFormatter(JSONFormatter())
        self.file_handler.setLevel(logging.DEBUG)  # File always captures everything

        # Set up console handler if requested
        if console_output:
            self.console_handler = logging.StreamHandler(sys.stderr)
            self.console_handler.setFormatter(ColoredConsoleFormatter())
            self.console_handler.setLevel(self.level)

        self._initialized = True

        # Update any existing loggers
        for logger in self._loggers.values():
            self._configure_logger(logger)

    def _configure_logger(self, logger: logging.Logger) -> None:
        """Configure a logger with current handlers."""
        logger.setLevel(logging.DEBUG)  # Logger captures all, handlers filter

        # Remove existing handlers
        logger.handlers.clear()

        if self.file_handler:
            logger.addHandler(self.file_handler)

        if self.console_handler and self.verbose:
            logger.addHandler(self.console_handler)

    def get_logger(self, component: str) -> logging.Logger:
        """
        Get a logger for a specific component.

        Args:
            component: Name of the component (e.g., "parser", "executor", "main")

        Returns:
            Configured logger instance
        """
        if component in self._loggers:
            return self._loggers[component]

        logger = logging.getLogger(f"suzerain.{component}")
        logger.propagate = False

        if self._initialized:
            self._configure_logger(logger)

        self._loggers[component] = logger
        return logger


class ComponentLogger:
    """
    Wrapper that adds component context to log calls.

    Provides convenience methods for logging with context.
    """

    def __init__(self, logger: logging.Logger, component: str):
        self._logger = logger
        self._component = component

    def _log(
        self,
        level: int,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        exc_info: bool = False
    ) -> None:
        """Internal log method that adds component and context."""
        extra = {"component": self._component}
        if context:
            extra["context"] = context

        self._logger.log(level, message, extra=extra, exc_info=exc_info)

    def debug(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log debug message (only shown in verbose mode)."""
        self._log(logging.DEBUG, message, context)

    def info(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log info message."""
        self._log(logging.INFO, message, context)

    def warning(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log warning message."""
        self._log(logging.WARNING, message, context)

    def error(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        exc_info: bool = False
    ) -> None:
        """Log error message, optionally with exception info."""
        self._log(logging.ERROR, message, context, exc_info=exc_info)

    def critical(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        exc_info: bool = False
    ) -> None:
        """Log critical message."""
        self._log(logging.CRITICAL, message, context, exc_info=exc_info)


def setup_logging(
    log_dir: Optional[Path] = None,
    verbose: bool = False,
    console_output: bool = True
) -> None:
    """
    Initialize the Suzerain logging system.

    Call this once at application startup.

    Args:
        log_dir: Directory for log files (default: ~/.suzerain/logs)
        verbose: Enable DEBUG level logging to console
        console_output: Enable colored console output for verbose mode
    """
    SuzerainLogger.get_instance().setup(
        log_dir=log_dir,
        verbose=verbose,
        console_output=console_output
    )


def get_logger(component: str) -> ComponentLogger:
    """
    Get a logger for a component.

    Args:
        component: Component name (e.g., "parser", "executor", "main")

    Returns:
        ComponentLogger instance with convenience methods

    Example:
        log = get_logger("parser")
        log.info("Matched command", context={"phrase": "they rode on", "score": 95})
        log.debug("Fuzzy match details", context={"candidates": 10, "threshold": 70})
        log.error("Match failed", context={"input": text}, exc_info=True)
    """
    instance = SuzerainLogger.get_instance()
    raw_logger = instance.get_logger(component)
    return ComponentLogger(raw_logger, component)
