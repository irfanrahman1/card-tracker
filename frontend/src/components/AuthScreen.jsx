import { useEffect, useState } from "react";
import { api } from "../api.js";

// The first screen for anyone not logged in: what the app does, how data is
// protected, and log in / create account / try the demo.
export default function AuthScreen({ onSignedIn }) {
  // A reset link from the "forgot password" email looks like  https://site/?reset=TOKEN.
  // Read when this screen opens (not once per page load), since it's removed after use.
  const [resetToken] = useState(() => new URLSearchParams(window.location.search).get("reset"));
  // "signup" | "login" | "forgot" (ask for a reset link) | "reset" (choose a new password)
  const [mode, setMode] = useState(resetToken ? "reset" : "signup");
  const [info, setInfo] = useState("");
  // Seconds until "Resend email" can be clicked again (so the link can't be spammed).
  const [cooldown, setCooldown] = useState(0);
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);
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
    if (mode === "forgot") {
      setBusy(true);
      setError("");
      api.forgotPassword(email)
        .then((r) => {
          setInfo(`${r.message} Check your inbox and spam folder; the link works for 30 minutes.`);
          setCooldown(60);
        })
        .catch((err) => setError(err.message))
        .finally(() => setBusy(false));
      return;
    }
    if (mode === "reset") {
      run(async () => {
        const user = await api.resetPassword(resetToken, password);
        window.history.replaceState(null, "", window.location.pathname); // drop the token from the address bar
        return user;
      });
      return;
    }
    run(() => (mode === "signup" ? api.signup(email, password) : api.login(email, password)));
  };

  const switchTo = (next) => {
    setMode(next);
    setError("");
    setInfo("");
    setCooldown(0);
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
        {(mode === "forgot" || mode === "reset") ? (
          <div className="grid" style={{ gap: 6, marginBottom: 14 }}>
            <h2>{mode === "forgot" ? "Reset your password" : "Choose a new password"}</h2>
            <p className="small muted" style={{ margin: 0 }}>
              {mode === "forgot"
                ? "Enter your account's email and we'll send you a link to choose a new password."
                : "This logs you out on every other device."}
            </p>
          </div>
        ) : (
        <div className="auth-tabs" role="tablist">
          <button role="tab" aria-selected={mode === "signup"} className={mode === "signup" ? "active" : ""}
            onClick={() => switchTo("signup")}>Create account</button>
          <button role="tab" aria-selected={mode === "login"} className={mode === "login" ? "active" : ""}
            onClick={() => switchTo("login")}>Log in</button>
        </div>
        )}
        <form onSubmit={submit} className="grid" style={{ gap: 12 }}>
          {mode !== "reset" && (
          <div className="field">
            <label htmlFor="auth-email">Email</label>
            <input id="auth-email" className="input" type="email" autoComplete="email" required
              value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          )}
          {mode !== "forgot" && (
          <div className="field">
            <label htmlFor="auth-password">{mode === "reset" ? "New password" : "Password"}</label>
            <div className="password-row">
              <input id="auth-password" className="input" type={showPassword ? "text" : "password"} required
                minLength={mode === "login" ? undefined : 10}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                value={password} onChange={(e) => setPassword(e.target.value)} />
              <button type="button" className="btn ghost small" onClick={() => setShowPassword((s) => !s)}>
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
            {mode !== "login" && <span className="small muted">At least 10 characters. A short sentence works well.</span>}
            {mode === "login" && (
              <button type="button" className="link small forgot-link" onClick={() => switchTo("forgot")}>
                Forgot password?
              </button>
            )}
          </div>
          )}
          {error && <div className="notice bad" style={{ marginTop: 0 }} role="alert">{error}</div>}
          {info && <div className="notice good" style={{ marginTop: 0 }} role="status">{info}</div>}
          <button className="btn primary" disabled={busy || (mode === "forgot" && cooldown > 0)}>
            {busy
              ? "One moment…"
              : mode === "forgot" && info
                ? (cooldown > 0 ? `Resend email in ${cooldown}s` : "Resend email")
                : { signup: "Create account", login: "Log in", forgot: "Send reset link", reset: "Save new password" }[mode]}
          </button>
          {(mode === "forgot" || mode === "reset") && (
            <button type="button" className="btn ghost" onClick={() => switchTo("login")}>← Back to log in</button>
          )}
        </form>
        {(mode === "signup" || mode === "login") && (<>
        <div className="auth-or"><span>or</span></div>
        <button className="btn" style={{ width: "100%" }} disabled={busy} onClick={() => run(api.tryDemo)}>
          ⚡ Try the demo, no sign-up
        </button>
        <p className="small muted" style={{ marginBottom: 0, textAlign: "center" }}>
          The demo uses sample data and is deleted after 24 hours.
        </p>
        </>)}
      </section>
    </div>
  );
}
