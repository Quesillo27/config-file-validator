# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Fixed
- La validacion de schemas `.env` ahora detecta estructuras invalidas (`allowed_keys`, `required`, `forbidden`, `patterns`, `no_empty_values`) y regex mal formadas sin provocar excepciones internas.

## [1.1.0] — 2026-04-19

### Added
- **`cfv diff`** — compara dos archivos de configuración y muestra claves añadidas, eliminadas y modificadas; soporta `--show-unchanged`, `--json-output` y formatos forzados
- **`cfv keys`** — lista todas las claves de uno o más archivos con aplanamiento dot-notation para estructuras anidadas; soporta `--count` y `--json-output`
- **`cfv export`** — exporta cualquier formato soportado a JSON o YAML; útil para conversiones y scripting
- **`--strict`** en `validate` — falla si hay advertencias además de errores (ideal para CI estricto)
- **`--dry-run`** en `schema-init` — muestra el schema generado sin escribir archivo
- **`--exit-zero`** en `validate` — siempre retorna código 0 (para pipelines que quieren reportar sin bloquear)
- Regla `allowed_keys` en schemas .env — genera advertencias para claves no declaradas
- Módulo `src/config.py` — centraliza constantes y configuración
- Módulo `src/logger.py` — logging estructurado con nivel configurable via `CFV_LOG_LEVEL`
- Módulo `src/diffing.py` — lógica de comparación desacoplada del CLI
- `flatten_keys()` en `parsers.py` — extrae claves en dot-notation de estructuras anidadas
- `to_dict()` en `ValidationResult` — serialización uniforme para salida JSON
- `strict_valid()` en `ValidationResult` — consulta modo estricto sin pasar flag
- Dockerfile multi-stage (builder + runtime mínimo)
- CI con GitHub Actions (Python 3.10, 3.11, 3.12)
- `setup.sh` — instalación en 1 comando
- `examples/` — schemas de ejemplo y scripts de uso
- `ARCHITECTURE.md` — decisiones de diseño y trade-offs
- `LICENSE` MIT

### Changed
- `src/parsers.py` usa `config.py` para el mapa de extensiones
- `src/validators.py` usa `SECRET_KEY_HINTS` desde `config.py`; agrega logs estructurados
- `cli.py` versión bumpeada a `1.1.0`
- `requirements.txt` sin cambios de dependencias de producción; `pytest` documentado en `requirements-dev.txt`
- Makefile expandido con targets `docker`, `setup`, `clean`

### Fixed
- Manejo de `None` en valores de env al aplicar patrones (convertía a string antes de `re.match`)

## [1.0.0] — 2026-04-11

### Added
- Validación de archivos `.env`, JSON y YAML
- JSON Schema draft-7 para JSON/YAML
- Reglas propias para `.env`: `required`, `forbidden`, `patterns`, `no_empty_values`
- Advertencias de secrets con valor vacío
- Comando `cfv validate` con `--schema`, `--format`, `--verbose`, `--json-output`
- Comando `cfv schema-init` — genera schema desde archivo existente
- 27 tests (100% pass)
