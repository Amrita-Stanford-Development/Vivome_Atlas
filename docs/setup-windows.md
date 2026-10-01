# Setting up on Windows

How to set up this repository on the Windows workstation with an NVIDIA GPU
(an RTX 4000 Ada) that does all development since October 2026. For the
state of the work and what to do next, read
[research/working-context.md](../research/working-context.md) after setup.

Each command block names the shell it runs in:

- **PowerShell**, built into Windows;
- **Git Bash**, installed with Git for Windows;
- **Miniforge Prompt**, installed with Miniforge.

The layout used throughout:

```
D:\Project\Vivome\Vivome_Atlas\   the repository
D:\Project\Vivome\notebooks\      the Colab notebooks
D:\Project\Vivome\drive\Data\     the project Drive's Data\ folder (Results\, scProteomics\)
```

No code depends on this location; another drive or folder works the same.

## 1. Install the tools (once)

- **Git for Windows** (winget `Git.Git`). It includes Git Bash, Git LFS and
  the credential manager. When the installer asks about line endings, choose
  **"Checkout as-is, commit as-is"**.
- **Miniforge** (winget `CondaForge.Miniforge3`), installed to
  `%USERPROFILE%\miniforge3`.
- **Node.js LTS** (winget `OpenJS.NodeJS.LTS`), for the web tests.
- **R for Windows** (winget `RProject.R`), only to rerun the Seurat baseline.
  In R, run `install.packages("Seurat")`; the finished runs used Seurat 5.5.1.
  Then add R's `bin` folder (for example `C:\Program Files\R\R-4.5.1\bin`)
  to the user `PATH`, so `Rscript` runs from Git Bash.
- **Long paths.** In PowerShell **run as administrator**:
  ```powershell
  New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force
  ```

## 2. Clone (Git Bash)

```bash
git config --global user.name "Amarnath K R"
git config --global user.email "aiamrita.stanford@gmail.com"
git config --global credential.https://github.com.username AiAmrita
git config --global core.autocrlf false
git config --global core.longpaths true
git lfs install
mkdir -p /d/Project/Vivome && cd /d/Project/Vivome
git clone https://github.com/Amrita-Stanford-Development/Vivome_Atlas.git
cd Vivome_Atlas && git checkout integration/v31
git lfs pull                                                                 # about 3.5 GB
```

Later updates, from the repository: `git pull && git lfs pull`.

**Push access.** The repository belongs to the personal account
Amrita-Stanford-Development and is public, so anyone can clone it, but only
the owner and collaborators can push. To push as AiAmrita:

1. Signed in to GitHub as **Amrita-Stanford-Development**, open the
   repository's Settings → Collaborators
   (github.com/Amrita-Stanford-Development/Vivome_Atlas/settings/access),
   choose **Add people** and invite **AiAmrita**.
2. Signed in as **AiAmrita**, accept the invitation from the email or from
   github.com/Amrita-Stanford-Development/Vivome_Atlas/invitations.
3. In the repository, run `git push --dry-run`. The first time, Git
   Credential Manager opens the browser to sign in; choose AiAmrita.
   "Everything up-to-date" means push access works; a 403 error means the
   invitation hasn't been accepted yet.

**Line endings.** `core.autocrlf false` leaves files as they are on disk;
`.gitattributes` does the rest:

- text is stored with LF (`* text=auto eol=lf`), so outputs that Python and
  pandas write with CRLF on Windows don't show as whole-file changes;
- the sha256-checked model files stay byte-exact (`-text`);
- shell and R scripts keep LF, so they run under Git Bash and Rscript.

## 3. The files git does not carry

`benchmark/results/` and `data/incoming/` are gitignored, and some of their
contents took hours of compute. Two zips on the project Google Drive hold
every local-only file:

| Zip | Holds | sha256 |
|---|---|---|
| `vivome_transfer.zip` (2.2 GB) | `benchmark/results/` (every finished run), `data/incoming/` (all notebook deliveries, Fulcher 2026, Khoury 2026), the Claude Code memory files | `9f4cfd38b0cf0fab9ab77a08cab4b05d3d94cb656a07895aa4c6a67034e1a996` |
| `vivome_transfer_extras.zip` (556 MB) | Seurat's input matrices, the smoke tests, partial score tables | `96f137dd1730f5c2d1899c60bccc3e764f3919a0e2fe94bf7a2555b1f44ed6e8` |

**Check each download before unzipping it.** A sha256 is a fingerprint of
the file's bytes: if the one PowerShell prints matches the table (it prints
upper case, which doesn't matter), the file arrived intact. If it doesn't,
download that file again.

PowerShell, with both zips in `Downloads`:

```powershell
Get-FileHash $HOME\Downloads\vivome_transfer.zip
Get-FileHash $HOME\Downloads\vivome_transfer_extras.zip
tar -xf $HOME\Downloads\vivome_transfer.zip -C D:\Project\Vivome\Vivome_Atlas
tar -xf $HOME\Downloads\vivome_transfer_extras.zip -C D:\Project\Vivome\Vivome_Atlas
```

Unzip them in that order, and use PowerShell's `tar`, not Explorer's
"Extract All", which adds a folder level (Git Bash's `tar` cannot read zips).
Then copy Seurat's inputs, identical for every seed, to seeds 1 and 2
(PowerShell, in the repository):

```powershell
foreach ($d in 'scope2','pbmc240','fulcher2026') { foreach ($s in 1,2) {
  New-Item -ItemType Directory -Force "benchmark\results\baselines_ext\$d\seurat_seed${s}_work" | Out-Null
  Copy-Item "benchmark\results\baselines_ext\$d\seurat_seed0_work\*.f32" `
            "benchmark\results\baselines_ext\$d\seurat_seed${s}_work\" } }
```

Notes on the zips' contents:

- Ignore `_transfer\README_TRANSFER.txt`; follow this page instead.
- `lane.sh` and `retry.sh` in `benchmark/results/baselines_ext/` are
  superseded. Use `benchmark/baselines_queue.sh`.
- `research/benchmark/baselines/` arrives with partial tables from a test of
  the scorer. The full scoring run overwrites them; don't commit them as
  they are.
- Khoury 2026 in `data/incoming/` is **sealed**: nothing embeds or scores it
  before the final v3.1 evaluation
  ([protocol](../research/benchmark/protocol-khoury2026.md)).

## 4. Python environment (Miniforge Prompt)

```bat
conda create -n vivome python=3.11 -y
conda activate vivome
cd D:\Project\Vivome\Vivome_Atlas
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -r service\requirements.txt openpyxl
pip install scvi-tools==1.4.2 scanpy==1.11.5 anndata==0.12.19 maxfuse matplotlib seaborn dill tqdm statsmodels parse networkx pynvml pytorch-ignite pyro-ppl tensorboardX h5py sparse packaging leidenalg muon
pip install --no-deps scglue==0.4.0
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
conda init bash
```

The CUDA check should print `True NVIDIA RTX 4000 Ada Generation`.
`conda init bash` lets Git Bash, and so Claude Code, use the environment. If
pip fails on `faiss-cpu`, run `conda install -c conda-forge faiss-cpu`.

Two packages have no Windows build:

- **pybedtools** (and its dependency pysam), which scglue requires. scglue
  imports it only for `scglue.genomics`, the genomic-interval guidance
  graphs; the benchmark's scGLUE runs use one self-loop per gene and never
  call it. So scglue is installed with `--no-deps` (its other dependencies
  are in the line before), plus a stand-in `pybedtools` package in the
  environment's `Lib\site-packages\pybedtools\` whose functions raise if
  ever called: `__init__.py` defines `BedTool` and `cleanup`,
  `cbedtools.py` defines `Interval`, `helpers.py` defines
  `set_bedtools_path`. Check with `python -c "import scglue"`.
- **harmonypy 2.0.2** compiles a C++ extension, which needs Visual Studio
  Build Tools (workload "Desktop development with C++"); conda-forge has no
  2.x build. Only the Harmony baseline uses it, and its runs are finished.
  To rerun them, install the Build Tools, then
  `pip install harmonypy==2.0.2`.

## 5. Restore and verify (Miniforge Prompt, in the repository)

```bat
python scripts\fetch_v31_members.py
python -m benchmark.datasets
python -m unittest discover -s scripts
python -m unittest discover -s service/tests -t .
node --test
python -m benchmark.v31_dev_gate
```

- `fetch_v31_members.py` copies the five v3.1 checkpoints from
  `data/incoming/NB1b/ckpt/` into `service/model/v3_1/members/` and checks
  each sha256. It must print "copied" or "in place" for all five.
- `benchmark.datasets` checks the Fulcher and Khoury files' sha256.
- `node --test` has 2 expected failures in `web/tests/lfs.test.js` after
  `git lfs pull`. Don't change that test.
- The dev gate must end with `GATE PASSED`.
- On this PC, 6 service tests fail by about 5e-7, against a tolerance of
  1e-6: `test_pipeline_versions` (v3 coordinates frozen on the Mac) and
  `test_ensemble.FullPathAgainstNb2CoreTests`. That is float32 summation
  order in the CPU math library, not a code change. Don't loosen the
  tolerance or refreeze the fixtures without the owner's decision.

A test may fail for a Windows-only reason, such as a path separator. Fix the
code, not the test.

## 6. Claude Code

1. In PowerShell: `irm https://claude.ai/install.ps1 | iex`. It uses Git Bash.
2. The project's memory folder is
   `%USERPROFILE%\.claude\projects\<repository path with - for \ : _>\memory\`,
   for this layout `D--Project-Vivome-Vivome-Atlas\memory\`. Copy
   `_transfer\claude_memory\*` into it.
3. Delete `_transfer\`.
4. Start the first session in the repository with: "Read CLAUDE.md and
   research/working-context.md, then continue."

## 7. Colab notebooks and Drive data

- **Download** with Google Drive for desktop, or directly:
  - `Colab Notebooks/` to `D:\Project\Vivome\notebooks\`;
  - `Data/` to `D:\Project\Vivome\drive\Data\`, including
    `Data/Results/Tier1_v31/` and the RNA `.h5ad` if you will rerun
    notebooks. A Drive folder download arrives as several zips; extract them
    all into the same folder with PowerShell's `tar -xf`.
- **Keep them outside the repository.** Bringing notebooks into git (outputs
  stripped, a folder chosen in [project-structure.md](project-structure.md),
  file-index lines) is a separate task.
- **To run a notebook locally:**
  1. `pip install jupyterlab` in the `vivome` environment.
  2. Replace `/content/drive/MyDrive/...` paths with
     `D:/Project/Vivome/drive/...`.
  3. Drop the `google.colab` mount cell.

## 8. Long runs

- **Keep the PC awake.** Settings → System → Power → Sleep: **Never** while
  runs go.
- **One heavy job at a time.** Baselines load the full 85,232-cell reference;
  parallel runs caused a memory spike before.
- **Run long queues in your own Git Bash window**, not as a Claude Code
  background task, which stops after 2 hours or when the session ends:
  ```bash
  conda activate vivome && cd /d/Project/Vivome/Vivome_Atlas
  benchmark/baselines_queue.sh maxfuse scglue
  ```
  The queue skips runs that already have their `.json` record, so rerunning
  the same command resumes it. Progress is in
  `benchmark/results/baselines_ext/logs/queue.txt`.
