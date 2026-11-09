import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

// Engineering-stage placeholder: loads the precomputed results so the build is exercised.
// The guided-story dashboard is designed in the next stage.
function App() {
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    fetch("/data/summary.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then(setSummary)
      .catch((e) => setError(String(e)));
  }, []);
  return (
    <main style={{ fontFamily: "system-ui, sans-serif", maxWidth: 760, margin: "2rem auto", padding: "0 1rem" }}>
      <h1>Lens tolerance yield</h1>
      <p>Precomputed results from a ray-traced Monte Carlo of a published phone lens.</p>
      {error && <p>Could not load results: {error}</p>}
      {summary && <pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>{JSON.stringify(summary, null, 1).slice(0, 4000)}</pre>}
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
