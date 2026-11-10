"""CV file -> visible text + hidden text.

Hidden text (white font without a dark background, <=3pt font, Word "vanish") is split from the
visible text: the evaluator never sees it, the injection scan does.
"""
import io
import re
from dataclasses import dataclass, field

IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MIN_TEXT = 200  # below this a PDF is considered scanned -> vision
TINY_PT = 3.0


@dataclass
class Parsed:
    text: str = ""
    hidden: list[str] = field(default_factory=list)
    needs_vision: bool = False
    vision_mime: str = ""


class UnsupportedFile(Exception):
    pass


def _is_white(color) -> bool:
    if color is None:
        return False
    if isinstance(color, (int, float)):
        return color >= 0.97
    try:
        vals = list(color)
    except TypeError:
        return False
    if not vals:
        return False
    if len(vals) == 1:
        return vals[0] >= 0.97
    if len(vals) == 3:
        return all(v >= 0.97 for v in vals)
    if len(vals) == 4:  # CMYK
        return all(v <= 0.03 for v in vals)
    return False


def _is_dark_fill(color) -> bool:
    if color is None:
        return False
    try:
        vals = list(color) if not isinstance(color, (int, float)) else [color]
    except TypeError:
        return False
    if len(vals) == 1:
        return vals[0] < 0.7
    if len(vals) == 3:
        return sum(vals) / 3 < 0.7
    if len(vals) == 4:
        return vals[3] > 0.3 or sum(vals[:3]) / 3 > 0.3
    return False


def _clean(t: str) -> str:
    t = t.replace(" ", " ").replace("​", "")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _parse_pdf(data: bytes) -> Parsed:
    import pdfplumber

    visible_pages, hidden = [], []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages[:8]:
            rects = [r for r in page.rects if r.get("fill") and _is_dark_fill(r.get("non_stroking_color"))]

            def on_dark(ch) -> bool:
                cx, cy = (ch["x0"] + ch["x1"]) / 2, (ch["top"] + ch["bottom"]) / 2
                return any(r["x0"] <= cx <= r["x1"] and r["top"] <= cy <= r["bottom"] for r in rects)

            def is_hidden(ch) -> bool:
                if ch.get("size", 10) <= TINY_PT:
                    return True
                return _is_white(ch.get("non_stroking_color")) and not on_dark(ch)

            hid_chars = [c for c in page.chars if is_hidden(c)]
            if hid_chars:
                hidden.append("".join(c["text"] for c in hid_chars))
                ids = {id(c) for c in hid_chars}
                page = page.filter(lambda o: id(o) not in ids if o.get("object_type") == "char" else True)
            visible_pages.append(page.extract_text() or "")
    text = _clean("\n\n".join(visible_pages))
    return Parsed(text=text, hidden=[_clean(h) for h in hidden if h.strip()], needs_vision=len(text) < MIN_TEXT)


def _parse_docx(data: bytes) -> Parsed:
    import docx
    from docx.oxml.ns import qn
    from docx.shared import Pt

    d = docx.Document(io.BytesIO(data))
    visible, hidden = [], []

    def shaded(el) -> bool:
        """Is the run inside a paragraph / cell with a non-white shading? (white-on-dark = legit)"""
        while el is not None:
            for shd in el.findall(qn("w:pPr") + "/" + qn("w:shd")) + el.findall(qn("w:tcPr") + "/" + qn("w:shd")):
                fill = (shd.get(qn("w:fill")) or "").lower()
                if fill and fill not in ("auto", "ffffff"):
                    return True
            el = el.getparent()
        return False

    def run_hidden(run, para_el) -> bool:
        f = run.font
        if f.hidden:
            return True
        if f.size is not None and f.size <= Pt(TINY_PT):
            return True
        rgb = f.color.rgb if f.color is not None and f.color.type is not None else None
        if rgb is not None and str(rgb).lower() == "ffffff" and not shaded(para_el):
            return True
        return False

    def handle_par(p):
        vis, hid = [], []
        for r in p.runs:
            (hid if run_hidden(r, p._p) else vis).append(r.text)
        if "".join(vis).strip():
            visible.append("".join(vis))
        if "".join(hid).strip():
            hidden.append("".join(hid))

    for p in d.paragraphs:
        handle_par(p)
    for t in d.tables:
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    handle_par(p)
    for section in d.sections:
        for p in section.header.paragraphs + section.footer.paragraphs:
            handle_par(p)
    return Parsed(text=_clean("\n".join(visible)), hidden=[_clean(h) for h in hidden])


def parse_cv(data: bytes, filename: str, mime: str = "") -> Parsed:
    name = filename.lower()
    if mime == "application/pdf" or name.endswith(".pdf"):
        return _parse_pdf(data)
    if name.endswith(".docx") or mime.endswith("wordprocessingml.document"):
        return _parse_docx(data)
    if mime in IMAGE_MIMES or name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        m = mime if mime in IMAGE_MIMES else ("image/png" if name.endswith(".png") else "image/jpeg")
        return Parsed(needs_vision=True, vision_mime=m)
    if name.endswith((".txt", ".md")) or mime.startswith("text/"):
        return Parsed(text=_clean(data.decode("utf-8", errors="replace")))
    raise UnsupportedFile("Format non supporté (PDF, DOCX, TXT ou image).")
