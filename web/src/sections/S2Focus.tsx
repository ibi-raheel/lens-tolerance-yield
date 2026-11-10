import { useEffect, useRef, useState } from "react";
import type { Data, Scrub } from "../data";
import { LineKey, Step, linePath, scale, ticks, useWidth } from "../ui";

const F = 111.6; // lp/mm, the spec frequency

/** erf, Abramowitz-Stegun 7.1.26 */
function erf(x: number) {
  const s = Math.sign(x), a = Math.abs(x);
  const t = 1 / (1 + 0.3275911 * a);
  const y = 1 - ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-a * a);
  return s * y;
}

/** Slanted-edge tile. Blur = Gaussian with the same MTF at 111.6 lp/mm:
 *  MTF(f) = exp(-2 pi^2 sigma^2 f^2)  =>  sigma = sqrt(-ln M / (2 pi^2 f^2)). */
function EdgeTile({ mtf, label, flip }: { mtf: number; label: string; flip?: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const N = 128;
    c.width = N;
    c.height = N;
    const ctx = c.getContext("2d")!;
    const img = ctx.createImageData(N, N);
    const sigmaUm = 1000 * Math.sqrt(-Math.log(Math.max(mtf, 1e-3)) / (2 * Math.PI ** 2 * F * F));
    const umPerPx = 16 / N; // tile spans 16 um on the sensor
    const sigPx = sigmaUm / umPerPx;
    const th = ((flip ? -5 : 5) * Math.PI) / 180; // 5 deg slant, as in ISO 12233
    const nx = Math.cos(th), ny = Math.sin(th);
    for (let j = 0; j < N; j++)
      for (let i = 0; i < N; i++) {
        const d = (i - N / 2) * nx + (j - N / 2) * ny;
        const v = 0.5 * (1 + erf(d / (sigPx * Math.SQRT2)));
        const g = Math.round(28 + v * (250 - 28));
        const k = 4 * (j * N + i);
        img.data[k] = g; img.data[k + 1] = g; img.data[k + 2] = g - 1; img.data[k + 3] = 255;
      }
    ctx.putImageData(img, 0, 0);
  }, [mtf, flip]);
  return (
    <div className="tile">
      <canvas ref={ref} aria-label={`Slanted edge rendered at MTF ${mtf.toFixed(2)}`} role="img" />
      <div className="t-name">{label}</div>
      <div className="t-val">{mtf.toFixed(2)}<small>MTF</small></div>
    </div>
  );
}

function interp(xs: number[], ys: number[], x: number) {
  if (x <= xs[0]) return ys[0];
  for (let i = 1; i < xs.length; i++) if (x <= xs[i]) { const t = (x - xs[i - 1]) / (xs[i] - xs[i - 1]); return ys[i - 1] + t * (ys[i] - ys[i - 1]); }
  return ys[ys.length - 1];
}

function ScrubChart({ s, mode, at, spec }: { s: Scrub; mode: "despace" | "tilt"; at: number; spec: { centre: number; corner_min: number } }) {
  const [ref, W] = useWidth<HTMLDivElement>();
  const H = Math.min(320, Math.max(240, W * 0.52));
  const m = { l: 40, r: W < 480 ? 112 : 124, t: 10, b: 40 };
  const xs = s.values.map((v) => (mode === "despace" ? v * 1000 : v));
  const x = scale(xs[0], xs[xs.length - 1], m.l, W - m.r);
  const y = scale(0.1, 0.7, H - m.b, m.t);
  const lines =
    mode === "despace"
      ? [
          { d: s.centre_af, dash: undefined, c: "var(--ink)", lab: "centre, refocused" },
          { d: s.centre_fixed, dash: "6 4", c: "var(--ink)", lab: "centre, fixed" },
          { d: s.worst_af, dash: undefined, c: "var(--f-line)", lab: "corner, refocused" },
          { d: s.worst_fixed, dash: "6 4", c: "var(--f-line)", lab: "corner, fixed" },
        ]
      : [
          { d: s.centre_af, dash: undefined, c: "var(--ink)", lab: "centre" },
          { d: s.corners_af.map((r) => r[2]), dash: undefined, c: "var(--f-line)", lab: "lower corner" },
          { d: s.corners_af.map((r) => r[0]), dash: undefined, c: "var(--carmine)", lab: "upper corner" },
        ];
  const xt = mode === "despace" ? ticks(0, 12, 3) : ticks(0, 0.2, 0.05);
  // keep end labels apart
  const ends = lines.map((l) => ({ ...l, ly: y(l.d[l.d.length - 1]) }));
  ends.sort((a, b) => a.ly - b.ly);
  for (let i = 1; i < ends.length; i++) if (ends[i].ly - ends[i - 1].ly < 14) ends[i].ly = ends[i - 1].ly + 14;
  return (
    <div ref={ref}>
      <svg className="chart" width={W} height={H} role="img" aria-label="MTF at 111.6 lp/mm against the error">
        <g className="grid">{ticks(0.1, 0.7, 0.1).map((t) => <line key={t} x1={m.l} x2={W - m.r} y1={y(t)} y2={y(t)} />)}</g>
        <g className="axis">
          {ticks(0.1, 0.7, 0.1).map((t) => <text key={t} x={m.l - 8} y={y(t) + 4} textAnchor="end">{t.toFixed(1)}</text>)}
          {xt.map((t) => <text key={t} x={x(t)} y={H - m.b + 18} textAnchor="middle">{mode === "despace" ? t : t.toFixed(2)}</text>)}
          <text className="axis-label" x={W - m.r} y={H - 4} textAnchor="end">{mode === "despace" ? "L1 to L2 spacing error (µm)" : "Image-plane tilt (deg)"}</text>
        </g>
        {/* corner spec */}
        <line x1={m.l} x2={W - m.r} y1={y(spec.corner_min)} y2={y(spec.corner_min)} stroke="var(--carmine)" strokeWidth="1" strokeDasharray="2 3" />
        <text x={m.l + 4} y={y(spec.corner_min) + 14} style={{ fill: "var(--carmine)" }}>corner spec {spec.corner_min.toFixed(3)}</text>
        {lines.map((l) => (
          <path key={l.lab} d={linePath(xs.map((v, i) => [x(v), y(l.d[i])]))} fill="none" stroke={l.c} strokeWidth="2" strokeDasharray={l.dash} strokeLinecap="round" />
        ))}
        {ends.map((l) => <text key={l.lab} x={W - m.r + 6} y={l.ly + 4} className="lbl">{l.lab}</text>)}
        <line x1={x(at)} x2={x(at)} y1={m.t} y2={H - m.b} stroke="var(--carmine)" strokeWidth="1" />
        {lines.map((l) => <circle key={l.lab} cx={x(at)} cy={y(interp(xs, l.d, at))} r="4" fill={l.c} stroke="var(--paper)" strokeWidth="2" />)}
      </svg>
    </div>
  );
}

export function S2Focus({ data }: { data: Data }) {
  const s = data.summary;
  const v = data.validation;
  const [mode, setMode] = useState<"despace" | "tilt">("despace");
  const [pos, setPos] = useState(0); // 0..100
  const rows = mode === "despace" ? s.scrubs.rows.despace : s.scrubs.rows.sensor_tilt;
  const xs = rows.values.map((vv) => (mode === "despace" ? vv * 1000 : vv));
  const at = (pos / 100) * xs[xs.length - 1];
  const dsp = s.scrubs.rows.despace;
  const last = dsp.values.length - 1;

  const tiles =
    mode === "despace"
      ? [
          { label: "Centre, refocused", mtf: interp(xs, rows.centre_af, at) },
          { label: "Centre, focus fixed", mtf: interp(xs, rows.centre_fixed, at) },
        ]
      : [
          { label: "Upper corner, refocused", mtf: interp(xs, rows.corners_af.map((r) => r[0]), at) },
          { label: "Lower corner, refocused", mtf: interp(xs, rows.corners_af.map((r) => r[2]), at), flip: true },
        ];

  return (
    <Step
      n={2}
      id="s2"
      title="Autofocus fixes spacing, not tilt"
      copy={
        <>
          Refocus recovers a 12 µm spacing error: centre MTF <b>{dsp.centre_af[last].toFixed(2)} with refocus, {dsp.centre_fixed[last].toFixed(2)} without</b>. Tilt splits the corners, and refocus can't help:{" "}
          <b>{v.tilt_hand_calc.tilt_to_reach_dof_deg_diagonal.toFixed(2)}° moves the corner a full depth of focus</b> (±{v.tilt_hand_calc.depth_of_focus_um.toFixed(1)} µm at F/1.49).
        </>
      }
      details={
        <>
          <div className="scroll-x">
            <h4>Scrub curves, MTF at 111.6 lp/mm</h4>
            <table>
              <thead><tr><th className="num">Spacing error (µm)</th><th className="num">Centre, refocused</th><th className="num">Centre, fixed</th><th className="num">Worst corner, refocused</th><th className="num">Worst corner, fixed</th></tr></thead>
              <tbody>
                {dsp.values.map((vv, i) => i % 2 === 0 && (
                  <tr key={i}><td className="num">{(vv * 1000).toFixed(1)}</td><td className="num">{dsp.centre_af[i].toFixed(3)}</td><td className="num">{dsp.centre_fixed[i].toFixed(3)}</td><td className="num">{dsp.worst_af[i].toFixed(3)}</td><td className="num">{dsp.worst_fixed[i].toFixed(3)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <p>
            Under tilt the worst corner falls almost linearly (fitted exponent {s.scrubs.rows.sensor_tilt.exponent_worst_corner?.toFixed(2)}): one corner sharpens while the opposite one blurs. Only the mean of the four corners is close to quadratic (exponent{" "}
            {s.scrubs.rows.sensor_tilt.exponent_mean_of_corners?.toFixed(2)}). Hand calculation: corner shift = y<sub>corner</sub> tan&theta;, depth of focus = ±2&lambda;N&sup2;. Focus is the only compensator modelled; active alignment would recover much of the tilt loss.
          </p>
          <p>The edge tiles are rendered from the traced MTF, as the Gaussian blur with the same MTF at 111.6 lp/mm, over a 16 µm patch of the sensor.</p>
        </>
      }
    >
      <div className="focus-grid">
        <div>
          <div className="switch" role="group" aria-label="Error type">
            <button aria-pressed={mode === "despace"} onClick={() => { setMode("despace"); }}>Spacing error</button>
            <button aria-pressed={mode === "tilt"} onClick={() => { setMode("tilt"); }}>Image-plane tilt</button>
          </div>
          <div className="scrub">
            <label htmlFor="scrub">{mode === "despace" ? "L1 to L2 air gap error" : "Image-plane tilt"}</label>
            <input id="scrub" type="range" min={0} max={100} step={1} value={pos} onChange={(e) => setPos(+e.target.value)} />
            <output htmlFor="scrub">{mode === "despace" ? `${at.toFixed(1)} µm` : `${at.toFixed(3)}°`}</output>
          </div>
          <div className="legend">
            <span><LineKey /> refocused</span>
            {mode === "despace" && <span><LineKey dash="6 4" /> focus fixed at nominal</span>}
          </div>
          <ScrubChart s={rows} mode={mode} at={at} spec={s.spec.thresholds} />
        </div>
        <div className="tiles">
          {tiles.map((t) => <EdgeTile key={t.label} {...t} />)}
        </div>
      </div>
    </Step>
  );
}
