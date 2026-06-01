import os
import numpy as np
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


_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        config = get_config()
        _db = Database(config.db_url)
    return _db


def _db_ok():
    try:
        db = get_db()
        db.get_last_successful_run()
        return True
    except Exception:
        global _db
        _db = None
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


def _cosine_sim(a, b):
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


@app.get("/api/graph")
def get_graph(cross_domain_threshold: float = 0.4):
    if not _db_ok():
        return {"nodes": [], "edges": []}
    db = get_db()
    conclusions = db.get_all_conclusions()
    nodes = []
    emb_map: dict[str, list[float]] = {}
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
        emb = c.get("embedding")
        if emb is not None:
            emb_map[c["id"]] = emb

    domains_seen = sorted({n["domain"] for n in nodes if n.get("domain")})

    edges = []
    for i, n1 in enumerate(nodes):
        for j, n2 in enumerate(nodes):
            if i >= j:
                continue
            if n1["id"] not in emb_map or n2["id"] not in emb_map:
                continue
            sim = _cosine_sim(emb_map[n1["id"]], emb_map[n2["id"]])
            if sim >= cross_domain_threshold:
                edges.append({
                    "source": n1["id"], "target": n2["id"],
                    "type": "cross_domain",
                    "strength": round(sim, 2),
                })

    return {"nodes": nodes, "edges": edges, "domains": domains_seen}


def _serialize_row(row, drop_fields=("embedding",)):
    """Convert a RealDictRow to a plain dict, stripping numpy arrays."""
    if row is None:
        return None
    out = {}
    for k, v in dict(row).items():
        if k in drop_fields:
            continue
        if hasattr(v, "tolist"):
            v = v.tolist()
        out[k] = v
    return out


@app.get("/api/graph/conclusion/{conclusion_id}")
def get_conclusion_detail(conclusion_id: str):
    if not _db_ok():
        return {"error": "database unavailable"}, 503
    db = get_db()
    conclusion = db.get_conclusion(conclusion_id)
    if not conclusion:
        return {"error": "not found"}, 404
    versions = db.get_conclusion_versions(conclusion_id)
    versions_out = [_serialize_row(v) for v in versions]

    # Collect supporting items from version history
    item_ids = set()
    for v in versions:
        triggered = v.get("triggered_by")
        if triggered:
            for t in triggered:
                item_ids.add(t.get("item_id", ""))

    items_out = []
    seen_ids = set()
    for short_id in item_ids:
        rows = db._query(
            "SELECT id, title, url, source, domain, domain_proposed, analysis, entities, exploit_score, "
            "published_at FROM items WHERE id LIKE %s || '%%'",
            (short_id,),
        )
        for r in rows:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                items_out.append(_serialize_row(r))

    # Also fetch domain-related items (scored items in the same domain, for broader context)
    domain_items = []
    if conclusion.get("domain"):
        domain_rows = db._query(
            "SELECT id, title, url, source, domain, domain_proposed, analysis, entities, exploit_score, "
            "published_at FROM items WHERE status IN ('assessed', 'incorporated') "
            "AND domain = %s ORDER BY exploit_score DESC LIMIT 30",
            (conclusion["domain"],),
        )
        for r in domain_rows:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                domain_items.append(_serialize_row(r))

    # Extract counter_evidence from latest version's change_description
    counter_evidence = ""
    if versions_out:
        latest = versions_out[-1]
        desc = latest.get("change_description") or ""
        if "反对意见:" in desc:
            counter_evidence = desc.split("反对意见:", 1)[1].strip()

    return {
        "conclusion": _serialize_row(conclusion),
        "versions": versions_out,
        "counter_evidence": counter_evidence,
        "items": items_out,
        "related_items": domain_items,
    }


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


@app.get("/api/surprise")
def get_surprise(limit: int = Query(20, le=50)):
    if not _db_ok():
        return []
    db = get_db()
    rows = db._query(
        "SELECT id, title, source, url, domain, domain_proposed, analysis, entities, exploit_score, "
        "surprise_score, published_at FROM items "
        "WHERE status IN ('assessed', 'incorporated') AND surprise_score > 0.5 "
        "ORDER BY surprise_score DESC LIMIT %s",
        (limit,),
    )
    return [_serialize_row(r) for r in rows]


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


@app.get("/api/domains")
def get_domains():
    config = get_config()
    configured = config.domains
    if not _db_ok():
        return {"configured": configured, "proposed": []}
    db = get_db()
    rows = db._query(
        "SELECT DISTINCT domain, domain_proposed FROM items "
        "WHERE domain IS NOT NULL AND domain != '' AND domain_proposed IS NOT NULL AND domain_proposed != ''"
    )
    proposed = [{"matched": r["domain"], "proposed": r["domain_proposed"]} for r in rows]
    return {"configured": configured, "proposed": proposed}


@app.get("/api/health")
def health():
    try:
        db = get_db()
        db.get_last_successful_run()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
