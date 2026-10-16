# specs — 仕様・作業ログ インデックス

このディレクトリには、light_token_server の仕様書・実装ログを日付順に格納しています。

## 命名規則

- `YYYY-MM-DD-spec.md` — その日の作業完了ログ（実装内容・テスト結果・設計判断）
- `YYYY-MM-DD-1-spec.md` / `YYYY-MM-DD-2-spec.md` — 同じ日に複数件ある場合の区別
- `YYYY-MM-DD-<テーマ>-spec.md` — 特定 API / 機能の仕様書

> **注意**: マイルストーン関連の仕様は時系列で改訂されており、**現行契約の正本（canonical）は `2026-10-13-milestone-event-retrieval-spec.md`** です。`2026-10-15-...` は PR #15 の**変更履歴（差分記録）**であり、エンドポイント・権限マトリクスなど現行定義の正は 10-13（正本）を参照します。作業ログ系ファイルは過去の実装記録なので、機能の現行契約を参照する場合は「最新仕様の把握方法」に従ってください。

## 一覧

| ファイル | 作成日 | 内容 |
|---|---|---|
| [2026-08-27-spec.md](./2026-08-27-spec.md) | 2026-08-27 | マイルストーン `status` の Boolean → String(10) 移行完了（`MILESTONE_OPEN` / `MILESTONE_WAITING` / `MILESTONE_CLOSED` 定数化）。全 37 テスト パス |
| [2026-08-28-1-spec.md](./2026-08-28-1-spec.md) | 2026-08-28 | `remove_milestone` を物理削除 → soft close 化（`target.status = MILESTONE_CLOSED`、レスポンス `{"closed": id}`）。全 37 テスト パス（baseline 失敗なし） |
| [2026-08-28-2-spec.md](./2026-08-28-2-spec.md) | 2026-08-28 | Issue #9: `guideline_end_date` スペル修正 + DB リビジョン、`/milestone/update/{id}` 拡張、`/milestone/all` を open+waiting に変更。テスト 42 passed |
| [2026-08-31-spec.md](./2026-08-31-spec.md) | 2026-08-31 | 全 44 テスト（うち milestone 17 件）成功。旧 boolean 値の正規化マイグレーション、`_next_color` の waiting 対応、`close_milestone` → `update_milestone` 改名 |
| [2026-09-07-spec.md](./2026-09-07-spec.md) | 2026-09-07 | `update_event_item` の `milestone_id` 判定を `is not None` → `model_fields_set` に変更（明示 null で「所属なし」保存）。44 passed |
| [2026-09-08-spec.md](./2026-09-08-spec.md) | 2026-09-08 | Task-11: マイルストーン自動 close スケジューラ（waiting → 猶予 5 日超過で自動 closed、APScheduler + BackgroundScheduler、`ENABLE_MILESTONE_SCHEDULER` で切替）。全テスト 50 件 GREEN |
| [2026-09-11-spec.md](./2026-09-11-spec.md) | 2026-09-11 | Task-12: `update_milestone` の re-open 分岐で子イベント `completed` を False に復帰。全テスト 51 passed |
| [2026-10-13-milestone-event-retrieval-spec.md](./2026-10-13-milestone-event-retrieval-spec.md) | 2026-10-13 | **現行契約の正本（canonical）**。マイルストーン所属イベント取得 API の完全仕様（`GET /milestone/{id}/events`＝open/waiting・非 admin 閲覧可、`GET /milestone/closed/{id}/events`＝closed・admin 限定、`group_name` 付与、レスポンス・権限マトリクス）。Issue #40 / PR #15 で改訂済み |
| [2026-10-15-milestone-events-group-name-auth-spec.md](./2026-10-15-milestone-events-group-name-auth-spec.md) | 2026-10-15 | **PR #15 の変更履歴（差分記録）**。権限緩和（open/waiting を非 admin にも許可）と `group_name` 付与の動機・実装箇所・テスト変更・影響範囲を記録。現行定義の正は上記の正本（10-13）を参照 |

## 最新仕様の把握方法

現在の正しい仕様を知りたい場合は、以下を確認してください。

- `specs/2026-10-13-milestone-event-retrieval-spec.md` — マイルストーン所属イベント取得 API 仕様（**現行契約の正本**）
- `AGENTS.md` — マイルストーン機能の概要（実装範囲）
- `.hermes/rules/milestones.md`（または `.hermes/rules/milestones.md` 相当のルールファイル）— 詳細な権限モデル・API 契約・色ルール
- `.hermes/rules/requirements/requirement-03.md` — マイルストーン機能の要件定義

> ⚠️ 8 月末〜9 月の作業ログ系ファイルは過去の実装記録であり、仕様を参照する用途には古い場合があります。機能の現行契約は必ず上記の「最新仕様の把握方法」で確認してください。マイルストーン API の現行アーキテクチャ契約（権限・状態遷移・色ルール）は `tasks/` 側の設計 docs と `.hermes/rules/milestones.md` に集約されています。
