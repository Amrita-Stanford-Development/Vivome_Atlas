// The cards and their cues: what every scene's timeline (compositions/)
// uses to fade its cards in and out where they stand, and to time what
// happens inside them to the voice.
//
// A card never moves: it fades in over FADE seconds as its scene's journey
// ends, holds, and fades out before the next journey (the last card stays
// to the end). The fade is set on each card, never on the scene's root: an
// element whose ancestor is fading is cut off from the water behind it in
// Chrome, so liquid glass faded through its root would lose its frost.
//
// A cue is when a phrase of the scene's voice line is said, in seconds into
// its card (web/js/reel-frames.js, `said`; scripts/prepare.mjs writes them
// into build/facts.js). A classic script, loaded after build/facts.js.
//
//   VivomeCue.cue(id, k, offset)   phrase k of scene id's line, plus offset
//   VivomeCue.exit(id)             when the card's closing picture starts
//   VivomeCue.end(id)              the card's length
//   VivomeCue.card(tl, root, id, { later })
//       fades the scene's cards in at 0 and out at the end; `later` cards,
//       [[element or selector, seconds], ...], fade in at their own time.

(function () {
  const V = window.VIVOME;
  const frameOf = (id) => {
    const f = V.frames.find((x) => x.id === id);
    if (!f) throw new Error(`no scene ${id}`);
    return f;
  };
  const cue = (id, k, offset = 0) => {
    const f = frameOf(id);
    if (!(k in f.cues)) throw new Error(`scene ${id} has no cue ${k}`);
    return f.cues[k] + offset;
  };
  const exit = (id) => frameOf(id).exit;
  const end = (id) => frameOf(id).card;

  // The scene's cards: its top-most cards, and anything else at its top that
  // holds no liquid glass (a picture, a word set apart); inside anything that
  // holds liquid glass, its own cards.
  function targets(root) {
    const out = [];
    const walk = (el) => {
      for (const child of el.children) {
        if (child.tagName === 'STYLE' || child.tagName === 'SCRIPT') continue;
        if (child.matches('.card, .sheet, .liquid') || !child.querySelector('.liquid')) out.push(child);
        else walk(child);
      }
    };
    walk(root);
    return out;
  }

  function card(tl, root, id, { later = [] } = {}) {
    const f = frameOf(id);
    const fade = V.fade;
    // HyperFrames takes the scene root's id away when it mounts the scene,
    // so a selector that starts with it is read inside the root instead.
    const pick = (x) => (typeof x === 'string' ? [...root.querySelectorAll(x.replace(`#s-${id} `, ':scope '))] : [x]);
    const late = new Map();
    for (const [what, at] of later) for (const el of pick(what)) late.set(el, at);
    const all = targets(root);
    for (const el of late.keys()) if (!all.includes(el)) all.push(el);
    for (const el of all) {
      const at = late.get(el) ?? 0;
      tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: fade, ease: 'power1.inOut', immediateRender: true }, at);
      if (!f.last) tl.fromTo(el, { opacity: 1 }, { opacity: 0, duration: fade, ease: 'power1.inOut', immediateRender: false }, f.card - fade);
    }
    tl.set({}, {}, f.card);
    return all;
  }

  window.VivomeCue = { cue, exit, end, card, targets };
})();
