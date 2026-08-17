from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import date


def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Мои события", callback_data="list_events")
    builder.button(text="Новое событие", callback_data="new_event")
    builder.adjust(1)
    return builder.as_markup()


def done_keyboard(event_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Сделано", callback_data=f"done:{event_id}")
    return builder.as_markup()


def repeat_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Раз в месяц", callback_data="repeat:monthly")
    builder.button(text="Раз в квартал", callback_data="repeat:quarterly")
    builder.button(text="Раз в год", callback_data="repeat:yearly")
    builder.button(text="Разово", callback_data="repeat:none")
    builder.adjust(1)
    return builder.as_markup()


def events_keyboard(events) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for event in events:
        due = date.fromisoformat(event["due_date"])
        builder.button(
            text=f"{event['title']} — {due.strftime('%d.%m.%Y')}",
            callback_data=f"open:{event['id']}",
        )
    builder.button(text="Новое событие", callback_data="new_event")
    builder.adjust(1)
    return builder.as_markup()


def event_actions(event_id: int, is_paused: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Сделано", callback_data=f"done:{event_id}")
    if is_paused:
        builder.button(text="Возобновить", callback_data=f"resume:{event_id}")
    else:
        builder.button(text="Пауза", callback_data=f"pause:{event_id}")
    builder.button(text="Удалить", callback_data=f"delete:{event_id}")
    builder.button(text="К списку", callback_data="list_events")
    builder.adjust(2, 2)
    return builder.as_markup()