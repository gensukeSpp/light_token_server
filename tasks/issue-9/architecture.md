# Issue-9 Architecture Snapshot: Milestone 更新処理 API 契約改善

## Purpose
Per Issue #9, upgrade the milestone update contract:
1. `/milestone/update/{id}` accepts editable fields(title/description/guideline_end_date) and replaces the "accomplished_date → **closed**" transition with "accomplished_date → **waiting**".
2. `/milestone/all` returns `status != 'closed'`(open + waiting) so the frontend's "猶予期間中(受け入れ 2)" display is satisfiable.
3. Fix the pervasive `guidline_end_date` → `guideline_end_date` typo (models / schemas / router / tests / alembic).

## Current behaviour (baseline, `app/routers/timetable.py`)
- `POST /milestone/update/{id}`: admin only; `MilestoneUpdate{accomplished_date}`(required); 409 if already closed; sets `status=closed`, `accomplished_date=body.accomplished_date`, and flips every child event (`milestone_id == id`) `completed=True`.
- `GET /milestone/all`: `filter(status == MILESTONE_OPEN)`.
- `DELETE /milestone/remove/{id}`: admin only; flips `status=closed` + children `completed=True`; returns `{"closed": id}`.
- `POST /milestone/add`: admin only; auto colour from open milestones only.

## Target contract (proposed; confirm via overview 判断ポイント before coding)
### `MilestoneUpdate` schema (`app/schemas.py`)
```python
class MilestoneUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    guideline_end_date: date | None = None   # was guidline_end_date
    accomplished_date: date | None = None
```
All fields optional → **partial update**: assign only non-`None` fields.
`accomplished_date` is used to drive the state transition (see below). Because it is `date | None`,
an explicit `null` (re-open) and an absent field must be distinguishable: use Pydantic to keep them
separate — e.g. inspect raw body keys, or simplest: treat the **presence** semantics as follows.

### State-transition rules for `/milestone/update/{id}`
Let `s = target.status`, `d = body.accomplished_date` (the *explicit* value actually resolved for this request).

| current `status` | body `accomplished_date` | result |
| :--- | :--- | :--- |
| open | given a date | → **waiting**, set accomplished_date; 子 completed (per 判断3) |
| waiting | given a date | stay **waiting** (date edited) |
| waiting | explicit `null` / no value(*) | **re-open** → open, clear accomplished_date(*) |
| closed | any | **409** (already closed) — unchanged from today |
| any | absent (no field) | kept; no status change — pure edit |

> (*) **Design decision needed** — the "re-open" trigger is the subtle piece. Two clean options:
>   - **Option A (explicit null = re-open):** the client sends `"accomplished_date": null` to re-open a `waiting` milestone. Absent field (just title edit) does not touch status.
>   - **Option B (edits keep date):** no re-open in this Issue (scope: only introduce waiting; re-open on the next). Simpler, less test churn.
> Recommend **Option A** since it matches the issue's "猶予期間中、再 open が可能". Confirm in overview 判断ポイント 1/4.

Because `MilestoneUpdate` fields are `str|date|None` with defaults, an omitted field is indistinguishable from an explicit `null` in pure pydantic fields. To implement Option A reliably, use a **model_validator / raw-dict presence check** in the endpoint or a sentinel (`model_fields_set`) so "字段が送られたか" is known. Simple implementation:
```python
from pydantic import model_validator, Field
class MilestoneUpdate(BaseModel):
    ...
    @model_validator(mode="before")
    @classmethod
    def _keep_fields(cls, v):
        cls.__generic__(v)  # capture set names; store on instance attr
```
or shorter: read `body.model_fields_set` in the router to know whether `accomplished_date` was provided at all. This is the crux — implement with `model_fields_set`.

### `/milestone/all`
```python
rows = db.query(MilestoneORM).filter(MilestoneORM.status != MILESTONE_CLOSED).all()
```
Returns both `open` and `waiting`.

## Colour rule (unchanged)
`_next_color` still picks a colour not used by **open** milestones only (waiting milestones no longer occupy a colour slot is out of scope — keep current). Add/remove unchanged.

## Spelling fix scope
Rename to `guideline_end_date` in:
- `app/models.py` (`Column` + `to_dict`)
- `app/schemas.py` (`MilestoneCreate` + `MilestoneUpdate`)
- `app/routers/timetable.py` (`/milestone/add` body reference)
- `tests/test_milestone.py` (if used)
- Alembic: new revision (rename column `guidline_end_date` → `guideline_end_date`). Run left to the user.

## Files
- Modify: `app/models.py`(rename column), `app/schemas.py`(extend MilestoneUpdate, spell), `app/routers/timetable.py`(update logic + all filter + spell)
- New: Alembic revision(diff only; apply = user)
- Modify tests: `tests/test_milestone.py`(closed→waiting, editing, all open+waiting)