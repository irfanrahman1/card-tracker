import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

// The account button in the top bar: who's logged in, sample data, password,
// deleting data, and logging out.
export default function AccountMenu({ user, onLoggedOut, refresh, notify }) {
  const [open, setOpen] = useState(false);
  const [dialog, setDialog] = useState(null); // null | "password" | "clear" | "delete"
  const menuRef = useRef(null);

  // Close the menu when clicking anywhere else.
  useEffect(() => {
    if (!open) return;
    const close = (e) => !menuRef.current?.contains(e.target) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const pick = (action) => {
    setOpen(false);
    action();
  };

  const logout = async () => {
    await api.logout().catch(() => {});
    onLoggedOut();
  };

  const loadSample = async () => {
    try {
      const res = await api.loadDemo();
      notify(res.transactions_added ? `Added ${res.transactions_added} sample purchases` : "Sample data is already loaded");
      refresh();
    } catch (err) {
      notify(err.message, "error");
    }
  };

  const label = user.is_demo ? "Demo account" : user.email;

  return (
    <div className="account" ref={menuRef}>
      <button className="btn account-button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-haspopup="menu">
        <span className="avatar" aria-hidden="true">{user.is_demo ? "⚡" : user.email[0].toUpperCase()}</span>
        <span className="account-email">{label}</span>
        <span aria-hidden="true">▾</span>
      </button>
      {open && (
        <div className="menu" role="menu">
          <div className="menu-head small muted">{label}</div>
          <button role="menuitem" onClick={() => pick(loadSample)}>⚡ Add sample data</button>
          {!user.is_demo && <button role="menuitem" onClick={() => pick(() => setDialog("password"))}>🔑 Change password</button>}
          <button role="menuitem" onClick={() => pick(() => setDialog("clear"))}>🗑️ Delete all my data</button>
          <button role="menuitem" className="danger" onClick={() => pick(() => setDialog("delete"))}>Delete account</button>
          <button role="menuitem" onClick={() => pick(logout)}>↩ Log out</button>
        </div>
      )}

      {dialog === "password" && <ChangePassword onClose={() => setDialog(null)} notify={notify} />}
      {dialog === "clear" && (
        <Confirm
          title="Delete all your data?"
          body="Removes every card, purchase and category fix in your account. Your account stays. This can't be undone."
          action="Delete my data"
          onClose={() => setDialog(null)}
          onConfirm={async () => {
            await api.clearAll();
            notify("All your data was deleted");
            refresh();
          }}
        />
      )}
      {dialog === "delete" && (
        <Confirm
          title="Delete your account?"
          body="Permanently deletes your account and everything in it. This can't be undone."
          action="Delete account"
          needsPassword={!user.is_demo}
          onClose={() => setDialog(null)}
          onConfirm={async (password) => {
            await api.deleteAccount(password);
            onLoggedOut();
          }}
        />
      )}
    </div>
  );
}

// A small pop-up asking "are you sure?", optionally with your password.
function Confirm({ title, body, action, needsPassword, onClose, onConfirm }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const go = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await onConfirm(password);
      onClose();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };
  return (
    <div className="overlay" onClick={onClose}>
      <form className="panel dialog" onClick={(e) => e.stopPropagation()} onSubmit={go} role="dialog" aria-modal="true">
        <h2>{title}</h2>
        <p className="muted">{body}</p>
        {needsPassword && (
          <div className="field">
            <label htmlFor="confirm-password">Your password</label>
            <input id="confirm-password" className="input" type="password" autoComplete="current-password" required
              autoFocus value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
        )}
        {error && <div className="notice bad" role="alert">{error}</div>}
        <div className="form-actions">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn danger-solid" disabled={busy}>{busy ? "Deleting…" : action}</button>
        </div>
      </form>
    </div>
  );
}

function ChangePassword({ onClose, notify }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.changePassword(current, next);
      notify("Password changed. Other devices were logged out.");
      onClose();
    } catch (err) {
      setError(err.message);
    }
  };
  return (
    <div className="overlay" onClick={onClose}>
      <form className="panel dialog" onClick={(e) => e.stopPropagation()} onSubmit={submit} role="dialog" aria-modal="true">
        <h2>Change password</h2>
        <div className="field">
          <label htmlFor="pw-current">Current password</label>
          <input id="pw-current" className="input" type="password" autoComplete="current-password" required autoFocus
            value={current} onChange={(e) => setCurrent(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="pw-new">New password (10+ characters)</label>
          <input id="pw-new" className="input" type="password" autoComplete="new-password" required minLength={10}
            value={next} onChange={(e) => setNext(e.target.value)} />
        </div>
        {error && <div className="notice bad" role="alert">{error}</div>}
        <div className="form-actions">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary">Change password</button>
        </div>
      </form>
    </div>
  );
}
