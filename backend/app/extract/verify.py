"""Citation verification: the model's quote must exist, exactly, in the source.

A quote is verified only if it appears verbatim in the document's words. The only
differences tolerated are case, whitespace, and typographic variants (curly vs straight
quotes, dash types, ligatures). No fuzzy matching: a quote with one word changed is
unverified. The matched words then become (a) the rectangles highlighted on the original
PDF and (b) the quote text we display, so what users see in quotation marks is always
the document's own text, never the model's copy of it.
"""
import unicodedata
from dataclasses import dataclass

_TYPO = str.maketrans({"‘": "'", "’": "'", "‚": "'", "‛": "'", "“": '"', "”": '"', "„": '"',
                       "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-", " ": " "})


def norm(s: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", s).translate(_TYPO).lower().split())


@dataclass
class Match:
    word_start: int  # inclusive, words.idx
    word_end: int
    text: str        # the source document's own words for the matched span
    score: float = 100.0


def locate(quote: str, words: list[dict]) -> Match | None:
    """Find `quote` verbatim within an ordered list of word rows ({idx, text, ...})."""
    q = norm(quote).strip(" \"'")  # models sometimes wrap the quote in quote marks
    if len(q) < 4 or not words:
        return None
    parts, owners, pos = [], [], 0
    for w in words:
        t = norm(w["text"])
        if not t:
            continue
        parts.append(t)
        owners.append((pos, pos + len(t), w))
        pos += len(t) + 1
    hay = " ".join(parts)
    i = hay.find(q)
    while i != -1:
        j = i + len(q)
        # Must start on a word boundary and not end mid-word ("PH-10" must not match "PH-102").
        if (i == 0 or hay[i - 1] == " ") and (j == len(hay) or not hay[j].isalnum()):
            hit = [w for s, e, w in owners if s < j and e > i]
            return Match(hit[0]["idx"], hit[-1]["idx"], " ".join(w["text"] for w in hit))
        i = hay.find(q, i + 1)
    return None


def rects_for(words: list[dict], start: int, end: int) -> list[dict]:
    """Merge word boxes into one rectangle per visual line."""
    rects: list[dict] = []
    for w in words:
        if not (start <= w["idx"] <= end):
            continue
        r = rects[-1] if rects else None
        if r and r["page"] == w["page"] and abs(r["y0"] - w["y0"]) < 3 and w["x0"] >= r["x0"]:
            r["x1"], r["y1"] = max(r["x1"], w["x1"]), max(r["y1"], w["y1"])
        else:
            rects.append({"page": w["page"], "x0": w["x0"], "y0": w["y0"], "x1": w["x1"], "y1": w["y1"]})
    return rects
