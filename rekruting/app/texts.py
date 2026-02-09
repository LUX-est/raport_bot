from __future__ import annotations
from datetime import date, time
from .enums import ReportStatus, ProblemUrgency


WELCOME_TEXT = (
    "Приветствую!\n\n"
    "Данный бот создан для оптимизации и дальнейшей коммуникации наших сотрудников с администрацией, коллегами.\n"
    "Здесь вы сможете задать свои вопросы, сдать ответы, получить бонусы и прочее.\n\n"
    "Прошу отнестись к боту с полной серьезностью так как это часть нашей экосистемы, благодаря которой мы будем всегда на связи и четко понимать и видеть наши усилия.\n\n"
    "Рады принять Вас в наши ряды.\n"
    "С уважением\n"
    "Администрация\n"
    "Good company"
)


def human_report_status(st: ReportStatus) -> str:
    return {
        ReportStatus.PENDING: "на проверке",
        ReportStatus.ACCEPTED: "принят",
        ReportStatus.REJECTED: "отклонён",
    }.get(st, st.value)


def human_urgency(u: ProblemUrgency) -> str:
    return {
        ProblemUrgency.URGENT: "🔴 срочно",
        ProblemUrgency.MEDIUM: "🟡 средне",
        ProblemUrgency.LOW: "🟢 не срочно",
    }.get(u, u.value)


def fmt_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def fmt_time(t: time) -> str:
    return t.strftime("%H:%M")
