from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import get_or_create_user, is_user_registered
from ..keyboards import main_menu_inline

router = Router()


@router.callback_query(F.data == "menu:main")
async def menu_main(cb: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, cb.from_user.id)
    if not await is_user_registered(user):
        await cb.message.answer("Сначала заполните профиль через /start.")
        await cb.answer()
        return
    await cb.message.answer("Главное меню:", reply_markup=main_menu_inline(is_working=user.is_working))
    await cb.answer()
