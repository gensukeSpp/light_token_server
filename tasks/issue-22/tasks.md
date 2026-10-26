# Issue-22 実装タスク（前半: テスト追加 → RED → 実装）

実装は下記を順に、各タスクで **TDD（失敗→実装→成功→Commit）** を回す。各タスクは 2–5 分規模。
後半（GREEN 確認・全回帰・記録）は `tasks2.md` を参照。

前提: 作業ディレクトリはプロジェクトルート `/home/nabu_dvl/workspace/the-calendar-to-timeline/light_token_server`。
`source .venv/bin/activate` を済ませてから `uv` 系コマンドを実行する（ユーザー指示。venv 未活性化での uv コマンドは禁止）。
テストは SQLite インメモリ（実 DB 不要）。DB マイグレーションは本 Issue には無い。

実装前に `tasks/issue-22/overview.md` の「判断ポイント」を確認する（**特に 4: admin は他人名義作成を許可のまま
= `_add_event_staff` が壊れないこと**。既定値がそのまま確定で進めて差し支えないレベル）。

**着手順・依存**

```
tasks.md: Task1(ベースライン+テスト) → Task2(RED) → Task3(実装)
    → tasks2.md: Task4(GREEN) → Task5(全回帰) → Task6(記録)
```

- Task 1 のテストは Task 2〜4 の土台。Task 3 の実装は Task 2 の RED が確認できてから（TDD 順守）。
- Task 5 は milestone を先に回す（`/event/add` を経由するヘルパーがあるため、timetable 単体より先に影響を確認）。
- Task 6 は任意だが、issue-20 の実績（spec 差分配録あり）に倣い推奨。

---

### Task 1: ベースライン確認 + 失敗テスト追加

**Objective:** 現状がグリーンであることを確認し、Issue #22 の受け入れ条件をテストで固定する（RED の準備）。

**Files:**
- Modify: `tests/test_timetable.py`（末尾に Issue #22 セクション追加）

**Step 1: ベースライン確認**

```bash
source .venv/bin/activate
uv run pytest -q
```

Expected: 全 PASS（PR #21 レビュー時点で 87 passed。数は環境で前後してよいが FAIL 0 であること）

**Step 2: 失敗テストを追加する**

`tests/test_timetable.py` の末尾（`test_date_update_admin_can_move_others_event` の後）に追加:

```python
# ===== Issue #22: /event/add の staff_id 検証（本人 or admin）=====

def _create_event_body(staff_id: int) -> dict:
    return {
        "staff_id": staff_id,
        "group": 3,
        "start_time": "2026-08-02T10:00:00.000Z",
        "end_time": "2026-08-02T11:00:00.000Z",
        "title": "new event",
    }


def test_event_add_self_non_admin_allowed(client):
    # 受入 1: 非 admin は自分の staff_id で作成できる。
    me = tokens.create_access_token(1002, 3, False)
    r = client.post(
        "/event/add", json=_create_event_body(1002), headers=_bearer(me),
        follow_redirects=False,
    )
    assert r.status_code == 201
    assert r.json()["staff_id"] == 1002


def test_event_add_other_member_forbidden_for_non_admin(client):
    # 受入 2: 非 admin が他人の staff_id を指定すると 403 となり、イベントは作成されない。
    me = tokens.create_access_token(1002, 3, False)
    before = client.get("/event/all", headers=_bearer(me), follow_redirects=False).json()
    r = client.post(
        "/event/add", json=_create_event_body(1001), headers=_bearer(me),
        follow_redirects=False,
    )
    assert r.status_code == 403
    # 一覧に混入していないこと（conftest の事前投入 1 件のまま）
    after = client.get("/event/all", headers=_bearer(me), follow_redirects=False).json()
    assert len(after) == len(before) == 1
    assert all(e["staff_id"] == 1001 for e in after)  # 1002 名義のイベントが増えていない


def test_event_add_admin_can_create_for_others(client):
    # 受入 3: admin は他人の staff_id でも作成できる。
    admin = tokens.create_access_token(1001, 3, True)
    r = client.post(
        "/event/add", json=_create_event_body(1002), headers=_bearer(admin),
        follow_redirects=False,
    )
    assert r.status_code == 201
    assert r.json()["staff_id"] == 1002


def test_event_add_nonexistent_staff_forbidden_for_non_admin(client):
    # エッジ: 非 admin が存在しない staff_id を指定しても 403（claims との不一致として拒否）。
    me = tokens.create_access_token(1002, 3, False)
    r = client.post(
        "/event/add", json=_create_event_body(9999), headers=_bearer(me),
        follow_redirects=False,
    )
    assert r.status_code == 403
```

> 注意: `test_timetable.py` には既に `_bearer(token: str) -> dict`（154 行目）がある。`tokens` は
> ファイル冒頭で import 済み（3 行目）。**`_bearer` / `tokens` の再定義や重複 import を追加しないこと**。

**Step 3: Commit（テストのみ）**

```bash
git add tests/test_timetable.py
git commit -m "test: issue-22 /event/add の staff_id 照合テストを追加 (RED)"
```

---

### Task 2: 失敗確認（RED）

**Objective:** 新規テストが現実装で失敗することを確認し、テストが受け入れ条件を正しく固定していると確かめる。

**Step 1: 新規テストのみ実行**

```bash
uv run pytest tests/test_timetable.py -k "event_add" -v
```

Expected: FAIL（`test_event_add_other_member_forbidden_for_non_admin` が 403 を期待して 201 を受ける、
`test_event_add_nonexistent_staff_forbidden_for_non_admin` も同様。他人・存在しない ID が現状では作成できてしまう）
※ `test_event_add_self_non_admin_allowed` / `test_event_add_admin_can_create_for_others` は既に通る（現状の挙動が許可のため）

**Step 2: 全テストへの影響を確認（現時点では変更なしのはず）**

```bash
uv run pytest -q
```

Expected: 新規 4 件のうち 2 件のみ FAIL、それ以外は PASS（他には影響なし）

---

### Task 3: ヘルパー実装 + `append_event_item` へ適用

**Objective:** 作成時チェックを実装し、非 admin の他人名義・不明 ID を 403 で拒否する。

**Files:**
- Modify: `app/routers/timetable.py`（`append_event_item` の直前、約 171 行目付近）

**Step 1: ヘルパー関数を追加**（`architecture.md` 3 節の完全形。`append_event_item` の定義の直前に置く）

```python
def _require_event_create_owner_or_admin(staff_id: int, claims: dict) -> None:
    """/event/add の staff_id を認証ユーザーと照合する (Issue #22)。

    非 admin は本人の staff_id のみ許可。admin は他人名義の作成を許可する。
    更新・削除用の _require_event_owner_or_admin は event オブジェクト基準なので、
    作成時は body の素の staff_id を受ける本関数を使う。
    claims は require_token 由来で、user_id / admin キーが常に存在する。
    """
    if staff_id == claims.get("user_id"):
        return
    if claims.get("admin"):
        return
    raise HTTPException(
        status_code=403,
        detail="not allowed to create event for other member",
    )
```

**Step 2: `append_event_item` の冒頭**（`event = EventORM(...)` の前）に 1 行追加

```python
    _require_event_create_owner_or_admin(body.staff_id, claims)
```

※ `HTTPException` は既に import 済み。新規 import・schema 変更・モデル変更は不要。

**Step 3: 差分確認**

```bash
git diff app/routers/timetable.py
```

Expected: 追加 15 行程度のみ（ヘルパー関数 + 呼び出し 1 行）

---

## 実装時の留意（共通・tasks2.md でも同じ）

- `uv` コマンド前は必ず `source .venv/bin/activate`（ユーザー指示）。
- `test_timetable.py` の `_bearer(token: str)` と `tokens` import は既存のものを再利用（再定義禁止）。
- 判定は必ず `db.add` より前。403 で DB に何も書かないこと。
- admin の他人名義作成は**許可のまま**（issue-20 の `_add_event_staff` が 201 を期待して依存している）。
- `_require_event_owner_or_admin`（更新・削除用）と `/date/update` / `/milestone/*` の契約は変えない。
- 新規 import（`HTTPException` 等）は不要。`app/schemas.py` / `app/models.py` は変更しない。
- 未追跡ファイル `pick_1020` は本 Issue と無関係。触らず、`git add .` / `git add -A` は使わない
  （対象ファイルを明示して add すること）。
