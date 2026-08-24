from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler


def create_scheduler(poll_func: Callable[[], None], interval_minutes: int) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        poll_func,
        "interval",
        minutes=interval_minutes,
        id="classroom-deadline-poll",
        replace_existing=True,
        max_instances=1,
    )
    return scheduler
