"""valuescale: is a quantification table still on a linear scale (it needs a
log), or already log-transformed?

The plan is research/value-scale-plan.md. Built so far: the diagnostic bank
(corpus/), real public tables whose scale is known from provenance, which
every later step is checked against. The detector itself (detect, apply)
comes in step B4. Nothing here imports the projection service, so the
package can leave this repository unchanged.
"""

__version__ = "0.0.1"
