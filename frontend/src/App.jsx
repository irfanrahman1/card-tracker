import { useCallback, useEffect, useState } from "react";
import { AUTH_REQUIRED, api } from "./api.js";
import AccountMenu from "./components/AccountMenu.jsx";
import AuthScreen from "./components/AuthScreen.jsx";
import Overview from "./components/Overview.jsx";
import BestCard from "./components/BestCard.jsx";
import Purchases from "./components/Purchases.jsx";
import Cards from "./components/Cards.jsx";
import Optimizer from "./components/Optimizer.jsx";

const TABS = [
  { id: "overview", label: "Overview", icon: "📊" },
  { id: "best", label: "Best card", icon: "✨" },
  { id: "optimize", label: "Optimize", icon: "🎯" },
  { id: "purchases", label: "Purchases", icon: "🧾" },
  { id: "cards", label: "Cards", icon: "💳" },
];

export default function App() {
  // undefined = still checking, null = logged out, object = logged-in user
  const [user, setUser] = useState(undefined);
  const [tab, setTab] = useState("overview");
  // Bumped after any change to the data; views re-fetch when it changes.
  const [dataVersion, setDataVersion] = useState(0);
  const [toast, setToast] = useState(null);
  const [backendUp, setBackendUp] = useState(true);

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

  // Who's logged in? And go back to the login screen if the session ends.
  useEffect(() => {
    api.me().then(setUser).catch(() => setUser(null));
    const onLoggedOut = () => setUser(null);
    window.addEventListener(AUTH_REQUIRED, onLoggedOut);
    return () => window.removeEventListener(AUTH_REQUIRED, onLoggedOut);
  }, []);

  // Check the backend is reachable, so a stopped server shows a clear message.
  useEffect(() => {
    fetch("/api/health")
      .then((r) => setBackendUp(r.ok))
      .catch(() => setBackendUp(false));
  }, [dataVersion, user]);

  const signedIn = (u) => {
    setUser(u);
    setTab("overview");
    refresh();
  };

  const loadDemo = async () => {
    try {
      const res = await api.loadDemo();
      notify(
        res.transactions_added
          ? `Loaded ${res.cards} sample cards and ${res.transactions_added} purchases`
          : "Sample data is already loaded"
      );
      refresh();
    } catch (err) {
      notify(err.message, "error");
    }
  };

  const backendBanner = !backendUp && (
    <div className="banner" role="alert">
      <span>
        <strong>Can't reach the server.</strong> If you're running it yourself, start it with{" "}
        <code>./start.sh</code>.
      </span>
      <button className="btn small" onClick={refresh}>Retry</button>
    </div>
  );

  if (user === undefined) return <div className="app"><div className="panel muted" style={{ marginTop: 24 }}>Loading…</div></div>;

  if (!user) {
    return (
      <div className="app">
        {backendBanner}
        <AuthScreen onSignedIn={signedIn} />
      </div>
    );
  }

  // Props every view gets.
  const shared = { dataVersion, refresh, notify, loadDemo, goTo: setTab };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-logo" aria-hidden="true" />
          <h1>Card Tracker</h1>
        </div>
        <AccountMenu user={user} onLoggedOut={() => setUser(null)} refresh={refresh} notify={notify} />
      </header>

      {backendBanner}

      {user.is_demo && (
        <div className="demo-banner">
          <span>
            <strong>You're in a demo account</strong> with sample data. It's deleted after 24 hours.
          </span>
          <button className="btn small primary" onClick={() => api.logout().finally(() => setUser(null))}>
            Create your own account
          </button>
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
        {tab === "optimize" && <Optimizer {...shared} />}
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
