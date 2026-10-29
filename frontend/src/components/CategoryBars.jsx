import { CATEGORIES, categoryColor, money } from "../categories.js";

// Horizontal bar per category for one month. Every bar is labeled with its
// amount and share, so the color is never the only way to read it.
// A category can be negative if refunds/credits outweigh spending; its bar is empty.
export default function CategoryBars({ byCategory, total }) {
  const max = Math.max(...Object.values(byCategory), 0);
  return (
    <div className="cat-rows">
      {CATEGORIES.map((c) => {
        const value = byCategory[c.id] ?? 0;
        const pct = total > 0 && value > 0 ? Math.round((value / total) * 100) : 0;
        return (
          <div className="cat-row" key={c.id} title={`${c.label}: ${money(value)} (${pct}% of month)`}>
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
            </div>
          </div>
        );
      })}
    </div>
  );
}
