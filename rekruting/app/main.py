from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from .config import load_config
from .db import make_engine, make_sessionmaker, init_db
from .middlewares import DbSessionMiddleware, ConfigMiddleware, SheetsMiddleware
from .repositories import seed_defaults
from .google_sheets import GoogleSheetsClient, SheetsTarget

from .handlers import (
    start,
    registration,
    navigation,
    work_tracking,
    employee_reports,
    employee_problems,
    employee_history,
    admin_reports,
    admin_settings,
    admin_motd,
    admin_workers,
    employee_menu,  
)


async def on_startup(dispatcher: Dispatcher, bot: Bot) -> None:
    engine = dispatcher["engine"]
    sessionmaker = dispatcher["sessionmaker"]
    await init_db(engine)
    async with sessionmaker() as session:
        await seed_defaults(session)
    logging.getLogger(__name__).info("DB initialized and defaults seeded.")

    sheets = dispatcher.get("sheets")
    if sheets is not None:
        try:
            sheets.ensure_sheets_exist()
            logging.getLogger(__name__).info("Google Sheets is ready.")
        except Exception:
            logging.getLogger(__name__).exception("Google Sheets init failed.")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    config = load_config()

    engine = make_engine(config.database_url)
    sessionmaker = make_sessionmaker(engine)

    sheets = None
    if config.google_sheets is not None:
        target = SheetsTarget(
            spreadsheet_id=config.google_sheets.spreadsheet_id,
            sheet_reports=config.google_sheets.sheet_reports,
            sheet_problems=config.google_sheets.sheet_problems,
            sheet_edits=config.google_sheets.sheet_edits,
            sheet_statuses=config.google_sheets.sheet_statuses,
        )
        sheets = GoogleSheetsClient(config.google_sheets.service_account_file, target)

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp["engine"] = engine
    dp["sessionmaker"] = sessionmaker
    dp["sheets"] = sheets

    dp.update.middleware(ConfigMiddleware(config))
    dp.update.middleware(DbSessionMiddleware(sessionmaker))
    dp.update.middleware(SheetsMiddleware(sheets))

    dp.include_router(start.router)
    dp.include_router(registration.router)

    dp.include_router(navigation.router)
    dp.include_router(work_tracking.router)

    dp.include_router(employee_reports.router)
    dp.include_router(employee_problems.router)
    dp.include_router(employee_history.router)

    dp.include_router(admin_reports.router)
    dp.include_router(admin_settings.router)
    dp.include_router(admin_motd.router)
    dp.include_router(admin_workers.router)

    dp.include_router(employee_menu.router)  

    dp.startup.register(on_startup)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
