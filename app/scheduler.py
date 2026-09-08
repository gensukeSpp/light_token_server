"""FastAPI lifespan から起動するマイルストーン自動 closed スケジューラ (Task-11)。"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import MILESTONE_CLOSE_INTERVAL_MINUTES
from app.jobs.close_milestones import execute_close_job


def create_milestone_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Tokyo")  # サーバーローカル日付で判定(決定事項2)
    scheduler.add_job(
        execute_close_job,
        trigger=IntervalTrigger(minutes=MILESTONE_CLOSE_INTERVAL_MINUTES),
        id="milestone-auto-close",
        replace_existing=True,
    )
    return scheduler
