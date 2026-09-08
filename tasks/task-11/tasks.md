# Task-11 実装タスク — グレース期間後のマイルストーン自動 closed

> 開始前に `overview.md` の「決定済み事項(2026-09-07)」を確認してから進めること。
> 実行方式・猶予境界・子イベント扱い・既定値はすべて確定済み。
> TDD(失敗→実装→成功→Commit)でタスク単位に進める。

## Task 1: 依存追加(apscheduler) + 設定追加

**Objective:** APScheduler を導入し、猶予日数・実行間隔を env で調整可能にする。

**Files:**
- Modify: `pyproject.toml`(`[project.dependencies]` に `"apscheduler>=3.10.0"` 追加)
- Modify: `app/config.py`

**Step 1: pyproject.toml に apscheduler を追加**
```toml
[project]
dependencies = [
    ...
    "apscheduler>=3.10.0",
]
```

**Step 2: config.py に猶予日数と実行制御を追加**
```python
# マイルストーン close 猶予(グレース)期間(日)。waiting 遷移後、この日数を経過して closed 確定。
MILESTONE_CLOSE_GRACE_DAYS = int(os.getenv("MILESTONE_CLOSE_GRACE_DAYS", "5"))
# 猶予チェックのバックグラウンド実行間隔(分)。dev で短くする用途。
MILESTONE_CLOSE_INTERVAL_MINUTES = int(os.getenv("MILESTONE_CLOSE_INTERVAL_MINUTES", "60"))
# False のときスケジューラを自動起動しない(dev / テスト用)。default True(production 想定)
ENABLE_MILESTONE_SCHEDULER = os.getenv("ENABLE_MILESTONE_SCHEDULER", "true").lower() == "true"
```

**Step 3: 依存インストール確認**
```bash
uv sync  # または bun 相当のパッケージ管理(プロジェクト運用に合わせる)
```
※ 実行環境の Python 3.13 に対応する apscheduler バージョンを確認して調整。

**Step 4: Commit**
```bash
git add pyproject.toml app/config.py
git commit -m "feat #(task11): apscheduler 追加と猶予日数/実行間隔設定を config 化"
```

---

## Task 2: ジョブ本体(純粋関数)の実装

**Objective:** waiting で猶予超過のマイルストーンを closed へ一括遷移する純粋関数を実装する。

**Files:**
- New: `app/jobs/__init__.py`
- New: `app/jobs/close_milestones.py`

**Step 1: パッケージ用 `__init__.py` を空で作成**
```bash
mkdir -p app/jobs
touch app/jobs/__init__.py
```

**Step 2: 純粋関数 `close_expired_waiting_milestones` を実装**
```python
from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.models import MilestoneORM, MILESTONE_WAITING, MILESTONE_CLOSED
from app.config import MILESTONE_CLOSE_GRACE_DAYS


def close_expired_waiting_milestones(db: Session, today: date | None = None) -> int:
    """waiting で猶予(グレース)期間を過ぎたマイルストーンを closed へ遷移し、件数を返す。"""
    today = today or date.today()
    cutoff = today - timedelta(days=MILESTONE_CLOSE_GRACE_DAYS)
    targets = (
        db.query(MilestoneORM)
        .filter(
            MilestoneORM.status == MILESTONE_WAITING,
            MilestoneORM.accomplished_date.isnot(None),
            MilestoneORM.accomplished_date <= cutoff,   # 境界確定: accomplished_date+GRACE_DAYS <= today
        )
        .all()
    )
    for ms in targets:
        ms.status = MILESTONE_CLOSED
    db.commit()
    return len(targets)
```
> 注: 境界は**決定済み**: `accomplished_date + GRACE_DAYS <= today`(`<=` 採用)。
> `+5 日`に達した当日をもって closed 確定(`+4 日`までは猶予内)。
> 子イベント completed は自動 closed では変更しない(waiting 遷移で済んでいるため)。

**Step 3: 実行ラッパー `execute_close_job` を実装**(SessionLocal を生成して呼ぶ)
```python
from app.database_base import SessionLocal
from app.jobs.close_milestones import close_expired_waiting_milestones


def execute_close_job() -> int:
    """スケジューラ/手動から呼ぶエントリポイント。closed 化した件数を返す。"""
    db = SessionLocal()
    try:
        return close_expired_waiting_milestones(db, date.today())
    finally:
        db.close()
```
> `execute_close_job` は `app/jobs/close_milestones.py` 内か、`app/scheduler.py` 内に配置。

**Step 4: Commit**
```bash
git add app/jobs/
git commit -m "feat #(task11): waiting 猶予超過のマイルストーンを closed へ一括遷移するジョブ関数"
```

---

## Task 3: スケジューラ組み込み(lifespan)

**Objective:** FastAPI 起動時に BackgroundScheduler がジョブを定期実行し、終了時に停止する。

**Files:**
- New: `app/scheduler.py`
- Modify: `app/main.py`

**Step 1: `app/scheduler.py` にスケジューララッパーを実装**
```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import MILESTONE_CLOSE_INTERVAL_MINUTES


def create_milestone_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Tokyo")  # サーバーローカル日付で判定(決定事項2)
    scheduler.add_job(
        execute_close_job,
        trigger=IntervalTrigger(minutes=MILESTONE_CLOSE_INTERVAL_MINUTES),
        id="milestone-auto-close",
        replace_existing=True,
    )
    return scheduler
```
> import: `execute_close_job` をここで import。

**Step 2: `app/main.py` に lifespan を追加**(自動起動フラグで制御)
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import ENABLE_MILESTONE_SCHEDULER
from app.scheduler import create_milestone_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if ENABLE_MILESTONE_SCHEDULER:
        scheduler = create_milestone_scheduler()
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown()


app = FastAPI(title="light-token-server", lifespan=lifespan)
```
> 既存 `app = FastAPI(title=...)` の行を lifespan 付きに置き換える。他のルーター登録は不変。

**Step 3: dev で自動起動を切った動作確認**(既存テストが通ること)
```bash
uv run pytest tests/test_milestone.py -v
# ENABLE_MILESTONE_SCHEDULER=false で起動し、サーバーが起動し続けること
ENABLE_MILESTONE_SCHEDULER=false uv run uvicorn app.main:app --port 8000
```

**Step 4: Commit**
```bash
git add app/scheduler.py app/main.py
git commit -m "feat #(task11): FastAPI lifespan で猶予チェック用スケジューラを起動/停止"
```

---

## Task 4: 自動 closed の統合テスト追加

**Objective:** 猶予前後・対象絞り込み・子イベント non-変更 を SQLite で検証する。

**Files:**
- Modify: `tests/test_milestone.py`

**Step 1: conftest のセッション構築を利用してテストを追加**(test-plan.md の一覧に従う)。
- waiting のマイルストーンを作るには既存ヘルパー `_add` + `/milestone/update` で
  `accomplished_date` を設定し、waiting 状態にしてから `close_expired_waiting_milestones(db, today)` を
  直接呼ぶ。
- `today` を引数で渡せるため、DB に古い / 新しい accomplished_date を入れて検証する。
- 子イベント completed 検証は `_add_event(milestone_id=..)` + `/event/all` で確認。

**Step 2: `pytest tests/test_milestone.py -v` で全件(既存 16 + 追加)が通ることを確認**

**Step 3: Commit**
```bash
git add tests/test_milestone.py
git commit -m "test #(task11): グレース期間後の自動 closed 遷移のテストを追加"
```

---

## Task 5: lint/review と最終確認

**Objective:** コード品質と既存契約の無変更を確認する。

**Step 1:** 追加した Python に未使用 import / コメント残骸がないか確認
```bash
uv run ruff check app/ tests/ 2>/dev/null || true  # 使用しているなら
```
※ この repo に ruff 設定が無ければ、piers 上の lint 運用に合わせて省略。

**Step 2:** 関連ドキュメント(`requirement-03.md` の「今後の展望」、本 overview)に
自動 closed 実装済みを反映(必要なら)。

**Step 3:** 最終コミット
```bash
git add -A
git commit -m "docs #(task11): 自動 closed の実装を反映"
```

> 完了後、利用者の実ブラウザ / API 検証(猶予期間を短く設定して経過確認)を待つ。