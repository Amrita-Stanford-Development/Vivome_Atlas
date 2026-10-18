# The Motion page and the film

`web/motion.html` is the storyboard for a film about VivOME: twelve scenes
over 120 seconds, each shown as a still rendered from the film itself,
beside its on-screen words, voice-over, motion notes and sound cue. The
film is made in its own project, `motion/`, with HyperFrames and other
motion tools; the page shows what it renders.

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
ink. Depth shows in the objects instead. Going down, the view narrows so
the cells are larger, the camera drifts on through them faster, the far
ones are softly blurred, and the particles grow; on the way up, all of that
eases back. A time code and a depth gauge in every frame carry the motif.
The end breaks the surface: "No cell placed without evidence."

Every word and diagram sits on a card, so it reads over the moving cells,
even at 720p: the site's white card with its blue halo (`.sheet`) in odd
scenes, its liquid glass (`.liquid`) in even ones, both straight from
`web/css/page.css`. The storyboard names each scene's card (`card`), the
page lists it among the scene's notes, and the test checks that each
composition uses its scene's kind and no other.

The film is one continuous move, with no cut and no fade between scenes.
The water, the cells, the particles and the camera never reset at a
scene's start: the depth, the particles' density and the water's rise
follow smooth curves through the scenes' values, one ripple field runs the
whole film, and one camera travels through a world in which each scene's
cards have their own place. The camera carries each scene's cards out of
the frame while it carries the next scene's in, and between the two
something of the outgoing scene becomes something of the incoming one (see
"The camera and the morphs" below).

The film's sound is a voice-over speaking each scene's line and a soft
music bed under the whole film, one continuous piece that rises towards the
end; there are no sound effects. The stills on the page are silent; the
sound is in the rendered film only.

## The camera and the morphs

Each scene's cards are a plane in one world (`motion/lib/plan.js`, `at`:
a place in the scenes' own pixels, with depth), and the camera
(`motion/lib/camera.js`) travels from plane to plane on one path. While a
scene plays, the camera makes a slow move of its own (`move`): a lateral
pan, a push in or a slow pull back, with a turn of a degree or two that
reads as a gentle orbit, kept small enough that every card stays in the
frame. Between scenes it travels on to the next plane, setting off 0.3
seconds before a scene ends and arriving 1.9 seconds into the next. The
path is a cubic Hermite curve through those keys whose speed carries on
through each key, so the camera never stops dead, never jumps and never
shakes; the one fast move is the pull back from scene 10 to the Atlas
window.

Each frame, `motion/lib/dive.js` sets every scene's host to where the
camera sees its plane (a CSS transform: a move, a perspective turn and a
scale), so the cards sit in the scene's space and move with the camera.
Each host lasts 1.5 seconds into the next scene (`HANDOVER` in the
storyboard); the test checks that each scene's cards are out of the frame
when its host starts and when it ends, so nothing appears or vanishes in
view. The water moves with the camera too, which gives the parallax: the
water's own camera follows the film camera's moves aside and up (with
their slow part taken out, so it never leaves the cells), a push in
carries it on through the cells, and the site's particles drift at about a
tenth of the camera's speed, each at its own pace. The focus racks: while a
scene plays the cells behind its cards go soft, and as the camera travels
they sharpen. The cards themselves are not blurred: a CSS blur on them
would switch off the liquid glass's frost.

The morphs (`motion/lib/bridges.js`) are drawn on one canvas over the
scenes, in the world: each end is a place in a scene's layout, projected
through the camera at that moment, so it moves with its scene.

| Between | The morph |
|---|---|
| 2 and 3 | The first protein cell of scene 2 stays as the camera sets off, loses its empty tag, and opens into its column of scene 3's matrix, one tile per protein, from the example file's own values |
| 3 and 4 | The missing values have fallen away; the measured tiles lift off as dots, turn from protein to RNA, and gather in front of the camera, where scene 4's atlas forms from them in 3D |
| 4 and 5 | Cells of the atlas, in their types' colours, stream into the VivOME wordmark, which forms as they arrive |
| 6 and 7 | The matrix's rows stream into the encoders, one for each member of the served model, which send points on to their places on scene 7's map |
| 7 and 8 | The ladder folds, and two currents leave it for the starts of scene 8's two paths |
| 9 and 10, 10 and 11 | The camera glides on; the result cards slide out of the frame as it pulls back to the Atlas window |
| 11 and 12 | The camera rises out of the map; the window drops away below and the end card comes into view as it surfaces |

## The page

| File | Role |
|---|---|
| `web/motion.html` | the page: the shared header and footer, a strip of every scene, then one block per scene, the script and the method |
| `web/js/reel-frames.js` | the storyboard, pure: every scene's timing, words, notes and number slots, and the page's markup builders |
| `web/js/reel.js` | loads the manifest, the manuscript data and the stills' sidecar, and fills the page |
| `web/css/reel.css` | the page's layout, for laptop and desktop screens |
| `web/motion/frames/NN-<scene>.webp` | the stills, 1920 by 1080, rendered by `motion/scripts/stills.mjs` |
| `web/motion/frames/index.json` | the sidecar: each still's time in the film and every number baked into it, with its record, file and field |
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
  and their sources;
- `web/tests/reel.test.js` fails when a sidecar value no longer matches its
  record (render the stills again), and the page marks such a still too.

The test also checks that the scenes add up to 120 seconds, that every
slot names a record, that no percentage or decimal is typed, that the copy
keeps the site's rules (no em dashes, none of the words that wait for
evidence), that every caveat is one of the Manuscript page's, that each
composition shows its scene's words and slots at its place in the film, on
its scene's card kind, and that the film keeps one white background. It
checks the camera: its path never jumps or lurches, frames each scene
while it plays, and has each scene's cards out of the frame at its host's
edges; and that the morphs start and end where the compositions draw their
pictures.

The voice-over speaks the same slots, filled from the same records when the
film is made (`motion/scripts/voice.mjs`); a spoken number is never typed.

## The tools, and why each

| Tool | Used for | Why |
|---|---|---|
| HyperFrames (HeyGen, Apache 2.0) | the film: one root composition and a composition per scene; the stills | scenes are plain HTML and CSS, seeked frame by frame in headless Chrome, so the site's own stylesheet and code render as they are |
| GSAP | the words and diagrams inside each scene | HyperFrames' default runtime: paused timelines it can seek |
| three.js, with the site's water | the dive under every scene: `web/js/biocells.js` and `web/js/water.js`, unchanged | the film's water is the site's: the same cells and threads in the same gel, with its rain and wake ripples. The flow and ink effects are not used: their caustic lines and coloured ink would change the background's colour |
| three.js points | the atlas in 3D in scenes 4 and 11 (`motion/lib/map3d.js`): the reference's own cells at their coordinates in the atlas's projection, in the atlas palette, with the Atlas page's looks for an answer | a flight through the real atlas needs real depth; the same three.js r128 the site uses |
| The site's particle field | `web/js/background.js`'s cells, strands, network and flow field, drawn by `motion/lib/field.js` | background.js moves each particle a step per animation frame with an unseeded random start; the film needs a picture that is a function of time, so the drawing is the same and the positions are computed |
| Manim | scene 7, the answers: the map, and an outline that narrows over it to each cell's set of plausible types | outlines that move between sets and hold exactly the types inside are geometry, which Manim draws and morphs precisely; it renders on a transparent background |
| FFmpeg | cutting Manim's QuickTime file into one frame per film frame; grading each still and writing it as WebP | Manim's own PNG sequence skips held frames, so its frame numbers would not be times |
| Canvas | the data pictures: the missing-value matrix and its sweeps, the second opinion's currents and gate; and the morphs between scenes | drawn from `web/data/workflow.json` on each seek, as the Workflow page draws them |
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
`%USERPROFILE%\.cache\hyperframes\tts\`, outside the repository. Each line
is fitted to its scene: it starts just after the scene does and ends before
the next. A line that runs long is spoken a little faster (at most 1.2
times), then given shorter pauses around it; the words never change. In
this draft every line fits: scene 5's is spoken at 1.08 times, the rest at
normal speed.

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
| `motion/index.html` | the root composition: 120 seconds, the water, the frost, the twelve scene hosts, the time code and the depth gauge |
| `motion/compositions/sNN-<scene>.html` | one scene each: its words, diagrams and GSAP timeline |
| `motion/lib/dive.js` | each frame, on every `hf-seek`: the scenes' hosts placed where the camera sees them; the water, with the cells and one ripple field stepped on a 60 a second grid from the film's start, so any frame renders the same on its own, and its camera following the film's; smooth curves through the scenes' values for depth, particles and rise; depth as the objects coming forward (a narrower view, the drift, the far cells blurred); the focus; the waterline; each scene's pictures kept drawn through its handover; the morphs; the motif |
| `motion/lib/camera.js` | the camera, pure: its keys from the plan, its eased path, how a scene's plane looks from it (and the CSS transform for that), where a point of a scene lands in the frame, how settled it is on a scene, and the waterline |
| `motion/lib/plan.js` | each scene's place in the world and the camera's move while it plays; what it asks of the water: particles, rise, and the drops (rain, wakes, a splash) that ring the one ripple field; the water's surface |
| `motion/lib/bridges.js` | the morphs between scenes, drawn over them in the world |
| `motion/lib/map3d.js` | the atlas in 3D as three.js points, and the same camera without three.js for the morphs |
| `motion/lib/field.js` | the site's particle field, as a function of time, moved with the camera |
| `motion/lib/scenes.js` | the data pictures and the Manim frames, on the same seek, and the places the morphs start and end |
| `motion/lib/slots.js` | fills number slots; counts them up with the landing's maths |
| `motion/lib/film.css` | the film's type and objects, from the site's tokens |
| `motion/manim/answers.py` | the Manim scene for scene 7: its outlines narrow through the stages `motion/scripts/prepare.mjs` works out from the type hierarchy, on whole frames of the film |
| `motion/scripts/hf.mjs` | runs the HyperFrames CLI with FFmpeg and Chrome found, and its telemetry, update checks and skill installs off |
| `motion/scripts/prepare.mjs` | copies the site's code into `motion/vendor/` and writes `motion/build/` |
| `motion/scripts/manim.mjs` | renders the Manim scene and cuts it into frames |
| `motion/scripts/stills.mjs` | snapshots each scene's still, grades it and writes the sidecar |
| `motion/scripts/voice.mjs` | speaks each scene's line with Kokoro and fits it to its scene; its report is `motion/build/audio/voice.json` |
| `motion/audio/score.py` | the music, synthesised in code: one continuous bed and its cues |
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

`npm run film` takes about three minutes on this PC. HyperFrames renders
the picture at the composition's 1920 by 1080 (`renders/vivome-draft-1080.mp4`,
silent); FFmpeg then writes `renders/vivome-draft.mp4`, 1280 by 720 with the
sound in AAC, and `renders/vivome-draft-share.mp4`, about 17 MB, for
sending. `motion/scripts/film.mjs` with `--skip-render` remixes the sound
over the last picture, and `--name` names the files. Renders stay in the
gitignored `motion/renders/` and are not on the site.

To change the film: edit the scene in `web/js/reel-frames.js` (words,
timing, notes), then its composition, and its host in `motion/index.html`
if its timing changed; the test checks they agree. Render the stills again.

## The script

Number slots are written as they are in the storyboard; the page and the
render show each record's value, or Pending. The voice-over runs at about
two words a second, read by Kokoro's `af_heart` voice, which says the name
as one word, Vivome.

### 1. The surface (0:00 to 0:08, 8 s)

Chapter: the problem. Made with HyperFrames, GSAP, three.js water (rain).

- **On screen:** eyebrow "Single-cell proteomics"; headline "Proteins, measured one cell at a time."
- **Voice-over:** "Mass spectrometry can now measure the proteins inside single cells, one cell at a time."
- **Cards:** White cards: the site's sheet, with its soft blue halo.
- **Camera:** Just under the surface, looking up; a slow push in as the film's one camera path begins.
- **Transition:** Opens from white light. The camera sinks on into scene 2, and the title card goes up and out of the frame with the surface.
- **Water:** Rain on the surface: each drop sends rings across the white gel, and a fine white waterline runs along the top.
- **Particles:** Sparse. Cells and molecules drift up towards the light.
- **Sound:** A low pad fades in from silence; one soft piano note as the title lands.

### 2. Without names (0:08 to 0:18, 10 s)

Chapter: the problem. Made with HyperFrames, GSAP, three.js water (still), canvas.

- **On screen:** headline "But they arrive without names."; line "Few protein datasets come labelled, and every lab detects a different set of proteins."; tag "Unnamed".
- **Voice-over:** "But those cells arrive without names. Labelled protein references are few, and every lab detects a different set of proteins."
- **Cards:** Liquid glass: the site's frosted glass over the gel.
- **Camera:** Sinks below the waterline and on among the cells: a slow push in with a gentle turn, the near cells passing faster than the far.
- **Transition:** As the camera sets off, the first cell stays, loses its empty tag and opens into its column of scene 3's matrix, one tile per protein, while the camera carries the matrix in.
- **Water:** The same white gel, still now; the waterline slides up out of sight.
- **Particles:** Protein cells in green drift past, each with an empty name tag.
- **Sound:** The pad carries on, a little lower, as the camera goes under.

### 3. Mostly missing (0:18 to 0:28, 10 s)

Chapter: the problem. Made with HyperFrames, GSAP, three.js water (still), canvas.

- **On screen:** headline "And each one is only partly seen."; number "{ms:wf_missing_share}"; label "of the values in one public file are missing"; caption "PBMC240, the example file on the Workflow page"; number "{ms:ds_fulcher2026_proteins_per_cell}"; label "proteins measured per cell in Fulcher 2026, the median"; caption "VivOME reads {ms:gs_size} genes."
- **Voice-over:** "And each cell is only partly seen. Much of a protein matrix is empty."
- **Cards:** White cards: the site's sheet, with its soft blue halo.
- **Camera:** A slow sideways track along the matrix, easing in a little as it goes.
- **Transition:** The missing values fall away. As the camera sets off, the measured tiles lift off as dots, turn from protein to RNA and fly ahead of it, to gather where scene 4's atlas forms.
- **Water:** The white gel. While the camera holds, the far cells go soft behind the cards; as it moves on, they sharpen.
- **Particles:** The molecular network loses links as values drop out.
- **Sound:** The pad thins to one held note as the missing values fall away.
- **Drawn from data:** The matrix: the PBMC240 example file's own values, one column per cell and one row per protein, as the Workflow page shows them (web/data/workflow.json). Each tile lights as it is read; striped tiles were not measured.

### 4. RNA has names (0:28 to 0:38, 10 s)

Chapter: the solution. Made with HyperFrames, GSAP, three.js atlas, three.js water (still).

- **On screen:** headline "RNA atlases already name their cells."; number "{ms:ref_cells}"; label "RNA cells, each one labelled"; caption "in {ms:ref_classes} blood and immune cell types, from Tabula Sapiens".
- **Voice-over:** "Single-cell RNA is different. Its atlases are large, and every cell in them has a name."
- **Cards:** Liquid glass: the site's frosted glass over the gel.
- **Camera:** Flies in through the atlas as it forms in 3D, then draws back and circles to see it whole.
- **Transition:** Cells of the atlas stream ahead of the camera into scene 5's wordmark, which forms from them.
- **Water:** The same white gel. The camera drifts on through the cells, which come closer and larger as it goes down.
- **Particles:** RNA strands in red and gold thread through the shoal.
- **Sound:** A warm chord: the first hint of the theme.
- **Drawn from data:** The atlas in 3D: a sample of the reference's own cells at their coordinates in the atlas's projection, coloured by type in the atlas palette, as the Atlas page draws them (web/data/workflow.json). They stream out of the dots from scene 3 as RNA, in orange, and take their type's colour as the types are named.

### 5. VivOME (0:38 to 0:50, 12 s)

Chapter: the solution. Made with HyperFrames, GSAP, three.js water (wake), canvas.

- **On screen:** wordmark "VivOME"; headline "Trained on RNA. Read on protein."; line "No protein labels, no paired cells, no retraining on your data."; label "Labelled RNA"; label "Your protein cells"; label "{ms:gs_size} genes link the two"; caption "It carries the names across. It never mixes the two kinds of data."
- **Voice-over:** "VivOME learns blood cell types from labelled RNA alone, then reads each protein cell against that reference. No protein labels, no paired cells, and no retraining on your data."
- **Cards:** White cards: the site's sheet, with its soft blue halo.
- **Camera:** A slow push in on the wordmark with a gentle turn, then on down to the link between the two sides.
- **Transition:** The wordmark forms from scene 4's cells as they arrive. Then the camera glides on and carries these cards out of the frame as scene 6's matrix comes in.
- **Water:** A slow wake ripples through the white gel as the wordmark rises.
- **Particles:** The network links up across the frame as the link forms; dots run along it from the RNA side to the protein side.
- **Sound:** The theme enters in full: a rising arpeggio as the wordmark appears.

### 6. Built for gaps (0:50 to 1:00, 10 s)

Chapter: what is new. Made with HyperFrames, GSAP, three.js water (still), canvas.

- **On screen:** headline "Built for missing values."; point "It knows which proteins were never measured."; point "It scales each protein within your file."; point "It borrows from similar cells in the same file."; point "{ms:wf_members} encoders answer together."
- **Voice-over:** "It is built for gaps: it knows which proteins were never measured, scales each one within your file, and asks {ms:wf_members} encoders to answer together."
- **Cards:** Liquid glass: the site's frosted glass over the gel.
- **Camera:** Tracks along the matrix from scene 3 as each step sweeps across it.
- **Transition:** Its matrix is scene 3's. As the camera sets off, its rows stream into the encoders, which send points on to scene 7's map.
- **Water:** The white gel, clearer than in scene 3; nearer cells drift larger past the camera, the far ones softly out of focus.
- **Particles:** The rows stream into the encoders, one for each of the served model's members.
- **Sound:** Soft tones, one per encoder, resolving into one chord.
- **Drawn from data:** The matrix: the same cells and proteins as scene 3. A mask marks each gap; a bright band sweeps down as each protein is scaled within the file, then across as each cell borrows from similar cells, as the Workflow page shows them (web/data/workflow.json).

### 7. Honest answers (1:00 to 1:12, 12 s)

Chapter: what is new. Made with Manim, HyperFrames, GSAP, three.js water (still), canvas.

- **On screen:** headline "When unsure, it says so."; label "Cell type"; label "Group"; label "Lineage"; label "No answer, and the reason"; caption "Cells of the PBMC240 example file, and the answers VivOME gave them."
- **Voice-over:** "Every cell gets the most precise answer the evidence allows: a cell type, its group, its lineage, or no answer, and the reason why."
- **Cards:** White cards: the site's sheet, with its soft blue halo.
- **Camera:** A slow push in on the reference map, with a slight turn.
- **Transition:** Points from scene 6's encoders land on the map as it appears. Each answer steps down the ladder in turn; at the end the ladder folds into two currents that fly on into scene 8.
- **Water:** Still gel, so the diagram reads cleanly.
- **Particles:** Few and slow, kept to the edges.
- **Sound:** Descending notes, one per rung, and a soft stop on no answer.
- **Drawn from data:** Manim draws the reference map and, for four real cells of the example file, an outline that narrows from the wider sets the cell's types belong to down to its set of plausible types, or widens when several types fit, with the sets and answers the served model gave them (web/data/workflow.json).

### 8. A second opinion (1:12 to 1:20, 8 s)

Chapter: what is new. Made with HyperFrames, GSAP, three.js water (wake), canvas.

- **On screen:** headline "One best guess, with a second opinion."; label "The encoder"; label "Correlation to each RNA type's average"; label "Used only when your file agrees with the encoder"; label "Best guess"; chip "New in {fact:model_name}".
- **Voice-over:** "Its best guess adds a second opinion, used only when your file agrees with the encoder."
- **Cards:** Liquid glass: the site's frosted glass over the gel.
- **Camera:** Tracks the two currents to the gate and on to the best guess.
- **Transition:** Its two currents start where scene 7's ladder folded into them. Then the camera sinks on to the deepest point.
- **Water:** A wake follows the two currents through the white gel.
- **Particles:** Particles flow along both currents and gather at the gate; a meter fills to its mark, the gate opens, and they run on as one.
- **Sound:** Two lines of melody braid into one.

### 9. On real protein data (1:20 to 1:32, 12 s)

Chapter: the results. Made with HyperFrames, GSAP, three.js water (still).

- **On screen:** headline "Checked against real data."; label "Fulcher 2026"; number "{ms:committed_fulcher}"; label "of cells given an answer"; number "{ms:correct_fulcher}"; label "of those answers right, at the level stated"; label "Khoury 2026"; number "{ms:khoury_lymphoid}"; label "of lymphoid cells put in the lymphoid lineage"; number "{ms:khoury_myeloid}"; label "of myeloid cells put in the myeloid lineage"; caption "Development: these data were used while VivOME was built. Post-hoc: their labels had been read before."
- **Caveats shown:** development, post-hoc.
- **Voice-over:** "On real blood protein data, here is how often it answers, and how often those answers are right."
- **Cards:** White cards: the site's sheet, with its soft blue halo.
- **Camera:** Settles at the deepest point of the dive with a slow push in; the cards hang among the nearest cells.
- **Transition:** The camera glides sideways to scene 10; these cards keep their places in the water and slide out of the frame.
- **Water:** The same white gel; at the deepest point the cells are closest and largest, and the far ones most softly blurred.
- **Particles:** Dense and close: cells and strands drift large around the cards.
- **Sound:** The music settles on a low, slow bass pulse under the numbers.

### 10. Against established methods (1:32 to 1:44, 12 s)

Chapter: the results. Made with HyperFrames, GSAP, three.js water (still).

- **On screen:** headline "Measured against established methods."; line "On real protein data, VivOME is level with the best of them and ahead of the rest."; number "{ms:bm_khoury_baseline_favour} of {ms:bm_khoury_baseline_runs}"; label "baseline runs favour VivOME on Khoury 2026"; number "{ms:bm_fulcher_favour} of {ms:bm_fulcher_pairings}"; label "paired comparisons favour VivOME on Fulcher 2026"; caption "Still weak: CD8 T cells and dendritic cells, for every method tested."; caption "A sealed test on sorted cells: {ms:open_sorted_test}".
- **Caveats shown:** post-hoc, in-sample, pending.
- **Voice-over:** "Against established methods, on real protein data, it is level with the best and ahead of the rest. Where it is still weak, it says so."
- **Cards:** Liquid glass: the site's frosted glass over the gel.
- **Camera:** A slow pan along the floor past the methods, each a bubble with its name.
- **Transition:** The camera pulls back and away towards the light: these result cards slide aside as the Atlas window comes in.
- **Water:** The same white gel; the cells begin to recede as the camera turns to rise.
- **Particles:** The methods rise past the camera as bubbles, each with its name: scANVI, MaxFuse, scGLUE, Harmony, Seurat, PCA and correlation.
- **Sound:** The pulse continues under a lighter counter-melody: the rise begins.

### 11. In your browser (1:44 to 1:54, 10 s)

Chapter: use it. Made with HyperFrames, GSAP, three.js atlas, three.js water (wake).

- **On screen:** headline "Label your own data."; line "Send a DIA-NN, FragPipe or CSV file from the Atlas page. Your cells land on the reference, each with its answer or the reason for none."; chip "The PBMC240 example file"; caption "Answered by {fact:model_name}, atlas {fact:atlas_version}".
- **Voice-over:** "It runs online. Send your file from the Atlas page, and your cells land on the map, each with its answer."
- **Cards:** White cards: the site's sheet, with its soft blue halo.
- **Camera:** Pulled back from the results, a gentle push in on a browser window floating near the surface.
- **Transition:** The camera rises out of the map towards the surface; the window drops away below as the end card comes into view.
- **Water:** A wake: the file leaves a trail of ripples as it drops into the atlas.
- **Particles:** The file's cells fly out of it in 3D, with trails, and land in their places.
- **Sound:** Bright plucks as each cell lands; the theme returns in full.
- **Drawn from data:** The map is the reference sample in 3D, and the cells are the PBMC240 example file's, landing with the answers the served model gave them, in the Atlas page's looks (web/data/workflow.json).

### 12. Into the light (1:54 to 2:00, 6 s)

Chapter: use it. Made with HyperFrames, GSAP, three.js water (rain).

- **On screen:** wordmark "VivOME"; headline "No cell placed without evidence."; chip "Explore the atlas"; chip "Label your data"; caption "vivome-atlas.pages.dev".
- **Voice-over:** "Bring your protein cells up into the light. VivOME: no cell placed without evidence."
- **Cards:** Liquid glass: the site's frosted glass over the gel.
- **Camera:** Rises and breaks the surface, then settles on the end card.
- **Transition:** The end card waits above the water and comes into view as the camera surfaces, and holds.
- **Water:** The waterline sweeps down the frame as we surface and settles low; rain rings the water under the end card.
- **Particles:** Bubbles rise and burst at the surface, then the frame clears.
- **Sound:** The music swells as the camera surfaces and resolves on a bright final chord, then fades to silence on the end card.
