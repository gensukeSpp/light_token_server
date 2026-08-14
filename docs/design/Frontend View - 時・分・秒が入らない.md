---
created: 2026-08-14T11:19
updated: 2026-08-14T11:25
---
## Issue 1: start_time/end_time に時・分・秒が入らない問題
- ~~報告の「src/hooks/useMutation.ts 14 行目 console.log」は実ファイル名としては useEventMutation.ts の可能性が高いと判断した（useMutation.ts は存在しない）~~ useEventMutation.ts です。
- 送信経路: TitleInput → createEvent.mutate → basicAxios.post('/event/add', timelineEvent)。タイムラインイベントは Date 型で、Axios によるシリアル化の際にバックエンド側で時分秒が欠ける可能性を仮説として立てた。もう1つの可能性として、そもそもフロントで start==end  の Date が作られてしまっている可能性も確認対象にした。
- 調査タスク: 送信データの一時確認 → resolveSlotEnd と InputTitleDialog の境界ケース追加テスト → ミューテーションボディの送信形式の 見直し → backend /event/add 受信ロジック確認 → 実ブラウザで時分秒 が入ることを確認。

- Issue 1 の原因理解に必要な backend の事実として、以下を整理した 。
  - frontend が送る start_time/end_time は EventCreate で「str」型として受け取る。
  - 永続化モデル T_TIMELINE_EVENT の start_time/end_time は Date() カラム。timestamps を持たない日付型。
  - convert_str_to_date は ISO 文字列の .dddZ を削り T を空白に置 き換えて datetime に変換するが、この datetime は時分秒を含む。
  - 永続化カラムが Date なので、時分秒は DB に入る段階で日付成分だけ残る（時分秒情報は失われる）。
  - EventORM.to_dict は start_time/end_time を %Y-%m-%dT%H:%M:%S.000Z 形式の文字列に整形して返すため、フロントには「.000Z」の形で戻 ってくる。
