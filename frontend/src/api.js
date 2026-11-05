// All calls to the backend live here. Paths start with /api, which Vite
// forwards to FastAPI during development (see vite.config.js).

// Fired when the server says "please log in" (expired session, logged out elsewhere),
// so the app can show the login screen.
export const AUTH_REQUIRED = "auth-required";

async function request(path, options = {}) {
  // The login cookie is sent automatically: same address as the website.
  const res = await fetch(path, { credentials: "same-origin", ...options });
  if (res.status === 401 && !path.startsWith("/api/auth/")) {
    window.dispatchEvent(new Event(AUTH_REQUIRED));
  }
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
  // Account
  me: () => request("/api/auth/me"),
  signup: (email, password) => request("/api/auth/signup", json("POST", { email, password })),
  login: (email, password) => request("/api/auth/login", json("POST", { email, password })),
  logout: () => request("/api/auth/logout", { method: "POST" }),
  tryDemo: () => request("/api/auth/demo", { method: "POST" }),
  changePassword: (current_password, new_password) =>
    request("/api/auth/change-password", json("POST", { current_password, new_password })),
  deleteAccount: (password) => request("/api/auth/delete-account", json("POST", { password })),

  // Cards
  listCards: () => request("/api/cards"),
  createCard: (card) => request("/api/cards", json("POST", card)),
  updateCard: (id, card) => request(`/api/cards/${id}`, json("PUT", card)),
  deleteCard: (id) => request(`/api/cards/${id}`, { method: "DELETE" }),
  catalog: () => request("/api/cards/catalog"),
  addFromCatalog: (catalogId, choice) =>
    request(`/api/cards/from-catalog/${catalogId}${choice ? `?choice=${choice}` : ""}`, { method: "POST" }),

  // Purchases
  // card: a card id, "none" (no card), or "all"/empty for every card.
  listTransactions: (month, category, card) => {
    const params = new URLSearchParams();
    if (month) params.set("month", month);
    if (category) params.set("category", category);
    if (card && card !== "all") params.set("card", card);
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
  summary: (month, card) => {
    const params = new URLSearchParams();
    if (month) params.set("month", month);
    if (card && card !== "all") params.set("card", card);
    return request(`/api/summary?${params}`);
  },
  trend: (card) => request(`/api/summary/trend${card && card !== "all" ? `?card=${card}` : ""}`),
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
