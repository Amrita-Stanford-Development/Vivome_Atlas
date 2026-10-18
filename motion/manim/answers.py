"""Scene 7 of the film, "Honest answers": the explainer shot, drawn by Manim.

The reference map (a sample of the atlas's own RNA cells, coloured by type)
grows out of the spot where scene 6 left its points; four cells of the
PBMC240 example file land in their places. Then, as the voice names each
rung (a cell type, its group, its lineage, or no answer), that cell's
outline is drawn faint round the widest set its types belong to, narrows to
its set of plausible types, and settles exactly as the rung is said: one
type for a cell-type answer, the types of one group for a group answer, of
one lineage for a lineage answer. With no answer it widens
instead, from the best guess to every type that fits, drawn dashed. The
types inside light up as it moves. The cells, their sets, their answers and
the times are the served model's and the storyboard's, from
web/data/workflow.json and web/js/reel-frames.js (scripts/prepare.mjs
writes build/answers.json). The words are the composition's
(compositions/s07-answers.html), so this draws none: Manim draws what has to
move exactly, the dots and the outlines.

Everything after the map has grown plays as one timeline, each thing on its
own track (a Succession of waits and moves), so the four cells' outlines can
narrow at their own moments. Rendered on a transparent background, one
frame per film frame (scripts/manim.mjs runs it):

    python -m manim render -t --format mov manim/answers.py Answers
"""

import json
from pathlib import Path

from manim import (
    WHITE, AnimationGroup, DashedVMobject, Dot, FadeIn, Polygon, Scene, Succession, Transform, VGroup, Wait,
    config, smooth,
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


def outline_of(points, around, dashed, strength=1.0):
    """A rounded outline round the points (or round `around` if too few);
    `strength` below 1 draws it fainter, for a set still to narrow."""
    corners = hull(points)
    if len(corners) < 3:
        cx, cy = (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)) if points else around
        r = 0.28
        corners = [(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r)]
    shape = Polygon(*[[x, y, 0] for x, y in corners]).round_corners(radius=0.18)
    width = 2.5 + 1.5 * strength
    if dashed:
        shape.set_stroke(NO_ANSWER, width=width, opacity=0.35 + 0.65 * strength)
        return DashedVMobject(shape, num_dashes=60)
    return shape.set_stroke(ACCENT, width=width, opacity=0.35 + 0.65 * strength).set_fill(ACCENT, opacity=0.03 + 0.07 * strength)


class Answers(Scene):
    def construct(self):
        place = placer(SHOT["box"], SHOT["bounds"])
        classes = DATA["classes"]
        by_type = {}
        box = SHOT["box"]
        targets = []
        for x, y, k in DATA["map"]["sample"]:
            px, py = place(x, y)
            if not (box[0] <= px <= box[2] and box[1] <= py <= box[3]):
                continue  # a close-up: the map outside the shot's box is not drawn
            dot = Dot(to_scene(px, py), radius=0.03, color=classes[k]["colour"], fill_opacity=0.8)
            by_type.setdefault(k, VGroup()).add(dot)
            targets.append((dot, to_scene(px, py)))
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

        # The map grows out of where scene 6 left its points.
        p6x, p6y = SHOT["from"]
        for i, (dot, _) in enumerate(targets):
            dot.move_to(to_scene(p6x + 30 * ((i * 0.618) % 1 - 0.5), p6y + 30 * ((i * 0.382) % 1 - 0.5)))
        self.add(*[d for d, _ in targets])
        until(SHOT["map"][0])
        play(AnimationGroup(*[d.animate(rate_func=smooth).move_to(t) for d, t in targets], lag_ratio=0.0006),
             run_time=SHOT["map"][1] - SHOT["map"][0])

        def light(types):
            """The types of a stage lit, the rest dimmed."""
            return AnimationGroup(*[g.animate.set_opacity(1 if t in types else 0.3) for t, g in by_type.items()])

        def cores(types):
            points = []
            for t in types:
                if t in by_type:
                    points += core([(d.get_center()[0], d.get_center()[1]) for d in by_type[t]])
            return points

        def wait(d):
            return [Wait(run_time=d)] if d > 1e-3 else []

        # Everything else on one timeline from here, each thing on its own track.
        t0 = clock / fps
        tracks = []
        lights = []
        lit_clock = t0
        for k, answer in enumerate(DATA["answers"]):
            target = to_scene(*place(*answer["xy"]))
            here = (target[0], target[1])
            dashed = answer["level"] == "none"
            stages = SHOT["stages"][k]
            land = SHOT["land"][k]
            settle = SHOT["settle"][k]
            narrow = settle - SHOT["step"] * (len(stages) - 1)
            # The cell: it appears beside the map and flies to its place.
            cell = Dot(to_scene(1180, 300 + 120 * k), radius=0.1, color=PROT, fill_opacity=1)
            cell.set_stroke(WHITE, width=4)
            tracks.append(Succession(*wait(land - t0),
                                     FadeIn(cell, scale=0.4, run_time=SHOT["fade"]),
                                     cell.animate(rate_func=smooth, run_time=SHOT["flight"]).move_to(target)))
            # Its outline: drawn faint round its widest set as its turn comes,
            # then narrowing stage by stage to settle as its rung is said.
            landed = land + SHOT["fade"] + SHOT["flight"]
            drawn = max(landed, narrow - SHOT["outline"] - 0.3)
            widest = outline_of(cores(stages[0]), here, dashed, strength=0.0 if len(stages) > 1 else 1.0)
            # It grows out of the cell: until then it is a speck, unseen (a
            # timeline's things are all on screen from its start).
            outline = widest.copy().scale(0.02).move_to(target).set_opacity(0)
            steps = [Transform(outline, widest, run_time=SHOT["outline"])]
            steps += wait(narrow - drawn - SHOT["outline"])
            for j, types in enumerate(stages[1:], start=1):
                final = j == len(stages) - 1
                steps.append(Transform(outline, outline_of(cores(types), here, dashed, strength=1.0 if final else 0.5),
                                       run_time=SHOT["step"]))
            tracks.append(Succession(*wait(drawn - t0), *steps))
            # The map lights each stage's types while the outline moves.
            lights += wait(narrow - lit_clock)
            for types in stages[1:]:
                lights.append(AnimationGroup(light(types), run_time=SHOT["step"]))
            lit_clock = settle
        tracks.append(Succession(*lights))
        length = max(track.get_run_time() for track in tracks)
        play(AnimationGroup(*tracks), run_time=length)
        until(SHOT["seconds"])
