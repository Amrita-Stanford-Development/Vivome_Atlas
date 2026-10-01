# Webpage concept: intro → landing → scroll story → dashboard → tools

This describes a website *concept* and the *process* used to build it, taken
from MargaLink (a privacy-first journal finder for researchers). It is meant
for a different product. Copy the structure, the mechanics and the way of
working. Do **not** copy MargaLink's look (its teal, its clay desk, its
fonts, its copy). Derive your own world from your own product using the
worksheet at the end.

---

## 1. The idea in one paragraph

A first-time visitor gets a short **intro** that asks the question the
product answers. The intro does not cut to a new screen; it **becomes** the
landing page (its last frame is the landing's first). The landing is quiet:
the name, one catchphrase, one sentence. Scrolling then tells a short
**story**, one beat per capability, over a single living 3D scene that
scrolls with the page, with a few moments where the page **holds** while
something animates. The story ends in an emotional payoff. From there, and
from a button in the header at any time, the visitor goes to a plain
**dashboard** (`/home`) that links to the actual **tools**. The tools and the
dashboard share one visual theme derived from the same scene, so the
product feels like one place.

```
first visit only                           every visit
┌───────────┐   morphs   ┌──────────┐ scroll ┌─────────────────────────┐        ┌───────────┐      ┌───────┐
│  Intro    │──────────▶│ Landing  │──────▶│ Story beats + holds      │──────▶│ Dashboard │─────▶│ Tools │
│ (question)│  in place  │ (name)   │        │ (one per capability)     │ button │  (/home)  │ links│       │
└───────────┘            └──────────┘        │ ... finale (payoff)      │        └───────────┘      └───────┘
                                              └─────────────────────────┘
          one 3D scene behind all of it, one "thread" running through it
```

---

## 2. The five parts, and the job of each

### 2.1 Intro (about 5 seconds, once per session)

- **Job:** name the visitor's pain as a question. MargaLink: "Struggling
  with paper publication?" Nothing else: no logo wall, no buttons.
- **Sequence:** the scene's objects float and tumble close to the camera
  while the question shows; halfway through, the question fades and the
  real landing wordmark starts to build; at the end the objects fall into
  their places, the camera eases back, and the rest of the landing slides in.
- **Mechanics:**
  - The intro is a **transparent overlay on top of the real landing**, not a
    separate screen. The 3D scene underneath is the landing's own scene, held
    in its "floating" state while the overlay is present. This is what makes
    the morph seamless: nothing is swapped, only released.
  - The overlay is in the **server-rendered HTML** from the first paint.
    The landing's entrance animations are paused with CSS while it is there
    (`body:has(.intro-overlay:not(.intro-fade)) .landing-in { animation-play-state: paused }`),
    and the wordmark's animation is un-paused at the halfway mark via a data
    attribute on the overlay. Keying on the overlay (not a body class added
    after hydration) prevents the landing from running before the intro starts.
  - Show it **once per session** (`sessionStorage` flag). Read the flag in a
    lazy `useState` initializer, and start `dismissed` as `false` to match
    the server render, then correct it in `useLayoutEffect` (before paint).
    Starting from the stored flag directly caused a hydration mismatch that
    left the overlay stuck on screen.
  - A thin progress line at the bottom shows how long it lasts.
  - `prefers-reduced-motion`: cut it to under half a second.

### 2.2 Landing

- **Job:** say who you are, calmly. The product name (with one styled
  motif, see 3.4), a catchphrase that plays on the name's meaning
  (MargaLink: *Marga* is Sanskrit for "path", so "Find your path."), one
  sentence of what it does, and a small "scroll" hint.
- **No buttons on the landing itself.** The header carries the only way in
  (a "Dashboard" link) plus sign-in. The page's job is to be scrolled.
- The 3D scene frames the centred text from the edges; the thread (3.2)
  starts here.

### 2.3 Story beats and holds

- **Job:** show each capability at a *showcase* level: a name, one short
  evocative line, three plain benefits, a simple picture, a link. **No
  mechanics** (settings, tiers, consent flows, filters). Those belong on the
  tool pages. The owner rejected detail here explicitly.
- **Two kinds of section:**
  1. **Beats:** short text blocks that scroll past normally. Each is styled as
     an *object in the world* (MargaLink: a sheet of paper with a second
     sheet askew beneath it, shadow cast in the scene's light direction), not
     text floating over a background. Beats alternate left and right so the
     3D props sit beside them.
  2. **Holds:** sections that pin (sticky) for more than a screen of scroll
     while scroll progress drives an animation in the scene. MargaLink has
     three:
     - the closing call-to-action, where a page stands up beside the copy
       and writes itself;
     - an open book whose pages turn, one tool per spread, with an HTML
       caption naming the spread on screen;
     - the finale, where the finished manuscript is stamped and flies off
       as a paper plane.
- **Finale:** an emotional payoff line (MargaLink: "Afraid of rejection?
  Not this time.") plus two or three proof points (numbers or plain facts),
  then a normal footer.

### 2.4 Dashboard (`/home`)

- **Job:** the practical front door for people who already know the product.
  Deliberately plain: no scroll story, no 3D. The ways in (primary tool,
  guide), account status, and a "What's new" list driven by a data file
  (add an entry at the top to announce a release).
- The header on every page links here. The landing's header links here.
- A normal site footer lives here (legal links, team, copyright), not on the
  landing.

### 2.5 Tools

- Each tool is its own page with a shared header (logo, a tool switcher,
  account status). All the detail the homepage leaves out lives here.
- Same theme as everything else (section 4), so moving from the story to a
  tool feels like walking into the next room, not onto another site.

---

## 3. The mechanics that make it work

### 3.1 One scene, one canvas, behind everything

- A single **fixed, full-viewport WebGL canvas** (three.js) sits behind the
  whole page (`position: fixed; inset: 0; pointer-events: none`). The HTML
  sections scroll over it.
- The camera **pans through the scene at the page's own scroll speed**, so
  3D objects appear to scroll with the HTML. Objects beside a beat are
  anchored to that beat's position on the page, so they stay beside its copy.
- While a section is **held**, the camera holds too, and that section's
  local progress drives the animation instead.
- **Build the scene in code**, not from model files: rounded boxes,
  extrusions, cylinders, capsules, all in one material family, text drawn on
  canvas textures. Small download, easy to recolour, every object on-palette.
  One soft environment light plus one key light (with soft shadows) and a
  shadow-only ground plane, so objects rest on the page's own background colour.
  Ambient occlusion as a post-process sells the "physical" look (load it
  asynchronously; render directly until it is ready; watch for double gamma
  correction if the AO pass already writes sRGB).
- Stop rendering when the scene is not visible or not needed (`active` prop).

### 3.2 The thread

The single most important concept. **One continuous line runs through the
entire scroll story** and ties it together. In MargaLink it is a route (the
"path") drawn on the desk: it starts at a pencil tip on the landing, loops
around the wordmark to a pin, winds off the edge and back to the closing
page's pin, weaves between the props of each beat, reaches the book (a pin
drops on it), and ends at the finale's manuscript. Pins mark checkpoints.

Pick a thread that comes from your product's meaning (see the worksheet):
a route, a wire, a thread of yarn, a timeline, a signal, a river. It gives
the scroll a direction and makes separate sections read as one journey.

### 3.3 Scroll progress, done robustly

- **One** `requestAnimationFrame`-throttled scroll listener for the whole page
  (not one per section). It computes:
  - **local progress** per section: 0 when the section's top reaches the
    bottom of the viewport, 1 once it has mostly arrived. Never use "fraction
    of total page scroll"; it breaks every time a section's height changes.
  - **pinned progress** per hold: `-rect.top / (section.offsetHeight - viewportHeight)`,
    clamped to 0..1.
- **Holds** are a tall wrapper with a sticky child:
  ```css
  .hold          { height: 130svh; }                      /* scroll length of the hold */
  .hold > section { position: sticky; top: 0; min-height: 100svh; }
  ```
- Small pure helpers, each with a tiny self-check:
  - `between(p, a, b)`: remap progress into a sub-window, clamped.
  - `stagger(p, i, n)`: sibling `i` of `n` gets its own reveal window, so
    items arrive in sequence.
  - `motionStyle(reduced, style)`: returns `{}` under reduced motion.
- **Timing tables live in data**, shared by the 3D scene and the HTML. For
  example, the book's page-turn windows and a `spreadAt(progress)` function
  are read by both the 3D book and the HTML caption, so the caption always
  names the spread that is on screen.
- **Content lives in data too**: one array of beats/spreads (name, line,
  points, link) drives both the 3D pages and the HTML (including the
  phone version).

### 3.4 A motif that recurs

Pick one small typographic device and reuse it at every level. MargaLink's
is the **cutout**: one key word set in a solid accent-colour block
("Marga[Link]", "Find where it [fits.]", "Not this [time.]"). It wipes in
on the landing (a `clip-path` animation) and then marks the key word of
every beat, every spread and the finale. One motif, used consistently,
does more than many decorations.

### 3.5 Phones

There is no room beside the text for 3D objects on a narrow screen, so
design a separate, simpler path instead of shrinking the desktop one:

- the landing and its scene **fade** into the next section;
- an **HTML version** replaces each 3D moment (a page that types itself in
  HTML; the book becomes a stack of cards);
- holds become normal sections (`position: relative; height: auto`).

Choose the layout once at mount from a media query (and listen for changes).

### 3.6 Accessibility and restraint

- `prefers-reduced-motion`: no scroll-linked transforms, content simply
  visible; global CSS that shortens all animations and transitions.
- Decorative layers (`aria-hidden`), real headings for every section (use
  `sr-only` where the heading is visual-only), visible keyboard focus.
- Motion answers scroll; nothing loops distractingly beside reading text.
  Small idle motion on props is fine.

---

## 4. Making every element match the theme

The whole visual system comes from **one imagined physical world**, and
every UI element is an object in that world. MargaLink's world is a
researcher's desk rendered in matte clay; yours will differ. The method:

1. **Pick the world** from the product's meaning and its users' daily
   surroundings (see the worksheet). Everything else is derived from it.
2. **Pick the materials** of that world (MargaLink: matte clay for objects,
   white paper for anything you read). Two or three at most.
3. **Pick one light.** One direction (MargaLink: from the top left), used by
   the 3D key light *and* every CSS shadow. Shadows are tinted with the
   world's warmth (e.g. `rgba(58,44,28,…)`), never neutral black.
4. **Take the palette from the scene**, then turn it into CSS tokens on
   `:root` and use only tokens:
   - a background ("the surface everything rests on");
   - ink and soft ink for text;
   - **one** accent (also used by the motif and focus rings);
   - a soft tint of the accent for selected states;
   - a line colour for hairlines;
   - **reserved colours with exactly one meaning each.** MargaLink has two:
     the logo dot's colour, used nowhere else, and an "away" colour used only
     to mark "this would leave your device". A reserved colour is never used
     decoratively, so when it appears it means something.
5. **Map each UI role to an object** and write it once as a component class
   (in CSS `@layer components` so utility classes can still override):
   | UI role | Object in MargaLink's world | CSS idea |
   |---|---|---|
   | Chrome: trays, toolbars, windows, buttons | raised clay | soft gradient, inner top highlight, two warm drop shadows |
   | Inputs, active item, notes | pressed into the clay (a well) | inset shadow, slightly darker fill |
   | Content you read (documents, results) | a paper sheet | white, thin edge, long soft shadow |
   | Small status or icon badges | a bead | small raised circle |
   Then build every page from these classes. New element? Ask "what object
   is this in the world?" and reuse or add one class, never a one-off style.
6. **Texture:** a very faint noise/grain overlay (SVG `feTurbulence`,
   multiply blend, low opacity) on the background of every page, so flat
   areas feel like a material.
7. **Type roles:** a display face for big moments, a clean sans for UI and
   body, and at most one more for small data. Headlines tight
   (negative letter-spacing), body lines under about 70 characters.
8. **Icons:** one icon set, one stroke width, everywhere.
9. **Logo from the same idea:** MargaLink's mark is its thread drawn as a
   letter (an "M" drawn as one route, ending at a dot in the reserved
   colour), and the wordmark's "i" carries the same dot. Design the logo
   last, when the world and thread are settled, and show many options side
   by side before choosing.
10. **Copy rules:** plain, sentence case, active voice, no hype words. The
    owner banned em dashes in all visible text (they read as generated);
    use a colon, comma or full stop instead. The homepage stays high-level;
    tool pages carry the detail.

---

## 5. The process (how it was actually built)

The final page took many small iterations, driven by the owner looking at
each version in the browser. What worked:

1. **Meaning first.** Start from the name and the user's pain. Write the
   intro question and the catchphrase before designing anything.
2. **Design options, not one design.** For the landing and the logo, build
   2 to 4 visibly different options (a quick page showing them side by side
   works well), let the owner pick, then refine the chosen one ("T7, but
   bolder, with the dot in the i").
3. **Build the skeleton in scroll order,** one piece per commit: intro →
   landing → the morph between them → the closing call-to-action → beats →
   the showcase (book) → finale → dashboard → theme across the tools.
4. **One visual change per commit, then look.** Screenshot it (headless
   browser at desktop and phone widths) before calling it done. Revert
   freely: a redesign that didn't land was reverted in one commit.
5. **Keep the intro and landing one object.** Several iterations were about
   removing seams (the intro became the landing; the landing's paper *became*
   the closing section's paper; the desk scrolls with the page rather than
   being swapped). Whenever two sections feel like two screens, ask what
   object could carry across the boundary.
6. **Add holds sparingly.** Each hold is one orchestrated moment. Three for
   the whole page was enough.
7. **Theme the tools last,** by writing the component classes (section 4.5)
   from the finished scene and applying them everywhere at once.
8. **Testing:** keep logic (scroll maths, timing helpers, data) in small
   pure functions with a self-check; for pure visual iteration the owner
   preferred to test by eye rather than wait for browser test suites.

### Pitfalls we hit

- Using fraction-of-page scroll instead of per-section local progress:
  every layout change broke the timings.
- The intro overlay and session storage: hydration mismatch (see 2.1).
- A second listener or animation loop per section: stutter. Use one of each.
- Putting feature details (settings, pricing tiers, consent flows) on the
  homepage: rejected, moved to the tool pages.
- Forgetting the phone path until the end: design it alongside, not after.
- Big text overlays centred against a full-height section: they only appear
  when the section is half scrolled. Size the overlay by its content's box.

---

## 6. Suggested structure (Next.js + three.js; adapt to your stack)

```
app/
  page.tsx                 landing + story; wraps it in <IntroSequence>
  _home/
    useScrollProgress.ts   the one scroll listener: local + pinned progress, reduced motion
    motion.ts              between / stagger / motionStyle (+ a self-check)
    HeroSection.tsx        the landing
    FinalSection.tsx, ...  one file per section
    home.css               homepage-only styles (holds, beats, motif)
  home/page.tsx            the dashboard
  globals.css              tokens on :root, grain, reduced-motion rules
  theme.css                component classes: raised / well / sheet / bead
components/
  IntroSequence.tsx        the transparent overlay
  Scene.tsx                the fixed canvas, render loop, post-processing
  three/scene.ts           the world built in code: objects, thread, holds' animations
  three/storyData.ts       beats/spreads content + timing tables, shared with the HTML
```

---

## 7. Worksheet for the new product (fill this in first)

1. **The pain, as one question** (the intro):
2. **The name's meaning, and a catchphrase that plays on it:**
3. **The world** (where your users are when they have this problem):
4. **The thread** that runs through the story (from the meaning or the world):
5. **The objects** in the scene (6 to 10, all from that world):
6. **Materials** (2 or 3) and **the light direction:**
7. **Palette:** background, ink, soft ink, one accent, accent tint, line,
   and each reserved colour with its single meaning:
8. **The motif** (one typographic device reused everywhere):
9. **The beats** (one per capability: name, one line, three benefits):
10. **The holds** (at most three moments where the page pins, and what animates):
11. **The finale** (payoff line + two or three proof points):
12. **UI roles → objects** (chrome, inputs, readable content, badges):
13. **Phone version** of each 3D moment:

Answer these with the owner before writing code, then build in the order of
section 5.
