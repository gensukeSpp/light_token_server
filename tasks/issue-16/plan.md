# Issue #16 実装計画 — マイルストーン所属イベント API の `summary` 除外 / `to_dict` 二重呼び出し解消

**Goal:** `GET /milestone/{id}/events` と `GET /milestone/closed/{id}/events` のレスポンスから `summary` を
除去し（ホワイトリスト化）、`_get_milestone_events` の `to_dict()` 二重呼び出しを 1 回に統一する。

**参照:** Issue #16 / フロントエンド PR #42 レビュー `.github/reports/pr-42-review.md` の
[中-1]（非 admin に他グループのイベント summary まで露出）と [低-6]（to_dict 二重呼び出し）。

**Tech Stack:** FastAPI / SQLAlchemy 2 / pytest（SQLite in-memory）/ uv + venv。

## 1. 現状（読み取ったコード）

- `app/models.py:109-126` `EventORM.to_dict()` が 11 キーを返す（`summary` を含む）。
  `/event/all` `/event/user` `/group/all` も同メソッドを使うため、**`to_dict()` 自体は変更しない**。
- `app/routers/timetable.py:297-318` `_get_milestone_events()`
  - 310行: `group_ids = {d["group"] for d in (ev.to_dict() for ev in events)}`（1 回目）
  - 313-316行: ループ内で `d = ev.to_dict()`（2 回目）→ [低-6]
  - open/waiting 用（`:321`）と closed 用（`:332`）の両方がこの共通関数を通る。
- `tests/test_milestone.py:766-792` が 11 キー + `group_name` を完全一致で検証（`summary` を含む）→ 更新必要。
- フロント `time-table-to-line` の `MilestoneEventsDrawer` は `summary` を参照していない
  （`MilestoneEventProps.summary?` は型定義のみ）→ フロントの実行時修正は不要。
- ベースライン: `pytest tests/test_milestone.py -q` → **46 passed**。

## 2. 方針（決定事項）

1. **ホワイトリスト方式**で公開キーを固定する。ブラックリスト（`pop("summary")`）は将来カラムが
   増えたときに漏えいが再発するため採らない（レビュー [中-1] の修正方向に一致）。
2. `EventORM` に `to_milestone_dict()` を追加。公開キーは
   `id / staff_id / group / start / end / title / progress / milestone_id / completed` の 9 キー。
   `group_name` はルータ側で付与（Team 一括取得による N+1 回避を維持）。
3. 変更点は **`_get_milestone_events`（`app/routers/timetable.py:297-318`）1 箇所**に集約する。
   この関数は **open/waiting 用（非 admin 閲覧可・[中-1] の本体）** と closed 用（admin 限定）の
   両方が通るため、open/waiting・closed の**どちらでも `summary` は非公開**になる。
   要件 1 の主対象は open/waiting（Task 1・Task 2 で担保）、closed は同じ変更の帰結（Task 4 で回帰固定）。
4. `to_dict()` は `/event/*` 用にそのまま残す（日時フォーマット定数を共有して二重定義を避ける）。
5. 1 イベントにつき dict 生成は 1 回。`group_ids` の収集も生成済みリストから行う。

## 3. 変更ファイル

| 種別 | パス | 内容 |
|---|---|---|
| Modify | `app/models.py` | `_EVENT_TIME_FORMAT` 定数化、`EventORM.MILESTONE_EVENT_KEYS` と `to_milestone_dict()` 追加 |
| Modify | `app/routers/timetable.py:297-318` | `_get_milestone_events` を 1 パス化 + `to_milestone_dict()` 使用 |
| Modify | `tests/test_milestone.py:766-792` | 期待キーから `summary` 削除 + 非含有アサート |
| Modify | `tests/test_milestone.py:205-237` | closed 経路（共有関数）でも `summary` 非含有を回帰アサート |

※ コミットは本 Issue の必須作業としない（ユーザー判断）。なお `tasks/` は **git 管理下**
（`.gitignore:20` の `# tasks/` はコメントアウトされており、既存の `tasks/task-01/` 等 23 ファイルが
追跡済み）。本計画書も通常の設計 docs として追跡対象になる（`git status` では `?? tasks/issue-16/`）。

## 4. タスク（各 2–5 分・TDD）

前提（セッション最初に 1 回だけ）:
```bash
cd /home/nabu_dvl/workspace/the-calendar-to-timeline/light_token_server
source .venv/bin/activate
```

### Task 1: 失敗するテストに更新する（open/waiting・RED）

**Objective:** `summary` を含まない 9+1 キーを期待するテストに書き換え、現状実装で落ちることを確認する。

**Files:** Modify `tests/test_milestone.py:766-792`

**Step 1:** 期待集合から `"summary"` を削除し、`summary="sum"` で作成したイベントが除外されることを明示検証。

```python
    assert set(event.keys()) == {
        "id", "staff_id", "group", "group_name", "start",
        "end", "title", "progress", "milestone_id", "completed",
    }
    # Issue #16 [中-1]: summary は非 admin に露出させない
    assert "summary" not in event
```

**Step 2:** 失敗を確認。

```bash
python -m pytest tests/test_milestone.py::test_milestone_events_response_keys_and_format -q
```
Expected: FAIL — `AssertionError`（`summary` が keys に残る / `"summary" not in event` が偽）。

### Task 2: `EventORM.to_milestone_dict()` を追加し、ルータを切り替える（GREEN）

**Objective:** ホワイトリスト 9 キーを返すシリアライザを追加し、`_get_milestone_events` から使う。

**Files:** Modify `app/models.py:105-126` / Modify `app/routers/timetable.py:308-316`

**Step 1:** `EventORM` クラス定義の直前に定数を置き、`to_dict()` 内のローカル変数 `f` を置き換える（DRY）。

```python
# イベント日時のシリアライズ形式（to_dict / to_milestone_dict で共有）
_EVENT_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.000Z"
```

**Step 2:** `EventORM` に公開キーとメソッドを追加（`to_dict()` の直後）。

```python
    # Issue #16 [中-1]: /milestone/*/events は非 admin も閲覧するため、
    # 表示に必要なキーのみをホワイトリストで公開する (summary は含めない)。
    MILESTONE_EVENT_KEYS = (
        "id", "staff_id", "group", "start", "end",
        "title", "progress", "milestone_id", "completed",
    )

    def to_milestone_dict(self):
        full = self.to_dict()
        return {key: full[key] for key in self.MILESTONE_EVENT_KEYS}
```

**Step 3:** `app/routers/timetable.py:308-316` を差し替える（この時点では 2 パスのまま・最小差分）。

```python
    events = db.query(EventORM).filter(EventORM.milestone_id == milestone_id).all()
    # N+1 対策: Team を一括取得 (spec §8 / PR #15 review 指摘 8)
    group_ids = {d["group"] for d in (ev.to_milestone_dict() for ev in events)}
    teams = (db.query(Team).filter(Team.CODE.in_(group_ids)).all()) if group_ids else []
    team_name_by_code = {t.CODE: t.SHORTNAME for t in teams}
    result = []
    for ev in events:
        d = ev.to_milestone_dict()
        d["group_name"] = team_name_by_code.get(d["group"])
        result.append(d)
    return result
```

**Step 4:** GREEN を確認。

```bash
python -m pytest tests/test_milestone.py -q
```
Expected: **46 passed**（既存の open/waiting/closed テストも緑のまま）。

### Task 3: `to_dict` 二重呼び出しを解消する（[低-6]・リファクタのみ）

**Objective:** 1 イベント 1 回の dict 生成にまとめる。挙動は変えない。

**Files:** Modify `app/routers/timetable.py:308-316`

**Step 1:** 生成済みリストを 1 度だけ作り、`group_ids` もそこから取る。

```python
    events = db.query(EventORM).filter(EventORM.milestone_id == milestone_id).all()
    # Issue #16 [低-6]: 1 イベントにつき dict 生成は 1 回だけ
    rows = [ev.to_milestone_dict() for ev in events]
    # N+1 対策: Team を一括取得 (spec §8 / PR #15 review 指摘 8)
    group_ids = {d["group"] for d in rows}
    teams = (db.query(Team).filter(Team.CODE.in_(group_ids)).all()) if group_ids else []
    team_name_by_code = {t.CODE: t.SHORTNAME for t in teams}
    for d in rows:
        d["group_name"] = team_name_by_code.get(d["group"])
    return rows
```

**Step 2:** マイルストーン経路から `to_dict(` が消えたことを確認。

```bash
grep -n "to_dict\|to_milestone_dict" app/routers/timetable.py
```
Expected: `_get_milestone_events` 内は `to_milestone_dict` のみ。`/event/*` `/group/all` は `to_dict` のまま。

**Step 3:** 回帰なしを確認（挙動不変の証明）→ Expected: 46 passed。

```bash
python -m pytest tests/test_milestone.py -q
```

### Task 4: open/waiting・closed 両経路と `/event/*` の回帰アサートを追加する

**Objective:** 要件 1（open/waiting での `summary` 非公開）は Task 1・Task 2 で担保済み。ここでは
同じ `_get_milestone_events` を通る **closed 経路でも summary が出ないこと**と、`to_dict()` を変更して
いないため **`/event/*` は従来どおり summary を返すこと**をテストで固定する。

**Files:** Modify `tests/test_milestone.py:205-237`（closed テスト末尾） / 同ファイル末尾に新規テスト

**Step 1:** closed テスト（`test_closed_milestone_events_returns_events_across_groups`）に 1 行追加。

```python
    # Issue #16: closed も同じ _get_milestone_events を通るため summary は返さない
    assert all("summary" not in event for event in events)
```

**Step 2:** ファイル末尾に `/event/all` の回帰テストを追加。

```python
# Issue #16: /event/* は従来どおり summary を返す（to_dict は変更しない）
def test_event_all_still_includes_summary(client):
    _add_event(client, summary="visible")

    events = client.get("/event/all", headers=_bearer(True)).json()

    assert len(events) == 1
    assert events[0]["summary"] == "visible"
```

**Step 3:** 実行 → Expected: **47 passed**。

```bash
python -m pytest tests/test_milestone.py -q
```

### Task 5: 全体検証と仕上げ

**Step 1:** 全体テスト → Expected: 全 passed（`test_milestone.py` は 47 passed）。

```bash
python -m pytest -q
```

**Step 2:** 無関係ファイルを巻き込んでいないか確認（特に `app/config.py` のローカル用 `APP_URL` 変更）。

```bash
git status --short
git diff --stat origin/main...HEAD
```

**Step 3:** 受け入れ条件の突き合わせ。
- [ ] `/milestone/{id}/events`・`/milestone/closed/{id}/events` に `summary` が無い
- [ ] `_get_milestone_events` で `to_dict()` を二重に呼んでいない
- [ ] `/event/all` `/event/user` `/group/all` は `summary` を返したまま
- [ ] `group_name` 付与と Team 一括取得（N+1 回避）が維持されている

## 5. リスク / 補足

- **フロントへの影響なし（実行時）**: 描画で `summary` 未使用。ただし `time-table-to-line` の
  `src/lib/TimelineType.ts` の `MilestoneEventProps.summary?` と `specs/2026-10-15-spec.md`
  §2-1 / §2-4 の記載は実態とずれる。**別リポジトリのため本 Issue のスコープ外**（必要なら
  フロント側で型から `summary?` 削除 + spec 更新を別途実施）。
- **互換性**: `summary` を参照する外部クライアントがあれば破壊的変更。リポジトリ内の参照は
  フロントの型定義のみであることを確認済み。
- **パフォーマンス**: `to_milestone_dict()` は `to_dict()` を 1 回呼んでキーを絞るだけ。追加クエリは
  無く、Team 一括取得も維持するため負荷増なし（dict 生成は半減）。
- **未決事項**: なし（closed も summary 非公開に揃える方針を採用。変更したい場合は Task 2 の時点で
  closed 用に `to_dict()` を使い分ける）。
