from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Config
from ..repositories import (
    get_or_create_user,
    is_user_registered,
    get_setting_bool,
    create_problem,
    list_admins,
)
from ..states import ProblemCreate
from ..keyboards import main_menu_inline, problem_type_inline, skip_inline, done_inline, urgency_inline, confirm_inline, back_to_menu_inline
from ..utils import detect_media, format_problem_preview
from ..enums import MediaType, ProblemUrgency

router = Router()


@router.callback_query(F.data == "menu:problem")
async def problem_start_cb(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await _start(cb.message, cb.from_user.id, state, session)
    await cb.answer()


@router.message(F.text == "Сообщить о проблеме")
async def problem_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _start(message, message.from_user.id, state, session)


async def _start(message_obj, tg_id: int, state: FSMContext, session: AsyncSession) -> None:
    user = await get_or_create_user(session, tg_id)
    if not await is_user_registered(user):
        await message_obj.answer("Сначала заполните профиль через /start.")
        return

    await state.clear()
    await message_obj.answer("Выберите тип проблемы:", reply_markup=problem_type_inline())
    await state.set_state(ProblemCreate.ptype)


@router.callback_query(ProblemCreate.ptype, F.data.startswith("p:type:"))
async def problem_type(cb: CallbackQuery, state: FSMContext) -> None:
    parts = cb.data.split(":", 3)
    ptype = parts[-1]
    await state.update_data(problem_type=ptype)
    await cb.message.answer("Кратко опишите проблему текстом:", reply_markup=back_to_menu_inline())
    await state.set_state(ProblemCreate.description)
    await cb.answer()


@router.message(ProblemCreate.description, F.text)
async def problem_desc(message: Message, state: FSMContext) -> None:
    txt = message.text.strip()
    if len(txt) < 3:
        await message.answer("Опишите чуть подробнее (минимум 3 символа):")
        return
    await state.update_data(description=txt)
    await message.answer("Локация / объект (адрес или описание места):")
    await state.set_state(ProblemCreate.address)


@router.message(ProblemCreate.address, F.text)
async def problem_address(message: Message, state: FSMContext) -> None:
    addr = message.text.strip()
    if len(addr) < 3:
        await message.answer("Укажите адрес/объект (минимум 3 символа):")
        return
    await state.update_data(address=addr)
    await message.answer("Номер самоката (если есть, можно пропустить):", reply_markup=skip_inline("p:skip_scooter"))
    await state.set_state(ProblemCreate.scooter_number)


@router.callback_query(ProblemCreate.scooter_number, F.data == "p:skip_scooter")
async def problem_skip_scooter(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.update_data(scooter_number=None, media=[])
    await _ask_problem_media(cb.message, state, session)
    await cb.answer()


@router.message(ProblemCreate.scooter_number, F.text)
async def problem_scooter(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.update_data(scooter_number=message.text.strip(), media=[])
    await _ask_problem_media(message, state, session)


async def _ask_problem_media(message: Message, state: FSMContext, session: AsyncSession) -> None:
    required = await get_setting_bool(session, "photo_required_problems")
    if required:
        await message.answer("Прикрепите 1–5 фото/видео (обязательно по настройкам). Отправляйте файлами.")
    else:
        await message.answer("Прикрепите 0–5 фото/видео. Отправляйте файлами или нажмите «Пропустить».",
                             reply_markup=skip_inline("p:skip_media"))
    await state.set_state(ProblemCreate.media)


@router.callback_query(ProblemCreate.media, F.data == "p:skip_media")
async def problem_skip_media(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(media=[])
    await cb.message.answer("Выберите срочность:", reply_markup=urgency_inline())
    await state.set_state(ProblemCreate.urgency)
    await cb.answer()


@router.callback_query(ProblemCreate.media, F.data == "p:media_done")
async def problem_media_done(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.message.answer("Выберите срочность:", reply_markup=urgency_inline())
    await state.set_state(ProblemCreate.urgency)
    await cb.answer()


@router.message(ProblemCreate.media)
async def problem_media_collect(message: Message, state: FSMContext, session: AsyncSession) -> None:
    media_item = detect_media(message)
    data = await state.get_data()
    media_list: list[tuple[str, str]] = data.get("media", [])

    required = await get_setting_bool(session, "photo_required_problems")

    if media_item is None:
        if required and not media_list:
            await message.answer("Нужно отправить хотя бы 1 фото или видео.")
        else:
            await message.answer(
                "Отправьте фото/видео, или нажмите «Готово».",
                reply_markup=done_inline("p:media_done", "p:skip_media" if not required and not media_list else None),
            )
        return

    if len(media_list) >= 5:
        await message.answer("Максимум 5 файлов. Нажмите «Готово».", reply_markup=done_inline("p:media_done"))
        return

    file_id, mtype = media_item
    media_list.append((file_id, mtype.value))
    await state.update_data(media=media_list)

    if len(media_list) >= 5:
        await message.answer("Добавлено 5/5. Нажмите «Готово».", reply_markup=done_inline("p:media_done"))
    else:
        await message.answer(f"Добавлено {len(media_list)}/5. Отправьте ещё файл или нажмите «Готово».",
                             reply_markup=done_inline("p:media_done"))


@router.callback_query(ProblemCreate.urgency, F.data.startswith("p:urgency:"))
async def problem_urgency(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    code = cb.data.split(":")[-1]
    urgency = {
        "urgent": ProblemUrgency.URGENT,
        "medium": ProblemUrgency.MEDIUM,
        "low": ProblemUrgency.LOW,
    }.get(code)
    if urgency is None:
        await cb.answer("Неизвестная срочность.", show_alert=True)
        return

    await state.update_data(urgency=urgency)

    data = await state.get_data()
    user = await get_or_create_user(session, cb.from_user.id)

    preview = format_problem_preview(
        user=user,
        ptype=data["problem_type"],
        desc=data["description"],
        address=data["address"],
        scooter=data.get("scooter_number"),
        urgency=urgency,
        media_count=len(data.get("media", [])),
    )
    await cb.message.answer(preview, reply_markup=confirm_inline("p:confirm", "p:cancel"))
    await state.set_state(ProblemCreate.confirm)
    await cb.answer()


@router.callback_query(ProblemCreate.confirm, F.data == "p:cancel")
async def problem_cancel(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await get_or_create_user(session, cb.from_user.id)
    await state.clear()
    await cb.message.answer("Отменено.", reply_markup=main_menu_inline(is_working=user.is_working))
    await cb.answer()


@router.callback_query(ProblemCreate.confirm, F.data == "p:confirm")
async def problem_confirm(cb: CallbackQuery, state: FSMContext, session: AsyncSession, config: Config, sheets) -> None:
    data = await state.get_data()
    user = await get_or_create_user(session, cb.from_user.id, mark_admin=(cb.from_user.id in config.admin_ids))

    media_list_raw: list[tuple[str, str]] = data.get("media", [])
    media_list = [(fid, MediaType(mtype)) for fid, mtype in media_list_raw]

    problem = await create_problem(
        session=session,
        user_id=user.id,
        problem_type=data["problem_type"],
        description=data["description"],
        address=data["address"],
        scooter_number=data.get("scooter_number"),
        urgency=data["urgency"],
        media=media_list,
    )

    await state.clear()
    await cb.message.answer(f"Сообщение отправлено. Номер: <b>#{problem.id}</b>", reply_markup=main_menu_inline(is_working=user.is_working))
    await cb.answer()

    if sheets is not None:
        try:
            uname = cb.from_user.username
            payload = {
                "event": "problem_created",
                "created_at_utc": problem.created_at.isoformat(),
                "problem_id": problem.id,
                "tg_id": user.tg_id,
                "tg_username": uname,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "position": user.position,
                "city": user.city,
                "problem_type": problem.problem_type,
                "description": problem.description,
                "address": problem.address,
                "scooter_number": problem.scooter_number,
                "urgency": data["urgency"].value,
                "media": [{"file_id": fid, "media_type": mt.value} for fid, mt in media_list],
            }
            sheets.append_problem(payload)
        except Exception:
            pass

    admins = await list_admins(session)
    admin_ids = {a.tg_id for a in admins} | set(config.admin_ids)
    display_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or str(user.tg_id)
    name_link = f"<a href=\"tg://user?id={user.tg_id}\">{display_name}</a>"
    uname = cb.from_user.username
    contact = f"@{uname}" if uname else f"<a href=\"tg://user?id={user.tg_id}\">написать</a>"
    text = (
        f"<b>Новая проблема #{problem.id}</b>\n\n"
        f"Сотрудник: {name_link} ({user.position}, {user.city})\n"
        f"Контакт: {contact}\n"
        f"Тип: <b>{problem.problem_type}</b>\n"
        f"Описание: {problem.description}\n"
        f"Адрес/объект: {problem.address}\n"
        f"Номер самоката: {problem.scooter_number if problem.scooter_number else '-'}\n"
        f"Срочность: <b>{data['urgency'].value}</b>\n"
        f"Вложений: <b>{len(media_list)}</b>"
    )

    for admin_id in admin_ids:
        try:
            await cb.bot.send_message(admin_id, text)
            for fid, mtype in media_list:
                if mtype == MediaType.PHOTO:
                    await cb.bot.send_photo(admin_id, photo=fid)
                else:
                    await cb.bot.send_video(admin_id, video=fid)
        except Exception:
            pass
