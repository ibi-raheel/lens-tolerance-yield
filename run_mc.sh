#!/usr/bin/env bash
# Runs a Monte Carlo stage. Python runs isolated (-I); the repo root is put on sys.path explicitly.
# Usage: ./run_mc.sh main|sens|diag|scrubs|verify <budget.json> <name>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
nice -n 10 "$PY" -I -W ignore -c "import sys; sys.path.insert(0, sys.argv[1]); from pipeline import mc; mc.dispatch(sys.argv[2:])" "$ROOT" "$@"
