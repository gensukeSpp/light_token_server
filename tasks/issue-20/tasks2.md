# Issue #20 実装タスク（2/2：Task 4–6）— 削除 GREEN・/date/update 統一・検証

> 前提（venv 起動）と Task 1–3 は同じディレクトリの `tasks.md` を参照。
> 共通ヘルパー `_require_event_owner_or_admin` は Task 2 で追加済み。

---

### Task 4: `remove_event_item` へ適用（GREEN）

**Objective:** Task 3 をグリーン化する（404 チェック直後にヘルパー呼び出し）。

**Files:** Modify `app/routers/timetable.py:252-254`

**Step 1:** `remove_event_item` の 404 チェック直後に呼び出しを追加。

```python
    _require_event_owner_or_admin(target, claims)
```

**Step 2:** 確認。

```bash
python -m pytest tests/test_timetable.py::test_event_remove_other_members_event_forbidden -q
python -m pytest tests/test_timetable.py::test_event_remove_owner_non_admin_allowed -q
python -m pytest tests/test_timetable.py::test_event_remove_admin_can_remove_others -q
python -m pytest tests/test_timetable.py::test_event_remove -q
```
Expected: 4 つとも PASS（既存 `test_event_remove` も本人&admin なので PASS のまま）。

---

### Task 5: `update_event_dates` に admin 例外を追加する（RED→GREEN）

**Objective:** ユーザー要件「admin は例外」に合わせ、`/date/update` の所有者チェックを「本人 or admin」に統一する（3 エンドポイントで同一ポリシー）。

**Files:** Modify `tests/test_timetable.py` / Modify `app/routers/timetable.py:234-238`

**Step 1:** テストを追加（非 admin・他人 → 403 の維持、admin・他人 → 200）。

```python
def test_date_update_other_members_event_forbidden(client):
    other = tokens.create_access_token(9999, 3, False)
    r = client.post(
        "/date/update",
        headers=_bearer(other),
        json={"data": [{"id": 1, "start_time": "x", "end_time": "y"}]},
        follow_redirects=False,
    )
    assert r.status_code == 403


def test_date_update_admin_can_move_others_event(client):
    admin = tokens.create_access_token(1001, 3, True)
    event_id = _add_event_staff(client, admin, 9999)

    r = client.post(
        "/date/update",
        headers=_bearer(admin),
        json={
            "data": [
                {
                    "id": event_id,
                    "start_time": "2026-08-02T14:00:00.000Z",
                    "end_time": "2026-08-02T15:00:00.000Z",
                }
            ]
        },
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert r.json()[0]["id"] == event_id
```

**Step 2:** RED 確認（admin 例外が無いため 2 つ目が 403 で失敗）。

```bash
python -m pytest tests/test_timetable.py::test_date_update_admin_can_move_others_event -q
```
Expected: FAIL。

**Step 3:** `update_event_dates` の `if target.staff_id != ...`（`app/routers/timetable.py:234-238`）をヘルパー呼び出しに置き換える。

```python
        _require_event_owner_or_admin(target, claims)
```

**Step 4:** GREEN 確認。

```bash
python -m pytest tests/test_timetable.py::test_date_update -q
python -m pytest tests/test_timetable.py::test_date_update_other_members_event_forbidden -q
python -m pytest tests/test_timetable.py::test_date_update_admin_can_move_others_event -q
```
Expected: 全て PASS（既存 `test_date_update_*` は本人&admin のため影響なし）。

---

### Task 6: 全体検証と仕上げ

**Objective:** 全テスト・影響範囲・受け入れ条件を確認する。

**Step 1:** 全体テスト → Expected: **87 passed**（79 + 新規 8）のグリーン。

```bash
python -m pytest -q
```

**Step 2:** 無関係ファイルを巻き込んでいないか確認。

```bash
git status --short
git diff --stat origin/main...HEAD
```

**Step 3:** 受け入れ条件の突き合わせ。
- [ ] `/event/update/{id}` — 他人を非 admin が更新 → 403 / 本人（非 admin）→ 200 / admin が他人 → 200
- [ ] `/event/remove/{id}` — 他人を非 admin が削除 → 403（イベントは残存）/ 本人（非 admin）→ 200 / admin が他人 → 200
- [ ] `/date/update` — 他人を非 admin → 403 / admin が他人 → 200（3 端末で「本人 or admin」に統一）
- [ ] 存在しないイベントは従来どおり 404
- [ ] 3 箇所の判定が共通ヘルパー `_require_event_owner_or_admin` に集約されている（DRY）