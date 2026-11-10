import type { Data } from "../data";
import { num } from "../data";
import { LineKey, Step, linePath, scale, ticks, useWidth } from "../ui";

function MtfChart({ v }: { v: Data["validation"] }) {
  const [ref, W] = useWidth<HTMLDivElement>();
  const H = Math.min(380, Math.max(260, W * 0.5));
  const m = { l: 40, r: 70, t: 30, b: 40 };
  const h = v.nominal_mtf_vs_height;
  const xMax = 2.7;
  const x = scale(0, xMax, m.l, W - m.r);
  const y = scale(0, 1, H - m.b, m.t);
  const series = [
    { k: "sag_n4", dash: undefined, w: 2, c: "var(--ink)" },
    { k: "tan_n4", dash: "6 4", w: 2, c: "var(--ink)" },
    { k: "sag_n2", dash: undefined, w: 1.5, c: "var(--f-line)" },
    { k: "tan_n2", dash: "6 4", w: 1.5, c: "var(--f-line)" },
  ] as const;
  const dl = v.mtf_vs_diffraction.diffraction_limit;
  const corner = v.tilt_hand_calc.corner_image_height_mm;
  return (
    <div ref={ref}>
      <div className="legend">
        <span><LineKey /> Sagittal, 111.6 lp/mm</span>
        <span><LineKey dash="6 4" /> Tangential, 111.6 lp/mm</span>
        <span><LineKey color="var(--f-line)" width={1.5} /> Sagittal, 223.2 lp/mm</span>
        <span><LineKey color="var(--f-line)" width={1.5} dash="6 4" /> Tangential, 223.2 lp/mm</span>
        <span><LineKey dash="1 3" width={1.5} /> Diffraction limit</span>
      </div>
      <svg className="chart" width={W} height={H} role="img" aria-label="Nominal MTF against image height for the rebuilt lens">
        <g className="grid">
          {ticks(0, 1, 0.2).map((t) => <line key={t} x1={m.l} x2={W - m.r} y1={y(t)} y2={y(t)} />)}
        </g>
        <g className="axis">
          {ticks(0, 1, 0.2).map((t) => <text key={t} x={m.l - 8} y={y(t) + 4} textAnchor="end">{t.toFixed(1)}</text>)}
          {ticks(0, 2.5, 0.5).map((t) => <text key={t} x={x(t)} y={H - m.b + 18} textAnchor="middle">{t.toFixed(1)}</text>)}
          <line x1={m.l} x2={W - m.r} y1={y(0)} y2={y(0)} />
          <text className="axis-label" x={W - m.r} y={H - 4} textAnchor="end">Image height (mm)</text>
          <text className="axis-label" x={m.l - 8} y={m.t - 16} textAnchor="start">MTF</text>
        </g>
        {/* corner of the evaluated field */}
        <line x1={x(corner)} x2={x(corner)} y1={y(1)} y2={y(0)} stroke="var(--rule)" />
        <text x={x(corner) + 4} y={y(0.97)}>0.7-field corner, {corner.toFixed(2)} mm</text>
        {dl.map((d, i) => (
          <g key={i}>
            <line x1={m.l} x2={W - m.r} y1={y(d)} y2={y(d)} stroke={i ? "var(--f-line)" : "var(--ink)"} strokeWidth="1.5" strokeDasharray="1 3" />
            <text x={W - m.r + 6} y={y(d) + 4} className="lbl">{d.toFixed(2)}</text>
          </g>
        ))}
        {series.map((s) => (
          <path key={s.k} d={linePath(h.img_ht_mm.map((t, i) => [x(t), y(h[s.k][i])]))} fill="none" stroke={s.c} strokeWidth={s.w} strokeDasharray={s.dash} strokeLinejoin="round" strokeLinecap="round" />
        ))}
      </svg>
    </div>
  );
}

export function S1Lens({ data }: { data: Data }) {
  const v = data.validation;
  const fo = v.first_order;
  const maxEl = Math.max(...v.element_focal_lengths.map((e) => Math.abs(e.err_pct)));
  return (
    <Step
      n={1}
      id="s1"
      title="A real lens, rebuilt"
      copy={
        <>
          A published six-element F/1.49 phone lens, ray-traced from the patent tables. Focal length <b>{fo.efl_mm.rebuilt.toFixed(3)} mm vs {fo.efl_mm.published.toFixed(2)}</b> published, track length{" "}
          <b>{fo.ttl_mm.rebuilt.toFixed(3)} vs {fo.ttl_mm.published.toFixed(2)}</b>, all six element focal lengths within {maxEl.toFixed(1)}%.
        </>
      }
      details={
        <>
          <div className="scroll-x">
            <h4>First-order checks</h4>
            <table>
              <thead><tr><th>Quantity</th><th className="num">Rebuilt</th><th className="num">Published</th><th className="num">Error</th></tr></thead>
              <tbody>
                <tr><td>Effective focal length (mm)</td><td className="num">{fo.efl_mm.rebuilt}</td><td className="num">{fo.efl_mm.published}</td><td className="num">{num(fo.efl_mm.err_pct)}%</td></tr>
                <tr><td>Total track length (mm)</td><td className="num">{fo.ttl_mm.rebuilt}</td><td className="num">{fo.ttl_mm.published}</td><td className="num">{num(fo.ttl_mm.err_pct)}%</td></tr>
                <tr><td>Entrance pupil diameter (mm)</td><td className="num">{fo.epd_mm.rebuilt}</td><td className="num">{fo.epd_mm.published_from_ratio}</td><td className="num">{num((100 * (fo.epd_mm.rebuilt - fo.epd_mm.published_from_ratio)) / fo.epd_mm.published_from_ratio)}%</td></tr>
                {v.element_focal_lengths.map((e) => (
                  <tr key={e.element}><td>{e.element} focal length (mm)</td><td className="num">{e.optiland}</td><td className="num">{e.published}</td><td className="num">{num(e.err_pct)}%</td></tr>
                ))}
                <tr><td>F-number (follows from the EFL; not an independent check)</td><td className="num">{fo.fno.rebuilt}</td><td className="num">{fo.fno.published}</td><td className="num">{num(fo.fno.err_pct)}%</td></tr>
              </tbody>
            </table>
          </div>
          <div className="scroll-x">
            <h4>Field curves and distortion against the patent's own plots</h4>
            <table>
              <thead><tr><th className="num">Image height (mm)</th><th className="num">Tangential (mm)</th><th className="num">Patent</th><th className="num">Sagittal (mm)</th><th className="num">Patent</th><th className="num">Distortion</th><th className="num">Patent</th></tr></thead>
              <tbody>
                {v.fig2_comparison.rows.map((r) => (
                  <tr key={r.img_ht}><td className="num">{r.img_ht}</td><td className="num">{num(r.tan_mm, 3)}</td><td className="num">{num(r.tan_patent)}</td><td className="num">{num(r.sag_mm, 3)}</td><td className="num">{num(r.sag_patent)}</td><td className="num">+{r.distortion_pct.toFixed(1)}%</td><td className="num">+{r.distortion_patent.toFixed(1)}%</td></tr>
                ))}
              </tbody>
            </table>
            <p style={{ marginTop: 8 }}>Patent values read by eye from its figure (about ±0.01 mm, ±0.4%). Distortion is referenced to the paraxial chief-ray height.</p>
          </div>
          <div className="scroll-x">
            <h4>Diffraction limit and the tilt hand calculation</h4>
            <table>
              <tbody>
                <tr><td>Nominal centre MTF, 111.6 / 223.2 lp/mm</td><td className="num">{v.mtf_vs_diffraction.nominal_centre.join(" / ")}</td></tr>
                <tr><td>Diffraction limit at F/1.49, 111.6 / 223.2 lp/mm</td><td className="num">{v.mtf_vs_diffraction.diffraction_limit.join(" / ")}</td></tr>
                <tr><td>Depth of focus, ±2&lambda;N&sup2;</td><td className="num">±{v.tilt_hand_calc.depth_of_focus_um} &micro;m</td></tr>
                {v.tilt_hand_calc.rows.map((r) => (
                  <tr key={r.theta_deg}><td>Corner shift at {r.theta_deg}&deg; tilt: hand calc vs traced</td><td className="num">{r.hand_calc_um} vs {r.traced_um} &micro;m</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      }
    >
      <MtfChart v={v} />
      <div className="caption">Nominal design, autofocus at best focus, polychromatic MTF from the traced wavefront. Frequencies are a quarter and half of the 1.12 &micro;m pixel Nyquist.</div>
    </Step>
  );
}
