import os
import re
from dataclasses import dataclass

import yaml


@dataclass
class Config:
    obsidian_vault_path: str
    brief_folder: str
    rss_sources: list[dict]
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    domains: list[str]
    slack_webhook: str | None = None


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

    return Config(
        obsidian_vault_path=os.path.expanduser(obsidian["vault_path"]),
        brief_folder=obsidian["brief_folder"],
        rss_sources=raw.get("sources", {}).get("rss", []),
        llm_api_key=_substitute_env(llm["api_key"]),
        llm_base_url=llm["base_url"],
        llm_model=llm["model"],
        domains=raw.get("domains", []),
        slack_webhook=notify.get("slack_webhook"),
    )
