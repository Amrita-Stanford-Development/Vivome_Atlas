"""Scene 7 of the film, "Honest answers": the explainer shot, drawn by Manim.

The reference map (a sample of the atlas's own RNA cells, coloured by type)
fades in as the points from scene 6's encoders land on it; then, one at a
time, four cells of the PBMC240 example file land in their places, and an
outline narrows over the map to the cell's set of plausible types: from the
wider sets its types belong to (its group, its lineage, or every type) down
to one type for a cell-type answer, the types of one group for a group
answer, of one lineage for a lineage answer. With no answer it widens
instead, from the best guess to every type that fits, drawn dashed. The
types inside light up as it moves. The cells, their sets and their answers
are the served model's, from web/data/workflow.json (scripts/prepare.mjs
writes build/answers.json, with the stages and their timing). The words are
the composition's (compositions/s07-answers.html), so this draws none:
Manim draws what has to move exactly, the dots and the outlines.

Rendered on a transparent background to a PNG sequence that the HyperFrames
composition shows frame by frame (scripts/manim.mjs runs it):

    python -m manim render -t --format png manim/answers.py Answers
"""

import json
from pathlib import Path

from manim import (
    WHITE, AnimationGroup, Create, DashedVMobject, Dot, FadeIn, FadeOut, Polygon, Scene, Transform, VGroup, config,
    smooth,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "build" / "answers.json").read_text(encoding="utf-8"))
SHOT = DATA["shot"]

config.pixel_width = 1920
config.pixel_height = 1080
config.frame_rate = SHOT["fps"]

PROT = "#2F8F6A"  # reserved: protein, and nothing else
ACCENT = "#0073AD"
NO_ANSWER = "#5B6B78"  # a grey on the site's white gel: no answer has no colour


def to_scene(px, py):
    """Frame pixels (1920 by 1080, from the top left) to Manim's units."""
    return [(px - 960) * config.frame_width / 1920, (540 - py) * config.frame_height / 1080, 0]


def placer(box, bounds):
    """The atlas's projection placed in a box, keeping its shape (as lib/scenes.js does)."""
    x0, x1, y0, y1 = bounds
    s = min((box[2] - box[0]) / (x1 - x0), (box[3] - box[1]) / (y1 - y0))
    ox = (box[0] + box[2]) / 2 - ((x0 + x1) / 2) * s
    oy = (box[1] + box[3]) / 2 + ((y0 + y1) / 2) * s
    return lambda x, y: (ox + x * s, oy - y * s)


def hull(points):
    """The convex hull of 2D points, counter-clockwise (Andrew's monotone chain)."""
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def core(points, keep=0.8):
    """A type's points nearest its centre: its body, without the stragglers."""
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    ranked = sorted(points, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
    return ranked[: max(3, int(len(ranked) * keep))]


def outline_of(points, around, dashed):
    """A rounded outline round the points (or round `around` if too few)."""
    corners = hull(points)
    if len(corners) < 3:
        cx, cy = (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)) if points else around
        r = 0.28
        corners = [(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r)]
    shape = Polygon(*[[x, y, 0] for x, y in corners]).round_corners(radius=0.18)
    if dashed:
        shape.set_stroke(NO_ANSWER, width=4)
        return DashedVMobject(shape, num_dashes=60)
    return shape.set_stroke(ACCENT, width=4).set_fill(ACCENT, opacity=0.1)


class Answers(Scene):
    def construct(self):
        place = placer(SHOT["box"], SHOT["bounds"])
        classes = DATA["classes"]
        by_type = {}
        box = SHOT["box"]
        for x, y, k in DATA["map"]["sample"]:
            px, py = place(x, y)
            if not (box[0] <= px <= box[2] and box[1] <= py <= box[3]):
                continue  # a close-up: the map outside the shot's box is not drawn
            dot = Dot(to_scene(px, py), radius=0.03, color=classes[k]["colour"], fill_opacity=0.8)
            by_type.setdefault(k, VGroup()).add(dot)
        everything = VGroup(*by_type.values())
        # The shot's clock, in whole frames. Manim rounds an animation's
        # length up to whole frames and a still wait's down, so each is asked
        # for a hair under or over its whole number of frames.
        fps = SHOT["fps"]
        clock = 0

        def until(t):
            nonlocal clock
            target = round(t * fps)
            if target > clock:
                self.wait((target - clock) / fps + 1e-6)
                clock = target

        def play(*animations, run_time):
            nonlocal clock
            frames = round(run_time * fps)
            self.play(*animations, run_time=frames / fps - 1e-6)
            clock += frames

        # The map arrives with the points scene 6's encoders send to it.
        until(0.6)
        play(FadeIn(everything, lag_ratio=0.0015), run_time=1.0)

        def light(types):
            """The types of a stage lit, the rest dimmed."""
            lit = [g for t, g in by_type.items() if t in types]
            rest = [g for t, g in by_type.items() if t not in types]
            return AnimationGroup(*[g.animate.set_opacity(1) for g in lit], *[g.animate.set_opacity(0.3) for g in rest])

        def cores(types):
            points = []
            for t in types:
                if t in by_type:
                    points += core([(d.get_center()[0], d.get_center()[1]) for d in by_type[t]])
            return points

        landed = []
        for k, answer in enumerate(DATA["answers"]):
            start = SHOT["starts"][k]
            last = k == len(DATA["answers"]) - 1
            until(start)
            target = to_scene(*place(*answer["xy"]))
            cell = Dot(to_scene(1180, 300 + 120 * k), radius=0.1, color=PROT, fill_opacity=1)
            cell.set_stroke(WHITE, width=4)
            play(FadeIn(cell, scale=0.4), run_time=0.2)
            play(cell.animate(rate_func=smooth).move_to(target), run_time=SHOT["land"] - 0.2)

            # The outline: drawn round the first stage's types, then moving
            # through each stage to the cell's own set.
            dashed = answer["level"] == "none"
            stages = SHOT["stages"][k]
            here = (target[0], target[1])
            outline = outline_of(cores(stages[0]), here, dashed)
            play(light(stages[0]), Create(outline), run_time=SHOT["first"])
            for types in stages[1:]:
                play(light(types), Transform(outline, outline_of(cores(types), here, dashed)), run_time=SHOT["step"])
            landed.append(cell)
            if last:
                until(SHOT["seconds"])
                break
            until(SHOT["starts"][k + 1] - 0.4)
            play(
                FadeOut(outline),
                AnimationGroup(*[g.animate.set_opacity(0.8) for g in by_type.values()]),
                cell.animate.scale(0.7),
                run_time=0.4,
            )
