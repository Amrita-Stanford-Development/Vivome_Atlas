# Detecting a table's value scale: research and proposed method

Status: proposal, 2026-10-27, for the owner's decision. Nothing here is
implemented. It answers the fault found on PXD064083
(`research/benchmark/protocol-pxd064083.md`, amendment 1; `research/todo.md`,
"the linear-scale rule misreads small-scale linear tables").

## The question

Stage 0 (`service/pipeline/alignment.py`, `detect_and_transform_value_scale`)
decides whether a protein upload still needs a log. Today: no negative value
and a non-zero median above 50 (`config.LINEAR_SCALE_MEDIAN_THRESHOLD`) means
linear. PXD064083's linear values (median 7 and 8, up to 211,481, 44% and 47%
zeros) were read as log.

**Only "log needed or not" matters here.** Every gene is z-scored within the
upload before the model sees it (`alignment.zscore_per_gene`), which removes
any log base and any constant added to every value. The base need not be
identified.

## What the research found

Three searches on 2026-10-27, sources below. D: documented at the source.
Three were re-checked by hand: the Omics Playground code, the DIA-NN README
on zeros, and the timsTOF sentence in Van Puyvelde 2022.

### Rules in use elsewhere

- **No published error rate for any rule was found.** GEOexplorer, which
  reuses GEO2R's rule, states it did no accuracy testing [1].
- **Every automatic rule found is a threshold on magnitude, chosen as a round
  number:**
  - GEO2R: log2 is taken if q99 > 100, or if (max − min > 50 and q25 > 0),
    or if q25 lies in (0, 1) and q75 in (1, 2) [2]; "99 or 101 would work
    as well" [3];
  - CIBERSORT: max < 50 means logged [4];
  - ExpressAnalyst: negatives, or a max below 50 with non-integers [5];
  - scGPT: logged unless max > 30, min < 0, or the smallest non-zero value
    ≥ 1 [6];
  - Omics Playground `is_logged`: possibly log if max < 60 or min < −1, and
    linear if rows look like ratios, max > 1000, all integers, or a large
    sparse single-cell matrix [7].
- **Proteomics tools mostly assume or ask:**
  - DEP and LFQ-Analyst always take log2 after zeros become NA [8];
  - pmartR asks the user for the scale [9];
  - prolfqua keeps a flag [10];
  - Perseus, MSstats and TMT-Integrator write log2 [11, 12, 13].

### Why magnitude cannot decide

- **Units differ by instrument.**
  - "The exported ion counts of the timsTOF Pro differ at least 1–2 orders
    of magnitude compared to both the Orbitrap and the TripleTOF 6600+" [14].
  - Orbitrap signals are not ion counts; TMT values are often
    signal-to-noise [15].
- **Many linear outputs are rescaled to small numbers:**
  - SCoPE2 reporter ions are divided by a reference channel (about 0.01),
    then by column medians and row means [16];
  - plexDIA reports relative levels centred on 1 [17];
  - Proteome Discoverer's scaled abundances average 100 per protein [18];
  - NSAF values are fractions [19];
  - iBAQ ppb is a fraction of the total × 10⁹ [20];
  - Skyline areas can be below 1 [21].
- **Zeros are a clue, not a proof.**
  - MaxQuant, DIA-NN's report and directLFQ write 0 for "not detected"
    (DIA-NN: "below the limit of reliable quantification"; "If the data
    needs to be log-transformed, these zeroes can be replaced with NA") [22].
  - Zero imputation puts zeros into log2 data in FragPipe-Analyst [23], and
    a zero-imputed matrix has been deposited [24].

### What holds across instruments and does not depend on units

1. **Wide, log-normal spread within one sample.**
   - Protein abundances within a sample are close to log-normal [25, 26, 27].
   - They span about 4 orders of magnitude in single cells at protein level
     [28], and 7–8 orders in cells and tissue [29, 30].
   - Log2 intensities sit in a narrow band (MaxQuant example 18–22;
     MSstatsTMT about 16) [31, 32].
2. **Multiplicative error.** At moderate and high intensity the CV is
   constant, so on the linear scale a protein's spread grows with its level
   [33, 34, 35]. After a log it does not.
3. **Missing values depend on intensity.** Detection probability rises with
   log-intensity (logit-linear; missing-at-random and censoring are its two
   extremes) [36]. Single-cell tables are often 50–90% missing [37].

All three are unchanged when a table is multiplied by a constant: new units,
a normalisation to 1 or to 100, or ppb.

## Proposed method

### 1. First, measure what each mistake costs

On development tables, run v4.1 with each table read correctly and read
wrongly, both ways. Count the answers that change and, where labels exist,
the change in accuracy.

- **Expected, to be measured, not assumed:** reading a log table as linear
  costs little here. Within one gene, a log of log2 values (say 15 to 25) is
  almost a straight line, and the z-scoring removes straight-line changes.
- **Reading a linear table as log,** today's fault, costs more.

The result fixes which error the test must control, and what "can't tell"
does.

### 2. Gates, by definition

- **Any negative value:** already transformed (log, centred or z-scored), as
  today.
- **The user states the scale:** a new request option, `value_scale`: auto,
  linear or log.
- **Every value a non-negative integer:** counts, so linear. Log values are
  never all integers.

### 3. Three statistics from the three properties

Each one is unchanged when the table is multiplied by a constant. On a log
table, each is also unchanged by the log base.

- **D, the spread within a cell** (property 1): for each cell, log10(Q95/Q05)
  of its positive values. D is the median over cells.
- **b, the spread–level slope** (property 2):
  - take each protein seen in at least half the cells;
  - its level is the median and its spread Q75 − Q50, with missing values
    ranked lowest, so up to half missing at the bottom cannot move them
    (property 3);
  - b is the Theil–Sen slope of log spread on log level, over the upper half
    of proteins by level [38, 33, 35].
  - Linear: b ≈ 1. Log: b ≤ 0.
- **K, the shape difference** (property 1): for each cell, the Bowley
  skewness of its positive values minus that of their logs. K is the median
  over cells.
  - Linear: values right-skewed, logs about symmetric, so K is large.
  - Log: values about symmetric, logs left-skewed, so K is small or below 0.

### 4. The decision: two one-sided tests, not a threshold

- **Call it log** only if D, b and K all fall below their 1% quantiles among
  linear tables of that size.
  - This is an intersection–union test [39]: the chance that a linear table
    is called log is at most 1%, with no joint model needed.
- **Call it linear** if any of the three lies beyond its 1/3% quantile among
  log tables (Bonferroni).
  - The chance that a log table is called linear is at most 1%.
- **Otherwise, "can't tell".**
  - The service then reads the table as step 1's result says: the cheaper
    error.
  - Its reply says so, the site shows it with a warning, and the user can
    override.
  - A table where both tests reject is also "can't tell", and is flagged.

The service already returns `value_scale` with each reply; the site will show
it for every upload ("log scale, used as given" or "raw, log2 taken").

### 5. The corpus that sets the quantiles

Chosen by rule, not by hand.

- **Every protein table this project may open**, as a complete set:
  - the development deposits and the spent held-out sets
    (`research/benchmark/side-tests.md`, amendment 6);
  - not the organ locked tests (PXD052341, MSV000094189, PXD042367);
  - not the reserve (PXD061065).
- **A random sample of public deposits.**
  - Drawn from PRIDE and MassIVE projects of 2020–2026 that hold a
    processed quantification table of a known type, with a fixed seed.
  - Stratified by software (DIA-NN, Spectronaut, MaxQuant, FragPipe,
    Proteome Discoverer, other) and by instrument family (Orbitrap, timsTOF,
    other TOF, Astral).
  - Fetched by script and recorded with sha256s.
- **Labels by provenance, fixed before any statistic is computed:**
  - documented native outputs are linear, or log where documented (MSstats,
    TMT-Integrator, Perseus);
  - an author-made table is labelled from its paper's methods;
  - anything unclear is left out and counted.
- **Variants with known labels:**
  - log2, log10, ln and log2(x+1) of each linear table;
  - normalised per cell and per protein (relative levels; scaled to 100);
  - multiplied by 10^k;
  - divided by a reference;
  - subsampled to the service's shapes (20–2,000 cells, 200–9,000
    proteins);
  - missing values made intensity-dependent at 20–80% (the logit model of
    [36]).

  A variant stays in its source's half.

### 6. Validation

- **Split by source deposit.**
  - The development half sets the quantiles; PXD064083 is in it, as a
    regression case.
  - The test half is sealed, then scored once.
- **Report, for each true scale,** the share called wrong and the share
  "can't tell", with Clopper–Pearson 95% intervals. The unit is the source
  deposit, since variants of one deposit are not independent.
- **Size:** 0 errors in n deposits bounds the error at about 3/n [40].
  - A claim under 1% needs about 300 test deposits.
  - 100 deposits bound it at about 3%.

### Not chosen, and why

- **A threshold on magnitude** (median, maximum, quantiles): it depends on
  units, which differ by instrument and normalisation, and no such rule has
  a measured error rate.
- **Box–Cox λ alone** [41, 42]: well founded, but its likelihood is nearly
  flat on log tables and is pushed by truncation. It is kept as a reported
  diagnostic.
- **A classifier on many features:** it needs more labelled deposits than
  the corpus will hold, and is harder to check than three quantiles.

### Scope

- Protein uploads only. RNA keeps today's rule, where a 0 is a measured
  value.
- The model and its weights are unchanged. A release follows the usual
  order: protocol, development, the sealed test, the owner's OK, deploy.

## Sources

1. GEOexplorer, Nucleic Acids Res 2022. https://academic.oup.com/nar/article/50/W1/W367/6591531
2. GEO2R script, as quoted at https://test.biostars.org/p/227516/ ; https://www.ncbi.nlm.nih.gov/geo/info/geo2r.html
3. https://www.biostars.org/p/99879/
4. CIBERSORT (mirror; the official code needs registration). https://enterprise.gitee.com/lzh23/GEO1/blob/master/CIBERSORT.R
5. ExpressAnalystR. https://github.com/xia-lab/ExpressAnalystR/blob/main/R/norm_utils.R
6. scGPT `check_logged`. https://github.com/bowang-lab/scGPT/blob/main/scgpt/preprocess.py
7. Omics Playground `is_logged` (checked 2026-10-27). https://github.com/bigomics/playbase/blob/main/R/pgx-functions.R
8. DEP `make_se`. https://github.com/bioc/DEP/blob/devel/R/functions.R ; LFQ-Analyst. https://github.com/MonashBioinformaticsPlatform/LFQ-Analyst/blob/master/server.R
9. pmartR. https://rdrr.io/cran/pmartR/man/as.pepData.html
10. prolfqua. https://github.com/fgcz/prolfqua/blob/main/R/LFQDataTransformer.R
11. Perseus data conversion guide. https://conwaymsserver.ucd.ie/guides/proteomics/data-conversion.html
12. MSstats `dataProcess`. https://rdrr.io/bioc/MSstats/man/dataProcess.html
13. TMT-Integrator. https://github.com/Nesvilab/TMT-Integrator
14. Van Puyvelde et al., Sci Data 2022 (checked 2026-10-27). https://pmc.ncbi.nlm.nih.gov/articles/PMC8967878/
15. Proteome Discoverer 3.1 User Guide. https://docs.thermofisher.com/r/Proteome-Discoverer-3.1-User-Guide/en-US1467223947v1
16. Specht et al., Genome Biol 2021 (SCoPE2). https://genomebiology.biomedcentral.com/articles/10.1186/s13059-021-02267-5 ; scp. https://uclouvain-cbio.github.io/scp/articles/scp.html
17. Derks et al., plexDIA. https://pmc.ncbi.nlm.nih.gov/articles/PMC9839897/
18. Proteome Discoverer 3.1 User Guide, scaled abundances. https://docs.thermofisher.com/r/Proteome-Discoverer-3.1-User-Guide/en-US1324923659v1
19. NSAF. https://proteomicsresource.washington.edu/tools/adjnsaf.php
20. ibaqpy. https://github.com/bigbio/ibaqpy
21. MSstatsConvert, Skyline cleaning. https://github.com/Vitek-Lab/MSstatsConvert/blob/devel/R/clean_Skyline.R
22. DIA-NN README (checked 2026-10-27). https://github.com/vdemichev/DiaNN
23. FragPipe-Analyst imputation. https://fragpipe-analyst-doc.nesvilab.org/documentation/imputation.html
24. scpdata, hu2023. https://github.com/UCLouvain-CBIO/scpdata/blob/master/R/hu2023.R
25. Ahlmann-Eltze & Anders, proDA. https://www.biorxiv.org/content/10.1101/661496v2.full
26. O'Brien et al. 2018. https://pmc.ncbi.nlm.nih.gov/articles/PMC6249692/
27. Zubarev 2013. https://pubmed.ncbi.nlm.nih.gov/23307342/
28. Single cells on timsTOF Ultra. https://pmc.ncbi.nlm.nih.gov/articles/PMC11231172/
29. Beck et al. 2011 (U2OS). https://pmc.ncbi.nlm.nih.gov/articles/PMC3261713/
30. Tissue proteomes over 29 tissues. https://pmc.ncbi.nlm.nih.gov/articles/PMC6379049/
31. proDA data import (MaxQuant LFQ example). https://www.bioconductor.org/packages/devel/bioc/vignettes/proDA/inst/doc/data-import.html
32. MSstatsTMT `proteinSummarization`. https://rdrr.io/bioc/MSstatsTMT/man/proteinSummarization.html
33. Rocke & Durbin 2001. https://pubmed.ncbi.nlm.nih.gov/11747612/
34. Anderle et al. 2004. https://pubmed.ncbi.nlm.nih.gov/15284095/
35. Huber et al. 2002 (VSN). https://pubmed.ncbi.nlm.nih.gov/12169536/
36. Li & Smyth 2023. https://pmc.ncbi.nlm.nih.gov/articles/PMC10174703/
37. Vanderaa & Gatto 2023. https://arxiv.org/abs/2304.06654
38. Spread–level plot (Hoaglin, Mosteller & Tukey 1983), `car::spreadLevelPlot`. https://rdrr.io/cran/car/man/spreadLevelPlot.html
39. Berger, R. L. (1982), Multiparameter hypothesis testing and acceptance sampling, Technometrics 24(4), 295–300; cited for the size of intersection–union tests at https://rdrr.io/cran/jocre/man/iutsize.html
40. Hanley & Lippman-Hand 1983, the rule of three. https://jamanetwork.com/journals/jama/article-abstract/389714
41. Box & Cox 1964, via MASS `boxcox`. https://rdrr.io/cran/MASS/man/boxcox.html
42. `EnvStats::boxcoxCensored`. https://rdrr.io/cran/EnvStats/man/boxcoxCensored.html
