import { useState } from "react";
import { CATEGORIES, categoryColor, money, monthLabel, monthShort } from "../categories.js";

// Stacked columns: one column per month, one colored segment per category.
// Hover (or tap) a column for the breakdown; "Show table" gives the exact numbers.
export default function TrendChart({ data, selectedMonth, onSelectMonth }) {
  const [hover, setHover] = useState(null); // index of hovered column
  const [showTable, setShowTable] = useState(false);

  const months = data.slice(-6); // last six months keeps columns readable on phones
  const totals = months.map((m) => CATEGORIES.reduce((sum, c) => sum + m[c.id], 0));
  // Column height uses only positive amounts (a category net-negative from refunds has no segment).
  const heights = months.map((m) => CATEGORIES.reduce((sum, c) => sum + Math.max(m[c.id], 0), 0));
  const max = Math.max(...heights, 1);

  return (
    <div className="trend">
      <div className="trend-plot" onMouseLeave={() => setHover(null)}>
        {months.map((m, i) => {
          const visible = CATEGORIES.filter((c) => m[c.id] > 0);
          return (
            <div
              key={m.month}
              className={`trend-col ${m.month === selectedMonth ? "active" : ""}`}
              style={{ height: `${(heights[i] / max) * 100}%`, cursor: onSelectMonth ? "pointer" : "default" }}
              onMouseEnter={() => setHover(i)}
              onClick={() => onSelectMonth?.(m.month)}
              aria-label={`${monthLabel(m.month)}: ${money(totals[i])}`}
            >
              {visible.map((c, j) => (
                <div
                  key={c.id}
                  className={`trend-seg ${j === visible.length - 1 ? "top" : ""}`}
                  style={{ flex: `${m[c.id]} 1 0px`, background: categoryColor(c.id) }}
                />
              ))}
            </div>
          );
        })}
      </div>
      <div className="trend-x">
        {months.map((m) => (
          <span key={m.month} style={m.month === selectedMonth ? { color: "var(--text)", fontWeight: 650 } : null}>
            {monthShort(m.month)}
          </span>
        ))}
      </div>

      {hover !== null && months[hover] && (
        <div
          className="tooltip"
          style={{
            left: `clamp(0px, calc(${((hover + 0.5) / months.length) * 100}% - 90px), calc(100% - 190px))`,
            top: 0,
          }}
        >
          <div className="tooltip-title">
            {monthLabel(months[hover].month)} · <span className="num">{money(totals[hover])}</span>
          </div>
          {CATEGORIES.map((c) => (
            <div className="tooltip-row" key={c.id}>
              <span>
                <span className="swatch" style={{ background: categoryColor(c.id) }} />
                {c.label}
              </span>
              <span className="num">{money(months[hover][c.id])}</span>
            </div>
          ))}
        </div>
      )}

      <div className="legend">
        {CATEGORIES.map((c) => (
          <span key={c.id}>
            <span className="swatch" style={{ background: categoryColor(c.id) }} />
            {c.label}
          </span>
        ))}
        <button className="btn ghost small" style={{ marginLeft: "auto" }} onClick={() => setShowTable((s) => !s)}>
          {showTable ? "Hide table" : "Show table"}
        </button>
      </div>

      {showTable && (
        <div className="table-scroll">
          <table className="data-table num">
            <thead>
              <tr>
                <th>Month</th>
                {CATEGORIES.map((c) => <th key={c.id}>{c.label}</th>)}
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {months.map((m, i) => (
                <tr key={m.month}>
                  <td>{monthShort(m.month)}</td>
                  {CATEGORIES.map((c) => <td key={c.id}>{money(m[c.id])}</td>)}
                  <td><strong>{money(totals[i])}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
