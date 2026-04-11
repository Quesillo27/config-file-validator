"""Validation logic for config files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from .parsers import ParseError, parse_file


class ValidationResult:
    """Holds the outcome of a validation run."""

    def __init__(self, path: str, fmt: str):
        self.path = path
        self.fmt = fmt
        self.errors: list[dict] = []
        self.warnings: list[dict] = []
        self.parsed_ok = False

    @property
    def valid(self) -> bool:
        return self.parsed_ok and len(self.errors) == 0

    def add_error(self, message: str, field: str = "", detail: str = ""):
        self.errors.append({"field": field, "message": message, "detail": detail})

    def add_warning(self, message: str, field: str = ""):
        self.warnings.append({"field": field, "message": message})


# ── Built-in rules for .env files ────────────────────────────────────────────

def _validate_env_rules(data: dict, result: ValidationResult, rules: dict):
    """Apply built-in + schema-defined rules to an env dict."""
    required = rules.get("required", [])
    forbidden = rules.get("forbidden", [])
    patterns = rules.get("patterns", {})  # key → regex
    no_empty = rules.get("no_empty_values", False)

    import re

    for key in required:
        if key not in data:
            result.add_error(f"Required key missing", field=key)
        elif no_empty and not data[key].strip():
            result.add_error(f"Required key is empty", field=key)

    for key in forbidden:
        if key in data:
            result.add_error(
                f"Forbidden key present (should not be set here)", field=key
            )

    for key, pattern in patterns.items():
        if key in data:
            if not re.match(pattern, data[key]):
                result.add_error(
                    f"Value does not match pattern '{pattern}'",
                    field=key,
                    detail=f"Got: {data[key]!r}",
                )

    # Warn about keys that look like secrets but have no value
    secret_hints = ("SECRET", "PASSWORD", "TOKEN", "KEY", "PWD", "PASS")
    for key, val in data.items():
        if any(hint in key.upper() for hint in secret_hints) and not val.strip():
            result.add_warning(f"Secret-looking key has empty value", field=key)


# ── JSON Schema validation ────────────────────────────────────────────────────

def _validate_jsonschema(data: Any, schema: dict, result: ValidationResult):
    """Validate data against a JSON Schema and collect all errors."""
    validator = jsonschema.Draft7Validator(schema)
    for error in sorted(validator.iter_errors(data), key=str):
        field = ".".join(str(p) for p in error.absolute_path) or "(root)"
        result.add_error(error.message, field=field)


# ── Schema file loader ────────────────────────────────────────────────────────

def load_schema(schema_path: Path) -> dict:
    """Load a validation schema (JSON or YAML)."""
    schema_path = Path(schema_path)
    if not schema_path.exists():
        raise ParseError(f"Schema file not found: {schema_path}")

    suffix = schema_path.suffix.lower()
    with open(schema_path, encoding="utf-8") as f:
        if suffix == ".json":
            try:
                return json.load(f)
            except json.JSONDecodeError as e:
                raise ParseError(f"Invalid schema JSON: {e}") from e
        if suffix in (".yaml", ".yml"):
            try:
                return yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise ParseError(f"Invalid schema YAML: {e}") from e
    raise ParseError(f"Schema must be .json or .yaml — got: {schema_path.suffix}")


# ── Main entry point ──────────────────────────────────────────────────────────

def validate(
    config_path: str | Path,
    schema_path: str | Path | None = None,
    fmt: str | None = None,
) -> ValidationResult:
    """
    Validate a config file.

    Args:
        config_path: Path to the .env / JSON / YAML file.
        schema_path: Optional path to a validation schema.
                     For .env files: a YAML/JSON with env-specific rules.
                     For JSON/YAML files: a JSON Schema draft-7 document.
        fmt: Force file format ('env', 'json', 'yaml').

    Returns:
        ValidationResult with all errors and warnings.
    """
    config_path = Path(config_path)
    result = ValidationResult(str(config_path), fmt or "")

    # 1. Parse the config file
    try:
        data, detected_fmt = parse_file(config_path, fmt)
        result.fmt = detected_fmt
        result.parsed_ok = True
    except ParseError as e:
        result.add_error(str(e))
        return result

    # 2. If a schema is provided, validate against it
    if schema_path:
        try:
            schema = load_schema(Path(schema_path))
        except ParseError as e:
            result.add_error(f"Schema load error: {e}")
            return result

        if result.fmt == "env":
            # .env files use custom rules (not JSON Schema)
            _validate_env_rules(data, result, schema)
        else:
            # JSON / YAML use JSON Schema validation
            _validate_jsonschema(data, schema, result)
    else:
        # No schema: just check parse + secret-warning for .env
        if result.fmt == "env":
            _validate_env_rules(data, result, {})

    return result
