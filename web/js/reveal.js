// Text reveals for the landing story: a different way in for each chapter.
// A chapter names its kind with data-reveal; web/js/story.js feeds each one
// its section's progress (0..1) from the one scroll loop. The text is real,
// readable HTML from the start: a reveal only changes how it arrives, and
// under reduced motion everything is simply shown.

import { between, smooth, stagger } from './motion.js';

// Wrap each word in <span class="w">. Child elements (the OME cutout, a
// data-fact number, a strong) stay whole and count as one word.
export function splitWords(el) {
  const words = [];
  for (const child of [...el.childNodes]) {
    if (child.nodeType === Node.ELEMENT_NODE) {
      child.classList.add('w');
      words.push(child);
    } else if (child.nodeType === Node.TEXT_NODE) {
      const frag = document.createDocumentFragment();
      for (const part of child.textContent.split(/(\s+)/)) {
        if (!part) continue;
        if (/^\s+$/.test(part)) { frag.append(part); continue; }
        const w = document.createElement('span');
        w.className = 'w';
        w.textContent = part;
        frag.append(w);
        words.push(w);
      }
      child.replaceWith(frag);
    }
  }
  return words;
}

// Wrap each letter of the text nodes in <span class="l">; child elements
// arrive whole, after the letters before them.
function splitLetters(el) {
  const letters = [];
  for (const child of [...el.childNodes]) {
    if (child.nodeType === Node.ELEMENT_NODE) {
      child.classList.add('l');
      letters.push(child);
    } else if (child.nodeType === Node.TEXT_NODE) {
      const frag = document.createDocumentFragment();
      for (const ch of child.textContent) {
        if (/\s/.test(ch)) { frag.append(ch); continue; }
        const l = document.createElement('span');
        l.className = 'l';
        l.textContent = ch;
        frag.append(l);
        letters.push(l);
      }
      child.replaceWith(frag);
    }
  }
  return letters;
}

const fade = (nodes, p, overlap, floor = 0) => {
  nodes.forEach((node, i) => {
    node.style.opacity = floor + (1 - floor) * stagger(p, i, nodes.length, overlap);
  });
};

const KINDS = {
  // Words ink in as you read down the paragraph.
  highlight(el) {
    const words = [...el.querySelectorAll('[data-words]')].flatMap(splitWords);
    return (t) => fade(words, between(t, 0.04, 0.72), 0.9, 0.14);
  },
  // Headline lines slide up out of a mask, then the facts arrive (CSS).
  mask(el) {
    return (t) => el.classList.toggle('is-in', t > 0.04);
  },
  // Two columns, RNA then protein, each tinted in its reserved colour.
  split(el) {
    const rna = [...el.querySelectorAll('.col-rna [data-words]')].flatMap(splitWords);
    const prot = [...el.querySelectorAll('.col-prot [data-words]')].flatMap(splitWords);
    return (t) => {
      fade(rna, between(t, 0.04, 0.4), 0.85, 0.12);
      fade(prot, between(t, 0.28, 0.64), 0.85, 0.12);
      el.classList.toggle('is-closed', t > 0.7);
    };
  },
  // A sticky 1 to 4 sequence: one step on stage at a time.
  steps(el) {
    const steps = [...el.querySelectorAll('.step')];
    return (t) => {
      const p = between(t, 0.02, 0.96);
      const current = Math.min(steps.length - 1, Math.floor(p * steps.length));
      steps.forEach((s, i) => {
        s.classList.toggle('is-current', i === current);
        s.classList.toggle('is-done', i < current);
      });
      el.style.setProperty('--progress', p.toFixed(3));
    };
  },
  // The usual answer is struck out, then VivOME's arrives.
  strike(el) {
    return (t) => {
      el.style.setProperty('--strike', smooth(between(t, 0.12, 0.36)).toFixed(3));
      el.classList.toggle('is-answered', t > 0.38);
    };
  },
  // Each rule of the benchmark underlines itself in turn.
  underline(el) {
    const marks = [...el.querySelectorAll('.draw')];
    return (t) => {
      const p = between(t, 0.08, 0.62);
      marks.forEach((m, i) => m.style.setProperty('--draw', stagger(p, i, marks.length, 0.3).toFixed(3)));
    };
  },
  // The thread draws down the releases; each arrives as the line reaches it.
  timeline(el) {
    const items = [...el.querySelectorAll('.release')];
    return (t) => {
      const p = between(t, 0.04, 0.78);
      el.style.setProperty('--line', p.toFixed(3));
      items.forEach((item, i) => item.classList.toggle('is-in', p > (i + 0.15) / items.length));
    };
  },
  // The payoff line arrives letter by letter, then everything under it.
  letters(el) {
    const letters = [...el.querySelectorAll('[data-letters]')].flatMap(splitLetters);
    return (t) => {
      fade(letters, between(t, 0.04, 0.36), 0.94);
      el.classList.toggle('is-in', t > 0.34);
    };
  },
};

// -> [{ el, update(t) }] for every [data-reveal] under root. Under reduced
// motion each reveal is shown at once and nothing is returned to update.
export function mountReveals(root, reduced) {
  const out = [];
  for (const el of root.querySelectorAll('[data-reveal]')) {
    const make = KINDS[el.dataset.reveal];
    if (!make) continue;
    const update = make(el);
    if (reduced) update(1);
    else out.push({ el, update });
  }
  return out;
}
