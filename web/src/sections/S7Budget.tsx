import type { BudgetRow, Data } from "../data";
import { REPO, num, pct } from "../data";
import { Step } from "../ui";

const fmt = (r: BudgetRow, v: number) => (r.unit === "mm" ? `${+(v * 1000).toFixed(2)} µm` : `${+v.toFixed(3)}°`);
const groupOf = (tol: string) => {
  const head = tol.split(" ")[0];
  if (head.startsWith("G")) return "Spacers";
  if (head === "Barrel") return "Barrel and holder";
  if (head === "Sensor") return "Sensor";
  return head;
};
const axis = (tol: string) => {
  const t = tol.split(" ")[1];
  return { dx: "decenter x", dy: "decenter y", tx: "tilt x", ty: "tilt y", ct: "centre thickness", gap: "air gap" }[t] ?? t;
};

function BudgetTable({ rows }: { rows: BudgetRow[] }) {
  const groups: [string, BudgetRow[]][] = [];
  for (const r of rows) {
    const g = groupOf(r.tol);
    if (!groups.length || groups[groups.length - 1][0] !== g) groups.push([g, []]);
    groups[groups.length - 1][1].push(r);
  }
  return (
    <table>
      <thead>
        <tr><th>Tolerance</th><th className="num">Current</th><th className="num">New</th><th className="num">Change</th></tr>
      </thead>
      <tbody>
        {groups.map(([g, rs]) => [
          <tr className="grp" key={g}>
            <td colSpan={4}>
              {g}
              {!/^L\d$/.test(g) && <span className="calls">{[...new Set(rs.map((r) => r.callout.replace(/^L\d-L\d /, "")))].join("; ")}</span>}
            </td>
          </tr>,
          ...rs.map((r) => {
            const cls = r.factor > 1 ? "loose" : r.factor < 1 ? "tight" : "";
            return (
              <tr key={r.tol} className={cls} title={r.callout}>
                <td>{g === "Spacers" ? r.callout.replace(" spacer / seat height", "") + " gap" : axis(r.tol)}</td>
                <td className="num">±{fmt(r, r.current)}</td>
                <td className="num">±{fmt(r, r.new)}</td>
                <td className="num chg">{r.factor === 1 ? "same" : r.factor > 1 ? `${+r.factor.toFixed(2)}× looser` : `tighten to ${+r.factor.toFixed(2)}×`}</td>
              </tr>
            );
          }),
        ])}
      </tbody>
    </table>
  );
}

export function S7Budget({ data }: { data: Data }) {
  const s = data.summary;
  const t = s.reallocation.table;
  const loose = t.filter((r) => r.factor > 1).length;
  const v = s.verification;
  const p = v.paired;
  const split = t.findIndex((r) => r.tol.startsWith("L5"));
  return (
    <Step
      n={7}
      id="s7"
      title="The solution: a reallocated budget"
      copy={
        <>
          <b>{loose} of {t.length} tolerances loosen and two tighten</b> (L1 decenter and L2 centre thickness), for a {Math.round(-s.reallocation.cost_change_pct)}% lower cost proxy. A fresh {v.n_new.toLocaleString()}-module Monte Carlo gives{" "}
          <b>{pct(v.new_budget_yield)} ± {(100 * v.new_budget_se).toFixed(1)} vs {pct(v.current_full_population_yield)} ± {(100 * v.current_full_population_se).toFixed(1)}</b> today, and a paired re-trace gives{" "}
          <b>{num(p.difference_pts, 1)} ± {p.difference_se_pts.toFixed(1)} pts</b>: yield holds within about 2 points.
        </>
      }
      details={
        <>
          <div className="scroll-x">
            <h4>Verification by ray trace</h4>
            <table>
              <tbody>
                <tr><td>Fresh, independent Monte Carlo on the new budget</td><td className="num">{pct(v.new_budget_yield)} ± {(100 * v.new_budget_se).toFixed(1)} (n = {v.n_new.toLocaleString()})</td></tr>
                <tr><td>Current budget, all simulated modules</td><td className="num">{pct(v.current_full_population_yield)} ± {(100 * v.current_full_population_se).toFixed(1)} (n = 6,000)</td></tr>
                <tr><td>Paired re-trace: same {p.n.toLocaleString()} held-out draws, new limits</td><td className="num">{num(p.difference_pts, 2)} ± {p.difference_se_pts.toFixed(2)} pts</td></tr>
                <tr><td>Paired 95% interval</td><td className="num">{num(p.difference_ci95_pts[0], 1)} to {num(p.difference_ci95_pts[1], 1)} pts</td></tr>
                <tr><td>Modules that flipped, fail to pass / pass to fail</td><td className="num">{p.flipped_to_pass} / {p.flipped_to_fail}</td></tr>
                <tr><td>Surrogate's aim (current to new)</td><td className="num">{pct(s.reallocation.current_yield_surrogate)} to {pct(s.reallocation.new_yield_surrogate)}</td></tr>
              </tbody>
            </table>
          </div>
          <p>Cost proxy = sum over the 41 tolerances of (current limit / new limit), so loosening one tolerance 2× halves its term. Only ray-traced yield is reported; the surrogate proposes, the ray trace decides. Most likely a small loss, within about 2 points.</p>
        </>
      }
    >
      <p className="caption" style={{ margin: "0 0 10px" }}>Drawing callouts, per element: decenter = OD-to-optical-axis concentricity + interlock fit; tilt = flange flatness / parallelism; centre thickness.</p>
      <div className="budget-key">
        <span><i />current and new limits, ± (2&sigma;)</span>
        <span><i className="t" />tightened</span>
      </div>
      <div className="budget">
        <BudgetTable rows={t.slice(0, split)} />
        <BudgetTable rows={t.slice(split)} />
      </div>
      <div className="close-links">
        <a href={`${REPO}/blob/main/SOLUTION.md`}>Playbook: week 1 on a module line &rarr;</a>
        <a href={`${REPO}/tree/main/tool`}>Tool: lensyield.py run / diagnose &rarr;</a>
        <a href={`${REPO}/blob/main/METHOD.md`}>Method and validation &rarr;</a>
      </div>
    </Step>
  );
}
