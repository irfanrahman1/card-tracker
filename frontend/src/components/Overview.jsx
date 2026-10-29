import { useEffect, useState } from "react";
import { api } from "../api.js";
import { categoryLabel, money, monthLabel } from "../categories.js";
import CategoryBars from "./CategoryBars.jsx";
import TrendChart from "./TrendChart.jsx";

// Dashboard: totals for a month, spending by category, and the monthly trend.
export default function Overview({ dataVersion, refresh, loadDemo, goTo, notify }) {
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
      <div className="grid">
        <SetupChecklist summary={summary} goTo={goTo} refresh={refresh} notify={notify} />
        <div className="panel empty">
          <div className="emoji">⚡</div>
          <h2>Just looking around?</h2>
          <p>Load sample cards and three months of made-up purchases to see how everything works.</p>
          <button className="btn primary" onClick={loadDemo}>⚡ Load demo data</button>
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

      <SetupChecklist summary={summary} goTo={goTo} refresh={refresh} notify={notify} />

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
            <span className="muted small">Tap one to see where</span>
          </div>
          <CategoryBars byCategory={summary.by_category} total={summary.total} month={summary.month} dataVersion={dataVersion} />
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

// Getting-started steps. Hidden once everything's set up.
function SetupChecklist({ summary, goTo, refresh, notify }) {
  const [cards, setCards] = useState([]);
  const [cardId, setCardId] = useState("");
  useEffect(() => {
    api.listCards().then((list) => {
      setCards(list);
      if (list.length) setCardId(String(list[0].id));
    }).catch(() => {});
  }, [summary]);

  const hasCards = summary.card_count > 0;
  const hasPurchases = summary.months.length > 0;
  const linked = hasPurchases && summary.without_card_total === 0;
  if (hasCards && hasPurchases && linked) return null;

  const link = async () => {
    try {
      const res = await api.assignCard(Number(cardId));
      notify(`Linked ${res.updated} purchases to your card`);
      refresh();
    } catch (err) {
      notify(err.message, "error");
    }
  };

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Get set up</h2>
        <span className="muted small">{[hasCards, hasPurchases, linked].filter(Boolean).length} of 3 done</span>
      </div>
      <div className="setup">
        <div className={`setup-step ${hasCards ? "done" : ""}`}>
          <span className="setup-num">{hasCards ? "✓" : 1}</span>
          <span className="setup-text">Add your credit cards (pick them from a list)</span>
          {!hasCards && <button className="btn small primary" onClick={() => goTo("cards")}>Add cards</button>}
        </div>
        <div className={`setup-step ${hasPurchases ? "done" : ""}`}>
          <span className="setup-num">{hasPurchases ? "✓" : 2}</span>
          <span className="setup-text">Upload your card's CSV export (or add purchases by hand)</span>
          {!hasPurchases && <button className="btn small primary" onClick={() => goTo("purchases")}>Upload CSV</button>}
        </div>
        <div className={`setup-step ${linked ? "done" : ""}`}>
          <span className="setup-num">{linked ? "✓" : 3}</span>
          <span className="setup-text">
            {hasPurchases && !linked
              ? `${summary.without_card_total} purchases aren't linked to a card, so rewards can't be counted. Link them to:`
              : "Link purchases to a card so rewards are counted"}
          </span>
          {hasPurchases && !linked && hasCards && (
            <>
              <select className="select" style={{ width: "auto" }} value={cardId} onChange={(e) => setCardId(e.target.value)}
                aria-label="Card to link purchases to">
                {cards.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <button className="btn small primary" onClick={link}>Link</button>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
