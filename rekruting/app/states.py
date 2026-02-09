from __future__ import annotations
from aiogram.fsm.state import StatesGroup, State


class Registration(StatesGroup):
    first_name = State()
    last_name = State()
    position = State()
    phone = State()
    leader = State()
    city = State()


class ReportCreate(StatesGroup):
    date = State()
    partner_name = State()
    work_types = State()
    quantity = State()
    start_time = State()
    end_time = State()
    comment = State()
    media = State()
    confirm = State()


class ProblemCreate(StatesGroup):
    ptype = State()
    description = State()
    address = State()
    scooter_number = State()
    media = State()
    urgency = State()
    confirm = State()


class AdminReject(StatesGroup):
    comment = State()


class AdminAddWorkType(StatesGroup):
    name = State()


class AdminMotd(StatesGroup):
    text = State()


class AdminSendMessage(StatesGroup):
    text = State()
