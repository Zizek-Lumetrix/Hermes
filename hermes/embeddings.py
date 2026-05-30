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


class StreamingClusterer:
    def __init__(self, distance_threshold: float = 0.5):
        self.threshold = distance_threshold
        self.centroids: list[np.ndarray] = []

    def assign(self, embedding: list[float]) -> int:
        vec = np.array(embedding, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

        if not self.centroids:
            self.centroids.append(vec)
            return 0

        best_cluster = 0
        best_sim = -1.0
        for i, c in enumerate(self.centroids):
            sim = float(np.dot(vec, c))
            if sim > best_sim:
                best_sim = sim
                best_cluster = i

        if (1.0 - best_sim) <= self.threshold:
            alpha = 0.1
            self.centroids[best_cluster] = self._normalize(
                (1 - alpha) * self.centroids[best_cluster] + alpha * vec
            )
            return best_cluster
        else:
            self.centroids.append(vec)
            return len(self.centroids) - 1

    def cold_start(self, embeddings: list[list[float]]) -> None:
        if not embeddings:
            return
        for emb in embeddings:
            self.assign(emb)

    @staticmethod
    def _normalize(vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec
