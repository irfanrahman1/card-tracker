import { useEffect, useState } from "react";
import { api } from "../api.js";
import { categoryLabel, money, monthLabel } from "../categories.js";
import CategoryBars from "./CategoryBars.jsx";
import TrendChart from "./TrendChart.jsx";

// Dashboard: totals for a month, spending by category, and the monthly trend,
// for all cards together or one card at a time.
export default function Overview({ dataVersion, refresh, loadDemo, goTo, notify }) {
  const [month, setMonth] = useState(null); // null = latest month with data
  const [summary, setSummary] = useState(null);
  const [trend, setTrend] = useState([]);
  const [card, setCard] = useState("all"); // "all", a card id, or "none"
  const [cards, setCards] = useState([]);

  useEffect(() => {
    Promise.all([api.summary(month, card), api.trend(card), api.listCards()])
      .then(([s, t, c]) => {
        setSummary(s);
        setTrend(t);
        setCards(c);
      })
      .catch((err) => notify(err.message, "error"));
  }, [month, card, dataVersion, notify]);

  // If the chosen card was deleted, go back to all cards.
  useEffect(() => {
    if (card !== "all" && card !== "none" && cards.length && !cards.some((c) => String(c.id) === card)) setCard("all");
  }, [cards, card]);

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
  const cardLabel = card === "none" ? "No card linked" : cards.find((c) => String(c.id) === card)?.name ?? "";
  // The side-by-side panel only helps when you have more than one card with purchases.
  const showByCard = card === "all" && summary.by_card.length > 1;

  return (
    <div className="grid">
      <div className="panel-head" style={{ marginBottom: 0 }}>
        <h2>
          {monthLabel(summary.month)}
          {card !== "all" && <span className="muted"> · {cardLabel}</span>}
        </h2>
        <div className="filters">
          <select className="select" value={card} onChange={(e) => setCard(e.target.value)} aria-label="Card">
            <option value="all">All cards</option>
            {cards.map((c) => <option key={c.id} value={String(c.id)}>{c.name}</option>)}
            {summary.without_card_total > 0 && <option value="none">No card linked</option>}
          </select>
          <select className="select" value={summary.month} onChange={(e) => setMonth(e.target.value)} aria-label="Month">
            {summary.months.map((m) => (
              <option key={m} value={m}>{monthLabel(m)}</option>
            ))}
          </select>
        </div>
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

      {showByCard && (
        <section className="panel">
          <div className="panel-head">
            <h2>By card</h2>
            <span className="muted small">Tap a card to see only its spending</span>
          </div>
          <div className="by-card">
            {summary.by_card.map((c) => {
              const share = summary.total > 0 ? Math.max(c.spent, 0) / summary.total : 0;
              return (
                <button key={c.card_id ?? "none"} className="by-card-row"
                  onClick={() => setCard(c.card_id ? String(c.card_id) : "none")}>
                  <span className="row-title">{c.name}</span>
                  <span className="muted small">{c.count} purchases</span>
                  <span className="bar-track"><span className="bar-fill by-card-fill" style={{ width: `${share * 100}%` }} /></span>
                  <span className="num by-card-spent">{money(c.spent)}</span>
                  <span className="num small good-text by-card-rewards">
                    {c.card_id ? `+${money(c.rewards)} rewards` : "no rewards counted"}
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      )}

      <div className="grid two">
        <section className="panel">
          <div className="panel-head">
            <h2>Spending by category</h2>
            <span className="muted small">Tap one to see where</span>
          </div>
          <CategoryBars byCategory={summary.by_category} total={summary.total} month={summary.month} card={card} dataVersion={dataVersion} />
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
