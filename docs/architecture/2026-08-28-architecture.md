# 2026-08-28 Architecture Snapshot: Milestone Data Schema & Soft Delete Implementation

## Purpose
マイルストーン機能におけるデータ状態管理の柔軟性向上と、安全な削除処理の実装。マイルストーンのステータスをブール型から文字列型（open/waiting/closed）に拡張し、物理削除からソフト削除（closedステータスへの変更）への移行を行う。

## Overview
マイルストーンのステータス管理の柔軟化と、物理削除廃止に伴う論理削除（クローズ処理）の実装。あわせて並列開発をサポートするDevToolsの追加。

## Key Design Decisions
- **Data Modeling**: `MilestoneORM.status` を `Boolean` から `String(10)` に変更。`MILESTONE_OPEN`, `MILESTONE_WAITING`, `MILESTONE_CLOSED` の定数を導入し、状態遷移を管理。
- **Soft Delete**: `/milestone/update/{id}` において物理削除を廃止し、ステータスを `MILESTONE_CLOSED` に変更する形式に統一。これに伴い、クローズ時に所属イベントを一括で完了（`completed=True`）にする処理を維持。
- **DevTools**: 並列開発環境を支えるレビューワーカーと監視スクリプトを導入。

## Next Steps / Improvements
- `waiting` ステータスへの対応。
- マイルストーンの属性（タイトル、説明、終了日）更新機能の実装。

## Commits
- fix #260828: マイルストーン属性の型変更と、並列開発スクリプト
- feature #260828: 削除はしないcloseのみ

## Changed Files
- `app/models.py`
- `app/routers/timetable.py`
- `tests/test_milestone.py`
- `migrations/versions/3be6e8d10186_v0_06.py`
- `devtools/` (review_worker.py, watch_reviews.sh)
- `specs/2026-08-27-spec.md`
