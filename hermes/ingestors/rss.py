import hashlib
import re
from dataclasses import dataclass

import feedparser
import html2text


@dataclass
class RawItem:
    id: str
    source: str
    title: str
    url: str
    content: str
    published_at: str | None
    simhash: str | None = None
    cluster_id: str | None = None


_html_cleaner = html2text.HTML2Text()
_html_cleaner.ignore_links = False
_html_cleaner.ignore_images = True
_html_cleaner.body_width = 0


def _clean_html(html: str) -> str:
    text = _html_cleaner.handle(html)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch_feed(url: str, name: str) -> list[RawItem]:
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries:
        content = entry.get("content", [{}])[0].get("value", "")
        if not content:
            content = entry.get("summary", entry.get("description", ""))
        content = _clean_html(content)

        link = entry.get("link", "")
        item_id = hashlib.sha256(link.encode()).hexdigest() if link else ""

        published = entry.get("published", entry.get("updated", None))

        items.append(RawItem(
            id=item_id,
            source=name,
            title=entry.get("title", "Untitled"),
            url=link,
            content=content,
            published_at=published,
        ))
    return items
