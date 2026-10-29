import { useEffect, useState } from "react";
import { api } from "../api.js";
import { CATEGORIES, categoryColor, categoryLabel, money } from "../categories.js";

// "Which card should I use?" Type a store and amount; results update as you type.
export default function BestCard({ dataVersion, goTo, notify }) {
  const [merchant, setMerchant] = useState("");
  const [amount, setAmount] = useState("50");
  const [category, setCategory] = useState(""); // "" = guess from the store name
  const [result, setResult] = useState(null);

  useEffect(() => {
    const value = parseFloat(amount);
    if (!(value > 0) || (!merchant.trim() && !category)) {
      setResult(null);
      return;
    }
    // Wait until typing pauses before asking the server.
    const timer = setTimeout(() => {
      api
        .recommend({ amount: value, category, merchant: merchant.trim() })
        .then(setResult)
        .catch((err) => notify(err.message, "error"));
    }, 250);
    return () => clearTimeout(timer);
  }, [merchant, amount, category, dataVersion, notify]);

  return (
    <div className="grid two">
      <section className="panel">
        <div className="panel-head">
          <h2>Best card for this purchase</h2>
        </div>
        <div className="form-grid">
          <div className="field full">
            <label htmlFor="bc-merchant">Where are you buying?</label>
            <input
              id="bc-merchant"
              className="input"
              placeholder="e.g. Amazon, Whole Foods, Uber"
              value={merchant}
              onChange={(e) => setMerchant(e.target.value)}
              autoFocus
            />
          </div>
          <div className="field">
            <label htmlFor="bc-amount">Amount ($)</label>
            <input
              id="bc-amount"
              className="input num"
              type="number"
              inputMode="decimal"
              min="0"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="bc-category">Category</label>
            <select id="bc-category" className="select" value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">Auto-detect from store</option>
              {CATEGORIES.map((c) => (
                <option key={c.id} value={c.id}>{c.icon} {c.label}</option>
              ))}
            </select>
          </div>
        </div>
        <p className="muted small" style={{ marginBottom: 0 }}>
          Tip: Amazon always counts as shopping. Pick a category yourself if auto-detect guesses wrong.
        </p>
      </section>

      <section className="panel">
        {!result && (
          <div className="empty">
            <div className="emoji">✨</div>
            <p>Enter a store (or pick a category) and an amount to see which card earns the most.</p>
          </div>
        )}

        {result && !result.best && (
          <div className="empty">
            <div className="emoji">💳</div>
            <p>You don't have any cards yet. Add one, or load the demo data.</p>
            <button className="btn primary" onClick={() => goTo("cards")}>Add a card</button>
          </div>
        )}

        {result?.best && (
          <>
            <div className="panel-head">
              <h2>Recommendation</h2>
              <span className="chip">
                <span className="swatch" style={{ background: categoryColor(result.category) }} />
                {categoryLabel(result.category)}
              </span>
            </div>
            <div className="reco-best">
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="small" style={{ color: "var(--good)", fontWeight: 650 }}>USE THIS CARD</div>
                <div style={{ fontSize: 19, fontWeight: 700 }}>{result.best.card_name}</div>
                <div className="small muted">{result.best.reason}</div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div className="big num">{money(result.best.reward)}</div>
                <div className="small muted">back on {money(result.amount)}</div>
              </div>
            </div>
            {result.options.length > 1 && (
              <div className="list">
                {result.options.slice(1).map((o, i) => (
                  <div className="list-row" key={o.card_id} style={{ gridTemplateColumns: "auto 1fr auto" }}>
                    <span className="reco-rank">{i + 2}</span>
                    <div className="row-main">
                      <div className="row-title">{o.card_name}</div>
                      <div className="row-meta">{o.reason}</div>
                    </div>
                    <div className="row-amount num">{money(o.reward)}</div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
