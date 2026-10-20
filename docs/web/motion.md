# The Motion page and the film

`web/motion.html` shows a film about VivOME, 2 minutes 49 seconds long,
and its storyboard: the film itself at the top, in a player, then its
twelve scenes, each shown as a still rendered from the film beside its
on-screen words, voice-over, motion notes and sound cue. The film is made in
its own project, `motion/`, with HyperFrames and other motion tools; the
page shows what it renders.

## The idea: a dive

The camera dives through the site's own living water and comes back up.

| Depth | Chapter | Scenes |
|---|---|---|
| At the surface | The problem: protein cells arrive unnamed and mostly unmeasured | 1 to 3 |
| Going down | The solution: RNA atlases already name their cells; VivOME carries the names across | 4 and 5 |
| The deep | What is new: built for missing values, honest answers, a second opinion | 6 to 8 |
| The floor | The results, with their caveats, and the limits | 9 and 10 |
| Rising, then the light | Use it: the Atlas page, then the end card | 11 and 12 |

The background never changes: every scene sits on the site's own white
field and gel, as the site's pages do, and every word is in the site's dark
ink. Depth shows in the journeys, in a time code and a depth gauge in every
frame (it moves only while the camera does), and in the waterline, seen on
the first card and the last. The water's objects never change size: each
cell and thread is at its own fixed depth, and only the camera moves. The
end breaks the surface: "No cell placed without evidence."

Every word and diagram sits on a card, so it reads over the water, even at
720p: the site's white card with its blue halo (`.sheet`) in odd scenes,
its liquid glass (`.liquid`) in even ones, both straight from
`web/css/page.css`. The storyboard names each scene's card (`card`), the
page lists it among the scene's notes, and the test checks that each
composition uses its scene's kind and no other.

The film's sound is a voice-over speaking each scene's line and a soft
music bed under the whole film, one continuous piece that rises towards the
end; there are no sound effects. The stills on the page are silent; the
sound is in the rendered film only.

The film has English captions (`web/motion/film/vivome.en.vtt`), off until
the viewer turns them on in the player. Each cue is one phrase of a scene's
voice line, from when it is said until the next phrase starts, with the
numbers the film says. `captionsVtt` in `web/js/reel-frames.js` builds them
from the same records the voice follows, and `motion/scripts/captions.mjs`
writes the file after a render. `web/tests/motion.test.js` fails if the
file and the records differ.

## Card, journey, card

The film has one rhythm. Before each scene the camera travels through the
water to the scene's place: a journey of 2.5 seconds (`JOURNEY` in the
storyboard), the first a 2-second descent through the surface
(`OPENING`). Then the camera stands exactly still, and the scene's cards
fade in where they stand over half a second (`FADE`), hold while the line
is said and read, and fade out before the next journey; the last card
stays to the end. No card moves, grows or turns, none is on screen while
the camera travels, and no two scenes are on at once: each scene's host in
`motion/index.html` is on for its card only.

A scene's `seconds` in the storyboard is its journey and its card. A card
lasts at least as long as its line, started 0.3 seconds in (`VOICE_AT`),
with 1.5 seconds after it (`AFTER`) and the fade out, and long enough to
read its words at about four a second; scene 9, with the most words, is 19
seconds long for that reason.

The cards fade one by one (`motion/lib/cues.js`), never through the scene's
root: in Chrome, an element whose ancestor is fading is cut off from what
lies behind it, so liquid glass faded through its scene would lose its
frost for the length of the fade.

### The journeys

The camera (`motion/lib/camera.js`) moves in a flat world of water units,
at a fixed distance and with a fixed field of view; each journey
(`motion/lib/plan.js`, `go`) is eased at both ends, so it sets off and
arrives at rest. As it travels, each of the water's objects moves across
the frame by the camera's travel over the object's depth
(`motion/lib/shoal.js`), so the near ones pass faster than the far, and the
site's particles slower still (`motion/lib/field.js`). The water's focus
racks: soft behind a card, sharper while the camera travels.

| Before scene | Direction | Before scene | Direction |
|---|---|---|---|
| 1 | down, through the surface | 7 | left |
| 2 | down | 8 | down and to the right |
| 3 | right | 9 | down |
| 4 | down and to the right | 10 | right |
| 5 | down | 11 | up and to the right |
| 6 | down and to the left | 12 | up, through the surface |

### Pictures that act out the voice

Each voice line is spoken whole, at its natural pace, and timed phrase by
phrase: the storyboard's `said` holds the line's length and when each
phrase starts (`phrasesOf` splits a line after each comma, full stop,
colon, semicolon, question or exclamation mark). `motion/scripts/voice.mjs`
measures it: each phrase's share of the line's phonemes, with a pause after
it by its last mark (0.48 seconds after a full stop, 0.40 after a colon,
0.22 after a comma), predicts where it starts; FFmpeg's `silencedetect`
(-38 dB, 0.10 seconds) finds the pauses in the speech, and a pause that
ends within 0.4 seconds of a prediction is where that phrase starts. A
phrase run on from the one before, with no pause, shares the speech
between the pauses on either side by its phonemes. The committed `said` is
what the film uses, so a still never depends on a generated file; the
script stops when a measurement drifts more than 0.15 seconds from it, or
a line no longer fits its card, and prints the lines to paste.

The compositions key what happens inside a card to those cues
(`VivomeCue.cue(scene, phrase)`), and so do the score's notes: in scene 7
each cell's outline settles as its rung is said; in scene 9 the grid fills
as the voice says how often VivOME answers, and its right answers turn
solid as it says how often they are right.

### What closes one card opens the next

Nothing crosses a journey. Instead, each card closes with a picture at its
edge, in its last moments before it fades, and the next card opens on the
same picture in the same spot (`RHYMES` in `motion/lib/plan.js`; the test
checks each pair is within 40 pixels), so the eye carries it across.

| Between | Closes on, and opens on |
|---|---|
| 1 and 2 | The protein cell, its bars folded back into it |
| 2 and 3 | The first cell's column of proteins, grown to full height; it becomes the matrix's first column |
| 3 and 4 | The measured values, lifted off as dots and gathered; the atlas streams out of them |
| 4 and 5 | A band of the atlas's cells; it flows into the wordmark |
| 5 and 6 | A row of tiles under the card; it rises and fills down into the matrix |
| 6 and 7 | The encoders' merged answers; the map grows out of them |
| 7 and 8 | Two strokes from the last cell's best guess; they start the two currents |
| 8 and 9 | A block of a hundred particles; it becomes the first result's grid |
| 9 and 10 | A row of dots under the results; it rises to become the row of methods |
| 10 and 11 | The squares gathered into a file; the example file in the window |
| 11 and 12 | A few landed cells rising; bubbles that burst at the wordmark |

## The page

| File | Role |
|---|---|
| `web/motion.html` | the page: the shared header and footer, the film in a native player (its controls, its poster, no autoplay), a strip of every scene, then one block per scene, the script and the method |
| `web/js/reel-frames.js` | the storyboard, pure: every scene's timing, words, notes and number slots, and the page's markup builders, the film's line and its warning among them |
| `web/js/reel.js` | loads the manifest, the manuscript data and the stills' and the film's sidecars, and fills the page |
| `web/css/reel.css` | the page's layout, for laptop and desktop screens |
| `web/motion/frames/NN-<scene>.webp` | the stills, 1920 by 1080, rendered by `motion/scripts/stills.mjs` |
| `web/motion/frames/index.json` | the sidecar: each still's time in the film and every number baked into it, with its record, file and field |
| `web/motion/film/vivome.mp4` | the film, 1280 by 720, H.264 and AAC, streamable, under 24 MB (Cloudflare Pages takes files up to 25 MiB), written by `motion/scripts/film.mjs` |
| `web/motion/film/poster.webp` | the player's poster: scene 1's card, at its still's time |
| `web/motion/film/index.json` | the film's sidecar: its sha256, size and length, the release it was made for, and every number baked into it (on screen or spoken), with its record, file and field |
| `web/tests/reel.test.js` | the checks below |

The storyboard is one copy, read by the page and by the render pipeline,
so the notes beside a still always describe the frame that was rendered.

## Numbers

No number is typed into the storyboard, the compositions or the page. A
slot names its record: `{ms:key}` a record of `web/data/manuscript.json`,
`{fact:key}` a manifest fact (the model's name and the atlas version). The
page shows each through the site's guards (`msFact`, `factText`), so a
record that is not measured reads Pending; the sealed test on sorted cells
does, on purpose.

A number baked into a render would bypass that guard, so:

- `motion/scripts/prepare.mjs` reads every slot from the two data files at
  render time, through the same formatters, into `motion/build/facts.js`,
  and refuses files built for different releases;
- the compositions fill their slots from it (`motion/lib/slots.js`); a
  pending record shows Pending;
- `motion/scripts/stills.mjs` writes the sidecar with each still's numbers
  and their sources, and `motion/scripts/film.mjs` the film's, with every
  number it shows or speaks;
- `web/tests/reel.test.js` fails when a sidecar value no longer matches its
  record (render the stills, or the film, again), and the page marks such a
  still, or the film, too. For the film it also fails when its length is
  not the storyboard's, its release is not the data's, or the file is not
  the one its sidecar describes (its size and sha256).

The test also checks that the scenes add up to the film's length, that every
slot names a record, that no percentage or decimal is typed, that the copy
keeps the site's rules (no em dashes, none of the words that wait for
evidence), that every caveat is one of the Manuscript page's, that each
composition shows its scene's words and slots at its place in the film, on
its scene's card kind, and that the film keeps one white background. It
checks the rhythm: a journey, then a card, with no card on screen while the
camera travels and none overlapping another; the camera: still for every
card, each journey eased at both ends and in its own direction, the last
one up, with the depth gauge and the waterline where they belong; the
water: every object at a constant size and depth, moving by the camera's
travel over its depth and wrapping only out of sight; the cards: no
composition moves, scales or turns anything, and each fades its own cards;
the voice: every line at its natural pace, its phrases in order inside its
card; and that each card opens where the last one closed.

The voice-over speaks the same slots, filled from the same records when the
film is made (`motion/scripts/voice.mjs`); a spoken number is never typed.

## The tools, and why each

| Tool | Used for | Why |
|---|---|---|
| HyperFrames (HeyGen, Apache 2.0) | the film: one root composition and a composition per scene; the stills | scenes are plain HTML and CSS, seeked frame by frame in headless Chrome, so the site's own stylesheet and code render as they are |
| GSAP | the words and diagrams inside each scene | HyperFrames' default runtime: paused timelines it can seek |
| three.js, with the site's water | the dive under every scene: `web/js/biocells.js` and `web/js/water.js`, unchanged | the film's water is the site's: the same cells and threads in the same gel, with its rain and wake ripples. The flow and ink effects are not used: their caustic lines and coloured ink would change the background's colour |
| three.js points | the atlas in 3D in scenes 4 and 11 (`motion/lib/map3d.js`): the reference's own cells at their coordinates in the atlas's projection, in the atlas palette, with the Atlas page's looks for an answer | the real atlas, turning slowly, needs real depth; the same three.js r128 the site uses |
| The site's particle field | `web/js/background.js`'s cells, strands, network and flow field, drawn by `motion/lib/field.js` | background.js moves each particle a step per animation frame with an unseeded random start; the film needs a picture that is a function of time, so the drawing is the same and the positions are computed |
| Manim | scene 7, the answers: the map, and for each cell an outline that narrows over it to its set of plausible types as its rung is said | outlines that move between sets and hold exactly the types inside are geometry, which Manim draws and morphs precisely, each on its own track of one timeline; it renders on a transparent background |
| FFmpeg | cutting Manim's QuickTime file into one frame per film frame; grading each still and writing it as WebP | Manim's own PNG sequence skips held frames, so its frame numbers would not be times |
| Canvas | the data pictures: the readout of one cell, the matrix and its sweeps, the encoders, the second opinion's currents and gate, the results' grid, bars and squares; and each card's closing and opening pictures | drawn from `web/data/workflow.json` and `web/data/manuscript.json` on each seek, as the Workflow and Manuscript pages draw them |
| Kokoro-82M, through HyperFrames' `tts` | the voice-over | a local, openly licensed text-to-speech model: the script never leaves this machine |
| numpy and soundfile | the music: the ambient bed and its musical cues, synthesised in `motion/audio/score.py` | made in code, so no music or sample is downloaded and nothing needs a licence |
| FFmpeg | the mix: each voice line at its time, the music ducked under the voice by a sidechain compressor, the whole at -16 LUFS; then the draft and the copy for sending | one tool for the sound and the encodes |

Lottie is not used: it plays animations designed elsewhere, and the film
has none; everything here is data, 3D or exact geometry. Remotion is not
used because of its company licence.

### The voice, and what it is made with

| Part | Version | Licence |
|---|---|---|
| Kokoro-82M (hexgrad), the voice model, as `kokoro-v1.0.onnx` and `voices-v1.0.bin` from kokoro-onnx's `model-files-v1.0` release | v1.0 | Apache 2.0 |
| The voice, `af_heart` ("Heart", American English) | in `voices-v1.0.bin` | Apache 2.0, with the model |
| kokoro-onnx, which runs it | 0.6.1 | MIT |
| onnxruntime | 1.31.0 | MIT |
| espeak-ng, the phonemizer kokoro-onnx loads | as bundled by espeakng-loader 0.2.4 | GPL-3.0 (the tool; the speech it helps make is not covered) |
| HyperFrames' `tts` command, which calls it | 0.8.169 | Apache 2.0 |
| numpy and soundfile, for the score | 2.5.4, 0.14.0 | BSD-3-Clause |
| FFmpeg, for the mix and the encodes | 9.0.2 (conda-forge) | LGPL and GPL |

HyperFrames downloads the model files once, about 350 MB, into
`%USERPROFILE%\.cache\hyperframes\tts\`, outside the repository. Every
line is spoken at its natural pace and starts 0.3 seconds after its card
appears; each card is long enough for its line (see "Card, journey,
card"), so no line is hurried and the words never change.

The voice says the name as one word, "Vivome", VIV-ohm, as in genome and
proteome; the screen keeps the wordmark VivOME. Written VivOME, the
phonemizer spells it out (`vˈaɪv ˌoʊˌɛmˈiː`, "vive O M E"); written Vivome it
gives `vˈɪvoʊm`, one word stressed on its first syllable, like `dʒˈiːnoʊm`
(genome) and `pɹˈoʊɾoʊm` (proteome). `motion/scripts/voice.mjs` reads every
line through the same phonemizer before speaking (`motion/audio/phonemes.py`),
records the phonemes in its report, and stops if the name would come out
any other way.

## The project: `motion/`

`motion/` is the film's own project, with its own `package.json`, so `web/`
keeps no build step.

| Path | Role |
|---|---|
| `motion/index.html` | the root composition: the film's length, the water, the frost, the twelve scene hosts (each on for its card only), the time code and the depth gauge |
| `motion/compositions/sNN-<scene>.html` | one scene each: its cards, words and pictures, and its GSAP timeline keyed to its cues: opacity and reveals only |
| `motion/lib/dive.js` | each frame, on every `hf-seek`: the water, with its objects placed for the camera and one ripple field stepped on a 60 a second grid from the film's start, so any frame renders the same on its own; the particles' density, network and rise, held for each card and eased on each journey; the focus; the waterline; the time code and the depth gauge; the pictures of the card on screen |
| `motion/lib/camera.js` | the camera, pure: each scene's place, the journeys between them, the camera's place at any time (exactly still during a card), how settled it is, the waterline, the depth gauge, and a journey's direction in words |
| `motion/lib/plan.js` | each scene's journey and what it asks of the water: particles, rise, and the drops (rain, wakes, a splash) that ring the one ripple field during its card; the water's surfaces; and where each card closes and the next opens (`RHYMES`) |
| `motion/lib/shoal.js` | the water's objects, each at a fixed depth and size, placed in closed form for the camera's place and the time; the site's own meshes and materials (through `specimen()` in `web/js/biocells.js`), with its table of kinds (kept the same by the test) |
| `motion/lib/cues.js` | fades each scene's cards in and out where they stand, and gives each phrase's cue |
| `motion/lib/map3d.js` | the atlas in 3D as three.js points, and the same camera without three.js for the pictures around it |
| `motion/lib/field.js` | the site's particle field, as a function of time, moved with the camera; every particle keeps its size |
| `motion/lib/scenes.js` | the pictures of each card, keyed to its cues, and its closing and opening pictures; the Manim frames |
| `motion/lib/slots.js` | fills number slots; counts them up with the landing's maths |
| `motion/lib/film.css` | the film's type and objects, from the site's tokens |
| `motion/manim/answers.py` | the Manim scene for scene 7: each cell's outline narrows through the stages `motion/scripts/prepare.mjs` works out from the type hierarchy, settling on its cue, on whole frames of the film |
| `motion/scripts/hf.mjs` | runs the HyperFrames CLI with FFmpeg and Chrome found, and its telemetry, update checks and skill installs off |
| `motion/scripts/prepare.mjs` | copies the site's code into `motion/vendor/` and writes `motion/build/` |
| `motion/scripts/manim.mjs` | renders the Manim scene and cuts it into frames |
| `motion/scripts/stills.mjs` | snapshots each scene's still, grades it and writes the sidecar |
| `motion/scripts/voice.mjs` | speaks each scene's line with Kokoro at its natural pace, times its phrases, and checks both against the storyboard; its report is `motion/build/audio/voice.json` |
| `motion/audio/score.py` | the music, synthesised in code: one continuous bed whose chords change on the journeys, and its cues |
| `motion/audio/phonemes.py` | the phonemes Kokoro will read for each line, so the voice script can check the name |
| `motion/scripts/film.mjs` | renders the whole film, then the voice, the score, the mix and the two encodes |

`motion/vendor/`, `motion/build/` (the generated sound included),
`motion/.hyperframes/` and `motion/renders/` are written by the scripts and
gitignored, as is `motion/node_modules/`.

## Rendering

The tools are set up once ([setup-windows.md](../setup-windows.md), "Motion
tools"). From `motion/`:

```bash
npm install          # HyperFrames, GSAP and three.js r128, pinned
npm run stills       # prepare, Manim, then the twelve stills and their sidecar
npm run film         # the whole film with its sound: a 720p draft and a copy to send
npm run preview      # HyperFrames Studio, to watch the film play
npm run lint         # HyperFrames' checks of the compositions
```

`npm run stills` takes under a minute. To render only some scenes, run
`npm run data`, then `motion/scripts/stills.mjs` with `--only <scene id>`
(comma-separated); the other stills and their sidecar entries stay. Commit
the stills and `web/motion/frames/index.json` together.

`npm run film` takes about four minutes on this PC. HyperFrames renders
the picture at the composition's 1920 by 1080 (`renders/vivome-draft-1080.mp4`,
silent); FFmpeg then writes `renders/vivome-draft.mp4`, 1280 by 720 with the
sound in AAC, and `renders/vivome-draft-share.mp4`, about 20 MB, for
sending (its picture rate is set from the film's length to keep it near
that size). Those stay in the gitignored `motion/renders/`.

It also writes the site's copy, `web/motion/film/vivome.mp4`: the same
picture and sound in two passes at the best rate that keeps it under 24 MB
(here about 960 kbit/s of picture and 128 of sound), with `+faststart` so
it plays as it loads; its poster; and its sidecar. The numbers a render
bakes in are kept beside it (`renders/<name>-1080.facts.json`), so the
sidecar describes the picture, not the data as it is when the film is
encoded; `--skip-render` remixes the sound over the last picture, and
`--name` names the drafts. Commit the film, its poster and its sidecar
together, as plain files (no Git LFS at this size).

To change the film: edit the scene in `web/js/reel-frames.js` (words,
timing, notes), then its composition, and its host in `motion/index.html`
if its timing changed; the test checks they agree. If its voice line
changed, run `motion/scripts/voice.mjs` and paste the `said` it prints.
Render the stills again.

## The script

Number slots are written as they are in the storyboard; the page and the
render show each record's value, or Pending. The voice-over runs at about
two words a second, read by Kokoro's `af_heart` voice, which says the name
as one word, Vivome.

### 1. The surface (0:00 to 0:10, 10 s)

Chapter: the problem. Made with HyperFrames, GSAP, three.js water (rain), canvas.

- **On screen:** eyebrow "Single-cell proteomics"; headline "Proteins, measured one cell at a time."; caption "One cell of the PBMC240 example file".
- **Voice-over:** "Mass spectrometry can now measure the proteins inside single cells, one cell at a time."
- **Cards:** White cards: the site's sheet, with its soft blue halo.
- **Camera:** Descends through the surface in the rain, then stands still while the card is on.
- **Transition:** Opens from white light as the camera comes down through the surface. At the close the bars fold back into the cell, which settles at the top of the card, where scene 2 opens on it.
- **Water:** Rain on the surface: each drop sends rings across the white gel, and a fine white waterline runs along the top.
- **Particles:** Sparse. Cells and molecules drift up towards the light, each keeping its size.
- **Sound:** A low pad fades in from silence; one soft piano note as the title lands.
- **Drawn from data:** One cell of the PBMC240 example file: its proteins as bars, long where much was measured, a striped stub where nothing was (web/data/workflow.json). Two more cells queue behind it as the voice says one cell at a time.

### 2. Without names (0:10 to 0:23, 13 s)

Chapter: the problem. Made with HyperFrames, GSAP, three.js water (still), canvas.

- **On screen:** headline "But they arrive without names."; line "Few protein datasets come labelled, and every lab detects a different set of proteins."; tag "Unnamed".
- **Voice-over:** "But those cells arrive without names. Labelled protein references are few, and every lab detects a different set of proteins."
- **Cards:** Liquid glass: the site's frosted glass over the gel.
- **Camera:** Travels down through the particles, then stands still.
- **Transition:** Opens on the cell where scene 1 left it. At the close the first cell's column of proteins grows to full height, where scene 3's matrix begins.
- **Water:** The same white gel, still; the waterline is far above now.
- **Particles:** Protein cells in green, each given an empty name tag as the voice says they have no names, then each its own short column of the proteins measured in it.
- **Sound:** The pad carries on, a little lower, as the camera goes under.
- **Drawn from data:** Each cell's column marks the proteins measured in one cell of the PBMC240 example file (web/data/workflow.json): the sets differ from cell to cell.

### 3. Mostly missing (0:23 to 0:37, 14 s)

Chapter: the problem. Made with HyperFrames, GSAP, three.js water (still), canvas.

- **On screen:** headline "And each one is only partly seen."; number "{ms:wf_missing_share}"; label "of the values in one public file are missing"; caption "PBMC240, the example file on the Workflow page"; number "{ms:ds_fulcher2026_proteins_per_cell}"; label "proteins measured per cell in Fulcher 2026, the median"; caption "VivOME reads {ms:gs_size} genes."
- **Voice-over:** "And each cell is only partly seen. Much of a protein matrix is empty."
- **Cards:** White cards: the site's sheet, with its soft blue halo.
- **Camera:** Travels to the right through the particles, then stands still.
- **Transition:** Opens on the column scene 2 left, which takes its place as the matrix's first. At the close the measured tiles lift off as dots and gather at the matrix's right edge, where scene 4's atlas begins.
- **Water:** The white gel; the far cells are soft behind the cards.
- **Particles:** The molecular network loses links as values drop out.
- **Sound:** The pad thins to one held note as the missing values fall away.
- **Drawn from data:** The matrix: the PBMC240 example file's own values, one column per cell and one row per protein, as the Workflow page shows them (web/data/workflow.json). Each tile lights as it is read; as the voice says much of it is empty, the missing ones fall away.

### 4. RNA has names (0:37 to 0:49, 12 s)

Chapter: the solution. Made with HyperFrames, GSAP, three.js atlas, three.js water (still).

- **On screen:** headline "RNA atlases already name their cells."; number "{ms:ref_cells}"; label "RNA cells, each one labelled"; caption "in {ms:ref_classes} blood and immune cell types, from Tabula Sapiens".
- **Voice-over:** "Single-cell RNA is different. Its atlases are large, and every cell in them has a name."
- **Cards:** Liquid glass: the site's frosted glass over the gel.
- **Camera:** Travels down and to the right, then stands still.
- **Transition:** Opens on scene 3's dots, gathered as an orange cloud. At the close a band of the atlas's cells gathers along the map's top edge, where scene 5's wordmark forms from them.
- **Water:** The same white gel. The cells pass at their own depths as the camera travels, the near ones faster.
- **Particles:** RNA strands in red and gold thread through the shoal.
- **Sound:** A warm chord: the first hint of the theme.
- **Drawn from data:** The atlas in 3D, turning slowly: a sample of the reference's own cells at their coordinates in the atlas's projection (web/data/workflow.json). They stream out of the cloud as RNA, in orange; as the voice says every cell has a name, each takes its type's colour in the atlas palette and the big types are named.

### 5. VivOME (0:49 to 1:07, 18 s)

Chapter: the solution. Made with HyperFrames, GSAP, three.js water (wake), canvas.

- **On screen:** wordmark "VivOME"; headline "Trained on RNA. Read on protein."; line "No protein labels, no paired cells, no retraining on your data."; label "Labelled RNA"; label "Your protein cells"; label "{ms:gs_size} genes link the two"; caption "It carries the names across. It never mixes the two kinds of data."
- **Voice-over:** "VivOME learns blood cell types from labelled RNA alone, then reads each protein cell against that reference. No protein labels, no paired cells, and no retraining on your data."
- **Cards:** White cards: the site's sheet, with its soft blue halo.
- **Camera:** Travels down, then stands still on the wordmark and the idea.
- **Transition:** Opens on scene 4's band of cells, which flows into the wordmark as it forms. At the close dots leave the link and line up as a row of tiles under the card, where scene 6's matrix fills from.
- **Water:** A slow wake ripples through the white gel as the wordmark forms.
- **Particles:** The network links up across the frame as the link forms; dots run along it from the RNA side to the protein side.
- **Sound:** The theme enters in full: a rising arpeggio as the wordmark appears.

### 6. Built for gaps (1:07 to 1:21, 14 s)

Chapter: what is new. Made with HyperFrames, GSAP, three.js water (still), canvas.

- **On screen:** headline "Built for missing values."; point "It knows which proteins were never measured."; point "It scales each protein within your file."; point "It borrows from similar cells in the same file."; point "{ms:wf_members} encoders answer together."
- **Voice-over:** "It is built for gaps: it knows which proteins were never measured, scales each one within your file, and asks {ms:wf_members} encoders to answer together."
- **Cards:** Liquid glass: the site's frosted glass over the gel.
- **Camera:** Travels down and to the left, then stands still.
- **Transition:** Opens on the row of tiles from scene 5, which rises and fills down into the matrix. At the close the encoders' merged answers gather at the matrix's left edge, where scene 7's map grows from.
- **Water:** The white gel, clearer than in scene 3; the far cells are soft behind the cards.
- **Particles:** The rows stream into the encoders inside the card, one for each of the served model's members, and their answers merge into one.
- **Sound:** Soft tones, one per encoder, resolving into one chord.
- **Drawn from data:** The matrix: the same cells and proteins as scene 3. As each point is said, its step: a mask marks each gap; a bright band sweeps down as each protein is scaled within the file, then across as each cell borrows from similar cells (web/data/workflow.json).

### 7. Honest answers (1:21 to 1:35, 14 s)

Chapter: what is new. Made with Manim, HyperFrames, GSAP, three.js water (still), canvas.

- **On screen:** headline "When unsure, it says so."; label "Cell type"; label "Group"; label "Lineage"; label "No answer, and the reason"; caption "Cells of the PBMC240 example file, and the answers VivOME gave them."
- **Voice-over:** "Every cell gets the most precise answer the evidence allows: a cell type, its group, its lineage, or no answer, and the reason why."
- **Cards:** White cards: the site's sheet, with its soft blue halo.
- **Camera:** Travels to the left, then stands still on the reference map.
- **Transition:** Opens on scene 6's merged answers, out of which the map grows. At the close the last cell's best guess splits into two strokes that run to the map's edge, where scene 8's two currents start.
- **Water:** Still gel, so the diagram reads cleanly.
- **Particles:** Few and slow, kept to the edges.
- **Sound:** Descending notes, one per rung, and a soft stop on no answer.
- **Drawn from data:** Manim draws the reference map and four real cells of the example file. As the voice names each rung, that cell's outline narrows from the widest set its types belong to down to its set of plausible types, or widens when several types fit, and its answer shows (web/data/workflow.json).

### 8. A second opinion (1:35 to 1:47, 12 s)

Chapter: what is new. Made with HyperFrames, GSAP, three.js water (wake), canvas.

- **On screen:** headline "One best guess, with a second opinion."; label "The encoder"; label "Correlation to each RNA type's average"; label "Used only when your file agrees with the encoder"; label "Best guess"; chip "New in {fact:model_name}".
- **Voice-over:** "Its best guess adds a second opinion, used only when your file agrees with the encoder."
- **Cards:** Liquid glass: the site's frosted glass over the gel.
- **Camera:** Travels down and to the right, then stands still on the two currents.
- **Transition:** Opens on scene 7's two strokes, which start the two currents. At the close the particles pack into a block of a hundred, where scene 9's first result fills from.
- **Water:** A wake follows the two currents through the white gel.
- **Particles:** Particles flow along both currents and gather at the gate; as the voice says when the second opinion is used, the gate appears, a meter fills to its mark, the gate opens, and they run on as one.
- **Sound:** Two lines of melody braid into one.

### 9. On real protein data (1:47 to 2:06, 19 s)

Chapter: the results. Made with HyperFrames, GSAP, three.js water (still), canvas.

- **On screen:** headline "Checked against real data."; label "Fulcher 2026"; number "{ms:committed_fulcher}"; label "of cells given an answer"; number "{ms:correct_fulcher}"; label "of those answers right, at the level stated"; label "Khoury 2026"; number "{ms:khoury_lymphoid}"; label "of lymphoid cells put in the lymphoid lineage"; number "{ms:khoury_myeloid}"; label "of myeloid cells put in the myeloid lineage"; caption "Development: these data were used while VivOME was built. Post-hoc: their labels had been read before."
- **Caveats shown:** development, post-hoc.
- **Voice-over:** "On real blood protein data, here is how often it answers, and how often those answers are right."
- **Cards:** White cards: the site's sheet, with its soft blue halo.
- **Camera:** Travels down to the deepest point of the dive and stands still there.
- **Transition:** Opens on scene 8's block, which becomes the first result's grid. At the close the grid's squares slide into a row under the results, where scene 10's methods line up.
- **Water:** The same white gel; at the deepest point the far cells are most softly blurred.
- **Particles:** Dense: cells and strands drift around the cards at their own depths.
- **Sound:** The music settles on a low, slow bass pulse under the numbers.
- **Drawn from data:** Each result from its own record (web/data/manuscript.json): as the voice says how often VivOME answers, a grid of a hundred squares fills to that share; as it says how often those answers are right, the right ones turn solid. Khoury 2026's two lineages fill as bars.

### 10. Against established methods (2:06 to 2:25, 19 s)

Chapter: the results. Made with HyperFrames, GSAP, three.js water (still), canvas.

- **On screen:** headline "Measured against established methods."; line "On real protein data, VivOME is level with the best of them and ahead of the rest."; number "{ms:bm_khoury_baseline_favour} of {ms:bm_khoury_baseline_runs}"; label "baseline runs favour VivOME on Khoury 2026"; number "{ms:bm_fulcher_favour} of {ms:bm_fulcher_pairings}"; label "paired comparisons favour VivOME on Fulcher 2026"; caption "Still weak: CD8 T cells and dendritic cells, for every method tested."; caption "A sealed test on sorted cells: {ms:open_sorted_test}".
- **Caveats shown:** post-hoc, in-sample, pending.
- **Voice-over:** "Against established methods, on real protein data, it is level with the best and ahead of the rest. Where it is still weak, it says so."
- **Cards:** Liquid glass: the site's frosted glass over the gel.
- **Camera:** Travels to the right along the floor, then stands still.
- **Transition:** Opens on scene 9's row, which rises to become the row of methods. At the close the squares gather into a file, where scene 11 opens on its file.
- **Water:** The same white gel, on the floor of the dive.
- **Particles:** The methods come in one after another, each with its name: scANVI, MaxFuse, scGLUE, Harmony, Seurat, PCA and correlation.
- **Sound:** The pulse continues under a lighter counter-melody: the rise begins.
- **Drawn from data:** One square for each baseline run and each paired comparison, filled where it favours VivOME, from the Manuscript page's records (web/data/manuscript.json); the types where every method is still weak as dashed rings in their atlas colours.

### 11. In your browser (2:25 to 2:39, 14 s)

Chapter: use it. Made with HyperFrames, GSAP, three.js atlas, three.js water (wake).

- **On screen:** headline "Label your own data."; line "Send a DIA-NN, FragPipe or CSV file from the Atlas page. Your cells land on the reference, each with its answer or the reason for none."; chip "The PBMC240 example file"; caption "Answered by {fact:model_name}, atlas {fact:atlas_version}".
- **Voice-over:** "It runs online. Send your file from the Atlas page, and your cells land on the map, each with its answer."
- **Cards:** White cards: the site's sheet, with its soft blue halo.
- **Camera:** Travels up and to the right towards the surface, then stands still on a browser window.
- **Transition:** Opens on scene 10's file, now the example file in the window. At the close a few landed cells rise to the window's top edge, where scene 12's bubbles start.
- **Water:** A wake: the file's cells leave a trail of ripples as they fly into the atlas.
- **Particles:** The file's cells fly out of it in 3D, with trails, and land in their places.
- **Sound:** Bright plucks as each cell lands; the theme returns in full.
- **Drawn from data:** The map is the reference sample in 3D, turning slowly, and the cells are the PBMC240 example file's, landing with the answers the served model gave them, in the Atlas page's looks (web/data/workflow.json).

### 12. Into the light (2:39 to 2:49, 10 s)

Chapter: use it. Made with HyperFrames, GSAP, three.js water (rain), canvas.

- **On screen:** wordmark "VivOME"; headline "No cell placed without evidence."; chip "Explore the atlas"; chip "Label your data"; caption "vivome-atlas.pages.dev".
- **Voice-over:** "Bring your protein cells up into the light. VivOME: no cell placed without evidence."
- **Cards:** Liquid glass: the site's frosted glass over the gel.
- **Camera:** Rises through the surface, then stands still under the end card.
- **Transition:** Opens on scene 11's cells, which rise as bubbles and burst at the wordmark as it forms. The end card stays to the end.
- **Water:** The waterline lies low in the frame now the camera has surfaced; rain rings the water under the end card.
- **Particles:** Bubbles rise and burst at the wordmark, then the frame clears.
- **Sound:** The music swells as the camera surfaces and resolves on a bright final chord, then fades to silence on the end card.
