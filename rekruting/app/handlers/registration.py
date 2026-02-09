from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from ..keyboards import city_pick_inline, contact_request_kb, main_menu_inline
from ..repositories import get_or_create_user
from ..states import Registration

router = Router()


@router.message(Registration.first_name, F.text)
async def reg_first_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await get_or_create_user(session, message.from_user.id)
    user.first_name = message.text.strip()
    await session.commit()

    await message.answer("Введите <b>фамилию</b>:")
    await state.set_state(Registration.last_name)


@router.message(Registration.last_name, F.text)
async def reg_last_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await get_or_create_user(session, message.from_user.id)
    user.last_name = message.text.strip()
    await session.commit()

    await message.answer("Введите <b>должность</b>:")
    await state.set_state(Registration.position)


@router.message(Registration.position, F.text)
async def reg_position(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await get_or_create_user(session, message.from_user.id)
    user.position = message.text.strip()
    await session.commit()

    await message.answer(
        "Отправьте <b>номер телефона</b>, привязанный к Telegram, кнопкой ниже:",
        reply_markup=contact_request_kb(),
    )
    await state.set_state(Registration.phone)


@router.message(Registration.phone, F.contact)
async def reg_phone(message: Message, state: FSMContext, session: AsyncSession) -> None:
    contact = message.contact
    if contact.user_id != message.from_user.id:
        await message.answer(
            "Нужно отправить свой контакт, привязанный к Telegram. Нажмите кнопку ниже.",
            reply_markup=contact_request_kb(),
        )
        return

    user = await get_or_create_user(session, message.from_user.id)
    user.phone = (contact.phone_number or "").strip()
    await session.commit()

    await message.answer("Укажите <b>лидера</b> (с кем контакт):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Registration.leader)


@router.message(Registration.phone)
async def reg_phone_invalid(message: Message) -> None:
    await message.answer(
        "Нужно отправить номер телефона через кнопку, чтобы он был привязан к Telegram.",
        reply_markup=contact_request_kb(),
    )


@router.message(Registration.leader, F.text)
async def reg_leader(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await get_or_create_user(session, message.from_user.id)
    user.leader = message.text.strip()
    await session.commit()

    await message.answer("Выберите <b>город</b> кнопкой или введите вручную:", reply_markup=city_pick_inline())
    await state.set_state(Registration.city)


@router.callback_query(Registration.city, F.data.startswith("city:set:"))
async def reg_city_set(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    city = cb.data.split(":", 2)[-1].strip()
    user = await get_or_create_user(session, cb.from_user.id)
    user.city = city
    await session.commit()

    await state.clear()
    await cb.message.answer("Профиль сохранен. Выберите действие:", reply_markup=main_menu_inline(is_working=user.is_working))
    await cb.answer()


@router.callback_query(Registration.city, F.data == "city:manual")
async def reg_city_manual(cb: CallbackQuery) -> None:
    await cb.message.answer("Введите <b>город</b> текстом:")
    await cb.answer()


@router.callback_query(Registration.city, F.data == "city:location")
async def reg_city_location(cb: CallbackQuery) -> None:
    await cb.message.answer("Отправьте геолокацию сообщением: 📎 (скрепка) -> Геопозиция.")
    await cb.answer()


@router.message(Registration.city, F.location)
async def reg_city_location_msg(message: Message, state: FSMContext, session: AsyncSession) -> None:
    loc = message.location
    city = f"GPS {loc.latitude:.5f},{loc.longitude:.5f}"

    user = await get_or_create_user(session, message.from_user.id)
    user.city = city
    await session.commit()

    await state.clear()
    await message.answer("Профиль сохранен. Выберите действие:", reply_markup=main_menu_inline(is_working=user.is_working))


@router.message(Registration.city, F.text)
async def reg_city(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await get_or_create_user(session, message.from_user.id)
    user.city = message.text.strip()
    await session.commit()

    await state.clear()
    await message.answer("Профиль сохранен. Выберите действие:", reply_markup=main_menu_inline(is_working=user.is_working))
