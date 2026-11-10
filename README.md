# Lens tolerance yield

Which mechanical tolerances in a compact camera lens actually set image-quality yield after autofocus, and how far off is the standard RSS stack? A ray-traced Monte Carlo of a published six-element phone lens, two classical baselines, a trained surrogate, and a reallocated tolerance budget checked by a fresh Monte Carlo.

**Live demo:** pending deploy

## The problem
A camera module's tolerance budget is set part by part: lens decenter and tilt, centre thickness, spacers, the barrel seat, the sensor die. Autofocus takes out spacing errors but not tilt or decenter. A sensitivity + RSS estimate is quick, but it treats one-sided MTF losses as zero-mean and ignores interactions, and it gives no yield distribution. So a budget can end up tight where it doesn't matter and loose where it does.

## What it does
The page walks through the answer in order:
1. **The question and the measured answer.** Three near-tied tolerances own 72% of the yield loss. The standard RSS estimate overstates yield by 11 points. A reallocated budget loosens 25 of 41 tolerances, and re-tracing the same held-out modules on it shows yield held to within about 2 points (−0.9 ± 0.7 points, paired).
2. **A real lens, rebuilt.** The published prescription ray-traced. EFL, TTL, entrance pupil and element focal lengths match the patent within 0.6%, and its field curves match the patent's own plots.
3. **Autofocus fixes spacing, not tilt.** Refocus recovers a 12 µm despace (centre MTF 0.62 with refocus against 0.41 without, so the module still passes). Under sensor tilt the corners split and focus can't recover them (hand calc: 0.08° = one depth of focus at the corner).
4. **6,000 simulated modules.** The worst-corner MTF distribution against the spec: measured yield 80.4% ± 0.9 on held-out modules, against 91.5% from the limit-based RSS and 75.0% from a second-order stack.
5. **What sets the yield, and the AI against the stacks.** Driver ranking (spot-checked by direct ray trace). On held-out modules the surrogate's worst-corner MTF error is 13× smaller than the second-order stack's (95% interval 11–14×) and its pass/fail call is right 99.4% of the time against 88%. For the yield number alone it is no better than counting the traced modules; its value is scoring budgets that were never traced.
6. **Which part is out?** From a failing module's through-field MTF, the classifier names the culprit 72% top-1 / 84% top-2, against 49% / 62% for a signature lookup.
7. **The solution.** Current vs reallocated tolerance table, the fresh-Monte-Carlo yield, and the CLI to run it on another design.

## How it works
- **Lens:** the published prescription (US 9,435,983 B2, embodiment 1) rebuilt in [Optiland](https://github.com/HarrisonKramer/optiland). EFL, TTL, entrance pupil and all six element focal lengths match the patent within 0.6% (the F-number follows from the EFL, since the aperture is set from it).
- **Modules:** 41 mechanical tolerances, each tied to a drawing callout with a GD&T hand calc, sampled as truncated normals. Every simulated module gets its own autofocus best focus. Polychromatic MTF comes from pupil autocorrelation on the traced wavefront.
- **Baselines:** limit-based RSS (2k+1 traces, sensitivity-report style) and a second-order (diagonal quadratic) stack from the same traces.
- **AI:** a neural-net surrogate that adds a learned correction to the quadratic stack. It is trained on the lens's exact rotational symmetry (8 images of every module) and scored only on held-out modules. A second model, a classifier, names the likely culprit part from a failing module's through-field MTF, compared with a signature-lookup baseline.
- **Solution:** a reallocated tolerance budget, verified by a fresh, independent ray-traced Monte Carlo, plus a CLI (`tool/lensyield.py run | diagnose`) that runs on data in the same format.

Details: [METHOD.md](METHOD.md) (equations, assumptions, validation, limitations) · [SOLUTION.md](SOLUTION.md) (playbook and week-1 plan).

## Run locally
```bash
# web demo (reads precomputed results in web/public/data)
cd web && npm install && npm run dev

# pipeline (Python 3.12)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -I -m pytest -q tests        # tests
PYTHON=.venv/bin/python ./run_pipeline.sh     # full pipeline, about 2.5 h on 4 cores
# or re-run only the analysis on the committed ray-traced runs in data/runs/ (minutes)
.venv/bin/python -I -c "import sys; sys.path.insert(0, '.'); from pipeline import analyze as A; A.main(['yield','surrogates','drivers','diagnosis','scrubs','verify','export'])"
```

## Data
- **Lens design (real):** US 9,435,983 B2, 1st embodiment, Tables 1–2, transcribed from the USPTO full text. US patent text is not under copyright; it is used here with citation.
- **Module population (simulated):** a physics simulation of that published design under the stated tolerance assumptions ([METHOD.md](METHOD.md) section 3). It is not measured line data, and it is labelled as simulated everywhere it appears.
- **Ray tracing:** Optiland 0.6.3, MIT licence.

---
Built by Ibi Raheel, mechanical engineer building AI tools. More work at [ibiraheel.com](https://ibiraheel.com).
