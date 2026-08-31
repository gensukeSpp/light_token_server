# Issue-9 テスト計画 — Milestone 更新処理 API 契約改善

## 方針
- 自動テストは **SQLite インメモリ**(`poolclass=StaticPool` + `check_same_thread=False`)で実施。実 DB(PostgreSQL)不要。
- 既存 `tests/test_milestone.py` の構成(Bearer トークン直接生成 `_bearer` / `_add` / `_add_event` ヘルパ)を踏襲する。セッションクッキーまわりに依存しない。
- ステータス遷移は「open / waiting のみ本 Issue で生成、closed は(DB データ上)自動生成しない」前提。既存の closed 期待テストは置き換える。

## テスト対象・期待結果

### `tests/test_milestone.py`(変更・追加)— マイルストーン更新契約
| テスト | 期待 |
| :--- | :--- |
| `test_milestone_update_edits_title_only` (追加) | `POST /milestone/update/{id}` json `{"title":"renamed"}` → 200、`title=="renamed"`、`status=="open"`(accomplished_date 未指定は状態変化なし) |
| `test_milestone_update_accomplished_sets_waiting` (追加) | accomplished_date 指定 → 200、`status=="waiting"`(closed ではない) |
| `test_milestone_reopen_from_waiting` (追加) | waiting のマイルストーンに `{"accomplished_date": null}` → 200、`status=="open"`、`accomplished_date is None` |
| `test_milestone_close_sets_waiting_and_completed` (変更) | waiting 遷移で、子イベント `completed=True`(判断 3 の「finished at waiting」確定後に) |
| `test_milestone_reclose_returns_409` (変更) | closed 状態へ再入力→409。closed を DB に無理やり挿入して検証 or waiting の再指定が 409 でないことを確認 |
| `test_milestone_all_returns_open_only` (変更) | open → waiting でも一覧に出続ける(現行の「close 後は消える」を置換) |
| `test_milestone_all_includes_waiting` (追加) | `/milestone/all` が open + waiting を含む(2 件) |
| `test_milestone_add_avoids_used_color` (不変) | 色衝突回避ロジックは open のみ基準で変更なし |
| `test_milestone_remove_closes_instead_of_delete` (不変) | remove は現状のまま(closed + 子 completed + `{"closed": id}`) |
| `test_event_add_accepts_milestone_id` / `test_event_update_sets_completed` (不変) | 既存 /event 契約の回帰 |

## 新契約での status 遷移(core テスト)
```
open    + accomplished_date=date  -> waiting
waiting + accomplished_date=date  -> waiting (編集、状態不変)
waiting + accomplished_date=null  -> open    (re-open、accomplished_date=None)
closed  + (再入力)                 -> 409 (既閉)
```
> re-open の実装は `model_fields_set` で「accomplished_date が送られたか」を判定(タスク 3)。

## 実行コマンド
```bash
source .venv/bin/activate
uv run pytest tests/test_milestone.py -v
uv run pytest -v   # 全体(回帰)
```

## 検証ポイント
1. `accomplished_date` 設定で status が **waiting**(closed でない)になる。
2. update が **部分更新**(title のみ編集で状態不変)。未指定フィールドは維持。
3. **re-open**(waiting → open)が事の実に。
4. `/milestone/all` が **open + waiting** を返す(`status != 'closed'`)。受け入れ 2 遵守。
5. `/milestone/remove`・`/milestone/add`・color ロジックが無変化。
6. `guidline_end_date` → `guideline_end_date` へのスペル修正が全所で反映(既存テストの field 参照含む)。
7. 既存 health / login / tokens / timetable の回帰が壊れない。

## 手動 QA(利用者実施)
- バックエンド(`uvicorn app.main:app`)を起動し、admin ユーザーで `/milestone/add` → `/milestone/update`(accomplished_date 入力)で一覧に「waiting」として残ることを /milestone/all で確認。
- カラム変更(`guideline_end_date`)後の PostgreSQL マイグレーションを利用者が実施し、再起動して /milestone/* の動作確認。
- フロント(Issue #18)との「猶予期間中表示」連携を確認。