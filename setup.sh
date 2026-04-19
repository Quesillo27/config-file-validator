#!/usr/bin/env bash
set -e

echo "→ Instalando config-file-validator..."
pip install -r requirements.txt
pip install -e .
echo "✅ Instalado. Ejecuta: cfv --help"
