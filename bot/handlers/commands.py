from __future__ import annotations

from collections import defaultdict
from html import escape
from typing import Iterable

from sqlalchemy import select
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.keyboards import finished_matches_keyboard, matches_keyboard
from bot.messages_fa import (
    API_SYNC_FAILED,
    CHOOSE_MATCH,
    EMPTY_LEADERBOARD,
    HELP,
    NO_FINISHED_MATCHES,
    NO_STATS,
    NO_UPCOMING_MATCHES,
    PRIVATE_ONLY_GROUPS,
    REGISTERED,
    REPORT_CHOOSE_MATCH,
    fa_digits,
    format_dt,
    h,
    mention,
    FUNNY_TITLES,
)
from bot.handlers.utils import ensure_group_user, get_group_by_chat, is_group_chat
from config import settings
from database.db import async_session_factory
from database.models import GroupUser, Match, Prediction, User
from services.background_tasks import sync_matches_once
from services.football_api import FINISHED_STATUSES, UPCOMING_STATUSES, FootballApiError, FootballDataClient


async def _require_group(update: Update) -> bool:
    chat = update.effective_chat
    if is_group_chat(chat):
        return True
    if update.effective_message:
        await update.effective_message.reply_html(PRIVATE_ONLY_GROUPS)
    return False


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await register_command(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_group(update):
        return
    await update.effective_message.reply_html(HELP, disable_web_page_preview=True)


async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_group(update):
        return
    assert update.effective_chat and update.effective_user and update.effective_message

    async with async_session_factory() as session:
        await ensure_group_user(session, update.effective_chat, update.effective_user)
        await session.commit()

    await update.effective_message.reply_html(REGISTERED)


async def matches_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_group(update):
        return
    assert update.effective_chat and update.effective_user and update.effective_message

    async with async_session_factory() as session:
        await ensure_group_user(session, update.effective_chat, update.effective_user)
        await session.commit()

    matches = await _get_upcoming_matches()
    if not matches:
        client = context.application.bot_data.get("football_client")
        if isinstance(client, FootballDataClient):
            try:
                await sync_matches_once(client)
            except FootballApiError:
                await update.effective_message.reply_html(API_SYNC_FAILED)
                return
            matches = await _get_upcoming_matches()

    if not matches:
        await update.effective_message.reply_html(NO_UPCOMING_MATCHES)
        return

    await update.effective_message.reply_html(CHOOSE_MATCH, reply_markup=matches_keyboard(matches))


async def _get_upcoming_matches() -> list[Match]:
    async with async_session_factory() as session:
        return (
            await session.execute(
                select(Match)
                .where(Match.status.in_(UPCOMING_STATUSES))
                .order_by(Match.kickoff_at.asc())
                .limit(settings.upcoming_matches_limit)
            )
        ).scalars().all()


async def matchreport_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_group(update):
        return
    assert update.effective_chat and update.effective_user and update.effective_message

    async with async_session_factory() as session:
        await ensure_group_user(session, update.effective_chat, update.effective_user)
        matches = (
            await session.execute(
                select(Match)
                .where(Match.status.in_(FINISHED_STATUSES), Match.home_score.is_not(None), Match.away_score.is_not(None))
                .order_by(Match.kickoff_at.desc())
                .limit(5)
            )
        ).scalars().all()
        await session.commit()

    if not matches:
        await update.effective_message.reply_html(NO_FINISHED_MATCHES)
        return

    await update.effective_message.reply_html(REPORT_CHOOSE_MATCH, reply_markup=finished_matches_keyboard(matches))


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_group(update):
        return
    assert update.effective_chat and update.effective_user and update.effective_message

    async with async_session_factory() as session:
        group, _, _ = await ensure_group_user(session, update.effective_chat, update.effective_user)
        active_users = (
            await session.execute(
                select(User)
                .join(GroupUser, GroupUser.user_id == User.id)
                .where(GroupUser.group_id == group.id, GroupUser.is_active.is_(True))
            )
        ).scalars().all()
        predictions = (
            await session.execute(select(Prediction).where(Prediction.group_id == group.id, Prediction.points.is_not(None)))
        ).scalars().all()
        await session.commit()

    totals: dict[int, int] = defaultdict(int)
    counts: dict[int, int] = defaultdict(int)
    for prediction in predictions:
        totals[prediction.user_id] += int(prediction.points or 0)
        counts[prediction.user_id] += 1

    ranked = sorted(active_users, key=lambda user: (-totals[user.id], mention(user.username, user.first_name, user.user_id)))
    if not ranked or all(totals[user.id] == 0 and counts[user.id] == 0 for user in ranked):
        await update.effective_message.reply_html(EMPTY_LEADERBOARD)
        return

    lines = ["🏆 <b>جدول کری‌خوانی گروه</b>", ""]
    for idx, user in enumerate(ranked, start=1):
        title = FUNNY_TITLES[min(idx - 1, len(FUNNY_TITLES) - 1)]
        lines.append(
            f"{fa_digits(idx)}. {mention(user.username, user.first_name, user.user_id)} — "
            f"<b>{fa_digits(totals[user.id])}</b> امتیاز | {title}"
        )

    await update.effective_message.reply_html("\n".join(lines), disable_web_page_preview=True)


async def myreport_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_group(update):
        return
    assert update.effective_chat and update.effective_user and update.effective_message

    async with async_session_factory() as session:
        group, user, _ = await ensure_group_user(session, update.effective_chat, update.effective_user)
        active_users = (
            await session.execute(
                select(User)
                .join(GroupUser, GroupUser.user_id == User.id)
                .where(GroupUser.group_id == group.id, GroupUser.is_active.is_(True))
            )
        ).scalars().all()
        predictions = (
            await session.execute(select(Prediction).where(Prediction.group_id == group.id, Prediction.points.is_not(None)))
        ).scalars().all()
        await session.commit()

    if not predictions:
        await update.effective_message.reply_html(NO_STATS)
        return

    totals: dict[int, int] = defaultdict(int)
    for prediction in predictions:
        totals[prediction.user_id] += int(prediction.points or 0)

    ranked = sorted(active_users, key=lambda row: -totals[row.id])
    rank = next((idx for idx, row in enumerate(ranked, start=1) if row.id == user.id), len(ranked))

    mine = [prediction for prediction in predictions if prediction.user_id == user.id]
    if not mine:
        await update.effective_message.reply_html(NO_STATS)
        return

    total_points = sum(int(prediction.points or 0) for prediction in mine)
    total_predictions = len(mine)
    exact_count = sum(1 for prediction in mine if prediction.points == settings.exact_score_points)
    correct_outcome_count = sum(1 for prediction in mine if (prediction.points or 0) > 0)
    accuracy = round((correct_outcome_count / total_predictions) * 100) if total_predictions else 0

    text = "\n".join(
        [
            "📋 <b>کارنامه فوتبالی تو</b>",
            "",
            f"امتیاز کل: <b>{fa_digits(total_points)}</b>",
            f"رتبه گروه: <b>{fa_digits(rank)}</b> از {fa_digits(len(ranked))}",
            f"تعداد پیش‌بینی‌های محاسبه‌شده: {fa_digits(total_predictions)}",
            f"نتیجه دقیق: {fa_digits(exact_count)} 🎯",
            f"درصد تشخیص روند بازی: {fa_digits(accuracy)}٪",
            "",
            "جمع‌بندی: هنوز وقت هست از گواردیولا جلو بزنی 😄",
        ]
    )
    await update.effective_message.reply_html(text)
