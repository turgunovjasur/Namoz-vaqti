#!/usr/bin/env bash

set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -ne 0 ]]; then
    echo "Foydalanish: bash run_local_bot.sh" >&2
    exit 2
fi

exec bash "$project_dir/run_bot.sh" --local
