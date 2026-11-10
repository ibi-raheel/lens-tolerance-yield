import { useEffect, useState } from "react";
import { loadData, type Data } from "./data";
import { S0Cover } from "./sections/S0Cover";
import { S1Lens } from "./sections/S1Lens";
import { S2Focus } from "./sections/S2Focus";
import { S3Population } from "./sections/S3Population";
import { S4Drivers } from "./sections/S4Drivers";
import { S5Ai } from "./sections/S5Ai";
import { S6Diagnosis } from "./sections/S6Diagnosis";
import { S7Budget } from "./sections/S7Budget";

const STEPS = [
  "Question, answer, solution",
  "A real lens, rebuilt",
  "Autofocus fixes spacing, not tilt",
  "6,000 modules (simulated)",
  "What sets the yield",
  "The AI vs the stack",
  "Which part is out?",
  "The reallocated budget",
];

function useActiveStep(ready: boolean) {
  const [active, setActive] = useState(0);
  useEffect(() => {
    if (!ready) return;
    const els = Array.from(document.querySelectorAll<HTMLElement>("[data-step]"));
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) if (e.isIntersecting) setActive(+(e.target as HTMLElement).dataset.step!);
      },
      { rootMargin: "-45% 0px -50% 0px" },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [ready]);
  return active;
}

function Rail({ active }: { active: number }) {
  return (
    <>
      <nav className="rail" aria-label="Steps">
        <ol>
          {STEPS.map((t, i) => (
            <li key={i}>
              <a href={`#s${i}`} aria-current={active === i ? "step" : undefined}>
                <span className="n">{i}</span>
                <span>{t}</span>
              </a>
            </li>
          ))}
        </ol>
      </nav>
      <nav className="rail-mobile" aria-label="Steps, compact">
        <div className="ticks">
          {STEPS.map((t, i) => (
            <a key={i} href={`#s${i}`} aria-label={t} aria-current={active === i ? "step" : undefined}>{i}</a>
          ))}
        </div>
        <span className="t">{STEPS[active]}</span>
      </nav>
    </>
  );
}

export default function App() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    loadData().then(setData).catch((e) => setError(String(e.message ?? e)));
  }, []);
  const active = useActiveStep(!!data);

  return (
    <>
      {data && <Rail active={active} />}
      <div className="sheet">
        <div className="masthead">
          <strong>Lens tolerance yield</strong>
          <span>Ray-traced Monte Carlo of a published six-element F/1.49 phone lens</span>
        </div>
        {error && (
          <div className="loading" role="alert">
            The precomputed results did not load ({error}). Reload the page; the data files live in <code>/data</code>.
          </div>
        )}
        {!data && !error && (
          <div className="loading" aria-busy="true">
            <div className="skel" /><div className="skel w2" /><div className="skel" />
          </div>
        )}
        {data && (
          <main>
            <S0Cover data={data} />
            <S1Lens data={data} />
            <S2Focus data={data} />
            <S3Population data={data} />
            <S4Drivers data={data} />
            <S5Ai data={data} />
            <S6Diagnosis data={data} />
            <S7Budget data={data} />
          </main>
        )}
        <footer className="colophon">
          <span className="more-work">More work at <a href="https://ibiraheel.com">ibiraheel.com</a></span>
          <span>Lens: US 9,435,983 B2, embodiment 1 (public patent text). Modules: physics simulation. Ray tracing: Optiland (MIT).</span>
        </footer>
      </div>
    </>
  );
}
