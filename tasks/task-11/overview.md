# Task-11 実装計画 — グレース期間後のマイルストーン自動 closed 遷移

> **For Hermes:** 実装は TDD(失敗→実装→成功→Commit)でタスク単位に進める。実装前に本ファイル群と `requirement-03.md`、`tasks/issue-9/` の waiting/closed 仕様、`app/routers/timetable.py` の既存 `/milestone/*` 実装を読み、**既存の waiting 遷移・remove の契約を壊さない**こと。

**Goal:** `accomplished_date` 入力で `waiting`(waiting for close) に遷移したマイルストーンが、猶予期間(グレース)経過後、**自動的に `closed` へ確定遷移**するバックエンド処理を追加する。猶予期間は設定値 `MILESTONE_CLOSE_GRACE_DAYS`(env、デフォルト 5 日)で制御する。

**Architecture:** FastAPI の **lifespan で起動する APScheduler のバックグラウンドジョブ**として定期実行し、`status == waiting` かつ `accomplished_date + GRACE_DAYS` を過ぎたマイルストーンを `closed` へ遷移させる。新規 `/milestone/*` エンドポイントは作らない(単体の DB 更新処理)。

**Tech Stack:** FastAPI, SQLAlchemy(2.x), APScheduler(+ 依存追加), pytest + TestClient(SQLite)

---

## この段階で完成するもの(成果物)

- 猶予日数設定 `MILESTONE_CLOSE_GRACE_DAYS`(config, env, デフォルト 5)
- 自動 closed ジョブ: `status == waiting` かつ `accomplished_date + GRACE_DAYS < today` のマイルストーンを `closed` へ一括遷移
- FastAPI lifespan にスケジューラを組み込み、アプリ起動時に自動スケジュール(dev 動作確認用に手動実行関数も export)
- 実行ログ(何件 closed にしたか)を返す/記録する手段
- テスト(`tests/test_milestone.py` に追加)が SQLite で自動・再現可能に通る(猶予前は遷移しない / 猶予後は closed 化 / 対象は waiting のみ / 子イベント completed は不変)

## スコープ外(今回はやらない)

- フロントエンド(time-table-to-line)側の変更 — **不要**。`/milestone/all` は `status != closed` のみ返すため、closed 化されたマイルストーンは自動で一覧・配色から外れ、所属イベントはデフォルト色 `#2196f3` に戻る(既存仕様で達成。追加 UI/API 不要)
- closed 済みマイルストーンの再 open API — 契約(閉じた後は再 open 不可)は維持
- 猶予期間中の経過日数表示 UI / バッジ — 本次はバックエンド確定遷移のみ
- PostgreSQL への **DB マイグレーション** — カラム追加なし(既存 `status` String(10) を流用)。マイグレーション不要
- waiting → open の再 open 挙動(issue-9 で実装済み)や remove(ソフト close)の変更
- **子イベント completed の整合処理** — 今回の自動 closed では completed を変更しない。
  closed 確定後の子イベント completed の扱い(維持/何らかの調整)は**次のタスク**で扱う。

## 現在のコンテキスト / 前提

- `MilestoneORM.status` は `String(10)`, 定数 `MILESTONE_OPEN` / `MILESTONE_WAITING` / `MILESTONE_CLOSED` が `app/models.py`(128-130 行)に定義済み
- `/milestone/update/{id}` は `accomplished_date` 設定時、`status = MILESTONE_WAITING` + 子イベント `completed=True` に遷移(既存、timetable.py 320-327 行)
- `/milestone/remove/{id}` は `status = MILESTONE_CLOSED` + 子イベント `completed=True`(既存、338-353 行)。**今回の自動 closed はこの remove と同じ終端遷移**だが、子イベント completed は waiting 移行で既に True のため変更不要
- `/milestone/all` は `status.in_([OPEN, WAITING])` を返す(closed を除外。286-289 行)。→ 自動 closed 後は一覧から消える(frontend は無変更で追従)
- `created_at` / `accomplished_date` は `Date` 型。`accomplished_date` は waiting にした際に必ず設定される(update 320-331 行。re-open 時のみ None)
- 認証 / groups は自動ジョブと無関係(サーバー内定期処理のため、トークン不要)
- テスト基盤: `tests/conftest.py` が SQLite + `StaticPool` で `app.dependency_overrides[get_db]` を使う。ジョブは `SessionLocal`(database_base) を直接使う設計にする(API 経由でなく単体で呼べるように)

## 構成方針の要点

- **スケジューリング方式: APScheduler(BlockingScheduler ではなく BackgroundScheduler)を FastAPI lifespan で起動**
- ジョブ本体は DB 更新ロジックを **純粋関数(例: `close_expired_waiting_milestones(db, today) -> int`)に抽出**し、スケジューラとテストの両方から呼べるようにする(テスト容易性)
- 依存追加: `apscheduler`(pyproject.toml の [project.dependencies])
- 猶予日数は `app/config.py` で `MILESTONE_CLOSE_GRACE_DAYS = int(os.getenv("MILESTONE_CLOSE_GRACE_DAYS", "5"))` として一元管理
- カットオフ判定: `accomplished_date != None and accomplished_date + timedelta(days=GRACE_DAYS) < date.today()` の waiting を閉じる(境界は「経過 = 未満」で判定。`==` 当日は猶予内とみなすか要確認→判断ポイント)
- **既存を壊さない**: update の waiting 遷移・re-open、remove の即時 closed は無変更。自動ジョブは「waiting のまま猶予を過ぎたもの」だけに限定
- **実行モデルの注意**: uvicorn が常駐し続けることを前提とする。開発時は再起動ごとにスケジューラが立ち上がる(HMR の再読み込みで多重起動しないよう、dev は手動起動/テストを主とする)

## 決定済み事項(利用者確認済み 2026-09-07)

1. **実行方式**: **FastAPI lifespan で APScheduler(BackgroundScheduler)を起動**する。(a) 採用。依存 `apscheduler` を追加。
2. **猶予日数と境界**: `MILESTONE_CLOSE_GRACE_DAYS` の env、**デフォルト 5 日**。`accomplished_date + 5 日` **に達したら(当日をもって)closed 確定**。すなわち判定は `accomplished_date + GRACE_DAYS <= today`(`<=` 採用。+5 日目当日に確定、+4 日目までは猶予内)。
3. **子イベント completed**: 自動 closed では **変更しない(何もしない)**。waiting 遷移時に既に `completed=True` になっているため。子イベント completed の整合は**次のタスク**で扱う(本次はスコープ外)。
4. **スケジュール間隔などの既定値**: 記載のまま。`MILESTONE_CLOSE_INTERVAL_MINUTES`(デフォルト 60 分)、`ENABLE_MILESTONE_SCHEDULER`(デフォルト true)。いずれも env で調整可能。

> 上記は確定仕様。実装は overview 冒頭の「構成方針」「(実装後)ディレクトリ構成」および
> tasks.md / architecture.md / test-plan.md の各該当箇所に反映済み。

## ディレクトリ構成(実装後)

```
app/
  config.py          # 変更: MILESTONE_CLOSE_GRACE_DAYS(env, デフォルト5)
  scheduler.py       # 新規: BackgroundScheduler 起動 + close_expired_waiting_milestones の登録
  jobs/
    close_milestones.py  # 新規: 純粋関数 close_expired_waiting_milestones(db, today) -> int
  main.py            # 変更: lifespan に scheduler 起動/停止を組み込み
tests/
  test_milestone.py  # 追加: 自動 closed の統合テスト(猶予前/後/waiting以外/子イベントcompleted)
```