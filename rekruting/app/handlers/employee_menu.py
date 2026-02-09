from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import get_or_create_user
from ..keyboards import main_menu_inline

router = Router()


@router.message(F.text == "Назад")
async def go_back(message: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(session, message.from_user.id)
    await message.answer("Главное меню:", reply_markup=main_menu_inline(is_working=user.is_working))
