from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import (
    get_or_create_user,
    list_pending_reports,
    set_report_status,
    get_report_with_user_and_tasks,
    list_admins,
    list_recent_reports,
    list_recent_report_edits,
    list_recent_problems,
    now_local,
)
from ..states import AdminReject
from ..enums import ReportStatus
from ..keyboards import admin_menu_inline
from ..config import Config

router = Router()


def _admin_display_name(admin) -> str:
    full = f"{admin.first_name or ''} {admin.last_name or ''}".strip()
    return full or str(admin.tg_id)


@router.callback_query(F.data == "admin:history:reports")
async def admin_reports_history(cb: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, cb.from_user.id)
    if not user.is_admin:
        await cb.answer("Нет доступа.", show_alert=True)
        return

    rows = await list_recent_reports(session, limit=20)
    if not rows:
        await cb.message.answer("История рапортов пуста.", reply_markup=admin_menu_inline())
        await cb.answer()
        return

    lines: list[str] = []
    for r in rows:
        uname = f"{r.user.first_name or ''} {r.user.last_name or ''}".strip() or str(r.user.tg_id)
        lines.append(
            f"#{r.id} | {r.report_date.strftime('%d.%m.%Y')} | {uname} | {r.status.value}"
        )

    text = "История рапортов (последние 20):\n" + "\n".join(lines)
    await cb.message.answer(text, reply_markup=admin_menu_inline())
    await cb.answer()


@router.callback_query(F.data == "admin:history:edits")
async def admin_edits_history(cb: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, cb.from_user.id)
    if not user.is_admin:
        await cb.answer("Нет доступа.", show_alert=True)
        return

    rows = await list_recent_report_edits(session, limit=20)
    if not rows:
        await cb.message.answer("История изменений пуста.", reply_markup=admin_menu_inline())
        await cb.answer()
        return

    lines: list[str] = []
    for log, editor in rows:
        ename = f"{editor.first_name or ''} {editor.last_name or ''}".strip() or str(editor.tg_id)
        when = log.edited_at.strftime('%d.%m.%Y %H:%M')
        lines.append(f"#{log.report_id} | {when} | {ename}")

    text = "История изменений (последние 20):\n" + "\n".join(lines)
    await cb.message.answer(text, reply_markup=admin_menu_inline())
    await cb.answer()


@router.callback_query(F.data == "admin:history:problems")
async def admin_problems_history(cb: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, cb.from_user.id)
    if not user.is_admin:
        await cb.answer("Нет доступа.", show_alert=True)
        return

    rows = await list_recent_problems(session, limit=20)
    if not rows:
        await cb.message.answer("История проблем пуста.", reply_markup=admin_menu_inline())
        await cb.answer()
        return

    lines: list[str] = []
    for p in rows:
        uname = f"{p.user.first_name or ''} {p.user.last_name or ''}".strip() or str(p.user.tg_id)
        when = p.created_at.strftime('%d.%m.%Y %H:%M')
        lines.append(f"#{p.id} | {when} | {uname} | {p.problem_type} | {p.urgency.value}")

    text = "История проблем (последние 20):\n" + "\n".join(lines)
    await cb.message.answer(text, reply_markup=admin_menu_inline())
    await cb.answer()


@router.callback_query(F.data == "admin:pending")
async def pending_reports(cb: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, cb.from_user.id)
    if not user.is_admin:
        await cb.answer("Нет доступа.", show_alert=True)
        return

    rows = await list_pending_reports(session, limit=15)
    if not rows:
        await cb.message.answer("Нет рапортов на проверке.", reply_markup=admin_menu_inline())
        await cb.answer()
        return

    ids = ", ".join([f"#{r.id}" for r in rows])
    await cb.message.answer(
        "Рапорты на проверке (последние 15):\n"
        f"{ids}\n\n"
        "Открывайте рапорт через уведомление о новом рапорте (там есть кнопки ✅/❌).",
        reply_markup=admin_menu_inline(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("r:accept:"))
async def accept_report(cb: CallbackQuery, session: AsyncSession, sheets, config: Config) -> None:
    admin = await get_or_create_user(session, cb.from_user.id)
    if not admin.is_admin:
        await cb.answer("Нет доступа.", show_alert=True)
        return

    report_id = int(cb.data.split(":")[-1])
    report = await set_report_status(session, report_id, ReportStatus.ACCEPTED, admin_comment=None)
    if report is None:
        await cb.answer("Рапорт не найден.", show_alert=True)
        return

    try:
        await cb.bot.send_message(report.user.tg_id, f"Ваш рапорт <b>#{report.id}</b> принят ✅")
    except Exception:
        pass

    try:
        admins = await list_admins(session)
        admin_ids = {a.tg_id for a in admins} | set(config.admin_ids)
        admin_ids.discard(admin.tg_id)
        who = _admin_display_name(admin)
        when = now_local().strftime("%d.%m.%Y %H:%M")
        note = f"Рапорт <b>#{report.id}</b> принят админом: {who}\nВремя: {when}"
        for aid in admin_ids:
            try:
                await cb.bot.send_message(aid, note)
            except Exception:
                pass
    except Exception:
        pass

    if sheets is not None:
        try:
            sheets.append_report_status({
                "event": "report_status",
                "changed_at_utc": __import__("datetime").datetime.utcnow().isoformat(),
                "report_id": report.id,
                "status": "accepted",
                "admin_tg_id": admin.tg_id,
                "admin_comment": None,
            })
        except Exception:
            pass

    if sheets is not None:
        try:
            full = await get_report_with_user_and_tasks(session, report.id)
            if full is not None:
                payload = {
                    "event": "report_created",
                    "created_at_utc": full.created_at.isoformat(),
                    "report_id": full.id,
                    "tg_id": full.user.tg_id,
                    "first_name": full.user.first_name,
                    "last_name": full.user.last_name,
                    "position": full.user.position,
                    "city": full.user.city,
                    "partner_name": full.partner_name,
                    "report_date": full.report_date.isoformat(),
                    "start_time": full.start_time.strftime("%H:%M"),
                    "end_time": full.end_time.strftime("%H:%M"),
                    "tasks": [{"type": t.work_type.name, "quantity": t.quantity} for t in full.tasks],
                    "comment": full.comment,
                    "media": [{"file_id": m.file_id, "media_type": m.media_type.value} for m in full.media],
                    "status": full.status.value,
                    "edit_count": full.edit_count,
                    "edited_at_utc": full.edited_at.isoformat() if full.edited_at else None,
                    "edited_by_tg_id": None,
                }
                sheets.append_report(payload)
        except Exception:
            pass

    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await cb.answer("Принято.")


@router.callback_query(F.data.startswith("r:reject:"))
async def reject_report(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    admin = await get_or_create_user(session, cb.from_user.id)
    if not admin.is_admin:
        await cb.answer("Нет доступа.", show_alert=True)
        return

    report_id = int(cb.data.split(":")[-1])
    await state.set_state(AdminReject.comment)
    await state.update_data(report_id=report_id)
    await cb.message.answer(f"Введите комментарий для отклонения рапорта <b>#{report_id}</b> (обязательно):")
    await cb.answer()


@router.message(AdminReject.comment, F.text)
async def reject_comment(message, state: FSMContext, session: AsyncSession, sheets) -> None:
    admin = await get_or_create_user(session, message.from_user.id)
    if not admin.is_admin:
        await state.clear()
        await message.answer("Нет доступа.")
        return

    data = await state.get_data()
    report_id = int(data["report_id"])
    comment = message.text.strip()
    if len(comment) < 2:
        await message.answer("Комментарий слишком короткий. Введите ещё раз:")
        return

    report = await set_report_status(session, report_id, ReportStatus.REJECTED, admin_comment=comment)
    if report is None:
        await message.answer("Рапорт не найден.")
        await state.clear()
        return

    try:
        await message.bot.send_message(report.user.tg_id, f"Ваш рапорт <b>#{report.id}</b> отклонён ❌\nКомментарий: {comment}")
    except Exception:
        pass

    if sheets is not None:
        try:
            sheets.append_report_status({
                "event": "report_status",
                "changed_at_utc": __import__("datetime").datetime.utcnow().isoformat(),
                "report_id": report.id,
                "status": "rejected",
                "admin_tg_id": admin.tg_id,
                "admin_comment": comment,
            })
        except Exception:
            pass

    await message.answer(f"Готово. Рапорт <b>#{report.id}</b> отклонён.")
    await state.clear()
