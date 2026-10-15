# PR #14 レビュー記録

- 対象: gensukeSpp/light_token_server PR #14「Feature: マイルストーンからイベントを参照する API エンドポイント」
- 状態: DRAFT / base: main / head: feature/milestone-event-api (074d863)
- 比較基準: origin/main (ローカルに main ブランチが無いため origin/main を使用)
- 差分: 追加 319 / 削除 99 / 変更 8 ファイル
- レビュー日: 2026-10-15

## 参照資料の確認

確認できたもの:
- PR 本文 (gh pr view 14)
- specs/2026-10-13-milestone-event-retrieval-spec.md (本 PR の新規 spec。対象機能に一致)
- .hermes/rules/milestones.md (マイルストーンのルール。本 PR で更新)
- tasks/task-11/ (自動 closed。closed 判定と猶予日数の根拠)
- tasks/task-12/overview.md (re-open 仕様変更の計画。本 PR とは別タスク)
- docs/design/2026-08-10-auth-contract-mismatch.md (トークン契約)

確認できなかったもの:
- Issue 番号: PR 本文・ブランチ名・コミットに明示的な Issue 番号が無いため gh issue view は実行せず、「issue なし」として扱った
- tasks/ 配下に本 PR 専用の task ディレクトリは無い。内容的に milestone 関連の task-11 / task-12 / issue-9 に近いが、対応する task は特定できず
- docs/architecture/ 配下の milestone 向け architecture: 2026-10-15-architecture.md は未追跡ファイル (ローカル作業物) で PR に含まれない。本 PR 専用の architecture は無い
- `.claude/settings.json`: ローカルでは未追跡の `.claude/` 配下にあり、リポジトリ管理下ではないため内容を確認できず

## 検証

- uv run pytest: 64 passed (PR 本文の「64 tests pass」と一致)
- better-code-review-graph review(action=context, base=origin/main): 変更 8 ファイル、影響ノード 0。グラフ上の影響範囲は小さいと判定。ただしグラフは新規エンドポイントを変更ノードとして捉えられていないため、判定は参考程度とした
- 差分の目視とソース照合を実施

## 総評

マイルストーンに所属するイベントを、admin 限定で全グループ横断取得する 2 エンドポイント (`GET /milestone/{id}/events`、`GET /milestone/closed/{id}/events`) を追加する PR。spec と rules の内容は実装と概ね一致しており、テストも 64 件通過している。

一方で、本来のスコープ外の変更が混入している。特に `app/config.py` の APP_URL の既定値変更と、マイルストーン関連設定の既定値変更は PR 本文に記載がなく、ローカル開発の挙動に影響する。また `.github/copilot-instructions.md` は大規模に書き換えられており、既存の内容が一部失われている。DRAFT のまま、これらを切り分けてから出すことを推奨する。

## 良い点

- 権限チェックは `require_token` の後、`claims.get("admin")` で 403 を返す。spec の「管理者以外は 403」と一致
- open/waiting 用と closed 用の endpoint で状態フィルタを分けており、spec の「closed は別 API」という方針どおり
- 対象状態以外・存在しない ID はどちらも 404 で統一されている
- テストで「グループ横断」「waiting の扱い」「closed 側の 404」「非 admin の 403」を押さえている
- rules の Permission model / API endpoints / spec の 3 箇所で仕様が揃っている

## 指摘事項

### [High] H-1: APP_URL の既定値が本番 URL に切り替わっている (app/config.py:43-46)
- 変更前は `CALENDAR_TIMELINE` 未設定時に `http://localhost:5173`、変更後は本番 URL `https://calendar-to-timeline.ktde-z3837.workers.dev` が既定値になっている
- 影響: 環境変数を設定せずに開発すると、`/timetable/auth` のリダイレクト先 (timetable.py:97) や login の app_url、CORS の許可オリジンが本番向けになる。開発時に本番フロントへ飛ぶ、もしくは CORS 挙動が変わる
- コメント「本番環境ならこっち、削除しないでね」「ローカルならこっち、削除しないでね」の意図を崩している
- 期待する修正: 本 PR からこの変更を外す。本番切替が必要なら、環境変数 (ENV=production 等) で分岐させるか、別 PR で扱う

### [High] H-2: マイルストーン設定の既定値変更が PR 本文に記載されていない (app/config.py:53,55)
- `MILESTONE_CLOSE_GRACE_DAYS` 既定値: 0 → 5
- `MILESTONE_CLOSE_INTERVAL_MINUTES` 既定値: 1 → 10
- 影響: 自動 closed の挙動 (猶予期間・実行頻度) が既定値で変わる。既存デプロイで環境変数を設定していない場合、closed 遷移のタイミングが変わる
- 矛盾: `.hermes/rules/milestones.md:59` と `tasks/task-11/architecture.md:71` は間隔の既定値を 60 分としており、config (10 分) と一致しない。どちらかが誤り
- 期待する修正: 本 PR のスコープから外すか、PR 本文に変更理由を明記する。その上で rules / task-11 と既定値を一致させる (例: 10 分 or 60 分のどちらかに統一)

### [Medium] M-1: .github/copilot-instructions.md の大規模な書き換えで情報が欠落
- 全体 123 行 → 63 行。変更は本 PR の目的 (マイルストーン参照 API) と無関係
- 失われた内容: 「Repository guidance and review workflow」節 (`.github/agents/pr-review.md` によるレビュー手順、`.github/reports/` への記録ルール、AGENTS.md / GEMINI.md の位置付け)、"Key conventions" の細部 (例: `requirement-02.md` / `requirement-03.md` の参照指示の表現、token contract の具体的な説明)
- 新たに「`.mcp.json` / `.claude/settings.json` で code-review-graph を使う」と記述されているが、`.claude/` はリポジトリ管理下に無く、本 PR にも含まれない
- 期待する修正: 本 PR からこのファイルの変更を外す。別途ドキュメント整理の PR で、失われた節を復元しつつ差分を最小化する

### [Medium] M-2: ルールの閲覧権限の記述が矛盾している (.hermes/rules/milestones.md:37 と :38-41)
- 37 行目「閲覧はグループ単位(既存のトークン `group_id` でフィルタ)」は既存の記述
- 38 行目以降の追記は「所属イベントは全グループから取得し、`group_id` では絞り込まない」
- 影響: 同じファイル内で閲覧ルールが食い違う。マイルストーン一覧 (`/milestone/all`) は group フィルタを受けないため、閲覧単位の仕様が曖昧
- 期待する修正: 37 行目を「マイルストーン本体は全グループ共有。所属イベントの参照は admin のみで全グループ横断」のように整理し、矛盾を解消する

### [Medium] M-3: テストの不足
本 PR のテストで未カバーの点:
1. 未認証 (トークン無し・期限切れ) での 401 を確認するテストが無い。`require_token` 任せにしているが、新エンドポイントで契約が保たれることを確認すべき
2. 非 admin かつ存在しない ID へのアクセスで 403 が優先されるか (現状の実装では 403 が先) を確認するテストが無い。意図として明文化されていない
3. 他マイルストーンのイベントが混入しないこと (`milestone_id` の絞り込み) を確認するテストが無い。現テストは全イベントが同じ milestone に属する構成
4. 自動 closed (`close_expired_waiting_milestones`) 後に `/milestone/closed/{id}/events` が 200 を返すこと、spec §5 の「自動 close も含む」の検証が無い。task-11 のテストと組み合わせた結合テストとして追加すべき
5. closed 後に子イベントの `milestone_id` が外れた場合 (remove 相当) の挙動の確認が無い (現状の仕様では外れたイベントは一覧に出ないはず)
6. `to_dict()` の全キー (spec §3 の 10 キー) と日時フォーマット `%Y-%m-%dT%H:%M:%S.000Z` の検証が無い。現テストは id / group / milestone_id のみ確認
7. イベントが 0 件の closed 側 (空配列 200) のテストが無い。open 側のみ存在する

### [Low] L-1: 2 つの endpoint の実装が重複している (app/routers/timetable.py:294-337 付近)
- 認証チェック、イベント取得、返却処理が同一で、状態フィルタだけが異なる
- 期待する修正: `_get_milestone_events(db, milestone_id, statuses)` のような共通ヘルパーに寄せる (変更は小さく、任意)

### [Low] L-2: 差分内の表記の揺れ
- `.github/copilot-instructions.md` と `app/tokens.py:71` で「Bearer ***」と表示されている箇所がある。ターミナル出力のマスキングによるものか、実際のテキストかは確認できなかった。実際のテキストであれば、トークン契約の説明として誤り (`Authorization: Bearer <token>` が正しい)
- index.html の文言変更 (time-table-to-line → calendar-to-timeline) は本 PR のスコープ外。意図的なら別 PR 扱いが望ましい

### [Info] I-1: 作業ツリーの状態 (レビュー対象外)
- ローカル作業ツリーに `docs/architecture/README.md` の変更、未追跡の `docs/architecture/2026-10-15-architecture.md` と `.claude/` がある。PR には含まれない

## 改善提案

優先順位順:
1. (H-1, H-2) app/config.py の変更を本 PR から外す。本番 URL の切替と既定値変更は別 PR で、PR 本文に理由を書く
2. (M-1) .github/copilot-instructions.md の変更を本 PR から外す
3. (M-2) .hermes/rules/milestones.md の閲覧権限の記述を整理し、矛盾を解消する
4. (M-3) テストを追加する。優先度は 4 (自動 closed 後の closed 側) > 3 (他マイルストーン混入) > 1 (401) > 6 (レスポンス形式)
5. (H-2 関連) 間隔の既定値 (10 分 / 60 分) を rules・task-11・config で統一する
6. (L-1) 2 endpoint の共通化は任意

## タスク番号の割り当て用

後で task 番号を付与しやすいように、指摘を ID で管理している:
- H-1 APP_URL 既定値 (config)
- H-2 マイルストーン設定既定値 (config) と間隔の矛盾
- M-1 copilot-instructions.md の書き換え
- M-2 rules の閲覧権限の矛盾
- M-3 テスト不足 (1〜7)
- L-1 endpoint 重複
- L-2 表記揺れ・スコープ外変更
- I-1 作業ツリーの状態
