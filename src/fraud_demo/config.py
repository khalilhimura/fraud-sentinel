"""Configuration loading and hashing helpers."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class RuleDefinition(BaseModel):
    """One configurable fraud rule definition."""

    enabled: bool = True
    weight: int = Field(ge=0)
    description: str
    required_features: list[str] = Field(default_factory=list)
    thresholds: dict[str, int | float | str | bool] = Field(default_factory=dict)


class RulesConfig(BaseModel):
    """Top-level rules configuration."""

    version: str
    alert_min_score: int = Field(ge=0, le=100)
    severity_bands: dict[str, tuple[int, int]]
    rules: dict[str, RuleDefinition]


def _read_yaml(path: Path | str) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{config_path} must contain a YAML mapping")
    return data


def load_rules_config(path: Path | str = "config/rules.yaml") -> RulesConfig:
    """Load and validate the rule configuration."""

    return RulesConfig.model_validate(_read_yaml(path))


def file_sha256(path: Path | str) -> str:
    """Return the SHA-256 digest for a file."""

    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_yaml_hash(path: Path | str) -> str:
    """Return a stable SHA-256 hash of parsed YAML content."""

    data = _read_yaml(path)
    canonical = yaml.safe_dump(data, sort_keys=True, allow_unicode=False)
    return sha256(canonical.encode("utf-8")).hexdigest()
