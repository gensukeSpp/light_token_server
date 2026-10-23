# Issue-22 実装計画 — `/event/add` の staff_id を認証ユーザーと照合する

> **For Hermes:** 実装は TDD（失敗→実装→成功→Commit）でタスク単位に進める。実装前に本ファイル群と
> `.github/reports/pr-21-review.md` 指摘事項 1、`tasks/issue-20/` の既存所有者チェック実装を読むこと。
> 既存の `_require_event_owner_or_admin`（更新・削除用）と `/event/add` の成功パスは壊さないこと。

**Goal:** `POST /event/add`（`append_event_item`）がリクエスト body の `staff_id` を認証 claims と照合する。
非 admin が他人の `staff_id` を指定したリクエストは **403 で拒否**し、admin は他人名義の作成を許可する。
これにより Issue #20 で導入した所有者ベースの更新・削除チェック（`_require_event_owner_or_admin`）の前提
「作成者 = staff_id」が崩れる穴を塞ぐ。

**Architecture:** 既存の更新・削除チェックと同じ「本人 or admin」ポリシーを、作成時に適用する。
`append_event_item` の冒頭（`db.add` より前）で `claims["user_id"]` と `body.staff_id` を照合する
モジュール内プライベートヘルパー `_require_event_create_owner_or_admin(staff_id, claims)` を追加し、
判定不一致かつ非 admin なら `HTTPException(403)` を raise する。DB 書き込みは発生しない。
`/event/add` の成功パス・レスポンス形式（201 + `to_dict()`）は変えない。フロント・認証契約の変更なし。

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Pydantic, pytest + httpx（SQLite in-memory StaticPool + get_db override）, uv

---

## この段階で完成するもの（成果物）

- `app/routers/timetable.py` に `_require_event_create_owner_or_admin(staff_id, claims)` を追加
- `append_event_item` 冒頭で上記ヘルパーを呼び、非 admin・不一致なら **403** で拒否（DB へ何も書かない）
- `tests/test_timetable.py` に Issue #22 セクションを追加（受入条件 3 つ + エッジ 1 つ）
- 全テスト（既存 87 passed 相当 + 新規 4）が SQLite で自動的に通る

## スコープ外（今回はやらない）

- `/event/update` `/event/remove` `/date/update` の既存チェック変更（Issue #20 済・不変）
- `staff_id` が存在するユーザーかどうかの検証（admin が存在しない ID で作成 → 従来どおり 201。今回対象外）
- `EventCreate` schema の変更（`staff_id` フィールド自体は必須のまま）
- フロントエンド（time-table-to-line）側の変更（API 直叩きの保険であり UI 変更不要）
- `app/tokens.py` の残存 `print(...)` 削除（別タスク）

## 現在のコンテキスト / 前提（読み取ったコード）

- `append_event_item` — `app/routers/timetable.py:170-190`
  `body: EventCreate` を受けて `body.staff_id` を無検証で `EventORM(staff_id=body.staff_id, ...)` に採用し
  `db.add → db.commit → db.refresh → to_dict()`、`status_code=201`。認可は `Depends(require_token)` のみ。
- `_require_event_owner_or_admin(target, claims)` — `app/routers/timetable.py:193-205`（Issue #20 で追加）
  `target.staff_id == claims["user_id"]` または `claims["admin"]` 以外を 403 にする。
  引数は **event オブジェクト基準**のため、body の `staff_id` を渡す作成時チェックにはそのまま使えない
  （別ヘルパーが必要。理由は architecture.md に記載）。
- claims の形状 — `app/tokens.py:29-33` で `create_access_token` が
  `{"user_id", "group_id", "admin", "type"}`
  を発行。`require_token`（`tokens.py:113-119`）は DB にユーザーが存在することを確認して claims を返すため、
  `claims.get("user_id")` / `claims.get("admin")` は常に存在する。
- `EventCreate` — `app/schemas.py:12-21`。`staff_id: int`（必須）。Pydantic バリデーションで int 以外は
  422（従来どおり、今回変更なし）。
- conftest — `tests/conftest.py:29-39`。`User(1001) + StaffLogin(1001, "secret", True)`（admin）、
  `User(1002) + StaffLogin(1002, "secret", False)`（非 admin）。イベント 1 件（staff_id=1001）事前投入。
- テストパターン — `tests/test_timetable.py:231-360` の Issue #20 セクションで
  `tokens.create_access_token(user_id, group_id, admin)` による **Bearer 直接生成**方式が確立済み。
  `tests/test_milestone.py:22-24` の `_bearer(admin=True)` は user 1001 固定。
- 既存テストの `/event/add` 呼び出し:
  - `test_timetable.py:73 test_event_add` — 1001（admin=True）が staff_id=1001 で作成 → **201 のまま通る**
  - `test_timetable.py:233 _add_event_staff` — admin が任意 staff_id で作成 → **201 のまま通る**
    （= admin 他人名義作成の受け入れ条件と一致。既存ヘルパーとして再利用可能）
  - `test_milestone.py:31-42 _add_event` — `_bearer(True)`（1001, admin）で staff_id=1001 → **201 のまま通る**
  - 非 admin で `/event/add` を呼ぶ既存テストは無い → 挙動変更の影響は新規テストのみ
- ベースライン: PR #21 レビュー記録（`.github/reports/pr-21-review.md:24`）で **87 passed**。
  作業開始時に `uv run pytest -q` で再確認する（Task 1）。
- 作業ブランチ: `feature/event-add-verify/22`（issue-22 用）。未追跡ファイル `pick_1020` あり
  （本 Issue とは無関係、触らない）。

## 判断ポイント（実装前に利用者へ確認、既定値つき）

1. **403 の detail 文言**（小さな決定）: 既定 `"not allowed to create event for other member"`。
   既存テストは文言を固定しておらず、フロントも 403 のステータスのみ扱う想定のため安全。
   (`_require_event_owner_or_admin` の文言とは別にする: 更新/削除と作成で意味が異なるため)
2. **テストの配置**（小さな決定）: 既定 `tests/test_timetable.py` の末尾に Issue #22 セクションを追加。
   新規テストファイルは作らない（issue-20 と同じ流儀）。
3. **ヘルパーの形状**: 既定では既存 `_require_event_owner_or_admin` とは**別関数**として追加する。
   既存関数は event オブジェクト基準（`target.staff_id`）、新規は素の `staff_id: int` 基準で、引数型が異なるため
   統合すると呼び出し側で `event_to_create.staff_id` のような変な中間表現が要る。可読性優先で別関数とする。
4. **admin の他人名義作成**: issue 記載どおり **許可**（既定・確定）。`_add_event_staff` が既にこの前提で動いており、
   これを拒否すると issue-20 の全テストが壊れるため、必ず許可のまま実装する。
5. **エッジ: 非 admin が存在しない staff_id（例: 9999）**: 他人名義と同じ扱いで **403**（既定）。
   claims との不一致判定だけで自然に決まる。admin の場合は 201 のまま（スコープ外）。

## ディレクトリ構成（実装後）

```
app/
  routers/
    timetable.py   # 変更: _require_event_create_owner_or_admin 追加 + append_event_item 冒頭で呼び出し
  schemas.py       # 変更なし
tests/
  test_timetable.py  # 変更: 末尾に Issue #22 セクション（新規テスト 4 件）を追加
specs/
  <date>-event-add-staff-owner-spec.md  # 新規(任意): 差分記録（実装後に作成。spec-change-records 参照）
```

## 着手順・依存

```
Task1(ベースライン+失敗テスト) → Task2(RED 確認) → Task3(ヘルパー実装+適用) → Task4(GREEN 確認)
    → Task5(全回帰: timetable + milestone + 全体) → Task6(差分記録 + commit)
```

- Task 1〜2 でテストファースト。Task 3 の実装は 1 関数追加 + 1 行呼び出しの最小差分。
- Task 5 で `test_timetable.py` / `test_milestone.py` / 全体を回帰し、`_add_event_staff` や
  milestone 経由の `/event/add` が壊れないことを確認。
- Task 6 の commit は推奨（ブランチ `feature/event-add-verify/22` で PR を出す想定）。
  issue-20 の取り決めどおり「コミットは必須作業としない」扱いでも可。
