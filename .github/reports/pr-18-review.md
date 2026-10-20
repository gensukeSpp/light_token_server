# PR #18 Review

**参照資料:** `time-table-to-line` Issue #41、light_token_server の `.hermes/rules/milestones.md`、`requirement-03.md`

## 総評

Issue #41 が必要とする閉じたマイルストーンの一覧 API は、admin 限定、closed 状態のみ、達成日の降順という要件を満たしています。実装上の重大な問題は見つかりませんでした。PR #18 のブランチには PR #17 のコミットも含まれているため、PR のスコープとマージ順は明確にしておく必要があります。

## 良い点

- `GET /milestone/closed` は認証後に admin 権限を検査し、closed 状態のデータだけを取得します。
- 達成日を降順で返し、`accomplished_date` が `NULL` の削除由来の closed マイルストーンを末尾に配置します。
- closed / open / waiting の除外、日付順、`NULL` の並び、非 admin の拒否をテストしています。

## 指摘事項

- **[低] PR スコープの重複:** PR #18 の `feature/milestone-closed/41` ブランチには、PR #17 のコミット `39979be`（Issue #16 の `summary` 除外とシリアライズ変更）が含まれています。この変更は Issue #41 の一覧 API には不要で、PR #17 も別途 open です。PR #18 を PR #17 に依存する stacked PR として扱うなら、その関係を明示し、PR #17 を base にするのが適切です。独立 PR とするなら、PR #17 の変更が main に入った後に PR #18 を更新すると、重複レビューやマージ時の曖昧さを避けられます。**実行時の不具合ではありません。**

## 検証

- ローカル checkout: `uv run pytest tests/test_milestone.py -q` — **51 passed**（FastAPI TestClient に関する Starlette の deprecation warning 1 件）。
- GitHub Actions: PR にチェック結果は報告されていません。
