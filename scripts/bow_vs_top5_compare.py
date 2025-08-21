import argparse
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import zipfile

def yearly_mean_se(df, value_col, year_col="year"):
    g = df.groupby(year_col)[value_col].agg(["mean","std","count"]).reset_index()
    g["se"] = g["std"] / np.sqrt(g["count"]).replace(0, np.nan)
    return g

def ols_trend(y_tbl):
    # y_tbl: columns year, mean
    x = y_tbl["year"].astype(float).values
    y = y_tbl["mean"].astype(float).values
    if len(x) < 5:
        return dict(n=len(x), slope=np.nan, r2=np.nan, p=np.nan)
    try:
        from scipy.stats import linregress
        r = linregress(x, y)
        return dict(n=len(x), slope=r.slope, r2=r.rvalue**2, p=r.pvalue)
    except Exception:
        slope = np.cov(x, y, ddof=1)[0,1] / np.var(x, ddof=1)
        yhat = slope*x + (y.mean() - slope*x.mean())
        ss_res = ((y-yhat)**2).sum(); ss_tot=((y-y.mean())**2).sum()
        r2 = 1-ss_res/ss_tot if ss_tot>0 else np.nan
        return dict(n=len(x), slope=slope, r2=r2, p=np.nan)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hot100_bow_csv", required=True)   # e.g., data_out/hot100_bow_1991_2011.csv
    ap.add_argument("--top5_metrics_csv", required=True) # e.g., data_out/top5_metrics.csv
    ap.add_argument("--out_prefix", default="data_out/bow_vs_top5_1991_2011")
    ap.add_argument("--min_n_per_year", type=int, default=20, help="min songs per year to keep (for 6-100)")
    ap.add_argument("--start", type=int, default=1991)
    ap.add_argument("--end",   type=int, default=2011)
    args = ap.parse_args()

    hot = pd.read_csv(args.hot100_bow_csv)
    top = pd.read_csv(args.top5_metrics_csv)

    # 只保留指定年份窗口
    hot = hot[(hot["year"].between(args.start, args.end))]
    top = top[(top["year"].between(args.start, args.end)) & (top["rank"]<=5)]

    # 只用 TTR 对齐（BoW 与 Top-5 唯一可直接对比的一致指标）
    # Hot-100(6–100) 年度均值 + 过滤每年样本量
    hot_y = yearly_mean_se(hot, "ttr")
    hot_y = hot_y[hot_y["count"]>=args.min_n_per_year]

    # Top-5 年度均值（每年 5 首，已在 CSV 内）
    top_y = yearly_mean_se(top, "ttr")

    # 年份交集
    years = sorted(set(hot_y["year"]).intersection(set(top_y["year"])))
    hot_y = hot_y[hot_y["year"].isin(years)].sort_values("year")
    top_y = top_y[top_y["year"].isin(years)].sort_values("year")

    # 保存年度表
    out_year_csv = f"{args.out_prefix}_yearly_ttr.csv"
    yearly_join = pd.DataFrame({
        "year": years,
        "ttr_hot_mean": [hot_y.set_index("year").loc[y,"mean"] for y in years],
        "ttr_hot_se":   [hot_y.set_index("year").loc[y,"se"]   for y in years],
        "ttr_hot_n":    [hot_y.set_index("year").loc[y,"count"]for y in years],
        "ttr_top5_mean":[top_y.set_index("year").loc[y,"mean"] for y in years],
        "ttr_top5_se":  [top_y.set_index("year").loc[y,"se"]   for y in years],
        "ttr_top5_n":   [top_y.set_index("year").loc[y,"count"]for y in years],
    })
    yearly_join.to_csv(out_year_csv, index=False)

    # OLS 趋势
    ols_hot = ols_trend(hot_y.rename(columns={"mean":"mean"}))
    ols_top = ols_trend(top_y.rename(columns={"mean":"mean"}))

    # 也做“差值曲线”的 OLS（Top-5 − Hot）
    diff_tbl = pd.DataFrame({"year": years, "mean": yearly_join["ttr_top5_mean"] - yearly_join["ttr_hot_mean"]})
    ols_diff = ols_trend(diff_tbl)

    out_ols_csv = f"{args.out_prefix}_ols.csv"
    pd.DataFrame([
        {"series":"Hot100_6_100_TTR", **ols_hot},
        {"series":"Top5_TTR",         **ols_top},
        {"series":"Top5_minus_Hot_TTR", **ols_diff},
    ]).to_csv(out_ols_csv, index=False)

    # 画一张对比图（两条线 + 95% CI）
    fig, ax = plt.subplots(figsize=(9,4.8))
    ax.plot(hot_y["year"], hot_y["mean"], marker='o', linewidth=1.5, label="Hot-100 (6–100) TTR")
    if hot_y["se"].notna().any():
        ax.fill_between(hot_y["year"], hot_y["mean"]-1.96*hot_y["se"], hot_y["mean"]+1.96*hot_y["se"], alpha=0.18)

    ax.plot(top_y["year"], top_y["mean"], marker='s', linewidth=1.5, label="Top-5 TTR")
    if top_y["se"].notna().any():
        ax.fill_between(top_y["year"], top_y["mean"]-1.96*top_y["se"], top_y["mean"]+1.96*top_y["se"], alpha=0.18)

    ax.set_xlabel("Year"); ax.set_ylabel("TTR")
    ax.set_title(f"TTR: Top-5 vs Hot-100 (6–100), {years[0]}–{years[-1]}")
    ax.legend()
    plt.tight_layout()
    plot_path = f"{args.out_prefix}_ttr.png"
    fig.savefig(plot_path, dpi=150, bbox_inches="tight")

    # 打包
    bundle = f"{args.out_prefix}_bundle.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(out_year_csv, arcname=Path(out_year_csv).name)
        z.write(out_ols_csv,  arcname=Path(out_ols_csv).name)
        z.write(plot_path,    arcname=Path(plot_path).name)
    print("Saved bundle:", bundle)

if __name__ == "__main__":
    main()
