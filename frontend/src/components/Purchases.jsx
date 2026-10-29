import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { CATEGORIES, categoryColor, categoryLabel, money, monthLabel, prettyMerchant, today } from "../categories.js";

const EMPTY_FORM = { date: today(), merchant: "", amount: "", category: "", card_id: "" };

// Add purchases by hand or from a CSV, and browse/delete them by month.
export default function Purchases({ dataVersion, refresh, notify }) {
  const [cards, setCards] = useState([]);
  const [rows, setRows] = useState([]);
  const [month, setMonth] = useState(""); // "" = all months
  const [category, setCategory] = useState(""); // "" = all categories
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.listCards().then(setCards).catch((err) => notify(err.message, "error"));
  }, [dataVersion, notify]);

  useEffect(() => {
    api.listTransactions(month, category).then(setRows).catch((err) => notify(err.message, "error"));
  }, [month, category, dataVersion, notify]);

  // Month choices come from all purchases, so we fetch once without a filter.
  const [months, setMonths] = useState([]);
  useEffect(() => {
    api.summary().then((s) => setMonths(s.months)).catch(() => {});
  }, [dataVersion]);

  const cardName = (id) => cards.find((c) => c.id === id)?.name;
  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const saved = await api.addTransaction({
        date: form.date,
        merchant: form.merchant,
        amount: parseFloat(form.amount),
        category: form.category || null,
        card_id: form.card_id ? Number(form.card_id) : null,
      });
      notify(`Added ${saved.merchant} as ${categoryLabel(saved.category)}`);
      setForm({ ...EMPTY_FORM, date: form.date, card_id: form.card_id });
      refresh();
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setSaving(false);
    }
  };

  // Fix a purchase's category. The backend also fixes this merchant's other
  // purchases and remembers it for future uploads.
  const recategorize = async (row, newCategory) => {
    try {
      const res = await api.updateTransaction(row.id, { category: newCategory });
      notify(
        res.updated > 1
          ? `Moved ${res.updated} purchases at ${prettyMerchant(res.merchant)} to ${categoryLabel(newCategory)}`
          : `Moved ${prettyMerchant(res.merchant)} to ${categoryLabel(newCategory)}`
      );
      refresh();
    } catch (err) {
      notify(err.message, "error");
    }
  };

  const remove = async (row) => {
    try {
      await api.deleteTransaction(row.id);
      notify(`Deleted ${row.merchant}`);
      refresh();
    } catch (err) {
      notify(err.message, "error");
    }
  };

  const total = rows.reduce((sum, r) => sum + r.amount, 0);

  return (
    <div className="grid">
      <div className="grid two">
        <section className="panel">
          <div className="panel-head">
            <h2>Add a purchase</h2>
          </div>
          <form onSubmit={submit}>
            <div className="form-grid">
              <div className="field full">
                <label htmlFor="p-merchant">Store / merchant</label>
                <input id="p-merchant" className="input" required placeholder="e.g. Trader Joe's"
                  value={form.merchant} onChange={set("merchant")} />
              </div>
              <div className="field">
                <label htmlFor="p-amount">Amount ($)</label>
                <input id="p-amount" className="input num" required type="number" inputMode="decimal"
                  min="0.01" step="0.01" placeholder="0.00" value={form.amount} onChange={set("amount")} />
              </div>
              <div className="field">
                <label htmlFor="p-date">Date</label>
                <input id="p-date" className="input" required type="date" value={form.date} onChange={set("date")} />
              </div>
              <div className="field">
                <label htmlFor="p-category">Category</label>
                <select id="p-category" className="select" value={form.category} onChange={set("category")}>
                  <option value="">Auto-detect</option>
                  {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.icon} {c.label}</option>)}
                </select>
              </div>
              <div className="field">
                <label htmlFor="p-card">Paid with</label>
                <select id="p-card" className="select" value={form.card_id} onChange={set("card_id")}>
                  <option value="">Not recorded</option>
                  {cards.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
            </div>
            <div className="form-actions">
              <button className="btn primary" disabled={saving}>{saving ? "Adding…" : "Add purchase"}</button>
            </div>
          </form>
        </section>

        <CsvUpload cards={cards} refresh={refresh} notify={notify} />
      </div>

      <section className="panel">
        <div className="panel-head">
          <h2>
            Purchases <span className="muted small num">· {rows.length} · {money(total)}</span>
          </h2>
          <div className="filters">
            <select className="select" value={category} onChange={(e) => setCategory(e.target.value)}
              aria-label="Filter by category">
              <option value="">All categories</option>
              {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.icon} {c.label}</option>)}
            </select>
            <select className="select" value={month} onChange={(e) => setMonth(e.target.value)}
              aria-label="Filter by month">
              <option value="">All months</option>
              {months.map((m) => <option key={m} value={m}>{monthLabel(m)}</option>)}
            </select>
          </div>
        </div>
        <p className="muted small" style={{ marginTop: 0 }}>
          Wrong category? Click it to change. The app updates that store's other purchases and remembers it for next time.
        </p>
        {rows.length === 0 ? (
          <p className="muted">No purchases{month || category ? " match these filters" : " yet"}.</p>
        ) : (
          <div className="list">
            {rows.map((r) => (
              <div className="list-row" key={r.id}>
                <div className="row-main">
                  <div className="row-title">{prettyMerchant(r.merchant)}</div>
                  <div className="row-meta">
                    <span>{new Date(r.date + "T00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>
                    <span className="chip">
                      <span className="swatch" style={{ background: categoryColor(r.category) }} />
                      <select
                        className="chip-select"
                        value={r.category}
                        onChange={(e) => recategorize(r, e.target.value)}
                        aria-label={`Category for ${r.merchant}`}
                      >
                        {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
                      </select>
                    </span>
                    {r.amount < 0 && <span className="refund">Refund / credit</span>}
                    {r.card_id && <span>{cardName(r.card_id)}</span>}
                    {r.description && <span>{r.description}</span>}
                  </div>
                </div>
                <div className={`row-amount num ${r.amount < 0 ? "refund" : ""}`}>{money(r.amount)}</div>
                <button className="btn ghost small" onClick={() => remove(r)} aria-label={`Delete ${r.merchant}`}>✕</button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

// CSV upload box: click or drag a file in.
function CsvUpload({ cards, refresh, notify }) {
  const inputRef = useRef(null);
  const [cardId, setCardId] = useState("");
  const [over, setOver] = useState(false);
  const [result, setResult] = useState(null);
  const [uploading, setUploading] = useState(false);

  const upload = async (file) => {
    if (!file) return;
    setUploading(true);
    setResult(null);
    try {
      const res = await api.uploadCsv(file, cardId);
      setResult({ ok: true, ...res });
      if (res.imported) refresh();
    } catch (err) {
      setResult({ ok: false, error: err.message });
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Upload a CSV</h2>
      </div>
      <div className="field" style={{ marginBottom: 12 }}>
        <label htmlFor="csv-card">Card for rows that don't name one</label>
        <select id="csv-card" className="select" value={cardId} onChange={(e) => setCardId(e.target.value)}>
          <option value="">None</option>
          {cards.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>
      <div
        className={`dropzone ${over ? "over" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); upload(e.dataTransfer.files[0]); }}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
      >
        <div style={{ fontSize: 26 }}>📄</div>
        <div><strong>{uploading ? "Uploading…" : "Choose a CSV file"}</strong> or drag it here</div>
        <div className="small muted">Needs columns: date, merchant (or description), amount</div>
      </div>
      <input ref={inputRef} type="file" accept=".csv,text/csv" hidden onChange={(e) => upload(e.target.files[0])} />

      {result?.ok && (
        <div className={`notice ${result.imported ? "good" : "info"}`}>
          {result.imported
            ? `Imported ${result.imported} purchase${result.imported === 1 ? "" : "s"}.`
            : "No new purchases found (already imported?)."}
          {result.skipped.length > 0 && (
            <>
              {" "}Skipped {result.skipped.length}:
              <ul>{result.skipped.slice(0, 5).map((s) => <li key={s}>{s}</li>)}</ul>
            </>
          )}
        </div>
      )}
      {result && !result.ok && <div className="notice bad">{result.error}</div>}
    </section>
  );
}
