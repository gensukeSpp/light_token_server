# セキュリティレビュー (2026-10-22)

- 対象: `light_token_server` (Python 30 ファイル / 217 ノード)
- 対象ブランチ: `feature/progress-null` (未コミットの `docs/architecture/README.md` 変更と未追跡の `docs/architecture/2026-10-22-architecture.md` / `pick_1020` は対象外)
- 実施内容: `security(action="scan", engine="heuristic")` の実行、および手動の grep / ソース確認による補完
- 種別: 読み取り専用 (コード変更なし)
- 比較基準: `main` ブランチは存在しないため未使用。ソース全体を対象とした

## 1. security scan 結果

- engine: heuristic
- total: 0 / by_severity: {} / by_rule: {} / suppressed: 0
- semgrep は未インストールのため未実行
- 注意: heuristic スキャンは 0 件だったが、後述の `print` による秘密情報出力は検出されていない。空の結果は「安全」を意味しない。

## 2. 手動確認による指摘事項

| # | 重要度 | カテゴリ | 箇所 | 内容 |
|---|--------|----------|------|------|
| S-1 | High | 秘密情報のログ出力 | app/tokens.py:26 | `_encode` が毎回 `SECRET_KEY[:5]` を標準出力へ出している。署名鍵の先頭 5 文字が全発行で露出し、鍵の探索空間を縮める。 |
| S-2 | High | トークンのログ出力 | app/tokens.py:64 | `_bearer_token` が `token[:10]` を出力。アクセストークン/リフレッシュトークンの先頭が残る。 |
| S-3 | Medium | 認証情報の過剰ログ | app/tokens.py:90 | `Decoded claims: {claims}` で user_id / group_id / admin / exp を出力。 |
| S-4 | Medium | ヘッダーの生出力 | app/tokens.py:61 | `Invalid Authorization header format: {auth}` で Authorization ヘッダー全体を出力。`Bearer` 以外のスキームで送られた場合に秘密値が丸ごと残る。 |
| S-5 | Medium | 開発用の既定秘密鍵 | app/config.py:40 | `SECRET_KEY` の既定値 `dev-insecure-secret-change-me` が、`ENV` 未設定時 (既定 `development`) にそのまま使われる。本番デプロイで `ENV` を設定し忘れると、公開されている既定値で JWT が署名・検証される。 |
| S-6 | Low | デバッグ出力の残存 | app/tokens.py:57,80,86,93,96 | 認証フローの print が本番でも出力される (情報量が多く、ログ監査を難しくする)。 |

## 3. 解消済みの確認

- 2026-08-10 レビューの指摘 #1 (app/config.py の `SECRET_KEY` 重複代入) は解消済み。現在は 1 回の代入 + 本番時の存在チェックになっている (app/config.py:39-42)。
- CORS は `allow_origins` が明示リストで、ワイルドカードではない (app/main.py:32-37)。
- Cookie は httpOnly / samesite=lax で設定されている (app/tokens.py:101-115)。
- JWT の検証は `algorithms=[ALGORITHM]` の固定指定で、alg 切り替え攻撃は防がれている (app/tokens.py:46)。

## 4. 改善提案

1. S-1 / S-2 / S-4: app/tokens.py の秘密情報を含む print を削除する。必要ならデバッグ用に `logging` を使い、トークン・秘密鍵・ヘッダー値は一切出さない。
2. S-3 / S-6: 認証フローの print をすべて削除するか、`logging.debug` に置き換える。
3. S-5: 本番判定を `ENV` の既定値 (development) に依存させない。`SECRET_KEY` 未設定で既定値に落ちる挙動を、`ENV` の値に関係なく失敗させるか、既定値の使用を明示的な開発フラグに限定する。
4. 対応後は `uv run pytest` (tests/test_tokens.py, tests/test_login.py) で認証フローの回帰を確認する。
5. heuristic スキャンでは秘密情報のログ出力を検出できないため、semgrep などのルールを併用することを検討する。

## 5. 作業メモ

- 修正は行っていない (指示どおり)。
- 対応する task 番号は未割当。優先度 High の S-1 / S-2 を先に処理することを推奨する。
