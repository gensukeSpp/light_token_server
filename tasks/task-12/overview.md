# Task-12 実装計画 — waiting からの re-open で子イベント completed=False に戻す

> **For Hermes:** 実装は TDD(失敗→実装→成功→Commit)でタスク単位に進める。実装前に本ファイル、
> `.hermes/rules/milestones.md`、`app/routers/timetable.py` の既存 `/milestone/update` 実装、
> `tests/test_milestone.py` の既存 re-open テスト(232 行)を読み、**waiting 遷移・自動 closed・remove の既存契約を壊さない**こと。

**Goal:** `waiting`(猶予期間)中のマイルストーンを `accomplished_date=null` で re-open(→ `open`)した際、
**子イベントの `completed` を `False` に戻す**。waiting 遷移時に一括で `True` にした子イベントを、
再 open で非完了に戻してマイルストーン配色(milestone color)へ復帰させる。

**現状との差分(仕様変更):** 現行の re-open は status→`open`・accomplished_date→`None` のみで
子イベント completed を変更していない(`app/routers/timetable.py:328-331`)。これは `.hermes/rules/milestones.md:28` にも
「re-open ではイベント completed は変更しない(非破壊)」と明記済み。**今回この仕様を書き換える**ため、
当該ルール行の更新も必須。

---

## この段階で完成するもの(成果物)

- `app/routers/timetable.py` の `update_milestone` re-open 分岐が、所属子イベントの `completed` を `False` に一括更新する
- `.hermes/rules/milestones.md:28` を新挙動に合わせて更新(「completed を False に戻す」に変更)
- `tests/test_milestone.py` に re-open で子イベント completed が False に戻る統合テストを追加
- 既存テスト(自動 closed 含む)が全て通ること

## スコープ外(今回はやらない)

- **closed からの再 open** — 従来どおり 409 で拒否(`update_milestone:306`)。re-open は waiting 由来のみ
- **フロントエンド(time-table-to-line)変更** — completed=False でイベント色がマイルストーン色に戻るのは
  既存フロント仕様(completed ならデフォルト色 `#2196f3`)で自動追従。追加実装不要
- **closed 確定後(自動/remove)の子イベント completed 整合** — 次タスクで扱う(本タスクの対象外)
- 手動で `completed` を個別操作した子イベントの保護 — 今回の仕様では re-open 時に**全ての**所属イベントを
  `False` にする(ユーザー指定どおり)

## 現在のコンテキスト / 前提

- `update_milestone`(`app/routers/timetable.py:294-335`):
  - `accomplished_date` 値あり → `status=waiting` + 子イベント全 `completed=True`(timetable.py:320-327)
  - `accomplished_date` 明示 None → re-open:`status=open` + `accomplished_date=None`。**子イベント completed は現状無変更**
    (timetable.py:328-331)
- `model_fields_set` で「accomplished_date が送られたか(None でも)」を判別している(`timetable.py:320`)。この仕組みは維持
- 判定は「明示的 null なら re-open」であり、`open` 状態のマイルストーンに null を送っても
  同様に `status=open` のまま(実害なし)。ただし re-open の completed リセットは
  **waiting 由来のときだけ**意図どおり。既に open のものを再 open しても completed=False 化は
  open 状態では子イベント completed が通常 False のため影響なし(安全)
- 子イベントは `EventORM.milestone_id == milestone_id` で特定(`timetable.py:324-327` と同じクエリを使用)
- `MilestoneORM.status` 定数 `MILESTONE_OPEN/WAITING/CLOSED` は `app/models.py` に定義済み
- テスト: `tests/conftest.py` が SQLite + StaticPool + `get_db` override。ヘルパー `_add` / `_add_event(client, milestone_id=)`
  / `_make_waiting(client, title, accomplished)` / `_bearer(admin=True)` を再利用できる
  (`tests/test_milestone.py:17-37,305-317`)

## 決定事項(利用者確認済み 2026-09-11)

1. **re-open 時の子イベント completed**: waiting 由来の re-open では、所属子イベントの `completed` を
   **一括で `False` に戻す**。waiting 遷移時に全 True にしたものを元に戻す(対称的な非破壊)。
2. **対象**: re-open の判定は現行どおり `accomplished_date in model_fields_set` かつ `None`。これに
   「子イベント completed=False 一括更新」を追加する。エンドポイント・パラメータ形状は不変。
3. **既存契約**: waiting 遷移(値あり時 completed=True)・自動 closed・remove は**無変更**。
4. **ルール文書**: `milestones.md:28` の「completed は変更しない(非破壊)」を
   「re-open 時は子イベント completed を False に戻す」へ更新する。

## タスク分解(TDD)

### Task 1: 失敗テストを追加(re-open で completed が False に戻る)

**Files:** Modify `tests/test_milestone.py`

1. `test_milestone_reopen_from_waiting`(232 行)の後に、新テストを追加:
   `test_milestone_reopen_resets_child_completed` を作る。
   - `_add` でマイルストーン作成 → `_add_event(client, milestone_id=..)` で子イベントを2つ作成
   - `/milestone/update/{id}` に `{accomplished_date: "2026-08-20"}` → waiting、子 completed=True を確認
   - `/milestone/update/{id}` に `{accomplished_date: None}` → re-open
   - 子イベント取得(`/event/...` または API 契約に合わせ)で completed が **False** に戻ったことを assert
2. `uv run pytest tests/test_milestone.py -v` で **失敗**(RED)を確認

### Task 2: 実装(update_milestone の re-open 分岐に completed リセット追加)

**Files:** Modify `app/routers/timetable.py`

- `update_milestone` の re-open 分岐(`timetable.py:328-331`)で、waiting 遷移と同じクエリ
  (`EventORM.milestone_id == milestone_id`)で子イベントを取得し、`ev.completed = False` を設定
  ```python
  else:
      # re-open: waiting の再 open。accomplished_date を None に戻し、
      # waiting 遷移時に一括 True にした子イベント completed を False に戻す(配色復帰)。
      target.status = MILESTONE_OPEN
      target.accomplished_date = None
      for ev in db.query(EventORM).filter(EventORM.milestone_id == milestone_id).all():
          ev.completed = False
  ```
- コメント(317-319 行)の「イベント completed は変更しない」記述を新挙動に合わせて更新
- `uv run pytest tests/test_milestone.py -v` で **成功**(GREEN)+ 既存全件(自動 closed 含む)が通ることを確認

### Task 3: ルール文書更新

**Files:** Modify `.hermes/rules/milestones.md`

- 28 行「`waiting` からは re-open 可…イベントの `completed` は変更しない(非破壊)」を
  「`completed` を False に戻す(子イベントを非完了へ復帰)」に書き換え
- 併せて 27 行(waiting 遷移時に completed=True)との対称性が読み取れるよう整える

### Task 4: 全テスト実行 + lint + 最終確認

- `source .venv/bin/activate && uv run pytest -v` で全体(他ルーター含む)が通ること
- 未使用 import / コメント残骸がないか確認(既存運用に合わせ ruff があれば実行、無ければ省略)
- `git status` で無関係変更(app/config.py の APP_URL 等)を巻き込んでいないか確認
- Commit:
  - `docs #(task12): waiting からの re-open で子イベント completed を False に戻す仕様を反映`

> 完了後、利用者の実ブラウザ / API 検証(re-open で子イベントの色が milestone color に戻ること)を待つ。
