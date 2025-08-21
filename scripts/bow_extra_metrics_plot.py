import argparse, numpy as np, pandas as pd
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import zipfile

def yearly(df, col):
    g = df.groupby("year")[col].agg(["mean","std","count"]).reset_index()
    g["se"] = g["std"]/np.sqrt(g["count"]).replace(0, np.nan)
    return g

def ols(tbl):
    x = tbl["year"].values.astype(float); y = tbl["mean"].values.astype(float)
    if len(x)<5: return dict(n=len(x), slope=np.nan, r2=np.nan, p=np.nan)
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
    ap.add_argument("--hot100_bow_csv", required=True)      # hot100_bow_1991_2011.csv
    ap.add_argument("--out_prefix", default="data_out/hot100_bow_1991_2011_extra")
    ap.add_argument("--min_n_per_year", type=int, default=20)
    args = ap.parse_args()

    df = pd.read_csv(args.hot100_bow_csv)
    keep = df.groupby("year").size().reset_index(name="n")
    years = set(keep[keep["n"]>=args.min_n_per_year]["year"])
    df = df[df["year"].isin(years)].copy()

    metrics = [m for m in ["entropy","hhi","max_p"] if m in df.columns]
    outs, ols_rows = [], []
    for m in metrics:
        y = yearly(df, m).sort_values("year")
        # plot
        fig, ax = plt.subplots(figsize=(9,4.2))
        ax.plot(y["year"], y["mean"], marker="o", linewidth=1.5, label=f"Hot-100 (6–100) {m}")
        if y["se"].notna().any():
            ax.fill_between(y["year"], y["mean"]-1.96*y["se"], y["mean"]+1.96*y["se"], alpha=0.18)
        ax.set_xlabel("Year"); ax.set_ylabel(m); ax.set_title(f"{m} – Hot-100 (6–100)")
        ax.legend(); plt.tight_layout()
        p_png = Path(f"{args.out_prefix}_{m}.png"); fig.savefig(p_png, dpi=150, bbox_inches="tight"); plt.close(fig)
        p_csv = Path(f"{args.out_prefix}_{m}_yearly.csv"); y.to_csv(p_csv, index=False)
        outs += [p_png, p_csv]
        # OLS
        s = ols(y); s.update(metric=m); ols_rows.append(s)

    ols_df = pd.DataFrame(ols_rows)[["metric","n","slope","r2","p"]]
    p_ols = Path(f"{args.out_prefix}_ols.csv"); ols_df.to_csv(p_ols, index=False)
    outs.append(p_ols)

    bundle = Path(f"{args.out_prefix}_bundle.zip")
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in outs: z.write(p, arcname=p.name)
    print("Saved bundle:", bundle)
    print(ols_df.to_string(index=False))

if __name__ == "__main__":
    main()
