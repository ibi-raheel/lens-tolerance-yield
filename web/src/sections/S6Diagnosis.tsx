import type { Data } from "../data";
import { pct } from "../data";
import { Step } from "../ui";

const NAMES = ["C", "M+x", "M-x", "M+y", "M-y", "K++", "K-+", "K--", "K+-"];
const GRID = ["K-+", "M+y", "K++", "M-x", "C", "M+x", "K--", "M-y", "K+-"];
const LABEL: Record<string, string> = { C: "centre", "M+x": "0.5 field, +x", "M-x": "0.5 field, −x", "M+y": "0.5 field, +y", "M-y": "0.5 field, −y", "K++": "corner +x +y", "K-+": "corner −x +y", "K--": "corner −x −y", "K+-": "corner +x −y" };
const MAX = 0.72;

function FieldMap({ ex }: { ex: Data["summary"]["diagnosis"]["example"] }) {
  return (
    <div className="field-map" role="table" aria-label="Through-field MTF of the failing module against nominal, 111.6 lp/mm">
      {GRID.map((f) => {
        const i = NAMES.indexOf(f);
        const [T, S] = ex.mtf[i][0];
        const [nT, nS] = ex.nominal[i][0];
        return (
          <div key={f} className={`cell${f.startsWith("K") ? " corner" : ""}`} role="row">
            <div className="fname">{LABEL[f]}</div>
            {[["T", T, nT], ["S", S, nS]].map(([k, v, n]) => (
              <div className="bar-row" key={k as string}>
                <b>{k}</b>
                <div className="track">
                  <div className={`fill${(v as number) < (n as number) - 0.01 ? " down" : ""}`} style={{ width: `${(100 * (v as number)) / MAX}%` }} />
                  <div className="nom" style={{ left: `${(100 * (n as number)) / MAX}%` }} />
                </div>
                <span className="v">{(v as number).toFixed(2)}</span>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

export function S6Diagnosis({ data }: { data: Data }) {
  const d = data.summary.diagnosis;
  const ex = d.example;
  const pModel = ex.proba[ex.model] ?? 0;
  const recall = (cm: number[][]) => cm.map((r, i) => (r.reduce((a, b) => a + b, 0) ? r[i] / r.reduce((a, b) => a + b, 0) : NaN));
  const rm = recall(d.model.confusion), rl = recall(d.lookup.confusion);
  return (
    <Step
      n={6}
      id="s6"
      title="Which part is out?"
      copy={
        <>
          From a failing module's MTF test, the classifier names the out-of-spec part first time on <b>{Math.round(100 * d.model.top1)}% of held-out failures</b> ({Math.round(100 * d.model.top2)}% in its top two, out of {d.classes.length} parts). A signature lookup gets{" "}
          <b>{Math.round(100 * d.lookup.top1)}% / {Math.round(100 * d.lookup.top2)}%</b>.
        </>
      }
      details={
        <>
          <p>
            Paired bootstrap over the {d.n_test_failing} held-out failing modules (4,000 resamples, 95%): classifier top-1 {pct(d.intervals.model_top1[0], 0)} to {pct(d.intervals.model_top1[1], 0)}, lookup {pct(d.intervals.lookup_top1[0], 0)} to{" "}
            {pct(d.intervals.lookup_top1[1], 0)}, gap +{Math.round(100 * d.intervals.top1_difference[0])} to +{Math.round(100 * d.intervals.top1_difference[1])} points. Chance is {pct(d.chance_top1, 0)}. The classifier is an MLP on the 36 through-field MTF changes, trained on {d.n_train.toLocaleString()} simulated
            modules with one part out of spec; the lookup fits a library of {d.lookup.library_traces} traced signatures. Trained on single-part failures only.
          </p>
          <div className="scroll-x">
            <h4>Right first time, by true part</h4>
            <table>
              <thead><tr><th>True part</th><th className="num">Held-out failures</th><th className="num">Classifier</th><th className="num">Lookup</th></tr></thead>
              <tbody>
                {d.classes.map((c, i) => (
                  <tr key={c}><td>{c}</td><td className="num">{d.test_failing_counts[c]}</td><td className="num">{isNaN(rm[i]) ? "" : pct(rm[i], 0)}</td><td className="num">{isNaN(rl[i]) ? "" : pct(rl[i], 0)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      }
    >
      <div className="diag">
        <div>
          <FieldMap ex={ex} />
          <div className="caption">One held-out failing module, MTF at 111.6 lp/mm, tangential and sagittal, at the 9 test fields laid out as on the sensor. Tick = nominal design; carmine = below nominal.</div>
        </div>
        <div className="picks">
          <div className="pick">
            <div className="who">Out of spec on this module (known in simulation)</div>
            <div className="what">{ex.true}</div>
          </div>
          <div className="pick">
            <div className="who">Classifier's pick</div>
            <div className="what">{ex.model}</div>
            <div className="score">probability {pModel.toFixed(2)}, correct</div>
          </div>
          <div className="pick">
            <div className="who">Signature lookup's pick</div>
            <div className="what wrong">{ex.lookup}</div>
            <div className="score">wrong part</div>
          </div>
        </div>
      </div>
    </Step>
  );
}
