# Issue-9 実装計画 — マイルストーン更新処理 API 契約の改善

> **For Hermes:** 実装は TDD(失敗→実装→成功→Commit)でタスク単位に進める。実装前に本ファイル群と `requirement-03.md`、`tasks/task-03/` の既存マイルストーン仕様を読み、未変更の部分(remove・イベント completed 連動)を壊さないこと。

**Goal:** GitHub Issue #9「[Feature]マイルストーン更新処理 API 契約の実装」のとおり、`/milestone/update/{id}` を **タイトル等の編集対応** に拡張し、accomplished_date 設定時の status 遷移を **「直接 closed」→「waiting(猶予期間)」** に変更する。あわせて `/milestone/all` が **open + waiting**(`status != 'closed'`)を返すようにして、フロント側(Issue #18)の「猶予期間中表示」を受け入れ 2 として成立させる。加えて全所の `guidline` スペルミス(`guidline_end_date` → `guideline_end_date`)を是正する。

**Architecture:** `/milestone/*` は既存通り `app/routers/timetable.py` 内の同一ルーターに実装する(新規ルーターは作らない)。`MilestoneUpdate` schema を拡張し、update は「部分更新(指定フィールドのみ反映)」とする。status 遷移は requirement-03.md の最新方針:
`open → accomplished_date入力で waiting → 猶予期間 → closed`。
`waiting` 中は再 open 可(なった場合に closed 後の 409 を「削除」し、waiting -> open の遷移を追加するのは次 Issue 対応。今回のスコープは「waiting を導入し、close は accomplished_date 入力の猶予扱い」にとどめ、**closed 自体は今回 DB データ上生じない**(既存テストの closed 期待は後述で調整)。正確な status 遷移ルールは overview「判断ポイント 1」参照)。

**Tech Stack:** FastAPI, SQLAlchemy(2.x), Pydantic, pytest + httpx(テスト用 SQLite)

---

## この段階で完成するもの(成果物)

- `MilestoneUpdate` schema を `{ title?, description?, guideline_end_date?, accomplished_date? }` に拡張(全部 optional・フィールドを明示更新)
- `POST /milestone/update/{id}` が編集対応。accomplished_date 設定時は status を **closed ではなく waiting**(`MILESTONE_WAITING`)へ遷移
- 編集可能: title / description / guideline_end_date(任意組合せで更新、未指定は不変)
- accomplished_date 解除(`None` 指定)→ `waiting` から `open` へ戻す(再 open)
- `GET /milestone/all` が **open + waiting**(`status != 'closed'`)を返す → 受け入れ 2(猶予中一覧表示)が成立
- `DELETE /milestone/remove/{id}` / `/milestone/add` は **現状のまま**(契約不変: remove は `{"closed": id}`、色自動選択は open のみ基準のまま)
- 全所に渡るスペル修正: `guideline_end_date`(SQLAlchemy から Pydantic・ルーター・テストまで)
- モデルのカラム名変更に伴う **PostgreSQL マイグレーションは利用者本人が実施**(本タスクでは SQLite・Alembic 差分生成のみ)
- テスト(`tests/test_milestone.py`)が SQLite で自動・再現可能に通る

## スコープ外(今回はやらない)

- **猶予期間の自動 closed(数日後の cron/ジョブ)** — issue 明示で「期間は未定のため今回スコープ外」
- closed 済みマイルストーンの再 open API(open データが無いため「waiting -> open」のみ対応。closed への遷移を来 Issue で扱う)
- フロントエンド(time-table-to-line)側 UI・TanStack Query・型定義変更(別リポジトリ / Issue #18)
- PostgreSQL への **DB マイグレーション本体 — 利用者本人が実施**(Alembic リビジョン作成までをこちらで用意し、実行は利用者)
- `guideline_end_date` 以外の schema/DB 設計変更(カラム追加・型変更はしない)

## 現在のコンテキスト / 前提

- マイルストーン機能(task-03 済み)で、`MilestoneORM`(status は `String(10)`, default `open`)と、`MILESTONE_OPEN` / `MILESTONE_WAITING` / `MILESTONE_CLOSED` 定数は `app/models.py` に定義済み
- `app/routers/timetable.py` に `/milestone/add` `/milestone/all` `/milestone/update/{id}` `/milestone/remove/{id}` が実装済み
- `MilestoneUpdate` schema(`app/schemas.py`)は現状 **`accomplished_date: date`(必須)** のみ。`/milestone/update` は `accomplished_date` を受けて status を直接 closed にし、子イベント completed=True を一括更新
- `/milestone/all` は `status == MILESTONE_OPEN` のみ返す
- 認証は既存 `Depends(require_token)`(Bearer 優先・httpOnly Cookie フォールバック)。update/remove/add は `claims["admin"]==True` のみ、all は require_token のみ
- 既存テスト `tests/test_milestone.py` は 「accomplished_date 入力 → status closed」 を期待(10 件)。これらは**新契約に合わせて更新必須**(tasks.md Task で置換)
- 現時点のコード・テストは `guidline_end_date` という誤スペル(どのファイルでも)。これは手動で `guideline_end_date` へ揃える

## 構成方針の要点

- **部分更新(partial update)**: `MilestoneUpdate` を全部 optional にし、None 以外のフィールドのみ対象へ代入。`accomplished_date` は「値を持つ -> waiting 遷移 / 編集」「None 明示 -> waiting から開き直し(open)」で判定
- **状態遷移テーブル**(次の判断ポイントで確定)
- **射影**: `/milestone/all` を `status != MILESTONE_CLOSED` で取得
- **既存を壊さない**: `/milestone/remove` の「closed 化 + 子 completed=True」と `/milestone/add` の色ロジックは無変更
- **スペル統一**: `guideline_end_date` を models / schemas / routers / test / alembic 全体で統一。カラム名変更は DB マイグレーション対象

## 判断ポイント(実装前に利用者へ確認)

1. **`/milestone/update/{id}` の status 遷移と closed の扱い** ⭐
   対象: 「open → waiting → closed」の closed 遷移は今回も**タイミングが未定(猶予期間スコープ外)**か。もしそうなら、本リリースでは **closed 自体を生成しない**(DB 上のデータは open / waiting のみ)でよいか。既存テストの「close 期待」はそれに合わせて削除/変更する。遷移の一案:
   - open で `accomplished_date` 指定 -> **waiting** + accomplished_date 設定 (子 completed=true にするかは判断 3 参照)
   - waiting で `accomplished_date=None` 明示 -> **open** (再 open、accomplished_date は None に戻す。子 completed を戻すかは判断 4 参照)
   - closed はこの Issue では生じない。確定仕様を tasks 冒頭に追記する。
2. **update の編集は「全部 optional で未指定は不変」でよいか**
   - 既定: 送られなかったフィールドは変更しない(部分 update)。title のみ更新したい場合に accomplished_date を渡さず編集できる。
3. **accomplished_date 設定時(waiting 遷移)の子イベント `completed`**: 現状は「close (=waiting) で全子イベント completed=True」を維持するか(推奨)、それとも closed 確定時のみに変更するか。
4. **waiting -> open(再 open)時の子イベント `completed`**: 現状未定義。既定は `completed=False` へ戻す(猶予中に開いたので未完扱い)が、既に完了したイベントを無理やり戻さない(completed=True は維持)という選択肢もある。
5. **`guideline_end_date` の DB カラム名変更**: 現在の既存テーブル(Migration `04ad260cac90` 含む)のカラムは `guidline_end_date`。SQLAlchemy の `Column` 名だけを変更すると既存 DB との不整合が生じるため、**DB マイグレーション(名前変更)が必ず必要**。リネーム方針で良いか(実行は利用者本人が PostgreSQL で実施)。

## ディレクトリ構成(実装後)

```
app/
  models.py         # 変更: guidline_end_date -> guideline_end_date(カラム名・to_dict)
  schemas.py        # 変更: MilestoneUpdate を拡張、MilestoneCreate の guidline を修正
  routers/
    timetable.py     # 変更: /milestone/update(編集+waiting)・/milestone/all(open+waiting)
migrations/
  versions/<new>.py  # 新規: カラムリネーム(DB マイグレーション本体は利用者実施)
tests/
  test_milestone.py # 変更: closed 期待 -> waiting 期待・編集テスト追加
```

## 着手順・依存

```
Task1(設計確定 / 判断ポイント回答) → Task2(スペル修正: guidline→guideline + Alembic リビジョン)
    → Task3(schemas.py 拡張 + /milestone/update 編集+waiting)
    → Task4(/milestone/all open+waiting)
    → Task5(テスト整備・全回帰)
```
- **Task 2 を先に**行う: モデルの `guidline_end_date` → `guideline_end_date` カラム名変更は後続 Task が依存する点であるため、最初に確定させる(Alembic リビジョン生成 + 実行は利用者)。
- Task 4 は Task 3 の update とはほぼ独立(読むだけの変更)。order 上は Task 3 の後に置く。
- Task 5 は既存 `tests/test_milestone.py` の closed 期待を waiting 期待へ書き換え、編集テストを追加する。本番 DB は不要(SQLite インメモリ)。