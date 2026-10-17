// Motion maths for the landing (web/js/story.js). Pure: no DOM, so node
// --test covers it. Every progress value is 0..1.

export const clamp01 = (x) => Math.min(1, Math.max(0, x));

// A number counting up to its final text, keeping the final's format:
// "85,233" passes through "42,617", "94.9%" through "47.5%". Text that isn't
// a single number, with nothing but symbols such as % around it ("Pending",
// a version such as "0.3.0", a name such as "VivOME v3.1") is left as it is.
export function countText(final, t) {
  const text = String(final);
  if (t >= 1) return text;
  const m = text.match(/^([^\dA-Za-z]*?)(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?([^\dA-Za-z.]*)$/);
  if (!m) return text;
  const [, before, whole, fraction = '', after] = m;
  const decimals = fraction ? fraction.length - 1 : 0;
  const target = Number(whole.replace(/,/g, '') + fraction);
  const eased = 1 - (1 - clamp01(t)) ** 3;
  let shown = (target * eased).toFixed(decimals);
  if (whole.includes(',')) {
    const [int, dec] = shown.split('.');
    shown = int.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + (dec ? `.${dec}` : '');
  }
  return before + shown + after;
}
