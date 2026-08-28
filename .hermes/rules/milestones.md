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
- `status="open"` → 作成直後。`status="closed"` → 達成済み(本実装では `/milestone/remove` のみ generated)。`status="waiting"` → 再 open の猶予期間(waiting for close)
- **accomplished_date 設定時は `waiting` へ遷移**(`closed` へ直接遷移しない)。`waiting` 中は子イベントの `completed=True` を自動更新(close 相当)
- **`waiting` からは re-open 可**: update で `accomplished_date` に `null` を明示すると `open` へ戻る。イベントの `completed` は変更しない(非破壊)
- 一度 `closed` にしたマイルストーンへの再 update は 409 で拒否(API レイヤ)。本 Issue では閉じの確定はデータ上生成しない → re-open は waiting 由来のみ
- `completed=True` または `milestone_id` が削除されたイベントはデフォルト色 (`#2196f3`) に変更
- マイルストーンはグループ横断共有。`group_id` カラムは不要

## Permission model
- `admin=True` のユーザー全員が作成/クローズ/削除可能
- 従来の「そのグループの管理者」→ 誤解を招く表現。実態は「全 admin ユーザー」
- 閲覧はグループ単位(既存のトークン `group_id` でフィルタ)

## Color rules
- 10 固定パターン: ` #9c27b0 #009688 #795548 #607d8b #e91e63 #3f51b5 #00bcd4 #ff5722 #8bc34a #ff9800`
- 作成時、open マイルストーンと被らない色を自動選択
- 10 件超えた場合は 1 番目の色から cyclic に戻す

## API endpoints
- `POST /milestone/add` — admin のみ、カラータブルから衝突回避
- `GET /milestone/all` — open + waiting 一覧(`status != "closed"` を返す。Issue #9 で変更多)
- `POST /milestone/update/{id}` — admin のみ・部分更新(`title?` / `description?` / `guideline_end_date?` / `accomplished_date?`)。編集フィールドは None 以外を反映し status 不変。`accomplished_date` 値あり → `waiting` + 子 completed=True、明示 `null` → re-open(`open`)
- `DELETE /milestone/remove/{id}` — admin のみ、削除でなく `status=closed`(子 completed=True)を返す `{"closed": id}`
- `POST /event/add` — `milestone_id` optional 追加
- `POST /event/update/{id}` — `completed` 対応

## UI conventions
- Japanese date format (UTC+9) for display only (stored as-is)
- Event default color: `#2196f3`
- Clicked color: `#ffc107`