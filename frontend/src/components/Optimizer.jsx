import { useEffect, useState } from "react";
import { api } from "../api.js";
import { CATEGORIES, categoryColor, categoryLabel, dollars, money } from "../categories.js";

const OPTIMIZED = CATEGORIES.filter((c) => c.id !== "fees"); // fees don't earn rewards

// "Am I using the right cards?" Yearly value of your wallet and the best cards to add,
// based on your real spending, with editable what-if numbers.
export default function Optimizer({ dataVersion, refresh, notify, goTo }) {
  const [result, setResult] = useState(null);
  const [spending, setSpending] = useState(null); // edited yearly numbers, or null = use real data
  const [pointValue, setPointValue] = useState("1");

  useEffect(() => {
    // Wait for typing to pause before recalculating.
    const timer = setTimeout(() => {
      const whatIf = { point_value: parseFloat(pointValue) || 1 };
      if (spending) {
        whatIf.spending = Object.fromEntries(Object.entries(spending).map(([k, v]) => [k, parseFloat(v) || 0]));
      }
      api.optimize(whatIf).then(setResult).catch((err) => notify(err.message, "error"));
    }, 300);
    return () => clearTimeout(timer);
  }, [spending, pointValue, dataVersion, notify]);

  if (!result) return <div className="panel muted">Calculating…</div>;

  const { current, add, best_single, best_pair, months_of_data } = result;
  const shown = spending ?? Object.fromEntries(OPTIMIZED.map((c) => [c.id, String(Math.round(result.spending[c.id] || 0))]));
  const hasCards = current.fees > 0 || current.rewards > 0 || Object.keys(current.per_category).length > 0;
  const noData = months_of_data === 0 && !spending;

  const addCard = async (catalogId, name) => {
    try {
      await api.addFromCatalog(catalogId);
      notify(`Added ${name} to your wallet`);
      refresh();
    } catch (err) {
      notify(err.message, "error");
    }
  };

  return (
    <div className="grid">
      {noData && (
        <div className="notice info" style={{ marginTop: 0 }}>
          No purchases yet, so these numbers are empty. Upload a statement, load the demo data, or type
          your yearly spending below to try it.
        </div>
      )}

      <div className="grid stats">
        <div className="panel">
          <div className="stat-label">Your cards earn per year</div>
          <div className={`stat-value num ${current.net < 0 ? "negative" : ""}`}>{money(current.net)}</div>
          <div className="stat-sub num">
            {money(current.rewards)} rewards − {money(current.fees)} fees
            {current.credits > 0 && <> + {money(current.credits)} perks</>}
          </div>
        </div>
        <div className="panel">
          <div className="stat-label">Best single card for you</div>
          <div className="stat-value small-value">{best_single?.cards[0].name ?? "—"}</div>
          <div className="stat-sub num">{best_single ? `${money(best_single.net)}/yr after fees` : ""}</div>
        </div>
        <div className="panel">
          <div className="stat-label">Best two-card combo</div>
          <div className="stat-value small-value">{best_pair ? best_pair.cards.map((c) => c.name).join(" + ") : "—"}</div>
          <div className="stat-sub num">{best_pair ? `${money(best_pair.net)}/yr after fees` : ""}</div>
        </div>
      </div>

      {hasCards && current.net < 0 && (
        <div className="notice bad" style={{ marginTop: 0 }}>
          At this spending, your annual fees cost more than your rewards. If you use your card's perks
          (airline, hotel or Uber credits), add their yearly value on the{" "}
          <button className="link" onClick={() => goTo("cards")}>Cards tab</button> to see the true picture.
        </div>
      )}

      <div className="grid two">
        <section className="panel">
          <div className="panel-head">
            <h2>Cards that would earn you more</h2>
          </div>
          {add.length === 0 ? (
            <p className="muted">No card in the catalog would add value at this spending. Nice wallet!</p>
          ) : (
            <div className="list">
              {add.map((a) => (
                <div className="list-row" key={a.card.key}>
                  <div className="row-main">
                    <div className="row-title">{a.card.name}</div>
                    <div className="row-meta">
                      <span>{a.card.annual_fee ? `${dollars(a.card.annual_fee)}/yr fee` : "No annual fee"}</span>
                      {a.card.notes && <span title={a.card.notes}>ⓘ {a.card.notes.slice(0, 60)}{a.card.notes.length > 60 ? "…" : ""}</span>}
                    </div>
                  </div>
                  <div className="row-amount num good-text">+{money(a.gain)}/yr</div>
                  <button className="btn small" onClick={() => addCard(a.card.key, a.card.name)}>Add</button>
                </div>
              ))}
            </div>
          )}
          <p className="small muted" style={{ marginBottom: 0 }}>
            Gains are after the new card's annual fee, and don't include sign-up bonuses or perks.
          </p>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>Which card to use for what</h2>
          </div>
          {Object.keys(current.per_category).length === 0 ? (
            <p className="muted">Add a card to see this.</p>
          ) : (
            <div className="list">
              {OPTIMIZED.filter((c) => current.per_category[c.id]).map((c) => {
                const row = current.per_category[c.id];
                return (
                  <div className="list-row" key={c.id}>
                    <div className="row-main">
                      <div className="row-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span className="swatch" style={{ background: categoryColor(c.id) }} />
                        {c.label}
                      </div>
                      <div className="row-meta">
                        {row.cards.map((u) => (
                          <span key={u.card + u.cents_per_dollar}>
                            {u.card} · {u.cents_per_dollar}¢/$
                            {row.cards.length > 1 && ` on ${dollars(u.spend)}`}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="row-amount num">{money(row.rewards)}/yr</div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>

      <section className="panel">
        <div className="panel-head">
          <h2>Your yearly spending</h2>
          {spending && (
            <button className="btn small" onClick={() => setSpending(null)}>Reset to my real spending</button>
          )}
        </div>
        <p className="small muted" style={{ marginTop: 0 }}>
          {spending
            ? "What-if mode: these are your numbers, not your purchases."
            : months_of_data > 0
              ? `From your last ${months_of_data} month${months_of_data === 1 ? "" : "s"} of purchases, scaled to a year. ` +
                "A one-off (like a big trip) gets multiplied too, so edit any number that looks off."
              : "Type yearly amounts to see which cards fit."}
        </p>
        <div className="spend-grid">
          {OPTIMIZED.map((c) => (
            <div className="field" key={c.id}>
              <label htmlFor={`sp-${c.id}`}>{c.icon} {categoryLabel(c.id)}</label>
              <input
                id={`sp-${c.id}`}
                className="input num"
                type="number"
                inputMode="decimal"
                min="0"
                step="100"
                value={shown[c.id] ?? "0"}
                onChange={(e) => setSpending({ ...shown, [c.id]: e.target.value })}
              />
            </div>
          ))}
          <div className="field">
            <label htmlFor="sp-pv">Value catalog points at (¢)</label>
            <input id="sp-pv" className="input num" type="number" inputMode="decimal" min="0.1" max="5" step="0.1"
              value={pointValue} onChange={(e) => setPointValue(e.target.value)} />
          </div>
        </div>
      </section>
    </div>
  );
}
