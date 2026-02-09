from __future__ import annotations

from pathlib import Path

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Config
from ..repositories import get_or_create_user, is_user_registered
from ..states import Registration
from ..keyboards import main_menu_inline, admin_menu_inline
from ..texts import WELCOME_TEXT

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession, config: Config) -> None:
    tg_id = message.from_user.id
    user = await get_or_create_user(session, tg_id, mark_admin=(tg_id in config.admin_ids))

    await state.clear()

    if not await is_user_registered(user):
        await message.answer("Для работы нужно заполнить профиль.\n\nВведите <b>имя</b>:")
        await state.set_state(Registration.first_name)
        return

    await message.answer("Главное меню:", reply_markup=main_menu_inline(is_working=user.is_working))


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession, config: Config) -> None:
    user = await get_or_create_user(session, message.from_user.id, mark_admin=(message.from_user.id in config.admin_ids))
    if not user.is_admin:
        await message.answer("Нет доступа.")
        return
    await message.answer("Админ-панель:", reply_markup=admin_menu_inline())
