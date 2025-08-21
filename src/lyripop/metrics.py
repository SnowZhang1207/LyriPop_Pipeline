import re
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import textstat
from .utils import clean_lyrics, repetition_ratio, compressibility

def _ttr(text: str) -> float:
    toks = re.findall(r"[a-zA-Z']+", (text or "").lower())
    return (len(set(toks)) / len(toks)) if toks else 0.0

def _fk(text: str) -> float:
    sents = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not sents: return 0.0
    block = ". ".join(sents)
    try: return float(textstat.flesch_kincaid_grade(block))
    except Exception: return 0.0

def _vader(text: str, ana=None) -> float:
    ana = ana or SentimentIntensityAnalyzer()
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines: return 0.0
    scores = [ana.polarity_scores(ln)["compound"] for ln in lines]
    return sum(scores)/len(scores)

def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    ana = SentimentIntensityAnalyzer()
    rows = []
    for _, r in df.iterrows():
        raw = r.get("lyrics_raw", "")
        if not isinstance(raw, str):
            raw = ""
        cln = clean_lyrics(raw)
        rows.append({
            **r.to_dict(),
            "lyrics_clean": cln,
            "lines": len([ln for ln in cln.splitlines() if ln.strip()]),
            "tokens": len(re.findall(r"[a-zA-Z']+", cln)),
            "vader": _vader(cln, ana),
            "fk_grade": _fk(cln),
            "ttr": _ttr(cln),
            "repetition_ratio": repetition_ratio(cln),
            "compressibility": compressibility(cln),
            "is_top5": int(r["rank"]) <= 5
        })
    return pd.DataFrame(rows)
