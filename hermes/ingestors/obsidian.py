import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VaultItem:
    id: str
    source: str
    title: str
    url: str
    content: str
    published_at: str | None


def read_vault(vault_path: str) -> list[VaultItem]:
    vault = Path(vault_path).expanduser()
    if not vault.exists():
        return []

    items = []
    for f in vault.rglob("*.md"):
        if ".obsidian" in f.parts:
            continue
        try:
            content = f.read_text()
            if not content.strip():
                continue
        except Exception:
            continue

        # Extract title: first # heading, or filename stem
        title = f.stem
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                title = stripped[2:].strip()
                break

        rel_path = str(f.relative_to(vault))
        item_id = hashlib.sha256(rel_path.encode()).hexdigest()
        from datetime import datetime, timezone
        mtime = f.stat().st_mtime
        published_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

        items.append(VaultItem(
            id=item_id,
            source=f"vault:{rel_path}",
            title=title,
            url=f"obsidian://{rel_path}",
            content=content[:10000],
            published_at=published_at,
        ))

    return items
