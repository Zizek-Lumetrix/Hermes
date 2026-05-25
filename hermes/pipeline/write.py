import json
import os
from datetime import date, datetime
from pathlib import Path

import frontmatter


def scan_feedback(vault_path: str, brief_folder: str) -> list[dict]:
    brief_dir = Path(vault_path) / brief_folder
    if not brief_dir.exists():
        return []

    feedback = []
    for f in brief_dir.glob("*.md"):
        try:
            post = frontmatter.load(f)
            if post.get("type") == "intel-brief" and "rating" in post:
                feedback.append({
                    "brief_date": str(post.get("date", "")),
                    "rating": post["rating"],
                })
        except Exception:
            continue

    return feedback


def write_brief(items: list[dict], vault_path: str, brief_folder: str) -> str:
    brief_dir = Path(vault_path) / brief_folder
    brief_dir.mkdir(parents=True, exist_ok=True)

    today = date.today()
    filename = f"Intel Brief – {today.isoformat()}.md"
    filepath = brief_dir / filename

    high_items = [i for i in items if i.get("relevance_score", 0) >= 7]
    mid_items = [i for i in items if 4 <= i.get("relevance_score", 0) <= 6]
    low_items = [i for i in items if 3 <= i.get("relevance_score", 0) <= 3]

    lines = [
        "---",
        f"date: {today}",
        "type: intel-brief",
        "---",
        "",
        f"# 今日情报 · {today}",
        "",
    ]

    if not items:
        lines.append("今日无重要情报。")
        filepath.write_text("\n".join(lines))
        return str(filepath)

    def _render_section(label: str, icon: str, item_list: list[dict]) -> None:
        if not item_list:
            return
        lines.append(f"## {icon} {label}（{len(item_list)}条）")
        lines.append("")
        for item in item_list:
            try:
                analysis = json.loads(item.get("analysis", "{}"))
            except (json.JSONDecodeError, TypeError):
                analysis = {}

            title = analysis.get("title_cn", item.get("title", "Untitled"))
            lines.append(f"### {title}")
            lines.append("")
            lines.append(f"> 来源：[{item.get('source', 'Unknown')}]({item.get('url', '')})")
            lines.append("")

            if analysis.get("confidence") == "low":
                lines.append("⚠️ **信源未充分验证，请交叉确认**")
                lines.append("")

            lines.append(analysis.get("summary", ""))
            lines.append("")

            key_points = analysis.get("key_points", [])
            if key_points:
                for kp in key_points:
                    lines.append(f"- {kp}")
                lines.append("")

            implications = analysis.get("implications", "")
            if implications:
                lines.append(f"**启示**：{implications}")
                lines.append("")

            linked = item.get("linked_notes", [])
            if linked:
                if isinstance(linked, str):
                    try:
                        linked = json.loads(linked)
                    except (json.JSONDecodeError, TypeError):
                        linked = []
                note_links = " · ".join(f"[[{n}]]" for n in linked)
                lines.append(f"→ 关联笔记：{note_links}")
                lines.append("")

            lines.append("---")
            lines.append("")

    _render_section("高相关", "🔴", high_items)
    _render_section("中相关", "🟡", mid_items)
    _render_section("低相关", "🟢", low_items)

    filepath.write_text("\n".join(lines))
    return str(filepath)
