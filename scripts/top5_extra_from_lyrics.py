import re, html, math, argparse
from pathlib import Path
from collections import Counter
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from nltk.stem import PorterStemmer
    stemmer = PorterStemmer()
except Exception:
    stemmer = None

def clean_text(raw: str) -> str:
    s = html.unescape(raw or "")
    s = re.sub(r"\[[^\]]*\]", " ", s)       # 去除 [Chorus] 等舞台标注
    s = re.sub(r"\([^)]*\)", " ", s)        # 去除(备注)
    s = s.lower()
    return s

def tokenize_stem(s: str):
    # 简单英文 token（保留撇号），再 Porter stem
    toks = re.findall(r"[a-z]+'?[a-z]*", s)
    if stemmer:
        toks = [stemmer.stem(t) for t in toks]
    return toks

def track_stats(tokens):
    total = len(tokens)
    if total == 0:
        return dict(total=0, ttr=0.0, entropy=0.0, hhi=0.0, max_p=0.0)
    c = Counter(tokens)
    uniq = len(c)
    ps = [v/total for v in c.values()]
    entropy = -sum(p*math.log(p+1e-12) for p in ps)  # 自然对数
    hhi = sum(p*p for p in ps)
    max_p = max(ps)
    ttr = uniq/total
    return dict(total=total, ttr=ttr, entropy=entropy, hhi=hhi, max_p=max_p)

def yearly_mean(df, col):
    g = df.groupby("year")[col].agg(["mean","std","count"]).reset_index()
    g["se"] = g["std"]/np.sqrt(g["count"]).replace(0, np.nan)
    return g

def ols(tbl):
    x = tbl["year"].values.astype(float); y = tbl["mean"].values.astype(float)
    if len(x) < 5:
        return dict(n=len(x), slope=np.nan, r2=np.nan, p=np.nan)
    try:
        from scipy.stats import linregress
        r = linregress(x,y)
        return dict(n=len(x), slope=r.slope, r2=r.rvalue**2, p=r.pvalue)
    except Exception:
        slope = np.cov(x,y,ddof=1)[0,1]/np.var(x,ddof=1)
        yhat = slope*x + (y.mean()-slope*x.mean())
        ss_res=((y-yhat)**2).sum(); ss_tot=((y-y.mean())**2).sum()
        r2 = 1-ss_res/ss_tot if ss_tot>0 else np.nan
        return dict(n=len(x), slope=slope, r2=r2, p=np.nan)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lyrics_csv", required=True)   # data_out/yearend_hot100_lyrics_1958_2024.csv
    ap.add_argument("--out_prefix", default="data_out/top5_extra_1958_2024")
    ap.add_argument("--start", type=int, default=1958)
    ap.add_argument("--end",   type=int, default=2024)
    args = ap.parse_args()

    df = pd.read_csv(args.lyrics_csv)
    df = df[(df["rank"]<=5) & (df["year"].between(args.start, args.end))].copy()
    # 清洗 + 词干化
    stats_rows = []
    for _, r in df.iterrows():
        txt = clean_text(str(r.get("lyrics_raw","")))
        toks = tokenize_stem(txt)
        st = track_stats(toks)
        stats_rows.append({**r.to_dict(), **st})
    out_tracks = f"{args.out_prefix}_tracks.csv"
    pd.DataFrame(stats_rows).to_csv(out_tracks, index=False)

    # 年度均值（Top-5 本来就 n=5/年；若有缺词则 <5）
    Y = {}
    for m in ["ttr","entropy","hhi","max_p"]:
        if m in stats_rows[0]:
            y = yearly_mean(pd.DataFrame(stats_rows), m).sort_values("year")
            Y[m] = y
            y.to_csv(f"{args.out_prefix}_{m}_yearly.csv", index=False)

    # 画图
    for m,y in Y.items():
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(9,4.2))
        ax.plot(y["year"], y["mean"], marker="o", linewidth=1.5, label=f"Top-5 {m} (stem-level)")
        if y["se"].notna().any():
            ax.fill_between(y["year"], y["mean"]-1.96*y["se"], y["mean"]+1.96*y["se"], alpha=0.18)
        ax.set_xlabel("Year"); ax.set_ylabel(m)
        ax.set_title(f"{m} – Top-5 (1958–2024)")
        ax.legend(); plt.tight_layout()
        fig.savefig(f"{args.out_prefix}_{m}.png", dpi=150, bbox_inches="tight")
        plt.close(fig)

    # OLS（年度均值）
    rows=[]
    for m,y in Y.items():
        s = ols(y); s.update(metric=m); rows.append(s)
    pd.DataFrame(rows)[["metric","n","slope","r2","p"]].to_csv(f"{args.out_prefix}_ols.csv", index=False)

    # 打包
    import zipfile
    bundle = f"{args.out_prefix}_bundle.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(out_tracks, arcname=Path(out_tracks).name)
        for m in Y:
            z.write(f"{args.out_prefix}_{m}_yearly.csv", arcname=f"{Path(args.out_prefix).name}_{m}_yearly.csv")
            z.write(f"{args.out_prefix}_{m}.png",         arcname=f"{Path(args.out_prefix).name}_{m}.png")
        z.write(f"{args.out_prefix}_ols.csv", arcname=f"{Path(args.out_prefix).name}_ols.csv")
    print("Saved bundle:", bundle)

if __name__ == "__main__":
    main()
