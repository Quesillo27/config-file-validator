# config-file-validator

![CI](https://github.com/Quesillo27/config-file-validator/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-yellow)
![Tests](https://img.shields.io/badge/tests-71%20pass-brightgreen)
![Version](https://img.shields.io/badge/version-1.1.0-informational)

CLI Python que valida, compara y exporta archivos `.env`, JSON y YAML contra schemas definidos. Detecta claves faltantes, tipos incorrectos, valores vacíos y patrones de expresión regular. Integrable en pipelines CI/CD.

## Instalación en 3 comandos

```bash
git clone https://github.com/Quesillo27/config-file-validator
cd config-file-validator
bash setup.sh
```

O instalar desde el repo directamente:

```bash
pip install -r requirements.txt && pip install -e .
```

## Comandos disponibles

| Comando | Descripción |
|---|---|
| `cfv validate <files...>` | Valida uno o más archivos de configuración |
| `cfv diff <file-a> <file-b>` | Compara dos archivos y muestra diferencias |
| `cfv keys <files...>` | Lista todas las claves de un archivo (dot-notation) |
| `cfv export <file>` | Convierte .env/JSON/YAML a JSON o YAML |
| `cfv schema-init <file>` | Genera un schema base desde un archivo existente |

---

## cfv validate

```bash
# Validar sintaxis básica (sin schema)
cfv validate .env
cfv validate config.json

# Validar contra un schema
cfv validate .env --schema schemas/env.schema.yaml
cfv validate config.json --schema schemas/app.schema.json

# Múltiples archivos a la vez
cfv validate .env.production .env.staging --schema schemas/env.schema.yaml

# Modo estricto: falla si hay advertencias
cfv validate .env --schema schemas/env.schema.yaml --strict

# Salida JSON para CI/CD
cfv validate .env --schema schemas/env.schema.yaml --json-output

# Siempre exit 0 (reporta sin bloquear el pipeline)
cfv validate .env --json-output --exit-zero
```

**Opciones de `validate`:**

| Opción | Descripción |
|---|---|
| `-s / --schema <path>` | Schema de validación (.json o .yaml) |
| `-f / --format` | Forzar formato: `env`, `json`, `yaml` |
| `-v / --verbose` | Mostrar advertencias detalladas |
| `--strict` | Fallar si hay advertencias además de errores |
| `--exit-zero` | Siempre salir con código 0 |
| `--json-output` | Salida en JSON (para CI/CD) |

### Ejemplo de salida

```
❌ .env (ENV) — inválido
   Campo         Error
   DATABASE_URL  Required key missing
   PORT          Value does not match pattern '^\d+$'   Got: 'abc'
```

---

## cfv diff

Compara dos archivos de configuración y muestra qué claves se añadieron, eliminaron o cambiaron. Ideal para detectar diferencias entre entornos (staging vs prod).

```bash
# Comparar .env de staging y producción
cfv diff .env.staging .env.production

# Incluir claves sin cambios
cfv diff .env.staging .env.production --show-unchanged

# Salida JSON para scripting
cfv diff .env.staging .env.production --json-output
```

**Salida ejemplo:**
```
Diferencias: .env.staging → .env.production

 Clave       Estado         ← staging       → production
 DB_URL      ✏️  cambiada   postgres://dev  postgres://prod
 NEW_KEY     ➕ añadida                     secret123
 DEBUG       ➖ eliminada   true

Resumen: 1 añadidas · 1 eliminadas · 1 cambiadas
```

---

## cfv keys

Lista todas las claves de un archivo en dot-notation (funciona con estructuras anidadas).

```bash
# Listar claves de un YAML anidado
cfv keys config.yaml

# Solo contar
cfv keys .env --count

# Comparar claves entre dos archivos
cfv keys .env.staging .env.production

# Salida JSON
cfv keys config.yaml --json-output
```

**Salida ejemplo (YAML anidado):**
```
  server.host
  server.port
  database.url
  database.pool_size
  features[0]
  features[1]

5 claves en total
```

---

## cfv export

Convierte cualquier formato soportado a JSON o YAML (útil para normalizar y comparar).

```bash
# .env a JSON
cfv export .env --output-format json

# YAML a JSON con indentación 4
cfv export config.yaml --output-format json --indent 4

# JSON a YAML
cfv export config.json --output-format yaml
```

---

## cfv schema-init

Genera un schema base a partir de un archivo de configuración existente.

```bash
# Desde .env (genera reglas env-specific)
cfv schema-init .env -o schemas/env.schema.yaml

# Desde JSON/YAML (genera JSON Schema draft-7)
cfv schema-init config.json -o schemas/app.schema.json

# Previsualizar sin escribir archivo
cfv schema-init config.yaml --dry-run
```

---

## Schemas para .env

```yaml
# schemas/env.schema.yaml
required:
  - DATABASE_URL
  - JWT_SECRET
  - PORT

no_empty_values: true

forbidden:
  - AWS_ROOT_ACCESS_KEY

patterns:
  PORT: '^\d+$'
  NODE_ENV: '^(development|production|test)$'

# Advertencia si hay claves no declaradas:
allowed_keys:
  - DATABASE_URL
  - JWT_SECRET
  - PORT
  - NODE_ENV
```

Notas del schema `.env`:
- La raiz debe ser un objeto YAML/JSON.
- `required`, `forbidden` y `allowed_keys` deben ser listas de strings.
- `patterns` debe mapear claves a regex validas; una regex invalida ahora se reporta como error de validacion en lugar de provocar un traceback.

## Schemas para JSON/YAML

Usa [JSON Schema draft-7](https://json-schema.org/):

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["name", "version", "port"],
  "properties": {
    "name":    { "type": "string" },
    "version": { "type": "integer", "minimum": 1 },
    "port":    { "type": "integer", "minimum": 1024, "maximum": 65535 }
  }
}
```

---

## Variables de entorno del CLI

| Variable | Descripción | Default |
|---|---|---|
| `CFV_LOG_LEVEL` | Nivel de logging interno (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `WARNING` |

---

## Integración CI/CD

```yaml
# .github/workflows/validate-config.yml
- name: Validar configuración
  run: |
    pip install -r requirements.txt && pip install -e .
    cfv validate .env.example --schema schemas/env.schema.yaml --strict

# Comparar staging vs producción (falla si difieren en claves)
- name: Verificar paridad de claves
  run: |
    cfv diff .env.staging .env.production --json-output | \
      python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(1 if d['summary']['added'] or d['summary']['removed'] else 0)"
```

---

## Docker

```bash
# Build
docker build -t cfv .

# Validar un archivo local
docker run --rm -v $(pwd):/data cfv validate /data/.env --schema /data/schemas/env.schema.yaml
```

---

## Desarrollo

```bash
make dev      # instala dependencias + paquete en modo editable
make test     # corre los 71 tests
make lint     # verifica sintaxis
make docker   # build de la imagen Docker
make clean    # limpia cachés
```

---

## Roadmap

- Soporte TOML (Python 3.11+ `tomllib`)
- Validación de archivos `.ini` y `.cfg`
- Comando `cfv watch <file>` — re-validar en cambios (modo desarrollo)
- Integración con Vault / AWS Secrets Manager para validar contra valores reales
- Plugin pre-commit (`cfv validate` como hook automático)
