# マイルストーン所属イベント API 改訂仕様 — `summary` 非公開化 / `to_dict` 二重呼び出し解消（Issue #16）

> 対象差分: ブランチ `fix/2points-from-front`（`origin/main` 起点）の作業ツリー
> **現行契約の正本は `2026-10-13-milestone-event-retrieval-spec.md` です。** 本ファイルは Issue #16 で発生した**変更内容（差分）の記録**であり、正本の代替ではない。エンドポイント・権限マトリクス・エラー境界の現在の定義は正本を参照してください。
> 変更の入力: フロントエンド PR #42 レビュー `.github/reports/pr-42-review.md` の [中-1]（非 admin に他グループのイベント `summary` まで露出する）と [低-6]（`_get_milestone_events` の `to_dict()` 二重呼び出し）。
> 関連: 正本 `specs/2026-10-13-...`, 差分記録 `specs/2026-10-15-...`, 実装計画 `tasks/issue-16/plan.md`

---

## 1. 変更の背景・動機

Issue #40 / PR #15 で open / waiting 用 `GET /milestone/{milestone_id}/events` を**非 admin にも開放**したが、レスポンスは `EventORM.to_dict()` をそのまま使っていた。`to_dict()` は `/event/*` `/group/all` 用の全キー（`summary` を含む）を返すため、**他グループのイベント概要文が非 admin に露出**していた。

| # | 指摘 | 内容 | 対応 |
|---|---|---|---|
| 1 | [中-1] | マイルストーンはグループ横断共有のため、open/waiting 一覧は非 admin も閲覧する。`summary` はイベント詳細の自由記述であり、他グループのメンバーに公開する契約になっていない | レスポンスを**ホワイトリスト方式**で 9 キーに固定（`summary` を含めない） |
| 2 | [低-6] | `_get_milestone_events` が 1 イベントにつき `to_dict()` を 2 回呼んでいた（`group_ids` 収集時と付与ループ時） | dict 生成を **1 イベント 1 回**に統一 |

ホワイトリスト方式を採用した理由: ブラックリスト（`pop("summary")`）は将来 `EventORM` にカラムが増えたとき、マイルストーン API 側で除外し忘れると漏えいが再発する。公開キーを列挙して固定すれば、新カラムは既定で非公開になる。

---

## 2. 変更サマリ（差分）

変更ファイルは 3 件（`+45 / -9`）。エンドポイント、権限マトリクス、エラー境界の**現行定義は正本 `2026-10-13-...` を参照**（本ファイルには記載しない）。レスポンスのキー集合のみ本 Issue で変更している（正本 §3 も同時に改訂）。

| ファイル | 変更 |
|---|---|
| `app/models.py` | `_EVENT_TIME_FORMAT` 定数化、`EventORM.MILESTONE_EVENT_KEYS` と `EventORM.to_milestone_dict()` を追加 |
| `app/routers/timetable.py` | `_get_milestone_events` を `to_milestone_dict()` + 1 パス生成に変更 |
| `tests/test_milestone.py` | 期待キーから `summary` 削除（open/waiting）、closed 経路の非含有アサート、`/event/all` の回帰テストを追加 |

### 2.1 ホワイトリスト シリアライザ（`app/models.py:94, 128-144`）

```python
# イベント日時のシリアライズ形式（to_dict / to_milestone_dict で共有）
_EVENT_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.000Z"


class EventORM(Base):
    ...
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

- **`to_dict()` は変更しない**（キー集合は従来どおり `summary` を含む）。`/event/all` `/event/user` `/group/all` の契約は不変。
- 日時フォーマットは定数 `_EVENT_TIME_FORMAT` を `to_dict()` と共有し、文字列リテラルの二重定義を避ける。
- `to_milestone_dict()` は `to_dict()` の結果からキーを絞るだけ。日時書式・値の変換ロジックは 1 箇所に保たれる。
- `group_name` はモデルでは付与しない（ルータ側の責務。Team 一括取得による N+1 回避を維持するため）。

### 2.2 `_get_milestone_events` の 1 パス化（`app/routers/timetable.py:297-318`）

```python
    events = db.query(EventORM).filter(EventORM.milestone_id == milestone_id).all()
    # Issue #16 [低-6]: 1 イベントにつき dict 生成は 1 回だけ
    rows = [ev.to_milestone_dict() for ev in events]
    # N+1 対策: イベント件数ぶん db.get(Team, ...) を発行しないよう、チームを一括取得して dict にまとめる
    group_ids = {d["group"] for d in rows}
    teams = (db.query(Team).filter(Team.CODE.in_(group_ids)).all()) if group_ids else []
    team_name_by_code = {t.CODE: t.SHORTNAME for t in teams}
    for d in rows:
        d["group_name"] = team_name_by_code.get(d["group"])
    return rows
```

- 変更前は `group_ids` 収集のために `(ev.to_dict() for ev in events)` を回し、続く付与ループで再び `ev.to_dict()` を呼んでいた（1 イベント 2 回）。変更後は生成済み `rows` を再利用する。
- クエリ発行回数は不変（イベント 1 回 + Team 1 回）。**dict 生成回数のみ半減**。
- `group_name` の値は `M_TEAM.SHORTNAME`、Team 未登録なら `null`（従来どおり）。
- この関数は open/waiting 用と closed 用の**共通経路**のため、`summary` 非公開は**両 API に適用**される。closed は admin 限定だが、契約を揃える方針を採った（変更したい場合は closed 側だけ `to_dict()` に戻す分岐が必要）。

---

## 3. レスポンス契約の変更

`GET /milestone/{milestone_id}/events`（open/waiting）と `GET /milestone/closed/{milestone_id}/events`（closed）の各要素は次の 10 キー（`group_name` を含む）となる。

| キー | 変更 | 内容 |
|---|---|---|
| `id` | 変更なし | イベント ID |
| `staff_id` | 変更なし | イベント作成者 ID |
| `group` | 変更なし | 所属グループ ID |
| `group_name` | 変更なし（Issue #40） | `Team.SHORTNAME`（未登録なら `null`） |
| `start` | 変更なし | 開始日時 (`YYYY-MM-DDTHH:mm:ss.000Z`) |
| `end` | 変更なし | 終了日時（同上） |
| `title` | 変更なし | イベントタイトル |
| ~~`summary`~~ | **削除（Issue #16）** | マイルストーン API では返さない |
| `progress` | 変更なし | 進捗 |
| `milestone_id` | 変更なし | 所属マイルストーン ID |
| `completed` | 変更なし | 完了状態 |

- キー集合は**完全一致**で検証している（追加キーも許容しない）。将来カラムを増やす場合は `MILESTONE_EVENT_KEYS` の更新とテストの同時更新が必要。
- `summary` が必要なクライアントは `/event/all` `/event/user` `/group/all`（`to_dict()` ベース）を利用する契約とする。

---

## 4. テスト変更（`tests/test_milestone.py`）

| テスト | 変更 |
|---|---|
| `test_milestone_events_response_keys_and_format` | 期待キー集合から `summary` を削除（11 → 10 キー）。加えて `summary="sum"` で作成したイベントに対し `assert "summary" not in event` を明示追加（open/waiting 経路の要件担保） |
| `test_closed_milestone_events_returns_events_across_groups` | 末尾に `assert all("summary" not in event for event in events)` を追加（closed 経路＝同じ共通関数の回帰固定） |
| `test_event_all_still_includes_summary`（新規） | `_add_event(client, summary="visible")` の後に `GET /event/all` を叩き、返却要素の `summary == "visible"` を検証（`to_dict()` を変えていないことの固定） |

> 補足: conftest はイベントを 1 件 seed するため、新規テストは「配列長 == 1」ではなく**作成したイベント ID で引き当てる**形にしている。

---

## 5. 影響範囲・非対象

- **フロントエンド（実行時）**: `time-table-to-line` の `MilestoneEventsDrawer` は `summary` を描画に使っていないため、動作変更なし。ただし `src/lib/TimelineType.ts` の `MilestoneEventProps.summary?` とフロント仕様書の記載は実態とずれる。**別リポジトリのため本 Issue のスコープ外**（必要なら型から `summary?` 削除 + 仕様更新をフロント側で別途実施）。
- **互換性**: `summary` を参照する外部クライアントがあれば破壊的変更。リポジトリ内の参照はフロントの型定義のみであることを確認済み。
- **DB スキーマ変更なし**: マイグレーション不要。`T_TIMELINE_EVENT.summary` カラムは存置（`/event/*` 用）。
- **既存契約への影響なし**: `/event/add|all|user`、`/group/all`、`/milestone/add|update|remove|all`、自動 close（Task-11）は不変。
- **パフォーマンス**: 追加クエリなし。Team 一括取得（N+1 回避）を維持し、dict 生成はイベントあたり 2 回 → 1 回に削減。

---

## 6. 検証

| コマンド | 結果 |
|---|---|
| `python -m pytest tests/test_milestone.py -q`（変更前 baseline） | 46 passed |
| 同（Task 1 直後・テストのみ更新） | 1 failed（`summary` 残存で RED を確認） |
| 同（実装後） | **47 passed** |
| `python -m pytest -q`（全体） | **74 passed** |
| `grep -n "to_dict\|to_milestone_dict" app/routers/timetable.py` | `_get_milestone_events` 内は `to_milestone_dict` のみ。`/event/*` `/group/all` は `to_dict` のまま |
| `git status --short` / `git diff --stat` | 変更は `app/models.py` / `app/routers/timetable.py` / `tests/test_milestone.py` の 3 件のみ（無関係ファイルの巻き込みなし） |

検証観点: 9+1 キーの完全一致、open/waiting と closed の両経路で `summary` 非含有、`/event/all` で `summary` 維持、`group_name` 付与と Team 一括取得の維持、既存 46 テストの回帰なし。

---

## 7. 未決事項

- なし（closed も `summary` 非公開に揃える方針を採用）。
- フロント側の型定義（`MilestoneEventProps.summary?`）とフロント仕様書の追随は別 Issue 扱い。
