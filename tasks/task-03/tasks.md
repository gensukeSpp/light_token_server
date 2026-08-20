# Task-03 実装タスク

実装は下記を順に、各タスクで **TDD(失敗→実装→成功→Commit)** を回す。各タスクは 5–15 分規模。

前提: 作業ディレクトリはプロジェクトルート `/home/nabu_dvl/workspace/the-calendar-to-timeline/light_token_server`。`source .venv/bin/activate` を済ませてから `uv` 系コマンドを実行する。

前タスク(Task 1: モデル / Task 2: スキーマ)は作業ツリーに実装済み・**未 Commit**。本タスクはそれらを土台に `/milestone/*` ルーターを実装し、最後にまとめて Commit する(Task 1・2 のファイルも一緒に上げる)。コミット粒度は後述(Task 5)参照。

---

### Task 1: モデルとスキーマの確定(前タスク分の再確認)

**Objective:** Task 1・2 で入っているモデル/スキーマが要件どおりか再確認し、実装の土台を固める。コード変更は必要に応じてのみ。

**Files:**
- Read: `app/models.py`(MilestoneORM, EventORM.milestone_id / completed)
- Read: `app/schemas.py`(MilestoneCreate / MilestoneUpdate / EventCreate / EventUpdate)

**Step 1:** `app/models.py` / `app/schemas.py` を読み、下表と一致するか確認する。

- `MilestoneORM`: id / staff_id(FK→M_LOGGININFO.STAFFID) / title(100) / description(256, nullable) / color(10) / status(bool, default=True) / created_at(Date) / guidline_end_date(Date, nullable) / accomplished_date(Date, nullable)
- `EventORM`: milestone_id(FK→M_MILESTONE.id, nullable) / completed(bool, default=False)
- `MilestoneCreate`: title / description? / guidline_end_date?
- `MilestoneUpdate`: accomplished_date
- `EventCreate` / `EventUpdate`: milestone_id / completed の optional 追加

**Step 2:** import が通るか検証
```bash
uv run python -c "from app.models import MilestoneORM, EventORM; from app.schemas import MilestoneCreate, MilestoneUpdate, EventCreate, EventUpdate; print('ok')"
```
Expected: `ok`

**Step 3:** Commit はせず、次の Task 2 へ(Task 1・2 の実装含め、まとめて後で Commit する)。

---

### Task 2: 失敗テストを書く — tests/test_milestone.py(本命)

**Objective:** /milestone/* の振る舞いを TDD で検証するための統合テストを先に作る。

**Files:**
- Create: `tests/test_milestone.py`

**注意:** 既存 `tests/test_timetable.py` のセッションクッキーまわり 10 件は**ベースから既に失敗**している。ここではその影響を受けないよう、`test_bearer_header_only_*` と同じく **Bearer トークンを直接生成して送る方式**を使う。

**Step 1:** ヘルパーを用意(ファイル冒頭)
```python
import jwt
from app import tokens

def _bearer(admin: bool = True) -> dict:
    access = tokens.create_access_token(1001, 3, admin)
    return {"Authorization": f"Bearer {access}"}
```

**Step 2: テストケースを書く(failing)**

| # | ケース | 期待 |
|---|--------|------|
| 1 | `POST /milestone/add`(admin) | 201、`color` が `MILESTONE_COLORS` の 未使用色、`status==True`、`staff_id==1001` |
| 2 | 色衝突回避: 1件目 `#9c27b0` → 2件目は `#009688` | 2 件目 add の color が `#009688` |
| 3 | `GET /milestone/all` | open のみ返る(作成後 1 件、close 後は 0 件) |
| 4 | `POST /milestone/add`(非 admin) | 403 |
| 5 | `POST /milestone/update/{id}`(admin, accomplished_date) | 200、status=False、子イベント completed=True |
| 6 | close 済みを再度 update | 409 |
| 7 | 存在しない id を update | 404 |
| 8 | `DELETE /milestone/remove/{id}`(admin) | 200、子イベント milestone_id=None |
| 9 | `/event/add` に milestone_id を渡す | 201、返る to_dict に milestone_id が入る |
| 10 | `/event/update/{id}` に completed=True | 200、to_dict の completed が True |

**Step 3: 失敗確認**
```bash
uv run pytest tests/test_milestone.py -v
```
Expected: FAIL(まだエンドポイント未実装 → 404)

**Step 4:** Commit(**まだしない**。Task 3–4 の実装が済んで初めて pass するため、このテストは「red」で残す)

---

### Task 3: 色パレット定義と _next_color ヘルパー

**Objective:** 10 固定パターンと、open 中の色を避けて選ぶヘルパーを実装する。

**Files:**
- Modify: `app/routers/timetable.py`

**Step 1:** `MILESTONE_COLORS` 定数と `_next_color(db)` ヘルパーを追加(architecture §4 のコード)。

- カラーパターンは AGENTS.md / requirement-03.md の 10 色をそのまま使う。
- `_next_color` は open(status=True)の MilestoneORM.color を集め、未使用色を先頭から返す。10 件全部使われていれば `MILESTONE_COLORS[0]` に戻す。

**Step 2: import 追加**
- `from datetime import date`(既存 import に date を足す)
- `from ..models import StaffLogin, Team, User, EventORM` → `MilestoneORM` を追加

**Step 3: ユニット確認**
```bash
uv run python -c "from app.routers.timetable import MILESTONE_COLORS, _next_color; print(len(MILESTONE_COLORS), _next_color)"
```
Expected: `10` と okay(実際に呼ぶには DB が要るため、ここでは import 確認のみ)

**Step 4:** Commit はせず、Task 4 へ。

---

### Task 4: /milestone/* エンドポイント実装

**Objective:** add / all / update(close) / remove の 4 つを実装し、Task 2 のテストを通す。

**Files:**
- Modify: `app/routers/timetable.py`

**Step 1:** architecture §5 のコードを `app/routers/timetable.py` に追記(4 エンドポイント)。admin 判定は `if not claims.get("admin"): raise HTTPException(403, ...)`。

**Step 1.5(close 実装の構造):** close 済みへの再 close は **409** で返す(利用者確認済み)。ただし将来「表記している間は再 open 可」に拡張する予定のため、status 遷移の分岐を**エンドポイント内で 1 箇所にまとめる**(`if target.status is False: 409` の直後に close 処理を続ける形。architecture §5 のコードがそのまま該当)。将来ここに re-open 分岐を足せるように、ロジックを素直に置く(この時点では複雑化しない)。

**Step 2: 既存 /event/add に milestone_id / completed を、/event/update に milestone_id / completed 反映を追加**(architecture §5 下部)。

**Step 3: テスト**
```bash
uv run pytest tests/test_milestone.py -v
```
Expected: すべて PASS。失敗があれば実装とテストを突き合わせて修正。

**Step 4:** Commit は Task 5 で一括。

---

### Task 5: 全テスト + まとめて Commit

**Objective:** マイルストーン系テストが通ること、既存を壊していないことを確認し、Task 1–4 をまとめて Commit する。

**Step 1: マイルストーンのみ確認**
```bash
uv run pytest tests/test_milestone.py -v
```
Expected: 全 PASS(実装タスクの完了条件)

**Step 2: 既存の壊れ具合を差分で確認**(あくまで情報)
```bash
uv run pytest -q
```
- 既存 `test_timetable` の 10 失敗は**ベースから既に存在**(本タスク起因ではない)。それ以外(new / health / login / tokens)は PASS のはず。
- マイルストーン実装が既存を新たに壊していないことを、ベース状態との 比較 で確認。

**Step 3: git add して Commit**
```bash
git add app/models.py app/schemas.py app/routers/timetable.py tests/test_milestone.py tasks/task-03/
git commit -m "feat #260820: マイルストーン /milestone/* API 追加 (モデル・スキーマ・ルーター・テスト)"
```

**Step 4:** `git status --short` が空(or 意図したファイルのみ)であることを確認。

---

## 着手順・依存

```
Task1(models/schemas 再確認) → Task2(テスト作成・未PASS)
 → Task3(色ヘルパー) → Task4(エンドポイント実装)
 → Task5(全テスト・Commit)
```

- Task 2 は Task 3/4 が無いと pass しないため、red のまま先に実装を進める(red→実装→green の順)。テストは実装前に書く(red)。
- Task 3→4 は logn順依存(色ヘルパーが add に使われる)。

## 実装時の留意(共通)

- **`uv` コマンド前は必ず `source .venv/bin/activate`**(ユーザー指示)。
- DB は必ず `Depends(get_db)` 経由。`SessionLocal()` 直呼びしない。
- `raise RedirectResponse(...)` は使わない(Starlette 1.4.1)。milestone 系は 303 を使わないが、共通注意として。
- 既存 `test_timetable.py` の 10 失敗は**本タスクのスコープ外**(別 Task)。勝手に直さない。
- コミットは **Task 1・2 の実装込みで Task 5 に一括**(このブランチはまだ作業中)。