from __future__ import annotations

import re

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.utils import ensure_group_user, is_group_chat, utc_now
from bot.messages_fa import (
    INVALID_SCORE,
    MATCH_LOCKED,
    MATCH_NOT_FOUND,
    NO_PENDING_PREDICTION,
    OUTCOME_LABELS,
    PREDICTION_SAVED,
    PREDICTION_UPDATED,
    SCORE_OUTCOME_MISMATCH,
    fa_digits,
    h,
    normalize_digits,
)
from database.db import async_session_factory
from database.models import Match, Prediction
from services.football_api import UPCOMING_STATUSES
from services.scoring import is_outcome_consistent
from services.time_utils import as_utc

SCORE_RE = re.compile(r"^\s*(\d{1,2})\s*[-:–—]\s*(\d{1,2})\s*$")


def parse_score(text: str) -> tuple[int, int] | None:
    normalized = normalize_digits(text)
    match = SCORE_RE.match(normalized)
    if not match:
        return None
    home = int(match.group(1))
    away = int(match.group(2))
    if home > 30 or away > 30:
        return None
    return home, away


async def score_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user or not update.effective_message:
        return
    if not is_group_chat(update.effective_chat):
        return

    pending_key = f"pending_prediction:{update.effective_chat.id}"
    pending = context.user_data.get(pending_key)
    if not pending:
        return

    parsed = parse_score(update.effective_message.text or "")
    if parsed is None:
        await update.effective_message.reply_html(INVALID_SCORE)
        return

    predicted_home, predicted_away = parsed
    selected_outcome = pending["outcome"]
    if not is_outcome_consistent(predicted_home, predicted_away, selected_outcome):
        label = OUTCOME_LABELS.get(selected_outcome, selected_outcome)
        await update.effective_message.reply_html(SCORE_OUTCOME_MISMATCH.format(outcome=h(label)))
        return

    async with async_session_factory() as session:
        group, user, _ = await ensure_group_user(session, update.effective_chat, update.effective_user)
        match = await session.get(Match, int(pending["match_id"]))

        if not match:
            await session.rollback()
            await update.effective_message.reply_html(MATCH_NOT_FOUND)
            return

        if as_utc(match.kickoff_at) <= utc_now() or match.status not in UPCOMING_STATUSES:
            await session.rollback()
            context.user_data.pop(pending_key, None)
            await update.effective_message.reply_html(MATCH_LOCKED)
            return

        prediction = await session.scalar(
            select(Prediction).where(
                Prediction.group_id == group.id,
                Prediction.user_id == user.id,
                Prediction.match_id == match.id,
            )
        )

        is_update = prediction is not None
        if prediction is None:
            prediction = Prediction(
                group_id=group.id,
                user_id=user.id,
                match_id=match.id,
                predicted_home=predicted_home,
                predicted_away=predicted_away,
                is_locked=False,
            )
            session.add(prediction)
        elif prediction.is_locked:
            await session.rollback()
            context.user_data.pop(pending_key, None)
            await update.effective_message.reply_html(MATCH_LOCKED)
            return
        else:
            prediction.predicted_home = predicted_home
            prediction.predicted_away = predicted_away
            prediction.points = None

        await session.commit()

    context.user_data.pop(pending_key, None)
    template = PREDICTION_UPDATED if is_update else PREDICTION_SAVED
    await update.effective_message.reply_html(
        template.format(
            home=h(match.home_team),
            away=h(match.away_team),
            ph=fa_digits(predicted_home),
            pa=fa_digits(predicted_away),
        )
    )
