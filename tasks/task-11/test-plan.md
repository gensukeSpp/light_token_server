# Task-11 Test Plan — グレース期間後のマイルストーン自動 closed

> テスト基盤: `tests/conftest.py`(SQLite + StaticPool + `dependency_overrides[get_db]`)。
> ジョブ本体は **API 経由ではなく純粋関数 `close_expired_waiting_milestones(db, today)` を
> 直接呼んで検証**する(`today` を注入できるため境界を決定的にテスト可能)。

## 前提・セットアップ

- テストでは `ENABLE_MILESTONE_SCHEDULER` を無効化するか、そもそもスケジューラを
  起動しない(既存 conftest の TestClient は lifespan を実行するため、
  万一多重起動を避けるため dev flag で OFF にする設定を考慮)。
- waiting 状態の生成: 既存ヘルパー `_add(client, ...)` でマイルストーン作成 →
  `POST /milestone/update/{id}` に `{"accomplished_date": "YYYY-MM-DD"}` で waiting 化
  (契約: 202, 320-327 行)。

## 追加テスト一覧

| # | テスト名 | シナリオ | 期待 |
|---|---|---|---|
| 1 | `test_auto_close_before_grace` | accomplished_date が猶予内(例: GRACE=5, today から 3 日前)で waiting | `close_expired_waiting_milestones(...)` が **0** 件、status は **waiting のまま** |
| 2 | `test_auto_close_after_grace` | accomplished_date が猶予超過(today から +6 日前)で waiting | 戻り値 **1**、status が **closed** |
| 3 | `test_auto_close_only_waiting` | open / closed が混在。several waiting のみ対象 | open / closed は変化せず、waiting 超過分のみ closed |
| 4 | `test_auto_close_keeps_completed` | 子イベントを持つ waiting 超過マイルストーン | マイルストーンは closed、**子イベント completed は True のまま(自動 closed では変更されない)** |
| 5 | `test_auto_close_boundary` | accomplished_date+5日 == today のケース | 境界確定(`<=` 採用): **当日をもって closed になる**。`+4日` は猶予内のまま |
| 6 | `test_auto_close_no_accomplished` | status が open で accomplished_date が None | 対象外(0 件)。None を誤って閉じない |

## 検証コマンド

```bash
cd light_token_server
uv run pytest tests/test_milestone.py -v
# 全件(既存 16 + 追加 6)が GREEN であること
```

## 回帰対象(壊さない確認)

- `test_milestone_remove_closes_instead_of_delete` — remove の即時 closed 契約が不変
- `test_milestone_update_accomplished_sets_waiting` — accomplished_date → waiting が不変
- `test_milestone_reopen_from_waiting` — waiting → open(再 open)が不変
- `test_milestone_all_returns_open_only` — `/milestone/all` の open+waiting 射影が不変

## 手動 QA(利用者実施)

1. env で `MILESTONE_CLOSE_GRACE_DAYS=0` + `MILESTONE_CLOSE_INTERVAL_MINUTES=1` に設定
2. サーバー起動し、waiting のマイルストーンを作成
3. 1 分後、`/milestone/all` から消え、DB 上 `status=closed` になることを API/画面で確認
4. 猶予日数を戻し、閉じたマイルストーンの配色がデフォルト(`#2196f3`)に戻ること(フロント)を確認