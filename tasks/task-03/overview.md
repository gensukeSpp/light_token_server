# Task-03 実装計画 — /milestone/* API エンドポイント追加

> **For Hermes:** 実装は TDD(失敗→実装→成功→Commit)でタスク単位に進める。実装前に本ファイル群を読み、requirement-03.md と突き合わせること。

**Goal:** マイルストーン機能のバックエンド API を実装する — `POST /milestone/add`(作成、admin のみ・カラー自動選択)、`GET /milestone/all`(open マイルストーン一覧)、`POST /milestone/update/{id}`(達成日設定で close・子イベント completed 自動更新)、`DELETE /milestone/remove/{id}`(admin のみ削除)。加えて既存 `/event/add`・`/event/update` に `milestone_id` / `completed` を反映する。

**Architecture:** 既存 CRUD(`app/routers/timetable.py` の `/event/*` 群)と同じパターンで `/milestone/*` を同一ルーターに追加する。モデル(`MilestoneORM` + `EventORM.milestone_id/completed`)と Pydantic スキーマ(`MilestoneCreate` / `MilestoneUpdate`、`EventCreate/Update` 拡張)は **前タスク(Task 1・2)で実装済み**。本タスクはルーター実装が中心。色の自動選択は 10 固定パターンをコード内に持ち、open 中のマイルストーンと被らない色を選ぶ。

**Tech Stack:** FastAPI, SQLAlchemy, PyJWT(認可は既存 `require_token` / `get_token_claims`), Pydantic, pytest + httpx(テスト用 SQLite)

---

## この段階で完成するもの(成果物)

- `POST /milestone/add` → 201、admin のみ、open 中の色と被らない色を自動選択して作成
- `GET /milestone/all` → 200、open(status=True)のマイルストーン一覧(グループ横断で全共有)
- `POST /milestone/update/{id}` → accomplished_date 設定で close(status=False) + 属する全イベントの completed を True に自動更新
  - 一度 closed になったものは再 open 不可(API 層で拒否)
- `DELETE /milestone/remove/{id}` → admin のみ、マイルストーン削除(子イベントの milestone_id は None 化)
- 既存 `/event/add` に `milestone_id`(optional)対応、`/event/update/{id}` に `milestone_id` / `completed`(optional)対応
- テスト(`tests/test_milestone.py`)が SQLite で自動・再現可能に通る

## スコープ外(今回はやらない)

- PostgreSQL への **DB マイグレーション本体 — 利用者本人が実施**(モデルは既に定義済み。Alembic は用意済みだが実行しない)
- フロントエンド(time-table-to-line)側の UI・TanStack Query ・型定義変更 — これは別リポジトリ
- マイルストーン一覧のドラッグ&ドロップ、イベント伸縮・移動、`month` ビュー日またぎなどの将来展望
- close 後に一定日数経過で消える挙動、および **「表記している間は再 open 可」拡張**(ユーザー方針として予定、今回見送り)。ただしいずれ実装するため、status 遷移は取り外しやすい構造に保つ(architecture §5)。
- グループ単位でのマイルストーン閲覧フィルタ(要件はグループ横断共有のため、フィルタしない)

## 現在のコンテキスト / 前提

- **Task 1(モデル)・Task 2(スキーマ)は作業ツリーに実装済み・未 Commit**。`app/models.py` に `MilestoneORM`、`EventORM` に `milestone_id` / `completed`、`app/schemas.py` に `MilestoneCreate` / `MilestoneUpdate` と `EventCreate` / `EventUpdate` 拡張がある。
- 認証は既存 `Depends(require_token)`(Bearer 優先・httpOnly Cookie フォールバック)で、claims に `user_id` / `group_id` / `admin` が入る。admin 判定は `claims["admin"]` を使う(全 admin ユーザーが作/閉/削除可能)。
- `app/routers/timetable.py` に既存 CRUD(`/group/all`, `/event/add`, `/event/update/{id}`, `/event/remove/{id}` 等)がある。ここに /milestone/* を追加する。
- 色の 10 固定パターンは AGENTS.md / requirement-03.md に定義あり(下記 Architec §6)。
- テストは `tests/conftest.py` の SQLite(StaticPool + check_same_thread=False)+ `get_db` 依存上書きで動く。`client` fixture と `db_session_factory` は既存。

## 構成方針の要点

- **既存パターン踏襲**: `/milestone/*` は `/event/*` と同じ「`require_token` 依存 → claims から user_id / admin 取得 → `Depends(get_db)` で DB → Pydantic body → to_dict() 返却」の形にする。ルーターへ**後付けで** router 登録は必要なし(main.py は既に timetable.router を include している)。→ 新規ルーターを作らない。
- **admin 判定**: 作成/close/削除は `claims.get("admin")` が True のときのみ許可。False / 欠如なら 403。閲覧(`GET /milestone/all`)は require_token のみ(全ユーザーが閲覧可)。
- **色自動選択**: open 中マイルストーンの color の集合を取り、10 パターン先頭から順に未使用色を選ぶ。10 件全部使用中なら 1 番目から cyclic に戻す。
- **再 open 不可**: update で既に status=False(閉)のマイルストーンに close を再度適用したら 409(Bad Request 相当)。また accomplished_date 以外のフィールド(開き直し)を受け付けない。
- **close 連動更新**: update close 時に `EventORM.milestone_id == id` の全行へ `completed=True` を一括 UPDATE。
- **削除連動**: remove 時に子イベントの `milestone_id` を None に(色をデフォルト #2196f3 に戻す裏付け)。

## 判断ポイント(実装前に利用者へ確認)

1. **既 close への再 close の扱い(確定: 409)**
   - 既に `status=False`(closed)のマイルストーンを再度 update で close しようとした場合、**409 で拒否する**。利用者確認済み(2026-08): この 409 扱いは良好。
   - ⚠️ **将来方針(今回見送り)**: requirement-03.md「操作の流れ 4」の「何日か後にマイルストーン表記が消える」と組み合わせ、**表記している間は再 open できる**ようにする拡張を予定している。これにより「一度 closed したら再 open 不可」という現状の構想(requirement-03.md のカラム説明)はユーザー方針として**変更される予定**。今回は実装しないが、**今回の実装(409 で再 open 不可)を将来取り外しやすい構造にしておく**こと(下記 architecture §5 の注記)。
2. **update に title / description / guidline_end_date 変更も受け付けるべき?**
   - 要件(実装詳細)は「達成日を入力」のみで、編集は状況次第。マイルストーンの内容編集(タイトル・説明の修正)は**今回スコープ外**とし、`MilestoneUpdate` は `accomplished_date` のみとする(既定)。もし編集も必要なら後続タスク。

## ディレクトリ構成(実装後)

```
app/
  routers/
    timetable.py   # 変更: /milestone/* と /event/* の milestone_id / completed 対応を追加
  models.py        # 変更済み(Task 1): MilestoneORM + EventORM.milestone_id / completed
  schemas.py       # 変更済み(Task 2): MilestoneCreate / MilestoneUpdate / Event 拡張
  tokens.py        # 変更なし(require_token を再利用)
tests/
  conftest.py      # 変更: MilestoneORM シード用 helper を追加(任意)
  test_milestone.py # 新規: /milestone/* の統合テスト
```