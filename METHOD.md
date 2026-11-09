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

{{PIPELINE_TABLE}}

**Baseline A, limit-based RSS** (what a sensitivity report gives). Trace each tolerance alone at +limit and −limit with focus re-optimised. Take the worse change of each criterion, dᵢ = min(m(+Lᵢ), m(−Lᵢ)) − m₀, and RSS = √Σdᵢ². The limit is 2σ, so the criterion is modelled as Normal(m₀, (RSS/2)²) with no mean shift. The RSS method reports nominal ± RSS. Yield = P(centre passes) × P(corner passes). Cost: 2k+1 = 83 traces.

**Baseline B, second-order (diagonal quadratic) stack.** Per field output y_f and tolerance i, from the same 83 traces: a_fi = (y_f(+1) − y_f(−1))/2 and b_fi = (y_f(+1) + y_f(−1))/2 − y_f0. Then y_f(u) = y_f0 + Σᵢ (a_fi uᵢ + b_fi uᵢ²), with u in units of the limit. It captures the one-sided quadratic loss from tilt and decenter, but no interactions and no compensator coupling. Yield = the share of held-out modules whose predicted criteria pass.

**Footnote, derivative-based linear stack.** y_f0 + Σ a_fi uᵢ. Shown only to make the point that a first derivative misses even losses.

**Surrogate.** Candidates: an MLP (tanh, 2×96, early stopping, ensemble of 3 seeds); a *hybrid* (the same MLP trained on the residual of Baseline B, y = B(u) + NN(u)); gradient-boosted trees; and a full quadratic ridge response surface (902 terms). All are trained on 3,000 traced modules, the model is selected on 1,000 validation modules, and it is scored once on 2,000 held-out modules.

**Driver ranking.** For each culprit group, the surrogate predicts the yield if that group were perfect (others at current tolerances, 60,000 sampled modules); share = recovered / Σ recovered. Sobol total-order indices of the worst-corner MTF (SALib, truncated-normal inputs, grouped) are reported beside it. The top answer is spot-checked by re-tracing 500 held-out modules with that group zeroed.

**Diagnosis.** Data: 2,400 traced modules with background tolerances plus one culprit group pushed to 2–4× its limit (random direction). Features: the 36 through-field MTF changes (9 fields × 2 frequencies × T/S) after autofocus. Model: MLP classifier, trained on 75% of the modules. Look-alike culprits are merged by 5-fold cross-validated confusion on the training set only (merge if mutual confusion > 35%). Baseline: least-squares fit of the change to a traced signature library (each culprit at 3× its limit, 8 directions for x/y pairs, both signs for single tolerances), with the best residual winning. Scored on the held-out modules that fail the spec.

**Reallocation.** Per culprit group, multiply the limits by k ∈ {0.5, 0.67, 0.8, 1, 1.25, 1.5, 2}. Cost proxy = Σ over the 41 tolerances of (current limit / new limit). Greedy search: take the cheapest feasible single loosening, and if none is feasible, tighten one top-6 driver while loosening another. Constraint: surrogate yield ≥ current + 0.5 points. The surrogate used here is retrained on 4,000 main modules + 2,000 "wide" modules sampled out to 2× every limit, so the loosened budget lies inside its training range. **Only the yield of a fresh, independent ray-traced Monte Carlo (seed 3) on the new budget is reported.**

## 6. Validation

{{VALIDATION_BLOCK}}

## 7. Results

{{RESULTS_BLOCK}}

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
