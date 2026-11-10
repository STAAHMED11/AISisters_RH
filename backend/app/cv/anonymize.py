"""Remove identity / protected attributes from the text the evaluator sees."""
import re
import unicodedata

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d .()-]{7,}\d)(?!\d)")
_URL = re.compile(r"(?:https?://|www\.|linkedin\.com/|github\.com/)\S+", re.I)
_AGE = re.compile(
    r"\b(\d{2})\s*(?:ans|an\b|years?\s*old|yo\b|y/o)|\bâgée?\s*de\s*\d{2}\b|\bage\s*:\s*\d{2}\b"
    r"|\bné(?:e)?\s+(?:le\s+)?[\d/ .a-zéû]+\d{4}|\bborn\s+(?:on\s+)?[\d/ .a-z]+\d{4}",
    re.I,
)
_ADDRESS = re.compile(
    r"\b\d{1,3}[ ,]*(?:bis|ter)?[ ,]*(?:rue|avenue|av\.|boulevard|bd|chemin|allée|impasse|place|route)\b[^\n·|]*",
    re.I,
)
_ZIP = re.compile(r"\b\d{5}\b")


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _name_pattern(name: str) -> re.Pattern | None:
    parts = [p for p in re.split(r"\s+", name.strip()) if len(p) >= 2]
    if not parts:
        return None
    alts = [re.escape(name.strip())] + [re.escape(p) for p in parts if len(p) >= 3]
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
    out = _AGE.sub("[ÂGE]", out)
    out = _ADDRESS.sub("[ADRESSE]", out)
    out = _PHONE.sub("[TÉLÉPHONE]", out)
    out = _ZIP.sub("[CP]", out)
    # city: only in the first lines (name / title / contact line), never in employers/schools further down
    city = (profile.get("city") or "").strip()
    if len(city) >= 3:
        lines = out.split("\n")
        head = "\n".join(lines[:4])
        head = re.sub(r"(?<!\w)" + re.escape(city) + r"(?!\w)", "[VILLE]", head, flags=re.I)
        out = head + "\n" + "\n".join(lines[4:])
    return out
