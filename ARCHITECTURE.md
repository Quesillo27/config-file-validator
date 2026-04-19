# Architecture

## Structure

```
src/
├── __init__.py
├── cli.py          # Click commands (validate, diff, keys, export, schema-init)
├── config.py       # Constants and settings
├── diffing.py      # Config comparison logic (DiffResult, DiffEntry)
├── logger.py       # Structured logging (CFV_LOG_LEVEL env var)
├── parsers.py      # File parsing (.env, JSON, YAML) + format detection
└── validators.py   # Validation rules + ValidationResult
```

## Design decisions

**Why separate parsers from validators?**
Parsing is format-specific I/O work. Validation is rule-checking logic. Keeping them separate lets `diff` and `keys` commands reuse parsers without triggering validation.

**Why custom rules for .env vs JSON Schema for JSON/YAML?**
`.env` files are flat key-value pairs with no native schema format. Rather than forcing JSON Schema onto them (which requires wrapping keys in an `object` schema), we use a simpler domain-specific schema that maps to real .env concepts: `required`, `forbidden`, `patterns`, `allowed_keys`. JSON and YAML already have a rich ecosystem around JSON Schema, so we delegate to `jsonschema` for those.

**Why not use Pydantic?**
Pydantic is a runtime data validator, not a config file validator. It would require loading values into typed models, losing the ability to report field-level errors as strings with file paths and context. `jsonschema` gives us Draft-7 support with rich error messages including paths.

**Why flatten nested keys for `diff` and `keys`?**
Flat dot-notation keys (`db.host`, `items[0]`) make diffs readable regardless of nesting depth. Comparing nested structures directly would require recursive tree diffing with ambiguous merge semantics.

**Why Click + Rich?**
Click provides declarative CLI with automatic `--help` generation. Rich gives styled terminal output without coupling presentation to logic — the validator itself returns a `ValidationResult` object; the CLI decides how to render it.

**Exit codes**
- `0`: all files valid (or `--exit-zero` was passed)
- `1`: at least one file invalid, or `diff` found differences
- Follows UNIX convention — composable in shell pipelines and CI

## Data flow

```
CLI command
    └── parse_file() → (data, fmt)
            └── validate() → ValidationResult
                    ├── _validate_env_rules()     # for .env
                    └── _validate_jsonschema()    # for JSON/YAML

    └── diff_configs() → DiffResult
                ├── _flatten(data_a)
                └── _flatten(data_b)
```
