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
exec "$python_bin" -m namoz_bot.main
