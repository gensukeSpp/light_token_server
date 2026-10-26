# アーキテクチャスナップショット: 2026-10-26 (Issue #22: /event/add におけるスタッフ情報の照合)

## 目的 (Purpose)
PR #21 のレビュー指摘（「作成時の staff_id 検証は未対応」）に基づき、イベント作成 API (`POST /event/add`) における `staff_id` の検証を実装。非 admin ユーザーが自分以外の `staff_id` でイベントを作成することを防ぎ、セキュリティと整合性を向上させる。

## 概要 (Overview)
- **API 改修**: `POST /event/add` 内で、認証されたユーザーのトークンクレーム (`claims`) とリクエストボディの `staff_id` を照合するヘルパー関数 `_require_event_create_owner_or_admin` を追加。
- **権限制御**:
  - 非 admin ユーザー: `staff_id` が自身の `user_id` と一致しない場合、403 Forbidden を返却し DB 書き込みを行わない。
  - admin ユーザー: 他人名義でのイベント作成を許可（従来どおり）。

## キーとなる技術的変更 (Key design decisions)
- **作成時専用検証ヘルパーの導入**:
  - `app/routers/timetable.py` に `_require_event_create_owner_or_admin(staff_id, claims)` を追加し、`append_event_item` の冒頭（`db.add` 前）で呼び出すことで不正な作成を早期遮断。
- **テストカバレッジの強化**:
  - `tests/test_timetable.py` に受入条件 3 件 + エッジケース 1 件（合計 4 件）のテストを追加し、TDD アプローチで検証を確実化。

## 今後の改善点 (Next steps/improvements)
- フロントエンド側との結合検証および運用環境での動作確認。

## コミットリスト
- `9edad96 test: issue-22 /event/add の staff_id 照合テストを追加 (RED)`
- `1c1e582 fix #22: /event/add の staff_id を認証ユーザーと照合 (admin は例外)`
- `0053f67 docs: issue-22 の実装計画・差分 配録・権限契約を更新`

## 変更されたファイル
- `app/routers/timetable.py`
- `tests/test_timetable.py`
- `specs/2026-10-23-event-add-staff-owner-spec.md`
- `specs/README.md`
- `tasks/issue-22/` 関連ファイル
