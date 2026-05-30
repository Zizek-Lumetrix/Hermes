import os
from functools import lru_cache

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from hermes.db import Database
from hermes.config import load_config


@lru_cache()
def get_config():
    config_path = os.environ.get("HERMES_CONFIG", os.path.expanduser("~/.hermes/config.yaml"))
    return load_config(config_path)


@lru_cache()
def get_db() -> Database:
    config = get_config()
    return Database(config.db_url)


def _db_ok():
    try:
        db = get_db()
        db.get_last_successful_run()
        return True
    except Exception:
        return False


app = FastAPI(title="Hermes", version="2.0.0")

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    with open(os.path.join(template_dir, "index.html")) as f:
        return f.read()


@app.get("/api/graph")
def get_graph():
    if not _db_ok():
        return {"nodes": [], "edges": []}
    db = get_db()
    conclusions = db.get_all_conclusions()
    nodes = []
    for c in conclusions:
        versions = db.get_conclusion_versions(c["id"])
        nodes.append({
            "id": c["id"],
            "type": "conclusion",
            "label": c["statement"][:80],
            "domain": c.get("domain"),
            "confidence": c.get("confidence"),
            "user_confirmation": c.get("user_confirmation"),
            "status": c.get("status"),
            "version_count": len(versions),
            "created_at": str(c.get("created_at", "")),
        })

    edges = []
    for i, n1 in enumerate(nodes):
        for j, n2 in enumerate(nodes):
            if i >= j:
                continue
            if n1.get("domain") and n2.get("domain") and n1["domain"] == n2["domain"]:
                edges.append({"source": n1["id"], "target": n2["id"], "type": "same_domain"})

    return {"nodes": nodes, "edges": edges}


@app.get("/api/graph/conclusion/{conclusion_id}")
def get_conclusion_detail(conclusion_id: str):
    if not _db_ok():
        return {"error": "database unavailable"}, 503
    db = get_db()
    conclusion = db.get_conclusion(conclusion_id)
    if not conclusion:
        return {"error": "not found"}, 404
    versions = db.get_conclusion_versions(conclusion_id)
    return {"conclusion": conclusion, "versions": versions}


@app.post("/api/graph/conclusion/{conclusion_id}/confirm")
def confirm_conclusion(conclusion_id: str, value: str = Query(...)):
    if value not in ("confirmed", "challenged"):
        return {"error": "value must be 'confirmed' or 'challenged'"}, 400
    db = get_db()
    db.confirm_conclusion(conclusion_id, value)
    return {"status": "ok"}


@app.get("/api/stream")
def get_stream(
    after: str | None = Query(None),
    type: str = Query("all"),
    limit: int = Query(50, le=100),
):
    if not _db_ok():
        return {"entries": []}
    db = get_db()
    rows = db._query(
        "SELECT run_id, stage, status, item_count, duration_ms, error, created_at "
        "FROM run_log ORDER BY created_at DESC LIMIT %s",
        (limit,),
    )
    entries = []
    for log in rows:
        entries.append({
            "type": "pipeline_event",
            "stage": log["stage"],
            "status": log["status"],
            "item_count": log.get("item_count", 0),
            "timestamp": str(log.get("created_at", "")),
        })
    return {"entries": entries}


@app.get("/api/predictions")
def get_predictions(status: str = Query("all")):
    if not _db_ok():
        return []
    db = get_db()
    return db.get_all_predictions(filter_status=status)


@app.get("/api/runs")
def get_runs():
    if not _db_ok():
        return []
    db = get_db()
    rows = db._query("SELECT * FROM run_log ORDER BY created_at DESC LIMIT 100")
    return rows


@app.get("/api/health")
def health():
    try:
        db = get_db()
        db.get_last_successful_run()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
