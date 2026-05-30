import os
import re
from dataclasses import dataclass

import yaml


@dataclass
class RSSSource:
    url: str
    name: str
    enabled: bool = True


@dataclass
class Config:
    obsidian_vault_path: str
    brief_folder: str
    rss_sources: list[RSSSource]
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    domains: list[str]
    slack_webhook: str | None = None
    db_url: str = "postgresql://localhost:5432/hermes"
    email_smtp_host: str = "localhost"
    email_smtp_port: int = 587
    email_from: str = "hermes@localhost"
    email_to: str = "user@localhost"
    email_password: str | None = None
    exploit_threshold: int = 5
    enrich_cluster_distance: float = 0.5


def _substitute_env(value: str) -> str:
    pattern = re.compile(r"\$\{(\w+)\}")
    matches = pattern.findall(value)
    for var in matches:
        env_val = os.environ.get(var, "")
        value = value.replace(f"${{{var}}}", env_val)
    return value


def load_config(path: str | None = None) -> Config:
    if path is None:
        path = os.path.expanduser("~/.hermes/config.yaml")

    with open(path) as f:
        raw = yaml.safe_load(f)

    llm = raw["llm"]
    obsidian = raw["obsidian"]
    notify = raw.get("notify", {})
    db_cfg = raw.get("database", {})
    email_cfg = raw.get("email", {})
    scoring = raw.get("scoring", {})

    rss_raw = raw.get("sources", {}).get("rss", [])
    rss_sources = [RSSSource(**s) for s in rss_raw]

    return Config(
        obsidian_vault_path=os.path.expanduser(obsidian["vault_path"]),
        brief_folder=obsidian["brief_folder"],
        rss_sources=rss_sources,
        llm_api_key=_substitute_env(llm["api_key"]),
        llm_base_url=llm["base_url"],
        llm_model=llm["model"],
        domains=raw.get("domains", []),
        slack_webhook=notify.get("slack_webhook"),
        db_url=db_cfg.get("url", "postgresql://localhost:5432/hermes"),
        email_smtp_host=email_cfg.get("smtp_host", "localhost"),
        email_smtp_port=email_cfg.get("smtp_port", 587),
        email_from=email_cfg.get("from_addr", "hermes@localhost"),
        email_to=email_cfg.get("to_addr", "user@localhost"),
        email_password=email_cfg.get("password"),
        exploit_threshold=scoring.get("exploit_threshold", 5),
        enrich_cluster_distance=scoring.get("enrich_cluster_distance", 0.5),
    )
