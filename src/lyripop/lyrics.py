import os, time, json, random
from pathlib import Path
from typing import Tuple, List, Dict

import requests
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from rapidfuzz import fuzz
from tqdm import tqdm

from .utils import safe_filename, normalise_artist, normalise_title

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HDRS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
}

def _get_token() -> str:
    # 显式从工程根目录加载 .env
    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(dotenv_path=project_root / ".env")
    tok = os.getenv("GENIUS_ACCESS_TOKEN", "").strip()
    if not tok:
        raise RuntimeError("Missing GENIUS_ACCESS_TOKEN (check .env or export it in shell)")
    return tok

def _official_api_search(token: str, query: str, per_page: int = 5) -> List[Dict]:
    # 用官方 API（需要 Bearer token），避免被 public/multi 403
    url = "https://api.genius.com/search"
    params = {"q": query, "per_page": per_page}
    headers = {"Authorization": f"Bearer {token}", "User-Agent": UA}
    r = requests.get(url, params=params, headers=headers, timeout=25)
    if r.status_code == 401:
        raise RuntimeError("Genius API 401 Unauthorized: check your token.")
    if r.status_code == 403:
        raise RuntimeError("Genius API 403 Forbidden: access blocked by Genius. Try later or different network.")
    r.raise_for_status()
    data = r.json()
    hits = data.get("response", {}).get("hits", [])
    return hits

def _scrape_lyrics_from_url(url: str) -> str:
    if not url:
        return ""
    # 解析歌词页面里的 data-lyrics-container 区块
    r = requests.get(url, headers=HDRS, timeout=25)
    if r.status_code == 403:
        return ""
    if r.status_code >= 400:
        return ""
    soup = BeautifulSoup(r.text, "html.parser")
    blocks = soup.select('div[data-lyrics-container="true"]')
    if not blocks:
        blk = soup.find("div", class_="Lyrics__Root")
        blocks = [blk] if blk else []
    lines = []
    for b in blocks:
        for br in b.find_all(['br']):
            br.replace_with("\n")
        text = b.get_text(separator="\n", strip=True)
        if text:
            lines.append(text)
    lyr = "\n".join(lines).strip()
    return lyr

def fetch_lyric_for_row(_unused, title: str, artist: str) -> Tuple[str, str]:
    # 用 官方API 搜索 → 选最佳候选 → 抓取歌词 HTML
    token = _get_token()
    q_title = normalise_title(title)
    q_artist = normalise_artist(artist)
    query = f"{q_title} {q_artist}".strip()

    try:
        hits = _official_api_search(token, query, per_page=5)
    except Exception:
        return "", ""

    best = None; best_sc = -1
    for h in hits:
        res = h.get("result", {})
        cand = f"{res.get('title','')} {res.get('primary_artist',{}).get('name','')}"
        sc = fuzz.token_set_ratio(query, cand)
        if sc > best_sc:
            best_sc, best = sc, res

    if not best:
        return "", ""

    url = best.get("url", "")
    lyr = _scrape_lyrics_from_url(url)
    time.sleep(0.3 + random.random()*0.4)  # 轻微延时，降低被拦截概率
    return (lyr or ""), (url or "")

def fetch_lyrics_for_chart(df: pd.DataFrame, cache_dir: Path) -> pd.DataFrame:
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for _, r in tqdm(
        df.iterrows(), total=len(df),
        desc=f"Fetching lyrics {int(df['year'].min())}-{int(df['year'].max())}"
    ):
        title, artist = r["title"], r["artist"]
        cache_name = safe_filename(f"{r['year']}_{r['rank']}_{title}_{artist}.json")
        cache_path = cache_dir / cache_name
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                raw, url = data.get("lyrics",""), data.get("url","")
            except Exception:
                raw, url = "", ""
        else:
            raw, url = fetch_lyric_for_row(None, title, artist)
            data = {"year": int(r["year"]), "rank": int(r["rank"]), "title": title, "artist": artist,
                    "lyrics": raw, "url": url}
            cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        out.append({**r.to_dict(), "lyrics_raw": raw, "lyrics_url": url})
    return pd.DataFrame(out)
