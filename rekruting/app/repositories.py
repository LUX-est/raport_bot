from __future__ import annotations

import json
from datetime import date as dt_date, datetime, time as dt_time
from zoneinfo import ZoneInfo

_TZ = ZoneInfo("Europe/Warsaw")

def now_local() -> datetime:
    return datetime.now(tz=_TZ).replace(tzinfo=None)


from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    User,
    WorkType,
    Report,
    ReportTask,
    ReportMedia,
    Problem,
    ProblemMedia,
    Setting,
    WorkSession,
    ReportEditLog,
)
from .enums import ReportStatus, MediaType, ProblemUrgency


DEFAULT_WORK_TYPES = [
    "сбор на зарядку",
    "перестановка",
    "деплой",
    "замена батарей",
    "ремонт",
]

DEFAULT_SETTINGS = {
    "photo_required_reports": "0",
    "photo_required_problems": "0",
    "motd": "",
}


async def get_or_create_user(session: AsyncSession, tg_id: int, *, mark_admin: bool = False) -> User:
    user = (await session.execute(select(User).where(User.tg_id == tg_id))).scalar_one_or_none()
    if user is None:
        user = User(tg_id=tg_id, is_admin=mark_admin)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    else:
        if mark_admin and not user.is_admin:
            user.is_admin = True
            await session.commit()
    return user


async def is_user_registered(user: User) -> bool:
    return bool(user.first_name and user.last_name and user.position and user.phone and user.leader and user.city)


async def seed_defaults(session: AsyncSession) -> None:
    existing = (await session.execute(select(Setting))).scalars().all()
    if not existing:
        for k, v in DEFAULT_SETTINGS.items():
            session.add(Setting(key=k, value=v))
        await session.commit()
    else:
        existing_keys = {s.key for s in existing}
        for k, v in DEFAULT_SETTINGS.items():
            if k not in existing_keys:
                session.add(Setting(key=k, value=v))
        await session.commit()

    cnt = (await session.execute(select(func.count(WorkType.id)))).scalar_one()
    if cnt == 0:
        for name in DEFAULT_WORK_TYPES:
            session.add(WorkType(name=name, is_active=True))
        await session.commit()



async def get_setting_bool(session: AsyncSession, key: str) -> bool:
    row = (await session.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
    if row is None:
        return False
    return row.value.strip() in {"1", "true", "True", "yes", "да"}


async def set_setting_bool(session: AsyncSession, key: str, value: bool) -> None:
    row = (await session.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
    if row is None:
        session.add(Setting(key=key, value="1" if value else "0"))
    else:
        row.value = "1" if value else "0"
    await session.commit()


async def get_setting_text(session: AsyncSession, key: str) -> str:
    row = (await session.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
    return (row.value if row else "").strip()


async def set_setting_text(session: AsyncSession, key: str, value: str) -> None:
    row = (await session.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value
    await session.commit()



async def list_active_work_types(session: AsyncSession) -> list[WorkType]:
    return (await session.execute(select(WorkType).where(WorkType.is_active.is_(True)).order_by(WorkType.id))).scalars().all()


async def add_work_type(session: AsyncSession, name: str) -> WorkType:
    name = name.strip().lower()
    wt = (await session.execute(select(WorkType).where(WorkType.name == name))).scalar_one_or_none()
    if wt is None:
        wt = WorkType(name=name, is_active=True)
        session.add(wt)
    else:
        wt.is_active = True
    await session.commit()
    await session.refresh(wt)
    return wt



async def start_work(session: AsyncSession, user: User) -> WorkSession:
    open_ws = (await session.execute(
        select(WorkSession).where(WorkSession.user_id == user.id).where(WorkSession.ended_at.is_(None))
    )).scalar_one_or_none()
    if open_ws is not None:
        user.is_working = True
        user.work_started_at = open_ws.started_at
        await session.commit()
        return open_ws

    now = now_local()
    ws = WorkSession(user_id=user.id, started_at=now, ended_at=None, linked_report_id=None)
    session.add(ws)
    user.is_working = True
    user.work_started_at = now
    await session.commit()
    await session.refresh(ws)
    return ws


async def stop_work(session: AsyncSession, user: User) -> WorkSession | None:
    ws = (await session.execute(
        select(WorkSession).where(WorkSession.user_id == user.id).where(WorkSession.ended_at.is_(None))
        .order_by(WorkSession.started_at.desc())
    )).scalar_one_or_none()
    if ws is None:
        user.is_working = False
        user.work_started_at = None
        await session.commit()
        return None

    now = now_local()
    ws.ended_at = now
    user.is_working = False
    user.work_started_at = None
    await session.commit()
    await session.refresh(ws)
    return ws


async def get_last_closed_session_for_date(session: AsyncSession, user_id: int, report_date: dt_date) -> WorkSession | None:
    rows = (await session.execute(
        select(WorkSession)
        .where(WorkSession.user_id == user_id)
        .where(WorkSession.ended_at.is_not(None))
        .where(WorkSession.linked_report_id.is_(None))
        .order_by(WorkSession.ended_at.desc())
        .limit(10)
    )).scalars().all()

    for ws in rows:
        if ws.started_at.date() == report_date:
            return ws
    return None


async def link_session_to_report(session: AsyncSession, work_session_id: int, report_id: int) -> None:
    ws = (await session.execute(select(WorkSession).where(WorkSession.id == work_session_id))).scalar_one_or_none()
    if ws is None:
        return
    ws.linked_report_id = report_id
    await session.commit()



async def create_report(
    session: AsyncSession,
    user_id: int,
    report_date: dt_date,
    start_time: dt_time,
    end_time: dt_time,
    partner_name: str | None,
    comment: str | None,
    tasks: list[tuple[int, int]],  
    media: tuple[str, MediaType] | None,
) -> Report:
    report = Report(
        user_id=user_id,
        report_date=report_date,
        start_time=start_time,
        end_time=end_time,
        partner_name=partner_name,
        comment=comment,
        status=ReportStatus.PENDING,
    )
    session.add(report)
    await session.flush()  

    for wt_id, qty in tasks:
        session.add(ReportTask(report_id=report.id, work_type_id=wt_id, quantity=qty))

    if media is not None:
        file_id, media_type = media
        session.add(ReportMedia(report_id=report.id, file_id=file_id, media_type=media_type))

    await session.commit()
    await session.refresh(report)
    await session.refresh(report, attribute_names=["user", "tasks", "media"])
    for t in report.tasks:
        await session.refresh(t, attribute_names=["work_type"])
    return report


async def get_report_with_user_and_tasks(session: AsyncSession, report_id: int) -> Report | None:
    report = (await session.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if report is None:
        return None
    await session.refresh(report, attribute_names=["user", "tasks", "media"])
    for t in report.tasks:
        await session.refresh(t, attribute_names=["work_type"])
    return report


async def list_user_reports(session: AsyncSession, user_id: int, limit: int = 10) -> list[Report]:
    return (await session.execute(
        select(Report).where(Report.user_id == user_id).order_by(Report.created_at.desc()).limit(limit)
    )).scalars().all()


async def sum_user_tasks_for_month(session: AsyncSession, user_id: int, year: int, month: int) -> int:
    start = dt_date(year, month, 1)
    end = dt_date(year + 1, 1, 1) if month == 12 else dt_date(year, month + 1, 1)

    total = (await session.execute(
        select(func.coalesce(func.sum(ReportTask.quantity), 0))
        .join(Report, Report.id == ReportTask.report_id)
        .where(Report.user_id == user_id)
        .where(Report.report_date >= start)
        .where(Report.report_date < end)
    )).scalar_one()
    return int(total or 0)


async def list_pending_reports(session: AsyncSession, limit: int = 20) -> list[Report]:
    return (await session.execute(
        select(Report).where(Report.status == ReportStatus.PENDING).order_by(Report.created_at.desc()).limit(limit)
    )).scalars().all()


async def list_recent_reports(session: AsyncSession, limit: int = 20) -> list[Report]:
    rows = (await session.execute(
        select(Report).order_by(Report.created_at.desc()).limit(limit)
    )).scalars().all()
    for r in rows:
        await session.refresh(r, attribute_names=["user"])
    return rows


async def list_recent_report_edits(session: AsyncSession, limit: int = 20) -> list[tuple[ReportEditLog, User]]:
    rows = (await session.execute(
        select(ReportEditLog, User)
        .join(User, User.id == ReportEditLog.editor_user_id)
        .order_by(ReportEditLog.edited_at.desc())
        .limit(limit)
    )).all()
    return [(log, user) for (log, user) in rows]


async def list_recent_problems(session: AsyncSession, limit: int = 20) -> list[Problem]:
    rows = (await session.execute(
        select(Problem).order_by(Problem.created_at.desc()).limit(limit)
    )).scalars().all()
    for p in rows:
        await session.refresh(p, attribute_names=["user"])
    return rows


async def set_report_status(session: AsyncSession, report_id: int, status: ReportStatus, admin_comment: str | None) -> Report | None:
    report = (await session.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if report is None:
        return None
    report.status = status
    report.admin_comment = admin_comment
    await session.commit()
    await session.refresh(report, attribute_names=["user"])
    return report


async def _snapshot_report(session: AsyncSession, report_id: int) -> dict:
    rep = await get_report_with_user_and_tasks(session, report_id)
    if rep is None:
        return {}
    return {
        "id": rep.id,
        "user_id": rep.user_id,
        "report_date": rep.report_date.isoformat(),
        "start_time": rep.start_time.strftime("%H:%M"),
        "end_time": rep.end_time.strftime("%H:%M"),
        "partner_name": rep.partner_name,
        "comment": rep.comment,
        "status": rep.status.value,
        "admin_comment": rep.admin_comment,
        "tasks": [{"work_type_id": t.work_type_id, "work_type": t.work_type.name, "quantity": t.quantity} for t in rep.tasks],
        "media": [{"file_id": m.file_id, "media_type": m.media_type.value} for m in rep.media],
        "edit_count": rep.edit_count,
        "edited_at": rep.edited_at.isoformat() if rep.edited_at else None,
        "edited_by_user_id": rep.edited_by_user_id,
    }


async def update_report_with_log(
    session: AsyncSession,
    report_id: int,
    editor_user_id: int,
    report_date: dt_date,
    start_time: dt_time,
    end_time: dt_time,
    partner_name: str | None,
    comment: str | None,
    tasks: list[tuple[int, int]],
    media: tuple[str, MediaType] | None,
) -> Report | None:
    report = (await session.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if report is None:
        return None

    old = await _snapshot_report(session, report_id)

    report.report_date = report_date
    report.start_time = start_time
    report.end_time = end_time
    report.partner_name = partner_name
    report.comment = comment

    await session.execute(delete(ReportTask).where(ReportTask.report_id == report_id))
    await session.execute(delete(ReportMedia).where(ReportMedia.report_id == report_id))

    for wt_id, qty in tasks:
        session.add(ReportTask(report_id=report_id, work_type_id=wt_id, quantity=qty))

    if media is not None:
        file_id, media_type = media
        session.add(ReportMedia(report_id=report_id, file_id=file_id, media_type=media_type))

    report.edit_count += 1
    report.edited_at = datetime.utcnow()
    report.edited_by_user_id = editor_user_id

    new = {
        **old,
        "report_date": report_date.isoformat(),
        "start_time": start_time.strftime("%H:%M"),
        "end_time": end_time.strftime("%H:%M"),
        "partner_name": partner_name,
        "comment": comment,
        "tasks": [{"work_type_id": wt_id, "quantity": qty} for wt_id, qty in tasks],
        "media": [{"file_id": media[0], "media_type": media[1].value}] if media else [],
        "edit_count": report.edit_count,
        "edited_at": report.edited_at.isoformat() if report.edited_at else None,
        "edited_by_user_id": report.edited_by_user_id,
    }
    session.add(ReportEditLog(
        report_id=report_id,
        editor_user_id=editor_user_id,
        old_snapshot_json=json.dumps(old, ensure_ascii=False),
        new_snapshot_json=json.dumps(new, ensure_ascii=False),
    ))

    await session.commit()
    await session.refresh(report)
    await session.refresh(report, attribute_names=["user", "tasks", "media"])
    for t in report.tasks:
        await session.refresh(t, attribute_names=["work_type"])
    return report



async def create_problem(
    session: AsyncSession,
    user_id: int,
    problem_type: str,
    description: str,
    address: str,
    scooter_number: str | None,
    urgency: ProblemUrgency,
    media: list[tuple[str, MediaType]],
) -> Problem:
    p = Problem(
        user_id=user_id,
        problem_type=problem_type,
        description=description,
        address=address,
        scooter_number=scooter_number,
        urgency=urgency,
    )
    session.add(p)
    await session.flush()

    for file_id, media_type in media:
        session.add(ProblemMedia(problem_id=p.id, file_id=file_id, media_type=media_type))

    await session.commit()
    await session.refresh(p)
    await session.refresh(p, attribute_names=["user", "media"])
    return p



async def list_admins(session: AsyncSession) -> list[User]:
    return (await session.execute(select(User).where(User.is_admin.is_(True)))).scalars().all()


async def list_workers(session: AsyncSession, limit: int = 50) -> list[User]:
    return (await session.execute(
        select(User).order_by(User.created_at.desc()).limit(limit)
    )).scalars().all()
