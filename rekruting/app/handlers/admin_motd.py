from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import get_or_create_user, get_setting_text, set_setting_text
from ..states import AdminMotd
from ..keyboards import admin_menu_inline

router = Router()


@router.callback_query(F.data == "admin:motd")
async def motd_open(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    admin = await get_or_create_user(session, cb.from_user.id)
    if not admin.is_admin:
        await cb.answer("Нет доступа.", show_alert=True)
        return

    current = await get_setting_text(session, "motd")
    await state.set_state(AdminMotd.text)
    await cb.message.answer(
        "Введите <b>сообщение дня</b> (можно пустое, чтобы отключить).\n\n"
        f"Текущее: {current if current else '-'}"
    )
    await cb.answer()


@router.message(AdminMotd.text, F.text)
async def motd_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    admin = await get_or_create_user(session, message.from_user.id)
    if not admin.is_admin:
        await state.clear()
        await message.answer("Нет доступа.")
        return

    text = message.text.strip()
    await set_setting_text(session, "motd", text)
    await state.clear()
    await message.answer("Сообщение дня сохранено.", reply_markup=admin_menu_inline())
