"""HTML version of the e-mails (the plain text is always sent too, as the multipart fallback)."""
import html
import re

BRAND, INK, MUTED, LINE = "#0B4F6C", "#0F1B24", "#5B6770", "#DADDD6"
_URL = re.compile(r"(https?://[^\s<]+)")


def _paragraphs(text: str) -> str:
    out = []
    for block in [b.strip() for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]:
        safe = html.escape(block).replace("\n", "<br>")
        safe = _URL.sub(lambda m: f'<a href="{m.group(1)}" style="color:{BRAND}">{m.group(1)}</a>', safe)
        out.append(f'<p style="margin:0 0 16px;line-height:1.6;color:{INK};font-size:15px">{safe}</p>')
    return "".join(out)


def build_html(body: str, *, cta_label: str | None = None, cta_url: str | None = None, note: str | None = None,
               lang: str = "fr") -> str:
    footer = ("You are receiving this message because you applied to a position at Groupe Orvane."
              if lang == "en" else "Vous recevez ce message car vous avez candidaté à un poste au Groupe Orvane.")
    button = ""
    if cta_label and cta_url:
        button = (f'<table role="presentation" cellspacing="0" cellpadding="0" style="margin:8px 0 20px"><tr><td style="background:{BRAND};border-radius:8px">'
                  f'<a href="{html.escape(cta_url)}" style="display:inline-block;padding:13px 24px;color:#fff;text-decoration:none;font-weight:600;font-size:15px">{html.escape(cta_label)}</a>'
                  "</td></tr></table>")
    note_html = (f'<p style="margin:0 0 8px;padding:10px 14px;background:#FFF6CC;border-radius:8px;color:{INK};font-size:14px">{html.escape(note)}</p>' if note else "")
    return f"""<!doctype html><html><body style="margin:0;background:#F2F3EF;font-family:Helvetica,Arial,sans-serif">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#F2F3EF"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="560" cellspacing="0" cellpadding="0" style="max-width:560px;background:#fff;border:1px solid {LINE};border-radius:12px;overflow:hidden">
<tr><td style="background:{BRAND};padding:18px 28px;color:#fff;font-size:17px;font-weight:700;letter-spacing:.2px">Groupe Orvane · Recrutement</td></tr>
<tr><td style="padding:28px 28px 8px">{_paragraphs(body)}{button}{note_html}</td></tr>
<tr><td style="padding:16px 28px 24px;border-top:1px solid {LINE};color:{MUTED};font-size:12px;line-height:1.5">{html.escape(footer)}</td></tr>
</table></td></tr></table></body></html>"""
