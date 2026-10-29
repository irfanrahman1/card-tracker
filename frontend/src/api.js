// All calls to the backend live here. Paths start with /api, which Vite
// forwards to FastAPI during development (see vite.config.js).

async function request(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    // FastAPI puts error messages in "detail" (a string, or a list for validation errors).
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((d) => d.msg).join("; ");
    } catch {
      /* response wasn't JSON; keep the generic message */
    }
    throw new Error(message);
  }
  return res.status === 204 ? null : res.json();
}

const json = (method, body) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  // Cards
  listCards: () => request("/api/cards"),
  createCard: (card) => request("/api/cards", json("POST", card)),
  updateCard: (id, card) => request(`/api/cards/${id}`, json("PUT", card)),
  deleteCard: (id) => request(`/api/cards/${id}`, { method: "DELETE" }),
  catalog: () => request("/api/cards/catalog"),
  addFromCatalog: (catalogId) => request(`/api/cards/from-catalog/${catalogId}`, { method: "POST" }),

  // Purchases
  listTransactions: (month, category) => {
    const params = new URLSearchParams();
    if (month) params.set("month", month);
    if (category) params.set("category", category);
    return request(`/api/transactions?${params}`);
  },
  // Link purchases with no card to this card.
  assignCard: (cardId) => request("/api/transactions/assign-card", json("POST", { card_id: cardId })),
  // Change a purchase's category (also fixes that merchant's other purchases).
  updateTransaction: (id, changes) => request(`/api/transactions/${id}`, json("PATCH", changes)),
  addTransaction: (tx) => request("/api/transactions", json("POST", tx)),
  deleteTransaction: (id) => request(`/api/transactions/${id}`, { method: "DELETE" }),
  uploadCsv: (file, cardId) => {
    const form = new FormData();
    form.append("file", file);
    if (cardId) form.append("card_id", cardId);
    return request("/api/transactions/upload", { method: "POST", body: form });
  },

  // Insights
  summary: (month) => request(`/api/summary${month ? `?month=${month}` : ""}`),
  trend: () => request("/api/summary/trend"),
  recommend: ({ amount, category, merchant }) => {
    const params = new URLSearchParams({ amount });
    if (category) params.set("category", category);
    if (merchant) params.set("merchant", merchant);
    return request(`/api/recommend?${params}`);
  },

  // Wallet optimizer. Pass { spending, point_value } for a what-if, or nothing for your real data.
  optimize: (whatIf = {}) => request("/api/optimizer", json("POST", whatIf)),

  // Demo
  loadDemo: () => request("/api/demo/load", { method: "POST" }),
  clearAll: () => request("/api/demo/clear", { method: "POST" }),
};
