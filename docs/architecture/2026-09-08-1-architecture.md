# アーキテクチャスナップショット: 2026-09-08-1

## 目的 (Purpose)
マイルストーンが「達成」されてから「確定（closed）」するまでに 5 日間の猶予期間（グレース期間）を設け、その後のクローズ処理を自動化することで、管理者の運用負荷を軽減しつつ、誤操作時の再 open（re-open）を可能にすることを目的としています。

## 概要 (Overview)
- **状態遷移**: マイルストーンに `accomplished_date` が設定されると `waiting` 状態になります。
- **自動化**: `waiting` 状態のまま猶予期間を過ぎたマイルストーンを、バックグラウンドジョブが検知して自動的に `closed` 状態へ遷移させます。
- **実行基盤**: FastAPI の `lifespan` プロトコルを使用して、アプリケーションの起動・停止に合わせて `APScheduler` を管理しています。

## キーとなる技術的変更 (Key design decisions)
- **Lifespan 統合**: `app/main.py` にて `asynccontextmanager` を用いた `lifespan` を実装し、スケジューラの安全な起動とシャットダウンを実現しています。
- **純粋関数によるロジック分離**: `app/jobs/close_milestones.py` の `close_expired_waiting_milestones` は、引数として DB セッションと日付を受け取る設計になっており、現在時刻に依存せずユニットテストが容易な構造になっています。
- **柔軟な設定**: 猶予日数 (`MILESTONE_CLOSE_GRACE_DAYS`) や実行間隔、スケジューラの有効化フラグを環境変数で制御可能です。
- **冪等な状態遷移**: `waiting` 遷移時に子イベントを `completed=True` に更新しますが、自動 `closed` 遷移時は子イベントを操作しないことで、ロジックの単純化と副作用の抑制を図っています。

## 今後の改善点 (Next steps/improvements)
- **子イベントの色の同期**: マイルストーンが `closed` になった際、フロントエンド側で子イベントの色をデフォルト（#2196f3）に戻すロジックの整合性確認（またはバックエンドでの明示的なフラグ提供）。
- **ロギングの強化**: 自動クローズされた件数や、エラー発生時の詳細を構造化ログとして出力する仕組みの導入。
- **re-open 時の整合性**: マイルストーンを `waiting` から `open` に戻した際、既に `completed=True` になった子イベントをどう扱うかの検討（現在は非破壊的に True のまま維持）。
- **手動実行 API**: 運用保守用に、スケジューラを待たずに即時クローズジョブを実行できる admin 専用エンドポイントの検討。

## コミットリスト
- d331b53 (HEAD -> feature/automate-close/11) docs #(task11): 自動 closed の実装を反映
- b8cd51f test #(task11): グレース期間後の自動 closed 遷移のテストを追加
- c47f0d1 feat #(task11): FastAPI lifespan で猶予チェック用スケジューラを起動/停止
- 8c8ca65 feat #(task11): waiting 猶予超過のマイルストーンを closed へ一括遷移するジョブ関数
- 836da2e feat #(task11): apscheduler 追加と猶予日数/実行間隔設定を config 化

## 変更されたファイル
- .gitignore
- .hermes/rules/milestones.md
- AGENTS.md
- app/config.py
- app/jobs/__init__.py
- app/jobs/close_milestones.py
- app/main.py
- app/routers/timetable.py
- app/scheduler.py
- pyproject.toml
- requirement-03.md
- specs/2026-09-07-spec.md
- tests/test_milestone.py
