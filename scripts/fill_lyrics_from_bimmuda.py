import re, json, argparse
from pathlib import Path
import pandas as pd
from rapidfuzz import fuzz

def norm_text(s):
    s = (s or "").lower().strip()
    s = s.replace("&", " and ")
    s = re.sub(r"feat\.|featuring|with", " ", s)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r'["“”‘’]', " ", s)
    s = re.sub(r"[^a-z0-9\s']", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

ARTIST_ALIAS = {
    "ross bagdasarian": "david seville",
    "the weeknd": "weeknd",
    "p!nk": "pink",
    "ac dc": "acdc",
    "marky mark and the funky bunch": "marky mark funky bunch",
    "prince and the revolution": "prince",
    "puff daddy": "diddy",
    "jay z": "jayz",
}
def canon_artist(s):
    s2 = norm_text(s)
    return ARTIST_ALIAS.get(s2, s2)

def combo_key(title, artist):
    return f"{norm_text(title)} {canon_artist(artist)}".strip()

def looks_like_lyrics(txt):
    if not txt or len(txt) < 80: return False
    lines = txt.splitlines()
    if len(lines) < 5: return False
    bad_hits = sum(1 for l in lines[:15] if "copyright" in l.lower() or "all rights" in l.lower())
    return bad_hits == 0

def safe_filename(name: str) -> str:
    name = name.replace("\n", " ").replace("\r", " ")
    name = re.sub(r'[\\/*?:\"<>|]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:180]

def load_bimmuda_metadata(broot: Path):
    meta_csv = broot / "metadata" / "bimmuda_per_song_metadata.csv"
    if not meta_csv.exists():
        raise FileNotFoundError(f"Missing metadata CSV: {meta_csv}")
    meta = pd.read_csv(meta_csv)
    cols = {c: c.strip() for c in meta.columns}
    meta.rename(columns=cols, inplace=True)
    keep = ['Title','Artist','Year','Position']
    meta = meta[[c for c in keep if c in meta.columns]].copy()
    meta = meta.dropna(subset=['Title','Artist','Year','Position'])
    meta['Year'] = pd.to_numeric(meta['Year'], errors='coerce').astype('Int64')
    meta['Position'] = pd.to_numeric(meta['Position'], errors='coerce').astype('Int64')
    meta = meta.dropna(subset=['Year','Position'])
    meta['ck'] = meta.apply(lambda r: combo_key(r['Title'], r['Artist']), axis=1)
    return meta

def load_bimmuda_candidates(broot: Path):
    pool = []
    for p in broot.rglob("*.txt"):
        if p.name.startswith("._"):
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if not looks_like_lyrics(txt):
            continue
        stem = p.stem
        parent = p.parent.name
        grand = p.parent.parent.name if p.parent and p.parent.parent else ""
        firstline = txt.splitlines()[0] if txt else ""
        candidates = []
        for c in [stem, parent, grand, firstline, f"{parent} {stem}", f"{grand} {parent} {stem}"]:
            c = (c or "").strip()
            if c and c not in candidates:
                candidates.append(c)
        disp = max(candidates, key=lambda s: len(s)) if candidates else stem
        pool.append((disp, txt))
    return pool

def read_bimmuda_lyrics_by_pos(broot: Path, year: int, pos: int):
    d = broot / "bimmuda_dataset" / str(year) / str(int(pos))
    if not d.exists():
        return None
    cand = list(d.glob("*_lyrics.txt"))
    for p in cand:
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            if looks_like_lyrics(txt):
                return txt
        except Exception:
            pass
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--charts_csv", required=True)
    ap.add_argument("--bimmuda_root", required=True)
    ap.add_argument("--out_csv", required=True)
    ap.add_argument("--manual_json", default="manual_lyrics.json")
    ap.add_argument("--threshold", type=int, default=65)
    ap.add_argument("--make_missing_stubs", action="store_true")
    ap.add_argument("--report_csv", default="data_out/top5_matching_report.csv")
    args = ap.parse_args()

    charts = pd.read_csv(args.charts_csv)
    charts = charts[['year','rank','title','artist']].copy()
    charts['year'] = pd.to_numeric(charts['year'], errors='coerce').astype('Int64')
    charts['rank'] = pd.to_numeric(charts['rank'], errors='coerce').astype('Int64')
    charts = charts.dropna(subset=['year','rank','title','artist']).sort_values(['year','rank'])

    broot = Path(args.bimmuda_root)
    meta  = load_bimmuda_metadata(broot)
    pool  = load_bimmuda_candidates(broot)
    pool_labels = [norm_text(lbl) for lbl,_ in pool]
    print("BiMMuDa metadata rows:", len(meta), " | candidate lyric files:", len(pool))

    rows = []
    rep_rows = []
    auto_exact = 0
    auto_sameyear_fuzzy = 0
    auto_global_fuzzy = 0

    for _, r in charts.iterrows():
        y = int(r['year']); rank = int(r['rank'])
        t = str(r['title']); a = str(r['artist'])
        lyr = ""; src = ""

        if 1958 <= y <= 2022 and rank <= 5:
            # (A) exact by Year+Position
            mrow = meta[(meta['Year']==y) & (meta['Position']==rank)]
            if not mrow.empty:
                mt, ma = mrow.iloc[0]['Title'], mrow.iloc[0]['Artist']
                comb_q = combo_key(t, a); comb_m = combo_key(mt, ma)
                sc = fuzz.token_set_ratio(comb_q, comb_m)  # 只是记录分数
                txt = read_bimmuda_lyrics_by_pos(broot, y, rank)
                if txt:
                    lyr = txt; src = f"meta_pos:{y}-{rank}"
                    auto_exact += 1
                    rep_rows.append({"year": y, "rank": rank, "title": t, "artist": a,
                                     "match_score": sc, "source_label": src})

            # (B) same-year fuzzy if still empty
            if not lyr:
                same_year = meta[meta['Year']==y].copy()
                if not same_year.empty:
                    comb_q = combo_key(t, a)
                    best_i, best_sc, best_pos = -1, -1, None
                    for i, mr in same_year.reset_index(drop=True).iterrows():
                        comb_m = combo_key(mr['Title'], mr['Artist'])
                        sc = fuzz.token_set_ratio(comb_q, comb_m)
                        if sc > best_sc:
                            best_sc, best_i, best_pos = sc, i, int(mr['Position'])
                    if best_sc >= args.threshold:
                        txt = read_bimmuda_lyrics_by_pos(broot, y, best_pos)
                        if txt:
                            lyr = txt; src = f"meta_year_fuzzy:{y}-{best_pos}"
                            auto_sameyear_fuzzy += 1
                            rep_rows.append({"year": y, "rank": rank, "title": t, "artist": a,
                                             "match_score": best_sc, "source_label": src})

            # (C) global fallback if still empty
            if not lyr and pool:
                q = norm_text(f"{t} {a}")
                best_j, best_sc = -1, -1
                for j, lbl in enumerate(pool_labels):
                    sc = fuzz.token_set_ratio(q, lbl)
                    if sc > best_sc:
                        best_sc, best_j = sc, j
                if best_sc >= args.threshold:
                    lyr = pool[best_j][1]; src = "fallback_pool"
                    auto_global_fuzzy += 1
                    rep_rows.append({"year": y, "rank": rank, "title": t, "artist": a,
                                     "match_score": best_sc, "source_label": src})

            # 即便没命中也记录一条
            if not lyr:
                rep_rows.append({"year": y, "rank": rank, "title": t, "artist": a,
                                 "match_score": -1, "source_label": ""})

        rows.append({**r.to_dict(), "lyrics_raw": lyr, "lyrics_url": ""})

    # Merge manual 2023–2024 Top-5
    mfp = Path(args.manual_json)
    manual = {}
    if mfp.exists():
        try:
            manual = json.loads(mfp.read_text(encoding="utf-8"))
        except Exception:
            manual = {}
    else:
        templ = {}
        for _, r2 in charts[(charts['rank']<=5) & (charts['year']>=2023)].iterrows():
            key = f"{int(r2['year'])} | {r2['artist']} | {r2['title']}"
            templ[key] = "PASTE LYRICS HERE"
        mfp.write_text(json.dumps(templ, ensure_ascii=False, indent=2), encoding="utf-8")
        manual = templ
        print(f"Created template -> {mfp}")

    manual_hits = 0
    for row in rows:
        if int(row['year'])>=2023 and int(row['rank'])<=5:
            k = f"{int(row['year'])} | {row['artist']} | {row['title']}"
            v = manual.get(k)
            if v and v!="PASTE LYRICS HERE":
                row["lyrics_raw"] = v
                manual_hits += 1

    out = pd.DataFrame(rows)
    Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out_csv, index=False)
    print("Wrote ->", args.out_csv, "rows:", len(out))

    # Save report
    rep = pd.DataFrame(rep_rows).sort_values(["year","rank"])
    Path(args.report_csv).parent.mkdir(parents=True, exist_ok=True)
    rep.to_csv(args.report_csv, index=False)

    # ===== 修复点：按“是否真的无歌词”来判缺 =====
    missing_df = out[(out["rank"]<=5) &
                     (out["year"].between(1958,2022)) &
                     (out["lyrics_raw"].fillna("")=="")][["year","rank","title","artist"]]
    print(f"Auto exact by position: {auto_exact} | same-year fuzzy: {auto_sameyear_fuzzy} | global fuzzy: {auto_global_fuzzy}")
    print("Missing (1958–2022 Top-5, true lyric-missing rows):", len(missing_df), "| Manual hits (2023–24):", manual_hits)

    # Optional: create stubs only for the true-missing list
    if args.make_missing_stubs:
        outdir = Path("manual_top5_missing"); outdir.mkdir(exist_ok=True)
        c = 0
        for _, rr in missing_df.iterrows():
            raw_name = f"{int(rr['year'])} | {rr['artist']} | {rr['title']}.txt"
            safe_name = safe_filename(raw_name)
            fp = outdir / safe_name
            if not fp.exists():
                fp.write_text("", encoding="utf-8")
                c += 1
        print("Missing stubs created in manual_top5_missing/:", c)

    # Summary
    top5_missing_now = out[(out["rank"]<=5) & ((out["lyrics_raw"].isna()) | (out["lyrics_raw"]==""))]
    print("Top-5 missing lyrics rows (after manual merge):", len(top5_missing_now))
    print("Report CSV ->", args.report_csv)

if __name__ == "__main__":
    main()
