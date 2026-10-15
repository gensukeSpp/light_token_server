# アーキテクチャスナップショット: 2026-10-15

## 目的 (Purpose)
マイルストーンから所属するイベントを状態別（open/waiting と closed）に参照できる API エンドポイントを追加し、管理者がグループを跨いでイベントの紐付け状況を確認できるようにする。

## 概要 (Overview)
- **新規 API エンドポイント**:
  - `GET /milestone/{milestone_id}/events`: `open` または `waiting` 状態のマイルストーンに所属する全グループのイベントを取得。
  - `GET /milestone/closed/{milestone_id}/events`: `closed` 状態のマイルストーンに所属する全グループのイベントを取得。
- **認可制御**: いずれのエンドポイントも管理者権限 (`admin` claim) を必須とし、非管理者の場合は `403 Forbidden` を返す。

## キーとなる技術的変更 (Key design decisions)
- **グループ横断の取得**: マイルストーン自体がグループ横断で共有される仕様に合わせ、紐づくイベントも特定のグループに限定せず全グループから取得する設計を採用。
- **状態別エンドポイントの分離**: `open`/`waiting` と `closed` でエンドポイントを明確に分離し、対象外の状態や存在しないマイルストーン ID に対しては `404 Not Found` を返却。
- **テストの拡充**: `tests/test_milestone.py` に新規 API エンドポイントの網羅的なテストケースを追加し、権限チェックや状態別の振る舞いを検証。

## 今後の改善点 (Next steps/improvements)
- フロントエンド UI からの新 API 統合と、マイルストーン詳細ビューにおけるイベント一覧表示の実装。

## コミットリスト
- `074d863` feat 261015: イベント from マイルストーン API

## 変更されたファイル
- `.github/copilot-instructions.md`
- `.hermes/rules/milestones.md`
- `app/config.py`
- `app/routers/timetable.py`
- `app/templates/index.html`
- `specs/2026-10-13-milestone-event-retrieval-spec.md`
- `tests/test_milestone.py`
