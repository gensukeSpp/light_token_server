# Issue-9 実装タスク

実装は下記を順に、各タスクで **TDD(失敗→実装→成功→Commit)** を回す。各タスクは 2–5 分規模。

前提: 作業ディレクトリはプロジェクトルート `/home/nabu_dvl/workspace/the-calendar-to-timeline/light_token_server`。`source .venv/bin/activate` を済ませてから `uv` 系コマンドを実行する。テストは SQLite インメモリ(実 DB 不要)。

まず実装前に、`tasks/issue-9/overview.md` の「判断ポイント」を利用者へ確認する(**特に 1: status 遷移と re-open のトリガー、3/4: 子 completed の扱い**)。

---

### Task 1: 設計確定(判断ポイントの利用者確認)

**Objective:** status 遷移・編集の部分 update・completed の扱い・カラム名のリネーム方針を確定する。

**Files:** なし(ドキュメントのみ `tasks/issue-9/overview.md` と本ファイル)

**Step 1:** 利用者へ確認:
1. **closed は本 Issue で生成しない**(open / waiting のみ)でよいか → 既存テストの close 期待を waiting 期待へ書き換える。
2. **update は全部 optional の部分更新**(title のみ編集可能)でよいか。
3. **waiting 遷移時(accomplished_date 設定)に子イベント `completed=True` にするか**(現行 close 相当の挙動維持)を決める。
4. **waiting → open(再 open)のトリガー**: `"accomplished_date": null` を明示で re-open(Option A)が良いか。
5. **`guidline_end_date` → `guideline_end_date` の DB カラム名リネーム**方針でよいか(実行は利用者本人)。

**Step 2:** 確定した値を本 overview.md / architecture.md / 以降のタスクへ反映する。

---

### Task 2: スペル修正 `guidline` → `guideline`(+ Alembic リビジョン)

**Objective:** 全所の誤スペルを `guideline_end_date` へ統一し、DB マイグレーション差分を用意する(実行は利用者)。

**Files:**
- Modify: `app/models.py`(Column + to_dict)
- Modify: `app/schemas.py`(`MilestoneCreate`)
- Modify: `app/routers/timetable.py`(`/milestone/add` の body 参照)
- New: `migrations/versions/<rev>_rename_guidline.guideline.py`

**Step 1: 置換(grep で全件特定)**
```bash
grep -rn "guidline" app/ || echo "none"
grep -rn "guidline" tests/ || echo "none"
```
**Step 2: `app/models.py`** の `guidline_end_date` → `guideline_end_date`(Column 名と to_dict key)。**SQLite テストではカラム名変更の影響が tidy**(テーブルは新規作成に再定義されるため)。**本番 PostgreSQL は他カラム名のため Migration が必要**(Step 6)。

**Step 3: `app/schemas.py`** `MilestoneCreate.guidline_end_date` → `guideline_end_date`。

**Step 4: `app/routers/timetable.py`** `/milestone/add` で `body.guideline_end_date` に変更。

**Step 5: 全テストで後続契約の移動前に回帰確認**(下記 Task 5 で書き換える。ここでは既存 test_milestone の spell 依存のみ確認でよいが、close 期待テストは変化しないため通るはず)。
```bash
uv run pytest tests/test_milestone.py -v
```
(もしテストが `guidline` key を参照していれば、テスト側を `guideline` に直す)

**Step 6: Alembic リビジョン生成**
```bash
alembic revision --autogenerate -m "rename guidline_end_date to guideline_end_date"
```
生成されたリビジョン内で `op.alter_column("M_MILESTONE", "guidline_end_date", new_column_name="guideline_end_date")` になっていることを確認。**実行(upgrade)は利用者本人**(AGENTS.md Pitfalls: DB マイグレーション実行はユーザー)。コミットメッセージに「リビジョン作成のみ・実行は利用者」と明記。

**Step 7: Commit**
```bash
git add app/models.py app/schemas.py app/routers/timetable.py migrations/
git commit -m "refactor: guidline_end_date を guideline_end_date に統一 (DB リネームは利用者実行)"
```

---

### Task 3: `MilestoneUpdate` schema 拡張 + `/milestone/update/{id}` の編集&waiting 遷移

**Objective:** update を部分更新(タイトル等編集可)にし、accomplished_date 設定時 status を waiting へ遷移、re-open 対応。

**Files:**
- Modify: `app/schemas.py`(`MilestoneUpdate` 拡張)
- Modify: `app/routers/timetable.py`(`close_milestone`)
- Test: `tests/test_milestone.py`(編集・waiting・re-open)

**Step 1: 失敗テストを書く**(判断 3/4 確定値に合わせる。ここでは「waiting で子 completed=True 維持」「null で re-open(open)」の既定を踏まえる)

```python
# tests/test_milestone.py に追加
def test_milestone_update_edits_title_only(client):
    ms = _add(client, "M1")
    ms_id = ms.json()["id"]
    r = client.post(f"/milestone/update/{ms_id}", json={"title": "renamed"},
                    headers=_bearer(True))
    assert r.status_code == 200
    assert r.json()["title"] == "renamed"
    assert r.json()["status"] == "open"   # accomplished_date 未指定なので状態変化なし

def test_milestone_update_accomplished_sets_waiting(client):
    ms = _add(client, "M1")
    ms_id = ms.json()["id"]
    r = client.post(f"/milestone/update/{ms_id}",
                    json={"accomplished_date": "2026-08-20"}, headers=_bearer(True))
    assert r.status_code == 200
    assert r.json()["status"] == "waiting"   # closed ではなく waiting

def test_milestone_reopen_from_waiting(client):
    ms = _add(client, "M1")
    ms_id = ms.json()["id"]
    client.post(f"/milestone/update/{ms_id}", json={"accomplished_date": "2026-08-20"},
                headers=_bearer(True))
    r = client.post(f"/milestone/update/{ms_id}", json={"accomplished_date": None},
                    headers=_bearer(True))
    assert r.status_code == 200
    assert r.json()["status"] == "open"
    assert r.json()["accomplished_date"] is None

def test_milestone_reclose_returns_409(client):
    # closed 状態自体は Task2 終了まで生成しない。closed になった後の再入力は 409 を期待。
    # ここでは「waiting から再度 accomplished_date 指定」は同一 waiting のまま(409 でない)を検証
    ...
```
> 注意: Task 2 まで closed は生成しないため、既存の `test_milestone_reclose_returns_409` と `test_milestone_close_sets_completed` は**書き換える**(closed 期待→waiting 期待に実装合わせ)。

**Step 2: 失敗確認**
```bash
uv run pytest tests/test_milestone.py -v
```
Expected: FAIL(新規テストが失敗、あるいは既存の closed 期待が新実装で壊れる)

**Step 3: schema 拡張とルーティング実装**

`app/schemas.py`:
```python
class MilestoneUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    guideline_end_date: date | None = None
    accomplished_date: date | None = None
```

`app/routers/timetable.py` `close_milestone`(要は renamed to `update_milestone`):
```python
@router.post("/milestone/update/{milestone_id}")
def update_milestone(milestone_id: int, body: MilestoneUpdate,
                     claims: dict = Depends(require_token), db: Session = Depends(get_db)):
    if not claims.get("admin"):
        raise HTTPException(status_code=403, detail="admin only")
    target = db.query(MilestoneORM).filter(MilestoneORM.id == milestone_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="milestone not found")

    # 編集(部分 update)
    if body.title is not None: target.title = body.title
    if body.description is not None: target.description = body.description
    if body.guideline_end_date is not None: target.guideline_end_date = body.guideline_end_date

    # accomplished_date の扱い(model_fields_set で「送られたか」を判別)
    fields = body.model_fields_set
    if "accomplished_date" in fields:
        if body.accomplished_date is not None:
            if target.status == MILESTONE_CLOSED:
                raise HTTPException(status_code=409, detail="already closed")
            target.accomplished_date = body.accomplished_date
            if target.status != MILESTONE_WAITING:
                target.status = MILESTONE_WAITING
            # 子イベント completed=True(判断 3: 「waiting で完了」が確定した場合)
            for ev in db.query(EventORM).filter(EventORM.milestone_id == milestone_id).all():
                ev.completed = True
        else:
            # re-open
            if target.status == MILESTONE_WAITING:
                target.status = MILESTONE_OPEN
                target.accomplished_date = None
                # (判断 4: re-open 時に completed を戻す場合は False へ)
            # else: closed への re-open は 409(判断 4 が閉を許容しない場合)
    db.commit()
    db.refresh(target)
    return target.to_dict()
```
> `model_fields_set` で「accomplished_date が送られたか(値が None でも)」が分かる。re-open は Option A(`null` 明示)を既定想定。

**Step 4: 成功確認**
```bash
uv run pytest tests/test_milestone.py -v
```
Expected: PASS(新しく入れた waiting / re-open / 編集テスト)

さらに既存の closed 期待テストは新契約に合わせて書き直す(テストに closed 期待が残っていれば fail)。

**Step 5: Commit**
```bash
git add app/schemas.py app/routers/timetable.py tests/test_milestone.py
git commit -m "feat: /milestone/update を編集対応&accomplished_date で status waiting 遷移 (re-open 対応)"
```

---

### Task 4: `/milestone/all` を open + waiting に変更

**Objective:** 一覧が `status != 'closed'` を返すよう変更。受け入れ 2(猶予中一覧表示)を成立させる。

**Files:**
- Modify: `app/routers/timetable.py`(`get_open_milestones`)
- Test: `tests/test_milestone.py`

**Step 1: 失敗テスト**
```python
def test_milestone_all_includes_waiting(client):
    ms = _add(client, "M1"); ms_id = ms.json()["id"]
    client.post(f"/milestone/update/{ms_id}", json={"accomplished_date": "2026-08-20"},
                headers=_bearer(True))
    rows = client.get("/milestone/all", headers=_bearer(True)).json()
    assert len(rows) == 1
    assert rows[0]["status"] == "waiting"
```
(既存 `test_milestone_all_returns_open_only` は「close 後は一覧から消える」を「re-open 以外 status 遷移」に合わせて書き換える)

**Step 2: 失敗確認**
```bash
uv run pytest tests/test_milestone.py -k "all" -v
```

**Step 3: 実装**
```python
@router.get("/milestone/all")
def get_open_milestones(claims=Depends(require_token), db=Depends(get_db)):
    rows = db.query(MilestoneORM).filter(MilestoneORM.status != MILESTONE_CLOSED).all()
    return [m.to_dict() for m in rows]
```

**Step 4: 成功確認**
```bash
uv run pytest tests/test_milestone.py -k "all" -v
```

**Step 5: Commit**
```bash
git add app/routers/timetable.py tests/test_milestone.py
git commit -m "feat: /milestone/all を open + waiting 一覧に変更 (status != closed)"
```

---

### Task 5: 全テスト整備・回帰確認

**Objective:** 既存 `tests/test_milestone.py` の closed 期待を新契約へ揃え、全体をグリーンにする。

**Step 1: 旧 close テストの置換**
- `test_milestone_all_returns_open_only`: 「update で waiting になり、一部候補から消える」を確認し、closed 参照を外す。
- `test_milestone_close_sets_completed`: waiting 遷移 + 子 completed=True の期待へ直す。
- `test_milestone_reclose_returns_409`: closed データを明示作って 409 を検証するか、または「waiting の返却が 409 でないこと」に置き換える。

**Step 2: 全体実行**
```bash
uv run pytest -v
```
Expected: 全 PASS(既存 health / login / tokens / timetable / milestone)

**Step 3: smoke**
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000   # 起動確認 → /health
```

**Step 4: Commit**
```bash
git add tests/
git commit -m "test: issue-9 契約(waiting・編集・re-open・all)にテストを揃える"
```

---

## 着手順・依存

```
Task1(設計確定) → Task2(スペル修正+リビジョン) → Task3(update 編集+waiting)
    → Task4(/milestone/all) → Task5(回帰・全体グリーン)
```
- Task1 は最初(利用者確認)。Task2 はモデル変更で後続が依存。
- Task3 → Task4 の順で update / all を実装。Task5 で全体グリーン。

## 実装時の留意(共通)

- `uv` コマンド前は必ず `source .venv/bin/activate`(ユーザー指示)。
- DB アクセスは必ず `db: Session = Depends(get_db)`。
- `raise RedirectResponse` は使わず、Starlette 1.4 に従う。
- **既存の /milestone/remove と /milestone/add の契約は変えない**(今回の差分は update / all のみ)。
- `model_fields_set` で「accomplished_date が送られたかどうか」を判定(部分 update と re-open を区別)。
- スペル修正対象は model / schema / router / 必要なら test。migration リビジョンの実行は利用者。