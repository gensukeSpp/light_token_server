---
created: 2026-10-22T11:57
updated: 2026-10-22T11:57
---

# Issue #44（バックエンド分）— イベント `progress` を明示的 null で解除可能に

対象ブランチ: `feature/progress-null`。フロントは `time-table-to-line`（branch `fix/three-repairments/44`）と連携。全体の仕様は `time-table-to-line/specs/2026-10-22-spec.md` を参照。

## 変更内容

`app/routers/timetable.py` の `update_event`（`POST /event/update/{id}`）で、`progress` の更新判定を `if body.progress is not None:` から `if "progress" in body.model_fields_set:` に変更した（`milestone_id` が既に採用しているパターン、および `update_milestone` の `accomplished_date` と同じ前例）。

- **変更前**: `progress` が `None` のときは更新をスキップ → 一度値を入れたイベントの進捗を「未定」へ戻せない。
- **変更後**: 「送られたか（`model_fields_set` に含まれるか、None でも）」で判別 → **明示的な `null` 送信で `progress = None` として保存**（解除）できる。

```python
if body.summary is not None:
    target.summary = body.summary
# Issue #44: progress も「送られたか(None でも)」で判別し、明示的 null で解除できるようにする
# （milestone_id と同じパターン）。summary は「送られたら上書き」のままで良い。
if "progress" in body.model_fields_set:
    target.progress = body.progress
```

- `summary`（`is not None`）は変更しない（空文字クリアはスコープ外・YAGNI）。
- スキーマ変更不要: `EventUpdate.progress: str | None` のまま。DB カラム `progress = Column(String(10), nullable=True)` のまま。

## テスト

`tests/test_timetable.py` に `test_event_update_progress_null_clears` を追加。

- 値を設定（`progress: "done"` → 200 / レスポンス `"done"`）
- `null` で解除（`progress: None` → 200 / レスポンス `None`）
- `GET /event/all` でも DB 反映（`progress is None`）を確認

## 検証結果

- `pytest tests/test_timetable.py` — **20 passed**
- 全体 `pytest -q` — **79 passed**（既存 `test_event_update` の progress 上書きも回帰なし）

## 既知の注意

- Pyright の誤検知（SQLAlchemy `Column[str]` への `str | None` 代入警告）は `milestone_id` と同じパターンで、実行時は問題なし・既存方針どおり無視。
- フロント側は「未定」を in-memory では `undefined` で持ち、送信時に `?? null` で明示的 null へ変換して本エンドポイントに送る（詳細はフロントの仕様を参照）。