export const toLocalYmd = (dt: Date) => {
  const y = dt.getFullYear();
  const m = String(dt.getMonth() + 1).padStart(2, "0");
  const d = String(dt.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
};

export const parseLocalYmd = (value: string): Date | null => {
  const parts = value.split("-").map(Number);
  if (parts.length >= 3 && parts.every((n) => Number.isFinite(n))) {
    const dt = new Date(parts[0], parts[1] - 1, parts[2]);
    return Number.isNaN(dt.getTime()) ? null : dt;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed;
};

export const todayLocalYmd = () => toLocalYmd(new Date());

export const genId = () => {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return Math.random().toString(36).slice(2, 10);
};

export const coerceConstraintWeight = (value: unknown, fallback = 10) => {
  if (typeof value === "boolean") return value ? 10 : 0;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(10, Math.max(0, parsed));
};

export const coercePrefWeight = (value: unknown, fallback = 5) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(10, Math.max(0, parsed));
};
