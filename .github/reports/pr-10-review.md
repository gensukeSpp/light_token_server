# PR #10 レビュー

## 参照資料

### 確認済み
- GitHub Issue #9: `gh issue view 9`
- Pull Request #10: `gh pr view 10`
- PR差分: `gh pr diff 10`
- ローカル差分: `git diff origin/main...HEAD`
- 最新 spec: `specs/2026-08-28-2-spec.md`
- 最新アーキテクチャ文書: `docs/architecture/2026-08-28-2-architecture.md`
- 補足: `tasks/issue-9/{overview,architecture,tasks,test-plan}.md`、`requirement-03.md`

### 存在しない／代替した資料
- ローカルの `main` ブランチは存在せず、`git diff main` は実行できなかったため、追跡済みの `origin/main` を比較対象にした。
- `.github/reports/pr-10-review.md` は存在しなかったため、新規作成した。
- 最新 spec とアーキテクチャ文書は作業ツリーには存在するが、現PRの差分には含まれない（未追跡ファイル）。レビューの仕様参照として確認した。

## 総評

Issue #9 の目的である、`/milestone/update/{id}` の部分更新対応、`accomplished_date` 設定時の `waiting` 遷移、`/milestone/all` の open + waiting 対応、スペル修正は概ね実装されている。Issue・PR本文・最新の仕様／アーキテクチャ文書の主要な契約も一致している。

ただし、既存DBに v0.06 以前からマイルストーンが存在する場合、旧ステータス値との互換性を考慮していないため、closed相当のデータが一覧に出たり、再更新できたりする可能性がある。加えて、Issueで維持するとした closed 再更新時の409を、テストが検証しなくなっている。

## 良い点

- `body.model_fields_set` により、`accomplished_date` の未指定と明示的 `null` を区別できている。
- `open -> waiting`、`waiting -> open`、closedへの更新拒否という状態遷移を、既存の管理者権限制御と組み合わせて実装している。
- `/milestone/all` を `status != MILESTONE_CLOSED` とし、waitingを一覧に含めるIssue要件を直接反映している。
- `guideline_end_date` のモデル、スキーマ、ルーター、レスポンス、Alembicリビジョンを揃えて変更している。
- `uv run pytest tests/test_milestone.py -q` は15件、全体テストは42件とも成功した。

## 指摘事項

### [P1] 旧ステータス値のまま残る既存行が、closedとして扱われない

- **箇所**: `app/routers/timetable.py:280-283, 300-301`、`migrations/versions/3be6e8d10186_v0_06.py:46-54`、今回追加の `migrations/versions/e0fbbca5c733_v0_07.py`
- **問題**: v0.06のマイグレーションは `Boolean` から文字列へ型変更するだけで、既存値 `true` / `false` を `open` / `closed` に正規化していないことをコメントでも示している。ところが今回の一覧取得は `status != 'closed'`、再更新拒否は `status == 'closed'` の完全一致である。
- **影響**: v0.06以前に作成された closed相当の行（`'false'`）が `/milestone/all` に表示され、`/milestone/update/{id}` でも409にならず更新・再オープンできる。既存データがある本番環境で、今回のstatus契約を満たさない。
- **望ましい対応**: マイグレーションで既存値を `true -> open`、`false -> closed` に変換してから新APIを有効化する。併せて一覧は必要に応じて `status.in_(MILESTONE_OPEN, MILESTONE_WAITING)` とし、未知の旧値を公開一覧へ流さない。既存データを使ったマイグレーション後の回帰テストも追加したい。

### [P2] closed再更新時の409がテストから抜けている

- **箇所**: `tests/test_milestone.py:124-143`
- **問題**: 旧 `test_milestone_reclose_returns_409` が、waiting中に日付を再指定して200になるテストへ置き換えられている。Issue #9および最新のIssueタスク／設計文書は「closed + any は409」を維持する契約である。
- **影響**: 現在の実装には409チェックがあるものの、将来その分岐を壊してもテストで検知できない。受け入れ条件の回帰検証が不足している。
- **望ましい対応**: `DELETE /milestone/remove/{id}` でclosed化した後、`POST /milestone/update/{id}` が409を返すテストを復元する。waitingへの再指定が200になるケースは別テストとして残す。

### 仕様上の差異（要確認）

- `.hermes/rules/milestones.md` は、セマンティクスでは「グループ横断共有・`group_id` 不要」としつつ、権限節では「閲覧は `group_id` でフィルタ」と記載している。ルーターの実装とIssue/PR本文はグループフィルタなしの挙動である。Issue #9の範囲外ではあるが、一覧の可視範囲をどちらにするか文書を統一したい。

## 改善提案

- `description` と `guideline_end_date` はモデル上nullableだが、`app/routers/timetable.py:304-309` では `None` を無視するため、既存値を明示的にクリアできない。nullを「クリア」として許可するか、現在の「未指定と同じく無視する」契約をAPI仕様に明記する。
- `tasks/task-03/*.md` には旧 `guidline_end_date` の記載が残っている。今回の「全所のスペル修正」という説明と齟齬があるため、履歴資料として残す場合でも旧仕様であることを明記する。

