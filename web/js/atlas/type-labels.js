// Names on the map: each shown cell type's plain name, drawn over the 3D
// view at the type's centre as an HTML label (a dot of the type's colour and
// its name), switched on and off by the visitor.
//
// labelLayout is the geometry and is pure, so node --test covers it: where
// each type's centre falls on the screen, which labels fit, larger types
// first. createTypeLabels keeps the labels in their container: they follow
// the camera, laid out at most once per drawn frame (the stage draws on
// every rig change and after every resize), and do nothing while off. Names
// are data, so they go in as text, never as markup.

import { CLASS_COLOURS, plainName } from '../workflow-data.js';
import { classAnchors } from './reference-data.js';
import { placeLabels, projectAll } from './spatial.js';

export const LABEL_PAD = 4;      // px kept clear between two labels
export const LABEL_HEIGHT = 20;  // px: 16px line, 2px padding above and below

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

// A label's size before the page has measured it: the name at about 6.4 px a
// character (12px type), plus the dot, the gap and the padding.
export const estimateBox = (name) => ({ w: Math.ceil(String(name).length * 6.4) + 27, h: LABEL_HEIGHT });

// The labels to draw: one {c, x, y, w, h} per type (x, y the box's centre in
// CSS pixels from the viewer's top left), larger types first. A type is left
// out when it is not shown, has no cells (sizeOf 0, or no anchor), or its
// centre is behind the camera, outside the depth the camera draws, or off
// screen. A box near an edge moves inside the screen; a box that overlaps
// one already kept is dropped (placeLabels keeps boxes in the order given,
// so the larger type wins). `anchors` is classAnchors' output: [x, y, z] in
// scene units, or null, per type; `viewProjection` is column-major
// (stage.viewProjection()).
export function labelLayout(anchors, viewProjection, width, height, {
  shown = () => true,
  sizeOf = () => 1,
  boxOf = () => ({ w: 120, h: LABEL_HEIGHT }),
  pad = LABEL_PAD,
} = {}) {
  const candidates = [];
  anchors.forEach((p, c) => {
    if (!p || !shown(c)) return;
    const size = sizeOf(c);
    if (size > 0) candidates.push({ c, size, p });
  });
  candidates.sort((a, b) => b.size - a.size || a.c - b.c);

  const pos = new Float32Array(candidates.length * 3);
  candidates.forEach(({ p }, i) => pos.set(p, i * 3));
  const screen = projectAll(pos, candidates.length, viewProjection, width, height);
  const m = viewProjection;
  const boxes = candidates.map(({ c, p }, i) => {
    const w = screen[i * 3 + 2];
    if (w === Infinity) return null;
    // In front of the eye but nearer than the near plane (or past the far
    // one): the camera does not draw it, so it gets no name either.
    const zc = m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14];
    if (zc < -w || zc > w) return null;
    const x = screen[i * 3];
    const y = screen[i * 3 + 1];
    if (!(x >= 0 && x <= width && y >= 0 && y <= height)) return null;
    const box = boxOf(c);
    if (box.w > width || box.h > height) return null;
    return {
      c,
      x: clamp(x, box.w / 2, width - box.w / 2),
      y: clamp(y, box.h / 2, height - box.h / 2),
      w: box.w,
      h: box.h,
    };
  });
  const keep = placeLabels(boxes, pad);
  return boxes.filter((b, i) => keep[i]);
}

// The labels over the stage, in `container` (an element covering the viewer,
// which takes no pointer events). Starts off. refresh() re-reads which types
// are shown; call it after a filter change. An organ's map brings its own
// colours and names (ref.colours, ref.nameOf; web/js/atlas/organs.js).
export function createTypeLabels({ stage, ref, layer, container }) {
  const nClasses = ref.order.length;
  const colours = ref.colours ?? CLASS_COLOURS;
  const names = ref.order.map((name) => (ref.nameOf ?? plainName)(name));
  const els = [];        // one label element per type, made on first show
  const measured = [];   // {w, h} per type once the page has laid it out
  let on = false;
  let dirty = false;
  let laidWidth = 0;
  let laidHeight = 0;
  let current = [];      // the elements in the container, in order
  let anchors = [];
  let counts = new Uint32Array(nClasses);
  let scratchPos = null;
  let scratchCodes = null;

  function element(c) {
    if (!els[c]) {
      const el = document.createElement('div');
      el.className = 'type-label';
      el.dataset.class = String(c);
      const dot = document.createElement('span');
      dot.className = 'type-label-dot';
      dot.style.background = colours[c];
      const name = document.createElement('span');
      name.className = 'type-label-name';
      name.textContent = names[c];
      el.append(dot, name);
      els[c] = el;
    }
    return els[c];
  }

  function show(nodes) {
    if (nodes.length === current.length && nodes.every((el, i) => el === current[i])) return;
    container.replaceChildren(...nodes);
    current = nodes;
  }

  // Which types have cells on show, how many, and where each one's name goes:
  // the shown member nearest the shown cells' mean, so hiding a modality
  // never leaves a name over empty space.
  function readShown() {
    const { positions, codes, n } = ref;
    scratchPos ??= new Float32Array(n * 3);
    scratchCodes ??= new Uint8Array(n);
    const classOn = Array.from({ length: nClasses }, (_, c) => layer.classOn(c));
    const visible = typeof layer.visible === 'function' ? layer.visible : null;
    counts = new Uint32Array(nClasses);
    let m = 0;
    for (let i = 0; i < n; i += 1) {
      const c = codes[i];
      if (!classOn[c] || (visible && !visible(i))) continue;
      counts[c] += 1;
      scratchPos[m * 3] = positions[i * 3];
      scratchPos[m * 3 + 1] = positions[i * 3 + 1];
      scratchPos[m * 3 + 2] = positions[i * 3 + 2];
      scratchCodes[m] = c;
      m += 1;
    }
    anchors = classAnchors(scratchPos, scratchCodes, m, nClasses);
  }

  // Each label's size as drawn: every label goes in the container once and is
  // read in one layout. One the page could not lay out (the viewer hidden)
  // keeps the estimate and is measured again next time.
  function measure() {
    const all = [];
    for (let c = 0; c < nClasses; c += 1) all.push(element(c));
    show(all);
    for (let c = 0; c < nClasses; c += 1) {
      if (measured[c]) continue;
      const w = els[c].offsetWidth;
      const h = els[c].offsetHeight;
      if (w > 0 && h > 0) measured[c] = { w, h };
    }
  }
  const boxOf = (c) => measured[c] ?? estimateBox(names[c]);

  function draw() {
    dirty = false;
    laidWidth = stage.width;
    laidHeight = stage.height;
    const placed = labelLayout(anchors, stage.viewProjection(), laidWidth, laidHeight, {
      shown: (c) => counts[c] > 0,
      sizeOf: (c) => counts[c],
      boxOf,
    });
    show(placed.map(({ c, x, y, w, h }) => {
      const el = element(c);
      el.style.transform = `translate(${Math.round(x - w / 2)}px, ${Math.round(y - h / 2)}px)`;
      return el;
    }));
  }

  stage.rig.on('change', () => { if (on) dirty = true; });
  stage.onFrame(() => {
    if (!on) return;
    if (dirty || stage.width !== laidWidth || stage.height !== laidHeight) draw();
  });

  return {
    setOn(next) {
      next = Boolean(next);
      if (next === on) return;
      on = next;
      if (on) {
        readShown();
        measure();
        draw();
      } else {
        dirty = false;
        show([]);
      }
    },
    get on() { return on; },
    refresh() {
      if (!on) return;
      readShown();
      draw();
    },
  };
}
