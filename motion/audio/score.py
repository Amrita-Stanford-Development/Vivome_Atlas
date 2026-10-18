"""The film's music, made here in code: no recorded or downloaded sound, so
nothing needs a licence. There are no sound effects; the film's sound is
this music and the voice-over.

Writes build/audio/music.wav, 48 kHz stereo, the length of the film: one
continuous ambient bed in D major that never stops or restarts at a scene
change (its chords cross-fade over a few seconds, its level is one smooth
curve that rises towards the end), and the storyboard's musical cues
(web/js/reel-frames.js, `sound`) played on it: the piano note on the title,
the theme, the arpeggio, one tone per encoder, the notes stepping down the
ladder, two lines braiding into one, a soft bass pulse, the plucks as cells
land, the final chord. The mix (scripts/film.mjs, with FFmpeg) ducks it
under the voice.

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


def tone(freq, dur, decay=1.2, attack=0.01, partials=((1, 1.0), (2, 0.35), (3, 0.12))):
    """A struck, bell-soft tone: partials with an exponential decay, and a
    short fade at its end so it never stops with a click."""
    t = np.arange(int(dur * SR)) / SR
    sig = sum(a * np.sin(2 * np.pi * freq * k * t) * np.exp(-t * (1 + k * 0.6) / decay) for k, a in partials)
    return sig * np.minimum(1, t / attack) * np.minimum(1, (dur - t) / 0.05)


def pluck(freq, dur=1.2):
    return tone(freq, dur, decay=0.45, attack=0.004, partials=((1, 1.0), (2, 0.5), (3, 0.22), (4, 0.1)))


music = np.zeros((N, 2))
t = np.arange(N) / SR

# ---- the bed: one chord per chapter, cross-fading, never stopping ----

CHORDS = [
    (0, ["D2", "A2", "F#3", "E4"]),
    (at("gaps", 0), ["B1", "F#2", "D3"]),
    (at("gaps", 6), ["A2", "A3"]),
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


FADE = 3.0  # seconds over which one chord gives way to the next
for k, (start, notes) in enumerate(CHORDS):
    end = CHORDS[k + 1][0] if k + 1 < len(CHORDS) else TOTAL
    a, b = int(max(0, start - FADE / 2) * SR), int(min(TOTAL, end + FADE / 2) * SR)
    length = b - a
    tt = np.arange(length) / SR
    # Equal-power cross-fades, so the bed keeps its level through a change.
    rise_in = np.sin(np.pi / 2 * np.clip(tt / FADE, 0, 1)) if start > 0 else np.ones(length)
    fall_out = np.cos(np.pi / 2 * np.clip((tt - (length / SR - FADE)) / FADE, 0, 1)) if end < TOTAL else np.ones(length)
    voices = sum(pad_voice(note(n), length, 100 * k + i) for i, n in enumerate(notes)) / np.sqrt(len(notes))
    music[a:b] += voices * (rise_in * fall_out)[:, None]


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


# Its level: in from silence over the first seconds, a slow rise towards
# the end, a swell as the camera surfaces that settles into the final
# chord, and out to silence on the end card. One smooth curve.
level = 0.16 + 0.14 * (t / TOTAL) ** 2
level *= 1 + 0.35 * smoothstep((t - at("light", 0)) / 2.9) * (1 - smoothstep((t - at("light", 3.0)) / 1.8))
level *= smoothstep(t / 3.0)
level *= smoothstep((TOTAL - 0.3 - t) / 2.6)
music *= level[:, None]

# ---- the cues, played on the bed ----

THEME = ["D5", "F#5", "E5", "A4"]

# Scene 1: one soft piano note as the title lands.
place(music, tone(note("D5"), 4, decay=1.6) + 0.6 * tone(note("A4"), 4, decay=1.6), at("surface", 2.9), gain=0.2)
# Scene 4: a warm chord and the first hint of the theme.
for i, n in enumerate(["G3", "B3", "D4", "F#4"]):
    place(music, tone(note(n), 5, decay=2.4, attack=0.2), at("rna", 1.5), pan=-0.3 + 0.2 * i, gain=0.08)
for i, n in enumerate(THEME):
    place(music, tone(note(n), 3, decay=1.4), at("rna", 3.0 + 0.7 * i), gain=0.07)
# Scene 5: a rising arpeggio as the wordmark appears, then the theme in full.
for i, n in enumerate(["D4", "F#4", "A4", "D5", "F#5", "A5"]):
    place(music, pluck(note(n)), at("vivome", 0.5 + 0.3 * i), pan=-0.5 + 0.2 * i, gain=0.1)
for i, n in enumerate(THEME):
    place(music, tone(note(n), 3, decay=1.6), at("vivome", 4.4 + 0.55 * i), gain=0.14)
    place(music, tone(note(n) / 2, 3, decay=1.6), at("vivome", 4.4 + 0.55 * i), gain=0.05)
# Scene 6: one soft tone per encoder, resolving into one chord.
for i, n in enumerate(["A4", "C#5", "E5", "F#5", "A5"]):
    place(music, tone(note(n), 2, decay=0.9), at("built-for-gaps", 8.0 + 0.16 * i), pan=-0.6 + 0.3 * i, gain=0.08)
for n in ["A3", "E4", "A4", "C#5"]:
    place(music, tone(note(n), 3, decay=1.5, attack=0.05), at("built-for-gaps", 8.9), gain=0.06)
# Scene 7: a note down for each rung of the ladder; a soft stop on no answer.
for k, n in enumerate(["D5", "B4", "A4", "F#4"]):
    last = k == 3
    place(music, tone(note(n), 2.5, decay=0.5 if last else 1.4), at("answers", TIMELINE["answers"][k] + 0.9), gain=0.09 if last else 0.13)
# Scene 8: two lines of melody braid into one.
for i, n in enumerate(["D5", "E5", "F#5", "A5"]):
    place(music, tone(note(n), 1.6, decay=0.8), at("second-opinion", 2.0 + 0.6 * i), pan=-0.5, gain=0.09)
for i, n in enumerate(["A4", "B4", "D5", "E5"]):
    place(music, tone(note(n), 1.6, decay=0.8), at("second-opinion", 2.3 + 0.6 * i), pan=0.5, gain=0.09)
for n in ["D5", "F#5"]:
    place(music, tone(note(n), 2.4, decay=1.2), at("second-opinion", 5.0), gain=0.12)
# Scenes 9 and 10: a soft bass pulse on the chord's root, a note every
# 1.5 seconds, swelling in and out; then a lighter counter-melody.
beat = 1.5
first, last = at("real-data", 0.5), at("atlas", 0)
for k in range(int((last - first) / beat)):
    when = first + k * beat
    swell = min(1.0, (k + 1) / 4) * min(1.0, (last - when) / 4.5)
    root = "B1" if when < at("methods", 0) else "E2"
    place(music, tone(note(root), 1.6, decay=0.5, attack=0.03, partials=((1, 1.0), (2, 0.25))), when, gain=0.16 * swell)
counter = ["F#5", "E5", "D5", "A4", "B4", "D5", "E5", "F#5", "A5", "F#5", "E5", "D5", "E5", "F#5", "A5", "B5"]
for i, n in enumerate(counter):
    place(music, pluck(note(n)), at("methods", 2.0 + 0.5 * i), pan=0.4 * np.sin(i), gain=0.06)
# Scene 11: bright plucks as the cells land, and the theme in full.
for i in range(22):
    n = ["D5", "E5", "F#5", "A5", "B5", "D6"][int(rng.integers(6))]
    place(music, pluck(note(n)), at("atlas", 2.0 + 4.0 * i / 22 + rng.uniform(0, 0.08)), pan=rng.uniform(-0.7, 0.7), gain=0.05)
for i, n in enumerate(THEME):
    place(music, tone(note(n), 3, decay=1.5), at("atlas", 3.0 + 0.55 * i), gain=0.12)
    place(music, tone(note(n) / 2, 3, decay=1.5), at("atlas", 3.0 + 0.55 * i), gain=0.045)
# Scene 12: the bright final chord as the camera surfaces; it rings out
# under the end card and fades with the bed.
for i, n in enumerate(["D3", "A3", "D4", "F#4", "A4", "D5", "F#5"]):
    place(music, tone(note(n), 2.75, decay=1.4, attack=0.02), at("light", 3.2 + 0.03 * i), pan=-0.5 + i / 6, gain=0.1)
music *= smoothstep((TOTAL - 0.05 - t) / 1.2)[:, None]

# ---- write, peaking a little under full scale ----

OUT.mkdir(parents=True, exist_ok=True)
music *= 0.5 / max(1e-9, np.abs(music).max())
sf.write(OUT / "music.wav", music.astype(np.float32), SR, subtype="PCM_16")
for stale in ("fx.wav",):
    (OUT / stale).unlink(missing_ok=True)
print(f"score: build/audio/music.wav, {TOTAL} s at {SR} Hz, music only")
