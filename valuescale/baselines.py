"""The baselines: the "already log?" rules other tools use, re-implemented.

The sealed test (research/value-scale-plan.md, B7) scores every rule here on
the same tables as the detector. Each rule is re-implemented from its source
at a pinned commit (SOURCES) as written: the same statistics, thresholds and
strict or inclusive comparisons, quirks included. Each function takes the
table the detector receives, genes x cells (rows proteins, columns samples
or cells), float64, NaN where missing, and returns:
- "linear" when the rule treats the table as not log-transformed (it would
  take a log, or calls the values raw, linear or counts);
- "log" when it treats the table as already logged, or otherwise
  transformed so that no log is taken;
- None when the rule cannot answer (the tool raises, returns NA, or returns
  a "don't know" type).

The rules in plain words (each function's docstring quotes its source):
- geo2r: the 99th percentile above 100, or a range above 50 with the 25th
  percentile above 0, means not yet log.
- expressanalyst: any negative, or more than half the values non-integers
  with every absolute value below 50, means already log.
- scgpt: already log1p when every value is in [0, 30] and some value is in
  (0, 1).
- omics_playground: possibly log when the maximum is below 60 or the minimum
  below -1, unless the rows are ratios, the maximum is above 1000, the values
  are counts, or it is a big zero-inflated single-cell table.
- proteopy: already log when at least 0.5% of the values are negative or the
  95th percentile is at most 100.
- gemma: a cascade (percent, counts, z-score, log-counts, then bounds on the
  maximum, then negatives); the type it infers maps to a reading.
- celltypist: log1p-normalised when the first 1000 cells lie within
  [0, 9.22].
- cibersort: a maximum below 50 means log (CIBERSORT then anti-logs).
- median_50: the projection service's old rule for protein: no negative and
  a median of the non-zero values above 50 means linear.

The rulings for every rule (made for B4, in the plan's ledger):
- **Missing values are left out.** Every statistic a rule computes uses the
  observed values only: pooled statistics use all of them, per-sample
  statistics each column's. This holds even where the tool itself would stop
  on a missing value (CIBERSORT; GEO2R on an all-missing table) or change
  behaviour because NaN poisons a max or a min (scGPT, CellTypist): each rule
  is scored as written on the values it would see if the missing ones were
  left out.
- A table with no observed value gets None from every rule.
- Zeros are values and are kept: the tools see the zeros a file holds.

Read from those rulings here:
- A sample (column) with no observed value is left out as a sample: it
  holds no value to compute on. That matters only where columns are counted
  or picked (Omics Playground's column counts, CellTypist's first 1000
  cells, Gemma's per-sample tests and first sample).
- +/-inf are values, not missing (the ruling is about NaN): each rule
  treats them as its source does (GEO2R, CIBERSORT, scGPT, CellTypist and
  Omics Playground keep them; ExpressAnalyst, ProteoPy and the median rule
  drop them; Gemma drops them from its maximum and minimum and keeps them in
  its means and medians).

numpy and the standard library only, like the rest of the package.
"""
from __future__ import annotations

import math
from typing import Callable

import numpy as np


def _matrix(values) -> np.ndarray:
    x = np.asarray(values, dtype=np.float64)
    if x.ndim != 2:
        raise ValueError(f"values must be a genes x cells matrix, got {x.ndim} dimension(s)")
    return x


def _observed(x: np.ndarray) -> np.ndarray:
    return x[~np.isnan(x)]


def _samples(x: np.ndarray) -> np.ndarray:
    """The columns that hold at least one observed value."""
    return x[:, (~np.isnan(x)).any(axis=0)]


# R's logicals, for the R rules: True, False, or None for NA. `||` and `&&`
# follow R: TRUE || NA is TRUE, FALSE || NA is NA, FALSE && NA is FALSE,
# TRUE && NA is NA. A comparison with NaN is NA.
def _r_or(a: bool | None, b: bool | None) -> bool | None:
    if a is True or b is True:
        return True
    return None if a is None or b is None else False


def _r_and(a: bool | None, b: bool | None) -> bool | None:
    if a is False or b is False:
        return False
    return None if a is None or b is None else True


def _r_not(a: bool | None) -> bool | None:
    return None if a is None else not a


def _r_gt(a: float, b: float) -> bool | None:
    return None if math.isnan(a) or math.isnan(b) else a > b


def _r_lt(a: float, b: float) -> bool | None:
    return None if math.isnan(a) or math.isnan(b) else a < b


def _more_than_half(count: int, n: int) -> bool:
    """R's mean(logical) > 0.5, exactly: count / n > 1/2."""
    return 2 * count > n


# --- GEO2R ---------------------------------------------------------------------------------------

GEO2R_PROBS = (0.0, 0.25, 0.5, 0.75, 0.99, 1.0)


def _r_quantile7(sorted_values: np.ndarray, probs) -> list[float]:
    """R's quantile(x, probs) of type 7, the default, on sorted values with
    no NA, computed as stats:::quantile.default does it (R 4.6.1):
        index <- 1 + max(n - 1, 0) * probs; lo <- floor(index); hi <- ceiling(index)
        qs <- x[lo]; i <- which(index > lo & x[hi] != qs)
        qs[i] <- (1 - h) * qs[i] + h * x[hi[i]]
    This is numpy's default "linear" method; R's arithmetic is kept so an
    infinite value gives R's answer (numpy's interpolation turns some into
    NaN)."""
    n = sorted_values.size
    out = []
    for p in probs:
        index = 1 + (n - 1) * p
        lo, hi = math.floor(index), math.ceil(index)
        qs, upper = float(sorted_values[lo - 1]), float(sorted_values[hi - 1])
        if index > lo and upper != qs:
            h = index - lo
            qs = (1 - h) * qs + h * upper
        out.append(qs)
    return out


def geo2r(values) -> str | None:
    """GEO2R's auto-detect, the current two-clause rule (new-style GEO2R
    scripts, and GEOexplorer, which reuses it):

        qx <- as.numeric(quantile(ex, c(0., 0.25, 0.5, 0.75, 0.99, 1.0), na.rm=T))
        LogC <- (qx[5] > 100) ||
          (qx[6]-qx[1] > 50 && qx[2] > 0)
        if (LogC) { ex[which(ex <= 0)] <- NaN
        exprs(gset) <- log2(ex) }

    https://github.com/saifusa21/Health-and-Bioinformatics-Project/blob/dfd806f900a04751c08ea4ccf4037fbd26cbca96/With%20Force%20Normalization.R#L21-L27
    https://github.com/guypwhunt/GEOexplorer/blob/77a7e56a1a9dec3e517ee4560f9b001887619bb7/R/backendExploratoryDataAnalysisDataFunctions.R#L455-L483

    The quantiles pool every observed value (GEO2R pools the samples
    assigned to a group; here, all columns). R's type 7, so numpy's default
    linear method. +/-inf are kept, as na.rm keeps them.

    LogC TRUE -> "linear" (GEO2R takes log2); FALSE -> "log"; NA (a quantile
    that is NaN, e.g. -inf and inf interpolated; the script stops at
    if (LogC)) -> None.

    Older GEO2R scripts (generated to at least 2018-09-24) had a third
    clause, `(qx[2] > 0 && qx[2] < 1 && qx[4] > 1 && qx[4] < 2)`, which calls
    unlogged ratios centred near 1 linear; it is not implemented here:
    https://github.com/hakyimlab/PrediXcan/blob/67efaef8eb022c7f3109f905b9fa40cac3a20255/Paper-Scripts/Eric/GEO.replication.RA.r#L22-L29
    """
    seen = np.sort(_observed(_matrix(values)))
    if seen.size == 0:
        return None
    q0, q25, _q50, _q75, q99, q100 = _r_quantile7(seen, GEO2R_PROBS)
    log_c = _r_or(_r_gt(q99, 100), _r_and(_r_gt(q100 - q0, 50), _r_gt(q25, 0)))
    if log_c is None:
        return None
    return "linear" if log_c else "log"


# --- ExpressAnalyst ------------------------------------------------------------------------------

def expressanalyst(values) -> str | None:
    """ExpressAnalystR's PerformNormalization, the rule added 2026-08-03
    (norm_utils.R), run when a count or raw method is requested:

        fin      <- m.chk[is.finite(m.chk)]
        has.neg  <- any(fin < 0)
        non.int  <- length(fin) > 0 && mean(abs(fin - round(fin)) > 1e-8) > 0.5
        small    <- length(fin) > 0 && max(abs(fin)) < 50
        is.log   <- has.neg || (non.int && small)

    https://github.com/xia-lab/ExpressAnalystR/blob/2d29fac8b5abdbe313974cf835ee7bca06a1abb5/R/norm_utils.R#L97-L103

    Before it, `data <- sanitizeSmallNumbers(data)` (norm_utils.R L66) sets
    `mat[abs(mat) < tol] <- 0` with tol = 1e-10, so a negative that small is
    not a negative:
    https://github.com/xia-lab/ExpressAnalystR/blob/50c122ce1ad82c4bab9fa4616658e1eb1b45109c/R/misc_utils.R#L1074-L1080

    Finite values only, pooled; zeros are integers and not negative. More
    than half is strict, the integer tolerance is absolute, and max |x| < 50
    is strict. The rule runs on the table as given, not after ExpressAnalyst's
    own filtering.

    is.log TRUE -> "log" (the method becomes per-sample median centring, no
    log); FALSE -> "linear" (the requested method runs and logs the data).
    """
    seen = _observed(_matrix(values))
    if seen.size == 0:
        return None
    sanitized = np.where(np.abs(seen) < 1e-10, 0.0, seen)
    fin = sanitized[np.isfinite(sanitized)]
    has_neg = bool((fin < 0).any())
    non_int = fin.size > 0 and _more_than_half(int(np.count_nonzero(np.abs(fin - np.round(fin)) > 1e-8)), fin.size)
    small = fin.size > 0 and float(np.abs(fin).max()) < 50
    return "log" if has_neg or (non_int and small) else "linear"


# --- scGPT ---------------------------------------------------------------------------------------

def scgpt(values) -> str | None:
    """scGPT's Preprocessor.check_logged:

        max_, min_ = data.max(), data.min()
        if max_ > 30:
            return False
        if min_ < 0:
            return False

        non_zero_min = data[data > 0].min()
        if non_zero_min >= 1:
            return False

        return True

    https://github.com/bowang-lab/scGPT/blob/f35fbecdea002d072e03e9c3bbf01bbb3c0cf3ce/scgpt/preprocess.py#L213-L236

    The whole table pooled; the "non-zero" minimum is the smallest strictly
    positive value (`data > 0`), so zeros are ignored there. Missing values
    are left out of the max and the min: in scGPT a single NaN makes both
    NaN, which silently skips the first two tests.

    True -> "log"; False -> "linear". No positive value left for the third
    test -> None (scGPT raises "zero-size array to reduction operation
    minimum").
    """
    seen = _observed(_matrix(values))
    if seen.size == 0:
        return None
    if seen.max() > 30:
        return "linear"
    if seen.min() < 0:
        return "linear"
    positive = seen[seen > 0]
    if positive.size == 0:
        return None
    if positive.min() >= 1:
        return "linear"
    return "log"


# --- Omics Playground ----------------------------------------------------------------------------

def _row_means_are_ratios(x: np.ndarray) -> bool | None:
    """is.ratio: rowMeans(x, na.rm = TRUE), rows with no mean (NaN) dropped,
    then sd / mean < 0.01 with R's sd (n - 1). NA when that is NaN, or when
    fewer than two row means are left (sd of one value is NA)."""
    observed = ~np.isnan(x)
    with np.errstate(invalid="ignore", divide="ignore"):
        means = np.where(observed, x, 0.0).sum(axis=1) / observed.sum(axis=1)
        means = means[~np.isnan(means)]
        if means.size < 2:
            return None
        cv = np.std(means, ddof=1) / np.mean(means)
    return _r_lt(float(cv), 0.01)


def omics_playground(values) -> str | None:
    """Omics Playground's is_logged (BigOmics playbase, pgx-functions.R),
    the dense-matrix branch:

        xmax <- max(x, na.rm = TRUE)
        all.lt60 <- xmax < 60
        has.bigx <- xmax > 1000
        xmin <- min(x, na.rm = TRUE)
        minx.neg <- xmin < -1
        all.pos <- xmin >= 0
        is.ratio <- FALSE
        if (NCOL(x) > 1 && all.pos) {
          rowx.mean <- Matrix::rowMeans(x, na.rm = TRUE)
          rowx.mean <- rowx.mean[!is.na(rowx.mean)]
          is.ratio <- (sd(rowx.mean) / mean(rowx.mean)) < 0.01
        }
        fraction.diff <- (x - round(x)) / mean(x, na.rm = TRUE)
        all.integer <- max(fraction.diff, na.rm = TRUE) < 1e-8
        is.counts <- all.pos && all.integer
        zero.inflated <- mean((is.na(x) | x == 0)) > 0.5
        is.singlecell <- NCOL(x) > 1000 && all.pos && all.lt60 && zero.inflated
        possible.log <- (all.lt60 || minx.neg)
        possible.linear <- (is.ratio || has.bigx || is.counts || is.singlecell)
        is.log <- possible.log && !possible.linear

    https://github.com/bigomics/playbase/blob/92ad155136e6ae2d298fa78f940bd4be59abd674/R/pgx-functions.R#L2514-L2583

    Ported as written: R's sd (n - 1); the integer test takes the signed
    maximum of (x - round(x)) / mean, so a table whose fractional parts are
    all above .5 counts as integers; an all-zero table counts as integers
    (every ratio is NaN, the maximum of nothing is -Inf). NA propagates as
    in R, so is.ratio can make the answer NA. Two departures, both from the
    missing-values ruling: zero.inflated counts only observed zeros among
    observed values (the source counts NA as zero), and NCOL counts only the
    samples with an observed value. R's mean and rowMeans sum in long
    double; numpy's sums can differ in the last bit, which matters only for
    a table on the 1e-8 or 0.01 edge.

    is.log TRUE -> "log"; FALSE -> "linear"; NA -> None.
    """
    x = _samples(_matrix(values))
    seen = _observed(x)
    if seen.size == 0:
        return None
    xmax, xmin = float(seen.max()), float(seen.min())
    all_lt60 = xmax < 60
    has_bigx = xmax > 1000
    minx_neg = xmin < -1
    all_pos = xmin >= 0
    columns = x.shape[1]
    is_ratio: bool | None = False
    if columns > 1 and all_pos:
        is_ratio = _row_means_are_ratios(x)
    with np.errstate(invalid="ignore", divide="ignore"):
        fraction_diff = (seen - np.round(seen)) / np.mean(seen)
    fraction_diff = fraction_diff[~np.isnan(fraction_diff)]
    all_integer = (float(fraction_diff.max()) if fraction_diff.size else -math.inf) < 1e-8
    is_counts = all_pos and all_integer
    zero_inflated = _more_than_half(int(np.count_nonzero(seen == 0)), seen.size)
    is_singlecell = columns > 1000 and all_pos and all_lt60 and zero_inflated
    possible_log = all_lt60 or minx_neg
    possible_linear = _r_or(_r_or(_r_or(is_ratio, has_bigx), is_counts), is_singlecell)
    is_log = _r_and(possible_log, _r_not(possible_linear))
    if is_log is None:
        return None
    return "log" if is_log else "linear"


# --- ProteoPy ------------------------------------------------------------------------------------

def proteopy(values) -> str | None:
    """ProteoPy's is_log_transformed (_is_log_transformed_array), with its
    defaults neg_frac_thresh=5e-3 and p95_thresh=100.0:

        finite = np.isfinite(X)
        vals = X[finite]
        if vals.size == 0:
            raise ValueError("No finite values found.")

        frac_negative = float(np.mean(vals < 0))
        p95 = float(np.nanpercentile(vals, 95))
        ...
        is_log = (
            frac_negative >= neg_frac_thresh
            or p95 <= p95_thresh
        )

    https://github.com/UKHD-NP/proteopy/blob/de35f963ea9e5be76625a64d82774b21e5528c31/proteopy/utils/array.py#L30-L45

    Finite values pooled, zeros kept (the public function; impute_downshift
    and normalize_median turn zeros into NaN first only when asked to).

    True -> "log"; False -> "linear"; no finite value -> None (it raises).
    """
    x = _matrix(values)
    vals = x[np.isfinite(x)]
    if vals.size == 0:
        return None
    frac_negative = float(np.mean(vals < 0))
    p95 = float(np.nanpercentile(vals, 95))
    return "log" if frac_negative >= 5e-3 or p95 <= 100.0 else "linear"


# --- Gemma ---------------------------------------------------------------------------------------

GEMMA_ATOL = 1e-8  # QuantitationTypeDetectionUtils.ATOL
GEMMA_RTOL = 1e-5  # .RTOL
GEMMA_LOG_COUNT_ATOL = 1e-32  # isLogTransformedCount's atol
GEMMA_BOUNDS = (4.81, 11.0, 20.0)
GEMMA_RATIOMETRIC_BOUNDS = (2.5, 2.5, 12.0)
GEMMA_BOUND_SCALES = ("LOG10", "LOGBASEUNKNOWN", "LOG2")
GEMMA_LINEAR_FROM = 10 ** 3.2  # Math.pow( 10, 3.2 ), 1584.89...

# The scale of the inferred type, to a reading. A ZSCORE type reads "log"
# whatever its scale: Gemma converts only amounts and counts to log2
# (QuantitationTypeConversionUtils L87-L89), so no log is taken.
_GEMMA_SCALE_READING = {
    "LINEAR": "linear", "COUNT": "linear",
    "LOG2": "log", "LOG10": "log", "LN": "log", "LOG1P": "log", "LOGBASEUNKNOWN": "log",
    "PERCENT": None, "PERCENT1": None, "OTHER": None,
}


def _close_to_zero(a: float) -> bool:
    return a == 0.0 or abs(a) < GEMMA_ATOL


def _close(a: float, b: float) -> bool:
    return a == b or abs(a - b) < GEMMA_RTOL * abs(b) + GEMMA_ATOL


def _java_mean(column: np.ndarray) -> float:
    """DescriptiveWithMissing.mean on a column with no NaN: the sum, added
    left to right as Java's loop adds it (np.cumsum is sequential), over the
    count. +/-inf are kept."""
    if column.size == 0:
        return math.nan
    with np.errstate(invalid="ignore", over="ignore"):
        total = float(np.cumsum(column)[-1])
    return total / column.size


def _colt_median(sorted_column: np.ndarray) -> float:
    """cern.jet.stat.Descriptive.median (Colt 1.2.0) of sorted values, read
    from the jar's bytecode: quantile(data, 0.5), which returns 0.0 for no
    value, and otherwise (1 - delta) * x[lhs] + delta * x[lhs + 1] with
    index = 0.5 * (n - 1), lhs = (int) index. For an odd count that is
    1 * x[mid] + 0 * x[mid + 1], NaN when the next value is +inf."""
    n = sorted_column.size
    if n == 0:
        return 0.0
    index = 0.5 * (n - 1)
    lhs = int(index)
    delta = index - lhs
    if lhs == n - 1:
        return float(sorted_column[lhs])
    return (1 - delta) * float(sorted_column[lhs]) + delta * float(sorted_column[lhs + 1])


def _gemma_zscore(columns: list[np.ndarray]) -> bool:
    """isZScore: some sample has a mean, or else a median, close to zero."""
    for column in columns:
        if _close_to_zero(_java_mean(column)):
            return True
        if _close_to_zero(_colt_median(np.sort(column))):
            return True
    return False


def _gemma_log_counts(first: np.ndarray) -> tuple[str, str] | None:
    """isLogTransformedCount on the first sample's distinct finite values."""
    finite = first[np.isfinite(first)]
    # Java's sorted().distinct() compares as Double.compare: 0.0 and -0.0 are two values.
    distinct = np.unique(finite.view(np.int64)).view(np.float64)
    if distinct.size < 10:
        return None
    with np.errstate(all="ignore"):
        for base, scale in ((2.0, "LOG2"), (math.e, "LN"), (10.0, "LOG10")):
            back = np.log(np.rint(np.power(base, distinct))) / np.log(base)
            if np.all(np.abs(back - distinct) < GEMMA_LOG_COUNT_ATOL):
                return ("COUNT", scale)
        # abs() before the subtraction, as in the source: one-sided
        if np.all(np.abs(np.log1p(np.rint(np.expm1(distinct)))) - distinct < GEMMA_LOG_COUNT_ATOL):
            return ("COUNT", "LOG1P")
    return None


def _gemma_infer(values) -> tuple[str, str]:
    """QuantitationTypeDetectionUtils.infer as (type, scale), for a table
    that is not microarray, with no recorded quantitation type (qt null, as
    inferQuantitationType passes). The table must hold an observed value."""
    x = _samples(_matrix(values))
    columns = [column[~np.isnan(column)] for column in x.T]
    seen = _observed(x)
    ip = bool(np.all((seen >= 0.0) & (seen <= 1.0)))  # isPercent
    ic = seen.size >= 10 and bool(np.all((seen >= 0) & (np.rint(seen) == seen)))  # isCount
    if ip and ic:
        return ("PRESENTABSENT", "OTHER")
    if ip:
        return ("AMOUNT", "PERCENT1")
    if ic:
        return ("COUNT", "COUNT")
    finite = seen[np.isfinite(seen)]
    maximum = float(finite.max()) if finite.size else math.nan
    if _close(maximum, 100) and bool(np.all((seen >= 0.0) & (seen <= 100.0))):  # isPercent100
        return ("AMOUNT", "PERCENT")
    if _gemma_zscore(columns):
        return ("ZSCORE", "LOGBASEUNKNOWN" if maximum < 20 else "OTHER")
    log_counts = _gemma_log_counts(columns[0])
    if log_counts is not None:
        return log_counts
    ratiometric = all(abs(_java_mean(column)) < 2 for column in columns)
    for bound, scale in zip(GEMMA_RATIOMETRIC_BOUNDS if ratiometric else GEMMA_BOUNDS, GEMMA_BOUND_SCALES):
        if maximum < bound:
            return ("AMOUNT", scale)
    minimum = float(finite.min()) if finite.size else math.nan
    if minimum < 0:
        return ("AMOUNT", "LOGBASEUNKNOWN")
    scale = "LINEAR" if maximum >= GEMMA_LINEAR_FROM else "OTHER"
    with np.errstate(divide="ignore", invalid="ignore"):
        logged = [np.log(column) for column in columns]
    if _gemma_zscore([column[~np.isnan(column)] for column in logged]):  # NaN-skipping, as Gemma's statistics
        return ("ZSCORE", scale)
    return ("AMOUNT", scale)


def _gemma_reading(kind: str, scale: str) -> str | None:
    return "log" if kind == "ZSCORE" else _GEMMA_SCALE_READING[scale]


def gemma(values) -> str | None:
    """Gemma's QuantitationTypeDetectionUtils.infer, the cascade in order
    (the first match wins; the decisive lines, L163-L244):

        if ( ip && ic ) {
            return new InferredQuantitationType( StandardQuantitationType.PRESENTABSENT, ScaleType.OTHER, false );
        if ( ip ) {
            return new InferredQuantitationType( StandardQuantitationType.AMOUNT, ScaleType.PERCENT1, false );
        if ( ic ) {
            return new InferredQuantitationType( StandardQuantitationType.COUNT, ScaleType.COUNT, false );
        if ( isPercent100( matrix, maximum ) ) {
            return new InferredQuantitationType( StandardQuantitationType.AMOUNT, ScaleType.PERCENT, false );
        if ( isZScore( matrix ) ) {
            return new InferredQuantitationType( StandardQuantitationType.ZSCORE,
                    maximum < 20 ? ScaleType.LOGBASEUNKNOWN : ScaleType.OTHER, false );  [one line in the source]
        if ( ( iqt = isLogTransformedCount( matrix ) ) != null ) {
        final double[] upperBounds = { 4.81, 11, 20 };
        final double[] ratiometricUpperBounds = { 2.5, 2.5, 12 };
        final ScaleType[] types = { ScaleType.LOG10, ScaleType.LOGBASEUNKNOWN, ScaleType.LOG2 };
        boolean ir = isRatiometric( matrix );
        double[] bounds = ir ? ratiometricUpperBounds : upperBounds;
            if ( maximum < bounds[i] ) {
                return new InferredQuantitationType( StandardQuantitationType.AMOUNT, types[i], ir );
        if ( minimum < 0 ) {
            return new InferredQuantitationType( StandardQuantitationType.AMOUNT, ScaleType.LOGBASEUNKNOWN, ir );
        ScaleType scaleType = maximum >= Math.pow( 10, 3.2 ) ? ScaleType.LINEAR : ScaleType.OTHER;
        if ( isZScore( logMatrix ) ) {
            return new InferredQuantitationType( StandardQuantitationType.ZSCORE, scaleType, false );
        return new InferredQuantitationType( StandardQuantitationType.AMOUNT, scaleType, false );

    https://github.com/PavlidisLab/Gemma/blob/58332e07b49196ccefb5213e7a80fc01ab1ea66a/gemma-core/src/main/java/ubic/gemma/core/analysis/preprocess/detect/QuantitationTypeDetectionUtils.java#L133-L245
    (helpers L247-L310 and L331-L555; the mean and median skip NaN,
    DescriptiveWithMissing.java L304-L306 and L382-L386; the median is Colt
    1.2.0's, https://repo1.maven.org/maven2/colt/colt/1.2.0/colt-1.2.0.jar)

    In words: isPercent, every value in [0, 1]; isCount, at least 10 values,
    each >= 0 and equal to its Math.rint (so +inf passes); isPercent100, the
    maximum within 1e-5 * 100 + 1e-8 of 100 and every value in [0, 100];
    isZScore, some sample's mean, or else median, within 1e-8 of zero;
    isLogTransformedCount, the first sample's distinct finite values (10 or
    more) each satisfy |log(rint(base^v)) / log(base) - v| < 1e-32 for base
    2, e or 10 (in that order), or else
    `Math.abs( Math.log1p( Math.rint( Math.expm1( val ) ) ) ) - val < atol`;
    isRatiometric, every sample mean below 2 in size. The maximum and the
    minimum are over finite values only.

    For a table that is not microarray (a protein table has no platform, so
    rounded values stay counts) and with no recorded quantitation type (qt
    null, as inferQuantitationType passes, so negatives always mean a log).
    Missing values are left out of every test (Gemma's own isPercent,
    isPercent100 and isCount fail on any NaN, and isCount counts every cell
    toward its 10), and a sample with no observed value is left out (Colt's
    median of nothing is 0.0, which would make that sample a z-score).

    Quirks ported as written: the log1p test applies abs() before the
    subtraction, so it is one-sided (a value passes whenever expm1(v) rounds
    down; any first sample within [0, ln 1.5) passes); log1p(k) of an integer
    k is ln(k + 1), so log1p counts are reported LN, which is tested first;
    the 1e-32 tolerance demands exact equality. That is where a Python port
    can disagree with Java: numpy's log, power, expm1 and log1p may differ
    from Java's Math in the last bit, so on a first sample made of exact
    log-counts one side may pass and the other fail. The reading then
    differs only when the steps after it would not say log (a maximum of 20
    or more, 12 if ratiometric, and no negative). Python's 10 ** 3.2 and
    Java's Math.pow( 10, 3.2 ) may differ in the last bit too. The sums
    follow Java's order, so the means match it.

    The inferred type to a reading: ZSCORE -> "log" (Gemma converts only
    amounts and counts to log2, so no log is taken:
    QuantitationTypeConversionUtils.java L87-L89 at the same commit); scale
    LINEAR or COUNT -> "linear"; LOG2, LOG10, LN, LOG1P or LOGBASEUNKNOWN ->
    "log"; PERCENT, PERCENT1 or OTHER (PRESENTABSENT included) -> None.
    """
    x = _matrix(values)
    if not (~np.isnan(x)).any():
        return None
    return _gemma_reading(*_gemma_infer(x))


# --- CellTypist ----------------------------------------------------------------------------------

CELLTYPIST_MAX = 9.22
CELLTYPIST_CELLS = 1000


def celltypist(values) -> str | None:
    """CellTypist's range check on prediction input (Classifier, AnnData or
    .h5ad):

        if (self.adata.X[:1000].min() < 0) or (self.adata.X[:1000].max() > 9.22):
            if not self.adata.raw:
                raise ValueError(

    with the message "Invalid expression matrix in `.X`, expect log1p
    normalized expression to 10000 counts per cell".

    https://github.com/Teichlab/celltypist/blob/f7cd78e2fe1c9803f4c69a1756f609d24147695c/celltypist/classifier.py#L307-L327

    The first 1000 cells are the first 1000 columns here (AnnData rows are
    cells), the samples with an observed value. Missing values are left out
    of the min and the max (in CellTypist one NaN makes both NaN and the
    check passes). The row-sum check on the first cell that follows
    (`np.abs(np.expm1(self.indata[0]).sum()-10000) > 1`) only warns in
    prediction, so it does not decide; the .raw fallback has no protein
    analogue.

    Outside [0, 9.22] -> "linear" (not log1p-normalised); within -> "log".
    """
    x = _samples(_matrix(values))
    if x.shape[1] == 0:
        return None
    first = _observed(x[:, :CELLTYPIST_CELLS])
    if first.min() < 0 or first.max() > CELLTYPIST_MAX:
        return "linear"
    return "log"


# --- CIBERSORT -----------------------------------------------------------------------------------

def cibersort(values) -> str | None:
    """CIBERSORT's anti-log check on the mixture file (CIBERSORT.R v1.04):

        #anti-log if max < 50 in mixture file
        if(max(Y) < 50) {Y <- 2^Y}

    https://github.com/margenomics/Deconvolution/blob/433e748059e1fd5d9fdbe43810ae8ed417338aee/CIBERSORT.R#L153-L154
    https://github.com/singha53/amritr/blob/879b1a4fbdbd526e535256e9084cf13bb4afef39/R/supportFunc_cibersort.R#L137-L138

    The official script needs a registration (cibersortx.stanford.edu), so
    the rule is re-implemented from these two mirrors, which agree, and the
    published description: "CIBERSORT works best on expression values in
    non-log linear space" (Newman et al., Nat Methods 2015, Online Methods;
    doi:10.1038/nmeth.3337; the paper does not give the threshold). The
    maximum of the whole table; missing values are left out (max(Y) has no
    na.rm, so CIBERSORT itself stops on any NA).

    Maximum below 50 -> "log" (it anti-logs); otherwise -> "linear".
    """
    seen = _observed(_matrix(values))
    if seen.size == 0:
        return None
    return "log" if float(seen.max()) < 50 else "linear"


# --- median_50 -----------------------------------------------------------------------------------

MEDIAN_THRESHOLD = 50.0  # service/config.py LINEAR_SCALE_MEDIAN_THRESHOLD


def median_50(values) -> str | None:
    """The projection service's old rule for protein, copied from
    service/pipeline/alignment.py median_rule with zeros_vote False and
    median_threshold 50 (not imported: valuescale never imports the
    service):

        observed = np.isfinite(values)
        if not observed.any():
            return "unknown"
        observed_values = values[observed]
        has_negative = bool((observed_values < 0).any())
        voters = observed_values if zeros_vote else observed_values[observed_values != 0]
        median_value = float(np.median(voters)) if voters.size else 0.0
        return "linear" if (not has_negative) and (median_value > median_threshold) else "log"

    https://github.com/Amrita-Stanford-Development/Vivome_Atlas/blob/80160251f4be0a09fee5704b6c80d2ef3fbf5602/service/pipeline/alignment.py#L535-L554

    Finite values only; zeros do not vote; no voter left gives a median of
    0. Any negative -> "log"; a median above 50 -> "linear", else "log";
    "unknown" (no finite value) -> None. Any array shape, as median_rule.
    """
    values = np.asarray(values, dtype=np.float64)
    observed = np.isfinite(values)
    if not observed.any():
        return None
    observed_values = values[observed]
    has_negative = bool((observed_values < 0).any())
    voters = observed_values[observed_values != 0]
    median_value = float(np.median(voters)) if voters.size else 0.0
    return "linear" if (not has_negative) and (median_value > MEDIAN_THRESHOLD) else "log"


# --- The registry --------------------------------------------------------------------------------

BASELINES: dict[str, Callable[[np.ndarray], str | None]] = {
    "geo2r": geo2r,
    "expressanalyst": expressanalyst,
    "scgpt": scgpt,
    "omics_playground": omics_playground,
    "proteopy": proteopy,
    "gemma": gemma,
    "celltypist": celltypist,
    "cibersort": cibersort,
    "median_50": median_50,
}

_GEMMA_DETECT = ("https://github.com/PavlidisLab/Gemma/blob/58332e07b49196ccefb5213e7a80fc01ab1ea66a/gemma-core/"
                 "src/main/java/ubic/gemma/core/analysis/preprocess/detect/QuantitationTypeDetectionUtils.java")
_GEMMA_MATH = ("https://github.com/PavlidisLab/Gemma/blob/58332e07b49196ccefb5213e7a80fc01ab1ea66a/gemma-core/"
               "src/main/java/ubic/gemma/core/util/math/DescriptiveWithMissing.java")

SOURCES: dict[str, tuple[str, ...]] = {
    "geo2r": (
        "https://github.com/saifusa21/Health-and-Bioinformatics-Project/blob/dfd806f900a04751c08ea4ccf4037fbd26cbca96/"
        "With%20Force%20Normalization.R#L21-L27",
        "https://github.com/nancyalnassar/DMD-gene-in-cancer/blob/b3cc111a468f737bf3576f25c0aac336b57b6a54/"
        "GEO2R%20Script#L21-L27",
        "https://github.com/guypwhunt/GEOexplorer/blob/77a7e56a1a9dec3e517ee4560f9b001887619bb7/"
        "R/backendExploratoryDataAnalysisDataFunctions.R#L455-L483",
        "https://github.com/bioc/GEOexplorer/blob/77a7e56a1a9dec3e517ee4560f9b001887619bb7/"
        "R/backendExploratoryDataAnalysisDataFunctions.R#L455-L483",
        "https://git.lsit.ucsb.edu/publicdata/nih-gov/src/commit/16b4b23030b9c25e5a647a69ebd82dc9aecccaad/"
        "www.ncbi.nlm.nih.gov/geo/info/geo2r.html#L428-L434",
    ),
    "expressanalyst": (
        "https://github.com/xia-lab/ExpressAnalystR/blob/2d29fac8b5abdbe313974cf835ee7bca06a1abb5/"
        "R/norm_utils.R#L97-L103",
        "https://github.com/xia-lab/ExpressAnalystR/blob/2d29fac8b5abdbe313974cf835ee7bca06a1abb5/"
        "R/norm_utils.R#L62-L66",
        "https://github.com/xia-lab/ExpressAnalystR/blob/50c122ce1ad82c4bab9fa4616658e1eb1b45109c/"
        "R/misc_utils.R#L1074-L1080",
    ),
    "scgpt": (
        "https://github.com/bowang-lab/scGPT/blob/f35fbecdea002d072e03e9c3bbf01bbb3c0cf3ce/"
        "scgpt/preprocess.py#L213-L236",
    ),
    "omics_playground": (
        "https://github.com/bigomics/playbase/blob/92ad155136e6ae2d298fa78f940bd4be59abd674/"
        "R/pgx-functions.R#L2514-L2583",
    ),
    "proteopy": (
        "https://github.com/UKHD-NP/proteopy/blob/de35f963ea9e5be76625a64d82774b21e5528c31/"
        "proteopy/utils/array.py#L30-L45",
    ),
    "gemma": (
        _GEMMA_DETECT + "#L133-L245",
        _GEMMA_DETECT + "#L247-L310",
        _GEMMA_DETECT + "#L331-L555",
        _GEMMA_MATH + "#L304-L306",
        _GEMMA_MATH + "#L382-L386",
    ),
    "celltypist": (
        "https://github.com/Teichlab/celltypist/blob/f7cd78e2fe1c9803f4c69a1756f609d24147695c/"
        "celltypist/classifier.py#L307-L327",
    ),
    "cibersort": (
        "https://github.com/margenomics/Deconvolution/blob/433e748059e1fd5d9fdbe43810ae8ed417338aee/"
        "CIBERSORT.R#L153-L154",
        "https://github.com/singha53/amritr/blob/879b1a4fbdbd526e535256e9084cf13bb4afef39/"
        "R/supportFunc_cibersort.R#L137-L138",
    ),
    "median_50": (
        "https://github.com/Amrita-Stanford-Development/Vivome_Atlas/blob/80160251f4be0a09fee5704b6c80d2ef3fbf5602/"
        "service/pipeline/alignment.py#L535-L554",
    ),
}
