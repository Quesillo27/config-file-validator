"""Tests for config-file-validator."""

import json
import tempfile
import textwrap
from pathlib import Path

import pytest

from src.validators import validate
from src.parsers import ParseError, parse_env, parse_json, parse_yaml, detect_format


# ── Helpers ───────────────────────────────────────────────────────────────────

def write_tmp(suffix: str, content: str) -> Path:
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    )
    f.write(textwrap.dedent(content))
    f.close()
    return Path(f.name)


# ── Parser tests ──────────────────────────────────────────────────────────────

class TestParsers:
    def test_parse_env_basic(self):
        p = write_tmp(".env", "DB_URL=postgres://localhost/db\nPORT=5432\n")
        data = parse_env(p)
        assert data["DB_URL"] == "postgres://localhost/db"
        assert data["PORT"] == "5432"

    def test_parse_json_valid(self):
        p = write_tmp(".json", '{"name": "test", "version": 1}')
        data = parse_json(p)
        assert data["name"] == "test"
        assert data["version"] == 1

    def test_parse_json_invalid(self):
        p = write_tmp(".json", '{invalid json}')
        with pytest.raises(ParseError, match="Invalid JSON"):
            parse_json(p)

    def test_parse_yaml_valid(self):
        p = write_tmp(".yaml", "name: test\nversion: 1\n")
        data = parse_yaml(p)
        assert data["name"] == "test"

    def test_parse_yaml_invalid(self):
        p = write_tmp(".yaml", "key: [\nbroken")
        with pytest.raises(ParseError, match="Invalid YAML"):
            parse_yaml(p)

    def test_detect_format_env(self):
        p = Path("/tmp/.env.production")
        assert detect_format(p) == "env"

    def test_detect_format_json(self):
        assert detect_format(Path("config.json")) == "json"

    def test_detect_format_yaml(self):
        assert detect_format(Path("config.yaml")) == "yaml"
        assert detect_format(Path("config.yml")) == "yaml"

    def test_detect_format_unknown(self):
        with pytest.raises(ParseError, match="Cannot detect format"):
            detect_format(Path("config.toml"))


# ── .env validation ───────────────────────────────────────────────────────────

class TestEnvValidation:
    def test_valid_env_no_schema(self):
        p = write_tmp(".env", "PORT=3000\nNAME=myapp\n")
        result = validate(p)
        assert result.valid
        assert result.fmt == "env"

    def test_required_keys_present(self):
        p = write_tmp(".env", "DATABASE_URL=postgres://x\nJWT_SECRET=abc\n")
        schema_p = write_tmp(".yaml", "required: [DATABASE_URL, JWT_SECRET]\n")
        result = validate(p, schema_path=schema_p)
        assert result.valid

    def test_required_key_missing(self):
        p = write_tmp(".env", "PORT=3000\n")
        schema_p = write_tmp(".yaml", "required: [DATABASE_URL]\n")
        result = validate(p, schema_path=schema_p)
        assert not result.valid
        assert any(e["field"] == "DATABASE_URL" for e in result.errors)

    def test_forbidden_key_detected(self):
        p = write_tmp(".env", "PORT=3000\nAWS_SECRET=shh\n")
        schema_p = write_tmp(".yaml", "forbidden: [AWS_SECRET]\n")
        result = validate(p, schema_path=schema_p)
        assert not result.valid
        assert any(e["field"] == "AWS_SECRET" for e in result.errors)

    def test_pattern_validation(self):
        p = write_tmp(".env", "PORT=abc\n")
        schema_p = write_tmp(".yaml", "patterns:\n  PORT: '^\\d+$'\n")
        result = validate(p, schema_path=schema_p)
        assert not result.valid
        assert any(e["field"] == "PORT" for e in result.errors)

    def test_pattern_valid(self):
        p = write_tmp(".env", "PORT=3000\n")
        schema_p = write_tmp(".yaml", "patterns:\n  PORT: '^\\d+$'\n")
        result = validate(p, schema_path=schema_p)
        assert result.valid

    def test_empty_secret_warning(self):
        p = write_tmp(".env", "JWT_SECRET=\n")
        result = validate(p)
        assert result.valid  # warning, not error
        assert any("SECRET" in w["field"] or "secret" in w["message"].lower()
                   for w in result.warnings)

    def test_no_empty_values_rule(self):
        p = write_tmp(".env", "DATABASE_URL=\n")
        schema_p = write_tmp(".yaml", "required: [DATABASE_URL]\nno_empty_values: true\n")
        result = validate(p, schema_path=schema_p)
        assert not result.valid


# ── JSON validation ───────────────────────────────────────────────────────────

class TestJsonValidation:
    def test_valid_json_no_schema(self):
        p = write_tmp(".json", '{"name": "test"}')
        result = validate(p)
        assert result.valid
        assert result.fmt == "json"

    def test_json_schema_valid(self):
        p = write_tmp(".json", '{"name": "test", "version": 1}')
        schema_content = json.dumps({
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["name", "version"],
            "properties": {
                "name": {"type": "string"},
                "version": {"type": "integer"}
            }
        })
        schema_p = write_tmp(".json", schema_content)
        result = validate(p, schema_path=schema_p)
        assert result.valid

    def test_json_schema_missing_field(self):
        p = write_tmp(".json", '{"name": "test"}')
        schema_content = json.dumps({
            "type": "object",
            "required": ["name", "version"],
            "properties": {"name": {"type": "string"}, "version": {"type": "integer"}}
        })
        schema_p = write_tmp(".json", schema_content)
        result = validate(p, schema_path=schema_p)
        assert not result.valid

    def test_json_schema_wrong_type(self):
        p = write_tmp(".json", '{"version": "not-an-int"}')
        schema_content = json.dumps({
            "type": "object",
            "properties": {"version": {"type": "integer"}}
        })
        schema_p = write_tmp(".json", schema_content)
        result = validate(p, schema_path=schema_p)
        assert not result.valid
        assert any(e["field"] == "version" for e in result.errors)


# ── YAML validation ───────────────────────────────────────────────────────────

class TestYamlValidation:
    def test_valid_yaml_no_schema(self):
        p = write_tmp(".yaml", "name: test\nversion: 1\n")
        result = validate(p)
        assert result.valid
        assert result.fmt == "yaml"

    def test_yaml_with_json_schema(self):
        p = write_tmp(".yaml", "name: test\nport: 3000\n")
        schema_content = json.dumps({
            "type": "object",
            "required": ["name", "port"],
            "properties": {
                "name": {"type": "string"},
                "port": {"type": "integer"}
            }
        })
        schema_p = write_tmp(".json", schema_content)
        result = validate(p, schema_path=schema_p)
        assert result.valid

    def test_yaml_schema_violation(self):
        p = write_tmp(".yaml", "name: 123\n")  # name should be string
        schema_content = json.dumps({
            "type": "object",
            "properties": {"name": {"type": "string"}}
        })
        schema_p = write_tmp(".json", schema_content)
        result = validate(p, schema_path=schema_p)
        assert not result.valid


# ── Force format ──────────────────────────────────────────────────────────────

class TestForceFormat:
    def test_force_env_format(self):
        # File has no extension but content is env-like
        p = write_tmp(".txt", "PORT=3000\nNAME=test\n")
        result = validate(p, fmt="env")
        assert result.valid
        assert result.fmt == "env"


# ── File not found ────────────────────────────────────────────────────────────

class TestErrors:
    def test_missing_file(self):
        result = validate("/nonexistent/path/config.env")
        assert not result.valid
        assert any("not found" in e["message"] for e in result.errors)

    def test_invalid_json_content(self):
        p = write_tmp(".json", "{broken json}")
        result = validate(p)
        assert not result.valid
        assert any("Invalid JSON" in e["message"] for e in result.errors)
