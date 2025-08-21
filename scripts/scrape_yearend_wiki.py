import time, re, requests
from io import StringIO
from pathlib import Path
import pandas as pd

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

def clean_title(s: str) -> str:
    s = str(s).strip()
    # 去掉两端引号（直/弯/单引号）
    return s.strip('"“”\'‘’')

def pick_year_table(tables):
    """从多个表里挑含标题+艺人列的那张表"""
    keysets = [
        ("title", "artist"),
        ("single", "artist"),
        ("title", "artist(s)"),
        ("single", "artist(s)"),
    ]
    for t in tables:
        cols = [str(c).strip().lower() for c in t.columns]
        for k1, k2 in keysets:
            if any(k1 in c for c in cols) and any(k2 in c for c in cols):
                return t
    return None

def parse_year(year: int) -> pd.DataFrame:
    url = f"https://en.wikipedia.org/wiki/Billboard_Year-End_Hot_100_singles_of_{year}"
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    tables = pd.read_html(StringIO(r.text))  # 走 lxml 解析
    tbl = pick_year_table(tables)
    if tbl is None:
        raise RuntimeError(f"No suitable table for {year}")

    # 统一列名
    tbl.columns = [str(c).strip().lower() for c in tbl.columns]

    # rank 列
    rank_col = None
    for cand in ("no.", "no", "position", "rank"):
        if cand in tbl.columns:
            rank_col = cand
            break
    if rank_col:
        tbl["rank"] = pd.to_numeric(tbl[rank_col], errors="coerce")
    else:
        tbl["rank"] = range(1, len(tbl)+1)

    # 标题/艺人列
    title_col = next((c for c in ("title","single") if c in tbl.columns), None)
    artist_col = next((c for c in ("artist","artist(s)") if c in tbl.columns), None)

    tbl["title"] = (
        tbl[title_col].astype(str)
        .str.replace(r"\[.*?\]", "", regex=True)
        .map(clean_title)
    )
    tbl["artist"] = (
        tbl[artist_col].astype(str)
        .str.replace(r"\[.*?\]", "", regex=True)
        .str.strip()
    )

    out = tbl[["rank","title","artist"]].dropna(subset=["title","artist"]).copy()
    out = out[(out["rank"]>=1) & (out["rank"]<=100)]
    out["rank"] = out["rank"].astype(int)
    out.insert(0, "year", int(year))
    return out

def main():
    outdir = Path("data_out"); outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    for y in range(1958, 2024+1):
        try:
            dfy = parse_year(y)
            rows.append(dfy)
            print(f"[OK] {y}: {len(dfy)} rows")
        except Exception as e:
            print(f"[WARN] {y}: {e}")
        time.sleep(1.0)  # 降低风控概率
    if not rows:
        raise SystemExit("No tables parsed. Check network/parse deps (lxml/html5lib).")
    all_df = pd.concat(rows, ignore_index=True)
    out_path = outdir / "yearend_hot100_1958_2024.csv"
    all_df.to_csv(out_path, index=False)
    chk = all_df.groupby("year")["rank"].count().reset_index(name="rows_per_year")
    print("Saved ->", out_path)
    print(chk.head(10).to_string(index=False))
    print("Years:", all_df["year"].min(), "-", all_df["year"].max(), "Total rows:", len(all_df))

if __name__ == "__main__":
    main()
