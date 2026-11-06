#!/usr/bin/env bash
# Run an auth CLI command in the fs container, where auth.db is mounted.
#
#   ./run-auth.sh create-user alice
#   ./run-auth.sh issue-token uploader alice --days 90
#   ./run-auth.sh --help
set -euo pipefail

if [[ $# -eq 0 ]]; then
  echo "usage: ${0##*/} <command> [<args> ...]; ${0##*/} --help lists the commands" >&2
  exit 2
fi

mkdir -p "$(dirname "$0")/data"

exec docker compose -f "$(dirname "$0")/docker-compose.yml" \
  run --rm fs python -m auth "$@"
