import { useEffect, useRef } from "react";
import type { Data } from "../data";
import { pct } from "../data";
import { LineKey, Step, linePath, scale, ticks, useWidth } from "../ui";

const LO = 0.16, HI = 0.4;

/** Predicted vs traced, drawn on a canvas (2,000 points) under an SVG axis layer. */
function Scatter({ traced, pred, spec, color, label }: { traced: number[]; pred: number[]; spec: number; color: string; label: string }) {
  const [ref, W] = useWidth<HTMLDivElement>(420);
  const cv = useRef<HTMLCanvasElement>(null);
  const H = Math.min(W, 360);
  const m = { l: 40, r: 10, t: 10, b: 38 };
  const x = scale(LO, HI, m.l, W - m.r);
  const y = scale(LO, HI, H - m.b, m.t);
  useEffect(() => {
    const c = cv.current;
    if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = W * dpr; c.height = H * dpr;
    const ctx = c.getContext("2d")!;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, H);
    const col = getComputedStyle(c).getPropertyValue("--dot").trim() || "#1d2126";
    ctx.fillStyle = col;
    ctx.globalAlpha = 0.38;
    for (let i = 0; i < traced.length; i++) {
      const px = x(Math.min(HI, Math.max(LO, traced[i]))), py = y(Math.min(HI, Math.max(LO, pred[i])));
      ctx.beginPath(); ctx.arc(px, py, 1.7, 0, 2 * Math.PI); ctx.fill();
    }
  }, [W, H, traced, pred, x, y]);
  const wrong = traced.reduce((a, t, i) => a + ((t >= spec) !== (pred[i] >= spec) ? 1 : 0), 0);
  return (
    <div ref={ref} style={{ position: "relative" }}>
      <canvas ref={cv} style={{ position: "absolute", inset: 0, width: W, height: H, ["--dot" as string]: color }} aria-hidden="true" />
      <svg className="chart" width={W} height={H} role="img" aria-label={`${label}: predicted against traced worst-corner MTF on 2,000 held-out modules`} style={{ position: "relative" }}>
        <g className="grid">
          {ticks(0.2, 0.4, 0.05).map((t) => <line key={"x" + t} x1={x(t)} x2={x(t)} y1={m.t} y2={H - m.b} />)}
          {ticks(0.2, 0.4, 0.05).map((t) => <line key={"y" + t} x1={m.l} x2={W - m.r} y1={y(t)} y2={y(t)} />)}
        </g>
        {ticks(0.2, 0.4, 0.1).map((t) => <text key={"a" + t} x={x(t)} y={H - m.b + 16} textAnchor="middle">{t.toFixed(1)}</text>)}
        {ticks(0.2, 0.4, 0.1).map((t) => <text key={"b" + t} x={m.l - 6} y={y(t) + 4} textAnchor="end">{t.toFixed(1)}</text>)}
        <text className="axis-label" x={W - m.r} y={H - 4} textAnchor="end">Traced worst-corner MTF</text>
        <text className="axis-label" x={m.l + 4} y={m.t + 12}>Predicted</text>
        <path d={linePath([[x(LO), y(LO)], [x(HI), y(HI)]])} stroke="var(--ink-3)" strokeWidth="1" />
        <line x1={x(spec)} x2={x(spec)} y1={m.t} y2={H - m.b} stroke="var(--carmine)" strokeDasharray="2 3" />
        <line x1={m.l} x2={W - m.r} y1={y(spec)} y2={y(spec)} stroke="var(--carmine)" strokeDasharray="2 3" />
        <text x={W - m.r - 4} y={y(spec) + 14} textAnchor="end" style={{ fill: "var(--carmine)" }}>spec</text>
        <text x={x(spec) + 6} y={H - m.b - 8} className="lbl">{wrong} wrong calls</text>
      </svg>
    </div>
  );
}

function LearningCurve({ s }: { s: Data["summary"] }) {
  const [ref, W] = useWidth<HTMLDivElement>();
  const H = 220, m = { l: 52, r: 120, t: 10, b: 36 };
  const lc = s.learning_curve;
  const x = scale(Math.log10(40), Math.log10(3200), m.l, W - m.r);
  const y = scale(Math.log10(0.0007), Math.log10(0.03), H - m.b, m.t);
  const chosen = lc.curves[s.surrogates.chosen].corner_rmse;
  const B = lc.B_reference.corner_rmse;
  return (
    <div ref={ref}>
      <svg className="chart" width={W} height={H} role="img" aria-label="Learning curve: surrogate error against number of traced training modules">
        <g className="grid">{[0.001, 0.003, 0.01, 0.03].map((t) => <line key={t} x1={m.l} x2={W - m.r} y1={y(Math.log10(t))} y2={y(Math.log10(t))} />)}</g>
        {[0.001, 0.003, 0.01, 0.03].map((t) => <text key={t} x={m.l - 6} y={y(Math.log10(t)) + 4} textAnchor="end">{t}</text>)}
        {lc.train_sizes.map((t) => <text key={t} x={x(Math.log10(t))} y={H - m.b + 16} textAnchor="middle">{t.toLocaleString()}</text>)}
        <text className="axis-label" x={W - m.r} y={H - 2} textAnchor="end">Traced training modules (log)</text>
        <line x1={m.l} x2={W - m.r} y1={y(Math.log10(B))} y2={y(Math.log10(B))} stroke="var(--ink)" strokeWidth="2" strokeDasharray="6 4" />
        <text x={W - m.r + 6} y={y(Math.log10(B)) + 4} className="lbl">second-order stack</text>
        <path d={linePath(lc.train_sizes.map((n, i) => [x(Math.log10(n)), y(Math.log10(chosen[i]))]))} fill="none" stroke="var(--model)" strokeWidth="2" />
        <text x={W - m.r + 6} y={y(Math.log10(chosen[chosen.length - 1])) + 4} className="lbl">surrogate</text>
        <text className="axis-label" x={m.l - 6} y={m.t - 0} textAnchor="end" />
      </svg>
      <p className="caption">Worst-corner RMSE on held-out modules (log). The stack uses 83 traces at any size.</p>
    </div>
  );
}

export function S5Ai({ data }: { data: Data }) {
  const s = data.summary;
  const sc = data.figures.scatter;
  const si = s.surrogate_intervals;
  const ratio = si.corner_rmse.B / si.corner_rmse.surrogate;
  const [r0, r1] = si.corner_rmse.ratio_B_over_surrogate_ci;
  const cand = s.surrogates.candidates;
  const names: Record<string, string> = { hybrid_sym: "Stack + neural-net correction, symmetry-trained (chosen)", mlp_sym: "Neural net, symmetry-trained", hybrid: "Stack + neural-net correction", mlp: "Neural net", quad_ridge: "Quadratic ridge regression", gbm: "Gradient-boosted trees" };
  return (
    <Step
      n={5}
      id="s5"
      title="The AI vs the stack"
      copy={
        <>
          On modules it never saw, the trained surrogate predicts worst-corner MTF <b>{Math.round(ratio)}× better</b> than the second-order stack (95%: {Math.round(r0)}-{Math.round(r1)}×) and calls pass/fail right on{" "}
          <b>{pct(si.pass_fail_accuracy.surrogate)} vs {pct(si.pass_fail_accuracy.B)}</b>. It ties the stack at about 100 traced modules, and for the yield number alone, counting traced modules does as well; its job is scoring budgets that were never traced.
        </>
      }
      details={
        <>
          <div>
            <h4>Learning curve</h4>
            <LearningCurve s={s} />
          </div>
          <div className="scroll-x">
            <h4>Candidate models, chosen on the validation split, scored once on held-out</h4>
            <table>
              <thead><tr><th>Model</th><th className="num">Validation RMSE</th><th className="num">Held-out RMSE</th><th className="num">Pass/fail right</th></tr></thead>
              <tbody>
                {Object.entries(cand).sort((a, b) => a[1].val_corner_rmse - b[1].val_corner_rmse).map(([k, v]) => (
                  <tr key={k}><td>{names[k] ?? k}</td><td className="num">{v.val_corner_rmse.toFixed(4)}</td><td className="num">{v.corner_rmse.toFixed(4)}</td><td className="num">{pct(v.pass_fail_accuracy)}</td></tr>
                ))}
                <tr><td>Second-order stack (baseline)</td><td className="num">&nbsp;</td><td className="num">{s.yield.B_quadratic.corner_rmse.toFixed(4)}</td><td className="num">{pct(s.yield.B_quadratic.pass_fail_accuracy)}</td></tr>
              </tbody>
            </table>
          </div>
          <p>
            Intervals: paired bootstrap over the 2,000 held-out modules, 4,000 resamples. Pass/fail gain {(100 * si.pass_fail_accuracy.difference_ci[0]).toFixed(1)} to {(100 * si.pass_fail_accuracy.difference_ci[1]).toFixed(1)} points. Yield on the held-out modules: traced {pct(si.yield_.heldout_traced)}, surrogate{" "}
            {pct(si.yield_.surrogate_on_same_modules)}, counting the 3,000 traced training modules {pct(si.yield_.counting_3000_training_traces)} ± {(100 * si.yield_.counting_se).toFixed(1)}.
          </p>
        </>
      }
    >
      <div className="legend">
        <span><LineKey color="var(--ink-3)" width={1} /> perfect prediction</span>
        <span><LineKey color="var(--carmine)" width={1} dash="2 3" /> spec 0.262 on both axes</span>
      </div>
      <div className="ai-grid">
        <div>
          <h3>Second-order stack</h3>
          <div className="sub">RMSE {sc.rmse_stack.toFixed(4)}, from 83 sensitivity traces</div>
          <Scatter traced={sc.traced} pred={sc.stack} spec={sc.spec} color="#1d2126" label="Second-order stack" />
        </div>
        <div>
          <h3>Trained surrogate</h3>
          <div className="sub">RMSE {sc.rmse_surrogate.toFixed(4)}, trained on 3,000 traced modules</div>
          <Scatter traced={sc.traced} pred={sc.surrogate} spec={sc.spec} color="#2c5bc8" label="Trained surrogate" />
        </div>
      </div>
    </Step>
  );
}
