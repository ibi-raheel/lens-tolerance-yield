import type { Data } from "../data";
import { pct, signed } from "../data";
import { Step, linePath, scale, ticks, useWidth } from "../ui";

function Histogram({ s }: { s: Data["summary"] }) {
  const [ref, W] = useWidth<HTMLDivElement>();
  const H = Math.min(300, Math.max(220, W * 0.4));
  const m = { l: 44, r: 16, t: 26, b: 40 };
  const e = s.histogram.edges, c = s.histogram.corner_counts;
  const lo = 0.14, hi = 0.4;
  const x = scale(lo, hi, m.l, W - m.r);
  const yMax = Math.ceil(Math.max(...c) / 200) * 200;
  const y = scale(0, yMax, H - m.b, m.t);
  const spec = s.spec.thresholds.corner_min;
  const nom = s.spec.nominal.corner_min;
  const mean = s.yield.mean_shift.corner_mean;
  return (
    <div ref={ref}>
      <svg className="chart" width={W} height={H} role="img" aria-label="Histogram of worst-corner MTF across 6,000 simulated modules, with the spec line">
        <g className="grid">{ticks(0, yMax, 200).map((t) => <line key={t} x1={m.l} x2={W - m.r} y1={y(t)} y2={y(t)} />)}</g>
        <g className="axis">
          {ticks(0, yMax, 200).map((t) => <text key={t} x={m.l - 8} y={y(t) + 4} textAnchor="end">{t}</text>)}
          {ticks(0.15, 0.4, 0.05).map((t) => <text key={t} x={x(t)} y={H - m.b + 18} textAnchor="middle">{t.toFixed(2)}</text>)}
          <text className="axis-label" x={W - m.r} y={H - 4} textAnchor="end">Worst-corner MTF at 111.6 lp/mm</text>
          <text className="axis-label" x={m.l - 8} y={m.t - 12}>Modules</text>
        </g>
        {c.map((n, i) => {
          if (!n || e[i] < lo || e[i + 1] > hi + 1e-9) return null;
          const x0 = x(e[i]) + 1, x1 = x(e[i + 1]) - 1;
          const fail = e[i + 1] <= spec + 1e-9;
          return (
            <rect key={i} x={x0} width={Math.max(1, x1 - x0)} y={y(n)} height={y(0) - y(n)} fill={fail ? "var(--carmine)" : "var(--ink)"} opacity={fail ? 0.85 : 0.82}>
              <title>{`${e[i].toFixed(2)} to ${e[i + 1].toFixed(2)}: ${n} modules`}</title>
            </rect>
          );
        })}
        <line x1={x(spec)} x2={x(spec)} y1={m.t - 6} y2={y(0)} stroke="var(--carmine)" strokeWidth="1.5" />
        <text x={x(spec) - 6} y={m.t + 4} textAnchor="end" className="lbl" style={{ fill: "var(--carmine)" }}>spec {spec.toFixed(3)}</text>
        <line x1={x(nom)} x2={x(nom)} y1={m.t - 6} y2={y(0)} stroke="var(--ink)" strokeDasharray="2 3" />
        <text x={W < 520 ? x(nom) - 6 : x(nom) + 6} y={W < 520 ? m.t - 10 : m.t + 4} textAnchor={W < 520 ? "end" : "start"} className="lbl">{W < 520 ? "nominal" : "nominal design"} {nom.toFixed(3)}</text>
        <line x1={x(mean)} x2={x(mean)} y1={y(0)} y2={y(0) + 6} stroke="var(--ink)" strokeWidth="2" />
      </svg>
    </div>
  );
}

function YieldScale({ s }: { s: Data["summary"] }) {
  const [ref, W] = useWidth<HTMLDivElement>();
  const narrowS = W < 520;
  const H = narrowS ? 150 : 118;
  const m = { l: 44, r: 16 };
  const x = scale(70, 95, m.l, W - m.r);
  const meas = 100 * s.yield.heldout_truth, se = 100 * s.yield.heldout_se;
  const rss = 100 * s.yield.A_limit_rss.yield_, quad = 100 * s.yield.B_quadratic.yield_;
  const narrow = W < 520;
  const base = 64;
  return (
    <div ref={ref}>
      <svg className="chart" width={W} height={H} role="img" aria-label="Yield: measured on held-out modules against the two classical estimates">
        <line x1={m.l} x2={W - m.r} y1={base} y2={base} stroke="var(--ink)" />
        {ticks(70, 95, 5).map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={base} y2={base + 5} stroke="var(--ink)" />
            <text x={x(t)} y={base + 20} textAnchor="middle">{t}%</text>
          </g>
        ))}
        {!narrowS && <text className="axis-label" x={W - m.r} y={H - 4} textAnchor="end">Yield</text>}
        {/* measured with +/- 2 SE */}
        <line x1={x(meas - 2 * se)} x2={x(meas + 2 * se)} y1={base} y2={base} stroke="var(--carmine)" strokeWidth="5" />
        <circle cx={x(meas)} cy={base} r="7" fill="var(--carmine)" stroke="var(--paper)" strokeWidth="2" />
        <text x={x(meas)} y={base - 34} textAnchor="middle" className="lbl-strong">{meas.toFixed(1)}% ± {se.toFixed(1)}</text>
        <text x={x(meas)} y={base - 18} textAnchor="middle">measured{narrow ? "" : ", held-out"}</text>
        {[
          { v: quad, a: "second-order", b: `${quad.toFixed(1)}%` },
          { v: rss, a: narrow ? "RSS" : "limit-based RSS", b: `${rss.toFixed(1)}%` },
        ].map((k) => (
          <g key={k.a}>
            <rect x={x(k.v) - 5} y={base - 5} width="10" height="10" fill="var(--paper)" stroke="var(--ink)" strokeWidth="1.5" />
            <text x={x(k.v)} y={narrow ? base + 40 : base - 34} textAnchor="middle" className="lbl-strong">{k.b}</text>
            <text x={x(k.v)} y={narrow ? base + 56 : base - 18} textAnchor="middle">{k.a}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}

function Convergence({ s }: { s: Data["summary"] }) {
  const [ref, W] = useWidth<HTMLDivElement>();
  const H = 200, m = { l: 44, r: 16, t: 10, b: 36 };
  const cv = s.population.convergence;
  const x = scale(Math.log10(50), Math.log10(6000), m.l, W - m.r);
  const y = scale(0.7, 0.82, H - m.b, m.t);
  return (
    <div ref={ref}>
      <svg className="chart" width={W} height={H} role="img" aria-label="Running yield against number of modules">
        <g className="grid">{[0.7, 0.74, 0.78, 0.82].map((t) => <line key={t} x1={m.l} x2={W - m.r} y1={y(t)} y2={y(t)} />)}</g>
        {[0.7, 0.74, 0.78, 0.82].map((t) => <text key={t} x={m.l - 8} y={y(t) + 4} textAnchor="end">{Math.round(t * 100)}%</text>)}
        {[50, 100, 300, 1000, 3000, 6000].map((t) => <text key={t} x={x(Math.log10(t))} y={H - m.b + 18} textAnchor="middle">{t.toLocaleString()}</text>)}
        <text className="axis-label" x={W - m.r} y={H - 2} textAnchor="end">Modules traced (log)</text>
        <path d={linePath(cv.n.map((n, i) => [x(Math.log10(n)), y(cv.yield_[i])]))} fill="none" stroke="var(--ink)" strokeWidth="2" />
      </svg>
    </div>
  );
}

export function S3Population({ data }: { data: Data }) {
  const s = data.summary;
  return (
    <Step
      n={3}
      id="s3"
      title="6,000 modules off the line"
      tag="simulated"
      copy={
        <>
          On {s.population.n_heldout.toLocaleString()} held-out modules, <b>{pct(s.yield.heldout_truth)} ± {(100 * s.yield.heldout_se).toFixed(1)} pass</b>; the limit-based RSS estimate says <b>{pct(s.yield.A_limit_rss.yield_)}</b> and a second-order stack{" "}
          <b>{pct(s.yield.B_quadratic.yield_)}</b>. Forty-one small one-sided losses shift the whole distribution down.
        </>
      }
      details={
        <>
          <div>
            <h4>Yield as modules accumulate (all 6,000)</h4>
            <Convergence s={s} />
          </div>
          <div className="scroll-x">
            <h4>Spec, shift and the estimates</h4>
            <table>
              <tbody>
                <tr><td>Pass rule</td><td>Centre at least 90% of nominal, and every corner at least 80% of the nominal worst corner; (T+S)/2 MTF at 111.6 lp/mm after refocus</td></tr>
                <tr><td>Worst-corner MTF: population mean vs nominal</td><td className="num">{s.yield.mean_shift.corner_mean.toFixed(3)} vs {s.yield.mean_shift.corner_nominal.toFixed(3)}</td></tr>
                <tr><td>Failures by cause (all modules)</td><td className="num">corner {s.histogram.fail_reason.corner_only.toLocaleString()}, centre {s.histogram.fail_reason.centre_only}, both {s.histogram.fail_reason.both}</td></tr>
                <tr><td>Yield, all 6,000 modules</td><td className="num">{pct(s.population.yield_all)} ± {(100 * s.population.yield_all_se).toFixed(1)}</td></tr>
                <tr><td>Limit-based RSS ({s.yield.A_limit_rss.traces} traces)</td><td className="num">{pct(s.yield.A_limit_rss.yield_)} ({signed(s.yield.A_limit_rss.error_pts)} pts)</td></tr>
                <tr><td>Second-order stack ({s.yield.B_quadratic.traces} traces)</td><td className="num">{pct(s.yield.B_quadratic.yield_)} ({signed(s.yield.B_quadratic.error_pts)} pts)</td></tr>
              </tbody>
            </table>
          </div>
          <p>Every module is one draw of all 41 tolerances (truncated normal, limit = 2&sigma;), refocused to its own best focus, then ray-traced at 9 field points in three wavelengths. It is a physics simulation of the published design under stated tolerances, not line data.</p>
        </>
      }
    >
      <Histogram s={s} />
      <div className="caption" style={{ marginBottom: 18 }}>All 6,000 simulated modules. Carmine bins lie wholly below the corner spec. Tick on the axis: population mean {s.yield.mean_shift.corner_mean.toFixed(3)}.</div>
      <YieldScale s={s} />
      <div className="caption">Measured = share of the 2,000 held-out modules that pass after ray trace, bar = ±2 standard errors. Squares = the two classical estimates from 83 sensitivity traces.</div>
    </Step>
  );
}
