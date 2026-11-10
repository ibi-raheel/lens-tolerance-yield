#!/usr/bin/env bash
# Full pipeline, in order. Python runs isolated (-I) with the repo root put on sys.path.
# Ray-traced stages use 4 workers under nice (pipeline/mc.py). About 2.5 h on a laptop.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
run() { nice -n 10 "$PY" -I -W ignore -c "import sys; sys.path.insert(0, sys.argv[1]); $1" "$ROOT"; }
run "from pipeline import validate; validate.run()"                       # lens rebuilt + checked
"$ROOT/run_mc.sh" sens                                                       # 2k+1 = 83 traces
"$ROOT/run_mc.sh" main                                                       # 6,000-module Monte Carlo
"$ROOT/run_mc.sh" diag                                                       # 2,400 single-culprit modules
"$ROOT/run_mc.sh" sig                                                        # lookup signature library
"$ROOT/run_mc.sh" wide                                                       # 2,000-module wide design
run "from pipeline import analyze as A; A.main(['yield','surrogates','drivers','diagnosis','scrubs'])"
run "from pipeline import analyze as A, module as M; import json; o=json.load(open(sys.argv[1]+'/results/summary.json')); A.make_spot([o['drivers']['rows'][0]['group']], name='spot1'); A.make_spot([r['group'] for r in o['drivers']['rows'][:3]], name='spot3')"
run "from pipeline import analyze as A; A.main(['drivers','realloc'])"
"$ROOT/run_mc.sh" verify "$ROOT/results/budget_reallocated.json" verify   # fresh MC, new budget
run "from pipeline import analyze as A; A.main(['verify','export'])"
