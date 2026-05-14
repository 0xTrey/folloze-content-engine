from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from exceptions import ConfigError


@dataclass(slots=True)
class SiteConfig:
    origin: str
    insights_path: str


@dataclass(slots=True)
class DeliveryConfig:
    target: str
    release_mode: str
    preview_url: str
    production_url: str


@dataclass(slots=True)
class PipelineConfig:
    quality_threshold: int
    max_retries_llm: int
    max_quality_repairs: int
    verify_timeout_seconds: int
    timezone: str
    run_hour: int
    log_level: str
    max_log_age_days: int
    geo_quality_threshold: int = 0


@dataclass(slots=True)
class EmailNotificationsConfig:
    enabled: bool
    smtp_host: str
    smtp_port: int
    from_address: str
    to_addresses: list[str]
    weekly_geo_to_addresses: list[str] | None = None


@dataclass(slots=True)
class NotificationsConfig:
    email: EmailNotificationsConfig
    discord: DiscordNotificationsConfig


@dataclass(slots=True)
class DiscordNotificationsConfig:
    enabled: bool
    channel_target: str


@dataclass(slots=True)
class ContentConfig:
    default_audience: str
    min_words_by_type: dict[str, int]


@dataclass(slots=True)
class LLMConfig:
    provider: str
    generation_model: str
    research_model: str


@dataclass(slots=True)
class Config:
    site: SiteConfig
    delivery: DeliveryConfig
    pipeline: PipelineConfig
    notifications: NotificationsConfig
    content: ContentConfig
    llm: LLMConfig

    @classmethod
    def load(cls, path: Path = Path("config.yaml")) -> Config:
        if not path.exists():
            raise ConfigError(f"Config file not found: {path}")

        raw = yaml.safe_load(path.read_text()) or {}
        try:
            config = cls(
                site=SiteConfig(**raw["site"]),
                delivery=DeliveryConfig(**raw["delivery"]),
                pipeline=PipelineConfig(**raw["pipeline"]),
                notifications=NotificationsConfig(
                    email=EmailNotificationsConfig(**raw["notifications"]["email"]),
                    discord=DiscordNotificationsConfig(**raw["notifications"]["discord"]),
                ),
                content=ContentConfig(**raw["content"]),
                llm=LLMConfig(**raw["llm"]),
            )
        except KeyError as exc:
            raise ConfigError(f"Missing config section or field: {exc}") from exc
        except TypeError as exc:
            raise ConfigError(f"Invalid config shape: {exc}") from exc

        config._validate()
        return config

    def _validate(self) -> None:
        if not 0 <= self.pipeline.quality_threshold <= 100:
            raise ConfigError("pipeline.quality_threshold must be between 0 and 100")

        if not 0 <= self.pipeline.geo_quality_threshold <= 100:
            raise ConfigError("pipeline.geo_quality_threshold must be between 0 and 100")

        if not 0 <= self.pipeline.run_hour <= 23:
            raise ConfigError("pipeline.run_hour must be between 0 and 23")

        if not 0 <= self.pipeline.max_quality_repairs <= 5:
            raise ConfigError("pipeline.max_quality_repairs must be between 0 and 5")

        try:
            ZoneInfo(self.pipeline.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ConfigError(
                f"pipeline.timezone must be a valid IANA timezone: {self.pipeline.timezone}"
            ) from exc

        if self.delivery.target != "vercel_static":
            raise ConfigError("delivery.target must be 'vercel_static'")

        if self.delivery.release_mode not in {"manual", "auto"}:
            raise ConfigError("delivery.release_mode must be 'manual' or 'auto'")

        if self.llm.provider != "gemini":
            raise ConfigError("llm.provider must be 'gemini'")

        if self.notifications.email.weekly_geo_to_addresses is None:
            self.notifications.email.weekly_geo_to_addresses = list(
                self.notifications.email.to_addresses
            )

        for field_name, value in (
            ("delivery.preview_url", self.delivery.preview_url),
            ("delivery.production_url", self.delivery.production_url),
            ("site.origin", self.site.origin),
        ):
            parsed = urlparse(value)
            if not parsed.scheme or not parsed.netloc:
                raise ConfigError(f"{field_name} must be an absolute URL")

        required_types = {"comparison", "guide", "faq", "glossary", "blog"}
        configured_types = set(self.content.min_words_by_type)
        if configured_types != required_types:
            raise ConfigError(
                "content.min_words_by_type must define comparison, guide, faq, glossary, blog"
            )
