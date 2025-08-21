import argparse, glob, os, re
from pathlib import Path
import pandas as pd
from rapidfuzz import fuzz

def norm(s):
    s = (s or "").lower().strip()
    s = s.replace("&", " and ")
    s = re.sub(r"feat\.|featuring|with", " ", s)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r'["“”‘’]', " ", s)
    s = re.sub(r"[^a-z0-9\s']", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def key_combo(title, artist):
    return f"{norm(title)} {norm(artist)}".strip()

def _clean_field(x: str) -> str:
    # 把多连下划线视作空格，清掉多余空格
    x = re.sub(r"_+", " ", x)
    x = re.sub(r"\s+", " ", x).strip()
    return x

def parse_stub_name(fn):
    base = os.path.splitext(os.path.basename(fn))[0].strip()

    # 1) 支持 YYYY | Artist | Title
    m = re.match(r"^(\d{4})\s*\|\s*(.+?)\s*\|\s*(.+)$", base)
    if m:
        y, a, t = m.groups()
        return int(y), _clean_field(a), _clean_field(t)

    # 2) 支持 YYYY _ Artist _ Title （safe_filename 典型输出）
    parts = re.split(r"\s+_\s+", base)
    if len(parts) >= 3 and re.match(r"^\d{4}$", parts[0].strip()):
        y = int(parts[0].strip())
        a = _clean_field(parts[1])
        t = _clean_field(" ".join(parts[2:]))
        return y, a, t

    # 3) 退一步：YYYY - Artist - Title
    parts = re.split(r"\s+-\s+", base)
    if len(parts) >= 3 and re.match(r"^\d{4}$", parts[0].strip()):
        y = int(parts[0].strip())
        a = _clean_field(parts[1])
        t = _clean_field(" ".join(parts[2:]))
        return y, a, t

    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lyrics_csv", required=True)
    ap.add_argument("--stubs_dir",   default="manual_top5_missing")
    ap.add_argument("--threshold",   type=int, default=75)  # 略放宽，适配“清洗后标题”
    args = ap.parse_args()

    df = pd.read_csv(args.lyrics_csv)
    # 只填 Top-5（1958–2022）且 lyrics_raw 为空的行
    cand = df[(df["rank"]<=5) & (df["year"].between(1958,2022)) & (df["lyrics_raw"].fillna("")=="")].copy()
    if cand.empty:
        print("No empty Top-5 rows to fill. Done.")
        return

    cand["combo"] = cand.apply(lambda r: key_combo(r["title"], r["artist"]), axis=1)

    filled = 0; tried = 0
    for fp in glob.glob(os.path.join(args.stubs_dir, "*.txt")):
        tried += 1
        parsed = parse_stub_name(fp)
        if not parsed:
            print("Skip (bad name):", fp)
            continue
        y, a_stub, t_stub = parsed

        txt = Path(fp).read_text(encoding="utf-8", errors="ignore")
        if not txt.strip():
            print("Skip (empty text):", fp)
            continue

        combo_stub = key_combo(t_stub, a_stub)

        # 先同年，再全局
        pool = cand[cand["year"]==y].copy()
        if pool.empty:
            pool = cand.copy()
            scope = "global"
        else:
            scope = f"year={y}"

        if pool.empty:
            print("No candidate pool for", fp); 
            continue

        best_i = None; best_sc = -1
        for i, row in pool.iterrows():
            sc = fuzz.token_set_ratio(combo_stub, row["combo"])
            if sc > best_sc:
                best_sc, best_i = sc, i

        if best_sc >= args.threshold and best_i is not None:
            idx = int(pool.loc[best_i].name)  # 原 df 的索引
            df.at[idx, "lyrics_raw"] = txt
            filled += 1
            cand = cand.drop(index=idx, errors="ignore")
            print(f"[OK] match {scope}: score={best_sc} -> row {idx}")
        else:
            print(f"[WARN] no good match ({scope}) for {fp} (best={best_sc})")

    df.to_csv(args.lyrics_csv, index=False)
    print(f"Filled rows: {filled} / stubs tried: {tried}")
    remaining = df[(df["rank"]<=5) & (df["year"].between(1958,2022)) & (df["lyrics_raw"].fillna("")=="")]
    print("Remaining true-missing Top-5:", len(remaining))

if __name__ == "__main__":
    main()
