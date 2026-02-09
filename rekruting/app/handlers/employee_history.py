from __future__ import annotations

from datetime import date

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import get_or_create_user, list_user_reports, sum_user_tasks_for_month
from ..texts import fmt_date, human_report_status
from ..keyboards import main_menu_inline, my_reports_inline
from ..handlers.employee_reports import _start_report  

router = Router()


@router.callback_query(F.data == "menu:history")
async def my_reports_cb(cb: CallbackQuery, session: AsyncSession) -> None:
    await _show(cb.message, cb.from_user.id, session)
    await cb.answer()


@router.message(F.text == "Мои рапорты")
async def my_reports_msg(message: Message, session: AsyncSession) -> None:
    await _show(message, message.from_user.id, session)


async def _show(message_obj, tg_id: int, session: AsyncSession) -> None:
    user = await get_or_create_user(session, tg_id)
    reports = await list_user_reports(session, user.id, limit=10)
    today = date.today()
    total = await sum_user_tasks_for_month(session, user.id, today.year, today.month)

    if not reports:
        await message_obj.answer(
            f"Рапортов пока нет.\nИтого задач за месяц: <b>{total}</b>",
            reply_markup=main_menu_inline(is_working=user.is_working),
        )
        return

    lines = [f"<b>Последние рапорты</b> (до 10 шт.)\nИтого задач за месяц: <b>{total}</b>\n"]
    ids = []
    for r in reports:
        ids.append(r.id)
        cmt = f" | комм.: {r.admin_comment}" if r.admin_comment else ""
        edited = f" | правок: {r.edit_count}" if r.edit_count else ""
        lines.append(f"• #{r.id} - {fmt_date(r.report_date)} - <b>{human_report_status(r.status)}</b>{cmt}{edited}")

    await message_obj.answer("\n".join(lines), reply_markup=my_reports_inline(ids))


@router.callback_query(F.data.startswith("my:edit:"))
async def edit_report(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    report_id = int(cb.data.split(":")[-1])
    await _start_report(cb.message, cb.from_user.id, state, session, editing_report_id=report_id)
    await cb.answer()
