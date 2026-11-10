"""Mini eval: 6 given CVs with expected outcomes. Real LLM calls.   python -m evals.run_eval"""
import json
import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(ROOT))

from backend.app.db import SessionLocal, init_db  # noqa: E402
from backend.app.models import Candidate, Job  # noqa: E402
from backend.app.routers.jobs import extract_criteria, set_criteria  # noqa: E402
from backend.app.screening.pipeline import process_candidate  # noqa: E402

FIX = ROOT / "fixtures"
SURPRISE = "--surprise" in sys.argv
EXPECTED = json.loads((ROOT / "evals" / ("expected_surprise.json" if SURPRISE else "expected.json")).read_text())


def main() -> int:
    init_db()
    db = SessionLocal()
    ex = extract_criteria((FIX / "job_post.txt").read_text())
    job = Job(title=ex.title, ref=ex.ref, description=(FIX / "job_post.txt").read_text())
    db.add(job); db.flush(); set_criteria(db, job, ex.criteria); db.commit()
    print(f"Job: {job.title} — {len(job.criteria)} critères\n")

    ids = {}
    files = sorted((ROOT / "evals" / "cvs").glob("S*")) if SURPRISE else sorted(FIX.glob("CV 0*.docx"))
    for f in files:
        c = Candidate(job_id=job.id, filename=f.name, mime="", file_bytes=f.read_bytes())
        db.add(c); db.flush(); ids[f.name[:2] if SURPRISE else f.name[:5]] = c.id
    db.commit()

    t0 = time.time()
    with ThreadPoolExecutor(6) as pool:
        list(pool.map(process_candidate, ids.values()))
    print(f"Pipeline: {time.time() - t0:.0f}s pour {len(ids)} CV\n")

    failures = 0
    for key, cid in ids.items():
        db.expire_all()
        c = db.get(Candidate, cid)
        exp = EXPECTED[key]
        probs = []
        want_status = exp.get("status", "screened")
        if c.status != want_status:
            probs.append(f"status={c.status} (attendu {want_status}) {c.error}")
        elif want_status == "failed":
            pass
        elif want_status == "screened":
            if c.triage not in exp["triage"]:
                probs.append(f"triage {c.triage} ∉ {exp['triage']}")
            if c.injection_flag != exp["injection"]:
                probs.append(f"injection {c.injection_flag} != {exp['injection']}")
            if "lang" in exp and not c.lang.startswith(exp["lang"]):
                probs.append(f"lang {c.lang} != {exp['lang']}")
            by_label = {k.id: k.label.lower() for k in job.criteria}
            for e in c.evaluations:
                if e.verdict != "not_evidenced" and not e.quote_verified:
                    probs.append(f"quote non vérifiée: {by_label[e.criterion_id]}")
                for kw, allowed in exp.get("verdicts", {}).items():
                    if kw in by_label[e.criterion_id] and e.verdict not in allowed:
                        probs.append(f"{by_label[e.criterion_id]}: {e.verdict} ∉ {allowed}")
        ok = not probs
        failures += 0 if ok else 1
        p = c.profile or {}
        print(f"{'✅' if ok else '❌'} {key} {(p.get('name') or c.filename)[:18]:18} {c.status:9} triage={c.triage or '-':5} "
              f"score={(c.cv_score or 0):.2f} inj={c.injection_flag!s:5} lang={c.lang} {('· ' + c.error[:60]) if c.error else ''}")
        for p_ in probs:
            print(f"      ↳ {p_}")
        if os.environ.get("VERBOSE"):
            by = {k.id: k.label for k in job.criteria}
            for e in c.evaluations:
                print(f"      {e.verdict:13} {by[e.criterion_id][:28]:28} “{e.quote[:70]}”")
    print(f"\n{len(ids) - failures}/{len(ids)} OK")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
