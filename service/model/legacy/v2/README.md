# Legacy v2 — audit trail and prior baseline only

The old `CrossModalNet` run: jointly trained on RNA and proteomics together,
over the old 2,903-gene shared space. Superseded by the 9,002-gene feature
space and the frozen-reference architecture (`decisive_summary.json`), but
kept here rather than deleted — see
[`../../../../docs/web/manifest.md`](../../../../docs/web/manifest.md) and
`versions.html`'s "prior baseline" card, which reads `provenance.json`
directly.

| File | Use |
|---|---|
| `provenance.json` | The old run's real numbers — `zero_shot_auc_raw`, `zero_shot_auc_smoothed`, the four properties it shipped. `scripts/build_manifest.py` reads this to populate `atlas_manifest.json`'s `previous_release` block, so the model card shows it as the documented "before", not a silently vanished number. |
| `shared_genes.csv` | The old 2,903-gene list. **Audit trail only — do not use as input anywhere.** `feature_space_genes.csv` (9,002 genes) is authoritative now. |

CrossModalNet had implicitly seen SCoPE2 during its joint training, which is
part of why its zero-shot numbers read higher than the honestly separated
v3 architecture's will once it exists. Both numbers are real; they answer
different questions.
