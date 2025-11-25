#!/usr/bin/env python3
"""
Minimal TUI to watch delegate tasks.
- Left pane: recent tasks (id, status, summary)
- Right pane: live tail of selected task stream
"""

import json
import os
import time
import curses
from pathlib import Path
import textwrap

RUNTIME_DIR = Path(__file__).parent / "runtime"
STREAM_FILE = RUNTIME_DIR / "delegate.stream"
OUT_FILE = RUNTIME_DIR / "delegate.out"

MAX_TASKS = 200
LOG_MAX_LINES = 500
OUT_CACHE_TTL = 0.5


def load_stream():
    STREAM_FILE.touch(exist_ok=True)
    with STREAM_FILE.open() as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.2)
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            yield ev


def draw(screen):
    curses.curs_set(0)
    screen.nodelay(True)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)   # ok
    curses.init_pair(2, curses.COLOR_YELLOW, -1)  # pending
    curses.init_pair(3, curses.COLOR_RED, -1)     # error/timeout
    curses.init_pair(4, curses.COLOR_CYAN, -1)    # label

    height, width = screen.getmaxyx()
    split = max(40, int(width * 0.45))

    tasks = []          # list of dict {id,status,summary,label,duration}
    logs = {}           # task_id_full -> list of lines
    selected = 0

    stream = load_stream()
    last_redraw = 0
    last_out_read = 0
    out_status = {}

    while True:
        # consume events quickly
        try:
            ev = next(stream)
            tid_full = ev.get("task_id", "")
            label = ev.get("label", "")
            if ev.get("type") == "request":
                summary = ev.get("instruction", "")
                tasks = [{"id": tid_full, "status": "pending", "summary": summary, "label": label, "duration": None}] + tasks
                tasks = tasks[:MAX_TASKS]
            elif ev.get("type") == "stream":
                line = ev.get("line", "")
                logs.setdefault(tid_full, []).append(line)
                logs[tid_full] = logs[tid_full][-LOG_MAX_LINES:]
            elif ev.get("type") == "final":
                status = ev.get("status", "")
                duration = ev.get("duration_ms")
                tasks = [
                    {**t, "status": status if t["id"] == tid_full else t["status"], "duration": duration if t["id"] == tid_full else t["duration"]}
                    for t in tasks
                ]
            elif ev.get("type") == "error":
                logs.setdefault(tid_full, []).append(f"[error] {ev.get('error','')}")
        except StopIteration:
            pass
        except Exception:
            pass

        # handle input
        ch = screen.getch()
        if ch == ord("q"):
            break
        if ch == curses.KEY_DOWN:
            selected = min(len(tasks) - 1, selected + 1)
        if ch == curses.KEY_UP:
            selected = max(0, selected - 1)

        # refresh delegate.out for statuses
        now = time.time()
        if now - last_out_read > OUT_CACHE_TTL and OUT_FILE.exists():
            try:
                with OUT_FILE.open() as f:
                    out_status.clear()
                    for line in f:
                        try:
                            obj = json.loads(line)
                            out_status[obj["task_id"]] = obj
                        except Exception:
                            continue
            except Exception:
                pass
            last_out_read = now

        # redraw throttled
        now = time.time()
        if now - last_redraw < 0.1:
            continue
        last_redraw = now

        screen.erase()
        height, width = screen.getmaxyx()
        split = max(40, int(width * 0.45))

        # header
        screen.addstr(0, 0, "Delegate TUI  q=quit  ↑↓ select")
        screen.hline(1, 0, curses.ACS_HLINE, width)

        # tasks pane
        header = "   ID        STATUS    DUR  LABEL         SUMMARY"
        screen.addnstr(2, 0, header, split - 1, curses.A_BOLD)
        for row, t in enumerate(tasks[: height - 4], start=3):
            marker = ">" if row - 3 == selected else " "
            status = t["status"]
            # sync with out_status if newer
            if t["id"] in out_status:
                status = out_status[t["id"]].get("status", status)
                t["status"] = status
                t["duration"] = out_status[t["id"]].get("duration_ms", t.get("duration"))
            color = curses.color_pair(1 if status == "ok" else 2 if status == "pending" else 3)
            summary = textwrap.shorten(t["summary"], width=split - 35, placeholder="…")
            label = textwrap.shorten(t.get("label", ""), width=12, placeholder="…")
            dur = ""
            if t.get("duration"):
                dur = f"{int(t['duration'])//1000:>3}s"
            line = f"{marker} {t['id'][:8]:<8} {status:<8} {dur:>4} {label:<12} {summary}"
            screen.addnstr(row, 0, line, split - 1, color)

        # log pane
        if tasks:
            t = tasks[selected]
            tid = t["id"]
            lines = logs.get(tid, [])
            max_lines = height - 4
            display = lines[-max_lines:]
            title = f"{tid[:8]} {t['status']} {t.get('label','')}"
            screen.addnstr(2, split + 1, title, width - split - 2, curses.A_BOLD)
            for i, l in enumerate(display):
                wrapped = textwrap.wrap(l, width=width - split - 3) or [""]
                for j, wline in enumerate(wrapped):
                    if i + j >= max_lines:
                        break
                    screen.addnstr(3 + i + j, split + 1, wline, width - split - 2)

        screen.refresh()
        time.sleep(0.05)


def main():
    curses.wrapper(draw)


if __name__ == "__main__":
    main()
