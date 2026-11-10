// Precomputed pipeline results, shipped as static JSON in public/data.
/* eslint-disable @typescript-eslint/no-explicit-any */

export type Scrub = {
  values: number[];
  unit: string;
  centre_af: number[];
  centre_fixed: number[];
  worst_af: number[];
  worst_fixed: number[];
  corners_af: number[][];
  focus_um: number[];
  exponent_worst_corner?: number;
  exponent_mean_of_corners?: number;
};

export type DriverRow = { group: string; yield_if_perfect: number; recovered_pts: number; share_of_loss: number };
export type BudgetRow = { tol: string; group: string; unit: string; callout: string; current: number; new: number; factor: number };

export type Summary = {
  scrubs: { rows: { despace: Scrub; sensor_tilt: Scrub }; corner_names: string[] };
  population: { n_total: number; n_train: number; n_val: number; n_heldout: number; yield_all: number; yield_all_se: number; convergence: { n: number[]; yield_: number[] } };
  spec: { thresholds: { centre: number; corner_min: number }; nominal: { centre: number; corner_min: number }; rule: string };
  histogram: { edges: number[]; corner_counts: number[]; fail_reason: { centre_only: number; corner_only: number; both: number } };
  yield: {
    heldout_truth: number;
    heldout_se: number;
    A_limit_rss: { yield_: number; error_pts: number; traces: number };
    B_quadratic: { yield_: number; error_pts: number; traces: number; corner_rmse: number; pass_fail_accuracy: number };
    B_quadratic_calibrated: { yield_: number; error_pts: number; traces: number };
    mean_shift: { corner_mean: number; corner_nominal: number; centre_mean: number; centre_nominal: number };
  };
  surrogates: { candidates: Record<string, any>; chosen: string; chosen_by: string };
  learning_curve: { train_sizes: number[]; curves: Record<string, { abs_yield_error_pts: number[]; corner_rmse: number[] }>; B_reference: { traces: number; corner_rmse: number; abs_yield_error_pts: number } };
  drivers: { rows: DriverRow[]; sobol_corner: Record<string, { ST: number; S1: number }>; spot_checks: { groups: string[]; n: number; traced_recovered_pts: number; surrogate_recovered_pts: number; traced_se_pts: number }[]; yield_all_surrogate: number };
  diagnosis: {
    n_train: number;
    n_test_failing: number;
    classes: string[];
    test_failing_counts: Record<string, number>;
    model: { top1: number; top2: number; confusion: number[][] };
    lookup: { top1: number; top2: number; confusion: number[][]; library_traces: number };
    chance_top1: number;
    intervals: { model_top1: number[]; lookup_top1: number[]; top1_difference: number[]; method: string };
    example: { true: string; model: string; lookup: string; mtf: number[][][]; nominal: number[][][]; proba: Record<string, number> };
  };
  reallocation: { table: BudgetRow[]; cost_change_pct: number; cost_model: string; current_yield_surrogate: number; new_yield_surrogate: number };
  verification: {
    new_budget_yield: number; new_budget_se: number; n_new: number;
    current_full_population_yield: number; current_full_population_se: number;
    paired: { n: number; difference_pts: number; difference_se_pts: number; difference_ci95_pts: number[]; flipped_to_pass: number; flipped_to_fail: number };
  };
  surrogate_intervals: {
    corner_rmse: { surrogate: number; B: number; ratio_B_over_surrogate_ci: number[] };
    pass_fail_accuracy: { surrogate: number; B: number; difference_ci: number[] };
    yield_: { heldout_traced: number; surrogate_on_same_modules: number; counting_3000_training_traces: number; counting_se: number };
  };
};

export type Validation = {
  first_order: {
    efl_mm: { rebuilt: number; published: number; err_pct: number };
    fno: { rebuilt: number; published: number; err_pct: number; note: string };
    ttl_mm: { rebuilt: number; published: number; err_pct: number };
    epd_mm: { rebuilt: number; published_from_ratio: number };
  };
  element_focal_lengths: { element: string; published: number; optiland: number; lensmaker: number; err_pct: number }[];
  mtf_vs_diffraction: { freqs: number[]; diffraction_limit: number[]; nominal_centre: number[]; cutoff_lpmm: number };
  tilt_hand_calc: { corner_image_height_mm: number; depth_of_focus_um: number; tilt_to_reach_dof_deg_diagonal: number; rows: { theta_deg: number; hand_calc_um: number; traced_um: number }[]; equation: string };
  fig2_comparison: { rows: { img_ht: number; field_deg: number; tan_mm: number; tan_patent: number; sag_mm: number; sag_patent: number; distortion_pct: number; distortion_patent: number }[]; note: string };
  nominal_mtf_vs_height: { img_ht_mm: number[]; tan_n4: number[]; sag_n4: number[]; tan_n2: number[]; sag_n2: number[] };
};

export type Figures = {
  lens: {
    surfaces: { name: string; element: number; z: number; sd: number; profile: number[][] }[];
    rays: { field: number; wl: number; py: number; pts: number[][] }[];
    wavelengths_um: number[];
  };
  scatter: { traced: number[]; stack: number[]; surrogate: number[]; spec: number; rmse_stack: number; rmse_surrogate: number; n: number };
};

export type Data = { summary: Summary; validation: Validation; figures: Figures };

export async function loadData(): Promise<Data> {
  const get = (f: string) => fetch(`${import.meta.env.BASE_URL}data/${f}`).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${f}: ${r.status}`))));
  const [summary, validation, figures] = await Promise.all([get("summary.json"), get("validation.json"), get("figures.json")]);
  return { summary, validation, figures };
}

// ---- formatting ----
const MINUS = "−";
export const pct = (x: number, d = 1) => `${(100 * x).toFixed(d)}%`;
export const num = (x: number, d = 2) => (x < 0 ? MINUS + Math.abs(x).toFixed(d) : x.toFixed(d));
export const signed = (x: number, d = 1) => (x < 0 ? MINUS : "+") + Math.abs(x).toFixed(d);

export const REPO = "https://github.com/ibi-raheel/lens-tolerance-yield";
