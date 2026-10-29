// Display info for the five spending categories. Order matches the backend.
// Each category keeps the same color everywhere in the app (colors are set in styles.css).
export const CATEGORIES = [
  { id: "food", label: "Food", icon: "🍽️" },
  { id: "transportation", label: "Transportation", icon: "🚇" },
  { id: "groceries", label: "Groceries", icon: "🛒" },
  { id: "shopping", label: "Shopping", icon: "🛍️" },
  { id: "travel", label: "Travel", icon: "✈️" },
  { id: "subscriptions", label: "Subscriptions", icon: "🔁" },
  { id: "fees", label: "Card fees", icon: "🏦" },
  { id: "other", label: "Other", icon: "📦" },
];

// Whole dollars, for fees and yearly figures: "$895"
export const dollars = (n) =>
  Number(n).toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export const categoryLabel = (id) => CATEGORIES.find((c) => c.id === id)?.label ?? id;
export const categoryColor = (id) => `var(--cat-${id})`;

export const money = (n) =>
  Number(n).toLocaleString("en-US", { style: "currency", currency: "USD" });

// "2026-10" -> "October 2026"
export const monthLabel = (ym) => {
  const [y, m] = ym.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleString("en-US", { month: "long", year: "numeric" });
};

// "2026-10" -> "Oct"
export const monthShort = (ym) => {
  const [y, m] = ym.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleString("en-US", { month: "short" });
};

export const today = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

// Bank exports shout: "OZBEK HALAL F" -> "Ozbek Halal F". Mixed-case names are left alone.
export const prettyMerchant = (name = "") => {
  if (name !== name.toUpperCase()) return name;
  return name
    .toLowerCase()
    .replace(/(^|[\s\-/&(])([a-z])/g, (m, sep, ch) => sep + ch.toUpperCase())
    .replace(/\b(Llc|Inc|Usa|Nyc|Ny|Nj|Ca|Ma|Pa|Wa|De|Mta|Nyct|Omny|Path|Cvs|Bp)\b/g, (w) => w.toUpperCase());
};

export const shortDate = (iso) =>
  new Date(iso + "T00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" });
