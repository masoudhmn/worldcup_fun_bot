from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from config import Settings, settings

logger = logging.getLogger(__name__)

FINISHED_STATUSES = {"FINISHED", "AWARDED"}
UPCOMING_STATUSES = {"SCHEDULED", "TIMED"}
LIVE_STATUSES = {"IN_PLAY", "PAUSED"}


class FootballApiError(RuntimeError):
    pass


def parse_utc_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _team_name(team: dict[str, Any]) -> str:
    return team.get("shortName") or team.get("tla") or team.get("name") or "تیم نامشخص"


class FootballDataClient:
    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings
        self._cache: dict[str, tuple[datetime, Any]] = {}
        self._client = httpx.AsyncClient(
            base_url=self.settings.football_api_base_url,
            headers={"X-Auth-Token": self.settings.football_data_token},
            timeout=httpx.Timeout(20.0),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any] | None = None, ttl_seconds: int | None = None) -> Any:
        ttl_seconds = ttl_seconds if ttl_seconds is not None else self.settings.football_api_cache_ttl_seconds
        cache_key = f"{path}:{sorted((params or {}).items())}"
        now = datetime.now(UTC)
        cached = self._cache.get(cache_key)
        if cached and (now - cached[0]).total_seconds() < ttl_seconds:
            return cached[1]

        try:
            response = await self._client.get(path, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            body = exc.response.text[:500]
            logger.warning("football-data.org returned %s: %s", status_code, body)
            raise FootballApiError(f"football-data.org HTTP {status_code}: {body}") from exc
        except httpx.HTTPError as exc:
            logger.warning("football-data.org request failed: %s", exc)
            raise FootballApiError(str(exc)) from exc

        data = response.json()
        self._cache[cache_key] = (now, data)
        return data

    async def get_world_cup_matches(self, days_back: int = 2, days_ahead: int = 80) -> list[dict[str, Any]]:
        today = date.today()
        params = {
            "dateFrom": (today - timedelta(days=days_back)).isoformat(),
            "dateTo": (today + timedelta(days=days_ahead)).isoformat(),
        }
        data = await self._get(f"/competitions/{self.settings.football_competition_code}/matches", params=params)
        return data.get("matches", [])

    async def get_match(self, api_id: int) -> dict[str, Any]:
        return await self._get(f"/matches/{api_id}", ttl_seconds=60)


def normalize_api_match(raw: dict[str, Any]) -> dict[str, Any]:
    score = raw.get("score") or {}
    full_time = score.get("fullTime") or {}
    status = raw.get("status") or "SCHEDULED"

    return {
        "api_id": int(raw["id"]),
        "home_team": _team_name(raw.get("homeTeam") or {}),
        "away_team": _team_name(raw.get("awayTeam") or {}),
        "kickoff_at": parse_utc_datetime(raw["utcDate"]),
        "status": status,
        "home_score": full_time.get("home"),
        "away_score": full_time.get("away"),
    }
