from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from app.services.monitor import DeadlineMonitor


def create_scheduler(monitor: DeadlineMonitor, interval_minutes: int) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        monitor.poll_once,
        "interval",
        minutes=interval_minutes,
        id="classroom-deadline-poll",
        replace_existing=True,
        max_instances=1,
    )
    return scheduler
