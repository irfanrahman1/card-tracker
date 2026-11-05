import { useEffect, useState } from "react";
import { api } from "../api.js";
import { CATEGORIES, categoryColor, money, prettyMerchant, shortDate } from "../categories.js";

// Horizontal bar per category for one month. Every bar is labeled with its
// amount and share, so the color is never the only way to read it.
// Tap a category to see its stores; tap a store to see each purchase.
// A category can be negative if refunds/credits outweigh spending; its bar is empty.
export default function CategoryBars({ byCategory, total, month, card, dataVersion }) {
  const [open, setOpen] = useState(null); // category id that's expanded
  const max = Math.max(...Object.values(byCategory), 0);
  return (
    <div className="cat-rows">
      {CATEGORIES.map((c) => {
        const value = byCategory[c.id] ?? 0;
        const pct = total > 0 && value > 0 ? Math.round((value / total) * 100) : 0;
        const isOpen = open === c.id;
        return (
          <div key={c.id} className={`cat-item ${isOpen ? "open" : ""}`}>
            <button
              className="cat-row"
              onClick={() => setOpen(isOpen ? null : c.id)}
              aria-expanded={isOpen}
              disabled={value === 0}
              title={`${c.label}: ${money(value)} (${pct}% of month)`}
            >
              <div className="cat-name">
                <span className="swatch" style={{ background: categoryColor(c.id) }} />
                {c.label}
              </div>
              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{ width: max && value > 0 ? `${(value / max) * 100}%` : 0, background: categoryColor(c.id) }}
                />
              </div>
              <div className="cat-amount num">
                {money(value)}
                <span className="cat-pct">{pct}%</span>
                <span className="chevron" aria-hidden="true">{value !== 0 ? (isOpen ? "▾" : "▸") : ""}</span>
              </div>
            </button>
            {isOpen && <CategoryDetail month={month} category={c.id} card={card} dataVersion={dataVersion} />}
          </div>
        );
      })}
    </div>
  );
}

// The stores in one category this month, biggest first. Tap a store for its purchases.
function CategoryDetail({ month, category, card, dataVersion }) {
  const [rows, setRows] = useState(null);
  const [openStore, setOpenStore] = useState(null);

  useEffect(() => {
    api.listTransactions(month, category, card).then(setRows).catch(() => setRows([]));
  }, [month, category, card, dataVersion]);

  if (!rows) return <div className="cat-detail muted small">Loading…</div>;

  // Group purchases by store.
  const stores = Object.values(
    rows.reduce((acc, r) => {
      const key = r.merchant.toLowerCase();
      acc[key] ??= { name: prettyMerchant(r.merchant), total: 0, items: [] };
      acc[key].total += r.amount;
      acc[key].items.push(r);
      return acc;
    }, {})
  ).sort((a, b) => b.total - a.total);

  return (
    <div className="cat-detail">
      {stores.map((s) => {
        const isOpen = openStore === s.name;
        const visits = s.items.filter((i) => i.amount > 0).length;
        return (
          <div key={s.name} className="store">
            <button className="store-row" onClick={() => setOpenStore(isOpen ? null : s.name)} aria-expanded={isOpen}>
              <span className="store-name">{s.name}</span>
              <span className="muted small">
                {visits} {visits === 1 ? "purchase" : "purchases"} · last {shortDate(s.items[0].date)}
              </span>
              <span className="num store-total">{money(s.total)}</span>
            </button>
            {isOpen && (
              <ul className="store-items">
                {s.items.map((i) => (
                  <li key={i.id}>
                    <span>{shortDate(i.date)}</span>
                    <span className="muted small">{i.description}</span>
                    <span className={`num ${i.amount < 0 ? "refund" : ""}`}>{money(i.amount)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}
