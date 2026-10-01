# Seurat CCA label transfer for the Track D extension, called by
# benchmark/baselines_run.py (tool "seurat"). Reads the inputs that script
# writes to its working directory, all already gene-fair and z-scored
# (benchmark/baselines_inputs.py):
#   rna.f32, query.f32   float32, genes x cells, column-major
#   genes.txt            gene names, in row order
#   rna_labels.csv       reference class per RNA cell
#   query_ids.csv        query cell ids, in column order
# The z-scored values are set as both "data" and "scale.data". Classes enter
# Seurat as safe tokens and are mapped back, so its name sanitising cannot
# change a label. Writes predictions.csv: cell_id, predicted, and score.<class>
# for every reference class.
#
#   Rscript seurat_cca_transfer.R WORKDIR N_RNA N_QUERY N_GENES SEED

args <- commandArgs(trailingOnly = TRUE)
dir <- args[1]
n_rna <- as.integer(args[2])
n_query <- as.integer(args[3])
n_genes <- as.integer(args[4])
seed <- as.integer(args[5])
set.seed(seed)
suppressMessages(library(Seurat))

read_f32 <- function(path, nrow, ncol) {
  con <- file(path, "rb")
  on.exit(close(con))
  matrix(readBin(con, what = "numeric", n = nrow * ncol, size = 4, endian = "little"), nrow = nrow, ncol = ncol)
}

genes <- sprintf("g%05d", seq_len(n_genes))  # safe feature names; the real ones are in genes.txt
labels <- read.csv(file.path(dir, "rna_labels.csv"), stringsAsFactors = FALSE)$label
query_ids <- read.csv(file.path(dir, "query_ids.csv"), colClasses = "character")$cell_id
classes <- sort(unique(labels))
tokens <- sprintf("class%02d", seq_along(classes))
token_of <- setNames(tokens, classes)

make_object <- function(x, prefix) {
  dimnames(x) <- list(genes, sprintf("%s%06d", prefix, seq_len(ncol(x))))
  object <- CreateSeuratObject(CreateAssayObject(data = x))
  SetAssayData(object, layer = "scale.data", new.data = x)
}
reference <- make_object(read_f32(file.path(dir, "rna.f32"), n_genes, n_rna), "r")
query <- make_object(read_f32(file.path(dir, "query.f32"), n_genes, n_query), "q")
reference$label <- unname(token_of[labels])

anchors <- FindTransferAnchors(reference = reference, query = query, features = genes,
                               reduction = "cca", dims = 1:30, verbose = FALSE)
predicted <- TransferData(anchorset = anchors, refdata = reference$label, dims = 1:30,
                          weight.reduction = "cca", verbose = FALSE)

out <- data.frame(cell_id = query_ids, predicted = classes[match(predicted$predicted.id, tokens)],
                  check.names = FALSE)
for (i in seq_along(classes)) {
  column <- paste0("prediction.score.", tokens[i])
  out[[paste0("score.", classes[i])]] <- if (column %in% colnames(predicted)) predicted[[column]] else 0
}
write.csv(out, file.path(dir, "predictions.csv"), row.names = FALSE)
cat(sprintf("seurat: %d anchors, %d query cells predicted\n", nrow(slot(anchors, "anchors")), nrow(out)))
