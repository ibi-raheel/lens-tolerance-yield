import type { Data } from "../data";
import { REPO } from "../data";

// Rays are drawn at 588 nm and coloured by field, as an optical layout plot does;
// the three wavelengths overlap at this scale.
const FIELD_COLOR: Record<string, string> = { "0": "var(--f-line)", "0.5": "var(--d-line)", "0.7": "var(--c-line)" };
const TINTED = new Set([1, 5]); // L1 and L5: two of the three yield drivers; image-plane tilt is the third

function LensDrawing({ lens }: { lens: Data["figures"]["lens"] }) {
  // meridional section, mm. z right, y up.
  const z0 = -0.75, z1 = 5.1, y0 = -2.35, y1 = 2.45;
  const W = 640, H = (W * (y1 - y0)) / (z1 - z0);
  const sx = (z: number) => ((z - z0) / (z1 - z0)) * W;
  const sy = (y: number) => ((y1 - y) / (y1 - y0)) * H;
  const P = (p: number[]) => `${sx(p[0]).toFixed(1)},${sy(p[1]).toFixed(1)}`;

  const elems = [1, 2, 3, 4, 5, 6].map((e) => {
    const [front, back] = lens.surfaces.filter((s) => s.element === e);
    const d = `M${front.profile.map(P).join("L")}L${[...back.profile].reverse().map(P).join("L")}Z`;
    const zc = (front.z + back.z) / 2;
    const sd = Math.max(front.sd, back.sd);
    return { e, d, zc, sd };
  });
  const filt = lens.surfaces.filter((s) => s.element === 0);
  const stop = lens.surfaces.find((s) => s.name === "stop")!;
  const img = lens.surfaces.find((s) => s.name === "image")!;
  const fieldOrder = [0, 0.5, 0.7];

  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H.toFixed(0)}`} role="img" aria-label="Cross-section of the six-element lens with ray fans at centre, 0.5 and 0.7 field. L1, L5 and the image plane are tinted.">
      {/* optical axis */}
      <line x1={sx(z0)} x2={sx(z1)} y1={sy(0)} y2={sy(0)} stroke="var(--ink-3)" strokeWidth="0.6" strokeDasharray="10 3 2 3" />
      {/* rays under the glass outlines */}
      <g>
        {lens.rays.filter((r) => Math.abs(r.wl - 0.5876) < 1e-3).map((r, i) => (
          <polyline
            key={i}
            className="ray"
            pathLength={1}
            points={r.pts.map(P).join(" ")}
            stroke={FIELD_COLOR[String(r.field)]}
            style={{ animationDelay: `${fieldOrder.indexOf(r.field) * 90 + 120}ms` }}
          />
        ))}
      </g>
      {/* elements */}
      {elems.map(({ e, d, zc, sd }) => (
        <g key={e}>
          <path d={d} fill={TINTED.has(e) ? "var(--carmine-wash)" : "rgba(233,238,244,0.55)"} stroke={TINTED.has(e) ? "var(--carmine)" : "var(--ink)"} strokeWidth={TINTED.has(e) ? 1.3 : 1} strokeLinejoin="round" />
          <text x={sx(zc)} y={sy(-sd) + 20} textAnchor="middle" className={TINTED.has(e) ? "lbl-strong" : "lbl"} style={TINTED.has(e) ? { fill: "var(--carmine)" } : undefined}>
            L{e}
          </text>
        </g>
      ))}
      {/* IR filter */}
      <rect x={sx(filt[0].z)} y={sy(filt[1].sd)} width={sx(filt[1].z) - sx(filt[0].z)} height={sy(-filt[1].sd) - sy(filt[1].sd)} fill="rgba(233,238,244,0.55)" stroke="var(--ink-3)" strokeWidth="0.8" />
      <text x={(sx(filt[0].z) + sx(filt[1].z)) / 2} y={sy(-filt[1].sd) + 20} textAnchor="middle">filter</text>
      {/* aperture stop */}
      <line x1={sx(stop.z)} x2={sx(stop.z)} y1={sy(stop.sd)} y2={sy(stop.sd + 0.32)} stroke="var(--ink)" strokeWidth="2" />
      <text x={sx(stop.z)} y={sy(stop.sd + 0.32) - 8} textAnchor="middle">stop</text>
      {/* image plane */}
      <line x1={sx(img.z)} x2={sx(img.z)} y1={sy(img.sd + 0.1)} y2={sy(-img.sd - 0.1)} stroke="var(--carmine)" strokeWidth="2.5" />
      <text x={sx(img.z) - 4} y={sy(img.sd + 0.1) - 8} textAnchor="end" className="lbl-strong" style={{ fill: "var(--carmine)" }}>image plane</text>
      {/* scale bar: 1 mm */}
      <g transform={`translate(${sx(-0.6)},${sy(-2.12)})`}>
        <line x1="0" x2={sx(1) - sx(0)} y1="0" y2="0" stroke="var(--ink)" strokeWidth="1" />
        <line x1="0" x2="0" y1="-4" y2="4" stroke="var(--ink)" />
        <line x1={sx(1) - sx(0)} x2={sx(1) - sx(0)} y1="-4" y2="4" stroke="var(--ink)" />
        <text x={(sx(1) - sx(0)) / 2} y="-8" textAnchor="middle">1 mm</text>
      </g>
    </svg>
  );
}

export function S0Cover({ data }: { data: Data }) {
  const s = data.summary;
  const top3 = s.drivers.rows.slice(0, 3).reduce((a, r) => a + r.share_of_loss, 0);
  const rssGap = s.yield.A_limit_rss.error_pts;
  const loosened = s.reallocation.table.filter((r) => r.factor > 1).length;
  return (
    <header className="cover" id="s0" data-step={0}>
      <div>
        <h1>Which tolerances in a compact camera module actually set image-quality yield?</h1>
        <dl className="qas">
          <div>
            <dt>Answer</dt>
            <dd>
              Three tolerances own <span className="big mark">{Math.round(100 * top3)}%</span> of the yield loss. The standard RSS estimate overstates yield by{" "}
              <span className="big mark">{Math.round(rssGap)} points</span>.
            </dd>
          </div>
          <div>
            <dt>Solution</dt>
            <dd>
              Loosen <span className="big">{loosened} of {s.reallocation.table.length}</span> tolerances, tighten two, checked by a fresh ray-traced Monte Carlo.
              <div className="cta-row">
                <a href={`${REPO}/blob/main/SOLUTION.md`}>Playbook &rarr;</a>
                <a href={`${REPO}/tree/main/tool`}>Tool &rarr;</a>
              </div>
            </dd>
          </div>
        </dl>
      </div>
      <div className="lens-wrap">
        <LensDrawing lens={data.figures.lens} />
        <div className="lens-key">
          <span><i style={{ background: "var(--f-line)" }} />centre</span>
          <span><i style={{ background: "var(--d-line)" }} />0.5 field</span>
          <span><i style={{ background: "var(--c-line)" }} />0.7 field</span>
          <span><i className="tint" />the three yield drivers</span>
        </div>
      </div>
    </header>
  );
}
