#!/usr/bin/env python3
"""watchmedo が変更イベントごとに起動する worker。

変更された .py ファイルに対し auto-skill-python-review-checklist スキルを
ロードした Hermes サブプロセス(review サブエージェント)を並列起動してレビュー結果を reports/ に書く。

watchdog は保存時に created/modified を連続発火するため、状態を STATE_DIR で管理し:
  - デバウンス: 同一ファイルの直近通知から REVIEW_DEBOUNCE 秒以内はスキップ
  - 並列上限: 実行中レビュー数が REVIEW_MAX_PARALLEL 未満のときだけ起動
  - 重複抑止: 同一ファイルのレビューが実行中ならスキップ

モード:
  watch <src> <event>   watchmedo から呼ばれる: フィルタ→スキップ判定→子プロセスで run を生成して即 return
  run <path>            子プロセス側: hermes chat を await し終了時にカウンタ/進行フラグを解放
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

# ---- watchmedo から注入される環境変数 ----
SRC = os.environ.get("watch_src_path", "")       # 変更されたファイルパス
EVENT = os.environ.get("watch_event_type", "")   # created / modified / deleted / moved

# ---- 設定(環境変数で上書き可) ----
ROOT = Path(os.environ.get("WATCH_ROOT", ".")).resolve()
DEBOUNCE = float(os.environ.get("REVIEW_DEBOUNCE", "8"))
MAX_PARALLEL = int(os.environ.get("REVIEW_MAX_PARALLEL", "3"))
SKILL = os.environ.get("REVIEW_SKILL", "auto-skill-python-review-checklist")
REPORT_DIR = Path(os.environ.get("REVIEW_REPORT_DIR", str(ROOT / "reports"))).resolve()
MODEL = os.environ.get("REVIEW_MODEL", "")       # 未指定なら hermes デフォルト

STATE_DIR = REPORT_DIR / ".state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
LAST_FILE = STATE_DIR / "last.ts"
ACTIVE_FILE = STATE_DIR / "active.txt"
COUNTER_FILE = STATE_DIR / "running.txt"


def log(msg: str) -> None:
    print(f"[review {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def is_python(p: Path) -> bool:
    return p.suffix == ".py"


def ignored(p: Path) -> bool:
    for part in p.parts:
        if part in {".venv", "__pycache__", ".git", "node_modules", "reports", "devtools"}:
            return True
    return False


def _read_lines(fp: Path) -> dict[str, float]:
    try:
        d = {}
        for line in fp.read_text().splitlines():
            if "\t" in line:
                k, _, v = line.partition("\t")
                d[k] = float(v)
        return d
    except (FileNotFoundError, ValueError):
        return {}


def is_debounced(p: Path) -> bool:
    """同一ファイルの直近通知から DEBOUNCE 秒以内なら True(通知は記録する)。"""
    m = _read_lines(LAST_FILE)
    key = str(p)
    now = time.time()
    debounced = (now - m.get(key, 0.0)) < DEBOUNCE
    m[key] = now
    LAST_FILE.write_text("\n".join(f"{k}\t{v}" for k, v in m.items()) + "\n")
    return debounced


def running_files() -> set[str]:
    try:
        return set(ACTIVE_FILE.read_text().splitlines())
    except FileNotFoundError:
        return set()


def add_active(key: str) -> bool:
    s = running_files()
    if key in s:
        return False
    s.add(key)
    ACTIVE_FILE.write_text("\n".join(sorted(s)) + "\n")
    return True


def remove_active(key: str) -> None:
    s = running_files()
    s.discard(key)
    ACTIVE_FILE.write_text("\n".join(sorted(s)) + "\n")


def try_slot() -> bool:
    """並列数計上。上限未満なら True(count を increment 済み)。"""
    try:
        n = int(COUNTER_FILE.read_text().strip() or "0")
    except (FileNotFoundError, ValueError):
        n = 0
    if n >= MAX_PARALLEL:
        return False
    COUNTER_FILE.write_text(str(n + 1))
    return True


def release_slot() -> None:
    try:
        n = int(COUNTER_FILE.read_text().strip() or "0")
    except (FileNotFoundError, ValueError):
        n = 0
    COUNTER_FILE.write_text(str(max(0, n - 1)))


def build_query(target: Path) -> str:
    return (
        f"[レビュー依頼]\n"
        f"あなたは auto-skill-python-review-checklist スキルを skill_view でロードして従う"
        f"レビュー担当サブエージェントです。\n"
        f"対象ファイル: {target}\n"
        f"- 読み取り専用: いかなるファイルも変更しないこと\n"
        f"- スキルの『明示的なファイル指定を優先する』規則に従い、上記1ファイルをレビュー対象に\n"
        f"- 出力はスキル指定の Markdown レポート形式で最終応答にまとめてください\n"
    )


def do_review(path: Path):
    """子プロセス側: hermes chat を await し、終了後フラグを解放してレポートを保存。"""
    key = str(path.resolve())
    query = build_query(path)
    qf = STATE_DIR / f"q-{path.stem}-{int(time.time())}.txt"
    qf.write_text(query)
    cmd = ["hermes", "chat", "-Q", "--query-file", str(qf), "-s", SKILL]
    if MODEL:
        cmd += ["-m", MODEL]
    report = REPORT_DIR / f"{'-'.join(path.relative_to(ROOT).with_suffix('').parts)}-{int(time.time())}.md"
    log(f"reviewing {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True,
                              text=True, timeout=1800)
        report.write_text((proc.stdout or "") + "\n\n--- stderr ---\n" + (proc.stderr or ""))
        log(f"written {report.relative_to(ROOT)} (rc={proc.returncode})")
    except Exception as e:
        log(f"error {path}: {e}")
        report.write_text(f"ERROR: {e}\n")
    finally:
        try:
            qf.unlink()
        except OSError:
            pass
        release_slot()
        remove_active(str(path))


def main_watch(src_s: str | None = None, event: str | None = None):
    src_s = src_s or SRC
    event = event or EVENT
    if not src_s or event in ("deleted", "moved"):
        return
    src = Path(src_s).resolve()
    if not is_python(src) or ignored(src) or not src.exists():
        return
    key = str(src)
    if is_debounced(src):
        log(f"debounce skip: {src.name}"); return
    if not add_active(key):
        log(f"already reviewing: {src.name}"); return
    if not try_slot():
        remove_active(key)
        log(f"parallel full ({MAX_PARALLEL}): skip {src.name}"); return
    # 占有は子(run モード)に移譲: 親は即 release しない。子レビュー完了時に解放。
    subprocess.Popen(
        [sys.executable, str(Path(sys.argv[0])), "run", str(src)],
        start_new_session=True,
    )
    log(f"spawned review for {src.name}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "run":
        do_review(Path(args[1]))
    elif len(args) >= 3 and args[0] == "watch":
        main_watch(args[1], args[2])
    else:
        main_watch()