import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import Overview from "./components/Overview.jsx";
import BestCard from "./components/BestCard.jsx";
import Purchases from "./components/Purchases.jsx";
import Cards from "./components/Cards.jsx";

const TABS = [
  { id: "overview", label: "Overview", icon: "📊" },
  { id: "best", label: "Best card", icon: "✨" },
  { id: "purchases", label: "Purchases", icon: "🧾" },
  { id: "cards", label: "Cards", icon: "💳" },
];

export default function App() {
  const [tab, setTab] = useState("overview");
  // Bumped after any change to the data; views re-fetch when it changes.
  const [dataVersion, setDataVersion] = useState(0);
  const [toast, setToast] = useState(null);
  const [backendUp, setBackendUp] = useState(true);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => setDataVersion((v) => v + 1), []);

  // Small pop-up message at the bottom of the screen.
  const notify = useCallback((message, kind = "info") => {
    setToast({ message, kind, id: Date.now() });
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 3200);
    return () => clearTimeout(timer);
  }, [toast]);

  // Check the backend is reachable, so a stopped server shows a clear message.
  useEffect(() => {
    fetch("/api/health")
      .then((r) => setBackendUp(r.ok))
      .catch(() => setBackendUp(false));
  }, [dataVersion]);

  const loadDemo = async () => {
    setBusy(true);
    try {
      const res = await api.loadDemo();
      notify(
        res.transactions_added
          ? `Loaded ${res.cards} demo cards and ${res.transactions_added} purchases`
          : "Demo data is already loaded"
      );
      refresh();
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusy(false);
    }
  };

  const clearAll = async () => {
    if (!window.confirm("Delete ALL cards and purchases? This can't be undone.")) return;
    try {
      await api.clearAll();
      notify("All data cleared");
      refresh();
    } catch (err) {
      notify(err.message, "error");
    }
  };

  // Props every view gets.
  const shared = { dataVersion, refresh, notify, loadDemo, goTo: setTab };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-logo" aria-hidden="true" />
          <h1>Card Tracker</h1>
        </div>
        <div className="top-actions">
          <button className="btn primary" onClick={loadDemo} disabled={busy}>
            ⚡<span className="btn-label"> Load demo data</span>
          </button>
          <button className="btn ghost" onClick={clearAll} title="Clear all data">
            🗑️<span className="btn-label"> Clear</span>
          </button>
        </div>
      </header>

      {!backendUp && (
        <div className="banner" role="alert">
          <span>
            <strong>Can't reach the backend.</strong> Start it with{" "}
            <code>uvicorn app.main:app --reload</code> in the <code>backend</code> folder.
          </span>
          <button className="btn small" onClick={refresh}>Retry</button>
        </div>
      )}

      <nav className="tabs" aria-label="Sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`tab ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
            aria-current={tab === t.id ? "page" : undefined}
          >
            <span className="tab-icon" aria-hidden="true">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </nav>

      <main>
        {tab === "overview" && <Overview {...shared} />}
        {tab === "best" && <BestCard {...shared} />}
        {tab === "purchases" && <Purchases {...shared} />}
        {tab === "cards" && <Cards {...shared} />}
      </main>

      {toast && (
        <div key={toast.id} className={`toast ${toast.kind === "error" ? "error" : ""}`} role="status">
          {toast.message}
        </div>
      )}
    </div>
  );
}
