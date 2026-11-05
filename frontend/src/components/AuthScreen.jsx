import { useState } from "react";
import { api } from "../api.js";

// The first screen for anyone not logged in: what the app does, how data is
// protected, and log in / create account / try the demo.
export default function AuthScreen({ onSignedIn }) {
  const [mode, setMode] = useState("signup"); // "signup" | "login"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const run = async (action) => {
    setBusy(true);
    setError("");
    try {
      onSignedIn(await action());
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const submit = (e) => {
    e.preventDefault();
    run(() => (mode === "signup" ? api.signup(email, password) : api.login(email, password)));
  };

  return (
    <div className="auth">
      <section className="auth-pitch">
        <div className="brand">
          <div className="brand-logo" aria-hidden="true" />
          <h1>Card Tracker</h1>
        </div>
        <h2 className="auth-headline">Stop leaving credit card rewards on the table.</h2>
      </section>

      <section className="auth-details">
        <ul className="auth-points">
          <li><strong>See where your money goes</strong>, by category and store, across all your cards.</li>
          <li><strong>Know which card to use</strong> for every purchase.</li>
          <li><strong>Find a better card setup</strong> for how you actually spend, after fees.</li>
        </ul>
        <div className="auth-privacy">
          <div className="auth-privacy-title">🔒 Your data stays yours</div>
          <ul>
            <li>Only your email is needed. No card numbers, ever.</li>
            <li>Passwords are stored as one-way hashes (Argon2), never as text.</li>
            <li>Your data is private to your account and never sold or shared.</li>
            <li>Delete your account and everything in it anytime, in one click.</li>
          </ul>
        </div>
      </section>

      <section className="panel auth-form">
        <div className="auth-tabs" role="tablist">
          <button role="tab" aria-selected={mode === "signup"} className={mode === "signup" ? "active" : ""}
            onClick={() => { setMode("signup"); setError(""); }}>Create account</button>
          <button role="tab" aria-selected={mode === "login"} className={mode === "login" ? "active" : ""}
            onClick={() => { setMode("login"); setError(""); }}>Log in</button>
        </div>
        <form onSubmit={submit} className="grid" style={{ gap: 12 }}>
          <div className="field">
            <label htmlFor="auth-email">Email</label>
            <input id="auth-email" className="input" type="email" autoComplete="email" required
              value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="auth-password">Password</label>
            <div className="password-row">
              <input id="auth-password" className="input" type={showPassword ? "text" : "password"} required
                minLength={mode === "signup" ? 10 : undefined}
                autoComplete={mode === "signup" ? "new-password" : "current-password"}
                value={password} onChange={(e) => setPassword(e.target.value)} />
              <button type="button" className="btn ghost small" onClick={() => setShowPassword((s) => !s)}>
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
            {mode === "signup" && <span className="small muted">At least 10 characters. A short sentence works well.</span>}
          </div>
          {error && <div className="notice bad" style={{ marginTop: 0 }} role="alert">{error}</div>}
          <button className="btn primary" disabled={busy}>
            {busy ? "One moment…" : mode === "signup" ? "Create account" : "Log in"}
          </button>
        </form>
        <div className="auth-or"><span>or</span></div>
        <button className="btn" style={{ width: "100%" }} disabled={busy} onClick={() => run(api.tryDemo)}>
          ⚡ Try the demo, no sign-up
        </button>
        <p className="small muted" style={{ marginBottom: 0, textAlign: "center" }}>
          The demo uses sample data and is deleted after 24 hours.
        </p>
      </section>
    </div>
  );
}
