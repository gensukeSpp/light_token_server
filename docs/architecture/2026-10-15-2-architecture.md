# アーキテクチャスナップショット: 2026-10-15 (#2)

## 目的 (Purpose)
Issue #40 に伴い、マイルストーンイベント参照 API (`GET /milestone/{milestone_id}/events` / `open` + `waiting` 対象) における認可制御の緩和（管理者限定から `require_token` のみへ変更）および、各イベントへの `group_name` 付与（`group_id` から `Team.SHORTNAME` を解決）を実装した。

## 概要 (Overview)
- **認可制御の緩和**: `open` および `waiting` 状態のマイルストーン所属イベント一覧取得 (`GET /milestone/{milestone_id}/events`) について、非管理者の一般ユーザーでも閲覧可能に緩和（管理者限定は `closed` 用エンドポイントに維持）。
- **`group_name` 付与**: イベントデータ取得時に `Team` モデルからグループ名 (`SHORTNAME`) を解決し、レスポンスの各イベント辞書に `group_name` を追加。
- **テストと仕様の更新**: 非 admin での正常系・異常系テストの拡充および仕様書・アーキテクチャスナップショットの更新。

## キーとなる技術的変更 (Key design decisions)
- **フロントエンド連携上の制約対応**: グループ名 (`group_name`) はフロントエンド側で直接解決することが困難なため、バックエンド側で `db.get(Team, d["group"])` を用いて効率的に解決・付与する設計を採用。
- **認可の分離**: 全ユーザーがマイルストーン画面の「...」ボタン等からイベント一覧を閲覧できるように `open`/`waiting` 用の閲覧権限を `require_token` に緩和しつつ、完了済み (`closed`) 用のエンドポイントは引き続き管理者限定として厳格性を維持。

## 今後の改善点 (Next steps/improvements)
- フロントエンド（`gensukeSpp/time-table-to-line` の PR）との統合テストおよび実際の UI 動作確認。

## コミットリスト
- `ab5127f` feat(issue-40): milestone events に group_name 付与 & 閲覧を require_token のみに緩和
- `e599666` docs(issue-40): milestone events API 仕様を改訂（閲覧権限緩和・group_name 追加）

## 変更されたファイル
- `app/routers/timetable.py`
- `specs/2026-10-13-milestone-event-retrieval-spec.md`
- `tests/test_milestone.py`
- `docs/architecture/2026-10-15-2-architecture.md`
- `docs/architecture/README.md`
