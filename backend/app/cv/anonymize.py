"""Remove identity / protected attributes from the text the evaluator sees."""
import re
import unicodedata

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# A phone number must look like one: French (0X or +33 then 4 pairs) or international with a leading "+".
# Date ranges ("2015 - 2024", "01/2015 - 12/2020") and volumes must never match.
_PHONE = re.compile(
    r"(?<![\w+])(?:(?:\+33\s?(?:\(0\))?\s?|0)[1-9](?:[\s.-]?\d{2}){4}"
    r"|\+(?!33)\d{1,3}(?:[\s.-]?\(?\d{1,4}\)?){2,5})(?!\d)"
)
_URL = re.compile(r"(?:https?://|www\.|linkedin\.com/|github\.com/)\S+", re.I)
# Explicit age / birth date: anywhere in the CV.
_AGE_EXPLICIT = re.compile(
    r"\b\d{2}\s*(?:years?\s*old|yo\b|y/o)|\bâgée?\s*de\s*\d{2}\b|\bage\s*:\s*\d{2}\b"
    r"|\bné(?:e)?\s+(?:le\s+)?[\d/ .a-zéû]+\d{4}|\bborn\s+(?:on\s+)?[\d/ .a-z]+\d{4}",
    re.I,
)
# A bare "38 ans" is an age only in the header; "15 ans d'expérience" is evidence and must survive.
_AGE_BARE = re.compile(r"\b\d{2}\s*ans\b(?!\s*(?:d['’]|de\s|dans\s|en\s|chez\s|au\s|à\s|comme\s))", re.I)
_ADDRESS = re.compile(
    r"\b\d{1,3}[ ,]*(?:bis|ter)?[ ,]*(?:rue|avenue|av\.|boulevard|bd|chemin|allée|impasse|place|route)\b[^\n·|]*",
    re.I,
)
_ZIP = re.compile(r"\b\d{5}\b")  # header only: "35000 m²" or "12000 références" further down are evidence
HEADER_LINES = 6

_ACCENTS = {"a": "aàâäá", "e": "eéèêë", "i": "iîïí", "o": "oôöó", "u": "uùûüú", "c": "cç", "n": "nñ", "y": "yÿ"}


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _loose(word: str) -> str:
    """Regex for a word that ignores accents: "Chloe" also matches "Chloé" (and the reverse)."""
    out = []
    for ch in word:
        base = _fold(ch).lower()
        out.append(f"[{_ACCENTS[base]}]" if base in _ACCENTS else re.escape(ch))
    return "".join(out)


def _name_pattern(name: str) -> re.Pattern | None:
    parts = [p for p in re.split(r"\s+", name.strip()) if len(p) >= 2]
    if not parts:
        return None
    full = r"\s+".join(_loose(p) for p in parts)
    alts = [full] + [_loose(p) for p in parts if len(p) >= 3]
    return re.compile(r"(?<!\w)(?:" + "|".join(alts) + r")(?!\w)", re.I)


def anonymize(text: str, profile: dict | None = None) -> str:
    profile = profile or {}
    out = text
    # Order matters: e-mails and links first. If the name were replaced first, "jean.dupont@school.tn" would become
    # "[CANDIDAT].[CANDIDAT]@school.tn", the e-mail pattern would no longer match and the domain would leak.
    out = _EMAIL.sub("[EMAIL]", out)
    out = _URL.sub("[LIEN]", out)
    if profile.get("name"):
        pat = _name_pattern(profile["name"])
        if pat:
            out = pat.sub("[CANDIDAT]", out)
    out = _AGE_EXPLICIT.sub("[ÂGE]", out)
    out = _ADDRESS.sub("[ADRESSE]", out)
    out = _PHONE.sub("[TÉLÉPHONE]", out)
    # Header only (name / title / contact lines): bare age, postcode and city. Further down, numbers and
    # place names are evidence (years of experience, m², employers, schools) and must stay readable.
    lines = out.split("\n")
    head, body = "\n".join(lines[:HEADER_LINES]), "\n".join(lines[HEADER_LINES:])
    head = _AGE_BARE.sub("[ÂGE]", head)
    head = _ZIP.sub("[CP]", head)
    city = (profile.get("city") or "").strip()
    if len(city) >= 3:
        head = re.sub(r"(?<!\w)" + _loose(city) + r"(?!\w)", "[VILLE]", head, flags=re.I)
    return head + ("\n" + body if body else "")
