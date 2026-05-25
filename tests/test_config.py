import tempfile
import os
from pathlib import Path
from hermes.config import load_config


def test_load_config_parses_yaml():
    yaml = """
obsidian:
  vault_path: ~/test-vault
  brief_folder: Briefs
sources:
  rss:
    - url: https://foo.com/rss
      name: Foo Blog
llm:
  api_key: sk-test
  base_url: https://api.deepseek.com
  model: deepseek-chat
domains:
  - AI
notify:
  slack_webhook: null
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name

    try:
        config = load_config(path)
        assert config.obsidian_vault_path == os.path.expanduser("~/test-vault")
        assert config.brief_folder == "Briefs"
        assert len(config.rss_sources) == 1
        assert config.rss_sources[0]["url"] == "https://foo.com/rss"
        assert config.llm_api_key == "sk-test"
        assert config.llm_model == "deepseek-chat"
        assert config.domains == ["AI"]
        assert config.slack_webhook is None
    finally:
        os.unlink(path)


def test_load_config_substitutes_env_vars(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "secret-123")
    yaml = """
obsidian:
  vault_path: /tmp/v
  brief_folder: B
sources:
  rss: []
llm:
  api_key: ${TEST_KEY}
  base_url: https://x.com
  model: m
domains: []
notify:
  slack_webhook: null
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        config = load_config(path)
        assert config.llm_api_key == "secret-123"
    finally:
        os.unlink(path)
