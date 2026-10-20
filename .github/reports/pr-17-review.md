# PR #17 Review

**参照資料:** light_token_server Issue #16、`tasks/issue-16/plan.md`、`specs/2026-10-13-milestone-event-retrieval-spec.md`、`specs/2026-10-19-milestone-events-summary-exclusion-spec.md`、`.hermes/rules/milestones.md`

## 総評

Issue #16 の目的である、マイルストーン所属イベント API から `summary` を除外し、`to_dict()` の二重呼び出しをなくす変更は、実装・仕様・テストが整合しています。指摘事項はありません。

## 良い点

- 非 admin も参照可能な open/waiting のイベント API に対し、ブラックリストではなく `to_milestone_dict()` のホワイトリストを設け、closed 用 API にも同じレスポンス契約を適用しています。
- `/event/*` 等は従来どおり `to_dict()` を使い、`summary` を含む既存契約を保っています。
- イベント辞書を一度だけ構築して Team 情報を一括付与するため、重複生成と N+1 クエリの再発を避けています。
- 変更に対応するレスポンスキーの検証と既存 API の回帰テストが追加されています。

## 指摘事項

なし。

## 検証

- ローカル checkout: `uv run pytest tests/test_milestone.py -q` — **51 passed**（FastAPI TestClient に関する Starlette の deprecation warning 1 件）。
- GitHub Actions: PR にチェック結果は報告されていません。
