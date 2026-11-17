// The Card Tracker logo: a small credit card with a stripe and a chip.
export default function Logo({ size = 28 }) {
  return (
    <svg width={size * 1.4} height={size} viewBox="0 0 42 30" aria-hidden="true" className="brand-logo">
      <defs>
        <linearGradient id="logo-gradient" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2a78d6" />
          <stop offset="1" stopColor="#6250d6" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="40" height="28" rx="6" fill="url(#logo-gradient)" />
      <rect x="1" y="8" width="40" height="5" fill="rgb(255 255 255 / 0.28)" />
      <rect x="7" y="18" width="8" height="6" rx="1.5" fill="#f2c94c" />
      <rect x="27" y="20" width="9" height="2.5" rx="1.25" fill="rgb(255 255 255 / 0.7)" />
    </svg>
  );
}
