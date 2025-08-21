import re, html, io, gzip
from unidecode import unidecode

BRACKET_RE = re.compile(r"\[[^\]]{1,40}\]")
NON_ASCII_RE = re.compile(r"[^\x00-\x7F]+")
SAFE_FN_RE = re.compile(r"[^a-zA-Z0-9._-]+")

def slugify(text: str) -> str:
    s = unidecode(text or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "na"

def safe_filename(name: str) -> str:
    return SAFE_FN_RE.sub("_", name or "na")

def clean_lyrics(raw: str) -> str:
    if not isinstance(raw, str):
        return ""
    s = html.unescape(raw)
    s = BRACKET_RE.sub(" ", s)               # [Chorus]
    s = s.replace("\r", "\n")
    s = s.replace("\u2005"," ").replace("\u2009"," ").replace("\u00a0"," ")
    s = NON_ASCII_RE.sub(" ", s)             # ASCII
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"(?im)^.*you might also like.*$", "", s)
    s = re.sub(r"(?im)^.*embed$", "", s)
    return s.strip()

def repetition_ratio(text: str) -> float:
    lines = [ln.strip().lower() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return 0.0
    total = len(lines); uniq = len(set(lines))
    return 1.0 - (uniq/total)

def compressibility(text: str) -> float:
    if not text:
        return 0.0
    raw = text.encode("utf-8", errors="ignore")
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb") as gz:
        gz.write(raw)
    comp = out.getvalue()
    ratio = 1.0 - (len(comp) / max(1, len(raw)))
    return max(0.0, min(1.0, ratio))

def normalise_artist(artist: str) -> str:
    import re
    a = re.split(r"feat\.|featuring|with|&|,|\(|\)", artist or "", maxsplit=1, flags=re.I)[0]
    return a.strip()

def normalise_title(title: str) -> str:
    import re
    t = re.sub(r"\([^)]*version[^)]*\)", "", title or "", flags=re.I)
    t = re.sub(r"\([^)]*remix[^)]*\)", "", t, flags=re.I)
    t = re.sub(r"\s+-\s+.*$", "", t)
    return t.strip()
