# 2026-08-28 Architecture Snapshot: Milestone Update API Expansion & Status Management

## Purpose
マイルストーン管理機能の柔軟性を向上させる。属性更新APIを拡張し、タイトル、説明、終了日、完了日の更新に対応。あわせてステータス管理に `waiting` を追加し、将来的な状態遷移（再オープン）の基盤を構築する。

## Overview
マイルストーン更新 API の入力パラメータ拡張と、データ状態管理における `waiting` ステータスの導入。

## Key Design Decisions
- **API Expansion**: `/milestone/update/{id}` に `title`, `description`, `guideline_end_date`, `accomplished_date` を追加。Pydantic の `model_fields_set` を用いて、リクエストで明示的に渡されたフィールドのみを更新するパッチ適用的な挙動を実現。
- **Status Management**: マイルストーンのステータスに `waiting` を追加。`waiting` を含む open/waiting ステータスのマイルストーンを一覧取得 API (`/milestone/all`) で対象とするよう変更。
- **Data Modeling**: `guideline_end_date` のスペルミスを修正。

## Next Steps / Improvements
- 猶予期間後のステータス自動クローズ機能の実装。

## Commits
- Feature/improve update api/9 (PR #10)

## Changed Files
- `app/models.py`
- `app/schemas.py`
- `app/routers/timetable.py`
- `tests/test_milestone.py`
- `migrations/versions/e0fbbca5c733_v0_07.py`
