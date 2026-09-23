#!/usr/bin/env bash

set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python_bin="$project_dir/.venv/bin/python"

if [[ ! -x "$python_bin" ]]; then
    echo "Xato: $python_bin topilmadi. Avval virtual muhit yarating." >&2
    exit 1
fi

if [[ ! -f "$project_dir/.env" ]]; then
    echo "Xato: $project_dir/.env topilmadi." >&2
    exit 1
fi

cd "$project_dir"
case "${1:-}" in
    "") module="namoz_bot.main" ;;
    --local) module="namoz_bot.local" ;;
    *) echo "Foydalanish: bash run_bot.sh [--local]" >&2; exit 2 ;;
esac
if [[ $# -gt 1 ]]; then
    echo "Foydalanish: bash run_bot.sh [--local]" >&2
    exit 2
fi
exec "$python_bin" -m "$module"
