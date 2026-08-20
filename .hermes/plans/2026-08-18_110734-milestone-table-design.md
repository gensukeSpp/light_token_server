# マイルストーン(大きなタスク)機能のテーブル設計と実装プラン

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 現在のイベント(`EventORM`/`T_TIMELINE_EVENT`)を「小さなタスク」として、その上位に「大きなタスク＝マイルストーン」を追加できるようにするバックエンド変更計画を定める。

**Architecture:** 新規にマイルストーン管理テーブル `T_MILESTONE` を追加し、`T_TIMELINE_EVENT` に nullable の `milestone_id` FK を追加する(イベントは既存のまま単独で存在できる)。マイルストーンの作成・完了設定は**グループの管理者**(`StaffLogin.ADMIN`)だけが行い、マイルストーンの `status`(open/in_progress/done)は**管理者が設定する運用値**として保存する。子イベントの完了状態(任意の `completed` 列)は**表示用**であり、マイルストーン done の自動判定には使わない。API は既存 CRUD パターン(`/event/*`)を踏襲し `/milestone/*` を追加、認可は `Depends(require_token)` + claims の `admin` でスコープする。データベースマイグレーションはユーザー本人が実行するため、Alembic マイグレーションは**準備のみ**で実行しない。

**Tech Stack:** FastAPI / SQLAlchemy / Pydantic / Alembic / pytest(SQLite in-memory)。契約先フロントは `time-table-to-line`(React + react-calendar-timeline)。

---

## 1. 現状の把握

### 現モデル
- `EventORM` = `T_TIMELINE_EVENT`(`app/models.py:92`)
  - `id`(PK), `staff_id`(FK→`M_LOGGININFO.STAFFID`), `group_id`(FK→`M_TEAM.CODE`),
    `start_time`, `end_time`, `title`, `summary`, `progress`
  - `to_dict()` は `{"id","staff_id","group","start","end","title","summary","progress"}` を ISO `"...000Z"` で返す(AGENTS.md: この形式を維持)。
- テーブル命名: 既存レガシー系は大文字(`M_STAFFINFO` ほか)だが、`EventORM` は小文字スネークで追加されている。**新規テーブルも `EventORM` に合わせ小文字スネークのカラムで作る。**

### トークン / 認可
- `require_token`(`app/tokens.py`)は claims に `{user_id, group_id, admin: bool, type, exp}` を含む。
- **`admin` は `StaffLogin.ADMIN` 由来**。マイルストーンの特権操作チェックにこれを利用する(`claims["admin"]` が True かどうか)。

### 現 API(`app/routers/timetable.py`)
- `/group/all` : 自グループのイベント全件
- `/event/all`, `/event/user`, `/event/add(201)`, `/event/update/{id}`, `/event/remove/{id}`
- 認可: 全 CRUD が `Depends(require_token)`。

### 契約先フロント(`../time-table-to-line`)
- `TimelineType.ts` の `EventItem`: `{title, start_time, end_time, staff_id, summary?, progress?}`
- 呼び出しは `/event/all` `/event/user` `/event/add` `/event/update` `/event/remove` を使用。
- マイルストーン表示は**未実装**。今回はバックエンド設計が主目標。

---

## 2. テーブル設計(確定版)

### 確定事項(ユーザー決定)
- マイルストーンに**時刻は持たせない**(start_time / end_time を設けない)。
- 作成者・完了判定者は**グループの管理者(`StaffLogin.ADMIN`)**。管理者だけが作成・完了設定できる。
- マイルストーンの `done` は「子タスクが全 completed → 自動判定」**ではない**。管理者が判断して `status` を設定する運用値。
- done_count/total_count の比率は完成判定に**使わない**(子タスクのタイトルが不均一で比率として意味をなさない)。

### 案A(採用): 専用テーブル + status(管理者設定) + 表示用 completed

```
T_MILESTONE (新規)
  id           INTEGER PK
  group_id     INTEGER NOT NULL FK -> M_TEAM.CODE         -- チームスコープ(認可の軸)
  staff_id     INTEGER NOT NULL FK -> M_LOGGININFO.STAFFID -- 作成者(管理者, 必須)
  title        VARCHAR(100) NOT NULL
  description  TEXT NULL
  status       VARCHAR(20) NOT NULL DEFAULT 'open'          -- open / in_progress / done(管理者が設定)
  created_at   DateTime NOT NULL
  -- 時刻なし。done は status='done'(保存値)が正。

T_TIMELINE_EVENT (既存 + 2列)
  ... 既存カラム ...
  milestone_id  INTEGER NULL FK -> T_MILESTONE.id (ondelete SET NULL)   -- 所属マイルストーン
  completed     BOOLEAN NOT NULL DEFAULT false   -- 表示用フラグ(管理者のレビュー用。マイルストーン done 判定には使わない)
```

**完了判定の設計(質問2・4への回答):**
- マイルストーンの done = **`status` 列**の値(open/in_progress/done)。**保存値**であり子から導出しない。
- `status` を設定できるのは**管理者**のみ(`claims["admin"] == True` チェック)。
- 子イベントの `completed`(Boolean)は任意の**表示用**フラグとして追加。管理者が子タスクの進捗を眺める材料にはするが、マイルストーン done の自動集計には**使わない**。
- 既存 `progress`(String, 自由記述)は温存し、表示のみ。
- **別テーブル不要。** マイルストーン↔イベントは `event.milestone_id` FK だけで表現できる。完了は status 列で一元管理。

**廃案:**
- 案B(`EventORM` 自己参照): マイルストーンに時刻・管理者資格付けが入り込み複雑 → 却下。
- 案C(`Project -> Milestone -> Task` の2階層): YAGNI で将来に延期。
- 案D(JSON列): リレーショナルでなく権限・参照が複雑化 → 却下。

---

## 3. 変更対象ファイル(概観)

- `app/models.py` — 新 `Milestone` モデル(status 含む) + `EventORM.milestone_id` FK + `EventORM.completed`
- `app/schemas.py` — `MilestoneCreate` / `MilestoneUpdate`(status 含む) 追加、`EventCreate`/`EventUpdate` に `milestone_id`/`completed` 追加
- `app/routers/timetable.py` — `/milestone/*` CRUD + 管理者チェック、`/event/add`・`/event/update` の milestone/completed 連携
- `app/tokens.py` — 変更不要(claims に admin あり)
- `alembic/` — 新マイグレーション(**準備のみ、実行しない**)
- `tests/` — `test_milestone.py` 追加、既存 `test_timetable.py` に結合テスト追加

---

## 4. 実装ステップ(タスク単位)

### Task 1: `Milestone` モデルを追加 + `EventORM` に `milestone_id`/`completed`
**Files:** Modify `app/models.py`
- `T_MILESTONE` の `Milestone(Base)` を追加。カラム: `id`, `group_id`(FK M_TEAM.CODE, NOT NULL), `staff_id`(FK M_LOGGININFO.STAFFID, NOT NULL), `title`(String(100), NOT NULL), `description`(Text, NULL), `status`(String(20), NOT NULL, default='open'), `created_at`(DateTime, NOT NULL)。時刻なし。
- `EventORM` に追加:
  - `milestone_id = Column(Integer, ForeignKey("T_MILESTONE.id", ondelete="SET NULL"), nullable=True, index=True)`
  - `completed = Column(Boolean, nullable=False, default=False)`
- `relationship("Milestone", backref="events")` (EventORM 側または Milestone 側)。
- `Milestone.to_dict()`:`{"id","group","staff_id","title","description","status","created_at"}`。
- `EventORM.to_dict()` に `milestone_id` と `completed` を**追加キーとして**含める(既存キー不変=後方互換)。

### Task 2: 管理者チェックヘルパー
**Files:** Modify `app/routers/timetable.py`
- `def _require_admin(claims):` — `if not claims.get("admin"): raise HTTPException(403, "admin only")`。マイルストーン作成・status 更新で呼ぶ。

### Task 3: マイルストーン Pydantic スキーマ
**Files:** Modify `app/schemas.py`
- `MilestoneCreate`: `{group:int, staff_id:int, title:str, description:str|None, status:str='open'}`
- `MilestoneUpdate`: `{title:str|None, description:str|None, status:str|None}`(すべて optional。status 変更は管理者のみ)
- `EventCreate` / `EventUpdate` に `milestone_id: int | None = None` と `completed: bool | None = None` を追加。

### Task 4: `/milestone/*` CRUD ルーター
**Files:** Modify `app/routers/timetable.py`
- `POST /milestone/add`(201) — `_require_admin(claims)` 必須。`group` が claims の `group_id` と一致すること(不一致 403)。`staff_id` は作成者。
- `GET /milestone/all` — `require_token` で自グループのマイルストーン一覧(`to_dict()`)。
- `POST /milestone/update/{id}` — title/description の編集。`status` を渡す場合は `_require_admin(claims)`。対象が別 group なら 403/404。
- `DELETE /milestone/remove/{id}` — `_require_admin(claims)`。子イベントは FK `ondelete SET NULL` で解放(イベントは残す)。

### Task 5: イベント ↔ マイルストーン/完了連携
**Files:** Modify `app/routers/timetable.py`
- `/event/add`: `body.milestone_id` があれば親マイルストーンが同一 group であることを検証してセット(不一致 400)。`body.completed` をセット。
- `/event/update/{id}`: `milestone_id`(移動/解除 NULL)と `completed` の更新に対応。milestone 変更時は group 整合を再検証。
- `/group/all`・`/event/all`・`/event/user`: `to_dict()` の追加キー `milestone_id` / `completed` がそのまま返る(後方互換)。

### Task 6: Alembic マイグレーション(準備のみ)
**Files:** Create `alembic/versions/xxxx_add_milestone.py`
- 新テーブル `T_MILESTONE` 作成 + `T_TIMELINE_EVENT` に `milestone_id`(FK, ondelete SET NULL, nullable)と `completed`(Boolean NOT NULL default false)列を追加。
- `downgrade` は列削除 + テーブル drop。
- **実行しない。** ユーザー本人が PostgreSQL 移行時に適用(AGENTS.md: "Do NOT run DB migrations")。

### Task 7: テスト
**Files:** Create `tests/test_milestone.py`、Modify `tests/test_timetable.py`
- SQLite in-memory(既存 StaticPool + get_db オーバーライド方式を踏襲)。
- テスト項目:
  - 管理者のみ `/milestone/add` と status 設定が可能 / 非管理者は 403
  - milestone create(+201) → GET /milestone/all で取得し group スコープ確認
  - milestone update(title / status) / remove(削除後、子イベント milestone_id が NULL)
  - `/event/add` に `milestone_id`/`completed` を渡して保存される
  - 別 group の milestone への関連付けが 400 で拒否される
  - status の文字列バリデーション(open/in_progress/done 以外は 422 など)
- 実行: `source .venv/bin/activate && uv run pytest -q` → 全テスト pass。

### Task 8: フロント契約メモ(任意・今回は設計のみ)
- `time-table-to-line` 側にマイルストーン UI を足すのは別タスク。バックエンド契約(レスポンス形状)をメモに残す。

---

## 5. テスト / 検証

- `source .venv/bin/activate && uv run pytest -q` — 既存 + 新規テストすべて pass
- `uvicorn app.main:app` → `/health` が `{"status":"ok"}`
- curl で `/milestone/*` と `/event/add?milestone_id=...` を管理者/非管理者両方で確認

---

## 6. リスク・トレードオフ・オープンクエスチョン

**リスク**
- `milestone_id` が nullable でイベントが「孤立」しうる(既存互換のため意図的)。
- 新テーブルは小文字カラム、既存レガシーは大文字 → 混在(`EventORM` が先行例)。
- `status` は管理者の運用によるため、誤設定(例: 子が未完でも done)を機械的に防げない。レビュー UI 側で補完する。
- マイグレーションはユーザー実行前提。Alembic を慎重に準備する。

**決定済みの追加事項:**
- イベント側 `completed` は**表示用フラグとして残す**(確定)。フロントの表示のあり方(プログレス表示)に関わるため。ただしマイルストーン done の自動判定には使わない。

**残るオープンクエスチョン(実装時・契約時に要確認)**
1. マイルストーンの表示対象: チーム全員にタイムライン上で可視化するか、管理者のみか。
2. `status` 値セット open / in_progress / done で十分か。

**将来のすり合わせ(重要):**
- ユーザーはこのマイルストーン構想を要件定義として `requirement-03.md` にまとめる予定。実装時は `requirement-03.md` を読み込み、**このプラン / 本会話の設計とすり合わせて**、変更差分(新たに加わった要件)を反映すること。

---

## 7. 実行ハンドオフ

計画完了・保存済み。`subagent-driven-development` でタスク単位に実装を進める準備ができています(各タスクを新しいサブエージェントへ委譲し、スペック準拠→コード品質の2段階レビュー)。プロジェクトは「一度に1変更ずつ」進める方針のため、まず **上記オープンクエスチョン1(completed 列要否)** と **Task 1 から**始めることを推奨します。進めてよろしいですか?