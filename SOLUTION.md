# SOLUTION: a tolerance-yield playbook for a compact camera module

**The question.** After autofocus, which mechanical tolerances in a compact camera module actually set image-quality yield, which can be loosened without losing it, and how close does a standard sensitivity + RSS estimate get to the yield a full Monte Carlo shows?

**What this repo answers on a published lens** (numbers from `results/summary.json`, all measured):
- **Three near-tied terms own 71% of the yield loss:** front-element (L1) decenter, image-plane tilt (barrel seat + sensor die), and L5 decenter. Each is worth about 8 yield points if perfect, and direct re-traces confirm it (+7.6 ± 2.3 traced vs +7.3 predicted for L1 decenter; +19.4 ± 1.8 vs +19.1 for all three).
- **Autofocus fixes spacing, not tilt.** A 12 µm despace is recovered by refocus (centre MTF 0.62 with refocus against 0.41 without; the module still passes). Sensor tilt is not: at this F/1.49 the depth of focus is ±2.6 µm, and 0.08° of tilt moves the 1.85 mm corner by a full depth of focus.
- **The standard limit-based RSS estimate overstates yield by 11 points** (91.5% predicted vs 80.4% ± 0.9 measured), because 41 small one-sided losses shift the whole distribution down and the RSS models a symmetric spread. A second-order stack understates it by 5 points (75.0%).
- **A trained surrogate predicts each module's worst-corner MTF within 0.001 RMSE**, 12× better than the second-order stack (95% interval 11–14×), and calls pass/fail right on 99.4% of held-out modules against 88%. It needs traces to get there: at the stack's budget (about 100 traced modules) the two tie. For the yield number alone, counting the 3,000 traced modules does as well; the surrogate earns its place by scoring tolerance budgets that were never traced (driver ranking, reallocation).
- **25 of 41 tolerances can be loosened, with 2 groups tightened** (L1 decenter 2 → 1.33 µm, L2 centre thickness 3 → 2 µm). That is a 20% lower cost proxy. A fresh 3,000-module Monte Carlo gives 79.2% ± 0.7 against 79.2% ± 0.5 before, and re-tracing the same 2,000 held-out modules on the new budget gives −0.9 ± 0.7 points (95% interval −2.2 to +0.5): yield held to within about 2 points, most likely a small loss, where the surrogate had aimed for +0.5.
- **A failing module's MTF test names the culprit part** first time in 72% of held-out failures (95% interval 66–77%), in the top two 84% (21 possible parts; a signature lookup gets 49% / 62%, and the paired gap is +16 to +29 points).

## The playbook

1. **Rebuild the lens and prove it.** Prescription to JSON. Check EFL, TTL, entrance pupil and each element's focal length against the design sheet (paraxial and the thick-lens lensmaker equation), and nominal MTF against the diffraction limit. Here every first-order value lands within 0.6% (`results/validation.json`).
2. **Write the tolerance table the way the drawings will.** Every optical perturbation traces back to a drawing callout and a hand calc (`METHOD.md` section 3): element decenter from OD-to-axis concentricity and interlock fit, element tilt from flange parallelism (θ ≈ Δ/D), image-plane tilt from holder-seat perpendicularity and bondline wedge, sensor tilt from die-attach wedge. A ±limit is 2σ, truncated.
3. **Make autofocus the compensator.** Each simulated module gets its own best focus, as the VCM would give it. This matters: spacing and thickness errors mostly vanish after refocus, while tilt and decenter do not.
4. **Run the Monte Carlo and size it from a timed pilot.** A 20-module pilot took 1.55 s per module on one core, so 6,000 modules took 52 minutes on 4 niced workers. Report yield with its standard error √(p(1−p)/n), never a bare number.
5. **Run the classical stack beside it and keep both.** The limit-based RSS takes 2k+1 traces and is what most sensitivity reports show. Its known blind spots are one-sided losses treated as zero-mean, no interactions, and no yield distribution. The second-order stack fixes the first. The Monte Carlo shows how far off each one is on this design.
6. **Train a surrogate on the traced modules and score it on modules it never saw.** Select on a validation split and report on the held-out split. Show the learning curve and the ray-trace budget, so it is clear how much of a win comes from more traces.
7. **Rank what actually costs yield.** For each part, ask the surrogate how much yield comes back if that part were perfect, then spot-check the top answer with a direct ray trace.
8. **Reallocate, then verify with a fresh Monte Carlo.** Loosen what doesn't matter, tighten the one or two terms that do, with yield held. Only ray-traced yield counts: a fresh, independent Monte Carlo, plus a paired re-trace of the same modules for a tight read on the change.
9. **Diagnose failing modules from their MTF test.** A failing module's through-field MTF pattern (T/S at centre, ±x, ±y and the corners) goes to a classifier trained on simulated failures with one part out of spec. Look-alike culprits are merged honestly, and it is compared against a signature-lookup baseline.

## Week 1 on your line

| Day | What I'd do | What you'd get |
|---|---|---|
| 1 | Take one module design: prescription, mechanical drawings, current tolerance table, the module MTF spec and test fields | The design rebuilt and checked against your own EFL/BFL/MTF numbers |
| 2 | Map every drawing callout to an optical perturbation with a hand calc (flatness over diameter → tilt, runout → decenter, bondline wedge → image tilt) | A tolerance table your mechanical and optical teams both recognise |
| 3 | Pilot, then full Monte Carlo with your autofocus/active-alignment as the compensator, run next to your current stack | Measured yield ± SE, and how far the current estimate sits from it |
| 4 | Driver ranking and a reallocated budget (which callouts can open up, which one or two to tighten) | A proposed budget with the cost proxy and the yield it holds |
| 5 | Fresh verification Monte Carlo on the proposed budget, plus the diagnosis model set up on your MTF test format | A verified budget, and a tool that names the likely part on a failing unit from the line |

## Run it on data in the same format

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# yield, both stacks, drivers and a reallocated table for a prescription + tolerance CSV
.venv/bin/python -I tool/lensyield.py run --prescription data/prescription_us9435983_e1.json \
    --tolerances tool/example_tolerances.csv --modules 400 --out out/
# verify the reallocated table with a fresh Monte Carlo (a new seed, so the check is independent
# of the draws the reallocation was chosen on; the same seed gives a paired, lower-noise comparison)
.venv/bin/python -I tool/lensyield.py run --tolerances out/tolerances_reallocated.csv --modules 400 --seed 8 --out out/verify
# a failing module's through-field MTF -> likely culprit part
.venv/bin/python -I tool/lensyield.py diagnose --mtf tool/example_failing_module.csv
```

Formats: the prescription JSON in `data/` (surfaces with R, thickness, n, V, conic, A4–A16, element index), a tolerance CSV `name,limit` (mm or deg, the ±limit at 2σ), and an MTF CSV `field,freq_lpmm,T,S` for the nine test fields at Nyquist/4 and Nyquist/2.

## What it does not do (yet)

- Surface form errors (power, irregularity), index and Abbe lot variation, and wedge are not in the tolerance set. They add to the yield loss, and the table structure takes them directly.
- The population is a physics simulation of a published design under stated tolerances. It is not measured line data. The first thing to do on a real line is calibrate the tolerance distributions against measured part data.
- Active alignment would change the compensator from focus only to focus plus tilt. The code takes extra compensators the same way it takes focus.
