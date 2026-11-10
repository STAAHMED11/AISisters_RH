"""Deploy on Modal — one always-warm container (SQLite => single writer).

    pip install modal && modal setup
    (cd frontend && npm ci && npm run build)
    modal secret create orvane-secrets --from-dotenv .env
    modal deploy modal_deploy.py        # prints the URL, e.g. https://<workspace>--orvane-rh.us-east.modal.run
    (then put that exact URL in PUBLIC_URL: modal secret create orvane-secrets --from-dotenv .env PUBLIC_URL=<url> --force, and redeploy)
"""
import modal

app = modal.App("orvane-rh")
data_vol = modal.Volume.from_name("orvane-data", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements("backend/requirements.txt")   # baked into the image: no install at start
    .env({"DATA_DIR": "/data", "DB_JOURNAL": "DELETE", "PYTHONUNBUFFERED": "1"})
    .add_local_dir("backend", remote_path="/app/backend")
    .add_local_dir("frontend/dist", remote_path="/app/frontend/dist")
    .add_local_dir("evals", remote_path="/app/evals")
    .add_local_dir("fixtures", remote_path="/app/fixtures")
)


@app.function(
    image=image,
    cpu=2.0,
    memory=2048,
    volumes={"/data": data_vol},
    secrets=[modal.Secret.from_name("orvane-secrets")],
    timeout=1800,
    min_containers=1,        # always warm: no cold start / init delay during the demo
    max_containers=1,        # SQLite => exactly one writer
    scaledown_window=1800,
)
@modal.concurrent(max_inputs=64)
@modal.asgi_app(label="orvane-rh")
def web():
    import sys
    import threading
    import time

    sys.path.insert(0, "/app")
    from backend.app.db import init_db
    from backend.app.main import app as fastapi_app

    init_db()  # tables ready before the first request

    def _commit_loop():  # persist SQLite writes to the Volume every few seconds
        while True:
            time.sleep(5)
            try:
                data_vol.commit()
            except Exception:
                pass

    threading.Thread(target=_commit_loop, daemon=True).start()
    return fastapi_app
