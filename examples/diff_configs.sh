#!/usr/bin/env bash
# Ejemplos de uso del comando cfv diff

# 1. Comparar dos archivos .env (staging vs production)
cfv diff .env.staging .env.production

# 2. Comparar y mostrar también las claves sin cambios
cfv diff .env.staging .env.production --show-unchanged

# 3. Comparar archivos JSON (como config de despliegue)
cfv diff config.staging.json config.production.json

# 4. Salida JSON para scripting
cfv diff .env.staging .env.production --json-output

# 5. En CI: verificar que staging y prod tienen las mismas claves
cfv diff .env.staging .env.production --json-output | \
  jq 'if .summary.added > 0 or .summary.removed > 0 then error("clave mismatch") else "ok" end'
