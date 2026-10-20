# アーキテクチャスナップショット: 2026-10-19

## 目的 (Purpose)
PR #17 および PR #18 の変更を反映し、マイルストーン関連APIのセキュリティ（機密情報の除外）と機能拡張（クローズ済みマイルストーン一覧取得）をドキュメント化する。

## 概要 (Overview)
- **PR #17 (Issue #16 修正)**: マイルストーン所属イベント一覧取得API (`GET /milestone/{milestone_id}/events` および `GET /milestone/closed/{milestone_id}/events`) における非adminへの `summary` 露出防止と、イベント辞書生成時の二重 `to_dict()` 呼び出しを修正。
- **PR #18 (Issue #41 連携)**: クローズされたマイルストーンの一覧を取得する新規APIエンドポイント `GET /milestone/closed` を新設。

## キーとなる技術的変更 (Key design decisions)
- **ホワイトリスト形式のシリアライゼーション (`to_milestone_dict`)**: 
  - イベント取得時に `EventORM.to_dict()` ではなく、必要なフィールドのみを返すホワイトリスト形式の `to_milestone_dict()` を採用。
  - レスポンスから `summary` を完全に除外（`/event/all` では引き続き `summary` を返却）。
- **Closedマイルストーン一覧API (`GET /milestone/closed`)**:
  - 管理者 (`admin` claim) 専用のエンドポイントとして実装。
  - ステータスが `closed` のマイルストーンを対象とし、`accomplished_date IS NULL` が末尾になるように降順ソートして返却。

## コミットリスト
- `39979be` fix #261019: Issue #16 summary 呼ばない、 to_dict() 二重呼び出し修正
- `8174cb8` feat(issue-41): 閉じたマイルストーン一覧 GET /milestone/closed を追加

## 変更されたファイル
- `.hermes/rules/milestones.md`
- `app/models.py`
- `app/routers/timetable.py`
- `specs/2026-10-13-milestone-event-retrieval-spec.md`
- `specs/2026-10-19-milestone-events-summary-exclusion-spec.md`
- `specs/README.md`
- `tasks/issue-16/plan.md`
- `tests/test_milestone.py`
