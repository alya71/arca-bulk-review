"""Citation verification: the model's quote must actually exist in the source.

A quote is located with fuzzy alignment (tolerates whitespace/hyphenation/case
differences from PDF extraction). The matched character span maps to word indices,
and the words to rectangles on the original PDF page. No match → unverified, and
the UI shows no highlight rather than a made-up one.
"""
import re
from dataclasses import dataclass

from rapidfuzz import fuzz

MIN_SCORE = 90.0
_norm_re = re.compile(r"[^a-z0-9%.,;:/()+\-<>]+")


def norm(s: str) -> str:
    return _norm_re.sub(" ", s.lower()).strip()


@dataclass
class Match:
    score: float
    word_start: int  # inclusive, words.idx
    word_end: int


def locate(quote: str, words: list[dict]) -> Match | None:
    """Find `quote` within an ordered list of word rows ({idx, text, ...})."""
    q = norm(quote)
    if len(q) < 4 or not words:
        return None
    # Build the normalized haystack with a char-offset → word map.
    parts, owners, pos = [], [], 0
    for w in words:
        t = norm(w["text"])
        if not t:
            continue
        parts.append(t)
        owners.append((pos, pos + len(t), w["idx"]))
        pos += len(t) + 1
    hay = " ".join(parts)
    if len(q) > len(hay):
        return None
    al = fuzz.partial_ratio_alignment(q, hay, score_cutoff=MIN_SCORE)
    if al is None:
        return None
    hit = [idx for s, e, idx in owners if s < al.dest_end and e > al.dest_start]
    return Match(al.score, hit[0], hit[-1]) if hit else None


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
