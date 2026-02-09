from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import get_or_create_user, is_user_registered, start_work, stop_work, get_setting_text
from ..keyboards import main_menu_inline
from ..texts import fmt_time

router = Router()


@router.callback_query(F.data == "work:start")
async def work_start(cb: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, cb.from_user.id)
    if not await is_user_registered(user):
        await cb.message.answer("Сначала заполните профиль через /start.")
        await cb.answer()
        return

    ws = await start_work(session, user)

    motd = await get_setting_text(session, "motd")
    if motd:
        await cb.message.answer(f"<b>Сообщение дня</b>\n{motd}")

    await cb.message.answer(f"Работа начата. Время: <b>{fmt_time(ws.started_at.time())}</b>",
                            reply_markup=main_menu_inline(is_working=True))
    await cb.answer()


@router.callback_query(F.data == "work:stop")
async def work_stop(cb: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, cb.from_user.id)
    if not await is_user_registered(user):
        await cb.message.answer("Сначала заполните профиль через /start.")
        await cb.answer()
        return

    ws = await stop_work(session, user)
    if ws is None:
        await cb.message.answer("У вас не было активной смены. Главное меню:", reply_markup=main_menu_inline(is_working=False))
        await cb.answer()
        return

    await cb.message.answer(
        f"Работа завершена.\nНачало: <b>{fmt_time(ws.started_at.time())}</b>\n"
        f"Конец: <b>{fmt_time(ws.ended_at.time())}</b>\n\n"
        "Теперь можно сдавать рапорт - время подставится автоматически (если дата совпадает).",
        reply_markup=main_menu_inline(is_working=False),
    )
    await cb.answer()
