// Drawing helpers shared by the Workflow page's scenes (web/js/scenes-*.js):
// a sharp canvas that follows its box, text, rounded bars, the hatch for a
// missing value, and dragging. DOM code; the maths lives in workflow-layout.js.

export const INK = '#1D2B36';
export const SOFT = '#4B4B4B';
export const FAINT = '#666666';
export const LINE = '#E4E3DE';
export const BENCH = '#F5F5F3';
export const ACCENT = '#0066A3';
export const RNA = '#C8641E';   // reserved: RNA, and nothing else
export const PROT = '#2F8F6A';  // reserved: protein, and nothing else
export const FONT = "'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif";

export function alpha(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}

// A canvas filling `el`, drawn at the device's pixel ratio (capped at 2, so
// phones keep their frame rate). Coordinates are CSS pixels.
export function mountCanvas(el) {
  const canvas = document.createElement('canvas');
  el.appendChild(canvas);
  const g = canvas.getContext('2d');
  const view = { canvas, g, width: 0, height: 0, dpr: 1 };
  view.resize = () => {
    const box = el.getBoundingClientRect();
    view.dpr = Math.min(2, window.devicePixelRatio || 1);
    view.width = Math.max(1, Math.round(box.width));
    view.height = Math.max(1, Math.round(box.height));
    canvas.width = Math.round(view.width * view.dpr);
    canvas.height = Math.round(view.height * view.dpr);
    g.setTransform(view.dpr, 0, 0, view.dpr, 0, 0);
  };
  view.clear = () => g.clearRect(0, 0, view.width, view.height);
  view.dispose = () => canvas.remove();
  view.resize();
  return view;
}

export function text(g, str, x, y, { size = 12, colour = INK, align = 'left', weight = 400, baseline = 'alphabetic', max, opacity = 1 } = {}) {
  g.save();
  g.globalAlpha *= opacity;
  g.font = `${weight} ${size}px ${FONT}`;
  g.fillStyle = colour;
  g.textAlign = align;
  g.textBaseline = baseline;
  let s = String(str);
  if (max && g.measureText(s).width > max) {
    while (s.length > 1 && g.measureText(`${s}…`).width > max) s = s.slice(0, -1);
    s = `${s}…`;
  }
  g.fillText(s, x, y);
  g.restore();
}

export function roundRect(g, x, y, w, h, r = 3) {
  const rr = Math.max(0, Math.min(r, Math.abs(w) / 2, Math.abs(h) / 2));
  g.beginPath();
  g.moveTo(x + rr, y);
  g.arcTo(x + w, y, x + w, y + h, rr);
  g.arcTo(x + w, y + h, x, y + h, rr);
  g.arcTo(x, y + h, x, y, rr);
  g.arcTo(x, y, x + w, y, rr);
  g.closePath();
}

export function bar(g, x, y, w, h, colour, r = 2, opacity = 1) {
  if (w <= 0 || h <= 0) return;
  g.save();
  g.globalAlpha *= opacity;
  g.fillStyle = colour;
  roundRect(g, x, y, w, h, r);
  g.fill();
  g.restore();
}

let hatchPattern = null;
// Diagonal stripes: a value the file left missing.
export function hatch(g, x, y, w, h, opacity = 1) {
  if (!hatchPattern) {
    const tile = document.createElement('canvas');
    tile.width = 6;
    tile.height = 6;
    const t = tile.getContext('2d');
    t.fillStyle = BENCH;
    t.fillRect(0, 0, 6, 6);
    t.strokeStyle = '#B9C2C9';
    t.lineWidth = 1.4;
    t.beginPath();
    t.moveTo(0, 6); t.lineTo(6, 0);
    t.moveTo(-1, 1); t.lineTo(1, -1);
    t.moveTo(5, 7); t.lineTo(7, 5);
    t.stroke();
    hatchPattern = g.createPattern(tile, 'repeat');
  }
  g.save();
  g.globalAlpha *= opacity;
  g.fillStyle = hatchPattern;
  g.fillRect(x, y, w, h);
  g.restore();
}

export function line(g, x0, y0, x1, y1, { colour = INK, width = 1, dash = null, opacity = 1 } = {}) {
  g.save();
  g.globalAlpha *= opacity;
  g.strokeStyle = colour;
  g.lineWidth = width;
  if (dash) g.setLineDash(dash);
  g.beginPath();
  g.moveTo(x0, y0);
  g.lineTo(x1, y1);
  g.stroke();
  g.restore();
}

export function dot(g, x, y, r, colour, opacity = 1, ring = null) {
  g.save();
  g.globalAlpha *= opacity;
  g.beginPath();
  g.arc(x, y, Math.max(0, r), 0, Math.PI * 2);
  g.fillStyle = colour;
  g.fill();
  if (ring) { g.lineWidth = 2; g.strokeStyle = ring; g.stroke(); }
  g.restore();
}

// A chip: text in a rounded white tag.
export function chip(g, str, x, y, { size = 12, colour = INK, fill = 'rgba(255,255,255,0.92)', align = 'left', opacity = 1, border = null } = {}) {
  g.save();
  g.globalAlpha *= opacity;
  g.font = `500 ${size}px ${FONT}`;
  const w = g.measureText(String(str)).width + size * 1.2;
  const h = size * 1.9;
  const x0 = align === 'center' ? x - w / 2 : align === 'right' ? x - w : x;
  g.fillStyle = fill;
  roundRect(g, x0, y - h / 2, w, h, h / 2);
  g.fill();
  if (border) { g.strokeStyle = border; g.lineWidth = 1.5; g.stroke(); }
  g.fillStyle = colour;
  g.textAlign = 'left';
  g.textBaseline = 'middle';
  g.fillText(String(str), x0 + size * 0.6, y + 0.5);
  g.restore();
  return w;
}

// Drag to turn: calls onDrag(dx, dy) in CSS pixels; returns a remover.
export function onDrag(el, handler) {
  let last = null;
  const down = (e) => { last = [e.clientX, e.clientY]; el.setPointerCapture?.(e.pointerId); };
  const move = (e) => {
    if (!last) return;
    handler(e.clientX - last[0], e.clientY - last[1]);
    last = [e.clientX, e.clientY];
  };
  const up = () => { last = null; };
  el.addEventListener('pointerdown', down);
  el.addEventListener('pointermove', move);
  el.addEventListener('pointerup', up);
  el.addEventListener('pointercancel', up);
  return () => {
    el.removeEventListener('pointerdown', down);
    el.removeEventListener('pointermove', move);
    el.removeEventListener('pointerup', up);
    el.removeEventListener('pointercancel', up);
  };
}

// Readable class names in tight spaces.
export const short = (name) => String(name)
  .replace('cd4-positive, alpha-beta t cell', 'CD4 T')
  .replace('cd8-positive, alpha-beta t cell', 'CD8 T')
  .replace('naive thymus-derived cd4-positive, alpha-beta t cell', 'naive CD4 T')
  .replace('naive thymus-derived CD4 T', 'naive CD4 T')
  .replace('natural killer cell', 'NK')
  .replace('mature nk t cell', 'NK T')
  .replace('regulatory t cell', 'regulatory T')
  .replace('hematopoietic precursor cell', 'precursor')
  .replace('hematopoietic stem cell', 'stem cell')
  .replace('common myeloid progenitor', 'myeloid progenitor')
  .replace('plasmacytoid dendritic cell', 'pDC')
  .replace('myeloid dendritic cell', 'mDC');
