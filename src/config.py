"""Centralized configuration and constants."""

VERSION = "1.1.0"

SUPPORTED_FORMATS = ("env", "json", "yaml")

ENV_EXTENSION_MAP = {
    ".env": "env",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
}

SECRET_KEY_HINTS = ("SECRET", "PASSWORD", "TOKEN", "KEY", "PWD", "PASS")

SCHEMA_EXTENSIONS = (".json", ".yaml", ".yml")

MAX_BATCH_SIZE = 50

DIFF_ADDED = "added"
DIFF_REMOVED = "removed"
DIFF_CHANGED = "changed"
DIFF_UNCHANGED = "unchanged"
