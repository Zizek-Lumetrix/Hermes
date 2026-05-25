import json
import tempfile
import os
from unittest.mock import MagicMock, patch
from pathlib import Path
from openai import OpenAI

from hermes.config import Config
from hermes.db import Database


def test_full_pipeline_with_mocks(monkeypatch, tmp_path):
    """Simulate a full pipeline run with mocked RSS and LLM."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "existing_note.md").write_text(
        "AI安全 对齐技术 大型语言模型 安全研究综述"
    )
    brief_dir = vault / "Briefs"
    brief_dir.mkdir()

    # Mock RSS feed
    SAMPLE_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item>
  <title>New AI Safety Paper Released</title>
  <link>https://example.com/ai-safety</link>
  <description>Researchers published a comprehensive survey of AI alignment techniques.</description>
</item>
<item>
  <title>Local Weather Update</title>
  <link>https://example.com/weather</link>
  <description>Partly cloudy with a high of 72.</description>
</item>
</channel></rss>"""

    import feedparser
    original_parse = feedparser.parse
    def mock_parse(url):
        return original_parse(SAMPLE_XML)
    monkeypatch.setattr("feedparser.parse", mock_parse)

    # Mock LLM responses - need separate responses for filter (2 items) + analyze (1 item)
    mock_client = MagicMock()

    filter_good = MagicMock()
    filter_good.choices = [
        MagicMock(message=MagicMock(content='{"score": 8, "reason": "直接相关AI安全"}'))
    ]

    filter_bad = MagicMock()
    filter_bad.choices = [
        MagicMock(message=MagicMock(content='{"score": 0, "reason": ""}'))
    ]

    analyze_good = MagicMock()
    analyze_good.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "title_cn": "AI安全综述论文发布",
            "summary": "研究者发布了AI对齐技术的综合综述。",
            "key_points": ["涵盖50+种技术", "基准测试结果积极"],
            "implications": "从业者应关注对齐技术的最新进展",
            "confidence": "high",
        })))
    ]

    mock_client.chat.completions.create.side_effect = [
        filter_good, filter_bad, analyze_good,
    ]

    # Write config
    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"""
obsidian:
  vault_path: {vault}
  brief_folder: Briefs
sources:
  rss:
    - url: https://example.com/feed.xml
      name: Test Feed
llm:
  api_key: sk-test
  base_url: https://api.deepseek.com
  model: deepseek-chat
domains:
  - AI安全
  - 大模型
notify:
  slack_webhook: null
""")

    # Patch DB path
    db_path = tmp_path / "test.db"

    import hermes.pipeline.run as run_module
    monkeypatch.setattr(run_module, "_get_db_path", lambda: str(db_path))

    # Patch the OpenAI client constructor
    original_init = OpenAI.__init__

    def mock_openai_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.chat = mock_client.chat

    monkeypatch.setattr(OpenAI, "__init__", mock_openai_init)

    # Run the pipeline
    run_module.run(str(config_path))

    # Verify outputs
    db = Database(str(db_path))
    items = db.get_items_by_status("written")
    assert len(items) == 1
    assert "ai safety" in items[0]["title"].lower()

    # Check brief file was created
    import datetime
    today = datetime.date.today().isoformat()
    brief_path = brief_dir / f"Intel Brief – {today}.md"
    assert brief_path.exists()

    content = brief_path.read_text()
    assert "AI安全综述" in content
    assert "高相关" in content
    assert "existing_note.md" in content  # auto-linked!
