import tempfile
import os
import json
from pathlib import Path
from datetime import date
from hermes.pipeline.write import write_brief, scan_feedback


def test_write_brief_creates_markdown_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        items = [
            {
                "id": "abc",
                "title": "GPT-5 Release",
                "url": "https://example.com/gpt5",
                "source": "Tech Blog",
                "relevance_score": 9,
                "analysis": json.dumps({
                    "title_cn": "GPT-5发布",
                    "summary": "OpenAI发布了GPT-5，在推理和编程任务上大幅提升。",
                    "key_points": ["推理提升30%", "编程能力超人类"],
                    "implications": "开发者应考虑升级到新模型",
                    "confidence": "high",
                }),
                "linked_notes": ["AI趋势.md", "GPT模型.md"],
            },
            {
                "id": "xyz",
                "title": "Minor Update",
                "url": "https://example.com/minor",
                "source": "Other Blog",
                "relevance_score": 4,
                "analysis": json.dumps({
                    "title_cn": "小更新",
                    "summary": "某公司发布了小版本更新。",
                    "key_points": ["bug修复"],
                    "implications": "无重大影响",
                    "confidence": "high",
                }),
                "linked_notes": [],
            },
        ]

        brief_path = write_brief(items, tmpdir, "Briefs")

        assert os.path.exists(brief_path)
        content = Path(brief_path).read_text()

        # Check frontmatter
        assert "type: intel-brief" in content
        assert str(date.today().year) in content

        # Check sections
        assert "高相关" in content
        assert "中相关" in content

        # Check the high-relevance item is present
        assert "GPT-5发布" in content
        assert "OpenAI发布了GPT-5" in content

        # Check wiki links
        assert "[[AI趋势.md]]" in content
        assert "[[GPT模型.md]]" in content

        # Check that items are in correct sections
        high_section_start = content.index("高相关")
        mid_section_start = content.index("中相关")
        assert content.index("GPT-5发布") < mid_section_start
        assert content.index("小更新") > mid_section_start


def test_write_brief_low_confidence_gets_warning():
    with tempfile.TemporaryDirectory() as tmpdir:
        items = [
            {
                "id": "low1",
                "title": "Rumor",
                "url": "https://x.com/r",
                "source": "Twitter",
                "relevance_score": 6,
                "analysis": json.dumps({
                    "title_cn": "传闻",
                    "summary": "某传闻称...",
                    "key_points": ["未证实的消息"],
                    "implications": "如果属实则有影响",
                    "confidence": "low",
                }),
                "linked_notes": [],
            }
        ]

        brief_path = write_brief(items, tmpdir, "Briefs")
        content = Path(brief_path).read_text()
        assert "信源未充分验证" in content


def test_write_brief_empty_items():
    with tempfile.TemporaryDirectory() as tmpdir:
        brief_path = write_brief([], tmpdir, "Briefs")
        content = Path(brief_path).read_text()
        assert "今日无重要情报" in content


def test_scan_feedback():
    with tempfile.TemporaryDirectory() as tmpdir:
        brief_dir = Path(tmpdir) / "Briefs"
        brief_dir.mkdir()
        brief_content = """---
date: 2026-05-21
type: intel-brief
rating: 2
---
# 昨日情报
内容...
"""
        (brief_dir / "Intel Brief – 2026-05-21.md").write_text(brief_content)

        # Create another without rating
        (brief_dir / "Intel Brief – 2026-05-20.md").write_text(
            "---\ndate: 2026-05-20\ntype: intel-brief\n---\n# 内容"
        )

        feedback = scan_feedback(str(tmpdir), "Briefs")
        assert len(feedback) == 1
        assert feedback[0]["rating"] == 2
