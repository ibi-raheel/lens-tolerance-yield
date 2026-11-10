import type { Data } from "../data";
import { signed } from "../data";
import { Step, scale, ticks, useWidth } from "../ui";

const pretty = (g: string) => g.replace("image-plane tilt", "Image-plane tilt").replace("barrel decenter", "Barrel decenter").replace("spacing", "Air-gap spacing");

function Bars({ s }: { s: Data["summary"] }) {
  const [ref, W] = useWidth<HTMLDivElement>();
  const rows = s.drivers.rows;
  const narrow = W < 560;
  const labelW = narrow ? 118 : 150;
  const bandH = 22, barH = 14;
  const m = { l: labelW, r: narrow ? 46 : 250, t: 24, b: 30 };
  const H = m.t + rows.length * bandH + m.b;
  const x = scale(0, 0.3, m.l, W - m.r);
  const spot = s.drivers.spot_checks.find((c) => c.groups.length === 3)!;
  const top3y0 = m.t, top3y1 = m.t + 3 * bandH;
  return (
    <div ref={ref}>
      <svg className="chart" width={W} height={H} role="img" aria-label="Share of yield loss by part group">
        <g className="grid">{ticks(0, 0.3, 0.1).map((t) => <line key={t} x1={x(t)} x2={x(t)} y1={m.t - 6} y2={H - m.b} />)}</g>
        {ticks(0, 0.3, 0.1).map((t) => <text key={t} x={x(t)} y={H - m.b + 18} textAnchor="middle">{Math.round(t * 100)}%</text>)}
        <text className="axis-label" x={W - m.r} y={m.t - 10} textAnchor="end">Share of yield loss</text>
        {rows.map((r, i) => {
          const yy = m.t + i * bandH + (bandH - barH) / 2;
          const top = i < 3;
          const w = Math.max(0, x(r.share_of_loss) - x(0));
          return (
            <g key={r.group}>
              <text x={m.l - 10} y={yy + barH - 3} textAnchor="end" className={top ? "lbl-strong" : undefined}>{pretty(r.group)}</text>
              {w > 0 && (
                <path
                  d={`M${x(0)},${yy}h${Math.max(0, w - 4)}a4,4 0 0 1 4,4v${barH - 8}a4,4 0 0 1 -4,4h${-Math.max(0, w - 4)}z`}
                  fill={top ? "var(--carmine)" : "var(--ink)"}
                  opacity={top ? 1 : 0.7}
                >
                  <title>{`${r.group}: ${(100 * r.share_of_loss).toFixed(1)}% of the loss, ${signed(r.recovered_pts)} pts if perfect`}</title>
                </path>
              )}
              {(top || i < 6) && <text x={x(r.share_of_loss) + 6} y={yy + barH - 3} className="lbl">{(100 * r.share_of_loss).toFixed(1)}%</text>}
            </g>
          );
        })}
        {/* direct re-trace of the top three */}
        {!narrow && (
          <g>
            <path d={`M${x(0.27)},${top3y0 + 3}h8v${top3y1 - top3y0 - 6}h-8`} fill="none" stroke="var(--ink)" />
            <text x={x(0.27) + 16} y={top3y0 + 18} className="lbl-strong">Re-traced, all three perfect</text>
            <text x={x(0.27) + 16} y={top3y0 + 36} className="lbl">{signed(spot.traced_recovered_pts)} ± {spot.traced_se_pts.toFixed(1)} pts</text>
            <text x={x(0.27) + 16} y={top3y0 + 54}>predicted {signed(spot.surrogate_recovered_pts)}</text>
          </g>
        )}
      </svg>
      {narrow && (
        <p className="caption" style={{ marginTop: 0 }}>
          Re-traced with all three perfect: <b style={{ color: "var(--ink)" }}>{signed(spot.traced_recovered_pts)} ± {spot.traced_se_pts.toFixed(1)} pts</b>, predicted {signed(spot.surrogate_recovered_pts)}.
        </p>
      )}
    </div>
  );
}

export function S4Drivers({ data }: { data: Data }) {
  const s = data.summary;
  const top3 = s.drivers.rows.slice(0, 3);
  const share = top3.reduce((a, r) => a + r.share_of_loss, 0);
  const spot3 = s.drivers.spot_checks.find((c) => c.groups.length === 3)!;
  const spot1 = s.drivers.spot_checks.find((c) => c.groups.length === 1)!;
  const sob = Object.entries(s.drivers.sobol_corner).sort((a, b) => b[1].ST - a[1].ST);
  return (
    <Step
      n={4}
      id="s4"
      title="What actually sets the yield"
      copy={
        <>
          L1 decenter, image-plane tilt and L5 decenter own <b>{Math.floor(100 * share)}% of the yield loss</b>, about 8 points each. A direct re-trace with all three perfect wins back{" "}
          <b>{signed(spot3.traced_recovered_pts)} ± {spot3.traced_se_pts.toFixed(1)} points</b>; the surrogate predicted {signed(spot3.surrogate_recovered_pts)}.
        </>
      }
      details={
        <>
          <p>
            Share of loss = yield recovered if that part group were perfect (every other tolerance at its current limit), scored by the surrogate on 60,000 sampled modules and divided by the sum over groups. Spot check by direct ray trace on 500 modules, L1 decenter alone:{" "}
            {signed(spot1.traced_recovered_pts)} ± {spot1.traced_se_pts.toFixed(1)} pts traced vs {signed(spot1.surrogate_recovered_pts)} predicted.
          </p>
          <div className="scroll-x">
            <h4>Sobol indices, worst-corner MTF</h4>
            <table>
              <thead><tr><th>Part group</th><th className="num">Total order S<sub>T</sub></th><th className="num">First order S<sub>1</sub></th></tr></thead>
              <tbody>
                {sob.slice(0, 10).map(([g, v]) => (
                  <tr key={g}><td>{pretty(g)}</td><td className="num">{v.ST.toFixed(3)}</td><td className="num">{Math.max(0, v.S1).toFixed(3)}</td></tr>
                ))}
              </tbody>
            </table>
            <p style={{ marginTop: 8 }}>Total order far above first order for the decenters and tilt: their cost is in interactions, which a one-at-a-time stack cannot see.</p>
          </div>
        </>
      }
    >
      <Bars s={s} />
    </Step>
  );
}
