import { useEffect, useState } from "react";
import { api } from "../api.js";
import { categoryLabel, money, monthLabel } from "../categories.js";
import CategoryBars from "./CategoryBars.jsx";
import TrendChart from "./TrendChart.jsx";

// Dashboard: totals for a month, spending by category, and the monthly trend.
export default function Overview({ dataVersion, loadDemo, goTo, notify }) {
  const [month, setMonth] = useState(null); // null = latest month with data
  const [summary, setSummary] = useState(null);
  const [trend, setTrend] = useState([]);

  useEffect(() => {
    Promise.all([api.summary(month), api.trend()])
      .then(([s, t]) => {
        setSummary(s);
        setTrend(t);
      })
      .catch((err) => notify(err.message, "error"));
  }, [month, dataVersion, notify]);

  // After "Clear", the chosen month may no longer exist; fall back to latest.
  useEffect(() => {
    if (summary && month && !summary.months.includes(month) && summary.months.length) setMonth(null);
  }, [summary, month]);

  if (!summary) return <div className="panel muted">Loading…</div>;

  if (summary.months.length === 0) {
    return (
      <div className="panel empty">
        <div className="emoji">💳</div>
        <h2>No purchases yet</h2>
        <p>Load the demo data to see how it works, or add your own cards and purchases.</p>
        <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
          <button className="btn primary" onClick={loadDemo}>⚡ Load demo data</button>
          <button className="btn" onClick={() => goTo("cards")}>Add a card</button>
        </div>
      </div>
    );
  }

  // Biggest category this month, for the headline tile.
  const top = Object.entries(summary.by_category).sort((a, b) => b[1] - a[1])[0];
  const missed = summary.rewards_possible - summary.rewards_earned;

  return (
    <div className="grid">
      <div className="panel-head" style={{ marginBottom: 0 }}>
        <h2>{monthLabel(summary.month)}</h2>
        <select
          className="select"
          style={{ width: "auto" }}
          value={summary.month}
          onChange={(e) => setMonth(e.target.value)}
          aria-label="Month"
        >
          {summary.months.map((m) => (
            <option key={m} value={m}>{monthLabel(m)}</option>
          ))}
        </select>
      </div>

      <div className="grid stats">
        <div className="panel">
          <div className="stat-label">Total spent</div>
          <div className="stat-value num">{money(summary.total)}</div>
          <div className="stat-sub">
            {summary.count} purchases
            {summary.refunds > 0 && <> · <span className="num">{money(summary.refunds)}</span> refunds/credits</>}
          </div>
        </div>
        <div className="panel">
          <div className="stat-label">Top category</div>
          <div className="stat-value">{top && top[1] > 0 ? categoryLabel(top[0]) : "—"}</div>
          <div className="stat-sub num">{top ? money(top[1]) : ""}</div>
        </div>
        <div className="panel">
          <div className="stat-label">Rewards earned</div>
          {summary.with_card === 0 ? (
            <>
              <div className="stat-value">—</div>
              <div className="stat-sub">
                No purchases are linked to a card yet. Add your card, then pick it when uploading a CSV.
              </div>
            </>
          ) : (
            <>
              <div className="stat-value num">{money(summary.rewards_earned)}</div>
              <div className={`stat-sub ${missed > 0.005 ? "" : "good"}`}>
                {missed > 0.005
                  ? `${money(missed)} more possible with your best cards`
                  : "✓ You used your best card every time"}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="grid two">
        <section className="panel">
          <div className="panel-head">
            <h2>Spending by category</h2>
          </div>
          <CategoryBars byCategory={summary.by_category} total={summary.total} />
        </section>
        <section className="panel">
          <div className="panel-head">
            <h2>Monthly trend</h2>
            <span className="muted small">Tap a month to view it</span>
          </div>
          <TrendChart data={trend} selectedMonth={summary.month} onSelectMonth={setMonth} />
        </section>
      </div>
    </div>
  );
}
