"""Tests for config-file-validator."""

import json
import tempfile
import textwrap
from pathlib import Path

import pytest

from src.validators import validate, ValidationResult
from src.parsers import (
    ParseError, parse_env, parse_json, parse_yaml,
    detect_format, parse_file, flatten_keys,
)
from src.diffing import diff_configs, DiffEntry, DiffResult
from src.config import DIFF_ADDED, DIFF_REMOVED, DIFF_CHANGED, DIFF_UNCHANGED


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

    def test_parse_env_with_comments(self):
        p = write_tmp(".env", "# comment\nPORT=3000\n")
        data = parse_env(p)
        assert "PORT" in data
        assert data["PORT"] == "3000"

    def test_parse_env_empty_value(self):
        p = write_tmp(".env", "EMPTY=\n")
        data = parse_env(p)
        assert data.get("EMPTY") == "" or data.get("EMPTY") is None

    def test_parse_json_valid(self):
        p = write_tmp(".json", '{"name": "test", "version": 1}')
        data = parse_json(p)
        assert data["name"] == "test"
        assert data["version"] == 1

    def test_parse_json_array(self):
        p = write_tmp(".json", '[1, 2, 3]')
        data = parse_json(p)
        assert data == [1, 2, 3]

    def test_parse_json_invalid(self):
        p = write_tmp(".json", '{invalid json}')
        with pytest.raises(ParseError, match="Invalid JSON"):
            parse_json(p)

    def test_parse_yaml_valid(self):
        p = write_tmp(".yaml", "name: test\nversion: 1\n")
        data = parse_yaml(p)
        assert data["name"] == "test"

    def test_parse_yaml_nested(self):
        p = write_tmp(".yaml", "db:\n  host: localhost\n  port: 5432\n")
        data = parse_yaml(p)
        assert data["db"]["host"] == "localhost"
        assert data["db"]["port"] == 5432

    def test_parse_yaml_invalid(self):
        p = write_tmp(".yaml", "key: [\nbroken")
        with pytest.raises(ParseError, match="Invalid YAML"):
            parse_yaml(p)

    def test_detect_format_env(self):
        p = Path("/tmp/.env.production")
        assert detect_format(p) == "env"

    def test_detect_format_env_dotenv(self):
        p = Path("/tmp/.env")
        assert detect_format(p) == "env"

    def test_detect_format_json(self):
        assert detect_format(Path("config.json")) == "json"

    def test_detect_format_yaml(self):
        assert detect_format(Path("config.yaml")) == "yaml"
        assert detect_format(Path("config.yml")) == "yaml"

    def test_detect_format_unknown(self):
        with pytest.raises(ParseError, match="Cannot detect format"):
            detect_format(Path("config.toml"))

    def test_parse_file_not_found(self):
        with pytest.raises(ParseError, match="not found"):
            parse_file(Path("/nonexistent/path/config.env"))

    def test_parse_file_unknown_format(self):
        p = write_tmp(".txt", "PORT=3000\n")
        with pytest.raises(ParseError):
            parse_file(p)

    def test_parse_file_forced_format(self):
        p = write_tmp(".txt", "PORT=3000\n")
        data, fmt = parse_file(p, fmt="env")
        assert fmt == "env"
        assert "PORT" in data


# ── flatten_keys tests ────────────────────────────────────────────────────────

class TestFlattenKeys:
    def test_flat_dict(self):
        keys = flatten_keys({"a": 1, "b": 2})
        assert sorted(keys) == ["a", "b"]

    def test_nested_dict(self):
        keys = flatten_keys({"a": {"b": {"c": 1}}})
        assert "a.b.c" in keys

    def test_list_values(self):
        keys = flatten_keys({"items": [10, 20]})
        assert "items[0]" in keys
        assert "items[1]" in keys

    def test_empty_dict(self):
        assert flatten_keys({}) == []

    def test_mixed_nesting(self):
        keys = flatten_keys({"db": {"hosts": ["h1", "h2"]}, "port": 5432})
        assert "port" in keys
        assert "db.hosts[0]" in keys
        assert "db.hosts[1]" in keys


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

    def test_multiple_required_keys_missing(self):
        p = write_tmp(".env", "PORT=3000\n")
        schema_p = write_tmp(".yaml", "required: [DATABASE_URL, JWT_SECRET, API_KEY]\n")
        result = validate(p, schema_path=schema_p)
        assert not result.valid
        assert len(result.errors) == 3

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

    def test_pattern_node_env(self):
        p = write_tmp(".env", "NODE_ENV=staging\n")
        schema_p = write_tmp(".yaml", "patterns:\n  NODE_ENV: '^(development|production|test)$'\n")
        result = validate(p, schema_path=schema_p)
        assert not result.valid

    def test_empty_secret_warning(self):
        p = write_tmp(".env", "JWT_SECRET=\n")
        result = validate(p)
        assert result.valid  # warning, not error
        assert any("secret" in w["message"].lower() for w in result.warnings)

    def test_no_empty_values_rule(self):
        p = write_tmp(".env", "DATABASE_URL=\n")
        schema_p = write_tmp(".yaml", "required: [DATABASE_URL]\nno_empty_values: true\n")
        result = validate(p, schema_path=schema_p)
        assert not result.valid

    def test_allowed_keys_warning_on_extra(self):
        p = write_tmp(".env", "PORT=3000\nUNKNOWN_KEY=val\n")
        schema_p = write_tmp(".yaml", "allowed_keys: [PORT]\n")
        result = validate(p, schema_path=schema_p)
        assert result.valid  # warnings only
        assert any(e["field"] == "UNKNOWN_KEY" for e in result.warnings)

    def test_strict_mode_fails_on_warning(self):
        p = write_tmp(".env", "JWT_SECRET=\n")
        result = validate(p)
        assert result.valid
        assert not result.strict_valid()  # has warnings

    def test_strict_mode_passes_no_warnings(self):
        p = write_tmp(".env", "PORT=3000\nNAME=app\n")
        result = validate(p)
        assert result.valid
        assert result.strict_valid()

    def test_schema_json_format(self):
        p = write_tmp(".env", "PORT=3000\n")
        schema = json.dumps({"required": ["PORT"]})
        schema_p = write_tmp(".json", schema)
        result = validate(p, schema_path=schema_p)
        assert result.valid


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

    def test_json_nested_schema_error(self):
        p = write_tmp(".json", '{"db": {"port": "not-int"}}')
        schema_content = json.dumps({
            "type": "object",
            "properties": {
                "db": {
                    "type": "object",
                    "properties": {"port": {"type": "integer"}}
                }
            }
        })
        schema_p = write_tmp(".json", schema_content)
        result = validate(p, schema_path=schema_p)
        assert not result.valid
        assert any("db.port" in e["field"] for e in result.errors)

    def test_json_minimum_constraint(self):
        p = write_tmp(".json", '{"port": 100}')
        schema_content = json.dumps({
            "type": "object",
            "properties": {"port": {"type": "integer", "minimum": 1024}}
        })
        schema_p = write_tmp(".json", schema_content)
        result = validate(p, schema_path=schema_p)
        assert not result.valid

    def test_invalid_json_file(self):
        p = write_tmp(".json", "{broken json}")
        result = validate(p)
        assert not result.valid
        assert any("Invalid JSON" in e["message"] for e in result.errors)


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
        p = write_tmp(".yaml", "name: 123\n")
        schema_content = json.dumps({
            "type": "object",
            "properties": {"name": {"type": "string"}}
        })
        schema_p = write_tmp(".json", schema_content)
        result = validate(p, schema_path=schema_p)
        assert not result.valid

    def test_yaml_schema_file(self):
        p = write_tmp(".yaml", "name: test\nversion: 2\n")
        schema_p = write_tmp(".yaml", "type: object\nrequired:\n  - name\n  - version\n")
        result = validate(p, schema_path=schema_p)
        assert result.valid

    def test_invalid_yaml_file(self):
        p = write_tmp(".yaml", "key: [\nbroken")
        result = validate(p)
        assert not result.valid
        assert any("Invalid YAML" in e["message"] for e in result.errors)


# ── Force format ──────────────────────────────────────────────────────────────

class TestForceFormat:
    def test_force_env_format(self):
        p = write_tmp(".txt", "PORT=3000\nNAME=test\n")
        result = validate(p, fmt="env")
        assert result.valid
        assert result.fmt == "env"

    def test_force_json_format(self):
        p = write_tmp(".txt", '{"key": "val"}')
        result = validate(p, fmt="json")
        assert result.valid
        assert result.fmt == "json"

    def test_force_yaml_format(self):
        p = write_tmp(".txt", "key: val\n")
        result = validate(p, fmt="yaml")
        assert result.valid
        assert result.fmt == "yaml"


# ── File not found / errors ───────────────────────────────────────────────────

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

    def test_missing_schema_file(self):
        p = write_tmp(".env", "PORT=3000\n")
        result = validate(p, schema_path="/nonexistent/schema.yaml")
        assert not result.valid
        assert any("Schema" in e["message"] for e in result.errors)

    def test_invalid_schema_json(self):
        p = write_tmp(".json", '{"key": "val"}')
        schema_p = write_tmp(".json", "{invalid json}")
        result = validate(p, schema_path=schema_p)
        assert not result.valid

    def test_invalid_schema_yaml(self):
        p = write_tmp(".json", '{"key": "val"}')
        schema_p = write_tmp(".yaml", "key: [\nbroken")
        result = validate(p, schema_path=schema_p)
        assert not result.valid

    def test_schema_wrong_extension(self):
        p = write_tmp(".json", '{"key": "val"}')
        schema_p = write_tmp(".toml", "key = 'val'")
        result = validate(p, schema_path=schema_p)
        assert not result.valid

    def test_env_schema_empty_file(self):
        p = write_tmp(".env", "PORT=3000\n")
        schema_p = write_tmp(".yaml", "")
        result = validate(p, schema_path=schema_p)
        assert not result.valid
        assert any("mapping/object" in e["message"] for e in result.errors)

    def test_env_schema_allowed_keys_must_be_list(self):
        p = write_tmp(".env", "PORT=3000\n")
        schema_p = write_tmp(".yaml", "allowed_keys: PORT\n")
        result = validate(p, schema_path=schema_p)
        assert not result.valid
        assert any(e["field"] == "allowed_keys" for e in result.errors)

    def test_env_schema_patterns_must_use_valid_regex(self):
        p = write_tmp(".env", "PORT=3000\n")
        schema_p = write_tmp(".yaml", "patterns:\n  PORT: '['\n")
        result = validate(p, schema_path=schema_p)
        assert not result.valid
        assert any(e["field"] == "PORT" and "Invalid regex pattern" in e["message"] for e in result.errors)

    def test_env_schema_no_empty_values_must_be_boolean(self):
        p = write_tmp(".env", "PORT=3000\n")
        schema_p = write_tmp(".yaml", "no_empty_values: 'yes'\n")
        result = validate(p, schema_path=schema_p)
        assert not result.valid
        assert any(e["field"] == "no_empty_values" for e in result.errors)


# ── ValidationResult ──────────────────────────────────────────────────────────

class TestValidationResult:
    def test_to_dict_structure(self):
        result = validate(write_tmp(".json", '{"k": "v"}'))
        d = result.to_dict()
        assert "file" in d
        assert "format" in d
        assert "valid" in d
        assert "errors" in d
        assert "warnings" in d

    def test_valid_no_errors(self):
        p = write_tmp(".env", "PORT=3000\n")
        result = validate(p)
        assert result.valid
        assert result.errors == []

    def test_add_error_field(self):
        from src.validators import ValidationResult
        r = ValidationResult("/tmp/test.env", "env")
        r.parsed_ok = True
        r.add_error("Missing key", field="MY_KEY", detail="Required")
        assert r.errors[0]["field"] == "MY_KEY"
        assert r.errors[0]["detail"] == "Required"

    def test_strict_valid_with_warnings(self):
        from src.validators import ValidationResult
        r = ValidationResult("/tmp/test.env", "env")
        r.parsed_ok = True
        r.add_warning("Watch out", field="TOKEN")
        assert r.valid
        assert not r.strict_valid()


# ── Diffing ───────────────────────────────────────────────────────────────────

class TestDiffing:
    def test_identical_dicts(self):
        result = diff_configs(
            {"a": 1, "b": 2}, {"a": 1, "b": 2},
            "a.json", "b.json", "json", "json"
        )
        assert not result.has_differences
        assert len(result.unchanged) == 2

    def test_added_key(self):
        result = diff_configs(
            {"a": 1}, {"a": 1, "b": 2},
            "a.json", "b.json", "json", "json"
        )
        assert result.has_differences
        assert len(result.added) == 1
        assert result.added[0].key == "b"

    def test_removed_key(self):
        result = diff_configs(
            {"a": 1, "b": 2}, {"a": 1},
            "a.json", "b.json", "json", "json"
        )
        assert result.has_differences
        assert len(result.removed) == 1
        assert result.removed[0].key == "b"

    def test_changed_value(self):
        result = diff_configs(
            {"port": 3000}, {"port": 4000},
            "a.json", "b.json", "json", "json"
        )
        assert result.has_differences
        assert len(result.changed) == 1
        assert result.changed[0].old_value == 3000
        assert result.changed[0].new_value == 4000

    def test_nested_diff(self):
        data_a = {"db": {"host": "localhost", "port": 5432}}
        data_b = {"db": {"host": "db.prod", "port": 5432}}
        result = diff_configs(data_a, data_b, "a.json", "b.json", "json", "json")
        assert result.has_differences
        changed_keys = [e.key for e in result.changed]
        assert "db.host" in changed_keys

    def test_to_dict_structure(self):
        result = diff_configs(
            {"a": 1}, {"a": 2},
            "a.json", "b.json", "json", "json"
        )
        d = result.to_dict()
        assert "file_a" in d
        assert "file_b" in d
        assert "summary" in d
        assert "entries" in d
        assert d["summary"]["changed"] == 1

    def test_env_diff(self):
        p_a = write_tmp(".env", "PORT=3000\nDB_URL=postgres://localhost\n")
        p_b = write_tmp(".env", "PORT=4000\nDB_URL=postgres://localhost\nNEW_KEY=val\n")
        from src.parsers import parse_env
        data_a = parse_env(p_a)
        data_b = parse_env(p_b)
        result = diff_configs(data_a, data_b, str(p_a), str(p_b), "env", "env")
        assert result.has_differences
        assert len(result.changed) == 1  # PORT changed
        assert len(result.added) == 1    # NEW_KEY added

    def test_diff_entry_to_dict_added(self):
        entry = DiffEntry("mykey", DIFF_ADDED, new_value="hello")
        d = entry.to_dict()
        assert d["status"] == DIFF_ADDED
        assert d["value"] == "hello"

    def test_diff_entry_to_dict_removed(self):
        entry = DiffEntry("mykey", DIFF_REMOVED, old_value="old")
        d = entry.to_dict()
        assert d["status"] == DIFF_REMOVED
        assert d["value"] == "old"

    def test_diff_entry_to_dict_changed(self):
        entry = DiffEntry("port", DIFF_CHANGED, old_value=3000, new_value=4000)
        d = entry.to_dict()
        assert d["old"] == 3000
        assert d["new"] == 4000
