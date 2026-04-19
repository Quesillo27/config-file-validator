#!/usr/bin/env bash
# Ejemplos de uso del comando cfv validate

# 1. Validar un .env sin schema (chequea sintaxis + advertencias de secrets)
cfv validate .env

# 2. Validar contra un schema
cfv validate .env --schema schemas/env.schema.yaml

# 3. Modo estricto: falla si hay advertencias
cfv validate .env --schema schemas/env.schema.yaml --strict

# 4. Múltiples archivos a la vez
cfv validate .env.development .env.staging .env.production --schema schemas/env.schema.yaml

# 5. Salida JSON para CI/CD pipelines
cfv validate .env --schema schemas/env.schema.yaml --json-output | jq '.[0].valid'

# 6. Salida JSON + siempre exit 0 (no bloquea CI, solo reporta)
cfv validate .env --schema schemas/env.schema.yaml --json-output --exit-zero

# 7. Forzar formato (útil para archivos sin extensión)
cfv validate /etc/myapp/config --format env

# 8. Verbose: muestra advertencias detalladas
cfv validate .env --schema schemas/env.schema.yaml --verbose
