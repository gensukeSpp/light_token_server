"""グレース期間後のマイルストーン自動 closed 遷移 (Task-11)。

- `close_expired_waiting_milestones(db, today)`: 純粋関数。テストからも直接呼べる。
- `execute_close_job()`: スケジューラ / 手動実行用エントリポイント。
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config import MILESTONE_CLOSE_GRACE_DAYS
from app.database_base import SessionLocal
from app.models import MILESTONE_CLOSED, MILESTONE_WAITING, MilestoneORM


def close_expired_waiting_milestones(db: Session, today: date | None = None) -> int:
    """waiting で猶予(グレース)期間を過ぎたマイルストーンを closed へ遷移し、件数を返す。

    境界 (決定事項 2): accomplished_date + GRACE_DAYS <= today で closed 確定。
    +5 日目の当日をもって確定し、+4 日目までは猶予内。
    子イベント completed は変更しない (waiting 遷移時に済んでいるため)。
    """
    today = today or date.today()
    cutoff = today - timedelta(days=MILESTONE_CLOSE_GRACE_DAYS)
    targets = (
        db.query(MilestoneORM)
        .filter(
            MilestoneORM.status == MILESTONE_WAITING,
            MilestoneORM.accomplished_date.isnot(None),
            MilestoneORM.accomplished_date <= cutoff,
        )
        .all()
    )
    for ms in targets:
        ms.status = MILESTONE_CLOSED
    db.commit()
    return len(targets)


def execute_close_job() -> int:
    """スケジューラ/手動から呼ぶエントリポイント。closed 化した件数を返す。"""
    db = SessionLocal()
    try:
        return close_expired_waiting_milestones(db, date.today())
    finally:
        db.close()
