
# LyriPop_Pipeline

# Author: Zhang Feixue 240651956

**An interpretable, rights‑respecting pipeline to analyse lyrical simplicity in Billboard Year‑End Hot‑100 Top‑5 (1958–2024), with a lawful mid‑chart benchmark (ranks 6–100, 1991–2011) via MSD×musiXmatch bag‑of‑words.**

---

## 1) Features

- **Transparent indicators**: Type–Token Ratio (TTR), Shannon Entropy (H, H_norm), Herfindahl–Hirschman Index (HHI, HHI_norm), dominant‑token share (max_p).  
- **Legality‑first**: no redistribution of full lyrics; Top‑5 stats derived from curated transcriptions; 6–100 uses lawful BoW counts from MSD×MXM.  
- **Reproducible scripts**: from ingestion to cleaning, metrics, yearly aggregation, plotting and Hot‑100 comparison.  
- **Small, clear codebase**: designed for teaching/assessment; easy to audit.

---

## 2) Repository layout

```
LyriPop_Pipeline/
├─ src/lyripop/
│  ├─ __init__.py
│  ├─ pipeline.py          # CLI entry: compute metrics / run pipeline steps
│  ├─ utils.py             # cleaning helpers, IO
│  ├─ metrics.py           # per-song metrics + yearly aggregation
│  └─ textprep.py          # clean_tokens() (optional: tokenisation logic)
├─ scripts/
│  ├─ fill_lyrics_from_bimmuda.py     # align Top‑5 with BiMMuDa lyric files
│  ├─ merge_manual_stubs.py           # merge manual Top‑5 missing *.txt into dataset
│  ├─ scrape_yearend_wiki.py          # fallback: scrape Year‑End lists from Wikipedia
│  ├─ mxm_hot100_compare.py           # Hot‑100 (6–100) BoW metrics (1991–2011)
│  ├─ bow_vs_top5_compare.py          # Compare 6–100 vs Top‑5 (plots + CSV)
│  └─ make_instance_story_metrics.py  # (optional) compute metrics for selected examples
├─ data_out/               # outputs: CSVs, figures
├─ data_mxm/               # put MXM files here (see §4)
├─ manual_top5_missing/    # optional: manual Top‑5 lyric stubs (.txt)
├─ .env                    # optional: tokens (not required by default)
└─ README.md
```

---

## 3) Environment & installation

### Option A — Conda (recommended)
```bash
conda create -n lyripop python=3.11 -y
conda activate lyripop
conda install -c conda-forge pandas numpy matplotlib statsmodels beautifulsoup4 lxml html5lib python-dotenv tqdm -y
# Optional (only if you experiment with Genius API; not needed for this pipeline):
pip install lyricsgenius==3.0.1
```

### Option B — pip (virtualenv)
```bash
python -m venv .venv && source .venv/bin/activate  # on macOS/Linux
pip install -U pandas numpy matplotlib statsmodels beautifulsoup4 lxml html5lib python-dotenv tqdm
```

Make sure the package path is visible when you run scripts:
```bash
export PYTHONPATH=src
```

---

## 4) Data inputs

### (A) Year‑End Hot‑100 lists (1958–2024)
- Preferred: place a CSV at `data_out/yearend_hot100_1958_2024.csv` with columns at least:
  `year,rank,title,artist`
- Fallback (if you don’t have the CSV): use the Wikimedia scraper:
  ```bash
  export PYTHONPATH=src
  python scripts/scrape_yearend_wiki.py
  # Requires: beautifulsoup4, lxml, html5lib
  # Output: data_out/yearend_hot100_1958_2024.csv
  ```

### (B) Top‑5 lyric alignment (1958–2024)
- If you have **BiMMuDa** locally, run:
  ```bash
  python scripts/fill_lyrics_from_bimmuda.py \
    --charts_csv data_out/yearend_hot100_1958_2024.csv \
    --bimmuda_root /path/to/BiMMuDa \
    --out_csv data_out/yearend_hot100_lyrics_1958_2024.csv \
    --threshold 60   # fuzzy match threshold (60–85 typical)
  ```
- If some Top‑5 songs remain missing, create short stubs in `manual_top5_missing/` using the naming convention:
  ```
  YYYY _ Artist _ Title.txt     # underscores separate fields; avoid slashes/quotes
  # example: 2012 _ Carly Rae Jepsen _ Call Me Maybe.txt
  ```
  Then merge:
  ```bash
  python scripts/merge_manual_stubs.py \
    --lyrics_csv data_out/yearend_hot100_lyrics_1958_2024.csv \
    --stubs_dir manual_top5_missing \
    --threshold 78
  ```

> **Copyright**: do not commit full lyrics to the repo. Stubs are for local metric computation only.

### (C) Hot‑100 (ranks 6–100) BoW (1991–2011)
Download three files into `data_mxm/`:
```
data_mxm/
├─ mxm_779k_matches.txt        # MSD track matching
├─ mxm_dataset_train.txt       # stemmed BoW (train)
└─ mxm_dataset_test.txt        # stemmed BoW (test)
```

---

## 5) Quickstart

### 5.1 Compute Top‑5 metrics (1958–2024)
```bash
export PYTHONPATH=src
python -m lyripop.pipeline --compute --start 1958 --end 2024
# writes: data_out/top5_metrics.csv (+ splits by year if configured)
```

### 5.2 Compute Hot‑100 (6–100) BoW metrics (1991–2011)
```bash
python scripts/mxm_hot100_compare.py \
  --yearend_csv data_out/yearend_hot100_1958_2024.csv \
  --mxm_matches data_mxm/mxm_779k_matches.txt \
  --mxm_dataset data_mxm/mxm_dataset_train.txt \
  --mxm_dataset2 data_mxm/mxm_dataset_test.txt \
  --out_csv data_out/hot100_bow_1991_2011.csv \
  --start 1991 --end 2011 \
  --threshold 76
```

### 5.3 Compare 6–100 vs Top‑5 (1991–2011)
```bash
python scripts/bow_vs_top5_compare.py \
  --hot100_bow_csv data_out/hot100_bow_1991_2011.csv \
  --top5_metrics_csv data_out/top5_metrics.csv \
  --out_prefix data_out/bow_vs_top5_1991_2011 \
  --min_n_per_year 20 \
  --start 1991 --end 2011
# outputs: PNG plots + OLS CSVs under data_out/bow_vs_top5_1991_2011_*.{png,csv}
```

### 5.4 Optional: “Instance stories” (micro‑hooks table)
Prepare a small list of songs and generate per‑song metrics:
```bash
python scripts/make_instance_story_metrics.py
# outputs: data_out/instance_stories_metrics.csv
# Combine with your instance_stories.png for slide/figure use.
```

---

## 6) Outputs (typical)

- `data_out/top5_metrics.csv` — yearly Top‑5 averages (TTR, H, H_norm, HHI, HHI_norm, max_p).  
- `data_out/yearend_hot100_lyrics_1958_2024.csv` — Top‑5 aligned rows with `lyrics_clean` (no redistribution).  
- `data_out/hot100_bow_1991_2011.csv` — ranks 6–100 BoW metrics by year.  
- `data_out/bow_vs_top5_1991_2011_*.png` — comparison plots.  
- `data_out/top5_*_1958_2024.png` — Top‑5 trends (TTR / Entropy / HHI / max_p).  
- `data_out/instance_stories_metrics.csv` + `instance_stories.png` — case examples for presentation.

---

## 7) Troubleshooting

- **403 / scraping blocked**: This repo is designed to avoid scraping lyrics. Use curated sources + BiMMuDa for Top‑5 and MSD×MXM for 6–100.  
- **`ModuleNotFoundError: matplotlib`**: install `matplotlib` in the active env.  
- **`html5lib` warning when scraping**: `conda install -c conda-forge html5lib` (only needed by `scrape_yearend_wiki.py`).  
- **`PYTHONPATH` not set**: `export PYTHONPATH=src` before running `python -m lyripop...`.  
- **Manual stub filenames**: use `YYYY _ Artist _ Title.txt`
- **Low match rate in MXM**: adjust `--threshold` (60–80), and check Year‑End CSV artist/title normalisation.

---

## 8) Legal & Ethics

- Do **not** redistribute full lyrics in this repository.  
- Top‑5 analysis uses **derived statistics**; figures may include ultra‑short “micro‑hooks” strictly under fair‑quotation norms.  
- Hot‑100 6–100 uses **MSD×MXM** stemmed word counts that are publicly available for research use.  
- All scripts are for research/teaching. Please respect rights holders’ terms for any additional sources you use locally.

---

## 9) How to cite

If you use this pipeline or its figures in academic work, please cite:

- Bertin‑Mahieux, T., Ellis, D.P.W., Whitman, B., Lamere, P. (2011). *The Million Song Dataset*. Proceedings of ISMIR.  
- The musiXmatch / MSD lyrics bag‑of‑words (see the MSD website for the standard citation).  
- This repository: **LyriPop_Pipeline** (version & date).

Example (Harvard style):

> Bertin‑Mahieux, T., Ellis, D.P.W., Whitman, B. and Lamere, P. (2011) The Million Song Dataset. In: Proceedings of the 12th International Society for Music Information Retrieval Conference (ISMIR).

---

## 10) Maintainers & reproducibility notes

- Python 3.11; main libs: `pandas`, `numpy`, `matplotlib`, `statsmodels`, `beautifulsoup4/lxml/html5lib` (scraper only), `python-dotenv`, `tqdm`.  
- Randomness: none required for the core indicators.  
- We recommend exporting your exact package versions with `pip freeze` or `conda env export` alongside your submission.

---

Date: 2025-07-12
