import re, argparse
from pathlib import Path
import pandas as pd

def norm(s):
    s = (s or "").lower()
    s = s.replace("&", " and ")
    s = re.sub(r"(feat\.|featuring|with)", " ", s)
    s = re.sub(r"[^a-z0-9\s']", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def first_word(s):
    s = norm(s)
    return s.split(" ")[0] if s else ""

def combo_key(title, artist):
    return f"{norm(title)} {norm(artist)}".strip()

def load_mxm_bow_one(txt_path: Path):
    vocab = []
    bow = {}
    with txt_path.open("r", encoding="utf-8", errors="ignore") as f:
        # read vocab line (starts with '#')
        for line in f:
            if not line:
                continue
            if line.startswith("#"):
                parts = [p.strip() for p in line[1:].strip().split(",") if p.strip()]
                for p in parts:
                    vocab.append(p.split(":", 1)[-1])
                break
        # read bow lines
        for line in f:
            line = line.strip()
            if not line or line.startswith("%"):
                continue
            if "," not in line:
                continue
            tid, rest = line.split(",", 1)
            pairs = [seg for seg in rest.split(",") if ":" in seg]
            if pairs:
                bow[tid] = pairs
    if not bow:
        raise RuntimeError(f"Failed to parse {txt_path}. Is it the unzipped txt?")
    return vocab, bow

def load_mxm_bow(train_path: Path, test_path: Path|None):
    v1, b1 = load_mxm_bow_one(train_path)
    total = len(b1)
    if test_path and test_path.exists():
        v2, b2 = load_mxm_bow_one(test_path)
        # 合并两个字典（后者覆盖前者同 id）
        b1.update(b2)
        total = len(b1)
    any_key = next(iter(b1))
    id_hint = "MSD(TR…)" if any_key.startswith("TR") else ("MXM" if any_key.upper().startswith("MXM") else "unknown")
    print(f"[OK] Loaded BoW tracks (merged): {total}  (ID type hint: {id_hint})")
    return b1

def load_matches(matches_path: Path, sample_lines=2000):
    delims = ["<SEP>", "\t", "|", ","]
    with matches_path.open("r", encoding="utf-8", errors="ignore") as f:
        lines = []
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            lines.append(line.rstrip("\n"))
            if len(lines) >= sample_lines:
                break
    if not lines:
        raise RuntimeError("mxm_779k_matches.txt seems empty or all commented; check the file.")

    def try_split(line, delim):
        if delim == "<SEP>":
            parts = re.split(r"\s*<SEP>\s*", line)
        else:
            parts = line.split(delim)
        return [p.strip() for p in parts if p is not None]

    best = None; best_med_cols = 0
    for d in delims:
        col_counts = []
        for ln in lines[:200]:
            parts = try_split(ln, d)
            col_counts.append(len(parts))
        median_cols = sorted(col_counts)[len(col_counts)//2]
        if median_cols > best_med_cols:
            best_med_cols = median_cols; best = d

    print(f"[INFO] Detected delimiter for matches: {best} (median cols ~ {best_med_cols})")

    rows = []
    with matches_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = try_split(line, best)
            if len(parts) < 4:
                continue
            msd_id, mxm_tid = parts[0], parts[1]
            artist, title = parts[-2], parts[-1]
            rows.append((msd_id, mxm_tid, artist, title))
    df = pd.DataFrame(rows, columns=["msd_id","mxm_tid","artist_mxm","title_mxm"])
    if df.empty:
        raise RuntimeError("Failed to parse mxm_779k_matches.txt — content/encoding looks wrong.")
    df["artist_key"] = df["artist_mxm"].map(norm)
    df["title_key"]  = df["title_mxm"].map(norm)
    df["first_artist_initial"] = df["artist_key"].map(lambda s: s[:1] if s else "")
    df["first_title_word"] = df["title_key"].map(first_word)
    df["mkey"] = df.apply(lambda r: f"{r['title_key']} {r['artist_key']}".strip(), axis=1)
    print(f"[OK] Parsed matches rows: {len(df)}")
    return df

def build_indices(mm: pd.DataFrame):
    idx_artist_init = {}; idx_title_first = {}
    for i, r in mm.iterrows():
        a0 = r["first_artist_initial"]; t0 = r["first_title_word"]
        idx_artist_init.setdefault(a0, []).append(i)
        idx_title_first.setdefault(t0, []).append(i)
    return idx_artist_init, idx_title_first

def candidate_rows(mm, a0, t0, idx_artist_init, idx_title_first, cap=3000):
    c1 = set(idx_artist_init.get(a0, []))
    c2 = set(idx_title_first.get(t0, []))
    inter = list(c1 & c2)
    if not inter:
        inter = list((c1 | c2))[:cap]
    if not inter:
        inter = list(range(min(cap, len(mm))))
    return mm.loc[inter]

def bow_stats(pairs):
    total = 0; counts = []
    for pc in pairs:
        try:
            _, c = pc.split(":")
            c = int(c)
            if c > 0:
                counts.append(c); total += c
        except Exception:
            pass
    if total == 0:
        return dict(total=0, ttr=0.0, entropy=0.0, hhi=0.0, max_p=0.0)
    import math
    ps = [c/total for c in counts]
    entropy = -sum(p*math.log(p+1e-12) for p in ps)
    hhi = sum(p*p for p in ps)
    max_p = max(ps)
    ttr = len(counts)/total
    return dict(total=total, ttr=ttr, entropy=entropy, hhi=hhi, max_p=max_p)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yearend_csv", required=True)
    ap.add_argument("--mxm_matches", required=True)
    ap.add_argument("--mxm_dataset", required=True)      # train
    ap.add_argument("--mxm_dataset2", default="", help="mxm_dataset_test.txt (optional)")  # test
    ap.add_argument("--out_csv", default="data_out/hot100_bow_1991_2024.csv")
    ap.add_argument("--start", type=int, default=1991)
    ap.add_argument("--end", type=int, default=2024)
    ap.add_argument("--threshold", type=int, default=76)     # 略放宽
    ap.add_argument("--limit_per_query", type=int, default=3000) # 候选池更大
    args = ap.parse_args()

    charts = pd.read_csv(args.yearend_csv)
    charts = charts[(charts["year"].between(args.start, args.end)) & (charts["rank"].between(6,100))].copy()
    if charts.empty:
        raise RuntimeError("No rows in the given year/rank range — check --start/--end and input CSV.")
    charts["qkey"] = charts.apply(lambda r: combo_key(r["title"], r["artist"]), axis=1)
    charts["a0"] = charts["artist"].map(lambda s: norm(s)[:1] if s else "")
    charts["t0"] = charts["title"].map(first_word)

    mm = load_matches(Path(args.mxm_matches))
    idx_artist_init, idx_title_first = build_indices(mm)
    bow = load_mxm_bow(Path(args.mxm_dataset), Path(args.mxm_dataset2) if args.mxm_dataset2 else None)
    bow_keys = set(bow.keys())

    try:
        from rapidfuzz import fuzz
    except Exception:
        raise SystemExit("Please install rapidfuzz:  conda install -c conda-forge rapidfuzz  (or pip install rapidfuzz)")

    recs = []
    for _, r in charts.iterrows():
        q = r["qkey"]; a0 = r["a0"]; t0 = r["t0"]
        cand = candidate_rows(mm, a0, t0, idx_artist_init, idx_title_first, cap=args.limit_per_query)
        best_idx, best_sc = None, -1
        for i, mr in cand.iterrows():
            sc = fuzz.token_set_ratio(q, mr["mkey"])
            if sc > best_sc:
                best_sc = sc; best_idx = i
        if best_idx is not None and best_sc >= args.threshold:
            mr = mm.loc[best_idx]
            # 关键：BoW 的键可能是 TR（MSD）或 MXM，谁存在用谁
            tid = mr["msd_id"] if mr["msd_id"] in bow_keys else (mr["mxm_tid"] if mr["mxm_tid"] in bow_keys else None)
            if tid:
                pairs = bow.get(tid)
                if pairs:
                    stats = bow_stats(pairs)
                    recs.append({**r.to_dict(), **stats,
                                 "bow_tid": tid, "match_score": best_sc,
                                 "artist_mxm": mr["artist_mxm"], "title_mxm":  mr["title_mxm"]})

    out = pd.DataFrame(recs)
    Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out_csv, index=False)
    print("Saved:", args.out_csv, "| rows:", len(out))
    if len(out):
        print(out.groupby("year")["ttr"].mean().head())

if __name__ == "__main__":
    main()
