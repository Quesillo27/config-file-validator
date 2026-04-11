# config-file-validator

![Python](https://img.shields.io/badge/python-3.10+-blue) ![license](https://img.shields.io/badge/license-MIT-yellow) ![tests](https://img.shields.io/badge/tests-27%20pass-brightgreen)

CLI Python que valida archivos `.env`, JSON y YAML contra schemas definidos. Detecta claves faltantes, tipos incorrectos, valores vacíos y patrones de expresión regular. Integrable en pipelines CI/CD.

## Instalación en 3 comandos

```bash
git clone https://github.com/Quesillo27/config-file-validator
cd config-file-validator
pip install -r requirements.txt
```

## Uso

```bash
# Validar sintaxis básica (sin schema)
python -m src.cli validate config.env
python -m src.cli validate config.json

# Validar contra un schema
python -m src.cli validate .env --schema schemas/env.schema.yaml
python -m src.cli validate config.json --schema schemas/app.schema.json

# Validar múltiples archivos de una vez
python -m src.cli validate .env.production .env.staging --schema schemas/env.schema.yaml

# Generar un schema base desde un archivo existente
python -m src.cli schema-init .env -o schemas/env.schema.yaml

# Salida JSON (útil en CI/CD)
python -m src.cli validate .env --schema schema.yaml --json-output
```

## Ejemplo

```bash
$ python -m src.cli validate .env --schema schemas/env.schema.yaml --verbose

✅ .env (ENV) — válido  (1 advertencia)
  ┌─────────────┬──────────────────────────────────────────────┐
  │ Campo       │ Advertencia                                  │
  ├─────────────┼──────────────────────────────────────────────┤
  │ JWT_SECRET  │ Secret-looking key has empty value           │
  └─────────────┴──────────────────────────────────────────────┘

$ echo $?
0
```

```bash
$ python -m src.cli validate config.json --schema schemas/app.schema.json

❌ config.json (JSON) — inválido
  ┌──────────┬──────────────────────────────────┐
  │ Campo    │ Error                            │
  ├──────────┼──────────────────────────────────┤
  │ version  │ 'abc' is not of type 'integer'   │
  │ port     │ 'port' is a required property    │
  └──────────┴──────────────────────────────────┘

$ echo $?
1
```

## Comandos disponibles

| Comando | Descripción |
|---|---|
| `cfv validate <files...>` | Valida uno o más archivos de configuración |
| `cfv schema-init <file>` | Genera un schema base a partir de un archivo existente |

### Opciones de `validate`

| Opción | Descripción |
|---|---|
| `-s / --schema <path>` | Schema de validación (.json o .yaml) |
| `-f / --format` | Forzar formato: `env`, `json`, `yaml` |
| `-v / --verbose` | Mostrar advertencias detalladas |
| `--json-output` | Salida en JSON (para CI/CD) |

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
```

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

## Integración CI/CD

```yaml
# .github/workflows/validate.yml
- name: Validar configuración
  run: |
    pip install -r requirements.txt
    python -m src.cli validate .env.example --schema schemas/env.schema.yaml
```

## Variables de entorno

Este CLI no requiere variables de entorno propias — valida las de tus proyectos.

## Contribuir

PRs bienvenidos. Corre `make test` antes de enviar.
