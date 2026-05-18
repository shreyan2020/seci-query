#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../.."

CONFIG="${1:-evals/suites/server_biomed_template.json}"
OUTPUT_DIR="${2:-data/eval_runs/server_biomed}"

shift $(( $# > 0 ? 1 : 0 ))
shift $(( $# > 0 ? 1 : 0 ))

python -m evals.run_suite --config "$CONFIG" --output-dir "$OUTPUT_DIR" "$@"
