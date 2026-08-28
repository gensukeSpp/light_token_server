#!/usr/bin/env bash
# Launcher: watchmedo で .py 変更を監視し、review_worker.py を起動して
# auto-skill-python-review-checklist スキルをサブエージェントで並列レビューさせる。
#
# 使い方:
#   devtools/watch_reviews.sh            # venv の watchmedo で監視開始
#   REVIEW_MAX_PARALLEL=5 devtools/watch_reviews.sh   # 並列数を上書き
#   REVIEW_MODEL='anthropic/claude-sonnet-4' devtools/watch_reviews.sh
#
# 停止: Ctrl-C (watchmedo 側のサブプロセスも終了する)
set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# ---- venv を確実に活性化(watchmedo が .venv/bin に無いと失敗するため) ----
if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
else
    echo "ERROR: .venv が見つかりません。先に 'uv sync' を実行してください。" >&2
    exit 1
fi
if ! command -v watchmedo >/dev/null 2>&1; then
    echo "ERROR: watchmedo がありません。'uv add watchdog' で入れてください。" >&2
    exit 1
fi

echo "Python:  $(command -v python)"
echo "watchmedo: $(command -v watchmedo)"
echo "parallel:  ${REVIEW_MAX_PARALLEL:-3}"
echo "watch dir: $ROOT"
echo "Ctrl-C で停止"

# watchmedo shell-command:
#   --recursive            サブディレクトリも監視
#   --patterns='*.py'      .py のみ対象
#   --ignore-directories   .py ディレクトリ自体は無視
#   --command=...          変更イベントごとに worker を起動
# watchmedo は事件情報を環境変数ではなく string.Template 置換で渡すため、
# ${watch_src_path} / ${watch_event_type} をコマンド文字列内に埋め込む
# (シェル展開されないよう \ でエスケープし、watchmedo 側で置換される)。
watchmedo shell-command \
    --recursive \
    --patterns '*.py' \
    --ignore-directories \
    --command "WATCH_ROOT='$ROOT' python '$ROOT/devtools/review_worker.py' watch '\${watch_src_path}' '\${watch_event_type}'" .