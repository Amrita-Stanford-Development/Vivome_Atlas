"""The film's music and sound effects, made here in code: no recorded or
downloaded sound, so nothing needs a licence.

Writes two 48 kHz stereo tracks the length of the film, so the mix
(scripts/film.mjs, with FFmpeg) can duck the music alone under the voice:

- build/audio/music.wav: a soft ambient bed in D major under the whole dive,
  one chord per chapter, rising towards the end; and the storyboard's
  musical cues (web/js/reel-frames.js, `sound`): the piano note on the
  title, the theme, the arpeggio, one tone per encoder, the notes stepping
  down the ladder, two lines braiding into one, the deep pulse, the plucks
  as cells land, the final chord;
- build/audio/fx.wav: rain on the surface, bubbles, the empty tags' hollow
  ticks, the dry ticks of missing values, the wordmark's whoosh, a sonar
  ping as each number lands, the splash on surfacing.

Each cue's time is a scene's start (build/timeline.json, from
scripts/prepare.mjs) plus an offset that matches its composition's
timeline. Every random choice is seeded, so the score is the same on every
run. Needs numpy and soundfile (the vivome-voice env has both).

    python audio/score.py
"""

import json
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
TIMELINE = json.loads((ROOT / "build" / "timeline.json").read_text(encoding="utf-8"))
OUT = ROOT / "build" / "audio"
SR = 48000
TOTAL = TIMELINE["total"]
N = int(TOTAL * SR)
START = {f["id"]: f["start"] for f in TIMELINE["frames"]}
rng = np.random.default_rng(7)


def at(scene, offset):
    """Seconds into the film: a scene's start plus an offset."""
    return START[scene] + offset


def note(name):
    """A note's frequency, e.g. 'D4' or 'F#5' (A4 = 440 Hz)."""
    steps = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3, "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((steps[pitch] + 12 * (octave - 4)) / 12)


def place(bus, sig, when, pan=0.0, gain=1.0):
    """Mix a mono signal into a stereo bus at `when` seconds, panned -1..1."""
    i = int(when * SR)
    if i >= N:
        return
    sig = sig[: N - i] * gain
    left, right = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    bus[i:i + len(sig), 0] += sig * left
    bus[i:i + len(sig), 1] += sig * right


def band(sig, low=0.0, high=None):
    """Keep only the frequencies between low and high (Hz), through the FFT."""
    spec = np.fft.rfft(sig)
    f = np.fft.rfftfreq(len(sig), 1 / SR)
    mask = (f >= low) & (f <= (high if high else SR / 2))
    # soft edges, so the cut does not ring
    if low > 0:
        mask = mask | ((f > low * 0.7) & (f < low))
    return np.fft.irfft(spec * mask, n=len(sig))


def tone(freq, dur, decay=1.2, attack=0.01, partials=((1, 1.0), (2, 0.35), (3, 0.12)), detune=0.0):
    """A struck, bell-soft tone: partials with an exponential decay."""
    t = np.arange(int(dur * SR)) / SR
    sig = sum(a * np.sin(2 * np.pi * freq * k * (1 + detune) * t) * np.exp(-t * (1 + k * 0.6) / decay) for k, a in partials)
    env = np.minimum(1, t / attack)
    return sig * env


def pluck(freq, dur=1.2):
    return tone(freq, dur, decay=0.45, attack=0.004, partials=((1, 1.0), (2, 0.5), (3, 0.22), (4, 0.1)))


def chirp(f0, f1, dur):
    """A rising sine: one bubble."""
    t = np.arange(int(dur * SR)) / SR
    f = f0 * (f1 / f0) ** (t / dur)
    phase = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(phase) * np.sin(np.pi * t / dur) ** 2


def noise(dur):
    return rng.standard_normal(int(dur * SR))


# ---- the music: a pad that changes chord with each chapter ----

music = np.zeros((N, 2))
fx = np.zeros((N, 2))
t = np.arange(N) / SR

# Each chapter's chord; the gaps scene thins to one held note.
CHORDS = [
    (0, ["D2", "A2", "F#3", "E4"]),
    (at("gaps", 0), ["B1", "F#2", "D3"]),
    (at("gaps", 6), ["A3"]),
    (at("rna", 0), ["G2", "D3", "B3", "F#4", "A4"]),
    (at("built-for-gaps", 0), ["E2", "B2", "G3", "D4", "F#4"]),
    (at("real-data", 0), ["B1", "F#2", "A3", "C#4", "D4"]),
    (at("atlas", 0), ["A2", "D3", "F#3", "A3", "E4"]),
    (at("light", 3.2), ["D2", "A2", "D3", "F#3", "A3", "D4", "F#4", "A4"]),
]


def pad_voice(freq, length, seed):
    """One sustained voice: three slightly detuned sines and soft overtones,
    with a slow swell, a little different on each side."""
    tt = np.arange(length) / SR
    r = np.random.default_rng(seed)
    out = np.zeros((length, 2))
    for side in (0, 1):
        ph = r.uniform(0, 2 * np.pi, 3)
        d = 0.0022 * (1 if side else -1)
        s = (np.sin(2 * np.pi * freq * (1 + d) * tt + ph[0])
             + np.sin(2 * np.pi * freq * (1 - d) * tt + ph[1])
             + 0.6 * np.sin(2 * np.pi * freq * tt + ph[2])
             + 0.18 * np.sin(2 * np.pi * freq * 2 * tt)
             + 0.05 * np.sin(2 * np.pi * freq * 3 * tt))
        out[:, side] = s * (0.8 + 0.2 * np.sin(2 * np.pi * 0.07 * tt + ph[0]))
    return out / 2.8


FADE = 2.2  # seconds of crossfade between chords
for k, (start, notes) in enumerate(CHORDS):
    end = CHORDS[k + 1][0] if k + 1 < len(CHORDS) else TOTAL
    a, b = int(max(0, start - FADE / 2) * SR), int(min(TOTAL, end + FADE / 2) * SR)
    length = b - a
    tt = np.arange(length) / SR
    env = np.minimum(1, tt / FADE) * np.minimum(1, (length / SR - tt) / FADE)
    voices = sum(pad_voice(note(n), length, 100 * k + i) for i, n in enumerate(notes)) / np.sqrt(len(notes))
    music[a:b] += voices * env[:, None]

# The bed rises towards the end, swells as the camera surfaces, then falls
# to silence on the end card.
rise = 0.16 + 0.14 * (t / TOTAL) ** 2
rise *= 1 + 0.5 * np.clip((t - at("light", 0)) / 2.9, 0, 1) * (t < at("light", 3.2))
rise *= np.clip((TOTAL - 0.2 - t) / 2.6, 0, 1)
rise *= np.clip(t / 2.5, 0, 1)
music *= rise[:, None]

THEME = ["D5", "F#5", "E5", "A4"]

# Scene 1: one soft piano note as the title lands.
place(music, tone(note("D5"), 4, decay=1.6) + 0.6 * tone(note("A4"), 4, decay=1.6), at("surface", 2.9), gain=0.22)
# Scene 4: a warm chord and the first hint of the theme.
for i, n in enumerate(["G3", "B3", "D4", "F#4"]):
    place(music, tone(note(n), 5, decay=2.4, attack=0.2), at("rna", 1.5), pan=-0.3 + 0.2 * i, gain=0.09)
for i, n in enumerate(THEME):
    place(music, tone(note(n), 3, decay=1.4), at("rna", 3.0 + 0.7 * i), gain=0.08)
# Scene 5: a rising arpeggio, then the theme in full on the headline.
for i, n in enumerate(["D4", "F#4", "A4", "D5", "F#5", "A5"]):
    place(music, pluck(note(n)), at("vivome", 0.5 + 0.3 * i), pan=-0.5 + 0.2 * i, gain=0.12)
for i, n in enumerate(THEME):
    place(music, tone(note(n), 3, decay=1.6), at("vivome", 4.4 + 0.55 * i), gain=0.16)
    place(music, tone(note(n) / 2, 3, decay=1.6), at("vivome", 4.4 + 0.55 * i), gain=0.06)
# Scene 6: one soft tone per encoder, resolving into one chord.
for i, n in enumerate(["A4", "C#5", "E5", "F#5", "A5"]):
    place(music, tone(note(n), 2, decay=0.9), at("built-for-gaps", 8.0 + 0.16 * i), pan=-0.6 + 0.3 * i, gain=0.09)
for n in ["A3", "E4", "A4", "C#5"]:
    place(music, tone(note(n), 3, decay=1.5, attack=0.05), at("built-for-gaps", 8.9), gain=0.07)
# Scene 7: a note down for each rung of the ladder; a soft stop on no answer.
for k, n in enumerate(["D5", "B4", "A4", "F#4"]):
    last = k == 3
    place(music, tone(note(n), 2.5, decay=0.5 if last else 1.4), at("answers", TIMELINE["answers"][k] + 0.9), gain=0.1 if last else 0.15)
# Scene 8: two lines of melody braid into one.
for i, n in enumerate(["D5", "E5", "F#5", "A5"]):
    place(music, tone(note(n), 1.6, decay=0.8), at("second-opinion", 2.0 + 0.6 * i), pan=-0.5, gain=0.1)
for i, n in enumerate(["A4", "B4", "D5", "E5"]):
    place(music, tone(note(n), 1.6, decay=0.8), at("second-opinion", 2.3 + 0.6 * i), pan=0.5, gain=0.1)
for n in ["D5", "F#5"]:
    place(music, tone(note(n), 2.4, decay=1.2), at("second-opinion", 5.0), gain=0.14)
# Scenes 9 and 10: a deep, soft pulse; then a lighter counter-melody as the rise begins.
beat = 0.75
pulse_t = np.arange(int(0.5 * SR)) / SR
thump = np.sin(2 * np.pi * (58 - 14 * pulse_t) * pulse_t) * np.exp(-pulse_t / 0.12)
for k in range(int((at("atlas", 0) - at("real-data", 0.5)) / beat)):
    when = at("real-data", 0.5) + k * beat
    swell = min(1, k / 6) * min(1, (at("atlas", 0) - when) / 3)
    place(music, thump, when, gain=0.22 * swell)
counter = ["F#5", "E5", "D5", "A4", "B4", "D5", "E5", "F#5", "A5", "F#5", "E5", "D5", "E5", "F#5", "A5", "B5"]
for i, n in enumerate(counter):
    place(music, pluck(note(n)), at("methods", 2.0 + 0.5 * i), pan=0.4 * np.sin(i), gain=0.07)
# Scene 11: bright plucks as the cells land, and the theme in full.
for i in range(22):
    n = ["D5", "E5", "F#5", "A5", "B5", "D6"][int(rng.integers(6))]
    place(music, pluck(note(n)), at("atlas", 2.0 + 4.0 * i / 22 + rng.uniform(0, 0.08)), pan=rng.uniform(-0.7, 0.7), gain=0.06)
for i, n in enumerate(THEME):
    place(music, tone(note(n), 3, decay=1.5), at("atlas", 3.0 + 0.55 * i), gain=0.14)
    place(music, tone(note(n) / 2, 3, decay=1.5), at("atlas", 3.0 + 0.55 * i), gain=0.05)
# Scene 12: the bright final chord as the end card lands.
for i, n in enumerate(["D3", "A3", "D4", "F#4", "A4", "D5", "F#5"]):
    place(music, tone(note(n), 3.4, decay=1.4, attack=0.01), at("light", 3.2 + 0.03 * i), pan=-0.5 + i / 6, gain=0.11)

# ---- the effects ----

# Scene 1: rain on the water, close; it muffles as the camera goes under.
rain_len = at("unnamed", 2.5)
hiss = band(noise(rain_len), 900, 9000) * 0.05
for _ in range(int(rain_len * 28)):
    when = rng.uniform(0, rain_len - 0.05)
    drop = tone(rng.uniform(1800, 5200), 0.05, decay=0.012, attack=0.0008, partials=((1, 1.0),))
    i = int(when * SR)
    hiss[i:i + len(drop)] += drop * rng.uniform(0.05, 0.18)
rt = np.arange(len(hiss)) / SR
under = np.clip((rt - at("unnamed", 0)) / 1.6, 0, 1)
muffled = band(hiss, 0, 500) * 2.2
rain = (hiss * (1 - under) + muffled * under) * np.clip(rt / 0.6, 0, 1) * np.clip((rain_len - rt) / 1.0, 0, 1)
place(fx, rain, 0, pan=-0.15, gain=1.0)
place(fx, np.roll(rain, 911), 0, pan=0.15, gain=0.9)
# Going under: a few bubbles, and a slow low swell.
for _ in range(14):
    place(fx, chirp(rng.uniform(260, 420), rng.uniform(900, 1500), rng.uniform(0.04, 0.09)), at("unnamed", rng.uniform(0.1, 1.8)), pan=rng.uniform(-0.6, 0.6), gain=0.05)
swell_len = 6.0
st = np.arange(int(swell_len * SR)) / SR
place(fx, band(noise(swell_len), 0, 180) * np.sin(np.pi * st / swell_len) ** 2 * 0.5, at("unnamed", 0.5))
# Scene 2: a hollow tick as each empty name tag appears.
for i in range(5):
    tick = tone(880, 0.25, decay=0.05, attack=0.002, partials=((1, 1.0), (2.76, 0.3)))
    place(fx, tick, at("unnamed", 1.0 + 0.5 * i), pan=0.3 + 0.1 * i, gain=0.09)
# Scene 3: dry ticks as the missing values fall away.
for _ in range(16):
    click = band(noise(0.02), 2000, 9000) * np.exp(-np.arange(int(0.02 * SR)) / SR / 0.004)
    place(fx, click, at("gaps", rng.uniform(4.8, 8.0)), pan=rng.uniform(-0.2, 0.8), gain=0.25)
# Scene 5: a soft whoosh as the wordmark locks.
wl = 1.1
wt = np.arange(int(wl * SR)) / SR
place(fx, band(noise(wl), 300, 4000) * np.sin(np.pi * wt / wl) ** 3 * 0.08, at("vivome", 1.0))
# Scene 9: a soft sonar ping as each number lands.
for off in (2.2, 3.0, 4.2, 5.0):
    ping = tone(1150, 1.6, decay=0.35, attack=0.004, partials=((1, 1.0),))
    for echo, g in ((0, 1.0), (0.32, 0.35), (0.64, 0.12)):
        place(fx, ping, at("real-data", off + echo), pan=0.2 if echo else 0, gain=0.07 * g)
# Scene 12: a rising rush, the splash as the camera breaks the surface, bubbles.
rush = 2.9
ru = np.arange(int(rush * SR)) / SR
place(fx, band(noise(rush), 200, 3000) * (ru / rush) ** 3 * 0.12, at("light", 0))
splash = band(noise(1.2), 150, 6000) * np.exp(-np.arange(int(1.2 * SR)) / SR / 0.22) * np.minimum(1, np.arange(int(1.2 * SR)) / (0.008 * SR))
place(fx, splash, at("light", 2.9), pan=-0.1, gain=0.3)
place(fx, np.roll(splash, 523), at("light", 2.9), pan=0.1, gain=0.25)
for _ in range(18):
    place(fx, chirp(rng.uniform(300, 500), rng.uniform(1000, 1800), rng.uniform(0.04, 0.08)), at("light", rng.uniform(2.95, 3.8)), pan=rng.uniform(-0.7, 0.7), gain=0.05)

# ---- write, each bus peaking a little under full scale ----

OUT.mkdir(parents=True, exist_ok=True)
for name, bus, peak in (("music", music, 0.5), ("fx", fx, 0.6)):
    bus *= peak / max(1e-9, np.abs(bus).max())
    sf.write(OUT / f"{name}.wav", bus.astype(np.float32), SR, subtype="PCM_16")
print(f"score: build/audio/music.wav and build/audio/fx.wav, {TOTAL} s at {SR} Hz")
