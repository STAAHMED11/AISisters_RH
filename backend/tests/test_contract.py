"""Contract between the two halves of the app: every API call written in the frontend must hit a Flask route."""
import re
from pathlib import Path

from werkzeug.exceptions import MethodNotAllowed, NotFound

from backend.app.main import app

SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"
CALL = re.compile(r"api(?:<[^>]*>)?\(\s*([`'])(.*?)\1\s*(?:,\s*\{([^}]*)\})?")


def frontend_calls() -> list[tuple[str, str, str]]:
    calls = []
    for f in sorted(SRC.rglob("*.ts*")):
        for m in CALL.finditer(f.read_text(encoding="utf-8")):
            path, opts = m.group(2), m.group(3) or ""
            method = (re.search(r"method:\s*'(\w+)'", opts) or [None, "GET"])[1]
            path = re.sub(r"\$\{[^}]*token[^}]*\}", "t" * 30, path)       # interview token
            path = re.sub(r"\$\{[^}]+\}", "1", path).split("?")[0]          # ids
            calls.append((method, "/api" + path, str(f.relative_to(SRC))))
    return calls


def test_every_frontend_api_call_has_a_backend_route():
    calls = frontend_calls()
    assert len(calls) > 30, "the scan found too few calls: the regex no longer matches api(...)"
    adapter = app.url_map.bind("localhost")
    broken = []
    for method, path, where in calls:
        try:
            adapter.match(path, method=method)
        except (NotFound, MethodNotAllowed) as e:
            broken.append(f"{method} {path} ({where}): {type(e).__name__}")
    assert not broken, "\n".join(broken)
