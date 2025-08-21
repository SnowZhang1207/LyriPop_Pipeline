import pandas as pd
import requests, re
from bs4 import BeautifulSoup
import billboard
from pathlib import Path

HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_year_end_hot100_billboardpy(year: int) -> pd.DataFrame:
    chart = billboard.ChartData("hot-100-songs", year=str(year))
    rows = [{
        "year": year,
        "rank": int(e.rank),
        "title": e.title,
        "artist": e.artist,
        "peakPos": getattr(e, "peakPos", None),
        "weeks": getattr(e, "weeks", None),
        "image": getattr(e, "image", None),
    } for e in chart]
    return pd.DataFrame(rows)

def fetch_year_end_hot100_scrape(year: int, save_html: Path=None) -> pd.DataFrame:
    url = f"https://www.billboard.com/charts/year-end/{year}/hot-100-songs/"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    html = r.text
    if save_html: save_html.write_text(html, encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    items = soup.select(".o-chart-results-list__item") or soup.select("ul.o-chart-results-list li")
    if not items:
        items = soup.find_all("li")
    rank = 0
    for it in items:
        title = None; artist = None
        t = it.select_one("h3.c-title") or it.select_one("h3")
        if t: title = t.get_text(strip=True)
        a = it.select_one("span.c-label.a-no-trucate") or it.select_one("span.c-label")
        if a: artist = a.get_text(strip=True)
        rk = it.get("data-rank")
        if rk and str(rk).isdigit():
            rank = int(rk)
        else:
            if title: rank += 1
        if title and artist and 1 <= rank <= 100:
            rows.append({"year": year, "rank": rank, "title": title, "artist": artist})
    df = pd.DataFrame(rows).drop_duplicates(subset=["year","rank"]).sort_values("rank")
    return df

def fetch_year_end_hot100(year: int, fallback_dir: Path=None) -> pd.DataFrame:
    try:
        df = fetch_year_end_hot100_billboardpy(year)
        if len(df) >= 95:
            return df
    except Exception:
        pass
    save_html = None
    if fallback_dir:
        fallback_dir.mkdir(parents=True, exist_ok=True)
        save_html = fallback_dir / f"billboard_yearend_{year}.html"
    return fetch_year_end_hot100_scrape(year, save_html=save_html)
