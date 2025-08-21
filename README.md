# LyriPop Pipeline v2

**What it does:** builds a large **Billboard Year‑End Hot 100** lyric corpus (1980–2024 by default), fetches lyrics via Genius, and computes transparent metrics (VADER, FK, TTR, repetition ratio, gzip‑compressibility). It labels **Top‑5** vs **others** for direct comparison.

## macOS + Anaconda
```bash
conda env create -f environment.yml
conda activate lyripop
cp .env.sample .env
# open .env and paste GENIUS_ACCESS_TOKEN
python -m lyripop.pipeline --fetch_charts --start 1980 --end 2024
python -m lyripop.pipeline --fetch_lyrics --start 1980 --end 2024
python -m lyripop.pipeline --compute      --start 1980 --end 2024
```

## Notes
- Uses `billboard.py` first; if it fails, falls back to scraping Year‑End pages (HTML saved under `data_out/_html/` for debugging).
- Lyrics are cached in `data_out/lyrics_cache/` to avoid duplicate API calls.
- All metrics are simple and reproducible—ideal to address "opaque simplicity metrics" concerns.

Date: 2025-07-12
