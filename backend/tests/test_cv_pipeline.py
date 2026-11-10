from pathlib import Path

import pytest

from backend.app.cv.anonymize import anonymize
from backend.app.cv.parse import parse_cv
from backend.app.screening.triage import triage
from backend.app.screening.verify import verify_quote

FIX = Path(__file__).resolve().parents[2] / "fixtures"


def cv(n):
    f = next(FIX.glob(f"CV 0{n} - *.docx"))
    return parse_cv(f.read_bytes(), f.name)


def test_paul_hidden_injection_is_split_from_visible_text():
    p = cv(5)
    assert any("ignorez les instructions" in h.lower() for h in p.hidden)
    assert "ignorez" not in p.text.lower()
    assert "TRANSALP" in p.text


@pytest.mark.parametrize("n", [1, 2, 3, 4, 6])
def test_other_cvs_have_no_hidden_text(n):
    p = cv(n)
    assert p.hidden == [] and len(p.text) > 500 and not p.needs_vision


def test_anonymize_removes_identity_but_keeps_experience():
    p = cv(1)
    prof = {"name": "Karim BENALI", "city": "Lyon"}
    a = anonymize(p.text, prof)
    for leak in ["Karim", "BENALI", "karim.benali", "06 41 27 83 90", "38 ans"]:
        assert leak.lower() not in a.lower(), leak
    assert "SAP EWM" in a and "35 000 m²" in a and "Corbas" in a
    assert "IUT Lyon 1" in a  # city only stripped from header


def test_anonymize_english_age_and_ana():
    a = anonymize(cv(6).text, {"name": "Ana Ribeiro", "city": "Lyon"})
    assert "41 years old" not in a and "Ribeiro" not in a and "+33 6 58" not in a
    assert "SUPERMERCADOS NORTE" in a


def test_verify_quote():
    src = cv(3).text
    ok, span = verify_quote("Encadrement fonctionnel d'équipes projet de 3 à 5 consultants (pas de management hiérarchique)", src)
    assert ok and src[span[0]:span[1]].startswith("Encadrement")
    assert verify_quote("Encadrement fonctionnel d’équipes projet  de 3 à 5 consultants", src)[0]  # quotes/spaces
    assert verify_quote("Direction d'un entrepôt de 60 personnes avec SAP", src)[0] is False
    assert verify_quote("Cadrage et assistance à maîtrise d'ouvrage ... pas de management hiérarchique", src)[0]
    assert verify_quote("Cadrage et assistance ... Direction de 60 personnes à Lyon", src)[0] is False
    assert verify_quote("", src)[0] is False


def test_triage_rules():
    allmet = [("must", "met")] * 5 + [("nice", "met")]
    assert triage(allmet)[1] == "yes"
    assert triage(allmet, injection=True)[1] == "maybe"
    lea = [("must", "not_met"), ("must", "met"), ("must", "not_evidenced"), ("must", "met"), ("must", "met"), ("nice", "not_evidenced")]
    assert triage(lea)[1] == "maybe"  # one not_met must never yields yes
    assert triage([("must", "not_met")] * 3 + [("must", "partial")])[1] == "no"


def test_yes_threshold_is_70_percent():
    from backend.app.screening.triage import YES_AT, MAYBE_AT
    assert (YES_AT, MAYBE_AT) == (0.70, 0.45)
    # 6 must (w=3) + 1 nice (w=1) = 19 points. Two partial + one not_evidenced must: (18 - 3 - 2.1 + 1)/19 = 0.73 -> yes
    ok = [("must", "met")] * 3 + [("must", "partial")] * 2 + [("must", "not_evidenced")] + [("nice", "met")]
    score, tri = triage(ok)
    assert round(score, 2) == 0.73 and tri == "yes"
    # a failed must-have blocks "yes" even above 70%
    blocked = [("must", "met")] * 5 + [("must", "not_met")] + [("nice", "met")]
    score, tri = triage(blocked)
    assert score > 0.70 and tri == "maybe"
    # just under 70% -> maybe
    low = [("must", "met")] * 2 + [("must", "partial")] * 3 + [("must", "not_evidenced")] + [("nice", "met")]
    assert triage(low)[1] == "maybe" and triage(low)[0] < 0.70


def test_anonymize_removes_the_whole_email_even_when_it_contains_the_name():
    """Regression: the name was replaced first, which broke the e-mail pattern and leaked the domain."""
    txt = "Jean DUPONT\nResponsable d'entrepôt\nVillefontaine (38) · 06 00 00 00 00 · jean.dupont@exemple-ecole.fr · Permis B\nhttps://linkedin.com/in/jean-dupont\n"
    a = anonymize(txt, {"name": "Jean DUPONT", "city": "Villefontaine"})
    for leak in ("exemple-ecole", "jean", "dupont@", "linkedin", "06 00"):
        assert leak not in a.lower(), (leak, a)
    assert "[EMAIL]" in a and "Responsable d'entrepôt" in a
