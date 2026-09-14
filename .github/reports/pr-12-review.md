# PR #12 Review

## 参照資料

- `.github/agents/pr-review.md`
- PR #12 本文・目的（`gh pr view 12`）
- `tasks/task-11/overview.md`
- `tasks/task-11/architecture.md`
- `tasks/task-11/tasks.md`
- `tasks/task-11/test-plan.md`
- `tasks/task-12/overview.md`
- `specs/2026-09-11-spec.md`
- `docs/architecture/2026-09-11-architecture.md`
- `origin/main` との差分

GitHub Issue は PR本文に関連付けられておらず、今回の変更は `tasks/task-11/` と
`tasks/task-12/` に対応しています。Issue #11 は本レビューの関連資料として扱いません。
PR本文にも Task-11/12 の記載はありませんでした。

## 総評

waiting 状態のマイルストーンを猶予期間経過後に自動で closed へ遷移する処理と、waiting から re-open した際に子イベントを未完了へ戻す処理が追加されています。

Task-11/12 の計画、実装内容は概ね整合しており、テストも全件成功しています。一方で、日付判定のタイムゾーン処理に実行環境依存の問題があり、JST基準の仕様を正確に満たせない可能性があります。また、PR本文に対応するタスク番号が記載されていないため、変更の背景と受け入れ条件を追跡しにくい状態です。

## 良い点

- `close_expired_waiting_milestones()` にDB更新ロジックを分離し、単体テストから直接検証できる構造になっている
- `MILESTONE_CLOSE_GRACE_DAYS`、`MILESTONE_CLOSE_INTERVAL_MINUTES`、`ENABLE_MILESTONE_SCHEDULER` を環境変数で制御できる
- FastAPI lifespanでスケジューラの起動・停止を管理している
- 自動 close の対象を `status == waiting` かつ `accomplished_date != None` に限定している
- `accomplished_date + grace_days <= today` の境界条件をテストしている
- re-open時の子イベント `completed=False` への変更について統合テストが追加されている
- 自動 close 時には子イベントの `completed` を変更しない仕様を維持している
- 全テストが成功しており、既存API挙動への明らかな回帰は確認されなかった

## 指摘事項

### [P1] JST基準の仕様に対して、日付取得がサーバーのローカルタイムゾーン依存

**対象箇所**

- `app/scheduler.py:11`
- `app/jobs/close_milestones.py:40-44`

`BackgroundScheduler` は `Asia/Tokyo` で設定されていますが、ジョブ内の日付取得は `date.today()` です。`date.today()` はOS・コンテナのローカルタイムゾーンに依存するため、サーバーがUTC設定の場合、スケジューラのJST設定と日付判定の基準が一致しません。

JSTの午前0時を基準に close すべきマイルストーンが、サーバーのタイムゾーンによって最大数時間ずれる可能性があります。境界日では、仕様上の「当日になったらclosed」と実際の動作がずれるおそれがあります。

**対応案**

```python
from datetime import datetime
from zoneinfo import ZoneInfo

today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
```

ジョブ側でも明示的にJSTの日付を取得し、スケジューラと判定基準を統一してください。

### [P2] re-open時に、waiting遷移で自動変更していない完了イベントまでFalseに戻す

**対象箇所**

- `app/routers/timetable.py:333-336`

re-open処理は、対象マイルストーンに所属する全イベントを無条件に `completed=False` にしています。

そのため、waiting遷移前から手動で `completed=True` にしていたイベントや、waiting中に個別に完了扱いへ変更したイベントも、re-open時に未完了へ戻されます。イベント単位で行った完了状態の変更が失われる可能性があります。

**対応案**

`tasks/task-12/overview.md` は今回の仕様として「所属する全イベントをFalseにする」と明記しているため、実装はタスク計画には一致しています。一方、これは手動完了状態も失わせる設計なので、将来仕様を変更する場合は、対象イベントを識別できる履歴・フラグ・遷移時点の状態保存などの設計が必要です。

なお、`.hermes/rules/milestones.md` の現行記述は「re-open時は子イベント completed を False に戻す」であり、Task-12の全件リセット方針と矛盾しないよう、手動完了状態もリセットされる点をより明示すると保守上安全です。

## 改善提案

1. JST基準の日付取得を共通化し、ジョブとテストで同じ基準を使用する
2. schedulerの単体テストを追加し、設定された間隔・タイムゾーン・ジョブ登録内容を検証する
3. 複数ワーカーでUvicornを起動する場合、各ワーカーが同じAPSchedulerを起動する点を確認する。重複実行を避ける場合は、専用ワーカー・分散ロック・DB側の排他制御などを検討する
4. PR本文に `tasks/task-11/` と `tasks/task-12/` の対応を明記し、自動 close と re-open の仕様・受け入れ条件を追跡可能にする
