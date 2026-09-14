# アーキテクチャスナップショット: 2026-09-11

## 目的 (Purpose)
マイルストーンを `waiting` 状態から `open`（再 open）へ戻す際、waiting 遷移時に一括で完了（`completed=True`）にした子イベントのステータスを非完了（`completed=False`）にリセットし、イベントの配色をマイルストーンカラーへ復帰させることで、直感的なステータス操作とUI整合性を実現する。

## 概要 (Overview)
- **挙動変更**: 再 open 処理（re-open）時に、所属する全子イベントの `completed` ステータスを一括で `False` に更新する処理を追加。

## キーとなる技術的変更 (Key design decisions)
- **ステータス整合性の維持**: `app/routers/timetable.py` における re-open のロジックを拡張し、`waiting` 遷移時との対称性を確保。
- **ルール文書の更新**: `.hermes/rules/milestones.md` を更新し、re-open 時の仕様変更（非破壊から復帰挙動へ）を明文化。

## コミットリスト
- feat: waiting からの re-open で子イベント completed=False に戻すロジックの実装

## 変更されたファイル
- app/routers/timetable.py
- .hermes/rules/milestones.md
- tests/test_milestone.py
