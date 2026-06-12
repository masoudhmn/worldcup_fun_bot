from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.messages_fa import fa_digits, format_dt
from database.models import Match


def matches_keyboard(matches: list[Match]) -> InlineKeyboardMarkup: 
    rows: list[list[InlineKeyboardButton]] = [] 
    for match in matches: 
        text = f"⚽️ {match.home_team} - {match.away_team} | {format_dt(match.kickoff_at)}" 
        rows.append([InlineKeyboardButton(text=text, callback_data=f"match:{match.id}")]) 
    return InlineKeyboardMarkup(rows)


def outcome_keyboard(match: Match) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"🏠 برد {match.home_team}", callback_data=f"outcome:{match.id}:HOME")],
            [InlineKeyboardButton("🤝 مساوی", callback_data=f"outcome:{match.id}:DRAW")],
            [InlineKeyboardButton(f"🚌 برد {match.away_team}", callback_data=f"outcome:{match.id}:AWAY")],
        ]
    )


def finished_matches_keyboard(matches: list[Match]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for match in matches:
        score = "؟-؟"
        if match.home_score is not None and match.away_score is not None:
            score = f"{fa_digits(match.home_score)}-{fa_digits(match.away_score)}"
        text = f"📊 {match.home_team} {score} {match.away_team}"
        rows.append([InlineKeyboardButton(text=text, callback_data=f"report:{match.id}")])
    return InlineKeyboardMarkup(rows)
