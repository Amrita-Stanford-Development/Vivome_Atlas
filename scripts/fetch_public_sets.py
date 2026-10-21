"""Fetches the public datasets chosen on 2026-10-14 into data/incoming/public_sets/
(research/benchmark/side-tests.md lists what each one is for and why).

Each entry has a role:
- reference: sorted bulk proteomes (Rieckmann; Khoury's), free to use for development and
  diagnosis, except Khoury's, which belongs to a post-hoc-only study: diagnosis only, never
  used to build or tune a model;
- development: free to use for development (since 2026-10-15, the owner's
  decision, this includes some sets first chosen as side tests);
- held_out: the internal test, locked on 2026-10-15 before any development:
  nothing opens these files until the end, when each is scored once on the
  final candidates under its own committed protocol;
- reserve: not downloaded, kept as a future test or future development data
  (tier B's single HeLa and HEK293T). research/benchmark/side-tests.md lists
  the other alternatives.

Tier C is the colon reference's data (side-tests.md, amendment 7; about 9 MB):
PXD052341, the colon's locked test, and the development sets PXD057118 and
PXD046999 (Deep Visual Proteomics pools). Tier L is the lung's (amendment 9;
about 930 MB): MSV000094189, the lung's locked test, and the development sets
MSV000094373, the Human Protein Atlas DVP samples and PXD029341. Tier N is the
lymph node's (amendment 11; about 2.6 GB): PXD042367's tonsil-niche results,
its locked test, and the development sets PXD047762, Zheng's tonsil tables
and PXD011683. Tier V is the organ references v2's fresh development sets
(amendment 13; about 190 MB), never read before v2: PXD058626 (lung airways
and alveoli) and PXD045043 (spleen red and white pulp, hosted by jPOST).
Tier W is the 2026-10-21 search's (amendment 20; about 500 MB): PXD056050
(FACS-sorted immune populations from another lab, development), Monaco 2019's
sorted RNA (GEO GSE107011) and the Allen Human Immune Health Atlas's
dendritic-cell and other-cells files (CELLxGENE), both RNA references.

Only processed outputs (search results, matrices, label maps) are fetched, never
raw mass-spectrometry files. Tier A is the core set (about 4 GB); tier B is the
large PXD070599 search outputs for the single HeLa and HEK293T cells (about 24 GB),
which repeat what smaller sets already give for abstention; tier C is the colon's.

The servers throttle each connection (about 50 KB/s), so a file is split into
8 MiB ranges fetched on several connections at once. A download resumes where
it stopped: the partial file and its list of finished ranges stay beside the
target until the file is complete and checked. Every file's size is checked
against the server's, its published checksum (when there is one) is verified,
and its sha256 is recorded in research/benchmark/public-sets-downloads.json.

    python scripts/fetch_public_sets.py --list             # from the repository root
    python scripts/fetch_public_sets.py                    # tier A
    python scripts/fetch_public_sets.py --tier all --only PXD070599_HeLa_HEK
    python scripts/fetch_public_sets.py --tier C --only Zheng2025_PXD057118,Kabatnik2024_PXD046999
    python scripts/fetch_public_sets.py --workers 24
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "data" / "incoming" / "public_sets"
RECORD = REPO / "research" / "benchmark" / "public-sets-downloads.json"
CHUNK = 8 << 20
ROLES, TIERS = ("reference", "development", "held_out", "reserve"), ("A", "B", "C", "L", "N", "V", "W")
RAW_SUFFIXES = (".raw", ".d.zip", ".wiff", ".mzml", ".mzml.zip", ".mzml.gz")
HOSTS = ("ftp.pride.ebi.ac.uk", "zenodo.org", "massive-ftp.ucsd.edu", "www.proteinatlas.org", "ftp.jpostdb.org",
         "ftp.ncbi.nlm.nih.gov", "datasets.cellxgene.cziscience.com")
PRIDE = "https://ftp.pride.ebi.ac.uk/pride/data/archive"
MASSIVE = "ftp://massive-ftp.ucsd.edu"
ZENODO = "https://zenodo.org/api/records"


def entry(group, role, name, url, size=None, check=None, tier="A"):
    return {"group": group, "role": role, "name": name, "url": url, "bytes": size, "check": check, "tier": tier}


def pride(group, role, acc, ym, name, size=None, sha1=None, tier="A"):
    return entry(group, role, name, f"{PRIDE}/{ym}/{acc}/{name}", size, ("sha1", sha1) if sha1 else None, tier)


ENTRIES = (
    # reference: sorted bulk proteomes
    pride("Rieckmann2017_PXD004352", "reference", "PXD004352", "2017/03", "total.proteomes.single.shot.zip", 680721621,
          "1b7c40bebd7158bdeea595d657d50eff6e83b43c"),
    pride("Rieckmann2017_PXD004352", "reference", "PXD004352", "2017/03", "PXD004352_community_annotated.sdrf.tsv", 468141),
    entry("Khoury2026_bulk_sorted", "reference", "Bulk_R1_LibGen_Global.zip", f"{ZENODO}/22649483/files/Bulk_R1_LibGen_Global.zip/content",
          577290773, ("md5", "ef370a6b9ff84b72f5543b38f641495f")),
    # development: unsorted PBMC single cells (Hendriks, Olsen; labels from clustering)
    pride("PXD070599_PBMC", "development", "PXD070599", "2026/08", "DS18_DIANN.tar.gz", 673262730),
    pride("PXD070599_PBMC", "development", "PXD070599", "2026/08", "DS19_DIANN.tar.gz", 881944156),
    pride("PXD070599_PBMC", "development", "PXD070599", "2026/08", "DataSet_to_rawfile_mapping_methods.txt", 992774),
    pride("PXD070599_PBMC", "development", "PXD070599", "2026/08", "DataSet_to_figure_mapping.txt", 2867),
    # first chosen as side tests; since 2026-10-15 (research/benchmark/side-tests.md,
    # amendment 1) each is development, held out as the internal test, or in reserve
    # (PXD061065 since amendment 3)
    entry("Tian_MSV000087462", "held_out", "proteinGroupsCD3CD4CD8.xlsx",
          f"{MASSIVE}/v03/MSV000087462/search/Search%20Engine%20Files/proteinGroupsCD3CD4CD8.xlsx", 10796475),
    entry("Tian_MSV000087462", "held_out", "proteinGroupsMMsample.xlsx",
          f"{MASSIVE}/v03/MSV000087462/search/Search%20Engine%20Files/proteinGroupsMMsample.xlsx", 18004656),
    pride("PXD073250", "held_out", "PXD073250", "2026/06", "report.pg_matrix.tsv", 6073326),
    pride("PXD073250", "held_out", "PXD073250", "2026/06", "report.pr_matrix.tsv", 49988348),
    pride("PXD073250", "held_out", "PXD073250", "2026/06", "report.stats.tsv", 132629),
    pride("PXD073250", "held_out", "PXD073250", "2026/06", "report.log.txt", 877815),
    pride("PXD061065", "reserve", "PXD061065", "2025/11", "20250204_112949_gbm_sc_full_fasta_19.4_Report.tsv", 31598500),
    pride("PXD061065", "reserve", "PXD061065", "2025/11", "PXD061065_community_annotated.sdrf.tsv", 329881),
    pride("PXD061052", "development", "PXD061052", "2025/11", "20241206_144402_gbm_minibulk_full_fasta_19.4_Report.tsv", 4995983),
    pride("PXD043355", "held_out", "PXD043355", "2023/10", "HeLa_VS_Jurkat_Proteins.txt", 9757952, "76723d5ad8649d5dab3188dff89a6d0691149664"),
    pride("PXD043355", "held_out", "PXD043355", "2023/10", "HeLa_VS_Jurkat_InputFiles.txt", 11731, "1aebd5319e8de86de82677ae31de19dc1efeb9f2"),
    pride("PXD043355", "held_out", "PXD043355", "2023/10", "PXD043355_community_annotated.sdrf.tsv", 130591),
    pride("PXD077946", "development", "PXD077946", "2026/09", "diann_singlecell.zip", 16952702),
    pride("PXD020586", "development", "PXD020586", "2021/05", "SCeptre_FINAL.zip", 980777917, "bdc7daffe7ad9108adb2b2973d2cf7407dd1ec45"),
    pride("PXD020586", "development", "PXD020586", "2021/05", "PXD020586_community_annotated.sdrf.tsv", 3820932),
    pride("PXD046211", "held_out", "PXD046211", "2024/02", "quant.cbio.tsv", 293233038, "a600d1be2b7c5a65e398a52354e069871b69c2a6"),
    pride("PXD046211", "held_out", "PXD046211", "2024/02", "results.sage.cbio.tsv", 547837792, "154ebf71d66ade15413c1f0e6b90add018e18b5d"),
    pride("PXD046211", "held_out", "PXD046211", "2024/02", "sample_to_data.sdrf.tsv", 199010, "584f2e7e98fa1ceed4f0f66dc61576ff555b8f96"),
    pride("PXD046211", "held_out", "PXD046211", "2024/02", "sampleAnnotations.csv", 35750, "f55be751ecda8d36560549ae90a6b6abc31f8aa4"),
    pride("PXD046211", "held_out", "PXD046211", "2024/02", "sampleAnnotation_cbio681.csv", 2948, "b340f68f74c1a5ac6612a626d5c87bddd9086a1a"),
    pride("PXD046211", "held_out", "PXD046211", "2024/02", "sampleAnnotation_cbio703.csv", 2948, "9cff714e17062b156e2c9e981f2c68e858e99c2b"),
    pride("PXD046211", "held_out", "PXD046211", "2024/02", "sampleAnnotation_cbio715.csv", 3926, "ed7913ea58f5960a039b1877aa8dd16d82728e0e"),
    pride("PXD046211", "held_out", "PXD046211", "2024/02", "sampleAnnotation_cbio725.csv", 5899, "4a7319bd620399d32ce4f9de3e1baa4e7c500ba6"),
    pride("PXD046211", "held_out", "PXD046211", "2024/02", "sampleAnnotation_cbio733.csv", 6027, "fa5a5db488fddbabac87d7b0ed7dcd24998c7f58"),
    pride("PXD046211", "held_out", "PXD046211", "2024/02", "sampleAnnotation_cbio754bis.csv", 5963, "23775f41af6a5ec9661b42fedaf48a7c6154c5ba"),
    pride("PXD046211", "held_out", "PXD046211", "2024/02", "sampleAnnotation_GIGA.csv", 3107, "dd361d805e1100d91b96213cf991adac63c2c978"),
    entry("PXD046211", "held_out", "sample_annotation.zip", f"{ZENODO}/8417228/files/sample_annotation.zip/content", 5838,
          ("md5", "47b33c0f6e4a6b326035dfd51cf24313")),
    pride("PXD021882", "held_out", "PXD021882", "2020/12", "proteinGroups.txt", 6946011, "bfeec099e680b4036c6941088dfa04379a1ef777"),
    pride("PXD021882", "held_out", "PXD021882", "2020/12", "tables.pdf", 54650, "eff128344b41e58a253e5fbc147903a719879ec2"),
    *[entry("MSV000099294", "development", n, f"{MASSIVE}/v11/MSV000099294/quant/Spectronaut/{d}/{n}", s)
      for d, n, s in (
          ("DirectDIA_Microglia_1cell_Reports", "DirectDIA_Microglia_1cell_Protein_Quant_Pivot_Report.tsv", 1285592),
          ("DirectDIA_Microglia_1cell_Reports", "DirectDIA_Microglia_1cell_ExperimentAnalysis.txt", 1376),
          ("DirectDIA_Microglia_1cell_Reports", "DirectDIA_Microglia_1cell_IdentificationsOverview.tsv", 5052),
          ("DirectDIA_HMC3_1cell_Reports", "DirectDIA_HMC3_1cell_Protein_Quant_Pivot_Report.tsv", 2094536),
          ("DirectDIA_HMC3_1cell_Reports", "DirectDIA_HMC3_1cell_ExperimentAnalysis.txt", 1399),
          ("DirectDIA_HMC3_1cell_Reports", "DirectDIA_HMC3_1cell_IdentificationsOverview.tsv", 3802))],
    # tier B: PXD070599's single HeLa and HEK293T cells (abstention), DIA-NN outputs
    *[pride("PXD070599_HeLa_HEK", "reserve", "PXD070599", "2026/08", f"DS{n}_DIANN.tar.gz", s, tier="B")
      for n, s in ((12, 1676819567), (15, 1276924248), (14, 4290218537), (25, 4528065652), (16, 5086300411), (13, 7217998803))],
    # tier C: the colon reference's data (side-tests.md, amendment 7); Deep Visual Proteomics pools.
    # PXD052341 is the colon's locked test (research/benchmark/protocol-colon-pxd052341.md)
    pride("Post2025_PXD052341", "held_out", "PXD052341", "2025/09", "DVP_data.pg_matrix.tsv", 8222603, tier="C"),
    pride("Post2025_PXD052341", "held_out", "PXD052341", "2025/09", "Post_et_al_organoid_DVP_metadata.tsv", 71245, tier="C"),
    *[pride("Zheng2025_PXD057118", "development", "PXD057118", "2024/12", n, s, tier="C")
      for n, s in (
          ("ColorectalCancer_pg_matrix_Macrophages.txt", 755998),
          ("Colorectal_Cancer_pg_matrix_Cytotoxic_T_Cells.txt", 757197),
          ("Colorectal_Cancer_pg_matrix_Helper_T_Cells.txt", 735134),
          ("Metadata.xlsx", 10304),
          ("PXD057118_community_annotated.sdrf.tsv", 107575))],
    *[pride("Kabatnik2024_PXD046999", "development", "PXD046999", "2024/08", n, s, tier="C")
      for n, s in (
          ("C3_region1k_DIANN181_MBR_c124.pg_matrix.tsv", 953149),
          ("C_HDA_NMN-study_class1_MBR.pg_matrix.tsv", 1050746),
          ("C_HDA_NMN-study_class4_MBR.pg_matrix.tsv", 795041),
          ("CRA_revision_timstofultra_specificcohort_DIANN181_libraryfree.pg_matrix.tsv", 2222897),
          ("CAA__MBR_LibraryFree_DIANN181.pg_matrix.tsv", 1389791),
          ("Metadata_DVPonCRA_Kabatnik_et_al.csv", 4477),
          ("Metadata_DVPonCRA_Kabatnik_et_al_revision_updated.csv", 5350),
          ("PXD046999_community_annotated.sdrf.tsv", 10274))],
    # tier L: the lung reference's data (side-tests.md, amendment 9). MSV000094189 is the lung's locked test
    # (research/benchmark/protocol-lung-msv000094189.md)
    *[entry("LungMAP2025_MSV000094189", "held_out", n, f"{MASSIVE}/v07/MSV000094189/quant/MaxQuant/{n}", s, tier="L")
      for n, s in (("proteinGroups.txt", 52208897), ("Protein_metadata.csv", 26370), ("summary.txt", 25536))],
    entry("LungMAP2025_BPD_MSV000094373", "development", "combined_protein.tsv",
          f"{MASSIVE}/v07/MSV000094373/quant/MSFragger/combined_protein.tsv", 2820464, tier="L"),
    *[entry("HPA2026_DVP", "development", n, f"https://www.proteinatlas.org/download/tsv/{n}", s, tier="L")
      for n, s in (("dvp_sample_data.tsv.zip", 20083408), ("dvp_cell_types.tsv.zip", 668))],
    pride("Herrera2022_PXD029341", "development", "PXD029341", "2022/08", "results.zip", 854720055, tier="L"),
    pride("Herrera2022_PXD029341", "development", "PXD029341", "2022/08", "sdrf.tsv", 8709, tier="L"),
    # tier N: the lymph node reference's data (side-tests.md, amendment 11). PXD042367's Fig. 4 results are the
    # lymph node's locked test (research/benchmark/protocol-ln-pxd042367.md)
    pride("Coscia2023_PXD042367", "held_out", "PXD042367", "2023/11", "DIANN_results_Fig4.rar", 230205158, tier="N"),
    *[pride("Coscia2024_PXD047762", "development", "PXD047762", "2024/03", n, s, tier="N")
      for n, s in (("DIANN_Fig2A.rar", 110267046), ("DIANN_Fig2B-F.rar", 424594120), ("DIANN_Fig3.rar", 59670355),
                   ("DIANN_FigS2D-G.rar", 55821551), ("Rawfile_description.xlsx", 11823))],
    *[pride("Zheng2025_PXD057118", "development", "PXD057118", "2024/12", n, s, tier="N")
      for n, s in (("Tonsil_Cancer_pg_matrix_B_Cells.txt", 360620), ("Tonsil_Cancer_pg_matrix_Cytotoxic_T_Cells.txt", 836594),
                   ("Tonsil_Cancer_pg_matrix_Helper_T_Cells.txt", 392851), ("Tonsil_Cancer_pg_matrix_Macrophages.txt", 264718),
                   ("Tonsil_Cancer_pg_matrix_Plasma_Cells.txt", 344622), ("Tonsil_Cancer_pg_matrix_Tumor_Cells.txt", 649882))],
    pride("DusSzachniewicz2021_PXD011683", "development", "PXD011683", "2021/09", "MaxQuant_Output.zip", 1932688240, tier="N"),
    # tier V: the organ references v2's fresh development sets (side-tests.md, amendment 13), unread before v2
    *[pride("Herrera2025_PXD058626", "development", "PXD058626", "2025/06", n, s, tier="V")
      for n, s in (("combined_protein.tsv", 6813450), ("experiment_annotation.tsv", 17734),
                   ("PXD058626_community_annotated.sdrf.tsv", 5930), ("fragpipe-files.fp-manifest", 15119))],
    entry("Kitata2025_PXD045043", "development", "Report_DIA-NN_Spleen.zip",
          "ftp://ftp.jpostdb.org/JPST002191/Report_DIA-NN_Spleen.zip", 185986731, tier="V"),
    # tier W: the 2026-10-21 search (side-tests.md, amendment 20; research/reference-data-search.md)
    *[pride("Zamore2025_PXD056050", "development", "PXD056050", "2025/07", n, s, tier="W")
      for n, s in (("DIA-NN_immune_cells.zip", 77701779), ("PXD056050_community_annotated.sdrf.tsv", 21321))],
    entry("Monaco2019_GSE107011", "reference", "GSE107011_Processed_data_TPM.txt.gz",
          "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE107nnn/GSE107011/suppl/GSE107011_Processed_data_TPM.txt.gz",
          15420393, tier="W"),
    # the Allen atlas's dendritic cells (CELLxGENE dataset dade16db-a38b-41f5-95c8-7ec0238d17fc) and other cells
    # (81ffdcd6-3f04-40bc-8bb0-9748f4ffe576), in collection 77f9d7e9-5675-49c3-abed-ce02f39eef1b
    *[entry("Gong2025_HIHA", "reference", n, f"https://datasets.cellxgene.cziscience.com/{n}", s, tier="W")
      for n, s in (("4f925e42-3e42-4e2d-8394-4e88bf9a0ff2.h5ad", 347259294),
                   ("70dd5115-cec8-49ad-a2fb-f985067b193f.h5ad", 59053452))],
)
# The two supplementary files of PXD073250's paper (Life Science Alliance, PMC13315484) have no stable direct
# link; they were saved by hand into data/incoming/public_sets/PXD073250/ and are recorded by --record-manual.
MANUAL = {"PXD073250": ("LSA-2026-03759_Supplemental_Data_1.xlsx", "LSA-2026-03759_Supplemental_Data_2.zip")}


# ---- the download ----

def digest(path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(4 << 20), b""):
            h.update(block)
    return h.hexdigest()


def remote_size(url: str) -> int:
    """The file's size, from a one-byte range request (HEAD is unreliable on these hosts)."""
    req = urllib.request.Request(url, headers={"Range": "bytes=0-0", "User-Agent": "vivome-fetch/1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        crange = r.headers.get("Content-Range", "")
        if "/" in crange:
            return int(crange.rsplit("/", 1)[1])
        return int(r.headers.get("Content-Length", "0"))


def fetch_range(url: str, start: int, end: int, tries: int = 6) -> bytes:
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}", "User-Agent": "vivome-fetch/1"})
            with urllib.request.urlopen(req, timeout=120) as r:
                if r.status != 206:
                    raise OSError(f"HTTP {r.status}: the server ignored the range")
                data = r.read()
            if len(data) != end - start + 1:
                raise OSError(f"short read: {len(data)} of {end - start + 1} bytes")
            return data
        except (OSError, urllib.error.URLError, http.client.HTTPException) as exc:  # IncompleteRead is an HTTPException
            last = exc
            time.sleep(min(2 ** attempt, 30))
    raise OSError(f"{url} bytes {start}-{end}: {last}")


def download_http(url: str, dest: Path, size: int, workers: int, chunk: int) -> None:
    part, state_path = dest.with_name(dest.name + ".part"), dest.with_name(dest.name + ".part.json")
    n = -(-size // chunk)
    done: set[int] = set()
    if part.exists() and state_path.exists():
        saved = json.loads(state_path.read_text())
        if saved.get("size") == size and saved.get("chunk") == chunk:
            done = set(saved["done"])
    if not part.exists() or not done:
        with part.open("wb") as fh:
            fh.truncate(size)
        done = set()
    lock, started, got = threading.Lock(), time.time(), [sum(min(chunk, size - i * chunk) for i in done)]
    base = got[0]

    def one(i: int) -> None:
        start = i * chunk
        data = fetch_range(url, start, min(start + chunk, size) - 1)
        with lock:
            with part.open("r+b") as fh:
                fh.seek(start)
                fh.write(data)
            done.add(i)
            got[0] += len(data)
            state_path.write_text(json.dumps({"size": size, "chunk": chunk, "done": sorted(done)}), newline="\n")

    todo = [i for i in range(n) if i not in done]
    if todo:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(one, i) for i in todo]
            for k, f in enumerate(futures):
                f.result()
                if size > 64 << 20 and (k % workers == 0 or k == len(futures) - 1):
                    rate = (got[0] - base) / max(time.time() - started, 1e-9) / 1e6
                    print(f"    {got[0] / 1e6:9.1f} / {size / 1e6:.1f} MB ({rate:.2f} MB/s)", flush=True)
    part.replace(dest)
    state_path.unlink(missing_ok=True)


def download_ftps(url: str, dest: Path, size: int | None) -> None:
    """MassIVE's FTP needs TLS (jPOST's takes plain FTP); curl resumes with -C -."""
    part = dest.with_name(dest.name + ".part")
    tls = ["--ssl-reqd"] if "massive-ftp" in url else []
    subprocess.run(["curl", "-s", *tls, "--retry", "5", "-C", "-", "-o", str(part), url], check=True)
    if size is not None and part.stat().st_size != size:
        raise OSError(f"{url}: {part.stat().st_size} bytes, expected {size}")
    part.replace(dest)


def fetch(item: dict, workers: int = 16, chunk: int = CHUNK, root: Path = ROOT) -> dict:
    """Downloads one entry (skipping a complete file), verifies it, returns its record."""
    dest = root / item["group"] / item["name"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    expected = item["bytes"]
    if not dest.exists():
        if item["url"].startswith("ftp://"):
            download_ftps(item["url"], dest, expected)
        else:
            size = remote_size(item["url"])
            if expected is not None and size != expected:
                raise OSError(f"{item['name']}: the server says {size} bytes, the table {expected}")
            download_http(item["url"], dest, size, workers, chunk)
    if expected is not None and dest.stat().st_size != expected:
        raise OSError(f"{dest}: {dest.stat().st_size} bytes, expected {expected}")
    if item["check"]:
        algorithm, want = item["check"]
        if digest(dest, algorithm) != want:
            raise OSError(f"{dest}: {algorithm} does not match the published {want}")
    return {"role": item["role"], "tier": item["tier"], "url": item["url"], "bytes": dest.stat().st_size,
            "sha256": digest(dest, "sha256"), "published_check": item["check"] and item["check"][0], "fetched": str(date.today())}


def load_record(path: Path = RECORD) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() and path.read_text().strip() else {}


def save_record(record: dict, path: Path = RECORD) -> None:
    path.write_bytes((json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", choices=(*TIERS, "all"), default="A")
    parser.add_argument("--only", help="comma-separated groups")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--list", action="store_true", help="list the entries and what is on disk; fetch nothing")
    parser.add_argument("--record-manual", action="store_true", help="record the hand-saved files (checksums only)")
    args = parser.parse_args()
    items = [e for e in ENTRIES if args.tier in ("all", e["tier"]) and (not args.only or e["group"] in args.only.split(","))]
    record = load_record()
    if args.record_manual:
        for group, names in MANUAL.items():
            for name in names:
                path = ROOT / group / name
                if path.exists():
                    record[f"{group}/{name}"] = {"role": "held_out", "tier": "A", "url": "saved by hand from the paper's supplementary files (PMC13315484)",
                                                 "bytes": path.stat().st_size, "sha256": digest(path, "sha256"), "published_check": None,
                                                 "fetched": str(date.today())}
                else:
                    print(f"missing: {path}")
        save_record(record)
        return 0
    if args.list:
        total = 0
        for e in sorted(items, key=lambda x: x["bytes"] or 0):
            have = (ROOT / e["group"] / e["name"]).exists()
            total += 0 if have else (e["bytes"] or 0)
            print(f"{'have' if have else 'todo':4}  {e['tier']}  {e['role']:11}  {(e['bytes'] or 0) / 1e6:10.1f} MB  {e['group']}/{e['name']}")
        print(f"to fetch: {total / 1e9:.2f} GB")
        return 0
    failures = 0
    for e in sorted(items, key=lambda x: x["bytes"] or 0):  # small files first, one large file at a time
        key = f"{e['group']}/{e['name']}"
        print(f"{key} ({(e['bytes'] or 0) / 1e6:.1f} MB)", flush=True)
        try:
            record[key] = fetch(e, args.workers)
            save_record(record)
        except (OSError, subprocess.CalledProcessError, urllib.error.URLError, http.client.HTTPException) as exc:
            failures += 1
            print(f"  FAILED: {exc}", file=sys.stderr, flush=True)
    print(f"done: {len(items) - failures} of {len(items)} files")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
