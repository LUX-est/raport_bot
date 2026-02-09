from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import get_or_create_user, get_setting_bool, set_setting_bool, add_work_type
from ..keyboards import settings_inline, admin_menu_inline
from ..states import AdminAddWorkType

router = Router()


@router.callback_query(F.data == "admin:settings")
async def open_settings(cb: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, cb.from_user.id)
    if not user.is_admin:
        await cb.answer("Нет доступа.", show_alert=True)
        return

    photo_reports = await get_setting_bool(session, "photo_required_reports")
    photo_problems = await get_setting_bool(session, "photo_required_problems")
    await cb.message.answer("Настройки:", reply_markup=settings_inline(photo_reports, photo_problems))
    await cb.answer()


@router.callback_query(F.data.startswith("set:toggle:"))
async def toggle_setting(cb: CallbackQuery, session: AsyncSession) -> None:
    admin = await get_or_create_user(session, cb.from_user.id)
    if not admin.is_admin:
        await cb.answer("Нет доступа.", show_alert=True)
        return

    key = cb.data.split(":")[-1]
    current = await get_setting_bool(session, key)
    await set_setting_bool(session, key, not current)

    photo_reports = await get_setting_bool(session, "photo_required_reports")
    photo_problems = await get_setting_bool(session, "photo_required_problems")
    await cb.message.edit_reply_markup(reply_markup=settings_inline(photo_reports, photo_problems))
    await cb.answer("Обновлено.")


@router.callback_query(F.data == "set:add_work_type")
async def add_worktype_start(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    admin = await get_or_create_user(session, cb.from_user.id)
    if not admin.is_admin:
        await cb.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminAddWorkType.name)
    await cb.message.answer("Введите название нового типа работ (пример: «мойка»):")
    await cb.answer()


@router.message(AdminAddWorkType.name, F.text)
async def add_worktype_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    admin = await get_or_create_user(session, message.from_user.id)
    if not admin.is_admin:
        await state.clear()
        await message.answer("Нет доступа.")
        return

    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Слишком коротко. Введите ещё раз:")
        return

    wt = await add_work_type(session, name)

    await state.clear()
    photo_reports = await get_setting_bool(session, "photo_required_reports")
    photo_problems = await get_setting_bool(session, "photo_required_problems")
    await message.answer(f"Добавлено/активировано: <b>{wt.name}</b>", reply_markup=settings_inline(photo_reports, photo_problems))
