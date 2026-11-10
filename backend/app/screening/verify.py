"""Quote verification: 'no quote, no verdict'. Code checks the quote really exists in the source text."""
import difflib
import re

_QUOTES = str.maketrans({"’": "'", "‘": "'", "`": "'", "“": '"', "”": '"', "«": '"', "»": '"',
                         "–": "-", "—": "-", " ": " ", " ": " "})


def _norm(text: str) -> tuple[str, list[int]]:
    """Lowercase, unify quotes/dashes, collapse whitespace. Returns normalized text + index map to the original."""
    out, idx = [], []
    prev_space = True
    for i, ch in enumerate(text):
        ch = ch.translate(_QUOTES).lower()
        if ch.isspace() or ch in "·•|":
            if not prev_space:
                out.append(" ")
                idx.append(i)
            prev_space = True
        else:
            out.append(ch)
            idx.append(i)
            prev_space = False
    return "".join(out), idx


def _segments(quote: str) -> list[str]:
    parts = re.split(r"\.\.\.|…|\[\.\.\.\]", quote)
    return [p.strip() for p in parts if len(p.strip()) >= 8]


def verify_quote(quote: str, source: str, *, fuzzy: float = 0.9) -> tuple[bool, tuple[int, int] | None]:
    """Return (verified, (start, end) span in `source`) — span is None when not found."""
    if not quote or len(quote.strip()) < 8 or not source:
        return False, None
    nsrc, idx = _norm(source)
    spans = []
    for seg in _segments(quote) or [quote]:
        nq, _ = _norm(seg)
        nq = nq.strip()
        if not nq:
            continue
        pos = nsrc.find(nq)
        if pos < 0 and fuzzy:
            m = difflib.SequenceMatcher(None, nq, nsrc, autojunk=False).find_longest_match(0, len(nq), 0, len(nsrc))
            if m.size >= fuzzy * len(nq):
                pos, nq = m.b, nsrc[m.b : m.b + m.size]
        if pos < 0:
            return False, None
        spans.append((idx[pos], idx[pos + len(nq) - 1] + 1))
    if not spans:
        return False, None
    return True, (min(s[0] for s in spans), max(s[1] for s in spans))
