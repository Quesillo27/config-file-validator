"""Parsers for .env, JSON, and YAML files."""

import json
import os
from pathlib import Path

import yaml
from dotenv import dotenv_values

from .config import ENV_EXTENSION_MAP, SUPPORTED_FORMATS
from .logger import log


class ParseError(Exception):
    """Raised when a file cannot be parsed."""


def parse_env(path: Path) -> dict:
    """Parse a .env file and return a dict of key→value strings."""
    try:
        values = dotenv_values(path)
        log.debug("Parsed env file: %s (%d keys)", path, len(values))
        return dict(values)
    except Exception as e:
        raise ParseError(f"Cannot parse .env file: {e}") from e


def parse_json(path: Path) -> dict | list:
    """Parse a JSON file and return the decoded object."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        log.debug("Parsed JSON file: %s", path)
        return data
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON at line {e.lineno}: {e.msg}") from e
    except OSError as e:
        raise ParseError(f"Cannot read file: {e}") from e


def parse_yaml(path: Path) -> dict | list:
    """Parse a YAML file and return the decoded object."""
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        log.debug("Parsed YAML file: %s", path)
        return data
    except yaml.YAMLError as e:
        raise ParseError(f"Invalid YAML: {e}") from e
    except OSError as e:
        raise ParseError(f"Cannot read file: {e}") from e


def detect_format(path: Path) -> str:
    """Auto-detect file format from extension."""
    suffix = path.suffix.lower()
    name = path.name.lower()

    if suffix in (".env",) or name.startswith(".env"):
        return "env"
    if suffix in ENV_EXTENSION_MAP:
        return ENV_EXTENSION_MAP[suffix]
    raise ParseError(
        f"Cannot detect format for '{path.name}'. "
        "Use --format to specify: env, json, yaml"
    )


def parse_file(path: Path, fmt: str | None = None) -> tuple[dict | list, str]:
    """Parse a config file, auto-detecting format if not given.

    Returns (data, detected_format).
    """
    path = Path(path)
    if not path.exists():
        raise ParseError(f"File not found: {path}")

    fmt = fmt or detect_format(path)

    if fmt not in SUPPORTED_FORMATS:
        raise ParseError(f"Unknown format: {fmt}. Valid: {', '.join(SUPPORTED_FORMATS)}")

    if fmt == "env":
        return parse_env(path), "env"
    if fmt == "json":
        return parse_json(path), "json"
    return parse_yaml(path), "yaml"


def flatten_keys(data: dict | list, prefix: str = "") -> list[str]:
    """Recursively extract all dot-notation keys from a nested dict/list."""
    keys = []
    if isinstance(data, dict):
        for k, v in data.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                keys.extend(flatten_keys(v, full_key))
            else:
                keys.append(full_key)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            full_key = f"{prefix}[{i}]"
            if isinstance(v, (dict, list)):
                keys.extend(flatten_keys(v, full_key))
            else:
                keys.append(full_key)
    return keys
