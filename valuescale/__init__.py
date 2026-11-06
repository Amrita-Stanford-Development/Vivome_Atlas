"""valuescale: is a quantification table still on a linear scale (it needs a
log), or already log-transformed?

The plan is research/value-scale-plan.md. Built so far:
- the diagnostic bank (corpus/, Step 1): real public tables whose scale is
  known from provenance, which every later step is checked against;
- the method (B2): gates.py, statistics.py, score.py, conformal.py and
  method.assess, from a table to a verdict with its reason;
- the calibration and test corpus (corpus/, B3): the frame, the walk and
  its log, and the hand audit. It is not shipped.
The thresholds come from B4's calibration, and with them the package's
detect and apply. Nothing here imports the projection service, so the
package can leave this repository unchanged.
"""

__version__ = "0.0.1"
