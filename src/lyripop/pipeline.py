import argparse
from pathlib import Path
import pandas as pd
from tqdm import tqdm
from .charts import fetch_year_end_hot100
from .lyrics import fetch_lyrics_for_chart
from .metrics import compute_metrics

def main():
    ap = argparse.ArgumentParser(description="LyriPop v2: Year-End Hot 100 lyrics pipeline")
    ap.add_argument("--outdir", default="data_out")
    ap.add_argument("--start", type=int, default=1980)
    ap.add_argument("--end", type=int, default=2024)
    ap.add_argument("--fetch_charts", action="store_true")
    ap.add_argument("--fetch_lyrics", action="store_true")
    ap.add_argument("--compute", action="store_true")
    args = ap.parse_args()

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    charts_csv = outdir / f"yearend_hot100_{args.start}_{args.end}.csv"
    lyrics_csv = outdir / f"yearend_hot100_lyrics_{args.start}_{args.end}.csv"
    metrics_csv = outdir / f"yearend_hot100_metrics_{args.start}_{args.end}.csv"

    if args.fetch_charts:
        frames = []
        for y in tqdm(range(args.start, args.end+1), desc="Year-End Hot 100"):
            df_y = fetch_year_end_hot100(y, fallback_dir=outdir/"_html")
            if df_y is None or df_y.empty:
                print(f"[WARN] No rows for {y}. Check saved HTML in {outdir/'_html'}.")
                continue
            frames.append(df_y)
        if not frames:
            raise SystemExit("[ERROR] No charts fetched. Aborting.")
        charts = pd.concat(frames, ignore_index=True)
        charts.to_csv(charts_csv, index=False)
        print(f"[OK] {len(charts)} rows -> {charts_csv}")

    if args.fetch_lyrics:
        if not charts_csv.exists():
            raise SystemExit(f"[ERROR] Missing charts CSV: {charts_csv}. Run --fetch_charts first.")
        charts = pd.read_csv(charts_csv)
        lyrics_df = fetch_lyrics_for_chart(charts, outdir / "lyrics_cache")
        lyrics_df.to_csv(lyrics_csv, index=False)
        print(f"[OK] {len(lyrics_df)} rows -> {lyrics_csv}")

    if args.compute:
        base_df = (pd.read_csv(lyrics_csv) if lyrics_csv.exists() else pd.read_csv(charts_csv)).fillna({"lyrics_raw": ""})
        metrics = compute_metrics(base_df)
        metrics.to_csv(metrics_csv, index=False)
        metrics[metrics["is_top5"] == 1].to_csv(outdir / "top5_metrics.csv", index=False)
        metrics[metrics["is_top5"] == 0].to_csv(outdir / "non_top5_metrics.csv", index=False)
        print(f"[OK] Metrics saved -> {metrics_csv} (+ splits)")

if __name__ == "__main__":
    main()
