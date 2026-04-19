"""Validation logic for config files."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from .config import SECRET_KEY_HINTS
from .logger import log
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

    def strict_valid(self) -> bool:
        """Returns False if there are errors OR warnings (strict mode)."""
        return self.valid and len(self.warnings) == 0

    def add_error(self, message: str, field: str = "", detail: str = ""):
        self.errors.append({"field": field, "message": message, "detail": detail})
        log.debug("Validation error — field=%s: %s", field or "(root)", message)

    def add_warning(self, message: str, field: str = ""):
        self.warnings.append({"field": field, "message": message})
        log.debug("Validation warning — field=%s: %s", field or "(root)", message)

    def to_dict(self) -> dict:
        return {
            "file": self.path,
            "format": self.fmt,
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ── Built-in rules for .env files ────────────────────────────────────────────

def _validate_env_rules(data: dict, result: ValidationResult, rules: dict):
    """Apply built-in + schema-defined rules to an env dict."""
    required = rules.get("required", [])
    forbidden = rules.get("forbidden", [])
    patterns = rules.get("patterns", {})
    no_empty = rules.get("no_empty_values", False)
    allowed_keys = rules.get("allowed_keys", None)

    for key in required:
        if key not in data:
            result.add_error("Required key missing", field=key)
        elif no_empty and not str(data.get(key, "")).strip():
            result.add_error("Required key is empty", field=key)

    for key in forbidden:
        if key in data:
            result.add_error(
                "Forbidden key present (should not be set here)", field=key
            )

    if allowed_keys is not None:
        for key in data:
            if key not in allowed_keys:
                result.add_warning(f"Unexpected key (not in allowed_keys)", field=key)

    for key, pattern in patterns.items():
        if key in data:
            val = str(data[key]) if data[key] is not None else ""
            if not re.match(pattern, val):
                result.add_error(
                    f"Value does not match pattern '{pattern}'",
                    field=key,
                    detail=f"Got: {val!r}",
                )

    for key, val in data.items():
        val_str = str(val) if val is not None else ""
        if any(hint in key.upper() for hint in SECRET_KEY_HINTS) and not val_str.strip():
            result.add_warning("Secret-looking key has empty value", field=key)


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
                     For .env files: YAML/JSON with env-specific rules.
                     For JSON/YAML files: JSON Schema draft-7 document.
        fmt: Force file format ('env', 'json', 'yaml').

    Returns:
        ValidationResult with all errors and warnings.
    """
    config_path = Path(config_path)
    result = ValidationResult(str(config_path), fmt or "")
    log.info("Validating: %s", config_path)

    try:
        data, detected_fmt = parse_file(config_path, fmt)
        result.fmt = detected_fmt
        result.parsed_ok = True
    except ParseError as e:
        result.add_error(str(e))
        return result

    if schema_path:
        try:
            schema = load_schema(Path(schema_path))
        except ParseError as e:
            result.add_error(f"Schema load error: {e}")
            return result

        if result.fmt == "env":
            _validate_env_rules(data, result, schema)
        else:
            _validate_jsonschema(data, schema, result)
    else:
        if result.fmt == "env":
            _validate_env_rules(data, result, {})

    log.info(
        "Validation complete: %s — %s (%d errors, %d warnings)",
        config_path,
        "valid" if result.valid else "invalid",
        len(result.errors),
        len(result.warnings),
    )
    return result
