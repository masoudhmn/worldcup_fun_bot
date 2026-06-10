from __future__ import annotations

import asyncio
import logging
import signal

from telegram import Update
from telegram.ext import Application, ApplicationBuilder

from bot.handlers import register_handlers
from config import settings
from database.db import close_db, init_db
from services.background_tasks import start_background_tasks, stop_background_tasks, sync_matches_once
from services.football_api import FootballDataClient, FootballApiError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def on_startup(application: Application) -> None:
    await init_db()

    client = FootballDataClient(settings)
    application.bot_data["football_client"] = client

    try:
        await sync_matches_once(client)
    except FootballApiError as exc:
        logger.warning("Initial match sync failed: %s", exc)

    application.bot_data["background_tasks"] = start_background_tasks(application, client)
    logger.info("Bot started with async polling and background tasks")


async def on_shutdown(application: Application) -> None:
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
        .concurrent_updates(True)
        .build()
    )
    register_handlers(application)
    return application


def main() -> None:
    application = build_application()
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        close_loop=True,
        stop_signals=(signal.SIGINT, signal.SIGTERM),
    )


if __name__ == "__main__":
    main()
