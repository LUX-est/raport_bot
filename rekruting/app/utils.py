from __future__ import annotations

from datetime import datetime, date, time

from .enums import MediaType
from .texts import fmt_date, fmt_time, human_report_status, human_urgency


def parse_date(text: str) -> date | None:
    t = text.strip().lower()
    if t in {"сегодня", "today"}:
        return date.today()
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return None


def parse_time(text: str) -> time | None:
    t = text.strip()
    try:
        return datetime.strptime(t, "%H:%M").time()
    except ValueError:
        return None


def detect_media(message) -> tuple[str, MediaType] | None:
    if message.photo:
        return message.photo[-1].file_id, MediaType.PHOTO
    if message.video:
        return message.video.file_id, MediaType.VIDEO
    return None


def format_report_preview(
    user,
    report_date,
    start_time,
    end_time,
    tasks_named: list[tuple[str, int]],
    partner_name: str | None,
    comment: str | None,
) -> str:
    tasks_lines = "\n".join([f"• {name}: <b>{qty}</b>" for name, qty in tasks_named]) or "-"
    return (
        f"<b>Предпросмотр рапорта</b>\n\n"
        f"Сотрудник: {user.first_name} {user.last_name} ({user.position}, {user.city})\n"
        f"Напарник: {partner_name if partner_name else '-'}\n"
        f"Дата: <b>{fmt_date(report_date)}</b>\n"
        f"Время: <b>{fmt_time(start_time)}–{fmt_time(end_time)}</b>\n"
        f"Типы работ/кол-во:\n{tasks_lines}\n"
        f"Комментарий: {comment if comment else '-'}"
    )


def format_problem_preview(user, ptype: str, desc: str, address: str, scooter: str | None, urgency, media_count: int) -> str:
    return (
        f"<b>Предпросмотр проблемы</b>\n\n"
        f"Сотрудник: {user.first_name} {user.last_name} ({user.position}, {user.city})\n"
        f"Тип: <b>{ptype}</b>\n"
        f"Описание: {desc}\n"
        f"Адрес/объект: {address}\n"
        f"Номер самоката: {scooter if scooter else '-'}\n"
        f"Срочность: <b>{human_urgency(urgency)}</b>\n"
        f"Вложений: <b>{media_count}</b>"
    )


def format_admin_report(report, tasks_lines: str) -> str:
    u = report.user
    return (
        f"<b>Новый рапорт #{report.id}</b>\n\n"
        f"Сотрудник: {u.first_name} {u.last_name} ({u.position}, {u.city})\n"
        f"Напарник: {report.partner_name if report.partner_name else '-'}\n"
        f"Дата: <b>{fmt_date(report.report_date)}</b>\n"
        f"Время: <b>{fmt_time(report.start_time)}–{fmt_time(report.end_time)}</b>\n"
        f"Типы работ/кол-во:\n{tasks_lines}\n"
        f"Комментарий: {report.comment if report.comment else '-'}\n"
        f"Статус: <b>{human_report_status(report.status)}</b>"
    )
