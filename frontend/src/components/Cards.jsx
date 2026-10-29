import { useEffect, useState } from "react";
import { api } from "../api.js";
import { CATEGORIES } from "../categories.js";

// Background for each card tile, picked by position so cards look distinct.
const CARD_THEMES = [
  "linear-gradient(135deg, #1c5cab, #6250d6)",
  "linear-gradient(135deg, #2b2b2b, #585858)",
  "linear-gradient(135deg, #0e6b52, #1baf7a)",
  "linear-gradient(135deg, #a2431c, #eb6834)",
  "linear-gradient(135deg, #7a2952, #d55181)",
];

const blankForm = () => ({ name: "", issuer: "", base_rate: "1", rates: {} });

// List, add, edit and delete credit cards and their reward rules.
export default function Cards({ dataVersion, refresh, notify, loadDemo }) {
  const [cards, setCards] = useState(null);
  const [form, setForm] = useState(blankForm());
  const [editingId, setEditingId] = useState(null); // null = adding a new card
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    api.listCards().then(setCards).catch((err) => notify(err.message, "error"));
  }, [dataVersion, notify]);

  const startAdd = () => {
    setForm(blankForm());
    setEditingId(null);
    setShowForm(true);
  };

  const startEdit = (card) => {
    setForm({
      name: card.name,
      issuer: card.issuer,
      base_rate: String(card.base_rate),
      rates: Object.fromEntries(card.rules.map((r) => [r.category, String(r.rate)])),
    });
    setEditingId(card.id);
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const submit = async (e) => {
    e.preventDefault();
    // Only categories with a number filled in become rules; blank = base rate.
    const rules = Object.entries(form.rates)
      .filter(([, rate]) => rate !== "" && !isNaN(parseFloat(rate)))
      .map(([category, rate]) => ({ category, rate: parseFloat(rate) }));
    const payload = {
      name: form.name.trim(),
      issuer: form.issuer.trim(),
      base_rate: parseFloat(form.base_rate) || 0,
      rules,
    };
    try {
      if (editingId) await api.updateCard(editingId, payload);
      else await api.createCard(payload);
      notify(editingId ? "Card updated" : `Added ${payload.name}`);
      setShowForm(false);
      refresh();
    } catch (err) {
      notify(err.message, "error");
    }
  };

  const remove = async (card) => {
    if (!window.confirm(`Delete ${card.name}? Its purchases stay, just without a card.`)) return;
    try {
      await api.deleteCard(card.id);
      notify(`Deleted ${card.name}`);
      refresh();
    } catch (err) {
      notify(err.message, "error");
    }
  };

  if (!cards) return <div className="panel muted">Loading…</div>;

  return (
    <div className="grid">
      <div className="panel-head" style={{ marginBottom: 0 }}>
        <h2>Your cards <span className="muted small">· {cards.length}</span></h2>
        {!showForm && <button className="btn primary" onClick={startAdd}>+ Add card</button>}
      </div>

      {showForm && (
        <section className="panel">
          <div className="panel-head">
            <h2>{editingId ? "Edit card" : "Add a card"}</h2>
          </div>
          <form onSubmit={submit}>
            <div className="form-grid">
              <div className="field">
                <label htmlFor="c-name">Card name</label>
                <input id="c-name" className="input" required placeholder="e.g. Gold Card"
                  value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </div>
              <div className="field">
                <label htmlFor="c-issuer">Issuer (optional)</label>
                <input id="c-issuer" className="input" placeholder="e.g. Amex"
                  value={form.issuer} onChange={(e) => setForm({ ...form, issuer: e.target.value })} />
              </div>
              <div className="field full">
                <label htmlFor="c-base">Base reward on everything (%)</label>
                <input id="c-base" className="input num" type="number" inputMode="decimal" min="0" step="0.1"
                  value={form.base_rate} onChange={(e) => setForm({ ...form, base_rate: e.target.value })} />
              </div>
            </div>
            <p className="small muted" style={{ margin: "16px 0 8px" }}>
              Bonus rates by category (%). Leave blank to use the base rate.
            </p>
            <div className="form-grid">
              {CATEGORIES.map((c) => (
                <div className="field" key={c.id}>
                  <label htmlFor={`c-rate-${c.id}`}>{c.icon} {c.label}</label>
                  <input
                    id={`c-rate-${c.id}`}
                    className="input num"
                    type="number"
                    inputMode="decimal"
                    min="0"
                    step="0.1"
                    placeholder={form.base_rate || "0"}
                    value={form.rates[c.id] ?? ""}
                    onChange={(e) => setForm({ ...form, rates: { ...form.rates, [c.id]: e.target.value } })}
                  />
                </div>
              ))}
            </div>
            <div className="form-actions">
              <button type="button" className="btn" onClick={() => setShowForm(false)}>Cancel</button>
              <button className="btn primary">{editingId ? "Save changes" : "Add card"}</button>
            </div>
          </form>
        </section>
      )}

      {cards.length === 0 && !showForm ? (
        <div className="panel empty">
          <div className="emoji">💳</div>
          <h2>No cards yet</h2>
          <p>Add your credit cards with their reward rates, or load the demo cards.</p>
          <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
            <button className="btn primary" onClick={startAdd}>+ Add card</button>
            <button className="btn" onClick={loadDemo}>⚡ Load demo data</button>
          </div>
        </div>
      ) : (
        <div className="cards-grid">
          {cards.map((card, i) => (
            <div className="cc" key={card.id} style={{ background: CARD_THEMES[i % CARD_THEMES.length] }}>
              <div>
                <div className="cc-top">
                  <div>
                    <div className="cc-name">{card.name}</div>
                    <div className="cc-issuer">{card.issuer || " "}</div>
                  </div>
                  <div className="cc-chip" aria-hidden="true" />
                </div>
                <div className="cc-rates">
                  {card.rules
                    .slice()
                    .sort((a, b) => b.rate - a.rate)
                    .map((r) => (
                      <span className="cc-rate" key={r.category}>
                        {r.rate}% {CATEGORIES.find((c) => c.id === r.category)?.label.toLowerCase()}
                      </span>
                    ))}
                  <span className="cc-rate">{card.base_rate}% everything else</span>
                </div>
              </div>
              <div className="cc-actions">
                <button className="btn small" onClick={() => startEdit(card)}>Edit</button>
                <button className="btn small" onClick={() => remove(card)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
