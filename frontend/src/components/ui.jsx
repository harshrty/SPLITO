// Shared UI primitives: inline icon set, avatars, badges, states.

const P = { fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round" };

const PATHS = {
  logo: <><path d="M12 2 4 6v6c0 5 3.4 8.3 8 10 4.6-1.7 8-5 8-10V6l-8-4Z" /><path d="M9 12h6M12 9v6" /></>,
  users: <><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></>,
  plus: <><path d="M12 5v14M5 12h14" /></>,
  arrowRight: <><path d="M5 12h14M12 5l7 7-7 7" /></>,
  arrowLeft: <><path d="M19 12H5M12 19l-7-7 7-7" /></>,
  check: <><path d="M20 6 9 17l-5-5" /></>,
  checkCircle: <><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><path d="m22 4-10 10.01-3-3" /></>,
  x: <><path d="M18 6 6 18M6 6l12 12" /></>,
  upload: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="M17 8l-5-5-5 5M12 3v12" /></>,
  receipt: <><path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z" /><path d="M8 7h8M8 11h8M8 15h5" /></>,
  scale: <><path d="M12 3v18M5 7h14M7 7l-3 6a3 3 0 0 0 6 0L7 7ZM17 7l-3 6a3 3 0 0 0 6 0l-3-6ZM4 21h16" /></>,
  wallet: <><path d="M20 12V8H6a2 2 0 0 1 0-4h12v4" /><path d="M4 6v12a2 2 0 0 0 2 2h14v-4" /><path d="M18 12a2 2 0 0 0 0 4h4v-4Z" /></>,
  coins: <><circle cx="8" cy="8" r="6" /><path d="M18.09 10.37A6 6 0 1 1 10.34 18M7 6h1v4M16.71 13.88l.7.71-2.82 2.82" /></>,
  handshake: <><path d="m11 17 2 2a1 1 0 1 0 3-3" /><path d="m14 14 2.5 2.5a1 1 0 1 0 3-3l-3.88-3.88a3 3 0 0 0-4.24 0l-.88.88a1 1 0 1 1-3-3l2.81-2.81a5.79 5.79 0 0 1 7.06-.87l.47.28a2 2 0 0 0 1.42.25L21 4" /><path d="M21 3v9M3 4l7.31 7.3a1 1 0 0 1 0 1.41l-2.6 2.6a1 1 0 0 1-1.41 0L3 12" /></>,
  logout: <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" /></>,
  sparkles: <><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6.3 6.3l2.4 2.4M15.3 15.3l2.4 2.4M17.7 6.3l-2.4 2.4M8.7 15.3l-2.4 2.4" /></>,
  shield: <><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" /><path d="m9 12 2 2 4-4" /></>,
  globe: <><circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10Z" /></>,
  alert: <><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" /><path d="M12 9v4M12 17h.01" /></>,
  folder: <><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2Z" /></>,
  chevronRight: <><path d="m9 18 6-6-6-6" /></>,
  info: <><circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" /></>,
  trendUp: <><path d="M23 6l-9.5 9.5-5-5L1 18" /><path d="M17 6h6v6" /></>,
};

export function Icon({ name, size = 18, className, style }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} className={className}
      style={{ display: "block", ...style }} {...P}>
      {PATHS[name] || null}
    </svg>
  );
}

// deterministic gradient avatar from a name
const AV_COLORS = [
  ["#8b5cf6", "#6d28d9"], ["#ec4899", "#be185d"], ["#f59e0b", "#d97706"],
  ["#10b981", "#059669"], ["#3b82f6", "#2563eb"], ["#06b6d4", "#0891b2"],
  ["#ef4444", "#dc2626"], ["#84cc16", "#65a30d"], ["#a855f7", "#7e22ce"],
  ["#14b8a6", "#0d9488"],
];
function hash(str = "") {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) | 0;
  return Math.abs(h);
}
export function initials(name = "?") {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
export function Avatar({ name, size, className = "" }) {
  const [a, b] = AV_COLORS[hash(name) % AV_COLORS.length];
  return (
    <span className={`avatar ${className}`} title={name}
      style={{ background: `linear-gradient(135deg, ${a}, ${b})`, ...(size ? { "--sz": `${size}px` } : {}) }}>
      {initials(name)}
    </span>
  );
}

export function Badge({ tone = "neutral", children, dot }) {
  return <span className={`badge ${tone}`}>{dot && <span className="dot" />}{children}</span>;
}

export function EmptyState({ icon = "folder", title, children }) {
  return (
    <div className="empty">
      <div className="empty-icon"><Icon name={icon} size={24} /></div>
      {title && <h4>{title}</h4>}
      {children && <p className="muted">{children}</p>}
    </div>
  );
}

export function Spinner({ label }) {
  return <div className="loading-row"><span className="spinner" />{label && <span>{label}</span>}</div>;
}

export function Brand({ withText = true }) {
  return (
    <span className="brand">
      <span className="brand-mark"><Icon name="logo" size={17} /></span>
      {withText && "SPLITO"}
    </span>
  );
}
