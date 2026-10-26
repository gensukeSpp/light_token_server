# Issue-22 実装タスク（後半: GREEN 確認 → 全回帰 → 記録）

前提・共通の実装時の留意は **`tasks.md` 冒頭**を参照（`.venv/bin/activate` 必須・`pick_1020` に触れない 等）。
本ファイルは `tasks.md` の Task 3（実装）が完了した後の続き。

---

### Task 4: 成功確認（GREEN）

**Objective:** 新規テストが全て通ることを確認する。

**Step 1: 新規テスト実行**

```bash
uv run pytest tests/test_timetable.py -k "event_add" -v
```

Expected: PASS（4 件全て。`test_event_add` 既存分を含む）

**Step 2: Issue #22 セクション全体**

```bash
uv run pytest tests/test_timetable.py -v
```

Expected: 全 PASS（issue-20 の所有者チェック 7 件 + 従来 14 件 + 新規 4 件等、既存の挙動が変わっていないこと）

**Step 3: Commit**

```bash
git add app/routers/timetable.py tests/test_timetable.py
git commit -m "fix #22: /event/add の staff_id を認証ユーザーと照合 (admin は例外)"
```

---

### Task 5: 全回帰確認

**Objective:** milestone 経由の `/event/add`（admin）を含め、全体がグリーンであることを確認する。

**Step 1: milestone テストを回帰**（`_add_event` ヘルパーが admin で staff_id=1001 を送る経路）

```bash
uv run pytest tests/test_milestone.py -v
```

Expected: 全 PASS（既存 60 件強。`_add_event` = admin 許可なので無影響のはず）

**Step 2: 全体実行**

```bash
uv run pytest -q
```

Expected: 全 PASS（87 passed + 新規 4 = 91 passed 相当、FAIL 0）

**Step 3: smoke（サーバー起動確認・任意）**

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000  # 起動後 Ctrl+C
```

Expected: 起動ログにエラーなし（`/health` 確認は任意）

---

### Task 6: 差分記録 + 最終確認

**Objective:** 実装結果を仕様差分として記録し、受け入れ条件に突き合わせる。

**Step 1: spec 差分記録を作成**（任意・推奨。`specs/2026-10-23-event-owner-permission-spec.md` の流儀に倣う。
spec-change-records スキルを参照）

- パス: `specs/2026-10-23-event-add-staff-owner-spec.md`
- 内容: 変更前後（`/event/add` の無検証 → claims 照合）、403 文言、テスト 4 件、受入条件との対応

**Step 2: 受け入れ条件の突き合わせ（issue の 4 条件）**

| 条件 | テスト | 結果 |
|---|---|---|
| 非 admin が自分の staff_id で作成できる | `test_event_add_self_non_admin_allowed` | PASS |
| 非 admin が他人の staff_id を指定 → 403・作成されない | `test_event_add_other_member_forbidden_for_non_admin` | PASS |
| admin は他人の staff_id でも作成できる | `test_event_add_admin_can_create_for_others` | PASS |
| 上記をカバーする API テストを追加 | Task 1-4 | PASS |

**Step 3: Commit（spec を含む）**

```bash
git add specs/2026-10-23-event-add-staff-owner-spec.md
git commit -m "docs: issue-22 実装の差分配録 (/event/add staff_id 照合)"
```
