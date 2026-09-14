# Task-11 Architecture — グレース期間後のマイルストーン自動 closed

## 1. 目的と背景

マイルストーンのライフサイクルは requirement-03.md(2026-08-27)で
`open → accomplished_date入力で waiting(猶予期間) → closed` と定義された。
`waiting` は **再 open の猶予期間**(waiting for close)であり、issue-9 では
「猶予期間の自動 closed(数日後の cron/ジョブ)は期間未定のため今回スコープ外」として
実装を見送られた。本 Task はこの抜けている「waiting → closed の自動確定」を追加する。

現状の closed 発生経路は以下の 2 つのみで、どちらも**即時/手動操作**:
- `POST /milestone/update/{id}` の `accomplished_date` 入力 → `waiting` へ変更(猶予開始)
- `DELETE /milestone/remove/{id}` → 管理者による即時 `closed`(ソフト削除。作成ミス用)

つまり **waiting のまま放置しても閉じられない**。グレース期間経過を検知して
`waiting -> closed` へ自動遷移させるジョブを追加するのが本 Task の目的。

## 2. 対象データモデル

`M_MILESTONE`(app/models.py)の既存カラムを流用する。**スキーマ変更なし**。

| カラム | 型 | 用途 |
|---|---|---|
| `id` | Integer PK | 対象特定 |
| `status` | String(10) | `open` / `waiting` / `closed`。**今回の遷移対象は `waiting` のみ** |
| `accomplished_date` | Date, nullable | **猶予開始日**。waiting 遷移時に必ず設定される |

- 定数: `MILESTONE_OPEN="open"`, `MILESTONE_WAITING="waiting"`, `MILESTONE_CLOSED="closed"`
- `accomplished_date` は update(320-331 行)で waiting にする際、必ず値が入る。
  `None`(再 open)は waiting ではないので対象外。

## 3. 遷移ルール

```
status == MILESTONE_WAITING
  AND accomplished_date IS NOT NULL
  AND accomplished_date + GRACE_DAYS <= today   (確定済み: 「+5日」に達した当日をもって closed。`<=` 採用)
  ──＞ status := MILESTONE_CLOSED
```

- 対象は **`status == 'waiting'` のものだけ**。
  `open`(accomplished_date None)は猶予開始していないため対象外。
  `closed` は既に終端のため対象外。
- 子イベント `completed` は **今回の自動 closed では変更しない**(決定済み)。
  waiting 遷移時に既に `completed=True` になっているため(update 323-327 行)。
  closed 確定後の子イベント completed の整合は**次のタスク**で扱う。
- その後 `/milestone/all`(status.in_([OPEN, WAITING]))はこの行を返さなくなり、
  フロントの MilestoneList(`status !== 'closed'` フィルタ)から自動で消える。
  所属イベントは milestone 色マップから外れ、デフォルト色 `#2196f3` に戻る。
  → **フロント変更不要**(既存仕様で達成)。

## 4. 実行方式(APScheduler + FastAPI lifespan)

依存追加: `apscheduler`(pyproject.toml [project.dependencies])

```
FastAPI app startup(lifespan)
   └─ BackgroundScheduler.start()
        └─ add_job(execute_close_job, trigger=IntervalTrigger..., ※判断ポイント4)
              └─ SessionLocal() を開き close_expired_waiting_milestones(db, today) を呼ぶ
              └─ db.commit() / db.close()
FastAPI app shutdown
   └─ scheduler.shutdown()
```

- **ジョブ本体を純粋関数に分離**: `close_expired_waiting_milestones(db, today) -> int`
  (closed 化した件数を返す)。スケジューラからもテストからも直接呼べる。
- DB セッションは `app.database_base.SessionLocal` をジョブ内で短期生成/破棄する
  (API の `get_db` 依存と混ぜない。認証不要の定期処理のため)。
- 猶予日数は `app/config.py` に `MILESTONE_CLOSE_GRACE_DAYS`(env, デフォルト 5)、
  実行間隔も `MILESTONE_CLOSE_INTERVAL_MINUTES`(env, デフォルト 60)、
  起動フラグ `ENABLE_MILESTONE_SCHEDULER`(env, デフォルト true)で調整可能にする。
- **実行方式は確定済み(決定事項 1)**: FastAPI lifespan + BackgroundScheduler。cron 案は不採用。

### 起動時の注意(多重起動・dev)
- uvicorn の `--reload` は子プロセスが再起動されるため、スケジューラが多重起動しうる。
  dev ではスケジューラ自動起動を OFF にできる flag(env `ENABLE_MILESTONE_SCHEDULER`)を
  設け、テスト・開発時は手動実行関数/テストで確認する方針を推奨。

## 5. ファイル構成と責務

| ファイル | 責務 | 変更種別 |
|---|---|---|
| `app/config.py` | `MILESTONE_CLOSE_GRACE_DAYS` 等の設定追加 | 変更 |
| `app/jobs/__init__.py` | パッケージ化 | 新規 |
| `app/jobs/close_milestones.py` | `close_expired_waiting_milestones(db, today)` 純粋関数 + `execute_close_job()`(SessionLocal 生成) | 新規 |
| `app/scheduler.py` | `BackgroundScheduler` 生成・ジョブ登録・start/shutdown ラッパー | 新規 |
| `app/main.py` | lifespan で scheduler 起動/停止(env flag で制御) | 変更 |
| `tests/test_milestone.py` | 自動 closed の統合テスト追加 | 変更 |
| `pyproject.toml` | `apscheduler` 追加 | 変更 |

## 6. テスト戦略

ジョブ本体(純粋関数)を、既存 conftest の SQLite + dependency_overrides を流用せず、
**関数に直接 `SessionLocal` 相当のセッションを渡して検証**する(API 経由でなく単体単位)。

```
tests/test_milestone.py に追加:
  test_auto_close_before_grace    : accomplished_date が猶予内 → closed にならない
  test_auto_close_after_grace     : 猶予超過 → closed になる、件数が返る
  test_auto_close_only_waiting    : open / closed は対象外
  test_auto_close_keeps_completed : 子イベント completed は True のまま(変更されない)
  test_auto_close_boundary        : accomplished_date+5日 == today → closed になる(境界 `<=` 検証)
```

- 実行間隔・スケジューラ自体の起動はテストしない(ライブラリ動作 + 起動フラグは
  手動/QA で確認)。**遷移ロジックのみを自動テスト**する。
- `pytest tests/test_milestone.py -v` で回帰(既存 16 件 + 追加)が通過すること。

## 7. 既存との整合性(非対象・影響)

| 既存機能 | 影響 |
|---|---|
| `/milestone/update` の waiting 遷移 / re-open | 無変更。自動 closed は対象を拡張しない |
| `/milestone/remove` の即時 closed | 無変更 |
| `/milestone/all` の open+waiting 射影 | 自動 closed 後に自動で一覧から外れる(望ましい挙動) |
| フロント MilestoneList / computeItemDecorations | 変更不要(closed は既に一覧外・色マップ外) |
| 認証(require_token) | 定期処理のため対象外。API 追加なし |

## 8. リスクと対策

- **スケジューラ多重起動(dev reload)**: env flag で dev の自動起動を OFF 化。
- **タイムゾーン**: `date.today()` はサーバーローカル日付。JST/UTC のずれで境界が
  前後 1 日ぶれる可能性。`accomplished_date` は `Date` 型(時刻なし)のため、日単位の
  判定で実用上許容(決定事項 2 の `<=` 境界はローカル日付で判定)。
- **DB 接続**: ジョブが短命セッションを毎回開くため、接続プールの枯渇リスクは
  低い。IntervallTrigger の間隔が短すぎないよう config で調整。