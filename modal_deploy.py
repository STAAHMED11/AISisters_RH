"""Deploy on Modal — one always-warm container running the SAME image as `docker compose` (Dockerfile):
Next.js UI on :3000 (public) + Flask API on :8000 (internal, reached through Next's /api proxy). SQLite => single writer.

    pip install modal && modal setup
    modal secret create orvane-secrets --from-dotenv .env
    modal deploy modal_deploy.py        # prints the URL, e.g. https://<workspace>--orvane-rh.us-east.modal.run
    (then put that exact URL in PUBLIC_URL: modal secret create orvane-secrets --from-dotenv .env PUBLIC_URL=<url> --force, and redeploy)
"""
import subprocess
import threading
import time

import modal

app = modal.App("orvane-rh")
data_vol = modal.Volume.from_name("orvane-data", create_if_missing=True)

# Built from the Dockerfile (Next.js standalone build + Python deps); .dockerignore keeps node_modules, .env, data out.
image = modal.Image.from_dockerfile("Dockerfile").env({"DB_JOURNAL": "DELETE"})  # network volume: no WAL


@app.function(
    image=image,
    cpu=2.0,
    memory=2048,
    volumes={"/data": data_vol},
    secrets=[modal.Secret.from_name("orvane-secrets")],
    timeout=1800,
    min_containers=1,        # always warm: no cold start during the demo
    max_containers=1,        # SQLite => exactly one writer
    scaledown_window=1800,
)
@modal.concurrent(max_inputs=64)
@modal.web_server(3000, startup_timeout=120, label="orvane-rh")
def web():
    subprocess.Popen(["/app/start.sh"])  # gunicorn (Flask) + node server.js (Next.js)

    def _commit_loop():  # persist SQLite writes to the Volume every few seconds
        while True:
            time.sleep(5)
            try:
                data_vol.commit()
            except Exception:
                pass

    threading.Thread(target=_commit_loop, daemon=True).start()
