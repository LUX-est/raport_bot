from __future__ import annotations

from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from .config import Config


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        super().__init__()
        self._sessionmaker = sessionmaker

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        async with self._sessionmaker() as session:
            data["session"] = session
            return await handler(event, data)


class ConfigMiddleware(BaseMiddleware):
    def __init__(self, config: Config):
        super().__init__()
        self._config = config

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        data["config"] = self._config
        return await handler(event, data)


class SheetsMiddleware(BaseMiddleware):
    def __init__(self, sheets):
        super().__init__()
        self._sheets = sheets

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        data["sheets"] = self._sheets
        return await handler(event, data)
