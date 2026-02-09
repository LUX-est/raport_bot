from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, echo=False, future=True)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    from . import models

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        dialect = getattr(conn.dialect, "name", "")
        if dialect != "sqlite":
            return

        async def has_col(table: str, column: str) -> bool:
            res = await conn.execute(text(f"PRAGMA table_info({table});"))
            return any(r[1] == column for r in res.fetchall())

        if not await has_col("users", "is_working"):
            await conn.execute(text("ALTER TABLE users ADD COLUMN is_working BOOLEAN NOT NULL DEFAULT 0;"))
        if not await has_col("users", "work_started_at"):
            await conn.execute(text("ALTER TABLE users ADD COLUMN work_started_at DATETIME NULL;"))
        if not await has_col("users", "phone"):
            await conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(32) NULL;"))
        if not await has_col("users", "leader"):
            await conn.execute(text("ALTER TABLE users ADD COLUMN leader VARCHAR(128) NULL;"))

        if not await has_col("reports", "edit_count"):
            await conn.execute(text("ALTER TABLE reports ADD COLUMN edit_count INTEGER NOT NULL DEFAULT 0;"))
        if not await has_col("reports", "edited_at"):
            await conn.execute(text("ALTER TABLE reports ADD COLUMN edited_at DATETIME NULL;"))
        if not await has_col("reports", "edited_by_user_id"):
            await conn.execute(text("ALTER TABLE reports ADD COLUMN edited_by_user_id INTEGER NULL;"))
        if not await has_col("reports", "partner_name"):
            await conn.execute(text("ALTER TABLE reports ADD COLUMN partner_name VARCHAR(128) NULL;"))
