#!/usr/bin/env bash
# Ejemplos de uso de cfv keys y cfv export

# --- cfv keys ---

# 1. Listar todas las claves de un .env
cfv keys .env

# 2. Contar claves
cfv keys .env --count

# 3. Comparar claves de múltiples archivos
cfv keys .env.staging .env.production

# 4. Salida JSON (ideal para scripting)
cfv keys config.yaml --json-output

# --- cfv export ---

# 5. Exportar un .env a JSON
cfv export .env --output-format json

# 6. Exportar un YAML complejo a JSON con indentación 4
cfv export config.yaml --output-format json --indent 4

# 7. Exportar un JSON a YAML
cfv export config.json --output-format yaml

# 8. Combinar con diff: exportar + comparar
cfv export .env.staging > /tmp/staging.json
cfv export .env.production > /tmp/production.json
diff /tmp/staging.json /tmp/production.json

# --- cfv schema-init ---

# 9. Generar schema desde un .env existente
cfv schema-init .env -o schemas/env.schema.yaml

# 10. Previsualizar sin escribir archivo
cfv schema-init config.json --dry-run
