from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def add_months(source: date, months: int) -> date:
    """
    Прибавляет месяцы, корректно обрабатывая нехватку дней.
    31 января + 1 месяц = 28 (или 29) февраля.
    """
    year = source.year + (source.month - 1 + months) // 12
    month = (source.month - 1 + months) % 12 + 1

    # определяем последний день целевого месяца
    if month == 12:
        next_month_first = date(year + 1, 1, 1)
    else:
        next_month_first = date(year, month + 1, 1)
    last_day = (next_month_first - timedelta(days=1)).day

    return date(year, month, min(source.day, last_day))


def next_due_date(current: date, repeat_type: str) -> date | None:
    """Считает следующий срок. Для разовых событий возвращает None."""
    if repeat_type == "monthly":
        return add_months(current, 1)
    if repeat_type == "quarterly":
        return add_months(current, 3)
    if repeat_type == "yearly":
        return add_months(current, 12)
    return None


def reminder_datetimes(
        due: date,
        days_before: int,
        notify_time: str,
        timezone: str,
) -> list[datetime]:
    """
    Возвращает список моментов напоминаний с учётом часового пояса.
    Напоминаем каждый день начиная за days_before дней, включая день срока.
    """
    hour, minute = map(int, notify_time.split(":"))
    tz = ZoneInfo(timezone)

    result = []
    for offset in range(days_before, -1, -1):
        day = due - timedelta(days=offset)
        moment = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
        result.append(moment)

    return result


def future_reminders(
        due: date,
        days_before: int,
        notify_time: str,
        timezone: str,
) -> list[datetime]:
    """Только те напоминания, которые ещё не прошли."""
    tz = ZoneInfo(timezone)
    now = datetime.now(tz)
    return [m for m in reminder_datetimes(due, days_before, notify_time, timezone) if m > now]