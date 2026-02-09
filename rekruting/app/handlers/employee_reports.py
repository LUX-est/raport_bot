from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Config
from ..repositories import (
    get_or_create_user,
    is_user_registered,
    list_active_work_types,
    get_setting_bool,
    create_report,
    list_admins,
    get_report_with_user_and_tasks,
    get_last_closed_session_for_date,
    link_session_to_report,
    update_report_with_log,
)
from ..states import ReportCreate
from ..keyboards import (
    main_menu_inline,
    work_types_select_inline,
    skip_inline,
    confirm_inline,
    report_review_inline,
    back_to_menu_inline,
)
from ..utils import parse_date, parse_time, detect_media, format_report_preview, format_admin_report
from ..texts import fmt_time
from ..enums import MediaType

router = Router()


async def _ask_work_types(message, state: FSMContext, session: AsyncSession) -> None:
    wts = await list_active_work_types(session)
    items = [(w.id, w.name) for w in wts]
    await state.update_data(selected_wt_ids=set())
    await message.answer(
        "Выберите тип(ы) работ (можно несколько), затем «Далее»:",
        reply_markup=work_types_select_inline(items, set()),
    )
    await state.set_state(ReportCreate.work_types)


@router.callback_query(F.data == "menu:report")
async def report_start_cb(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await _start_report(cb.message, cb.from_user.id, state, session, editing_report_id=None)
    await cb.answer()


@router.message(F.text == "Сдать рапорт")
async def report_start_msg(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _start_report(message, message.from_user.id, state, session, editing_report_id=None)


async def _start_report(message_obj, tg_id: int, state: FSMContext, session: AsyncSession, editing_report_id: int | None) -> None:
    user = await get_or_create_user(session, tg_id)
    if not await is_user_registered(user):
        await message_obj.answer("Сначала заполните профиль через /start.")
        return

    await state.clear()
    if editing_report_id is not None:
        await state.update_data(editing_report_id=editing_report_id)
        await message_obj.answer(f"Редактирование рапорта <b>#{editing_report_id}</b>. Заполним заново все поля.")
    await message_obj.answer("Введите дату (ДД.ММ.ГГГГ) или напишите «сегодня»:", reply_markup=back_to_menu_inline())
    await state.set_state(ReportCreate.date)


@router.message(ReportCreate.date, F.text)
async def report_date(message: Message, state: FSMContext, session: AsyncSession) -> None:
    d = parse_date(message.text)
    if d is None:
        await message.answer("Не понял дату. Пример: 10.01.2026 или «сегодня». Попробуйте ещё раз:")
        return

    await state.update_data(report_date=d)

    await message.answer("Введите имя напарника (можно пропустить):", reply_markup=skip_inline("r:skip_partner"))
    await state.set_state(ReportCreate.partner_name)


@router.callback_query(ReportCreate.partner_name, F.data == "r:skip_partner")
async def report_skip_partner(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.update_data(partner_name=None)
    await _ask_work_types(cb.message, state, session)
    await cb.answer()


@router.message(ReportCreate.partner_name, F.text)
async def report_partner_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    name = (message.text or "").strip()
    await state.update_data(partner_name=name if name else None)
    await _ask_work_types(message, state, session)


@router.callback_query(ReportCreate.work_types, F.data.startswith("wt:toggle:"))
async def report_wt_toggle(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    wt_id = int(cb.data.split(":")[-1])
    data = await state.get_data()
    selected: set[int] = set(data.get("selected_wt_ids") or set())
    if wt_id in selected:
        selected.remove(wt_id)
    else:
        selected.add(wt_id)

    await state.update_data(selected_wt_ids=selected)

    wts = await list_active_work_types(session)
    items = [(w.id, w.name) for w in wts]
    await cb.message.edit_reply_markup(reply_markup=work_types_select_inline(items, selected))
    await cb.answer()


@router.callback_query(ReportCreate.work_types, F.data == "wt:next")
async def report_wt_next(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    selected: set[int] = set(data.get("selected_wt_ids") or set())
    if not selected:
        await cb.answer("Нужно выбрать хотя бы один тип работ.", show_alert=True)
        return

    wts = await list_active_work_types(session)
    id_to_name = {w.id: w.name for w in wts}
    selected_list = [wt_id for wt_id in selected if wt_id in id_to_name]

    await state.update_data(
        selected_wt_ids=selected_list,
        wt_index=0,
        tasks=[],
        id_to_name=id_to_name,
    )

    first_id = selected_list[0]
    await cb.message.answer(f"Введите количество для «<b>{id_to_name[first_id]}</b>» (целое число):")
    await state.set_state(ReportCreate.quantity)
    await cb.answer()


@router.message(ReportCreate.quantity, F.text)
async def report_quantity(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    selected_list: list[int] = data["selected_wt_ids"]
    idx: int = data["wt_index"]
    id_to_name: dict[int, str] = data["id_to_name"]
    tasks: list[tuple[int, int]] = data.get("tasks", [])

    try:
        qty = int(message.text.strip())
        if qty < 0:
            raise ValueError
    except ValueError:
        await message.answer("Количество должно быть целым числом ≥ 0. Введите ещё раз:")
        return

    wt_id = selected_list[idx]
    tasks.append((wt_id, qty))
    idx += 1

    if idx >= len(selected_list):
        await state.update_data(tasks=tasks, wt_index=idx)

        user = await get_or_create_user(session, message.from_user.id)
        ws = await get_last_closed_session_for_date(session, user.id, data["report_date"])
        if ws is not None:
            await state.update_data(
                start_time=ws.started_at.time().replace(second=0, microsecond=0),
                end_time=ws.ended_at.time().replace(second=0, microsecond=0) if ws.ended_at else ws.started_at.time(),
                work_session_id=ws.id,
            )
            await message.answer(
                f"Время подставлено автоматически: <b>{fmt_time(ws.started_at.time())}</b>–<b>{fmt_time(ws.ended_at.time())}</b>\n"
                "Комментарий (можно пропустить):",
                reply_markup=skip_inline("r:skip_comment"),
            )
            await state.set_state(ReportCreate.comment)
            return

        await message.answer("Введите время <b>начала</b> (HH:MM), например 09:30:")
        await state.set_state(ReportCreate.start_time)
        return

    await state.update_data(tasks=tasks, wt_index=idx)
    next_id = selected_list[idx]
    await message.answer(f"Введите количество для «<b>{id_to_name[next_id]}</b>» (целое число):")


@router.message(ReportCreate.start_time, F.text)
async def report_start_time(message: Message, state: FSMContext) -> None:
    t = parse_time(message.text)
    if t is None:
        await message.answer("Неверный формат. Пример: 09:30. Введите ещё раз:")
        return
    await state.update_data(start_time=t)
    await message.answer("Введите время <b>окончания</b> (HH:MM), например 18:10:")
    await state.set_state(ReportCreate.end_time)


@router.message(ReportCreate.end_time, F.text)
async def report_end_time(message: Message, state: FSMContext) -> None:
    t = parse_time(message.text)
    if t is None:
        await message.answer("Неверный формат. Пример: 18:10. Введите ещё раз:")
        return
    await state.update_data(end_time=t)
    await message.answer("Комментарий (можно пропустить):", reply_markup=skip_inline("r:skip_comment"))
    await state.set_state(ReportCreate.comment)


@router.callback_query(ReportCreate.comment, F.data == "r:skip_comment")
async def report_skip_comment(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.update_data(comment=None)
    photo_required = await get_setting_bool(session, "photo_required_reports")
    if photo_required:
        await cb.message.answer("Прикрепите фото/видео (обязательно по настройкам).")
    else:
        await cb.message.answer("Прикрепите фото/видео (можно пропустить):", reply_markup=skip_inline("r:skip_media"))
    await state.set_state(ReportCreate.media)
    await cb.answer()


@router.message(ReportCreate.comment, F.text)
async def report_comment(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.update_data(comment=message.text.strip() if message.text else None)
    photo_required = await get_setting_bool(session, "photo_required_reports")
    if photo_required:
        await message.answer("Прикрепите фото/видео (обязательно по настройкам).")
    else:
        await message.answer("Прикрепите фото/видео (можно пропустить):", reply_markup=skip_inline("r:skip_media"))
    await state.set_state(ReportCreate.media)


@router.callback_query(ReportCreate.media, F.data == "r:skip_media")
async def report_skip_media(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.update_data(media=None)
    await _send_report_preview(cb.message, cb.from_user.id, state, session)
    await cb.answer()


@router.message(ReportCreate.media)
async def report_media(message: Message, state: FSMContext, session: AsyncSession) -> None:
    media = detect_media(message)
    if media is None:
        photo_required = await get_setting_bool(session, "photo_required_reports")
        if photo_required:
            await message.answer("Нужно отправить фото или видео.")
        else:
            await message.answer("Отправьте фото/видео или нажмите «Пропустить».", reply_markup=skip_inline("r:skip_media"))
        return

    await state.update_data(media=media)
    await _send_report_preview(message, message.from_user.id, state, session)


async def _send_report_preview(message, tg_id: int, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    report_date = data["report_date"]
    partner_name = data.get("partner_name")
    start_time = data["start_time"]
    end_time = data["end_time"]
    comment = data.get("comment")
    tasks: list[tuple[int, int]] = data["tasks"]
    id_to_name: dict[int, str] = data["id_to_name"]

    tasks_named = [(id_to_name[wt_id], qty) for wt_id, qty in tasks]
    user = await get_or_create_user(session, tg_id)

    text = format_report_preview(user, report_date, start_time, end_time, tasks_named, partner_name, comment)

    if data.get("editing_report_id"):
        await message.answer(text, reply_markup=confirm_inline("r:confirm_edit", "r:cancel"))
    else:
        await message.answer(text, reply_markup=confirm_inline("r:confirm", "r:cancel"))
    await state.set_state(ReportCreate.confirm)


@router.callback_query(ReportCreate.confirm, F.data == "r:cancel")
async def report_cancel(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await get_or_create_user(session, cb.from_user.id)
    await state.clear()
    await cb.message.answer("Отменено.", reply_markup=main_menu_inline(is_working=user.is_working))
    await cb.answer()


@router.callback_query(ReportCreate.confirm, F.data == "r:confirm")
async def report_confirm(cb: CallbackQuery, state: FSMContext, session: AsyncSession, config: Config, sheets) -> None:
    data = await state.get_data()
    user = await get_or_create_user(session, cb.from_user.id, mark_admin=(cb.from_user.id in config.admin_ids))

    report = await create_report(
        session=session,
        user_id=user.id,
        report_date=data["report_date"],
        start_time=data["start_time"],
        end_time=data["end_time"],
        partner_name=data.get("partner_name"),
        comment=data.get("comment"),
        tasks=data["tasks"],
        media=data.get("media"),
    )

    ws_id = data.get("work_session_id")
    if ws_id:
        await link_session_to_report(session, int(ws_id), report.id)

    await state.clear()
    await cb.message.answer(f"Рапорт отправлен. Номер: <b>#{report.id}</b>", reply_markup=main_menu_inline(is_working=user.is_working))
    await cb.answer()

    if sheets is not None:
        try:
            payload = {
                "event": "report_created",
                "created_at_utc": report.created_at.isoformat(),
                "report_id": report.id,
                "tg_id": user.tg_id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "position": user.position,
                "city": user.city,
                "partner_name": report.partner_name,
                "report_date": report.report_date.isoformat(),
                "start_time": report.start_time.strftime("%H:%M"),
                "end_time": report.end_time.strftime("%H:%M"),
                "tasks": [{"type": t.work_type.name, "quantity": t.quantity} for t in report.tasks],
                "comment": report.comment,
                "media": [{"file_id": m.file_id, "media_type": m.media_type.value} for m in report.media],
                "status": report.status.value,
                "edit_count": report.edit_count,
                "edited_at_utc": report.edited_at.isoformat() if report.edited_at else None,
                "edited_by_tg_id": None,
            }
            sheets.append_report(payload)
        except Exception:
            pass

    admins = await list_admins(session)
    admin_ids = {a.tg_id for a in admins} | set(config.admin_ids)
    report_full = await get_report_with_user_and_tasks(session, report.id)
    if report_full is None:
        return

    tasks_lines = "\n".join([f"• {t.work_type.name}: <b>{t.quantity}</b>" for t in report_full.tasks]) or "-"
    admin_text = format_admin_report(report_full, tasks_lines)

    for admin_id in admin_ids:
        try:
            await cb.bot.send_message(admin_id, admin_text, reply_markup=report_review_inline(report.id))
            if report_full.media:
                m = report_full.media[0]
                if m.media_type == MediaType.PHOTO:
                    await cb.bot.send_photo(admin_id, photo=m.file_id)
                else:
                    await cb.bot.send_video(admin_id, video=m.file_id)
        except Exception:
            pass


@router.callback_query(ReportCreate.confirm, F.data == "r:confirm_edit")
async def report_confirm_edit(cb: CallbackQuery, state: FSMContext, session: AsyncSession, config: Config, sheets) -> None:
    data = await state.get_data()
    user = await get_or_create_user(session, cb.from_user.id, mark_admin=(cb.from_user.id in config.admin_ids))
    report_id = int(data["editing_report_id"])

    updated = await update_report_with_log(
        session=session,
        report_id=report_id,
        editor_user_id=user.id,
        report_date=data["report_date"],
        start_time=data["start_time"],
        end_time=data["end_time"],
        partner_name=data.get("partner_name"),
        comment=data.get("comment"),
        tasks=data["tasks"],
        media=data.get("media"),
    )
    await state.clear()
    await cb.message.answer(f"Рапорт <b>#{report_id}</b> обновлён.", reply_markup=main_menu_inline(is_working=user.is_working))
    await cb.answer()

    if updated is None:
        return

    if sheets is not None:
        try:
            payload = {
                "event": "report_edited",
                "edited_at_utc": updated.edited_at.isoformat() if updated.edited_at else None,
                "report_id": updated.id,
                "editor_tg_id": user.tg_id,
                "editor_name": f"{user.first_name} {user.last_name}",
                "edit_count": updated.edit_count,
            }
            sheets.append_report_edit(payload)
        except Exception:
            pass

    admins = await list_admins(session)
    admin_ids = {a.tg_id for a in admins} | set(config.admin_ids)
    try:
        msg = (
            f"✏️ Рапорт <b>#{updated.id}</b> отредактирован.\n"
            f"Кто: {user.first_name} {user.last_name} ({user.city})\n"
            f"Правок: <b>{updated.edit_count}</b>"
        )
        for admin_id in admin_ids:
            try:
                await cb.bot.send_message(admin_id, msg)
            except Exception:
                pass
    except Exception:
        pass
