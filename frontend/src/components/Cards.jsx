import { useEffect, useState } from "react";
import { api } from "../api.js";
import { CATEGORIES, categoryLabel, dollars, money } from "../categories.js";

// Background for each card tile, picked by position so cards look distinct.
const CARD_THEMES = [
  "linear-gradient(135deg, #1c5cab, #6250d6)",
  "linear-gradient(135deg, #2b2b2b, #585858)",
  "linear-gradient(135deg, #0e6b52, #1baf7a)",
  "linear-gradient(135deg, #a2431c, #eb6834)",
  "linear-gradient(135deg, #7a2952, #d55181)",
];

const blankForm = () => ({
  name: "", issuer: "", base_rate: "1", reward_type: "cash", point_value: "1",
  annual_fee: "0", credits_value: "0", catalog_id: null, rates: {}, caps: {},
});

const unit = (card) => (card.reward_type === "points" ? "x" : "%");

// List, add (from the catalog or by hand), edit and delete credit cards.
export default function Cards({ dataVersion, refresh, notify, loadDemo }) {
  const [cards, setCards] = useState(null);
  const [catalog, setCatalog] = useState([]);
  const [form, setForm] = useState(blankForm());
  const [editingId, setEditingId] = useState(null); // null = adding a new card
  const [mode, setMode] = useState(null); // null | "catalog" | "form"

  useEffect(() => {
    api.listCards().then(setCards).catch((err) => notify(err.message, "error"));
  }, [dataVersion, notify]);
  useEffect(() => {
    api.catalog().then(setCatalog).catch(() => {});
  }, []);

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const addFromCatalog = async (spec) => {
    try {
      const card = await api.addFromCatalog(spec.id);
      notify(`Added ${card.name}. Check the point value and perks you use.`);
      setMode(null);
      refresh();
    } catch (err) {
      notify(err.message, "error");
    }
  };

  const startCustom = () => {
    setForm(blankForm());
    setEditingId(null);
    setMode("form");
  };

  const startEdit = (card) => {
    setForm({
      name: card.name,
      issuer: card.issuer,
      base_rate: String(card.base_rate),
      reward_type: card.reward_type,
      point_value: String(card.point_value),
      annual_fee: String(card.annual_fee),
      credits_value: String(card.credits_value),
      catalog_id: card.catalog_id,
      rates: Object.fromEntries(card.rules.map((r) => [r.category, String(r.rate)])),
      caps: Object.fromEntries(card.rules.filter((r) => r.cap).map((r) => [r.category, String(r.cap)])),
    });
    setEditingId(card.id);
    setMode("form");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const submit = async (e) => {
    e.preventDefault();
    const num = (v, fallback = 0) => (isNaN(parseFloat(v)) ? fallback : parseFloat(v));
    // Only categories with a number filled in become rules; blank = base rate.
    const rules = Object.entries(form.rates)
      .filter(([, rate]) => rate !== "" && !isNaN(parseFloat(rate)))
      .map(([category, rate]) => ({
        category,
        rate: parseFloat(rate),
        cap: form.caps[category] ? num(form.caps[category], null) : null,
      }));
    const payload = {
      name: form.name.trim(),
      issuer: form.issuer.trim(),
      base_rate: num(form.base_rate),
      reward_type: form.reward_type,
      point_value: form.reward_type === "points" ? num(form.point_value, 1) : 1,
      annual_fee: num(form.annual_fee),
      credits_value: num(form.credits_value),
      catalog_id: form.catalog_id,
      rules,
    };
    try {
      if (editingId) await api.updateCard(editingId, payload);
      else await api.createCard(payload);
      notify(editingId ? "Card updated" : `Added ${payload.name}`);
      setMode(null);
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
  const ownedCatalogIds = new Set(cards.map((c) => c.catalog_id).filter(Boolean));
  const points = form.reward_type === "points";

  return (
    <div className="grid">
      <div className="panel-head" style={{ marginBottom: 0 }}>
        <h2>Your cards <span className="muted small">· {cards.length}</span></h2>
        {!mode && <button className="btn primary" onClick={() => setMode("catalog")}>+ Add card</button>}
      </div>

      {mode === "catalog" && (
        <section className="panel">
          <div className="panel-head">
            <h2>Pick your card</h2>
            <div className="filters">
              <button className="btn" onClick={startCustom}>My card isn't listed</button>
              <button className="btn ghost" onClick={() => setMode(null)}>Cancel</button>
            </div>
          </div>
          <div className="catalog-grid">
            {catalog.map((spec) => (
              <button
                key={spec.id}
                className="catalog-item"
                onClick={() => addFromCatalog(spec)}
                disabled={ownedCatalogIds.has(spec.id)}
              >
                <div className="catalog-top">
                  <span className="row-title">{spec.issuer} {spec.name}</span>
                  <span className="muted small num">{spec.annual_fee ? `${dollars(spec.annual_fee)}/yr` : "No fee"}</span>
                </div>
                <div className="row-meta">
                  {spec.rules.map((r) => (
                    <span className="chip" key={r.category}>
                      {r.rate}{spec.reward_type === "points" ? "x" : "%"} {categoryLabel(r.category).toLowerCase()}
                    </span>
                  ))}
                  <span className="chip">{spec.base_rate}{spec.reward_type === "points" ? "x" : "%"} else</span>
                </div>
                {ownedCatalogIds.has(spec.id) && <div className="small muted">Already in your wallet</div>}
              </button>
            ))}
          </div>
          <p className="small muted" style={{ marginBottom: 0 }}>
            Reward terms were checked in October 2026 and can change. Check your card's terms if something looks off.
          </p>
        </section>
      )}

      {mode === "form" && (
        <section className="panel">
          <div className="panel-head">
            <h2>{editingId ? "Edit card" : "Add a custom card"}</h2>
          </div>
          <form onSubmit={submit}>
            <div className="form-grid">
              <div className="field">
                <label htmlFor="c-name">Card name</label>
                <input id="c-name" className="input" required placeholder="e.g. Gold Card" value={form.name} onChange={set("name")} />
              </div>
              <div className="field">
                <label htmlFor="c-issuer">Issuer (optional)</label>
                <input id="c-issuer" className="input" placeholder="e.g. Amex" value={form.issuer} onChange={set("issuer")} />
              </div>
              <div className="field">
                <label htmlFor="c-type">Rewards are</label>
                <select id="c-type" className="select" value={form.reward_type} onChange={set("reward_type")}>
                  <option value="cash">Cash back (%)</option>
                  <option value="points">Points or miles (x per $)</option>
                </select>
              </div>
              {points ? (
                <div className="field">
                  <label htmlFor="c-pv">One point is worth (¢)</label>
                  <input id="c-pv" className="input num" type="number" inputMode="decimal" min="0.1" max="10" step="0.05"
                    value={form.point_value} onChange={set("point_value")} />
                </div>
              ) : <div />}
              <div className="field">
                <label htmlFor="c-base">Base reward on everything ({points ? "x" : "%"})</label>
                <input id="c-base" className="input num" type="number" inputMode="decimal" min="0" step="0.1"
                  value={form.base_rate} onChange={set("base_rate")} />
              </div>
              <div className="field">
                <label htmlFor="c-fee">Annual fee ($)</label>
                <input id="c-fee" className="input num" type="number" inputMode="decimal" min="0" step="1"
                  value={form.annual_fee} onChange={set("annual_fee")} />
              </div>
              <div className="field full">
                <label htmlFor="c-credits">Perks you actually use, per year ($)</label>
                <input id="c-credits" className="input num" type="number" inputMode="decimal" min="0" step="1"
                  value={form.credits_value} onChange={set("credits_value")} />
                <span className="small muted">
                  E.g. airline or Uber credits you'd spend anyway. Counted against the annual fee in Optimize.
                </span>
              </div>
            </div>
            {points && (
              <p className="small muted">
                Point value: 1¢ is a safe cash-like value. Transferring to airlines/hotels can be worth more (often 1.5–2¢).
              </p>
            )}
            <p className="small muted" style={{ margin: "16px 0 8px" }}>
              Bonus rates by category. Leave blank to use the base rate. Cap = yearly spend limit for that rate.
            </p>
            <div className="rule-grid">
              {CATEGORIES.filter((c) => c.id !== "fees").map((c) => (
                <div className="rule-row" key={c.id}>
                  <label htmlFor={`c-rate-${c.id}`}>{c.icon} {c.label}</label>
                  <input id={`c-rate-${c.id}`} className="input num" type="number" inputMode="decimal" min="0" step="0.1"
                    placeholder={`${form.base_rate || 0}${points ? "x" : "%"}`} value={form.rates[c.id] ?? ""}
                    onChange={(e) => setForm({ ...form, rates: { ...form.rates, [c.id]: e.target.value } })}
                    aria-label={`${c.label} rate`} />
                  <input className="input num" type="number" inputMode="decimal" min="0" step="100" placeholder="No cap"
                    value={form.caps[c.id] ?? ""}
                    onChange={(e) => setForm({ ...form, caps: { ...form.caps, [c.id]: e.target.value } })}
                    aria-label={`${c.label} yearly cap`} />
                </div>
              ))}
            </div>
            <div className="form-actions">
              <button type="button" className="btn" onClick={() => setMode(null)}>Cancel</button>
              <button className="btn primary">{editingId ? "Save changes" : "Add card"}</button>
            </div>
          </form>
        </section>
      )}

      {cards.length === 0 && !mode ? (
        <div className="panel empty">
          <div className="emoji">💳</div>
          <h2>No cards yet</h2>
          <p>Pick your cards from the list. Their reward rules fill in automatically.</p>
          <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
            <button className="btn primary" onClick={() => setMode("catalog")}>+ Add card</button>
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
                    <div className="cc-issuer">
                      {card.annual_fee ? `${dollars(card.annual_fee)}/yr` : "No annual fee"}
                      {card.reward_type === "points" && ` · points at ${card.point_value}¢`}
                      {card.credits_value > 0 && ` · ${dollars(card.credits_value)} perks`}
                    </div>
                  </div>
                  <div className="cc-chip" aria-hidden="true" />
                </div>
                <div className="cc-rates">
                  {card.rules
                    .slice()
                    .sort((a, b) => b.rate - a.rate)
                    .map((r) => (
                      <span className="cc-rate" key={r.category}>
                        {r.rate}{unit(card)} {categoryLabel(r.category).toLowerCase()}
                        {r.cap ? ` (to ${dollars(r.cap)})` : ""}
                      </span>
                    ))}
                  <span className="cc-rate">{card.base_rate}{unit(card)} everything else</span>
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
