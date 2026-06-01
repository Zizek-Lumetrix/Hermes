from sentence_transformers import SentenceTransformer

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
    return _model


def enrich_items(items: list[dict], clusterer) -> list[dict]:
    if not items:
        return []

    model = _get_model()
    texts = []
    for item in items:
        title = item.get("title", "")
        content = item.get("content", "")[:2000]
        texts.append(f"{title}\n{content}")

    embeddings = model.encode(texts)

    for i, item in enumerate(items):
        emb = embeddings[i].tolist()
        item["embedding"] = emb
        item["implicit_cluster"] = clusterer.assign(emb)
        item["status"] = "enriched"

    return items
