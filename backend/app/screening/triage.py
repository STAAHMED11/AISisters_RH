"""Triage = pure code over per-criterion verdicts. The LLM never sets a score."""

VERDICT_VALUE = {"met": 1.0, "partial": 0.5, "not_evidenced": 0.3, "not_met": 0.0}
KIND_WEIGHT = {"must": 3.0, "nice": 1.0}
from ..config import settings

YES_AT = settings.yes_threshold      # default 0.70, override with YES_THRESHOLD in .env
MAYBE_AT = settings.maybe_threshold  # default 0.45

PREQUAL = {"yes": "pass", "maybe": "review", "no": "fail"}
UNVERIFIED_FAIL = "[citation non vérifiée, verdict initial: not_met]"


def unverified_fail(rationale: str) -> bool:
    """The model said "not met" but its quote was not found: the verdict is downgraded, the doubt is not."""
    return (rationale or "").startswith(UNVERIFIED_FAIL)


def cv_score(items: list[tuple[str, str]]) -> float:
    """items: [(kind, verdict)] for CV-source criteria only. Returns 0..1."""
    tot = sum(KIND_WEIGHT[k] for k, _ in items)
    if not tot:
        return 0.0
    return sum(KIND_WEIGHT[k] * VERDICT_VALUE[v] for k, v in items) / tot


def triage(items: list[tuple[str, str]], injection: bool = False, doubt: bool = False) -> tuple[float, str]:
    """`doubt`: a must-have was judged not met without a verifiable quote -> never an automatic "yes"."""
    score = cv_score(items)
    blocked = doubt or any(k == "must" and v == "not_met" for k, v in items)
    if score >= YES_AT and not blocked and not injection:
        return score, "yes"
    if score >= MAYBE_AT:
        return score, "maybe"
    return score, "no"
