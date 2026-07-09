// paise (integer minor units) -> ₹ display
export function rupees(minor) {
  const sign = minor < 0 ? "-" : "";
  const abs = Math.abs(minor);
  return `${sign}₹${(abs / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
}
