"""
Suzerain Configuration Management.

Loads settings from (in priority order):
1. ~/.suzerain/config.yaml (user config)
2. Environment variables (fallback)
3. Sensible defaults

"Whatever exists without my knowledge exists without my consent."
"""

import os
import stat
import warnings
from pathlib import Path
from typing import Any, Optional

import yaml


# === Configuration Paths ===

CONFIG_DIR = Path.home() / ".suzerain"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


# === Default Configuration ===

DEFAULT_CONFIG = {
    "deepgram": {
        "api_key": None,
    },
    "picovoice": {
        "access_key": None,
    },
    "grimoire": {
        "file": "vanilla.yaml",  # Default to simple mode
    },
    "parser": {
        "threshold": 80,
        "scorer": "ratio",
    },
    "audio": {
        "sample_rate": 16000,
        "channels": 1,
    },
    "claude": {
        "timeout": 120,
    },
}

# Template for --init-config (with placeholders and comments)
CONFIG_TEMPLATE = """\
# Suzerain Configuration
# "Whatever exists without my knowledge exists without my consent."
#
# This file configures the Suzerain voice-activated Claude Code interface.
# API keys can also be set via environment variables (DEEPGRAM_API_KEY, PICOVOICE_ACCESS_KEY).

deepgram:
  # Required for voice mode - get a free key at https://console.deepgram.com/
  api_key: ""

picovoice:
  # Optional - for wake word detection. Get free key at https://console.picovoice.ai/
  access_key: ""

grimoire:
  # Which grimoire to use: vanilla.yaml (simple), commands.yaml (Blood Meridian), or dune.yaml
  file: vanilla.yaml

parser:
  # Fuzzy match threshold (0-100). Higher = stricter matching.
  threshold: 80
  # Scoring algorithm: ratio, partial_ratio, token_sort_ratio, token_set_ratio
  scorer: ratio

audio:
  # Audio capture settings
  sample_rate: 16000
  channels: 1

claude:
  # Timeout in seconds for Claude Code execution
  timeout: 120
"""


# === Security ===

class ConfigSecurityWarning(UserWarning):
    """Warning for insecure configuration file permissions."""
    pass


def check_file_permissions(path: Path) -> list[str]:
    """
    Check if config file has secure permissions.

    Args:
        path: Path to config file

    Returns:
        List of security warnings (empty if secure)
    """
    warnings_list = []

    if not path.exists():
        return warnings_list

    try:
        file_stat = path.stat()
        mode = file_stat.st_mode

        # Check if world-readable (others can read)
        if mode & stat.S_IROTH:
            warnings_list.append(
                f"Config file {path} is world-readable. "
                f"Run: chmod 600 {path}"
            )

        # Check if group-readable (group can read)
        if mode & stat.S_IRGRP:
            warnings_list.append(
                f"Config file {path} is group-readable. "
                f"Consider: chmod 600 {path}"
            )

        # Check if world-writable
        if mode & stat.S_IWOTH:
            warnings_list.append(
                f"Config file {path} is world-writable! "
                f"CRITICAL: Run: chmod 600 {path}"
            )

    except OSError:
        # Can't stat the file, don't warn
        pass

    return warnings_list


def secure_file(path: Path) -> None:
    """
    Set secure permissions on config file (owner read/write only).

    Args:
        path: Path to config file
    """
    if path.exists():
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600


# === Configuration Class ===

class Config:
    """
    Suzerain configuration manager.

    Priority order:
    1. Config file (~/.suzerain/config.yaml)
    2. Environment variables
    3. Default values

    Usage:
        config = Config()
        api_key = config.get("deepgram", "api_key")

        # Or use require() for operations that need the key:
        api_key = config.require("deepgram", "api_key")  # Raises if missing
    """

    # Environment variable mappings
    ENV_MAPPINGS = {
        ("deepgram", "api_key"): "DEEPGRAM_API_KEY",
        ("picovoice", "access_key"): "PICOVOICE_ACCESS_KEY",
    }

    def __init__(self, config_path: Optional[Path] = None, warn_permissions: bool = True):
        """
        Initialize configuration.

        Args:
            config_path: Override config file path (for testing)
            warn_permissions: If True, warn about insecure file permissions
        """
        self.config_path = config_path or CONFIG_FILE
        self._config = self._deep_copy(DEFAULT_CONFIG)
        self._loaded_from_file = False

        # Load config file if it exists
        self._load_config_file()

        # Check permissions and warn
        if warn_permissions:
            self._check_permissions()

    def _deep_copy(self, d: dict) -> dict:
        """Deep copy a nested dict."""
        result = {}
        for key, value in d.items():
            if isinstance(value, dict):
                result[key] = self._deep_copy(value)
            else:
                result[key] = value
        return result

    def _load_config_file(self) -> None:
        """Load configuration from YAML file if it exists."""
        if not self.config_path.exists():
            return

        try:
            with open(self.config_path, "r") as f:
                file_config = yaml.safe_load(f)

            if file_config:
                self._merge_config(file_config)
                self._loaded_from_file = True

        except yaml.YAMLError as e:
            warnings.warn(f"Error parsing config file {self.config_path}: {e}")
        except IOError as e:
            warnings.warn(f"Could not read config file {self.config_path}: {e}")

    def _merge_config(self, file_config: dict) -> None:
        """
        Merge file config into internal config.

        Only merges keys that exist in DEFAULT_CONFIG to prevent
        arbitrary key injection.
        """
        for section, values in file_config.items():
            if section in self._config and isinstance(values, dict):
                for key, value in values.items():
                    if key in self._config[section]:
                        # Don't overwrite with empty strings from template
                        if value != "" and value is not None:
                            self._config[section][key] = value
                        elif value == "":
                            # Keep as None if template placeholder
                            pass

    def _check_permissions(self) -> None:
        """Check file permissions and emit warnings."""
        warnings_list = check_file_permissions(self.config_path)
        for warning in warnings_list:
            warnings.warn(warning, ConfigSecurityWarning)

    def _get_env_value(self, section: str, key: str) -> Optional[str]:
        """Get value from environment variable if mapped."""
        env_key = self.ENV_MAPPINGS.get((section, key))
        if env_key:
            return os.environ.get(env_key)
        return None

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Priority: config file > environment variable > default

        Args:
            section: Config section (e.g., "deepgram")
            key: Config key (e.g., "api_key")
            default: Default value if not found anywhere

        Returns:
            Configuration value or default
        """
        # First check config file value
        if section in self._config and key in self._config[section]:
            value = self._config[section][key]
            if value is not None:
                return value

        # Then check environment variable
        env_value = self._get_env_value(section, key)
        if env_value:
            return env_value

        # Fall back to default parameter, then DEFAULT_CONFIG
        if default is not None:
            return default

        if section in DEFAULT_CONFIG and key in DEFAULT_CONFIG[section]:
            return DEFAULT_CONFIG[section][key]

        return None

    def require(self, section: str, key: str, operation: str = "this operation") -> Any:
        """
        Get a configuration value, raising an error if not set.

        Use this for operations that absolutely require a config value.

        Args:
            section: Config section
            key: Config key
            operation: Description of operation requiring this value (for error message)

        Returns:
            Configuration value

        Raises:
            ConfigurationError: If value is not set
        """
        value = self.get(section, key)

        if value is None:
            env_key = self.ENV_MAPPINGS.get((section, key), f"{section.upper()}_{key.upper()}")
            raise ConfigurationError(
                f"{section}.{key} is required for {operation}. "
                f"Set it in {self.config_path} or via {env_key} environment variable. "
                f"Run 'python src/main.py --init-config' to create a config template."
            )

        return value

    def set(self, section: str, key: str, value: Any) -> None:
        """
        Set a configuration value in memory.

        Note: Does not persist to disk. Call save() to persist.

        Args:
            section: Config section
            key: Config key
            value: Value to set
        """
        if section not in self._config:
            self._config[section] = {}
        self._config[section][key] = value

    def save(self) -> None:
        """
        Save current configuration to file.

        Creates the config directory if it doesn't exist.
        Sets secure file permissions (0600).
        """
        # Ensure directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.config_path, "w") as f:
            yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)

        # Set secure permissions
        secure_file(self.config_path)

    def validate(self) -> list[str]:
        """
        Validate current configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Validate Deepgram API key format if set
        api_key = self.get("deepgram", "api_key")
        if api_key:
            if len(api_key) < 32:
                errors.append(f"deepgram.api_key appears invalid (too short: {len(api_key)} chars)")
            elif not api_key.replace("-", "").replace("_", "").isalnum():
                errors.append("deepgram.api_key contains invalid characters")

        # Validate Picovoice access key format if set
        access_key = self.get("picovoice", "access_key")
        if access_key:
            if len(access_key) < 20:
                errors.append(f"picovoice.access_key appears invalid (too short: {len(access_key)} chars)")

        # Validate parser threshold
        threshold = self.get("parser", "threshold")
        if threshold is not None:
            if not isinstance(threshold, int) or threshold < 0 or threshold > 100:
                errors.append(f"parser.threshold must be an integer between 0 and 100 (got: {threshold})")

        # Validate parser scorer
        valid_scorers = ("ratio", "partial_ratio", "token_sort_ratio", "token_set_ratio")
        scorer = self.get("parser", "scorer")
        if scorer and scorer not in valid_scorers:
            errors.append(f"parser.scorer must be one of {valid_scorers} (got: {scorer})")

        # Validate audio settings
        sample_rate = self.get("audio", "sample_rate")
        if sample_rate is not None:
            if not isinstance(sample_rate, int) or sample_rate <= 0:
                errors.append(f"audio.sample_rate must be a positive integer (got: {sample_rate})")

        channels = self.get("audio", "channels")
        if channels is not None:
            if channels not in (1, 2):
                errors.append(f"audio.channels must be 1 or 2 (got: {channels})")

        # Validate Claude timeout
        timeout = self.get("claude", "timeout")
        if timeout is not None:
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                errors.append(f"claude.timeout must be a positive number (got: {timeout})")

        return errors

    @property
    def loaded_from_file(self) -> bool:
        """Whether config was loaded from a file."""
        return self._loaded_from_file

    @property
    def config_exists(self) -> bool:
        """Whether config file exists."""
        return self.config_path.exists()

    # === Convenience Properties ===

    @property
    def deepgram_api_key(self) -> Optional[str]:
        """Get Deepgram API key."""
        return self.get("deepgram", "api_key")

    @property
    def picovoice_access_key(self) -> Optional[str]:
        """Get Picovoice access key."""
        return self.get("picovoice", "access_key")

    @property
    def parser_threshold(self) -> int:
        """Get parser threshold."""
        return self.get("parser", "threshold")

    @property
    def parser_scorer(self) -> str:
        """Get parser scorer."""
        return self.get("parser", "scorer")

    @property
    def audio_sample_rate(self) -> int:
        """Get audio sample rate."""
        return self.get("audio", "sample_rate")

    @property
    def audio_channels(self) -> int:
        """Get audio channels."""
        return self.get("audio", "channels")

    @property
    def claude_timeout(self) -> int:
        """Get Claude timeout."""
        return self.get("claude", "timeout")

    @property
    def grimoire_file(self) -> str:
        """Get selected grimoire file."""
        return self.get("grimoire", "file")

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"Config(path={self.config_path}, "
            f"exists={self.config_exists}, "
            f"deepgram={'set' if self.deepgram_api_key else 'unset'}, "
            f"picovoice={'set' if self.picovoice_access_key else 'unset'})"
        )


# === Exceptions ===

class ConfigurationError(Exception):
    """Raised when a required configuration value is missing."""
    pass


# === Module-level Interface ===

# Global config instance (lazy-loaded)
_global_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get the global configuration instance.

    Returns:
        Config instance (creates one if needed)
    """
    global _global_config
    if _global_config is None:
        _global_config = Config()
    return _global_config


def reload_config() -> Config:
    """
    Reload configuration from disk.

    Returns:
        Fresh Config instance
    """
    global _global_config
    _global_config = Config()
    return _global_config


def init_config(force: bool = False) -> tuple[bool, str]:
    """
    Initialize config file with template.

    Args:
        force: If True, overwrite existing config

    Returns:
        Tuple of (success, message)
    """
    if CONFIG_FILE.exists() and not force:
        return False, f"Config file already exists at {CONFIG_FILE}. Use --force to overwrite."

    # Ensure directory exists
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Write template
    with open(CONFIG_FILE, "w") as f:
        f.write(CONFIG_TEMPLATE)

    # Set secure permissions
    secure_file(CONFIG_FILE)

    return True, f"Config template created at {CONFIG_FILE}"


# === CLI Entry Point ===

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "--init":
            force = "--force" in sys.argv
            success, message = init_config(force=force)
            print(message)
            sys.exit(0 if success else 1)
        elif sys.argv[1] == "--validate":
            config = Config()
            errors = config.validate()
            if errors:
                print("Configuration errors:")
                for error in errors:
                    print(f"  - {error}")
                sys.exit(1)
            else:
                print("Configuration valid.")
                sys.exit(0)
        elif sys.argv[1] == "--status":
            config = Config()
            print(f"Config file: {config.config_path}")
            print(f"  Exists: {config.config_exists}")
            print(f"  Loaded from file: {config.loaded_from_file}")
            print("\nSettings:")
            print(f"  deepgram.api_key: {'set' if config.deepgram_api_key else 'not set'}")
            print(f"  picovoice.access_key: {'set' if config.picovoice_access_key else 'not set'}")
            print(f"  parser.threshold: {config.parser_threshold}")
            print(f"  parser.scorer: {config.parser_scorer}")
            print(f"  audio.sample_rate: {config.audio_sample_rate}")
            print(f"  audio.channels: {config.audio_channels}")
            print(f"  claude.timeout: {config.claude_timeout}")
            sys.exit(0)

    print("Usage: python src/config.py [--init [--force] | --validate | --status]")
    sys.exit(1)
