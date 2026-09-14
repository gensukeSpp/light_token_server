"""FastAPI lifespan から起動するマイルストーン自動 closed スケジューラ (Task-11)。"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import MILESTONE_CLOSE_INTERVAL_MINUTES
from app.jobs.close_milestones import MILESTONE_TIMEZONE, execute_close_job


def create_milestone_scheduler() -> BackgroundScheduler:
    # スケジューラとジョブ内の日付判定を同じ JST で揃える (PR #12 レビュー [P1] 対応)。
    # サーバーが UTC でも JST の午前0時を境界に closed 化される。
    scheduler = BackgroundScheduler(timezone=MILESTONE_TIMEZONE)
    scheduler.add_job(
        execute_close_job,
        trigger=IntervalTrigger(minutes=MILESTONE_CLOSE_INTERVAL_MINUTES),
        id="milestone-auto-close",
        replace_existing=True,
    )
    return scheduler
