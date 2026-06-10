from __future__ import annotations

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from bot.handlers.callbacks import match_selected_callback, outcome_selected_callback, report_callback
from bot.handlers.commands import (
    help_command,
    leaderboard_command,
    matchreport_command,
    matches_command,
    myreport_command,
    register_command,
    start_command,
)
from bot.handlers.predictions import score_text_handler


def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("register", register_command))
    application.add_handler(CommandHandler("matches", matches_command))
    application.add_handler(CommandHandler("leaderboard", leaderboard_command))
    application.add_handler(CommandHandler("myreport", myreport_command))
    application.add_handler(CommandHandler("matchreport", matchreport_command))

    application.add_handler(CallbackQueryHandler(match_selected_callback, pattern=r"^match:\d+$"))
    application.add_handler(CallbackQueryHandler(outcome_selected_callback, pattern=r"^outcome:\d+:(HOME|DRAW|AWAY)$"))
    application.add_handler(CallbackQueryHandler(report_callback, pattern=r"^report:\d+$"))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, score_text_handler))
