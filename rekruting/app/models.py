from __future__ import annotations

from datetime import datetime, date, time

from sqlalchemy import (
    String,
    Integer,
    Date,
    Time,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
    Enum,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .enums import ReportStatus, ProblemUrgency, MediaType


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)

    first_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    position: Mapped[str | None] = mapped_column(String(128), nullable=True)
    city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    leader: Mapped[str | None] = mapped_column(String(128), nullable=True)

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_working: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    work_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    reports: Mapped[list["Report"]] = relationship(back_populates="user")
    problems: Mapped[list["Problem"]] = relationship(back_populates="user")
    work_sessions: Mapped[list["WorkSession"]] = relationship(back_populates="user")


class WorkType(Base):
    __tablename__ = "work_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    partner_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status"),
        default=ReportStatus.PENDING,
        nullable=False,
    )
    admin_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    edit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    edited_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="reports")
    tasks: Mapped[list["ReportTask"]] = relationship(back_populates="report", cascade="all, delete-orphan")
    media: Mapped[list["ReportMedia"]] = relationship(back_populates="report", cascade="all, delete-orphan")
    edits: Mapped[list["ReportEditLog"]] = relationship(back_populates="report", cascade="all, delete-orphan")


class ReportTask(Base):
    __tablename__ = "report_tasks"
    __table_args__ = (UniqueConstraint("report_id", "work_type_id", name="uq_report_task"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    work_type_id: Mapped[int] = mapped_column(ForeignKey("work_types.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    report: Mapped["Report"] = relationship(back_populates="tasks")
    work_type: Mapped["WorkType"] = relationship()


class ReportMedia(Base):
    __tablename__ = "report_media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)

    file_id: Mapped[str] = mapped_column(String(256), nullable=False)
    media_type: Mapped[MediaType] = mapped_column(Enum(MediaType, name="media_type"), nullable=False)

    report: Mapped["Report"] = relationship(back_populates="media")


class ReportEditLog(Base):
    __tablename__ = "report_edit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    editor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    edited_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    old_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    new_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)

    report: Mapped["Report"] = relationship(back_populates="edits")


class WorkSession(Base):
    __tablename__ = "work_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    linked_report_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship(back_populates="work_sessions")


class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    problem_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    scooter_number: Mapped[str | None] = mapped_column(String(64), nullable=True)

    urgency: Mapped[ProblemUrgency] = mapped_column(Enum(ProblemUrgency, name="problem_urgency"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="problems")
    media: Mapped[list["ProblemMedia"]] = relationship(back_populates="problem", cascade="all, delete-orphan")


class ProblemMedia(Base):
    __tablename__ = "problem_media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"), index=True)

    file_id: Mapped[str] = mapped_column(String(256), nullable=False)
    media_type: Mapped[MediaType] = mapped_column(Enum(MediaType, name="media_type"), nullable=False)

    problem: Mapped["Problem"] = relationship(back_populates="media")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(2048), nullable=False)
