"""Create the demo job from Sylvie's job post and screen the 6 given CVs (real LLM calls, ~30 s).
    .venv/bin/python scripts/seed_demo.py
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.db import SessionLocal, init_db  # noqa: E402
from backend.app.models import Candidate, Job  # noqa: E402
from backend.app.routers.jobs import extract_criteria, set_criteria  # noqa: E402
from backend.app.screening.pipeline import process_candidate  # noqa: E402

init_db()
db = SessionLocal()
text = (ROOT / "fixtures" / "job_post.txt").read_text()
ex = extract_criteria(text)
job = Job(title=ex.title, ref=ex.ref, description=text)
db.add(job); db.flush(); set_criteria(db, job, ex.criteria); db.commit()
ids = []
for f in sorted((ROOT / "fixtures").glob("CV 0*.docx")):
    c = Candidate(job_id=job.id, filename=f.name, file_bytes=f.read_bytes())
    db.add(c); db.flush(); ids.append(c.id)
db.commit()
with ThreadPoolExecutor(6) as pool:
    list(pool.map(process_candidate, ids))
db.expire_all()
for i in ids:
    c = db.get(Candidate, i)
    print(f"{(c.profile or {}).get('name', c.filename):18} {c.triage or '-':5} {c.cv_score or 0:.2f} {c.status}")
print(f"\nJob #{job.id} ready: open /jobs/{job.id}/candidates")
