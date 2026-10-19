# Milestones — light_token_server / time-table-to-line 共通要件 (`requirement-03.md`)

> RULE ファイル(AGENTS.md から分割)。マイルストーン機能は更新が頻繁なため独立管理する。
> 変更時は本ファイルを更新し、AGENTS.md のリンク anchor(`## Milestones (requirement-03.md)`)は維持する。
> 本要件は `requirement-03.md` を正とする。変更時は必ず読み直す。

## Table schema
- `M_MILESTONE` — テーブル名は既存規則 (`M_STAFFINFO`) に合わせる
  - `id: Integer, primary_key`
  - `staff_id: Integer, ForeignKey("M_LOGININFO.STAFFID")` — 作成者ID
  - `title: String(100)`
  - `description: String(256), nullable`
  - `color: String(10)` — カラーコード
  - `status: String(10), default="open"` — `open` / `waiting` / `closed`
    (`waiting` は再 open の猶予期間 = waiting for close。定数 `MILESTONE_OPEN`/`MILESTONE_WAITING`/`MILESTONE_CLOSED` を models に定義)
  - `created_at: Date` — 作成日（時刻不要）
  - `guideline_end_date: Date, nullable` — 達成目安日（旧 `guidline_end_date` はスペル修正済み・Issue #9）
  - `accomplished_date: Date, nullable` — 達成日(入力=waiting 遷移)
- `T_TIMELINE_EVENT` に追加
  - `milestone_id: Integer, ForeignKey("M_MILESTONE.id"), nullable` — 所属マイルストーン
  - `completed: Boolean, default=False` — 完了フラグ

## Semantic rules
- `status="open"` → 作成直後。`status="closed"` → 達成済み。`status="waiting"` → 再 open の猶予期間(waiting for close)
- **closed の発生経路は 2 つ**: (1) `/milestone/remove` による即時 closed(作成ミス用・子 completed=True)、
  (2) waiting からの**自動 closed**(Task-11, 2026-09-08。グレース期間経過後、子イベント completed は不変。下記 API endpoints 参照)
- **accomplished_date 設定時は `waiting` へ遷移**(`closed` へ直接遷移しない)。`waiting` 中は子イベントの `completed=True` を自動更新(close 相当)
- **`waiting` からは re-open 可**: update で `accomplished_date` に `null` を明示すると `open` へ戻る。
  子イベントの `completed` は **`False` に戻す**(waiting 遷移で一括 `True` にしたものを復帰、配色を milestone color に戻す)
- 一度 `closed` にしたマイルストーンへの再 update は 409 で拒否(API レイヤ)。本 Issue では閉じの確定はデータ上生成しない → re-open は waiting 由来のみ
- `completed=True` または `milestone_id` が削除されたイベントはデフォルト色 (`#2196f3`) に変更
- マイルストーンはグループ横断共有。`group_id` カラムは不要

## Permission model
- `admin=True` のユーザー全員が作成/クローズ/削除可能
- 従来の「そのグループの管理者」→ 誤解を招く表現。実態は「全 admin ユーザー」
- ~~閲覧はグループ単位(既存のトークン `group_id` でフィルタ)~~ マイルストーン本体は全グループ共有。所属イベントの参照は open/waiting 用は `require_token` のみ、closed 用は admin のみで全グループ横断
- `GET /milestone/{milestone_id}/events` は有効なアクセストークンのみで参照可能(`require_token`、admin 不要)。対象 milestone はグループ横断共有のため、
  所属イベントも全グループから取得し、トークンの `group_id` では絞り込まない。
- `GET /milestone/closed/{milestone_id}/events` も admin のみ。closed milestone のイベントを全グループから取得し、
  open / waiting 用 endpoint と同じイベント形式で返す。

## Color rules
- 10 固定パターン: ` #9c27b0 #009688 #795548 #607d8b #e91e63 #3f51b5 #00bcd4 #ff5722 #8bc34a #ff9800`
- 作成時、一覧表示中 (open + waiting) のマイルストーンと被らない色を自動選択
- 10 件超えた場合は 1 番目の色から cyclic に戻す

## API endpoints
- `POST /milestone/add` — admin のみ、カラータブルから衝突回避
- `GET /milestone/all` — open + waiting 一覧(`status.in_(["open", "waiting"])` の完全一致。旧 boolean 由来の未知ステータス値を公開しない。Issue #9 で変更多)
- `GET /milestone/{milestone_id}/events` — `require_token` のみ(admin 不要)。open / waiting milestone の所属イベントを全グループから `EventORM.to_milestone_dict()`（ホワイトリスト）形式で返す。存在しない ID と closed / 対象外状態の ID は 404。
- `GET /milestone/closed/{milestone_id}/events` — admin のみ。closed milestone の所属イベントを全グループから `EventORM.to_milestone_dict()`（ホワイトリスト）形式で返す。存在しない ID または closed 以外の状態は 404。
- 両 endpoint 共通のレスポンス仕様（Issue #16、2026-10-19）:
  - 公開キーは **`id` / `staff_id` / `group` / `group_name` / `start` / `end` / `title` / `progress` / `milestone_id` / `completed`** の 10 キーのみ（`EventORM.MILESTONE_EVENT_KEYS`）。
  - **`summary` は含めない**。open / waiting 一覧は非 admin も閲覧するため、他グループのイベント概要文を露出させない。`summary` が必要な場合は `/event/all` / `/event/user` / `/group/all`（`EventORM.to_dict()` ベース）を使う。
  - ブラックリスト（`pop("summary")`）ではなくホワイトリスト方式。`EventORM` にカラムを追加しても既定で非公開になる（追加する場合は `MILESTONE_EVENT_KEYS` とテストを同時更新）。
  - `group_name` は `M_TEAM.SHORTNAME`（Team 未登録なら `null`）。ルータ側で Team を一括取得して付与（N+1 回避）。
  - 共通ヘルパ `_get_milestone_events` は 1 イベントにつき dict 生成を 1 回だけ行う（`to_dict()` の二重呼び出しをしない、Issue #16 [低-6]）。
  - 正本仕様: `specs/2026-10-13-milestone-event-retrieval-spec.md`。差分記録: `specs/2026-10-19-milestone-events-summary-exclusion-spec.md`
- `POST /milestone/update/{id}` — admin のみ・部分更新(`title?` / `description?` / `guideline_end_date?` / `accomplished_date?`)。編集フィールドは None 以外を反映し status 不変。`accomplished_date` 値あり → `waiting` + 子 completed=True、明示 `null` → re-open(`open`)
- `DELETE /milestone/remove/{id}` — admin のみ、削除でなく `status=closed`(子 completed=True)を返す `{"closed": id}`
- 自動 closed (Task-11, 2026-09-08 実装): `waiting` のマイルストーンは猶予期間(グレース)経過後、
  APScheduler のバックグラウンドジョブ(FastAPI lifespan で起動)により**自動で `closed` へ確定遷移**する。
  - 猶予日数: `MILESTONE_CLOSE_GRACE_DAYS`(env, デフォルト 5 日)。境界は
    `accomplished_date + GRACE_DAYS <= today`(`<=` 採用。+5 日目の当日をもって closed 確定)
  - 実行間隔: `MILESTONE_CLOSE_INTERVAL_MINUTES`(env, デフォルト 10 分)。
    自動起動無効化: `ENABLE_MILESTONE_SCHEDULER=false`(dev / テスト用, デフォルト true)
  - 実装: `app/jobs/close_milestones.py`(`close_expired_waiting_milestones(db, today)` 純粋関数 +
    `execute_close_job()` エントリポイント)、`app/scheduler.py`、`app/main.py` の lifespan
  - **子イベント `completed` は変更しない**(waiting 遷移時に既に True)。closed 確定後の
    子イベント completed の整合は次のタスクで扱う
  - closed 化されたマイルストーンは `/milestone/all`(open + waiting のみ)から自動で外れ、
    所属イベントはデフォルト色 `#2196f3` に戻る(フロント変更不要)
- `POST /event/add` — `milestone_id` optional 追加
- `POST /event/update/{id}` — `completed` 対応。`milestone_id` は `model_fields_set` で判別し、明示的 `null` 送信で「所属なし」(milestone_id=None) として保存可(2026-09 追加。色のデフォルト復帰は未実装)

## UI conventions
- Japanese date format (UTC+9) for display only (stored as-is)
- Event default color: `#2196f3`
- Clicked color: `#ffc107`