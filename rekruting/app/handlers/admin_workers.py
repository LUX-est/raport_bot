from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import get_or_create_user, list_workers
from ..states import AdminSendMessage
from ..keyboards import workers_inline, admin_menu_inline
from ..texts import fmt_time

router = Router()


@router.callback_query(F.data == "admin:workers")
async def workers_list(cb: CallbackQuery, session: AsyncSession) -> None:
    admin = await get_or_create_user(session, cb.from_user.id)
    if not admin.is_admin:
        await cb.answer("Нет доступа.", show_alert=True)
        return

    users = await list_workers(session, limit=30)
    lines = ["<b>Сотрудники</b> (до 30):\n"]
    btn_users = []
    for u in users:
        name = f"{u.first_name or ''} {u.last_name or ''}".strip() or f"tg:{u.tg_id}"
        status = "🟢 работает" if u.is_working else "⚪ не работает"
        since = f" с {fmt_time(u.work_started_at.time())}" if u.is_working and u.work_started_at else ""
        phone = u.phone or "-"
        leader = u.leader or "-"
        lines.append(
            f"• {name} ({u.city or '-'}) - {status}{since}\n"
            f"  Номер телефона: {phone}\n"
            f"  Лидер: {leader}"
        )
        btn_users.append((u.tg_id, name))

    await cb.message.answer("\n".join(lines), reply_markup=workers_inline(btn_users))
    await cb.answer()


@router.callback_query(F.data == "admin:back")
async def back(cb: CallbackQuery) -> None:
    await cb.message.answer("Админ-панель:", reply_markup=admin_menu_inline())
    await cb.answer()


@router.callback_query(F.data.startswith("admin:msg:"))
async def msg_pick(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    admin = await get_or_create_user(session, cb.from_user.id)
    if not admin.is_admin:
        await cb.answer("Нет доступа.", show_alert=True)
        return

    target_tg_id = int(cb.data.split(":")[-1])
    await state.set_state(AdminSendMessage.text)
    await state.update_data(target_tg_id=target_tg_id)
    await cb.message.answer("Введите сообщение сотруднику:")
    await cb.answer()


@router.message(AdminSendMessage.text, F.text)
async def msg_send(message: Message, state: FSMContext, session: AsyncSession) -> None:
    admin = await get_or_create_user(session, message.from_user.id)
    if not admin.is_admin:
        await state.clear()
        await message.answer("Нет доступа.")
        return

    data = await state.get_data()
    target_tg_id = int(data["target_tg_id"])
    text = message.text

    try:
        await message.bot.send_message(target_tg_id, f"Сообщение от администратора:\n\n{text}")
        await message.answer("Отправлено.", reply_markup=admin_menu_inline())
    except Exception:
        await message.answer(
            "Не удалось отправить (возможно пользователь не писал боту).",
            reply_markup=admin_menu_inline(),
        )

    await state.clear()
