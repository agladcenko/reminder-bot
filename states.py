from aiogram.fsm.state import State, StatesGroup


class NewEvent(StatesGroup):
    title = State()
    due_date = State()
    repeat = State()
    days_before = State()
    notify_time = State()