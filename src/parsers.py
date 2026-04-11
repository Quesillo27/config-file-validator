"""Parsers for .env, JSON, and YAML files."""

import json
import os
from pathlib import Path

import yaml
from dotenv import dotenv_values


class ParseError(Exception):
    """Raised when a file cannot be parsed."""


def parse_env(path: Path) -> dict:
    """Parse a .env file and return a dict of key→value strings."""
    try:
        values = dotenv_values(path)
        return dict(values)
    except Exception as e:
        raise ParseError(f"Cannot parse .env file: {e}") from e


def parse_json(path: Path) -> dict | list:
    """Parse a JSON file and return the decoded object."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON at line {e.lineno}: {e.msg}") from e
    except OSError as e:
        raise ParseError(f"Cannot read file: {e}") from e


def parse_yaml(path: Path) -> dict | list:
    """Parse a YAML file and return the decoded object."""
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
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
    if suffix == ".json":
        return "json"
    if suffix in (".yaml", ".yml"):
        return "yaml"
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

    if fmt == "env":
        return parse_env(path), "env"
    if fmt == "json":
        return parse_json(path), "json"
    if fmt == "yaml":
        return parse_yaml(path), "yaml"
    raise ParseError(f"Unknown format: {fmt}. Valid: env, json, yaml")
