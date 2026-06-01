import numpy as np


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
