from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer") from exc


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _normalize_mysql_url(url: str) -> str:
    """Accept common MySQL DSNs and make them async-SQLAlchemy compatible."""
    if url.startswith("mysql+asyncmy://"):
        return url
    if url.startswith("mysql://"):
        return "mysql+asyncmy://" + url.removeprefix("mysql://")
    if url.startswith("mysql+pymysql://"):
        return "mysql+asyncmy://" + url.removeprefix("mysql+pymysql://")
    return url


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    football_data_token: str
    mysql_url: str

    football_api_base_url: str = "https://api.football-data.org/v4"
    football_competition_code: str = "WC"
    bot_timezone: str = "Asia/Tehran"

    upcoming_matches_limit: int = 5
    football_api_cache_ttl_seconds: int = 600
    match_sync_interval_seconds: int = 1800
    scoring_interval_seconds: int = 60
    reminder_interval_seconds: int = 300
    reminder_window_seconds: int = 600

    exact_score_points: int = 3
    outcome_points: int = 1
    wrong_points: int = 0

    debug_sql: bool = False

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.bot_timezone)


def get_settings() -> Settings:
    missing = [
        name
        for name in ("TELEGRAM_BOT_TOKEN", "FOOTBALL_DATA_TOKEN", "MYSQL_URL")
        if not os.getenv(name)
    ]
    if missing:
        missing_text = ", ".join(missing)
        raise RuntimeError(f"Missing required environment variables: {missing_text}")

    return Settings(
        telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        football_data_token=os.environ["FOOTBALL_DATA_TOKEN"],
        mysql_url=_normalize_mysql_url(os.environ["MYSQL_URL"]),
        football_api_base_url=os.getenv("FOOTBALL_API_BASE_URL", "https://api.football-data.org/v4").rstrip("/"),
        football_competition_code=os.getenv("FOOTBALL_COMPETITION_CODE", "WC"),
        bot_timezone=os.getenv("BOT_TIMEZONE", "Asia/Tehran"),
        upcoming_matches_limit=_env_int("UPCOMING_MATCHES_LIMIT", 5),
        football_api_cache_ttl_seconds=_env_int("FOOTBALL_API_CACHE_TTL_SECONDS", 600),
        match_sync_interval_seconds=_env_int("MATCH_SYNC_INTERVAL_SECONDS", 1800),
        scoring_interval_seconds=_env_int("SCORING_INTERVAL_SECONDS", 60),
        reminder_interval_seconds=_env_int("REMINDER_INTERVAL_SECONDS", 300),
        reminder_window_seconds=_env_int("REMINDER_WINDOW_SECONDS", 600),
        exact_score_points=_env_int("EXACT_SCORE_POINTS", 3),
        outcome_points=_env_int("OUTCOME_POINTS", 1),
        wrong_points=_env_int("WRONG_POINTS", 0),
        debug_sql=_env_bool("DEBUG_SQL", False),
    )


settings = get_settings()
