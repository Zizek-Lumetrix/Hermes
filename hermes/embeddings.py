from pathlib import Path
from sentence_transformers import SentenceTransformer
import numpy as np


class EmbeddingIndex:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.paths: list[str] = []
        self.embeddings: np.ndarray | None = None

    def build(self, vault_path: str) -> None:
        vault = Path(vault_path).expanduser()
        if not vault.exists():
            self.paths = []
            self.embeddings = None
            return

        md_files = list(vault.rglob("*.md"))
        texts = []
        paths = []

        for f in md_files:
            try:
                content = f.read_text()
                if content.strip():
                    texts.append(content[:2000])
                    paths.append(str(f.relative_to(vault)))
            except Exception:
                continue

        if texts:
            self.embeddings = self.model.encode(texts)
            self.paths = paths
        else:
            self.embeddings = None
            self.paths = []

    def query(self, text: str, top_k: int = 3) -> list[tuple[str, float]]:
        if self.embeddings is None or len(self.paths) == 0:
            return []

        query_vec = self.model.encode([text])[0]
        similarities = np.dot(self.embeddings, query_vec) / (
            np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_vec)
        )
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        results = []
        for idx in top_indices:
            if similarities[idx] > 0.3:
                results.append((self.paths[idx], float(similarities[idx])))
        return results
