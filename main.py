from __future__ import annotations

import logging
import signal
from logging.handlers import RotatingFileHandler
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ContextTypes,
)

from bot.handlers import register_handlers
from config import settings
from database.db import close_db, init_db
from services.background_tasks import (
    start_background_tasks,
    stop_background_tasks,
    sync_matches_once,
)
from services.football_api import FootballApiError, FootballDataClient


BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        RotatingFileHandler(
            LOG_DIR / "bot.log",
            maxBytes=5_000_000,
            backupCount=5,
            encoding="utf-8",
        ),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


async def telegram_error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    logger.error(
        "Unhandled exception while processing update: %r",
        update,
        exc_info=context.error,
    )


async def on_startup(application: Application) -> None:
    logger.info("Bot startup initiated")

    try:
        await init_db()

        client = FootballDataClient(settings)
        application.bot_data["football_client"] = client

        try:
            await sync_matches_once(client)
        except FootballApiError:
            logger.exception("Initial match sync failed")

        application.bot_data["background_tasks"] = start_background_tasks(
            application,
            client,
        )

        logger.info("Bot started with polling and background tasks")

    except Exception:
        logger.exception("Fatal error during startup")
        raise


async def on_shutdown(application: Application) -> None:
    logger.info("Bot shutdown initiated")

    tasks = application.bot_data.get("background_tasks", [])
    await stop_background_tasks(tasks)

    client = application.bot_data.get("football_client")
    if isinstance(client, FootballDataClient):
        await client.close()

    await close_db()
    logger.info("Bot shutdown complete")


def build_application() -> Application:
    application = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .concurrent_updates(8)
        .build()
    )

    register_handlers(application)
    application.add_error_handler(telegram_error_handler)

    return application


def main() -> None:
    application = build_application()

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        close_loop=True,
        stop_signals=(signal.SIGINT, signal.SIGTERM),
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Bot process terminated because of a fatal error")
        raise