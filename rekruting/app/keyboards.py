from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_inline(*, is_working: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if not is_working:
        kb.button(text="🟢 Начал работу", callback_data="work:start")
    else:
        kb.button(text="🔴 Закончить работу", callback_data="work:stop")

    kb.button(text="Сдать рапорт", callback_data="menu:report")
    kb.button(text="Сообщить о проблеме", callback_data="menu:problem")
    kb.button(text="Мои рапорты", callback_data="menu:history")
    kb.adjust(1, 2, 1)
    return kb.as_markup()


def back_to_menu_inline() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ В меню", callback_data="menu:main")
    return kb.as_markup()


def admin_menu_inline() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Рапорты на проверке", callback_data="admin:pending")
    kb.button(text="История рапортов", callback_data="admin:history:reports")
    kb.button(text="История изменений", callback_data="admin:history:edits")
    kb.button(text="История проблем", callback_data="admin:history:problems")
    kb.button(text="Настройки", callback_data="admin:settings")
    kb.button(text="Сообщение дня", callback_data="admin:motd")
    kb.button(text="Сотрудники", callback_data="admin:workers")
    kb.button(text="⬅️ В меню", callback_data="menu:main")
    kb.adjust(1)
    return kb.as_markup()


def skip_inline(action: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Пропустить", callback_data=action)
    return kb.as_markup()


def done_inline(done_action: str, skip_action: str | None = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Готово", callback_data=done_action)
    if skip_action:
        kb.button(text="Пропустить", callback_data=skip_action)
    kb.adjust(2)
    return kb.as_markup()


def confirm_inline(confirm: str, cancel: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Подтвердить и отправить", callback_data=confirm)
    kb.button(text="Отмена", callback_data=cancel)
    kb.adjust(1, 1)
    return kb.as_markup()


def work_types_select_inline(items: list[tuple[int, str]], selected: set[int]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for wt_id, name in items:
        mark = "✅ " if wt_id in selected else "☑️ "
        kb.button(text=f"{mark}{name}", callback_data=f"wt:toggle:{wt_id}")
    kb.button(text="Далее", callback_data="wt:next")
    kb.adjust(1)
    return kb.as_markup()


def report_review_inline(report_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Принять", callback_data=f"r:accept:{report_id}")
    kb.button(text="❌ Отклонить", callback_data=f"r:reject:{report_id}")
    kb.adjust(2)
    return kb.as_markup()


def settings_inline(photo_reports: bool, photo_problems: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=f"Фото в рапорте: {'обяз.' if photo_reports else 'не обяз.'}",
        callback_data="set:toggle:photo_required_reports",
    )
    kb.button(
        text=f"Фото в проблеме: {'обяз.' if photo_problems else 'не обяз.'}",
        callback_data="set:toggle:photo_required_problems",
    )
    kb.button(text="➕ Добавить тип работ", callback_data="set:add_work_type")
    kb.adjust(1)
    return kb.as_markup()


def problem_type_inline() -> InlineKeyboardMarkup:
    items = [
        "поломка техники",
        "ошибка в задании",
        "нету самоката",
        "проблема с приложением",
        "аварийная ситуация",
        "другое",
    ]
    kb = InlineKeyboardBuilder()
    for i, name in enumerate(items):
        kb.button(text=name, callback_data=f"p:type:{i}:{name}")
    kb.adjust(1)
    return kb.as_markup()


def urgency_inline() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔴 срочно", callback_data="p:urgency:urgent")
    kb.button(text="🟡 средне", callback_data="p:urgency:medium")
    kb.button(text="🟢 не срочно", callback_data="p:urgency:low")
    kb.adjust(1)
    return kb.as_markup()


def my_reports_inline(report_ids: list[int]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for rid in report_ids:
        kb.button(text=f"✏️ Редактировать #{rid}", callback_data=f"my:edit:{rid}")
    kb.button(text="⬅️ В меню", callback_data="menu:main")
    kb.adjust(1)
    return kb.as_markup()


def workers_inline(users: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for tg_id, label in users:
        kb.button(text=f"✉️ {label}", callback_data=f"admin:msg:{tg_id}")
    kb.button(text="⬅️ Назад", callback_data="admin:back")
    kb.adjust(1)
    return kb.as_markup()


def city_pick_inline() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📍 Варшава", callback_data="city:set:Варшава")
    kb.button(text="📍 Вроцлав", callback_data="city:set:Вроцлав")
    kb.button(text="✍️ Ввести вручную", callback_data="city:manual")
    kb.button(text="📌 Отправить местоположение", callback_data="city:location")
    kb.adjust(2, 2)
    return kb.as_markup()


def contact_request_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отправить номер телефона", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Нажмите кнопку, чтобы отправить контакт",
    )
