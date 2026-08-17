import asyncio
import logging
import os
from datetime import date, datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from dotenv import load_dotenv

import database as db
import reminder_scheduler as sched
from keyboards import (
    done_keyboard,
    event_actions,
    events_keyboard,
    main_menu,
    repeat_keyboard,
)
from scheduler_logic import next_due_date
from states import NewEvent

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()

REPEAT_NAMES = {
    "monthly": "раз в месяц",
    "quarterly": "раз в квартал",
    "yearly": "раз в год",
    "none": "разово",
}


@dp.message(CommandStart())
async def start_handler(message: Message):
    db.ensure_user(message.from_user.id)
    await message.answer(
        "Напоминаю о делах, которые повторяются: счётчики, коммуналка, налоги.\n\n"
        "Создайте событие один раз — дальше я напомню сам.",
        reply_markup=main_menu(),
    )


@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "Что я умею:\n\n"
        "/events — список ваших событий\n"
        "/new — создать событие\n"
        "/timezone Europe/Moscow — сменить часовой пояс\n\n"
        "Когда дело сделано — нажмите «Сделано», "
        "и оставшиеся напоминания этого цикла не придут."
    )


@dp.message(Command("timezone"))
async def timezone_handler(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        current = db.get_timezone(message.from_user.id)
        await message.answer(
            f"Сейчас: {current}\n\n"
            "Сменить: /timezone Asia/Yekaterinburg"
        )
        return

    tz = parts[1].strip()
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(tz)
    except Exception:
        await message.answer("Не знаю такой пояс. Пример: Europe/Moscow")
        return

    db.ensure_user(message.from_user.id)
    db.set_timezone(message.from_user.id, tz)

    for event in db.get_user_events(message.from_user.id):
        sched.reschedule_event(event["id"])

    await message.answer(f"Часовой пояс: {tz}")


@dp.message(Command("events"))
async def events_command(message: Message):
    await show_events(message.from_user.id, message.answer)


@dp.callback_query(F.data == "list_events")
async def events_callback(callback: CallbackQuery):
    await show_events(callback.from_user.id, callback.message.edit_text)
    await callback.answer()


async def show_events(user_id: int, sender):
    events = db.get_user_events(user_id)
    if not events:
        await sender(
            "Событий пока нет.",
            reply_markup=main_menu(),
        )
        return
    await sender("Ваши события:", reply_markup=events_keyboard(events))


@dp.callback_query(F.data.startswith("open:"))
async def open_event(callback: CallbackQuery):
    event_id = int(callback.data.split(":")[1])
    event = db.get_event(event_id)

    if event is None:
        await callback.answer("Событие не найдено")
        return

    await callback.message.edit_text(
        f"{event['title']}\n\n"
        f"Срок: {event['due_date']}\n"
        f"Повтор: {REPEAT_NAMES.get(event['repeat_type'], '—')}\n"
        f"Напоминаю за {event['days_before']} дн. в {event['notify_time']}",
        reply_markup=event_actions(event_id),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("done:"))
async def done_event(callback: CallbackQuery):
    event_id = int(callback.data.split(":")[1])
    event = db.get_event(event_id)

    if event is None:
        await callback.answer("Событие не найдено")
        return

    current = date.fromisoformat(event["due_date"])
    following = next_due_date(current, event["repeat_type"])

    db.mark_done(event_id, following.isoformat() if following else None)
    sched.reschedule_event(event_id)

    if following:
        text = f"Отмечено. Следующий срок: {following.isoformat()}"
    else:
        text = "Отмечено. Событие разовое, больше не напомню."

    await callback.message.edit_text(text, reply_markup=main_menu())
    await callback.answer()


@dp.callback_query(F.data.startswith("delete:"))
async def delete_event_handler(callback: CallbackQuery):
    event_id = int(callback.data.split(":")[1])
    sched.unschedule_event(event_id)
    db.delete_event(event_id)
    await callback.message.edit_text("Событие удалено.", reply_markup=main_menu())
    await callback.answer()

@dp.callback_query(F.data == "new_event")
async def new_event_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(NewEvent.title)
    await callback.message.edit_text(
        "Как назвать событие?\n\n"
        "Например: Показания счётчиков, Оплата коммуналки"
    )
    await callback.answer()


@dp.message(Command("new"))
async def new_event_command(message: Message, state: FSMContext):
    db.ensure_user(message.from_user.id)
    await state.set_state(NewEvent.title)
    await message.answer("Как назвать событие?")


@dp.message(NewEvent.title)
async def new_event_title(message: Message, state: FSMContext):
    title = message.text.strip()

    if len(title) > 100:
        await message.answer("Слишком длинно, до 100 символов.")
        return

    await state.update_data(title=title)
    await state.set_state(NewEvent.due_date)
    await message.answer(
        "Когда срок? Дата в формате ДД.ММ.ГГГГ\n\n"
        "Например: 15.09.2026"
    )


@dp.message(NewEvent.due_date)
async def new_event_date(message: Message, state: FSMContext):
    try:
        due = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        await message.answer("Не понял дату. Формат: 15.09.2026")
        return

    if due < date.today():
        await message.answer("Эта дата уже прошла. Укажите будущую.")
        return

    await state.update_data(due_date=due.isoformat())
    await state.set_state(NewEvent.repeat)
    await message.answer("Как часто повторять?", reply_markup=repeat_keyboard())


@dp.callback_query(NewEvent.repeat, F.data.startswith("repeat:"))
async def new_event_repeat(callback: CallbackQuery, state: FSMContext):
    repeat_type = callback.data.split(":")[1]
    await state.update_data(repeat_type=repeat_type)
    await state.set_state(NewEvent.days_before)
    await callback.message.edit_text(
        "За сколько дней начать напоминать?\n\n"
        "Число от 0 до 30. Например: 3"
    )
    await callback.answer()


@dp.message(NewEvent.days_before)
async def new_event_days(message: Message, state: FSMContext):
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer("Нужно число. Например: 3")
        return

    if not 0 <= days <= 30:
        await message.answer("От 0 до 30.")
        return

    await state.update_data(days_before=days)
    await state.set_state(NewEvent.notify_time)
    await message.answer("Во сколько напоминать? Формат ЧЧ:ММ\n\nНапример: 09:30")


@dp.message(NewEvent.notify_time)
async def new_event_time(message: Message, state: FSMContext):
    text = message.text.strip()

    try:
        parsed = datetime.strptime(text, "%H:%M")
    except ValueError:
        await message.answer("Не понял время. Формат: 09:30")
        return

    notify_time = parsed.strftime("%H:%M")
    data = await state.get_data()
    await state.clear()

    event_id = db.add_event(
        user_id=message.from_user.id,
        title=data["title"],
        due_date=data["due_date"],
        repeat_type=data["repeat_type"],
        days_before=data["days_before"],
        notify_time=notify_time,
    )

    sched.schedule_event(event_id)

    tz = db.get_timezone(message.from_user.id)
    await message.answer(
        f"Готово: {data['title']}\n\n"
        f"Срок: {data['due_date']}\n"
        f"Повтор: {REPEAT_NAMES.get(data['repeat_type'], '—')}\n"
        f"Напомню за {data['days_before']} дн. в {notify_time} ({tz})",
        reply_markup=main_menu(),
    )

async def main():
    db.init_db()

    bot = Bot(token=TOKEN)
    sched.set_bot(bot)
    sched.scheduler.start()
    sched.restore_all()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())