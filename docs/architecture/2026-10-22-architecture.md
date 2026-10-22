# アーキテクチャスナップショット: 2026-10-22 (Issue #44: イベント progress の明示的 null 解除対応)

## 目的 (Purpose)
フロントエンド側からの要望（Issue #44: 一度設定した進捗 `progress` を「未定（null）」に戻せない問題）に対応するため、バックエンドのイベント更新 API における `progress` の更新判定を改修し、明示的な `null` 送信による解除を可能にする。

## 概要 (Overview)
- **API 改修**: `POST /event/update/{id}` において、`progress` の更新を従来の「値が non-None かどうか」から、`milestone_id` と同様に `model_fields_set` を用いた「フィールド自体がリクエストに含まれているか（明示的 null を含む）」の判定方式に変更。

## キーとなる技術的変更 (Key design decisions)
- **`model_fields_set` によるフィールド送信判定**: 
  - `if body.progress is not None:` を `if "progress" in body.model_fields_set:` に変更。これにより、クライアントから `{"progress": null}` が送信された際に `target.progress = None` が正常に適用され、DB上で進捗のクリア（未定への復帰）が可能になった。
- **既存仕様との整合性**:
  - 既に `milestone_id` の更新などで採用されている設計パターンを踏襲し、一貫性と型安全性を維持。

## 今後の改善点 (Next steps/improvements)
- フロントエンド（`gensukeSpp/time-table-to-line` PR #44）との結合確認の継続。

## コミットリスト
- `feat #261022: イベント progress に null(None) 値を入れる` (PR #19)

## 変更されたファイル
- `app/routers/timetable.py`
- `specs/2026-10-22-progress-null-spec.md`
- `specs/README.md`
- `tests/test_timetable.py`
