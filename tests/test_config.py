import tempfile
import os
from pathlib import Path
from hermes.config import load_config


def test_load_config_with_pg_and_email(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("""
sources:
  rss:
    - url: https://example.com/feed.xml
      name: Test
llm:
  api_key: sk-test
  base_url: https://api.deepseek.com
  model: deepseek-chat
domains:
  - AI
database:
  url: postgresql://localhost:5432/hermes
email:
  smtp_host: smtp.example.com
  smtp_port: 587
  from_addr: hermes@example.com
  to_addr: user@example.com
scoring:
  exploit_threshold: 5
notify:
  slack_webhook: null
""")
    config = load_config(str(config_path))
    assert config.db_url == "postgresql://localhost:5432/hermes"
    assert config.email_smtp_host == "smtp.example.com"
    assert config.email_from == "hermes@example.com"
    assert config.email_to == "user@example.com"
    assert config.exploit_threshold == 5


def test_load_config_parses_yaml():
    yaml = """
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
        assert len(config.rss_sources) == 1
        assert config.rss_sources[0].url == "https://foo.com/rss"
        assert config.rss_sources[0].name == "Foo Blog"
        assert config.rss_sources[0].enabled is True
        assert config.llm_api_key == "sk-test"
        assert config.llm_model == "deepseek-chat"
        assert config.domains == ["AI"]
        assert config.slack_webhook is None
    finally:
        os.unlink(path)


def test_load_config_substitutes_env_vars(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "secret-123")
    yaml = """
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
