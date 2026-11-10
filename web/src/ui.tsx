import { useEffect, useRef, useState, type ReactNode } from "react";

/** Width of a container, for charts drawn in pixel units (text stays legible at 375px). */
export function useWidth<T extends HTMLElement>(initial = 640) {
  const ref = useRef<T>(null);
  const [w, setW] = useState(initial);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(260, Math.round(e.contentRect.width))));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

export const scale = (d0: number, d1: number, r0: number, r1: number) => (v: number) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);

export function ticks(d0: number, d1: number, step: number) {
  const out: number[] = [];
  for (let v = Math.ceil(d0 / step - 1e-9) * step; v <= d1 + 1e-9; v += step) out.push(+v.toFixed(6));
  return out;
}

export const linePath = (pts: [number, number][]) => pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join("");

export function Step({ n, id, title, tag, copy, children, details }: { n: number; id: string; title: string; tag?: string; copy: ReactNode; children: ReactNode; details?: ReactNode }) {
  return (
    <section className="step" id={id} data-step={n} aria-labelledby={`${id}-h`}>
      <div className="step-head">
        <span className="step-num" aria-hidden="true">{n}</span>
        <h2 id={`${id}-h`}>
          {title}
          {tag && <span className="sim-tag">{tag}</span>}
        </h2>
      </div>
      <p className="step-copy">{copy}</p>
      <div className="figure">{children}</div>
      {details && <Details>{details}</Details>}
    </section>
  );
}

export function Details({ children }: { children: ReactNode }) {
  return (
    <details className="more">
      <summary>
        <svg className="chev" viewBox="0 0 10 10" aria-hidden="true"><path d="M3 1.5 L7 5 L3 8.5" fill="none" stroke="currentColor" strokeWidth="1.4" /></svg>
        Show details
      </summary>
      <div className="body">{children}</div>
    </details>
  );
}

export function LineKey({ dash, color = "var(--ink)", width = 2 }: { dash?: string; color?: string; width?: number }) {
  return (
    <svg width="22" height="8" aria-hidden="true"><line x1="0" x2="22" y1="4" y2="4" stroke={color} strokeWidth={width} strokeDasharray={dash} /></svg>
  );
}
export function DotKey({ color }: { color: string }) {
  return (
    <svg width="10" height="10" aria-hidden="true"><circle cx="5" cy="5" r="4" fill={color} /></svg>
  );
}
