from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Iterable

from sqlalchemy import select
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application

from bot.messages_fa import REMINDER_TEXT, format_dt, h, mention
from config import settings
from database.db import async_session_factory
from database.models import Group, GroupUser, Match, Prediction, ReminderLog, User
from services.football_api import FINISHED_STATUSES, UPCOMING_STATUSES, FootballDataClient, FootballApiError, normalize_api_match
from services.scoring import calculate_prediction_points
from services.time_utils import as_utc, utc_now

logger = logging.getLogger(__name__)

REMINDER_WINDOWS: tuple[tuple[str, int, str], ...] = (
    ("24h", 24 * 60 * 60, "۲۴ ساعت"),
    ("3h", 3 * 60 * 60, "۳ ساعت"),
    ("30m", 30 * 60, "۳۰ دقیقه"),
)


async def sync_matches_once(client: FootballDataClient) -> int:
    raw_matches = await client.get_world_cup_matches()
    normalized = [normalize_api_match(item) for item in raw_matches]
    normalized.sort(key=lambda item: item["kickoff_at"])

    now = utc_now()
    upcoming_kept = 0
    synced_count = 0

    async with async_session_factory() as session:
        for item in normalized:
            is_upcoming = item["status"] in UPCOMING_STATUSES and as_utc(item["kickoff_at"]) > now
            should_keep_upcoming = is_upcoming and upcoming_kept < settings.upcoming_matches_limit
            should_update_existing = item["status"] in FINISHED_STATUSES or as_utc(item["kickoff_at"]) <= now + timedelta(days=2)

            if not should_keep_upcoming and not should_update_existing:
                continue

            if should_keep_upcoming:
                upcoming_kept += 1

            match = await session.scalar(select(Match).where(Match.api_id == item["api_id"]))
            if match is None:
                session.add(Match(**item))
            else:
                match.home_team = item["home_team"]
                match.away_team = item["away_team"]
                match.kickoff_at = item["kickoff_at"]
                match.status = item["status"]
                match.home_score = item["home_score"]
                match.away_score = item["away_score"]
            synced_count += 1
        await session.commit()

    logger.info("Synced %s World Cup matches from football-data.org", synced_count)
    return synced_count


async def lock_due_predictions_once() -> int:
    now = utc_now()
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(Prediction)
                .join(Match, Prediction.match_id == Match.id)
                .where(Prediction.is_locked.is_(False), Match.kickoff_at <= now)
            )
        ).scalars()
        count = 0
        for prediction in rows:
            prediction.is_locked = True
            count += 1
        await session.commit()
        return count


async def calculate_scores_once() -> int:
    async with async_session_factory() as session:
        predictions = (
            await session.execute(
                select(Prediction, Match)
                .join(Match, Prediction.match_id == Match.id)
                .where(
                    Match.status.in_(FINISHED_STATUSES),
                    Match.home_score.is_not(None),
                    Match.away_score.is_not(None),
                    Prediction.points.is_(None),
                )
            )
        ).all()

        count = 0
        for prediction, match in predictions:
            prediction.points = calculate_prediction_points(
                prediction.predicted_home,
                prediction.predicted_away,
                int(match.home_score),
                int(match.away_score),
            )
            prediction.is_locked = True
            count += 1

        await session.commit()
        return count


async def _get_missing_predictors(group_id: int, match_id: int) -> list[User]:
    async with async_session_factory() as session:
        active_users = (
            await session.execute(
                select(User)
                .join(GroupUser, GroupUser.user_id == User.id)
                .where(GroupUser.group_id == group_id, GroupUser.is_active.is_(True))
            )
        ).scalars().all()

        predicted_user_ids = set(
            (
                await session.execute(
                    select(Prediction.user_id).where(Prediction.group_id == group_id, Prediction.match_id == match_id)
                )
            ).scalars().all()
        )

        return [user for user in active_users if user.id not in predicted_user_ids]


async def send_reminders_once(application: Application) -> int:
    now = utc_now()
    sent_count = 0

    async with async_session_factory() as session:
        matches = (
            await session.execute(
                select(Match).where(
                    Match.status.in_(UPCOMING_STATUSES),
                    Match.kickoff_at > now,
                    Match.kickoff_at <= now + timedelta(hours=25),
                )
            )
        ).scalars().all()
        groups = (await session.execute(select(Group))).scalars().all()

    for match in matches:
        seconds_to_kickoff = (as_utc(match.kickoff_at) - now).total_seconds()
        for key, target_seconds, label in REMINDER_WINDOWS:
            if not (0 < seconds_to_kickoff <= target_seconds):
                continue
            if target_seconds - seconds_to_kickoff > settings.reminder_window_seconds:
                continue

            for group in groups:
                async with async_session_factory() as session:
                    already_sent = await session.scalar(
                        select(ReminderLog).where(
                            ReminderLog.group_id == group.id,
                            ReminderLog.match_id == match.id,
                            ReminderLog.reminder_key == key,
                        )
                    )
                    if already_sent:
                        continue

                    missing_users = await _get_missing_predictors(group.id, match.id)
                    if not missing_users:
                        session.add(ReminderLog(group_id=group.id, match_id=match.id, reminder_key=key))
                        await session.commit()
                        continue

                    mentions = "\n".join(
                        f"• {mention(user.username, user.first_name, user.user_id)}" for user in missing_users
                    )
                    text = REMINDER_TEXT.format(
                        label=label,
                        home=h(match.home_team),
                        away=h(match.away_team),
                        kickoff=format_dt(match.kickoff_at),
                        mentions=mentions,
                    )
                    try:
                        await application.bot.send_message(
                            chat_id=group.chat_id,
                            text=text,
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=True,
                        )
                        session.add(ReminderLog(group_id=group.id, match_id=match.id, reminder_key=key))
                        await session.commit()
                        sent_count += 1
                    except TelegramError as exc:
                        await session.rollback()
                        logger.warning("Failed to send reminder to group %s: %s", group.chat_id, exc)

    return sent_count


async def match_sync_loop(client: FootballDataClient) -> None:
    while True:
        try:
            await sync_matches_once(client)
        except FootballApiError as exc:
            logger.warning("Match sync skipped: %s", exc)
        except Exception:
            logger.exception("Unexpected error in match sync loop")
        await asyncio.sleep(settings.match_sync_interval_seconds)


async def scoring_loop() -> None:
    while True:
        try:
            locked = await lock_due_predictions_once()
            scored = await calculate_scores_once()
            if locked or scored:
                logger.info("Locked %s predictions and scored %s predictions", locked, scored)
        except Exception:
            logger.exception("Unexpected error in scoring loop")
        await asyncio.sleep(settings.scoring_interval_seconds)


async def reminder_loop(application: Application) -> None:
    while True:
        try:
            sent = await send_reminders_once(application)
            if sent:
                logger.info("Sent %s reminder messages", sent)
        except Exception:
            logger.exception("Unexpected error in reminder loop")
        await asyncio.sleep(settings.reminder_interval_seconds)


def start_background_tasks(application: Application, client: FootballDataClient) -> list[asyncio.Task[None]]:
    return [
        asyncio.create_task(match_sync_loop(client), name="match-sync-loop"),
        asyncio.create_task(scoring_loop(), name="scoring-loop"),
        asyncio.create_task(reminder_loop(application), name="reminder-loop"),
    ]


async def stop_background_tasks(tasks: Iterable[asyncio.Task[None]]) -> None:
    task_list = list(tasks)
    for task in task_list:
        task.cancel()
    await asyncio.gather(*task_list, return_exceptions=True)
