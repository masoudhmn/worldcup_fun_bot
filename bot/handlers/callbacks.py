from __future__ import annotations

from sqlalchemy import select
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.keyboards import outcome_keyboard
from bot.messages_fa import (
    ASK_EXACT_SCORE,
    CHOOSE_OUTCOME,
    MATCH_LOCKED,
    MATCH_NOT_FOUND,
    OUTCOME_LABELS,
    h,
)
from bot.handlers.reports import build_match_report
from bot.handlers.utils import ensure_group_user, is_group_chat, utc_now
from services.time_utils import as_utc
from database.db import async_session_factory
from database.models import Match
from services.football_api import UPCOMING_STATUSES


async def match_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message or not update.effective_user:
        return
    await query.answer()

    chat = query.message.chat
    if not is_group_chat(chat):
        return

    try:
        match_id = int(query.data.split(":", maxsplit=1)[1])
    except (AttributeError, ValueError, IndexError):
        await query.edit_message_text(MATCH_NOT_FOUND, parse_mode=ParseMode.HTML)
        return

    async with async_session_factory() as session:
        await ensure_group_user(session, chat, update.effective_user)
        match = await session.get(Match, match_id)
        await session.commit()

    if not match:
        await query.edit_message_text(MATCH_NOT_FOUND, parse_mode=ParseMode.HTML)
        return

    if as_utc(match.kickoff_at) <= utc_now() or match.status not in UPCOMING_STATUSES:
        await query.edit_message_text(MATCH_LOCKED, parse_mode=ParseMode.HTML)
        return

    text = CHOOSE_OUTCOME.format(home=h(match.home_team), away=h(match.away_team))
    await query.edit_message_text(text=text, parse_mode=ParseMode.HTML, reply_markup=outcome_keyboard(match))


async def outcome_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message or not update.effective_user:
        return
    await query.answer()

    chat = query.message.chat
    if not is_group_chat(chat):
        return

    try:
        _, match_id_raw, selected_outcome = query.data.split(":", maxsplit=2)
        match_id = int(match_id_raw)
    except (AttributeError, ValueError):
        await query.edit_message_text(MATCH_NOT_FOUND, parse_mode=ParseMode.HTML)
        return

    async with async_session_factory() as session:
        await ensure_group_user(session, chat, update.effective_user)
        match = await session.get(Match, match_id)
        await session.commit()

    if not match:
        await query.edit_message_text(MATCH_NOT_FOUND, parse_mode=ParseMode.HTML)
        return

    if as_utc(match.kickoff_at) <= utc_now() or match.status not in UPCOMING_STATUSES:
        await query.edit_message_text(MATCH_LOCKED, parse_mode=ParseMode.HTML)
        return

    context.user_data[f"pending_prediction:{chat.id}"] = {
        "match_id": match.id,
        "outcome": selected_outcome,
    }

    outcome_label = OUTCOME_LABELS.get(selected_outcome, selected_outcome)
    await query.edit_message_text(
        text=f"✅ انتخابت: <b>{outcome_label}</b>\n\n{ASK_EXACT_SCORE}",
        parse_mode=ParseMode.HTML,
    )


async def report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message or not update.effective_user:
        return
    await query.answer()

    chat = query.message.chat
    if not is_group_chat(chat):
        return

    try:
        match_id = int(query.data.split(":", maxsplit=1)[1])
    except (AttributeError, ValueError, IndexError):
        await query.edit_message_text(MATCH_NOT_FOUND, parse_mode=ParseMode.HTML)
        return

    async with async_session_factory() as session:
        await ensure_group_user(session, chat, update.effective_user)
        text = await build_match_report(session, chat.id, match_id)
        await session.commit()

    await query.edit_message_text(text=text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
