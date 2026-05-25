import hashlib
import uuid
from hermes.ingestors.rss import RawItem


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def compute_simhash(text: str, bits: int = 64) -> str:
    tokens = _tokenize(text)
    vector = [0.0] * bits

    for idx, token in enumerate(tokens):
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        weight = 1.0 / ((idx + 1) ** 2)
        for i in range(bits):
            if h & (1 << i):
                vector[i] += weight
            else:
                vector[i] -= weight

    fingerprint = 0
    for i in range(bits):
        if vector[i] > 0:
            fingerprint |= (1 << i)

    return format(fingerprint, "016x")


def hamming_distance(a: str, b: str) -> int:
    a_int = int(a, 16)
    b_int = int(b, 16)
    xor = a_int ^ b_int
    return xor.bit_count()


def dedup_items(items: list[RawItem], existing_urls: set[str]) -> list[RawItem]:
    for item in items:
        prefix = item.content[:500] if item.content else item.title
        item.simhash = compute_simhash(prefix)

    clusters: dict[str, list[RawItem]] = {}
    assigned = set()

    for i, item in enumerate(items):
        if i in assigned:
            continue
        cluster_key = item.simhash
        clusters[cluster_key] = [item]
        for j in range(i + 1, len(items)):
            if j in assigned:
                continue
            other = items[j]
            if hamming_distance(item.simhash, other.simhash) <= 3:
                clusters[cluster_key].append(other)
                assigned.add(j)

    for cluster_items in clusters.values():
        cluster_id = str(uuid.uuid4())[:8]
        for item in cluster_items:
            item.cluster_id = cluster_id

    return items
