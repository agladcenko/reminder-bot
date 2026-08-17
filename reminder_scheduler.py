from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

import database as db
from scheduler_logic import future_reminders

scheduler = AsyncIOScheduler(
    jobstores={"default": SQLAlchemyJobStore(url="sqlite:///jobs.db")},
    timezone="UTC",
)

_bot = None  # ссылка на бота, задаётся при старте


def set_bot(bot) -> None:
    global _bot
    _bot = bot


async def send_reminder(event_id: int) -> None:
    """Отправляет напоминание. Вызывается планировщиком."""
    event = db.get_event(event_id)

    if event is None or event["is_done"] or event["is_paused"]:
        return

    from keyboards import done_keyboard

    from datetime import date as date_type
    due = date_type.fromisoformat(event["due_date"])

    await _bot.send_message(
        event["user_id"],
        f"Напоминание: {event['title']}\n"
        f"Срок: {due.strftime('%d.%m.%Y')}",
        reply_markup=done_keyboard(event_id),
    )


def schedule_event(event_id: int) -> None:
    """Планирует все будущие напоминания для события."""
    event = db.get_event(event_id)
    if event is None:
        return

    timezone = db.get_timezone(event["user_id"])
    due = date.fromisoformat(event["due_date"])

    moments = future_reminders(
        due,
        event["days_before"],
        event["notify_time"],
        timezone,
    )

    for index, moment in enumerate(moments):
        scheduler.add_job(
            send_reminder,
            trigger="date",
            run_date=moment,
            args=[event_id],
            id=f"event_{event_id}_{index}",
            replace_existing=True,
            misfire_grace_time=3600,
        )


def unschedule_event(event_id: int) -> None:
    """Снимает все запланированные напоминания события."""
    prefix = f"event_{event_id}_"
    for job in scheduler.get_jobs():
        if job.id.startswith(prefix):
            job.remove()


def reschedule_event(event_id: int) -> None:
    unschedule_event(event_id)
    schedule_event(event_id)


def restore_all() -> None:
    """Восстанавливает расписание при старте бота."""
    for event in db.get_all_active_events():
        reschedule_event(event["id"])