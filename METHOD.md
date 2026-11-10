# METHOD

How the numbers in this repo are made, what they assume, and how they were checked. Every result here is computed by `pipeline/` and stored in `results/`. Nothing is typed in by hand except the patent tables and the tolerance assumptions, which are listed below.

## 1. The lens (real, published)

**Source.** US 9,435,983 B2, 1st embodiment, Tables 1 and 2: a six-element plastic phone lens, f = 3.43 mm, F/1.49, HFOV 39.5°, TL 4.85 mm, ImgH = TL / 1.67 = 2.904 mm. The tables were transcribed from the USPTO full-text PDF image into `data/prescription_us9435983_e1.json`. US patent text is not under copyright (USPTO policy) and is used here with citation.

**Why this design.** The plan called for a five-element phone lens from a patent citation list. All five candidates checked turned out to be six- or seven-element designs, or their tables are image-only figures, so a comparable six-element, single-focal-length phone wide lens with clean tables was used. A fast (F/1.49) lens is also the harder and more current case for tolerancing.

**Surface sag** (the patent's convention, confirmed in its text):

  X(Y) = (Y²/R) / (1 + √(1 − (1+k)(Y/R)²)) + Σᵢ Aᵢ Yⁱ,  i = 4, 6, …, 16

Optiland's `even_asphere` takes the coefficients of r², r⁴, …, so the patent's A4…A16 are passed as `[0, A4, …, A16]`.

**Aperture stop.** The patent lists the stop with thickness −0.379 mm before L1, so the stop plane sits 0.379 mm *behind* the L1 front vertex, inside L1's front sag. It is modelled as a plane inside L1's material, and it belongs to the barrel, not to element 1. Getting this wrong (stop in air ahead of L1) breaks the chief-ray path at the edge of the field.

**Materials.** Each plastic is set by (n_d, V_d) from the table through Optiland's `AbbeMaterial` (Buchdahl model). Its index at 587.6 nm is reproduced to 2×10⁻⁶.

**Wavelengths and fields.** F, d, C (486.1, 587.6, 656.3 nm), equal weights. Nine evaluation fields: the centre; four mid-field points at 0.5 × HFOV on ±x and ±y (image height 1.27 mm); four corners at 0.7 × HFOV on the diagonals (image height 1.85 mm, 64% of ImgH). Beyond about 0.9 field, chief rays reach the outer zone of L5's front asphere, where the Newton intersection can jump to a wrong root. Full-field points are not used.

## 2. MTF engine (`pipeline/mtf.py`)

Optiland's `FFTMTF` aborts a whole field if any pupil ray fails, and that happens on this design's steep asphere edges. So the MTF is computed by pupil autocorrelation on Optiland's traced wavefront, with failed rays treated as vignetted:

- Pupil grid 40 × 40 (uniform in normalised entrance-pupil coordinates p). OPD W(p) in waves comes from Optiland's chief-ray reference-sphere strategy.
- Pupil function P(p) = A(p) e^{2πiW(p)}, with A = 1 for a valid ray and 0 otherwise.
- A linear map J: p → (L − L_c, M − M_c) is fitted to the image-space direction cosines. A spatial frequency vector ν (cycles/mm) shears the pupil by Δp = J⁻¹ λν.
- OTF_λ(ν) = Σ_p P(p) P*(p − Δp) / Σ_p A(p), with bilinear interpolation.
- Polychromatic: OTF(ν) = (1/3) Σ_λ OTF_λ(ν) · e^{−2πi ν·Δx_λ}. Here Δx_λ is the chief-ray image point of wavelength λ relative to d, so lateral colour costs contrast as it should.
- **Tangential** = frequency vector along the radial direction of the field point in the image; **sagittal** = perpendicular. MTF = |OTF|.
- **Through-focus is analytic.** Moving the image plane by dz moves the reference point by δ = dz (L_c/N_c, M_c/N_c, 1). That adds −δ·(k − k_c)/λ waves to every ray. This is first order in dz; against a full re-trace at +8 µm it agrees to 0.01 MTF.

Checks: a perfect pupil reproduces the circular-aperture MTF (2/π)(φ − cos φ sin φ), φ = acos(ν/ν_c), to 0.02. On axis it agrees with Optiland's FFTMTF to 0.005; at 0.7 field to 0.003 (tangential) and 0.024 (sagittal, where FFTMTF uses a single working F-number). Sampling noise floor: about 0.008 MTF on a mid-field sagittal value when the pupil grid shifts 20 µm (`tests/test_physics.py`).

**Frequencies.** 1.12 µm pixel → Nyquist 446.4 lp/mm. The spec uses Nyquist/4 = 111.6 lp/mm; Nyquist/2 = 223.2 lp/mm is reported and used by the diagnosis model.

## 3. Mechanical tolerances (assumptions) and the GD&T behind them

Each perturbation corresponds to a drawing callout. Each limit is a ±value read as **2σ** of a normal distribution, truncated at the limit. This is the Zemax-style Monte Carlo default.

| Tolerance (count) | ± limit | Drawing callout and hand calc |
|---|---|---|
| Element decenter x, y (12) | 2 µm | Lens OD-to-optical-axis concentricity (~1 µm, precision molding) + interlock/barrel fit (~1 µm) |
| Element tilt x, y (12) | 0.03° | Flange (bearing-face) parallelism: θ ≈ Δ / D = 1.8 µm / 3.5 mm = 0.03° |
| Centre thickness (6) | 3 µm | Molded centre thickness |
| Air gaps (5) | 3 µm | Spacer thickness (±2 µm) + seat flatness (±1 µm) |
| Barrel decenter x, y (2) | 20 µm | Holder bore position. Moves the image only; a built-in null check |
| Barrel-to-sensor tilt x, y (2) | 0.08° | Holder seat perpendicularity + adhesive bondline wedge: θ ≈ Δ / D = 8 µm / 6 mm = 0.076° |
| Sensor tilt x, y (2) | 0.05° | Die-attach bondline wedge: 4 µm / 4.6 mm die = 0.05° |

41 tolerances in total. Rigid element tilt is applied about the element's mid-thickness point: both surfaces rotate by the same angle, and each vertex moves to pivot + R(vertex − pivot) (test: thickness preserved, both vertices on the tilted axis). Barrel tilt pivots at the barrel's mid-length. Sensor tilt pivots at the sensor centre.

**Sources for the sizes.** S. Nam, *Tolerance analysis using Zemax, the case for the small optics* (Univ. of Arizona OPTI 521 report): for a three-element cell-phone lens it uses 0.010 mm thickness, 0.05° element tilt and 0.010 mm element decenter as perturbations, and it calls these lenses "very tight and challenging". This design is F/1.49 with 1.12 µm pixels against that report's 45 lp/mm criterion, so the decenter, thickness and gap limits used here are 3–5× tighter, and tilts are derived from flatness over diameter as above. These are stated assumptions, not a supplier's capability data. The first job on a real line is to replace them with measured part distributions (SOLUTION.md).

**Compensator.** Image distance (the VCM/focus). Per module it maximises the mean over the nine fields of (T+S)/2 MTF at Nyquist/4. A 2 µm grid over ±30 µm around nominal is refined by a parabola through the best three points.

## 4. Spec (fixed before any Monte Carlo was run)

A module **passes** if, at its own autofocus best focus:
- centre (T+S)/2 MTF at 111.6 lp/mm ≥ 90% of nominal (0.604), and
- each of the four corners (T+S)/2 MTF at 111.6 lp/mm ≥ 80% of the nominal worst corner (0.262).

Nominal: centre 0.671, worst corner 0.327 (tangential 0.232 / sagittal 0.423 at the corners). The design's off-axis tangential MTF is low because its tangential field curve swings by tens of µm across the field. That is visible in the patent's own FIG. 2 and reproduced in section 6.

## 5. Pipeline

| Stage | Code | Ray traces | What it produces |
|---|---|---|---|
| Rebuild + validate | `pipeline/validate.py` | ~20 | `results/validation.json` |
| Sensitivity (2k+1) | `pipeline/mc.py sens` | 83 | Baselines A and B |
| Main Monte Carlo | `pipeline/mc.py main` | 6,000 | Yield; train 3,000 / validation 1,000 / held-out 2,000 |
| Diagnosis set | `pipeline/mc.py diag` | 2,400 | Single-culprit failures |
| Signature library | `pipeline/mc.py sig` | 143 | Lookup baseline |
| Wide design | `pipeline/mc.py wide` | 2,000 | Reallocation surrogate coverage to 2× limits |
| Spot checks | `analyze.make_spot` | 2 × 500 | Direct-trace check of the driver ranking |
| Verification | `pipeline/mc.py verify` | 3,000 | Fresh Monte Carlo on the reallocated budget |

Timing: a pilot of 20 modules took 1.55 s per module on one core. With 4 niced workers the throughput was about 115 modules per minute, so 6,000 modules took 52 minutes. That sized the main run at 6,000: the held-out yield standard error is 0.9 points and the full-population standard error 0.5 points.

**Baseline A, limit-based RSS** (what a sensitivity report gives). Trace each tolerance alone at +limit and −limit with focus re-optimised. Take the worse change of each criterion, dᵢ = min(m(+Lᵢ), m(−Lᵢ)) − m₀, and RSS = √Σdᵢ². The limit is 2σ, so the criterion is modelled as Normal(m₀, (RSS/2)²) with no mean shift. The RSS method reports nominal ± RSS. Yield = P(centre passes) × P(corner passes). Cost: 2k+1 = 83 traces.

**Baseline B, second-order (diagonal quadratic) stack.** Per field output y_f and tolerance i, from the same 83 traces: a_fi = (y_f(+1) − y_f(−1))/2 and b_fi = (y_f(+1) + y_f(−1))/2 − y_f0. Then y_f(u) = y_f0 + Σᵢ (a_fi uᵢ + b_fi uᵢ²), with u in units of the limit. It captures the one-sided quadratic loss from tilt and decenter, but no interactions and no compensator coupling. Yield = the share of held-out modules whose predicted criteria pass.

**Footnote, derivative-based linear stack.** y_f0 + Σ a_fi uᵢ. Shown only to make the point that a first derivative misses even losses.

**Surrogate.** Candidates: an MLP (tanh, 2×96, early stopping, ensemble of 3 seeds); a *hybrid* (the same MLP trained on the residual of Baseline B, y = B(u) + NN(u)); each of those two also *symmetry-trained*; gradient-boosted trees; and a full quadratic ridge response surface (902 terms). All are trained on 3,000 traced modules, the model is selected on 1,000 validation modules (lowest worst-corner RMSE), and it is scored once on 2,000 held-out modules.

*Symmetry training* (`pipeline/symmetry.py`). The nominal lens is rotationally symmetric. Rotating a module by 90° maps every x/y pair as a vector, (dx, dy) → (−dy, dx) and (tx, ty) → (−ty, tx), and moves each corner to the next. Mirroring x maps (dx, dy) → (−dx, dy) and (tx, ty) → (tx, −ty) (a tilt is an axial vector), and swaps corners in pairs. Both maps are checked against direct ray traces (within 0.002). Every training module therefore yields 8 exact training examples, and predictions are averaged over the same 8 images, so the model is symmetric by construction.

*Yield from a regression model.* A surrogate predicts E[y | u], which is smoother than y, so thresholding it overstates the pass rate. Yield is therefore estimated by thresholding prediction + residual, with residual vectors drawn jointly across the five outputs from the **validation** set (40 draws). Uncalibrated yields are also stored in `results/summary.json`.

**Driver ranking.** For each culprit group, the surrogate predicts the yield if that group were perfect (others at current tolerances, 60,000 sampled modules); share = recovered / Σ recovered. Sobol total-order indices of the worst-corner MTF (SALib, truncated-normal inputs, grouped) are reported beside it. The top answer is spot-checked by re-tracing 500 held-out modules with that group zeroed.

**Diagnosis.** Data: 2,400 traced modules with background tolerances plus one culprit group pushed to 2–4× its limit (random direction). Features: the 36 through-field MTF changes (9 fields × 2 frequencies × T/S) after autofocus. Model: MLP classifier, trained on 75% of the modules and their 8 symmetry images (the culprit label is invariant under rotation and mirroring; field order permutes). Look-alike culprits are merged by 5-fold cross-validated confusion on the training set only (merge if mutual confusion > 35%). Baseline: least-squares fit of the change to a traced signature library (each culprit at 3× its limit, 8 directions for x/y pairs, both signs for single tolerances), with the best residual winning. Scored on the held-out modules that fail the spec.

**Reallocation.** Per culprit group, multiply the limits by k ∈ {0.5, 0.67, 0.8, 1, 1.25, 1.5, 2}. Cost proxy = Σ over the 41 tolerances of (current limit / new limit). Greedy search: take the cheapest feasible single loosening, and if none is feasible, tighten one top-6 driver while loosening another. Constraint: surrogate yield ≥ current + 0.5 points. The surrogate used here (same architecture) is retrained on the 3,000 training modules + 2,000 "wide" modules, calibrated on the 1,000 validation modules, sampled out to 2× every limit, so the loosened budget lies inside its training range. **Only the yield of a fresh, independent ray-traced Monte Carlo (seed 3) on the new budget is reported.**

## 6. Validation

All values from `results/validation.json` and `tests/` (27 tests pass).

**First order vs the patent.**

| Quantity | Rebuilt | Published | Error |
|---|---|---|---|
| EFL (mm) | 3.428 | 3.43 | −0.06% |
| F-number | 1.489 | 1.49 | −0.06% |
| TTL (mm) | 4.851 | 4.85 | +0.02% |
| EPD (mm) | 2.302 | 2.294 (from EPD/ImgH = 0.79) | +0.3% |

**Element focal lengths** (Optiland paraxial on the isolated element; the thick-lens lensmaker equation 1/f = (n−1)[1/R₁ − 1/R₂ + (n−1)t/(nR₁R₂)] agrees to < 0.1%):

| | L1 | L2 | L3 | L4 | L5 | L6 |
|---|---|---|---|---|---|---|
| Published (mm) | 3.97 | −7.78 | 5.36 | −5.88 | 6.56 | −16.31 |
| Rebuilt (mm) | 3.970 | −7.773 | 5.366 | −5.884 | 6.558 | −16.401 |
| Error | −0.01% | −0.08% | +0.11% | +0.07% | −0.03% | +0.56% |

**Against the patent's own aberration plots (FIG. 2, read by eye ±0.01 mm).** Narrow-pencil field curves: tangential +0.016 / +0.005 / −0.026 mm at image heights 0.72 / 1.45 / 2.17 mm, against the plot's ≈ +0.02 / −0.01 / −0.06. Sagittal +0.003 / −0.015 / −0.027 against ≈ 0.00 / −0.01 / −0.03. Agreement is within about 0.015 mm, except tangential at 2.17 mm, where the plotted curve is on a steep slope. Distortion is +2.3 / +3.3 / +3.1% against ≈ +1.0 / +2.8 / +2.7%, i.e. 0.4–0.5 points higher at mid-field and 1.3 points higher at 0.72 mm. The sign, size and shape (the large tangential swing that keeps off-axis tangential MTF low) are reproduced.

**Diffraction limit.** Cutoff 1/(λN) = 1,143 lp/mm at 587.6 nm, F/1.489. The polychromatic diffraction-limited MTF is 0.878 / 0.758 at 111.6 / 223.2 lp/mm. Nominal centre MTF is 0.671 / 0.550, and every field and frequency is under the limit.

**Sensor-tilt hand calc.** A field point at image height y sees an axial image-plane shift Δz = y·tan θ. For the corner (y-component 1.310 mm), the hand calc against the traced shift of that corner's best focus:

| θ | Hand calc | Traced |
|---|---|---|
| 0.05° | 1.14 µm | 1.13 µm |
| 0.10° | 2.29 µm | 2.26 µm |
| 0.15° | 3.43 µm | 3.39 µm |

The depth of focus is ±2λN² = ±2.61 µm. A tilt of 0.081° along the diagonal moves the 1.853 mm corner by a full depth of focus. Autofocus cannot help, because the opposite corner moves the other way.

**Tilt response shape (measured).** Sensor tilt 0 → 0.2° with autofocus: the centre holds at 0.671 and the focus does not move. The worst-corner MTF falls with an exponent of 1.17 (V-shaped, first order at one corner), while the mean of the four corners (a symmetric metric) falls with an exponent of 1.99 (quadratic, zero slope at nominal). That is the reason a derivative-based linear stack misses tilt and decenter. A despace error (L1–L2 gap, 0 → 12 µm) is fully recovered by autofocus (worst corner 0.327 → 0.376, centre 0.671 → 0.623). With focus held, the worst corner collapses to 0.124.

**Physical nulls and symmetry.** Barrel decenter (20 µm) changes the spec metrics by < 10⁻³ (it only shifts the image). Decenter at +limit and −limit gives the same loss (even response). Rotating every x/y perturbation pair by 90°, or mirroring x, permutes the traced corner MTFs exactly as predicted (within 0.002), which is what licenses the symmetry augmentation.

**Monte Carlo.** Seeds are fixed and reproducible (tested). 0 of 6,000 modules were untraceable. The yield convergence curve is in `results/summary.json` (`population.convergence`).

**Driver ranking spot-check (direct ray trace, 500 held-out modules each).** Setting L1 decenter perfect recovers +7.6 ± 2.3 yield points traced, against +7.3 predicted by the surrogate. Setting the top three groups perfect recovers +19.4 ± 1.8 traced, against +19.1 predicted.

## 7. Results

All on the 2,000 held-out modules unless stated. Measured yield: **80.4% ± 0.9** (full 6,000-module population 79.2% ± 0.5). Of the 1,248 failures in the full population, 1,240 fail only on a corner, 6 on both, and 2 only on the centre. Mean worst-corner MTF falls from 0.327 (nominal) to 0.283. The loss is one-sided.

**Classical stacks vs the Monte Carlo**

| Method | Ray traces | Predicted yield | Error vs measured | Worst-corner RMSE per module |
|---|---|---|---|---|
| Measured (Monte Carlo) | 6,000 | 80.4% ± 0.9 | | |
| A: limit-based RSS | 83 | 91.5% | **+11.1 pts** (overstates) | (distribution only) |
| B: second-order stack | 83 | 75.0% | −5.4 pts (understates) | 0.0124 |
| B + its validation residuals | 83 + 1,000 | 75.9% | −4.5 pts | 0.0124 |
| Linear (derivative) stack, footnote | 83 | 95.6% | +15.2 pts | |

The limit-based RSS treats every loss as a symmetric ± spread around nominal. Here 41 terms each cost a little MTF in the same direction, so the real distribution shifts down by 0.044 and the RSS misses that shift. The second-order stack captures the shift but overstates it: it adds each term's loss independently and has no interactions or compensator coupling.

**Surrogates (trained on 3,000, selected on 1,000, scored on 2,000 held-out)**

| Model | Yield error | Worst-corner RMSE | Pass/fail accuracy |
|---|---|---|---|
| Quadratic stack + neural-net correction, symmetry-trained (**chosen**) | **+0.02 pts** | **0.0010** | **99.4%** |
| Plain neural net, symmetry-trained | +0.12 pts | 0.0010 | 99.2% |
| Plain neural net | −0.49 pts | 0.0040 | 96.6% |
| Quadratic stack + neural-net correction | +0.09 pts | 0.0064 | 94.4% |
| Full quadratic ridge response surface (902 terms) | +0.86 pts | 0.0072 | 93.9% |
| Gradient-boosted trees | +7.79 pts | 0.0134 | 87.8% |

Learning curve (chosen model, held-out): worst-corner RMSE 0.0142 / 0.0120 / 0.0098 / 0.0055 / 0.0020 / 0.0014 / 0.0010 at 50 / 100 / 200 / 400 / 800 / 1,600 / 3,000 training modules. It matches the second-order stack's per-module accuracy (0.0124, 83 traces) at about 100–200 traced modules and is 2× better by 400. Yield errors below about 400 training modules swing by 1–3 points (small-sample noise). So the surrogate's win comes from a better model of the same physics (symmetry plus interactions), and the extra traces do not explain it: the plain neural net on the same 3,000 modules is 4× worse per module.

**What sets the yield** (yield recovered if a group were perfect; surrogate on 60,000 sampled modules)

| Group | Recovered | Share of loss | Sobol total order (worst corner) |
|---|---|---|---|
| L1 decenter | +8.4 pts | 25% | 0.37 |
| Image-plane tilt (barrel + sensor) | +8.1 pts | 24% | 0.30 |
| L5 decenter | +8.0 pts | 23% | 0.33 |
| L1 tilt | +2.5 pts | 7% | 0.13 |
| Spacing (5 gaps) | +2.0 pts | 6% | 0.13 |
| L2 thickness | +1.5 pts | 4% | 0.08 |

Three near-tied terms own 71% of the yield loss. Decenter of the strongest front element (L1) and of L5, which sits where the off-axis beams are widest, cost as much as image-plane tilt. Tilts of L3–L6 and barrel decenter cost almost nothing.

**Diagnosis (247 held-out failing modules, 21 culprit classes, chance 13%)**

| Method | Top-1 | Top-2 |
|---|---|---|
| Trained classifier (symmetry-augmented MLP) | **72%** | **84%** |
| Nearest-signature lookup (143 traced signatures) | 49% | 62% |

No pair of culprits crossed the 35% mutual-confusion merge threshold on the training folds, so nothing was merged. The weakest classes are small-effect tilts of L3–L6 and L4 decenter, which only fail the spec with help from the background tolerances. A module whose injected culprit is barrel decenter fails for other reasons and cannot be attributed (2 cases). The lookup confuses L1 decenter with L5 decenter in half of the L1 cases, because their corner signatures are similar in shape. The classifier separates them by using the mid-field and Nyquist/2 channels.

**Reallocated budget.** Tighten 2 groups (L1 decenter 2 → 1.33 µm, L2 centre thickness 3 → 2 µm). Loosen 11 groups (25 tolerances): L3–L6 tilt and L3 decenter ×2, L2 tilt, L4 decenter and all spacers ×1.5, L2/L6 decenter ×1.25, barrel decenter ×2. The cost proxy falls 20.3% (18.8% excluding the free barrel-decenter loosening). Surrogate yield goes from 79.2% to 79.7% (target ≥ current + 0.5).

**Verification (fresh, independent ray-traced Monte Carlo, seed 3, 3,000 modules on the reallocated budget):** yield **79.2% ± 0.7**. The current budget measured 79.2% ± 0.5 over all 6,000 modules, a difference of **+0.0 ± 0.9 points**, and 80.4% ± 0.9 on its 2,000 held-out modules, a difference of −1.2 ± 1.2 points. Within the resolution of these Monte Carlo sizes (about 1 point), the reallocated budget holds yield while loosening 25 of 41 tolerances. The surrogate predicted 79.7%, inside the verified interval. To claim a hold tighter than ±1 point would take roughly 4× more verification modules.

## 8. Limitations

- The population is a physics simulation of a published design under the stated tolerance assumptions. It is not measured line data, and the tolerance sizes are assumptions (section 3).
- Not modelled: surface form (power/irregularity), index and Abbe lot variation, element wedge, stray light, sensor package effects beyond die tilt, and lens-actuator tilt during focus.
- Fields stop at 0.7 × HFOV on the diagonal, because the outer asphere zones break the intersection solver near full field. Real corner performance (and its sensitivity) at full field will be worse.
- Focus is the only compensator. Active alignment (focus + tilt) would recover much of the image-plane tilt loss.
- The MTF engine is a pupil-autocorrelation model with a linear pupil-to-direction map. It agrees with Optiland's FFT MTF within 0.024 where both run, and its sampling noise floor is about 0.008 MTF.
- The diagnosis model is trained on simulated single-culprit failures. Real failures can have two parts out at once, and the training set doesn't cover that.

## References

- US 9,435,983 B2, *Photographing optical lens assembly, image capturing unit and mobile device*, 1st embodiment (prescription source). USPTO full text.
- H. Kramer et al., Optiland (MIT licence), https://github.com/HarrisonKramer/optiland, version 0.6.3: sequential ray tracing and wavefront.
- S. Nam, *Tolerance analysis using Zemax, the case for the small optics*, Univ. of Arizona OPTI 521.
- J. W. Goodman, *Introduction to Fourier Optics*: OTF as the normalised pupil autocorrelation; diffraction-limited MTF of a circular pupil.
- Depth of focus ±2λN² and defocus from tilt Δz = y·tan θ: standard first-order optics.
- I. M. Sobol / SALib (Herman & Usher, JOSS 2017): variance-based sensitivity indices.
