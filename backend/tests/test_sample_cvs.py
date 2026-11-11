"""The real sample data: the six CVs of the brief and the eight trap CVs (offline: parsing, anonymization, injection net)."""
import re
from pathlib import Path

import pytest

from backend.app.cv.anonymize import anonymize
from backend.app.cv.parse import parse_cv
from backend.app.screening.pipeline import _INJ_RE

ROOT = Path(__file__).resolve().parents[2]
BRIEF = {"01": "Karim Benali", "02": "Léa Fontaine", "03": "Thomas Rey",
         "04": "Inès Morel", "05": "Paul Vasseur", "06": "Ana Ribeiro"}
SAMPLES = sorted((ROOT / "fixtures").glob("CV *.docx")) + sorted((ROOT / "evals" / "cvs").glob("*"))


def _parse(f: Path):
    return parse_cv(f.read_bytes(), f.name)


@pytest.mark.parametrize("num,name", sorted(BRIEF.items()))
def test_no_name_or_contact_leaks_after_anonymization(num, name):
    f = next((ROOT / "fixtures").glob(f"CV {num} - *.docx"))
    text = _parse(f).text
    a = anonymize(text, {"name": name, "city": ""})
    for part in name.split():
        assert not re.search(rf"(?<!\w){re.escape(part)}(?!\w)", a, re.I), (part, f.name)
    assert "@" not in a and "[EMAIL]" in a and "[TÉLÉPHONE]" in a


def test_injection_net_flags_exactly_the_two_trap_cvs():
    flagged = set()
    for f in SAMPLES:
        p = _parse(f)
        if _INJ_RE.search(p.text + "\n" + "\n".join(p.hidden)):
            flagged.add(f.name)
    assert flagged == {"CV 05 - Paul Vasseur.docx", "S2 - Chloe Martin (hidden injection).pdf"}, flagged


def test_every_sample_file_parses():
    assert len(SAMPLES) == 14
    for f in SAMPLES:
        p = _parse(f)
        if f.suffix == ".png" or "vide" in f.name:
            assert p.needs_vision or not p.text.strip(), f.name     # scan / empty: goes to vision or fails cleanly
        else:
            assert len(p.text) > 80, f.name
