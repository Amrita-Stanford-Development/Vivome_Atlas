# Fair baseline comparison — documentation suite

This folder documents the **fair baseline comparison tool**: a from-scratch
rebuild of VivOME Atlas's cross-modal integration benchmark (comparing the
shipped frozen RNA reference encoder against MaxFuse, Harmony, scANVI, and
scGLUE), built after the repository owner rejected an earlier, methodologically
unfair version of the same comparison.

**This is documentation about investigative/benchmarking work, not about the
shipped static app.** It lives here (`Documentation/`), separate from
`docs/` (which documents the live app — manifest, data files, the projection
service). Nothing described here is wired into the site:
`Atlas/atlas_manifest.json`'s `benchmark.rows` stays `[]`/pending regardless
of what these documents say, until the repository owner explicitly signs off.

## Read these in order

1. **[methodology.md](methodology.md)** — the repository owner's explicit
   rules for what makes this comparison fair, and exactly how the shared
   evaluation protocol (classifier choice, restricted/unrestricted regimes,
   bootstrap confidence intervals, the majority-class floor) implements them.
2. **[architecture.md](architecture.md)** — what each file in
   `tools/fair_benchmark/` does, what it reads, what it writes, and how to
   run the whole pipeline end to end.
3. **[bugs-and-fixes.md](bugs-and-fixes.md)** — every real bug hit while
   building this, including one that was fixed in the *actual production
   service* (`service/pipeline/smoothing.py`), not just in this benchmark
   tooling.
4. **[known-limitations.md](known-limitations.md)** — the open,
   unresolved issues, most importantly a data-provenance gap in the "ours"
   reconstruction that cannot be fixed from this machine.
5. **[results.md](results.md)** — the actual numbers, kept up to date as
   runs complete.

## The one-paragraph version

An earlier comparison scored the shipped model with full RNA-label access
against baselines that got no labels, a 15,000-cell subsample instead of the
full 85,232-cell RNA reference, and a scoring rule that wasn't necessarily
each baseline's own native protocol. The repository owner called this out
as measuring label access and effort, not method quality, and gave nine
explicit rules for a redo (see [methodology.md](methodology.md)). This suite
documents the rebuild: every method now gets the full RNA reference and RNA
labels, protein labels are touched only once, at final scoring, everyone is
scored by one shared rule (with native protocols reported alongside), every
regime and every divergence is disclosed in the table, and nothing is wired
into the live site until the methodology is clean.

## Where the actual code and data live

The runnable scripts are committed at `tools/fair_benchmark/` (paths fixed
to be repo-relative, so they run from a fresh clone — see
[architecture.md](architecture.md) for how). Their **outputs**
(`tools/fair_benchmark/results/*.npy`, `*.csv`, `*.json`, `*.log`) are
`.gitignore`d — regenerable, large (the RNA expression matrix alone is
~1&nbsp;GB), and not source. Re-run `load.py` first to regenerate them
locally.
